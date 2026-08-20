"""lottery.py 纯函数测试（无 DB）：抽样 / 票面反演不变量 / 金砖拆分 / 理论赔率 / 蒙特卡洛。

核心性质：build_ticket 产出的票面「按真票规则人工核对的结果 === prize」——
落空票绝不撞号、绝不出现特殊符号；中奖票 wins 金额合计 === prize。
"""
import random

import pytest

from app import lottery
from app.lottery import (
    MY_CELL_COUNT,
    REAL_ODDS,
    SPECIALS,
    WIN_NUMBER_COUNT,
    build_ticket,
    calc_odds_stats,
    draw_outcome,
    split_amount,
)


def replay_ticket_prize(ticket: dict) -> int:
    """按真票规则重放票面求中奖总额（兼中兼得）：
    撞号中该格金额；🪙 中该格金额；💴 中 5 倍；🧱 中 20 格金额之和。
    """
    total = 0
    for c in ticket["cells"]:
        if c["kind"] == "num" and c["num"] in ticket["win_numbers"]:
            total += c["amt"]
        elif c["kind"] == "cash":
            total += c["amt"]
        elif c["kind"] == "rmb":
            total += c["amt"] * 5
        elif c["kind"] == "gold":
            total += sum(x["amt"] for x in ticket["cells"])
    return total


# ── draw_outcome（累计概率抽样）──


def test_draw_outcome_deterministic_with_seed():
    assert draw_outcome(random.Random(42)) == draw_outcome(random.Random(42))


def test_draw_outcome_outside_total_is_zero():
    # r 落在概率总和（≈0.50）之外 → 未中奖；构造 rand 恒返回 0.9 的假 rng
    class _HighRand(random.Random):
        def random(self):
            return 0.9

    assert draw_outcome(_HighRand()) == 0


def test_draw_outcome_all_tiers_reachable():
    # 大样本下 9 级奖均应被抽到过（最稀的 100 档 1/720，20 万样本期望 ~278 次）
    rng = random.Random(7)
    seen = {draw_outcome(rng) for _ in range(200_000)}
    assert set(p for p, _ in REAL_ODDS) <= seen


# ── build_ticket：落空票不变量 ──


def test_losing_ticket_never_matches():
    rng = random.Random(1)
    for _ in range(200):
        t = build_ticket(0, rng)
        assert t["prize"] == 0
        assert t["wins"] == []
        assert len(t["win_numbers"]) == WIN_NUMBER_COUNT
        assert len(t["cells"]) == MY_CELL_COUNT
        nums = [c["num"] for c in t["cells"]]
        assert len(set(nums)) == MY_CELL_COUNT  # 20 格号码互不相同
        assert not set(nums) & set(t["win_numbers"])  # 绝不撞号
        assert all(c["kind"] == "num" for c in t["cells"])  # 绝无特殊符号
        assert replay_ticket_prize(t) == 0


def test_winning_ticket_replay_equals_prize():
    """核心不变量：无论哪种演出方式，重放票面规则 === prize（金额全档覆盖）。"""
    rng = random.Random(2)
    prizes = [p for p, _ in REAL_ODDS]
    for _ in range(50):
        for prize in prizes:
            t = build_ticket(prize, rng)
            assert replay_ticket_prize(t) == prize
            assert sum(w["amount"] for w in t["wins"]) == prize


@pytest.mark.parametrize("mech,prize", [
    ("match", 100),        # match 恒可选（封顶大奖用号码匹配更有戏剧性）
    ("cash", 80),          # cash 需 20≤prize≤1000
    ("rmb", 100),          # rmb 需 %5==0 且 100~10000（100//5=20）
    ("gold", 1000),        # gold 需 400~5000（当前奖级表无此档，保留路径回归）
])
def test_each_mech_plays_out(monkeypatch, mech, prize):
    monkeypatch.setattr(lottery, "_pick_mech", lambda p, r: mech)
    rng = random.Random(3)
    for _ in range(20):
        t = build_ticket(prize, rng)
        w = t["wins"][0]
        idx = w["idx"]
        assert w["amount"] == prize
        assert replay_ticket_prize(t) == prize
        if mech == "match":
            cell = t["cells"][idx]
            assert cell["kind"] == "num" and cell["num"] in t["win_numbers"] and cell["amt"] == prize
        elif mech == "cash":
            assert t["cells"][idx] == {"kind": "cash", "amt": prize}
        elif mech == "rmb":
            assert t["cells"][idx] == {"kind": "rmb", "amt": prize // 5}
            assert t["cells"][idx]["amt"] * 5 == prize
        else:
            assert t["cells"][idx]["kind"] == "gold"
            assert sum(c["amt"] for c in t["cells"]) == prize  # 金砖 = 20 格金额之和


def test_mech_eligibility_guards():
    # 资格表：非 10 倍数且 <400 的大奖只能 match/cash（如 100）；
    # 10000000 超出 cash/rmb/gold 全部上限 → 只剩 match
    for prize in (20, 100, 400, 5000, 10000, 100000, 1000000):
        mechs = ["match"]
        if 20 <= prize <= 1000:
            mechs.append("cash")
        if prize % 5 == 0 and 100 <= prize <= 10000:
            mechs.append("rmb")
        if 400 <= prize <= 5000:
            mechs.append("gold")
        rng = random.Random(prize)
        seen_mecks = set()
        for _ in range(300):
            seen_mecks.add(lottery._pick_mech(prize, rng))
        assert seen_mecks == set(mechs)
        assert "match" in seen_mecks  # match 恒可选


def test_specials_symbols_complete():
    # 三种特殊符号都有定义（前端渲染依赖）
    assert set(SPECIALS) == {"cash", "rmb", "gold"}


# ── split_amount（金砖拆分）──


def test_split_amount_properties():
    rng = random.Random(4)
    for amount in (500, 1000, 5000):
        parts = split_amount(amount, 20, rng)
        assert sum(parts) == amount
        assert len(parts) == 20
        assert all(p >= 10 for p in parts)          # 全 ≥10
        assert all(p % 10 == 0 for p in parts)      # 全 10 的倍数
        assert max(parts) <= 500 or sum(parts) == amount  # 单格 ≤500（残量兜底理论不触发）


def test_split_amount_invalid_inputs():
    rng = random.Random(5)
    with pytest.raises(ValueError):
        split_amount(205, 20, rng)   # 非 10 的倍数
    with pytest.raises(ValueError):
        split_amount(100, 20, rng)   # < 20×10


# ── 理论赔率与蒙特卡洛（原版 simRTP 同款认知）──


def test_calc_odds_stats():
    stats = calc_odds_stats()
    assert 0.10 < stats["rtp"] < 0.20          # 理论 ≈15.5%
    assert 0.45 < stats["hit_rate"] < 0.55     # 理论 ≈50.4%（两张基本中一张）


def test_prize_table_policy():
    # 2026-08 定档：大奖封顶 100、新增 1/2/5/10 小奖档（小额常中、无高额）
    prizes = {p for p, _ in REAL_ODDS}
    assert max(prizes) == 100
    assert {1, 2, 5, 10} <= prizes


def test_monte_carlo_rtp_close_to_theory():
    rng = random.Random(6)
    n = 50_000
    won = sum(draw_outcome(rng) for _ in range(n))
    rtp = won / (n * lottery.TICKET_PRICE)
    assert abs(rtp - calc_odds_stats()["rtp"]) < 0.02  # 无头奖后方差小，容差收紧
