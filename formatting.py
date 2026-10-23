"""Rendering: the posted RC summary and the periodic ETA updates.

Everything that reaches Telegram goes through ``e()`` — RC text is arbitrary
document content and would otherwise break HTML parsing.
"""

from datetime import datetime
from html import escape

import extraction
import geo
from i18n import t

SEP = "========================="


def e(value) -> str:
    return escape(str(value), quote=False)


def fmt_12h(dt: datetime) -> str:
    """12-hour clock without a leading zero, portable across platforms."""
    return dt.strftime("%I:%M %p").lstrip("0")


def _stop_lines(stop: dict, label: str, date_label: str, lang: str) -> list[str]:
    lines = [f"<b>{label}:</b>"]
    if stop.get("company"):
        lines.append(e(stop["company"]))

    street = ", ".join(
        e(p) for p in (stop.get("street"), stop.get("city"), stop.get("state"), stop.get("zip")) if p
    )
    if street:
        lines.append(street)
    if stop.get("phone"):
        lines.append(f"{t(lang, 'lbl_phone')}: {e(stop['phone'])}")

    when = " ".join(e(p) for p in (stop.get("date"), stop.get("time_text")) if p)
    if when:
        lines.append(f"<b>{date_label}:</b> {when}")

    address = extraction.full_address(stop)
    if address:
        lines.append(f'<a href="{e(geo.maps_link(address))}">{t(lang, "lbl_directions")}</a>')
    return lines


def format_summary(data: dict, lang: str, show_rate: bool, miles: float | None) -> str:
    """The clean, template-shaped message posted into the driver's group."""
    out: list[str] = []

    header = f"<b>Load # {e(data.get('load_id') or '—')}</b>"
    if data.get("broker"):
        header += f"\n{e(data['broker'])}"
    out.append(header)

    refs = [
        (f"PU# {e(data['pu_number'])}" if data.get("pu_number") else None),
        (f"PO# {e(data['po_number'])}" if data.get("po_number") else None),
        (f"BOL# {e(data['bol_number'])}" if data.get("bol_number") else None),
        (f"Ref# {e(data['ref_number'])}" if data.get("ref_number") else None),
    ]
    refs = [r for r in refs if r]
    if refs:
        out.append("   ".join(refs))

    conflicts = data.get("conflicts") or []
    if conflicts:
        block = [f"<b>{t(lang, 'conflicts_header')}</b>"]
        block += [f"• {e(c)}" for c in conflicts]
        out.append("\n".join(block))

    out.append(SEP)
    out.append("\n".join(_stop_lines(
        data.get("pickup") or {}, t(lang, "lbl_pu_address"), t(lang, "lbl_pu_date"), lang)))

    out.append(SEP)
    out.append("\n".join(_stop_lines(
        data.get("delivery") or {}, t(lang, "lbl_del_address"), t(lang, "lbl_del_date"), lang)))

    out.append(SEP)

    freight = [
        " ".join(e(p) for p in (data.get("commodity"), data.get("dimensions")) if p),
        e(data["pieces"]) if data.get("pieces") else "",
    ]
    freight_line = ", ".join(p for p in freight if p)
    if freight_line:
        out.append(freight_line)

    specs = []
    if data.get("equipment"):
        specs.append(f"{t(lang, 'lbl_equipment')}: {e(data['equipment'])}")
    if data.get("weight_lbs"):
        specs.append(f"{t(lang, 'lbl_weight')}: {e(data['weight_lbs'])}")
    if specs:
        out.append("   ".join(specs))

    out.append(_money_line(data, lang, show_rate, miles))

    requirements = data.get("requirements") or []
    if requirements:
        block = [f"<b>{t(lang, 'lbl_requirements')}:</b>"]
        block += [f"• {e(r)}" for r in requirements]
        out.append("\n".join(block))

    out.append(SEP)
    out.append(t(lang, "footer"))

    return "\n\n".join(part for part in out if part)


def _money_line(data: dict, lang: str, show_rate: bool, miles: float | None) -> str:
    """Rate/RPM when visible; miles alone when the group hides the rate."""
    rate = data.get("rate_usd")
    miles_txt = f"{miles:,.0f} mi" if miles else t(lang, "miles_unknown")

    if not show_rate:
        return f"{t(lang, 'lbl_miles')}: {miles_txt}"

    parts = []
    if rate:
        parts.append(f"<b>{t(lang, 'lbl_rate')}: ${rate:,.0f}</b>")
    parts.append(f"{t(lang, 'lbl_miles')}: {miles_txt}")
    if rate and miles:
        parts.append(f"{t(lang, 'lbl_rpm')}: ${rate / miles:,.2f}/mi")
    return "   ".join(parts)


def format_eta_update(
    load: dict,
    lang: str,
    status_key: str,
    miles: float | None,
    hours: float | None,
    eta: datetime | None,
    loc_age_min: int | None,
    stale: bool,
    driver_eta: datetime | None,
) -> str:
    """One scheduled progress update."""
    lines = [
        f"<b>{t(lang, 'upd_title', load=e(load.get('load_id') or '—'), status=t(lang, status_key))}</b>"
    ]

    if miles is not None:
        lines.append(t(lang, "upd_miles_left", miles=f"{miles:,.0f}"))

    # A driver-reported ETA beats the routing estimate — they know about the
    # breakdown or the sleep stop that the map does not.
    if driver_eta:
        lines.append(t(lang, "upd_driver_eta", eta=fmt_12h(driver_eta)))
    elif eta and hours is not None:
        lines.append(t(lang, "upd_eta", eta=fmt_12h(eta), hours=f"{hours:.1f}"))

    if loc_age_min is not None:
        key = "upd_loc_stale" if stale else "upd_loc_age"
        lines.append(t(lang, key, mins=loc_age_min))

    return "\n".join(lines)
