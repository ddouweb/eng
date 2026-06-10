from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.unit_service import UnitService


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def service(mock_session):
    return UnitService(mock_session)


@pytest.mark.asyncio
async def test_create_unit_success(service, mock_session):
    service.repo.get_by_sequence = AsyncMock(return_value=None)
    service.repo.create = AsyncMock()
    service.repo.create.return_value = MagicMock(
        id=1, title="Unit 1", sequence=1, image_url=None,
        created_at=None, updated_at=None,
    )
    result = await service.create_unit({"title": "Unit 1", "sequence": 1})
    assert result["code"] == 200
    assert result["data"]["title"] == "Unit 1"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_unit_duplicate_sequence(service):
    service.repo.get_by_sequence = AsyncMock(return_value=MagicMock())
    result = await service.create_unit({"title": "Unit 1", "sequence": 1})
    assert result["code"] == 409


@pytest.mark.asyncio
async def test_get_unit_not_found(service):
    service.repo.get_by_id = AsyncMock(return_value=None)
    result = await service.get_unit(999)
    assert result["code"] == 404


@pytest.mark.asyncio
async def test_delete_unit_success(service, mock_session):
    service.repo.get_by_id = AsyncMock(return_value=MagicMock(id=1))
    service.repo.delete = AsyncMock()
    result = await service.delete_unit(1)
    assert result["code"] == 200
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_unit_success(service, mock_session):
    unit = MagicMock(id=1, title="Unit 1", sequence=1, image_url=None,
                     created_at=None, updated_at=None)
    service.repo.get_by_id = AsyncMock(return_value=unit)
    service.repo.get_by_sequence = AsyncMock(return_value=None)
    service.repo.update = AsyncMock(return_value=unit)
    result = await service.update_unit(1, {"title": "Unit 1 - Updated"})
    assert result["code"] == 200
    mock_session.commit.assert_awaited_once()
