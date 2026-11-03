"""화면·게임 경로·장애를 실제 API 과금 없이 검증한다. 실제 AI 품질은 별도 검수한다."""

import json
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import app as web
from services.chatbot_service import ChatbotService
from services.generator import AIUnavailable, DemoGenerator
from services.retriever import KnowledgeHit


def intent(
    kind="talk",
    target="",
    topic="other",
    mode="act",
    features=(),
    denied=(),
    recipient="",
    described_item="ticket_old",
    relation="same",
):
    return dict(
        intent=kind,
        target=target,
        recipient=recipient,
        topic=topic,
        mode=mode,
        affirmed_features=list(features),
        denied_features=list(denied),
        quote="검수 입력",
        described_item=described_item,
        referent_relation=relation,
        feature_evidence=[],
        requested_facts=[],
        behavior="",
        dialogue_choice_id="",
    )


class ScriptedModel:
    def __init__(self):
        self.value = intent()
        self.fail = False

    def interpret(self, message, context):
        if self.fail:
            raise AIUnavailable("검수용 연결 실패")
        return self.value.copy()

    def generate(self, question, username, character, knowledge):
        if self.fail:
            raise AIUnavailable("검수용 연결 실패")
        return character.get("_runtime", {}).get(
            "canonical", "안녕, " + username + "님!"
        )


class GameTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.model = ScriptedModel()
        self.seq = 0
        self.service = ChatbotService(
            generator=self.model, db_path=Path(self.tmp.name) / "state.sqlite3"
        )
        self.swap = patch.object(web, "chatbot", self.service)
        self.swap.start()
        self.client = web.app.test_client()
        self.new()

    def tearDown(self):
        self.swap.stop()
        self.tmp.cleanup()

    def new(self):
        r = self.client.post("/api/game/new", json={"username": "헤슬"})
        self.assertEqual(r.status_code, 200)
        self.data = r.json

    def call(self, action=None, value=None, message="검수 입력", rid=None):
        self.seq += 1
        if value is not None:
            value = dict(value)
            if message == "검수 입력":
                if value.get("quote") != "검수 입력":
                    message = value["quote"]
                elif value["intent"] == "describe":
                    parts=[]
                    for f in ("faded", "hole"):
                        if f in value.get("denied_features", []):
                            parts.append("종이는 바래지 않았습니다" if f == "faded" else "구멍은 없습니다")
                        elif f in value.get("affirmed_features", []):
                            parts.append("누렇게 바랜 종이입니다" if f == "faded" else "구멍이 있습니다")
                    message=". ".join(parts)+"."
            value["quote"]=message
            self.model.value = value
        p = {
            "request_id": rid or "request_" + str(self.seq),
            "revision": self.data["game"]["revision"],
        }
        if action is not None:
            p["action"] = action
        else:
            p["message"] = message
        r = self.client.post("/api/chat", json=p)
        self.assertEqual(r.status_code, 200, r.json)
        self.data = r.json
        return self.data

    def a(self, kind, target="", **extra):
        return self.call(action={"type": kind, "target": target, **extra})

    def t(self, npc, topic="other", **kw):
        return self.call(value=intent(target=npc, topic=topic, **kw))

    def flags(self):
        return self.service.store.get(self.client.get_cookie(web.COOKIE).value)["flags"]

    def items(self):
        return {x["id"] for x in self.data["game"]["inventory"]}

    def three(self):
        self.a("inspect", "notice")
        self.a("move", "car_2")
        self.t("explorer", "identity")
        self.t("explorer", "departure")
        self.a("move", "car_3")
        self.a("use_item", "flashlight")

    def ticket(self):
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")
        self.call(
            value=intent(
                "describe", "cleaner", "appearance", features=["faded", "hole"]
            )
        )
        self.a("read_item", "ticket_old")
        self.call(value=intent("present", "ticket_old", recipient="elder"))
        self.t("elder", "destination")

    def four(self):
        self.three()
        self.ticket()
        self.a("move", "car_4")

    def office(self):
        self.t("attendant", "loop")
        self.t("attendant", "permission")
        self.call(value=intent("accept", "attendant"))
        self.a("read_item", "facility_manual")
        self.a("operate", "cover")
        self.a("operate", "lever_down")
        self.a("operate", "handle")

    def engine(self):
        self.four()
        self.office()
        self.a("move", "crew")
        self.a("read_report")
        self.a("ack_document", "route_report")
        self.a("move", "car_4")
        self.call(value=intent("present", "route_report", recipient="attendant"))
        self.a("move", "engine")
        self.t("driver", "destination")

    def prove(self, item="ticket_current"):
        self.a("prepare_evidence", item)
        self.a("confirm", token=self.data["game"]["confirmation"]["token"])

    def submit(self, destination="아지산역", password="2026"):
        self.a("prepare_control", destination=destination, password=password)
        self.a("confirm", token=self.data["game"]["confirmation"]["token"])

