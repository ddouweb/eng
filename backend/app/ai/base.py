from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class DialogueLine:
    role: str  # teacher / student / narrator
    english: str
    chinese: str


@dataclass
class DialogueResult:
    scenario: str
    lines: list[DialogueLine] = field(default_factory=list)


@dataclass
class ExerciseItem:
    question: str
    options: list[str] = field(default_factory=list)
    answer: str = ""
    explanation: str = ""


@dataclass
class ExerciseResult:
    mode: str
    items: list[ExerciseItem] = field(default_factory=list)


@dataclass
class ParseNLWordItem:
    english: str
    chinese: str
    word_type: str = "word"
    phonetic: str = ""
    pos: str = ""
    example: str = ""


@dataclass
class ParseNLResult:
    words: list[ParseNLWordItem] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class CheckinEncouragementResult:
    """每日签到 AI 励学寄语（best-effort：解析失败时 message 兜底为原文）。"""
    title: str = ""
    message: str = ""


class AIProvider(Protocol):
    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult: ...
    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult: ...
    async def parse_natural_language(self, text: str) -> ParseNLResult: ...
    async def generate_checkin_encouragement(self, profile_summary: str) -> CheckinEncouragementResult: ...
