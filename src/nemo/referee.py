"""The referee: the deterministic check that must pass before anything is saved.

It is a referee, not a validator and not a gate. A **rejection** is a structural or integrity
defect — a fabricated quote, a grid that cannot be read, a claim the method does not allow. A
**finding** is what the referee will not resolve on the human's behalf: it is data carried to the
card and to the signature, never a wall.

Ported from v1's `bia_referee.py`, whose checks came in turn from the demo engine's `validate`.
The gate bookkeeping did not come with them: there is no save token, no peppered finding tag and
no writing back into the record. `review` reads; it reports; it records nothing.

Two rules read differently here than in v1, on `CONTEXT.md`'s wording of *Referee*: the MTPD is
**derived**, so an asserted one that the grid does not support is a finding rather than a refusal,
and an RTO that is not strictly inside its MTPD is a refusal unless the gap is acknowledged.
"""

from __future__ import annotations

import datetime
import itertools
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# The duration reader is `nemo.duration`'s, at the bottom of the layers. It was private here, and
# `nemo.next_step` and the skin — which read the same number — reached across this seam for it
# fifteen times, so ticket 130's nudge changed them without naming them (ticket 218). Bound to a
# private name for the same reason as the two below.
from nemo.duration import minutes as _minutes
from nemo.duration import upper_edge as _upper_edge
from nemo.duration import worst_case as _worst_case

# The grid derivation is `nemo.impact`'s, below this module and below `nemo.views`, because both
# need the figure and neither is a client of the other. Bound to private names for the same reason
# as `nemo.method`'s below: every call site here still reads as the referee's own.
from nemo.impact import NO_MTPD as _NO_MTPD
from nemo.impact import canonicalize_grid as _canonicalize_grid
from nemo.impact import derive_mtpd
from nemo.impact import is_score as _is_score
from nemo.impact import unrated_bands as _unrated_bands
from nemo.impact import worst_case_row as _worst_case_row

# The method's parameter names are `nemo.method`'s, not this module's: `walk` copies the same
# five onto the record (and the beyond word where a method states one) and the two spellings
# must not be able to drift.
from nemo.method import beyond_horizons as _beyond_horizons
from nemo.method import horizons as _horizons
from nemo.method import lenses as _lenses
from nemo.method import rpo_vocabulary as _rpo_vocabulary

# The record's field names are `nemo.record`'s for the same reason: `nemo.bia` writes the
# activity this module reads back, the two may not import each other, and a figure filed under a
# name this one does not read is a figure nobody checks.
from nemo.record import (
    ACTIVITIES,
    ACTIVITY,
    ANSWERS,
    ASSET_ID,
    ASSET_IDS,
    CHAT_CONFIRMATION,
    DEPENDENCIES,
    DEPT,
    EVIDENCE,
    IMPACT_GRID,
    LENS,
    MTPD,
    ON,
    QUOTE,
    RECOVERY_TARGET,
    REGISTER_NO_RPO,
    REGISTER_ROW,
    RPO,
    SOURCE_PATH,
    TRANSCRIPT_QUOTE,
    TURN_ID,
    TYPE,
    UNRATED_BAND_ACK,
    WORDS,
)

# Every way this referee can refuse a record is a name in `nemo.refusal`, below this module
# and below `nemo.walk`: the referee decides that a record cannot be saved, the walk writes
# the sentence a manager reads about it, and neither is the other's source for the names.
from nemo.refusal import (
    BAND_UNSCORED,
    BOUNDARY,
    EVIDENCE_UNCHECKED,
    HANDOFF_ITEM,
    INVALID_SCORE,
    LENS_UNQUOTED,
    MALFORMED_ACTIVITY,
    MISSING_HORIZONS,
    MISSING_LENSES,
    NO_ACTIVITIES,
    NO_RECOVERY_TARGET,
    OWNER_NOT_A_PERSON,
    QUOTE_NOT_FOUND,
    REVIEW_DATE_PASSED,
    REVIEW_DATE_UNUSABLE,
    RPO_NOT_ALLOWED,
    TARGET_OUTSIDE_MTPD,
    UNKNOWN_HORIZONS,
    UNKNOWN_LENS,
    UNRATED_BAND_NEEDS_OWNER,
    UNREADABLE_EVIDENCE,
    UNREADABLE_GRID,
    UNREADABLE_ROW,
    UNREADABLE_TARGET,
    UNSCORED_NEEDS_OWNER,
    UNSIGNED_ACK,
    Rejection,
)
from nemo.text import (
    found_in,  # the one comparison: bia names the file with it (ticket 131)
    norm,  # the project's one normalizer: tolerate typography, never reword
)

EVIDENCE_TYPES = ("company_file", "prior_bia", "prior_cycle", TRANSCRIPT_QUOTE, CHAT_CONFIRMATION,
                  REGISTER_ROW, REGISTER_NO_RPO)

#: What each check is called once it has actually run, in the manager's words. A clause reaches a
#: receipt because the check that names it ran over this record and for no other reason: stage 4's
#: sentence is assembled from `Verdict.checked`, so a run that refereed nothing has nothing to say.
#: v1's closure note was a literal asserting "record validated and saved" whatever the run did, and
#: a literal is unfalsifiable — this is the same sentence made false-impossible instead.
QUOTES_CHECK = "found every quote word for word in a file in your room"
GRID_CHECK = "read the grid across every category and horizon your method names"
MTPD_CHECK = "derived the MTPD from that grid rather than taking the one you were told"
RTO_CHECK = "held the recovery target against the MTPD it belongs to"
RPO_CHECK = "checked the data-loss answer against the words your method allows"
BOUNDARY_CHECK = "confirmed this is still a BIA and not a continuity plan"

