"""Income/Loan Agent (Anaaj Mitra, Stream 4).

Issues a receipt when trust is at/above the threshold AND the hash chain is
intact; otherwise routes to manual review with explicit reasons.
Hard rule: a broken chain ALWAYS means manual review, whatever the score.
"""
import hashlib
from datetime import datetime, timezone

from config import TRUST_CONFIG


def append_log(log, agent, action, details):
    """Shared log-append convention (align with Agrima's coordinator)."""
    if log is not None:
        log.append({"ts": datetime.now(timezone.utc).isoformat(),
                    "agent": agent, "action": action, "details": details})


def decide(trust_result, stock=None, threshold=None, log=None, now=None):
    """Return a loan decision dict from an evaluate_trust() result."""
    threshold = TRUST_CONFIG["trust_threshold"] if threshold is None else threshold
    score = trust_result["trust_score"]
    chain_ok = trust_result["chain"]["valid"]
    comps = trust_result["components"]
    warehouse = trust_result.get("warehouse_id")
    ts = (now or datetime.now(timezone.utc)).isoformat()

    reasons = []
    if not chain_ok:
        reasons.append(f"hash chain broken at record {trust_result['chain']['first_broken_index']}")
    if not trust_result["verification"]["match"]:
        reasons.append("primary and independent fill readings disagree "
                       f"(diff {trust_result['verification']['diff']})")
    if comps["recency"] < 0.5:
        reasons.append("human confirmation missing or stale")
    if score < threshold:
        reasons.append(f"trust score {score} below threshold {threshold}")

    if chain_ok and score >= threshold:
        rid = "RCPT-" + hashlib.sha256(f"{warehouse}|{ts}|{score}".encode()).hexdigest()[:10].upper()
        decision = {"decision": "receipt", "receipt_id": rid, "warehouse_id": warehouse,
                    "stock": stock, "trust_score": score, "threshold": threshold,
                    "chain_valid": True, "timestamp": ts, "reasons": []}
    else:
        decision = {"decision": "manual_review", "warehouse_id": warehouse,
                    "stock": stock, "trust_score": score, "threshold": threshold,
                    "chain_valid": chain_ok, "timestamp": ts,
                    "reasons": reasons or ["trust score below threshold"]}
    append_log(log, "loan_agent", decision["decision"],
               {k: decision[k] for k in ("warehouse_id", "trust_score", "reasons")})
    return decision
