"""
RegLens Document Parser

Parsing hierarchy (best to fallback):
1. LlamaParse  — cloud VLM, best quality, requires LLAMA_CLOUD_API_KEY
2. Docling     — local AI/ML layout understanding, no API key, free
3. read_text() — plain text files only (.txt, .md)

Why Docling as the local parser:
- AI/ML layout understanding (DocLayNet model)
- Preserves table structure — critical for FATF matrices, Basel capital
  tables, and SADC framework comparison grids
- Handles multi-column layouts (common in regulator PDFs)
- Handles DOCX, PPTX, XLSX, HTML natively
- Outputs structured markdown — same format as LlamaParse
- Runs locally: no API cost, no network dependency, no corpus data
  leaving the regulator's environment
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional


# ============================================================
# LLAMAPARSE
# ============================================================

async def _parse_with_llamaparse(file_path: Path) -> Optional[str]:
    """
    Parse using LlamaParse cloud API.
    Best quality — VLM-based, handles scanned PDFs, nested tables,
    complex multi-column regulatory documents.
    Requires LLAMA_CLOUD_API_KEY in environment.
    Free tier: 10,000 pages/month at https://cloud.llamaindex.ai/
    """
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        return None

    try:
        from llama_parse import LlamaParse
        from llama_index.core import SimpleDirectoryReader

        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",     # preserves table and section structure
            num_workers=1,
            verbose=False,
            language="en",              # extend to "fr" / "pt" for francophone Africa
        )

        reader = SimpleDirectoryReader(
            input_files=[str(file_path)],
            file_extractor={file_path.suffix.lower(): parser},
        )
        documents = await reader.aload_data()

        if not documents:
            return None

        text = "\n\n".join(doc.text for doc in documents if doc.text.strip())
        return text.strip() or None

    except ImportError:
        # Not installed — skip silently, fall through to Docling
        return None
    except Exception as e:
        print(f"[parser] LlamaParse failed for {file_path.name}: {e}")
        return None


# ============================================================
# DOCLING
# ============================================================

def _parse_with_docling(file_path: Path) -> Optional[str]:
    """
    Parse using Docling — local AI/ML document understanding.
    No API key required. Runs entirely on the local machine.
    Supports: PDF, DOCX, PPTX, XLSX, HTML, MD, images, AsciiDoc.
    Install: pip install docling
    """
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result    = converter.convert(str(file_path))
        markdown  = result.document.export_to_markdown()

        return markdown.strip() or None

    except ImportError:
        print(
            f"[parser] Docling not installed — cannot parse {file_path.name}.\n"
            f"         Install with: pip install docling\n"
            f"         Docling is strongly recommended for regulatory PDFs."
        )
        return None
    except Exception as e:
        print(f"[parser] Docling failed for {file_path.name}: {e}")
        return None


# ============================================================
# PLAIN TEXT
# ============================================================

def _read_plain_text(file_path: Path) -> Optional[str]:
    """Read plain text files — no parsing needed."""
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore").strip() or None
    except Exception as e:
        print(f"[parser] Could not read {file_path.name}: {e}")
        return None


# ============================================================
# PUBLIC INTERFACE
# ============================================================

SUPPORTED_EXTENSIONS = {
    # Plain text — no parser needed
    ".txt", ".md",
    # Docling / LlamaParse handle all of these
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm",
}


async def parse_document(file_path: Path) -> str:
    """
    Parse any regulatory document and return clean text.

    Hierarchy:
      1. LlamaParse  (if LLAMA_CLOUD_API_KEY set)
      2. Docling     (local — recommended fallback)
      3. read_text   (plain text only)

    Returns empty string if parsing fails completely.
    Caller (ingest.py) should skip files with <50 words.
    """
    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        print(f"[parser] Unsupported extension: {suffix} — skipping {file_path.name}")
        return ""

    # Plain text — no parser needed
    if suffix in (".txt", ".md"):
        text = _read_plain_text(file_path)
        if text:
            print(f"[parser] read_text OK {file_path.name} ({len(text):,} chars)")
        return text or ""

    # All other formats: LlamaParse → Docling
    print(f"[parser] Parsing {file_path.name}...")

    text = await _parse_with_llamaparse(file_path)
    if text:
        print(f"[parser] LlamaParse OK {file_path.name} ({len(text):,} chars)")
        return text

    text = _parse_with_docling(file_path)
    if text:
        print(f"[parser] Docling OK {file_path.name} ({len(text):,} chars)")
        return text

    print(
        f"[parser] FAILED to parse {file_path.name}\n"
        f"         For PDFs: set LLAMA_CLOUD_API_KEY or pip install docling"
    )
    return ""


def get_parser_status() -> dict:
    """
    Check which parsers are available in the current environment.
    Call at startup or via CLI ('parsers' command) to diagnose capability.
    """
    status: dict = {
        "llamaparse": False,
        "docling":    False,
        "plain_text": True,     # always available
    }

    # Check LlamaParse
    try:
        import llama_parse  # noqa: F401
        api_key = os.getenv("LLAMA_CLOUD_API_KEY", "")
        status["llamaparse"] = bool(api_key)
        status["llamaparse_installed"] = True
        status["llamaparse_api_key_set"] = bool(api_key)
    except ImportError:
        status["llamaparse_installed"] = False
        status["llamaparse_api_key_set"] = False

    # Check Docling
    try:
        import docling  # noqa: F401
        status["docling"] = True
    except ImportError:
        status["docling"] = False

    # Best available
    if status["llamaparse"]:
        status["best_available"] = "llamaparse"
    elif status["docling"]:
        status["best_available"] = "docling"
    else:
        status["best_available"] = "plain_text_only"
        status["warning"] = (
            "No document parser available for PDFs. "
            "Install docling: pip install docling"
        )

    return status
