"""Small JSON log of produced/published reels, used to avoid repeating themes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def append(path: Path, entry: dict) -> None:
    items = load(path)
    entry = {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    items.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update(path: Path, reel_dir: str, **fields) -> None:
    items = load(path)
    for item in reversed(items):
        if item.get("dir") == reel_dir:
            item.update(fields)
            break
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recent(path: Path, n: int = 30) -> list[dict]:
    return load(path)[-n:]
