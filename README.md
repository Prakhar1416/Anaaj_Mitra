# Anaaj Mitra

Merged group build. One web app runs the members' modules in dependency order:

1. CGWB water assessment, then crop rules that use that water condition.
2. Warehouse sensor reading, then storage capacity and spoilage.
3. Logistics, which looks for another warehouse when storage cannot take the crop.
4. Trust score from the storage fill, then the loan decision.
5. Validation of those outputs. The health report on the page reassesses nutrition priority against the stock this pipeline publishes.

`streams/environment` is the CGWB water and crop work. `streams/iot` is sensor, storage, spoilage, and the actuator. `streams/logistics` is the warehouse-transfer agent. `streams/finance` is trust, loans, and validation. The dashboard and health workflow stay in `backend/`.

Smart-village resource coordination prototype. The Python backend stores hamlet health priority, asks a logistics adapter to reassess stock, and exposes that state to the page. Use **Run coordination** on the dashboard to execute the merged pipeline. The sliders are sent with that run. If the API is unreachable, the page falls back to the original in-browser simulation.

Warehouse stock shipped with this backend is simulated and labelled `simulated`. A logistics result is a recommendation. It is not a completed delivery.

## Run locally

Python 3.10 or later.

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_all.py
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_all.py
```

`run_all.py` loads configuration, creates the SQLite schema and demo seed, then starts the API. Open <http://127.0.0.1:8001> for the dashboard and <http://127.0.0.1:8001/docs> for the API. `GET /health` returns `{"status":"ok"}`.

The database file is `data/anaaj_mitra.db`. Restarting `run_all.py` keeps saved health reports, events, and logistics decisions. Delete that file to return to the demo seed.

The static page can still be opened on its own:

```bash
python -m http.server 8000
```

From port 8000 the health panel calls `http://127.0.0.1:8001`. The simulation sliders do not need the API.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANAAJ_MITRA_HAMLET_IDS` | `hamlet-001,hamlet-002` | Hamlet registry |
| `ANAAJ_MITRA_WAREHOUSE_IDS` | `warehouse-001` | Warehouse registry |
| `ANAAJ_MITRA_DB_PATH` | `data/anaaj_mitra.db` | SQLite file |
| `ANAAJ_MITRA_SIMULATED_STOCK_KG` | `250` | Seed stock for a new warehouse row |
| `ANAAJ_MITRA_MIN_DELIVERY_KG` | `25` | Minimum stock for a feasible recommendation |
| `ANAAJ_MITRA_GRAIN_TYPE` | `millet` | Seed grain type |
| `ANAAJ_MITRA_HOST` | `127.0.0.1` | Bind host |
| `ANAAJ_MITRA_PORT` | `8001` | Bind port |

`hamlet-001` and `warehouse-001` are the original identifiers. `hamlet-002` was added so a priority list can show one hamlet without marking every hamlet. Sample ids such as `HAM001` are rejected.

Drought and spoilage thresholds in `backend/config.py` are unchanged and match `script.js`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

See `TESTING.md` for the cases and the last run.

## Further reading

- `IMPLEMENTATION_AUDIT.md` — what was already in the repo
- `BACKEND_ARCHITECTURE.md` — process and adapters
- `SHARED_STATE_SCHEMA.md` — fields, owners, idempotency
- `API_DOCUMENTATION.md` — routes and examples
