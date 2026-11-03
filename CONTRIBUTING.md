# 贡献指南

感谢你愿意改进 `astrbot_plugin_deepseek_balance`。本插件刻意保持小巧：只提供一个无参数的余额查询工具，只读取两个配置项。贡献时请优先考虑“修复明确问题”，而不是“增加新能力”。

开始之前建议先读：

- [README.md](README.md)：用户安装、配置与错误处理
- [DEVELOPMENT.md](DEVELOPMENT.md)：架构、测试体系、调试与发布细节
- [worklog.md](worklog.md)：分阶段开发记录与已验证事实

## 1. 可以贡献什么

欢迎的贡献：

- 修复真实缺陷（错误分类不正确、异常未捕获、返回结构不一致等）。
- 补充测试覆盖，尤其是能在无网络环境下复现问题的单元测试。
- 改进文档中过时、含混或错误的内容。
- 提升与 AstrBot `>=4.29.0` 的兼容性。
- 更清晰的错误提示与日志（不得泄露 Key 或余额明细）。

通常不会被接受的改动：

- 定时查询、余额告警、历史记录、数据库、缓存。
- 多 Key、多 Provider、接入其他服务商的余额接口。
- 聊天命令、管理面板、MCP、固定回复模板。
- 引入 `pytest`、`requests` 或新的运行时依赖。
- 自动补全 URL 路径、自动跟随重定向、自动重试。
- 为“以后可能用到”而增加的抽象层或配置项。

如果想法可能触及上述边界，请先开 Issue 说明动机与使用场景，再决定是否实现。

## 2. 报告问题

提交 Issue 前请先搜索是否已有相同问题。一个可处理的问题报告应包含：

| 内容 | 说明 |
| --- | --- |
| 环境 | AstrBot 版本、Python 版本、操作系统 |
| 现象 | 实际发生了什么，最好附上完整错误文本 |
| 期望 | 你认为正确的结果 |
| 复现步骤 | 配置内容（**Key 用 `sk-***` 代替**）、操作路径 |
| 日志 | 已脱敏的相关日志行 |

不要在 Issue 中粘贴：

- 真实 API Key（即使已失效）
- 完整账户余额或账单截图（除非你确认可以公开）
- 含 Key 的插件配置文件、E2E `--keep` 目录内容

如果怀疑是安全问题（例如 Key 出现在日志或工具返回值中），请不要开公开 Issue，直接通过仓库维护者提供的私下渠道联系。

## 3. 开发流程

### 3.1 准备环境

```bash
git clone https://github.com/msksbr515/astrbot_plugin_deepseek_balance.git
cd astrbot_plugin_deepseek_balance
uv venv --python 3.12
uv pip install astrbot ruff
```

运行基线检查：

```bash
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
```

单元测试完全离线，不需要 Key。涉及真实接口的测试需要 `.env`：

```bash
cp .env.example .env
# 填写 DEEPSEEK_TEST_API_KEY，只用于本地验证
```

`.env` 不得提交、不得贴进 Issue/PR。

### 3.2 分支与提交

- 从最新的 `main` 拉出功能分支。
- 分支名建议：`fix/redirect-error`、`docs/e2e-troubleshooting`、`test/timeout-boundary`。
- 一个分支只做一件事；重构与行为变更不要混在同一个提交里。
- 提交信息使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

| 前缀 | 用途 | 示例 |
| --- | --- | --- |
| `feat` | 新能力（需先确认符合项目边界） | `feat(http): classify 408 responses as timeout` |
| `fix` | 修复缺陷 | `fix(client): avoid leaking key in DNS errors` |
| `test` | 只改测试 | `test(e2e): assert currency set equality` |
| `docs` | 只改文档 | `docs(readme): clarify full URL requirement` |
| `refactor` | 不改行为的结构调整 | `refactor(service): extract result builder` |
| `chore` | 构建、依赖、发布杂项 | `chore(release): bump version to 0.2.0` |

提交主题用祈使句、不超过约 72 字符；正文说明**为什么**改，而不是逐行复述 diff。

### 3.3 改动要求

代码：

- 保持模块扁平，新增职责时新建同目录小模块，不新增子包。
- 跨模块导入必须使用相对导入（`from .balance_response import ...`）。
- 公共函数/方法写类型标注；异步方法返回明确类型。
- 工具内部失败必须转成 `ToolResult.failure()`，不要让异常穿透到 AstrBot。
- 不引入新的运行时依赖；`aiohttp` 由 AstrBot 提供。
- 注释只解释“为什么”，不复述代码。

测试：

- 修复缺陷时，先补一个能失败的回归测试，再修复。
- 单元测试放在 `tests/test_*.py`，使用标准库 `unittest`。
- 需要 HTTP Mock 时复用 `BalanceMockServer`；需要构造插件时复用 `BalanceToolHarness`。
- 测试中的 Key 必须是明显假值（如 `sk-test-key-1234567890`）。
- 测试不得依赖执行顺序，也不得访问真实网络（`test_real_api.py` 与 E2E 除外）。

文档：

