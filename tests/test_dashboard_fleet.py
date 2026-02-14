"""Tests for fleet control API routes in dashboard."""

import asyncio
import re
from pathlib import Path
from unittest.mock import patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


# ── Fleet state management ───────────────────────────────


class TestFleetState:
    """Fleet state dict should be protected by asyncio.Lock."""

    def test_fleet_state_exists(self):
        import dashboard

        assert hasattr(dashboard, "_fleet_state")
        assert isinstance(dashboard._fleet_state, dict)

    def test_fleet_lock_exists(self):
        import dashboard

        assert hasattr(dashboard, "_fleet_lock")
        assert isinstance(dashboard._fleet_lock, asyncio.Lock)


# ── agent_id validation ──────────────────────────────────


class TestAgentIdValidation:
    def test_valid_ids(self):
        pattern = re.compile(r"^[a-z0-9-]+$")
        for aid in ["implementer-0", "reviewer-1", "docs-0", "a1-b2"]:
            assert pattern.match(aid), f"{aid} should be valid"

    def test_rejects_invalid_ids(self):
        pattern = re.compile(r"^[a-z0-9-]+$")
        for aid in ["bad;id", "UPPER", "space name", "../path", ""]:
            assert not pattern.match(aid), f"{aid} should be rejected"


# ── Fleet routes (via TestClient) ────────────────────────


@pytest.fixture
def client():
    """Create a TestClient for the dashboard app."""
    from starlette.testclient import TestClient

    import dashboard

    # Reset fleet state before each test
    dashboard._fleet_state.clear()
    return TestClient(dashboard.app)


class TestFleetStartRoute:
    @patch("dashboard.orchestrator.init_upstream")
    @patch("dashboard.orchestrator.start_agent")
    def test_fleet_start_creates_agents(self, mock_start, mock_init, client):
        mock_init.return_value = True
        mock_start.return_value = {"container_id": "abc123", "status": "running"}
        response = client.post("/fleet/start")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        # Should have called start_agent for each role×count
        assert mock_start.call_count > 0

    @patch("dashboard.orchestrator.init_upstream")
    @patch("dashboard.orchestrator.start_agent")
    def test_fleet_start_populates_state(self, mock_start, mock_init, client):
        mock_init.return_value = True
        mock_start.return_value = {"container_id": "abc123", "status": "running"}
        client.post("/fleet/start")
        import dashboard

        assert len(dashboard._fleet_state) > 0

    @patch("dashboard.orchestrator.init_upstream")
    @patch("dashboard.orchestrator.start_agent")
    def test_fleet_start_handles_failure(self, mock_start, mock_init, client):
        mock_init.return_value = True
        mock_start.return_value = {"container_id": "", "status": "failed"}
        response = client.post("/fleet/start")
        assert response.status_code == 200
        data = response.json()
        # Failed agents should still be tracked
        assert "agents" in data


class TestFleetStopRoute:
    @patch("dashboard.orchestrator.stop_fleet")
    def test_fleet_stop_clears_state(self, mock_stop, client):
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc",
        }
        mock_stop.return_value = 1
        response = client.post("/fleet/stop")
        assert response.status_code == 200
        data = response.json()
        assert "stopped" in data
        assert len(dashboard._fleet_state) == 0


class TestFleetStatusRoute:
    def test_fleet_status_returns_json(self, client):
        response = client.get("/fleet/status")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "count" in data


class TestAgentStopRoute:
    @patch("dashboard.orchestrator.stop_agent")
    def test_agent_stop_valid_id(self, mock_stop, client):
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
        }
        mock_stop.return_value = True
        response = client.post("/agents/impl-0/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

    def test_agent_stop_invalid_id(self, client):
        response = client.post("/agents/bad;id/stop")
        assert response.status_code == 400

    def test_agent_stop_not_found(self, client):
        response = client.post("/agents/nonexistent-0/stop")
        assert response.status_code == 404


class TestAgentRestartRoute:
    @patch("dashboard.orchestrator.restart_agent")
    def test_agent_restart_valid_id(self, mock_restart, client):
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
        }
        mock_restart.return_value = {"container_id": "abc123", "status": "running"}
        response = client.post("/agents/impl-0/restart")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_agent_restart_invalid_id(self, client):
        response = client.post("/agents/bad;id/restart")
        assert response.status_code == 400

    def test_agent_restart_not_found(self, client):
        response = client.post("/agents/nonexistent-0/restart")
        assert response.status_code == 404


