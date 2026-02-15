#!/usr/bin/env python3
"""TDD enforcer hook for Claude Code.

Checks that source file modifications have corresponding test files.

Trigger: PostToolUse on Write|Edit|MultiEdit
Input: JSON on stdin with tool_input.file_path
Output: stderr reminder if no test found (exit 2)
"""

import json
import os
import sys

# Extensions to check for TDD compliance
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".rs"}

# Files/patterns to skip
SKIP_EXTENSIONS = {
    ".md", ".json", ".yaml", ".yml", ".toml", ".lock", ".env",
    ".cfg", ".ini", ".txt", ".csv", ".html", ".css", ".scss",
    ".svg", ".png", ".jpg", ".gif",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv",
    "dist", "build", "target", ".ruff_cache", ".mypy_cache",
    ".pytest_cache", "coverage", ".next",
}

SKIP_FILENAMES = {
    "__init__.py", "conftest.py", "setup.py", "manage.py",
    "main.py", "main.ts", "index.ts", "mod.rs", "lib.rs", "main.rs",
}


def is_test_file(filepath: str) -> bool:
    """Check if the file is itself a test file."""
    name = os.path.basename(filepath)
    # Python
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    # TypeScript
    if ".test." in name or ".spec." in name:
        return True
    # Rust tests dir
    if "/tests/" in filepath:
        return True
    return False


def should_skip(filepath: str) -> bool:
    """Check if this file should be skipped for TDD enforcement."""
    _, ext = os.path.splitext(filepath)

    if ext in SKIP_EXTENSIONS:
        return True
    if ext not in SOURCE_EXTENSIONS:
        return True

    name = os.path.basename(filepath)
    if name in SKIP_FILENAMES:
        return True

    parts = filepath.replace("\\", "/").split("/")
    if any(d in SKIP_DIRS for d in parts):
        return True

    if is_test_file(filepath):
        return True

    return False


def find_python_test(filepath: str) -> bool:
    """Look for corresponding Python test file."""
    dirpath = os.path.dirname(filepath)
    name = os.path.splitext(os.path.basename(filepath))[0]

    candidates = [
        os.path.join(dirpath, f"test_{name}.py"),
        os.path.join(dirpath, f"{name}_test.py"),
        os.path.join(dirpath, "tests", f"test_{name}.py"),
        os.path.join(os.path.dirname(dirpath), "tests", f"test_{name}.py"),
        os.path.join(os.path.dirname(dirpath), "tests", "unit", f"test_{name}.py"),
    ]

    return any(os.path.exists(c) for c in candidates)


def find_typescript_test(filepath: str) -> bool:
    """Look for corresponding TypeScript test file."""
    dirpath = os.path.dirname(filepath)
    base = os.path.splitext(os.path.basename(filepath))[0]
    # Remove .test/.spec if already in name
    base = base.replace(".test", "").replace(".spec", "")

    exts = [".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx"]
    candidates = []
    for ext in exts:
        candidates.append(os.path.join(dirpath, f"{base}{ext}"))
        candidates.append(os.path.join(dirpath, "__tests__", f"{base}{ext}"))
        candidates.append(os.path.join(os.path.dirname(dirpath), "__tests__", f"{base}{ext}"))

    return any(os.path.exists(c) for c in candidates)


def find_rust_test(filepath: str) -> bool:
    """Check for Rust tests: inline #[cfg(test)] or tests/ directory."""
    # Check for inline tests in the file itself
    try:
        with open(filepath, "r") as f:
            content = f.read()
            if "#[cfg(test)]" in content:
                return True
    except (IOError, OSError):
        pass

    # Check for tests/ directory near Cargo.toml
    dirpath = os.path.dirname(filepath)
    current = dirpath
    for _ in range(5):  # Walk up max 5 levels
        cargo_path = os.path.join(current, "Cargo.toml")
        tests_dir = os.path.join(current, "tests")
        if os.path.exists(cargo_path) and os.path.isdir(tests_dir):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return False


def main() -> int:
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        hook_input = {}

    # Extract file path from tool input
    tool_input = hook_input.get("tool_input", {})
    filepath = tool_input.get("file_path", "")

    if not filepath:
        return 0

    if should_skip(filepath):
        return 0

    _, ext = os.path.splitext(filepath)

    test_found = False
    if ext == ".py":
        test_found = find_python_test(filepath)
    elif ext in (".ts", ".tsx"):
        test_found = find_typescript_test(filepath)
    elif ext == ".rs":
        test_found = find_rust_test(filepath)

    if not test_found:
        name = os.path.basename(filepath)
        print(
            f"TDD Reminder: No test file found for `{name}`. "
            "Write a failing test first (RED), then implement (GREEN), then refactor. "
            "See .claude/rules/tdd-enforcement.md for conventions.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
