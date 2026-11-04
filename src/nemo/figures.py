"""The sentences one activity's figures are said in, below every document that says them.

The record is the single source every view, figure and graph is generated from, and stage 4's four
views and stage 5's two documents are five arrangements of the **same** sentences over it. Where
those sentences live decides whether that can stay true. Until this module they lived in
`nemo.views`, and `nemo.handover` imported the renderer to reach them — so the stage-5 documents
depended on the stage-4 renderer, and through it on the disk door `nemo.views.write` opens, for six
sentences that touch neither. The alternative a layer reaches for when that import looks wrong is
worse: it says the figure in its own words, and then `output/<process>/` holds `24 h` in the record,
`8 h` in the handover and `0–4 hours` in the worksheet, which is v1's defect and the reason the
views module exists.

**This is the move this package has already made twice, and it is the same move.** `nemo.record`
holds the vocabulary the handover and the walk both need, below both, because the handover may not
import the walk. `nemo.impact` holds the MTPD derivation the worksheet and the referee both need,
below both — so, in the words `nemo.views` records it in, "the worksheet and the referee cannot
derive two MTPDs, and neither layer imports the other". This module is the third: what two layers
both need sits under both of them, rather than one of them importing the other for it.

**Nothing here reaches the disk, the clock, the network or the room.** Every sentence is a function
of the activity it is handed and of the method that activity was scored under, and of nothing else,
so two documents built from the same record say the same figure and rendering twice produces the
same bytes twice. `nemo.test_figures` holds that shut with the package's seal rather than by
reading the source and believing it.

**A fact the record does not carry is never fetched.** It is said to be not established, in the
manager's words, once, in `NOTHING` — because a gap the reader cannot see is a gap nobody fixes,
and a blank, a dash or a figure borrowed from another activity are all worse than the sentence.
"""

from __future__ import annotations

from collections.abc import Sequence

from nemo.impact import NO_MTPD, crossing
from nemo.record import (
    BY_WHEN,
    DATA_SETS,
    DEPENDENCIES,
    IMPACT_GRID,
    MBCO,
    MTPD,
    NAME,
    RECOVERY_TARGET,
    RESOURCES,
    RPO,
    WORKAROUND,
    Record,
)

#: What stands where the record holds no figure at all. One wording for every gap, so a reader
#: learns it once, and never a blank, a dash or a figure borrowed from another activity.
NOTHING = "not established"

MTPD_SAYS = ("Your grid for {activity} first reaches the level your method calls intolerable under "
             "{lenses}, and it reaches it at {horizon}, so the longest {activity} can be down "
             "before that becomes unacceptable stands at {horizon}.")
NO_MTPD_SAYS = ("Your grid for {activity} never reaches the level your method calls intolerable "
                "inside the horizons it scored, so I have put no longest-tolerable outage on it "
                "at all rather than one nobody derived.")

STATED = ("Your interview puts the longest {activity} can be down at {mtpd}, and the grid was read "
          "beside it rather than instead of it.")
WHOLE = ("No data set is named for {activity} in this BIA, so what stands below stands for the "
         "activity as a whole rather than for one set of its data.")
TARGETS = "For {name}: the recovery target is {rto}, and the recovery point is {rpo}."
MBCO_SAYS = "The minimum acceptable service for {activity} is {mbco}."
RESOURCES_SAY = "The minimum resources {activity} needs over time, and what stands in for each:"
RESOURCE = "{name} — needed by {by_when}. Without it: {workaround}."
NO_RESOURCES = ("The minimum resources over time for {activity} were not established, so this "
                "document names none rather than one nobody wrote down.")
DEPENDS = "{activity} depends on {ids}, by the ids your dependency register holds for them."
NO_DEPENDS = ("No dependency of {activity} resolved to an id in your dependency register, so none "
              "is named here.")

#: Ticket 120 (the owner's ruling, 2026-09-22T09:58:13Z): the one line nemo adds after a side he
#: took whose own figure the record does not carry. Third person, because the certificate and the
#: handover say it. "Tighter" is true in one case only, so his own figure kept has its own sentence.
KEPT_TIGHTER = "The tighter figure, {kept}, stands."
KEPT_HIS = "The manager's own figure, {kept}, stands."


