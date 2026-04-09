"""
api/server.py
SmartSalai Edge-Sentinel — FastAPI REST + Live Streaming Server

Existing REST endpoints (unchanged):
  POST /api/v1/internal/ingest          — Edge telemetry ingest (100 Hz)
  GET  /api/v1/fleet-routing-hazards    — Premium hazard feed (API-key gated)
  POST /api/v1/webhook/razorpay         — Razorpay HMAC-SHA256 webhook

Live / real-time endpoints (NEW):
  GET  /                                — Live dashboard (HTML single-page app)
  GET  /video_feed                      — MJPEG camera stream (cv2 required)
  WS   /ws/live                         — WebSocket JSON event stream
                                          broadcasts: detection | alert | gps | imu | heartbeat
  POST /api/v1/gps/update               — Push GPS coordinates; broadcasts to all WS clients

Camera / inference background task:
  Enabled when LIVE_CAMERA_ENABLED=1 (default: off, so tests are unaffected).
  Camera index controlled by CAMERA_INDEX env var (default: 0).
  Vision inference runs via VisionAuditEngine (mock-safe).

STARTUP:
  # Simple REST + WebSocket server (no camera):
  uvicorn api.server:app --host 0.0.0.0 --port 8000

  # Live camera + inference (use live_runner.py instead):
  LIVE_CAMERA_ENABLED=1 CAMERA_INDEX=0 uvicorn api.server:app --host 0.0.0.0 --port 8000

NOTE:
  All secrets are read from environment variables / .env — never hardcoded.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import queue as _queue
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("edge_sentinel.api")

# ---------------------------------------------------------------------------
# Optional FastAPI import — graceful degradation so importing this module
# in unit tests does not fail if fastapi is not installed.
# ---------------------------------------------------------------------------
try:
    from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, status
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Optional cv2 — only needed for MJPEG camera stream
# ---------------------------------------------------------------------------
try:
    import cv2 as _cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration (all secrets from env — never hardcoded)
# ---------------------------------------------------------------------------
_FLEET_API_KEYS = set(filter(None, os.getenv("FLEET_API_KEYS", "").split(",")))
_RAZORPAY_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
_LIVE_CAMERA_ENABLED = os.getenv("LIVE_CAMERA_ENABLED", "0") == "1"
_CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))

# ---------------------------------------------------------------------------
# Live GPS state — updated via POST /api/v1/gps/update or env vars
# ---------------------------------------------------------------------------
_live_gps: Dict[str, float] = {
    "lat": float(os.getenv("GPS_LAT", "13.0827")),   # Default: Chennai
    "lon": float(os.getenv("GPS_LON", "80.2707")),
}
_gps_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Alert log — rolling window of last 200 alerts, thread-safe append
# ---------------------------------------------------------------------------
_alert_log: deque = deque(maxlen=200)
_alert_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Thread → async event bridge
# Camera/IMU threads post dicts here; async broadcast_task drains it.
# ---------------------------------------------------------------------------
_event_queue: _queue.Queue = _queue.Queue(maxsize=200)

# ---------------------------------------------------------------------------
# MJPEG frame queue — camera thread posts encoded JPEG bytes here.
# Latest frame is held in _latest_frame for new MJPEG subscribers.
# ---------------------------------------------------------------------------
_frame_queue: _queue.Queue = _queue.Queue(maxsize=2)
_latest_frame: Optional[bytes] = None
_frame_lock = threading.Lock()


# ---------------------------------------------------------------------------
# WebSocket connection manager
# All mutations happen in the asyncio event loop — no asyncio.Lock needed.
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Manages the set of active WebSocket connections.

    connect()    — accept + register a new client
    disconnect() — remove a client (called on WebSocketDisconnect or error)
    broadcast()  — send a JSON string to every connected client; dead
                   connections are pruned silently so the loop never blocks.
    """

    def __init__(self) -> None:
        self.active: Set["WebSocket"] = set()

    async def connect(self, websocket: "WebSocket") -> None:
        await websocket.accept()
        self.active.add(websocket)
        logger.info("[WS] client connected (%d total)", len(self.active))

    def disconnect(self, websocket: "WebSocket") -> None:
        self.active.discard(websocket)
        logger.info("[WS] client disconnected (%d remaining)", len(self.active))

    async def broadcast(self, message: str) -> None:
        dead: Set["WebSocket"] = set()
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self.active -= dead


