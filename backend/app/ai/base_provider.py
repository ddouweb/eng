import json
import logging

from app.ai.base import (
    CheckinEncouragementResult, DialogueLine, DialogueResult, ExerciseItem, ExerciseResult,
    ParseNLResult, ParseNLWordItem,
)

logger = logging.getLogger(__name__)

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
    {"english": "hello", "chinese": "你好", "type": "word", "phonetic": "/həˈloʊ/", "pos": "int.", "example": "Hello, how are you? 你好，你好吗？"},
    {"english": "How are you?", "chinese": "你好吗？", "type": "sentence", "phonetic": "", "pos": "", "example": ""}
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
- phonetic：单词/短语尽量给出 IPA 音标（如 /həˈloʊ/）；原文未提供且无把握时给空串 ""；句子一律给 ""
- pos：单词的词性缩写（如 n. v. adj. adv. prep. int.）；短语/句子给空串 ""
- example：若原文含该词的例句则原样填入；否则尽量造一个简短、适合家庭学习的例句并附中文译文；无把握时给空串 ""
- 只返回 JSON，不要其他内容"""


SYSTEM_PROMPT_CHECKIN = """你是一位温暖、懂鼓励的家庭英语学习陪伴者。

用户每日"签到"时会给你一份他当前的学习状态摘要。请据此写一段**个性化**的鼓励与劝学寄语：肯定他的坚持，结合摘要里的具体数据（连续天数 / 掌握度 / 正确率 / 段位 / freeze 等）给一句正向反馈，再温和地劝他今天继续学一点。语气像家人朋友，真诚不浮夸，适合小学生和家长一起读。

返回严格 JSON 格式：
{
  "title": "不超过 12 字的标题，如「连续5天，真棒！」",
  "message": "2-4 句话的寄语正文"
}

规则：
- 必须结合摘要里的真实数据，不要空泛套话
- message 用中文，2-4 句，自然口语
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

    def _parse_dialogue(self, text: str) -> DialogueResult:
        data = self._extract_json(text)
        if not data:
            return DialogueResult(scenario="", lines=[])
        lines = [
            DialogueLine(role=line.get("role", "narrator"), english=line["english"], chinese=line["chinese"])
            for line in data.get("lines", [])
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
                phonetic=(item.get("phonetic") or "").strip().strip("/"),
                pos=(item.get("pos") or "").strip(),
                example=(item.get("example") or "").strip(),
            )
            for item in data.get("words", [])
        ]
        return ParseNLResult(words=words, raw_text=text)

    def _parse_checkin(self, text: str) -> CheckinEncouragementResult:
        data = self._extract_json(text)
        if not data:
            # 模型偶发不返回 JSON 时，原文兜底（比空串友好）
            return CheckinEncouragementResult(title="今日寄语", message=text.strip().strip("`"))
        return CheckinEncouragementResult(
            title=(data.get("title") or "今日寄语").strip(),
            message=(data.get("message") or "").strip(),
        )
