"""RC bot: extract rate confirmations, post them to a driver's group, track the load.

Flow: dispatcher drops an RC into a driver's group -> the bot extracts it and
posts a clean summary with map links and RPM -> the driver taps Accept -> the
summary is pinned and scheduled ETA updates begin from the driver's live
location -> the bot asks for BOL/POD when each appointment window passes.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import db
import extraction
import formatting
import geo
import tracking
from i18n import LANG_NAMES, LANGS, t

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
log = logging.getLogger("rcbot")

TZ = ZoneInfo(config.TIMEZONE)
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ETA_MESSAGE_CHARS = 200

INTERVAL_CHOICES = (1, 2, 3, 4, 6, 8, 12, 24)

# "ETA 3pm", "eta 15:30", "ETA - 7:45 AM"
ETA_RE = re.compile(
    r"\beta\b\D{0,12}(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.IGNORECASE
)
# Enough RC-shaped vocabulary that we don't spend API credits on group chatter.
RC_HINT_RE = re.compile(
    r"(load\s*#|rate\s*con|pu\s*#|bol\s*#|pickup|delivery|shipper|consignee)",
    re.IGNORECASE,
)


# --------------------------------------------------------------------- helpers


def lang_of(chat_id: int) -> str:
    return tracking.get_settings(chat_id).get("lang", "en")


def is_admin(user_id: int) -> bool:
    return config.ADMIN_TELEGRAM_ID and user_id == config.ADMIN_TELEGRAM_ID


def parse_iso_local(value: str | None) -> datetime | None:
    """Parse the model's local-time ISO string into an aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not config.ADMIN_TELEGRAM_ID:
        return
    try:
        await context.bot.send_message(
            config.ADMIN_TELEGRAM_ID, text, parse_mode=ParseMode.HTML
        )
    except TelegramError as exc:
        log.warning("could not reach admin: %s", exc)


def job_names(chat_id: int) -> dict[str, str]:
    return {
        "track": f"track:{chat_id}",
        "pu": f"pucheck:{chat_id}",
        "del": f"delcheck:{chat_id}",
    }