_PLAN_MARKERS = (
    "immediate actions", "recovery actions", "invocation trigger", "roles and responsibilities",
    "roles & responsibilities", "action card", "declare an incident", "declare incident",
    "0-1 hour", "step 1:", "activate the plan",
)
_AI_WORDS = {"ai", "assistant", "llm", "model", "gpt", "claude", "glm", "bot", "agent"}
_PP4_PREFIX = re.compile(r"^(gap|option|human decisions?|missing evidence)\b")
REVIEW_DATE = "review_date"
_ACK_FIELDS = (
    ("approved_by", 'not_elicited_ack needs "approved_by" — the sponsor or management, never the '
                    "analyst who ran the interview"),
    ("reason", 'not_elicited_ack needs a "reason" naming what was asked and declined — an '
               "acceptance that does not say what it accepted cannot be audited later"),
    ("review_owner", 'not_elicited_ack needs "review_owner" — the person who gets asked at the '
                     "review date. A date with nobody against it is a deferral, not a plan"),
    ("next_question", 'not_elicited_ack needs "next_question" — what would have to be answered '
                      "to produce a number, so the review has something to test"),
    ("owner_informed", 'not_elicited_ack needs "owner_informed" — the owner who declined is told '
                       "that a document records their declining, and who told them is part of "
                       "the record"),
)
#: What a named acknowledgement of an unrated band carries (ADR-0050): `not_elicited_ack`'s first
#: three fields, in its order.
_BAND_ACK_FIELDS = ("approved_by", "reason", "review_owner")
_NO_ACK = (
    "the impact grid is entirely unscored. That is a legitimate outcome — an owner may decline "
    "every figure, and inventing one is the failure this referee exists to prevent — but "
    "somebody has to own it. Record who accepts the unscored assessment and why, with "
    '{"not_elicited_ack": {"approved_by": "<sponsor/management name>", "review_date": '
    '"<YYYY-MM-DD>", "reason": "<what was asked and declined>", "review_owner": "<who gets asked '
    'at the review>", "next_question": "<what answer would produce a number>", "owner_informed": '
    '"<who told them>"}} on the activity.'
)


#: t116: the one finding class that asks the manager something, a figure he asserted against the
#: one the method derives. Its question key, and the two answers the record can carry to it (the
#: third, withdrawing it, is the derived figure on the record, so nothing is asked).
ASSERTED_MTPD = f"{MTPD}.asserted"
KEEP = "keep"
LEAVE_OPEN = "leave_open"
#: withdrawn: the record carries the grid's figure, so nothing is asked; the answer is kept in the
#: decision trail with the quote that stated the withdrawn figure (14_nemo_check's ruling (b))
WITHDRAW = "withdraw"
#: What the finding's line says once he has answered, in nemo's fixed words, never his or a model's
#: except the reason he typed himself, word for word.
KEPT_SAYS = ". The manager's answer: kept, with his reason, word for word: {reason}"
KEPT_NO_REASON_SAYS = ". The manager's answer: kept, no reason given"
LEFT_OPEN_SAYS = ". The manager's answer: left open for the owners, his decision"
WITHDRAWN_SAYS = ". The manager's answer: withdrawn, the grid's figure stands"


def answer_says(answer: str, reason: str | None = None) -> str:
    """The fixed words the line carries after his answer (`KEEP` or `LEAVE_OPEN`)."""
    if answer == LEAVE_OPEN:
        return LEFT_OPEN_SAYS
    if answer == WITHDRAW:
        return WITHDRAWN_SAYS
    return KEPT_SAYS.format(reason=reason) if reason else KEPT_NO_REASON_SAYS


def his_answers(answer: str, asserted: object, derived: object, reason: str | None = None,
                quote: str | None = None) -> dict[str, Any]:
    """His answer to the MTPD question, as the record carries it (`ANSWERS`): the answer, the two
    figures it answered, his reason word for word where he gave one, the quote that stated a
    withdrawn figure (14_nemo_check's ruling (b)), and nemo's fixed words for it.

    The one writer (t224): moved here from the phone skin's `_answers` byte for byte, so the walk
    and the skin cannot come to spell the entry apart. A withdrawal carries no reason.
    """
    reason = None if answer == WITHDRAW else reason
    return {ANSWERS: {ASSERTED_MTPD: {
        "answer": answer, "asserted": asserted, "derived": derived,
        **({"reason": reason} if reason else {}),
        **({"quote": quote} if answer == WITHDRAW and quote else {}),
        "says": answer_says(answer, reason).removeprefix(". ")}}}


@dataclass(frozen=True)
class Question:
    """A finding that asks the manager something, open until the record carries his answer.

    Its id is built from the activity and the field, never from where it falls in a list the way
    an open item's `OPEN-n` is, so an answer keyed by it survives a finding added before it.
    """

    activity: str
    key: str
    asserted: str
    derived: str

    @property
    def id(self) -> str:
        return f"{self.activity}.{self.key}"


