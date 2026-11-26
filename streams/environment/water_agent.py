"""CGWB-backed Water Agent for Madhya Pradesh.
Uses January 2025 village-level groundwater observations and 2024 district rainfall
summaries extracted from the uploaded CGWB Ground Water Year Book 2024-25.
No 30-day rainfall or flood score is calculated because those inputs are absent.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
GROUNDWATER_FILE = ROOT / "data/raw/real/cgwb_groundwater_jan2025.csv"
RAINFALL_FILE = ROOT / "data/raw/real/cgwb_district_rainfall_2024.csv"


def load_cgwb_data():
    """Load the two real CGWB-derived tables; fail clearly if files are missing."""
    if not GROUNDWATER_FILE.exists() or not RAINFALL_FILE.exists():
        raise FileNotFoundError("CGWB CSV files are missing from data/raw/real/")
    groundwater = pd.read_csv(GROUNDWATER_FILE)
    rainfall = pd.read_csv(RAINFALL_FILE)
    groundwater["district_key"] = groundwater["district"].astype(str).str.strip().str.upper()
    rainfall["district_key"] = rainfall["district"].astype(str).str.strip().str.upper()
    return groundwater, rainfall


def groundwater_category(depth_m_bgl: float) -> str:
    """Project interpretation of CGWB depth bands; not an official CGWB risk label."""
    depth = float(depth_m_bgl)
    if depth < 0:
        raise ValueError("Groundwater depth cannot be negative")
    if depth <= 5:
        return "Shallow"
    if depth <= 10:
        return "Moderate"
    return "Deep"


def assess_record(record_id: int):
    """Assess one actual well record by its record_id from the CGWB annexure."""
    groundwater, rainfall = load_cgwb_data()
    matches = groundwater[groundwater["record_id"] == int(record_id)]
    if matches.empty:
        raise ValueError(f"No CGWB groundwater record found for record_id={record_id}")
    row = matches.iloc[0]
    rain_rows = rainfall[rainfall["district_key"] == row["district_key"]]
    rain = rain_rows.iloc[0].to_dict() if not rain_rows.empty else None
    return {
        "record_id": int(row["record_id"]),
        "district": row["district"], "block": row["block"], "village": row["village"],
        "observation_date": row["observation_date"],
        "groundwater_depth_m_bgl": float(row["water_level_m_bgl"]),
        "groundwater_category": groundwater_category(row["water_level_m_bgl"]),
        "well_type": row["well_type"], "data_source": "REAL_CGWB",
        "annual_rainfall_2024": ({
            "rainfall_mm": float(rain["rainfall_2024_mm"]),
            "normal_rainfall_mm": float(rain["normal_rainfall_mm"]),
            "departure_percent": float(rain["departure_percent"]),
            "reported_status": rain["rainfall_status_reported"],
            "data_source": "REAL_CGWB_REPORT_TABLE_2_2",
        } if rain else None),
        "drought_risk_30d": "Insufficient data",
        "flood_risk": "Insufficient data",
        "limitation": "The report provides annual rainfall summaries, not daily/30-day rainfall or flood-event data."
    }


def district_summary(district: str):
    """Return actual well observations and rainfall summary for a district."""
    groundwater, rainfall = load_cgwb_data()
    key = str(district).strip().upper()
    wells = groundwater[groundwater["district_key"] == key]
    rain = rainfall[rainfall["district_key"] == key]
    if wells.empty and rain.empty:
        raise ValueError(f"No CGWB data found for district: {district}")
    result = {"district": district.title(), "well_records": int(len(wells)), "data_source": "REAL_CGWB"}
    if not wells.empty:
        result["mean_groundwater_depth_m_bgl"] = round(float(wells["water_level_m_bgl"].mean()), 2)
        result["groundwater_categories"] = wells["water_level_m_bgl"].map(groundwater_category).value_counts().to_dict()
    if not rain.empty:
        r=rain.iloc[0]
        result["annual_rainfall_2024_mm"] = float(r["rainfall_2024_mm"])
        result["rainfall_departure_percent"] = float(r["departure_percent"])
        result["rainfall_status_reported"] = r["rainfall_status_reported"]
    result["drought_risk_30d"] = "Insufficient data"
    result["flood_risk"] = "Insufficient data"
    return result


if __name__ == "__main__":
    groundwater, rainfall = load_cgwb_data()
    print(f"Loaded {len(groundwater)} real CGWB groundwater records")
    print(f"Loaded {len(rainfall)} district rainfall records")
    print("Sample well assessment:")
    print(assess_record(int(groundwater.iloc[0]["record_id"])))
    print("Sample district summary:")
    print(district_summary(str(groundwater.iloc[0]["district"])))
