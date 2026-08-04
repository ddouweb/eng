from typing import Any, Generic, TypeVar, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepo(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def get_by_id_for_update(self, id: int) -> ModelType | None:
        """同 get_by_id，但加 FOR UPDATE 行锁，串行化对同一行的并发事务。

        典型用途：submit_answer 锁父 PracticeSession 行，使同一会话的并发提交
        串行——第二条提交等第一条提交后即可在去重查询里读到已存在记录，避免
        双插入/双计 XP。SQLite 下 with_for_update 为 no-op（单写者串行，测试安全）。
        """
        stmt = select(self.model).where(self.model.id == id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self, *, page: int = 1, page_size: int = 20, filters: list[Any] | None = None
    ) -> tuple[Sequence[ModelType], int]:
        stmt = select(self.model)
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(total_stmt)
        total = total_result.scalar_one()
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return result.scalars().all(), total

    async def create(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelType, data: dict[str, Any]) -> ModelType:
        for key, value in data.items():
            if value is not None:
                setattr(obj, key, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def get_paginated(
        self, stmt: Select, *, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[ModelType], int]:
        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(total_stmt)).scalar_one()
        result = await self.session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return result.scalars().all(), total
