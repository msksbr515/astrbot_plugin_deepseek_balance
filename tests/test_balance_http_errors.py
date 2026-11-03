from __future__ import annotations

from aiohttp import web
from balance_fixtures import API_KEY
from balance_test_case import BalanceToolTestCase


class BalanceHttpErrorTest(BalanceToolTestCase):
    async def test_401_is_auth_error(self) -> None:
        payload = {"error": {"message": "Authentication Fails", "type": "auth"}}

        async def handler(request):
            return web.json_response(payload, status=401)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertEqual(result["error"]["http_status"], 401)
        self.assertEqual(result["error"]["response"], payload)

    async def test_403_is_auth_error(self) -> None:
        async def handler(request):
            return web.json_response({"error": "forbidden"}, status=403)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertEqual(result["error"]["http_status"], 403)

    async def test_404_is_endpoint_not_found(self) -> None:
        async def handler(request):
            return web.Response(status=404)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "endpoint_not_found")
        self.assertEqual(result["error"]["http_status"], 404)

    async def test_429_is_rate_limited(self) -> None:
        async def handler(request):
            return web.json_response({"error": "rate limit"}, status=429)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "rate_limited")

    async def test_5xx_is_server_error(self) -> None:
        async def handler(request):
            return web.Response(text="upstream failed", status=503)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "server_error")
        self.assertEqual(result["error"]["http_status"], 503)
        self.assertEqual(result["error"]["body_preview"], "upstream failed")

    async def test_other_http_status_is_http_error(self) -> None:
        async def handler(request):
            return web.Response(status=418)

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "http_error")
        self.assertEqual(result["error"]["http_status"], 418)

    async def test_redirect_is_not_followed(self) -> None:
        async def handler(request):
            return web.Response(status=302, headers={"Location": "https://example.com"})

        url = await self.server.start(handler)
        _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "redirect_error")
        self.assertEqual(result["error"]["http_status"], 302)

    async def test_api_key_is_redacted_from_error_body(self) -> None:
        async def handler(request):
            return web.Response(
                text=f"bad key: {API_KEY}",
                status=401,
                content_type="text/plain",
            )

        url = await self.server.start(handler)
        text, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertNotIn(API_KEY, text)
        self.assertIn("***", text)
