from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member


class MemberRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[Member]:
        result = await self.session.execute(select(Member).order_by(Member.id))
        return list(result.scalars().all())

    async def get_by_id(self, member_id: int) -> Member | None:
        return await self.session.get(Member, member_id)
