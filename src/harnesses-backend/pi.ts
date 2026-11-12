// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Adapts Pi's native extension lifecycle to the ForeRSI Coordinator.
 * Pi owns authentication, model selection, sessions and terminal behavior; this
 * adapter loads the Coordinator prompt and registers its task tools and handlers.
 */
import { readFile } from "node:fs/promises";
import type { ExtensionAPI, ExtensionFactory } from "@earendil-works/pi-coding-agent";
import registerCoordinatorTools from "../rsi-workflows/agent-team/coordinator/tools.ts";

/** Bind a selected workflow to the Pi extension factory used by the CLI. */
export function createPiExtension(requestedWorkflow?: string): ExtensionFactory {
  return async (pi: ExtensionAPI): Promise<void> => {
    const systemPrompt = await readFile(
      new URL("../rsi-workflows/agent-team/coordinator/system-prompt.jinja", import.meta.url),
      "utf8",
    );
    registerCoordinatorTools(pi, systemPrompt, requestedWorkflow);
  };
}