- 行为、错误类型、配置项、返回结构发生变化时，同步更新 `README.md`。
- 架构或测试流程变化时，同步更新 `DEVELOPMENT.md`。
- 完成一个阶段或一次完整验证后，在 `worklog.md` 追加记录，写明执行了什么、结果如何、哪些没有做。

## 4. 测试矩阵

提交 PR 前至少完成：

| 检查 | 命令 | 要求 |
| --- | --- | --- |
| 单元测试 | `uv run python -m unittest discover -s tests -v` | 全部通过 |
| 静态检查 | `uv run ruff check .` | 无告警 |
| 格式检查 | `uv run ruff format --check .` | 无差异 |

涉及以下改动时，还需要额外验证：

| 改动类型 | 额外要求 |
| --- | --- |
| 修改工具描述 | 同步 `tests/balance_fixtures.py` 的 `TOOL_DESCRIPTION`，并说明是否需要重跑 E2E |
| 修改请求逻辑或错误分类 | 补充对应单元测试 |
| 新增/修改配置项 | 同步 `_conf_schema.json`、`SettingsReader`、README 与测试 |
| 修改打包相关文件 | 本地构建 ZIP，并用 `_PluginUpdater.inspect_plugin_archive` 检查 |
| 修改 E2E 流程 | 在真实 AstrBot 实例中跑通 `tests/e2e_real_astrbot.py` |

有条件时请运行真实接口与 E2E：

```bash
uv run python -m unittest discover -s tests -v
uv run python tests/e2e_real_astrbot.py
```

E2E 会消耗真实模型调用与少量余额，属于外部副作用；维护者不会要求每位贡献者都运行。**在 PR 中请如实说明哪些测试跑过、哪些没跑**，不要根据“应该能通过”推断结果。

## 5. 安全与凭据

这是本项目的硬性规则：

- 永远不要把真实 API Key 写入代码、测试、文档、worklog、Issue、PR 或提交信息。
- 永远不要提交 `.env`；`.env.example` 只能包含占位符。
- 日志不得包含 Key、完整响应体或余额明细。
- 新增错误分支必须经过 `SecretRedactor`，失败结果必须通过 `ToolResult.failure()`。
- `body_preview` 先截断到 300 字符再脱敏。
- E2E `--keep` 目录包含真实 Key，排查完请立即删除。
- 如果 Key 曾出现在对话、日志、截图或临时目录中，请立即到 DeepSeek 控制台轮换。

提交前请检查暂存内容：

```bash
git status
git diff --cached
```

如果发现疑似敏感文件被暂存，先取消暂存并确认，不要依赖后续提交“覆盖”。

## 6. 提交 Pull Request

PR 描述建议包含：

1. **问题**：要解决什么，为什么现有行为不对。
2. **方案**：如何修改，关键取舍是什么。
3. **测试**：实际执行了哪些命令、结果如何；未执行的部分要说明原因。
4. **影响面**：是否改变工具返回值、错误类型、配置项或打包内容。

PR 自查清单：

- [ ] 改动聚焦单一目的，没有夹带无关重构
- [ ] 新增/修改行为有对应测试
- [ ] `unittest`、`ruff check`、`ruff format --check` 通过
- [ ] 没有提交 `.env`、真实 Key、缓存目录或临时文件
- [ ] 新增日志不含敏感信息，错误分支仍经过脱敏
- [ ] 同步更新了 README / DEVELOPMENT / worklog（如适用）
- [ ] PR 描述如实说明测试范围

维护者可能会要求拆分过大的 PR，或拒绝超出项目边界的功能。这不是对贡献者的否定，而是为了保持插件可预测、易维护。

## 7. 审核关注点

审核时主要看：

- 是否仍只做“查询余额”这一件事。
- 失败是否仍然返回结构化错误，而不是虚假的零余额或异常。
- Key 是否出现在任何输出、日志或断言信息中。
- 配置项是否仍然只有 `api_url` 与 `api_key`。
- 是否仍然兼容 AstrBot `>=4.29.0`，是否仍以 `data.plugins.<name>.main` 相对导入方式加载。
- 测试是否真正覆盖改动，而不是只改断言迎合实现。
- 文档描述与实际行为是否一致。

## 8. 版本与发布

版本号在 `metadata.yaml` 中维护，遵循语义化版本：

- 修复兼容性或错误分类：`patch`（如 `0.1.1`）
- 新增向后兼容能力：`minor`（如 `0.2.0`）
- 破坏工具返回值或配置结构：`major`（如 `1.0.0`）

发布由维护者执行：更新版本与文档、提交、打 `v<version>` 标签并推送。GitHub Actions 会校验标签与版本一致，构建 ZIP 并创建 Release。贡献者无需自行打标签或发布。

## 9. 许可证

提交贡献即表示你同意以本项目的 [MIT License](LICENSE) 授权你的贡献。请确保提交的代码为你本人原创，或来自与本项目许可证兼容的来源，并在 PR 中注明第三方代码的来源与许可证。

## 10. 行为准则

- 讨论聚焦技术与事实，尊重不同经验水平的贡献者。
- 不公开他人凭据、余额或其他敏感信息。
- 不提交针对真实服务的压测、扫描或滥用性测试。
- 对不确定的结论明确标注“未验证”，不要用推测冒充实测结果。