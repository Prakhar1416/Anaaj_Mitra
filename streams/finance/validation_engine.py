"""Reality Check & Validation Engine (Anaaj Mitra, Stream 4).

Checks agent OUTPUTS against independent reference data, expected outcomes and
rules. (The trust framework checks data agreement/integrity; this checks
whether results are right against a reference.)

Statuses: Verified | Warning | Rejected | Pending Human Review
Each result is tagged validation_type:
  - "rule_based"        : output matches documented rules/test cases
  - "observed_outcome"  : output matches independent real-world observation
A rule match does NOT prove a real-world prediction is correct; the dashboard
should label these two types separately.

Usage:
    result = validate("storage", output_dict, reference_dict)
"""
from datetime import datetime, timezone

from config import TRUST_CONFIG, VALIDATION_CONFIG

VERIFIED, WARNING, REJECTED, PENDING = "Verified", "Warning", "Rejected", "Pending Human Review"
STATUSES = (VERIFIED, WARNING, REJECTED, PENDING)
RULE_BASED, OBSERVED = "rule_based", "observed_outcome"

_VALIDATORS = {}


def register(component):
    def deco(fn):
        _VALIDATORS[component] = fn
        return fn
    return deco


def make_result(component, status, rule, expected, actual, evidence,
                vtype=RULE_BASED, source=None, diff=None, notes=None):
    assert status in STATUSES
    return {"component": component, "status": status, "validation_type": vtype,
            "rule": rule, "expected": expected, "actual": actual, "diff": diff,
            "reference_source": source, "evidence": evidence, "notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat()}


def _pending(component, rule, actual, why):
    return make_result(component, PENDING, rule, None, actual, why,
                       notes="No usable reference; human decision or more evidence needed")


def validate(component, output, reference=None):
    fn = _VALIDATORS.get(component)
    if fn is None:
        return _pending(component, "no validator registered", output,
                        f"component '{component}' is not supported")
    if not isinstance(output, dict):
        return _pending(component, "output must be a dict", output, "malformed output")
    try:
        return fn(output, reference or {})
    except KeyError as e:
        return _pending(component, "required field present", output, f"missing field: {e}")


def validate_many(items):
    """items: iterable of (component, output, reference). Returns list of results."""
    return [validate(c, o, r) for c, o, r in items]


# ---------------- Water Agent ----------------
@register("water")
def _water(out, ref):
    if "expected_risk_score" not in ref:
        return _pending("water", "risk score within tolerance of reference", out, "no reference record")
    tol = ref.get("tolerance", VALIDATION_CONFIG["water_score_tolerance"])
    exp, act = ref["expected_risk_score"], out["risk_score"]
    diff = round(abs(exp - act), 4)
    status = VERIFIED if diff <= tol else WARNING if diff <= 2 * tol else REJECTED
    return make_result("water", status, f"|expected - actual| <= {tol}", exp, act,
                       f"expected {exp}, got {act}, diff {diff}", RULE_BASED,
                       ref.get("source", "reference test case"), diff)


# ---------------- Crop Agent ----------------
@register("crop")
def _crop(out, ref):
    table = ref.get("rule_table")
    if not table:
        return _pending("crop", "crop in suitability rule for (soil, risk)", out, "no rule table")
    key = f"{out['soil_type']}|{out['drought_risk']}"
    if key not in table:
        return _pending("crop", "crop in suitability rule for (soil, risk)", out["crop"],
                        f"no rule for {key}")
    allowed = table[key]
    ok = out["crop"] in allowed
    return make_result("crop", VERIFIED if ok else REJECTED,
                       f"recommended crop must be in rule[{key}]", allowed, out["crop"],
                       f"rule {key} -> {allowed}; recommendation {'matches' if ok else 'not in rule'}",
                       RULE_BASED, ref.get("source", "crop-suitability rule table"),
                       notes="Rule match only; real crop performance needs observed outcome data")


# ---------------- Storage Agent ----------------
@register("storage")
def _storage(out, ref):
    if ref.get("independent_fill_pct") is None:
        return _pending("storage", "fill within tolerance of independent reading", out, "no independent reading")
    tol = ref.get("tolerance", VALIDATION_CONFIG["storage_tolerance_pct"])
    exp, act = ref["independent_fill_pct"], out["fill_pct"]
    diff = round(abs(exp - act), 4)
    status = VERIFIED if diff <= tol else WARNING if diff <= 2 * tol else REJECTED
    return make_result("storage", status, f"|independent - calculated| <= {tol} pct points", exp, act,
                       f"reading difference {diff}, tolerance {tol}", OBSERVED,
                       ref.get("source", "manual/secondary sensor"), diff)


# ---------------- Spoilage Agent ----------------
_LEVELS = ["low", "medium", "high"]


@register("spoilage")
def _spoilage(out, ref):
    if ref.get("expected_risk") not in _LEVELS:
        return _pending("spoilage", "predicted risk equals reference label", out, "no labelled scenario")
    exp, act = ref["expected_risk"], out["predicted_risk"]
    if act not in _LEVELS:
        return _pending("spoilage", "predicted risk equals reference label", act, "unrecognised risk level")
    gap = abs(_LEVELS.index(exp) - _LEVELS.index(act))
    status = VERIFIED if gap == 0 else WARNING if gap == 1 else REJECTED
    vtype = OBSERVED if ref.get("observed") else RULE_BASED
    return make_result("spoilage", status, "predicted risk level equals reference label", exp, act,
                       f"predicted {act} vs reference {exp} ({gap} level(s) apart)", vtype,
                       ref.get("source", "labelled scenario"), gap)


# ---------------- Logistics Agent ----------------
@register("logistics")
def _logistics(out, ref):
    wh = ref.get("warehouses")
    if not wh:
        return _pending("logistics", "selected warehouse has capacity and compatibility", out, "no ground truth")
    sel = out["selected_warehouse"]
    if sel not in wh:
        return make_result("logistics", REJECTED, "selected warehouse must exist in ground truth",
                           list(wh), sel, f"{sel} not found", RULE_BASED, ref.get("source", "simulated ground truth"))
    info = wh[sel]
    cap_ok = info["capacity_available"] >= out["quantity"]
    comp_ok = out["crop"] in info["compatible_crops"]
    problems = []
    if not cap_ok:
        problems.append(f"capacity {info['capacity_available']} < quantity {out['quantity']}")
    if not comp_ok:
        problems.append(f"crop {out['crop']} incompatible")
    return make_result("logistics", VERIFIED if not problems else REJECTED,
                       "capacity >= quantity AND crop compatible",
                       {"min_capacity": out["quantity"], "crop": out["crop"]},
                       {"capacity_available": info["capacity_available"], "compatible_crops": info["compatible_crops"]},
                       "capacity and compatibility OK" if not problems else "; ".join(problems),
                       RULE_BASED, ref.get("source", "simulated ground truth"))


# ---------------- Loan Agent ----------------
@register("loan")
def _loan(out, ref):
    threshold = ref.get("threshold", TRUST_CONFIG["trust_threshold"])
    expected = "receipt" if (out["chain_valid"] and out["trust_score"] >= threshold) else "manual_review"
    ok = out["decision"] == expected
    return make_result("loan", VERIFIED if ok else REJECTED,
                       f"receipt iff chain valid and trust >= {threshold}", expected, out["decision"],
                       f"trust {out['trust_score']}, chain_valid {out['chain_valid']}, threshold {threshold}",
                       RULE_BASED, "configured trust and approval rules")


# ---------------- Health Agent ----------------
@register("health")
def _health(out, ref):
    if "expected_flag" not in ref:
        return _pending("health", "priority flag + override propagated", out, "no expected outcome")
    hid = out["hamlet_id"]
    flag = bool(out["shared_state"].get("nutrition_priority", {}).get(hid, False))
    events = [e for e in out.get("event_log", [])
              if e.get("event") == "delivery_reprioritised" and e.get("hamlet_id") == hid]
    if flag != ref["expected_flag"]:
        return make_result("health", REJECTED, "nutrition_priority flag in shared state matches expected",
                           ref["expected_flag"], flag, f"flag for {hid} is {flag}", RULE_BASED, "state/event-log comparison")
    needs_override = ref["expected_flag"] and ref.get("stock_available", True)
    if needs_override and not events:
        return make_result("health", REJECTED, "override event logged when flag set and stock available",
                           "delivery_reprioritised event", "none found",
                           "flag propagated but no reprioritisation event in log", RULE_BASED, "state/event-log comparison")
    return make_result("health", VERIFIED, "flag propagated and override logged as expected",
                       {"flag": ref["expected_flag"], "override": needs_override},
                       {"flag": flag, "override_events": len(events)},
                       "state and event log agree", RULE_BASED, "state/event-log comparison")


# ---------------- Reporting ----------------
def results_to_markdown(results):
    lines = ["| Component | Type | Rule | Expected | Actual | Status |", "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['component']} | {r['validation_type']} | {r['rule']} | {r['expected']} | {r['actual']} | {r['status']} |")
    return "\n".join(lines)
