"""Broad deterministic-router regression suite (stdlib unittest only)."""

import unittest

from bot import schema
from bot.normalize import normalize, tokens
from bot.router import route


class NormalizeTests(unittest.TestCase):
    def test_diacritics_and_tatweel(self):
        self.assertEqual(normalize("جَــوَازُ السَّفَر"), "جواز السفر")

    def test_arabic_letter_variants(self):
        self.assertEqual(normalize("أإآٱ ى ة ؤ ئ"), "اااا ي ه و ي")

    def test_arabic_indic_digits(self):
        self.assertEqual(normalize("٠١٢٣٤٥٦٧٨٩"), "0123456789")

    def test_persian_digits(self):
        self.assertEqual(normalize("۰۱۲۳۴۵۶۷۸۹"), "0123456789")

    def test_latin_lowercase(self):
        self.assertEqual(normalize("PASSPORT ID"), "passport id")

    def test_punctuation_becomes_spaces(self):
        self.assertEqual(normalize("جواز،هوية/دفتر؟ 20%"), "جواز هويه دفتر 20")

    def test_whitespace_collapses(self):
        self.assertEqual(normalize("  دفتر\n\t العائلة  "), "دفتر العايله")

    def test_tokens_uses_normalization(self):
        self.assertEqual(tokens("هُويّة، PASSPORT"), ["هويه", "passport"])


class RouterContractTests(unittest.TestCase):
    def test_exact_contract_keys(self):
        self.assertEqual(
            set(route("تجديد الجواز")),
            {"status", "services", "candidates", "fields", "missing", "inherited", "mentions", "reason"},
        )

    def test_none_never_raises(self):
        result = route(None)
        self.assertEqual(result["status"], schema.STATUS_OUT_OF_SCOPE)

    def test_non_string_never_raises(self):
        result = route(12345)
        self.assertIn(result["status"], {schema.STATUS_OUT_OF_SCOPE, schema.STATUS_UNCLEAR})

    def test_all_output_types(self):
        result = route("كم رسوم تجديد الجواز؟")
        self.assertIsInstance(result["services"], list)
        self.assertIsInstance(result["candidates"], list)
        self.assertIsInstance(result["fields"], list)
        self.assertIsInstance(result["mentions"], dict)
        self.assertIsInstance(result["reason"], str)


class GeneratedRouteTests(unittest.TestCase):
    """Individual generated methods keep the unittest result count honest."""


def _add_route_test(number, question, expected_service=None, status="ok", fields=(), missing=None,
                    expected_services=None, candidate_count=None):
    def test(self):
        result = route(question)
        self.assertEqual(result["status"], status, (question, result))
        self.assertEqual(result["missing"], missing, (question, result))
        if expected_service is not None:
            self.assertEqual(result["services"], [expected_service], (question, result))
        if expected_services is not None:
            self.assertEqual(result["services"], list(expected_services), (question, result))
        for field in fields:
            self.assertIn(field, result["fields"], (question, result))
        if candidate_count is not None:
            self.assertEqual(len(result["candidates"]), candidate_count, (question, result))
        self.assertTrue(set(result["fields"]).issubset(schema.FIELD_KEYS))

    name = "test_route_%03d" % number
    setattr(GeneratedRouteTests, name, test)


