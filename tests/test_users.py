"""Tests for the user role and management system.

Covers the parts that are easy to get wrong and expensive to get wrong in
production: who can see which admin area, who can hand out which role, that
a suspended account loses access on the next request, that an invitation can
be redeemed exactly once, and that the last superadmin cannot be locked out.
"""

import os
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="asaoz-users-")
os.environ["SECRET_KEY"] = "users-test-key-not-a-real-secret"
os.environ["ADMIN_PASSWORD"] = "users_test_password"
os.environ["DATABASE"] = os.path.join(_TMP, "users.sqlite3")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["APP_URL"] = "http://localhost:5000"
os.environ["MAIL_SYNC"] = "1"

for _key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ADMIN_EMAIL", "FROM_EMAIL",
             "GOOGLE_DRIVE_CREDENTIALS", "GOOGLE_PHOTOS_CREDENTIALS", "STRIPE_SECRET_KEY"):
    os.environ.pop(_key, None)

import app as application  # noqa: E402  (import must follow the env setup)
import db as database  # noqa: E402
import roles  # noqa: E402

flask_app = application.app
flask_app.config["TESTING"] = True


def make_user(username, role, status="active", password="a-long-enough-password"):
    """Create (or reset) a test account. The suite shares one database."""
    existing = database.get_user_by_username(username)
    if existing:
        database.delete_user(existing["id"])
    user, _token = database.create_user(username, f"{username}@example.com", "", role,
                                        password=password)
    if status != "active":
        database.set_user_status(user["id"], status)
        user = database.get_user(user["id"])
    return user


def reset_user(username):
    """Remove a leftover account so a test can create it again."""
    existing = database.get_user_by_username(username)
    if existing:
        database.delete_user(existing["id"])


