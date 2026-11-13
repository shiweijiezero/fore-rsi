# Contributing to ForeRSI

English | [简体中文](CONTRIBUTING_zh.md)

## Local development

Follow the [README](README.md#install) to install Pi and create the Python environment. The editable install makes changes under `src/fore_rsi/` available to the `fore-rsi` command.

The current implementation is a small Python CLI that launches Pi. Keep code easy to read and give each function a clear responsibility. Use Python type annotations and the standard library where practical. Keep Pi-specific behavior separate from future task-management logic.

Keep English and Chinese documentation aligned. Update commands, examples, and their consumers together. Keep credentials, private infrastructure details, personal paths, and local execution data outside the repository.

## Verify changes

With the Python environment active and Pi installed, run:

```bash
fore-rsi --help
fore-rsi --version
fore-rsi -- --version
fore-rsi -- --help
```

These checks exercise the ForeRSI entry point and forwarding to Pi without calling a model. For argument-handling changes, also verify file paths containing spaces and the `--` separator. For process-handling changes, verify terminal interaction, cancellation, and exit status.

Record the commands and actual results relevant to the change. Add tests for important behavior or concrete regressions; keep new dependencies and test infrastructure proportionate to the code.

## Pull requests

Keep each change focused and explain the problem, resulting behavior, and validation. Discuss changes to public interfaces or module responsibilities with the maintainers before a larger implementation.

Use a short English title beginning with a change tag such as `[Bugfix]`, `[Feature]`, `[Refactor]`, or `[Docs]`. Write commit messages in English.

Contributions are distributed under the [Apache License 2.0](LICENSE). Verify the provenance and licensing of any material you include.
