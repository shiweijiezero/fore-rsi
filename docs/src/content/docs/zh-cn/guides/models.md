---
title: 模型与登录
description: 登录模型服务商，选择模型，并按需设置网络代理。
---

## 登录

打开 ForeRSI 后输入：

```text
/login
```

选择服务商，按照提示完成其提供的订阅登录或 API Key 配置。也可以使用环境变量中的 `OPENAI_API_KEY`、`ANTHROPIC_API_KEY` 等凭据。

## 选择模型

`/model` 选择当前对话使用的模型，`/thinking` 设置推理强度。可选的推理强度取决于模型支持范围。

启动时也可以通过 `--model` 指定模型 ID，或使用 `服务商/模型ID` 的形式。例如，已配置 OpenAI 凭据时：

```bash
fore-rsi --model openai/gpt-4o-mini
```

`--provider` 将模型查找范围限定为一个服务商，`--thinking` 则设置启动时的推理强度。模型匹配规则与服务商支持见 [Pi 模型指南](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md)。

## 使用 HTTP 代理

需要代理时，在启动 ForeRSI 的同一终端设置以下变量。将示例地址替换为实际 HTTP 代理地址：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=localhost,127.0.0.1,::1
fore-rsi
```

Pi 首次使用时下载所需的文件搜索工具，也会沿用这些代理设置。
