"""
Quick tests for the Arabic RAG setup (42 Irbid AI Hackathon).

Usage:
    python quick_tests.py                   # run all tests (~1-2 min)
    python quick_tests.py path/to/file.pdf  # also test extraction on a real Arabic PDF

Each test prints PASS / WARN / FAIL with a short hint.
"""
import os
import re
import sys
import time
import unicodedata

os.environ.setdefault("HF_HUB_OFFLINE", "1")          # use cached HF models, never wait on Wi-Fi
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import ollama

LLM = "qwen3:8b"
EMBED_MODELS = ["bge-m3", "qwen3-embedding:0.6b"]
RERANKER = "BAAI/bge-reranker-v2-m3"

# Fictional passages so the model cannot answer from memory
PASSAGES = [
    "سياسة الإجازات: يحق للموظف في شركة النخيل للتقنية الحصول على إجازة سنوية مدفوعة الأجر مدتها واحد وعشرون يوماً، وترتفع إلى ثلاثين يوماً بعد إتمام خمس سنوات من الخدمة.",
    "ساعات العمل: يبدأ الدوام الرسمي في الشركة الساعة الثامنة والنصف صباحاً وينتهي الساعة الرابعة والنصف مساءً، من يوم الأحد إلى يوم الخميس.",
    "العمل عن بُعد: يُسمح للموظفين بالعمل من المنزل يومين في الأسبوع كحد أقصى، بشرط الحصول على موافقة مسبقة من المدير المباشر.",
    "التدريب والتطوير: تخصص الشركة ميزانية تدريب سنوية قدرها ٨٠٠ دينار أردني لكل موظف لحضور الدورات والمؤتمرات المهنية.",
    "بدل المواصلات: يحصل كل موظف على بدل مواصلات شهري قيمته ٤٥ ديناراً يُصرف مع الراتب في نهاية كل شهر.",
]
# (question, index of the passage that answers it) - some use synonyms on purpose
QUESTIONS = [
    ("كم يوماً من الإجازة السنوية يحصل عليها الموظف؟", 0),
    ("متى ينتهي الدوام الرسمي؟", 1),
    ("هل يمكنني العمل من البيت؟", 2),           # البيت vs المنزل
    ("كم المبلغ المخصص لتدريب كل موظف؟", 3),
    ("ما قيمة بدل النقل الشهري؟", 4),            # النقل vs المواصلات
]
UNANSWERABLE = "ما هو راتب المدير العام للشركة؟"
REFUSAL = "لا تتوفر هذه المعلومة في المستندات."


def report(status, name, detail=""):
    print(f"[{status}] {name}" + (f"  ->  {detail}" if detail else ""))


# ---------------------------------------------------------------- Arabic text helpers
DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")


def normalize_ar(text):
    text = unicodedata.normalize("NFKC", text)   # presentation forms -> normal letters
    text = DIACRITICS.sub("", text)              # remove tashkeel
    text = text.replace("\u0640", "")            # remove tatweel
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return text


def tokenize_ar(text):
    tokens = []
    for t in re.findall(r"\w+", normalize_ar(text)):
        for p in PREFIXES:
            if t.startswith(p) and len(t) - len(p) >= 2:
                t = t[len(p):]
                break
        tokens.append(t)
    return tokens


def cosine(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    b /= np.linalg.norm(b, axis=1, keepdims=True)
    return a @ b.T


# ---------------------------------------------------------------- tests
def test_normalization():
    cases = [
        ("أَحْمَد", "احمد"),
        ("مـــدرسة", "مدرسه"),
        ("\uFEE3\uFEAE\uFEA3\uFE92\uFE8E", "مرحبا"),   # presentation forms
        ("٢٠٢٦", "2026"),
        ("إلى", "الي"),
    ]
    bad = [(i, normalize_ar(i), e) for i, e in cases if normalize_ar(i) != e]
    ok_tok = tokenize_ar("والمدرسة") == ["مدرسه"]
    if not bad and ok_tok:
        report("PASS", "Arabic normalization + prefix stripping")
    else:
        report("FAIL", "Arabic normalization", f"mismatches: {bad}, tokenizer ok: {ok_tok}")


def test_bm25():
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi([tokenize_ar(p) for p in PASSAGES])
    variant_top = int(np.argmax(bm25.get_scores(tokenize_ar("الاجازه السنويه"))))
    report("PASS" if variant_top == 0 else "FAIL", "BM25 matches different spellings",
           "" if variant_top == 0 else "normalization is not applied to index or query")
    hits = sum(int(np.argmax(bm25.get_scores(tokenize_ar(q)))) == g for q, g in QUESTIONS)
    report("PASS" if hits == len(QUESTIONS) else "WARN", f"BM25 top-1: {hits}/{len(QUESTIONS)}",
           "" if hits == len(QUESTIONS) else "normal: BM25 misses synonyms, which is why you combine it with vectors")


def test_embeddings():
    instruct = "Instruct: Given a question, retrieve passages that answer the question\nQuery: "
    chunk = " ".join(PASSAGES) * 2                      # ~230 Arabic words, a realistic chunk
    for model in EMBED_MODELS:
        try:
            doc_vecs = ollama.embed(model=model, input=PASSAGES).embeddings
        except Exception as e:
            report("FAIL", f"embed {model}", f"{e}  (ollama pull {model})")
            continue
        qs = [q for q, _ in QUESTIONS]
        if model.startswith("qwen3-embedding"):
            qs = [instruct + q for q in qs]
        sims = cosine(ollama.embed(model=model, input=qs).embeddings, doc_vecs)
        hits = sum(int(np.argmax(sims[i])) == g for i, (_, g) in enumerate(QUESTIONS))

        start = time.time()
        ollama.embed(model=model, input=[chunk] * 32)
        rate = 32 / (time.time() - start)
        report("PASS" if hits == len(QUESTIONS) else "WARN",
               f"{model}: top-1 {hits}/{len(QUESTIONS)}, {rate:.1f} chunks/sec",
               f"50k chunks ~ {50000 / rate / 60:.0f} min, 5k chunks ~ {5000 / rate / 60:.1f} min")


def test_reranker():
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder(RERANKER, device="mps", max_length=512)
    except Exception as e:
        report("FAIL", "load reranker", str(e))
        return
    hits = sum(int(np.argmax(model.predict([(q, p) for p in PASSAGES]))) == g for q, g in QUESTIONS)
    report("PASS" if hits == len(QUESTIONS) else "WARN", f"reranker top-1: {hits}/{len(QUESTIONS)}")


def test_tokens_per_word():
    sample = " ".join(PASSAGES)
    r = ollama.generate(model=LLM, prompt=sample, raw=True, options={"num_predict": 1})
    ratio = r["prompt_eval_count"] / len(sample.split())
    report("PASS", f"Qwen3 uses ~{ratio:.2f} tokens per Arabic word",
           f"a 500-token chunk ~ {int(500 / ratio)} words; 5 chunks of that ~ {5 * 500} tokens of context")


def ask(question):
    system = ("You answer questions using ONLY the provided context. "
              "Answer in Modern Standard Arabic, concisely. "
              f"If the answer is not in the context, reply exactly: {REFUSAL}")
    context = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(PASSAGES))
    start = time.time()
    r = ollama.chat(
        model=LLM,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": f"السياق:\n{context}\n\nالسؤال: {question}"}],
        think=False,
        options={"temperature": 0, "num_ctx": 8192},
    )
    return r, time.time() - start


