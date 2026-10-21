# Asa-OZ — Agent Guide

Flask + SQLite + HTMX site and CMS. Production runs on the VPS (Docker Compose behind Traefik); `DEPLOY.md` is the full production runbook (§ 11 covers the VPS).

## Search Cheaply (read this first — token efficiency)

- Code is NOT in the semantic index (retired 2026-10-18: embedding the corpus cost hours of CPU to save cents of tokens). For code use `Grep`/`Glob`; for structure use `graphify`.
- `app.py` is one large module with no factory. Grep for the route or helper you need — do not read the file whole.
- Deployment, env vars, SMTP, Drive and AdSense are documented in `DEPLOY.md`. Read the relevant section before touching deploy config. The VPS runs the app as the `asaoz-web` Compose service; `/home/agent/asa-oz/app` is a git checkout of `master`, so a deploy is `git pull` + `docker compose build` + `docker compose up -d`.

## Quick Start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# .env is gitignored and required: SECRET_KEY and ADMIN_PASSWORD both fail-fast
python run.py            # PORT default 5000; FLASK_DEBUG=1 enables the reloader
```

`run.py` calls `load_dotenv(override=True)`, so `.env` wins over ambient vars locally.

Production entrypoint (from the `Dockerfile`):

```
gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --timeout 120 app:app
```

## Tech Stack

| Layer | Technology |
|---|---|
| Web | Flask 3.1, HTMX, server-rendered Jinja |
| Data | SQLite |
| Deploy | VPS (`Dockerfile`, `docker-compose.yml`, Traefik) |
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

- **`SECRET_KEY` and `ADMIN_PASSWORD` are required and deliberately fail-fast** — a misconfigured deploy must be loud, not silent. In production they live in `/home/agent/asa-oz/app/.env` (mode `600`); that file is never committed and never baked into the image.
- **`ADMIN_PASSWORD` only seeds the first boot.** Afterwards change it at `/admin/password`; editing the env var will not update an existing admin row.
- **Never inline a secret.** `.env` locally (gitignored) and `/home/agent/asa-oz/app/.env` on the VPS. `.dockerignore` keeps `.env` out of the image — never remove that line.
- **Style fingerprint.** `tests/e2e_styles.py` records the computed style of
  the shell, the typography and the page furniture on every page, and diffs two
  runs of it. Use it to prove a CSS change moved nothing:
  `.venv/bin/python tests/e2e_styles.py --base http://127.0.0.1:5055 --admin --out before.json`,
  make the change, run it again, then
  `.venv/bin/python tests/e2e_styles.py --diff before.json after.json`.
- **End-to-end audit harness.** `tests/e2e_server.py` runs the app against an isolated
  database (no mail, no Drive), `tests/e2e_seed.py` fills it with representative content,
  and `tests/e2e_audit.py` crawls every public and admin page at desktop, tablet and
  mobile, capturing JavaScript errors, failed requests, broken images, horizontal
  overflow and dead links. Run it before a release:
  `.venv/bin/python tests/e2e_server.py --port 5055 --fresh` then
  `.venv/bin/python tests/e2e_audit.py --base http://127.0.0.1:5055`.
- **Three environments, one switch.** `APP_ENV` is `dev` (default), `test` or
  `prod`; `run.py` loads `.env` only in dev and never with `override=True`, and
  sets `FLASK_SKIP_DOTENV=1` otherwise so Flask cannot pull the production
  credentials into a dev server. Production is gunicorn; `APP_ENV=prod python
  run.py` refuses to start and prints the command. `FLASK_ENV` is not used
  (Flask removed it in 3.0).
- **Member accounts.** A `member` is a public-site account: sign in at
  `/account`, share a story, add a testimonial, leave feedback, and see their
  own orders. Orders are matched by account id, and by email only once the
  address is confirmed, so nobody can claim another person's order by signing
  up with their address. The member area is in `templates/account/`, the
  permission matrix in `roles.py`, and the data in `db.py`.
- **Kilo is the agent runtime here; OpenCode is retired.** Project config is `kilo.json` (repo root) and `.kilo/`; MCP servers live in the user-level `~/.config/kilo/kilo.jsonc`. Anything committed must carry placeholders only — real credentials stay in `~/.config/opencode/keys/` (mode `600`), referenced as `"{file:~/.config/opencode/keys/<name>"}`.
- `app.py` is large — grep for the symbol rather than dumping it into context.
