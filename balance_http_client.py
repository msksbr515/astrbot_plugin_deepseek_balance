from __future__ import annotations

from dataclasses import dataclass

import aiohttp

REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class HttpResponse:
    status: int
    content_type: str
    body: str


class HttpTransportError(Exception):
    def __init__(self, error_type: str, message: str, log_message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.log_message = log_message


class BalanceHttpClient:
    def __init__(self, timeout_seconds: float | None = None) -> None:
        self._timeout_seconds = (
            REQUEST_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        )

    async def get(self, url: str, api_key: str) -> HttpResponse:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(url, headers=headers, allow_redirects=False) as response,
            ):
                return HttpResponse(
                    status=response.status,
                    content_type=response.headers.get("Content-Type", ""),
                    body=await response.text(errors="replace"),
                )
        except TimeoutError:
            raise HttpTransportError(
                "timeout",
                f"请求超时（{self._timeout_seconds} 秒），请稍后重试。",
                "DeepSeek balance request timed out",
            ) from None
        except aiohttp.ClientSSLError:
            raise HttpTransportError(
                "ssl_error",
                "TLS 证书校验失败，无法建立安全连接。",
                "DeepSeek balance request failed: TLS error",
            ) from None
        except aiohttp.ClientConnectorDNSError:
            raise HttpTransportError(
                "dns_error",
                "DNS 解析失败，无法解析 API 地址中的域名。",
                "DeepSeek balance request failed: DNS error",
            ) from None
        except aiohttp.ClientConnectorError:
            raise HttpTransportError(
                "connection_error",
                "无法连接到 API 服务，请检查网络连接或 API 地址。",
                "DeepSeek balance request failed: connection error",
            ) from None
        except aiohttp.InvalidUrlClientError:
            raise HttpTransportError(
                "invalid_url",
                "API 地址无效，无法发起请求。",
                "DeepSeek balance request failed: invalid URL",
            ) from None
        except aiohttp.ClientError as exc:
            raise HttpTransportError(
                "network_error",
                f"网络请求失败（{type(exc).__name__}）。",
                f"DeepSeek balance request failed: {type(exc).__name__}",
            ) from None
