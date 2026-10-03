"""Google Photos integration via the Picker API (admin media library).

Why the Picker API and not the Library API: Google removed the
``photoslibrary.readonly``, ``photoslibrary.sharing`` and ``photoslibrary``
scopes on 1 April 2025. The Library API can now only read media that the app
itself uploaded, so there is no longer any server-side way to browse a user's
existing Google Photos library. The Picker API is the only supported route: the
user selects items in Google Photos and the app may then read back exactly those
selections.

The flow is interactive by design and cannot be automated away:

  1. ``create_session()``  -> a ``pickerUri`` the user opens in a browser
  2. the user selects photos inside Google Photos
  3. ``get_session()``     -> ``mediaItemsSet`` flips to true
  4. ``list_media_items()`` -> the picks, each with a short-lived ``baseUrl``
  5. download the bytes and store them like any other upload

Because a picked item's ``baseUrl`` expires, a pick is always **imported**
(bytes copied into UPLOAD_DIR). There is no "link" mode equivalent to the Drive
integration, which streams from a stable file id.

Configuration (environment variables):

  GOOGLE_PHOTOS_CREDENTIALS
      Path to a JSON file, or the JSON payload itself — the authorized-user
      token from ``authorize_google.py``. Scope:
      ``photospicker.mediaitems.readonly``. The Photos APIs do not support
      service accounts, so a service-account key is rejected here.

The app degrades gracefully: without credentials the admin Photos page explains
the setup and every other feature keeps working.
"""
import logging
import os
from urllib.parse import quote, urlsplit, urlunsplit

import requests

import google_creds

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
API_BASE = "https://photospicker.googleapis.com/v1"
# Appending `=d` asks the media host for the original bytes rather than a
# resized rendition. Some media URLs reject it, so a download retries without.
ORIGINAL_SUFFIX = "=d"

_TOKEN_CACHE = {}


class PhotosError(Exception):
    """Raised for any Google Photos API / configuration failure."""


def is_configured():
    """True when Google Photos credentials are configured."""
    return bool((os.environ.get("GOOGLE_PHOTOS_CREDENTIALS") or "").strip())


def _credentials():
    try:
        return google_creds.load("GOOGLE_PHOTOS_CREDENTIALS", SCOPES)
    except google_creds.CredentialError as exc:
        raise PhotosError(str(exc))


def _access_token():
    creds = _TOKEN_CACHE.get("creds")
    if creds is None:
        creds = _credentials()
        _TOKEN_CACHE["creds"] = creds
    try:
        return google_creds.access_token(creds)
    except Exception as exc:  # google.auth RefreshError and friends
        logger.warning("photos: token refresh failed: %s", _exc_text(exc))
        raise PhotosError("Photos token refresh failed: %s" % _exc_text(exc))


