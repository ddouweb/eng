import hashlib
import json
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

_redis = None


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return _redis
    except Exception as e:
        logger.info("Redis not available, caching disabled: %s", e)
        return None


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None


async def get_cached(key: str) -> Any | None:
    r = _get_redis()
    if not r:
        return None
    try:
        val = await r.get(key)
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None


async def set_cached(key: str, value: Any, ttl: int = 300) -> None:
    r = _get_redis()
    if not r:
        return
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cached(ttl: int = 300, key_prefix: str = "", key_builder: Callable | None = None):
    """Decorator for caching async function results in Redis.

    Falls back to no caching if Redis is unavailable.
    Only use with methods whose args are JSON-serializable.

    缓存键默认纳入参数指纹（剔除 self），避免不同参数命中同一 key 串数据；
    可通过 key_builder 自定义键（接收与被装饰方法相同的参数，返回字符串）。
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            r = _get_redis()
            if not r:
                return await func(*args, **kwargs)

            base = key_prefix or func.__name__
            if key_builder is not None:
                param_part = key_builder(*args, **kwargs)
            else:
                # args[0] 通常是 self（repository），剔除后参与指纹
                try:
                    payload = {"args": list(args[1:]), "kwargs": kwargs}
                    param_part = hashlib.md5(
                        json.dumps(payload, default=str, sort_keys=True).encode()
                    ).hexdigest()[:12]
                except (TypeError, ValueError):
                    param_part = ""  # 不可序列化 → 退化为仅函数名
            cache_key = f"{base}:{param_part}" if param_part else base

            try:
                cached_val = await get_cached(cache_key)
                if cached_val is not None:
                    return cached_val
            except Exception:
                return await func(*args, **kwargs)

            result = await func(*args, **kwargs)
            try:
                await set_cached(cache_key, result, ttl)
            except Exception:
                pass
            return result
        return wrapper
    return decorator
