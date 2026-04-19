import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.models import CommandSchema

client = TestClient(app)

# Test headers
HEADERS = {"X-API-Key": "dev-secret-key-123"}

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_missing_api_key():
    response = client.post("/api/v1/parse-command", json={"instruction": "test"})
    assert response.status_code == 401

@patch("app.main.parse_instruction_to_command")
def test_successful_safe_command(mock_ai):
    # Mock LLM returning a safe, valid operation
    mock_ai.return_value = CommandSchema(
        op="system.check_and_fix",
        actions=["health_check"],
        is_safe=True,
        needs_clarification=False
    )
    
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "Check system health and fix minor issues"},
        headers=HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["op"] == "system.check_and_fix"

@patch("app.main.parse_instruction_to_command")
def test_ambiguous_command(mock_ai):
    # Mock LLM needing clarification
    mock_ai.return_value = CommandSchema(
        op="unknown",
        actions=[],
        is_safe=True,
        needs_clarification=True,
        clarification_message="Which server's health should I check?"
    )
    
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "Check health"},
        headers=HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "Which server's health should I check?"

@patch("app.main.parse_instruction_to_command")
def test_unsafe_destructive_command(mock_ai):
    # Mock LLM properly flagging a dark prompt
    mock_ai.return_value = CommandSchema(
        op="database.drop",
        actions=["drop_all"],
        is_safe=False,
        needs_clarification=False
    )
    
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "Drop entire production database"},
        headers=HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False # Should be blocked
    assert "Security Policy Blocked Request" in data["error"]

@patch("app.main.parse_instruction_to_command")
def test_llm_hallucinates_dangerous_op_but_flags_safe(mock_ai):
    # Mock LLM being naive and marking a bad op as safe
    mock_ai.return_value = CommandSchema(
        op="system.rm_rf",
        actions=["delete_root"],
        is_safe=True,  # AI failed to flag hazard
        needs_clarification=False
    )
    
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "Clean up space by running rm -rf /"},
        headers=HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "blocked by security policy" in data["error"].lower() or "not permitted" in data["error"].lower()

@patch("app.main.parse_instruction_to_command")
def test_empty_instruction_handled_gracefully(mock_ai):
    # User sends empty instruction
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "    "}, # Just whitespace
        headers=HEADERS
    )
    
    assert response.status_code == 400
    assert "Instruction cannot be empty" in response.json()["detail"]

@patch("app.main.parse_instruction_to_command")
def test_unwhitelisted_operation_denied(mock_ai):
    # Mock LLM outputs an operation that is safe but NOT in the whitelist
    mock_ai.return_value = CommandSchema(
        op="billing.update_credit_card",
        actions=["update_cc"],
        is_safe=True, 
        needs_clarification=False
    )
    
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "Update user's billing credit card"},
        headers=HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not in the allowed list" in data["error"] or "not permitted" in data["error"]

@patch("app.main.parse_instruction_to_command")
def test_ai_service_runtime_error(mock_ai):
    # Simulates Gemini API going down or throwing an exception
    mock_ai.side_effect = RuntimeError("Failed to reach Gemini API")
    
    response = client.post(
        "/api/v1/parse-command", 
        json={"instruction": "Check system health"},
        headers=HEADERS
    )
    
    # Wait, FastAPI catches exceptions as 500
    assert response.status_code == 500
    assert "Failed to reach Gemini API" in response.json()["detail"]
