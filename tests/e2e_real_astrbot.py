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
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "astrbot_plugin_deepseek_balance"
PLUGIN_FILES = ("main.py", "metadata.yaml", "_conf_schema.json")
TOOL_NAME = "deepseek_balance_fetch"
PROMPT = "查余额"
CHAT_PROVIDER_ID = "deepseek-e2e"
CHAT_API_BASE = "https://api.deepseek.com/v1"
CHAT_MODEL = "deepseek-chat"
STARTUP_TIMEOUT_SECONDS = 180
CHAT_TIMEOUT_SECONDS = 180

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9]{8,}")


class E2EError(RuntimeError):
    pass


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")


def _redact(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "***")
    return _SECRET_PATTERN.sub("sk-***", text)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _generate_dashboard_password() -> str:
    # AstrBot 要求至少包含大写、小写和数字。
    return f"E2e{secrets.token_hex(8)}9A"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )


def _prepare_instance(root: Path, password: str) -> dict:
    init = subprocess.run(
        [sys.executable, "-m", "astrbot.cli", "init", "-y"],
        cwd=root,
        check=False,
        env={**os.environ, "ASTRBOT_DASHBOARD_INITIAL_PASSWORD": password},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if init.returncode != 0:
        raise E2EError(f"astrbot init failed: {init.stderr.strip()[-800:]}")
    config_path = root / "data" / "cmd_config.json"
    if not config_path.is_file():
        raise E2EError("astrbot init did not create data/cmd_config.json")
    return _read_json(config_path)


def _install_plugin(root: Path, api_url: str, api_key: str) -> Path:
    plugin_dir = root / "data" / "plugins" / PLUGIN_NAME
    plugin_dir.mkdir(parents=True)
    for name in PLUGIN_FILES:
        shutil.copy2(REPO_ROOT / name, plugin_dir / name)
    config_path = root / "data" / "config" / f"{PLUGIN_NAME}_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(config_path, {"api_url": api_url, "api_key": api_key})
    return plugin_dir


def _configure_instance(config: dict, port: int) -> None:
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
    config["dashboard"]["port"] = port


def _start_server(
    root: Path,
    port: int,
    password: str,
    log_path: Path,
) -> tuple[subprocess.Popen, object]:
    env = {
        **os.environ,
        "ASTRBOT_DASHBOARD_INITIAL_PASSWORD": password,
        "DASHBOARD_HOST": "127.0.0.1",
        "DASHBOARD_PORT": str(port),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    log_file = log_path.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [sys.executable, "-m", "astrbot.cli", "run"],
        cwd=root,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    return proc, log_file


def _stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _log_text(log_path: Path) -> str:
    return log_path.read_text(encoding="utf-8", errors="replace")


def _wait_for_startup(proc: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise E2EError(
                f"AstrBot exited early with code {proc.returncode}:\n"
                f"{_log_text(log_path)[-1500:]}",
            )
        if "AstrBot started." in _log_text(log_path):
            return
        time.sleep(1)
    raise E2EError(f"AstrBot did not start within {STARTUP_TIMEOUT_SECONDS}s")


async def _login(base_url: str, password: str) -> str:
    timeout = aiohttp.ClientTimeout(total=15)
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.post(
            f"{base_url}/api/v1/auth/login",
            json={"username": "astrbot", "password": password},
        ) as response,
    ):
        payload = await response.json(content_type=None)
        if response.status != 200 or payload.get("status") != "ok":
            raise E2EError(
                f"dashboard login failed (HTTP {response.status}): "
                f"{payload.get('message')}",
            )
        token = (payload.get("data") or {}).get("token")
        if not isinstance(token, str) or not token:
            raise E2EError("dashboard login returned no token")
        return token


async def _plugin_status(base_url: str, token: str) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"Authorization": f"Bearer {token}"}
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.get(
            f"{base_url}/api/plugin/get",
            headers=headers,
        ) as response,
    ):
        payload = await response.json(content_type=None)
    if payload.get("status") != "ok":
        raise E2EError(f"plugin list failed: {payload.get('message')}")
    data = payload.get("data")
    plugins = data if isinstance(data, list) else (data or {}).get("plugins", [])
    for plugin in plugins:
        if plugin.get("name") == PLUGIN_NAME:
            return plugin
    return None


async def _wait_for_plugin(base_url: str, token: str) -> dict:
    deadline = time.monotonic() + 60
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            plugin = await _plugin_status(base_url, token)
            if plugin and plugin.get("activated"):
                return plugin
        except (TimeoutError, aiohttp.ClientError, E2EError) as exc:
            last_error = exc
        await asyncio.sleep(1)
    detail = f" (last error: {last_error})" if last_error else ""
    raise E2EError(f"plugin {PLUGIN_NAME} was not activated{detail}")


