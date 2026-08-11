"""Email notifications for admin alerts.

Sends notifications to the admin when a visitor submits a booking, order,
contact form, or feedback. Uses SMTP via stdlib smtplib — no extra deps.

Configuration (environment variables):
  SMTP_HOST       — SMTP server hostname (e.g. smtp.gmail.com)
  SMTP_PORT       — SMTP port (default: 587)
  SMTP_USERNAME   — SMTP login username
  SMTP_PASSWORD   — SMTP login password / app password
  ADMIN_EMAIL     — recipient address for notifications
  FROM_EMAIL      — sender address (defaults to SMTP_USERNAME)

If any of SMTP_HOST / ADMIN_EMAIL are unset, notifications are silently
skipped (and logged to the Flask logger) — the site keeps working.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _smtp_configured():
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("ADMIN_EMAIL"))


def _send(to, subject, body):
    if not _smtp_configured():
        logger.debug("email skipped (SMTP not configured): %s", subject)
        return False
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USERNAME") or os.environ.get("FROM_EMAIL") or os.environ["ADMIN_EMAIL"]
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("FROM_EMAIL") or user

    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(_html_body(body), "html"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            if port == 587:
                server.starttls()
                server.ehlo()
            if password:
                server.login(user, password)
            server.sendmail(sender, [to], msg.as_string())
        logger.info("email sent: %s -> %s", subject, to)
        return True
    except Exception as exc:
        logger.error("email failed (%s): %s", subject, exc)
        return False


def _html_body(text):
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = escaped.split("\n")
    items = "".join("<li>%s</li>" % ln.strip() for ln in lines if ln.strip())
    return "<ul>%s</ul>" % items if items else "<p>%s</p>" % escaped


def notify_booking(data):
    body = (
        "New discovery-call booking request:\n\n"
        "Name: %(name)s\n"
        "Email: %(email)s\n"
        "Phone: %(phone)s\n"
        "Date: %(date)s\n"
        "Time: %(time)s\n"
        "Message: %(message)s\n"
    ) % data
    return _send(os.environ["ADMIN_EMAIL"], "New Asa-OZ Booking Request", body)


def notify_order(items, total):
    lines = ["New Asa-OZ order:\n"]
    for it in items:
        lines.append("- %(qty)s × %(name)s (€%(price)s)" % it)
    lines.append("\nTotal: €%s" % total)
    return _send(os.environ["ADMIN_EMAIL"], "New Asa-OZ Order", "\n".join(lines))


def notify_contact(name, email, message):
    body = (
        "New contact message from the Asa-OZ website:\n\n"
        "From: %(name)s <%(email)s>\n\n"
        "%(message)s"
    ) % {"name": name, "email": email, "message": message}
    return _send(os.environ["ADMIN_EMAIL"], "New Asa-OZ Contact Message", body)


def notify_feedback(category, text):
    body = (
        "New feedback submitted on the Asa-OZ website:\n\n"
        "Category: %(category)s\n\n"
        "%(text)s"
    ) % {"category": category or "(none)", "text": text}
    return _send(os.environ["ADMIN_EMAIL"], "New Asa-OZ Feedback", body)


def notify_waitlist(email, source):
    body = "New Asa-OZ waitlist signup:\n\nEmail: %(email)s\nSource: %(source)s" % {
        "email": email,
        "source": source or "(none)",
    }
    return _send(os.environ["ADMIN_EMAIL"], "New Asa-OZ Waitlist Signup", body)
