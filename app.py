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
import mimetypes
import os
import uuid
import datetime
from datetime import datetime as _dt
from functools import wraps

import stripe
from flask import (
    Flask, abort, flash, jsonify, redirect, render_template, request, session, send_from_directory, url_for,
)
from werkzeug.utils import secure_filename

import db
import cms

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STRIPE_SECRET = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_URL = (os.environ.get("APP_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:5000").rstrip("/")
BASE_URL = APP_URL

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "asa-oz-dev-secret-change-me")


ENDPOINT_PAGE = {
    "index": "home",
    "about": "about",
    "faq": "faq",
    "terms": "terms",
    "privacy": "privacy",
    "contact": "contact",
    "store": "home",
    "product": "home",
}


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
    """Serve files from UPLOAD_DIR (bytes live here; DB stores only the path)."""
    return send_from_directory(UPLOAD_DIR, filename)


def _wall_files():
    if not os.path.isdir(WALL_DIR):
        return []
    try:
        files = sorted(os.listdir(WALL_DIR))
    except OSError:
        return []
    return ["wall-of-memories/%s" % f
            for f in files if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))]


def _wall_moments():
    """Marquee + wall-of-memories photo urls.

    Uses the home CMS "marquee" images when any are set; otherwise falls back
    to scanning images/wall-of-memories/ (served via /images, each url-quoted)."""
    marquee = cms.resolve("home", db.get_page_sections("home")).get("marquee") or {}
    urls = [img.get("image", "").strip() for img in (marquee.get("images") or [])]
    urls = [u for u in urls if u]
    if urls:
        return urls
    return [url_for("images", filename=url) for url in _wall_files()]


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
    with open(dest, "wb") as f:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                os.remove(dest)
                raise ValueError("file exceeds %d MB" % MAX_UPLOAD_MB)
            f.write(chunk)
    return size


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


@app.context_processor
def inject_globals():
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
        "store_copy": {
            "hero_title": _settings_snapshot().get("store_hero_title", "Tools for the journey"),
            "hero_lede": _settings_snapshot().get(
                "store_hero_lede",
                "Thoughtfully made things to support your return — journals, guides, circles, and keepsakes. Every item carries the same intention as the experiences themselves.",
            ),
            "similar_title": _settings_snapshot().get("store_similar_title", "You may also like"),
            "tools_heading": _settings_snapshot().get("tools_heading", "Tools for the journey"),
        },
    }


# ------------------ public pages ------------------
@app.route("/")
def index():
    return render_template("index.html", products=db.list_products(active_only=True))


@app.route("/api/wall")
def api_wall():
    return jsonify({"images": _wall_moments()})


@app.route("/store")
def store():
    type_filter = request.args.get("type", "all")
    products = db.list_products(active_only=True)
    return render_template("store.html", products=products, type_filter=type_filter)


@app.route("/store/partial")
def store_partial():
    type_filter = request.args.get("type", "all")
    products = db.list_products(active_only=True)
    return render_template("partials/store_grid.html", products=products, type_filter=type_filter)


@app.route("/product/<product_id>")
def product(product_id):
    product = db.get_product(product_id)
    if not product:
        abort(404)
    others = [p for p in db.list_products(active_only=True) if p["id"] != product_id]
    similar = [p for p in others if p["type"] == product["type"]] or others[:3]
    return render_template("product.html", product=product, similar=similar[:3])


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