async def _send_chat(base_url: str, token: str) -> tuple[str, list[dict]]:
    ws_url = f"{base_url}/api/v1/unified-chat/ws?token={token}"
    message_id = secrets.token_hex(8)
    session_id = f"e2e_{secrets.token_hex(4)}"
    texts: list[str] = []
    events: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=CHAT_TIMEOUT_SECONDS + 30)
    async with (
        aiohttp.ClientSession(timeout=timeout) as session,
        session.ws_connect(ws_url, heartbeat=30) as ws,
    ):
        await ws.send_json(
            {
                "ct": "chat",
                "t": "send",
                "message": [{"type": "plain", "text": PROMPT}],
                "session_id": session_id,
                "message_id": message_id,
            }
        )
        deadline = time.monotonic() + CHAT_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise E2EError(
                    f"no chat response within {CHAT_TIMEOUT_SECONDS}s",
                )
            msg = await ws.receive(timeout=remaining)
            if msg.type != aiohttp.WSMsgType.TEXT:
                raise E2EError(f"WebSocket closed unexpectedly: {msg.type}")
            payload = json.loads(msg.data)
            if payload.get("message_id") not in (None, message_id):
                continue
            events.append(payload)
            if payload.get("t") == "error":
                raise E2EError(
                    f"chat error: {payload.get('code')} {payload.get('data')}",
                )
            if payload.get("type") == "plain" and payload.get("data"):
                texts.append(str(payload["data"]))
            if payload.get("type") == "end":
                return "".join(texts), events


def _extract_tool_result(log_text: str) -> dict | None:
    marker = f"Tool `{TOOL_NAME}` Result: "
    index = log_text.rfind(marker)
    if index < 0:
        return None
    start = log_text.find("{", index + len(marker))
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for pos in range(start, len(log_text)):
        char = log_text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(log_text[start : pos + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _failure_report(
    log_path: Path,
    api_key: str,
    limit: int = 40,
) -> str:
    lines = _log_text(log_path).splitlines()[-limit:]
    safe = [
        _redact(line, api_key)
        for line in lines
        if "balance_infos" not in line
        and "total_balance" not in line
        and "granted_balance" not in line
        and "topped_up_balance" not in line
    ]
    return "\n".join(safe)


async def _run(args: argparse.Namespace) -> int:
    _load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_TEST_API_KEY", "").strip()
    api_url = os.environ.get(
        "DEEPSEEK_TEST_API_URL",
        "https://api.deepseek.com/user/balance",
    ).strip()
    if not api_key:
        raise E2EError(
            "DEEPSEEK_TEST_API_KEY is not set; create .env from .env.example",
        )
    parts = urlsplit(api_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise E2EError("DEEPSEEK_TEST_API_URL must be a full http(s) URL")

    password = _generate_dashboard_password()
    port = _free_port()
    root = Path(tempfile.mkdtemp(prefix="astrbot_deepseek_e2e_"))
    log_path = root / "astrbot.log"
    base_url = f"http://127.0.0.1:{port}"
    proc: subprocess.Popen | None = None
    log_file = None
    completed = False
    try:
        print(f"[1/7] 创建临时 AstrBot 实例: {root}")
        config = _prepare_instance(root, password)
        _configure_instance(config, port)
        _write_json(root / "data" / "cmd_config.json", config)

        print(f"[2/7] 安装插件并写入插件配置（api_url={api_url}）")
        _install_plugin(root, api_url, api_key)

        print(f"[3/7] 启动 AstrBot: {base_url}")
        proc, log_file = _start_server(root, port, password, log_path)
        _wait_for_startup(proc, log_path)

        token = await _login(base_url, password)
        plugin = await _wait_for_plugin(base_url, token)
        print(
            f"[4/7] 插件已加载: {plugin.get('name')} "
            f"v{plugin.get('version')} activated={plugin.get('activated')}",
        )

        print(f"[5/7] 通过 WebChat 发送消息: {PROMPT!r}（模型 {CHAT_MODEL}）")
        reply, _events = await _send_chat(base_url, token)

        if log_file is not None:
            log_file.flush()
        log_text = _log_text(log_path)
        tool_result = _extract_tool_result(log_text)
        if tool_result is None:
            raise E2EError(
                "模型回复了，但没有找到 deepseek_balance_fetch 的工具结果；"
                f"回复长度={len(reply)}",
            )
        if not tool_result.get("ok"):
            raise E2EError(f"工具返回失败: {tool_result.get('error')}")
        data = tool_result.get("data") or {}
        balance_infos = data.get("balance_infos")
        if not isinstance(balance_infos, list):
            raise E2EError("工具返回中缺少 balance_infos")

        print("[6/7] 工具调用成功:")
        print(f"      tool={TOOL_NAME} ok=True")
        print(f"      is_available={data.get('is_available')}")
        print(f"      balance_infos={len(balance_infos)} 条")
        print(
            f"[7/7] 助手回复: 长度={len(reply)} 提到“余额”={'余额' in reply}",
        )
        if not reply.strip():
            raise E2EError("助手没有返回文本回复")

        print("\nE2E 测试通过：真实 AstrBot 实例加载插件，模型实际调用了余额查询工具。")
        completed = True
        return 0
    except E2EError as exc:
        print(f"\nE2E 测试失败: {exc}", file=sys.stderr)
        if log_path.is_file():
            print("\n--- 服务器日志（已脱敏，隐藏余额字段）---", file=sys.stderr)
            print(_failure_report(log_path, api_key), file=sys.stderr)
        return 1
    finally:
        if proc is not None:
            _stop_server(proc)
        if log_file is not None:
            log_file.close()
        if args.keep:
            print(f"\n已保留临时实例（包含真实 Key 的插件配置）: {root}")
        else:
            for _ in range(5):
                shutil.rmtree(root, ignore_errors=True)
                if not root.exists():
                    break
                await asyncio.sleep(0.5)
        if not completed and not args.keep:
            print("临时实例已删除。")


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
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\n已中断。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
