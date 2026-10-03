"""Google Drive integration for the admin media library.

Uses the official Google libraries — ``google-api-python-client`` (Drive API
v3) for metadata and listing, ``google-auth`` for credentials, and
``requests`` (already a google-auth dependency) for byte streaming.

Two ways files reach the frontend:

  * Import  — bytes are downloaded into ``UPLOAD_DIR`` and recorded in the DB
    (``source='drive-import'``). Served by the normal ``/media/<path>`` route.
  * Link    — a record (``source='drive'``) whose ``/media/drive/<id>/<name>``
    URL streams bytes live from Google Drive through the app.

Configuration (environment variables):

  GOOGLE_DRIVE_CREDENTIALS
      Path to a JSON file, or the JSON payload itself. Normally the
      authorized-user token written by ``authorize_google.py``, which acts as
      the Google account that granted consent. A service-account key is also
      accepted here (unlike the Photos integration, the Drive API supports
      them); share the target folder with the service account's email.
      Scope used: ``drive.readonly``.

  GOOGLE_DRIVE_FOLDER_ID
      Id of the Drive folder shown in the admin browser (optional; defaults to
      the account's My Drive).

A bare OAuth *client* file from the Cloud console is not sufficient on its own:
it proves which app is asking but carries no refresh token. ``google_creds``
detects that case and the error tells the operator to run the consent helper.

The app degrades gracefully: without credentials the admin Drive page explains
the setup and every other feature keeps working.
"""
import logging
import os
from urllib.parse import quote

import requests

import google_creds

logger = logging.getLogger(__name__)

# Mime types that Google stores natively and cannot be downloaded as raw bytes
# (importing those would require an export step, which is out of scope).
GOOGLE_NATIVE_MIMES = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.shortcut",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.slides",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
    "application/vnd.google-apps.script",
    "application/vnd.google-apps.site",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.photo",
    "application/vnd.google-apps.apps.folder",
    "application/vnd.google-apps.drive-sdk",
}

# ``drive.readonly`` browses and links files that already exist; ``drive.file``
# is the narrow write scope — it permits creating folders and uploading files
# the app owns, while still leaving the rest of the account untouched.
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

_CREDS = None
_SERVICE = None


class DriveError(Exception):
    """Raised for any Google Drive API / configuration failure."""


def is_configured():
    """True when Google Drive credentials are configured."""
    raw = os.environ.get("GOOGLE_DRIVE_CREDENTIALS", "").strip()
    return bool(raw)


def root_folder_id():
    return (os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip() or None


def _credentials():
    """Load (and cache) google-auth credentials from the environment."""
    global _CREDS
    if _CREDS is None:
        try:
            _CREDS = google_creds.load(
                "GOOGLE_DRIVE_CREDENTIALS", SCOPES, allow_service_account=True
            )
        except google_creds.CredentialError as exc:
            raise DriveError(str(exc))
    return _CREDS


def _access_token():
    try:
        return google_creds.access_token(_credentials())
    except DriveError:
        # Already a clear configuration message; don't bury it in a wrapper.
        raise
    except Exception as exc:  # google.auth RefreshError and friends
        logger.warning("drive: token refresh failed: %s", _exc_text(exc))
        raise DriveError("Drive token refresh failed: %s" % _exc_text(exc))


def _service():
    """Build (and cache) the Drive API v3 client."""
    global _SERVICE
    if _SERVICE is None:
        from googleapiclient.discovery import build
        try:
            _SERVICE = build("drive", "v3", credentials=_credentials(), cache_discovery=False)
        except google_creds.CredentialError as exc:
            raise DriveError(str(exc))
    return _SERVICE


def _annotate(item):
    mime = item.get("mimeType", "")
    item["is_folder"] = mime == "application/vnd.google-apps.folder"
    item["is_binary"] = mime not in GOOGLE_NATIVE_MIMES
    return item


def _q_value(value):
    return str(value).replace("'", "''")


def root_label():
    """Human-readable name of the configured root folder."""
    folder = root_folder_id()
    if not folder:
        return "My Drive"
    try:
        return get_metadata(folder).get("name") or folder
    except DriveError as exc:
        logger.warning("drive.root_label failed for %s: %s", folder, _exc_text(exc))
        return folder


def get_metadata(file_id):
    """Metadata for a single Drive item (folders included)."""
    if not file_id:
        raise DriveError("missing file id")
    try:
        res = _service().files().get(
            fileId=file_id,
            supportsAllDrives=True,
            fields="id,name,mimeType,size,parents,thumbnailLink,iconLink,webViewLink,modifiedTime",
        ).execute()
    except Exception as exc:  # googleapiclient.HttpError and friends
        logger.warning("drive.get_metadata failed for %s: %s", file_id, _exc_text(exc))
        raise DriveError("Drive lookup failed for %r: %s" % (file_id, _exc_text(exc)))
    return _annotate(res)


def list_folder(folder_id=None, page_token=None, page_size=50):
    """List children of a folder; returns (items, next_page_token).

    ``folder_id`` defaults to the configured root folder (or My Drive). Items
    are dicts annotated with ``is_folder`` / ``is_binary``; only non-trash
    items are returned."""
    folder = folder_id or root_folder_id() or "root"
    query = "'%s' in parents and trashed = false" % _q_value(folder)
    try:
        req = _service().files().list(
            q=query,
            pageToken=page_token,
            pageSize=page_size,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="nextPageToken, files(id, name, mimeType, size, thumbnailLink, iconLink, webViewLink, modifiedTime)",
        )
        res = req.execute()
    except Exception as exc:
        logger.warning("drive.list_folder failed for folder=%s: %s", folder, _exc_text(exc))
        raise DriveError("Drive listing failed: %s" % _exc_text(exc))
    files = [_annotate(f) for f in res.get("files", [])]
    # Keep folders (for navigation) and binary files; hide Google-native items
    # (Docs/Sheets/Slides/…) that cannot be fetched or streamed as raw bytes.
    files = [f for f in files if f["is_folder"] or f["is_binary"]]
    return files, res.get("nextPageToken")


def stream_download(file_id, chunk_size=64 * 1024):
    """Open a streaming download for a Drive file.

    Returns a ``requests.Response`` opened in stream mode; callers iterate
    ``response.iter_content(chunk_size)`` (or pass ``response.raw`` to a
    consumer that reads it) and must close the response when done."""
    url = "https://www.googleapis.com/drive/v3/files/%s?alt=media&supportsAllDrives=true" % quote(
        str(file_id), safe=""
    )
    try:
        resp = requests.get(
            url,
            headers={"Authorization": "Bearer %s" % _access_token()},
            stream=True,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.warning("drive.stream_download network error for %s: %s", file_id, exc)
        raise DriveError("Drive download failed: %s" % exc)
    if resp.status_code != 200:
        logger.warning("drive.stream_download HTTP %s for %s", resp.status_code, file_id)
        resp.close()
        raise DriveError("Drive download failed with HTTP %s" % resp.status_code)
    logger.info("drive.stream_download ok file=%s status=200", file_id)
    return resp


def iter_chunks(response, chunk_size=64 * 1024):
    """Yield raw bytes from an open streaming ``requests.Response``."""
    try:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                yield chunk
    finally:
        response.close()


def _exc_text(exc):
    msg = getattr(exc, "reason", None) or str(exc)
    try:
        details = getattr(exc, "resp", None)
        if details is not None:
            msg = "%s (%s)" % (msg, details.get("content", "").decode("utf-8", "replace")[:300])
    except Exception:
        pass
    return msg
