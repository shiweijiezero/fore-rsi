<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">An RSI framework built on Agent Teams that autonomously explore approaches in parallel, execute work, and verify results, with feedback driving continuous improvement.</p>

<p align="center">
  English · <a href="README_zh.md">简体中文</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-446bcb?style=flat-square" alt="Apache-2.0 license"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-22.19%2B-446bcb?style=flat-square" alt="Node.js 22.19 or later"></a>
</p>

ForeRSI is a recursive self-improvement (RSI) framework built on Agent Teams. With objectives and constraints defined, teams can autonomously explore approaches in parallel, collaborate on execution, verify results, and refine their approaches and working methods through feedback.

ForeRSI uses decentralized collaboration: agents communicate directly and share progress, reducing information bottlenecks and enabling greater parallelism. If one member stalls or fails, others can continue with independent work. The terminal interface lets you provide materials, refine requirements, and manage tasks. The [documentation](docs/README.md) includes usage guides, a workflow tutorial, and API reference.

## Quick start

Requires Node.js 22.19.0 or later and npm.

### 1. Install

```bash
npm install -g github:shiweijiezero/fore-rsi
```

<details>
<summary>Install from a local checkout instead</summary>

From the ForeRSI repository root:

```bash
npm install
npm install -g .
```

</details>

<details>
<summary>Update or uninstall an installation</summary>

For a GitHub installation, repeat the GitHub installation command. For a local-source installation, run from that checkout:

```bash
git pull --ff-only
npm install
npm install -g .
```

Uninstall either installation with:

```bash
npm uninstall -g fore-rsi
```

</details>

### 2. Start and sign in

Start in the project directory you want to work with:

```bash
fore-rsi
```

Inside the terminal interface, use Pi's built-in commands:

```text
/login
/model
```

Use `/login` to choose a model provider and follow its subscription sign-in or API-key setup. Existing credentials in environment variables such as `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` also work.

`/model` selects the model for the Coordinator, the agent you speak with; `/thinking` adjusts its reasoning level.

Tools use the permissions of the operating-system user running ForeRSI, without per-call approval.

<details>
<summary>Use a network proxy</summary>

If your connection needs a proxy, set these variables before starting. Replace `http://127.0.0.1:7890` with your HTTP proxy's address:

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=localhost,127.0.0.1,::1
fore-rsi
```

</details>

### 3. Define objectives and start RSI

Specify the task's objectives, constraints, available resources, and time budget. Workflows define team roles and execution steps; the task description can specify which roles to use, their concurrency, runtimes, models, and reasoning levels. The team then autonomously advances the work.

> Optimize my SGLang service's throughput for the current workload while preserving answer quality and latency requirements. Use the designated GPU environment, work within a two-hour budget, and deliver a recommended configuration, measurements, and a summary of changes.
>
> Set concurrency to 4 Explorers investigating and comparing approaches, 4 Workers executing plans, and 2 Verifiers checking results. Keep the workflow's defaults for the other roles.

Use `--workflow` to choose the workflow for a new task. Omit it to use `default`; use `inference` for inference optimization. A resumed task keeps its saved workflow.

Use `--task` to submit a Markdown task file at startup. For example, run the [SGLang throughput task](tasks/inference-optimization/sglang-throughput.md) from the ForeRSI repository root:

```bash
fore-rsi --workflow inference \
  --task tasks/inference-optimization/sglang-throughput.md
```

Replace the path with your own task file as needed. Continue refining the requirements in the conversation, and use `@` to find and reference code, configuration, data, or other files. With only an objective, the team prepares an initial plan and begins the first iteration.

### 4. Name and resume sessions

Give a session a name when starting it:

```bash
fore-rsi --name "Inference throughput optimization"
```

Use `/name` in the conversation to rename it and `/session` to find its ID. Choose a resume command below; replace `ID` with the session ID:

```bash
fore-rsi --resume       # Open the session picker and search by name
fore-rsi --continue     # Continue the latest session for the current directory
fore-rsi --session ID   # Resume a session by ID
```

## The improvement loop

<p align="center">
  <img src="docs/assets/improvement-loop.svg" alt="Agent Teams advance the task loop, the Watchdog oversees collaboration, and humans and agents iterate on the Harness through separate maintenance tasks." width="564">
</p>

### Task iteration

1. Explore approaches: examine the available materials and possible paths against the objectives and constraints, then develop an actionable plan.
2. Execute the plan: carry out the work and produce code, configuration, analyses, documents, or other outputs ready for verification.
3. Verify results: gather feedback through tests, measurements, simulations, or human review, assess the outcome against the objectives and constraints, and decide what to retain or revise.

Feedback guides the next round of exploration and execution. The team can also request feedback during exploration.

The Coordinator connects user requirements with task progress, while the Checker reviews plans, work, and conclusions at each relevant stage. Use the conversation to add requirements, share materials, or pause, resume, and end a task.

### Watchdog: workflow oversight and improvement

The Watchdog periodically reviews task progress and team collaboration, identifies stalled work, repeated attempts, and handoff problems, and follows up with the members responsible. It focuses on the effectiveness of the overall workflow and captures reusable lessons.

### Humans and agents: Harness iteration

Humans and agents use task experience and Watchdog feedback to improve the Harness—the framework supporting the whole team, including collaboration, prompts, tools, scheduling, and recovery. These changes are developed as separate maintenance tasks and applied to subsequent tasks after design, implementation, and validation.

## Design your custom RSI workflow

A workflow defines team roles, tools, execution steps, and handoff rules. Reuse an existing workflow or develop one for the task.

Workflows can include domain prompts, reference materials, knowledge, methods, and evaluation criteria.

- Software development: implement features or algorithms and refine them through testing and feedback.
- Inference optimization: improve code, configuration, and runtime performance in systems such as Foretoken, SGLang, and vLLM.
- Scientific research: combine domain literature, data, simulations, and expert review.

## Contributing

Community contributions to ForeRSI are welcome. See the [contribution guide](CONTRIBUTING.md) for local development, code and documentation standards, and pull requests.

Thank you to all [contributors](https://github.com/shiweijiezero/fore-rsi/graphs/contributors) who help improve ForeRSI through code, documentation, ideas, and feedback.

## License

[Apache License 2.0](LICENSE).
