import json
import base64

import httpx

from app.ai.base import OCRResult, OCRWordItem


SYSTEM_PROMPT = """你是一个英语教材 OCR 解析助手。用户会上传一张教材页面图片。
请识别图片中的所有英文单词、句子及其对应的中文释义。

返回严格 JSON 格式：
{
  "words": [
    {"english": "hello", "chinese": "你好", "type": "word"},
    {"english": "How are you?", "chinese": "你好吗？", "type": "sentence"}
  ]
}

规则：
- type 只能是 "word" 或 "sentence"
- 英文短语（2-4个词）也算 "word"
- 完整句子（有主谓结构）算 "sentence"
- 只返回 JSON，不要其他内容"""


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def parse_image(self, image_bytes: bytes, filename: str = "") -> OCRResult:
        media_type = self._guess_media_type(filename)
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_b64,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "请解析这张教材图片中的英文单词和句子。",
                                },
                            ],
                        }
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["content"][0]["text"]

        return self._parse_response(text)

    async def generate_dialogue(self, words: list[str], scenario: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 2048,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"用以下单词生成一段{scenario}场景对话：{', '.join(words)}。要求包含中英文对照。",
                        }
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]

    async def generate_exercise(self, words: list[str], mode: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 2048,
                    "messages": [
                        {
                            "role": "user",
                            "content": f"用以下单词生成{mode}练习题：{', '.join(words)}",
                        }
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]

    def _parse_response(self, text: str) -> OCRResult:
        try:
            json_str = text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            data = json.loads(json_str)
            words = [
                OCRWordItem(
                    english=item["english"],
                    chinese=item["chinese"],
                    word_type=item.get("type", "word"),
                )
                for item in data.get("words", [])
            ]
            return OCRResult(words=words, raw_text=text)
        except (json.JSONDecodeError, KeyError) as e:
            return OCRResult(words=[], raw_text=text)

    @staticmethod
    def _guess_media_type(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        mapping = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
        return mapping.get(ext, "image/png")
