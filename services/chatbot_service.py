"""베이스의 서비스 경계를 유지하는 열차 진행 엔진과 SQLite 저장."""

from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time

from .generator import DemoGenerator, approved_reply, grounded_features
from .image_selector import DemoImageSelector
from .retriever import DemoRetriever

BASE_DIR = Path(__file__).resolve().parents[1]
LOCATIONS = {
    "car_1": "1호차",
    "car_2": "2호차",
    "car_3": "3호차",
    "car_4": "4호차",
    "crew": "승무원실",
    "engine": "기관실",
    "platform": "승강장",
}
EDGES = {
    "car_1": ["car_2"],
    "car_2": ["car_1", "car_3"],
    "car_3": ["car_2", "car_4"],
    "car_4": ["car_3", "crew", "engine"],
    "crew": ["car_4"],
    "engine": ["car_4"],
    "platform": [],
}
UI_ACTIONS = {
    "look",
    "move",
    "select_npc",
    "inspect",
    "read_item",
    "use_item",
    "operate",
    "read_report",
    "prepare_evidence",
    "prepare_control",
    "confirm",
    "cancel",
    "abandon",
    "hint",
    "disembark",
    "end_talk",
    "present",
}


class GameError(RuntimeError):
    def __init__(self, message, code="invalid_action", status=400):
        super().__init__(message)
        self.code, self.status = code, status


def load_game_config():
    return json.loads(
        (BASE_DIR / "config/chatbot_config.json").read_text(encoding="utf-8")
    )


class GameStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else BASE_DIR / "data/train_state.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS games (id TEXT PRIMARY KEY, state TEXT NOT NULL, revision INTEGER NOT NULL, lease TEXT, lease_until REAL NOT NULL DEFAULT 0)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS turns (game_id TEXT NOT NULL, request_id TEXT NOT NULL, digest TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(game_id,request_id))"
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=8)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=8000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, username):
        gid = secrets.token_urlsafe(32)
        state = {
            "schema": 1,
            "revision": 0,
            "username": username,
            "location": "car_1",
            "npc": "",
            "status": "playing",
            "reason": "",
            "inventory": ["ticket_current"],
            "read": [],
            "flags": {},
            "visited": ["car_1"],
            "history": [],
            "journal": [],
            "pending_dialogue": "",
            "features": [],
            "description_item": "",
            "expression": "neutral",
            "npc_turns": {},
            "cleaner_count": 0,
            "confirmation": None,
            "attempts": 1,
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO games(id,state,revision) VALUES(?,?,0)",
                (gid, json.dumps(state, ensure_ascii=False)),
            )
        return gid, state

    def get(self, gid):
        with self.connect() as db:
            row = db.execute("SELECT state FROM games WHERE id=?", (gid,)).fetchone()
        if not row:
            raise GameError(
                "저장된 게임을 찾지 못했습니다. 새 게임을 시작해 주세요.",
                "game_missing",
                404,
            )
        return json.loads(row["state"])

    def reserve(self, gid, rid, digest, expected):
        lease = secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cached = db.execute(
                "SELECT digest,response FROM turns WHERE game_id=? AND request_id=?",
                (gid, rid),
            ).fetchone()
            if cached:
                if cached["digest"] != digest:
                    raise GameError(
                        "같은 요청 번호에 서로 다른 입력을 사용할 수 없습니다.",
                        "request_conflict",
                        409,
                    )
                return None, None, json.loads(cached["response"])
            row = db.execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
            if not row:
                raise GameError("저장된 게임이 없습니다.", "game_missing", 404)
            if expected is not None and expected != row["revision"]:
                raise GameError(
                    "다른 화면에서 진행 상태가 바뀌었습니다. 최신 상태를 불러와 주세요.",
                    "stale_state",
                    409,
                )
            if row["lease"] and row["lease_until"] > time.time():
                raise GameError(
                    "이전 응답을 처리 중입니다. 잠시 후 다시 시도해 주세요.",
                    "turn_busy",
                    409,
                )
            db.execute(
                "UPDATE games SET lease=?,lease_until=? WHERE id=?",
                (lease, time.time() + 100, gid),
            )
            return json.loads(row["state"]), lease, None

    def release(self, gid, lease):
        with self.connect() as db:
            db.execute(
                "UPDATE games SET lease=NULL,lease_until=0 WHERE id=? AND lease=?",
                (gid, lease),
            )

    def commit(self, gid, rid, digest, lease, old_revision, state, response):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE games SET state=?,revision=?,lease=NULL,lease_until=0 WHERE id=? AND revision=? AND lease=?",
                (
                    json.dumps(state, ensure_ascii=False),
                    state["revision"],
                    gid,
                    old_revision,
                    lease,
                ),
            ).rowcount
            if changed != 1:
                raise GameError(
                    "진행 상태가 변경되어 입력을 확정하지 않았습니다. 새로 불러와 주세요.",
                    "stale_state",
                    409,
                )
            db.execute(
                "INSERT INTO turns VALUES(?,?,?,?)",
                (gid, rid, digest, json.dumps(response, ensure_ascii=False)),
            )


