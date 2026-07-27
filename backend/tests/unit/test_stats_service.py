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
        member = MagicMock(total_xp=100)
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
        assert service.session.add.call_count == 2  # 1 徽章 + 1 settlement 行

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
