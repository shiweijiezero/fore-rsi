// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Defines team settings and the runtime records for their members.
 * Team settings describe each role's execution backend, model and concurrency.
 * Member records connect stable identities to native sessions and execution state.
 */
import Type from "typebox";
import { DurableTaskIdSchema } from "../schema.ts";

/** Role names supplied by a workflow. */
export const AgentRoleSchema = Type.String();

/** Team execution settings saved with each task revision. */
export const AgentTeamSpecSchema = Type.Object({
  roles: Type.Record(AgentRoleSchema, Type.Array(Type.Object({
    harness: Type.String({
      description: "Registered session backend; the host binds its execution target and authentication.",
    }),
    model: Type.String({
      description: "Model identifier interpreted by the selected harness.",
    }),
    thinkingLevel: Type.Union([Type.String(), Type.Null()], {
      description: "Harness-native reasoning level; null uses that harness's default.",
    }),
    slots: Type.Union([Type.Integer({ minimum: 0 }), Type.Null()], {
      description: "Maximum simultaneously active members. Zero pauses dispatch; null adds no fixed limit. Task constraints still apply.",
    }),
  })), {
    description: "Execution allocations for the roles used by the workflow; slot counts limit active members, not historical sessions.",
  }),
  teamComments: Type.Array(Type.String()),
});

/** Common progress states for a member's execution. */
export const AgentLifecycleStateSchema = Type.Union([
  Type.Literal("creating", { description: "Preparing a session and execution context; a slot is reserved." }),
  Type.Literal("ready", { description: "Runnable work is waiting for a slot." }),
  Type.Literal("running", { description: "Executing role work and occupying a slot." }),
  Type.Literal("waiting", { description: "The native session is idle; waiting for results, resources or messages without occupying a slot." }),
  Type.Literal("pausing", { description: "Yielding work; the slot remains occupied until the native session is idle." }),
  Type.Literal("paused", { description: "Execution is paused with its progress preserved." }),
  Type.Literal("retired", { description: "The member's responsibility has ended; its session and results remain available." }),
  Type.Literal("failed", { description: "Execution failed; diagnostic and recovery records remain available." }),
]);

/** A member's identity, current session settings and workflow binding. */
export const AgentInstanceSchema = Type.Object({
  name: Type.Readonly(Type.String({
    description: "Stable task-local member name, also used as its member-table key.",
  })),
  role: Type.Readonly(AgentRoleSchema),
  harness: Type.Readonly(Type.String({
    description: "Actual session backend. Changing the backend creates a new member and native session.",
  })),
  model: Type.String({
    description: "Model currently used by the native session.",
  }),
  thinkingLevel: Type.Union([Type.String(), Type.Null()], {
    description: "Actual harness-native reasoning level; null when unavailable.",
  }),
  sessionId: Type.Union([Type.String(), Type.Null()], {
    description: "Host session-record ID; null until the session is created.",
  }),
  workflowTaskId: Type.Union([DurableTaskIdSchema, Type.Null()], {
    description: "Current or most recent role workflow task, or null before one is created.",
  }),
  appliedTaskRevision: Type.Readonly(Type.Union([
    Type.Integer({ minimum: 1 }),
    Type.Null(),
  ], {
    description: "Task revision actually loaded by this member; null before initialization.",
  })),
  state: Type.Readonly(AgentLifecycleStateSchema),
});

/** Current team settings with all member records, including paused and retired members. */
export const AgentTeamSchema = Type.Object({
  ...AgentTeamSpecSchema.properties,
  agents: Type.Record(Type.String(), AgentInstanceSchema),
});

export const AgentModelAllocationSchema = Type.RecordValue(AgentTeamSpecSchema.properties.roles).items;

export type AgentTeamSpec = Type.Static<typeof AgentTeamSpecSchema>;
export type AgentTeam = Type.Static<typeof AgentTeamSchema>;
export type AgentInstance = Type.Static<typeof AgentInstanceSchema>;
export type AgentRole = Type.Static<typeof AgentRoleSchema>;
export type AgentLifecycleState = Type.Static<typeof AgentLifecycleStateSchema>;
export type AgentModelAllocation = Type.Static<typeof AgentModelAllocationSchema>;
