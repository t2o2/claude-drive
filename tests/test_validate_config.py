"""Tests for scripts/validate_agent_config.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_agent_config import validate


def _valid_config() -> dict:
    return {
        "runtime": "docker",
        "roles": [
            {
                "name": "implementer",
                "count": 2,
                "model": "claude-sonnet-4-5-20250929",
                "prompt_file": ".drive/agents/roles/implementer.md",
                "max_turns": 50,
                "max_sessions": 20,
            }
        ],
        "docker": {"image": "claude-drive-agent", "mount_paths": {"upstream": "/upstream"}},
        "devpod": {"provider": "docker", "instance_type": "small", "ide": "none"},
        "sync": {"upstream_path": ".drive/upstream", "upstream_remote": "", "branch": "main"},
        "auth": {"method": "env_var", "env_var_name": "ANTHROPIC_API_KEY"},
    }


def test_valid_config_passes():
    assert validate(_valid_config()) == []


def test_missing_top_level_key():
    config = _valid_config()
    del config["runtime"]
    errors = validate(config)
    assert any("Missing top-level" in e for e in errors)


def test_invalid_runtime():
    config = _valid_config()
    config["runtime"] = "podman"
    errors = validate(config)
    assert any("Invalid runtime" in e for e in errors)


def test_empty_roles():
    config = _valid_config()
    config["roles"] = []
    errors = validate(config)
    assert any("non-empty list" in e for e in errors)


def test_role_missing_keys():
    config = _valid_config()
    del config["roles"][0]["max_sessions"]
    errors = validate(config)
    assert any("Role 0 missing" in e for e in errors)


def test_role_count_below_one():
    config = _valid_config()
    config["roles"][0]["count"] = 0
    errors = validate(config)
    assert any("count must be >= 1" in e for e in errors)


def test_role_max_sessions_below_one():
    config = _valid_config()
    config["roles"][0]["max_sessions"] = 0
    errors = validate(config)
    assert any("max_sessions must be >= 1" in e for e in errors)


def test_missing_docker_keys():
    config = _valid_config()
    del config["docker"]["image"]
    errors = validate(config)
    assert any("docker section missing" in e for e in errors)


def test_missing_devpod_keys():
    config = _valid_config()
    del config["devpod"]["provider"]
    errors = validate(config)
    assert any("devpod section missing" in e for e in errors)


def test_missing_sync_keys():
    config = _valid_config()
    del config["sync"]["branch"]
    errors = validate(config)
    assert any("sync section missing" in e for e in errors)


def test_missing_auth_keys():
    config = _valid_config()
    del config["auth"]["method"]
    errors = validate(config)
    assert any("auth section missing" in e for e in errors)


def test_devpod_runtime_valid():
    config = _valid_config()
    config["runtime"] = "devpod"
    assert validate(config) == []


def test_cli_valid_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_valid_config()))
    result = subprocess.run(
        [sys.executable, "scripts/validate_agent_config.py", str(config_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["valid"] is True


def test_cli_invalid_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"runtime": "bad"}))
    result = subprocess.run(
        [sys.executable, "scripts/validate_agent_config.py", str(config_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_cli_missing_file():
    result = subprocess.run(
        [sys.executable, "scripts/validate_agent_config.py", "/nonexistent/config.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
