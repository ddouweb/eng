"""BaseAIProvider 的 NL 解析测试：富字段（音标/词性/例句）透传与规整。

_parse_nl 从 AI 返回的 JSON 抽取词条；音标统一去包裹斜杠成裸 IPA（与 ECDICT 导入一致）。
"""
from app.ai.base import ParseNLWordItem
from app.ai.base_provider import BaseAIProvider


def _provider():
    # BaseAIProvider 是共享解析逻辑的基类，无需 __init__ 参数
    return BaseAIProvider()


def test_parse_nl_passes_through_rich_fields():
    raw = '{"words": [{"english": "hello", "chinese": "你好", "type": "word", ' \
          '"phonetic": "/həˈloʊ/", "pos": "int.", "example": "Hello! 你好！"}]}'
    w: ParseNLWordItem = _provider()._parse_nl(raw).words[0]
    assert w.english == "hello"
    assert w.chinese == "你好"
    assert w.word_type == "word"
    assert w.phonetic == "həˈloʊ"   # 去包裹斜杠，统一裸 IPA
    assert w.pos == "int."
    assert w.example == "Hello! 你好！"


def test_parse_nl_defaults_empty_when_rich_fields_missing():
    raw = '{"words": [{"english": "hi", "chinese": "嗨"}]}'
    w = _provider()._parse_nl(raw).words[0]
    assert w.phonetic == ""
    assert w.pos == ""
    assert w.example == ""
    assert w.word_type == "word"   # 缺省 type -> "word"


def test_parse_nl_strips_whitespace_and_slashes_on_phonetic():
    raw = '{"words": [{"english": "hi", "chinese": "嗨", ' \
          '"phonetic": "  /haɪ/  ", "pos": "  int.  "}]}'
    w = _provider()._parse_nl(raw).words[0]
    assert w.phonetic == "haɪ"      # 同时去空白与斜杠
    assert w.pos == "int."          # 仅去空白


def test_parse_nl_tolerates_codefenced_json():
    raw = '```json\n{"words": [{"english": "go", "chinese": "去", "pos": "v."}]}\n```'
    w = _provider()._parse_nl(raw).words[0]
    assert w.english == "go" and w.pos == "v."


def test_parse_nl_empty_words_on_bad_json():
    assert _provider()._parse_nl("not json at all").words == []
    assert _provider()._parse_nl("").words == []
