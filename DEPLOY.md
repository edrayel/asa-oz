# Deploying Asa-OZ

Flask + SQLite + HTMX, deployed on Render. This document covers the full
production setup: env vars, secrets, the admin, the CMS, the SMTP provider
(Zoho Mail), Google Drive as an admin media library, Google AdSense, and
the commandcode Render MCP integration.

## 1. Required environment variables

The app refuses to start without these two. They are not defaulted to
placeholder strings — fail-fast is intentional so a misconfigured deploy is
loud, not silent.

| Var | Purpose | How to set |
|---|---|---|
| `SECRET_KEY` | Flask session signing key (≥ 48 random bytes) | `python -c 'import secrets; print(secrets.token_urlsafe(48))'` |
| `ADMIN_PASSWORD` | Initial admin password (≥ 12 chars). Used only on first boot to seed the admin row, then change it at `/admin/password`. | A long random string or a passphrase. |

`render.yaml` declares both as `sync: false` — set them in the Render
dashboard's **Environment** tab, not in the YAML.

## 2. Optional environment variables

All other vars are optional. If a var is missing, the corresponding
feature degrades gracefully (no email sent, no payment, no Drive, no ads).

### 2.1 Payments (Stripe)

| Var | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe API secret. If unset, checkout records orders as `enquiry` instead of opening a Stripe Checkout session. |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret. Reserved for future server-side fulfilment. |

### 2.2 Email (Zoho Mail)

If any of these are unset, every notification (booking / contact / feedback
/ waitlist / order) is silently skipped — the form still saves to the DB.

Asa-OZ uses **Zoho Mail** for transactional email. The settings below are
for a custom-domain account on `asa-oz.com` (use `smtp.zoho.com` for a
plain `zoho.com` personal account).

| Var | Value | Purpose |
|---|---|---|
| `SMTP_HOST` | `smtppro.zoho.com` | Zoho's outgoing server for custom-domain accounts. |
| `SMTP_PORT` | `587` | TLS (STARTTLS). Use `465` with `SMTP_USE_SSL=1` if you prefer implicit SSL. |
| `SMTP_USERNAME` | `notifications@asa-oz.com` (or whatever you create) | The full mailbox address. |
| `SMTP_PASSWORD` | The mailbox password, or an app password if 2FA is enabled on the Zoho account. | Generate an app password at <https://accounts.zoho.com> → Security → App Passwords. |
| `ADMIN_EMAIL` | `info@asa-oz.com` | Recipient for admin notifications. |
| `FROM_EMAIL` | Defaults to `SMTP_USERNAME`. | Override only if you want a different Reply-To or display name (set the display name in the Zoho account, not here). |

Notes specific to Zoho:
- If you enable 2FA on the Zoho account, **app passwords are required**.
  A regular login password will be rejected.
- The `From` address in outgoing mail must match the SMTP account (or one
  of its aliases) or Zoho will return `Relaying disallowed`.
- Render's outbound IPs are not on any RBL, so no special DNS work is
  needed. Add SPF / DKIM / DMARC records on `asa-oz.com` once you have a
  stable sending domain to improve deliverability.

### 2.3 Google Drive (admin media library)

| Var | Purpose |
|---|---|
| `GOOGLE_DRIVE_CREDENTIALS` | Service-account JSON, either a path to a file or the raw JSON string. `drive.readonly` scope only. |
| `GOOGLE_DRIVE_FOLDER_ID` | Drive folder to browse by default. Optional. |

### 2.4 App

| Var | Default | Purpose |
|---|---|---|
| `APP_URL` | `RENDER_EXTERNAL_URL` (set by Render) or `http://localhost:5000` | Canonical site URL. Set this only if you're behind a custom domain that Render doesn't know about. |
| `RENDER_EXTERNAL_URL` | — | Set automatically by Render. |
| `DATABASE` | `instance/asaoz.sqlite3` | SQLite file path. |
| `UPLOAD_DIR` | `instance/uploads/` | File-upload directory. |
| `MAX_UPLOAD_MB` | `20` | Max upload size in MB. Enforced at the Werkzeug level (413 on oversize). |
| `PYTHON_VERSION` | `3.12` | Set in `render.yaml`. |
| `FLASK_ENV` | `production` | Set in `render.yaml`. |

