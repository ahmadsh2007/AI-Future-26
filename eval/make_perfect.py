# -*- coding: utf-8 -*-
"""Self-test for the eval kit.

1. Asserts every ref_contexts snippet in eval/dev_set.json exists verbatim
   (whitespace-normalized) in the raw data file of an expected service, and that
   must_include / must_not_include are consistent with ref_answer.
2. Prints dev-set coverage (types, services, multi-turn chats) and asserts the
   minimums from the task.
3. Writes eval/perfect_answers.json (answer = ref_answer, contexts = ref_contexts,
   debug.route from expect_status / expect_services).

Usage: python3 eval/make_perfect.py   then   python3 eval/score.py eval/dev_set.json eval/perfect_answers.json
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score  # noqa: E402  (eval/score.py, independent of bot/*)

DEV = os.path.join(HERE, "dev_set.json")
OUT = os.path.join(HERE, "perfect_answers.json")
EXPECT_KEYS = ("type", "expect_status", "expect_services", "must_include", "must_not_include",
               "ref_answer", "ref_contexts")


def coverage(dev):
    types, services, multi = {}, {}, 0
    n_msgs = 0
    for chat in dev["chats"]:
        if len(chat["messages"]) > 1:
            multi += 1
        for m in chat["messages"]:
            n_msgs += 1
            types[m["type"]] = types.get(m["type"], 0) + 1
            for s in m["expect_services"]:
                services[s] = services.get(s, 0) + 1
    return n_msgs, types, services, multi


def main():
    n, problems = score.check_dev_set(DEV)
    with open(DEV, encoding="utf-8") as f:
        dev = json.load(f)
    for chat in dev["chats"]:
        for m in chat["messages"]:
            for k in EXPECT_KEYS:
                if k not in m:
                    problems.append("%s: missing key %s" % (m.get("message_id"), k))
            if m.get("type") not in score.TYPES:
                problems.append("%s: bad type %r" % (m.get("message_id"), m.get("type")))
            if m.get("expect_status") not in ("ok", "unclear", "out_of_scope"):
                problems.append("%s: bad expect_status" % m.get("message_id"))
            if m.get("expect_status") != "ok" and (m.get("expect_services") or m.get("ref_contexts")):
                problems.append("%s: non-ok item must have no services/contexts" % m.get("message_id"))
            if m.get("expect_status") == "ok" and not m.get("ref_contexts"):
                problems.append("%s: ok item without ref_contexts" % m.get("message_id"))

    n_msgs, types, services, multi = coverage(dev)
    print("dev set: %d chats, %d messages, %d multi-turn chats" % (len(dev["chats"]), n_msgs, multi))
    print("types:   " + ", ".join("%s=%d" % (t, types.get(t, 0)) for t in score.TYPES))
    print("services:" + ", ".join(" %s=%d" % (s, services.get(s, 0)) for s in score.SERVICE_IDS))
    if len(dev["chats"]) < 45 or n_msgs < 60:
        problems.append("dev set too small")
    if multi < 8:
        problems.append("need >= 8 multi-turn chats")
    problems += ["type %s < 4" % t for t in score.TYPES if types.get(t, 0) < 4]
    problems += ["service %s < 3" % s for s in score.SERVICE_IDS if services.get(s, 0) < 3]

    print("snippet check: %d ref_contexts snippets verified" % n)
    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for p in problems:
            print("  -", p)
    assert not problems, "dev set check failed"
    print("dev set check: OK")

    out = {"chats": []}
    for chat in dev["chats"]:
        msgs = []
        for m in chat["messages"]:
            msgs.append({
                "message_id": m["message_id"],
                "question": m["question"],
                "answer": m["ref_answer"],
                "contexts": list(m["ref_contexts"]),
                "debug": {"route": {"status": m["expect_status"], "services": list(m["expect_services"])}},
            })
        out["chats"].append({"chat_id": chat["chat_id"], "messages": msgs})
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("wrote %s" % os.path.relpath(OUT, os.path.dirname(HERE)))


if __name__ == "__main__":
    main()
