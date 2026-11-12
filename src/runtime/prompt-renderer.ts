// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/**
 * Creates file-backed Jinja-style prompt renderers using Nunjucks.
 * A workflow owns its renderer and template root. Nunjucks loads and reuses
 * templates, including shared fragments and inherited templates under that root.
 */
import { fileURLToPath } from "node:url";
import nunjucks, { type Environment } from "nunjucks";

/**
 * Create a renderer for workflow authors, with template names relative to root.
 * Prompt text is not HTML-escaped; missing output values raise rendering errors.
 */
export function createPromptRenderer(root: URL): Environment {
  return new nunjucks.Environment(
    new nunjucks.FileSystemLoader(fileURLToPath(root)),
    { autoescape: false, throwOnUndefined: true },
  );
}
