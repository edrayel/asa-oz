"""Branded, non-blocking transactional email.

Two jobs:

1. Render. Visitor-facing copy lives in the CMS (the ``emails`` page), so the
   subject, heading and body are editable without a deploy. Templates in
   ``templates/emails/`` own the layout only.

2. Deliver without blocking the request. ``send()`` renders, then hands the
   message to a background worker thread, so a slow SMTP handshake can never
   stall a form POST. Set ``MAIL_SYNC=1`` to deliver inline (tests).

SMTP configuration is read from the environment only:

  SMTP_HOST       SMTP server hostname (e.g. smtppro.zoho.eu)
  SMTP_PORT       SMTP port (default 587)
  SMTP_USE_SSL    "1" to force implicit TLS. Defaults on for port 465.
  SMTP_USERNAME   login username
  SMTP_PASSWORD   login password / app password
  ADMIN_EMAIL     where admin alerts go, also the Reply-To
  FROM_EMAIL      sender; defaults to SMTP_USERNAME
  APP_URL         absolute base URL for links and the logo

If SMTP_HOST or ADMIN_EMAIL is unset every send is skipped and recorded as
such, and the forms carry on working exactly as before.

Credentials are never hard-coded here and never logged.
"""
import html
import logging
import os
import queue
import re
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

import cms
import db

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates", "emails")

# Kinds that carry a one-click unsubscribe header.
MARKETING_KINDS = {"newsletter_welcome"}

# Used only when the CMS subject field is left blank, so a message never sends
# with an empty subject.
FALLBACK_SUBJECTS = {
    "newsletter_confirm": "Confirm your email | Asa-OZ",
    "newsletter_welcome": "You are on the list | Asa-OZ",
    "contact_ack": "We have your message | Asa-OZ",
    "booking_confirm": "Your discovery call | Asa-OZ",
    "order_confirm": "Your Asa-OZ order | Asa-OZ",
    "story_ack": "We have your story | Asa-OZ",
    "admin": "Asa-OZ notification",
}

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _paragraphs(value):
    """Turn a CMS textarea into email-safe paragraphs."""
    out = []
    for block in re.split(r"\n\s*\n", str(value or "")):
        block = block.strip()
        if not block:
            continue
        out.append(
            '<p style="margin:0 0 14px;">%s</p>' % html.escape(block).replace("\n", "<br />")
        )
    return Markup("".join(out))


_env.filters["paragraphs"] = _paragraphs


# ---------- configuration ----------

CANONICAL_URL = "https://asa-oz.com"


def base_url():
    """Canonical public base URL, used for every absolute link the app emits.

    That covers emailed confirm and unsubscribe links, the logo, Stripe return
    URLs, OG tags and the sitemap. Override with APP_URL (a local run can point
    it at http://localhost:5000).

    The default is the live domain on purpose. Render's RENDER_EXTERNAL_URL
    resolves to the *.onrender.com host, and that must never end up in a mailed
    link or an indexed URL, so it is not used as a fallback.
    """
    return (os.environ.get("APP_URL") or CANONICAL_URL).strip().rstrip("/")


def _sender():
    return os.environ.get("FROM_EMAIL") or os.environ.get("SMTP_USERNAME") or ""


def _reply_to():
    return os.environ.get("ADMIN_EMAIL") or _sender()


def is_configured():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("ADMIN_EMAIL"))


def _use_implicit_ssl(port):
    """Implicit TLS (SMTPS) for port 465, or whenever SMTP_USE_SSL is truthy."""
    flag = os.environ.get("SMTP_USE_SSL", "").strip().lower()
    if flag:
        return flag not in ("0", "false", "no", "off")
    return port == 465


def _connect(host, port):
    """Open an SMTP connection, upgrading with STARTTLS when offered."""
    if _use_implicit_ssl(port):
        server = smtplib.SMTP_SSL(host, port, timeout=15)
        server.ehlo()
        return server
    server = smtplib.SMTP(host, port, timeout=15)
    server.ehlo()
    if server.has_extn("starttls"):
        server.starttls()
        server.ehlo()
    return server


# ---------- rendering ----------

def content():
    """CMS copy for every email, resolved with defaults from cms.PAGES."""
    return cms.resolve("emails", db.get_page_sections("emails"))


def _site():
    """Site-wide CMS fields (contact email, legal line), flattened."""
    out = {}
    for section in cms.resolve("sitewide", db.get_page_sections("sitewide")).values():
        out.update({k: v for k, v in section.items() if k != "active"})
    return out


def render(kind, ctx=None):
    """Return (subject, text_body, html_body) for one message kind."""
    copy = content()
    section = copy.get(kind) or {}
    footer = copy.get("footer") or {}
    site = _site()

    context = dict(ctx or {})
    context.update(
        section=section,
        footer=footer,
        site_email=site.get("email", ""),
        base_url=base_url(),
        marketing=kind in MARKETING_KINDS,
    )
    context.setdefault("unsubscribe_url", "")
    html_body = _env.get_template("%s.html" % kind).render(**context)
    subject = (section.get("subject") or "").strip() or FALLBACK_SUBJECTS.get(kind, "Asa-OZ")
    return subject, _html_to_text(html_body), html_body


