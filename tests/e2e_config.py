from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from e2e_error import E2EError
from env_file import EnvFile

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "astrbot_plugin_deepseek_balance"
TOOL_NAME = "deepseek_balance_fetch"
PROMPT = "查余额"
CHAT_PROVIDER_ID = "deepseek-e2e"
CHAT_API_BASE = "https://api.deepseek.com/v1"
CHAT_MODEL = "deepseek-chat"
STARTUP_TIMEOUT_SECONDS = 180
CHAT_TIMEOUT_SECONDS = 180
DEFAULT_API_URL = "https://api.deepseek.com/user/balance"


@dataclass(frozen=True)
class TestCredentials:
    api_key: str
    api_url: str

    @classmethod
    def from_env(cls, env_path: Path) -> TestCredentials:
        EnvFile(env_path).load()
        api_key = os.environ.get("DEEPSEEK_TEST_API_KEY", "").strip()
        api_url = os.environ.get(
            "DEEPSEEK_TEST_API_URL",
            DEFAULT_API_URL,
        ).strip()
        if not api_key:
            raise E2EError(
                "DEEPSEEK_TEST_API_KEY is not set; create .env from .env.example",
            )
        parts = urlsplit(api_url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise E2EError("DEEPSEEK_TEST_API_URL must be a full http(s) URL")
        return cls(api_key=api_key, api_url=api_url)
