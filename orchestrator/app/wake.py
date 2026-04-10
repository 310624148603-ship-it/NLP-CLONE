"""
Wyoming OpenWakeWord client stub.

TODO: Replace with a real Wyoming protocol client once the service is running.
      The Wyoming protocol uses length-prefixed JSON+binary frames over TCP.
      See https://github.com/rhasspy/wyoming for the spec.
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger("wake")

WAKE_URI: str = os.environ.get("WAKE_URI", "tcp://openwakeword:10400")


async def wait_for_wakeword() -> str:
    """
    Block until the wake-word service detects the configured phrase.

    Returns the name of the detected wake-word model (e.g. ``"hey_jarvis"``).

    This is currently a stub — it resolves immediately with the default model
    name so that the rest of the pipeline can be developed and tested without
    a live OpenWakeWord container.
    """
    # TODO: open a TCP connection to WAKE_URI and implement the Wyoming
    #       AudioChunk / Detection frame exchange.
    logger.debug("wake.wait_for_wakeword() stub called (WAKE_URI=%s)", WAKE_URI)
    await asyncio.sleep(0)
    return "hey_jarvis"
