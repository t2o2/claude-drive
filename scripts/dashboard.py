# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi[standard]"]
# ///
"""Multi-agent dashboard — FastAPI + htmx + Pico CSS.

Run: uv run scripts/dashboard.py
Open: http://localhost:8000
"""

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Import board, lock, and orchestrator from same directory
sys.path.insert(0, str(SCRIPT_DIR))
import board  # noqa: E402
import lock  # noqa: E402
import orchestrator  # noqa: E402
import validate_agent_config  # noqa: E402

TASKS_DIR = PROJECT_ROOT / ".drive" / "agents" / "tasks"
LOCKS_DIR = PROJECT_ROOT / ".drive" / "agents" / "locks"
MESSAGES_DIR = PROJECT_ROOT / ".drive" / "agents" / "messages"
ARCHIVE_DIR = PROJECT_ROOT / ".drive" / "agents" / "archive"
CONFIG_PATH = PROJECT_ROOT / ".drive" / "agents" / "config.json"
UPSTREAM_PATH = PROJECT_ROOT / ".drive" / "upstream"

AGENT_ID_RE = re.compile(r"^[a-z0-9-]+$")

HEALTH_CHECK_INTERVAL = 30
MAX_RESTARTS = 3


async def _health_check() -> None:
    """Check agent health: detect crashed containers and auto-restart."""
    async with _fleet_lock:
        if not _fleet_state:
            return

        # Get currently running containers
        running = orchestrator.list_running_agents()
        running_ids = {a["container_id"] for a in running}

        for agent_id, state in _fleet_state.items():
            container_id = state.get("container_id", "")
            if not container_id:
                continue

            if container_id in running_ids:
                state["status"] = "healthy"
            else:
                # Container not running — crashed or stopped
                restart_count = state.get("restart_count", 0)
                if restart_count < MAX_RESTARTS:
                    result = orchestrator.restart_agent(container_id)
                    state["status"] = (
                        "restarting" if result["status"] == "running" else "crashed"
                    )
                    state["restart_count"] = restart_count + 1
                else:
                    state["status"] = "crashed"


