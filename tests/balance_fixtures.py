from __future__ import annotations

API_KEY = "sk-test-key-1234567890"

TOOL_DESCRIPTION = (
    "查询当前配置的 DeepSeek API 账户余额，返回账户余额信息，包括货币类型、"
    "总余额以及不同类型的余额明细。适用于用户询问 API 账户余额、可用额度或"
    "账户资金情况时。"
)

BALANCE_PAYLOAD = {
    "is_available": True,
    "balance_infos": [
        {
            "currency": "CNY",
            "total_balance": "110.00",
            "granted_balance": "10.00",
            "topped_up_balance": "100.00",
        }
    ],
}
