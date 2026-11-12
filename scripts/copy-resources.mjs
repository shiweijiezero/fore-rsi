// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/** Copy runtime Jinja templates into dist, preserving their relative paths and omitting local Chinese review copies. */
import { copyFile, glob, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const source = fileURLToPath(new URL("../src/", import.meta.url));
const target = fileURLToPath(new URL("../dist/", import.meta.url));

for await (const template of glob("**/*.jinja", { cwd: source, exclude: ["**/*-zh.jinja"] })) {
  const destination = join(target, template);
  await mkdir(dirname(destination), { recursive: true });
  await copyFile(join(source, template), destination);
}
