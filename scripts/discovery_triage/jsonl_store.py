"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/jsonl_store.py
=============================================================================

DESCRIPTION:
Concurrency-safe append-only JSONL persistence for the ASADO Discovery Triage
Court. All durable Court records (research looks, detector drafts, claims, etc.)
are append-only event streams; this module guarantees that ID minting and the
append happen inside ONE `fcntl.flock`-guarded critical section so parallel
writers cannot mint duplicate IDs or interleave torn lines (the Sakana/Fugu
review flagged that a temp-file + os.replace strategy is WRONG for append-only
ledgers — it loses concurrent appends). Per-object frozen artifacts (YAML/JSON)
are not append-only and may still use atomic temp-file + os.replace.

INPUT/OUTPUT FILES:
- This is a library module. It does not own fixed paths; callers pass the target
  JSONL/JSON file path. Append-only ledgers it is used for include (absolute):
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO_worktrees/claude-kahuna/journal/looks/research_looks.jsonl
    .../journal/drafts/detector_drafts.jsonl
    .../journal/claims/claims.jsonl
  A sibling lock file `<path>.lock` is created next to each ledger.

VERSION: 1.1 (PR-1: lock-protected append + minting, tz-aware timestamps)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: standard library only (fcntl, json, os, tempfile, datetime).
=============================================================================
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


def now_iso() -> str:
    """Timezone-aware local-offset ISO timestamp, e.g. 2026-06-25T11:30:00-07:00.

    FuguPRD §11.3 examples carry an offset; a tz-naive stamp sorts/round-trips
    incorrectly across the ledgers, so we always emit the local UTC offset.
    """
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@contextmanager
def _exclusive(path: Path) -> Iterator[None]:
    """Hold an exclusive advisory lock for the duration of a critical section.

    The lock lives in a sibling `<name>.lock` file so the data file itself is
    only ever opened for the brief append.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    import fcntl  # local import: POSIX-only, keeps module importable for inspection

    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _append_line(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON line with O_APPEND semantics and fsync. Caller holds lock."""
    with path.open("a", encoding="utf-8") as f:  # "a" => O_APPEND
        f.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


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


def append_jsonl(
    path: Path,
    record: dict[str, Any],
    *,
    validate: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Append a record that already carries its own ID (e.g. a readout).

    Stamps `recorded_ts`, optionally validates (BEFORE writing, so a rejected
    record never touches the file), then appends under an exclusive lock.
    """
    enriched = {"recorded_ts": now_iso(), **record}
    with _exclusive(path):
        if validate is not None:
            validate(enriched)
        _append_line(path, enriched)
    return enriched


def latest_id(prefix: str, records: Iterable[dict[str, Any]], key: str) -> int:
    """Highest trailing NNN among records with this prefix (any day). Retained for
    callers that want a global max; `next_id` is the per-day minter used on write."""
    nums: list[int] = []
    for rec in records:
        val = str(rec.get(key, ""))
        if val.startswith(prefix + "_"):
            try:
                nums.append(int(val.rsplit("_", 1)[1]))
            except Exception:  # noqa: BLE001
                pass
    return max(nums) if nums else 0


def next_id(prefix: str, records: Iterable[dict[str, Any]], key: str) -> str:
    """Mint PREFIX_YYYYMMDD_NNN, incrementing NNN within TODAY (FuguPRD §3.1)."""
    today = datetime.now().strftime("%Y%m%d")
    best = 0
    for rec in records:
        val = str(rec.get(key, ""))
        if not val.startswith(prefix + "_"):
            continue
        parts = val.split("_")
        if len(parts) >= 3 and parts[-2] == today:
            try:
                best = max(best, int(parts[-1]))
            except ValueError:
                pass
    return f"{prefix}_{today}_{best + 1:03d}"


def append_with_minted_id(
    path: Path,
    prefix: str,
    id_key: str,
    build_record: Callable[[str], dict[str, Any]],
    *,
    validate: Callable[[dict[str, Any]], Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Mint an ID and append the built record as ONE critical section.

    `(read existing rows -> mint id -> build -> validate -> append+fsync)` all
    happen while holding the exclusive lock, so concurrent writers never collide
    on an ID. If `validate` raises, nothing is written and the file is left intact.
    """
    with _exclusive(path):
        rows = read_jsonl(path)
        new_id = next_id(prefix, rows, id_key)
        record = build_record(new_id)
        record.setdefault(id_key, new_id)
        record = {"recorded_ts": now_iso(), **record}
        if validate is not None:
            validate(record)
        _append_line(path, record)
    return new_id, record


def atomic_write_text(path: Path, text: str) -> None:
    """L4 (red-team 2026-06-26): atomic text write (temp-file + fsync + os.replace)
    for per-object YAML artifacts, so a crash mid-write can't leave a torn file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path: Path, record: dict[str, Any]) -> None:
    """Atomically write a single frozen object (NOT append-only): temp-file +
    os.replace in the same directory. Safe for per-object YAML/JSON artifacts."""
    atomic_write_text(path, json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
