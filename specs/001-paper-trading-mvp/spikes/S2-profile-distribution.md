# S2: profile distribution (T007)

**Status: PASS, with caveats the build must act on.** Run 2026-10-17 by Jarvis using scratch names (the real `kalshi-bot` profile existed and was left untouched). Raw output: [handoff](../handoff/phase1-backend-spikes.md) section S2.

- `hermes profile install <git URL | local dir with distribution.yaml at its root> [--name N]`. Only `name` is required.
- A distribution can ship `config.yaml`, `SOUL.md`, `cron/jobs.json`, `scripts/` and **`plugins/`** (the plugin tree), so the profile can carry the plugin and its enabled flag (`plugins: enabled: [hermes-kalshi]`); no separate per-profile plugin install.
- Shipped cron jobs arrive **paused** with `paused_reason`, never firing until resumed.
- `--clone-from` copies config, SOUL, plugins/, platforms/; it does **not** copy `cron/jobs.json` or `scripts/`.

## Corrections the build must follow
1. `cron/jobs.json` must be the canonical store `{"jobs":[{id,name,prompt,skills,skill,script,no_agent,schedule{kind,expr,display},schedule_display,repeat,enabled,state,deliver}],"updated_at":...}`. A bare array installs **zero jobs with no error** (the stub had this bug; fixed).
2. The distribution `config.yaml` replaces profile defaults: ship `model:`, `timezone: America/New_York`, and the `secrets` env map, or the profile has no model and no keys. Add `hermes_requires` / `env_requires`.
3. `ops setup-ab` must create the cron jobs and copy the scripts for `-a`/`-b` itself.
4. `profile delete` then `profile install` of the same name fails (tombstone at `profiles/.deleted/<name>`); use a new `--name` or remove the tombstone. Deletes can also be undone by the gateway re-materializing the dir: follow with `profile purge-identity`.