def cancel_jobs(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    for name in job_names(chat_id).values():
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()


# ----------------------------------------------------------------- RC handling


async def process_rc(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     payload: bytes | str, mime: str | None) -> None:
    """Extract an RC, post the summary, and offer the Accept button."""
    chat = update.effective_chat
    user = update.effective_user
    settings = tracking.ensure_settings(chat.id, chat.title)
    lang = settings["lang"]

    if not db.can_use(user.id):
        await update.effective_message.reply_text(
            t(lang, "paywall", free=config.FREE_TRIAL_RCS)
        )
        return

    notice = await update.effective_message.reply_text(t(lang, "extracting"))

    try:
        data = await extraction.extract(payload, mime)
    except extraction.ExtractionError as exc:
        await notice.edit_text(t(lang, "extract_failed", error=str(exc)))
        return
    except Exception as exc:  # noqa: BLE001 - surface anything else to the chat
        log.exception("extraction crashed")
        await notice.edit_text(t(lang, "extract_failed", error=str(exc)))
        return

    db.consume(user.id)

    pu_address = extraction.full_address(data.get("pickup"))
    del_address = extraction.full_address(data.get("delivery"))

    pu_coords = await geo.geocode(pu_address) if pu_address else None
    del_coords = await geo.geocode(del_address) if del_address else None

    miles = None
    if pu_coords and del_coords:
        leg = await geo.route(pu_coords, del_coords)
        if leg:
            miles = leg["miles"]
    if miles is None and data.get("stated_miles"):
        miles = float(data["stated_miles"])

    tracking.register_load(
        chat.id,
        load_id=data.get("load_id"),
        broker=data.get("broker"),
        pu_address=pu_address,
        del_address=del_address,
        pu_lat=pu_coords[0] if pu_coords else None,
        pu_lon=pu_coords[1] if pu_coords else None,
        del_lat=del_coords[0] if del_coords else None,
        del_lon=del_coords[1] if del_coords else None,
        pu_due=(data.get("pickup") or {}).get("datetime_iso"),
        del_due=(data.get("delivery") or {}).get("datetime_iso"),
    )

    summary = formatting.format_summary(data, lang, bool(settings["show_rate"]), miles)
    sent = await context.bot.send_message(
        chat.id, summary, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )
    tracking.set_load_field(chat.id, "summary_msg", sent.message_id)
    await notice.delete()

    load_label = data.get("load_id") or "—"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, "accept_button", load=load_label), callback_data="accept")
    ]])
    await context.bot.send_message(
        chat.id, t(lang, "accept_prompt", load=load_label), reply_markup=keyboard
    )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A document or photo: either the BOL/POD we asked for, or a new RC."""
    message = update.effective_message
    chat = update.effective_chat
    lang = lang_of(chat.id)

    load = tracking.get_load(chat.id)
    if load and load.get("awaiting_doc"):
        await receive_document(update, context, load)
        return

    if message.photo:
        tg_file = await message.photo[-1].get_file()
        mime = "image/jpeg"
    elif message.document:
        doc = message.document
        mime = doc.mime_type or ""
        if mime != "application/pdf" and not mime.startswith("image/"):
            await message.reply_text(t(lang, "unsupported_file"))
            return
        if doc.file_size and doc.file_size > MAX_FILE_BYTES:
            await message.reply_text(t(lang, "unsupported_file"))
            return
        tg_file = await doc.get_file()
    else:
        return

    payload = bytes(await tg_file.download_as_bytearray())
    await process_rc(update, context, payload, mime)


async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           load: dict) -> None:
    """Driver sent the BOL or POD we requested — acknowledge and forward it."""
    chat = update.effective_chat
    lang = lang_of(chat.id)
    kind = (load.get("awaiting_doc") or "").upper()

    tracking.set_load_field(chat.id, "awaiting_doc", None)
    await update.effective_message.reply_text(
        t(lang, "doc_received", kind=kind, load=load.get("load_id") or "—")
    )

    if config.ADMIN_TELEGRAM_ID:
        try:
            await context.bot.forward_message(
                config.ADMIN_TELEGRAM_ID, chat.id, update.effective_message.message_id
            )
        except TelegramError as exc:
            log.warning("could not forward %s: %s", kind, exc)
        await notify_admin(context, t("en", "dispatcher_doc", kind=kind,
                                      load=load.get("load_id") or "—",
                                      group=formatting.e(chat.title or chat.id)))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Plain text: a driver ETA, a pasted RC, or ordinary chatter we ignore."""
    message = update.effective_message
    chat = update.effective_chat
    text = message.text or ""

    if await try_driver_eta(update, context, text):
        return

    looks_like_rc = len(text) >= 120 and RC_HINT_RE.search(text)
    if chat.type == ChatType.PRIVATE:
        looks_like_rc = len(text) >= 80
    if looks_like_rc:
        await process_rc(update, context, text, None)


async def rc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/rc <text>, or /rc as a reply — force extraction of text we'd otherwise skip."""
    message = update.effective_message
    text = " ".join(context.args) if context.args else ""
    if not text and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
    if not text.strip():
        await message.reply_text(t(lang_of(update.effective_chat.id), "unsupported_file"))
        return
    await process_rc(update, context, text, None)


