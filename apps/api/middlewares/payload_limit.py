"""Limite de tamanho de payload (anti buffer overflow / DoS por corpo gigante)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB (payloads JSON; uploads de imagem usam URL)


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > MAX_CONTENT_LENGTH:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "Corpo da requisicao excede o limite de 2 MB.",
                        }
                    },
                )
        return await call_next(request)
