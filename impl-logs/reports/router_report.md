# Deterministic Router Implementation Report

## Files written

- `bot/normalize.py` — lossy Arabic/Latin normalization and tokenization for matching.
- `bot/router.py` — deterministic service, field, status, candidate, multi-service, and history routing.
- `tests/__init__.py` — test package marker.
- `tests/test_router.py` — 124-case `unittest` regression suite.
- `impl-logs/reports/router_report.md` — this report.

No files under `data/` were modified. `bot/schema.py`, `bot/kb.py`, and `eval/` were not modified.

## Verification

Commands run from `/Users/alsalayh/Downloads/participant_pack`:

```text
python3 -m unittest tests.test_router -v
Ran 124 tests in 0.148s
OK
```

```text
python3 -m py_compile bot/normalize.py bot/router.py tests/test_router.py
Exit code: 0
```

A separate contract smoke test passed 8/8 malformed, empty, normalized-Arabic, and ambiguous inputs. Every result had exactly the required eight keys and a valid status. The suite covers all 12 services in formal Arabic and Jordanian dialect, challenge-brief and practice questions, all field keys, normalization, attached proclitics and possessives, look-alike traps, comparisons, long multi-person stories, unclear and unsupported requests, and multi-turn clarification/follow-up behavior.

## Lexicon and routing summary

- Normalization removes Arabic diacritics/tatweel, unifies common letter variants, converts Arabic-Indic and Persian digits to ASCII, lowercases Latin text, replaces punctuation with spaces, and collapses whitespace.
- Word matching tolerates attached `و/ف/ب/ل/ال/وال/بال/لل` forms and common possessive suffixes, including forms such as `وللهوية`, `بالجواز`, `جوازي`, `هويتي`, and `دفترنا`.
- Document vocabulary covers passport (`جواز`, `باسبور`, `passport`), smart ID (`هوية`, `بطاقة شخصية/ذكية/أحوال`, `ID`), and family book (`دفتر العائلة/العيلة`, civil-record and head-of-family topics).
- Situation vocabulary covers first issue/extraction, renewal/expiry/full pages, loss/theft, and damage/tearing/burning/water damage, including official `بدل فاقد` and `بدل تالف` language.
- Known false-friend exclusions include `دفتر خدمة العلم`, bridge/statistics/Palestinian cards, and unsupported related services such as diplomatic/special/temporary passports, certificates as services, residence/visa, driving licence, nationality, family reunification, and flights. In-scope questions may still mention these terms as required documents or circumstances.
- Multi-service resolution pairs situations with document mentions, shares a sole document or situation across coordinated mentions, preserves mention order, and deduplicates services. Loss/damage predicates prefer the nearest preceding document to handle multi-person narratives.
- Field detection covers fees, documents, conditions, locations, time, procedure, partners, beneficiaries, and explicit notes/exceptions. `شو المطلوب` maps to documents plus conditions; `شو بعمل` maps to procedure plus documents.
- History inherits only missing dimensions and, when the follow-up has no field vocabulary, prior fields. Candidate alternatives from an unclear turn are not promoted to definite facts. Explicit current service details override history, while unsupported follow-ups remain unsupported.

## Known weak spots

- This is a finite deterministic lexicon; unseen spelling errors, uncommon slang, Arabizi, or highly creative paraphrases can remain unclear or unsupported.
- Dense sentences with several documents and situations in unusual word order may defeat nearest/predecessor pairing, especially when pronouns rather than document names carry the relationship.
- Bare `بطاقة` is treated as an ID card unless it matches a known non-ID card trap; an unseen card service could therefore be mistaken for the smart ID.
- The deceased-parents/head-of-family question is routed to family-book first issue because that is the most targeted source, although a duplicate rule also appears in family-book renewal.
- Follow-ups to a prior multi-service answer are intentionally conservative when the new message does not identify which prior service it refers to.
## Round 2

### Accuracy

Using the required dry-run command:

- Before: status `81/90`; status + exact services `70/90`.
- After: status `90/90`; status + exact services `89/90`.

### Changes

- Treated `أول مرة` and equivalent first-time phrases near loss/damage as replacement counts rather than first-issue requests for the same document.
- Added clause-local first-issue detection for negated issuance and possession (`ما طلعنا`, `عمري ما طلع`, `لسا ما استخرجت`, `ما معي`, and related forms).
- Expanded renewal, loss, and damage morphology, including attached prefixes/pronouns, broken chips, water/washing, fading, punctures, and deliberate damage wording.
- Prevented replacement wording such as `وحدة بدالها` from falling back to first issue.
- Excluded Jerusalem IDs and later bare references to `دفتر خدمة العلم` from supported document detection.
- Defaulted head-of-family, deceased-head, and multiple-wives family-book topics without another situation to first issue.
- Improved situation-to-document pairing when the verb comes before the document, and ignored trailing repeated document mentions once that document type is resolved.
- Added explicit unsupported subjects such as work permits, professional licences, commercial registries, vehicle registration, health insurance, social security, bank cards, and foreign-passport requests.
- Kept the orchestrator's added time-field words unchanged.