class GameEngine:
    def __init__(self, config):
        self.config = config

    def result(self, text, npc="", facts=None, ui=None):
        return {"canonical": text, "npc": npc, "facts": facts or [], "ui": ui or {}}

    def end_talk(self, s):
        s["npc"] = ""
        s["pending_dialogue"] = ""
        s["features"] = []
        s["description_item"] = ""
        s["pending_features"] = []
        s["expression"] = "neutral"
        return self.result("대화를 마치고 주변으로 시선을 돌렸다. " + self.look(s))

    def mark(self, s, name, note=None):
        fresh = not s["flags"].get(name)
        s["flags"][name] = True
        if fresh and note and note not in s["journal"]:
            s["journal"].append(note)
        return fresh

    def give(self, s, item):
        if item not in s["inventory"]:
            s["inventory"].append(item)

    def available_npcs(self, s):
        if s["flags"].get("route_open"):
            return []
        if s["location"] == "car_3" and not s["flags"].get("light_on"):
            return []
        return [
            k for k, v in self.config["npcs"].items() if v["location"] == s["location"]
        ]

    def context(self, s):
        return {
            "location": LOCATIONS[s["location"]],
            "active_npc": s["npc"],
            "visible_npcs": [
                {"id": x, "name": self.config["npcs"][x]["name"]}
                for x in self.available_npcs(s)
            ],
            "owned_items": [
                {"id": i, "name": self.config["items"][i]["name"]}
                for i in s["inventory"]
            ],
            "targets": {
                "car_1": "1호차",
                "car_2": "2호차",
                "car_3": "3호차",
                "car_4": "4호차",
                "crew": "승무원실",
                "engine": "기관실",
                "platform": "열차에서 내리기",
                "notice": "안내문",
                "window": "창문",
                "cover": "점검 덮개 열기",
                "lever_down": "레버를 아래로 끝까지 내리기",
                "lever_up": "레버 올리기",
                "handle": "문손잡이 당기기",
                "route_report": "책상 위 운행 서류",
                "desk": "책상",
            },
            "pending_dialogue": s["pending_dialogue"],
            "features_in_this_description": s["features"],
            "description_item": s.get("description_item", ""),
            "recent_dialogue": [h for h in s["history"] if h.get("npc") == s["npc"]][-6:],
        }

    def can_enter(self, s, loc):
        f = s["flags"]
        if loc == "car_1":
            return True, ""
        if loc == "car_2":
            return bool(f.get("notice_read")), "먼저 1호차의 안내문을 확인해야 한다."
        if loc == "car_3":
            return bool(
                f.get("supplies_received")
            ), "탐험가와 대화하고 앞쪽을 조사할 도구를 받아야 한다."
        if loc == "car_4":
            return bool(
                f.get("destination_hint")
            ), "노인의 분실물을 찾아 돌려드리고, 목적지에 관해 더 물어보자."
        if loc == "crew":
            return bool(
                f.get("door_open")
            ), "승무원실 문이 잠겨 있다. 출입문 옆 장치를 확인할 수 있다."
        if loc == "engine":
            return bool(
                f.get("engine_permission")
            ), "승무원이 기관실 출입을 막고 있다. 부탁받은 일을 마무리해야 한다."
        if loc == "platform":
            return bool(f.get("route_open")), "달리는 열차에서 내릴 수 없다."
        return False, "이동할 수 없는 장소다."

    def move(self, s, target):
        if target not in LOCATIONS:
            return self.result("이동할 장소를 분명하게 말해 주세요.")
        if target == "platform":
            if not s["flags"].get("route_open"):
                return self.result(
                    "열차는 아직 달리고 있다. 지금은 밖으로 나갈 수 없다."
                )
            s["status"] = "good"
            s["location"] = "platform"
            s["npc"] = ""
            s["confirmation"] = None
            self.mark(s, "disembarked", "승강장에 발을 딛고 현실로 돌아왔다.")
            return self.result(
                "승무원이 부축한 탐험가와 함께 승강장으로 내려선다. 노인과 청소원, 기관사도 차례로 열차에서 내린다. 발이 땅에 닿는 순간, 2026년의 현실이 돌아온다."
            )
        if s["location"] == "platform":
            if target in s["visited"]:
                s["location"] = target
            else:
                return self.result("열차가 정차했다. 먼저 승강장으로 내려설 수 있다.")
        else:
            queue = [(s["location"], [])]
            seen = set()
            route = None
            while queue:
                at, path = queue.pop(0)
                if at == target:
                    route = path
                    break
                if at in seen:
                    continue
                seen.add(at)
                for nxt in EDGES[at]:
                    queue.append((nxt, path + [nxt]))
            if route is None:
                return self.result("연결된 통로로 이동해야 한다.")
            for place in route:
                ok, why = self.can_enter(s, place)
                if not ok:
                    return self.result(why)
            s["location"] = target
        s["pending_dialogue"] = ""
        s["features"] = []
        s["description_item"] = ""
        s["confirmation"] = None
        if target not in s["visited"]:
            s["visited"].append(target)
        s["npc"] = ""
        s["expression"] = "neutral"
        descriptions = {
            "car_1": "1호차로 돌아왔다. 좌석 옆 안내문과 창문이 보인다.",
            "car_2": "2호차에 들어섰다. 앞 좌석에 젊은 남성이 앉아 있다. 발목을 다친 듯하다.",
            "car_3": "3호차에 들어서자 불이 꺼져 아무것도 보이지 않는다. 커피 냄새와 청소하는 소리가 희미하게 느껴진다."
            if not s["flags"].get("light_on")
            else "손전등이 밝힌 3호차에 노인과 청소원이 있다.",
            "car_4": "4호차는 밝다. 텅 빈 좌석 사이에서 승무원이 서류를 정리하다 고개를 든다. “지금은 위험합니다. 좌석으로 돌아가십시오.”",
            "crew": "문을 열고 들어서자 작은 책상과 서류 보관함이 보인다. 책상 위에 여러 장의 운행 서류가 놓여 있다.",
            "engine": "기관실에 들어섰다. 제어 장치 앞의 기관사가 차갑게 돌아본다. “여기 들어오시면 안 됩니다.”",
        }
        return self.result(descriptions[target])

    def read_item(self, s, item):
        if item not in s["inventory"]:
            return self.result("지금 보관함에는 그 물건이 없다.")
        if item not in s["read"]:
            s["read"].append(item)
        if item == "facility_manual":
            self.mark(s, "manual_read", "시설 안내서의 비상 개방 절차를 읽었다.")
        if item == "ticket_old":
            self.mark(
                s,
                "old_ticket_read",
                "오래된 승차권은 2016년 발급이며 하차역 글자가 훼손되었다.",
            )
        if item == "ticket_current":
            self.mark(s, "current_ticket_read", "자신의 승차권 발행 연도는 2026년이다.")
        if item == "newspaper":
            self.mark(
                s, "newspaper_read", "2016년 실종 사건의 자료 사진에도 13-Fri가 보인다."
            )
        doc = self.document(s, item)
        return self.result(doc["title"] + " 내용을 확인했다.", ui={"document": doc})

    def document(self, s, item):
        if item not in s["inventory"]:
            raise GameError("보유하지 않은 문서는 열 수 없습니다.", "not_owned", 403)
        if item == "elder_testimony":
            paragraphs = []
            if s["flags"].get("elder_features"):
                paragraphs.append(
                    "승차권은 누렇게 바랜 종이에 구멍이 뚫려 있었다. 노인은 커피를 쏟은 뒤 승차권을 잃어버렸다고 했다."
                )
            if s["flags"].get("destination_hint"):
                paragraphs.append(
                    "목적지에 “산”이라는 글자가 들어간다. 삶과 죽음의 경계라고 해서 그런 이름이 붙었다고 했다."
                )
            return {
                "id": item,
                "kind": "note",
                "eyebrow": "WITNESS NOTE",
                "title": "노인의 증언",
                "fields": [],
                "paragraphs": paragraphs,
            }
        doc = deepcopy(self.config["items"][item]["document"])
        doc.update(id=item, kind=self.config["items"][item]["kind"])
        if item == "ticket_old" and s["flags"].get("ticket_returned"):
            doc["paragraphs"].append(
                "원본은 노인에게 돌려드렸다. 이 화면은 당시 확인한 내용을 보존한 조사 기록이다."
            )
        return doc

    def operate(self, s, target):
        f = s["flags"]
        if s["location"] not in ("car_4", "crew"):
            return self.result("이 장소에는 승무원실 출입문 장치가 없다.")
        if not f.get("mission_accepted"):
            return self.result("출입문을 조작하기 전에 승무원과 이야기해야 한다.")
        if not f.get("manual_read"):
            return self.result(
                "잠금장치가 고장 나 있다. 구형 시설 안내서에서 비상 개방 절차를 확인할 수 있다."
            )
        if target == "cover":
            self.mark(s, "cover_open")
            return self.result(
                "출입문 오른쪽 하단의 사각형 점검 덮개를 열었다. 안쪽에 노란색 수동 해제 레버가 보인다.",
                ui={"lever": True},
            )
        if target in ("lever_down", "lever_up"):
            if not f.get("cover_open"):
                return self.result("덮개가 닫혀 있어 내부 레버에 손이 닿지 않는다.")
            if target == "lever_up":
                return self.result(
                    "레버를 위로 움직여도 잠금은 풀리지 않는다. 안내서의 방향을 다시 확인하자.",
                    ui={"lever": True},
                )
            self.mark(s, "lever_down")
            return self.result(
                "노란색 레버를 아래로 끝까지 내렸다. “철컥―” 잠금 해제음이 들렸다.",
                ui={"lever": True},
            )
        if target == "handle":
            if not f.get("lever_down"):
                return self.result(
                    "문손잡이를 당겨도 문이 움직이지 않는다. 잠금이 아직 풀리지 않았다."
                )
            self.mark(s, "door_open", "비상 개방 절차에 따라 승무원실 문을 열었다.")
            return self.result(
                "잠금이 풀린 문손잡이를 당겼다. 승무원실 문이 열리고 안쪽 책상이 보인다."
            )
        return self.result("어느 장치를 어떻게 조작할지 분명하게 말해 주세요.")

    def inspect(self, s, target):
        if target in self.config["items"]:
            if target == "route_report" and target not in s["inventory"]:
                return self.read_report(s)
            return self.read_item(s, target)
        if target == "notice":
            if s["location"] != "car_1":
                return self.result("그 안내문은 1호차에 있다.")
            self.mark(s, "notice_read", "안내문: 열차의 정차는 기관실에서만 가능.")
            return self.result(
                "안내문을 직접 읽었다. “Warning : 열차의 정차는 기관실에서만 가능.” 1호차에는 기관실이 보이지 않는다. 반대편 객차부터 살펴보자.", ui={"notice": True}
            )
        if target == "window":
            if s["location"] not in ("car_1", "car_2", "car_3", "car_4", "engine"):
                return self.result("이곳에서는 그 창문을 조사할 수 없다.")
            self.mark(s, "loop_observed", "창밖에 같은 철교와 터널이 반복된다.")
            return self.result(
                "창밖을 자세히 본다. 조금 전에 지났던 것 같은 철교와 터널이 다시 나타난다. 열차는 앞으로 움직이는데 풍경은 반복된다."
            )
        if target == "desk" and s["location"] == "crew":
            return self.result(
                "책상 위에는 여러 장의 운행 서류가 놓여 있다. 내용을 읽어볼 수 있다."
            )
        if (
            target in ("door", "cover", "handle", "lever_down")
            and s["location"] == "car_4"
        ):
            return self.result(
                "관계자 외 출입금지 문이다. 카드 인식기에는 빨간불이 깜빡인다. 문 오른쪽 하단에 사각형 점검 덮개가 있다.",
                ui={"lever": bool(s["flags"].get("mission_accepted"))},
            )
        return self.result(
            "지금 보이거나 보유한 대상 중 무엇을 조사할지 구체적으로 말해 주세요."
        )

    def read_report(self, s):
        if s["location"] != "crew" or not s["flags"].get("door_open"):
            return self.result("서류가 있는 승무원실에 먼저 들어가야 한다.")
        self.give(s, "route_report")
        self.mark(
            s,
            "report_read",
            "보고서에서 아지산역과 분기기 잠금, 자동 정차 정보를 확인했다.",
        )
        if "route_report" not in s["read"]:
            s["read"].append("route_report")
        return self.result(
            "책상 위 운행 서류를 실제로 읽었다. 제목은 “2016년 아지산역 폐쇄 예정 및 선로 통제 보고서”. 이제 목적지를 특정할 수 있다.",
            ui={"document": self.document(s, "route_report")},
        )

    def talk(self, s, npc, topic, intent):
        if npc not in self.available_npcs(s):
            return self.result("지금 이곳에서 대화할 수 있는 상대를 선택해 주세요.")
        if s["npc"] != npc:
            s["features"] = []
            s["pending_dialogue"] = ""
            s["description_item"] = ""
        s["npc"] = npc
        f = s["flags"]
        turns = s.setdefault("npc_turns", {})
        turns[npc] = turns.get(npc, 0) + 1
        if topic == "off_topic":
            lines = {
                "explorer": "그건 솔직히 저도 모르겠는데요. 제가 직접 확인한 열차 이야기라면 말씀드릴게요.",
                "elder": "아이고, 그건 기억이 안 나는구먼. 내가 아는 것만 말해주겠네.",
                "cleaner": "죄송하지만 거기까지는 모르겠습니다. 저는 지금 청소 중입니다.",
                "attendant": "그 사항은 확인할 수 없습니다. 현재 객실에서 필요한 도움을 말씀하십시오.",
                "driver": "확인하지 못한 내용에는 답할 수 없습니다. 운행에 관한 용건을 말씀하십시오.",
            }
            return self.result(lines[npc], npc)
        if npc == "explorer":
            if not f.get("explorer_met"):
                self.mark(
                    s, "explorer_met", "탐험가는 2016년 실종된 13-Fri를 조사해 왔다."
                )
                self.give(s, "newspaper")
                prefix = "저는 탐험가예요. 10년 전 23시 59분에 출발하고 사라진 13-Fri를 조사했는데, 2026년에 같은 열차가 다시 나타났잖아요? 자료 사진이 있는 이 신문을 가져가세요. "
            else:
                prefix = ""
            if topic in ("tools", "help") or intent["intent"] == "accept":
                if f.get("supplies_received"):
                    return self.result("손전등과 구형 시설 안내서는 이미 드렸잖아요? 제 발목은 여전히 움직이기 힘드네요. 가지고 계신 물건을 조사에 써보세요.", npc, ["explorer_loop"])
                self.give(s, "flashlight")
                self.give(s, "facility_manual")
                self.mark(
                    s,
                    "supplies_received",
                    "탐험가에게 손전등과 구형 열차 시설 안내서를 받았다.",
                )
                return self.result(
                    prefix
                    + "저도 기관실로 가려 했지만 앞쪽에서 넘어져 발목을 다쳤어요. 대신 조사할 때 쓰던 손전등과 구형 열차 시설 안내서를 가져가세요. 당신이라면 제가 못 찾은 걸 찾을지도 모르잖아요?",
                    npc,
                    ["explorer_case", "explorer_loop"],
                )
            if topic == "loop":
                return self.result(
                    prefix
                    + "창밖을 자세히 보면 같은 철교와 터널이 계속 반복돼요. 앞으로 가는데 같은 곳으로 돌아오는 거라니까요. 기관실을 조사해야겠는데 저는 발목을 다쳐 걷기가 힘드네요.",
                    npc,
                    ["explorer_loop"],
                )
            if topic == "destination":
                return self.result(
                    prefix
                    + "도착해야 할 장소의 이름은 조사한 기록에서 찾지 못했어요. 당시 발급된 물건이나 기록이 있으면 결정적인 증거가 될 텐데요.",
                    npc,
                    ["explorer_case"],
                )
            if topic == "year":
                return self.result(
                    prefix
                    + "제가 열차에 탄 건 2026년이에요. 하지만 이 안에는 10년 전 실종 사건과 닮은 점이 너무 많잖아요?",
                    npc,
                    ["explorer_case"],
                )
            s["pending_dialogue"] = "explorer_tools"
            return self.result(
                (prefix + "앞쪽을 조사해 보시겠어요?")
                if prefix
                else "실종 당시와 지금의 출발 시각도, 열차 번호도 같아요. 아직 추측이지만 열차 안에 당시 물건이나 기록이 남아 있을 수 있겠는데요? 앞쪽을 조사해 보시겠어요?",
                npc,
                ["explorer_case", "explorer_loop"],
            )
        if npc == "elder":
            self.mark(s, "elder_met")
            if topic == "appearance":
                self.give(s, "elder_testimony")
                self.mark(
                    s,
                    "elder_features",
                    "노인의 표: 누렇게 바랜 종이에 구멍이 뚫려 있었다.",
                )
                return self.result(
                    "아이고, 누렇게 바랜 종이에 구멍이 뚫린 표였어. 창가에서 커피를 쏟고 나서는 영 기억이 안 나는구먼. 그때 청소하는 사람이 지나갔던 것 같네.",
                    npc,
                    ["elder_appearance"],
                )
            if topic == "destination":
                if not f.get("ticket_returned"):
                    return self.result(
                        "목적지는 내 승차권에 있었는데, 표부터 찾아야겠구먼. 아직 승무원 검사도 못 받았네.",
                        npc,
                        ["elder_lost"],
                    )
                self.give(s, "elder_testimony")
                self.mark(
                    s,
                    "destination_hint",
                    "노인은 목적지에 산이 들어가며 삶과 죽음의 경계와 관련 있다고 했다.",
                )
                return self.result(
                    "아이고, 정확한 이름은 잘 기억이 안 나네. 무슨 “산”이었는데… 삶과 죽음의 경계라고 해서 그런 이름이 붙었다고 들었네.",
                    npc,
                    ["elder_destination"],
                )
            if topic == "year":
                return self.result(
                    "아이고, 지금은 2016년 아이가. 2026년이라니 농담도 참 별나게 하는구먼.",
                    npc,
                    ["elder_year"],
                )
            if topic == "origin":
                return self.result(
                    "부산이 내 고향이지. 어디로 가던 길이었는지는 승차권을 봐야겠는데, 그걸 잃어버렸네.",
                    npc,
                    ["elder_year", "elder_lost"],
                )
            if f.get("ticket_returned"):
                return self.result(
                    "내 표를 찾아줘 고맙네. 기억나는 것이라도 물어보면 이야기해 주겠구먼.",
                    npc,
                    ["elder_lost"],
                )
            return self.result(
                "아이고, 거기 누구요? 아까 커피를 쏟고 나서 승차권이 안 보이네. 아직 검사도 못 받았는데 꼭 찾아야 하거든.",
                npc,
                ["elder_lost"],
            )
        if npc == "cleaner":
            s["cleaner_count"] += 1
            if topic == "year":
                return self.result("2016년이지요. 2026년이라니 농담이시겠지요. 저는 지금 커피를 청소하고 있습니다.", npc, ["cleaner_lost"])
            if topic in ("greeting", "other") and intent["intent"] not in ("describe", "accept"):
                if s["cleaner_count"] >= 3:
                    hint = " 먼저 옆의 노인과 대화해 분실물 특징을 확인해 주시겠어요?" if not f.get("elder_features") else " 분실물에 관해 필요한 것이 있으면 다시 말씀해 주세요."
                    return self.result("아이고, 손님. 같은 질문은 들었습니다. 커피를 마저 닦아야 하니 잠시 비켜 주시겠어요?" + hint, npc, ["cleaner_lost"])
                s["pending_dialogue"] = "describe_ticket"
                return self.result("무슨 일이세요? 지금은 커피를 청소 중이라 통행이 조금 불편하실 수 있습니다. 분실물을 찾으시면 어떤 모양인지 말씀해 주시겠어요?", npc, ["cleaner_lost"])
            if not f.get("elder_features"):
                hint = (
                    " 옆의 어르신께 먼저 분실물 특징을 여쭤보시겠어요?"
                    if s["cleaner_count"] >= 3
                    else ""
                )
                return self.result(
                    "아이고, 손님. 잃어버린 물건의 모양을 명확히 설명해 주시면 찾아드리겠습니다."
                    + hint,
                    npc,
                    ["cleaner_lost"],
                )
            if (
                intent["intent"] == "accept"
                and s["pending_dialogue"] == "confirm_description"
            ):
                intent = dict(
                    intent,
                    intent="describe",
                    mode="act",
                    affirmed_features=s.get("pending_features", []),
                    denied_features=[],
                    described_item="ticket_old",
                    referent_relation="same",
                )
                s["pending_dialogue"] = "describe_ticket"
                s["pending_features"] = []
                topic = "appearance"
            if intent["intent"] == "describe" or topic == "appearance":
                if intent["mode"] != "act":
                    s["pending_dialogue"] = "describe_ticket"
                    return self.result(
                        "그 물건의 특징을 확인해서 말씀하시는 건가요? 찾으시는 표의 모양을 확실하게 설명해 주시겠어요?",
                        npc,
                        ["cleaner_lost"],
                    )
                # 질문에 답하는 맥락이 없으면, 명사 나열을 확정된 묘사로 승격하지 않는다.
                clause = intent.get("quote", "")
                item = intent.get("described_item", "unknown") or "unknown"
                if item == "unknown" and s["pending_dialogue"] in ("describe_ticket", "confirm_description"):
                    item = "ticket_old"
                if item != "ticket_old" or intent.get("referent_relation") == "different":
                    s["features"] = []
                    s["description_item"] = ""
                    s["pending_features"] = []
                    s["pending_dialogue"] = "describe_ticket"
                    return self.result("그 물건과 어르신의 승차권은 같은 물건인가요? 다른 물건의 특징을 합쳐서는 분실물을 찾기 어렵습니다. 어르신의 표 하나에 해당하는 특징을 말씀해 주시겠어요?", npc, ["cleaner_lost"])
                has_predicate = bool(
                    re.search(
                        r"(?:있(?:어|다|습|는)|뚫렸|맞(?:아|다|습)|(?:종이|표|승차권)(?:예요|에요|입니다|이야)|생겼|바랬|바래졌|변색됐)",
                        clause,
                    )
                )
                if s["pending_dialogue"] != "describe_ticket" and not has_predicate:
                    proposed = set(intent.get("affirmed_features", [])) - set(
                        intent.get("denied_features", [])
                    )
                    s["pending_features"] = sorted(proposed)
                    s["pending_dialogue"] = "confirm_description"
                    return self.result(
                        "말씀하신 특징들이 같은 승차권의 모양이라는 뜻인가요? 그 물건을 찾으시는 것인지 확인해 주시겠어요?",
                        npc,
                        ["cleaner_lost"],
                    )
                if s.get("description_item") not in ("", "ticket_old"):
                    s["features"] = []
                s["description_item"] = "ticket_old"
                features = set(s["features"])
                features.update(intent.get("affirmed_features", []))
                features.difference_update(intent.get("denied_features", []))
                s["features"] = sorted(features)
                s["pending_dialogue"] = "describe_ticket"
                if features == {"faded", "hole"}:
                    self.give(s, "ticket_old")
                    self.mark(
                        s,
                        "ticket_recovered",
                        "청소원에게 두 외형 특징을 설명하고 오래된 승차권을 받았다.",
                    )
                    s["pending_dialogue"] = ""
                    s["features"] = []
                    return self.result(
                        "누렇게 바랜 종이에 구멍이 뚫린 표 말씀이시군요. 여기 있습니다. 어르신의 승차권을 찾아드릴 수 있어 다행입니다.",
                        npc,
                        ["cleaner_lost"],
                    )
                if features == {"faded"}:
                    return self.result(
                        "바랜 종이라면 이 휴지인가요? 더 구별할 만한 특징도 말씀해 주시겠어요?",
                        npc,
                        ["cleaner_lost"],
                    )
                if features == {"hole"}:
                    return self.result(
                        "구멍이 있는 것은 이 영수증도 있네요. 종이는 어떤 모양이었는지 더 알려주시겠어요?",
                        npc,
                        ["cleaner_lost"],
                    )
                return self.result(
                    "말씀하신 특징만으로는 물건을 확정하기 어렵습니다. 어르신께 들은 외형을 다시 설명해 주시겠어요?",
                    npc,
                    ["cleaner_lost"],
                )
            if topic == "year":
                return self.result(
                    "2016년이지요. 2026년이라니 농담이시겠지요. 저는 지금 커피를 청소하고 있습니다.",
                    npc,
                    ["cleaner_lost"],
                )
            if f.get("ticket_recovered"):
                return self.result(
                    "분실물은 이미 찾아드렸습니다. 저는 남은 커피 자국을 정리하겠습니다. 잠시 비켜 주시겠어요?",
                    npc,
                    ["cleaner_lost"],
                )
            s["pending_dialogue"] = "describe_ticket"
            return self.result(
                "승차권을 찾으시는군요. 잃어버린 표의 외형을 구체적으로 말씀해 주시겠어요?",
                npc,
                ["cleaner_lost"],
            )
        if npc == "attendant":
            if topic == "year":
                return self.result("지금이 2026년이라고요? 믿기 어렵습니다. 제 시계는 계속 23시 59분입니다. 그렇다고 승객의 기관실 출입을 바로 허가할 수는 없습니다.", npc, ["attendant_rule"])
            if f.get("engine_permission"):
                return self.result(
                    "도와주셔서 감사합니다. 약속대로 기관실 문을 열어두었습니다. 조심해서 들어가십시오.",
                    npc,
                    ["attendant_help"],
                )
            if topic == "loop":
                self.mark(s, "anomaly_discussed")
                self.mark(s, "mission_offered")
                s["pending_dialogue"] = "crew_help"
                return self.result(
                    "역시 저만 이상하게 느낀 것이 아니었군요. 운행 시간이 지났는데도 도착하지 않고 있습니다. 승무원실의 잠금장치가 고장 났습니다. 문을 열고 운행 서류를 확인해 주시면 기관실로 가도록 돕겠습니다. 부탁드려도 되겠습니까?",
                    npc,
                    ["attendant_rule"],
                )
            if intent["intent"] == "accept" and s["pending_dialogue"] == "crew_help":
                self.mark(
                    s,
                    "mission_accepted",
                    "승무원실을 열고 운행 서류를 찾아달라는 부탁을 수락했다.",
                )
                s["pending_dialogue"] = ""
                return self.result(
                    "감사합니다. 저쪽 관계자 외 출입금지 문이 승무원실입니다. 카드 인식기가 고장 나 있습니다. 문을 열고 서류를 확인해 주십시오.",
                    npc,
                    ["attendant_rule"],
                )
            if topic in ("permission", "help", "stop"):
                if f.get("anomaly_discussed"):
                    self.mark(s, "mission_offered")
                    s["pending_dialogue"] = "crew_help"
                    return self.result(
                        "좋습니다. 대신 잠긴 승무원실 문을 열고 운행 서류를 확인해 주십시오. 도와주시겠습니까?",
                        npc,
                        ["attendant_rule"],
                    )
                s["pending_dialogue"] = "why_engine"
                return self.result(
                    "기관실은 앞쪽에 있지만 승객은 들어갈 수 없습니다. 왜 기관실에 가야 하는지, 이 열차에서 무슨 이상을 보셨는지 말씀해 주십시오.",
                    npc,
                    ["attendant_rule"],
                )
            if f.get("mission_accepted"):
                return self.result(
                    "승무원실을 열고 운행 서류를 확인해 주십시오. 서류를 가져오시면 기관실 출입을 돕겠습니다.",
                    npc,
                    ["attendant_rule"],
                )
            if topic == "year":
                return self.result(
                    "지금이 2026년이라고요? 믿기 어렵습니다. 제 시계는 계속 23시 59분입니다.",
                    npc,
                    ["attendant_rule"],
                )
            return self.result(
                "지금은 위험합니다. 좌석으로 돌아가 주십시오. 도움이 필요하면 말씀하십시오.",
                npc,
                ["attendant_rule"],
            )
        if npc == "driver":
            if f.get("year_proven"):
                return self.result(
                    "증거로 현재가 2026년임을 확인했습니다. 더는 2016년으로 판단하지 않겠습니다. 마지막 입력 기회는 한 번입니다. 제어 장치에서 목적지와 네 자리 비밀번호를 직접 입력하십시오.",
                    npc,
                    ["driver_accept"],
                )
            if topic in ("destination", "password", "help") and f.get("report_read"):
                self.mark(
                    s,
                    "driver_explained",
                    "기관사는 비밀번호가 현재 연도이며 2016 입력에 실패했고 한 번 남았다고 했다.",
                )
                return self.result(
                    "아지산역 분기기는 잠겨 있습니다. 비밀번호는 현재 연도입니다. 2016을 아무리 입력해도 열리지 않았습니다. 이제 한 번만 남았습니다. 지금이 다른 연도라는 말에는 증거가 필요합니다.",
                    npc,
                    ["driver_lock"],
                )
            if topic in ("loop", "stop"):
                return self.result(
                    "저도 같은 선로가 반복되는 것을 알고 있습니다. 레버를 당겨도 이 반복에서 벗어나지 못합니다. 정차 요구만으로 해결되지 않습니다.",
                    npc,
                    ["driver_loop"],
                )
            if topic == "year":
                return self.result(
                    "현재는 2016년입니다. 다른 연도라고 주장하려면 객관적인 자료를 제시하십시오.",
                    npc,
                    ["driver_loop"],
                )
            return self.result(
                "관계자 외 출입금지 구역입니다. 무슨 이유로 오셨습니까?",
                npc,
                ["driver_loop"],
            )
        return self.result("대화 상대를 확인해 주세요.")

    def present(self, s, item, recipient=""):
        if recipient and recipient not in self.available_npcs(s):
            return self.result("그 인물은 현재 장소에 없다. 직접 찾아가야 한다.")
        npc = recipient or s["npc"]
        if item not in s["inventory"]:
            return self.result("보유하지 않은 물건을 보여줄 수 없다.")
        if npc in self.available_npcs(s):
            if s["npc"] != npc:
                s["features"] = []
                s["pending_dialogue"] = ""
            s["npc"] = npc
        if npc == "elder" and s["location"] == "car_3" and item == "ticket_old":
            if s["flags"].get("ticket_returned"):
                return self.result("아이고, 승차권 원본은 아까 돌려받았네. 자네에게 남은 건 그때 확인한 조사 기록이지. 다시 찾을 필요는 없구먼.", npc)
            if not s["flags"].get("old_ticket_read"):
                return self.result(
                    "원본을 돌려드리기 전에 반드시 승차권을 열어 발급 연도와 내용을 확인해야 한다. 보관함에서 오래된 승차권을 열고, 확인한 뒤 반환하자.", ui={"inventory": True}
                )
            self.mark(
                s,
                "ticket_returned",
                "승차권 원본을 노인에게 돌려드리고 조사 기록을 남겼다.",
            )
            return self.result(
                "아이고, 내 승차권을 찾았구먼. 고맙네. 표를 돌려받으니 한결 마음이 놓이네.",
                npc,
                ["elder_lost"],
            )
        if npc == "attendant" and item == "route_report" and s["location"] == "car_4":
            if s["flags"].get("engine_permission"):
                return self.result("보고서 원본은 이미 전달받았습니다. 조사 기록은 계속 확인하셔도 됩니다. 기관실 출입 허가는 그대로입니다.", npc)
            if not s["flags"].get("report_read"):
                return self.result("먼저 서류의 내용을 실제로 확인해야 한다.")
            self.mark(
                s,
                "engine_permission",
                "보고서를 전달하자 승무원이 기관실 출입을 허가했다.",
            )
            return self.result(
                "정말 문을 여셨군요. 서류도 확인했습니다. 감사합니다. 약속대로 기관실로 가실 수 있게 해드리겠습니다.",
                npc,
                ["attendant_help"],
            )
        if npc == "driver" and s["location"] == "engine":
            return self.prepare_evidence(s, item)
        return self.result(
            "이 물건을 이 인물에게 제시해도 새로운 진행 조건은 충족되지 않는다."
        )

    def prepare_evidence(self, s, item):
        if s["location"] != "engine" or not s["flags"].get("driver_explained"):
            return self.result(
                "기관사와 먼저 분기기와 현재 연도에 관한 대화를 해야 한다."
            )
        if s["flags"].get("year_proven"):
            return self.result("현재 연도에 관한 증거는 이미 확인받았다.")
        if item not in s["inventory"]:
            raise GameError(
                "보유하지 않은 물건은 제출할 수 없습니다.", "not_owned", 403
            )
        text = "이 물건을 현재 연도의 증거로 최종 제출합니다. 잘못된 증거이면 이번 탈출 시도는 종료됩니다."
        if item == "newspaper":
            text += " 신문의 과거 사건 기록과 처음부터 소지한 승차권의 연도를 함께 대조합니다."
        s["confirmation"] = {
            "kind": "evidence",
            "token": secrets.token_urlsafe(24),
            "item": item,
            "title": self.config["items"][item]["name"],
            "text": text,
        }
        return self.result(
            "보여줄 자료를 선택했다. 내용을 확인한 뒤 최종 제출 여부를 결정할 수 있다."
        )

    def prepare_control(self, s, destination, password):
        if s["location"] != "engine" or not s["flags"].get("year_proven"):
            return self.result("아직 제어 장치를 조작할 권한이 없다.")
        if not isinstance(destination, str) or not isinstance(password, str):
            raise GameError("목적지와 비밀번호는 문자열로 입력해 주세요.")
        destination = destination.strip()
        password = password.strip()
        if (
            not destination
            or len(destination) > 30
            or re.fullmatch(r"[0-9]{4}", password) is None
        ):
            raise GameError(
                "목적지와 숫자 네 자리 비밀번호를 입력해 주세요. 형식 오류로 기회가 소모되지는 않습니다.",
                "invalid_control",
            )
        if s["attempts"] != 1:
            return self.result("사용할 수 있는 입력 기회가 없다.")
        s["confirmation"] = {
            "kind": "control",
            "token": secrets.token_urlsafe(24),
            "destination": destination,
            "password": password,
            "title": "마지막 분기기 입력",
            "text": "남은 기회는 한 번입니다. 목적지 또는 비밀번호가 틀리면 장치가 잠기고 탈출할 수 없습니다. 이 입력을 최종 확정할까요?",
        }
        return self.result(
            "입력안을 준비했다. 아직 기회는 소모하지 않았다. 마지막 확인 후에만 장치로 전송된다."
        )

    def confirm(self, s, token):
        c = s["confirmation"]
        if (
            not c
            or not isinstance(token, str)
            or not secrets.compare_digest(c["token"], token)
        ):
            raise GameError(
                "유효한 최종 확인이 아닙니다. 현재 화면에서 다시 확인해 주세요.",
                "invalid_confirmation",
                409,
            )
        s["confirmation"] = None
        if c["kind"] == "abandon":
            return self.bad(
                s,
                "abandoned",
                "탈출을 포기한다. 열차는 같은 선로를 끝없이 달리고, 당신은 영원한 승객으로 남는다.",
            )
        if c["kind"] == "evidence":
            if (
                s["location"] != "engine"
                or not s["flags"].get("driver_explained")
                or c["item"] not in s["inventory"]
            ):
                raise GameError("증거 제출 조건이 바뀌었습니다.", "stale_state", 409)
            if c["item"] not in ("ticket_current", "newspaper"):
                return self.bad(
                    s,
                    "wrong_evidence",
                    "기관사는 자료를 밀어놓는다. “이것으로 현재 연도가 달라졌다고 할 수 없습니다. 지금 나가십시오.” 기관실 문이 닫히고 열차는 계속 달린다.",
                )
            self.mark(
                s,
                "year_proven",
                "기관사가 2026년 승차권과 과거 기록의 시간 차이를 인정했다.",
            )
            if "ticket_current" not in s["read"]:
                s["read"].append("ticket_current")
            self.mark(s, "current_ticket_read")
            return self.result(
                "기관사는 승차권의 2026년 표기와 과거 기록을 대조한다. “정말 지금이 2016년이 아니라니 믿기 어렵군요. 증거는 확인했습니다. 마지막 입력을 직접 해보십시오.”",
                "driver", ["driver_accept"],
                ui={"control": True},
            )
        if c["kind"] == "control":
            if (
                s["location"] != "engine"
                or not s["flags"].get("year_proven")
                or s["attempts"] != 1
            ):
                raise GameError(
                    "제어 장치의 입력 조건이 바뀌었습니다.", "stale_state", 409
                )
            s["attempts"] = 0
            if (
                c["destination"] not in ("아지산", "아지산역")
                or c["password"] != "2026"
            ):
                return self.bad(
                    s,
                    "wrong_control",
                    "입력 오류. 분기기 장치에 잠금 표시가 켜진다. 마지막 기회를 모두 사용했다. 열차는 반복되는 본선을 벗어나지 못한다.",
                )
            self.mark(
                s, "route_open", "분기 선로가 열렸다. 열차가 아지산역에 자동 정차했다."
            )
            s["location"] = "platform"
            s["npc"] = ""
            s["pending_dialogue"] = ""
            if "platform" not in s["visited"]:
                s["visited"].append("platform")
            return self.result(
                "분기기 잠금이 풀린다. 창밖의 풍경이 바뀌고 멈췄던 시계의 초침이 움직인다. 열차가 아지산역 승강장에 자동으로 정차한다. 승무원이 부상당한 탐험가를 부축해 합류한다. 문이 열렸고, 이제 함께 내릴 수 있다."
            )
        raise GameError("알 수 없는 최종 확인입니다.")

    def bad(self, s, reason, text):
        s["status"] = "bad"
        s["reason"] = reason
        s["confirmation"] = None
        s["pending_dialogue"] = ""
        return self.result(text)

    def hint(self, s):
        f = s["flags"]
        if not f.get("notice_read"):
            text = "좌석 옆 안내문을 실제로 읽어보자."
        elif not f.get("supplies_received"):
            text = "2호차의 남성과 이야기하고 앞쪽을 조사하겠다는 뜻을 전해보자."
        elif not f.get("light_on"):
            text = "탐험가가 준 도구 중 어둠을 밝힐 수 있는 것을 사용해보자."
        elif not f.get("elder_features"):
            text = "분실물을 찾는 사람에게 외형을 먼저 물어보자."
        elif not f.get("ticket_recovered"):
            text = "노인에게 들은 두 특징을 같은 물건의 모습으로 설명해보자."
        elif not f.get("ticket_returned"):
            text = "승차권 내용을 확인하고 주인에게 돌려주자. 조사 기록은 남는다."
        elif not f.get("destination_hint"):
            text = "승차권을 돌려드렸다면 목적지의 기억을 물어보자."
        elif not f.get("mission_accepted"):
            text = "승무원에게 열차의 이상 현상과 기관실에 갈 필요를 설명하고 부탁을 수락하자."
        elif not f.get("door_open"):
            text = (
                "보관함의 시설 안내서를 읽고 문 옆 장치의 위치와 조작 순서를 확인하자."
            )
        elif not f.get("report_read"):
            text = "열린 승무원실 안 책상에 운행 서류가 있다. 직접 읽어보자."
        elif not f.get("engine_permission"):
            text = "확인한 서류를 승무원에게 보여주자."
        elif not f.get("driver_explained"):
            text = "기관사에게 보고서에서 찾은 목적지로 갈 방법을 물어보자."
        elif not f.get("year_proven"):
            text = "인물의 주장과 실제 발급 기록의 연도를 비교하자. 보관함에서는 열람과 최종 제출을 구분한다."
        elif not f.get("route_open"):
            text = "보고서의 목적지, 기관사의 비밀번호 기준, 자신의 실제 탑승 기록을 종합하자. 최종 기회는 한 번이다."
        else:
            text = "열차가 정차했다. 일행과 함께 승강장으로 내려서자."
        return self.result(text)

    def apply_action(self, s, a):
        if (
            not isinstance(a, dict)
            or not isinstance(a.get("type"), str)
            or a["type"] not in UI_ACTIONS
        ):
            raise GameError("지원하지 않는 화면 조작입니다.")
        kind = a["type"]
        target = a.get("target", "")
        if not isinstance(target, str) or len(target) > 80:
            raise GameError("조작 대상이 올바르지 않습니다.")
        if kind == "look":
            return self.result(self.look(s))
        if kind == "move":
            return self.move(s, target)
        if kind == "disembark":
            return self.move(s, "platform")
        if kind == "select_npc":
            if target not in self.available_npcs(s):
                return self.result("지금은 그 인물을 확인하거나 대화할 수 없다.")
            return self.talk(s, target, "greeting", {"intent": "talk", "mode": "act"})
        if kind == "end_talk":
            return self.end_talk(s)
        if kind == "present":
            recipient = a.get("recipient", "")
            if not isinstance(recipient, str) or recipient not in ("", *self.config["npcs"]):
                raise GameError("물건을 보여줄 상대가 올바르지 않습니다.")
            return self.present(s, target, recipient)
        if kind == "inspect":
            return self.inspect(s, target)
        if kind == "read_report":
            return self.read_report(s)
        if kind == "read_item":
            return self.read_item(s, target)
        if kind == "operate":
            return self.operate(s, target)
        if kind == "use_item":
            if target not in s["inventory"]:
                return self.result("보유하지 않은 물건은 사용할 수 없다.")
            if target == "flashlight":
                if s["location"] != "car_3":
                    return self.result(
                        "손전등은 가지고 있다. 이곳에서는 객차의 시야를 바꿀 필요가 없다."
                    )
                self.mark(
                    s,
                    "light_on",
                    "손전등으로 어두운 3호차를 밝혀 노인과 청소원을 확인했다.",
                )
                return self.result(
                    "손전등을 켜서 어둠 속을 비춘다. 창가의 노인과 커피를 청소하는 직원이 보인다. 누구에게 말을 걸지 선택할 수 있다."
                )
            return self.read_item(s, target)
        if kind == "prepare_evidence":
            return self.prepare_evidence(s, target)
        if kind == "prepare_control":
            return self.prepare_control(s, a.get("destination"), a.get("password"))
        if kind == "confirm":
            return self.confirm(s, a.get("token"))
        if kind == "cancel":
            s["confirmation"] = None
            return self.result("최종 제출을 취소했다. 진행과 마지막 기회는 그대로다.")
        if kind == "abandon":
            s["confirmation"] = {
                "kind": "abandon",
                "token": secrets.token_urlsafe(24),
                "title": "탈출 포기",
                "text": "탈출을 포기하면 영원한 승객 엔딩으로 이번 게임이 종료됩니다. 잠시 쉬려면 창을 닫아 진행을 보관할 수 있습니다. 정말 포기할까요?",
            }
            return self.result(
                "탈출 포기 여부를 확인한다. 아직 게임은 종료되지 않았다."
            )
        if kind == "hint":
            return self.hint(s)
        raise GameError("조작을 확인하지 못했습니다.")

    def apply_intent(self, s, i):
        kind = i["intent"]
        mode = i["mode"]
        target = i["target"]
        if kind == "abandon":
            quote = i.get("quote", "")
            final_clause = re.split(
                r"하지만|그렇지만|그러나|대신|이제는|지금은", quote
            )[-1]
            if re.search(
                r"포기(?:하(?:지|지는|진)|할\s*생각이)\s*(?:않|없)|포기\s*안|그만두지\s*않",
                final_clause,
            ):
                return self.result(
                    "탈출을 포기하지 않겠다는 뜻을 확인했다. 조사를 계속할 수 있다."
                )
            if "포기" not in quote and not re.search(
                r"(?:게임|탈출).{0,12}(?:그만|종료)", quote
            ):
                return self.result(
                    "취소하려는 것이 어떤 행동인지 확인해 주세요. 대화나 설명의 취소는 게임 포기로 처리하지 않았다."
                )
        if mode in ("negated", "reported", "hypothesis", "unclear"):
            if kind == "describe" and mode == "unclear" and s["npc"] == "cleaner":
                return self.talk(s, "cleaner", "appearance", i)
            return self.result(
                "실제 행동이 확정되지 않아 진행은 그대로다. 지금 직접 하려는 행동이나 묻고 싶은 내용을 명확하게 말해 주세요."
            )
        if kind == "talk" or kind == "describe" or kind == "accept":
            npc = (
                target
                if target in self.config["npcs"]
                else (i.get("recipient") or s["npc"])
            )
            if not npc:
                return self.result(
                    "대화할 인물을 골라 주세요. 이름을 말하거나 화면에서 선택할 수 있다."
                )
            return self.talk(s, npc, i["topic"], i)
        if kind == "end_talk":
            return self.end_talk(s)
        if kind == "look":
            return self.result(self.look(s))
        if (
            kind in ("inspect", "use", "operate", "present", "move", "abandon")
            and mode != "act"
        ):
            return self.result(
                "질문이나 추측만으로 물건을 사용하거나 장치를 조작하지 않았다. 실행할 행동을 분명히 말해 주세요."
            )
        if kind == "inspect":
            return self.inspect(s, target)
        if kind == "move":
            if (
                s["location"] == "car_2"
                and target == "car_3"
                and s["flags"].get("explorer_met")
                and not s["flags"].get("supplies_received")
            ):
                return self.talk(s, "explorer", "tools", i)
            return self.move(s, target)
        if kind == "use":
            return self.apply_action(s, {"type": "use_item", "target": target})
        if kind == "operate":
            return self.operate(s, target)
        if kind == "present":
            return self.present(s, target, i.get("recipient", ""))
        if kind == "abandon":
            return self.apply_action(s, {"type": "abandon"})
        if kind == "threat":
            npc = target if target in self.config["npcs"] else s["npc"]
            if npc in self.available_npcs(s):
                s["npc"] = npc
                action = i.get("behavior", "threaten")
                starts = {"push": "밀치는 손에 상대가 한 발 물러서 자세를 바로잡는다. ", "hit": "상대가 몸을 피하며 팔을 막아선다. "}
                lines = {"explorer": "다친 사람한테 그러시면 곤란한데요. 이야기는 계속할 수 있으니 진정해 주세요.", "elder": "아이고, 와 이라노! 밀지 말고 말로 하소.", "cleaner": "손님, 다칠 수 있습니다. 손을 떼 주시겠어요?", "attendant": "뒤로 물러서십시오. 위험한 행동은 그만두십시오.", "driver": "물러서십시오. 제 몸을 밀어도 분기기와 제어 권한은 달라지지 않습니다."}
                return self.result(starts.get(action, "상대가 경계하며 거리를 둔다. ") + lines[npc], npc, ui={"reaction": "guarded", "non_progress": True})
            return self.result(
                "달리는 열차 안에서 위험한 행동을 시도해도 문제는 해결되지 않는다. 시설은 파괴되지 않았고 진행은 그대로다."
            )
        if kind == "impossible":
            return self.result("", ui={"ignored": True})
        if kind == "ambient":
            if i.get("behavior") == "sit" and s["location"] in ("car_1", "car_2", "car_3", "car_4"):
                return self.result("빈 좌석에 잠시 앉아 흔들리는 객차를 살핀다. 다시 일어나 조사를 이어갈 수 있다.", ui={"non_progress": True})
            npc = target if target in self.config["npcs"] else s["npc"]
            if npc in self.available_npcs(s):
                return self.result(self.config["npcs"][npc]["name"] + "이 잠시 시선을 돌려 반응한다. 짧은 몸짓을 주고받은 뒤 이야기를 이어갈 수 있다.", npc, ui={"non_progress": True})
            return self.result("주변을 건드려 보지만 새로운 변화는 없다. 조사하던 곳으로 시선을 돌린다.", ui={"non_progress": True})
        return self.result(
            "말씀하신 의도를 분명하게 이해하지 못했다. 현재 보이는 대상이나 대화 상대를 정해 한 가지 행동으로 말해 주세요."
        )

    def look(self, s):
        loc = s["location"]
        f = s["flags"]
        if loc == "car_1":
            return "텅 빈 좌석과 창문, 좌석 옆 기관실 안내문이 있다. 다음 문은 2호차로 이어진다."
        if loc == "car_2":
            return "젊은 탐험가가 발목을 다친 채 앉아 있다. 옆에는 조사에 쓰던 가방이 있다."
        if loc == "car_3":
            return (
                "손전등 빛에 창가의 노인과 커피를 청소하는 직원이 보인다."
                if f.get("light_on")
                else "불이 꺼져 아무것도 보이지 않는다. 커피 냄새와 청소하는 소리만 느껴진다."
            )
        if loc == "car_4":
            return "승무원이 통로를 지키고 있다. 승무원실 문 옆 카드 인식기는 빨간불을 깜빡인다. 오른쪽 하단에 점검 덮개가 있다."
        if loc == "crew":
            return "작은 책상과 서류 보관함이 있다. 책상 위 운행 관련 서류를 조사할 수 있다."
        if loc == "engine":
            return "기관사 앞에 운전 레버와 분기기 제어 장치가 있다. 시계는 23시 59분을 가리킨다."
        return "아지산역에 열차가 정차했다. 문이 열렸고 일행과 함께 내릴 수 있다."

    def objective(self, s):
        f = s["flags"]
        if s["status"] == "good":
            return "현실로 돌아왔다"
        if s["status"] == "bad":
            return "영원한 승객"
        conditions = [
            ("notice_read", "주변을 확인하고 안내문을 읽기"),
            ("explorer_met", "2호차의 낯선 승객과 대화하기"),
            ("supplies_received", "앞쪽을 조사할 도구 받기"),
            ("light_on", "어두운 객차의 시야 확보"),
            ("elder_features", "인물들과 대화하여 분실물 정보 찾기"),
            ("ticket_recovered", "분실물의 외형을 설명하기"),
            ("ticket_returned", "승차권을 확인하고 주인에게 돌려드리기"),
            ("destination_hint", "노인의 목적지 기억 확인"),
            ("mission_accepted", "승무원에게 출입 필요를 설명하고 부탁 수락"),
            ("door_open", "잠긴 승무원실 문 개방"),
            ("report_read", "운행 서류 직접 조사"),
            ("engine_permission", "서류를 전달하고 출입 허가 받기"),
            ("driver_explained", "기관사에게 운행과 분기기 질문"),
            ("year_proven", "현재 연도를 증명할 자료 검토"),
            ("route_open", "마지막 제어 장치 입력"),
        ]
        return next(
            (label for flag, label in conditions if not f.get(flag)),
            "일행과 함께 승강장으로 하차",
        )

    def public(self, s):
        f = s["flags"]
        loc = s["location"]
        inventory = []
        for item in s["inventory"]:
            meta = self.config["items"][item]
            name = meta["name"]
            if item == "ticket_old" and f.get("ticket_returned"):
                name = "오래된 승차권 조사 기록"
            inventory.append(
                {
                    "id": item,
                    "name": name,
                    "kind": meta["kind"],
                    "stamp": meta["stamp"],
                    "description": meta["description"],
                    "read": item in s["read"],
                }
            )
        places = []
        for key, name in LOCATIONS.items():
            label = name
            if key == "platform":
                label = "아지산역" if f.get("report_read") else "미확인 구역"
            ok, _ = self.can_enter(s, key)
            places.append(
                {
                    "id": key,
                    "name": label,
                    "visited": key in s["visited"],
                    "open": ok,
                    "current": loc == key,
                }
            )
        view = {
            "revision": s["revision"],
            "username": s["username"],
            "status": s["status"],
            "reason": s["reason"],
            "location": {
                "id": loc,
                "name": (
                    "아지산역 · 열린 열차 문" if loc == "platform" else LOCATIONS[loc]
                ),
            },
            "npc": s["npc"],
            "inventory": inventory,
            "map": places,
            "journal": s["journal"],
            "history": [
                {
                    "role": "narrator",
                    "speaker": "차내",
                    "text": self.config["greeting"],
                },
                *s["history"],
            ],
            "objective": self.objective(s),
            "confirmation": deepcopy(s["confirmation"]),
            "bag_hint": (loc == "car_3" and not f.get("light_on"))
            or (loc == "car_4" and f.get("mission_accepted") and not f.get("door_open"))
            or (
                loc == "engine"
                and f.get("driver_explained")
                and not f.get("year_proven")
            ),
            "controls": {
                "door": loc == "car_4" and bool(f.get("mission_accepted")),
                "proof": loc == "engine"
                and bool(f.get("driver_explained"))
                and not f.get("year_proven"),
                "control": loc == "engine"
                and bool(f.get("year_proven"))
                and not f.get("route_open"),
                "exit": bool(f.get("route_open")),
            },
            "door": {
                "cover_open": bool(f.get("cover_open")),
                "lever_down": bool(f.get("lever_down")),
                "open": bool(f.get("door_open")),
            },
            "attempts": s["attempts"] if f.get("driver_explained") else None,
            "conversation": {"active": bool(s["npc"]), "npc": s["npc"], "can_end": bool(s["npc"])},
            "suggestions": self.suggestions(s),
            "clock_running": bool(f.get("route_open")),
        }
        if s["status"] != "playing":
            view["news"] = {
                "label": "GOOD ENDING · 탈출"
                if s["status"] == "good"
                else "BAD ENDING · 영원한 승객",
                "headline": "10년 전 실종된 13-Fri 열차, 기적적으로 발견"
                if s["status"] == "good"
                else "실종 10년째, 13-Fri 열차 여전히 행방 묘연",
                "body": "승객과 승무원들이 2026년 현실로 돌아왔다. 10년 전 사라졌던 열차의 실종 사건이 마침내 끝났다."
                if s["status"] == "good"
                else "열차의 실종 사건은 여전히 해결되지 않았다. 같은 선로 위로 23시 59분의 밤이 다시 찾아온다.",
            }
        return view

    def suggestions(self, s):
        npc, f = s["npc"], s["flags"]
        if npc == "explorer":
            return ["왜 이 열차에 계신가요?", "창밖에서 무엇을 확인했나요?"] if not f.get("supplies_received") else ["다친 발목은 괜찮으세요?", "도착역에 대해 아는 게 있나요?"]
        if npc == "elder":
            return ["잃어버린 승차권은 어떻게 생겼나요?", "마지막으로 표를 본 곳은 어디인가요?"] if not f.get("ticket_returned") else ["하차역 이름이 기억나세요?", "현재가 몇 년이라고 생각하세요?"]
        if npc == "cleaner":
            return ["승차권을 보셨나요?", "어르신께 들은 외형을 직접 설명해 보세요."]
        if npc == "attendant":
            return ["열차가 같은 곳을 반복하고 있어요.", "기관실에 가려면 어떻게 해야 하나요?"] if not f.get("mission_accepted") else ["승무원실 출입문을 확인하겠습니다.", "확인한 운행 서류를 보여드리겠습니다."]
        if npc == "driver":
            return ["분기기는 어떻게 열 수 있나요?", "비밀번호는 무엇을 기준으로 하나요?"] if not f.get("year_proven") else ["마지막 입력 기회가 남아 있나요?"]
        return []


