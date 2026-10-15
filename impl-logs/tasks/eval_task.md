# TASK (pp-opus / claude-opus-5.5): Build an independent evaluation set and scorer

The hidden test questions are not available; we need our own hard dev set to measure the bot.

Project folder: /Users/alsalayh/Downloads/participant_pack (Python 3.9 stdlib only, no pip). Read first:
- impl-logs/brief.txt (the challenge brief; read ALL of it — section 4 "Questions you will face", section 5 file formats and section 6 "How you are evaluated" define what you must cover)
- questions.json and answers_example.json (practice input and expected output format)
- bot/schema.py (service ids == data file names; field keys). Do NOT edit it.
- ALL 12 files in data/ — read every line. Never modify data/.

Other engineers are writing bot/kb.py, bot/router.py, bot/answer.py in parallel. Your eval must be INDEPENDENT of them: do not import bot.kb / bot.router / bot.answer / bot.normalize (you may import bot.schema). Your files: eval/dev_set.json, eval/score.py, eval/make_perfect.py. Work without asking questions; make reasonable choices and report them.

## 1) eval/dev_set.json
Same structure as questions.json (`{"chats":[{"chat_id","messages":[{"message_id","question"}]}]}`), with extra keys on each message:
- "type": one of simple_fact | fee_situation | documents_conditions | hidden_in_notes | comparison | dialect | conversation | long_story | wrong_assumption | unclear | not_in_data
- "expect_status": "ok" | "unclear" | "out_of_scope"
- "expect_services": [service ids the answer must use] ([] for unclear/out_of_scope)
- "must_include": [short key facts a correct answer MUST contain, e.g. "50", "180", "أكبر الأبناء"] — numbers as ASCII digits; keep each item short so wording differences don't matter (prefer numbers and 1-2 word key terms)
- "must_not_include": [values that would be WRONG here, typically the value from a look-alike service, e.g. "125" where the right answer is "100"] — only values that should truly never appear in a correct answer
- "ref_answer": a short correct Arabic answer written ONLY from the documents
- "ref_contexts": exact snippets copied verbatim from the data file(s) that support the ref_answer
- optional "note"

Size: at least 45 chats / 60 messages. Cover all 12 services (each at least 3 times) and every type at least 4 times. Make them HARD and realistic, like the hidden test: Jordanian dialect (الباسبور، الهوية، اهترى، شو بلزمني، قديش بدفع، ضاع، انسرق), fee rules that depend on age / expiry / days left / inside vs outside Jordan / how many times lost / within N years / urgent office (+25), facts hidden in ملاحظات, comparisons between look-alike services (which is more expensive / what differs), long stories with several people and irrelevant details where every asked part must be answered, wrong assumptions to correct (e.g. a wife needs her husband's approval), unclear questions that need a clarifying question (e.g. "بدي أجدد، شو المطلوب؟"), out-of-scope questions incl. related-sounding services not in the data (university certificate attestation, birth certificate, diplomatic passport, visas, flight prices, driving licence …) AND in-scope questions that contain trap words ("دفتر خدمة العلم" inside a passport question, "بطاقة الجسور" inside an ID question). Include at least 8 multi-turn chats (2-3 messages) with follow-ups like "وكم بتكلف؟", "وإذا كنت برا البلد؟", "وللهوية؟", and one where the user answers the bot's clarifying question (e.g. msg1 unclear "بدي أجدد", msg2 "الهوية" -> id_card_renewal). Do NOT copy the brief's example questions verbatim (paraphrase), and do not reuse the 5 practice questions.

ACCURACY IS CRITICAL: every number/fact in ref_answer and must_include must be traceable to a ref_contexts snippet that exists verbatim in the raw file. Do a final pass where, for every message, you re-read the relevant data file(s) and confirm. If a fee rule is ambiguous in the document, either avoid that question or keep must_include to the unambiguous part, and say so in "note". Also write a script check (inside make_perfect.py or score.py --check) that asserts every ref_contexts snippet exists (whitespace-normalized) in the raw data.

## 2) eval/score.py
Usage: `python3 eval/score.py eval/dev_set.json <answers.json>`. The answers file has the same structure with "answer" and "contexts" added per message (and maybe extra debug keys, e.g. "debug": {"route": {...}} — use debug.route.status / debug.route.services if present, never require them). Match messages by chat_id + message_id. Per message compute:
- status_ok: out_of_scope -> answer declines (phrases like "لا تتوفر", "لا أملك معلومات", "عذراً", "خارج", "لا يوجد لدي", "ليست لدي"); unclear -> answer asks a question (contains "؟" or "?" and words like "أي", "هل تقصد", "ماذا تقصد", "حدد", "وضح", "أيّ"); ok -> neither a decline nor only a question. Report both debug-based and text-based status; use text-based for the score.
- facts: fraction of must_include present in the answer (normalize both: Arabic-Indic digits -> ASCII, remove diacritics/tatweel, unify alef/ya/ta-marbuta, collapse spaces).
- wrong: any must_not_include present as a whole token/number (e.g. "25" must not match inside "125") -> failure.
- source: attribute every context string to its best-matching service by char 4-gram overlap against the raw data files (menu lines stripped); report "covers" (attributed set ⊇ expect_services) and "precise" (no service outside expect_services). For out_of_scope/unclear, source ok = contexts is [].
- grounded: every number in the answer appears in the contexts (after normalization); report ungrounded numbers.
- missing: message missing, or answer == "" or "error".
Print one line per failing message (message_id, type, failed checks, answer truncated to 200 chars, expected facts) and a summary table: overall and per type — status acc, mean facts, wrong count, source covers/precise, grounded rate, and an overall score = mean over messages of (status_ok and facts==1 and not wrong). Also write details to eval/last_score.json. Exit code 0 always. Must not crash on malformed input (missing keys, wrong types) — report instead.

## 3) eval/make_perfect.py
Builds eval/perfect_answers.json from dev_set (answer = ref_answer, contexts = ref_contexts, plus debug.route from expect_status/expect_services). Run score.py on it: it must score ~100% on every check (if not, fix the dev set or the scorer). Also run score.py with questions.json as the dev set and answers_example.json as answers (no expect keys — must handle gracefully and just check format).

## Report
Write your final report to impl-logs/reports/eval_report.md and also print it: files written, counts by type and by service, the self-test score output, and the 10 hardest items with why they are hard.
