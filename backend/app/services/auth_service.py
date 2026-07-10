import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# 注意：本项目曾用 passlib CryptContext，但 passlib 1.7.x 与 bcrypt 4.x 存在兼容性问题
# （hash/verify 会抛 "password cannot be longer than 72 bytes" 等错误），
# 故直接使用 bcrypt 模块，更轻量且稳定。
_BCRYPT_MAX_BYTES = 72  # bcrypt 只取口令前 72 字节，超出部分本就忽略；显式截断避免 4.x 报错


def hash_password(plain: str) -> str:
    """生成口令的 bcrypt 哈希（用于首次配置 .env）。"""
    return bcrypt.hashpw(plain.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str) -> bool:
    """校验口令。

    AUTH_PASSWORD 推荐存 bcrypt 哈希（以 $2 开头），此时走恒定时间的 bcrypt 校验；
    为平滑迁移，若配置的仍是明文，则用恒定时间字符串比较（hmac.compare_digest）兜底。
    """
    stored = settings.AUTH_PASSWORD
    if not stored:
        return False
    if stored.startswith("$2"):  # bcrypt 哈希特征（$2a/$2b/$2y）
        try:
            return bcrypt.checkpw(
                plain.encode("utf-8")[:_BCRYPT_MAX_BYTES],
                stored.encode("utf-8"),
            )
        except ValueError:
            return False
    # 明文兜底（旧部署迁移期，不推荐长期使用）
    return hmac.compare_digest(plain, stored)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
