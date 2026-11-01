"""장소·시야·대화 상태로 배경·표정·화면 내 조사점을 고른다."""


class DemoImageSelector:
    def select(self, reply: str, character: dict) -> str | None:
        return character.get("_runtime", {}).get("scene_image")

    def scene(self, state: dict, config: dict) -> dict:
        location, flags = state["location"], state["flags"]
        backgrounds = {"car_1": "scene_01.png", "car_2": "scene_05.png", "car_3": "scene_06.png", "car_4": "scene_07.png", "crew": "scene_02.png", "engine": "scene_03.png", "platform": "scene_04.png"}
        if location == "car_4" and flags.get("door_open"):
            backgrounds["car_4"] = "scene_08.png"
        dark = location == "car_3" and not flags.get("light_on")
        people = []
        placements = {"explorer": [8, 20, 39, 80], "elder": [7, 17, 40, 83], "cleaner": [60, 11, 34, 89], "attendant": [18, 6, 32, 94], "driver": [7, 9, 38, 91]}
        if not dark and state["status"] == "playing" and not flags.get("route_open"):
            for npc_id, npc in config["npcs"].items():
                if npc["location"] != location:
                    continue
                active = state["npc"] == npc_id
                expression = state.get("expression", "neutral") if active else ("guarded" if npc_id == "attendant" and not flags.get("engine_permission") else "relieved" if npc_id == "elder" and flags.get("ticket_returned") else "neutral")
                filename = npc.get("expressions", {}).get(expression, npc["image"])
                people.append({"id": npc_id, "name": npc["name"], "image": "/assets/images/" + filename, "active": active, "expression": expression, "bounds": placements[npc_id]})
        points = []

        def point(key, label, bounds, kind, target="", **extra):
            points.append({"id": key, "label": label, "bounds": bounds, "kind": kind, "target": target, **extra})

        if state["status"] == "playing" and not state["npc"]:
            if location == "car_1":
                point("notice", "안내문 살펴보기", [38, 38, 7, 11], "inspect", "notice", appearance="paper")
                point("window", "창밖 살펴보기", [5, 15, 21, 34], "inspect", "window")
            elif location == "car_2":
                point("window", "창밖 살펴보기", [67, 20, 23, 20], "inspect", "window")
            elif location == "car_4":
                point("crew_door", "승무원실 출입문 확인", [68, 12, 21, 73], "focus", "door")
                point("inspection_cover", "오른쪽 하단 점검 덮개 확인", [79.5, 63, 7, 14], "focus", "door")
            elif location == "crew":
                point("report", "책상 위 운행 서류 읽기", [27, 56, 14, 8], "read_report")
                point("desk", "책상 살펴보기", [48, 58, 16, 9], "inspect", "desk")
            elif location == "engine":
                point("control", "분기기 제어 장치 확인", [58, 59, 11, 12], "focus", "control", appearance="control")
            elif location == "platform":
                point("exit", "일행과 함께 하차", [52, 47, 24, 35], "disembark")
        return {"background": "/assets/images/" + backgrounds[location], "dark": dark, "light_mode": "dark" if dark else "flashlight" if location == "car_3" else "normal", "people": people, "hotspots": points, "arrived": bool(flags.get("route_open")), "ending": state["status"]}
