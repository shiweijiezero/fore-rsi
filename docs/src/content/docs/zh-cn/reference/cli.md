---
title: 命令行参考
description: ForeRSI 启动参数，以及通过同一命令使用的 Pi 原生参数。
---

```text
fore-rsi [options] [pi-args...]
```

在终端中执行 `fore-rsi` 会打开 Pi 交互界面。`--` 之前的选项可以按任意顺序组合。

## ForeRSI 参数

- `--task <file>`：将任务文件作为初始输入提交。相对路径以当前工作目录为基准，无默认值。
- `--workflow <name>`：为新任务选择工作流。目前内置 `default` 和 `inference`，默认使用 `default`。恢复任务时沿用已保存的工作流。
- `--harness <name>`：选择 Agent 运行后端。目前支持 `pi`，默认值也是 `pi`。
- `-h`、`--help`：显示 ForeRSI 帮助。
- `-V`、`--version`：显示 ForeRSI 包版本。

例如，在 ForeRSI 仓库根目录执行：

```bash
fore-rsi --workflow inference \
  --name "SGLang 吞吐优化" \
  --task tasks/inference-optimization/sglang-throughput.md
```

## Pi 参数

其余选项交给 Pi 处理，常用参数包括：

- `--model <pattern>`、`--provider <name>`：选择模型及服务商。
- `--thinking <level>`：设置推理强度。
- `--name <name>`：设置会话显示名称。
- `--resume`：打开会话选择器；`--continue`：继续当前目录最近的会话；`--session <path|id>`：打开指定会话。
- `--print`：输出一次回答后退出；`--mode json`：输出 JSON 事件；`--mode rpc`：使用 Pi 的 RPC 接口。

查看已安装版本支持的完整参数：

```bash
fore-rsi -- --help
```

第一个 `--` 结束 ForeRSI 参数解析，使后面的 `--help` 交给 Pi。Pi 也提供 `auth`、`install`、`list` 等子命令，具体用法见 [Pi 命令行参考](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md)。

## 对话内命令

通过 `/login` 登录，`/model` 选择对话模型，`/thinking` 设置推理强度，`/name` 修改会话名，`/session` 查看会话信息。在输入框中键入 `/` 可以浏览 Pi 提供的命令。
