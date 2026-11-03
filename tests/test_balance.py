import asyncio
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault(
    "ASTRBOT_ROOT",
    os.path.join(tempfile.gettempdir(), "astrbot_plugin_deepseek_balance_tests"),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp import web

import main

API_KEY = "sk-test-key-1234567890"
TOOL_DESCRIPTION = (
    "查询当前配置的 DeepSeek API 账户余额，返回账户余额信息，包括货币类型、"
    "总余额以及不同类型的余额明细。适用于用户询问 API 账户余额、可用额度或"
    "账户资金情况时。"
)
BALANCE_PAYLOAD = {
    "is_available": True,
    "balance_infos": [
        {
            "currency": "CNY",
            "total_balance": "110.00",
            "granted_balance": "10.00",
            "topped_up_balance": "100.00",
        }
    ],
}


class ToolRegistrationTest(unittest.TestCase):
    def test_tool_is_registered_without_parameters(self):
        from astrbot.core.provider.register import llm_tools

        tool = llm_tools.get_func("deepseek_balance_fetch")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "deepseek_balance_fetch")
        self.assertEqual(tool.description, TOOL_DESCRIPTION)
        self.assertEqual(tool.parameters, {"type": "object", "properties": {}})


class BalanceToolTest(unittest.IsolatedAsyncioTestCase):
    async def _start_server(self, handler, path="/user/balance"):
        app = web.Application()
        app.router.add_get(path, handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        self.addAsyncCleanup(runner.cleanup)
        port = runner.addresses[0][1]
        return f"http://127.0.0.1:{port}{path}"

    def _plugin(self, url, api_key=API_KEY):
        return main.DeepSeekBalancePlugin(
            context=None,
            config={"api_url": url, "api_key": api_key},
        )

    async def _call(self, url, api_key=API_KEY):
        result = await self._plugin(url, api_key).deepseek_balance_fetch(None)
        return result, json.loads(result)

    async def test_success_returns_raw_balance_data(self):
        async def handler(request):
            self.assertEqual(request.path, "/user/balance")
            self.assertEqual(request.headers["Authorization"], f"Bearer {API_KEY}")
            return web.json_response(BALANCE_PAYLOAD)

        url = await self._start_server(handler)
        text, result = await self._call(url)

        self.assertTrue(result["ok"])
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["data"], BALANCE_PAYLOAD)
        self.assertNotIn(API_KEY, text)

    async def test_available_false_and_empty_balance_is_still_valid(self):
        payload = {"is_available": False, "balance_infos": []}

        async def handler(request):
            return web.json_response(payload)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], payload)

    async def test_401_is_auth_error(self):
        payload = {"error": {"message": "Authentication Fails", "type": "auth"}}

        async def handler(request):
            return web.json_response(payload, status=401)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertEqual(result["error"]["http_status"], 401)
        self.assertEqual(result["error"]["response"], payload)

    async def test_403_is_auth_error(self):
        async def handler(request):
            return web.json_response({"error": "forbidden"}, status=403)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertEqual(result["error"]["http_status"], 403)

    async def test_404_is_endpoint_not_found(self):
        async def handler(request):
            return web.Response(status=404)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "endpoint_not_found")
        self.assertEqual(result["error"]["http_status"], 404)

    async def test_429_is_rate_limited(self):
        async def handler(request):
            return web.json_response({"error": "rate limit"}, status=429)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "rate_limited")

    async def test_5xx_is_server_error(self):
        async def handler(request):
            return web.Response(text="upstream failed", status=503)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "server_error")
        self.assertEqual(result["error"]["http_status"], 503)
        self.assertEqual(result["error"]["body_preview"], "upstream failed")

    async def test_other_http_status_is_http_error(self):
        async def handler(request):
            return web.Response(status=418)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "http_error")
        self.assertEqual(result["error"]["http_status"], 418)

    async def test_redirect_is_not_followed(self):
        async def handler(request):
            return web.Response(status=302, headers={"Location": "https://example.com"})

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "redirect_error")
        self.assertEqual(result["error"]["http_status"], 302)

    async def test_non_json_response_is_invalid_json(self):
        async def handler(request):
            return web.Response(text="<html>oops</html>", content_type="text/html")

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "invalid_json")
        self.assertEqual(result["error"]["http_status"], 200)
        self.assertIn("text/html", result["error"]["content_type"])
        self.assertEqual(result["error"]["body_preview"], "<html>oops</html>")

    async def test_empty_body_is_invalid_json(self):
        async def handler(request):
            return web.Response(text="", status=200)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "invalid_json")

    async def test_undecodable_body_is_invalid_json(self):
        async def handler(request):
            return web.Response(
                body=b"\xff\xfe\x00",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "invalid_json")

    async def test_missing_balance_fields_is_invalid_response(self):
        payload = {"is_available": True}

        async def handler(request):
            return web.json_response(payload)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "invalid_response")
        self.assertEqual(result["error"]["response"], payload)

    async def test_non_object_json_is_invalid_response(self):
        async def handler(request):
            return web.json_response([1, 2, 3])

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "invalid_response")

    async def test_json_business_error(self):
        payload = {"error": {"message": "invalid request", "type": "bad_request"}}

        async def handler(request):
            return web.json_response(payload)

        url = await self._start_server(handler)
        _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "business_error")
        self.assertEqual(result["error"]["response"], payload)

    async def test_timeout(self):
        async def handler(request):
            await asyncio.sleep(1)
            return web.json_response(BALANCE_PAYLOAD)

        url = await self._start_server(handler)
        with patch.object(main, "REQUEST_TIMEOUT_SECONDS", 0.2):
            _, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "timeout")

    async def test_connection_refused(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        _, result = await self._call(f"http://127.0.0.1:{port}/user/balance")

        self.assertEqual(result["error"]["type"], "connection_error")

    async def test_api_key_is_redacted_from_error_body(self):
        async def handler(request):
            return web.Response(
                text=f"bad key: {API_KEY}",
                status=401,
                content_type="text/plain",
            )

        url = await self._start_server(handler)
        text, result = await self._call(url)

        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertNotIn(API_KEY, text)
        self.assertIn("***", text)

    async def test_missing_api_url(self):
        plugin = main.DeepSeekBalancePlugin(
            context=None,
            config={"api_url": "", "api_key": API_KEY},
        )
        result = json.loads(await plugin.deepseek_balance_fetch(None))

        self.assertEqual(result["error"]["type"], "config_error")
        self.assertIn("API 地址", result["error"]["message"])

    async def test_missing_api_key(self):
        plugin = main.DeepSeekBalancePlugin(
            context=None,
            config={"api_url": "https://api.deepseek.com/user/balance", "api_key": " "},
        )
        result = json.loads(await plugin.deepseek_balance_fetch(None))

        self.assertEqual(result["error"]["type"], "config_error")
        self.assertIn("API Key", result["error"]["message"])

    async def test_url_without_scheme_is_config_error(self):
        plugin = main.DeepSeekBalancePlugin(
            context=None,
            config={"api_url": "api.deepseek.com/user/balance", "api_key": API_KEY},
        )
        result = json.loads(await plugin.deepseek_balance_fetch(None))

        self.assertEqual(result["error"]["type"], "config_error")
        self.assertIn("格式无效", result["error"]["message"])

    async def test_non_http_scheme_is_config_error(self):
        plugin = main.DeepSeekBalancePlugin(
            context=None,
            config={
                "api_url": "ftp://api.deepseek.com/user/balance",
                "api_key": API_KEY,
            },
        )
        result = json.loads(await plugin.deepseek_balance_fetch(None))

        self.assertEqual(result["error"]["type"], "config_error")


if __name__ == "__main__":
    unittest.main()
