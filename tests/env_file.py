from __future__ import annotations

import os
from pathlib import Path


class EnvFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> None:
        if not self._path.is_file():
            return
        for raw_line in self._path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if name and name not in os.environ:
                os.environ[name] = value.strip().strip('"').strip("'")
