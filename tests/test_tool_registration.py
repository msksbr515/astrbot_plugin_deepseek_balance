from __future__ import annotations

import unittest

from astrbot.api.star import Star
from balance_fixtures import TOOL_DESCRIPTION
from plugin_loader import load_plugin_module

main = load_plugin_module("main")


class ToolRegistrationTest(unittest.TestCase):
    def test_plugin_class_is_a_star(self) -> None:
        self.assertTrue(issubclass(main.DeepSeekBalancePlugin, Star))

    def test_tool_is_registered_without_parameters(self) -> None:
        from astrbot.core.provider.register import llm_tools

        tool = llm_tools.get_func("deepseek_balance_fetch")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "deepseek_balance_fetch")
        self.assertEqual(tool.description, TOOL_DESCRIPTION)
        self.assertEqual(tool.parameters, {"type": "object", "properties": {}})
