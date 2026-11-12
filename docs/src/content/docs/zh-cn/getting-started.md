---
title: 快速开始
description: 安装 ForeRSI，选择模型并开始终端对话。
---

需要 Node.js 22.19.0 或更高版本，以及 npm。

## 安装

```bash
npm install -g github:shiweijiezero/fore-rsi
```

如果从本地源码安装，在 ForeRSI 仓库根目录执行：

```bash
npm install
npm install -g .
```

## 开始对话

在希望处理的项目目录中启动：

```bash
fore-rsi
```

进入终端界面后，登录并选择模型：

```text
/login
/model
```

`/login` 会提供所选服务商支持的认证方式，也可以直接使用服务商的 API Key 环境变量。通过 `/thinking` 选择模型支持的推理强度。

随后输入目标，例如：

> 检查这个项目的启动说明。找出最短可用的安装路径，对照代码核实命令，并提出简洁的修改建议。

工具以运行 ForeRSI 的系统用户权限执行，默认无需逐次审批。输入框为空时按 Ctrl+D 退出。

需要复用要求时，参阅[任务文件](../guides/tasks/)；下次继续同一段对话，参阅[会话管理](../guides/sessions/)。

## 更新与卸载

从 GitHub 安装时，重新执行安装命令即可更新。从本地源码安装时，在原仓库目录执行：

```bash
git pull --ff-only
npm install
npm install -g .
```

两种安装方式均可通过以下命令卸载：

```bash
npm uninstall -g fore-rsi
```
