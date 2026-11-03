from __future__ import annotations

import logging
from typing import Any

from .balance_http_client import BalanceHttpClient, HttpTransportError
from .balance_response import BalanceResponseParser
from .http_errors import HttpErrorCatalog
from .secret_redactor import SecretRedactor
from .settings_reader import ConfigError, SettingsReader
from .tool_result import ToolResult


class BalanceService:
    def __init__(
        self,
        client: BalanceHttpClient,
        settings_reader: SettingsReader,
        logger: logging.Logger,
    ) -> None:
        self._client = client
        self._settings_reader = settings_reader
        self._logger = logger
        self._parser = BalanceResponseParser()

    async def fetch(self, config: Any) -> str:
        try:
            settings = self._settings_reader.read(config)
        except ConfigError as exc:
            return ToolResult.failure(
                "config_error",
                str(exc),
                redactor=SecretRedactor(exc.api_key),
            ).to_json()

        redactor = SecretRedactor(settings.api_key)
        try:
            response = await self._client.get(settings.api_url, settings.api_key)
        except HttpTransportError as exc:
            self._logger.warning("%s", exc.log_message)
            return ToolResult.failure(
                exc.error_type,
                exc.message,
                redactor=redactor,
            ).to_json()

        status = response.status
        data = self._parser.parse(response.body)

        if not 200 <= status < 300:
            detail = HttpErrorCatalog.describe(status)
            self._logger.warning(
                "DeepSeek balance query returned HTTP %s (%s)",
                status,
                detail.error_type,
            )
            return ToolResult.failure(
                detail.error_type,
                detail.message,
                redactor=redactor,
                http_status=status,
                response=data,
                content_type=None if data is not None else response.content_type,
                body_preview=(
                    None if data is not None else redactor.preview(response.body)
                ),
            ).to_json()

        if data is None:
            return ToolResult.failure(
                "invalid_json",
                f"API 返回的不是有效 JSON（HTTP {status}）。",
                redactor=redactor,
                http_status=status,
                content_type=response.content_type,
                body_preview=redactor.preview(response.body),
            ).to_json()

        if self._parser.has_business_error(data):
            return ToolResult.failure(
                "business_error",
                "API 返回业务错误。",
                redactor=redactor,
                http_status=status,
                response=data,
            ).to_json()

        if not self._parser.is_balance_payload(data):
            return ToolResult.failure(
                "invalid_response",
                "API 响应缺少 is_available 或 balance_infos 字段。",
                redactor=redactor,
                http_status=status,
                response=data,
            ).to_json()

        return ToolResult.success(
            http_status=status,
            data=data,
            redactor=redactor,
        ).to_json()
