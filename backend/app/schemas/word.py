from pydantic import BaseModel, Field

from app.models.enums import TagType, WordType


class WordCreate(BaseModel):
    english: str = Field(..., max_length=500)
    chinese: str = Field(..., max_length=500)
    type: WordType = WordType.word


class WordBatchCreate(BaseModel):
    words: list[WordCreate] = Field(..., min_length=1)


class WordUpdate(BaseModel):
    english: str | None = Field(None, max_length=500)
    chinese: str | None = Field(None, max_length=500)
    type: WordType | None = None


class TagOperation(BaseModel):
    tags: list[TagType] = Field(..., min_length=1)
