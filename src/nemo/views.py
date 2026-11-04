"""The four documents a human reads, rendered from the record bytes and from nothing else.

In v1 the closed package for one room held MTPD `24 h` in the record, `8 h` in the handover and
`0–4 hours` in the worksheet, with owner validation pending, and nothing compared them. The fix
here is not a comparison. `render` is a function of one record, the four documents are four
arrangements of the **same** rendered sentences, and there is nowhere for a second figure to enter:
the worksheet cannot disagree with the capture because neither of them was written.

**Nothing in this module reaches the disk, the clock, the network or the room** — except `write`,
which is the one place the four land, and which takes the record it renders. A view that needed a
transcript, the dependency register or the method file would be a document that renders differently
depending on what the room happens to hold today, and the guarantee above would hold by luck. A
fact the record does not carry is therefore never fetched: it is said to be not established, in the
manager's words, because a gap the reader cannot see is a gap nobody fixes.

**The sentences themselves are `nemo.figures`', not this module's.** The stage 4 card, the
worksheet and stage 5's handover say the same figure to the same human hours apart, and two
spellings of that sentence is the v1 defect one layer up. They used to live here, which made this
module the place `nemo.handover` had to import to say them — a stage-5 document depending on the
stage-4 renderer, and through it on `write` below, for sentences that reach no disk. They now sit
below both, so the four documents and the handover cannot say one figure two ways and neither layer
imports the other.

**The figure inside those sentences is `nemo.impact`'s, not this module's and not the referee's.**
This module used to import `nemo.referee` for it, which put six hundred lines of judgement under
the rendering layer and pointed an import at the module whose verdict travels the other way. The
derivation now sits below both (`nemo.impact`), so the worksheet and the referee cannot derive two
MTPDs, and neither layer imports the other. `nemo.figures` is the same move made a second time, and
this module reaches the derivation through it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path

from nemo.figures import depends, says
from nemo.impact import NOT_RATED, unrated_bands
from nemo.method import horizons as _horizons
from nemo.record import (
    ACTIVITIES,
    ACTIVITY,
    ASSET_ID,
    ASSET_IDS,
    CHAT_CONFIRMATION,
    DEPT,
    EVIDENCE,
    IMPACT_GRID,
    LENS,
    METHOD,
    NAME,
    ON,
    OPEN_ITEMS,
    QUOTE,
    REGISTER_NO_RPO,
    REGISTER_ROW,
    SOURCE_PATH,
    TYPE,
    WORDS,
    Record,
)
from nemo.room_store import write_document

#: The four documents, under the names the story names them by, in the order the walk produced
#: what is in them. `render` hands back exactly these and a room holds exactly these.
SCOPE = "stage1-scope-and-guide.md"
CAPTURE = "stage2-interview-capture.md"
ANALYSIS = "stage3-dependency-analysis.md"
WORKSHEET = "stage4-worksheet.md"
FOUR = (SCOPE, CAPTURE, ANALYSIS, WORKSHEET)

#: What a cell nobody scored says in the grid. The record spells it `MISSING`, which is a word for
#: the referee rather than for the manager reading this.
NOT_SCORED = "not scored"

STILL_OPEN = "## What is still open"
NOTHING_OPEN = "Nothing in this BIA was left open."

IN_SCOPE = "{activity} is in the scope of this BIA, and what follows was agreed for it."
SCORED = "{lens} — “{quote}” ({path})"
SAID = "“{quote}” ({path})"
#: Ticket 132 (ADR-0030): a figure the manager confirmed in chat, said as his confirmation with its
#: day, in the worksheet beside the quotes and never inside an interview-quote block.
CONFIRMED = "The manager's confirmation in chat on {on}: {words}"
#: Ticket 171: the register row a derived RPO rests on, said as the register's, never as a quote.
REGISTERED = ("The dependency register gives {asset} a recovery point of {quote} for {activity} "
              "({path})")
#: t171-shape (DRAFT, awaiting the owner): the register giving an activity no RPO; the rows read.
NO_RPO_REGISTERED = ("The dependency register gives no recovery point for {activity} in its rows "
                     "for {assets} ({path})")

SCOPE_LEAD = ("This is the scope this BIA was agreed over, and the figures that were agreed under "
              "it. Every sentence below is read out of the BIA record in your room, so it says "
              "what the record says or it does not appear.")
CAPTURE_LEAD = ("The interview this BIA rests on, in its own words, with the file each sentence "
                "was read out of beside it. Nothing has been tidied and nothing has been "
                "shortened.")
ANALYSIS_LEAD = ("What this department depends on, named by the ids your dependency register "
                 "holds, and what the analysis left for somebody to decide.")
WORKSHEET_LEAD = ("The worksheet: for each activity, what an outage of it costs over time, how "
                  "long it can be down, what has to be back and by when, and the words each of "
                  "those rests on.")

_NOT_A_NAME = re.compile(r"[^a-z0-9]+")


def render(record: Record) -> dict[str, str]:
    """The four documents this record says, each as markdown a human reads. Writes nothing."""
    method: Record = record.get(METHOD) or {}
    return {
        SCOPE: _document("The scope this BIA was agreed over", SCOPE_LEAD, record, method,
                         _in_scope),
        CAPTURE: _document("The interview this BIA rests on", CAPTURE_LEAD, record, method,
                           _quotes),
        ANALYSIS: _document("What this BIA depends on", ANALYSIS_LEAD, record, method, depends),
        WORKSHEET: _document("The worksheet", WORKSHEET_LEAD, record, method,
                             lambda activity: _worksheet(activity, method)),
    }


def folder(record: Record) -> str:
    """Where this record's four documents live, relative to the room: `output/<process>/`."""
    return f"output/{_NOT_A_NAME.sub('-', str(record.get(DEPT, '')).lower())}"


