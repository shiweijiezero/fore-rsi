// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

/** Remove generated output before compilation so deleted modules and templates leave the package. */
import { rm } from "node:fs/promises";

await rm(new URL("../dist/", import.meta.url), { recursive: true, force: true });
