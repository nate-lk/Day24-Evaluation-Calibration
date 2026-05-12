"""Shared configuration for Lab 18."""

import os
from typing import Any
from dotenv import load_dotenv

# Force override environment variables with .env values
load_dotenv(override=True)

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "").strip()

# For backwards compatibility with scripts that expect CURSOR_API_KEY
CURSOR_API_KEY = OPENAI_API_KEY 

def lab24_chat_model() -> str:
    return os.getenv("LAB24_CHAT_MODEL", "gpt-4o-mini").strip()

def lab24_embedding_model() -> str:
    return os.getenv("LAB24_EMBEDDING_MODEL", "text-embedding-3-small").strip()

def openai_sdk_kwargs() -> dict[str, Any]:
    return {"api_key": OPENAI_API_KEY}

def chat_openai_llm(temperature: float = 0):
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=lab24_chat_model(),
        temperature=temperature,
        api_key=OPENAI_API_KEY
    )

def lab24_openai_embeddings():
    from langchain_openai import OpenAIEmbeddings
    return OpenAIEmbeddings(
        model=lab24_embedding_model(),
        api_key=OPENAI_API_KEY
    )

# --- Qdrant ---
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "lab18_production"
NAIVE_COLLECTION = "lab18_naive"

# --- Embedding ---
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# --- Chunking ---
HIERARCHICAL_PARENT_SIZE = 2048
HIERARCHICAL_CHILD_SIZE = 256
SEMANTIC_THRESHOLD = 0.85

# --- Search ---
BM25_TOP_K = 20
DENSE_TOP_K = 20
HYBRID_TOP_K = 20
RERANK_TOP_K = 3

# --- Paths ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TEST_SET_PATH = os.path.join(os.path.dirname(__file__), "test_set.json")
