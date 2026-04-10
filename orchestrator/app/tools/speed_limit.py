"""
orchestrator/app/tools/speed_limit.py
======================================
Speed-limit lookup stub backed by the Valhalla routing engine.

In production this module will:
1. Send the current GPS co-ordinates (lat, lon) to the Valhalla
   ``/locate`` endpoint with ``verbose=true`` to snap to the nearest road.
2. Parse the ``speed_limit`` field from the returned edge metadata.
3. Fall back to the Tamil Nadu default table when Valhalla is unavailable.

TODO: Wire to the actual Valhalla HTTP API.
      Reference: https://valhalla.github.io/valhalla/api/locate/api-reference/
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_HOST = os.getenv("VALHALLA_HOST", "valhalla")
_PORT = int(os.getenv("VALHALLA_PORT", "8002"))
_BASE_URL = f"http://{_HOST}:{_PORT}"

# ---------------------------------------------------------------------------
# Tamil Nadu default speed limits (km/h)
# Source: CMV Rules 1989 read with TN Motor Vehicles (Amendment) Rules
# ---------------------------------------------------------------------------
TN_DEFAULT_SPEED_LIMITS: dict = {
    "expressway":          120,  # National expressways (e.g. Chennai-Bengaluru)
    "national_highway":    100,  # NH — 4-lane sections
    "state_highway":        80,  # SH — undivided carriageway
    "district_road":        60,  # MDR / ODR
    "urban_arterial":       50,  # Municipal roads outside core zone
    "urban_core":           30,  # City centre / school zones
    "unknown":              50,  # Conservative fallback
}


async def get_speed_limit(lat: float, lon: float) -> dict:
    """
    Return the speed limit (km/h) and road type for a given GPS position.

    Parameters
    ----------
    lat:
        Latitude in decimal degrees (WGS-84).
    lon:
        Longitude in decimal degrees (WGS-84).

    Returns
    -------
    dict
        Keys: ``speed_kmh`` (int), ``road_type`` (str), ``source`` (str).

    Notes
    -----
    This is currently a **stub** that returns Tamil Nadu urban-arterial
    defaults.  Wire in the Valhalla ``/locate`` API for real map-matched
    speed limits.
    """
    # TODO: Make async HTTP call to Valhalla /locate endpoint
    # Example:
    #   url = f"{_BASE_URL}/locate?json={{\"locations\":[{{\"lon\":{lon},\"lat\":{lat}}}],\"verbose\":true}}"
    #   async with httpx.AsyncClient() as client:
    #       resp = await client.get(url, timeout=5.0)
    #       data = resp.json()
    #       speed = data[0]["edges"][0]["speed_limit"]
    #       ...

    logger.warning(
        "speed_limit.get_speed_limit() is a stub — returning TN default. "
        "Wire in Valhalla at %s for real map-matched speed limits. "
        "(lat=%.5f, lon=%.5f)",
        _BASE_URL,
        lat,
        lon,
    )

    road_type = "urban_arterial"
    speed_kmh = TN_DEFAULT_SPEED_LIMITS[road_type]

    return {
        "speed_kmh": speed_kmh,
        "road_type": road_type,
        "source": "tn_default_table",
    }
