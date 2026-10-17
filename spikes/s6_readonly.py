"""S6: continuous writer plus 100 read-only reads on a WAL SQLite file.
Usage: python3 spikes/s6_readonly.py <db_path>
Pass: zero read errors. Run it as the same user/process context as the dashboard if you can."""
import json
import multiprocessing as mp
import sqlite3
import sys
import time


def writer(path, stop):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)")
    con.commit()
    while not stop.is_set():
        con.execute("INSERT INTO t (v) VALUES (?)", (str(time.time()),))
        con.commit()


if __name__ == "__main__":
    path = sys.argv[1]
    stop = mp.Event()
    seed = sqlite3.connect(path)
    seed.execute("PRAGMA journal_mode=WAL")
    seed.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)")
    seed.commit()
    seed.close()
    p = mp.Process(target=writer, args=(path, stop))
    p.start()
    errors, ok = [], 0
    for _ in range(100):
        try:
            con = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=2)
            con.execute("SELECT count(*) FROM t").fetchone()
            con.close()
            ok += 1
        except Exception as e:  # record, do not stop
            errors.append(repr(e))
        time.sleep(0.02)
    stop.set()
    p.join()
    print(json.dumps({"ok": ok, "errors": errors[:5], "error_count": len(errors)}))
    sys.exit(0 if not errors else 1)
