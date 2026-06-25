from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    enriched = {"recorded_ts": now_iso(), **record}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, sort_keys=True, default=str) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} line {i} is not valid JSON: {exc}") from exc
    return out


def write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def latest_id(prefix: str, records: Iterable[dict[str, Any]], key: str) -> int:
    nums = []
    for rec in records:
        val = str(rec.get(key, ""))
        if val.startswith(prefix + "_"):
            try:
                nums.append(int(val.rsplit("_", 1)[1]))
            except Exception:  # noqa: BLE001
                pass
    return max(nums) if nums else 0
