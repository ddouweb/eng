import logging

import httpx

from app.ai.base import DialogueResult, ExerciseResult, ParseNLResult
from app.ai.base_provider import (
    BaseAIProvider, SYSTEM_PROMPT_DIALOGUE, SYSTEM_PROMPT_EXERCISE,
    SYSTEM_PROMPT_PARSE_NL,
)

logger = logging.getLogger(__name__)

_HEADERS = {
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}


class ClaudeProvider(BaseAIProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                headers={**_HEADERS, "x-api-key": self.api_key},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _call_api(self, payload: dict) -> dict:
        client = await self._get_client()
        resp = await client.post(self.base_url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult:
        data = await self._call_api({
            "model": self.model, "max_tokens": 2048,
            "system": SYSTEM_PROMPT_DIALOGUE,
            "messages": [{"role": "user", "content": f"单词：{', '.join(words)}\n场景：{scenario}"}],
        })
        return self._parse_dialogue(data["content"][0]["text"])

    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult:
        data = await self._call_api({
            "model": self.model, "max_tokens": 2048,
            "system": SYSTEM_PROMPT_EXERCISE,
            "messages": [{"role": "user", "content": f"单词：{', '.join(words)}\n练习类型：{mode}"}],
        })
        return self._parse_exercise(data["content"][0]["text"])

    async def parse_natural_language(self, text: str) -> ParseNLResult:
        data = await self._call_api({
            "model": self.model, "max_tokens": 4096,
            "system": SYSTEM_PROMPT_PARSE_NL,
            "messages": [{"role": "user", "content": text}],
        })
        return self._parse_nl(data["content"][0]["text"])
