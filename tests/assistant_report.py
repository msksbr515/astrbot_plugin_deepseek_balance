from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from e2e_error import E2EError
from json_extraction import JsonObjectExtractor

_AMOUNT_FIELDS = ("total_balance", "granted_balance", "topped_up_balance")


@dataclass(frozen=True)
class BalanceInfo:
    currency: str
    total_balance: str
    granted_balance: str
    topped_up_balance: str

    @classmethod
    def from_payload(cls, payload: Any) -> BalanceInfo:
        if not isinstance(payload, dict):
            raise E2EError("余额明细必须是 JSON 对象")
        currency = payload.get("currency")
        if not isinstance(currency, str) or not currency.strip():
            raise E2EError("余额明细缺少有效的 currency")
        return cls(
            currency=currency.strip().upper(),
            total_balance=_amount(payload, "total_balance"),
            granted_balance=_amount(payload, "granted_balance"),
            topped_up_balance=_amount(payload, "topped_up_balance"),
        )


@dataclass(frozen=True)
class AssistantReport:
    saw_tool: bool
    called_tool: bool
    tool_succeeded: bool
    is_available: bool
    balance_infos: tuple[BalanceInfo, ...]
    evaluation: str
    reason: str

    def check_against(self, actual_data: dict[str, Any]) -> list[str]:
        problems: list[str] = []
        actual_available = actual_data.get("is_available")
        if not isinstance(actual_available, bool):
            raise E2EError("真实工具结果缺少布尔型 is_available")
        if self.is_available != actual_available:
            problems.append(
                f"is_available 不一致：报告={self.is_available} "
                f"实际={actual_available}",
            )

        actual_payloads = actual_data.get("balance_infos")
        if not isinstance(actual_payloads, list):
            raise E2EError("真实工具结果缺少 balance_infos 列表")
        actual_infos = [BalanceInfo.from_payload(item) for item in actual_payloads]

        reported = {info.currency: info for info in self.balance_infos}
        actual = {info.currency: info for info in actual_infos}
        if len(reported) != len(self.balance_infos):
            problems.append("报告中的 balance_infos 存在重复币种")
        if set(reported) != set(actual):
            problems.append(
                f"币种集合不一致：报告={sorted(reported)} 实际={sorted(actual)}",
            )

        for currency in sorted(set(reported) & set(actual)):
            for field in _AMOUNT_FIELDS:
                reported_value = getattr(reported[currency], field)
                actual_value = getattr(actual[currency], field)
                if not _amounts_equal(reported_value, actual_value):
                    problems.append(
                        f"{currency}.{field} 不一致：报告={reported_value} "
                        f"实际={actual_value}",
                    )
        return problems


class AssistantReportParser:
    def __init__(self) -> None:
        self._json = JsonObjectExtractor()

    def parse(self, reply: str) -> AssistantReport:
        payload = self._json.last_object(reply)
        if payload is None:
            raise E2EError("助手回复中没有可解析的 JSON 对象")
        infos = payload.get("balance_infos")
        if not isinstance(infos, list) or not infos:
            raise E2EError("助手 JSON 的 balance_infos 必须是非空列表")
        return AssistantReport(
            saw_tool=_boolean(payload, "saw_tool"),
            called_tool=_boolean(payload, "called_tool"),
            tool_succeeded=_boolean(payload, "tool_succeeded"),
            is_available=_boolean(payload, "is_available"),
            balance_infos=tuple(BalanceInfo.from_payload(item) for item in infos),
            evaluation=_text(payload, "evaluation"),
            reason=_text(payload, "reason"),
        )


def _amount(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise E2EError(f"余额明细缺少有效的 {field}")
    text = str(value).strip()
    try:
        Decimal(text)
    except InvalidOperation:
        raise E2EError(f"余额明细字段 {field} 不是有效金额: {text!r}") from None
    return text


def _amounts_equal(left: str, right: str) -> bool:
    try:
        return Decimal(left) == Decimal(right)
    except InvalidOperation:
        return left == right


def _boolean(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise E2EError(f"助手 JSON 字段 {field} 必须是布尔值")
    return value


def _text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise E2EError(f"助手 JSON 字段 {field} 必须是非空字符串")
    return value.strip()
