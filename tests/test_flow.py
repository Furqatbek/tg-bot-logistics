"""End-to-end lifecycle with Telegram and Claude stubbed out.

Drives the real handlers: RC posted -> summary -> Accept -> scheduled update ->
pickup check -> BOL request -> document received -> cancel.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "flow.db"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ["ADMIN_TELEGRAM_ID"] = "999"

import bot  # noqa: E402
import db  # noqa: E402
import extraction  # noqa: E402
import geo  # noqa: E402
import tracking  # noqa: E402
from tests.test_offline import SAMPLE  # noqa: E402

db.init()
tracking.init()

import itertools

_group_ids = itertools.count(-100777)
_driver_ids = itertools.count(4242)
GROUP = -100777
DRIVER = 4242


# ------------------------------------------------------------------- fakes


class FakeMessage:
    def __init__(self, bot_, chat_id, text=None, message_id=1):
        self._bot = bot_
        self.chat_id = chat_id
        self.text = text
        self.caption = None
        self.message_id = message_id
        self.photo = []
        self.document = None
        self.location = None
        self.reply_to_message = None
        self.deleted = False

    async def reply_text(self, text, **kw):
        return self._bot.record("reply", self.chat_id, text, kw)

    async def edit_text(self, text, **kw):
        self.text = text
        return self._bot.record("edit", self.chat_id, text, kw)

    async def delete(self):
        self.deleted = True


class FakeBot:
    def __init__(self):
        self.sent = []
        self.pinned = []
        self.unpinned = []
        self.forwarded = []
        self._next_id = 100

    def record(self, kind, chat_id, text, kw=None):
        self._next_id += 1
        msg = FakeMessage(self, chat_id, text, self._next_id)
        self.sent.append({"kind": kind, "chat_id": chat_id, "text": text,
                          "markup": (kw or {}).get("reply_markup")})
        return msg

    async def send_message(self, chat_id, text, **kw):
        return self.record("send", chat_id, text, kw)

    async def pin_chat_message(self, chat_id, message_id, **kw):
        self.pinned.append((chat_id, message_id))

    async def unpin_chat_message(self, chat_id, message_id=None):
        self.unpinned.append((chat_id, message_id))

    async def forward_message(self, to_chat, from_chat, message_id):
        self.forwarded.append((to_chat, from_chat, message_id))

    def texts(self, chat_id=None):
        return [s["text"] for s in self.sent
                if chat_id is None or s["chat_id"] == chat_id]

    def to_admin(self):
        return self.texts(999)


class FakeJob:
    def __init__(self, callback, name, chat_id, kind, when=None):
        self.callback, self.name, self.chat_id = callback, name, chat_id
        self.kind, self.when = kind, when
        self.removed = False

    def schedule_removal(self):
        self.removed = True


class FakeJobQueue:
    def __init__(self):
        self.jobs = []

    def get_jobs_by_name(self, name):
        return [j for j in self.jobs if j.name == name and not j.removed]

    def run_repeating(self, callback, interval, first, chat_id, name):
        job = FakeJob(callback, name, chat_id, "repeating", interval)
        self.jobs.append(job)
        return job

    def run_once(self, callback, when, chat_id, name):
        job = FakeJob(callback, name, chat_id, "once", when)
        self.jobs.append(job)
        return job

    def active(self):
        return [j for j in self.jobs if not j.removed]


class FakeApp:
    def __init__(self, jq):
        self.job_queue = jq


class FakeContext:
    def __init__(self, bot_, jq, args=None, job=None):
        self.bot = bot_
        self.job_queue = jq
        self.application = FakeApp(jq)
        self.args = args or []
        self.job = job


class FakeChat:
    def __init__(self, cid, title, ctype="supergroup"):
        self.id, self.title, self.type = cid, title, ctype


class FakeUser:
    def __init__(self, uid, name):
        self.id, self.full_name = uid, name


class FakeQuery:
    def __init__(self, bot_, data, chat_id):
        self._bot, self.data, self.chat_id = bot_, data, chat_id
        self.answered = False
        self.edited = None

    async def answer(self, text=None, show_alert=False):
        self.answered = True

    async def edit_message_text(self, text, **kw):
        self.edited = text
        self._bot.record("edit", self.chat_id, text, kw)


class FakeUpdate:
    def __init__(self, chat, user, message=None, query=None, edited=None):
        self.effective_chat = chat
        self.effective_user = user
        self.effective_message = message
        self.callback_query = query
        self.edited_message = edited


@pytest.fixture
def env(monkeypatch):
    # A fresh group and driver per test: they share one SQLite file, and a
    # reused driver would burn through the free trial partway down the suite.
    global GROUP, DRIVER
    GROUP = next(_group_ids)
    DRIVER = next(_driver_ids)
    fake_bot, jq = FakeBot(), FakeJobQueue()

    async def fake_extract(payload, mime=None):
        return SAMPLE

    async def fake_geocode(address):
        return (43.0619, -73.8219) if "CADY" in address else (41.7783, -73.1092)

    async def fake_route(a, b):
        return {"miles": 118.5, "hours": 2.85}

    monkeypatch.setattr(extraction, "extract", fake_extract)
    monkeypatch.setattr(geo, "geocode", fake_geocode)
    monkeypatch.setattr(geo, "route", fake_route)

    chat = FakeChat(GROUP, "Ali's group")
    tracking.ensure_settings(GROUP, "Ali's group")
    user = FakeUser(DRIVER, "Ali")
    return {"bot": fake_bot, "jq": jq, "chat": chat, "user": user,
            "group": GROUP, "ctx": FakeContext(fake_bot, jq)}


async def post_rc(env, text="Load # 35840 pickup delivery PU# 41767 " + "x" * 120):
    msg = FakeMessage(env["bot"], GROUP, text)
    update = FakeUpdate(env["chat"], env["user"], message=msg)
    await bot.process_rc(update, env["ctx"], text, None)
    return update


async def accept(env):
    query = FakeQuery(env["bot"], "accept", GROUP)
    update = FakeUpdate(env["chat"], env["user"], query=query)
    await bot.accept_callback(update, env["ctx"])
    return query


# ------------------------------------------------------------------- tests


@pytest.mark.asyncio
async def test_rc_posts_summary_and_accept_button_but_does_not_pin(env):
    await post_rc(env)

    summary = next(t for t in env["bot"].texts() if "Load # 35840" in t)
    assert "33 CADY HILL BLVD" in summary
    assert "RPM: $8.02/mi" in summary          # 950 / 118.5
    assert "Miles: 118 mi" in summary

    assert any("tap to confirm" in t for t in env["bot"].texts())
    assert env["bot"].pinned == []             # nothing pinned before acceptance
    assert env["jq"].active() == []            # and no tracking yet

    load = tracking.get_load(GROUP)
    assert load["load_id"] == "35840" and load["accepted"] == 0


@pytest.mark.asyncio
async def test_accept_pins_and_starts_tracking(env):
    await post_rc(env)
    query = await accept(env)

    assert "Ali accepted Load #35840" in query.edited
    assert len(env["bot"].pinned) == 1
    assert tracking.get_load(GROUP)["accepted"] == 1

    names = {j.name for j in env["jq"].active()}
    assert f"track:{GROUP}" in names
    assert f"pucheck:{GROUP}" in names
    assert f"delcheck:{GROUP}" in names

    assert any("Send my location" in str(s["markup"]) for s in env["bot"].sent)


@pytest.mark.asyncio
async def test_scheduled_update_needs_a_location_first(env):
    await post_rc(env)
    await accept(env)

    job = next(j for j in env["jq"].active() if j.kind == "repeating")
    await bot.scheduled_update(FakeContext(env["bot"], env["jq"], job=job))
    assert any("no live location" in t for t in env["bot"].texts())


@pytest.mark.asyncio
async def test_scheduled_update_reports_miles_and_eta(env):
    await post_rc(env)
    await accept(env)
    tracking.save_location(GROUP, 42.0, -73.5, DRIVER)

    job = next(j for j in env["jq"].active() if j.kind == "repeating")
    await bot.scheduled_update(FakeContext(env["bot"], env["jq"], job=job))

    update = env["bot"].texts()[-1]
    assert "Load #35840" in update
    assert "Miles to delivery: 118 mi" in update
    assert "ETA:" in update


@pytest.mark.asyncio
async def test_driver_at_pickup_is_detected_by_proximity(env):
    await post_rc(env)
    await accept(env)
    tracking.save_location(GROUP, 43.0619, -73.8219, DRIVER)   # on the pickup

    job = next(j for j in env["jq"].active() if j.kind == "repeating")
    await bot.scheduled_update(FakeContext(env["bot"], env["jq"], job=job))
    assert "Likely at pickup" in env["bot"].texts()[-1]


@pytest.mark.asyncio
async def test_driver_eta_overrides_and_alerts_dispatch(env):
    await post_rc(env)
    await accept(env)
    tracking.save_location(GROUP, 42.0, -73.5, DRIVER)

    msg = FakeMessage(env["bot"], GROUP, "truck broke down, ETA 9pm")
    update = FakeUpdate(env["chat"], env["user"], message=msg)
    handled = await bot.try_driver_eta(update, env["ctx"], msg.text)

    assert handled
    assert tracking.get_load(GROUP)["driver_eta"] is not None
    assert any("ETA change" in t for t in env["bot"].to_admin())

    job = next(j for j in env["jq"].active() if j.kind == "repeating")
    await bot.scheduled_update(FakeContext(env["bot"], env["jq"], job=job))
    assert "9:00 PM" in env["bot"].texts()[-1]


@pytest.mark.asyncio
async def test_ordinary_chatter_is_not_mistaken_for_an_eta(env):
    await post_rc(env)
    await accept(env)
    msg = FakeMessage(env["bot"], GROUP, "ok boss, on my way")
    update = FakeUpdate(env["chat"], env["user"], message=msg)
    assert not await bot.try_driver_eta(update, env["ctx"], msg.text)


@pytest.mark.asyncio
async def test_pickup_check_asks_for_bol_and_document_is_forwarded(env):
    await post_rc(env)
    await accept(env)

    pu_job = next(j for j in env["jq"].active() if j.name == f"pucheck:{GROUP}")
    await bot.pickup_check(FakeContext(env["bot"], env["jq"], job=pu_job))
    assert any("Did you pick up?" in t for t in env["bot"].texts())

    query = FakeQuery(env["bot"], "stop:pu:yes", GROUP)
    await bot.stop_callback(FakeUpdate(env["chat"], env["user"], query=query), env["ctx"])

    assert tracking.get_load(GROUP)["awaiting_doc"] == "bol"
    assert any("BOL" in t for t in env["bot"].texts())
    assert any("answered \"yes\"" in t for t in env["bot"].to_admin())

    photo_msg = FakeMessage(env["bot"], GROUP, None, message_id=555)
    update = FakeUpdate(env["chat"], env["user"], message=photo_msg)
    await bot.receive_document(update, env["ctx"], tracking.get_load(GROUP))

    assert tracking.get_load(GROUP)["awaiting_doc"] is None
    assert env["bot"].forwarded == [(999, GROUP, 555)]


@pytest.mark.asyncio
async def test_not_yet_reschedules_instead_of_dropping_it(env):
    await post_rc(env)
    await accept(env)

    query = FakeQuery(env["bot"], "stop:pu:no", GROUP)
    await bot.stop_callback(FakeUpdate(env["chat"], env["user"], query=query), env["ctx"])

    assert tracking.get_load(GROUP)["awaiting_doc"] is None
    retry = [j for j in env["jq"].active()
             if j.name == f"pucheck:{GROUP}" and j.kind == "once"]
    assert retry, "pickup check should be asked again later"


@pytest.mark.asyncio
async def test_cancel_stops_every_job_and_unpins(env):
    await post_rc(env)
    await accept(env)
    assert env["jq"].active()

    await bot.finish_load(env["ctx"], GROUP, "cancel_done")

    assert tracking.get_load(GROUP) is None
    assert env["jq"].active() == []
    assert env["bot"].unpinned
    assert any("cancelled" in t for t in env["bot"].texts())


@pytest.mark.asyncio
async def test_rate_hidden_group_sees_miles_but_no_money(env):
    tracking.ensure_settings(GROUP, "Ali's group")
    tracking.update_setting(GROUP, "show_rate", 0)
    tracking.update_setting(GROUP, "lang", "uz")
    try:
        await post_rc(env)
        summary = next(t for t in env["bot"].texts() if "Load # 35840" in t)
        assert "Milya: 118 mi" in summary
        assert "$950" not in summary and "RPM" not in summary
        assert "PU Manzil" in summary
    finally:
        tracking.update_setting(GROUP, "show_rate", 1)
        tracking.update_setting(GROUP, "lang", "en")


@pytest.mark.asyncio
async def test_paywall_blocks_once_the_trial_is_spent(env, monkeypatch):
    broke = FakeUser(5555, "Broke Dispatcher")
    for _ in range(bot.config.FREE_TRIAL_RCS):
        db.consume(broke.id)

    msg = FakeMessage(env["bot"], GROUP, "Load # 1")
    update = FakeUpdate(env["chat"], broke, message=msg)
    await bot.process_rc(update, env["ctx"], "Load # 1", None)

    assert any("free extractions" in t for t in env["bot"].texts())
    assert not any("Load # 35840" in t for t in env["bot"].texts())


@pytest.mark.asyncio
async def test_extraction_failure_is_reported_not_swallowed(env, monkeypatch):
    async def boom(payload, mime=None):
        raise extraction.ExtractionError("not a rate confirmation")

    monkeypatch.setattr(extraction, "extract", boom)
    await post_rc(env)
    assert any("not a rate confirmation" in t for t in env["bot"].texts())
    assert tracking.get_load(GROUP) is None


@pytest.mark.asyncio
async def test_restart_restores_tracking_jobs(env):
    await post_rc(env)
    await accept(env)

    fresh = FakeJobQueue()
    await bot.on_startup(FakeApp(fresh))

    names = {j.name for j in fresh.active()}
    assert f"track:{GROUP}" in names


@pytest.mark.asyncio
async def test_yes_answer_confirms_the_stop_not_the_acceptance(env):
    await post_rc(env)
    await accept(env)
    query = FakeQuery(env["bot"], "stop:pu:yes", GROUP)
    await bot.stop_callback(FakeUpdate(env["chat"], env["user"], query=query), env["ctx"])
    assert "Picked up" in query.edited
    assert "accepted" not in query.edited.lower()


@pytest.mark.asyncio
async def test_pasted_rc_mentioning_eta_is_not_read_as_a_driver_eta(env):
    await post_rc(env)
    await accept(env)
    rc_text = (
        "Load # 35840 Jake Brake Logistics PU# 41767 pickup delivery "
        "Must call ahead & provide ETA at pickup 7 days a week. "
    ) * 3
    msg = FakeMessage(env["bot"], GROUP, rc_text)
    update = FakeUpdate(env["chat"], env["user"], message=msg)
    assert not await bot.try_driver_eta(update, env["ctx"], rc_text)
    assert tracking.get_load(GROUP)["driver_eta"] is None
