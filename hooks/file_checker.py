#!/usr/bin/env python3
"""File checker hook for Claude Code.

Runs language-specific linting/checking on modified files.
Truncates output to first 5 error lines, logs full output to .drive/lint-output.log.

Trigger: PostToolUse on Write|Edit|MultiEdit
Input: JSON on stdin with tool_input.file_path
Output: Exit 2 with block decision if errors found, exit 0 if clean
"""

import json
import os
import subprocess
import sys

SUBPROCESS_TIMEOUT = 15  # seconds per command
MAX_ERROR_LINES = 5
LOG_FILE = ".drive/lint-output.log"


def ensure_log_dir(project_dir: str) -> None:
    log_path = os.path.join(project_dir, os.path.dirname(LOG_FILE))
    os.makedirs(log_path, exist_ok=True)


def log_full_output(project_dir: str, filepath: str, output: str) -> str:
    """Log full output to file and return the log path."""
    ensure_log_dir(project_dir)
    log_path = os.path.join(project_dir, LOG_FILE)
    try:
        with open(log_path, "w") as f:
            f.write(f"File: {filepath}\n\n{output}\n")
    except (IOError, OSError):
        pass
    return log_path


def truncate_errors(output: str) -> str:
    """Truncate to first MAX_ERROR_LINES lines, add count of remaining."""
    lines = output.strip().splitlines()
    if len(lines) <= MAX_ERROR_LINES:
        return output.strip()

    truncated = "\n".join(lines[:MAX_ERROR_LINES])
    remaining = len(lines) - MAX_ERROR_LINES
    return f"{truncated}\n... and {remaining} more errors. See {LOG_FILE}"


def prefix_errors(output: str) -> str:
    """Prefix each non-empty line with ERROR: for machine parseability."""
    lines = output.strip().splitlines()
    prefixed = []
    for line in lines:
        if line.strip() and not line.startswith("ERROR:") and not line.startswith("..."):
            prefixed.append(f"ERROR: {line}")
        else:
            prefixed.append(line)
    return "\n".join(prefixed)


def run_cmd(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    """Run a command and return (returncode, combined output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            cwd=cwd,
        )
        output = result.stdout + result.stderr
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {SUBPROCESS_TIMEOUT}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 0, ""  # Tool not installed, skip silently


def find_project_root(filepath: str, marker: str) -> str | None:
    """Walk up from filepath to find directory containing marker file."""
    current = os.path.dirname(os.path.abspath(filepath))
    for _ in range(10):
        if os.path.exists(os.path.join(current, marker)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def check_python(filepath: str) -> tuple[bool, str]:
    """Run ruff check and format check on a Python file."""
    errors = []

    rc, out = run_cmd(["ruff", "check", filepath])
    if rc != 0 and out:
        errors.append(f"ruff check:\n{out}")

    rc, out = run_cmd(["ruff", "format", "--check", filepath])
    if rc != 0 and out:
        errors.append(f"ruff format:\n{out}")

    if errors:
        return False, "\n\n".join(errors)
    return True, ""


def check_typescript(filepath: str) -> tuple[bool, str]:
    """Run tsc --noEmit on the TypeScript project."""
    project_root = find_project_root(filepath, "tsconfig.json")
    if not project_root:
        return True, ""  # No tsconfig found, skip

    rc, out = run_cmd(["npx", "tsc", "--noEmit"], cwd=project_root)
    if rc != 0 and out:
        return False, f"tsc --noEmit:\n{out}"
    return True, ""


def check_rust(filepath: str) -> tuple[bool, str]:
    """Run cargo check and clippy on the Rust project."""
    project_root = find_project_root(filepath, "Cargo.toml")
    if not project_root:
        return True, ""  # No Cargo.toml found, skip

    errors = []

    rc, out = run_cmd(
        ["cargo", "check", "--message-format=short"],
        cwd=project_root,
    )
    if rc != 0 and out:
        errors.append(f"cargo check:\n{out}")

    rc, out = run_cmd(
        ["cargo", "clippy", "--message-format=short", "--", "-D", "warnings"],
        cwd=project_root,
    )
    if rc != 0 and out:
        errors.append(f"cargo clippy:\n{out}")

    if errors:
        return False, "\n\n".join(errors)
    return True, ""


# Skip patterns
SKIP_EXTENSIONS = {
    ".md", ".json", ".yaml", ".yml", ".toml", ".lock", ".env",
    ".cfg", ".ini", ".txt", ".csv", ".html", ".css", ".scss",
    ".svg", ".png", ".jpg", ".gif",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "dist", "build", "target", ".ruff_cache",
}


def should_skip(filepath: str) -> bool:
    """Check if this file should be skipped."""
    _, ext = os.path.splitext(filepath)
    if ext in SKIP_EXTENSIONS:
        return True
    parts = filepath.replace("\\", "/").split("/")
    return any(d in SKIP_DIRS for d in parts)


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")

    if not filepath or should_skip(filepath):
        return 0

    _, ext = os.path.splitext(filepath)

    ok = True
    errors = ""

    if ext == ".py":
        ok, errors = check_python(filepath)
    elif ext in (".ts", ".tsx"):
        ok, errors = check_typescript(filepath)
    elif ext == ".rs":
        ok, errors = check_rust(filepath)
    else:
        return 0

    if not ok:
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

        # Log full output to file
        log_full_output(project_dir, filepath, errors)

        # Truncate and prefix for context
        display_errors = prefix_errors(truncate_errors(errors))

        result = {
            "decision": "block",
            "reason": display_errors,
        }
        print(json.dumps(result))
        print(
            f"Lint errors in {os.path.basename(filepath)}:\n{display_errors}",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
