# Contributing to ForeRSI

English | [简体中文](CONTRIBUTING_zh.md)

## Local development

Use Node.js 22.19.0 or later. From the repository root:

```bash
npm install
npm run dev
```

Pass application arguments after `--`, for example `npm run dev -- --help`.

## Code and documentation standards

- Use TypeScript with ESM and strict types, following the repository's compiler configuration.
- Give each state transition, configuration value, and resource lifecycle one owner. Keep domain-specific behavior separate from shared workflow mechanisms.
- Reuse the agent runtime's public APIs for sessions, authentication, and tools. Keep runtime-specific details in their adapters.
- Keep changes cohesive. Remove superseded paths and duplicate state when replacing an implementation.
- Write concise English comments for public interfaces, complete processing stages, and non-obvious constraints. Explain purpose, inputs, outputs, and ownership where they matter.
- Keep English and Chinese documentation aligned. Write for the reader's task and update commands, configuration, examples, and their consumers together.
- Keep credentials, private infrastructure details, personal paths, and local execution data outside the repository.

## Verify changes

Run the type check and build:

```bash
npm run check
npm run build
```

Exercise the behavior affected by the change. Inspect rendered pages for interface or documentation changes; run the relevant task path for workflow, execution, or recovery changes. Record the inputs, environment, commands, and observed results needed to understand the outcome.

Tests should protect important behavior or a concrete regression. Prefer integration and end-to-end coverage of shared behavior. New dependencies, tests, or CI should have a clear purpose and an understood maintenance cost.

## Pull requests

Use a fork for external contributions and a focused branch for each change. Discuss changes to public interfaces, workflow semantics, or repository structure in an issue before undertaking a larger implementation.

A pull request should explain the problem, the approach, and the relevant validation results. Keep its scope focused and include the corresponding documentation and examples.

### Titles and classification

Start the PR title with bracketed tags, followed by a concise English description:

- Change type: `[Bugfix]`, `[Feature]`, `[Perf]`, `[Refactor]`, `[Docs]`, `[Test]`, `[CI]`, or `[Misc]`.
- Affected area, when useful: `[Runtime]`, `[Workflow]`, `[Harness]`, `[UI]`, or another descriptive tag.

Combine adjacent tags without spaces. For example:

```text
[Bugfix][Runtime] Resume paused tasks correctly
[Feature][Harness] Add Codex authentication
[Docs] Clarify Agent Team configuration
```

Commit messages should describe the specific change in English.

Contributions are distributed under the [Apache License 2.0](LICENSE). Verify the provenance and licensing of any material you include.
