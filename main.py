"""Entry point:  python main.py questions.json   ->  writes answers.json next to questions.json.
Offline: needs Ollama running with the event model pulled (set LLM_MODEL / LLM_BACKEND if different)."""
import json
import sys
import time
from pathlib import Path

import gov_bot

ERROR_ANSWER = "error"


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python main.py questions.json")
    src = Path(sys.argv[1])
    out = src.parent / "answers.json"
    data = json.loads(src.read_text(encoding="utf-8-sig"))

    t0 = time.time()
    for chat in data["chats"]:
        bot = gov_bot.Chat()   # every chat is a new user
        for msg in chat["messages"]:
            try:
                res = bot.ask(msg["question"])
                msg["answer"], msg["contexts"] = res["answer"], res["contexts"]
            except Exception as e:   # one bad message must not stop the run
                print(f"[{msg.get('message_id')}] ERROR {type(e).__name__}: {e}")
                msg["answer"], msg["contexts"] = ERROR_ANSWER, []
            print(f"[{msg.get('message_id')}] {time.time() - t0:5.0f}s  {msg['question'][:50]} -> {msg['answer'][:70]}")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")  # partial file after every chat
    print(f"wrote {out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
