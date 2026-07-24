"""音标查询的共享工具（发音音频见 api_client.get_tts_url）。

音标优先用词条已存储的 ``phonetic``（来自 ECDICT 导入或 AI 解析，已规整为裸 IPA）；
缺省时回退 ``eng_to_ipa`` 本地词典实时计算（零网络）。两者都返回**裸 IPA**（不含
包裹斜杠），由调用方在展示时统一加 /.../。

单词管理 / 错题本 / 练习页 / 查询页统一用这里的 ``phonetic``，避免重复实现与多份缓存。
"""
from __future__ import annotations

try:
    import eng_to_ipa as _ipa

    _HAS_IPA = True
except ImportError:
    _ipa = None
    _HAS_IPA = False

_CACHE: dict[str, str] = {}


def phonetic(english: str, stored: str | None = None) -> str:
    """返回裸 IPA 音标（不含包裹斜杠；展示方各自包 /.../）；无音标返回空串。

    - ``stored`` 非空（来自 Word.phonetic）优先返回，跳过本地词典计算；
    - 否则回退 ``eng_to_ipa`` 实时转换（OOV / 句子等未命中返回空串）。
    """
    if stored:
        # 入库时已规整为裸 IPA，这里再去一次斜杠做双保险
        return stored.strip().strip("/")
    if not english or not _HAS_IPA:
        return ""
    s = english.strip()
    if not s:
        return ""
    cached = _CACHE.get(s)
    if cached is not None:
        return cached
    try:
        result = _ipa.convert(s, keep_punct=False)
    except Exception:  # noqa: BLE001 —— 词典异常时优雅降级为空
        result = ""
    # 末尾 * 表示词典未命中、结果不可靠，不展示
    if result.endswith("*"):
        result = ""
    _CACHE[s] = result
    return result
