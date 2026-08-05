from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import MasteryRecord
from app.models.unit import Unit
from app.models.wrong_book import WrongWordBook
from app.models.word import Word
from app.repositories.wrong_book_repo import WrongWordBookRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException
from app.services.badge_service import award_badge_if_new


class WrongBookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = WrongWordBookRepo(session)

    async def list(
        self,
        member_id: int,
        page: int,
        page_size: int,
        sort_by: str = "added_at",
        order: str = "desc",
    ) -> dict:
        total = await self.repo.count_by_member(member_id)
        if total == 0:
            return success(
                data={"items": [], "total": 0, "page": page, "page_size": page_size}
            )

        base_filter = WrongWordBook.member_id == member_id

        # 排序字段白名单：added_at(默认,最近加入) / wrong_count(错误次数) / english(英文)。
        # 统一以 word_id 作确定性 tiebreaker —— 同值时保证分页顺序稳定，避免翻页错位/丢行。
        sort_columns = {
            "added_at": WrongWordBook.added_at,
            "wrong_count": WrongWordBook.wrong_count,
            "english": Word.english,
        }
        sort_col = sort_columns.get(sort_by, WrongWordBook.added_at)
        order_expr = sort_col.desc() if order == "desc" else sort_col.asc()

        # count 已单独算过；这里只取分页数据，join 一次性带出 Word / Unit / Mastery
        stmt = (
            select(
                WrongWordBook,
                Word,
                Unit.title.label("unit_title"),
                MasteryRecord,
            )
            .join(Word, Word.id == WrongWordBook.word_id)
            .outerjoin(Unit, Unit.id == Word.unit_id)
            .outerjoin(
                MasteryRecord,
                (MasteryRecord.member_id == WrongWordBook.member_id)
                & (MasteryRecord.word_id == WrongWordBook.word_id),
            )
            .where(base_filter)
            .order_by(order_expr, WrongWordBook.word_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        items = []
        for wb, word, unit_title, mastery in rows:
            items.append({
                "id": wb.id,
                "word_id": wb.word_id,
                "english": word.english,
                "chinese": word.chinese,
                "unit_id": word.unit_id,
                "unit_title": unit_title,
                "word_type": word.type.value,
                "added_at": wb.added_at.isoformat() if wb.added_at else None,
                "wrong_count": wb.wrong_count,
                "mastery_level": mastery.level.value if mastery else None,
                "mastery_wrong_count": mastery.wrong_count if mastery else 0,
                "mastery_correct_count": mastery.correct_count if mastery else 0,
            })

        return success(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )

    async def count(self, member_id: int) -> dict:
        total = await self.repo.count_by_member(member_id)
        return success(data={"total": total})

    async def remove(self, member_id: int, word_id: int) -> dict:
        deleted = await self.repo.delete_by_member_word(member_id, word_id)
        if not deleted:
            raise AppException(404, "该词不在错题本中")
        await self.session.commit()
        # 错题本清零徽章：删完最后一个错题（规模归 0）时发放。
        if await self.repo.count_by_member(member_id) == 0:
            if await award_badge_if_new(self.session, member_id, "wrongbook_clear"):
                await self.session.commit()
        return success(data={"word_id": word_id})

    async def clear(self, member_id: int) -> dict:
        removed = await self.repo.delete_all_by_member(member_id)
        await self.session.commit()
        # 错题本清零徽章：仅当确有错题被清空（removed>0）时发放，避免空错题本误发。
        if removed and await award_badge_if_new(self.session, member_id, "wrongbook_clear"):
            await self.session.commit()
        return success(data={"removed": removed})

    async def add_manual(self, member_id: int, word_id: int) -> dict:
        word = await self.session.get(Word, word_id)
        if not word:
            raise AppException(404, "Word not found")

        existing = await self.repo.get_by_member_word(member_id, word_id)
        if existing:
            return success(data={"id": existing.id, "already_existed": True})

        await self.repo.upsert_on_wrong(member_id, word_id)
        await self.session.commit()
        return success(data={"word_id": word_id, "already_existed": False})
