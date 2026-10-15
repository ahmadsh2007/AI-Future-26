# TASK (pp-gpt / gpt-5.6-sol): Router fixes, round 2

You wrote bot/normalize.py, bot/router.py and tests/test_router.py (report: impl-logs/reports/router_report.md). The orchestrator added a few time-field words to `_FIELD_PATTERNS["time"]` in bot/router.py (keep them). Do not edit bot/schema.py, bot/kb.py, bot/answer.py, bot/facts.py, eval/ or data/.

An independent dev set (eval/dev_set.json, written by another agent) found these routing errors. Fix them as GENERAL rules that also cover similar wordings. Do NOT copy dev-set questions into the tests; write your own new paraphrases for every category (at least 3 new tests per category), so the dev set stays an honest held-out check. Keep all existing tests passing.

Measure with this command (prints accuracy + remaining failures) — run it before and after:
```
python3 main.py eval/dev_set.json --dry-run --debug --out /tmp/pp_dev_dry.json 2>/dev/null && python3 impl-logs/tasks/route_eval.py /tmp/pp_dev_dry.json
```
Baseline: status 81/90, status+services 70/90.

## Failures by category (question -> got -> expected)
1. "أول مرة" as a modifier of loss/damage wrongly adds first_issue:
   - "انسرق الباسبور تبعي بإسطنبول وهاي أول مرة بيضيع مني..." -> [passport_lost, passport_first_issue], expected [passport_lost]
   - "يا جماعة انسرق الباسبور مني بعمان، أول مرة بيصير معي..." -> same error
   - "كم رسوم جواز سفر بدل فاقد إذا أول مرة بضيع؟" -> same error (then the follow-ups "وللهوية؟" and "وبقدر أطلعها من السفارة؟" inherit [id_card_lost, id_card_first_issue], expected [id_card_lost])
   - "شو أغلى: جواز بدل فاقد لأول مرة ولا جواز بدل تالف؟" -> [lost, first_issue, damaged], expected [passport_damaged, passport_lost]
   Rule idea: "أول/لأول/أول مرة/المرة الأولى/ثاني مرة/تالت مرة..." next to (or in the same clause as) a lost/damaged word, or right after "بدل فاقد/بدل تالف", is a count of losses, not a first issue. Also "بيصير معي" style.
2. Negated issuance = first issue ("never got one"):
   - "عمري 20 سنة وعمري ما طلعت هوية، بدي أطلعها هلأ" -> unclear, expected id_card_first_issue
   - "تزوجنا من 4 شهور وما فتحنا دفتر عائلة لهلأ" -> unclear, expected family_book_first_issue
   - "ابني الكبير عمره 17 وعمره ما طلع هوية" (inside a long story that also renews passports) -> id_card_renewal (situation shared from another clause), expected id_card_first_issue
   - "تزوجت قبل سنة، وما طلعنا دفتر عائلة لليوم ... وكمان زوجتي جوازها منتهي ... بدها تجدده" -> family_book_renewal, expected family_book_first_issue (+ passport_renewal)
   Rule idea: "(عمري|عمره|عمرها)? ما (طلعت|طلع|طلعنا|طلعت|عملت|فتحنا|فتحت|استخرجت)", "لسا ما طلعت", "ما عندي/ما معي (هوية|جواز|دفتر)", "ولا مرة طلعت" -> first_issue for that doc. A clause-local situation must win over a situation shared from another clause.
3. Missing situation verbs / forms (check suffixes ه/ها/هم and prefixes ب/بت/بي/ت/ي/ن):
   - renewal: "بدي أجدده", "بدها تجدده", "لازم يتجدد", "نجددها", "يتجدد", "تتجدد"
   - lost: "بتضيع", "بيضيع", "تضيع", "يضيع", "ضاعت", "بضيع", "ضايعه"
   - damaged: "متلف/متلفه" (deliberately damaged), "اتلفت", "انكسرت/انكسر/مكسور/مكسوره/كسرت", "الشريحه طالعه/خربانه", "انمسحت/ممسوح/باهت", "وقعت عليه مي", "مبلول", "انغسل/غسلتها", "مخزوق/انخزق"
   - "أطلع وحدة بدالها / بداله / بدل" means a replacement, never first_issue.
   Failing examples: "جوازي لسا ساري لسنة ونص، بس بدي أجدده..." (unclear, expected passport_renewal), "هاي تالت مرة بتضيع فيها هويتي" (unclear, expected id_card_lost), "إذا الموظف شك إني متلف الجواز عن قصد، شو بصير بالمعاملة؟" (unclear, expected passport_damaged), "الهوية تبعتي انكسرت ونص الشريحة طالعة، شو بلزمني عشان أطلع وحدة بدالها؟" (id_card_first_issue, expected id_card_damaged).
4. Trap words that are NOT the document:
   - "هوية مقدسية / الهويات المقدسية / هوية القدس" is a Jerusalem ID mentioned in passport fee notes, NOT the smart ID: "معي هوية مقدسية، بدفع رسوم تجديد الجواز زي الأردنيين ولا أكثر؟" -> [id_card_renewal, passport_renewal], expected [passport_renewal]
   - "دفتر خدمة العلم": when it appears, a later bare "الدفتر/دفتر" (without العائلة/العيلة) refers to it: "معي دفتر خدمة العلم ومأجل، وبدي أطلع جواز سفر لأول مرة. شو كمان بدي أجيب غير الدفتر؟" -> [passport_first_issue, family_book_first_issue], expected [passport_first_issue]
5. Family-book topics without a situation:
   - "أبوي وأمي الله يرحمهم توفوا الاثنين، مين فينا بصير رب الأسرة بدفتر العيلة؟" -> unclear; expected family_book_first_issue (the head-of-family rules are in first_issue and renewal notes; default to first_issue when no situation is given and the topic is رب الأسرة / وفاة رب الأسرة / تعدد الزوجات).
6. Status unclear although services were resolved — find out why and fix:
   - "طلعت جواز بدل فاقد ودفعت كفالة، وهلأ ضاع الجواز الجديد كمان. شو بصير؟" -> status unclear, services [passport_lost]; expected ok [passport_lost] ("طلعت جواز بدل فاقد" is a past lost-replacement, not a first issue)
   - Long story: "...امبارح انسرقت محفظتي بالباص وفيها الهوية، وقبل 4 سنين كمان كانت ضاعت مني هوية وطلعت بدالها. وكمان دفتر العيلة وقعت عليه مي وصار تالف. بدي أعرف قديش رسوم الهوية وقديش رسوم الدفتر." -> status unclear with services [id_card_lost, family_book_damaged]; expected ok. Rule: if every doc mentioned resolved to a service, a leftover unresolved situation word (e.g. from "طلعت بدالها") must not make the whole question unclear.
7. Out-of-scope missed:
   - "كم رسوم تجديد تصريح العمل للعامل الوافد؟" -> unclear (renewal without doc); expected out_of_scope. Add unsupported subjects: تصريح عمل/تصريح العمل/اذن عمل/عامل وافد/العماله الوافده, رخصه مهن, سجل تجاري, ترخيص سياره/تسجيل سياره, تامين صحي, ضمان اجتماعي, اقامه (as subject), بطاقه بنك/فيزا كارد, جواز سفر لغير الاردنيين ... General rule: a situation word (تجديد/بدل فاقد/...) whose object is an explicit unsupported noun is out_of_scope, not unclear.

## Report
Append a "Round 2" section to impl-logs/reports/router_report.md: before/after numbers from the command above, what you changed, new test count, and any dev failure you chose not to fix (with the reason). Print it at the end.
