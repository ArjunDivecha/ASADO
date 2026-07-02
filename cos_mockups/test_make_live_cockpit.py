#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: test_make_live_cockpit.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/make_live_cockpit.py
    The generator under test (run as a subprocess).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit.html
    The scripted mock the generator transforms.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit_live.html
    Regenerated as a side effect of running the generator (its normal output).

VERSION: 1.0
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha / Claude Code

DESCRIPTION:
Generation-parity test for the live cockpit (frontend audit 2026-07-01,
priority item 3 / red-team AC13). make_live_cockpit.py works by string
surgery on anchors in cockpit.html; if an anchor drifts, a replacement can
silently no-op and ship a page that calls undefined functions (the setHor
bug) or recites mock narration. This test runs the generator and asserts:
  1. it exits 0 (its internal parity check passed),
  2. every function referenced by generated onclick= handlers is defined,
  3. no scripted mock narration survives into the live page.

DEPENDENCIES:
- pytest (standard library otherwise)

USAGE:
  source venv/bin/activate
  pytest cos_mockups/test_make_live_cockpit.py -v
=============================================================================
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "make_live_cockpit.py"
LIVE = HERE / "cockpit_live.html"


@pytest.fixture(scope="module")
def live_html() -> str:
    """Run the generator once for the module; fail the suite if it fails."""
    proc = subprocess.run(
        [sys.executable, str(GENERATOR)], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, f"generator failed:\n{proc.stdout}\n{proc.stderr}"
    return LIVE.read_text()


def test_generator_parity_gate_passes(live_html):
    assert "window.COCKPIT_DATA" in live_html


def test_every_onclick_function_is_defined(live_html):
    """Every function name used in an onclick= handler must be defined
    somewhere in the page (function declaration or const/let assignment).
    This is the class of bug that shipped the missing setHor()."""
    called = set(re.findall(r'onclick="([a-zA-Z_$][\w$]*)\(', live_html))
    defined = set(re.findall(r"function\s+([a-zA-Z_$][\w$]*)\s*\(", live_html))
    defined |= set(re.findall(r"(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=", live_html))
    missing = sorted(called - defined)
    assert not missing, f"onclick references undefined functions: {missing}"


@pytest.mark.parametrize(
    "name",
    ["setHor", "absPhrase", "qs", "esc", "openGap", "openCountry", "openSignal", "ask", "chip"],
)
def test_required_function_defined(live_html, name):
    assert re.search(rf"function\s+{name}\s*\(", live_html), f"function {name}() missing"


@pytest.mark.parametrize(
    "mock_text",
    [
        "(prototype: scripted)",
        "2 WATCH · 39 WEAK · 31 DEAD",
        "16 Jun 2026",
        "%, reflation",
        "As-of 16 Jun · 79 rows",
    ],
)
def test_no_mock_narration_leaks(live_html, mock_text):
    assert mock_text not in live_html, f"mock narration leaked: {mock_text!r}"


def test_repriced_against_never_shows_unabsorbed_pct(live_html):
    """F2: the absorption phrase for repriced_against must show the signed
    index, and the generic '% unabsorbed' path must be behind the state check."""
    assert "repriced against · index" in live_html
    m = re.search(r"function absPhrase\(g\)\{(.*?)\}\n", live_html, re.S)
    assert m, "absPhrase not found"
    body = m.group(1)
    assert body.index("repriced_against") < body.index("% unabsorbed")
