"""NPC와 진행 조건을 먼저 제한한 뒤 허용된 사실을 검색한다."""

from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class KnowledgeHit:
    title: str
    content: str


class DemoRetriever:
    def __init__(self, path=None):
        self.path = (
            Path(path)
            if path
            else Path(__file__).resolve().parents[1] / "data/knowledge/example_lore.md"
        )

    def search(
        self, question: str, *, allowed_ids=None, npc=None, flags=None
    ) -> list[KnowledgeHit]:
        # 일반 공개 검색 요청에는 시나리오 전체를 돌려주지 않는다.
        if allowed_ids is None or npc is None:
            return []
        text = self.path.read_text(encoding="utf-8")
        chunks = re.split(r"<!-- fact: (.*?) -->\s*", text, flags=re.S)
        hits = []
        enabled = set(flags or [])
        for i in range(1, len(chunks) - 1, 2):
            meta = json.loads(chunks[i])
            if (
                meta["id"] not in allowed_ids
                or npc not in meta["npcs"]
                or not set(meta["requires"]).issubset(enabled)
            ):
                continue
            heading, _, content = chunks[i + 1].strip().partition("\n")
            hits.append(
                KnowledgeHit(heading.removeprefix("## ").strip(), content.strip())
            )
        return hits[:3]
