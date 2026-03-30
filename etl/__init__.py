"""
etl/__init__.py
SmartSalai Edge-Sentinel — Persona 6: ETL Data Scavenger
Package: edge_sentinel.etl

Stages:
  1. pdf_extractor.py     → raw text extraction (pdfplumber + Tesseract OCR fallback)
  2. text_chunker.py      → section-aware legal chunking
  3. embedder.py          → local ONNX-INT8 vector generation
  4. sqlite_vss_ingestor.py → Edge-RAG SQLite-VSS persistence
  5. pipeline.py          → orchestrator (directory watcher + ordered stage execution)

ZERO cloud API calls. All inference on-device.
"""

from .pipeline import ETLPipeline

__all__ = ["ETLPipeline"]
__version__ = "0.1.0"
