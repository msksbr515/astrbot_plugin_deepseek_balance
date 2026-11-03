from __future__ import annotations

import json
from types import ModuleType
from typing import Any

from balance_fixtures import API_KEY


class BalanceToolHarness:
    def __init__(self, plugin_module: ModuleType, api_key: str = API_KEY) -> None:
        self._plugin_module = plugin_module
        self.api_key = api_key

    def build_plugin(self, api_url: str, api_key: str | None = None):
        return self._plugin_module.DeepSeekBalancePlugin(
            context=None,
            config={
                "api_url": api_url,
                "api_key": self.api_key if api_key is None else api_key,
            },
        )

    async def call(
        self,
        api_url: str,
        api_key: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        text = await self.build_plugin(api_url, api_key).deepseek_balance_fetch(None)
        return text, json.loads(text)
