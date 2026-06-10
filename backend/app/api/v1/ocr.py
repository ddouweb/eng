from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ocr import OCRConfirmRequest
from app.services.ocr_service import OCRService

router = APIRouter(prefix="/units", tags=["ocr"])


@router.post("/{unit_id}/upload-image")
async def upload_image(
    unit_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """上传教材图片并 OCR 解析。

    Example:
        curl -X POST http://localhost:8000/api/v1/units/1/upload-image \\
             -F "file=@textbook_page.jpg"
    """
    image_bytes = await file.read()
    svc = OCRService(db)
    return await svc.upload_and_parse(unit_id, image_bytes, file.filename or "image.png")


@router.get("/{unit_id}/ocr-result")
async def get_ocr_result(unit_id: int, db: AsyncSession = Depends(get_db)):
    """获取 OCR 草稿结果。

    Example:
        curl http://localhost:8000/api/v1/units/1/ocr-result
    """
    svc = OCRService(db)
    return await svc.get_ocr_result(unit_id)


@router.post("/{unit_id}/confirm-ocr")
async def confirm_ocr(
    unit_id: int, body: OCRConfirmRequest, db: AsyncSession = Depends(get_db)
):
    """确认 OCR 结果，写入单词表。

    Example:
        curl -X POST http://localhost:8000/api/v1/units/1/confirm-ocr \\
             -H 'Content-Type: application/json' \\
             -d '{"words":[{"english":"hello","chinese":"你好","type":"word"}]}'
    """
    svc = OCRService(db)
    return await svc.confirm_ocr(unit_id, [w.model_dump() for w in body.words])
