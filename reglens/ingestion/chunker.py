from __future__ import annotations
from typing import List


def chunk_document(
    text:       str,
    chunk_size: int = 800,
    overlap:    int = 150,
) -> List[str]:
    """
    Paragraph-aware chunking with word overlap.
    Regulatory documents benefit from paragraph boundaries as natural chunk edges.
    Preserves numbered article/section structure where possible.
    """
    # Split on double newlines (paragraph breaks) as primary boundary
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[str] = []
    current_words: List[str] = []

    for para in paragraphs:
        words = para.split()
        if not words:
            continue

        if current_words and len(current_words) + len(words) > chunk_size:
            chunk_text = " ".join(current_words)
            if len(chunk_text.split()) > 20:
                chunks.append(chunk_text)
            # Overlap: keep tail of previous chunk
            current_words = current_words[-overlap:] + words
        else:
            current_words.extend(words)

    # Final chunk
    if current_words:
        chunk_text = " ".join(current_words)
        if len(chunk_text.split()) > 20:
            chunks.append(chunk_text)

    return chunks