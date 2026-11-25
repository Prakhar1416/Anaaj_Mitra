from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.logistics_agent import (
    EARLY_MOVEMENT,
    NO_URGENT_MOVEMENT,
    LogisticsAgent,
)
from tests.conftest import make_settings

REPORT = {
    "hamlet_id": "hamlet-001",
    "nutrition_priority": True,
    "reason": "High nutritional vulnerability",
    "reported_by": "CHW001",
}


def test_existing_health_and_config_endpoints(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    config = client.get("/api/config").json()
    assert config["hamlet_ids"] == ["hamlet-001", "hamlet-002"]
    assert config["warehouse_ids"] == ["warehouse-001"]
    assert config["default_warehouse_fill_percent"] == 72
    assert config["thresholds"]["drought"]["high_below_mm"] == 30
    assert config["thresholds"]["spoilage"]["high_temperature_c"] == 35


def test_valid_health_priority_report(client: TestClient) -> None:
    response = client.post("/api/health/reports", json=REPORT)
    assert response.status_code == 201
    body = response.json()
    assert body["accepted"] is True
    assert body["duplicate"] is False
    assert body["event_id"].startswith("EVT-")
    assert body["logistics_decision"]["decision"] == "REPRIORITISE"

    status = client.get("/api/health/hamlets/hamlet-001").json()
    assert status["nutrition_priority"] is True
    assert status["reason"] == REPORT["reason"]
    assert status["reported_by"] == "CHW001"
    assert status["last_event_id"] == body["event_id"]

    events = client.get("/api/health/events").json()["events"]
    reports = client.get("/api/health/reports").json()["reports"]
    assert len(events) == 1
    assert events[0]["event_type"] == "HEALTH_PRIORITY_UPDATED"
    assert len(reports) == 1


def test_invalid_hamlet_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/health/reports",
        json={**REPORT, "hamlet_id": "HAM001"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "unknown_hamlet"

    status = client.get("/api/health/hamlets/hamlet-001").json()
    assert status["nutrition_priority"] is False
    assert status["last_event_id"] is None
    logs = client.get("/api/logs", params={"status": "failure"}).json()["logs"]
    assert logs
    assert logs[0]["agent_name"] == "health_agent"
    assert logs[0]["status"] == "failure"
    assert logs[0]["hamlet_id"] == "HAM001"


def test_priority_override_reaches_logistics(client: TestClient) -> None:
    response = client.post("/api/health/reports", json=REPORT)
    body = response.json()
    decision = body["logistics_decision"]
    assert decision["decision"] == "REPRIORITISE"
    assert decision["feasible"] is True
    assert decision["stock_available"] is True
    assert decision["delivery_completed"] is False
    assert decision["warehouse_id"] == "warehouse-001"
    assert decision["event_id"] == body["event_id"]
    assert "No delivery was executed." in decision["recommendation"]

    logs = client.get(
        "/api/logs", params={"event_id": body["event_id"]}
    ).json()["logs"]
    agents = {entry["agent_name"] for entry in logs}
    assert {"health_agent", "coordinator", "logistics_agent"} <= agents
    assert any(
        entry["event_type"] == "HEALTH_PRIORITY_RECEIVED" for entry in logs
    )


def test_stock_unavailable_does_not_claim_delivery(client: TestClient) -> None:
    stock = client.patch(
        "/api/storage/warehouses/warehouse-001",
        json={"available_stock_kg": 0},
    )
    assert stock.status_code == 200
    assert stock.json()["available_stock_kg"] == 0
    assert stock.json()["stock_source"] == "simulated"

    response = client.post("/api/health/reports", json=REPORT)
    assert response.status_code == 201
    decision = response.json()["logistics_decision"]
    assert decision["decision"] == "STOCK_UNAVAILABLE"
    assert decision["stock_available"] is False
    assert decision["feasible"] is False
    assert decision["delivery_completed"] is False
    assert decision["warehouse_id"] is None
    assert "No delivery was executed." in decision["recommendation"]

    events = client.get("/api/health/events").json()["events"]
    assert len(events) == 1
    assert events[0]["nutrition_priority"] is True
    stored = client.get("/api/logistics/hamlets/hamlet-001").json()["decision"]
    assert stored["decision"] == "STOCK_UNAVAILABLE"


def test_duplicate_report_does_not_repeat_delivery_action(client: TestClient) -> None:
    first = client.post("/api/health/reports", json=REPORT)
    assert first.status_code == 201
    second = client.post("/api/health/reports", json=REPORT)
    assert second.status_code == 200
    body = second.json()
    assert body["accepted"] is False
    assert body["duplicate"] is True
    assert body["reassessment_triggered"] is False
    assert body["event_id"] == first.json()["event_id"]

    assert len(client.get("/api/health/events").json()["events"]) == 1
    assert len(client.get("/api/logistics/decisions").json()["decisions"]) == 1


def test_same_idempotency_key_is_not_applied_twice(client: TestClient) -> None:
    payload = {**REPORT, "idempotency_key": "report-001"}
    assert client.post("/api/health/reports", json=payload).status_code == 201
    replay = client.post("/api/health/reports", json=payload)
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    conflict = client.post(
        "/api/health/reports",
        json={**payload, "nutrition_priority": False},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert len(client.get("/api/logistics/decisions").json()["decisions"]) == 1


def test_priority_correction_keeps_history(client: TestClient) -> None:
    created = client.post("/api/health/reports", json=REPORT)
    assert created.status_code == 201
    original_event = created.json()["event_id"]

    corrected = client.put(
        "/api/health/hamlets/hamlet-001",
        json={
            "hamlet_id": "hamlet-001",
            "nutrition_priority": False,
            "reason": "Follow-up shows improvement",
            "reported_by": "CHW001",
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["accepted"] is True
    assert corrected.json()["nutrition_priority"] is False
    assert corrected.json()["logistics_decision"]["decision"] == "PRIORITY_CLEARED"

    status = client.get("/api/health/hamlets/hamlet-001").json()
    assert status["nutrition_priority"] is False
    assert status["reason"] == "Follow-up shows improvement"

    events = client.get("/api/health/events").json()["events"]
    assert len(events) == 2
    assert any(
        event["event_id"] == original_event and event["nutrition_priority"] is True
        for event in events
    )
    received = [
        entry
        for entry in client.get("/api/logs").json()["logs"]
        if entry["event_type"] == "HEALTH_PRIORITY_RECEIVED"
    ]
    assert len(received) == 2


def test_persistence_across_restart(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "persist.db")
    with TestClient(create_app(settings)) as first:
        response = first.post("/api/health/reports", json=REPORT)
        assert response.status_code == 201
        event_id = response.json()["event_id"]

    with TestClient(create_app(settings)) as second:
        status = second.get("/api/health/hamlets/hamlet-001")
        assert status.status_code == 200
        assert status.json()["nutrition_priority"] is True
        assert status.json()["last_event_id"] == event_id
        decision = second.get("/api/logistics/hamlets/hamlet-001").json()["decision"]
        assert decision["decision"] == "REPRIORITISE"
        assert decision["delivery_completed"] is False


def test_end_to_end_health_priority_workflow(client: TestClient) -> None:
    response = client.post("/api/health/reports", json=REPORT)
    assert response.status_code == 201
    event_id = response.json()["event_id"]

    state = client.get("/api/state").json()
    hamlet = state["hamlets"]["hamlet-001"]
    assert hamlet["health"]["nutrition_priority"] is True
    assert "hamlet-001" in state["health"]["priority_hamlet_ids"]
    assert hamlet["logistics"]["decision"] == "REPRIORITISE"
    assert hamlet["logistics"]["event_id"] == event_id
    assert state["warehouses"]["warehouse-001"]["available_stock_kg"] == 250
    assert state["warehouses"]["warehouse-001"]["stock_source"] == "simulated"

    chronological = list(
        reversed(client.get("/api/logs", params={"event_id": event_id}).json()["logs"])
    )
    assert [
        (entry["agent_name"], entry["event_type"]) for entry in chronological
    ] == [
        ("health_agent", "HEALTH_REPORT_ACCEPTED"),
        ("coordinator", "HEALTH_PRIORITY_RECEIVED"),
        ("logistics_agent", "LOGISTICS_REASSESSED"),
        ("coordinator", "LOGISTICS_DECISION_RECORDED"),
    ]
    assert all(entry["status"] == "success" for entry in chronological)


def test_spoilage_rule_is_preserved_and_does_not_complete_delivery(
    client: TestClient,
) -> None:
    published = client.put(
        "/api/streams/environment/village",
        json={"spoilage_risk": "HIGH"},
    )
    assert published.status_code == 200
    response = client.post("/api/health/reports", json=REPORT)
    recommendation = response.json()["logistics_decision"]["recommendation"]
    assert EARLY_MOVEMENT in recommendation
    assert response.json()["logistics_decision"]["delivery_completed"] is False

    agent = LogisticsAgent(shared_state=None, min_delivery_kg=25)  # type: ignore[arg-type]
    assert agent.movement_recommendation("HIGH") == EARLY_MOVEMENT
    assert agent.movement_recommendation("MEDIUM") == NO_URGENT_MOVEMENT


def test_non_boolean_priority_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/health/reports",
        json={**REPORT, "nutrition_priority": "true"},
    )
    assert response.status_code == 422
    status = client.get("/api/health/hamlets/hamlet-001").json()
    assert status["nutrition_priority"] is False
