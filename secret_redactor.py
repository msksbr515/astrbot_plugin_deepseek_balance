from __future__ import annotations

import json
from typing import Any

BODY_PREVIEW_LIMIT = 300
_MIN_SECRET_LENGTH = 8


class SecretRedactor:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def redact(self, text: str) -> str:
        if len(self._secret) >= _MIN_SECRET_LENGTH and self._secret in text:
            return text.replace(self._secret, "***")
        return text

    def dump(self, payload: dict[str, Any]) -> str:
        return self.redact(json.dumps(payload, ensure_ascii=False, indent=2))

    def preview(self, body: str, limit: int = BODY_PREVIEW_LIMIT) -> str:
        text = body.strip()
        if len(text) > limit:
            text = text[:limit] + "..."
        return self.redact(text)