class SmokeTest(GameTestCase):
    def test_pages_and_referenced_assets(self):
        for route in ("/", "/detail", "/chat?username=헤슬", "/health"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        for asset in (
            "js/chatbot.js",
            "js/puzzles.js",
            "puzzles/lever-box/style.css",
            "puzzles/lever-box/images/box.webp",
            "puzzles/lever-box/images/lever-handle.webp",
            "puzzles/dial-puzzle/style.css",
            "puzzles/dial-puzzle/images/panel.webp",
            "puzzles/dial-puzzle/images/lever-arm.webp",
            "css/style.css",
            "css/NanumGothic.ttf",
            "images/hateslop-logo.png",
            "images/scene_01.png",
            "images/portrait_01.png",
            "images/car1/background.png",
            "images/car1/window.png",
            "images/car1/notice-hotspot.png",
            "images/car1/notice.png",
            "videos/car1-window-loop.mp4",
            "videos/car1-window-loop.webm",
        ):
            r = self.client.get("/assets/" + asset)
            self.assertEqual(r.status_code, 200)
            r.close()

    def test_chat_returns_demo_response(self):
        # 원본 테스트 이름만 보존하며 API 호출은 모의 생성기로 격리한다.
        self.a("inspect", "notice")
        self.a("move", "car_2")
        self.t("explorer", "identity")
        self.assertIn("newspaper", self.items())
        self.assertIsInstance(self.data["reply"], str)

    def test_bad_inputs_are_rejected(self):
        cases = [
            ({}, 400),
            ({"message": "   "}, 400),
            ({"message": "x" * 2001}, 413),
            ({"message": "안녕", "username": 1}, 400),
            ({"message": 5}, 400),
            ({"message": "x", "action": {}}, 400),
            ({"action": 5}, 400),
            ({"action": {"type": "look"}, "revision": True}, 400),
            ({"message": "안녕", "request_id": "x"}, 400),
        ]
        for p, status in cases:
            with self.subTest(case=str(p)[:40]):
                self.assertEqual(
                    self.client.post("/api/chat", json=p).status_code, status
                )
        self.assertEqual(
            self.client.post(
                "/api/chat", data="broken", content_type="application/json"
            ).status_code,
            400,
        )

    def test_service_failure_is_not_a_successful_null(self):
        self.model.fail = True
        rev = self.data["game"]["revision"]
        r = self.client.post(
            "/api/chat",
            json={"message": "안녕", "request_id": "failed_once", "revision": rev},
        )
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.client.get("/api/game").json["game"]["revision"], rev)

    def test_service_passes_character_and_retrieved_sources_to_generator(self):
        hit = KnowledgeHit("세계관 설정", "검수 자료")

        class Retriever:
            def search(self, q):
                return [hit]

        class Generator:
            def generate(self, *args):
                self.args = args
                return "확인했습니다."

        gen = Generator()
        svc = ChatbotService(
            Retriever(), gen, db_path=Path(self.tmp.name) / "legacy.sqlite3"
        )
        c = {"name": "안내인"}
        r = svc.generate_response("질문", "헤슬", c)
        self.assertEqual(gen.args, ("질문", "헤슬", c, [hit]))
        self.assertEqual(r["sources"], ["세계관 설정"])

    def test_initial_state_and_private_paths(self):
        self.assertEqual(self.items(), {"ticket_current"})
        for p in (
            "/.env",
            "/.env.example",
            "/config/chatbot_config.json",
            "/data/knowledge/example_lore.md",
            "/api/item/route_report",
        ):
            with self.subTest(path=p):
                r = self.client.get(p)
                self.assertIn(r.status_code, (403, 404))
                r.close()
        self.assertNotIn("아지산", json.dumps(self.data, ensure_ascii=False))

    def test_preconditions_cannot_be_skipped(self):
        for kind, target in [
            ("move", "engine"),
            ("move", "car_3"),
            ("move", "crew"),
            ("read_item", "facility_manual"),
            ("operate", "lever_down"),
            ("read_report", ""),
        ]:
            self.a(kind, target)
            self.assertEqual(self.data["game"]["location"]["id"], "car_1")
            self.assertEqual(self.items(), {"ticket_current"})

    def test_dark_room_does_not_reveal_npcs(self):
        self.a("inspect", "notice")
        self.a("move", "car_2")
        self.t("explorer", "departure")
        self.a("move", "car_3")
        self.assertEqual(self.data["scene"]["people"], [])
        self.t("elder", "appearance")
        self.assertNotIn("elder_testimony", self.items())
        self.a("use_item", "flashlight")
        self.assertEqual(len(self.data["scene"]["people"]), 2)

    def test_unprompted_keyword_list_waits_for_confirmation(self):
        self.three()
        self.t("elder", "appearance")
        self.call(
            value=dict(
                intent("describe", "cleaner", "appearance", features=["faded", "hole"]),
                quote="바랜 종이 구멍",
            )
        )
        self.assertNotIn("ticket_old", self.items())
        self.assertEqual(
            self.service.store.get(self.client.get_cookie(web.COOKIE).value)[
                "pending_dialogue"
            ],
            "confirm_description",
        )
        self.call(value=intent("accept", "cleaner"))
        self.assertIn("ticket_old", self.items())

    def test_misparsed_negative_abandon_is_not_prepared(self):
        self.call(value=dict(intent("abandon"), quote="탈출을 포기하지 않겠습니다."))
        self.assertIsNone(self.data["game"]["confirmation"])
        self.assertEqual(self.data["game"]["status"], "playing")

    def test_canceling_a_description_is_not_abandon(self):
        self.call(
            value=dict(intent("abandon"), quote="구멍이 없다는 설명을 취소할게요.")
        )
        self.assertIsNone(self.data["game"]["confirmation"])

    def test_concurrent_turn_does_not_execute_twice(self):
        entered = threading.Event()
        release = threading.Event()
        gid = self.client.get_cookie(web.COOKIE).value
        original = self.model.interpret

        def blocking(*args):
            entered.set()
            release.wait(3)
            return original(*args)

        self.model.interpret = blocking
        errors = []

        def first():
            try:
                self.service.process(
                    gid, "concurrent_first", message="검수 입력", expected=0
                )
            except Exception as ex:
                errors.append(ex)

        thread = threading.Thread(target=first)
        thread.start()
        self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(Exception) as caught:
                self.service.process(
                    gid, "concurrent_second", action={"type": "look"}, expected=0
                )
            self.assertEqual(getattr(caught.exception, "code", ""), "turn_busy")
        finally:
            release.set()
            thread.join(4)
        self.assertFalse(errors)
        self.assertEqual(self.service.store.get(gid)["revision"], 1)

    def test_npc_history_does_not_share_other_conversations(self):
        self.three()
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")
        with patch.object(
            self.model, "generate", wraps=self.model.generate
        ) as generated:
            self.t("elder", "year")
        history = generated.call_args.args[2]["_runtime"]["history"]
        self.assertTrue(history)
        self.assertTrue(all(h.get("npc") == "elder" for h in history))

    def test_non_actions_do_not_award(self):
        for mode in ("negated", "hypothesis", "reported", "unclear", "question"):
            self.call(value=intent("inspect", "notice", mode=mode))
            self.assertFalse(self.flags().get("notice_read"))
        self.a("inspect", "notice")
        self.assertTrue(self.flags()["notice_read"])

    def test_cleaner_requires_owner_information(self):
        self.three()
        self.call(
            value=intent(
                "describe", "cleaner", "appearance", features=["faded", "hole"]
            )
        )
        self.assertNotIn("ticket_old", self.items())

    def test_cleaner_third_turn_hint_and_no_lockout(self):
        self.three()
        for _ in range(3):
            self.t("cleaner", "lost_ticket")
        self.assertIn("어르신", self.data["reply"])
        self.ticket()
        self.assertIn("ticket_old", self.items())

    def test_partial_feature_answers_are_separate_retries(self):
        self.three()
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")
        self.call(value=intent("describe", "cleaner", "appearance", features=["faded"]))
        self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("describe", "cleaner", "appearance", features=["hole"]))
        self.assertIn("영수증", self.data["reply"])
        self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("describe", "cleaner", "appearance", features=["faded", "hole"]))
        self.assertIn("ticket_old", self.items())

    def test_denied_feature_prevents_ticket(self):
        self.three()
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")
        self.call(
            value=intent(
                "describe",
                "cleaner",
                "appearance",
                features=["faded", "hole"],
                denied=["hole"],
            )
        )
        self.assertNotIn("ticket_old", self.items())

    def test_switching_npc_clears_partial_description(self):
        self.three()
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")
        self.call(value=intent("describe", "cleaner", "appearance", features=["faded"]))
        self.a("select_npc", "elder")
        self.a("select_npc", "cleaner")
        self.call(value=intent("describe", "cleaner", "appearance", features=["hole"]))
        self.assertNotIn("ticket_old", self.items())

    def test_return_preserves_record(self):
        self.three()
        self.ticket()
        self.assertIn("ticket_old", self.items())
        self.assertIn("원본은", str(self.client.get("/api/item/ticket_old").json))

    def test_ownership_is_not_reading(self):
        self.three()
        self.assertFalse(self.flags().get("manual_read"))
        self.a("read_item", "facility_manual")
        self.assertTrue(self.flags()["manual_read"])

    def test_door_sequence_and_manual_gate(self):
        self.four()
        self.t("attendant", "loop")
        self.t("attendant", "permission")
        self.call(value=intent("accept", "attendant"))
        self.a("operate", "cover")
        self.assertFalse(self.flags().get("cover_open"))
        self.a("read_item", "facility_manual")
        self.a("operate", "lever_down")
        self.assertFalse(self.flags().get("lever_down"))
        self.a("operate", "cover")
        self.a("operate", "handle")
        self.assertFalse(self.flags().get("door_open"))
        self.a("operate", "lever_up")
        self.assertFalse(self.flags().get("lever_down"))
        self.a("operate", "lever_down")
        self.a("operate", "handle")
        self.assertTrue(self.flags()["door_open"])

    def test_destination_revealed_by_report_only(self):
        self.four()
        self.office()
        self.a("move", "crew")
        self.assertNotIn("아지산", json.dumps(self.data, ensure_ascii=False))
        self.a("inspect", "desk")
        self.assertIn("아지산", json.dumps(self.data, ensure_ascii=False))
        self.assertTrue(self.flags()["report_found"])
        self.assertFalse(self.flags().get("report_read"))
        self.a("read_report")
        self.assertIn("아지산", json.dumps(self.data, ensure_ascii=False))

    def test_engine_requires_report_delivery(self):
        self.four()
        self.office()
        self.a("move", "engine")
        self.assertEqual(self.data["game"]["location"]["id"], "car_4")
        self.a("move", "crew")
        self.a("read_report")
        self.a("move", "engine")
        self.assertNotEqual(self.data["game"]["location"]["id"], "engine")

    def test_reading_inventory_is_not_submission(self):
        self.engine()
        for item in sorted(self.items()):
            self.a("read_item", item)
            self.assertEqual(self.data["game"]["status"], "playing")
        self.assertFalse(self.flags().get("year_proven"))

    def test_evidence_cancel_is_safe(self):
        self.engine()
        self.a("prepare_evidence", "flashlight")
        self.assertEqual(self.data["game"]["status"], "playing")
        self.a("cancel")
        self.assertEqual(self.data["game"]["status"], "playing")

    def test_wrong_evidence_requires_confirmation(self):
        for item in (
            "flashlight",
            "facility_manual",
            "elder_testimony",
            "ticket_old",
            "route_report",
        ):
            with self.subTest(item=item):
                self.new()
                self.engine()
                self.a("prepare_evidence", item)
                self.assertEqual(self.data["game"]["status"], "playing")
                self.a("confirm", token=self.data["game"]["confirmation"]["token"])
                self.assertEqual(self.data["game"]["status"], "bad")
                self.assertEqual(self.data["game"]["reason"], "wrong_evidence")

    def test_good_paths_both_evidence_items_and_spaces(self):
        for evidence in ("ticket_current", "newspaper"):
            for dest in ("아지산역",):
                for pw in ("2026", " 2026 "):
                    with self.subTest(evidence=evidence, dest=dest, pw=pw):
                        self.new()
                        self.engine()
                        self.prove(evidence)
                        self.assertEqual(self.data["game"]["attempts"], 1)
                        self.submit(dest, pw)
                        self.assertEqual(self.data["game"]["status"], "playing")
                        self.assertEqual(
                            self.data["game"]["location"]["id"], "platform"
                        )
                        self.a("disembark")
                        self.assertEqual(self.data["game"]["status"], "good")

    def test_valid_wrong_control_is_bad(self):
        for dest, pw in [
            ("아지산역", "2016"),
            ("아지산역", "0000"),
            ("다른역", "2026"),
        ]:
            with self.subTest(dest=dest, pw=pw):
                self.new()
                self.engine()
                self.prove()
                self.submit(dest, pw)
                self.assertEqual(self.data["game"]["status"], "bad")
                self.assertEqual(self.data["game"]["attempts"], 0)

    def test_bad_format_preserves_attempt(self):
        self.engine()
        self.prove()
        for dest, pw in [
            ("", "2026"),
            ("아지산", "26"),
            ("아지산", "２０２６"),
            ("아지산", "2026년"),
            ("아지산", None),
        ]:
            self.seq += 1
            r = self.client.post(
                "/api/chat",
                json={
                    "action": {
                        "type": "prepare_control",
                        "destination": dest,
                        "password": pw,
                    },
                    "request_id": "format_" + str(self.seq),
                    "revision": self.data["game"]["revision"],
                },
            )
            self.assertEqual(r.status_code, 400)
            self.assertEqual(self.client.get("/api/game").json["game"]["attempts"], 1)

    def test_password_question_does_not_operate(self):
        self.engine()
        self.prove()
        self.t("driver", "password", mode="question")
        self.assertEqual(self.data["game"]["attempts"], 1)
        self.assertEqual(self.data["game"]["status"], "playing")

    def test_abandon_is_explicit(self):
        self.call(value=intent("abandon", mode="negated"))
        self.assertEqual(self.data["game"]["status"], "playing")
        self.a("abandon")
        self.assertEqual(self.data["game"]["status"], "playing")
        self.a("confirm", token=self.data["game"]["confirmation"]["token"])
        self.assertEqual(self.data["game"]["status"], "bad")

    def test_threat_impossible_and_unknown(self):
        for kind in ("threat", "impossible", "unknown"):
            self.call(value=intent(kind))
            self.assertEqual(self.items(), {"ticket_current"})
            self.assertEqual(self.data["game"]["status"], "playing")

    def test_duplicate_returns_exact_result(self):
        d = self.call(
            action={"type": "inspect", "target": "notice"}, rid="duplicate_check"
        )
        r = self.client.post(
            "/api/chat",
            json={
                "action": {"type": "inspect", "target": "notice"},
                "request_id": "duplicate_check",
                "revision": 0,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, d)

    def test_reused_id_conflict(self):
        self.call(action={"type": "inspect", "target": "notice"}, rid="conflict_check")
        r = self.client.post(
            "/api/chat",
            json={"action": {"type": "look"}, "request_id": "conflict_check"},
        )
        self.assertEqual(r.status_code, 409)

    def test_final_double_submit_and_terminal(self):
        self.engine()
        self.prove()
        self.a("prepare_control", destination="아지산역", password="2016")
        token = self.data["game"]["confirmation"]["token"]
        rev = self.data["game"]["revision"]
        d = self.call(action={"type": "confirm", "token": token}, rid="final_once")
        r = self.client.post(
            "/api/chat",
            json={
                "action": {"type": "confirm", "token": token},
                "request_id": "final_once",
                "revision": rev,
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json, d)
        self.a("inspect", "notice")
        self.assertEqual(self.data["game"]["status"], "bad")
        self.assertEqual(self.data["game"]["attempts"], 0)

    def test_stale_revision_and_confirmation_rejected(self):
        self.a("inspect", "notice")
        r = self.client.post(
            "/api/chat",
            json={
                "action": {"type": "look"},
                "request_id": "stale_check",
                "revision": 0,
            },
        )
        self.assertEqual(r.status_code, 409)
        r = self.client.post(
            "/api/chat",
            json={
                "action": {"type": "confirm", "token": "fake"},
                "request_id": "token_check",
                "revision": 1,
            },
        )
        self.assertEqual(r.status_code, 409)

    def test_save_restore_after_restart(self):
        self.three()
        gid = self.client.get_cookie(web.COOKIE).value
        again = ChatbotService(generator=self.model, db_path=self.service.store.path)
        self.assertEqual(again.snapshot(gid)["game"], self.data["game"])

    def test_same_name_users_are_isolated(self):
        self.a("inspect", "notice")
        other = web.app.test_client()
        r = other.post("/api/game/new", json={"username": "헤슬"})
        self.assertNotEqual(
            self.client.get_cookie(web.COOKIE).value, other.get_cookie(web.COOKIE).value
        )
        self.assertEqual(r.json["game"]["revision"], 0)
        self.assertEqual(r.json["game"]["journal"], [])

    def test_origin_and_bad_cookie(self):
        r = self.client.post(
            "/api/chat",
            json={"action": {"type": "look"}},
            headers={"Origin": "https://example.invalid"},
        )
        self.assertEqual(r.status_code, 403)
        other = web.app.test_client()
        other.set_cookie(web.COOKIE, "bad")
        self.assertEqual(other.get("/api/game").status_code, 404)

    def test_repeated_items_are_unique(self):
        self.three()
        self.a("move", "car_2")
        self.t("explorer", "departure")
        self.t("explorer", "departure")
        self.assertEqual(len(self.items()), len(self.data["game"]["inventory"]))

    def test_new_game_clears_progress(self):
        self.engine()
        self.prove()
        self.submit()
        self.a("disembark")
        self.new()
        self.assertEqual(self.items(), {"ticket_current"})
        self.assertNotIn("아지산", json.dumps(self.data, ensure_ascii=False))

    def test_generation_failure_rolls_back_gift(self):
        self.a("inspect", "notice")
        self.a("move", "car_2")
        self.model.value = intent(target="explorer")
        before = self.data["game"]
        with patch.object(
            self.model, "generate", side_effect=AIUnavailable("연결 실패")
        ):
            r = self.client.post(
                "/api/chat",
                json={
                    "message": "안녕",
                    "request_id": "generation_failure",
                    "revision": before["revision"],
                },
            )
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.client.get("/api/game").json["game"], before)

    def test_premature_model_spoiler_is_replaced_with_approved_dialogue(self):
        self.a("inspect", "notice")
        self.a("move", "car_2")
        before = self.data["game"]
        self.model.value = intent(target="explorer")
        with patch.object(self.model, "generate", return_value="아지산역으로 가세요"):
            r = self.client.post(
                "/api/chat",
                json={
                    "message": "안녕",
                    "request_id": "spoiler_failure",
                    "revision": before["revision"],
                },
            )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("아지산", r.json["reply"])
        self.assertIn("당신은 여기에 왜", r.json["reply"])
        self.assertEqual(r.json["game"]["revision"], before["revision"]+1)

    def test_scene_sources_and_cache(self):
        self.three()
        self.assertEqual(
            {p["id"] for p in self.data["scene"]["people"]}, {"elder", "cleaner"}
        )
        self.t("elder", "appearance")
        self.assertIn("실제로 확인한 외형 증언", self.data["sources"])
        self.assertNotIn("아지산", str(self.data["sources"]))
        self.assertEqual(
            self.client.get("/api/game").headers.get("Cache-Control"), "no-store"
        )


    # v1.1: audit F01-F13 and the requested interaction contract.
    def test_f01_excluded_targets_preserve_window(self):
        g=DemoGenerator()
        for text in ["안내문 대신 창문을 살펴보겠습니다.","안내문이 아니라 창문을 조사합니다.","안내문 말고 창문을 살펴볼게요."]:
            value=intent("inspect","window");value["quote"]=text
            parsed=g._ground(value,text,{})
            self.assertEqual(parsed["target"],"window")
            self.call(value=parsed,message=text)
            self.assertFalse(self.flags().get("notice_read"))
            self.assertTrue(self.flags().get("loop_observed"))

    def test_f01_desk_and_old_ticket_normalization(self):
        g=DemoGenerator()
        self.assertEqual(g._ground(intent("inspect","desk"),"시설 안내서 대신 책상을 살펴보겠습니다.")["target"],"desk")
        self.assertEqual(g._ground(intent("inspect","ticket_current"),"2016년 승차권을 읽겠습니다.")["target"],"ticket_old")

    def test_f02_other_objects_do_not_accumulate(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded"],described_item="tissue"),message="이 휴지는 누렇게 바랜 종이입니다.")
        self.call(value=intent("describe","cleaner","appearance",features=["hole"],described_item="receipt"),message="저 영수증에는 구멍이 있어요.")
        self.assertNotIn("ticket_old",self.items())

    def test_f02_current_ticket_is_not_old_ticket(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]),message="제 승차권은 누렇게 바랜 종이에 구멍이 있어요.")
        self.assertNotIn("ticket_old",self.items())

    def test_f03_all_fault_dialogues_replaced(self):
        self.three()
        for bad in ["목적지는 아-지-산 역입니다", "목적지는 아 지 산입니다", "초성은 ㅇㅈㅅ입니다", "비밀번호는 2026입니다", "황금 열쇠를 찾으세요", "표는 새 파란 종이입니다", "잘 모르겠구먼", "원하는 결말로 성공했어요"]:
            with patch.object(self.model,"generate",return_value=bad):
                self.t("elder","appearance")
            self.assertIn("바랜",self.data["reply"]);self.assertIn("구멍",self.data["reply"])
            self.assertNotIn(bad,self.data["reply"])
            self.assertIn("elder_testimony",self.items())

    def test_f04_injected_positive_is_overridden_by_explicit_negative(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        for text in ["구멍은 없고 종이는 바래지 않았어요.","이 표는 파란 종이이고 구멍이 없어요."]:
            self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]),message=text)
            self.assertNotIn("ticket_old",self.items())

    def test_f05_suggestions_are_state_bounded(self):
        self.three();self.t("elder","lost_ticket")
        self.assertTrue(self.data["game"]["suggestions"])
        self.assertNotIn("아지산",str(self.data["game"]["suggestions"]))
        self.a("end_talk");self.assertEqual(self.data["game"]["suggestions"],[])

    def test_f06_repeat_greetings_do_not_lock_cleaner(self):
        self.three()
        for _ in range(4):self.t("cleaner","greeting")
        self.assertIn("비켜",self.data["reply"])
        self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]))
        self.assertIn("ticket_old",self.items())

    def test_f06_attendant_year_does_not_grant_access(self):
        self.four();self.call(value=intent(target="attendant",topic="year"),message="지금은 2026년입니다.")
        self.assertIn("2026",self.data["reply"]);self.assertIn("믿기",self.data["reply"])
        self.assertFalse(self.flags().get("engine_permission"))

    def test_f07_repeat_return_is_record(self):
        self.three();self.ticket()
        self.a("present","ticket_old",recipient="elder")
        self.assertIn("아까",self.data["reply"]);self.assertIn("조사 기록",self.data["reply"])

    def test_f08_unread_return_has_explicit_gate(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]))
        self.a("present","ticket_old",recipient="elder")
        self.assertIn("반드시",self.data["reply"]);self.assertFalse(self.flags().get("ticket_returned"))
        self.a("read_item","ticket_old");self.a("present","ticket_old",recipient="elder")
        self.assertTrue(self.flags()["ticket_returned"])

    def test_f09_appearance_synonyms_record_same_fact(self):
        self.three()
        g=DemoGenerator()
        for text in ["잃어버린 승차권은 어떻게 생겼나요?", "잃어버린 표의 모양과 특징을 알려주세요."]:
            i=g._ground(intent("talk","elder",topic="lost_ticket"),text,{})
            self.assertEqual(i["topic"],"appearance")
            self.call(value=i,message=text)
            self.assertTrue(self.flags().get("elder_features"));self.assertIn("elder_testimony",self.items())

    def test_f09_lost_fact_does_not_disclose_appearance(self):
        self.three();self.t("elder","lost_ticket")
        self.assertNotIn("바랜",self.data["reply"]);self.assertNotIn("구멍",self.data["reply"])
        self.assertFalse(self.flags().get("elder_features"))

    def test_f10_unmentioned_denial_does_not_erase_feature(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded"],denied=["hole"]),message="그 표는 누렇게 바랜 종이로 되어 있어요.")
        self.call(value=intent("describe","cleaner","appearance",features=["hole"],denied=["faded"]),message="같은 표에 구멍도 뚫려 있습니다.")
        self.assertNotIn("ticket_old",self.items())
        self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]),message="그 승차권은 누렇게 바랜 종이에 구멍이 뚫려 있어요.")
        self.assertIn("ticket_old",self.items())

    def test_f10_context_keeps_old_ticket_when_model_chooses_current(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded"],described_item="ticket_current",relation="different"),message="그 표는 누렇게 바랜 종이로 되어 있어요.")
        self.call(value=intent("describe","cleaner","appearance",features=["hole"],described_item="ticket_current",relation="different"),message="그 표에는 구멍이 있어요.")
        self.assertNotIn("ticket_old",self.items())
        self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]),message="그 승차권은 누렇게 바랜 종이에 구멍이 뚫려 있어요.")
        self.assertIn("ticket_old",self.items())

    def test_f10_reversed_split_and_correction(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["hole"]),message="같은 표에 구멍이 있습니다.")
        self.call(value=intent("describe","cleaner","appearance",denied=["hole"]),message="구멍은 없습니다.")
        gid=self.client.get_cookie(web.COOKIE).value
        self.assertNotIn("hole",self.service.store.get(gid)["features"])
        self.call(value=intent("describe","cleaner","appearance",features=["hole"]),message="구멍이 없다고 했지만 취소할게요. 실제로 구멍이 뚫려 있어요.")
        self.call(value=intent("describe","cleaner","appearance",features=["faded"]),message="같은 표는 누렇게 바랜 종이입니다.")
        self.assertNotIn("ticket_old",self.items())
        self.call(value=intent("describe","cleaner","appearance",features=["faded","hole"]),message="그 승차권은 누렇게 바랜 종이에 구멍이 뚫려 있어요.")
        self.assertIn("ticket_old",self.items())

    def test_f11_yes_other_action_is_not_acceptance(self):
        self.four();self.t("attendant","loop");self.t("attendant","permission")
        text="네, 하지만 지금은 제 승차권을 먼저 읽겠습니다."
        i=DemoGenerator()._ground(intent("inspect","ticket_current"),text,{"pending_dialogue":"crew_help"})
        self.call(value=i,message=text)
        self.assertFalse(self.flags().get("mission_accepted"));self.assertTrue(self.flags().get("current_ticket_read"))

    def test_f12_unique_backgrounds_and_flashlight_state(self):
        gid=self.client.get_cookie(web.COOKIE).value;s=self.service.store.get(gid)
        scenes=[]
        for loc in ("car_1","car_2","car_3","car_4","crew","engine","platform"):
            s["location"]=loc;scenes.append(self.service.image_selector.scene(s,self.service.config)["background"])
        self.assertEqual(len(set(scenes)),7)
        self.three();self.assertEqual(self.data["scene"]["light_mode"],"flashlight")
        self.assertFalse(self.data["game"]["clock_running"])

    def test_f13_proven_year_retained(self):
        self.engine();self.prove();self.t("driver","password")
        self.assertIn("현재가 2026",self.data["reply"]);self.assertEqual(self.data["game"]["attempts"],1)
        person=next(x for x in self.data["scene"]["people"] if x["id"]=="driver")
        self.assertEqual(person["expression"],"surprised")

    def test_click_starts_dialogue_and_end_returns_to_scene(self):
        self.a("inspect","notice");self.a("move","car_2")
        self.assertFalse(self.data["game"]["conversation"]["active"])
        self.a("select_npc","explorer")
        self.assertEqual(self.data["game"]["history"][-1]["speaker"],"탐험가")
        self.assertNotIn("newspaper",self.items())
        self.a("end_talk")
        self.assertFalse(self.data["game"]["npc"])
        self.assertTrue(self.data["scene"]["people"])
        self.assertFalse(any(p["target"] == "window" for p in self.data["scene"]["hotspots"]))

    def test_physical_reaction_does_not_change_progress(self):
        self.engine();before=dict(self.flags());attempts=self.data["game"]["attempts"]
        self.call(value=dict(intent("threat","driver"),behavior="push"),message="기관사를 밀친다.")
        self.assertIn("물러",self.data["reply"]);self.assertEqual(self.flags(),before)
        self.assertEqual(self.data["game"]["attempts"],attempts);self.assertEqual(self.data["game"]["status"],"playing")

    def test_impossible_has_no_dialogue_or_progress(self):
        before=self.data["game"]
        self.call(value=intent("impossible"),message="가지고 있지 않은 총으로 총을 쏜다.")
        after=self.data["game"]
        self.assertEqual(self.data["reply"],"");self.assertTrue(self.data["ui"]["ignored"])
        for key in ("history","inventory","journal","location","status","attempts"):
            self.assertEqual(before[key],after[key])

    def test_acquisition_events_all_distinct(self):
        self.a("inspect","notice");self.a("move","car_2");self.a("select_npc","explorer")
        self.assertEqual(self.data["events"], [])
        self.pick("여기에 왜 있어요?")
        self.pick("열차에 탔는데 내리지를 못했어요.")
        self.assertEqual([e["item"]["id"] for e in self.data["events"]],["newspaper"])
        self.t("explorer","departure")
        self.assertEqual([e["item"]["id"] for e in self.data["events"]],["flashlight","facility_manual"])
        self.assertEqual(len({e["event_id"] for e in self.data["events"]}),2)

    def choice(self):
        choices = self.data["game"]["choices"]
        self.assertIn(len(choices), (1, 2))
        self.assertTrue(all(c["kind"] == "interaction" for c in choices))
        for option in choices:
            self.assertTrue(option["label"].endswith((".", "?")))
            self.assertEqual(option["action"], {"type": "choose", "target": option["id"]})
        return choices[0]

    def pick(self, label):
        option = next(c for c in self.data["game"]["choices"] if c["label"] == label)
        return self.call(action=option["action"])

    def hint_choice(self):
        self.a("hint")
        option = self.data["ui"]["hint_choice"]
        self.assertEqual(option["kind"], "hint")
        self.assertTrue(option["id"].startswith("hint."))
        self.assertEqual(option["action"], {"type": "choose", "target": option["id"]})
        self.assertNotRegex(option["label"], r"2026|2016|아지산|누렇게|구멍")
        self.choice()
        return option

    def test_normal_choices_do_not_follow_or_advance_the_solution(self):
        first = deepcopy(self.data["game"]["choices"])
        for choice in first:
            self.call(action=choice["action"])
            self.assertFalse(self.flags().get("notice_read"))
            if choice["id"].endswith(".window"):
                self.assertTrue(self.data["ui"]["window_video"])
            else:
                self.assertTrue(self.data["ui"]["non_progress"])
            self.assertNotIn("hint_choice", self.data["ui"])
        self.a("inspect", "notice")
        self.assertEqual(self.data["game"]["choices"], first)
        self.assertNotIn("notice", str(first))
        self.assertNotIn("next_car", str(first))

    def test_hint_is_required_and_exposes_one_immediate_action(self):
        rejected = self.client.post("/api/chat", json={
            "request_id": "unrequested_hint",
            "revision": self.data["game"]["revision"],
            "action": {"type": "choose", "target": "hint.car_1.notice"},
        })
        self.assertEqual(rejected.status_code, 409)
        option = self.hint_choice()
        self.assertEqual(option["id"], "hint.car_1.notice")
        self.assertFalse(self.flags().get("notice_read"))
        self.call(action=option["action"])
        self.assertTrue(self.flags()["notice_read"])
        self.assertNotIn("hint_choice", self.data["ui"])
        duplicate = self.client.post("/api/chat", json={
            "request_id": "consumed_hint",
            "revision": self.data["game"]["revision"], "action": option["action"],
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_requested_hints_reach_description_without_filling_it(self):
        for expected in (
            "hint.car_1.notice", "hint.car_1.next_step", "hint.car_2.meet_passenger",
            "hint.car_2.offer_inquiry", "hint.car_2.next_step",
        ):
            option = self.hint_choice()
            self.assertEqual(option["id"], expected)
            self.call(action=option["action"])
        self.assertTrue(self.data["scene"]["dark"])
        self.assertNotRegex(str(self.data["game"]["choices"]), "노인|청소원|elder|cleaner")
        for expected in ("hint.car_3.flashlight", "hint.car_3.meet_elder",
                         "hint.car_3.lost_property", "hint.car_3.meet_cleaner"):
            option = self.hint_choice()
            self.assertEqual(option["id"], expected)
            self.call(action=option["action"])
        option = self.hint_choice()
        self.assertEqual(option["id"], "hint.car_3.describe_property")
        before = deepcopy(self.flags())
        self.call(action=option["action"])
        self.assertTrue(self.data["ui"]["compose"])
        self.assertEqual(self.flags(), before)
        self.assertNotIn("ticket_old", self.items())
        self.assertNotRegex(self.data["reply"], "바랜|구멍")

    def test_ambient_interactions_preserve_progress(self):
        state = self.service.store.get(self.client.get_cookie(web.COOKIE).value)
        for location in ("car_1", "car_2", "car_3", "car_4", "crew", "engine"):
            sample = deepcopy(state)
            sample.update(location=location, npc="")
            if location == "car_1":
                self.service.engine.inspect(sample, "window")
            original = deepcopy(sample)
            choices = self.service.engine.choices(sample)
            self.assertEqual(len(choices), 2)
            for choice in choices:
                result = self.service.engine.choose(sample, choice["id"])
                self.assertEqual(sample, original)
                self.assertTrue(result["ui"].get("non_progress") or result["ui"].get("window_video"))

    def test_suggested_questions_are_offered_once_then_end_talk(self):
        state = self.service.store.get(self.client.get_cookie(web.COOKIE).value)
        sample = deepcopy(state)
        sample.update(location="engine", npc="driver")
        engine = self.service.engine
        asked = []
        with patch.object(engine, "_scenario_options", return_value=[]):
            while (choices := engine.choices(sample))[0]["id"] != "end_talk":
                self.assertFalse(any(c["id"] in asked for c in choices))
                asked.append(choices[0]["id"])
                engine.choose(sample, choices[0]["id"])
            self.assertEqual(len(asked), 4)
            self.assertEqual(choices, [{"id": "end_talk", "label": "대화를 마친다.", "kind": "interaction",
                                        "action": {"type": "end_talk"}}])
            sample["npc"] = ""
            self.assertNotEqual(engine.choices(sample)[0]["id"], "end_talk")

    def test_window_video_is_only_available_in_car_one(self):
        self.a("inspect", "window")
        self.assertTrue(self.data["ui"]["window_video"])
        self.assertTrue(self.flags()["loop_observed"])
        self.a("inspect", "notice")
        self.assertTrue(self.data["ui"]["notice"])
        state = self.service.store.get(self.client.get_cookie(web.COOKIE).value)
        for location in ("car_2", "car_3", "car_4", "crew", "engine", "platform"):
            with self.subTest(location=location):
                sample = deepcopy(state)
                sample.update(location=location, npc="")
                original = deepcopy(sample)
                result = self.service.engine.inspect(sample, "window")
                self.assertNotIn("window_video", result["ui"])
                self.assertEqual(sample, original)
                scene = self.service.image_selector.scene(sample, self.service.config)
                self.assertFalse(any(p.get("target") == "window" for p in scene["hotspots"]))
                self.assertFalse(any(c["id"].endswith(".window") for c in self.service.engine.choices(sample)))
                self.assertNotIn("window", self.service.engine.context(sample)["targets"])

    def test_authored_explorer_dialogue_and_acquisition_timing(self):
        self.a("inspect", "notice")
        self.a("move", "car_2")
        self.a("select_npc", "explorer")
        self.assertEqual([c["label"] for c in self.data["game"]["choices"]],
                         ["여기에 왜 있어요?", "여기가 어디예요?"])
        self.assertNotIn("newspaper", self.items())
        first = self.data["game"]["choices"][0]
        self.pick("여기에 왜 있어요?")
        self.assertEqual(self.data["reply"], "저는 궁금해서 직접 타봤는데요? 당신은 여기에 왜 있죠?")
        self.assertNotIn("newspaper", self.items())
        self.assertEqual([c["label"] for c in self.data["game"]["choices"]],
                         ["열차에 탔는데 내리지를 못했어요."])
        # A reply from a previous dialogue node cannot be replayed.
        stale = self.client.post("/api/chat", json={
            "request_id": "old_story_reply", "revision": self.data["game"]["revision"],
            "action": first["action"],
        })
        self.assertEqual(stale.status_code, 409)
        self.pick("열차에 탔는데 내리지를 못했어요.")
        for phrase in ("흥미롭잖아요", "2016년", "2026년", "23시 59분", "순전히 궁금해서", "이 신문을 보시겠어요"):
            self.assertIn(phrase, self.data["reply"])
        self.assertIn("newspaper", self.items())
        self.assertNotIn("flashlight", self.items())
        self.assertEqual(self.data["game"]["history"][-2]["text"],
                         "열차에 탔는데 내리지를 못했어요.")
        self.pick("신문을 본다.")
        self.assertEqual(self.data["ui"]["document"]["id"], "newspaper")
        self.assertIn("한 가지 이상한 점", self.data["reply"])
        self.pick("그게 뭔데요?")
        self.assertIn("13-Fri", self.data["reply"])
        self.pick("그러면 이 열차가 10년 전의 열차라고 생각하시는 거예요?")
        self.assertIn("결정적인 증거", self.data["reply"])
        self.pick("어떤 증거가 필요해요?")
        self.pick("또 알고 있는 게 있나요?")
        self.assertIn("같은 곳으로 돌아오는", self.data["reply"])
        self.assertNotIn("flashlight", self.items())
        self.pick("다른 칸으로 넘어가려고요.")
        self.assertTrue(self.flags()["supplies_received"])
        self.assertTrue({"flashlight", "facility_manual"} <= self.items())
        self.assertNotIn("hint_choice", self.data["ui"])

    def test_authored_elder_and_cleaner_preserve_manual_description(self):
        self.three()
        self.a("select_npc", "elder")
        self.assertEqual([c["label"] for c in self.data["game"]["choices"]],
                         ["괜찮으세요?", "여기서 뭘 하고 계세요?"])
        for label in ("괜찮으세요?", "뭘 찾고 계신데요?", "마지막으로 본 게 언제예요?",
                      "그때 주변에 누가 있었나요?"):
            self.pick(label)
            self.assertFalse(self.flags().get("elder_features"))
        self.pick("승차권은 어떻게 생겼나요?")
        self.assertIn("바랜", self.data["reply"])
        self.assertIn("구멍", self.data["reply"])
        self.assertTrue(self.flags()["elder_features"])
        self.pick("청소 직원이랑 대화한다.")
        self.pick("혹시 승차권을 보셨나요?")
        self.pick("분실물의 모양을 직접 설명한다.")
        self.assertTrue(self.data["ui"]["compose"])
        self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("describe", "cleaner", "appearance", features=["faded"]))
        before = deepcopy(self.flags())
        self.pick("분실물의 모양을 직접 설명한다.")
        self.assertEqual(self.flags(), before)
        self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("describe", "cleaner", "appearance", features=["hole"]))
        self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("describe", "cleaner", "appearance", features=["faded", "hole"]))
        self.assertIn("ticket_old", self.items())
        self.pick("승차권을 본다.")
        self.assertEqual(self.data["ui"]["document"]["id"], "ticket_old")
        self.pick("노인이랑 다시 대화한다.")
        self.pick("찾은 승차권을 돌려드린다.")
        self.assertTrue(self.flags()["ticket_returned"])
        self.pick("하차역 이름이 기억나세요?")
        self.assertTrue(self.flags()["destination_hint"])
        self.assertIn("삶과 죽음의 경계", self.data["reply"])
        self.assertNotIn("아지산", self.data["reply"])

    def test_authored_attendant_and_driver_keep_puzzles_player_operated(self):
        self.four()
        self.a("select_npc", "attendant")
        for label in ("왜 위험하죠?", "기관실은 어디 있나요?", "이 차를 멈춰야 합니다.",
                      "네.", "그래서 기관실에 가봐야겠어요."):
            self.pick(label)
        self.pick("지금 규정이 중요한 상황인가요?")
        self.pick("무슨 부탁이죠?")
        self.assertTrue(self.flags()["mission_offered"])
        self.assertFalse(self.flags().get("mission_accepted"))
        self.pick("좋아요.")
        self.assertTrue(self.flags()["mission_accepted"])
        self.assertFalse(self.flags().get("door_open"))
        self.assertNotIn("inventory", self.data["ui"])
        for kind, target in (("read_item", "facility_manual"), ("operate", "cover"),
                             ("operate", "lever_down"), ("operate", "handle"),
                             ("move", "crew"), ("read_report", ""), ("ack_document", "route_report"), ("move", "car_4")):
            self.a(kind, target)
        self.a("select_npc", "attendant")
        self.pick("운행 관련 서류를 가져왔어요.")
        self.assertTrue(self.flags()["engine_permission"])
        self.a("move", "engine")
        self.a("select_npc", "driver")
        self.pick("당장 멈추세요.")
        self.pick("아지산으로 가야 합니다.")
        self.pick("비밀번호가 뭐죠?")
        self.assertTrue(self.flags()["driver_explained"])
        self.assertIn("2016", self.data["reply"])
        self.pick("보관함에서 자료를 살펴본다.")
        self.assertTrue(self.data["ui"]["inventory"])
        self.assertFalse(self.flags().get("year_proven"))
        self.assertIsNone(self.data["game"]["confirmation"])
        self.prove()
        self.pick("마지막 한 번을 직접 입력해 보겠습니다.")
        self.assertTrue(self.data["ui"]["control"])
        self.assertEqual(self.data["game"]["attempts"], 1)
        self.assertIsNone(self.data["game"]["confirmation"])
        self.submit()
        self.a("disembark")
        self.assertEqual(self.data["game"]["status"], "good")

    def test_hints_route_back_to_unfinished_task_and_show_one_door_step(self):
        self.three()
        self.a("move", "car_1")
        option = self.hint_choice()
        self.assertEqual(option["id"], "hint.car_1.next_step")
        self.assertIn("2호차", option["label"])
        self.call(action=option["action"])
        self.assertEqual(self.data["game"]["location"]["id"], "car_2")
        option = self.hint_choice()
        self.assertIn("3호차", option["label"])
        self.call(action=option["action"])
        self.ticket()
        self.a("move", "car_4")
        self.t("attendant", "loop")
        self.t("attendant", "permission")
        self.call(value=intent("accept", "attendant"))
        for expected in ("read_manual", "open_cover", "release_lever"):
            option = self.hint_choice()
            self.assertEqual(option["id"], "hint.car_4." + expected)
            self.call(action=option["action"])
        self.assertTrue(self.flags()["lever_down"])
        self.assertEqual(self.hint_choice()["id"], "hint.car_4.next_step")

    def test_hint_preserves_final_evidence_and_input_decisions(self):
        self.engine()
        self.assertFalse(any(c["kind"] == "hint" for c in self.data["game"]["choices"]))
        option = self.hint_choice()
        self.assertEqual(option["id"], "hint.engine.review_records")
        self.call(action=option["action"])
        self.assertTrue(self.data["ui"]["inventory"])
        self.assertIsNone(self.data["game"]["confirmation"])
        self.assertFalse(self.flags().get("year_proven"))
        self.prove()
        option = self.hint_choice()
        self.assertEqual(option["id"], "hint.engine.control_device")
        self.call(action=option["action"])
        self.assertTrue(self.data["ui"]["control"])
        self.assertEqual(self.data["game"]["attempts"], 1)
        self.assertNotRegex(self.data["reply"], "아지산|2026")
        self.a("prepare_control", destination="아지산역", password="2026")
        self.assertEqual(self.data["game"]["choices"], [])
        self.a("hint")
        self.assertNotIn("hint_choice", self.data["ui"])
        self.a("cancel")
        self.submit()
        option = self.hint_choice()
        self.call(action=option["action"])
        self.assertEqual(self.data["game"]["status"], "good")
        self.assertEqual(self.data["game"]["choices"], [])

    def test_hint_grant_expires_after_another_interaction(self):
        option = self.hint_choice()
        self.call(action=self.choice()["action"])
        rejected = self.client.post("/api/chat", json={
            "request_id": "expired_hint",
            "revision": self.data["game"]["revision"], "action": option["action"],
        })
        self.assertEqual(rejected.status_code, 409)
        option = self.hint_choice()
        self.a("inspect", "window")
        rejected = self.client.post("/api/chat", json={
            "request_id": "expired_after_inspect",
            "revision": self.data["game"]["revision"], "action": option["action"],
        })
        self.assertEqual(rejected.status_code, 409)
        for target in ("car_1.notice", "engine.control_device", "hint.engine.control_device"):
            rejected = self.client.post("/api/chat", json={
                "request_id": "forged_" + target.replace(".", "_"),
                "revision": self.data["game"]["revision"],
                "action": {"type": "choose", "target": target},
            })
            self.assertEqual(rejected.status_code, 409)
        self.a("abandon")
        self.assertEqual(self.data["game"]["choices"], [])
        self.a("confirm", token=self.data["game"]["confirmation"]["token"])
        self.assertEqual(self.data["game"]["choices"], [])