@dataclass
class Verdict:
    """What the referee saw. Nothing else: it does not record that it looked."""

    rejections: list[Rejection] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    #: t116: what it asks the manager and he has not answered; a step answer never settles one.
    questions: list[Question] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when nothing blocks the save. Findings ride along with a pass."""
        return not self.rejections

    def ran(self, check: str) -> None:
        """Record that a check ran over this record, once however many activities it ran over."""
        if check not in self.checked:
            self.checked.append(check)


def _squash(value: object) -> str:
    """`norm` with every space dropped, so '24 h' and '24h' are one key."""
    return re.sub(r"\s+", "", norm(value))


def _same_horizon(left: object, right: object) -> bool:
    """True when two labels name one horizon despite typography or unit."""
    if _squash(left) == _squash(right):
        return True
    minutes = _minutes(left)
    return minutes is not None and minutes == _minutes(right)


def _has_plan_language(text: object) -> bool:
    normalized = norm(text)
    return any(marker in normalized for marker in _PLAN_MARKERS)


def _plan_language_findings(where: str, text: object, note: str = "") -> list[str]:
    """The PP4 finding raised wherever the record starts drafting; `where` names the place.

    Plan language is never a refusal: the boundary is the human's to judge, so it rides to the
    card as a finding. `_review_boundary` refuses only a plan the record actually carries.
    """
    if not _has_plan_language(text):
        return []
    return [f"Human decisions: possible plan-drafting language in {where} — review against the "
            f"PP4 boundary{note}"]


# ── the grid ─────────────────────────────────────────────────────────────────
def _horizon_list_rejection(aid: str, lens: str, kind: str, what: str,
                          horizons: list[str]) -> list[Rejection]:
    if not horizons:
        return []
    return [Rejection(kind, f"activity {aid}: impact_grid[{lens!r}] {what}: {horizons}",
                      activity=aid, lens=lens, horizons=tuple(horizons))]


def _horizon_rejections(aid: str, lens: str, row: Mapping[str, Any],
                      horizons: list[str]) -> list[Rejection]:
    """Every horizon the method names, and nothing it does not."""
    return (_horizon_list_rejection(aid, lens, UNKNOWN_HORIZONS, "has unknown horizon(s)",
                                  [h for h in row if h not in horizons])
            + _horizon_list_rejection(aid, lens, MISSING_HORIZONS, "missing horizon(s)",
                                    [h for h in horizons if h not in row]))


def _score_rejections(aid: str, lens: str, row: Mapping[str, Any]) -> list[Rejection]:
    return [Rejection(INVALID_SCORE,
                      f"activity {aid}: impact_grid[{lens!r}][{h!r}] invalid score {v!r} "
                      "(1-5 or 'MISSING')",
                      activity=aid, lens=lens, horizon=h, score=v)
            for h, v in row.items() if v != "MISSING" and not _is_score(v)]


def _row_rejections(aid: str, lens: str, row: object, horizons: list[str]) -> list[Rejection]:
    if not isinstance(row, dict):
        return [Rejection(UNREADABLE_ROW,
                          f"activity {aid}: impact_grid[{lens!r}] must be an object of "
                          f"{{horizon: score}}, got {type(row).__name__}",
                          activity=aid, lens=lens)]
    return _horizon_rejections(aid, lens, row, horizons) + _score_rejections(aid, lens, row)


def _shape_rejections(aid: str, grid: Mapping[str, Any],
                    method: Mapping[str, Any]) -> list[Rejection]:
    lenses = _lenses(method)
    rejections = [Rejection(UNKNOWN_LENS,
                            f"activity {aid}: impact_grid lens {lens!r} is not a method scenario "
                            f"id — method scenario ids: {sorted(lenses)}",
                            activity=aid, lens=lens)
                  for lens in grid if lens not in lenses]
    absent = sorted(set(lenses) - set(grid))
    if absent:
        rejections.append(Rejection(
            MISSING_LENSES, f"activity {aid}: impact_grid missing lens row(s): {absent}",
            activity=aid, lenses=tuple(absent)))
    horizons = _horizons(method)
    for lens, row in grid.items():
        if lens in lenses:
            rejections += _row_rejections(aid, lens, row, horizons)
    return rejections


def _unscored_rejections(
    aid: str, grid: Mapping[str, Any], method: Mapping[str, Any], ack: object, band_acks: object
) -> list[Rejection]:
    """A band the source left unrated is filable once named; so is a grid with no figure at all.

    Being honest about one lens is allowed. A time band no lens rated is filable only with a
    named acknowledgement of that band (ticket 376, ADR-0050), and an interview that produced no
    figures anywhere is a different event, filable once a named sponsor owns it.
    """
    horizons = _horizons(method)
    unscored = _unrated_bands(grid, horizons)
    if not unscored:
        return []
    if len(unscored) < len(horizons):
        return [r for h in unscored for r in _band_rejections(aid, h, _band_ack(band_acks, h))]
    return _ack_rejections(aid, ack)


def _band_ack(acks: object, band: str) -> object:
    """The acknowledgement filed under this band, in any spelling of it, or None."""
    if not isinstance(acks, dict):
        return None
    return next((ack for key, ack in acks.items() if _squash(key) == _squash(band)), None)


def _band_rejections(aid: str, band: str, ack: object) -> list[Rejection]:
    """An unrated band with no acknowledgement, or with one that leaves a field blank."""
    if not isinstance(ack, dict):
        return [Rejection(BAND_UNSCORED,
                          f"activity {aid}: impact_grid horizon {band!r} has no scored lens "
                          "(all MISSING) — cannot derive MTPD",
                          activity=aid, horizon=band)]
    missing = tuple(key for key in _BAND_ACK_FIELDS if not str(ack.get(key) or "").strip())
    if not missing:
        return []
    return [Rejection(UNRATED_BAND_NEEDS_OWNER,
                      f"activity {aid}: {UNRATED_BAND_ACK}[{band!r}] needs {list(missing)}",
                      activity=aid, horizon=band, missing=missing)]


def _ack_rejections(aid: str, ack: object) -> list[Rejection]:
    """What the acknowledgement of a wholly unscored grid still needs, prefixed with the activity.

    The five field rejections are one refusal and not five: they are one thing missing from one
    acknowledgement, and a card that said the same sentence five times over would be the referee's
    list of fields wearing prose. The developer's line keeps all five, as it always did.
    """
    if not isinstance(ack, dict):
        return [_no_ack_rejection(aid)]
    return _unowned_rejections(aid, ack) + _review_date_rejections(aid, ack.get(REVIEW_DATE))


def _no_ack_rejection(aid: str) -> Rejection:
    """No acknowledgement at all, so every field is missing — the review date among them."""
    return Rejection(UNSCORED_NEEDS_OWNER, f"activity {aid}: {_NO_ACK}", activity=aid,
                     missing=tuple(key for key, _text in _ACK_FIELDS) + (REVIEW_DATE,))


def _missing_ack_fields(ack: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The acknowledgement fields left blank, each with the developer's line that says why."""
    return [(key, text) for key, text in _ACK_FIELDS if not str(ack.get(key) or "").strip()]


def _unowned_rejections(aid: str, ack: Mapping[str, Any]) -> list[Rejection]:
    """The blank fields as one refusal: one acknowledgement is incomplete, not five of them."""
    missing = _missing_ack_fields(ack)
    if not missing:
        return []
    return [Rejection(UNSCORED_NEEDS_OWNER,
                      " ".join(f"activity {aid}: {text}" for _key, text in missing),
                      activity=aid, missing=tuple(key for key, _text in missing))]


