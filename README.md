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

ForeRSI uses decentralized collaboration: agents communicate directly and share progress, reducing information bottlenecks and enabling greater parallelism. If one member stalls or fails, others can continue with independent work. The terminal and web interfaces let you provide materials, refine requirements, and manage tasks.

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

### 2. Deploy and start

Select the team's default agent runtime with `--harness` (`pi`, `codex`, or `claude-code`) and its authentication method with `--auth` (`subscription` or `api-key`). Choose one of these startup options; replace `your-api-key` with your OpenAI API key in the API-key example.

```bash
# Pi with subscription sign-in, terminal interface
fore-rsi --harness pi --auth subscription

# Pi with an OpenAI API key, terminal interface
export OPENAI_API_KEY="your-api-key"
fore-rsi --harness pi --auth api-key

# Pi with subscription sign-in, web interface
fore-rsi --harness pi --auth subscription --ui web
```

Subscription mode follows the selected runtime's sign-in flow. API-key mode reads the model provider's environment variable; for example, Anthropic uses `ANTHROPIC_API_KEY`. Use `--harness codex` or `--harness claude-code` to select another runtime. `--ui web` selects the browser interface for either authentication method.

After startup, choose models, reasoning levels, and an execution environment in the terminal or web interface. Individual roles can override the team's default runtime, authentication method, model, and reasoning level.

### 3. Define objectives and start RSI

Specify the task's objectives, constraints, available resources, and time budget. Plugins provide the roles and workflow; the task description can specify which roles to use, their concurrency, runtimes, models, and reasoning levels. The team then autonomously advances the work.

```bash
fore-rsi
# Choose the terminal or web interface, runtime, and authentication method,
# then enter the task in the conversation.
```

> Optimize my SGLang service's throughput for the current workload while preserving answer quality and latency requirements. Use the designated GPU environment, work within a two-hour budget, and deliver a recommended configuration, measurements, and a summary of changes.
>
> Set concurrency to 4 Explorers investigating and comparing approaches, 4 Workers executing plans, and 2 Verifiers checking results. Keep the plugin's defaults for other roles and use the runtimes, models, and reasoning levels selected at startup.

Attach code, configuration, papers, data, or previous results. You can also submit just an objective and let the team prepare an initial plan and begin the first iteration.

<details>
<summary>Start from a Markdown task</summary>

Run the SGLang throughput example from the local repository root:

```bash
# Terminal
fore-rsi run ./tasks/inference_domain/sglang-throughput.md --harness pi --auth subscription

# Web
fore-rsi run ./tasks/inference_domain/sglang-throughput.md --harness pi --auth subscription --ui web
```

The terminal and web interfaces also let you choose a built-in example or your own task file.

</details>

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

Define team roles, tools, workflow steps, and handoff rules through plugins. Install existing plugins or develop your own, then combine and reuse them across tasks.

Plugins can include domain prompts, reference materials, knowledge, methods, and evaluation criteria. Specify each role's concurrency, runtime, model, and reasoning level in the task description.

- Software development: implement features or algorithms and refine them through testing and feedback.
- Inference optimization: improve code, configuration, and runtime performance in systems such as Foretoken, SGLang, and vLLM.
- Scientific research: combine domain literature, data, simulations, and expert review.

## Contributing

Community contributions to ForeRSI are welcome. See the [contribution guide](CONTRIBUTING.md) for local development, code and documentation standards, and pull requests.

Thank you to all [contributors](https://github.com/shiweijiezero/fore-rsi/graphs/contributors) who help improve ForeRSI through code, documentation, ideas, and feedback.

## License

[Apache License 2.0](LICENSE).
