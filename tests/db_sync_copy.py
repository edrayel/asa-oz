"""Copy a database's content from one database into another.

Two scopes:

``--scope copy``     the words on the site: page sections, settings,
                     navigation, products, stories, media. The live database
                     is the source of truth for these, because the admin
                     edits them in the CMS.
``--scope activity``  what people wrote or bought: feedback, bookings,
                     contacts, subscribers, orders, the waitlist, the
                     email log.

The tables are read from the schema, so a column that only exists on one
side is simply left alone, and a row is matched on its key columns
rather than on its position.

    # what would change
    .venv/bin/python tests/db_sync_copy.py --from live.sqlite3 --to instance/asaoz.sqlite3 --scope activity

    # do it
    .venv/bin/python tests/db_sync_copy.py --from live.sqlite3 --to instance/asaoz.sqlite3 --scope activity --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

COPY_TABLES = ["page_sections", "settings", "navigation", "products", "blog_posts", "files"]
ACTIVITY_TABLES = ["feedback_items", "bookings", "contacts", "journey_subscribers",
                    "orders", "waitlist", "email_log"]

# How a row is identified, so it can be matched across databases.
KEYS = {
    "page_sections": ("page", "section"),
    "settings": ("key",),
    "navigation": ("id",),
    "products": ("id",),
    "blog_posts": ("id",),
    "files": ("id",),
    "feedback_items": ("id",),
    "bookings": ("id",),
    "contacts": ("id",),
    "journey_subscribers": ("id",),
    "orders": ("id",),
    "waitlist": ("id",),
    "email_log": ("id",),
}


def columns(conn, table):
    try:
        return [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
    except sqlite3.OperationalError:
        return []


def digest(values):
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def sync_table(src, dst, table, apply):
    src_cols = columns(src, table)
    dst_cols = columns(dst, table)
    if not src_cols or not dst_cols:
        return None
    shared = [c for c in src_cols if c in dst_cols]
    key_cols = [c for c in KEYS.get(table, ("id",)) if c in shared]
    if not key_cols:
        return None

    src_rows = src.execute("SELECT * FROM %s" % table).fetchall()
    dst_rows = {tuple(r[c] for c in key_cols): r for r in dst.execute("SELECT * FROM %s" % table)}

    added = updated = unchanged = 0
    for row in src_rows:
        values = {c: row[c] for c in shared}
        key = tuple(row[c] for c in key_cols)
        existing = dst_rows.get(key)
        if existing is None:
            added += 1
            if apply:
                cols = list(values.keys())
                dst.execute(
                    "INSERT INTO %s (%s) VALUES (%s)" % (
                        table, ", ".join(cols), ", ".join("?" for _ in cols)),
                    [values[c] for c in cols],
                )
            continue
        current = {c: existing[c] for c in shared}
        if digest(current) == digest(values):
            unchanged += 1
            continue
        updated += 1
        if apply:
            sets = ", ".join("%s = ?" % c for c in shared if c not in key_cols)
            if sets:
                dst.execute(
                    "UPDATE %s SET %s WHERE %s" % (
                        table, sets, " AND ".join("%s = ?" % c for c in key_cols)),
                    [values[c] for c in shared if c not in key_cols] + list(key),
                )
    # Rows only in the target are left alone: the local database may hold
    # work of its own. Use --replace to make the target match the source.
    extra = len(dst_rows) - (len(src_rows) - added)
    return {"table": table, "source": len(src_rows), "target": len(dst_rows),
            "added": added, "updated": updated, "unchanged": unchanged,
            "only_in_target": max(extra, 0)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", required=True)
    parser.add_argument("--to", dest="target", required=True)
    parser.add_argument("--scope", default="copy", choices=["copy", "activity", "all"])
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--replace", action="store_true",
                        help="delete the target rows that are not in the source")
    args = parser.parse_args()

    source_path = pathlib.Path(args.source).resolve()
    target_path = pathlib.Path(args.target).resolve()
    for path in (source_path, target_path):
        if not path.exists():
            print("no database at", path)
            return 1

    src = sqlite3.connect("file:%s?mode=ro" % source_path, uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(target_path)
    dst.row_factory = sqlite3.Row

    tables = []
    if args.scope in ("copy", "all"):
        tables += COPY_TABLES
    if args.scope in ("activity", "all"):
        tables += ACTIVITY_TABLES

    changes = 0
    for table in tables:
        if args.replace:
            src_ids = {tuple(r[c] for c in KEYS.get(table, ("id",))) for r in src.execute("SELECT * FROM %s" % table)}
            dst_ids = {tuple(r[c] for c in KEYS.get(table, ("id",))) for r in dst.execute("SELECT * FROM %s" % table)}
            for key in dst_ids - src_ids:
                changes += 1
                if args.apply:
                    where = " AND ".join("%s = ?" % c for c in KEYS.get(table, ("id",)))
                    dst.execute("DELETE FROM %s WHERE %s" % (table, where), list(key))
        result = sync_table(src, dst, table, args.apply)
        if result:
            changes += result["added"] + result["updated"]
            print("%-20s source=%-4d added=%-3d updated=%-3d unchanged=%-4d only_in_target=%d"
                  % (table, result["source"], result["added"], result["updated"],
                     result["unchanged"], result["only_in_target"]))
    if args.apply:
        dst.commit()
        print("\napplied %d change(s) to %s" % (changes, target_path))
    else:
        print("\n%d change(s) would be made to %s (use --apply)" % (changes, target_path))
    src.close()
    dst.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
