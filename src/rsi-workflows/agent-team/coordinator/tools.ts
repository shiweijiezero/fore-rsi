// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Registers the Coordinator's Pi tools and session handlers.
 * The Pi-specific extension factory loads the system prompt and calls this module;
 * this module owns the task preparation behavior that the Coordinator exposes.
 */
import { isDeepStrictEqual } from "node:util";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import Type from "typebox";
import { Compile } from "typebox/compile";
import { CoordinatorTaskSchema, TaskRequirementsSchema, type CoordinatorTask, workflowNames } from "./task-requirements.ts";

const entryType = "fore-rsi.coordinator";
const taskValidator = Compile(CoordinatorTaskSchema);

const workflowGuidance: Record<CoordinatorTask["workflow"], string> = {
  default: "Prepare a general task: capture the desired outcome, permitted work, constraints and how to assess the result.",
  inference: "Prepare an inference optimization task: capture the service, model, workload, performance and quality criteria, available environment, and separate per-workload and total experiment budgets. Keep exact evaluation commands and other domain requirements in taskComments.",
};

/** Register Coordinator tools and restore task requirements from Pi's active conversation branch. */
export default function registerCoordinatorTools(
  pi: ExtensionAPI,
  systemPrompt: string,
  requestedWorkflow?: string,
): void {
  pi.on("session_start", (_event, ctx) => {
    const task = readTask(ctx);
    const requested = requestedWorkflow;
    if (task && requested !== undefined && requested !== task.workflow) {
      ctx.ui.notify(`Resuming the ${task.workflow} workflow. Use /new to select another workflow.`, "info");
    }
    showStatus(ctx, task?.workflow ?? selectedWorkflow(requestedWorkflow));
  });
  pi.on("session_tree", (_event, ctx) => {
    showStatus(ctx, readTask(ctx)?.workflow ?? selectedWorkflow(requestedWorkflow));
  });

  pi.on("before_agent_start", (event, ctx) => {
    const task = readTask(ctx) ?? { workflow: selectedWorkflow(requestedWorkflow), requirements: null };
    event.systemPromptOptions.sections.fore_rsi_coordinator = systemPrompt;
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
      const task = readTask(ctx) ?? { workflow: selectedWorkflow(requestedWorkflow), requirements: null };
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
function selectedWorkflow(requestedWorkflow?: string): CoordinatorTask["workflow"] {
  const name = requestedWorkflow ?? "default";
  if (!workflowNames.includes(name as CoordinatorTask["workflow"])) {
    throw new Error(`Unknown workflow ${String(name)}. Choose ${workflowNames.join(" or ")}.`);
  }
  return name as CoordinatorTask["workflow"];
}

/** Identify the Coordinator in Pi's existing footer without replacing any native UI. */
function showStatus(ctx: ExtensionContext, workflow: CoordinatorTask["workflow"]): void {
  ctx.ui.setStatus("fore-rsi", `Coordinator · ${workflow}`);
}
