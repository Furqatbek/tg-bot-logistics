"""Environment-backed configuration, loaded once at import."""

import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw)
    except ValueError:
        return default


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ADMIN_TELEGRAM_ID = _int("ADMIN_TELEGRAM_ID", 0)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5").strip()
EXTRACTION_EFFORT = os.getenv("EXTRACTION_EFFORT", "medium").strip()

TIMEZONE = os.getenv("TIMEZONE", "America/New_York").strip()
FREE_TRIAL_RCS = _int("FREE_TRIAL_RCS", 5)

OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
CENSUS_URL = os.getenv("CENSUS_URL", "https://geocoding.geo.census.gov").rstrip("/")
PHOTON_URL = os.getenv("PHOTON_URL", "https://photon.komoot.io").rstrip("/")
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org").rstrip("/")
GEOCODER_CONTACT = os.getenv("GEOCODER_CONTACT", "unset@example.com").strip()

DB_PATH = os.getenv("DB_PATH", "bot.db")

# How close to an address the truck must be before we call it "at" that stop.
ARRIVAL_RADIUS_MI = 1.5
# A GPS ping older than this is reported as stale rather than trusted.
STALE_LOCATION_MINUTES = 90

# Placeholder pricing. Set real UZS amounts before taking payments.
PRICING = {
    "credits_10": {"credits": 10, "price": "25 000 UZS"},
    "credits_50": {"credits": 50, "price": "100 000 UZS"},
    "sub_30": {"days": 30, "price": "200 000 UZS"},
}


def missing_required() -> list[str]:
    """Names of settings the bot cannot start without."""
    missing = []
    if not BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    return missing
