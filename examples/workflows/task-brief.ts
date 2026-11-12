// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/** A small workflow demonstrating a typed requirement and a native Durable task. */
import { defineExtension, defineTask } from "@earendil-works/pi-durable";
import type { ForeRsiWorkflow, TaskRevision } from "fore-rsi";
import Type from "typebox";

const Requirements = Type.Object({
  audience: Type.String({ minLength: 1, description: "Who will use the task's results." }),
});

type Input = TaskRevision & Type.Static<typeof Requirements>;
type Checkpoint = { phase: "compose" };

const ComposeBrief = defineTask<Input, Checkpoint, string>({
  name: "task-brief.compose",
  version: 1,
  initial: () => ({ phase: "compose" }),
  phases: {
    compose: (task, runtime, context) => runtime.commit(() => ({
      status: "terminal",
      outcome: {
        status: "completed",
        result: `# Task brief\n\n${task.input.goal}\n\nAudience: ${task.input.audience}\n`,
      },
    }), context),
  },
  abort: (_task, runtime, context) => runtime.commit(() => ({
    status: "terminal",
    outcome: { status: "aborted" },
  }), context),
});

const workflow: ForeRsiWorkflow<typeof Requirements, Checkpoint, string> = {
  name: "task-brief",
  title: "Task brief",
  taskSchema: Requirements,
  /** Register the entry task in a native Durable extension. */
  build() {
    return {
      entry: ComposeBrief,
      extensions: [defineExtension({ name: "task-brief", tasks: [ComposeBrief] })],
    };
  },
};

export default workflow;
