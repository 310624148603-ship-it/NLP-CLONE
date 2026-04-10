# NNDL Voice Assistant — Architecture

## Overview

NNDL is an **offline, hands-free voice assistant** for Tamil Nadu drivers.
All services run locally (laptop or Android hotspot client) using Docker
containers — no cloud connectivity required.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       NNDL Voice Assistant Stack                         │
│                                                                          │
│  ┌───────────┐   Wake      ┌──────────────────────────────────────────┐  │
│  │ Microphone│──word ────► │          Orchestrator  :9000             │  │
│  │  (client) │  detect     │          (FastAPI / Python)              │  │
│  └───────────┘             │                                          │  │
│        ▲                   │  POST /gps  ──► GPS rolling trace (50pt) │  │
│        │  WAV              │  WS /ws/mic ──► Audio pipeline:          │  │
│        │  reply            │    PCM frames ► STT ► Intent ► TTS       │  │
│        │                   └──────────┬───────────────────────────────┘  │
│                                       │                                  │
│              ┌────────────────────────┼────────────────────────────┐     │
│              │                        │                            │     │
│              ▼                        ▼                            ▼     │
│   ┌─────────────────┐   ┌──────────────────────┐   ┌───────────────────┐│
│   │  openwakeword   │   │        vosk           │   │      piper        ││
│   │   Wyoming STT   │   │   Wyoming STT (ASR)   │   │  Wyoming TTS      ││
│   │    :10400       │   │      :10300           │   │    :10200         ││
│   └─────────────────┘   └──────────────────────┘   └───────────────────┘│
│                                       │                                  │
│              ┌────────────────────────┼────────────────────────────┐     │
│              │                        │                            │     │
│              ▼                        ▼                            ▼     │
│   ┌─────────────────┐   ┌──────────────────────┐                        │
│   │     qdrant      │   │      valhalla         │                        │
│   │  Vector DB/RAG  │   │  Map-matching/Speed   │                        │
│   │    :6333        │   │    :8002              │                        │
│   └─────────────────┘   └──────────────────────┘                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Port Reference Table

| Service        | Port  | Protocol | Description                              |
|----------------|-------|----------|------------------------------------------|
| orchestrator   | 9000  | HTTP/WS  | FastAPI coordinator (REST + WebSocket)   |
| openwakeword   | 10400 | TCP      | Wyoming wake-word detection              |
| vosk           | 10300 | TCP      | Wyoming offline speech-to-text           |
| piper          | 10200 | TCP      | Wyoming offline text-to-speech           |
| qdrant         | 6333  | HTTP     | Qdrant vector DB (REST API)              |
| qdrant (gRPC)  | 6334  | gRPC     | Qdrant gRPC interface                    |
| valhalla       | 8002  | HTTP     | Valhalla routing / speed-limit API       |

---

## Audio Format Specification

All audio in this stack uses a single canonical format to avoid resampling
overhead on constrained hardware:

| Parameter    | Value         |
|--------------|---------------|
| Sample rate  | 16 000 Hz     |
| Bit depth    | 16-bit signed |
| Channels     | 1 (mono)      |
| Encoding     | PCM little-endian |
| Frame size   | 640 bytes (= 320 samples = 20 ms) |

### Why 20 ms frames?
The Wyoming protocol and most ASR engines (Vosk, Whisper, Silero-VAD) work
optimally with 20 ms chunks.  openWakeWord also uses 80 ms windows composed
of four 20 ms frames.

---

## Data Flow Diagrams

### Audio Pipeline

```
Microphone (laptop)
       │
       │  640-byte binary WS frames (20 ms PCM)
       ▼
  ws://localhost:9000/ws/mic
       │
       │  (buffer until {"type":"end"} text frame)
       ▼
   transcribe_audio()   ──►  Wyoming Vosk :10300  ──►  text transcript
       │
       ▼
   [Intent / RAG]       ──►  Qdrant :6333         ──►  context passages
       │
       ▼
   create_wav_bytes()   ──►  Wyoming Piper :10200  ──►  WAV bytes
       │
       │  binary WS frame (WAV)
       ▼
  Client saves reply.wav + plays audio
```

