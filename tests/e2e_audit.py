"""End-to-end audit of the Asa-OZ site and CMS.

Reproducible Playwright sweep over every public and admin page at three
viewports, plus interaction tests (menus, drawers, modals, accordions,
cart, forms, CRUD flows). Captures JavaScript errors, failed requests,
non-2xx responses, broken images, horizontal overflow and dead internal
links, and writes a JSON report.

Usage:

    .venv/bin/python tests/e2e_audit.py --base http://127.0.0.1:5055 \
        --out tests/.e2e/report.json

The server is expected to be running already (see ``tests/e2e_server.py``).
Exit code is 1 when the audit finds anything, so it can gate CI.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.parse

from playwright.sync_api import sync_playwright

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 834, "height": 1112},
    "mobile": {"width": 390, "height": 844},
}

# Third-party hosts the page is allowed to fail against (the test box has
# no business failing the build because unpkg is slow).
EXTERNAL_HOSTS = {
    "unpkg.com", "fonts.googleapis.com", "fonts.gstatic.com", "pagead2.googlesyndication.com",
    "www.googletagmanager.com", "googleads.g.doubleclick.net", "api.githubcopilot.com",
    "mcp.cloudflare.com", "www.google-analytics.com", "cdn.jsdelivr.net",
}

PUBLIC_PAGES = [
    "/", "/about", "/faq", "/blog", "/blog/submit", "/store", "/terms", "/privacy",
    "/policies", "/contact", "/sitemap.xml", "/robots.txt", "/ads.txt", "/api/wall",
    "/health", "/ping", "/nonexistent-page-404",
    "/account/login", "/account/signup",
]

ADMIN_PAGES = [
    "/admin", "/admin/products", "/admin/files", "/admin/blog", "/admin/blog/new",
    "/admin/drive", "/admin/photos", "/admin/feedback", "/admin/import", "/admin/waitlist",
    "/admin/emails", "/admin/bookings", "/admin/contacts", "/admin/journey", "/admin/orders",
    "/admin/pages", "/admin/pages/home", "/admin/settings", "/admin/password", "/admin/export",
    "/admin/dynamic-pages", "/admin/dynamic-pages/new", "/admin/navigation", "/admin/brand",
    "/admin/users", "/admin/testimonials",
]

EXPECTED_404 = {"/nonexistent-page-404"}


class Audit:
    def __init__(self, base: str, out: pathlib.Path, shots: pathlib.Path | None) -> None:
        self.base = base.rstrip("/")
        self.out = out
        self.shots = shots
        self.findings: list[dict] = []
        self.pages: list[dict] = []
        self.links: dict[str, str] = {}

    # ---------- finding helpers ----------
    def add(self, kind: str, url: str, viewport: str, detail: str, severity: str = "error") -> None:
        self.findings.append({
            "kind": kind, "url": url, "viewport": viewport, "detail": detail, "severity": severity,
        })

    # ---------- page harness ----------
    def watch(self, page, url: str, viewport: str) -> list[dict]:
        """Attach listeners; return the list they append to."""
        events: list[dict] = []
        page.on("console", lambda m: events.append({"kind": "console", "level": m.type, "text": m.text})
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: events.append({"kind": "pageerror", "text": str(e)}))
        page.on("requestfailed", lambda r: events.append(
            {"kind": "requestfailed", "text": f"{r.url} :: {r.failure}" if r.failure else r.url}))
        page.on("response", lambda r: events.append(
            {"kind": "http", "text": f"{r.status} {r.url}"}) if r.status >= 400 else None)
        return events

    def absorb(self, events: list[dict], url: str, viewport: str) -> None:
        for ev in events:
            if ev["kind"] == "console":
                if "404" in ev["text"] and any(e in url for e in EXPECTED_404):
                    continue
                if ev["level"] == "error":
                    self.add("console-error", url, viewport, ev["text"][:400])
                else:
                    self.add("console-warning", url, viewport, ev["text"][:300], severity="warning")
            elif ev["kind"] == "pageerror":
                self.add("js-exception", url, viewport, ev["text"][:400])
            elif ev["kind"] == "requestfailed":
                text = ev["text"]
                if any(h in text for h in EXTERNAL_HOSTS):
                    continue
                if "ERR_ABORTED" in text and any(text.split(" ")[0].endswith(ext) for ext in (".mp4", ".webm", ".m4v")):
                    # The browser cancels a media preload when the page moves on.
                    self.add("media-aborted", url, viewport, text[:300], severity="warning")
                    continue
                self.add("request-failed", url, viewport, text[:300])
            elif ev["kind"] == "http":
                text = ev["text"]
                if any(h in text for h in EXTERNAL_HOSTS):
                    continue
                status = int(text.split(" ", 1)[0])
                path = urllib.parse.urlparse(text.split(" ", 1)[1]).path
                if status >= 500:
                    self.add("server-error", url, viewport, text[:300])
                elif status >= 400 and path not in EXPECTED_404:
                    self.add("client-error", url, viewport, text[:300])

    def scroll_through(self, page) -> None:
        """Scroll to the bottom in steps so lazy/reveal work actually runs."""
        height = page.evaluate("document.body.scrollHeight")
        step = max(400, height // 12)
        pos = 0
        while pos < height:
            pos += step
            page.evaluate(f"window.scrollTo(0, {pos})")
            page.wait_for_timeout(120)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(350)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(150)

    def audit_page(self, page, path: str, viewport: str, events: list[dict]) -> dict:
        url = self.base + path
        events.clear()
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else 0
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(250)
        self.scroll_through(page)

        title = page.title()
        overflow = page.evaluate(
            "() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth})")
        if not path.endswith(".xml") and overflow["sw"] > overflow["iw"] + 2:
            self.add("horizontal-overflow", url, viewport,
                     f"scrollWidth={overflow['sw']} innerWidth={overflow['iw']}")
        broken = page.evaluate("""() => Array.from(document.images)
            .filter(i => i.complete && i.naturalWidth === 0 && i.currentSrc)
            .map(i => i.currentSrc)""")
        for src in broken[:10]:
            self.add("broken-image", url, viewport, src[:200])
        empty_forms = page.evaluate("""() => Array.from(document.querySelectorAll('form'))
            .filter(f => !f.querySelector('input,textarea,select,button'))
            .length""")
        if empty_forms:
            self.add("empty-form", url, viewport, f"{empty_forms} form(s) with no fields")
        for href in page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
            if href and href.startswith("/") and not href.startswith("//"):
                self.links[href.split("#")[0]] = path
        self.absorb(events, url, viewport)
        record = {"url": url, "viewport": viewport, "status": status, "title": title}
        self.pages.append(record)
        return record

    # ---------- phases ----------
    def run_public(self, browser) -> None:
        for name, size in VIEWPORTS.items():
            ctx = browser.new_context(viewport=size, ignore_https_errors=True)
            page = ctx.new_page()
            events = self.watch(page, "", name)
            for path in PUBLIC_PAGES:
                try:
                    self.audit_page(page, path, name, events)
                except Exception as exc:  # noqa: BLE001
                    self.add("navigation-error", self.base + path, name, str(exc)[:200])
            ctx.close()

    def run_admin(self, browser) -> None:
        for name, size in VIEWPORTS.items():
            ctx = browser.new_context(viewport=size, ignore_https_errors=True)
            page = ctx.new_page()
            events = self.watch(page, "", name)
            self.login(page, name, events)
            for path in ADMIN_PAGES:
                try:
                    self.audit_page(page, path, name, events)
                except Exception as exc:  # noqa: BLE001
                    self.add("navigation-error", self.base + path, name, str(exc)[:200])
            ctx.close()

    def submit(self, page, selector, timeout=20000) -> bool:
        """Click something and wait for the page it leads to.

        The captcha widget solves its proof of work when the form is sent and
        then submits it, so the navigation lands a moment after the click.
        """
        try:
            with page.expect_navigation(timeout=timeout):
                page.click(selector)
            return True
        except Exception:
            page.wait_for_load_state("domcontentloaded")
            return False

    def login(self, page, viewport: str, events: list[dict]) -> None:
        events.clear()
        page.goto(self.base + "/admin/login", wait_until="domcontentloaded")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "e2e-admin-password")
        self.submit(page, 'form button[type="submit"], form input[type="submit"]')
        if "/admin/login" in page.url:
            self.add("login-failed", self.base + "/admin/login", viewport, "still on the login page")
        self.absorb(events, self.base + "/admin/login", viewport)

    def run_interactions(self, browser) -> None:
        size = VIEWPORTS["desktop"]
        ctx = browser.new_context(viewport=size)
        page = ctx.new_page()
        events = self.watch(page, "", "interact")
        self.interact_public(page, events)
        ctx.close()

        msize = VIEWPORTS["mobile"]
        mctx = browser.new_context(viewport=msize)
        mpage = mctx.new_page()
        mevents = self.watch(mpage, "", "interact")
        self.step("mobile-menu", self.interact_mobile, mpage, mevents)
        mctx.close()

        ctx = browser.new_context(viewport=size)
        page = ctx.new_page()
        events = self.watch(page, "", "interact")
        self.login(page, "interact", events)
        self.interact_admin(page, events)
        ctx.close()

        # the member journey runs in its own context: it signs in as a member
        mctx2 = browser.new_context(viewport=size)
        mpage2 = mctx2.new_page()
        self.watch(mpage2, "", "interact")
        self.step("member-journey", self._member_journey, mpage2)
        mctx2.close()

    def dismiss_cookie_bar(self, page) -> None:
        """The consent bar is fixed to the bottom of the window and covers
        whatever sits behind it, so accept it before clicking anything low
        on a page."""
        bar = page.locator("#cookieBar")
        if bar.count() and bar.is_visible():
            accept = page.locator("#ckAccept")
            if accept.count():
                accept.click()
                page.wait_for_timeout(400)

    def step(self, label: str, fn, *args, **kwargs) -> None:
        """Run one interaction step; a failure is a finding, not a crash."""
        try:
            fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self.add("interaction-error", self.base, "interact", f"{label}: {str(exc)[:200]}")

    def interact_public(self, page, events: list[dict]) -> None:
        base = self.base
        # 1. Cookie consent bar
        self.step("consent-bar", self._consent, page, base)
        # 2. FAQ accordion
        self.step("faq-accordion", self._accordion, page, base)
        # 3. Back to top
        self.step("back-to-top", self._back_to_top, page, base)
        # 4. Contact form validation (empty submit must not 500)
        self.step("contact-form", self._contact_form, page, events, base)
        # 5. Store filter buttons (HTMX)
        self.step("store-filters", self._store_filters, page, events, base)
        # 6. Cart: add -> drawer -> remove
        self.step("cart", self._cart, page, events, base)
        # 7. Booking modal
        self.step("booking-modal", self._booking, page, events, base)
        # 8. Blog submission (public form)
        self.step("blog-submit", self._blog_submit, page, events, base)
        # 9. The waitlist band
        self.step("waitlist", self._waitlist, page, events, base)


    # ---- individual interaction steps ----
    def _consent(self, page, base) -> None:
        page.goto(base + "/", wait_until="domcontentloaded")
        if page.locator("#cookieBar").is_visible():
            page.click("#ckAccept")
            page.wait_for_timeout(300)
            if page.locator("#cookieBar").is_visible():
                self.add("ui", base + "/", "interact", "consent bar did not hide after Accept")

    def _accordion(self, page, base) -> None:
        page.goto(base + "/faq", wait_until="domcontentloaded")
        details = page.locator("details")
        if details.count():
            details.first.locator("summary").click()
            page.wait_for_timeout(200)
            if not details.first.evaluate("d => d.open"):
                self.add("ui", base + "/faq", "interact", "FAQ <details> did not open on click")

    def _back_to_top(self, page, base) -> None:
        page.goto(base + "/about", wait_until="domcontentloaded")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(300)
        if page.locator("#backToTop").is_visible():
            page.click("#backToTop")
            # The scroll is smooth: wait for it to settle rather than guessing.
            for _ in range(40):
                page.wait_for_timeout(150)
                y = page.evaluate("window.scrollY")
                if y <= 5:
                    break
            if y > 40:
                self.add("ui", base + "/about", "interact", f"back-to-top left scrollY={y}")

    def _contact_form(self, page, events, base) -> None:
        page.goto(base + "/contact", wait_until="domcontentloaded")
        events.clear()
        page.click('#contactForm button[type="submit"], #contactForm input[type="submit"]')
        page.wait_for_timeout(900)
        self.absorb(events, base + "/contact", "interact")

    def _store_filters(self, page, events, base) -> None:
        page.goto(base + "/store", wait_until="domcontentloaded")
        filters = page.locator(".filter-btn")
        for i in range(filters.count()):
            events.clear()
            filters.nth(i).click()
            page.wait_for_timeout(900)
            self.absorb(events, base + "/store", "interact")

    def _cart(self, page, events, base) -> None:
        page.goto(base + "/store", wait_until="domcontentloaded")
        add = page.locator("form[hx-post*='cart/add'] button, form[action*='cart/add'] button")
        if not add.count():
            self.add("ui", base + "/store", "interact", "no add-to-cart control found")
            return
        events.clear()
        add.first.click()
        page.wait_for_timeout(1500)
        self.absorb(events, base + "/store", "interact")
        if not page.locator("#cartDrawer").is_visible():
            self.add("ui", base + "/store", "interact", "cart drawer did not open after add")
            return
        qty = page.locator("form[hx-post*='cart/qty'] button, form[action*='cart/qty'] button")
        if qty.count():
            qty.first.click()
            page.wait_for_timeout(900)
        remove = page.locator("form[hx-post*='cart/remove'] button, form[action*='cart/remove'] button")
        if remove.count():
            remove.first.click()
            page.wait_for_timeout(900)

    def _waitlist(self, page, events, base) -> None:
        """The waitlist band: the form must be there and it must save."""
        page.goto(base + "/", wait_until="domcontentloaded")
        self.dismiss_cookie_bar(page)
        form = page.locator("#waitform")
        if not form.count():
            self.add("ui", base + "/", "interact", "the waitlist form is not on the home page")
            return
        events.clear()
        form.locator("input[name='email']").fill("audit-waitlist@example.com")
        form.locator("button[type=submit]").first.click()
        page.wait_for_timeout(1200)
        self.absorb(events, base + "/", "interact")
        msg = page.locator("#waitlistMsg")
        text = (msg.inner_text() if msg.count() else "").strip().lower()
        if "thank" not in text and "already" not in text:
            self.add("ui", base + "/", "interact", f"the waitlist form gave no confirmation ({text[:60]!r})")

    def _booking(self, page, events, base) -> None:
        page.goto(base + "/", wait_until="domcontentloaded")
        trigger = page.locator("#headerBookingTrigger, .pricing-btn")
        if not trigger.count():
            self.add("ui", base + "/", "interact", "no booking trigger found")
            return
        events.clear()
        trigger.first.click()
        page.wait_for_timeout(700)
        self.absorb(events, base + "/", "interact")
        if not page.locator("#bookingOverlay").is_visible():
            self.add("ui", base + "/", "interact", "booking overlay did not open")
            return
        close = page.locator("#bookingClose")
        if close.count():
            close.click()
            page.wait_for_timeout(500)

    def _blog_submit(self, page, events, base) -> None:
        page.goto(base + "/blog/submit", wait_until="domcontentloaded")
        events.clear()
        page.fill('input[name="title"]', "E2E audit story")
        page.fill('textarea[name="body"]', "Submitted by the automated audit.")
        page.click('form button[type="submit"], form input[type="submit"]')
        page.wait_for_timeout(1200)
        self.absorb(events, base + "/blog/submit", "interact")
        body = page.content().lower()
        if "thank" not in body and "received" not in body and "story" not in body:
            self.add("ui", base + "/blog/submit", "interact",
                     f"no confirmation on the response page ({page.url})")

    def _member_journey(self, page) -> None:
        """Sign up as a member, use the account area, sign out."""
        base = self.base
        page.goto(base + "/account/signup", wait_until="domcontentloaded")
        self.dismiss_cookie_bar(page)
        page.locator("form:has(input[name='email']) input[name='full_name']").fill("Audit Member")
        # a fresh address every run: the account survives between runs
        page.fill("input[name='email']", "audit-member-%d@example.com" % int(time.time()))
        page.fill("input[name='password']", "audit-member-password-123")
        page.fill("input[name='confirm']", "audit-member-password-123")
        self.submit(page, "form:has(input[name='email']) button[type=submit]")
        if "/account" not in page.url:
            self.add("ui", base + "/account/signup", "interact", f"the sign-up did not land on the account ({page.url})")
            return
        # the account page shows the sections
        for path in ("/account", "/account/orders", "/account/testimonial", "/account/feedback",
                     "/account/profile"):
            resp = page.goto(base + path, wait_until="domcontentloaded")
            if resp and resp.status != 200:
                self.add("ui", base + path, "interact", f"the account page returned {resp.status}")
        # a testimonial
        page.goto(base + "/account/testimonial", wait_until="domcontentloaded")
        self.dismiss_cookie_bar(page)
        page.fill("textarea[name='quote']", "The audit wrote this testimonial.")
        self.submit(page, "form:has(textarea[name='quote']) button[type=submit]")
        if "The audit wrote this testimonial." not in page.content():
            self.add("ui", base + "/account/testimonial", "interact", "the testimonial was not saved")
        # feedback
        page.goto(base + "/account/feedback", wait_until="domcontentloaded")
        self.dismiss_cookie_bar(page)
        page.fill("textarea[name='text']", "The audit wrote this feedback.")
        self.submit(page, "form:has(textarea[name='text']) button[type=submit]")
        if "The audit wrote this feedback." not in page.content():
            self.add("ui", base + "/account/feedback", "interact", "the feedback was not saved")
        # sign out
        page.goto(base + "/account", wait_until="domcontentloaded")
        signout = page.locator("form[action*='/account/logout'] button")
        if signout.count():
            signout.first.click()
            page.wait_for_load_state("domcontentloaded")
            page.goto(base + "/account", wait_until="domcontentloaded")
            if "/account/login" not in page.url:
                self.add("security", base + "/account", "interact", "the account is still reachable after signing out")
        else:
            self.add("ui", base + "/account", "interact", "no sign-out control found")

    def interact_mobile(self, page, events: list[dict]) -> None:
        base = self.base
        page.goto(base + "/", wait_until="domcontentloaded")
        # The consent bar sits over the header on a small screen, so it has to
        # go before the menu button can be reached.
        self.dismiss_cookie_bar(page)
        if page.locator("#menuToggle").is_visible():
            page.click("#menuToggle")
            page.wait_for_timeout(600)
            if not page.locator("#mobileMenu").is_visible():
                self.add("ui", base + "/", "interact", "mobile menu did not open")
            else:
                page.click("#menuClose")
                page.wait_for_timeout(400)

    def interact_admin(self, page, events: list[dict]) -> None:
        base = self.base
        for label, fn in (
            ("admin-product-create", self._admin_product),
            ("admin-blog-create", self._admin_blog),
            ("admin-dynamic-page", self._admin_dynamic_page),
            ("admin-settings", self._admin_settings),
            ("admin-navigation", self._admin_navigation),
            ("admin-brand", self._admin_brand),
            ("admin-exports", self._admin_exports),
            ("admin-logout", self._admin_logout),
        ):
            self.step(label, fn, page, events, base)

    def _admin_product(self, page, events, base) -> None:
        page.goto(base + "/admin/products", wait_until="domcontentloaded")
        events.clear()
        form = page.locator("form[action*='products/new']")
        if form.count():
            form.locator("input[name='name']").fill("E2E Audit Product")
            form.locator("textarea[name='desc'], input[name='desc']").fill("Created by the audit script")
            form.locator("input[name='price']").fill("1500")
            form.locator("button[type=submit], input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
            if "E2E Audit Product" not in page.content():
                self.add("ui", base + "/admin/products", "interact", "new product did not appear in the list")
        self.absorb(events, base + "/admin/products", "interact")

    def _admin_blog(self, page, events, base) -> None:
        page.goto(base + "/admin/blog/new", wait_until="domcontentloaded")
        events.clear()
        page.fill("input[name='title']", "E2E Audit Post")
        page.fill("textarea[name='body']", "Body of the audit post.")
        page.locator("form:has(textarea[name='body']) button[type=submit]").first.click()
        page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/blog/new", "interact")

    def _admin_dynamic_page(self, page, events, base) -> None:
        page.goto(base + "/admin/dynamic-pages/new", wait_until="domcontentloaded")
        events.clear()
        slug = page.locator("input[name='slug']")
        if slug.count():
            slug.fill("e2e-audit-page-2")
            page.locator("form:has(input[name='slug']) button[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/dynamic-pages/new", "interact")

    def _admin_settings(self, page, events, base) -> None:
        page.goto(base + "/admin/settings", wait_until="domcontentloaded")
        events.clear()
        toggles = page.locator("form[action*='settings'] input[type=checkbox]")
        if toggles.count():
            before = toggles.first.is_checked()
            toggles.first.click()
            page.locator("form[action*='settings'] button[type=submit], form[action*='settings'] input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
            after = page.locator("form[action*='settings'] input[type=checkbox]").first.is_checked()
            if before == after:
                self.add("ui", base + "/admin/settings", "interact", "settings toggle did not persist")
        self.absorb(events, base + "/admin/settings", "interact")

    def _admin_navigation(self, page, events, base) -> None:
        page.goto(base + "/admin/navigation", wait_until="domcontentloaded")
        events.clear()
        nav = page.locator("form[action*='navigation']").first
        if nav.count():
            nav.locator("input[name='label']").first.fill("E2E nav item")
            nav.locator("input[name='url']").first.fill("/about")
            nav.locator("button[type=submit], input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
            # remove it again: a test link in the navigation reads like a
            # mistake, and the next run would add another one
            page.goto(base + "/admin/navigation", wait_until="domcontentloaded")
            row = page.locator("li.nav-item", has_text="E2E nav item")
            if row.count():
                remove = row.first.locator("form[action*='navigation'] button.btn-danger")
                if remove.count():
                    # the row's delete button asks for confirmation
                    page.once("dialog", lambda dialog: dialog.accept())
                    remove.click()
                    page.wait_for_load_state("domcontentloaded")
                    if "E2E nav item" in page.content():
                        self.add("ui", base + "/admin/navigation", "interact",
                                 "the navigation item the audit added was not removed")
        self.absorb(events, base + "/admin/navigation", "interact")

    def _admin_brand(self, page, events, base) -> None:
        page.goto(base + "/admin/brand", wait_until="domcontentloaded")
        events.clear()
        brand = page.locator("form[action*='brand']")
        if brand.count():
            brand.locator("input[name='logo_alt']").fill("Asa-OZ")
            brand.locator("button[type=submit], input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/brand", "interact")

    def _admin_exports(self, page, events, base) -> None:
        # The CSV endpoints are downloads, so they are fetched through the
        # request context instead of being navigated to.
        for path in ("/admin/export", "/admin/export/waitlist.csv", "/admin/export/orders.csv",
                     "/admin/export/contacts.csv", "/admin/export/bookings.csv", "/admin/export/feedback.csv"):
            # Fetched from inside the page: an out-of-band request would share
            # the cookie jar and replace the signed-in session cookie with the
            # one the login redirect sets.
            status = page.evaluate(
                """async (url) => {
                    const r = await fetch(url, {credentials: 'same-origin'});
                    return r.status;
                }""", base + path)
            if status >= 400:
                self.add("ui", base + path, "interact", f"export returned {status}")

    def _admin_logout(self, page, events, base) -> None:
        events.clear()
        page.goto(base + "/admin", wait_until="domcontentloaded")
        toggle = page.locator("#adminProfileToggle")
        if toggle.count():
            toggle.click()
            page.wait_for_timeout(300)
        logout = page.locator("form[action*='logout'] button")
        if not logout.count():
            self.add("ui", base + "/admin", "interact",
                     f"no logout control found (url={page.url}, title={page.title()[:60]!r})")
            return
        logout.first.click()
        page.wait_for_load_state("domcontentloaded")
        page.goto(base + "/admin", wait_until="domcontentloaded")
        if "/admin/login" not in page.url:
            self.add("security", base + "/admin", "interact", "admin still reachable after logout")
        self.absorb(events, base + "/admin", "interact")

    def _unused_interact_admin(self, page, events: list[dict]) -> None:
        base = self.base
        # 1. Create a product
        page.goto(base + "/admin/products", wait_until="domcontentloaded")
        events.clear()
        form = page.locator("form[action*='products/new']")
        if form.count():
            form.locator("input[name='name']").fill("E2E Audit Product")
            form.locator("textarea[name='desc'], input[name='desc']").fill("Created by the audit script")
            form.locator("input[name='price']").fill("1500")
            form.locator("button[type=submit], input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
            if "E2E Audit Product" not in page.content():
                self.add("ui", base + "/admin/products", "interact", "new product did not appear in the list")
        self.absorb(events, base + "/admin/products", "interact")
        # 2. Create a blog post
        page.goto(base + "/admin/blog/new", wait_until="domcontentloaded")
        events.clear()
        page.fill("input[name='title']", "E2E Audit Post")
        page.fill("textarea[name='body']", "Body of the audit post.")
        page.locator("form:has(textarea[name='body']) button[type=submit]").first.click()
        page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/blog/new", "interact")
        # 3. Dynamic page
        page.goto(base + "/admin/dynamic-pages/new", wait_until="domcontentloaded")
        events.clear()
        slug = page.locator("input[name='slug']")
        if slug.count():
            slug.fill("e2e-audit-page")
            page.click("form button[type=submit], form input[type=submit]")
            page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/dynamic-pages/new", "interact")
        # 4. Settings toggle
        page.goto(base + "/admin/settings", wait_until="domcontentloaded")
        events.clear()
        toggles = page.locator("form[action*='settings'] input[type=checkbox]")
        if toggles.count():
            before = toggles.first.is_checked()
            toggles.first.click()
            page.click("form[action*='settings'] button[type=submit], form[action*='settings'] input[type=submit]")
            page.wait_for_load_state("domcontentloaded")
            after = page.locator("form[action*='settings'] input[type=checkbox]").first.is_checked()
            if before == after:
                self.add("ui", base + "/admin/settings", "interact", "settings toggle did not persist")
        self.absorb(events, base + "/admin/settings", "interact")
        # 5. Navigation add
        page.goto(base + "/admin/navigation", wait_until="domcontentloaded")
        events.clear()
        nav = page.locator("form[action*='navigation']").first
        if nav.count():
            nav.locator("input[name='label']").first.fill("E2E Audit Link")
            nav.locator("input[name='url']").first.fill("/e2e-audit")
            nav.locator("button[type=submit], input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/navigation", "interact")
        # 6. Brand save
        page.goto(base + "/admin/brand", wait_until="domcontentloaded")
        events.clear()
        brand = page.locator("form[action*='brand']")
        if brand.count():
            brand.locator("input[name='logo_alt']").fill("Asa-OZ")
            brand.locator("button[type=submit], input[type=submit]").first.click()
            page.wait_for_load_state("domcontentloaded")
        self.absorb(events, base + "/admin/brand", "interact")
        # 7. Export endpoints
        for path in ("/admin/export", "/admin/export/waitlist.csv", "/admin/export/orders.csv"):
            events.clear()
            resp = page.goto(base + path, wait_until="domcontentloaded")
            if resp and resp.status >= 400:
                self.add("ui", base + path, "interact", f"export returned {resp.status}")
            self.absorb(events, base + path, "interact")
        # 8. Logout
        events.clear()
        page.goto(base + "/admin", wait_until="domcontentloaded")
        logout = page.locator("form[action*='logout'] button, form[action*='logout'] input[type=submit]")
        if logout.count():
            logout.first.click()
            page.wait_for_load_state("domcontentloaded")
            page.goto(base + "/admin", wait_until="domcontentloaded")
            if "/admin/login" not in page.url:
                self.add("security", base + "/admin", "interact", "admin still reachable after logout")
        self.absorb(events, base + "/admin", "interact")


    def run_roles(self, browser) -> None:
        """Create a limited account through the UI and check what it can reach."""
        ctx = browser.new_context(viewport=VIEWPORTS["desktop"])
        page = ctx.new_page()
        events = self.watch(page, "", "roles")
        self.login(page, "roles", events)
        base = self.base

        for username, role, allowed, forbidden in (
            ("audit-marketing", "digital marketing manager", ["/admin/pages", "/admin/blog"], ["/admin/products", "/admin/users", "/admin/settings"]),
            ("audit-ecommerce", "ecommerce manager", ["/admin/products", "/admin/orders"], ["/admin/blog", "/admin/users", "/admin/settings"]),
        ):
            self.step(f"signin-super-{username}", self._sign_in_super, page)
            self.step(f"create-{username}", self._create_user, page, username, role)
            self.step(f"access-{username}", self._check_role, page, username, allowed, forbidden)
        ctx.close()

    def _sign_in_super(self, page) -> None:
        """Sign back in as the superadmin, whatever the session currently holds."""
        page.goto(self.base + "/admin", wait_until="domcontentloaded")
        if "/admin/login" not in page.url:
            toggle = page.locator("#adminProfileToggle")
            if toggle.count():
                toggle.click()
                page.wait_for_timeout(250)
            form = page.locator("form[action*='logout'] button")
            if form.count():
                form.first.click()
                page.wait_for_load_state("domcontentloaded")
        page.goto(self.base + "/admin/login", wait_until="domcontentloaded")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "e2e-admin-password")
        self.submit(page, 'form button[type="submit"]')
        if "/admin/login" in page.url:
            self.add("ui", self.base + "/admin/login", "roles", "the superadmin could not sign back in")

    def _create_user(self, page, username, role) -> None:
        page.goto(self.base + "/admin/users", wait_until="domcontentloaded")
        form = page.locator("form[action*='/admin/users/new']")
        if not form.count():
            self.add("ui", self.base + "/admin/users", "roles", "no create-user form")
            return
        form.locator("input[name='username']").fill(username)
        form.locator("input[name='email']").fill(f"{username}@example.com")
        form.locator("select[name='role']").select_option(label=None, value=role)
        form.locator("input[name='password']").fill("audit-password-12345")
        form.locator("button[type=submit]").first.click()
        page.wait_for_load_state("domcontentloaded")
        if username not in page.content():
            self.add("ui", self.base + "/admin/users", "roles", f"{username} was not created")

    def _check_role(self, page, username, allowed, forbidden) -> None:
        base = self.base
        # sign the limited account in
        page.goto(base + "/admin/login", wait_until="domcontentloaded")
        if "/admin/login" not in page.url:
            logout = page.locator("#adminProfileToggle")
            if logout.count():
                logout.click()
                page.wait_for_timeout(200)
            form = page.locator("form[action*='logout'] button")
            if form.count():
                form.first.click()
                page.wait_for_load_state("domcontentloaded")
        page.goto(base + "/admin/login", wait_until="domcontentloaded")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', "audit-password-12345")
        self.submit(page, 'form button[type="submit"]')
        if "/admin/login" in page.url:
            self.add("ui", base + "/admin/login", "roles", f"{username} could not sign in")
            return
        for path in allowed:
            resp = page.goto(base + path, wait_until="domcontentloaded")
            if resp and resp.status != 200:
                self.add("ui", base + path, "roles", f"{username} was refused a page it should have ({resp.status})")
        for path in forbidden:
            resp = page.goto(base + path, wait_until="domcontentloaded")
            if resp and resp.status != 403:
                self.add("security", base + path, "roles",
                         f"{username} reached a page it should not have ({resp.status})")
        # the sidebar must not offer what the role cannot use
        page.goto(base + "/admin", wait_until="domcontentloaded")
        html = page.content()
        for path in forbidden:
            if f'href="{path}"' in html:
                self.add("ui", base + "/admin", "roles", f"the sidebar still links {path} for {username}")

    # ---------- link check ----------
    def check_links(self, browser) -> None:
        ctx = browser.new_context()
        page = ctx.new_page()
        for target, source in sorted(self.links.items()):
            if target.startswith("/static") or target.startswith("/media") or target.startswith("/images"):
                continue
            try:
                resp = page.goto(self.base + target, wait_until="domcontentloaded", timeout=20000)
            except Exception as exc:  # noqa: BLE001
                self.add("dead-link", target, "link-check", f"{source} -> {exc}"[:200])
                continue
            status = resp.status if resp else 0
            if status >= 400 and target not in EXPECTED_404:
                self.add("dead-link", target, "link-check", f"linked from {source}, HTTP {status}")
        ctx.close()

    # ---------- report ----------
    def report(self) -> int:
        by_kind: dict[str, int] = {}
        for f in self.findings:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        payload = {
            "base": self.base,
            "pages_checked": len(self.pages),
            "links_checked": len(self.links),
            "counts": by_kind,
            "findings": self.findings,
            "pages": self.pages,
        }
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text(json.dumps(payload, indent=1))
        print(f"\npages checked : {len(self.pages)}")
        print(f"links checked : {len(self.links)}")
        print(f"findings      : {len(self.findings)}")
        for kind, count in sorted(by_kind.items(), key=lambda kv: -kv[1]):
            print(f"  {kind:22} {count}")
        for f in self.findings[:40]:
            print(f"  - [{f['severity']}] {f['kind']} {f['viewport']} {f['url']} :: {f['detail'][:160]}")
        if len(self.findings) > 40:
            print(f"  ... {len(self.findings) - 40} more in {self.out}")
        return 1 if any(f["severity"] == "error" for f in self.findings) else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5055")
    parser.add_argument("--out", default="tests/.e2e/report.json")
    parser.add_argument("--phase", default="all",
                        choices=["all", "public", "admin", "interact", "links", "roles"])
    args = parser.parse_args()

    audit = Audit(args.base, pathlib.Path(args.out), None)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        try:
            if args.phase in ("all", "public"):
                audit.run_public(browser)
            if args.phase in ("all", "admin"):
                audit.run_admin(browser)
            if args.phase in ("all", "interact"):
                audit.run_interactions(browser)
            if args.phase in ("all", "roles"):
                audit.run_roles(browser)
            if args.phase in ("all", "links"):
                audit.check_links(browser)
        finally:
            browser.close()
    return audit.report()


if __name__ == "__main__":
    sys.exit(main())
