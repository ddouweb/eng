from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import PlanStatus, TaskStatus
from app.schemas.exceptions import AppException
from app.services.plan_service import PlanService


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
        result = PlanService(plan=None)._plan_to_dict(plan)
        assert result["name"] == "test plan"
        assert result["status"] == "active"
        assert result["deadline"] == "2026-07-31"

    def test_plan_to_dict_without_deadline(self):
        plan = MagicMock(
            id=2, member_id=1, name="no deadline", daily_goal=10,
            deadline=None, status=PlanStatus.active,
            created_at=None,
        )
        result = PlanService(plan=None)._plan_to_dict(plan)
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

        result = await service.update_task(1, 1, 5, 2)
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
