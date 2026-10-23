"""Geocoding, driving distance, and map links.

Uses free public services: Nominatim for address -> coordinates and OSRM for
driving distance/duration. Neither needs an API key, but both are shared
community servers — point OSRM_URL / NOMINATIM_URL at your own instances if
the volume grows.
"""

import asyncio
import logging
from urllib.parse import quote_plus

import httpx2 as httpx

import config
import tracking

log = logging.getLogger(__name__)

METERS_PER_MILE = 1609.344

# Nominatim's usage policy allows at most one request per second.
_nominatim_lock = asyncio.Lock()

_USER_AGENT = f"rc-logistics-bot/1.0 ({config.GEOCODER_CONTACT})"


def maps_link(address: str) -> str:
    """Google Maps directions link to an address, routed from wherever the driver is."""
    return (
        "https://www.google.com/maps/dir/?api=1&destination="
        + quote_plus(address)
        + "&travelmode=driving"
    )


async def _geocode_census(client: "httpx.AsyncClient", address: str):
    """US Census geocoder: free, no key, exact on US street addresses."""
    resp = await client.get(
        f"{config.CENSUS_URL}/geocoder/locations/onelineaddress",
        params={"address": address, "benchmark": "Public_AR_Current", "format": "json"},
    )
    resp.raise_for_status()
    matches = (resp.json().get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    coords = matches[0]["coordinates"]
    return float(coords["y"]), float(coords["x"])


async def _geocode_photon(client: "httpx.AsyncClient", address: str):
    """Photon (OSM-backed): global, no key, tolerant of datacenter IPs."""
    resp = await client.get(
        f"{config.PHOTON_URL}/api", params={"q": address, "limit": 1}
    )
    resp.raise_for_status()
    features = resp.json().get("features") or []
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"]
    return float(lat), float(lon)


async def _geocode_nominatim(client: "httpx.AsyncClient", address: str):
    """Nominatim: last resort. Its policy caps us at 1 req/s and it 403s
    from many datacenter IPs, so it only runs when the others come up empty."""
    async with _nominatim_lock:
        try:
            resp = await client.get(
                f"{config.NOMINATIM_URL}/search",
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            results = resp.json()
        finally:
            await asyncio.sleep(1.0)
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


_PROVIDERS = (
    ("census", _geocode_census),
    ("photon", _geocode_photon),
    ("nominatim", _geocode_nominatim),
)


async def geocode(address: str) -> tuple[float, float] | None:
    """Address -> (lat, lon), trying each provider in turn.

    Results are cached in SQLite, misses included, so a bad address is not
    re-queried on every scheduled update.
    """
    if not address:
        return None
    address = address.strip()

    hit = tracking.cached_geocode(address)
    if hit:
        return hit

    async with httpx.AsyncClient(timeout=20.0,
                                 headers={"User-Agent": _USER_AGENT}) as client:
        for name, provider in _PROVIDERS:
            try:
                found = await provider(client, address)
            except Exception as exc:  # network, HTTP, malformed payload
                log.warning("geocoder %s failed for %r: %s", name, address, exc)
                continue
            if found:
                tracking.cache_geocode(address, found[0], found[1])
                return found
            log.info("geocoder %s had no match for %r", name, address)

    # Cache the miss so every provider isn't re-tried on each update.
    tracking.cache_geocode(address, None, None)
    return None


async def route(origin: tuple[float, float], dest: tuple[float, float]) -> dict | None:
    """Driving distance and duration between two coordinate pairs.

    Returns ``{"miles": float, "hours": float}`` or None if routing fails.
    """
    (lat1, lon1), (lat2, lon2) = origin, dest
    url = f"{config.OSRM_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.get(url, params={"overview": "false"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        log.warning("routing failed %s -> %s: %s", origin, dest, exc)
        return None

    routes = data.get("routes") or []
    if not routes:
        return None
    leg = routes[0]
    return {
        "miles": leg["distance"] / METERS_PER_MILE,
        "hours": leg["duration"] / 3600.0,
    }


async def route_between_addresses(origin: str, dest: str) -> dict | None:
    """Convenience wrapper: geocode both ends, then route."""
    a = await geocode(origin)
    b = await geocode(dest)
    if not a or not b:
        return None
    return await route(a, b)


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line distance — used only for the 'are we there yet' radius check."""
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 3958.7613 * asin(sqrt(h))
