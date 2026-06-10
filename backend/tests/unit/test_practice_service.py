from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import MasteryLevel, PracticeMode
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
