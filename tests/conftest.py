from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.config import DroughtThresholds, Settings, SpoilageThresholds


def make_settings(database_path: Path, stock_kg: float = 250) -> Settings:
    return Settings(
        warehouse_ids=("warehouse-001",),
        hamlet_ids=("hamlet-001", "hamlet-002"),
        database_path=database_path,
        default_warehouse_fill_percent=72,
        warehouse_capacity_kg=1000,
        grain_type="millet",
        stock_source="simulated",
        simulated_stock_kg=stock_kg,
        min_delivery_kg=25,
        drought=DroughtThresholds(),
        spoilage=SpoilageThresholds(),
        host="127.0.0.1",
        port=8001,
    )


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(make_settings(tmp_path / "anaaj.db"))
    with TestClient(app) as test_client:
        yield test_client
