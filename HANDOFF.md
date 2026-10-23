# RC Bot — Project Handoff / Wrap-Up

**Source:** shared Claude chat (owner: *Jalol*), summarized 2026-10-23.

**Status update (same day):** the 7 files from that chat were lost, so the project was
**rebuilt from scratch in this repo** — see `README.md`. This document is kept as the record
of what was decided and why. The design below is what got built, with two differences noted
inline: the geocoder is now a fallback chain, and the previously unfinished BOL/POD and
driver-ETA features are implemented and tested.

---

## 🔴 Do these two things before anything else

**1. Revoke the Telegram bot token.**
The token `8384992812:AAGJ...` was pasted in plaintext into a chat that was then **shared via public link**.
Treat it as compromised. In Telegram: `@BotFather` → `/revoke` → select the bot → get a new token.
Put the new one only in `.env`, never in a message.

**2. ~~Download the 7 code files out of that chat.~~ Done differently.**
The files were lost before they could be recovered, so the project was rewritten from the
design recorded here. The code now lives in this repo with a test suite. Nothing further is
needed from Jalol's chat.

---

## What the bot does

A Telegram bot for a trucking dispatch operation. Dispatcher forwards a **rate confirmation (RC)**
into a driver's group chat; the bot reads it, reformats it into the company's standard template,
and then tracks the load to delivery.

**Pipeline:**

1. Dispatcher sends an RC — PDF, photo, or plain text — into the driver's standing Telegram group.
2. Claude (vision) extracts structured fields: Load ID, PU#, PO#, BOL#, Ref#, PU/DEL addresses,
   appointment or FCFS times (converted to 12h AM/PM), commodity, weight, dimensions,
   equipment, rate, special requirements.
3. Bot computes real driving distance PU→DEL via OSRM (free, no API key) → **RPM = rate ÷ miles**.
4. Bot posts a formatted summary with a **Google Maps directions link under each address**,
   plus the static fine-rules footer (late PU/DEL $250, Macropoint required, BOL/POD photos, etc.).
5. **Conflict detection** — if the RC disagrees with itself (e.g. header says PU 07/30 but the
   STOPS table says 07/29), the bot posts a warning block at the top rather than silently guessing.
   This was a deliberate decision: surface it, let a human resolve it.
6. An **"✅ Accept Load #X"** button sits under the summary. Nothing is pinned and no tracking
   starts until the driver taps it.
7. On accept: summary gets pinned, tracking starts, bot requests a one-time location and prompts
   the driver to turn on Live Location.
8. Every N hours (configurable): bot posts miles remaining, ETA, and a proximity-inferred status
   (*near pickup* / *en route* / *near delivery*), with a staleness warning if the last GPS ping
   is >90 min old.
9. `/cancel_load` — works in the group, or remotely from your private chat with the bot
   (lists all active loads across all driver groups).

