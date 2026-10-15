"""LLM-free tests for the government-services bot: data parsing, dialect routing, section selection, answers.json format."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gov_data import FIELDS, load_services, section_context  # noqa: E402
from gov_router import route  # noqa: E402

SERVICES = load_services()


class TestGovData:
    def test_twelve_services_nine_fields(self):
        assert len(SERVICES) == 12
        for s in SERVICES.values():
            assert set(s["sections"]) == set(FIELDS), s["id"]

    def test_menu_lines_removed_and_facts_kept(self):
        for s in SERVICES.values():
            blob = "\n".join(s["sections"].values())
            assert "دليل الخدمات" not in blob and "\t" not in blob
        assert "125 دينار" in SERVICES["passport_lost"]["sections"]["الرسوم"]
        assert "250" in SERVICES["passport_lost"]["sections"]["الرسوم"]
        assert "180" in SERVICES["passport_renewal"]["sections"]["الرسوم"]
        assert "25 دينار" in SERVICES["passport_renewal"]["sections"]["ملاحظات"]

    def test_context_format(self):
        c = section_context(SERVICES["family_book_renewal"], "الزمن المستغرق")
        assert c.startswith("تجديد دفتر العائلة - الزمن المستغرق:") and "45" in c


DEV = json.load(open(ROOT / "dev" / "dev_set.json", encoding="utf-8"))


@pytest.mark.parametrize("case", [c for c in DEV if "svc" in c], ids=lambda c: c["id"])
def test_dev_set_routing(case):
    """Replays each dev conversation through the router only (history = previous resolved services)."""
    hist = []
    for q in case["q"]:
        r = route(q, hist)
        assert r.kind == "services", (q, r.kind)
        hist.append((sorted({d for d, _ in r.services}), sorted({s for _, s in r.services})))
    got = {f"{d}_{s}" for d, s in r.services}
    assert got == set(case["svc"]), (case["id"], got)


@pytest.mark.parametrize("q,kind", [
    ("بدي أجدد، شو المطلوب؟", "unknown"),            # no document -> LLM decides clarify vs decline
    ("كم رسوم الجواز؟", "unknown"),                   # no situation
    ("كم سعر تذكرة الطيران من عمان إلى دبي؟", "out_of_scope"),
    ("شو الطقس اليوم بعمان؟", "out_of_scope"),
    ("كم رسوم جواز السفر الدبلوماسي؟", "out_of_scope"),
])
def test_non_service_routes(q, kind):
    assert route(q).kind == kind


@pytest.mark.parametrize("q,pairs", [
    ("قديش صورة شخصية بحتاج للبطاقة الذكية لأول مرة، وقديش لتجديد جواز السفر؟",
     {("id_card", "first_issue"), ("passport", "renewal")}),
    ("قديش مدة تجديد الجواز ومدة إصدار البطاقة الذكية؟", {("passport", "renewal"), ("id_card", "first_issue")}),
    ("وين بقدر أطلع جواز سفر بدل فاقد؟", {("passport", "lost")}),          # "أطلع" must not add first_issue
    ("خلص الباسبور شو أعمل؟", {("passport", "renewal")}),
    ("ضيعت الهوية", {("id_card", "lost")}),
    ("كم رسوم دفتر عائلة جديد لمولودي؟", {("family_book", "first_issue")}),
])
def test_pairing_and_dialect(q, pairs):
    assert set(route(q).services) == pairs


def test_followup_inherits_service():
    first = route("كم تكلفة بدل فاقد للجواز؟")
    hist = [(["passport"], ["lost"])]
    assert first.services == [("passport", "lost")]
    r = route("وكم بياخد وقت؟", hist)
    assert r.services == [("passport", "lost")] and "الزمن المستغرق" in r.fields


def test_field_selection_is_narrow_but_keeps_notes_for_fees():
    r = route("كم رسوم تجديد جواز السفر؟")
    assert set(r.fields) == {"الرسوم", "ملاحظات"}
    assert route("كم يستغرق تجديد دفتر العائلة؟").fields == ["الزمن المستغرق"]
    assert len(route("إذا توفي الأب والأم من يصير ربّ الأسرة في دفتر العائلة؟").fields) >= 3


def test_main_writes_valid_answers_json(tmp_path, monkeypatch):
    """main.py keeps the input structure, adds answer+contexts to EVERY message, and survives per-message errors."""
    import gov_bot
    import main as main_mod

    class FakeChat:
        def ask(self, q):
            if "boom" in q:
                raise RuntimeError("x")
            return {"answer": "ok", "contexts": ["c"]}

    monkeypatch.setattr(gov_bot, "Chat", FakeChat)
    src = tmp_path / "questions.json"
    qs = {"chats": [{"chat_id": "c1", "messages": [{"message_id": "c1-1", "question": "a"},
                                                    {"message_id": "c1-2", "question": "boom"}]}]}
    src.write_text(json.dumps(qs, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["main.py", str(src)])
    main_mod.main()
    out = json.loads((tmp_path / "answers.json").read_text(encoding="utf-8"))
    msgs = out["chats"][0]["messages"]
    assert [m["message_id"] for m in msgs] == ["c1-1", "c1-2"]
    assert msgs[0]["answer"] == "ok" and msgs[0]["contexts"] == ["c"]
    assert msgs[1]["answer"] == "error" and msgs[1]["contexts"] == []
