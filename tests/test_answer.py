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
        self.assertIn("أقل من 180 يوماً", prompt)   # precomputed comparison given to the model
        self.assertIn("أكبر من 16 سنة", prompt)
        self.assertTrue(ctx and all(c.startswith("تجديد جواز السفر") for c in ctx), ctx)
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
        self.assertIn("السؤال السابق", bot.llm.calls[1][1])

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
        self.assertTrue(all(c.startswith("بطاقة ذكية بدل تالف") for c in ctx), ctx)

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
