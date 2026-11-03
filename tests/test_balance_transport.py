from __future__ import annotations

import asyncio
import socket
from unittest.mock import patch

from aiohttp import web
from balance_fixtures import BALANCE_PAYLOAD
from balance_test_case import BalanceToolTestCase
from plugin_loader import load_plugin_module

http_client = load_plugin_module("balance_http_client")


class BalanceTransportTest(BalanceToolTestCase):
    async def test_timeout(self) -> None:
        async def handler(request):
            await asyncio.sleep(1)
            return web.json_response(BALANCE_PAYLOAD)

        url = await self.server.start(handler)
        with patch.object(http_client, "REQUEST_TIMEOUT_SECONDS", 0.2):
            _, result = await self.call_tool(url)

        self.assertEqual(result["error"]["type"], "timeout")

    async def test_connection_refused(self) -> None:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        _, result = await self.call_tool(f"http://127.0.0.1:{port}/user/balance")

        self.assertEqual(result["error"]["type"], "connection_error")
