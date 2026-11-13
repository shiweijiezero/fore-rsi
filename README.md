<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">English · <a href="README_zh.md">简体中文</a></p>

ForeRSI uses Typer to parse command-line options. Each kind of configuration has its own dataclass and `handle()` method. The CLI validates the configurations before calling their handlers. Business handlers are currently skeletons: they report that their operation is not implemented. The workflow will own agent execution and scheduling, while Herdr provides the display.

## Install

Requires Python 3.10 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Installation includes Typer. Keep the environment active when using `fore-rsi`.

## Options

```bash
fore-rsi --help
fore-rsi --version
fore-rsi --task task.md
fore-rsi --workflow workflow_name
fore-rsi --harness harness_name
fore-rsi --session session_name
fore-rsi --detach
```

Only these seven options are supported:

| Option | Parsed value |
| --- | --- |
| `--version` | Print the version and exit |
| `--help` | Print help and exit |
| `--task FILE` | `TaskConfig(path: Path)` |
| `--workflow NAME` | `WorkflowConfig(name: str)` |
| `--harness NAME` | `HarnessConfig(name: str)` |
| `--session ID` | `SessionConfig(session_id: str)` |
| `--detach` | `DetachConfig(enabled=True)` |

Only supplied business options create configuration objects. Parsing preserves relative paths without reading files. Quote values containing spaces. Subcommands, positional messages, and unknown options are rejected. All options belong to ForeRSI; parameters are not forwarded to Pi or Herdr. `--help` and `--version` work; invoking a business handler currently exits with an explicit not-implemented error.

## Code structure

- [src/cli.py](src/cli.py): `parse_args()` constructs and validates configurations; `cli()` calls their handlers; `main()` starts the CLI. Examples appear in both the source and `--help`.
- [src/config.py](src/config.py): separate parameter dataclasses, each with a `handle()` method for its operation.
- [src/config_validator.py](src/config_validator.py): checks configuration field types.

When constructing configuration from Python, call `validate_config()` to check its types before `handle()`. Operation logic and any dependencies between operations will be added after their design is agreed.

See the [contribution guide](CONTRIBUTING.md) for checks and [documentation links](docs/README.md) for references.

## License

[Apache License 2.0](LICENSE).
