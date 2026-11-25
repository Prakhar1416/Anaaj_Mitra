import logging
from typing import Any

from backend.common import utcnow_iso
from backend.errors import AppError
from backend.logistics_agent import LogisticsAgent
from backend.shared_state import SharedState

logger = logging.getLogger("anaaj_mitra.coordinator")


class Coordinator:
    """Adapter for the missing coordination engine.

    Health priority is the only event this process handles today. Publishing
    that event asks the logistics adapter to reassess stock and feasibility.
    The coordinator stores the decision and writes the trace that links the
    health event to the logistics result.
    """

    def __init__(self, shared_state: SharedState, logistics_agent: LogisticsAgent) -> None:
        self.shared_state = shared_state
        self.logistics_agent = logistics_agent

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("event_type") != "HEALTH_PRIORITY_UPDATED":
            self.shared_state.append_log(
                {
                    "agent_name": "coordinator",
                    "event_type": str(event.get("event_type") or "UNKNOWN_EVENT"),
                    "event_id": event.get("event_id"),
                    "hamlet_id": event.get("hamlet_id"),
                    "warehouse_id": None,
                    "input_summary": "Event stored for a stream that is not connected yet.",
                    "result": "ignored",
                    "status": "success",
                    "error_detail": None,
                }
            )
            return {}
        return self._reassess(event, "HEALTH_PRIORITY_RECEIVED")

    def request_reassessment(self, hamlet_id: str) -> dict[str, Any]:
        hamlet = self.shared_state.get_hamlet(hamlet_id)
        if hamlet is None:
            raise AppError(
                "unknown_hamlet",
                f"Unknown hamlet_id '{hamlet_id}'.",
                404,
            )
        health = hamlet["health"]
        event = {
            "event_id": health["last_event_id"],
            "event_type": "HEALTH_PRIORITY_REASSESSMENT",
            "hamlet_id": hamlet_id,
            "nutrition_priority": health["nutrition_priority"],
            "reason": health["reason"],
            "reported_by": health["reported_by"],
            "source": "coordinator",
            "timestamp": utcnow_iso(),
        }
        return self._reassess(event, "HEALTH_PRIORITY_REASSESSMENT")

    def _reassess(self, event: dict[str, Any], received_type: str) -> dict[str, Any]:
        self.shared_state.append_log(
            {
                "agent_name": "coordinator",
                "event_type": received_type,
                "event_id": event.get("event_id"),
                "hamlet_id": event.get("hamlet_id"),
                "warehouse_id": None,
                "input_summary": (
                    f"nutrition_priority={event.get('nutrition_priority')}; "
                    f"source={event.get('source')}"
                ),
                "result": "reassessment_requested",
                "status": "success",
                "error_detail": None,
            }
        )
        try:
            decision = self.logistics_agent.reassess_health_priority(event)
        except Exception as exc:
            logger.exception("Logistics reassessment failed")
            self.shared_state.append_log(
                {
                    "agent_name": "logistics_agent",
                    "event_type": "LOGISTICS_REASSESSED",
                    "event_id": event.get("event_id"),
                    "hamlet_id": event.get("hamlet_id"),
                    "warehouse_id": None,
                    "input_summary": "Health-priority reassessment",
                    "result": "failed",
                    "status": "failure",
                    "error_detail": "Logistics reassessment failed.",
                }
            )
            raise AppError(
                "logistics_reassessment_failed",
                "Nutrition-priority status was saved, but logistics reassessment failed.",
                502,
            ) from exc

        self.shared_state.insert_decision(decision)
        self.shared_state.append_log(
            {
                "agent_name": "logistics_agent",
                "event_type": "LOGISTICS_REASSESSED",
                "event_id": decision.get("event_id"),
                "hamlet_id": decision["hamlet_id"],
                "warehouse_id": decision.get("warehouse_id"),
                "input_summary": (
                    f"warehouses_checked={len(decision['details']['warehouses_checked'])}; "
                    f"nutrition_priority={decision['nutrition_priority']}"
                ),
                "result": decision["decision"],
                "status": "success",
                "error_detail": None,
            }
        )
        self.shared_state.append_log(
            {
                "agent_name": "coordinator",
                "event_type": "LOGISTICS_DECISION_RECORDED",
                "event_id": decision.get("event_id"),
                "hamlet_id": decision["hamlet_id"],
                "warehouse_id": decision.get("warehouse_id"),
                "input_summary": decision["decision"],
                "result": "recorded",
                "status": "success",
                "error_detail": None,
            }
        )
        return decision
