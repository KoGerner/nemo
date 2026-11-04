"""What a room's ``method.json`` calls the five things it states, and how to read them.

Two layers read the same file for opposite reasons and neither of them may own the spelling.
``walk`` copies the method onto the run record, parameter by parameter, so a card is judged under
the room's own method rather than a hard-coded one. ``referee`` reads those same parameters back
out to judge a grid against them.

A name stated in both places can drift in one of them, and the drift is silent: drop
``intolerability_threshold`` from what the walk copies and the referee does not refuse the record,
it reads nothing, and ``derive_mtpd`` compares a score against ``None``. So the names are stated
here, once, below both — and the accessors sit beside the names rather than in whichever layer
happened to need them first.

Nothing here defaults or invents. A parameter the room's file does not carry stays absent, and an
accessor for one hands back an empty list rather than a guess: an empty method names no horizon
and no lens, which is a method that judges nothing, not a method that judges by our defaults.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCENARIOS = "scenarios"
TIME_HORIZONS = "time_horizons"
SEVERITY_SCALE = "severity_scale"
INTOLERABILITY_THRESHOLD = "intolerability_threshold"
RPO_VOCABULARY = "rpo_vocabulary"
#: The method's own word for an MTPD past its last horizon (">168 h" in the seed's method, ruled by
#: 0_marschkamp in c9cefb0, ticket 136). A method may state it or not; the old seed's did not.
BEYOND_HORIZONS = "beyond_horizons"
#: Whose method this is — the company the room's own method file names. Stated by the method and
#: never inferred: it is what the dependency page is titled and filed under (ticket 143).
ORG = "org"

#: The five parameters a walk carries out of the room's method file: the impact categories, the
#: time bands, the 1-5 scale, the score at which impact is intolerable, and the words an RPO may
#: be said in. Copied; never defaulted, never invented.
PARAMETERS = (SCENARIOS, TIME_HORIZONS, SEVERITY_SCALE, INTOLERABILITY_THRESHOLD, RPO_VOCABULARY)


def horizons(method: Mapping[str, Any]) -> list[str]:
    """The time bands, in the order the method names them. The order is the method's meaning."""
    return list(method.get(TIME_HORIZONS) or [])


def lenses(method: Mapping[str, Any]) -> list[str]:
    """The impact categories, by the ``id`` each scenario states. One without an id is not one."""
    return [s["id"] for s in method.get(SCENARIOS) or [] if isinstance(s, dict) and s.get("id")]


def threshold(method: Mapping[str, Any]) -> Any:
    """The score at which impact is intolerable. Absent from the file, absent here."""
    return method.get(INTOLERABILITY_THRESHOLD)


def rpo_vocabulary(method: Mapping[str, Any]) -> list[str]:
    """The data-loss answers the method allows, in its own words."""
    return list(method.get(RPO_VOCABULARY) or [])


def beyond_horizons(method: Mapping[str, Any]) -> str | None:
    """The method's word for an MTPD past the last horizon, or None where it states none."""
    word = method.get(BEYOND_HORIZONS)
    return str(word) if word else None
