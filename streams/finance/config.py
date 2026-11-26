"""Shared configuration for Stream 4 (Trust, Finance & Verification).

Nidhan owns the project-wide config. Until it is merged, these defaults live
here so nothing is hard-coded inside the modules. Move/merge these keys into
the shared config file when the backend structure is agreed.
"""

TRUST_CONFIG = {
    # Cross-sensor verification (percentage points of fill level)
    "sensor_tolerance_pct": 5.0,     # difference up to this counts as a match
    "sensor_max_diff_pct": 20.0,     # difference at/after which agreement score is 0

    # Composite trust score weights (must sum to 1.0)
    "weights": {"agreement": 0.40, "integrity": 0.35, "recency": 0.25},

    # Human confirmation recency: score decays linearly from 1 to 0 over this window
    "confirmation_window_hours": 24.0,

    # Loan agent
    "trust_threshold": 0.70,         # receipt only at/above this (and chain intact)
}

# Validation engine defaults
VALIDATION_CONFIG = {
    "storage_tolerance_pct": 5.0,
    "water_score_tolerance": 0.05,
}
