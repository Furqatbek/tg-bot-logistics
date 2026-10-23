"""RC extraction via the Claude API.

A rate confirmation can arrive as a PDF, a phone photo, or pasted text, and
every broker lays theirs out differently — so this hands the raw document to
the model with a strict JSON schema rather than trying to regex it.
"""

import base64
import json
import logging

import anthropic

import config

log = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


class ExtractionError(Exception):
    """Raised when the document could not be turned into structured data."""


_STOP_FIELDS = {
    "company": {"type": ["string", "null"]},
    "street": {"type": ["string", "null"]},
    "city": {"type": ["string", "null"]},
    "state": {"type": ["string", "null"]},
    "zip": {"type": ["string", "null"]},
    "phone": {"type": ["string", "null"]},
    "date": {"type": ["string", "null"], "description": "MM/DD/YYYY"},
    "time_text": {
        "type": ["string", "null"],
        "description": "Appointment or FCFS window in 12h format, e.g. '7:00 AM' or 'FCFS 7:00 AM - 4:00 PM'",
    },
    "datetime_iso": {
        "type": ["string", "null"],
        "description": "The appointment start as ISO 8601 local time, e.g. 2026-07-30T07:00. "
                       "For an FCFS window use the window's end.",
    },
}

_STOP_SCHEMA = {
    "type": "object",
    "properties": _STOP_FIELDS,
    "required": list(_STOP_FIELDS),
    "additionalProperties": False,
}

_PROPS = {
    "is_rate_confirmation": {
        "type": "boolean",
        "description": "False if the document is not a load/rate confirmation at all.",
    },
    "load_id": {"type": ["string", "null"]},
    "broker": {"type": ["string", "null"]},
    "pu_number": {"type": ["string", "null"]},
    "po_number": {"type": ["string", "null"]},
    "bol_number": {"type": ["string", "null"]},
    "ref_number": {"type": ["string", "null"]},
    "pickup": _STOP_SCHEMA,
    "delivery": _STOP_SCHEMA,
    "commodity": {"type": ["string", "null"]},
    "pieces": {"type": ["string", "null"], "description": "Piece/unit count as written"},
    "dimensions": {"type": ["string", "null"]},
    "equipment": {"type": ["string", "null"], "description": "Flatbed, Van, Reefer, Stepdeck..."},
    "weight_lbs": {"type": ["string", "null"]},
    "rate_usd": {"type": ["number", "null"], "description": "Total linehaul rate in dollars"},
    "stated_miles": {"type": ["number", "null"], "description": "Mileage printed on the RC, if any"},
    "requirements": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Load-specific instructions: tarping, photos, check calls, seals, "
                       "tracking apps. Omit the broker's boilerplate fine schedule.",
    },
    "conflicts": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Plain-English notes where the document contradicts itself, e.g. "
                       "'Pickup date differs: header says 07/30, stops table says 07/29.'",
    },
}

RC_SCHEMA = {
    "type": "object",
    "properties": _PROPS,
    "required": list(_PROPS),
    "additionalProperties": False,
}

SYSTEM = """You extract structured data from freight rate confirmations (RCs) for a trucking dispatch bot.

Rules:
- Transcribe what the document says. Never invent a value: use null when a field is absent.
- Convert every time to 12-hour format with AM/PM. Keep FCFS windows as a range.
- datetime_iso drives automated check-ins, so it must be the real appointment moment in the
  stop's local time. For an FCFS window, use the end of the window.
- Addresses: split company, street, city, state, ZIP. If a stop has both a company name and a
  yard/facility name, join them with " / " in company.
- rate_usd is the total linehaul rate paid to the carrier, as a number without currency symbols.
- requirements: only load-specific instructions (tarping, photo proof, check calls, seal rules,
  required tracking apps). Skip the standard fine schedule the dispatcher appends to every load.
- conflicts: RCs often disagree with themselves — a header date against the stops table, a rate
  stated twice, two different weights. Report each disagreement, naming both values and where
  each came from. Do not silently pick one. If nothing conflicts, return an empty array.
"""


def _content_blocks(payload: bytes | str, mime: str | None) -> list[dict]:
    if isinstance(payload, str):
        return [{"type": "text", "text": f"Rate confirmation:\n\n{payload}"}]

    data = base64.standard_b64encode(payload).decode("ascii")
    if mime == "application/pdf":
        block = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
    else:
        block = {
            "type": "image",
            "source": {"type": "base64", "media_type": mime or "image/jpeg", "data": data},
        }
    return [block, {"type": "text", "text": "Extract this rate confirmation."}]


async def extract(payload: bytes | str, mime: str | None = None) -> dict:
    """Return the structured RC. Raises ExtractionError on failure."""
    messages = [{"role": "user", "content": _content_blocks(payload, mime)}]
    output_config = {
        "effort": config.EXTRACTION_EFFORT,
        "format": {"type": "json_schema", "schema": RC_SCHEMA},
    }

    try:
        resp = await client().beta.messages.create(
            model=config.MODEL,
            max_tokens=8000,
            system=SYSTEM,
            messages=messages,
            output_config=output_config,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except (TypeError, anthropic.BadRequestError) as exc:
        # Older SDK or a model/platform that doesn't take server-side fallbacks.
        log.info("retrying extraction without server-side fallback: %s", exc)
        try:
            resp = await client().messages.create(
                model=config.MODEL,
                max_tokens=8000,
                system=SYSTEM,
                messages=messages,
                output_config=output_config,
            )
        except anthropic.APIError as inner:
            raise ExtractionError(str(inner)) from inner
    except anthropic.APIError as exc:
        raise ExtractionError(str(exc)) from exc

    if resp.stop_reason == "refusal":
        raise ExtractionError("the model declined to process this document")

    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        raise ExtractionError("empty response from the model")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"malformed JSON from the model: {exc}") from exc

    if not data.get("is_rate_confirmation"):
        raise ExtractionError("not a rate confirmation")

    return data


def full_address(stop: dict | None) -> str:
    """One-line address for geocoding and map links."""
    if not stop:
        return ""
    parts = [stop.get("street"), stop.get("city"), stop.get("state"), stop.get("zip")]
    return ", ".join(p.strip() for p in parts if p and p.strip())
