---
title: Models and authentication
description: Sign in to a provider, choose a model, and configure a network proxy.
---

## Sign in

Open ForeRSI and enter:

```text
/login
```

Choose a provider and follow the subscription sign-in or API-key flow it offers. Existing environment variables such as `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are also supported.

## Choose a model

Use `/model` to select the model for the current conversation. `/thinking` sets its reasoning level; the available levels depend on the model.

At startup, `--model` accepts a model ID or a `provider/model-id` pair. For example, with an OpenAI credential:

```bash
fore-rsi --model openai/gpt-4o-mini
```

`--provider` can restrict model lookup to one provider. `--thinking` sets a reasoning level at startup. See [Pi's model guide](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md) for model matching and supported providers.

## Use an HTTP proxy

Set the proxy variables in the same terminal before starting ForeRSI. Replace the example address with your HTTP proxy's address:

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=localhost,127.0.0.1,::1
fore-rsi
```

These settings also apply when Pi downloads the file-search tools it needs on first use.
