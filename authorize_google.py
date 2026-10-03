#!/usr/bin/env python3
"""One-time OAuth consent for the Google Drive and Google Photos integrations.

The provided credential is a *Web* OAuth client, which authorises nothing on its
own: it only proves which app is asking. To let the server read Drive (and, if
you opt in, run the Photos Picker) you must consent once as the Google account
that owns the content. This script performs that consent flow and writes the
resulting refresh token to a JSON blob the app can use.

Usage:

    .venv/bin/python authorize_google.py                 # Drive + Photos scopes
    .venv/bin/python authorize_google.py --scopes drive  # Drive only
    .venv/bin/python authorize_google.py --scopes photos # Photos only

The consent must land on a redirect URI registered on the OAuth client. The
default (``http://localhost:5000/auth/callback``) is already registered, so the
script runs a throwaway HTTP listener on that host/port and no Cloud Console
change is needed. Nothing about the app's Flask routes is involved.

The refresh token is written OUTSIDE the repo, one file per credential, to match
the rest of this project's secret handling. Never commit it.

Security notes:
  * PKCE (S256) is used even though this is a confidential client.
  * No secret is ever printed; only the granted scopes and the output path are.
  * The token file is created with mode 600.
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import requests

import google_creds

DEFAULT_OUT = os.path.expanduser("~/.config/opencode/keys/asa-oz_google_oauth_token.json")
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

SCOPE_SETS = {
    "drive": [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
    ],
    "photos": ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"],
}
SCOPE_SETS["both"] = SCOPE_SETS["drive"] + SCOPE_SETS["photos"]
SCOPE_SETS["all"] = SCOPE_SETS["both"]

# Common Google error codes mapped to the actual fix, so a failed probe is
# actionable rather than a bare error string.
DIAGNOSIS = {
    "invalid_scope": (
        "Google rejected the scope list. Either the API is not enabled on this "
        "Cloud project, or the scope is missing from the OAuth consent screen. "
        "Enable it under APIs & Services -> Library, then add the scope under "
        "APIs & Services -> OAuth consent screen -> Data access."
    ),
    "redirect_uri_mismatch": (
        "The redirect URI used here is not registered on the OAuth client. "
        "Add it under APIs & Services -> Credentials, or pick one that is."
    ),
    "access_denied": (
        "Consent was refused. If this is a Testing-mode app, the signed-in "
        "account must be listed under OAuth consent screen -> Test users."
    ),
    "invalid_client": "The client id/secret pair was rejected; re-download the client file.",
    "invalid_grant": "The code was already used, expired, or does not match this client.",
}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Receives the single ``?code=…`` redirect, then stops the server."""

    result = {}
    done = threading.Event()

    def do_GET(self):  # noqa: N802 - stdlib naming
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != self.redirect_path:
            self.send_error(404, "not the callback path")
            return
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.result = {
            "code": (params.get("code") or [None])[0],
            "state": (params.get("state") or [None])[0],
            "error": (params.get("error") or [None])[0],
        }
        body = self._page(self.result.get("error"))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        _CallbackHandler.done.set()

    @staticmethod
    def _page(error):
        if error:
            note = "<p>Consent failed: <code>%s</code>. You can close this tab.</p>" % error
        else:
            note = "<p>Consent received. You can close this tab and return to the terminal.</p>"
        html = (
            "<!doctype html><meta charset=utf-8><title>Asa-OZ Google authorisation</title>"
            "<body style=\"font-family:system-ui;margin:4rem auto;max-width:32rem;line-height:1.5\">"
            "<h1 style=\"font-size:1.1rem\">Google authorisation</h1>%s</body>" % note
        )
        return html.encode("utf-8")

    def log_message(self, *_args):
        pass  # keep the terminal output to the script's own messaging


def _find_client_file(explicit):
    if explicit:
        return explicit
    env = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRETS", "").strip()
    if env:
        return env
    import glob
    matches = sorted(glob.glob(os.path.join(REPO_DIR, "client_secret*.json")))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(
            "No client_secret*.json found in %s. Pass --client-secrets PATH." % REPO_DIR
        )
    raise SystemExit(
        "Multiple client_secret*.json files found; pass --client-secrets PATH explicitly."
    )


def _pick_redirect(redirect_uris, port):
    """Choose the loopback redirect to use, preferring a registered one."""
    loopbacks = []
    for uri in redirect_uris:
        parsed = urllib.parse.urlparse(uri)
        if parsed.hostname in ("localhost", "127.0.0.1"):
            loopbacks.append(parsed)
    if not loopbacks:
        raise SystemExit(
            "None of the registered redirect URIs is a loopback address:\n  %s\n"
            "Add http://localhost:%d/auth/callback in the Cloud Console."
            % ("\n  ".join(redirect_uris) or "(none registered)", port)
        )
    chosen = next((p for p in loopbacks if p.port == port), None) or (
        loopbacks[0] if port is None else None
    )
    if chosen is None:
        raise SystemExit(
            "No registered loopback redirect uses port %d. Registered: %s\n"
            "Either re-run with the registered port, or add "
            "http://localhost:%d/auth/callback in the Cloud Console."
            % (port, ", ".join(p.geturl() for p in loopbacks), port)
        )
    return chosen.geturl(), (chosen.port or 80), chosen.path or "/auth/callback"


