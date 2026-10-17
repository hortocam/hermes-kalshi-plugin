# S1: unified package install and load (T006)

**Status: PASS.** Run 2026-10-17 by Jarvis on the backend (Hermes v0.22.2, git install); Desktop step by Cameron on the Mac. Raw commands and output: [handoff](../handoff/phase1-backend-spikes.md) section S1.

- Backend Python: **3.14.7** (managed runtime). plan.md's "3.10+ compatible" target stands; code must run on both.
- Install: copy the package to `$HERMES_HOME/plugins/hermes-kalshi/` + `hermes -p <profile> plugins enable hermes-kalshi`. `hermes plugins install <local path>` does not work (catalog name / git URL / owner/repo only). A distribution can also ship the plugin tree (see S2).
- Skill: `skill_view("hermes-kalshi:stub")` works; namespace derived from the plugin name, so register as `"stub"`, never with a colon.
- Tool saw the **profile's** `HERMES_HOME`; slash command handler is `handler(raw_args: str) -> str|None` (one positional string). Plugin commands run only in interactive/TUI/platform sessions, not `chat -q`. Names that collide with built-ins are refused.
- Dashboard: routes need `dashboard/manifest.json` (`name`, `api`) + module-level `router`; **no restart needed** (hot-mounted, enable/disable gated per request). Plugin host is in-process with the dashboard. Production dashboard launch home is the root `~/.hermes` and sits behind a login gate.
- `plugin.yaml` does **not** need to declare `dashboard/` or the desktop half (found by convention).
- Desktop: renders only when the file is on the **app machine** (`~/.hermes/desktop-plugins/hermes-kalshi/plugin.js`), opted in and rescanned; the backend's copy shows "unavailable (remote backend)". The module must **default-export an object with `id` and `register(ctx)`**.

## Corrections the build must follow (deviations from the stub / research.md)
1. `ctx.register_tool(name, toolset, schema, handler, ...)`: `toolset` is required (use `hermes_kalshi`).
2. Tool handlers must **return a string** (JSON text), not a dict.
3. `plugin.yaml` needs `provides_tools: [...]` or `hermes plugins validate` exits 1.
4. **`register()` aborts at the first exception**, silently dropping later registrations; `plugins list` still says "enabled" and validate's probe uses a permissive fake ctx. Build guard: wrap each registration, register in a deliberate order, and add a test that calls `register()` with a strict fake ctx matching the real signatures.
5. R1's "desktop half rides in the unified package" is machine-local; with a remote backend it needs its own delivery step (plan.md amended).

The repaired stubs are committed under `spikes/stub-plugin/`.