def _review_date_rejections(aid: str, raw: object) -> list[Rejection]:
    try:
        review_date = datetime.date.fromisoformat(str(raw).strip())
    except ValueError:
        return [Rejection(
            REVIEW_DATE_UNUSABLE,
            f'activity {aid}: not_elicited_ack needs a usable "review_date" as an ISO date '
            "(YYYY-MM-DD) — an acceptance without one is not an acceptance, it is a shrug",
            activity=aid)]
    if review_date < datetime.date.today():
        return [Rejection(
            REVIEW_DATE_PASSED,
            f"activity {aid}: the not_elicited_ack review date ({review_date.isoformat()}) has "
            "passed — the unscored assessment is due for review. Re-accept with a new "
            "review_date, or go back to the owner for the figures",
            activity=aid, date=review_date.isoformat())]
    return []


def _claimed_lenses(grid: Mapping[str, Any]) -> set[str]:
    """The lenses this grid makes a claim about — any cell at 2 or above. 1 is negligible."""
    return {lens for lens, row in grid.items() if isinstance(row, dict)
            and any(_is_score(v) and v >= 2 for v in row.values())}


def _lens_quote_rejections(
    aid: str, grid: Mapping[str, Any], method: Mapping[str, Any], evidence: Sequence[Any]
) -> list[Rejection]:
    tagged = {e.get(LENS) for e in evidence if isinstance(e, dict)}
    claimed = sorted(_claimed_lenses(grid) & set(_lenses(method)))
    return [Rejection(LENS_UNQUOTED,
                      f"activity {aid}: impact_grid[{lens!r}] is scored but no evidence item "
                      f"carries lens {lens!r} — tag the quote that supports the score with "
                      f"lens={lens!r}, or set the row to 'MISSING'",
                      activity=aid, lens=lens)
            for lens in claimed if lens not in tagged]


def _lenses_by_quote(claimed: set[str], evidence: Sequence[Any]) -> dict[str, set[str]]:
    by_quote: dict[str, set[str]] = {}
    for item in evidence:
        if isinstance(item, dict) and item.get(LENS) in claimed:
            by_quote.setdefault(norm(_quote_of(item)), set()).add(item[LENS])
    return by_quote


def _reused_quotes(grid: Mapping[str, Any], evidence: Sequence[Any]) -> list[list[str]]:
    """The lens sets that rest on one and the same quote."""
    by_quote = _lenses_by_quote(_claimed_lenses(grid), evidence)
    return sorted(sorted(lenses) for text, lenses in by_quote.items()
                  if text and len(lenses) > 1)


def _ack_signer(ack: object) -> tuple[str, set[str]]:
    """Who signed the shared-quote acknowledgement, and which lenses they signed for."""
    if not isinstance(ack, dict):
        return "", set()
    return str(ack.get("approved_by") or "").strip(), set(ack.get("lenses") or [])


def _shared_quotes(
    verdict: Verdict, aid: str, grid: Mapping[str, Any], evidence: Sequence[Any], ack: object
) -> None:
    """Reuse is a judgement call for whoever signs — unless the acknowledgement is unsigned.

    A value was supplied but carries no name: that is a false claim rather than silence, and it
    stays a refusal. Genuine absence is the finding.
    """
    who, named = _ack_signer(ack)
    unsigned = ack is not None and not who
    for lenses in _reused_quotes(grid, evidence):
        if who and set(lenses) <= named:
            continue
        if unsigned:
            verdict.rejections.append(_unsigned_ack_text(aid, lenses))
        else:
            verdict.findings.append(_reuse_finding_text(aid, lenses))


def _unsigned_ack_text(aid: str, lenses: list[str]) -> Rejection:
    return Rejection(UNSIGNED_ACK,
                     f"activity {aid}: shared_quote_ack was supplied for {lenses} but has no "
                     "approved_by — an unsigned entry is not an acknowledgement",
                     activity=aid, lenses=tuple(lenses))


def _reuse_finding_text(aid: str, lenses: list[str]) -> str:
    return (f"Human decisions: activity {aid} — the same quote is the evidence for {lenses}. One "
            f"quote cannot be what supports {len(lenses)} different impact categories unless a "
            "human confirms it. Quote the span that supports each category separately, or record "
            f'{{"shared_quote_ack": {{"lenses": {lenses}, '
            '"approved_by": "<name of the person approving>"}}')


def _falling_horizons(worst: Mapping[str, int], method: Mapping[str, Any]) -> list[str]:
    present = [h for h in _horizons(method) if h in worst]
    return [f"impact falls from {worst[a]} at {a} to {worst[b]} at {b}"
            for a, b in itertools.pairwise(present) if worst[b] < worst[a]]


# ── the evidence ─────────────────────────────────────────────────────────────
def _quote_of(item: Mapping[str, Any]) -> str:
    return str(item.get(QUOTE) or item.get("ref") or "")


def _looks_like_source_path(value: str) -> bool:
    text = value.strip().lower()
    return "/" in text and text.endswith((".md", ".json", ".jsonl", ".txt"))


def _resolve(source_path: str, files: Mapping[str, str]) -> tuple[str, str] | None:
    """The room file a cited path names, without guessing between two candidates."""
    wanted = source_path.strip().lstrip("/")
    if wanted in files:
        return wanted, files[wanted]
    matches = [(path, text) for path, text in files.items()
               if wanted.endswith("/" + path) or path.endswith("/" + wanted)]
    return matches[0] if len(matches) == 1 else None


def _cited_file_rejections(
    aid: str, kind: object, quote: str, source_path: str, files: Mapping[str, str]
) -> list[Rejection]:
    resolved = _resolve(source_path, files)
    if resolved is None:
        return [Rejection(EVIDENCE_UNCHECKED,
                          f"activity {aid}: evidence source_path not found or ambiguous: "
                          f"{source_path!r}", activity=aid)]
    if not found_in(quote, dict([resolved])):
        return [Rejection(QUOTE_NOT_FOUND,
                          f"activity {aid}: {kind} quote not found in {resolved[0]!r} "
                          f"(possible fabrication): {quote!r}", activity=aid, quote=quote)]
    return []


