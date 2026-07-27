from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import PlanStatus, PlanType, TaskStatus
from app.schemas.exceptions import AppException
from app.services.plan_service import PlanService, _count_learn_days


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def service(mock_session):
    return PlanService(mock_session)


class TestPlanToDict:
    def test_plan_to_dict_with_deadline(self):
        plan = MagicMock(
            id=1, member_id=1, name="test plan", daily_goal=15,
            deadline="2026-07-31", status=PlanStatus.active,
            created_at=None,
        )
        # MagicMock 的 name 是特殊参数（设 repr 名而非属性），需显式赋值才能被 .name 取到
        plan.name = "test plan"
        result = PlanService(None)._plan_to_dict(plan)
        assert result["name"] == "test plan"
        assert result["status"] == "active"
        assert result["deadline"] == "2026-07-31"

    def test_plan_to_dict_without_deadline(self):
        plan = MagicMock(
            id=2, member_id=1, name="no deadline", daily_goal=10,
            deadline=None, status=PlanStatus.active,
            created_at=None,
        )
        result = PlanService(None)._plan_to_dict(plan)
        assert result["deadline"] is None


class TestTaskToDict:
    def test_task_to_dict(self):
        task = MagicMock(
            id=1, plan_id=1, task_date="2026-06-10",
            new_count=15, review_count=5,
            completed_new=10, completed_review=3,
            status=TaskStatus.in_progress,
        )
        result = PlanService._task_to_dict(task)
        assert result["new_count"] == 15
        assert result["status"] == "in_progress"
        assert result["task_date"] == "2026-06-10"


class TestPausePlan:
    @pytest.mark.asyncio
    async def test_pause_plan_not_found(self, service):
        service.plan_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppException) as exc_info:
            await service.pause_plan(999)
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    async def test_pause_plan_success(self, service, mock_session):
        plan = MagicMock(status=PlanStatus.active)
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        mock_session.commit = AsyncMock()

        result = await service.pause_plan(1)
        assert result["code"] == 200
        assert plan.status == PlanStatus.paused


class TestResumePlan:
    @pytest.mark.asyncio
    async def test_resume_plan_not_found(self, service):
        service.plan_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppException) as exc_info:
            await service.resume_plan(999)
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    async def test_resume_plan_success(self, service, mock_session):
        plan = MagicMock(status=PlanStatus.paused)
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        mock_session.commit = AsyncMock()

        result = await service.resume_plan(1)
        assert result["code"] == 200
        assert plan.status == PlanStatus.active


class TestUpdateTask:
    @pytest.mark.asyncio
    async def test_update_task_not_found(self, service):
        service.task_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppException) as exc_info:
            await service.update_task(999, 1, 5, 3)
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    async def test_update_task_wrong_plan(self, service):
        task = MagicMock(plan_id=2, new_count=10, review_count=5, status=TaskStatus.pending)
        service.task_repo.get_by_id = AsyncMock(return_value=task)
        with pytest.raises(AppException) as exc_info:
            await service.update_task(1, 1, 10, 5)
        assert exc_info.value.code == 400

    @pytest.mark.asyncio
    async def test_update_task_to_completed(self, service, mock_session):
        task = MagicMock(
            plan_id=1, new_count=10, review_count=5,
            completed_new=0, completed_review=0,
            status=TaskStatus.pending,
        )
        service.task_repo.get_by_id = AsyncMock(return_value=task)
        mock_session.commit = AsyncMock()

        result = await service.update_task(1, 1, 10, 5)
        assert result["code"] == 200
        assert task.completed_new == 10
        assert task.completed_review == 5
        assert task.status == TaskStatus.completed

    @pytest.mark.asyncio
    async def test_update_task_to_in_progress(self, service, mock_session):
        task = MagicMock(
            plan_id=1, new_count=10, review_count=5,
            completed_new=0, completed_review=0,
            status=TaskStatus.pending,
        )
        service.task_repo.get_by_id = AsyncMock(return_value=task)
        mock_session.commit = AsyncMock()

        await service.update_task(1, 1, 5, 2)
        assert task.status == TaskStatus.in_progress


class TestGetPlan:
    @pytest.mark.asyncio
    async def test_get_plan_not_found(self, service):
        service.plan_repo.get_with_units = AsyncMock(return_value=None)
        with pytest.raises(AppException) as exc_info:
            await service.get_plan(999)
        assert exc_info.value.code == 404


