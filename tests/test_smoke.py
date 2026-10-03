"""Smoke tests for the admin surface.

These cover the failure modes that no other check in this project catches. There
is no test suite and no lint config, so the admin templates and the sidebar are
otherwise verified only by eye. Two classes of bug are guarded here:

  * Jinja silently discards a ``{% block %}`` that no ancestor defines, and
    silently ignores an ``{% extends %}`` naming a template that does not exist.
    The admin shell refactor rewrote 25 templates onto a new parent chain, so a
    mismatch would remove a sidebar or a page heading without any error.
  * ``url_for`` and the sidebar's endpoint tables reference Flask endpoint
    names as strings, which are only checked when that branch is rendered.

Run with:

    .venv/bin/python -m unittest discover -s tests -v

Environment is configured before ``app`` is imported, because db.init_db() runs
as a side effect of that import and would otherwise touch the real database.
"""

import os
import re
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="asaoz-smoke-")
os.environ["SECRET_KEY"] = "smoke-test-key-not-a-real-secret"
os.environ["ADMIN_PASSWORD"] = "smoke_test_password"
os.environ["DATABASE"] = os.path.join(_TMP, "smoke.sqlite3")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["APP_URL"] = "http://localhost:5000"

import app as application  # noqa: E402  (import must follow the env setup)

from jinja2 import nodes  # noqa: E402

flask_app = application.app
TEMPLATE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

# Endpoints reachable with no parameters, i.e. everything the sidebar links to.
NAV_ENDPOINTS = [
    "admin_dashboard", "admin_blog", "admin_pages", "admin_dynamic_pages",
    "admin_navigation", "admin_brand", "admin_files", "admin_drive",
    "admin_photos", "admin_products", "admin_orders", "admin_feedback",
    "admin_waitlist", "admin_journey", "admin_bookings", "admin_contacts",
    "admin_emails", "admin_import", "admin_settings", "admin_password",
]

URL_FOR_RE = re.compile(r"url_for\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")

# The complete block vocabulary of the admin shell (admin/base.html plus the
# blocks admin/app.html adds for its children). A template may override any of
# these; anything else is a typo or a leftover from before the refactor.
APP_BLOCKS = {
    "title", "styles", "head", "body",
    "page_title", "page_actions", "content",
}


def admin_templates():
    """Every template under templates/admin, as template names."""
    base = os.path.join(TEMPLATE_ROOT, "admin")
    out = []
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if name.endswith(".html"):
                full = os.path.join(dirpath, name)
                out.append(os.path.relpath(full, TEMPLATE_ROOT).replace(os.sep, "/"))
    return sorted(out)


class AdminPagesRender(unittest.TestCase):
    """Every sidebar page renders for a logged-in admin."""

    def setUp(self):
        flask_app.config["TESTING"] = True
        self.client = flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["admin"] = "admin"

    def test_every_nav_page_returns_200(self):
        for endpoint in NAV_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                rule = next(
                    r for r in flask_app.url_map.iter_rules()
                    if r.endpoint == endpoint and "GET" in r.methods
                )
                response = self.client.get(rule.rule)
                self.assertEqual(
                    response.status_code, 200,
                    "%s (%s) returned %s" % (endpoint, rule.rule, response.status_code),
                )

    def test_admin_redirects_when_logged_out(self):
        client = flask_app.test_client()
        for endpoint in NAV_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                rule = next(
                    r for r in flask_app.url_map.iter_rules()
                    if r.endpoint == endpoint and "GET" in r.methods
                )
                response = client.get(rule.rule)
                self.assertEqual(
                    response.status_code, 302,
                    "%s is reachable without auth" % endpoint,
                )