def _verbatim_rejections(
    aid: str, kind: object, quote: str, source_path: str, files: Mapping[str, str]
) -> list[Rejection]:
    if not files:
        return [Rejection(EVIDENCE_UNCHECKED,
                          f"activity {aid}: {kind} evidence cannot be verified — no file in the "
                          "room is readable, so nothing was checked. Cite the file the words come "
                          "from in source_path", activity=aid)]
    if source_path:
        return _cited_file_rejections(aid, kind, quote, source_path, files)
    if found_in(quote, files):
        return []
    return [Rejection(QUOTE_NOT_FOUND,
                      f"activity {aid}: {kind} quote not found in any readable file in the room "
                      f"(possible fabrication): {quote!r}", activity=aid, quote=quote)]


def _quote_shape_rejections(aid: str, item: Mapping[str, Any]) -> list[Rejection]:
    """Why this item does not carry a quote at all ([] = it does)."""
    kind = item.get(TYPE)
    legacy_ref = item.get("ref")
    if kind not in EVIDENCE_TYPES:
        return [Rejection(UNREADABLE_EVIDENCE,
                          f"activity {aid}: unknown evidence type {kind!r} "
                          f"(allowed: {sorted(EVIDENCE_TYPES)})", activity=aid)]
    if (not item.get(QUOTE) and isinstance(legacy_ref, str)
            and _looks_like_source_path(legacy_ref)):
        return [Rejection(UNREADABLE_EVIDENCE,
                          f"activity {aid}: evidence.ref contains a file path, not a quote; use "
                          f'{{"type": {kind!r}, "quote": "exact contiguous text", '
                          f'"source_path": {legacy_ref!r}}}', activity=aid)]
    if not norm(_quote_of(item)):
        return [Rejection(UNREADABLE_EVIDENCE, f"activity {aid}: {kind} evidence quote is empty",
                          activity=aid)]
    return []


def _quote_rejections(aid: str, item: Mapping[str, Any],
                    files: Mapping[str, str]) -> list[Rejection]:
    rejections = _quote_shape_rejections(aid, item)
    if rejections:
        return rejections
    return _verbatim_rejections(aid, item.get(TYPE), _quote_of(item),
                              str(item.get(SOURCE_PATH) or ""), files)


def _confirmation_rejections(aid: str, item: Mapping[str, Any],
                             turns: Mapping[str, Mapping[str, str]]) -> list[Rejection]:
    """Ticket 132 (ADR-0030): a chat confirmation is his, or it is refused. Its turn is in the
    room's turn file, its words are his words on that turn (by the one comparison), and its day
    is that turn's. A model call cannot put words into one that are not on his turn.

    It is refused under the two kinds a quote is, and adds none: words that are not his are
    words not found (`QUOTE_NOT_FOUND`, the words as the quote); a turn the file does not hold,
    or holds on another day, is evidence nothing could be checked against (`EVIDENCE_UNCHECKED`).
    """
    turn_id = str(item.get(TURN_ID) or "")
    turn = turns.get(turn_id)
    if turn is None:
        return [Rejection(EVIDENCE_UNCHECKED,
                          f"activity {aid}: a chat confirmation names turn {turn_id!r}, which the "
                          "room's turn file does not hold", activity=aid, turn=turn_id,
                          on=item.get(ON))]
    words = str(item.get(WORDS) or "")
    if not _his_words(words, turn):
        return [Rejection(QUOTE_NOT_FOUND, f"activity {aid}: a chat confirmation's words "
                          f"{words!r} are not his on turn {turn_id!r}",
                          activity=aid, quote=words, turn=turn_id, on=turn.get(ON))]
    if item.get(ON) != turn.get(ON):
        return [Rejection(EVIDENCE_UNCHECKED, f"activity {aid}: a chat confirmation is dated "
                          f"{item.get(ON)!r}, and turn {turn_id!r} was on {turn.get(ON)!r}",
                          activity=aid, turn=turn_id, on=turn.get(ON), claimed=item.get(ON))]
    return []


def _his_words(words: str, turn: Mapping[str, str]) -> bool:
    """A chat confirmation's words are his on its turn: some words, found by the one comparison."""
    return bool(norm(words) and found_in(words, {WORDS: str(turn.get(WORDS) or "")}))


def _register_of(source_path: str, files: Mapping[str, str]) -> dict[str, Any] | None:
    """The register a row names, parsed: None where the room holds no such file, or the file does
    not read as a register (not JSON, or JSON that is no mapping)."""
    resolved = _resolve(source_path, files)
    if resolved is None:
        return None
    try:
        register = json.loads(resolved[1])
    except ValueError:
        return None
    return register if isinstance(register, dict) else None


def _held(register: Mapping[str, Any], asset: str, activity: str) -> set[str]:
    """Every value the register's entry for `asset` holds FOR `activity`, normalized (t171-shape,
    DRAFT): an entry with `consumers` holds only its consumer row's RPO for that department; one
    with none holds its own strings for every activity; no such entry holds nothing."""
    entry = register.get(asset)
    if not isinstance(entry, dict):
        return set()
    if "consumers" not in entry:
        return {norm(v) for v in entry.values() if isinstance(v, str)}
    return _consumer_held(entry["consumers"], activity)


def _consumer_held(rows: object, activity: str) -> set[str]:
    """The RPO an entry's consumer rows give `activity`, normalized, where its row names one."""
    return {norm(row[RPO]) for row in rows if isinstance(row, dict)
            and row.get("department") == activity and isinstance(row.get(RPO), str)} \
        if isinstance(rows, list) else set()


def _register_or_unchecked(aid: str, item: Mapping[str, Any], files: Mapping[str, str],
                           ) -> tuple[dict[str, Any] | None, list[Rejection]]:
    """The register a row names, or the rejection saying nothing could be checked."""
    source_path = str(item.get(SOURCE_PATH) or "")
    register = _register_of(source_path, files)
    if register is not None:
        return register, []
    return None, [Rejection(EVIDENCE_UNCHECKED,
                            f"activity {aid}: {item.get(TYPE)} names {source_path!r}, which is no "
                            "register the room holds, so nothing was checked", activity=aid)]


