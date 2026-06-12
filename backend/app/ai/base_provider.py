import json
import logging

from app.ai.base import (
    DialogueLine, DialogueResult, ExerciseItem, ExerciseResult,
    OCRResult, OCRWordItem, ParseNLResult, ParseNLWordItem,
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

SYSTEM_PROMPT_PARSE_NL = """你是一个英语学习材料解析助手。用户会提供一段自然语言文本，其中包含英语单词、短语、句子及其对应的中文释义。

请从文本中提取所有英语词条，返回严格 JSON 格式：
{
  "words": [
    {"english": "hello", "chinese": "你好", "type": "word"},
    {"english": "How are you?", "chinese": "你好吗？", "type": "sentence"}
  ]
}

规则：
- 仔细分析文本，提取每一个英语词条和对应的中文释义
- type 只能是 "word" 或 "sentence"
- 单个单词或短语（2-4个词）算 "word"
- 完整句子（有主谓结构）算 "sentence"
- 如果文本中同时包含单词和句子，都要提取
- 如果中文释义不明确，根据上下文合理推断
- 忽略与英语学习无关的内容（如页码、章节标题等）
- 只返回 JSON，不要其他内容"""


class BaseAIProvider:
    """Shared parsing logic for all AI providers."""

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

    def _parse_nl(self, text: str) -> ParseNLResult:
        data = self._extract_json(text)
        if not data:
            return ParseNLResult(words=[], raw_text=text)
        words = [
            ParseNLWordItem(
                english=item["english"], chinese=item["chinese"],
                word_type=item.get("type", "word"),
            )
            for item in data.get("words", [])
        ]
        return ParseNLResult(words=words, raw_text=text)

    @staticmethod
    def _guess_media_type(filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
        return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
