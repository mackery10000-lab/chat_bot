"""Opt-in scenario QA against the configured real model and real Flask routes.

No remote calls happen on import. Player games are never used as fixtures. Run
``python tools/check_live_scenario.py --smoke`` before the larger suite, then
``python tools/check_live_scenario.py --export-checkpoints``. Reports contain
synthetic game conversations only; API credentials, request headers, model
instructions, and exception text are deliberately excluded.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
from typing import Any
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")[:90] or "case"


def safe_exception(error: BaseException) -> dict:
    """Return diagnostic locations only, without exception text or source lines."""
    frames = []
    trace = error.__traceback__
    while trace is not None:
        code = trace.tb_frame.f_code
        path = Path(code.co_filename)
        try:
            filename = path.resolve().relative_to(BASE).as_posix()
        except (OSError, ValueError):
            filename = path.name
        frames.append({"file": filename, "function": code.co_name,
                       "line": trace.tb_lineno})
        trace = trace.tb_next
    return {"type": type(error).__name__, "frames": frames[-12:]}


def _retry_file_operation(operation):
    # Windows readers and antivirus can briefly hold a file without delete/write
    # sharing. Readers are allowed during a live run; transient sharing violations
    # must not discard a paid scenario turn or stop its remaining checks.
    for attempt in range(21):
        try:
            return operation()
        except PermissionError:
            if attempt == 20:
                raise
            time.sleep(0.05)


def connection_configuration() -> dict:
    """Inspect the application's normal configuration without exposing its key."""
    from dotenv import dotenv_values

    values = dotenv_values(BASE / ".env")
    key = os.getenv("OPENAI_API_KEY") or values.get("OPENAI_API_KEY") or ""
    model = os.getenv("OPENAI_MODEL") or values.get("OPENAI_MODEL") or "gpt-4o-mini"
    model = model.strip()
    return {
        "configured": bool(key.strip()),
        "model": model if re.fullmatch(r"[A-Za-z0-9._:/-]{1,100}", model) else "configured-model",
        "endpoint": "https://api.openai.com/v1",
        "sdk_retries": 0,
        "per_call_timeout_seconds": 22,
    }


class ScenarioFailure(RuntimeError):
    """Only a fixed safe message is emitted by the CLI for this exception."""


