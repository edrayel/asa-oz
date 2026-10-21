"""Tests for the keyless captcha.

ALTCHA's proof-of-work challenge: the browser solves a small puzzle and the
server checks the answer. There is no account, no API key and no third-party
request — so the tests can solve the challenge in Python and check that the
server accepts a real answer and rejects everything else.
"""

import os
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="asaoz-captcha-")
os.environ["SECRET_KEY"] = "captcha-test-key-not-a-real-secret"
os.environ["ADMIN_PASSWORD"] = "captcha_test_password"
os.environ["DATABASE"] = os.path.join(_TMP, "captcha.sqlite3")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["APP_URL"] = "http://localhost:5000"
os.environ["APP_ENV"] = "test"

for _key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ADMIN_EMAIL", "FROM_EMAIL",
             "GOOGLE_DRIVE_CREDENTIALS", "GOOGLE_PHOTOS_CREDENTIALS", "STRIPE_SECRET_KEY"):
    os.environ.pop(_key, None)

import app as application  # noqa: E402  (import must follow the env setup)
import captcha  # noqa: E402
import db as database  # noqa: E402

flask_app = application.app
flask_app.config["TESTING"] = True


def csrf_token(client, path):
    html = client.get(path).get_data(as_text=True)
    marker = 'name="_csrf" value="'
    assert marker in html, "no CSRF token on %s" % path
    return html.split(marker, 1)[1].split('"', 1)[0]


class Challenge(unittest.TestCase):
    def test_the_challenge_endpoint_returns_a_challenge(self):
        client = flask_app.test_client()
        response = client.get("/captcha/challenge")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        for key in ("algorithm", "challenge", "maxNumber", "salt", "signature"):
            self.assertIn(key, data)
        self.assertEqual(data["algorithm"], "SHA-256")
        self.assertGreater(data["maxNumber"], 0)

    def test_a_solved_challenge_verifies(self):
        payload = captcha.solve_for_tests()
        ok, reason = captcha.verify(payload)
        self.assertTrue(ok, reason)

    def test_a_garbage_payload_is_refused(self):
        ok, reason = captcha.verify("not-a-payload")
        self.assertFalse(ok)
        self.assertTrue(reason)

    def test_an_empty_payload_is_refused(self):
        ok, reason = captcha.verify("")
        self.assertFalse(ok)

    def test_a_payload_signed_with_another_key_is_refused(self):
        """A challenge signed with a different key must not pass."""
        import altcha
        import base64
        import datetime
        import json
        challenge = altcha.create_challenge_v1(
            algorithm="SHA-256", max_number=100000, hmac_key="somebody-elses-key",
            expires=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5),
        )
        solution = altcha.solve_challenge_v1(challenge)
        payload = challenge.to_dict()
        payload["number"] = solution.number
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        ok, _ = captcha.verify(encoded)
        self.assertFalse(ok)


class FormsAreProtected(unittest.TestCase):
    def setUp(self):
        # the suite shares one database
        conn = database.get_conn()
        for table in ("contacts", "feedback_items"):
            conn.execute("DELETE FROM %s" % table)
        conn.commit()
        conn.close()
        self.client = flask_app.test_client()

    def test_the_contact_form_refuses_a_post_without_a_captcha(self):
        token = csrf_token(self.client, "/contact")
        response = self.client.post("/contact-msg", data={
            "name": "Bot", "email": "bot@example.com", "message": "Hello there.",
            "_csrf": token,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("verification", response.get_data(as_text=True).lower())
        self.assertEqual(database.list_contacts(), [])

    def test_the_contact_form_accepts_a_solved_captcha(self):
        token = csrf_token(self.client, "/contact")
        response = self.client.post("/contact-msg", data={
            "name": "Person", "email": "person@example.com", "message": "Hello there.",
            "_csrf": token, "altcha": captcha.solve_for_tests(),
        })
        self.assertIn("Thank you", response.get_data(as_text=True))
        self.assertEqual(len(database.list_contacts()), 1)

    def test_the_feedback_form_refuses_a_post_without_a_captcha(self):
        token = csrf_token(self.client, "/")
        response = self.client.post("/feedback", data={
            "category": "General", "text": "Spam", "_csrf": token,
        })
        self.assertIn("verification", response.get_data(as_text=True).lower())
        self.assertEqual(len(database.list_feedback()), 0)

    def test_a_signed_in_user_is_exempt(self):
        """Signing in is already proof of a person, so the captcha is skipped."""
        user = database.get_user_by_username("admin")
        with self.client.session_transaction() as sess:
            sess["user_id"] = user["id"]
            sess["auth_version"] = user["auth_version"]
            sess["admin"] = user["username"]
        token = csrf_token(self.client, "/account/feedback")
        response = self.client.post("/account/feedback", data={
            "category": "General", "text": "A real note.", "_csrf": token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(database.list_feedback_for_user(user["id"])), 1)


if __name__ == "__main__":
    unittest.main()
