from fastapi import APIRouter

from app.schemas.common import success

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    """Health check endpoint.

    Example:
        curl http://localhost:8000/api/v1/health
    """
    return success(data={"status": "ok"})