def _request(method, path, *, params=None, json_body=None, stream=False, url=None):
    """Call the Picker API (or an absolute media URL) with a bearer token."""
    target = url or (API_BASE + path)
    try:
        resp = requests.request(
            method,
            target,
            params=params,
            json=json_body,
            headers={"Authorization": "Bearer %s" % _access_token()},
            stream=stream,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.warning("photos.%s network error %s: %s", method, path or target, exc)
        raise PhotosError("Photos request failed: %s" % exc)
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        logger.warning("photos.%s HTTP %s %s", method, resp.status_code, path or target)
        resp.close()
        raise PhotosError("Photos API %s failed with HTTP %s%s" % (
            method, resp.status_code, (": " + detail) if detail else ""))
    return resp


def create_session(max_items=None):
    """Create a picking session; returns the PickingSession dict."""
    body = {}
    params = {}
    if max_items:
        # Documented cap; Google coerces anything above 2000.
        body["pickingConfig"] = {"maxItemCount": str(min(int(max_items), 2000))}
    # A UUIDv4 requestId enables the limited-input-device picking flow, which
    # matters when the user completes the pick on a phone.
    params["requestId"] = _uuid4()
    resp = _request("POST", "/sessions", params=params, json_body=body)
    session = resp.json()
    if not session.get("pickerUri"):
        raise PhotosError("Photos returned a session without a picker URI")
    logger.info("photos.create_session ok id=%s mediaItemsSet=%s",
                session.get("id"), session.get("mediaItemsSet"))
    return session


def get_session(session_id):
    """Retrieve a picking session (used to poll for completion)."""
    if not session_id:
        raise PhotosError("missing session id")
    return _request("GET", "/sessions/%s" % quote(str(session_id), safe="")).json()


def delete_session(session_id):
    """Delete a picking session. Best-effort: failure is logged, not raised."""
    if not session_id:
        return False
    try:
        _request("DELETE", "/sessions/%s" % quote(str(session_id), safe=""))
        logger.info("photos.delete_session ok id=%s", session_id)
        return True
    except PhotosError as exc:
        logger.warning("photos.delete_session failed id=%s: %s", session_id, exc)
        return False


def list_media_items(session_id, page_token=None, page_size=50):
    """List the items picked in a session; returns (items, next_page_token).

    Google returns FAILED_PRECONDITION while the user is still picking, which
    surfaces here as a PhotosError."""
    if not session_id:
        raise PhotosError("missing session id")
    params = {"sessionId": session_id, "pageSize": min(int(page_size), 100)}
    if page_token:
        params["pageToken"] = page_token
    data = _request("GET", "/mediaItems", params=params).json()
    items = data.get("mediaItems", []) or []
    logger.info("photos.list_media_items ok session=%s count=%d", session_id, len(items))
    return items, data.get("nextPageToken")


def all_media_items(session_id, page_size=100, max_items=500):
    """Page through every picked item in a session."""
    items, token = [], None
    while True:
        page, token = list_media_items(session_id, page_token=token, page_size=page_size)
        items.extend(page)
        if not token or len(items) >= max_items:
            break
    return items[:max_items]


def download(base_url):
    """Open a streaming download of a picked media item.

    Returns an open ``requests.Response``; callers hand ``response.raw`` to the
    app's upload path and must close it. Falls back to the bare ``baseUrl`` when
    the media host rejects the "original bytes" suffix."""
    if not base_url:
        raise PhotosError("missing media base URL")
    try:
        resp = _request("GET", None, url=base_url + ORIGINAL_SUFFIX, stream=True)
        logger.info("photos.download ok (original bytes)")
        return resp
    except PhotosError as exc:
        logger.warning("photos.download original bytes refused (%s); retrying bare URL", exc)
    resp = _request("GET", None, url=base_url, stream=True)
    logger.info("photos.download ok (resized rendition)")
    return resp


def poll_hint(session):
    """Whole seconds to wait before the next poll, from the session's pollingConfig."""
    config = session.get("pollingConfig") or {}
    # Google returns a duration, so this parses to a float. The value is used as a
    # refresh interval and as prose ("every N seconds"), so it is rounded down to
    # a whole number rather than surfacing as "4.0".
    return max(2, int(_duration_seconds(config.get("pollInterval"), default=3)))


def picker_url(session, autoclose=True):
    """The picker URI to hand the user, optionally with ``/autoclose``.

    Google closes the Google Photos tab itself once picking finishes, which
    avoids leaving the user on a dead "Done" screen. The suffix is inserted
    before any query string rather than naively appended."""
    uri = session.get("pickerUri") or ""
    if not uri or not autoclose:
        return uri
    parts = urlsplit(uri)
    path = parts.path.rstrip("/") + "/autoclose"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _duration_seconds(value, default=0):
    """Parse a google-duration string such as ``"3s"`` or ``"1.5s"``."""
    if not value or not isinstance(value, str):
        return default
    text = value.strip().lower()
    try:
        if text.endswith("ms"):
            return float(text[:-2]) / 1000.0
        if text.endswith("s"):
            return float(text[:-1])
    except ValueError:
        return default
    return default


def _uuid4():
    import uuid
    return str(uuid.uuid4())


def _error_detail(resp):
    try:
        body = resp.json()
    except ValueError:
        return (resp.text or "")[:200]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err.get("status") or "")[:200]
    return ""


def _exc_text(exc):
    """A short, human-readable description of an auth or transport exception.

    Google's own message is appended when the exception carries a raw HTTP body,
    so an operator sees ``invalid_grant`` rather than a bare reason string. The
    body read is best-effort: it is a response attribute that may be absent or
    undecodable, and losing the detail must never mask the original error.
    """
    msg = getattr(exc, "reason", None) or str(exc)
    try:
        details = getattr(exc, "resp", None)
        if details is not None:
            msg = "%s (%s)" % (msg, details.get("content", "").decode("utf-8", "replace")[:300])
    except Exception:
        pass
    return msg[:300]
