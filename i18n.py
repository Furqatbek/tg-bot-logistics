"""EN / RU / UZ strings.

Every key must exist in ``en``; ``ru`` and ``uz`` fall back to it when a key
is missing, so a half-finished translation degrades instead of crashing.
"""

LANGS = ("en", "ru", "uz")
LANG_NAMES = {"en": "English", "ru": "Русский", "uz": "O'zbekcha"}

EN = {
    "extracting": "Reading the RC…",
    "extract_failed": "Couldn't read that document: {error}",
    "not_a_load": "That doesn't look like a rate confirmation — no load number or addresses found.",
    "unsupported_file": "Send a PDF, a photo, or paste the RC as text.",

    "conflicts_header": "⚠️ Conflicting info in the RC — verify with the broker before trusting either value:",
    "lbl_pu_address": "PU Address",
    "lbl_del_address": "DEL Address",
    "lbl_pu_date": "PU Date",
    "lbl_del_date": "DEL Date",
    "lbl_phone": "Phone",
    "lbl_directions": "🗺 Directions",
    "lbl_equipment": "Equipment",
    "lbl_weight": "Weight",
    "lbl_rate": "Rate",
    "lbl_miles": "Miles",
    "lbl_rpm": "RPM",
    "lbl_requirements": "⚠️ Additional requirements",
    "miles_unknown": "not available",
    "footer": (
        "⏰Late pick up = $250 fine❗️\n"
        "⏰Late delivery = $250 fine❗️\n"
        "📱Macro-point is MUST / $250 fine❗️\n"
        "📝BOL/POD/ Freight pictures/Seal pictures MUST send otherwise $250 fine❗️\n"
        "🚨 No update / $250 fine❗️\n"
        "Your communication is really important to keep the business going smoothly❗️"
    ),

    "accept_prompt": "Driver: tap to confirm you've taken Load #{load}. Tracking starts after that.",
    "accept_button": "✅ Accept Load #{load}",
    "accepted_by": "✅ {who} accepted Load #{load}.",
    "tracking_on": "📡 Tracking is on for this group — updates every {hours}h.",
    "share_live_hint": "Driver: tap 📎 Attach → Location → <b>Share Live Location</b> so updates keep coming.",
    "send_location_button": "📍 Send my location",
    "location_received": "📍 Location received, thanks.",
    "location_keyboard_prompt": "Tap the button below to send your current location.",

    "upd_title": "Load #{load} — {status}",
    "status_en_route": "En route",
    "status_at_pickup": "📍 Likely at pickup",
    "status_at_delivery": "✅ Likely at delivery",
    "upd_miles_left": "Miles to delivery: {miles} mi",
    "upd_eta": "ETA: ~{eta} (about {hours}h)",
    "upd_loc_age": "(location updated {mins} min ago)",
    "upd_loc_stale": "⚠️ Location is {mins} min old — driver may have stopped sharing.",
    "upd_no_location": "Load #{load}: no live location received yet — ask the driver to share it.",
    "upd_driver_eta": "ETA (from driver): ~{eta}",

    "cancel_done": "❌ Load #{load} cancelled. Tracking stopped.",
    "cancel_none": "No active load in this group.",
    "cancel_choose": "Pick the load to cancel:",
    "cancel_no_loads": "No active loads anywhere.",

    "pu_check_q": "Load #{load}: pickup time has passed. Did you pick up?",
    "del_check_q": "Load #{load}: delivery time has passed. Did you deliver?",
    "btn_picked": "✅ Picked up",
    "btn_delivered": "✅ Delivered",
    "btn_not_yet": "❌ Not yet",
    "ask_bol": "Send the <b>BOL</b> photo for Load #{load} now.",
    "ask_pod": "Send the <b>POD</b> photo for Load #{load} now.",
    "doc_received": "✅ {kind} received for Load #{load}. Forwarded to dispatch.",
    "not_yet_ack": "Noted — I'll ask again later. Tell dispatch if something is wrong.",
    "delivered_done": "✅ Load #{load} marked delivered. Tracking stopped.",

    "driver_eta_saved": "✅ Got it — using your ETA of {eta} for Load #{load}.",
    "dispatcher_eta_alert": "🔔 ETA change — Load #{load} ({group})\nDriver {who} reported ETA {eta}.\nOriginal estimate: {old}.",
    "dispatcher_doc": "📄 {kind} for Load #{load} from {group}.",
    "dispatcher_status": "🔔 Load #{load} ({group}): driver answered \"{answer}\" to the {stop} check.",

    "settings_title": "⚙️ Settings",
    "settings_pick_group": "Pick a driver group to configure:",
    "settings_for": "⚙️ Settings for <b>{group}</b>",
    "settings_lang": "🌐 Language: {value}",
    "settings_interval": "⏱ Update interval: {value}h",
    "settings_rate": "💵 Rate: {value}",
    "rate_shown": "shown",
    "rate_hidden": "hidden",
    "settings_saved": "Saved.",
    "settings_no_groups": "No driver groups yet. Add the bot to a group and send an RC there first.",
    "btn_back": "‹ Back",
    "settings_private_only": "Open settings in a private chat with me, not in the group.",

    "paywall": "You've used your {free} free extractions. Use /buy for credits or a subscription, or ask the admin for access.",
    "status_msg": "Free left: {free}\nCredits: {credits}\nSubscription: {sub}",
    "sub_none": "none",
    "sub_until": "active until {date}",
    "buy_title": "Pick a plan (payment is not wired up yet — contact the admin to activate):",
    "buy_contact": "Payment gateway isn't connected yet. Message the admin to get credits added.",
    "granted": "✅ Granted.",
    "grant_usage": "Usage: /grant <telegram_id> credits <n>  |  /grant <telegram_id> sub <days>",
    "admin_only": "Admin only.",
    "group_only": "Use this in a driver's group.",

    "help": (
        "<b>RC Bot</b>\n\n"
        "Send a rate confirmation (PDF, photo, or text) into a driver's group. "
        "I extract it, post a clean summary with map links and RPM, and wait for the driver to accept. "
        "After that I post ETA updates from the driver's live location.\n\n"
        "<b>In a driver group</b>\n"
        "/eta — distance and ETA right now\n"
        "/cancel_load — cancel the active load\n"
        "/delivered — close the load out\n\n"
        "<b>In private chat with me</b>\n"
        "/settings — language, update interval, rate visibility per group\n"
        "/cancel_load — cancel any load remotely\n"
        "/status — your usage\n"
        "/buy — plans"
    ),
    "eta_not_accepted": "Load #{load} hasn't been accepted yet — tracking starts after the driver taps Accept.",
    "no_load": "No load registered in this group yet.",
}