**Multi-driver:** each driver has one standing group; the group's chat ID *is* the driver identifier.
Groups are fully independent — Ali's group can be Uzbek + rate hidden + 2h updates while Odil's is
English + rate shown + 4h. One active load per group (a new RC replaces the old one's tracking).

---

## Files

| File | Purpose |
|---|---|
| `bot.py` | Main bot — extraction, formatting, paywall, tracking, settings, accept/cancel flows |
| `db.py` | SQLite: free trial counting, credits, subscriptions |
| `tracking.py` | Group ↔ load ↔ live location ↔ per-group settings |
| `i18n.py` | EN / RU / UZ translations |
| `requirements.txt` | Dependencies (incl. job-queue support) |
| `.env` | Bot token, Anthropic API key, `ADMIN_TELEGRAM_ID` — **never share this file** |
| `README.md` | Full setup, BotFather steps, settings walkthrough, monetization, limitations |

---

## Settings (private DM with the bot only)

Deliberately kept out of group chats so drivers never see a config menu.
Message the bot privately → `/settings` → pick a driver group → set:

- **Language** — EN / RU / UZ
- **Update interval** — 1–24h
- **Rate visibility** — shown/hidden. Hidden still shows PU→DEL miles, just no `$` or RPM
  (company drivers don't need to see the rate).

---

## Monetization (built, gateways stubbed)

- **5 free RC extractions** per user, then paywalled
- `/status` — trial / credits / subscription balance
- `/buy` — plan buttons; **prices are placeholders**, set real UZS numbers in `PRICING` at the top of `bot.py`
- `/grant <telegram_id> credits <n> | sub <days>` — admin command to activate someone manually, no gateway needed
- `build_payment_link()` is a clearly-marked stub where Click/Payme plugs in later

**Decision made:** full Click/Payme API integration deferred (you have a registered business, but
integration requires a public HTTPS webhook endpoint with SSL — meaning a VPS + domain, not the home PC).
Manual `/grant` is the interim.

---

## Running it free

Runs free on the Windows PC (already has AnyDesk + Tailscale, sleep disabled):
Python 3.11+ → `python -m venv venv` → `venv\Scripts\activate` → `pip install -r requirements.txt`
→ fill `.env` → `python bot.py`. Task Scheduler ("At startup", "Run whether user is logged on or not")
keeps it alive without a window.

**Only real cost is the Claude API**, usage-based not flat-rate. As discussed in that chat:
roughly **$0.01–0.015 per RC** (~2–4k input tokens + ~300–500 output), so ~$10–15 per 1,000 RCs.
New Anthropic accounts get $5 free credit. *Verify current pricing before relying on these numbers.*

**One-time setup you must not skip:**
- `@BotFather` → `/setprivacy` → **Disable** (otherwise the bot can't see location shares in groups)
- Make the bot an **admin with pin permission** in each driver's group

---

## ✅ Was unfinished in the chat — now built and tested

The original conversation cut off mid-build on the last feature. Both parts are now
implemented and covered by tests (`tests/test_flow.py`):

- **Deadline status checks** — when the pickup window passes, bot asks the driver in-group
  "did you pick up?" and, if yes, requests the **BOL** photo. Same pattern at delivery for the **POD**.
  (Required DB columns and datetime fields were added; handlers were being wired.)
- **Driver ETA override** — if the driver types an ETA in the group (sleeping, truck broke down),
  the bot's calculations defer to the driver's ETA instead of the GPS-derived one, **and notify
  the dispatcher/updater that the ETA changed.**

Both are exercised end to end in the test suite, including the case where a pasted RC
contains the words "provide ETA at pickup" and must *not* be read as a driver ETA.

---

## Known limitations (design ceilings, not bugs)

- **Telegram cannot pull a location.** A bot only receives location when the user pushes it.
  One-tap buttons give a *single* location fix; continuous tracking requires the driver to manually
  turn on Live Location, which maxes out around 8h per session. "Register once, tracks forever"
  is impossible via Telegram alone.
- **"Status" is only proximity inference** from GPS — where the truck is, never what's happening
  with the freight. No real "loaded" / "at dock" / "seal broken" events.
- **No delivered event.** A finished load just stops mattering when the next RC replaces it.
- **One active load per group.** Two simultaneous loads per driver would need a redesign
  (tagging updates by load ID within one group).

---

## Open decisions / follow-ups

**Offered but never answered — pick these up:**
1. `/mark_delivered` command, to close a load out cleanly instead of it fading away.
2. Stale-location reminder — bot nudges the driver in-group to re-share when the GPS feed goes cold.
3. Full untrimmed sample output for both language/rate scenarios.

**Bigger strategic decision — real GPS:**
The goal stated was "work for everyone, every ELD, every company." Two paths surfaced:
- **Motive API** — self-serve and instant (Fleet Dashboard → Admin → Developers → Request API Key).
  Works today *if* the trucks run Motive. Samsara has a similar self-serve portal.
- **TruckerCloud / Open Visibility Network** — an aggregator with connections to 50+ ELD providers
  behind a single API. This is the genuine "every ELD" answer. Paid B2B, per-truck or per-carrier;
  **pricing was never looked up** — that's an open action item. Each carrier still does a one-time connect.
- **Macropoint is not directly integrable by you** — it's broker-facing. Your ELD reports *into*
  Macropoint via a native toggle when a broker requests tracking. Don't plan an integration around it.

Telegram Live Location is the free stand-in until one of the above lands. The location source can be
swapped without touching group binding, scheduling, or update formatting.

**Also outstanding:**
- Set real UZS pricing in `PRICING`
- Get an Anthropic API key + credit (nothing has been tested against a live API yet — only logic simulations)
- Decide Click vs Payme, then provision VPS + domain + Let's Encrypt for the webhook
- Extraction accuracy still has **never been tested against a real API call** — this needs an
  API key with credit. Everything else is tested: 46 tests cover the full lifecycle with
  Claude and Telegram stubbed, and geocoding/routing were verified live (the Jake Brake load
  routes to 118.5 mi / $8.02 RPM, not the ~128 mi / $7.42 estimated in the chat)