def sign_in(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["auth_version"] = user["auth_version"]
        sess["admin"] = user["username"]


def csrf_token(client, path="/admin/users"):
    """Read a CSRF token off a rendered page, the way a browser would."""
    html = client.get(path).get_data(as_text=True)
    marker = 'name="_csrf" value="'
    assert marker in html, f"no CSRF token on {path}"
    return html.split(marker, 1)[1].split('"', 1)[0]


def post(client, path, data=None, token_from=None):
    """POST with the CSRF token, like a browser form does."""
    payload = dict(data or {})
    payload["_csrf"] = csrf_token(client, token_from or path)
    return client.post(path, data=payload)


class RoleMatrix(unittest.TestCase):
    def test_superadmin_holds_everything(self):
        for permission in roles.ALL_PERMISSIONS:
            self.assertTrue(roles.has_permission(roles.SUPERADMIN, permission), permission)

    def test_member_holds_nothing(self):
        for permission in roles.ALL_PERMISSIONS:
            self.assertFalse(roles.has_permission(roles.MEMBER, permission), permission)

    def test_marketing_manager_has_no_shop_access(self):
        self.assertTrue(roles.has_permission(roles.MARKETING, "content.pages"))
        self.assertTrue(roles.has_permission(roles.MARKETING, "audience.feedback"))
        self.assertFalse(roles.has_permission(roles.MARKETING, "shop.products"))
        self.assertFalse(roles.has_permission(roles.MARKETING, "system.settings"))
        self.assertFalse(roles.has_permission(roles.MARKETING, "system.users"))

    def test_ecommerce_manager_has_no_content_access(self):
        self.assertTrue(roles.has_permission(roles.ECOMMERCE, "shop.orders"))
        self.assertTrue(roles.has_permission(roles.ECOMMERCE, "shop.products"))
        self.assertFalse(roles.has_permission(roles.ECOMMERCE, "content.pages"))
        self.assertFalse(roles.has_permission(roles.ECOMMERCE, "system.restore"))

    def test_admin_cannot_hand_out_superadmin(self):
        self.assertFalse(roles.may_assign(roles.ADMIN, roles.SUPERADMIN))
        self.assertTrue(roles.may_assign(roles.ADMIN, roles.ADMIN))
        self.assertTrue(roles.may_assign(roles.ADMIN, roles.MARKETING))
        self.assertTrue(roles.may_assign(roles.SUPERADMIN, roles.SUPERADMIN))

    def test_unknown_route_is_superadmin_only(self):
        self.assertEqual(roles.permission_for("admin_not_a_real_route"), roles.SUPERADMIN_ONLY)
        self.assertEqual(roles.permission_for("admin_dashboard"), None)


class AdminAccess(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.test_client()
        self.superadmin = database.get_user_by_username("admin")
        self.marketing = make_user("maria", roles.MARKETING)
        self.ecommerce = make_user("eve", roles.ECOMMERCE)

    def test_logged_out_is_redirected(self):
        response = flask_app.test_client().get("/admin/products")
        self.assertEqual(response.status_code, 302)

    def test_marketing_manager_cannot_reach_the_shop(self):
        sign_in(self.client, self.marketing)
        self.assertEqual(self.client.get("/admin/products").status_code, 403)
        self.assertEqual(self.client.get("/admin/orders").status_code, 403)

    def test_marketing_manager_can_reach_content(self):
        sign_in(self.client, self.marketing)
        self.assertEqual(self.client.get("/admin/pages").status_code, 200)
        self.assertEqual(self.client.get("/admin/blog").status_code, 200)

    def test_ecommerce_manager_can_reach_the_shop(self):
        sign_in(self.client, self.ecommerce)
        self.assertEqual(self.client.get("/admin/products").status_code, 200)
        self.assertEqual(self.client.get("/admin/orders").status_code, 200)
        self.assertEqual(self.client.get("/admin/blog").status_code, 403)

    def test_sidebar_hides_what_the_role_cannot_use(self):
        sign_in(self.client, self.marketing)
        html = self.client.get("/admin").get_data(as_text=True)
        self.assertNotIn('href="/admin/products"', html)
        self.assertIn('href="/admin/pages"', html)

    def test_dashboard_only_counts_what_the_role_may_see(self):
        sign_in(self.client, self.ecommerce)
        html = self.client.get("/admin").get_data(as_text=True)
        self.assertNotIn(">Feedback<", html)
        self.assertIn(">Orders<", html)

    def test_suspending_an_account_ends_its_session(self):
        client = flask_app.test_client()
        sign_in(client, self.marketing)
        self.assertEqual(client.get("/admin/pages").status_code, 200)
        database.set_user_status(self.marketing["id"], "suspended")
        self.assertEqual(client.get("/admin/pages").status_code, 302)

    def test_role_change_ends_live_sessions(self):
        client = flask_app.test_client()
        sign_in(client, self.marketing)
        database.set_user_role(self.marketing["id"], roles.MEMBER)
        self.assertEqual(client.get("/admin/pages").status_code, 302)


class UserManagement(unittest.TestCase):
    def setUp(self):
        self.client = flask_app.test_client()
        self.superadmin = database.get_user_by_username("admin")
        sign_in(self.client, self.superadmin)

    def test_create_user_sends_an_invite_and_leaves_the_account_invited(self):
        reset_user("newbie")
        response = post(self.client, "/admin/users/new",
                        {"username": "newbie", "email": "newbie@example.com", "role": roles.MARKETING},
                        token_from="/admin/users")
        self.assertEqual(response.status_code, 302)
        user = database.get_user_by_username("newbie")
        self.assertIsNotNone(user)
        self.assertEqual(user["status"], "invited")
        self.assertTrue(user["invite_token"])

    def test_invite_can_be_redeemed_once(self):
        reset_user("redeemer")
        post(self.client, "/admin/users/new",
             {"username": "redeemer", "email": "redeemer@example.com", "role": roles.MARKETING},
             token_from="/admin/users")
        user = database.get_user_by_username("redeemer")
        client = flask_app.test_client()
        page = client.get(f"/invite/{user['invite_token']}")
        self.assertEqual(page.status_code, 200)
        # the CSRF token is in the form
        html = page.get_data(as_text=True)
        token = html.split('name="_csrf" value="')[1].split('"')[0]
        ok = client.post(f"/invite/{user['invite_token']}",
                         data={"password": "a-very-good-password", "confirm": "a-very-good-password",
                               "_csrf": token})
        self.assertEqual(ok.status_code, 302)
        fresh = database.get_user_by_username("redeemer")
        self.assertEqual(fresh["status"], "active")
        self.assertTrue(fresh["password_hash"])
        # the same link cannot be used twice
        again = flask_app.test_client().get(f"/invite/{user['invite_token']}")
        self.assertEqual(again.status_code, 404)

    def test_invite_requires_matching_passwords(self):
        reset_user("mismatch")
        post(self.client, "/admin/users/new",
             {"username": "mismatch", "email": "mismatch@example.com", "role": roles.ADMIN},
             token_from="/admin/users")
        user = database.get_user_by_username("mismatch")
        client = flask_app.test_client()
        html = client.get(f"/invite/{user['invite_token']}").get_data(as_text=True)
        token = html.split('name="_csrf" value="')[1].split('"')[0]
        client.post(f"/invite/{user['invite_token']}",
                    data={"password": "a-very-good-password", "confirm": "different",
                          "_csrf": token})
        self.assertEqual(database.get_user_by_username("mismatch")["status"], "invited")

    def test_admin_cannot_create_a_superadmin(self):
        admin_user = make_user("second-admin", roles.ADMIN)
        client = flask_app.test_client()
        sign_in(client, admin_user)
        reset_user("sneaky")
        post(client, "/admin/users/new",
             {"username": "sneaky", "email": "sneaky@example.com", "role": roles.SUPERADMIN},
             token_from="/admin/users")
        self.assertIsNone(database.get_user_by_username("sneaky"))

    def test_admin_cannot_edit_a_superadmin(self):
        client = flask_app.test_client()
        sign_in(client, make_user("another-admin", roles.ADMIN))
        response = post(client, f"/admin/users/{self.superadmin['id']}/role",
                        {"role": roles.MEMBER}, token_from=f"/admin/users/{self.superadmin['id']}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.get_user(self.superadmin["id"])["role"], roles.SUPERADMIN)

    def test_the_last_superadmin_cannot_be_demoted(self):
        client = flask_app.test_client()
        sign_in(client, self.superadmin)
        post(client, f"/admin/users/{self.superadmin['id']}/role", {"role": roles.ADMIN},
             token_from=f"/admin/users/{self.superadmin['id']}")
        self.assertEqual(database.get_user(self.superadmin["id"])["role"], roles.SUPERADMIN)

    def test_the_last_superadmin_cannot_be_suspended(self):
        client = flask_app.test_client()
        sign_in(client, self.superadmin)
        post(client, f"/admin/users/{self.superadmin['id']}/status", {"status": "suspended"},
             token_from=f"/admin/users/{self.superadmin['id']}")
        self.assertEqual(database.get_user(self.superadmin["id"])["status"], "active")

    def test_actions_are_logged(self):
        reset_user("logged")
        post(self.client, "/admin/users/new",
             {"username": "logged", "email": "logged@example.com", "role": roles.MEMBER},
             token_from="/admin/users")
        entries = database.list_audit(50)
        self.assertTrue(any(e["action"] == "user-created" for e in entries))


class LoginThrottle(unittest.TestCase):
    def test_repeated_failures_lock_the_account_out(self):
        client = flask_app.test_client()
        for _ in range(6):
            post(client, "/admin/login", {"username": "admin", "password": "wrong-password"},
                 token_from="/admin/login")
        response = post(client, "/admin/login", {"username": "admin", "password": "wrong-password"},
                        token_from="/admin/login")
        self.assertIn(b"Too many failed attempts", response.data)
        # a correct password is refused while the lock is on
        locked = post(client, "/admin/login",
                      {"username": "admin", "password": "users_test_password"},
                      token_from="/admin/login")
        self.assertIn(b"Too many failed attempts", locked.data)

    def test_a_successful_login_clears_the_counter(self):
        client = flask_app.test_client()
        post(client, "/admin/login", {"username": "admin", "password": "wrong-password"},
             token_from="/admin/login")
        post(client, "/admin/login", {"username": "admin", "password": "users_test_password"},
             token_from="/admin/login")
        again_client = flask_app.test_client()
        again = post(again_client, "/admin/login",
                     {"username": "admin", "password": "wrong-password"},
                     token_from="/admin/login")
        self.assertNotIn(b"Too many failed attempts", again.data)


if __name__ == "__main__":
    unittest.main()