# Module-level singleton — shared between endpoints and background tasks.
manager: ConnectionManager = ConnectionManager()


# ---------------------------------------------------------------------------
# Camera / inference background helpers
# ---------------------------------------------------------------------------

def _camera_thread_fn(camera_index: int) -> None:
    """
    Runs in a daemon thread when LIVE_CAMERA_ENABLED=1.

    Reads frames from cv2.VideoCapture, runs VisionAuditEngine inference,
    and posts events into _event_queue / _frame_queue for the async layer.
    Falls back gracefully if cv2 or onnxruntime are unavailable.
    """
    global _latest_frame  # noqa: PLW0603

    if not _CV2_AVAILABLE:
        logger.warning("[CAM] cv2 not installed — camera thread exiting.")
        return

    # Lazy-import vision engine to avoid circular deps at module load time.
    try:
        import sys
        import os as _os
        _root = _os.path.dirname(_os.path.dirname(__file__))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from vision_audit import VisionAuditEngine  # noqa: PLC0415
        _engine = VisionAuditEngine()
    except Exception as exc:
        logger.error("[CAM] VisionAuditEngine init failed: %s", exc)
        _engine = None

    cap = _cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        logger.error("[CAM] Cannot open camera index %d", camera_index)
        return

    logger.info("[CAM] Camera %d opened — streaming at native FPS", camera_index)

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.warning("[CAM] Frame read failed — retrying in 100 ms")
            time.sleep(0.1)
            continue

        # --- Vision inference ---
        detections: List[Dict[str, Any]] = []
        if _engine is not None and not _engine.is_mock:
            try:
                detections = _engine.run_inference(frame)
            except Exception as exc:
                logger.debug("[CAM] Inference error: %s", exc)

        # --- Encode frame as JPEG for MJPEG stream ---
        ok, buf = _cv2.imencode(".jpg", frame, [int(_cv2.IMWRITE_JPEG_QUALITY), 75])
        if ok:
            jpeg_bytes = buf.tobytes()
            with _frame_lock:
                _latest_frame = jpeg_bytes  # type: ignore[assignment]
            # Drop old frame to avoid stale data
            if _frame_queue.full():
                try:
                    _frame_queue.get_nowait()
                except _queue.Empty:
                    pass
            _frame_queue.put_nowait(jpeg_bytes)

        # --- Post detection event ---
        if detections:
            _event_queue.put_nowait({
                "type": "detection",
                "data": detections,
                "ts": time.time(),
            })

        # --- Post GPS heartbeat (10 Hz) ---
        with _gps_lock:
            lat = _live_gps["lat"]
            lon = _live_gps["lon"]
        _event_queue.put_nowait({
            "type": "gps",
            "lat": lat,
            "lon": lon,
            "ts": time.time(),
        })

        time.sleep(0.033)  # ~30 FPS cap — leaves CPU headroom for inference

    cap.release()


async def _broadcast_task() -> None:
    """
    Async task that drains _event_queue and broadcasts JSON to all WS clients.
    Also sends a heartbeat every 2 seconds when the queue is idle.
    """
    last_heartbeat = time.time()
    while True:
        try:
            event = _event_queue.get_nowait()
            await manager.broadcast(json.dumps(event))
        except _queue.Empty:
            now = time.time()
            if now - last_heartbeat >= 2.0:
                last_heartbeat = now
                with _gps_lock:
                    lat = _live_gps["lat"]
                    lon = _live_gps["lon"]
                await manager.broadcast(json.dumps({
                    "type": "heartbeat",
                    "ts": now,
                    "lat": lat,
                    "lon": lon,
                    "connected_clients": len(manager.active),
                }))
            await asyncio.sleep(0.02)   # 50 Hz polling — sub-20 ms event latency


# ---------------------------------------------------------------------------
# Dashboard HTML path
# ---------------------------------------------------------------------------
_UI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
_DASHBOARD_PATH = os.path.join(_UI_DIR, "dashboard.html")


