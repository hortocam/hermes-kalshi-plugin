# Contract: Agent Tools and Slash Commands

Registered in `__init__.py::register(ctx)`. Handlers have the Hermes signature `def handler(args: dict, **kwargs) -> str` and return JSON text. All tools are deterministic wrappers over `lib/kalshi_paper`; none calls an authenticated Kalshi endpoint.

## Tools (toolset `hermes_kalshi`)

### `kalshi_get_packet`
Args: `{ "slot": "2026-10-17-midday", "watch": "KXHIGHTBOS" (optional) }`.
Returns:
```json
{
  "snapshot_id": "sha256:...", "slot": "...", "as_of": "...", "cap_points": 15,
  "events": [{
    "event_ticker": "KXHIGHTBOS-26OCT17", "kind": "high", "city": "Boston", "local_date": "2026-10-17",
    "observed": {"extreme_so_far_f": 63, "last_obs_at": "...", "hours_observed": 14},
    "ensemble": {"models": ["gfs025","ecmwf_ifs025"], "members": 82, "mean_f": 64.8, "p10_f": 62.1, "p90_f": 67.0},
    "brackets": [{"ticker": "...-B64.5", "label": "64-65", "p_ensemble": 0.31, "p_market": 0.27, "yes_bid": 0.26, "yes_ask": 0.28}]
  }]
}
```
The packet contains no account balances and no trade instructions.

### `kalshi_submit_adjustments`
Args: `{ "snapshot_id": "...", "events": [{"event_ticker": "...", "deltas": {"<market_ticker>": -0.04}, "rationale": "text <= 1200 chars"}] }`.
Behavior: validates the snapshot id; clips each delta to `+/- cap_points/100`; adds to `p_ensemble`; floors at 0.001; renormalizes within each event; stores `p_llm_proposed`, `p_final`, `clipped`, rationale (+ raw hash, model id); then runs `finalize` for the slot. Returns a summary: brackets adjusted, clips, recommendations by decision, paper fills, skips. Idempotent per (snapshot, event, model); a second call returns `already_done`. Invalid/malformed input returns `{"success": false, "error": "..."}` and leaves the slot for the ensemble-only `finalize` job.

### `kalshi_status`
Args: `{ "scope": "watches" | "today" | "health" | "proposals" }`. Read-only summaries for chat.

## Slash commands (`ctx.register_command`)
| Command | Effect |
|---|---|
| `/kalshi-watch <enable|pause|disable> <series>` | manage a watch |
| `/kalshi-proposals` | list pending proposals with evidence summary |
| `/kalshi-approve <id>` / `/kalshi-reject <id>` | decide a proposal (creates a strategy version) |
| `/kalshi-report [days]` | recent scores, calibration, P&L |

Approval commands require the explicit proposal id; there is no "approve all". Handler arguments follow the signature confirmed in spike S1.

## Evaluation skill contract (`hermes-kalshi:kalshi-evaluator`)
The cron prompt: "Run the Kalshi evaluation for slot `<slot>`: call `kalshi_get_packet`, review each event's ensemble, observations and market prices, propose bracket deltas within the cap with a short rationale, call `kalshi_submit_adjustments`, then stop." The skill states the cap, forbids inventing data, and instructs the agent to submit zero deltas when it has no justified view.
