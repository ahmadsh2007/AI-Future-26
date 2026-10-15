# TASK (pp-gpt / gpt-5.6-sol): Build the deterministic question router

Project folder: /Users/alsalayh/Downloads/participant_pack (Python 3.9 stdlib only, no pip). Read first:
- impl-logs/brief.txt (the challenge brief; section 3 "What makes it hard" and section 4 "Questions you will face" matter most)
- bot/schema.py (shared contract: service ids, doc/situation keys, field keys, statuses). Do NOT edit schema.py.
- ALL 12 files in data/ (read them to learn the vocabulary of each service and field). Never modify data/.

Other engineers are writing bot/kb.py and eval/ in parallel; do not import or touch them. Your files: bot/normalize.py, bot/router.py, tests/__init__.py, tests/test_router.py. Work without asking questions; make reasonable choices and report them.

## Why this matters
The 4 passport files (and the 4 family book / 4 ID card files) are almost identical. If the bot picks the wrong file, the answer looks perfect but is wrong. The answering LLM is a small 7B model, so routing must be done by code, not by the model. Users write in Jordanian dialect.

## 1) bot/normalize.py
`normalize(text) -> str`: remove diacritics/tatweel, unify أ/إ/آ/ٱ -> ا, ى -> ي, ة -> ه, ؤ -> و, ئ -> ي (be consistent), Arabic-Indic and Persian digits -> ASCII, Latin lowercase, punctuation -> space (keep digits), collapse spaces. Also `tokens(text) -> list[str]`. Match keywords on normalized text (normalize your keyword lists the same way). Handle the Arabic proclitics و/ف/ب/ل/ال/وال/بال/لل when matching words (e.g. "وللهوية", "بالجواز", "والدفتر").

## 2) bot/router.py
`route(question, history=None) -> dict` with EXACTLY these keys:
```
{
  "status": "ok" | "unclear" | "out_of_scope",   # schema.STATUS_*
  "services": [service_id, ...],   # definite services, in order of mention; [] if not definite
  "candidates": [service_id, ...], # all services consistent with what was detected (== services when definite; e.g. the 4 passport ids when only the doc is known)
  "fields": [field_key, ...],      # fields asked about (schema.FIELD_KEYS); [] if none detected
  "missing": None | "doc" | "situation" | "doc_and_situation",
  "inherited": bool,               # True if any part came from history
  "mentions": {"docs": [...], "situations": [...]},  # debug
  "reason": str                    # short debug text
}
```
history = list of previous turns of the SAME chat, oldest first: `[{"question": str, "route": <dict returned by route>}, ...]`. None or [] = new chat. Must never raise (wrap and return out_of_scope/unclear with a reason on internal error).

