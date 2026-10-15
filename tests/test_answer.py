"""Tests for bot.answer with a fake LLM (no Ollama needed). Run: python3 -m unittest tests.test_answer -v"""
import unittest

from bot.answer import Bot


class FakeLLM:
    """Returns scripted replies in order and records every prompt."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, system, user, num_predict=None, temperature=None):
        self.calls.append((system, user))
        return self.replies.pop(0) if self.replies else ""


class AnswerTests(unittest.TestCase):
    def test_fee_rule_contexts_and_hints(self):
        llm = FakeLLM(["رسوم التجديد في حالتك 50 دينار، لأن عمرك فوق 16 سنة والمتبقي على جوازك أقل من 180 يوم."])
        ans, ctx, dbg = Bot(llm).answer("عمري 17 وجوازي باقي عليه 3 شهور، كم رسوم التجديد؟")
        self.assertIn("50", ans)
        prompt = llm.calls[0][1]
        # code picked the applicable fee line and shows it to the model
        self.assertIn("ينطبق: «50 دينار لمن هم فوق سن السادسة عشر", prompt)
        self.assertIn("لا ينطبق: «25 دينار", prompt)
        self.assertTrue(ctx and all(c.startswith("تجديد جواز السفر العادي") for c in ctx), ctx)
        self.assertTrue(any("50 دينار" in c for c in ctx), ctx)
        self.assertFalse(any("125" in c for c in ctx))

    def test_ungrounded_number_triggers_retry(self):
        llm = FakeLLM(["الرسوم 333 دينار.", "الرسوم 50 دينار لمن هم فوق سن 16 وجوازه متبقي به أقل من 180 يوم."])
        ans, ctx, dbg = Bot(llm).answer("عمري 20 وجوازي باقي عليه شهرين، قديش رسوم التجديد؟")
        self.assertEqual(len(llm.calls), 2)
        self.assertEqual(dbg.get("ungrounded_first_try"), ["333"])
        self.assertIn("50", ans)
        self.assertNotIn("333", ans)

    def test_total_of_two_source_fees_is_grounded(self):
        llm = FakeLLM(["رسوم التجديد 50 دينار، ويضاف 25 دينار لمكتب الخدمة المستعجلة، فيكون المجموع 75 ديناراً."])
        ans, ctx, dbg = Bot(llm).answer("جوازي منتهي وعمري 30 وبدي اياه بالخدمة المستعجلة، قديش المجموع؟")
        self.assertEqual(len(llm.calls), 1)  # 75 = 50 + 25, no retry
        self.assertTrue(any("مكتب الخدمة المستعجلة" in c for c in ctx), ctx)

    def test_out_of_scope_model_decline(self):
        llm = FakeLLM(["عذراً، لا تتوفر لدي معلومات عن تصديق الشهادات. أستطيع مساعدتك في خدمات جواز السفر ودفتر العائلة والبطاقة الذكية."])
        ans, ctx, dbg = Bot(llm).answer("كم رسوم تصديق الشهادة الجامعية؟")
        self.assertEqual(ctx, [])
        self.assertIn("عذراً", ans)
        self.assertNotIn("template", dbg)

    def test_out_of_scope_model_invents_number_uses_template(self):
        llm = FakeLLM(["سعر التذكرة حوالي 150 دينار."])
        ans, ctx, dbg = Bot(llm).answer("كم سعر تذكرة الطيران من عمان إلى دبي؟")
        self.assertEqual(ctx, [])
        self.assertEqual(dbg.get("template"), "decline")
        self.assertNotIn("150", ans)

    def test_unclear_asks_question(self):
        llm = FakeLLM(["هل تقصد تجديد جواز السفر أم تجديد دفتر العائلة أم تجديد البطاقة الذكية؟"])
        ans, ctx, dbg = Bot(llm).answer("بدي أجدد، شو المطلوب؟")
        self.assertEqual(ctx, [])
        self.assertIn("؟", ans)

    def test_unclear_but_same_value_everywhere_is_answered(self):
        llm = FakeLLM(["تستغرق خدمة البطاقة الذكية 20 دقيقة."])
        ans, ctx, dbg = Bot(llm).answer("قديش بتاخد الهوية وقت؟")
        self.assertIn("resolved_shared_field", dbg["route"])
        self.assertTrue(any("20 دقيقة" in c for c in ctx), ctx)

    def test_follow_up_uses_history(self):
        bot = Bot(FakeLLM([
            "المطلوب: دفتر العائلة المراد تجديده، والبطاقة الشخصية لمقدم الطلب، وبطاقة إحصاءات الجسور الصفراء أو مشروحات المتابعة والتفتيش لمن يلزم ذلك.",
            "نعم، يمكنك تقديم طلب تجديد دفتر العائلة في السفارات الأردنية والقنصليات بالخارج.",
        ]))
        hist = []
        q1 = "شو الأوراق المطلوبة لتجديد دفتر العائلة؟"
        a1, c1, d1 = bot.answer(q1, hist)
        hist.append({"question": q1, "route": d1["route"], "answer": a1})
        a2, c2, d2 = bot.answer("وبقدر أقدّم الطلب من السفارة إذا كنت برا البلد؟", hist)
        self.assertEqual(d2["route"]["services"], ["family_book_renewal"])
        self.assertTrue(any("أماكن تقديم الخدمة" in c and "السفارات" in c for c in c2), c2)
        self.assertIn("رسالة متابعة", bot.llm.calls[1][1])
        self.assertIn("يسأل عن أماكن تقديم الخدمة لخدمة تجديد دفتر العائلة", bot.llm.calls[1][1])

    def test_llm_failure_falls_back(self):
        class Broken:
            def chat(self, *a, **k):
                raise OSError("down")
        ans, ctx, dbg = Bot(Broken()).answer("كم يستغرق تجديد دفتر العائلة؟")
        self.assertEqual(dbg.get("template"), "extractive_fallback")
        self.assertIn("45", ans)
        self.assertTrue(ctx)

    def test_unclear_situation_resolved_by_model(self):
        q = "الهوية تبعتي صارت بحالة سيئة جداً بعد الرحلة الطويلة، شو بلزمني؟"
        llm = FakeLLM(["damaged", "المطلوب: نموذج البطاقة الشخصية، وإثبات شخصية، والبطاقة التالفة."])
        ans, ctx, dbg = Bot(llm, llm_route_fallback=True).answer(q)
        self.assertEqual(dbg["route"].get("resolved_by_llm"), "id_card_damaged")
        self.assertEqual(dbg["route"]["services"], ["id_card_damaged"])
        self.assertIn("damaged =", llm.calls[0][1])  # classification prompt offers the situations
        self.assertNotIn("passport", llm.calls[0][1])
        self.assertTrue(all(c.startswith("بطاقة الأحوال المدنية الذكية بدل تالف") for c in ctx), ctx)

    def test_unclear_model_says_none_keeps_clarifying(self):
        q = "الهوية تبعتي صارت بحالة سيئة جداً بعد الرحلة الطويلة، شو بلزمني؟"
        llm = FakeLLM(["none", "هل تقصد إصدار البطاقة لأول مرة أم تجديدها أم بدل فاقد أم بدل تالف؟"])
        ans, ctx, dbg = Bot(llm, llm_route_fallback=True).answer(q)
        self.assertNotIn("resolved_by_llm", dbg["route"])
        self.assertEqual(ctx, [])
        self.assertIn("؟", ans)

    def test_short_unclear_question_is_not_sent_to_classifier(self):
        llm = FakeLLM(["هل تقصد جواز سفر لأول مرة أم تجديد جواز السفر أم بدل فاقد أم بدل تالف؟"])
        ans, ctx, dbg = Bot(llm, llm_route_fallback=True).answer("كم رسوم جواز السفر؟")
        self.assertEqual(len(llm.calls), 1)  # only the clarifying question, no classification
        self.assertEqual(ctx, [])

    def test_comparison_gets_both_services(self):
        llm = FakeLLM(["جواز السفر بدل فاقد أغلى: رسومه 125 دينار للمرة الأولى، بينما رسوم بدل التالف 100 دينار."])
        ans, ctx, dbg = Bot(llm).answer("أيهما أغلى: جواز بدل تالف ولا بدل فاقد؟")
        joined = " ".join(ctx)
        self.assertIn("جواز سفر بدل فاقد - الرسوم", joined)
        self.assertIn("جواز سفر بدل تالف - الرسوم", joined)


if __name__ == "__main__":
    unittest.main()


class FalseDeclineTests(unittest.TestCase):
    """Routing is ok but the model says the info is missing (the #1 failure with command-r7b)."""

    def test_not_found_then_retry_answers(self):
        llm = FakeLLM(["NOT_FOUND", "رسوم البطاقة الذكية بدل تالف 3 دنانير."])
        ans, ctx, dbg = Bot(llm).answer("طيب والبطاقة الذكية بدل تالف قديش؟")
        self.assertEqual(len(llm.calls), 2)
        self.assertTrue(dbg.get("retry_not_found"))
        self.assertIn("NOT_FOUND", llm.calls[0][0])            # marker, not a ready-made refusal sentence
        self.assertNotIn("لا تتوفر لدي هذه المعلومة", llm.calls[0][0])
        self.assertIn("3", ans)
        self.assertTrue(ctx)

    def test_old_refusal_sentence_also_retried(self):
        llm = FakeLLM(["عذراً، لا تتوفر لدي هذه المعلومة في وثائق الخدمة.",
                       "لا تُصرف البطاقة المفقودة إلا بعد أسبوعين من تاريخ تبليغ الشرطة وبموافقة مدير المديرية."])
        ans, ctx, dbg = Bot(llm).answer("ضاعت هويتي وبلغت الشرطة امبارح، إيمتى بقدر أستلم البطاقة الجديدة؟")
        self.assertIn("أسبوعين", ans)
        self.assertTrue(any("ملاحظات" in c for c in ctx), ctx)

    def test_decline_followed_by_real_answer_is_kept(self):
        llm = FakeLLM(["عذراً، لا تتوفر لدي هذه المعلومة في وثائق الخدمة.\n\nوفقاً للمصادر، يجب فتح السجل المدني قبل مرور 90 يوم من تاريخ عقد الزواج، "
                       "وهناك غرامة قدرها 10 دنانير في حال التأخر."])
        ans, ctx, dbg = Bot(llm).answer("دفتر العائلة لأول مرة بنطلعه وقت ما بدنا وما في أي غرامة، صح؟")
        self.assertEqual(len(llm.calls), 1)
        self.assertNotIn("عذراً", ans)
        self.assertIn("90", ans)
        self.assertTrue(ctx)

    def test_two_not_found_gives_model_decline(self):
        llm = FakeLLM(["NOT_FOUND", "NOT_FOUND", "عذراً، هذه المعلومة غير متوفرة في وثائق الخدمة."])
        ans, ctx, dbg = Bot(llm).answer("هل بقدر أدفع رسوم تجديد الجواز بالبطاقة البنكية؟")
        self.assertTrue(dbg.get("not_in_documents"))
        self.assertEqual(ctx, [])
        self.assertIn("عذراً", ans)
        self.assertNotIn("NOT_FOUND", ans)

    def test_clarify_list_numbers_are_removed(self):
        llm = FakeLLM(["ما الوثيقة التي فقدتها؟\n1. جواز سفر بدل فاقد\n2. دفتر عائلة بدل فاقد\n3. بطاقة ذكية بدل فاقد"])
        ans, ctx, dbg = Bot(llm).answer("ضاع مني، شو بعمل؟")
        self.assertNotIn("template", dbg)
        self.assertFalse(any(ch.isdigit() for ch in ans), ans)


class FeeCaseTests(unittest.TestCase):
    """Code picks the applicable fee line; the model only copies it."""

    def setUp(self):
        from bot.kb import load_kb
        self.kb = load_kb()

    def _cases(self, q):
        from bot import fees, router
        return fees.cases(q, router.route(q)["services"], self.kb)

    def _amounts(self, case):
        from bot.fees import _amount
        return sorted(_amount(x) for x in case.apply)

    def test_valid_passport_more_than_180_days(self):
        c = self._cases("جوازي لسا ساري لسنة كاملة وعمري 35 وأنا بإربد، قديش تجديده؟")[0]
        self.assertEqual(self._amounts(c), [100])

    def test_urgent_office_total(self):
        c = self._cases("جوازي منتهي وعمري 45 وبدي أجدده بالخدمة المستعجلة، كم المجموع؟")[0]
        self.assertEqual(self._amounts(c), [25, 50])
        self.assertEqual(c.total[1], 75)

    def test_child_first_passport(self):
        c = self._cases("بنتي عمرها 7 سنين بدنا نطلعلها جواز لأول مرة، قديش؟")[0]
        self.assertEqual(self._amounts(c), [25])

    def test_first_passport_abroad(self):
        c = self._cases("عمري 30 ومقيم بقطر، بدي أطلع جواز سفر لأول مرة، كم الرسوم؟")[0]
        self.assertEqual(self._amounts(c), [100])

    def test_passport_lost_second_time(self):
        c = self._cases("جوازي ضاع تاني مرة، قديش بدفع؟")[0]
        self.assertEqual(self._amounts(c), [250])

    def test_family_book_late_fine(self):
        c = self._cases("اتجوزنا من خمس شهور ولسا ما طلعنا دفتر عائلة، قديش الرسوم؟")[0]
        self.assertEqual(self._amounts(c), [2, 10])
        self.assertEqual(c.total[1], 12)

    def test_family_book_renewal_not_expired(self):
        c = self._cases("دفتر العيلة لسا ساري بس بدي أجدده، قديش؟")[0]
        self.assertEqual(self._amounts(c), [3])

    def test_id_first_issue_adult_fine(self):
        c = self._cases("عمري 21 وعمري ما طلعت هوية، قديش بدفع؟")[0]
        self.assertEqual(self._amounts(c), [2, 10])

    def test_unknown_situation_gives_alternatives(self):
        c = self._cases("قديش رسوم تجديد دفتر العائلة؟")[0]
        self.assertEqual(c.apply, [])
        self.assertEqual(len(c.conditional), 2)

    def test_multi_person_story(self):
        q = ("أخوي ساكن بالسعودية وبدو يجدد جوازه، وأختي عمرها 12 وبدها جواز لأول مرة، "
             "وأنا جوازي انمزق، قديش كل واحد بيدفع؟")
        cs = {(c.service, c.who): self._amounts(c) for c in self._cases(q)}
        self.assertEqual(cs.get(("passport_renewal", "الأخ")), [100])
        self.assertEqual(cs.get(("passport_first_issue", "الأخت")), [25])
        self.assertEqual(cs.get(("passport_damaged", "المستخدم نفسه")), [100])

    def test_follow_up_uses_previous_question_facts(self):
        from bot import fees
        c = fees.cases("وإذا كنت برا البلد؟", ["passport_first_issue"], self.kb,
                       previous=["كم رسوم جواز السفر لأول مرة؟"])[0]
        self.assertEqual(self._amounts(c), [100])


class ModelDeclineWordingTest(unittest.TestCase):
    """The model's own decline wording must be accepted, otherwise the fixed template replaces it (rule: answers are model-generated)."""

    def test_real_model_declines_are_accepted(self):
        from bot import answer as A
        for text in [
            "أنا آسف، لا يمكنني الإجابة على هذا السؤال. أنا متخصص في خدمات دائرة الأحوال المدنية والجوازات، ويمكنني مساعدتك في جواز السفر ودفتر العائلة والبطاقة الذكية.",
            "عذراً، لا تتوفر لدي معلومات عن هذا الموضوع.",
            "أنا آسف، لا يمكنني الإجابة على هذا السؤال. هل هناك أي شيء آخر يمكنني مساعدتك به؟",
        ]:
            self.assertTrue(A._is_decline(text), text)

    def test_real_answers_are_not_declines(self):
        from bot import answer as A
        for text in ["يستغرق تجديد دفتر العائلة 45 دقيقة.", "الرسوم 50 دينار لمن تجاوز السادسة عشرة وجوازه منتهي.",
                     "يمكنك تقديم الطلب في مكاتب دائرة الأحوال المدنية والجوازات."]:
            self.assertFalse(A._is_decline(text), text)


class NoModelSubstitutionTest(unittest.TestCase):
    """Rule: only the provided model may generate answers; a missing model must never be replaced by another one."""

    def test_missing_model_is_not_replaced(self):
        from bot.llm import LLM, load_config
        llm = LLM(load_config())
        llm.available_models = lambda: ["qwen3:8b", "llama3:8b"]
        model, status = llm.resolve_model()
        self.assertEqual(model, llm.model)
        self.assertNotIn(model, ("qwen3:8b", "llama3:8b"))
        self.assertTrue(status.startswith("configured model"))

    def test_configured_model_found(self):
        from bot.llm import LLM, load_config
        llm = LLM(load_config())
        llm.available_models = lambda: [llm.model]
        self.assertEqual(llm.resolve_model(), (llm.model, "ok"))
