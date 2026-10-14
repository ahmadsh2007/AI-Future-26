"""Retrieval + generation with hard anti-hallucination gates.

Gate 1: best cosine similarity < SIM_THRESHOLD  -> return "لا أعرف" WITHOUT calling the LLM.
Gate 2: LLM output is normalized: any refusal-like answer collapses to exactly "لا أعرف".

CLI:
    python rag_pipeline.py "سؤالك هنا"
    python rag_pipeline.py "سؤالك" --debug      # show retrieved chunks + scores
    python rag_pipeline.py --calibrate           # help choosing SIM_THRESHOLD
"""
import argparse
import re
import sys

import config
import prompts
from text_utils import clean_text, normalize_for_match

IDK = config.IDK_ANSWER
# Phrases a 7B model uses when it wants to refuse but ignores the exact-string instruction.
_IDK_PATTERNS = [
    "لا اعرف", "لا أعرف", "لااعرف", "لا يوجد", "لا توجد", "لا تتوفر", "لا يتوفر", "غير موجود", "غير مذكور",
    "لم يذكر", "لم يرد", "لا تحتوي", "لا يحتوي", "لا استطيع", "لا أستطيع", "لا يمكنني", "لا اعلم", "لا أعلم",
    "i don't know", "i do not know", "not mentioned", "no information", "cannot answer",
]
_IDK_NORM = [normalize_for_match(p) for p in _IDK_PATTERNS]


# ---------------------------------------------------------------- retrieval
def retrieve(question: str, top_k: int = None) -> list[dict]:
    """Returns chunks sorted by similarity (desc): [{text, score, source, page}]."""
    from ingest import embed, get_collection
    top_k = top_k or config.TOP_K
    col = get_collection()
    if col.count() == 0:
        sys.exit("Vector DB is empty - run: python ingest.py")
    q = embed([clean_text(question)], is_query=True)[0]
    res = col.query(query_embeddings=[q], n_results=min(top_k * 2 if config.USE_RERANKER else top_k, col.count()))
    chunks = [
        {"text": d, "score": 1.0 - dist, "source": m["source"], "page": m["page"]}  # cosine distance -> similarity
        for d, dist, m in zip(res["documents"][0], res["distances"][0], res["metadatas"][0])
    ]
    if config.USE_RERANKER:
        chunks = _rerank(question, chunks)[:top_k]
    return chunks


_reranker = None


def _rerank(question: str, chunks: list[dict]) -> list[dict]:
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(config.RERANKER_MODEL)
    scores = _reranker.predict([(question, c["text"]) for c in chunks])
    for c, s in zip(chunks, scores):
        c["rerank"] = float(s)
    return sorted(chunks, key=lambda c: c["rerank"], reverse=True)  # 'score' (cosine) is kept for the gate


# ---------------------------------------------------------------- LLM backends
_hf = {}


def generate(messages: list[dict]) -> str:
    b = config.LLM_BACKEND
    if b == "ollama":
        import ollama
        r = ollama.chat(model=config.LLM_MODEL, messages=messages, think=False,
                        options={"temperature": config.LLM_TEMPERATURE, "num_ctx": config.LLM_NUM_CTX,
                                 "num_predict": config.LLM_MAX_NEW_TOKENS})
        return r["message"]["content"]
    if b == "openai":
        from openai import OpenAI  # pip install openai (only for this backend)
        r = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY).chat.completions.create(
            model=config.LLM_MODEL, messages=messages, temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_NEW_TOKENS)
        return r.choices[0].message.content
    if b == "hf":
        if not _hf:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            _hf["tok"] = AutoTokenizer.from_pretrained(config.LLM_MODEL)
            _hf["model"] = AutoModelForCausalLM.from_pretrained(config.LLM_MODEL, torch_dtype="auto", device_map="auto")
        tok, model = _hf["tok"], _hf["model"]
        if getattr(tok, "chat_template", None):
            ids = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)["input_ids"]
        else:  # base model without a chat template: plain-text prompt
            ids = tok("\n\n".join(m["content"] for m in messages) + "\n", return_tensors="pt")["input_ids"]
        ids = ids.to(model.device)
        kw = {"do_sample": True, "temperature": config.LLM_TEMPERATURE} if config.LLM_TEMPERATURE > 0 else {"do_sample": False}
        out = model.generate(ids, max_new_tokens=config.LLM_MAX_NEW_TOKENS, **kw)
        return tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
    sys.exit(f"Unknown LLM_BACKEND: {b}")


