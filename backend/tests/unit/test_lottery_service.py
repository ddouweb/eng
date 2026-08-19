"""lottery_service mock 测试（照 test_stats_service.py 范式：AsyncMock repo + savepoint stub）。

重点：
- _sync_grants 幂等（差集预过滤）与 IntegrityError 自愈；
- draw 次数不足 400 / 出票减次；
- draw_batch 边界（0/超上限/超可用）与共享 batch_id；
- settle 幂等（已结算直返 / rowcount=0 竞态回滚重取）；
- get_state 的 tasks 组装与两台账对账。
"""
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.exceptions import AppException
from app.services.lottery_service import MAX_BATCH_SIZE, TASK_META, LotteryService


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo, monkeypatch):
    svc = LotteryService(MagicMock())  # 构造时包 MagicMock session，无 DB 调用
    svc.repo = mock_repo
    svc.stats_repo = AsyncMock()
    return svc


class _OkSavepoint:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _RaisingSavepoint:
    def __init__(self, exc):
        self.exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        raise self.exc


def _facts(**over) -> dict:
    """最小 facts（空历史）：候选只剩 init:boot + daily:{today}。"""
    base = dict(
        today=date(2026, 8, 19),
        ended_practice_count=0,
        units_status=[],
        learn_task_done=False,
        review_task_done=False,
        stars=0,
        badge_keys=[],
        week_stars=[],
    )
    base.update(over)
    return base


def _member(**over):
    m = MagicMock(total_xp=0, lottery_wealth=0.0)
    for k, v in over.items():
        setattr(m, k, v)
    return m


def _ticket_row(id=7, prize=500, batch_id=None, settled=False):
    return MagicMock(
        id=id, prize=prize, batch_id=batch_id,
        ticket={"prize": prize, "win_numbers": [], "cells": [], "wins": []},
        created_at=datetime(2026, 8, 19, 12, 0, 0),
        settled_at=datetime(2026, 8, 19, 12, 1, 0) if settled else None,
    )


# ── _sync_grants：幂等 + 自愈 ──


class TestSyncGrants:
    @pytest.mark.asyncio
    async def test_first_sync_grants_init_and_daily(self, service, mock_repo):
        """空台账首刷：init:boot(5) + daily + practice 满 5 场补 2 笔。"""
        mock_repo.get_granted_keys = AsyncMock(return_value=set())
        service.session.begin_nested = MagicMock(return_value=_OkSavepoint())
        service.session.commit = AsyncMock()

        granted = await service._sync_grants(1, _facts(ended_practice_count=12))

        assert granted == 4  # init:boot + daily + practice:1 + practice:2（12 场 → 2 笔）
        keys = {c.args[1].key for c in mock_repo.add_grant.call_args_list}
        assert keys == {
            "init:boot", "daily:2026-08-19", "practice:1", "practice:2",
        }
        init_cand = next(
            c.args[1] for c in mock_repo.add_grant.call_args_list
            if c.args[1].key == "init:boot"
        )
        assert init_cand.draws == 5
        service.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_second_sync_grants_nothing(self, service, mock_repo):
        """已发 key 全集做差集：二次同步零写入、零 commit。"""
        mock_repo.get_granted_keys = AsyncMock(return_value={
            "init:boot", "daily:2026-08-19",
        })
        service.session.begin_nested = MagicMock(return_value=_OkSavepoint())
        service.session.commit = AsyncMock()

        granted = await service._sync_grants(1, _facts())

        assert granted == 0
        mock_repo.add_grant.assert_not_awaited()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_integrity_error_selfheals(self, service, mock_repo):
        """savepoint 抛 IntegrityError（并发撞唯一约束）：跳过该条，其余照发。"""
        mock_repo.get_granted_keys = AsyncMock(return_value=set())
        sp = [_RaisingSavepoint(IntegrityError("INSERT", {}, Exception("uq"))), _OkSavepoint()]
        service.session.begin_nested = MagicMock(side_effect=lambda: sp.pop(0))
        service.session.commit = AsyncMock()

        granted = await service._sync_grants(1, _facts())

        assert granted == 1  # init 撞约束跳过，daily 正常发
        assert mock_repo.add_grant.await_count == 2  # 两条都尝试过
        service.session.commit.assert_awaited_once()


# ── draw / draw_batch ──


class TestDraw:
    @pytest.mark.asyncio
    async def test_draw_insufficient_raises(self, service, mock_repo):
        mock_repo.sum_grant_draws = AsyncMock(return_value=5)
        mock_repo.count_tickets = AsyncMock(return_value=5)
        with pytest.raises(AppException) as e:
            await service.draw(1)
        assert e.value.code == 400

    @pytest.mark.asyncio
    async def test_draw_success_decrements(self, service, mock_repo):
        mock_repo.sum_grant_draws = AsyncMock(return_value=6)
        mock_repo.count_tickets = AsyncMock(return_value=1)
        row = _ticket_row(id=9)
        mock_repo.add_ticket = AsyncMock(return_value=row)
        service.session.commit = AsyncMock()

        result = await service.draw(1)

        assert result["code"] == 200
        assert result["data"]["id"] == 9
        assert result["data"]["draw_count_left"] == 4  # 6-1-1
        # 出票即消耗：单张 batch_id=None
        assert mock_repo.add_ticket.call_args.kwargs["batch_id"] is None
        service.session.commit.assert_awaited_once()


