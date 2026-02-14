#!/usr/bin/env python3
"""Session end hook for Claude Code.

Runs on Stop event. Three responsibilities:
1. Auto-commit tracked file changes with a summary message
2. Remind if progress file wasn't updated this session
3. Send Telegram notification if configured

Input: JSON on stdin (ignored)
Output: Status messages to stderr
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

CONFIG_FILE = ".drive/config.json"
PROGRESS_FILE = ".drive/claude-progress.txt"


def get_project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def is_git_repo(project_dir: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def auto_commit(project_dir: str) -> tuple[bool, int, str]:
    """Commit tracked file changes. Returns (committed, file_count, summary)."""
    if not is_git_repo(project_dir):
        return False, 0, "not a git repo"

    # Check for changes to tracked files
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        staged_result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, 0, "git error"

    changed_files = set()
    if diff_result.stdout.strip():
        changed_files.update(diff_result.stdout.strip().splitlines())
    if staged_result.stdout.strip():
        changed_files.update(staged_result.stdout.strip().splitlines())

    if not changed_files:
        return False, 0, "no changes"

    # Build summary from changed file names
    file_list = sorted(changed_files)
    file_count = len(file_list)
    if file_count <= 3:
        summary = ", ".join(Path(f).name for f in file_list)
    else:
        summary = ", ".join(Path(f).name for f in file_list[:3]) + f" +{file_count - 3} more"

    commit_msg = f"wip: {summary}"

    try:
        subprocess.run(
            ["git", "add", "-u"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_dir,
        )
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg, "--no-verify"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_dir,
        )
        if result.returncode == 0:
            return True, file_count, summary
        return False, file_count, f"commit failed: {result.stderr.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, file_count, "commit error"


def check_progress_updated(project_dir: str) -> bool:
    """Check if progress file was modified in the last 5 minutes."""
    path = os.path.join(project_dir, PROGRESS_FILE)
    if not os.path.exists(path):
        return False
    try:
        mtime = os.path.getmtime(path)
        return (time.time() - mtime) < 300  # 5 minutes
    except OSError:
        return False


def load_config(project_dir: str) -> dict | None:
    path = os.path.join(project_dir, CONFIG_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def send_telegram(config: dict, message: str) -> None:
    """Send message via Telegram bot API using curl. Fails silently."""
    tg = config.get("telegram", {})
    if not tg.get("enabled"):
        return

    bot_token = tg.get("bot_token", "")
    chat_id = tg.get("chat_id", "")
    if not bot_token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        subprocess.run(
            [
                "curl", "-s", "-X", "POST", url,
                "-d", f"chat_id={chat_id}",
                "-d", f"text={message}",
                "-d", "parse_mode=Markdown",
            ],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def main() -> int:
    # Consume stdin
    try:
        sys.stdin.read()
    except IOError:
        pass

    project_dir = get_project_dir()

    # Step 1: Auto-commit
    committed, file_count, summary = auto_commit(project_dir)
    if committed:
        print(f"[SESSION END] Auto-committed {file_count} file(s): {summary}", file=sys.stderr)
    elif file_count > 0:
        print(f"[SESSION END] Commit skipped: {summary}", file=sys.stderr)

    # Step 2: Progress reminder
    if not check_progress_updated(project_dir):
        print(
            "[SESSION END] Progress file not updated this session. "
            "Consider appending a session block to .drive/claude-progress.txt",
            file=sys.stderr,
        )

    # Step 3: Telegram notification
    config = load_config(project_dir)
    if config and config.get("telegram", {}).get("enabled"):
        project_name = config.get("project_name", "Unknown Project")
        if committed:
            msg = f"*{project_name}*\nSession ended. Committed {file_count} file(s): {summary}"
        else:
            msg = f"*{project_name}*\nSession ended. No changes committed."

        # Include completed task count if any tasks were done this session
        tasks = config.get("tasks", [])
        done_count = sum(1 for t in tasks if t.get("done"))
        if done_count:
            msg += f"\n✅ {done_count} task(s) completed."

        send_telegram(config, msg)
        print("[SESSION END] Telegram notification sent.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
