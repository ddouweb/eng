from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.stats_service import StatsService


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo, monkeypatch):
    from app.repositories import stats_repo
    monkeypatch.setattr(stats_repo, "StatsRepo", lambda session: mock_repo)
    svc = StatsService(MagicMock())
    svc.repo = mock_repo
    return svc


class TestGetOverview:
    @pytest.mark.asyncio
    async def test_overview_with_data(self, service, mock_repo):
        mock_repo.get_mastery_distribution = AsyncMock(return_value={
            "unlearned": 50, "learning": 20, "familiar": 15, "permanent": 15,
        })
        mock_repo.get_total_word_count = AsyncMock(return_value=100)
        mock_repo.get_practice_summary = AsyncMock(return_value={
            "session_count": 10, "total_questions": 100, "total_correct": 80,
        })
        mock_repo.get_streak = AsyncMock(return_value=5)

        result = await service.get_overview(member_id=1)
        assert result["code"] == 200
        data = result["data"]
        assert data["total_words"] == 100
        assert data["mastered_count"] == 30
        assert data["mastery_rate"] == 30.0
        assert data["accuracy"] == 80.0
        assert data["streak_days"] == 5

    @pytest.mark.asyncio
    async def test_overview_no_data(self, service, mock_repo):
        mock_repo.get_mastery_distribution = AsyncMock(return_value={
            "unlearned": 0, "learning": 0, "familiar": 0, "permanent": 0,
        })
        mock_repo.get_total_word_count = AsyncMock(return_value=0)
        mock_repo.get_practice_summary = AsyncMock(return_value={
            "session_count": 0, "total_questions": 0, "total_correct": 0,
        })
        mock_repo.get_streak = AsyncMock(return_value=0)

        result = await service.get_overview(member_id=1)
        assert result["data"]["mastery_rate"] == 0.0
        assert result["data"]["accuracy"] == 0.0


class TestGetUnitStats:
    @pytest.mark.asyncio
    async def test_unit_stats(self, service, mock_repo):
        mock_repo.get_mastery_by_unit = AsyncMock(return_value={
            "unlearned": 5, "learning": 3, "familiar": 2, "permanent": 0,
        })
        mock_repo.get_total_word_count = AsyncMock(return_value=10)

        result = await service.get_unit_stats(member_id=1, unit_id=1)
        assert result["code"] == 200
        assert result["data"]["total_words"] == 10
        assert result["data"]["mastered_count"] == 2
        assert result["data"]["mastery_rate"] == 20.0


class TestGetTrend:
    @pytest.mark.asyncio
    async def test_trend(self, service, mock_repo):
        mock_repo.get_recent_practice_daily = AsyncMock(return_value=[
            {"date": "2026-06-09", "total": 20, "correct": 16},
            {"date": "2026-06-10", "total": 15, "correct": 12},
        ])

        result = await service.get_trend(member_id=1, days=7)
        assert result["code"] == 200
        assert result["data"]["days"] == 7
        assert len(result["data"]["daily"]) == 2


# ── 每周结算 _settle_one_week / _maybe_settle_week ──
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


