# TL;DR: Arabic RAG Q&A

## The one-line pitch
Arabic document Q&A that **answers only from the documents and says `لا أعرف` otherwise**. Two independent safety gates make it hard to hallucinate.

## How it works
```
Docs (PDF/TXT) → clean + chunk → embed (bge-m3) → ChromaDB
Question → embed → top-5 chunks
   Gate 1: best similarity < threshold? → "لا أعرف" (LLM never called)
   else → strict few-shot prompt → LLM (temperature 0)
   Gate 2: output looks like a refusal? → exactly "لا أعرف"
```

## Design choices to explain to the judges
1. **Gate 1: a similarity threshold skips the LLM.** An off-topic question can't hallucinate, because the model never sees it. The threshold depends on the embedding model: 0.55 for `bge-m3`, 0.80 for `e5-large`. We measured these on our data, and `--calibrate` suggests a value for any new corpus.
2. **A constrained prompt for 7B models.** It has short numbered rules, a hard refusal string, and two few-shot examples (one answerable, one refused). It comes in Arabic and English, so we can test which refuses more reliably.
3. **Gate 2: post-processing.** It strips `<think>` blocks and answer labels. Any refusal-like wording ("لا يوجد في السياق…", "I don't know") collapses to exactly `لا أعرف`. It also catches "I don't know, but maybe X" and returns a pure refusal rather than a half-guess.
4. **Arabic-aware chunking.** It splits on sentence boundaries (including `؟ ؛ ۔`), never mid-sentence, with a 1-sentence overlap between chunks. Text cleaning removes tashkeel and tatweel, and Unicode normalization (NFKC) fixes PDF glyph forms.
5. **A PDF extraction fix.** Arabic PDFs often come out of PyMuPDF with reversed word order, reversed numbers (`١٩٩٨` → `٨٩٩١`) and misplaced punctuation. We rebuild each line from glyph positions, which fixes all three. This is a good story for the presentation.
6. **Swappable parts.** The LLM backend is `ollama`, `openai` (vLLM or LM Studio) or `hf`, and the embedder is `bge-m3` or `e5-large`. An optional reranker is available. Everything is set by environment variables. We use ChromaDB and sentence-transformers directly, not LangChain, so it's easy to debug.

## Results
- **42 of 42 tests pass.** They cover the threshold, in-context LLM refusal, PDF integrity and backend config.
- Four in-domain-looking unanswerable questions (Apple's CEO, silver price, and so on) pass Gate 1 and reach the LLM. `qwen2.5:7b` and `qwen3:8b` both refuse them, in Arabic and English prompt modes.
- Answerable questions, including facts from the PDF, are answered correctly.
- Threshold separation:
  - `bge-m3`: off-topic questions score 0.51 or lower, real questions 0.62–0.93.
  - `e5-large`: off-topic 0.77 or lower, real 0.84 or higher.

## Honest limits (say these before the judges ask)
- The test PDF is synthetic. Tables, multi-column and scanned PDFs are untested, and scanned ones would need OCR.
- We tested with qwen models, not the event model. Its refusal wording may need extra phrases in `rag_pipeline.py`.
- A thin similarity gap could hurt very short or vague questions, so we calibrate on event day.

## Event-day runbook
1. Copy the documents to `data/raw_docs/`, then run `python ingest.py`.
2. Set the model, for example `LLM_BACKEND=ollama LLM_MODEL=<tag>`.
3. Run `python rag_pipeline.py --calibrate` and set `SIM_THRESHOLD`.
4. Try `PROMPT_LANG=ar` and `PROMPT_LANG=en`, and keep whichever refuses more reliably.
5. Ask 5 real questions and 5 trick questions with `--debug`, and check the scores and refusals.
6. Run `python scripts/run_all_tests.py --fast` as a sanity check.

## Study questions for the team
- Why skip the LLM below the threshold instead of only prompting it to refuse?
- Why does the threshold differ between `bge-m3` and `e5-large`?
- What goes wrong with a PDF that stores Arabic in visual order, and how do we fix it?
- Why does Gate 2 return a pure `لا أعرف` for "لا أعرف، ولكن ربما…"?

See `README.md` for the full commands.
