from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cash import build_badge_reward_candidates
from app.services.badge_service import award_badge_if_new


# ── award_badge_if_new（幂等发放基元）──
@pytest.mark.asyncio
async def test_award_badge_if_new_inserts_when_absent():
    """未持有：SELECT 返回 None → add(MemberBadge) + flush，返回 True。"""
    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()

    granted = await award_badge_if_new(session, member_id=1, key="streak_7")

    assert granted is True
    session.add.assert_called_once()
    assert session.add.call_args.args[0].badge_key == "streak_7"
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_award_badge_if_new_skips_when_exists():
    """已持有：SELECT 返回已存在行 → 不 add、不 flush，返回 False（幂等快速路径）。"""
    session = MagicMock()
    session.scalar = AsyncMock(return_value=MagicMock())  # 已存在该徽章
    session.add = MagicMock()
    session.flush = AsyncMock()

    granted = await award_badge_if_new(session, member_id=1, key="streak_7")

    assert granted is False
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


# ── build_badge_reward_candidates（徽章一次性现金奖励候选）──
def test_build_badge_reward_candidates_maps_each_badge():
    """每枚已获徽章 → 一个 badge_reward:{key} 候选；金额一致、snapshot 带 badge_key。"""
    cands = build_badge_reward_candidates(["streak_7", "xp_100"], amount=10.0)
    assert len(cands) == 2
    assert {c.key for c in cands} == {"badge_reward:streak_7", "badge_reward:xp_100"}
    for c in cands:
        assert c.type == "badge_reward"
        assert c.amount == 10.0
        assert c.threshold == 0
        assert "badge_key" in c.snapshot


def test_build_badge_reward_candidates_empty():
    """无已获徽章 → 无候选（调用方靠 uq_member_milestone_key 幂等去重）。"""
    assert build_badge_reward_candidates([], amount=10.0) == []
