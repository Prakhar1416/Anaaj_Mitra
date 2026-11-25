# Implementation audit

Audit date: 25 November 2026. This document records the repository as it existed before the health-agent integration, then the work added on top of it.

The smoke check before any feature code was written:

- `GET /health` returned HTTP 200 and `{"status":"ok"}`.
- Configured identifiers were `hamlet-001` and `warehouse-001`.
- `data/anaaj_mitra.db` was created as a 0-byte file. SQLite had no tables.
- There was no test suite and no Python agent, coordinator, or shared-state module.

## Existing project architecture

Anaaj Mitra is a static single-page dashboard plus a separate Python API.

| Layer | Technology | Role |
|---|---|---|
| Browser UI | HTML, CSS, vanilla JavaScript | Environmental simulation and agent conversation |
| API | FastAPI on Uvicorn, port 8001 | Health check and public configuration |
| Database | SQLite via the standard library | File created on startup, previously with no schema |
| Configuration | Environment variables read in `backend/config.py` | Hamlet IDs, warehouse IDs, drought and spoilage thresholds |

The browser simulation and the API did not talk to each other. Drought and spoilage thresholds in `backend/config.py` match the rules in `script.js`.

```
Rainfall < 30 mm        drought HIGH
Rainfall < 60 mm        drought MEDIUM
otherwise               drought LOW

Temperature > 35°C or humidity > 80%   spoilage HIGH
Temperature > 30°C or humidity > 70%   spoilage MEDIUM
otherwise                              spoilage LOW

Spoilage HIGH           "Early movement recommended"
otherwise               "No urgent warehouse transfer required"
```

Warehouse fill defaults to 72 percent in both the page and the config.

## Existing backend functionality

`run_all.py` started Uvicorn against `backend.api:app` on `127.0.0.1:8001` with reload disabled.

`backend/api.py` created the FastAPI app, called `initialize_database()` during lifespan, and exposed:

- `GET /health`
- `GET /api/config`

There was no shared state, no agent registry, and no coordinator.

## Existing database and data models

`backend/database.py` created the parent directory and opened a SQLite connection. It did not create tables, seed rows, or expose queries. There were no models.

Identifiers already in use:

- Warehouses: `warehouse-001` (override with `ANAAJ_MITRA_WAREHOUSE_IDS`)
- Hamlets: `hamlet-001` (override with `ANAAJ_MITRA_HAMLET_IDS`)
- Database path: `data/anaaj_mitra.db` (override with `ANAAJ_MITRA_DB_PATH`)

Sample identifiers such as `HAM001` do not match this project.

## Existing APIs

Only `GET /health` and `GET /api/config`. FastAPI serves generated docs at `/docs`.

`GET /api/config` returned warehouse IDs, hamlet IDs, the default fill percent, drought and spoilage thresholds, and the slider ranges used by the page.

## Existing agent implementations

| Agent | Where it lived | Backend status |
|---|---|---|
| Water / drought | `script.js` | Not in Python |
| Crop | `script.js` | Not in Python |
| Spoilage | `script.js` | Not in Python |
| Storage | `script.js`, static 72% fill | Not in Python |
| Logistics | `script.js` spoilage movement sentence | Not in Python |
| Health | Badge only, status READY | No logic |
| Coordinator | Not present | No event bus |

## Missing functionality

- Shared state and field ownership
- Health-report validation and nutrition-priority updates
- Health-priority events and agent logs
- Persistence of reports, events, and logistics decisions
- A coordinator path from health events to logistics reassessment
- Stock and feasibility checks (the page cannot know warehouse stock)
- API endpoints for health, state, logs, and logistics decisions
- Automated tests
- A startup path that initialises the database schema and agents

## Bugs and integration problems

- The database file could be created without a schema, so a restart kept an empty file.
- The dashboard hardcoded fill, temperature, humidity, and trust values. Running the simulation rewrote only the conversation log.
- The Health Agent badge never left READY.
- Nothing stopped a future Python agent from inventing a second ID scheme (`HAM001` versus `hamlet-001`).
- Logistics in the browser recommends movement from spoilage alone. It has no stock check, so it must not be treated as a completed delivery.

## Files modified by the integration

- `backend/config.py` — settings object, second demo hamlet, delivery minimum, public logistics fields. Existing threshold names kept.
- `backend/database.py` — schema, seed, and connections. Startup still goes through this module.
- `backend/api.py` — existing `/health` and `/api/config` kept. New routes added.
- `run_all.py` — loads settings, initialises the database, then starts the same Uvicorn app.
- `requirements.txt` — pytest and httpx for the test client.
- `README.md` — setup, startup, and test commands.
- `.gitignore` — pytest cache.
- `index.html`, `style.css`, `script.js` — additive nutrition-priority panel. The environmental simulation is unchanged.
- `project-report.md` — short pointer to the new backend docs. The original simulation write-up remains.

## Files created

- `backend/common.py`
- `backend/errors.py`
- `backend/schemas.py`
- `backend/shared_state.py`
- `backend/health_agent.py`
- `backend/logistics_agent.py` — adapter, because no Python logistics agent existed
- `backend/coordinator.py` — adapter, because no coordinator existed
- `tests/conftest.py`
- `tests/test_health_workflow.py`
- `BACKEND_ARCHITECTURE.md`
- `SHARED_STATE_SCHEMA.md`
- `API_DOCUMENTATION.md`
- `TESTING.md`

## Assumptions

- Hamlet and warehouse IDs remain the configured strings. Defaults are now `hamlet-001`, `hamlet-002`, and `warehouse-001`. `hamlet-001` is unchanged.
- Warehouse stock is simulated and labelled `simulated` until the storage stream writes it.
- The Python logistics module is an adapter. It keeps the browser spoilage sentences and adds a stock and feasibility recommendation. It does not dispatch grain.
- The coordinator is the single publisher used by the health agent. Other streams can call the same object later.
- Identical resubmission of the current priority, reason, and reporter does not create another event or another logistics decision. A changed value does. See `SHARED_STATE_SCHEMA.md`.
