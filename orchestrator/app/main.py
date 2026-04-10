"""
orchestrator/app/main.py
========================
FastAPI coordinator for the NNDL offline voice assistant stack.

Endpoints
---------
GET  /health      — Returns health status of the orchestrator and downstream services.
POST /gps         — Receives GPS data and maintains a 50-point rolling trace.
WS   /ws/mic      — WebSocket for real-time audio streaming:
                    • Client sends 640-byte binary PCM frames (20 ms @ 16 kHz/16-bit/mono)
                    • Client sends {"type":"end"} JSON text frame to signal utterance end
                    • Server transcribes audio, synthesises reply, returns WAV bytes
"""

from __future__ import annotations

import json
import logging
import os
from collections import deque
from typing import Deque, Dict, List

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .stt import transcribe_audio
from .tts import create_wav_bytes

# ---------------------------------------------------------------------------
# Logging — use module-level logger; uvicorn configures the root handler
# ---------------------------------------------------------------------------
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="NNDL Voice Assistant Orchestrator",
    description="Offline voice assistant coordinator for Tamil Nadu drivers",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# GPS rolling trace — keeps last 50 fixes
# ---------------------------------------------------------------------------
GPS_TRACE_LEN = 50
_gps_trace: Deque[Dict] = deque(maxlen=GPS_TRACE_LEN)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class GPSPoint(BaseModel):
    """A single GPS fix from the driver device."""
    lat: float
    lon: float
    speed_mps: float = 0.0
    bearing: float = 0.0
    ts: float  # Unix timestamp (seconds)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", summary="Service health check")
async def health() -> Dict:
    """
    Returns the health status of the orchestrator and a summary of its
    connectivity to downstream services (optimistic — does not open TCP
    connections at query time; relies on env vars for addresses).
    """
    return {
        "status": "ok",
        "services": {
            "openwakeword": {
                "host": os.getenv("OPENWAKEWORD_HOST", "openwakeword"),
                "port": int(os.getenv("OPENWAKEWORD_PORT", "10400")),
            },
            "vosk": {
                "host": os.getenv("VOSK_HOST", "vosk"),
                "port": int(os.getenv("VOSK_PORT", "10300")),
            },
            "piper": {
                "host": os.getenv("PIPER_HOST", "piper"),
                "port": int(os.getenv("PIPER_PORT", "10200")),
            },
            "qdrant": {
                "host": os.getenv("QDRANT_HOST", "qdrant"),
                "port": int(os.getenv("QDRANT_PORT", "6333")),
            },
            "valhalla": {
                "host": os.getenv("VALHALLA_HOST", "valhalla"),
                "port": int(os.getenv("VALHALLA_PORT", "8002")),
            },
        },
        "gps_trace_length": len(_gps_trace),
    }


@app.post("/gps", summary="Receive a GPS fix")
async def receive_gps(point: GPSPoint) -> Dict:
    """
    Stores an incoming GPS fix in the rolling 50-point trace.
    Returns the current trace length for confirmation.
    """
    _gps_trace.append(point.model_dump())
    logger.debug("GPS fix stored: lat=%.5f lon=%.5f speed=%.1f m/s", point.lat, point.lon, point.speed_mps)
    return {"status": "stored", "trace_length": len(_gps_trace)}


@app.get("/gps/trace", summary="Return current GPS trace")
async def get_gps_trace() -> Dict:
    """Returns the current rolling GPS trace (up to 50 points)."""
    return {"trace": list(_gps_trace)}


@app.websocket("/ws/mic")
async def ws_mic(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio streaming.

    Protocol
    --------
    Client → Server (binary):  640-byte raw PCM frames
                                (20 ms @ 16 kHz / 16-bit / mono)
    Client → Server (text):    {"type": "end"}  — signals utterance boundary
    Server → Client (binary):  WAV file bytes containing the TTS reply
    Server → Client (text):    {"type": "transcript", "text": "..."}
                                (sent before the WAV)

    The server buffers incoming PCM frames until it receives the "end" signal,
    then runs STT → intent resolution → TTS and sends the reply back.
    """
    await websocket.accept()
    logger.info("WebSocket /ws/mic: client connected")

    pcm_buffer: List[bytes] = []

    try:
        while True:
            # Receive either a binary PCM frame or a JSON control message
            message = await websocket.receive()

            if "bytes" in message and message["bytes"] is not None:
                # Binary PCM frame (640 bytes = 20 ms @ 16 kHz/16-bit/mono)
                pcm_buffer.append(message["bytes"])

            elif "text" in message and message["text"] is not None:
                try:
                    ctrl = json.loads(message["text"])
                except json.JSONDecodeError:
                    logger.warning("Non-JSON text frame received; ignoring")
                    continue

                if ctrl.get("type") == "end":
                    # Utterance boundary reached — process the buffered audio
                    logger.info("Utterance end signal received; %d PCM frames buffered", len(pcm_buffer))

                    # Concatenate all PCM bytes into one buffer
                    raw_pcm = b"".join(pcm_buffer)
                    pcm_buffer.clear()

                    # --- STT ---
                    transcript = await transcribe_audio(raw_pcm)
                    logger.info("Transcript: %r", transcript)

                    # Send transcript back so the client can display it
                    await websocket.send_text(
                        json.dumps({"type": "transcript", "text": transcript})
                    )

                    # --- TTS ---
                    wav_bytes = create_wav_bytes(transcript)
                    await websocket.send_bytes(wav_bytes)
                    logger.info("TTS reply sent (%d bytes)", len(wav_bytes))

    except WebSocketDisconnect:
        logger.info("WebSocket /ws/mic: client disconnected")
    except Exception as exc:
        logger.exception("WebSocket /ws/mic error: %s", exc)
        await websocket.close(code=1011)
