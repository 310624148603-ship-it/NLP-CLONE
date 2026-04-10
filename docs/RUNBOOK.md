# NNDL Voice Assistant — Operations Runbook

## Prerequisites

| Requirement          | Version / Notes                                      |
|----------------------|------------------------------------------------------|
| OS                   | Windows 10/11 (22H2+) or Ubuntu 22.04+               |
| Docker Desktop       | 4.20+ with WSL 2 backend (Windows) or Docker Engine 24+ (Linux) |
| Python               | 3.9 or later                                         |
| RAM                  | ≥ 8 GB (16 GB recommended for all 6 services)        |
| Disk                 | ≥ 4 GB free (models + images)                        |
| Microphone           | Any USB or built-in mic supported by sounddevice     |

---

## Step-by-Step Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Gokzz-glitch/NNDL.git
cd NNDL
```

### Step 2 — Create Required Directory Structure

These directories are excluded from git (see `.gitignore`) but must exist
before starting the stack:

```bash
# STT model
mkdir -p models/vosk

# TTS voices
mkdir -p voices

# Valhalla map tiles
mkdir -p data/valhalla_tiles
```

### Step 3 — Download the Vosk Speech Model

1. Visit [https://alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)
2. Download a model appropriate for your language:
   - English (small, ~40 MB): `vosk-model-small-en-us-0.15`
   - Tamil (if available): search for `vosk-model-ta`
3. Extract the ZIP so that the directory structure is:
   ```
   models/vosk/model/          ← this exact path is mounted by docker-compose
   models/vosk/model/am/
   models/vosk/model/conf/
   models/vosk/model/graph/
   ...
   ```

> **Windows tip:** Use 7-Zip or the built-in Explorer ZIP extractor.
> Make sure you don't end up with a double-nested folder like
> `models/vosk/vosk-model-small-en-us-0.15/model/`.

### Step 4 — Download a Piper Voice

1. Visit [https://github.com/rhasspy/piper/releases](https://github.com/rhasspy/piper/releases)
2. Download a `.onnx` voice file and its matching `.onnx.json` config, e.g.:
   - `en_US-lessac-medium.onnx`
   - `en_US-lessac-medium.onnx.json`
3. Place both files in `./voices/`:
   ```
   voices/
   ├── en_US-lessac-medium.onnx
   └── en_US-lessac-medium.onnx.json
   ```

### Step 5 — Build and Start the Docker Stack

```bash
docker compose up --build
```

On first run, Docker will pull base images and build the orchestrator.
This may take 5–10 minutes depending on internet speed.

To run in detached (background) mode:
```bash
docker compose up --build -d
```

### Step 6 — Verify All Services Are Running

Wait ~30 seconds for all containers to initialise, then:

```bash
# Check orchestrator health
curl http://localhost:9000/health

# Expected output:
# {"status":"ok","services":{...},"gps_trace_length":0}

# Check Qdrant
curl http://localhost:6333/healthz

# Check Valhalla
curl http://localhost:8002/status
```

To see running containers:
```bash
docker compose ps
```

All 6 containers should show `Up` or `healthy` status.

### Step 7 — Install Mic Client Dependencies

```bash
pip install sounddevice websocket-client numpy soundfile
```

> **Windows note:** If `sounddevice` fails to install, install PortAudio first:
> Download the pre-built wheel from [https://www.lfd.uci.edu/~gohlke/pythonlibs/](https://www.lfd.uci.edu/~gohlke/pythonlibs/)
> or use: `pip install sounddevice` (it bundles PortAudio on Windows).

### Step 8 — Run the Mic Client

```bash
python scripts/mic_client.py --sec 4
```

This will:
1. Record 4 seconds from your default microphone
2. Stream 20 ms PCM frames to `ws://localhost:9000/ws/mic`
3. Display the transcript received from the server
4. Save the TTS reply to `reply.wav`
5. Attempt to play `reply.wav` through your speakers

Other options:
```bash
# Record 8 seconds
python scripts/mic_client.py --sec 8

# Use a custom orchestrator URL (e.g., Android hotspot)
python scripts/mic_client.py --url ws://192.168.4.1:9000/ws/mic

# Save reply to a different file
python scripts/mic_client.py --save output/my_reply.wav

# Skip audio playback
python scripts/mic_client.py --no-play
```

---

## Troubleshooting

