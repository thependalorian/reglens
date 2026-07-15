from __future__ import annotations
import os
from typing import List
from openai import AsyncOpenAI


async def embed_chunks(
    client:     AsyncOpenAI,
    chunks:     List[str],
    batch_size: int = 20,
) -> List[List[float]]:
    """Batch embed chunks. Respects API rate limits via batching."""
    model        = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    all_embeddings: List[List[float]] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        resp  = await client.embeddings.create(model=model, input=batch)
        all_embeddings.extend(r.embedding for r in resp.data)
        done = min(i + batch_size, len(chunks))
        print(f"[embed] {done}/{len(chunks)} chunks embedded")

    return all_embeddings