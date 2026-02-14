"""Tests for Docker orchestrator module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import orchestrator


# ── Validation ────────────────────────────────────────────


class TestValidateRoleName:
    def test_valid_names(self):
        for name in ["implementer", "reviewer-0", "docs", "a1-b2"]:
            orchestrator.validate_role_name(name)  # should not raise

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid role name"):
            orchestrator.validate_role_name("bad name")

    def test_rejects_shell_chars(self):
        with pytest.raises(ValueError, match="Invalid role name"):
            orchestrator.validate_role_name("role;rm -rf /")

    def test_rejects_uppercase(self):
        with pytest.raises(ValueError, match="Invalid role name"):
            orchestrator.validate_role_name("Implementer")

    def test_rejects_too_long(self):
        with pytest.raises(ValueError, match="Invalid role name"):
            orchestrator.validate_role_name("a" * 33)

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid role name"):
            orchestrator.validate_role_name("")


# ── build_image ───────────────────────────────────────────


class TestBuildImage:
    @patch("orchestrator.subprocess.run")
    def test_build_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = orchestrator.build_image("my-image", Path("/path/to/dir"))
        assert result is True
        args = mock_run.call_args
        assert args[0][0][0] == "docker"
        assert "build" in args[0][0]
        assert args[1]["shell"] is not True if "shell" in args[1] else True

    @patch("orchestrator.subprocess.run")
    def test_build_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = orchestrator.build_image("my-image", Path("/path/to/dir"))
        assert result is False

    @patch("orchestrator.subprocess.run")
    def test_build_uses_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        orchestrator.build_image("img", Path("/dir"))
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)

    @patch("orchestrator.subprocess.run")
    def test_build_has_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        orchestrator.build_image("img", Path("/dir"))
        assert mock_run.call_args[1].get("timeout") is not None


# ── init_upstream ─────────────────────────────────────────


class TestInitUpstream:
    @patch("orchestrator.subprocess.run")
    def test_init_creates_bare_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = orchestrator.init_upstream(
            Path("/project"), Path("/project/.drive/upstream"), "main"
        )
        assert result is True
        # Should call git init --bare and git push
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert any("init" in c for c in calls)

    @patch("orchestrator.subprocess.run")
    def test_init_uses_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        orchestrator.init_upstream(Path("/p"), Path("/p/up"), "main")
        for call in mock_run.call_args_list:
            assert isinstance(call[0][0], list)


# ── start_agent ───────────────────────────────────────────


class TestStartAgent:
    @patch("orchestrator.subprocess.run")
    def test_start_returns_dict(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123container\n")
        result = orchestrator.start_agent(
            agent_id="implementer-0",
            role="implementer",
            model="claude-sonnet-4-5-20250929",
            max_sessions=20,
            image="claude-drive-agent",
            upstream_path=Path("/upstream"),
            credentials_path=Path("/home/.claude/credentials.json"),
            api_key=None,
        )
        assert isinstance(result, dict)
        assert "container_id" in result
        assert "status" in result

    @patch("orchestrator.subprocess.run")
    def test_start_uses_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")
        orchestrator.start_agent(
            agent_id="implementer-0",
            role="implementer",
            model="m",
            max_sessions=20,
            image="img",
            upstream_path=Path("/up"),
        )
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)
        assert cmd[0] == "docker"

    @patch("orchestrator.subprocess.run")
    def test_start_validates_role_name(self, mock_run):
        with pytest.raises(ValueError):
            orchestrator.start_agent(
                agent_id="bad;agent",
                role="bad;role",
                model="m",
                max_sessions=20,
                image="img",
                upstream_path=Path("/up"),
            )

    @patch("orchestrator.subprocess.run")
    def test_start_with_api_key(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")
        orchestrator.start_agent(
            agent_id="impl-0",
            role="implementer",
            model="m",
            max_sessions=20,
            image="img",
            upstream_path=Path("/up"),
            api_key="sk-ant-test",
        )
        cmd = mock_run.call_args[0][0]
        assert any("ANTHROPIC_API_KEY=sk-ant-test" in str(a) for a in cmd)


# ── stop_agent ────────────────────────────────────────────


class TestStopAgent:
    @patch("orchestrator.subprocess.run")
    def test_stop_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert orchestrator.stop_agent("abc123") is True

    @patch("orchestrator.subprocess.run")
    def test_stop_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert orchestrator.stop_agent("abc123") is False

    @patch("orchestrator.subprocess.run")
    def test_stop_uses_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        orchestrator.stop_agent("abc123")
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)


# ── restart_agent ─────────────────────────────────────────


class TestRestartAgent:
    @patch("orchestrator.subprocess.run")
    def test_restart_returns_dict(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
        result = orchestrator.restart_agent("abc123")
        assert isinstance(result, dict)
        assert "status" in result

    @patch("orchestrator.subprocess.run")
    def test_restart_uses_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n")
        orchestrator.restart_agent("abc123")
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)


# ── stop_fleet ────────────────────────────────────────────


class TestStopFleet:
    @patch("orchestrator.subprocess.run")
    def test_stop_fleet_returns_count(self, mock_run):
        # First call: docker ps returns container names
        # Second+ calls: docker stop
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="claude-agent-impl-0\nclaude-agent-rev-0\n"),
            MagicMock(returncode=0),
            MagicMock(returncode=0),
        ]
        count = orchestrator.stop_fleet()
        assert count == 2

    @patch("orchestrator.subprocess.run")
    def test_stop_fleet_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        count = orchestrator.stop_fleet()
        assert count == 0


# ── list_running_agents ───────────────────────────────────


class TestListRunningAgents:
    @patch("orchestrator.subprocess.run")
    def test_list_returns_list_of_dicts(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"ID":"abc","Names":"claude-agent-impl-0","Status":"Up 5 min","RunningFor":"5 minutes"}\n',
        )
        result = orchestrator.list_running_agents()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "container_id" in result[0]
        assert "name" in result[0]
        assert "status" in result[0]

    @patch("orchestrator.subprocess.run")
    def test_list_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = orchestrator.list_running_agents()
        assert result == []


# ── get_agent_logs ────────────────────────────────────────


class TestGetAgentLogs:
    @patch("orchestrator.subprocess.run")
    def test_logs_returns_string(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="line1\nline2\nline3\n", stderr=""
        )
        result = orchestrator.get_agent_logs("abc123", lines=100)
        assert isinstance(result, str)
        assert "line1" in result

    @patch("orchestrator.subprocess.run")
    def test_logs_uses_tail_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        orchestrator.get_agent_logs("abc123", lines=50)
        cmd = mock_run.call_args[0][0]
        assert "--tail" in cmd
        assert "50" in cmd

    @patch("orchestrator.subprocess.run")
    def test_logs_uses_list_args_with_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        orchestrator.get_agent_logs("abc123")
        assert isinstance(mock_run.call_args[0][0], list)
        assert mock_run.call_args[1].get("timeout") is not None
