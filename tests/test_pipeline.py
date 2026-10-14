"""Validation suite. Categories (used by scripts/run_all_tests.py for the summary):
  TestThreshold  - vector threshold filtering (+ per-embedding-model threshold config, calibration)
  TestLLMRefusal - in-context LLM refusal + post-processing + prompt modes
  TestPDF        - Arabic PDF text extraction integrity
  TestBackends   - multi-backend config sanity (ollama / openai / hf / reranker)
"""
import json
import os
import subprocess
import sys
import threading
import unicodedata
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import config
import prompts
import rag_pipeline as rp
from conftest import ROOT, _build_db
from make_arabic_pdf import LINES
from text_utils import clean_text

IDK = config.IDK_ANSWER
LLMS = ["qwen2.5:7b", "qwen3:8b"]

OFF_TOPIC = ["ما هي عاصمة اليابان؟", "كيف أطبخ المنسف؟", "من فاز بكأس العالم 2022؟", "اكتب لي قصيدة عن الحب"]
# In-domain-looking but NOT answerable from the corpus; all pass the 0.55 bge-m3 gate (verified in test_unanswerables_pass_gate).
UNANSWERABLE = [
    "ما اسم الرئيس التنفيذي لشركة أبل؟",
    "كم بلغ سعر الفضة اليوم؟",
    "كم عدد موظفي شركة الواحة في فرع العقبة؟",
    "ما نسبة الأرباح التي وزعتها شركة الواحة عام 2020؟",
]
# (question, substrings of which at least one must appear in the answer)
ANSWERABLE = [
    ("كم بلغت أرباح شركة الواحة خلال عام 2024؟", ["45", "٤٥"]),
    ("في أي مدينة تأسست شركة الواحة للاستثمار؟", ["إربد", "اربد"]),
    ("ما هو سعر الذهب؟", ["1430", "١٤٣٠"]),
]


# =============================================================== vector threshold filtering
class TestThreshold:
    def test_off_topic_short_circuits_without_llm(self, bge_db, monkeypatch):
        def boom(_):
            raise AssertionError("LLM must NOT be called below the threshold")
        monkeypatch.setattr(rp, "generate", boom)
        for q in OFF_TOPIC:
            r = rp.answer_question(q)
            assert r["best_score"] < config.SIM_THRESHOLD, (q, r["best_score"])
            assert r["answer"] == IDK and not r["llm_called"]

    def test_unanswerables_pass_gate(self, bge_db, monkeypatch):
        """These are meant to reach the LLM - proves the LLM-level refusal test is a real test."""
        monkeypatch.setattr(rp, "generate", lambda m: IDK)
        for q in UNANSWERABLE:
            r = rp.answer_question(q)
            assert r["llm_called"], f"{q} scored {r['best_score']:.3f} < threshold - pick a harder question"

    def test_in_corpus_passes_gate(self, bge_db, monkeypatch):
        monkeypatch.setattr(rp, "generate", lambda m: "ok")
        for q, _ in ANSWERABLE:
            assert rp.answer_question(q)["llm_called"], q

    def test_calibrate_separates_and_suggests(self, bge_db):
        res = rp.calibrate(verbose=False)
        assert res["separable"], res
        assert res["off_max"] < res["suggested"] < res["in_min"]
        # the shipped default must sit inside the gap too
        assert res["off_max"] < config.SIM_THRESHOLD < res["in_min"], (res, config.SIM_THRESHOLD)

    @pytest.mark.parametrize("model,thr,qp", [("BAAI/bge-m3", 0.55, ""),
                                              ("intfloat/multilingual-e5-large", 0.80, "query: ")])
    def test_env_switch_updates_config(self, model, thr, qp):
        """Fresh interpreter: EMBED_MODEL env -> matching threshold + prefixes; explicit env var still wins."""
        def run(extra=None):
            env = {**os.environ, "EMBED_MODEL": model, **(extra or {})}
            env.pop("SIM_THRESHOLD", None) if not extra else None
            out = subprocess.check_output([sys.executable, "-c",
                "import config as c, json; print(json.dumps([c.SIM_THRESHOLD, c.QUERY_PREFIX]))"],
                cwd=ROOT, env=env, text=True)
            return json.loads(out)
        assert run() == [thr, qp]
        assert run({"SIM_THRESHOLD": "0.9"})[0] == 0.9

    @pytest.mark.slow
    def test_e5_threshold_separates_live(self, tmp_path_factory, pdf_path):
        """Actually embeds with multilingual-e5-large and checks its default threshold splits the data."""
        mp = _build_db(tmp_path_factory.mktemp("e5"), "e5", pdf_path, 8, "intfloat/multilingual-e5-large")
        try:
            off = max(rp.retrieve(q, 1)[0]["score"] for q in OFF_TOPIC)
            on = rp.retrieve("كم بلغت أرباح شركة الواحة خلال عام 2024؟", 1)[0]["score"]
            assert off < config.SIM_THRESHOLD < on, (off, config.SIM_THRESHOLD, on)
        finally:
            mp.undo()


