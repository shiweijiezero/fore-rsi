// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Composes the team's role integrations for a user-facing Pi session.
 * The harness adapter enters registerAgentTeam(), which renders role prompts
 * through src/runtime/prompt-renderer.ts and registers tools and session handlers.
 * Role implementations stay in their own directories beneath agent-team/.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createPromptRenderer } from "../../runtime/prompt-renderer.ts";
import registerCoordinatorTools from "./coordinator/tools.ts";

/** Register the team's user-facing role before Pi starts processing the conversation. */
export function registerAgentTeam(pi: ExtensionAPI, requestedWorkflow?: string): void {
  const prompts = createPromptRenderer(new URL("../", import.meta.url));
  const coordinatorPrompt = prompts.render("agent-team/coordinator/system-prompt.jinja");

  registerCoordinatorTools(pi, coordinatorPrompt, requestedWorkflow); // coordinator/tools.ts: task preparation and session hooks.

  // Execution-role workflows to connect at this composition boundary:
  // Explorer: investigate directions and develop proposals.
  // Worker: implement proposals and submit work for feedback.
  // Verifier: prepare execution environments and gather feedback.
  // Checker: review proposals and the reusability of retained work.
  // Watchdog: inspect team progress and follow up on stalled work.
}
