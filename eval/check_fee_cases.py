# -*- coding: utf-8 -*-
"""Check eval/fee_cases.json against the raw files in data/.

Independent of the builder: re-reads data/ and dev_set.json itself.
Asserts:
  - every "lines" entry is a whitespace-normalized raw line of data/<service>.txt
  - every must_amount appears in the case's lines (digits or Arabic words);
    an amount found only elsewhere in the service file is a warning
  - must_not_amounts are disjoint from must_amounts and are fee/notes amounts of
    the service (or, with a warning, of a look-alike service of the same document)
  - total is null or equals sum(must_amounts)
  - services == services of the cases, in order; ids unique; >= 45 items
  - questions are not copies of eval/dev_set.json questions
Writes a summary to impl-logs/reports/fee_cases_report.md.
Run: python3 eval/check_fee_cases.py
"""
import difflib
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CASES = os.path.join(ROOT, "eval", "fee_cases.json")
DEV = os.path.join(ROOT, "eval", "dev_set.json")
REPORT = os.path.join(ROOT, "impl-logs", "reports", "fee_cases_report.md")

# Amounts written as words in the data files.
WORD_AMOUNTS = {"دينارين": 2, "ثلاثة دنانير": 3, "خمسة دنانير": 5, "عشرة دنانير": 10}


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def amounts_in(text):
    found = {int(n) for n in re.findall(r"\d+", text)}
    for w, v in WORD_AMOUNTS.items():
        if w in text:
            found.add(v)
    return found


def load_service(service):
    path = os.path.join(DATA, service + ".txt")
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    lines = {norm(l) for l in raw.splitlines() if norm(l)}
    return lines, norm(raw)


def fee_section_amounts(service):
    """Amounts in the notes + fees part (from the ملاحظات line to the end)."""
    with open(os.path.join(DATA, service + ".txt"), encoding="utf-8") as f:
        lines = [norm(l) for l in f if norm(l)]
    start = next((i for i, l in enumerate(lines) if l.startswith("ملاحظات")), 0)
    return amounts_in(" ".join(lines[start:]))


def document_of(service):
    """passport / family_book / id_card: the look-alike group of a service."""
    for doc in ("family_book", "id_card", "passport"):
        if service.startswith(doc):
            return doc
    return service


def dev_questions():
    with open(DEV, encoding="utf-8") as f:
        d = json.load(f)
    out = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "question" and isinstance(v, str):
                    out.append(norm(v))
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    return out


def main():
    with open(CASES, encoding="utf-8") as f:
        items = json.load(f)
    services_known = {n[:-4] for n in os.listdir(DATA) if n.endswith(".txt")}
    cache = {s: load_service(s) for s in services_known}
    fee_amounts = {s: fee_section_amounts(s) for s in services_known}
    devq = dev_questions()
    errors, warnings = [], []
    ids = Counter(it.get("id") for it in items)
    for i, n in ids.items():
        if n > 1:
            errors.append("duplicate id %s" % i)
    if len(items) < 45:
        errors.append("only %d items (< 45)" % len(items))

    for it in items:
        iid = it["id"]
        q = norm(it["question"])
        for dq in devq:
            if q == dq or difflib.SequenceMatcher(None, q, dq).ratio() > 0.8:
                errors.append("%s: too close to dev question: %s" % (iid, dq))
        case_services = []
        for c in it["cases"]:
            if c["service"] not in case_services:
                case_services.append(c["service"])
        if it["services"] != case_services:
            errors.append("%s: services %s != case services %s" % (iid, it["services"], case_services))
        for k, c in enumerate(it["cases"]):
            tag = "%s case %d (%s)" % (iid, k, c["service"])
            if c["service"] not in services_known:
                errors.append("%s: unknown service" % tag)
                continue
            file_lines, file_text = cache[c["service"]]
            if not c["lines"]:
                errors.append("%s: no lines" % tag)
            for ln in c["lines"]:
                if norm(ln) not in file_lines:
                    if norm(ln) in file_text:
                        warnings.append("%s: line is only a substring: %s" % (tag, ln))
                    else:
                        errors.append("%s: line not in file: %s" % (tag, ln))
            line_amounts = amounts_in(" ".join(c["lines"]))
            file_amounts = amounts_in(file_text)
            if not c["must_amounts"]:
                errors.append("%s: empty must_amounts" % tag)
            for a in c["must_amounts"]:
                if a not in line_amounts:
                    if a in file_amounts:
                        warnings.append("%s: must amount %s only in service file, not in lines" % (tag, a))
                    else:
                        errors.append("%s: must amount %s not in lines or file" % (tag, a))
            # must_not amounts must be real fee amounts: from the notes/fees part
            # of this service or of a look-alike service of the same document.
            doc = document_of(c["service"])
            sibling_fees = set()
            for s in services_known:
                if document_of(s) == doc:
                    sibling_fees |= fee_amounts[s]
            for a in c["must_not_amounts"]:
                if a in c["must_amounts"]:
                    errors.append("%s: %s is both must and must_not" % (tag, a))
                if a in fee_amounts[c["service"]]:
                    continue
                if a in sibling_fees:
                    warnings.append("%s: must_not amount %s comes from a look-alike service" % (tag, a))
                else:
                    errors.append("%s: must_not amount %s is not a fee of this document" % (tag, a))
            if c["total"] is not None and c["total"] != sum(c["must_amounts"]):
                errors.append("%s: total %s != sum %s" % (tag, c["total"], c["must_amounts"]))

    # ---- summary ----
    by_service = Counter(c["service"] for it in items for c in it["cases"])
    tags = Counter(t for it in items for t in it.get("tags", []))
    multi = sum(1 for it in items if len(it["cases"]) > 1)
    with_total = sum(1 for it in items for c in it["cases"] if c["total"] is not None)
    n_cases = sum(len(it["cases"]) for it in items)
    rows = ["| %s | %d |" % (s, by_service.get(s, 0)) for s in sorted(services_known)]
    report = "\n".join([
        "# Fee cases report",
        "",
        "Source: `eval/fee_cases.json` (built by `eval/build_fee_cases.py`, checked by `eval/check_fee_cases.py`).",
        "",
        "- items: %d, cases: %d" % (len(items), n_cases),
        "- multi-person / multi-service items: %d" % multi,
        "- durations/ages in words or dialect: %d" % tags.get("words", 0),
        "- missing-detail items (all candidates, total null): %d" % tags.get("missing", 0),
        "- cases with an added total: %d" % with_total,
        "- check result: %s (%d errors, %d warnings)" % ("PASS" if not errors else "FAIL", len(errors), len(warnings)),
        "",
        "Look-alike warnings are intended: services with one fee (damaged, ID renewal) use the fee of a",
        "sibling service (e.g. 125 of passport_lost for passport_damaged) as the wrong-file amount.",
        "",
        "| service | cases |",
        "|---|---|",
    ] + rows + [""]
        + (["## Errors", ""] + ["- " + e for e in errors] + [""] if errors else [])
        + (["## Warnings", ""] + ["- " + w for w in warnings] + [""] if warnings else []))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
