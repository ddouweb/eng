from pydantic import BaseModel, Field


class OCRDraftWord(BaseModel):
    english: str = Field(..., max_length=500)
    chinese: str = Field(..., max_length=500)
    type: str = Field(default="word")


class OCRConfirmRequest(BaseModel):
    words: list[OCRDraftWord] = Field(..., min_length=1)
