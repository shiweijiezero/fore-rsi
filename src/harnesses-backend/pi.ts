// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Connects Pi's native extension startup to the team composition entry.
 * Pi owns authentication, model selection, sessions and terminal behavior.
 * Role initialization continues in src/rsi-workflows/agent-team/workflow.ts.
 */
import type { ExtensionFactory } from "@earendil-works/pi-coding-agent";
import { registerAgentTeam } from "../rsi-workflows/agent-team/workflow.ts";

/** Bind a selected workflow to the Pi extension factory used by the CLI. */
export function createPiExtension(requestedWorkflow?: string): ExtensionFactory {
  return (pi) => registerAgentTeam(pi, requestedWorkflow);
}
