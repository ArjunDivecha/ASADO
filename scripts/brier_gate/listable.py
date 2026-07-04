"""
=============================================================================
SCRIPT NAME: listable.py (Brier Gate — US-listability classifier)
=============================================================================

INPUT FILES:
- None (pure library module; classifies question strings passed in)

OUTPUT FILES:
- None (pure library module; no file I/O)

VERSION: 1.0
LAST UPDATED: 2026-07-04
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Classifies a prediction-market question as listable (True) or not (False)
on a CFTC-regulated US exchange (Polymarket US / Kalshi). CFTC Regulation
40.11 prohibits US-registered exchanges from listing event contracts on
WAR, TERRORISM, or ASSASSINATION (plus gaming/unlawful activity). This is
a keyword heuristic, not legal advice: it flags conflict/violence contracts
as not-listable and treats everything else (elections, leadership changes,
diplomacy, economics, commodities) as listable. Used to split the Brier
Gate scoreboard into "edge tradeable on the US site today" vs
"offshore-only edge".

DEPENDENCIES:
- Standard library only (re)

USAGE:
  from listable import us_listable
  us_listable("Will the U.S. invade Iran before 2027?")  # -> False
  us_listable("Will Renan Santos win the 2026 Brazilian election?")  # -> True

NOTES:
- Conservative on the prohibited side: any conflict/violence vocabulary
  marks the contract not-listable, since a false "listable" would overstate
  the US-tradeable edge.
- Borderline cases (sanctions, blockades, shipping disruption caused by
  conflict) are marked NOT listable — they are war-adjacent and unlikely
  to clear a DCM's product review.
=============================================================================
"""

from __future__ import annotations

import re

_PROHIBITED = re.compile(
    r"\b("
    r"war|invade|invasion|military (action|clash|strike|operation|conflict)|"
    r"attack|strike[s]? (on|against)|airstrike|missile|bomb|nuclear (test|strike|weapon)|"
    r"ceasefire|cease-fire|truce|armistice|"
    r"troops|forces (enter|capture|withdraw|advance)|capture[sd]? (all of|the city)|"
    r"recapture|occupied|occupation|annex|"
    r"terror|assassinat|hostage|coup\b|"
    r"blockade|hormuz|strait (of|closure)|shot down|shoot[s]? down|"
    r"killed|casualties|"
    r"front ?line|offensive\b"
    r")",
    re.IGNORECASE,
)


def us_listable(question: str) -> bool:
    """True if the contract could plausibly list on a CFTC-regulated US venue."""
    return not bool(_PROHIBITED.search(question or ""))
