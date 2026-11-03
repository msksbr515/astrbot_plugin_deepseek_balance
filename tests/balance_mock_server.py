from __future__ import annotations

import unittest
from collections.abc import Awaitable, Callable

from aiohttp import web

RequestHandler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class BalanceMockServer:
    def __init__(self, test_case: unittest.IsolatedAsyncioTestCase) -> None:
        self._test_case = test_case

    async def start(
        self,
        handler: RequestHandler,
        path: str = "/user/balance",
    ) -> str:
        app = web.Application()
        app.router.add_get(path, handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        self._test_case.addAsyncCleanup(runner.cleanup)
        port = runner.addresses[0][1]
        return f"http://127.0.0.1:{port}{path}"
