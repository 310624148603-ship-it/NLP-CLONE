# Changelog — SmartSalai Edge-Sentinel
> Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
> Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)  
> Persona responsible for maintenance: **P5 (DevOps & CI/CD Commander)**

---

## [Unreleased]

---

## [0.1.0] — 2026-03-31

### Added — P1 (Decentralized Architect)
- `schemas/universal_legal_schema.json` v1.0.0: jurisdiction-swappable offence ontology
  - `IN_SEC_194D`: Sec 194D MVA 2019 — Helmet violation; TN pillion-rider mandate (G.O.(Ms).No.56/2022); penalty INR 1000/2000; IDD class `rider_no_helmet`; min confidence 0.82; min 3 evidence frames
  - `IN_SEC_183`: Sec 183 MVA 2019 — Speeding; TN speed-zone thresholds (urban 50, SH-2W 80, EX-2W 100, school 25 km/h); GPS + IMU-TCN fusion; Section 208 trigger flag
  - `IN_SEC_177`: Sec 177 MVA 2019 — General violation; INR 500/1500
  - `section_208_protocol`: Auto-audit-request template with SHA3-256 evidence hashing
  - `jurisdiction_swap_targets.UK_RTA_1988`: hot-swap stub mapping to Road Traffic Act 1988

### Added — P3 (Edge-Vision & Kinetic Engineer)
- `agents/imu_near_miss_detector.py` v0.1.0
  - `IMUBuffer`: circular buffer for 3-axis accelerometer + gyroscope at 100 Hz (numpy ring-buffer, zero heap allocation in hot-path)
  - `TCNNearMissDetector`: 3-layer Temporal Convolutional Network; receptive field 120 samples (1.2 s); channels [64, 128, 64]; kernel size 3; dropout 0.2
  - Feature extraction: RMS-jerk (X,Y,Z), lateral-G peak, yaw-rate delta, TTC-proxy from longitudinal deceleration gradient
  - Inference: PyTorch forward pass → ONNX Runtime INT8 export hook
  - `NearMissEvent` dataclass: severity enum {CRITICAL, HIGH, MEDIUM}, timestamp_epoch_ms, gps_lat/lon placeholders, irad_category_code V-NMS-01
  - Calibration: `calibrate_gravity()` — 1 s static sample mean subtraction

### Added — P6 (ETL Data Scavenger)
- Full 5-stage ETL pipeline (`etl/`):
  - `pdf_extractor.py`: Hybrid pdfplumber + Tesseract OCR extraction.
  - `text_chunker.py`: Section-aware hierarchical legal chunking.
  - `embedder.py`: Multi-mode offline embedding (ONNX INT8, ST FP32, Hash).
  - `sqlite_vss_ingestor.py`: Vector persistence for Edge-RAG.
  - `pipeline.py`: Unified orchestrator.

### Added — P5 (DevOps & CI/CD Commander)
- `tasks.md`: Added fixed deadlines (72h MVP, 6w Production).
- `raw_data/`: Seeded directory for incoming PDF statutes.

### Changed
- `README.md`: Replaced generic stub with SmartSalai Edge-Sentinel project documentation

### Security
- All telemetry schemas annotated with ZKP-required fields; NO plaintext PII fields defined in any schema

---

## [0.0.1] — 2026-03-30

### Added
- Initial Git repository initialization (`Gokzz-glitch/NLP`)
- Empty `schemas/` directory stub
