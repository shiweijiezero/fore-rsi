# Contributing to ForeRSI

English | [简体中文](CONTRIBUTING_zh.md)

## Local development

Follow the [README](README.md#install) to create the Python environment and install. An editable installation makes changes under `src/` available to the `fore-rsi` command.

Declare ForeRSI options through Typer. Each configuration dataclass in `config.py` holds its parameters and defines a `handle()` method; `config_validator.py` checks their types. Give each function a clear responsibility and keep code readable. The workflow owns agent execution; Herdr provides the display. Business handlers are currently skeletons.

Keep English and Chinese documentation aligned. Update commands, examples, and configuration fields together. Keep credentials, private infrastructure details, and local runtime data outside the repository.

## Verify changes

These commands do not call a model or create agents:

```bash
fore-rsi --help
fore-rsi --version
fore-rsi --task task.md --workflow workflow_name --harness harness_name
fore-rsi --session session_name --detach
```

For CLI changes, check how options map to their dataclasses and handlers, values containing spaces, and rejection of subcommands, positional messages, and unknown options. The supported options are `--version`, `--help`, `--task`, `--workflow`, `--harness`, `--session`, and `--detach`. For dataclass changes, check invalid types supplied by Python callers.

The first two commands should succeed. The business examples currently exit nonzero with a not-implemented message. Use stand-in handlers to check dispatch without running a workflow. Record commands and actual results; keep tests and dependencies proportionate to the code.

## Pull requests

Keep changes focused and explain the problem, resulting behavior, and validation. Discuss major interface or responsibility changes with the maintainers first.

Use a short English PR title beginning with a tag such as `[Bugfix]`, `[Feature]`, `[Refactor]`, or `[Docs]`. Write commit messages in English.

Contributions are distributed under the [Apache License 2.0](LICENSE).
