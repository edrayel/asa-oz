"""Tests for the public member accounts.

A member is a person with an account on the public site: they can share a
story, add a testimonial, leave feedback and see their orders. The rules that
matter are the ones about ownership — a member sees their own orders, and
nobody else's, even when they know the email address.
"""

import os
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="asaoz-accounts-")
os.environ["SECRET_KEY"] = "accounts-test-key-not-a-real-secret"
os.environ["ADMIN_PASSWORD"] = "accounts_test_password"
os.environ["DATABASE"] = os.path.join(_TMP, "accounts.sqlite3")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["APP_URL"] = "http://localhost:5000"
os.environ["APP_ENV"] = "test"
os.environ["MAIL_SYNC"] = "1"

for _key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ADMIN_EMAIL", "FROM_EMAIL",
             "GOOGLE_DRIVE_CREDENTIALS", "GOOGLE_PHOTOS_CREDENTIALS", "STRIPE_SECRET_KEY"):
    os.environ.pop(_key, None)

import app as application  # noqa: E402  (import must follow the env setup)
import db as database  # noqa: E402
import roles  # noqa: E402

flask_app = application.app
flask_app.config["TESTING"] = True

PASSWORD = "a-long-enough-password"


def csrf_token(client, path):
    html = client.get(path).get_data(as_text=True)
    marker = 'name="_csrf" value="'
    assert marker in html, "no CSRF token on %s" % path
    return html.split(marker, 1)[1].split('"', 1)[0]


def clean_members():
    """The suite shares one database: start every test from a clean slate."""
    conn = database.get_conn()
    conn.execute("DELETE FROM users WHERE role = 'member'")
    conn.execute("DELETE FROM testimonials")
    conn.execute("DELETE FROM feedback_items WHERE user_id != 0")
    conn.execute("DELETE FROM orders WHERE user_id != 0")
    conn.execute("DELETE FROM blog_posts WHERE user_id != 0")
    conn.commit()
    conn.close()


def signup(client, email="member@example.com", name="Mem Ber", password=PASSWORD):
    token = csrf_token(client, "/account/signup")
    return client.post("/account/signup", data={
        "email": email, "full_name": name, "password": password, "confirm": password,
        "_csrf": token,
    })


def logout(client):
    token = csrf_token(client, "/account")
    return client.post("/account/logout", data={"_csrf": token})


def login(client, email="member@example.com", password=PASSWORD):
    token = csrf_token(client, "/account/login")
    return client.post("/account/login", data={
        "login": email, "password": password, "_csrf": token,
    })


