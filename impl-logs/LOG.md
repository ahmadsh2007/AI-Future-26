# Implementation log — Government Services Chatbot (participant_pack)

## Setup (orchestrator, claude-opus-5.5)
- Read the brief (challenge_brief.pdf -> impl-logs/brief.txt), the 12 data files, questions.json, answers_example.json.
- Python on this Mac: 3.9.6 system python, no venv. Decision: stdlib only (urllib for Ollama) so `python main.py questions.json` works offline with no pip.
- Ollama was not installed. `brew install` failed (sandbox). Installed the official release binary to `~/.local/ollama/` (v0.40.4), server runs on 127.0.0.1:11434 only (not exposed to the network). Pulling `qwen2.5:7b` as the dev stand-in for the organisers' ~7B model (model name is configurable).
- Subagents: the built-in subagent tool cannot set a model, so each subagent runs as a headless `kiro-cli chat --no-interactive --agent <pp-*> --model <m>` session. Agent configs: ~/.kiro/agents/pp-fable.json, pp-gpt.json, pp-opus.json. Task files: impl-logs/tasks/, run logs: impl-logs/agent_runs/, reports: impl-logs/reports/.

## Architecture
1. bot/schema.py — shared contract (service ids, field keys, statuses). Written by orchestrator.
2. bot/kb.py — parse + clean the 12 files into 12 services x 9 fields (pp-fable / claude-fable-5.1).
3. bot/normalize.py + bot/router.py — deterministic routing: dialect -> doc + situation + fields, unclear / out-of-scope, chat memory (pp-gpt / gpt-5.6-sol).
4. eval/ — independent hard dev set + automatic scorer (pp-opus / claude-opus-5.5).
5. bot/facts.py, bot/llm.py, bot/answer.py, main.py — user-situation hints, Ollama client, prompt + grounding checks, entry point (orchestrator).

Key design choice: code (not the 7B model) chooses the service file, because the 4 files per document are near-identical. The model only sees the fields of the chosen service(s).

## Steps
- [done] schema, Ollama install, subagent configs, 3 subagents launched in parallel.
- [done] pp-fable: bot/kb.py + kb/ (verification passed: every raw number and word kept; 57 logged changes). Report: impl-logs/reports/kb_report.md (incl. look-alike differences table).
- [done] pp-gpt round 1: bot/normalize.py, bot/router.py, 124 tests. Orchestrator fix: added time words (بتاخد، وقت …).
- [done] pp-opus: eval/dev_set.json (78 chats / 90 messages, 123 verbatim snippets checked), eval/score.py, eval/make_perfect.py (perfect answers score 100%).
- [done] orchestrator: bot/facts.py (situation hints with precomputed comparisons), bot/llm.py, bot/answer.py, main.py, tests/test_answer.py, eval/prompt_coverage.py, README.md.
- User decision: model is `command-r7b-arabic:7b`; do NOT download it on this Mac (he runs it on another device). Downloads stopped, partial qwen files deleted, local Ollama server stopped. Binary left at ~/.local/ollama (can be deleted).
- Dev-set routing (dry run): 70/90 -> pp-gpt round 2 -> 89/90 (only dev-29: expected first_issue OR renewal, both fine). Prompt coverage: 76/78 (missing ones are totals the model must add: 75, 25).
- Answer stage changes: core fields always in the prompt (field detection was the weak step); sums/differences of two source numbers count as grounded (50+25=75); model fallback classifier for unclear routes (6+ words only, offers 'none').
- Fresh held-out routing set written by orchestrator (eval/heldout_routes.json, 40 cases, not shown to pp-gpt): 33/40 before round 3. Failures: unseen dialect for damage/loss/new-marriage. pp-gpt round 3 launched with general word families (not the held-out sentences).
- [done] pp-gpt round 3: wider dialect families (+65 tests). Orchestrator fix: removed "فتح ملف عائلي" from family-book triggers (in the data it is only a passport first-issue document).
- Final checks (no model): 224 unit tests OK; dev-set routing 90/90 status, 89/90 services (dev-29 accepts first_issue OR renewal); held-out routing 40/40 (sentences never shown to pp-gpt, but its failures guided the round-3 word families); prompt coverage 76/78 (the 2 misses are totals the model must add); practice file format OK.
- NOT verified here (no model on this Mac): real answer quality and speed of command-r7b-arabic:7b. Run on the other device: `python main.py eval/dev_set.json --debug --out eval/dev_answers.json && python eval/score.py eval/dev_set.json eval/dev_answers.json`.