async def _health_monitor_loop() -> None:
    """Background loop that runs health checks every 30s."""
    while True:
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
        try:
            await _health_check()
        except Exception:
            pass  # Don't crash the background task


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Reconstruct fleet state and start health monitor on startup."""
    _reconstruct_fleet_state()
    task = asyncio.create_task(_health_monitor_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Agent Dashboard", lifespan=_lifespan)
templates = Jinja2Templates(directory=str(SCRIPT_DIR / "templates"))

# Fleet state: agent_id -> {status, container_id, started_at, role, model, restart_count}
_fleet_state: dict[str, dict] = {}
_fleet_lock = asyncio.Lock()


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


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


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


def _get_agent_cards() -> list[dict]:
    """Merge fleet state (containers) with lock data (task assignments).

    Returns list of agent card dicts with fields:
    agent_id, role, status, container_id, task_id, heartbeat_ago, uptime, fresh, orphaned_lock
    """
    cards: dict[str, dict] = {}

    # Start from fleet state (container info)
    for agent_id, state in _fleet_state.items():
        cards[agent_id] = {
            "agent_id": agent_id,
            "role": state.get("role", ""),
            "status": state.get("status", "unknown"),
            "container_id": state.get("container_id", ""),
            "task_id": None,
            "heartbeat_ago": "—",
            "uptime": _timeago(state.get("started_at")),
            "fresh": state.get("status") == "running",
            "orphaned_lock": False,
        }

    # Enrich with lock data (task assignment, heartbeat)
    locks = _annotate_locks()
    for lk in locks:
        agent_id = lk.get("agent_id", "")
        if agent_id in cards:
            cards[agent_id]["task_id"] = lk.get("task_id")
            cards[agent_id]["heartbeat_ago"] = lk.get("heartbeat_ago", "—")
            cards[agent_id]["fresh"] = lk.get("fresh", False)
        else:
            # Lock exists but no container — orphaned lock
            cards[agent_id] = {
                "agent_id": agent_id,
                "role": "",
                "status": "no container",
                "container_id": "",
                "task_id": lk.get("task_id"),
                "heartbeat_ago": lk.get("heartbeat_ago", "—"),
                "uptime": "—",
                "fresh": False,
                "orphaned_lock": True,
            }

    return sorted(cards.values(), key=lambda c: c["agent_id"])


def _get_fleet_context() -> dict:
    """Build template context for fleet controls section."""
    config = _load_config()
    runtime = config.get("runtime", "docker")
    running_count = sum(
        1 for a in _fleet_state.values() if a.get("status") == "running"
    )
    fleet_status = "running" if running_count > 0 else "stopped"
    open_tasks = len(_get_grouped_tasks().get("open", []))
    return {
        "fleet_status": fleet_status,
        "fleet_count": running_count,
        "fleet_total": len(_fleet_state),
        "open_tasks": open_tasks,
        "runtime": runtime,
    }


# ── Routes: Full page ────────────────────────────────────


def _render(
    request: Request, partial: str | None = None, **ctx: object
) -> HTMLResponse:
    """Render dashboard template with the new TemplateResponse API."""
    return templates.TemplateResponse(
        request, "dashboard.html", {"partial": partial, **ctx}
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render(
        request,
        groups=_get_grouped_tasks(),
        stats=_get_stats(),
        locks=_annotate_locks(),
        agent_cards=_get_agent_cards(),
        messages=_get_all_messages(),
        fleet=_get_fleet_context(),
        config=_load_config(),
        config_errors=[],
    )


# ── Routes: Partials (htmx) ──────────────────────────────


@app.get("/partials/fleet", response_class=HTMLResponse)
async def partial_fleet(request: Request):
    return _render(request, "fleet", fleet=_get_fleet_context())


@app.get("/partials/board", response_class=HTMLResponse)
async def partial_board(request: Request):
    return _render(request, "board", groups=_get_grouped_tasks())


@app.get("/partials/stats", response_class=HTMLResponse)
async def partial_stats(request: Request):
    return _render(request, "stats", stats=_get_stats())


@app.get("/partials/agents", response_class=HTMLResponse)
async def partial_agents(request: Request):
    return _render(
        request, "agents", locks=_annotate_locks(), agent_cards=_get_agent_cards()
    )


@app.get("/partials/messages", response_class=HTMLResponse)
async def partial_messages(request: Request):
    return _render(request, "messages", messages=_get_all_messages())


# ── Routes: Actions ──────────────────────────────────────


@app.post("/tasks", response_class=HTMLResponse)
async def add_task(
    request: Request,
    description: str = Form(...),
    priority: int = Form(1),
):
    _ensure_dirs()
    board.add_task(TASKS_DIR, description, priority=priority)
    return _render(request, "board", groups=_get_grouped_tasks())


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
        lock_path = LOCKS_DIR / f"{task_id}.lock"
        if lock_path.exists():
            lock_path.unlink()
    return _render(request, "board", groups=_get_grouped_tasks())


@app.post("/tasks/{task_id}/delete", response_class=HTMLResponse)
async def delete_task(request: Request, task_id: str):
    task_path = TASKS_DIR / f"{task_id}.json"
    if task_path.exists():
        task_path.unlink()
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        lock_path.unlink()
    return _render(request, "board", groups=_get_grouped_tasks())


@app.post("/locks/cleanup", response_class=HTMLResponse)
async def cleanup_locks(request: Request):
    _ensure_dirs()
    lock.cleanup_stale(LOCKS_DIR)
    return _render(request, "agents", locks=_annotate_locks())


@app.post("/tasks/archive", response_class=HTMLResponse)
async def archive_tasks(request: Request):
    _ensure_dirs()
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    board.archive_done(TASKS_DIR, ARCHIVE_DIR)
    return _render(request, "board", groups=_get_grouped_tasks())


# ── Log endpoints ────────────────────────────────────────


@app.get("/agents/{agent_id}/logs", response_class=HTMLResponse)
async def agent_logs_static(agent_id: str):
    """Return last 100 lines of agent logs as HTML pre block."""
    if not _validate_agent_id(agent_id):
        return JSONResponse({"error": "Invalid agent_id"}, status_code=400)

    async with _fleet_lock:
        if agent_id not in _fleet_state:
            return JSONResponse({"error": "Agent not found"}, status_code=404)
        container_id = _fleet_state[agent_id]["container_id"]

    raw = orchestrator.get_agent_logs(container_id, lines=100)
    clean = _strip_ansi(raw)
    return HTMLResponse(
        f"<pre style='font-size:0.8rem;white-space:pre-wrap;'>{clean}</pre>"
    )


@app.websocket("/agents/{agent_id}/logs/ws")
async def agent_logs_ws(websocket: WebSocket, agent_id: str):
    """Stream live container logs over WebSocket."""
    if not _validate_agent_id(agent_id):
        await websocket.close(code=1008, reason="Invalid agent_id")
        return

    async with _fleet_lock:
        if agent_id not in _fleet_state:
            await websocket.close(code=1008, reason="Agent not found")
            return
        container_id = _fleet_state[agent_id]["container_id"]

    await websocket.accept()
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "logs",
            "--tail",
            "100",
            "-f",
            container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        lines_per_sec = 0
        import time

        last_reset = time.monotonic()

        while True:
            assert proc.stdout is not None
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=30.0)
            if not line:
                break
            # Rate limiting: max 500 lines/sec
            now = time.monotonic()
            if now - last_reset >= 1.0:
                lines_per_sec = 0
                last_reset = now
            lines_per_sec += 1
            if lines_per_sec > 500:
                if lines_per_sec == 501:
                    await websocket.send_text("[log output throttled]")
                continue
            clean = _strip_ansi(line.decode("utf-8", errors="replace").rstrip())
            await websocket.send_text(clean)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if proc and proc.returncode is None:
            proc.kill()
            await proc.wait()


# ── Config management routes ─────────────────────────────


@app.get("/config")
async def get_config():
    """Return current config as JSON."""
    config = _load_config()
    return JSONResponse(config)


@app.post("/config", response_class=HTMLResponse)
async def save_config(request: Request, config_json: str = Form(...)):
    """Validate and save config. Returns config partial with errors if invalid."""
    try:
        new_config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return _render(
            request,
            "config",
            config=_load_config(),
            config_errors=[f"Invalid JSON: {e}"],
        )

    errors = validate_agent_config.validate(new_config)
    if errors:
        return _render(request, "config", config=_load_config(), config_errors=errors)

    # Backup before save
    if CONFIG_PATH.exists():
        backup = CONFIG_PATH.with_suffix(".json.bak")
        backup.write_text(CONFIG_PATH.read_text())

    CONFIG_PATH.write_text(json.dumps(new_config, indent=2))
    return _render(request, "config", config=new_config, config_errors=[])


@app.get("/partials/config", response_class=HTMLResponse)
async def partial_config(request: Request):
    return _render(request, "config", config=_load_config(), config_errors=[])


# ── Fleet state helpers ──────────────────────────────────

# Env vars forwarded from host to agent containers
_FORWARD_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "API_TIMEOUT_MS",
]


def _load_config() -> dict:
    """Load agent config from .drive/agents/config.json."""
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def _build_provider_env(config: dict) -> dict[str, str]:
    """Build provider env vars from config.provider block + host environment.

    Config example for GLM-5:
      "provider": {
        "base_url": "https://api.z.ai/api/anthropic",
        "auth_token": "your-zai-key",
        "default_model": "glm-5"
      }
    """
    env: dict[str, str] = {}

    # 1. Forward matching env vars from host
    for key in _FORWARD_ENV_VARS:
        val = os.environ.get(key)
        if val:
            env[key] = val

    # 2. Override from config.provider block
    provider = config.get("provider", {})
    if provider.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = provider["base_url"]
    if provider.get("auth_token"):
        env["ANTHROPIC_AUTH_TOKEN"] = provider["auth_token"]
    if provider.get("default_model"):
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = provider["default_model"]
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = provider["default_model"]
    if provider.get("timeout_ms"):
        env["API_TIMEOUT_MS"] = str(provider["timeout_ms"])

    return env


def _reconstruct_fleet_state() -> None:
    """Reconstruct fleet state from running Docker containers."""
    _fleet_state.clear()
    prefix = orchestrator.CONTAINER_PREFIX
    for agent in orchestrator.list_running_agents():
        name = agent["name"]
        if name.startswith(prefix):
            agent_id = name[len(prefix) :]
            _fleet_state[agent_id] = {
                "status": "running",
                "container_id": agent["container_id"],
                "started_at": None,
                "role": agent_id.rsplit("-", 1)[0] if "-" in agent_id else agent_id,
                "model": "",
                "restart_count": 0,
            }


def _validate_agent_id(agent_id: str) -> bool:
    """Validate agent_id format."""
    return bool(AGENT_ID_RE.match(agent_id))


# ── Fleet control routes ─────────────────────────────────


def _run_preflight_checks() -> list[dict]:
    """Run preflight checks before fleet start. Returns list of {name, status, message}."""
    checks = []

    # 1. Docker daemon running
    try:
        result = orchestrator._run(["docker", "ps"], timeout=10)
        if result.returncode == 0:
            checks.append(
                {
                    "name": "Docker daemon",
                    "status": "pass",
                    "message": "Docker is running",
                }
            )
        else:
            checks.append(
                {
                    "name": "Docker daemon",
                    "status": "fail",
                    "message": "Docker daemon not responding",
                }
            )
    except Exception:
        checks.append(
            {"name": "Docker daemon", "status": "fail", "message": "Docker not found"}
        )

    # 2. Docker image exists
    config = _load_config()
    image = config.get("docker", {}).get("image", "claude-drive-agent")
    try:
        result = orchestrator._run(["docker", "images", "-q", image], timeout=10)
        if result.stdout.strip():
            checks.append(
                {
                    "name": "Docker image",
                    "status": "pass",
                    "message": f"Image '{image}' found",
                }
            )
        else:
            checks.append(
                {
                    "name": "Docker image",
                    "status": "fail",
                    "message": f"Image '{image}' not found. Build required.",
                }
            )
    except Exception:
        checks.append(
            {
                "name": "Docker image",
                "status": "fail",
                "message": "Could not check Docker images",
            }
        )

    # 3. Credentials exist
    creds_path = Path.home() / ".claude" / "credentials.json"
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if creds_path.exists():
        checks.append(
            {
                "name": "Credentials",
                "status": "pass",
                "message": "credentials.json found",
            }
        )
    elif api_key:
        checks.append(
            {
                "name": "Credentials",
                "status": "pass",
                "message": "ANTHROPIC_API_KEY set",
            }
        )
    else:
        checks.append(
            {
                "name": "Credentials",
                "status": "fail",
                "message": "No credentials.json or ANTHROPIC_API_KEY",
            }
        )

    # 4. Config valid
    errors = validate_agent_config.validate(config) if config else ["No config found"]
    if not errors:
        checks.append(
            {"name": "Config valid", "status": "pass", "message": "Config is valid"}
        )
    else:
        checks.append(
            {"name": "Config valid", "status": "fail", "message": "; ".join(errors)}
        )

    # 5. Open tasks on board
    groups = _get_grouped_tasks()
    open_count = len(groups.get("open", []))
    if open_count > 0:
        checks.append(
            {
                "name": "Open tasks",
                "status": "pass",
                "message": f"{open_count} open tasks",
            }
        )
    else:
        checks.append(
            {
                "name": "Open tasks",
                "status": "warn",
                "message": "No open tasks on board",
            }
        )

    return checks


@app.get("/fleet/preflight")
async def fleet_preflight():
    """Run preflight checks and return results."""
    checks = _run_preflight_checks()
    return JSONResponse({"checks": checks})


@app.post("/fleet/start")
async def fleet_start():
    """Start all agents per config."""
    config = _load_config()
    if not config.get("roles"):
        return JSONResponse({"error": "No roles configured"}, status_code=400)

    async with _fleet_lock:
        branch = config.get("sync", {}).get("branch", "main")
        upstream = PROJECT_ROOT / config.get("sync", {}).get(
            "upstream_path", ".drive/upstream"
        )
        orchestrator.init_upstream(PROJECT_ROOT, upstream, branch)

        image = config.get("docker", {}).get("image", "claude-drive-agent")
        credentials_path = Path.home() / ".claude" / "credentials.json"
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        # Build provider env vars from config + host environment
        provider_env = _build_provider_env(config)

        agents = []
        for role_cfg in config["roles"]:
            role = role_cfg["name"]
            count = role_cfg.get("count", 1)
            model = role_cfg.get("model", "claude-sonnet-4-5-20250929")
            max_sessions = role_cfg.get("max_sessions", 20)

            for i in range(count):
                agent_id = f"{role}-{i}"
                result = orchestrator.start_agent(
                    agent_id=agent_id,
                    role=role,
                    model=model,
                    max_sessions=max_sessions,
                    image=image,
                    upstream_path=upstream,
                    credentials_path=credentials_path,
                    api_key=api_key,
                    provider_env=provider_env,
                    project_root=PROJECT_ROOT,
                )
                _fleet_state[agent_id] = {
                    "status": result["status"],
                    "container_id": result["container_id"],
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "role": role,
                    "model": model,
                    "restart_count": 0,
                }
                agents.append({"agent_id": agent_id, **result})

    return JSONResponse({"agents": agents})


@app.post("/fleet/stop")
async def fleet_stop():
    """Stop all agents."""
    async with _fleet_lock:
        stopped = orchestrator.stop_fleet()
        _fleet_state.clear()
    return JSONResponse({"stopped": stopped})


@app.get("/fleet/status")
async def fleet_status():
    """Return current fleet state."""
    async with _fleet_lock:
        agents = dict(_fleet_state)
    return JSONResponse({"agents": agents, "count": len(agents)})


@app.post("/agents/{agent_id}/stop")
async def agent_stop(agent_id: str):
    """Stop a single agent."""
    if not _validate_agent_id(agent_id):
        return JSONResponse({"error": "Invalid agent_id"}, status_code=400)

    async with _fleet_lock:
        if agent_id not in _fleet_state:
            return JSONResponse({"error": "Agent not found"}, status_code=404)

        container_id = _fleet_state[agent_id]["container_id"]
        orchestrator.stop_agent(container_id)
        _fleet_state[agent_id]["status"] = "stopped"

    return JSONResponse({"agent_id": agent_id, "status": "stopped"})


@app.post("/agents/{agent_id}/restart")
async def agent_restart(agent_id: str):
    """Restart a single agent."""
    if not _validate_agent_id(agent_id):
        return JSONResponse({"error": "Invalid agent_id"}, status_code=400)

    async with _fleet_lock:
        if agent_id not in _fleet_state:
            return JSONResponse({"error": "Agent not found"}, status_code=404)

        container_id = _fleet_state[agent_id]["container_id"]
        result = orchestrator.restart_agent(container_id)
        _fleet_state[agent_id]["status"] = result["status"]
        _fleet_state[agent_id]["restart_count"] = (
            _fleet_state[agent_id].get("restart_count", 0) + 1
        )

    return JSONResponse({"agent_id": agent_id, "status": result["status"]})


# ── CLI args ─────────────────────────────────────────────


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent Dashboard")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Bind port (default: 8000)"
    )
    return parser.parse_args(argv)


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    args = _parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