def stands(activity: Record, method: Record) -> str:
    """How long this activity can be down, said as a consequence with the reason before it.

    The stage 4 card's sentence and the worksheet's, because they are one sentence: the card says
    it by calling this, and so does the worksheet, hours apart, to the same human. A grid that
    reaches nothing crosses nowhere: what comes back then says so, and carries no figure for a
    reader to mistake for one somebody derived.
    """
    horizon, lenses = crossing(activity.get(IMPACT_GRID) or {}, method)
    if horizon == NO_MTPD:
        return NO_MTPD_SAYS.format(activity=activity[NAME])
    return MTPD_SAYS.format(activity=activity[NAME], lenses=listed(lenses), horizon=horizon)


def says(activity: Record, method: Record) -> list[str]:
    """The figures this activity stands at, in the sentences every document says them in.

    The figure the interview stated and the figure the grid derives are both here, because the
    record holds both and a document that showed one of them would be the reader's only sight of
    it. Where they differ it is the record that is wrong, and the referee has already said so.
    """
    stated = [STATED.format(activity=activity[NAME], mtpd=activity[MTPD])] if activity.get(
        MTPD) else []
    return [*stated, stands(activity, method), *_targets(activity),
            MBCO_SAYS.format(activity=activity[NAME], mbco=_held(activity.get(MBCO))),
            *_resources(activity)]


def depends(activity: Record) -> list[str]:
    """The dependencies by the register ids the record holds, and no id it does not hold."""
    ids = [str(item) for item in activity.get(DEPENDENCIES) or []]
    return [DEPENDS.format(activity=activity[NAME], ids=listed(ids)) if ids
            else NO_DEPENDS.format(activity=activity[NAME])]


def requirements(activity: Record, method: Record) -> list[str]:
    """The continuity requirements this activity stands at, in the sentences the documents say
    them in.

    Stage 5's handover is a fifth arrangement of the same rendered sentences rather than a fifth
    renderer (ticket 18): how long the activity can be down, what has to be back and by when, the
    minimum acceptable service, the resources and what stands in for each, and what it depends on.
    A handover that said any of them in its own words could disagree with the worksheet a manager
    read an hour earlier, which is the defect this module exists to make impossible.
    """
    return [*says(activity, method), *depends(activity)]


def listed(words: Sequence[str]) -> str:
    """Words as a manager reads a list of them: commas, and an *and* before the last."""
    return " and ".join([part for part in (", ".join(words[:-1]), *words[-1:]) if part])


def _targets(activity: Record) -> list[str]:
    """The recovery target and the recovery point, per data set where the record names them.

    Where it names none, the figures the activity carries are said to stand for the whole of it —
    which is what they do — rather than being printed as though one data set's figure covered
    every set of data the activity touches.
    """
    named = activity.get(DATA_SETS) or []
    if named:
        return [_target(item[NAME], item) for item in named]
    return [WHOLE.format(activity=activity[NAME]), _target(activity[NAME], activity)]


def _target(name: str, holder: Record) -> str:
    return TARGETS.format(name=name, rto=_held(holder.get(RECOVERY_TARGET)),
                          rpo=_held(holder.get(RPO)))


def _resources(activity: Record) -> list[str]:
    """Each resource with what is needed by when, and the workaround for doing without it."""
    named = activity.get(RESOURCES) or []
    if not named:
        return [NO_RESOURCES.format(activity=activity[NAME])]
    return [RESOURCES_SAY.format(activity=activity[NAME]),
            *(RESOURCE.format(name=item[NAME], by_when=_held(item.get(BY_WHEN)),
                              workaround=_held(item.get(WORKAROUND))) for item in named)]


def _held(value: object) -> str:
    """The record's own string for a figure, or the words for one the record does not hold."""
    return str(value) if value else NOTHING


def kept_says(kept: object, his: bool = False) -> str:
    """The figure the record kept over a side he took ("" if none was kept); `his` is his own
    figure kept, which is said as his and not as the tighter one. No source (14_nemo_check)."""
    if not kept:
        return ""
    return KEPT_HIS.format(kept=kept) if his else KEPT_TIGHTER.format(kept=kept)
