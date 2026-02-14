"""Tests for scripts/lock.py — file-based locking with heartbeat support."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Adjust import path so we can import from scripts/
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lock import (
    acquire_lock,
    cleanup_stale,
    is_locked,
    list_locks,
    refresh_lock,
    release_lock,
)


AGENT_ID = "implementer-0"
TASK_ID = "task-abc123"


# ── acquire_lock ──────────────────────────────────────────────────────


def test_acquire_lock_creates_file(tmp_path: Path) -> None:
    result = acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    assert result is True

    lock_file = tmp_path / f"{TASK_ID}.lock"
    assert lock_file.exists()

    data = json.loads(lock_file.read_text())
    assert data["agent_id"] == AGENT_ID
    assert data["task_id"] == TASK_ID
    assert "acquired_at" in data
    assert "last_heartbeat" in data
    assert data["acquired_at"] == data["last_heartbeat"]


def test_acquire_lock_fails_if_exists(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    result = acquire_lock(tmp_path, TASK_ID, "implementer-1")
    assert result is False


# ── release_lock ──────────────────────────────────────────────────────


def test_release_lock_deletes_file(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    result = release_lock(tmp_path, TASK_ID, AGENT_ID)
    assert result is True
    assert not (tmp_path / f"{TASK_ID}.lock").exists()


def test_release_lock_rejects_wrong_owner(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    result = release_lock(tmp_path, TASK_ID, "implementer-99")
    assert result is False
    assert (tmp_path / f"{TASK_ID}.lock").exists()


def test_release_lock_returns_false_if_not_found(tmp_path: Path) -> None:
    result = release_lock(tmp_path, "nonexistent-task", AGENT_ID)
    assert result is False


# ── refresh_lock ──────────────────────────────────────────────────────


def test_refresh_lock_updates_heartbeat(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    lock_file = tmp_path / f"{TASK_ID}.lock"
    original = json.loads(lock_file.read_text())

    time.sleep(0.05)
    result = refresh_lock(tmp_path, TASK_ID, AGENT_ID)
    assert result is True

    updated = json.loads(lock_file.read_text())
    assert updated["last_heartbeat"] > original["last_heartbeat"]
    assert updated["acquired_at"] == original["acquired_at"]


def test_refresh_lock_rejects_wrong_owner(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    result = refresh_lock(tmp_path, TASK_ID, "implementer-99")
    assert result is False


# ── is_locked ─────────────────────────────────────────────────────────


def test_is_locked_returns_info(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    info = is_locked(tmp_path, TASK_ID)
    assert info is not None
    assert info["agent_id"] == AGENT_ID
    assert info["task_id"] == TASK_ID


def test_is_locked_returns_none(tmp_path: Path) -> None:
    info = is_locked(tmp_path, "nonexistent-task")
    assert info is None


# ── list_locks ────────────────────────────────────────────────────────


def test_list_locks_returns_all(tmp_path: Path) -> None:
    acquire_lock(tmp_path, "task-1", "agent-a")
    acquire_lock(tmp_path, "task-2", "agent-b")
    locks = list_locks(tmp_path)
    assert len(locks) == 2
    task_ids = {lock["task_id"] for lock in locks}
    assert task_ids == {"task-1", "task-2"}


def test_list_locks_empty(tmp_path: Path) -> None:
    locks = list_locks(tmp_path)
    assert locks == []


# ── cleanup_stale ─────────────────────────────────────────────────────


def test_cleanup_stale_removes_old_locks(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)

    lock_file = tmp_path / f"{TASK_ID}.lock"
    data = json.loads(lock_file.read_text())
    old_time = "2020-01-01T00:00:00+00:00"
    data["last_heartbeat"] = old_time
    data["acquired_at"] = old_time
    lock_file.write_text(json.dumps(data))

    cleaned = cleanup_stale(tmp_path, max_age_seconds=60)
    assert TASK_ID in cleaned
    assert not lock_file.exists()


def test_cleanup_stale_keeps_fresh_locks(tmp_path: Path) -> None:
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)
    cleaned = cleanup_stale(tmp_path, max_age_seconds=7200)
    assert cleaned == []
    assert (tmp_path / f"{TASK_ID}.lock").exists()


def test_cleanup_stale_uses_heartbeat_not_acquired(tmp_path: Path) -> None:
    """Stale detection must use last_heartbeat, not acquired_at."""
    acquire_lock(tmp_path, TASK_ID, AGENT_ID)

    lock_file = tmp_path / f"{TASK_ID}.lock"
    data = json.loads(lock_file.read_text())
    # Old acquired_at but fresh heartbeat — should NOT be cleaned
    data["acquired_at"] = "2020-01-01T00:00:00+00:00"
    data["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    lock_file.write_text(json.dumps(data))

    cleaned = cleanup_stale(tmp_path, max_age_seconds=60)
    assert cleaned == []
    assert lock_file.exists()
