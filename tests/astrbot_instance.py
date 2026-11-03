from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from e2e_config import (
    CHAT_API_BASE,
    CHAT_MODEL,
    CHAT_PROVIDER_ID,
    PLUGIN_NAME,
    REPO_ROOT,
    STARTUP_TIMEOUT_SECONDS,
    TestCredentials,
)
from e2e_error import E2EError


class AstrBotInstance:
    def __init__(self, root: Path, credentials: TestCredentials) -> None:
        self.root = root
        self.credentials = credentials
        self.port = self._free_port()
        self.password = self._generate_dashboard_password()
        self.log_path = root / "astrbot.log"
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._process: subprocess.Popen | None = None
        self._log_file = None

    def initialize(self) -> None:
        config = self._initialize()
        self._configure(config)
        self._write_json(self.root / "data" / "cmd_config.json", config)

    def start(self) -> None:
        env = {
            **os.environ,
            "ASTRBOT_DASHBOARD_INITIAL_PASSWORD": self.password,
            "DASHBOARD_HOST": "127.0.0.1",
            "DASHBOARD_PORT": str(self.port),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        self._log_file = self.log_path.open("w", encoding="utf-8", errors="replace")
        self._process = subprocess.Popen(
            [sys.executable, "-m", "astrbot.cli", "run"],
            cwd=self.root,
            env=env,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

    def wait_until_started(self) -> None:
        if self._process is None:
            raise E2EError("AstrBot process has not been started")
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise E2EError(
                    f"AstrBot exited early with code {self._process.returncode}:\n"
                    f"{self.log_text()[-1500:]}",
                )
            if "AstrBot started." in self.log_text():
                return
            time.sleep(1)
        raise E2EError(f"AstrBot did not start within {STARTUP_TIMEOUT_SECONDS}s")

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=10)
        if self._log_file is not None:
            self._log_file.flush()
            self._log_file.close()
            self._log_file = None

    def flush_log(self) -> None:
        if self._log_file is not None:
            self._log_file.flush()

    def log_text(self) -> str:
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def _initialize(self) -> dict[str, Any]:
        init = subprocess.run(
            [sys.executable, "-m", "astrbot.cli", "init", "-y"],
            cwd=self.root,
            check=False,
            env={
                **os.environ,
                "ASTRBOT_DASHBOARD_INITIAL_PASSWORD": self.password,
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if init.returncode != 0:
            raise E2EError(f"astrbot init failed: {init.stderr.strip()[-800:]}")
        config_path = self.root / "data" / "cmd_config.json"
        if not config_path.is_file():
            raise E2EError("astrbot init did not create data/cmd_config.json")
        return self._read_json(config_path)

    def _configure(self, config: dict[str, Any]) -> None:
        config["provider"] = [
            {
                "id": CHAT_PROVIDER_ID,
                "provider": "deepseek",
                "type": "openai_chat_completion",
                "provider_type": "chat_completion",
                "enable": True,
                "model": CHAT_MODEL,
                "key": ["$DEEPSEEK_TEST_API_KEY"],
                "api_base": CHAT_API_BASE,
                "timeout": 120,
                "proxy": "",
                "custom_headers": {},
            }
        ]
        config["agent_runner"]["runner_type"] = "local"
        config["agent_runner"]["config"]["model"]["provider_id"] = CHAT_PROVIDER_ID
        config["provider_settings"]["enable"] = True
        config["dashboard"]["enable"] = True
        config["dashboard"]["host"] = "127.0.0.1"
        config["dashboard"]["port"] = self.port

    def install_plugin(self) -> None:
        plugin_dir = self.root / "data" / "plugins" / PLUGIN_NAME
        plugin_dir.mkdir(parents=True)
        for source in self._plugin_files():
            shutil.copy2(source, plugin_dir / source.name)
        config_path = self.root / "data" / "config" / f"{PLUGIN_NAME}_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(
            config_path,
            {
                "api_url": self.credentials.api_url,
                "api_key": self.credentials.api_key,
            },
        )

    @staticmethod
    def _plugin_files() -> tuple[Path, ...]:
        modules = sorted(REPO_ROOT.glob("*.py"))
        extras = [REPO_ROOT / name for name in ("metadata.yaml", "_conf_schema.json")]
        return (*modules, *extras)

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _generate_dashboard_password() -> str:
        # AstrBot 要求至少包含大写、小写和数字。
        return f"E2e{secrets.token_hex(8)}9A"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