_ROUTE_CASES = [
    # Every service in formal Arabic.
    ("إصدار جواز سفر لأول مرة", "passport_first_issue"),
    ("تجديد جواز السفر", "passport_renewal"),
    ("جواز سفر بدل فاقد", "passport_lost"),
    ("جواز سفر بدل تالف", "passport_damaged"),
    ("الحصول على دفتر عائلة لأول مرة", "family_book_first_issue"),
    ("تجديد دفتر العائلة", "family_book_renewal"),
    ("دفتر عائلة بدل فاقد", "family_book_lost"),
    ("دفتر عائلة بدل تالف", "family_book_damaged"),
    ("إصدار بطاقة الأحوال المدنية الذكية لأول مرة", "id_card_first_issue"),
    ("تجديد البطاقة الذكية", "id_card_renewal"),
    ("بطاقة الأحوال المدنية الذكية بدل فاقد", "id_card_lost"),
    ("بطاقة الأحوال المدنية الذكية بدل تالف", "id_card_damaged"),
    # Every service in Jordanian/dialectal language and possessives.
    ("بدي باسبور جديد", "passport_first_issue"),
    ("الباسبور خلص", "passport_renewal"),
    ("ضاع باسبوري", "passport_lost"),
    ("جوازي انمزق", "passport_damaged"),
    ("بدي أعمل دفترنا أول مرة", "family_book_first_issue"),
    ("بدي أجدد الدفتر", "family_book_renewal"),
    ("دفترنا ضايع", "family_book_lost"),
    ("الدفتر تبلل", "family_book_damaged"),
    ("بدي أطلع هويتي أول مرة", "id_card_first_issue"),
    ("بجدد هويتي", "id_card_renewal"),
    ("ضيعت بطاقتي", "id_card_lost"),
    ("هويتي اهترت", "id_card_damaged"),
    # Brief and practice questions.
    ("كم يستغرق إصدار دفتر العائلة؟", "family_book_first_issue", ("time",)),
    ("عمري 17 وجوازي باقي عليه 3 شهور، كم رسوم التجديد؟", "passport_renewal", ("fees", "conditions")),
    ("شو المطلوب لتجديد دفتر العائلة؟", "family_book_renewal", ("documents", "conditions")),
    ("إذا توفي الأب والأم، مين بصير رب الأسرة؟", "family_book_first_issue", ("conditions",)),
    ("الباسبور خلص، شو بعمل؟", "passport_renewal", ("procedure", "documents")),
    ("الزوجة لازم تجيب موافقة جوزها عشان تطلع جواز، صح؟", "passport_first_issue", ("conditions",)),
    ("كم يستغرق تجديد دفتر العائلة؟", "family_book_renewal", ("time",)),
    ("وين بقدر أطلع جواز سفر بدل فاقد؟", "passport_lost", ("locations",)),
    ("شو الأوراق المطلوبة لتجديد دفتر العائلة؟", "family_book_renewal", ("documents",)),
    # Field lexicon across all field keys.
    ("قديش بدفع لتجديد جوازي؟", "passport_renewal", ("fees",)),
    ("كم بكلف دفتر عائلة بدل فاقد؟", "family_book_lost", ("fees",)),
    ("شو بلزمني لجواز بدل تالف؟", "passport_damaged", ("documents",)),
    ("أي وثائق لتجديد الهوية؟", "id_card_renewal", ("documents",)),
    ("مين بقدر يطلع دفتر عائلة لأول مرة؟", "family_book_first_issue", ("conditions",)),
    ("هل لازم حضور شخصي لجواز بدل فاقد؟", "passport_lost", ("conditions",)),
    ("وين السفارة اللي بتجدد الجواز؟", "passport_renewal", ("locations",)),
    ("هل أجدد دفتر العائلة خارج الأردن؟", "family_book_renewal", ("locations",)),
    ("قديش بياخد بدل تالف للهوية؟", "id_card_damaged", ("time",)),
    ("متى بيطلع جواز بدل فاقد؟", "passport_lost", ("time",)),
    ("شو خطوات تجديد الدفتر؟", "family_book_renewal", ("procedure",)),
    ("كيف بقدم على بطاقة ذكية لأول مرة؟", "id_card_first_issue", ("procedure",)),
    ("مين الجهات الشريكة بجواز بدل تالف؟", "passport_damaged", ("partners",)),
    ("مين الفئة المستفيدة من دفتر عائلة بدل فاقد؟", "family_book_lost", ("beneficiaries",)),
    ("هل الخدمة لغير الأردنيين لتجديد الهوية؟", "id_card_renewal", ("beneficiaries",)),
    ("شو الملاحظات والاستثناءات على جواز بدل فاقد؟", "passport_lost", ("notes",)),
    ("قديش صورة شخصية بحتاج للبطاقة الذكية لأول مرة؟", "id_card_first_issue", ("documents",)),
    ("كم يوم يستغرق بدل فاقد للبطاقة؟", "id_card_lost", ("time",)),
    # Normalization and proclitic attachment.
    ("وللهوية بدل تالف؟", "id_card_damaged"),
    ("بالجواز بدل فاقد شو المطلوب؟", "passport_lost", ("documents", "conditions")),
    ("والدفتر بدي أجدد", "family_book_renewal"),
    ("PASSPORT RENEWAL تجديد", "passport_renewal"),
    ("هُوِيَّتي تَلِفَت", "id_card_damaged"),
    # Alternate situation vocabulary.
    ("جوازي انتهت صلاحيته", "passport_renewal"),
    ("جوازي ممتلئ الصفحات", "passport_renewal"),
    ("فقدت دفتر العيلة", "family_book_lost"),
    ("انسرقت الهوية الذكية", "id_card_lost"),
    ("دفتر العائلة خربان", "family_book_damaged"),
    ("البطاقة الذكية انحرقت", "id_card_damaged"),
    ("استخرج جواز سفر", "passport_first_issue"),
    ("فتح قيد مدني جديد شو أوراقه؟", "family_book_first_issue", ("documents",)),
    # In-scope detail words that must not hijack routing.
    ("دفتر خدمة العلم مطلوب لتجديد جوازي؟", "passport_renewal", ("documents",)),
    ("بطاقة الجسور مطلوبة لتجديد الجواز؟", "passport_renewal", ("documents",)),
    ("هل البطاقة الفلسطينية مطلوبة لجواز بدل تالف؟", "passport_damaged", ("documents",)),
    ("شو بحتاج إذا ضاع جوازي برا البلد؟", "passport_lost", ("documents", "locations")),
    ("هل شهادة الزواج مطلوبة لدفتر عائلة أول مرة؟", "family_book_first_issue", ("documents",)),
    ("شهادة وفاة رب الأسرة لفتح دفتر جديد", "family_book_first_issue"),
    ("هل جواز السفر الأجنبي مطلوب للجواز لأول مرة؟", "passport_first_issue", ("documents",)),
]

