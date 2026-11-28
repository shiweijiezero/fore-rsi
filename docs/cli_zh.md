# 命令行参考

[English](cli.md) | 简体中文

## 启动与恢复

在项目目录运行 `fore-rsi` 或 `fore-rsi run`，进入终端界面后直接描述任务。两种写法接受相同的参数，可以选择工作流、指定 Agent 后端、命名会话，并提供任务文件：

```bash
fore-rsi --session sglang-throughput \
  --task tasks/inference-optimization/sglang-throughput.md
```

示例使用 ForeRSI 仓库根目录下的任务文件。在没有交互终端的脚本中，传入 `--task FILE` 即可运行同一套工作流。命令不打开前台界面，等工作流结束后返回；会话和结果保留，仍可查看。

启动参数：

- `--workflow NAME` 按名称选择已注册的工作流，省略时使用内置的 `default`。
- `--harness NAME` 选择运行 Agent 的原生 CLI：`pi`、`codex` 或 `claude`（Claude Code）。新会话默认使用 Pi，按名称恢复时沿用原来的后端。
- `--model MODEL` 只指定入口 Agent（默认工作流的 Coordinator）使用的模型。名称沿用所选后端的写法；省略时由后端选择。
- `--effort LEVEL` 设置该 Agent 的推理强度，可以单独使用，也可以搭配模型，例如 `fore-rsi --harness claude --model sonnet --effort high`。可用档位取决于后端和模型，省略时沿用原生设置。
- `--max-attempts N` 设置每次工具提交的尝试上限，含首次，默认 3 次。默认工作流每轮最多提出 N 个方向；每个工作组的结束审核跨轮累计，最多尝试 N 次。
- `--session NAME` 指定要创建或恢复的 ForeRSI 会话名称。
- `--task FILE` 提供 Markdown 任务文件。省略时，在对话中直接描述任务。
- `--cache-dir PATH` 指定新会话的工作流存储目录，默认 `./cache`。相对路径以当前项目的 Git 仓库根目录为基准；不在 Git 仓库中时使用启动目录，绝对路径直接使用。工作流数据保存在其中的 `workflows/` 子目录。当前用户的每个会话名称绑定首次确定的存储位置，之后即使换目录启动，也沿用原位置。

值中有空格时加引号。任务文件的相对路径以工作目录为基准。要调整要求，直接在原对话中告诉协调者即可。发生变化的任务会保存为新的版本文件；之前提交的任务版本仍可查阅，恢复会话时使用最新版本。

例如，可以告诉协调者：「三名实验者共用八张 GPU，每 20 分钟巡查一次进展。」调整人数后，新实验会等当前实验结束、团队重新分好资源再开始。将实验者配额调为零可以暂停接单。

使用 `--harness claude` 时，工作流消息直接进入成员当前的 Claude Code 对话，不占用你正在编辑的输入框。如果用 `Esc` 手动中断回合，Claude Code 会暂停接受插件派工；在该终端发一条消息后，即可再次派工。

恢复时使用相同的 `--session` 名称，无需重复提交 `--task`。每个 Agent 都会从 `<cache-dir>/workflows/<session>/harnesses/` 下打开自己的原生对话记录。要换后端，请另起一个会话名。退出快捷键见[退出与恢复](../README_zh.md#退出与恢复)。

`fore-rsi --help` 显示可用参数，`fore-rsi --version` 显示安装版本，输出后退出。

## 列出会话

按保存的存储位置汇总已登记的工作流，以及本地终端会话：

```bash
fore-rsi list
```

`WORKFLOW` 显示登记的工作流名称。`WORKFLOW_STATE` 保留已记录的 `completed`、`stopped` 和 `failed` 结果；对于 `running` 记录，会核对本机宿主进程的 PID 和创建时间。同一进程仍存活时显示 `running`，宿主已退出或 PID 已被复用时显示 `interrupted`，缺少身份信息或无法查询进程信息时显示 `unknown`。查询结果不会回写记录文件。

`TERMINAL_SERVER` 独立显示终端服务器的 `running`、`stopped` 或 `unavailable` 状态。缺少某一侧记录，或工作流记录尚未保存状态时，显示 `—`。

查询、停止和删除已有会话无需再提供 `--cache-dir`。尚未绑定存储位置的工作流记录，仍从当前项目的默认缓存或 `--cache-dir` 指定的目录查找。

使用列表中的名称运行 `fore-rsi --session NAME` 即可恢复会话。`list` 不接受 `--session`。

## 查看工作进展

点击侧栏顶部的「工作进展」可切回进展页。工作区下先列 `global` 组，组内第一项是当前工作流的入口 Agent，显示该 Agent 自己的名字。也可以在另一个终端单独打开进展页：

```bash
fore-rsi workprogress --session sglang-throughput
```

单独打开的进展页可按 `q` 或 `Esc` 退出，不影响工作流。终端里只能关闭自己创建的窗格，工作流的进展页和 Agent 窗格会保留。该命令使用会话保存的位置，不接受 `--cache-dir`。

点选探索节点可查看该项的实验结果和详细记录。旁边的巡查报告按发布顺序串成一条链，点选节点即可阅读对应的报告。

## 停止会话

停止会话并保留数据：

```bash
fore-rsi stop --session sglang-throughput
```

`stop` 必须提供 `--session NAME`，并自动使用保存的存储位置。命令会等待工作流收尾，再停止终端服务器，保留会话数据与存储绑定。重复停止已停止的会话会成功返回；名称不存在时会报错。默认会话也可以通过 `--session default` 停止。Windows 上需先退出运行中的工作流。

## 删除会话

停止并删除命名会话：

```bash
fore-rsi delete --session sglang-throughput
```

`delete` 必须提供 `--session NAME`。命令按会话绑定的存储位置找到工作流，先停止并等待清理完成，再停止并删除终端会话，最后删除工作流目录及其存储绑定。只有工作流或只有终端记录的会话也可以删除。停止失败时，命令会报告错误并保留工作流缓存与绑定。

删除会话会一并删除其中各 Agent 的原生对话记录。默认会话 `default`、会话目录之外的项目文件，以及原生 CLI 在 ForeRSI 之外保存的个人配置和历史记录都会保留。Windows 上需先退出运行中的工作流，再删除会话。

`--workflow`、`--harness`、`--model`、`--effort`、`--max-attempts` 和 `--task` 仅用于 `run`。`--cache-dir` 用于 `run`、`list`、`stop` 和 `delete`。

## 诊断日志

Python 诊断日志默认以 `INFO` 级别和文本格式写入 stderr。可以提高详细程度，或在 stderr 输出之外追加保存 JSON 日志：

```bash
fore-rsi --log-level DEBUG
fore-rsi --log-format json --log-file logs/fore-rsi.jsonl
```

`--log-format` 同时作用于 stderr 和指定文件。文件以 UTF-8 追加写入，缺少的父目录会自动创建；独立运行的进程应使用不同文件。帮助和版本命令不会创建日志文件，正式命令结果仍输出到 stdout。

Agent 对话和原生终端日志沿用各自的记录路径。
