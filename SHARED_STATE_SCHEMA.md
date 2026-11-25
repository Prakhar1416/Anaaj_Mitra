# Shared state schema

State is stored in SQLite. `GET /api/state` builds the snapshot below. Writers update their own columns or their own stream object. They do not replace the whole snapshot.

Identifiers match `backend/config.py`: `hamlet-001`, `hamlet-002`, `warehouse-001`. Override them with `ANAAJ_MITRA_HAMLET_IDS` and `ANAAJ_MITRA_WAREHOUSE_IDS`. An id is 1–64 characters from letters, digits, `_`, and `-`.

```json
{
  "hamlets": {
    "hamlet-001": {
      "hamlet_id": "hamlet-001",
      "name": "Hamlet 001",
      "health": {},
      "logistics": {}
    }
  },
  "warehouses": {},
  "health": {"priority_hamlet_ids": []},
  "environment": {},
  "storage": {},
  "logistics": {"decisions": []},
  "finance": {},
  "verification": {},
  "agent_logs": []
}
```

`health.priority_hamlet_ids` and `logistics.decisions` are derived from the tables. The latest 50 decisions and logs are included in the snapshot. Use the list endpoints for a filtered history.

## Ownership

| Field | Type | Owner | Readers |
|---|---|---|---|
| `hamlets.*.health.nutrition_priority` | boolean | Health Agent | All |
| `hamlets.*.health.reason` | string or null | Health Agent | All |
| `hamlets.*.health.reported_by` | string or null | Health Agent | All |
| `hamlets.*.health.reported_at` | ISO-8601 string or null | Health Agent | All |
| `hamlets.*.health.updated_at` | ISO-8601 string or null | Health Agent | All |
| `hamlets.*.health.last_event_id` | string or null | Health Agent | Coordinator, dashboard |
| `hamlets.*.logistics` | decision object or null | Logistics adapter, via the coordinator | All |
| `warehouses.*.fill_percent` | integer 0–100 | Storage stream | Logistics, dashboard |
| `warehouses.*.capacity_kg` | number | Storage stream | Logistics, dashboard |
| `warehouses.*.available_stock_kg` | number | Storage stream | Logistics, dashboard |
| `warehouses.*.grain_type` | string | Storage stream | Logistics, dashboard |
| `warehouses.*.stock_source` | string | Storage stream | Logistics, dashboard |
| `environment.*` | JSON object | Environment stream | Logistics reads `village.spoilage_risk` |
| `storage.*` | JSON object | Storage stream | Dashboard |
| `finance.*` | JSON object | Finance stream | Dashboard |
| `verification.*` | JSON object | Verification stream | Dashboard |
| `agent_logs[]` | log records | Each agent appends | All |

Seed stock is `stock_source: "simulated"`. The health agent never writes warehouse columns. The storage patch never writes hamlet health columns.

Compatible grains for a nutrition recommendation are millet, sorghum, wheat, rice, and mixed.

## Tables

- `hamlets` — current nutrition-priority flag. One row per hamlet.
- `warehouses` — current stock. One row per warehouse.
- `health_reports` — every accepted report, including corrections.
- `health_priority_events` — append-only `HEALTH_PRIORITY_UPDATED` history.
- `logistics_decisions` — append-only recommendations.
- `agent_logs` — append-only trace.
- `stream_state` — partial JSON for environment, storage, finance, and verification.

A correction updates the hamlet row and inserts another event. Older events stay.

## Idempotency

A report matches the current status when `nutrition_priority`, `reason`, and `reported_by` are unchanged and the hamlet already has an event.

- Matching report: HTTP 200, `duplicate: true`, `accepted: false`, `reassessment_triggered: false`. No new report, event, or logistics decision. The attempt is still written to `agent_logs`.
- Changed priority, reason, or reporter: the new status is saved, a new event is stored, and logistics runs again. The new decision is another recommendation, not a second dispatch.
- `idempotency_key`: the same key and the same identity fields replay the first result. The same key with different identity fields returns HTTP 409 `idempotency_conflict`.
- To reassess without changing the health flag, call `POST /api/logistics/reassess`. That writes a new decision and does not write a new health event.

`reported_at` is not part of the identity. Sending the same flag with a new timestamp does not create another event.

## Event

```json
{
  "event_id": "EVT-0123456789AB",
  "event_type": "HEALTH_PRIORITY_UPDATED",
  "hamlet_id": "hamlet-001",
  "nutrition_priority": true,
  "source": "health_agent",
  "reason": "High nutritional vulnerability",
  "reported_by": "CHW001",
  "report_id": "RPT-0123456789AB",
  "timestamp": "2026-11-25T12:00:00Z"
}
```

## Logistics decision

`decision` is `REPRIORITISE`, `STOCK_UNAVAILABLE`, or `PRIORITY_CLEARED`.

`delivery_completed` is false for every decision this adapter writes. `details.warehouses_checked` lists the stock that was actually read. `details.note` states that stock was not decremented.

## Log record

`agent_name`, `event_type`, `event_id`, `hamlet_id`, `warehouse_id`, `input_summary`, `result`, `status` (`success` or `failure`), `error_detail`, `timestamp`.

A successful priority flow for one event id, oldest first:

1. `health_agent` / `HEALTH_REPORT_ACCEPTED`
2. `coordinator` / `HEALTH_PRIORITY_RECEIVED`
3. `logistics_agent` / `LOGISTICS_REASSESSED`
4. `coordinator` / `LOGISTICS_DECISION_RECORDED`

The API returns logs newest first.
