from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: T | None = None


def success(data: Any = None, message: str = "success") -> dict:
    return ApiResponse(code=200, message=message, data=data).model_dump()


def error(code: int = 400, message: str = "error", data: Any = None) -> dict:
    return ApiResponse(code=code, message=message, data=data).model_dump()
