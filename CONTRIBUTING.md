# Contributing to ForeRSI

English | [简体中文](CONTRIBUTING_zh.md)

## Local development

Follow the [README](README.md#install) to create the Python environment and install. An editable installation makes changes under `src/` available to the `fore-rsi` command.

## Configuration and execution

- [src/config.py](src/config.py) defines `Config`, `WorkflowConfig`, and `UIConfig`. Task and harness settings belong to `WorkflowConfig`; the named Herdr session belongs to `UIConfig`.
- [src/cli.py](src/cli.py) uses tyro to generate options from these dataclasses and return one complete `Config`. It also handles help and version output. Keep option names, defaults, types, and help with the configuration definitions.

Keep configuration as data. The CLI handles argument conversion; the workflow owns business validation, agent roles, scheduling, and management rules, harnesses execute agents, and Herdr provides the display. Avoid maintaining a second list of field types or a separate handler for each option.

The CLI reads the installed version through `importlib.metadata`; [pyproject.toml](pyproject.toml) is the source for package version metadata.

Keep English and Chinese documentation aligned. Update commands, examples, and configuration fields together. Keep credentials, private infrastructure details, and local runtime data outside the repository.

## Verify changes

```bash
fore-rsi --help
fore-rsi --version
python -m unittest discover -s tests
```

For CLI changes, check omitted values, individual and combined options, paths and session names containing spaces, and rejection of unknown arguments. Verify that workflow settings and UI settings land in the correct nested configuration, and that help and version exit successfully. The user-facing option reference is [docs/cli.md](docs/cli.md).

The tests cover parsing and command output without calling models. Record commands and actual results; keep tests and dependencies proportionate to the change.

## Pull requests

Keep changes focused and explain the problem, resulting behavior, and validation. Discuss major interface or responsibility changes with the maintainers first.

Use a short English PR title beginning with a tag such as `[Bugfix]`, `[Feature]`, `[Refactor]`, or `[Docs]`. Write commit messages in English.

Contributions are distributed under the [Apache License 2.0](LICENSE).
