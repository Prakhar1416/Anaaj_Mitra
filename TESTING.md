# Testing

From the project root, with the virtual environment activated:

```powershell
python -m pip install -r requirements.txt
python -m pytest
```

On this machine the command was:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Pytest uses a temporary SQLite file per test. Nothing is written to `data/anaaj_mitra.db` by the suite. The persistence test closes the app and opens a new app on the same temporary file, which is the restart behaviour of `run_all.py`.

Starlette currently warns that `httpx` with `starlette.testclient` is deprecated in favour of `httpx2`. The suite still passes on `httpx` 0.28.

## Last run

25 November 2026, Python 3.14, pytest 9.2.0.

```
12 passed, 1 warning in 0.64s
```

## Cases

| Test | Input | Expected | Result |
|---|---|---|---|
| `test_valid_health_priority_report` | `hamlet-001`, `nutrition_priority: true`, reason and `CHW001` | HTTP 201, flag stored, one event, one report | Pass |
| `test_invalid_hamlet_is_rejected` | `HAM001` | HTTP 404 `unknown_hamlet`, `hamlet-001` unchanged, failure log | Pass |
| `test_priority_override_reaches_logistics` | Priority true with 250 kg simulated millet | Coordinator and logistics logs, `REPRIORITISE`, `delivery_completed` false | Pass |
| `test_stock_unavailable_does_not_claim_delivery` | Stock patched to 0 kg, then a priority report | Event stored, `STOCK_UNAVAILABLE`, no warehouse chosen, delivery not completed | Pass |
| `test_duplicate_report_does_not_repeat_delivery_action` | Same report posted twice | Second response duplicate, one event, one decision | Pass |
| `test_same_idempotency_key_is_not_applied_twice` | Key `report-001`, then the same key with the opposite flag | Replay is duplicate; conflicting reuse is HTTP 409; still one decision | Pass |
| `test_priority_correction_keeps_history` | True, then false with a new reason | Current flag false, both events present, two coordinator receipts, `PRIORITY_CLEARED` | Pass |
| `test_persistence_across_restart` | Submit, close the app, open a new app on the same file | Priority and `REPRIORITISE` decision still there | Pass |
| `test_end_to_end_health_priority_workflow` | One priority report, then `GET /api/state` and logs | Health flag, decision, unchanged 250 kg stock, and the four-step log trace | Pass |
| `test_spoilage_rule_is_preserved_and_does_not_complete_delivery` | Environment spoilage `HIGH`, then a priority report | Recommendation includes `Early movement recommended` and does not complete a delivery | Pass |
| `test_existing_health_and_config_endpoints` | `GET /health`, `GET /api/config` | `status: ok`, original thresholds, `hamlet-001`, `warehouse-001` | Pass |
| `test_non_boolean_priority_is_rejected` | `"nutrition_priority": "true"` | HTTP 422, flag stays false | Pass |

`test_spoilage_rule_is_preserved_and_does_not_complete_delivery` also checks the adapter sentences used by the browser: high spoilage is `Early movement recommended`, and medium spoilage is `No urgent warehouse transfer required`.