for _index, _case in enumerate(_ROUTE_CASES, 1):
    _question, _service = _case[0], _case[1]
    _fields = _case[2] if len(_case) > 2 else ()
    _add_route_test(_index, _question, expected_service=_service, fields=_fields)


class MultiServiceTests(unittest.TestCase):
    def test_shared_passport_two_situations(self):
        result = route("جواز بدل تالف ولا بدل فاقد؟ أيهما أغلى")
        self.assertEqual(result["services"], ["passport_damaged", "passport_lost"])
        self.assertIn("fees", result["fields"])

    def test_two_docs_two_situations(self):
        result = route("ضاع جوازي وهوية ابني اهترت")
        self.assertEqual(result["services"], ["passport_lost", "id_card_damaged"])

    def test_practice_two_services(self):
        result = route("قديش صورة شخصية بحتاج للبطاقة الذكية لأول مرة، وقديش لتجديد جواز السفر؟")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["services"], ["id_card_first_issue", "passport_renewal"])
        self.assertIn("documents", result["fields"])

    def test_one_situation_shared_by_two_docs(self):
        result = route("بدي أجدد الجواز والهوية")
        self.assertEqual(result["services"], ["passport_renewal", "id_card_renewal"])

    def test_long_multi_person_story(self):
        question = "أنا في إربد وضاع جوازي أمس، وبنفس الوقت دفتر عائلة والدي تمزق، وهوية ابني انتهت؛ شو الرسوم؟"
        result = route(question)
        self.assertEqual(
            result["services"],
            ["passport_lost", "family_book_damaged", "id_card_renewal"],
        )
        self.assertIn("fees", result["fields"])

    def test_deduplicates_repeated_service(self):
        result = route("جوازي ضاع، الجواز نفسه مفقود")
        self.assertEqual(result["services"], ["passport_lost"])


class UnclearTests(unittest.TestCase):
    def test_missing_doc(self):
        result = route("بدي أجدد، شو المطلوب؟")
        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["missing"], "doc")
        self.assertEqual(len(result["candidates"]), 3)

    def test_missing_situation_passport(self):
        result = route("كم رسوم الجواز؟")
        self.assertEqual(result["missing"], "situation")
        self.assertEqual(len(result["candidates"]), 4)

    def test_missing_situation_family_book(self):
        result = route("شو أوراق دفتر العائلة؟")
        self.assertEqual(result["missing"], "situation")
        self.assertEqual(len(result["candidates"]), 4)

    def test_missing_situation_id(self):
        result = route("كم رسوم الهوية؟")
        self.assertEqual(result["missing"], "situation")
        self.assertEqual(len(result["candidates"]), 4)

    def test_missing_both(self):
        result = route("كم الرسوم؟")
        self.assertEqual(result["missing"], "doc_and_situation")
        self.assertEqual(len(result["candidates"]), 12)


