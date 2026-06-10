from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.unit import UnitCreate, UnitUpdate
from app.services.unit_service import UnitService

router = APIRouter(prefix="/units", tags=["units"])


@router.post("")
async def create_unit(body: UnitCreate, db: AsyncSession = Depends(get_db)):
    """创建 Unit。

    Example:
        curl -X POST http://localhost:8000/api/v1/units \\
             -H 'Content-Type: application/json' \\
             -d '{"title":"Unit 1","sequence":1}'
    """
    svc = UnitService(db)
    return await svc.create_unit(body.model_dump())


@router.get("")
async def list_units(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Unit 列表（分页）。

    Example:
        curl http://localhost:8000/api/v1/units?page=1&page_size=20
    """
    svc = UnitService(db)
    return await svc.get_units(page=page, page_size=page_size)


@router.get("/{unit_id}")
async def get_unit(unit_id: int, db: AsyncSession = Depends(get_db)):
    """Unit 详情。

    Example:
        curl http://localhost:8000/api/v1/units/1
    """
    svc = UnitService(db)
    return await svc.get_unit(unit_id)


@router.put("/{unit_id}")
async def update_unit(
    unit_id: int, body: UnitUpdate, db: AsyncSession = Depends(get_db)
):
    """更新 Unit。

    Example:
        curl -X PUT http://localhost:8000/api/v1/units/1 \\
             -H 'Content-Type: application/json' \\
             -d '{"title":"Unit 1 - Greetings"}'
    """
    svc = UnitService(db)
    return await svc.update_unit(unit_id, body.model_dump(exclude_unset=True))


@router.delete("/{unit_id}")
async def delete_unit(unit_id: int, db: AsyncSession = Depends(get_db)):
    """删除 Unit（级联删除关联单词）。

    Example:
        curl -X DELETE http://localhost:8000/api/v1/units/1
    """
    svc = UnitService(db)
    return await svc.delete_unit(unit_id)