class TestDrawBatch:
    @pytest.mark.asyncio
    async def test_batch_bounds_validated_before_available(self, service, mock_repo):
        """0 / 超上限 在查次数前直接 400（不给 DB 加压）。"""
        mock_repo.sum_grant_draws = AsyncMock()
        for bad in (0, -1, MAX_BATCH_SIZE + 1):
            with pytest.raises(AppException) as e:
                await service.draw_batch(1, bad)
            assert e.value.code == 400
        mock_repo.sum_grant_draws.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_batch_exceeds_available(self, service, mock_repo):
        mock_repo.sum_grant_draws = AsyncMock(return_value=5)
        mock_repo.count_tickets = AsyncMock(return_value=0)
        with pytest.raises(AppException) as e:
            await service.draw_batch(1, 6)
        assert e.value.code == 400

    @pytest.mark.asyncio
    async def test_batch_success_shared_batch_id(self, service, mock_repo):
        mock_repo.sum_grant_draws = AsyncMock(return_value=10)
        mock_repo.count_tickets = AsyncMock(return_value=0)
        rows = [_ticket_row(id=i) for i in (11, 12, 13)]
        mock_repo.add_ticket = AsyncMock(side_effect=rows)
        service.session.commit = AsyncMock()

        result = await service.draw_batch(1, 3)

        d = result["data"]
        assert d["ticket_ids"] == [11, 12, 13]
        assert d["draw_count_left"] == 7
        batch_ids = {c.kwargs["batch_id"] for c in mock_repo.add_ticket.call_args_list}
        assert len(batch_ids) == 1 and batch_ids == {d["batch_id"]}
        # 悬念：开批不回 prize，只回 id 清单
        assert "prize" not in d and "tickets" not in d


# ── settle：幂等 + 竞态 ──


class TestSettle:
    @pytest.mark.asyncio
    async def test_settle_success_accrues_wealth(self, service, mock_repo):
        row = _ticket_row(id=7, prize=500)
        mock_repo.get_ticket = AsyncMock(return_value=row)
        member = _member(lottery_wealth=88.5)
        service.session.get = AsyncMock(return_value=member)
        result_mock = MagicMock(rowcount=1)
        service.session.execute = AsyncMock(return_value=result_mock)
        service.session.commit = AsyncMock()

        result = await service.settle(1, 7)

        d = result["data"]
        assert d["prize"] == 500
        assert member.lottery_wealth == 588.5
        assert d["wealth"] == 588.5
        assert d["already_settled"] is False

    @pytest.mark.asyncio
    async def test_settle_already_settled_is_idempotent(self, service, mock_repo):
        row = _ticket_row(id=7, prize=500, settled=True)
        mock_repo.get_ticket = AsyncMock(return_value=row)
        member = _member(lottery_wealth=588.5)
        service.session.get = AsyncMock(return_value=member)
        service.session.execute = AsyncMock()

        result = await service.settle(1, 7)

        d = result["data"]
        assert d["already_settled"] is True
        assert d["wealth"] == 588.5  # 不重复入账
        service.session.execute.assert_not_awaited()
        service.session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_settle_race_refetches_after_rollback(self, service, mock_repo):
        """rowcount=0（并发已结算）：rollback 过期 ORM 对象后重新取票取人。"""
        fresh = _ticket_row(id=7, prize=500, settled=True)
        mock_repo.get_ticket = AsyncMock(side_effect=[_ticket_row(id=7, prize=500), fresh])
        member = _member(lottery_wealth=588.5)
        service.session.get = AsyncMock(return_value=member)
        service.session.execute = AsyncMock(return_value=MagicMock(rowcount=0))
        service.session.rollback = AsyncMock()

        result = await service.settle(1, 7)

        d = result["data"]
        assert d["already_settled"] is True
        assert d["wealth"] == 588.5
        service.session.rollback.assert_awaited_once()
        assert mock_repo.get_ticket.await_count == 2  # 重取过

    @pytest.mark.asyncio
    async def test_settle_batch_ticket_includes_summary(self, service, mock_repo):
        row = _ticket_row(id=7, prize=500, batch_id="abc")
        mock_repo.get_ticket = AsyncMock(return_value=row)
        service.session.get = AsyncMock(return_value=_member())
        service.session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
        service.session.commit = AsyncMock()
        mock_repo.get_batch_tickets = AsyncMock(return_value=[row])
        mock_repo.batch_summary = MagicMock(return_value={
            "batch_id": "abc", "size": 4, "settled": 1, "remaining": 3,
            "total_prize": 500, "hit_count": 1, "best_prize": 500,
            "tickets": ["..."],  # 摘要子集不含票列表
        })

        result = await service.settle(1, 7)

        batch = result["data"]["batch"]
        assert set(batch) == {
            "batch_id", "size", "settled", "remaining",
            "total_prize", "hit_count", "best_prize",
        }
        assert batch["total_prize"] == 500

    @pytest.mark.asyncio
    async def test_settle_ticket_not_found(self, service, mock_repo):
        mock_repo.get_ticket = AsyncMock(return_value=None)
        with pytest.raises(AppException) as e:
            await service.settle(1, 99)
        assert e.value.code == 404


