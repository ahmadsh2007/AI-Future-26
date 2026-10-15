"""Extract the user's personal situation from the question (age, days left, abroad, times lost ...).

The 7B model is weak at arithmetic and at comparing numbers with thresholds, so code does it and
the result is given to the model as plain-Arabic hints, e.g.
    "العمر المذكور: 17 سنة، أي أكبر من 16 سنة وأقل من 18 سنة."
The hints never contain document facts; they only restate what the user said.
"""
import re

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def _norm(text):
    t = (text or "").translate(_AR_DIGITS)
    t = _DIACRITICS.sub("", t)
    t = re.sub(r"[أإآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


# Spoken / written number words (normalized spelling) -> value. Jordanian forms included.
_NUM_WORDS = {
    "واحد": 1, "وحده": 1, "سنه": 1, "اثنين": 2, "اتنين": 2, "ثنتين": 2, "تنتين": 2,
    "ثلاث": 3, "ثلاثه": 3, "تلات": 3, "تلاته": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5,
    "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تمن": 8, "تمانيه": 8, "ثماني": 8,
    "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
    "احدعش": 11, "احدعشر": 11, "اطنعش": 12, "اثنعش": 12, "اثنا عشر": 12, "اثني عشر": 12,
    "تلطعش": 13, "ثلاثطعش": 13, "ثلاثه عشر": 13, "ثلاث عشره": 13,
    "اربعطعش": 14, "اربعه عشر": 14, "اربع عشره": 14,
    "خمسطعش": 15, "خمسه عشر": 15, "خمس عشره": 15,
    "ستطعش": 16, "سته عشر": 16, "ست عشره": 16, "السادسه عشر": 16, "سادسه عشر": 16,
    "سبعطعش": 17, "سبعه عشر": 17, "سبع عشره": 17,
    "تمنطعش": 18, "ثمنطعش": 18, "ثمانيه عشر": 18, "ثماني عشره": 18, "الثامنه عشر": 18,
    "تسعطعش": 19, "تسعه عشر": 19, "تسع عشره": 19,
    "عشرين": 20, "ثلاثين": 30, "تلاتين": 30, "اربعين": 40, "خمسين": 50, "ستين": 60,
    "سبعين": 70, "ثمانين": 80, "تمانين": 80, "تسعين": 90,
}
_NUM_ALT = "|".join(sorted((re.escape(k) for k in _NUM_WORDS), key=len, reverse=True))
_NUM = r"(\d+(?:\.\d+)?|%s)" % _NUM_ALT


def _val(tok):
    if tok is None:
        return None
    if re.match(r"^\d", tok):
        return float(tok) if "." in tok else int(tok)
    return _NUM_WORDS.get(tok)


# Who the number belongs to (looked up just before the age expression).
_PERSONS = [
    (r"\b(ابني|ابنى|ولدي|الولد|ابن)\b", "الابن"),
    (r"\b(بنتي|ابنتي|البنت|بنت)\b", "البنت"),
    (r"\b(اخوي|اخي|اخو)\b", "الأخ"),
    (r"\b(اختي|اخت)\b", "الأخت"),
    (r"\b(ابوي|ابي|والدي|ابوه)\b", "الأب"),
    (r"\b(امي|والدتي|امه)\b", "الأم"),
    (r"\b(زوجتي|مرتي|مراتي)\b", "الزوجة"),
    (r"\b(زوجي|جوزي)\b", "الزوج"),
    (r"\b(انا|عمري)\b", "المستخدم نفسه"),
]

_AGE_PATTERNS = [
    r"عمر(?:ي|ه|ها|و|هم|نا)?\s+(?:صار\s+|هلا\s+|حاليا\s+)?" + _NUM,
    _NUM + r"\s+(?:سنه|سنين|سنوات|عام|اعوام)\s+(?:عمري|عمره|عمرها|من عمره|من عمرها)",
    r"(?:ابني|ابنى|ولدي|بنتي|ابنتي|اخوي|اخي|اختي|ابوي|امي|زوجتي|زوجي|جوزي|مرتي)\s+(?:عمره|عمرها)?\s*" + _NUM + r"\s*(?:سنه|سنين|سنوات|عام|اعوام)",
    r"(?:طفل|طفله|قاصر)\s+(?:عمره|عمرها)?\s*" + _NUM + r"\s*(?:سنه|سنين|سنوات)",
]

_ABROAD = [
    "برا البلد", "بره البلد", "برا الاردن", "بره الاردن", "خارج الاردن", "خارج البلاد", "خارج البلد",
    "خارج المملكه", "مغترب", "مغتربه", "بالغربه", "في الغربه", "عايش برا", "ساكن برا", "مقيم برا",
    "مقيم في الخارج", "بالخارج", "في الخارج", "من السفاره", "بالسفاره", "في السفاره", "القنصليه",
    "بالسعوديه", "في السعوديه", "بالامارات", "في الامارات", "بدبي", "في دبي", "بقطر", "في قطر",
    "بالكويت", "في الكويت", "بامريكا", "في امريكا", "بالمانيا", "في المانيا", "بتركيا", "في تركيا",
    "بمصر", "في مصر", "بكندا", "في كندا", "ببريطانيا", "في بريطانيا", "بلندن", "بالعراق", "بعمان العاصمه العمانيه",
]
_INSIDE = ["بالاردن", "في الاردن", "داخل الاردن", "داخل البلاد", "جوا البلد", "بعمان", "في عمان", "باربد", "في اربد", "بالزرقا"]

_URGENT = ["مستعجل", "مستعجله", "الخدمه المستعجله", "مكتب الخدمه المستعجله", "عاجل", "بسرعه", "بنفس اليوم", "ضروري اليوم"]
_MILITARY = ["عسكري", "عسكريه", "بالجيش", "في الجيش", "القوات المسلحه", "الامن العام", "الدفاع المدني",
             "الدرك", "حفظ السلام", "الاجهزه الامنيه", "شرطي", "ضابط"]
_JERUSALEM = ["مقدسي", "مقدسيه", "هويه مقدسيه", "الهويات المقدسيه", "هويه القدس"]
_FULL_PAGES = ["ممتلي", "ممتلئ", "تعبي", "تعبت صفحاته", "خلصت صفحاته", "خلصو الصفحات", "خلصت الصفحات",
               "ما ضل فيه صفحات", "ما في صفحات", "الصفحات خلصت", "صفحاته خلصت", "امتلا", "امتلات"]
_EXPIRED = ["منتهي", "منتهيه", "انتهي", "انتهت", "خلص", "خلصت", "مخلص", "انتهت صلاحيته", "صلاحيته منتهيه", "مش ساري", "مو ساري"]
_MARITAL = ["تغيير الحاله الاجتماعيه", "تزوجت", "اتزوجت", "اتجوزت", "تجوزت", "طلقت", "تطلقت", "انطلقت", "ترملت"]
_INTENTIONAL = ["قصدا", "متعمد", "عن قصد", "بقصد", "عمدا", "قطعته", "مزعته بايدي"]

_TIMES = [
    (r"(?:للمره|المره|مره)\s+(?:الثالثه|التالته|ثالثه|تالته)|(?:ثالث|تالت)\s+مره|3\s*مرات|ثلاث مرات|تلات مرات", 3),
    (r"(?:للمره|المره|مره)\s+(?:الثانيه|التانيه|ثانيه|تانيه)|(?:ثاني|تاني)\s+مره|مرتين|2\s*مرات", 2),
    (r"(?:للمره|المره)\s+(?:الاولي|الاوله)|اول\s+مره\s+(?:بضيع|يضيع|ضاع|بفقد|افقد|فقدت|اضيع|ضيعت)|(?:ضاع|ضيعت|فقدت)\S*\s+(?:لاول|اول)\s+مره", 1),
]


def _has(t, phrases):
    return any(re.search(r"(?:^|\s)" + re.escape(p) + r"(?:$|\s)", t) for p in phrases)


def _duration_days(n, unit):
    if n is None:
        return None
    if unit.startswith("يوم") or unit.startswith("ايام"):
        return n
    if unit.startswith("اسبوع") or unit.startswith("اسابيع"):
        return n * 7
    if unit.startswith("سن") or unit.startswith("عام") or unit.startswith("اعوام"):
        return n * 365
    return n * 30  # months


_UNIT = r"(يوم|ايام|اسبوع|اسابيع|شهر|شهور|اشهر|سنه|سنين|سنوات|عام|اعوام)"
_DUAL = {"شهرين": (2, "شهر"), "يومين": (2, "يوم"), "اسبوعين": (2, "اسبوع"), "سنتين": (2, "سنه"), "عامين": (2, "عام")}


def _remaining_days(t):
    """Days left before the document expires, e.g. 'باقي عليه 3 شهور', 'بيخلص بعد شهرين'."""
    lead = r"(?:باقي|بقي|ضايل|ضل|متبقي|ظل|ضالل)\s+(?:عليه|عليها|له|لها|الو|الها|فيه|فيها|علي|على انتهايه|على صلاحيته)?\s*(?:بس|فقط|حوالي|تقريبا)?\s*"
    lead2 = r"(?:بيخلص|بخلص|بينتهي|بنتهي|ينتهي|تنتهي|بتنتهي|بتخلص|صلاحيته)\s+(?:بعد|خلال|كمان)\s+(?:بس|حوالي|تقريبا)?\s*"
    for ld in (lead, lead2):
        m = re.search(ld + _NUM + r"\s*" + _UNIT, t)
        if m:
            return _duration_days(_val(m.group(1)), m.group(2)), m.group(0)
        m = re.search(ld + r"(شهرين|يومين|اسبوعين|سنتين|عامين)", t)
        if m:
            n, u = _DUAL[m.group(1)]
            return _duration_days(n, u), m.group(0)
        m = re.search(ld + r"(شهر|يوم|اسبوع|سنه)\b", t)
        if m:
            return _duration_days(1, m.group(1)), m.group(0)
    return None, None


def _since_days(t, anchors):
    """Days since an event, e.g. 'تزوجت من 4 شهور', 'ضاع قبل سنتين'."""
    for a in anchors:
        m = re.search(a + r"\s+(?:\S+\s+){0,3}?(?:من|قبل|صرلي|صارلي|صار لي|صار)\s+(?:حوالي|تقريبا)?\s*" + _NUM + r"\s*" + _UNIT, t)
        if m:
            return _duration_days(_val(m.group(1)), m.group(2)), m.group(0)
        m = re.search(a + r"\s+(?:\S+\s+){0,3}?(?:من|قبل|صرلي|صارلي|صار لي|صار)\s+(شهرين|يومين|اسبوعين|سنتين|عامين)", t)
        if m:
            n, u = _DUAL[m.group(1)]
            return _duration_days(n, u), m.group(0)
    return None, None


def extract(question):
    """Return a dict of detected situation facts (only keys that were detected)."""
    t = _norm(question)
    out = {}

    ages = []
    for pat in _AGE_PATTERNS:
        for m in re.finditer(pat, t):
            v = _val(m.group(1))
            if v is None or not (0 < v < 120):
                continue
            before = t[max(0, m.start() - 25):m.end()]
            who = "غير محدد"
            for rx, name in _PERSONS:
                if re.search(rx, before):
                    who = name
            if (v, who) not in ages:
                ages.append((v, who))
    if ages:
        out["ages"] = ages

    days, src = _remaining_days(t)
    if days is not None:
        out["days_left"] = days

    if _has(t, _ABROAD):
        out["abroad"] = True
    elif _has(t, _INSIDE):
        out["abroad"] = False
    if _has(t, _URGENT):
        out["urgent"] = True
    if _has(t, _MILITARY):
        out["military"] = True
    if _has(t, _JERUSALEM):
        out["jerusalem_id"] = True
    if _has(t, _FULL_PAGES):
        out["full_pages"] = True
    if _has(t, _EXPIRED) and "full_pages" not in out and days is None:
        out["expired"] = True
    if _has(t, _MARITAL):
        out["marital_change"] = True
    if _has(t, _INTENTIONAL):
        out["intentional"] = True

    for rx, n in _TIMES:
        if re.search(rx, t):
            out["times_lost"] = n
            break

    d, _ = _since_days(t, [r"(?:تزوجت|اتزوجت|اتجوزت|تجوزت|تزوجنا|اتجوزنا|عقد الزواج|كتبنا الكتاب|كتب كتابي|عرسي|زواجي)"])
    if d is not None:
        out["days_since_marriage"] = d
    d, _ = _since_days(t, [r"(?:ضاع|ضيعت|فقدت|انسرق|سرق|الفقدان|اول مره|المره الاولي|المره الماضيه|اخر مره|اخر جواز|اخر هويه|اخر دفتر)"])
    if d is not None:
        out["days_since_previous"] = d
    return out


def _cmp(v, thr, unit):
    if v > thr:
        return "أكبر من %s %s" % (thr, unit)
    if v < thr:
        return "أقل من %s %s" % (thr, unit)
    return "يساوي %s %s" % (thr, unit)


def _fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


# Which situation facts matter for which document (others are dropped so the model is not distracted).
_KEYS_BY_DOC = {
    "passport": {"ages", "days_left", "expired", "full_pages", "abroad", "urgent", "military",
                 "jerusalem_id", "marital_change", "intentional", "times_lost", "days_since_previous"},
    "family_book": {"expired", "abroad", "times_lost", "days_since_previous", "days_since_marriage", "intentional"},
    "id_card": {"ages", "expired", "abroad", "times_lost", "days_since_previous", "intentional"},
}


def hints(question, docs=None):
    """Arabic hint lines describing the user's situation, with threshold comparisons precomputed.

    docs: optional iterable of doc keys ("passport", "family_book", "id_card"); when given, only
    facts relevant to those documents are returned.
    """
    f = extract(question)
    if docs:
        keep = set()
        for d in docs:
            keep |= _KEYS_BY_DOC.get(d, set())
        f = {k: v for k, v in f.items() if k in keep}
    lines = []
    for v, who in f.get("ages", []):
        lines.append("عمر %s: %s سنة، أي %s و%s." % (who, _fmt(v), _cmp(v, 16, "سنة"), _cmp(v, 18, "سنة")))
    if "days_left" in f:
        d = f["days_left"]
        lines.append("المدة المتبقية على انتهاء صلاحية الوثيقة: حوالي %s يوماً، أي %s (الوثيقة غير منتهية بعد)." % (_fmt(d), _cmp(d, 180, "يوماً")))
    if f.get("expired"):
        lines.append("ذكر المستخدم أن الوثيقة منتهية الصلاحية.")
    if f.get("full_pages"):
        lines.append("ذكر المستخدم أن صفحات الجواز ممتلئة.")
    if f.get("abroad") is True:
        lines.append("المستخدم موجود خارج الأردن (خارج البلاد).")
    elif f.get("abroad") is False:
        lines.append("المستخدم موجود داخل الأردن.")
    if f.get("urgent"):
        lines.append("المستخدم يريد الخدمة المستعجلة.")
    if f.get("military"):
        lines.append("المستخدم من العسكريين أو الأجهزة الأمنية.")
    if f.get("jerusalem_id"):
        lines.append("المستخدم يحمل هوية مقدسية.")
    if f.get("marital_change"):
        lines.append("ذكر المستخدم تغييراً في الحالة الاجتماعية.")
    if f.get("intentional"):
        lines.append("ذكر المستخدم أن التلف كان متعمداً.")
    if "times_lost" in f:
        names = {1: "الأولى", 2: "الثانية", 3: "الثالثة"}
        lines.append("هذه المرة %s التي يفقد فيها الوثيقة." % names.get(f["times_lost"], str(f["times_lost"])))
    if "days_since_marriage" in f:
        d = f["days_since_marriage"]
        lines.append("مضى على عقد الزواج حوالي %s يوماً، أي %s." % (_fmt(d), _cmp(d, 90, "يوماً")))
    if "days_since_previous" in f:
        d = f["days_since_previous"]
        lines.append("مضى على المرة السابقة حوالي %s يوماً (حوالي %s سنة)، أي %s و%s." % (
            _fmt(d), _fmt(round(d / 365.0, 1)), _cmp(d / 365.0, 3, "سنوات"), _cmp(d / 365.0, 5, "سنوات")))
    return lines, f


if __name__ == "__main__":
    import sys
    for q in sys.argv[1:]:
        print(q)
        for line in hints(q)[0]:
            print("  -", line)
