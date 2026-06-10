from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.base import OCRResult, OCRWordItem
from app.services.ocr_service import OCRService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def service(mock_session):
    return OCRService(mock_session)


@pytest.mark.asyncio
async def test_upload_and_parse_success(service, mock_session):
    from app.services.ocr_service import _drafts

    mock_unit = MagicMock(id=1)
    mock_unit_repo = MagicMock()
    mock_unit_repo.get_by_id = AsyncMock(return_value=mock_unit)
    mock_unit_repo.update = AsyncMock()

    mock_ocr_result = OCRResult(words=[
        OCRWordItem(english="hello", chinese="你好", word_type="word"),
        OCRWordItem(english="How are you?", chinese="你好吗？", word_type="sentence"),
    ])

    with patch("app.services.ocr_service.get_ai_provider") as mock_get_provider, \
         patch("app.services.ocr_service.UnitRepo", return_value=mock_unit_repo):
        mock_provider = AsyncMock()
        mock_provider.parse_image = AsyncMock(return_value=mock_ocr_result)
        mock_get_provider.return_value = mock_provider

        result = await service.upload_and_parse(1, b"fake_image_bytes", "test.jpg")

    assert result["code"] == 200
    assert result["data"]["parsed_count"] == 2
    assert result["data"]["draft_words"][0]["english"] == "hello"
    assert 1 in _drafts
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upload_unit_not_found(service):
    mock_unit_repo = MagicMock()
    mock_unit_repo.get_by_id = AsyncMock(return_value=None)

    with patch("app.services.ocr_service.UnitRepo", return_value=mock_unit_repo):
        result = await service.upload_and_parse(999, b"bytes", "test.jpg")

    assert result["code"] == 404


@pytest.mark.asyncio
async def test_get_ocr_result_with_draft(service):
    from app.services.ocr_service import _drafts

    _drafts[42] = [{"english": "test", "chinese": "测试", "type": "word"}]
    result = await service.get_ocr_result(42)
    assert result["code"] == 200
    assert result["data"]["parsed_count"] == 1

    del _drafts[42]


@pytest.mark.asyncio
async def test_get_ocr_result_no_draft(service):
    from app.services.ocr_service import _drafts

    _drafts.pop(9999, None)
    result = await service.get_ocr_result(9999)
    assert result["code"] == 200
    assert result["data"]["draft_words"] == []


@pytest.mark.asyncio
async def test_confirm_ocr_success(service, mock_session):
    from app.services.ocr_service import _drafts

    _drafts[1] = [{"english": "old", "chinese": "旧", "type": "word"}]

    mock_unit = MagicMock(id=1)
    mock_unit_repo = MagicMock()
    mock_unit_repo.get_by_id = AsyncMock(return_value=mock_unit)

    with patch("app.services.ocr_service.UnitRepo", return_value=mock_unit_repo), \
         patch.object(service.word_service, "batch_create", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = {"code": 200, "data": {"created_count": 1, "words": []}}
        words = [{"english": "hello", "chinese": "你好", "type": "word"}]
        result = await service.confirm_ocr(1, words)

    assert result["code"] == 200
    assert 1 not in _drafts
