"""Government-services chatbot: route -> select sections -> LLM answer. Returns answer + contexts."""
import re

import config
import gov_prompts as P
from gov_data import DOCS, SITUATIONS, load_services, section_context
from gov_router import route
from rag_pipeline import generate
from text_utils import normalize_for_match

SERVICES = load_services()
IDK_FALLBACK = "عذراً، لا أعرف. هذه المعلومة غير متوفرة في وثائق الخدمات المتاحة لدي."


def _clean(ans: str) -> str:
    ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.S).strip()
    return re.sub(r"^(الجواب|الإجابة)\s*[:：]\s*", "", ans).strip()


def _llm(messages, fallback: str, think: bool = False) -> str:
    try:
        out = _clean(generate(messages, think=think))
        if not out and think:   # thinking used up its token budget without a final answer -> answer directly
            out = _clean(generate(messages, think=False))
        return out or fallback
    except Exception as e:  # never crash the run
        print("  [LLM error]", type(e).__name__, str(e)[:100])
        return fallback


def _contexts(services_: list[tuple[str, str]], fields: list[str]):
    """Section texts used for the answer: (display block for the LLM, plain context strings for answers.json)."""
    blocks, ctxs = [], []
    for doc, sit in services_:
        s = SERVICES[f"{doc}_{sit}"]
        parts = []
        for f in fields:
            txt = s["sections"].get(f, "").strip()
            if not txt or (txt == "لا يوجد" and f == "ملاحظات"):
                continue
            c = section_context(s, f)
            ctxs.append(c)
            parts.append(c)
        blocks.append("\n".join(parts))
    return blocks, ctxs


class Chat:
    """One user. Holds the little state needed for follow-up questions."""

    def __init__(self):
        self.route_hist: list[tuple[list, list]] = []
        self.turns: list[tuple[str, str]] = []

    def ask(self, question: str) -> dict:
        r = route(question, self.route_hist)
        kind = r.kind

        if kind == "unknown":   # domain-ish but incomplete: unclear (ask) or out of scope (decline)?
            lab = _llm(P.simple_messages(P.CLASSIFY_SYSTEM, question), "OUT")
            kind = "clarify" if "UNCLEAR" in lab.upper() else "out_of_scope"
            r.missing = r.missing or "doc"

        if kind == "out_of_scope":
            ans = _llm(P.simple_messages(P.DECLINE_SYSTEM, question), IDK_FALLBACK)
            return self._done(question, ans, [], r)

        if kind == "clarify":
            if r.missing == "situation":
                docs = "، ".join(P.DOC_AR[d] for d in r.docs)
                extra = (f"المستخدم يسأل عن {docs} لكنه لم يحدد الحالة. الخيارات: إصدار لأول مرة، تجديد، "
                         "بدل فاقد، بدل تالف. اسأله أي حالة يقصد.")
            else:
                extra = "لم يحدد المستخدم أي وثيقة. الخيارات: جواز السفر، دفتر العائلة، البطاقة الذكية. اسأله أي وثيقة يقصد."
            ans = _llm(P.simple_messages(P.CLARIFY_SYSTEM, question, extra),
                       "هل يمكنك توضيح الوثيقة والحالة (إصدار، تجديد، بدل فاقد، بدل تالف) التي تقصدها؟")
            return self._done(question, ans, [], r)

        blocks, ctxs = _contexts(r.services, r.fields)
        think = "fee" in r.intents    # fee rules (age / expiry / count) need step-by-step reasoning
        ans = _llm(P.answer_messages(question, blocks, self.turns), IDK_FALLBACK, think=think)
        return self._done(question, ans, ctxs, r)

    def _done(self, question, ans, ctxs, r):
        if r.kind == "services":
            self.route_hist.append((sorted({d for d, _ in r.services}), sorted({s for _, s in r.services})))
        self.turns.append((question, ans))
        return {"answer": ans, "contexts": ctxs, "route": {"kind": r.kind, "services": r.services}}
