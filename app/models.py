from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class UserRole(str, Enum):
    viewer = "viewer"
    operator = "operator"
    approver = "approver"
    admin = "admin"


class ExecutionMode(str, Enum):
    execute = "execute"
    dry_run = "dry_run"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class CommandStatus(str, Enum):
    received = "received"
    parsed = "parsed"
    needs_clarification = "needs_clarification"
    blocked = "blocked"
    dry_run_completed = "dry_run_completed"
    needs_approval = "needs_approval"
    approved = "approved"
    rejected = "rejected"
    queued = "queued"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class CommandRequest(BaseModel):
    instruction: str = Field(..., min_length=1, description="Natural language instruction submitted by the user.")
    environment: str = Field(default="staging", description="Target environment such as dev, staging, or production.")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.execute)
    context: dict[str, Any] = Field(default_factory=dict, description="Optional caller context for downstream execution.")

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Instruction cannot be empty.")
        return trimmed

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        return normalized or "staging"


class CommandSchema(BaseModel):
    op: str = Field(..., description="Structured operation name, for example `service.restart`.")
    summary: str = Field(default="", description="Human-readable summary of the requested action.")
    actions: list[str] = Field(default_factory=list, description="Fine-grained tasks for the execution worker.")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Arguments required by the operation.")
    target_service: str = Field(default="", description="Named service or subsystem affected by the command.")
    environment: str = Field(default="staging", description="Target environment extracted from the request.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Parser confidence score between 0 and 1.")
    risk_level: RiskLevel = Field(default=RiskLevel.medium)
    is_safe: bool = Field(..., description="Whether the requested action is non-destructive.")
    approval_required: bool = Field(default=False, description="Whether the command should wait for human approval.")
    needs_clarification: bool = Field(default=False, description="Whether the command is too ambiguous to proceed.")
    clarification_message: str = Field(default="", description="Question shown when more information is required.")
    execution_notes: str = Field(default="", description="Additional notes for operators or workers.")
    parser_source: str = Field(default="mock", description="Name of the parser implementation that generated the command.")
    intent_label: str = Field(default="", description="Short label that describes the matched workflow.")
    matched_terms: list[str] = Field(default_factory=list, description="Keywords or phrases that helped determine the intent.")
    explanation_steps: list[str] = Field(default_factory=list, description="Human-readable explanation of how the parser understood the query.")

    @field_validator("environment")
    @classmethod
    def normalize_command_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        return normalized or "staging"

    @field_validator("summary")
    @classmethod
    def populate_summary(cls, value: str, info) -> str:
        if value.strip():
            return value.strip()
        op = info.data.get("op", "command")
        return f"Execute {op}"


class AuthenticatedUser(BaseModel):
    user_id: str
    display_name: str
    role: UserRole
    api_key_name: str = "default"


class CommandAuditEvent(BaseModel):
    id: int
    command_id: str
    event_type: str
    actor_id: str
    actor_role: UserRole
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CommandRecord(BaseModel):
    id: str
    instruction: str
    requested_by: str
    requester_role: UserRole
    environment: str
    execution_mode: ExecutionMode
    status: CommandStatus
    risk_level: RiskLevel
    approval_required: bool
    parser_source: str
    confidence: float
    decision_summary: str = ""
    decision_reasons: list[str] = Field(default_factory=list)
    next_action: str = ""
    command: CommandSchema | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    audit_trail: list[CommandAuditEvent] = Field(default_factory=list)


class CommandResponse(BaseModel):
    success: bool
    data: CommandRecord | None = None
    error: str | None = None


class CommandListResponse(BaseModel):
    commands: list[CommandRecord]


class MetricsResponse(BaseModel):
    total_commands: int
    approvals_pending: int
    blocked_commands: int
    completed_commands: int
    dry_runs: int
    failed_commands: int
    average_confidence: float


class DecisionResult(BaseModel):
    status: CommandStatus
    risk_level: RiskLevel
    approval_required: bool
    summary: str
    next_action: str
    reasons: list[str] = Field(default_factory=list)


class ApprovalActionRequest(BaseModel):
    note: str = Field(default="", description="Optional audit note recorded with the action.")
