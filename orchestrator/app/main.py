"""
FastAPI orchestrator — coordinates wake-word, STT, TTS, RAG, and routing.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Deque, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.stt import transcribe
from app.tts import synthesize

logger = logging.getLogger("orchestrator")

app = FastAPI(title="Voice Assistant Orchestrator", version="0.1.0")

# ---------------------------------------------------------------------------
# In-memory GPS state
# ---------------------------------------------------------------------------

MAX_TRACE_POINTS = 50

class GPSPoint(BaseModel):
    lat: float
    lon: float
    speed_mps: float = 0.0
    bearing: float = 0.0
    ts: int = 0


_last_gps: Optional[GPSPoint] = None
_gps_trace: Deque[GPSPoint] = deque(maxlen=MAX_TRACE_POINTS)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Return service health status."""
    return {"status": "ok"}


@app.post("/gps")
async def receive_gps(point: GPSPoint) -> dict:
    """Store the latest GPS fix and append to the rolling 50-point trace."""
    global _last_gps
    _last_gps = point
    _gps_trace.append(point)
    return {"stored": True, "trace_len": len(_gps_trace)}


async def _handle_end_frame(websocket: WebSocket, pcm_buffer: bytearray) -> None:
    """Transcribe accumulated audio, synthesise a reply, and send WAV bytes."""
    text = await transcribe(bytes(pcm_buffer))
    logger.info("Transcribed: %r", text)
    wav_bytes = await synthesize(text or "")
    await websocket.send_bytes(wav_bytes)
    pcm_buffer.clear()


@app.websocket("/ws/mic")
async def mic_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for audio I/O.

    Protocol (client → server)
    --------------------------
    • Binary frames  : 640-byte PCM chunks (20 ms @ 16 kHz / 16-bit / mono).
    • Text frame     : JSON ``{"type": "end"}`` signals end of utterance.

    Protocol (server → client)
    --------------------------
    • Binary frame   : synthesised WAV bytes.
    """
    await websocket.accept()
    pcm_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"] is not None:
                pcm_buffer.extend(message["bytes"])
                continue

            if "text" in message and message["text"] is not None:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    logger.warning("Non-JSON text frame ignored: %s", message["text"])
                    continue

                if payload.get("type") == "end":
                    await _handle_end_frame(websocket, pcm_buffer)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