def _pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _diagnose(error_code, detail):
    hint = DIAGNOSIS.get(error_code)
    if hint:
        print("\n  %s" % hint, file=sys.stderr)
    if detail:
        print("  Google said: %s" % detail, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scopes", default="both", choices=sorted(SCOPE_SETS),
                        help="which consent to request (default: both)")
    parser.add_argument("--client-secrets", help="path to the OAuth client JSON")
    parser.add_argument("--out", default=DEFAULT_OUT, help="where to write the token blob")
    parser.add_argument("--port", type=int, help="loopback port (default: the registered one)")
    parser.add_argument("--no-browser", action="store_true",
                        help="print the URL instead of opening a browser")
    parser.add_argument("--timeout", type=int, default=300,
                        help="seconds to wait for the redirect (default: 300)")
    args = parser.parse_args()

    client_file = _find_client_file(args.client_secrets)
    with open(client_file, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    client_id, client_secret, redirect_uris = google_creds.parse_client_file(payload)

    scopes = SCOPE_SETS[args.scopes]
    redirect_uri, port, callback_path = _pick_redirect(redirect_uris, args.port)

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        # Force the refresh token to be reissued: without prompt=consent a repeat
        # run returns only an access token and the flow is wasted.
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = google_creds.AUTH_URI + "?" + urllib.parse.urlencode(auth_params)

    _CallbackHandler.redirect_path = callback_path
    _CallbackHandler.result = {}
    _CallbackHandler.done.clear()

    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _CallbackHandler)
    except OSError as exc:
        raise SystemExit(
            "Cannot listen on 127.0.0.1:%d (%s).\n"
            "The registered redirect is %s, so that port must be free. "
            "Stop whatever holds it, or re-run with --port for another registered port."
            % (port, exc, redirect_uri)
        )
    server.timeout = 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("Scopes requested:")
    for scope in scopes:
        print("  - %s" % scope)
    print("Redirect URI:  %s" % redirect_uri)
    print("Token will be written to: %s" % args.out)
    print("\nOpen this URL and approve access:\n\n%s\n" % auth_url)
    if not args.no_browser:
        webbrowser.open(auth_url)

    if not _CallbackHandler.done.wait(timeout=args.timeout):
        server.shutdown()
        server.server_close()
        raise SystemExit("Timed out after %ds waiting for the redirect." % args.timeout)
    server.shutdown()
    server.server_close()

    result = _CallbackHandler.result
    if result.get("error"):
        _diagnose(result["error"], None)
        raise SystemExit(1)
    if result.get("state") != state:
        raise SystemExit("State mismatch on the redirect; aborting without exchanging the code.")
    if not result.get("code"):
        raise SystemExit("No authorization code in the redirect.")

    token_resp = requests.post(google_creds.TOKEN_URI, data={
        "code": result["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }, timeout=30)

    if token_resp.status_code != 200:
        try:
            err = token_resp.json()
        except ValueError:
            err = {}
        code = err.get("error", "http_%d" % token_resp.status_code)
        print("\nToken exchange failed: %s" % code, file=sys.stderr)
        _diagnose(code, err.get("error_description"))
        raise SystemExit(1)

    tokens = token_resp.json()
    refresh_token = tokens.get("refresh_token")
    granted = (tokens.get("scope") or "").split()

    if not refresh_token:
        print(
            "\nGoogle returned no refresh_token. This normally means consent was "
            "already granted for this client and account; revoke it at "
            "https://myaccount.google.com/permissions and re-run.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    blob = google_creds.authorized_user_blob(client_id, client_secret, refresh_token, granted)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    # Create with restrictive permissions, then write: never a world-readable window.
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=2)
            fh.write("\n")
    except Exception:
        os.chmod(args.out, 0o600)
        raise
    os.chmod(args.out, 0o600)

    print("\nConsent complete.")
    print("Granted scopes:")
    for scope in granted or ["(none reported)"]:
        print("  - %s" % scope)
    print("Refresh token: obtained (not shown)")
    print("Written to:    %s (mode 600)" % args.out)
    print(
        "\nNext: export the environment so the app picks it up, e.g.\n"
        "  export GOOGLE_DRIVE_CREDENTIALS=\"$(cat %s)\"\n"
        "  export GOOGLE_PHOTOS_CREDENTIALS=\"$(cat %s)\"\n"
        "or point both at the file path: GOOGLE_DRIVE_CREDENTIALS=%s"
        % (args.out, args.out, args.out)
    )


if __name__ == "__main__":
    main()
