"""彩票抽卡（Scratch Lottery）纯定义：奖级赔率 + 出票反演 + 抽卡次数候选。

仅含常量与纯函数，无 DB/ORM 依赖（镜像 cash.py / gamification.py 的分层规则）。
- LotteryService.draw 用 draw_outcome + build_ticket 出票；
- LotteryService._sync_grants 用 build_grant_candidates 生成补发候选。

移植自 E:\\share\\caipiao（体彩顶呱刮「点石成金」20 元票模拟器，原版为纯前端 JS）：
- js/game.js L62-68   draw_outcome：累计概率抽样；
- js/game.js L100-160 build_ticket：先抽结果再反演票面（按票面规则人工核对 === prize）；
- js/game.js L164-176 split_amount：金砖奖拆成 20 个「像真票的」小金额。
原版 20 币/张的扣费逻辑不移植——本项目抽卡免费，抽卡次数是唯一货币（学习行为赚取），
中奖金额进独立彩金余额 Member.lottery_wealth（与现金激励 cash_balance 完全分开）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from app.gamification import BADGES

# ── 票面玩法（照抄真票：中奖号码 5 格 + 你的号码 20 格，兼中兼得）──
TICKET_NAME = "点石成金"
TICKET_PRICE = 20  # 票面标注面值，仅用于 RTP 展示口径（抽卡不扣钱）
TOP_PRIZE = 100  # 2026-08 定档：大奖封顶 100（原 100 万，200 以上档已全部删除）
NUMBER_MAX = 99  # 号码范围 01~99
WIN_NUMBER_COUNT = 5
MY_CELL_COUNT = 20

# 特殊符号规则：cash 中该格金额；rmb 中 5 倍；gold 中 20 格金额之和
SPECIALS = {"cash": "🪙", "rmb": "💴", "gold": "🧱"}

# 诱饵金额：未中奖格随机展示的「差一点」奖金（与奖级表同步封顶 100，不再出现 200/500）
DECOY_AMOUNTS = (20, 20, 20, 40, 40, 40, 60, 60, 60, 80, 80, 80, 100, 100, 100, 100)

# 9 级赔率 (prize, one_in)：返还率≈15.5%、中奖率≈50.4%（两张基本中一张）。
# 2026-08 按用户定档调整（原为真票 20~100 万 12 级、返还率≈65%）：
#   新增 1/2/5 高频小奖（1/4、1/8、1/16）+ 10 补档（原表无）；
#   20 档概率 ÷2，40/60 档 ÷4，80/100 档 ÷8；200 以上档全部删除，大奖封顶 100。
# 调概率只改这里；想改票面坐标/手感改前端 constants/lottery.ts（沿用原版「只改 config」约定）。
REAL_ODDS: tuple[tuple[int, int], ...] = (
    (100, 720),
    (80, 440),
    (60, 104),
    (40, 40),
    (20, 90),
    (10, 60),
    (5, 16),
    (2, 8),
    (1, 4),
)

# 中奖演出方式权重（大奖一律可用「号码匹配」，更有戏剧性——原版 game.js L126-135）
MECH_WEIGHTS = {"match": 0.6, "cash": 0.15, "rmb": 0.15, "gold": 0.1}

# ── 抽卡次数获取规则 ──
INIT_GRANT_DRAWS = 5  # init:boot 一笔补偿 5 次（弥补系统上线前）
PRACTICE_PER_DRAW = 5  # 终身累计每 5 场 ended 练习 = 1 次


def draw_outcome(rng: random.Random) -> int:
    """按赔率表抽一张票的结果，返回中奖金额（0 = 未中奖）。

    累计概率抽样，与原版 game.js drawOutcome 逐行等价；rng 注入便于 seeded 单测。
    """
    r = rng.random()
    for prize, one_in in REAL_ODDS:
        r -= 1.0 / one_in
        if r < 0:
            return prize
    return 0


def calc_odds_stats() -> dict:
    """理论返还率（RTP）与中奖率（测试断言与前端展示用）。"""
    rtp = sum(prize / one_in for prize, one_in in REAL_ODDS)
    hit_rate = sum(1.0 / one_in for _prize, one_in in REAL_ODDS)
    return {"rtp": rtp / TICKET_PRICE, "hit_rate": hit_rate}


def split_amount(amount: int, count: int, rng: random.Random) -> list[int]:
    """把总额拆成 count 个「像真票的」金额（10 的倍数、小的多大的少）。

    金砖玩法专用；amount 必须是 10 的倍数且 ≥ count×10。2026-08 奖级封顶 100 后
    已无 gold 资产档（400~5000），build_ticket 当前不会走到此路径；保留给未来
    恢复高额档时用（单测仍覆盖）。原版 game.js L164-176：全 10 起步、偏小分布抽增量、
    单格上限 500、guard 5000 防死循环、残量兜底塞随机格。
    """
    if amount % 10 != 0 or amount < count * 10:
        raise ValueError(f"split_amount 要求 10 的倍数且 ≥ {count * 10}: {amount}")
    parts = [10] * count
    rest = amount - count * 10
    choices = (10, 10, 10, 20, 20, 40, 60, 90, 240, 490)  # 偏小奖的分布
    guard = 0
    while rest > 0 and guard < 5000:
        guard += 1
        i = rng.randrange(count)
        step = min(choices[rng.randrange(len(choices))], rest)
        if parts[i] + step <= 500:
            parts[i] += step
            rest -= step
    if rest > 0:  # 兜底（理论上不会走到）
        parts[rng.randrange(count)] += rest
    return parts


def _pick_mech(prize: int, rng: random.Random) -> str:
    """按资格表 + 权重选一种中奖演出方式（原版 game.js L126-135）。

    match 恒可选；cash 需 20≤prize≤1000；rmb 需 prize%5==0 且 100≤prize≤10000；
    gold 需 400≤prize≤5000。加权随机在可选集内进行（总权重归一）。
    """
    mechs = ["match"]
    if 20 <= prize <= 1000:
        mechs.append("cash")
    if prize % 5 == 0 and 100 <= prize <= 10000:
        mechs.append("rmb")
    if 400 <= prize <= 5000:
        mechs.append("gold")
    r = rng.random() * sum(MECH_WEIGHTS[m] for m in mechs)
    for m in mechs:
        r -= MECH_WEIGHTS[m]
        if r < 0:
            return m
    return mechs[0]


def build_ticket(prize: int, rng: random.Random) -> dict:
    """生成一张票的完整数据（game.js L100-160 移植）。

    思路：先按概率抽出结果金额 prize，再把它「演」成真票上的一种中奖方式，
    保证按票面规则人工核对的结果 === prize，其余格子绝不产生额外中奖。

    格子结构（你的号码，20 格）：
      {"kind": "num",  "num": 88, "amt": 100}  普通号格：num 撞中奖号才中 amt
      {"kind": "cash", "amt": 500}             现金币：必中 amt
      {"kind": "rmb",  "amt": 100}             人民币：必中 5×amt
      {"kind": "gold", "amt": 60}              金砖：必中 20 格金额之和
    wins 构建时算好（idx/amount/reason），结算高亮直接用。
    """
    pool = list(range(1, NUMBER_MAX + 1))
    # 不放回抽 5 个中奖号 + 20 个你的号 → 落空票「绝不撞号」由构造直接保证
    win_numbers: list[int] = []
    for _ in range(WIN_NUMBER_COUNT):
        win_numbers.append(pool.pop(rng.randrange(len(pool))))
    nums: list[int] = []
    for _ in range(MY_CELL_COUNT):
        nums.append(pool.pop(rng.randrange(len(pool))))

    cells = [
        {"kind": "num", "num": n, "amt": DECOY_AMOUNTS[rng.randrange(len(DECOY_AMOUNTS))]}
        for n in nums
    ]
    wins: list[dict] = []

    if prize > 0:
        mech = _pick_mech(prize, rng)
        idx = rng.randrange(len(cells))
        if mech == "match":
            cells[idx]["num"] = win_numbers[rng.randrange(len(win_numbers))]
            cells[idx]["amt"] = prize
            wins.append({"idx": idx, "amount": prize, "reason": "号码匹配"})
        elif mech == "cash":
            cells[idx] = {"kind": "cash", "amt": prize}
            wins.append({"idx": idx, "amount": prize, "reason": "现金币"})
        elif mech == "rmb":
            cells[idx] = {"kind": "rmb", "amt": prize // 5}
            wins.append({"idx": idx, "amount": prize, "reason": "人民币 ×5"})
        else:  # gold：先把 20 格金额凑成恰好等于 prize，金砖格自己也占一份
            parts = split_amount(prize, len(cells), rng)
            for c, p in zip(cells, parts):
                c["amt"] = p
            cells[idx] = {"kind": "gold", "amt": parts[idx]}
            wins.append({"idx": idx, "amount": prize, "reason": "金砖 · 20 格金额之和"})

    return {"prize": prize, "win_numbers": win_numbers, "cells": cells, "wins": wins}


# ── 抽卡次数补发候选（懒同步：打开 /lottery/state 时重建全量候选，差集补发）──


@dataclass(frozen=True)
class GrantCandidate:
    """待补发抽卡次数候选（纯数据）。幂等去重由调用方靠 uq_member_lottery_grant 保证。

    key 为「源:粒度标识」全局唯一（如 unit:5 / weekstars:2026-W30:3）；每次同步重建
    候选集、与已发 key 做差，绝不解析已存 key。XP 可被 rejudge 回退 → 段位星跌再涨
    不重发不回收（snapshot 语义，同 cash_milestone）。
    """

    key: str
    source: str  # init/daily/practice/unit/learn_task/review_task/star/badge/weekstars
    draws: int = 1
    remark: str = ""


def build_grant_candidates(
    *,
    today: date,
    ended_practice_count: int,
    units_status: list[dict],
    learn_task_done: bool,
    review_task_done: bool,
    stars: int,
    badge_keys: list[str],
    week_stars: list[tuple[str, int]],
) -> list[GrantCandidate]:
    """根据当下状态生成全部「已达成」的抽卡次数候选（纯函数，便于单测）。

    输入事实全部由 service 查好传入（绝不在纯函数里碰 DB）：
    - ended_practice_count: 终身 ended 练习场数（口径同 StatsRepo.get_practice_summary）
    - units_status: StatsRepo.get_all_units_mastery_status 的返回
    - learn_task_done / review_task_done: 今日 DailyTask 完成标记（repo 已做空槽守卫）
    - stars: xp_to_level(member.total_xp)["stars"]（大师段位后每 1000XP 一星）
    - badge_keys: 已获全部徽章 key（历史全量补发）
    - week_stars: [(week_key, stars)] 已落表周结算（懒回算仅 4 周窗口，超窗少算为已知盲区）
    """
    candidates: list[GrantCandidate] = [
        # ① init：首次同步补偿（候选恒含，发过即被差集跳过）
        GrantCandidate("init:boot", "init", INIT_GRANT_DRAWS, "系统上线补偿"),
        # ② daily：打卡式每日免费（当天不开抽卡页则该天不发，懒哲学）
        GrantCandidate(f"daily:{today:%Y-%m-%d}", "daily", 1, "每日免费抽卡"),
    ]
    # ③ practice：终身累计每 PRACTICE_PER_DRAW 场 ended 练习 = 1 次
    for n in range(1, ended_practice_count // PRACTICE_PER_DRAW + 1):
        candidates.append(GrantCandidate(
            f"practice:{n}", "practice", 1, f"累计完成 {n * PRACTICE_PER_DRAW} 场练习",
        ))
    # ④ unit：每个全掌握单元（mastered>=total>0）
    for u in units_status:
        total = int(u.get("total_words", 0))
        mastered = int(u.get("mastered", 0))
        if total > 0 and mastered >= total:
            uid = int(u["unit_id"])
            candidates.append(GrantCandidate(
                f"unit:{uid}", "unit", 1, f"Unit {uid} 全部学完（{total} 词）",
            ))
    # ⑤⑥ 今日学习 / 今日复习任务（每天最多各 1 次）
    if learn_task_done:
        candidates.append(GrantCandidate(f"learn_task:{today:%Y-%m-%d}", "learn_task", 1, "完成今日学习"))
    if review_task_done:
        candidates.append(GrantCandidate(f"review_task:{today:%Y-%m-%d}", "review_task", 1, "完成今日到期复习"))
    # ⑦ 段位星：每加一星 1 次（星数回退再涨不重发，key 已在）
    for n in range(1, max(stars, 0) + 1):
        candidates.append(GrantCandidate(f"star:{n}", "star", 1, f"段位晋升 {n}⭐"))
    # ⑧ 徽章：每枚 1 次（历史徽章全量补发）
    for k in badge_keys:
        name = BADGES.get(k, {}).get("name", k)
        candidates.append(GrantCandidate(f"badge:{k}", "badge", 1, f"获得徽章「{name}」"))
    # ⑨ 周结算星：每星 1 次（weekstars:{week_key}:{i}）
    for week_key, s in week_stars:
        for i in range(1, max(int(s), 0) + 1):
            candidates.append(GrantCandidate(
                f"weekstars:{week_key}:{i}", "weekstars", 1, f"{week_key} 结算 {s} 星",
            ))
    return candidates
