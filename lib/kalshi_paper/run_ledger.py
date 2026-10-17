"""Run ledger: one `runs` row per (profile, slot, job), with `run_events` for skips/errors.

States: running -> ok | partial | skipped | failed. `ok` and `skipped` are final: a
later begin returns `already_done`. `failed` and `partial` may be retried on the same
row. A `running` row older than STALE_AFTER_SECONDS (a crashed runner) can be taken over.
"""
from collections import namedtuple
from datetime import datetime, timedelta, timezone

from .timeutil import to_utc_iso

STALE_AFTER_SECONDS = 30 * 60
JOBS = ("snapshot", "evaluate", "finalize", "settle", "learn")
FINAL = ("ok", "partial", "skipped", "failed")
LEVELS = ("info", "skip", "error")

BeginResult = namedtuple("BeginResult", "run_id state status")


class RunStateError(Exception):
    pass


def _iso(now):
    return to_utc_iso(now if now is not None else datetime.now(timezone.utc))


def begin_run(con, profile, slot_key, job, now=None, model_id=None):
    """Claim a run. state is 'started' (caller runs it), 'already_done', or 'in_progress'."""
    if job not in JOBS:
        raise ValueError("unknown job %r" % (job,))
    now_iso = _iso(now)
    now_dt = now if now is not None else datetime.now(timezone.utc)
    cutoff = to_utc_iso(now_dt - timedelta(seconds=STALE_AFTER_SECONDS))
    with con:
        cur = con.execute(
            "INSERT INTO runs (profile, slot_key, job, started_at, status, model_id) "
            "VALUES (?, ?, ?, ?, 'running', ?) ON CONFLICT (profile, slot_key, job) DO NOTHING",
            (profile, slot_key, job, now_iso, model_id))
        if cur.rowcount == 1:
            return BeginResult(cur.lastrowid, "started", "running")
        # Retry a failed/partial run, or take over a stale running one; one statement, so
        # exactly one concurrent caller can win.
        cur = con.execute(
            "UPDATE runs SET status='running', started_at=?, finished_at=NULL, model_id=COALESCE(?, model_id) "
            "WHERE profile=? AND slot_key=? AND job=? "
            "AND (status IN ('failed', 'partial') OR (status='running' AND started_at <= ?))",
            (now_iso, model_id, profile, slot_key, job, cutoff))
        row = con.execute("SELECT id, status FROM runs WHERE profile=? AND slot_key=? AND job=?",
                          (profile, slot_key, job)).fetchone()
    if cur.rowcount == 1:
        return BeginResult(row["id"], "started", "running")
    state = "in_progress" if row["status"] == "running" else "already_done"
    return BeginResult(row["id"], state, row["status"])


def finish_run(con, run_id, status, now=None):
    if status not in FINAL:
        raise ValueError("status must be one of %s" % (FINAL,))
    with con:
        cur = con.execute("UPDATE runs SET status=?, finished_at=? WHERE id=? AND status='running'",
                          (status, _iso(now), run_id))
    if cur.rowcount != 1:
        raise RunStateError("run %s is not running" % run_id)


def record_event(con, run_id, level, code, detail="", watch_id=None, now=None):
    if level not in LEVELS:
        raise ValueError("level must be one of %s" % (LEVELS,))
    with con:
        con.execute("INSERT INTO run_events (run_id, at, level, watch_id, code, detail) VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, _iso(now), level, watch_id, code, detail))


def events(con, run_id):
    return con.execute("SELECT * FROM run_events WHERE run_id=? ORDER BY id", (run_id,)).fetchall()


def count_events(con, run_id, level):
    return con.execute("SELECT count(*) FROM run_events WHERE run_id=? AND level=?", (run_id, level)).fetchone()[0]
