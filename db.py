"""SQLite data layer for Asa-OZ.

Thin helpers on top of stdlib sqlite3. The DB file lives at DATABASE (default
instance/asaoz.sqlite3) and is auto-created + seeded on first import.
"""
import json
import os
import secrets
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

import cms

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
  status TEXT NOT NULL DEFAULT 'pending',
  token TEXT NOT NULL DEFAULT '',
  confirmed_at TEXT NOT NULL DEFAULT '',
  unsubscribed_at TEXT NOT NULL DEFAULT '',
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

-- Accounts for the CMS. ``admins`` above is the legacy single-admin table and
-- is only read to migrate the first superadmin; new accounts live here.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT 'member',
  status TEXT NOT NULL DEFAULT 'invited',
  password_hash TEXT NOT NULL DEFAULT '',
  invited_by INTEGER,
  invite_token TEXT,
  invite_expires_at TEXT,
  auth_version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  last_login_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_id INTEGER,
  actor TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  target TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT '',
  at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Testimonials written by members. The home page also has a single editable
-- testimonial in the CMS; these are the ones members sent in.
CREATE TABLE IF NOT EXISTS testimonials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  name TEXT NOT NULL DEFAULT '',
  quote TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'Community member',
  status TEXT NOT NULL DEFAULT 'new',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL DEFAULT '',
  ip TEXT NOT NULL DEFAULT '',
  at TEXT NOT NULL DEFAULT (datetime('now'))
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
  photos_id TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS blog_posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  author_email TEXT NOT NULL DEFAULT '',
  image TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft',
  published_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  recipient TEXT NOT NULL,
  subject TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'sent',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

DEFAULT_SETTINGS = {
    # Prices are not final, so they are hidden unless an admin turns them on.
    # "1" exposes the numeric price on the store, product pages, the home
    # teaser and the "Things to take with you" section. "0" hides the price
    # element entirely. Applies to every fresh database, including production.
    "show_prices": "0",
    "show_signup": "1",
    "show_supporting": "1",
    "show_faq_section": "1",
    # Store is hidden until the shop is ready. "1" shows the store section, the
    # Store link and the store pages. Applies to every fresh database.
    "show_store": "0",
    "simple_mode": "0",
    "show_not_this": "0",
    "show_testimonials": "0",
    # Membership pricing is not final, so it is hidden unless an admin turns it
    # on. Applies to every fresh database, including production.
    "show_pricing": "0",
    "show_ads": "1",
    # Automatic email. These keys must stay in this dict: admin_settings calls
    # prune_settings(DEFAULT_SETTINGS), which deletes any stored key not listed.
    "email_confirm": "1",
    "email_welcome": "1",
    "email_contact_ack": "1",
    "email_booking_confirm": "1",
    "email_order_confirm": "1",
    "email_story_ack": "1",
    "email_admin_alerts": "1",
}

DEFAULT_PRODUCTS = [
    {"id": "journal", "name": "Travel Journal", "type": "physical", "price": 24,
     "img": "https://picsum.photos/seed/asaoz-journal/600/450",
     "desc": "A guided journal for the trips you take, with room for notes, maps and sketches."},
    {"id": "print", "name": "Heritage Print", "type": "physical", "price": 18,
     "img": "https://picsum.photos/seed/asaoz-print/600/450",
     "desc": "A keepsake art print celebrating the places we travel between."},
    {"id": "session", "name": "Culture Night", "type": "virtual", "price": 12,
     "img": "https://picsum.photos/seed/asaoz-circle/600/450",
     "desc": "An online evening of food, music and stories from home and away."},
    {"id": "story", "name": "Story Archive", "type": "virtual", "price": 8,
     "img": "https://picsum.photos/seed/asaoz-story/600/450",
     "desc": "A digital collection of stories, recipes and travel notes from our trips."},
    {"id": "kit", "name": "Trip Kit", "type": "physical", "price": 35,
     "img": "https://picsum.photos/seed/asaoz-kit/600/450",
     "desc": "Pre-trip materials: packing lists, city guides and tips for the road."},
    {"id": "letter", "name": "Welcome Letter", "type": "virtual", "price": 0,
     "img": "https://picsum.photos/seed/asaoz-letter/600/450",
     "desc": "A welcome letter and a printable guide to member offers and trips."},
]


