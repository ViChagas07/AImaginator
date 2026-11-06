"""Limite de tamanho de payload (anti buffer overflow / DoS por corpo gigante)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from infra.settings import get_settings

MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB (payloads JSON; uploads usam URL)
_EDIT_UPLOAD_PATH = "/api/v1/generations/edits/upload"
_MULTIPART_OVERHEAD = 1024 * 1024


class PayloadLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        max_length = MAX_CONTENT_LENGTH
        if request.url.path == _EDIT_UPLOAD_PATH:
            settings = get_settings()
            max_length = settings.edit_upload_max_bytes + _MULTIPART_OVERHEAD

        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > max_length:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "Corpo da requisicao excede o limite configurado.",
                        }
                    },
                )
        return await call_next(request)