RU = {
    "footer": (
        "⏰Опоздание на погрузку = штраф $250❗️\n"
        "⏰Опоздание на выгрузку = штраф $250❗️\n"
        "📱Macro-point ОБЯЗАТЕЛЕН / штраф $250❗️\n"
        "📝BOL/POD/ фото груза/фото пломбы ОБЯЗАТЕЛЬНО, иначе штраф $250❗️\n"
        "🚨 Нет обновлений / штраф $250❗️\n"
        "Ваша связь очень важна для бесперебойной работы❗️"
    ),
    "help": (
        "<b>RC Bot</b>\n\n"
        "Отправьте rate confirmation (PDF, фото или текст) в группу водителя. "
        "Я извлеку данные, опубликую сводку с картами и ставкой за милю и буду ждать подтверждения водителя. "
        "После этого начну присылать ETA по его геопозиции.\n\n"
        "<b>В группе водителя</b>\n"
        "/eta — расстояние и ETA сейчас\n"
        "/cancel_load — отменить загрузку\n"
        "/delivered — закрыть загрузку\n\n"
        "<b>В личном чате</b>\n"
        "/settings — язык, интервал, видимость ставки по группам\n"
        "/cancel_load — отменить любую загрузку\n"
        "/status — ваш лимит\n"
        "/buy — тарифы"
    ),
    "extracting": "Читаю RC…",
    "extract_failed": "Не удалось прочитать документ: {error}",
    "not_a_load": "Это не похоже на rate confirmation — не нашёл номер загрузки и адреса.",
    "unsupported_file": "Отправьте PDF, фото или вставьте текст RC.",

    "conflicts_header": "⚠️ Противоречия в RC — уточните у брокера, прежде чем доверять значениям:",
    "lbl_pu_address": "Адрес погрузки",
    "lbl_del_address": "Адрес выгрузки",
    "lbl_pu_date": "Дата погрузки",
    "lbl_del_date": "Дата выгрузки",
    "lbl_phone": "Телефон",
    "lbl_directions": "🗺 Маршрут",
    "lbl_equipment": "Техника",
    "lbl_weight": "Вес",
    "lbl_rate": "Ставка",
    "lbl_miles": "Мили",
    "lbl_rpm": "Ставка за милю",
    "lbl_requirements": "⚠️ Дополнительные требования",
    "miles_unknown": "нет данных",

    "accept_prompt": "Водитель: нажмите, чтобы подтвердить загрузку #{load}. Отслеживание начнётся после этого.",
    "accept_button": "✅ Принять загрузку #{load}",
    "accepted_by": "✅ {who} принял загрузку #{load}.",
    "tracking_on": "📡 Отслеживание включено — обновления каждые {hours} ч.",
    "share_live_hint": "Водитель: нажмите 📎 → Геопозиция → <b>Транслировать геопозицию</b>.",
    "send_location_button": "📍 Отправить геопозицию",
    "location_received": "📍 Геопозиция получена, спасибо.",
    "location_keyboard_prompt": "Нажмите кнопку ниже, чтобы отправить геопозицию.",

    "upd_title": "Загрузка #{load} — {status}",
    "status_en_route": "В пути",
    "status_at_pickup": "📍 Вероятно на погрузке",
    "status_at_delivery": "✅ Вероятно на выгрузке",
    "upd_miles_left": "До выгрузки: {miles} миль",
    "upd_eta": "Прибытие: ~{eta} (примерно {hours} ч)",
    "upd_loc_age": "(геопозиция обновлена {mins} мин назад)",
    "upd_loc_stale": "⚠️ Геопозиции уже {mins} мин — возможно, трансляция выключена.",
    "upd_no_location": "Загрузка #{load}: геопозиция не получена — попросите водителя включить трансляцию.",
    "upd_driver_eta": "Прибытие (со слов водителя): ~{eta}",

    "cancel_done": "❌ Загрузка #{load} отменена. Отслеживание остановлено.",
    "cancel_none": "В этой группе нет активной загрузки.",
    "cancel_choose": "Выберите загрузку для отмены:",
    "cancel_no_loads": "Активных загрузок нет.",

    "pu_check_q": "Загрузка #{load}: время погрузки прошло. Загрузились?",
    "del_check_q": "Загрузка #{load}: время выгрузки прошло. Выгрузились?",
    "btn_picked": "✅ Загрузился",
    "btn_delivered": "✅ Выгрузился",
    "btn_not_yet": "❌ Ещё нет",
    "ask_bol": "Отправьте фото <b>BOL</b> для загрузки #{load}.",
    "ask_pod": "Отправьте фото <b>POD</b> для загрузки #{load}.",
    "doc_received": "✅ {kind} по загрузке #{load} получен. Передано диспетчеру.",
    "not_yet_ack": "Принято — спрошу позже. Сообщите диспетчеру, если есть проблема.",
    "delivered_done": "✅ Загрузка #{load} выгружена. Отслеживание остановлено.",

    "driver_eta_saved": "✅ Принято — считаю по вашему ETA {eta} для загрузки #{load}.",
    "dispatcher_eta_alert": "🔔 Изменение ETA — загрузка #{load} ({group})\nВодитель {who} сообщил ETA {eta}.\nБыло: {old}.",
    "dispatcher_doc": "📄 {kind} по загрузке #{load} из {group}.",
    "dispatcher_status": "🔔 Загрузка #{load} ({group}): водитель ответил «{answer}» на проверку {stop}.",

    "settings_title": "⚙️ Настройки",
    "settings_pick_group": "Выберите группу водителя:",
    "settings_for": "⚙️ Настройки для <b>{group}</b>",
    "settings_lang": "🌐 Язык: {value}",
    "settings_interval": "⏱ Интервал обновлений: {value} ч",
    "settings_rate": "💵 Ставка: {value}",
    "rate_shown": "показана",
    "rate_hidden": "скрыта",
    "settings_saved": "Сохранено.",
    "settings_no_groups": "Групп пока нет. Добавьте бота в группу и отправьте туда RC.",
    "btn_back": "‹ Назад",
    "settings_private_only": "Откройте настройки в личном чате со мной.",

    "paywall": "Бесплатные {free} извлечений закончились. /buy — кредиты или подписка, либо запросите доступ у админа.",
    "status_msg": "Осталось бесплатно: {free}\nКредиты: {credits}\nПодписка: {sub}",
    "sub_none": "нет",
    "sub_until": "активна до {date}",
    "buy_title": "Выберите план (оплата пока не подключена — свяжитесь с админом):",
    "buy_contact": "Платёжный шлюз не подключён. Напишите админу для активации.",
    "granted": "✅ Выдано.",
    "grant_usage": "Формат: /grant <telegram_id> credits <n>  |  /grant <telegram_id> sub <дней>",
    "admin_only": "Только для админа.",
    "group_only": "Используйте это в группе водителя.",
    "eta_not_accepted": "Загрузка #{load} ещё не принята — отслеживание начнётся после нажатия «Принять».",
    "no_load": "В этой группе нет загрузки.",
}

