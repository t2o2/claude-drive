"""File-based locking with heartbeat support for multi-agent coordination.

Lock files live in a shared directory (e.g. .drive/agents/locks/) and use
JSON format with agent ownership and heartbeat timestamps. Git push conflict
is the true arbitration — on push failure, agents must abort and retry.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _lock_path(locks_dir: Path, task_id: str) -> Path:
    return locks_dir / f"{task_id}.lock"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_lock(lock_file: Path) -> dict | None:
    if not lock_file.exists():
        return None
    return json.loads(lock_file.read_text())


def acquire_lock(locks_dir: Path, task_id: str, agent_id: str) -> bool:
    """Write a lock file for task_id owned by agent_id.

    Returns True if created, False if lock already exists.
    """
    lock_file = _lock_path(locks_dir, task_id)
    if lock_file.exists():
        return False

    now = _now_iso()
    data = {
        "agent_id": agent_id,
        "task_id": task_id,
        "acquired_at": now,
        "last_heartbeat": now,
    }
    lock_file.write_text(json.dumps(data, indent=2))
    return True


def release_lock(locks_dir: Path, task_id: str, agent_id: str) -> bool:
    """Delete lock file only if owned by agent_id.

    Returns True if released, False if wrong owner or not found.
    """
    lock_file = _lock_path(locks_dir, task_id)
    data = _read_lock(lock_file)
    if data is None:
        return False
    if data["agent_id"] != agent_id:
        return False

    lock_file.unlink()
    return True


def refresh_lock(locks_dir: Path, task_id: str, agent_id: str) -> bool:
    """Update last_heartbeat timestamp for a lock owned by agent_id.

    Returns True if refreshed, False if wrong owner or not found.
    """
    lock_file = _lock_path(locks_dir, task_id)
    data = _read_lock(lock_file)
    if data is None:
        return False
    if data["agent_id"] != agent_id:
        return False

    data["last_heartbeat"] = _now_iso()
    lock_file.write_text(json.dumps(data, indent=2))
    return True


def is_locked(locks_dir: Path, task_id: str) -> dict | None:
    """Return lock info dict if task is locked, None otherwise."""
    return _read_lock(_lock_path(locks_dir, task_id))


def list_locks(locks_dir: Path) -> list[dict]:
    """Return all active locks in the directory."""
    locks: list[dict] = []
    for lock_file in sorted(locks_dir.glob("*.lock")):
        data = _read_lock(lock_file)
        if data is not None:
            locks.append(data)
    return locks


def cleanup_stale(locks_dir: Path, max_age_seconds: int = 7200) -> list[str]:
    """Remove locks where last_heartbeat is older than max_age_seconds.

    Defaults to 2 hours (7200 seconds). Uses last_heartbeat, not acquired_at.
    Returns list of cleaned task_ids.
    """
    now = datetime.now(timezone.utc)
    cleaned: list[str] = []

    for lock_file in locks_dir.glob("*.lock"):
        data = _read_lock(lock_file)
        if data is None:
            continue

        heartbeat = datetime.fromisoformat(data["last_heartbeat"])
        age_seconds = (now - heartbeat).total_seconds()

        if age_seconds > max_age_seconds:
            lock_file.unlink()
            cleaned.append(data["task_id"])

    return cleaned


# ── CLI ───────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    import sys

    DEFAULT_LOCKS_DIR = ".drive/agents/locks"

    parser = argparse.ArgumentParser(description="Lock protocol CLI — JSON output")
    parser.add_argument("--locks-dir", default=DEFAULT_LOCKS_DIR)
    sub = parser.add_subparsers(dest="command")

    # acquire
    p_acq = sub.add_parser("acquire")
    p_acq.add_argument("task_id")
    p_acq.add_argument("agent_id")

    # release
    p_rel = sub.add_parser("release")
    p_rel.add_argument("task_id")
    p_rel.add_argument("agent_id")

    # refresh
    p_ref = sub.add_parser("refresh")
    p_ref.add_argument("task_id")
    p_ref.add_argument("agent_id")

    # list
    sub.add_parser("list")

    # cleanup
    p_clean = sub.add_parser("cleanup")
    p_clean.add_argument("--max-age", type=int, default=7200)

    args = parser.parse_args()

    if not args.command:
        parser.print_help(sys.stderr)
        sys.exit(1)

    locks_path = Path(args.locks_dir)
    locks_path.mkdir(parents=True, exist_ok=True)

    try:
        if args.command == "acquire":
            ok = acquire_lock(locks_path, args.task_id, args.agent_id)
            print(json.dumps({"acquired": ok}))

        elif args.command == "release":
            ok = release_lock(locks_path, args.task_id, args.agent_id)
            print(json.dumps({"released": ok}))

        elif args.command == "refresh":
            ok = refresh_lock(locks_path, args.task_id, args.agent_id)
            print(json.dumps({"refreshed": ok}))

        elif args.command == "list":
            all_locks = list_locks(locks_path)
            print(json.dumps(all_locks))

        elif args.command == "cleanup":
            cleaned = cleanup_stale(locks_path, max_age_seconds=args.max_age)
            print(json.dumps({"cleaned": cleaned}))

    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
