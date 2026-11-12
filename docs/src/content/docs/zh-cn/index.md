---
title: ForeRSI
description: 从终端使用 ForeRSI，开发可复用的 RSI 工作流。
---

ForeRSI 是一个基于 Agent Team 的递归自我改进框架。任务描述目标与约束，工作流定义团队如何探索方案、执行工作和验证结果。

## 从一个任务开始

[安装 ForeRSI 并打开对话](getting-started/)，选择模型后输入目标。需要保存和复用要求时，可以使用[任务文件](guides/tasks/)。

终端界面沿用 Pi 的原生命令，完成[登录与模型选择](guides/models/)以及[会话管理](guides/sessions/)。

## 开发工作流

[工作流教程](tutorials/workflow/)使用 ForeRSI 的公开接口和 Pi Durable 原生任务定义，完成一个工作流模块的编写、加载与装配。

[任务数据](reference/task-data/)介绍工作流使用的共用任务要求、团队配置和资源约束。

## 查阅接口

- [命令行参考](reference/cli/)介绍 ForeRSI 参数，并提供 Pi 完整参数的查询入口。
- [API 参考](../api/)从 `fore-rsi` 和 `fore-rsi/workflows` 的公开导出生成，保留英文标识与源码注释。