class DocumentRouteTest(GameTestCase):
    """Source-document gates and dialogue transitions, without duplicating smoke cases."""

    def test_doc_first_greeting_does_not_hand_over_items(self):
        self.a("inspect", "notice"); self.a("move", "car_2")
        self.t("explorer", "greeting")
        self.assertIn("당신은 여기에 왜", self.data["reply"])
        self.assertNotIn("newspaper", self.items())
        self.t("explorer", "tools")
        self.assertNotIn("flashlight", self.items())
        self.t("explorer", "case")
        self.assertIn("newspaper", self.items())
        self.assertNotIn("flashlight", self.items())
        self.t("explorer", "departure")
        self.assertTrue({"flashlight", "facility_manual"} <= self.items())
        self.t("explorer", "departure")
        self.assertEqual(self.data["events"], [])

    def test_doc_anomaly_does_not_immediately_offer_mission(self):
        self.four()
        self.assertFalse(any(p.get("target") == "door" for p in self.data["scene"]["hotspots"]))
        self.t("attendant", "loop")
        self.assertTrue(self.flags()["anomaly_discussed"])
        self.assertFalse(self.flags().get("mission_offered"))
        self.call(value=intent("accept", "attendant"))
        self.assertFalse(self.flags().get("mission_accepted"))
        self.t("attendant", "permission")
        self.assertTrue(self.flags()["mission_offered"])
        self.call(value=intent("accept", "attendant"))
        self.assertTrue(self.flags()["mission_accepted"])

    def test_doc_newspaper_is_not_a_mandatory_gate_for_tools(self):
        self.a("inspect", "notice"); self.a("move", "car_2"); self.a("select_npc", "explorer")
        self.assertNotIn("newspaper", self.items())
        self.call(value=intent("move", "car_3"), message="앞쪽 객차로 가서 직접 조사하겠습니다.")
        self.assertTrue({"flashlight", "facility_manual"} <= self.items())
        self.assertNotIn("newspaper", self.items())
        self.assertEqual(self.data["game"]["location"]["id"], "car_2")
        self.a("move", "car_3")
        self.assertEqual(self.data["game"]["location"]["id"], "car_3")

    def test_doc_hardware_moves_only_from_ui_actions(self):
        self.four()
        self.t("attendant", "loop"); self.t("attendant", "permission")
        self.call(value=intent("accept", "attendant"))
        self.a("read_item", "facility_manual")
        self.call(value=intent("operate", "cover"), message="점검 덮개를 연다.")
        self.assertFalse(self.flags().get("cover_open"))
        self.a("operate", "cover")
        self.call(value=intent("operate", "lever_down"), message="레버를 내린다.")
        self.assertFalse(self.flags().get("lever_down"))
        self.a("operate", "lever_down"); self.a("operate", "handle")
        self.assertTrue(self.flags()["door_open"])

    def test_doc_report_discovery_and_read_completion_are_separate(self):
        self.four(); self.office(); self.a("move", "crew")
        self.a("inspect", "desk")
        self.assertIn("route_report", self.items())
        self.assertTrue(self.flags()["report_found"])
        self.assertFalse(self.flags().get("report_read"))
        self.assertEqual(self.data["ui"]["document"]["id"], "route_report")
        self.a("move", "car_4")
        self.a("present", "route_report", recipient="attendant")
        self.assertFalse(self.flags().get("engine_permission"))
        self.a("read_item", "route_report")
        self.assertFalse(self.flags().get("report_read"))
        self.a("ack_document", "route_report")
        self.assertTrue(self.flags()["report_read"])
        self.a("present", "route_report", recipient="attendant")
        self.a("move", "engine")
        self.assertEqual(self.data["game"]["location"]["id"], "engine")

    def test_doc_read_ack_cannot_be_forged_or_replayed(self):
        state = self.service.store.get(self.client.get_cookie(web.COOKIE).value)
        with self.assertRaises(web.GameError):
            self.service.engine.acknowledge_document(state, "route_report")
        self.four(); self.office(); self.a("move", "crew"); self.a("read_report")
        self.a("read_item", "ticket_current")
        state = self.service.store.get(self.client.get_cookie(web.COOKIE).value)
        with self.assertRaises(web.GameError):
            self.service.engine.acknowledge_document(state, "route_report")
        self.assertFalse(state["flags"].get("report_read"))

    def test_doc_unlocked_lever_allows_room_entry_without_extra_gate(self):
        self.four()
        self.t("attendant", "loop"); self.t("attendant", "permission")
        self.call(value=intent("accept", "attendant"))
        self.a("read_item", "facility_manual")
        self.a("operate", "cover"); self.a("operate", "lever_down")
        self.assertFalse(self.flags().get("door_open"))
        self.a("move", "crew")
        self.assertEqual(self.data["game"]["location"]["id"], "crew")
        self.assertTrue(self.flags()["door_open"])

    def test_doc_current_natural_language_answer_uses_authored_node(self):
        self.a("inspect", "notice"); self.a("move", "car_2"); self.a("select_npc", "explorer")
        first = self.data["game"]["choices"][0]["id"].removeprefix("car_2.")
        value = dict(intent("talk", "explorer", "identity"), dialogue_choice_id=first)
        self.call(value=value, message="여기에는 왜 계신 거예요?")
        self.assertEqual(self.data["reply"], "저는 궁금해서 직접 타봤는데요? 당신은 여기에 왜 있죠?")
        self.assertNotIn("newspaper", self.items())
        next_id = self.data["game"]["choices"][0]["id"].removeprefix("car_2.")
        value = dict(intent("talk", "explorer", "case"), dialogue_choice_id=next_id)
        with patch.object(self.model, "generate", wraps=self.model.generate) as generated:
            self.call(value=value, message="내리려고 했는데 열차에서 내릴 수가 없었어요.")
            generated.assert_not_called()
        self.assertIn("newspaper", self.items())
        self.assertIn("이 신문을 보시겠어요", self.data["reply"])
        self.assertEqual(self.data["game"]["choices"][0]["label"], "신문을 본다.")

    def test_doc_future_dialogue_node_cannot_skip_the_scene(self):
        self.a("inspect", "notice"); self.a("move", "car_2"); self.a("select_npc", "explorer")
        before = deepcopy(self.flags())
        self.model.value = dict(intent("talk", "explorer", "departure"),
                                dialogue_choice_id="story.explorer.plans.investigate")
        response = self.client.post("/api/chat", json={
            "request_id": "future_story_answer", "revision": self.data["game"]["revision"],
            "message": "다음 칸으로 가려고요.",
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.flags(), before)
        self.assertNotIn("flashlight", self.items())

    def test_doc_newspaper_is_independent_2026_evidence(self):
        self.engine()
        doc = self.service.config["items"]["newspaper"]["document"]
        self.assertIn(["발행 연도", "2026"], doc["fields"])
        self.assertFalse(self.flags().get("current_ticket_read"))
        self.prove("newspaper")
        self.assertTrue(self.flags()["newspaper_read"])
        self.assertFalse(self.flags().get("current_ticket_read"))
        self.assertTrue(self.flags()["year_proven"])

    def test_doc_destination_requires_full_station_name(self):
        self.engine(); self.prove(); self.submit("아지산", "2026")
        self.assertEqual(self.data["game"]["status"], "bad")
        self.assertEqual(self.data["game"]["reason"], "wrong_control")
        self.assertEqual(self.data["game"]["attempts"], 0)

    def test_doc_arrival_waits_for_explicit_disembarkation(self):
        self.engine(); self.prove(); self.submit()
        self.assertTrue(self.flags()["station_arrived"])
        self.assertFalse(self.flags().get("disembarked"))
        self.a("look")
        self.assertEqual(self.data["game"]["status"], "playing")
        self.a("disembark")
        self.assertEqual(self.data["game"]["status"], "good")


class CleanerQuestionRegressionTest(GameTestCase):
    def ready_for_description(self):
        self.three()
        self.t("elder", "appearance")
        self.a("read_item", "elder_testimony")
        self.a("select_npc", "cleaner")
        self.a("choose", "car_3.story.cleaner.entry.ticket")
        self.a("choose", "car_3.story.cleaner.describe.describe")

    def test_finding_question_cannot_be_swallowed_by_compose_choice(self):
        for mode, choice in (("question", "story.cleaner.describe.describe"),
                             ("act", "story.cleaner.describe.describe"),
                             ("unclear", ""), ("question", "story.cleaner.entry.ticket")):
            with self.subTest(mode=mode, choice=choice):
                self.new()
                self.ready_for_description()
                message = "누렇게 바랜 종이에 구멍이 뚫려있는 승차권 보신적 있으신가요?"
                raw = intent("talk", "cleaner", "lost_ticket", mode=mode, described_item="unknown")
                raw.update(quote=message, dialogue_choice_id=choice)
                parser = DemoGenerator()
                with patch.object(parser, "_complete", return_value=json.dumps(raw)), \
                     patch.object(self.model, "interpret", side_effect=parser.interpret):
                    self.call(message=message)
                self.assertIn("ticket_old", self.items())
                self.assertTrue(self.flags()["ticket_recovered"])
                self.assertIn("여기 있습니다", self.data["reply"])
                self.assertNotIn("compose", self.data["ui"])
                self.assertEqual([e["item"]["id"] for e in self.data["events"]], ["ticket_old"])
                saved = self.client.get("/api/game").json
                self.assertIn("ticket_old", {i["id"] for i in saved["game"]["inventory"]})

    def test_known_description_can_be_asked_with_polite_variants(self):
        for message in ("누렇게 바랜 종이에 구멍이 있는 승차권을 보셨나요?",
                        "누런 종이에 검표 자국이 있는 어르신의 표를 주우셨나요?",
                        "노인의 표는 빛바랜 종이에 구멍이 뚫려 있습니다."):
            with self.subTest(message=message):
                self.new()
                self.ready_for_description()
                raw = intent("talk", "cleaner", "other", mode="question", described_item="unknown")
                raw["dialogue_choice_id"] = "story.cleaner.describe.describe"
                self.call(value=raw, message=message)
                self.assertIn("ticket_old", self.items())
                self.assertFalse(self.data["ui"].get("compose"))

    def test_feature_guessing_negation_hypothesis_and_wrong_owner_do_not_award(self):
        self.ready_for_description()
        for message, mode in (
            ("승차권은 누렇게 바랜 종이인가요? 구멍이 있나요?", "question"),
            ("누렇게 바랜 종이에 구멍이 없는 승차권 보셨나요?", "question"),
            ("제 승차권은 누렇게 바랜 종이에 구멍이 있는데 보셨나요?", "question"),
            ("만약 누렇게 바랜 종이에 구멍이 있는 승차권을 보셨다면?", "hypothesis"),
            ("누렇게 바랜 종이에 구멍이 있는 표를 보셨는지 묻지 않겠습니다.", "negated"),
        ):
            with self.subTest(message=message):
                self.call(value=intent("talk", "cleaner", "appearance", mode=mode,
                                       described_item="unknown"), message=message)
                self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("talk", "cleaner", mode="question"),
                  message="누렇게 바랜 종이에 구멍이 뚫려 있는 승차권 보셨나요?")
        self.assertIn("ticket_old", self.items())


