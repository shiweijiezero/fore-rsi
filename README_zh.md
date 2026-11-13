<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center"><a href="README.md">English</a> · 简体中文</p>

ForeRSI 用 Typer 解析命令行参数。每种配置有独立的 dataclass 和 `handle()` 处理函数，CLI 先校验配置，再调用对应函数。业务处理函数目前只有骨架，会明确提示操作尚未实现。Agent 的运行与调度由 workflow 负责，Herdr 负责展示。

## 安装

需要 Python 3.10 或更高版本。在仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

安装包含 Typer。使用 `fore-rsi` 时保持环境激活。

## 参数

```bash
fore-rsi --help
fore-rsi --version
fore-rsi --task task.md
fore-rsi --workflow workflow_name
fore-rsi --harness harness_name
fore-rsi --session session_name
fore-rsi --detach
```

只支持以下七个选项：

| 选项 | 解析结果 |
| --- | --- |
| `--version` | 显示版本并退出 |
| `--help` | 显示帮助并退出 |
| `--task FILE` | `TaskConfig(path: Path)` |
| `--workflow NAME` | `WorkflowConfig(name: str)` |
| `--harness NAME` | `HarnessConfig(name: str)` |
| `--session ID` | `SessionConfig(session_id: str)` |
| `--detach` | `DetachConfig(enabled=True)` |

只为用户提供的业务选项创建对应配置对象。解析保留相对路径，不读取文件；值中有空格时加引号。子命令、位置消息参数和未知选项会报错。所有参数均属于 ForeRSI，不透传给 Pi 或 Herdr。`--help` 和 `--version` 可用；调用业务处理函数目前会以非零状态退出，明确提示尚未实现。

## 代码结构

- [src/cli.py](src/cli.py)：`parse_args()` 构造并校验各项配置，`cli()` 调用对应处理函数，`main()` 启动 CLI。源码和 `--help` 中均有使用例子。
- [src/config.py](src/config.py)：各自独立的配置数据类，每个类用 `handle()` 定义对应操作。
- [src/config_validator.py](src/config_validator.py)：检查配置字段类型。

直接在 Python 中构造配置时，先调用 `validate_config()` 检查类型，再调用 `handle()`。具体操作逻辑及操作之间的依赖关系待设计确定后再补充。

验证步骤见[贡献指南](CONTRIBUTING_zh.md)，参考资料见[文档链接](docs/README.md)。

## 许可证

[Apache License 2.0](LICENSE)。
