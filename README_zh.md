<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/fore-rsi-dark.png">
    <img src="docs/assets/fore-rsi-light.png" alt="ForeRSI" width="720">
  </picture>
</h1>

<p align="center">基于 Agent Team 的 RSI 框架，自主并行探索方案、执行工作、开展实验，并以反馈驱动持续改进。</p>

<p align="center"><a href="README.md">English</a> · 简体中文</p>

ForeRSI 是一个基于 Agent Team 的递归自我改进（Recursive Self-Improvement，RSI）框架。设定目标与约束后，Agent Team 可以自主并行探索方案、协作执行工作、开展实验，并根据反馈调整方案和工作方法，持续推进迭代。

ForeRSI 采用去中心化协作理念：Agent 成员直接交流与共享进展，减少信息转发瓶颈，提升并行度，让独立工作持续推进。

用户提供目标、材料、约束、可用资源与时间预算，工作流据此组织团队。命令行用法与开发指南见[文档](docs/README.md)。

## 快速开始

### 安装

使用 [uv](https://docs.astral.sh/uv/) 安装，自动准备 Python 3.13 运行环境：

```bash
uv tool install --python 3.13 fore-rsi
```

<details>
<summary>使用 pip 安装</summary>

在 Python 3.13 或更高版本的环境中执行：

```bash
pip install fore-rsi
```

</details>

<details>
<summary>从源码进行可编辑安装</summary>

源码构建需要 [Rustup](https://rustup.rs/) 和系统 C/C++ 构建工具。安装时会自动准备所需的 Rust 与 Zig 工具链，并编译内置终端。

在 ForeRSI 仓库根目录执行，uv 会自动管理 Python 环境：

```bash
uv tool install --python 3.13 -e .
```

可编辑安装直接引用本地 Python 源码，无需激活虚拟环境。

也可以用 pip 安装到虚拟环境。macOS 的后台终端需要从虚拟环境启动，因此请把环境放在桌面等受保护目录之外；源码仓库不需要移动。

```bash
python3.13 -m venv "$HOME/.venvs/fore-rsi"
source "$HOME/.venvs/fore-rsi/bin/activate"
pip install -e .
```

运行 `fore-rsi` 前，先激活这个环境。

</details>

<details>
<summary>更新或卸载</summary>

使用 uv 安装发布版时：

```bash
# 更新
uv tool upgrade fore-rsi

# 卸载
uv tool uninstall fore-rsi
```

使用 pip 安装发布版时：

```bash
# 更新
pip install --upgrade fore-rsi

# 卸载
pip uninstall fore-rsi
```

源码安装的依赖、原生代码或构建配置变更后，在仓库根目录重新安装：

```bash
uv tool install --python 3.13 --reinstall -e .
```

使用 pip 可编辑安装时，在原环境中执行 `pip install -e .`。卸载命令与发布版相同。

更新或卸载前先[退出程序](#退出与恢复)。更新后按会话名称恢复运行，即可使用新版本。卸载会保留已保存的会话数据。

</details>

<details>
<summary>使用网络代理</summary>

需要代理时，在安装或运行命令前设置以下变量。将示例中的 `http://127.0.0.1:7890` 替换为实际 HTTP 代理地址：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=localhost,127.0.0.1,::1
```

</details>

### 选择工作流并启动

在希望处理的项目目录中启动。内置的 `default` 工作流会打开协调者的原生 Pi 对话。给会话起一个名字，之后就可以按名称恢复：

```bash
fore-rsi --session sglang-throughput
```

ForeRSI 优先复用已安装的 CLI，缺失时调用所选后端的官方安装器。按安装器提示准备依赖；需要认证时，使用原生工具的登录流程。

也可以根据任务需要[定制 RSI 工作流](#设计你的定制-rsi-工作流)，调整团队角色、工具、执行步骤与评价标准。参数说明见 [CLI 参考](docs/cli_zh.md)，或运行 `fore-rsi --help`。

### 提供任务

可以直接在终端对话中描述任务，也可以在启动时通过 `--task` 传入 Markdown 文件。

进入界面后，向 Coordinator（协调者）说明目标、约束、可用资源、时间预算与预期交付。例如：

> 优化 SGLang 上的 BF16 Qwen3.5-35B-A3B，在请求并发为 1 和 16 时提高输出 token 吞吐量、降低每个输出 token 的耗时（TPOT），并保持回答质量。单机最多使用两张 NVIDIA A100，时间预算为 24 小时。
>
> 团队并行度：4 个 Explorer、4 个 Worker、2 个 Experimenter。

如果已经写好任务文件，可以在启动时一并提供。例如，在 ForeRSI 仓库根目录运行 [SGLang 吞吐优化任务](tasks/inference-optimization/sglang-throughput.md)：

```bash
fore-rsi --session sglang-throughput \
  --task tasks/inference-optimization/sglang-throughput.md
```

使用自己的任务时，将路径替换为实际文件路径。相对路径以运行命令时的工作目录为基准。两种方式都可以在后续对话中继续补充材料或调整要求。

### 退出与恢复

按 `Ctrl+B`，松开后再按 `q` 退出。在 Agent 对话中，`Ctrl+C` 用于中断当前轮次。

列出会话，查看工作流名称、工作流状态和终端服务器状态：

```bash
fore-rsi list
```

按名称恢复已有会话：

```bash
fore-rsi --session sglang-throughput
```

会话使用已保存的工作流和任务进度继续执行，无需再次传入 `--task`。

### 停止会话

停止会话并保留数据：

```bash
fore-rsi stop --session sglang-throughput
```

### 删除会话

删除不再需要的命名会话：

```bash
fore-rsi delete --session sglang-throughput
```

## 持续改进循环

<p align="center">
  <img src="docs/assets/improvement-loop_zh.png" alt="Agent Team 探索、执行与实验，反馈驱动下一轮；Watchdog 监督整个任务循环并提醒成员；人类与 Agent 改进任务循环和 Watchdog。" width="720">
</p>

### 任务迭代

1. 探索方案：围绕目标与约束，分析已有材料、比较可行路径，形成可执行方案。
2. 执行工作：落实方案，产出代码、配置、分析、文档等可供实验的结果。
3. 运行实验：通过测试、测量、模拟或人工评阅取得反馈，对照目标与约束评估结果，决定保留或调整。

反馈回到探索与执行，指导下一轮改进。探索阶段也可以直接请求反馈。

Coordinator（协调者）对接用户要求与任务进展，Checker（检查者）负责方案、工作和结论的阶段检查。用户通过 Coordinator 补充要求与材料，调整任务方向。

### Watchdog：监督与提醒

Watchdog（看门狗）定期巡查任务进展和团队协作，识别停滞、重复尝试与交接问题，向相关成员发出提醒并跟进处理。它关注整个流程能否有效推进任务，并总结可复用的工作经验。

### 人类与 Agent：改进任务循环与 Watchdog

人类与 Agent 根据任务经验和 Watchdog 反馈，分别改进任务循环和 Watchdog 的监督与提醒机制。这些改进经过设计、实现与验证后，应用于后续任务。

## 设计你的定制 RSI 工作流

工作流定义团队角色、工具、执行步骤和交接规则，也可以携带领域提示词、参考资料、专业知识、工作方法和评价标准。根据任务需要组织团队，让持续改进循环服务于不同领域：

- 软件开发：迭代实现功能或算法，通过测试与反馈改进。
- 推理优化：优化 Foretoken、SGLang、vLLM 等推理系统的代码、配置与运行表现。
- 科学研究：结合专业文献、数据、模拟和专家评阅组织工作。

## 贡献

欢迎参与 ForeRSI。开发环境、验证方式与 Pull Request 流程见[贡献指南](CONTRIBUTING_zh.md)。

感谢所有通过代码、文档、想法和反馈帮助 ForeRSI 改进的[贡献者](https://github.com/shiweijiezero/fore-rsi/graphs/contributors)。

## 许可证

[Apache License 2.0](LICENSE)。
