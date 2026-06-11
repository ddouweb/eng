import json
import logging

import httpx

from app.ai.base import (
    DialogueLine, DialogueResult, ExerciseItem, ExerciseResult,
    OCRResult, OCRWordItem,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_OCR = """你是一个英语教材 OCR 解析助手。用户会上传一张教材页面图片。
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

SYSTEM_PROMPT_DIALOGUE = """你是一个英语教学助手，擅长创建贴近生活的英语场景对话。

根据用户给的单词列表和场景，生成一段对话。返回严格 JSON 格式：
{
  "scenario": "场景描述",
  "lines": [
    {"role": "teacher", "english": "Good morning!", "chinese": "早上好！"},
    {"role": "student", "english": "Good morning, teacher.", "chinese": "早上好，老师。"}
  ]
}

规则：
- role 只能是 "teacher"、"student" 或 "narrator"
- 每行对话必须同时包含 english 和 chinese
- 对话应自然使用给定的单词，适合小学生理解
- 对话长度 6-12 行
- 只返回 JSON，不要其他内容"""

SYSTEM_PROMPT_EXERCISE = """你是一个英语教学助手，擅长创建英语练习题。

根据用户给的单词列表和练习类型，生成练习题。返回严格 JSON 格式：
{
  "mode": "练习类型",
  "items": [
    {
      "question": "「你好」的英文是？",
      "options": ["hello", "goodbye", "sorry", "thanks"],
      "answer": "hello",
      "explanation": "hello 是最常用的打招呼用语"
    }
  ]
}

规则：
- choice 模式：每题 4 个选项，1 个正确答案
- fill 模式：question 包含填空提示，answer 是正确答案，options 为空
- 每个单词至少出一题，共 5-10 题
- 题目适合小学生水平
- 只返回 JSON，不要其他内容"""


class DeepSeekProvider:
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

    async def _chat(self, messages: list[dict], max_tokens: int = 4096) -> str:
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def parse_image(self, image_bytes: bytes, filename: str = "") -> OCRResult:
        import base64
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
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

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        json_str = text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning("JSON parse failed: %s | raw: %.200s", e, text)
            return None

    def _parse_ocr(self, text: str) -> OCRResult:
        data = self._extract_json(text)
        if not data:
            return OCRResult(words=[], raw_text=text)
        words = [
            OCRWordItem(english=item["english"], chinese=item["chinese"], word_type=item.get("type", "word"))
            for item in data.get("words", [])
        ]
        return OCRResult(words=words, raw_text=text)

    def _parse_dialogue(self, text: str) -> DialogueResult:
        data = self._extract_json(text)
        if not data:
            return DialogueResult(scenario="", lines=[])
        lines = [
            DialogueLine(role=l.get("role", "narrator"), english=l["english"], chinese=l["chinese"])
            for l in data.get("lines", [])
        ]
        return DialogueResult(scenario=data.get("scenario", ""), lines=lines)

    def _parse_exercise(self, text: str) -> ExerciseResult:
        data = self._extract_json(text)
        if not data:
            return ExerciseResult(mode="", items=[])
        items = [
            ExerciseItem(
                question=item["question"], options=item.get("options", []),
                answer=item.get("answer", ""), explanation=item.get("explanation", ""),
            )
            for item in data.get("items", [])
        ]
        return ExerciseResult(mode=data.get("mode", ""), items=items)