class RegisteredSceneTest(GameTestCase):
    def test_cutouts_use_the_background_canvas_and_are_served(self):
        import struct
        from services.image_selector import REGISTRATIONS
        image_root = Path(__file__).resolve().parents[1] / "public"
        for key, art in REGISTRATIONS.items():
            with self.subTest(key=key):
                for field in ("image", "background"):
                    path = image_root / art[field].lstrip("/")
                    with path.open("rb") as file:
                        file.seek(16)
                        self.assertEqual(list(struct.unpack(">II", file.read(8))), art["size"])
                    response = self.client.get(art[field])
                    self.assertEqual(response.status_code, 200)
                    response.close()
                self.assertTrue(all(0 <= x <= 100 and 0 <= y <= 100 for x, y in art["polygon"]))

    def test_scene_ratio_and_interactions_match_supplied_backgrounds(self):
        gid = self.client.get_cookie(web.COOKIE).value
        state = self.service.store.get(gid)
        state["flags"].update(light_on=True, mission_accepted=True, door_open=True)
        expected = {"car_1": {"notice", "window"}, "car_4": {"crew_door", "inspection_cover", "door_handle"},
                    "crew": {"report", "desk"}, "engine": {"control", "engine_lever"}}
        for location in ("car_1", "car_2", "car_3", "car_4", "crew", "engine"):
            state["location"] = location
            scene = self.service.image_selector.scene(state, self.service.config)
            if location in expected:
                self.assertEqual({p["id"] for p in scene["hotspots"]}, expected[location])
            for point in scene["hotspots"] + scene["people"]:
                art = point.get("registration")
                if art:
                    self.assertEqual(art["background"], scene["background"])
                    self.assertEqual(scene["aspect_ratio"], " / ".join(map(str, art["size"])))
            if location in ("car_2", "car_3"):
                self.assertTrue(all("registration" in p for p in scene["people"]))


