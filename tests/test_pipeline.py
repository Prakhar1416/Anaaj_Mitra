def test_pipeline_follows_dependency_order_and_publishes_stock(client):
    response = client.post(
        "/api/pipeline/run",
        json={
            "soil_type": "loamy",
            "scenario": "spoilage",
            "sensor_index": 10,
            "temperature_c": 33,
            "humidity_pct": 79,
            "rainfall_mm": 42,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["order"][0] == "water"
    assert body["order"].index("crop") < body["order"].index("storage")
    assert body["order"].index("storage") < body["order"].index("logistics")
    assert body["order"].index("trust") < body["order"].index("loan")
    assert body["water"]["data_source"] == "REAL_CGWB"
    assert body["crop"]["water_condition"] in {"high", "medium", "low"}
    assert body["storage"]["status"]
    assert body["spoilage"]["risk_level"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert body["loan"]["decision"] in {"receipt", "manual_review"}
    assert body["warehouse"]["stock_source"] == "storage_agent"
    assert body["warehouse"]["available_stock_kg"] > 0
    agents = [entry["agent"] for entry in body["conversation"]]
    assert agents.index("Water Agent") < agents.index("Crop Agent")
    assert agents.index("Storage Agent") < agents.index("Logistics Agent")
    assert agents.index("Trust Framework") < agents.index("Loan Agent")

    latest = client.get("/api/pipeline/latest")
    assert latest.status_code == 200
    state = client.get("/api/state").json()
    assert state["environment"]["village"]["payload"]["spoilage_risk"] == body["spoilage"]["health_spoilage_risk"]
    assert state["warehouses"]["warehouse-001"]["stock_source"] == "storage_agent"
