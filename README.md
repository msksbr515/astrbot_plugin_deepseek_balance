# AstrBot DeepSeek 余额查询插件

为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 的 AI Agent 提供查询 DeepSeek API 账户余额的工具。用户询问余额时，模型可以自主调用该工具；插件请求用户配置的 API 地址，并把原始余额数据交还给模型，由模型组织回答。

## 功能

- 注册一个 Agent Tool：`deepseek_balance_fetch`，无需用户提供参数。
- 使用插件配置中的**完整 API URL** 发起 HTTP GET 请求，不拼接、不追加任何路径。
- 通过 `Authorization: Bearer <API_KEY>` 认证。
- 成功时返回结构化 JSON，保留接口返回的原始业务字段（`is_available`、`balance_infos` 及其明细）。
- 对配置缺失、网络异常、HTTP 错误、超时、非 JSON 响应、字段缺失等情况返回明确的错误类型，不会把失败当成余额为零。
- 不会在日志或工具返回内容中输出 API Key。

本插件不包含定时查询、余额告警、历史记录、数据库、多 Key / 多 Provider 管理等功能。

## 工具说明

| 项目 | 内容 |
| --- | --- |
| 工具名称 | `deepseek_balance_fetch` |
| 工具参数 | 无 |
| 调用方式 | 由模型根据用户意图自主调用（function calling） |
| 适用场景 | 用户询问 API 账户余额、可用额度或账户资金情况 |
| 返回内容 | JSON 文本，包含 HTTP 状态码与接口原始数据；失败时包含错误类型、原因与状态码 |

成功返回示例：

```json
{
  "ok": true,
  "http_status": 200,
  "data": {
    "is_available": true,
    "balance_infos": [
      {
        "currency": "CNY",
        "total_balance": "110.00",
        "granted_balance": "10.00",
        "topped_up_balance": "100.00"
      }
    ]
  }
}
```

失败返回示例：

```json
{
  "ok": false,
  "error": {
    "type": "auth_error",
    "message": "API 认证失败（HTTP 401），请检查 API Key 是否正确以及是否有访问权限。",
    "http_status": 401,
    "response": { "error": { "message": "Authentication Fails" } }
  }
}
```

## 插件配置

插件只有一个配置文件 `_conf_schema.json`，配置页面中只有两个配置项：

| 配置项 | 类型 | 说明 |
| --- | --- | --- |
| `api_url` | 字符串 | 余额查询接口的**完整 URL** |
| `api_key` | 字符串（Secret，密码框显示） | DeepSeek API Key，用于 Bearer 认证 |

### API URL 填写要求

插件会**原样使用**配置的 URL 发起请求，不会自动添加 `/user/balance`、不会追加斜杠、不会改写路径。

- 正确示例：`https://api.deepseek.com/user/balance`
- 错误示例：`https://api.deepseek.com`（缺少路径，插件不会自动补全）
- 错误示例：`api.deepseek.com/user/balance`（缺少 `http://` 或 `https://`）

