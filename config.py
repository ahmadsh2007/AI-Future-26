"""Central configuration. Every value can be overridden with an environment variable,
so on hackathon day you only need e.g.:  LLM_MODEL=qwen3:8b python rag_pipeline.py "..."
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- paths
DOCS_DIR = Path(os.getenv("DOCS_DIR", BASE_DIR / "data" / "raw_docs"))
VECTOR_DB_DIR = Path(os.getenv("VECTOR_DB_DIR", BASE_DIR / "data" / "vector_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "arabic_docs")

# ---------------------------------------------------------------- embedding model
# BAAI/bge-m3 (default) - no prefixes needed, strong Arabic.
# intfloat/multilingual-e5-large - also good, needs "query: " / "passage: " prefixes (auto-handled below).
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "")  # "" = auto (cuda / mps / cpu)
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))
EMBED_MAX_SEQ_LENGTH = int(os.getenv("EMBED_MAX_SEQ_LENGTH", "512"))

_IS_E5 = "e5" in EMBED_MODEL.lower()
QUERY_PREFIX = os.getenv("QUERY_PREFIX", "query: " if _IS_E5 else "")
PASSAGE_PREFIX = os.getenv("PASSAGE_PREFIX", "passage: " if _IS_E5 else "")

# ---------------------------------------------------------------- optional reranker
# Re-orders the retrieved chunks (does NOT affect the similarity threshold).
USE_RERANKER = os.getenv("USE_RERANKER", "0") == "1"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

# ---------------------------------------------------------------- chunking (characters)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "700"))
CHUNK_OVERLAP_SENTENCES = int(os.getenv("CHUNK_OVERLAP_SENTENCES", "1"))
MIN_CHUNK_CHARS = int(os.getenv("MIN_CHUNK_CHARS", "40"))

# ---------------------------------------------------------------- retrieval
TOP_K = int(os.getenv("TOP_K", "5"))
# Cosine similarity (0..1). If the BEST chunk is below SIM_THRESHOLD the LLM is never called.
# Scores are embedding-model specific, so defaults are chosen per model (measured on the test corpus):
#   bge-m3   : off-topic <= 0.51, real questions 0.62-0.93  -> 0.55
#   e5-large : off-topic <= 0.77, real questions 0.84-0.93  -> 0.80 (e5 scores are compressed into ~0.7-0.95)
# Env vars always win. For a NEW model / corpus calibrate with:  python rag_pipeline.py --calibrate
_THRESHOLD_DEFAULTS = {"e5": (0.80, 0.75), "bge-m3": (0.55, 0.45)}  # (SIM_THRESHOLD, CONTEXT_MIN_SIM)
_default_thr = next((v for k, v in _THRESHOLD_DEFAULTS.items() if k in EMBED_MODEL.lower()), (0.55, 0.45))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", _default_thr[0]))
# Chunks below this are not passed to the LLM as context (keeps the prompt clean).
CONTEXT_MIN_SIM = float(os.getenv("CONTEXT_MIN_SIM", _default_thr[1]))

# ---------------------------------------------------------------- LLM
# LLM_BACKEND: "ollama" | "openai" (vLLM / LM Studio / llama.cpp server) | "hf" (transformers)
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "command-r7b-arabic:7b")  # ollama tag, OpenAI model name, or HF repo/local path
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")  # openai backend only
LLM_API_KEY = os.getenv("LLM_API_KEY", "EMPTY")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_NEW_TOKENS = int(os.getenv("LLM_MAX_NEW_TOKENS", "300"))
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))  # ollama context window
LLM_THINK_TOKENS = int(os.getenv("LLM_THINK_TOKENS", "1500"))  # budget when thinking mode is used (gov_bot fee questions)

# Prompt language: "ar" (Arabic system prompt) or "en" (English system prompt, Arabic answer).
# Try both on the day with the real model - whichever refuses more reliably wins.
PROMPT_LANG = os.getenv("PROMPT_LANG", "ar")

# ---------------------------------------------------------------- fallback answer
IDK_ANSWER = "لا أعرف"
