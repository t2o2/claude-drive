"""Task board operations using file-per-task architecture.

Each task is stored as an individual JSON file in a tasks directory,
and each message as a JSON file in a messages directory. This avoids
git merge conflicts when multiple agents modify the board simultaneously.
"""

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _read_task(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_task(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


# ── Task operations ────────────────────────────────────────


def add_task(tasks_dir: Path, description: str, priority: int = 1) -> str:
    """Create a new task file. Returns the task_id."""
    task_id = _new_id()
    task = {
        "id": task_id,
        "description": description,
        "status": "open",
        "locked_by": None,
        "priority": priority,
        "created_at": _now_iso(),
        "completed_at": None,
        "heartbeat": None,
    }
    _write_task(tasks_dir / f"{task_id}.json", task)
    return task_id


def list_tasks(tasks_dir: Path, status_filter: str | None = None) -> list[dict]:
    """Read all task files, optionally filtering by status."""
    tasks: list[dict] = []
    for path in tasks_dir.glob("*.json"):
        task = _read_task(path)
        if status_filter is None or task["status"] == status_filter:
            tasks.append(task)
    return tasks


def claim_task(tasks_dir: Path, agent_id: str) -> dict | None:
    """Pick the highest-priority open task, lock it, and return it. Returns None if none available."""
    open_tasks = list_tasks(tasks_dir, status_filter="open")
    if not open_tasks:
        return None

    open_tasks.sort(key=lambda t: t["priority"], reverse=True)
    chosen = open_tasks[0]

    chosen["status"] = "locked"
    chosen["locked_by"] = agent_id
    chosen["heartbeat"] = _now_iso()
    _write_task(tasks_dir / f"{chosen['id']}.json", chosen)
    return chosen


def _verify_owner(task: dict, task_id: str, agent_id: str) -> None:
    """Raise PermissionError if the task is not locked by the given agent."""
    if task["status"] != "locked" or task["locked_by"] != agent_id:
        raise PermissionError(
            f"Task {task_id} is not locked by {agent_id} "
            f"(status={task['status']}, locked_by={task['locked_by']})"
        )


def complete_task(tasks_dir: Path, task_id: str, agent_id: str) -> None:
    """Mark a task as done. Raises PermissionError if not locked by agent_id."""
    path = tasks_dir / f"{task_id}.json"
    task = _read_task(path)
    _verify_owner(task, task_id, agent_id)

    task["status"] = "done"
    task["completed_at"] = _now_iso()
    _write_task(path, task)


def fail_task(tasks_dir: Path, task_id: str, agent_id: str, reason: str) -> None:
    """Mark a task as failed with a reason. Raises PermissionError if not locked by agent_id."""
    path = tasks_dir / f"{task_id}.json"
    task = _read_task(path)
    _verify_owner(task, task_id, agent_id)

    task["status"] = "failed"
    task["completed_at"] = _now_iso()
    task["reason"] = reason
    _write_task(path, task)


# ── Message operations ─────────────────────────────────────


def post_message(messages_dir: Path, from_role: str, to_role: str, text: str) -> str:
    """Create a new message file. Returns the msg_id."""
    msg_id = _new_id()
    message = {
        "id": msg_id,
        "from": from_role,
        "to": to_role,
        "timestamp": _now_iso(),
        "text": text,
        "read": False,
    }
    _write_task(messages_dir / f"{msg_id}.json", message)
    return msg_id


def get_messages(
    messages_dir: Path, for_role: str, unread_only: bool = True
) -> list[dict]:
    """Read messages addressed to a role, optionally only unread ones."""
    messages: list[dict] = []
    for path in messages_dir.glob("*.json"):
        msg = _read_task(path)
        if msg["to"] != for_role:
            continue
        if unread_only and msg["read"]:
            continue
        messages.append(msg)
    return messages


def mark_read(messages_dir: Path, msg_id: str) -> None:
    """Set read=True on a message file."""
    path = messages_dir / f"{msg_id}.json"
    msg = _read_task(path)
    msg["read"] = True
    _write_task(path, msg)


# ── Archive ────────────────────────────────────────────────


def archive_done(tasks_dir: Path, archive_dir: Path, older_than_days: int = 7) -> None:
    """Move done/failed tasks older than threshold to archive_dir."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

    for path in list(tasks_dir.glob("*.json")):
        task = _read_task(path)
        if task["status"] not in ("done", "failed"):
            continue
        if task["completed_at"] is None:
            continue

        completed = datetime.fromisoformat(task["completed_at"])
        if completed < cutoff:
            shutil.move(str(path), str(archive_dir / path.name))


# ── CLI ───────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    import sys

    DEFAULT_TASKS_DIR = ".drive/agents/tasks"
    DEFAULT_MESSAGES_DIR = ".drive/agents/messages"

    parser = argparse.ArgumentParser(description="Task board CLI — JSON output")
    parser.add_argument("--tasks-dir", default=DEFAULT_TASKS_DIR)
    parser.add_argument("--messages-dir", default=DEFAULT_MESSAGES_DIR)
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add")
    p_add.add_argument("description")
    p_add.add_argument("--priority", type=int, default=1)

    # list
    p_list = sub.add_parser("list")
    p_list.add_argument("--status", default=None)

    # claim
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("agent_id")

    # complete
    p_complete = sub.add_parser("complete")
    p_complete.add_argument("task_id")
    p_complete.add_argument("agent_id")

    # fail
    p_fail = sub.add_parser("fail")
    p_fail.add_argument("task_id")
    p_fail.add_argument("agent_id")
    p_fail.add_argument("reason")

    # message
    p_msg = sub.add_parser("message")
    p_msg.add_argument("from_role")
    p_msg.add_argument("to_role")
    p_msg.add_argument("text")

    # messages
    p_msgs = sub.add_parser("messages")
    p_msgs.add_argument("role")
    p_msgs.add_argument("--unread", action="store_true", default=False)

    # mark-read
    p_mr = sub.add_parser("mark-read")
    p_mr.add_argument("msg_id")

    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    tasks_path = Path(args.tasks_dir)
    messages_path = Path(args.messages_dir)

    try:
        if args.command == "add":
            tasks_path.mkdir(parents=True, exist_ok=True)
            tid = add_task(tasks_path, args.description, priority=args.priority)
            print(json.dumps({"task_id": tid, "status": "created"}))

        elif args.command == "list":
            tasks_path.mkdir(parents=True, exist_ok=True)
            tasks = list_tasks(tasks_path, status_filter=args.status)
            print(json.dumps(tasks))

        elif args.command == "claim":
            tasks_path.mkdir(parents=True, exist_ok=True)
            task = claim_task(tasks_path, args.agent_id)
            print(json.dumps({"task": task}))

        elif args.command == "complete":
            complete_task(tasks_path, args.task_id, args.agent_id)
            print(json.dumps({"status": "completed"}))

        elif args.command == "fail":
            fail_task(tasks_path, args.task_id, args.agent_id, args.reason)
            print(json.dumps({"status": "failed"}))

        elif args.command == "message":
            messages_path.mkdir(parents=True, exist_ok=True)
            mid = post_message(messages_path, args.from_role, args.to_role, args.text)
            print(json.dumps({"msg_id": mid}))

        elif args.command == "messages":
            messages_path.mkdir(parents=True, exist_ok=True)
            msgs = get_messages(messages_path, args.role, unread_only=args.unread)
            print(json.dumps(msgs))

        elif args.command == "mark-read":
            mark_read(messages_path, args.msg_id)
            print(json.dumps({"status": "read"}))

    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
