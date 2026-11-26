"""Simple rule-based crop advisory prototype (demo rules, not CGWB recommendations)."""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent
SUITABILITY_FILE = ROOT / "data/crop_suitability.csv"
STORAGE_FILE = ROOT / "data/crop_storage.csv"


def recommend_crops(soil_type: str, water_condition: str):
    soil = soil_type.strip().lower()
    water = water_condition.strip().lower()
    rules = {
        ("sandy", "high"): ["Pearl Millet"],
        ("loamy", "medium"): ["Wheat", "Maize"],
        ("clayey", "low"): ["Rice"],
        ("alluvial", "medium"): ["Wheat", "Maize"],
    }
    return rules.get((soil, water), ["No rule-based recommendation available; verify locally"])


def check_storage(crop: str, available_storage: str):
    """Demo compatibility check; revise only using configured prototype rules."""
    compatibility = {
        "Pigeon Pea": "Dry Grain Storage",
        "Sesame": "Dry Grain Storage",
        "Wheat": "Dry Grain Storage",
        "Maize": "Dry Grain Storage",
        "Pearl Millet": "Dry Grain Storage",
        "Rice": "Moisture-Controlled Storage",
    }
    required = compatibility.get(crop)
    if required is None:
        return {"status": "Needs review", "crop": crop, "required_storage": "Not configured"}
    if required.lower() == available_storage.strip().lower():
        return {"status": "Compatible", "crop": crop, "required_storage": required}
    alternatives = [c for c, s in compatibility.items() if s.lower() == available_storage.strip().lower() and c != crop]
    return {"status": "Revised" if alternatives else "No alternative configured", "original_crop": crop,
            "crops": alternatives[:1], "required_storage": required,
            "message": "Storage mismatch detected; prototype alternative selected." if alternatives else "Storage mismatch; no configured alternative."}


if __name__ == "__main__":
    print("Sandy + high water stress:", recommend_crops("Sandy", "High"))
    print("Loamy + medium water stress:", recommend_crops("Loamy", "Medium"))
    print("Storage demo:", check_storage("Pigeon Pea", "Moisture-Controlled Storage"))
