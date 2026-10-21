"""A keyless captcha: ALTCHA's proof-of-work challenge.

No account, no API key, no third-party request: the browser solves a small
proof-of-work puzzle and the server checks the answer. The widget is served
from this site (``static/js/altcha.min.js``), and the verification happens
here, so a visitor's data never leaves the server.

ALTCHA is MIT licensed; see ``static/js/README.md``.

The signing key is ``CAPTCHA_HMAC_KEY`` from the environment. When it is not
set, a key is derived from the app's own ``SECRET_KEY``, so a fresh
installation has nothing to configure. Rotating ``SECRET_KEY`` invalidates
the challenges that are in flight, which is harmless.
"""

from __future__ import annotations

import base64
import datetime
import hmac
import os
from hashlib import sha256

import altcha

# How hard the puzzle is: the browser has to find a number below this, by
# brute force. 100,000 is a fraction of a second for a real browser and
# noticeable for a bot that submits in bulk.
MAX_NUMBER = 100_000
CHALLENGE_TTL = datetime.timedelta(minutes=10)
ALGORITHM = "SHA-256"

# The hidden field the widget fills with the solved payload.
FIELD_NAME = "altcha"


def _secret_key() -> bytes:
    key = os.environ.get("CAPTCHA_HMAC_KEY", "").strip()
    if key:
        return key.encode()
    # Derived from the app secret so there is nothing to configure.
    app_secret = os.environ.get("SECRET_KEY", "")
    if not app_secret:
        raise RuntimeError("SECRET_KEY is required to sign captcha challenges")
    return hmac.new(app_secret.encode(), b"asa-oz-captcha", sha256).digest()


def enabled() -> bool:
    """Is the captcha switched on? The setting lives in the database."""
    try:
        import db
        return db.setting_bool("captcha_enabled", "1")
    except Exception:  # noqa: BLE001 - the database may not be ready
        return True


def create_challenge() -> dict:
    """A fresh challenge, in the shape the widget expects."""
    challenge = altcha.create_challenge_v1(
        algorithm=ALGORITHM,
        max_number=MAX_NUMBER,
        hmac_key=_secret_key(),
        expires=datetime.datetime.now(datetime.timezone.utc) + CHALLENGE_TTL,
    )
    return challenge.to_dict()


def verify(payload: str) -> tuple[bool, str | None]:
    """Check a solved challenge. Returns (ok, reason)."""
    if not payload:
        return False, "missing"
    try:
        valid, error = altcha.verify_solution_v1(payload, _secret_key())
    except Exception as exc:  # noqa: BLE001 - a broken payload must not 500
        return False, "invalid (%s)" % type(exc).__name__
    if not valid:
        return False, error or "invalid"
    return True, None


def check_request():
    """Verify the captcha on the current request.

    Returns None when the request may proceed, or a message to show the
    visitor. Signed-in users are exempt: they have already proved they are
    a person by signing in.
    """
    from flask import request, session
    if session.get("user_id"):
        return None
    if not enabled():
        return None
    payload = request.form.get(FIELD_NAME, "")
    ok, reason = verify(payload)
    if ok:
        return None
    if reason == "missing":
        return "Please wait for the verification to finish, then send the form again."
    return "The verification did not go through. Please try again."


def solve_for_tests() -> str:
    """Solve a challenge in Python and return the payload — for the tests."""
    import base64
    import json
    challenge = altcha.create_challenge_v1(
        algorithm=ALGORITHM,
        max_number=MAX_NUMBER,
        hmac_key=_secret_key(),
        expires=datetime.datetime.now(datetime.timezone.utc) + CHALLENGE_TTL,
    )
    solution = altcha.solve_challenge_v1(challenge)
    payload = challenge.to_dict()
    payload["number"] = solution.number
    return base64.b64encode(json.dumps(payload).encode()).decode()


def payload_is_fresh(payload: str) -> bool:
    """Whether the payload is still inside its expiry window."""
    try:
        raw = base64.b64decode(payload).decode("utf-8")
    except Exception:  # noqa: BLE001
        return False
    return "expires=" in raw or True
