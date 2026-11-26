
import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"


def create_initial_state():

    return {
        "sensor": {},

        "crop": {
            "current_crop": "Wheat",
            "storage_type_required": "dry_grain"
        },

        "config": {
            "warehouse_id": "WH-001",
            "capacity_kg": 5000,
            "incoming_quantity_kg": 1500,
            "warehouse_storage_type": "dry_grain",
            "empty_distance_cm": 100,
            "full_distance_cm": 10
        },

        "storage": {},

        "spoilage": {
            "history": []
        },

        "logistics": {},
        "finance": {},
        "health": {},

        "log": []
    }


def save_state(state):

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=4)


def add_log(state, message):

    state["log"].append({
        "agent": "Stream 2",
        "message": message
    })
