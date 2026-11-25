import json
from typing import Any

from backend.common import ID_PATTERN, new_id, utcnow_iso
from backend.coordinator import Coordinator
from backend.errors import AppError
from backend.shared_state import SharedState

DUPLICATE_MESSAGE = (
    "Current nutrition-priority status already matches this report. "
    "No new event or logistics reassessment was created."
)


class HealthAgent:
    """Accepts a community health-worker report and marks hamlet priority.

    The agent is rule-based. It checks the hamlet registry, stores the current
    flag, keeps every accepted change as an event, and asks the coordinator
    to reassess logistics. An identical resubmission is a duplicate: the
    current flag stays, history stays, and logistics is not asked again.
    """

    def __init__(self, shared_state: SharedState, coordinator: Coordinator) -> None:
        self.shared_state = shared_state
        self.coordinator = coordinator

    def process_health_report(self, report: dict[str, Any]) -> dict[str, Any]:
        try:
            normalized = self._normalize(report)
        except AppError as error:
            self._log_rejection(report, error)
            raise

        duplicate_result: dict[str, Any] | None = None
        accepted: dict[str, Any] | None = None
        conflict: AppError | None = None

        with self.shared_state.transaction() as connection:
            if not self.shared_state.hamlet_exists(normalized["hamlet_id"], connection):
                conflict = AppError(
                    "unknown_hamlet",
                    f"Unknown hamlet_id '{normalized['hamlet_id']}'.",
                    404,
                )
            else:
                existing = None
                if normalized["idempotency_key"]:
                    existing = self.shared_state.get_report_by_key(
                        normalized["idempotency_key"], connection
                    )
                if existing is not None and not _same_identity(existing, normalized):
                    conflict = AppError(
                        "idempotency_conflict",
                        "idempotency_key was already used with a different report.",
                        409,
                    )
                elif existing is not None:
                    duplicate_result = self._duplicate_from_row(existing)
                    self._log(
                        connection,
                        "HEALTH_REPORT_DUPLICATE",
                        duplicate_result.get("event_id"),
                        normalized,
                        "duplicate",
                        "success",
                        None,
                    )
                else:
                    row = connection.execute(
                        "SELECT * FROM hamlets WHERE hamlet_id = ?",
                        (normalized["hamlet_id"],),
                    ).fetchone()
                    current_matches = (
                        row["last_event_id"] is not None
                        and bool(row["nutrition_priority"])
                        == normalized["nutrition_priority"]
                        and row["priority_reason"] == normalized["reason"]
                        and row["priority_reported_by"] == normalized["reported_by"]
                    )
                    if current_matches:
                        latest = self.shared_state.latest_report(
                            normalized["hamlet_id"], connection
                        )
                        duplicate_result = self._duplicate_from_row(latest)
                        self._log(
                            connection,
                            "HEALTH_REPORT_DUPLICATE",
                            duplicate_result.get("event_id"),
                            normalized,
                            "duplicate",
                            "success",
                            None,
                        )
                    else:
                        accepted = self._persist(connection, normalized)

        if conflict is not None:
            self._log_rejection(normalized, conflict)
            raise conflict
        if duplicate_result is not None:
            return duplicate_result

        assert accepted is not None
        decision = self.coordinator.publish(accepted["event"])
        accepted["result"]["logistics_decision"] = decision
        accepted["result"]["reassessment_triggered"] = True
        self.shared_state.update_report_result(
            accepted["result"]["report_id"], accepted["result"]
        )
        return accepted["result"]

    def _persist(
        self, connection: Any, normalized: dict[str, Any]
    ) -> dict[str, Any]:
        timestamp = utcnow_iso()
        report_id = new_id("RPT")
        event_id = new_id("EVT")
        event = {
            "event_id": event_id,
            "event_type": "HEALTH_PRIORITY_UPDATED",
            "hamlet_id": normalized["hamlet_id"],
            "nutrition_priority": normalized["nutrition_priority"],
            "source": "health_agent",
            "reason": normalized["reason"],
            "reported_by": normalized["reported_by"],
            "report_id": report_id,
            "timestamp": timestamp,
        }
        stored_report = {
            "report_id": report_id,
            "hamlet_id": normalized["hamlet_id"],
            "nutrition_priority": normalized["nutrition_priority"],
            "reason": normalized["reason"],
            "reported_by": normalized["reported_by"],
            "reported_at": normalized["reported_at"] or timestamp,
            "idempotency_key": normalized["idempotency_key"],
            "event_id": event_id,
            "created_at": timestamp,
        }
        self.shared_state.insert_health_report(stored_report, connection)
        self.shared_state.update_hamlet_health(
            {
                "hamlet_id": normalized["hamlet_id"],
                "nutrition_priority": normalized["nutrition_priority"],
                "reason": normalized["reason"],
                "reported_by": normalized["reported_by"],
                "reported_at": stored_report["reported_at"],
                "updated_at": timestamp,
                "last_event_id": event_id,
            },
            connection,
        )
        self.shared_state.insert_event(event, connection)
        result = {
            "accepted": True,
            "duplicate": False,
            "status": "accepted",
            "reassessment_triggered": True,
            "hamlet_id": normalized["hamlet_id"],
            "nutrition_priority": normalized["nutrition_priority"],
            "reason": normalized["reason"],
            "reported_by": normalized["reported_by"],
            "event_id": event_id,
            "event_type": "HEALTH_PRIORITY_UPDATED",
            "report_id": report_id,
            "message": (
                "Nutrition-priority status updated. Logistics reassessment completed."
            ),
            "logistics_decision": None,
        }
        self._log(
            connection,
            "HEALTH_REPORT_ACCEPTED",
            event_id,
            normalized,
            "accepted",
            "success",
            None,
        )
        return {"event": event, "result": result}

    def _duplicate_from_row(self, row: dict[str, Any] | None) -> dict[str, Any]:
        stored = None
        if row and row.get("result_json"):
            stored = json.loads(row["result_json"])
        if isinstance(stored, dict):
            result = dict(stored)
        else:
            result = {
                "hamlet_id": None if row is None else row.get("hamlet_id"),
                "nutrition_priority": None
                if row is None
                else bool(row.get("nutrition_priority")),
                "reason": None if row is None else row.get("reason"),
                "reported_by": None if row is None else row.get("reported_by"),
                "event_id": None if row is None else row.get("event_id"),
                "event_type": "HEALTH_PRIORITY_UPDATED",
                "report_id": None if row is None else row.get("report_id"),
                "logistics_decision": None,
            }
        result["accepted"] = False
        result["duplicate"] = True
        result["status"] = "duplicate"
        result["reassessment_triggered"] = False
        result["message"] = DUPLICATE_MESSAGE
        return result

    def _normalize(self, report: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(report, dict):
            raise AppError("malformed_report", "Health report must be an object.")
        hamlet_id = report.get("hamlet_id")
        if not isinstance(hamlet_id, str) or not ID_PATTERN.fullmatch(hamlet_id.strip()):
            raise AppError(
                "invalid_hamlet_id",
                "hamlet_id must be 1-64 characters of letters, numbers, '_' or '-'.",
            )
        if not isinstance(report.get("nutrition_priority"), bool):
            raise AppError(
                "invalid_nutrition_priority",
                "nutrition_priority must be a boolean.",
            )
        reason = _optional_text(report.get("reason"), "reason", 500)
        reported_by = report.get("reported_by")
        if reported_by is not None:
            if not isinstance(reported_by, str) or not ID_PATTERN.fullmatch(
                reported_by.strip()
            ):
                raise AppError(
                    "invalid_reported_by",
                    "reported_by must be 1-64 characters of letters, numbers, '_' or '-'.",
                )
            reported_by = reported_by.strip()
        idempotency_key = report.get("idempotency_key")
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not ID_PATTERN.fullmatch(
                idempotency_key.strip()
            ):
                raise AppError(
                    "invalid_idempotency_key",
                    "idempotency_key must be 1-64 characters of letters, numbers, '_' or '-'.",
                )
            idempotency_key = idempotency_key.strip()
        reported_at = report.get("reported_at")
        if reported_at is not None and not isinstance(reported_at, str):
            raise AppError(
                "invalid_reported_at",
                "reported_at must be an ISO-8601 string.",
            )
        return {
            "hamlet_id": hamlet_id.strip(),
            "nutrition_priority": report["nutrition_priority"],
            "reason": reason,
            "reported_by": reported_by,
            "reported_at": reported_at,
            "idempotency_key": idempotency_key,
        }

    def _log_rejection(self, report: dict[str, Any] | Any, error: AppError) -> None:
        hamlet_id = None
        if isinstance(report, dict) and isinstance(report.get("hamlet_id"), str):
            hamlet_id = report["hamlet_id"][:64]
        self.shared_state.append_log(
            {
                "agent_name": "health_agent",
                "event_type": "HEALTH_REPORT_REJECTED",
                "event_id": None,
                "hamlet_id": hamlet_id,
                "warehouse_id": None,
                "input_summary": _summary(report if isinstance(report, dict) else {}),
                "result": "rejected",
                "status": "failure",
                "error_detail": error.message,
            }
        )

    def _log(
        self,
        connection: Any,
        event_type: str,
        event_id: str | None,
        report: dict[str, Any],
        result: str,
        status: str,
        error_detail: str | None,
    ) -> None:
        self.shared_state.append_log(
            {
                "agent_name": "health_agent",
                "event_type": event_type,
                "event_id": event_id,
                "hamlet_id": report.get("hamlet_id"),
                "warehouse_id": None,
                "input_summary": _summary(report),
                "result": result,
                "status": status,
                "error_detail": error_detail,
            },
            connection,
        )


def _optional_text(value: object, field_name: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AppError(
            "invalid_reason",
            f"{field_name} must be a string when supplied.",
        )
    text = value.strip()
    if not text:
        raise AppError(
            "invalid_reason",
            f"{field_name} must be a non-empty string when supplied.",
        )
    if len(text) > limit:
        raise AppError(
            "invalid_reason",
            f"{field_name} must be at most {limit} characters.",
        )
    return text


def _same_identity(existing: dict[str, Any], normalized: dict[str, Any]) -> bool:
    return (
        existing["hamlet_id"] == normalized["hamlet_id"]
        and bool(existing["nutrition_priority"]) == normalized["nutrition_priority"]
        and existing["reason"] == normalized["reason"]
        and existing["reported_by"] == normalized["reported_by"]
    )


def _summary(report: dict[str, Any]) -> str:
    reason = report.get("reason")
    reason_text = ""
    if isinstance(reason, str) and reason.strip():
        reason_text = f"; reason={reason.strip()[:120]}"
    return (
        f"hamlet_id={report.get('hamlet_id')}; "
        f"nutrition_priority={report.get('nutrition_priority')}; "
        f"reported_by={report.get('reported_by')}"
        f"{reason_text}"
    )
