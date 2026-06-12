from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.schemas.common import success
from app.services.auth_service import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    """登录认证，返回 JWT token。

    Example:
        curl -X POST http://localhost:8000/api/v1/auth/login \\
             -H 'Content-Type: application/json' \\
             -d '{"username":"admin","password":"admin123"}'
    """
    if body.username != settings.AUTH_USERNAME or not verify_password(body.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(subject=body.username)
    return success(data={"token": token, "token_type": "bearer"})
