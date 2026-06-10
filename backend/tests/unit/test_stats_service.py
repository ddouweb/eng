from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.stats_service import StatsService


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def service(mock_repo, monkeypatch):
    from app.repositories import stats_repo
    monkeypatch.setattr(stats_repo, "StatsRepo", lambda session: mock_repo)
    svc = StatsService(MagicMock())
    svc.repo = mock_repo
    return svc


class TestGetOverview:
    @pytest.mark.asyncio
    async def test_overview_with_data(self, service, mock_repo):
        mock_repo.get_mastery_distribution = AsyncMock(return_value={
            "unlearned": 50, "learning": 20, "familiar": 15, "permanent": 15,
        })
        mock_repo.get_total_word_count = AsyncMock(return_value=100)
        mock_repo.get_practice_summary = AsyncMock(return_value={
            "session_count": 10, "total_questions": 100, "total_correct": 80,
        })
        mock_repo.get_streak = AsyncMock(return_value=5)

        result = await service.get_overview(member_id=1)
        assert result["code"] == 200
        data = result["data"]
        assert data["total_words"] == 100
        assert data["mastered_count"] == 30
        assert data["mastery_rate"] == 30.0
        assert data["accuracy"] == 80.0
        assert data["streak_days"] == 5

    @pytest.mark.asyncio
    async def test_overview_no_data(self, service, mock_repo):
        mock_repo.get_mastery_distribution = AsyncMock(return_value={
            "unlearned": 0, "learning": 0, "familiar": 0, "permanent": 0,
        })
        mock_repo.get_total_word_count = AsyncMock(return_value=0)
        mock_repo.get_practice_summary = AsyncMock(return_value={
            "session_count": 0, "total_questions": 0, "total_correct": 0,
        })
        mock_repo.get_streak = AsyncMock(return_value=0)

        result = await service.get_overview(member_id=1)
        assert result["data"]["mastery_rate"] == 0.0
        assert result["data"]["accuracy"] == 0.0


class TestGetUnitStats:
    @pytest.mark.asyncio
    async def test_unit_stats(self, service, mock_repo):
        mock_repo.get_mastery_by_unit = AsyncMock(return_value={
            "unlearned": 5, "learning": 3, "familiar": 2, "permanent": 0,
        })
        mock_repo.get_total_word_count = AsyncMock(return_value=10)

        result = await service.get_unit_stats(member_id=1, unit_id=1)
        assert result["code"] == 200
        assert result["data"]["total_words"] == 10
        assert result["data"]["mastered_count"] == 2
        assert result["data"]["mastery_rate"] == 20.0


class TestGetTrend:
    @pytest.mark.asyncio
    async def test_trend(self, service, mock_repo):
        mock_repo.get_recent_practice_daily = AsyncMock(return_value=[
            {"date": "2026-06-09", "total": 20, "correct": 16},
            {"date": "2026-06-10", "total": 15, "correct": 12},
        ])

        result = await service.get_trend(member_id=1, days=7)
        assert result["code"] == 200
        assert result["data"]["days"] == 7
        assert len(result["data"]["daily"]) == 2
