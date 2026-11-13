# 为 ForeRSI 做贡献

[English](CONTRIBUTING.md) | 简体中文

## 本地开发

按照 [README](README_zh.md#安装) 创建 Python 环境并安装。可编辑安装后，`src/` 下的修改会直接用于 `fore-rsi` 命令。

Typer 统一定义 ForeRSI 参数；`config.py` 中每种配置的 dataclass 保存对应参数并定义 `handle()` 函数，`config_validator.py` 检查类型。让每个函数承担明确职责，保持代码易读。Agent 运行管理属于 workflow，Herdr 用于展示；业务处理函数目前只有骨架。

中英文文档保持一致。命令、示例和配置字段一起更新。凭据、私有基础设施信息和本地运行数据保留在仓库之外。

## 验证改动

以下命令不会调用模型，也不会创建 Agent：

```bash
fore-rsi --help
fore-rsi --version
fore-rsi --task task.md --workflow workflow_name --harness harness_name
fore-rsi --session session_name --detach
```

修改 CLI 时检查参数与各自 dataclass、处理函数的对应关系、带空格的值，以及对子命令、位置消息参数和未知选项的拒绝。当前支持的选项为 `--version`、`--help`、`--task`、`--workflow`、`--harness`、`--session`、`--detach`。修改 dataclass 时检查手动构造的非法字段类型。

前两条命令应成功；业务选项示例目前会以非零状态退出，提示尚未实现。可使用替代处理函数检查分发过程，避免运行 workflow。记录检查命令和实际结果；测试与依赖的规模应与代码相称。

## 提交 Pull Request

保持改动集中，说明问题、结果和验证。涉及公开接口或职责的大改动，先与维护者讨论。

PR 使用简短英文标题，以 `[Bugfix]`、`[Feature]`、`[Refactor]` 或 `[Docs]` 等标签开头；提交信息使用英文。

贡献采用 [Apache License 2.0](LICENSE) 许可证。
