"""Export exact server-authored records for the bitmap printing step."""
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from services.chatbot_service import GameEngine, load_game_config


def main():
    config = load_game_config()
    engine = GameEngine(config)
    state = {"inventory": list(config["items"]), "flags": {}}
    records = []
    for item in config["items"]:
        if item != "elder_testimony":
            records.append(engine.document(state, item))
    for appearance, destination in ((False, False), (True, False), (False, True), (True, True)):
        state["flags"] = {"elder_features": appearance, "destination_hint": destination}
        records.append(engine.document(state, "elder_testimony"))
    state["flags"] = {"ticket_returned": True}
    records.append(engine.document(state, "ticket_old"))
    # Safe fallback for tools/old saved previews without an artwork field.
    empty = dict(records[6], artwork="/assets/images/inventory/records/elder-testimony.png")
    records.append(empty)
    actions = {
        "confirm-report": "보고서 내용 확인", "use-flashlight": "손전등 사용",
        "return-ticket": "노인에게 원본 돌려드리기", "show-ticket-record": "노인에게 조사 기록 보여주기",
        "show-route-report": "승무원에게 보고서 보여주기", "submit-evidence": "이 물건을 최종 증거로 제출",
        "inventory-back": "소지품 펼쳐 보기", "previous": "이전", "next": "다음",
        "confirm-final": "최종 확정", "cancel-review": "취소하고 다시 살펴보기",
        "abandon-final": "탈출을 포기한다",
    }
    target = BASE / "public/assets/images/inventory/print-source.json"
    target.write_text(json.dumps({"records": records, "actions": actions}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(records)} records and {len(actions)} button labels.")


if __name__ == "__main__":
    main()