class OutOfScopeTests(unittest.TestCase):
    QUESTIONS = (
        "كم رسوم تصديق الشهادة الجامعية؟",
        "كيف أطلع شهادة ميلاد؟",
        "كم رسوم شهادة وفاة؟",
        "بدي جواز سفر دبلوماسي",
        "شو شروط الجواز الخاص؟",
        "كيف أطلع جواز مؤقت؟",
        "كيف أقدم على إقامة؟",
        "وين بطلع فيزا؟",
        "كم رسوم التأشيرة؟",
        "كيف أجدد رخصة السواقة؟",
        "كيف أطلع عدم محكومية؟",
        "شو أوراق لم الشمل؟",
        "كيف أقدم على التجنيس؟",
        "بدي أطلع الجنسية",
        "كم سعر تذكرة الطيران من عمان إلى دبي؟",
        "كيف أجدد جواز السفر الأجنبي؟",
        "مرحبا كيفك",
        "بطاقة الجسور الصفراء كيف أجددها؟",
        "كيف أجدد بطاقة الجسور الصفراء؟",
        "كيف أجدد دفتر خدمة العلم؟",
    )


def _add_out_of_scope_test(number, question):
    def test(self):
        result = route(question)
        self.assertEqual(result["status"], "out_of_scope", (question, result))
        self.assertEqual(result["services"], [])

    setattr(OutOfScopeTests, "test_out_of_scope_%02d" % number, test)


for _index, _question in enumerate(OutOfScopeTests.QUESTIONS, 1):
    _add_out_of_scope_test(_index, _question)


class HistoryTests(unittest.TestCase):
    @staticmethod
    def _turn(question, history=None):
        return {"question": question, "route": route(question, history)}

    def test_followup_location(self):
        first = self._turn("شو الأوراق المطلوبة لتجديد دفتر العائلة؟")
        result = route("وبقدر أقدم الطلب من السفارة إذا كنت برا البلد؟", [first])
        self.assertEqual(result["services"], ["family_book_renewal"])
        self.assertEqual(result["fields"], ["locations"])
        self.assertTrue(result["inherited"])

    def test_followup_fee(self):
        first = self._turn("شو الأوراق المطلوبة لتجديد دفتر العائلة؟")
        result = route("وكم بتكلف؟", [first])
        self.assertEqual(result["services"], ["family_book_renewal"])
        self.assertIn("fees", result["fields"])
        self.assertTrue(result["inherited"])

    def test_doc_switch_inherits_situation_and_fields(self):
        first = self._turn("شو أوراق تجديد دفتر العائلة؟")
        result = route("وللهوية؟", [first])
        self.assertEqual(result["services"], ["id_card_renewal"])
        self.assertIn("documents", result["fields"])
        self.assertTrue(result["inherited"])

    def test_answer_clarification(self):
        first = self._turn("بدي أجدد، شو المطلوب؟")
        result = route("الجواز", [first])
        self.assertEqual(result["services"], ["passport_renewal"])
        self.assertIn("documents", result["fields"])
        self.assertTrue(result["inherited"])

    def test_answer_situation_clarification(self):
        first = self._turn("شو المطلوب لدفتر العائلة؟")
        result = route("ضاع", [first])
        self.assertEqual(result["services"], ["family_book_lost"])
        self.assertTrue(result["inherited"])

    def test_no_field_inherits_previous_field(self):
        first = self._turn("كم رسوم تجديد الجواز؟")
        result = route("وللهوية بدل فاقد؟", [first])
        self.assertEqual(result["services"], ["id_card_lost"])
        self.assertEqual(result["fields"], ["fees"])
        self.assertTrue(result["inherited"])

    def test_explicit_doc_and_situation_override_history(self):
        first = self._turn("كم رسوم تجديد الجواز؟")
        result = route("دفتر العائلة بدل تالف وين بطلع؟", [first])
        self.assertEqual(result["services"], ["family_book_damaged"])
        self.assertEqual(result["fields"], ["locations"])
        self.assertFalse(result["inherited"])

    def test_out_of_scope_followup_stays_out(self):
        first = self._turn("كم رسوم تجديد الجواز؟")
        result = route("وكيف أطلع فيزا؟", [first])
        self.assertEqual(result["status"], "out_of_scope")
        self.assertFalse(result["inherited"])

    def test_uses_most_recent_relevant_turn(self):
        first = self._turn("كم رسوم تجديد الجواز؟")
        second = self._turn("مرحبا", [first])
        result = route("وكم بياخد وقت؟", [first, second])
        self.assertEqual(result["services"], ["passport_renewal"])
        self.assertIn("time", result["fields"])

    def test_does_not_promote_ambiguous_candidates(self):
        first = self._turn("كم رسوم الجواز؟")
        result = route("وكم بتكلف؟", [first])
        self.assertEqual(result["status"], "unclear")
        self.assertEqual(result["missing"], "situation")
        self.assertEqual(result["services"], [])
        self.assertTrue(result["inherited"])


