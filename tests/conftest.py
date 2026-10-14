import shutil
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import config  # noqa: E402


def ollama_models() -> set[str]:
    try:
        import ollama
        return {m.model for m in ollama.list().models}
    except Exception:
        return set()


@pytest.fixture(scope="session")
def pdf_path(tmp_path_factory):
    from make_arabic_pdf import make
    return make(tmp_path_factory.mktemp("pdf") / "oasis_report.pdf")


def _build_db(tmp_root: Path, name: str, pdf: Path, n_articles: int, embed_model: str | None = None):
    """Ingest PDF + articles into an isolated DB by patching config (ingest/rag read config at call time)."""
    import ingest
    articles = sorted((ROOT / "data" / "raw_docs").glob("article_*.txt"))[:n_articles]
    if not articles:
        pytest.fail("data/raw_docs/article_*.txt missing - run: python download_test_data.py")
    docs = tmp_root / f"docs_{name}"
    docs.mkdir()
    for a in articles:
        shutil.copy(a, docs)
    shutil.copy(pdf, docs / "oasis_report.pdf")

    mp = pytest.MonkeyPatch()
    mp.setattr(config, "VECTOR_DB_DIR", tmp_root / f"db_{name}")
    mp.setattr(config, "COLLECTION_NAME", f"test_{name}")
    if embed_model:
        is_e5 = "e5" in embed_model.lower()
        mp.setattr(config, "EMBED_MODEL", embed_model)
        mp.setattr(config, "QUERY_PREFIX", "query: " if is_e5 else "")
        mp.setattr(config, "PASSAGE_PREFIX", "passage: " if is_e5 else "")
        mp.setattr(config, "SIM_THRESHOLD", 0.80 if is_e5 else 0.55)
        mp.setattr(config, "CONTEXT_MIN_SIM", 0.75 if is_e5 else 0.45)
        mp.setattr(ingest, "_model", None)
    ids, texts, metas = ingest.build_chunks(docs)
    col = ingest.get_collection(reset=True)
    col.upsert(ids=ids, documents=texts, embeddings=ingest.embed(texts), metadatas=metas)
    return mp


@pytest.fixture(scope="session")
def bge_db(tmp_path_factory, pdf_path):
    """All 30 articles + the PDF, embedded with bge-m3 (the default)."""
    mp = _build_db(tmp_path_factory.mktemp("bge"), "bge", pdf_path, 30)
    yield
    mp.undo()


@pytest.fixture
def pick_llm(request):
    model = request.param
    have = ollama_models()
    if model not in have:
        pytest.skip(f"ollama model {model} not available")
    return model