DeepSeek 官方接口参考：[获取用户余额](https://api-docs.deepseek.com/zh-cn/api/get-user-balance)（`GET /user/balance`）。

插件不跟随 HTTP 重定向。如果接口返回 3xx，请把配置改为最终地址。

### API Key 配置方法

在 AstrBot WebUI 的插件配置页面填写 `api_key`。该字段使用 Secret 类型，页面以密码形式展示。API Key 只用于生成请求头 `Authorization: Bearer <API_KEY>`，不会写入日志、工具返回值或错误信息。

## 使用示例

用户在聊天中询问：

> 我的 DeepSeek API 还有多少余额？

模型调用 `deepseek_balance_fetch`，插件请求配置的 URL，返回上述 JSON；模型再根据 `data` 中的余额字段向用户说明。插件本身不生成固定文案。

## 错误处理

所有失败都会返回 `ok: false` 与 `error.type`，不会返回虚假的零余额。

| `error.type` | 含义 |
| --- | --- |
| `config_error` | API URL 或 API Key 未配置，或 URL 格式无效 |
| `invalid_url` | URL 无法被 HTTP 客户端解析 |
| `dns_error` | 域名解析失败 |
| `connection_error` | 无法建立连接（如连接被拒绝） |
| `ssl_error` | TLS 证书校验失败 |
| `timeout` | 请求超时（15 秒） |
| `network_error` | 其他网络请求错误 |
| `auth_error` | HTTP 401 / 403 |
| `endpoint_not_found` | HTTP 404 |
| `rate_limited` | HTTP 429 |
| `redirect_error` | HTTP 3xx（插件不跟随重定向） |
| `server_error` | HTTP 5xx |
| `http_error` | 其他非 2xx 状态码 |
| `invalid_json` | 响应不是有效 JSON |
| `invalid_response` | JSON 中缺少 `is_available` 或 `balance_infos` |
| `business_error` | 响应 JSON 中包含 `error` 字段 |

接口返回的 JSON 错误信息会放在 `error.response` 中；非 JSON 响应会提供截断到 300 字符的 `body_preview` 与 `content_type`。

## 安装

仓库地址：<https://github.com/msksbr515/astrbot_plugin_deepseek_balance>

### 1. 插件市场安装

本插件目前**尚未提交/收录到 AstrBot 插件市场**。待上架后，可在 AstrBot WebUI 的插件市场搜索 `astrbot_plugin_deepseek_balance` 或“DeepSeek 余额”安装。

插件市场安装由官方渠道分发，与下面的 GitHub 安装方式互不影响。

### 2. WebUI 通过 URL 安装

1. 打开 AstrBot WebUI，进入插件管理页面。
2. 点击安装插件，选择从链接安装。
3. 填写 Git 仓库地址（不是 README 网页地址）：
   `https://github.com/msksbr515/astrbot_plugin_deepseek_balance`
4. 等待安装完成，确认插件已加载。
5. 在插件配置页填写 `api_url` 与 `api_key`。

### 3. ZIP 安装

1. 打开 GitHub 仓库页面，选择 `Code` → `Download ZIP`。
2. 在 AstrBot WebUI 的插件安装界面选择从文件安装。
3. 上传 ZIP，等待安装完成并检查插件加载状态。
4. 在插件配置页填写配置。

ZIP 中包含完整插件文件，无需手动修改源码。

### 4. Git Clone 手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/msksbr515/astrbot_plugin_deepseek_balance.git
```

然后在 AstrBot WebUI 中检查插件列表，必要时重载插件。使用 Docker 部署时，`AstrBot/data/plugins` 的宿主机路径以实际挂载目录为准。

### 安装方式区别

| 方式 | 来源 | 更新方式 |
| --- | --- | --- |
| 插件市场 | 官方市场收录的版本 | 通过 WebUI 更新 |
| URL 安装 | GitHub 仓库 | 通过 WebUI 重新安装或更新 |
| ZIP 安装 | 手动下载的源码包 | 重新下载并上传 |
| Git Clone | 本地克隆的仓库 | 在插件目录内 `git pull` |

## 兼容性

- 开发与验证环境：AstrBot **4.29.4**、Python **3.12.15**。
- `metadata.yaml` 声明 `astrbot_version: ">=4.29.4"`，AstrBot 启动时会按该范围检查兼容性。
- 依赖：仅使用 AstrBot 自带的 `aiohttp`，因此没有 `requirements.txt`。

## 已知限制

- 仅适配 DeepSeek `GET /user/balance` 的响应结构（`is_available` + `balance_infos`）；其他服务商的余额接口未适配。
- 不跟随 HTTP 重定向，不自动重试，不做余额告警或历史记录。
- 工具注册、请求与错误处理已通过本地 Mock HTTP 服务测试；**尚未在真实 DeepSeek 账户与真实 AstrBot 运行实例中做端到端验证**（详见 `worklog.md`）。

## 开发与测试

```bash
uv venv --python 3.12
uv pip install astrbot ruff
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
```

测试使用本地 `aiohttp` Mock 服务，不访问真实 DeepSeek 接口，也不需要真实 API Key。

## 插件市场发布（维护者）

1. 将代码推送到公开 GitHub 仓库。
2. 注册 AstrBot Cloud 账号。
3. 打开插件发布入口 <https://plugins.astrbot.app/>，并按官方文档在 <https://cloud.astrbot.app/publish> 提交插件。
4. 等待审核结果。

提交前确认 `metadata.yaml`、README、`LICENSE` 与版本号均为最新；插件市场 ZIP 包大小上限为 16 MB（官方文档：[插件发布](https://docs.astrbot.app/dev/star/plugin-publish.html)）。

## 许可证

本项目采用 [MIT License](LICENSE)。许可证文件位于仓库根目录的 `LICENSE`。

直接依赖 `aiohttp` 由 AstrBot 提供，其包元数据标注许可证为 `Apache-2.0 AND MIT`，与本项目的 MIT 分发方式兼容；本项目未复制或修改第三方源码。插件运行在 AstrBot（AGPL-3.0-or-later）之上，本仓库不包含 AstrBot 本体源码。
