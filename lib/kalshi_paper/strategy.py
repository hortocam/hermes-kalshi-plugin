"""Default strategy-version parameters (contracts/strategy-config.md).

The contract's JSON shows one calibration override ("KXHIGHTBOS|midday") as an example;
the shipped default has none, so every station starts from the prior sigma 2.5 F.
Changes arrive only as new versions through the proposal flow, never by editing these.
"""
import json

DEFAULT_PARAMS = {
    "min_net_edge": 0.04,
    "price_gate": {"min": 0.05, "max": 0.95},
    "kelly_fraction": 0.25,
    "shrink_weight_to_model": 0.5,
    "caps": {"per_trade": 0.05, "per_event": 0.10, "per_day": 0.20},
    "llm_cap_points": 15,
    "max_snapshot_age_min": 20,
    "burn_in_days": 3,
    "min_depth_contracts": 5,
    "calibration": {"default": {"bias_f": 0.0, "sigma_f": 2.5}, "overrides": {}},
    "bankrolls": {"real_micro": 100_000_000, "test_micro": 1_000_000_000},
    "slots": {"morning": "07:00", "midday": "12:30", "afternoon": "16:30", "tz": "America/New_York"},
    "proposal_min_samples": {"bucket": 30, "calibration_days": 10},
}


def canonical_json(params):
    return json.dumps(params, sort_keys=True, separators=(",", ":"))