def _load_dashboard_html() -> str:
    """Load the dashboard HTML from ui/dashboard.html if it exists."""
    try:
        with open(_DASHBOARD_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "<h1>SmartSalai Edge-Sentinel</h1><p>ui/dashboard.html not found.</p>"


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

if FASTAPI_AVAILABLE:
    class TelemetryIngestPayload(BaseModel):
        node_id: str
        event_type: str
        hazard_class: Optional[str] = None
        confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
        gps_lat: Optional[float] = None
        gps_lon: Optional[float] = None
        timestamp: float = Field(default_factory=time.time)

    class RazorpayWebhookPayload(BaseModel):
        razorpay_payment_id: Optional[str] = None
        razorpay_order_id: Optional[str] = None
        razorpay_signature: Optional[str] = None

    class GPSUpdatePayload(BaseModel):
        lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
        lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")


# ---------------------------------------------------------------------------
# Signature verification helpers
# ---------------------------------------------------------------------------

def _verify_razorpay_signature(
    order_id: str, payment_id: str, signature: str, secret: str
) -> bool:
    """
    Razorpay HMAC-SHA256 verification:
    expected = HMAC-SHA256( key=secret, message=order_id + "|" + payment_id )
    """
    if not secret:
        return False
    msg = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> "FastAPI":
    if not FASTAPI_AVAILABLE:
        raise ImportError(
            "fastapi is not installed. Run: pip install fastapi uvicorn"
        )

    app = FastAPI(
        title="SmartSalai Edge-Sentinel API",
        version="0.1.0",
        description="Internal telemetry ingest + fleet hazard routing + live vision dashboard.",
    )

    # ------------------------------------------------------------------
    # Lifespan: start background tasks and camera thread on startup
    # ------------------------------------------------------------------

    @app.on_event("startup")
    async def _startup() -> None:
        # Start the async broadcast task (always active — drains event queue)
        asyncio.create_task(_broadcast_task())
        logger.info("[SERVER] Broadcast task started.")

        if _LIVE_CAMERA_ENABLED:
            t = threading.Thread(
                target=_camera_thread_fn,
                args=(_CAMERA_INDEX,),
                daemon=True,
                name="camera_inference",
            )
            t.start()
            logger.info("[SERVER] Camera thread started (index=%d).", _CAMERA_INDEX)
        else:
            logger.info("[SERVER] Camera disabled (LIVE_CAMERA_ENABLED != 1).")

    # ------------------------------------------------------------------
    # GET / — Live dashboard
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard() -> HTMLResponse:
        """Serve the single-page live dashboard."""
        return HTMLResponse(content=_load_dashboard_html())

    # ------------------------------------------------------------------
    # GET /video_feed — MJPEG camera stream
    # ------------------------------------------------------------------

    async def _mjpeg_generator():
        """Async generator that yields MJPEG multipart frames."""
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        # Send latest frame immediately if available so the browser doesn't
        # show a blank image while waiting for the next capture.
        with _frame_lock:
            seed = _latest_frame
        if seed:
            yield boundary + seed + b"\r\n"

        while True:
            try:
                jpeg = _frame_queue.get(timeout=1.0)
                yield boundary + jpeg + b"\r\n"
            except _queue.Empty:
                # Keep connection alive — yield a keep-alive comment in the stream
                yield b"--frame\r\nContent-Type: text/plain\r\n\r\nkeep-alive\r\n"

    @app.get("/video_feed", include_in_schema=False)
    async def video_feed():
        """
        MJPEG stream for the live camera.
        Returns 503 when cv2 / camera is unavailable.
        """
        if not _CV2_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Camera unavailable: cv2 not installed. "
                       "Run: pip install opencv-python",
            )
        if not _LIVE_CAMERA_ENABLED:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Camera stream disabled. Set LIVE_CAMERA_ENABLED=1 to enable.",
            )
        return StreamingResponse(
            _mjpeg_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    # ------------------------------------------------------------------
    # WS /ws/live — real-time JSON event stream
    # ------------------------------------------------------------------

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket):
        """
        WebSocket endpoint that streams live events to browser clients.

        Message types:
          detection — {type, data: [{label, conf, bbox}], ts}
          alert     — {type, severity, message, ts}
          gps       — {type, lat, lon, ts}
          imu       — {type, ax, ay, az, severity, ts}
          heartbeat — {type, ts, lat, lon, connected_clients}
        """
        await manager.connect(websocket)
        # Send current GPS state immediately on connect
        with _gps_lock:
            lat = _live_gps["lat"]
            lon = _live_gps["lon"]
        try:
            await websocket.send_text(json.dumps({
                "type": "gps",
                "lat": lat,
                "lon": lon,
                "ts": time.time(),
            }))
            # Keep the connection open; broadcast_task handles outgoing messages.
            # We keep a receive loop so we can detect disconnects.
            while True:
                await websocket.receive_text()   # client messages currently ignored
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception:
            manager.disconnect(websocket)

    # ------------------------------------------------------------------
    # POST /api/v1/gps/update — push GPS from external source
    # ------------------------------------------------------------------

    @app.post("/api/v1/gps/update", status_code=status.HTTP_200_OK)
    async def gps_update(payload: GPSUpdatePayload):
        """
        Update the live GPS coordinates.

        Intended for:
          • A GPS USB dongle feeding position via a small companion script.
          • The live_runner.py NMEA serial reader.
          • Manual override for testing.

        Broadcasts a 'gps' event to all connected WebSocket clients immediately.
        """
        with _gps_lock:
            _live_gps["lat"] = payload.lat
            _live_gps["lon"] = payload.lon

        event = {"type": "gps", "lat": payload.lat, "lon": payload.lon, "ts": time.time()}
        await manager.broadcast(json.dumps(event))
        return {"status": "OK", "lat": payload.lat, "lon": payload.lon}

    # ------------------------------------------------------------------
    # POST /api/v1/internal/ingest
    # ------------------------------------------------------------------
    @app.post("/api/v1/internal/ingest", status_code=status.HTTP_201_CREATED)
    async def ingest_telemetry(payload: TelemetryIngestPayload):
        """
        Receive a telemetry event from an edge node (dashcam / IMU sensor).
        Broadcasts detections / alerts to WebSocket clients in addition to
        returning the standard ACCEPTED response.
        """
        logger.info(
            f"[INGEST] node={payload.node_id} event={payload.event_type} "
            f"hazard={payload.hazard_class} conf={payload.confidence}"
        )

        # Broadcast hazard as alert event so the dashboard gets notified
        if payload.hazard_class:
            alert_event = {
                "type": "alert",
                "severity": "HIGH",
                "message": f"Hazard detected: {payload.hazard_class} "
                           f"(conf={payload.confidence:.2f})" if payload.confidence else
                           f"Hazard detected: {payload.hazard_class}",
                "node_id": payload.node_id,
                "ts": time.time(),
            }
            with _alert_lock:
                _alert_log.append(alert_event)
            _event_queue.put_nowait(alert_event)

        return {
            "status": "ACCEPTED",
            "event_type": payload.event_type,
            "node_id": payload.node_id,
            "server_epoch_ms": int(time.time() * 1000),
        }

    # ------------------------------------------------------------------
    # GET /api/v1/fleet-routing-hazards
    # ------------------------------------------------------------------
    @app.get("/api/v1/fleet-routing-hazards")
    async def fleet_routing_hazards(x_api_key: Optional[str] = Header(None)):
        """
        Returns active hazard feed for fleet routing decisions.
        Requires X-API-Key header with a valid key from FLEET_API_KEYS env var.
        """
        if not x_api_key or x_api_key not in _FLEET_API_KEYS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key.",
            )
        # TODO (T-018): query edge_spatial.db for recent hazards (last 30 min)
        return {"hazards": [], "generated_at_epoch_ms": int(time.time() * 1000)}

    # ------------------------------------------------------------------
    # POST /api/v1/webhook/razorpay
    # ------------------------------------------------------------------
    @app.post("/api/v1/webhook/razorpay")
    async def razorpay_webhook(payload: RazorpayWebhookPayload):
        """
        Razorpay payment webhook handler.
        Verifies HMAC-SHA256 signature before processing.
        """
        if not payload.razorpay_payment_id or not payload.razorpay_order_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing payment_id or order_id.",
            )
        if not payload.razorpay_signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Razorpay signature.",
            )
        if not _verify_razorpay_signature(
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
            _RAZORPAY_SECRET,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Razorpay signature. Payment verification failed.",
            )
        logger.info(f"[WEBHOOK] Payment verified: {payload.razorpay_payment_id}")
        return {"status": "PAYMENT_VERIFIED", "payment_id": payload.razorpay_payment_id}

    return app


# ---------------------------------------------------------------------------
# ASGI app instance (used by uvicorn)
# ---------------------------------------------------------------------------
if FASTAPI_AVAILABLE:
    app = create_app()
