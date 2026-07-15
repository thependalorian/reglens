import pytest
from unittest.mock import AsyncMock, MagicMock
from agent.tools import discover_corpus_map, format_chunks_for_agent


def _mock_pool(rows):
    """asyncpg pool stub — fetch() resolves to the given rows."""
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=rows)
    pool.fetchval = AsyncMock(return_value=len(rows))   # chunk count query
    return pool


@pytest.mark.asyncio
async def test_discover_corpus_map_empty():
    """Empty corpus returns sensible defaults."""
    result = await discover_corpus_map(_mock_pool([]))

    assert result["document_count"]    == 0
    assert result["regulatory_bodies"] == ["Unknown"]
    assert result["domains"]           == ["General regulatory"]
    assert "coverage_summary" in result


@pytest.mark.asyncio
async def test_discover_corpus_map_with_documents():
    """Corpus map correctly aggregates document metadata."""
    rows = [
        {"document_uid": "1", "description": "EMIR Regulation",
         "metadata": {"regulatory_body": "ESMA", "domain": "derivatives"},
         "status": "active"},
        {"document_uid": "2", "description": "PSD2",
         "metadata": {"regulatory_body": "EBA", "domain": "payments"},
         "status": "active"},
        {"document_uid": "3", "description": "FATF Recommendations",
         "metadata": {"regulatory_body": "FATF", "domain": "AML/CFT"},
         "status": "active"},
    ]

    result = await discover_corpus_map(_mock_pool(rows))

    assert result["document_count"] == 3
    assert "ESMA" in result["regulatory_bodies"]
    assert "FATF" in result["regulatory_bodies"]
    assert "AML/CFT" in result["domains"]
    assert "payments" in result["domains"]


def test_format_chunks_empty():
    result = format_chunks_for_agent([])
    assert "No relevant" in result


def test_format_chunks_includes_metadata():
    chunks = [
        {
            "document_title":    "EMIR Regulation",
            "document_source":   "/data/emir.txt",
            "document_metadata": {"regulatory_body": "ESMA", "domain": "derivatives"},
            "content":           "Article 9(1) counterparties shall report...",
            "combined_score":    0.91,
        }
    ]
    result = format_chunks_for_agent(chunks)

    assert "SOURCE 1"       in result
    assert "EMIR Regulation" in result
    assert "ESMA"            in result
    assert "derivatives"     in result
    assert "Article 9(1)"   in result
