from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import AppSettings
from app.main import create_app
from app.models import CommandSchema, RiskLevel


def build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        app_name="Test Control Center",
        app_version="test",
        app_secret_key="test-secret",
        gemini_api_key="",
        parser_mode="mock",
        allowed_origins=["http://localhost:5173"],
        command_db_path=str(tmp_path / "test_commands.db"),
        request_rate_limit=50,
        rate_limit_window_seconds=60,
        execution_delay_seconds=0.0,
    )


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(build_settings(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(role: str = "operator", user_id: str = "tester") -> dict[str, str]:
    return {
        "X-API-Key": "test-secret",
        "X-User-Id": user_id,
        "X-User-Name": "Test User",
        "X-User-Role": role,
    }


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_missing_api_key(client: TestClient):
    response = client.get("/api/v1/commands")
    assert response.status_code == 401


@patch("app.command_service.parse_instruction_to_command")
def test_safe_command_is_queued_and_completes(mock_parse, client: TestClient):
    mock_parse.return_value = CommandSchema(
        op="system.check_and_fix",
        summary="Check health and apply safe remediations.",
        actions=["health_check", "auto_fix"],
        parameters={"auto_fix_scope": "minor"},
        target_service="platform",
        environment="staging",
        confidence=0.95,
        risk_level=RiskLevel.medium,
        is_safe=True,
        approval_required=False,
        needs_clarification=False,
        clarification_message="",
        execution_notes="Routine maintenance flow.",
        parser_source="mock",
    )

    response = client.post(
        "/api/v1/parse-command",
        headers=auth_headers(),
        json={
            "instruction": "Check system health and fix minor issues",
            "environment": "staging",
            "execution_mode": "execute",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "queued"

    detail = client.get(f"/api/v1/commands/{payload['data']['id']}", headers=auth_headers())
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "completed"


@patch("app.command_service.parse_instruction_to_command")
def test_ambiguous_command_requests_clarification(mock_parse, client: TestClient):
    mock_parse.return_value = CommandSchema(
        op="clarification.required",
        summary="Clarification required.",
        actions=[],
        parameters={},
        target_service="",
        environment="staging",
        confidence=0.33,
        risk_level=RiskLevel.medium,
        is_safe=True,
        approval_required=False,
        needs_clarification=True,
        clarification_message="Which service should be restarted?",
        execution_notes="Not enough context.",
        parser_source="mock",
    )

    response = client.post(
        "/api/v1/parse-command",
        headers=auth_headers(),
        json={"instruction": "Restart it", "environment": "staging", "execution_mode": "execute"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["status"] == "needs_clarification"
    assert payload["error"] == "Which service should be restarted?"


@patch("app.command_service.parse_instruction_to_command")
def test_dangerous_command_is_blocked(mock_parse, client: TestClient):
    mock_parse.return_value = CommandSchema(
        op="database.drop",
        summary="Drop the production database.",
        actions=["drop_database"],
        parameters={},
        target_service="database",
        environment="production",
        confidence=0.92,
        risk_level=RiskLevel.critical,
        is_safe=False,
        approval_required=True,
        needs_clarification=False,
        clarification_message="",
        execution_notes="Dangerous request.",
        parser_source="mock",
    )

    response = client.post(
        "/api/v1/parse-command",
        headers=auth_headers(),
        json={"instruction": "Drop the production database", "environment": "production", "execution_mode": "execute"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["status"] == "blocked"
    assert "blocked" in payload["error"].lower()


@patch("app.command_service.parse_instruction_to_command")
def test_operator_request_can_wait_for_approval_then_execute(mock_parse, client: TestClient):
    mock_parse.return_value = CommandSchema(
        op="service.restart",
        summary="Restart the auth service.",
        actions=["restart_service", "verify_uptime"],
        parameters={"service": "auth"},
        target_service="auth",
        environment="production",
        confidence=0.89,
        risk_level=RiskLevel.high,
        is_safe=True,
        approval_required=True,
        needs_clarification=False,
        clarification_message="",
        execution_notes="Production restart requires approval.",
        parser_source="mock",
    )

    initial = client.post(
        "/api/v1/parse-command",
        headers=auth_headers(role="operator"),
        json={"instruction": "Restart auth in production", "environment": "production", "execution_mode": "execute"},
    )
    command_id = initial.json()["data"]["id"]

    assert initial.status_code == 200
    assert initial.json()["data"]["status"] == "needs_approval"

    approval = client.post(
        f"/api/v1/commands/{command_id}/approve",
        headers=auth_headers(role="approver", user_id="approver-1"),
        json={"note": "Safe to execute during the maintenance window."},
    )

    assert approval.status_code == 200
    assert approval.json()["data"]["status"] == "queued"

    detail = client.get(f"/api/v1/commands/{command_id}", headers=auth_headers(role="approver"))
    assert detail.json()["data"]["status"] == "completed"


@patch("app.command_service.parse_instruction_to_command")
def test_dry_run_returns_preview(mock_parse, client: TestClient):
    mock_parse.return_value = CommandSchema(
        op="service.scale",
        summary="Scale billing service.",
        actions=["validate_capacity_window", "update_scaling_policy"],
        parameters={"desired_capacity": 4},
        target_service="billing",
        environment="production",
        confidence=0.81,
        risk_level=RiskLevel.high,
        is_safe=True,
        approval_required=True,
        needs_clarification=False,
        clarification_message="",
        execution_notes="Preview only.",
        parser_source="mock",
    )

    response = client.post(
        "/api/v1/parse-command",
        headers=auth_headers(),
        json={"instruction": "Scale billing to 4", "environment": "production", "execution_mode": "dry_run"},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "dry_run_completed"
    assert payload["data"]["result"]["mode"] == "dry_run"


@patch("app.command_service.parse_instruction_to_command")
def test_role_based_policy_blocks_viewer_actions(mock_parse, client: TestClient):
    mock_parse.return_value = CommandSchema(
        op="user.create",
        summary="Create a user account.",
        actions=["create_user"],
        parameters={"requested_role": "viewer"},
        target_service="identity",
        environment="staging",
        confidence=0.86,
        risk_level=RiskLevel.medium,
        is_safe=True,
        approval_required=False,
        needs_clarification=False,
        clarification_message="",
        execution_notes="Viewer should not be able to create users.",
        parser_source="mock",
    )

    response = client.post(
        "/api/v1/parse-command",
        headers=auth_headers(role="viewer"),
        json={"instruction": "Create a user", "environment": "staging", "execution_mode": "execute"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "blocked"


def test_metrics_endpoint_reports_totals(client: TestClient):
    metrics = client.get("/api/v1/metrics", headers=auth_headers())
    assert metrics.status_code == 200
    assert metrics.json()["total_commands"] == 0
