"""Parse PDFs/TXTs -> chunk -> embed -> store in a local ChromaDB.

Usage:
    python ingest.py                 # ingest everything in DOCS_DIR (rebuilds the DB)
    python ingest.py --docs path/    # custom folder
    python ingest.py --keep          # append to existing DB instead of rebuilding
"""
import argparse
import shutil
import sys
from pathlib import Path

import config
from text_utils import chunk_text, clean_text

_model = None


def get_embedder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        kwargs = {"device": config.EMBED_DEVICE} if config.EMBED_DEVICE else {}
        _model = SentenceTransformer(config.EMBED_MODEL, **kwargs)
        _model.max_seq_length = config.EMBED_MAX_SEQ_LENGTH
    return _model


def embed(texts: list[str], is_query: bool = False, show_progress: bool = False):
    prefix = config.QUERY_PREFIX if is_query else config.PASSAGE_PREFIX
    return get_embedder().encode(
        [prefix + t for t in texts],
        batch_size=config.EMBED_BATCH_SIZE,
        normalize_embeddings=True,  # unit vectors -> dot product == cosine similarity
        show_progress_bar=show_progress,
    ).tolist()


def get_collection(reset: bool = False):
    import chromadb
    client = chromadb.PersistentClient(path=str(config.VECTOR_DB_DIR))
    if reset:
        try:
            client.delete_collection(config.COLLECTION_NAME)
        except Exception:
            pass
    return client.get_or_create_collection(config.COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def read_pdf(path: Path) -> list[tuple[int, str]]:
    import fitz  # PyMuPDF
    pages = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True)
            if text.strip():
                pages.append((i, text))
    if not pages:
        print(f"  [WARN] {path.name}: no text layer (scanned PDF? needs OCR)")
    return pages


def read_txt(path: Path) -> list[tuple[int, str]]:
    for enc in ("utf-8-sig", "utf-8", "cp1256", "iso-8859-6"):
        try:
            return [(1, path.read_text(encoding=enc))]
        except UnicodeDecodeError:
            continue
    print(f"  [WARN] {path.name}: could not decode")
    return []


def load_documents(docs_dir: Path):
    files = sorted(p for p in docs_dir.rglob("*") if p.suffix.lower() in {".pdf", ".txt", ".md"})
    for p in files:
        yield p, (read_pdf(p) if p.suffix.lower() == ".pdf" else read_txt(p))


def build_chunks(docs_dir: Path):
    ids, texts, metas = [], [], []
    for path, pages in load_documents(docs_dir):
        n = 0
        for page_no, raw in pages:
            for j, chunk in enumerate(chunk_text(raw, config.CHUNK_SIZE,
                                                 config.CHUNK_OVERLAP_SENTENCES, config.MIN_CHUNK_CHARS)):
                rel = str(path.relative_to(docs_dir))
                ids.append(f"{rel}::p{page_no}::c{j}")
                texts.append(chunk)
                metas.append({"source": rel, "page": page_no, "chunk": j})
                n += 1
        print(f"  {path.name}: {n} chunks")
    return ids, texts, metas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=str(config.DOCS_DIR))
    ap.add_argument("--keep", action="store_true", help="append instead of rebuilding the DB")
    args = ap.parse_args()

    docs_dir = Path(args.docs)
    if not docs_dir.exists():
        sys.exit(f"Docs folder not found: {docs_dir}")

    print(f"Reading documents from {docs_dir}")
    ids, texts, metas = build_chunks(docs_dir)
    if not texts:
        sys.exit("No chunks produced - check the folder / file types.")
    print(f"Total chunks: {len(texts)}  | embedding with {config.EMBED_MODEL}")

    embeddings = embed(texts, show_progress=True)
    col = get_collection(reset=not args.keep)
    B = 256
    for i in range(0, len(ids), B):
        col.upsert(ids=ids[i:i + B], documents=texts[i:i + B],
                   embeddings=embeddings[i:i + B], metadatas=metas[i:i + B])
    print(f"Done. {col.count()} chunks stored in {config.VECTOR_DB_DIR}")


if __name__ == "__main__":
    main()
