// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/** Copy runtime resources that TypeScript does not emit into the distribution tree. */
import { cp, mkdir } from "node:fs/promises";

const source = new URL("../src/rsi-workflows/agent-team/coordinator/system-prompt.jinja", import.meta.url);
const target = new URL("../dist/rsi-workflows/agent-team/coordinator/system-prompt.jinja", import.meta.url);

await mkdir(new URL("../dist/rsi-workflows/agent-team/coordinator/", import.meta.url), { recursive: true });
await cp(source, target);
