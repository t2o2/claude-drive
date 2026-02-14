"""Docker orchestrator — manages agent containers via Docker CLI.

All subprocess calls use list args (never shell=True) with timeouts.
Role names are validated to prevent command injection.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

CONTAINER_PREFIX = "claude-agent-"
ROLE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
DEFAULT_TIMEOUT = 30
BUILD_TIMEOUT = 300


def validate_role_name(name: str) -> None:
    """Raise ValueError if role name contains invalid characters."""
    if not ROLE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid role name: '{name}'. "
            "Must match ^[a-z0-9][a-z0-9-]{{0,31}}$ (lowercase alphanumeric + hyphen, max 32 chars)."
        )


def _run(
    cmd: list[str], timeout: int = DEFAULT_TIMEOUT, **kwargs
) -> subprocess.CompletedProcess:
    """Run a subprocess command with list args and timeout."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, **kwargs
    )


# ── Image management ──────────────────────────────────────


def build_image(image_name: str, dockerfile_dir: Path) -> bool:
    """Build Docker image from a directory containing a Dockerfile. Returns True on success."""
    cmd = [
        "docker",
        "build",
        "-t",
        image_name,
        "-f",
        str(dockerfile_dir / "Dockerfile"),
        str(dockerfile_dir),
    ]
    result = _run(cmd, timeout=BUILD_TIMEOUT)
    return result.returncode == 0


# ── Upstream repo ─────────────────────────────────────────


def init_upstream(project_root: Path, upstream_path: Path, branch: str) -> bool:
    """Initialize a bare git repo at upstream_path and push project state to it."""
    if not upstream_path.exists():
        result = _run(["git", "init", "--bare", str(upstream_path)])
        if result.returncode != 0:
            return False

    # Push current project state to upstream
    result = _run(
        ["git", "push", str(upstream_path), f"HEAD:refs/heads/{branch}", "--force"],
        timeout=DEFAULT_TIMEOUT,
    )
    return result.returncode == 0


# ── Container lifecycle ───────────────────────────────────


def start_agent(
    agent_id: str,
    role: str,
    model: str,
    max_sessions: int,
    image: str,
    upstream_path: Path,
    credentials_path: Path | None = None,
    api_key: str | None = None,
) -> dict:
    """Start a Docker container for an agent. Returns {container_id, status}."""
    validate_role_name(role)
    # Also validate agent_id format
    if not re.match(r"^[a-z0-9-]+$", agent_id):
        raise ValueError(f"Invalid agent_id: '{agent_id}'")

    container_name = f"{CONTAINER_PREFIX}{agent_id}"

    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "--rm",
        "-v",
        f"{upstream_path}:/upstream",
        "-e",
        f"AGENT_ROLE={role}",
        "-e",
        f"AGENT_ID={agent_id}",
        "-e",
        f"AGENT_MODEL={model}",
        "-e",
        "UPSTREAM_REMOTE=/upstream",
        "-e",
        f"MAX_SESSIONS={max_sessions}",
    ]

    if credentials_path and credentials_path.exists():
        cmd.extend(["-v", f"{credentials_path}:/root/.claude/credentials.json:ro"])

    if api_key:
        cmd.extend(["-e", f"ANTHROPIC_API_KEY={api_key}"])

    cmd.extend([image, "bash", "/workspace/scripts/entrypoint.sh"])

    result = _run(cmd)
    container_id = result.stdout.strip()[:12] if result.returncode == 0 else ""
    return {
        "container_id": container_id,
        "status": "running" if result.returncode == 0 else "failed",
    }


def stop_agent(container_id: str) -> bool:
    """Stop a Docker container. Returns True on success."""
    result = _run(["docker", "stop", container_id])
    return result.returncode == 0


def restart_agent(container_id: str) -> dict:
    """Restart a Docker container. Returns {container_id, status}."""
    result = _run(["docker", "restart", container_id])
    return {
        "container_id": container_id,
        "status": "running" if result.returncode == 0 else "failed",
    }


def stop_fleet() -> int:
    """Stop all claude-agent-* containers. Returns count of stopped containers."""
    result = _run(
        [
            "docker",
            "ps",
            "--filter",
            f"name={CONTAINER_PREFIX}",
            "--format",
            "{{.Names}}",
        ]
    )

    names = [n.strip() for n in result.stdout.strip().split("\n") if n.strip()]
    if not names:
        return 0

    stopped = 0
    for name in names:
        r = _run(["docker", "stop", name])
        if r.returncode == 0:
            stopped += 1
    return stopped


# ── Queries ───────────────────────────────────────────────


def list_running_agents() -> list[dict]:
    """List all running claude-agent-* containers. Returns list of dicts."""
    result = _run(
        [
            "docker",
            "ps",
            "--filter",
            f"name={CONTAINER_PREFIX}",
            "--format",
            '{"ID":"{{.ID}}","Names":"{{.Names}}","Status":"{{.Status}}","RunningFor":"{{.RunningFor}}"}',
        ]
    )

    if not result.stdout.strip():
        return []

    agents = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            agents.append(
                {
                    "container_id": data["ID"],
                    "name": data["Names"],
                    "status": data["Status"],
                    "running_for": data.get("RunningFor", ""),
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return agents


def get_agent_logs(container_id: str, lines: int = 100) -> str:
    """Get recent logs from a container. Returns log text."""
    result = _run(
        ["docker", "logs", "--tail", str(lines), container_id],
        timeout=DEFAULT_TIMEOUT,
    )
    return result.stdout + result.stderr
