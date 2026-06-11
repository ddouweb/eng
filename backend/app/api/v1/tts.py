from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.ai.tts_service import get_tts_service

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/generate")
async def generate_tts(
    text: str = Query(..., max_length=500),
    lang: str = Query("en", pattern="^(en|zh)$"),
):
    """文本转语音。

    Example:
        直接在浏览器打开: http://localhost:8000/api/v1/tts/generate?text=hello&lang=en
    """
    svc = get_tts_service()
    audio_bytes = await svc.generate(text, lang)
    if not audio_bytes:
        return Response(content=b"", media_type="audio/mpeg", status_code=503)
    return Response(content=audio_bytes, media_type="audio/mpeg")
