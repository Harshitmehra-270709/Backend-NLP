from __future__ import annotations

from dataclasses import dataclass

from .models import AuthenticatedUser, CommandSchema, CommandStatus, DecisionResult, ExecutionMode, RiskLevel, UserRole


@dataclass(frozen=True, slots=True)
class PolicyRule:
    operation: str
    allowed_roles: tuple[UserRole, ...]
    base_risk: RiskLevel
    production_requires_approval: bool = False


POLICY_RULES: dict[str, PolicyRule] = {
    "system.health_check": PolicyRule(
        operation="system.health_check",
        allowed_roles=(UserRole.viewer, UserRole.operator, UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.low,
    ),
    "system.check_and_fix": PolicyRule(
        operation="system.check_and_fix",
        allowed_roles=(UserRole.operator, UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.medium,
        production_requires_approval=True,
    ),
    "service.restart": PolicyRule(
        operation="service.restart",
        allowed_roles=(UserRole.operator, UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.high,
        production_requires_approval=True,
    ),
    "service.scale": PolicyRule(
        operation="service.scale",
        allowed_roles=(UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.high,
        production_requires_approval=True,
    ),
    "database.backup": PolicyRule(
        operation="database.backup",
        allowed_roles=(UserRole.operator, UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.medium,
        production_requires_approval=True,
    ),
    "user.create": PolicyRule(
        operation="user.create",
        allowed_roles=(UserRole.operator, UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.medium,
    ),
    "user.update": PolicyRule(
        operation="user.update",
        allowed_roles=(UserRole.operator, UserRole.approver, UserRole.admin),
        base_risk=RiskLevel.medium,
    ),
}

DANGEROUS_OPERATIONS = {
    "database.drop",
    "system.rm_rf",
    "user.delete_all",
}


def evaluate_command(
    command: CommandSchema,
    user: AuthenticatedUser,
    execution_mode: ExecutionMode,
) -> DecisionResult:
    reasons: list[str] = []

    if command.needs_clarification:
        return DecisionResult(
            status=CommandStatus.needs_clarification,
            risk_level=command.risk_level,
            approval_required=False,
            summary="The request is too vague to execute safely.",
            next_action="Add the missing target service or resource and submit the request again.",
            reasons=["The parser could not identify enough detail to proceed safely."],
        )

    if not command.is_safe or command.op in DANGEROUS_OPERATIONS:
        reasons.append("The command was marked unsafe or matched an explicitly blocked operation.")
        return DecisionResult(
            status=CommandStatus.blocked,
            risk_level=RiskLevel.critical,
            approval_required=False,
            summary="The request was blocked by the safety policy.",
            next_action="Change the request to a safe and allowed operation before retrying.",
            reasons=reasons,
        )

    rule = POLICY_RULES.get(command.op)
    if rule is None:
        reasons.append("The command is not on the allowed operations list.")
        return DecisionResult(
            status=CommandStatus.blocked,
            risk_level=RiskLevel.high,
            approval_required=False,
            summary="The requested workflow is not registered in the policy engine.",
            next_action="Use a supported workflow or extend the backend policy registry.",
            reasons=reasons,
        )

    if execution_mode == ExecutionMode.dry_run:
        reasons.append("Dry runs are allowed for supported workflows because they do not touch downstream systems.")
        return DecisionResult(
            status=CommandStatus.dry_run_completed,
            risk_level=rule.base_risk,
            approval_required=False,
            summary="The request was converted into a preview-only dry run.",
            next_action="Review the preview and resubmit in execute mode if it looks correct.",
            reasons=reasons,
        )

    if user.role not in rule.allowed_roles:
        reasons.append(f"Role '{user.role.value}' is not allowed to request '{command.op}'.")
        return DecisionResult(
            status=CommandStatus.blocked,
            risk_level=rule.base_risk,
            approval_required=False,
            summary="The current role is not allowed to run this operation.",
            next_action="Switch to an allowed role or request a lower-risk action.",
            reasons=reasons,
        )

    approval_required = command.approval_required or (
        command.environment == "production" and rule.production_requires_approval
    )

    if approval_required and user.role not in (UserRole.approver, UserRole.admin):
        reasons.append("This operation requires approval before execution in the selected environment.")
        return DecisionResult(
            status=CommandStatus.needs_approval,
            risk_level=rule.base_risk,
            approval_required=True,
            summary="The command is valid, but policy requires an approver before execution.",
            next_action="Ask an approver or admin to review and approve this request.",
            reasons=reasons,
        )

    reasons.append("Command passed parser and policy validation.")
    return DecisionResult(
        status=CommandStatus.approved,
        risk_level=rule.base_risk,
        approval_required=approval_required,
        summary="The command passed policy checks and can enter the execution queue.",
        next_action="The worker will execute the command immediately.",
        reasons=reasons,
    )
