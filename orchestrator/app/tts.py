"""
TTS helper — generates a WAV file containing an 880 Hz sine-wave tone.

This acts as a placeholder until the Piper TTS service is wired in.

Piper swap-in
-------------
To replace this stub with real neural TTS:

1. Ensure the ``piper`` service in docker-compose.yml is running and healthy.
2. In ``synthesize()``, open a TCP connection to ``TTS_URI`` (Wyoming protocol).
3. Send a Wyoming ``Synthesize`` request containing the ``text`` field.
4. Receive the streamed ``AudioChunk`` frames and reassemble them into a WAV.

Example Wyoming Synthesize request (JSON, length-prefixed):
    {"type": "synthesize", "data": {"text": "<utterance>"}}
"""

from __future__ import annotations

import io
import logging
import math
import os
import struct
import wave

logger = logging.getLogger("tts")

TTS_URI: str = os.environ.get("TTS_URI", "tcp://piper:10200")

# Sine-wave parameters
_SAMPLE_RATE = 16_000        # Hz
_FREQUENCY = 880             # Hz  (A5)
_DURATION_S = 1.0            # seconds
_AMPLITUDE = 16_000          # out of 32 767


def _generate_sine_wav(
    frequency: float = _FREQUENCY,
    duration_s: float = _DURATION_S,
    sample_rate: int = _SAMPLE_RATE,
    amplitude: int = _AMPLITUDE,
) -> bytes:
    """Return WAV bytes for a pure sine-wave tone."""
    n_samples = int(sample_rate * duration_s)
    samples = [
        int(amplitude * math.sin(2 * math.pi * frequency * t / sample_rate))
        for t in range(n_samples)
    ]

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *samples))

    return buf.getvalue()


async def synthesize(text: str) -> bytes:
    """
    Synthesise speech for *text* and return WAV bytes.

    Parameters
    ----------
    text:
        The utterance to speak.  Currently ignored by the stub.

    Returns
    -------
    bytes
        WAV audio bytes (16 kHz, 16-bit, mono).
    """
    logger.debug("tts.synthesize() stub called with text=%r (TTS_URI=%s)", text, TTS_URI)
    # TODO: implement Wyoming Piper client (see module docstring for plan)
    return _generate_sine_wav()
