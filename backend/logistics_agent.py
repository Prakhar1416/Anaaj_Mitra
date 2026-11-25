from typing import Any

from backend.common import new_id, utcnow_iso
from backend.config import COMPATIBLE_GRAIN_TYPES
from backend.shared_state import SharedState

EARLY_MOVEMENT = "Early movement recommended"
NO_URGENT_MOVEMENT = "No urgent warehouse transfer required"


class LogisticsAgent:
    """Adapter for the logistics stream.

    The browser simulation is still the logistics rule other teammates shipped:
    high spoilage asks for early movement, and every other spoilage level does
    not. This adapter keeps those sentences and adds a stock and feasibility
    check when the coordinator asks for a nutrition-priority reassessment.

    A reassessment records a recommendation. It does not decrement stock and
    it never marks a delivery complete.
    """

    def __init__(self, shared_state: SharedState, min_delivery_kg: float) -> None:
        self.shared_state = shared_state
        self.min_delivery_kg = min_delivery_kg

    def movement_recommendation(self, spoilage_risk: str | None) -> str | None:
        if not spoilage_risk:
            return None
        if spoilage_risk.strip().upper() == "HIGH":
            return EARLY_MOVEMENT
        return NO_URGENT_MOVEMENT

    def reassess_health_priority(self, event: dict[str, Any]) -> dict[str, Any]:
        warehouses = self.shared_state.list_warehouses()
        checked = []
        suitable = []
        compatible = {grain.lower() for grain in COMPATIBLE_GRAIN_TYPES}
        for warehouse in warehouses:
            grain = str(warehouse["grain_type"]).lower()
            is_suitable = (
                grain in compatible
                and float(warehouse["available_stock_kg"]) >= self.min_delivery_kg
            )
            checked.append(
                {
                    "warehouse_id": warehouse["warehouse_id"],
                    "available_stock_kg": warehouse["available_stock_kg"],
                    "grain_type": warehouse["grain_type"],
                    "stock_source": warehouse["stock_source"],
                    "suitable": is_suitable,
                }
            )
            if is_suitable:
                suitable.append(warehouse)

        spoilage_risk = self.shared_state.environment_spoilage_risk()
        spoilage_movement = self.movement_recommendation(spoilage_risk)
        nutrition_priority = bool(event["nutrition_priority"])
        hamlet_id = event["hamlet_id"]
        chosen = None
        if nutrition_priority and suitable:
            chosen = max(suitable, key=lambda item: float(item["available_stock_kg"]))
            decision = "REPRIORITISE"
            feasible = True
            stock_available = True
            recommendation = (
                f"Prioritise a nutrition delivery of {chosen['grain_type']} "
                f"from {chosen['warehouse_id']} to {hamlet_id}. "
                f"Suitable stock is available "
                f"({chosen['available_stock_kg']} kg, source: {chosen['stock_source']}). "
                "This is a recommendation only. No delivery was executed."
            )
        elif nutrition_priority:
            decision = "STOCK_UNAVAILABLE"
            feasible = False
            stock_available = False
            recommendation = (
                f"Nutrition priority is recorded for {hamlet_id}. "
                f"No warehouse has at least {self.min_delivery_kg:g} kg of suitable grain. "
                "No delivery was executed."
            )
        else:
            decision = "PRIORITY_CLEARED"
            feasible = False
            stock_available = bool(suitable)
            recommendation = (
                f"Nutrition priority was cleared for {hamlet_id}. "
                "No priority delivery is recommended. No delivery was executed."
            )

        if spoilage_movement:
            recommendation = f"{recommendation} Existing spoilage rule: {spoilage_movement}."

        return {
            "decision_id": new_id("DEC"),
            "event_id": event.get("event_id"),
            "hamlet_id": hamlet_id,
            "warehouse_id": None if chosen is None else chosen["warehouse_id"],
            "decision": decision,
            "recommendation": recommendation,
            "stock_available": stock_available,
            "feasible": feasible,
            "nutrition_priority": nutrition_priority,
            "spoilage_risk": spoilage_risk,
            "delivery_completed": False,
            "details": {
                "delivery_completed": False,
                "min_delivery_kg": self.min_delivery_kg,
                "warehouses_checked": checked,
                "spoilage_movement": spoilage_movement,
                "note": (
                    "Stock was not decremented. This record is a recommendation, "
                    "not a completed delivery."
                ),
            },
            "created_at": utcnow_iso(),
        }
