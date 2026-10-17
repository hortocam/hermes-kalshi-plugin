# Handoff: Phase 1 backend spikes (S1, S2, S3, S4, S6)

**For**: Jarvis (Hermes backend, homelab). **From**: Claude Code (builder). **Reviewer/owner**: Cameron.
**Tasks**: T006 (S1), T007 (S2), T008 (S3), T009 (S4), T011 (S6) in `tasks.md`.
**Branch**: `003-setup-spikes`. Results are written **into this file** (the `Result` blocks below), then committed on that branch. Do not edit anything else except the optional spike notes named in each section.

> **Status: all five spikes run on the backend 2026-10-17 (CT 914). S1 PARTIAL (desktop half only — needs Cameron), S2 PASS with caveats, S3 PASS, S4 PASS, S6 PASS.**
> Nothing in the repo's `spikes/` stubs was edited (per the ground rules) — the two code fixes the stubs need are recorded in the S1 deviations and applied only to the throwaway installed copy.

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

Cloned to `~/projects/hermes-kalshi-plugin` (backend convention is lowercase `~/projects/`); repo on branch `003-setup-spikes` at `c2454a7`.

### Result: environment
```
$ python3 --version                      -> Python 3.13.5            # /usr/bin/python3, ad-hoc scripts
$ hermes --version                       -> Hermes Agent v0.22.2 (2026.9.24) · stable · local d923a5eb487a
                                            Install directory: /home/hermes/.hermes/hermes-agent
                                            Install method: git
                                            Python: 3.14.7
$ echo $HERMES_HOME                      -> /home/hermes/.hermes     (default profile)
$ id -un; uname -a                       -> hermes; Linux hermes 6.17.9-1-pve #1 SMP PREEMPT_DYNAMIC PMX ... x86_64
$ df -T ~ | tail -1                      -> local-nvme/subvol-914-disk-0 zfs  104857600 10854912 94002688 11% /
```
Backend Python version: **3.14.7** — the managed runtime (`~/.hermes/tools/python-3.14.7+…/bin/python3`, a Clang 22.1.3 build), confirmed by the S1 stub tool's `sys.version` *inside* the backend process. `/usr/bin/python3` is 3.13.5 and is only used for ad-hoc scripts. plan.md's "Python 3.10+" target is fine; 3.14 is what actually runs the plugin, the CLI and cron script jobs.
Hermes version: **v0.22.2 (2026.9.24), git install, local revision `d923a5eb487a`** (the checkout is the live install; `hermes-agent` is a git tree, not a packaged wheel).
Filesystem of HERMES_HOME: **ZFS** (`local-nvme/subvol-914-disk-0`). Single local volume — `findmnt` shows no separate mount for `~/.hermes` and it is **not** a network/NFS mount (relevant to S4's `O_EXCL`).
OS user running gateway/dashboard: **`hermes` (uid 1000)** for both the gateway (`hermes-gateway.service`, PID 358, *multiplexed* over the profiles) and the dashboard (`hermes-dashboard.service`, PID 356, bound `0.0.0.0:9119`). Every profile runs as that same OS user — permissions between profiles are never a factor on this host.

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
Status: PARTIAL   (every backend-side item PASS; step 8 is the only unverified item -> needs Desktop)

Install method that worked:
  Copy the package directory into the profile's plugin root:
      mkdir -p $HERMES_HOME/plugins && cp -r spikes/stub-plugin/hermes-kalshi $HERMES_HOME/plugins/
      hermes -p spike-s1 plugins enable hermes-kalshi --no-allow-tool-override
  -> "Plugin hermes-kalshi enabled. Takes effect on next session.
      Gateway reloaded plugins; nothing of this plugin needs a session or restart."
  Methods that do NOT work:
    * `hermes plugins install <local path>`: the identifier is only ever a catalog name, a Git URL,
      or owner/repo. A filesystem path is parsed as owner/repo:
        Error: Could not download the plugin from https://github.com/home/hermes.git ...
        fatal: repository 'https://github.com/home/hermes.git/' not found
    * symlinked plugin dir: discovery and `plugins validate` follow the symlink fine, but see S3 —
      cron scripts specifically reject symlinks.
  Install location: `$HERMES_HOME/plugins/<id>/` (flat layout) — profile-scoped. The root home's
  `plugins/` is the *launch* home's install dir for the dashboard/gateway.

validate output (`hermes plugins validate spikes/stub-plugin/hermes-kalshi --install-deps`, exit 1):
  ok  manifest — plugin.yaml parses
  ok  manifest fields — name, version, description present
  ok  requires_hermes — not declared
  ok  config schema — not declared
  ok  requires_env — all entries UPPER_SNAKE
  ok  loadable — entry: __init__.py, desktop/plugin.js
  ok  python dependencies — none declared
  ok  capability probe — register() ran in isolation
  FAIL declared tools — undeclared tools registered (not in provides_tools): kalshi_stub_ping
  ok  declared hooks — matches registrations
  ok  declared middleware — matches registrations
  ok  built-in tool collisions — no collisions
  ok  security scan — safe
  ok  no core override — no runtime rebinds of Hermes core
  ok  desktop surface — stays inside the plugin SDK surface
  Isolation: verdict "host", host_ready true — "dashboard backend API is served through the plugin
  host (buffered responses)"; ctx_methods: register_command, register_skill, register_tool
  `hermes plugins doctor <dir>` agrees: "OK: runtime discovery, manifest parsing, import, and
  registration passed" + WARN "registration adds tool 'kalshi_stub_ping' not listed in provides_tools".
  NB the validate harness uses a permissive fake ctx (`register_tool(self, name, *args, **kwargs)`), so
  "capability probe" PASSES even for a register() that cannot load for real (see deviations).

skill_view result (live agent session in profile spike-s1):
  skill_view(name='hermes-kalshi:stub') ->
  {"success": true, "name": "hermes-kalshi:stub",
   "content": "[Bundle context: This skill is part of the 'hermes-kalshi' plugin.]\n\n---\nname: stub\ndescription: S1 spike skill...\n",
   "description": "S1 spike skill. Say STUB-SKILL-OK when loaded.", "linked_files": null,
   "readiness_status": "available",
   "skill_dir": "/home/hermes/.hermes/profiles/spike-s1/plugins/hermes-kalshi/skills/stub",
   "_source_path": ".../skills/stub/SKILL.md"}
  The namespace is derived from the plugin name automatically (`hermes-kalshi:stub`); a ':' in the
  registered name is rejected. The skill is NOT copied into ~/.hermes/skills/.

tool result (python/HERMES_HOME):
  kalshi_stub_ping({}) -> {"ok": true, "python": "3.14.7 (main, Sep  1 2026, 14:18:09) [Clang 22.1.3 ]",
                           "hermes_home": "/home/hermes/.hermes/profiles/spike-s1"}
  -> the tool saw the PROFILE's HERMES_HOME, and the backend process Python is 3.14.7.

slash-command handler signature that worked:
  handler(raw_args: str) -> str|None  — ONE positional string, no kwargs.
  Probe: handler("a b") -> args=('a b',) kwargs={}
  Live, in an interactive session (TUI), typing `/kalshi-stub a b`:
        ⚙️  /kalshi-stub a b
        hermes-kalshi stub command ok; args=('a b',) kwargs={}
  It short-circuits the LLM (no model call).
  NOT dispatched in one-shot mode: `hermes -p spike-s1 chat -q "/kalshi-stub a b"` did not run the
  handler — the agent received it as a prompt ("Run kalshi-stub with args a b") and answered from the
  skill. Plugin slash commands are an interactive/TUI/platform-adapter feature; `chat -q` goes
  straight to the agent loop. Any scripted test of a plugin command must drive a real session.
  Registration also refuses a name that collides with a built-in command.

dashboard route result + HERMES_HOME seen by dashboard process:
  Method: `hermes dashboard --host 127.0.0.1 --port 9121 --no-open --skip-build --isolated` with
  HERMES_HOME=<scratch profile>. (Even a loopback instance token-protects /api/plugins/*: the SPA HTML
  injects window.__HERMES_SESSION_TOKEN__, sent as header X-Hermes-Session-Token.)
  A. plugin absent + not enabled in config:
       GET /api/plugins/hermes-kalshi/ping -> HTTP 404 {"detail":"Plugin not found"}
  B. copied the dir in + `plugins enable` WHILE THE SERVER RAN:
       GET .../ping -> HTTP 200
       {"ok":true,"source":"hermes-kalshi spike",
        "hermes_home":"/home/hermes/.hermes/profiles/spike-s1","python":"3.14.7","pid":714236}
  C. `plugins disable` while running -> HTTP 404 again (runtime gate).
  -> NO RESTART IS NEEDED. Routes mount at startup from <plugins root>/*/dashboard/manifest.json, and a
     plugin installed/enabled later is hot-mounted on first request (`_plugin_api_hot_mount` fallback
     behind /api/plugins/{name}/{path}); the enable/disable gate is enforced per request. The manifest
     needs {"name","api":"plugin_api.py"} and plugin_api.py must export a module-level `router` (FastAPI
     APIRouter). A user plugin's Python is only imported when it is in `plugins.enabled` and not in
     `plugins.disabled`.
  Which HERMES_HOME does the dashboard process see:
     * the pid that answered the route == the uvicorn listener pid -> with isolation "host" the plugin
       host is IN-PROCESS for the launch profile here (no separate host process on this host).
     * HERMES_HOME inside the handler = the process's own HERMES_HOME (the profile when launch-scoped).
     * the PRODUCTION dashboard (PID 356, `hermes dashboard --host 0.0.0.0 --port 9119 --no-open`) has
       no HERMES_HOME in /proc/356/environ, so its launch home = the default root /home/hermes/.hermes,
       and it scans /home/hermes/.hermes/plugins/*/dashboard/manifest.json (+ the default root, plus
       project plugins only when explicitly opted in).
     * that production instance sits behind the auth gate (basic-auth provider configured from .env:
       HERMES_DASHBOARD_BASIC_AUTH_USERNAME/PASSWORD_HASH/SECRET), so an unauthenticated curl returns
       HTTP 401 {"error":"unauthenticated","detail":"Unauthorized","reason":"no_cookie","login_url":"/login"}
       for every /api/plugins/* route. Verifying a route THERE needs Cameron's dashboard password or a
       session cookie — neither is obtainable from the shell, and neither is needed: the mechanism above
       is the identical code path.

desktop pane (done by: Jarvis | Cameron | not done): NOT DONE -> needs Desktop (Cameron).
  `desktop/plugin.js` passes the static admission lint ("desktop surface — stays inside the plugin SDK
  surface"), so nothing is known to be wrong with it, but the pane cannot be seen from the backend: the
  Desktop app runs on Cameron's Mac against this remote backend, and Electron loads a COPY from the *app
  machine's* <root>/desktop-plugins/<id>/plugin.js. A remote backend cannot materialize that copy — per
  the SDK docs the package's Desktop half shows as "unavailable (remote backend)" on Capabilities ->
  Plugins until it is installed locally. To close step 8 Cameron must, on the Mac, either:
    (a) Capabilities -> Plugins -> Install from Git, repo `hortocam/hermes-kalshi-plugin`, with the
        Desktop component ticked (copies desktop/plugin.js into
        <Mac home>/.hermes/desktop-plugins/hermes-kalshi/), or
    (b) drop `spikes/stub-plugin/hermes-kalshi/desktop/plugin.js` into
        ~/.hermes/desktop-plugins/hermes-kalshi/plugin.js on the Mac and hit Rescan,
  then confirm the pane renders the ping JSON (its ctx.rest call hits the backend's
  /api/plugins/hermes-kalshi/ping, which requires the plugin enabled on the backend too).

Deviations from the stub / research.md assumptions (all four need code/config changes):
  1. **`register_tool` requires `toolset`** as the 2nd positional argument:
     `register_tool(name, toolset, schema, handler, check_fn=None, requires_env=None, is_async=False,
      description="", emoji="", override=False)`.
     The stub's `register_tool(name=..., description=..., handler=..., schema=...)` raises
        PluginContext.register_tool() missing 1 required positional argument: 'toolset'
     and because register() aborts at the FIRST exception, the skill and the command never registered
     either. `hermes plugins list` still showed the plugin as "enabled" — the real error only appears in
     PluginManager state (`error=...`). Fix applied to the installed copy: `toolset="hermes_kalshi"`
     (matches plan.md's `toolset hermes_kalshi` for the kalshi-bot profile config).
     Lesson for the builder: one bad signature in register() silently costs every later registration in
     the same call — the tool was registered first, so the skill and command vanished with no visible
     error on any CLI surface.
  2. **Tool handlers must return a string.** Returning a dict is rejected by the registry:
        {"error": "Tool handler returned unsupported result type: dict",
         "error_type": "tool_result_contract", "tool": "kalshi_stub_ping", "result_type": "dict"}
     Fix applied: `return json.dumps({...})`. This confirms tasks.md's
     `def handler(args: dict, **kwargs) -> str` returning JSON.
  3. **`plugin.yaml` needs `provides_tools: [kalshi_stub_ping]`.** Without it validate exits 1 on the
     "declared tools" check (catalog-admission gate) and `plugins doctor` warns. The field does NOT gate
     whether an enabled plugin's tools load — it drives validate/catalog/auth-hint only.
  4. **research.md R1's desktop-half claim is machine-local, not package-local.** "a unified package
     carries the Desktop half at `$HERMES_HOME/plugins/<id>/desktop/plugin.js`" is only true on the
     machine running the Desktop app. With a remote backend (this project's actual topology — app on
     Cameron's Mac, backend on CT 914) the backend's copy is never loaded. plan.md needs a delivery step
     for the Desktop half. `plugin.yaml` itself does NOT need to declare the desktop half or `dashboard/`
     — both are found by convention (confirmed).
  Signatures that matched the stub: `register_skill(name, path, description="", frontmatter=None)` and
  `register_command(name, handler, description="", args_hint="", argument_mode=None)`.
  Extra: a fresh scratch profile cannot reach a model — credentials come from the profile's own config
  (`secrets.onepassword` env map in the default profile's config.yaml); a new profile gets an empty .env
  template, so `hermes -p <new> chat -q ...` fails with
  "No usable credentials found for provider 'ollama-cloud'. Set OLLAMA_API_KEY."
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
Status: PASS (with three caveats the builder must act on)

A real `kalshi-bot` profile already exists on this host (created 2026-10-16, from the earlier kalshi
work). It was left untouched — verified afterwards (config.yaml 14 Oct, cron/jobs.json 14 Oct, dir mtime
16 Oct). All S2 work used scratch names: kalshi-bot-spike (repo stub), kalshi-bot-fresh (corrected
stub), kalshi-bot-spike-a and -b (clones).

Installer's expected layout:
  `hermes profile install <source> [--name N] [--alias] [--force] [-y]`; source = a git URL or a LOCAL
  DIRECTORY containing `distribution.yaml` at its root. That is all it needs; the repo-root layout is
  not required.
  Only `name` is required in the manifest — version defaulted to 0.1.0 when absent. `--name` overrides
  the manifest name, so the stub can be installed under a scratch name unmodified.
  A distribution's payload owns everything in the source tree except the shared user-owned exclusions
  (memories, sessions, plans, workspace, home, backups, cache, local, state.db*, logs, auth.json, .env,
  …) — so it can legitimately ship `config.yaml`, `SOUL.md`, `cron/jobs.json`, `scripts/` AND
  **`plugins/`** (verified: the plugin tree is copied into the profile).
  `cron/jobs.json` is special-cased: it is merged by job id into the profile's canonical store.

Profile created? Cron jobs present + paused?
  FIRST install of the repo stub exactly as shipped (--name kalshi-bot-spike):
    * profile created; SOUL.md + config.yaml applied; a cron store written
    * **ZERO cron jobs installed**: `cron list` -> "No scheduled jobs in profile". The installed store
      was {"jobs": [], "updated_at": ...}. The installer reported no error and still warned
      "This distribution ships cron jobs ... review and enable manually."
    * CAUSE (stub bug, not a Hermes limitation): `cron/jobs.json` must be the canonical multi-record
      store `{"jobs": [ {...} ], "updated_at": "..."}`. The stub ships a bare JSON array `[ {...} ]`,
      which `cron.jobs.load_jobs()` reads as an empty store.
      Required record fields (taken from a working store): id (12 hex), name, prompt, skills, skill,
      script, no_agent, schedule {"kind":"cron","expr":…,"display":…}, schedule_display,
      repeat {"times":null,"completed":0}, enabled, state, deliver.
  RE-TEST with a corrected canonical `cron/jobs.json` (one no-agent script job, enabled true) and a full
  payload (config.yaml + SOUL.md + cron/ + scripts/ + plugins/):
    * `hermes -p kalshi-bot-spike cron list` ->
        5b2c1f7a9e01 [paused]
          Name: kalshi-stub-job   Schedule: 30 12 * * *   Repeat: ∞
          Next run: None          Deliver: local          Script: kalshi_stub.sh
          Mode: no-agent (script stdout delivered directly)
    * stored record: enabled=False, state="paused", next_run_at=None,
      paused_reason="Installed from a profile distribution; review it, then resume."
  -> PASS: shipped jobs arrive **paused**, with an explicit reason, and never fire until resumed.
  A fresh profile also needs a gateway serving it before the scheduler runs at all; until then `cron list`
  warns "Scheduler is not ready for profile X: no gateway serves it and no fresh ticker heartbeat". The
  multiplexed gateway's reconcile picked new profiles up on its own within ~1 min.

Plugin enabled for profile? How:
  YES. `hermes -p kalshi-bot-spike plugins list --user --plain` -> "enabled  user  0.0.1-spike  hermes-kalshi".
  Two independent things make that work, and both are needed:
    (a) the distribution's config.yaml carries `plugins: enabled: [hermes-kalshi]` (it replaces the
        profile's config on a fresh install, so this is how the enable flag ships), and
    (b) the distribution ships the plugin TREE under `plugins/hermes-kalshi/` — a distribution can do
        this. With (a) but not (b) the profile simply has an enabled entry for a plugin that is not
        installed (observed on the first, plugin-less install: `plugins list --user` printed nothing
        while config said enabled).
  This matters for US9: the kalshi-bot distribution can carry the plugin itself, so no separate
  per-profile `plugins install` step is required.

--clone results (a, b), including cron behavior:
  `hermes profile create kalshi-bot-spike-a --clone-from kalshi-bot-spike --no-alias` (and `-b`):
    * copied: config.yaml (with _config_version added), SOUL.md, .env (blank template), plugins/ (the
      stub plugin came along), platforms/, skills/ (empty — nothing to copy)
    * NOT copied: **cron/jobs.json** (the clone has no jobs at all, paused or otherwise — `cron list` ->
      "No scheduled jobs"; its cron/ holds only runtime files: .jobs.lock, .tick.lock, executions.db,
      output/, ticker_heartbeat) and **scripts/** (absent)
    * distribution.yaml is not carried (clones are not distributions)
  -> the A/B path works for config/SOUL/plugin, but `ops setup-ab` must also create the cron jobs and
     install the scripts for -a/-b. Cloned jobs do not arrive paused because none arrive.

Deviations:
  1. `cron/jobs.json` must be the canonical `{"jobs":[...],"updated_at":...}` store (see above).
  2. The distribution's `config.yaml` REPLACES the profile defaults, so it must be complete enough to be
     self-sufficient: with only `plugins:` in it the profile had no model at all (`hermes profile list`
     shows "—" in the Model column, i.e. agent jobs would have nothing to run on) and no API keys (the
     1Password `secrets` block lives in the root config.yaml — see the S1 extra note). Ship `model:`
     (default/provider/base_url/api_mode), `timezone:`, and the `secrets.onepassword` env map, or the
     profile is inert.
  3. `hermes profile install` of the SAME NAME right after `hermes profile delete <name> -y` FAILS partway
     and cannot be recovered with --force:
        FileNotFoundError: Named profile home does not exist:
          /home/hermes/.hermes/profiles/kalshi-bot-spike. Create the profile explicitly before using it.
        (on retry: "Profile ... already exists ... pass --force"; --force hits the same error)
     CAUSE: `profile delete` writes a tombstone at `profiles/.deleted/<name>`; every later write goes
     through `mkdir_under_hermes_home() -> assert_named_profile_home_live()`, which refuses a tombstoned
     home. WORKAROUND: install under a new `--name`, or clear the tombstone first
     (`rm ~/.hermes/profiles/.deleted/<name>`, the inverse of `mark_named_profile_deleted`). A fresh
     install under a new name succeeded cleanly (exit 0), so this is purely the delete/reuse-same-name
     path — but `ops setup-ab` and iterative development will hit it.
  4. Minor / for the manifest: add `hermes_requires` (e.g. ">=0.22.0") and `env_requires`; the docs expect
     them and `profile info` surfaces them. Neither is required to install.
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
Status: PASS

Script install method (copy/symlink) and whether symlink works:
  COPY — and symlinks are REJECTED.
    mkdir -p $HERMES_HOME/scripts && cp spikes/stub-scripts/kalshi_stub.sh $HERMES_HOME/scripts/ && chmod +x
    -> works. A distribution can also ship `scripts/` (payload paths are copied verbatim).
  Symlink refusal, exact text:
    ln -s <repo>/spikes/stub-scripts/kalshi_stub.sh $HERMES_HOME/scripts/kalshi_s3_link.sh
    hermes -p <profile> cron create "*/1 * * * *" --no-agent --script kalshi_s3_link.sh --name s3-symlink
    -> Failed to create job: Script path escapes the scripts directory via traversal: 'kalshi_s3_link.sh'
  A missing script is also refused at create time:
    -> Failed to create job: Script file not found: <home>/scripts/does_not_exist.sh. Create it in
       <home>/scripts/ first.
  => `ops install-scripts` must COPY into $HERMES_HOME/scripts/, never symlink, and should verify the
     target exists before creating jobs.

cron create command that worked:
  hermes -p kalshi-bot-spike-a cron create "*/2 * * * *" --no-agent --script kalshi_stub.sh --name s3-stub
  -> Created job: 03342465fad0 / Schedule: */2 * * * * / Mode: no-agent (script stdout delivered
     directly) / Next run: 2026-10-17T11:48:00-04:00
  No prompt argument is needed for a --no-agent script job (the `[prompt]` positional is optional).
  The known argument-order trap (flags between schedule and prompt) does not apply here, since a
  --no-agent job has no prompt positional to swallow.

Job belongs to correct profile? log HERMES_HOME:
  Fired at 11:48:42 (scheduled 11:48:00 — the ticker runs every 60 s, so dispatch landed ~41 s after the
  minute, consistently across every run; see the surprises list). Log line written by the stub:
    2026-10-17T15:48:42Z local=2026-10-17T11:48:42-0400 home=/home/hermes/.hermes/profiles/kalshi-bot-spike-a
  -> correct UTC + local + PROFILE home. The job lives in that profile's store only (the default
     profile's `cron list` never showed it; `hermes -p <profile> cron list` shows it and `--json` gives
     id/state/next_run_at/last_status). Execution history: `cron runs` ->
     "830840d95c23425188fa2a5e34cff976 completed job=03342465fad0 source=builtin ...".
  Scheduler topology: ONE multiplexed gateway (hermes-gateway.service, PID 358) serves ALL profiles and
  ticks their stores; a new profile is picked up by its reconcile watcher automatically. No per-profile
  gateway needed.

Timezone interpretation of schedule expressions:
  The effective configured timezone of the PROFILE, resolved by `hermes_time.get_timezone()`:
    HERMES_TZ env -> config.yaml `timezone:` (via the effective/managed-config loader) -> server-local.
  There is **no `--tz` flag on `hermes cron create`** and no per-job timezone field in the job record.
  Host `timedatectl`: America/New_York (EDT, -0400); config `timezone: America/New_York`.
  `cron create "30 12 * * *"` -> next run 2026-10-17T12:30:00-04:00 (local ET, not UTC — a `0 7 * * *`
  job in the same store also shows 07:00-04:00).
  TRAP for the ops runbook: the clone profile's config.yaml had NO `timezone:` key, yet hermes_time still
  resolved America/New_York — it came from the root/managed overlay. So a profile-scoped cron silently
  inherits the root config's zone, and with no zone anywhere falls back to server-local time. Pin
  `timezone: America/New_York` in the kalshi-bot distribution config.

DST conclusion (explicit tz supported? fallback needed?):
  Explicit IANA tz supported; DST is handled correctly by zoneinfo — NO UTC-regeneration fallback needed.
  `cron.jobs.compute_next_run({"kind":"cron","expr":"30 12 * * *","display":"30 12 * * *"})`:
    now (Oct)        -> 2026-10-17T12:30:00-04:00
    after 2026-11-01 -> 2026-11-01T12:30:00-05:00     (transition day, EST)
    after 2026-11-02 -> 2026-11-03T12:30:00-05:00
    after 2026-11-03 -> 2026-11-04T12:30:00-05:00
  i.e. the expression keeps meaning "12:30 local" across the boundary. The 07:00/12:30/16:30 ET slot table
  in plan.md can be expressed as plain cron expressions with `timezone` pinned.

Failure / empty-stdout / overlap behavior:
  Failure (`exit 3`, deliver=local):
    * execution recorded as failed with the exit code and captured stdout:
        failed  job=d98be6fbb425  "Script exited with code 3 / stdout: s3-fail stdout line: ..."
    * job record: last_status="error", last_error="Script exited with code 3\nstdout:\n...",
      failure_streak=2 (it stays scheduled and keeps retrying on its normal schedule)
    * an INCIDENT is raised: `hermes cron incidents` -> 2 incidents, each "detected", with job id,
      first/last seen, error text and a link to the captured output file
    * artifact per run: `cron/output/<jobid>/<YYYY-MM-DD_HH-MM-SS>.md` ->
        "# Cron Job: s3-fail ... **Mode:** no_agent (script) **Status:** script failed
         Script exited with code 3  stdout: ..."
    * with `--deliver local` there is no external notice ("local" = no chat delivery); the notice path is
      the configured delivery target, and `--failure-deliver local` suppresses failures only.
    * incidents stay unacknowledged until `hermes cron incidents ack <id>` — an ops health check should
      read them.
  Empty stdout = silent, confirmed: the same script when it printed nothing produced
      "# Cron Job: s3-stub ... **Status:** silent (empty output)"
    and nothing was delivered anywhere.
  Overlap = REFUSED, twice over:
    * a 90 s script on a `*/1` schedule produced exactly ONE START/END pair (11:50:43 -> 11:52:13); the
      11:51 fire was skipped and left NO execution row
    * a manual trigger during the run: `hermes cron run 61d01026f731` ->
        "Triggered job: s3-overlap (61d01026f731) / Next run: 2026-10-17T11:51:00-04:00
         Job is already being fired by the scheduler; not run again."
    * the scheduler's guard logs "Job '<label>' already running — skipping" and releases the claim so the
      next tick retries rather than wedging. (A per-job concurrent option exists in the code, off by
      default.)

Deviations:
  None that break the plan. Two operational notes for plan.md / US9:
    * dispatch lateness ~41 s on a 60 s ticker — the +2 min evaluate job and the +12 min finalize job have
      plenty of margin, but health checks should not flag a job late before ~2 min.
    * `cron list` on a freshly created profile warns until a gateway/ticker serves it; expected, and it
      clears by itself once the multiplex gateway reconciles (~1 min).
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
Status: PASS

Single run output:
  $ python3 spikes/s4_snapshot_race.py /home/hermes/.hermes/plugin-data/hermes-kalshi-spike/snapshots --procs 8
  {"winners": 1, "distinct_hashes": 1, "hashes": ["85d5b1fbc248eda133c5676f204464cbd8f2426a26d6f504c2252297bdda6f76"]}
  exit 0

20-run loop: N failures of 20   -> 0 of 20
  Every run: winners=1, distinct_hashes=1, exit 0 (fresh dir each iteration; the 3 distinct hash values
  seen across the 20 runs are expected — the body hashes the WINNER's identity, and the winner differs).

Two-profile concurrent run output:
  Two concurrent invocations against ONE fresh shared dir, each with its own real profile environment
  (HERMES_HOME=/…/profiles/spike-s1 and HERMES_HOME=/…/profiles/kalshi-bot-spike-a):
    kalshi-bot-spike-a     exit=0 {"winners": 1, "distinct_hashes": 1, "hashes": ["85d5b1fb…"]}
    spike-s1               exit=1 {"winners": 0, "distinct_hashes": 1, "hashes": ["85d5b1fb…"]}
  -> exactly ONE winner across both invocations, and both saw the SAME hash. No permission errors; both
     created dirs and wrote files in the shared tree.
  A third, sequential run against the now-populated dir: winners=0, same hash (the "reuse" path).
  On-disk result: slots/2026-01-15-0700.json == {"hash": "85d5b1fb…"} plus objects/85d5b1fb….json holding
  the winner's body — one pointer, one object.
  CAVEAT for the builder's own test: the script's exit code is a SINGLE-POOL pass criterion. When two
  independent pools race one create-once pointer the loser necessarily reports winners=0 and exits 1, so a
  multi-processor test must assert "exactly one winner across all invocations + identical hashes" (which
  held), not "every invocation exits 0".

Filesystem / network mount?:
  ZFS on a single local NVMe volume (local-nvme/subvol-914-disk-0). `findmnt` shows no separate mount for
  ~/.hermes and there is no NFS/CIFS in the path, so O_EXCL create-if-absent is trustworthy here. If the
  snapshot dir ever moves to a network share, re-run this spike — that is the documented failure mode for
  create-if-absent.

Permission issues?:
  None — by construction and by measurement. The whole shared tree is hermes:hermes 0700 (drwx------ on
  plugin-data, the spike dir, snapshots/, slots/, objects/; the pointer file 0700), and every profile runs
  as the same OS user `hermes`, so all profiles can read and write it. A third profile
  (kalshi-bot-spike-b) read the pointer written by another profile without issue.
  Shared dir used: <root>/plugin-data/hermes-kalshi-spike/snapshots (removed in cleanup).
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
Status: PASS

Script output:
  $ python3 spikes/s6_readonly.py /home/hermes/.hermes/plugin-data/hermes-kalshi-spike/s6.db
  {"ok": 100, "errors": [], "error_count": 0}
  exit 0

Dashboard-process read test (done? how?):
  DONE, for real — the read side ran INSIDE the dashboard process, not merely as the same OS user.
  A temporary route was added to the stub's dashboard/plugin_api.py (installed copy only; the repo stub was
  not edited):
      GET /api/plugins/hermes-kalshi/s6read?db=<path>&n=100&gap_ms=20
      -> performs n read-only opens (file:...?mode=ro, timeout=2) plus, as a negative control, one
         read-only INSERT attempt.
  A loopback dashboard instance was started with HERMES_HOME=<scratch profile> and, while a SEPARATE writer
  process hammered the same DB (2,773 commits in 30 s, WAL), the route returned:
      HTTP 200
      {"ok": 100, "error_count": 0, "errors": [],
       "process_pid": 727353,
       "hermes_home": "/home/hermes/.hermes/profiles/spike-s1",
       "readonly_write_attempt": "write refused as expected: OperationalError: attempt to write a readonly
                                  database"}
  -> 100 read-only opens during a continuous write loop, zero errors, from the dashboard's own process; and
     the read-only connection genuinely cannot write.
  Process identity: the answering pid (727353) was also the uvicorn listener pid for that instance — with
  `plugins.isolation: host` the plugin host runs IN-PROCESS for the launch profile here, so the route
  executed in the dashboard server process itself (a stronger context than a sidecar). The S1 stub also
  confirmed this a second time (separate instance, pid 714236): router and listener share the process.
  Root-home visibility (R3's "enumerate profiles from the root home explicitly"), read from inside that same
  process:
      {"profile_dirs": [".deleted","engineer","firmware-engineer","kalshi-bot","kalshi-bot-fresh",
                        "kalshi-bot-spike","kalshi-bot-spike-a","kalshi-bot-spike-b","kalshi-engineer",
                        "kalshi-reviewer","research","reviewer","soundscape-engineer","soundscape-qa",
                        "soundscape-reviewer","spike-s1","understudy-engineer","understudy-reviewer",
                        "web-developer","writing-partner"],
       "plugin_dbs_visible": [{"profile":"spike-s1",
                               "path":"/home/hermes/.hermes/profiles/spike-s1/plugin-data/hermes-kalshi/data.db",
                               "readable": true}],
       "shared_snapshot_dir_exists": true}
  -> the dashboard process can list <root>/profiles/* and open
     <root>/profiles/<name>/plugin-data/hermes-kalshi/data.db read-only. (A DB path only appears once a
     plugin has actually created it — the list was empty before the probe created one; the enumerator itself
     is what was under test. `.deleted` should be filtered out of the profile scan.)

Permissions on <root>/profiles/*:
  /home/hermes/.hermes/profiles                 drwxr-xr-x  hermes:hermes
  /home/hermes/.hermes/profiles/<name>          drwx------  hermes:hermes     (each profile home)
  <profile>/plugin-data/hermes-kalshi/data.db   -rw-------  hermes:hermes
  Gateway, dashboard and every profile all run as uid hermes, so the dashboard can read any profile's DB
  with no permission work. If profiles are ever run as different OS users, re-run this spike — the 0700
  profile homes would then block the dashboard.
```

---

## Cleanup

Remove scratch plugin, scratch profiles (`spike-s1`, S2/S3 scratch names), cron jobs `s3-stub`, and scratch dirs. Confirm the real `kalshi-bot` profile (if it existed before) was untouched.

### Result: cleanup
```
Removed:
  * scratch plugin install : <scratch profile>/plugins/hermes-kalshi — the only hermes-kalshi anywhere
                             under ~/.hermes. A follow-up find confirms none remain.
  * scratch profiles       : spike-s1, kalshi-bot-spike, kalshi-bot-spike-a, kalshi-bot-spike-b,
                             kalshi-bot-fresh (dirs + registry entries + their tombstones; spike-s1 also
                             had a session/routing identity purge via `profile purge-identity`)
  * S3 cron jobs           : s3-stub (03342465fad0), s3-fail (d98be6fbb425), s3-overlap (61d01026f731);
                             `cron list` for the scratch profile is empty again. s3-symlink and
                             s3-missing were never created (rejected at create time).
  * shared scratch data    : <root>/plugin-data/hermes-kalshi-spike (S4 snapshot objects/pointer and the S6
                             db + WAL) and the then-empty <root>/plugin-data; the S6 probe DB under the
                             scratch profile; /tmp and cache/scratch working files
  * test dashboards        : both temporary loopback dashboard instances on 127.0.0.1:9121 stopped. The
                             production 0.0.0.0:9119 dashboard and the gateway were never restarted or
                             interrupted.

Left behind (and why):
  * a ghost "spike-s1" row in the gateway's routing index. Its directory is gone and it holds no data;
    `profile purge-identity` reported "Session/routing identity purged: spike-s1", and the docs note the
    routing index reloads from the DB on the next gateway restart. Not restarted on purpose — the live
    desktop session runs under the dashboard and a gateway bounce was not worth the risk. It clears itself;
    nothing to fix.
  * `hermes profile list` shows exactly the 15 pre-existing profiles (default + engineer,
    firmware-engineer, kalshi-bot, kalshi-engineer, kalshi-reviewer, research, reviewer,
    soundscape-engineer, soundscape-qa, soundscape-reviewer, understudy-engineer, understudy-reviewer,
    web-developer, writing-partner).
  * one transient oddity worth knowing: deleting a profile does not always stick on the first try — the
    multiplexed gateway re-materialised spike-s1's directory twice after `profile delete` (its ticker
    recreated it) until the delete and `purge-identity` were run back to back. Idempotent on retry;
    recorded so a future cleanup does not chase it.

Confirmed untouched:
  * the real kalshi-bot profile: config.yaml 2026-10-14, cron/jobs.json 2026-10-14, dir mtime 2026-10-16
    (all predate this session); it was never written to.
  * the default profile: config.yaml plugins.enabled is still [a2a-platform, homeassistant,
    sdd-kanban-enforcer] with disabled: []; ~/.hermes/plugins holds only homeassistant, sdd_kanban_enforcer
    and .install-metadata.json; the default cron store still has its original 23 jobs.
```

## Summary for Cameron (Jarvis fills in at the end)

| Spike | Status | Plan change needed? |
|---|---|---|
| S1 | PARTIAL — every backend item PASS; desktop pane unverified (needs the Desktop app on Cameron's Mac) | Yes — (a) the package's Desktop half must be delivered to the Mac (a remote backend cannot supply it); (b) stub fixes: `register_tool(toolset=…)`, handlers must return a **string**, `plugin.yaml` needs `provides_tools` |
| S2 | PASS (with caveats) | Yes — `cron/jobs.json` must be the canonical `{"jobs":[…],"updated_at":…}` store; the distribution's `config.yaml` must carry model/provider/timezone/secrets or the profile is inert; `--clone` carries neither cron jobs nor scripts, so `ops setup-ab` must create both; note the delete-then-reinstall-same-name tombstone trap |
| S3 | PASS | No — but pin `timezone: America/New_York` in the shipped config, copy (never symlink) scripts into `$HERMES_HOME/scripts/`, expect ~41 s dispatch lateness, and have health read `cron incidents` |
| S4 | PASS | No — 0 failures in 20 runs and across two profiles; the two-profile test must assert "one winner overall + same hash" |
| S6 | PASS | No — 100 read-only opens from inside the dashboard process during a continuous writer, zero errors, read-only writes refused; filter `.deleted` out of the root-home profile scan |

Open questions / surprises:
1. **Desktop half (needs Cameron, S1 step 8).** The Desktop app is on his Mac and this backend is remote, so `desktop/plugin.js` can never reach it from CT 914. He has to install the Desktop half locally (Capabilities → Plugins → Install from Git with the Desktop component, or drop `plugin.js` into the Mac's `~/.hermes/desktop-plugins/hermes-kalshi/`) and confirm the pane shows the ping JSON. That is the only outstanding item in this handoff — everything else about the unified package (skill, tool, slash command, dashboard route, hot-mount without restart) is verified.
2. **One bad signature in `register()` silently costs every later registration.** The `toolset` omission produced no visible error in `hermes plugins list`, and validate's "capability probe" PASSES because it uses a permissive fake ctx. Only the real manager state and `hermes plugins doctor` surface it. Worth a build-side guard (register cheap items first, or wrap each registration).
3. **Cron dispatch runs up to ~41 s late** on a 60 s ticker. Fine for the 07:00/12:30/16:30 slots and the +2/+12 min follow-ups, but snapshot-age gates and health checks should not assume the scheduled minute.
4. **A profile-scoped cron with no `timezone` silently inherits the root config's zone**, and with no zone anywhere falls back to server-local time. Pin it in the distribution.
5. **A fresh profile has no model and no API keys** until its own config.yaml supplies them (the 1Password `secrets` map lives in the root config). The `kalshi-bot` distribution must ship `model:`, `timezone:` and the `secrets.onepassword` block, and declare `env_requires`, or the agent (`evaluate`) step cannot run.
6. **A distribution CAN ship the plugin under `plugins/`** — this removes any separate per-profile `plugins install` step from US9. It also ships `scripts/` for a fresh install (though `--clone` does not).
7. **`hermes profile install` after `hermes profile delete` of the same name is broken** (tombstone at `profiles/.deleted/<name>` ⇒ `FileNotFoundError: Named profile home does not exist`), unrecoverable with `--force`; use a new `--name` or clear the tombstone. Also: deleting a profile can be undone by the gateway re-materialising it — delete then `purge-identity` back to back.

---
*After Jarvis finishes: commit this file on `003-setup-spikes`, then tell the builder session. The builder will write the `spikes/S*.md` notes from these results and amend `plan.md` for any failed spike before Phase 2.*
