"""Ticket 263: how soon each resource is needed back, and where an RTO is too slow.

The owner's words (bc25d46c, Q4 and Q6): for every system, the tightest recovery need among the
activities that depend on it, directly or through other systems, and down the process chain (a
downstream activity's MTPD bounds its upstream activity's recovery); a flag where an RTO equals or
exceeds such an MTPD. Computed, nothing authored: no figure is written anywhere (ADR-0032 d10).

The MTPD is the one the room sheet holds (the record's, else the draft's: cf6ad015), and an RTO is
held against it by the referee's own reading (`handover.gap_reading`: `>=` is outside, both past
the horizons is inside, an MTPD that cannot be read claims nothing). The referee's activity-level
rule is not touched. Pure: the caller reads the room (`PROTOTYPE_core.resource_needs`).
"""

from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple

from nemo import duration, handover


class Held(NamedTuple):
    """An activity as the room sheet holds it: its name, its MTPD and RTO, and whether the MTPD
    is a record's (agreed) or the draft's (proposed)."""

    name: str
    mtpd: str | None
    rto: str | None
    agreed: bool


def followed(down: Mapping[str, Sequence[str]], start: str | None) -> list[str]:
    """Every name `down` puts after `start`, followed to the end, nearest first, each once."""
    reached: list[str] = []
    todo = list(down.get(start or "", ()))
    while todo:
        step = todo.pop(0)
        if step not in reached:
            reached.append(step)
            todo += down.get(step, ())
    return reached


def _outside(rto: object, mtpd: str | None, method: Mapping[str, Any]) -> bool:
    return handover.gap_reading({"recovery_target": rto, "mtpd": mtpd}, dict(method)) is True


def _differs(said: object, mtpd: str) -> bool:
    a, b = duration.worst_case(said), duration.worst_case(mtpd)
    return (a != b) if a is not None and b is not None else str(said).strip() != mtpd.strip()


Bound = tuple[str, str, dict[str, Any]]


def needs(register: Mapping[str, Any], held: Mapping[str, Held], down: Mapping[str, Sequence[str]],
          method: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Per asset id, for every asset some activity depends on: `within`, the tightest MTPD reached,
    `set_by` the activity holding it and `mtpd` "agreed" or "proposed"; `register`, the figure the
    asset's own register row for that activity states where it differs (188's gap, stated); and
    `flags`, each an RTO ("who"'s) at or past an activity's MTPD. `held` and `down` are keyed by
    the room's activity slug; a consumer row names its activity by `department`, else by name."""
    assets = {k: v for k, v in register.items() if isinstance(v, dict)}
    stands_on: dict[str, list[str]] = {}
    for aid, a in assets.items():
        for dep in a.get("depends_on") or []:
            stands_on.setdefault(dep, []).append(aid)
    by_name = {h.name: slug for slug, h in held.items()}
    users = {aid: [(row.get("department") if row.get("department") in held
                    else by_name.get(row.get("activity")), row)
                   for row in a.get("consumers") or []] for aid, a in assets.items()}
    out = {}
    for aid, asset in assets.items():
        # (the user's slug, the activity whose MTPD bounds it, the asset's own row for it or {})
        bounds: list[Bound] = [
            (slug, bound, row if user == aid and bound == slug else {})
            for user in [aid, *followed(stands_on, aid)]
            for slug, row in users.get(user, []) if slug is not None and slug in held
            for bound in [slug, *followed(down, slug)] if bound in held]
        if found := _need(asset.get("name") or aid, asset, bounds, held, method):
            out[aid] = found
    return out


def _need(name: str, asset: Mapping[str, Any], bounds: list[Bound], held: Mapping[str, Held],
          method: Mapping[str, Any]) -> dict[str, Any] | None:
    flags = _flags(name, asset, bounds, held, method)
    readable = [(limit, i) for i, (_, bound, _) in enumerate(bounds)
                if (limit := duration.worst_case(held[bound].mtpd)) is not None]
    if not readable and not flags:
        return None
    found: dict[str, Any] = {"resource": name}
    if readable:
        _, bound, own = bounds[min(readable)[1]]  # a tie goes to the first reached
        at, said = held[bound], own.get("consumer_mtpd")
        found.update(within=at.mtpd, set_by=at.name, mtpd="agreed" if at.agreed else "proposed")
        if said and _differs(said, str(at.mtpd)):
            found["register"] = said
    return found | ({"flags": flags} if flags else {})


def _flags(name: str, asset: Mapping[str, Any], bounds: list[Bound], held: Mapping[str, Held],
           method: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The asset's own RTO against every MTPD that bounds it, its row's against its own
    activity's, and down the chain each upstream activity's RTO against the MTPD below it."""
    flags: list[dict[str, Any]] = []
    for slug, bound, own in bounds:
        at = held[bound]
        tried = [(name, asset.get("rto")), *([(name, own.get("rto"))] if own else []),
                 *([(held[slug].name, held[slug].rto)] if bound != slug else [])]
        for who, rto in tried:
            f = {"who": who, "rto": rto, "activity": at.name, "mtpd": at.mtpd}
            if f not in flags and _outside(rto, at.mtpd, method):
                flags.append(f)
    return flags



Found = Mapping[str, Mapping[str, Any]]


def split(found: Found) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """t339: `needs`' result as the model reads it. Each resource's entry keeps its own flags
    only; a chain flag ("who" an activity, not the resource) is carried on every resource the
    activity uses, so it moves to one list, once per (activity, downstream activity), with
    `through` naming once each resource it ran on. First seen order; `found` is not changed."""
    entries: list[dict[str, Any]] = []
    chains: dict[tuple[str, str], dict[str, Any]] = {}
    for need in found.values():
        name, flags = need["resource"], need.get("flags", [])
        for f in (f for f in flags if f["who"] != name):
            through = chains.setdefault((f["who"], f["activity"]), {**f, "through": []})["through"]
            through += [name] if name not in through else []
        own = [f for f in flags if f["who"] == name]
        entry = {k: v for k, v in need.items() if k != "flags"}
        entries.append(entry | {"flags": own} if own else entry)
    return entries, list(chains.values())
