"""Shared Google credential loading for the Drive and Photos integrations.

One place resolves credential material from the environment, so ``drive.py``
and ``photos.py`` cannot drift apart on how they read a JSON blob.

The environment variable holds *either* a path to a JSON file *or* the JSON
payload itself. Four shapes are understood:

  * ``{"type": "authorized_user", "client_id": …, "client_secret": …,
    "refresh_token": …}`` — produced by ``authorize_google.py``. This is the
    recommended server credential: it acts as the Google account that granted
    consent, and refreshes its own access tokens.
  * an OAuth client file straight from the Cloud console
    (``{"web": {…}}`` / ``{"installed": {…}}``) — the envelope is unwrapped so
    the client id/secret can be read, but a client file alone carries **no
    refresh token**, so loading it raises with instructions to run the consent
    helper. This makes the common mistake self-explanatory instead of a
    confusing API error.
  * a service-account key — only accepted when the caller opts in via
    ``allow_service_account``. The Google Photos APIs do not support service
    accounts at all, so ``photos.py`` never opts in.
  * the bare ``{"client_id": …, "client_secret": …, "refresh_token": …}`` form
    without a ``type`` key.

Scopes are always requested explicitly at load time, so a token minted for more
scopes than a caller needs is still narrowed to what that caller asked for.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"

CLIENT_ENVELOPES = ("web", "installed")


class CredentialError(Exception):
    """Raised when credential material is missing or unusable."""


def _read_payload(env_var):
    raw = (os.environ.get(env_var) or "").strip()
    if not raw:
        raise CredentialError("%s is not set" % env_var)
    if os.path.isfile(raw):
        try:
            with open(raw, "r", encoding="utf-8") as fh:
                payload = fh.read()
        except OSError as exc:
            raise CredentialError("cannot read credentials file %s: %s" % (env_var, exc))
    else:
        payload = raw
    try:
        info = json.loads(payload)
    except ValueError as exc:
        raise CredentialError("%s is neither a readable file nor valid JSON: %s" % (env_var, exc))
    if not isinstance(info, dict):
        raise CredentialError("%s must contain a JSON object" % env_var)
    return info


def unwrap(info, env_var="credentials"):
    """Return the inner credential dict from a console client-secret file."""
    for key in CLIENT_ENVELOPES:
        inner = info.get(key)
        if isinstance(inner, dict):
            merged = dict(inner)
            # A hand-assembled blob may sit the refresh token alongside the
            # envelope rather than inside it.
            for extra in ("refresh_token", "scopes", "type", "quota_project_id"):
                if extra in info and extra not in merged:
                    merged[extra] = info[extra]
            return merged
    return info


def parse_client_file(payload):
    """Extract (client_id, client_secret, redirect_uris) from a client file."""
    info = unwrap(payload)
    client_id = (info.get("client_id") or "").strip()
    client_secret = (info.get("client_secret") or "").strip()
    redirect_uris = info.get("redirect_uris") or []
    if not client_id or not client_secret:
        raise CredentialError("client file has no client_id/client_secret")
    if not isinstance(redirect_uris, list):
        redirect_uris = []
    return client_id, client_secret, redirect_uris


def is_service_account(info):
    return info.get("type") == "service_account" or "client_email" in info


def has_refresh_token(info):
    return bool(info.get("refresh_token")) and bool(info.get("client_id"))


def load(env_var, scopes, allow_service_account=False):
    """Return google-auth credentials for ``env_var``, scoped to ``scopes``."""
    info = unwrap(_read_payload(env_var), env_var)

    if has_refresh_token(info):
        if not info.get("client_secret"):
            raise CredentialError(
                "%s has a refresh_token but no client_secret; re-run authorize_google.py" % env_var
            )
        from google.oauth2.credentials import Credentials as OAuthCredentials
        return OAuthCredentials(
            token=None,
            refresh_token=info["refresh_token"],
            client_id=info["client_id"],
            client_secret=info["client_secret"],
            token_uri=info.get("token_uri") or TOKEN_URI,
            scopes=scopes,
            quota_project_id=info.get("quota_project_id"),
        )

    if is_service_account(info):
        if not allow_service_account:
            raise CredentialError(
                "%s is a service account, which this API does not support; "
                "run authorize_google.py instead" % env_var
            )
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    # A console client file: readable, but it authorises nothing until a user
    # has granted consent and we hold the resulting refresh token.
    if info.get("client_id") and info.get("client_secret"):
        raise CredentialError(
            "%s is an OAuth *client* file, which carries no refresh token. "
            "Run `python authorize_google.py` once to grant consent, then point "
            "%s at the token file it writes." % (env_var, env_var)
        )

    raise CredentialError(
        "%s is not usable: expected an authorized-user token (client_id, "
        "client_secret, refresh_token), an OAuth client file, or a "
        "service-account key" % env_var
    )


def access_token(credentials):
    """Return a fresh bearer token, refreshing if the cached one has expired."""
    if not credentials.valid:
        from google.auth.transport.requests import Request
        credentials.refresh(Request())
    return credentials.token


def authorized_user_blob(client_id, client_secret, refresh_token, scopes, token_uri=TOKEN_URI):
    """Build the JSON payload written by ``authorize_google.py``."""
    return {
        "type": "authorized_user",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "token_uri": token_uri,
        "scopes": list(scopes),
    }


def scopes_of(info):
    """Scopes recorded in a credential payload (for diagnostics, no secrets)."""
    scopes = unwrap(info).get("scopes") or []
    return scopes if isinstance(scopes, list) else []
