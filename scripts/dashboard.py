# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi[standard]"]
# ///
"""Multi-agent dashboard — FastAPI + htmx + Pico CSS.

Run: uv run scripts/dashboard.py
Open: http://localhost:8000
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Import board and lock from same directory
sys.path.insert(0, str(SCRIPT_DIR))
import board  # noqa: E402
import lock  # noqa: E402

TASKS_DIR = PROJECT_ROOT / ".drive" / "agents" / "tasks"
LOCKS_DIR = PROJECT_ROOT / ".drive" / "agents" / "locks"
MESSAGES_DIR = PROJECT_ROOT / ".drive" / "agents" / "messages"
ARCHIVE_DIR = PROJECT_ROOT / ".drive" / "agents" / "archive"

app = FastAPI(title="Agent Dashboard")
templates = Jinja2Templates(directory=str(SCRIPT_DIR / "templates"))


# ── Jinja2 filters ────────────────────────────────────────


def _timeago(iso_str: str | None) -> str:
    """Convert ISO timestamp to relative time string."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except (ValueError, TypeError):
        return "—"


templates.env.filters["timeago"] = _timeago


# ── Helpers ───────────────────────────────────────────────


def _ensure_dirs() -> None:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    MESSAGES_DIR.mkdir(parents=True, exist_ok=True)


def _get_grouped_tasks() -> dict[str, list[dict]]:
    """Group tasks by status, sorted by priority descending."""
    _ensure_dirs()
    all_tasks = board.list_tasks(TASKS_DIR)
    groups: dict[str, list[dict]] = {
        "open": [],
        "locked": [],
        "done": [],
        "failed": [],
    }
    for t in all_tasks:
        status = t.get("status", "open")
        if status in groups:
            groups[status].append(t)
    for status_list in groups.values():
        status_list.sort(key=lambda t: t.get("priority", 0), reverse=True)
    return groups


def _get_all_messages(limit: int = 50) -> list[dict]:
    """Read all messages, sorted by timestamp descending."""
    _ensure_dirs()
    messages: list[dict] = []
    for path in MESSAGES_DIR.glob("*.json"):
        try:
            messages.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    messages.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
    return messages[:limit]


def _annotate_locks() -> list[dict]:
    """List locks with freshness annotation."""
    _ensure_dirs()
    locks = lock.list_locks(LOCKS_DIR)
    now = datetime.now(timezone.utc)
    for lk in locks:
        try:
            hb = datetime.fromisoformat(lk["last_heartbeat"])
            age_minutes = (now - hb).total_seconds() / 60
            lk["fresh"] = age_minutes < 10
            lk["heartbeat_ago"] = _timeago(lk["last_heartbeat"])
        except (ValueError, KeyError):
            lk["fresh"] = False
            lk["heartbeat_ago"] = "—"
        lk["acquired_ago"] = _timeago(lk.get("acquired_at"))
    return locks


def _get_stats() -> dict:
    """Compute task counts and agent stats."""
    groups = _get_grouped_tasks()
    total = sum(len(v) for v in groups.values())
    done_count = len(groups["done"])
    completion = round(done_count / total * 100) if total > 0 else 0
    locks = _annotate_locks()
    active_agents = len([lk for lk in locks if lk["fresh"]])
    return {
        "open": len(groups["open"]),
        "locked": len(groups["locked"]),
        "done": done_count,
        "failed": len(groups["failed"]),
        "total": total,
        "completion": completion,
        "active_agents": active_agents,
    }


# ── Routes: Full page ────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "partial": None,
            "groups": _get_grouped_tasks(),
            "stats": _get_stats(),
            "locks": _annotate_locks(),
            "messages": _get_all_messages(),
        },
    )


# ── Routes: Partials (htmx) ──────────────────────────────


@app.get("/partials/board", response_class=HTMLResponse)
async def partial_board(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "board", "groups": _get_grouped_tasks()},
    )


@app.get("/partials/stats", response_class=HTMLResponse)
async def partial_stats(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "stats", "stats": _get_stats()},
    )


@app.get("/partials/agents", response_class=HTMLResponse)
async def partial_agents(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "agents", "locks": _annotate_locks()},
    )


@app.get("/partials/messages", response_class=HTMLResponse)
async def partial_messages(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "messages", "messages": _get_all_messages()},
    )


# ── Routes: Actions ──────────────────────────────────────


@app.post("/tasks", response_class=HTMLResponse)
async def add_task(
    request: Request,
    description: str = Form(...),
    priority: int = Form(1),
):
    _ensure_dirs()
    board.add_task(TASKS_DIR, description, priority=priority)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "board", "groups": _get_grouped_tasks()},
    )


@app.post("/tasks/{task_id}/reopen", response_class=HTMLResponse)
async def reopen_task(request: Request, task_id: str):
    task_path = TASKS_DIR / f"{task_id}.json"
    if task_path.exists():
        task = json.loads(task_path.read_text())
        task["status"] = "open"
        task["locked_by"] = None
        task["heartbeat"] = None
        task["completed_at"] = None
        task_path.write_text(json.dumps(task, indent=2))
        # Clean up associated lock file
        lock_path = LOCKS_DIR / f"{task_id}.lock"
        if lock_path.exists():
            lock_path.unlink()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "board", "groups": _get_grouped_tasks()},
    )


@app.post("/tasks/{task_id}/delete", response_class=HTMLResponse)
async def delete_task(request: Request, task_id: str):
    task_path = TASKS_DIR / f"{task_id}.json"
    if task_path.exists():
        task_path.unlink()
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        lock_path.unlink()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "board", "groups": _get_grouped_tasks()},
    )


@app.post("/locks/cleanup", response_class=HTMLResponse)
async def cleanup_locks(request: Request):
    _ensure_dirs()
    lock.cleanup_stale(LOCKS_DIR)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "agents", "locks": _annotate_locks()},
    )


@app.post("/tasks/archive", response_class=HTMLResponse)
async def archive_tasks(request: Request):
    _ensure_dirs()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    board.archive_done(TASKS_DIR, ARCHIVE_DIR)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "partial": "board", "groups": _get_grouped_tasks()},
    )


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
