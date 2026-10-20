# Asa-OZ — Agent Guide

Flask + SQLite + HTMX site and CMS. Production runs on the VPS (Docker Compose behind Traefik); `DEPLOY.md` is the full production runbook (§ 11 covers the VPS).

## Search Cheaply (read this first — token efficiency)

- Code is NOT in the semantic index (retired 2026-10-18: embedding the corpus cost hours of CPU to save cents of tokens). For code use `Grep`/`Glob`; for structure use `graphify`.
- `app.py` is one large module with no factory. Grep for the route or helper you need — do not read the file whole.
- Deployment, env vars, SMTP, Drive, AdSense and the Render MCP integration are documented in `DEPLOY.md`. Read the relevant section before touching deploy config. The VPS runs the app as the `asaoz-web` Compose service; the code on the VPS is a copy, not a git checkout, so a deploy is `rsync` + `docker compose build` + `docker compose up -d`.

## Quick Start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# .env is gitignored and required: SECRET_KEY and ADMIN_PASSWORD both fail-fast
python run.py            # PORT default 5000; FLASK_DEBUG=1 enables the reloader
```

`run.py` calls `load_dotenv(override=True)`, so `.env` wins over ambient vars locally.

Production entrypoint (from `Procfile`):

```
gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app
```

## Tech Stack

| Layer | Technology |
|---|---|
| Web | Flask 3.1, HTMX, server-rendered Jinja |
| Data | SQLite |
| Deploy | VPS (`Dockerfile`, `docker-compose.yml`, Traefik); Render (`Procfile`, `render.yaml`) is a secondary target |
| Mail | Zoho Mail over SMTP |
| Media | Google Drive as the admin media library |
| Payments | Stripe |
| Sanitising | nh3 |

## Architecture

- `app.py` — the Flask app (`app = Flask(__name__)`, no factory), routes, cart helpers (`cart_contents`, `save_cart`, …), a static-asset versioning `_url_for` override, and `_current_cms()`.
- `db.py` — SQLite access plus `init_db()` which seeds the admin row.
- `cms.py` — CMS layer behind editable page content.
- `csrf.py` — CSRF protection.
- `photos.py`, `drive.py`, `google_creds.py`, `authorize_google.py` — Google Drive media pipeline.
- `mailer.py`, `notify.py` — outbound mail/notifications (`zoho_asa-oz_smtp_*` keys).
- `templates/` — Jinja (`base.html` is the shell; `admin/` holds CMS views). `static/` — css, js, images.

## Critical Rules

- **`SECRET_KEY` and `ADMIN_PASSWORD` are required and deliberately fail-fast** — a misconfigured deploy must be loud, not silent. Both are `sync: false` in `render.yaml`: set them in the Render dashboard's **Environment** tab, not in the YAML.
- **`ADMIN_PASSWORD` only seeds the first boot.** Afterwards change it at `/admin/password`; editing the env var will not update an existing admin row.
- **Never inline a secret.** `.env` locally (gitignored), Render env vars in production, and `/home/agent/asa-oz/app/.env` on the VPS. `.dockerignore` keeps `.env` out of the image — never remove that line.
- `app.py` is large — grep for the symbol rather than dumping it into context.
