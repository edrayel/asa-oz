"""SQLite data layer for Asa-OZ.

Thin helpers on top of stdlib sqlite3. The DB file lives at DATABASE (default
instance/asaoz.sqlite3) and is auto-created + seeded on first import.
"""
import json
import os
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE", os.path.join(BASE_DIR, "instance", "asaoz.sqlite3"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'physical',
  price INTEGER NOT NULL DEFAULT 0,
  img TEXT NOT NULL DEFAULT '',
  desc TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  sort INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS waitlist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  date TEXT NOT NULL DEFAULT '',
  time TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS journey_subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  journey_stage TEXT NOT NULL DEFAULT 'interest',
  source TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_email TEXT NOT NULL DEFAULT '',
  items TEXT NOT NULL DEFAULT '[]',
  total INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'enquiry',
  stripe_session_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admins (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  username TEXT NOT NULL,
  password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'image',
  size INTEGER NOT NULL DEFAULT 0,
  mime TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'upload',
  drive_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS page_sections (
  page TEXT NOT NULL,
  section TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '{}',
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (page, section)
);

CREATE TABLE IF NOT EXISTS dynamic_pages (
  slug TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  template TEXT NOT NULL DEFAULT 'default',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS navigation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL,
  url TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);
"""

DEFAULT_SETTINGS = {
    "show_prices": "1",
    "show_signup": "1",
    "show_supporting": "1",
    "show_faq_section": "1",
    "show_store": "1",
    "simple_mode": "0",
    "show_not_this": "0",
    "show_testimonials": "0",
    "show_pricing": "1",
    "price_public": "1",
    "price_free_first": "0",
    "price_commitment": "0",
}

DEFAULT_PRODUCTS = [
    {"id": "journal", "name": "Reflection Journal", "type": "physical", "price": 24,
     "img": "https://picsum.photos/seed/asaoz-journal/600/450",
     "desc": "A guided journal for identity reflection and rediscovery."},
    {"id": "print", "name": "Heritage Print", "type": "physical", "price": 18,
     "img": "https://picsum.photos/seed/asaoz-print/600/450",
     "desc": "A keepsake art print rooted in heritage and memory."},
    {"id": "session", "name": "Identity Circle Session", "type": "virtual", "price": 12,
     "img": "https://picsum.photos/seed/asaoz-circle/600/450",
     "desc": "Join an online guided circle to share and be seen."},
    {"id": "story", "name": "Cultural Storytelling Access", "type": "virtual", "price": 8,
     "img": "https://picsum.photos/seed/asaoz-story/600/450",
     "desc": "Digital collection of stories that remember you."},
    {"id": "kit", "name": "Journey Kit", "type": "physical", "price": 35,
     "img": "https://picsum.photos/seed/asaoz-kit/600/450",
     "desc": "Pre-trip materials to prepare mind and heart for travel."},
    {"id": "letter", "name": "Welcome Letter", "type": "virtual", "price": 0,
     "img": "https://picsum.photos/seed/asaoz-letter/600/450",
     "desc": "A welcome letter and printable reflection guide."},
]


def get_conn():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_column(conn, table, column, ddl):
    """Add ``column`` to ``table`` if it is missing (lightweight migration)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table).fetchall()}
    if column not in cols:
        conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl))


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()

    # Migrate: add drive_id to existing files tables created before the
    # Google Drive integration existed.
    _ensure_column(conn, "files", "drive_id", "TEXT NOT NULL DEFAULT ''")

    seed = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if seed == 0:
        conn.executemany(
            "INSERT INTO products (id, name, type, price, img, desc, sort) "
            "VALUES (:id, :name, :type, :price, :img, :desc, :sort)",
            [{**p, "sort": i} for i, p in enumerate(DEFAULT_PRODUCTS)],
        )

    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    if conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()["c"] == 0:
        pw = os.environ.get("ADMIN_PASSWORD", "asa-oz-admin")
        conn.execute(
            "INSERT INTO admins (id, username, password_hash) VALUES (1, 'admin', ?)",
            (generate_password_hash(pw),),
        )
    conn.commit()
    conn.close()


# ---------- Products ----------

