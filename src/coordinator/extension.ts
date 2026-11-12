// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/** Adds task preparation to Pi while leaving conversation, authentication and tools with the native CLI. */
import { isDeepStrictEqual } from "node:util";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import Type from "typebox";
import { Compile } from "typebox/compile";
import { CoordinatorTaskSchema, TaskRequirementsSchema, type CoordinatorTask, workflowNames } from "./task.ts";

const entryType = "fore-rsi.coordinator";
const taskValidator = Compile(CoordinatorTaskSchema);

const coordinatorGuidance = `You are the ForeRSI Coordinator, the user's continuing point of contact.
Understand the objective, constraints, available resources, team preferences and expected deliverables.
Read referenced task files and project instructions before interpreting their requirements.
The current task snapshot is injected into your Coordinator context before each turn.
Use fore_rsi_task_update to prepare a new Task or an explicit change to its requirements. Preserve requirements the user has not changed.
Answer questions normally; a question or a request to discuss an idea does not itself create or revise a task.
For an unspecified resource restriction or nullable limit, use null. Empty maps or arrays in resource selectors mean that no machine, GPU or interface is allowed; use them only when the user explicitly requests that restriction. Empty comments, fixedFields, stopConditions or role allocations are valid when nothing was supplied. Do not invent available machines, credentials, resource capacity or measurements.
When the user specifies role counts without execution settings, use the current Pi model and thinking level returned by fore_rsi_task_read. Leave unspecified role allocations empty.
Keep secrets in the execution environment, not in task requirements. Reference the existing file or environment variable instead.
Explain the resulting objective and important open requirements briefly in the user's language. Internal revisions are for the tools.
This integration prepares and saves requirements. Team execution is not connected: saving requirements does not launch members, deployments or experiments.
When asked to start execution, state that the requirements are saved and the team runner is not yet available. Do not perform the team's implementation or experiments yourself.`;

const workflowGuidance: Record<CoordinatorTask["workflow"], string> = {
  default: "Prepare a general task: capture the desired outcome, permitted work, constraints and how to assess the result.",
  inference: "Prepare an inference optimization task: capture the service, model, workload, performance and quality criteria, available environment, and separate per-workload and total experiment budgets. Keep exact evaluation commands and other domain requirements in taskComments.",
};

/** Register Coordinator tools and restore task requirements from Pi's active conversation branch. */
export default function coordinator(pi: ExtensionAPI): void {
  pi.registerFlag("workflow", {
    description: "Workflow for a new task: default or inference; resumed tasks keep their selection",
    type: "string",
  });

  pi.on("session_start", (_event, ctx) => {
    const task = readTask(ctx);
    const requested = pi.getFlag("workflow");
    if (task && requested !== undefined && requested !== task.workflow) {
      ctx.ui.notify(`Resuming the ${task.workflow} workflow. Use /new to select another workflow.`, "info");
    }
    showStatus(ctx, task?.workflow ?? selectedWorkflow(pi));
  });
  pi.on("session_tree", (_event, ctx) => {
    showStatus(ctx, readTask(ctx)?.workflow ?? selectedWorkflow(pi));
  });

  pi.on("before_agent_start", (event, ctx) => {
    const task = readTask(ctx) ?? { workflow: selectedWorkflow(pi), requirements: null };
    event.systemPromptOptions.sections.fore_rsi_coordinator = coordinatorGuidance;
    event.systemPromptOptions.sections.fore_rsi_workflow = workflowGuidance[task.workflow];
    event.systemPromptOptions.sections.fore_rsi_task = formatTaskContext(task, ctx);
  });

  pi.registerTool({
    name: "fore_rsi_task_update",
    label: "Prepare task",
    description: "Prepare a Task from the user's requirements. The current task snapshot is already in the Coordinator context. Preserve unaffected fields. The host assigns the revision and parses the structured result; this action saves requirements only and does not start workflow execution.",
    outputSchema: CoordinatorTaskSchema,
    parameters: Type.Object({
      requirements: TaskRequirementsSchema,
    }),
    executionMode: "sequential",
    async execute(_id, params, _signal, _onUpdate, ctx) {
      const task = readTask(ctx) ?? { workflow: selectedWorkflow(pi), requirements: null };
      const revision = task.requirements?.revision ?? 0;
      const nextRequirements = { ...params.requirements, revision: revision + 1 };
      const updated = task.requirements !== null && isDeepStrictEqual(task.requirements, {
        ...params.requirements,
        revision,
      })
        ? task
        : { ...task, requirements: nextRequirements };
      if (updated !== task) pi.appendEntry(entryType, updated);
      showStatus(ctx, updated.workflow);
      return {
        content: [{ type: "text", text: `Task prepared; execution has not started.\n${JSON.stringify(updated)}` }],
        details: updated,
        structuredContent: updated,
      };
    },
  });
}

/** Read only the active branch so session navigation and forks retain their own requirements. */
function readTask(ctx: ExtensionContext): CoordinatorTask | null {
  const entries = ctx.sessionManager.getBranch();
  for (let index = entries.length - 1; index >= 0; index--) {
    const entry = entries[index];
    if (entry.type !== "custom" || entry.customType !== entryType) continue;
    if (!taskValidator.Check(entry.data)) {
      throw new Error("The saved Coordinator task does not match its requirement schema.");
    }
    return entry.data;
  }
  return null;
}

/** Render the saved Task as Coordinator context without exposing its host-assigned revision. */
function formatTaskContext(task: CoordinatorTask, ctx: ExtensionContext): string {
  const requirements = task.requirements === null ? null : (() => {
    const { revision: _revision, ...current } = task.requirements;
    return current;
  })();
  const modelDefaults = ctx.model === undefined ? null : {
    harness: "pi",
    model: `${ctx.model.provider}/${ctx.model.id}`,
    thinkingLevel: ctx.thinkingLevel,
  };
  return `Current workflow: ${task.workflow}\nSaved Task requirements (null means not prepared):\n${JSON.stringify(requirements)}\nCurrent Coordinator model defaults for unspecified Agent settings:\n${JSON.stringify(modelDefaults)}`;
}

/** Resolve a new conversation's workflow; an existing task keeps its saved binding. */
function selectedWorkflow(pi: ExtensionAPI): CoordinatorTask["workflow"] {
  const name = pi.getFlag("workflow") ?? "default";
  if (!workflowNames.includes(name as CoordinatorTask["workflow"])) {
    throw new Error(`Unknown workflow ${String(name)}. Choose ${workflowNames.join(" or ")}.`);
  }
  return name as CoordinatorTask["workflow"];
}

/** Identify the Coordinator in Pi's existing footer without replacing any native UI. */
function showStatus(ctx: ExtensionContext, workflow: CoordinatorTask["workflow"]): void {
  ctx.ui.setStatus("fore-rsi", `Coordinator · ${workflow}`);
}
