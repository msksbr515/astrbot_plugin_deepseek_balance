from __future__ import annotations

import asyncio
import json
import secrets
import time
from typing import Any

import aiohttp
from e2e_config import CHAT_TIMEOUT_SECONDS, PLUGIN_NAME, PROMPT
from e2e_error import E2EError


class DashboardClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def login(self, password: str) -> str:
        timeout = aiohttp.ClientTimeout(total=15)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.post(
                f"{self._base_url}/api/v1/auth/login",
                json={"username": "astrbot", "password": password},
            ) as response,
        ):
            payload = await response.json(content_type=None)
            if response.status != 200 or payload.get("status") != "ok":
                raise E2EError(
                    f"dashboard login failed (HTTP {response.status}): "
                    f"{payload.get('message')}",
                )
            token = (payload.get("data") or {}).get("token")
            if not isinstance(token, str) or not token:
                raise E2EError("dashboard login returned no token")
            return token

    async def plugin_status(self, token: str) -> dict[str, Any] | None:
        timeout = aiohttp.ClientTimeout(total=15)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(
                f"{self._base_url}/api/plugin/get",
                headers={"Authorization": f"Bearer {token}"},
            ) as response,
        ):
            payload = await response.json(content_type=None)
        if payload.get("status") != "ok":
            raise E2EError(f"plugin list failed: {payload.get('message')}")
        data = payload.get("data")
        plugins = data if isinstance(data, list) else (data or {}).get("plugins", [])
        for plugin in plugins:
            if plugin.get("name") == PLUGIN_NAME:
                return plugin
        return None

    async def wait_for_plugin(self, token: str) -> dict[str, Any]:
        deadline = time.monotonic() + 60
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                plugin = await self.plugin_status(token)
                if plugin and plugin.get("activated"):
                    return plugin
            except (TimeoutError, aiohttp.ClientError, E2EError) as exc:
                last_error = exc
            await asyncio.sleep(1)
        detail = f" (last error: {last_error})" if last_error else ""
        raise E2EError(f"plugin {PLUGIN_NAME} was not activated{detail}")

    async def send_chat(self, token: str) -> tuple[str, list[dict[str, Any]]]:
        ws_url = f"{self._base_url}/api/v1/unified-chat/ws?token={token}"
        message_id = secrets.token_hex(8)
        session_id = f"e2e_{secrets.token_hex(4)}"
        texts: list[str] = []
        events: list[dict[str, Any]] = []
        timeout = aiohttp.ClientTimeout(total=CHAT_TIMEOUT_SECONDS + 30)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.ws_connect(ws_url, heartbeat=30) as ws,
        ):
            await ws.send_json(
                {
                    "ct": "chat",
                    "t": "send",
                    "message": [{"type": "plain", "text": PROMPT}],
                    "session_id": session_id,
                    "message_id": message_id,
                }
            )
            deadline = time.monotonic() + CHAT_TIMEOUT_SECONDS
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise E2EError(
                        f"no chat response within {CHAT_TIMEOUT_SECONDS}s",
                    )
                msg = await ws.receive(timeout=remaining)
                if msg.type != aiohttp.WSMsgType.TEXT:
                    raise E2EError(f"WebSocket closed unexpectedly: {msg.type}")
                payload = json.loads(msg.data)
                if payload.get("message_id") not in (None, message_id):
                    continue
                events.append(payload)
                if payload.get("t") == "error":
                    raise E2EError(
                        f"chat error: {payload.get('code')} {payload.get('data')}",
                    )
                if payload.get("type") == "plain" and payload.get("data"):
                    texts.append(str(payload["data"]))
                if payload.get("type") == "end":
                    return "".join(texts), events
