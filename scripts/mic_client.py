#!/usr/bin/env python3
"""
mic_client.py — Demo script: record from laptop mic and send to orchestrator.

Usage
-----
    pip install sounddevice websocket-client numpy
    python scripts/mic_client.py --sec 4
    # Saves the TTS reply to reply.wav

Protocol
--------
    Client streams 640-byte (20 ms @ 16 kHz/16-bit/mono) binary PCM frames.
    After recording, sends {"type":"end"} JSON text frame.
    Server responds with WAV bytes which are saved to reply.wav.
"""

from __future__ import annotations

import argparse
import io
import sys
import wave

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    print("sounddevice not found. Install with: pip install sounddevice", file=sys.stderr)
    sys.exit(1)

try:
    import websocket
except ImportError:
    print("websocket-client not found. Install with: pip install websocket-client", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Audio constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16_000      # Hz
CHANNELS = 1
SAMPLE_WIDTH = 2          # bytes (16-bit)
FRAME_MS = 20             # milliseconds per PCM chunk
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000   # 320 samples
FRAME_BYTES = FRAME_SAMPLES * SAMPLE_WIDTH        # 640 bytes

SERVER_URL = "ws://localhost:9000/ws/mic"
OUTPUT_FILE = "reply.wav"


def record_pcm(seconds: int) -> bytes:
    """Record *seconds* of audio from the default microphone."""
    print(f"Recording {seconds}s … (speak now)", flush=True)
    samples = sd.rec(
        int(SAMPLE_RATE * seconds),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )
    sd.wait()
    print("Recording complete.", flush=True)
    return samples.tobytes()


def send_and_receive(pcm_bytes: bytes, url: str = SERVER_URL) -> bytes:
    """Stream PCM frames to the server and return the WAV reply bytes."""
    ws = websocket.WebSocket()
    ws.connect(url)
    print(f"Connected to {url}", flush=True)

    # Stream 640-byte frames
    offset = 0
    while offset < len(pcm_bytes):
        frame = pcm_bytes[offset : offset + FRAME_BYTES]
        ws.send_binary(frame)
        offset += FRAME_BYTES

    # Signal end of utterance
    ws.send('{"type":"end"}')
    print("Sent end signal, waiting for reply …", flush=True)

    # Receive WAV reply
    result = ws.recv()
    ws.close()

    if isinstance(result, str):
        raise ValueError(f"Expected binary WAV reply, got text: {result!r}")

    return result  # type: ignore[return-value]


def save_wav(wav_bytes: bytes, path: str) -> None:
    """Validate and save WAV bytes to *path*."""
    # Quick sanity-check: attempt to open as a WAV
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        frames = wf.getnframes()
    print(f"Reply WAV: {channels}ch, {rate} Hz, {frames} frames")

    with open(path, "wb") as f:
        f.write(wav_bytes)
    print(f"Saved reply to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice assistant mic demo client")
    parser.add_argument(
        "--sec",
        type=int,
        default=4,
        metavar="SECONDS",
        help="Number of seconds to record (default: 4)",
    )
    parser.add_argument(
        "--url",
        default=SERVER_URL,
        metavar="WS_URL",
        help=f"Orchestrator WebSocket URL (default: {SERVER_URL})",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_FILE,
        metavar="FILE",
        help=f"Output WAV file (default: {OUTPUT_FILE})",
    )
    args = parser.parse_args()

    pcm = record_pcm(args.sec)

    wav = send_and_receive(pcm, url=args.url)
    save_wav(wav, args.output)


if __name__ == "__main__":
    main()
