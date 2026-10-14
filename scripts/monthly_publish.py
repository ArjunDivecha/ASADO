"""Journaled, reversible monthly publication; no collection or implicit retries.

Inputs: verified staged files + original backup manifest under
/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/monthly/runs/<run>/.
Outputs: publication.jsonl there, approved ASADO/Data/ and
/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 NN/{production,Data/live}/ files.
Caller must hold producer/repair/NN locks. Roots are injectable for isolated tests.
"""
import os
import shutil
from pathlib import Path
from monthly_readiness import sha, read, atomic, append


def allowed(path, roots):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f"Publication target is a symlink: {path}")
    resolved = path.resolve()
    if not any(resolved.is_relative_to(Path(r).resolve()) for r in roots):
        raise RuntimeError(f"Publication outside approved roots: {path}")
    return path


def backup(paths, directory, roots):
    """Backup every possible target before collection. Never replace a backup."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    rows = {}
    for i, path in enumerate(sorted(set(map(str, paths)))):
        p = allowed(path, roots)
        row = dict(destination=str(p), existed=p.exists(), before_sha256=None, backup=None)
        if p.exists():
            if not p.is_file():
                raise RuntimeError(f"Expected regular file: {p}")
            stat = p.stat()
            dest = directory / f"{i:04d}_{p.name}"
            shutil.copy2(p, dest)
            digest = sha(p)
            if sha(dest) != digest or (p.stat().st_size, p.stat().st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                raise RuntimeError(f"Backup mismatch/source changed: {p}")
            row.update(before_sha256=digest, backup=str(dest))
        rows[str(p)] = row
        atomic(directory / "manifest.json", rows)
    return rows


def fsync_dir(path):
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(plan, originals, journal, roots, fault=None):
    """PREPARED before replacement handles crashes between rename and receipt.

    The fault callback is only supplied by isolated tests. All targets, before
    states and staged digests are verified before the first canonical write.
    """
    seen = set()
    for row in plan:
        dest = allowed(row["destination"], roots)
        if str(dest) in seen or str(dest) not in originals:
            raise RuntimeError(f"Duplicate/unbacked publication target: {dest}")
        seen.add(str(dest))
        orig = originals[str(dest)]
        if (sha(dest) if dest.exists() else None) != orig["before_sha256"]:
            raise RuntimeError(f"Canonical target changed since backup: {dest}")
        if sha(row["source"]) != row["sha256"]:
            raise RuntimeError(f"Staged output changed: {row['source']}")
    try:
        for i, row in enumerate(plan):
            dest = Path(row["destination"])
            orig = originals[str(dest)]
            event = dict(event="PREPARED", **row, **{k: orig[k] for k in ("existed", "before_sha256", "backup")})
            append(journal, event)
            if fault:
                fault("before_replace", i)
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_name(dest.name + ".asado-monthly.tmp")
            if temp.exists():
                raise RuntimeError(f"Unreconciled publication temporary: {temp}")
            shutil.copy2(row["source"], temp)
            with temp.open("rb") as f:
                os.fsync(f.fileno())
            if sha(temp) != row["sha256"]:
                raise RuntimeError(f"Publication copy mismatch: {dest}")
            os.replace(temp, dest)
            fsync_dir(dest.parent)
            if fault:
                fault("after_replace", i)
            append(journal, {"event": "REPLACED", "destination": str(dest), "sha256": row["sha256"]})
    except BaseException:
        rollback(journal, roots)
        raise


def rollback(journal, roots):
    """Restore only our known before/new bytes. Never clobber a later writer."""
    journal = Path(journal)
    if not journal.exists():
        return
    import json
    events = [json.loads(line) for line in journal.read_text().splitlines() if line]
    prepared = [r for r in events if r.get("event") == "PREPARED"]
    # Check all conflicts before restoring any target.
    for row in prepared:
        dest = allowed(row["destination"], roots)
        current = sha(dest) if dest.exists() else None
        if current not in (row["sha256"], row["before_sha256"]):
            raise RuntimeError(f"Rollback blocked by later writer: {dest}")
        if row["existed"] and sha(row["backup"]) != row["before_sha256"]:
            raise RuntimeError(f"Rollback backup changed: {dest}")
    for row in reversed(prepared):
        dest = Path(row["destination"])
        current = sha(dest) if dest.exists() else None
        if current == row["before_sha256"]:
            continue
        if row["existed"]:
            temp = dest.with_name(dest.name + ".asado-rollback.tmp")
            shutil.copy2(row["backup"], temp)
            os.replace(temp, dest)
        elif dest.exists():
            dest.unlink()
        fsync_dir(dest.parent)
        append(journal, {"event": "ROLLED_BACK", "destination": str(dest)})
    for row in prepared:
        temp = Path(row["destination"]).with_name(Path(row["destination"]).name + ".asado-monthly.tmp")
        if temp.exists():
            if sha(temp) != row["sha256"]:
                raise RuntimeError(f"Unknown interrupted temporary: {temp}")
            temp.unlink()
