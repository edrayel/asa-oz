"""Style fingerprint: proof that a CSS change did not move anything.

The page stylesheets are standalone sheets — each one carries the design
tokens, the reset and the body typography, and they are all near-copies of
each other. Centralising that base layer is a large diff with a small
chance of a visual regression, so it needs a check that does not rely on
eyeballs.

This tool visits every public page (and a few admin ones) and records the
computed style of a curated list of elements, then writes it to JSON. Run it
before a change and after it, and diff the two files: any difference is a
regression.

    .venv/bin/python tests/e2e_styles.py --base http://127.0.0.1:5055 --out before.json
    # ... the change ...
    .venv/bin/python tests/e2e_styles.py --base http://127.0.0.1:5055 --out after.json
    .venv/bin/python tests/e2e_styles.py --diff before.json after.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

PAGES = [
    "/", "/about", "/faq", "/blog", "/blog/submit", "/terms", "/privacy",
    "/policies", "/contact", "/store",
]

ADMIN_PAGES = ["/admin", "/admin/pages", "/admin/blog", "/admin/settings", "/admin/users"]

# The properties that decide how a page looks. Layout boxes are included
# because a missing reset rule shows up there first.
PROPERTIES = [
    "font-family", "font-size", "font-weight", "line-height", "letter-spacing",
    "color", "background-color", "background-image", "margin", "padding",
    "border", "border-radius", "box-shadow", "max-width", "display",
    "flex-direction", "gap", "text-align", "text-transform", "opacity",
    "position", "top", "left", "right", "bottom", "width", "height", "z-index",
]

# Selectors worth checking on every page: the shell, the typography and the
# page furniture that a base-layer change could disturb.
SELECTORS = [
    "body", ".site-header", ".site-header .header-inner", ".brand-link", ".main-nav",
    ".main-nav a", ".header-actions", ".header-booking", ".header-account",
    ".shell", "main", ".footer-grid", ".footer-brand", ".footer-proof h4",
    ".footer-legal", ".mobile-menu", ".cookie-bar", ".ambience", ".grain",
    "h1", "h2", "h3", "p", "a", "ul", "li", "blockquote", "button", "input",
    "select", "textarea", "table", "th", "td", "form",
]

# Page-specific furniture, checked only where it exists.
OPTIONAL = [
    ".hero", ".hero h1", ".hero .lede", ".signup form", ".signup input",
    ".stories-band", ".stories-grid", ".story-card", ".ethos", ".faq",
    ".faq details", ".faq summary", ".feedback-section", ".feedback-form",
    ".testimonial-ribbon", ".pricing-section", ".pricing-card", ".page-section",
    ".page-cta", ".page-btn", ".contact-form", ".contact-form input",
    ".blog-card", ".blog-grid", ".store-grid", ".store-card", ".waitlist-band",
    ".waitlist-form", ".waitlist-form input", ".waitlist-form button",
    ".member-testimonials", ".member-testimonial", ".account-hero", ".account-nav",
    ".account-content", ".account-btn", ".account-field input",
    ".admin-wrap", ".admin-sidebar", ".admin-nav a", ".admin-appbar", ".card",
    ".admin-table", ".stat", ".badge",
]


def snapshot(page) -> dict:
    return page.evaluate(
        """([selectors, optional, properties]) => {
            const out = {};
            const read = (el) => {
                const cs = getComputedStyle(el);
                const box = el.getBoundingClientRect();
                const values = {};
                for (const prop of properties) values[prop] = cs.getPropertyValue(prop);
                values['__box'] = [Math.round(box.width), Math.round(box.height)];
                return values;
            };
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) out[sel] = read(el);
            }
            for (const sel of optional) {
                const el = document.querySelector(sel);
                if (el) out[sel] = read(el);
            }
            out['__page'] = {
                scrollWidth: document.documentElement.scrollWidth,
                innerWidth: window.innerWidth,
                bodyFont: getComputedStyle(document.body).fontFamily,
                bodyBg: getComputedStyle(document.body).backgroundColor,
                rootVars: (() => {
                    const cs = getComputedStyle(document.documentElement);
                    const vars = {};
                    for (const name of ['--espresso','--tobacco','--cafe','--cafe-ink','--sand',
                                        '--cream','--paper','--sage','--sage-deep','--ink','--muted',
                                        '--serif','--sans','--ease']) {
                        vars[name] = cs.getPropertyValue(name).trim();
                    }
                    return vars;
                })(),
            };
            return out;
        }""",
        [SELECTORS, OPTIONAL, PROPERTIES],
    )


def collect(base: str, admin: bool, password: str) -> dict:
    pages = list(PAGES) + (list(ADMIN_PAGES) if admin else [])
    result = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        # Reduced motion switches the scroll-reveal animations off, so the
        # fingerprint is not comparing two frames of the same fade.
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  reduced_motion="reduce")
        page = ctx.new_page()
        if admin:
            page.goto(base + "/admin/login", wait_until="domcontentloaded")
            page.fill('input[name="username"]', "admin")
            page.fill('input[name="password"]', password)
            page.click('form button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")
        for path in pages:
            try:
                page.goto(base + path, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(300)
                result[path] = snapshot(page)
            except Exception as exc:  # noqa: BLE001
                result[path] = {"__error": str(exc)[:200]}
        browser.close()
    return result


def diff(before: dict, after: dict) -> int:
    changes = 0
    for path in sorted(set(before) | set(after)):
        b = before.get(path, {})
        a = after.get(path, {})
        for key in sorted(set(b) | set(a)):
            if b.get(key) != a.get(key):
                changes += 1
                print(f"CHANGED {path} :: {key}")
                bv = b.get(key)
                av = a.get(key)
                if isinstance(bv, dict) and isinstance(av, dict):
                    for prop in sorted(set(bv) | set(av)):
                        if bv.get(prop) != av.get(prop):
                            print(f"    {prop}: {bv.get(prop)!r} -> {av.get(prop)!r}")
                else:
                    print(f"    {bv!r} -> {av!r}")
    if not changes:
        print("no style differences")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5055")
    parser.add_argument("--out", default="tests/.e2e/styles.json")
    parser.add_argument("--admin", action="store_true", help="include the admin pages")
    parser.add_argument("--password", default="e2e-admin-password")
    parser.add_argument("--diff", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()

    if args.diff:
        before = json.loads(pathlib.Path(args.diff[0]).read_text())
        after = json.loads(pathlib.Path(args.diff[1]).read_text())
        return 1 if diff(before, after) else 0

    data = collect(args.base, args.admin, args.password)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, sort_keys=True))
    print(f"captured {len(data)} pages -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
