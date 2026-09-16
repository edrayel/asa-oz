"""Admin alert emails.

Notifies the Asa-OZ admin when a visitor submits a booking, order, contact
form, feedback, newsletter signup or story. Delivery goes through mailer.py,
so there is one SMTP transport and one background queue for the whole app.

These are internal operations messages, not site copy, so their wording lives
here rather than in the CMS. Visitor-facing mail is templated and CMS-editable
(see mailer.py and the ``emails`` page in cms.py).

Every alert is skipped when SMTP is unconfigured, or when the admin turns
``email_admin_alerts`` off in Settings.
"""
import logging
import os

import db
import mailer

logger = logging.getLogger(__name__)


def is_configured():
    return mailer.is_configured()


def _alerts_enabled():
    try:
        return db.setting_bool("email_admin_alerts", "1")
    except Exception:
        return True


def _send(subject, body):
    if not _alerts_enabled():
        logger.debug("admin alert skipped (disabled): %s", subject)
        return False
    recipient = os.environ.get("ADMIN_EMAIL", "")
    if not recipient:
        logger.debug("admin alert skipped (no ADMIN_EMAIL): %s", subject)
        return False
    return mailer.send_raw(recipient, subject, body)


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
    return _send("New Asa-OZ Booking Request", body)


def notify_order(items, total, customer_email=""):
    lines = ["New Asa-OZ order:\n"]
    for it in items:
        lines.append("- %(qty)s × %(name)s (€%(price)s)" % it)
    lines.append("\nTotal: €%s" % total)
    if customer_email:
        lines.append("Email: %s" % customer_email)
    return _send("New Asa-OZ Order", "\n".join(lines))


def notify_contact(name, email, message):
    body = (
        "New contact message from the Asa-OZ website:\n\n"
        "From: %(name)s <%(email)s>\n\n"
        "%(message)s"
    ) % {"name": name, "email": email, "message": message}
    return _send("New Asa-OZ Contact Message", body)


def notify_feedback(category, text):
    body = (
        "New feedback submitted on the Asa-OZ website:\n\n"
        "Category: %(category)s\n\n"
        "%(text)s"
    ) % {"category": category or "(none)", "text": text}
    return _send("New Asa-OZ Feedback", body)


def notify_waitlist(email, source):
    body = "New Asa-OZ waitlist signup:\n\nEmail: %(email)s\nSource: %(source)s" % {
        "email": email,
        "source": source or "(none)",
    }
    return _send("New Asa-OZ Waitlist Signup", body)


def notify_subscriber(email, name="", source=""):
    body = (
        "New newsletter signup (awaiting confirmation):\n\n"
        "Email: %(email)s\n"
        "Name: %(name)s\n"
        "Source: %(source)s"
    ) % {"email": email, "name": name or "(none)", "source": source or "(none)"}
    return _send("New Asa-OZ Newsletter Signup", body)


def notify_story(title, author, author_email):
    body = (
        "A member submitted a story for review:\n\n"
        "Title: %(title)s\n"
        "Author: %(author)s\n"
        "Email: %(email)s\n\n"
        "It is saved as a draft. Review it under Stories in the admin."
    ) % {"title": title, "author": author or "(none)", "email": author_email or "(none)"}
    return _send("New Asa-OZ Story Submission", body)
