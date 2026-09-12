"""Lightweight CSRF protection for the Asa-OZ Flask app.

Generates a per-session token at first use; the token is rendered into every
POST form via ``{{ csrf_input() }}`` (a Jinja global registered in app.py) and
validated on submit by ``@require_csrf`` or by the explicit ``validate()``
helper. Tokens are compared in constant time via ``hmac.compare_digest``.
"""
import hmac
import secrets
from functools import wraps

from flask import abort, request, session
from markupsafe import Markup

FIELD = "_csrf"
_SESSION_KEY = "_csrf_token"


def _token():
    tok = session.get(_SESSION_KEY)
    if not tok:
        tok = secrets.token_urlsafe(32)
        session[_SESSION_KEY] = tok
        session.modified = True
    return tok


def generate():
    """Return the current session's CSRF token (creating it on first use)."""
    return _token()


def render_input():
    """Return an ``<input type="hidden" ...>`` for inclusion in a POST form."""
    return Markup(f'<input type="hidden" name="{FIELD}" value="{_token()}">')


def validate():
    """Validate the submitted form's CSRF token against the session token.

    Returns ``True`` on success, ``False`` otherwise. Callers may want to
    ``abort(400)`` on a ``False`` return — the ``@require_csrf`` decorator does
    this for you.
    """
    expected = session.get(_SESSION_KEY)
    if not expected:
        return False
    submitted = request.form.get(FIELD, "")
    if not submitted:
        return False
    return hmac.compare_digest(str(expected), str(submitted))


def require_csrf(view):
    """Decorator: reject POSTs whose CSRF token doesn't match the session."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not validate():
            abort(400, "CSRF token missing or invalid")
        return view(*args, **kwargs)

    return wrapper
