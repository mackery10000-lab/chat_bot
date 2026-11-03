"""Remove disposable local QA profiles/copies; keep saves, source art and reports.

Preview: runtime/python.exe tools/clean_generated.py
Apply after browsers exit: runtime/python.exe tools/clean_generated.py --apply
"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import shutil
import sqlite3
import stat

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
PROFILES = (
    "qa-chrome-profile",
    "driver-console-qa/chrome-profile",
    "inventory-audio-qa/chrome-profile",
    "registered-qa/chrome-profile",
)


def checked_target(path):
    resolved = path.resolve(strict=True)
    resolved.relative_to(LOCAL.resolve(strict=True))
    if resolved == LOCAL.resolve() or path.is_symlink():
        raise ValueError(f"Unsafe cleanup target: {path}")
    # Refuse junctions too, so a disposable folder cannot redirect outside .local.
    for child in [path, *path.rglob("*")]:
        attributes = getattr(child.lstat(), "st_file_attributes", 0)
        if child.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"Cleanup target contains a link: {child}")
    return resolved


def disposable_copy(folder):
    game = folder / "13Fri"
    if not all((game / name).is_file() for name in
               ("launch_game.py", "runtime/python.exe", "templates/chat.html")):
        return False
    if any(path.is_file() for path in game.glob(".env*")):
        return False
    database = game / "data/train_state.sqlite3"
    if database.exists():
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            if db.execute("SELECT count(*) FROM games").fetchone()[0]:
                return False
    return True


def candidates():
    if not LOCAL.is_dir():
        return
    for name in PROFILES:
        path = LOCAL / name
        if path.is_dir():
            yield path
    for folder in LOCAL.iterdir():
        if folder.is_dir() and re.fullmatch(r"배포본 검수 \d+", folder.name):
            if disposable_copy(folder):
                yield folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = {"applied": args.apply, "removed_bytes": 0, "entries": []}
    for path in candidates():
        resolved = checked_target(path)
        size = sum(file.stat().st_size for file in resolved.rglob("*") if file.is_file())
        entry = {"path": path.relative_to(ROOT).as_posix(), "bytes": size}
        if args.apply:
            try:
                shutil.rmtree(resolved)
                report["removed_bytes"] += size
                entry["removed"] = True
            except OSError as error:
                entry.update(removed=False, error=str(error))
        report["entries"].append(entry)
    output = LOCAL / "generated-cleanup.json"
    if LOCAL.is_dir():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if any(entry.get("removed") is False for entry in report["entries"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
