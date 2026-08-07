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


def _make_word(id=1, english="hello", chinese="你好", type="word", unit_id=1,
               phonetic=None, definition=None, pos=None, example=None):
    w = MagicMock(id=id, english=english, chinese=chinese, unit_id=unit_id,
                  phonetic=phonetic, definition=definition, pos=pos, example=example)
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
    w = MagicMock(id=id, english=english, chinese=chinese, unit_id=unit_id, seq=None,
                  phonetic=None, definition=None, pos=None, example=None)
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
    assert item["mastery_level"] == "learning"  # 前端单词列表按此字符串渲染掌握度
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
    assert result["data"]["items"][0]["mastery_level"] is None
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


@pytest.mark.asyncio
async def test_to_dict_includes_rich_fields(service):
    """_to_dict 必须输出 phonetic/definition/pos/example 富字段（新加列）。"""
    rich = _make_word(
        phonetic="həˈloʊ", definition="used as a greeting",
        pos="int.", example="Hello! 你好！",
    )
    service.repo.get_by_id = AsyncMock(return_value=_make_word())
    service.repo.update = AsyncMock(return_value=rich)
    result = await service.update_word(1, {"english": "hello"})
    d = result["data"]
    assert d["phonetic"] == "həˈloʊ"
    assert d["definition"] == "used as a greeting"
    assert d["pos"] == "int."
    assert d["example"] == "Hello! 你好！"   # example 原样透传


@pytest.mark.asyncio
async def test_batch_create_passes_rich_fields_through(service, mock_session):
    """batch_create 用 **d 透传，富字段应原样进入 Word 构造。"""
    service.repo.batch_create = AsyncMock(return_value=[_make_word()])
    await service.batch_create(1, [{
        "english": "hello", "chinese": "你好", "type": "word",
        "phonetic": "həˈloʊ", "definition": "greeting",
        "pos": "int.", "example": "Hi!",
    }])
    # repo.batch_create 收到的是 Word 实例列表（由 service 用 **d 构造）
    created = service.repo.batch_create.call_args.args[0]
    assert created[0].phonetic == "həˈloʊ"
    assert created[0].pos == "int."


@pytest.mark.asyncio
async def test_get_by_unit_emits_mastery_level_string(service):
    """单词管理页按 mastery_level(字符串)渲染掌握度;get_by_unit 必须给出该字段
    (旧实现只给 mastery 对象,前端读不到 mastery_level,所有词都误显「未学」)。"""
    service.repo.get_by_unit = AsyncMock(return_value=([_make_search_word()], 1))
    result = await service.get_by_unit(3, page=1, page_size=50)
    item = result["data"]["items"][0]
    assert item["mastery_level"] == "learning"
    assert item["mastery"]["level"] == "learning"  # 兼容:对象仍保留


@pytest.mark.asyncio
async def test_get_by_unit_mastery_level_none_when_no_record(service):
    w = _make_search_word()
    w.mastery_records = []  # 无记录 -> mastery_level 为 None(前端回落显示「未学」)
    service.repo.get_by_unit = AsyncMock(return_value=([w], 1))
    result = await service.get_by_unit(3)
    assert result["data"]["items"][0]["mastery_level"] is None
