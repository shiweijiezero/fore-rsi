// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Package-level imports for workflow and plugin authors.
 * Exposes the plugin interfaces and shared data schemas. Host-side plugin loading
 * and assembly are available through fore-rsi/plugins.
 */
export type {
  ForeRsiPlugin,
  PluginResources,
  PluginWorkflow,
  WorkflowContext,
} from "./plugin.ts";
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
  type AgentModelAllocation,
  AgentModelAllocationSchema,
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