def _register_row_rejections(aid: str, item: Mapping[str, Any], files: Mapping[str, str],
                             dept: str) -> list[Rejection]:
    """Ticket 171: a register row is the room's register's own words for the asset it names, for
    the record's own activity. Its file is one the room holds and reads as a register, and its
    quote is the value that asset's entry holds for that activity (by the one normalizer), not
    another activity's row and not words found anywhere else in the file."""
    register, unchecked = _register_or_unchecked(aid, item, files)
    if register is None:
        return unchecked
    quote, asset = _quote_of(item), str(item.get(ASSET_ID) or "")
    if item.get(ACTIVITY) == dept and norm(quote) and norm(quote) in _held(register, asset, dept):
        return []
    return [Rejection(QUOTE_NOT_FOUND,
                      f"activity {aid}: register_row quote not held for {asset!r} for "
                      f"{item.get(ACTIVITY)!r} in {item.get(SOURCE_PATH)!r} (possible "
                      f"fabrication): {quote!r}", activity=aid, quote=quote)]


def _naming_a_figure(register: Mapping[str, Any], assets: list[Any], dept: str) -> list[str]:
    """Those of `assets` whose register entry names a figure for `dept`, sorted."""
    return sorted({str(a) for a in assets if _held(register, str(a), dept)})


def _no_rpo_rejections(aid: str, item: Mapping[str, Any], files: Mapping[str, str], dept: str,
                       listed: list[Any]) -> list[Rejection]:
    """t171-shape (DRAFT): the register gives the record's activity no RPO: no dependency the row
    or the activity lists names a figure for it in the room's register."""
    register, unchecked = _register_or_unchecked(aid, item, files)
    if register is None:
        return unchecked
    named = _naming_a_figure(register, [*(item.get(ASSET_IDS) or []), *listed], dept)
    if item.get(ACTIVITY) == dept and not named:
        return []
    return [Rejection(QUOTE_NOT_FOUND,
                      f"activity {aid}: register_no_rpo for {item.get(ACTIVITY)!r}, but the "
                      f"register names a figure for {dept!r} in {named} (possible fabrication)",
                      activity=aid, quote=str(named))]


def _lens_rejections(aid: str, item: Mapping[str, Any],
                     method: Mapping[str, Any]) -> list[Rejection]:
    """An evidence item's lens, where it names one, is one of the method's scenario ids."""
    lens = item.get(LENS)
    if lens is None or lens in _lenses(method):
        return []
    return [Rejection(
        UNKNOWN_LENS,
        f"activity {aid}: evidence lens {lens!r} is not a method scenario id — "
        f"method scenario ids: {sorted(_lenses(method))}", activity=aid, lens=lens)]


def _kind_rejections(aid: str, item: Mapping[str, Any], files: Mapping[str, str],
                     turns: Mapping[str, Mapping[str, str]] | None,
                     activity: Mapping[str, Any]) -> list[Rejection]:
    """The check the item's type calls for: his turn, the register, or a quote in its file."""
    if item.get(TYPE) == CHAT_CONFIRMATION:
        return _confirmation_rejections(aid, item, turns or {})
    if item.get(TYPE) in (REGISTER_ROW, REGISTER_NO_RPO):
        return _register_rejections(aid, item, files, activity)
    return _quote_rejections(aid, item, files)


def _register_rejections(aid: str, item: Mapping[str, Any], files: Mapping[str, str],
                         activity: Mapping[str, Any]) -> list[Rejection]:
    """A register row, or the register's no-RPO row, held against the room's register for the
    record's own department (t171-shape, DRAFT)."""
    dept = str(activity.get(DEPT) or "")
    if item.get(TYPE) == REGISTER_ROW:
        return _register_row_rejections(aid, item, files, dept)
    return _no_rpo_rejections(aid, item, files, dept, activity.get(DEPENDENCIES) or [])


def _evidence_rejections(
    aid: str, item: object, method: Mapping[str, Any], files: Mapping[str, str],
    turns: Mapping[str, Mapping[str, str]] | None = None,
    activity: Mapping[str, Any] | None = None,
) -> list[Rejection]:
    if not isinstance(item, dict):
        return [Rejection(UNREADABLE_EVIDENCE,
                          f"activity {aid}: malformed evidence item (expected an object with "
                          f"type/quote/source_path, got {type(item).__name__})", activity=aid)]
    return _lens_rejections(aid, item, method) + _kind_rejections(aid, item, files, turns,
                                                                  activity or {})


def _evidence_of(activity: Mapping[str, Any]) -> list[Any]:
    """Whatever the activity filed as evidence, as a list — a non-list is one malformed item."""
    evidence = activity.get(EVIDENCE) or []
    return evidence if isinstance(evidence, list) else [evidence]


# ── one activity ─────────────────────────────────────────────────────────────
def _review_grid(
    verdict: Verdict, aid: str, activity: Mapping[str, Any], method: Mapping[str, Any]
) -> str | None:
    """Judge the grid and return the MTPD it derives, or None when it cannot be judged."""
    raw = activity.get(IMPACT_GRID)
    if not isinstance(raw, dict):
        verdict.rejections.append(Rejection(
            UNREADABLE_GRID, f"activity {aid}: impact_grid must be an object of "
            f"{{lens: {{horizon: score}}}}, got {type(raw).__name__}", activity=aid))
        return None
    grid = _canonicalize_grid(raw, method)
    evidence = _evidence_of(activity)
    rejections = _shape_rejections(aid, grid, method) + _lens_quote_rejections(
        aid, grid, method, evidence)
    _shared_quotes(verdict, aid, grid, evidence, activity.get("shared_quote_ack"))
    if not rejections:
        rejections = _unscored_rejections(aid, grid, method, activity.get("not_elicited_ack"),
                                          activity.get(UNRATED_BAND_ACK))
    verdict.rejections += rejections
    if rejections:
        return None
    verdict.ran(GRID_CHECK)
    worst = _worst_case_row(grid)
    verdict.findings += [
        f"Gap: activity {aid}: the worst case improves with time — {fall}. A later outage "
        "cannot hurt less than an earlier one; say why, or correct the grid"
        for fall in _falling_horizons(worst, method)]
    mtpd = derive_mtpd(worst, method)
    verdict.ran(MTPD_CHECK)
    _review_asserted_mtpd(verdict, aid, activity.get(MTPD), mtpd, _beyond_horizons(method),
                          (activity.get(ANSWERS) or {}).get(ASSERTED_MTPD))
    return mtpd


