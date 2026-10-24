# RC Bot — rate confirmation extractor + load tracker

A Telegram bot for a trucking dispatch operation.

Drop a rate confirmation into a driver's group chat — as a PDF, a phone photo,
or pasted text — and the bot reads it, posts it back in your standard template
with map links and rate-per-mile, waits for the driver to accept, then tracks
the load to delivery.

---

## What happens, start to finish

1. **Dispatcher sends the RC** into the driver's standing group.
2. **Bot extracts it** with Claude: Load ID, PU#, PO#, BOL#, Ref#, both
   addresses, appointment or FCFS times (converted to 12-hour), commodity,
   dimensions, equipment, weight, rate, and any load-specific requirements.
3. **Bot posts a clean summary** — a Google Maps directions link under each
   address, real driving distance PU→DEL, `RPM = rate ÷ miles`, and the
   standard fine-rules footer.
4. **Conflicts are flagged, not guessed.** RCs routinely disagree with
   themselves (header says pickup 07/30, the stops table says 07/29). The bot
   prints both values at the top of the message and leaves the call to a human.
5. **Driver taps `✅ Accept Load #…`.** Nothing is pinned and no tracking runs
   until they do. On accept the summary is pinned, tracking starts, and the bot
   asks for a location.
6. **Scheduled updates** (default every 2h) post miles remaining, ETA, and a
   proximity status — *likely at pickup* / *en route* / *likely at delivery* —
   plus a warning when the GPS ping has gone stale.
7. **Window checks.** When the pickup time passes the bot asks "did you pick
   up?"; on yes it requests the **BOL** photo and forwards it to dispatch. Same
   at delivery for the **POD**.
8. **Driver-reported ETA wins.** If the driver types `ETA 9pm` in the group —
   they're sleeping, the truck broke down — the bot uses that instead of the
   routed estimate and alerts dispatch that the ETA changed.
9. **`/cancel_load`** stops everything; **`/delivered`** closes the load out.

Each driver's group is tracked independently by its chat ID. Ali's group can be
Uzbek with the rate hidden on a 2h interval while Odil's is English with the
rate shown on 4h, with no overlap.

---

## Running with Docker (recommended)

One command, no Python install, and the bot restarts itself if it crashes or
the machine reboots.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(Windows/macOS) or Docker Engine (Linux). Nothing else — not even Python.

```bash
git clone --branch claude/epic-darwin-c4gwrm https://github.com/Furqatbek/tg-bot-logistics.git rc_bot
cd rc_bot
cp .env.example .env          # copy .env.example .env   on Windows
```

Edit `.env` and fill in `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY` and
`ADMIN_TELEGRAM_ID` (see the table above). Then:

```bash
docker compose up -d --build
```

That's it — the bot is live.

| Task | Command |
|---|---|
| Follow the logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Update to the latest code | `git pull && docker compose up -d --build` |
| Run the test suite | `docker compose run --rm tests` |
| Open a shell inside | `docker compose exec bot sh` |

**The database lives in a named volume** (`bot-data`), not in the image, so
active loads, group settings and credits survive rebuilds and updates. To back
it up:

```bash
docker run --rm -v tg-bot-logistics_bot-data:/data -v "$PWD:/backup"   busybox cp /data/bot.db /backup/bot-backup.db
```

`docker compose down -v` deletes that volume along with everything in it — use
plain `down` unless you mean to wipe state.

**If the container keeps restarting**, run `docker compose logs` and read the
last few lines. The two usual causes are a missing value in `.env` (it names
the setting) and a rejected bot token (it says so explicitly) — `restart:
unless-stopped` will retry a bad token forever, so check the log rather than
waiting.

Notes: the image runs as a non-root user, logs are capped at 3 × 10 MB so they
can't fill the disk, and the `tests` service is behind a profile so
`up` never starts it.


---

## Setup (without Docker)

### 1. Create the bot

In Telegram, message `@BotFather`:

- `/newbot` → pick a name and a username ending in `bot` → copy the token.
- `/setprivacy` → select your bot → **Disable**.
  **This one is required.** With privacy enabled a bot only sees commands, so
  it would never receive the driver's location shares in a group.

### 2. Install

Python **3.11 or newer**.


```bash
git clone https://github.com/Furqatbek/tg-bot-logistics.git
cd tg-bot-logistics
python -m venv venv
venv\Scripts\activate          # Windows;  source venv/bin/activate  on macOS/Linux
pip install -r requirements.txt
```

### 3. Configure

```bash
copy .env.example .env         # cp on macOS/Linux
```

Fill in:

| Setting | Where it comes from |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `@BotFather` |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `ADMIN_TELEGRAM_ID` | message `@userinfobot` — it replies with your numeric ID |

Everything else has a working default.

