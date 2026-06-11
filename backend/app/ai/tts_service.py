import logging
import io

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-Speech using edge-tts (free, no API key required)."""

    async def generate(self, text: str, lang: str = "en") -> bytes:
        try:
            import edge_tts
        except ImportError:
            logger.warning("edge-tts not installed, returning empty audio")
            return b""

        voice = "en-US-AriaNeural" if lang == "en" else "zh-CN-XiaoxiaoNeural"
        communicate = edge_tts.Communicate(text, voice)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        return buffer.getvalue()


_tts_service: TTSService | None = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
