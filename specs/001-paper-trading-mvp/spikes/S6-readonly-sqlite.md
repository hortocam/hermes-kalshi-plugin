# S6: read-only SQLite during writes (T011)

**Status: PASS.** Run 2026-10-17 by Jarvis. Raw output: [handoff](../handoff/phase1-backend-spikes.md) section S6.

- Script run: 100 read-only opens (`file:...?mode=ro`, 2 s timeout) during a continuous WAL writer, 0 errors.
- Run again **inside the dashboard process** via a temporary route during 2,773 writer commits: 100 reads, 0 errors; a write attempt on the read-only connection was refused, as required for the read-only dashboard.
- The dashboard process (in-process plugin host) can list `<root>/profiles/*` and open `<profile>/plugin-data/hermes-kalshi/data.db`. A DB appears only after the plugin creates it, so the enumerator must tolerate profiles without one. **Filter `.deleted`** out of the profile scan.
- If profiles ever run as different OS users, re-run (profile homes are 0700).
