# SmartSalai Edge-Sentinel — Task Board
> **Project**: IIT Madras CoERS Hackathon 2026  
> **Schema**: `tasks.md v0.1.0`  
> **Maintainer**: Persona 5 (DevOps & CI/CD Commander)  
> **Last Updated**: 2026-03-31T00:05:07+05:30

---

## Legend
| State | Symbol | Meaning |
|---|---|---|
| `TODO` | ⬜ | Defined, not started |
| `IN-PROGRESS` | 🟡 | Active execution |
| `BLOCKED` | 🔴 | Dependency unresolved — see blocker note |
| `DONE` | ✅ | Merged, tested, logged in CHANGELOG |

---

## SPRINT 0 — Repository Initialization & Core Schema
**TARGET: [2026-03-31 T 12:00:00]** | **STATE: 100% COMPLETE**

| ID | Task | Owner | State | Blocker / Notes |
|---|---|---|---|---|
| T-001 | Initialize Git repository and project scaffolding | P5 | ✅ DONE | Repo at `Gokzz-glitch/NLP` |
| T-002 | Author `tasks.md` Kanban board (this file) | P5 | ✅ DONE | — |
| T-003 | Author `CHANGELOG.md` (Keep-a-Changelog standard) | P5 | ✅ DONE | — |
| T-004 | Define `schemas/universal_legal_schema.json` — Sec 194D + 183 + TN GOs | P1 | ✅ DONE | Validated against S.O. 2224(E) + TN G.O.(Ms).No.56/2022 |
| T-005 | Author `agents/imu_near_miss_detector.py` (TCN sensor fusion) | P3 | ✅ DONE | ONNX export hook included |
| T-006 | Define project directory structure + `__init__ stubs` | P5 | ✅ DONE | — |
| T-007 | Author `README.md` project overview | P5 | ✅ DONE | — |
| T-021 | Author `etl/` pipeline (Stages 1-4) | P6 | ✅ DONE | OCR, Chunking, Embedding, Ingestion complete. |

---

## SPRINT 1 — Agent Core Implementation
**TARGET: [2026-04-03 T 00:00:00 (MVP)]** | **STATE: 5% COMPLETE**

| ID | Task | Owner | State | Blocker / Notes |
|---|---|---|---|---|
| T-008 | BLE Mesh hazard-share protocol (`agents/ble_mesh_broker.py`) | P1 | ⬜ TODO | Requires Android BLE GATT server permissions spec |
| T-009 | YOLOv8-nano sign-audit pipeline (`agents/sign_auditor.py`) | P3 | ⬜ TODO | Weights: IDD-trained ONNX INT8. ERR_DATA_MISSING: IDD YOLOv8 checkpoint URL |
| T-010 | RAG pipeline for MVA statute retrieval (`agents/legal_rag.py`) | P2 | ⬜ TODO | Requires llama.cpp GGUF 4-bit LLM (Gemma-2B-Indic or equivalent) |
| T-011 | Section 208 Audit-Request auto-drafter (`agents/sec208_drafter.py`) | P2 | ⬜ TODO | Blocked on T-010 (RAG) + T-009 (sign detection) |
| T-012 | Bhashini/IndicTrans2 TTS voice interface (`agents/acoustic_ui.py`) | P4 | ⬜ TODO | ERR_DATA_MISSING: Bhashini offline model package path |
| T-013 | JSON-RPC inter-agent message bus (`core/agent_bus.py`) | P1 | ⬜ TODO | Must be event-loop safe (asyncio) |
| T-014 | ZKP telemetry envelope (`core/zkp_envelope.py`) | P1 | ⬜ TODO | Candidate: Pedersen Commitment over secp256k1 |
| T-015 | iRAD-schema telemetry serializer (`core/irad_serializer.py`) | P3 | ⬜ TODO | IRAD field spec: MoRTH circular 2022 |

---

## SPRINT 2 — Integration & Validation

| ID | Task | Owner | State | Blocker / Notes |
|---|---|---|---|---|
| T-016 | End-to-end pipeline integration test (offline, no cloud) | P5 | ⬜ TODO | Blocked on T-008..T-015 |
| T-017 | NPU benchmark: latency profiling on Android mid-range (Dimensity 700 class) | P3 | ⬜ TODO | ERR_DATA_MISSING: Target device ADB profile |
| T-018 | YOLOv8-nano frame-rate validation ≥10 FPS @ INT8 | P3 | ⬜ TODO | Blocked on T-009, T-017 |
| T-019 | Voice interrupt sub-100ms latency test | P4 | ⬜ TODO | Blocked on T-012 |
| T-020 | Section 208 legal review by mock RTO schema | P2 | ⬜ TODO | Blocked on T-011 |

---

## BLOCKED — Pending External Data

| ID | Missing Node | Assigned | Impact |
|---|---|---|---|
| ERR-001 | IDD YOLOv8-nano ONNX INT8 checkpoint download URI | P3 | T-009, T-018 |
| ERR-002 | Bhashini offline TTS model package path / APK | P4 | T-012, T-019 |
| ERR-003 | Target Android device ADB fingerprint for NPU profiling | P3 | T-017, T-018 |
