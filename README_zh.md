<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center"><a href="README.md">English</a> · 简体中文</p>

ForeRSI 希望通过 Agent 协作实现递归自我改进。当前版本是一个小型 Python 命令行入口，负责启动 Pi，并传入用户消息或 Markdown 任务文件。

终端界面、模型接入、工具和对话历史由 Pi 提供。当前版本尚未实现 Coordinator 任务管理和 Agent Team 执行。

## 安装

需要 Python 3.10 或更高版本、Node.js 22.19.0 或更高版本，以及 npm。ForeRSI 的 Python 运行代码只使用标准库；Pi 单独安装。

安装本项目使用的 Pi 版本：

```bash
npm install -g @earendil-works/pi-coding-agent@1.5.2
```

在 ForeRSI 仓库根目录创建 Python 环境并安装命令：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

使用 `fore-rsi` 时保持这个环境激活，并确保 `PATH` 中能找到 `pi` 命令。

## 使用

在希望处理的项目目录中打开 Pi 终端界面：

```bash
fore-rsi
```

使用 Pi 的 `/login` 配置访问凭据，`/model` 选择模型，`/thinking` 选择推理强度。Pi 也支持模型服务商的 API Key 环境变量。

直接提供初始消息：

```bash
fore-rsi "梳理提高推理吞吐的任务要求"
```

也可以提交 Markdown 文件，并附加消息。以下示例在 ForeRSI 仓库根目录运行：

```bash
fore-rsi --task tasks/inference-optimization/sglang-throughput.md "先解释目标和约束"
```

`--task FILE` 将文件作为 `@FILE` 传给 Pi；相对路径以当前工作目录为准。路径中有空格时加引号。任务文件是对话输入，不会据此启动 Agent Team。

ForeRSI 处理 `--task`、`-h` / `--help` 和 `--version`，其他参数交给 Pi。`--` 后的参数全部交给 Pi，不再解析为 ForeRSI 选项：

```bash
fore-rsi --help             # ForeRSI 选项
fore-rsi --version          # ForeRSI 版本
fore-rsi -- --help          # Pi 选项
fore-rsi --model MODEL      # 选择 Pi 模型
fore-rsi --resume           # 打开 Pi 会话选择器
fore-rsi --continue         # 继续当前目录最近的 Pi 会话
fore-rsi --session ID       # 按 ID 打开 Pi 会话
```

会话命令恢复的是 Pi 对话。ForeRSI 不维护独立的任务数据库或工作流状态，原有的 `--workflow` 和 `--harness` 选项已移除。

## 开发

从 [src/fore_rsi/cli.py](src/fore_rsi/cli.py) 开始阅读。这个 Python 入口解析 ForeRSI 选项，再把控制交给已安装的 Pi 命令。包信息和 `fore-rsi` 命令入口定义在 [pyproject.toml](pyproject.toml)。

开发检查见[贡献指南](CONTRIBUTING_zh.md)，Pi 使用指南见[文档链接](docs/README.md)。

## 许可证

[Apache License 2.0](LICENSE)。
