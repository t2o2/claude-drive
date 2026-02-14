#!/usr/bin/env python3
"""Validate .drive/agents/config.json schema."""

import json
import sys
from pathlib import Path

REQUIRED_TOP_KEYS = {"runtime", "roles", "docker", "devpod", "sync", "auth"}
VALID_RUNTIMES = {"docker", "devpod"}
REQUIRED_ROLE_KEYS = {"name", "count", "model", "prompt_file", "max_turns", "max_sessions"}
REQUIRED_DOCKER_KEYS = {"image", "mount_paths"}
REQUIRED_DEVPOD_KEYS = {"provider", "instance_type", "ide"}
REQUIRED_SYNC_KEYS = {"upstream_path", "upstream_remote", "branch"}
REQUIRED_AUTH_KEYS = {"method", "env_var_name"}


def validate(config: dict) -> list[str]:
    """Return list of validation errors. Empty list = valid."""
    errors: list[str] = []

    # Top-level keys
    missing = REQUIRED_TOP_KEYS - set(config.keys())
    if missing:
        errors.append(f"Missing top-level keys: {missing}")
        return errors

    # Runtime
    if config["runtime"] not in VALID_RUNTIMES:
        errors.append(f"Invalid runtime: {config['runtime']}. Must be one of {VALID_RUNTIMES}")

    # Roles
    roles = config["roles"]
    if not isinstance(roles, list) or len(roles) == 0:
        errors.append("roles must be a non-empty list")
    else:
        for i, role in enumerate(roles):
            role_missing = REQUIRED_ROLE_KEYS - set(role.keys())
            if role_missing:
                errors.append(f"Role {i} missing keys: {role_missing}")
            if isinstance(role.get("count"), int) and role["count"] < 1:
                errors.append(f"Role {i} count must be >= 1")
            if isinstance(role.get("max_sessions"), int) and role["max_sessions"] < 1:
                errors.append(f"Role {i} max_sessions must be >= 1")

    # Docker
    docker_missing = REQUIRED_DOCKER_KEYS - set(config["docker"].keys())
    if docker_missing:
        errors.append(f"docker section missing keys: {docker_missing}")

    # DevPod
    devpod_missing = REQUIRED_DEVPOD_KEYS - set(config["devpod"].keys())
    if devpod_missing:
        errors.append(f"devpod section missing keys: {devpod_missing}")

    # Sync
    sync_missing = REQUIRED_SYNC_KEYS - set(config["sync"].keys())
    if sync_missing:
        errors.append(f"sync section missing keys: {sync_missing}")

    # Auth
    auth_missing = REQUIRED_AUTH_KEYS - set(config["auth"].keys())
    if auth_missing:
        errors.append(f"auth section missing keys: {auth_missing}")

    return errors


def main() -> int:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".drive/agents/config.json")

    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        return 1

    errors = validate(config)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    print(json.dumps({"valid": True, "roles": len(config["roles"]), "runtime": config["runtime"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
