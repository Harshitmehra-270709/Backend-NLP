from __future__ import annotations

import time

from .config import AppSettings
from .models import AuthenticatedUser, CommandRecord, CommandStatus, UserRole
from .storage import CommandRepository


SYSTEM_ACTOR = AuthenticatedUser(
    user_id="system-worker",
    display_name="System Worker",
    role=UserRole.admin,
    api_key_name="internal",
)


class ExecutionEngine:
    def __init__(self, repository: CommandRepository, settings: AppSettings) -> None:
        self.repository = repository
        self.settings = settings

    def build_dry_run_preview(self, record: CommandRecord) -> dict:
        command = record.command
        if command is None:
            return {"preview": "Command not parsed yet."}

        return {
            "mode": "dry_run",
            "would_execute": command.op,
            "target_service": command.target_service or "generic-system",
            "environment": command.environment,
            "actions": command.actions,
            "parameters": command.parameters,
            "notes": [
                "No downstream action was executed.",
                "This preview is intended for operator review and debugging.",
            ],
        }

    def run(self, command_id: str) -> None:
        record = self.repository.get_command(command_id)
        command = record.command
        if command is None:
            self.repository.update_command(
                command_id,
                status=CommandStatus.failed,
                decision_summary="Execution stopped because there was no parsed command to run.",
                decision_reasons=["The worker expected a structured command, but none was attached to this record."],
                next_action="Inspect the parser response and submit the request again.",
                error="Execution aborted because no parsed command was attached.",
            )
            return

        self.repository.update_command(
            command_id,
            status=CommandStatus.executing,
            decision_summary="The worker is currently executing the approved command.",
            next_action="Wait for the worker to finish and then review the execution result.",
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=SYSTEM_ACTOR,
            event_type="executing",
            message=f"Worker started executing {command.op}.",
            payload={"actions": command.actions},
        )

        time.sleep(self.settings.execution_delay_seconds)

        result = {
            "worker": "mock-executor",
            "status": "completed",
            "operation": command.op,
            "target_service": command.target_service or "generic-system",
            "environment": command.environment,
            "actions_executed": command.actions,
            "parameters_used": command.parameters,
            "message": f"Mock execution finished for {command.op}.",
        }
        self.repository.update_command(
            command_id,
            status=CommandStatus.completed,
            decision_summary="The worker finished the command successfully.",
            decision_reasons=["The command reached the execution layer and completed without raising an error."],
            next_action="Inspect the result payload or submit another request.",
            result=result,
        )
        self.repository.add_audit_event(
            command_id=command_id,
            actor=SYSTEM_ACTOR,
            event_type="completed",
            message=f"Worker completed {command.op}.",
            payload=result,
        )
