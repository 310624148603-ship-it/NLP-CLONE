"""
Wyoming Vosk STT client stub.

TODO: Replace with a real Wyoming protocol client that streams PCM audio to
      the vosk container and returns the transcript string.
      The Wyoming protocol uses length-prefixed JSON+binary frames over TCP.
      See https://github.com/rhasspy/wyoming for the spec.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("stt")

STT_URI: str = os.environ.get("STT_URI", "tcp://vosk:10300")


async def transcribe(pcm_bytes: bytes) -> str:
    """
    Transcribe raw 16 kHz / 16-bit / mono PCM audio.

    Parameters
    ----------
    pcm_bytes:
        Raw PCM audio bytes (16 kHz, 16-bit signed, mono).

    Returns
    -------
    str
        The transcribed text, or an empty string when nothing was recognised.

    Notes
    -----
    This is currently a stub — it always returns an empty string.
    Swap-in plan:
      1. Open a TCP connection to ``STT_URI``.
      2. Send Wyoming ``AudioStart`` frame.
      3. Chunk ``pcm_bytes`` into 960-sample frames and send ``AudioChunk``
         frames.
      4. Send ``AudioStop`` frame and await ``Transcript`` response.
    """
    logger.debug(
        "stt.transcribe() stub called — %d PCM bytes (STT_URI=%s)",
        len(pcm_bytes),
        STT_URI,
    )
    # TODO: implement Wyoming Vosk client
    return ""
