#!/usr/bin/env python3
"""
scripts/mic_client.py
=====================
Demo client — records audio from the laptop microphone, streams it to the
NNDL orchestrator WebSocket endpoint, and plays back the TTS reply.

Usage
-----
    python scripts/mic_client.py [--sec 4] [--url ws://localhost:9000/ws/mic]

Requirements
------------
    pip install sounddevice websocket-client numpy

Arguments
---------
--sec     Recording duration in seconds (default: 4)
--url     Orchestrator WebSocket URL (default: ws://localhost:9000/ws/mic)
--save    Path to save the received WAV reply (default: reply.wav)
--no-play Skip playback even if sounddevice is available
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys
import time
import wave

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mic_client")

# Audio capture parameters (must match the orchestrator's expected format)
SAMPLE_RATE = 16_000     # Hz
CHANNELS = 1             # mono
DTYPE = "int16"          # 16-bit PCM
FRAME_SAMPLES = 320      # 20 ms worth of samples at 16 kHz
FRAME_BYTES = FRAME_SAMPLES * 2  # 2 bytes per int16 sample = 640 bytes per frame
RECEIVE_TIMEOUT_S = 30  # seconds to wait for WAV reply from orchestrator


def record_audio(duration_s: float) -> np.ndarray:
    """
    Record *duration_s* seconds of audio from the default microphone.

    Returns
    -------
    np.ndarray
        1-D int16 array of PCM samples.
    """
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        logger.error("sounddevice not installed.  Run: pip install sounddevice")
        sys.exit(1)

    logger.info("Recording %.1f seconds from microphone...", duration_s)
    samples = sd.rec(
        int(duration_s * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
    )
    sd.wait()
    logger.info("Recording complete.")
    return samples.flatten()


def play_wav(wav_bytes: bytes) -> None:
    """
    Attempt to play *wav_bytes* (a complete WAV file) through the speakers.
    Silently skips if sounddevice is unavailable.
    """
    try:
        import sounddevice as sd  # type: ignore
        import soundfile as sf    # type: ignore
    except ImportError:
        logger.warning("sounddevice/soundfile not available — skipping playback.")
        return

    buf = io.BytesIO(wav_bytes)
    data, fs = sf.read(buf, dtype="int16")
    logger.info("Playing TTS reply (%.2f s @ %d Hz)...", len(data) / fs, fs)
    sd.play(data, fs)
    sd.wait()


def stream_and_receive(samples: np.ndarray, url: str) -> bytes:
    """
    Stream PCM audio to the orchestrator and receive the WAV reply.

    Parameters
    ----------
    samples:
        1-D int16 PCM array to stream.
    url:
        WebSocket URL of the orchestrator mic endpoint.

    Returns
    -------
    bytes
        The WAV reply received from the orchestrator.
    """
    try:
        import websocket  # type: ignore (websocket-client)
    except ImportError:
        logger.error("websocket-client not installed.  Run: pip install websocket-client")
        sys.exit(1)

    logger.info("Connecting to %s ...", url)
    ws = websocket.create_connection(url)
    logger.info("Connected.")

    # Send audio in 640-byte (20 ms) frames
    raw = samples.tobytes()
    total_frames = 0
    for offset in range(0, len(raw), FRAME_BYTES):
        chunk = raw[offset : offset + FRAME_BYTES]
        if len(chunk) < FRAME_BYTES:
            # Zero-pad the final partial frame to exactly 640 bytes
            chunk = chunk + b"\x00" * (FRAME_BYTES - len(chunk))
        ws.send_binary(chunk)
        total_frames += 1

    logger.info("Sent %d PCM frames (%d bytes total)", total_frames, len(raw))

    # Signal end of utterance
    ws.send(json.dumps({"type": "end"}))
    logger.info("Sent end signal, waiting for reply...")

    wav_bytes = b""
    transcript = ""

    # Receive messages until we get a binary WAV reply
    deadline = time.time() + RECEIVE_TIMEOUT_S
    while time.time() < deadline:
        try:
            opcode, data = ws.recv_data()
            # opcode 1 = text, opcode 2 = binary
            if opcode == 2:  # binary — WAV reply
                wav_bytes = data
                logger.info("Received WAV reply (%d bytes)", len(wav_bytes))
                break
            elif opcode == 1:  # text — likely transcript message
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "transcript":
                        transcript = msg.get("text", "")
                        logger.info("Transcript: %r", transcript)
                except json.JSONDecodeError:
                    pass
        except Exception as exc:
            logger.error("WebSocket receive error: %s", exc)
            break

    ws.close()
    return wav_bytes


def save_wav(wav_bytes: bytes, path: str) -> None:
    """Save WAV bytes to a file."""
    with open(path, "wb") as f:
        f.write(wav_bytes)
    logger.info("Saved reply to %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record mic audio, stream to NNDL orchestrator, play TTS reply."
    )
    parser.add_argument(
        "--sec",
        type=float,
        default=4.0,
        help="Recording duration in seconds (default: 4)",
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:9000/ws/mic",
        help="Orchestrator WebSocket URL (default: ws://localhost:9000/ws/mic)",
    )
    parser.add_argument(
        "--save",
        default="reply.wav",
        help="Path to save the received WAV reply (default: reply.wav)",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="Skip audio playback",
    )
    args = parser.parse_args()

    # 1. Record
    samples = record_audio(args.sec)

    # 2. Stream and receive reply
    wav_bytes = stream_and_receive(samples, args.url)

    if not wav_bytes:
        logger.error("No WAV reply received from orchestrator.")
        sys.exit(1)

    # 3. Save
    save_wav(wav_bytes, args.save)

    # 4. Play back (optional)
    if not args.no_play:
        play_wav(wav_bytes)


if __name__ == "__main__":
    main()