### 4. Run

```bash
python bot.py
```

Leave the window open. To keep it running without one, use Task Scheduler →
Create Task → trigger **At startup** → action `venv\Scripts\python.exe bot.py`
with **Start in** set to the project folder, and tick *Run whether user is
logged on or not*.

### 5. Per group, once

Add the bot to each driver's group and **make it an admin with permission to
pin messages** — otherwise it can extract and post but not pin.

---

## Commands

**In a driver's group**

| Command | Does |
|---|---|
| `/eta` | distance and ETA right now |
| `/cancel_load` | cancel the active load, unpin, stop updates |
| `/delivered` | close the load out |
| `/rc` | force-extract a pasted RC the bot skipped (or reply to it with `/rc`) |

**In a private chat with the bot**

| Command | Does |
|---|---|
| `/settings` | per-group language, interval, rate visibility |
| `/cancel_load` | pick any active load across all groups and cancel it |
| `/status` | your trial / credits / subscription |
| `/buy` | plans |
| `/grant <id> credits <n>` · `/grant <id> sub <days>` | admin: activate someone manually |

Settings deliberately live only in the private chat, so drivers never see a
config menu in their group.

---

## Costs

Running the bot is free. The only metered cost is the Claude API call per RC.

The default model is `claude-opus-5-5`. For a document-extraction job like this
`claude-sonnet-5-5` is usually sufficient and roughly half the price per token —
switch with `ANTHROPIC_MODEL` in `.env`. `EXTRACTION_EFFORT` (`low`/`medium`/
`high`) trades thoroughness against spend; `medium` is the default.

An RC is a small request — a page or two of image plus a short JSON response —
so cost per RC is in the cents. Check current per-token rates at
[claude.com/pricing](https://claude.com/pricing) and measure your own first
week rather than trusting an estimate.

Geocoding and routing cost nothing: the bot uses the US Census geocoder, then
Photon, then Nominatim as fallbacks, and OSRM for driving distance.

---

## Architecture

| File | Role |
|---|---|
| `bot.py` | handlers, scheduled jobs, the accept → track → document lifecycle |
| `extraction.py` | the Claude call, JSON schema, and extraction prompt |
| `formatting.py` | the posted summary and ETA updates (HTML-escaped) |
| `geo.py` | geocoding chain, OSRM routing, map links |
| `tracking.py` | per-group load, settings, last GPS ping, geocode cache |
| `db.py` | trial / credits / subscriptions |
| `i18n.py` | EN / RU / UZ strings |
| `config.py` | env-backed settings |

State lives in one SQLite file (`bot.db` by default). Tracking jobs are
re-armed on startup, so a restart doesn't lose an in-flight load.

### Tests

```bash
venv/bin/python -m pytest tests/ -q
```

46 tests, no network and no API key needed — Telegram and Claude are stubbed.
They cover the full lifecycle (RC → summary → accept → update → window check →
BOL → cancel), both sample RCs from the design notes, HTML escaping of document
content, the paywall, per-group isolation, and job restoration after restart.

---

## Known limitations

These are design ceilings, not bugs — worth knowing before you promise any of
it to a customer.

- **Telegram cannot pull a location.** A bot only receives one when the user
  pushes it. The one-tap button sends a *single* fix; continuous tracking needs
  the driver to turn on Live Location manually, and a share lasts at most ~8
  hours. "Register once, tracks forever" is not possible through Telegram
  alone. The real fix is an ELD integration — Motive and Samsara both have
  self-serve APIs for fleet admins, and TruckerCloud aggregates 50+ providers
  behind one API if you need to support whatever ELD a carrier already runs.
  Macropoint is broker-facing and can't be integrated directly by a carrier; it
  rides on top of your ELD.
- **"Status" is proximity inference**, not a real event. The bot knows where
  the truck is, never what's happening with the freight. The pickup/delivery
  window checks exist to close that gap by asking.
- **One active load per group.** A new RC into the same group replaces the
  previous load's tracking. Two simultaneous loads per driver would need
  updates tagged by load ID.
- **Single-tenant settings.** `/settings` and remote `/cancel_load` are
  restricted to `ADMIN_TELEGRAM_ID` and list *every* group the bot knows.
  The billing tables are per-user, but group ownership is not modeled — before
  selling this to a second dispatcher, add an owner column to `settings` and
  scope those two commands by it.
- **Payments are not wired up.** Trial, credits, subscriptions and `/grant` all
  work; `db.build_payment_link()` is a clearly-marked stub. Click and Payme
  both need a merchant account *and* a public HTTPS callback URL, which means a
  VPS with a domain and SSL — not a home PC behind Tailscale.
- **A document sent while the bot is waiting for a BOL/POD is treated as that
  document**, not as a new RC.
