# Handoff: Phase 1 backend spikes (S1, S2, S3, S4, S6)

**For**: Jarvis (Hermes backend, homelab). **From**: Claude Code (builder). **Reviewer/owner**: Cameron.
**Tasks**: T006 (S1), T007 (S2), T008 (S3), T009 (S4), T011 (S6) in `tasks.md`.
**Branch**: `003-setup-spikes`. Results are written **into this file** (the `Result` blocks below), then committed on that branch. Do not edit anything else except the optional spike notes named in each section.

## Ground rules

- **No Kalshi auth, no real orders, no keys.** These spikes never touch Kalshi at all.
- Everything here is throwaway. Install stubs under a **scratch name or scratch profile**; remove them at the end (see Cleanup). Do not touch the real `default` profile's config beyond what a step says.
- Never paste tokens, API keys, or full config files containing secrets. Redact.
- If a step fails or a doc/API differs from what the stub assumes: **record the exact command, the exact error, and what you changed to make it work**. A failed or adapted step is a valid, useful result. Do not loop on a failure more than ~3 attempts; write down what you tried and move on.
- Pass criteria come from `plan.md` (Phase 0 Spikes). Mark each result PASS / PARTIAL / FAIL.

## Step 0: get the repo and record the environment

```sh
git clone <repo-url> ~/hermes-kalshi-plugin-spike   # or git fetch + checkout in an existing clone
cd ~/hermes-kalshi-plugin-spike && git checkout 003-setup-spikes
python3 --version
hermes --version
echo "$HERMES_HOME"; id -un; uname -a; df -T ~ | tail -1     # filesystem type matters for S4
```

### Result: environment
```
(paste output)
Backend Python version: 
Hermes version: 
Filesystem of HERMES_HOME: 
OS user running gateway/dashboard: 
```

---

## S1: unified package installs and loads (T006)

**Question**: does a unified package install (skills, tool, command, dashboard route, desktop pane)? What Python does the backend run?

Stub lives in `spikes/stub-plugin/hermes-kalshi/` (plugin.yaml, `__init__.py` with `register(ctx)`, `skills/stub/SKILL.md`, `dashboard/{manifest.json,plugin_api.py}`, `desktop/plugin.js`). Its API calls follow `research.md` R1 and are **best guesses**; fix them to the real signatures and record each change.

