"""kalshi-paper command line (contracts/cli.md). Stdlib only; never prints secrets.

Exit codes: 0 ok / already_done, 2 usage error, 3 partial, 4 fatal.
Run as `python3 lib/kalshi_paper/cli.py ...` or `PYTHONPATH=lib python3 -m kalshi_paper ...`.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

try:
    from . import bootstrap, config, money, store, watches
except ImportError:  # executed as a script: put lib/ on the path and import as a package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from kalshi_paper import bootstrap, config, money, store, watches

EXIT_OK, EXIT_USAGE, EXIT_PARTIAL, EXIT_FATAL = 0, 2, 3, 4


def _count(n, singular, plural):
    return "%d %s" % (n, singular if n == 1 else plural)


def _cmd_init(args):
    db = config.resolve_db(args.db)
    try:
        con = store.connect(db)
        try:
            result = bootstrap.initialize(con)
        finally:
            con.close()
    except (store.SchemaMismatch, sqlite3.Error, OSError, config.ConfigError) as e:
        print("init failed: %s" % e, file=sys.stderr)
        return EXIT_FATAL
    result["db"] = str(db)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        c = result["created"]
        if any(c.values()):
            print("init: created %s, %s, %s (db: %s)" % (
                _count(c["watches"], "watch", "watches"), _count(c["accounts"], "account", "accounts"),
                _count(c["strategy_versions"], "strategy version", "strategy versions"), db))
        else:
            print("init: no changes (db: %s)" % db)
    return EXIT_OK


def _dollars_arg(text):
    micro = money.dollars_to_micro(text)
    if micro <= 0:
        raise ValueError("amount must be positive")
    return micro


def _cmd_watch(args):
    db = config.resolve_db(args.db)
    try:
        con = store.connect(db)
        try:
            store.migrate(con)
            return _watch_action(con, args)
        finally:
            con.close()
    except (store.SchemaMismatch, sqlite3.Error, OSError) as e:
        print("watch failed: %s" % e, file=sys.stderr)
        return EXIT_FATAL


def _watch_action(con, args):
    try:
        if args.watch_action == "list":
            rows = watches.list_watches(con)
            if args.json:
                for r in rows:
                    r["accounts"] = {k: money.micro_to_dollars(v) for k, v in r["accounts"].items()}
                print(json.dumps({"watches": [
                    {k: r[k] for k in ("series_ticker", "kind", "city", "cli_code", "obs_station", "tz",
                                       "status", "accounts")} for r in rows]}, sort_keys=True))
            else:
                for r in rows:
                    print(watches.format_line(r))
            return EXIT_OK
        if args.watch_action == "enable":
            real = _dollars_arg(args.real_dollars) if args.real_dollars else None
            test = _dollars_arg(args.test_dollars) if args.test_dollars else None
            result = watches.enable(con, args.series, real_micro=real, test_micro=test)
        elif args.watch_action == "pause":
            result = watches.pause(con, args.series)
        else:
            result = watches.disable(con, args.series)
    except (watches.WatchError, ValueError) as e:
        print("watch: %s" % e, file=sys.stderr)
        return EXIT_USAGE
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(watches.describe(result))
    return EXIT_OK


def _common(suppress):
    """--db/--json. A parent's actions are shared objects, so each parser gets its own copy;
    the subcommand's copy uses SUPPRESS so it does not overwrite values given before the command."""
    kw = {"argument_default": argparse.SUPPRESS} if suppress else {}
    parent = argparse.ArgumentParser(add_help=False, **kw)
    parent.add_argument("--db", help="database path (default: from HERMES_HOME)")
    parent.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    return parent


def build_parser():
    parser = argparse.ArgumentParser(prog="kalshi-paper", parents=[_common(False)])
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("init", parents=[_common(True)],
                       help="create/migrate the DB and seed watches, accounts, strategy")
    p.set_defaults(func=_cmd_init)
    w = sub.add_parser("watch", help="list / enable / pause / disable watches")
    wsub = w.add_subparsers(dest="watch_action")
    for action, text in (("list", "show watches and bankrolls"), ("enable", "enable (creating accounts if missing)"),
                         ("pause", "stop evaluating; open positions still settle"),
                         ("disable", "stop evaluating; open positions still settle")):
        wp = wsub.add_parser(action, parents=[_common(True)], help=text)
        wp.set_defaults(func=_cmd_watch)
        if action != "list":
            wp.add_argument("series")
        if action == "enable":
            wp.add_argument("--real-dollars", help="real-scale bankroll for NEW accounts (default $100.00)")
            wp.add_argument("--test-dollars", help="test-scale bankroll for NEW accounts (default $1,000.00)")
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code else EXIT_OK
    if not getattr(args, "func", None):
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
