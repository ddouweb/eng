from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import MasteryLevel, TagType
from app.schemas.exceptions import AppException
from app.services.word_service import WordService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def service(mock_session):
    return WordService(mock_session)


def _make_word(id=1, english="hello", chinese="你好", type="word", unit_id=1):
    w = MagicMock(id=id, english=english, chinese=chinese, type=type, unit_id=unit_id)
    w.created_at = datetime(2026, 1, 1)
    w.updated_at = datetime(2026, 1, 1)
    w.type.value = type
    return w


@pytest.mark.asyncio
async def test_batch_create(service, mock_session):
    service.repo.batch_create = AsyncMock(return_value=[_make_word()])
    result = await service.batch_create(1, [
        {"english": "hello", "chinese": "你好", "type": "word"}
    ])
    assert result["code"] == 200
    assert result["data"]["created_count"] == 1
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_word_not_found(service):
    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(AppException) as exc_info:
        await service.update_word(999, {"english": "hi"})
    assert exc_info.value.code == 404


@pytest.mark.asyncio
async def test_set_tags(service, mock_session):
    service.repo.get_by_id = AsyncMock(return_value=_make_word())
    service.repo.set_tags = AsyncMock()
    result = await service.set_tags(1, ["favorite", "high_freq"])
    assert result["code"] == 200
    assert result["data"]["tags"] == ["favorite", "high_freq"]
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_tag_success(service, mock_session):
    service.repo.get_by_id = AsyncMock(return_value=_make_word())
    service.repo.remove_tag = AsyncMock(return_value=True)
    result = await service.remove_tag(1, "favorite")
    assert result["code"] == 200
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_tag_invalid(service):
    service.repo.get_by_id = AsyncMock(return_value=_make_word())
    with pytest.raises(AppException) as exc_info:
        await service.remove_tag(1, "nonexistent_tag")
    assert exc_info.value.code == 400


@pytest.mark.asyncio
async def test_get_mastery_creates_default(service, mock_session):
    service.repo.get_by_id = AsyncMock(return_value=_make_word())
    record = MagicMock(
        word_id=1, member_id=1, level=MasteryLevel.unlearned,
        consecutive_correct=0, correct_count=0, wrong_count=0,
        updated_at=datetime(2026, 1, 1),
    )
    record.level.value = "unlearned"
    service.mastery_repo.get_or_create = AsyncMock(return_value=record)
    result = await service.get_mastery(1)
    assert result["code"] == 200
    assert result["data"]["level"] == "unlearned"
    mock_session.commit.assert_awaited_once()