def list_products(active_only=False):
    conn = get_conn()
    where = "WHERE active = 1 " if active_only else ""
    rows = conn.execute(
        f"SELECT * FROM products {where}ORDER BY sort, name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(product_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_product(product):
    conn = get_conn()
    conn.execute(
        """INSERT INTO products (id, name, type, price, img, desc, active, sort)
           VALUES (:id, :name, :type, :price, :img, :desc, :active, :sort)
           ON CONFLICT(id) DO UPDATE SET
             name=:name, type=:type, price=:price, img=:img,
             desc=:desc, active=:active, sort=:sort""",
        product,
    )
    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = get_conn()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def list_product_types(active_only=False):
    """Distinct product type values, ordered for store filters."""
    conn = get_conn()
    if active_only:
        rows = conn.execute(
            "SELECT DISTINCT type FROM products WHERE active = 1 AND type != '' ORDER BY type"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT type FROM products WHERE type != '' ORDER BY type"
        ).fetchall()
    conn.close()
    return [r["type"] for r in rows]


# ---------- Settings ----------

def get_settings():
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def set_settings(mapping):
    conn = get_conn()
    for key, value in mapping.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
    conn.commit()
    conn.close()


def prune_settings(valid_keys):
    """Delete stored settings keys that are no longer valid (e.g. moved to CMS)."""
    valid_keys = list(valid_keys)
    conn = get_conn()
    if valid_keys:
        placeholders = ",".join("?" for _ in valid_keys)
        conn.execute(
            "DELETE FROM settings WHERE key NOT IN (%s)" % placeholders,
            valid_keys,
        )
    else:
        conn.execute("DELETE FROM settings")
    conn.commit()
    conn.close()


def setting_bool(key, default="0"):
    val = get_settings().get(key, default)
    return str(val).lower() in {"1", "true", "yes", "on"}


# ---------- Feedback ----------

def add_feedback(category, text):
    conn = get_conn()
    conn.execute(
        "INSERT INTO feedback_items (category, text) VALUES (?, ?)", (category, text)
    )
    conn.commit()
    conn.close()


def list_feedback():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM feedback_items ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_feedback(feedback_id, status, note):
    conn = get_conn()
    conn.execute(
        "UPDATE feedback_items SET status = ?, note = ? WHERE id = ?",
        (status, note, feedback_id),
    )
    conn.commit()
    conn.close()


def delete_feedback(feedback_id):
    conn = get_conn()
    conn.execute("DELETE FROM feedback_items WHERE id = ?", (feedback_id,))
    conn.commit()
    conn.close()


# ---------- Waitlist ----------

def add_waitlist(email, source=""):
    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM waitlist WHERE email = ?", (email,)).fetchone()
    if exists:
        conn.close()
        return False
    conn.execute(
        "INSERT INTO waitlist (email, source) VALUES (?, ?)", (email, source)
    )
    conn.commit()
    conn.close()
    return True


def list_waitlist():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM waitlist ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Bookings ----------

def add_booking(data):
    conn = get_conn()
    conn.execute(
        """INSERT INTO bookings (name, email, phone, date, time, message)
           VALUES (:name, :email, :phone, :date, :time, :message)""",
        data,
    )
    conn.commit()
    conn.close()


def list_bookings():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM bookings ORDER BY date, time").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_booking_status(booking_id, status):
    conn = get_conn()
    conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
    conn.commit()
    conn.close()


# ---------- Contacts ----------

def add_contact(name, email, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO contacts (name, email, message) VALUES (?, ?, ?)",
        (name, email, message),
    )
    conn.commit()
    conn.close()


def list_contacts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM contacts ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Journey Subscribers ----------

def add_journey_subscriber(email, name="", journey_stage="interest", source=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO journey_subscribers (email, name, journey_stage, source) VALUES (?, ?, ?, ?)",
        (email, name, journey_stage, source),
    )
    conn.commit()
    conn.close()
    return True


def list_journey_subscribers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM journey_subscribers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_journey_subscriber(subscriber_id):
    conn = get_conn()
    conn.execute("DELETE FROM journey_subscribers WHERE id = ?", (subscriber_id,))
    conn.commit()
    conn.close()


# ---------- Orders ----------

def add_order(items, total, customer_email="", status="enquiry", stripe_session_id=""):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO orders (items, total, customer_email, status, stripe_session_id)
           VALUES (?, ?, ?, ?, ?)""",
        (json.dumps(items), total, customer_email, status, stripe_session_id),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def set_order_status(order_id, status):
    conn = get_conn()
    conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_orders():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Files ----------

def add_file(path, name="", kind="image", size=0, mime="", source="upload", drive_id=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO files (path, name, kind, size, mime, source, drive_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (path, name, kind, size, mime, source, drive_id),
    )
    conn.commit()
    conn.close()


def list_files():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM files ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_file(file_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_file_by_path(path):
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_file(file_id):
    conn = get_conn()
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()


# ---------- Pages (CMS) ----------

def get_page_sections(page):
    """Return {section_key: {content: dict, active: bool}} for a page."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT section, content, active FROM page_sections WHERE page = ?", (page,)
    ).fetchall()
    conn.close()
    return {
        r["section"]: {"content": json.loads(r["content"] or "{}"), "active": bool(r["active"])}
        for r in rows
    }


