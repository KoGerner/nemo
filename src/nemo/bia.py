"""The BIA record this run produced: how it is built, and how the room knows it is this run's.

Stage 4 is where the walk stops being reversible, and two properties of it live here because
neither is prose and neither touches the disk.

**The record is a function of the run state and of the files it was handed, and of nothing else.**
It is assembled out of what the human endorsed at stage 3 — the activities, their grids, the
sentences behind every figure — and the one thing it asks of the room is where each quote's words
are: the walk hands over the confirmed interviews, the same bytes the referee then checks, and the
record names the file each quote was found in (ticket 131, ADR-0030 decision 3). Nothing here reads
the disk, which is what makes the movement re-executable: running it twice over the same run state
and files produces the same bytes, which is what ADR-0010 requires of an interrupted side effect.

**A walk may only close over a record it produced itself.** v1 closed a room with zero referee calls
and zero record writes, because the BIA the room shipped with satisfied every check that was made.
The check is `run_id`, which is in the record's schema and is the run's own identity (ADR-0010).
It is deliberately **not** a modification time: the top-level keys of a live record on this box are
`activities, comparison, dept, plan, pp4_handoff, provenance_version, quotations,
record_schema_version, run_id, source_digests, version` — there is no `modified` among them, so a
`modified` comparison reads `None` on every real record and waves every stale one through.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from nemo.record import (
    ACTIVITIES,
    ALSO_IN,
    ANSWERS,
    DEPENDENCIES,
    DEPT,
    EVIDENCE,
    IMPACT_GRID,
    LENS,
    MBCO,
    METHOD,
    MTPD,
    OPEN_ITEMS,
    OWNER,
    PENDING_REFERRALS,
    QUOTE,
    RECOVERY_TARGET,
    REFERRALS,
    RPO,
    SOURCE_PATH,
    TRANSCRIPT_QUOTE,
    TYPE,
    Record,
)
from nemo.text import finder

#: The version of the record shape this walk writes. The room's own record carries the same key.
RECORD_SCHEMA = 1

#: Which field of the record each thing stage 3 standardised is recorded under. The labels are
#: `nemo.evidence.LABELS` and the field names are `nemo.record`'s, which is where the referee
#: reads them from too; this is the one place the two vocabularies meet. A label the interview
#: never stated leaves its field off the activity altogether, so nothing downstream can read an
#: absence as a stated figure.
FIELDS = {"MTPD": MTPD, "RTO": RECOVERY_TARGET, "RPO": RPO, "MBCO": MBCO}
#: t232: his act, where a stage-3 evidence row carries one (a Withdraw typed at the door on its
#: turn): the record cites it in the place of the row's quote.
HIS_ACT = "his_act"

STALE = ("The BIA already in your room was not produced by this walk — it carries the run {found}, "
         "and this walk is {mine}. A walk may only finish over the record it produced itself, so "
         "there is nothing here for it to close over.")
NO_RUN_AT_ALL = "no run at all"


class StaleRecord(Exception):
    """The record in the room is not the one this run produced."""

    def __init__(self, found: Any, mine: Any) -> None:
        super().__init__(STALE.format(found=found or NO_RUN_AT_ALL, mine=mine or NO_RUN_AT_ALL))
        self.found = found


def build(run: Record, files: Mapping[str, str]) -> Record:
    """The BIA record this run has produced, out of the run state and the room's readable files.

    `files` are the confirmed interviews in the order the run confirmed them, path to text — what
    `walk.readable` hands the referee too. Each quote is cited to the first of them holding its
    words (`_cited`).
    """
    find = finder(files)  # each file folded once per build, not once per quote
    return {
        "record_schema_version": RECORD_SCHEMA,
        "run_id": run["run_id"],
        DEPT: run["process"],
        # The method this BIA was judged under, and what the walk left open, are in the record
        # because ticket 16's four views are a function of the record bytes: a document that had
        # to go to the room for the horizons it lays a grid over, or for the open items it lists,
        # could be rendered twice from one record and come back different.
        METHOD: run.get(METHOD) or {},
        OPEN_ITEMS: list(run.get(OPEN_ITEMS) or []),
        ACTIVITIES: [_cited(_activity(proposed), find, str(run["transcript"]["path"]))
                     for proposed in run.get("activities") or []],
        # t256: the run's referrals, carried as they stand; no key where there are none, so a
        # record without any is the bytes it always was
        **({REFERRALS: list(run[PENDING_REFERRALS])} if run.get(PENDING_REFERRALS) else {}),
    }


def own(saved: Record | None, run_id: Any) -> Record:
    """The record in the room, iff this run produced it. Refused on run identity and on nothing
    else — never on a timestamp a real record has never carried.

    An absence is an absence rather than a value: a record carrying no run at all was produced by
    no run, least of all this one, so it is refused whatever this walk happens to be called. There
    is no spelling of "missing" here that a run could be named after and match.
    """
    found = (saved or {}).get("run_id")
    if saved is None or found is None or found != run_id:
        raise StaleRecord(found, run_id)
    return saved


def is_ours(saved: Record | None, run_id: Any) -> bool:
    """Whether the room's record is this run's, asked where the answer is not a refusal."""
    try:
        own(saved, run_id)
    except StaleRecord:
        return False
    return True


def _activity(proposed: Record) -> Record:
    """One activity as the record carries it: its grid, its figures and the quotes behind them."""
    return {
        "name": proposed["name"],
        OWNER: _owner(proposed),
        IMPACT_GRID: proposed["impact_grid"],
        EVIDENCE: _evidence(proposed),
        DEPENDENCIES: [item["asset_id"] for item in proposed["dependencies"]
                       if item["asset_id"]],
        **_stated(proposed["evidence"]),
        # t116: his answers to the referee's questions, where the stage that drafted it holds any
        **({ANSWERS: proposed[ANSWERS]} if proposed.get(ANSWERS) else {}),
    }


def _owner(proposed: Record) -> str:
    """Who this activity's own figures stand on, where the interview has somebody stating them.

    The owner-stated figures are the ones stage 3 already puts in a person's mouth on the card —
    *{speaker} stated the MTPD, so it stands as their own answer rather than as mine* — so the
    person the interview has stating them is the person the record has owning the activity. A
    transcript where nobody states one leaves the owner empty, which is the honest answer and the
    one stage 5 refuses to close a run on: a signature has to identify somebody with the authority
    to give it, and there is nobody here to match a signer against.
    """
    stated = [item["speaker"] for item in proposed["evidence"] if item["owner_stated"]]
    return str(stated[0]) if stated else ""


def _stated(statements: list[Any]) -> Record:
    """The figures the interview stated, each under the field the referee reads it back from."""
    return {FIELDS[item["label"]]: item["value"] for item in statements
            if item["label"] in FIELDS}


def _evidence(proposed: Record) -> list[Record]:
    """Every quote this activity rests on, or his act where a row carries one (t232); `_cited`
    then says where each quote's words are.

    A scored category carries its lens, because the referee refuses a score no quote is tagged for
    — and it is also what puts the exact sentence beside the score on the card.
    """
    return [item.get(HIS_ACT) or {TYPE: TRANSCRIPT_QUOTE, QUOTE: item["quote"]}
            for item in proposed["evidence"]] + [
        {TYPE: TRANSCRIPT_QUOTE, QUOTE: item["quote"], LENS: item["lens"]}
        for item in proposed["scores"]]


def _cited(activity: Record, find: Callable[[object], list[str]], bound: str) -> Record:
    """The activity with every interview quote naming the file its words were found in.

    The first file holding them, in the order the run confirmed its interviews, is `source_path`;
    every other one holding them is `also_in`, as data and never as a sentence. Words no file holds
    keep the file they were claimed from (the entry's own, else `bound`, the interview stage 3
    read), so the referee's refusal names the file that does not hold them; refused, they are never
    signed. Only an interview quote is sought: any other kind of evidence says for itself where it
    stands.
    """
    return {**activity, EVIDENCE: [_found(item, find, bound)
                                   if item.get(TYPE) == TRANSCRIPT_QUOTE else item
                                   for item in activity[EVIDENCE]]}


def _found(item: Record, find: Callable[[object], list[str]], bound: str) -> Record:
    first, *others = find(item[QUOTE]) or [item.get(SOURCE_PATH) or bound]
    rest = {key: value for key, value in item.items() if key not in (SOURCE_PATH, ALSO_IN)}
    return {**rest, SOURCE_PATH: first, **({ALSO_IN: others} if others else {})}
