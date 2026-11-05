"""장소·시야·대화 상태로 배경·표정·화면 내 조사점을 고른다."""

import json
from pathlib import Path


REGISTRATIONS = json.loads(
    (Path(__file__).resolve().parents[1]
     / "public/assets/images/scenes/registration.json").read_text(encoding="utf-8")
)

# Door outlines use the same full-canvas coordinates as their source backgrounds.
# The engine view faces the controls and has no visible doorway to register.
DOOR_OUTLINES = {
    "car_1": {
        "polygon": [[46.01, 32.62], [54.56, 32.62], [54.85, 33.24],
                    [54.85, 59.71], [54.49, 60.07], [46.01, 60.07],
                    [45.72, 59.54], [45.72, 33.24]],
    },
    "car_2": {
        "polygon": [[53.93, 33.84], [60.89, 33.84], [61.21, 34.31],
                    [61.21, 60.42], [60.89, 60.89], [53.68, 60.89],
                    [53.44, 60.42], [53.44, 34.31]],
    },
    "car_3": {
        "polygon": [[46.07, 37.72], [54.26, 37.72], [54.68, 38.35],
                    [54.68, 68.67], [54.35, 69.05], [46.07, 69.05],
                    [45.65, 68.55], [45.65, 38.35]],
    },
    "car_4": REGISTRATIONS["crew-door.crew_door"],
    "crew": {
        "polygon": [[45.08, 35.85], [55.61, 35.85], [56.07, 36.42],
                    [56.07, 68.39], [55.67, 68.82], [45.08, 68.82],
                    [44.68, 68.39], [44.68, 36.42]],
    },
}


class DemoImageSelector:
    def select(self, reply: str, character: dict) -> str | None:
        return character.get("_runtime", {}).get("scene_image")

    def scene(self, state: dict, config: dict, *, allowed_moves=()) -> dict:
        location, flags = state["location"], state["flags"]
        backgrounds = {"car_1": "car1/background.png", "car_2": "scenes/car2.png", "car_3": "scenes/car3.png", "car_4": "scenes/crew-door.png", "crew": "scenes/crew.png", "engine": "scenes/engine.png"}
        sizes = {location: REGISTRATIONS[key]["size"] for location, key in {
            "car_1": "car1.window", "car_2": "car2.explorer", "car_3": "car3.cleaner",
            "car_4": "crew-door.crew_door", "crew": "crew.report", "engine": "engine.control",
        }.items()}
        dark = location == "car_3" and not flags.get("light_on")
        people = []
        placements = {"explorer": [8, 20, 39, 80], "elder": [7, 17, 40, 83], "cleaner": [60, 11, 34, 89], "attendant": [-6, 4, 48, 106], "driver": [13, 16, 34, 84]}
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
            door_target = {"car_1": "car_2", "car_2": "car_3", "car_3": "car_4",
                           "car_4": "crew", "crew": "engine"}.get(location)
            door_available = not dark and door_target in allowed_moves
            if location == "car_1":
                registered("notice", "안내문 살펴보기", "car1.notice", "inspect", "notice")
                registered("window", "창밖 살펴보기", "car1.window", "inspect", "window")
            elif location == "car_4" and flags.get("mission_accepted") and not door_available:
                registered("crew_door", "승무원실 출입문 확인", "crew-door.crew_door", "focus", "door")
                registered("inspection_cover", "오른쪽 하단 점검 덮개 확인", "crew-door.inspection_cover", "focus", "door")
                registered("door_handle", "문손잡이 확인", "crew-door.door_handle", "focus", "door")
            elif location == "crew":
                registered("report", "책상 위 운행 서류 읽기", "crew.report", "read_report")
                registered("desk", "책상 위 기록 살펴보기", "crew.desk", "inspect", "desk")
            elif location == "engine":
                registered("control", "분기기 제어 장치 확인", "engine.control", "focus", "control")
                registered("engine_lever", "제어 장치 레버 확인", "engine.engine-lever", "focus", "control")
            if door_available:
                polygon = DOOR_OUTLINES[location]["polygon"]
                xs, ys = zip(*polygon)
                bounds = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
                destination = {"car_2": "2호차", "car_3": "3호차", "car_4": "4호차",
                               "crew": "승무원실", "engine": "기관실"}[door_target]
                point("door_to_" + door_target, destination + "로 이동", bounds,
                      "move", door_target, polygon=polygon,
                      background="/assets/images/" + backgrounds[location])
        width, height = sizes[location]
        return {"background": "/assets/images/" + backgrounds[location], "aspect_ratio": f"{width} / {height}", "dark": dark, "light_mode": "dark" if dark else "flashlight" if location == "car_3" else "normal", "people": people, "hotspots": points, "arrived": bool(flags.get("route_open")), "ending": state["status"]}
