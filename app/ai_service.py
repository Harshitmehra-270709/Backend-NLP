from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from google import genai
from google.genai import types

from .config import AppSettings
from .models import CommandSchema, RiskLevel


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You convert natural language operational requests into a strict JSON command schema.

Rules:
1. Return only JSON that matches the supplied schema.
2. Use namespaced operations such as service.restart or database.backup.
3. Mark destructive actions as unsafe.
4. Ask for clarification if the request is too ambiguous to execute safely.
5. Set approval_required to true for risky production actions.
6. Fill intent_label, matched_terms, and explanation_steps so operators can understand why the command was created.
"""


@dataclass(frozen=True, slots=True)
class QueryContext:
    raw_text: str
    normalized_text: str
    environment: str
    target_service: str


def parse_instruction_to_command(
    instruction: str,
    environment: str,
    settings: AppSettings | None = None,
) -> CommandSchema:
    active_settings = settings or AppSettings.from_env()
    parser_mode = active_settings.parser_mode

    if parser_mode == "mock":
        return _mock_parse(instruction, environment)

    if parser_mode == "gemini" or (parser_mode == "auto" and active_settings.gemini_api_key):
        try:
            return _gemini_parse(active_settings.gemini_api_key, instruction, environment)
        except Exception:
            logger.exception("Gemini parser failed; falling back to the deterministic mock parser.")
            return _mock_parse(instruction, environment)

    return _mock_parse(instruction, environment)


def _gemini_parse(api_key: str, instruction: str, environment: str) -> CommandSchema:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Environment: {environment}\nInstruction: {instruction}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=CommandSchema,
            temperature=0.0,
        ),
    )
    return CommandSchema.model_validate_json(response.text)


def _mock_parse(instruction: str, environment: str) -> CommandSchema:
    # The mock parser is intentionally rule-based. That keeps the local demo
    # deterministic and makes the query-to-command logic easy to inspect.
    context = _build_query_context(instruction, environment)

    for handler in (
        _match_ambiguous_request,
        _match_dangerous_request,
        _match_health_fix_request,
        _match_health_request,
        _match_restart_request,
        _match_backup_request,
        _match_create_user_request,
        _match_update_user_request,
        _match_scale_request,
    ):
        command = handler(context)
        if command is not None:
            return command

    return _build_clarification_command(
        context,
        intent_label="Unsupported workflow",
        clarification_message=(
            "This workflow is not recognized yet. Try specifying the target system "
            "and the action more clearly."
        ),
        matched_terms=[],
        explanation_steps=[
            "Normalized the query but could not match it to a supported workflow.",
            "No command was generated because the backend only allows known operational actions.",
        ],
    )


def _build_query_context(instruction: str, environment: str) -> QueryContext:
    raw_text = instruction.strip()
    normalized_text = re.sub(r"\s+", " ", raw_text.lower())
    detected_environment = _extract_environment(normalized_text) or environment.strip().lower() or "staging"
    target_service = _extract_target_service(normalized_text)

    return QueryContext(
        raw_text=raw_text,
        normalized_text=normalized_text,
        environment=detected_environment,
        target_service=target_service,
    )


def _match_ambiguous_request(context: QueryContext) -> CommandSchema | None:
    if not _is_ambiguous(context.normalized_text):
        return None

    matched_terms = _collect_terms(context.normalized_text, ["fix", "restart", "server"])
    explanation_steps = [
        "Normalized the request and found a very short instruction without a reliable target.",
        "The parser avoided guessing because executing the wrong system action would be risky.",
    ]
    return _build_clarification_command(
        context,
        intent_label="Needs clarification",
        clarification_message="Please specify the target service or system and what exact action should be taken.",
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
    )


def _match_dangerous_request(context: QueryContext) -> CommandSchema | None:
    dangerous_terms = _collect_terms(context.normalized_text, ["drop", "wipe", "delete all", "rm -rf"])
    if not dangerous_terms:
        return None

    operation = "database.drop" if "database" in context.normalized_text else "system.rm_rf"
    explanation_steps = [
        f"Detected destructive language: {', '.join(dangerous_terms)}.",
        f"Mapped the request to the blocked operation `{operation}` and marked it unsafe.",
    ]
    return _build_command(
        context,
        op=operation,
        intent_label="Blocked destructive request",
        summary="Potentially destructive operation detected.",
        actions=["destructive_action_detected"],
        parameters={"original_instruction": context.raw_text},
        risk_level=RiskLevel.critical,
        confidence=0.92,
        is_safe=False,
        approval_required=True,
        matched_terms=dangerous_terms,
        explanation_steps=explanation_steps,
        execution_notes="Dangerous requests are blocked regardless of model output.",
    )


def _match_health_fix_request(context: QueryContext) -> CommandSchema | None:
    matched_terms = _collect_terms(context.normalized_text, ["health", "fix"])
    if len(matched_terms) < 2:
        return None

    explanation_steps = [
        "Matched both `health` and `fix`, which maps to the safe remediation workflow.",
        "Built a structured command that first checks health and then applies minor predefined fixes.",
    ]
    return _build_command(
        context,
        op="system.check_and_fix",
        intent_label="Safe remediation",
        summary="Run a health check and apply predefined low-risk fixes.",
        actions=["health_check", "auto_fix"],
        parameters={"auto_fix_scope": "minor"},
        target_service=context.target_service or "platform",
        risk_level=RiskLevel.medium,
        confidence=0.94,
        is_safe=True,
        approval_required=context.environment == "production",
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Suitable for routine remediation flows.",
    )


def _match_health_request(context: QueryContext) -> CommandSchema | None:
    matched_terms = _collect_terms(context.normalized_text, ["health", "status"])
    if not matched_terms:
        return None

    explanation_steps = [
        f"Matched read-only diagnostic terms: {', '.join(matched_terms)}.",
        "Mapped the query to the health-check workflow because no destructive action was requested.",
    ]
    return _build_command(
        context,
        op="system.health_check",
        intent_label="Health inspection",
        summary="Inspect service health and report the status.",
        actions=["health_check"],
        parameters={"include_dependencies": True},
        target_service=context.target_service or "platform",
        risk_level=RiskLevel.low,
        confidence=0.90,
        is_safe=True,
        approval_required=False,
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Read-only diagnostic action.",
    )


def _match_restart_request(context: QueryContext) -> CommandSchema | None:
    if "restart" not in context.normalized_text:
        return None

    matched_terms = _with_target_service(context, ["restart"])
    explanation_steps = [
        "Matched the `restart` intent and looked for a target service in the request.",
        (
            f"Detected the target service `{context.target_service}`."
            if context.target_service
            else "No target service was detected, so the command must be clarified before it can run."
        ),
    ]
    return _build_command(
        context,
        op="service.restart",
        intent_label="Service restart",
        summary="Restart the requested service.",
        actions=["restart_service", "verify_uptime"],
        parameters={"service": context.target_service or "unspecified-service"},
        risk_level=RiskLevel.high,
        confidence=0.88,
        is_safe=True,
        approval_required=context.environment == "production",
        needs_clarification=not bool(context.target_service),
        clarification_message="Which service should be restarted?" if not context.target_service else "",
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Restarting services in production requires approval.",
    )


def _match_backup_request(context: QueryContext) -> CommandSchema | None:
    if "backup" not in context.normalized_text:
        return None

    matched_terms = _with_target_service(context, ["backup"])
    explanation_steps = [
        "Matched the `backup` keyword and treated the request as a pre-change safety step.",
        "Built a command that validates the destination, creates the backup, and verifies the artifact.",
    ]
    return _build_command(
        context,
        op="database.backup",
        intent_label="Database backup",
        summary="Create a backup before a sensitive change.",
        actions=["validate_backup_target", "create_backup", "verify_backup_artifact"],
        parameters={"compression": "enabled"},
        target_service=context.target_service or "database",
        risk_level=RiskLevel.medium,
        confidence=0.87,
        is_safe=True,
        approval_required=context.environment == "production",
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Useful as a pre-deployment safeguard.",
    )


def _match_create_user_request(context: QueryContext) -> CommandSchema | None:
    if not any(phrase in context.normalized_text for phrase in ("create user", "add user")):
        return None

    requested_role = _extract_user_role(context.normalized_text)
    matched_terms = _dedupe(["create user", requested_role])
    explanation_steps = [
        "Matched the user-provisioning workflow from the phrase `create user` or `add user`.",
        f"Extracted the requested role `{requested_role}` for the downstream identity action.",
    ]
    return _build_command(
        context,
        op="user.create",
        intent_label="User provisioning",
        summary="Provision a new user account.",
        actions=["validate_user_payload", "create_user", "send_invite"],
        parameters={"requested_role": requested_role},
        target_service=context.target_service or "identity",
        risk_level=RiskLevel.medium,
        confidence=0.85,
        is_safe=True,
        approval_required=False,
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Can be extended to sync with an identity provider.",
    )


def _match_update_user_request(context: QueryContext) -> CommandSchema | None:
    if not any(phrase in context.normalized_text for phrase in ("update user", "change user")):
        return None

    matched_terms = _collect_terms(context.normalized_text, ["update user", "change user"])
    explanation_steps = [
        "Matched a user-maintenance request from the phrases `update user` or `change user`.",
        "Prepared a record-update workflow that loads the user, applies changes, and records an audit entry.",
    ]
    return _build_command(
        context,
        op="user.update",
        intent_label="User maintenance",
        summary="Update an existing user record.",
        actions=["load_user", "apply_changes", "write_audit_entry"],
        parameters={},
        target_service=context.target_service or "identity",
        risk_level=RiskLevel.medium,
        confidence=0.82,
        is_safe=True,
        approval_required=False,
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Requires downstream identity system integration in production.",
    )


def _match_scale_request(context: QueryContext) -> CommandSchema | None:
    if "scale" not in context.normalized_text:
        return None

    desired_capacity = _extract_capacity(context.normalized_text)
    matched_terms = _with_target_service(context, ["scale", str(desired_capacity)])
    explanation_steps = [
        "Matched the `scale` intent and extracted the requested capacity value.",
        (
            f"Detected the target service `{context.target_service}`."
            if context.target_service
            else "No target service was detected, so the workflow must be clarified before execution."
        ),
    ]
    return _build_command(
        context,
        op="service.scale",
        intent_label="Service scaling",
        summary="Scale a service up or down.",
        actions=["validate_capacity_window", "update_scaling_policy", "verify_health"],
        parameters={"desired_capacity": desired_capacity},
        risk_level=RiskLevel.high,
        confidence=0.80,
        is_safe=True,
        approval_required=True,
        needs_clarification=not bool(context.target_service),
        clarification_message="Which service should be scaled?" if not context.target_service else "",
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Scaling actions are approval-gated because they affect live traffic.",
    )


def _build_clarification_command(
    context: QueryContext,
    *,
    intent_label: str,
    clarification_message: str,
    matched_terms: list[str],
    explanation_steps: list[str],
) -> CommandSchema:
    return _build_command(
        context,
        op="clarification.required",
        intent_label=intent_label,
        summary="More detail is needed before the command can be executed.",
        actions=[],
        parameters={"original_instruction": context.raw_text},
        risk_level=RiskLevel.medium,
        confidence=0.34,
        is_safe=True,
        approval_required=False,
        needs_clarification=True,
        clarification_message=clarification_message,
        matched_terms=matched_terms,
        explanation_steps=explanation_steps,
        execution_notes="Parser requested clarification because the instruction lacked reliable detail.",
    )


def _build_command(
    context: QueryContext,
    *,
    op: str,
    intent_label: str,
    summary: str,
    actions: list[str],
    parameters: dict,
    risk_level: RiskLevel,
    confidence: float,
    is_safe: bool,
    approval_required: bool,
    matched_terms: list[str],
    explanation_steps: list[str],
    target_service: str = "",
    needs_clarification: bool = False,
    clarification_message: str = "",
    execution_notes: str = "",
) -> CommandSchema:
    resolved_target_service = target_service or context.target_service
    terms = _dedupe([*matched_terms, context.environment, resolved_target_service])

    return CommandSchema(
        op=op,
        intent_label=intent_label,
        summary=summary,
        actions=actions,
        parameters=parameters,
        target_service=resolved_target_service,
        environment=context.environment,
        confidence=confidence,
        risk_level=risk_level,
        is_safe=is_safe,
        approval_required=approval_required,
        needs_clarification=needs_clarification,
        clarification_message=clarification_message,
        execution_notes=execution_notes,
        parser_source="mock",
        matched_terms=terms,
        explanation_steps=[
            f"Normalized query: `{context.normalized_text}`.",
            *explanation_steps,
        ],
    )


def _collect_terms(text: str, candidates: list[str]) -> list[str]:
    return [candidate for candidate in candidates if candidate and candidate in text]


def _with_target_service(context: QueryContext, terms: list[str]) -> list[str]:
    return _dedupe([*terms, context.target_service])


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _extract_environment(text: str) -> str:
    for environment in ("production", "staging", "dev"):
        if environment in text:
            return environment
    return ""


def _extract_target_service(text: str) -> str:
    for service in (
        "auth",
        "billing",
        "search",
        "payments",
        "database",
        "gateway",
        "frontend",
        "backend",
        "api",
        "server",
    ):
        if service in text:
            return service
    return ""


def _extract_user_role(text: str) -> str:
    for role in ("admin", "viewer", "operator", "approver"):
        if role in text:
            return role
    return "viewer"


def _extract_capacity(text: str) -> int:
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 2


def _is_ambiguous(text: str) -> bool:
    short_prompts = {
        "fix it",
        "restart it",
        "do it",
        "handle it",
        "fix the server",
    }
    return text in short_prompts
