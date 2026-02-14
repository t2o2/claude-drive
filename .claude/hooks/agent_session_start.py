#!/usr/bin/env python3
"""Agent session start hook for multi-agent Claude Code.

Provides context to agent sessions: board status, lock state,
messages, recent activity from other agents.

Trigger: SessionStart (when AGENT_ROLE env var is set)
Input: JSON on stdin (consumed but unused)
Output: Agent context injected to stdout
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def _get_project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def _load_board_module(project_dir: str):
    """Import board.py from scripts/ via sys.path manipulation."""
    scripts_dir = os.path.join(project_dir, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import board
    return board


def _load_lock_module(project_dir: str):
    """Import lock.py from scripts/ via sys.path manipulation."""
    scripts_dir = os.path.join(project_dir, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import lock
    return lock


def _board_summary(board_mod, tasks_dir: Path) -> str:
    """Produce board status line with task counts by status."""
    all_tasks = board_mod.list_tasks(tasks_dir)
    counts: dict[str, int] = {"open": 0, "locked": 0, "done": 0, "failed": 0}
    for task in all_tasks:
        status = task.get("status", "open")
        if status in counts:
            counts[status] += 1
    parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
    return f"[BOARD STATUS] {', '.join(parts)}" if parts else "[BOARD STATUS] Empty board"


def _locked_tasks_summary(lock_mod, locks_dir: Path) -> str:
    """List all currently locked tasks and their owners."""
    locks = lock_mod.list_locks(locks_dir)
    if not locks:
        return "[LOCKED TASKS] None"
    lines = ["[LOCKED TASKS]"]
    for lk in locks:
        lines.append(f"- {lk['task_id']}: locked by {lk['agent_id']}")
    return "\n".join(lines)


def _messages_summary(board_mod, messages_dir: Path, role: str) -> str:
    """Show unread messages for this agent's role."""
    if not messages_dir.exists():
        return f"[MESSAGES FOR {role}] No messages directory"
    messages = board_mod.get_messages(messages_dir, for_role=role, unread_only=True)
    if not messages:
        return f"[MESSAGES FOR {role}] No unread messages"
    lines = [f"[MESSAGES FOR {role}] {len(messages)} unread:"]
    for msg in messages:
        lines.append(f"- From {msg['from']}: \"{msg['text']}\"")
    return "\n".join(lines)


def _next_task_hint(board_mod, tasks_dir: Path) -> str:
    """Suggest the highest-priority open task."""
    open_tasks = board_mod.list_tasks(tasks_dir, status_filter="open")
    if not open_tasks:
        return "[NEXT TASK HINT] No open tasks available"
    open_tasks.sort(key=lambda t: t.get("priority", 0), reverse=True)
    top = open_tasks[0]
    return (
        f"[NEXT TASK HINT] Highest priority open: "
        f"\"{top['description']}\" (priority {top.get('priority', 0)})"
    )


def _recent_agent_activity(project_dir: str, agent_id: str) -> str:
    """Show last 10 git commits NOT by this agent."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-30", "--format=%h %s"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "[RECENT AGENT ACTIVITY] No git history available"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "[RECENT AGENT ACTIVITY] Git not available"

    lines = []
    for line in result.stdout.strip().splitlines():
        # Skip commits by this agent (format: "hash agent/<id>: message")
        if f"agent/{agent_id}:" in line:
            continue
        lines.append(line)
        if len(lines) >= 10:
            break

    if not lines:
        return "[RECENT AGENT ACTIVITY] No recent commits from other agents"

    header = "[RECENT AGENT ACTIVITY]"
    return header + "\n" + "\n".join(lines)


def main() -> int:
    # Consume stdin (hook input JSON)
    try:
        sys.stdin.read()
    except IOError:
        pass

    project_dir = _get_project_dir()
    role = os.environ.get("AGENT_ROLE", "unknown")
    agent_id = os.environ.get("AGENT_ID", "unknown-0")

    tasks_dir = Path(project_dir) / ".drive" / "agents" / "tasks"
    locks_dir = Path(project_dir) / ".drive" / "agents" / "locks"
    messages_dir = Path(project_dir) / ".drive" / "agents" / "messages"

    output_parts: list[str] = []

    # Identity
    output_parts.append(f"[AGENT INIT] Role: {role} | ID: {agent_id}")

    # Board status
    if tasks_dir.exists():
        board_mod = _load_board_module(project_dir)
        output_parts.append(_board_summary(board_mod, tasks_dir))
        output_parts.append(_next_task_hint(board_mod, tasks_dir))
        output_parts.append(_messages_summary(board_mod, messages_dir, role))
    else:
        output_parts.append("[BOARD STATUS] Tasks directory not found")

    # Lock status
    if locks_dir.exists():
        lock_mod = _load_lock_module(project_dir)
        output_parts.append(_locked_tasks_summary(lock_mod, locks_dir))
    else:
        output_parts.append("[LOCKED TASKS] Locks directory not found")

    # Recent activity from other agents
    output_parts.append(_recent_agent_activity(project_dir, agent_id))

    print("\n".join(output_parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
