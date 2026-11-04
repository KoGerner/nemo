"""The impact grid and the one MTPD it derives, below every layer that needs that figure.

Two layers need the same derivation for opposite reasons and neither of them may own it. The
**referee** reads a submitted grid to judge it and to put the derived MTPD onto the record. The
**views** read a saved grid to say that same figure to a manager, with the reason before it
(`docs/voice.md`). Both need "which horizon does this grid cross at, and which categories cross
there"; neither is a client of the other.

`nemo.views` used to import `nemo.referee` for exactly `crossing` and `NO_MTPD` — the same shape
`nemo.text`'s docstring records for the card, and the same repair. That edge made the rendering
layer depend on six hundred lines of judgement it never calls: shape rejections, evidence
resolution, finding wording. Worse, it pointed the wrong way for what travels between them. The
referee's verdict travels *to* the documents, so the day a finding needs rendering the import comes
back and the cycle is there. So the derivation lives here, below both, and neither imports the
other.

**A second derivation standing beside this one is the v1 defect.** That closed package held MTPD
`24 h` in the record, `8 h` in the handover and `0–4 hours` in the worksheet. The fix is not a
comparison between three figures: it is that there is one function, so there is only ever one
figure to say. Anything that derives an MTPD derives it here or it is a second answer.

Pure: no disk, no clock, no network, no room. A grid and a method in, a horizon and its reasons
out. Nothing here defaults or invents — a method that names no horizon derives no MTPD, which is
`NO_MTPD`, not a guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nemo.method import horizons as _horizons
from nemo.method import lenses as _lenses
from nemo.method import threshold as _threshold
from nemo.text import norm

#: What a grid that never reaches the method's intolerability threshold derives. A refusal to put
#: a figure on the activity, said in words, rather than the last horizon or an empty string — both
#: of which a reader would take for a derived MTPD.
NO_MTPD = "no MTPD within horizons"
#: Ticket 376 (ADR-0050): what a time band the source left "–" in every category is said as,
#: wherever a band is shown. Never a score and never a blank.
NOT_RATED = "not rated in the source"


def is_score(value: object) -> bool:
    """A cell the method can judge: an integer 1-5. `True` is not a 1 and `"MISSING"` is not a 5."""
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 5


def _canonicalize(row: Mapping[str, Any], canonical: Mapping[str, str]) -> dict[str, Any]:
    """Replace typographic variants with the method's own labels.

    A raw key whose canonical form is already taken keeps its raw spelling, so a collision is
    rejected explicitly rather than silently overwriting the value beside it.
    """
    out: dict[str, Any] = {}
    for raw, value in row.items():
        key = canonical.get(norm(raw), raw)
        out[raw if key in out else key] = value
    return out


def canonicalize_grid(grid: Mapping[str, Any], method: Mapping[str, Any]) -> dict[str, Any]:
    """The grid said in the method's own spellings, so an en dash cannot become a second horizon."""
    horizons = {norm(h): h for h in _horizons(method)}
    rows = _canonicalize(grid, {norm(lens): lens for lens in _lenses(method)})
    return {
        lens: _canonicalize(row, horizons) if isinstance(row, dict) else row
        for lens, row in rows.items()
    }


def unrated_bands(grid: Mapping[str, Any], horizons: list[str]) -> list[str]:
    """The time bands no category put a figure against: the source left them "–" in every one.

    Every row is an object by the time this runs, as for `worst_case_row`. A grid with no
    category at all rates nothing and leaves nothing unrated.
    """
    return [h for h in horizons
            if grid and not any(is_score(row.get(h)) for row in grid.values())]


def worst_case_row(grid: Mapping[str, Any]) -> dict[str, int]:
    """The grid collapsed to the worst score per horizon. MISSING cells do not pull it down.

    Every row is an object by the time this runs: a row that is not one is a shape rejection.
    """
    worst: dict[str, int] = {}
    for row in grid.values():
        for horizon, value in row.items():
            if is_score(value):
                worst[horizon] = max(worst.get(horizon, value), value)
    return worst


def derive_mtpd(worst: Mapping[str, int], method: Mapping[str, Any]) -> str:
    """The earliest horizon whose worst case reaches the method's intolerability threshold."""
    intolerable: Any = _threshold(method)
    for horizon in _horizons(method):
        if horizon in worst and worst[horizon] >= intolerable:
            return horizon
    return NO_MTPD


def crossing(grid: Mapping[str, Any], method: Mapping[str, Any]) -> tuple[str, list[str]]:
    """The MTPD this grid derives, and the categories whose own score reaches it there.

    The horizon is ``derive_mtpd``'s, over the same canonicalized grid the referee judges — never a
    second derivation standing beside it, which is how a card would come to say a figure the
    referee did not derive. The categories are the *reason*, and stage 4 says the reason before the
    figure (``docs/voice.md``): a grid that reaches nothing crosses nowhere and names nobody, which
    is the honest shape of "no MTPD within horizons".
    """
    reading = mtpd_reading(grid, method)
    return reading["horizon"], reading["lenses"]


def mtpd_reading(grid: Mapping[str, Any], method: Mapping[str, Any]) -> dict[str, Any]:
    """Ticket 601: the MTPD reading as data, the one derivation every reader of it calls
    (``crossing`` too): the horizon ``derive_mtpd`` gives over the canonicalized grid, the
    categories whose own score reaches it there, and the highest of those scores (`None` where
    the grid derives no MTPD)."""
    canonical = canonicalize_grid(grid, method)
    horizon = derive_mtpd(worst_case_row(canonical), method)
    intolerable: Any = _threshold(method)
    lenses = [lens for lens, row in canonical.items()
              if is_score(row.get(horizon)) and row[horizon] >= intolerable]
    return {"horizon": horizon, "lenses": lenses,
            "score": max((canonical[x][horizon] for x in lenses), default=None)}
