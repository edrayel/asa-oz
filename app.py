"""Asa-OZ — Flask + Jinja2 + SQLite + HTMX application.

Migration of the legacy static site (index/store/product/about/faq/terms/
privacy/contact/admin) into a server-rendered, dynamic app:
  * Products, feedback, waitlist, bookings, contacts, orders + settings in SQLite.
  * Header/footer/cart/booking chrome moved into Jinja partials.
  * Full-page CSS/JS preserved from the originals (static/css/<page>.css).
  * HTMX for cart operations, forms, filters and the admin panel.
  * Stripe Checkout when STRIPE_SECRET_KEY is configured; otherwise orders are
    recorded as enquiries.
"""
import json
import logging
import mimetypes
import os
import sqlite3
import uuid
import base64
import csv
import io
import re
import datetime
from datetime import datetime as _dt
from functools import wraps
from urllib.parse import quote

import stripe
import itsdangerous
from markupsafe import Markup
from flask import (
    Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, send_from_directory, url_for,
)
from werkzeug.utils import secure_filename

import db
import captcha
import cms
import csrf
import drive
import mailer
import notify
import photos
import nh3
import roles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
ADSENSE_PUBLISHER_ID = os.environ.get("ADSENSE_PUBLISHER_ID", "").strip()
# Canonical public URL, resolved in one place so emailed links, Stripe return
# URLs, OG tags and the sitemap can never disagree.
BASE_URL = mailer.base_url()

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY env var is required. Generate one with: "
        "python -c 'import secrets; print(secrets.token_urlsafe(48))'"
    )

app = Flask(__name__)
app.secret_key = SECRET_KEY
# Surface INFO-level app logs (boot diagnostics, "email sent" / "email failed").
# Without this the stdlib default hides them, since nothing else configures
# logging and the root logger sits at WARNING.
app.logger.setLevel(logging.INFO)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_MB", "20")) * 1024 * 1024,
    SEND_FILE_MAX_AGE_DEFAULT=60 * 60 * 24 * 7,  # 1 week for /images, /static
    # Pick up template edits without a restart outside production, so the CMS
    # chrome can be changed while the dev server is running.
    TEMPLATES_AUTO_RELOAD=os.environ.get("FLASK_ENV") != "production",
)


def _static_version(filename):
    """Cache-busting token for a static file, derived from its mtime."""
    try:
        return str(int(os.path.getmtime(os.path.join(app.static_folder or "", filename))))
    except OSError:
        return "0"


def _url_for(endpoint, **values):
    """``url_for`` that versions static asset URLs.

    SEND_FILE_MAX_AGE_DEFAULT is a week, so a changed stylesheet or script must
    get a *different* URL to avoid clients serving a stale copy after a deploy.
    """
    url = url_for(endpoint, **values)
    if endpoint == "static" and values.get("filename"):
        url = f"{url}?v={_static_version(values['filename'])}"
    return url


app.jinja_env.globals["url_for"] = _url_for


def _b64(value):
    """Base64-encode a value so it never sits in the HTML in plain text."""
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


# Templates use this to keep the phone number out of the raw markup.
app.jinja_env.filters["b64"] = _b64


ENDPOINT_PAGE = {
    "index": "home",
    "about": "about",
    "faq": "faq",
    "terms": "terms",
    "privacy": "privacy",
    "policies": "policies",
    "contact": "contact",
    "store": "home",
    "product": "home",
}


def captcha_script():
    """The tag that loads the ALTCHA widget. Served from this site."""
    return Markup(
        '<script async defer type="module" src="%s"></script>'
        % url_for("static", filename="js/altcha.min.js")
    )


def captcha_field():
    """The widget itself: a proof-of-work puzzle the browser solves."""
    # type="native" is the quiet bar that solves itself; auto="onsubmit" means
    # the proof of work is only computed when the form is actually sent.
    return Markup(
        '<altcha-widget class="captcha-widget" challenge="%s" name="altcha" '
        'type="native" auto="onsubmit" '
        'style="--altcha-max-width: 320px; --altcha-border-radius: 12px;"></altcha-widget>'
        % url_for("captcha_challenge")
    )


def _current_cms():
    """Resolved CMS content for the page serving the current request."""
    page = ENDPOINT_PAGE.get(request.endpoint or "")
    if not page:
        return {}
    return cms.resolve(page, db.get_page_sections(page))


# ------------------ cart helpers ------------------

def cart_contents():
    """Return list of {product, qty} derived from the session cart."""
    raw = session.get("cart", {})
    items = []
    for i, q in raw.items():
        p = db.get_product(i)
        if p:
            items.append({**p, "qty": q})
    return items


def cart_count():
    return sum(q for q in session.get("cart", {}).values())


def cart_total():
    return sum(p["price"] * p["qty"] for p in cart_contents())


def save_cart(cart_dict):
    session["cart"] = {k: v for k, v in cart_dict.items() if v > 0}
    session.modified = True


def _settings_snapshot():
    return db.get_settings()


# ------------------ context ------------------
WALL_DIR = os.path.join(BASE_DIR, "images", "wall-of-memories")
FOUNDER_DIR = os.path.join(BASE_DIR, "images", "founder")
# Storage: database only stores relative paths; bytes live under UPLOAD_DIR.
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "instance", "uploads"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif", "avif",
               "pdf", "doc", "docx", "txt", "md", "csv",
               "mp3", "m4a", "wav", "ogg",
               "mp4", "mov", "avi", "webm", "zip"}
IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif", "avif"}

FOUNDER_FILES = [
    "founder/WhatsApp Image 2026-08-04 at 17.17.33.jpeg",
    "founder/WhatsApp Image 2026-08-08 at 10.57.48.jpeg",
    "founder/WhatsApp Image 2026-08-08 at 10.59.58 (1).jpeg",
]


@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory(os.path.join(BASE_DIR, "images"), filename)


@app.route("/media/<path:filename>")
def media(filename):
    """Serve files from UPLOAD_DIR, or stream Drive-backed records live."""
    if filename.startswith("drive/"):
        return _serve_drive_media(filename)
    return send_from_directory(UPLOAD_DIR, filename)


def _stream_drive_with_retry(file_id, max_attempts=3):
    """Stream a Drive file with exponential backoff on transient 5xx/network errors.

    Returns an open ``requests.Response`` (caller must close). Raises
    ``drive.DriveError`` if all attempts fail or a non-transient error is hit.
    """
    import time
    delay = 0.5
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return drive.stream_download(file_id)
        except drive.DriveError as exc:
            last_exc = exc
            msg = str(exc).lower()
            transient = "http 5" in msg or "http 429" in msg or "network" in msg or "timeout" in msg
            if not transient or attempt == max_attempts:
                raise
            app.logger.warning("drive stream retry %d/%d for %s: %s", attempt, max_attempts, file_id, exc)
            time.sleep(delay)
            delay *= 2
    # Defensive — loop always either returns or raises
    raise last_exc  # pragma: no cover


def _serve_drive_media(filename):
    """Stream a registered Drive-backed file (``source='drive'``) to the client.

    The DB record is the source of truth: only paths recorded there are
    proxied, so arbitrary Drive file ids cannot be requested."""
    f = db.get_file_by_path(filename)
    if not f or f.get("source") != "drive" or not f.get("drive_id"):
        abort(404)
    try:
        resp = _stream_drive_with_retry(f["drive_id"])
    except drive.DriveError:
        abort(502)
    headers = {
        "Cache-Control": "public, max-age=300",
        "Content-Length": str(f.get("size") or 0) if f.get("size") else None,
    }
    return Response(
        drive.iter_chunks(resp),
        mimetype=f.get("mime") or resp.headers.get("Content-Type", "application/octet-stream"),
        headers={k: v for k, v in headers.items() if v is not None},
        direct_passthrough=True,
    )


def _wall_files():
    if not os.path.isdir(WALL_DIR):
        return []
    try:
        files = sorted(os.listdir(WALL_DIR))
    except OSError:
        return []
    return ["wall-of-memories/%s" % f
            for f in files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))]


def _seed_home_marquee():
    """Seed the home marquee from images/wall-of-memories/ once (fresh DB).

    Only runs when the marquee section has never been saved; afterwards the
    CMS is the single source of truth for marquee photos."""
    if "marquee" in db.get_page_sections("home"):
        return
    photos = [{"image": "/images/" + "/".join(quote(p, safe="") for p in rel.split("/"))}
              for rel in _wall_files()]
    db.save_page_section("home", "marquee", {"rows": "3", "images": photos}, active=True)


def _wall_moments():
    """Marquee + wall-of-memories photo urls from the home CMS (single source)."""
    marquee = cms.resolve("home", db.get_page_sections("home")).get("marquee") or {}
    urls = [img.get("image", "").strip() for img in (marquee.get("images") or [])]
    return [u for u in urls if u]


# ------------------ file storage ------------------

def _upload_abs(rel):
    """Map a DB-stored relative path to an absolute path under UPLOAD_DIR.

    Only well-formed relative names are accepted (no absolute paths, no ..)."""
    if not rel or rel.startswith(("/", "\\")) or ".." in rel.split("/"):
        raise ValueError("unsafe path: %r" % rel)
    rel = rel.replace("\\", "/")
    path = os.path.abspath(os.path.join(UPLOAD_DIR, rel))
    if not path.startswith(os.path.abspath(UPLOAD_DIR) + os.sep):
        raise ValueError("unsafe path: %r" % rel)
    return path


def _ext_of(filename):
    return (filename.rsplit(".", 1)[1] if "." in filename else "").lower()


def _media_url(rel):
    return url_for("media", filename=rel)


def _size_fmt(n):
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / (1024 * 1024))
    if n >= 1024:
        return "%.0f KB" % (n / 1024)
    return "%d B" % n


def _new_rel_path(name):
    """`<uuid8>/<safe-name>` relative path into UPLOAD_DIR."""
    ext = _ext_of(name)
    stem = secure_filename(os.path.splitext(name)[0])[:80] or "file"
    for _ in range(5):
        rel = "%s/%s.%s" % (uuid.uuid4().hex[:8], stem, ext) if ext else "%s/%s" % (uuid.uuid4().hex[:8], stem)
        if not os.path.exists(_upload_abs(rel)):
            return rel
    raise ValueError("could not allocate a unique path")


