"""Rule-based routing: question -> (services, sections). Handles Jordanian dialect.
Everything here is plain regex on normalized Arabic, so it is fast, offline and easy to debug."""
import re
from dataclasses import dataclass, field

from text_utils import normalize_for_match

# ---- vocabulary (applied to normalize_for_match text: alef/yaa/taa-marbuta unified, no tashkeel)
DOC_PATTERNS = {
    "passport": r"جواز|جوازي|جوازات(?! الاحوال)|باسبور|بسبور|باصبور|passport|وثيقه سفر",
    "family_book": r"دفتر|كتيب(?: ال)?عايل|كتيب(?: ال)?عائل",
    "id_card": r"بطاق(?:ه|ت)(?: ال)?(?:ذكي|شخصي|احوال|مدني)|بطاقتي|هويه|هويت|الهويه|\bid\b|بطاقه ذكيه|البطاقه",
}
SIT_PATTERNS = {
    "lost": r"فقد|فاقد|مفقود|ضاع|ضايع|ضاعت|ضيع|ضياع|سرق|سرقت|ضايعه|بدل فاقد",
    "damaged": r"تالف|تلف|تالفه|خربان|خربت|اتخرب|خرب|تضرر|متضرر|ممزق|تمزق|تمزقت|اتقطع|تقطع|مكسور|انكسر|مبلول|احترق|محروق|ساحت|بدل تالف",
    "renewal": r"تجديد|اجدد|جدد|يجدد|تجدد|منتهي|انتهت|انتهى|انتهاء|خلص|خلصت|مخلص|expired|renew|اجدده|نجدد",
    "first_issue": r"لاول مره|اول مره|لاول|(?<!ت)جديد|اصدار|استخراج|اطلع|اخرج|بطلع|بخرج|طلعت|طلع|اطلعت|مولود|ولد(?:ت)? ابني|عمل (?:دفتر|جواز|هويه)|اصدر",
}
STRONG_FIRST = r"لاول مره|اول مره|لاول"   # weak triggers (اطلع/اخرج/جديد...) lose against lost/damaged/renewal
# detail: when "جديد" etc. appears together with renewal words, renewal wins (handled by priority below)
SIT_PRIORITY = ["lost", "damaged", "renewal", "first_issue"]

# generic domain words: present => question is about gov services (so "unclear" instead of "out of scope")
DOMAIN_WORDS = r"جواز|باسبور|دفتر|عايل|عائل|هويه|بطاق|احوال|سفر|رسوم|تجديد|فاقد|تالف|مدني"

# intent -> which fields to feed the model (notes are always added: exceptions/surcharges hide there)
INTENTS = {
    "fee": (r"كم (?:ال)?(?:سعر|رسوم|كلف|تكلف|بدفع|بكلف|ادفع|بتدفع|يكلف|تكلفه)|قديش|بكم|سعر|رسوم|كلفه|تكلف|تكاليف|بدفع|ادفع|غرام|تعهد|كفال|مبلغ|دينار|اغلي|ارخص|اغلى|فلوس|مصاري|يضاف|ينضاف|بينضاف|اضافي|زياده|مستعجل", ["الرسوم", "ملاحظات"]),
    "time": (r"يستغرق|كم وقت|قديش وقت|كم دقيق|كم ساع|بياخد وقت|بتاخد وقت|وقت|يوم جاهز|متى يجهز|بجهز", ["الزمن المستغرق"]),
    "docs": (r"اوراق|وثائق|مستندات|ورق|احضر|اجيب|بجيب|اجلب|مطلوب|لازم(?:ني)? (?:ا|ن)?جيب|شو بدي|ايش بدي|صور|صوره|صورة", ["الوثائق المطلوبة"]),
    "where": (r"وين|اين|مكان|اماكن|سفار|قنصل|فرع|مكتب|اقدم|برا البلد|خارج الاردن|خارج البلد|عنوان", ["أماكن تقديم الخدمة"]),
    "eligibility": (r"يحق|بحق|بقدر|بسمح|يسمح|شروط|شرط|مين|من يحق|عمر|سن |عمره|قاصر|ولي|وصاي|ولايه|زوج|زوجه|موافقه|ابني|بنتي|طفل|الفئه|مواطن|مقدس|اجنب", ["الفئة المستفيدة", "شروط تقديم الخدمة", "ملاحظات"]),
    "procedure": (r"خطوات|اجراءات|كيف|طريقه|شو اعمل|شو بعمل|مراحل", ["إجراءات تقديم الخدمة"]),
    "duration": (r"مده|المده|كم سنه|كم شهر|متى", ["الزمن المستغرق", "شروط تقديم الخدمة", "ملاحظات"]),
    "partners": (r"شركاء|جهات|جهه", ["شركاء الخدمة"]),
}
ALL_FIELDS = ["الفئة المستفيدة", "أماكن تقديم الخدمة", "شروط تقديم الخدمة", "الوثائق المطلوبة",
              "الزمن المستغرق", "شركاء الخدمة", "ملاحظات", "الرسوم", "إجراءات تقديم الخدمة"]


