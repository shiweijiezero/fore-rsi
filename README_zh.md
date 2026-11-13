<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">基于 Agent Team 的 RSI 框架：并行探索方案、执行工作、验证效果，并以反馈驱动持续改进。</p>

<p align="center"><a href="README.md">English</a> · 简体中文</p>

ForeRSI 是一个递归自我改进（Recursive Self-Improvement，RSI）框架，目标是把用户的目标与约束转化为持续、可验证的工作。Agent Team 探索不同方案、协作执行，并通过证据改进结果和工作方法。

长期优化与研究需要反复提出方案、实现、测量和比较结果，人往往还要不断交接工作、追踪进展、整理证据。ForeRSI 希望把持续迭代交给团队，让人专注于目标、约束和评估。

ForeRSI 采用去中心化协作理念：Agent 成员直接交流与共享进展，减少信息转发瓶颈，让独立工作并行推进。用户提供目标、材料、约束、可用资源与时间预算，workflow 据此组织团队。

Workflow 与 UI 各自承担明确职责：

- **Workflow** 负责任务输入，定义 Agent 角色、协作与交接规则、调度及任务推进方式，并选择执行 Agent 工作的后端 harness。
- **UI** 通过 Herdr 及其命名展示会话，向用户呈现团队进展与结果。

**当前阶段：** Python CLI 已能将参数解析为一份完整配置，workflow 执行与 Herdr UI 尚未接通。`--help` 和 `--version` 可用，任务命令目前会以一条尚未实现的提示退出；下文描述了系统的设计目标。

## 快速开始

### 安装

需要 Python 3.10 或更高版本。在仓库根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

使用 `fore-rsi` 时保持环境激活。运行 `fore-rsi --help` 查看可用参数。

### 提供任务

在 Markdown 文件中描述目标、约束、可用资源，以及判断结果所需的证据。仓库提供了一个 [SGLang 吞吐优化任务](tasks/inference-optimization/sglang-throughput.md)：

```bash
fore-rsi --task tasks/inference-optimization/sglang-throughput.md
```

只需提供需要设置的参数。`--workflow` 选择工作流，`--harness` 选择其执行后端，`--session` 指定 Herdr 展示会话的名称。各参数的含义见 [CLI 参考](docs/cli.md)。

## 持续改进循环

<p align="center">
  <img src="docs/assets/improvement-loop_zh.svg" alt="Agent Team 探索、执行与验证，Watchdog 监督协作，人类与 Agent 通过独立维护任务改进 ForeRSI。" width="564">
</p>

### 任务迭代

1. 探索方案：围绕目标与约束，分析已有材料、比较可行路径，形成可执行方案。
2. 执行工作：落实方案，产出代码、配置、分析、文档等可供验证的结果。
3. 验证效果：通过测试、测量、模拟或人工评阅取得证据，对照目标评估结果，决定保留或调整。

反馈回到探索与执行，指导下一轮改进。探索阶段也可以直接请求反馈。在这一工作流中，Coordinator 对接用户要求与任务进展，Checker 负责方案、工作和结论的阶段检查。

用户通过 Coordinator 补充材料、调整要求，以及暂停或恢复任务。

### Watchdog：改进团队协作

Watchdog（看门狗）定期巡查任务进展和团队协作，识别停滞、重复尝试与交接问题，并跟进相关成员的处理。它关注工作流能否有效推进任务，并总结可复用的经验。

### 人类与 Agent：改进 ForeRSI

人类与 Agent 根据任务经验和 Watchdog 反馈，共同改进工作流与支撑框架。协作规则、提示词、工具、调度、恢复机制及 harness 接入的改进作为独立维护任务开展，验证后再应用于后续工作。

## 设计你的定制 RSI 工作流

工作流定义团队角色、工具、执行步骤和交接规则，可以携带领域提示词、参考资料、工作方法和评价标准，并决定如何根据任务要求配置团队及其 harness。

同一套持续改进循环可以服务于不同领域：

- 软件开发：迭代实现功能或算法，通过测试与反馈改进。
- 推理优化：优化 Foretoken、SGLang、vLLM 等推理系统的代码、配置与运行表现。
- 科学研究：结合专业文献、数据、模拟和专家评阅组织工作。

## 贡献

欢迎参与 ForeRSI。开发与验证方式见[贡献指南](CONTRIBUTING_zh.md)，参考资料见[文档](docs/README.md)。

感谢所有通过代码、文档、想法和反馈帮助 ForeRSI 改进的[贡献者](https://github.com/shiweijiezero/fore-rsi/graphs/contributors)。

## 许可证

[Apache License 2.0](LICENSE)。
