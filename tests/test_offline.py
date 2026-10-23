"""Offline checks: no Telegram, no Anthropic, no network.

Run with:  venv/bin/python -m pytest tests/ -q
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("ADMIN_TELEGRAM_ID", "999")

import config  # noqa: E402
import db  # noqa: E402
import extraction  # noqa: E402
import formatting  # noqa: E402
import geo  # noqa: E402
import tracking  # noqa: E402
from i18n import EN, TRANSLATIONS, t  # noqa: E402

db.init()
tracking.init()

# The Jake Brake RC from the design conversation, as the model should return it.
SAMPLE = {
    "is_rate_confirmation": True,
    "load_id": "35840",
    "broker": "Jake Brake Logistics",
    "pu_number": "41767",
    "po_number": None,
    "bol_number": None,
    "ref_number": "GIO 7/28",
    "pickup": {
        "company": "INV-KIEWIT POWER CONSTRUC #33",
        "street": "33 CADY HILL BLVD",
        "city": "Saratoga Springs", "state": "NY", "zip": "12866",
        "phone": "838-250-8924",
        "date": "07/30/2026", "time_text": "7:00 AM",
        "datetime_iso": "2026-07-30T07:00",
    },
    "delivery": {
        "company": "SUPREME INDUSTRIES INC / SUPREME YARD",
        "street": "216 LOWER BOGUE ROAD",
        "city": "Harwinton", "state": "CT", "zip": "06791",
        "phone": "860-348-7789",
        "date": "07/30/2026", "time_text": "FCFS 7:00 AM - 4:00 PM",
        "datetime_iso": "2026-07-30T16:00",
    },
    "commodity": 'HARDWOOD-MIXED DENSE USED 8" <script>',
    "pieces": "20 PCS", "dimensions": "4X16/SOLID",
    "equipment": "Flatbed", "weight_lbs": "48000 lbs",
    "rate_usd": 950.0, "stated_miles": None,
    "requirements": ["Must call ahead & provide ETA at pickup", "No tarp required"],
    "conflicts": [],
}

MEGACORP_CONFLICTS = [
    "Pickup date differs: header says 2026-07-30, stops table says 2026-07-29.",
    "Delivery date differs: header says 2026-07-31, stops table says 2026-07-30.",
]


# ----------------------------------------------------------------------- i18n

def test_every_language_has_every_key():
    for code, table in TRANSLATIONS.items():
        missing = set(EN) - set(table)
        assert not missing, f"{code} is missing {sorted(missing)}"


def test_missing_key_falls_back_instead_of_raising():
    assert t("uz", "definitely_not_a_key") == "definitely_not_a_key"
    assert t("ru", "lbl_miles") == "Мили"


# ------------------------------------------------------------------ extraction

def test_schema_is_strict_and_complete():
    schema = extraction.RC_SCHEMA
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    for stop in ("pickup", "delivery"):
        sub = schema["properties"][stop]
        assert sub["additionalProperties"] is False
        assert set(sub["required"]) == set(sub["properties"])


def test_full_address_skips_missing_parts():
    assert extraction.full_address(SAMPLE["pickup"]) == \
        "33 CADY HILL BLVD, Saratoga Springs, NY, 12866"
    assert extraction.full_address({"street": "1 Main St", "city": "Ames"}) == "1 Main St, Ames"
    assert extraction.full_address(None) == ""


def test_pdf_and_image_build_different_blocks():
    pdf = extraction._content_blocks(b"%PDF-1.4", "application/pdf")
    assert pdf[0]["type"] == "document"
    assert pdf[0]["source"]["media_type"] == "application/pdf"
    img = extraction._content_blocks(b"\xff\xd8\xff", "image/jpeg")
    assert img[0]["type"] == "image"
    text = extraction._content_blocks("Load # 1", None)
    assert text[0]["type"] == "text"


# ------------------------------------------------------------------ formatting

def test_summary_with_rate_shown():
    out = formatting.format_summary(SAMPLE, "en", show_rate=True, miles=128.4)
    assert "Load # 35840" in out
    assert "Jake Brake Logistics" in out
    assert "PU# 41767" in out
    assert "Ref# GIO 7/28" in out
    assert "33 CADY HILL BLVD, Saratoga Springs, NY, 12866" in out
    assert "216 LOWER BOGUE ROAD, Harwinton, CT, 06791" in out
    assert "FCFS 7:00 AM - 4:00 PM" in out
    assert out.count("google.com/maps/dir") == 2          # one link per stop
    assert "Rate: $950" in out
    assert "Miles: 128 mi" in out
    assert "RPM: $7.40/mi" in out                          # 950 / 128.4
    assert "Must call ahead" in out
    assert "Macro-point is MUST" in out                    # static footer


def test_rate_hidden_keeps_miles_and_drops_money():
    out = formatting.format_summary(SAMPLE, "uz", show_rate=False, miles=128.4)
    assert "Milya: 128 mi" in out
    assert "$950" not in out
    assert "RPM" not in out
    assert "PU Manzil" in out                              # Uzbek labels
    assert "jarima" in out                                 # Uzbek footer


def test_delivery_block_is_never_truncated():
    out = formatting.format_summary(SAMPLE, "uz", show_rate=False, miles=100)
    delivery = out.split("DEL Manzil")[1]
    for fragment in ("SUPREME INDUSTRIES INC", "216 LOWER BOGUE ROAD",
                     "Harwinton", "06791", "860-348-7789", "maps/dir"):
        assert fragment in delivery, fragment


def test_document_content_is_html_escaped():
    out = formatting.format_summary(SAMPLE, "en", show_rate=True, miles=100)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_conflicts_surface_at_the_top():
    data = dict(SAMPLE, load_id="2683071", conflicts=MEGACORP_CONFLICTS)
    out = formatting.format_summary(data, "en", show_rate=True, miles=336)
    assert "Conflicting info" in out
    assert "header says 2026-07-30" in out
    assert out.index("Conflicting info") < out.index("PU Address")


def test_missing_rate_or_miles_does_not_crash():
    data = dict(SAMPLE, rate_usd=None)
    out = formatting.format_summary(data, "en", show_rate=True, miles=None)
    assert "not available" in out
    assert "RPM" not in out


def test_twelve_hour_clock_has_no_leading_zero():
    assert formatting.fmt_12h(datetime(2026, 7, 30, 7, 0)) == "7:00 AM"
    assert formatting.fmt_12h(datetime(2026, 7, 30, 16, 5)) == "4:05 PM"
    assert formatting.fmt_12h(datetime(2026, 7, 30, 0, 30)) == "12:30 AM"


def test_driver_eta_overrides_routed_eta():
    load = {"load_id": "35840"}
    routed = datetime(2026, 7, 30, 14, 0)
    driver = datetime(2026, 7, 30, 18, 30)
    out = formatting.format_eta_update(
        load, "en", "status_en_route", 64.0, 1.2, routed, 12, False, driver)
    assert "6:30 PM" in out
    assert "2:00 PM" not in out


def test_stale_location_is_flagged():
    out = formatting.format_eta_update(
        {"load_id": "1"}, "en", "status_en_route", 10.0, 0.3,
        datetime(2026, 7, 30, 9, 0), 240, True, None)
    assert "stopped sharing" in out


# ------------------------------------------------------------------------- geo

def test_maps_link_encodes_the_address():
    link = geo.maps_link("33 CADY HILL BLVD, Saratoga Springs, NY, 12866")
    assert link.startswith("https://www.google.com/maps/dir/?api=1&destination=")
    assert "33+CADY+HILL+BLVD" in link
    assert "travelmode=driving" in link


def test_haversine_roughly_matches_known_distance():
    saratoga = (43.0831, -73.7846)
    harwinton = (41.7592, -73.0665)
    miles = geo.haversine_miles(saratoga, harwinton)
    assert 90 < miles < 120, miles       # straight line is shorter than the 128mi drive


# -------------------------------------------------------------------- billing

def test_free_trial_then_block():
    uid = 1001
    for i in range(config.FREE_TRIAL_RCS):
        assert db.can_use(uid), f"blocked early at {i}"
        db.consume(uid)
    assert not db.can_use(uid)
    assert db.status(uid)["free_left"] == 0


def test_credits_resume_access_and_decrement():
    uid = 1002
    for _ in range(config.FREE_TRIAL_RCS):
        db.consume(uid)
    assert not db.can_use(uid)
    db.add_credits(uid, 2)
    assert db.can_use(uid)
    db.consume(uid)
    assert db.status(uid)["credits"] == 1


def test_subscription_does_not_consume_credits():
    uid = 1003
    db.add_credits(uid, 5)
    db.add_sub_days(uid, 30)
    for _ in range(10):
        db.consume(uid)
    status = db.status(uid)
    assert status["credits"] == 5
    assert status["sub_active"]


def test_payment_link_is_still_a_stub():
    assert db.build_payment_link(1, "credits_10") is None


# ------------------------------------------------------------------- tracking

def test_load_lifecycle():
    chat = -100123
    tracking.ensure_settings(chat, "Ali's group")
    tracking.register_load(chat, load_id="35840", pu_address="a", del_address="b",
                           pu_lat=1.0, pu_lon=2.0, del_lat=3.0, del_lon=4.0,
                           pu_due="2026-07-30T07:00", del_due="2026-07-30T16:00")
    load = tracking.get_load(chat)
    assert load["load_id"] == "35840"
    assert load["accepted"] == 0
    # Scoped to this chat: other tests share the same SQLite file.
    assert chat not in [l["chat_id"] for l in tracking.active_loads()]

    tracking.accept_load(chat, "Ali")
    assert tracking.get_load(chat)["accepted"] == 1
    assert chat in [l["chat_id"] for l in tracking.active_loads()]

    tracking.clear_load(chat)
    assert tracking.get_load(chat) is None


def test_new_rc_replaces_the_previous_load_and_its_gps():
    chat = -100124
    tracking.register_load(chat, load_id="A")
    tracking.save_location(chat, 40.0, -75.0, 7)
    tracking.accept_load(chat, "Odil")
    tracking.register_load(chat, load_id="B")
    load = tracking.get_load(chat)
    assert load["load_id"] == "B"
    assert load["accepted"] == 0                   # must be accepted again
    assert tracking.get_location(chat) is None     # stale GPS does not carry over


def test_groups_are_independent():
    ali, odil = -100201, -100202
    tracking.ensure_settings(ali, "Ali")
    tracking.ensure_settings(odil, "Odil")
    tracking.update_setting(ali, "lang", "uz")
    tracking.update_setting(ali, "show_rate", 0)
    tracking.update_setting(odil, "interval_hours", 6)

    a, o = tracking.get_settings(ali), tracking.get_settings(odil)
    assert (a["lang"], a["show_rate"], a["interval_hours"]) == ("uz", 0, 2)
    assert (o["lang"], o["show_rate"], o["interval_hours"]) == ("en", 1, 6)


def test_settings_default_before_any_write():
    s = tracking.get_settings(-999999)
    assert s["lang"] == "en" and s["show_rate"] == 1 and s["interval_hours"] == 2


def test_geocode_cache_remembers_misses():
    tracking.cache_geocode("nowhere at all", None, None)
    assert tracking.cached_geocode("nowhere at all") is None
    tracking.cache_geocode("somewhere", 1.5, -2.5)
    assert tracking.cached_geocode("somewhere") == (1.5, -2.5)


def test_unknown_field_names_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        tracking.update_setting(-1, "drop table", "x")
    with pytest.raises(ValueError):
        tracking.set_load_field(-1, "nonsense", 1)


# ------------------------------------------------------- bot-level pure logic

def test_eta_regex_catches_the_shapes_drivers_type():
    import bot
    for text, (hour, minute) in [
        ("ETA 3pm", (3, 0)),
        ("eta 15:30", (15, 30)),
        ("ETA - 7:45 AM", (7, 45)),
        ("my eta is 11pm, truck broke down", (11, 0)),
    ]:
        m = bot.ETA_RE.search(text)
        assert m, text
        assert int(m.group(1)) == hour
        assert int(m.group(2) or 0) == minute


def test_eta_regex_ignores_ordinary_chatter():
    import bot
    assert not bot.ETA_RE.search("on my way")
    assert not bot.ETA_RE.search("loaded 20 units")


def test_rc_hint_filter_avoids_spending_credits_on_chatter():
    import bot
    assert bot.RC_HINT_RE.search("Load # 35840 ... PU Address")
    assert not bot.RC_HINT_RE.search("ok boss on my way see you tomorrow morning")


def test_parse_iso_local_attaches_timezone():
    import bot
    dt = bot.parse_iso_local("2026-07-30T07:00")
    assert dt is not None and dt.tzinfo is not None
    assert dt.hour == 7
    assert bot.parse_iso_local(None) is None
    assert bot.parse_iso_local("garbage") is None