class ChatbotService:
    def __init__(
        self, retriever=None, generator=None, image_selector=None, *, db_path=None
    ):
        self.retriever = retriever or DemoRetriever()
        self.generator = generator or DemoGenerator()
        self.image_selector = image_selector or DemoImageSelector()
        self.config = load_game_config()
        self.engine = GameEngine(self.config)
        self.store = GameStore(db_path)

    def new_game(self, username="사용자"):
        gid, s = self.store.create(username)
        return gid, self.snapshot_from(s)

    def snapshot_from(self, s):
        scene = self.image_selector.scene(s, self.config)
        return {
            "reply": s["history"][-1]["text"]
            if s["history"]
            else self.config["greeting"],
            "image": scene["background"],
            "sources": [],
            "game": self.engine.public(s),
            "scene": scene,
            "ui": {},
        }

    def snapshot(self, gid):
        return self.snapshot_from(self.store.get(gid))

    def generate_response(
        self, user_message: str, username: str = "사용자", character: dict | None = None
    ) -> dict:
        """기존 베이스의 일반 서비스 계약도 유지한다."""
        knowledge = self.retriever.search(user_message)
        character = character or {}
        reply = self.generator.generate(user_message, username, character, knowledge)
        return {
            "reply": reply,
            "image": self.image_selector.select(reply, character),
            "sources": list(dict.fromkeys(k.title for k in knowledge)),
        }

    def process(self, gid, rid, *, message="", action=None, expected=None):
        digest = hashlib.sha256(
            json.dumps(
                {"message": message, "action": action},
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        s, lease, cached = self.store.reserve(gid, rid, digest, expected)
        if cached is not None:
            return cached
        original = deepcopy(s)
        old_revision = s["revision"]
        try:
            if s["status"] != "playing":
                result = self.engine.result(
                    "이 게임은 종료되었다. 엔딩을 확인하거나 새 게임을 시작할 수 있다."
                )
            elif action is not None:
                result = self.engine.apply_action(s, action)
            else:
                context = self.engine.context(s)
                intent = self.generator.interpret(message, context)
                if intent.get("intent") == "describe":
                    intent = grounded_features(intent, message, context)
                result = self.engine.apply_intent(s, intent)
            canonical = result["canonical"]
            reply = canonical
            npc = result["npc"]
            sources = []
            if npc and action is None and not result["ui"].get("non_progress"):
                flags = {k for k, v in s["flags"].items() if v}
                knowledge = self.retriever.search(
                    message, allowed_ids=result["facts"], npc=npc, flags=flags
                )
                character = deepcopy(self.config["npcs"][npc])
                character["_id"] = npc
                character["_runtime"] = {
                    "canonical": canonical,
                    "history": [h for h in original["history"] if h.get("npc") == npc],
                    "destination_known": bool(s["flags"].get("report_read")),
                    "recognized_year": 2026 if npc == "explorer" or (npc == "driver" and s["flags"].get("year_proven")) else 2016,
                    "mood": "협조적"
                    if s["flags"].get("engine_permission") and npc == "attendant"
                    else "원래 성격 유지",
                }
                reply = self.generator.generate(
                    message, s["username"], character, knowledge
                )
                reply = approved_reply(reply, canonical, npc)
                sources = [k.title for k in knowledge]
            if npc:
                s["expression"] = result["ui"].get("reaction", self.expression(s, npc, canonical))
            if not s["flags"].get("report_read") and "아지산" in canonical:
                raise RuntimeError("Premature destination disclosure")
            speaker = self.config["npcs"][npc]["name"] if npc else "차내"
            ignored = result["ui"].get("ignored", False)
            if message and not ignored:
                s["history"].append(
                    {
                        "role": "user",
                        "speaker": s["username"],
                        "npc": npc,
                        "text": message,
                    }
                )
            if not ignored:
                s["history"].append({
                    "role": "npc" if npc else "narrator",
                    "speaker": speaker,
                    "npc": npc,
                    "text": reply,
                    "record": canonical if npc and canonical != reply else "",
                })
            s["history"] = s["history"][-240:]
            s["revision"] = old_revision + 1
            response = self.snapshot_from(s)
            response.update(reply=reply, sources=sources, ui=result["ui"])
            new_items = [
                {"id": i, "name": self.config["items"][i]["name"], "kind": self.config["items"][i]["kind"], "stamp": self.config["items"][i]["stamp"]}
                for i in s["inventory"]
                if i not in original["inventory"]
            ]
            response["events"] = [
                {"type": "item_acquired", "item": x, "event_id": str(s["revision"]) + ":" + x["id"]} for x in new_items
            ]
            if original["status"] != s["status"]:
                response["events"].append({"type": "ending", "value": s["status"]})
            self.store.commit(gid, rid, digest, lease, old_revision, s, response)
            return response
        except Exception:
            self.store.release(gid, lease)
            raise

    @staticmethod
    def expression(s, npc, canonical):
        f = s["flags"]
        if npc == "explorer":
            return "animated"
        if npc == "elder":
            return "relieved" if f.get("ticket_returned") else "neutral"
        if npc == "cleaner":
            return "asking" if s["pending_dialogue"] or not f.get("ticket_recovered") else "neutral"
        if npc == "attendant":
            return "neutral" if f.get("engine_permission") else "guarded"
        if npc == "driver":
            return "surprised" if f.get("year_proven") else "neutral"
        return "neutral"
