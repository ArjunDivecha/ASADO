"""Before network I/O, require the still-live owner of this exact monthly claim.

Input only: ASADO/Data/monthly/attempts/YYYY-MM.json and parent PID. No file writes,
signals or provider calls. Killed/interrupted parents cannot leave a collector
issuing new requests. Staging readers can still be tested offline independently.
"""
from datetime import datetime
import os
from pathlib import Path
from monthly_readiness import read, PACIFIC


def assert_owner(c):
    owner = int(os.environ.get('ASADO_MONTHLY_LOCK_OWNER', '0'))
    rec = read(Path(c['root']) / f"Data/monthly/attempts/{c['month']}.json", {})
    if not owner or rec.get('pid') != owner or rec.get('run') != c['run'] or rec.get('state') != 'RUNNING':
        raise RuntimeError('Monthly network owner/claim no longer active; stop without retry')
    try:
        os.kill(owner, 0)  # Existence check only; does not deliver a signal.
    except ProcessLookupError as exc:
        raise RuntimeError('Monthly parent is gone; no new requests') from exc
    if datetime.now(PACIFIC).strftime('%Y-%m') != c['month']:
        raise RuntimeError('Month rolled over; no provider work for an old claim')
