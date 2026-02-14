#!/usr/bin/env python3
"""Session start hook for Claude Code.

Deterministic init sequence:
1. Environment summary (pwd, recent git log, project type)
2. Progress file (last 2 session blocks)
3. Continuation file (if exists)

Trigger: SessionStart (startup|resume|clear|compact)
Input: JSON on stdin
Output: Context injected to stdout, instructions to stderr
"""

import os
import re
import subprocess
import sys

CONTINUATION_FILE = ".drive/sessions/continuation.md"
PROGRESS_FILE = ".drive/claude-progress.txt"


def get_project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def env_summary(project_dir: str) -> str:
    """Print pwd, last 5 git commits, project type marker."""
    lines = [f"[SESSION INIT] pwd: {project_dir}"]

    # Detect project type
    markers = {
        "pyproject.toml": "Python (uv)",
        "package.json": "TypeScript/Node",
        "Cargo.toml": "Rust",
    }
    for marker, label in markers.items():
        if os.path.exists(os.path.join(project_dir, marker)):
            lines.append(f"[SESSION INIT] Project type: {label}")
            break

    # Recent git log
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines.append(f"[SESSION INIT] Recent commits:\n{result.stdout.strip()}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return "\n".join(lines)


def read_progress(project_dir: str) -> str | None:
    """Read last 2 session blocks from progress file."""
    path = os.path.join(project_dir, PROGRESS_FILE)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r") as f:
            content = f.read().strip()
    except (IOError, OSError):
        return None

    if not content:
        return None

    # Split by session markers (lines starting with "## Session")
    blocks = re.split(r"(?=^## Session )", content, flags=re.MULTILINE)
    # Filter empty blocks and take last 2
    blocks = [b.strip() for b in blocks if b.strip()]
    recent = blocks[-2:] if len(blocks) >= 2 else blocks

    return "\n\n".join(recent)


def read_continuation(project_dir: str) -> str | None:
    """Read continuation file if it exists."""
    path = os.path.join(project_dir, CONTINUATION_FILE)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r") as f:
            content = f.read().strip()
    except (IOError, OSError):
        return None

    return content if content else None


def main() -> int:
    try:
        sys.stdin.read()
    except IOError:
        pass

    project_dir = get_project_dir()
    output_parts = []

    # 1. Environment summary
    output_parts.append(env_summary(project_dir))

    # 2. Progress file
    progress = read_progress(project_dir)
    if progress:
        output_parts.append(f"[PROJECT PROGRESS] Recent session history:\n\n{progress}")

    # 3. Continuation file
    continuation = read_continuation(project_dir)
    if continuation:
        output_parts.append(
            f"[SESSION CONTINUATION] Resuming from previous session:\n\n{continuation}"
        )
        print(
            "IMPORTANT: Read the continuation context above, follow the Next Steps, "
            "then delete .drive/sessions/continuation.md",
            file=sys.stderr,
        )

    # Print all context to stdout
    print("\n\n".join(output_parts))

    # Stderr instruction
    print(
        "Do NOT explore the codebase from scratch. "
        "Trust progress file and continuation context.",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
