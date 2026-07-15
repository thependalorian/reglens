"""
Shared clients: Neon Postgres (asyncpg pool) + OpenAI-compatible clients.

DATABASE_URL points at the Neon project (pooled connection string).
statement_cache_size=0 is required behind Neon's pgbouncer pooler.
JSONB codec registered so metadata columns round-trip as dicts.
"""
from __future__ import annotations
import os
import json
import asyncpg
from openai import AsyncOpenAI

_pool: asyncpg.Pool | None = None
_embedding_client: AsyncOpenAI | None = None
_llm_client: AsyncOpenAI | None = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def get_pg_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=5,
            command_timeout=60,
            statement_cache_size=0,
            init=_init_connection,
        )
    return _pool


async def close_pg_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_embedding_client() -> AsyncOpenAI:
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = AsyncOpenAI(
            api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", "")),
            base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
        )
    return _embedding_client


def get_llm_client() -> AsyncOpenAI:
    """Raw OpenAI client for lightweight extraction calls (metadata, corpus discovery)."""
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        )
    return _llm_client
