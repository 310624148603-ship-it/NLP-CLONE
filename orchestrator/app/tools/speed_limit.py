"""
Valhalla speed-limit lookup stub + Tamil Nadu default speed-limit table.

TODO: Replace with a real Valhalla ``trace_attributes`` API call that uses
      the current GPS trace to determine road class and posted speed limit.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("speed_limit")

VALHALLA_URL: str = os.environ.get("VALHALLA_URL", "http://valhalla:8002")

# ---------------------------------------------------------------------------
# Tamil Nadu default speed limits (km/h) by road class
# Source: Motor Vehicles Act, 1988 / TNMVR amendments
# ---------------------------------------------------------------------------
TN_DEFAULT_LIMITS_KMH: dict[str, int] = {
    "motorway":       100,
    "trunk":           80,
    "primary":         70,
    "secondary":       60,
    "tertiary":        50,
    "residential":     30,
    "service":         20,
    "unclassified":    40,
    "living_street":   10,
    "unknown":         50,   # conservative default
}


async def get_speed_limit(
    lat: float,
    lon: float,
    shape: Optional[list] = None,
) -> int:
    """
    Return the speed limit in km/h for the road at (*lat*, *lon*).

    Parameters
    ----------
    lat, lon:
        Current GPS position in decimal degrees.
    shape:
        Optional list of ``{"lat": ..., "lon": ...}`` dicts representing
        the recent GPS trace, used for Valhalla ``trace_attributes``.

    Returns
    -------
    int
        Speed limit in km/h.  Falls back to the TN default for ``unknown``
        road class when Valhalla is unavailable.
    """
    if shape:
        limit = await _valhalla_trace_attributes(shape)
        if limit is not None:
            return limit

    logger.debug(
        "speed_limit stub: Valhalla unavailable — returning TN default %d km/h",
        TN_DEFAULT_LIMITS_KMH["unknown"],
    )
    return TN_DEFAULT_LIMITS_KMH["unknown"]


async def _valhalla_trace_attributes(shape: list) -> Optional[int]:
    """
    Call the Valhalla ``/trace_attributes`` endpoint.

    Returns the posted speed limit in km/h, or ``None`` on failure.
    """
    payload = {
        "shape": shape,
        "costing": "auto",
        "shape_match": "map_snap",
        "filters": {
            "attributes": ["edge.speed_limit"],
            "action": "include",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{VALHALLA_URL}/trace_attributes",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            edges = data.get("edges", [])
            if edges:
                limit = edges[0].get("speed_limit")
                if isinstance(limit, (int, float)) and limit > 0:
                    return int(limit)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.debug("Valhalla trace_attributes failed: %s", exc)

    return None
