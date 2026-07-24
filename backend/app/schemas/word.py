from pydantic import BaseModel, Field

from app.models.enums import TagType, WordType


class WordCreate(BaseModel):
    english: str = Field(..., max_length=500)
    chinese: str = Field(..., max_length=500)
    type: WordType = WordType.word
    seq: int | None = None
    # 富字段：可选。AI 解析 / ECDICT 导入 / 手动补录均可提供。
    phonetic: str | None = Field(None, max_length=200)
    definition: str | None = Field(None, max_length=1000)
    pos: str | None = Field(None, max_length=100)
    example: str | None = None


class WordBatchCreate(BaseModel):
    words: list[WordCreate] = Field(..., min_length=1)


class WordUpdate(BaseModel):
    english: str | None = Field(None, max_length=500)
    chinese: str | None = Field(None, max_length=500)
    type: WordType | None = None
    seq: int | None = None
    phonetic: str | None = Field(None, max_length=200)
    definition: str | None = Field(None, max_length=1000)
    pos: str | None = Field(None, max_length=100)
    example: str | None = None


class TagOperation(BaseModel):
    tags: list[TagType] = Field(..., min_length=1)
