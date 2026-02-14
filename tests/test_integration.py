"""Integration tests for multi-agent coordination.

Simulates N agents running concurrently using Python threads to verify
that the board and lock modules handle concurrent access correctly.
All file operations use temporary directories.
"""

import json
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from board import add_task, claim_task, complete_task, get_messages, list_tasks, post_message
from lock import acquire_lock, cleanup_stale, release_lock


NUM_AGENTS = 5
NUM_TASKS = 10
WORK_DURATION = 0.01


def _agent_worker(
    agent_id: str,
    tasks_dir: Path,
    messages_dir: Path,
    results: dict[str, list[str]],
    barrier: threading.Barrier,
    lock: threading.Lock,
) -> None:
    """Simulate an agent: claim tasks, do work, complete, post messages."""
    barrier.wait()
    while True:
        with lock:
            task = claim_task(tasks_dir, agent_id)
        if task is None:
            break
        time.sleep(WORK_DURATION)
        with lock:
            complete_task(tasks_dir, task["id"], agent_id)
            post_message(
                messages_dir,
                from_role=agent_id,
                to_role="orchestrator",
                text=f"Completed task {task['id']}",
            )
            results[agent_id].append(task["id"])


def _run_agents(
    tasks_dir: Path,
    messages_dir: Path,
    num_agents: int = NUM_AGENTS,
    num_tasks: int = NUM_TASKS,
) -> dict[str, list[str]]:
    """Set up tasks, spawn agent threads, return {agent_id: [task_ids]}."""
    tasks_dir.mkdir(parents=True, exist_ok=True)
    messages_dir.mkdir(parents=True, exist_ok=True)

    for i in range(num_tasks):
        add_task(tasks_dir, f"Task {i}", priority=num_tasks - i)

    results: dict[str, list[str]] = {}
    barrier = threading.Barrier(num_agents)
    lock = threading.Lock()
    threads: list[threading.Thread] = []

    for i in range(num_agents):
        agent_id = f"agent-{i}"
        results[agent_id] = []
        t = threading.Thread(
            target=_agent_worker,
            args=(agent_id, tasks_dir, messages_dir, results, barrier, lock),
        )
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    return results


class TestNoDuplicateClaims:
    """5 agents, 10 tasks -- no task claimed by more than one agent."""

    def test_no_duplicate_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            messages_dir = base / "messages"

            results = _run_agents(tasks_dir, messages_dir)

            all_claimed: list[str] = []
            for task_ids in results.values():
                all_claimed.extend(task_ids)

            counts = Counter(all_claimed)
            duplicates = {tid: c for tid, c in counts.items() if c > 1}
            assert not duplicates, f"Tasks claimed by multiple agents: {duplicates}"

            done_tasks = list_tasks(tasks_dir, status_filter="done")
            locked_by_values = [t["locked_by"] for t in done_tasks]
            by_task: dict[str, list[str]] = {}
            for t in done_tasks:
                by_task.setdefault(t["id"], []).append(t["locked_by"])
            for tid, owners in by_task.items():
                assert len(owners) == 1, f"Task {tid} has multiple owners: {owners}"


class TestAllTasksComplete:
    """5 agents, 10 tasks -- all tasks reach done status."""

    def test_all_tasks_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            messages_dir = base / "messages"

            _run_agents(tasks_dir, messages_dir)

            all_tasks = list_tasks(tasks_dir)
            assert len(all_tasks) == NUM_TASKS

            done_tasks = list_tasks(tasks_dir, status_filter="done")
            assert len(done_tasks) == NUM_TASKS, (
                f"Expected {NUM_TASKS} done tasks, got {len(done_tasks)}. "
                f"Statuses: {Counter(t['status'] for t in all_tasks)}"
            )


class TestMessagesDelivered:
    """Agents post messages -- get_messages returns them for the correct role."""

    def test_messages_delivered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tasks_dir = base / "tasks"
            messages_dir = base / "messages"

            results = _run_agents(tasks_dir, messages_dir)

            total_completed = sum(len(v) for v in results.values())

            orchestrator_msgs = get_messages(messages_dir, "orchestrator", unread_only=False)
            assert len(orchestrator_msgs) == total_completed, (
                f"Expected {total_completed} messages, got {len(orchestrator_msgs)}"
            )

            for msg in orchestrator_msgs:
                assert msg["to"] == "orchestrator"
                assert msg["from"].startswith("agent-")
                assert "Completed task" in msg["text"]

            other_msgs = get_messages(messages_dir, "nonexistent-role", unread_only=False)
            assert len(other_msgs) == 0


class TestStaleLockCleanup:
    """Create a lock with old heartbeat -- cleanup_stale removes it."""

    def test_stale_lock_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            locks_dir = Path(tmp) / "locks"
            locks_dir.mkdir(parents=True, exist_ok=True)

            assert acquire_lock(locks_dir, "task-old", "agent-0")
            assert acquire_lock(locks_dir, "task-fresh", "agent-1")

            old_lock_path = locks_dir / "task-old.lock"
            old_data = json.loads(old_lock_path.read_text())
            stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
            old_data["last_heartbeat"] = stale_time
            old_lock_path.write_text(json.dumps(old_data, indent=2))

            cleaned = cleanup_stale(locks_dir, max_age_seconds=7200)

            assert "task-old" in cleaned, f"Expected task-old in cleaned, got {cleaned}"
            assert "task-fresh" not in cleaned
            assert not old_lock_path.exists()
            assert (locks_dir / "task-fresh.lock").exists()


class TestClaimReturnsNoneOnEmptyBoard:
    """When all tasks are claimed, new claim returns None."""

    def test_claim_returns_none_on_empty_board(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_dir = Path(tmp) / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)

            result = claim_task(tasks_dir, "agent-lonely")
            assert result is None

    def test_claim_returns_none_when_all_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_dir = Path(tmp) / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)

            add_task(tasks_dir, "Only task", priority=1)

            claimed = claim_task(tasks_dir, "agent-0")
            assert claimed is not None

            second = claim_task(tasks_dir, "agent-1")
            assert second is None

    def test_claim_returns_none_when_all_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_dir = Path(tmp) / "tasks"
            tasks_dir.mkdir(parents=True, exist_ok=True)

            tid = add_task(tasks_dir, "Finish me", priority=1)
            claimed = claim_task(tasks_dir, "agent-0")
            assert claimed is not None
            complete_task(tasks_dir, tid, "agent-0")

            result = claim_task(tasks_dir, "agent-1")
            assert result is None
