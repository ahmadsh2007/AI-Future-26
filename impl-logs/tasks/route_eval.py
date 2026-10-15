"""Routing accuracy on eval/dev_set.json from a `main.py --dry-run --debug` output file."""
import json
import sys

ROOT = __file__.rsplit("/impl-logs/", 1)[0]
dev = json.load(open(ROOT + "/eval/dev_set.json", encoding="utf-8"))
ans = json.load(open(sys.argv[1], encoding="utf-8"))
amap = {(c["chat_id"], m["message_id"]): m for c in ans["chats"] for m in c["messages"]}
n = ok_st = ok_sv = 0
fails = []
for c in dev["chats"]:
    for m in c["messages"]:
        r = amap[(c["chat_id"], m["message_id"])]["debug"]["route"]
        st, sv = r["status"], r.get("resolved_shared_field") or r["services"]
        if r.get("resolved_shared_field"):
            st = "ok"
        n += 1
        good_st = st == m["expect_status"]
        exp = set(m["expect_services"])
        anyx = m.get("expect_any")
        anyx = set(x for x in anyx if isinstance(x, str)) if isinstance(anyx, list) else set()
        good_sv = True
        if m["expect_status"] == "ok":
            good_sv = set(sv) == exp or (bool(anyx) and len(sv) == 1 and sv[0] in anyx)
        ok_st += good_st
        ok_sv += good_st and good_sv
        if not (good_st and good_sv):
            fails.append((m["message_id"], m["type"], m["expect_status"], sorted(exp), st, sv, r["fields"], m["question"][:160]))
print("route status acc: %d/%d   status+services acc: %d/%d" % (ok_st, n, ok_sv, n))
for f in fails:
    print(f)