### GPS Pipeline

```
Android phone (hotspot, 192.168.4.1)
       │
       │  POST /gps  {lat, lon, speed_mps, bearing, ts}
       ▼
   orchestrator :9000
       │
       │  50-point rolling deque
       ▼
   speed_limit lookup  ──►  Valhalla :8002  ──►  speed_kmh, road_type
```

---

## WebSocket Protocol Details

### Endpoint
`ws://<host>:9000/ws/mic`

### Client → Server

| Frame type | Content                      | Description                      |
|------------|------------------------------|----------------------------------|
| binary     | 640 bytes raw PCM            | One 20 ms audio frame            |
| text       | `{"type": "end"}`            | End-of-utterance signal          |

### Server → Client

| Frame type | Content                                          | Description            |
|------------|--------------------------------------------------|------------------------|
| text       | `{"type": "transcript", "text": "..."}` | Recognised transcript  |
| binary     | WAV file bytes                                   | TTS audio reply        |

### Example session

```
Client: [binary 640 bytes]  # frame 1
Client: [binary 640 bytes]  # frame 2
...
Client: [binary 640 bytes]  # frame N
Client: {"type": "end"}
Server: {"type": "transcript", "text": "what is the speed limit here"}
Server: [binary WAV bytes]
```

---

## Environment Variable Reference

These variables are set in `docker-compose.yml` for the orchestrator service.

| Variable             | Default         | Description                         |
|----------------------|-----------------|-------------------------------------|
| `OPENWAKEWORD_HOST`  | `openwakeword`  | Hostname of the wake-word service   |
| `OPENWAKEWORD_PORT`  | `10400`         | TCP port of the wake-word service   |
| `VOSK_HOST`          | `vosk`          | Hostname of the Vosk STT service    |
| `VOSK_PORT`          | `10300`         | TCP port of the Vosk STT service    |
| `PIPER_HOST`         | `piper`         | Hostname of the Piper TTS service   |
| `PIPER_PORT`         | `10200`         | TCP port of the Piper TTS service   |
| `QDRANT_HOST`        | `qdrant`        | Hostname of the Qdrant vector DB    |
| `QDRANT_PORT`        | `6333`          | HTTP port of Qdrant                 |
| `VALHALLA_HOST`      | `valhalla`      | Hostname of the Valhalla service    |
| `VALHALLA_PORT`      | `8002`          | HTTP port of Valhalla               |
| `LOG_LEVEL`          | `info`          | Uvicorn log level                   |

---

## Android Hotspot Note

When running from a phone hotspot (e.g. during in-car testing on NH-48),
the laptop typically receives the IP `192.168.4.1` from the Android hotspot.
Update the client URL accordingly:

```bash
python scripts/mic_client.py --url ws://192.168.4.1:9000/ws/mic
```

The `docker-compose.yml` services communicate via the internal `va_net`
bridge network — only the orchestrator's port 9000 needs to be reachable
from external clients.

---

## Roadmap / TODOs

| # | Item                                                        | Priority |
|---|-------------------------------------------------------------|----------|
| 1 | Wire `stt.py` to Wyoming Vosk (TCP socket, Wyoming protocol) | High     |
| 2 | Wire `tts.py` to Wyoming Piper (replace 880 Hz stub)        | High     |
| 3 | Wire `wake.py` to Wyoming openWakeWord                       | High     |
| 4 | Implement RAG embedding + Qdrant upsert/search in `rag.py`  | Medium   |
| 5 | Wire `speed_limit.py` to Valhalla `/locate` API             | Medium   |
| 6 | Add Tamil language support (Vosk Tamil model + Piper voice)  | Medium   |
| 7 | Android mic client app (Kotlin + WebSocket)                 | Low      |
| 8 | BLE mesh broadcast of hazard alerts                         | Low      |
| 9 | GPS-triggered speed warnings using rolling trace            | Low      |