# =============================================================== in-context LLM refusal
class TestLLMRefusal:
    @pytest.mark.parametrize("pick_llm", LLMS, indirect=True)
    @pytest.mark.parametrize("lang", ["ar", "en"])
    def test_llm_refuses_when_context_lacks_answer(self, bge_db, monkeypatch, pick_llm, lang):
        monkeypatch.setattr(config, "LLM_MODEL", pick_llm)
        monkeypatch.setattr(config, "PROMPT_LANG", lang)
        for q in UNANSWERABLE:
            r = rp.answer_question(q)
            assert r["llm_called"], q
            assert r["answer"] == IDK, f"[{pick_llm}/{lang}] {q}\n raw={r['raw_answer']!r}"

    @pytest.mark.parametrize("pick_llm", LLMS, indirect=True)
    @pytest.mark.parametrize("lang", ["ar", "en"])
    def test_llm_answers_answerable(self, bge_db, monkeypatch, pick_llm, lang):
        monkeypatch.setattr(config, "LLM_MODEL", pick_llm)
        monkeypatch.setattr(config, "PROMPT_LANG", lang)
        for q, needles in ANSWERABLE:
            a = rp.answer_question(q)["answer"]
            assert a != IDK and any(n in a for n in needles), f"[{pick_llm}/{lang}] {q} -> {a!r}"

    @pytest.mark.parametrize("raw", [
        "لا أعرف", "  لا أعرف.  ", "الجواب: لا أعرف", "<think>hmm no info</think>\nلا أعرف",
        "لا يوجد في السياق ما يدل على ذلك.", "المعلومة غير مذكورة في النص.", "لا تتوفر هذه المعلومة في المستندات.",
        "لا اعرف", "لا أعرف، ولكن ربما يكون 50 مليون", "I don't know.", "Answer: The context does not mention this; no information.",
        "", "<think>x</think>",
    ])
    def test_postprocess_collapses_refusals(self, raw):
        assert rp.postprocess(raw) == IDK

    @pytest.mark.parametrize("raw,expected", [
        ("<think>reasoning</think>\nالجواب: ٤٥ مليون دينار", "٤٥ مليون دينار"),
        ("تأسست الشركة في إربد عام ١٩٩٨.", "تأسست الشركة في إربد عام ١٩٩٨."),
    ])
    def test_postprocess_keeps_real_answers(self, raw, expected):
        assert rp.postprocess(raw) == expected

    def test_prompts_ar_en(self):
        for lang, marker in (("ar", "السياق"), ("en", "Context")):
            msgs = prompts.build_messages("سؤال؟", "نص", lang)
            assert [m["role"] for m in msgs] == ["system", "user"]
            assert IDK in msgs[0]["content"] and marker in msgs[1]["content"]
            assert "سؤال؟" in msgs[1]["content"] and "نص" in msgs[1]["content"]
        assert prompts.SYSTEM_PROMPT_AR != prompts.SYSTEM_PROMPT_EN


# =============================================================== Arabic PDF extraction
class TestPDF:
    def _pages(self, pdf):
        import ingest
        return ingest.read_pdf(pdf)

    def test_text_is_logical_order_exact(self, pdf_path):
        text = clean_text(self._pages(pdf_path)[0][1])
        expected = [clean_text(l) for l in LINES]
        assert text.splitlines() == expected

    def test_numbers_not_reversed(self, pdf_path):
        text = clean_text(self._pages(pdf_path)[0][1])
        for n in ("١٩٩٨", "٢٠٢٤", "٤٥", "٣٢٠", "٢٠٢٥"):
            assert n in text, n
        for bad in ("٨٩٩١", "٤٢٠٢", "٠٢٣"):
            assert bad not in text, bad

    def test_words_attached_and_punctuation_trailing(self, pdf_path):
        text = clean_text(self._pages(pdf_path)[0][1])
        assert "شركة الواحة للاستثمار" in text           # word order
        assert not any(l.startswith(".") for l in text.splitlines())  # '.' not stranded at line start
        assert all(l.endswith(".") for l in text.splitlines()[1:])

    def test_pdf_chunks_and_retrieval(self, bge_db):
        r = rp.retrieve("من هو مؤسس شركة الواحة؟", 3)
        assert any(c["source"] == "oasis_report.pdf" for c in r)
        top_pdf = next(c for c in r if c["source"] == "oasis_report.pdf")
        assert "خالد المنصور" in top_pdf["text"]


