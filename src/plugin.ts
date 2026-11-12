// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Defines how built-in and external plugins provide a workflow to ForeRSI.
 * The plugin entry describes task requirements and resource directories, then builds
 * the native Durable tasks and extensions used to carry out the work.
 */
import type { AnyTask, Extension, TaskDefinition } from "@earendil-works/pi-durable";
import type { Static, TSchema } from "typebox";
import type { TaskRevision } from "./runtime/task.ts";

/** Default export of a plugin module. */
export interface ForeRsiPlugin<TTaskSchema extends TSchema = TSchema> {
  readonly name: string;
  readonly title: string;

  /** Plugin requirements combined with the common task requirements. */
  readonly taskSchema: TTaskSchema;

  /** Build the native workflow definitions for a task. */
  workflow(context: WorkflowContext): PluginWorkflow<TTaskSchema> | Promise<PluginWorkflow<TTaskSchema>>;

  readonly resources?: PluginResources;
}

/** Entry task and the extensions that register it and its supporting tasks. */
export interface PluginWorkflow<TTaskSchema extends TSchema = TSchema> {
  /** Initial input follows the task schema; checkpoint and result types come from the native task. */
  readonly entry: AnyTask & {
    readonly definition: Pick<
      TaskDefinition<TaskRevision & Static<TTaskSchema>, { phase: string }, unknown, object>,
      "initial"
    >;
  };
  readonly extensions: readonly Extension[];
}

/** Task identity and output location supplied to the workflow factory. */
export interface WorkflowContext {
  readonly taskName: string;
  /** Base directory URL for task artifacts. */
  readonly taskDirectory: URL;
}

/** Resource directories resolved relative to the plugin module. */
export interface PluginResources {
  readonly prompts?: URL;
  readonly guidance?: URL;
  readonly templates?: URL;
  readonly tasks?: URL;
}
