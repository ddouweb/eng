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


class TestTodayProgress:
    @pytest.fixture
    def today_mocks(self, service, mock_repo):
        """配置 get_today_progress 所需 mock：今日任务 + 实际练习 + forward 计划 + 错题总量。"""
        mock_repo.get_today_task_stats = AsyncMock(
            return_value={"new_done": 5, "new_target": 10, "review_done": 3, "review_target": 8}
        )
        mock_repo.get_today_practice_summary = AsyncMock(
            return_value={"correct_count": 42, "new_word_count": 6}
        )
        mock_repo.get_active_forward_plan_with_remaining = AsyncMock(
            return_value={
                "plan_id": 18, "deadline": date(2026, 12, 31), "daily_goal": 93,
                "learn_weekdays_raw": "[0,1,2,3,4]", "total_words": 2000, "mastered": 800,
            }
        )
        service.wrong_repo = MagicMock()
        service.wrong_repo.count_by_member = AsyncMock(return_value=12)
        return service

    @pytest.mark.asyncio
    async def test_today_progress_aggregates_fields(self, today_mocks):
        result = await today_mocks.get_today_progress(1)
        assert result["code"] == 200
        d = result["data"]
        assert d["today_new_done"] == 5
        assert d["today_new_target"] == 10
        assert d["today_review_done"] == 3
        assert d["today_review_target"] == 8
        assert d["today_correct"] == 42
        assert d["today_new_words"] == 6
        assert d["wrong_book_total"] == 12
        assert d["has_active_plan"] is True
        # plan_health 以今天为基准：remaining_unmastered = 2000 - 800 = 1200
        assert d["plan_health"] is not None
        assert d["plan_health"]["remaining_unmastered"] == 1200

    @pytest.mark.asyncio
    async def test_today_progress_no_active_plan(self, service, mock_repo):
        mock_repo.get_today_task_stats = AsyncMock(
            return_value={"new_done": 0, "new_target": 0, "review_done": 0, "review_target": 0}
        )
        mock_repo.get_today_practice_summary = AsyncMock(
            return_value={"correct_count": 0, "new_word_count": 0}
        )
        mock_repo.get_active_forward_plan_with_remaining = AsyncMock(return_value=None)
        service.wrong_repo = MagicMock()
        service.wrong_repo.count_by_member = AsyncMock(return_value=0)
        result = await service.get_today_progress(1)
        d = result["data"]
        assert d["has_active_plan"] is False
        assert d["plan_health"] is None

    @pytest.mark.asyncio
    async def test_today_progress_does_not_settle(self, today_mocks):
        """首页高频打开：get_today_progress 不得触发懒结算（_maybe_settle_week）。"""
        today_mocks._maybe_settle_week = AsyncMock()
        await today_mocks.get_today_progress(1)
        today_mocks._maybe_settle_week.assert_not_awaited()


class TestWeekProgress:
    @pytest.fixture
    def week_mocks(self, service, mock_repo):
        """配置 get_week_progress 所需 mock：本周活跃/新词/任务/forward 计划。"""
        mock_repo.get_week_active_days = AsyncMock(return_value=3)
        mock_repo.get_week_new_word_count = AsyncMock(return_value=12)
        mock_repo.get_week_task_stats = AsyncMock(return_value={
            "completed_slots": 18, "planned_slots": 25, "tasks_due": 5, "tasks_done": 3
        })
        mock_repo.get_active_forward_plan_with_remaining = AsyncMock(return_value={
            "plan_id": 18, "deadline": date(2026, 12, 31), "daily_goal": 30,
            "learn_weekdays_raw": "[0,1,2,3,4]", "total_words": 2000, "mastered": 800,
        })
        return service

    @pytest.mark.asyncio
    async def test_week_progress_aggregates_fields(self, week_mocks):
        result = await week_mocks.get_week_progress(1)
        assert result["code"] == 200
        d = result["data"]
        assert d["week_key"].startswith("20")        # 2026-Wxx
        assert d["active_days"] == 3
        assert d["new_words"] == 12
        assert d["has_active_plan"] is True
        # daily_goal=30, exp_days=5（工作日）→ weekly_new_target=150
        assert d["weekly_new_target"] == 150
        # login=score_login(3,5)=round(3/5*45)=27
        assert d["login_score"] == 27
        assert d["login_full"] == 45
        assert d["new_full"] == 25
        assert d["plan_full"] == 30
        # total = 三维分之和（new=score_new(12,150)=2, plan=score_plan(18,25)=22）
        assert d["total_score"] == d["login_score"] + d["new_score"] + d["plan_score"]

    @pytest.mark.asyncio
    async def test_week_progress_no_active_plan(self, service, mock_repo):
        mock_repo.get_week_active_days = AsyncMock(return_value=0)
        mock_repo.get_week_new_word_count = AsyncMock(return_value=0)
        mock_repo.get_week_task_stats = AsyncMock(return_value={
            "completed_slots": 0, "planned_slots": 0, "tasks_due": 0, "tasks_done": 0
        })
        mock_repo.get_active_forward_plan_with_remaining = AsyncMock(return_value=None)
        result = await service.get_week_progress(1)
        d = result["data"]
        assert d["has_active_plan"] is False
        assert d["total_score"] == 0
        assert d["stars"] == 0
        assert d["bonus_xp"] == 0

    @pytest.mark.asyncio
    async def test_week_progress_does_not_settle(self, week_mocks):
        """首页高频：get_week_progress 不得触发懒结算（纯只读预估，不落表不发奖）。"""
        week_mocks._maybe_settle_week = AsyncMock()
        await week_mocks.get_week_progress(1)
        week_mocks._maybe_settle_week.assert_not_awaited()


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
    async def test_settle_success_grants_bonus_freeze_badge(self, settle_mocks, monkeypatch):
        # 钉死 CASH_ENABLED=False，避免 .env 设 true 时 compute_weekly_cash 发现金让 cash_balance 断言失败
        from app.config import settings
        monkeypatch.setattr(settings, "CASH_ENABLED", False)
        service, state, member = settle_mocks
        # 无 plan → exp_days=5, daily_goal=30：login=45, new=1(5/150), plan=30, bonus=round(75/75*30)=30
        # 全勤7 → freeze_granted=1（2→3）；total=76<100 不发满分徽章，仅 week_login_7
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
        """CASH_ENABLED=true：4★+100%完成 → 命中 4star_full 档 ¥30，累加进 cash_balance。"""
        from app.config import settings
        monkeypatch.setattr(settings, "CASH_ENABLED", True)
        service, _state, member = settle_mocks
        # total=76 → stars=4；plan_completion=1.0 → compute_weekly_cash(4,1.0)=(30.0,"4star_full")
        done = await service._settle_one_week(
            1, "2026-W29", date(2026, 7, 13), date(2026, 7, 19)
        )
        assert done is True
        assert member.cash_balance == 30.0        # round(0.0 + 30.0, 2)
        row = service.session.add.call_args_list[-1].args[0]
        assert row.cash_reward == 30.0
        assert row.cash_tier_label == "4star_full"
        # bonus 仍正常发（cash 与 bonus 独立、同 savepoint 原子）
        assert member.total_xp == 130

    # 原 test_settle_cash_accrues_even_when_bonus_zero 已移除：三维重分配（坚持 35 / 新词 25 / 计划 40）
    # 后，bonus==0 ⟹ login+plan≤11 ⟹ total≤36 ⟹ stars≤2 ⟹ cash==0，「bonus==0 但发现金」的
    # 组合数学上不再可能。cash 与 bonus 同累加的覆盖由 test_settle_grants_cash_when_enabled 承担。

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
