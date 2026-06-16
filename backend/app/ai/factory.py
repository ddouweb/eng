from __future__ import annotations

from app.ai.base import AIProvider

_provider: AIProvider | None = None


def _create(provider_name: str, api_key: str, model: str = "") -> AIProvider:
    if provider_name == "claude":
        from app.ai.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key)
    elif provider_name == "deepseek":
        from app.ai.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(api_key=api_key, model=model or "deepseek-chat")
    elif provider_name == "glm":
        from app.ai.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(
            api_key=api_key,
            model=model or "glm-4-flash",
            base_url="https://open.bigmodel.cn/api/paas/v4",
        )
    raise ValueError(f"Unknown AI provider: {provider_name}")


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is not None:
        return _provider
    from app.config import settings
    _provider = _create(settings.AI_PROVIDER, settings.AI_API_KEY, settings.AI_MODEL)
    return _provider


async def close_ai_provider() -> None:
    global _provider
    if _provider is not None and hasattr(_provider, "close"):
        await _provider.close()
        _provider = None
