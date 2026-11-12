// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Loads plugin modules and assembles their workflows for the application.
 * Imports the selected entry and package version, combines task schemas, and
 * registers native Durable extensions. Returns the workflow entry, registry and
 * task validator for the application to use.
 */
import { findPackageJSON } from "node:module";
import { pathToFileURL } from "node:url";
import { createRegistry } from "@earendil-works/pi-durable";
import Type from "typebox";
import { Compile } from "typebox/compile";
import type { ForeRsiPlugin, WorkflowContext } from "../plugin.ts";
import { TaskRevisionSchema } from "../runtime/task.ts";

/**
 * Import a resolved plugin entry and obtain its version from package.json.
 * Both imports use Node's module cache.
 */
export async function loadPlugin(entrypoint: URL): Promise<LoadedPlugin> {
  const manifestPath = findPackageJSON(entrypoint);
  if (manifestPath === undefined) {
    throw new Error(`No package.json found for plugin entry ${entrypoint.href}`);
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
    throw new TypeError(`Plugin package ${manifestPath} must declare a version`);
  }

  const module: { default?: unknown } = await import(entrypoint.href);
  const definition = module.default;
  if (
    definition === null || typeof definition !== "object" ||
    !("name" in definition) || typeof definition.name !== "string" || definition.name.length === 0 ||
    !("title" in definition) || typeof definition.title !== "string" ||
    !("taskSchema" in definition) || definition.taskSchema === null || typeof definition.taskSchema !== "object" ||
    !("workflow" in definition) || typeof definition.workflow !== "function"
  ) {
    throw new TypeError(`Plugin entry ${entrypoint.href} must default-export a ForeRsiPlugin`);
  }

  return {
    definition: definition as ForeRsiPlugin,
    version: manifest.version,
    entrypoint,
  };
}

/**
 * Combine task requirements and register a plugin's native workflow definitions.
 * Return the selected entry, registry and input validator for the task host.
 */
export async function assembleWorkflow<TTaskSchema extends Type.TSchema>(
  plugin: ForeRsiPlugin<TTaskSchema>,
  context: WorkflowContext,
) {
  const taskValidator = Compile(Type.Intersect([TaskRevisionSchema, plugin.taskSchema]));
  const workflow = await plugin.workflow(context);
  const registry = createRegistry();
  for (const extension of workflow.extensions) {
    registry.install(extension);
  }

  // Match the selected entry to the definition installed in the native registry.
  if (registry.snapshot().task(workflow.entry.definition.name)?.definition !== workflow.entry.definition) {
    throw new Error(`Plugin ${plugin.name} must register its selected entry task in its extensions`);
  }

  return { entry: workflow.entry, registry, taskValidator };
}

/** A loaded plugin definition with its package version and module location. */
export interface LoadedPlugin {
  readonly definition: ForeRsiPlugin;
  readonly version: string;
  readonly entrypoint: URL;
}
