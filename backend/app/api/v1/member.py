from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories.member_repo import MemberRepo
from app.schemas.common import success

router = APIRouter(prefix="/members", tags=["members"])


@router.get("")
async def list_members(db: AsyncSession = Depends(get_db)):
    """列出所有家庭成员。

    Example:
        curl http://localhost:8000/api/v1/members
    """
    repo = MemberRepo(db)
    members = await repo.get_all()
    return success(data=[
        {"id": m.id, "name": m.name, "avatar": m.avatar}
        for m in members
    ])
