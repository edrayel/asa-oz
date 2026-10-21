"""Copy the web copy from one database into another.

The admin edits the words on the site in the CMS, so the live database is
the source of truth for the copy. A local development database drifts
behind it: the pages still show the words from whenever that copy was
taken. This tool copies the copy-bearing tables across and leaves
everything else — the feedback, the bookings, the orders, the accounts —
alone.

    # what would change
    .venv/bin/python tests/db_sync_copy.py --from live.sqlite3 --to instance/asaoz.sqlite3

    # do it
    .venv/bin/python tests/db_sync_copy.py --from live.sqlite3 --to instance/asaoz.sqlite3 --apply

The tables it touches are the ones the site reads its words from:
``page_sections``, ``settings``, ``navigation``, ``products``,
``blog_posts`` and ``files``. Nothing else is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

COPY_TABLES = {
    "page_sections": ["page", "section", "content", "active"],
    "settings": ["key", "value"],
    "navigation": ["id", "label", "url", "position", "active"],
    "products": ["id", "name", "desc", "price", "image", "active", "position"],
    "blog_posts": ["id", "slug", "title", "summary", "body", "author", "category",
                   "status", "published_at", "image"],
    "files": ["id", "path", "filename", "kind", "size", "mime", "created_at"],
}

# The columns that identify a row, so a row can be matched across databases.
KEYS = {
    "page_sections": ("page", "section"),
    "settings": ("key",),
    "navigation": ("id",),
    "products": ("id",),
    "blog_posts": ("id",),
    "files": ("id",),
}


def rows(conn, table):
    try:
        return conn.execute("SELECT * FROM %s" % table).fetchall()
    except sqlite3.OperationalError:
        return []


def digest(values):
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="source", required=True)
    parser.add_argument("--to", dest="target", required=True)
    parser.add_argument("--apply", action="store_true", help="write the changes")
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

    changes = 0
    for table, columns in COPY_TABLES.items():
        key_cols = KEYS[table]
        source_rows = rows(src, table)
        if not source_rows:
            continue
        target_rows = {tuple(r[k] for k in key_cols): r for r in rows(dst, table)}
        for row in source_rows:
            key = tuple(row[k] for k in key_cols)
            values = {c: row[c] for c in columns if c in row.keys()}
            existing = target_rows.get(key)
            if existing is not None:
                current = {c: existing[c] for c in columns if c in existing.keys()}
                if digest(current) == digest(values):
                    continue
            changes += 1
            label = values.get("page") or values.get("key") or values.get("slug") or values.get("name") or key
            print("%-14s %-46s %s" % (table, str(label)[:46], "update" if existing else "add"))
            if args.apply:
                cols = list(values.keys())
                placeholders = ", ".join("?" for _ in cols)
                dst.execute(
                    "INSERT OR REPLACE INTO %s (%s) VALUES (%s)" % (table, ", ".join(cols), placeholders),
                    [values[c] for c in cols],
                )
        # rows that only exist in the target are left alone: they may be
        # local work, and this tool copies the site's words, it does not
        # delete anything.
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
