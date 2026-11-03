from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from assistant_report import AssistantReport, AssistantReportParser
from astrbot_dashboard import DashboardClient
from astrbot_instance import AstrBotInstance
from e2e_config import CHAT_MODEL, REPO_ROOT, TOOL_NAME, TestCredentials
from e2e_error import E2EError
from e2e_logs import LogRedactor, ToolResultExtractor


class E2ERunner:
    def __init__(self, keep: bool) -> None:
        self._keep = keep

    async def run(self) -> int:
        try:
            credentials = TestCredentials.from_env(REPO_ROOT / ".env")
        except E2EError as exc:
            print(f"E2E 测试失败: {exc}", file=sys.stderr)
            return 1

        root = Path(tempfile.mkdtemp(prefix="astrbot_deepseek_e2e_"))
        instance = AstrBotInstance(root, credentials)
        redactor = LogRedactor(credentials.api_key)
        completed = False
        try:
            print(f"[1/7] 创建临时 AstrBot 实例: {root}")
            instance.initialize()

            print(f"[2/7] 安装插件并写入插件配置（api_url={credentials.api_url}）")
            instance.install_plugin()

            print(f"[3/7] 启动 AstrBot: {instance.base_url}")
            instance.start()
            instance.wait_until_started()

            dashboard = DashboardClient(instance.base_url)
            token = await dashboard.login(instance.password)
            plugin = await dashboard.wait_for_plugin(token)
            print(
                f"[4/7] 插件已加载: {plugin.get('name')} "
                f"v{plugin.get('version')} activated={plugin.get('activated')}",
            )

            print(f"[5/7] 通过 WebChat 发送结构化 JSON 提示词（模型 {CHAT_MODEL}）")
            reply, _events = await dashboard.send_chat(token)

            instance.flush_log()
            tool_result = ToolResultExtractor(TOOL_NAME).extract(instance.log_text())
            actual_data = self._validate_tool_result(tool_result, reply)

            report = AssistantReportParser().parse(reply)
            problems = [
                *self._claim_problems(report),
                *report.check_against(actual_data),
            ]

            print("[6/7] 模型 JSON 报告（已与服务器工具结果逐字段比对）:")
            print(
                f"      saw_tool={report.saw_tool} "
                f"called_tool={report.called_tool} "
                f"tool_succeeded={report.tool_succeeded}",
            )
            print(f"      is_available={report.is_available}")
            for info in report.balance_infos:
                print(
                    f"      {info.currency}: "
                    f"total_balance={info.total_balance} "
                    f"granted_balance={info.granted_balance} "
                    f"topped_up_balance={info.topped_up_balance}",
                )
            print("[7/7] 助手评价（仅输出，不参与断言）:")
            print(f"      evaluation={redactor.redact(report.evaluation)}")
            print(f"      reason={redactor.redact(report.reason)}")

            if problems:
                raise E2EError(
                    "模型报告未通过校验：\n- " + "\n- ".join(problems),
                )

            print(
                "\nE2E 测试通过：真实 AstrBot 实例加载插件，"
                "模型实际调用了余额查询工具，JSON 报告与真实结果一致。",
            )
            completed = True
            return 0
        except E2EError as exc:
            print(f"\nE2E 测试失败: {exc}", file=sys.stderr)
            if instance.log_path.is_file():
                print(
                    "\n--- 服务器日志（已脱敏，隐藏余额字段）---",
                    file=sys.stderr,
                )
                print(redactor.failure_report(instance.log_text()), file=sys.stderr)
            return 1
        finally:
            instance.stop()
            if self._keep:
                print(f"\n已保留临时实例（包含真实 Key 的插件配置）: {root}")
            else:
                await self._remove_instance(root)
            if not completed and not self._keep:
                print("临时实例已删除。")

    @staticmethod
    def _validate_tool_result(
        tool_result: dict[str, Any] | None,
        reply: str,
    ) -> dict[str, Any]:
        if tool_result is None:
            raise E2EError(
                "模型回复了，但没有找到 deepseek_balance_fetch 的工具结果；"
                f"回复长度={len(reply)}",
            )
        if not tool_result.get("ok"):
            raise E2EError(f"工具返回失败: {tool_result.get('error')}")
        data = tool_result.get("data")
        if not isinstance(data, dict):
            raise E2EError("工具返回的 data 不是 JSON 对象")
        if not isinstance(data.get("balance_infos"), list):
            raise E2EError("工具返回中缺少 balance_infos")
        return data

    @staticmethod
    def _claim_problems(report: AssistantReport) -> list[str]:
        problems: list[str] = []
        if not report.saw_tool:
            problems.append("saw_tool=False：模型表示未在提示词中看到工具")
        if not report.called_tool:
            problems.append("called_tool=False：模型表示未调用工具")
        if not report.tool_succeeded:
            problems.append("tool_succeeded=False：模型表示工具调用失败")
        return problems

    @staticmethod
    async def _remove_instance(root: Path) -> None:
        for _ in range(5):
            shutil.rmtree(root, ignore_errors=True)
            if not root.exists():
                return
            await asyncio.sleep(0.5)
