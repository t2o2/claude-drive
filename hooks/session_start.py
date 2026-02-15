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

import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timezone

CONFIG_FILE = ".drive/config.json"
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


def _send_telegram_reply(bot_token: str, chat_id: str, text: str) -> None:
    """Send a reply via Telegram bot API. Fails silently."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        subprocess.run(
            [
                "curl", "-s", "-X", "POST", url,
                "-d", f"chat_id={chat_id}",
                "-d", f"text={text}",
            ],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def poll_telegram_feedback(project_dir: str) -> list[str]:
    """Poll Telegram getUpdates for messages sent between sessions.

    Only processes messages from approved senders. Unknown senders can
    pair by sending the pairing code as their first message.
    """
    config_path = os.path.join(project_dir, CONFIG_FILE)
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path) as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    tg = config.get("telegram", {})
    if not tg.get("enabled") or not tg.get("bot_token") or not tg.get("chat_id"):
        return []

    bot_token = tg["bot_token"]
    chat_id = str(tg["chat_id"])
    last_update_id = tg.get("last_update_id", 0)
    approved_senders: list[int] = tg.get("approved_senders", [])
    pairing_code = str(tg.get("pairing_code", ""))
    offset = last_update_id + 1 if last_update_id else 0

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={offset}"
    try:
        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return []

    if not data.get("ok") or not data.get("result"):
        return []

    new_tasks: list[str] = []
    max_update_id = last_update_id
    config_changed = False

    tasks_list = config.setdefault("tasks", [])

    for update in data["result"]:
        update_id = update.get("update_id", 0)
        if update_id > max_update_id:
            max_update_id = update_id

        message = update.get("message", {})
        msg_chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()
        sender_id = message.get("from", {}).get("id")

        if msg_chat_id != chat_id or not text or sender_id is None:
            continue

        if sender_id in approved_senders:
            # Approved sender — process as task
            tasks_list.append({
                "text": text,
                "from": "telegram",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "done": False,
            })
            new_tasks.append(text)
        elif pairing_code and text == pairing_code:
            # Pairing attempt — verify and approve
            approved_senders.append(sender_id)
            tg["approved_senders"] = approved_senders
            # Generate a new code for future pairing
            tg["pairing_code"] = str(random.randint(100000, 999999))
            config_changed = True
            _send_telegram_reply(
                bot_token, msg_chat_id,
                "Paired successfully. Your messages will now be processed.",
            )
        # else: unknown sender, wrong code — silently ignore

    if max_update_id > last_update_id or config_changed:
        tg["last_update_id"] = max_update_id
        config["telegram"] = tg
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
                f.write("\n")
        except IOError:
            pass

    return new_tasks


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

    # 4. Telegram feedback polling
    new_tasks = poll_telegram_feedback(project_dir)
    if new_tasks:
        task_lines = "\n".join(f"- {t}" for t in new_tasks)
        output_parts.append(
            f"[TELEGRAM FEEDBACK] {len(new_tasks)} new task(s) from Telegram:\n{task_lines}"
        )

    # Print all context to stdout
    print("\n\n".join(output_parts))

    # 5. First-run detection
    config_path = os.path.join(project_dir, CONFIG_FILE)
    if not os.path.exists(config_path):
        print(
            "[FIRST RUN] No project config found. "
            "Run /setup to configure Claude Drive for this project.",
            file=sys.stderr,
        )

    # Stderr instruction
    print(
        "Do NOT explore the codebase from scratch. "
        "Trust progress file and continuation context.",
        file=sys.stderr,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
