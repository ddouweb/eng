import base64
import logging

import httpx

from app.ai.base import OCRResult, DialogueResult, ExerciseResult, ParseNLResult
from app.ai.base_provider import (
    BaseAIProvider, SYSTEM_PROMPT_OCR, SYSTEM_PROMPT_DIALOGUE, SYSTEM_PROMPT_EXERCISE,
    SYSTEM_PROMPT_PARSE_NL,
)

logger = logging.getLogger(__name__)


class DeepSeekProvider(BaseAIProvider):
    def __init__(self, api_key: str, model: str = "deepseek-chat", base_url: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _chat(self, messages: list[dict], max_tokens: int = 4096) -> str:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def parse_image(self, image_bytes: bytes, filename: str = "") -> OCRResult:
        mime = self._guess_media_type(filename)
        b64 = base64.b64encode(image_bytes).decode()
        text = await self._chat([
            {"role": "system", "content": SYSTEM_PROMPT_OCR},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": "请解析这张教材图片中的英文单词和句子。"},
            ]},
        ])
        return self._parse_ocr(text)

    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult:
        text = await self._chat([
            {"role": "system", "content": SYSTEM_PROMPT_DIALOGUE},
            {"role": "user", "content": f"单词：{', '.join(words)}\n场景：{scenario}"},
        ], max_tokens=2048)
        return self._parse_dialogue(text)

    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult:
        text = await self._chat([
            {"role": "system", "content": SYSTEM_PROMPT_EXERCISE},
            {"role": "user", "content": f"单词：{', '.join(words)}\n练习类型：{mode}"},
        ], max_tokens=2048)
        return self._parse_exercise(text)

    async def parse_natural_language(self, text: str) -> ParseNLResult:
        result = await self._chat([
            {"role": "system", "content": SYSTEM_PROMPT_PARSE_NL},
            {"role": "user", "content": text},
        ], max_tokens=4096)
        return self._parse_nl(result)
