"""The derivation.

An activity's RPO is the tightest recovery point among the register entries it depends on that
hold data; when none of them hold data it is the method's no-data value, or, for a method with no
such word, no figure at all (190, the owner's "No RPO at all"). The figure never travels without
its reason: the dependency ids that justified it, all of them where several tie, or `NO_DATA_HELD`
where no figure is owed.

A register entry's recovery point stands for the duration it begins with, however it is written:
`4 h` and `4 h (ERP order data)` are the same four hours, `n/a` and `n/a (physical)` the same
nothing. Durations are compared with durations; what the register wrote is quoted back unchanged.

Only an asset is asked for a recovery point. An id the register holds as metadata, or does not hold
at all, sets no figure — nothing is known about what it holds — and is named back as unrecognised
rather than silently counted as holding no data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from bia_figures.register import Register, recovery_point_for
from bia_figures.vocabulary import (
    Method,
    duration_of,
    looseness,
    no_data_duration,
    words_by_duration,
)

__all__ = ["NO_DATA_HELD", "Derivation", "Method", "derive_rpo"]

#: Why an activity has no RPO where none of its dependencies declares one for it, under a method
#: with no no-data word (190 item 2, the owner's (a), "No RPO at all"). Kept apart from `unmatched`.
#: 190 REASON WORDING (16_nemo_check): a system may hold data and still give no RPO for this
#: activity (time-recording's), so the words say that, not "holds no data".
NO_DATA_HELD = "none of the systems it depends on gives one for this activity"


@dataclass(frozen=True)
class Derivation:
    """A figure and the dependencies that justified it, or no figure and why not."""

    figure: str | None
    reason: tuple[str, ...] = ()
    unmatched: tuple[tuple[str, str], ...] = ()
    unrecognised: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Declaration:
    """What one dependency declares: the recovery point as written, and the duration it stands for.

    Reading the duration once, here, is what keeps the rest of the derivation comparing durations
    with durations while still quoting the register's own words back in a complaint.
    """

    dependency: str
    as_written: str
    duration: str


def _declarations(
    dependency_ids: Iterable[str],
    register: Register,
    activity: str | None,
) -> tuple[list[_Declaration], tuple[str, ...]]:
    """What the dependencies declare for the activity, and the ids that declare nothing for it."""
    declared: list[_Declaration] = []
    unrecognised: list[str] = []
    for dependency in dependency_ids:
        as_written = recovery_point_for(register, dependency, activity)
        if as_written is None:
            unrecognised.append(dependency)
            continue
        declared.append(_Declaration(dependency, as_written, duration_of(as_written)))
    return declared, tuple(unrecognised)


def _data_holders(declared: Iterable[_Declaration], no_data: str | None) -> list[_Declaration]:
    """Those declarations that hold data: every duration but the method's no-data one."""
    return [holder for holder in declared if holder.duration != no_data]


def _beyond_the_vocabulary(
    holders: Iterable[_Declaration],
    vocabulary: Mapping[str, str],
) -> tuple[tuple[str, str], ...]:
    """The holders declaring a recovery point the method has no word for: a human's business."""
    return tuple(
        (holder.dependency, holder.as_written)
        for holder in holders
        if holder.duration not in vocabulary
    )


def _tightest(holders: Sequence[_Declaration]) -> tuple[str, tuple[str, ...]]:
    """The tightest recovery point among the holders, and every dependency declaring it."""
    duration = min((holder.duration for holder in holders), key=looseness)
    return duration, tuple(holder.dependency for holder in holders if holder.duration == duration)


def derive_rpo(
    dependency_ids: Iterable[str],
    register: Register,
    method: Method,
    activity: str | None = None,
) -> Derivation:
    """Derive the activity's RPO as one of the method's own words, with the reason for it.

    `activity` (its slug): a dependency's consumer row for it stands over its own recovery point
    (190 PER-CONSUMER); without it only the entries' own recovery points are read."""
    vocabulary = words_by_duration(method)
    no_data = no_data_duration(vocabulary)
    declared, unrecognised = _declarations(dependency_ids, register, activity)
    holders = _data_holders(declared, no_data)
    unmatched = _beyond_the_vocabulary(holders, vocabulary)
    if unmatched:
        return Derivation(None, unmatched=unmatched, unrecognised=unrecognised)
    if not holders:
        if no_data is None:
            return Derivation(None, (NO_DATA_HELD,), unrecognised=unrecognised)
        return Derivation(vocabulary[no_data], unrecognised=unrecognised)
    duration, reason = _tightest(holders)
    return Derivation(vocabulary[duration], reason, unrecognised=unrecognised)
