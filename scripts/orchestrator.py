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
    provider_env: dict[str, str] | None = None,
    project_root: Path | None = None,
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
    ]

    # Mount shared agent directories at /board/ so agents see the host's task board
    if project_root:
        agent_dir = project_root / ".drive" / "agents"
        for subdir in ("tasks", "locks", "messages", "logs"):
            host_path = agent_dir / subdir
            host_path.mkdir(parents=True, exist_ok=True)
            cmd.extend(["-v", f"{host_path}:/board/{subdir}"])

    cmd += [
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
        cmd.extend(["-v", f"{credentials_path}:/home/claude/.claude/credentials.json:ro"])

    if api_key:
        cmd.extend(["-e", f"ANTHROPIC_API_KEY={api_key}"])

    # Pass provider-specific env vars (e.g. for GLM-5 via Z.AI)
    if provider_env:
        for key, val in provider_env.items():
            cmd.extend(["-e", f"{key}={val}"])

    cmd.extend([image, "bash", "/opt/claude-drive/scripts/entrypoint.sh"])

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


# ── Branch management ────────────────────────────────────


def list_agent_branches(upstream_path: Path) -> list[dict]:
    """List agent/* branches in the upstream bare repo with commit info."""
    result = _run(
        ["git", "-C", str(upstream_path), "for-each-ref",
         "--format=%(refname:short) %(objectname:short) %(committerdate:iso8601) %(subject)",
         "refs/heads/agent/"],
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    branches = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split(" ", 3)
        if len(parts) < 4:
            continue
        branch, commit, date, subject = parts[0], parts[1], parts[2], parts[3]
        # Count commits ahead of main
        ahead_result = _run(
            ["git", "-C", str(upstream_path), "rev-list", "--count", f"main..{branch}"],
        )
        ahead = int(ahead_result.stdout.strip()) if ahead_result.returncode == 0 else 0
        branches.append({
            "branch": branch,
            "agent_id": branch.removeprefix("agent/"),
            "commit": commit,
            "date": date,
            "subject": subject,
            "ahead": ahead,
        })
    return branches


def sync_branches_to_origin(upstream_path: Path, project_root: Path) -> int:
    """Push all agent/* branches from upstream bare repo to origin.

    Returns count of branches pushed. The host repo has origin credentials,
    so we fetch from the bare upstream into the host repo, then push to origin.
    """
    branches = list_agent_branches(upstream_path)
    pushed = 0
    for b in branches:
        branch = b["branch"]
        if b["ahead"] == 0:
            continue
        # Fetch branch from bare upstream into host repo
        fetch_result = _run(
            ["git", "-C", str(project_root), "fetch", str(upstream_path),
             f"{branch}:{branch}", "--force"],
        )
        if fetch_result.returncode != 0:
            continue
        # Push to origin
        push_result = _run(
            ["git", "-C", str(project_root), "push", "origin", f"{branch}:{branch}", "--force"],
            timeout=60,
        )
        if push_result.returncode == 0:
            pushed += 1
    return pushed


def merge_agent_branch(
    upstream_path: Path, branch: str, project_root: Path
) -> dict:
    """Merge an agent branch into main. Returns {success, message, conflicts}."""
    if not branch.startswith("agent/"):
        return {"success": False, "message": f"Invalid branch: {branch}", "conflicts": []}

    # Fetch the branch from upstream bare repo into host repo
    result = _run(
        ["git", "-C", str(project_root), "fetch", str(upstream_path),
         f"{branch}:{branch}", "--force"],
    )
    if result.returncode != 0:
        return {"success": False, "message": f"Failed to fetch {branch}: {result.stderr}", "conflicts": []}

    # Try merge into current branch (should be main)
    result = _run(
        ["git", "-C", str(project_root), "merge", branch, "--no-ff",
         "-m", f"Merge {branch} into main"],
    )
    if result.returncode != 0:
        # Check for conflicts
        conflicts_result = _run(
            ["git", "-C", str(project_root), "diff", "--name-only", "--diff-filter=U"],
        )
        conflicts = [f.strip() for f in conflicts_result.stdout.strip().split("\n") if f.strip()]
        _run(["git", "-C", str(project_root), "merge", "--abort"])
        return {"success": False, "message": "Merge conflicts", "conflicts": conflicts}

    # Push merged main to both upstream and origin
    _run(["git", "-C", str(project_root), "push", str(upstream_path), "HEAD:main"])
    _run(["git", "-C", str(project_root), "push", "origin", "main"], timeout=60)

    # Delete the agent branch everywhere
    _run(["git", "-C", str(upstream_path), "branch", "-D", branch])
    _run(["git", "-C", str(project_root), "branch", "-d", branch])
    _run(["git", "-C", str(project_root), "push", "origin", "--delete", branch], timeout=60)

    return {"success": True, "message": f"Merged {branch} into main and pushed to origin", "conflicts": []}