UZ = {
    "footer": (
        "⏰Kechikkan yuklash = $250 jarima❗️\n"
        "⏰Kechikkan tushirish = $250 jarima❗️\n"
        "📱Macro-point MAJBURIY / $250 jarima❗️\n"
        "📝BOL/POD/ yuk rasmlari/plomba rasmlari MAJBURIY, aks holda $250 jarima❗️\n"
        "🚨 Yangilik yo'q / $250 jarima❗️\n"
        "Ishimiz silliq ketishi uchun aloqangiz juda muhim❗️"
    ),
    "help": (
        "<b>RC Bot</b>\n\n"
        "Rate confirmation (PDF, rasm yoki matn) ni haydovchi guruhiga yuboring. "
        "Men uni o'qib, xarita havolalari va milyaga stavka bilan toza xulosa chiqaraman va haydovchi qabul qilishini kutaman. "
        "Shundan keyin uning joylashuvi asosida ETA yuborib turaman.\n\n"
        "<b>Haydovchi guruhida</b>\n"
        "/eta — hozirgi masofa va ETA\n"
        "/cancel_load — yukni bekor qilish\n"
        "/delivered — yukni yopish\n\n"
        "<b>Shaxsiy chatda</b>\n"
        "/settings — til, oraliq, stavka ko'rinishi (guruh bo'yicha)\n"
        "/cancel_load — istalgan yukni bekor qilish\n"
        "/status — limitingiz\n"
        "/buy — tariflar"
    ),
    "extracting": "RC o'qilmoqda…",
    "extract_failed": "Hujjatni o'qib bo'lmadi: {error}",
    "not_a_load": "Bu rate confirmation'ga o'xshamaydi — yuk raqami va manzillar topilmadi.",
    "unsupported_file": "PDF, rasm yuboring yoki RC matnini tashlang.",

    "conflicts_header": "⚠️ RC ichida ziddiyat bor — brokerdan aniqlang:",
    "lbl_pu_address": "PU Manzil",
    "lbl_del_address": "DEL Manzil",
    "lbl_pu_date": "PU Sana",
    "lbl_del_date": "DEL Sana",
    "lbl_phone": "Telefon",
    "lbl_directions": "🗺 Yo'nalish",
    "lbl_equipment": "Uskuna",
    "lbl_weight": "Og'irlik",
    "lbl_rate": "Stavka",
    "lbl_miles": "Milya",
    "lbl_rpm": "Milyaga stavka",
    "lbl_requirements": "⚠️ Qo'shimcha talablar",
    "miles_unknown": "ma'lumot yo'q",

    "accept_prompt": "Haydovchi: Load #{load}ni qabul qilganingizni tasdiqlash uchun bosing. Kuzatuv shundan keyin boshlanadi.",
    "accept_button": "✅ Load #{load}ni qabul qilish",
    "accepted_by": "✅ {who} Load #{load}ni qabul qildi.",
    "tracking_on": "📡 Kuzatuv yoqildi — har {hours} soatda yangilanadi.",
    "share_live_hint": "Haydovchi: 📎 → Location → <b>Share Live Location</b> tugmasini bosing.",
    "send_location_button": "📍 Joylashuvimni yuborish",
    "location_received": "📍 Joylashuv olindi, rahmat.",
    "location_keyboard_prompt": "Joylashuvni yuborish uchun quyidagi tugmani bosing.",

    "upd_title": "Load #{load} — {status}",
    "status_en_route": "Yo'lda",
    "status_at_pickup": "📍 Ehtimol yuklash manzilida",
    "status_at_delivery": "✅ Ehtimol tushirish manzilida",
    "upd_miles_left": "Tushirish manziligacha: {miles} mi",
    "upd_eta": "Yetib borish: ~{eta} (taxminan {hours} soat)",
    "upd_loc_age": "(joylashuv {mins} daqiqa oldin yangilandi)",
    "upd_loc_stale": "⚠️ Joylashuv {mins} daqiqa eski — haydovchi ulashishni to'xtatgan bo'lishi mumkin.",
    "upd_no_location": "Load #{load}: joylashuv hali kelmadi — haydovchidan ulashishni so'rang.",
    "upd_driver_eta": "Yetib borish (haydovchi aytgan): ~{eta}",

    "cancel_done": "❌ Load #{load} bekor qilindi. Kuzatuv to'xtatildi.",
    "cancel_none": "Bu guruhda faol yuk yo'q.",
    "cancel_choose": "Bekor qilinadigan yukni tanlang:",
    "cancel_no_loads": "Faol yuklar yo'q.",

    "pu_check_q": "Load #{load}: yuklash vaqti o'tdi. Yukni oldingizmi?",
    "del_check_q": "Load #{load}: tushirish vaqti o'tdi. Tushirdingizmi?",
    "btn_picked": "✅ Oldim",
    "btn_delivered": "✅ Tushirdim",
    "btn_not_yet": "❌ Hali yo'q",
    "ask_bol": "Load #{load} uchun <b>BOL</b> rasmini yuboring.",
    "ask_pod": "Load #{load} uchun <b>POD</b> rasmini yuboring.",
    "doc_received": "✅ Load #{load} uchun {kind} olindi. Dispetcherga yuborildi.",
    "not_yet_ack": "Tushunarli — keyinroq yana so'rayman. Muammo bo'lsa dispetcherga ayting.",
    "delivered_done": "✅ Load #{load} tushirildi deb belgilandi. Kuzatuv to'xtatildi.",

    "driver_eta_saved": "✅ Qabul qilindi — Load #{load} uchun sizning ETA {eta} ishlatiladi.",
    "dispatcher_eta_alert": "🔔 ETA o'zgardi — Load #{load} ({group})\nHaydovchi {who} ETA {eta} deb xabar berdi.\nAvvalgi hisob: {old}.",
    "dispatcher_doc": "📄 {group} dan Load #{load} uchun {kind}.",
    "dispatcher_status": "🔔 Load #{load} ({group}): haydovchi {stop} tekshiruviga «{answer}» deb javob berdi.",

    "settings_title": "⚙️ Sozlamalar",
    "settings_pick_group": "Sozlash uchun haydovchi guruhini tanlang:",
    "settings_for": "⚙️ <b>{group}</b> uchun sozlamalar",
    "settings_lang": "🌐 Til: {value}",
    "settings_interval": "⏱ Yangilanish oralig'i: {value} soat",
    "settings_rate": "💵 Stavka: {value}",
    "rate_shown": "ko'rsatiladi",
    "rate_hidden": "yashirilgan",
    "settings_saved": "Saqlandi.",
    "settings_no_groups": "Hali guruh yo'q. Botni guruhga qo'shing va u yerga RC yuboring.",
    "btn_back": "‹ Orqaga",
    "settings_private_only": "Sozlamalarni men bilan shaxsiy chatda oching.",

    "paywall": "{free} ta bepul ishlatish tugadi. /buy orqali kredit yoki obuna oling, yoki admindan so'rang.",
    "status_msg": "Bepul qoldi: {free}\nKreditlar: {credits}\nObuna: {sub}",
    "sub_none": "yo'q",
    "sub_until": "{date} gacha faol",
    "buy_title": "Tarifni tanlang (to'lov hali ulanmagan — admin bilan bog'laning):",
    "buy_contact": "To'lov tizimi hali ulanmagan. Kredit qo'shish uchun adminga yozing.",
    "granted": "✅ Berildi.",
    "grant_usage": "Format: /grant <telegram_id> credits <n>  |  /grant <telegram_id> sub <kun>",
    "admin_only": "Faqat admin uchun.",
    "group_only": "Buni haydovchi guruhida ishlating.",
    "eta_not_accepted": "Load #{load} hali qabul qilinmagan — kuzatuv Accept bosilgandan keyin boshlanadi.",
    "no_load": "Bu guruhda yuk ro'yxatdan o'tmagan.",
}

TRANSLATIONS = {"en": EN, "ru": RU, "uz": UZ}


def t(lang: str, key: str, **kwargs) -> str:
    """Look up ``key``, falling back to English, then to the key itself."""
    table = TRANSLATIONS.get(lang, EN)
    template = table.get(key) or EN.get(key) or key
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template
