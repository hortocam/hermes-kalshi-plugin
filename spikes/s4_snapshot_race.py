"""S4: N processes race to create one slot pointer atomically in a shared dir.
Usage: python3 spikes/s4_snapshot_race.py <shared_dir> [--procs 8]
Pass: exactly one winner; every process reads back the same hash."""
import hashlib
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path


def worker(args):
    shared, who = args
    slots = Path(shared) / "slots"
    slots.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"writer": who}).encode()
    digest = hashlib.sha256(body).hexdigest()
    snap = Path(shared) / "objects" / (digest + ".json")
    snap.parent.mkdir(parents=True, exist_ok=True)
    tmp = snap.with_suffix(".tmp.%d" % os.getpid())
    tmp.write_bytes(body)
    os.replace(tmp, snap)
    pointer = slots / "2026-01-15-0700.json"
    won = False
    try:
        fd = os.open(pointer, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            json.dump({"hash": digest}, f)
        won = True
    except FileExistsError:
        pass
    # The winner's write may be mid-flight for a loser; retry until non-empty.
    for _ in range(200):
        text = pointer.read_text()
        if text:
            return won, json.loads(text)["hash"]
    return won, None


if __name__ == "__main__":
    shared = sys.argv[1]
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 8
    with mp.Pool(procs) as pool:
        res = pool.map(worker, [(shared, "p%d" % i) for i in range(procs)])
    winners = sum(1 for w, _ in res if w)
    hashes = {h for _, h in res}
    print(json.dumps({"winners": winners, "distinct_hashes": len(hashes), "hashes": sorted(map(str, hashes))}))
    sys.exit(0 if winners == 1 and len(hashes) == 1 and None not in hashes else 1)