### Tests

Added 22 independent paraphrase tests: at least three for each of the seven requested categories. The complete router suite now runs 146 tests.

### Remaining dev-set mismatch

One exact-service mismatch remains for `dev-29-1`. The task says a head-of-family topic with no explicit situation must default to `family_book_first_issue`, which the router now does. The dev-set entry instead requires both `family_book_first_issue` and `family_book_renewal`. Adding renewal would contradict the written default and make an unstated situation definite, so this mismatch was intentionally not changed. Its route status is now correctly `ok`.
## Round 3

### Accuracy

Using the required dry-run command after the changes:

- Route status: `90/90`.
- Route status + exact services: `89/90`.
- These match the Round 2 baseline; neither score went down.

### Changes

- Added a bounded word-family matcher for common Jordanian verb prefixes (`ت/ي/ب/بت/بي/ن`), suffix and object-pronoun combinations, and requested dialect spelling substitutions (`ق/ء/ك`, `ذ/د/ز`, `ث/ت`, `ظ/ض`).
- Expanded loss routing for dropped, unfindable, forgotten, disappeared, pickpocketed, stolen, and snatched documents.
- Expanded damage routing for cuts, tears, water/washing, adhesive, melting, burning, scribbling/erasure, fading, breaking, folding/bending, pet damage, and child damage. Replacement wording after damage remains damage, not first issue.
- Expanded renewal routing for expired or nearly expired validity, remaining months, old documents, explicit renewal, and validity extension.
- Expanded first-issue routing for productive issuance forms, non-possession, newlywed phrases, civil-record opening, separate records, second/multiple wives, and children born outside marriage.
- Added family-book topic detection without requiring the word `دفتر`, while keeping explicit loss/damage/renewal situations stronger than newlywed defaults.
- Added explicit exclusions for certificates requested as services, diplomatic/special passports, visas, licences, opening hours/holidays, and online appointment/application/site-only questions. A complete document+situation request may still mention an electronic appointment.
- Added a narrow `الشقة` guard after dev-set validation showed that the short damage stem `شق` could otherwise misread a newlywed story about an apartment.

### Tests

- Added 65 independently phrased Round 3 router tests, exceeding the requested 30.
- Router suite: `python3 -m unittest tests.test_router` -> 211 tests, all passed.
- Full suite: `python3 -m unittest discover -s tests` -> 224 tests, all passed.
- Syntax check: `python3 -m py_compile bot/router.py tests/test_router.py` -> passed.

### Open issue

The same intentional dev-set mismatch remains at `dev-29-1`: the expected data lists both family-book first issue and renewal, while the written routing rule says a head-of-family topic without another situation defaults to first issue. The router keeps only `family_book_first_issue`; route status is still correct.
## Round 4

### Accuracy

Using the required dry-run command after the changes:

- Route status: `90/90`.
- Route status + exact services: `89/90`.
- These match the Round 3 baseline; neither score went down.

### Changes

- Added passport plural, dual, and possessive-plural forms, including `جوازات`, `جوازين`, and `باسبورات` families.
- Added ID plural, dual, and possessive-plural forms for `هويات` and `بطاقات`, while keeping bridge/statistics cards excluded.
- Added family-book plural and dual forms while keeping military-service booklets excluded, including later bare references to an introduced military booklet.
- Added `أول جواز`, `أول هوية`, `أول بطاقة`, and `أول دفتر` as first-issue signals.
- Added `خلصان`, `خلصانه`, `خالص`, and `مخلّص` as renewal/expiry signals.
- Split routing evidence at punctuation and at conjunctions that introduce a person or document, then resolved each clause independently.
- Limited cross-clause situation sharing to clear coordinated document lists. A clause with its own explicit or implicit situation keeps that situation.
- Preserved single-document pronoun continuations, comparison routing, repeated trailing field references, newlywed overrides, and shared-situation lists from earlier rounds.

### Tests

- Added 26 independently phrased Round 4 tests, exceeding the requested 15.
- Router suite: `python3 -m unittest tests.test_router` -> 237 tests, all passed.
- Full suite: `python3 -m unittest discover -s tests` -> 266 tests, all passed.
- Syntax check: `python3 -m py_compile bot/router.py tests/test_router.py` -> passed.
- Direct smoke checks passed for both task examples and the existing comparison/shared-loss examples.

### Open issue

The same intentional dev-set mismatch remains at `dev-29-1`: the expected data lists both family-book first issue and renewal, while the written routing rule says a head-of-family topic without another situation defaults to first issue. The router keeps only `family_book_first_issue`; route status remains correct.