class Round2RouterTests(unittest.TestCase):
    """Independent paraphrases for each round-two routing category."""

    def assert_route(self, question, services, status="ok"):
        result = route(question)
        self.assertEqual(result["status"], status, (question, result))
        self.assertEqual(result["services"], services, (question, result))

    # 1. Ordinals near loss/damage count replacements, not first issues.
    def test_loss_count_after_family_book_loss(self):
        self.assert_route(
            "ضاع دفتر العيلة، ولأول مرة بصير معنا هالشي",
            ["family_book_lost"],
        )

    def test_first_damage_count_after_official_label(self):
        self.assert_route(
            "كم بكلف جواز بدل تالف للمرة الأولى؟",
            ["passport_damaged"],
        )

    def test_first_loss_count_in_id_comparison(self):
        self.assert_route(
            "هويتي بدل فاقد لأول مرة ولا بدل تالف؟",
            ["id_card_lost", "id_card_damaged"],
        )

    # 2. Never having obtained a document means first issue, clause-locally.
    def test_never_extracted_passport(self):
        self.assert_route(
            "لسا ما استخرجت جواز سفر بحياتي",
            ["passport_first_issue"],
        )

    def test_new_couple_never_made_family_book(self):
        self.assert_route(
            "تزوجنا جديد وما عملنا دفتر عيلة إلى الآن",
            ["family_book_first_issue"],
        )

    def test_never_issued_id_beats_other_clause_renewal(self):
        self.assert_route(
            "جواز أمي منتهي وبدها تجدده، وابني عمره ما طلع هوية",
            ["passport_renewal", "id_card_first_issue"],
        )

    # 3. Productive verb forms and replacement wording.
    def test_passport_reflexive_renewal_form(self):
        self.assert_route("جوازي لازم يتجدد قبل السفر", ["passport_renewal"])

    def test_prefixed_id_loss_form(self):
        self.assert_route(
            "هاي رابع مرة بتضيع فيها بطاقتي الذكية",
            ["id_card_lost"],
        )

    def test_washed_family_book_damage_forms(self):
        self.assert_route(
            "دفتر العيلة انغسل وصار مبلول",
            ["family_book_damaged"],
        )

    def test_broken_id_replacement_is_not_first_issue(self):
        self.assert_route(
            "هويتي انكسرت والشريحة خربانة وبدي أطلع وحدة بدالها",
            ["id_card_damaged"],
        )

    # 4. Look-alike identity and booklet terms are not supported documents.
    def test_jerusalem_identity_does_not_add_id_service(self):
        self.assert_route(
            "معي هوية القدس، وين أجدد جواز السفر؟",
            ["passport_renewal"],
        )

    def test_plural_jerusalem_id_does_not_add_id_service(self):
        self.assert_route(
            "هل الهويات المقدسية بتغير رسوم جواز بدل فاقد؟",
            ["passport_lost"],
        )

    def test_bare_booklet_refers_to_military_service_booklet(self):
        self.assert_route(
            "دفتر خدمة العلم معي؛ لإصدار الجواز أول مرة هل أحتاج الدفتر؟",
            ["passport_first_issue"],
        )

    # 5. Family-head topics default to family-book first issue.
    def test_deceased_family_head_topic(self):
        self.assert_route(
            "بعد وفاة رب الأسرة، مين يسجل في دفتر العائلة؟",
            ["family_book_first_issue"],
        )

    def test_multiple_wives_family_head_topic(self):
        self.assert_route(
            "في حالة تعدد الزوجات، مين رب الأسرة في دفتر العيلة؟",
            ["family_book_first_issue"],
        )

    def test_both_parents_deceased_family_head_topic(self):
        self.assert_route(
            "والدي ووالدتي توفوا، مين بيكون رب الأسرة؟",
            ["family_book_first_issue"],
        )

    # 6. Repeated resolved mentions do not leave status unclear.
    def test_second_lost_replacement_passport_is_resolved(self):
        self.assert_route(
            "استخرجت جواز بدل فاقد السنة الماضية، واليوم فقدت الجواز البديل مرة ثانية",
            ["passport_lost"],
        )

    def test_second_lost_replacement_id_is_resolved(self):
        self.assert_route(
            "ضاعت هويتي زمان وطلعت بدالها، وهلأ انسرقت الهوية الجديدة",
            ["id_card_lost"],
        )

    def test_trailing_fee_document_references_are_resolved(self):
        self.assert_route(
            "باسبوري انمزق، ودفتر العيلة ضاع. كم رسوم الجواز ودفتر العيلة؟",
            ["passport_damaged", "family_book_lost"],
        )

    # 7. Explicit unsupported service subjects are outside the knowledge base.
    def test_work_authorization_renewal_is_out_of_scope(self):
        self.assert_route("شو تكلفة تجديد إذن العمل؟", [], "out_of_scope")

    def test_commercial_registry_issue_is_out_of_scope(self):
        self.assert_route("كيف أستخرج سجل تجاري جديد؟", [], "out_of_scope")

    def test_vehicle_registration_renewal_is_out_of_scope(self):
        self.assert_route("وين أجدد تسجيل السيارة؟", [], "out_of_scope")


