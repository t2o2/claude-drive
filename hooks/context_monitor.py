#!/usr/bin/env python3
"""Context monitor hook for Claude Code.

Primary heuristic: count "tool_use" occurrences in transcript as proxy for exchanges.
Fallback: file size if JSON parsing fails.
Typical exhaustion at ~100 exchanges.

Trigger: PostToolUse (broad matcher) + Stop
Input: JSON on stdin with session info
Output: stderr warnings, exit codes per Claude Code hooks API
"""

import json
import os
import sys

# Exchange-based thresholds (typical exhaustion ~100 exchanges)
WARN_EXCHANGES = 75       # 0.75 of ~100
CRITICAL_EXCHANGES = 88   # 0.88 of ~100
MAX_EXCHANGES = 100       # estimated max before context exhaustion

# Fallback: file size thresholds
WARN_BYTES = 640 * 1024
CRITICAL_BYTES = 720 * 1024
MAX_BYTES = 800 * 1024


def count_tool_uses(transcript_path: str) -> int | None:
    """Count tool_use occurrences in transcript as exchange proxy."""
    try:
        with open(transcript_path, "r") as f:
            content = f.read()
        return content.count('"tool_use"')
    except (IOError, OSError):
        return None


def get_transcript_size(transcript_path: str) -> int:
    """Get transcript file size as fallback metric."""
    try:
        return os.path.getsize(transcript_path)
    except OSError:
        return 0


def compute_usage(transcript_path: str) -> float:
    """Return context usage as 0.0-1.0 fraction."""
    if not transcript_path or not os.path.exists(transcript_path):
        return 0.0

    # Primary: tool_use count
    count = count_tool_uses(transcript_path)
    if count is not None and count > 0:
        return min(1.0, count / MAX_EXCHANGES)

    # Fallback: file size
    size = get_transcript_size(transcript_path)
    if size > 0:
        return min(1.0, size / MAX_BYTES)

    return 0.0


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    transcript_path = hook_input.get("transcript_path", "")
    usage = compute_usage(transcript_path)

    if usage < 0.75:
        return 0

    hook_event = hook_input.get("hook_event", "")
    pct = int(usage * 100)

    if usage >= 0.88:
        msg = (
            f"CRITICAL: Context usage ~{pct}%. "
            "Write .drive/sessions/continuation.md NOW with full state, "
            "append progress block to .drive/claude-progress.txt, "
            "then inform the user."
        )
        print(msg, file=sys.stderr)
        if hook_event == "Stop":
            return 2
        return 0

    # usage >= 0.75
    msg = (
        f"Context usage ~{pct}%. Consider wrapping up the current subtask. "
        "Avoid starting large new operations."
    )
    print(msg, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
