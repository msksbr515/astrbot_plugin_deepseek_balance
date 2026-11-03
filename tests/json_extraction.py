from __future__ import annotations

import json
from typing import Any


class JsonObjectExtractor:
    def __init__(self) -> None:
        self._decoder = json.JSONDecoder()

    def first_object(self, text: str, start: int = 0) -> dict[str, Any] | None:
        index = text.find("{", start)
        while index >= 0:
            try:
                value, _ = self._decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                index = text.find("{", index + 1)
                continue
            if isinstance(value, dict):
                return value
            index = text.find("{", index + 1)
        return None

    def last_object(self, text: str) -> dict[str, Any] | None:
        result = None
        index = text.find("{")
        while index >= 0:
            try:
                value, end = self._decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                index = text.find("{", index + 1)
                continue
            if isinstance(value, dict):
                result = value
            index = text.find("{", end)
        return result