class InventoryPresentationTest(GameTestCase):
    def test_fonts_music_and_browser_range_requests_are_served_locally(self):
        for page in ("/", "/detail", "/chat"):
            self.assertIn("assets/js/audio.js", self.client.get(page).text)
        for asset in ("css/OG-Renaissance-Secret.ttf", "images/inventory/book-overview.png",
                      "images/inventory/book-detail.png", "images/inventory/photo-mount.png",
                      "images/inventory/record-paper.png", "images/inventory/actions/use-flashlight.png",
                      "images/inventory/actions/submit-evidence.png"):
            response=self.client.get("/assets/"+asset)
            self.assertEqual(response.status_code,200)
            response.close()
        response=self.client.get("/assets/audio/train-theme.mp3",headers={"Range":"bytes=0-31"})
        self.assertEqual(response.status_code,206)
        self.assertEqual(len(response.data),32)
        self.assertTrue(response.content_type.startswith("audio/"))
        self.assertTrue(response.headers["Content-Range"].startswith("bytes 0-31/"))
        response.close()

    def test_every_record_image_matches_current_server_authored_content(self):
        import struct
        root=Path(__file__).resolve().parents[1]
        printed=json.loads((root/"public/assets/images/inventory/print-source.json").read_text(encoding="utf-8"))
        source={row["artwork"]:row for row in printed["records"]}
        state={"inventory":list(self.service.config["items"]),"flags":{}}
        for flags in ({},{"elder_features":True},{"destination_hint":True},
                      {"elder_features":True,"destination_hint":True},{"ticket_returned":True}):
            state["flags"]=flags
            for item in state["inventory"]:
                document=self.service.engine.document(state,item)
                with self.subTest(item=item,flags=flags):
                    self.assertEqual(document,source[document["artwork"]])
                    with (root/"public"/document["artwork"].lstrip("/")).open("rb") as file:
                        self.assertEqual(file.read(8),b"\x89PNG\r\n\x1a\n")
                        file.seek(16)
                        self.assertEqual(struct.unpack(">II",file.read(8)),(900,1120))

    def test_testimony_artwork_reveals_only_the_learned_clues(self):
        state={"inventory":["elder_testimony"],"flags":{}}
        unknown=self.service.engine.document(state,"elder_testimony")
        self.assertEqual(unknown["paragraphs"],[])
        state["flags"]["elder_features"]=True
        appearance=self.service.engine.document(state,"elder_testimony")
        self.assertNotEqual(unknown["artwork"],appearance["artwork"])
        self.assertIn("구멍",appearance["paragraphs"][0])
        self.assertNotIn("삶과 죽음",str(appearance["paragraphs"]))
        state["flags"]["destination_hint"]=True
        complete=self.service.engine.document(state,"elder_testimony")
        self.assertNotEqual(appearance["artwork"],complete["artwork"])
        self.assertIn("삶과 죽음",str(complete["paragraphs"]))