def postprocess(answer: str) -> str:
    """Strip <think> blocks / labels; collapse any refusal-like answer to exactly IDK."""
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.S).strip()
    answer = re.sub(r"^(الجواب|الإجابة|Answer)\s*[:：]\s*", "", answer).strip()
    if not answer:
        return IDK
    norm = normalize_for_match(answer).lower()
    if any(p in norm for p in _IDK_NORM):
        return IDK  # even "لا أعرف, but maybe X" -> pure refusal (safer than a half-guess)
    return answer


# ---------------------------------------------------------------- main entry
def answer_question(question: str, debug: bool = False) -> dict:
    chunks = retrieve(question)
    best = chunks[0]["score"] if chunks else 0.0
    out = {"question": question, "answer": IDK, "best_score": best, "chunks": chunks, "llm_called": False}

    if best < config.SIM_THRESHOLD:  # Gate 1
        return out

    ctx_chunks = [c for c in chunks if c["score"] >= config.CONTEXT_MIN_SIM] or chunks[:1]
    messages = prompts.build_messages(question, prompts.format_context(ctx_chunks))
    out["llm_called"] = True
    out["raw_answer"] = generate(messages)
    out["answer"] = postprocess(out["raw_answer"])  # Gate 2
    return out


def calibrate(verbose: bool = True) -> dict:
    """Scores in-corpus vs. off-topic queries and suggests a SIM_THRESHOLD.
    In-corpus queries are the first sentences of real chunks (optimistic: real questions score a bit lower),
    so the suggestion sits just above the off-topic ceiling rather than mid-gap."""
    import random
    from ingest import get_collection
    col = get_collection()
    docs = col.get()["documents"]
    random.Random(0).shuffle(docs)
    in_scores = []
    for d in docs[:10]:
        q = re.split(r"(?<=[.؟!])\s", d)[0][:150]
        in_scores.append(retrieve(q, 1)[0]["score"])
    off = ["ما هي عاصمة اليابان؟", "كيف أطبخ المنسف؟", "من فاز بكأس العالم 2022؟", "اكتب لي قصيدة عن الحب",
           "ما هو أفضل علاج للصداع؟", "كم تبعد الأرض عن الشمس؟"]
    off_scores = [retrieve(q, 1)[0]["score"] for q in off]
    res = {"in_min": min(in_scores), "off_max": max(off_scores)}
    res["suggested"] = round(res["off_max"] + 0.03, 2)
    res["separable"] = res["suggested"] < res["in_min"]
    if verbose:
        print(f"embed model     : {config.EMBED_MODEL}")
        print(f"in-corpus  scores: min={res['in_min']:.3f}  (n={len(in_scores)})")
        print(f"off-topic  scores: max={res['off_max']:.3f}  (n={len(off_scores)})")
        print(f"current SIM_THRESHOLD={config.SIM_THRESHOLD}  ->  suggested SIM_THRESHOLD={res['suggested']}")
        if not res["separable"]:
            print("WARNING: off-topic and in-corpus scores overlap - rely on the prompt/LLM gate or try another embedding model.")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    if a.calibrate:
        return calibrate()
    if not a.question:
        ap.error("question required")
    r = answer_question(a.question)
    if a.debug:
        print(f"best_score={r['best_score']:.3f} threshold={config.SIM_THRESHOLD} llm_called={r['llm_called']}")
        for c in r["chunks"]:
            print(f"  [{c['score']:.3f}] {c['source']} p{c['page']}: {c['text'][:90]}...")
        if "raw_answer" in r:
            print("raw:", r["raw_answer"])
    print(r["answer"])


if __name__ == "__main__":
    main()
