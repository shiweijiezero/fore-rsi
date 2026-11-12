// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Loads a workflow module together with its package version.
 * The main flow reads package metadata, imports the selected entry and returns
 * the exported workflow definition for the task host.
 * @module fore-rsi/workflows
 */
import { findPackageJSON } from "node:module";
import { pathToFileURL } from "node:url";
import type { ForeRsiWorkflow } from "../workflow-api.ts";

/** Import a resolved workflow entry and return its definition, version and location. */
export async function loadWorkflow(entrypoint: URL): Promise<LoadedWorkflow> {
  const version = await readPackageVersion(entrypoint);
  const module: { default?: unknown } = await import(entrypoint.href);
  const definition = readWorkflowDefinition(module.default, entrypoint);

  return { definition, version, entrypoint };
}

/** Read the owning package's version through Node's module loader. */
async function readPackageVersion(entrypoint: URL): Promise<string> {
  const manifestPath = findPackageJSON(entrypoint);
  if (manifestPath === undefined) {
    throw new Error(`No package.json found for workflow entry ${entrypoint.href}`);
  }

  const { default: manifest }: { default: unknown } = await import(
    pathToFileURL(manifestPath).href,
    { with: { type: "json" } },
  );
  if (
    manifest === null || typeof manifest !== "object" ||
    !("version" in manifest) || typeof manifest.version !== "string" ||
    manifest.version.length === 0
  ) {
    throw new TypeError(`Workflow package ${manifestPath} must declare a version`);
  }

  return manifest.version;
}

/** Read the workflow definition at the JavaScript module boundary. */
function readWorkflowDefinition(value: unknown, entrypoint: URL): ForeRsiWorkflow {
  if (
    value === null || typeof value !== "object" ||
    !("name" in value) || typeof value.name !== "string" || value.name.length === 0 ||
    !("title" in value) || typeof value.title !== "string" ||
    !("taskSchema" in value) || value.taskSchema === null || typeof value.taskSchema !== "object" ||
    !("build" in value) || typeof value.build !== "function"
  ) {
    throw new TypeError(`Workflow entry ${entrypoint.href} must default-export a ForeRsiWorkflow`);
  }

  return value as ForeRsiWorkflow;
}

/** A loaded workflow definition with its package version and module location. */
export interface LoadedWorkflow {
  /** Default-exported workflow definition after shape validation. */
  readonly definition: ForeRsiWorkflow;
  /** Version read from the package that owns the entrypoint. */
  readonly version: string;
  /** Resolved module URL used to load the workflow. */
  readonly entrypoint: URL;
}

export { assembleWorkflow, type AssembledWorkflow } from "../runtime/workflow-assembly.ts";
