"""徽章发放共享基元。

提供幂等发放函数 ``award_badge_if_new``，供 practice / stats / checkin / plan /
wrong_book 等所有写入路径复用，消除原先散落在 ``PracticeService._award_badge_if_new``
与 ``StatsService._settle_one_week`` 里两份重复的「SELECT 预过滤 + uq_member_badge
唯一约束兜底」逻辑。

调用方负责事务 / savepoint 边界；本函数仅 ``add`` + ``flush``（不 ``commit``）。
在 ``begin_nested()`` savepoint 内调用时，``flush`` 受该 savepoint 约束，
随 savepoint 回滚而回滚（与 row 同原子）。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.streak import MemberBadge


async def award_badge_if_new(session: AsyncSession, member_id: int, key: str) -> bool:
    """幂等发放一枚徽章。已存在返回 False；新发放 ``add``+``flush`` 后返回 True。

    幂等两层：① SELECT 预过滤（快速路径，绝大多数命中）；② ``uq_member_badge``
    唯一约束兜底（并发竞态时由调用方事务整体回滚自愈，下次重提 SELECT 已命中）。
    """
    existing = await session.scalar(
        select(MemberBadge).where(
            MemberBadge.member_id == member_id, MemberBadge.badge_key == key,
        )
    )
    if existing:
        return False
    session.add(MemberBadge(member_id=member_id, badge_key=key))
    await session.flush()
    return True
