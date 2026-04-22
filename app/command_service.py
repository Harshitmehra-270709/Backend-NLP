from __future__ import annotations

from uuid import uuid4

from fastapi import BackgroundTasks

from .ai_service import parse_instruction_to_command
from .config import AppSettings
from .execution_engine import ExecutionEngine, SYSTEM_ACTOR
from .models import AuthenticatedUser, CommandRecord, CommandRequest, CommandResponse, CommandStatus, UserRole
from .security_policy import evaluate_command
from .storage import CommandRepository


class CommandService:
    def __init__(
        self,
        repository: CommandRepository,
        execution_engine: ExecutionEngine,
        settings: AppSettings,
    ) -> None:
        self.repository = repository
        self.execution_engine = execution_engine
        self.settings = settings

    def submit_command(
        self,
        request: CommandRequest,
        user: AuthenticatedUser,
        background_tasks: BackgroundTasks,
    ) -> CommandResponse:
        # We persist the command immediately so every request leaves an audit trail,
        # even if the parser or policy engine later rejects it.
        command_id = f"cmd_{uuid4().hex[:12]}"
        record = self.repository.create_command(
            command_id=command_id,
            instruction=request.instruction,
            user=user,
            environment=request.environment,
            execution_mode=request.execution_mode,
        )

        try:
            command = parse_instruction_to_command(
                instruction=request.instruction,
                environment=request.environment,
                settings=self.settings,
            )
        except Exception as exc:
            message = str(exc)
            self.repository.update_command(
                command_id,
                status=CommandStatus.failed,
                decision_summary="The parser failed before a command could be created.",
                decision_reasons=["The backend could not convert the query into a structured command."],
                next_action="Inspect the parser error and submit the request again.",
                error=message,
            )
            self.repository.add_audit_event(
                command_id=command_id,
                actor=user,
                event_type="parser_failed",
                message="Parser failed before policy checks could run.",
                payload={"error": message},
            )
            return CommandResponse(success=False, data=self.repository.get_command(command_id), error=message)

        self.repository.update_command(
            command_id,
            status=CommandStatus.parsed,
            risk_level=command.risk_level,
            approval_required=command.approval_required,
            parser_source=command.parser_source,
            confidence=command.confidence,
            decision_summary="The request was parsed successfully and is waiting for policy evaluation.",
            decision_reasons=command.explanation_steps,
            next_action="Review the policy decision to see whether the command can run, needs approval, or must be revised.",
            command=command,
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=user,
            event_type="parsed",
            message=f"Parser returned {command.op}.",
            payload={"command": command.model_dump(mode="json")},
        )

        decision = evaluate_command(command, user, request.execution_mode)
        record = self.repository.update_command(
            command_id,
            status=decision.status,
            risk_level=decision.risk_level,
            approval_required=decision.approval_required,
            decision_summary=decision.summary,
            decision_reasons=decision.reasons,
            next_action=decision.next_action,
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=user,
            event_type="policy_decision",
            message="Policy engine evaluated the command.",
            payload={"reasons": decision.reasons, "status": decision.status.value},
        )

        if decision.status == CommandStatus.needs_clarification:
            return CommandResponse(
                success=False,
                data=record,
                error=command.clarification_message or "More information is required before this command can continue.",
            )

        if decision.status == CommandStatus.blocked:
            return CommandResponse(
                success=False,
                data=record,
                error="Security policy blocked the request.",
            )

        if decision.status == CommandStatus.dry_run_completed:
            preview = self.execution_engine.build_dry_run_preview(record)
            self.repository.update_command(
                command_id,
                result=preview,
                next_action="Review the dry run preview. If everything looks right, switch to execute mode and submit again.",
            )
            self.repository.add_audit_event(
                command_id=command_id,
                actor=user,
                event_type="dry_run_preview",
                message="Dry run preview generated.",
                payload=preview,
            )
            return CommandResponse(success=True, data=self.repository.get_command(command_id))

        if decision.status == CommandStatus.needs_approval:
            return CommandResponse(
                success=True,
                data=record,
                error="Command is waiting for approver review before execution.",
            )

        return CommandResponse(success=True, data=self._queue_execution(record.id, background_tasks))

    def approve_command(
        self,
        command_id: str,
        user: AuthenticatedUser,
        background_tasks: BackgroundTasks,
        note: str = "",
    ) -> CommandRecord:
        if user.role not in (UserRole.approver, UserRole.admin):
            raise ValueError("Only approvers or admins can approve commands.")

        record = self.repository.get_command(command_id)
        if record.status != CommandStatus.needs_approval:
            raise ValueError("Only commands waiting for approval can be approved.")

        self.repository.update_command(
            command_id,
            status=CommandStatus.approved,
            decision_summary="The command was approved and is ready to execute.",
            decision_reasons=["An approver or admin reviewed the request and allowed execution."],
            next_action="The worker will queue and execute the command next.",
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=user,
            event_type="approved",
            message="Approver approved the command for execution.",
            payload={"note": note},
        )
        return self._queue_execution(command_id, background_tasks)

    def reject_command(self, command_id: str, user: AuthenticatedUser, note: str = "") -> CommandRecord:
        if user.role not in (UserRole.approver, UserRole.admin):
            raise ValueError("Only approvers or admins can reject commands.")

        record = self.repository.get_command(command_id)
        if record.status != CommandStatus.needs_approval:
            raise ValueError("Only commands waiting for approval can be rejected.")

        self.repository.update_command(
            command_id,
            status=CommandStatus.rejected,
            decision_summary="The command was rejected during human review.",
            decision_reasons=["An approver or admin rejected the request before execution."],
            next_action="Revise the request or add more context before trying again.",
            error="Command rejected by approver.",
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=user,
            event_type="rejected",
            message="Approver rejected the command.",
            payload={"note": note},
        )
        return self.repository.get_command(command_id)

    def _queue_execution(self, command_id: str, background_tasks: BackgroundTasks) -> CommandRecord:
        self.repository.update_command(
            command_id,
            status=CommandStatus.queued,
            decision_summary="The command is valid and has been placed in the execution queue.",
            next_action="Wait for the worker to execute the command and then review the result.",
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=SYSTEM_ACTOR,
            event_type="queued",
            message="Command queued for execution.",
            payload={},
        )
        background_tasks.add_task(self.execution_engine.run, command_id)
        return self.repository.get_command(command_id)
