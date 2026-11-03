from __future__ import annotations

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.config import AstrBotConfig

from .balance_http_client import BalanceHttpClient
from .balance_service import BalanceService
from .settings_reader import SettingsReader


class DeepSeekBalancePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self._service = BalanceService(
            BalanceHttpClient(),
            SettingsReader(),
            self.logger,
        )

    @filter.llm_tool(name="deepseek_balance_fetch")
    async def deepseek_balance_fetch(self, event: AstrMessageEvent) -> str:
        """查询当前配置的 DeepSeek API 账户余额，返回账户余额信息，包括货币类型、总余额以及不同类型的余额明细。适用于用户询问 API 账户余额、可用额度或账户资金情况时。"""
        return await self._service.fetch(self.config)
