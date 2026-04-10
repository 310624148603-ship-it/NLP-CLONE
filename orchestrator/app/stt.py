"""
orchestrator/app/stt.py
=======================
Wyoming Vosk Speech-to-Text client stub.

A full implementation would:

1. Open a TCP connection to the Vosk Wyoming server.
2. Send an ``audio-start`` event (sample_rate=16000, width=2, channels=1).
3. Stream the raw PCM bytes as ``audio-chunk`` events (chunk_samples=480).
4. Send an ``audio-stop`` event to signal end-of-utterance.
5. Await a ``transcript`` event and return its ``text`` field.

TODO: Wire to the actual Vosk Wyoming server.
      Reference: https://github.com/rhasspy/wyoming-vosk
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_HOST = os.getenv("VOSK_HOST", "vosk")
_PORT = int(os.getenv("VOSK_PORT", "10300"))


async def transcribe_audio(raw_pcm: bytes) -> str:
    """
    Transcribe raw PCM audio to text.

    Parameters
    ----------
    raw_pcm:
        Raw 16 kHz / 16-bit / mono PCM bytes (little-endian).

    Returns
    -------
    str
        The transcribed text, or an empty string if recognition failed.

    Notes
    -----
    This is currently a **stub** that returns a placeholder string.
    Wire in the Wyoming Vosk client (TCP socket at ``_HOST:_PORT``) to
    perform real speech recognition.
    """
    # TODO: Open TCP socket to _HOST:_PORT and implement Wyoming STT protocol
    frame_count = len(raw_pcm) // 2  # 16-bit samples
    duration_ms = (frame_count / 16000) * 1000

    logger.warning(
        "stt.transcribe_audio() is a stub — returning placeholder text. "
        "Wire in Wyoming Vosk at %s:%s to enable real STT. "
        "(received %.0f ms of audio, %d bytes)",
        _HOST,
        _PORT,
        duration_ms,
        len(raw_pcm),
    )

    # Placeholder transcript for integration testing
    return "placeholder transcription — wire in vosk"
