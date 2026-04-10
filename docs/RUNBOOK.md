# Runbook — Offline Voice Assistant for Tamil Nadu Drivers

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker Desktop | 4.x+ | Windows host; enable WSL 2 backend |
| Python | 3.9+ | For the mic client demo |
| `sounddevice` | latest | `pip install sounddevice` |
| `websocket-client` | latest | `pip install websocket-client` |
| `numpy` | latest | `pip install numpy` |
| ~4 GB RAM free | — | For all containers |

---

## Setup Steps

### 1. Clone the repository

```powershell
git clone https://github.com/<your-org>/NLP-CLONE.git
cd NLP-CLONE
```

### 2. Download the Vosk model

Download a Vosk model (English or Tamil) from https://alphacephei.com/vosk/models

Recommended: **vosk-model-en-us-0.22** (~1.8 GB)

```powershell
# Extract and place at:
mkdir -p models\vosk
# Resulting layout:
#   models\vosk\model\am\
#   models\vosk\model\conf\
#   models\vosk\model\graph\
#   ...
```

The Vosk Wyoming service expects the model at `./models/vosk/model/`.

### 3. Download a Piper voice

Download a Piper `.onnx` voice file from https://huggingface.co/rhasspy/piper-voices

Recommended: **en_US-lessac-medium**

```powershell
mkdir voices
# Place en_US-lessac-medium.onnx (and .onnx.json config) in ./voices/
```

The default voice selection is controlled by the `PIPER_VOICE` environment
variable in `docker-compose.yml`. Adjust if you choose a different voice:

```yaml
# docker-compose.yml → piper service
environment:
  - PIPER_VOICE=en_US-lessac-medium
```

### 4. (Optional) Add Valhalla tiles

Download OSM tiles for Tamil Nadu from https://download.geofabrik.de/asia/india.html

Place extracted tiles in `./data/valhalla_tiles/`.

If you skip this step, the `speed_limit` tool falls back to TN default limits.

### 5. Start all services

```powershell
docker compose up --build
```

Expected healthy output (may take a few minutes on first run):

```
orchestrator   | INFO:     Uvicorn running on http://0.0.0.0:9000
vosk           | INFO:     Listening on tcp://0.0.0.0:10300
piper          | INFO:     Listening on tcp://0.0.0.0:10200
openwakeword   | INFO:     Listening on tcp://0.0.0.0:10400
qdrant         | {"level":"INFO","message":"Qdrant HTTP listening on 0.0.0.0:6333"}
valhalla       | [INFO] valhalla_service: Listening on 0.0.0.0:8002
```

### 6. Verify health endpoint

```powershell
curl http://localhost:9000/health
# Expected: {"status":"ok"}
```

### 7. Run the mic client demo

```powershell
# Install Python dependencies
pip install sounddevice websocket-client numpy

# Record 4 seconds and send to orchestrator
python scripts/mic_client.py --sec 4
```

The script will:
1. Record 4 seconds from your default microphone
2. Stream 20 ms PCM frames to `ws://localhost:9000/ws/mic`
3. Save the TTS reply WAV to `reply.wav`

Play back the reply:

```powershell
# Windows
start reply.wav

# Or use any media player
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPER_VOICE` | `en_US-lessac-medium` | Voice file name (without `.onnx`) |
| `WAKE_URI` | `tcp://openwakeword:10400` | Wyoming wake-word service |
| `STT_URI` | `tcp://vosk:10300` | Wyoming STT service |
| `TTS_URI` | `tcp://piper:10200` | Wyoming TTS service |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant vector DB |
| `VALHALLA_URL` | `http://valhalla:8002` | Valhalla routing engine |

Set overrides in a `.env` file at the repository root.

---

## Port Verification

```powershell
# Check which containers are running and their ports
docker compose ps

# Expected:
# orchestrator    0.0.0.0:9000->9000/tcp
# vosk            0.0.0.0:10300->10300/tcp
# piper           0.0.0.0:10200->10200/tcp
# openwakeword    0.0.0.0:10400->10400/tcp
# qdrant          0.0.0.0:6333->6333/tcp
# valhalla        0.0.0.0:8002->8002/tcp
```

---

## Inspect Logs

```powershell
# All services
docker compose logs -f

# Single service
docker compose logs -f orchestrator
docker compose logs -f vosk
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `orchestrator` exits immediately | Missing Python dependency | Check `docker compose logs orchestrator` |
| Vosk container crashes | Model not found | Verify `./models/vosk/model/` exists and is a valid Vosk model |
| Piper container crashes | Voice file missing | Verify `./voices/<PIPER_VOICE>.onnx` exists |
| `reply.wav` is silent / 880 Hz tone | STT/TTS stubs active | Expected until Wyoming clients are implemented |
| `curl /health` returns connection refused | Orchestrator not ready | Wait ~10 s; check `docker compose ps` |
| Qdrant port 6333 conflicts | Another service on 6333 | Change host port in `docker-compose.yml`: `"16333:6333"` |
| Valhalla slow startup | Large tile set | Wait for "Loaded graph" log line before sending requests |
| `sounddevice` error on Windows | No audio device | Install PortAudio: `pip install sounddevice` (includes PortAudio) |
| WebSocket `ConnectionRefusedError` | Orchestrator not running | Run `docker compose up` first |

---

## Stopping the Stack

```powershell
# Stop all containers (data volumes preserved)
docker compose down

# Stop and remove volumes (wipes Qdrant data)
docker compose down -v
```
