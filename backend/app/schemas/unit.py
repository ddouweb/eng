from pydantic import BaseModel, Field


class UnitCreate(BaseModel):
    title: str = Field(..., max_length=100)
    sequence: int = Field(..., ge=1)


class UnitUpdate(BaseModel):
    title: str | None = Field(None, max_length=100)
    sequence: int | None = Field(None, ge=1)
