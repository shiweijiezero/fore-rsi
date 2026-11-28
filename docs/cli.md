# CLI reference

English | [简体中文](cli_zh.md)

## Start or resume

Run `fore-rsi` or `fore-rsi run` in the project directory to start a ForeRSI session and describe the task in the conversation. Both forms accept the same options. You can select a workflow, choose an agent backend, name the session, and supply a task file:

```bash
fore-rsi --session sglang-throughput \
  --task tasks/inference-optimization/sglang-throughput.md
```

This example uses the task file from the ForeRSI repository root. In a script without a terminal, pass `--task FILE`: the command runs the same workflow without attaching the foreground interface and returns its outcome. The named session and its results remain available after the command exits.

Startup options:

- `--workflow NAME` selects a registered workflow by name. The built-in `default` is selected if you omit it.
- `--harness NAME` selects the native agent CLI: `pi`, `codex`, or `claude` (Claude Code). New sessions default to Pi; resuming by name keeps the saved backend.
- `--model MODEL` selects the entry agent's model (the Coordinator in the default workflow). Use a model name accepted by the backend, or omit it to keep the native selection.
- `--effort LEVEL` sets reasoning effort for that agent, independently of `--model`. For example: `fore-rsi --harness claude --model sonnet --effort high`. Supported levels depend on the backend and model; omitting the option keeps the native setting.
- `--max-attempts N` limits attempts per required tool submission, including the first (default: 3). The default workflow also allows up to N direction proposals per round and N finish-review attempts in total per workgroup.
- `--session NAME` names the ForeRSI session to create or resume.
- `--task FILE` provides a Markdown task file. Omit it to describe the task in the conversation.
- `--cache-dir PATH` chooses workflow storage for a new session (default: `./cache`). Relative paths use the current project's Git repository root, or the startup directory outside Git; absolute paths are used directly. Workflow data is stored in its `workflows/` subdirectory. Each session name keeps its original storage location for the current user, even when started again from another directory.

Quote values containing spaces. Relative task paths are relative to the working directory. To change a requirement, tell the Coordinator in the same conversation. Each change is saved as a new task revision with its own file; previously submitted task versions stay readable and a resumed session uses the latest one.

For example, tell the Coordinator, “Share eight GPUs among three Experimenters and review progress every 20 minutes.” If you resize the team, new measurements wait until current runs finish and the team has reassigned its resources. Set the Experimenter quota to zero to pause new measurements.

With `--harness claude`, workflow messages appear in the member’s existing Claude Code conversation and leave its prompt box free for you to type. If you interrupt a turn with `Esc`, send a message in that terminal before dispatching more work: Claude Code pauses plugin-initiated prompts after a manual stop.

To resume, use the same `--session` name without resubmitting `--task`. Each agent reopens its own native conversation under `<cache-dir>/workflows/<session>/harnesses/`. To switch backends, start a new named session. See [Exit and resume](../README.md#exit-and-resume) for the exit shortcut.

`fore-rsi --help` lists available options; `fore-rsi --version` prints the installed version. Both commands exit after displaying their output.

## List sessions

List registered workflows from their saved locations and local terminal sessions:

```bash
fore-rsi list
```

`WORKFLOW` shows the registered workflow name. `WORKFLOW_STATE` preserves recorded `completed`, `stopped`, and `failed` outcomes. For a `running` record, it checks the local host's PID and creation time: a matching live process remains `running`, an exited host or reused PID shows `interrupted`, and missing identity or unavailable process information shows `unknown`. These observations do not change the saved record.

`TERMINAL_SERVER` independently shows `running`, `stopped`, or `unavailable`. A dash (`—`) marks a missing record or a workflow record that has no saved state.

Saved sessions do not need `--cache-dir` for listing, stopping, or deletion. The current project's default cache, or a directory selected with `--cache-dir`, is also checked for workflow records without a saved storage binding.

Use a name from the list with `fore-rsi --session NAME` to resume it. `list` does not accept `--session`.

## Open work progress

Select Work progress at the top of the sidebar to switch to the progress page. Under the workspace, `global` is the first group. Its first member is the workflow's entry agent, listed by name. To open the progress page in a separate terminal:

```bash
fore-rsi workprogress --session sglang-throughput
```

Press `q` or `Esc` to close this separate viewer without affecting the workflow. In the session terminal, you can close panes you create. The workflow keeps its progress and agent panes open. The command uses the session's saved location and does not accept `--cache-dir`.

Select an exploration node to see its experiment result and working notes. Select a node in the separate Watchdog report chain to read that review.

## Stop a session

Stop a session while keeping its data:

```bash
fore-rsi stop --session sglang-throughput
```

`stop` requires `--session NAME` and uses the saved storage location. It waits for workflow cleanup before stopping the terminal server, keeping session data and the storage binding. An already stopped session succeeds; an unknown name reports an error. The default session can also be stopped with `--session default`. On Windows, exit the running workflow first.

## Delete a session

Stop and delete a named session:

```bash
fore-rsi delete --session sglang-throughput
```

`delete` requires `--session NAME`. It uses the session's saved storage location, stops the workflow and waits for cleanup, then stops and deletes the terminal session, and finally removes the workflow directory and its storage binding. It also handles sessions present on only one side. If shutdown fails, the command reports the error and retains the workflow cache and binding.

Deletion removes the session's native agent conversations along with its workflow data. It preserves the default session `default`, project files outside the session directory, and the native CLI's personal settings and history outside ForeRSI. On Windows, exit the running workflow before deleting its session.

`--workflow`, `--harness`, `--model`, `--effort`, `--max-attempts`, and `--task` apply only to `run`. `--cache-dir` applies to `run`, `list`, `stop`, and `delete`.

## Diagnostic logs

Python diagnostics use `INFO` level and readable text on stderr by default. Increase detail or keep a JSON log alongside stderr:

```bash
fore-rsi --log-level DEBUG
fore-rsi --log-format json --log-file logs/fore-rsi.jsonl
```

`--log-format` applies to stderr and the optional file. File output appends in UTF-8 and creates missing parent directories. Use separate files for independently running processes. Help and version commands do not create log files, and normal command results remain on stdout.

Agent conversations and native terminal logs retain their own recording paths.