# ------------------ forms (HTMX) ------------------
@app.route("/waitlist", methods=["POST"])
def waitlist():
    email = (request.form.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return '<p class="msg" style="color:#b5482c;" role="status">Please enter a valid email address.</p>'
    ok = db.add_waitlist(email, request.form.get("source", ""))
    if ok:
        return '<p class="msg" role="status">Thank you. You&rsquo;ll be among the first to return to yourself.</p>'
    return '<p class="msg" style="color:#b5482c;" role="status">You&rsquo;re already on the list — we&rsquo;ll be in touch.</p>'


@app.route("/booking", methods=["POST"])
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
    return render_template("partials/booking_confirm.html")


@app.route("/feedback", methods=["POST"])
def feedback():
    text = (request.form.get("text") or "").strip()
    category = (request.form.get("category") or "").strip()
    if not text:
        return '<p class="feedback-msg" style="color:#b5482c;" role="status">Please write a little something first.</p>'
    db.add_feedback(category, text)
    return '<p class="feedback-msg" role="status">Thank you. Your feedback has been saved.</p>'


@app.route("/contact-msg", methods=["POST"])
def contact_msg():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    message = (request.form.get("message") or "").strip()
    if not all([name, email, message]):
        return '<p class="form-msg" style="color:#b5482c;" role="status">Please fill in every field.</p>'
    db.add_contact(name, email, message)
    return '<p class="form-msg" role="status">Thank you — your message has been saved. We&rsquo;ll reply to you shortly.</p>'


@app.route("/journey", methods=["POST"])
def journey_subscribe():
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    journey_stage = (request.form.get("journey_stage") or "interest").strip()
    source = (request.form.get("source") or "").strip()
    if not email or "@" not in email:
        return '<p class="msg" style="color:#b5482c;" role="status">Please enter a valid email address.</p>'
    db.add_journey_subscriber(email, name, journey_stage, source)
    return '<p class="msg" role="status">Welcome to the journey. We\'ll be in touch soon.</p>'


# ------------------ cart (HTMX) ------------------
@app.route("/cart/drawer")
def cart_drawer_view():
    return cart_drawer()


@app.route("/cart/add", methods=["POST"])
def cart_add():
    product_id = request.form.get("id")
    p = db.get_product(product_id)
    if not p:
        abort(404)
    cart = session.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    save_cart(cart)
    return cart_drawer()


@app.route("/cart/qty", methods=["POST"])
def cart_qty():
    product_id, delta = request.form.get("id"), int(request.form.get("delta", 0))
    cart = session.get("cart", {})
    cart[product_id] = max(0, cart.get(product_id, 0) + delta)
    save_cart(cart)
    return cart_drawer()


@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    product_id = request.form.get("id")
    cart = session.get("cart", {})
    cart.pop(product_id, None)
    save_cart(cart)
    return cart_drawer()


def cart_drawer():
    return render_template(
        "partials/cart_drawer.html",
        cart_items=cart_contents(),
        cart_count=cart_count(),
        cart_total=cart_total(),
    )


# ------------------ checkout ------------------
@app.route("/checkout", methods=["POST"])
def checkout():
    items = cart_contents()
    if not items:
        abort(400)
    total = cart_total()

    if not STRIPE_SECRET:
        order_id = db.add_order(items, total)
        return redirect(url_for("checkout_success", order_id=order_id))

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
        order_id = db.add_order(items, total)
        return redirect(url_for("checkout_success", order_id=order_id))

    order_id = db.add_order(items, total, status="pending")
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=BASE_URL + url_for("checkout_success", order_id=order_id),
            cancel_url=BASE_URL + url_for("checkout_cancel", order_id=order_id),
        )
    except Exception as exc:  # pragma: no cover - network/Stripe errors
        app.logger.error("Stripe session error: %s", exc)
        db.set_order_status(order_id, "enquiry")
        return redirect(url_for("checkout_success", order_id=order_id))

    db.set_order_status(order_id, "pending")
    return redirect(checkout_session.url)


@app.route("/checkout/cancel")
def checkout_cancel():
    order_id = request.args.get("order_id", type=int)
    if order_id:
        db.set_order_status(order_id, "cancelled")
    return render_template("checkout_cancel.html", cart_count=cart_count())


@app.route("/checkout/success")
def checkout_success():
    order_id = request.args.get("order_id", type=int)
    order = db.get_order(order_id) if order_id else None
    if not order:
        abort(404)
    items = json.loads(order["items"] or "[]")
    session.pop("cart", None)
    return render_template("checkout_success.html", order=items, total=order["total"])


# ------------------ admin ------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if db.verify_admin(username, password):
            session["admin"] = username
            return redirect(url_for("admin_dashboard"))
        return render_template("admin/login.html", error="Invalid credentials")
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper


@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html", stats={
        "feedback": len(db.list_feedback()),
        "waitlist": len(db.list_waitlist()),
        "journey": len(db.list_journey_subscribers()),
        "bookings": len(db.list_bookings()),
        "contacts": len(db.list_contacts()),
        "orders": len(db.list_orders()),
        "products": len(db.list_products()),
        "files": len(db.list_files()),
        "recent_waitlist": db.list_waitlist()[:5],
        "recent_feedback": db.list_feedback()[:5],
    })


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
    if errors:
        flash("; ".join(errors), "error")
    if added:
        flash("%d file(s) uploaded." % added)
    return redirect(url_for("admin_files"))


@app.route("/admin/files/<int:file_id>/delete", methods=["POST"])
@admin_required
def admin_file_delete(file_id):
    f = db.get_file(file_id)
    if not f:
        abort(404)
    try:
        path = _upload_abs(f["path"])
        if os.path.isfile(path):
            os.remove(path)
        db.delete_file(file_id)
        flash("Deleted %s." % (f["name"] or f["path"]))
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_files"))