class TestWeeklySettlement:
    @pytest.fixture
    def settle_mocks(self, service, mock_repo):
        """配置 _settle_one_week 成功路径所需 mock：全勤 7 天 + 满计划 + 无 active plan。"""
        mock_repo.get_week_active_days = AsyncMock(return_value=7)
        mock_repo.get_week_correct_breakdown = AsyncMock(
            return_value={"correct_words": 10, "hard_words": 3}
        )
        mock_repo.get_week_new_word_count = AsyncMock(return_value=5)
        mock_repo.get_week_task_stats = AsyncMock(
            return_value={"completed_slots": 20, "planned_slots": 20,
                          "tasks_due": 5, "tasks_done": 5}
        )
        mock_repo.get_active_forward_plan_with_remaining = AsyncMock(return_value=None)
        # existing settlement 检查 + 徽章检查 都返回 None（未结算/未发徽章）
        service.session.scalar = AsyncMock(return_value=None)
        state = MagicMock(freeze_balance=2)
        member = MagicMock(total_xp=100, cash_balance=0.0)
        service.session.get = AsyncMock(
            side_effect=lambda cls, _mid: state if cls.__name__ == "MemberStreak" else member
        )
        service.session.add = MagicMock()
        service.session.begin_nested = MagicMock(return_value=_OkSavepoint())
        return service, state, member

    @pytest.mark.asyncio
    async def test_settle_success_grants_bonus_freeze_badge(self, settle_mocks):
        service, state, member = settle_mocks
        # 无 plan → exp_days=5, daily_goal=30：login=25, plan=30, bonus=round(55/55*30)=30
        # 全勤7 → freeze_granted=1（2→3）；total=68<100 不发满分徽章，仅 week_login_7
        done = await service._settle_one_week(
            1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19)
        )
        assert done is True
        assert state.freeze_balance == 3          # 2 + 1
        assert member.total_xp == 130             # 100 + bonus 30
        assert member.cash_balance == 0.0         # CASH_ENABLED 默认关 → 不发现金
        assert service.session.add.call_count == 2  # 1 徽章 + 1 settlement 行
        # settlement 行带 cash 字段（默认 0/None）
        row = service.session.add.call_args_list[-1].args[0]
        assert row.cash_reward == 0.0
        assert row.cash_tier_label is None

    @pytest.mark.asyncio
    async def test_settle_grants_cash_when_enabled(self, settle_mocks, monkeypatch):
        """CASH_ENABLED=true：3★+100%完成 → 命中 3star 档 ¥10，累加进 cash_balance。"""
        from app.config import settings
        monkeypatch.setattr(settings, "CASH_ENABLED", True)
        service, _state, member = settle_mocks
        # total=68 → stars=3；plan_completion=1.0 → compute_weekly_cash(3,1.0)=(10.0,"3star")
        done = await service._settle_one_week(
            1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19)
        )
        assert done is True
        assert member.cash_balance == 10.0        # round(0.0 + 10.0, 2)
        row = service.session.add.call_args_list[-1].args[0]
        assert row.cash_reward == 10.0
        assert row.cash_tier_label == "3star"
        # bonus 仍正常发（cash 与 bonus 独立、同 savepoint 原子）
        assert member.total_xp == 130

    @pytest.mark.asyncio
    async def test_settle_cash_accrues_even_when_bonus_zero(self, settle_mocks, monkeypatch):
        """坑#1 回归保护：bonus==0 但 stars>=3 时，cash_reward 仍须累加 cash_balance。

        若有人把 savepoint 条件误改回 `if bonus > 0:`（漏 or cash_reward），
        本测试会失败——bonus=0 不加载 member、cash_balance 不累加。
        场景：active=1→login=5；hard6/correct10→difficulty=25；new150/target150→new=20；
        completed2/planned20→plan=3；total=53→stars=3；bonus=round(8/55*30)=4<5→0。
        """
        from app.config import settings
        monkeypatch.setattr(settings, "CASH_ENABLED", True)
        service, _state, member = settle_mocks
        service.repo.get_week_active_days = AsyncMock(return_value=1)
        service.repo.get_week_correct_breakdown = AsyncMock(
            return_value={"correct_words": 10, "hard_words": 6}
        )
        service.repo.get_week_new_word_count = AsyncMock(return_value=150)
        service.repo.get_week_task_stats = AsyncMock(
            return_value={"completed_slots": 2, "planned_slots": 20,
                          "tasks_due": 1, "tasks_done": 0}
        )
        await service._settle_one_week(1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19))
        assert member.cash_balance == 10.0     # bonus=0 但 cash 仍累加（or cash_reward 分支生效）
        assert member.total_xp == 100          # bonus=0 → total_xp 不变
        row = service.session.add.call_args_list[-1].args[0]
        assert row.bonus_xp == 0
        assert row.cash_reward == 10.0
        assert row.cash_tier_label == "3star"

    @pytest.mark.asyncio
    async def test_settle_skips_already_settled(self, service, mock_repo):
        service.session.scalar = AsyncMock(return_value=MagicMock())  # 已存在该周结算
        mock_repo.get_week_active_days = AsyncMock(return_value=7)    # 不应被调用
        done = await service._settle_one_week(
            1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19)
        )
        assert done is False
        mock_repo.get_week_active_days.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_settle_skips_no_activity(self, service, mock_repo):
        service.session.scalar = AsyncMock(return_value=None)
        mock_repo.get_week_active_days = AsyncMock(return_value=0)
        done = await service._settle_one_week(
            1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19)
        )
        assert done is False   # 不造 0 分垃圾行

    @pytest.mark.asyncio
    async def test_settle_race_returns_false(self, settle_mocks):
        service, _state, _member = settle_mocks
        # savepoint 退出时抛 IntegrityError（模拟并发命中唯一约束）
        service.session.begin_nested = MagicMock(
            return_value=_RaisingSavepoint(IntegrityError("INSERT", {}, Exception("uq")))
        )
        done = await service._settle_one_week(
            1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19)
        )
        assert done is False   # savepoint 回滚 bonus/freeze/徽章/row，安全跳过

    @pytest.mark.asyncio
    async def test_maybe_settle_processes_weeks_ascending(self, service):
        """freeze 对顺序敏感：必须按 week_key 升序结算（较老的全勤周先拿 freeze）。"""
        seen: list[str] = []

        async def fake_settle(member_id, week_key, ws, we):
            seen.append(week_key)
            return False

        service._settle_one_week = fake_settle
        service.session.commit = AsyncMock()
        await service._maybe_settle_week(1)
        assert len(seen) == 4
        assert seen == sorted(seen)   # 升序

    @pytest.mark.asyncio
    async def test_maybe_settle_no_commit_when_nothing_settled(self, service):
        service._settle_one_week = AsyncMock(return_value=False)
        service.session.commit = AsyncMock()
        await service._maybe_settle_week(1)
        service.session.commit.assert_not_awaited()


