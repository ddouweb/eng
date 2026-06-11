from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.base import DialogueResult, DialogueLine, ExerciseResult, ExerciseItem
from app.schemas.exceptions import AppException
from app.services.exercise_service import ExerciseService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def service(mock_session):
    return ExerciseService(mock_session)


@pytest.mark.asyncio
async def test_generate_dialogue_success(service, mock_session):
    mock_result = MagicMock()
    mock_result.all.return_value = [("hello",), ("world",)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    dialogue = DialogueResult(
        scenario="购物",
        lines=[
            DialogueLine(role="teacher", english="Hello!", chinese="你好！"),
            DialogueLine(role="student", english="Hi!", chinese="嗨！"),
        ],
    )
    with patch("app.services.exercise_service.get_ai_provider") as mock_provider:
        mock_provider.return_value.generate_dialogue = AsyncMock(return_value=dialogue)
        result = await service.generate_dialogue([1], "购物")

    assert result["code"] == 200
    assert result["data"]["scenario"] == "购物"
    assert len(result["data"]["lines"]) == 2


@pytest.mark.asyncio
async def test_generate_dialogue_no_words(service, mock_session):
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(AppException) as exc_info:
        await service.generate_dialogue([1], "购物")
    assert exc_info.value.code == 400


@pytest.mark.asyncio
async def test_generate_exercise_success(service, mock_session):
    mock_result = MagicMock()
    mock_result.all.return_value = [("hello",)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    exercise = ExerciseResult(
        mode="choice",
        items=[
            ExerciseItem(
                question="「你好」的英文是？",
                options=["hello", "goodbye", "sorry", "thanks"],
                answer="hello",
                explanation="hello 是打招呼用语",
            ),
        ],
    )
    with patch("app.services.exercise_service.get_ai_provider") as mock_provider:
        mock_provider.return_value.generate_exercise = AsyncMock(return_value=exercise)
        result = await service.generate_exercise([1], "choice")

    assert result["code"] == 200
    assert result["data"]["mode"] == "choice"
    assert len(result["data"]["items"]) == 1
    assert result["data"]["items"][0]["answer"] == "hello"
