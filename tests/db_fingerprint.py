"""Fingerprint the copy-bearing tables of a database.

Used to compare the local database with the live one without copying any
data around: every row is reduced to a hash of its own content, so the two
sides can be compared row by row without moving customer data anywhere.

    .venv/bin/python tests/db_fingerprint.py --db instance/asaoz.sqlite3 --out local.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sqlite3
import sys

# The tables that hold the words on the site.
COPY_TABLES = {
    "page_sections": ["page", "section", "content", "active"],
    "settings": ["key", "value"],
    "navigation": ["id", "label", "url", "position", "active"],
    "products": ["id", "name", "desc", "price", "image", "active", "position"],
    "blog_posts": ["id", "slug", "title", "summary", "body", "author", "category",
                   "status", "published_at", "image"],
    "files": ["id", "path", "filename", "kind", "size", "mime", "created_at"],
}

# The tables that hold what people wrote or bought. Counted, never copied.
ACTIVITY_TABLES = ["feedback_items", "bookings", "contacts", "journey_subscribers",
                   "orders", "testimonials", "users", "waitlist", "email_log",
                   "login_attempts", "audit_log"]


# The columns that identify a row, so a row can be matched across databases.
KEYS = {
    "page_sections": ("page", "section"),
    "settings": ("key",),
    "navigation": ("id",),
    "products": ("id",),
    "blog_posts": ("id",),
    "files": ("id",),
}


def fingerprint(conn, table, columns):
    try:
        rows = conn.execute("SELECT * FROM %s" % table).fetchall()
    except sqlite3.OperationalError:
        return None
    key_cols = KEYS.get(table, ("id",))
    out = {}
    for row in rows:
        values = {c: row[c] for c in columns if c in row.keys()}
        # a composite key: two sections of the same page are two rows
        key = "|".join(str(row[c]) for c in key_cols if c in row.keys())
        digest = hashlib.sha256(
            json.dumps(values, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        out[key] = {"hash": digest, "content": values}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", action="store_true", help="include the row content")
    args = parser.parse_args()

    path = pathlib.Path(args.db).resolve()
    if not path.exists():
        print("no database at", path)
        return 1
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    conn.row_factory = sqlite3.Row
    data = {"db": str(path), "copy": {}, "activity": {}}
    for table, columns in COPY_TABLES.items():
        rows = fingerprint(conn, table, columns)
        if rows is None:
            continue
        if not args.preview:
            for row in rows.values():
                row.pop("content", None)
        data["copy"][table] = rows
    for table in ACTIVITY_TABLES:
        try:
            data["activity"][table] = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        except sqlite3.OperationalError:
            data["activity"][table] = None
    conn.close()
    pathlib.Path(args.out).write_text(json.dumps(data, indent=1, sort_keys=True, default=str))
    print("fingerprinted %s -> %s" % (path, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