@dataclass
class Route:
    kind: str                       # "services" | "clarify" | "out_of_scope" | "unknown"
    services: list = field(default_factory=list)   # [(doc, situation)]
    fields: list = field(default_factory=list)
    missing: str = ""               # "doc" | "situation"
    docs: list = field(default_factory=list)
    sits: list = field(default_factory=list)
    intents: list = field(default_factory=list)


def _find_all(patterns: dict, text: str) -> list[tuple[int, str]]:
    hits = []
    for key, pat in patterns.items():
        for m in re.finditer(pat, text):
            hits.append((m.start(), key))
    hits.sort()
    seen, out = set(), []
    for pos, key in hits:
        if key not in seen:
            seen.add(key)
            out.append((pos, key))
    return out


UNSUPPORTED = r"دبلوماسي|دبلوماسيه|مؤقت|طوارئ|الحج|حجاج|وثيقه سفر للاجئ|لاجئ"   # variants that are NOT in the 12 files


def detect(question: str):
    q = normalize_for_match(question).lower()
    doc_hits = _find_all(DOC_PATTERNS, q)
    sit_hits = _find_all(SIT_PATTERNS, q)
    # a bare "بطاقة" must not turn a passport/family-book question into an ID question
    if len(doc_hits) > 1 and not re.search(r"ذكي|شخصي|هويه|احوال", q):
        doc_hits = [h for h in doc_hits if h[1] != "id_card"]
    # weak first-issue words (اطلع/اخرج/جديد...) lose against lost/damaged/renewal when only ONE document is asked about
    if len(doc_hits) <= 1 and len(sit_hits) > 1 and not re.search(STRONG_FIRST, q):
        sit_hits = [h for h in sit_hits if h[1] != "first_issue"]
    return q, doc_hits, sit_hits


def pair_services(doc_hits, sit_hits) -> list[tuple[str, str]]:
    docs, sits = [d for _, d in doc_hits], [s for _, s in sit_hits]
    if len(docs) <= 1 or len(sits) <= 1:   # one document x its situations (comparison), or several docs x one situation
        return [(d, s) for d in docs for s in sits][:4]
    pairs = []   # several docs AND several situations: attach each situation to the nearest document
    for dp, d in doc_hits:
        near = min(sit_hits, key=lambda h: abs(h[0] - dp))
        pairs.append((d, near[1]))
    for sp, s in sit_hits:   # a situation nobody picked still deserves its nearest document
        if s not in [x[1] for x in pairs]:
            pairs.append((min(doc_hits, key=lambda h: abs(h[0] - sp))[1], s))
    return list(dict.fromkeys(pairs))[:4]


def pick_fields(q: str) -> tuple[list[str], list[str]]:
    wanted, intents = [], []
    for name, (pat, fields_) in INTENTS.items():
        if re.search(pat, q):
            intents.append(name)
            wanted += fields_
    if not wanted or len(intents) >= 3:   # unclear intent or a long multi-part story -> everything
        return list(ALL_FIELDS), intents
    return [f for f in ALL_FIELDS if f in wanted], intents


def route(question: str, history: list[tuple] | None = None) -> Route:
    """history: [(docs, sits)] resolved earlier in the same chat (most recent last)."""
    q, doc_hits, sit_hits = detect(question)
    docs, sits = [d for _, d in doc_hits], [s for _, s in sit_hits]
    fields_, intents = pick_fields(q)
    r = Route(kind="services", fields=fields_, docs=docs, sits=sits, intents=intents)

    if re.search(UNSUPPORTED, q):
        r.kind = "out_of_scope"
        return r

    if history:   # follow-up: inherit what the user did not restate
        prev_docs, prev_sits = history[-1]
        if not docs:
            docs = prev_docs
            if not sits:
                sits = prev_sits
        elif not sits and set(docs) == set(prev_docs):
            sits = prev_sits
        r.docs, r.sits = docs, sits
        if not doc_hits:   # inherited: positions are meaningless, pairing is a plain cross product
            doc_hits = [(0, d) for d in docs]
        if not sit_hits:
            sit_hits = [(0, s) for s in sits]

    if not docs:
        has_domain = bool(re.search(DOMAIN_WORDS, q)) or bool(sits)
        r.kind = "unknown" if has_domain else "out_of_scope"   # "unknown" -> LLM decides clarify vs out_of_scope
        return r
    if not sits:
        r.kind, r.missing = "unknown", "situation"   # LLM decides: truly unclear, or an unsupported variant?
        return r
    r.services = pair_services(doc_hits, sit_hits)
    return r
