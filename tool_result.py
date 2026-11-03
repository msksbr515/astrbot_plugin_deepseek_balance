from __future__ import annotations

from typing import Any

from .secret_redactor import SecretRedactor


class ToolResult:
    def __init__(self, payload: dict[str, Any], redactor: SecretRedactor) -> None:
        self._payload = payload
        self._redactor = redactor

    @classmethod
    def success(
        cls,
        *,
        http_status: int,
        data: Any,
        redactor: SecretRedactor,
    ) -> ToolResult:
        return cls(
            {"ok": True, "http_status": http_status, "data": data},
            redactor,
        )

    @classmethod
    def failure(
        cls,
        error_type: str,
        message: str,
        *,
        redactor: SecretRedactor,
        http_status: int | None = None,
        response: Any = None,
        content_type: str | None = None,
        body_preview: str | None = None,
    ) -> ToolResult:
        error: dict[str, Any] = {"type": error_type, "message": message}
        if http_status is not None:
            error["http_status"] = http_status
        if response is not None:
            error["response"] = response
        if content_type:
            error["content_type"] = content_type
        if body_preview is not None:
            error["body_preview"] = body_preview
        return cls({"ok": False, "error": error}, redactor)

    def to_json(self) -> str:
        return self._redactor.dump(self._payload)