@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    return render_template("admin/feedback.html", items=db.list_feedback())


@app.route("/admin/feedback/<int:feedback_id>", methods=["POST"])
@admin_required
def admin_feedback_update(feedback_id):
    db.update_feedback(feedback_id, request.form.get("status", "new"), request.form.get("note", ""))
    return redirect(url_for("admin_feedback"))


@app.route("/admin/feedback/<int:feedback_id>/delete", methods=["POST"])
@admin_required
def admin_feedback_delete(feedback_id):
    db.delete_feedback(feedback_id)
    return redirect(url_for("admin_feedback"))


@app.route("/admin/waitlist")
@admin_required
def admin_waitlist():
    return render_template("admin/waitlist.html", items=db.list_waitlist())


@app.route("/admin/bookings")
@admin_required
def admin_bookings():
    return render_template("admin/bookings.html", items=db.list_bookings())


@app.route("/admin/bookings/<int:booking_id>/status", methods=["POST"])
@admin_required
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
def admin_order_status(order_id):
    db.set_order_status(order_id, request.form.get("status", "enquiry"))
    return redirect(url_for("admin_orders"))


# ------------------ admin: pages (CMS) ------------------

@app.route("/admin/pages")
@admin_required
def admin_pages():
    return render_template("admin/pages.html", pages=cms.PAGES)


@app.route("/admin/pages/<page>", methods=["GET", "POST"])
@admin_required
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
    return render_template("admin/page_edit.html", page_key=page, page_schema=schema,
                           stored=stored, media=media)


def _parse_cms_section(section, form):
    """Parse submitted form fields into a content dict per the field types."""
    content = {}
    for f in section["fields"]:
        key = f["key"]
        if f["type"] in ("text", "textarea", "longtext", "image"):
            content[key] = (form.get("field_%s" % key) or "").strip()
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
    return content


def _list_item_is_empty(item_schema, item):
    """True when every sub-field of a list item holds an empty value."""
    for sub_key, sub in item_schema.items():
        v = item.get(sub_key)
        if sub["type"] == "checkbox":
            if v:
                return False
        elif isinstance(v, list):
            if v:
                return False
        elif str(v or "").strip():
            return False
    return True


def _cms_section_is_empty(section, content):
    """True when every field holds an empty/default value (no real content)."""
    for f in section["fields"]:
        v = content.get(f["key"])
        if f["type"] == "list":
            if any(not _list_item_is_empty(f["item"], item) for item in (v or [])):
                return False
        elif f["type"] == "listlines":
            if v:
                return False
        elif f["type"] == "checkbox":
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
def admin_settings():
    if request.method == "POST":
        text_keys = ("store_hero_title", "store_hero_lede", "store_similar_title", "tools_heading",
                     "site_tagline", "site_email", "site_phone", "site_legal", "site_rc",
                     "booking_label", "booking_submit", "booking_cancel",
                     "booking_full_name", "booking_email", "booking_phone",
                     "booking_date", "booking_time", "booking_topic",
                     "booking_placeholder_full", "booking_placeholder_email",
                     "booking_placeholder_phone", "booking_placeholder_topic",
                     "booking_err_name", "booking_err_email", "booking_err_date", "booking_err_time",
                     "booking_confirm_title", "booking_confirm_body", "booking_confirm_close")
        boolean_keys = [k for k, _ in db.DEFAULT_SETTINGS.items()
                        if k not in ("price_public", "price_free_first", "price_commitment") + text_keys]
        mapping = {k: ("1" if k in request.form else "0") for k in boolean_keys}
        mapping["price_public"] = request.form.get("price_public", "0")
        mapping["price_free_first"] = request.form.get("price_free_first", "0")
        mapping["price_commitment"] = request.form.get("price_commitment", "0")
        for k in text_keys:
            mapping[k] = request.form.get(k, db.DEFAULT_SETTINGS.get(k, ""))
        db.set_settings(mapping)
        flash("Settings saved.")
        return redirect(url_for("admin_settings"))
    s = db.get_settings()
    return render_template("admin/settings.html", settings=s)


@app.route("/admin/password", methods=["GET", "POST"])
@admin_required
def admin_password():
    if request.method == "POST":
        new_pw = request.form.get("password", "")
        if len(new_pw) >= 8:
            db.set_admin_password(request.form.get("username", "admin"), new_pw)
            return redirect(url_for("admin_dashboard"))
    return render_template("admin/password.html", admin_user=session.get("admin", "admin"))


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


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 5000), debug=True)