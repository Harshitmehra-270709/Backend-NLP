from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    AuthenticatedUser,
    CommandAuditEvent,
    CommandRecord,
    CommandSchema,
    CommandStatus,
    ExecutionMode,
    RiskLevel,
    UserRole,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CommandRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS commands (
                    id TEXT PRIMARY KEY,
                    instruction TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    requester_role TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    approval_required INTEGER NOT NULL DEFAULT 0,
                    parser_source TEXT NOT NULL DEFAULT 'mock',
                    confidence REAL NOT NULL DEFAULT 0.0,
                    decision_summary TEXT NOT NULL DEFAULT '',
                    decision_reasons_json TEXT NOT NULL DEFAULT '[]',
                    next_action TEXT NOT NULL DEFAULT '',
                    command_json TEXT,
                    result_json TEXT,
                    error_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(command_id) REFERENCES commands(id)
                )
                """
            )
            self._ensure_column(connection, "commands", "decision_summary", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "commands", "decision_reasons_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(connection, "commands", "next_action", "TEXT NOT NULL DEFAULT ''")
            connection.commit()

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    def create_command(
        self,
        *,
        command_id: str,
        instruction: str,
        user: AuthenticatedUser,
        environment: str,
        execution_mode: ExecutionMode,
    ) -> CommandRecord:
        now = utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO commands (
                    id, instruction, requested_by, requester_role, environment, execution_mode,
                    status, risk_level, approval_required, parser_source, confidence,
                    decision_summary, decision_reasons_json, next_action,
                    command_json, result_json, error_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command_id,
                    instruction,
                    user.user_id,
                    user.role.value,
                    environment,
                    execution_mode.value,
                    CommandStatus.received.value,
                    RiskLevel.low.value,
                    0,
                    "pending",
                    0.0,
                    "The command was received and is waiting for parser analysis.",
                    json.dumps([]),
                    "Wait for the parser to translate the request into a structured command.",
                    None,
                    json.dumps({}),
                    None,
                    now,
                    now,
                ),
            )
            connection.commit()

        self.add_audit_event(
            command_id=command_id,
            actor=user,
            event_type="received",
            message=f"Command received from {user.display_name}.",
            payload={"instruction": instruction, "environment": environment, "execution_mode": execution_mode.value},
        )
        return self.get_command(command_id)

    def update_command(
        self,
        command_id: str,
        *,
        status: CommandStatus | None = None,
        risk_level: RiskLevel | None = None,
        approval_required: bool | None = None,
        parser_source: str | None = None,
        confidence: float | None = None,
        decision_summary: str | None = None,
        decision_reasons: list[str] | None = None,
        next_action: str | None = None,
        command: CommandSchema | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> CommandRecord:
        now = utc_now().isoformat()
        updates: list[str] = ["updated_at = ?"]
        values: list[Any] = [now]

        if status is not None:
            updates.append("status = ?")
            values.append(status.value)
        if risk_level is not None:
            updates.append("risk_level = ?")
            values.append(risk_level.value)
        if approval_required is not None:
            updates.append("approval_required = ?")
            values.append(int(approval_required))
        if parser_source is not None:
            updates.append("parser_source = ?")
            values.append(parser_source)
        if confidence is not None:
            updates.append("confidence = ?")
            values.append(confidence)
        if decision_summary is not None:
            updates.append("decision_summary = ?")
            values.append(decision_summary)
        if decision_reasons is not None:
            updates.append("decision_reasons_json = ?")
            values.append(json.dumps(decision_reasons))
        if next_action is not None:
            updates.append("next_action = ?")
            values.append(next_action)
        if command is not None:
            updates.append("command_json = ?")
            values.append(command.model_dump_json())
        if result is not None:
            updates.append("result_json = ?")
            values.append(json.dumps(result))
        if error is not None:
            updates.append("error_text = ?")
            values.append(error)

        values.append(command_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE commands SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            connection.commit()

        return self.get_command(command_id)

    def add_audit_event(
        self,
        *,
        command_id: str,
        actor: AuthenticatedUser,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    command_id, event_type, actor_id, actor_role, message, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command_id,
                    event_type,
                    actor.user_id,
                    actor.role.value,
                    message,
                    json.dumps(payload or {}),
                    utc_now().isoformat(),
                ),
            )
            connection.commit()

    def get_command(self, command_id: str) -> CommandRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commands WHERE id = ?",
                (command_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Command '{command_id}' was not found.")

            audit_rows = connection.execute(
                "SELECT * FROM audit_events WHERE command_id = ? ORDER BY created_at ASC, id ASC",
                (command_id,),
            ).fetchall()

        return self._deserialize_command(row, audit_rows)

    def list_commands(self, limit: int = 25) -> list[CommandRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM commands ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            audit_rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY created_at DESC, id DESC"
            ).fetchall()

        audit_map: dict[str, list[sqlite3.Row]] = {}
        for audit_row in audit_rows:
            audit_map.setdefault(audit_row["command_id"], []).append(audit_row)

        records: list[CommandRecord] = []
        for row in rows:
            row_audit = list(reversed(audit_map.get(row["id"], [])))
            records.append(self._deserialize_command(row, row_audit))
        return records

    def get_metrics(self) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute("SELECT status, execution_mode, confidence FROM commands").fetchall()

        total = len(rows)
        if total == 0:
            return {
                "total_commands": 0,
                "approvals_pending": 0,
                "blocked_commands": 0,
                "completed_commands": 0,
                "dry_runs": 0,
                "failed_commands": 0,
                "average_confidence": 0.0,
            }

        average_confidence = sum(float(row["confidence"]) for row in rows) / total
        return {
            "total_commands": total,
            "approvals_pending": sum(row["status"] == CommandStatus.needs_approval.value for row in rows),
            "blocked_commands": sum(row["status"] == CommandStatus.blocked.value for row in rows),
            "completed_commands": sum(row["status"] == CommandStatus.completed.value for row in rows),
            "dry_runs": sum(row["execution_mode"] == ExecutionMode.dry_run.value for row in rows),
            "failed_commands": sum(row["status"] == CommandStatus.failed.value for row in rows),
            "average_confidence": round(average_confidence, 3),
        }

    def _deserialize_command(
        self,
        row: sqlite3.Row,
        audit_rows: list[sqlite3.Row],
    ) -> CommandRecord:
        command_payload = json.loads(row["command_json"]) if row["command_json"] else None
        result_payload = json.loads(row["result_json"]) if row["result_json"] else {}
        command = CommandSchema.model_validate(command_payload) if command_payload else None
        audit_trail = [
            CommandAuditEvent(
                id=audit_row["id"],
                command_id=audit_row["command_id"],
                event_type=audit_row["event_type"],
                actor_id=audit_row["actor_id"],
                actor_role=UserRole(audit_row["actor_role"]),
                message=audit_row["message"],
                payload=json.loads(audit_row["payload_json"]) if audit_row["payload_json"] else {},
                created_at=datetime.fromisoformat(audit_row["created_at"]),
            )
            for audit_row in audit_rows
        ]

        return CommandRecord(
            id=row["id"],
            instruction=row["instruction"],
            requested_by=row["requested_by"],
            requester_role=UserRole(row["requester_role"]),
            environment=row["environment"],
            execution_mode=ExecutionMode(row["execution_mode"]),
            status=CommandStatus(row["status"]),
            risk_level=RiskLevel(row["risk_level"]),
            approval_required=bool(row["approval_required"]),
            parser_source=row["parser_source"],
            confidence=float(row["confidence"]),
            decision_summary=row["decision_summary"],
            decision_reasons=json.loads(row["decision_reasons_json"]) if row["decision_reasons_json"] else [],
            next_action=row["next_action"],
            command=command,
            result=result_payload,
            error=row["error_text"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            audit_trail=audit_trail,
        )
