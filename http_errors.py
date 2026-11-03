from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HttpErrorDetail:
    error_type: str
    message: str


class HttpErrorCatalog:
    @staticmethod
    def describe(status: int) -> HttpErrorDetail:
        if status in (401, 403):
            return HttpErrorDetail(
                "auth_error",
                f"API 认证失败（HTTP {status}），请检查 API Key 是否正确以及是否有访问权限。",
            )
        if status == 404:
            return HttpErrorDetail(
                "endpoint_not_found",
                "请求地址不存在（HTTP 404），请检查配置的 API 地址。",
            )
        if status == 429:
            return HttpErrorDetail(
                "rate_limited",
                "请求过于频繁或超出配额（HTTP 429），请稍后重试。",
            )
        if 300 <= status < 400:
            return HttpErrorDetail(
                "redirect_error",
                f"API 返回重定向（HTTP {status}），请将配置的 API 地址改为最终地址。",
            )
        if 500 <= status < 600:
            return HttpErrorDetail(
                "server_error",
                f"API 服务端错误（HTTP {status}），请稍后重试。",
            )
        return HttpErrorDetail("http_error", f"API 请求失败（HTTP {status}）。")
