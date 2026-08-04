from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.ai.tts_service import get_tts_service
from app.utils.rate_limit import SlidingWindowLimiter

router = APIRouter(prefix="/tts", tags=["tts"])

# 免登录公开端点限流：每 IP 每 60s 30 次。防止公网滥用（不同文本可迅速撑满磁盘缓存、
# 或缓存未命中时触发 edge-tts 网络合成消耗带宽/CPU）。超限返回 429（经统一信封）。
_tts_limiter = SlidingWindowLimiter(max_requests=30, window_seconds=60)


async def _tts_rate_limit(request: Request) -> None:
    # 优先取反向代理透传的真实 IP（生产经 nginx），否则回退直连 client host
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    if not _tts_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


@router.get("/generate", dependencies=[Depends(_tts_rate_limit)])
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
    # 同一 (text,lang) 内容确定不变：让浏览器/中间件长期缓存，重复播放不再回源（含旧页面）。
    return Response(
        content=audio_bytes, media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )
