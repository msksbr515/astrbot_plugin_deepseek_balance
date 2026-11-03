from __future__ import annotations

from aiohttp import web
from balance_fixtures import API_KEY, BALANCE_PAYLOAD
from balance_test_case import BalanceToolTestCase


class BalanceSuccessTest(BalanceToolTestCase):
    async def test_success_returns_raw_balance_data(self) -> None:
        async def handler(request):
            self.assertEqual(request.path, "/user/balance")
            self.assertEqual(request.headers["Authorization"], f"Bearer {API_KEY}")
            return web.json_response(BALANCE_PAYLOAD)

        url = await self.server.start(handler)
        text, result = await self.call_tool(url)

        self.assertTrue(result["ok"])
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["data"], BALANCE_PAYLOAD)
        self.assertNotIn(API_KEY, text)

    async def test_available_false_and_empty_balance_is_still_valid(self) -> None:
        payload = {"is_available": False, "balance_infos": []}

        async def handler(request):
            return web.json_response(payload)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], payload)
