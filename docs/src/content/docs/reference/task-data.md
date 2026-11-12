---
title: Task data
description: Understand the structured requirements and runtime records used by workflows.
---

Workflow code consumes structured task data. People can describe their requirements in a [Markdown task file](../../guides/tasks/); the application supplies the structured values to a workflow.

## Requirements and runtime records

`TaskRevision` contains the objective, constraints, team configuration, environment settings, and a revision number. A workflow can add domain-specific fields through its `taskSchema`.

`Task` adds the stable task name, workflow name and version, execution state, first start time, and member records. Its `workflowTaskId` links the task to its entry task in Pi Durable.

`assembleWorkflow()` combines the common requirements with the workflow's schema and returns a validator. Use that validator before creating the native entry task.

## Team configuration

`AgentTeamSpec.roles` maps role names to execution allocations. Each allocation names a harness, model, reasoning level, and number of active slots. Role names come from the workflow.

`AgentTeam` also contains member records. Each `AgentInstance` has a stable name and records its session, workflow task, applied requirement revision, and lifecycle state. A slot limit controls active work; it is not a limit on how many historical sessions can be retained.

## Resource and time limits

Resource requirements distinguish three scopes:

- `machineConstraints`: concurrent limits for each machine.
- `perExecutionConstraints`: limits for one complete workload, including its related jobs and services.
- `totalExecutionConstraints`: concurrent totals across managed workloads.

Within a scope, `null` adds no restriction beyond the enclosing limits. Empty allowed-machine or GPU-selector collections allow no matching resources.

`maxHostMemory` numbers use GB; strings can include a unit. `minLinkSpeedGbps` describes negotiated link speed, not reserved network bandwidth.

`timeBudgetSeconds` counts wall-clock time from the first execution, including pauses. Resuming work preserves the original start time. A `null` budget has no time limit.

The [API reference](../../api/) contains the complete exported types and schemas, including field descriptions and state values.
