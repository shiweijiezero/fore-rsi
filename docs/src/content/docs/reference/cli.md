---
title: CLI reference
description: ForeRSI startup options and the Pi options available through the same command.
---

```text
fore-rsi [options] [pi-args...]
```

With a terminal attached, `fore-rsi` opens Pi's interactive interface. Options can be combined in any order before `--`.

## ForeRSI options

- `--task <file>` submits a task file as the initial input. Relative paths use the current working directory. It has no default value.
- `--workflow <name>` selects the workflow for a new task. The built-in choices are `default` and `inference`; the default is `default`. A resumed task keeps its saved workflow.
- `--harness <name>` selects the agent runtime. The supported value and default are `pi`.
- `-h`, `--help` displays ForeRSI help.
- `-V`, `--version` displays the ForeRSI package version.

For example, from the ForeRSI repository root:

```bash
fore-rsi --workflow inference \
  --name "SGLang throughput" \
  --task tasks/inference-optimization/sglang-throughput.md
```

## Pi options

Pi handles the remaining options. Common choices include:

- `--model <pattern>` and `--provider <name>` for model selection.
- `--thinking <level>` for reasoning intensity.
- `--name <name>` for the session display name.
- `--resume` for the session picker, `--continue` for the latest local session, and `--session <path|id>` for a specific session.
- `--print` for a one-shot response, `--mode json` for JSON events, and `--mode rpc` for Pi's RPC interface.

Run the installed version's complete help with:

```bash
fore-rsi -- --help
```

The first `--` ends ForeRSI option parsing, so the following `--help` reaches Pi. Pi also provides commands such as `auth`, `install`, and `list`; their behavior is described in the [Pi command-line reference](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md).

## In the conversation

Use `/login` to sign in, `/model` to choose the conversation model, `/thinking` to set its reasoning level, `/name` to rename the session, and `/session` to inspect it. Type `/` to browse Pi's available commands.
