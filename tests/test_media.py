"""Unit tests for the media-import helpers hardened alongside the Photos picker.

These cover the pure functions, so no Google credentials or network are needed.
They pin the behaviour that protects the media library: a phone original must
never be stored under an extension that implies a browser can render it, and a
failed write must never leave a half-written file behind.

Run with:

    .venv/bin/python -m unittest discover -s tests -v
"""

import io
import os
import sqlite3
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="asaoz-media-")
os.environ["SECRET_KEY"] = "media-test-key-not-a-real-secret"
os.environ["ADMIN_PASSWORD"] = "media_test_password"
os.environ["DATABASE"] = os.path.join(_TMP, "media.sqlite3")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")
os.environ["APP_URL"] = "http://localhost:5000"

import app as application  # noqa: E402  (import must follow the env setup)

photos_extension = application._photos_extension
save_stream = application._save_stream
upload_abs = application._upload_abs
discard_partial = application._discard_partial


class PhotosExtension(unittest.TestCase):
    """A picked item is either given a serveable extension or skipped."""

    def test_renders_known_types(self):
        cases = [
            ({"filename": "IMG_0001.JPG", "mimeType": "image/jpeg"}, "jpg"),
            ({"filename": "shot.png", "mimeType": "image/png"}, "png"),
            ({"mimeType": "image/webp"}, "webp"),
            ({"mimeType": "video/mp4"}, "mp4"),
            ({"filename": "clip.mov", "mimeType": "video/quicktime"}, "mov"),
        ]
        for media, expected in cases:
            with self.subTest(media=media):
                self.assertEqual(photos_extension(media), expected)

    def test_skips_phone_originals(self):
        """HEIC and HEIF cannot be rendered, whichever field misreports it."""
        cases = [
            {"filename": "IMG_1234.HEIC", "mimeType": "image/heic"},
            {"filename": "IMG_1234.heic", "mimeType": "image/heic-sequence"},
            {"filename": "IMG_1234", "mimeType": "image/heic"},
            # MIME says renderable, the name says otherwise: trust the name.
            {"filename": "photo.heic", "mimeType": "image/jpeg"},
            {"filename": "photo.jpg", "mimeType": "image/heic"},
            {"filename": "clip.heif", "mimeType": "video/mp4"},
            {"filename": "photo.heif", "mimeType": "image/heif-sequence"},
        ]
        for media in cases:
            with self.subTest(media=media):
                self.assertEqual(photos_extension(media), "")

    def test_tolerates_missing_and_odd_metadata(self):
        for media in ({}, {"filename": ""}, {"mimeType": None}, {"mimeType": ""},
                      {"filename": "notes", "mimeType": "application/pdf"}):
            with self.subTest(media=media):
                self.assertEqual(photos_extension(media), "")

    def test_mime_parameters_do_not_break_the_lookup(self):
        self.assertEqual(
            photos_extension({"filename": "a.jpg", "mimeType": "IMAGE/JPEG; charset=binary"}),
            "jpg",
        )
        self.assertEqual(
            photos_extension({"filename": "a.jpg", "mimeType": "image/heic; charset=binary"}),
            "",
        )


class PollHint(unittest.TestCase):
    """The refresh interval is used as HTML meta content and as prose."""

    def test_returns_whole_seconds(self):
        for raw, expected in [("4s", 4), ("1.5s", 2), ("500ms", 2), ("10s", 10)]:
            with self.subTest(raw=raw):
                value = application.photos.poll_hint({"pollingConfig": {"pollInterval": raw}})
                self.assertEqual(value, expected)
                self.assertIsInstance(value, int)

    def test_falls_back_when_absent_or_unparseable(self):
        for session in ({}, {"pollingConfig": {}}, {"pollingConfig": None},
                        {"pollingConfig": {"pollInterval": "soon"}}):
            with self.subTest(session=session):
                self.assertEqual(application.photos.poll_hint(session), 3)


class _BrokenStream:
    """A stream that fails part-way through, as a dropped connection would."""

    def __init__(self, chunks, fail_at):
        self._chunks = chunks
        self._fail_at = fail_at
        self._index = 0

    def read(self, _size):
        if self._index >= self._fail_at:
            raise OSError("connection reset by peer")
        self._index += 1
        return self._chunks[self._index - 1]


class SaveStream(unittest.TestCase):
    """Writing bytes is all-or-nothing: no truncated files survive a failure."""

    def setUp(self):
        self.rel = "unittest/abcd1234.bin"
        abs_path = upload_abs(self.rel)
        if os.path.exists(abs_path):
            os.remove(abs_path)

    def test_writes_bytes_and_reports_size(self):
        payload = b"a" * 4096
        size = save_stream(io.BytesIO(payload), self.rel)
        self.assertEqual(size, len(payload))
        with open(upload_abs(self.rel), "rb") as fh:
            self.assertEqual(fh.read(), payload)

    def test_removes_partial_file_when_the_size_cap_is_hit(self):
        original = application.MAX_UPLOAD_MB
        application.MAX_UPLOAD_MB = 0
        try:
            with self.assertRaises(ValueError):
                save_stream(io.BytesIO(b"x" * 1024), self.rel)
        finally:
            application.MAX_UPLOAD_MB = original
        self.assertFalse(os.path.exists(upload_abs(self.rel)))

    def test_removes_partial_file_when_the_stream_fails(self):
        """A mid-download failure must not leave a plausible-looking file."""
        stream = _BrokenStream([b"x" * 1024, b"x" * 1024], fail_at=1)
        with self.assertRaises(OSError):
            save_stream(stream, self.rel)
        self.assertFalse(
            os.path.exists(upload_abs(self.rel)),
            "a truncated file was left behind after the stream failed",
        )

    def test_discard_partial_tolerates_a_missing_file(self):
        discard_partial("unittest/does-not-exist.bin")  # must not raise
        discard_partial(None)                            # must not raise


class PhotosIdUniqueness(unittest.TestCase):
    """The dedup key is enforced by the database, not just by a read."""

    def test_a_media_id_can_only_be_stored_once(self):
        conn = application.db.get_conn()
        try:
            names = {
                row["name"] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
            self.assertIn("idx_files_photos_id", names)
        finally:
            conn.close()

    def test_second_insert_of_the_same_id_is_rejected(self):
        # db.add_file returns nothing, so the guarantee is asserted by the
        # insert that must fail rather than by inspecting a return value.
        application.db.add_file(
            path="unittest/dup-a.bin", name="dup-a.bin", source="photos", photos_id="media-1"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            application.db.add_file(
                path="unittest/dup-b.bin", name="dup-b.bin", source="photos", photos_id="media-1"
            )

    def test_an_empty_id_is_not_a_duplicate(self):
        """Rows without a pick id must not collide on the empty string."""
        for suffix in ("a", "b"):
            application.db.add_file(
                path="unittest/empty-%s.bin" % suffix,
                name="empty-%s.bin" % suffix,
                source="photos", photos_id="",
            )
        rows = application.db.list_files()
        stored = [f for f in rows if f["path"].startswith("unittest/empty-")]
        self.assertEqual(len(stored), 2, "empty photos_id rows collided on the index")


if __name__ == "__main__":
    unittest.main()