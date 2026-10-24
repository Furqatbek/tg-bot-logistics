#!/usr/bin/env python3
"""Run one RC through extraction and print what the bot would post.

Lets you verify the expensive part — the Claude call, geocoding, routing and
the rendered message — without a Telegram group, a driver, or a bot token.

    python try_extract.py rc.pdf
    python try_extract.py rc.pdf --lang uz --hide-rate
    python try_extract.py --text "Load # 35840 ..."
    python try_extract.py --dry-run          # sample data, costs nothing

Only TELEGRAM_BOT_TOKEN is unnecessary here; ANTHROPIC_API_KEY must be set
unless you pass --dry-run.
"""

import argparse
import asyncio
import json
import mimetypes
import sys
from pathlib import Path

import config
import extraction
import formatting
import geo
import tracking

SAMPLE = {
    "is_rate_confirmation": True, "load_id": "35840",
    "broker": "Jake Brake Logistics", "pu_number": "41767",
    "po_number": None, "bol_number": None, "ref_number": "GIO 7/28",
    "pickup": {"company": "INV-KIEWIT POWER CONSTRUC #33",
               "street": "33 CADY HILL BLVD", "city": "Saratoga Springs",
               "state": "NY", "zip": "12866", "phone": "838-250-8924",
               "date": "07/30/2026", "time_text": "7:00 AM",
               "datetime_iso": "2026-07-30T07:00"},
    "delivery": {"company": "SUPREME INDUSTRIES INC / SUPREME YARD",
                 "street": "216 LOWER BOGUE ROAD", "city": "Harwinton",
                 "state": "CT", "zip": "06791", "phone": "860-348-7789",
                 "date": "07/30/2026", "time_text": "FCFS 7:00 AM - 4:00 PM",
                 "datetime_iso": "2026-07-30T16:00"},
    "commodity": 'HARDWOOD-MIXED DENSE USED 8"', "pieces": "20 PCS",
    "dimensions": "4X16/SOLID", "equipment": "Flatbed", "weight_lbs": "48000 lbs",
    "rate_usd": 950.0, "stated_miles": None,
    "requirements": ["Must call ahead & provide ETA at pickup", "No tarp required"],
    "conflicts": [],
}


async def run(args: argparse.Namespace) -> int:
    tracking.init()

    if args.dry_run:
        print("— dry run: built-in sample, no API call —\n")
        data = SAMPLE
    else:
        if not config.ANTHROPIC_API_KEY:
            print("ANTHROPIC_API_KEY is not set (put it in .env).", file=sys.stderr)
            return 2
        if args.text:
            payload, mime = args.text, None
        else:
            path = Path(args.file)
            if not path.is_file():
                print(f"No such file: {path}", file=sys.stderr)
                return 2
            payload = path.read_bytes()
            mime = mimetypes.guess_type(path.name)[0] or "application/pdf"
            print(f"Sending {path.name} ({len(payload):,} bytes, {mime}) "
                  f"to {config.MODEL}…\n")
        try:
            data = await extraction.extract(payload, mime)
        except extraction.ExtractionError as exc:
            print(f"Extraction failed: {exc}", file=sys.stderr)
            return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print()

    pu = extraction.full_address(data.get("pickup"))
    dl = extraction.full_address(data.get("delivery"))
    print(f"Geocoding:\n  PU  {pu or '(none)'}\n  DEL {dl or '(none)'}")

    a = await geo.geocode(pu) if pu else None
    b = await geo.geocode(dl) if dl else None
    print(f"  -> {a}\n  -> {b}")

    miles = None
    if a and b:
        leg = await geo.route(a, b)
        if leg:
            miles = leg["miles"]
            print(f"Routing: {miles:,.1f} mi, {leg['hours']:.2f} h driving")
        else:
            print("Routing: FAILED (OSRM unreachable)")
    else:
        print("Routing: skipped, an address did not geocode")
        if data.get("stated_miles"):
            miles = float(data["stated_miles"])
            print(f"  falling back to the mileage printed on the RC: {miles}")

    if data.get("conflicts"):
        print(f"\nConflicts found: {len(data['conflicts'])}")

    print("\n" + "=" * 60)
    print("What the bot would post:")
    print("=" * 60 + "\n")
    print(formatting.format_summary(data, args.lang, not args.hide_rate, miles))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("file", nargs="?", help="PDF or image of a rate confirmation")
    src.add_argument("--text", help="RC as plain text instead of a file")
    src.add_argument("--dry-run", action="store_true",
                     help="render built-in sample data, no API call")
    p.add_argument("--lang", default="en", choices=("en", "ru", "uz"))
    p.add_argument("--hide-rate", action="store_true",
                   help="render as a group with the rate hidden")
    p.add_argument("--json", action="store_true", help="also dump the raw extraction")
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
