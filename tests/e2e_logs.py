from __future__ import annotations

import json
import re
from typing import Any

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9]{8,}")
_BALANCE_FIELDS = (
    "balance_infos",
    "total_balance",
    "granted_balance",
    "topped_up_balance",
)


class LogRedactor:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def redact(self, text: str) -> str:
        if self._api_key:
            text = text.replace(self._api_key, "***")
        return _SECRET_PATTERN.sub("sk-***", text)

    def failure_report(self, log_text: str, limit: int = 40) -> str:
        lines = log_text.splitlines()[-limit:]
        return "\n".join(
            self.redact(line)
            for line in lines
            if not any(field in line for field in _BALANCE_FIELDS)
        )


class ToolResultExtractor:
    def __init__(self, tool_name: str) -> None:
        self._marker = f"Tool `{tool_name}` Result: "

    def extract(self, log_text: str) -> dict[str, Any] | None:
        index = log_text.rfind(self._marker)
        if index < 0:
            return None
        start = log_text.find("{", index + len(self._marker))
        if start < 0:
            return None
        return self._json_object_at(log_text, start)

    @staticmethod
    def _json_object_at(text: str, start: int) -> dict[str, Any] | None:
        depth = 0
        in_string = False
        escaped = False
        for pos in range(start, len(text)):
            char = text[pos]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : pos + 1])
                    except json.JSONDecodeError:
                        return None
        return None
