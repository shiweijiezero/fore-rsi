---
title: ForeRSI
description: Use ForeRSI from the terminal and build reusable RSI workflows.
---

ForeRSI is a recursive self-improvement framework built on Agent Teams. A task describes the objective and constraints; a workflow defines how the team explores approaches, executes work, and evaluates results.

## Start with a task

[Install ForeRSI and open a conversation](getting-started/), choose a model, and provide your objective. Use a [task file](guides/tasks/) when the requirements need to be saved and reused.

The terminal interface uses Pi's commands for [authentication and model selection](guides/models/) and [session management](guides/sessions/).

## Build a workflow

The [workflow tutorial](tutorials/workflow/) defines and loads a complete workflow module using ForeRSI's public interfaces and Pi Durable's native task definitions.

[Task data](reference/task-data/) explains the shared requirements, team settings, and resource constraints used by workflow authors.

## Look up an interface

- [CLI reference](reference/cli/) covers ForeRSI options and the entry point to Pi's full command reference.
- [API reference](api/) is generated from the `fore-rsi` and `fore-rsi/workflows` public exports.
