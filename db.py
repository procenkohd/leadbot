"""
SQLite-хранилище: заявки на разработку и отзывы с модерацией.

Соединение открывается на каждый вызов и сразу закрывается — заявок мало,
бот один polling-процесс, отдельный пул соединений тут не нужен.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from storage import data_path

DB_PATH = data_path("leads.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT,
    bot_type TEXT NOT NULL,
    description TEXT NOT NULL,
    contact TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT NOT NULL,
    text TEXT NOT NULL,
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    admin_message_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guide_downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    full_name TEXT NOT NULL,
    downloaded_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_request(user_id: int, username: str | None, full_name: str, bot_type: str, description: str, contact: str) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO requests (user_id, username, full_name, bot_type, description, contact, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, full_name, bot_type, description, contact, _now()),
        )
        conn.commit()
        return cur.lastrowid


def add_review(user_id: int, username: str | None, full_name: str, text: str, is_anonymous: bool) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO reviews (user_id, username, full_name, text, is_anonymous, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (user_id, username, full_name, text, int(is_anonymous), _now()),
        )
        conn.commit()
        return cur.lastrowid


def set_review_admin_message_id(review_id: int, admin_message_id: int) -> None:
    with closing(_connect()) as conn:
        conn.execute(
            "UPDATE reviews SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, review_id),
        )
        conn.commit()


def get_review(review_id: int) -> sqlite3.Row | None:
    with closing(_connect()) as conn:
        return conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()


def set_review_status(review_id: int, status: str) -> None:
    with closing(_connect()) as conn:
        conn.execute("UPDATE reviews SET status = ? WHERE id = ?", (status, review_id))
        conn.commit()


def get_approved_reviews() -> list[sqlite3.Row]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM reviews WHERE status = 'approved' ORDER BY id DESC"
        ).fetchall()


def add_guide_download(user_id: int, username: str | None, full_name: str) -> int:
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO guide_downloads (user_id, username, full_name, downloaded_at)"
            " VALUES (?, ?, ?, ?)",
            (user_id, username, full_name, _now()),
        )
        conn.commit()
        return cur.lastrowid
