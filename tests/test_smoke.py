"""화면·게임 경로·장애를 실제 API 과금 없이 검증한다. 실제 AI 품질은 별도 검수한다."""

import json
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


class SmokeTest(unittest.TestCase):
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
        self.t("explorer", "tools")
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

    def test_pages_and_referenced_assets(self):
        for route in ("/", "/detail", "/chat?username=헤슬", "/health"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        for asset in (
            "js/chatbot.js",
            "css/style.css",
            "css/NanumGothic.ttf",
            "images/hateslop-logo.png",
            "images/scene_01.png",
            "images/portrait_01.png",
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
        self.t("explorer", "tools")
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

    def test_features_accumulate(self):
        self.three()
        self.t("elder", "appearance")
        self.t("cleaner", "lost_ticket")
        self.call(value=intent("describe", "cleaner", "appearance", features=["faded"]))
        self.assertNotIn("ticket_old", self.items())
        self.call(value=intent("describe", "cleaner", "appearance", features=["hole"]))
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
        self.assertNotIn("아지산", json.dumps(self.data, ensure_ascii=False))
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

    def test_good_paths_evidence_alias_and_spaces(self):
        for evidence in ("ticket_current", "newspaper"):
            for dest in ("아지산", "아지산역"):
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
        self.t("explorer", "tools")
        self.t("explorer", "tools")
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
        self.assertIn("탐험가", r.json["reply"])
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
        self.four();self.t("attendant","year")
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
        self.assertIn("ticket_old",self.items())

    def test_f10_context_keeps_old_ticket_when_model_chooses_current(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["faded"],described_item="ticket_current",relation="different"),message="그 표는 누렇게 바랜 종이로 되어 있어요.")
        self.call(value=intent("describe","cleaner","appearance",features=["hole"],described_item="ticket_current",relation="different"),message="그 표에는 구멍이 있어요.")
        self.assertIn("ticket_old",self.items())

    def test_f10_reversed_split_and_correction(self):
        self.three();self.t("elder","appearance");self.t("cleaner","lost_ticket")
        self.call(value=intent("describe","cleaner","appearance",features=["hole"]),message="같은 표에 구멍이 있습니다.")
        self.call(value=intent("describe","cleaner","appearance",denied=["hole"]),message="구멍은 없습니다.")
        gid=self.client.get_cookie(web.COOKIE).value
        self.assertNotIn("hole",self.service.store.get(gid)["features"])
        self.call(value=intent("describe","cleaner","appearance",features=["hole"]),message="구멍이 없다고 했지만 취소할게요. 실제로 구멍이 뚫려 있어요.")
        self.call(value=intent("describe","cleaner","appearance",features=["faded"]),message="같은 표는 누렇게 바랜 종이입니다.")
        self.assertIn("ticket_old",self.items())

    def test_f11_yes_other_action_is_not_acceptance(self):
        self.four();self.t("attendant","loop")
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
        self.assertIn("newspaper",self.items())
        self.a("end_talk")
        self.assertFalse(self.data["game"]["npc"]);self.assertTrue(self.data["scene"]["hotspots"])

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
        self.assertEqual([e["item"]["id"] for e in self.data["events"]],["newspaper"])
        self.t("explorer","tools")
        self.assertEqual([e["item"]["id"] for e in self.data["events"]],["flashlight","facility_manual"])
        self.assertEqual(len({e["event_id"] for e in self.data["events"]}),2)


class GeneratorValidationTest(unittest.TestCase):
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
