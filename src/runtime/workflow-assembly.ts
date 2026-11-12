// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Prepares a workflow's task definitions for the ForeRSI host.
 * Combines common and workflow-specific requirements, builds the native definitions,
 * and registers their extensions with Pi Durable. The result supplies the host with
 * an entry task, a registry and a task-data validator.
 */
import { createRegistry, type Registry } from "@earendil-works/pi-durable";
import Type from "typebox";
import { Compile, type Validator } from "typebox/compile";
import type { ForeRsiWorkflow, WorkflowContext, WorkflowDefinition } from "../workflow-api.ts";
import { TaskRevisionSchema } from "./task.ts";

/** Build and register the native workflow definitions for one task. */
export async function assembleWorkflow<
  TTaskSchema extends Type.TSchema,
  TCheckpoint extends { phase: string },
  TResult,
  THooks extends object,
>(
  workflow: ForeRsiWorkflow<TTaskSchema, TCheckpoint, TResult, THooks>,
  context: WorkflowContext,
): Promise<AssembledWorkflow<TTaskSchema, TCheckpoint, TResult, THooks>> {
  const taskSchema = Type.Intersect([TaskRevisionSchema, workflow.taskSchema]);
  const taskValidator = Compile(taskSchema);
  const { entry, extensions } = await workflow.build(context);

  const registry = createRegistry();
  for (const extension of extensions) {
    registry.install(extension);
  }

  const registeredEntry = registry.snapshot().task(entry.definition.name);
  if (registeredEntry?.definition !== entry.definition) {
    throw new Error(`Workflow ${workflow.name} must register its selected entry task in its extensions`);
  }

  return { entry, registry, taskValidator };
}

/** Registered workflow definitions and input validation used by the task host. */
export interface AssembledWorkflow<
  TTaskSchema extends Type.TSchema = Type.TSchema,
  TCheckpoint extends { phase: string } = { phase: string },
  TResult = unknown,
  THooks extends object = object,
> {
  /** Native entry task registered in the workflow's extensions. */
  entry: WorkflowDefinition<TTaskSchema, TCheckpoint, TResult, THooks>["entry"];
  /** Registry containing the workflow's extensions and task definitions. */
  registry: Registry;
  /** Validator for common and workflow-specific task requirements. */
  taskValidator: Validator<{}, Type.TIntersect<[typeof TaskRevisionSchema, TTaskSchema]>>;
}
