# Government Services Chatbot (Jordan CSPD: passport, family book, smart ID)

## Run

Requirements: Python 3.8+ (standard library only, no `pip install`), and Ollama with the model.

```bash
# once, while online
ollama pull command-r7b-arabic:7b

# the evaluation command (Ollama must be running: the desktop app, or `ollama serve`)
python main.py questions.json        # -> answers.json next to questions.json
```

- Model name is in `config.json` (`"model"`). Override without editing: `OLLAMA_MODEL=other:tag python main.py questions.json`.
- `num_ctx` is set to 8192 in `config.json` (Ollama's default window is small and cuts text silently).
- Before the evaluation: turn Wi-Fi off and run once to confirm it works offline.
- Optional flags: `--debug` (adds a `debug` key per message: route, timing; the graders ignore extra keys), `--out PATH`, `--dry-run` (no model, only for testing the pipeline).

## Check quality before the evaluation

```bash
python -m unittest discover -s tests                         # router + answer-stage tests (no model needed)
python main.py eval/dev_set.json --debug --out eval/dev_answers.json   # 90 hard dev questions, real model
python eval/score.py eval/dev_set.json eval/dev_answers.json # score: status, facts, wrong values, sources, grounding
python main.py questions.json && python eval/score.py questions.json answers.json   # practice file: format check
```

## Approach (for the walkthrough)

1. Data (`bot/kb.py`). Each of the 12 files is parsed into the same 9 fields (who, where, conditions, documents, procedure, time, partners, notes, fees). Website menu lines are removed, numbering is unified, clear typos are fixed, one copy-paste duplicate is removed, and amounts written in words get the digits added, e.g. "ثلاثة أشهر (3)". No fact is changed: a check confirms every number and every word of each raw file is still in the cleaned data. Every change is listed in `kb/cleaning_log.txt`.
2. Finding the right file (`bot/router.py`). Code picks the file, not the model, because the 4 files of each document are almost the same. Dialect is normalized (الباسبور، الهوية، اهترى، ضاع، خلص…). The code finds the document (passport / family book / ID) and the situation (first time / renewal / lost / damaged) for each part of the question. It also finds the fields asked (fees, documents, time…). It handles comparisons and long stories with several people. It stops trap words from being taken as the document (e.g. "دفتر خدمة العلم" is a passport document, "بطاقة الجسور" is not the smart ID). If the document or situation is missing, it asks the user what they mean. If the topic is not in the 12 files, it declines. In a chat, a follow-up takes the missing parts from earlier messages.
3. The user's situation (`bot/facts.py`). A 7B model is weak at comparing numbers, so code reads the user's details first: age, days left on the passport, inside or outside Jordan, how many times it was lost, urgent office, military, and so on. It does the comparisons itself, e.g. "17 is more than 16", "3 months is about 90 days, less than 180". Then it gives these to the model as plain hints.
4. Answering (`bot/answer.py`). The model (`command-r7b-arabic:7b`, temperature 0) only sees the fields of the chosen service(s). Notes are always included because extra fees and deadlines hide there. The prompt rules are: use only the sources, apply the fee rule that fits the user, answer every part, correct wrong assumptions, and say "not available" instead of guessing.
5. Stopping made-up answers. Every number in the answer must come from the sources, the question, or a sum of two source amounts (e.g. 50 + 25 urgent = 75). If not, the model is asked again once. Declines and clarifying questions are also written by the model, but they are rejected if they contain numbers. A fixed text is used only if the model fails.
6. Contexts. Only the items the answer actually used are returned, in the form "<service> - <field>: <items>". The code checks which items share numbers and words with the answer. Declines and clarifying questions return `[]`.
7. Robust run. Every message is filled with `"error"` first and the file is saved after every chat. Errors are caught per message. All files are read and written as UTF-8. If Ollama is down, the bot still writes short answers taken directly from the documents.

## Layout

```
main.py              entry point
config.json          model name + Ollama options
bot/schema.py        service ids, field names (shared contract)
bot/kb.py            parse + clean the 12 files (python -m bot.kb writes kb/ for review)
bot/normalize.py     Arabic normalization
bot/router.py        service / field / unclear / out-of-scope / chat memory
bot/facts.py         user situation -> hints with precomputed comparisons
bot/answer.py        prompt, number checks, context selection
bot/llm.py           Ollama HTTP client (stdlib)
tests/               unit tests (no model needed)
eval/                90-message dev set, scorer, prompt-coverage check
```

---
Original repo note: first link: https://claude.ai/share/05296964-50a2-42df-b7d2-d2471e58cb42
