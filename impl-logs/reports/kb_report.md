# KB report — bot/kb.py (pp-fable / claude-fable-5.1)

## Files written
- `bot/kb.py` — parser + cleaner + verification. Python 3.9 stdlib only. Imports `bot.schema`, nothing else from the project.
- `kb/services.json` — cleaned KB (UTF-8, ensure_ascii=False, indent=2). Review artifact only; `load_kb()` re-parses `data/` on every call. Verified deterministic (two runs, byte-identical).
- `kb/services_clean.txt` — human-readable dump: every service, every field, every item, with item counts.
- `kb/cleaning_log.txt` — 57 logged changes beyond whitespace/numbering (TYPO / DUP / DIGITS), per service.
- `impl-logs/reports/kb_report.md` — this file.

Not touched: `data/`, `bot/schema.py`, `bot/router.py`, `bot/normalize.py`, `eval/`.

## API (bot/kb.py)
- `load_kb(data_dir=None) -> dict` — service_id -> `{"id","doc","situation","name_ar","title_raw","title_raw_alt","fields":{key:[items]}}`; all 9 `schema.FIELD_KEYS` always present (`[]` if the file has no such field). `data_dir` defaults to `<project>/data` resolved relative to kb.py (works from any cwd; tested from /tmp).
- `get_kb()` — module-level cache (loaded once).
- `field_items(service_id, field_key, kb=None) -> list[str]`
- `context_string(service_id, field_key, items=None, kb=None) -> str` — `"<name_ar> - <label>: <items>"`. Example output: `تجديد دفتر العائلة - الوثائق المطلوبة: 1. دفتر العائلة المراد تجديده. 2. البطاقة الشخصية لمقدم الطلب 3. بطاقة إحصاءات الجسور الصفراء أو مشروحات المتابعة والتفتيش لمن يلزم ذلك.`
- `service_text(service_id, kb=None, fields=None) -> list[str]` — one context string per non-empty field (convenience for the answer stage).
- `python3 -m bot.kb` — writes the kb/ files and prints the verification report; exit code 0 only if all checks pass.

## Verification output (summary of `python3 -m bot.kb`)
```
(a) number coverage: 12/12 OK — every number in a raw file (numbering prefixes stripped) appears in the cleaned text of the same service.
(b) word coverage: 10 raw lines flagged (>10% words missing), ALL explained by typo fixes; 0 unexplained:
    passport_first_issue/procedure  'الوئيقه'                 -> fixed to الوثيقة
    passport_lost/partners          'العمل'                   -> خدمة العمل -> خدمة العلم
    family_book_first_issue/proc.   'فسم','الوئيفه'           -> قسم, الوثيقة
    family_book_renewal/procedure   'الوئيقه'                 -> الوثيقة
    family_book_damaged/documents   'ا','حصاءات' (إ‘حصاءات)   -> إحصاءات
    id_card_renewal/procedure       'لاعلامهبجاهزيه'          -> لإعلامه بجاهزية
    id_card_lost/procedure          'والرسال','الكترونياالي'  -> وإرسال, الكترونيا إلى
    id_card_lost/partners           'بطافات'                  -> بطاقات
    id_card_damaged/procedure       'الصندوقلاستيفاء'         -> الصندوق لاستيفاء
    id_card_damaged/partners        'مشرحات'                  -> مشروحات
(c) item counts (benef locat condi docum proce time partn notes fees):
    passport_first_issue      1 2 5 10  7 1 5 1 4
    passport_renewal          1 2 6  8  7 1 5 2 6
    passport_lost             1 2 5 11 10 1 7 1 2
    passport_damaged          1 2 5  8  7 1 5 1 1
    family_book_first_issue   1 2 5  6  6 1 1 4 2
    family_book_renewal       1 2 2  3  6 1 1 4 2
    family_book_lost          1 2 2  5  6 1 3 3 3
    family_book_damaged       1 2 3  5  6 1 1 1 2
    id_card_first_issue       1 1 2  7  8 1 3 1 2
    id_card_renewal           1 1 2  4  8 1 3 1 1
    id_card_lost              1 1 3  9  8 1 4 4 2
    id_card_damaged           1 1 3  5  9 1 2 1 1
    -> beneficiaries, locations, documents, procedure, time, fees non-empty for all 12.
(d) spot checks: all OK — passport_renewal fees 6 lines incl. (180) يوم and السادسة عشر (16);
    passport_lost fees 125 / 250 / 5 سنوات; id_card_lost notes 4 items incl. (10) دنانير, (50) دينار, أسبوعين (2);
    family_book_first_issue notes (oldest son, ثلاثة أشهر (3), 30 يوم) and fees ((2) دينار, (10) دنانير after (90) يوم);
    family_book_damaged fees = "3 دنانير" + continuation line "استيفاء قيمة التعهد السابق ...".
VERIFICATION PASSED (0 problems)
```

