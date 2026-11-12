---
title: 会话管理
description: 为对话命名，按名称查找，并从保存的上下文继续。
---

Pi 会话保存对话历史，以及继续对话所需的上下文。启动时可以取一个便于识别的名字：

```bash
fore-rsi --name "SGLang 吞吐优化"
```

在对话中，`/name` 用于改名，`/session` 显示会话 ID、文件和用量。名称是显示标签，可以重复；会话 ID 用于定位一份确定的会话。

## 找回对话

```bash
fore-rsi --resume
```

在选择器中输入名称，选中对应会话后按回车。选择器默认展示当前目录的会话，按 Tab 可以扩大到其他目录。

继续当前目录最近的会话：

```bash
fore-rsi --continue
```

按已知 ID 打开时，将 `ID` 替换为 `/session` 显示的会话 ID：

```bash
fore-rsi --session ID
```

`--session` 接受会话 ID、能唯一匹配的 ID 前缀或会话文件路径；按显示名称查找则使用选择器。打开会话时，也会恢复该会话的工作目录。

## 保存哪些内容

Pi 保留对话记录、模型选择和上下文压缩记录。新打开的会话在包含用户或模型消息后才会写入磁盘。

Coordinator 将任务要求和所选工作流一同保存在会话中，恢复时沿用已保存的工作流。这组命令恢复对话与任务要求；团队执行和外部作业需要通过任务级恢复重新接入。

分支、上下文压缩、导出和存储设置见 [Pi 会话指南](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sessions.md)。
