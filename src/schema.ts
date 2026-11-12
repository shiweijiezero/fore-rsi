// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Common TypeBox schemas for JSON values and native Durable task identifiers.
 * Task, member and plugin schemas use these shared definitions to represent
 * upstream data types consistently.
 */
import type { JsonValue } from "@earendil-works/chord/json";
import type { TaskId } from "@earendil-works/pi-durable";
import Type from "typebox";

/** Recursive JSON values for task requirements and plugin-defined data. */
export const JsonValueSchema = Type.Unsafe<JsonValue>(Type.Cyclic({
  JsonValue: Type.Union([
    Type.Null(),
    Type.Boolean(),
    Type.Number(),
    Type.String(),
    Type.Array(Type.Ref("JsonValue")),
    Type.Record(Type.String(), Type.Ref("JsonValue")),
  ]),
}, "JsonValue"));

/** Integer representation retaining the native task ID's nominal TypeScript type. */
export const DurableTaskIdSchema = Type.Unsafe<TaskId>(Type.Integer());
