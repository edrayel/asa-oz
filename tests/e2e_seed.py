"""Seed the E2E test database with representative content.

The audit is only meaningful when the CMS has something to show: a blog
post, a dynamic page, products, orders, bookings, feedback, subscribers,
contacts and media rows. Everything is written through the app's own
``db`` layer so the seeded rows look exactly like rows the CMS would
have written.

    .venv/bin/python tests/e2e_seed.py --db tests/.e2e/asaoz-e2e.sqlite3
"""

from __future__ import annotations

import argparse
import base64
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(HERE / ".e2e" / "asaoz-e2e.sqlite3"))
    parser.add_argument("--uploads", default=str(HERE / ".e2e" / "uploads"))
    args = parser.parse_args()

    os.environ.setdefault("SECRET_KEY", "e2e-secret-key-not-a-real-secret-0123456789")
    os.environ.setdefault("ADMIN_PASSWORD", "e2e-admin-password")
    os.environ["DATABASE"] = str(pathlib.Path(args.db).resolve())
    os.environ["UPLOAD_DIR"] = str(pathlib.Path(args.uploads).resolve())
    os.environ["APP_URL"] = "http://127.0.0.1:5055"
    for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ADMIN_EMAIL", "FROM_EMAIL",
                "GOOGLE_DRIVE_CREDENTIALS", "GOOGLE_PHOTOS_CREDENTIALS", "STRIPE_SECRET_KEY"):
        os.environ.pop(key, None)

    import db

    # Open the store so the store, cart and checkout surfaces are reachable.
    db.set_setting("show_store", "1")
    db.set_setting("show_prices", "1")

    db.add_feedback("general", "The wall of memories is the best part of the site.")
    db.add_feedback("membership", "Would love a member app.")
    db.add_waitlist("waitlist-a@example.com", "instagram")
    db.add_waitlist("waitlist-b@example.com", "referral")
    db.add_booking({"name": "Ada Example", "email": "ada@example.com", "phone": "+353800000001",
                    "message": "Evening discovery call", "date": "2026-11-02", "time": "18:00"})
    db.add_contact("Grace Example", "grace@example.com", "Is the membership open in Ireland?")
    db.subscribe_journey("subscriber-a@example.com", "Sam", "interest", "footer")
    db.subscribe_journey("subscriber-b@example.com", "Kim", "curious", "footer")
    db.add_order([{"id": "seed-product", "name": "Seed Product", "price": 2500, "qty": 1}],
                 2500, "buyer@example.com", "enquiry")
    seed_image = pathlib.Path(args.uploads) / "images" / "wall-of-memories"
    seed_image.mkdir(parents=True, exist_ok=True)
    (seed_image / "seed.jpg").write_bytes(base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
        "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
        "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="))
    existing = db.get_file_by_path("images/wall-of-memories/seed.jpg")
    if existing:
        db.delete_file(existing["id"])
    db.add_file("images/wall-of-memories/seed.jpg", "seed.jpg", "image", 1024, "image/jpeg", "upload")
    for item in db.list_navigation():
        if item["label"] == "Audit Link":
            db.delete_navigation_item(item["id"])
    db.save_navigation_item(0, "Audit Link", "/about", 99, True)
    db.save_dynamic_page("e2e-audit-page", "E2E audit page", "A seeded dynamic page.", "default", True)
    db.save_blog_post({
        "title": "Seeded audit story",
        "slug": "seeded-audit-story",
        "summary": "A seeded story so the blog index is not empty.",
        "body": "<p>Seeded body.</p>",
        "author": "Seed Author",
        "category": "general",
        "image": "",
    }, publish=True)
    print("seeded:", args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
