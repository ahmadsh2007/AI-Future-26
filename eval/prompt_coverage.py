"""Prompt coverage check (no Ollama needed).

For every dev-set message, run the bot with a fake LLM that records the prompt, then check that every
`must_include` fact is present in the prompt (sources + situation hints). A fact missing from the
prompt can never be answered correctly by the model, so this is an upper bound on answer accuracy.

Usage: python3 eval/prompt_coverage.py [eval/dev_set.json]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot.answer import Bot  # noqa: E402
from bot.normalize import normalize  # noqa: E402


class RecordingLLM:
    def __init__(self):
        self.prompts = []

    def chat(self, system, user, num_predict=None, temperature=None):
        self.prompts.append(user)
        return ""  # empty -> bot uses its extractive fallback; we only need the prompt


def present(fact, text):
    for alt in str(fact).split("|"):
        a = normalize(alt)
        if re.fullmatch(r"\d+", a):
            if re.search(r"(?<!\d)%s(?!\d)" % a, text):
                return True
        elif a and a in text:
            return True
    return False


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "eval", "dev_set.json")
    dev = json.load(open(path, encoding="utf-8"))
    llm = RecordingLLM()
    bot = Bot(llm)
    n = full = 0
    misses = []
    for chat in dev["chats"]:
        history = []
        for m in chat["messages"]:
            before = len(llm.prompts)
            ans, ctx, dbg = bot.answer(m["question"], history)
            history.append({"question": m["question"], "route": dbg.get("route") or {}, "answer": ans})
            if m.get("expect_status") != "ok":
                continue
            prompt = normalize(" ".join(llm.prompts[before:]))
            need = m.get("must_include") or []
            missing = [f for f in need if not present(f, prompt)]
            n += 1
            if not missing:
                full += 1
            else:
                misses.append((m["message_id"], m.get("type"), (dbg.get("route") or {}).get("services"), missing))
    print("prompt contains all must_include facts: %d/%d ok-messages" % (full, n))
    for x in misses:
        print("  MISS", x)


if __name__ == "__main__":
    main()