| Symptom                        | Likely Cause                        | Resolution                                                          |
|--------------------------------|-------------------------------------|---------------------------------------------------------------------|
| **Docker containers won't start** | Docker Desktop not running or WSL 2 not enabled | Start Docker Desktop; enable WSL 2 integration in Settings → Resources → WSL Integration |
| **Vosk model not found** | `models/vosk/model/` is empty or wrongly structured | Re-read Step 3; check that `models/vosk/model/am/` exists |
| **WebSocket connection refused** | Orchestrator not yet healthy | Wait 30 s then retry; run `docker compose logs orchestrator` |
| **Microphone not detected** | Wrong device index or no PortAudio | Run `python -c "import sounddevice; print(sounddevice.query_devices())"` to list devices |
| **Out of memory** | All 6 containers competing for RAM | Increase Docker memory limit in Docker Desktop → Settings → Resources; or shut down unused services with `docker compose stop <name>` |
| **Port already in use** | Another service is bound to the same port | `netstat -ano | findstr :<port>` (Windows) or `lsof -i :<port>` (Linux) to find the conflicting process |
| **Piper TTS not responding** | No voice files in `./voices/` | Follow Step 4 to download a voice; restart with `docker compose restart piper` |
| **Valhalla returns 404** | No tiles in `./data/valhalla_tiles/` | Download Tamil Nadu OSM PBF and run Valhalla tile build (see Valhalla docs) |
| **`reply.wav` is a sine wave** | STT/TTS stubs still active | The stubs are placeholders until Wyoming clients are wired in; see `TODO` comments in `orchestrator/app/stt.py` and `orchestrator/app/tts.py` |

---

## Testing Checklist

- [ ] `docker compose ps` shows 6 containers in `Up` / `healthy` state
- [ ] `curl http://localhost:9000/health` returns `{"status":"ok",...}`
- [ ] `curl http://localhost:6333/healthz` returns `{"title":"qdrant - ok",...}`
- [ ] `curl http://localhost:8002/status` returns a JSON status object
- [ ] `python scripts/mic_client.py --sec 4` completes without errors
- [ ] `reply.wav` is created and is a valid WAV file
- [ ] Audio plays back (even if it is the placeholder sine wave)
- [ ] Transcript message is printed in the client output

---

## Port Reference Table

| Service        | Host Port | Container Port | Access URL                          |
|----------------|-----------|----------------|-------------------------------------|
| orchestrator   | 9000      | 9000           | http://localhost:9000/health        |
| orchestrator   | 9000      | 9000           | ws://localhost:9000/ws/mic          |
| openwakeword   | 10400     | 10400          | tcp://localhost:10400               |
| vosk           | 10300     | 10300          | tcp://localhost:10300               |
| piper          | 10200     | 10200          | tcp://localhost:10200               |
| qdrant         | 6333      | 6333           | http://localhost:6333               |
| qdrant gRPC    | 6334      | 6334           | grpc://localhost:6334               |
| valhalla       | 8002      | 8002           | http://localhost:8002               |

---

## Development Tips

### View logs for a specific service

```bash
docker compose logs -f orchestrator
docker compose logs -f vosk
```

### Restart a single service (e.g., after editing orchestrator code)

```bash
docker compose restart orchestrator
```

Or rebuild and restart:
```bash
docker compose up --build orchestrator
```

### Open a shell inside a running container

```bash
docker compose exec orchestrator bash
docker compose exec qdrant bash
```

### Stop all services and remove containers

```bash
docker compose down
```

### Stop and remove volumes (resets Qdrant data)

```bash
docker compose down -v
```

---

## Next Steps — Phase 2

1. **Wire STT** — Implement Wyoming client in `orchestrator/app/stt.py` to
   connect to the Vosk TCP server and perform real transcription.

2. **Wire TTS** — Implement Wyoming client in `orchestrator/app/tts.py` to
   use Piper for natural-sounding Tamil speech output.

3. **Wake-word activation** — Implement `orchestrator/app/wake.py` so that the
   mic pipeline starts only when "hey jarvis" is detected.

4. **RAG knowledge base** — Populate Qdrant with Tamil Nadu traffic law
   document chunks; wire `orchestrator/app/tools/rag.py` for real retrieval.

5. **Speed-limit alerts** — Download Tamil Nadu OSM tiles for Valhalla; wire
   `orchestrator/app/tools/speed_limit.py` to give real-time limit warnings.

6. **Android client** — Build a Kotlin app that streams mic audio from the
   driver's phone to the orchestrator over the Android hotspot.

7. **BLE mesh** — Broadcast hazard alerts to nearby vehicles using the
   BLE mesh protocol defined in `ble_mesh_protocol.json`.
