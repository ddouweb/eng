from pydantic import BaseModel, Field


class UnitCreate(BaseModel):
    title: str = Field(..., max_length=100)
    sequence: int = Field(..., ge=1)
    image_url: str | None = None


class UnitUpdate(BaseModel):
    title: str | None = Field(None, max_length=100)
    sequence: int | None = Field(None, ge=1)
    image_url: str | None = None