# ── Startup state reconstruction ─────────────────────────


class TestStateReconstruction:
    @patch("dashboard.orchestrator.list_running_agents")
    def test_reconstruct_from_docker(self, mock_list):
        import dashboard

        mock_list.return_value = [
            {
                "container_id": "abc123",
                "name": "claude-agent-impl-0",
                "status": "Up 5 minutes",
                "running_for": "5 minutes",
            },
        ]
        dashboard._reconstruct_fleet_state()
        assert "impl-0" in dashboard._fleet_state
        assert dashboard._fleet_state["impl-0"]["container_id"] == "abc123"

    @patch("dashboard.orchestrator.list_running_agents")
    def test_reconstruct_empty(self, mock_list):
        import dashboard

        mock_list.return_value = []
        dashboard._fleet_state.clear()
        dashboard._reconstruct_fleet_state()
        assert len(dashboard._fleet_state) == 0


# ── CLI args ─────────────────────────────────────────────


class TestCLIArgs:
    def test_default_host_is_localhost(self):
        """Dashboard should bind to 127.0.0.1 by default, not 0.0.0.0."""
        import dashboard

        # Check that the module has CLI arg parsing
        assert hasattr(dashboard, "_parse_args")
        args = dashboard._parse_args([])
        assert args.host == "127.0.0.1"
        assert args.port == 8000

    def test_custom_host_and_port(self):
        import dashboard

        args = dashboard._parse_args(["--host", "0.0.0.0", "--port", "9000"])
        assert args.host == "0.0.0.0"
        assert args.port == 9000


# ── Fleet partial route ──────────────────────────────────


class TestFleetPartialRoute:
    def test_fleet_partial_returns_html(self, client):
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_fleet_partial_shows_stopped_when_empty(self, client):
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        assert "Stopped" in response.text or "stopped" in response.text.lower()

    def test_fleet_partial_shows_running_with_agents(self, client):
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc",
            "role": "implementer",
        }
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        text = response.text.lower()
        assert "running" in text

    def test_fleet_partial_shows_start_button(self, client):
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        assert "Start Fleet" in response.text

    def test_fleet_partial_shows_stop_button(self, client):
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc",
            "role": "implementer",
        }
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        assert "Stop Fleet" in response.text

    def test_fleet_partial_warns_no_open_tasks(self, client):
        """When no open tasks exist, show warning."""
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        # Warning should mention no tasks or empty board
        text = response.text.lower()
        assert "no open tasks" in text or "add tasks" in text

    def test_full_page_includes_fleet_section(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "fleet" in response.text.lower()


# ── Agent cards (Task 4) ─────────────────────────────────


class TestAgentCardsPartial:
    def test_agent_cards_partial_returns_html(self, client):
        """The agents partial should return agent cards."""
        response = client.get("/partials/agents")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_agent_cards_show_container_status(self, client):
        """Cards should show container status from fleet state."""
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
            "model": "claude-sonnet-4-5-20250929",
            "restart_count": 0,
            "started_at": "2026-02-14T10:00:00+00:00",
        }
        response = client.get("/partials/agents")
        assert response.status_code == 200
        assert "impl-0" in response.text
        assert "running" in response.text.lower()

    def test_agent_cards_show_stop_button(self, client):
        """Running agents should have a Stop button."""
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
        }
        response = client.get("/partials/agents")
        assert response.status_code == 200
        assert "/agents/impl-0/stop" in response.text

    def test_agent_cards_show_restart_button(self, client):
        """Running agents should have a Restart button."""
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
        }
        response = client.get("/partials/agents")
        assert response.status_code == 200
        assert "/agents/impl-0/restart" in response.text

    def test_agent_cards_merge_lock_data(self, client):
        """Cards should show task assignment from lock data."""
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
        }
        # _get_agent_cards merges fleet + lock data
        assert hasattr(dashboard, "_get_agent_cards")


# ── Log streaming (Task 5) ───────────────────────────────