# =============================================================== backend / mode sanity
MESSAGES = prompts.build_messages("سؤال؟", "[1] نص")


class _FakeOpenAI(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeOpenAI.seen.append((self.path, body))
        out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                          "choices": [{"index": 0, "finish_reason": "stop",
                                       "message": {"role": "assistant", "content": "لا يوجد في السياق"}}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

    def log_message(self, *a): pass


class TestBackends:
    def test_openai_backend_against_fake_server(self, monkeypatch):
        srv = HTTPServer(("127.0.0.1", 0), _FakeOpenAI)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            monkeypatch.setattr(config, "LLM_BACKEND", "openai")
            monkeypatch.setattr(config, "LLM_MODEL", "my-7b")
            monkeypatch.setattr(config, "LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
            out = rp.generate(MESSAGES)
            path, body = _FakeOpenAI.seen[-1]
            assert path.endswith("/chat/completions") and body["model"] == "my-7b"
            assert body["temperature"] == config.LLM_TEMPERATURE and body["messages"][0]["role"] == "system"
            assert rp.postprocess(out) == IDK
        finally:
            srv.shutdown()

    @pytest.mark.parametrize("model", ["trl-internal-testing/tiny-Qwen2ForCausalLM-2.5",  # has chat template
                                       "sshleifer/tiny-gpt2"])                              # no template -> fallback path
    def test_hf_backend_tiny_model(self, monkeypatch, model):
        pytest.importorskip("torch")
        monkeypatch.setattr(config, "LLM_BACKEND", "hf")
        monkeypatch.setattr(config, "LLM_MODEL", model)
        monkeypatch.setattr(config, "LLM_MAX_NEW_TOKENS", 5)
        monkeypatch.setattr(rp, "_hf", {})
        out = rp.generate(MESSAGES)
        assert isinstance(out, str)
        assert isinstance(rp.postprocess(out), str)

    def test_ollama_backend(self):
        if config.LLM_BACKEND != "ollama" or "qwen2.5:7b" not in __import__("conftest").ollama_models():
            pytest.skip("ollama/qwen2.5:7b unavailable")
        cfg = (config.LLM_MODEL, config.LLM_BACKEND)
        config.LLM_MODEL = "qwen2.5:7b"
        try:
            assert rp.generate(prompts.build_messages("كم 2+2؟", "[1] لا شيء")).strip()
        finally:
            config.LLM_MODEL, config.LLM_BACKEND = cfg

    def test_unknown_backend_exits(self, monkeypatch):
        monkeypatch.setattr(config, "LLM_BACKEND", "nope")
        with pytest.raises(SystemExit):
            rp.generate(MESSAGES)

    def test_env_backend_config_loads(self):
        env = {**os.environ, "LLM_BACKEND": "openai", "LLM_MODEL": "m", "LLM_BASE_URL": "http://h:1/v1",
               "PROMPT_LANG": "en", "USE_RERANKER": "1"}
        out = subprocess.check_output([sys.executable, "-c",
            "import config as c, json; print(json.dumps([c.LLM_BACKEND,c.LLM_MODEL,c.LLM_BASE_URL,c.PROMPT_LANG,c.USE_RERANKER]))"],
            cwd=ROOT, env=env, text=True)
        assert json.loads(out) == ["openai", "m", "http://h:1/v1", "en", True]

    @pytest.mark.slow
    def test_reranker(self, bge_db, monkeypatch):
        monkeypatch.setattr(config, "USE_RERANKER", True)
        monkeypatch.setattr(rp, "_reranker", None)
        r = rp.retrieve("من هو مؤسس شركة الواحة؟", 3)
        assert len(r) == 3 and all("rerank" in c for c in r)
        assert r[0]["rerank"] >= r[1]["rerank"] >= r[2]["rerank"]
        assert r[0]["source"] == "oasis_report.pdf"
        assert all("score" in c for c in r)  # cosine kept for the gate
