from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


def _envelope(code: int, message: str) -> dict:
    return {"code": code, "message": message, "data": None}


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """业务异常：统一走 {code,message,data} 信封。"""
    return JSONResponse(status_code=exc.code, content=_envelope(exc.code, exc.message))


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """兜底所有 HTTPException（含 deps.py 的 401、路由 404 等），统一信封。

    覆盖 Starlette 默认的 {"detail": ...} 响应，满足 CLAUDE.md 强制信封约定。
    """
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc.status_code, str(exc.detail)))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求体/参数校验失败（422）：把 detail 列表拼成可读消息，统一信封。"""
    msgs: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("body",))
        msg = err.get("msg", "")
        msgs.append(f"{loc}: {msg}" if loc else msg)
    message = "；".join(m for m in msgs if m) or "请求参数校验失败"
    return JSONResponse(status_code=422, content=_envelope(422, message))
