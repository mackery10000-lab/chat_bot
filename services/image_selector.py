"""장소·시야·대화 상태로 배경·표정·화면 내 조사점을 고른다."""

import json
from pathlib import Path


REGISTRATIONS = json.loads(
    (Path(__file__).resolve().parents[1]
     / "public/assets/images/scenes/registration.json").read_text(encoding="utf-8")
)


class DemoImageSelector:
    def select(self, reply: str, character: dict) -> str | None:
        return character.get("_runtime", {}).get("scene_image")

    def scene(self, state: dict, config: dict) -> dict:
        location, flags = state["location"], state["flags"]
        backgrounds = {"car_1": "car1/background.png", "car_2": "scenes/car2.png", "car_3": "scenes/car3.png", "car_4": "scenes/crew-door.png", "crew": "scenes/crew.png", "engine": "scenes/engine.png", "platform": "scene_04.png"}
        sizes = {location: REGISTRATIONS[key]["size"] for location, key in {
            "car_1": "car1.window", "car_2": "car2.explorer", "car_3": "car3.cleaner",
            "car_4": "crew-door.crew_door", "crew": "crew.report", "engine": "engine.control",
        }.items()}
        sizes["platform"] = [3, 2]
        dark = location == "car_3" and not flags.get("light_on")
        people = []
        placements = {"explorer": [8, 20, 39, 80], "elder": [7, 17, 40, 83], "cleaner": [60, 11, 34, 89], "attendant": [2, 16, 29, 84], "driver": [13, 16, 34, 84]}
        if not dark and state["status"] == "playing" and not flags.get("route_open"):
            for npc_id, npc in config["npcs"].items():
                if npc["location"] != location:
                    continue
                active = state["npc"] == npc_id
                expression = state.get("expression", "neutral") if active else ("guarded" if npc_id == "attendant" and not flags.get("door_open") else "relieved" if npc_id == "elder" and flags.get("ticket_returned") else "neutral")
                filename = npc.get("expressions", {}).get(expression, npc["image"])
                person = {"id": npc_id, "name": npc["name"], "image": "/assets/images/" + filename, "active": active, "expression": expression, "bounds": placements[npc_id]}
                key = {"explorer": "car2.explorer", "elder": "car3.elder", "cleaner": "car3.cleaner"}.get(npc_id)
                if key:
                    person["registration"] = REGISTRATIONS[key]
                    person["bounds"] = REGISTRATIONS[key]["bounds"]
                people.append(person)
        points = []

        def point(key, label, bounds, kind, target="", **extra):
            points.append({"id": key, "label": label, "bounds": bounds, "kind": kind, "target": target, **extra})

        def registered(key, label, art, kind, target=""):
            registration = REGISTRATIONS[art]
            point(key, label, registration["bounds"], kind, target,
                  image=registration["image"], registration=registration)

        if state["status"] == "playing" and not state["npc"]:
            if location == "car_1":
                registered("notice", "안내문 살펴보기", "car1.notice", "inspect", "notice")
                registered("window", "창밖 살펴보기", "car1.window", "inspect", "window")
            elif location == "car_4" and flags.get("mission_accepted"):
                registered("crew_door", "승무원실 출입문 확인", "crew-door.crew_door", "focus", "door")
                registered("inspection_cover", "오른쪽 하단 점검 덮개 확인", "crew-door.inspection_cover", "focus", "door")
                registered("door_handle", "문손잡이 확인", "crew-door.door_handle", "focus", "door")
            elif location == "crew":
                registered("report", "책상 위 운행 서류 읽기", "crew.report", "read_report")
                registered("desk", "책상 위 기록 살펴보기", "crew.desk", "inspect", "desk")
            elif location == "engine":
                registered("control", "분기기 제어 장치 확인", "engine.control", "focus", "control")
                registered("engine_lever", "제어 장치 레버 확인", "engine.engine-lever", "focus", "control")
            elif location == "platform":
                point("exit", "일행과 함께 하차", [52, 47, 24, 35], "disembark")
        width, height = sizes[location]
        return {"background": "/assets/images/" + backgrounds[location], "aspect_ratio": f"{width} / {height}", "dark": dark, "light_mode": "dark" if dark else "flashlight" if location == "car_3" else "normal", "people": people, "hotspots": points, "arrived": bool(flags.get("route_open")), "ending": state["status"]}
