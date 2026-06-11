from app.ai.base import AIProvider
from app.config import settings


def get_ai_provider() -> AIProvider:
    if settings.AI_PROVIDER == "claude":
        from app.ai.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=settings.AI_API_KEY)
    if settings.AI_PROVIDER == "deepseek":
        from app.ai.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(api_key=settings.AI_API_KEY)
    raise ValueError(f"Unknown AI provider: {settings.AI_PROVIDER}")
