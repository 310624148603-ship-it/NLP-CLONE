"""
orchestrator/app/tts.py
=======================
Text-to-Speech helper for the orchestrator.

In production this module will forward text to the Wyoming Piper TTS server
and return real synthesised speech.  For now it generates an 880 Hz sine-wave
WAV file as a placeholder so that the WebSocket pipeline can be tested
end-to-end without a running Piper instance.

Swapping in Piper
-----------------
1. Open a TCP connection to PIPER_HOST:PIPER_PORT (Wyoming protocol).
2. Send a ``synthesize`` event with the text and optional voice name.
3. Await ``audio-start`` then stream ``audio-chunk`` events until
   ``audio-stop``.
4. Concatenate the raw PCM chunks and wrap them in a WAV container using
   ``create_wav_bytes()``.

References
----------
* Wyoming protocol: https://github.com/rhasspy/wyoming
* Piper voices:     https://github.com/rhasspy/piper/releases
"""

from __future__ import annotations

import io
import logging
import math
import os
import struct
import wave

logger = logging.getLogger(__name__)

_HOST = os.getenv("PIPER_HOST", "piper")
_PORT = int(os.getenv("PIPER_PORT", "10200"))

# Audio parameters for the placeholder sine wave
_SAMPLE_RATE = 16_000  # Hz
_SAMPLE_WIDTH = 2      # bytes (16-bit)
_CHANNELS = 1          # mono
_TONE_HZ = 880         # A5 — audible confirmation tone
_DURATION_S = 0.5      # seconds


def _generate_sine_pcm(
    frequency: float = _TONE_HZ,
    duration_s: float = _DURATION_S,
    sample_rate: int = _SAMPLE_RATE,
    amplitude: float = 0.5,
) -> bytes:
    """
    Generate raw 16-bit mono PCM bytes for a sine wave.

    Parameters
    ----------
    frequency:
        Tone frequency in Hz.
    duration_s:
        Duration of the tone in seconds.
    sample_rate:
        Sample rate in Hz (default 16 000).
    amplitude:
        Amplitude in [0, 1] (default 0.5 to avoid clipping).

    Returns
    -------
    bytes
        Raw little-endian 16-bit PCM samples.
    """
    num_samples = int(sample_rate * duration_s)
    max_val = int(32767 * amplitude)
    raw = bytearray(num_samples * 2)
    for i in range(num_samples):
        sample = int(max_val * math.sin(2 * math.pi * frequency * i / sample_rate))
        struct.pack_into("<h", raw, i * 2, sample)
    return bytes(raw)


def create_wav_bytes(text: str) -> bytes:
    """
    Return WAV-encoded audio for the given *text*.

    Currently generates an 880 Hz placeholder tone regardless of the text
    content.  Replace the body of this function with a real Piper Wyoming
    client call to synthesise natural speech.

    Parameters
    ----------
    text:
        The text to synthesise (logged but not yet used for real TTS).

    Returns
    -------
    bytes
        A complete WAV file as bytes, ready to send over the WebSocket.
    """
    logger.warning(
        "tts.create_wav_bytes() is a stub — returning 880 Hz sine wave. "
        "Wire in Wyoming Piper at %s:%s to enable real TTS. (text=%r)",
        _HOST,
        _PORT,
        text,
    )

    # TODO: Replace with Wyoming Piper client call
    pcm = _generate_sine_pcm()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(pcm)

    return buffer.getvalue()
