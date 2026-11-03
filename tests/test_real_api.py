from __future__ import annotations

import json
import os
import unittest

from env_file import EnvFile
from plugin_loader import REPO_ROOT, load_plugin_module

main = load_plugin_module("main")


class RealBalanceApiTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        EnvFile(REPO_ROOT / ".env").load()
        cls.api_key = os.environ.get("DEEPSEEK_TEST_API_KEY", "").strip()
        cls.api_url = os.environ.get(
            "DEEPSEEK_TEST_API_URL",
            "https://api.deepseek.com/user/balance",
        ).strip()

    def setUp(self) -> None:
        if not self.api_key:
            self.skipTest(
                "DEEPSEEK_TEST_API_KEY is not set; create .env from .env.example",
            )

    def _plugin(self, api_key: str) -> main.DeepSeekBalancePlugin:
        return main.DeepSeekBalancePlugin(
            context=None,
            config={"api_url": self.api_url, "api_key": api_key},
        )

    async def test_real_balance_query(self) -> None:
        text = await self._plugin(self.api_key).deepseek_balance_fetch(None)

        self.assertNotIn(self.api_key, text)
        result = json.loads(text)
        self.assertTrue(
            result.get("ok"),
            f"real balance query failed: {result.get('error')}",
        )
        data = result["data"]
        self.assertIn("is_available", data)
        self.assertIsInstance(data["balance_infos"], list)

    async def test_real_invalid_key_is_auth_error(self) -> None:
        text = await self._plugin(
            "sk-invalid-key-for-testing",
        ).deepseek_balance_fetch(None)
        result = json.loads(text)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "auth_error")
        self.assertEqual(result["error"]["http_status"], 401)
