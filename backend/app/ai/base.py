from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class OCRWordItem:
    english: str
    chinese: str
    word_type: str = "word"


@dataclass
class OCRResult:
    words: list[OCRWordItem] = field(default_factory=list)
    raw_text: str = ""


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


class AIProvider(Protocol):
    async def parse_image(self, image_bytes: bytes, filename: str = "") -> OCRResult: ...
    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult: ...
    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult: ...
