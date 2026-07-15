"""
LLM-based regulatory metadata extraction.
Called once per document during ingestion.
Uses mini model + 200 token limit — cost-efficient.
This is what makes RegLens adaptive: every document is annotated
with its regulatory context, enabling corpus-wide discovery later.
"""
from __future__ import annotations
import json
import os
from openai import AsyncOpenAI
from agent.prompts import DOCUMENT_METADATA_EXTRACTION_PROMPT


async def extract_document_metadata(
    client:    AsyncOpenAI,
    content:   str,
    file_name: str = "",
) -> dict:
    """
    Extract regulatory metadata from document using lightweight LLM call.
    Samples first 3000 chars only — cost control.
    Returns dict with: regulatory_body, domain, document_type,
                       regulatory_level, obligations_present
    """
    sample = content[:3000].strip()
    if not sample:
        return _empty_metadata()

    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM_CHOICE", "gpt-4o-mini"),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{DOCUMENT_METADATA_EXTRACTION_PROMPT}\n\n"
                        f"Document filename: {file_name}\n\n"
                        f"Document excerpt:\n{sample}"
                    ),
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.0,
        )
        raw = response.choices[0].message.content or "{}"
        meta = json.loads(raw)

        # Validate and normalise keys
        supersedes = meta.get("supersedes")
        return {
            "regulatory_body":   str(meta.get("regulatory_body", "Unknown"))[:200],
            "domain":            str(meta.get("domain", "general"))[:100],
            "document_type":     str(meta.get("document_type", "unknown"))[:100],
            "regulatory_level":  str(meta.get("regulatory_level", "unknown"))[:100],
            "obligations_present": bool(meta.get("obligations_present", False)),
            "publication_date":  str(meta.get("publication_date", "unknown"))[:20],
            "language":          str(meta.get("language", "unknown"))[:10],
            "supersedes":        str(supersedes)[:300] if supersedes else None,
        }
    except Exception as e:
        print(f"[extractor] metadata extraction failed for '{file_name}': {e}")
        return _empty_metadata()


def _empty_metadata() -> dict:
    return {
        "regulatory_body":    "Unknown",
        "domain":             "general",
        "document_type":      "unknown",
        "regulatory_level":   "unknown",
        "obligations_present": False,
        "publication_date":   "unknown",
        "language":           "unknown",
        "supersedes":         None,
    }