first link: https://claude.ai/share/05296964-50a2-42df-b7d2-d2471e58cb42


# Arabic RAG Q&A (hackathon pipeline)

Strict, hallucination-averse Arabic document Q&A. Answers only from retrieved context, otherwise returns exactly `لا أعرف`.

```
question ─► embed ─► ChromaDB top-k ─► Gate 1: best cosine < SIM_THRESHOLD? ─► "لا أعرف" (LLM never called)
                                         │ no
                                         ▼
                              constrained prompt (few-shot) ─► LLM (temp 0) ─► Gate 2: refusal-like text ─► "لا أعرف"
```

| File | Role |
|---|---|
| `config.py` | all paths/models/thresholds (every value overridable via env var) |
| `text_utils.py` | Arabic cleaning (NFKC fixes PDF glyphs, strips tashkeel/tatweel) + sentence-aware chunking |
| `ingest.py` | PDF/TXT → chunks → embeddings → ChromaDB |
| `rag_pipeline.py` | retrieval, similarity gate, LLM backends (`ollama`/`openai`/`hf`), answer post-processing |
| `prompts.py` | Arabic + English constrained system prompts with few-shot examples |
| `pdf_extract.py` | geometry-based PDF extraction that fixes reversed Arabic words/digits (see Testing) |
| `download_test_data.py` | pulls 30 Arabic finance articles into `data/raw_docs/` |
| `scripts/run_all_tests.py` | runs the validation suite and prints a pass/fail report |

## Quick start

```bash
python3.11 -m venv .venv && source .venv/bin/activate     # 3.10-3.12 recommended
pip install -r requirements.txt

python download_test_data.py            # 30 AraFinNews articles -> data/raw_docs/*.txt
python ingest.py                        # chunk + embed -> data/vector_db/  (rebuilds each run)

ollama serve &                          # if not already running
ollama pull qwen2.5:7b
LLM_MODEL=qwen2.5:7b python rag_pipeline.py "ما هو سعر الذهب؟" --debug      # answerable
LLM_MODEL=qwen2.5:7b python rag_pipeline.py "ما هي عاصمة اليابان؟" --debug  # -> لا أعرف (no LLM call)
python rag_pipeline.py --calibrate      # prints in-corpus vs off-topic scores to tune SIM_THRESHOLD
```

## Hackathon day checklist

1. Put the real files in `data/raw_docs/` (or `DOCS_DIR=...`), run `python ingest.py`.
2. Set the model: `LLM_BACKEND=ollama LLM_MODEL=<tag>` · vLLM/LM Studio: `LLM_BACKEND=openai LLM_BASE_URL=http://host:8000/v1 LLM_MODEL=<name>` · local HF weights: `LLM_BACKEND=hf LLM_MODEL=<repo or path>`.
3. Run `python rag_pipeline.py --calibrate`, then set `SIM_THRESHOLD` between the highest off-topic score and the lowest in-corpus score. **Scores are model-specific**: `bge-m3` separates widely (default 0.55: off-topic ≤0.51, real questions 0.62–0.93); `multilingual-e5-large` compresses scores (off-topic ≤0.77, real ≥0.84), so its default is 0.80. Defaults switch automatically with `EMBED_MODEL`; `SIM_THRESHOLD` always overrides. `--calibrate` prints a suggested value. Use `EMBED_MODEL=intfloat/multilingual-e5-large` (prefixes are automatic) and re-ingest if you switch.
4. A/B the prompt language with the real model: `PROMPT_LANG=ar` vs `PROMPT_LANG=en`.
5. Optional accuracy boost: `USE_RERANKER=1` (bge-reranker-v2-m3). Retrieval too coarse/fine? Tune `CHUNK_SIZE` (default 700 chars) and `TOP_K`, then re-ingest.
6. PDFs: if extracted Arabic looks reversed/garbled, inspect with `python ingest.py` output chunks (or `--debug` queries); scanned PDFs without a text layer need OCR (ingest warns).

## Notes
- Programmatic use: `from rag_pipeline import answer_question; answer_question("...")["answer"]`.
- Gate 2 deliberately collapses *any* answer containing refusal wording (even "لا أعرف, but maybe X") to a pure `لا أعرف`.
- Chroma + `sentence-transformers` are used directly instead of LangChain — fewer layers to debug in 4 hours.

## Testing

```bash
pip install -r requirements-test.txt
python download_test_data.py
python scripts/run_all_tests.py          # full pass (~4 min; first run downloads e5-large + reranker)
python scripts/run_all_tests.py --fast   # skips the slow e5 / reranker tests
```
LLM tests need Ollama running with `qwen2.5:7b` and `qwen3:8b` (missing models are skipped, not passed).

**Last full run (Python 3.11, macOS): 42 passed, 0 failed, 0 skipped.**

| Area | Result |
|---|---|
| Vector threshold filtering | off-topic questions never reach the LLM; 4 in-domain-looking unanswerables do pass the gate; calibration separates the data; bge-m3 / e5-large defaults switch with `EMBED_MODEL` (live e5 run included) |
| In-context LLM refusal | the 4 unanswerables return exactly `لا أعرف` on both `qwen2.5:7b` and `qwen3:8b`, with Arabic and English prompts; answerable questions (incl. PDF facts) are answered correctly; post-processing collapses 13 messy refusal formats and leaves real answers untouched |
| Arabic PDF extraction | test PDF is generated in visual order like real-world PDFs; extracted lines match the source exactly |
| Backend sanity | `openai` (against a local fake server), `hf` (tiny models, with and without a chat template), `ollama`, env-var config loading, unknown backend, reranker |

**PDF bug found and fixed:** PyMuPDF's sorted extraction returned Arabic PDFs with reversed word order, reversed digits (`١٩٩٨` → `٨٩٩١`) and stranded punctuation. `pdf_extract.py` now rebuilds each line from glyph positions. `PDF_EXTRACT_MODE=plain` restores PyMuPDF's default.

**Limits of this validation:** the PDF is synthetic (one font, single column); real hackathon PDFs, especially tables, multi-column or scanned ones, may still need checking. The 7B models tested are qwen2.5/qwen3, not the event model. Refusal wording rules in `rag_pipeline.py` may need extra phrases for a different model.