class Round3RouterTests(unittest.TestCase):
    """Generated independent paraphrases for the wider dialect families."""


def _add_round3_test(number, question, expected_services, status="ok"):
    def test(self):
        result = route(question)
        self.assertEqual(result["status"], status, (question, result))
        self.assertEqual(result["services"], list(expected_services), (question, result))

    setattr(Round3RouterTests, "test_round3_%03d" % number, test)


_ROUND3_CASES = (
    # Lost: movement, failed search, theft, disappearance, and dialect letters.
    ("جوازي وقع مني بالسوق ومش لاقيه", ("passport_lost",)),
    ("الهوية طاحت مني وما بلاقيها", ("id_card_lost",)),
    ("نسيت دفتر العيلة بالتكسي وراح", ("family_book_lost",)),
    ("جوازي نشلوه مني بالباص", ("passport_lost",)),
    ("سرقوها من جيبتي، هويتي الذكية", ("id_card_lost",)),
    ("دفترنا اختفى ومش عارف وينه", ("family_book_lost",)),
    ("ظيعت الباسبور بالعزال", ("passport_lost",)),
    ("هويتي انخطفت مع المحفظة", ("id_card_lost",)),
    ("وقّعته مني وما رجع لقيته، جوازي", ("passport_lost",)),
    # Damaged: cuts, water, heat, adhesive, marks, bends, and child/pet damage.
    ("جوازي انشق وصار مشقوق", ("passport_damaged",)),
    ("هويتي انشكت من الطرف", ("id_card_damaged",)),
    ("قصوا دفترنا وصار مقصوص", ("family_book_damaged",)),
    ("الباسبور انكتع نصين", ("passport_damaged",)),
    ("غرق جوازي لما وقع بالمي", ("passport_damaged",)),
    ("هويتي تبللت وصارت مبلولة", ("id_card_damaged",)),
    ("نقعنا دفتر العيلة بالغلط", ("family_book_damaged",)),
    ("جوازي انغسل مع الغسيل", ("passport_damaged",)),
    ("بطاقتي ملزقة وذاب طرفها", ("id_card_damaged",)),
    ("طرف الباسبور داب من الحر", ("passport_damaged",)),
    ("دفتر العائلة ولع وصار محروق", ("family_book_damaged",)),
    ("هويتي اتمزعت وشخبطوا عليها", ("id_card_damaged",)),
    ("جوازي انمحى وصار ممسوح", ("passport_damaged",)),
    ("بطاقتي انطوت وصارت مطعوجة", ("id_card_damaged",)),
    ("الكلب أكل دفتر العيلة وبدي بدل عنه", ("family_book_damaged",)),
    ("الولد لعب في هويتي وخربها", ("id_card_damaged",)),
    ("جوازي انكسر وطق من النص", ("passport_damaged",)),
    ("دفترنا ملزق ومخربش", ("family_book_damaged",)),
    # Renewal: expiry, remaining validity, age, and extension conjugations.
    ("جوازي خلصت مدته", ("passport_renewal",)),
    ("هويتي قربت تخلص", ("id_card_renewal",)),
    ("دفترنا بيخلص الشهر الجاي", ("family_book_renewal",)),
    ("ضل فيه شهرين هالباسبور", ("passport_renewal",)),
    ("هويتي باقي فيها شهر", ("id_card_renewal",)),
    ("دفتر العيلة صار قديم وبدي أمدده", ("family_book_renewal",)),
    ("بدي تمديد صلاحية جوازي", ("passport_renewal",)),
    ("لازم نجدد هويتنا قبل السفر", ("id_card_renewal",)),
    # First issue and family-record topics without the word دفتر.
    ("لسا ما طلعت هويتي", ("id_card_first_issue",)),
    ("عمري ما استخرجت جواز سفر", ("passport_first_issue",)),
    ("ما عندنا دفتر عيلة لحد الآن", ("family_book_first_issue",)),
    ("أول مرة بطلع باسبور", ("passport_first_issue",)),
    ("بدي أعمل بطاقة ذكية", ("id_card_first_issue",)),
    ("لسا ما بنطلع جواز سفر لأي حدا منا", ("passport_first_issue",)),
    ("بدنا نطلع هوية جديدة", ("id_card_first_issue",)),
    ("لسا متجوزين وما معنا دفتر", ("family_book_first_issue",)),
    ("كتبنا الكتاب وبنسأل شو المطلوب", ("family_book_first_issue",)),
    ("فتح قيد مدني بعد العرس", ("family_book_first_issue",)),
    ("السجل المدني للزوجة الثانية شو شروطه", ("family_book_first_issue",)),
    ("المطلقة بدها تفتح قيد منفصل", ("family_book_first_issue",)),
    ("كيف نسجل الأبناء غير الشرعيين بالقيد المدني", ("family_book_first_issue",)),
    ("الزوجتين بدهم فتح سجل مدني", ("family_book_first_issue",)),
    ("حديثاً متزوجين وبدنا دفتر للعيلة", ("family_book_first_issue",)),
    # Marriage vocabulary must not override an explicit family-book situation.
    ("تزوجنا، بس دفترنا انسرق", ("family_book_lost",)),
    ("فتح قيد ودفتر العيلة ضاع", ("family_book_lost",)),
    # Explicit exclusions, including hours and online-only requests.
    ("كيف أطلع شهادة ميلاد لابني؟", (), "out_of_scope"),
    ("شو رسوم إصدار شهادة وفاة؟", (), "out_of_scope"),
    ("تزوجنا وبدي أطلع شهادة زواج", (), "out_of_scope"),
    ("وين بطلع شهادة طلاق؟", (), "out_of_scope"),
    ("شو ساعات دوام تجديد الجواز؟", (), "out_of_scope"),
    ("المكتب بعطل الجمعة لتجديد الهوية؟", (), "out_of_scope"),
    ("كيف أحجز موعد إلكتروني؟", (), "out_of_scope"),
    ("من وين أنزل تطبيق الهوية؟", (), "out_of_scope"),
    ("وين موقع إلكتروني لاستخراج الطلب؟", (), "out_of_scope"),
    ("كيف أحجز موعد إلكتروني لتجديد الجواز؟", ("passport_renewal",)),
    ("كيف أطلع رخصة مهنية جديدة؟", (), "out_of_scope"),
    ("بدي فيزا زيارة شو أوراقها؟", (), "out_of_scope"),
    ("شو شروط الجواز الخاص؟", (), "out_of_scope"),
)

for _index, _case in enumerate(_ROUND3_CASES, 1):
    _add_round3_test(_index, _case[0], _case[1], _case[2] if len(_case) > 2 else "ok")


if __name__ == "__main__":
    unittest.main()
