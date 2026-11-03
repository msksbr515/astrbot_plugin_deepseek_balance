from __future__ import annotations

import unittest
from typing import Any

from balance_fixtures import API_KEY
from balance_mock_server import BalanceMockServer
from plugin_loader import load_plugin_module
from tool_harness import BalanceToolHarness

main = load_plugin_module("main")


class BalanceToolTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.server = BalanceMockServer(self)
        self.harness = BalanceToolHarness(main, API_KEY)

    async def call_tool(
        self,
        api_url: str,
        api_key: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        return await self.harness.call(api_url, api_key)