class GeneratorValidationTest(unittest.TestCase):
    def test_plain_ticket_description_is_understood_as_cleaner_answer(self):
        text = "승차권은 누렇게 바랜 종이에 구멍이 뚫려있다"
        value = intent("talk", "cleaner", topic="other", described_item="unknown")
        value["quote"] = text
        parsed = DemoGenerator()._ground(value, text, {"active_npc": "cleaner", "pending_dialogue": "describe_ticket"})
        self.assertEqual((parsed["intent"], parsed["target"]), ("describe", "cleaner"))
        self.assertEqual(set(parsed["affirmed_features"]), {"faded", "hole"})

    def test_bad_structured_output_rejected(self):
        g = DemoGenerator()
        v = intent()
        v["quote"] = "실제로 없는 구절"
        with patch.object(g, "_complete", return_value=json.dumps(v)):
            self.assertEqual(g.interpret("표를 읽는다", {})["mode"], "unclear")
        v["quote"] = "표를 읽는다"
        v["extra"] = "grant_all"
        with patch.object(g, "_complete", return_value=json.dumps(v)):
            with self.assertRaises(AIUnavailable):
                g.interpret("표를 읽는다", {})

    def test_notice_and_manual_are_disambiguated(self):
        message = "안내문은 아까 안 읽었다. 지금은 직접 읽는다."
        value = intent("use", "facility_manual")
        value["quote"] = message
        with patch.object(DemoGenerator, "_complete", return_value=json.dumps(value)):
            parsed = DemoGenerator().interpret(message, {})
        self.assertEqual((parsed["intent"], parsed["target"]), ("inspect", "notice"))

    def test_model_act_does_not_override_explicit_read_negation(self):
        message = "안내문을 읽지 않겠습니다."
        value = intent("inspect", "notice")
        value["quote"] = message
        with patch.object(DemoGenerator, "_complete", return_value=json.dumps(value)):
            parsed = DemoGenerator().interpret(message, {})
        self.assertEqual(parsed["mode"], "negated")

    def test_office_help_acceptance_is_not_door_operation(self):
        message = "좋아요. 승무원실 문을 여는 일을 도와드리겠습니다."
        value = intent("operate", "door", topic="help", recipient="attendant")
        value["quote"] = message
        with patch.object(DemoGenerator, "_complete", return_value=json.dumps(value)):
            parsed = DemoGenerator().interpret(
                message, {"pending_dialogue": "crew_help"}
            )
        self.assertEqual((parsed["intent"], parsed["target"]), ("accept", "attendant"))

    def test_object_owner_is_not_dialogue_recipient(self):
        text="노인의 표는 누렇게 바랜 종이에 구멍이 뚫려 있습니다."
        value=intent("talk","elder",topic="appearance")
        result=DemoGenerator()._ground(value,text,{"active_npc":"cleaner","pending_dialogue":"describe_ticket"})
        self.assertEqual((result["intent"],result["target"]),("describe","cleaner"))
        self.assertEqual(set(result["affirmed_features"]),{"faded","hole"})

    def test_missing_key_sanitized(self):
        with (
            patch("services.generator.dotenv_values", return_value={}),
            patch.dict("os.environ", {"OPENAI_API_KEY": ""}),
        ):
            with self.assertRaises(AIUnavailable):
                DemoGenerator()._complete("x", {})


if __name__ == "__main__":
    unittest.main()