def test_llm():
    try:
        r, dt = ask("ما هي ميزانية التدريب السنوية لكل موظف؟")
    except Exception as e:
        report("FAIL", "LLM chat", str(e))
        return
    ans = r["message"]["content"].strip()
    letters = re.findall(r"[^\W\d_]", ans)
    arabic_share = sum("\u0600" <= c <= "\u06FF" for c in letters) / max(len(letters), 1)
    print(f"      answer: {ans}")
    report("PASS" if "800" in normalize_ar(ans) else "FAIL", "LLM grounded answer (expects 800)")
    report("PASS" if arabic_share > 0.7 else "WARN", f"answer is {arabic_share:.0%} Arabic letters")
    gen_speed = r["eval_count"] / (r["eval_duration"] / 1e9)
    prompt_speed = r["prompt_eval_count"] / (r["prompt_eval_duration"] / 1e9)
    report("PASS", f"total {dt:.1f}s (model load {r['load_duration'] / 1e9:.1f}s)",
           f"reads {prompt_speed:.0f} tok/s, writes {gen_speed:.1f} tok/s")

    r2, dt2 = ask(UNANSWERABLE)
    ans2 = r2["message"]["content"].strip()
    print(f"      answer: {ans2}")
    refused = normalize_ar("لا تتوفر") in normalize_ar(ans2)
    report("PASS" if refused else "FAIL", f"LLM refuses unanswerable question ({dt2:.1f}s)",
           "" if refused else "model invented an answer: tighten the system prompt")


def test_pdf(path):
    import fitz
    doc = fitz.open(path)
    n = min(len(doc), 10)
    text = "".join(doc[i].get_text() for i in range(n))
    per_page = len(text.strip()) / max(n, 1)
    if per_page < 50:
        report("FAIL", "PDF has almost no text", "probably scanned: you need OCR (tesseract -l ara)")
        return
    pres = len(re.findall(r"[\uFB50-\uFDFF\uFE70-\uFEFF]", text))
    arabic = len(re.findall(r"[\u0600-\u06FF]", text))
    report("WARN" if pres > 0.1 * (arabic + pres) else "PASS", "presentation forms",
           f"{pres} shaped chars vs {arabic} normal (normalize_ar fixes this)" if pres else "none")
    words = re.findall(r"\w+", normalize_ar(text))
    common = ["في", "من", "علي", "الي", "التي", "الذي"]
    n_ok = sum(words.count(w) for w in common)
    n_rev = sum(words.count(w[::-1]) for w in common)
    report("FAIL" if n_rev > n_ok else "PASS", f"word direction (normal {n_ok}, reversed {n_rev})",
           "text is reversed: try pdfplumber or reverse each line" if n_rev > n_ok else "")
    print(f"      first 300 chars (check by eye):\n{normalize_ar(text)[:300]}")


if __name__ == "__main__":
    t0 = time.time()
    print("== Text processing")
    test_normalization()
    test_bm25()
    print("\n== Ollama")
    try:
        names = [m.model for m in ollama.list().models]
        report("PASS", "Ollama is running")
        for m in [LLM] + EMBED_MODELS:
            found = any(n in (m, m + ":latest") for n in names)
            report("PASS" if found else "FAIL", f"model {m}", "" if found else f"ollama pull {m}")
        print("\n== Embeddings (retrieval accuracy + speed)")
        test_embeddings()
        print("\n== Reranker")
        test_reranker()
        print("\n== LLM")
        test_tokens_per_word()
        test_llm()
    except Exception as e:
        report("FAIL", "Ollama is running", f"{e}  -> open the Ollama app")
    if len(sys.argv) > 1:
        print("\n== PDF extraction")
        test_pdf(sys.argv[1])
    print(f"\nDone in {time.time() - t0:.0f}s")