Steps:
1. Install the stub using the documented plugin install method (copy/symlink to `$HERMES_HOME/plugins/hermes-kalshi/`, or `hermes plugins install <path>`; record which one worked). Use a scratch profile (`hermes profile create spike-s1`) if possible.
2. `hermes plugins validate <stub dir> --install-deps`. Record output. Note especially whether `plugin.yaml` must declare the desktop half or `dashboard/` (research.md says it should not need to).
3. Enable the plugin; restart gateway/dashboard as required.
4. Skill: in a session, call `skill_view("hermes-kalshi:stub")`. Expect `STUB-SKILL-OK` text.
5. Tool: confirm `kalshi_stub_ping` is callable by the agent and returns python version and HERMES_HOME (note: which HERMES_HOME did it see?).
6. Slash command: run `/kalshi-stub a b`. Record the handler signature that actually worked (args vs kwargs vs a single string).
7. Dashboard: `curl` the route `/api/plugins/hermes-kalshi/ping` (behind the dashboard auth gate; use the documented auth). Record whether a restart was needed, and **which `HERMES_HOME` the dashboard process sees** (add a temporary print/log if needed).
8. Desktop: from the Desktop app, confirm the pane appears and shows the ping JSON. If it does not, record what the console shows. (Cameron may need to do this step; mark it `needs Desktop` if you can't.)

### Result: S1
```
Status: PASS | PARTIAL | FAIL
Install method that worked:
validate output:
skill_view result:
tool result (python/HERMES_HOME):
slash-command handler signature that worked:
dashboard route result + HERMES_HOME seen by dashboard process:
desktop pane (done by: Jarvis | Cameron | not done):
Deviations from the stub / research.md assumptions:
```

---

## S2: profile distribution (T007)

**Question**: does a profile distribution create `kalshi-bot` with paused cron jobs and the plugin enabled? Does `--clone` work for `-a`/`-b`?

Stub lives in `spikes/stub-profile/kalshi-bot/` (`distribution.yaml`, `SOUL.md`, `config.yaml`, `cron/jobs.json`). Use a scratch name if `kalshi-bot` already exists; tell us what you used.

Steps:
1. `hermes profile install spikes/stub-profile/kalshi-bot` (adjust to the documented form; the stub dir may need to be the repo root layout instead, so record what the installer expects).
2. `hermes profile list`; inspect the profile directory.
3. `hermes -p <profile> cron list`: are the shipped jobs present and **paused**?
4. Is `hermes-kalshi` listed as enabled for that profile (`hermes -p <profile> plugins list`)? If the distribution cannot enable it, record how to enable it per profile.
5. `hermes profile create <profile>-a --clone <profile>` and `-b`; confirm they copy config/SOUL and that cloned cron jobs arrive paused (or not).

### Result: S2
```
Status:
Installer's expected layout:
Profile created? Cron jobs present + paused?
Plugin enabled for profile? How:
--clone results (a, b), including cron behavior:
Deviations:
```

---

## S3: cron, timezone, scripts (T008)

**Question**: script-only jobs from `$HERMES_HOME/scripts/`; `hermes -p <profile> cron create` targets the right profile; timezone behavior of schedule expressions across a DST boundary.

Stub script: `spikes/stub-scripts/kalshi_stub.sh` (appends a UTC and America/New_York timestamp plus `$HERMES_HOME` to `$HERMES_HOME/plugin-data/hermes-kalshi-spike-s3.log`).

Steps:
1. Copy (or symlink; record which) the script into `$HERMES_HOME/scripts/` of the scratch profile. Check whether symlinks are accepted.
2. `hermes -p <profile> cron create "<expr>" "" --no-agent --script kalshi_stub.sh --name s3-stub` (adjust per `hermes cron create --help`; for a script-only job the prompt arg may be omitted). Pick an expression that fires within the next few minutes so you can observe it.
3. Confirm the job fires, appears under **that profile** (`cron list` for it and for `default`), and the log line shows the right `HERMES_HOME`.
4. **Timezone**: determine how the schedule expression's timezone is interpreted. Does the CLI/config accept an explicit timezone (e.g. `TZ=America/New_York`, a `--tz` flag, a config key)? Or is it the host's local time, or UTC? Test by scheduling `30 12 * * *` and reading `cron list` for the next-run time, plus what the host `timedatectl` says.
5. **DST**: the next DST change is Sun 2026-11-01 (US). If the scheduler supports an explicit tz, show its next-run time for a date after that boundary (or reason from the docs/source). If tz is unsupported, state the UTC-regeneration fallback is needed.
6. Failure behavior: make the script `exit 3` once; record whether the cron system alerts/logs it, and whether empty stdout is silent.
7. Overlap: manually trigger the job while it is running (add `sleep 30` temporarily); confirm it is refused.

### Result: S3
```
Status:
Script install method (copy/symlink) and whether symlink works:
cron create command that worked:
Job belongs to correct profile? log HERMES_HOME:
Timezone interpretation of schedule expressions:
DST conclusion (explicit tz supported? fallback needed?):
Failure / empty-stdout / overlap behavior:
Deviations:
```

---

## S4: shared snapshot directory across profiles (T009)

**Question**: can two profiles (same OS user) read/write one directory under the **root** Hermes home, and does the atomic create-if-absent pointer work on the homelab filesystem?

Script: `spikes/s4_snapshot_race.py <shared_dir> [--procs N]`; stdlib only; prints JSON; exit 0 on PASS (exactly one winner, one shared hash).

Steps:
1. Run it plainly: `python3 spikes/s4_snapshot_race.py <root>/plugin-data/hermes-kalshi-spike/snapshots --procs 8` (remove the dir afterwards; the pointer is create-once so reruns need a fresh dir).
2. Run it 20 times in a loop with a fresh dir each time. Record failures, if any.
3. Run it with the **two profiles' real environments**: e.g. start two shells with `HERMES_HOME` set to each profile and run the script concurrently pointing at the same root-home dir. Confirm both can read/write (permissions) and see the same hash.
4. Note the filesystem type (from Step 0) and whether the dir is on a network mount (O_EXCL is unreliable on some NFS setups).

### Result: S4
```
Status:
Single run output:
20-run loop: N failures of 20
Two-profile concurrent run output:
Filesystem / network mount?:
Permission issues?:
```

---

## S6: read-only SQLite during writes (T011)

**Question**: can the dashboard process open a profile DB read-only while a writer is active, with zero errors?

Script: `spikes/s6_readonly.py <db_path>`: starts a continuous writer, performs 100 read-only opens (`file:...?mode=ro`, 2 s busy timeout), exits 0 if zero errors.

Steps:
1. Run on the backend in a scratch dir: `python3 spikes/s6_readonly.py <scratch>/s6.db`.
2. **Dashboard context**: the real question is the dashboard/gateway process. Run the read side from inside that process if feasible (e.g. temporarily via the stub route from S1 reading a DB the writer script is hammering). If that is not feasible, state so; then at minimum run the script as the same OS user as the gateway and confirm the dashboard process can read the profile dir (`ls -l <root>/profiles/`, plugin-data dirs).
3. Confirm the dashboard process's visible path to `<root>/profiles/*/plugin-data/hermes-kalshi/data.db` (R3 says enumerate profiles from the root home explicitly).

### Result: S6
```
Status:
Script output:
Dashboard-process read test (done? how?):
Permissions on <root>/profiles/*:
```

---

## Cleanup

Remove scratch plugin, scratch profiles (`spike-s1`, S2/S3 scratch names), cron jobs `s3-stub`, and scratch dirs. Confirm the real `kalshi-bot` profile (if it existed before) was untouched.

### Result: cleanup
```
Removed:
Left behind (and why):
```

## Summary for Cameron (Jarvis fills in at the end)

| Spike | Status | Plan change needed? |
|---|---|---|
| S1 | | |
| S2 | | |
| S3 | | |
| S4 | | |
| S6 | | |

Open questions / surprises:

---
*After Jarvis finishes: commit this file on `003-setup-spikes`, then tell the builder session. The builder will write the `spikes/S*.md` notes from these results and amend `plan.md` for any failed spike before Phase 2.*
