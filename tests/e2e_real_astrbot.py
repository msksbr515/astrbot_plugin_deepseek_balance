"""在真实 AstrBot 实例中验证插件：安装插件 -> 配置真实 Key -> 模型调用工具 -> 查询余额。

用法（仓库根目录）：

    uv run python tests/e2e_real_astrbot.py

凭据从仓库根目录的 `.env` 读取：

    DEEPSEEK_TEST_API_KEY=...
    DEEPSEEK_TEST_API_URL=https://api.deepseek.com/user/balance

脚本会在临时目录启动一个真实的 AstrBot（dashboard + WebChat），把本插件安装到
`data/plugins/`，在插件配置中写入真实 Key，并让 DeepSeek 模型（同一个 Key）通过
dashboard 的 WebChat 会话回答“查余额”。测试不打印 Key、余额数值或助手的完整回复。
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys

from e2e_runner import E2ERunner


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    parser = argparse.ArgumentParser(
        description="在真实 AstrBot 中端到端验证 DeepSeek 余额插件",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="保留临时 AstrBot 目录用于排查（目录内含真实 API Key）",
    )
    args = parser.parse_args()

    if importlib.util.find_spec("astrbot") is None:
        print(
            "未找到 astrbot，请在仓库根目录使用 `uv run python "
            "tests/e2e_real_astrbot.py` 运行。",
            file=sys.stderr,
        )
        return 2

    try:
        return asyncio.run(E2ERunner(args.keep).run())
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
