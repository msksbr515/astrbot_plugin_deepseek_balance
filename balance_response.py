from __future__ import annotations

import json
from typing import Any


class BalanceResponseParser:
    @staticmethod
    def parse(body: str) -> Any:
        if not body.strip():
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def has_business_error(data: Any) -> bool:
        return isinstance(data, dict) and bool(data.get("error"))

    @staticmethod
    def is_balance_payload(data: Any) -> bool:
        return (
            isinstance(data, dict)
            and "is_available" in data
            and isinstance(data.get("balance_infos"), list)
        )
