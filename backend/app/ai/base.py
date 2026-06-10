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


class AIProvider(Protocol):
    async def parse_image(self, image_bytes: bytes, filename: str = "") -> OCRResult: ...
    async def generate_dialogue(self, words: list[str], scenario: str) -> str: ...
    async def generate_exercise(self, words: list[str], mode: str) -> str: ...
