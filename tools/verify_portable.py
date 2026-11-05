"""Verify a freshly extracted Windows bundle without API calls or credentials."""

import argparse
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tools.build_portable import bundle_files, include_in_archive

DEPENDENCY_CHECK = """
import ssl
import sqlite3
import certifi
import httpx
from openai import OpenAI

ssl.create_default_context(cafile=certifi.where())
with sqlite3.connect(':memory:') as database:
    assert database.execute('select 13').fetchone() == (13,)

def respond(request):
    assert request.url.path == '/v1/responses'
    return httpx.Response(200, json={
        'id': 'resp_portable_check', 'object': 'response', 'created_at': 0,
        'status': 'completed', 'model': 'portable-check', 'output': [{
            'id': 'msg_check', 'type': 'message', 'role': 'assistant', 'status': 'completed',
            'content': [{'type': 'output_text', 'text': 'ok', 'annotations': []}]
        }]
    })

transport = httpx.MockTransport(respond)
with OpenAI(api_key='portable-test', base_url='https://portable.test/v1',
            http_client=httpx.Client(transport=transport, trust_env=False)) as client:
    assert client.responses.create(model='portable-check', input='check').output_text == 'ok'
print('OK: SSL trust store, SQLite and AI SDK response parsing (offline).')
"""


def verify_archive(archive_path, base=BASE, browser=False):
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Corrupt portable archive.")
        expected = {"13Fri/" + path.relative_to(base).as_posix(): path for path in bundle_files(base)}
        if set(archive.namelist()) != set(expected):
            raise RuntimeError("Archive does not match the current bundle manifest.")
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if (name.is_absolute() or ".." in name.parts or name.parts[0] != "13Fri"
                    or not include_in_archive(Path(*name.parts[1:]))):
                raise RuntimeError("Unexpected archive path: " + info.filename)
            if archive.read(info.filename) != expected[info.filename].read_bytes():
                raise RuntimeError("Stale archive file: " + info.filename)
        local = base / ".local"
        local.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="portable-verify-", dir=local) as temporary:
            archive.extractall(temporary)
            game = Path(temporary) / "13Fri"
            python = game / "runtime/python.exe"
            subprocess.run([str(python), "-I", "-B", "-X", "utf8", "-c", DEPENDENCY_CHECK],
                           cwd=temporary, check=True, timeout=60)
            for mode in ("--check", "--smoke-test"):
                subprocess.run([str(python), "-I", "-B", "-X", "utf8",
                                str(game / "launch_game.py"), mode], cwd=temporary, check=True, timeout=60)
            # Check the actual launcher with a caller outside the extracted game.
            subprocess.run(["cmd.exe", "/d", "/c", str(game / "게임시작.cmd"), "--check"],
                           cwd=temporary, check=True, timeout=60)
            if browser:
                node = shutil.which("node")
                if not node:
                    raise RuntimeError("Node.js is required for --browser.")
                environment = {
                    **os.environ,
                    "GAMEPLAY_QA_GAME_ROOT": str(game),
                    "GAMEPLAY_QA_PYTHON": str(python),
                    "DIALOGUE_QA_PYTHON": str(python),
                }
                subprocess.run([node, str(base / "tools/check_gameplay_ui.mjs")], cwd=base,
                               env=environment, check=True, timeout=180,
                               creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    print("OK: extracted launcher, server, assets and video; bundle matches source and excludes keys/saves.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=BASE / "dist/13Fri-Windows.zip")
    parser.add_argument("--browser", action="store_true",
                        help="Run offline browser gameplay checks against the extracted bundle.")
    args = parser.parse_args()
    verify_archive(args.archive, browser=args.browser)


if __name__ == "__main__":
    main()
