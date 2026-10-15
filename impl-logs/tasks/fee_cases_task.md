# TASK (pp-opus / claude-opus-5.5): Independent fee-situation test cases

Project: /Users/alsalayh/Downloads/participant_pack (Python 3.9 stdlib only). Read ALL 12 files in data/ (every line), and impl-logs/brief.txt section 3-4. Do not read or edit anything in bot/ (the code under test must stay independent of your cases), and do not edit eval/dev_set.json or data/.

Write `eval/fee_cases.json`: a list of at least 45 NEW realistic user situations (Jordanian dialect and MSA mixed, NOT copied from eval/dev_set.json — open it only to avoid duplicates) where the correct fee depends on the person's situation. Each item:
```
{"id": "fee-01",
 "question": "...",                       # one user message
 "services": ["passport_renewal"],        # service ids (== data file names) the question is about, in mention order
 "cases": [                               # one entry per person/document that needs a fee
   {"service": "passport_renewal",
    "who": "المستخدم",                      # short Arabic label of the person
    "must_amounts": [50, 25],             # every amount (in JD) that MUST be in a correct answer for this case
    "total": 75,                          # only when the document clearly ADDS amounts (e.g. +25 urgent office, +10 fine); else null
    "must_not_amounts": [100],            # amounts from other fee lines that would be WRONG here
    "lines": ["50 دينار لمن هم فوق سن السادسة عشر بيوم ...", "يضاف 25 دينار ..."]   # the exact raw source lines that apply (copied verbatim, whitespace-normalized)
   }],
 "note": "why"}
```
Coverage (at least): passport_renewal (under 16; adult expired; adult with <180 days left; adult with >180 days left; still valid but pages full; abroad; military; marital-status change; urgent office +25 combined with another line), passport_first_issue (under 16, adult inside, adult abroad, military), passport_lost (first loss, second loss within 5 years -> 250 + previous bail collected, second loss after more than 5 years), passport_damaged, family_book_first_issue (within 90 days of the marriage contract, after 90 days -> 2 + 10 fine), family_book_renewal (expired -> 2, not expired -> 3), family_book_lost (first, second within 3 years, third -> 50 bail), family_book_damaged (within 3 years of previous issue / later), id_card_first_issue (under 18, 18 or older without a card -> +10 fine), id_card_renewal, id_card_lost (first, second within 3 years -> 10 pledge first, third -> 50 bail, second after more than 3 years), id_card_damaged. Include at least 8 multi-person / multi-service questions (2-3 people, irrelevant details mixed in), at least 6 questions where durations are written in words or dialect ("سنة ونص", "شهرين", "تلات سنين", "ستطعش سنة", "من شي أربع شهور"), and at least 4 where the needed detail is missing so no single line can be chosen (then "must_amounts" = all candidate amounts and "total": null, and say so in "note").

Accuracy rules: every amount and every "lines" entry must be verbatim-checkable in the raw file of that service. Where the document is genuinely ambiguous (e.g. under 16 AND abroad for passport renewal), do not include that case. Write a small checker `eval/check_fee_cases.py` that asserts every "lines" entry exists (whitespace-normalized) in data/<service>.txt and every must_amount appears in the case's lines or in that service file; run it until it passes.

Report: print a summary (counts by service, multi-person count) and write it to impl-logs/reports/fee_cases_report.md.
