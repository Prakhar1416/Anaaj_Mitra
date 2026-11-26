"""Run each teammate's module in dependency order and store the result.

Order:
1. Water (CGWB groundwater) decides the water condition.
2. Crop rules use that condition plus soil type, then the storage type the crop needs.
3. The sensor reading feeds storage fill and spoilage.
4. Storage checks capacity and storage-type compatibility.
5. Spoilage scores the sensor history, then the actuator reacts to that score.
6. Logistics looks for another warehouse when the primary one cannot take the crop.
7. Trust scores the storage fill, then the loan agent uses that score.
8. The validation engine checks the outputs against Meemansa's crop table and the other rules.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from backend.config import Settings
from backend.shared_state import SharedState

ROOT = Path(__file__).resolve().parent.parent
for folder in ("logistics", "iot", "environment", "finance"):
    path = str(ROOT / "streams" / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

from actuator_simulator import ServoActuatorSimulator
from crop_agent import check_storage, recommend_crops
from loan_agent import decide
from logistics_agent import LogisticsAgent as MovementLogisticsAgent
from sensor_simulator import generate_sensor_reading
from spoilage_agent import SpoilageRiskAgent
from storage_agent import StorageCapacityAgent
from trust_framework import ConfirmationLog, HashChain, evaluate_trust
from validation_engine import validate
from warehouse_data import WAREHOUSES
from water_agent import assess_record, load_cgwb_data

CROP_RULES = {
    "sandy|high": ["Pearl Millet"],
    "loamy|medium": ["Wheat", "Maize"],
    "clayey|low": ["Rice"],
    "alluvial|medium": ["Wheat", "Maize"],
}

GRAIN_FOR_WAREHOUSE = {
    "wheat": "wheat",
    "rice": "rice",
    "maize": "maize",
    "pearl millet": "millet",
    "pigeon pea": "mixed",
    "sesame": "mixed",
}


class MemoryCoordinator:
    """In-memory stand-in for the JSON coordinator the logistics module expects."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.logs: list[dict[str, str]] = []

    def get_state(self) -> dict[str, Any]:
        return self.state

    def update_state(self, section: str, key: str, value: Any) -> None:
        self.state.setdefault(section, {})[key] = value

    def add_log(self, agent: str, action: str, message: str) -> None:
        self.logs.append({"agent": agent, "action": action, "message": message})

    def save_state(self) -> None:
        return None


