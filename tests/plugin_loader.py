from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

os.environ.setdefault(
    "ASTRBOT_ROOT",
    os.path.join(tempfile.gettempdir(), "astrbot_plugin_deepseek_balance_tests"),
)


def load_plugin_module(name: str):
    parent = str(REPO_ROOT.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    return importlib.import_module(f"{REPO_ROOT.name}.{name}")
