"""Local conftest for Discovery Triage tests.

Puts this directory on sys.path so sibling test helpers (e.g. ``fixtures.py``)
can be imported as top-level modules WITHOUT marking the whole ``tests/`` tree
as a package (which would change collection/importmode for tests/loop/)."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