class PhotosTemplateContract(unittest.TestCase):
    """The picker states are only reachable with live Google credentials.

    ``/admin/photos`` renders its setup card when the integration is
    unconfigured, so the states that matter -- a live picker link, a populated
    pick list, an API error -- never appear in a plain page request. The real
    route is driven here with only the Google layer replaced, so the template
    stays pinned to the context ``admin_photos`` actually builds.
    """

    SESSION = {"mediaItemsSet": False, "pickerUri": "https://photos.example/p/abc",
               "pollingConfig": {"pollInterval": "4s"}}
    ITEMS = [{"id": "m1", "type": "PHOTO",
              "mediaFile": {"filename": "a.jpg", "mimeType": "image/jpeg",
                            "mediaFileMetadata": {"width": 800, "height": 600}}},
             {"id": "m2", "type": "PHOTO",
              "mediaFile": {"filename": "b.png", "mimeType": "image/png"}}]

    def _stub(self, configured=True, live=None, items=None, error=None):
        """Replace only the Photos network layer and render the real page.

        picker_url and poll_hint are left alone: both are pure functions, so the
        real ones prove the autoclose suffix and the 4s pollingConfig parse.
        """
        photos = application.photos
        originals = {name: getattr(photos, name) for name in
                     ("is_configured", "get_session", "all_media_items")}
        photos.is_configured = lambda: configured

        def fake_get_session(_session_id):
            if error:
                raise photos.PhotosError(error)
            return dict(self.SESSION if live is None else live)

        photos.get_session = fake_get_session
        photos.all_media_items = lambda _sid, **kw: list(self.ITEMS if items is None else items)
        self.addCleanup(lambda: [setattr(photos, n, v) for n, v in originals.items()])

        client = flask_app.test_client()
        with client.session_transaction() as sess:
            sess["admin"] = "admin"
            sess["photos_picker_session"] = "test-session"
        response = client.get("/admin/photos")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_setup_card_when_not_configured(self):
        html = self._stub(configured=False)
        self.assertIn("Set up Google Photos", html)
        self.assertNotIn("Start picking session", html)

    def test_idle_card_offers_a_new_session(self):
        html = self._stub(live={})
        self.assertIn("Start picking session", html)

    def test_live_picker_offers_the_link_and_refreshes(self):
        html = self._stub()
        self.assertIn("Open Google Photos picker", html)
        self.assertIn("/autoclose", html)
        self.assertIn('http-equiv="refresh"', html)
        self.assertIn('content="4"', html)
        self.assertIn("every 4 seconds", html)
        self.assertNotIn("Start picking session", html)

    def test_listed_pick_shows_every_item_and_stops_refreshing(self):
        html = self._stub(live={"mediaItemsSet": True}, items=self.ITEMS)
        self.assertIn("a.jpg", html)
        self.assertIn("b.png", html)
        # The count must match what an import will fetch, not just the first page.
        self.assertIn("Import 2 item(s)", html)
        self.assertNotIn('http-equiv="refresh"', html)

    def test_api_error_is_surfaced(self):
        html = self._stub(error="token refresh failed: invalid_grant")
        self.assertIn("token refresh failed", html)


