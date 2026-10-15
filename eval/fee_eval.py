"""Check bot/fees.py fee-line selection against eval/fee_cases.json (no model needed).

For each case: the router must find the service, and the fee lines shown to the model must
(a) contain every must_amount (in 'ينطبق' lines, or in 'غير معروف' alternatives when the case says the
detail is missing), and (b) not present any must_not_amount as applicable.
Usage: python3 eval/fee_eval.py [-v]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import fees, router  # noqa: E402
from bot.kb import load_kb  # noqa: E402
from bot.normalize import normalize  # noqa: E402


def amounts(lines):
    out = set()
    for it in lines:
        out |= set(int(x) for x in re.findall(r"\d+", normalize(re.sub(r"^\s*\d{1,2}\s*[.)\-]\s", " ", it))))
    return out


def main():
    verbose = "-v" in sys.argv
    kb = load_kb()
    data = json.load(open(os.path.join(ROOT, "eval", "fee_cases.json"), encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("items", [])
    n = ok = 0
    for item in items:
        q = item["question"]
        rt = router.route(q)
        cs = fees.cases(q, rt.get("services") or [], kb)
        for exp in item["cases"]:
            n += 1
            mine = [c for c in cs if c.service == exp["service"]]
            if len(mine) > 1 and exp.get("who"):
                named = [c for c in mine if c.who and normalize(c.who) in normalize(exp["who"])]
                mine = named or mine
            if not mine:
                print("FAIL %s %s: service not routed (got %s)" % (item["id"], exp["service"], rt.get("services")))
                continue
            shown_apply = set()
            shown_any = set()
            for c in mine:
                shown_apply |= amounts(c.apply)
                shown_any |= amounts(c.apply) | amounts([x for _, x in c.conditional])
                if c.total:
                    shown_apply.add(c.total[1])
                    shown_any.add(c.total[1])
            need = set(exp.get("must_amounts") or [])
            if exp.get("total"):
                need.add(exp["total"])
            bad = set(exp.get("must_not_amounts") or []) & shown_apply
            missing = need - shown_any
            if not missing and not bad:
                ok += 1
                if verbose:
                    print("ok   %s %s" % (item["id"], exp["service"]))
            else:
                print("FAIL %s %s who=%s missing=%s wrong=%s | %s" % (
                    item["id"], exp["service"], exp.get("who"), sorted(missing), sorted(bad), q[:110]))
                if verbose:
                    print(fees.render(mine, kb))
    print("fee cases correct: %d/%d" % (ok, n))


if __name__ == "__main__":
    main()
