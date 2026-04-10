# Architecture — Offline Voice Assistant for Tamil Nadu Drivers

## Overview

This system runs entirely on a Windows laptop (Docker Desktop) and provides a
hands-free, voice-activated assistant for drivers. All speech processing
happens locally — no internet connection is required at runtime.

---

## Component Diagram

```
  ┌──────────────────────────────────────────────────────────────┐
  │                        Docker Host                           │
  │                                                              │
  │  ┌────────────────┐    ┌────────────────┐                    │
  │  │  openwakeword  │    │      vosk      │                    │
  │  │  (Wyoming)     │    │  (Wyoming STT) │                    │
  │  │  port 10400    │    │  port 10300    │                    │
  │  └───────┬────────┘    └───────┬────────┘                    │
  │          │ wake event          │ transcript                  │
  │          ▼                     ▼                             │
  │  ┌──────────────────────────────────────────────────────┐    │
  │  │               orchestrator  (FastAPI)                │    │
  │  │               port 9000                              │    │
  │  │                                                      │    │
  │  │   /health   /gps   /ws/mic                          │    │
  │  └────┬──────────────────────────┬─────────────────────┘    │
  │       │                          │                           │
  │       ▼                          ▼                           │
  │  ┌──────────┐            ┌───────────────┐                   │
  │  │  piper   │            │    qdrant     │                   │
  │  │  (TTS)   │            │  (vector DB)  │                   │
  │  │ port 10200│           │  port 6333    │                   │
  │  └──────────┘            └───────────────┘                   │
  │                                                              │
  │  ┌──────────────────────┐                                    │
  │  │      valhalla        │                                    │
  │  │  (offline routing)   │                                    │
  │  │  port 8002           │                                    │
  │  └──────────────────────┘                                    │
  └──────────────────────────────────────────────────────────────┘

  External clients
  ────────────────
  Laptop browser / Python script ──► ws://localhost:9000/ws/mic
  Android thin client (Phase 2)  ──► ws://192.168.4.1:9000/ws/mic
```

---

## Port Table

| Service        | Port  | Protocol  | Purpose                          |
|----------------|-------|-----------|----------------------------------|
| openwakeword   | 10400 | TCP (Wyoming) | Wake-word detection ("hey jarvis") |
| vosk           | 10300 | TCP (Wyoming) | Offline speech-to-text           |
| piper          | 10200 | TCP (Wyoming) | Neural text-to-speech            |
| qdrant         | 6333  | HTTP/gRPC | Vector database for RAG          |
| valhalla       | 8002  | HTTP      | Map-matching & routing           |
| orchestrator   | 9000  | HTTP/WS   | FastAPI coordinator              |

---

## Data Flows

### Voice I/O (WebSocket `/ws/mic`)

```
Android / laptop mic
        │
        │  640-byte PCM frames (20 ms each)
        ▼
  orchestrator  ──► vosk  ──► transcript text
        │
        ├──► qdrant  ──► relevant context (RAG)
        ├──► valhalla ──► speed limit / road info
        │
        ▼
  piper / TTS stub  ──► WAV bytes
        │
        ▼
  client plays audio
```

### GPS Updates (`POST /gps`)

```
GPS source (Android / NMEA)
        │
        │  JSON: {lat, lon, speed_mps, bearing, ts}
        ▼
  orchestrator  stores last fix + 50-point rolling trace
        │
        └──► valhalla trace_attributes  ──► speed limit
```

---

## Audio Format Specification

| Parameter   | Value            |
|-------------|------------------|
| Sample rate | 16 000 Hz        |
| Bit depth   | 16-bit signed    |
| Channels    | 1 (mono)         |
| Frame size  | 640 bytes (20 ms)|
| Container   | Raw PCM (upstream) / WAV (downstream) |

---

## Hotspot / Android Connection

When the laptop creates a Wi-Fi hotspot, Android devices connect to
`192.168.4.1`. The orchestrator WebSocket is reachable at:

```
ws://192.168.4.1:9000/ws/mic
```

GPS data is POSTed to `http://192.168.4.1:9000/gps`.

---

## Roadmap / TODOs

- [ ] Wire `app/stt.py` to the Wyoming Vosk TCP service
- [ ] Wire `app/tts.py` to the Wyoming Piper TCP service
- [ ] Wire `app/wake.py` to the Wyoming OpenWakeWord TCP service
- [ ] Implement `app/tools/rag.py` Qdrant retrieval with sentence-transformers
- [ ] Implement `app/tools/speed_limit.py` Valhalla trace_attributes call
- [ ] Add LLM reasoning layer (local Ollama / llama.cpp)
- [ ] Android thin client (Phase 2)
- [ ] Tamil language Vosk + Piper voice support
