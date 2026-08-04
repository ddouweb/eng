import hashlib
import io
import logging
from pathlib import Path

import anyio

logger = logging.getLogger(__name__)

# backend/static/audio/  —— 同一 (text, lang) 只合成一次，落盘后直接读文件
_CACHE_DIR = Path(__file__).resolve().parents[2] / "static" / "audio"
# 缓存文件数上限：/tts/generate 公网免登录，防恶意用大量不同文本把磁盘撑爆；
# 超限按 mtime 淘汰最旧的一批（留 5% 余量，避免每次写都触发扫描）。
_CACHE_MAX_FILES = 2000


class TTSService:
    """Text-to-Speech using edge-tts (free, no API key required).

    带磁盘缓存：同一 (text, lang) 只合成一次，结果落盘到 static/audio/，
    后续请求直接读文件返回（秒回、可离线、配合免登录路由即可被播放）。

    可靠性：所有文件 I/O（exists/read/mkdir/write）都是同步阻塞操作，通过
    anyio.to_thread.run_sync 移出事件循环——公开端点高并发时不会钉死唯一 async
    worker（否则连登录/提交等请求都会被拖慢）。缓存另设文件数上限 + 最久访问淘汰，
    防止免登录端点被不同文本撑爆磁盘。
    """

    async def generate(self, text: str, lang: str = "en") -> bytes:
        text = (text or "").strip()
        if not text:
            return b""

        cache_path = self._cache_path(text, lang)
        # 同步文件 I/O 移出事件循环（公开端点高并发时避免钉死 worker）
        if await anyio.to_thread.run_sync(cache_path.exists):
            return await anyio.to_thread.run_sync(cache_path.read_bytes)

        audio_bytes = await self._synthesize(text, lang)
        if audio_bytes:
            try:
                await anyio.to_thread.run_sync(self._write_cache, cache_path, audio_bytes)
            except OSError as e:
                logger.warning("TTS 缓存写盘失败 %s: %s", cache_path, e)
        return audio_bytes

    @staticmethod
    def _write_cache(cache_path: Path, audio_bytes: bytes) -> None:
        """落盘 + 缓存上限淘汰（同步阻塞，须在 worker 线程执行）。"""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(audio_bytes)
        TTSService._enforce_cache_cap()

    @staticmethod
    def _enforce_cache_cap() -> None:
        """缓存文件数超过 _CACHE_MAX_FILES 时，按 mtime 淘汰最旧的一批。"""
        try:
            files = [p for p in _CACHE_DIR.iterdir() if p.is_file()]
        except FileNotFoundError:
            return
        if len(files) <= _CACHE_MAX_FILES:
            return
        keep = int(_CACHE_MAX_FILES * 0.95)  # 留 5% 余量，避免每次写都触发淘汰
        files.sort(key=lambda p: p.stat().st_mtime)
        for p in files[: max(0, len(files) - keep)]:
            try:
                p.unlink()
            except OSError:
                pass

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
