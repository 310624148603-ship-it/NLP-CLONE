"""
orchestrator/app/tools/rag.py
==============================
Retrieval-Augmented Generation (RAG) stub backed by Qdrant.

In production this module will:
1. Embed the driver's query with a small on-device embedding model (e.g.
   sentence-transformers/all-MiniLM-L6-v2 via ONNX Runtime).
2. Query the Qdrant collection for the top-k most similar document chunks.
3. Return the retrieved context strings to the orchestrator for inclusion
   in the LLM prompt.

TODO: Implement real embedding + Qdrant retrieval.
      Reference: https://qdrant.tech/documentation/
"""

from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger(__name__)

_HOST = os.getenv("QDRANT_HOST", "qdrant")
_PORT = int(os.getenv("QDRANT_PORT", "6333"))
_COLLECTION = os.getenv("QDRANT_COLLECTION", "tn_driver_kb")


async def query_rag(query: str, top_k: int = 3) -> List[str]:
    """
    Retrieve the top-k context passages relevant to *query*.

    Parameters
    ----------
    query:
        The driver's natural-language query or recognised utterance.
    top_k:
        Number of context passages to retrieve (default 3).

    Returns
    -------
    List[str]
        A list of context string snippets.  Empty list on error.

    Notes
    -----
    This is currently a **stub** that returns dummy results.  Wire in the
    Qdrant client (``pip install qdrant-client``) pointing at
    ``http://{_HOST}:{_PORT}`` to enable real vector search.
    """
    # TODO: Embed query, call Qdrant collection _COLLECTION, return real results
    logger.warning(
        "rag.query_rag() is a stub — returning dummy context. "
        "Wire in Qdrant at %s:%s (collection=%r) for real RAG.",
        _HOST,
        _PORT,
        _COLLECTION,
    )

    return [
        "[STUB] Tamil Nadu Motor Vehicles Act Section 112 — speed limits on different road types.",
        "[STUB] Highway Code of India — overtaking rules and safe following distance.",
        f"[STUB] Query was: {query!r}",
    ]
