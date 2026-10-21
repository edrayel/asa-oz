"""Local E2E test server.

Starts the Asa-OZ app against an isolated SQLite database and upload
directory so an end-to-end run never touches the real data, and never
sends mail.

Run it directly (or let ``tests/e2e_audit.py`` start it for you):

    .venv/bin/python tests/e2e_server.py --port 5055

Environment overrides (defaults in brackets):

    ASAOZ_TEST_DB      [tests/.e2e/asaoz-e2e.sqlite3]
    ASAOZ_TEST_UPLOADS [tests/.e2e/uploads]
    ASAOZ_TEST_PORT    [5055]
    ASAOZ_ADMIN_USER   [admin]
    ASAOZ_ADMIN_PASS   [e2e-admin-password]

SMTP is deliberately left unconfigured: ``mailer.is_configured()`` returns
False, so every send is recorded as ``skipped`` instead of being delivered.
"""

import argparse
import os
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("ASAOZ_TEST_PORT", "5055")))
    parser.add_argument("--db", default=os.environ.get("ASAOZ_TEST_DB", str(HERE / ".e2e" / "asaoz-e2e.sqlite3")))
    parser.add_argument("--uploads", default=os.environ.get("ASAOZ_TEST_UPLOADS", str(HERE / ".e2e" / "uploads")))
    parser.add_argument("--user", default=os.environ.get("ASAOZ_ADMIN_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("ASAOZ_ADMIN_PASS", "e2e-admin-password"))
    parser.add_argument("--fresh", action="store_true", help="delete the test database before starting")
    args = parser.parse_args()

    db_path = pathlib.Path(args.db).resolve()
    upload_dir = pathlib.Path(args.uploads).resolve()
    if args.fresh and db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "e2e-secret-key-not-a-real-secret-0123456789"
    os.environ["ADMIN_PASSWORD"] = args.password
    os.environ["DATABASE"] = str(db_path)
    os.environ["UPLOAD_DIR"] = str(upload_dir)
    os.environ["APP_URL"] = f"http://127.0.0.1:{args.port}"
    os.environ["APP_ENV"] = "test"
    # Flask's ``app.run()`` calls ``flask.cli.load_dotenv()``, which would
    # re-read the repository ``.env`` and hand the test run the real SMTP and
    # Google credentials. Skip it so the run stays hermetic.
    os.environ["FLASK_SKIP_DOTENV"] = "1"
    # No mail, no Drive, no Photos: keep the run hermetic.
    for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ADMIN_EMAIL", "FROM_EMAIL",
                "GOOGLE_DRIVE_CREDENTIALS", "GOOGLE_PHOTOS_CREDENTIALS", "STRIPE_SECRET_KEY"):
        os.environ.pop(key, None)

    from app import app  # noqa: E402  (import after the env is set)

    app.config["TESTING"] = True
    print("=" * 72)
    print("TEST FIXTURE — this is a throwaway database with seeded content,")
    print("not the site's data. For the real copy, run: python run.py  (port 5000)")
    print("=" * 72)
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
