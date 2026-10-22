# Captcha validation and UI placement plan

## Goal
Fix captcha validation freshness bug and improve widget UI placement across forms.

## Context
- Server: `captcha.py` (`verify`, `payload_is_fresh`, `check_request`)
- Client: `static/js/captcha.js` (widget discovery/placement)
- Templates: `templates/contact.html`, `templates/index.html`, `partials/waitlist_band.html`, `account/signup.html`, `blog_submit.html`, `admin/login.html`
- Helper: `app.py:captcha_field`, `captcha_script`

## Issues
1. `payload_is_fresh` always returns True (`"expires=" in raw or True`), so expired payloads pass freshness checks.
2. Widget is rendered as a sibling after the form; JS searches following siblings. In several templates the widget lands between form and unrelated content, causing awkward placement and fragile DOM coupling.

## Plan
1. Implement real expiry parsing in `payload_is_fresh`: decode payload, parse `expires`, compare to UTC now, return False on missing/invalid/expired.
2. Optionally have `verify` enforce freshness before `altcha.verify_solution_v1`.
3. Move widget rendering inside each form (before submit button) and update `captcha.js` to find widget within form (`form.querySelector('altcha-widget')`) rather than sibling search.
4. Update templates to place `{{ captcha_field() }}` inside the `<form>` just before submit button.
5. Adjust CSS `.captcha-widget` spacing accordingly.
6. Add/extend tests for expired payload rejection and widget placement (manual/audit).

## Validation
- Run `tests/test_captcha.py`.
- Run e2e audit for layout/JS errors.
