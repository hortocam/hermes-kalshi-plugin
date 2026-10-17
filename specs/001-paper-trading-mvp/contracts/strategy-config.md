# Contract: Strategy Version Parameters

Stored as `params_json` in `strategy_versions`; each version immutable. Defaults come from the interview and addendum; the learning loop proposes diffs.

```json
{
  "min_net_edge": 0.04,
  "price_gate": {"min": 0.05, "max": 0.95},
  "kelly_fraction": 0.25,
  "shrink_weight_to_model": 0.5,
  "caps": {"per_trade": 0.05, "per_event": 0.10, "per_day": 0.20},
  "llm_cap_points": 15,
  "max_snapshot_age_min": 20,
  "burn_in_days": 3,
  "min_depth_contracts": 5,
  "calibration": {"default": {"bias_f": 0.0, "sigma_f": 2.5}, "overrides": {"KXHIGHTBOS|midday": {"bias_f": 0.0, "sigma_f": 2.0}}},
  "bankrolls": {"real_micro": 100000000, "test_micro": 1000000000},
  "slots": {"morning": "07:00", "midday": "12:30", "afternoon": "16:30", "tz": "America/New_York"},
  "proposal_min_samples": {"bucket": 30, "calibration_days": 10}
}
```

## Rules
- A proposal may change only keys in this document; unknown keys are rejected.
- Per-watch overrides inherit the global version and replace only listed keys.
- Every recommendation and prediction records its `strategy_version_id` (FR-021).
- Changing `bankrolls` affects only newly created accounts.
- Edge arithmetic: BUY YES net edge = `p_used - ask - fee_per_contract`; BUY NO = `bid_yes - p_used - fee_per_contract`; walked levels qualify only while their marginal net edge >= `min_net_edge`.
- Sizing: `kelly = fraction * (p - c)/(1 - c)` of account equity with `c` the all-in cost per contract (cost plus fee); contracts = min(kelly, per-trade, per-event remaining, per-day remaining, qualified depth), floored to an integer; binding constraint stored.
