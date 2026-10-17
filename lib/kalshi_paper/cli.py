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
    from . import bootstrap, config, store
except ImportError:  # executed as a script: put lib/ on the path and import as a package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from kalshi_paper import bootstrap, config, store

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
