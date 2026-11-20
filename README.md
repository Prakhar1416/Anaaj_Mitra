# Anaaj Mitra

## Run locally

Install Python 3.10 or later, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_all.py
```

The backend listens at <http://127.0.0.1:8001>. Check `/health` to confirm
it is running, or open `/docs` for the FastAPI interface. It creates
`data/anaaj_mitra.db` on startup.

The only API routes are `GET /health` and `GET /api/config`. Warehouse IDs,
hamlet IDs, and thresholds are configured in `backend/config.py`; IDs can be
overridden with `ANAAJ_MITRA_WAREHOUSE_IDS` and `ANAAJ_MITRA_HAMLET_IDS`.
The default IDs are placeholders. No agent logic or frontend/API integration
has been added.

To run the existing static website separately, use
`python3 -m http.server 8000` and open <http://127.0.0.1:8000>.
