"""Isolated Flask fixture; paid model calls require the explicit --live-api mode."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import zipfile

from flask import Response, redirect, request
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as web
from services.chatbot_service import ChatbotService
from services.generator import AIUnavailable, DemoGenerator


class OfflineModel:
    def interpret(self, message, context):
        if message != "입력창 확인":
            raise AssertionError("The browser regression must not call a live model")
        return dict(intent="talk", target=context["active_npc"], topic="off_topic",
                    mode="act", quote=message)

    def generate(self, question, username, character, knowledge):
        return character["_runtime"]["canonical"]


LIVE_API = os.environ.get("DIALOGUE_QA_LIVE_API") == "1"
model_calls = []


class LiveModel(DemoGenerator):
    def _complete(self, instructions, payload, schema=None):
        if len(model_calls) >= 16:
            raise AIUnavailable("실제 화면 검수의 API 호출 상한에 도달했습니다.")
        record = {"kind": "interpret" if schema and "intent" in schema.get("properties", {}) else "reply",
                  "status": "pending"}
        model_calls.append(record)
        started = time.perf_counter()
        try:
            value = super()._complete(instructions, payload, schema)
            record["status"] = "completed"
            return value
        except AIUnavailable:
            record["status"] = "unavailable"
            raise
        finally:
            record["seconds"] = round(time.perf_counter() - started, 3)


temporary = tempfile.TemporaryDirectory(prefix="dialogue-ui-")
web.chatbot = ChatbotService(generator=LiveModel() if LIVE_API else OfflineModel(),
                             db_path=Path(temporary.name) / "qa.sqlite3")


@web.app.get("/qa/model-stats")
def model_stats():
    return {"live_api": LIVE_API, "calls": model_calls}


@web.app.before_request
def baseline_assets():
    archive = os.environ.get("DIALOGUE_UI_BASELINE_ZIP")
    assets = {"/assets/js/chatbot.js": "text/javascript",
              "/assets/css/style.css": "text/css"}
    if archive and request.path in assets:
        with zipfile.ZipFile(archive) as baseline:
            content = baseline.read("13Fri/public" + request.path)
        response = Response(content, mimetype=assets[request.path])
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Dialogue-QA-Baseline"] = "distribution-zip"
        return response


@web.app.get("/qa/dialogue")
def seed_dialogue():
    npc = request.args.get("npc", "driver")
    locations = {"driver": "engine", "attendant": "car_4", "explorer": "car_2",
                 "cleaner": "car_3", "elder": "car_3", "crew": "crew"}
    if npc not in locations:
        return {"error": "Unknown dialogue fixture"}, 400
    game_id, state = web.chatbot.store.create("대화 화면 회귀 검사")
    state["location"] = locations[npc]
    state["visited"] = ["car_1", "car_2", "car_3", "car_4", "crew", "engine"]
    state["flags"].update(notice_read=True, light_on=True)
    if npc != "explorer":
        state["inventory"] += ["newspaper", "flashlight", "facility_manual"]
        state["flags"].update(explorer_met=True, supplies_received=True)
    if npc in ("driver", "crew"):
        state["inventory"] += ["elder_testimony", "ticket_old", "route_report"]
        state["flags"].update(elder_features=True, mission_accepted=True,
                              door_open=True, report_found=True, report_read=True,
                              ticket_recovered=True, old_ticket_read=True,
                              ticket_returned=True, engine_permission=True)
        state["read"].append("route_report")
    if npc == "cleaner":
        state["flags"]["elder_features"] = True
        state["inventory"].append("elder_testimony")
    with web.chatbot.store.connect() as database:
        database.execute("UPDATE games SET state=? WHERE id=?",
                         (json.dumps(state, ensure_ascii=False), game_id))
    if request.args.get("active") == "1" and npc != "crew":
        web.chatbot.process(game_id, "fixture-entry", expected=0,
                            action={"type": "select_npc", "target": npc})
    response = redirect("/chat")
    response.set_cookie(web.COOKIE, game_id, httponly=True, samesite="Lax")
    return response


if __name__ == "__main__":
    server = make_server("127.0.0.1", 0, web.app, threaded=True)
    print("QA_PORT=" + str(server.server_port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        temporary.cleanup()
