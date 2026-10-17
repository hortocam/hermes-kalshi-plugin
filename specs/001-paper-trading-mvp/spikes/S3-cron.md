# S3: cron, timezone, scripts (T008)

**Status: PASS (no plan change needed beyond operational notes).** Run 2026-10-17 by Jarvis. Raw output: [handoff](../handoff/phase1-backend-spikes.md) section S3.

- Script-only job: `hermes -p <profile> cron create "<expr>" --no-agent --script <file> --name <n>` (no prompt argument). The job lives in that profile's store and fires with that profile's `HERMES_HOME`.
- Scripts must be **copied** into `$HERMES_HOME/scripts/`; **symlinks are rejected** ("escapes the scripts directory via traversal"), and a missing script is refused at create time. T067 must copy, not symlink.
- Timezone: schedule expressions use the profile's effective `timezone` (HERMES_TZ, then config `timezone:`, then root/managed overlay, then server-local). No `--tz` flag. DST handled correctly (`30 12 * * *` stays 12:30 local, -04:00 to -05:00 across 2026-11-01). **No UTC-regeneration fallback needed.** Pin `timezone: America/New_York` in the distribution config (a clone silently inherited the root's zone).
- Dispatch is up to **~41 s late** on the 60 s ticker; health checks should not flag a job late before ~2 min.
- Failure: non-zero exit is recorded (stdout captured), the job keeps its schedule, and an incident is raised (`hermes cron incidents`, ack with `incidents ack <id>`); health should read incidents. Empty stdout is silent. Overlap is refused (scheduler claim + manual `cron run` both refuse).
- One multiplexed gateway serves all profiles; new profiles are picked up within ~1 min.
