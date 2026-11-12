#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Entry point for the fore-rsi command. main() parses ForeRSI options and passes
 * Pi arguments to runPiCli(), which calls Pi's public main().
 * Pi owns command dispatch, session management and the terminal lifecycle.
 * It initializes the Coordinator through extensionFactories; the extension
 * registers --workflow, task read/update tools, and session_start, session_tree
 * and before_agent_start handlers.
 */
import { Command, Option } from "commander";
import metadata from "../../package.json" with { type: "json" };
import { createPiExtension } from "../harnesses-backend/pi.ts";
import { workflowNames } from "../rsi-workflows/agent-team/coordinator/task-requirements.ts";

/** Parse ForeRSI options and pass the remaining arguments to Pi. */
async function main(): Promise<void> {
  const program = new Command()
    .name(metadata.name)
    .description(metadata.description)
    .version(metadata.version)
    // Handle help as an option so -- can pass it through to Pi.
    .helpOption(false)
    .option("-h, --help", "Display ForeRSI help")
    .on("option:help", () => program.help())
    .addOption(new Option("--harness <name>", "Agent runtime").choices(["pi"]).default("pi"))
    .option("--task <file>", "Start with instructions from a task file")
    .addOption(new Option("--workflow <name>", "Workflow for a new task (default: default)")
      .choices([...workflowNames]))
    .argument("[pi-args...]", "Pi options, commands or an initial prompt")
    .allowUnknownOption()
    .addHelpText("after", `
Examples:
  ${metadata.name}                       Open the Pi terminal interface
  ${metadata.name} --workflow inference  Use the inference workflow
  ${metadata.name} --task FILE           Start with a task file
  ${metadata.name} --name "My task"      Start a named session
  ${metadata.name} --resume              Find a saved session by name
  ${metadata.name} --continue            Continue this directory's latest session
  ${metadata.name} --session ID          Resume by the ID shown in /session
  ${metadata.name} -- --help             Show all Pi options and commands

In Pi: /login to sign in, /model to choose a model, /thinking for reasoning.
Resumed tasks keep their saved workflow. Provider API-key environment variables
are also supported.`)
    .action((args: string[], options: { task?: string; workflow?: string }) => {
      const piArgs = options.task === undefined ? args : [`@${options.task}`, ...args];
      return runPiCli(piArgs, options.workflow);
    });

  await program.parseAsync();
}

/** Start Pi with native arguments and a workflow-bound Coordinator extension. */
async function runPiCli(args: string[], workflow?: string): Promise<void> {
  const { main: piMain } = await import("@earendil-works/pi-coding-agent");
  await piMain(args, {
    extensionFactories: [
      createPiExtension(workflow), // src/harnesses-backend/pi.ts: bind the workflow and register Coordinator behavior.
    ],
  });
}

await main();
