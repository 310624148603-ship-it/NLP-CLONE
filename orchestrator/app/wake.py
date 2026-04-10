"""
orchestrator/app/wake.py
========================
Wyoming openWakeWord client stub.

The Wyoming protocol is a simple line-delimited JSON + binary socket protocol
used by Home Assistant add-ons. A full implementation would:

1. Open a TCP connection to the openWakeWord Wyoming server.
2. Send a ``describe`` event and await the ``info`` response.
3. Stream 16kHz/16-bit/mono PCM chunks wrapped in ``audio-chunk`` events.
4. Await a ``detection`` event whose ``name`` matches the configured wake word.

TODO: Implement actual Wyoming wake-word detection.
      Reference: https://github.com/rhasspy/wyoming
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_HOST = os.getenv("OPENWAKEWORD_HOST", "openwakeword")
_PORT = int(os.getenv("OPENWAKEWORD_PORT", "10400"))


async def wait_for_wakeword() -> str:
    """
    Block until the configured wake word is detected.

    Returns
    -------
    str
        The name of the detected wake word (e.g. ``"hey_jarvis"``).

    Notes
    -----
    This is currently a **stub** and returns immediately without performing
    real detection.  Wire in the Wyoming openWakeWord client to enable live
    detection.
    """
    # TODO: Open TCP socket to _HOST:_PORT and implement Wyoming protocol
    logger.warning(
        "wake.wait_for_wakeword() is a stub — returning 'hey_jarvis' immediately. "
        "Wire in Wyoming openWakeWord at %s:%s to enable real detection.",
        _HOST,
        _PORT,
    )
    return "hey_jarvis"
