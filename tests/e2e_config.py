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
PROMPT = """请执行一次余额查询自检，并严格按以下要求回答：

1. 检查你当前可用的工具中是否存在 DeepSeek 余额查询工具。
2. 如果存在，必须调用它一次，查询当前账户余额。
3. 完成后只输出一个 JSON 对象，不要使用 Markdown 代码块，也不要输出 JSON 之外的任何文字。

JSON 必须包含以下字段：
{
  "saw_tool": true,
  "called_tool": true,
  "tool_succeeded": true,
  "is_available": true,
  "balance_infos": [
    {
      "currency": "CNY",
      "total_balance": "0.00",
      "granted_balance": "0.00",
      "topped_up_balance": "0.00"
    }
  ],
  "evaluation": "本次查询的简短评价",
  "reason": "给出该评价的原因"
}

字段要求：
- saw_tool：你的工具列表中是否出现了余额查询工具，必须为布尔值。
- called_tool：本次是否实际调用了该工具，必须为布尔值。
- tool_succeeded：工具是否返回成功，必须为布尔值。
- is_available：工具返回的 is_available，必须为布尔值。
- balance_infos：原样填写工具返回的每条余额明细；currency 使用 CNY、USD 等原始币种，金额保持字符串。
- evaluation：你对本次查询的简短评价。
- reason：评价原因。
示例中的值仅表示格式，必须替换为工具的真实返回值。"""
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
