# 为 ForeRSI 做贡献

[English](CONTRIBUTING.md) | 简体中文

## 本地开发

按照 [README](README_zh.md#安装) 创建 Python 环境并安装。可编辑安装后，`src/` 下的修改会直接用于 `fore-rsi` 命令。

## 配置与执行

- [src/config.py](src/config.py) 定义 `Config`、`WorkflowConfig` 和 `UIConfig`。任务与 harness 设置属于 `WorkflowConfig`，Herdr 命名会话属于 `UIConfig`。
- [src/cli.py](src/cli.py) 使用 tyro 从这些 dataclass 生成参数，返回一个完整的 `Config`，并处理帮助与版本输出。参数名称、默认值、类型和帮助说明随配置定义维护。

配置只保存数据。CLI 负责参数转换，workflow 负责业务校验、Agent 角色、调度和管理规则，harness 执行 Agent，Herdr 负责展示。避免另行维护一份字段类型清单，或为每个参数设置独立执行函数。

CLI 通过 `importlib.metadata` 读取安装版本；[pyproject.toml](pyproject.toml) 是包版本元数据的来源。

中英文文档保持一致。命令、示例和配置字段一起更新。凭据、私有基础设施信息和本地运行数据保留在仓库之外。

## Pre-commit

在当前 Python 环境中安装仓库钩子，并在提交改动前运行完整检查：

```bash
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

钩子会检查仓库文件规范、Python 语法、终端 Rust 格式以及严格 Clippy。

## 验证改动

```bash
fore-rsi --help
fore-rsi --version
python -m unittest discover -s tests
```

修改 CLI 时检查省略值、单独与组合参数、带空格的路径及会话名，以及对未知参数的拒绝。确认 workflow 与 UI 设置归入正确的嵌套配置，帮助与版本命令正常退出。面向用户的参数参考见 [docs/cli.md](docs/cli.md)。

测试覆盖参数解析与命令输出，无需调用模型。记录检查命令和实际结果；测试与依赖的规模应与改动相称。

## 提交 Pull Request

保持改动集中，说明问题、结果和验证。涉及公开接口或职责的大改动，先与维护者讨论。

PR 使用简短英文标题，以 `[Bugfix]`、`[Feature]`、`[Refactor]` 或 `[Docs]` 等标签开头；提交信息使用英文。

贡献采用 [Apache License 2.0](LICENSE) 许可证。
