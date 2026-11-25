# API documentation

Base URL when started with `python run_all.py`: `http://127.0.0.1:8001`.

Interactive schemas are at `/docs`. Error bodies use:

```json
{"detail": {"message": "Unknown hamlet_id 'HAM001'.", "code": "unknown_hamlet"}}
```

Validation errors keep FastAPI's 422 `detail` list. Unknown hamlets return 404. An idempotency key reused with a different report returns 409.

Hamlet ids in examples are the project ids. `HAM001` is not registered.

## System

### `GET /health`

```json
{"status": "ok"}
```

### `GET /api/config`

Returns hamlet ids, warehouse ids, fill default, drought and spoilage thresholds, slider ranges, `min_delivery_kg`, compatible grains, and `stock_source`.

## Health

### `POST /api/health/reports`

HTTP 201 when the report changes state. HTTP 200 when it duplicates the current state.

```json
{
  "hamlet_id": "hamlet-001",
  "nutrition_priority": true,
  "reason": "High nutritional vulnerability",
  "reported_by": "CHW001"
}
```

`nutrition_priority` must be a JSON boolean. `reason` and `reported_by` are optional. `reported_at` is an optional ISO-8601 datetime. `idempotency_key` is optional.

```json
{
  "accepted": true,
  "duplicate": false,
  "status": "accepted",
  "reassessment_triggered": true,
  "hamlet_id": "hamlet-001",
  "nutrition_priority": true,
  "reason": "High nutritional vulnerability",
  "reported_by": "CHW001",
  "event_id": "EVT-0123456789AB",
  "event_type": "HEALTH_PRIORITY_UPDATED",
  "report_id": "RPT-0123456789AB",
  "message": "Nutrition-priority status updated. Logistics reassessment completed.",
  "logistics_decision": {
    "decision": "REPRIORITISE",
    "delivery_completed": false,
    "stock_available": true,
    "feasible": true,
    "warehouse_id": "warehouse-001",
    "recommendation": "Prioritise a nutrition delivery of millet from warehouse-001 to hamlet-001. Suitable stock is available (250.0 kg, source: simulated). This is a recommendation only. No delivery was executed."
  }
}
```

The decision object also includes `decision_id`, `event_id`, `hamlet_id`, `spoilage_risk`, `details`, and `created_at`.

A duplicate response sets `accepted` false, `duplicate` true, and `reassessment_triggered` false.

### `PUT /api/health/hamlets/{hamlet_id}`

Same body as the post. The body `hamlet_id` must match the path. Use this to correct a flag. History is kept.

### `GET /api/health/hamlets/{hamlet_id}`

Current health fields for one hamlet.

### `GET /api/health/priorities`

```json
{"hamlets": []}
```

Only hamlets whose current `nutrition_priority` is true.

### `GET /api/health/events?hamlet_id=&limit=50`

Append-only priority events, newest first. `limit` is 1–200.

### `GET /api/health/reports?hamlet_id=&limit=50`

Accepted reports, newest first.

## Shared state

### `GET /api/state`

Full snapshot described in `SHARED_STATE_SCHEMA.md`.

### `GET /api/hamlets/{hamlet_id}`

Hamlet name, current health, and the latest logistics decision or `null`.

### `GET /api/logs?agent=&hamlet_id=&event_id=&status=&limit=50`

`agent` is `health_agent`, `coordinator`, or `logistics_agent`. `status` is `success` or `failure`.

### `PUT /api/streams/{stream}/{entity_id}`

`stream` is `environment`, `storage`, `finance`, or `verification`. The body is a JSON object and is merged into the existing object for that entity.

```json
{"spoilage_risk": "HIGH"}
```

`PUT /api/streams/environment/village` with that body makes the logistics adapter append `Existing spoilage rule: Early movement recommended.`

### `GET /api/streams/{stream}/{entity_id}`

Returns the merged payload. 404 when nothing has been stored.

## Logistics

### `GET /api/logistics/decisions?hamlet_id=&limit=50`

Newest recommendations first.

### `GET /api/logistics/hamlets/{hamlet_id}`

```json
{"hamlet_id": "hamlet-001", "decision": null}
```

`decision` is the latest recommendation once a reassessment has run.

### `POST /api/logistics/reassess`

```json
{"hamlet_id": "hamlet-001"}
```

Runs the coordinator against the current health flag. Does not create a health event. Returns the new decision. Stock is still not consumed.

## Storage

### `PATCH /api/storage/warehouses/{warehouse_id}`

Updates only the fields that are sent.

```json
{"available_stock_kg": 0}
```

`fill_percent` is 0–100. Quantities must be zero or greater. Unknown warehouse ids return 404 `unknown_warehouse`.

This is the write path for the storage stream. Seeded stock stays `simulated` until `stock_source` is patched.

## Dashboard

The page at `/` loads `GET /api/config` and `GET /api/state`, and submits `POST /api/health/reports`. The environmental simulation does not call these routes. If the API is down and the page was opened from another port, the nutrition panel says the health backend is unreachable and the sliders still run.
