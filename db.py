"""Billing state: free trial counting, credits, subscriptions.

One SQLite file shared with tracking.py. All access goes through module-level
functions so the connection handling stays in one place.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username    TEXT,
    free_used   INTEGER NOT NULL DEFAULT 0,
    credits     INTEGER NOT NULL DEFAULT 0,
    sub_until   TEXT,
    created_at  TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_user(telegram_id: int, username: str | None = None) -> sqlite3.Row:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, created_at) VALUES (?, ?, ?)",
            (telegram_id, username, _now()),
        )
        if username:
            conn.execute(
                "UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id)
            )
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def _sub_active(row: sqlite3.Row) -> bool:
    if not row["sub_until"]:
        return False
    try:
        return datetime.fromisoformat(row["sub_until"]) > datetime.now(timezone.utc)
    except ValueError:
        return False


def free_left(row: sqlite3.Row) -> int:
    return max(0, config.FREE_TRIAL_RCS - row["free_used"])


def can_use(telegram_id: int) -> bool:
    row = ensure_user(telegram_id)
    return _sub_active(row) or row["credits"] > 0 or free_left(row) > 0


def consume(telegram_id: int) -> None:
    """Charge one extraction: subscription first, then free trial, then credits."""
    row = ensure_user(telegram_id)
    if _sub_active(row):
        return
    with connect() as conn:
        if free_left(row) > 0:
            conn.execute(
                "UPDATE users SET free_used = free_used + 1 WHERE telegram_id = ?",
                (telegram_id,),
            )
        elif row["credits"] > 0:
            conn.execute(
                "UPDATE users SET credits = credits - 1 WHERE telegram_id = ?",
                (telegram_id,),
            )


def add_credits(telegram_id: int, amount: int) -> None:
    ensure_user(telegram_id)
    with connect() as conn:
        conn.execute(
            "UPDATE users SET credits = credits + ? WHERE telegram_id = ?",
            (amount, telegram_id),
        )


def add_sub_days(telegram_id: int, days: int) -> None:
    row = ensure_user(telegram_id)
    base = datetime.now(timezone.utc)
    if row["sub_until"]:
        try:
            current = datetime.fromisoformat(row["sub_until"])
            base = max(base, current)
        except ValueError:
            pass
    until = (base + timedelta(days=days)).isoformat()
    with connect() as conn:
        conn.execute(
            "UPDATE users SET sub_until = ? WHERE telegram_id = ?", (until, telegram_id)
        )


def status(telegram_id: int) -> dict:
    row = ensure_user(telegram_id)
    return {
        "free_left": free_left(row),
        "credits": row["credits"],
        "sub_active": _sub_active(row),
        "sub_until": row["sub_until"],
    }


def build_payment_link(telegram_id: int, plan_key: str) -> str | None:
    """Stub for Click/Payme.

    Both gateways need a merchant account and a public HTTPS callback URL, so
    this stays unwired until the bot is on a VPS with a domain. Return a real
    checkout URL here and the /buy buttons start working; until then the bot
    tells the user to contact the admin and credits get added with /grant.
    """
    return None
