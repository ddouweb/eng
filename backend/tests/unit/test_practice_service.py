from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import MasteryLevel, PlanStatus, PracticeMode, TaskStatus
from app.schemas.exceptions import AppException
from app.services.practice_service import PracticeService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def service(mock_session):
    return PracticeService(mock_session)


def _make_word(word_id=1, english="hello", chinese="你好"):
    w = MagicMock(id=word_id, english=english, chinese=chinese)
    w.type.value = "word"
    return w


class TestMasteryUpgrade:
    def test_unlearned_to_learning(self):
        record = MagicMock(level=MasteryLevel.unlearned, consecutive_correct=1, correct_count=1)
        PracticeService._try_upgrade(record)
        assert record.level == MasteryLevel.learning

    def test_learning_to_familiar(self):
        record = MagicMock(level=MasteryLevel.learning, consecutive_correct=3, correct_count=3)
        PracticeService._try_upgrade(record)
        assert record.level == MasteryLevel.familiar

    def test_learning_not_enough_consecutive(self):
        record = MagicMock(level=MasteryLevel.learning, consecutive_correct=2, correct_count=2)
        PracticeService._try_upgrade(record)
        assert record.level == MasteryLevel.learning

    def test_familiar_to_permanent(self):
        record = MagicMock(level=MasteryLevel.familiar, consecutive_correct=5, correct_count=8)
        PracticeService._try_upgrade(record)
        assert record.level == MasteryLevel.permanent

    def test_familiar_not_enough_total(self):
        record = MagicMock(level=MasteryLevel.familiar, consecutive_correct=5, correct_count=7)
        PracticeService._try_upgrade(record)
        assert record.level == MasteryLevel.familiar


class TestMasteryDowngrade:
    def test_familiar_to_learning(self):
        record = MagicMock(level=MasteryLevel.familiar, wrong_count=1)
        PracticeService._try_downgrade(record)
        assert record.level == MasteryLevel.learning

    def test_permanent_to_familiar(self):
        record = MagicMock(level=MasteryLevel.permanent, wrong_count=2)
        PracticeService._try_downgrade(record)
        assert record.level == MasteryLevel.familiar

    def test_permanent_stays_on_first_wrong(self):
        record = MagicMock(level=MasteryLevel.permanent, wrong_count=1)
        PracticeService._try_downgrade(record)
        assert record.level == MasteryLevel.permanent

    def test_learning_no_downgrade(self):
        record = MagicMock(level=MasteryLevel.learning, wrong_count=5)
        PracticeService._try_downgrade(record)
        assert record.level == MasteryLevel.learning


@pytest.mark.asyncio
async def test_submit_answer_session_not_found(service):
    service.session_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(AppException) as exc_info:
        await service.submit_answer(999, 1, True)
    assert exc_info.value.code == 404


@pytest.mark.asyncio
async def test_submit_answer_session_already_ended(service):
    ps = MagicMock(ended_at="2026-01-01")
    service.session_repo.get_by_id = AsyncMock(return_value=ps)
    with pytest.raises(AppException) as exc_info:
        await service.submit_answer(1, 1, True)
    assert exc_info.value.code == 400


@pytest.mark.asyncio
async def test_finish_practice(service, mock_session):
    ps = MagicMock(
        id=1, mode=PracticeMode.flashcard, total_count=10, correct_count=8,
        started_at=None, ended_at=None,
    )
    service.session_repo.get_by_id = AsyncMock(return_value=ps)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await service.finish_practice(1)

    assert result["code"] == 200
    assert result["data"]["accuracy"] == 80.0
    assert ps.ended_at is not None


@pytest.mark.asyncio
async def test_finish_practice_not_found(service):
    service.session_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(AppException) as exc_info:
        await service.finish_practice(999)
    assert exc_info.value.code == 404


# ────────────────────────────────────────────────────────────
# daily_task 回流测试
# ────────────────────────────────────────────────────────────


def _mock_scalar_result(value):
    """模拟 session.execute(...).scalar_one() 的链式调用。"""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


class TestClassifyAttempt:
    @pytest.mark.asyncio
    async def test_first_time_ever(self, service, mock_session):
        # 今天 0 条、历史 0 条 → (True, True)
        mock_session.execute = AsyncMock(
            side_effect=[_mock_scalar_result(0), _mock_scalar_result(0)]
        )
        is_first, is_new = await service._classify_attempt(1, 100, date(2026, 6, 16))
        assert is_first is True
        assert is_new is True

    @pytest.mark.asyncio
    async def test_already_practiced_today(self, service, mock_session):
        # 今天已有 1 条 → (False, True)
        mock_session.execute = AsyncMock(
            side_effect=[_mock_scalar_result(1), _mock_scalar_result(0)]
        )
        is_first, is_new = await service._classify_attempt(1, 100, date(2026, 6, 16))
        assert is_first is False
        assert is_new is True

    @pytest.mark.asyncio
    async def test_practiced_in_prior_days(self, service, mock_session):
        # 今天 0 条、历史 2 条 → (True, False)
        mock_session.execute = AsyncMock(
            side_effect=[_mock_scalar_result(0), _mock_scalar_result(2)]
        )
        is_first, is_new = await service._classify_attempt(1, 100, date(2026, 6, 16))
        assert is_first is True
        assert is_new is False


