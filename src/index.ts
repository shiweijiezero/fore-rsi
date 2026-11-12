// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Package-level imports for workflow authors.
 * Exposes workflow interfaces and shared data schemas. Host-side workflow loading
 * and assembly are available through fore-rsi/workflows.
 * @module fore-rsi
 */
export type {
  ForeRsiWorkflow,
  WorkflowDefinition,
  WorkflowContext,
  WorkflowResources,
} from "./workflow-api.ts";
export {
  type EnvConfig,
  EnvConfigSchema,
  type Task,
  TaskSchema,
  type TaskConstraints,
  TaskConstraintsSchema,
  type TaskRevision,
  TaskRevisionSchema,
  type TaskState,
  TaskStateSchema,
} from "./runtime/task.ts";
export {
  type AgentInstance,
  AgentInstanceSchema,
  type AgentLifecycleState,
  AgentLifecycleStateSchema,
  type AgentRoleAllocation,
  AgentRoleAllocationSchema,
  type AgentRole,
  AgentRoleSchema,
  type AgentTeam,
  AgentTeamSchema,
  type AgentTeamSpec,
  AgentTeamSpecSchema,
} from "./runtime/members.ts";
export {
  type GpuConstraints,
  GpuConstraintsSchema,
  type NetworkConstraints,
  NetworkConstraintsSchema,
  type Resource,
  ResourceSchema,
  type ResourceConstraints,
  ResourceConstraintsSchema,
} from "./runtime/resources.ts";
export { DurableTaskIdSchema, JsonValueSchema } from "./schema.ts";