_TAG_RE = re.compile(r"<(script|style|head)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_BREAK = "\x00"
_BREAK_RE = re.compile(r"<\s*(br|/p|/h1|/h2|/h3|/tr|/table|/div|/td)\s*/?\s*>", re.IGNORECASE)
_TAGS_RE = re.compile(r"<[^>]+>")


def _html_to_text(markup):
    """Plain-text alternative derived from the rendered HTML.

    Deriving it keeps the two alternatives in step with a single source of copy.
    Block-level tags become line breaks; the source's own newlines collapse to
    spaces so inline elements (a link, a separator) stay on one line.
    """
    text = _TAG_RE.sub("", markup)
    text = _BREAK_RE.sub(_BREAK, text)
    text = _TAGS_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split(_BREAK)]
    out = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip() + "\n"


# ---------- delivery ----------

def _log(kind, recipient, subject, status, error=""):
    try:
        db.log_email(kind, recipient, subject, status, error)
    except Exception:
        logger.warning("mailer: could not write email_log for %s", kind)


def _deliver(kind, recipient, subject, text, html_body, marketing, unsub_url=""):
    if not is_configured():
        _log(kind, recipient, subject, "skipped", "smtp-unconfigured")
        return False

    message = MIMEMultipart("alternative")
    message["From"] = formataddr(("Asa-OZ", _sender()))
    message["To"] = recipient
    message["Subject"] = subject
    if _reply_to():
        message["Reply-To"] = _reply_to()
    if marketing and unsub_url:
        message["List-Unsubscribe"] = "<%s>" % unsub_url
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.attach(MIMEText(text, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USERNAME") or _sender() or os.environ["ADMIN_EMAIL"]
    password = os.environ.get("SMTP_PASSWORD", "")

    try:
        server = _connect(host, port)
        try:
            if password:
                server.login(user, password)
            server.sendmail(_sender(), [recipient], message.as_string())
        finally:
            server.quit()
    except Exception as exc:
        # Log the class only: smtplib errors can echo the server banner.
        logger.error("mailer: %s failed (%s)", kind, type(exc).__name__)
        _log(kind, recipient, subject, "failed", type(exc).__name__)
        return False

    logger.info("mailer: %s sent", kind)
    _log(kind, recipient, subject, "sent")
    return True


_queue = queue.Queue()
_worker_lock = threading.Lock()
_worker_started = False


def _worker():
    while True:
        job = _queue.get()
        try:
            _deliver(**job)
        except Exception:
            logger.error("mailer: worker error", exc_info=True)
        finally:
            _queue.task_done()


def _ensure_worker():
    global _worker_started
    if _worker_started:
        return
    with _worker_lock:
        if _worker_started:
            return
        threading.Thread(target=_worker, name="asaoz-mailer", daemon=True).start()
        _worker_started = True


def _dispatch(kind, recipient, subject, text, html_body, marketing, unsub_url):
    job = dict(
        kind=kind,
        recipient=recipient,
        subject=subject,
        text=text,
        html_body=html_body,
        marketing=marketing,
        unsub_url=unsub_url,
    )
    if os.environ.get("MAIL_SYNC") == "1":
        return _deliver(**job)
    _ensure_worker()
    _queue.put(job)
    return True


def send(kind, recipient, ctx=None, marketing=None, unsub_url=""):
    """Render and queue one templated email. Never raises."""
    recipient = (recipient or "").strip()
    if not recipient or "@" not in recipient:
        return False
    if not str((content().get(kind) or {}).get("body", "")).strip():
        # An admin has blanked the copy for this message. Sending a bare shell
        # to a real person would be worse than not sending at all.
        logger.error("mailer: %s has no body copy, skipping", kind)
        _log(kind, recipient, "", "skipped", "empty-copy")
        return False
    try:
        subject, text, html_body = render(kind, ctx)
    except Exception as exc:
        logger.error("mailer: render failed for %s (%s)", kind, type(exc).__name__)
        _log(kind, recipient, "", "failed", "render:" + type(exc).__name__)
        return False
    if marketing is None:
        marketing = kind in MARKETING_KINDS
    if not unsub_url:
        # The template gets the link through the render context; the
        # List-Unsubscribe header needs the same URL, so pick it up from there.
        unsub_url = (ctx or {}).get("unsubscribe_url", "")
    return _dispatch(kind, recipient, subject, text, html_body, marketing, unsub_url)


def send_raw(recipient, subject, text, kind="admin"):
    """Plain notification (admin alerts), through the same queue and transport."""
    recipient = (recipient or "").strip()
    if not recipient:
        return False
    body = '<pre style="font-family:monospace; font-size:13px; white-space:pre-wrap;">%s</pre>' % html.escape(text)
    return _dispatch(kind, recipient, subject, text + "\n", body, False, "")


def drain(timeout=5):
    """Block until the queue is empty. Used by tests."""
    _queue.join()
