import hashlib
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/static/audio/  —— 同一 (text, lang) 只合成一次，落盘后直接读文件
_CACHE_DIR = Path(__file__).resolve().parents[2] / "static" / "audio"


class TTSService:
    """Text-to-Speech using edge-tts (free, no API key required).

    带磁盘缓存：同一 (text, lang) 只合成一次，结果落盘到 static/audio/，
    后续请求直接读文件返回（秒回、可离线、配合免登录路由即可被 st.audio 播放）。
    """

    async def generate(self, text: str, lang: str = "en") -> bytes:
        text = (text or "").strip()
        if not text:
            return b""

        cache_path = self._cache_path(text, lang)
        if cache_path.exists():
            return cache_path.read_bytes()

        audio_bytes = await self._synthesize(text, lang)
        if audio_bytes:
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(audio_bytes)
            except OSError as e:
                logger.warning("TTS 缓存写盘失败 %s: %s", cache_path, e)
        return audio_bytes

    async def _synthesize(self, text: str, lang: str) -> bytes:
        try:
            import edge_tts
        except ImportError:
            logger.warning("edge-tts not installed, returning empty audio")
            return b""

        voice = "en-US-AriaNeural" if lang == "en" else "zh-CN-XiaoxiaoNeural"
        try:
            communicate = edge_tts.Communicate(text, voice)
            buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buffer.write(chunk["data"])
            return buffer.getvalue()
        except Exception as e:  # noqa: BLE001 —— 网络/服务异常时优雅降级，返回空让端点回 503
            logger.warning("edge-tts 合成失败 (%r): %s", text, e)
            return b""

    @staticmethod
    def _cache_path(text: str, lang: str) -> Path:
        digest = hashlib.md5(text.lower().encode("utf-8")).hexdigest()
        return _CACHE_DIR / f"{lang}_{digest}.mp3"


_tts_service: TTSService | None = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
