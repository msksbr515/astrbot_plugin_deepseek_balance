from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit


class ConfigError(Exception):
    def __init__(self, message: str, api_key: str = "") -> None:
        super().__init__(message)
        self.api_key = api_key


class PluginSettings:
    __slots__ = ("api_key", "api_url")

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url
        self.api_key = api_key


class SettingsReader:
    def read(self, config: Any) -> PluginSettings:
        values = config or {}
        url_value = values.get("api_url")
        key_value = values.get("api_key")
        api_url = url_value.strip() if isinstance(url_value, str) else ""
        api_key = key_value.strip() if isinstance(key_value, str) else ""

        if not api_url:
            raise ConfigError(
                "未配置 API 地址，请在插件配置中填写完整的 API URL。",
                api_key,
            )
        if not api_key:
            raise ConfigError(
                "未配置 API Key，请在插件配置中填写 DeepSeek API Key。",
                api_key,
            )

        try:
            parts = urlsplit(api_url)
        except ValueError:
            parts = None
        if parts is None or parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ConfigError(
                "API 地址格式无效，必须是包含 http:// 或 https:// 的完整 URL。",
                api_key,
            )

        return PluginSettings(api_url, api_key)
