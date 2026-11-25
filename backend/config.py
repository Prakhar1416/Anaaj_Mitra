import os
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPATIBLE_GRAIN_TYPES = ("millet", "sorghum", "wheat", "rice", "mixed")


def _configured_ids(environment_variable: str, default: str) -> tuple[str, ...]:
    values = tuple(
        value.strip()
        for value in os.getenv(environment_variable, default).split(",")
        if value.strip()
    )
    if not values:
        raise ValueError(f"{environment_variable} must contain at least one ID")
    return values


def _configured_float(environment_variable: str, default: str) -> float:
    raw = os.getenv(environment_variable, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{environment_variable} must be a number") from exc
    if value < 0:
        raise ValueError(f"{environment_variable} must be >= 0")
    return value


def _configured_int(environment_variable: str, default: str) -> int:
    raw = os.getenv(environment_variable, default)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{environment_variable} must be an integer") from exc
    return value


WAREHOUSE_IDS = _configured_ids("ANAAJ_MITRA_WAREHOUSE_IDS", "warehouse-001")
HAMLET_IDS = _configured_ids("ANAAJ_MITRA_HAMLET_IDS", "hamlet-001,hamlet-002")
DATABASE_PATH = Path(
    os.getenv("ANAAJ_MITRA_DB_PATH", str(PROJECT_ROOT / "data" / "anaaj_mitra.db"))
)
DEFAULT_WAREHOUSE_FILL_PERCENT = 72
DEFAULT_WAREHOUSE_CAPACITY_KG = 1000.0
DEFAULT_GRAIN_TYPE = "millet"
SIMULATED_STOCK_SOURCE = "simulated"


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


@dataclass(frozen=True)
class Settings:
    warehouse_ids: tuple[str, ...]
    hamlet_ids: tuple[str, ...]
    database_path: Path
    default_warehouse_fill_percent: int
    warehouse_capacity_kg: float
    grain_type: str
    stock_source: str
    simulated_stock_kg: float
    min_delivery_kg: float
    drought: DroughtThresholds
    spoilage: SpoilageThresholds
    host: str
    port: int

    def public_dict(self) -> dict[str, object]:
        return {
            "warehouse_ids": list(self.warehouse_ids),
            "hamlet_ids": list(self.hamlet_ids),
            "default_warehouse_fill_percent": self.default_warehouse_fill_percent,
            "thresholds": {
                "drought": asdict(self.drought),
                "spoilage": asdict(self.spoilage),
            },
            "input_ranges": {
                "rainfall_mm": [0, 150],
                "temperature_c": [10, 50],
                "humidity_percent": [20, 100],
            },
            "logistics": {
                "min_delivery_kg": self.min_delivery_kg,
                "compatible_grain_types": list(COMPATIBLE_GRAIN_TYPES),
                "stock_source": self.stock_source,
            },
        }


def load_settings() -> Settings:
    min_delivery_kg = _configured_float("ANAAJ_MITRA_MIN_DELIVERY_KG", "25")
    if min_delivery_kg <= 0:
        raise ValueError("ANAAJ_MITRA_MIN_DELIVERY_KG must be greater than 0")
    port = _configured_int("ANAAJ_MITRA_PORT", "8001")
    if not 1 <= port <= 65535:
        raise ValueError("ANAAJ_MITRA_PORT must be between 1 and 65535")
    grain_type = os.getenv("ANAAJ_MITRA_GRAIN_TYPE", DEFAULT_GRAIN_TYPE).strip()
    return Settings(
        warehouse_ids=_configured_ids("ANAAJ_MITRA_WAREHOUSE_IDS", "warehouse-001"),
        hamlet_ids=_configured_ids(
            "ANAAJ_MITRA_HAMLET_IDS", "hamlet-001,hamlet-002"
        ),
        database_path=Path(
            os.getenv(
                "ANAAJ_MITRA_DB_PATH",
                str(PROJECT_ROOT / "data" / "anaaj_mitra.db"),
            )
        ),
        default_warehouse_fill_percent=DEFAULT_WAREHOUSE_FILL_PERCENT,
        warehouse_capacity_kg=DEFAULT_WAREHOUSE_CAPACITY_KG,
        grain_type=grain_type or DEFAULT_GRAIN_TYPE,
        stock_source=SIMULATED_STOCK_SOURCE,
        simulated_stock_kg=_configured_float("ANAAJ_MITRA_SIMULATED_STOCK_KG", "250"),
        min_delivery_kg=min_delivery_kg,
        drought=DROUGHT_THRESHOLDS,
        spoilage=SPOILAGE_THRESHOLDS,
        host=os.getenv("ANAAJ_MITRA_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=port,
    )


def public_config() -> dict[str, object]:
    return load_settings().public_dict()
