from sqlalchemy.ext.asyncio import AsyncSession

from app.models.unit import Unit
from app.repositories.unit_repo import UnitRepo
from app.schemas.common import error, success
from app.schemas.exceptions import AppException


class UnitService:
    def __init__(self, session: AsyncSession):
        self.repo = UnitRepo(session)
        self.session = session

    async def create_unit(self, data: dict) -> dict:
        existing = await self.repo.get_by_sequence(data["sequence"])
        if existing:
            raise AppException(409, f"Unit sequence {data['sequence']} already exists")
        unit = Unit(**data)
        unit = await self.repo.create(unit)
        await self.session.commit()
        return success(data=self._to_dict(unit, word_count=0))

    async def get_units(self, page: int = 1, page_size: int = 20) -> dict:
        rows, total = await self.repo.get_with_word_counts(page=page, page_size=page_size)
        items = [self._to_dict(unit, word_count=wc) for unit, wc in rows]
        return success(data={"items": items, "total": total, "page": page, "page_size": page_size})

    async def get_unit(self, unit_id: int) -> dict:
        unit = await self.repo.get_by_id(unit_id)
        if not unit:
            raise AppException(404, "Unit not found")
        return success(data=self._to_dict(unit))

    async def update_unit(self, unit_id: int, data: dict) -> dict:
        unit = await self.repo.get_by_id(unit_id)
        if not unit:
            raise AppException(404, "Unit not found")
        if "sequence" in data and data["sequence"] != unit.sequence:
            existing = await self.repo.get_by_sequence(data["sequence"])
            if existing:
                raise AppException(409, f"Unit sequence {data['sequence']} already exists")
        unit = await self.repo.update(unit, data)
        await self.session.commit()
        return success(data=self._to_dict(unit))

    async def delete_unit(self, unit_id: int) -> dict:
        unit = await self.repo.get_by_id(unit_id)
        if not unit:
            raise AppException(404, "Unit not found")
        await self.repo.delete(unit)
        await self.session.commit()
        return success(message="Unit deleted")

    def _to_dict(self, unit: Unit, **extra) -> dict:
        d = {
            "id": unit.id,
            "title": unit.title,
            "sequence": unit.sequence,
            "created_at": unit.created_at.isoformat() if unit.created_at else None,
            "updated_at": unit.updated_at.isoformat() if unit.updated_at else None,
        }
        d.update(extra)
        return d
