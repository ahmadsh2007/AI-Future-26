# Prompt to paste into the other team's AI session

You are taking over a hackathon project: an Arabic government-services chatbot (Jordan: passport, family book, smart ID). It is scored automatically on ACCURACY. Time only breaks ties between teams with equal scores. The code works end to end but scores 70.0 on our 90-question dev set with the real model, and the failures are well understood. Your job is to raise the score without breaking anything.

## Read first (in this order)
1. `docs/Government_Chatbot_Handoff.md`: full context, the organizers' rules, all test results and all 34 failing questions with the bot's answer and the reference answer.
2. `eval/results/2026-10-15_command-r7b/FAILURES.md` and `score_report.txt`: same failures in raw form and the scorer's output (baseline).
3. `bot/answer.py` (prompt and checks), `bot/facts.py` (situation hints), `bot/router.py` (routing).

Work on branch `feature/gov-chatbot` (GitHub: ahmadsh2007/AI-Future-26).

## Hard rules (from the organizers; do not violate)
- Answers must be generated at run time by the provided model: `command-r7b-arabic:7b` through Ollama. No other AI model, no online AI service. Local embeddings or rerankers are allowed but are not needed.
- Only the 12 files in `data/` are knowledge. No pre-written answers. You may clean and restructure the data but must not change its facts.
- The program is run as `python main.py questions.json` on a laptop with the internet OFF and must write `answers.json` next to it. Each message needs `answer` and `contexts` (the data pieces actually used; `[]` when nothing). Keep `chats / chat_id / messages / message_id / question` untouched, answer EVERY message, UTF-8, per-message error handling.
- Judging: (1) correct answer for the user's situation, nothing wrong added; out-of-scope declined; unclear questions get a clarifying question; (2) `contexts` come from the right service(s); (3) the answer is supported by `contexts`.
- The model has no thinking mode (`ollama show` lists only completion and tools). Improve prompt and code, not reasoning mode.

- Refusal wording: the organizers did NOT mandate a fixed string. Their only example (flight-ticket question, `contexts = []`) is: `عذراً، لا تتوفر لدي معلومات عن أسعار تذاكر الطيران. أستطيع المساعدة في خدمات جواز السفر ودفتر العائلة والبطاقة الذكية فقط.` Unclear questions must ask which document is meant.

## What to fix, in priority order
0. **Out-of-scope declines are never model-written (7 of 7 in the dev run).** The model's decline (e.g. `أنا آسف، لا يمكنني الإجابة على هذا السؤال…`) is rejected by `_is_decline` / `DECLINE_WORDS` in `bot/answer.py`, so the fixed template is always used. Add the wording the model really uses and check that valid declines are accepted. This keeps declines model-generated, as the organizers require.
1. **False declines (14 questions).** Routing is correct, yet the model copies the refusal sentence from rule 2 of `SYSTEM_ANSWER` ("عذراً، لا تتوفر لدي هذه المعلومة في وثائق الخدمة.") even when the answer is in the sources, mostly on short follow-ups and some fee questions. Ideas: retry once with a prompt that has no ready-made refusal sentence when routing is ok; accept the decline only if the retry also declines; rewrite follow-ups into standalone questions in code.
2. **Wrong fee line / missing list items (15 questions).** Extend `bot/facts.py` so it produces one explicit "applicable fee line" hint (exact source sentence plus computed total, e.g. 50 + 25 = 75) and make the prompt copy it. For documents or conditions questions make sure the full list is returned.
3. **Conversation follow-ups** (bonus category, can only add points): inherited service and situation must reach the prompt and the fee hints.
4. **Tighter `contexts` (5 questions):** drop items from services not in the route; require a minimum overlap with the answer.
5. **Speed only after accuracy:** shorter prompts, skip extra model calls when the router is certain. Never trade accuracy for time.

## Do not break
- `answers.json` format and the "answer every message" behaviour.
- Offline operation (nothing but local Ollama at 127.0.0.1:11434).
- Declines and clarifying questions stay model-generated (fixed templates only when the model fails).
- The 224 unit tests: `python3 -m unittest discover -s tests`.
- Do not tune answers to the dev questions themselves (hidden test set is different and much larger). Prefer general fixes. If you add test cases, add them as NEW items, never edit the existing reference answers.

## How to test
```bash
ollama list     # must show command-r7b-arabic:7b (5.1 GB; do not delete it)
python3 main.py eval/dev_set.json --debug --out eval/dev_answers.json
python3 eval/score.py eval/dev_set.json eval/dev_answers.json
python3 -m unittest discover -s tests
```
Baseline: overall 70.0 (status 84.4, facts 75.0, wrong values 0, source covers 83.3, source precise 76.7, grounded 82.2); conversation 41.7, wrong_assumption 40, fee_situation 50; average 11.4 s per question. If you do not have the model on your machine, still make the changes and unit tests pass, and say clearly that the model run was not done.

## When you finish: report back with
1. The list of files changed and a one-line reason for each.
2. The new score table (same format as above) next to the baseline, and the list of dev questions that still fail.
3. Any new risk, and anything you chose not to do.
4. A commit on `feature/gov-chatbot` (do not push to `main`; do not open a pull request unless asked).

If you are unsure whether a change might violate an organizer rule, do not do it and ask instead.
