from datetime import datetime

from pydantic import BaseModel


class WrongWordItem(BaseModel):
    """错题本列表项：错题本记录 + 单词 + Unit 标题 + 掌握度聚合。"""

    id: int
    word_id: int
    english: str
    chinese: str
    unit_id: int
    unit_title: str | None = None
    word_type: str
    added_at: datetime
    wrong_count_snapshot: int
    mastery_level: str | None = None
    mastery_wrong_count: int = 0
    mastery_correct_count: int = 0


class WrongBookPage(BaseModel):
    items: list[WrongWordItem]
    total: int
    page: int
    page_size: int
