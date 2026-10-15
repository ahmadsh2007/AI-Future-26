# -*- coding: utf-8 -*-
"""Independent scorer for the government-services chatbot.

Usage:
    python3 eval/score.py eval/dev_set.json <answers.json>
    python3 eval/score.py --check            # verify dev_set ref_contexts exist in data/

Does NOT import bot.kb / bot.router / bot.answer / bot.normalize.
Always exits 0; malformed input is reported, never raised.
"""
import json
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(ROOT, "data")
sys.path.insert(0, ROOT)
try:
    from bot.schema import SERVICES  # only the contract module
    SERVICE_IDS = list(SERVICES.keys())
except Exception:  # pragma: no cover - fallback if schema missing
    SERVICE_IDS = sorted(f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".txt"))

TYPES = ["simple_fact", "fee_situation", "documents_conditions", "hidden_in_notes", "comparison",
         "dialect", "conversation", "long_story", "wrong_assumption", "unclear", "not_in_data"]

# ------------------------------------------------------------------ normalization
_DIAC = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")  # harakat + tatweel
_DIGITS = {ord(a): ord("0") + i for i, a in enumerate("٠١٢٣٤٥٦٧٨٩")}
_DIGITS.update({ord(a): ord("0") + i for i, a in enumerate("۰۱۲۳۴۵۶۷۸۹")})

# number words (already in normalized spelling); multi-word first
_NUM_PHRASES = [
    (r"مئه وخمسه وعشرين|ميه وخمسه وعشرين|مائه وخمسه وعشرين", "125"),
    (r"مئتين وخمسين|ميتين وخمسين|مائتين وخمسين|مئتان وخمسون", "250"),
    (r"خمسه وعشرين|خمسه وعشرون|خمس وعشرين", "25"),
    (r"(?:ال)?سادسه عشر(?:ه)?", "16"),
    (r"(?:ال)?ثامنه عشر(?:ه)?", "18"),
]
_NUM_WORDS = {
    "واحد": "1", "واحده": "1",
    "اثنين": "2", "اثنان": "2", "اثنتين": "2", "اثنتان": "2",
    "ثلاث": "3", "ثلاثه": "3", "الثلاث": "3", "تلات": "3", "تلاته": "3",
    "اربع": "4", "اربعه": "4", "خمس": "5", "خمسه": "5",
    "عشر": "10", "عشره": "10", "عشرين": "20", "عشرون": "20",
    "خمسين": "50", "خمسون": "50", "مئه": "100", "مائه": "100", "ميه": "100",
    "تسعين": "90", "تسعون": "90", "ثلاثين": "30", "ثلاثون": "30",
}
_DUALS = {"دينارين": "2 دينار", "ديناران": "2 دينار", "صورتين": "2 صوره", "صورتان": "2 صوره"}


