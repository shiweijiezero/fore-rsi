<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">English · <a href="README_zh.md">简体中文</a></p>

ForeRSI aims to support recursive self-improvement through collaborating agents. The current version is a small Python command-line entry point that launches Pi and passes it user input or a Markdown task file.

Pi provides the terminal interface, model access, tools, and conversation history. Coordinator task management and Agent Team execution are not implemented in this version.

## Install

Requirements: Python 3.10 or later, Node.js 22.19.0 or later, and npm. ForeRSI uses Python's standard library at runtime; Pi is installed separately.

Install the Pi version used by this project:

```bash
npm install -g @earendil-works/pi-coding-agent@1.5.2
```

From the ForeRSI repository root, create a Python environment and install the command:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Keep this environment active when using `fore-rsi`. The `pi` command must also be available on `PATH`.

## Use

Open Pi's terminal interface in the directory where you want to work:

```bash
fore-rsi
```

Use Pi's `/login` to configure access, `/model` to choose a model, and `/thinking` to choose a reasoning level. Pi also supports provider API-key environment variables.

Provide an initial message:

```bash
fore-rsi "Review the requirements for improving inference throughput"
```

Or submit a Markdown file, optionally with a message. This example runs from the ForeRSI repository root:

```bash
fore-rsi --task tasks/inference-optimization/sglang-throughput.md "First explain the goal and constraints"
```

`--task FILE` passes the file to Pi as `@FILE`; relative paths use the current working directory. Quote paths containing spaces. The task file is conversation input, not a command to start an Agent Team.

ForeRSI handles `--task`, `-h` / `--help`, and `--version`. Other arguments are passed to Pi. Arguments after `--` are passed to Pi without ForeRSI option parsing:

```bash
fore-rsi --help             # ForeRSI options
fore-rsi --version          # ForeRSI version
fore-rsi -- --help          # Pi options
fore-rsi --model MODEL      # Choose a Pi model
fore-rsi --resume           # Open Pi's session picker
fore-rsi --continue         # Continue Pi's latest session for this directory
fore-rsi --session ID       # Open a Pi session by ID
```

Session commands restore Pi conversations. ForeRSI does not maintain a separate task database or workflow state. The earlier `--workflow` and `--harness` options have been removed.

## Develop

Start with [src/fore_rsi/cli.py](src/fore_rsi/cli.py). The Python entry point parses ForeRSI options and hands control to the installed Pi command. Package metadata and the `fore-rsi` entry point are defined in [pyproject.toml](pyproject.toml).

See the [contribution guide](CONTRIBUTING.md) for development checks and [documentation links](docs/README.md) for Pi's own guides.

## License

[Apache License 2.0](LICENSE).
