"""기존 Flask 진입점: 화면, 채팅, 게임 저장 상태와 소지품 열람."""

import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, url_for
from services import ChatbotService
from services.chatbot_service import GameError
from services.generator import AIUnavailable

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config/chatbot_config.json"
load_dotenv(BASE_DIR / ".env")
IS_VERCEL = os.getenv("VERCEL") == "1"
app = Flask(
    __name__,
    static_folder=None if IS_VERCEL else "public",
    static_url_path=None if IS_VERCEL else "",
)
app.config["MAX_CONTENT_LENGTH"] = 16384
chatbot = ChatbotService()
COOKIE = "train_game"


def asset_url(filename: str) -> str:
    return (
        "/" + filename.lstrip("/")
        if IS_VERCEL
        else url_for("static", filename=filename)
    )


app.jinja_env.globals["asset_url"] = asset_url


def load_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not isinstance(config.get("name"), str):
        raise ValueError("config/chatbot_config.json의 name을 확인하세요.")
    return config


def bot_view(config: dict) -> dict:
    return {
        "name": config["name"],
        "description": config.get("description", ""),
        "tags": config.get("tags", []),
        "greeting": config.get("greeting", ""),
        "image": asset_url(
            config.get("thumbnail") or "assets/images/hateslop-logo.png"
        ),
    }


def error_response(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@app.before_request
def same_origin():
    if (
        request.path.startswith("/api/")
        and request.method == "POST"
        and request.headers.get("Origin")
    ):
        try:
            origin = urlsplit(request.headers["Origin"])
            if origin.scheme not in ("http", "https") or origin.netloc != request.host:
                return error_response(
                    "invalid_origin", "같은 게임 화면에서 요청해 주세요.", 403
                )
        except ValueError:
            return error_response(
                "invalid_origin", "요청 출처가 올바르지 않습니다.", 403
            )


@app.after_request
def response_headers(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.errorhandler(GameError)
def game_error(error):
    return error_response(error.code, str(error), error.status)


@app.errorhandler(AIUnavailable)
def ai_error(error):
    return error_response("ai_unavailable", str(error), 503)


@app.errorhandler(413)
def too_large(error):
    return error_response(
        "request_too_large",
        "입력 크기가 너무 큽니다. 메시지는 2000자 이하로 보내주세요.",
        413,
    )


def game_id():
    gid = request.cookies.get(COOKIE, "")
    if re.fullmatch(r"[A-Za-z0-9_-]{40,80}", gid) is None:
        raise GameError("시작 화면에서 게임을 시작해 주세요.", "game_missing", 404)
    return gid


@app.get("/")
def index():
    return render_template("index.html", bot=bot_view(load_config()))


@app.get("/detail")
def detail():
    return render_template("detail.html", bot=bot_view(load_config()))


@app.get("/chat")
def chat():
    username = (request.args.get("username") or "사용자").strip()[:50] or "사용자"
    return render_template("chat.html", bot=bot_view(load_config()), username=username)


@app.get("/api/game")
def game_state():
    return jsonify(chatbot.snapshot(game_id()))


@app.post("/api/game/new")
def new_game():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("invalid_json", "JSON 객체를 보내주세요.", 400)
    username = payload.get("username", "사용자")
    if not isinstance(username, str):
        return error_response("invalid_username", "이름은 문자열이어야 합니다.", 400)
    gid, data = chatbot.new_game(username.strip()[:50] or "사용자")
    response = jsonify(data)
    response.set_cookie(
        COOKIE,
        gid,
        max_age=30 * 86400,
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
    )
    return response


@app.get("/api/item/<item_id>")
def item_view(item_id):
    state = chatbot.store.get(game_id())
    return jsonify({"document": chatbot.engine.document(state, item_id)})


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("invalid_json", "JSON 객체를 보내주세요.", 400)
    action = payload.get("action")
    message = payload.get("message", "")
    if not isinstance(message, str):
        return error_response("invalid_message", "메시지는 문자열이어야 합니다.", 400)
    message = message.strip()
    if len(message) > 2000:
        return error_response(
            "message_too_long", "메시지는 2000자 이하로 입력해 주세요.", 413
        )
    if action is None and not message:
        return error_response("invalid_message", "메시지를 입력해 주세요.", 400)
    if action is not None and (not isinstance(action, dict) or message):
        return error_response(
            "invalid_action", "채팅과 화면 조작은 각각 하나씩 보내주세요.", 400
        )
    username = payload.get("username", "사용자")
    if not isinstance(username, str):
        return error_response("invalid_username", "이름은 문자열이어야 합니다.", 400)
    rid = payload.get("request_id") or secrets.token_urlsafe(18)
    if not isinstance(rid, str) or re.fullmatch(r"[A-Za-z0-9_-]{8,80}", rid) is None:
        return error_response(
            "invalid_request_id", "요청 번호가 올바르지 않습니다.", 400
        )
    expected = payload.get("revision")
    if expected is not None and (type(expected) is not int or expected < 0):
        return error_response("invalid_revision", "진행 번호가 올바르지 않습니다.", 400)
    try:
        result = chatbot.process(
            game_id(), rid, message=message, action=action, expected=expected
        )
        return jsonify(result)
    except (GameError, AIUnavailable):
        raise
    except sqlite3.Error:
        return error_response(
            "storage_busy",
            "저장소를 사용 중입니다. 진행을 다시 불러온 뒤 시도해 주세요.",
            503,
        )
    except Exception as error:
        app.logger.error("게임 요청 실패: %s", type(error).__name__)
        return error_response(
            "chat_failed",
            "응답을 처리하지 못했습니다. 진행을 불러온 뒤 다시 시도해 주세요.",
            500,
        )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