### 2.5 Google AdSense (only after AdSense approval)

| Var | Purpose |
|---|---|
| `ADSENSE_PUBLISHER_ID` | Your AdSense `ca-pub-XXXXXXXXXXXXXXXX` ID. If unset, the AdSense script does not load. |

### 2.6 Render MCP (commandcode)

This is for the commandcode AI agent, not the running app. See
[§ 7 Render MCP](#7-render-mcp-commandcode).

| Var | Purpose |
|---|---|
| `RENDER_ASAOZ_API_KEY` | Render API key with read access to your workspace. Read from the shell at agent startup. |

## 3. The admin / CMS

- Login at `/admin` with `username=admin` and the value of `ADMIN_PASSWORD`.
- **Change the password** at `/admin/password` on the first login.
- Products, files, feedback, waitlist, bookings, contacts, journey
  subscribers, orders, and dynamic pages all live under `/admin/*`.
- CMS-managed pages: home, about, faq, terms, privacy, contact, sitewide
  (footer copy), store, booking (modal labels).
- Drag-to-reorder sections per page; toggle each section's `active` flag
  to hide/show it.
- The **Brand** admin only manages `logo`, `logo_alt`, and `favicon`.
  Brand colours were removed because they didn't actually wire through to
  the CSS.
- All admin POSTs require a valid CSRF token (auto-injected by the
  `{{ csrf_input() }}` helper).
- Rich-text fields are sanitized server-side with `nh3` (tight allow-list
  of tags, `http(s)/mailto/tel` URL schemes only).

## 4. SEO and social

- `robots.txt` is served at the root, references `/sitemap.xml`.
- `sitemap.xml` is generated by Flask (static routes + every active
  dynamic page).
- `ads.txt` is served at the root with the IAB-required placement.
- Open Graph + Twitter Card meta is rendered on every page from
  per-page CMS content. The default `og:image` is
  `static/images/og-default.svg`.
- JSON-LD `Organization` schema is emitted on every page. To add per-page
  schemas (`FAQPage`, `Product`, etc.), override the `{% block jsonld %}`
  in the child template.

### 4.1 Open Graph image

The default is a 1200×630 branded SVG. If you want a raster:

1. Export the SVG to a 1200×630 PNG.
2. Save as `static/images/og-default.jpg`.
3. Update `_og_image_url` in `app.py` to point at the new path.

Per-page overrides: set the `image` field in any page's `hero` CMS
section.

### 4.2 Image optimization (one-time)

The marquee uses large WhatsApp JPEGs. To reduce payload, convert the
biggest ones to WebP. The marquee seeding code (`app.py:_wall_files`)
already accepts `.webp`, and `app.py` reads by relative path — no other
code change needed.

```python
import glob, os
from PIL import Image
for src in glob.glob("images/wall-of-memories/*") + glob.glob("images/founder/*"):
    if not src.lower().endswith((".jpg", ".jpeg")): continue
    if os.path.getsize(src) <= 200 * 1024: continue
    dst = os.path.splitext(src)[0] + ".webp"
    if os.path.exists(dst): continue
    Image.open(src).save(dst, "WEBP", quality=80, method=6)
```

The marquee is committed to the repo and only seeded on the very first
run; the WebP conversion takes effect on the next fresh-DB deploy, or
after the admin re-uploads the marquee image list via the CMS.

## 5. Google AdSense

The site is AdSense-ready out of the box. Ad slots do not render unless
both `ADSENSE_PUBLISHER_ID` is set **and** the `show_ads` setting is on
(it's on by default, toggle in `/admin/settings`).

1. Replace the `XXXXXXXXXXXXXXXX` placeholder in `static/ads.txt` with
   your real AdSense publisher ID.
2. Set the `ADSENSE_PUBLISHER_ID` env var to the same value.
3. After the first deploy with that env var, the AdSense script loads.
   The auto-ads feature injects units.
4. Replace the placeholder `data-ad-slot` values in
   `templates/partials/ads.html` with your real slot IDs once AdSense
   approves your account. (The placeholders are the ones currently in
   `templates/index.html`, `templates/store.html`, etc.)

The cookie banner fires `gtag('consent', 'update', …)` against Google's
Consent Mode v2 signals. The default signals (before the user clicks
anything) are `denied` for `ad_storage`, `ad_user_data`,
`ad_personalization`, and `analytics_storage`. A user "Accept all"
upgrades all four to `granted`. A user "Reject non-essential" keeps
them all at `denied`.

The privacy policy's CMS section 4a "Advertising (Google AdSense)" is
pre-filled with the AdSense disclosure language. Edit it from
`/admin/pages/privacy` if you need to tweak it.

## 6. Health check

`GET /health` returns a JSON status report. It exercises the SQLite
database and (if configured) Google Drive. Returns HTTP 200 with
`{"db": true, "status": "ok"}` when both subsystems respond, or HTTP 503
with `{"db": false, ...}` / `{"drive": false, ...}` if anything is
degraded. Use this URL as your Render healthcheck.

`GET /ping` is a cheap no-op alias — used by the keep-alive cron.

## 7. MCP servers (commandcode)

The repo's `.mcp.json` (project scope, committed) configures:

| Server | Why project-scoped |
|---|---|
| `github-edrayel` | Personal GitHub PAT — only this repo's sessions need it. |
| `render` | `RENDER_ASAOZ_API_KEY` reads from env; only this project uses Render for Asa-OZ. |
| `playwright` | Launches a real Chrome browser. Per-project because the spawned browser holds a singleton user-data-dir lock; if two opencode sessions on the same machine both enable it, the second one fails to start. |
| `chrome-devtools` | Same browser-process concern as playwright. |

The user-level `~/.commandcode/mcp.json` keeps cross-project MCPs
(`vps-manager`, `supermemory`, `paperplain`) but **not** the browser
MCPs — those live at the project scope so they don't collide between
different opencode instances on the same machine.

### Render API key

The env-var name is `RENDER_ASAOZ_API_KEY` (service-prefixed, so
multiple Render accounts cluster as `RENDER_*` when listed with
`env | grep ^RENDER_`).

In your shell, export it once per session:

```bash
export RENDER_ASAOZ_API_KEY="$(cat ~/.config/opencode/keys/render_asa-oz_api_key)"
```

Generate a new key at
<https://dashboard.render.com/u/settings?add-api-key> if you ever need
to rotate. After editing `.mcp.json`, restart the agent or run
`/mcp` inside an active session to pick up the new server. The first
time the agent invokes a Render tool, it will scope the connection to
a workspace.

## 8. First-time local setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

export SECRET_KEY=$(.venv/bin/python -c 'import secrets;print(secrets.token_urlsafe(48))')
export ADMIN_PASSWORD=$(.venv/bin/python -c 'import secrets;print(secrets.token_urlsafe(16))')

.venv/bin/python app.py    # dev server, http://localhost:5000
```

Log in at `/admin` with the value of `ADMIN_PASSWORD`.

## 9. Production checklist

- [ ] `SECRET_KEY` set to a random 48+ byte value
- [ ] `ADMIN_PASSWORD` set to a strong (≥ 12 char) initial value, then
      changed at `/admin/password`
- [ ] `APP_URL` set if using a custom domain
- [ ] `STRIPE_SECRET_KEY` set if you want to take real payments
      (otherwise the site runs in enquiry-only mode)
- [ ] `SMTP_*` set with Zoho Mail credentials (use an app password if 2FA
      is enabled on the Zoho account)
- [ ] `GOOGLE_DRIVE_CREDENTIALS` set if you want the admin Drive browser
- [ ] First boot logs `boot: drive configured=True` (or `False` if
      intentionally skipped)
- [ ] `GET /health` returns 200 with all subsystems `true`

## 10. Security model — quick reference

- **CSRF** on every POST endpoint (public forms, cart, admin). The
  `{{ csrf_input() }}` helper injects the token; `hmac.compare_digest`
  validates it.
- **Session cookies** are `Secure`, `HttpOnly`, `SameSite=Lax`.
- **Rich-text content** is sanitized server-side with `nh3` before
  being stored.
- **Navigation URLs** must be `/` or `http(s)/mailto` — anything else
  is rejected at save time.
- **Admin password** is hashed with `werkzeug.security` (pbkdf2:sha256).
- **`MAX_CONTENT_LENGTH`** rejects oversize uploads at the Werkzeug
  level (HTTP 413) before they reach the view code.
- **Google Drive credentials** never touch the database and are never
  logged. The Drive integration has read-only scope.
