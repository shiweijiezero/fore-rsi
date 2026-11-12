<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">基于 Agent Team 的 RSI 框架，自主并行探索方案、执行工作、验证效果，并以反馈驱动持续改进。</p>

<p align="center">
  <a href="README.md">English</a> · 简体中文
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-446bcb?style=flat-square" alt="Apache-2.0 许可证"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/Node.js-22.19%2B-446bcb?style=flat-square" alt="Node.js 22.19 或更高版本"></a>
</p>

ForeRSI 是一个基于 Agent Team 的递归自我改进（Recursive Self-Improvement，RSI）框架。设定目标与约束后，Agent Team 可以自主并行探索方案、协作执行工作、验证效果，并根据反馈调整方案和工作方法，持续推进迭代。

ForeRSI 采用去中心化协作理念：Agent 成员直接交流与共享进展，减少信息转发瓶颈，提升并行度；单个成员出现异常时，其他独立工作仍可继续推进。

用户可以通过终端或 Web 界面提供材料、调整要求和管理任务。

## 快速开始

需要 Node.js 22.19.0 或更高版本，以及 npm。

### 1. 安装

```bash
npm install -g github:shiweijiezero/fore-rsi
```

<details>
<summary>也可以从本地源码安装</summary>

在 ForeRSI 仓库根目录执行：

```bash
npm install
npm install -g .
```

</details>

<details>
<summary>更新或卸载安装版</summary>

从 GitHub 安装时，重新执行对应的安装命令即可更新。从本地源码安装时，在原仓库目录执行：

```bash
git pull --ff-only
npm install
npm install -g .
```

两种安装方式均使用以下命令卸载：

```bash
npm uninstall -g fore-rsi
```

</details>

### 2. 部署与启动

通过 `--harness` 选择团队默认使用的 Agent 运行后端（`pi`、`codex` 或 `claude-code`），通过 `--auth` 选择认证方式（`subscription` 或 `api-key`）。按需要选择一种启动方式；API Key 示例中的 `your-api-key` 替换为自己的 OpenAI API Key。

```bash
# Pi 后端，订阅登录，终端界面
fore-rsi --harness pi --auth subscription

# Pi 后端，OpenAI API Key，终端界面
export OPENAI_API_KEY="your-api-key"
fore-rsi --harness pi --auth api-key

# Pi 后端，订阅登录，Web 界面
fore-rsi --harness pi --auth subscription --ui web
```

订阅模式通过所选后端的登录流程认证；API Key 模式读取模型服务的环境变量，例如 Anthropic 使用 `ANTHROPIC_API_KEY`。切换后端时使用 `--harness codex` 或 `--harness claude-code`。两种认证方式都可以添加 `--ui web` 使用浏览器界面。

启动后，在终端或 Web 界面选择模型、推理强度与执行环境。各角色可以在团队默认设置的基础上，分别配置后端、认证方式、模型和推理强度。

### 3. 设定目标并进行 RSI 工作

在对话中设定任务目标、约束、可用资源与时间预算。插件提供团队角色和执行流程，本次任务的角色组成、并行数量、后端、模型与推理强度可以在任务要求中指定。提交后由团队自主推进。

```bash
fore-rsi
# 随后在命令行中选择，终端/web，harness后端，以及订阅/API，在对话中输入任务：
```

> 优化 SGLang 服务在当前工作负载下的吞吐量，保持回答质量和延迟要求。使用指定的 GPU 环境，预算两小时，交付推荐配置、测量结果与改动说明。
>
> 团队并行度设置为：4 个 Explorer 探索和比较方案，4 个 Worker 执行方案，2 个 Verifier 负责验证。其他角色沿用插件预设，后端、模型与推理强度沿用启动时的设置。

支持附加代码、配置、论文、数据或历史结果，也支持仅提交目标，由团队自主准备初始方案并开始第一轮工作。

<details>
<summary>从 Markdown 任务启动</summary>

在本地仓库根目录运行 SGLang 吞吐量任务示例：

```bash

# 终端
fore-rsi run ./tasks/inference_domain/sglang-throughput.md --harness pi --auth subscription

# Web
fore-rsi run ./tasks/inference_domain/sglang-throughput.md --harness pi --auth subscription --ui web
```

也可以在终端或 Web 界面中选择内置示例或自己的任务文件。

</details>

## 持续改进循环

<p align="center">
  <img src="docs/assets/improvement-loop_zh.svg" alt="Agent Team 推进任务循环，Watchdog 监督并改进协作，人类与 Agent 通过独立维护任务迭代整体 Harness。" width="564">
</p>

### 任务迭代

1. 探索方案：围绕目标与约束，分析已有材料、比较可行路径，形成可执行方案。
2. 执行工作：落实方案，产出代码、配置、分析、文档等可供验证的结果。
3. 验证效果：通过测试、测量、模拟或人工评阅取得反馈，对照目标与约束评估结果，决定保留或调整。

反馈回到探索与执行，指导下一轮改进。探索阶段也可以直接请求反馈。

Coordinator 对接用户要求与任务进展，Checker 负责方案、工作和结论的阶段检查。用户可以通过对话补充要求与材料，暂停、继续或结束任务。

### Watchdog：监督与改进工作流

Watchdog（看门狗）定期巡查任务进展和团队协作，识别停滞、重复尝试与交接问题，向相关成员提出调整建议并跟进处理。它关注整个流程是否顺畅、有效，并总结可复用的工作经验。

### 人类与 Agent：迭代整体 Harness

人类与 Agent 根据任务经验和 Watchdog 反馈，共同改进 Harness——支撑整个团队运行的框架，包括协作流程、提示词、工具接入、调度与恢复机制。Harness 迭代作为独立维护任务开展，完成设计、实现与验证后，再将改进应用于后续任务。

## 设计你的定制 RSI 工作流

通过插件定义团队角色、工具、工作步骤和交接规则。可以安装已有插件，也可以编写自己的插件，并按任务组合和复用。

插件可以携带领域的提示词、参考资料、专业知识、工作方法和评价标准。各角色的并行数量、后端、模型与推理强度则可以在任务说明中指定。

- 软件开发：迭代实现功能或算法，通过测试与反馈改进。
- 推理优化：优化 Foretoken、SGLang、vLLM 等推理系统的代码、配置与运行表现。
- 科学研究：结合专业文献、数据、模拟和专家评阅组织工作。

## 贡献

欢迎社区开发者参与 ForeRSI。开发环境、代码与文档规范、Pull Request 流程见[贡献指南](CONTRIBUTING_zh.md)。

感谢所有通过代码、文档、想法和反馈帮助 ForeRSI 改进的[贡献者](https://github.com/shiweijiezero/fore-rsi/graphs/contributors)。

## 许可证

[Apache License 2.0](LICENSE)。
