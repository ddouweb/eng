from __future__ import annotations

from app.ai.base import AIProvider

_provider: AIProvider | None = None


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is not None:
        return _provider
    from app.config import settings
    if settings.AI_PROVIDER == "claude":
        from app.ai.claude_provider import ClaudeProvider
        _provider = ClaudeProvider(api_key=settings.AI_API_KEY)
    elif settings.AI_PROVIDER == "deepseek":
        from app.ai.deepseek_provider import DeepSeekProvider
        _provider = DeepSeekProvider(api_key=settings.AI_API_KEY)
    else:
        raise ValueError(f"Unknown AI provider: {settings.AI_PROVIDER}")
    return _provider


async def close_ai_provider() -> None:
    global _provider
    if _provider is not None and hasattr(_provider, "close"):
        await _provider.close()
        _provider = None
