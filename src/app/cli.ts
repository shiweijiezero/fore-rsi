#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Executable entry point for the installed fore-rsi command.
 * Configures Commander's program identity, help and version output from package.json
 * so command-line metadata follows the distributed package.
 */
import { Command } from "commander";
import metadata from "../../package.json" with { type: "json" };

/** Run the installed CLI, using package metadata for its identity and version. */
function main(): void {
  const program = new Command()
    .name(metadata.name)
    .description(metadata.description)
    .version(metadata.version);

  program.action(() => program.help()).parse();
}

main();
