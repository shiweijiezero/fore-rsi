# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the ForeRSI project

"""Manage Claude Code conversation records and project links."""

import json
from pathlib import Path
from uuid import UUID, uuid4

from fore_rsi.utils.paths import write_private_text


def get_claude_project_link(home: Path, conversation: str) -> Path:
    """Return the stable project alias for one Claude Code conversation."""
    return home / "projects" / f"fore-rsi-{UUID(conversation)}"


def link_project_directory(link: Path, target: Path) -> None:
    """Expose a workflow-owned Claude project without replacing an existing project directory."""
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    link.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except FileExistsError:
        if not link.is_symlink() or link.resolve() != target.resolve():
            raise RuntimeError(f"Claude project directory is already in use: {link}") from None


def remove_project_link(link: Path, target: Path) -> None:
    """Remove only the Claude project link still owned by this workflow member."""
    if link.is_symlink() and link.resolve() == target.resolve():
        link.unlink()


def session_directory(member: Path) -> Path:
    """Locate the workflow-owned Claude project directory for one member."""
    return member.parent / "projects" / "agents" / member.stem


def fork_claude_session(seed: Path, child: Path) -> None:
    """Bind a new member UUID to a native fork of the seed's exact transcript on first launch."""
    source = json.loads(seed.with_suffix(".session").read_bytes())
    transcript = session_directory(seed) / f"{UUID(source['id'])}.jsonl"
    if not transcript.is_file():
        raise FileNotFoundError(f"Claude seed has no saved conversation: {transcript}")
    record = child.with_suffix(".session")
    if record.exists():
        raise FileExistsError(f"Claude member already has a session: {record}")

    # Claude may write the fork before the session-start hook. Route its entire project
    # directory to the child from launch, rather than linking a transcript after that write.
    profile = source.get("native_profile") or source.get("profile") or source["home"]
    binding = {"id": str(uuid4()), "profile": profile, "fork_transcript": str(transcript.resolve())}
    write_private_text(record, json.dumps(binding))


def bind_session_transcript(member: Path, native: Path) -> None:
    """Link the native per-session filename to the member record when using Claude's default profile."""
    record = member.with_suffix(".session")
    binding = json.loads(record.read_bytes())
    conversation = str(UUID(binding["id"]))
    profile = binding.get("native_profile") or binding.get("profile") or binding["home"]
    projects = Path(profile) / "projects"
    directory = session_directory(member)
    owned = directory / f"{conversation}.jsonl"
    if native.resolve() == owned.resolve():
        return
    if native.name != owned.name or not native.is_absolute() or native.parent.resolve().parent != projects.resolve():
        raise ValueError(f"Unexpected Claude transcript location for session {conversation}.")
    native.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Install the link before Claude's first write. Never replace an existing
    # native record, even if another session happens to claim the same name.
    native.symlink_to(owned)
    binding["transcript_link"] = str(native)
    write_private_text(record, json.dumps(binding))


def prepare_claude_session(member: Path, profile: Path) -> tuple[dict[str, str], list[str], str]:
    """Return the profile, native launch arguments and UUID for a fresh, forked or resumed member."""
    record = member.with_suffix(".session")
    directory = session_directory(member)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        binding = json.loads(record.read_bytes())
    except FileNotFoundError:
        binding = {"id": str(uuid4()), "native_profile": str(profile)}
        write_private_text(record, json.dumps(binding))

    conversation = str(UUID(binding["id"]))
    environment = {}
    if "native_profile" not in binding:
        profile = Path(binding.get("profile") or binding["home"])
        alias = get_claude_project_link(profile, conversation)
        link_project_directory(alias, directory)
        environment = {"CLAUDE_CONFIG_DIR": str(profile), "CLAUDE_CODE_PROJECT_DIR_NAME": alias.name}

    if (directory / f"{conversation}.jsonl").is_file():
        arguments = ["--resume", conversation]
    elif "fork_transcript" in binding:
        arguments = ["--resume", binding["fork_transcript"], "--fork-session", "--session-id", conversation]
    else:
        arguments = ["--session-id", conversation]
    if "fork_transcript" in binding:
        # Apply the child's role instructions rather than replaying the seed's saved system prompt.
        arguments.extend(["--system-prompt-snapshot", "off"])
    return environment, arguments, conversation
