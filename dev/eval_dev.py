"""Run the dev set through the bot and print pass/fail per check.
    python dev/eval_dev.py [id-substring]
Checks: kind (clarify/decline), expected services present in contexts, expected substrings (any-of per group), forbidden substrings."""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gov_bot
from text_utils import normalize_for_match as N
from gov_data import load_services

TITLES = {sid: s["title"] for sid, s in load_services().items()}


def main():
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    cases = [c for c in json.load(open(Path(__file__).parent / "dev_set.json", encoding="utf-8")) if flt in c["id"]]
    ok_all, t0 = 0, time.time()
    for c in cases:
        bot, problems, res = gov_bot.Chat(), [], None
        answers = []
        for q in c["q"]:
            res = bot.ask(q)
            answers.append(res["answer"])
        ans, ctx = N(" ".join(answers)), N(" ".join(res["contexts"])) if res["contexts"] else ""
        kind = res["route"]["kind"]
        if c.get("kind") == "clarify" and not (kind == "clarify" or "؟" in res["answer"] or "?" in res["answer"]):
            problems.append("not a clarification")
        if c.get("kind") == "decline":
            if res["contexts"]:
                problems.append("decline but contexts non-empty")
            if not re.search(N("لا اعرف|لا تتوفر|غير متوفر|لا املك|لا يوجد"), ans):
                problems.append("no decline wording")
        for sid in c.get("svc", []):
            # every expected service title must appear in at least one context
            if N(TITLES[sid]) not in ctx and not any(N(TITLES[sid]) in N(x) for x in res["contexts"]):
                problems.append(f"missing source {sid}")
        for group in c.get("all", []):
            if not any(N(g) in ans for g in group):
                problems.append(f"answer lacks any of {group}")
        for bad in c.get("none", []):
            if N(bad) in ans:
                problems.append(f"answer contains forbidden '{bad}'")
        ok = not problems
        ok_all += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {c['id']:<22} {'; '.join(problems)}")
        if not ok or "-v" in sys.argv:
            print("      Q:", c["q"][-1][:80]); print("      A:", answers[-1].replace("\n", " | ")[:300])
    print(f"\n{ok_all}/{len(cases)} passed in {time.time() - t0:.0f}s  (model={__import__('config').LLM_MODEL})")


if __name__ == "__main__":
    main()
