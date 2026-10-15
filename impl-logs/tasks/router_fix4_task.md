# TASK (pp-gpt / gpt-5.6-sol): Router round 4 — two general gaps

Context: impl-logs/reports/router_report.md (your rounds 1-3). The orchestrator added fee words to `_FIELD_PATTERNS["fees"]` (مبلغ، المبالغ، مصاري، فلوس، بيترتب علي، المجموع، كلفه ...) — keep them. Edit ONLY bot/router.py and tests/test_router.py. Do not edit bot/answer.py, bot/facts.py, bot/fees.py, bot/kb.py, bot/schema.py, eval/ or data/ (another engineer is editing bot/facts.py and bot/fees.py right now).

Keep all tests passing (`python3 -m unittest discover -s tests`) and keep the dev-set routing (`python3 main.py eval/dev_set.json --dry-run --debug --out /tmp/pp_dev_dry.json 2>/dev/null && python3 impl-logs/tasks/route_eval.py /tmp/pp_dev_dry.json`, now 90/90 status, 89/90 services) from going down.

## Gap 1: plural / dual / collective document words are not detected
"عندي توأم عمرهم ست سنين وبدي أطلعلهم جوازات لأول مرة من عمان، قديش لكل واحد؟" -> unclear (missing doc); expected passport_first_issue.
Add plural, dual and possessive-plural forms for every document: جوازات/جوازاتهم/جوازاتنا/جوازين/باسبورات, هويات/هوياتهم/هويتين/بطاقات (but NOT بطاقات الجسور / بطاقات إحصاءات), دفاتر (but NOT دفاتر خدمة العلم), and "أول جواز / أول هوية / أول دفتر" = first issue. Expired synonyms: خلصان، خلصانه، خالص، مخلّص (= expired -> renewal).

## Gap 2: one damage/loss word is shared to every document even when other clauses have their own situation
"تزوجنا من شهر ونص وبدنا نطلع دفتر عائلة، وزوجتي عمرها 22 وبدها تطلع أول جواز إلها من عمان، وأنا هويتي اهترت وبدي بدالها. شو رسوم كل شي؟"
-> got [family_book_damaged, passport_damaged, id_card_damaged]; expected [family_book_first_issue, passport_first_issue, id_card_damaged].
Rule: resolve the situation per clause (split at ، . ؛ and at "و" before a person word or a new document). A clause that has its own situation signal (including implicit first-issue verbs like نطلع/تطلع/أطلع + doc, "أول جواز", newlywed words for the family book) keeps it; only a clause with NO situation signal may borrow a situation from a neighbouring clause, and only when the user is clearly listing several documents with one shared verb (e.g. "ضاعوا الجواز والهوية"). Make sure the existing comparison / shared-situation tests still pass ("جواز بدل تالف ولا بدل فاقد" -> 2 passport services; "ضاع جوازي وهويتي" -> passport_lost + id_card_lost).

Write at least 15 new tests in your own words (not copied from these examples) for both gaps. Append a "Round 4" section to impl-logs/reports/router_report.md (changes, test counts, dev numbers) and print it.
