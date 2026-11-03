"""Portable Windows entry point: start the local game and open its browser."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import threading
import urllib.request
import webbrowser

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))


def configure_connection():
    from dotenv import load_dotenv

    load_dotenv(BASE / ".env")
    load_dotenv(BASE / ".env.local", override=True)
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return
    print("처음 실행하는 PC에서는 AI 연결용 API 키를 한 번 입력해 주세요.")
    print("입력한 키는 화면에 표시되지 않으며 이 폴더의 .env.local에 저장됩니다.")
    key = getpass.getpass("OpenAI API 키: ").strip()
    if not key:
        raise ValueError("API 키를 입력하지 않아 실행을 취소했습니다.")
    os.environ["OPENAI_API_KEY"] = key
    with (BASE / ".env.local").open("a", encoding="utf-8") as file:
        file.write("\nOPENAI_API_KEY=" + json.dumps(key) + "\n")


def main():
    parser = argparse.ArgumentParser(description="13-Fri 게임 실행")
    parser.add_argument("--check", action="store_true", help="설치 상태만 검사")
    parser.add_argument("--smoke-test", action="store_true", help="브라우저 없이 로컬 서버 검사")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 생략")
    args = parser.parse_args()
    os.chdir(BASE)
    if not (args.check or args.smoke_test):
        configure_connection()
    import flask
    import openai
    import httpx
    from werkzeug.serving import make_server
    from app import app

    if args.check:
        required = ("templates/chat.html", "config/dialogue_scenario.json",
                    "public/assets/js/puzzles.js", "public/assets/videos/car1-window-loop.mp4")
        for filename in required:
            if not (BASE / filename).is_file():
                raise FileNotFoundError(filename)
        print("OK: Python, Flask, AI libraries and game assets are ready.")
        return
    server = make_server("127.0.0.1", 0, app, threaded=True)
    address = "http://127.0.0.1:" + str(server.server_port)
    if args.smoke_test:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for route in ("/health", "/chat", "/assets/js/puzzles.js"):
                with urllib.request.urlopen(address + route, timeout=10) as response:
                    if response.status != 200:
                        raise RuntimeError("Startup check failed")
            request = urllib.request.Request(address + "/assets/videos/car1-window-loop.mp4",
                                             headers={"Range": "bytes=0-255"})
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status != 206 or len(response.read()) != 256:
                    raise RuntimeError("Video streaming check failed")
            print("OK: portable server, game screen and video streaming.")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        return
    print("\n13-Fri · 종착역이 없는 열차")
    print("게임 주소: " + address)
    print("브라우저가 자동으로 열립니다. 열리지 않으면 위 주소로 접속하세요.")
    print("게임 중에는 이 창을 열어 두세요. 종료: Ctrl+C 또는 이 창 닫기.\n")
    if not args.no_browser:
        opener = threading.Timer(.5, webbrowser.open, args=(address,))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("\n게임을 시작하지 못했습니다: " + type(error).__name__)
        print("ZIP 전체를 압축 해제했는지, runtime 폴더가 함께 있는지 확인해 주세요.")
        raise SystemExit(1)