# ── get_state / _tasks_payload / history ──


class TestGetState:
    @pytest.fixture
    def state_mocks(self, service, mock_repo):
        """全空历史成员：facts 全零，sync 首刷发 init+daily。"""
        member = _member(lottery_wealth=88.5)
        service.session.get = AsyncMock(return_value=member)
        mock_repo.get_today_task_flags = AsyncMock(return_value={"learn": False, "review": False})
        mock_repo.count_ended_sessions = AsyncMock(return_value=0)
        service.stats_repo.get_all_units_mastery_status = AsyncMock(return_value=[])
        mock_repo.get_badge_keys = AsyncMock(return_value=[])
        mock_repo.get_week_stars = AsyncMock(return_value=[])
        mock_repo.get_granted_keys = AsyncMock(return_value=set())
        service.session.begin_nested = MagicMock(return_value=_OkSavepoint())
        service.session.commit = AsyncMock()
        mock_repo.sum_grant_draws = AsyncMock(return_value=6)   # init 5 + daily 1
        mock_repo.count_tickets = AsyncMock(return_value=1)
        mock_repo.get_won_stats = AsyncMock(return_value={"total_won": 540, "hit_count": 2})
        mock_repo.find_active_batch = AsyncMock(return_value=None)
        mock_repo.find_pending_single = AsyncMock(return_value=None)
        mock_repo.recent_tickets = AsyncMock(return_value=[])
        return service

    @pytest.mark.asyncio
    async def test_state_assembles_overview(self, state_mocks):
        result = await state_mocks.get_state(1)
        d = result["data"]
        assert d["draw_count"] == 5        # 6 - 1
        assert d["wealth"] == 88.5
        assert d["total_granted"] == 6
        assert d["total_drawn"] == 1
        assert d["total_won"] == 540
        assert d["hit_count"] == 2
        # 任务清单 8 项、顺序与 TASK_META 一致
        assert [t["key"] for t in d["tasks"]] == [m["key"] for m in TASK_META]
        daily = next(t for t in d["tasks"] if t["key"] == "daily")
        assert daily["done"] is True       # 打开即领
        practice = next(t for t in d["tasks"] if t["key"] == "practice")
        assert practice["done"] is False

    @pytest.mark.asyncio
    async def test_state_member_missing_404(self, service):
        service.session.get = AsyncMock(return_value=None)
        with pytest.raises(AppException) as e:
            await service.get_state(1)
        assert e.value.code == 404

    def test_tasks_payload_math(self):
        """单元通关 / 练习批次 / 周星合计 的动态 note 与 draws。"""
        facts = _facts(
            ended_practice_count=12,
            units_status=[
                {"total_words": 10, "mastered": 10},   # 通关
                {"total_words": 10, "mastered": 3},    # 未通
                {"total_words": 0, "mastered": 0},     # 空单元不计
            ],
            learn_task_done=True,
            review_task_done=False,
            stars=3,
            badge_keys=["streak_3", "xp_1000"],
            week_stars=[("2026-W30", 4), ("2026-W31", 2)],
        )
        tasks = {t["key"]: t for t in LotteryService._tasks_payload(facts)}
        assert tasks["unit"]["draws"] == 1
        assert tasks["practice"]["draws"] == 2          # 12 // 5
        assert tasks["practice"]["note"] == "累计 12 场 · 已领 2 次"
        assert tasks["star"]["draws"] == 3
        assert tasks["badge"]["draws"] == 2
        assert tasks["weekstars"]["draws"] == 6         # 4 + 2
        assert tasks["weekstars"]["note"] == "历史 6 星"
        assert tasks["learn_task"]["done"] is True
        assert tasks["review_task"]["done"] is False


class TestHistory:
    @pytest.mark.asyncio
    async def test_history_summary(self, service, mock_repo):
        mock_repo.get_won_stats = AsyncMock(return_value={"total_won": 540, "hit_count": 2})
        mock_repo.count_tickets = AsyncMock(return_value=7)
        mock_repo.recent_tickets = AsyncMock(return_value=[{"id": 9, "prize": 0}])

        result = await service.history(1, limit=20)

        d = result["data"]
        assert d["total"] == 7
        assert d["total_won"] == 540
        assert len(d["items"]) == 1
        mock_repo.recent_tickets.call_args.kwargs["limit"] == 20

    @pytest.mark.asyncio
    async def test_batch_summary_not_found(self, service, mock_repo):
        mock_repo.get_batch_tickets = AsyncMock(return_value=[])
        with pytest.raises(AppException) as e:
            await service.batch_summary(1, "nope")
        assert e.value.code == 404
