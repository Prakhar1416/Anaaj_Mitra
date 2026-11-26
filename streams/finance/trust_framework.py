"""Trust & Verification Framework (Anaaj Mitra, Stream 4).

Components
  1. cross_sensor_verify  - primary vs independent fill-level estimate
  2. HashChain            - SHA-256 chained readings + tamper-detecting verifier
  3. ConfirmationLog      - human-confirmation checkpoint
  4. compute_trust_score  - composite of agreement, integrity, confirmation recency
  5. evaluate_trust       - convenience wrapper returning the full breakdown

Note: a hash chain proves stored records were *edited*, not that the original
data was true. Anyone who rewrites the whole chain can recompute every hash,
so keep the head hash somewhere separate (shared state/log) and pass it to
verify(expected_head=...) to detect full rewrites and truncation.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

from config import TRUST_CONFIG

GENESIS_HASH = "0" * 64


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _parse(ts):
    return datetime.fromisoformat(ts) if isinstance(ts, str) else ts


# --------------------------------------------------------------------------
# 1. Cross-sensor verification
# --------------------------------------------------------------------------
def cross_sensor_verify(primary, secondary, tolerance=None, max_diff=None):
    """Compare the primary fill % (ultrasonic) with an independent estimate.

    agreement_score = 1.0 when diff <= tolerance, then falls linearly to 0.0
    at diff >= max_diff.
    """
    tolerance = TRUST_CONFIG["sensor_tolerance_pct"] if tolerance is None else tolerance
    max_diff = TRUST_CONFIG["sensor_max_diff_pct"] if max_diff is None else max_diff
    if max_diff <= tolerance:
        raise ValueError("max_diff must be greater than tolerance")

    if primary is None or secondary is None:
        return {"match": False, "diff": None, "tolerance": tolerance,
                "agreement_score": 0.0, "reason": "missing reading"}

    diff = abs(float(primary) - float(secondary))
    if diff <= tolerance:
        score = 1.0
    else:
        score = max(0.0, 1.0 - (diff - tolerance) / (max_diff - tolerance))
    return {"match": diff <= tolerance, "diff": round(diff, 4),
            "tolerance": tolerance, "agreement_score": round(score, 4),
            "primary": primary, "secondary": secondary}


# --------------------------------------------------------------------------
# 2. SHA-256 hash chain
# --------------------------------------------------------------------------
def compute_hash(index, timestamp, data, prev_hash):
    payload = json.dumps(
        {"index": index, "timestamp": timestamp, "data": data, "prev_hash": prev_hash},
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HashChain:
    """Append-only chain of readings. Each record stores the previous hash."""

    def __init__(self, records=None):
        self.records = records or []

    def append_record(self, data, timestamp=None):
        index = len(self.records)
        prev_hash = self.records[-1]["hash"] if self.records else GENESIS_HASH
        ts = timestamp or _iso(_now())
        rec = {"index": index, "timestamp": ts, "data": data,
               "prev_hash": prev_hash,
               "hash": compute_hash(index, ts, data, prev_hash)}
        self.records.append(rec)
        return rec

    @property
    def head_hash(self):
        return self.records[-1]["hash"] if self.records else GENESIS_HASH

    def verify_chain(self, expected_head=None):
        """Recompute every hash and check every link.

        Returns {valid, first_broken_index, checked, valid_links, integrity_fraction,
                 reason}. If expected_head is given (an externally stored head
        hash), a mismatch also marks the chain invalid (catches truncation and
        full-chain rewrites).
        """
        prev = GENESIS_HASH
        first_broken, reason, ok_links = None, None, 0
        for i, rec in enumerate(self.records):
            problem = None
            if rec.get("index") != i:
                problem = "index out of sequence"
            elif rec.get("prev_hash") != prev:
                problem = "prev_hash does not match previous record"
            elif compute_hash(rec["index"], rec["timestamp"], rec["data"],
                              rec["prev_hash"]) != rec.get("hash"):
                problem = "record contents do not match stored hash"
            if problem is None:
                ok_links += 1
            elif first_broken is None:
                first_broken, reason = i, problem
            prev = rec.get("hash", "")  # follow the stored hash so later links are judged independently

        if first_broken is None and expected_head is not None and self.head_hash != expected_head:
            first_broken = len(self.records) - 1 if self.records else 0
            reason = "head hash differs from externally stored head (truncated or rewritten)"

        checked = len(self.records)
        return {"valid": first_broken is None, "first_broken_index": first_broken,
                "checked": checked, "valid_links": ok_links,
                "integrity_fraction": (ok_links / checked) if checked else 1.0,
                "reason": reason}

    # persistence (JSON; swap for SQLite when Nidhan's layer is ready)
    def save(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.records, f, indent=2)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            return cls(json.load(f))


# --------------------------------------------------------------------------
# 3. Human-confirmation checkpoint
# --------------------------------------------------------------------------
class ConfirmationError(Exception):
    pass


class ConfirmationLog:
    def __init__(self, records=None):
        self.records = records or []

    def confirm_reading(self, warehouse_id, reading_index, confirmed_by,
                        verification=None, require_match=False, now=None):
        """Record that a person confirmed a reading.

        If require_match=True, the reading must have passed cross-sensor
        verification (pass the dict returned by cross_sensor_verify).
        """
        if require_match and not (verification and verification.get("match")):
            raise ConfirmationError(
                "reading has not passed cross-sensor verification; cannot confirm")
        rec = {"warehouse_id": warehouse_id, "reading_index": reading_index,
               "confirmed_by": confirmed_by, "timestamp": _iso(now or _now())}
        self.records.append(rec)
        return rec

    def latest(self, warehouse_id):
        mine = [r for r in self.records if r["warehouse_id"] == warehouse_id]
        return max(mine, key=lambda r: r["timestamp"]) if mine else None

    def save(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.records, f, indent=2)

    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            return cls(json.load(f))


def recency_score(last_confirmed, now=None, window_hours=None):
    """1.0 just confirmed, decaying linearly to 0.0 at window_hours. None -> 0."""
    window_hours = TRUST_CONFIG["confirmation_window_hours"] if window_hours is None else window_hours
    if last_confirmed is None:
        return 0.0
    now = now or _now()
    age_h = (now - _parse(last_confirmed)).total_seconds() / 3600.0
    if age_h < 0:
        age_h = 0.0
    return round(max(0.0, 1.0 - age_h / window_hours), 4)


# --------------------------------------------------------------------------
# 4. Composite trust score
# --------------------------------------------------------------------------
def compute_trust_score(agreement, integrity, recency, weights=None):
    weights = weights or TRUST_CONFIG["weights"]
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("trust weights must sum to 1.0")
    parts = {"agreement": agreement, "integrity": integrity, "recency": recency}
    contributions = {k: round(weights[k] * parts[k], 4) for k in parts}
    return {"trust_score": round(sum(contributions.values()), 4),
            "components": parts, "weights": dict(weights),
            "contributions": contributions}


def evaluate_trust(chain, primary, secondary, confirmations, warehouse_id,
                   now=None, config=None, expected_head=None):
    """Full trust evaluation for one warehouse. Returns score + full breakdown."""
    cfg = {**TRUST_CONFIG, **(config or {})}
    verification = cross_sensor_verify(primary, secondary,
                                       cfg["sensor_tolerance_pct"], cfg["sensor_max_diff_pct"])
    chain_result = chain.verify_chain(expected_head=expected_head)
    last = confirmations.latest(warehouse_id)
    rec = recency_score(last["timestamp"] if last else None, now,
                        cfg["confirmation_window_hours"])
    integrity = 1.0 if chain_result["valid"] else 0.0
    result = compute_trust_score(verification["agreement_score"], integrity, rec, cfg["weights"])
    t = result["trust_score"]
    result.update({
        "warehouse_id": warehouse_id,
        "verification": verification,
        "chain": chain_result,
        "last_confirmation": last,
        "threshold": cfg["trust_threshold"],
        "level": ("high" if t >= cfg["trust_threshold"]
                  else "medium" if t >= cfg["trust_threshold"] - 0.2 else "low"),
    })
    return result