def _mock_task_result(task):
    """模拟 session.execute(...).scalar_one_or_none() 的链式调用。"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = task
    return result


class TestTickDailyTask:
    @pytest.mark.asyncio
    async def test_tick_new_word(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=3, completed_review=2,
            status=TaskStatus.in_progress,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=True)

        assert task.completed_new == 4
        assert task.completed_review == 2
        assert task.status == TaskStatus.in_progress

    @pytest.mark.asyncio
    async def test_tick_review_word(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=3, completed_review=2,
            status=TaskStatus.in_progress,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=False)

        assert task.completed_new == 3
        assert task.completed_review == 3
        assert task.status == TaskStatus.in_progress

    @pytest.mark.asyncio
    async def test_cap_new_does_not_overflow(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=10, completed_review=2,
            status=TaskStatus.in_progress,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=True)

        assert task.completed_new == 10  # 已满，不溢出

    @pytest.mark.asyncio
    async def test_both_filled_marks_completed(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=9, completed_review=5,
            status=TaskStatus.in_progress,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=True)

        assert task.completed_new == 10
        assert task.completed_review == 5
        assert task.status == TaskStatus.completed

    @pytest.mark.asyncio
    async def test_no_matching_task_is_noop(self, service, mock_session):
        mock_session.execute = AsyncMock(return_value=_mock_task_result(None))

        # 不应抛异常
        await service._tick_daily_task(member_id=1, unit_id=999, today=date(2026, 6, 16), is_new_word=True)


@pytest.mark.asyncio
async def test_submit_answer_reflows_to_daily_task(service, mock_session):
    """完整链路：答对 + 首次今日 → 调 _tick_daily_task。"""
    ps = MagicMock(id=1, member_id=7, ended_at=None, correct_count=3)
    service.session_repo.get_by_id = AsyncMock(return_value=ps)

    word = MagicMock(id=42, unit_id=10, english="hello", chinese="你好")
    service.session.get = AsyncMock(return_value=word)

    service.record_repo.create = AsyncMock()
    service._update_mastery = AsyncMock(return_value=MagicMock(
        level=MasteryLevel.learning, consecutive_correct=1,
        correct_count=1, wrong_count=0,
    ))
    mock_session.commit = AsyncMock()

    # _classify_attempt → (True, True) 首次今日 + 新词
    service._classify_attempt = AsyncMock(return_value=(True, True))
    service._tick_daily_task = AsyncMock()

    result = await service.submit_answer(session_id=1, word_id=42, is_correct=True)

    assert result["code"] == 200
    service._tick_daily_task.assert_awaited_once()
    args, kwargs = service._tick_daily_task.call_args
    assert args == (7, 10, date.today(), True)


@pytest.mark.asyncio
async def test_submit_answer_wrong_answer_does_not_tick(service, mock_session):
    """答错不回流。"""
    ps = MagicMock(id=1, member_id=7, ended_at=None, correct_count=3)
    service.session_repo.get_by_id = AsyncMock(return_value=ps)

    word = MagicMock(id=42, unit_id=10, english="hello", chinese="你好")
    service.session.get = AsyncMock(return_value=word)

    service.record_repo.create = AsyncMock()
    service._update_mastery = AsyncMock(return_value=MagicMock(
        level=MasteryLevel.unlearned, consecutive_correct=0,
        correct_count=0, wrong_count=1,
    ))
    mock_session.commit = AsyncMock()

    service._classify_attempt = AsyncMock(return_value=(True, True))
    service._tick_daily_task = AsyncMock()

    await service.submit_answer(session_id=1, word_id=42, is_correct=False)

    service._tick_daily_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_answer_second_attempt_today_does_not_tick(service, mock_session):
    """同一天二次答对：is_first_today=False → 不回流。"""
    ps = MagicMock(id=1, member_id=7, ended_at=None, correct_count=3)
    service.session_repo.get_by_id = AsyncMock(return_value=ps)

    word = MagicMock(id=42, unit_id=10, english="hello", chinese="你好")
    service.session.get = AsyncMock(return_value=word)

    service.record_repo.create = AsyncMock()
    service._update_mastery = AsyncMock(return_value=MagicMock(
        level=MasteryLevel.learning, consecutive_correct=2,
        correct_count=2, wrong_count=0,
    ))
    mock_session.commit = AsyncMock()

    service._classify_attempt = AsyncMock(return_value=(False, False))  # 今天已练过
    service._tick_daily_task = AsyncMock()

    await service.submit_answer(session_id=1, word_id=42, is_correct=True)

    service._tick_daily_task.assert_not_awaited()
