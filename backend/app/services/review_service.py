from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel
from app.models.mastery import MasteryRecord
from app.models.word import Word
from app.schemas.common import success
from app.utils.phonetics import phonetic


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_due(
        self, member_id: int, unit_ids: list[int] | None = None, limit: int = 50,
    ) -> dict:
        """今日到期复习画像：到期/逾期/新词 计数 + 到期词列表（按紧迫度排序）。

        - due_today：有 mastery 行、next_review_date<=today、level!=permanent。
        - overdue：其中 next_review_date<today（已逾期）。
        - new_available：无 mastery 行的新词（范围内）。
        - permanent 词两边都不计（到期概念不适用；其低频回炉由 weighting 负责）。
        """
        today = date.today()
        stmt = (
            select(Word, MasteryRecord)
            .outerjoin(MasteryRecord, and_(
                MasteryRecord.word_id == Word.id,
                MasteryRecord.member_id == member_id,
            ))
        )
        if unit_ids:
            stmt = stmt.where(Word.unit_id.in_(unit_ids))
        rows = (await self.session.execute(stmt)).all()

        due_items: list[tuple[Word, MasteryRecord]] = []
        new_available = 0
        overdue = 0
        for word, m in rows:
            if m is None:
                new_available += 1
                continue
            if m.level == MasteryLevel.permanent:
                continue
            if m.next_review_date is not None and m.next_review_date <= today:
                due_items.append((word, m))
                if m.next_review_date < today:
                    overdue += 1

        due_items.sort(key=lambda wm: (
            -((today - wm[1].next_review_date).days if wm[1].next_review_date else 0),
            -wm[1].wrong_count,
        ))
        items = [self._item(w, m, today) for w, m in due_items[:limit]]

        return success(data={
            "due_today": len(due_items),
            "overdue": overdue,
            "new_available": new_available,
            "items": items,
        })

    @staticmethod
    def _item(word: Word, m: MasteryRecord, today: date) -> dict:
        nrd = m.next_review_date
        return {
            "word_id": word.id,
            "english": word.english,
            "chinese": word.chinese,
            "phonetic": phonetic(word.english, word.phonetic),
            "pos": word.pos,
            "definition": word.definition,
            "example": word.example,
            "mastery_level": m.level.value,
            "next_review_date": nrd.isoformat() if nrd else None,
            "days_overdue": (today - nrd).days if nrd and nrd < today else 0,
            "wrong_count": m.wrong_count,
        }