## Parsing approach
- Menu lines (`الرئيسية`, `الخدمات`, `دليل الخدمات`, `شارك`) dropped; the remaining pre-label lines are titles. `title_raw` = last one (the H1 after شارك, parentheses stripped); `title_raw_alt` = the breadcrumb title when different (only family_book_first_issue: "دفتر عائلة لأول مرة لغير المسجلين مدنياً", and family_book_renewal: "تجديد دفتر عائلة").
- A line is a label iff the text before its first TAB (or the whole line) equals one of the 9 labels, AND the line does not start with whitespace+TAB (that pattern is a continuation of the current field — the fees of family_book_damaged / family_book_renewal). Stray trailing TABs in value lines are therefore harmless.
- Items: for list fields (conditions, documents, procedure, notes) a new item starts at a numbering prefix (`1.`, `1-`, `4..`, `8تحويل`, leading spaces allowed; the digit-glued-to-letter form is only recognised inside list fields so `45دقيقة` / `20 دينار` are never mistaken for numbering). `-` bullets after a numbered item are **merged into the parent item** (kept with their dash) so nothing is lost: passport_lost document 11 (3 sub-items), family_book_first_issue document 2 (3 certificate cases). A `-` bullet with no numbered parent becomes its own item (passport notes). Un-numbered wrapped lines after a numbered item would be merged as continuation (no such case exists in the data).
- Non-list fields (beneficiaries, locations, time, partners, fees): one raw line = one item, never renumbered.
- Renumbering: list fields are renumbered `1. 2. 3.` in original order if the raw field was numbered or has ≥2 items (so id_card_first_issue / id_card_renewal conditions, which are two un-numbered sentences, become 1./2.). A single un-numbered item stays plain (passport notes, "لا يوجد").