# The founder's own account of why Asa-OZ exists, in her voice. This is the
# long-form companion to the shorter founder excerpt on the about page, which
# links here. Wording is the founder's, with the site's no-dashes rule applied.
FOUNDER_STORY_BODY = """
<p>My name is Ifeoma Adaora, and for almost 30 years I have travelled the world searching for meaning, connection, and the quiet places where a woman can hear her own voice again. I didn\u2019t always know these journeys were shaping a calling. I only knew that every time I stepped into a new culture, something inside me softened, opened, and remembered itself.</p>

<p>I created Asa-OZ because I know what it feels like to reach a stage in life where you have given so much, to family, to work, to survival, that you begin to lose sight of who you are becoming. I know what it feels like to carry strength on the outside while your inner world is asking for gentleness, clarity, and renewal. And I know the quiet ache of wanting to start a new chapter, but not knowing where to begin.</p>

<p>Travel changed that for me. Not the kind of travel that rushes from one attraction to the next, but the kind that slows you down, roots you in culture, and reminds you of your own dignity. The kind that heals you in motion. The kind that restores identity.</p>

<p>Across continents, I met countless adults, especially women, who felt unseen, lonely, stuck, or unsure how to begin again. Women who had spent years holding families together, navigating transitions, surviving heartbreak, or rebuilding after life shifted unexpectedly. Women who were ready for joy but didn\u2019t know how to access it.</p>

<p>Asa-OZ was born from them. From us. From the truth that healing is not a luxury. It is a return to self.</p>

<p>This is not a travel company. It is a cultural wellness space. A place where identity is restored, confidence is rebuilt, and belonging is rediscovered. A place where adults can breathe, reconnect, and rise into the next chapter with dignity and purpose.</p>

<p>Every retreat, every circle, every cultural experience is designed with intention, to help you remember who you are, reclaim what life tried to silence, and step forward with clarity, strength, and joy.</p>

<p>You don\u2019t have to start over alone. You don\u2019t have to carry everything by yourself. You don\u2019t have to shrink to fit the life you\u2019ve outgrown.</p>

<p>Asa-OZ is your invitation to return to yourself. To travel with purpose. To heal with dignity. To rediscover the person you are becoming.</p>
""".strip()


class _Connection(sqlite3.Connection):
    """A connection that never leaves a write transaction open.

    A failed statement (a duplicate key, a constraint violation) would
    otherwise keep the transaction — and with it the database write lock —
    alive until the connection happened to be collected. On a busy site that
    turns one bad insert into "database is locked" for every other writer.
    """

    def execute(self, *args, **kwargs):
        try:
            return super().execute(*args, **kwargs)
        except Exception:
            try:
                self.rollback()
            finally:
                self.close()
            raise

    def executemany(self, *args, **kwargs):
        try:
            return super().executemany(*args, **kwargs)
        except Exception:
            try:
                self.rollback()
            finally:
                self.close()
            raise


