<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">An RSI framework built around Agent Teams: explore approaches in parallel, execute work, verify results, and improve through feedback.</p>

<p align="center">English · <a href="README_zh.md">简体中文</a></p>

ForeRSI is a recursive self-improvement (RSI) framework for turning objectives and constraints into sustained, verifiable work. Its goal is to let Agent Teams explore alternatives, collaborate on execution, and use evidence to improve both their results and their working methods.

Long-running optimization and research require repeated rounds of proposing approaches, implementing them, measuring outcomes, and comparing evidence. People often spend much of that time coordinating handoffs, tracking progress, and collecting results. ForeRSI aims to give the team responsibility for that ongoing iteration, so people can focus on objectives, constraints, and evaluation.

The design favors decentralized collaboration: agents communicate directly and share progress, reducing information bottlenecks so independent work can advance in parallel. Users provide objectives, materials, constraints, resources, and time budgets; a workflow organizes the team around them.

The workflow and UI have distinct responsibilities:

- **Workflow** owns task input and defines agent roles, collaboration and handoff rules, scheduling, and task progress. It selects the harness, the execution backend through which agents carry out work.
- **UI** shows the team's progress and results to users through Herdr and its named display sessions.

**Current stage:** the Python CLI parses options into one configuration; workflow execution and the Herdr UI are not connected yet. `--help` and `--version` work, while task commands currently exit with a single not-implemented message; the following sections describe the intended system.

## Quick start

### Install

Requires Python 3.10 or later. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Keep this environment active when using `fore-rsi`. View the available options with `fore-rsi --help`.

### Provide a task

Describe the objective, constraints, available resources, and evidence needed to judge the result in a Markdown file. The [SGLang throughput task](tasks/inference-optimization/sglang-throughput.md) is one example:

```bash
fore-rsi --task tasks/inference-optimization/sglang-throughput.md
```

Only supply the options you need. `--workflow` selects a workflow, `--harness` selects its execution backend, and `--session` names a Herdr display session. See the [CLI reference](docs/cli.md) for their meanings.

## The improvement loop

<p align="center">
  <img src="docs/assets/improvement-loop.svg" alt="Agent Teams explore, execute, and verify; the Watchdog oversees collaboration; humans and agents improve ForeRSI through separate maintenance tasks." width="564">
</p>

### Task iteration

1. Explore approaches: examine the available materials and possible paths against the objectives and constraints, then develop an actionable plan.
2. Execute the plan: carry out the work and produce code, configuration, analyses, documents, or other outputs ready for verification.
3. Verify results: gather evidence through tests, measurements, simulations, or human review, assess the outcome against the objectives, and decide what to retain or revise.

Feedback guides the next round of exploration and execution. The team can also seek feedback while exploring an approach. In this workflow, the Coordinator connects user requirements with task progress, while the Checker reviews plans, work, and conclusions at relevant stages.

Through the Coordinator, users can add materials, refine requirements, and pause or resume the task.

### Watchdog: improve team collaboration

The Watchdog periodically reviews progress and collaboration, identifies stalled work, repeated attempts, and handoff problems, and follows up with the members responsible. It assesses how effectively the workflow advances the task and captures reusable lessons.

### Humans and agents: improve ForeRSI

Humans and agents use task experience and Watchdog feedback to improve workflows and the supporting framework. Changes to collaboration rules, prompts, tools, scheduling, recovery, and harness integration are developed as separate maintenance tasks, validated, and then applied to subsequent work.

## Design a custom RSI workflow

A workflow defines team roles, tools, execution steps, and handoff rules. It can carry domain prompts, reference materials, methods, and evaluation criteria, and determine how task requirements configure the team and its harnesses.

The same improvement loop can serve different kinds of work:

- Software development: implement features or algorithms and refine them through testing and feedback.
- Inference optimization: improve code, configuration, and runtime performance in systems such as Foretoken, SGLang, and vLLM.
- Scientific research: combine domain literature, data, simulations, and expert review.

## Contributing

Contributions to ForeRSI are welcome. See the [contribution guide](CONTRIBUTING.md) for development and validation, and the [documentation](docs/README.md) for references.

Thank you to all [contributors](https://github.com/shiweijiezero/fore-rsi/graphs/contributors) who help improve ForeRSI through code, documentation, ideas, and feedback.

## License

[Apache License 2.0](LICENSE).