def normalize(text):
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    t = unicodedata.normalize("NFC", text)
    t = t.translate(_DIGITS)
    t = _DIAC.sub("", t)
    t = re.sub("[أإآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = t.replace("\u200f", " ").replace("\u200e", " ").replace("\xa0", " ")
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def numify(t):
    """Map Arabic number words in an already-normalized string to digits."""
    for pat, val in _NUM_PHRASES:
        t = re.sub(r"(?<![\w])(?:%s)(?![\w])" % pat, " %s " % val, t)

    def rep(m):
        w = m.group(0)
        if w in _DUALS:
            return _DUALS[w]
        return _NUM_WORDS.get(w, w)
    t = re.sub(r"[^\W\d_]+", rep, t)
    return re.sub(r"\s+", " ", t).strip()


def norm_full(text):
    return numify(normalize(text))


def numbers(t):
    return set(int(x) for x in re.findall(r"\d+", t) if len(x) < 9)


def has_number(t, n):
    return re.search(r"(?<!\d)%s(?!\d)" % re.escape(str(n)), t) is not None


def item_present(item, t):
    """item may contain alternatives separated by '|'. Numbers match as whole numbers."""
    for alt in str(item).split("|"):
        a = norm_full(alt)
        if not a:
            continue
        if re.fullmatch(r"\d+", a):
            if has_number(t, a):
                return True
        elif a in t:
            return True
    return False


# ------------------------------------------------------------------ status detection
_DECLINE = [normalize(x) for x in [
    "لا تتوفر", "لا أملك معلومات", "لا املك", "عذراً", "عذرا", "خارج نطاق", "خارج اختصاص", "لا يوجد لدي",
    "ليست لدي", "ليس لدي معلومات", "ليس لدي", "لا تتوفر لدي", "غير متوفرة لدي", "لا أستطيع المساعدة في",
    "لا تغطي", "لا تشمل الوثائق", "غير مشمول", "لا أعرف", "لا تتضمن الوثائق المتوفرة",
]]
_CLARIFY = [normalize(x) for x in [
    "هل تقصد", "ماذا تقصد", "ما الذي تقصد", "شو قصدك", "شو بتقصد", "تقصد", "حدد", "حدّد", "وضح", "وضّح",
    "توضيح", "اي وثيقه", "أي خدمة", "اي خدمه", "ما الوثيقة", "ما الخدمة",
]]  # the bare token "أي/أيّ" is matched separately as a whole word


def is_decline(a_norm):
    return any(p in a_norm for p in _DECLINE)


def asks_clarify(a_norm):
    if "؟" not in a_norm and "?" not in a_norm:
        return False
    if any(p in a_norm for p in _CLARIFY):
        return True
    return re.search(r"(?<![\w])اي(?![\w])", a_norm) is not None


def only_question(a_norm):
    """True when the non-question part of the answer is tiny (it just asks back)."""
    parts = re.split(r"(?<=[.!؟?\n])", a_norm)
    rest = "".join(p for p in parts if not p.strip().endswith(("؟", "?")))
    return len(rest.strip()) < 40


def text_status(answer):
    a = normalize(answer)
    if is_decline(a) and not asks_clarify(a):
        return "out_of_scope"
    if asks_clarify(a) and only_question(a):
        return "unclear"
    if is_decline(a):
        return "out_of_scope"
    return "ok"


def status_ok(expect, answer):
    a = normalize(answer)
    if expect == "out_of_scope":
        return is_decline(a)
    if expect == "unclear":
        return asks_clarify(a)
    return not is_decline(a) and not (asks_clarify(a) and only_question(a))


# ------------------------------------------------------------------ source attribution
_MENU = {"الرئيسية", "الخدمات", "دليل الخدمات", "شارك"}


def load_raw():
    raw = {}
    for sid in SERVICE_IDS:
        p = os.path.join(DATA_DIR, sid + ".txt")
        try:
            with open(p, encoding="utf-8") as f:
                raw[sid] = f.read()
        except Exception:
            raw[sid] = ""
    return raw


def strip_menu(text):
    lines = text.splitlines()
    head = [l.strip() for l in lines[:8]]
    if "شارك" in head:  # drop the menu block (incl. breadcrumb title) up to "شارك"
        lines = lines[head.index("شارك") + 1:]
    return "\n".join(l for l in lines if l.strip() not in _MENU)


def grams(t, n=4):
    # punctuation / list markers are formatting noise, not evidence of a source
    t = re.sub(r"[^\w\s]|_", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return set(t[i:i + n] for i in range(max(0, len(t) - n + 1)))


class Attributor(object):
    def __init__(self, raw):
        self.g = {sid: grams(normalize(strip_menu(txt))) for sid, txt in raw.items()}
        df = {}
        for gs in self.g.values():
            for x in gs:
                df[x] = df.get(x, 0) + 1
        n = len(self.g)
        self.idf = {x: math.log(1.0 + float(n) / c) for x, c in df.items()}
        self.idf_unknown = math.log(1.0 + n)

    def scores(self, ctx):
        cg = grams(normalize(ctx))
        if not cg:
            return {}
        tot = sum(self.idf.get(x, self.idf_unknown) for x in cg)
        return {sid: sum(self.idf[x] for x in cg if x in gs) / tot for sid, gs in self.g.items()}

    def tie_set(self, ctx, min_score=0.25, eps=1e-9):
        sc = self.scores(ctx)
        if not sc:
            return [], 0.0
        best = max(sc.values())
        if best < min_score:
            return [], best
        return sorted(s for s, v in sc.items() if v >= best - eps), best


def resolve(ties, expected):
    """A context identical in several look-alike files counts for the expected one."""
    inter = [s for s in ties if s in expected]
    return inter if inter else list(ties)


# ------------------------------------------------------------------ IO helpers
def load_json(path, errors):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        errors.append("cannot read %s: %s" % (path, e))
        return None


def iter_messages(doc, label, errors):
    """Yield (chat_index, chat_id, message dict) and record format problems."""
    if not isinstance(doc, dict) or not isinstance(doc.get("chats"), list):
        errors.append("%s: top level must be {'chats': [...]}" % label)
        return
    for ci, chat in enumerate(doc["chats"]):
        if not isinstance(chat, dict):
            errors.append("%s: chat #%d is not an object" % (label, ci))
            continue
        cid = chat.get("chat_id")
        msgs = chat.get("messages")
        if not isinstance(msgs, list):
            errors.append("%s: chat %r has no messages list" % (label, cid))
            continue
        for mi, m in enumerate(msgs):
            if not isinstance(m, dict):
                errors.append("%s: chat %r message #%d is not an object" % (label, cid, mi))
                continue
            yield ci, cid, m


def str_list(x):
    if isinstance(x, list):
        return [s for s in x if isinstance(s, str)]
    if isinstance(x, str):
        return [x]
    return []


# ------------------------------------------------------------------ --check
def ws(t):
    return re.sub(r"\s+", " ", t).strip()


def check_dev_set(dev_path=None):
    """Assert every ref_contexts snippet exists verbatim (whitespace-normalized) in its data file(s)."""
    dev_path = dev_path or os.path.join(HERE, "dev_set.json")
    errors = []
    dev = load_json(dev_path, errors)
    raw = load_raw()
    raw_ws = {sid: ws(t) for sid, t in raw.items()}
    problems = []
    n = 0
    for _, cid, m in iter_messages(dev, "dev_set", errors):
        exp = str_list(m.get("expect_services"))
        for sid in exp:
            if sid not in raw:
                problems.append("%s: unknown service %s" % (m.get("message_id"), sid))
        for c in str_list(m.get("ref_contexts")):
            n += 1
            hits = [sid for sid, t in raw_ws.items() if ws(c) in t]
            if not hits:
                problems.append("%s: snippet not in any data file: %s" % (m.get("message_id"), c[:90]))
            elif exp and not set(hits) & set(exp):
                problems.append("%s: snippet only in %s, not in expected %s: %s" % (m.get("message_id"), hits, exp, c[:60]))
        # every must_include item must be supported by the reference answer itself
        ref = norm_full(m.get("ref_answer", ""))
        for it in str_list(m.get("must_include")):
            if not item_present(it, ref):
                problems.append("%s: must_include %r not in ref_answer" % (m.get("message_id"), it))
        for it in str_list(m.get("must_not_include")):
            if item_present(it, ref):
                problems.append("%s: must_not_include %r found in ref_answer" % (m.get("message_id"), it))
    return n, errors + problems


# ------------------------------------------------------------------ scoring
def score(dev_path, ans_path):
    errors = []
    dev = load_json(dev_path, errors)
    ans = load_json(ans_path, errors)
    raw = load_raw()
    att = Attributor(raw)

    # index answers
    ans_idx = {}
    ans_order = []
    for ci, cid, m in iter_messages(ans, "answers", errors) if ans is not None else []:
        key = (cid, m.get("message_id"))
        if key in ans_idx:
            errors.append("answers: duplicate message %r" % (key,))
        ans_idx[key] = m
        ans_order.append(key)
    dev_order = []

    results = []
    for ci, cid, dm in iter_messages(dev, "dev_set", errors) if dev is not None else []:
        mid = dm.get("message_id")
        dev_order.append((cid, mid))
        r = {"chat_id": cid, "message_id": mid, "type": dm.get("type", "unlabeled"),
             "question": dm.get("question", ""), "failed": []}
        am = ans_idx.get((cid, mid))
        labeled = "expect_status" in dm
        r["labeled"] = labeled
        # ---- format
        fmt = []
        if am is None:
            fmt.append("missing")
            answer, contexts = "", []
        else:
            answer = am.get("answer")
            if not isinstance(answer, str):
                fmt.append("answer_not_string")
                answer = "" if answer is None else str(answer)
            if answer.strip() == "" or answer.strip().lower() == "error":
                fmt.append("empty_or_error")
            contexts = am.get("contexts")
            if not isinstance(contexts, list):
                fmt.append("contexts_not_list")
            elif any(not isinstance(c, str) for c in contexts):
                fmt.append("contexts_non_string")
            contexts = str_list(contexts)
            if am.get("question") != dm.get("question"):
                fmt.append("question_changed")
        r["format_issues"] = fmt
        r["missing"] = bool({"missing", "empty_or_error"} & set(fmt))
        r["answer"] = answer
        r["contexts"] = contexts

        # ---- debug route (optional)
        route = {}
        try:
            route = am.get("debug", {}).get("route", {}) if am else {}
            if not isinstance(route, dict):
                route = {}
        except Exception:
            route = {}
        r["debug_status"] = route.get("status") if isinstance(route.get("status"), str) else None
        r["debug_services"] = str_list(route.get("services"))
        r["text_status"] = text_status(answer)

        # ---- attribution (always reported)
        exp_status = dm.get("expect_status") if labeled else None
        expected = str_list(dm.get("expect_services"))
        attributed = []
        resolved_all = []
        for c in contexts:
            ties, best = att.tie_set(c)
            res = resolve(ties, expected)
            attributed.append({"context": c[:120], "ties": ties, "score": round(best, 3), "resolved": res})
            resolved_all.extend(res)
        r["attribution"] = attributed
        r["attributed_services"] = sorted(set(resolved_all))

        if not labeled:
            results.append(r)
            continue

        a_full = norm_full(answer)
        # status
        r["status_ok"] = (not r["missing"]) and status_ok(exp_status, answer)
        r["debug_status_ok"] = (r["debug_status"] == exp_status) if r["debug_status"] else None
        if expected and r["debug_status"] is not None:
            r["debug_services_ok"] = set(r["debug_services"]) == set(expected)
        else:
            r["debug_services_ok"] = None
        # facts
        must = str_list(dm.get("must_include"))
        hit = [it for it in must if item_present(it, a_full)]
        r["facts"] = 1.0 if not must else float(len(hit)) / len(must)
        r["facts_missing"] = [it for it in must if it not in hit]
        if r["missing"]:
            r["facts"] = 0.0 if must else r["facts"]
        # wrong
        bad = [it for it in str_list(dm.get("must_not_include")) if item_present(it, a_full)]
        r["wrong_values"] = bad
        r["wrong"] = bool(bad)
        # source
        if exp_status in ("out_of_scope", "unclear"):
            r["source_covers"] = r["source_precise"] = (len(contexts) == 0)
        else:
            got = set(resolved_all)
            if dm.get("expect_any"):
                r["source_covers"] = bool(got & set(expected))
            else:
                r["source_covers"] = bool(contexts) and set(expected) <= got
            r["source_precise"] = bool(contexts) and got <= set(expected) and all(a["ties"] for a in attributed)
        # grounded
        ctx_nums = set()
        for c in contexts:
            ctx_nums |= numbers(norm_full(c))
        q_nums = numbers(norm_full(dm.get("question", "")))
        ans_nums = numbers(a_full)
        derived = set()
        cl = sorted(ctx_nums)
        for i, x in enumerate(cl):
            for y in cl[i:]:
                derived.add(x + y)
                derived.add(abs(x - y))
        ung = sorted(n for n in ans_nums if n not in ctx_nums and n not in q_nums and n not in derived)
        r["ungrounded_numbers"] = ung
        r["derived_numbers"] = sorted(n for n in ans_nums if n not in ctx_nums and n not in q_nums and n in derived)
        r["grounded"] = (not ung) and not (r["missing"])
        if exp_status == "ok" and not contexts:
            r["grounded"] = False
        # overall
        r["pass"] = bool(r["status_ok"] and r["facts"] == 1.0 and not r["wrong"])
        for k, name in [("status_ok", "status"), ("wrong", None), ("source_covers", "source_covers"),
                        ("source_precise", "source_precise"), ("grounded", "grounded")]:
            if k == "wrong":
                if r["wrong"]:
                    r["failed"].append("wrong:" + ",".join(bad))
            elif not r[k]:
                r["failed"].append(name)
        if r["facts"] < 1.0:
            r["failed"].append("facts:%s" % "/".join(r["facts_missing"]))
        if r["missing"]:
            r["failed"].insert(0, "missing")
        r["expect_status"] = exp_status
        r["expect_services"] = expected
        r["must_include"] = must
        results.append(r)

    extra = [k for k in ans_order if k not in set(dev_order)]
    if extra:
        errors.append("answers contain %d messages not in dev set, e.g. %r" % (len(extra), extra[0]))
    common = [k for k in ans_order if k in set(dev_order)]
    if common != [k for k in dev_order if k in set(common)]:
        errors.append("answers: chats/messages are in a different order than the questions file")
    return results, errors


def mean(xs):
    xs = list(xs)
    return float(sum(xs)) / len(xs) if xs else float("nan")


def summarize(rows):
    return {
        "n": len(rows),
        "score": mean(1.0 if r["pass"] else 0.0 for r in rows),
        "status_acc": mean(1.0 if r["status_ok"] else 0.0 for r in rows),
        "debug_status_acc": mean(1.0 if r["debug_status_ok"] else 0.0 for r in rows if r["debug_status_ok"] is not None),
        "facts": mean(r["facts"] for r in rows),
        "wrong": sum(1 for r in rows if r["wrong"]),
        "covers": mean(1.0 if r["source_covers"] else 0.0 for r in rows),
        "precise": mean(1.0 if r["source_precise"] else 0.0 for r in rows),
        "grounded": mean(1.0 if r["grounded"] else 0.0 for r in rows),
        "missing": sum(1 for r in rows if r["missing"]),
    }


def fmt_pct(x):
    return "  -  " if x != x else "%5.1f" % (100 * x)


def main(argv):
    if len(argv) >= 2 and argv[1] == "--check":
        n, probs = check_dev_set(argv[2] if len(argv) > 2 else None)
        print("checked %d ref_contexts snippets: %s" % (n, "OK" if not probs else "%d problems" % len(probs)))
        for p in probs:
            print("  -", p)
        return 0
    if len(argv) < 3:
        print("usage: python3 eval/score.py <dev_set.json> <answers.json>   |   python3 eval/score.py --check")
        return 0
    dev_path, ans_path = argv[1], argv[2]
    try:
        results, errors = score(dev_path, ans_path)
    except Exception as e:  # never crash
        print("scorer internal error: %r" % (e,))
        return 0

    for e in errors:
        print("FORMAT:", e)
    labeled = [r for r in results if r.get("labeled")]
    unlabeled = [r for r in results if not r.get("labeled")]
    fmt_bad = [r for r in results if r["format_issues"]]
    print("messages: %d (labeled %d, unlabeled %d), format issues in %d" % (
        len(results), len(labeled), len(unlabeled), len(fmt_bad)))
    for r in fmt_bad:
        print("  format %-12s %s" % (r["message_id"], ",".join(r["format_issues"])))

    if unlabeled:
        print("\nunlabeled messages (format + attribution only):")
        for r in unlabeled:
            print("  %-12s text_status=%-12s ctx=%d sources=%s | %s" % (
                r["message_id"], r["text_status"], len(r["contexts"]), ",".join(r["attributed_services"]) or "-",
                r["answer"][:80].replace("\n", " ")))

    if labeled:
        print("\nFAILURES:")
        nfail = 0
        for r in labeled:
            if r["failed"]:
                nfail += 1
                print("- %s [%s] failed=%s" % (r["message_id"], r["type"], ";".join(r["failed"])))
                print("    Q: %s" % r["question"][:140])
                print("    A: %s" % r["answer"][:200].replace("\n", " "))
                print("    expected: status=%s services=%s facts=%s" % (
                    r["expect_status"], ",".join(r["expect_services"]) or "-", r["must_include"]))
                if r.get("ungrounded_numbers"):
                    print("    ungrounded numbers: %s" % r["ungrounded_numbers"])
                if r["attributed_services"] or r["contexts"]:
                    print("    sources: %s (debug route: %s %s)" % (
                        ",".join(r["attributed_services"]) or "-", r["debug_status"], ",".join(r["debug_services"])))
        if not nfail:
            print("  none")

        print("\n%-22s %4s %6s %6s %6s %6s %5s %6s %6s %6s" % (
            "type", "n", "SCORE", "status", "dbgst", "facts", "wrong", "covers", "precis", "ground"))
        groups = [("OVERALL", labeled)] + [(t, [r for r in labeled if r["type"] == t]) for t in TYPES]
        others = sorted(set(r["type"] for r in labeled) - set(TYPES))
        groups += [(t, [r for r in labeled if r["type"] == t]) for t in others]
        table = {}
        for name, rows in groups:
            if not rows:
                continue
            s = summarize(rows)
            table[name] = s
            print("%-22s %4d %6s %6s %6s %6s %5d %6s %6s %6s" % (
                name, s["n"], fmt_pct(s["score"]), fmt_pct(s["status_acc"]), fmt_pct(s["debug_status_acc"]),
                fmt_pct(s["facts"]), s["wrong"], fmt_pct(s["covers"]), fmt_pct(s["precise"]), fmt_pct(s["grounded"])))
            if name == "OVERALL":
                print("-" * 84)
        print("\nSCORE = share of messages with status_ok AND all must_include facts AND no wrong value.")
    else:
        table = {}

    out = os.path.join(HERE, "last_score.json")
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"dev_set": dev_path, "answers": ans_path, "errors": errors, "summary": table,
                       "results": results}, f, ensure_ascii=False, indent=1)
        print("details -> %s" % os.path.relpath(out, ROOT))
    except Exception as e:
        print("could not write last_score.json: %r" % (e,))
    return 0


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as e:  # absolute last resort
        print("scorer crashed: %r" % (e,))
    sys.exit(0)
