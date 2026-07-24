"""ECDICT 导入脚本的纯函数测试（不连真实 DB）。

scripts/import_ecdict.py 的 _clean / _truncate / _normalize 是无副作用的纯函数，
直接测其字段回填与音标规整逻辑。导入该模块会触发 app.database 的 engine 创建
（懒连接、不实际连库），在测试环境无害。
"""
import sys
from pathlib import Path

# scripts/ 是命名空间包（无 __init__.py），需把 backend 根加入 sys.path 才能 import
_BACKEND = str(Path(__file__).resolve().parents[2])
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from scripts.import_ecdict import _clean, _normalize, _truncate  # noqa: E402


def test_clean_strips_whitespace_and_wrapping_slashes():
    # 音标统一存裸 IPA：去首尾空白 + 去包裹斜杠
    assert _clean("  /həˈloʊ/  ") == "həˈloʊ"
    assert _clean("/həˈloʊ/") == "həˈloʊ"
    assert _clean("həˈloʊ") == "həˈloʊ"


def test_clean_handles_empty_and_none():
    assert _clean("") == ""
    assert _clean(None) == ""
    assert _clean("   ") == ""


def test_normalize_extracts_rich_fields():
    row = {
        "word": "hello", "translation": "你好",
        "collins": "4", "oxford": "1",
        "phonetic": "/həˈloʊ/", "definition": "used as a greeting",
        "pos": "int.",
    }
    n = _normalize(row)
    assert n["word"] == "hello"
    assert n["collins"] == 4 and n["oxford"] == 1
    assert n["phonetic"] == "həˈloʊ"   # 去斜杠
    assert n["definition"] == "used as a greeting"
    assert n["pos"] == "int."


def test_normalize_missing_rich_fields_become_empty_string():
    n = _normalize({"word": "x", "translation": "X"})
    assert n["phonetic"] == ""
    assert n["definition"] == ""
    assert n["pos"] == ""


def test_normalize_empty_translation_falls_back_handled_by_caller():
    # _normalize 只负责规整，空 translation 由调用方处理（cn = translation or word）
    n = _normalize({"word": "solo", "translation": ""})
    assert n["word"] == "solo"
    assert n["translation"] == ""


def test_truncate_limits_and_nullifies():
    assert _truncate("abc", 10) == "abc"
    assert _truncate("abcdef", 3) == "abc"
    assert _truncate("", 10) is None
    assert _truncate(None, 10) is None
    assert _truncate("   ", 10) is None   # 全空白 -> None（nullable 语义）