def save_page_section(page, section, content, active=True):
    conn = get_conn()
    conn.execute(
        """INSERT INTO page_sections (page, section, content, active, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(page, section) DO UPDATE SET
             content=excluded.content, active=excluded.active, updated_at=datetime('now')""",
        (page, section, json.dumps(content), int(active)),
    )
    conn.commit()
    conn.close()


def list_page_section_keys():
    conn = get_conn()
    rows = conn.execute("SELECT page, section FROM page_sections ORDER BY page, section").fetchall()
    conn.close()
    return [(r["page"], r["section"]) for r in rows]


# ---------- Admin ----------

def verify_admin(username, password):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM admins WHERE id = 1 AND username = ?", (username,)
    ).fetchone()
    conn.close()
    if not row:
        return False
    return check_password_hash(row["password_hash"], password)


def set_admin_password(username, password):
    conn = get_conn()
    conn.execute(
        "INSERT INTO admins (id, username, password_hash) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET username=excluded.username, password_hash=excluded.password_hash",
        (username, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()


# ---------- Dynamic pages ----------

def list_dynamic_pages(active_only=False):
    conn = get_conn()
    where = "WHERE active = 1 " if active_only else ""
    rows = conn.execute(f"SELECT * FROM dynamic_pages {where}ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dynamic_page(slug):
    conn = get_conn()
    row = conn.execute("SELECT * FROM dynamic_pages WHERE slug = ?", (slug,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_dynamic_page(slug, title, description="", template="default", active=True):
    conn = get_conn()
    conn.execute(
        """INSERT INTO dynamic_pages (slug, title, description, template, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
           ON CONFLICT(slug) DO UPDATE SET
             title=excluded.title, description=excluded.description,
             template=excluded.template, active=excluded.active,
             updated_at=datetime('now')""",
        (slug, title, description, template),
    )
    conn.execute("UPDATE dynamic_pages SET active = ? WHERE slug = ?", (1 if active else 0, slug))
    conn.commit()
    conn.close()


def delete_dynamic_page(slug):
    conn = get_conn()
    conn.execute("DELETE FROM dynamic_pages WHERE slug = ?", (slug,))
    conn.execute("DELETE FROM page_sections WHERE page = ?", (slug,))
    conn.commit()
    conn.close()


# ---------- Navigation ----------

def list_navigation(active_only=False):
    conn = get_conn()
    where = "WHERE active = 1 " if active_only else ""
    rows = conn.execute(f"SELECT * FROM navigation {where}ORDER BY position, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_navigation_item(item_id, label, url, position=0, active=True):
    conn = get_conn()
    if item_id:
        conn.execute(
            "UPDATE navigation SET label=?, url=?, position=?, active=? WHERE id=?",
            (label, url, position, 1 if active else 0, item_id),
        )
    else:
        conn.execute(
            "INSERT INTO navigation (label, url, position, active) VALUES (?, ?, ?, ?)",
            (label, url, position, 1 if active else 0),
        )
    conn.commit()
    conn.close()


def delete_navigation_item(item_id):
    conn = get_conn()
    conn.execute("DELETE FROM navigation WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def reorder_navigation(ordered_ids):
    conn = get_conn()
    for pos, item_id in enumerate(ordered_ids):
        conn.execute("UPDATE navigation SET position = ? WHERE id = ?", (pos, item_id))
    conn.commit()
    conn.close()


init_db()
