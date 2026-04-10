"""
Qdrant RAG retrieval stub.

TODO: Replace with a real Qdrant client that embeds the query and performs
      a nearest-neighbour search over the ``knowledge`` collection.
"""

from __future__ import annotations

import logging
import os
from typing import List

logger = logging.getLogger("rag")

QDRANT_URL: str = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = "knowledge"
TOP_K = 3


async def retrieve(query: str) -> List[str]:
    """
    Return the top-k text chunks most relevant to *query*.

    Parameters
    ----------
    query:
        Natural-language question or statement from the driver.

    Returns
    -------
    List[str]
        Ranked list of relevant text passages.  Currently always empty.

    Notes
    -----
    Swap-in plan:
      1. Install ``qdrant-client`` and add it to requirements.txt.
      2. Create an async ``QdrantClient(url=QDRANT_URL)``.
      3. Embed *query* with a small sentence-transformer model.
      4. Call ``client.search(COLLECTION_NAME, query_vector=embedding, limit=TOP_K)``.
      5. Return the ``payload["text"]`` field from each result.
    """
    logger.debug("rag.retrieve() stub called with query=%r (QDRANT_URL=%s)", query, QDRANT_URL)
    # TODO: implement Qdrant retrieval
    return []