def write(room_folder: Path, record: Record) -> None:
    """The four into the room. A document offered a fraction of its saved bytes is refused."""
    at = folder(record)
    for name, text in render(record).items():
        write_document(room_folder, f"{at}/{name}", text)


# ── the shape all four share ─────────────────────────────────────────────────


def _document(title: str, lead: str, record: Record, method: Record,
              section: Callable[[Record], list[str]]) -> str:
    """One document: a heading, what it is, each activity, and what is still open.

    Every one of the four is built here, and every one of them carries `nemo.figures.says`
    under each activity. That is the whole mechanism behind "the views cannot disagree": there is
    one sentence per figure and four documents that quote it — and `nemo.handover` quotes the same
    sentences from the same place, which is why they are not this module's.
    """
    parts = [f"# {title} — {record.get(DEPT, '')}", lead]
    for activity in record.get(ACTIVITIES) or []:
        parts += [f"## {activity[NAME]}", *section(activity), *says(activity, method)]
    parts += [STILL_OPEN, *(record.get(OPEN_ITEMS) or [NOTHING_OPEN])]
    return "\n\n".join(parts) + "\n"


def _in_scope(activity: Record) -> list[str]:
    """What the scope guide says above the figures: that this activity is in the scope agreed."""
    return [IN_SCOPE.format(activity=activity[NAME])]


def _worksheet(activity: Record, method: Record) -> list[str]:
    """What the worksheet says above the figures: the grid, the dependencies, and the quotes.

    The worksheet is the one document that carries all three, because it is the one a human works
    from: the score, the id it depends on and the words it rests on, beside each other.
    """
    return [*_grid(activity, method), *depends(activity), *_quotes(activity),
            *_confirmations(activity), *_registered(activity)]


def _quotes(activity: Record) -> list[str]:
    """Every quote this activity rests on, with the file it came from, and its score where it
    supports one. Character for character: a quote retyped is a quote nobody can check."""
    return [SCORED.format(lens=item[LENS], quote=item[QUOTE], path=item[SOURCE_PATH])
            if item.get(LENS) else
            SAID.format(quote=item[QUOTE], path=item[SOURCE_PATH])
            for item in activity.get(EVIDENCE) or []
            if item.get(TYPE) not in (CHAT_CONFIRMATION, REGISTER_ROW, REGISTER_NO_RPO)]


def _confirmations(activity: Record) -> list[str]:
    """Every figure the manager confirmed in chat, as his confirmation on its day (ticket 132)."""
    return [CONFIRMED.format(on=item[ON], words=item[WORDS])
            for item in activity.get(EVIDENCE) or [] if item.get(TYPE) == CHAT_CONFIRMATION]


def _registered(activity: Record) -> list[str]:
    """Every register row a derived RPO rests on, as the register's own words (ticket 171), and
    the register's no-RPO row (t171-shape, DRAFT)."""
    return [_register_line(item) for item in activity.get(EVIDENCE) or []
            if item.get(TYPE) in (REGISTER_ROW, REGISTER_NO_RPO)]


def _register_line(item: Record) -> str:
    """One register row, or the no-RPO row, as the worksheet says it."""
    if item.get(TYPE) == REGISTER_ROW:
        return REGISTERED.format(asset=item[ASSET_ID], quote=item[QUOTE],
                                 activity=item.get(ACTIVITY), path=item[SOURCE_PATH])
    return NO_RPO_REGISTERED.format(activity=item.get(ACTIVITY), path=item[SOURCE_PATH],
                                    assets=", ".join(item.get(ASSET_IDS) or []) or "no dependency")


def _grid(activity: Record, method: Record) -> list[str]:
    """The impact grid as a table, across every horizon the method covers."""
    grid: Record = activity.get(IMPACT_GRID) or {}
    lenses = list(grid)
    return [_row("Horizon", lenses), _row("---", ["---"] * len(lenses)),
            *(_band(grid, lenses, band) for band in _bands(grid, method))]


def _bands(grid: Record, method: Record) -> list[str]:
    """Every horizon the method covers, falling back to the ones the grid was scored over.

    Every horizon, not every horizon somebody scored: a band the interview never reached is a row
    saying nothing was scored in it, because a dropped row reads as a band with no impact in it.
    """
    return _horizons(method) or sorted({band for row in grid.values() for band in row})


def _band(grid: Record, lenses: Sequence[str], band: str) -> str:
    """One row of the table: the horizon, and what each lens scored in it. A band no lens rated
    says so in every cell (ADR-0050), never as a score and never as a blank."""
    if unrated_bands(grid, [band]):
        return _row(band, [NOT_RATED] * len(lenses))
    return _row(band, [_cell(grid[lens].get(band)) for lens in lenses])


def _row(first: str, rest: Sequence[str]) -> str:
    return "| " + " | ".join([first, *rest]) + " |"


def _cell(value: object) -> str:
    """A score as the record holds it, or the words for a cell nobody scored."""
    return str(value) if isinstance(value, int) else NOT_SCORED