def _review_asserted_mtpd(
    verdict: Verdict, aid: str, asserted: object, derived: str, beyond: str | None,
    answer: object = None,
) -> None:
    """An asserted MTPD the grid does not support is a finding. The method's own word for past
    the last horizon (`beyond_horizons`, t139) agrees with a grid that never crosses and with
    nothing else; read from the method, never a literal, so a method without one has no such word.

    t116: it is also a question, open until the record carries his answer to these two figures
    (`KEEP` or `LEAVE_OPEN`, `ANSWERS`). An answer to other figures answers nothing, so a later
    change to either reopens it (amendment 1). His answer is said after the finding's own words.
    """
    if asserted is None or _grid_agrees(asserted, derived, beyond):
        return
    said = (f"Gap: activity {aid}: the grid derives an MTPD of {derived!r}, not the asserted "
            f"{asserted!r} — the MTPD comes from the grid, so the assertion is the thing to "
            "explain or withdraw")
    if isinstance(answer, dict) and _answers(answer, str(asserted), str(derived)):
        verdict.findings.append(said + answer_says(answer["answer"], answer.get("reason")))
        return
    verdict.findings.append(said)
    verdict.questions.append(Question(aid, ASSERTED_MTPD, str(asserted), str(derived)))


def _grid_agrees(asserted: object, derived: str, beyond: str | None) -> bool:
    """Whether the grid's MTPD supports the asserted one: the method's word for past the last
    horizon agrees only with a grid that never crosses; any other figure, only with its horizon."""
    if beyond is not None and _squash(asserted) == _squash(beyond):
        return derived == _NO_MTPD
    return _same_horizon(asserted, derived)


def _answers(answer: object, asserted: str, derived: str) -> bool:
    """Whether a stored answer answers this question: a known answer, to exactly these figures."""
    return (isinstance(answer, dict) and answer.get("answer") in (KEEP, LEAVE_OPEN)
            and answer.get("asserted") == asserted and answer.get("derived") == derived)


def _both_beyond(target: object, mtpd: str | None, beyond: str | None) -> bool:
    """True when the RTO is the method's beyond word and the MTPD is past the horizons too."""
    if beyond is None or not target or _squash(target) != _squash(beyond):
        return False
    return mtpd == _NO_MTPD or _squash(mtpd) == _squash(beyond)


def _review_rto(
    verdict: Verdict, aid: str, activity: Mapping[str, Any], mtpd: str | None,
    beyond: str | None,
) -> None:
    """An RTO must sit strictly inside its MTPD. The one exception (the owner's ruling, t139 (c)):
    an RTO that is the method's own word past the last horizon, over an MTPD that is past it too
    (no crossing within the horizons, or that same word), is neither refused nor flagged. Past
    means the MTPD the target is held against (`_held_mtpd`, ADR-0030 decision 2), not the grid."""
    if _both_beyond(activity.get(RECOVERY_TARGET), _held_mtpd(activity, mtpd), beyond):
        verdict.ran(RTO_CHECK)
        return
    _review_recovery(verdict, aid, activity, mtpd)


def _held_mtpd(activity: Mapping[str, Any], mtpd: str | None) -> str | None:
    """The MTPD the target is held against: the record's own where it can be read, else `mtpd`."""
    carried = activity.get(MTPD)
    return carried if _minutes(carried) is not None else mtpd


def _review_recovery(
    verdict: Verdict, aid: str, activity: Mapping[str, Any], mtpd: str | None
) -> None:
    """The target is held against the MTPD the record carries, whether or not the grid could be
    judged: a signed record agrees with itself (ADR-0030 decision 2, t75). The grid's MTPD is the
    fallback where the record carries none that can be read.

    t74, the owner's ruling (2026-09-18): this one comparison reads a band MTPD at its UPPER edge,
    so "< 4 h" is inside "0–4 h" and "4 h" is not. `duration.minutes` keeps its lower-edge reading
    everywhere else. The refusal names the band the record carries, and its edge as a part of its
    own, so the card can say why from the figures (241 slice 3: the phone's patch, now nemo's)."""
    carried = activity.get(MTPD)
    mtpd = carried if _worst_case(carried) is not None else mtpd
    target = activity.get(RECOVERY_TARGET)
    minutes = _readable_target(verdict, aid, target)
    if minutes is None:
        return
    limit = _worst_case(mtpd)
    if limit is None:
        return
    verdict.ran(RTO_CHECK)
    if minutes >= limit and not activity.get("recovery_gap_flagged"):
        _reject_outside_mtpd(verdict, aid, target, mtpd)


def _readable_target(verdict: Verdict, aid: str, target: Any) -> int | None:
    """The recovery target in worst-case minutes, or None with the rejection saying why: there is
    none, or it is not a duration that can be compared to the MTPD."""
    if not target:
        verdict.rejections.append(Rejection(
            NO_RECOVERY_TARGET,
            f"activity {aid}: no recovery_target — record the RTO the owner stated, as "
            '"recovery_target": "8 h"', activity=aid))
        return None
    minutes = _worst_case(target)
    if minutes is None:
        verdict.rejections.append(Rejection(
            UNREADABLE_TARGET,
            f"activity {aid}: recovery_target {target!r} is not a parseable duration — give a "
            "bare number and unit like '8 h', '24 h' or '2-4 hours' so the RTO can be compared "
            "to the MTPD (a trailing note in parentheses is ignored)",
            activity=aid, target=target))
    return minutes