## Cleaning — judgment calls
1. **Whitespace only** (not logged): tabs/multiple spaces collapsed; space removed before `.،:؛)` and after `(`; space inserted between digit and letter (`45دقيقة` -> `45 دقيقة`, `250دينار` -> `250 دينار`, `(10دنانير )` -> `(10 دنانير)`), between a letter and `(` / `)` and a letter (`الطلب(رب` -> `الطلب (رب`), after `،`; `/` spacing normalised (`الأب /الأم` -> `الأب/الأم`); `الصورة+ الأصل` -> `الصورة + الأصل`.
2. **Typo fixes** (logged, 25 patterns, applied only where meaning is unambiguous): the listed ones (دنانبر, بطافات, فسم, الوئيفة, إ‘حصاءات, مكاتب ]دائرة, تتسليم, اختصاصة) plus: الوئيقة->الوثيقة (3 files), `؟أمين`->`أمين` (stray question mark), `االدفترلمتلقي`->`الدفتر لمتلقي`, `لمتلفي الخدمة`->`لمتلقي الخدمة`, glued words split (`الأصولوسحب`, `الصندوقلاستيفاء`, `التأكدمن`, `أخذالتوقيع`, `لإعلامهبجاهزية`, `الكترونياإلى`, `الامرالاب`), `والرسال امر`->`وإرسال امر`, `مشرحات`->`مشروحات`, `الياً`->`آلياً` (قراءته آلياً, 4 passport files), `للعسكرين`->`للعسكريين`, `إفراد الأسرة`->`أفراد الأسرة`, and `انهاء خدمة العمل`->`انهاء خدمة العلم` (passport_lost partners; the same file's documents say خدمة العلم). Hamza/ta-marbuta spelling variants (اصدار/إصدار, متوفي/متوفى, الاصول/الأصول …) were left untouched.
3. **Not fixed (ambiguous), flagged for the answer stage**: passport_first_issue document 5 `لوتصريح الاحتلال` (probably "أو تصريح الاحتلال"); id_card_lost procedure 8 `من بيانات المواطن خلال البصمة` (missing "من"); family_book_lost document 5 `واذا تكرار الفقدان` (grammar); id_card_damaged procedure has 9 steps where 8 and 9 both say "deliver the card" (kept both — not identical text).
4. **Duplicates removed** (logged): exactly one — passport_renewal conditions raw #4 ("إذا كان مقدم الطلب حاصلا على جنسية أخرى … بهدف تخزين الاسم الوارد في الجنسية الأخرى") is a strict word-subset of raw #2 (which adds "باللغة الانجليزية"); #2 kept, so passport_renewal has 6 conditions. Rule: within one field, an item whose normalised word set equals or is a strict subset (≥5 words) of another item is dropped; the run shows it fired only on this case. Cross-service repeats (e.g. the Jerusalem-ID note in passport_first_issue and passport_renewal) are kept.
5. **Digits appended after amounts/durations written in words** (logged, words kept): `ثلاثة أشهر (3)`, `ثلاث سنوات (3)` / `الثلاث سنوات (3)`, `أسبوعين (2)`, `عشرة دنانير (10)`, `دينارين (2)`, `ثلاثة دنانير (3)`, `الثامنة عشر (18)`, `السادسة عشر (16)`. Ordinals (المرة الأولى/الثانية/الثالثة) were deliberately left alone. No number, amount, age, duration, condition or exception was altered; check (a) confirms every raw number survives.
6. Arabic-Indic digit conversion is implemented but the raw files contain none.
7. `context_string` joins numbered items with a single space (as specified) and **un-numbered multi-item fields (locations, partners, fees) with "؛ "** so separate fee rules / places stay distinguishable for the 7B model (e.g. `… أماكن تقديم الخدمة: مكاتب دائرة الأحوال المدنية والجوازات؛ السفارات الأردنية والقنصليات في الخارج.`). Change `_join_items` if the team prefers a plain space.
8. `notes` = `["لا يوجد"]` is kept as-is for id_card_first_issue / id_card_renewal / id_card_damaged (tells the model there are no notes).
9. Correction to the task text: family_book_lost and family_book_renewal DO have a conditions field (the label stands alone on its own line, values below: "ان يكون حاصلاً على البطاقة الشخصية الذكية" + one more). No service has an empty field; every field of every service has ≥1 item.

## Things the answering stage must handle (odd data)
- **Fees are rule tables, not one number**: passport_renewal has 6 lines (20/25/20/50/100/100) keyed on age (<16 vs >16), passport validity (expired or <180 days left vs >180 days), full pages, military, abroad; passport_first_issue has 4 (20 military / 25 under 16 / 50 inside / 100 abroad); passport_lost 125 first time, 250 afterwards (+ previous guarantee if <5 years); family_book_renewal 2 JD expired vs 3 JD not expired; id_card_first_issue 2 JD + 10 JD late fine if 18 and no card yet.
- **Extra charges hide in notes/documents**: passport_renewal note "+25 دينار at the express office"; family_book_damaged document 4 "10 دنانير written undertaking"; family_book_lost / id_card_lost repeated-loss escalation (10 JD undertaking, 50 JD bail on 3rd loss, collected if within 3 years); id_card_lost "card not issued until two weeks after police report"; passport_lost bail 50–500 JD set by the investigation committee.
- **"Not expired" costs more** for family_book_renewal (3 JD vs 2 JD) — counter-intuitive; passport renewal of a still-valid passport (>180 days left) costs 100 vs 50.
- passport_damaged conditions/documents are copy-pasted from renewal (they say "تجديد"); passport_lost condition 2 also says تجديد. Fine for answers, but don't let the word "تجديد" inside a damaged/lost file confuse routing.
- Family book: no photos required; passports require 2 photos; ID card requires 1 photo (first issue and lost only; renewal/damaged list none).
- Locations: passport and family book services can be done at embassies/consulates abroad; **all 4 ID card services are offices only** (no embassy line).
- Times: passports and family book 45 دقيقة; all ID card services 20 دقيقة.
- Beneficiaries are always "المواطنون الأردنيون"; passport_first_issue/renewal notes say Jerusalem ID holders are treated as Jordanians for fees.
- family_book_first_issue breadcrumb title adds "لغير المسجلين مدنياً" (for people not yet civilly registered) — stored in `title_raw_alt`.
- Wife rule (brief's "wrong assumption" example): every passport file states the wife may get/renew a passport **without** her husband's consent (condition 4/5/5/5).
- "رب الأسرة" rules live in family_book_first_issue AND family_book_renewal notes (oldest Jordanian wife becomes head if polygamous husband dies; eldest child if both parents die).

## Look-alike differences

### Passport (4 files) — identical: beneficiaries, locations (offices + embassies/consulates abroad), time 45 دقيقة, partners التعبئة والتجنيد / المتابعة والتفتيش / القيادة العامة / قاضي القضاة / المخابرات العامة
| | first_issue | renewal | lost | damaged |
|---|---|---|---|---|
| fees | (20 دينار) military/security/civil defence in peacekeeping; (25 دينار) under 16; 50 دينار inside Jordan; 100 دينار abroad | 20 دينار military/security/civil defence/peacekeeping + change of marital status + military↔civil status change; 25 دينار under 16; 20 دينار full pages & still valid; 50 دينار over 16 and passport expired or <180 days left; 100 دينار not expired / >180 days left; 100 دينار abroad (or equivalent in embassy currency) | 125 دينار first time; 250 دينار any later time + previous bail collected if previous loss <5 years ago | 100 دينار (single line) |
| notes | Jerusalem ID holders treated as Jordanians for fees | same Jerusalem note + **25 دينار added at the express office (مكتب الخدمة المستعجلة)** | if the passport/document issued after the bail is lost again, no replacement until the bail is paid and a new bail given; bail term = legal validity of the passport | if damage is deliberate -> investigation committee, legal action, security approvals |
| conditions | personal attendance for 18+ **or an adult family member**; ID card if 16+; parent may apply for minors; wife without husband's consent; guardianship deed | personal attendance for 18+; **dual nationals must show the other passport (English name)**; guardianship deed; ID card if 16+; wife without consent; parent for minors | personal attendance for 18+; guardianship deed; parent may apply for lost replacement for minors; ID card if 16+; wife without consent | personal attendance (no age stated); guardianship deed; parent for minors; ID card if 16+; wife without consent |
| documents (unique) | director-general approval if abroad; **passport the person was added to (to cancel the addition page)**; **proof of nationality/residence (law 6/1954) if no family file**; foreign passport; 2 photos; guardianship deed; military approval letter incl. المخابرات | director-general approval if abroad; **the passport to be renewed**; foreign passport; 2 photos; military approval (if husband's name not on passport) | **investigation committee approval**; **bail 50–500 دينار**; **police loss report**; **security approval**; 2 photos; if lost abroad: translated loss report, emergency travel document, foreign passport showing entry | **the damaged passport**; **bail or personal undertaking to keep the passport**; 2 photos; military approval |
| documents count | 10 | 8 | 11 | 8 |
| procedure | 7 steps | 7 steps | **10 steps** (investigation committee contacts security, sets bail; approval letter; audit step) | 7 steps |
| partners extra | — | — | **+ وزارة العدل (bail), المركز الأمني (loss circular), المخابرات (security approval)** — 7 partners | — |

### Family book (4 files) — identical: beneficiaries, locations (offices + embassies/consulates abroad), time 45 دقيقة, procedure (6 steps), document "بطاقة إحصاءات الجسور الصفراء أو مشروحات المتابعة والتفتيش لمن يلزم ذلك"
| | first_issue | renewal | lost | damaged |
|---|---|---|---|---|
| fees | رسوم إصدار الدفتر (2) دينار; **غرامة (10) دنانير if (90) يوم passed since the marriage contract** | **دينارين (2) if the book is expired; ثلاثة دنانير (3) if NOT expired** | 5 دنانير; written undertaking (10) دنانير; previous undertaking collected if lost again within 3 years | 3 دنانير; previous undertaking collected if damaged within 3 years of previous issue |
| notes | 4: polygamous deceased head -> each wife separate book, oldest Jordanian wife becomes head; eldest child becomes head if both parents die; renew within ثلاثة أشهر (3) of expiry; report data changes within 30 يوم | same 4 notes (minor wording: "اقدم الزوجات" without الأردنيات) | 3: 10 JD undertaking on 1st loss; 10 JD undertaking on 2nd loss, collected if within 3 years; **كفالة عدلية (50) دينار on 3rd loss** + collect 2nd undertaking + previous 10 JD if within 3 years | 1: on damage **or loss** report to the office of residence within 30 يوم |
| conditions | 5: marriage/divorce event entered in the system (divorcee may open a separate record from her father's book); both spouses hold smart ID (Jordanians); applied by one of the spouses; new residence proofs if different from ID; **open civil record before (90) يوم from the marriage contract** | 2: holds smart ID; old family book | 2: holds smart ID; **application only by head of family or wife** | 3: holds smart ID; old family book; **damage must not be deliberate** |
| documents | 6: new civil record form; certificates issued by the department (marriage / divorce for divorcee / death of head when >1 wife); social development letter for illegitimate children; **both spouses' ID cards**; bridges card; copy of foreign passport if one spouse is non-Jordanian | 3: book to be renewed; applicant's ID; bridges card | 5: family book form; applicant's ID (head or wife); bridges card; **police loss report (inside Jordan or from the foreign country's authority)**; **written undertaking for 1st/2nd loss, bail (50) دينار if more** | 5: family book form; **the damaged book**; applicant's ID; **written undertaking set by office head (10 دنانير)**; bridges card |
| partners | المتابعة والتفتيش | المتابعة والتفتيش | **المركز الأمني, وزارة العدل, المتابعة والتفتيش** | المتابعة والتفتيش |
| title | "الحصول على دفتر عائلة لأول مرة" / breadcrumb "لغير المسجلين مدنياً" | | | |

### ID card (4 files) — identical: beneficiaries, locations (**offices only — no embassies**), time 20 دقيقة, documents "نموذج البطاقة الشخصية", military approval letter, bridges card (copy + original) or inspection stamp
| | first_issue | renewal | lost | damaged |
|---|---|---|---|---|
| fees | 2 دينار; **10 دنانير late fine if 18 years old and never issued a card** | 2 دينار | 5 دنانير; previous undertaking collected if lost again within 3 years | 3 دنانير |
| notes | لا يوجد | لا يوجد | 4: 2nd loss within <3 years -> pay the (10) دنانير undertaking first; **card issued only after أسبوعين (2) from the police report + director approval**; 3rd loss -> investigation committee; **(50) دينار bail on 3rd loss** + collect 2nd undertaking + previous one if within 3 years | لا يوجد |
| conditions | applicant in person; proof of identity + testimony of an adult family member | applicant in person; **proof of identity (passport) if the photo on the card is unclear, or a first-degree identifier** | applicant = owner of the lost card; **minor: guardian applies, no power of attorney/delegation**; proof of identity or testimony of a family member with official documents | applicant in person (damaged card); **minor: guardian (father/mother), no power of attorney**; proof of identity or family member testimony |
| documents (unique) | proof of identity or first-degree identifier; **guardian consent if under 16**; **1 photo**; **blood-type medical test or written declaration** — 7 docs | **the card to be renewed** — 4 docs | proof of identity; **written undertaking for 1st/2nd loss**; **investigation committee report for 3rd loss**; **1 photo**; **electronic police report**; **bail for 3rd loss** — 9 docs | proof of identity; **the damaged card** — 5 docs |
| procedure | 8 steps (step 2 adds address, iris capture, blood type) | 8 steps | 8 steps (cashier before office head) | 9 steps (8 and 9 both about delivery) |
| partners | المتابعة والتفتيش, القيادة العامة, **وزارة الصحة (blood type)** | same 3 | **المركز الأمني, المتابعة والتفتيش, القيادة العامة, وزارة العدل** | المتابعة والتفتيش, القيادة العامة |

## Open issues
- None blocking. `context_string` separator for un-numbered fields ("؛ ") is a deliberate deviation from "joined with ' '" — one-line change if unwanted.
- The near-duplicate rule is generic (subset of words); it is verified to fire only on passport_renewal condition 4 for the current data. If data/ changes, re-check kb/cleaning_log.txt.
