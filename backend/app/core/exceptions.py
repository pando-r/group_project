from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在", *, code: str = "NOT_FOUND") -> None:
        super().__init__(code, message, status_code=404)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "请先登录") -> None:
        super().__init__("UNAUTHORIZED", message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "无权执行该操作") -> None:
        super().__init__("FORBIDDEN", message, status_code=403)


class ConflictError(AppError):
    def __init__(self, message: str, *, code: str = "CONFLICT") -> None:
        super().__init__(code, message, status_code=409)


class ValidationAppError(AppError):
    def __init__(self, message: str, *, data: Any = None) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code=422, data=data)


def _envelope(code: str, message: str, data: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
        "traceId": trace_id_ctx.get(),
    }


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for error in exc.errors():
            details.append(
                {
                    "field": ".".join(str(part) for part in error.get("loc", [])),
                    "message": error.get("msg", "请求参数不合法"),
                }
            )
        return JSONResponse(
            status_code=422,
            content=_envelope("VALIDATION_ERROR", "请求参数不合法", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "请求失败"
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(f"HTTP_{exc.status_code}", message),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "服务暂时不可用，请稍后重试"),
        )