async def try_driver_eta(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         text: str) -> bool:
    """A driver typing an ETA overrides the routed estimate and alerts dispatch."""
    chat = update.effective_chat
    load = tracking.get_load(chat.id)
    if not load or not load.get("accepted"):
        return False

    # A full RC often says "provide ETA at pickup"; only a short message is a
    # driver actually reporting one.
    if len(text) > MAX_ETA_MESSAGE_CHARS:
        return False

    match = ETA_RE.search(text)
    if not match:
        return False

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return False

    now = datetime.now(TZ)
    eta = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if eta < now:
        eta += timedelta(days=1)

    tracking.set_load_field(chat.id, "driver_eta", eta.isoformat())

    lang = lang_of(chat.id)
    load_label = load.get("load_id") or "—"
    await update.effective_message.reply_text(
        t(lang, "driver_eta_saved", eta=formatting.fmt_12h(eta), load=load_label)
    )

    old = "—"
    computed = await compute_progress(chat.id, load)
    if computed and computed.get("eta"):
        old = formatting.fmt_12h(computed["eta"])
    who = update.effective_user.full_name if update.effective_user else "driver"
    await notify_admin(context, t("en", "dispatcher_eta_alert",
                                  load=formatting.e(load_label),
                                  group=formatting.e(chat.title or chat.id),
                                  who=formatting.e(who),
                                  eta=formatting.fmt_12h(eta), old=old))
    return True


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Live-location pings (silent) and one-time shares (acknowledged)."""
    message = update.effective_message
    loc = message.location
    if not loc:
        return

    chat = update.effective_chat
    tracking.save_location(
        chat.id, loc.latitude, loc.longitude,
        update.effective_user.id if update.effective_user else None,
    )

    # Live-location updates arrive constantly as edited messages; only a
    # deliberate one-time share deserves a reply.
    is_live = bool(loc.live_period) or update.edited_message is not None
    if not is_live:
        await message.reply_text(
            t(lang_of(chat.id), "location_received"),
            reply_markup=ReplyKeyboardRemove(),
        )


# ------------------------------------------------------------------- lifecycle


async def accept_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat = update.effective_chat
    lang = lang_of(chat.id)
    load = tracking.get_load(chat.id)

    if not load:
        await query.answer(t(lang, "no_load"), show_alert=True)
        return
    if load.get("accepted"):
        await query.answer()
        return

    who = update.effective_user.full_name if update.effective_user else "driver"
    tracking.accept_load(chat.id, who)
    await query.answer()

    settings = tracking.get_settings(chat.id)
    hours = settings["interval_hours"]
    load_label = load.get("load_id") or "—"

    await query.edit_message_text(
        t(lang, "accepted_by", who=formatting.e(who), load=formatting.e(load_label))
        + "\n\n" + t(lang, "tracking_on", hours=hours)
        + "\n" + t(lang, "share_live_hint"),
        parse_mode=ParseMode.HTML,
    )

    if load.get("summary_msg"):
        try:
            await context.bot.pin_chat_message(
                chat.id, load["summary_msg"], disable_notification=True
            )
        except TelegramError as exc:
            log.warning("pin failed in %s (is the bot an admin?): %s", chat.id, exc)

    # One tap gives an immediate fix; Live Location is what keeps it current.
    await context.bot.send_message(
        chat.id,
        t(lang, "location_keyboard_prompt"),
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(t(lang, "send_location_button"), request_location=True)]],
            one_time_keyboard=True, resize_keyboard=True,
        ),
    )

    schedule_tracking(context.application, chat.id, hours)
    schedule_deadlines(context.application, chat.id, load)


def schedule_tracking(app: Application, chat_id: int, hours: int) -> None:
    name = job_names(chat_id)["track"]
    for job in app.job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    app.job_queue.run_repeating(
        scheduled_update, interval=hours * 3600, first=hours * 3600,
        chat_id=chat_id, name=name,
    )


def schedule_deadlines(app: Application, chat_id: int, load: dict) -> None:
    names = job_names(chat_id)
    now = datetime.now(TZ)
    for key, field, callback in (
        ("pu", "pu_due", pickup_check),
        ("del", "del_due", delivery_check),
    ):
        for job in app.job_queue.get_jobs_by_name(names[key]):
            job.schedule_removal()
        due = parse_iso_local(load.get(field))
        if not due:
            continue
        # A window that already closed gets asked about shortly, not never.
        when = max(due, now + timedelta(minutes=2))
        app.job_queue.run_once(callback, when=when, chat_id=chat_id, name=names[key])


# ------------------------------------------------------------------------ jobs


async def compute_progress(chat_id: int, load: dict) -> dict | None:
    """Distance/ETA/status from the last known GPS ping."""
    loc = tracking.get_location(chat_id)
    if not loc:
        return None

    here = (loc["lat"], loc["lon"])
    age = tracking.location_age_minutes(loc)

    status = "status_en_route"
    if load.get("pu_lat") is not None:
        if geo.haversine_miles(here, (load["pu_lat"], load["pu_lon"])) <= config.ARRIVAL_RADIUS_MI:
            status = "status_at_pickup"
    if load.get("del_lat") is not None:
        if geo.haversine_miles(here, (load["del_lat"], load["del_lon"])) <= config.ARRIVAL_RADIUS_MI:
            status = "status_at_delivery"

    miles = hours = eta = None
    if load.get("del_lat") is not None:
        leg = await geo.route(here, (load["del_lat"], load["del_lon"]))
        if leg:
            miles, hours = leg["miles"], leg["hours"]
            eta = datetime.now(TZ) + timedelta(hours=hours)

    return {
        "status": status, "miles": miles, "hours": hours, "eta": eta,
        "age": age, "stale": age > config.STALE_LOCATION_MINUTES,
    }


async def scheduled_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    load = tracking.get_load(chat_id)
    if not load or not load.get("accepted"):
        context.job.schedule_removal()
        return

    lang = lang_of(chat_id)
    progress = await compute_progress(chat_id, load)

    if not progress:
        await context.bot.send_message(
            chat_id, t(lang, "upd_no_location", load=load.get("load_id") or "—")
        )
        return

    text = formatting.format_eta_update(
        load, lang, progress["status"], progress["miles"], progress["hours"],
        progress["eta"], progress["age"], progress["stale"],
        parse_iso_local(load.get("driver_eta")),
    )
    await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)


async def _stop_check(context: ContextTypes.DEFAULT_TYPE, stop: str) -> None:
    chat_id = context.job.chat_id
    load = tracking.get_load(chat_id)
    if not load or not load.get("accepted"):
        return

    lang = lang_of(chat_id)
    load_label = load.get("load_id") or "—"
    yes_key, question = (
        ("btn_picked", "pu_check_q") if stop == "pu" else ("btn_delivered", "del_check_q")
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(lang, yes_key), callback_data=f"stop:{stop}:yes"),
        InlineKeyboardButton(t(lang, "btn_not_yet"), callback_data=f"stop:{stop}:no"),
    ]])
    await context.bot.send_message(
        chat_id, t(lang, question, load=load_label), reply_markup=keyboard
    )


async def pickup_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    await _stop_check(context, "pu")


async def delivery_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    await _stop_check(context, "del")


async def stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat = update.effective_chat
    lang = lang_of(chat.id)
    _, stop, answer = query.data.split(":")

    load = tracking.get_load(chat.id)
    if not load:
        await query.answer(t(lang, "no_load"), show_alert=True)
        return
    await query.answer()

    load_label = load.get("load_id") or "—"
    who = update.effective_user.full_name if update.effective_user else "driver"
    yes_key = "btn_picked" if stop == "pu" else "btn_delivered"

    await notify_admin(context, t("en", "dispatcher_status",
                                  load=formatting.e(load_label),
                                  group=formatting.e(chat.title or chat.id),
                                  answer="yes" if answer == "yes" else "not yet",
                                  stop="pickup" if stop == "pu" else "delivery"))

    if answer == "no":
        await query.edit_message_text(t(lang, "not_yet_ack"))
        # Ask again in an hour rather than dropping the thread.
        context.job_queue.run_once(
            pickup_check if stop == "pu" else delivery_check,
            when=timedelta(hours=1), chat_id=chat.id, name=job_names(chat.id)[stop],
        )
        return

    kind = "bol" if stop == "pu" else "pod"
    tracking.set_load_field(chat.id, "awaiting_doc", kind)
    await query.edit_message_text(f"{t(lang, yes_key)} — {formatting.e(who)}")
    await context.bot.send_message(
        chat.id, t(lang, f"ask_{kind}", load=load_label), parse_mode=ParseMode.HTML
    )


# -------------------------------------------------------------------- commands


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = lang_of(update.effective_chat.id)
    await update.effective_message.reply_text(t(lang, "help"), parse_mode=ParseMode.HTML)


async def eta_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    lang = lang_of(chat.id)
    load = tracking.get_load(chat.id)

    if not load:
        await update.effective_message.reply_text(t(lang, "no_load"))
        return
    if not load.get("accepted"):
        await update.effective_message.reply_text(
            t(lang, "eta_not_accepted", load=load.get("load_id") or "—")
        )
        return

    progress = await compute_progress(chat.id, load)
    if not progress:
        await update.effective_message.reply_text(
            t(lang, "upd_no_location", load=load.get("load_id") or "—")
        )
        return

    await update.effective_message.reply_text(
        formatting.format_eta_update(
            load, lang, progress["status"], progress["miles"], progress["hours"],
            progress["eta"], progress["age"], progress["stale"],
            parse_iso_local(load.get("driver_eta")),
        ),
        parse_mode=ParseMode.HTML,
    )


async def finish_load(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                      message_key: str) -> str:
    """Stop everything for a group's load and return its label."""
    load = tracking.get_load(chat_id)
    label = (load or {}).get("load_id") or "—"
    cancel_jobs(context, chat_id)
    if load and load.get("summary_msg"):
        try:
            await context.bot.unpin_chat_message(chat_id, load["summary_msg"])
        except TelegramError:
            pass
    tracking.clear_load(chat_id)
    await context.bot.send_message(chat_id, t(lang_of(chat_id), message_key, load=label))
    return label


