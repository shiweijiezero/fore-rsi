// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/** Defines the Coordinator's workflow selection and persisted task-requirement schemas. */
import Type from "typebox";
import { TaskRevisionSchema } from "../../../runtime/task.ts";

/** Built-in workflow choices accepted by the CLI and Coordinator. */
export const workflowNames = ["default", "inference"] as const;

/** Requirements supplied by the Coordinator; the host assigns their revision. */
export const TaskRequirementsSchema = Type.Omit(TaskRevisionSchema, ["revision"]);

/** Session-owned task preparation, before a workflow owns execution and member state. */
export const CoordinatorTaskSchema = Type.Object({
  workflow: Type.Union(workflowNames.map((name) => Type.Literal(name))),
  requirements: Type.Union([TaskRevisionSchema, Type.Null()]),
});

export type CoordinatorTask = Type.Static<typeof CoordinatorTaskSchema>;
