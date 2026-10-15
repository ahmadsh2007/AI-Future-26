# TASK (pp-fable / claude-fable-5.1): Build the knowledge-base module

Project folder: /Users/alsalayh/Downloads/participant_pack (Python 3.9 stdlib only, no pip). Read first:
- impl-logs/brief.txt (the challenge brief, extracted from challenge_brief.pdf)
- bot/schema.py (the shared contract: SERVICES ids == data file names, FIELDS keys + Arabic labels). Do NOT edit schema.py.
- ALL 12 files in data/ — read every line of every file. Never modify data/.

Other engineers are writing bot/router.py, bot/normalize.py and eval/ in parallel; do not touch those. Your files: bot/kb.py and the kb/ output folder. Work without asking questions; make reasonable choices and report them.

## What the raw files look like (verified)
- Top lines are website menu leftovers: "الرئيسية", "الخدمات", "دليل الخدمات", the page title, "شارك", title again. The title sometimes has parentheses, e.g. "(تجديد جواز السفر العادي)". Drop these menu lines (keep the title as title_raw).
- Then 9 fields. A label is usually followed by a TAB and the first value line ("الرسوم\t5 دنانير"), but some labels stand alone on their own line with values below (always "إجراءات تقديم الخدمة"; also "شروط تقديم الخدمة" in family_book_damaged). Label text can have trailing spaces. The documents label is "الوثائق المطلوبة للحصول على الخدمة" -> key "documents". Some services have no conditions field at all (e.g. family_book_lost, family_book_renewal) -> empty list.
- Value lines can contain stray TABs that are NOT labels (e.g. "9.تسليم الجواز وقراءته الياً\t" in passport_lost procedure, "6.تغليف الجواز وقراءته الياً.\t" in passport_renewal). A line that starts with whitespace+TAB (e.g. " \tاستيفاء قيمة التعهد السابق ..." in family_book_damaged / family_book_renewal) is a continuation of the previous field (fees), not a new label.
- Mixed numbering styles ("1. ", "1-", "4.", "8تحويل", " 2. "), sub-items with "-" or "    - (", blank lines, typos, repeated lines, amounts as digits in one place and words in another.

## Requirements for bot/kb.py
1. `load_kb(data_dir=None) -> dict`: service_id -> {
     "id", "doc", "situation", "name_ar" (from schema.SERVICES), "title_raw",
     "fields": {field_key: [item, item, ...]}   # every key in schema.FIELD_KEYS present; [] if missing
   }
   data_dir defaults to the project's data/ folder resolved relative to kb.py (so it works from any cwd). Each item = one logical point (one numbered item, or one line for unnumbered fields like fees/partners/locations/notes). Sub-items ("- ...") are merged into their parent item or kept as their own item — your choice, but nothing may be lost.
2. Cleaning: normalize whitespace; renumber numbered fields consistently as "1. ...", "2. ..." in original order; remove exact duplicate lines and copy-paste near-duplicates only when they say exactly the same thing (e.g. passport_renewal conditions 2 and 4 — keep the more complete one, and record what you removed). Fix obvious spelling typos ONLY where the meaning is unambiguous (e.g. "دنانبر"->"دنانير", "بطافات"->"بطاقات", "فسم"->"قسم", "الوئيفة"->"الوثيقة", "إ‘حصاءات"->"إحصاءات", "مكاتب ]دائرة"->"مكاتب دائرة", "تتسليم"->"تسليم", "اختصاصة"->"اختصاصه"). NEVER change any number, amount, age, duration, condition, or exception. Where an amount/duration is written in words (e.g. "ثلاثة أشهر", "ثلاث سنوات", "أسبوعين"), keep the words and append the digits in parentheses, e.g. "ثلاثة أشهر (3)". Convert any Arabic-Indic digits to ASCII digits.
3. `context_string(service_id, field_key, items=None, kb=None) -> str`: returns "<name_ar> - <Arabic label>: <items joined with ' '>" (items default to all items of that field). Example: "تجديد دفتر العائلة - الوثائق المطلوبة: 1. دفتر العائلة المراد تجديده. 2. البطاقة الشخصية لمقدم الطلب 3. ..." — use the labels from schema.FIELD_LABELS. Make kb optional (load and cache once at module level if None).
4. `python3 -m bot.kb` (run from the project folder) writes kb/services.json (UTF-8, ensure_ascii=False, indent=2) and kb/services_clean.txt (human-readable dump: every service, every field, every item) and prints a verification report. load_kb() parses the raw files every call (they are tiny) — the JSON is for review only; keep it deterministic.
5. Also write kb/cleaning_log.txt: every change you made that is more than whitespace/numbering (typo fixes, removed duplicates, digits appended), per service.

## Verification (must run and pass before you report)
a) Every number that appears in a raw file (after Arabic-Indic->ASCII) appears in the cleaned output of the same service.
b) Every non-menu raw line has its content present in the cleaned output (compare normalized word sets; report any line where >10% of words are missing and explain each).
c) Each of the 12 services has non-empty fields for beneficiaries, locations, documents, procedure, time, fees; print item counts per field per service.
d) Spot-check by eye in kb/services_clean.txt: passport_renewal fees (6 fee lines, 180 days, 16 years), passport_lost fees (125 / 250 / 5 years), id_card_lost notes (4 notes, 10 دنانير, 50 دينار, two weeks), family_book_first_issue notes (oldest son rule, 3 months, 30 days) and fees (2 دينار, 10 دنانير fine after 90 days), family_book_damaged fees (3 دنانير + the continuation line).

## Report
Write your final report to impl-logs/reports/kb_report.md and also print it: files written, the verification output (summary), every judgment call (e.g. what you treated as duplicates, any field you were unsure about), and anything odd in the data that the answering stage must handle. IMPORTANT: include a section "Look-alike differences" listing the key differences between the 4 passport files, the 4 family book files and the 4 ID card files in fees/notes/conditions/documents/locations/time (with the exact values). This list is used to write the answer prompt and test cases.
