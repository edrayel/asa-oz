"""Development and test entrypoint.

The app runs in three environments, selected with ``APP_ENV``:

    dev   python run.py                  loads .env, debug on
    test  APP_ENV=test python run.py     loads .env, no debug
    prod  gunicorn --bind 0.0.0.0:8000  no .env, no debug, the real entrypoint

``APP_ENV`` defaults to ``dev``.

Why not ``FLASK_ENV``: Flask removed it in 3.0. ``APP_ENV`` is ours, and it
means what it says in every environment.

Why ``FLASK_SKIP_DOTENV``: Flask's ``app.run()`` calls
``flask.cli.load_dotenv()``, which reads the ``.env`` sitting next to the app
and hands a dev server the production SMTP and Google credentials. In dev we
load the file ourselves — real environment variables win — and everywhere
else Flask is told not to touch it.
"""
import os
import sys

from dotenv import load_dotenv

APP_ENV = (os.environ.get("APP_ENV") or "dev").strip().lower()
if APP_ENV not in ("dev", "test", "prod"):
    sys.exit("APP_ENV must be dev, test or prod (got %r)" % APP_ENV)

if APP_ENV == "dev":
    # A value already in the environment wins over the file, so a single
    # variable can be overridden for one run without editing .env.
    load_dotenv(override=False)
else:
    os.environ["FLASK_SKIP_DOTENV"] = "1"

os.environ.setdefault("APP_ENV", APP_ENV)

if APP_ENV == "prod":
    sys.exit(
        "APP_ENV=prod is served by gunicorn, not by app.run():\n"
        "  gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 120 app:app"
    )

from app import app  # noqa: E402  (the import has to follow the environment)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = APP_ENV == "dev" and os.environ.get("FLASK_DEBUG", "1") == "1"
    print("Asa-OZ: %s on http://%s:%s (debug=%s)" % (APP_ENV, host, port, debug))
    app.run(host=host, port=port, debug=debug, use_reloader=debug)