def _save_stream(stream, rel):
    """Stream a binary source to disk under UPLOAD_DIR; enforces the size cap."""
    dest = _upload_abs(rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    size = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise ValueError("file exceeds %d MB" % MAX_UPLOAD_MB)
                f.write(chunk)
    except ValueError:
        _discard_partial(rel)
        raise
    except OSError as exc:
        # A full disk or a broken connection must not leave a truncated file
        # that looks like a complete upload to the media library.
        _discard_partial(rel)
        raise OSError("could not write %s: %s" % (rel, exc))
    return size


def _discard_partial(rel):
    """Remove a half-written upload; a missing file is not an error."""
    if not rel:
        return
    try:
        os.remove(_upload_abs(rel))
    except OSError:
        pass


def _store_upload(file_storage):
    """Persist a Werkzeug FileStorage; returns (rel, kind, size, mime)."""
    name = secure_filename(file_storage.filename or "")
    if not name:
        raise ValueError("missing filename")
    ext = _ext_of(name)
    if ext not in ALLOWED_EXT:
        raise ValueError("file type .%s is not allowed" % ext)
    rel = _new_rel_path(name)
    size = _save_stream(file_storage.stream, rel)
    kind = "image" if ext in IMAGE_EXT else "document"
    mime = file_storage.mimetype or mimetypes.guess_type(name)[0] or ""
    return rel, kind, size, mime


def _flat_cms(page_name):
    """Resolve a CMS page and flatten its sections into one dict of field values."""
    out = {}
    for section in cms.resolve(page_name, db.get_page_sections(page_name)).values():
        out.update({k: v for k, v in section.items() if k != "active"})
    return out


@app.context_processor
def inject_globals():
    request_path = request.path if request else "/"
    return {
        "base_url": BASE_URL,
        "today": _dt.now().strftime("%d %B %Y"),
        "settings": _settings_snapshot(),
        "cart_count": cart_count(),
        "cart_total": cart_total(),
        "cart_items": cart_contents(),
        "marquee_images": _wall_moments(),
        "founder_photos": FOUNDER_FILES,
        "store_types": db.list_product_types(active_only=True),
        "cms": _current_cms(),
        "cms_pages": cms.PAGES,
        "cms_site": _flat_cms("sitewide"),
        "cms_store": _flat_cms("store"),
        "cms_booking": _flat_cms("booking"),
        "csrf_input": csrf.render_input,
        "og_image_url": _og_image_url(request_path),
        "adsense_publisher_id": ADSENSE_PUBLISHER_ID,
        "current_user": current_user(),
        "can": can,
        "roles": roles,
        "captcha_script": captcha_script,
        "captcha_field": captcha_field,
    }


def _og_image_url(request_path):
    """Resolve a per-page OG image. Falls back to the default.

    Per-page override lives in the page's CMS hero section as an `image` field.
    The default is /static/images/og-default.jpg (ships in static/images/).
    """
    page = ENDPOINT_PAGE.get(request.endpoint or "")
    stored = db.get_page_sections(page) if page else {}
    hero = (stored or {}).get("hero", {}) or {}
    img = (hero.get("image") or "").strip()
    if img:
        if img.startswith("http://") or img.startswith("https://") or img.startswith("/"):
            return img
        return f"{BASE_URL}/{img.lstrip('/')}"
    return f"{BASE_URL}/static/images/og-default.svg"


# ------------------ public pages ------------------
@app.route("/")
def index():
    return render_template("index.html",
                           products=db.list_products(active_only=True),
                           # More than three keeps the stories band useful: the
                           # template turns four or more into a scrollable rail.
                           blog_posts=db.list_blog_posts(status="published", limit=8),
                           member_testimonials=db.list_testimonials(status="approved"))


# -------------------- Blog --------------------

@app.route("/blog")
def blog():
    posts = db.list_blog_posts(status="published", limit=12)
    blog_cms = cms.resolve("blog", db.get_page_sections("blog"))
    return render_template("blog.html", posts=posts, blog_cms=blog_cms,
                           category=request.args.get("category"),
                           categories=db.list_blog_categories())


@app.route("/blog/<slug>")
def blog_post(slug):
    post = db.get_blog_post(slug=slug)
    if not post or post["status"] != "published":
        abort(404)
    others = [p for p in db.list_blog_posts(status="published", limit=4) if p["id"] != post["id"]]
    return render_template("blog_post.html", post=post, others=others[:3])


@app.route("/blog/submit", methods=["GET", "POST"])
def blog_submit():
    """Public endpoint for members to submit a story for review."""
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        problem = captcha.check_request()
        if problem:
            return render_template("blog_submit.html", error=problem, form=request.form), 400
        if not request.form.get("title", "").strip() or not request.form.get("body", "").strip():
            return render_template("blog_submit.html", error="Title and story are required.",
                                   form=request.form), 400
        author_email = (request.form.get("author_email") or "").strip()
        member = current_user()
        db.save_blog_post({
            "title": request.form["title"],
            "summary": request.form.get("summary", ""),
            "body": request.form["body"],
            "author": request.form.get("author", "").strip()
                      or (member["full_name"] or member["username"] if member else "Anonymous member"),
            "author_email": author_email or (member["email"] if member else ""),
            "image": request.form.get("image", ""),
            "category": request.form.get("category", "Member stories"),
            "status": "draft",
            "user_id": member["id"] if member else 0,
        })
        notify.notify_story(request.form["title"], request.form.get("author", ""), author_email)
        if author_email and db.setting_bool("email_story_ack", "1"):
            mailer.send("story_ack", author_email, {"story_title": request.form["title"]})
        return render_template("blog_submitted.html")
    member = current_user()
    form = {}
    if member:
        form = {"author": member["full_name"] or member["username"], "author_email": member["email"]}
    return render_template("blog_submit.html", form=form)


@app.route("/confirm/<token>")
def email_confirm(token):
    """Double opt-in landing page: confirm a newsletter subscription."""
    existing = db.get_subscriber_by_token(token)
    first_time = bool(existing) and existing["status"] != "confirmed"
    sub = db.confirm_subscriber(token) if existing else None
    if sub and first_time and db.setting_bool("email_welcome", "1"):
        mailer.send("newsletter_welcome", sub["email"], {
            "unsubscribe_url": BASE_URL + url_for("email_unsubscribe", token=sub["token"]),
        })
    return render_template("email_confirmed.html", subscriber=sub, confirmed=bool(sub))


@app.route("/unsubscribe/<token>", methods=["GET", "POST"])
def email_unsubscribe(token):
    """Unsubscribe landing page.

    GET only *offers* the unsubscribe: a mail scanner, security proxy or
    link preview that follows the link in an incoming email must not be able
    to opt somebody out. POST performs it (one-click unsubscribe posts to
    this URL too, RFC 8058).
    """
    if request.method == "POST":
        sub = db.unsubscribe_by_token(token)
        if not sub:
            return render_template("email_unsubscribed.html", subscriber=None, done=False, pending=False), 404
        return render_template("email_unsubscribed.html", subscriber=sub, done=True, pending=False)
    sub = db.get_subscriber_by_token(token)
    return render_template("email_unsubscribed.html", subscriber=sub, done=False, pending=bool(sub))


@app.route("/api/wall")
def api_wall():
    return jsonify({"images": _wall_moments()})


@app.route("/health")
def health():
    """Real liveness probe — exercises DB and (if configured) Drive.

    Returns 200 with a JSON status report when all subsystems respond, or
    503 when anything is degraded. Safe to use as a Render healthcheck.
    """
    report = {"status": "ok", "db": False}
    http_status = 200
    # 1. Database
    try:
        db.get_conn().execute("SELECT 1").fetchone()
        report["db"] = True
    except Exception as exc:  # noqa: BLE001
        report["db"] = False
        report["db_error"] = str(exc)
        report["status"] = "degraded"
        http_status = 503
    # 2. Drive (only if configured)
    if drive.is_configured():
        report["drive"] = False
        folder = drive.root_folder_id() or "root"
        try:
            drive.get_metadata(folder)
            report["drive"] = True
        except drive.DriveError as exc:
            report["drive"] = False
            report["drive_error"] = str(exc)
            report["status"] = "degraded"
            http_status = 503
    return jsonify(report), http_status


@app.route("/ping")
def ping():
    """Cheap no-op alias of /health for keep-alive pings."""
    return jsonify({"status": "ok"}), 200


# ------------------ SEO: robots / sitemap / ads ------------------

@app.route("/ads.txt")
def ads_txt():
    """Serve ads.txt at the IAB-required domain root."""
    return send_from_directory(app.static_folder, "ads.txt", mimetype="text/plain")


@app.route("/robots.txt")
def robots():
    return Response(render_template("robots.txt"), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    """Generate a sitemap of all public pages + active dynamic pages."""
    today = _dt.now().strftime("%Y-%m-%d")
    static_routes = [
        ("/", 1.0, today),
        ("/about", 0.8, today),
        ("/faq", 0.7, today),
        ("/terms", 0.5, today),
        ("/privacy", 0.5, today),
        ("/policies", 0.5, today),
        ("/contact", 0.8, today),
    ]
    if db.get_settings().get("show_store", "0") == "1":
        static_routes.insert(2, ("/store", 0.7, today))
    urls = []
    for path, priority, lastmod in static_routes:
        urls.append({
            "loc": f"{BASE_URL}{path}",
            "lastmod": lastmod,
            "priority": f"{priority:.1f}",
        })
    # Dynamic CMS pages
    try:
        for p in db.list_dynamic_pages(active_only=True):
            urls.append({
                "loc": f"{BASE_URL}/page/{p['slug']}",
                "lastmod": (p.get("updated_at") or today)[:10],
                "priority": "0.6",
            })
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("sitemap: dynamic page list failed: %s", exc)

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{u['loc']}</loc>")
        xml_lines.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        xml_lines.append(f"    <priority>{u['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")
    return Response("\n".join(xml_lines), mimetype="application/xml")


@app.route("/store")
def store():
    if _store_off():
        abort(404)
    type_filter = request.args.get("type", "all")
    products = db.list_products(active_only=True)
    return render_template("store.html", products=products, type_filter=type_filter)


@app.route("/store/partial")
def store_partial():
    if _store_off():
        abort(404)
    type_filter = request.args.get("type", "all")
    products = db.list_products(active_only=True)
    return render_template("partials/store_grid.html", products=products, type_filter=type_filter)


@app.route("/product/<product_id>")
def product(product_id):
    if _store_off():
        abort(404)
    product = db.get_product(product_id)
    if not product:
        abort(404)
    others = [p for p in db.list_products(active_only=True) if p["id"] != product_id]
    similar = [p for p in others if p["type"] == product["type"]] or others[:3]
    return render_template("product.html", product=product, similar=similar[:3])


@app.route("/about")
def about():
    return render_template("about.html",
                           products=db.list_products(active_only=True),
                           home_cms=cms.resolve("home", db.get_page_sections("home")))


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/policies")
def policies():
    return render_template("policies.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# ------------------ dynamic pages ------------------

@app.route("/page/<slug>")
def dynamic_page(slug):
    page = db.get_dynamic_page(slug)
    if not page or not page.get("active"):
        abort(404)
    stored = db.get_page_sections(slug)
    # Build a generic schema from stored sections so the template can render them
    sections = []
    for key, data in stored.items():
        sections.append({
            "key": key,
            "label": key.replace("_", " ").title(),
            "active": data.get("active", True),
            "content": data.get("content", {}),
        })
    return render_template("dynamic_page.html", page=page, sections=sections)


# ------------------ captcha ------------------
@app.route("/captcha/challenge")
def captcha_challenge():
    """A fresh proof-of-work challenge for the ALTCHA widget.

    No account, no API key: the widget solves a small puzzle in the
    browser and the answer is checked on the server.
    """
    if not captcha.enabled():
        return jsonify({"algorithm": captcha.ALGORITHM, "challenge": "", "maxNumber": 0,
                         "salt": "", "signature": ""})
    return jsonify(captcha.create_challenge())


# ------------------ forms (HTMX) ------------------
@app.route("/waitlist", methods=["POST"])
@csrf.require_csrf
def waitlist():
    email = (request.form.get("email") or "").strip().lower()
    problem = captcha.check_request()
    if problem:
        return '<p class="msg" style="color:#b5482c;" role="status">%s</p>' % problem
    if not email or "@" not in email:
        return '<p class="msg" style="color:#b5482c;" role="status">Please enter a valid email address.</p>'
    ok = db.add_waitlist(email, request.form.get("source", ""))
    if ok:
        notify.notify_waitlist(email, request.form.get("source", ""))
        return '<p class="msg" role="status">Thank you. You&rsquo;ll be among the first to hear about new offers and trips.</p>'
    return '<p class="msg" style="color:#b5482c;" role="status">You&rsquo;re already on the list — we&rsquo;ll be in touch.</p>'


@app.route("/booking", methods=["POST"])
@csrf.require_csrf
def booking():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    date = (request.form.get("date") or "").strip()
    time = (request.form.get("time") or "").strip()
    errors = []
    if not name:
        errors.append("name")
    if not email or "@" not in email:
        errors.append("email")
    if not date:
        errors.append("date")
    if not time:
        errors.append("time")
    if errors:
        return jsonify({"ok": False, "errors": errors}), 422

    db.add_booking({
        "name": name,
        "email": email,
        "phone": (request.form.get("phone") or "").strip(),
        "date": date,
        "time": time,
        "message": (request.form.get("message") or "").strip(),
    })
    notice = {
        "name": name, "email": email,
        "phone": (request.form.get("phone") or "").strip(),
        "date": date, "time": time,
        "message": (request.form.get("message") or "").strip(),
    }
    notify.notify_booking(notice)
    if db.setting_bool("email_booking_confirm", "1"):
        mailer.send("booking_confirm", email, {"booking": notice})
    return render_template("partials/booking_confirm.html")


@app.route("/feedback", methods=["POST"])
@csrf.require_csrf
def feedback():
    text = (request.form.get("text") or "").strip()
    category = (request.form.get("category") or "").strip()
    problem = captcha.check_request()
    if problem:
        return '<p class="feedback-msg" style="color:#b5482c;" role="status">%s</p>' % problem
    if not text:
        return '<p class="feedback-msg" style="color:#b5482c;" role="status">Please write a little something first.</p>'
    db.add_feedback(category, text)
    notify.notify_feedback(category, text)
    return '<p class="feedback-msg" role="status">Thank you. Your feedback has been saved.</p>'


@app.route("/contact-msg", methods=["POST"])
@csrf.require_csrf
def contact_msg():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    message = (request.form.get("message") or "").strip()
    problem = captcha.check_request()
    if problem:
        return '<p class="form-msg" style="color:#b5482c;" role="status">%s</p>' % problem
    if not all([name, email, message]):
        return '<p class="form-msg" style="color:#b5482c;" role="status">Please fill in every field.</p>'
    db.add_contact(name, email, message)
    notify.notify_contact(name, email, message)
    if db.setting_bool("email_contact_ack", "1"):
        mailer.send("contact_ack", email, {"name": name, "message": message})
    return '<p class="form-msg" role="status">Thank you — your message has been saved. We&rsquo;ll reply to you shortly.</p>'


@app.route("/journey", methods=["POST"])
@csrf.require_csrf
def journey_subscribe():
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    journey_stage = (request.form.get("journey_stage") or "interest").strip()
    source = (request.form.get("source") or "").strip()
    problem = captcha.check_request()
    if problem:
        return render_template("partials/journey_confirm.html", variant="error",
                               title="We could not check that you are human",
                               body=problem,
                               hint="Please try again in a moment.")
    if not email or "@" not in email:
        # Rendered as a card, not a caption: the old one-line <p> was small
        # and italic, so visitors assumed nothing had happened.
        return render_template("partials/journey_confirm.html", variant="error",
                               title="That email address isn't valid",
                               body="Please enter a valid email address and try again.",
                               hint="Check for a missing @ or a typo.")

    sub = db.subscribe_journey(email, name, journey_stage, source)
    if sub["is_new"]:
        notify.notify_subscriber(sub["email"], name, source)

    if sub["status"] == "pending":
        if db.setting_bool("email_confirm", "1"):
            mailer.send("newsletter_confirm", sub["email"], {
                "confirm_url": BASE_URL + url_for("email_confirm", token=sub["token"]),
            })
        return render_template("partials/journey_confirm.html", variant="pending",
                               title="Nearly there",
                               body="Check your inbox and click the link to confirm your email.",
                               hint="If it hasn't arrived in a minute or two, check your spam folder.")

    return render_template("partials/journey_confirm.html", variant="already",
                           title="You're already on the list",
                           body="We'll be in touch. Thanks for being with us early.")


# ------------------ cart (HTMX) ------------------
# Cart and checkout are store surfaces: when the store is hidden they 404,
# so nobody can order a shop that is not open yet.
def _store_off():
    return db.get_settings().get("show_store", "0") == "0"


@app.route("/cart/drawer")
def cart_drawer_view():
    if _store_off():
        # The store is closed: answer with an empty drawer instead of a 404 so
        # a stale tab (or the shell) does not spam the error log.
        return ""
    return cart_drawer()


@app.route("/cart/add", methods=["POST"])
@csrf.require_csrf
def cart_add():
    if _store_off():
        abort(404)
    product_id = request.form.get("id")
    p = db.get_product(product_id)
    if not p:
        abort(404)
    cart = session.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    save_cart(cart)
    return cart_drawer()


@app.route("/cart/qty", methods=["POST"])
@csrf.require_csrf
def cart_qty():
    if _store_off():
        abort(404)
    product_id, delta = request.form.get("id"), int(request.form.get("delta", 0))
    cart = session.get("cart", {})
    cart[product_id] = max(0, cart.get(product_id, 0) + delta)
    save_cart(cart)
    return cart_drawer()


@app.route("/cart/remove", methods=["POST"])
@csrf.require_csrf
def cart_remove():
    if _store_off():
        abort(404)
    product_id = request.form.get("id")
    cart = session.get("cart", {})
    cart.pop(product_id, None)
    save_cart(cart)
    return cart_drawer()


def cart_drawer(checkout_email="", error=""):
    return render_template(
        "partials/cart_drawer.html",
        cart_items=cart_contents(),
        cart_count=cart_count(),
        cart_total=cart_total(),
        checkout_email=checkout_email,
        error=error,
    )


def _send_order_confirm(order_id, items, total, email):
    """Confirmation for an order that is complete as an enquiry (nothing to pay)."""
    if not db.setting_bool("email_order_confirm", "1"):
        return False
    return mailer.send("order_confirm", email, {
        "order_items": items,
        "order_total": total,
        "order_ref": "A-%d" % order_id,
    })


# ------------------ checkout ------------------
_ORDER_SALT = "asa-oz-order"


def _order_token(order_id):
    """Sign an order id so only the browser that placed it can read it."""
    return itsdangerous.URLSafeTimedSerializer(SECRET_KEY, salt=_ORDER_SALT).dumps(str(order_id))


def _authorised_order(order_id, token):
    """Return the order id the caller is allowed to see, or None.

    An order is authorised when the URL carries a valid signature, or when
    the order was placed in this browser session.
    """
    if not order_id:
        return None
    if token:
        try:
            value = itsdangerous.URLSafeTimedSerializer(SECRET_KEY, salt=_ORDER_SALT).loads(
                token, max_age=60 * 60 * 24 * 30)
        except (itsdangerous.BadSignature, itsdangerous.SignatureExpired):
            value = None
        if value is not None and str(order_id) == str(value):
            return order_id
    if session.get("order_id") == order_id:
        return order_id
    return None


@app.route("/checkout", methods=["POST"])
@csrf.require_csrf
def checkout():
    if _store_off():
        abort(404)
    items = cart_contents()
    if not items:
        abort(400)
    total = cart_total()

    email = (request.form.get("email") or "").strip()
    if not email or "@" not in email:
        return cart_drawer(
            checkout_email=email,
            error="Please add an email address so we can confirm your order.",
        ), 400

    member = current_user()
    member_id = member["id"] if member else 0

    if not STRIPE_SECRET:
        order_id = db.add_order(items, total, customer_email=email, user_id=member_id)
        notify.notify_order(items, total, customer_email=email)
        _send_order_confirm(order_id, items, total, email)
        session["order_id"] = order_id
        return redirect(url_for("checkout_success", order_id=order_id, token=_order_token(order_id)))

    stripe.api_key = STRIPE_SECRET
    line_items = [
        {
            "price_data": {
                "currency": "eur",
                "product_data": {"name": it["name"], "description": it["desc"][:200]},
                "unit_amount": it["price"] * 100,
            },
            "quantity": it["qty"],
        }
        for it in items
        if it["price"] > 0
    ]
    if not line_items:
        order_id = db.add_order(items, total, customer_email=email, user_id=member_id)
        notify.notify_order(items, total, customer_email=email)
        _send_order_confirm(order_id, items, total, email)
        session["order_id"] = order_id
        return redirect(url_for("checkout_success", order_id=order_id, token=_order_token(order_id)))

    # Priced items go to Stripe, so payment is not complete yet. No confirmation
    # is sent here: mailing "order confirmed" for an unpaid cart would be wrong.
    # A receipt belongs on the payment webhook, which is still to be built.
    order_id = db.add_order(items, total, customer_email=email, status="pending",
                            user_id=member_id)
    notify.notify_order(items, total, customer_email=email)
    token = _order_token(order_id)
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=BASE_URL + url_for("checkout_success", order_id=order_id, token=token),
            cancel_url=BASE_URL + url_for("checkout_cancel", order_id=order_id, token=token),
        )
    except Exception as exc:  # pragma: no cover - network/Stripe errors
        app.logger.error("Stripe session error: %s", exc)
        db.set_order_status(order_id, "enquiry")
        session["order_id"] = order_id
        return redirect(url_for("checkout_success", order_id=order_id, token=token))

    db.set_order_stripe_session(order_id, checkout_session.id)
    db.set_order_status(order_id, "pending")
    session["order_id"] = order_id
    return redirect(checkout_session.url)


@app.route("/checkout/cancel")
def checkout_cancel():
    order_id = request.args.get("order_id", type=int)
    if _authorised_order(order_id, request.args.get("token")):
        db.set_order_status(order_id, "cancelled")
    return render_template("checkout_cancel.html", cart_count=cart_count())


@app.route("/checkout/success")
def checkout_success():
    order_id = request.args.get("order_id", type=int)
    order_id = _authorised_order(order_id, request.args.get("token"))
    order = db.get_order(order_id) if order_id else None
    if not order:
        abort(404)
    items = json.loads(order["items"] or "[]")
    session.pop("cart", None)
    return render_template("checkout_success.html", order=items, total=order["total"])


# ------------------ admin ------------------
def current_user():
    """The signed-in user, re-validated against the database.

    Returns None when there is no session, when the account has been
    deleted or suspended, or when ``auth_version`` moved on (a role change
    or a password reset ends every live session for that account).
    """
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.get_user(user_id)
    if not user or user.get("status") != "active":
        session.pop("user_id", None)
        session.pop("admin", None)
        session.pop("auth_version", None)
        return None
    if session.get("auth_version") != user.get("auth_version"):
        session.pop("user_id", None)
        session.pop("admin", None)
        session.pop("auth_version", None)
        return None
    return user


def can(permission):
    """True when the signed-in user holds ``permission``."""
    user = current_user()
    if not user:
        return False
    return roles.has_permission(user["role"], permission)


def sign_in(user):
    session["user_id"] = user["id"]
    session["auth_version"] = user["auth_version"]
    session["admin"] = user["username"]
    session.modified = True
    db.touch_login(user["id"])


def sign_out():
    session.pop("user_id", None)
    session.pop("admin", None)
    session.pop("auth_version", None)
    session.modified = True


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST" and not csrf.validate():
        abort(400, "CSRF token missing or invalid")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        ip = ip.split(",")[0].strip()
        problem = captcha.check_request()
        if problem:
            return render_template("admin/login.html", error=problem)
        wait = db.login_lockout(username, ip)
        if wait:
            return render_template(
                "admin/login.html",
                error=f"Too many failed attempts. Try again in {max(1, wait // 60)} minute(s).",
            )
        user = db.verify_user(username, password)
        if user:
            db.clear_login_failures(username, ip)
            sign_in(user)
            db.log_action(user["id"], user["username"], "sign-in", user["username"], user["role"])
            return redirect(url_for("admin_dashboard"))
        db.record_login_failure(username, ip)
        db.log_action(None, username, "sign-in-failed", username, ip)
        return render_template("admin/login.html", error="Invalid credentials")
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.route("/admin/logout", methods=["POST"])
@csrf.require_csrf
def admin_logout():
    user = current_user()
    if user:
        db.log_action(user["id"], user["username"], "sign-out", user["username"], "")
    sign_out()
    return redirect(url_for("admin_login"))


def admin_required(fn):
    """Require a signed-in user, and a role that may use this view.

    The permission is looked up from ``roles.ROUTE_PERMISSIONS`` by endpoint,
    so a view that is not in the map is superadmin-only: new admin pages fail
    closed instead of being open to every role.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("admin_login"))
        permission = roles.permission_for(request.endpoint)
        if permission and not roles.has_permission(user["role"], permission):
            db.log_action(user["id"], user["username"], "denied", request.endpoint or "", user["role"])
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


@app.route("/admin")
@admin_required
def admin_dashboard():
    """Overview. Only the numbers this role is allowed to see are counted."""
    user = current_user()
    role = user["role"]

    def allow(permission):
        return roles.has_permission(role, permission)

    stats = {}
    if allow("audience.feedback"):
        stats["feedback"] = len(db.list_feedback())
        stats["recent_feedback"] = db.list_feedback()[:5]
    if allow("audience.waitlist"):
        stats["waitlist"] = len(db.list_waitlist())
        stats["recent_waitlist"] = db.list_waitlist()[:5]
    if allow("audience.journey"):
        stats["journey"] = len(db.list_journey_subscribers())
    if allow("audience.bookings"):
        stats["bookings"] = len(db.list_bookings())
    if allow("audience.contacts"):
        stats["contacts"] = len(db.list_contacts())
    if allow("shop.orders"):
        stats["orders"] = len(db.list_orders())
    if allow("shop.products"):
        stats["products"] = len(db.list_products())
    if allow("media.files"):
        stats["files"] = len(db.list_files())
    return render_template("admin/dashboard.html", stats=stats, can_export=allow("system.export"))


@app.route("/admin/products")
@admin_required
def admin_products():
    files = []
    for f in db.list_files():
        if f["kind"] == "image":
            files.append({"id": f["id"], "name": f["name"], "url": _media_url(f["path"])})
    return render_template("admin/products.html", products=db.list_products(),
                           media=files, product_types=db.list_product_types(active_only=False))


@app.route("/admin/products/new", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_products_new():
    existing = db.list_products()
    used_ids = {p["id"] for p in existing}
    p_id = (request.form.get("id") or "").strip().lower().replace(" ", "-")
    if p_id in used_ids or not p_id:
        base = p_id or "product"
        i = 1
        while f"{base}-{i}" in used_ids:
            i += 1
        p_id = f"{base}-{i}"
    db.save_product({
        "id": p_id,
        "name": request.form.get("name", "New product"),
        "type": request.form.get("type", "physical"),
        "price": int(request.form.get("price", 0) or 0),
        "img": request.form.get("img", ""),
        "desc": request.form.get("desc", ""),
        "active": int("active" in request.form),
        "sort": int(request.form.get("sort", 0) or 0),
    })
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<product_id>", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_product_update(product_id):
    p = db.get_product(product_id) or {}
    db.save_product({
        "id": product_id,
        "name": request.form.get("name", p.get("name", "")),
        "type": request.form.get("type", p.get("type", "physical")),
        "price": request.form.get("price", p.get("price", 0)),
        "img": request.form.get("img", p.get("img", "")),
        "desc": request.form.get("desc", p.get("desc", "")),
        "active": int("active" in request.form),
        "sort": request.form.get("sort", p.get("sort", 0)),
    })
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<product_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_product_delete(product_id):
    db.delete_product(product_id)
    return redirect(url_for("admin_products"))


# ------------------ admin: files ------------------

@app.route("/admin/files")
@admin_required
def admin_files():
    files = []
    for f in db.list_files():
        f["url"] = _media_url(f["path"])
        f["size_label"] = _size_fmt(f["size"])
        files.append(f)
    return render_template("admin/files.html", files=files, max_mb=MAX_UPLOAD_MB)


@app.route("/admin/files/upload", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_files_upload():
    uploaded = request.files.getlist("files")
    if not uploaded:
        flash("No files received.", "error")
        return redirect(url_for("admin_files"))
    errors, added = [], 0
    for fs in uploaded:
        if not fs or not fs.filename:
            continue
        try:
            rel, kind, size, mime = _store_upload(fs)
            db.add_file(path=rel, name=secure_filename(fs.filename), kind=kind,
                        size=size, mime=mime, source="upload")
            added += 1
        except ValueError as exc:
            errors.append("%s: %s" % (fs.filename, exc))
        except (OSError, sqlite3.Error) as exc:
            # One bad file must not fail the whole batch.
            errors.append("%s: %s" % (fs.filename, exc))
    if errors:
        flash("; ".join(errors), "error")
    if added:
        flash("%d file(s) uploaded." % added)
    return redirect(url_for("admin_files"))


@app.route("/admin/files/<int:file_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_file_delete(file_id):
    f = db.get_file(file_id)
    if not f:
        abort(404)
    try:
        if f.get("source") != "drive":
            path = _upload_abs(f["path"])
            if os.path.isfile(path):
                os.remove(path)
        db.delete_file(file_id)
        flash("Deleted %s." % (f["name"] or f["path"]))
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_files"))


# ------------------ admin: blog ------------------

@app.route("/admin/blog")
@admin_required
def admin_blog():
    status = request.args.get("status")
    status_filter = status if status in ("draft", "published") else None
    posts = db.list_blog_posts(status=status_filter)
    return render_template("admin/blog.html", posts=posts, status_filter=status_filter)


@app.route("/admin/blog/new", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_blog_new():
    if request.method == "POST":
        post_id = db.save_blog_post({
            "title": request.form.get("title", ""),
            "slug": request.form.get("slug", ""),
            "summary": request.form.get("summary", ""),
            "body": request.form.get("body", ""),
            "author": request.form.get("author", ""),
            "image": request.form.get("image", ""),
            "category": request.form.get("category", ""),
            "status": request.form.get("status", "draft"),
        }, publish=("publish" in request.form))
        return redirect(url_for("admin_blog_edit", post_id=post_id))
    return render_template("admin/blog_edit.html", post=None, form={})


@app.route("/admin/blog/<int:post_id>", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_blog_edit(post_id):
    post = db.get_blog_post(post_id=post_id)
    if not post:
        abort(404)
    author_verified = db.author_email_verified(post.get("user_id"))
    if request.method == "POST":
        if "publish" in request.form and not author_verified:
            flash("This story came from an account whose email is not confirmed, so it "
                  "cannot be published under that name yet.", "error")
            return redirect(url_for("admin_blog_edit", post_id=post_id))
        db.save_blog_post({
            "id": post_id,
            "title": request.form.get("title", post["title"]),
            "slug": request.form.get("slug", post["slug"]),
            "summary": request.form.get("summary", post["summary"]),
            "body": request.form.get("body", post["body"]),
            "author": request.form.get("author", post["author"]),
            "image": request.form.get("image", post["image"]),
            "category": request.form.get("category", post["category"]),
            "status": request.form.get("status", post["status"]),
        }, publish=("publish" in request.form))
        return redirect(url_for("admin_blog_edit", post_id=post_id))
    return render_template("admin/blog_edit.html", post=post, form=post,
                           author_verified=author_verified)


@app.route("/admin/blog/<int:post_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_blog_delete(post_id):
    db.delete_blog_post(post_id)
    return redirect(url_for("admin_blog"))


# ------------------ admin: Google Drive ------------------

@app.route("/admin/drive")
@admin_required
def admin_drive():
    folder = (request.args.get("folder") or "").strip()
    page = request.args.get("page") or ""
    ctx = {"drive_ok": False, "setup_needed": True, "files": [], "folder": folder,
           "up_folder": "", "folder_name": "", "root_label": "My Drive",
           "next_page": None, "prev_page": None}
    if not drive.is_configured():
        return render_template("admin/drive.html", **ctx)
    try:
        files, next_page = drive.list_folder(folder_id=folder or None, page_token=page or None)
        ctx.update(drive_ok=True, setup_needed=False, files=files, next_page=next_page,
                   prev_page=page or None, root_label=drive.root_label())
        if folder:
            meta = drive.get_metadata(folder)
            ctx["folder_name"] = meta.get("name") or folder
            parents = meta.get("parents") or []
            ctx["up_folder"] = parents[0] if parents else ""
    except drive.DriveError as exc:
        ctx["setup_needed"] = False
        flash("Google Drive error: %s" % exc, "error")
    return render_template("admin/drive.html", **ctx)


@app.route("/admin/drive/import", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_drive_import():
    """Download a Drive file into UPLOAD_DIR and record it (source=drive-import)."""
    file_id = (request.form.get("file_id") or "").strip()
    back = request.form.get("back") or url_for("admin_drive")
    if not file_id:
        flash("Missing Drive file id.", "error")
        return redirect(back)
    resp = None
    rel = None
    try:
        meta = drive.get_metadata(file_id)
        if meta.get("is_folder") or not meta.get("is_binary"):
            raise drive.DriveError("Google-native or folder items cannot be imported")
        ext = _ext_of(meta.get("name") or "")
        if ext not in ALLOWED_EXT:
            raise drive.DriveError("file type .%s is not allowed" % ext)
        rel = _new_rel_path(meta.get("name") or "file")
        resp = drive.stream_download(file_id)
        size = _save_stream(resp.raw, rel)
        kind = "image" if ext in IMAGE_EXT else "document"
        mime = meta.get("mimeType") or resp.headers.get("Content-Type", "")
        db.add_file(path=rel, name=meta.get("name") or rel, kind=kind, size=size,
                    mime=mime, source="drive-import", drive_id=file_id)
        flash("Imported “%s” from Drive." % (meta.get("name") or "file"))
    except (drive.DriveError, ValueError) as exc:
        flash("Import failed: %s" % exc, "error")
        _discard_partial(rel)
    except sqlite3.Error as exc:
        flash("Import failed: could not record file (%s)" % exc, "error")
        _discard_partial(rel)
    finally:
        if resp is not None:
            resp.close()
    return redirect(back)


@app.route("/admin/drive/link", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_drive_link():
    """Register a Drive file that is streamed live through /media/drive/..."""
    file_id = (request.form.get("file_id") or "").strip()
    back = request.form.get("back") or url_for("admin_drive")
    if not file_id:
        flash("Missing Drive file id.", "error")
        return redirect(back)
    try:
        meta = drive.get_metadata(file_id)
        if meta.get("is_folder") or not meta.get("is_binary"):
            raise drive.DriveError("Google-native or folder items cannot be linked")
        name = meta.get("name") or "file"
        rel = "drive/%s/%s" % (file_id, secure_filename(name) or "file")
        if db.get_file_by_path(rel):
            flash("“%s” is already linked." % name, "error")
            return redirect(back)
        mime = meta.get("mimeType") or ""
        kind = "image" if mime.startswith("image/") else "document"
        size = int(meta.get("size") or 0)
        db.add_file(path=rel, name=name, kind=kind, size=size, mime=mime,
                    source="drive", drive_id=file_id)
        flash("Linked “%s” — streamed from Drive at /media/drive/…" % name)
    except (drive.DriveError, ValueError) as exc:
        flash("Link failed: %s" % exc, "error")
    return redirect(back)


# ------------------ admin: Google Photos ------------------
# Picks are always *imported*, never linked: a picked item's baseUrl expires,
# so unlike a Drive link there is nothing stable to stream from afterwards.

PHOTOS_SESSION_KEY = "photos_picker_session"
# Fallback extensions for items whose filename carries nothing usable. HEIC is
# deliberately absent: Google returns phone originals, browsers cannot render
# them, and importing one would put a broken image in the media library.
PHOTOS_MIME_EXT = {
    "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
    "image/gif": "gif", "image/avif": "avif",
    "video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov",
}
# Types no browser can render, whatever the filename claims. A phone original
# is reported as one of these, so they are checked before the filename: a mislabelled
# item must be skipped rather than stored under an extension that implies it works.
PHOTOS_UNRENDERABLE_MIME = {
    "image/heic", "image/heic-sequence", "image/heif", "image/heif-sequence",
}
# The same formats by extension, for the reverse mislabelling: a .heic name whose
# MIME claims JPEG still holds HEIC bytes, and renaming it .jpg would import a
# broken image rather than prevent one.
PHOTOS_UNRENDERABLE_EXT = {"heic", "heic-sequence", "heif", "heif-sequence"}


def _photos_extension(media):
    """A serveable extension for a picked item, or "" when none applies."""
    mime = (media.get("mimeType") or "").split(";")[0].strip().lower()
    if mime in PHOTOS_UNRENDERABLE_MIME:
        return ""
    ext = _ext_of(media.get("filename") or "")
    if ext in PHOTOS_UNRENDERABLE_EXT:
        return ""
    if ext in ALLOWED_EXT:
        return ext
    return PHOTOS_MIME_EXT.get(mime, "")


@app.route("/admin/photos")
@admin_required
def admin_photos():
    ctx = {"photos_ok": photos.is_configured(), "picker": "", "items": [],
           "poll_seconds": 5, "error": ""}
    if not ctx["photos_ok"]:
        return render_template("admin/photos.html", **ctx)
    session_id = session.get(PHOTOS_SESSION_KEY)
    if session_id:
        try:
            live = photos.get_session(session_id)
        except photos.PhotosError as exc:
            # A session that expired or was deleted is dropped rather than left
            # to fail on every page load.
            session.pop(PHOTOS_SESSION_KEY, None)
            ctx["error"] = str(exc)
            return render_template("admin/photos.html", **ctx)
        ctx["poll_seconds"] = photos.poll_hint(live)
        if live.get("mediaItemsSet"):
            try:
                # Paged fully, so the count on screen matches what an import of
                # this session will actually fetch.
                ctx["items"] = photos.all_media_items(session_id)
            except photos.PhotosError as exc:
                ctx["error"] = str(exc)
        else:
            ctx["picker"] = photos.picker_url(live)
    return render_template("admin/photos.html", **ctx)


@app.route("/admin/photos/session", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_photos_session():
    if not photos.is_configured():
        abort(404)
    # One open session at a time: Google rate-limits them per user, and an
    # abandoned one is dead the moment the user taps Done anyway.
    previous = session.pop(PHOTOS_SESSION_KEY, None)
    if previous:
        photos.delete_session(previous)
    try:
        created = photos.create_session()
    except photos.PhotosError as exc:
        flash("Could not start a Google Photos session: %s" % exc, "error")
        return redirect(url_for("admin_photos"))
    new_id = (created.get("id") or "").strip()
    if not new_id:
        # create_session only guarantees a picker URI; a response without an id
        # would be unusable, so it is treated as a failure rather than stored.
        app.logger.warning("photos: create_session returned no session id")
        flash("Google Photos returned a session without an id — try again.", "error")
        return redirect(url_for("admin_photos"))
    session[PHOTOS_SESSION_KEY] = new_id
    return redirect(url_for("admin_photos"))


@app.route("/admin/photos/cancel", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_photos_cancel():
    session_id = session.pop(PHOTOS_SESSION_KEY, None)
    if session_id:
        photos.delete_session(session_id)
        flash("Picking session discarded.")
    return redirect(url_for("admin_photos"))


@app.route("/admin/photos/import", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_photos_import():
    if not photos.is_configured():
        abort(404)
    session_id = session.get(PHOTOS_SESSION_KEY)
    if not session_id:
        flash("No Google Photos session is open — start one first.", "error")
        return redirect(url_for("admin_photos"))
    try:
        live = photos.get_session(session_id)
        if not live.get("mediaItemsSet"):
            flash("Nothing picked yet — finish selecting in Google Photos, then check again.", "error")
            return redirect(url_for("admin_photos"))
        items = photos.all_media_items(session_id)
    except photos.PhotosError as exc:
        # An expired or deleted session must not be retried against; drop it so
        # the next page load offers a fresh one instead of erroring again.
        session.pop(PHOTOS_SESSION_KEY, None)
        flash("Google Photos error: %s" % exc, "error")
        return redirect(url_for("admin_photos"))

    added, duplicates, skipped, errors = 0, 0, 0, []
    for item in items:
        media = item.get("mediaFile") or {}
        # PickedMediaItem.id is stable across sessions, so a re-pick of the same
        # photo is recognised instead of imported twice.
        media_id = (item.get("id") or "").strip()
        if media_id and db.get_file_by_photos_id(media_id):
            duplicates += 1
            continue
        ext = _photos_extension(media)
        if not ext or not media.get("baseUrl"):
            skipped += 1
            app.logger.warning(
                "photos import: skipped %s (type %s not serveable)",
                media.get("filename") or media_id or "unknown item",
                media.get("mimeType") or "unknown",
            )
            continue
        name = media.get("filename") or "photo.%s" % ext
        resp = None
        rel = None
        try:
            rel = _new_rel_path(name)
            resp = photos.download(media["baseUrl"])
            size = _save_stream(resp.raw, rel)
            # Inside the guard: a failed insert would otherwise 500 with the
            # bytes already on disk and no row pointing at them.
            db.add_file(path=rel, name=name,
                        kind="image" if ext in IMAGE_EXT else "document",
                        size=size, mime=media.get("mimeType") or "",
                        source="photos", photos_id=media_id)
        except (photos.PhotosError, ValueError) as exc:
            errors.append("%s: %s" % (name, exc))
            _discard_partial(rel)
            continue
        except sqlite3.IntegrityError:
            # The partial unique index on photos_id means a concurrent import of
            # the same photo lost the race. The other copy is already stored, so
            # treat this as the duplicate it is rather than a failure.
            duplicates += 1
            _discard_partial(rel)
            continue
        except sqlite3.Error as exc:
            errors.append("%s: could not record file (%s)" % (name, exc))
            _discard_partial(rel)
            continue
        finally:
            if resp is not None:
                resp.close()
        added += 1

    if errors:
        # Keep the session so a failed item can be retried; otherwise consume it.
        flash("Some items could not be imported: %s" % "; ".join(errors[:5]), "error")
    else:
        photos.delete_session(session_id)
        session.pop(PHOTOS_SESSION_KEY, None)

    summary = "Imported %d item(s) from Google Photos." % added
    if duplicates:
        summary += " %d already in the library." % duplicates
    if skipped:
        summary += " %d skipped as unserveable." % skipped
    flash(summary, "error" if errors else "success")
    return redirect(url_for("admin_photos"))


@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    return render_template("admin/feedback.html", items=db.list_feedback())


@app.route("/admin/feedback/<int:feedback_id>", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_feedback_update(feedback_id):
    db.update_feedback(feedback_id, request.form.get("status", "new"), request.form.get("note", ""))
    return redirect(url_for("admin_feedback"))


@app.route("/admin/feedback/<int:feedback_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_feedback_delete(feedback_id):
    db.delete_feedback(feedback_id)
    return redirect(url_for("admin_feedback"))


@app.route("/admin/import", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_import():
    """Restore a /admin/export payload. Admin only, idempotent on row id."""
    if request.method == "POST":
        upload = request.files.get("payload")
        raw = upload.read().decode("utf-8", "replace") if upload else request.form.get("payload", "")
        if not raw.strip():
            flash("Choose a backup file or paste its contents first.", "error")
            return redirect(url_for("admin_import"))
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            flash("That file is not valid JSON: %s" % exc, "error")
            return redirect(url_for("admin_import"))
        if not isinstance(payload, dict):
            flash("Expected a JSON object at the top level.", "error")
            return redirect(url_for("admin_import"))
        report = db.import_backup(payload)
        summary = ", ".join("%s %d" % (k, v) for k, v in report.items() if v)
        flash("Imported: %s" % (summary or "nothing new, every row already present"))
        return redirect(url_for("admin_import"))
    counts = {
        "feedback": len(db.list_feedback()),
        "bookings": len(db.list_bookings()),
        "contacts": len(db.list_contacts()),
        "journey": len(db.list_journey_subscribers()),
        "waitlist": len(db.list_waitlist()),
        "orders": len(db.list_orders()),
        "products": len(db.list_products()),
        "cms": len(db.list_page_section_keys()),
    }
    return render_template("admin/import.html", counts=counts)


@app.route("/admin/waitlist")
@admin_required
def admin_waitlist():
    return render_template("admin/waitlist.html", items=db.list_waitlist())


@app.route("/admin/emails")
@admin_required
def admin_emails():
    return render_template(
        "admin/emails.html",
        items=db.list_email_log(300),
        configured=mailer.is_configured(),
        host=os.environ.get("SMTP_HOST", ""),
        sender=os.environ.get("FROM_EMAIL") or os.environ.get("SMTP_USERNAME", ""),
    )


@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    return render_template("admin/bookings.html", items=db.list_bookings())


@app.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_booking_status(booking_id):
    db.set_booking_status(booking_id, request.form.get("status", "new"))
    return redirect(url_for("admin_bookings"))


@app.route("/admin/contacts")
@admin_required
def admin_contacts():
    return render_template("admin/contacts.html", items=db.list_contacts())


@app.route("/admin/journey")
@admin_required
def admin_journey():
    return render_template("admin/journey.html", items=db.list_journey_subscribers())


@app.route("/admin/journey/<int:subscriber_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_journey_delete(subscriber_id):
    db.delete_journey_subscriber(subscriber_id)
    return redirect(url_for("admin_journey"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    items = db.list_orders()
    for o in items:
        o["items_parsed"] = json.loads(o.get("items") or "[]")
    return render_template("admin/orders.html", items=items)


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_order_status(order_id):
    db.set_order_status(order_id, request.form.get("status", "enquiry"))
    return redirect(url_for("admin_orders"))


# ------------------ admin: pages (CMS) ------------------

def _video_embed(url):
    """Convert a YouTube or Vimeo URL to an embed iframe HTML."""
    if not url:
        return ""
    url = url.strip()
    # YouTube
    yt_match = None
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{6,})',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            yt_match = m.group(1)
            break
    if yt_match:
        return '<div class="video-embed"><iframe src="https://www.youtube.com/embed/%s" frameborder="0" allowfullscreen allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture"></iframe></div>' % yt_match
    # Vimeo
    vm = re.search(r'vimeo\.com\/(\d+)', url)
    if vm:
        return '<div class="video-embed"><iframe src="https://player.vimeo.com/video/%s" frameborder="0" allowfullscreen allow="autoplay;fullscreen;picture-in-picture"></iframe></div>' % vm.group(1)
    # Already an iframe or unrecognized — return as-is if it looks like embed code
    if url.startswith('<iframe'):
        return url
    return ''

@app.context_processor
def _inject_cms_helpers():
    # Build lookup: {(page, section_key, field_key): type} for richtext/video
    field_types = {}
    for pname, page_schema in cms.PAGES.items():
        for sec in page_schema["sections"]:
            for f in cms._flatten_fields(sec["fields"]):
                if f["type"] in ("richtext", "video", "image", "content_blocks", "section_style"):
                    field_types[(pname, sec["key"], f["key"])] = f["type"]
    return {
        '_video_embed': _video_embed,
        '_flatten_fields': cms._flatten_fields,
        '_cms_field_types': field_types,
        '_cms_is_richtext': lambda p, s, k: field_types.get((p, s, k)) == "richtext",
        '_cms_is_video': lambda p, s, k: field_types.get((p, s, k)) == "video",
        '_cms_is_blocks': lambda p, s, k: field_types.get((p, s, k)) == "content_blocks",
        '_cms_is_style': lambda p, s, k: field_types.get((p, s, k)) == "section_style",
        'BLOCK_TYPES': cms.BLOCK_TYPES,
        'SECTION_STYLE_OPTIONS': cms.SECTION_STYLE_OPTIONS,
    }


@app.route("/admin/pages")
@admin_required
def admin_pages():
    return render_template("admin/pages.html", pages=cms.PAGES)


@app.route("/admin/pages/<page>", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_page(page):
    schema = cms.PAGES.get(page)
    if not schema:
        abort(404)
    if request.method == "POST":
        section_key = request.form.get("section_key", "")
        section = next((s for s in schema["sections"] if s["key"] == section_key), None)
        if section:
            content = _parse_cms_section(section, request.form)
            active = "active" in request.form
            if _cms_section_is_empty(section, content):
                db.save_page_section(page, section_key, {}, active=False)
            else:
                db.save_page_section(page, section_key, content, active=active)
            flash("Saved %s — %s." % (schema["label"], section["label"]))
            return redirect(url_for("admin_page", page=page))
    media = [{"name": f["name"], "url": _media_url(f["path"])}
             for f in db.list_files() if f["kind"] == "image"]
    stored = db.get_page_sections(page)
    sections = list(schema["sections"])
    saved_order = db.get_settings().get("section_order_%s" % page, "")
    if saved_order:
        order_list = [k for k in saved_order.split(",") if k]
        order_idx = {k: i for i, k in enumerate(order_list)}
        sections.sort(key=lambda s: order_idx.get(s["key"], 999))
    return render_template("admin/page_edit.html", page_key=page, page_schema=schema,
                           stored=stored, media=media, sections=sections)


@app.route("/admin/pages/<page>/reorder", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_page_reorder(page):
    schema = cms.PAGES.get(page)
    if not schema:
        abort(404)
    order = request.form.get("section_order", "").strip()
    if order:
        valid_keys = {s["key"] for s in schema["sections"]}
        filtered = [k for k in order.split(",") if k in valid_keys]
        db.set_setting("section_order_%s" % page, ",".join(filtered))
        flash("Section order updated.")
    return redirect(url_for("admin_page", page=page))


# Rich-text sanitization. Keeps a tight allow-list of tags/attributes and
# strips any URL whose scheme is not in the same allow-list used by the
# RTE on the client side. Called from _parse_cms_section for every
# `richtext` field before the content is persisted.

_RTE_TAGS = {
    "p", "h2", "h3", "h4", "blockquote",
    "ul", "ol", "li",
    "strong", "em", "u", "s", "br", "a",
}
_RTE_ATTRIBUTES = {"a": {"href", "title"}}
_RTE_URL_SCHEMES = {"http", "https", "mailto", "tel"}


def _sanitize_rte_html(raw):
    """Return sanitized HTML for a richtext field, or an empty string."""
    if not raw:
        return ""
    return nh3.clean(
        raw,
        tags=_RTE_TAGS,
        attributes=_RTE_ATTRIBUTES,
        url_schemes=_RTE_URL_SCHEMES,
        link_rel="noopener",
    ).strip()


def _parse_cms_section(section, form):
    """Parse submitted form fields into a content dict per the field types."""
    content = {}
    for f in cms._flatten_fields(section["fields"]):
        key = f["key"]
        if f["type"] in ("text", "textarea", "longtext", "image", "video", "select"):
            content[key] = (form.get("field_%s" % key) or "").strip()
        elif f["type"] == "richtext":
            content[key] = _sanitize_rte_html(form.get("field_%s" % key) or "")
        elif f["type"] == "checkbox":
            content[key] = bool(key in form)
        elif f["type"] == "listlines":
            raw = (form.get("field_%s" % key) or "").strip()
            content[key] = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        elif f["type"] == "list":
            prefix = "item_%s" % key
            indexes = _form_indexes(form, prefix)
            items = []
            for idx in indexes:
                item = {}
                for sub_key, sub in f["item"].items():
                    name = "%s_%s_%s" % (prefix, idx, sub_key)
                    if sub["type"] in ("text", "textarea"):
                        item[sub_key] = (form.get(name) or "").strip()
                    elif sub["type"] == "listlines":
                        item[sub_key] = [ln.strip() for ln in (form.get(name) or "").splitlines() if ln.strip()]
                    elif sub["type"] == "checkbox":
                        item[sub_key] = bool(name in form)
                    else:
                        item[sub_key] = (form.get(name) or "").strip()
                if not _list_item_is_empty(f["item"], item):
                    items.append(item)
            content[key] = items
        elif f["type"] == "content_blocks":
            raw_json = (form.get("field_%s" % key) or "[]").strip()
            try:
                parsed = json.loads(raw_json)
                if not isinstance(parsed, list):
                    parsed = []
            except (ValueError, TypeError):
                parsed = []
            content[key] = parsed
        elif f["type"] == "section_style":
            content[key] = {
                "background": (form.get("style_%s_background" % key) or "none").strip(),
                "background_custom": (form.get("style_%s_background_custom" % key) or "").strip(),
                "text_align": (form.get("style_%s_text_align" % key) or "left").strip(),
                "padding": (form.get("style_%s_padding" % key) or "medium").strip(),
            }
    return content


def _cms_section_is_empty(section, content):
    """True when every field holds an empty/default value (no real content)."""
    for f in cms._flatten_fields(section["fields"]):
        v = content.get(f["key"])
        if f["type"] == "list":
            if any(not _list_item_is_empty(f["item"], item) for item in (v or [])):
                return False
        elif f["type"] == "listlines":
            if v:
                return False
        elif f["type"] == "content_blocks":
            if v:
                return False
        elif f["type"] == "section_style":
            continue
        elif isinstance(v, list):
            if v:
                return False
        elif str(v or "").strip():
            return False
    return True


def _form_indexes(form, prefix):
    """Collect the numeric indexes present for names like ``<prefix>_<n>_<key>``."""
    seen = set()
    for name in form.keys():
        if not name.startswith(prefix + "_"):
            continue
        rest = name[len(prefix) + 1:]
        num = rest.split("_", 1)[0]
        if num.isdigit():
            seen.add(num)
    return sorted(int(x) for x in seen)


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_settings():
    if request.method == "POST":
        boolean_keys = list(db.DEFAULT_SETTINGS.keys())
        mapping = {k: ("1" if k in request.form else "0") for k in boolean_keys}
        db.set_settings(mapping)
        db.prune_settings(db.DEFAULT_SETTINGS.keys())
        flash("Settings saved.")
        return redirect(url_for("admin_settings"))
    s = db.get_settings()
    return render_template("admin/settings.html", settings=s)


@app.route("/admin/password", methods=["GET", "POST"])
@admin_required
def admin_password():
    if request.method == "POST" and not csrf.validate():
        abort(400, "CSRF token missing or invalid")
    if request.method == "POST":
        new_pw = request.form.get("password", "")
        current_pw = request.form.get("current_password", "")
        user = current_user()
        if not user:
            return redirect(url_for("admin_login"))
        if not db.verify_user(user["username"], current_pw):
            flash("Your current password is not correct.", "error")
            return render_template("admin/password.html")
        if len(new_pw) >= 12:
            db.set_user_password(user["id"], new_pw)
            db.log_action(user["id"], user["username"], "password-changed", user["username"], "")
            flash("Password updated.")
            return redirect(url_for("admin_dashboard"))
        flash("Password must be at least 12 characters.", "error")
    return render_template("admin/password.html")


@app.route("/admin/export")
@admin_required
def admin_export():
    return jsonify({
        "feedback": db.list_feedback(),
        "waitlist": db.list_waitlist(),
        "bookings": db.list_bookings(),
        "contacts": db.list_contacts(),
        "orders": db.list_orders(),
        "settings": db.get_settings(),
        "products": db.list_products(),
        "files": db.list_files(),
        "exportedAt": _dt.now().isoformat(),
    })


# ------------------ admin: CSV exports ------------------

def _csv_response(filename, headers, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=%s" % filename},
    )


@app.route("/admin/export/waitlist.csv")
@admin_required
def export_waitlist_csv():
    rows = [(w["email"], w["source"], w["created_at"]) for w in db.list_waitlist()]
    return _csv_response("asa-oz-waitlist.csv", ["Email", "Source", "Date"], rows)


@app.route("/admin/export/contacts.csv")
@admin_required
def export_contacts_csv():
    rows = [(c["name"], c["email"], c["message"].replace("\n", " "), c["created_at"]) for c in db.list_contacts()]
    return _csv_response("asa-oz-contacts.csv", ["Name", "Email", "Message", "Date"], rows)


@app.route("/admin/export/orders.csv")
@admin_required
def export_orders_csv():
    rows = []
    for o in db.list_orders():
        items = json.loads(o.get("items") or "[]")
        names = ", ".join("%s ×%d" % (it["name"], it["qty"]) for it in items)
        rows.append((o["id"], names, o["total"], o["status"], o["created_at"], o.get("customer_email", "")))
    return _csv_response("asa-oz-orders.csv",
                         ["Order ID", "Items", "Total (EUR)", "Status", "Date", "Email"],
                         rows)


@app.route("/admin/export/bookings.csv")
@admin_required
def export_bookings_csv():
    rows = [(b["name"], b["email"], b["phone"], b["date"], b["time"], b["status"], b["created_at"]) for b in db.list_bookings()]
    return _csv_response("asa-oz-bookings.csv", ["Name", "Email", "Phone", "Date", "Time", "Status", "Created"], rows)


@app.route("/admin/export/feedback.csv")
@admin_required
def export_feedback_csv():
    rows = [(f["category"], f["text"].replace("\n", " "), f["status"], f["note"], f["created_at"]) for f in db.list_feedback()]
    return _csv_response("asa-oz-feedback.csv", ["Category", "Text", "Status", "Note", "Date"], rows)


# ------------------ admin: dynamic pages ------------------

@app.route("/admin/dynamic-pages", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_dynamic_pages():
    if request.method == "POST":
        slug = (request.form.get("slug") or "").strip().lower()
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        if not slug or not title:
            flash("Slug and title are required.", "error")
        else:
            db.save_dynamic_page(slug, title, description)
            flash("Page '%s' created." % title, "success")
        return redirect(url_for("admin_dynamic_pages"))
    pages = db.list_dynamic_pages()
    return render_template("admin/dynamic_pages.html", pages=pages)


@app.route("/admin/dynamic-pages/new", methods=["GET", "POST"])
@admin_required
@csrf.require_csrf
def admin_dynamic_page_new():
    return render_template("admin/dynamic_page_edit.html", page=None, slug="", stored={}, media=_media_library())


@app.route("/admin/dynamic-pages/<slug>")
@admin_required
def admin_dynamic_page_edit(slug):
    page = db.get_dynamic_page(slug)
    if not page:
        flash("Page not found.", "error")
        return redirect(url_for("admin_dynamic_pages"))
    stored = db.get_page_sections(slug)
    return render_template("admin/dynamic_page_edit.html", page=page, slug=slug, stored=stored, media=_media_library())


@app.route("/admin/dynamic-pages/<slug>/save", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_dynamic_page_save(slug):
    page = db.get_dynamic_page(slug)
    if not page:
        abort(404)
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    active = request.form.get("active") == "1"
    db.save_dynamic_page(slug, title, description, page.get("template", "default"), active)
    flash("Page settings updated.", "success")
    return redirect(url_for("admin_dynamic_page_edit", slug=slug))


@app.route("/admin/dynamic-pages/<slug>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_dynamic_page_delete(slug):
    page = db.get_dynamic_page(slug)
    if not page:
        abort(404)
    if request.form.get("confirm") == "1":
        db.delete_dynamic_page(slug)
        flash("Page deleted.", "success")
    return redirect(url_for("admin_dynamic_pages"))


@app.route("/admin/dynamic-pages/<slug>/section", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_dynamic_page_section(slug):
    section_key = request.form.get("section_key", "")
    content = {
        "heading": (request.form.get("heading") or "").strip(),
        "body": (request.form.get("body") or "").strip(),
    }
    blocks_raw = (request.form.get("blocks_json") or "[]").strip()
    try:
        content["blocks"] = json.loads(blocks_raw) if blocks_raw else []
    except (ValueError, TypeError):
        content["blocks"] = []
    if request.form.get("image"):
        content["image"] = (request.form.get("image") or "").strip()
        content["image_alt"] = (request.form.get("image_alt") or "").strip()
    if not content["heading"] and not content["body"] and not content.get("blocks") and not content.get("image"):
        db.save_page_section(slug, section_key, {}, active=False)
    else:
        db.save_page_section(slug, section_key, content, active=("active" in request.form))
    flash("Section saved.", "success")
    return redirect(url_for("admin_dynamic_page_edit", slug=slug))


# ------------------ admin: navigation ------------------

def _safe_navigation_url(url):
    """Allow only internal paths or http(s)/mailto schemes. Returns (ok, value)."""
    if not isinstance(url, str):
        return False, ""
    u = url.strip()
    if not u:
        return False, ""
    if u.startswith("/"):
        if u.startswith("//") or u.startswith("/\\"):
            return False, ""
        return True, u
    # mailto: has no // separator
    if u.lower().startswith("mailto:"):
        return True, u
    if "://" not in u:
        return False, ""
    scheme = u.split("://", 1)[0].lower()
    if scheme not in {"http", "https"}:
        return False, ""
    return True, u


@app.route("/admin/navigation", methods=["GET", "POST"])
@admin_required
def admin_navigation():
    if request.method == "POST" and not csrf.validate():
        abort(400, "CSRF token missing or invalid")
    if request.method == "POST":
        if "delete_id" in request.form:
            db.delete_navigation_item(int(request.form.get("delete_id", 0)))
            flash("Navigation item deleted.", "success")
        elif "reorder_ids" in request.form:
            ids = [int(i) for i in request.form.get("reorder_ids", "").split(",") if i.strip().isdigit()]
            db.reorder_navigation(ids)
            flash("Navigation reordered.", "success")
        else:
            ok, safe_url = _safe_navigation_url(request.form.get("url", ""))
            if not ok:
                flash("Invalid URL — must start with / or use http(s)/mailto.", "error")
            else:
                db.save_navigation_item(
                    None if request.form.get("id") == "new" else int(request.form.get("id", 0) or 0),
                    request.form.get("label", ""),
                    safe_url,
                    int(request.form.get("position", 99)),
                    request.form.get("active") == "1",
                )
                flash("Navigation item saved.", "success")
        return redirect(url_for("admin_navigation"))
    items = db.list_navigation()
    return render_template("admin/navigation.html", items=items)


def _media_library():
    return [{"name": f["name"], "url": _media_url(f["path"])}
            for f in db.list_files() if f["kind"] == "image"]


# ------------------ admin: brand settings ------------------

@app.route("/admin/brand", methods=["GET", "POST"])
@admin_required
def admin_brand():
    if request.method == "POST" and not csrf.validate():
        abort(400, "CSRF token missing or invalid")
    if request.method == "POST":
        brand = {
            "logo": (request.form.get("logo") or "").strip(),
            "logo_alt": (request.form.get("logo_alt") or "").strip(),
            "favicon": (request.form.get("favicon") or "").strip(),
        }
        db.set_setting("brand", json.dumps(brand))
        flash("Brand settings saved.", "success")
        return redirect(url_for("admin_brand"))
    raw = db.get_settings().get("brand", "{}")
    try:
        brand = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        brand = {}
    defaults = {"logo": "", "logo_alt": "Asa-OZ", "favicon": ""}
    defaults.update(brand)
    return render_template("admin/brand.html", brand=defaults, media=_media_library())


@app.context_processor
def _inject_nav_and_brand():
    nav = db.list_navigation(active_only=True)
    raw = db.get_settings().get("brand", {})
    try:
        brand = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        brand = {}
    defaults = {"logo": "", "logo_alt": "Asa-OZ", "favicon": ""}
    defaults.update(brand if brand else {})
    return {
        "nav_items": nav,
        "brand_settings": defaults,
    }


# ------------------ member accounts ------------------

def member_required(fn):
    """Require a signed-in account. Members use the public site, not the admin."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("account_login"))
        return fn(*args, **kwargs)
    return wrapper


def _member_orders(user):
    """The orders this account owns.

    Orders placed while signed in carry the account id. Older orders are
    matched on the email address, but only once that address is verified —
    otherwise anybody could sign up with somebody else's address and read
    their orders.
    """
    verified = db.email_verified(user)
    return db.list_orders_for_user(user["id"], email=user["email"], include_email=verified)


@app.route("/account/login", methods=["GET", "POST"])
def account_login():
    if current_user():
        return redirect(url_for("account"))
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        login = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""
        user = db.verify_user(login, password)
        if user:
            sign_in(user)
            db.log_action(user["id"], user["username"], "member-sign-in", user["email"], user["role"])
            nxt = request.args.get("next") or ""
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("account"))
        db.record_login_failure(login, request.remote_addr or "")
        return render_template("account/login.html", error="That email or password is not right.",
                               login=login), 401
    return render_template("account/login.html", login="")


@app.route("/account/signup", methods=["GET", "POST"])
def account_signup():
    if current_user():
        return redirect(url_for("account"))
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        problem = captcha.check_request()
        if problem:
            return render_template("account/signup.html", error=problem,
                                   email=(request.form.get("email") or ""),
                                   full_name=(request.form.get("full_name") or "")), 400
        email = (request.form.get("email") or "").strip().lower()
        full_name = (request.form.get("full_name") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if "@" not in email or "." not in email.split("@")[-1]:
            return render_template("account/signup.html", error="We need a valid email address.",
                                   email=email, full_name=full_name), 400
        if len(password) < 12:
            return render_template("account/signup.html",
                                   error="A password needs at least 12 characters.",
                                   email=email, full_name=full_name), 400
        if password != confirm:
            return render_template("account/signup.html", error="The two passwords do not match.",
                                   email=email, full_name=full_name), 400
        if db.email_taken(email):
            return render_template("account/signup.html",
                                   error="There is already an account with that email. Sign in instead.",
                                   email=email, full_name=full_name), 400
        try:
            user, token = db.create_member(email, full_name, password)
        except sqlite3.IntegrityError:
            return render_template("account/signup.html",
                                   error="There is already an account with that email. Sign in instead.",
                                   email=email, full_name=full_name), 400
        sign_in(user)
        db.log_action(user["id"], user["username"], "member-sign-up", user["email"], "")
        _send_member_verify(user, token)
        flash("Your account is ready. Check your email to confirm it.", "success")
        return redirect(url_for("account"))
    return render_template("account/signup.html", email="", full_name="")


def _send_member_verify(user, token=None):
    """Send (or re-send) the address confirmation email."""
    token = token or db.create_verify_token(user["id"])
    link = f"{BASE_URL}/account/verify/{token}"
    return mailer.send("member_verify", user["email"], {
        "confirm_url": link,
        "member_name": user["full_name"] or user["username"],
    })


@app.route("/account/verify/<token>")
def account_verify(token):
    user = db.get_user_by_verify_token(token)
    if not user:
        return render_template("account/verify.html", ok=False), 404
    if db.invite_expired(user):
        return render_template("account/verify.html", ok=False, expired=True), 410
    db.set_user_email_verified(user["id"])
    db.log_action(user["id"], user["username"], "email-verified", user["email"], "")
    return render_template("account/verify.html", ok=True)


@app.route("/account/verify", methods=["POST"])
@member_required
@csrf.require_csrf
def account_verify_resend():
    user = current_user()
    token = db.create_verify_token(user["id"])
    _send_member_verify(user, token)
    flash("We sent the confirmation link again.", "success")
    return redirect(url_for("account"))


@app.route("/account/logout", methods=["POST"])
@member_required
@csrf.require_csrf
def account_logout():
    user = current_user()
    db.log_action(user["id"], user["username"], "member-sign-out", user["email"], "")
    sign_out()
    return redirect(url_for("index"))


@app.route("/account")
@member_required
def account():
    user = current_user()
    orders = _member_orders(user)
    return render_template(
        "account/overview.html",
        user=user,
        orders=orders,
        total_spent=sum(o["total"] for o in orders if o["status"] in ("paid", "shipped")),
        stories=db.list_blog_posts_by_user(user["id"]),
        feedback=db.list_feedback_for_user(user["id"]),
        testimonials=db.list_testimonials(user_id=user["id"]),
        verified=db.email_verified(user),
    )


@app.route("/account/orders")
@member_required
def account_orders():
    user = current_user()
    orders = _member_orders(user)
    return render_template(
        "account/orders.html",
        user=user,
        orders=orders,
        total_spent=sum(o["total"] for o in orders if o["status"] in ("paid", "shipped")),
        verified=db.email_verified(user),
    )


@app.route("/account/testimonial", methods=["GET", "POST"])
@member_required
def account_testimonial():
    user = current_user()
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        quote = (request.form.get("quote") or "").strip()
        if len(quote) < 10:
            flash("Tell us a little more — a sentence or two.", "error")
            return render_template("account/testimonial.html", user=user, quote=quote)
        db.add_testimonial(user["id"], user["full_name"] or user["username"], quote,
                           request.form.get("role") or "Community member")
        flash("Thank you. We will read it before it goes on the site.", "success")
        return redirect(url_for("account"))
    return render_template("account/testimonial.html", user=user, quote="")


@app.route("/account/feedback", methods=["GET", "POST"])
@member_required
def account_feedback():
    user = current_user()
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        text = (request.form.get("text") or "").strip()
        category = (request.form.get("category") or "General").strip()
        if not text:
            flash("Write a little something first.", "error")
            return render_template("account/feedback.html", user=user, text=text)
        db.add_feedback(category, text, user_id=user["id"])
        notify.notify_feedback(category, text)
        flash("Thank you. Your feedback has been sent.", "success")
        return redirect(url_for("account"))
    return render_template("account/feedback.html", user=user, text="")


@app.route("/account/profile", methods=["GET", "POST"])
@member_required
def account_profile():
    user = current_user()
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        current_password = request.form.get("current_password") or ""
        if email and email != user["email"] and db.email_taken(email):
            flash("That email address already has an account.", "error")
            return render_template("account/profile.html", user=user)
        if password:
            if not db.verify_user(user["username"], current_password):
                flash("Your current password is not right.", "error")
                return render_template("account/profile.html", user=user)
            if len(password) < 12:
                flash("A password needs at least 12 characters.", "error")
                return render_template("account/profile.html", user=user)
            db.change_user_password(user["id"], password)
        if email and email != user["email"]:
            db.update_user_profile(user["id"], full_name, email)
            db.create_verify_token(user["id"])
            _send_member_verify(db.get_user(user["id"]))
            flash("Details saved. Confirm the new address from your email.", "success")
        else:
            db.update_user_profile(user["id"], full_name)
            flash("Details saved.", "success")
        return redirect(url_for("account"))
    return render_template("account/profile.html", user=user)


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("admin/403.html"), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ------------------ users, roles and invites ------------------

def _invite_url(token):
    return f"{BASE_URL}/invite/{token}"


def _can_manage(actor, target):
    """May ``actor`` change ``target``'s account? (role, status, delete)"""
    if not actor or not target:
        return False
    if target["id"] == actor["id"]:
        return False
    return roles.may_manage(actor["role"], target["role"])


@app.route("/admin/testimonials")
@admin_required
def admin_testimonials():
    rows = db.list_testimonials()
    for row in rows:
        row["author_verified"] = db.author_email_verified(row.get("user_id"))
    return render_template("admin/testimonials.html", testimonials=rows)


@app.route("/admin/testimonials/<int:testimonial_id>/status", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_testimonial_status(testimonial_id):
    status = (request.form.get("status") or "new").strip()
    if status not in ("new", "approved", "rejected"):
        abort(400)
    row = db.get_testimonial(testimonial_id)
    if row and status == "approved" and not db.author_email_verified(row.get("user_id")):
        flash("That testimonial came from an account whose email is not confirmed. "
              "Ask them to confirm it before it goes on the site.", "error")
        return redirect(url_for("admin_testimonials"))
    db.set_testimonial_status(testimonial_id, status)
    user = current_user()
    db.log_action(user["id"], user["username"], "testimonial-status", str(testimonial_id), status)
    flash("Testimonial updated.", "success")
    return redirect(url_for("admin_testimonials"))


@app.route("/admin/testimonials/<int:testimonial_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_testimonial_delete(testimonial_id):
    db.delete_testimonial(testimonial_id)
    user = current_user()
    db.log_action(user["id"], user["username"], "testimonial-deleted", str(testimonial_id), "")
    flash("Testimonial removed.", "success")
    return redirect(url_for("admin_testimonials"))


@app.route("/admin/users")
@admin_required
def admin_users():
    user = current_user()
    status = (request.args.get("status") or "").strip()
    role = (request.args.get("role") or "").strip()
    search = (request.args.get("q") or "").strip()
    return render_template(
        "admin/users.html",
        users=db.list_users(status=status, role=role, search=search),
        roles=roles,
        actor=user,
        assignable=roles.assignable_roles(user["role"]),
        status_filter=status,
        role_filter=role,
        search=search,
        audit=db.list_audit(25),
    )


@app.route("/admin/users/new", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_user_new():
    actor = current_user()
    username = (request.form.get("username") or "").strip().lower()
    email = (request.form.get("email") or "").strip()
    full_name = (request.form.get("full_name") or "").strip()
    role = (request.form.get("role") or "").strip()
    password = (request.form.get("password") or "").strip()

    if not username or not re.match(r"^[a-z0-9._-]{3,32}$", username):
        flash("Username must be 3-32 characters: letters, digits, dot, dash or underscore.", "error")
        return redirect(url_for("admin_users"))
    if "@" not in email or "." not in email.split("@")[-1]:
        flash("A valid email address is required — the invitation is sent there.", "error")
        return redirect(url_for("admin_users"))
    if not roles.is_role(role):
        flash("Unknown role.", "error")
        return redirect(url_for("admin_users"))
    if not roles.may_assign(actor["role"], role):
        flash("You cannot hand out a role above your own.", "error")
        return redirect(url_for("admin_users"))
    if db.username_taken(username):
        flash("That username is taken.", "error")
        return redirect(url_for("admin_users"))
    if db.email_taken(email):
        flash("That email address already has an account.", "error")
        return redirect(url_for("admin_users"))
    if password and len(password) < 12:
        flash("A password must be at least 12 characters.", "error")
        return redirect(url_for("admin_users"))

    user, token = db.create_user(username, email, full_name, role, invited_by=actor["id"],
                                 password=password)
    db.log_action(actor["id"], actor["username"], "user-created", username, role)
    if password:
        flash(f"{username} created with a password. They can sign in now.")
    else:
        invite = _invite_url(token)
        sent = mailer.send_user_invite(email, full_name or username, invite, roles.label(role))
        db.log_action(actor["id"], actor["username"], "invite-sent", username,
                      "sent" if sent else "not-configured")
        if sent:
            flash(f"Invitation sent to {email}.")
        else:
            flash("Mail is not configured, so the invitation was not sent. Copy the link below.",
                  "error")
        flash(invite)
    return redirect(url_for("admin_user_edit", user_id=user["id"]))


@app.route("/admin/users/<int:user_id>")
@admin_required
def admin_user_edit(user_id):
    actor = current_user()
    target = db.get_user(user_id)
    if not target:
        abort(404)
    invite = ""
    if target["status"] == "invited" and target.get("invite_token"):
        invite = _invite_url(target["invite_token"])
    return render_template(
        "admin/user_edit.html",
        target=target,
        actor=actor,
        roles=roles,
        assignable=roles.assignable_roles(actor["role"]),
        manageable=_can_manage(actor, target),
        invite_url=invite,
        audit=db.list_audit(20),
    )


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_user_role(user_id):
    actor = current_user()
    target = db.get_user(user_id)
    role = (request.form.get("role") or "").strip()
    if not target:
        abort(404)
    if not _can_manage(actor, target):
        flash("You cannot change that account.", "error")
        return redirect(url_for("admin_user_edit", user_id=user_id))
    if not roles.is_role(role) or not roles.may_assign(actor["role"], role):
        flash("You cannot hand out that role.", "error")
        return redirect(url_for("admin_user_edit", user_id=user_id))
    if target["role"] == roles.SUPERADMIN and role != roles.SUPERADMIN:
        if db.count_active_superadmins(exclude_id=target["id"]) == 0:
            flash("The last superadmin cannot be demoted.", "error")
            return redirect(url_for("admin_user_edit", user_id=user_id))
    db.set_user_role(user_id, role)
    db.log_action(actor["id"], actor["username"], "role-changed", target["username"],
                  f"{target['role']} -> {role}")
    flash(f"{target['username']} is now {roles.label(role)}.")
    return redirect(url_for("admin_user_edit", user_id=user_id))


@app.route("/admin/users/<int:user_id>/status", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_user_status(user_id):
    actor = current_user()
    target = db.get_user(user_id)
    status = (request.form.get("status") or "").strip()
    if not target:
        abort(404)
    if not _can_manage(actor, target):
        flash("You cannot change that account.", "error")
        return redirect(url_for("admin_user_edit", user_id=user_id))
    if status not in ("active", "suspended", "invited"):
        abort(400)
    if target["role"] == roles.SUPERADMIN and status != "active":
        if db.count_active_superadmins(exclude_id=target["id"]) == 0:
            flash("The last superadmin cannot be suspended.", "error")
            return redirect(url_for("admin_user_edit", user_id=user_id))
    db.set_user_status(user_id, status)
    db.log_action(actor["id"], actor["username"], "status-changed", target["username"], status)
    flash(f"{target['username']} is now {status}.")
    return redirect(url_for("admin_user_edit", user_id=user_id))


@app.route("/admin/users/<int:user_id>/invite", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_user_invite(user_id):
    """Re-send an invitation (or issue a password reset link)."""
    actor = current_user()
    target = db.get_user(user_id)
    if not target:
        abort(404)
    if not _can_manage(actor, target):
        flash("You cannot change that account.", "error")
        return redirect(url_for("admin_user_edit", user_id=user_id))
    token = db.create_invite(user_id)
    invite = _invite_url(token)
    sent = mailer.send_user_invite(target["email"], target["full_name"] or target["username"],
                                   invite, roles.label(target["role"]))
    db.log_action(actor["id"], actor["username"], "invite-sent", target["username"],
                  "sent" if sent else "not-configured")
    if sent:
        flash(f"A new invitation was sent to {target['email']}.")
    else:
        flash("Mail is not configured, so the invitation was not sent. Copy the link below.", "error")
        flash(invite)
    return redirect(url_for("admin_user_edit", user_id=user_id))


@app.route("/admin/users/<int:user_id>/verify", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_user_verify(user_id):
    """Send a member the link that confirms their address."""
    actor = current_user()
    target = db.get_user(user_id)
    if not target:
        abort(404)
    if not _can_manage(actor, target):
        flash("You cannot change that account.", "error")
        return redirect(url_for("admin_user_edit", user_id=user_id))
    token = db.create_verify_token(user_id)
    invite = f"{BASE_URL}/account/verify/{token}"
    sent = mailer.send("member_verify", target["email"], {
        "confirm_url": invite,
        "member_name": target["full_name"] or target["username"],
    })
    db.log_action(actor["id"], actor["username"], "verify-sent", target["username"],
                  "sent" if sent else "not-configured")
    if sent:
        flash(f"We sent a confirmation link to {target['email']}.", "success")
    else:
        flash("Mail is not configured, so the link was not sent. Copy it below.", "error")
        flash(invite)
    return redirect(url_for("admin_user_edit", user_id=user_id))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
@csrf.require_csrf
def admin_user_delete(user_id):
    actor = current_user()
    target = db.get_user(user_id)
    if not target:
        abort(404)
    if not _can_manage(actor, target):
        flash("You cannot delete that account.", "error")
        return redirect(url_for("admin_users"))
    if target["role"] == roles.SUPERADMIN and db.count_active_superadmins(exclude_id=target["id"]) == 0:
        flash("The last superadmin cannot be deleted.", "error")
        return redirect(url_for("admin_user_edit", user_id=user_id))
    db.delete_user(user_id)
    db.log_action(actor["id"], actor["username"], "user-deleted", target["username"], target["role"])
    flash(f"{target['username']} was removed.")
    return redirect(url_for("admin_users"))


@app.route("/invite/<token>", methods=["GET", "POST"])
def invite_accept(token):
    """Redeem an invitation: the invite token is the credential."""
    user = db.get_user_by_invite_token(token)
    if not user:
        return render_template("invite_accept.html", user=None, error="This invitation is not valid."), 404
    if db.invite_expired(user):
        return render_template(
            "invite_accept.html", user=user,
            error="This invitation has expired. Ask an administrator to send a new one.",
        ), 410
    if request.method == "POST":
        if not csrf.validate():
            abort(400, "CSRF token missing or invalid")
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if password != confirm:
            flash("The two passwords do not match.", "error")
            return render_template("invite_accept.html", user=user)
        if len(password) < 12:
            flash("A password must be at least 12 characters.", "error")
            return render_template("invite_accept.html", user=user)
        db.set_user_password(user["id"], password)
        db.log_action(user["id"], user["username"], "invite-accepted", user["username"], user["role"])
        fresh = db.get_user(user["id"])
        sign_in(fresh)
        flash("Your account is ready.")
        if user["role"] == roles.MEMBER:
            return redirect(url_for("index"))
        return redirect(url_for("admin_dashboard"))
    return render_template("invite_accept.html", user=user)


with app.app_context():
    _seed_home_marquee()
    app.logger.info("boot: drive configured=%s", drive.is_configured())
    app.logger.info("boot: photos configured=%s", photos.is_configured())
    app.logger.info("boot: email configured=%s host=%s", notify.is_configured(), os.environ.get("SMTP_HOST", "-"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 5000), debug=False)
