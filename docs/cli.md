# CLI reference / 命令行参考

## English

`fore-rsi` accepts options for one workflow invocation and its UI. All business options are optional; specify only the values needed for the task.

| Option | Meaning |
| --- | --- |
| `--task FILE` | Markdown task file for the workflow. |
| `--workflow NAME` | Workflow selection. |
| `--harness NAME` | Agent execution backend for the workflow. |
| `--session NAME` | Named Herdr display session. |
| `--help` | Show available options and exit. |
| `--version` | Show the installed ForeRSI version and exit. |

For example, from the repository root:

```bash
fore-rsi --task tasks/inference-optimization/sglang-throughput.md
```

Quote values containing spaces. Relative task paths are relative to the working directory. The parser preserves omitted values as unspecified; the workflow entry point will resolve workflow and harness defaults. No built-in workflow names are currently registered.

`--session` follows Herdr's named-session meaning. It identifies the display session; workflow execution state and task recovery belong to the workflow. See the [Herdr CLI reference](https://herdr.dev/tui/docs/cli-reference/) for Herdr's own session commands.

## 中文

`fore-rsi` 接收一次 workflow 调用及其 UI 的参数。所有业务参数都可以省略，按任务需要设置即可。

| 选项 | 含义 |
| --- | --- |
| `--task FILE` | 提供给 workflow 的 Markdown 任务文件。 |
| `--workflow NAME` | 选择工作流。 |
| `--harness NAME` | 选择 workflow 的 Agent 执行后端。 |
| `--session NAME` | Herdr 展示会话的名称。 |
| `--help` | 显示可用参数并退出。 |
| `--version` | 显示已安装的 ForeRSI 版本并退出。 |

例如，在仓库根目录执行：

```bash
fore-rsi --task tasks/inference-optimization/sglang-throughput.md
```

值中有空格时加引号。任务文件的相对路径以工作目录为基准。省略的值在解析后仍保持未指定，workflow 与 harness 的默认选择将由工作流入口处理。目前没有注册内置的工作流名称。

`--session` 沿用 Herdr 的命名会话语义，用于标识展示会话；workflow 的执行状态与任务恢复由工作流负责。Herdr 自身的会话命令见 [Herdr CLI 参考](https://herdr.dev/tui/docs/cli-reference/)。
