---
title: Get started
description: Install ForeRSI, choose a model, and start a terminal conversation.
---

Use Node.js 22.19.0 or later and npm.

## Install

```bash
npm install -g github:shiweijiezero/fore-rsi
```

For a local checkout, run these commands from the ForeRSI repository root instead:

```bash
npm install
npm install -g .
```

## Start a conversation

Run ForeRSI in the project directory you want to work on:

```bash
fore-rsi
```

In the terminal interface, sign in and choose a model:

```text
/login
/model
```

`/login` offers the authentication methods supported by the selected provider. Provider API-key environment variables also work. Use `/thinking` to choose a reasoning level supported by the model.

Enter an objective, for example:

> Review this project's startup instructions. Identify the shortest working setup, check the commands against the code, and propose concise corrections.

Tools run with the operating-system permissions of the user running ForeRSI, without per-call approval. Press Ctrl+D with an empty editor to exit.

For reusable requirements, continue with [task files](../guides/tasks/). To return to a conversation later, see [sessions](../guides/sessions/).

## Update or uninstall

Repeat the installation command to update a GitHub installation. For a local checkout:

```bash
git pull --ff-only
npm install
npm install -g .
```

Uninstall either installation with:

```bash
npm uninstall -g fore-rsi
```
