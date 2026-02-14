"""CLI tests for scripts/board.py — exercises all subcommands via subprocess."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BOARD_SCRIPT = str(Path(__file__).resolve().parent.parent / "scripts" / "board.py")


def run_board(*args: str, tasks_dir: str = "", messages_dir: str = "") -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, BOARD_SCRIPT]
    if tasks_dir:
        cmd += ["--tasks-dir", tasks_dir]
    if messages_dir:
        cmd += ["--messages-dir", messages_dir]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)


# ── add / list / claim / complete cycle ──────────────────────


def test_add_list_claim_complete_cycle(tmp_path: Path) -> None:
    td = str(tmp_path / "tasks")
    md = str(tmp_path / "messages")

    # add two tasks
    r1 = run_board("add", "Task A", "--priority", "3", tasks_dir=td, messages_dir=md)
    assert r1.returncode == 0
    j1 = json.loads(r1.stdout)
    assert j1["status"] == "created"
    task_a_id = j1["task_id"]

    r2 = run_board("add", "Task B", "--priority", "1", tasks_dir=td, messages_dir=md)
    assert r2.returncode == 0

    # list all
    r_list = run_board("list", tasks_dir=td, messages_dir=md)
    assert r_list.returncode == 0
    tasks = json.loads(r_list.stdout)
    assert len(tasks) == 2

    # list by status
    r_open = run_board("list", "--status", "open", tasks_dir=td, messages_dir=md)
    assert r_open.returncode == 0
    assert len(json.loads(r_open.stdout)) == 2

    # claim (should get Task A — higher priority)
    r_claim = run_board("claim", "agent-1", tasks_dir=td, messages_dir=md)
    assert r_claim.returncode == 0
    claimed = json.loads(r_claim.stdout)["task"]
    assert claimed is not None
    assert claimed["description"] == "Task A"

    # complete
    r_done = run_board("complete", task_a_id, "agent-1", tasks_dir=td, messages_dir=md)
    assert r_done.returncode == 0
    assert json.loads(r_done.stdout)["status"] == "completed"

    # list done
    r_done_list = run_board("list", "--status", "done", tasks_dir=td, messages_dir=md)
    assert r_done_list.returncode == 0
    assert len(json.loads(r_done_list.stdout)) == 1


def test_fail_task_via_cli(tmp_path: Path) -> None:
    td = str(tmp_path / "tasks")
    md = str(tmp_path / "messages")

    r_add = run_board("add", "Doomed task", tasks_dir=td, messages_dir=md)
    tid = json.loads(r_add.stdout)["task_id"]

    run_board("claim", "agent-1", tasks_dir=td, messages_dir=md)

    r_fail = run_board("fail", tid, "agent-1", "Tests broke", tasks_dir=td, messages_dir=md)
    assert r_fail.returncode == 0
    assert json.loads(r_fail.stdout)["status"] == "failed"


def test_claim_empty_board(tmp_path: Path) -> None:
    td = str(tmp_path / "tasks")
    md = str(tmp_path / "messages")

    r = run_board("claim", "agent-1", tasks_dir=td, messages_dir=md)
    assert r.returncode == 0
    assert json.loads(r.stdout)["task"] is None


# ── message round-trip ───────────────────────────────────────


def test_message_roundtrip(tmp_path: Path) -> None:
    td = str(tmp_path / "tasks")
    md = str(tmp_path / "messages")

    # post message
    r_msg = run_board("message", "reviewer", "implementer", "Fix the bug", tasks_dir=td, messages_dir=md)
    assert r_msg.returncode == 0
    msg_id = json.loads(r_msg.stdout)["msg_id"]

    # get messages (all, not just unread)
    r_msgs = run_board("messages", "implementer", tasks_dir=td, messages_dir=md)
    assert r_msgs.returncode == 0
    msgs = json.loads(r_msgs.stdout)
    assert len(msgs) == 1
    assert msgs[0]["text"] == "Fix the bug"

    # get unread
    r_unread = run_board("messages", "implementer", "--unread", tasks_dir=td, messages_dir=md)
    assert r_unread.returncode == 0
    assert len(json.loads(r_unread.stdout)) == 1

    # mark read
    r_mr = run_board("mark-read", msg_id, tasks_dir=td, messages_dir=md)
    assert r_mr.returncode == 0
    assert json.loads(r_mr.stdout)["status"] == "read"

    # unread now empty
    r_unread2 = run_board("messages", "implementer", "--unread", tasks_dir=td, messages_dir=md)
    assert r_unread2.returncode == 0
    assert len(json.loads(r_unread2.stdout)) == 0


# ── error cases ──────────────────────────────────────────────


def test_complete_wrong_owner_returns_nonzero(tmp_path: Path) -> None:
    td = str(tmp_path / "tasks")
    md = str(tmp_path / "messages")

    r_add = run_board("add", "Some task", tasks_dir=td, messages_dir=md)
    tid = json.loads(r_add.stdout)["task_id"]
    run_board("claim", "agent-1", tasks_dir=td, messages_dir=md)

    r = run_board("complete", tid, "agent-wrong", tasks_dir=td, messages_dir=md)
    assert r.returncode != 0
    assert r.stderr.strip() != ""


def test_no_command_returns_nonzero(tmp_path: Path) -> None:
    r = subprocess.run(
        [sys.executable, BOARD_SCRIPT],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode != 0