class LiveScenarioRunner:
    def __init__(self, *, max_calls: int = 160, output_root: Path | None = None,
                 run_id: str | None = None, export_checkpoints: bool = False):
        if not 1 <= max_calls <= 160:
            raise ValueError("max_calls must be between 1 and 160")
        run_id = _slug(run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                       + "-" + secrets.token_hex(3))
        self.output_dir = (output_root or BASE / ".local/live-scenario-qa") / run_id
        self.output_dir.mkdir(parents=True, exist_ok=False)
        self.report_path = self.output_dir / "report.json"
        self.events_path = self.output_dir / "events.jsonl"
        self.export_checkpoints = export_checkpoints
        self.max_calls = max_calls
        self.checkpoints: dict[str, dict] = {}
        self.cases: list[LiveScenarioCase] = []
        self._current_case: LiveScenarioCase | None = None
        self._current_step: dict | None = None
        self._entered = False
        self._finished = False
        self._sequence = 0
        self.report = {
            "version": 1, "run_id": run_id, "started_utc": _utc_now(),
            "status": "prepared", "connection": connection_configuration(),
            "isolation": "Temporary SQLite; app.chatbot replaced only for this process",
            "max_model_calls": max_calls, "model_calls": [], "cases": [],
            "checkpoints": [], "checks": {"passed": 0, "failed": 0},
            "usage": None,
            "usage_note": "DemoGenerator returns text only; SDK token usage is not exposed. Calls and elapsed time are measured.",
        }
        self._persist()

    def __enter__(self):
        if not self.report["connection"]["configured"]:
            self.report["status"] = "configuration_missing"
            self._persist()
            raise ScenarioFailure("API configuration is missing")
        # Importing app is intentionally delayed until the explicit live run.
        import app as web
        from services.chatbot_service import ChatbotService
        from services.generator import AIUnavailable, DemoGenerator

        self.web = web
        self._temporary = tempfile.TemporaryDirectory(prefix="live-scenario-qa-")
        generator = DemoGenerator()
        original_complete = generator._complete

        def measured_complete(instructions, payload, schema=None):
            if len(self.report["model_calls"]) >= self.max_calls:
                self.report["budget_exhausted"] = True
                self._persist()
                raise AIUnavailable("검수 API 호출 상한에 도달했습니다. 진행은 보존됩니다.")
            record = {
                "number": len(self.report["model_calls"]) + 1,
                "kind": "interpret" if schema and "intent" in schema.get("properties", {}) else "reply",
                "case": self._current_case.name if self._current_case else "",
                "step": self._current_step["number"] if self._current_step else None,
                "started_utc": _utc_now(), "status": "pending",
            }
            self.report["model_calls"].append(record)
            self._persist()
            started = time.perf_counter()
            try:
                value = original_complete(instructions, payload, schema)
                record["status"] = "completed"
                if record["kind"] == "interpret":
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict):
                            record["interpretation"] = {
                                key: parsed.get(key) for key in (
                                    "intent", "target", "recipient", "topic", "mode",
                                    "affirmed_features", "denied_features", "described_item",
                                    "referent_relation", "dialogue_choice_id", "behavior")
                            }
                    except (ValueError, TypeError):
                        record["interpretation_invalid_json"] = True
                return value
            except Exception:
                record["status"] = "ai_unavailable"
                # Never retain SDK exception text or chained request details.
                raise AIUnavailable("실제 API 검수 연결이 완료되지 않았습니다. 진행은 보존됩니다.") from None
            finally:
                record["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                self._event("model_call", record)

        generator._complete = measured_complete
        self.service = ChatbotService(generator=generator,
                                      db_path=Path(self._temporary.name) / "qa.sqlite3")
        self._swap = patch.object(web, "chatbot", self.service)
        self._swap.start()
        self._entered = True
        self.report["status"] = "running"
        self._event("started", {"connection": self.report["connection"]})
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is not None:
                self.report["interrupted"] = True
                self.report["diagnostic"] = safe_exception(exc_value)
            self.finish()
        finally:
            if self._entered:
                self._swap.stop()
                self._temporary.cleanup()
                self._entered = False
        return False

    def _persist(self):
        pending = self.report_path.with_suffix(".json.tmp")
        content = json.dumps(self.report, ensure_ascii=False, indent=2)
        _retry_file_operation(lambda: pending.write_text(content, encoding="utf-8"))
        _retry_file_operation(lambda: pending.replace(self.report_path))

    def _event(self, kind, data):
        content = json.dumps({"at_utc": _utc_now(), "type": kind, "data": data},
                             ensure_ascii=False) + "\n"
        def append_event():
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(content)
        _retry_file_operation(append_event)
        self._persist()

    def new_case(self, name: str, checkpoint: str | None = None):
        if not self._entered:
            raise ScenarioFailure("Runner must be entered before starting a case")
        if any(case.name == name for case in self.cases):
            raise ScenarioFailure("Case names must be unique")
        case = LiveScenarioCase(self, name)
        self.cases.append(case)
        self.report["cases"].append(case.record)
        self._current_case = case
        response = case.client.post("/api/game/new", json={"username": "실제 API 시나리오 검수"})
        if response.status_code != 200:
            raise ScenarioFailure("Isolated game could not start")
        case.data = response.get_json()
        case.game_id = case.client.get_cookie(self.web.COOKIE).value
        if checkpoint is not None:
            if checkpoint not in self.checkpoints:
                raise ScenarioFailure("Checkpoint does not exist")
            state = deepcopy(self.checkpoints[checkpoint])
            # Forks use their own cookie, game ID, request cache, and revision.
            with self.service.store.connect() as database:
                database.execute("UPDATE games SET state=?,revision=?,lease=NULL,lease_until=0 WHERE id=?",
                                 (json.dumps(state, ensure_ascii=False), state["revision"], case.game_id))
            snapshot = case.client.get("/api/game")
            if snapshot.status_code != 200:
                raise ScenarioFailure("Checkpoint could not be loaded")
            case.data = snapshot.get_json()
            case.record["checkpoint_source"] = checkpoint
        case.record["initial_state"] = case.state
        case.record["initial_response"] = deepcopy(case.data)
        self._event("case_started", {"name": name, "checkpoint": checkpoint})
        return case

    def fork(self, name: str, checkpoint: str):
        return self.new_case(name, checkpoint=checkpoint)

    @property
    def has_failed(self):
        return self.report["checks"]["failed"] > 0

    def finish(self):
        if self._finished:
            return self.report_path
        for case in self.cases:
            case.record["final_state"] = case.state
            case.record["final_response"] = deepcopy(case.data)
            case.record["status"] = "failed" if any(
                not check["passed"] for check in case.record["checks"]) else "passed"
        self.report["status"] = "failed" if (self.has_failed or self.report.get("interrupted")
                                               or self.report.get("budget_exhausted")) else "passed"
        self.report["finished_utc"] = _utc_now()
        self.report["model_call_count"] = len(self.report["model_calls"])
        self.report["model_elapsed_seconds"] = round(sum(
            call.get("elapsed_seconds", 0) for call in self.report["model_calls"]), 3)
        self._finished = True
        self._event("finished", {"status": self.report["status"], "checks": self.report["checks"]})
        return self.report_path


class LiveScenarioCase:
    def __init__(self, runner: LiveScenarioRunner, name: str):
        self.runner, self.name = runner, name
        self.client = runner.web.app.test_client()
        self.game_id = ""
        self.data: dict = {}
        self.record = {"name": name, "status": "running", "turns": [], "checks": []}

    @property
    def state(self):
        return self.runner.service.store.get(self.game_id)

    @property
    def flags(self):
        return self.state["flags"]

    @property
    def items(self):
        return set(self.state["inventory"])

    def check(self, condition: bool, label: str, *, actual=None, expected=None, fatal=False):
        record = {"label": label, "passed": bool(condition)}
        if actual is not None:
            record["actual"] = sorted(actual) if isinstance(actual, set) else actual
        if expected is not None:
            record["expected"] = sorted(expected) if isinstance(expected, set) else expected
        self.record["checks"].append(record)
        self.runner.report["checks"]["passed" if condition else "failed"] += 1
        self.runner._event("check", {"case": self.name, **record})
        if not condition and fatal:
            raise ScenarioFailure("A required scenario assertion failed")
        return bool(condition)

    def expect(self, path: str, expected: Any, label: str = "", *, fatal=False):
        if path.startswith("state."):
            actual, keys = self.state, path.split(".")[1:]
        elif path.split(".")[0] in self.data:
            actual, keys = self.data, path.split(".")
        else:
            actual, keys = self.state, path.split(".")
        try:
            for key in keys:
                actual = actual[int(key)] if isinstance(actual, list) else actual[key]
        except (KeyError, IndexError, ValueError, TypeError):
            return self.check(False, label or path, actual="<missing>", expected=expected, fatal=fatal)
        return self.check(actual == expected, label or path, actual=actual, expected=expected, fatal=fatal)

    def say(self, text: str, *, label: str = "", expected_http: int = 200):
        return self._turn({"message": text}, label or text, expected_http)

    def action(self, kind: str, target: str = "", *, label: str = "", expected_http: int = 200,
               **extra):
        return self._turn({"action": {"type": kind, "target": target, **extra}},
                          label or kind + (":" + target if target else ""), expected_http)

    def _turn(self, payload: dict, label: str, expected_http: int):
        self.runner._current_case = self
        self.runner._sequence += 1
        before = self.state
        request_payload = {"request_id": "live_qa_" + str(self.runner._sequence),
                           "revision": self.data["game"]["revision"], **payload}
        calls_before = len(self.runner.report["model_calls"])
        turn = {"number": len(self.record["turns"]) + 1, "label": label,
                "input": deepcopy(payload), "before": before, "status": "pending"}
        self.record["turns"].append(turn)
        self.runner._current_step = turn
        self.runner._event("turn_started", {"case": self.name, "turn": turn})
        started = time.perf_counter()
        try:
            response = self.client.post("/api/chat", json=request_payload)
        except Exception:
            turn.update(status="request_failed", elapsed_seconds=round(time.perf_counter() - started, 3))
            self.check(False, label + ": request completed")
            raise ScenarioFailure("The isolated HTTP request failed") from None
        finally:
            self.runner._current_step = None
        body = response.get_json(silent=True)
        after = self.state
        turn.update(http_status=response.status_code, status="completed",
                    elapsed_seconds=round(time.perf_counter() - started, 3),
                    model_calls=len(self.runner.report["model_calls"]) - calls_before,
                    response=body, after=after)
        self.check(response.status_code == expected_http, label + ": HTTP status",
                   actual=response.status_code, expected=expected_http)
        if response.status_code == 200 and isinstance(body, dict) and "game" in body:
            self.data = body
            self.check(isinstance(body.get("reply"), str) and bool(body["reply"].strip()),
                       label + ": nonempty reply")
            self.check(body["game"].get("revision") == before["revision"] + 1,
                       label + ": revision advanced once")
            self.check(after["revision"] == body["game"].get("revision"),
                       label + ": persisted revision matches response")
        else:
            self.check(after == before, label + ": rejected request preserves state")
        self.runner._event("turn_finished", {"case": self.name, "turn": turn})
        if response.status_code != expected_http:
            raise ScenarioFailure("The HTTP status differed from the scenario expectation")
        return body

    def checkpoint(self, name: str):
        if name in self.runner.checkpoints:
            raise ScenarioFailure("Checkpoint names must be unique")
        state = deepcopy(self.state)
        self.runner.checkpoints[name] = state
        record = {"name": name, "source_case": self.name, "revision": state["revision"],
                  "provenance": "actual Flask gameplay requests", "state": state}
        if self.runner.export_checkpoints:
            directory = self.runner.output_dir / "checkpoints"
            directory.mkdir(exist_ok=True)
            path = directory / (_slug(name) + ".json")
            path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            record["file"] = str(path.relative_to(self.runner.output_dir))
        self.runner.report["checkpoints"].append(record)
        self.runner._event("checkpoint", record)
        return name

    def expect_terminal(self, status: str):
        if status not in ("good", "bad"):
            raise ScenarioFailure("Terminal status must be good or bad")
        self.expect("game.status", status, "expected " + status + " ending")
        self.expect("game.ending_video", {
            "kind": status,
            "src": "/assets/videos/" + status + "-ending.mp4",
        }, "ending selects the supplied video")
        self.check(self.data["game"]["location"]["id"] != "platform",
                   "ending requires no separate exit room")
        self.check(not any(location["id"] == "platform"
                           for location in self.data["game"].get("map", [])),
                   "map has no exit room")
        self.check(self.state["confirmation"] is None, "ending has no pending confirmation")
        return self.data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="One real interpretation call only")
    parser.add_argument("--connection-check", action="store_true", help="Read configuration without a remote call")
    parser.add_argument("--suite", default="tools.live_scenario_cases:run_suite")
    parser.add_argument("--max-calls", type=int, default=160)
    parser.add_argument("--run-id")
    parser.add_argument("--export-checkpoints", action="store_true")
    args = parser.parse_args(argv)
    if args.connection_check:
        print(json.dumps(connection_configuration(), ensure_ascii=False))
        return 0
    runner = None
    try:
        runner = LiveScenarioRunner(max_calls=args.max_calls, run_id=args.run_id,
                                    export_checkpoints=args.export_checkpoints)
        with runner:
            if args.smoke:
                case = runner.new_case("real-api-connection")
                case.say("주변을 살펴본다.", label="single interpretation connection check")
                case.expect("game.status", "playing")
                case.check(len(runner.report["model_calls"]) == 1, "smoke uses exactly one model call")
            else:
                module_name, separator, function_name = args.suite.partition(":")
                if not separator:
                    function_name = "run_suite"
                suite = getattr(importlib.import_module(module_name), function_name)
                suite(runner)
        print(json.dumps({"status": runner.report["status"], "report": str(runner.report_path),
                          "model_calls": len(runner.report["model_calls"]),
                          "checks": runner.report["checks"]}, ensure_ascii=False))
        return 1 if runner.has_failed or runner.report["status"] != "passed" else 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "report": str(runner.report_path) if runner else None}))
        return 130
    except Exception as error:
        # SDK errors can include credentials or request data: never print str(error).
        print(json.dumps({"status": "failed", "reason": "Check the safe local report; no credentials or exception details were logged.",
                          "diagnostic": safe_exception(error),
                          "report": str(runner.report_path) if runner else None}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