def get_conn():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    # A busy timeout keeps concurrent writers (the request threads and the
    # mailer worker) from failing each other with "database is locked".
    conn = sqlite3.connect(DATABASE, timeout=15, factory=_Connection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def _ensure_column(conn, table, column, ddl):
    """Add ``column`` to ``table`` if it is missing (lightweight migration)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table).fetchall()}
    if column not in cols:
        conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, ddl))


def init_db():
    conn = get_conn()
    # Write-ahead logging: readers never block the writer, so the request
    # threads and the mailer worker can share the file. Set once, here.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    conn.executescript(SCHEMA)
    conn.commit()

    # Migrate: add drive_id to existing files tables created before the
    # Google Drive integration existed.
    _ensure_column(conn, "files", "drive_id", "TEXT NOT NULL DEFAULT ''")

    # Migrate: add photos_id for the Google Photos Picker integration, which
    # records the persistent media-item id of each imported pick.
    _ensure_column(conn, "files", "photos_id", "TEXT NOT NULL DEFAULT ''")

    # Migrate: member accounts. These columns tie a story, a piece of feedback,
    # an order and a testimonial to the account that sent them.
    _ensure_column(conn, "users", "email_verified_at", "TEXT")
    _ensure_column(conn, "users", "verify_token", "TEXT")
    _ensure_column(conn, "users", "verify_expires_at", "TEXT")
    _ensure_column(conn, "blog_posts", "user_id", "INTEGER")
    _ensure_column(conn, "feedback_items", "user_id", "INTEGER")
    _ensure_column(conn, "orders", "user_id", "INTEGER")

    # Migrate: double opt-in state for existing newsletter lists. Rows that
    # predate this feature are treated as confirmed, since they signed up when
    # the site promised a single-step join.
    _ensure_column(conn, "journey_subscribers", "status", "TEXT NOT NULL DEFAULT 'pending'")
    _ensure_column(conn, "journey_subscribers", "token", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "journey_subscribers", "confirmed_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "journey_subscribers", "unsubscribed_at", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "blog_posts", "author_email", "TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "UPDATE journey_subscribers SET status = 'confirmed', "
        "confirmed_at = created_at WHERE status = 'pending' AND token = ''"
    )

    # Migrate: collapse duplicate newsletter addresses (the old insert path had
    # no uniqueness check), keeping the oldest row per address.
    conn.execute(
        "DELETE FROM journey_subscribers WHERE id NOT IN "
        "(SELECT MIN(id) FROM journey_subscribers GROUP BY lower(email))"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_journey_email "
        "ON journey_subscribers(lower(email))"
    )
    # Migrate: make photos_id unique so re-picking the same photo can never store
    # a second copy. The import loop already checks for an existing row; this
    # index is what makes that check safe under two concurrent requests, which
    # a read-then-write alone does not. Any pre-existing duplicate keeps its
    # earliest row (so nothing is deleted or orphaned on disk) and simply loses
    # the id, which is a better outcome than failing to boot.
    conn.execute(
        "UPDATE files SET photos_id = '' WHERE photos_id != '' AND id NOT IN "
        "(SELECT MIN(id) FROM files WHERE photos_id != '' GROUP BY photos_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_photos_id "
        "ON files(photos_id) WHERE photos_id != ''"
    )

    # Every subscriber needs a token so marketing mail can carry an unsubscribe
    # link, including rows that predate double opt-in.
    for row in conn.execute("SELECT id FROM journey_subscribers WHERE token = ''").fetchall():
        conn.execute(
            "UPDATE journey_subscribers SET token = ? WHERE id = ?",
            (new_token(), row["id"]),
        )

    seed = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if seed == 0:
        conn.executemany(
            "INSERT INTO products (id, name, type, price, img, desc, sort) "
            "VALUES (:id, :name, :type, :price, :img, :desc, :sort)",
            [{**p, "sort": i} for i, p in enumerate(DEFAULT_PRODUCTS)],
        )

    # The founder story is a page the about section links to, so it is seeded
    # like a default rather than as content: present whenever its slug is
    # missing, including on a database that already has other posts. Clear the
    # about "Read-more link" field to hide the link, or unpublish the post.
    conn.execute(
        """INSERT OR IGNORE INTO blog_posts
           (slug, title, summary, body, author, author_email, image, category,
            status, published_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '', ?, ?, 'published',
                   datetime('now'), datetime('now'), datetime('now'))""",
        (
            "the-story-behind-asa-oz",
            "The story behind Asa-OZ",
            "Our founder on almost 30 years of travel, and why she built a club "
            "for people who want to see the world with good company.",
            FOUNDER_STORY_BODY,
            "Ifeoma Adaora",
            "/images/founder/WhatsApp%20Image%202026-08-04%20at%2017.17.33.jpeg",
            "From the team",
        ),
    )

    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    # Retired settings: price_public duplicated show_prices, and price_free_first /
    # price_commitment were never wired to anything. Fold the price_public choice
    # into show_prices, then drop all three keys.
    legacy = conn.execute("SELECT value FROM settings WHERE key = 'price_public'").fetchone()
    if legacy is not None and str(legacy["value"]) == "0":
        conn.execute("UPDATE settings SET value = '0' WHERE key = 'show_prices'")
    conn.execute(
        "DELETE FROM settings WHERE key IN "
        "('price_public', 'price_free_first', 'price_commitment')"
    )

    # Copy refresh: the footer tagline was rewritten from a three-word line to a
    # full sentence. Stored CMS content wins over the schema default, so the old
    # text has to be replaced here too. Only a row still holding the previous
    # default is touched, so a tagline the owner has edited is never lost.
    old_tagline = "Culture, community and travel."
    row = conn.execute(
        "SELECT content FROM page_sections WHERE page = 'sitewide' AND section = 'site'"
    ).fetchone()
    if row:
        content = json.loads(row["content"] or "{}")
        if content.get("tagline") == old_tagline:
            content["tagline"] = cms.SITE_TAGLINE
            conn.execute(
                "UPDATE page_sections SET content = ?, updated_at = datetime('now') "
                "WHERE page = 'sitewide' AND section = 'site'",
                (json.dumps(content),),
            )
    conn.commit()

    if conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()["c"] == 0:
        pw = os.environ.get("ADMIN_PASSWORD")
        if not pw:
            raise RuntimeError(
                "ADMIN_PASSWORD env var is required on first run to seed the admin user"
            )
        if len(pw) < 12:
            raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")
        conn.execute(
            "INSERT INTO admins (id, username, password_hash) VALUES (1, 'admin', ?)",
            (generate_password_hash(pw),),
        )
    conn.commit()

    _migrate_admin_to_users(conn)
    conn.commit()
    conn.close()


# ---------- Users, invites, audit ----------

def _migrate_admin_to_users(conn):
    """Turn the legacy single-admin row into the first ``superadmin`` account.

    The ``admins`` table can only ever hold one row, so it cannot grow into a
    user system. The row is copied into ``users`` (keeping the same password
    hash) and the account is left where it is so an older deployment keeps
    working until the first sign-in.
    """
    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] > 0:
        return
    legacy = conn.execute("SELECT username, password_hash FROM admins LIMIT 1").fetchone()
    if not legacy:
        return
    username = legacy["username"] or "admin"
    email = (os.environ.get("ADMIN_EMAIL") or "").strip()
    if not email or "@" not in email:
        email = f"{username}@localhost"
    conn.execute(
        """INSERT OR IGNORE INTO users
             (username, email, full_name, role, status, password_hash, created_at)
           VALUES (?, ?, '', 'superadmin', 'active', ?, datetime('now'))""",
        (username, email, legacy["password_hash"]),
    )


def list_users(status="", role="", search=""):
    conn = get_conn()
    sql = "SELECT * FROM users WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if role:
        sql += " AND role = ?"
        params.append(role)
    if search:
        sql += " AND (username LIKE ? OR email LIKE ? OR full_name LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    sql += " ORDER BY CASE role WHEN 'superadmin' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END, username"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_invite_token(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE invite_token = ? AND status = 'invited'", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def username_taken(username):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()["c"]
    conn.close()
    return n > 0


def email_taken(email):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE email = ? COLLATE NOCASE", (email,)
    ).fetchone()["c"]
    conn.close()
    return n > 0


def create_user(username, email, full_name="", role="member", invited_by=None, password=""):
    """Create an account. Returns (user_dict, invite_token).

    With a password the account is active straight away; without one it is
    left ``invited`` and the token is the key to the invite link.
    """
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO users
             (username, email, full_name, role, status, password_hash, invited_by,
              invite_token, invite_expires_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (
            username, email, full_name or "", role,
            "active" if password else "invited",
            generate_password_hash(password) if password else "",
            invited_by,
            token if not password else None,
            None if password else _invite_expiry(),
        ),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return get_user(user_id), token


def _invite_expiry(days=7):
    import datetime as _dt
    return (_dt.datetime.now() + _dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def set_user_password(user_id, password):
    conn = get_conn()
    conn.execute(
        """UPDATE users SET password_hash = ?, status = 'active', invite_token = NULL,
             invite_expires_at = NULL, auth_version = auth_version + 1, updated_at = datetime('now')
           WHERE id = ?""",
        (generate_password_hash(password), user_id),
    )
    conn.commit()
    conn.close()


def set_user_role(user_id, role):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET role = ?, auth_version = auth_version + 1, updated_at = datetime('now') WHERE id = ?",
        (role, user_id),
    )
    conn.commit()
    conn.close()


def set_user_status(user_id, status):
    """Suspend or reactivate an account. Suspending ends live sessions."""
    conn = get_conn()
    conn.execute(
        """UPDATE users SET status = ?, auth_version = auth_version + 1, updated_at = datetime('now')
           WHERE id = ?""",
        (status, user_id),
    )
    conn.commit()
    conn.close()


def update_user_profile(user_id, full_name="", email=None):
    conn = get_conn()
    if email:
        conn.execute(
            "UPDATE users SET full_name = ?, email = ?, updated_at = datetime('now') WHERE id = ?",
            (full_name or "", email, user_id),
        )
    else:
        conn.execute(
            "UPDATE users SET full_name = ?, updated_at = datetime('now') WHERE id = ?",
            (full_name or "", user_id),
        )
    conn.commit()
    conn.close()


def create_invite(user_id, days=7):
    """Mint a fresh invite token for an account and put it back in the invited state."""
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    conn.execute(
        """UPDATE users SET status = 'invited', invite_token = ?, invite_expires_at = ?,
             auth_version = auth_version + 1, updated_at = datetime('now')
           WHERE id = ?""",
        (token, _invite_expiry(days), user_id),
    )
    conn.commit()
    conn.close()
    return token


def invite_expired(user):
    if not user or not user.get("invite_expires_at"):
        return False
    import datetime as _dt
    try:
        expiry = _dt.datetime.strptime(user["invite_expires_at"], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return False
    return expiry < _dt.datetime.now()


def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def count_active_superadmins(exclude_id=0):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'superadmin' AND status = 'active' AND id != ?",
        (exclude_id,),
    ).fetchone()["c"]
    conn.close()
    return n


def verify_user(login, password):
    """Check a login (username or email) against the password. Returns the row or None."""
    if not login or not password:
        return None
    user = get_user_by_username(login) or get_user_by_email(login)
    if not user or not user.get("password_hash"):
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    if user.get("status") != "active":
        return None
    return user


def touch_login(user_id):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,)
    )
    conn.commit()
    conn.close()


def log_action(actor_id, actor, action, target="", detail=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (actor_id, actor, action, target, detail) VALUES (?, ?, ?, ?, ?)",
        (actor_id, actor or "", action, target or "", detail or ""),
    )
    conn.commit()
    conn.close()


def list_audit(limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Member accounts ----------

def create_member(email, full_name="", password="", username=""):
    """Create a public-site account. Returns (user, verify_token)."""
    email = (email or "").strip().lower()
    full_name = (full_name or "").strip()
    if not username:
        base = (email.split("@")[0] or "member").replace(".", "-").replace("_", "-")
        base = "".join(ch for ch in base if ch.isalnum() or ch in "-")[:24] or "member"
        username = base
        suffix = 1
        while username_taken(username):
            suffix += 1
            username = "%s-%d" % (base, suffix)
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO users
             (username, email, full_name, role, status, password_hash, verify_token,
              verify_expires_at, created_at, updated_at)
           VALUES (?, ?, ?, 'member', 'active', ?, ?, ?, datetime('now'), datetime('now'))""",
        (username, email, full_name, generate_password_hash(password), token,
         _invite_expiry(7)),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return get_user(user_id), token


def get_user_by_verify_token(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE verify_token = ? AND verify_token IS NOT NULL", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_user_email_verified(user_id):
    conn = get_conn()
    conn.execute(
        """UPDATE users SET email_verified_at = datetime('now'), verify_token = NULL,
             verify_expires_at = NULL, updated_at = datetime('now') WHERE id = ?""",
        (user_id,),
    )
    conn.commit()
    conn.close()


def email_verified(user):
    return bool(user and user.get("email_verified_at"))


def author_email_verified(user_id):
    """Has the account behind this content confirmed its address?

    Content that is published under a member's name (a story, a testimonial)
    may only go out once the address behind it has been confirmed, otherwise
    anybody could claim a name that is not theirs.
    """
    if not user_id:
        return True
    conn = get_conn()
    row = conn.execute(
        "SELECT email_verified_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return bool(row and row["email_verified_at"])


def create_verify_token(user_id, days=7):
    token = secrets.token_urlsafe(32)
    conn = get_conn()
    conn.execute(
        """UPDATE users SET verify_token = ?, verify_expires_at = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (token, _invite_expiry(days), user_id),
    )
    conn.commit()
    conn.close()
    return token


def change_user_password(user_id, password):
    conn = get_conn()
    conn.execute(
        """UPDATE users SET password_hash = ?, auth_version = auth_version + 1,
             updated_at = datetime('now') WHERE id = ?""",
        (generate_password_hash(password), user_id),
    )
    conn.commit()
    conn.close()


# ---------- Testimonials ----------

def add_testimonial(user_id, name, quote, role="Community member"):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO testimonials (user_id, name, quote, role) VALUES (?, ?, ?, ?)",
        (user_id or 0, (name or "").strip(), (quote or "").strip(), (role or "").strip()),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def list_testimonials(status="", user_id=0):
    conn = get_conn()
    sql = "SELECT * FROM testimonials WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if user_id:
        sql += " AND user_id = ?"
        params.append(user_id)
    sql += " ORDER BY id DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_testimonial(testimonial_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM testimonials WHERE id = ?", (testimonial_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_testimonial_status(testimonial_id, status):
    conn = get_conn()
    conn.execute("UPDATE testimonials SET status = ? WHERE id = ?", (status, testimonial_id))
    conn.commit()
    conn.close()


def delete_testimonial(testimonial_id):
    conn = get_conn()
    conn.execute("DELETE FROM testimonials WHERE id = ?", (int(testimonial_id),))
    conn.commit()
    conn.close()


# ---------- Login throttling ----------

def record_login_failure(username, ip):
    conn = get_conn()
    conn.execute(
        "INSERT INTO login_attempts (username, ip) VALUES (?, ?)", (username, ip)
    )
    conn.execute(
        "DELETE FROM login_attempts WHERE at < datetime('now', '-1 day')"
    )
    conn.commit()
    conn.close()


def clear_login_failures(username, ip):
    conn = get_conn()
    conn.execute(
        "DELETE FROM login_attempts WHERE username = ? AND ip = ?", (username, ip)
    )
    conn.commit()
    conn.close()


def login_lockout(username, ip, max_attempts=5, window_minutes=15, lock_minutes=15):
    """Seconds to wait before another attempt is allowed (0 when allowed)."""
    conn = get_conn()
    row = conn.execute(
        """SELECT COUNT(*) AS n,
                  CAST((julianday('now') - julianday(MAX(at))) * 86400 AS INTEGER) AS age
             FROM login_attempts
            WHERE username = ? AND ip = ? AND at > datetime('now', ?)""",
        (username, ip, f"-{window_minutes} minutes"),
    ).fetchone()
    conn.close()
    if not row or row["n"] < max_attempts:
        return 0
    age = row["age"] if row["age"] is not None else 0
    remaining = lock_minutes * 60 - int(age)
    return remaining if remaining > 0 else 0



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

def add_feedback(category, text, user_id=0):
    conn = get_conn()
    conn.execute(
        "INSERT INTO feedback_items (category, text, user_id) VALUES (?, ?, ?)",
        (category, text, user_id or 0),
    )
    conn.commit()
    conn.close()


def list_feedback_for_user(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM feedback_items WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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

def new_token():
    """Opaque single-purpose token for confirm / unsubscribe links."""
    return secrets.token_urlsafe(24)


def subscribe_journey(email, name="", journey_stage="interest", source=""):
    """Add or refresh a newsletter subscriber and return the stored row.

    An address that already exists is refreshed, never duplicated. A confirmed
    address keeps its state (a repeat submit must not resend anything), while an
    unsubscribed address is put back into double opt-in with a fresh token,
    because re-submitting the form is an explicit request to rejoin.
    """
    email = (email or "").strip().lower()
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM journey_subscribers WHERE lower(email) = ?", (email,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO journey_subscribers (email, name, journey_stage, source, status, token) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (email, name, journey_stage, source, new_token()),
        )
    elif row["status"] == "unsubscribed":
        conn.execute(
            "UPDATE journey_subscribers SET status = 'pending', token = ?, "
            "confirmed_at = '', unsubscribed_at = '', name = ?, journey_stage = ?, source = ? "
            "WHERE id = ?",
            (new_token(), name or row["name"], journey_stage, source, row["id"]),
        )
    conn.commit()
    out = dict(conn.execute(
        "SELECT * FROM journey_subscribers WHERE lower(email) = ?", (email,)
    ).fetchone())
    conn.close()
    out["is_new"] = row is None
    return out


def get_subscriber(email):
    if not email:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM journey_subscribers WHERE lower(email) = ?", ((email or "").strip().lower(),)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_subscriber_by_token(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM journey_subscribers WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def confirm_subscriber(token):
    """Mark a pending subscriber confirmed. Returns the row, or None if unknown.

    The token is kept afterwards so the same link can also unsubscribe.
    """
    sub = get_subscriber_by_token(token)
    if not sub:
        return None
    conn = get_conn()
    conn.execute(
        "UPDATE journey_subscribers SET status = 'confirmed', confirmed_at = datetime('now'), "
        "unsubscribed_at = '' WHERE id = ?",
        (sub["id"],),
    )
    conn.commit()
    conn.close()
    return get_subscriber_by_token(token)


def unsubscribe_by_token(token):
    sub = get_subscriber_by_token(token)
    if not sub:
        return None
    conn = get_conn()
    conn.execute(
        "UPDATE journey_subscribers SET status = 'unsubscribed', "
        "unsubscribed_at = datetime('now') WHERE id = ?",
        (sub["id"],),
    )
    conn.commit()
    conn.close()
    return get_subscriber_by_token(token)


def list_journey_subscribers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM journey_subscribers ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_journey_subscriber(subscriber_id):
    conn = get_conn()
    conn.execute("DELETE FROM journey_subscribers WHERE id = ?", (int(subscriber_id),))
    conn.commit()
    conn.close()


# ---------- Email log ----------

def log_email(kind, recipient, subject="", status="sent", error=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO email_log (kind, recipient, subject, status, error) VALUES (?, ?, ?, ?, ?)",
        (kind, recipient, subject, status, error),
    )
    conn.commit()
    conn.close()


def list_email_log(limit=200):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM email_log ORDER BY id DESC LIMIT ?", (int(limit),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Backup restore ----------

# Whitelist of importable tables and their columns. Anything not listed here is
# ignored, so a crafted payload cannot reach an arbitrary table or column.
BACKUP_TABLES = {
    "feedback": ("feedback_items", [
        "id", "category", "text", "status", "note", "created_at"]),
    "waitlist": ("waitlist", [
        "id", "email", "source", "created_at"]),
    "bookings": ("bookings", [
        "id", "name", "email", "phone", "date", "time", "message", "status", "created_at"]),
    "contacts": ("contacts", [
        "id", "name", "email", "message", "created_at"]),
    "orders": ("orders", [
        "id", "customer_email", "items", "total", "status", "stripe_session_id", "created_at"]),
    "journey_subscribers": ("journey_subscribers", [
        "id", "email", "name", "journey_stage", "source", "status", "token",
        "confirmed_at", "unsubscribed_at", "created_at"]),
    "files": ("files", [
        "id", "path", "name", "kind", "size", "mime", "source", "drive_id", "photos_id",
        "created_at"]),
}


def import_backup(payload):
    """Restore rows from a /admin/export style payload.

    Only the whitelisted columns above are ever written, and only those a row
    actually carries. Rows that include their id are idempotent via OR IGNORE;
    rows without one fall back to whatever unique key the table has (the
    newsletter list is unique on lower(email)). Running the same payload twice
    therefore adds nothing the second time.

    Returns a {label: count} report of rows actually written.
    """
    report = {}
    conn = get_conn()
    try:
        for key, (table, allowed) in BACKUP_TABLES.items():
            written = 0
            for row in payload.get(key) or []:
                if not isinstance(row, dict):
                    continue
                cols = [c for c in allowed if c in row and row[c] is not None]
                if not cols:
                    continue
                cur = conn.execute(
                    "INSERT OR IGNORE INTO %s (%s) VALUES (%s)"
                    % (table, ", ".join(cols), ", ".join("?" for _ in cols)),
                    [row[c] for c in cols],
                )
                written += max(cur.rowcount, 0)
            report[key] = written

        products = payload.get("products") or []
        written = 0
        for row in products:
            if not isinstance(row, dict) or not row.get("id"):
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO products (id, name, type, price, img, desc, active, sort) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row.get("id"), row.get("name", ""), row.get("type", ""),
                 row.get("price", 0), row.get("img", ""), row.get("desc", ""),
                 row.get("active", 1), row.get("sort", 0)),
            )
            written += cur.rowcount if cur.rowcount > 0 else 0
        report["products"] = written

        settings = payload.get("settings") or {}
        written = 0
        for key, value in settings.items():
            if not isinstance(key, str):
                continue
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, "" if value is None else str(value)),
            )
            written += 1
        report["settings"] = written

        # CMS content: {page: {section: {field: value}}}
        cms_data = payload.get("cms") or {}
        written = 0
        for page, sections in cms_data.items():
            if not isinstance(sections, dict):
                continue
            for section, content in sections.items():
                if not isinstance(content, dict) or not content:
                    continue
                existing = conn.execute(
                    "SELECT content FROM page_sections WHERE page = ? AND section = ?",
                    (page, section),
                ).fetchone()
                merged = dict(json.loads(existing["content"])) if existing else {}
                merged.update(content)
                conn.execute(
                    "INSERT INTO page_sections (page, section, content, active, updated_at) "
                    "VALUES (?, ?, ?, 1, datetime('now')) "
                    "ON CONFLICT(page, section) DO UPDATE SET "
                    "content = excluded.content, updated_at = excluded.updated_at",
                    (page, section, json.dumps(merged)),
                )
                written += 1
        report["cms_sections"] = written

        conn.commit()
    finally:
        conn.close()
    return report


# ---------- Orders ----------

def add_order(items, total, customer_email="", status="enquiry", stripe_session_id="", user_id=0):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO orders (items, total, customer_email, status, stripe_session_id, user_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (json.dumps(items), total, customer_email, status, stripe_session_id, user_id or 0),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def set_order_stripe_session(order_id, session_id):
    conn = get_conn()
    conn.execute("UPDATE orders SET stripe_session_id = ? WHERE id = ?", (session_id, order_id))
    conn.commit()
    conn.close()


def list_orders_for_user(user_id, email=None, include_email=False):
    """The orders belonging to an account.

    Orders placed while signed in carry the account id. Orders placed before
    the member had an account are matched on the email address, but only when
    that address is verified: otherwise anybody could sign up with somebody
    else's address and read their orders.
    """
    conn = get_conn()
    if include_email and email:
        rows = conn.execute(
            """SELECT * FROM orders
                WHERE user_id = ? OR (customer_email = ? AND customer_email != '')
                ORDER BY id DESC""",
            (user_id, email),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,)
        ).fetchall()
    conn.close()
    out = []
    for r in rows:
        row = dict(r)
        row["items_parsed"] = json.loads(row.get("items") or "[]")
        out.append(row)
    return out


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

def add_file(path, name="", kind="image", size=0, mime="", source="upload", drive_id="",
             photos_id=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO files (path, name, kind, size, mime, source, drive_id, photos_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (path, name, kind, size, mime, source, drive_id, photos_id),
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


def get_file_by_photos_id(photos_id):
    """Look up an imported Google Photos pick by its persistent media-item id."""
    if not photos_id:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM files WHERE photos_id = ?", (photos_id,)).fetchone()
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


# ---------- Blog ----------

def slugify(text):
    """URL-safe slug from a title."""
    import re, unicodedata
    text = unicodedata.normalize('NFKD', text or 'post').encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return text or 'post'


def list_blog_posts(status=None, limit=None, newest_first=True):
    conn = get_conn()
    sql = "SELECT * FROM blog_posts"
    args = []
    if status is not None:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY " + ("published_at DESC, created_at DESC" if newest_first else "created_at ASC")
    if limit:
        sql += " LIMIT %d" % int(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_blog_post(post_id=None, slug=None):
    conn = get_conn()
    if slug is not None:
        row = conn.execute("SELECT * FROM blog_posts WHERE slug = ?", (slug,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM blog_posts WHERE id = ?", (int(post_id),)).fetchone()
    conn.close()
    return dict(row) if row else None


def _unique_slug(conn, base, exclude_id=None):
    """Ensure slug is unique, appending -2, -3, ... as needed."""
    slug = base
    n = 1
    while True:
        q = "SELECT id FROM blog_posts WHERE slug = ?"
        params = [slug]
        if exclude_id is not None:
            q += " AND id != ?"
            params.append(int(exclude_id))
        if not conn.execute(q, params).fetchone():
            return slug
        n += 1
        slug = "%s-%d" % (base, n)


def save_blog_post(post, publish=False):
    """Insert or update a blog post.

    post dict may contain: id (omit to create), slug, title, summary, body,
    author, image, category, status. When publish=True and status is 'draft',
    flips to 'published' and stamps published_at.
    """
    conn = get_conn()
    is_new = not post.get("id")
    base_slug = slugify(post.get("slug") or post.get("title") or "post")
    ts = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "slug": base_slug,
        "title": post.get("title", "").strip(),
        "summary": post.get("summary", ""),
        "body": post.get("body", ""),
        "author": post.get("author", "").strip(),
        "author_email": (post.get("author_email") or "").strip(),
        "image": post.get("image", ""),
        "category": post.get("category", ""),
        "status": post.get("status", "draft"),
        "published_at": "",
        "user_id": int(post.get("user_id") or 0),
    }

    if is_new:
        data["slug"] = _unique_slug(conn, base_slug)
        status = data["status"]
        if publish and status == "draft":
            data["status"] = "published"
            data["published_at"] = ts
        conn.execute(
            """INSERT INTO blog_posts
               (slug, title, summary, body, author, author_email, image, category, status,
                published_at, user_id, created_at, updated_at)
               VALUES (:slug, :title, :summary, :body, :author, :author_email, :image, :category,
                       :status, :published_at, :user_id, :created_at, :updated_at)""",
            {**data, "created_at": ts, "updated_at": ts},
        )
        post_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    else:
        post_id = int(post["id"])
        existing = conn.execute("SELECT status FROM blog_posts WHERE id = ?", (post_id,)).fetchone()
        old_status = existing["status"] if existing else "draft"
        if publish and old_status == "draft":
            data["status"] = "published"
            data["published_at"] = ts
        else:
            # preserve existing published_at
            cur = conn.execute("SELECT published_at FROM blog_posts WHERE id = ?", (post_id,)).fetchone()
            data["published_at"] = cur["published_at"] if cur else ""
        data["slug"] = _unique_slug(conn, base_slug, exclude_id=post_id)
        data["id"] = post_id
        # An edit must not wipe the submitter's email or the account it came
        # from: the admin form does not carry those fields, so keep whatever
        # is already stored.
        if not data["author_email"]:
            kept = conn.execute(
                "SELECT author_email, user_id FROM blog_posts WHERE id = ?", (post_id,)
            ).fetchone()
            if kept:
                data["author_email"] = kept["author_email"] or ""
                if not data["user_id"]:
                    data["user_id"] = kept["user_id"] or 0
        conn.execute(
            """UPDATE blog_posts SET
               slug=:slug, title=:title, summary=:summary, body=:body, author=:author,
               author_email=:author_email, image=:image, category=:category, status=:status,
               published_at=:published_at, user_id=:user_id, updated_at=:updated_at
               WHERE id=:id""",
            {**data, "updated_at": ts},
        )
    conn.commit()
    conn.close()
    return post_id


def list_blog_posts_by_user(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM blog_posts WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_blog_post(post_id):
    conn = get_conn()
    conn.execute("DELETE FROM blog_posts WHERE id = ?", (int(post_id),))
    conn.commit()
    conn.close()


def list_blog_categories():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT category FROM blog_posts WHERE status='published' AND category != '' ORDER BY category"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


init_db()
