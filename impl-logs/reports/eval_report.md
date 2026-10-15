# Eval report (pp-opus): independent dev set and scorer

## Files written
- `eval/build_dev_set.py`: the source of truth for the dev set. Each verbatim data snippet is stored once as a named constant and reused across items. Run it to regenerate `dev_set.json`. This file wasn't on the task's list; I added it so the set is easy to edit without hand-editing JSON.
- `eval/dev_set.json`: 78 chats and 90 messages, in the questions.json structure plus `type`, `expect_status`, `expect_services`, `must_include`, `must_not_include`, `ref_answer`, `ref_contexts`, and optional `note` / `expect_any`.
- `eval/score.py`: the scorer. `python3 eval/score.py <dev_set.json> <answers.json>` scores a run, and `python3 eval/score.py --check` runs the snippet check. Details go to `eval/last_score.json`. It always exits 0 and imports only `bot.schema`.
- `eval/make_perfect.py`: checks the dev set (snippets, keys, coverage minimums) and writes `eval/perfect_answers.json`.
- `eval/perfect_answers.json` and `eval/last_score.json`: generated outputs.

## Dev set coverage
- **Types:** simple_fact 9, fee_situation 14, documents_conditions 13, hidden_in_notes 9, comparison 6, dialect 5, conversation 12, long_story 5, wrong_assumption 5, unclear 5, not_in_data 7.
- **Services (count of `expect_services`):** passport_first_issue 9, passport_renewal 12, passport_lost 7, passport_damaged 8, family_book_first_issue 8, family_book_renewal 4, family_book_lost 7, family_book_damaged 7, id_card_first_issue 7, id_card_renewal 4, id_card_lost 12, id_card_damaged 5.
- **Multi-turn chats:** 10 (dev-69 to dev-78). They cover:
  - answering the bot's clarifying question ("بدي أعمل تجديد…" then "الهوية")
  - "وكم بتكلف؟" and "وإذا كنت برا البلد؟"
  - "وللهوية؟", which switches document and keeps the situation
  - an out-of-scope turn followed by an in-scope one
  - "وإذا تأخرنا عن هالمدة؟"
- **Statuses:** ok 78, unclear 5, out_of_scope 7.
- **Out-of-scope topics:** university degree attestation, birth certificate, diplomatic passport, Schengen visa, criminal-record certificate, work permit, driving licence.
- **In-scope questions with trap words:** "دفتر خدمة العلم" in a passport question (dev-27), "بطاقة الجسور" in an ID question (dev-28), "هوية مقدسية" in a passport question (dev-35).
- Nothing is copied from the brief's examples or the 5 practice questions.

## Verification
- **Snippets exist in the raw data:** `score.py --check` and `make_perfect.py` confirm that all 123 `ref_contexts` snippets appear verbatim (whitespace-normalized) in the raw file of an expected service.
- **Answer keys match the reference answers:** every `must_include` item appears in its own `ref_answer`, and no `must_not_include` value does. `make_perfect.py` asserts the coverage minimums.
- **Accuracy pass:** I re-read each item against its data file.
- **Self-test on perfect answers:**
```
type                      n  SCORE status  dbgst  facts wrong covers precis ground
OVERALL                  90  100.0  100.0  100.0  100.0     0  100.0  100.0  100.0
(every type row: 100.0 on every column, wrong = 0)
```
- **Practice files** (`score.py questions.json answers_example.json`): there are no expect keys, so it only checks format and attribution. All 6 messages are well formed. chat-05 is detected as a decline. Sources are attributed correctly; chat-01 and chat-03-2 show a family_book_first_issue/renewal tie, because the example text matches both files.
- **Negative tests** (temporary files, deleted afterwards). Each of these broken answers was caught:

| Broken answer | Caught as |
|---|---|
| "125" where 250 is right | wrong + facts |
| contexts from the wrong passport file | covers/precise |
| a number from memory ("7 أيام") | ungrounded |
| "1250" | does not trigger `must_not` "125", but is ungrounded |
| a fee answered to an unclear question | status |
| a hallucinated diplomatic-passport fee | status + wrong + grounded |
| an in-scope trap question declined | status |
| "خارج البلاد" in a non-decline | not counted as a decline |
| "عذراً، هل تقصد…" | still counted as a clarification |
| a clarify-only reply to an ok question | status |
| "error", a None answer, missing contexts, a missing chat, a non-JSON file, a nonexistent file | reported, no crash |