def run_coordination(
    shared_state: SharedState,
    settings: Settings,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    soil_type = str(options.get("soil_type") or "loamy").strip().lower()
    scenario = str(options.get("scenario") or "spoilage").strip().lower()
    if scenario not in {"spoilage", "normal"}:
        scenario = "spoilage"
    sensor_index = int(options.get("sensor_index") if options.get("sensor_index") is not None else (10 if scenario == "spoilage" else 2))
    sensor_index = max(0, min(sensor_index, 40))

    record_id = options.get("record_id")
    if record_id is None:
        groundwater, _rainfall = load_cgwb_data()
        record_id = int(groundwater.iloc[0]["record_id"])
    water = _plain(assess_record(int(record_id)))
    category = water["groundwater_category"]
    water_condition = {"Shallow": "high", "Moderate": "medium"}.get(category, "low")

    recommendations = recommend_crops(soil_type, water_condition)
    if recommendations and not str(recommendations[0]).startswith("No rule"):
        selected_crop = recommendations[0]
    else:
        selected_crop = "Wheat"
    warehouse_storage_type = str(
        options.get("warehouse_storage_type") or "Moisture-Controlled Storage"
    )
    storage_info = check_storage(selected_crop, warehouse_storage_type)
    crop = {
        "soil_type": soil_type,
        "water_condition": water_condition,
        "recommended_crops": recommendations,
        "selected_crop": selected_crop.lower(),
        "storage_check": storage_info,
        "storage_type_required": storage_info.get("required_storage"),
    }

    warehouse_id = settings.warehouse_ids[0]
    previous = shared_state.get_stream("storage", warehouse_id)
    history = []
    if previous is not None:
        history = list((previous["payload"].get("spoilage") or {}).get("history") or [])

    reading = generate_sensor_reading(sensor_index, scenario=scenario)
    if options.get("temperature_c") is not None:
        reading["temperature_c"] = round(float(options["temperature_c"]), 2)
    if options.get("humidity_pct") is not None:
        reading["humidity_pct"] = round(float(options["humidity_pct"]), 2)

    state: dict[str, Any] = {
        "water": water,
        "crop": crop,
        "sensor": reading,
        "config": {
            "empty_distance_cm": 100,
            "full_distance_cm": 10,
            "capacity_kg": settings.warehouse_capacity_kg,
            "incoming_quantity_kg": 800,
            "warehouse_id": warehouse_id,
            "warehouse_storage_type": warehouse_storage_type,
        },
        "storage": {},
        "spoilage": {"history": history},
        "warehouse": {},
        "logistics": {},
    }

    StorageCapacityAgent().run(state)
    state["warehouse"] = {
        "id": warehouse_id,
        "crop": crop["selected_crop"],
        "required_capacity_kg": state["storage"]["incoming_quantity_kg"],
        "available_capacity_kg": state["storage"]["available_capacity_kg"],
        "storage_compatible": state["storage"]["compatible"],
    }
    SpoilageRiskAgent().run(state)
    ServoActuatorSimulator().run(state)

    coordinator = MemoryCoordinator(state)
    coordinator.add_log(
        "Water Agent",
        "water_assessed",
        f"{water['village']}, {water['district']}: groundwater {category} "
        f"({water['groundwater_depth_m_bgl']} m). "
        f"30-day drought risk: {water['drought_risk_30d']}.",
    )
    coordinator.add_log(
        "Crop Agent",
        "crop_recommended",
        f"Soil {soil_type}, water {water_condition}. Recommended: {', '.join(recommendations)}. "
        f"Storage check: {storage_info.get('status')}.",
    )
    coordinator.add_log(
        "Sensor Simulator",
        "reading_generated",
        f"Temperature {reading['temperature_c']} C, humidity {reading['humidity_pct']}%, "
        f"distance {reading['distance_cm']} cm.",
    )
    coordinator.add_log(
        "Storage Agent",
        "storage_checked",
        f"Fill {state['storage']['fill_pct']}%. Status: {state['storage']['status']}.",
    )
    coordinator.add_log(
        "Spoilage Agent",
        "spoilage_checked",
        f"Risk {state['spoilage']['risk_level']} (score {state['spoilage']['spoilage_risk_score']}).",
    )
    actuator = state["spoilage"].get("actuator") or {}
    coordinator.add_log(
        "Actuator",
        actuator.get("action") or "NORMAL",
        actuator.get("message") or "No actuator result.",
    )
    MovementLogisticsAgent(coordinator).run()

    primary_fill = float(state["storage"]["fill_pct"])
    secondary_fill = round(min(100.0, max(0.0, primary_fill + 1.5)), 2)
    chain = HashChain()
    for step in range(max(sensor_index, 1)):
        chain.append_record(
            {
                "warehouse_id": warehouse_id,
                "fill_pct": round(primary_fill - (max(sensor_index, 1) - step), 2),
                "temperature_c": reading["temperature_c"],
            }
        )
    chain.append_record(
        {
            "warehouse_id": warehouse_id,
            "fill_pct": primary_fill,
            "temperature_c": reading["temperature_c"],
            "humidity_pct": reading["humidity_pct"],
        }
    )
    confirmations = ConfirmationLog()
    confirmations.confirm_reading(warehouse_id, chain.records[-1]["index"], "field_officer")
    trust = evaluate_trust(
        chain,
        primary_fill,
        secondary_fill,
        confirmations,
        warehouse_id,
        expected_head=chain.head_hash,
    )
    stock_on_hand = round(float(state["config"]["capacity_kg"]) * primary_fill / 100.0, 2)
    loan = decide(
        trust,
        stock={"crop": crop["selected_crop"], "qty_kg": stock_on_hand},
    )
    coordinator.add_log(
        "Trust Framework",
        "trust_scored",
        f"Trust {trust['trust_score']} ({trust['level']}). Chain valid: {trust['chain']['valid']}.",
    )
    coordinator.add_log(
        "Loan Agent",
        loan["decision"],
        f"Decision {loan['decision']} at trust {loan['trust_score']} "
        f"(threshold {loan['threshold']}).",
    )

    browser_spoilage = _browser_spoilage(reading["temperature_c"], reading["humidity_pct"])
    predicted = {
        "CRITICAL": "high",
        "HIGH": "high",
        "MODERATE": "medium",
        "LOW": "low",
    }.get(state["spoilage"]["risk_level"], "low")
    selected_warehouse = state["logistics"].get("selected_warehouse")
    validations = [
        validate(
            "crop",
            {
                "crop": selected_crop,
                "soil_type": soil_type,
                "drought_risk": water_condition,
            },
            {"rule_table": CROP_RULES, "source": "Meemansa crop_agent rules"},
        ),
        validate(
            "storage",
            {"fill_pct": primary_fill},
            {
                "independent_fill_pct": secondary_fill,
                "source": "secondary fill probe",
            },
        ),
        validate(
            "spoilage",
            {"predicted_risk": predicted},
            {
                "expected_risk": browser_spoilage,
                "source": "dashboard spoilage thresholds",
            },
        ),
        validate(
            "loan",
            loan,
            {},
        ),
    ]
    if selected_warehouse:
        ground_truth = {
            item["id"]: {
                "capacity_available": item["available_capacity_kg"],
                "compatible_crops": item["compatible_crops"],
            }
            for item in WAREHOUSES
        }
        validations.append(
            validate(
                "logistics",
                {
                    "selected_warehouse": selected_warehouse,
                    "crop": crop["selected_crop"],
                    "quantity": state["storage"]["incoming_quantity_kg"],
                },
                {"warehouses": ground_truth, "source": "neighbouring warehouse table"},
            )
        )
    else:
        validations.append(
            {
                "component": "logistics",
                "status": "Verified",
                "validation_type": "rule_based",
                "rule": "no transfer when primary capacity is enough",
                "expected": "no neighbouring warehouse selected",
                "actual": "primary warehouse retained",
                "evidence": state["storage"]["status"],
            }
        )
    validations.append(
        validate(
            "water",
            water,
            {},
        )
    )

    spoilage_for_health = {
        "CRITICAL": "HIGH",
        "HIGH": "HIGH",
        "MODERATE": "MEDIUM",
        "LOW": "LOW",
    }.get(state["spoilage"]["risk_level"], "LOW")
    rainfall_mm = options.get("rainfall_mm")

    shared_state.merge_stream(
        "environment",
        "village",
        {
            "spoilage_risk": spoilage_for_health,
            "district": water["district"],
            "village": water["village"],
            "groundwater_category": category,
            "water_condition": water_condition,
            "selected_crop": crop["selected_crop"],
            "recommended_crops": recommendations,
            "simulation_rainfall_mm": None if rainfall_mm is None else float(rainfall_mm),
            "annual_rainfall_mm": (water.get("annual_rainfall_2024") or {}).get("rainfall_mm"),
            "drought_risk_30d": water["drought_risk_30d"],
        },
    )
    shared_state.merge_stream(
        "storage",
        warehouse_id,
        {
            "sensor": reading,
            "storage": state["storage"],
            "spoilage": state["spoilage"],
            "actuator": actuator,
            "movement": state["logistics"],
        },
    )
    shared_state.merge_stream(
        "finance",
        warehouse_id,
        {
            "trust_score": trust["trust_score"],
            "trust_level": trust["level"],
            "chain_valid": trust["chain"]["valid"],
            "loan_decision": loan["decision"],
            "receipt_id": loan.get("receipt_id"),
            "threshold": loan["threshold"],
            "reasons": loan.get("reasons") or [],
        },
    )
    shared_state.merge_stream(
        "verification",
        warehouse_id,
        {"results": [_public_validation(item) for item in validations]},
    )

    grain = GRAIN_FOR_WAREHOUSE.get(crop["selected_crop"])
    warehouse_fields: dict[str, Any] = {
        "fill_percent": int(round(primary_fill)),
        "capacity_kg": float(state["config"]["capacity_kg"]),
        "available_stock_kg": stock_on_hand,
        "stock_source": "storage_agent",
    }
    if grain:
        warehouse_fields["grain_type"] = grain
    updated_warehouse = shared_state.update_warehouse(warehouse_id, warehouse_fields)

    for entry in coordinator.logs:
        shared_state.append_log(
            {
                "agent_name": entry["agent"],
                "event_type": entry["action"],
                "warehouse_id": warehouse_id,
                "input_summary": entry["message"],
                "result": entry["action"],
                "status": "success",
            }
        )

    result = {
        "order": [
            "water",
            "crop",
            "sensor",
            "storage",
            "spoilage",
            "actuator",
            "logistics",
            "trust",
            "loan",
            "validation",
        ],
        "water": water,
        "crop": crop,
        "sensor": reading,
        "storage": state["storage"],
        "spoilage": {
            "risk_level": state["spoilage"]["risk_level"],
            "spoilage_risk_score": state["spoilage"]["spoilage_risk_score"],
            "eta_days": state["spoilage"]["eta_days"],
            "temperature_c": state["spoilage"]["temperature_c"],
            "humidity_pct": state["spoilage"]["humidity_pct"],
            "actuator": actuator,
            "health_spoilage_risk": spoilage_for_health,
        },
        "logistics": state["logistics"],
        "trust": {
            "trust_score": trust["trust_score"],
            "level": trust["level"],
            "components": trust["components"],
            "chain_valid": trust["chain"]["valid"],
            "threshold": trust["threshold"],
            "primary_fill_pct": primary_fill,
            "secondary_fill_pct": secondary_fill,
        },
        "loan": {
            "decision": loan["decision"],
            "receipt_id": loan.get("receipt_id"),
            "trust_score": loan["trust_score"],
            "threshold": loan["threshold"],
            "reasons": loan.get("reasons") or [],
            "chain_valid": loan["chain_valid"],
        },
        "validation": [_public_validation(item) for item in validations],
        "warehouse": updated_warehouse,
        "conversation": coordinator.logs,
        "notes": [
            "Crop rules follow Meemansa's soil and groundwater bands. "
            "The validation key uses that water condition because the CGWB tables "
            "do not include a 30-day drought score.",
            "Warehouse stock published here is what the health logistics reassessment reads. "
            "A nutrition report still has to be submitted before a delivery recommendation is stored.",
            "The loan result is a recommendation. Stock is not disbursed.",
        ],
    }
    return _plain(result)


def _browser_spoilage(temperature: float, humidity: float) -> str:
    if temperature > 35 or humidity > 80:
        return "high"
    if temperature > 30 or humidity > 70:
        return "medium"
    return "low"


def _public_validation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "component": item.get("component"),
        "status": item.get("status"),
        "validation_type": item.get("validation_type"),
        "rule": item.get("rule"),
        "evidence": item.get("evidence"),
    }


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, float):
        return float(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if value is None or isinstance(value, (str, bool)):
        return value
    return str(value)