async def cancel_load(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    lang = lang_of(chat.id)

    if chat.type != ChatType.PRIVATE:
        if not tracking.get_load(chat.id):
            await update.effective_message.reply_text(t(lang, "cancel_none"))
            return
        await finish_load(context, chat.id, "cancel_done")
        return

    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(t(lang, "admin_only"))
        return

    loads = tracking.all_loads()
    if not loads:
        await update.effective_message.reply_text(t(lang, "cancel_no_loads"))
        return

    rows = []
    for load in loads:
        title = tracking.get_settings(load["chat_id"]).get("title") or load["chat_id"]
        rows.append([InlineKeyboardButton(
            f"#{load.get('load_id') or '—'} — {title}",
            callback_data=f"cancelpick:{load['chat_id']}",
        )])
    await update.effective_message.reply_text(
        t(lang, "cancel_choose"), reply_markup=InlineKeyboardMarkup(rows)
    )


async def cancel_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer(t("en", "admin_only"), show_alert=True)
        return
    chat_id = int(query.data.split(":")[1])
    await query.answer()
    label = await finish_load(context, chat_id, "cancel_done")
    await query.edit_message_text(t("en", "cancel_done", load=label))


async def delivered_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    lang = lang_of(chat.id)
    if chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(t(lang, "group_only"))
        return
    if not tracking.get_load(chat.id):
        await update.effective_message.reply_text(t(lang, "cancel_none"))
        return
    await finish_load(context, chat.id, "delivered_done")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = lang_of(update.effective_chat.id)
    info = db.status(update.effective_user.id)
    sub = t(lang, "sub_none")
    if info["sub_active"]:
        sub = t(lang, "sub_until", date=info["sub_until"][:10])
    await update.effective_message.reply_text(
        t(lang, "status_msg", free=info["free_left"], credits=info["credits"], sub=sub)
    )


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = lang_of(update.effective_chat.id)
    rows = []
    for key, plan in config.PRICING.items():
        label = (f"{plan['credits']} credits — {plan['price']}" if "credits" in plan
                 else f"{plan['days']} days — {plan['price']}")
        rows.append([InlineKeyboardButton(label, callback_data=f"buy:{key}")])
    await update.effective_message.reply_text(
        t(lang, "buy_title"), reply_markup=InlineKeyboardMarkup(rows)
    )


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    plan_key = query.data.split(":")[1]
    link = db.build_payment_link(update.effective_user.id, plan_key)
    await query.answer()
    lang = lang_of(update.effective_chat.id)
    await query.edit_message_text(link or t(lang, "buy_contact"))


async def grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = lang_of(update.effective_chat.id)
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(t(lang, "admin_only"))
        return

    args = context.args or []
    if len(args) != 3 or args[1] not in ("credits", "sub"):
        await update.effective_message.reply_text(t(lang, "grant_usage"))
        return
    try:
        target, amount = int(args[0]), int(args[2])
    except ValueError:
        await update.effective_message.reply_text(t(lang, "grant_usage"))
        return

    if args[1] == "credits":
        db.add_credits(target, amount)
    else:
        db.add_sub_days(target, amount)
    await update.effective_message.reply_text(t(lang, "granted"))


# -------------------------------------------------------------------- settings


def settings_menu(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    settings = tracking.get_settings(chat_id)
    lang = settings["lang"]
    rate = t(lang, "rate_shown" if settings["show_rate"] else "rate_hidden")
    title = settings.get("title") or chat_id
    rows = [
        [InlineKeyboardButton(t(lang, "settings_lang", value=LANG_NAMES[settings["lang"]]),
                              callback_data=f"set:lang:{chat_id}")],
        [InlineKeyboardButton(t(lang, "settings_interval", value=settings["interval_hours"]),
                              callback_data=f"set:int:{chat_id}")],
        [InlineKeyboardButton(t(lang, "settings_rate", value=rate),
                              callback_data=f"set:rate:{chat_id}")],
        [InlineKeyboardButton(t(lang, "btn_back"), callback_data="set:groups:0")],
    ]
    return t(lang, "settings_for", group=formatting.e(title)), InlineKeyboardMarkup(rows)


def groups_menu(lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
    groups = tracking.known_groups()
    if not groups:
        return t(lang, "settings_no_groups"), None
    rows = [[InlineKeyboardButton(g.get("title") or str(g["chat_id"]),
                                  callback_data=f"set:open:{g['chat_id']}")]
            for g in groups]
    return t(lang, "settings_pick_group"), InlineKeyboardMarkup(rows)


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    lang = lang_of(chat.id)
    if chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text(t(lang, "settings_private_only"))
        return
    if not is_admin(update.effective_user.id):
        await update.effective_message.reply_text(t(lang, "admin_only"))
        return

    text, markup = groups_menu(lang)
    await update.effective_message.reply_text(text, reply_markup=markup,
                                              parse_mode=ParseMode.HTML)


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer(t("en", "admin_only"), show_alert=True)
        return

    parts = query.data.split(":")
    action, target = parts[1], parts[2]
    await query.answer()

    if action == "groups":
        text, markup = groups_menu(lang_of(update.effective_chat.id))
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    chat_id = int(target)

    if action == "open":
        text, markup = settings_menu(chat_id)
        await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    if action == "lang":
        rows = [[InlineKeyboardButton(LANG_NAMES[code], callback_data=f"set:setlang:{chat_id}:{code}")]
                for code in LANGS]
        rows.append([InlineKeyboardButton(t("en", "btn_back"), callback_data=f"set:open:{chat_id}")])
        await query.edit_message_text(t(lang_of(chat_id), "settings_title"),
                                      reply_markup=InlineKeyboardMarkup(rows))
        return

    if action == "int":
        rows, row = [], []
        for hours in INTERVAL_CHOICES:
            row.append(InlineKeyboardButton(f"{hours}h", callback_data=f"set:setint:{chat_id}:{hours}"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton(t("en", "btn_back"), callback_data=f"set:open:{chat_id}")])
        await query.edit_message_text(t(lang_of(chat_id), "settings_title"),
                                      reply_markup=InlineKeyboardMarkup(rows))
        return

    if action == "rate":
        current = tracking.get_settings(chat_id)["show_rate"]
        tracking.update_setting(chat_id, "show_rate", 0 if current else 1)
    elif action == "setlang":
        tracking.update_setting(chat_id, "lang", parts[3])
    elif action == "setint":
        hours = int(parts[3])
        tracking.update_setting(chat_id, "interval_hours", hours)
        load = tracking.get_load(chat_id)
        if load and load.get("accepted"):
            schedule_tracking(context.application, chat_id, hours)

    text, markup = settings_menu(chat_id)
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------- startup


async def on_startup(app: Application) -> None:
    """Re-arm jobs for loads that were active when the bot last stopped."""
    restored = 0
    for load in tracking.active_loads():
        chat_id = load["chat_id"]
        schedule_tracking(app, chat_id, tracking.get_settings(chat_id)["interval_hours"])
        schedule_deadlines(app, chat_id, load)
        restored += 1
    log.info("restored tracking for %d load(s)", restored)


def build_application() -> Application:
    app = Application.builder().token(config.BOT_TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("rc", rc_command))
    app.add_handler(CommandHandler("eta", eta_command))
    app.add_handler(CommandHandler("cancel_load", cancel_load))
    app.add_handler(CommandHandler("delivered", delivered_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("grant", grant_command))
    app.add_handler(CommandHandler("settings", settings_command))

    app.add_handler(CallbackQueryHandler(accept_callback, pattern=r"^accept$"))
    app.add_handler(CallbackQueryHandler(stop_callback, pattern=r"^stop:"))
    app.add_handler(CallbackQueryHandler(cancel_pick_callback, pattern=r"^cancelpick:"))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy:"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^set:"))

    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


def main() -> None:
    missing = config.missing_required()
    if missing:
        raise SystemExit(
            "Missing required settings in .env: " + ", ".join(missing)
        )

    db.init()
    tracking.init()
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
