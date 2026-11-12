---
title: Sessions
description: Name a conversation, find it later, and continue with its saved context.
---

A Pi session stores the conversation history and the context needed to continue it. Give it a recognizable name when starting:

```bash
fore-rsi --name "SGLang throughput"
```

In the conversation, `/name` changes the name and `/session` shows the session ID, file, and usage. Names are display labels and may be reused; the session ID identifies one session.

## Find a conversation

```bash
fore-rsi --resume
```

Type the name in the picker, select the matching session, and press Enter. The picker starts with sessions for the current directory; press Tab to include other directories.

To continue the latest session for the current directory:

```bash
fore-rsi --continue
```

To open a known session, replace `ID` with the ID shown by `/session`:

```bash
fore-rsi --session ID
```

`--session` accepts an ID, a unique ID prefix, or a session file path. Use the picker to search by display name. Opening a session restores its working directory as well as its conversation context.

## What is preserved

Pi retains conversation entries, model choices, and context-compaction records. A newly opened session is written to disk once it contains a user or assistant message.

The Coordinator saves task requirements and the selected workflow with the conversation. Resuming keeps the saved workflow. These commands restore the conversation and its requirements; team execution and external jobs require task-level recovery.

See [Pi's sessions guide](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/sessions.md) for branching, compaction, export, and storage settings.
