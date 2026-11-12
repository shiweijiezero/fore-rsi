// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Defines the task requirements and runtime view shared by ForeRSI workflows.
 * A requirement revision contains the goal, resources, team settings and environment.
 * The runtime view adds task identity, execution state and member records.
 */
import Type from "typebox";
import { DurableTaskIdSchema, JsonValueSchema } from "../schema.ts";
import { AgentTeamSchema, AgentTeamSpecSchema } from "./members.ts";
import { ResourceSchema } from "./resources.ts";

/** A complete revision of task requirements. */
export const TaskRevisionSchema = Type.Object({
  revision: Type.Integer({
    minimum: 1,
    description: "Host-assigned requirement revision, starting at 1 and increasing when requirements change.",
  }),
  goal: Type.String({
    description: "The problem, expected deliverables and criteria for the task's outcome.",
  }),
  constraints: Type.Object({
    fixedFields: Type.Record(Type.String(), JsonValueSchema, {
      description: "Conditions and values that must remain unchanged during the task.",
    }),
    resources: ResourceSchema,
    timeBudgetSeconds: Type.Union([Type.Number({ minimum: 0 }), Type.Null()], {
      description: "Wall-clock limit in seconds from the first execution, including pauses; null means unlimited.",
    }),
    stopConditions: Type.Array(Type.String(), {
      description: "End the task when any condition holds. Requirements that must hold together belong in one condition.",
    }),
  }),
  taskComments: Type.Array(Type.String()),
  agentTeam: AgentTeamSpecSchema,
  envConfig: Type.Object({
    variables: Type.Record(Type.String(), Type.String(), {
      description: "Shared non-sensitive environment variables.",
    }),
    envComments: Type.Array(Type.String()),
  }),
});

/** Overall task progress, including asynchronous pause and completion. */
export const TaskStateSchema = Type.Union([
  Type.Literal("ready", { description: "Created but not yet started." }),
  Type.Literal("running", { description: "The workflow is progressing, including waits within its stages." }),
  Type.Literal("pausing", { description: "Stopping dispatch and bringing members to a pausable boundary." }),
  Type.Literal("paused", { description: "Sessions, progress and registered external jobs are preserved." }),
  Type.Literal("finishing", { description: "Ending member work and cleaning up executions owned by this task." }),
  Type.Literal("completed", { description: "The workflow completed the task." }),
  Type.Literal("stopped", { description: "Ended by a user request or stop condition, preserving existing results." }),
  Type.Literal("failed", { description: "Execution failed; diagnostic and recovery records are preserved." }),
]);

/** Current task requirements together with their runtime identity and execution state. */
export const TaskSchema = Type.Object({
  ...TaskRevisionSchema.properties,
  name: Type.Readonly(Type.String({
    description: "Stable task name, unique within the run-data root.",
  })),
  workflow: Type.Readonly(Type.Object({
    name: Type.Readonly(Type.String()),
    version: Type.Readonly(Type.String()),
  }, {
    description: "Workflow bound to this task, identified by its name and package version.",
  })),
  workflowTaskId: Type.Readonly(Type.Union([DurableTaskIdSchema, Type.Null()], {
    description: "Entry workflow task, or null before it is created.",
  })),
  state: Type.Readonly(TaskStateSchema),
  startedAt: Type.Readonly(Type.Union([Type.String(), Type.Null()], {
    description: "First execution time as an ISO 8601 UTC string, or null before execution. Resuming and revising requirements preserve this time.",
  })),
  agentTeam: AgentTeamSchema,
});

export const TaskConstraintsSchema = TaskRevisionSchema.properties.constraints;
export const EnvConfigSchema = TaskRevisionSchema.properties.envConfig;

export type Task = Type.Static<typeof TaskSchema>;
export type TaskRevision = Type.Static<typeof TaskRevisionSchema>;
export type TaskState = Type.Static<typeof TaskStateSchema>;
export type TaskConstraints = Type.Static<typeof TaskConstraintsSchema>;
export type EnvConfig = Type.Static<typeof EnvConfigSchema>;