class MemberSignup(unittest.TestCase):
    def setUp(self):
        clean_members()
        self.client = flask_app.test_client()

    def test_signup_creates_an_active_member(self):
        response = signup(self.client)
        self.assertEqual(response.status_code, 302)
        user = database.get_user_by_email("member@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], roles.MEMBER)
        self.assertEqual(user["status"], "active")
        self.assertTrue(user["password_hash"])
        self.assertFalse(user["email_verified_at"])

    def test_signup_signs_the_member_in(self):
        signup(self.client)
        response = self.client.get("/account")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Mem Ber", response.get_data(as_text=True))

    def test_a_short_password_is_refused(self):
        response = signup(self.client, password="short")
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(database.get_user_by_email("member@example.com"))

    def test_two_different_passwords_are_refused(self):
        token = csrf_token(self.client, "/account/signup")
        response = self.client.post("/account/signup", data={
            "email": "member@example.com", "full_name": "Mem", "password": PASSWORD,
            "confirm": "something-else", "_csrf": token,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(database.get_user_by_email("member@example.com"))

    def test_a_second_account_for_the_same_email_is_refused(self):
        signup(self.client)
        other = flask_app.test_client()
        response = signup(other)
        self.assertEqual(response.status_code, 400)
        self.assertIn("already an account", response.get_data(as_text=True))

    def test_the_email_must_be_valid(self):
        response = signup(self.client, email="not-an-email")
        self.assertEqual(response.status_code, 400)


class MemberSignIn(unittest.TestCase):
    def setUp(self):
        clean_members()
        self.client = flask_app.test_client()
        signup(self.client)
        logout(self.client)

    def test_sign_in_with_the_email(self):
        response = login(self.client)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account", response.headers["Location"])

    def test_a_wrong_password_is_refused(self):
        response = login(self.client, password="not-the-password")
        self.assertEqual(response.status_code, 401)
        self.assertIn("not right", response.get_data(as_text=True))

    def test_the_account_pages_need_a_sign_in(self):
        for path in ("/account", "/account/orders", "/account/testimonial",
                     "/account/feedback", "/account/profile"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn("/account/login", response.headers["Location"])

    def test_a_member_cannot_reach_the_admin(self):
        login(self.client)
        response = self.client.get("/admin/users")
        self.assertIn(response.status_code, (302, 403))


class MemberOrders(unittest.TestCase):
    def setUp(self):
        clean_members()
        self.client = flask_app.test_client()
        signup(self.client)

    def test_an_order_placed_while_signed_in_is_theirs(self):
        user = database.get_user_by_email("member@example.com")
        database.add_order([{"id": "p", "name": "Trip", "price": 2500, "qty": 1}], 2500,
                           customer_email=user["email"], user_id=user["id"])
        html = self.client.get("/account/orders").get_data(as_text=True)
        self.assertIn("Trip", html)
        self.assertIn("2,500", html.replace("2500", "2,500"))

    def test_an_order_with_another_email_is_not_theirs(self):
        database.add_order([{"id": "p", "name": "Somebody else's", "price": 100, "qty": 1}],
                           100, customer_email="other@example.com")
        html = self.client.get("/account/orders").get_data(as_text=True)
        self.assertNotIn("Somebody else's", html)

    def test_an_order_on_their_email_appears_once_the_address_is_confirmed(self):
        database.add_order([{"id": "p", "name": "Earlier order", "price": 100, "qty": 1}],
                           100, customer_email="member@example.com")
        html = self.client.get("/account/orders").get_data(as_text=True)
        self.assertNotIn("Earlier order", html)

        user = database.get_user_by_email("member@example.com")
        database.set_user_email_verified(user["id"])
        html = self.client.get("/account/orders").get_data(as_text=True)
        self.assertIn("Earlier order", html)

    def test_the_verification_link_confirms_the_address(self):
        user = database.get_user_by_email("member@example.com")
        token = database.create_verify_token(user["id"])
        response = self.client.get("/account/verify/%s" % token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(database.get_user(user["id"])["email_verified_at"])

    def test_an_unknown_verification_token_is_refused(self):
        response = self.client.get("/account/verify/not-a-token")
        self.assertEqual(response.status_code, 404)


class MemberContent(unittest.TestCase):
    def setUp(self):
        clean_members()
        self.client = flask_app.test_client()
        signup(self.client)
        self.user = database.get_user_by_email("member@example.com")

    def test_feedback_is_linked_to_the_account(self):
        token = csrf_token(self.client, "/account/feedback")
        response = self.client.post("/account/feedback", data={
            "category": "General", "text": "The club is lovely.", "_csrf": token,
        })
        self.assertEqual(response.status_code, 302)
        rows = database.list_feedback_for_user(self.user["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "The club is lovely.")

    def test_a_testimonial_starts_as_new_and_is_shown_to_the_member(self):
        token = csrf_token(self.client, "/account/testimonial")
        self.client.post("/account/testimonial", data={
            "quote": "I came for a trip and stayed for the people.", "role": "Member",
            "_csrf": token,
        })
        rows = database.list_testimonials(user_id=self.user["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "new")
        self.assertIn("I came for a trip", self.client.get("/account").get_data(as_text=True))

    def test_only_approved_testimonials_reach_the_home_page(self):
        database.add_testimonial(self.user["id"], "Mem Ber", "Not on the page yet.")
        self.assertNotIn("Not on the page yet", self.client.get("/").get_data(as_text=True))
        row = database.list_testimonials(user_id=self.user["id"])[0]
        database.set_testimonial_status(row["id"], "approved")
        self.assertIn("Not on the page yet", self.client.get("/").get_data(as_text=True))

    def test_a_story_is_linked_to_the_account(self):
        token = csrf_token(self.client, "/blog/submit")
        self.client.post("/blog/submit", data={
            "title": "My story", "body": "It happened to me.", "_csrf": token,
        })
        posts = database.list_blog_posts_by_user(self.user["id"])
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["title"], "My story")
        # the submitter's address survives an admin edit
        database.save_blog_post({"id": posts[0]["id"], "title": "My story",
                                 "body": "Edited.", "status": "draft"}, publish=False)
        stored = database.get_blog_post(slug=posts[0]["slug"])
        self.assertEqual(stored["author_email"], self.user["email"])
        self.assertEqual(stored["user_id"], self.user["id"])

    def test_the_profile_can_be_updated(self):
        token = csrf_token(self.client, "/account/profile")
        response = self.client.post("/account/profile", data={
            "full_name": "New Name", "email": self.user["email"], "_csrf": token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.get_user(self.user["id"])["full_name"], "New Name")

    def test_changing_the_password_ends_the_old_session(self):
        token = csrf_token(self.client, "/account/profile")
        self.client.post("/account/profile", data={
            "full_name": self.user["full_name"], "email": self.user["email"],
            "current_password": PASSWORD, "password": "another-long-password",
            "_csrf": token,
        })
        # the auth_version moved, so the live session is no longer valid
        self.assertEqual(self.client.get("/account").status_code, 302)
        other = flask_app.test_client()
        self.assertEqual(login(other, password="another-long-password").status_code, 302)


class AdminTestimonialQueue(unittest.TestCase):
    def setUp(self):
        clean_members()
        self.admin = database.get_user_by_username("admin")
        self.client = flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["auth_version"] = self.admin["auth_version"]
            sess["admin"] = self.admin["username"]
        member = database.create_member("testimonial@example.com", "Testy", PASSWORD)[0]
        database.add_testimonial(member["id"], "Testy", "A fine quote.", "Member")

    def test_the_admin_sees_the_queue(self):
        html = self.client.get("/admin/testimonials").get_data(as_text=True)
        self.assertIn("A fine quote.", html)

    def test_the_admin_can_approve(self):
        row = database.list_testimonials()[0]
        token = csrf_token(self.client, "/admin/testimonials")
        response = self.client.post("/admin/testimonials/%d/status" % row["id"],
                                    data={"status": "approved", "_csrf": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(database.list_testimonials()[0]["status"], "approved")

    def test_the_admin_can_delete(self):
        row = database.list_testimonials()[0]
        token = csrf_token(self.client, "/admin/testimonials")
        self.client.post("/admin/testimonials/%d/delete" % row["id"], data={"_csrf": token})
        self.assertEqual(len(database.list_testimonials()), 0)


if __name__ == "__main__":
    unittest.main()
