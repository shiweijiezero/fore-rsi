// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Defines the public interface for built-in and external ForeRSI workflows.
 * A workflow describes its task requirements and resource directories, then builds
 * the native Durable tasks and extensions used to carry out the work.
 */
import type { Extension, Task as DurableTask } from "@earendil-works/pi-durable";
import type { Static, TSchema } from "typebox";
import type { TaskRevision } from "./runtime/task.ts";

/** Default export of a workflow module, preserving its native checkpoint, result and hook types. */
export interface ForeRsiWorkflow<
  TTaskSchema extends TSchema = TSchema,
  TCheckpoint extends { phase: string } = { phase: string },
  TResult = unknown,
  THooks extends object = object,
> {
  /** Stable identifier stored with tasks that use this workflow. */
  readonly name: string;
  readonly title: string;

  /** Workflow requirements combined with the common task requirements. */
  readonly taskSchema: TTaskSchema;

  /** Build the native task definitions for this workflow. */
  build(context: WorkflowContext):
    | WorkflowDefinition<TTaskSchema, TCheckpoint, TResult, THooks>
    | Promise<WorkflowDefinition<TTaskSchema, TCheckpoint, TResult, THooks>>;

  readonly resources?: WorkflowResources;
}

/** Entry task and the extensions that register it and its supporting tasks. */
export interface WorkflowDefinition<
  TTaskSchema extends TSchema = TSchema,
  TCheckpoint extends { phase: string } = { phase: string },
  TResult = unknown,
  THooks extends object = object,
> {
  /** Native task passed to Durable's createTask() with the validated requirements. */
  readonly entry: DurableTask<TaskRevision & Static<TTaskSchema>, TCheckpoint, TResult, THooks>;
  readonly extensions: readonly Extension[];
}

/** Task identity and output location supplied to the workflow builder. */
export interface WorkflowContext {
  /** Stable task name used for the workflow's runtime records and artifacts. */
  readonly taskName: string;
  /** Base directory URL for task artifacts. */
  readonly taskDirectory: URL;
}

/** Resource directories resolved relative to the workflow module. */
export interface WorkflowResources {
  /** Prompt templates used by the workflow. */
  readonly prompts?: URL;
  readonly guidance?: URL;
  /** Output and report templates. */
  readonly templates?: URL;
  /** Maintained task-file examples. */
  readonly tasks?: URL;
}
