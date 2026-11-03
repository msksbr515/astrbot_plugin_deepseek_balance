from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.config import AstrBotConfig

REQUEST_TIMEOUT_SECONDS = 15
_BODY_PREVIEW_LIMIT = 300
_REDACT_MIN_LENGTH = 8


def _redact(text: str, api_key: str) -> str:
    if len(api_key) >= _REDACT_MIN_LENGTH and api_key in text:
        return text.replace(api_key, "***")
    return text


def _dump(payload: dict[str, Any], api_key: str) -> str:
    return _redact(
        json.dumps(payload, ensure_ascii=False, indent=2),
        api_key,
    )


def _failure(
    error_type: str,
    message: str,
    *,
    api_key: str,
    http_status: int | None = None,
    response: Any = None,
    content_type: str | None = None,
    body_preview: str | None = None,
) -> str:
    error: dict[str, Any] = {"type": error_type, "message": message}
    if http_status is not None:
        error["http_status"] = http_status
    if response is not None:
        error["response"] = response
    if content_type:
        error["content_type"] = content_type
    if body_preview is not None:
        error["body_preview"] = body_preview
    return _dump({"ok": False, "error": error}, api_key)


def _parse_json(body: str) -> Any:
    if not body.strip():
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _body_preview(body: str, api_key: str) -> str:
    text = body.strip()
    if len(text) > _BODY_PREVIEW_LIMIT:
        text = text[:_BODY_PREVIEW_LIMIT] + "..."
    return _redact(text, api_key)


def _describe_http_error(status: int) -> tuple[str, str]:
    if status in (401, 403):
        return (
            "auth_error",
            f"API 认证失败（HTTP {status}），请检查 API Key 是否正确以及是否有访问权限。",
        )
    if status == 404:
        return (
            "endpoint_not_found",
            "请求地址不存在（HTTP 404），请检查配置的 API 地址。",
        )
    if status == 429:
        return (
            "rate_limited",
            "请求过于频繁或超出配额（HTTP 429），请稍后重试。",
        )
    if 300 <= status < 400:
        return (
            "redirect_error",
            f"API 返回重定向（HTTP {status}），请将配置的 API 地址改为最终地址。",
        )
    if 500 <= status < 600:
        return (
            "server_error",
            f"API 服务端错误（HTTP {status}），请稍后重试。",
        )
    return "http_error", f"API 请求失败（HTTP {status}）。"


class DeepSeekBalancePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config

    @filter.llm_tool(name="deepseek_balance_fetch")
    async def deepseek_balance_fetch(self, event: AstrMessageEvent) -> str:
        """查询当前配置的 DeepSeek API 账户余额，返回账户余额信息，包括货币类型、总余额以及不同类型的余额明细。适用于用户询问 API 账户余额、可用额度或账户资金情况时。"""
        api_url, api_key, config_error = self._read_config()
        if config_error is not None:
            return config_error

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(
                    api_url,
                    headers=headers,
                    allow_redirects=False,
                ) as response,
            ):
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                body = await response.text(errors="replace")
        except TimeoutError:
            self.logger.warning("DeepSeek balance request timed out")
            return _failure(
                "timeout",
                f"请求超时（{REQUEST_TIMEOUT_SECONDS} 秒），请稍后重试。",
                api_key=api_key,
            )
        except aiohttp.ClientSSLError:
            self.logger.warning("DeepSeek balance request failed: TLS error")
            return _failure(
                "ssl_error",
                "TLS 证书校验失败，无法建立安全连接。",
                api_key=api_key,
            )
        except aiohttp.ClientConnectorDNSError:
            self.logger.warning("DeepSeek balance request failed: DNS error")
            return _failure(
                "dns_error",
                "DNS 解析失败，无法解析 API 地址中的域名。",
                api_key=api_key,
            )
        except aiohttp.ClientConnectorError:
            self.logger.warning("DeepSeek balance request failed: connection error")
            return _failure(
                "connection_error",
                "无法连接到 API 服务，请检查网络连接或 API 地址。",
                api_key=api_key,
            )
        except aiohttp.InvalidUrlClientError:
            self.logger.warning("DeepSeek balance request failed: invalid URL")
            return _failure(
                "invalid_url",
                "API 地址无效，无法发起请求。",
                api_key=api_key,
            )
        except aiohttp.ClientError as exc:
            self.logger.warning(
                "DeepSeek balance request failed: %s",
                type(exc).__name__,
            )
            return _failure(
                "network_error",
                f"网络请求失败（{type(exc).__name__}）。",
                api_key=api_key,
            )

        data = _parse_json(body)

        if not 200 <= status < 300:
            error_type, message = _describe_http_error(status)
            self.logger.warning(
                "DeepSeek balance query returned HTTP %s (%s)",
                status,
                error_type,
            )
            return _failure(
                error_type,
                message,
                api_key=api_key,
                http_status=status,
                response=data,
                content_type=content_type if data is None else None,
                body_preview=_body_preview(body, api_key) if data is None else None,
            )

        if data is None:
            return _failure(
                "invalid_json",
                f"API 返回的不是有效 JSON（HTTP {status}）。",
                api_key=api_key,
                http_status=status,
                content_type=content_type,
                body_preview=_body_preview(body, api_key),
            )

        if isinstance(data, dict) and data.get("error"):
            return _failure(
                "business_error",
                "API 返回业务错误。",
                api_key=api_key,
                http_status=status,
                response=data,
            )

        if (
            not isinstance(data, dict)
            or "is_available" not in data
            or not isinstance(data.get("balance_infos"), list)
        ):
            return _failure(
                "invalid_response",
                "API 响应缺少 is_available 或 balance_infos 字段。",
                api_key=api_key,
                http_status=status,
                response=data,
            )

        return _dump(
            {"ok": True, "http_status": status, "data": data},
            api_key,
        )

    def _read_config(self) -> tuple[str, str, str | None]:
        config = self.config or {}
        url_value = config.get("api_url")
        key_value = config.get("api_key")
        api_url = url_value.strip() if isinstance(url_value, str) else ""
        api_key = key_value.strip() if isinstance(key_value, str) else ""

        if not api_url:
            return (
                "",
                api_key,
                _failure(
                    "config_error",
                    "未配置 API 地址，请在插件配置中填写完整的 API URL。",
                    api_key=api_key,
                ),
            )
        if not api_key:
            return (
                api_url,
                "",
                _failure(
                    "config_error",
                    "未配置 API Key，请在插件配置中填写 DeepSeek API Key。",
                    api_key=api_key,
                ),
            )

        try:
            parts = urlsplit(api_url)
        except ValueError:
            parts = None
        if parts is None or parts.scheme not in {"http", "https"} or not parts.netloc:
            return (
                api_url,
                api_key,
                _failure(
                    "config_error",
                    "API 地址格式无效，必须是包含 http:// 或 https:// 的完整 URL。",
                    api_key=api_key,
                ),
            )

        return api_url, api_key, None