class TestLogEndpoints:
    @patch("dashboard.orchestrator.get_agent_logs")
    def test_get_static_logs(self, mock_logs, client):
        """GET /agents/{id}/logs returns last 100 lines as HTML."""
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
        }
        mock_logs.return_value = "line1\nline2\nline3\n"
        response = client.get("/agents/impl-0/logs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "line1" in response.text

    def test_get_logs_invalid_id(self, client):
        response = client.get("/agents/bad;id/logs")
        assert response.status_code == 400

    def test_get_logs_not_found(self, client):
        response = client.get("/agents/nonexistent-0/logs")
        assert response.status_code == 404

    @patch("dashboard.orchestrator.get_agent_logs")
    def test_logs_strip_ansi(self, mock_logs, client):
        """ANSI escape codes should be stripped from log output."""
        import dashboard

        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
        }
        mock_logs.return_value = "\x1b[31mred text\x1b[0m normal"
        response = client.get("/agents/impl-0/logs")
        assert response.status_code == 200
        assert "\x1b[" not in response.text
        assert "red text" in response.text

    def test_websocket_endpoint_exists(self):
        """WebSocket endpoint should be registered."""
        import dashboard

        routes = [r.path for r in dashboard.app.routes]
        assert "/agents/{agent_id}/logs/ws" in routes


# ── Health monitor (Task 6) ───────────────────────────────


def _run_health_check():
    """Run _health_check synchronously, creating a fresh lock to avoid event loop issues."""
    import dashboard

    dashboard._fleet_lock = asyncio.Lock()
    asyncio.run(dashboard._health_check())


class TestHealthMonitor:
    def test_health_check_function_exists(self):
        import dashboard

        assert hasattr(dashboard, "_health_check")

    @patch("dashboard.orchestrator.list_running_agents")
    @patch("dashboard.orchestrator.restart_agent")
    def test_detects_crashed_container(self, mock_restart, mock_list):
        """If container not in docker ps, mark as crashed."""
        import dashboard

        dashboard._fleet_state.clear()
        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
            "restart_count": 0,
        }
        mock_list.return_value = []
        mock_restart.return_value = {"container_id": "abc123", "status": "running"}

        _run_health_check()
        assert mock_restart.called

    @patch("dashboard.orchestrator.list_running_agents")
    @patch("dashboard.orchestrator.restart_agent")
    def test_respects_max_restarts(self, mock_restart, mock_list):
        """Don't restart if restart_count >= 3."""
        import dashboard

        dashboard._fleet_state.clear()
        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
            "restart_count": 3,
        }
        mock_list.return_value = []

        _run_health_check()
        assert not mock_restart.called
        assert dashboard._fleet_state["impl-0"]["status"] == "crashed"

    @patch("dashboard.orchestrator.list_running_agents")
    def test_healthy_agent_stays_healthy(self, mock_list):
        """Agent in docker ps keeps running status."""
        import dashboard

        dashboard._fleet_state.clear()
        dashboard._fleet_state["impl-0"] = {
            "status": "running",
            "container_id": "abc123",
            "role": "implementer",
            "restart_count": 0,
        }
        mock_list.return_value = [
            {
                "container_id": "abc123",
                "name": "claude-agent-impl-0",
                "status": "Up",
                "running_for": "5m",
            },
        ]

        _run_health_check()
        assert dashboard._fleet_state["impl-0"]["status"] == "healthy"


# ── Config management (Task 7) ────────────────────────────


class TestConfigRoutes:
    def test_get_config_returns_json(self, client):
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_post_config_validates(self, client):
        """POST /config validates before saving."""
        response = client.post(
            "/config",
            data={"config_json": '{"invalid": true}'},
        )
        assert response.status_code == 200
        # Should return errors since it's missing required fields
        text = response.text.lower()
        assert "error" in text or "missing" in text

    def test_config_partial_returns_html(self, client):
        response = client.get("/partials/config")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


# ── Preflight checks (Task 8) ─────────────────────────────


class TestPreflightRoute:
    def test_preflight_returns_json(self, client):
        response = client.get("/fleet/preflight")
        assert response.status_code == 200
        data = response.json()
        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_preflight_checks_have_required_fields(self, client):
        response = client.get("/fleet/preflight")
        data = response.json()
        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert check["status"] in ("pass", "fail", "warn")
            assert "message" in check


class TestDevPodFallback:
    @patch("dashboard._load_config")
    def test_devpod_shows_fallback_message(self, mock_config, client):
        mock_config.return_value = {"runtime": "devpod", "roles": []}
        response = client.get("/partials/fleet")
        assert response.status_code == 200
        text = response.text.lower()
        assert "devpod" in text
