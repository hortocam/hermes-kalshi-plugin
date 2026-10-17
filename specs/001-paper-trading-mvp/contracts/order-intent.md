# Contract: Order Intent (trading seam)

Purpose: define the one shape through which every trade passes, so a future authenticated executor can replace the paper executor without changing sizing, risk checks, or storage. **The MVP implements only the paper executor.** No credentials, signing, or authenticated HTTP exist in the codebase (constitution III, SC-009).

## Order intent
```json
{
  "intent_id": 123, "recommendation_id": 456, "account_id": 7,
  "market_ticker": "KXHIGHTBOS-26OCT17-B64.5",
  "side": "yes", "action": "buy", "contracts": 12,
  "limit_price": "0.2800", "tif": "ioc",
  "mode": "paper",
  "risk_check": {"per_trade": {"limit": "5.00", "value": "3.36", "ok": true}, "per_event": {...}, "per_day": {...}, "price_gate": {...}, "depth": {...}},
  "snapshot_id": "sha256:...", "strategy_version_id": 4
}
```

## Interfaces (Python, `kalshi_paper.executor`)
- `RiskChecker.check(intent, account_state, strategy) -> RiskResult` (pure; same checks for any executor).
- `Executor.execute(intent, book) -> list[Fill]` protocol. `PaperExecutor` walks the snapshot orderbook with the fee model. A real executor would implement the same protocol and is **not** present.
- `ApprovalGate.required(intent, context) -> bool`: in the MVP always `False` for paper. For a future real mode the spec must define: human confirmation per order, hard per-trade and per-day dollar caps independent of bankroll percentages, kill switch, and key storage in the profile credential store (never `argv`, logs, or the repo).

## Constraints
- `mode` is `paper`; the database has a CHECK constraint to that effect.
- Intent creation and risk checks are recorded even for rejected trades (reject code stored).
- Real-money enablement requires: a new spec, constitution amendment, and the user's explicit approval.
