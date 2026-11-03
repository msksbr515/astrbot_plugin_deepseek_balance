from __future__ import annotations

from balance_test_case import BalanceToolTestCase


class BalanceConfigTest(BalanceToolTestCase):
    async def test_missing_api_url(self) -> None:
        _, result = await self.call_tool("")

        self.assertEqual(result["error"]["type"], "config_error")
        self.assertIn("API 地址", result["error"]["message"])

    async def test_missing_api_key(self) -> None:
        _, result = await self.call_tool(
            "https://api.deepseek.com/user/balance",
            api_key=" ",
        )

        self.assertEqual(result["error"]["type"], "config_error")
        self.assertIn("API Key", result["error"]["message"])

    async def test_url_without_scheme_is_config_error(self) -> None:
        _, result = await self.call_tool("api.deepseek.com/user/balance")

        self.assertEqual(result["error"]["type"], "config_error")
        self.assertIn("格式无效", result["error"]["message"])

    async def test_non_http_scheme_is_config_error(self) -> None:
        _, result = await self.call_tool("ftp://api.deepseek.com/user/balance")

        self.assertEqual(result["error"]["type"], "config_error")