# ── 现金里程碑 _maybe_grant_milestones ──
class TestMaybeGrantMilestones:
    @pytest.fixture
    def grant_mocks(self, service, mock_repo):
        mock_repo.get_all_units_mastery_status = AsyncMock(return_value=[])
        mock_repo.get_full_attendance_week_streak = AsyncMock(return_value=0)
        service.session.scalar = AsyncMock(return_value=None)   # 无已发里程碑
        member = MagicMock(cash_balance=0.0)
        service.session.get = AsyncMock(return_value=member)
        service.session.add = MagicMock()
        service.session.begin_nested = MagicMock(return_value=_OkSavepoint())
        service.session.commit = AsyncMock()
        return service, member

    def _added_keys(self, service):
        return {c.args[0].milestone_key for c in service.session.add.call_args_list}

    @pytest.mark.asyncio
    async def test_unit_complete_grants_once(self, grant_mocks, mock_repo):
        service, member = grant_mocks
        mock_repo.get_all_units_mastery_status = AsyncMock(
            return_value=[{"unit_id": 5, "total_words": 120, "mastered": 120}]
        )
        await service._maybe_grant_milestones(1)
        # unit_complete(120词→¥50) + mastered_total=120 越过 cumulative_words:100(¥10) → 共 60
        # （两类里程碑 key 不同、可同发，符合设计：奖励不同的离散成就）
        assert member.cash_balance == 60.0
        keys = self._added_keys(service)
        assert "unit_complete:5" in keys
        assert "cumulative_words:100" in keys
        service.session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_idempotent_skip_existing(self, grant_mocks, mock_repo):
        service, member = grant_mocks
        mock_repo.get_all_units_mastery_status = AsyncMock(
            return_value=[{"unit_id": 5, "total_words": 120, "mastered": 120}]
        )
        service.session.scalar = AsyncMock(return_value=MagicMock())   # 已存在
        await service._maybe_grant_milestones(1)
        assert member.cash_balance == 0.0           # 不重复发
        service.session.add.assert_not_called()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cumulative_words_and_streak(self, grant_mocks, mock_repo):
        service, member = grant_mocks
        mock_repo.get_full_attendance_week_streak = AsyncMock(return_value=8)
        # 600 < 1000 → 非 unit_complete；mastered_total=600
        mock_repo.get_all_units_mastery_status = AsyncMock(
            return_value=[{"unit_id": 1, "total_words": 1000, "mastered": 600}]
        )
        await service._maybe_grant_milestones(1)
        # words: 100→10, 500→20 (合计 30)；streak: 4→20, 8→50 (合计 70) → 共 100
        assert member.cash_balance == 100.0
        keys = self._added_keys(service)
        assert {"cumulative_words:100", "cumulative_words:500"} <= keys
        assert "cumulative_words:1000" not in keys   # 600 < 1000
        assert {"attendance_streak:4", "attendance_streak:8"} <= keys

    @pytest.mark.asyncio
    async def test_no_candidates_no_commit(self, grant_mocks, mock_repo):
        service, member = grant_mocks
        mock_repo.get_all_units_mastery_status = AsyncMock(
            return_value=[{"unit_id": 1, "total_words": 100, "mastered": 0}]  # 未掌握
        )
        await service._maybe_grant_milestones(1)
        assert member.cash_balance == 0.0
        service.session.add.assert_not_called()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_race_single_candidate_no_crash(self, grant_mocks, mock_repo):
        """单候选 savepoint 抛 IntegrityError → 捕获跳过，不抛、不 commit。"""
        service, _member = grant_mocks
        mock_repo.get_all_units_mastery_status = AsyncMock(
            return_value=[{"unit_id": 1, "total_words": 1000, "mastered": 100}]  # 1 候选 words:100
        )
        service.session.begin_nested = MagicMock(
            return_value=_RaisingSavepoint(IntegrityError("INSERT", {}, Exception("uq")))
        )
        await service._maybe_grant_milestones(1)    # 不抛
        service.session.commit.assert_not_awaited()  # granted_any=False
