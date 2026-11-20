import os
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _configured_ids(environment_variable: str, default: str) -> tuple[str, ...]:
    values = tuple(
        value.strip()
        for value in os.getenv(environment_variable, default).split(",")
        if value.strip()
    )
    if not values:
        raise ValueError(f"{environment_variable} must contain at least one ID")
    return values


WAREHOUSE_IDS = _configured_ids("ANAAJ_MITRA_WAREHOUSE_IDS", "warehouse-001")
HAMLET_IDS = _configured_ids("ANAAJ_MITRA_HAMLET_IDS", "hamlet-001")
DATABASE_PATH = Path(
    os.getenv("ANAAJ_MITRA_DB_PATH", str(PROJECT_ROOT / "data" / "anaaj_mitra.db"))
)
DEFAULT_WAREHOUSE_FILL_PERCENT = 72


@dataclass(frozen=True)
class DroughtThresholds:
    high_below_mm: int = 30
    medium_below_mm: int = 60


@dataclass(frozen=True)
class SpoilageThresholds:
    high_temperature_c: int = 35
    high_humidity_percent: int = 80
    medium_temperature_c: int = 30
    medium_humidity_percent: int = 70


DROUGHT_THRESHOLDS = DroughtThresholds()
SPOILAGE_THRESHOLDS = SpoilageThresholds()


def public_config() -> dict[str, object]:
    return {
        "warehouse_ids": list(WAREHOUSE_IDS),
        "hamlet_ids": list(HAMLET_IDS),
        "default_warehouse_fill_percent": DEFAULT_WAREHOUSE_FILL_PERCENT,
        "thresholds": {
            "drought": asdict(DROUGHT_THRESHOLDS),
            "spoilage": asdict(SPOILAGE_THRESHOLDS),
        },
        "input_ranges": {
            "rainfall_mm": [0, 150],
            "temperature_c": [10, 50],
            "humidity_percent": [20, 100],
        },
    }
