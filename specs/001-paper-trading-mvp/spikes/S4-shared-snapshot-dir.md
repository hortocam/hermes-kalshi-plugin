# S4: shared snapshot directory across profiles (T009)

**Status: PASS.** Run 2026-10-17 by Jarvis. Raw output: [handoff](../handoff/phase1-backend-spikes.md) section S4.

- 8-process race: exactly one winner, one shared hash. 20 fresh-dir loops: 0 failures.
- Two real profile environments racing one dir: exactly one winner overall, both read the same hash, no permission errors (all profiles run as the same OS user; tree is 0700 hermes:hermes).
- Filesystem: ZFS on local NVMe, not a network mount, so `O_EXCL` create-if-absent is reliable. Re-run this spike if the snapshot dir ever moves to a network share.
- **Test note:** the loser of a two-pool race reports `winners=0` and exits 1. The build's test must assert "one winner across all invocations and identical hashes", not "every invocation exits 0". The `snapshot.py` implementation should treat `FileExistsError` as "reuse", and tolerate an empty/partial pointer read from the winner (the spike's retry loop).
