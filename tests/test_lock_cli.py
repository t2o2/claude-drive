"""CLI tests for scripts/lock.py — exercises all subcommands via subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

LOCK_SCRIPT = str(Path(__file__).resolve().parent.parent / "scripts" / "lock.py")


def run_lock(*args: str, locks_dir: str = "") -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, LOCK_SCRIPT]
    if locks_dir:
        cmd += ["--locks-dir", locks_dir]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


# ── acquire / list / refresh / release cycle ─────────────────


def test_acquire_list_refresh_release_cycle(tmp_path: Path) -> None:
    ld = str(tmp_path / "locks")

    # acquire
    r_acq = run_lock("acquire", "task-1", "agent-a", locks_dir=ld)
    assert r_acq.returncode == 0
    assert json.loads(r_acq.stdout)["acquired"] is True

    # acquire again fails
    r_acq2 = run_lock("acquire", "task-1", "agent-b", locks_dir=ld)
    assert r_acq2.returncode == 0
    assert json.loads(r_acq2.stdout)["acquired"] is False

    # list
    r_list = run_lock("list", locks_dir=ld)
    assert r_list.returncode == 0
    locks = json.loads(r_list.stdout)
    assert len(locks) == 1
    assert locks[0]["task_id"] == "task-1"

    # refresh
    r_ref = run_lock("refresh", "task-1", "agent-a", locks_dir=ld)
    assert r_ref.returncode == 0
    assert json.loads(r_ref.stdout)["refreshed"] is True

    # refresh wrong owner
    r_ref_bad = run_lock("refresh", "task-1", "agent-wrong", locks_dir=ld)
    assert r_ref_bad.returncode == 0
    assert json.loads(r_ref_bad.stdout)["refreshed"] is False

    # release
    r_rel = run_lock("release", "task-1", "agent-a", locks_dir=ld)
    assert r_rel.returncode == 0
    assert json.loads(r_rel.stdout)["released"] is True

    # list empty
    r_list2 = run_lock("list", locks_dir=ld)
    assert r_list2.returncode == 0
    assert json.loads(r_list2.stdout) == []


# ── cleanup ──────────────────────────────────────────────────


def test_cleanup_removes_stale(tmp_path: Path) -> None:
    ld = str(tmp_path / "locks")

    # acquire a lock
    run_lock("acquire", "task-old", "agent-a", locks_dir=ld)

    # backdate the heartbeat to make it stale
    lock_file = tmp_path / "locks" / "task-old.lock"
    data = json.loads(lock_file.read_text())
    data["last_heartbeat"] = "2020-01-01T00:00:00+00:00"
    lock_file.write_text(json.dumps(data))

    # cleanup with low max-age
    r = run_lock("cleanup", "--max-age", "60", locks_dir=ld)
    assert r.returncode == 0
    result = json.loads(r.stdout)
    assert "task-old" in result["cleaned"]


def test_cleanup_keeps_fresh(tmp_path: Path) -> None:
    ld = str(tmp_path / "locks")

    run_lock("acquire", "task-fresh", "agent-a", locks_dir=ld)

    r = run_lock("cleanup", "--max-age", "7200", locks_dir=ld)
    assert r.returncode == 0
    assert json.loads(r.stdout)["cleaned"] == []


# ── release wrong owner ──────────────────────────────────────


def test_release_wrong_owner(tmp_path: Path) -> None:
    ld = str(tmp_path / "locks")

    run_lock("acquire", "task-x", "agent-a", locks_dir=ld)
    r = run_lock("release", "task-x", "agent-wrong", locks_dir=ld)
    assert r.returncode == 0
    assert json.loads(r.stdout)["released"] is False


# ── no command ───────────────────────────────────────────────


def test_no_command_returns_nonzero() -> None:
    r = subprocess.run(
        [sys.executable, LOCK_SCRIPT],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode != 0
