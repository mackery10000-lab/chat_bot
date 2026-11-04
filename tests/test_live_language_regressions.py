"""실모델의 올바른 해석을 서버 보정이 뒤집지 않는지 실제 게임 경로로 확인한다."""

import json
from unittest.mock import patch

from services.generator import DemoGenerator
from tests.test_smoke import GameTestCase, intent


class LiveLanguageRegressionTest(GameTestCase):
    def ready_for_description(self):
        self.three()
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")

    def parsed_call(self, message, raw):
        raw = dict(raw, quote=message)
        parser = DemoGenerator()
        with patch.object(parser, "_complete", return_value=json.dumps(raw)) as complete, \
             patch.object(self.model, "interpret", side_effect=parser.interpret):
            self.call(message=message)
        complete.assert_called_once()

    def test_correct_model_hole_negation_never_awards_ticket(self):
        for message in (
            "누렇게 바랜 종이에 구멍이 안 난 승차권을 찾고 있어요.",
            "구멍은 안 나 있고 종이는 누렇게 바랬어요.",
            "누렇게 바랜 종이인데 구멍은 안 났다니까요.",
            "승차권은 누렇게 바랜 종이예요. 구멍은 안났어요.",
        ):
            with self.subTest(message=message):
                self.new()
                self.ready_for_description()
                self.parsed_call(message, intent(
                    "describe", "cleaner", "appearance", features=["faded"], denied=["hole"]
                ))
                self.assertNotIn("ticket_old", self.items())
                self.assertFalse(self.flags().get("ticket_recovered"))
                self.assertIn("휴지", self.data["reply"])
                self.assertEqual(self.data["events"], [])

    def test_explicit_hole_negation_overrides_incorrect_model_positive(self):
        self.ready_for_description()
        self.parsed_call(
            "누렇게 바랜 종이에 구멍이 안 난 승차권 보셨나요?",
            intent("describe", "cleaner", "appearance", features=["faded", "hole"]),
        )
        self.assertNotIn("ticket_old", self.items())
        self.assertIn("휴지", self.data["reply"])

    def test_emphasis_keeps_both_features_and_awards_only_once(self):
        for message in (
            "누렇게 바랜 종이에 실제로 구멍이 뚫린 승차권 보셨나요?",
            "실제로 누렇게 바랜 종이에 구멍이 있는 승차권을 찾고 있어요.",
            "누렇게 바랜 종이입니다. 실제로 구멍도 뚫려 있는 승차권이에요.",
        ):
            with self.subTest(message=message):
                self.new()
                self.ready_for_description()
                raw = intent("describe", "cleaner", "appearance", features=["faded", "hole"])
                self.parsed_call(message, raw)
                self.assertIn("ticket_old", self.items())
                self.assertTrue(self.flags()["ticket_recovered"])
                self.assertIn("여기 있습니다", self.data["reply"])
                self.assertEqual([e["item"]["id"] for e in self.data["events"]], ["ticket_old"])
                self.parsed_call(message, raw)
                self.assertEqual(self.data["events"], [])

    def test_explicit_correction_keeps_final_positive_description(self):
        self.ready_for_description()
        self.parsed_call(
            "구멍이 없다고 한 설명은 취소할게요. 실제로 누렇게 바랜 종이에 구멍이 뚫린 승차권이에요.",
            intent("describe", "cleaner", "appearance", features=["faded", "hole"]),
        )
        self.assertIn("ticket_old", self.items())
        self.assertIn("여기 있습니다", self.data["reply"])

    def test_model_question_and_non_execution_modes_are_preserved(self):
        for mode in ("question", "negated", "reported", "hypothesis"):
            with self.subTest(mode=mode):
                self.new()
                self.ready_for_description()
                message = {
                    "question": "그 승차권은 실제로 누렇게 바랜 종이인가요? 구멍도 있나요?",
                    "negated": "누렇게 바랜 종이에 실제로 구멍이 뚫린 표를 찾지는 않겠습니다.",
                    "reported": "어르신이 실제로 누렇게 바랜 종이에 구멍이 있다고 말했대요.",
                    "hypothesis": "만약 실제로 누렇게 바랜 종이에 구멍이 있는 표라면 어떨까요?",
                }[mode]
                self.parsed_call(message, intent(
                    "describe", "cleaner", "appearance", mode=mode, features=["faded", "hole"]
                ))
                self.assertNotIn("ticket_old", self.items())
                self.assertFalse(self.flags().get("ticket_recovered"))
