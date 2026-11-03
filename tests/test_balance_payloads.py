from __future__ import annotations

from aiohttp import web
from balance_test_case import BalanceToolTestCase


class BalancePayloadTest(BalanceToolTestCase):
    async def test_non_json_response_is_invalid_json(self) -> None:
        async def handler(request):
            return web.Response(text="<html>oops</html>", content_type="text/html")

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "invalid_json")
        self.assertEqual(result["error"]["http_status"], 200)
        self.assertIn("text/html", result["error"]["content_type"])
        self.assertEqual(result["error"]["body_preview"], "<html>oops</html>")

    async def test_empty_body_is_invalid_json(self) -> None:
        async def handler(request):
            return web.Response(text="", status=200)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "invalid_json")

    async def test_undecodable_body_is_invalid_json(self) -> None:
        async def handler(request):
            return web.Response(
                body=b"\xff\xfe\x00",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "invalid_json")

    async def test_missing_balance_fields_is_invalid_response(self) -> None:
        payload = {"is_available": True}

        async def handler(request):
            return web.json_response(payload)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "invalid_response")
        self.assertEqual(result["error"]["response"], payload)

    async def test_non_object_json_is_invalid_response(self) -> None:
        async def handler(request):
            return web.json_response([1, 2, 3])

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "invalid_response")

    async def test_json_business_error(self) -> None:
        payload = {"error": {"message": "invalid request", "type": "bad_request"}}

        async def handler(request):
            return web.json_response(payload)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "business_error")
        self.assertEqual(result["error"]["response"], payload)
