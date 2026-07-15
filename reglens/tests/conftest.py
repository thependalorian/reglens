"""
Test bootstrap: load .env when present, otherwise stub the LLM keys so
agent modules (which construct Pydantic AI agents at import time) can be
imported without real credentials.
"""
import os
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("EMBEDDING_API_KEY", "test-key")