class TemplateIntegrity(unittest.TestCase):
    """Block chains and url_for references resolve."""

    def _parse(self, name):
        with open(os.path.join(TEMPLATE_ROOT, name), encoding="utf-8") as fh:
            return flask_app.jinja_env.parse(fh.read())

    def _blocks(self, name):
        ast = self._parse(name)
        blocks = {b.name for b in ast.find_all(nodes.Block)}
        parent = None
        for node in ast.find_all(nodes.Extends):
            if isinstance(node.template, nodes.Const):
                parent = node.template.value
            break
        return blocks, parent

    def test_extends_targets_exist(self):
        for name in admin_templates():
            _blocks, parent = self._blocks(name)
            if parent and parent != name:
                with self.subTest(template=name):
                    self.assertTrue(
                        os.path.exists(os.path.join(TEMPLATE_ROOT, parent)),
                        "%s extends missing template %s" % (name, parent),
                    )

    def test_overrides_use_a_real_block_name(self):
        """A template may only override block names its shell actually defines.

        Jinja discards a block whose name no ancestor declares, so a typo or a
        stale name from before the shell refactor drops that section without any
        error. Restricting children to the shell's real vocabulary is what makes
        the silent failure impossible; a block a template *introduces* is fine,
        since admin/app.html defines page_title, page_actions and content for
        its own children.
        """
        info = {}
        for name in admin_templates():
            info[name] = self._blocks(name)

        for name, (blocks, parent) in info.items():
            if not blocks or not parent:
                continue
            allowed = self._inherited(info, name)
            with self.subTest(template=name):
                self.assertTrue(
                    blocks <= allowed or blocks & allowed,
                    "%s overrides no known block of %s: %s"
                    % (name, parent, sorted(blocks - allowed)),
                )
                unknown = {b for b in blocks if b not in allowed and b not in APP_BLOCKS}
                self.assertEqual(
                    unknown, set(),
                    "%s uses block names the admin shell never defines: %s"
                    % (name, sorted(unknown)),
                )


    def test_every_defined_block_is_used_by_a_descendant(self):
        """A block nobody renders is dead markup, usually a refactor leftover."""
        info = {}
        for name in admin_templates():
            info[name] = self._blocks(name)

        def extends(name, target, seen=None):
            """True when `name`'s chain reaches `target`."""
            seen = seen or set()
            if name in seen:
                return False
            seen.add(name)
            blocks, parent = info.get(name, (set(), None))
            if parent == target:
                return True
            return extends(parent, target, seen) if parent else False

        for name, (blocks, parent) in info.items():
            introduced = blocks - self._inherited(info, name)
            for block in sorted(introduced):
                consumers = [
                    other for other in info
                    if other != name and block in info[other][0] and extends(other, name)
                ]
                with self.subTest(template=name, block=block):
                    self.assertTrue(
                        consumers,
                        "%s defines block %r that no child renders" % (name, block),
                    )

    @staticmethod
    def _inherited(info, name):
        out = set()
        walk, seen = info.get(name, (set(), None))[1], set()
        while walk and walk not in seen:
            seen.add(walk)
            if walk not in info:
                break
            parent_blocks, walk = info[walk]
            out |= parent_blocks
        return out

    def test_url_for_targets_are_real_endpoints(self):
        endpoints = {r.endpoint for r in flask_app.url_map.iter_rules()}
        for name in admin_templates():
            with open(os.path.join(TEMPLATE_ROOT, name), encoding="utf-8") as fh:
                referenced = set(URL_FOR_RE.findall(fh.read()))
            for target in sorted(referenced):
                with self.subTest(template=name, endpoint=target):
                    self.assertIn(
                        target, endpoints,
                        "%s calls url_for('%s'), which is not a route" % (name, target),
                    )


class NavIntegrity(unittest.TestCase):
    """The sidebar's string endpoint tables stay in sync with the URL map."""

    def _nav_source(self):
        with open(os.path.join(TEMPLATE_ROOT, "admin/_nav.html"), encoding="utf-8") as fh:
            return fh.read()

    def test_nav_sections_and_children_exist(self):
        source = self._nav_source()
        endpoints = {r.endpoint for r in flask_app.url_map.iter_rules()}
        section_block, parent_block = source.split("nav_parent", 1)
        sections = set(re.findall(r"\('(admin_[A-Za-z0-9_]*)',\s*'", section_block))
        children = set(re.findall(r"'(admin_[A-Za-z0-9_]*)':", parent_block))
        targets = set(re.findall(r":\s*'(admin_[A-Za-z0-9_]*)'", parent_block))
        self.assertTrue(sections, "no nav sections parsed from _nav.html")
        for endpoint in sorted(sections | children):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, endpoints, "_nav.html names missing route %s" % endpoint)
        for target in sorted(targets):
            with self.subTest(target=target):
                self.assertIn(
                    target, sections,
                    "_nav.html maps a child to %s, which is not a nav section" % target,
                )

    def test_photos_and_drive_children_are_mapped(self):
        """The POST endpoints in the media area must keep the sidebar lit."""
        parent_block = self._nav_source().split("nav_parent", 1)[1]
        for endpoint in ("admin_photos_session", "admin_photos_cancel",
                         "admin_photos_import", "admin_drive_import", "admin_drive_link"):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, parent_block, "%s has no nav_parent entry" % endpoint)


if __name__ == "__main__":
    unittest.main()