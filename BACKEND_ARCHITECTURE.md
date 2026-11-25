# Backend architecture

One Uvicorn process serves the API and the existing dashboard. `run_all.py` is the startup command. It loads settings, initialises SQLite, then runs `backend.api:app`. The FastAPI lifespan builds the only in-memory agent graph, all of it pointed at that same database file.

```
Community health worker
        │  POST /api/health/reports
        ▼
Health Agent
        │  validate, persist current flag, append event
        ▼
SQLite shared state
        │  HEALTH_PRIORITY_UPDATED
        ▼
Coordinator adapter
        │  request reassessment
        ▼
Logistics adapter
        │  read warehouse stock and optional spoilage risk
        ▼
logistics_decisions + agent_logs
        │
        ▼
GET /api/state  →  dashboard nutrition panel
```

There is no second shared-state object and reload is off, so the server does not fork a second copy of the agents.

## Components

| Module | Responsibility |
|---|---|
| `backend/config.py` | Identifiers, thresholds, delivery minimum, database path |
| `backend/database.py` | Schema, connection, demo seed |
| `backend/shared_state.py` | Field-level reads and writes |
| `backend/health_agent.py` | Report validation and priority updates |
| `backend/coordinator.py` | Receives health events and stores logistics results |
| `backend/logistics_agent.py` | Stock and feasibility recommendation |
| `backend/api.py` | HTTP routes, including the original `/health` and `/api/config` |
| `run_all.py` | One startup command |

## Adapters, not replacements

The coordination stream and the logistics stream do not have Python modules in this repository. Their behaviour today lives in `script.js`.

- `Coordinator.publish()` is the integration point. It handles `HEALTH_PRIORITY_UPDATED`. Any other event type is logged and ignored.
- `LogisticsAgent.movement_recommendation()` returns the original sentences: `Early movement recommended` when spoilage is `HIGH`, otherwise `No urgent warehouse transfer required`.
- `LogisticsAgent.reassess_health_priority()` adds the health-priority check. It reads warehouse rows and, when present, `environment/village` field `spoilage_risk`.

When those teammates add their own modules, they can replace the bodies of `publish` and `reassess_health_priority` without changing the health agent or the HTTP paths.

## What a priority report does

1. The health agent rejects a malformed body, a non-boolean flag, or an unknown hamlet id.
2. A new or changed report updates only the hamlet health columns, inserts a report row, and inserts a `HEALTH_PRIORITY_UPDATED` event.
3. The coordinator logs receipt and calls the logistics adapter.
4. The adapter checks every warehouse for a compatible grain and at least `min_delivery_kg` (default 25).
5. It stores one of `REPRIORITISE`, `STOCK_UNAVAILABLE`, or `PRIORITY_CLEARED`.
6. `delivery_completed` is false. Stock is not reduced.

`REPRIORITISE` means the hamlet should be considered first when a later dispatcher has stock and capacity. It does not mean grain has moved.

## Other streams

Environment, storage metadata, finance, and verification can merge JSON into `stream_state` through `PUT /api/streams/{stream}/{entity_id}`. A partial object updates only the keys it sends.

Warehouse quantity is not stored in that blob. The storage stream should patch `/api/storage/warehouses/{warehouse_id}`. Logistics reads that table, so a health reassessment sees the stock the storage stream last wrote.

The browser simulation still computes drought, crop, and spoilage locally. It does not overwrite backend health or logistics rows.