def _reject_outside_mtpd(verdict: Verdict, aid: str, target: Any, mtpd: str | None) -> None:
    """The refusal of a target not strictly inside the MTPD, naming the band's edge if any."""
    edge = _upper_edge(mtpd)
    verdict.rejections.append(Rejection(
        TARGET_OUTSIDE_MTPD,
        f"activity {aid}: recovery target {target} is not strictly inside the MTPD {mtpd} — "
        "close the gap, or acknowledge it deliberately with recovery_gap_flagged",
        activity=aid, target=target, mtpd=mtpd, **({"edge": edge} if edge else {})))


def _review_rpo(
    verdict: Verdict, aid: str, activity: Mapping[str, Any], method: Mapping[str, Any]
) -> None:
    rpo = activity.get(RPO)
    if rpo is None:
        return
    verdict.ran(RPO_CHECK)
    vocabulary = _rpo_vocabulary(method)
    if _squash(rpo) not in {_squash(entry) for entry in vocabulary}:
        verdict.rejections.append(Rejection(
            RPO_NOT_ALLOWED,
            f"activity {aid}: rpo {rpo!r} is not in the method's rpo_vocabulary — "
            f"allowed: {vocabulary}", activity=aid, rpo=rpo, allowed=tuple(vocabulary)))


def _review_activity(
    verdict: Verdict, activity: Mapping[str, Any], method: Mapping[str, Any],
    files: Mapping[str, str], turns: Mapping[str, Mapping[str, str]] | None = None,
    dept: object = None,
) -> None:
    aid = str(activity.get("id") or activity.get("name") or "?")
    evidence = _evidence_of(activity)
    # the register rows are read for the record's own department (t171-shape, DRAFT)
    judged = {**activity, DEPT: dept}
    for item in evidence:
        verdict.rejections += _evidence_rejections(aid, item, method, files, turns, judged)
    if evidence and files:
        verdict.ran(QUOTES_CHECK)
    _review_rto(verdict, aid, activity, _review_grid(verdict, aid, activity, method),
                _beyond_horizons(method))
    _review_rpo(verdict, aid, activity, method)
    verdict.findings += _plan_language_findings(
        f"activity {aid}", activity.get("impact_summary"), " (options and questions only)")


# ── the record ───────────────────────────────────────────────────────────────
_BOUNDARY_KEYS = (
    ("plan", "a continuity plan"),
    ("recovery_solution", "a chosen recovery solution"),
)


def _review_boundary(verdict: Verdict, record: Mapping[str, Any]) -> None:
    """The BIA stops at handover. A plan or a chosen solution is over the PP4 boundary.

    The check records itself only where this record carried something to judge. It used to say it
    had run before it looked, over keys no record this walk builds can hold — so every manager
    read "confirmed this is still a BIA and not a continuity plan" about a check that had examined
    nothing, which is v1's hard-coded "record validated and saved" wearing the new mechanism.
    """
    handed_over = list(record.get("pp4_handoff") or [])
    carried = _boundary_rejections(record)
    if not carried and not handed_over:
        return
    verdict.ran(BOUNDARY_CHECK)
    verdict.rejections += carried
    for item in handed_over:
        _review_handoff_item(verdict, item)


def _boundary_rejections(record: Mapping[str, Any]) -> list[Rejection]:
    """A refusal for each key this record carries that belongs to solution design, not to a BIA."""
    return [Rejection(BOUNDARY,
                      f"{what} is present in {key!r} — the PP4 boundary is violated: the BIA hands "
                      "requirements to solution design and stops before drafting either",
                      what=what)
            for key, what in _BOUNDARY_KEYS if record.get(key) is not None]


def _review_handoff_item(verdict: Verdict, item: object) -> None:
    if not _PP4_PREFIX.match(norm(item)):
        verdict.rejections.append(Rejection(
            HANDOFF_ITEM,
            "pp4_handoff item must start with Gap:/Option:/Human decisions:/Missing evidence: "
            f"— got {item!r}", item=item))
    verdict.findings += _plan_language_findings(f"pp4_handoff item {item!r}", item)


def _review_comparison(verdict: Verdict, record: Mapping[str, Any]) -> None:
    for conflict in record.get("comparison") or []:
        _review_conflict(verdict, conflict)


def _review_conflict(verdict: Verdict, conflict: Mapping[str, Any]) -> None:
    """An un-owned conflict is an absent decision; one owned by the AI is a false record."""
    issue = conflict.get("issue", "?")
    who = str(conflict.get("escalated_to") or "")
    if not who:
        verdict.findings.append(
            f"Human decisions: conflict {issue!r} needs a named human owner (escalated_to) "
            "before it can be resolved")
    elif set(re.findall(r"[a-z]+", who.lower())) & _AI_WORDS:
        verdict.rejections.append(Rejection(
            OWNER_NOT_A_PERSON,
            f"comparison {issue!r}: escalated_to names the AI, not a human ({who!r})",
            issue=issue, who=who))
    verdict.findings += _plan_language_findings(
        f"comparison {issue!r}", conflict.get("why_it_matters"))


def review(
    record: Mapping[str, Any],
    method: Mapping[str, Any],
    files: Mapping[str, str] | None = None,
    turns: Mapping[str, Mapping[str, str]] | None = None,
) -> Verdict:
    """Referee one record against the method and the room's readable files.

    `files` maps a room-relative path to that file's text: the only place a quote may come from.
    `turns` is his words on each turn of his, by turn id (`nemo.turn_file.his_turns`): the only
    place a chat confirmation may come from (ticket 132).
    """
    verdict = Verdict()
    files = files or {}
    activities = record.get(ACTIVITIES) or []
    if not activities:
        verdict.rejections.append(Rejection(
            NO_ACTIVITIES, "no activities — a BIA must record at least one critical activity"))
    for activity in activities:
        if isinstance(activity, dict):
            _review_activity(verdict, activity, method, files, turns, record.get(DEPT))
        else:
            verdict.rejections.append(Rejection(
                MALFORMED_ACTIVITY,
                f"malformed activity (expected an object, got {type(activity).__name__})"))
    _review_boundary(verdict, record)
    _review_comparison(verdict, record)
    return verdict
