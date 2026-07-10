"""音标查询的共享工具（发音音频见 api_client.get_tts_url）。

音标用 ``eng_to_ipa`` 本地词典查询（零网络请求）；词典未收录的
（句子、专有名词、OOV 词，结果末尾会带 ``*`` 标记）返回空串，
由调用方决定是否展示。

单词管理 / 错题本 / 练习页统一用这里的 ``phonetic``，避免重复实现与多份缓存。
"""
from __future__ import annotations

try:
    import eng_to_ipa as _ipa

    _HAS_IPA = True
except ImportError:
    _ipa = None
    _HAS_IPA = False

_CACHE: dict[str, str] = {}


def phonetic(english: str) -> str:
    """返回 IPA 音标；词典未命中（含 OOV 推测，末尾带 ``*``）返回空串。"""
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