## Scoring choices
- **Normalization:** Arabic-Indic and Persian digits become ASCII; diacritics and tatweel are removed; alef, ya, ta-marbuta, ؤ and ئ are unified; spaces are collapsed.
- **Number words:** they are converted to digits (دينارين→2, ثلاثة→3, عشرة→10, السادسة عشر→16, الثامنة عشر→18 …) because the files themselves write some fees in words.
- **`must_include` matching:** numeric items match as whole numbers and text items as normalized substrings. An item can list alternatives with `|`.
- **Text-based status (this one counts for the score):**
  - A decline is a phrase such as لا تتوفر / عذراً / لا أملك معلومات / خارج نطاق / ليس لدي. Bare "خارج" is not used, because ok answers say "خارج البلاد".
  - A clarification is "؟" or "?" plus a word such as هل تقصد / حدد / وضح / أي.
  - An ok answer must not be a decline, and must not be only a question (less than 40 characters outside question sentences).
  - The debug-based status is reported in the `dbgst` column but not scored.
- **Source attribution:**
  - Each context is matched against every data file (menu lines stripped, punctuation removed) using idf-weighted char 4-gram overlap.
  - Text that is identical in look-alike files produces a tie. A tie that includes an expected service counts for that service, since text alone can't tell them apart.
  - `expect_any` (used only for dev-29, the oldest-son note that exists in two family book files) means one of the listed services is enough.
- **Grounded:** a number in the answer counts as grounded if it appears in the contexts or the question, or equals the sum or difference of two context numbers. That allows totals like 50+25=75 and differences like 125−100=25. Derived numbers are listed separately in `last_score.json`.

## 10 hardest items
1. **dev-11:** passport renewal at the urgent office. The +25 surcharge appears only in ملاحظات, and the answer must give the 75 total.
2. **dev-50:** a long story with a second ID loss that happened *more than* 3 years after the first, so the 10 JD pledge rule does *not* apply. Lost family book is the trap. It also has a damaged family book plus irrelevant details.
3. **dev-51:** three people and three passport services: renewal abroad 100, first issue under 16 = 25, damaged 100. 125 is the trap.
4. **dev-49:** two passport renewals (adult expired 50, child 25) plus a first ID at age 17, where the 10 JD late fine must *not* be charged.
5. **dev-14:** second passport loss within 5 years: 250 plus collection of the previous guarantee. The first-loss fee of 125 is the look-alike value.
6. **dev-71 (3 turns):** passport lost, then "وللهوية؟", then "وبقدر أطلعها من السفارة؟". The answer must stay on id_card_lost, which has no embassies, while passport_lost does allow them.
7. **dev-05 / dev-43:** where to apply. The ID card files list offices only, while the passport and family book files list embassies.
8. **dev-36 / dev-37:** third loss of an ID card or family book: investigation committee, a 50 JD guarantee, and earlier pledges collected. The amounts are spread across documents, notes and fees.
9. **dev-18 / dev-40:** family book fees written in words (دينارين / ثلاثة دنانير). Renewal depends on whether the book has expired (2 vs 3), and the first issue costs the same as an expired renewal.
10. **dev-27 / dev-28 / dev-35:** in-scope questions with trap words (دفتر خدمة العلم, بطاقة الجسور, هوية مقدسية) that a keyword router will send to the wrong document.

## Open issues
- **Ambiguous rules I avoided or narrowed** (each has a `note` on the item):
  - The amount of the "previous pledge" for a damaged family book (dev-20) isn't stated, so only "3" and "تعهد" are required.
  - A second ID loss after more than 3 years (dev-50) only requires the 5 JD fee.
  - A renewal for someone under 16 who lives abroad isn't asked at all, because two fee lines could both apply.
- **`must_not_include` limits:** it only lists values that should never appear. A few items (for example dev-14's "125") would also penalize a very thorough answer that quotes the first-loss fee just for contrast.
- **Lenient tie resolution:** for snippets that are identical across files (generic time and location lines, "الرسوم 3 دنانير"), "precise" can't catch a wrong-file pick. The facts and `must_not_include` checks cover those cases instead.
- **Approximate status detection:** it is keyword-based. A bot that declines with unusual wording (no لا تتوفر / عذراً / ليس لدي …) would be marked as not declining. Check the FAILURES list when a status score looks off.