class TestListPlans:
    @pytest.mark.asyncio
    async def test_list_plans_invalid_status(self, service):
        with pytest.raises(AppException) as exc_info:
            await service.list_plans(member_id=1, status="invalid_status")
        assert exc_info.value.code == 400

    @pytest.mark.asyncio
    async def test_list_plans_success(self, service):
        plan = MagicMock(
            id=1, member_id=1, name="test", daily_goal=15,
            deadline=None, status=PlanStatus.active, created_at=None,
        )
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [plan]
        mock_result.scalars.return_value = mock_scalars
        service.session.execute = AsyncMock(return_value=mock_result)

        result = await service.list_plans(member_id=1)
        assert result["code"] == 200
        assert len(result["data"]) == 1


# ── 手动重新平衡计划 rebalance_plan ──
def _plan_mock(**kw) -> MagicMock:
    """forward/active 计划 MagicMock，daily_goal=30→cap=45，默认全工作日。"""
    p = MagicMock(
        id=1, member_id=1, daily_goal=30, deadline=None,
        status=PlanStatus.active, plan_type=PlanType.forward,
        learn_weekdays="[0,1,2,3,4]", last_rebalanced_at=None,
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _remaining_exec_seq(unit_rows, total, mastered, occupied=None) -> AsyncMock:
    """模拟重建路径的 session.execute 序列：
    unit_ids→total→mastered（_remaining_unmastered）+ occupied 日期（存留 learn 任务）。"""
    r1, r2, r3, r4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    r1.all.return_value = unit_rows
    r2.scalar_one.return_value = total
    r3.scalar_one.return_value = mastered
    r4.all.return_value = [(d,) for d in (occupied or [])]
    return AsyncMock(side_effect=[r1, r2, r3, r4])


class TestRebalance:
    @pytest.mark.asyncio
    async def test_rebalance_not_found(self, service):
        service.plan_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(AppException) as exc_info:
            await service.rebalance_plan(999)
        assert exc_info.value.code == 404

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan_type,status", [
        (PlanType.review_only, PlanStatus.active),
        (PlanType.wrong_word_drill, PlanStatus.active),
        (PlanType.forward, PlanStatus.paused),
    ])
    async def test_rebalance_not_rebalanceable_short_circuits(self, service, plan_type, status):
        plan = _plan_mock(plan_type=plan_type, status=status)
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        service.task_repo.delete_future_pending_learn = AsyncMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["feasible"] is False
        assert data["reason"] == "not_rebalanceable"
        assert data["cap"] == 45
        service.task_repo.delete_future_pending_learn.assert_not_awaited()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebalance_no_deadline_short_circuits(self, service):
        plan = _plan_mock(deadline=None)
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        service.task_repo.delete_future_pending_learn = AsyncMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        assert result["data"]["reason"] == "no_deadline"
        service.task_repo.delete_future_pending_learn.assert_not_awaited()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebalance_deadline_passed_warns_no_rebuild(self, service):
        # deadline 在昨天 → (today+1, deadline] 为空 → 0 学习日 → deadline_passed
        plan = _plan_mock(deadline=date.today() - timedelta(days=1))
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        # remaining=60（非空 units，否则会先命中 nothing_to_rebalance）
        service.session.execute = _remaining_exec_seq([(1,)], 100, 40)
        service.task_repo.delete_future_pending_learn = AsyncMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["feasible"] is False
        assert data["reason"] == "deadline_passed"
        assert data["remaining_unmastered"] == 60
        service.task_repo.delete_future_pending_learn.assert_not_awaited()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebalance_nothing_to_rebalance(self, service):
        """已无未掌握词（remaining=0）→ 不动任何任务。"""
        plan = _plan_mock(deadline=date.today() + timedelta(days=30))
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        service.session.execute = _remaining_exec_seq([(1,)], 100, 100)  # remaining=0
        service.task_repo.delete_future_pending_learn = AsyncMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["feasible"] is False
        assert data["reason"] == "nothing_to_rebalance"
        assert data["remaining_unmastered"] == 0
        service.task_repo.delete_future_pending_learn.assert_not_awaited()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebalance_infeasible_warns_but_rebuilds_at_cap(self, service):
        # 剩余 1000 词，deadline 较近 → needed 远超 cap=45 → 按 cap 重建 + 告警
        plan = _plan_mock(deadline=date.today() + timedelta(days=10))
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        service.session.execute = _remaining_exec_seq([(1,)], 1040, 40)  # remaining=1000
        service.task_repo.delete_future_pending_learn = AsyncMock(return_value=7)
        service.session.add = MagicMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["feasible"] is False
        assert data["reason"] == "infeasible"
        assert data["new_per_day"] == 45          # 不越界，封顶 cap
        assert data["cap"] == 45
        assert data["remaining_unmastered"] == 1000
        service.task_repo.delete_future_pending_learn.assert_awaited_once()
        assert service.task_repo.delete_future_pending_learn.await_args.args[0] == 1
        service.session.commit.assert_awaited_once()
        assert service.session.add.call_count >= 1  # 按 cap 重建了未来新词槽
        assert data["last_rebalanced_at"] is not None

    @pytest.mark.asyncio
    async def test_rebalance_success_feasible(self, service):
        # 剩余 60 词，deadline 远 → needed≈3 ≤ cap → feasible，new_per_day=3
        plan = _plan_mock(deadline=date.today() + timedelta(days=30))
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        service.session.execute = _remaining_exec_seq([(1,)], 100, 40)  # remaining=60
        service.task_repo.delete_future_pending_learn = AsyncMock(return_value=20)
        service.session.add = MagicMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["feasible"] is True
        assert data["reason"] is None
        assert data["new_per_day"] == 3
        assert data["remaining_unmastered"] == 60
        service.task_repo.delete_future_pending_learn.assert_awaited_once()
        service.session.commit.assert_awaited_once()
        # 重建的新词槽每个都 ≤ new_per_day
        for call in service.session.add.call_args_list:
            task = call.args[0]
            assert task.new_count <= 3
        assert data["last_rebalanced_at"] is not None

    @pytest.mark.asyncio
    async def test_rebalance_no_free_learn_days(self, service):
        """所有未来学习日都被手动占用（非 pending）→ 无可重排日，feasible=False，
        不删不建不提交（noop 全在写之前判定）。"""
        plan = _plan_mock(deadline=date.today() + timedelta(days=30))
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        # 未来 60 天全部「已被手动占用」
        occupied_dates = [date.today() + timedelta(days=i) for i in range(1, 61)]
        service.session.execute = _remaining_exec_seq(
            [(1,)], 100, 40, occupied=occupied_dates,
        )  # remaining=60
        service.task_repo.delete_future_pending_learn = AsyncMock()
        service.session.add = MagicMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["feasible"] is False
        assert data["reason"] == "no_free_learn_days"
        service.task_repo.delete_future_pending_learn.assert_not_awaited()
        service.session.add.assert_not_called()
        service.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebalance_partial_occupied_uses_effective_days(self, service):
        """#1 修复验证：feasible 基于「有效学习日」(= 未来学习日 − 手动占用日)，而非全部
        未来学习日——否则占用时 feasible 虚高、词被静默丢弃。"""
        today = date.today()
        deadline = today + timedelta(days=30)
        weekdays = [0, 1, 2, 3, 4]
        rld = _count_learn_days(today + timedelta(days=1), deadline, weekdays)
        # 占用到只剩 10 个有效学习日
        future_learn = [
            today + timedelta(days=i) for i in range(1, 31)
            if (today + timedelta(days=i)).weekday() in weekdays
            and today + timedelta(days=i) <= deadline
        ]
        occupied_dates = future_learn[:max(rld - 10, 0)]
        effective = rld - len(occupied_dates)  # 期望 10
        # remaining=900 → needed=ceil(900/10)=90 > cap 45 → infeasible；若误用 rld(~21) 则 43≤45 误报 True
        plan = _plan_mock(deadline=deadline)
        service.plan_repo.get_by_id = AsyncMock(return_value=plan)
        service.session.execute = _remaining_exec_seq(
            [(1,)], 1000, 100, occupied=occupied_dates,
        )  # remaining=900
        service.task_repo.delete_future_pending_learn = AsyncMock()
        service.session.add = MagicMock()
        service.session.commit = AsyncMock()

        result = await service.rebalance_plan(1)
        data = result["data"]
        assert data["effective_learn_days"] == effective == 10
        assert data["feasible"] is False          # 修复后正确告警（旧逻辑会误报 True）
        assert data["reason"] == "infeasible"
        assert data["new_per_day"] == 45          # 封顶 cap，不越界
