"""Per-group load state: the active load, its settings, and the last GPS ping.

A driver's Telegram group is the unit of tracking — the group's chat_id is the
driver identifier. One active load per group; a new RC replaces the old one.
"""

import sqlite3
from datetime import datetime, timezone

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS loads (
    chat_id       INTEGER PRIMARY KEY,
    load_id       TEXT,
    broker        TEXT,
    pu_address    TEXT,
    del_address   TEXT,
    pu_lat        REAL,
    pu_lon        REAL,
    del_lat       REAL,
    del_lon       REAL,
    pu_due        TEXT,
    del_due       TEXT,
    accepted      INTEGER NOT NULL DEFAULT 0,
    accepted_by   TEXT,
    accepted_at   TEXT,
    summary_msg   INTEGER,
    awaiting_doc  TEXT,
    driver_eta    TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locations (
    chat_id    INTEGER PRIMARY KEY,
    lat        REAL NOT NULL,
    lon        REAL NOT NULL,
    user_id    INTEGER,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    chat_id        INTEGER PRIMARY KEY,
    title          TEXT,
    lang           TEXT NOT NULL DEFAULT 'en',
    show_rate      INTEGER NOT NULL DEFAULT 1,
    interval_hours INTEGER NOT NULL DEFAULT 2
);

CREATE TABLE IF NOT EXISTS geocache (
    address TEXT PRIMARY KEY,
    lat     REAL,
    lon     REAL
);
"""

DEFAULT_SETTINGS = {"lang": "en", "show_rate": 1, "interval_hours": 2, "title": None}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------- settings


def get_settings(chat_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM settings WHERE chat_id = ?", (chat_id,)).fetchone()
    if row is None:
        return dict(DEFAULT_SETTINGS, chat_id=chat_id)
    return dict(row)


def ensure_settings(chat_id: int, title: str | None = None) -> dict:
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO settings (chat_id, title) VALUES (?, ?)", (chat_id, title))
        if title:
            conn.execute("UPDATE settings SET title = ? WHERE chat_id = ?", (title, chat_id))
    return get_settings(chat_id)


def update_setting(chat_id: int, field: str, value) -> None:
    if field not in ("lang", "show_rate", "interval_hours", "title"):
        raise ValueError(f"unknown setting: {field}")
    ensure_settings(chat_id)
    with connect() as conn:
        conn.execute(f"UPDATE settings SET {field} = ? WHERE chat_id = ?", (value, chat_id))


def known_groups() -> list[dict]:
    """Every group the bot has seen an RC in, for the settings picker."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM settings WHERE chat_id < 0 ORDER BY COALESCE(title, '')"
        ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------------ loads


def register_load(chat_id: int, **fields) -> None:
    """Replace the group's active load with a freshly extracted one."""
    cols = (
        "load_id", "broker", "pu_address", "del_address",
        "pu_lat", "pu_lon", "del_lat", "del_lon", "pu_due", "del_due",
    )
    values = {c: fields.get(c) for c in cols}
    with connect() as conn:
        conn.execute("DELETE FROM loads WHERE chat_id = ?", (chat_id,))
        conn.execute(
            f"INSERT INTO loads (chat_id, {', '.join(cols)}, created_at) "
            f"VALUES (?, {', '.join('?' * len(cols))}, ?)",
            (chat_id, *[values[c] for c in cols], _now()),
        )
        conn.execute("DELETE FROM locations WHERE chat_id = ?", (chat_id,))


def get_load(chat_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM loads WHERE chat_id = ?", (chat_id,)).fetchone()
    return dict(row) if row else None


def active_loads() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM loads WHERE accepted = 1").fetchall()
    return [dict(r) for r in rows]


def all_loads() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM loads").fetchall()
    return [dict(r) for r in rows]


def set_load_field(chat_id: int, field: str, value) -> None:
    allowed = {
        "accepted", "accepted_by", "accepted_at", "summary_msg",
        "awaiting_doc", "driver_eta", "pu_lat", "pu_lon", "del_lat", "del_lon",
    }
    if field not in allowed:
        raise ValueError(f"unknown load field: {field}")
    with connect() as conn:
        conn.execute(f"UPDATE loads SET {field} = ? WHERE chat_id = ?", (value, chat_id))


def accept_load(chat_id: int, who: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE loads SET accepted = 1, accepted_by = ?, accepted_at = ? WHERE chat_id = ?",
            (who, _now(), chat_id),
        )


def clear_load(chat_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM loads WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM locations WHERE chat_id = ?", (chat_id,))


# -------------------------------------------------------------------- locations


def save_location(chat_id: int, lat: float, lon: float, user_id: int | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO locations (chat_id, lat, lon, user_id, updated_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET lat=excluded.lat, lon=excluded.lon, "
            "user_id=excluded.user_id, updated_at=excluded.updated_at",
            (chat_id, lat, lon, user_id, _now()),
        )


def get_location(chat_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM locations WHERE chat_id = ?", (chat_id,)).fetchone()
    return dict(row) if row else None


def location_age_minutes(loc: dict) -> int:
    try:
        then = datetime.fromisoformat(loc["updated_at"])
    except (ValueError, KeyError, TypeError):
        return 10**6
    return int((datetime.now(timezone.utc) - then).total_seconds() // 60)


# --------------------------------------------------------------------- geocache


def cached_geocode(address: str) -> tuple[float, float] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT lat, lon FROM geocache WHERE address = ?", (address,)
        ).fetchone()
    if row and row["lat"] is not None:
        return row["lat"], row["lon"]
    return None


def cache_geocode(address: str, lat: float | None, lon: float | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO geocache (address, lat, lon) VALUES (?, ?, ?)",
            (address, lat, lon),
        )
