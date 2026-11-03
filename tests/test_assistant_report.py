from __future__ import annotations

import copy
import json
import unittest

from assistant_report import AssistantReportParser
from e2e_error import E2EError

VALID_REPORT = {
    "saw_tool": True,
    "called_tool": True,
    "tool_succeeded": True,
    "is_available": True,
    "balance_infos": [
        {
            "currency": "CNY",
            "total_balance": "110.00",
            "granted_balance": "10.00",
            "topped_up_balance": "100.00",
        }
    ],
    "evaluation": "查询正常",
    "reason": "工具成功返回了余额信息",
}

ACTUAL_DATA = {
    "is_available": True,
    "balance_infos": copy.deepcopy(VALID_REPORT["balance_infos"]),
}


class AssistantReportParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = AssistantReportParser()

    def test_parses_last_json_object_from_prose_and_fence(self) -> None:
        reply = (
            '先看示例 {"saw_tool": false}\n'
            "最终结果：\n```json\n"
            f"{json.dumps(VALID_REPORT, ensure_ascii=False)}\n"
            "```"
        )

        report = self.parser.parse(reply)

        self.assertTrue(report.saw_tool)
        self.assertTrue(report.called_tool)
        self.assertTrue(report.tool_succeeded)
        self.assertEqual(report.balance_infos[0].currency, "CNY")
        self.assertEqual(report.evaluation, "查询正常")

    def test_cross_check_accepts_equivalent_amounts(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["balance_infos"][0]["total_balance"] = "110"

        report = self.parser.parse(json.dumps(payload))

        self.assertEqual(report.check_against(ACTUAL_DATA), [])

    def test_cross_check_reports_currency_mismatch(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["balance_infos"][0]["currency"] = "USD"

        problems = self.parser.parse(json.dumps(payload)).check_against(ACTUAL_DATA)

        self.assertTrue(any("币种集合不一致" in problem for problem in problems))

    def test_cross_check_reports_amount_mismatch(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["balance_infos"][0]["granted_balance"] = "11.00"

        problems = self.parser.parse(json.dumps(payload)).check_against(ACTUAL_DATA)

        self.assertTrue(any("granted_balance" in problem for problem in problems))

    def test_cross_check_reports_availability_mismatch(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["is_available"] = False

        problems = self.parser.parse(json.dumps(payload)).check_against(ACTUAL_DATA)

        self.assertTrue(any("is_available" in problem for problem in problems))

    def test_rejects_non_boolean_claim(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["saw_tool"] = "true"

        with self.assertRaises(E2EError):
            self.parser.parse(json.dumps(payload))

    def test_rejects_missing_evaluation(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["evaluation"] = ""

        with self.assertRaises(E2EError):
            self.parser.parse(json.dumps(payload))

    def test_rejects_invalid_amount(self) -> None:
        payload = copy.deepcopy(VALID_REPORT)
        payload["balance_infos"][0]["total_balance"] = "很多"

        with self.assertRaises(E2EError):
            self.parser.parse(json.dumps(payload))

    def test_rejects_reply_without_json(self) -> None:
        with self.assertRaises(E2EError):
            self.parser.parse("没有调用工具")