Detection rules (implement, then extend from the data and brief):
- Docs (with dialect/typos/article/possessives like جوازي، هويتي، دفترنا): passport: جواز، الجواز، جواز السفر، باسبور، الباسبور، باسبوري، passport. id_card: هويه/الهوية، بطاقه شخصيه، البطاقة الذكية، الذكية، البطاقة (when not part of a non-ID meaning like بطاقة الجسور / بطاقة إحصاءات / البطاقة الفلسطينية), ID, الهوية الذكية، بطاقة الأحوال. family_book: دفتر العائلة، دفتر عيلة، دفتر العيله، الدفتر، دفتر (but NOT "دفتر خدمة العلم" which is a required document for passports). Topic words that imply family_book when no doc is named: رب الأسرة، فتح قيد/سجل مدني، الزوجات، المطلقة تفتح سجل … (check the data).
- Situations: first_issue: أول مرة، لأول مرة، جديد، إصدار/اصدار، أطلع/اطلع/طلّع/استخرج/أعمل/بدي جواز (implicit first issue only when no other situation word is present and the verb clearly means getting a new one; when unsure prefer "unclear"). renewal: تجديد، أجدد، جدد، بجدد، انتهى/خلص/منتهي/انتهت صلاحيته، ممتلئ/تعبّى/خلصت صفحاته. lost: ضاع، ضايع، ضيعت، فقدت، فاقد، مفقود، انسرق، سرق، أضعت. damaged: تلف، تالف، اهترى، مهتري، انمزق، تمزق، ممزق، مشقوق، تبلل/تبهدل/خرب/خربان/انحرق/محروق/اتلف. Note "بدل فاقد"/"بدل تالف" are the official phrasing. Careful: "الباسبور خلص" means expired -> renewal.
- Multi-service: comparisons ("أيهما أغلى"، "ولا"، "الفرق بين"، "مقارنة") and long stories about several people/problems. Pair each situation mention with the nearest doc mention (a shared doc applies to several situations: "جواز بدل تالف ولا بدل فاقد" -> passport_damaged, passport_lost; "ضاع جوازي وهوية ابني اهترت" -> passport_lost, id_card_damaged). Return all, deduplicated, in mention order.
- Fields: fees (رسوم، كم/قديش بدفع، بكلف، تكلفه، سعر، دينار، غرامه، كفاله), documents (اوراق، وثائق، شو بدي اجيب، شو بلزمني، شو المطلوب، صور شخصيه، مستندات), conditions (شروط، مين بقدر، بحقلي/يحق، لازم، موافقه، حضور شخصي، عمر …), locations (وين، مكان، اماكن، سفاره، قنصليه، برا البلد، خارج الاردن), time (قديش بياخد/وقت/مده/يستغرق/دقيقه/متى بيطلع), procedure (خطوات، اجراءات، كيف بقدم، شو بعمل، شو الطريقه), partners (شركاء، جهات)، beneficiaries (مين الفئه، مين بستفيد، لغير الاردنيين). "شو المطلوب" -> documents + conditions. "شو بعمل" -> procedure + documents. Add "notes" only when the question is clearly about notes/exceptions (the answer stage always adds notes anyway).
- Status:
  * out_of_scope: the question is about a service/topic NOT in the 12 files, including related-sounding ones (تصديق الشهادة الجامعية، شهادة ميلاد/وفاة as a service, جواز سفر دبلوماسي/خاص/مؤقت، إقامة/فيزا/تأشيرة، رخصة سواقة، عدم محكومية، لم شمل، تجنيس/جنسية، تذاكر طيران …), or it mentions no doc, no situation, no in-scope topic and there is nothing to inherit. Careful: some of those words DO appear in the data as required documents (e.g. "شهادة الزواج", "شهادة وفاة رب الأسرة" in family_book_first_issue, "وثيقة سفر اضطرارية" in passport_lost, "جواز السفر الأجنبي") — grep data/ and make sure questions about those in-scope details are NOT declined (e.g. "شو بحتاج إذا ضاع جوازي برا البلد؟" is in scope). Out-of-scope triggers win only when they are the subject of the question.
  * unclear: situation known but doc unknown (e.g. "بدي أجدد، شو المطلوب؟" -> missing "doc", candidates = the 3 renewal services); doc known but situation unknown (missing "situation", candidates = the 4 services of that doc); in-scope intent with neither (missing "doc_and_situation", candidates = all 12).
  * ok: every mention resolved to definite services.
- History (conversation bonus): if the current question lacks doc and/or situation, inherit the missing part from the most recent turn that has services or candidates (after "شو الأوراق المطلوبة لتجديد دفتر العائلة؟", the follow-up "وبقدر أقدّم الطلب من السفارة إذا كنت برا البلد؟" -> family_book_renewal, fields [locations], inherited True; "وكم بتكلف؟" -> same service, fields [fees]; "وللهوية؟" -> id_card + inherited situation + inherited fields). If the previous turn was "unclear" and the current message supplies the missing piece (user: "بدي أجدد، شو المطلوب؟", bot asks, user: "الجواز"), merge: services = passport_renewal, fields from the previous question. A follow-up that is itself out of scope stays out_of_scope. A new explicit doc+situation overrides history. When a follow-up has no field words, inherit the previous fields.

## 3) tests/test_router.py
unittest, run with `python3 -m unittest tests.test_router -v` from the project folder. At least 80 cases covering: every one of the 12 services in MSA and in dialect; each brief example question (section 4 table) and the practice questions.json; look-alike traps ("دفتر خدمة العلم" in a passport question must not route to family_book; "بطاقة الجسور" must not route to id_card); comparisons; long multi-person stories; all field types; unclear cases; out-of-scope incl. related-sounding services and in-scope questions that contain trap words; multi-turn follow-ups incl. answering a clarification. All tests must pass.

## Report
Write your final report to impl-logs/reports/router_report.md and also print it: files written, test results (counts), lexicon summary, and the known weak spots (cases you think will still route wrongly).
