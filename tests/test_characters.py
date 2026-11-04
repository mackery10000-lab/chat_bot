"""사용자 인물 설정의 실제 대화 반영과 기존 진행 조건 보존을 검증한다."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import app as web
from services.character_dialogue import character_mood
from services.generator import DemoGenerator
from tests.test_smoke import GameTestCase, intent


class CharacterDialogueTest(GameTestCase):
    def stable_progress(self):
        state = self.service.store.get(self.client.get_cookie(web.COOKIE).value)
        return {key: deepcopy(state.get(key)) for key in
                ("flags", "inventory", "read", "attempts", "confirmation", "status", "scenario_steps")}

    def test_explorer_has_source_background_and_keeps_cheerful_attitude(self):
        self.a("inspect", "notice"); self.a("move", "car_2")
        self.a("select_npc", "explorer")
        before = self.stable_progress()
        self.t("explorer", "background")
        for text in ("탐험가", "2016", "2026", "궁금해서", "신나는"):
            self.assertIn(text, self.data["reply"])
        self.assertEqual(before, self.stable_progress())
        self.t("explorer", "injury")
        self.assertIn("낡은 바닥이 무너져", self.data["reply"])
        self.assertIn("2호차", self.data["reply"])
        self.assertEqual(before, self.stable_progress())
        self.t("explorer", "warning")
        for text in ("수첩", "장소와 시간", "다른 승객"):
            self.assertIn(text, self.data["reply"])
        self.assertEqual(before, self.stable_progress())

    def test_elder_distinguishes_hometown_memory_from_unknown_details(self):
        self.three()
        self.t("elder", "greeting")
        self.assertTrue(self.data["reply"].startswith("아이고"))
        self.assertIn("어디로 가는 길", self.data["reply"])
        before = self.stable_progress()
        self.t("elder", "background")
        for text in ("부산", "2016", "23시 59분", "기억이 안"):
            self.assertIn(text, self.data["reply"])
        self.assertNotRegex(self.data["reply"], "버뮤다|아지산|삶과 죽음|누렇게|구멍")
        self.t("elder", "off_topic")
        self.assertIn("기억이 안", self.data["reply"])
        self.assertEqual(before, self.stable_progress())

    def test_warning_does_not_make_elder_or_cleaner_omniscient(self):
        self.three()
        for npc in ("elder", "cleaner"):
            with self.subTest(npc=npc):
                before = self.stable_progress()
                self.t(npc, "warning")
                self.assertIn("걱정", self.data["reply"])
                self.assertNotRegex(self.data["reply"], "2026|10년|버뮤다|아지산|비밀번호|누렇게|구멍")
                self.assertEqual(before, self.stable_progress())

    def test_year_question_and_future_claim_have_distinct_reactions(self):
        self.three()
        for npc in ("elder", "cleaner"):
            self.call(value=intent(target=npc, topic="year"), message="지금 몇 년인가요?")
            self.assertIn("2016", self.data["reply"])
            self.assertNotIn("2026", self.data["reply"])
            self.call(value=intent(target=npc, topic="year"), message="지금은 2026년입니다.")
            self.assertIn("농담", self.data["reply"])
        self.ticket(); self.a("move", "car_4")
        before = self.stable_progress()
        self.call(value=intent(target="attendant", topic="year"), message="지금 몇 년입니까?")
        self.assertIn("2016년입니다", self.data["reply"])
        self.assertNotIn("2026", self.data["reply"])
        self.call(value=intent(target="attendant", topic="year"), message="현재는 2026년입니다.")
        self.assertIn("믿기 어렵", self.data["reply"])
        self.assertEqual(before, self.stable_progress())

    def test_rudeness_keeps_the_question_and_does_not_lock_out_elder(self):
        self.three()
        self.call(value=dict(intent(target="elder", topic="appearance"), behavior="rush"),
                  message="빨리 승차권 모양이나 말해요.")
        self.assertIn("재촉", self.data["reply"])
        self.assertIn("구멍", self.data["reply"])
        self.assertTrue(self.flags()["elder_features"])
        self.assertIn("elder_testimony", self.items())
        self.t("elder", "origin")
        self.assertIn("부산", self.data["reply"])
        self.assertEqual(self.data["game"]["status"], "playing")

    def test_cleaner_repetition_and_rudeness_do_not_swallow_ticket_description(self):
        self.three(); self.t("elder", "appearance")
        for _ in range(3):
            self.t("cleaner", "off_topic")
        self.assertIn("비켜", self.data["reply"])
        self.assertNotIn("ticket_old", self.items())
        description = "누렇게 바랜 종이에 구멍이 뚫려있는 승차권 보신적 있으신가요?"
        self.call(value=dict(intent(target="cleaner"), behavior="rush"), message=description)
        self.assertIn("ticket_old", self.items())
        self.assertIn("차분히", self.data["reply"])
        self.assertIn("그러시구먼요", self.data["reply"])
        self.assertTrue(self.flags()["ticket_recovered"])

    def test_attendant_softens_on_help_without_unlocking_engine_early(self):
        self.four(); self.a("select_npc", "attendant")
        self.assertEqual(self.data["scene"]["people"][0]["expression"], "guarded")
        self.office(); self.t("attendant", "greeting")
        self.assertIn("문을 열어주셔서 감사합니다", self.data["reply"])
        self.assertEqual(self.data["scene"]["people"][0]["expression"], "neutral")
        self.assertFalse(self.flags().get("engine_permission"))
        self.a("move", "engine")
        self.assertEqual(self.data["game"]["location"]["id"], "car_4")
        self.a("move", "crew"); self.a("read_report"); self.a("ack_document", "route_report")
        self.a("move", "car_4"); self.a("present", "route_report", recipient="attendant")
        self.assertTrue(self.flags()["engine_permission"])
        self.call(value=intent(target="attendant", topic="year"), message="지금은 2026년입니다.")
        self.assertIn("약속대로", self.data["reply"])
        self.assertNotIn("허가할 수는 없습니다", self.data["reply"])

    def test_driver_remains_cautious_and_only_changes_year_after_proof(self):
        self.engine()
        before = self.stable_progress()
        self.t("driver", "background")
        self.assertIn("2016년 23시 59분", self.data["reply"])
        self.assertIn("경로 확인", self.data["reply"])
        self.assertEqual(before, self.stable_progress())
        self.t("driver", "destination")
        self.assertIn("위험 구간", self.data["reply"])
        self.call(value=intent(target="driver", topic="year"), message="지금은 2026년입니다.")
        self.assertIn("현재는 2016년", self.data["reply"])
        self.assertFalse(self.flags().get("year_proven"))
        self.assertEqual(self.data["game"]["attempts"], 1)
        self.prove(); self.t("driver", "year")
        self.assertIn("10년이나", self.data["reply"])
        self.assertIn("현재가 2026년", self.data["reply"])
        self.assertEqual(self.data["game"]["attempts"], 1)

    def test_runtime_passes_character_mood_and_knowledge_boundaries(self):
        self.four(); self.office()
        with patch.object(self.model, "generate", wraps=self.model.generate) as generated:
            self.t("attendant", "off_topic")
        character = generated.call_args.args[2]
        self.assertIn("부드럽게", character["_runtime"]["mood"])
        self.assertEqual(character["_runtime"]["recognized_year"], 2016)
        self.assertIn("unknown_information", character["persona"])
        generator = DemoGenerator()
        with patch.object(generator, "_complete", return_value=json.dumps({"lead_in": ""})) as complete:
            generator.generate("질문", "사용자", character, [])
        payload = complete.call_args.args[1]
        self.assertEqual(payload["current_mood"], character["_runtime"]["mood"])
        self.assertEqual(payload["current_year_belief"], 2016)
        self.assertIn("협조", character_mood("driver", {"year_proven": True}))


class CharacterInterpretationTest(unittest.TestCase):
    def test_background_and_injury_do_not_match_unrelated_story_choices(self):
        for message, topic in (("왜 이 열차에 타셨나요?", "background"),
                               ("무슨 일을 하시나요?", "background"),
                               ("발목은 어쩌다 다쳤어요?", "injury")):
            with self.subTest(message=message):
                value = dict(intent(target="explorer"), dialogue_choice_id="story.explorer.entry.why", quote=message)
                with patch.object(DemoGenerator, "_complete", return_value=json.dumps(value)):
                    parsed = DemoGenerator().interpret(message, {"active_npc": "explorer"})
                self.assertEqual(parsed["topic"], topic)
                self.assertEqual(parsed["dialogue_choice_id"], "")

    def test_rushed_question_keeps_topic_and_description_is_prioritized(self):
        message = "빨리 표의 모양이나 알려주세요."
        value = dict(intent(target="elder", topic="appearance"), behavior="rush", quote=message)
        with patch.object(DemoGenerator, "_complete", return_value=json.dumps(value)):
            parsed = DemoGenerator().interpret(message, {"active_npc": "elder"})
        self.assertEqual((parsed["intent"], parsed["topic"], parsed["behavior"]), ("talk", "appearance", "rush"))


if __name__ == "__main__":
    unittest.main()
