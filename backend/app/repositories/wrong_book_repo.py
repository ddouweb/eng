from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wrong_book import WrongWordBook
from app.repositories.base import BaseRepo


class WrongWordBookRepo(BaseRepo[WrongWordBook]):
    def __init__(self, session: AsyncSession):
        super().__init__(WrongWordBook, session)

    async def get_by_member_word(
        self, member_id: int, word_id: int
    ) -> WrongWordBook | None:
        stmt = select(WrongWordBook).where(
            WrongWordBook.member_id == member_id,
            WrongWordBook.word_id == word_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_on_wrong(
        self, member_id: int, word_id: int, wrong_count_snapshot: int
    ) -> None:
        """答错时调用：已存在则更新 wrong_count_snapshot（added_at 保留）；
        不存在则插入。MySQL 走原生 ON DUPLICATE KEY UPDATE，SQLite 走两步。
        """
        bind = self.session.bind
        dialect = bind.dialect.name if bind else "sqlite"
        if dialect == "mysql":
            await self.session.execute(
                text(
                    "INSERT INTO wrong_word_book (member_id, word_id, wrong_count_snapshot) "
                    "VALUES (:mid, :wid, :wc) "
                    "ON DUPLICATE KEY UPDATE wrong_count_snapshot = VALUES(wrong_count_snapshot)"
                ),
                {"mid": member_id, "wid": word_id, "wc": wrong_count_snapshot},
            )
        else:
            existing = await self.get_by_member_word(member_id, word_id)
            if existing is None:
                self.session.add(
                    WrongWordBook(
                        member_id=member_id,
                        word_id=word_id,
                        wrong_count_snapshot=wrong_count_snapshot,
                    )
                )
            else:
                existing.wrong_count_snapshot = wrong_count_snapshot
        await self.session.flush()

    async def list_word_ids_by_member(self, member_id: int) -> list[int]:
        stmt = select(WrongWordBook.word_id).where(
            WrongWordBook.member_id == member_id
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def delete_by_member_word(self, member_id: int, word_id: int) -> bool:
        stmt = delete(WrongWordBook).where(
            WrongWordBook.member_id == member_id,
            WrongWordBook.word_id == word_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def delete_all_by_member(self, member_id: int) -> int:
        stmt = delete(WrongWordBook).where(WrongWordBook.member_id == member_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def count_by_member(self, member_id: int) -> int:
        stmt = select(func.count()).select_from(WrongWordBook).where(
            WrongWordBook.member_id == member_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
