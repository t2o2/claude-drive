"""Tests for scripts/board.py — task board operations with file-per-task architecture."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from board import (
    add_task,
    list_tasks,
    claim_task,
    complete_task,
    fail_task,
    post_message,
    get_messages,
    mark_read,
    archive_done,
)


@pytest.fixture
def tasks_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tasks"
    d.mkdir()
    return d


@pytest.fixture
def messages_dir(tmp_path: Path) -> Path:
    d = tmp_path / "messages"
    d.mkdir()
    return d


@pytest.fixture
def archive_dir(tmp_path: Path) -> Path:
    d = tmp_path / "archive"
    d.mkdir()
    return d


# ── Task CRUD ──────────────────────────────────────────────


def test_add_task_creates_file(tasks_dir: Path) -> None:
    task_id = add_task(tasks_dir, "Implement feature X", priority=2)

    task_file = tasks_dir / f"{task_id}.json"
    assert task_file.exists()

    data = json.loads(task_file.read_text())
    assert data["id"] == task_id
    assert data["description"] == "Implement feature X"
    assert data["status"] == "open"
    assert data["locked_by"] is None
    assert data["priority"] == 2
    assert data["created_at"] is not None
    assert data["completed_at"] is None
    assert data["heartbeat"] is None


def test_add_task_default_priority(tasks_dir: Path) -> None:
    task_id = add_task(tasks_dir, "Low priority task")
    data = json.loads((tasks_dir / f"{task_id}.json").read_text())
    assert data["priority"] == 1


def test_list_tasks_returns_all(tasks_dir: Path) -> None:
    add_task(tasks_dir, "Task A")
    add_task(tasks_dir, "Task B")
    add_task(tasks_dir, "Task C")

    tasks = list_tasks(tasks_dir)
    assert len(tasks) == 3
    descriptions = {t["description"] for t in tasks}
    assert descriptions == {"Task A", "Task B", "Task C"}


def test_list_tasks_filters_by_status(tasks_dir: Path) -> None:
    add_task(tasks_dir, "Open task")
    add_task(tasks_dir, "Will be locked")

    claim_task(tasks_dir, "agent-1")

    open_tasks = list_tasks(tasks_dir, status_filter="open")
    locked_tasks = list_tasks(tasks_dir, status_filter="locked")

    assert len(open_tasks) == 1
    assert (
        open_tasks[0]["description"] == "Open task" or open_tasks[0]["status"] == "open"
    )
    assert len(locked_tasks) == 1
    assert locked_tasks[0]["status"] == "locked"


def test_list_tasks_empty_dir(tasks_dir: Path) -> None:
    tasks = list_tasks(tasks_dir)
    assert tasks == []


# ── Claim ──────────────────────────────────────────────────


def test_claim_task_picks_highest_priority(tasks_dir: Path) -> None:
    add_task(tasks_dir, "Low priority", priority=1)
    add_task(tasks_dir, "High priority", priority=5)
    add_task(tasks_dir, "Medium priority", priority=3)

    claimed = claim_task(tasks_dir, "agent-1")
    assert claimed is not None
    assert claimed["description"] == "High priority"
    assert claimed["status"] == "locked"
    assert claimed["locked_by"] == "agent-1"


def test_claim_task_returns_none_when_empty(tasks_dir: Path) -> None:
    result = claim_task(tasks_dir, "agent-1")
    assert result is None


def test_claim_task_skips_locked(tasks_dir: Path) -> None:
    add_task(tasks_dir, "Task A", priority=5)
    add_task(tasks_dir, "Task B", priority=3)

    claim_task(tasks_dir, "agent-1")

    claimed = claim_task(tasks_dir, "agent-2")
    assert claimed is not None
    assert claimed["description"] == "Task B"
    assert claimed["locked_by"] == "agent-2"


def test_claim_task_returns_none_all_locked(tasks_dir: Path) -> None:
    add_task(tasks_dir, "Only task", priority=1)
    claim_task(tasks_dir, "agent-1")

    result = claim_task(tasks_dir, "agent-2")
    assert result is None


# ── Complete / Fail ────────────────────────────────────────


def test_complete_task_sets_done(tasks_dir: Path) -> None:
    tid = add_task(tasks_dir, "Do something")
    claim_task(tasks_dir, "agent-1")

    complete_task(tasks_dir, tid, "agent-1")

    data = json.loads((tasks_dir / f"{tid}.json").read_text())
    assert data["status"] == "done"
    assert data["completed_at"] is not None
    assert data["locked_by"] == "agent-1"


def test_complete_task_rejects_wrong_owner(tasks_dir: Path) -> None:
    tid = add_task(tasks_dir, "Do something")
    claim_task(tasks_dir, "agent-1")

    with pytest.raises(PermissionError):
        complete_task(tasks_dir, tid, "agent-2")


def test_complete_task_rejects_unclaimed(tasks_dir: Path) -> None:
    tid = add_task(tasks_dir, "Unclaimed task")

    with pytest.raises(PermissionError):
        complete_task(tasks_dir, tid, "agent-1")


def test_fail_task_sets_failed(tasks_dir: Path) -> None:
    tid = add_task(tasks_dir, "Doomed task")
    claim_task(tasks_dir, "agent-1")

    fail_task(tasks_dir, tid, "agent-1", "Tests failed")

    data = json.loads((tasks_dir / f"{tid}.json").read_text())
    assert data["status"] == "failed"
    assert data["completed_at"] is not None
    assert data["reason"] == "Tests failed"


def test_fail_task_rejects_wrong_owner(tasks_dir: Path) -> None:
    tid = add_task(tasks_dir, "Doomed task")
    claim_task(tasks_dir, "agent-1")

    with pytest.raises(PermissionError):
        fail_task(tasks_dir, tid, "agent-2", "Not my task")


# ── Messages ───────────────────────────────────────────────


def test_post_message_creates_file(messages_dir: Path) -> None:
    msg_id = post_message(messages_dir, "reviewer", "implementer", "Fix the bug")

    msg_file = messages_dir / f"{msg_id}.json"
    assert msg_file.exists()

    data = json.loads(msg_file.read_text())
    assert data["id"] == msg_id
    assert data["from"] == "reviewer"
    assert data["to"] == "implementer"
    assert data["text"] == "Fix the bug"
    assert data["read"] is False
    assert data["timestamp"] is not None


def test_get_messages_filters_by_role(messages_dir: Path) -> None:
    post_message(messages_dir, "reviewer", "implementer", "Fix bug A")
    post_message(messages_dir, "reviewer", "docs", "Update readme")
    post_message(messages_dir, "janitor", "implementer", "Lint warning")

    impl_msgs = get_messages(messages_dir, "implementer", unread_only=False)
    assert len(impl_msgs) == 2
    texts = {m["text"] for m in impl_msgs}
    assert texts == {"Fix bug A", "Lint warning"}


def test_get_messages_unread_only(messages_dir: Path) -> None:
    msg_id = post_message(messages_dir, "reviewer", "implementer", "Read this")
    post_message(messages_dir, "reviewer", "implementer", "Unread msg")

    mark_read(messages_dir, msg_id)

    unread = get_messages(messages_dir, "implementer", unread_only=True)
    assert len(unread) == 1
    assert unread[0]["text"] == "Unread msg"


def test_get_messages_all(messages_dir: Path) -> None:
    post_message(messages_dir, "reviewer", "implementer", "Msg 1")
    msg2 = post_message(messages_dir, "reviewer", "implementer", "Msg 2")
    mark_read(messages_dir, msg2)

    all_msgs = get_messages(messages_dir, "implementer", unread_only=False)
    assert len(all_msgs) == 2


def test_mark_read(messages_dir: Path) -> None:
    msg_id = post_message(messages_dir, "reviewer", "implementer", "Read me")

    mark_read(messages_dir, msg_id)

    data = json.loads((messages_dir / f"{msg_id}.json").read_text())
    assert data["read"] is True


# ── Archive ────────────────────────────────────────────────


def test_archive_done_moves_old_tasks(tasks_dir: Path, archive_dir: Path) -> None:
    old_id = add_task(tasks_dir, "Old done task")
    new_id = add_task(tasks_dir, "Recent done task")

    # Claim and complete both
    claim_task(tasks_dir, "agent-1")
    claim_task(tasks_dir, "agent-1")
    complete_task(tasks_dir, old_id, "agent-1")
    complete_task(tasks_dir, new_id, "agent-1")

    # Backdate the old task's completed_at
    old_file = tasks_dir / f"{old_id}.json"
    data = json.loads(old_file.read_text())
    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    data["completed_at"] = old_time
    old_file.write_text(json.dumps(data))

    archive_done(tasks_dir, archive_dir, older_than_days=7)

    # Old task moved to archive
    assert not (tasks_dir / f"{old_id}.json").exists()
    assert (archive_dir / f"{old_id}.json").exists()

    # Recent task stays
    assert (tasks_dir / f"{new_id}.json").exists()
    assert not (archive_dir / f"{new_id}.json").exists()


def test_archive_done_skips_open_tasks(tasks_dir: Path, archive_dir: Path) -> None:
    tid = add_task(tasks_dir, "Still open")

    archive_done(tasks_dir, archive_dir, older_than_days=0)

    assert (tasks_dir / f"{tid}.json").exists()
    assert not list(archive_dir.iterdir())


# ── Concurrency-like ───────────────────────────────────────


def test_sequential_claims_return_different_tasks(tasks_dir: Path) -> None:
    for i in range(5):
        add_task(tasks_dir, f"Task {i}", priority=i)

    claimed_ids: list[str] = []
    for i in range(5):
        result = claim_task(tasks_dir, f"agent-{i}")
        assert result is not None
        claimed_ids.append(result["id"])

    # All claimed IDs should be unique
    assert len(set(claimed_ids)) == 5

    # No more tasks available
    assert claim_task(tasks_dir, "agent-extra") is None
