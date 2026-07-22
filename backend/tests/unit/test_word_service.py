from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import MasteryLevel, TagType, WordType
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
    w = MagicMock(id=id, english=english, chinese=chinese, unit_id=unit_id)
    w.created_at = datetime(2026, 1, 1)
    w.updated_at = datetime(2026, 1, 1)
    # word.type 是 WordType 枚举，业务代码访问 word.type.value
    w.type = MagicMock(value=type)
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
    # level 已是真枚举 MasteryLevel.unlearned，其 .value 本就是 "unlearned"，无需也不可再赋值
    service.mastery_repo.get_or_create = AsyncMock(return_value=record)
    result = await service.get_mastery(1)
    assert result["code"] == 200
    assert result["data"]["level"] == "unlearned"
    mock_session.commit.assert_awaited_once()


def _make_search_word(
    id=1, english="apple", chinese="苹果", unit_id=3, unit_title="Unit 3 - Fruits",
):
    """search() 会读 w.unit.title / w.tags / w.mastery_records，需补齐这些关系。"""
    w = MagicMock(id=id, english=english, chinese=chinese, unit_id=unit_id, seq=None)
    w.created_at = datetime(2026, 1, 1)
    w.updated_at = datetime(2026, 1, 1)
    w.type = MagicMock(value="word")
    w.unit = MagicMock(title=unit_title)
    tag = MagicMock()
    tag.tag = TagType.favorite
    w.tags = [tag]
    w.mastery_records = [MagicMock(
        member_id=1, level=MasteryLevel.learning,
        consecutive_correct=1, correct_count=2, wrong_count=0,
    )]
    return w


@pytest.mark.asyncio
async def test_search_assembles_unit_title_tags_mastery(service):
    service.repo.search = AsyncMock(return_value=([_make_search_word()], 1))
    result = await service.search(q="app", member_id=1)
    assert result["code"] == 200
    assert result["data"]["total"] == 1
    item = result["data"]["items"][0]
    assert item["unit_title"] == "Unit 3 - Fruits"
    assert item["tags"] == ["favorite"]
    assert item["mastery"]["level"] == "learning"
    # 透传给 repo 的参数
    kwargs = service.repo.search.call_args.kwargs
    assert kwargs["q"] == "app" and kwargs["member_id"] == 1


@pytest.mark.asyncio
async def test_search_mastery_none_when_no_record(service):
    w = _make_search_word(id=2, english="banana", chinese="香蕉")
    w.tags = []
    w.mastery_records = []  # 无记录 -> mastery 为 None
    service.repo.search = AsyncMock(return_value=([w], 1))
    result = await service.search(q="ban", member_id=2)
    assert result["data"]["items"][0]["mastery"] is None
    assert service.repo.search.call_args.kwargs["member_id"] == 2


@pytest.mark.asyncio
async def test_search_mastery_none_when_record_is_other_member(service):
    # 记录存在但属于 member 1；按 member 2 搜 -> mastery None（验证 _mastery_from_record 的 member 过滤）
    w = _make_search_word()
    w.mastery_records[0].member_id = 1
    service.repo.search = AsyncMock(return_value=([w], 1))
    result = await service.search(q="x", member_id=2)
    assert result["data"]["items"][0]["mastery"] is None


@pytest.mark.asyncio
async def test_search_forwards_all_filters_to_repo(service):
    service.repo.search = AsyncMock(return_value=([], 0))
    await service.search(
        q="x", member_id=7, level=MasteryLevel.familiar,
        tag=TagType.exam_focus, unit_id=3, word_type=WordType.sentence,
    )
    kw = service.repo.search.call_args.kwargs
    assert kw["level"] is MasteryLevel.familiar
    assert kw["tag"] is TagType.exam_focus
    assert kw["member_id"] == 7
    assert kw["unit_id"] == 3
    assert kw["word_type"] is WordType.sentence
