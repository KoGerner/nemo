"""PROTOTYPE, throwaway (2026-09-17). The conversation core: model + nemo tools, no UI.

Answers: with the owner's rulings of 2026-09-17 (UX first; the model proposes and guides, clearly
marked; stage 2 = all interviews about the activity; stage 3 = a seed-built, verified draft the
manager settles; cards only at activity pick, record and certificate), can a manager walk Slaughter
on a phone to the certificate — and which model does it best?

nemo's source is not changed. This process patches, at runtime and only here:
- walk.evidence_card / _WHAT_FOLLOWS: stage 3's proposal comes from the settled draft;
- walk.readable: nemo reads the confirmed interviews off the run record (ticket 168); this adds
  what nemo does not hold yet, an added activity's room files (t72) and risk rows (t72b), and a run
  the skin confirmed before 168;
- bia._activity: origin (stated/proposed/manager), owner, recovery gap flag (t131: nemo itself now
  writes the file each quote was found in);
- referee: a "manager_confirmed" evidence type for a proposal no quote supports (not
verbatim-checked).

13_nemo, t72: a manager can start a BIA for an activity the files don't list. It comes into being
in exactly two ways, neither of which reads his words for meaning (M13): the model's `add_activity`
call with the name, or the pick card's "Another activity…" tap, after which the server takes his
next typed line as the name. The name joins the room as a file (`ADDED`), is drafted in that room
(`PROTOTYPE_draft.draft_in_room`), and stage 2 holds nemo's live interview (`nemo.conduct`,
`walk.held_interview`) when no interview for it is on file; the draft is rebuilt once it is filed.
"""

from __future__ import annotations

import calendar
import collections
import contextlib
import contextvars
import copy
import datetime
import functools
import inspect
import itertools
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any, NamedTuple, cast

import impact_chart
import needs
import shown
import worded_scores

from nemo import (
    bia,
    conduct,
    duration,
    facts,
    handover,
    impact,
    interview,
    referee,
    turn_file,
    verbatim,
    walk,
)
from nemo import lane as nemo_lane  # t220: its `post` and its `MODEL`, read live
from nemo import next_step as offer
from nemo import refusal as nemo_refusal
from nemo.ask import GUIDELINE, TITLE_SEPARATOR, ask, call_guidance, source_of
from nemo.evidence import MISSING, standardise
from nemo.figures import kept_says, listed
from nemo.impact import NOT_RATED, derive_mtpd, unrated_bands, worst_case_row
from nemo.interview import text as interview_text
from nemo.lane import LaneUnavailable, call_lane
from nemo.method import BEYOND_HORIZONS, TIME_HORIZONS
from nemo.method import lenses as method_lenses
from nemo.record import (
    ACTIVITY,
    ANSWERS,
    ASSET_ID,
    ASSET_IDS,
    CARRIED,  # noqa: F401  # read by the fidelity check as `core.CARRIED`
    CHAT_CONFIRMATION,
    DEPENDENCIES,
    EVIDENCE,
    IMPACT_GRID,
    LENS,
    MODEL_NOTES,
    MTPD,
    ON,
    OWNER,
    PENDING_REFERRALS,
    QUOTE,
    REFERRALS,
    REGISTER_NO_RPO,
    REGISTER_ROW,
    SOURCE_PATH,
    TRANSCRIPT_QUOTE,
    TURN_ID,
    TYPE,
    WORDS,
)
from nemo.room_store import jailed_path, room_lock, write_file, write_record

import PROTOTYPE_draft as drafting
import PROTOTYPE_lanes as lanes
import PROTOTYPE_words as words
from bia_figures import deps as figures_deps  # this tree's copy, beside the skin (189, ADR-0035)
from bia_figures import impact as figures_impact
from bia_figures.register import recovery_point_for
from bia_figures.vocabulary import RPO_VOCABULARY, duration_of, words_by_duration

DRAFTS, FIXTURES = drafting.DRAFTS, drafting.FIXTURES  # t176: the cache, then the tracked fixtures
MANAGER = "manager_confirmed"
STATE = "output/.proto/{slug}.json"


#: t71: the state file's ledger of every reservation nemo took, word for word ({stage, naming});
#: and the state key holding the decisions as a reopen found them, with the ids decided again since
#: (`touched`). The run key a reopen carries reservations under is nemo's `CARRIED` (241).
RESERVATIONS, REOPENED = "reservations", "reopened"
#: t71 fix 2: the documents are owed a rewrite (a reservation's words landed while the record's
#: picture was not drawn); the next step move at step 5, or the signature, writes them
DOCUMENTS_OWED = "documents_owed"
#: t71b: a note a tool call supplies (`decide(…, note=…)`) is never his reason. It is logged in the
#: run file under nemo's `MODEL_NOTES`, marked as whose it was, and reaches no signed view. Only the
#: model passes one in a walk; a direct tool call (no model in between) is marked as that.
BY_MODEL, BY_CALL = "the model", "a direct tool call"
#: t71b: how the record says a figure the manager set, and what it says with no reason of his
SET_BY, NO_REASON = "Set by the manager in chat: ", "no reason given"
#: t71b: every line the manager typed, and every text a tool call outside the model's turn carried
#: (his tap's typed value, his reservation, the tools driven directly): what the fidelity check
#: holds manager-origin text to. Room-wide, so it outlives a restart of the app.
SAID = "output/.proto/_said.json"


def said_lines(folder: Path) -> list[str]:
    p = folder / SAID
    return [str(r["line"]) for r in json.loads(p.read_text())] if p.exists() else []


def log_said(folder: Path, line: str, how: str) -> None:
    """t71b: one manager line (typed) or one text his own tool call carried (tool), kept once.

    t208 (B8): reading the file, adding to it and writing it back is one step under the room's own
    lock, and the bytes go through the store's staged write. Two turns overlap — his double-tap,
    or the room open on a second device, both in the app's thread pool — and without the lock they
    both read the same rows and the second write drops the first line for good; without the staged
    write a stop mid-write leaves `_said.json` unparseable, and the fidelity check reads it.
    """
    with room_lock(folder):
        p = folder / SAID
        rows = json.loads(p.read_text()) if p.exists() else []
        if any(r["line"] == line for r in rows):
            return
        write_file(folder, SAID, json.dumps(
            [*rows, {"line": line, "how": how, "at": time.strftime("%H:%M:%S")}],
            indent=1, ensure_ascii=False))


def slug(activity: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", activity.lower()).strip("-")


# ── state: the collected set and the manager's decisions on the draft ─────────────────────────
def load_state(folder: Path, activity: str) -> dict[str, Any]:
    p = folder / STATE.format(slug=slug(activity))
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(folder: Path, activity: str, state: dict[str, Any]) -> None:
    """t208 (B8): through the store's staged write, so a stop mid-write leaves the state that was
    there rather than half a file `load_state` cannot parse."""
    write_file(folder, STATE.format(slug=slug(activity)),
               json.dumps(state, indent=1, ensure_ascii=False))


def holds_the_room[Tool: Callable[..., Any]](tool: Tool) -> Tool:
    """t238 (C7): a Session method that loads the state, changes it and saves it, run whole under
    the room's lock. Two turns on one room (his double-tap, or the room open in two tabs, each a
    thread of the app's pool) otherwise both load one state, and the second save drops the first
    one's decision. Only for a method that calls no lane: a model call inside would hold every
    other tap on the room for as long as the call takes. A method that can reach a lane
    (`get_step`, `confirm_interviews` through `_draft`) takes the lock around its own load and save.
    """
    @functools.wraps(tool)
    def held(self: Any, *args: Any, **kwargs: Any) -> Any:
        with room_lock(self.folder):
            return tool(self, *args, **kwargs)
    return cast(Tool, held)


def draft_for(activity: str, model: str, folder: Path | None = None) -> dict[str, Any] | None:
    """The prepared draft: the room's own first (an added activity's, t72), then the shared ones:
    the cache, then the tracked fixtures (t176)."""
    places = ([folder / drafting.ROOM_DRAFTS] if folder is not None else []) + [DRAFTS, FIXTURES]
    for place in places:
        for m in (model, "glm", "gpt6", "deepseek"):
            p = place / f"{slug(activity)}.{m}.json"
            if p.exists():
                return json.loads(p.read_text())  # type: ignore[no-any-return]  # a JSON object
    return None


# ── activities a manager added to the room (13_nemo, t72) ─────────────────────────────────────
#: The room's list of added activities. Shape: {"activities": [{"name": <exactly as he gave it>,
#: "route": "add_activity" | "another_activity_tap", "added_at": "<ISO time>"}]}. A file in the
#: room, so every later conversation there lists it (nemo's seam settles the real home).
ADDED = drafting.ADDED_FILE
ROUTE_TOOL, ROUTE_TAP = "add_activity", "another_activity_tap"


def added_activities(folder: Path) -> list[dict[str, Any]]:
    p = folder / ADDED
    return (json.loads(p.read_text()).get("activities") or []) if p.exists() else []


def added_names(folder: Path) -> list[str]:
    return [a["name"] for a in added_activities(folder)]


def add_to_room(folder: Path, name: str, route: str) -> tuple[str, bool]:
    """(the room's name for it, whether it is new). The name is kept as given, outer spaces aside.

    One the room already holds (the same name as a file spells it, `slug`) is that activity, and
    nothing is written: the file lists what the room does not hold otherwise.

    t238 (C8): the check, the read and the write are one step under the room's lock, and the bytes
    go through the store's staged write, as `log_said`'s do. Two tabs adding at once both read the
    list, so one addition was lost, or both wrote one fixed `.tmp` and a torn file was published
    that every later `walk.processes` raised on.
    """
    name = name.strip()
    with room_lock(folder):
        held = next((p for p in walk.processes(folder) if slug(p) == slug(name)), None)
        if held is not None:
            return held, False
        entries = added_activities(folder) + [
            {"name": name, "route": route, "added_at": time.strftime("%Y-%m-%dT%H:%M:%S")}]
        write_file(folder, ADDED, json.dumps({"activities": entries}, indent=1, ensure_ascii=False))
    return name, True


def is_added(folder: Path, activity: str) -> bool:
    return any(slug(n) == slug(activity) for n in added_names(folder))


#: Draft an added activity in a thread, so the walk never waits for it before stage 3 (tests:
#: False).
BACKGROUND_DRAFTS = True


def draft_added(folder: Path, activity: str, model: str) -> dict[str, Any] | None:
    """Draft an added activity in its room; None when it failed or went stale.

    Never waits for another draft of it (fix 2: on seed 8181 the rebuild after the interview waited
    498 s for a slow draft of the room as it was before). A draft that finishes after its room
    gained an interview drops itself (`PROTOTYPE_draft._draft`), so the last one written reads the
    room as it is. A failure is logged beside the draft and the walk carries on: stage 3 tries
    again.
    """
    before = lanes.note_purpose(
        "draft"
    )  # t82: so a turn blocked on this call can name what it waited for
    try:
        return drafting.draft_in_room(folder, activity, model)
    except Exception as e:  # noqa: BLE001 — a failed draft is retried at stage 3, never fatal here
        where = folder / drafting.ROOM_DRAFTS
        where.mkdir(parents=True, exist_ok=True)
        with (where / f"{slug(activity)}.{model}.failed.txt").open("a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {type(e).__name__}: {e}\n")
        return None
    finally:  # t33: on his turn's thread (the confirm tap), the calls after it are the turn's again
        lanes.note_purpose(before)


def start_draft(folder: Path, activity: str, model: str) -> None:
    if BACKGROUND_DRAFTS:
        threading.Thread(target=draft_added, args=(folder, activity, model), daemon=True).start()
    else:
        draft_added(folder, activity, model)


#: t191: where a stopped interview says why. stdlib logging, unconfigured, so stderr: the journal.
_LOG = logging.getLogger(__name__)
#: Asks per interview question when the lane answers empty: his, apart from `lanes.TRIES` even while
#: both are 1 (ticket 229, TYPED 2026-09-30T06:27:45Z in fb099549, "yes, dont forget").
EMPTY_REPLY_TRIES = 1

#: The owner's label wherever the lane writes it (`conduct.ANSWERED`'s word), bare or dressed:
#: "Owner:", "**Owner:**", "Owner (Anja):", "_Owner_ :" (fix round 1, minor 3).
_OWNER_WORD = conduct.ANSWERED.format(answer="").strip().rstrip(":")
_OWNER_LINE = re.compile(r"[*_(\[]*(?<![A-Za-z])" + re.escape(_OWNER_WORD)
                         + r"(?![A-Za-z])[*_]*\s*(?:\([^)\n]*\))?\s*[*_)\]]*\s*:")


def interview_lane(model: str, room: Path | None = None) -> Callable[[str], str]:
    """The lane nemo's live interview asks its questions over: the session's own model.

    The lane is handed the interview in the lines it will be filed in, so it sometimes goes on
    writing them: on seed 7272 (13_nemo, t72) its sixth question ended with an `Owner:` line the
    manager never said, and that line was filed as his testimony. nemo already strips the
    interviewer's own label for this reason (`conduct._said`); the question here ends where the
    owner's label begins, so what the lane writes in the manager's name never reaches the file.
    """
    def ask(prompt: str) -> str:
        before = lanes.note_purpose("interview")
        try:
            said = (
                lanes.chat(model, [{"role": "user", "content": prompt}], room=room).get("content")
                or ""
            )
        except Exception as e:  # noqa: BLE001 — any lane failure is nemo's one "unavailable"
            # t191: the manager sees STOPPED; the journal sees why (lanes.chat spent its own tries)
            _LOG.warning("the interview lane failed: %s: %s", type(e).__name__, e)
            raise LaneUnavailable(str(e)) from e
        finally:  # t33 fix 1: the rest of his turn is the turn's, in the ledger 95 reads
            lanes.note_purpose(before)
        # one line, so every "Owner:" line in the filed transcript comes from a typed answer
        return " ".join(_OWNER_LINE.split(said, maxsplit=1)[0].split())

    def lane(prompt: str) -> str:
        # t191: a reply cut off by max_tokens after the reasoning has no content; that is a failed
        # try, asked again within EMPTY_REPLY_TRIES, never filed as an empty question
        for _ in range(EMPTY_REPLY_TRIES):
            if question := ask(prompt):
                return question
        _LOG.warning("the interview lane answered empty %d times", EMPTY_REPLY_TRIES)
        raise LaneUnavailable(f"lane {model} answered empty {EMPTY_REPLY_TRIES} times")
    return lane


def _as_proposed(value: Any) -> Any:
    """t85: a recovery gap said as the proposal it is. Everything `items` yields is the drafting
    model's proposal, waiting on him, so a gap word in one is never the acknowledgement's."""
    return GAP_PROPOSED if is_gap(value) else value


def _side_as_proposed(side: dict[str, Any]) -> dict[str, Any]:
    """t85: one side of a conflict, with the recovery gap it would put on an RTO said as the
    proposal it is. A copy: the draft itself is saved, and no stored value moves (t75)."""
    implied = side.get("implies")
    if not (isinstance(implied, dict) and str(implied.get("item_id") or "").endswith(".rto")
            and is_gap(implied.get("value"))):
        return side
    return {**side, "implies": {**implied, "value": _as_proposed(implied["value"])}}


def said_alone(x: dict[str, Any], key: str = "reason", marked: bool = False) -> str:
    """t79 fix 2: the sentence its author wrote, with nemo's own note split off where a draft on
    file has it welded inside (`_authored`). The record's evidence quote is composed from this and
    never from the raw draft item: nemo's words inside somebody else's sentence is the defect this
    ticket exists to remove, and the evidence quote is on what he signs."""
    return str(_authored(x, key, marked).get(key) or "")


def _authored(x: dict[str, Any], key: str, marked: bool = False) -> dict[str, Any]:
    """t79 fix 1: an item's `reason` or `why` with whoever wrote it beside it, so a card attributes
    it per item instead of calling every one of them the drafting model's.

    Four places write a sentence NEMO composed into the draft object — `PROTOTYPE_draft`'s
    synthesised MTPD-rule conflict, the row it writes where the draft has none and the note its
    verify pass makes, and the merged grid row in `collapse_to_scope` here — and each marks it
    `floor`, the way `with_floor` marks an interview nemo put back.

    A draft already on file was drawn before those marks existed and a saved draft is never
    rewritten (t75's box), so nemo recognises its own sentences in one too: by the constants nemo
    wrote them from (`PROTOTYPE_draft.NEMO_S_OWN`), never by anything the model wrote. The note the
    verify pass used to append INSIDE the model's sentence is split back out the same way, against
    nemo's own literal. The file keeps its bytes; what changes is that the card prints the model's
    sentence and nemo's note as the two separate things they always were.

    t79 fix 2: that literal branch is **transitional and retires itself**. A draft nemo's own
    verify pass built carries nemo's stamp (`MARKED_BY_NEMO`, written after the boundary filter, so
    the model cannot supply it), and `marked` turns both the exact-match and the weld-split off:
    a marked draft is read through nemo's own fields alone. Only a draft drawn before the marks
    existed — the five cached in `drafts/` — takes the literal route, and it stops the day they are
    redrawn. `floor` itself is honoured either way: on a marked draft the boundary makes it nemo's
    by construction, and no cached draft carries one on a row, a figure or a conflict at all.
    """
    marked = bool(marked)
    said = str(x.get(key) or "")
    note = str(x.get("check_note") or "") if marked else ""
    if not marked and said.endswith(drafting.CHECK_NOTE_APPENDED):
        said, note = said[:-len(drafting.CHECK_NOTE_APPENDED)], drafting.CHECK_NOTE
    floor = bool(x.get("floor")) or (not marked and said in drafting.NEMO_S_OWN)
    return {key: said or x.get(key),
            **({"floor": True} if floor else {}), **({"check_note": note} if note else {})}


def items(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Everything in the draft that is the model's proposal, so the manager has to settle it."""
    out = []
    marked = bool(draft.get(drafting.MARKED_BY_NEMO))  # t79 fix 2: read off the draft, once
    for a in draft["activities"]:
        for lens, row in a["grid"].items():
            if row.get("kind") in ("proposed", "none"):
                out.append({"id": f"{a['id']}.{lens}", "activity": a["name"], "type": "score",
                            "lens": lens, "scores": row["scores"], "kind": row["kind"],
                            "quote": row.get("quote", ""), "path": row.get("path", ""),
                            **_authored(row, "reason", marked)})
        for f in ("mtpd", "rto", "rpo"):
            x = a.get(f) or {}
            if x.get("kind") != "stated" and x.get("value"):
                out.append({"id": f"{a['id']}.{f}", "activity": a["name"], "type": f.upper(),
                            "value": _as_proposed(x.get("value")) if f == "rto" else x.get("value"),
                            "kind": "proposed", "quote": x.get("quote", ""),
                            "path": x.get("path", ""), **_authored(x, "reason", marked)})
    for c in draft.get("conflicts") or []:
        out.append({"id": c["id"], "type": "conflict", "activity": c.get("activity"),
                    "about": c.get("about"),
                    "sides": [_side_as_proposed(s) for s in c["sides"]] if c.get("sides")
                             else c.get("sides"),
                    "recommend": c.get("recommend"), **_authored(c, "why", marked)})
    return out


def known_items(draft: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every item a `decide` can name: the draft's proposals, and every stated figure and score row,
    which can be changed too and then become the manager's."""
    known = {i["id"]: i for i in items(draft)}
    for a in draft.get("activities") or []:
        for key in [*a["grid"], "mtpd", "rto", "rpo"]:
            known.setdefault(f"{a['id']}.{key}", {"id": f"{a['id']}.{key}", "type": "figure"})
        # 195: one item per dependency the draft lists, so his tap on a proposal has an id to
        # name. Whether it is a proposal at all takes the register, which no caller of this
        # has; a tap on one his own files already name records a decision and moves nothing.
        for row in unique_dependencies(a.get("dependencies") or []):
            if row.get("asset_id"):
                iid = dep_item_id(a["id"], row["asset_id"])
                known.setdefault(iid, {"id": iid, "type": DEP, "asset_id": row["asset_id"],
                                       "heard": row.get("heard") or ""})
    return known


def explicit_change(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    """t71 fix 2c: his explicit change of a figure (a "Change …" with his value), never one an
    evidence side implied (`by`); an implied one written over his keeps his underneath (`over`)."""
    d = decision or {}
    # why: `over` may be None, and the return below tests `d` before it uses it
    d = d.get("over") if d.get("by") else d  # type: ignore[assignment]
    return d if d and d.get("decision") == "change" and d.get("value") else None


def rule_is_latest(decisions: dict[str, Any], aid: str) -> bool:
    """t71 fix 2/2c: "latest wins" among his explicit figure decisions only: a typed change of the
    MTPD, and the sides of the method-rule conflict. The rule stands over his change only when he
    took it after the change (`seq`, `Session._apply`; none counts as 0). An evidence side (C1…Cn)
    is no figure decision: it can tighten the figure carried, never beat the rule (73b)."""
    m = explicit_change(decisions.get(f"{aid}.mtpd"))
    if m is None:
        return True
    return int((decisions.get(f"{aid}-MTPD-RULE") or {}).get("seq") or 0) > int(m.get("seq") or 0)


def question_key(aid: str) -> str:
    """t116: the state key his answer to the referee's asserted-MTPD question is stored under."""
    return f"{aid}.{referee.ASSERTED_MTPD}"


def withdrawn(decisions: dict[str, Any], aid: str) -> bool:
    """t116: he withdrew the asserted MTPD ("Withdraw it: use the grid's …"), and no decision on
    the MTPD came after it: a later change of the figure, or a side of the method's rule, is his
    latest word and stands over the withdrawal (`seq`, as `rule_is_latest` reads it)."""
    w = decisions.get(question_key(aid)) or {}
    if w.get("decision") != DERIVED:
        return False
    later = [decisions.get(f"{aid}.mtpd"), decisions.get(f"{aid}-MTPD-RULE")]
    return all(int((d or {}).get("seq") or 0) < int(w.get("seq") or 0) for d in later)


def evidence_tightened(draft: dict[str, Any], decisions: dict[str, Any], aid: str,
                       start: Any) -> tuple[Any, str | None]:
    """t71 fix 3: an MTPD with every settled evidence side (C1…Cn) applied to it, as
    `Session._apply` applies them one by one, in the order he took them: a side is written over the
    figure unless both are durations and it is the looser (fix 4: the same test as `_apply`, so a
    side whose figure is no duration is written here too, as it is there).
    Returns the figure and the conflict that set it (None: `start` stands)."""
    value, by = start, None
    settled = sorted((c for c in draft.get("conflicts") or [] if c["id"] in decisions),
                     key=lambda c: int(decisions[c["id"]].get("seq") or 0))
    for c in settled:
        side, sides = decisions[c["id"]].get("side"), c.get("sides") or []
        implied = (
            sides[side].get("implies") if isinstance(side, int) and side < len(sides) else None
        )
        if (
            isinstance(implied, dict)
            and implied.get("item_id") == f"{aid}.mtpd"
            and implied.get("value")
        ):
            new, old = duration.minutes(str(implied["value"])), duration.minutes(str(value))
            if not (new is not None and old is not None and new > old):
                value, by = implied["value"], c["id"]
    return value, by


def effective(
    draft: dict[str, Any], decisions: dict[str, Any], method: dict[str, Any]
) -> list[dict[str, Any]]:
    """The draft with the manager's decisions applied."""
    acts = []
    for a in draft["activities"]:
        grid, origin = {}, {}
        for lens, row in a["grid"].items():
            d = decisions.get(f"{a['id']}.{lens}")
            scores, org = dict(row["scores"]), row.get("kind")
            if d and d["decision"] == "reject":
                scores, org = dict.fromkeys(scores, MISSING), "rejected"
            elif d and d["decision"] == "change" and d.get("scores"):
                scores.update({h: int(v) for h, v in d["scores"].items() if h in scores})
                org = "manager"
            elif d and row.get("kind") == "none":
                org = "blank"
            grid[lens], origin[lens] = scores, org
        figures = {}
        for f in ("mtpd", "rto", "rpo"):
            x = dict(a.get(f) or {})
            d = decisions.get(f"{a['id']}.{f}")
            if d and d["decision"] == "change" and d.get("value"):
                # t71b: a note is carried only where nemo wrote it, for a conflict that set the
                # figure (`by`). Any other note is a tool call's: logged in the run file since
                # t71b, and one a state file kept from before t71b (the model's, on the owner's
                # live room) is dropped the same way (fix 1). `typed`: the value is his typed line
                # t64: or his own reason, typed when nemo asked for it after his typed value
                x.update(
                    value=d["value"],
                    kind="manager",
                    note=d.get("note")
                    if d.get("by")
                    else (d.get("reason") if d.get("typed") else "") or "",
                    typed=bool(d.get("typed")),
                    # t80: he took the tap nemo drew for a figure named in chat
                    confirmed=bool(d.get("confirmed")),
                    # t132: the turn he took it on, whose line holds his words
                    turn_id=d.get(TURN_ID) or "",
                    # t171: and the turn he gave his reason on (t64), whose line holds it
                    reason_turn_id=d.get("reason_turn_id") or "",
                )
            elif d and d["decision"] == "reject":
                x = {}
            if f == "rto" and d is None and is_gap(x.get("value")):
                # t85: a recovery gap nemo's own draft proposed, and he has answered nothing on
                # this RTO: it is a proposal, and reads as one wherever this figure is said —
                # `decide`'s figures, the record-to-be, the room-state line, the cards. Any
                # decision of his on the item is his act (`_note_gaps` counts the same ones), so
                # from there the acknowledgement's own spelling stands, exactly as it was stored.
                x = {**x, "value": GAP_PROPOSED}
            figures[f] = x
        c = decisions.get(f"{a['id']}-MTPD-RULE")
        derived = derive_mtpd(worst_case_row({k: {h: v for h, v in r.items() if isinstance(v, int)}
                                              for k, r in grid.items()}), method)
        if c and c.get("side") == 0 and figures["mtpd"] and rule_is_latest(decisions, a["id"]):
            figures["mtpd"] = {**figures["mtpd"], "value": derived, "kind": "method"}
        elif (
            c
            and c.get("side") == 1
            and a.get("mtpd")
            and figures["mtpd"]
            and rule_is_latest(decisions, a["id"])
        ):
            # fix 2c/3: the rule's other side, taken after his typed change, is the draft's own MTPD
            # with every evidence side applied to it, in any order, exactly as without his change.
            # t369 r3: without a change too, so a side he took while the rule was tighter (and
            # `_apply` kept the rule's figure) is applied here, never lost
            value, by = evidence_tightened(draft, decisions, a["id"], a["mtpd"].get("value"))
            figures["mtpd"] = dict(a["mtpd"]) if by is None else {
                **a["mtpd"], "value": value, "kind": "manager",
                "note": f"settled by the manager on conflict {by}"}
        if figures["mtpd"] and withdrawn(decisions, a["id"]):
            # t116: he withdrew the MTPD he asserted, so the record carries the grid's, and
            # follows the grid from here, never a figure frozen at the tap (amendment 1)
            # (b): its evidence is the grid's line, never the quote that stated the withdrawn
            # figure; that quote goes to the decision trail (`_answers`)
            figures["mtpd"] = {"value": derived, "kind": "method", "withdrawn": True,
                               "withdrawn_quote": figures["mtpd"].get("quote") or ""}
        acts.append(
            {
                **a,
                "grid_now": grid,
                "origin": origin,
                "derived_now": derived,
                **{f"{k}_now": v for k, v in figures.items()},
            }
        )
    return acts


REGISTER = "03_Dependencies/dependency-register.json"


def _room_facts(folder: Path | None, state: dict[str, Any],
                activity: str = "") -> tuple[dict[str, Any], list[str]]:
    """The register and the confirmed interviews, as data for `bia_figures`, which reads nothing.

    Another department's interview is read `elsewhere` (ticket 184): its "Depends on:" line is
    that activity's list, not this one's."""
    if folder is None or not (folder / REGISTER).exists():
        return {}, []
    register = drafting.read_register(folder)
    own = set(drafting.own_interviews(folder, activity)) if activity else set()
    texts = []
    for path in state.get("interviews") or []:
        try:
            text = jailed_path(folder, path).read_text(errors="replace")
        except OSError:  # a dropped interview is not a reason to lose the register
            continue
        texts.append(text if path in own else figures_deps.elsewhere(text))
    return register, texts


# ── 195: the dependencies the model proposed, said once and only here ───────────────────────────
def _drafted_activity(state: dict[str, Any]) -> str:
    """The activity this draft was drawn for, as `build_proposal` reads it: which interviews the
    floor reads whole turns on it, so the card and the record must ask it the same way (195)."""
    return str(((state.get("draft") or {}).get("meta") or {}).get("activity") or "")


def dep_item_id(activity_id: str, asset_id: str) -> str:
    """The item his tap on a proposed dependency records (`decide`'s `item_id`)."""
    return f"{activity_id}.{DEP}.{asset_id}"


def dep_asset(item_id: str) -> str:
    """The register id a dependency item names, or "" where the id is not one (195)."""
    aid, _, rest = item_id.partition(".")
    kind, _, asset = rest.partition(".")
    return asset if aid and kind == DEP else ""


def dep_name(register: dict[str, Any], asset_id: str) -> str:
    """The register's own name for an asset — the words a person says — else its id (t64's rule)."""
    entry = register.get(asset_id)
    return str(entry.get("name") or asset_id) if isinstance(entry, dict) else asset_id


def unique_dependencies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """195: one entry per dependency, in the draft's own order, keyed on the register id where it
    has one and on the words it was heard in where it has none. A draft may name the same thing
    under several sub-steps — time-recording's lists its own system four times — and the record
    carries what the activity depends on, which is that thing, once."""
    seen: set[str] = set()
    out = []
    for row in rows:
        key = str(row.get("asset_id") or row.get("heard") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def dependency_source(folder: Path | None, state: dict[str, Any], register: dict[str, Any],
                      asset_id: str) -> str:
    """195: the confirmed interview whose own words name `asset_id`, as the room path, or "".

    The two ways an interview names a register entry are the floor's (ticket 184): by its id, or
    by the register's name for it. Read whole, not `elsewhere`: the question here is which file
    says the words, not whose dependency list they stand on — that is what made it a proposal.
    """
    if folder is None:
        return ""
    for path in state.get("interviews") or []:
        try:
            text = jailed_path(folder, path).read_text(errors="replace")
        except OSError:  # a dropped interview names nothing
            continue
        if asset_id in figures_deps.floor(register, [text]):
            return path  # type: ignore[no-any-return]  # the register's path, a JSON value
    return ""


def proposed_dependencies(
    draft: dict[str, Any],
    state: dict[str, Any],
    register: dict[str, Any],
    interviews: list[str],
    folder: Path | None = None,
) -> list[dict[str, Any]]:
    """195: every dependency of this draft the model proposed, each once, with where it came from.

    `bia_figures.deps.dependencies` tells the two apart: an id a confirmed interview names is the
    floor's (`files`) and is the activity's own, whatever any model said; anything else the draft
    lists is `proposed`. A proposal is on his record only after the tap this item id carries.
    """
    decisions = state.get("decisions") or {}
    out = []
    for a in draft.get("activities") or []:
        rows = unique_dependencies(a.get("dependencies") or [])
        origin = figures_deps.dependencies(
            register, interviews, [r["asset_id"] for r in rows if r.get("asset_id")]) \
            if register else {}
        for row in rows:
            asset = str(row.get("asset_id") or "")
            if origin.get(asset) != figures_deps.PROPOSED:
                continue
            iid = dep_item_id(a["id"], asset)
            path = dependency_source(folder, state, register, asset)
            out.append({"id": iid, "type": DEP, "activity_id": a["id"], "activity": a["name"],
                        "asset_id": asset, "name": dep_name(register, asset), "path": path,
                        "heard": str(row.get("heard") or ""),
                        "source": NAMED_IN.format(path=path) if path else MODEL_INFERRED,
                        "added": (decisions.get(iid) or {}).get("decision") == "accept"})
    return out


#: A risk-register row attached to an added activity's evidence (13_nemo, t72b): by the floor (its
#: name names the row, `PROTOTYPE_draft.risk_floor`) or kept by the manager on the stage-2 card.
#: The record carries it as a quote with this origin; it sets no figure.
ROW_FLOOR, ROW_KEPT = "risk_register_floor", "risk_register_kept"


def attached_rows(draft: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """The risk-register rows an added activity's evidence carries: the draft's floor rows, then
    the ones the manager kept at stage 2, each once (the floor's first). Filed activities: none."""
    out, seen = [], set()
    for row, origin in [*((r, ROW_FLOOR) for r in draft.get("risk_rows") or []),
                        *((r, ROW_KEPT) for r in state.get("risk_rows_kept") or [])]:
        if row.get("id") not in seen:
            seen.add(row.get("id"))
            out.append({**row, "origin": origin})
    return out


RANGE = re.compile(r"\d\s*[–—-]\s*\d")


def tighter(mine: Any, derived: Any) -> bool:
    """Whether the manager's figure is a duration strictly shorter than the derived one (t71). A
    figure that is no duration ("n/a (physical)") is tighter than nothing, and neither is a range
    ("0–4 h" reads as 0 minutes, and is no point to recover to); an equal one is the
    derivation's."""
    if RANGE.search(duration_of(str(mine))):
        return False
    a, b = duration.minutes(str(mine)), duration.minutes(str(derived))
    if a is not None and b is None and not re.search(r"\d", duration_of(str(derived))):
        # fix 2: against the method's no-data word ("n/a (physical)") any duration keeps more data,
        # the method's own order (bia_figures.vocabulary.looseness), so a duration he gives is
        # tighter
        return True
    return a is not None and b is not None and a < b


def is_gap(value: Any) -> bool:
    """Whether an RTO value is the recovery gap's word (`GAP`), not a duration (t71 fix 4)."""
    return "gap" in str(value).lower()


def same_figure(mine: Any, derived: Any) -> bool:
    """Both figures are single durations and the same one (fix 2: never "can't compare")."""
    a, b = duration.minutes(str(mine)), duration.minutes(str(derived))
    return a is not None and a == b and not RANGE.search(duration_of(str(mine))) \
        and not RANGE.search(duration_of(str(derived)))


def side_speaker(draft: dict[str, Any], decisions: dict[str, Any], conflict: Any) -> str:
    """The speaker of the side the manager took on `conflict` ("" for none, or no such side)."""
    c = next((c for c in draft.get("conflicts") or [] if c.get("id") == conflict), None)
    side = (decisions.get(conflict) or {}).get("side") if c else None
    sides = (c or {}).get("sides") or []
    return (
        str(sides[side].get("speaker") or "") if isinstance(side, int) and side < len(sides) else ""
    )


#: t76 (the owner's ruling, 2026-09-19: "Changing the target alone does not close it"): an
#: acknowledged recovery gap is a fact about the activity, not the value of its RTO. The state file
#: keeps it per draft activity — {aid: {at, seq, by, closed: {words, at, seq}}} — so it stays while
#: the target moves, until he records in his own words that the arrangements can meet the target.
GAP_ACKS = "recovery_gaps"
#: the record's key for those words of his, once he has closed a gap with them (nemo's own, t133)
GAP_CLOSED = handover.GAP_CLOSED
#: t76: the third choice on every conflict, as the decision the state file records
UNRESOLVED = "unresolved"
#: One conflict on the record's open items: settled on a side (the speaker as the draft stores it,
#: 6_nemo_check's finding of 2026-09-19), or left unresolved and referred to the activity's owner
#: (t84r, the owner's ruling of 2026-09-21), with the tighter figure the record carries meanwhile
#: said as the assumption it is.
SETTLED_HEAD = "Human decisions: {about} — settled by the manager"
UNRESOLVED_HEAD = "Human decisions: {about} — left unresolved by the manager"
ON_HIS_SIDE = " on {speaker}'s side"
#: the method's own side speaks for nobody, so it is said as the side it is
THE_METHOD = "the method"
#: t84r: one sentence, on the stage-3 card and the record's open item alike
REFERRAL_SAYS = "Referred to {owner}, who owns this activity"
#: t84r, brought to the owner for his word: the draft names no owner for the activity
NO_OWNER_SAYS = "Referred to the owner of this activity, whom the record does not name"
ASSUMED_SAYS = (" The record carries assumed {value} (cautious) while unresolved: an assumption, "
                "not a resolution.")

# ── 195: a dependency the model proposed is his only by his own act ─────────────────────────────
#: The owner's rule of 2026-09-20T21:09:58Z ("Gate it — AI proposes, you act", ticket 83) on the
#: last thing the model still wrote onto the record by itself. A dependency the activity's own
#: files name is the floor's (`files`, ticket 01/184) and is unchanged; one the model proposed is
#: on the card as a proposal, says where it came from, and is on the record only after his tap.
DEP = "dep"
#: where it came from: the first confirmed interview whose own words name it, or nothing at all
NAMED_IN = "{path} names it"
MODEL_INFERRED = "no interview this draft rests on names it, so the model inferred it"
#: the card's line, the tap's label and the record's open item, each said once and only here
DEPS_HEADING = "**What it depends on**"
PROPOSED_DEP_SAYS = "{name} ({asset_id}) {mark} — {source}."
RECORDED_DEP_SAYS = "{name} ({asset_id})"
ADD_DEP_TAP = "Add {name}"
ADDED_DEP_SAYS = ("Human decisions: {name} ({asset_id}) — added as a dependency by the manager, "
                  "where it was nemo's proposal and {source}.")


def settled_says(about: Any, speaker: Any, claim: Any, kept: str = "") -> str:
    """The open item a settled conflict leaves: whose side he took, in the draft's own words, and
    t120: nemo's one line after it where the record kept another figure (`kept_line`)."""
    who = str(speaker or "").strip()
    return (
        SETTLED_HEAD.format(about=about)
        + (ON_HIS_SIDE.format(speaker=THE_METHOD if _who(who) == "method" else who) if who else "")
        + f": {claim}"
        # t120: a claim the draft ended with no stop gets one before nemo's sentence
        + (
            ("" if str(claim).rstrip().endswith((".", "!", "?")) else ".") + f" {kept}"
            if kept
            else ""
        )
    )


def kept_line(decision: dict[str, Any] | None) -> str:
    """t120 (the owner's ruling, 2026-09-22; wording 14_nemo_check's): the settled side's figure is
    not the record's, since `Session._apply` kept a tighter one (`kept`) or his own (`kept_his`).
    "" where the record carries the side's figure."""
    d = decision or {}
    return kept_says(d.get("kept"), his=bool(d.get("kept_his")))


#: t84r fix 1: the `owner:` field of an interview's front matter, and only there. The body names
#: facilitators and stand-ins too; the front matter's field is data nobody's prose can move.
_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*$", re.S | re.M)
_OWNER_FIELD = re.compile(r"^owner:[ \t]*(.+?)[ \t]*$", re.M)


def interview_owner(folder: Path | None, path: Any) -> str:
    """The `owner:` field of the interview at `path`, or "" when there is no such file or field."""
    if folder is None or not isinstance(path, str) or not path:
        return ""
    try:
        head = _FRONT_MATTER.match((Path(folder) / path).read_text(encoding="utf-8"))
    except OSError:
        return ""
    field = _OWNER_FIELD.search(head.group(1)) if head else None
    return field.group(1).strip().strip("\"'") if field else ""


def referred_to(draft: dict[str, Any], folder: Path | None) -> str:
    """t84r: whom an unresolved conflict is referred to — the activity's owner, never whoever argued
    a side. Fix 1 (8_nemo_check's ruling (d), 2026-09-21): the name is the `owner:` field of the
    interview the draft's owner entry cites with a verified quote. The model's name string is never
    read: real drafts named "the HR lead" and the facilitator. No field, no name: the sentence says
    the record does not name one, because the file does not."""
    owner = (draft.get("activities") or [{}])[0].get("owner") or {}
    name = interview_owner(folder, owner.get("path")) if owner.get("verified_quote") is True else ""
    return REFERRAL_SAYS.format(owner=name) if name else NO_OWNER_SAYS


def side_values(conflict: dict[str, Any]) -> tuple[str, list[str]]:
    """The one figure item a conflict's sides are about, and every value they name for it ("" and
    [] where its sides name no figure, or more than one)."""
    named = [(str(s["implies"].get("item_id")), str(s["implies"].get("value")))
             for s in conflict.get("sides") or []
             if isinstance(s.get("implies"), dict) and s["implies"].get("item_id")
             and s["implies"].get("value")]
    items_ = {item for item, _ in named}
    return (items_.pop(), [v for _, v in named]) if len(items_) == 1 else ("", [])


def cautious(carried: Any, values: list[str]) -> bool:
    """t76: whether the figure the record carries while a conflict is unresolved is the tighter of
    the sides — no longer than any duration they name, and shorter than one of them. That is the
    method's MIN principle standing in for a decision, so the record names it as an assumption."""
    mine = duration.minutes(str(carried))
    theirs = [n for n in (duration.minutes(str(v)) for v in values) if n is not None]
    return mine is not None and bool(theirs) and mine <= min(theirs) and mine < max(theirs)


def unresolved_says(conflict: dict[str, Any], carried: Any, draft: dict[str, Any],
                    folder: Path | None = None) -> str:
    """The open item an unresolved conflict leaves: referred to the activity's owner (t84r), and
    the cautious figure the record carries meanwhile named as an assumption (t76)."""
    return (
        UNRESOLVED_HEAD.format(about=conflict.get("about"))
        + ". "
        + referred_to(draft, folder)
        + "."
        + (
            ASSUMED_SAYS.format(value=carried)
            if cautious(carried, side_values(conflict)[1])
            else ""
        )
    )


#: t93: the open item an RPO of his that disagrees with the register's derivation leaves. Third
#: person: it is accepted by id at the signature, so it is about him, never addressed to him.
RPO_DISAGREES = ("Human decisions: the recovery point — the manager set {his}. The dependency "
                 "register derives {derived} from {reason}. The record carries the manager's "
                 "figure; nemo put the choice to him.")


def rpo_disagrees_says(mine: dict[str, Any], derived: Any) -> str:
    """t93: both figures on one line, from the record's own statement and the derivation's own
    reason. nemo's note, on its own line: it is never appended inside his quote (the 79 rule)."""
    return RPO_DISAGREES.format(his=mine.get("value"), derived=derived.figure,
                                reason=", ".join(derived.reason) or "no named system")


def gap_ack(state: dict[str, Any], aid: str) -> dict[str, Any]:
    """The recovery gap acknowledged for this draft activity, as the state file holds it ({}:
    none)."""
    return (state.get(GAP_ACKS) or {}).get(aid) or {}


def gap_stands(state: dict[str, Any], aid: str) -> bool:
    """Whether an acknowledged recovery gap stands: acknowledged, and not closed in his own words
    (t76). A room decided before t76 has no acknowledgement on file, so the gap word on its RTO
    decision stands for it, exactly as it did then."""
    ack = gap_ack(state, aid)
    if ack:
        return not ack.get("closed")
    return is_gap(((state.get("decisions") or {}).get(f"{aid}.rto") or {}).get("value"))


def gap_closed_words(state: dict[str, Any], aid: str) -> str:
    """The words he closed this activity's recovery gap with, verbatim ("": he has closed none)."""
    return str((gap_ack(state, aid).get("closed") or {}).get("words") or "")


def act_turn(decisions: dict[str, Any], aid: str, key: str, x: dict[str, Any]) -> str:
    """t171: the turn of his act a row rests on: his decision on the item, or where a conflict's
    side set it (`by`) his tap on that conflict, or for an MTPD the method's rule carries, his tap
    on the rule. "" where no act of his on a turn is on file, and the referee refuses that row."""
    d = decisions.get(f"{aid}.{key}") or {}
    if key == "mtpd" and x.get("kind") == "method":
        d = decisions.get(f"{aid}-MTPD-RULE") or d
    if d.get("by"):
        d = decisions.get(d["by"]) or {}
    return str(d.get(TURN_ID) or "")


#: t171: the turn under way in each room, by the room's folder: its id and his words on it (typed,
#: or the tap he was shown) with its day. The app writes a turn's line only once the turn is over,
#: and an act of his is refereed in the very turn he takes it (a tap that settles stage 4's
#: refusal),
#: so until then this is the line his act rests on. The next turn replaces it; the file holds it.
#: nemo's own since 241 slice 4, which reads it beside the turn file (`walk.confirmed_turns`).
IN_FLIGHT = walk.IN_FLIGHT


def his_turns(folder: Path, wanted: set[str]) -> dict[str, dict[str, str]]:
    """His words on the wanted turns: the room's turn file, and the turn under way (`IN_FLIGHT`)."""
    tid, said = IN_FLIGHT.get(str(folder), ("", {}))
    return {**({tid: said} if tid in wanted else {}), **turn_file.his_turns(folder, wanted)}


def his_act(folder: Path | None, turn_id: str) -> dict[str, Any]:
    """t132/t171: his act as the record carries it: his words on that turn (typed, or the tap he
    was shown), its day and its id, read from the room's turn file and never from a model call. A
    turn not on the file gives no words, and the referee refuses the row rather than guess them."""
    said = his_turns(folder, {turn_id}).get(turn_id, {}) if folder and turn_id else {}
    return {"type": CHAT_CONFIRMATION, WORDS: said.get("words", ""), ON: said.get("on", ""),
            TURN_ID: turn_id}


def register_rows(
    register: dict[str, Any], assets: Any, activity: str | None
) -> list[dict[str, Any]]:
    """t171 (e): the register's own recovery point for each asset a derived RPO came from, as it
    gives it to THIS activity (t171-shape, DRAFT awaiting the owner): its consumer row for the
    activity, else an entry's own where it has no consumer rows at all (`recovery_point_for`)."""
    return [{"asset_id": x, "quote": point, ACTIVITY: activity}
            for x in assets if (point := recovery_point_for(register, x, activity)) is not None]


def build_proposal(draft: dict[str, Any], state: dict[str, Any], method: dict[str, Any],
                   folder: Path | None = None) -> dict[str, Any]:
    decisions = state.get("decisions", {})
    marked = bool(draft.get(drafting.MARKED_BY_NEMO))  # t79 fix 2, as `items` reads it
    register, interviews = _room_facts(folder, state, (draft.get("meta") or {}).get("activity", ""))
    activities, statements, deps_all, open_items = [], [], [], []
    rows = attached_rows(draft, state)
    figures: dict[str, dict[str, Any]] = {}
    for n, a in enumerate(effective(draft, decisions, method)):
        stmts = []
        # t76: the gap he acknowledged stands until he closes it in his own words, whatever target
        # he typed since; his words, once he has, are what the record says he closed it with
        ack = gap_ack(state, a["id"])
        stands, closed = gap_stands(state, a["id"]), gap_closed_words(state, a["id"])
        for label, key in (("MTPD", "mtpd_now"), ("RTO", "rto_now"), ("RPO", "rpo_now")):
            x = a[key]
            if not x.get("value"):
                continue
            value = x["value"]
            # fix 1 (I2): a gap he has closed is closed, whatever the RTO decision still carries,
            # so the record states his words instead of a flag the views would then refuse
            gap = label == "RTO" and not closed and (is_gap(value) or stands)
            if label == "RTO" and is_gap(value):
                # t71: the method's RTO for the MTPD the record carries (the manager's 0–4 h over a
                # grid's 8 h gave "< 8 h" against 0–4 h); the grid's own where it carries none.
                # t139 (13_nemo_check's ruling (1)): a method with no rto_map derives no RTO, so
                # the gap stays for the manager to state
                rto_map = method.get("rto_map") or {}
                value = rto_map.get(str((a["mtpd_now"] or {}).get("value")),
                                    rto_map.get(a["derived_now"], ""))
            if gap:
                # t75: whose account he settled on, where a conflict's side carried the gap. t76:
                # the speaker as the acknowledgement resolved him (fix 1, I4), so neither a target
                # he types later nor another side of that conflict moves the account on the record.
                # A room acknowledged before t76 carries no acknowledgement: read it live, as t75.
                account = ack.get("account") or (
                    "" if ack else side_speaker(draft, decisions,
                                                (decisions.get(f"{a['id']}.rto") or {}).get("by")))
            quote = x.get("quote") or ""
            if x.get("kind") == "manager":
                # t71: a figure the manager set rests on his decision, said with his reason, and
                # never on the draft's quote, which supports the figure he replaced
                quote = ""
                if label == "RPO" and value not in method.get(RPO_VOCABULARY, [value]):
                    word = words_by_duration(method).get(duration_of(str(value)))
                    value = word or value  # the method's own word for the duration he typed
                # t71b: never a note a tool call supplied; with no reason of his, "no reason given".
                # "He typed" only where he did. t171 (kind 6, 14_nemo_check's ruling): a value no
                # word of his gave is never said as given in chat; his act on its turn is the row
                x = {
                    **x,
                    "reason": f"{SET_BY}{(x.get('note') or NO_REASON).rstrip('.')}."
                    + (
                        (
                            f" He typed {x['value']}"
                            if x.get("typed")
                            else f" He confirmed {x['value']}, which was named in chat"
                        )
                        + f"; {value} is the method's word for it."
                        if value != x["value"]
                        and not gap
                        and (x.get("typed") or x.get("confirmed"))
                        else ""
                    ),
                }
            if x.get("kind") == "manager" and x.get("confirmed") and x.get("turn_id"):
                # t132 (ADR-0030): a figure named in chat and recorded by his tap is his
                # confirmation, never a quote: his words on that turn, its day and its id, read
                # from the room's turn file and never from the model's call. A turn not (yet) on
                # the file gives no words, and the referee refuses it rather than guess them.
                stmts.append({"label": label, "value": value, "speaker": "", "typed": x["value"],
                              "confirmed": True, "quote": "", "owner_stated": False,
                              "source_path": "", **his_act(folder, x["turn_id"]),
                              "origin": "manager", "gap": gap,
                              **({"account": account} if gap and account else {})})
                continue
            # t171: a figure of his, or nemo's proposal with no quote, rests on his act on a turn
            # (his typed words, or the tap he was shown), never on words under MANAGER unchecked
            his = x.get("kind") == "manager" or not quote
            stmts.append(
                {
                    "label": label,
                    "value": value,
                    "speaker": x.get("speaker") or "",
                    **({"typed": x["value"]} if x.get("kind") == "manager" else {}),
                    # a figure named in chat and recorded by his tap: origin `manager`, since
                    # tapping Record IS deciding, and the card counts it as his decision
                    # (8_nemo_check, 2026-09-21, on dispute 5959, overturning 7_nemo_check's
                    # ruling D: nemo cannot tell from data who first named a chat figure).
                    # The flag keeps the provenance on the evidence row.
                    **({"confirmed": True} if x.get("confirmed") else {}),
                    # t79 fix 2: the draft's own sentence alone — nemo's note never rides
                    # inside the quote the record carries and the signature accepts
                    "quote": quote
                    or (
                        x["reason"]
                        if x.get("kind") == "manager"
                        else "Proposed by nemo, confirmed by the manager in chat: "
                        + (said_alone(x, "reason", marked) or label)
                    ),
                    "owner_stated": x.get("kind") == "stated",
                    "source_path": x.get("path") if quote else "",
                    **(
                        his_act(folder, act_turn(decisions, a["id"], label.lower(), x))
                        if his
                        else {"type": TRANSCRIPT_QUOTE}
                    ),
                    **(
                        {"acts": [his_act(folder, x["reason_turn_id"])]}
                        if his and x.get("reason_turn_id")
                        else {}
                    ),
                    "origin": x.get("kind"),
                    "gap": gap,
                    **({"account": account} if gap and account else {}),
                }
            )
            if label == "MTPD" and x.get("withdrawn"):
                # t116 (b): the figure the record carries is the grid's. t171 on 116
                # (19_nemo_check's
                # STOP-B ruling (a)): the row under it rests on his Withdraw tap on its turn, a chat
                # confirmation, and never on a sentence of nemo's, which is no source
                stmts[-1].update(quote="", source_path="", origin="method", owner_stated=False,
                                 **his_act(folder, str((decisions.get(question_key(a["id"])) or {})
                                                       .get(TURN_ID) or "")))
            elif (label == "MTPD" and x.get("kind") == "method") or \
                    (label == "RTO" and is_gap(x["value"]) and x.get("kind") != "manager"):
                # t173 (ruling (a) above, on its two sibling sites): the rule's MTPD and the gap's
                # method target state a figure the draft's quote does not, so each row rests on his
                # act on its turn (his tap on the rule, or the one that acknowledged the gap), and
                # the draft's quote stays in the draft he decided on
                stmts[-1].update(quote="", source_path="", owner_stated=False,
                                 **his_act(folder, act_turn(decisions, a["id"], label.lower(), x)))
        scores = []
        for lens, row in a["grid"].items():
            if not any(isinstance(v, int) for v in a["grid_now"][lens].values()):
                continue
            quote = row.get("quote") or ""
            org = a["origin"][lens]
            # t171 (d): a score he changed rests on his act, and the draft's quote, which supports
            # the scores he replaced, is his evidence nowhere: it stays in the draft, the prior
            # value
            his = org == "manager" or not quote
            scores.append({"lens": lens,  # t79 fix 2: the same split, on the score rows
                           "quote": "" if org == "manager" else quote or (
                               "Proposed by nemo, confirmed by the manager in chat: "
                               + said_alone(row, "reason", marked)),
                           "speaker": row.get("speaker") or "", "row": a["grid_now"][lens],
                           "source_path": row.get("path") if quote and not his else "",
                           **(his_act(folder, act_turn(decisions, a["id"], lens, {})) if his
                              else {"type": TRANSCRIPT_QUOTE}), "origin": org})
        # 195: one entry per dependency, whatever the draft's list repeats
        deps = [
            {
                "heard": d.get("heard", ""),
                "owner": "",
                "asset_id": d.get("asset_id", ""),
                "held_by": "",
            }
            for d in unique_dependencies(a.get("dependencies") or [])
        ]
        # The floor: a register id a confirmed interview names is a dependency whatever the model
        # proposed (bia_figures, walked green 2026-09-18). Four models gave four different lists on
        # this room, and the one the best of them missed is the entry the RPO derives from.
        if register:
            origin = figures_deps.dependencies(
                register, interviews, [d["asset_id"] for d in deps if d["asset_id"]])
            known = {d["asset_id"] for d in deps}
            deps += [{"heard": "named in a confirmed interview", "owner": "", "asset_id": asset,
                      "held_by": ""}
                     for asset, came in sorted(origin.items())
                     if came == figures_deps.FILES and asset not in known]
            # 195 (the owner's "Gate it — AI proposes, you act"): everything else the model
            # proposed is his only where he tapped it, and the record says he added it. The
            # derivation below reads `origin`, so it reads the dependencies the record carries
            # and never one it does not.
            his = {i["asset_id"]: i
                   for i in proposed_dependencies(draft, state, register, interviews, folder)
                   if i["activity_id"] == a["id"] and i["added"]}
            deps = [d for d in deps if origin.get(d["asset_id"]) != figures_deps.PROPOSED
                    or d["asset_id"] in his]
            origin = {k: v for k, v in origin.items()
                      if v != figures_deps.PROPOSED or k in his}
            open_items += [ADDED_DEP_SAYS.format(name=i["name"], asset_id=i["asset_id"],
                                                 source=i["source"]) for i in his.values()]
            # 190 PER-CONSUMER (16_nemo_check): each dependency's RPO for THIS activity, its
            # consumer
            # row's first. Since 184 `dependencies` keeps every dependable entry (microsoft-365, no
            # top-level rpo), so `origin` is every dependency the record lists but a metadata key
            activity = (draft.get("meta") or {}).get("activity")
            derived = figures_impact.derive_rpo(origin, register, method, activity)
            # t93 (the owner's ruling of 2026-09-20T21:08:27Z, "Nemo asks you", on his own finding
            # that "'Nemo keeps' a figure you enter is false for some RPO changes"): a figure HE
            # set is never replaced by the derivation. It stands, as his typed MTPD stands against
            # the grid (his ruling of 2026-09-18), and where the two disagree the record says both
            # on its own line and nemo puts the choice to him as a tap. The derivation carries the
            # RPO where he set none, or where he handed it over himself (`DERIVED`).
            # Read from HIS DECISION, never from the draft's `kind`: a drafting model writes that
            # field, and a figure nobody set must not read as his.
            named = decisions.get(f"{a['id']}.rpo") or {}
            any_mine = next((s for s in stmts if s["label"] == "RPO" and s["origin"] == "manager"),
                            None)
            mine = any_mine if explicit_change(named) else None
            if derived.figure and mine is None:
                # Why the derivation carries it, where a decision named a figure anyway: a conflict
                # side that implied one (t71/t73b: an evidence side tightens and never loosens -
                # the method's own semantics, and the owner's parked question), or his own choice
                # to hand it over (t93). fix 1: the fidelity check no longer READS either
                # sentence — it keys on the decision — so these words are ticket 91's to change;
                # an implied figure equal to the derivation leaves its evidence exactly as it was.
                said = (
                    None
                    if any_mine and same_figure(any_mine["value"], derived.figure)
                    else any_mine
                )
                why = ""
                if said:
                    why = (f" The manager's {said['typed']} is not tighter, so the derivation "
                           "stands.")
                elif named.get("decision") == DERIVED and (named.get("over") or {}).get("value"):
                    why = (f" The manager set {named['over']['value']} and chose the register's "
                           "figure over it.")
                stmts = [s for s in stmts if s["label"] != "RPO"]
                stmts.append({
                    "label": "RPO", "value": derived.figure, "speaker": "",
                    "quote": "Derived from the dependency register: the tightest recovery point "
                             f"among the systems this activity depends on that hold data "
                             f"({', '.join(derived.reason) or 'none'})." + why,
                    "owner_stated": False, "source_path": "", "type": REGISTER_ROW,
                    # t171 (e): it rests on the register's own row for each asset it came from
                    "rows": register_rows(register, derived.reason or list(origin), activity),
                    # t93/t171: where he handed the RPO over, his act of handing it over and, under
                    # it, his act that set his own figure: each on its turn, so none vanishes
                    "acts": [his_act(folder, str(d.get(TURN_ID) or ""))
                             for d in ([named, explicit_change(named.get("over"))]
                                       if named.get("decision") == DERIVED else []) if d],
                    "origin": "method", "gap": False})
            elif any_mine is None and derived.reason == (figures_impact.NO_DATA_HELD,):
                # 190 (the owner's "No RPO at all"): none of the dependencies holds data and the
                # method has no word for that, so the record carries no RPO, and says why, in
                # place of a figure the draft proposed. A figure he set stands (`any_mine`): his
                # own, or one a side he took implied, which is tighter than no RPO (`tighter`).
                stmts = [s for s in stmts if s["label"] != "RPO"]
                stmts.append({
                    "label": "RPO", "value": None, "speaker": "",
                    "quote": "Derived from the dependency register: no RPO, because "
                             f"{figures_impact.NO_DATA_HELD}.",
                    "owner_stated": False, "source_path": "", "type": REGISTER_NO_RPO,
                    # t171-shape (DRAFT, awaiting the owner): the register gives this activity no
                    # RPO, which the referee confirms against every dependency listed here
                    ACTIVITY: activity, ASSET_IDS: list(origin),
                    "origin": "method", "gap": False})
            elif mine and derived.figure and tighter(mine["value"], derived.figure):
                # t71's approved rule, and his own proven walk ("0 h (no loss)"): his tighter
                # figure stands and the record says so. Untouched by t93, which is about the
                # disagreement his finding names - the one that was dropped in silence.
                mine["quote"] += (
                    f" The register derives {derived.figure}; the manager's figure is "
                    "tighter, so it stands."
                )
            elif mine and derived.figure and not same_figure(mine["value"], derived.figure):
                # t93: his figure is NOT tighter, so until now it was dropped and the record said
                # "The manager's X is not tighter, so the derivation stands" - the owner's finding
                # 1, word for word. Now his stands, both figures are on the record's own open line,
                # and nemo puts the choice to him. nemo's note goes on its own line, never inside
                # his quote (the 79 rule). `derived` beside it is nemo's own reading of the
                # register, kept out of `clean` (the record's evidence) and read by the tap.
                mine["derived"], mine["derived_reason"] = derived.figure, list(derived.reason)
                open_items.append(rpo_disagrees_says(mine, derived))
        clean = [
            {k: i[k] for k in ("label", "value", "speaker", "quote", "owner_stated")} for i in stmts
        ]
        figures[a["id"]] = {i["label"]: i["value"] for i in stmts}
        activities.append({"name": a["name"], "impact_grid": a["grid_now"], "evidence": clean,
                           "evidence_meta": stmts,
                           # t76: the words he closed an acknowledged gap with, so every view says
                           # from the record itself that he closed it and what he said
                           **({GAP_CLOSED: closed} if closed else {}),
                           "scores": scores, "dependencies": deps,
                           # t72b: evidence only, on the (single) activity an added one is agreed as
                           **({"risk_rows": rows} if rows and n == 0 else {}),
                           "owner_name": (a.get("owner") or {}).get("name", ""),
                           **_answers(decisions.get(question_key(a["id"])),
                                      (a["mtpd_now"] or {}).get("withdrawn_quote"))})
        statements += clean
        deps_all += deps
    for c in draft.get("conflicts") or []:
        d = decisions.get(c["id"]) or {}
        if isinstance(d.get("side"), int) and d["side"] < len(c.get("sides") or []):
            side = c["sides"][d["side"]]
            open_items.append(settled_says(c.get("about"), side.get("speaker"), side.get("claim"),
                                           kept_line(d)))
        elif d.get("decision") == UNRESOLVED:
            # t76: open, referred to the activity's owner (t84r), and the figure the record
            # carries meanwhile named as an assumption where it is the cautious one
            item, _ = side_values(c)
            carried = figures.get(item.split(".")[0], {}).get(item.rsplit(".", 1)[-1].upper()) \
                if item else None
            open_items.append(unresolved_says(c, carried, draft, folder))
    return {"evidence": statements, "dependencies": deps_all, "open_items": open_items,
            "worst_case": {}, "not_elicited": "", "activities": activities}



def _answers(d: dict[str, Any] | None, withdrawn_quote: str | None = None) -> dict[str, Any]:
    """t116: his answer to the referee's question, as the record carries it (`ANSWERS`): the
    answer, the two figures it answered, his reason word for word where he typed one, and
    nemo's fixed words for it. A withdrawal is in the trail only while it stands (`withdrawn`,
    read here off the figure `effective` withdrew), with the quote that stated the withdrawn
    figure (14_nemo_check's ruling (b)): that quote is never under the grid's MTPD."""
    word = (d or {}).get("decision")
    if word == DERIVED and withdrawn_quote is not None:
        answer = referee.WITHDRAW
    elif word in (referee.KEEP, UNRESOLVED):
        answer = referee.KEEP if word == referee.KEEP else referee.LEAVE_OPEN
    else:
        return {}
    # t224: the entry is nemo's to write, so the walk's door writes the same bytes
    return referee.his_answers(answer, (d or {}).get("asserted"), (d or {}).get("derived"),
                               (d or {}).get("reason"), withdrawn_quote)


# ── the scope list: what a BIA is about, fixed at stage 1 (owner's ruling, 2026-09-17) ────────
PRIOR = "08_Prior-Cycle"
_PRIOR_LINE = re.compile(r"^###\s+(BIA-\d{4}-\d+)\s+[—-]\s+(.+?)\s*(\*\(.*\)\*)?\s*$", re.M)


PROCESS_MAP = "01_Organisation/process-map.md"
#: t377 D1: the BIA programme plan, which says which BIAs are due for review
PROGRAMME_PLAN = "01_Organisation/bia-programme-plan.md"
#: t377 F1: the room's planning files, a source in the figure check (`Session._flag`) whether
#: the model read them this turn or not. Named one by one, never "every room file": 09_Evaluation's
#: synthetic poison file must never trace.
TRACED_PLANS = (PROGRAMME_PLAN,)
#: a process-map row: `| <no.> | <name> | `<slug>` | ...` (ticket 137's map)
_MAP_ROW = re.compile(r"^\|\s*[\d.]+\s*\|\s*([^|]+?)\s*\|\s*`([^`|]+)`\s*\|", re.M)


def _map_key(text: str) -> str:
    """A process-map cell as it is compared: hyphens as spaces, trimmed, case ignored."""
    return text.replace("-", " ").strip().lower()


class MapRow(NamedTuple):
    """One process as the room's process map states it (t261). `upstream` and `downstream` are the
    names its cells give ("none" or blank is no name); None where its table has no such column."""

    group: str
    number: str
    name: str
    slug: str
    walkable: bool
    upstream: tuple[str, ...] | None
    downstream: tuple[str, ...] | None


def _neighbours(cell: str | None) -> tuple[str, ...] | None:
    """The activities a map cell names; "none" and t333's "not stated" (the HR and IT records say
    nothing there) name none."""
    if cell is None:
        return None
    names = (n.strip() for n in re.split(r"[,;]", cell))
    return tuple(n for n in names
                 if n and n.lower() not in ("none", "not stated", "-", "\u2014"))


def process_map_rows(folder: Path) -> list[MapRow]:
    """t261: every row of the room's process map, in its order, each under its `## ` group (the
    heading's own words, its number dropped). The one reader of the map: `process_map_order`, the
    workspace's page, and whoever follows the chain. A room with no map has no rows."""
    path = folder / PROCESS_MAP
    rows: list[MapRow] = []
    group, header = "", [""]
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        if line.startswith("## "):
            group = re.sub(r"^[\d.]+\s*", "", line[3:].strip())
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            slug = re.fullmatch(r"`([^`|]+)`", cells[2]) if len(cells) > 2 else None
            if not (re.fullmatch(r"[\d.]+", cells[0]) and slug):
                header = [c.lower() for c in cells] if cells[0].lower() == "no." else header
                continue
            cell = dict(zip(header, cells, strict=False))
            rows.append(MapRow(group, cells[0], cells[1], slug[1],
                               cell.get("walkable", "").lower() == "yes",
                               _neighbours(cell.get("upstream")),
                               _neighbours(cell.get("downstream"))))
    return rows


def resource_needs(folder: Path, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """t263: how soon each resource is needed back (`needs.needs`), from the room sheet's `rows`
    (each activity's MTPD as the room holds it, record else draft), the room's register and its
    process map's chain, read through `process_map_rows` alone."""
    chain = process_map_rows(folder)
    slug_of = {r.name: r.slug for r in chain}
    held = {r["activity"]: needs.Held(
        next((m.name for m in chain if m.slug == r["activity"]), r["activity"]),
        r["figures"]["MTPD"]["value"], r["figures"]["RTO"]["value"],
        r["figures"]["MTPD"]["mark"] == ACCEPTED) for r in rows}
    down = {r.slug: tuple(slug_of[n] for n in r.downstream or () if n in slug_of) for r in chain}
    register = drafting.read_register(folder)
    return needs.needs(register, held, down, walk._method(folder))


def process_name(folder: Path, process: str) -> str:
    """t139 F2: the name the room's process map gives a slug, or the process as it came.

    A walk keys a process on its slug ("order-picking"); the prior cycle heads it by name ("Order
    picking"), and a slug does not start with the name. A room with no map, or a process the map
    does not list, is matched as it always was.

    t139f: callers also hand in the humanised slug ("Helpdesk and support"), which the map's own
    name need not begin with ("IT helpdesk and support"), so a row is reached through either of
    its two columns — hyphens read as spaces, case ignored."""
    return _listed_name(folder, process) or process


def _listed_name(folder: Path, process: str) -> str | None:
    """The name the room's process map gives a process (by slug or name), None if unlisted."""
    path = folder / PROCESS_MAP
    if path.is_file():
        want = _map_key(process)
        for name, slug_ in _MAP_ROW.findall(path.read_text(encoding="utf-8")):
            if want in (_map_key(slug_), _map_key(name)):
                return name  # type: ignore[no-any-return]  # re.findall's items are Any
    return None


def map_name(folder: Path, process: str) -> str:
    """255b: a process as a heading shows it, the process map's name, never its slug ("Goods
    dispatch and delivery" for `dispatch-and-delivery`). A process the map does not list reads as
    its own words, hyphens as spaces (252b's rule); t358: a listed one keeps the map's name word for
    word, hyphens and all ("One-off payments and salary transfers")."""
    return _listed_name(folder, process) or process.replace("-", " ")


def scope_from_files(folder: Path, process: str) -> dict[str, Any]:
    """The activities this BIA is about, and where the list comes from.

    A BIA activity is what the manager agreed at stage 1, never what an interview's headings
    happen to be: an interview written in six sections is six sections of evidence about the
    activity in scope. The list starts from the room's own prior cycle, so "the activities that
    are set initially" is read off the files rather than proposed by a model.
    """
    first = process_name(folder, process).split("/")[0].strip().lower()
    for md in sorted((folder / PRIOR).glob("*.md")) if (folder / PRIOR).is_dir() else []:
        for ref, name, _ in _PRIOR_LINE.findall(md.read_text(encoding="utf-8")):
            if name.split("(")[0].strip().lower().startswith(first):
                return {"activities": [name], "source": f"{PRIOR}/{md.name} · {ref}",
                        "how": "last cycle's BIA names this as one activity"}
    if is_added(folder, process):  # 13_nemo, t72: no file lists it; the manager named it
        return {
            "activities": [process],
            "source": f"the manager, who added it to the room ({ADDED})",
            "how": "no prior cycle names it, so it is one activity on its own",
        }
    return {"activities": [process], "source": "the room's own interview files",
            "how": "no prior cycle names it, so the process itself is the one activity"}


def collapse_to_scope(draft: dict[str, Any], names: list[str]) -> dict[str, Any]:
    """The draft as the agreed scope, merging the interview's sub-steps into the scoped activity.

    Merged conservatively, the way the method's MIN principle reads: the worst score per category
    and horizon wins and carries its own quote, the tightest MTPD and RTO win, and every
    dependency is kept. Nothing is averaged and nothing is dropped.
    """
    acts = draft.get("activities") or []
    if len(acts) <= 1 or [a.get("name") for a in acts] == names:
        return draft
    target = names[0]
    horizons = [h for a in acts for h in next(iter(a["grid"].values()))["scores"]]
    horizons = list(dict.fromkeys(horizons))
    grid: dict[str, Any] = {}
    for lens in dict.fromkeys(l for a in acts for l in a["grid"]):
        rows = [(a["name"], a["grid"][lens]) for a in acts if lens in a["grid"]]
        scores, whose = {}, {}
        for h in horizons:
            best = [(r["scores"].get(h), name, r) for name, r in rows
                    if isinstance(r["scores"].get(h), int)]
            if best:
                score, name, row = max(best, key=lambda x: x[0])
                scores[h], whose[h] = score, (name, row)
            else:
                scores[h] = MISSING
        sources = {name for name, _ in whose.values()}
        # The worst cell decides, so the row can come from more than one sub-step. One quote can
        # only speak for one of them: a mixed row is the model's proposal, with the sub-step that
        # set the worst cell quoted and the others named. A row from a single sub-step keeps its
        # own kind and quote.
        at_worst = max(whose.values(), key=lambda x: max(v for v in x[1]["scores"].values()
                                                         if isinstance(v, int)), default=None) \
            if whose else None
        row = dict(at_worst[1]) if at_worst else {"lens": lens, "quote": "", "kind": "none"}
        row["scores"] = scores
        row["from"] = sorted(sources)
        if len(sources) > 1:
            row["kind"] = "proposed"
            # t79 fix 1: nemo composes this reason, so it carries `floor` like every other sentence
            # nemo puts into the draft object, and a card attributes it to nemo and not to the model
            row["floor"] = True
            row["reason"] = ("worst case across " + ", ".join(sorted(sources)) +
                             # why: `at_worst` is set here: two sources mean `whose` was not empty
                             f"; the quote is {at_worst[0]}'s")  # type: ignore[index]
        grid[lens] = row

    def tightest(key: str) -> dict[str, Any]:
        seen = [a[key] for a in acts if (a.get(key) or {}).get("value")]
        if not seen:
            return {}
        def minutes(x: dict[str, Any]) -> int:
            # `or` would be wrong here: an MTPD of "0–4 h" parses to 0, which is falsy, and the
            # tightest clock in the set would lose to every other one.
            parsed = duration.minutes(str(x["value"]))
            return parsed if parsed is not None else 10 ** 9

        return min(seen, key=minutes)

    merged = {
        "id": "A0", "name": target,
        "owner": acts[0].get("owner") or {},
        "grid": grid,
        "mtpd": tightest("mtpd"), "rto": tightest("rto"),
        "rpo": next((a["rpo"] for a in acts if (a.get("rpo") or {}).get("value")), {}),
        "dependencies": [d for a in acts for d in a.get("dependencies") or []],
        "merged_from": [a["name"] for a in acts],
    }
    merged["derived_mtpd"] = acts[0].get("derived_mtpd")
    ids = {a["id"] for a in acts}
    conflicts = []
    for conflict in draft.get("conflicts") or []:
        sides = []
        for side in conflict.get("sides") or []:
            implied = side.get("implies")
            if isinstance(implied, dict) and str(implied.get("item_id", "")).split(".")[0] in ids:
                field = str(implied["item_id"]).split(".", 1)[-1]
                implied = {**implied, "item_id": f"{merged['id']}.{field}"}
            sides.append({**side, "implies": implied})
        conflicts.append({**conflict, "sides": sides, "activity": target})
    return {**draft, "activities": [merged], "_conflicts_remapped": True,
            "scope_note": f"{len(acts)} sub-steps named in the interview were merged into "
                          f"{target!r}: the worst score per category and the tightest clock win.",
            "conflicts": conflicts}



_PRIOR_FIELD = re.compile(r"^\|\s*(MTPD|RTO[^|]*|MBCO|Rank[^|]*)\s*\|\s*(.+?)\s*\|\s*$", re.M)


#: t256: the impact grid as the prior cycle states it, one table per section: its header row names
#: the horizons, each row a category, its remark and one cell per horizon ("–" is a blank cell)
_PRIOR_GRID = re.compile(
    r"^\| *Category *\| *Remark *\|(.+)\| *\n\|[-| ]+\| *\n((?:\|.*\| *(?:\n|$))+)", re.M)
#: t256: an earlier signed walk's record, as ticket 245 set it aside, said where `ref` is shown
SET_ASIDE_REF = "the earlier signed BIA"
#: t282 (ADR-0045 amended): the process owner last year's record states for an activity, and the
#: record's number ("1.1"), which the organisation file's Records column names
_PRIOR_OWNER = re.compile(r"^\|\s*Process owner\s*\|\s*(.*?)\s*\|\s*$", re.M)
_PRIOR_NUMBER = re.compile(r"^\|\s*Prior BIA record\s*\|\s*(.*?)\s*\|\s*$", re.M)
#: t377: the record's interview and its participants, as stated
_PRIOR_INTERVIEW = re.compile(r"^\|\s*Interview\s*\|\s*(.*?)\s*\|\s*$", re.M)
_PRIOR_PEOPLE = re.compile(r"^\|\s*Participants\s*\|\s*(.*?)\s*\|\s*$", re.M)


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _prior_grid(section: str) -> dict[str, Any] | None:
    """t256: the grid as the record states it, `{category: {"remark", "cells": {horizon: value}}}`;
    a blank cell ("–") stays blank (""), and nothing is filled in. None where the section holds
    none.
    For display only (ADR-0044's note): the comparative check reads the figures, never this."""
    found = _PRIOR_GRID.search(section)
    if not found:
        return None
    horizons = _cells(found.group(1))
    grid: dict[str, Any] = {}
    for row in found.group(2).strip().splitlines():
        category, remark, *values = _cells(row)
        grid[category] = {"remark": remark, "cells": {
            h: "" if v == "–" else v for h, v in zip(horizons, values, strict=False)}}
    return grid


def last_year(folder: Path, scope_name: str) -> dict[str, Any]:
    """What last cycle's BIA said about this activity: named figures, which the comparative check
    reads, never grids (ticket 39, ADR-0014).

    Matched on the activity name the prior cycle itself used (ticket 38). No match is "first
    assessment" and says so, because a comparison nobody can make is not a finding.

    t256: `grid` is the impact grid as that record states it, for display only (ADR-0044's note),
    and absent where it states none. t282: `owner`, its process owner as the record states it
    ("purchasing management (Jens Harder)"), and `record`, its number ("1.1"), each absent where
    it states none. With no prior-cycle
    section, an earlier signed walk of this process set aside under ticket 245 is last year's record
    too: `found`, `source` its file, and no figures, grid or owner, because the certificate states
    none. `source` always says which was read.
    """
    head = process_name(folder, scope_name).split("(")[0].strip().lower()
    for md in sorted((folder / PRIOR).glob("*.md")) if (folder / PRIOR).is_dir() else []:
        text = md.read_text(encoding="utf-8")
        for match in _PRIOR_LINE.finditer(text):
            if not match.group(2).split("(")[0].strip().lower().startswith(head):
                continue
            section = text[match.end(): text.find("\n### ", match.end()) % (len(text) + 1)]
            figures = {label.split("(")[0].strip().upper(): value
                       for label, value in _PRIOR_FIELD.findall(section)}
            grid = _prior_grid(section)
            stated = {key: found.group(1) for key, rx in (("owner", _PRIOR_OWNER),
                                                          ("record", _PRIOR_NUMBER),
                                                          ("interview", _PRIOR_INTERVIEW),
                                                          ("participants", _PRIOR_PEOPLE))
                      if (found := rx.search(section))}
            return {"found": True, "ref": match.group(1), "name": match.group(2),
                    "figures": figures, "source": f"{PRIOR}/{md.name}", **stated,
                    **({"grid": grid} if grid is not None else {})}
    for aside in sorted((folder / "output").glob(f"*/{walk.SET_ASIDE.format(run='*')}")):
        if _map_key(process_name(folder, aside.parent.name)) == _map_key(head):
            return {"found": True, "ref": SET_ASIDE_REF, "name": scope_name, "figures": {},
                    "source": aside.relative_to(folder).as_posix()}
    return {"found": False, "note": "no prior cycle names this activity — first assessment"}


# ── runtime patches over nemo (this process only) ────────────────────────────────────────────
def quoted_paths(draft: dict[str, Any]) -> set[str]:
    """Every room file a verified quote in the draft names (t72: what the referee must read)."""
    items = [
        i
        for a in draft.get("activities") or []
        for i in [
            *(a.get("grid") or {}).values(),
            *(a.get(f) or {} for f in ("mtpd", "rto", "rpo")),
            a.get("owner") or {},
            *(a.get("dependencies") or []),
        ]
    ]
    items += [s for c in draft.get("conflicts") or [] for s in c.get("sides") or []]
    items += draft.get("risk_rows") or []  # t72b: the risk-register floor's rows
    return {
        i["path"] for i in items if i.get("verified_quote") and i.get("quote") and i.get("path")
    }


def _rows(i: dict[str, Any]) -> list[dict[str, Any]]:
    """The record's evidence rows for one statement: his act (t132/t171: no quote, no file), the
    register's rows (t171 (e): each asset's own words in the room's register), or a quote; then
    any further act of his it rests on (t171: his reason's turn, or a hand-over and his figure
    under it), each checked against its turn like the first."""
    if i.get("type") == CHAT_CONFIRMATION:
        rows = [{TYPE: CHAT_CONFIRMATION, WORDS: i[WORDS], ON: i[ON], TURN_ID: i[TURN_ID]}]
    elif i.get("type") == REGISTER_ROW:
        rows = [
            {
                TYPE: REGISTER_ROW,
                ACTIVITY: r[ACTIVITY],
                ASSET_ID: r["asset_id"],
                QUOTE: r["quote"],
                SOURCE_PATH: REGISTER,
            }
            for r in i.get("rows") or []
        ]
    elif i.get("type") == REGISTER_NO_RPO:
        rows = [
            {
                TYPE: REGISTER_NO_RPO,
                ACTIVITY: i[ACTIVITY],
                ASSET_IDS: i[ASSET_IDS],
                SOURCE_PATH: REGISTER,
            }
        ]
    else:
        rows = [{TYPE: i.get("type", TRANSCRIPT_QUOTE), QUOTE: i["quote"],
                 SOURCE_PATH: i.get("source_path") or ""}]
    return rows + [_rows(act)[0] for act in i.get("acts") or []]


def _patched_activity(proposed: dict[str, Any]) -> dict[str, Any]:
    # t131: the source_path written here is only the draft's claim. nemo's `bia.build` replaces it
    # on every transcript quote with the first confirmed file holding the words (and `also_in` for
    # the others), and keeps it (else the bound interview) only for words found nowhere, which the
    # referee then refuses naming it. The "" stands only on a manager_confirmed entry. t132: a chat
    # confirmation carries no quote and no file at all (his words, its day and its turn id).
    out = {
        "name": proposed["name"],
        OWNER: proposed.get("owner_name") or bia._owner(proposed),
        IMPACT_GRID: proposed["impact_grid"],
        EVIDENCE: [
            row
            | {
                "origin": i.get("origin"),
                "label": i.get("label"),  # t71: which figure it stands behind
                # t80: a figure named in chat and recorded by his tap; provenance only
                **({"confirmed": True} if i.get("confirmed") else {}),
            }
            for i in proposed.get("evidence_meta", proposed["evidence"])
            for row in _rows(i)
        ]
        + [
            row | {LENS: i["lens"], "origin": i.get("origin")}
            for i in proposed["scores"]
            for row in _rows(i)
        ]
        +
        # t72b: a risk-register row attached to an added activity, its line word for word
        [
            {
                TYPE: TRANSCRIPT_QUOTE,
                QUOTE: r["quote"],
                SOURCE_PATH: r["path"],
                "origin": r["origin"],
            }
            for r in proposed.get("risk_rows") or []
        ],
        DEPENDENCIES: [i["asset_id"] for i in proposed["dependencies"] if i["asset_id"]],
        **bia._stated(proposed["evidence"]),
    }
    gap = next((i for i in proposed.get("evidence_meta", []) if i.get("gap")), None)
    if gap:
        out["recovery_gap_flagged"] = True
        if gap.get("account"):  # t75: whose account he settled on, so every view says it from here
            out[GAP_ACCOUNT] = gap["account"]
    if proposed.get(GAP_CLOSED):  # t76: the words he closed an acknowledged gap with
        out[GAP_CLOSED] = proposed[GAP_CLOSED]
    if proposed.get(ANSWERS):  # t116: his answers to the referee's questions
        out[ANSWERS] = proposed[ANSWERS]
    return out


_orig_readable = walk.readable


def _patched_readable(room_folder: Path, saved: dict[str, Any]) -> dict[str, str]:
    """nemo's confirmed interviews, off the run record (ticket 168), then what nemo does not hold:
    an added activity's room files its draft quotes (t72) and its risk rows (t72b). A run the skin
    confirmed before 168 has no list on its record, and its confirmed set is still this file's."""
    state = load_state(room_folder, saved["process"])
    legacy = walk.INTERVIEWS_CONFIRMED not in saved and state.get("interviews")
    files = {p: interview_text(jailed_path(room_folder, p)) for p in legacy} if legacy \
        else _orig_readable(room_folder, saved)
    extra = (state.get("sources") or []) + [
        r["path"] for r in attached_rows(state.get("draft") or {}, state)
    ]
    return {
        **files,
        **{p: interview_text(jailed_path(room_folder, p)) for p in extra if p not in files},
    }


_orig_evidence_card = walk.evidence_card


def _patched_evidence_card(room_folder: Path, process: str) -> walk.Card:
    saved = walk.read_record(room_folder, walk.run_file(process)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
    state = load_state(room_folder, process)
    draft = state.get("draft") or {}
    method = json.loads((room_folder / walk.METHOD).read_text())
    open_ = open_items(state)
    proposal = build_proposal(draft, state, method, room_folder) if draft and not open_ else {}
    # `name` is nemo's own name for its stage-3 card (nemo 729a22b: a decision records which card
    # it was taken on). nemo spells it inside `walk.evidence_card` and nowhere a caller can read,
    # so it is retyped here and pinned against nemo's own card in tests/test_stage3_cards.py.
    return walk.Card(stage=walk.STAGE_3, name="evidence", heading=walk.HEADING_3,
                     activities=(process,),
                     body=f"{len(open_)} proposals still open" if open_ else "draft settled",
                     sources=tuple(state.get("interviews") or []), buttons=walk.GRADIENT,
                     decision=walk.DECISION_3, rule=walk.RULE_3, gradient=walk.GRADIENT,
                     method=walk._method(room_folder), saved=saved,
                     revision=walk._revision(saved), proposal=proposal)


def _mtpd_words(method: dict[str, Any]) -> list[str]:
    """t139 (13_nemo_check's ruling (2)): the MTPD's words are the method's horizons and its own
    word for past the last one (`beyond_horizons`). A method that states no such word is the old
    seed's, whose words were its rto_map keys, and those stay its words."""
    beyond = method.get(BEYOND_HORIZONS)
    if beyond:
        return [*(method.get(TIME_HORIZONS) or []), str(beyond)]
    return list(method.get("rto_map") or {})


#: a band MTPD read at its upper edge (t74), and whether the record's target is outside the MTPD it
#: carries (t75): nemo's own since t133, because the gap sentences he signs read them
BAND, upper_edge, gap_reading = handover.BAND, handover.upper_edge, handover.gap_reading


def needs_gap(a: dict[str, Any], method: dict[str, Any] | None = None) -> bool:
    """Whether the record's own figures put its target outside its MTPD (`gap_reading`)."""
    return gap_reading(a, method) is True


#: 241 slice 3 (D2): t74's band MTPD, read at its upper edge, is nemo's own
#: (`referee._review_recovery`, `walk._refusal_says`), no longer a patch over them. The edge
#: sentence's name stays here for the tests that read it.
EDGE_SAYS = walk.EDGE_SAYS


#: Ticket 134: `handover.capacity` used to be patched here, and the delegate's authority was read
#: out of a module global holding the role string he had typed. Who he signs as is his own explicit
#: choice now (ADR-0030 decision 7): nemo draws the two taps (`walk.signing_choices`) and the one he
#: picks is an argument of `sign`, so nothing typed about anybody decides it.
#: 241 slice 2 (ADR-0030 decision 5): the certificate he signs, its figure lines and the 190 no-RPO
#: words are nemo's own (`handover.certificate`), no longer a patch over it. The names stay here for
#: the stage card and the fidelity check, which read them.
ON_BEHALF, NO_RPO = handover.ON_BEHALF, handover.NO_RPO
no_rpo, rpo_clause, figure_line = handover.no_rpo, handover.rpo_clause, handover.figure_line


def norm_name(name: str) -> str:
    return " ".join(str(name).lower().split())


#: t71/t75/t76/t79 fix 1: the recovery-gap sentences the BIA, the handover and the certificate say
#: are nemo's own since t133 (ADR-0030 decision 5): one source writes what he signs. The names stay
#: here for the stage card and the fidelity check, which read them.
GAP_ACCOUNT, ACCOUNT_SAYS = handover.GAP_ACCOUNT, handover.ACCOUNT_SAYS
GAP_SAYS, GAP_ACK_SAYS, GAP_CARRIED_SAYS = (handover.GAP_SAYS, handover.GAP_ACK_SAYS,
                                            handover.GAP_CARRIED_SAYS)
GAP_WORDS, WHERE_WORDS = handover.GAP_WORDS, handover.WHERE_WORDS
CLOSED_MARK, CLOSED_WORDS, CLOSED_SAYS = (handover.CLOSED_MARK, handover.CLOSED_WORDS,
                                          handover.CLOSED_SAYS)
gap_says, gap_words = handover.gap_says, handover.gap_words
closed_says, closed_words = handover.closed_says, handover.closed_words
#: the same three as a stage card says them, because a card addresses him. Which spelling a sentence
#: is in comes from the function composing the document, never from a flag a caller passes:
#: `nemo.handover` writes the BIA, the handover and the certificate, and
#: `Session.record_card_text` the card, so each one names the words its own document speaks in.
CLOSED_MARK_TO_HIM = "a recovery gap you closed"
CLOSED_WORDS_TO_HIM = CLOSED_MARK_TO_HIM + ", in your own words: “{words}”"
CLOSED_SAYS_TO_HIM = ("For {activity} the record carries " + CLOSED_MARK_TO_HIM + ": you recorded, "
                      "in your own words, that the arrangements can now meet the recovery target "
                      "— “{words}”.")
#: both spellings, for the check that holds every view stating a close to the words he typed
CLOSED_MARKS = (CLOSED_MARK, CLOSED_MARK_TO_HIM)


def closed_says_to_him(a: dict[str, Any]) -> str:
    """The same sentence as a stage card says it, because a card speaks to him (t79 fix 1)."""
    return CLOSED_SAYS_TO_HIM.format(activity=a.get("name"), words=a.get(GAP_CLOSED))


def closed_words_to_him(a: dict[str, Any]) -> str:
    """The same few words as a stage card's figure line carries them (t79 fix 1)."""
    return CLOSED_WORDS_TO_HIM.format(words=a.get(GAP_CLOSED))


#: 241 slice 4: the activities a manager added (t72) and the turn under way (t171) are nemo's own
#: (`walk.processes`, `walk.confirmed_turns`), no longer patches over them.
_orig_refereed = walk._refereed


# why: a ticket-105 site (ADR-0030, site 6): 128 touches it no further than this
def _patched_refereed(room_folder: Path, saved: dict[str, Any], method: dict[str, Any]):  # type: ignore[no-untyped-def]
    """Stage 4 reads the draft as the manager has settled it NOW, so a fix made after a refusal
    lands."""
    state = load_state(room_folder, saved.get("process", ""))
    if state.get("draft") and not open_items(state):
        room_method = json.loads((room_folder / walk.METHOD).read_text())
        saved = {**saved, **build_proposal(state["draft"], state, room_method, room_folder)}
    return _orig_refereed(room_folder, saved, method)


def install_patches() -> None:
    walk._refereed = _patched_refereed
    bia._activity = _patched_activity
    walk.readable = _patched_readable
    walk.evidence_card = _patched_evidence_card
    # why: a ticket-105 site (ADR-0030, site 6): 128 touches it no further than this
    walk._WHAT_FOLLOWS = tuple(  # type: ignore[assignment]
        (s, a, _patched_evidence_card if f.__name__ == "evidence_card" else f)
        for s, a, f in walk._WHAT_FOLLOWS
    )


def open_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    if not state.get("draft"):
        return []
    return [i for i in items(state["draft"]) if i["id"] not in state.get("decisions", {})]


# ── refusals: a wrong call or a standing refusal, told apart where they are raised (ticket 67) ──
#: A wrong call: the model called a tool the walk cannot take now (another stage's tool, an item id
#: that does not exist). The model repairs it by making the right call, in the same turn.
#: t107: which text a turn's line holds. `Session.turn` returns, and its "said" line holds, the
#: RAW text the model and nemo wrote; the turn he reads is NAMED by the skin that draws it (the app,
#: and the scenario turn file, through `drawn_turn`): each abbreviation and method term followed
#: by its plain name at its first use in the turn, and (t215) the standard's own words at their
#: first use in the conversation.
RAW, NAMED = "raw", "named"
WRONG_CALL = "wrong_call"
#: A standing refusal: the world says no, and nothing the model calls will change it this turn.
#: The whole reply is the refusal: the skin ends the model's turn and renders `say` with `next` as
#: the taps, and nothing the model wrote goes beside it (v1's M3: a refusal the model is left to
#: word becomes "retry?" or an invented way round it).
STANDING = "standing"

#: What a standing refusal waits on, in words; `Session._precondition` reads each off the files.
WAITS_ON = {
    "draft_exists": "a prepared draft for this activity",
    "run_not_closed": "the run not being signed, which it never stops being",
    "handover_accepted": "the handover accepted at step 5",
    "record_changes": "a change to the record the referee refused",
    "record_faithful": "the record and the views carrying every decision made in the walk",
    "reservation_typed": "the reservation, typed by the manager in his own words",
    "gap_closed_typed": "the words closing the recovery gap, typed by the manager himself",
    # t80/t83 (the owner, 2026-09-20: "Gate it - AI proposes, you act"): both wait on an act of
    # his, which is the same tool called again off the model's turn, so neither is held (`hold`).
    "figure_set_by_him": "the figure, set by the manager himself",
    "referral_made_by_him": "the referral, made by the manager himself",
    # t94 (the owner, 2026-09-21: "only your tap may accept all"): the same shape again.
    "accepted_by_him": "the open proposals, accepted by the manager himself",
    # fix 3: every other decide on a model turn, the same shape again
    "decided_by_him": "the decision, taken by the manager himself",
    # fix 4 (ruling 3): closing step 3, or accepting the record at step 4, on a model turn
    "endorsed_by_him": "the step's answer, given by the manager himself",
    # t116: a step answer never settles an open referee question; his answer to it does
    "question_answered": "the open question, answered by the manager himself",
    # t134 (ADR-0030 decision 7): who he signs as, which nobody else in this product may decide.
    "signed_as_by_him": "who he signs as, chosen by the manager himself",
}


def wrong_call(error: str, **extra: Any) -> dict[str, Any]:
    return {"error": error, "refusal": WRONG_CALL, **extra}


def standing(say: str, next_: list[str], waits_on: str, hold: bool = True) -> dict[str, Any]:
    """A standing refusal: `say` is one plain sentence naming what is missing and the one thing that
    would change it, or that nothing in this walk will; `next` holds only moves a tool can make, and
    never the refused move. `error` carries `say` too, so every reader of tool errors still sees it.

    `hold=False` keeps it out of the conversation's refusal ledger (`Session.dispatch`), which
    otherwise gives the same refusal to every later call of that tool on that activity until what
    it waits on changes. A refusal that waits on an act of HIS, taken through the same tool, must
    not be held: the ledger would refuse his own tap (t80/t83).
    """
    assert waits_on in WAITS_ON, waits_on
    return {"error": say, "refusal": STANDING, "say": say, "next": list(next_),
            "waits_on": waits_on, "hold": hold,
            # t96: the taps as he reads them, where that differs, so the model names them to him
            **({"next_as_he_reads_them": [TAP_WORDS.get(x, x) for x in next_]}
               if any(x in TAP_WORDS for x in next_) else {})}


AFTER_SIGNING = ["Show the signed record", "Pick another activity"]
#: t134: the one question nemo asks before it writes a signature, where the record names an owner.
SIGN_AS_WHICH = ("Before I write it: are you signing as the owner yourself, or on behalf of "
                 "{owner}, whom the record holds as the owner? Take the one that is true — your "
                 "certificate will say which of the two you picked.")


# ── the taps: every one drawn by nemo from the room's data (13_nemo, t73) ──────────────────────
#: During a walk the model writes no tap. Each tap below is drawn from the run, the draft, the
#: manager's decisions and nemo's own cards, and stands for exactly one tool call whose arguments
#: are
#: fixed from that data; tapping it makes that call and nothing else (`Session._tap_turn`). The
#: model's OPTIONS line, if it writes one, is logged and dropped whole (M13: never filtered).
PICK_ANOTHER = AFTER_SIGNING[1]
CHANGE_SCOPE = "Change the scope"
ACCEPT_ALL = "Accept all open proposals"
ACK_GAP = "Acknowledge the recovery gap"
CHANGE_FIGURE = "Change the figure"
ACCEPT_HANDOVER = "Accept the handover"
GO_BACK = "Go back to step 3"
#: under a "Change …" question: leave it as it is (the pending change is cleared; nothing is called)
KEEP_AS_IS = "Keep it as it is"
#: t116: the referee's open question (an MTPD he asserted against the grid's) and its three
#: answers, nemo's fixed words with the room's figures. Each is `decide` on the question's own id
#: (`question_key`), with the answer as its decision: keep, the derivation, or left open (t83's
#: word). A step answer never settles it (the owner, TYPED, ce2e8d7b). Drafted; his to approve.
KEEP_ASSERTED_TAP = "Keep {asserted}, and say why"
WITHDRAW_ASSERTED_TAP = "Withdraw it: use the grid's {derived}"
LEAVE_OPEN_TAP = "Leave it open for the owners"
QUESTION_SAYS = ("A question on {activity} is still open: the MTPD stands at {asserted}, and the "
                 "grid derives {derived}. Closing the step does not answer it, so nothing has "
                 "changed. Tap one of its three answers first.")
QUESTION_HEADING = "**A question for you"
QUESTION_CARD = ("{heading} · {activity}**\n\nThe MTPD stands at {asserted}. The grid derives "
                 "{derived}, and the MTPD comes from the grid, so the check asks you to explain "
                 "{asserted} or withdraw it. Keep it and say why, withdraw it and use the grid's "
                 "{derived}, or leave it open for the owners: the record says which, and step 3 "
                 "closes once you have answered.")
ASK_KEEP_REASON = walk.ASK_KEEP_REASON  # t224: nemo's, so the door asks it in the same words
#: the value an acknowledged recovery gap is decided with (the referee's "said in as many words")
GAP = "RECOVERY GAP (acknowledged)"
#: t85: what a recovery gap the DRAFT proposes reads as, everywhere nemo says it. Two claims need
#: two spellings: `GAP` is the value an act of HIS records (t76), and the only one nemo calls
#: acknowledged; a gap nemo proposed to him is a proposal until he answers it. This one is SAID,
#: never stored — `GAP` stays the value a decision carries, so t75's box holds and no saved room
#: is rewritten. The source of truth is `recovery_gaps` (and, for a room decided before t76, his
#: own decision on the RTO); the spelling follows it, and never the other way round.
GAP_PROPOSED = "RECOVERY GAP (proposed)"
#: t76 (the owner's ruling, 2026-09-19): the one tap that can close an acknowledged gap. It asks
#: for his words and records the next line he types, as it is; nothing else closes a gap.
GAP_CLOSE_TAP = "The arrangements can now meet the target"
ASK_GAP_WORDS = ("Type, in your own words, how the arrangements now meet the recovery target for "
                 "{activity}. nemo records the line as you type it, and the recovery gap is closed "
                 "only then.")
#: what a "Change RTO" tap says while an acknowledged gap stands, so the label tells the truth (73b)
GAP_STAYS = " · the gap stays"
#: t154: a method with no rto_map derives no RTO for a recovery gap (13_nemo_check's t139 ruling
#: (1)), so the manager states it. The tap and the question nemo asks with it, in plain words;
#: step 3 does not close on a gap with no RTO, since the referee refuses a record that names none.
STATE_RTO = "State the RTO"
ASK_GAP_RTO = ("Type the RTO for {activity}: how long it may take to come back. The method sets no "
               "RTO of its own for a recovery gap, so the record needs yours.")
RTO_WANTED_SAYS = (
    "The recovery gap on {activity} leaves its RTO for you to state, and nemo's referee "
    "won't pass a BIA with no RTO, so step 3 stays open until you give it: tap "
    f"“{STATE_RTO}”."
)
#: t76: the third choice on every conflict card and its taps (the owner's ruling, 2026-09-19)
UNRESOLVED_TAP = "Leave unresolved: refer to the owners"

# ── AI proposes, you act (the owner, 2026-09-20T21:09:58Z; tickets 80, 83, 93) ─────────────────
#: The acts a model turn cannot perform, because each of them lands on the record he signs:
#: naming a figure into it (80), leaving a conflict open and so naming people on his certificate
#: as the owners it is referred to (83), and handing an RPO of his to the register's derivation
#: (93). Each is refused at the one function that writes (`Session.decide`), BEFORE anything is
#: applied, and each becomes a tap he takes. The gate rests on `Session._model_turn`, which nemo's
#: own code sets around `_model_calls` and which appears in no model JSON: the model cannot write
#: it. Nothing here reads the model's words.
#: t93: the decision that hands the RPO to the dependency register's derivation. It is his act, so
#: it is a decision like any other; the record then says the figure is the register's, not his.
DERIVED = "derived"


def confirm_figure_tap(kind: str, value: Any) -> str:
    """t80: the tap that records a figure named in chat, naming the figure from nemo's own stored
    proposal and never from the model's sentence."""
    return f"Record {str(kind).upper()} {value}"


def change_figure_tap(kind: str) -> str:
    """The "Change …" tap stage 3 already draws for that figure, so his two ways out of a figure
    named in chat are the two words he already knows (t63's vocabulary, no new one)."""
    return f"Change {str(kind).upper()}"


def keep_figure_tap(kind: str, value: Any) -> str:
    """t93: on a disagreement, the tap that keeps the figure he just set."""
    return f"Keep {str(kind).upper()} {value}"


def derived_figure_tap(kind: str, value: Any) -> str:
    """t93: on a disagreement, the tap that hands it to the register's derivation."""
    return f"Use the register's {str(kind).upper()} {value}"


#: t80: what nemo says when a figure is named in chat. Drafted by the build; the owner's to approve.
CHAT_FIGURE_SAYS = ("nemo records a figure only when you set it. {kind} {value} for {activity} was "
                    "named in chat, so it is not on the record. Tap “{confirm}” to record "
                    "it, or “{change}” to type your own.")
#: fix 3 (8_nemo_check's ruling of 2026-09-21, the owner's words of 2026-09-20T21:09:58Z applied
#: as written): on a model turn NO `decide` writes to his record, whatever the word and whatever
#: the item. Each becomes a tap for him. `what` is drawn from data — the tap nemo's card would
#: draw for that one call, which names what the record would carry — never from the model's words.
#: Drafted by the build; his to approve.
PROPOSED_SAYS = "nemo suggests: {what}. Tap to use it."
#: a conflict: the card's own side taps, the one the model proposed named first in the sentence
PROPOSED_SIDE_SAYS = "nemo suggests: {what}. Tap to use it, or pick another side."
#: a call nemo cannot name as one tap (a word no card uses): the card's taps
PROPOSED_ANY_SAYS = "nemo suggests a decision here. Tap one to make it."
#: fix 4 (8_nemo_check's ruling 4, 2026-09-21): each line says what happens to HIS figure, and a
#: conflict with no side is named. Every value is drawn from data: `what` from the card's tap,
#: `his` from his own decision on the item, `about` from the conflict's subject in the draft.
PROPOSED_OVER_HIS_SAYS = "nemo suggests {what} instead of your {his}. Tap to use it."
PROPOSED_REMOVE_HIS_SAYS = "nemo suggests removing the {name} you set ({his}). Tap to remove it."
PROPOSED_CONFLICT_SAYS = "nemo suggests a decision on {about}. Tap one to make it."
#: fix 3: the one line the MODEL reads in the tool result, on every `decide` its turn cannot make.
#: The manager never sees it (his screen shows `say`). Brought for 8_nemo_check's choice of wording.
PROPOSED_TOLD = (
    "Not recorded: nemo drew this for the manager as a tap (in next), and only his tap "
    "records it. When you speak to him about it, name that tap in one sentence, as in "
    "'tap “…” to use it', and leave the card as nemo printed it."
)
#: fix 3: what nemo says when the fidelity net finds a figure he set moved on a model turn.
FIGURE_KEPT_SAYS = ("nemo kept the figures you set for {activity}. Only you change a figure you "
                    "set, so nothing has changed on the record.")
#: t94: what nemo says when a model turn tries to accept every open proposal at once. The tap is
#: the stage-3 card's own batch label (`ACCEPT_ALL`), so no new tap reaches his screen. His to
#: approve.
ACCEPT_ALL_SAYS = (
    "nemo records what you accept. Accepting every open proposal at once is yours to "
    "do, so nothing has changed on the record. Tap \u201c{tap}\u201d and nemo records "
    "it, or ask nemo about any one of them first."
)
#: fix 4 (8_nemo_check's ruling 3, 2026-09-21): closing step 3 or accepting the record at step 4
#: is "a decision that lands on your signed record" (the owner, 2026-09-20T21:09:58Z), so a model
#: turn's plain endorsement becomes his tap: the card's own answer label. Drafted; his to approve.
#: t96 (ADR-0023 decision 9): the gradient's tap labels in plain words. Its four meanings stay, the
#: record stores the gradient value, and the tap's call is unchanged: only what he reads moves
#: (`Session.shown`). Drafted; his to approve.
TAP_WORDS = {walk.GRADIENT[0]: "Yes, agreed",
             walk.GRADIENT[1]: "Yes, with a reservation",
             walk.GRADIENT[2]: "Not yet, it needs discussion",
             walk.GRADIENT[3]: "No, it's blocked"}
#: t96 fix 1 (M7): nemo's stage-4 line (`walk.ACCEPTING`, nemo's own words) says what he did by the
#: plain word of the tap he took ("Yes, agreed"), from the same map; the record still stores
#: endorsed
ACCEPTING_ENDORSED = "out of what you " + walk.ENDORSED
ACCEPTING_AGREED = "out of what you " + TAP_WORDS[walk.ENDORSED].split(", ")[-1]


def by_his_tap(body: str) -> str:
    return body.replace(ACCEPTING_ENDORSED, ACCEPTING_AGREED)


#: t377c G2: what a model's endorsement of the scope gets back; the scope waits on his tap
SCOPE_IS_HIS = ("the scope for {activity} is not agreed: the manager agrees it with his tap "
                "“{tap}” on the card above, so tell him to tap it; nothing is agreed until he does")
#: t377k: what a model's confirm_interviews gets back; the interviews wait on his Keep or Drop tap
INTERVIEWS_ARE_HIS = ("the interviews for {activity} are not confirmed: the manager keeps or drops "
                      "them with his taps on the card above, so tell him to tap one; nothing is "
                      "confirmed until he does")
ENDORSE_SAYS = {
    3: "nemo suggests closing step 3 for {activity}. Tap “"
    + TAP_WORDS[walk.ENDORSED]
    + "” to close it.",
    4: "nemo suggests accepting the record for {activity}. Tap “"
    + TAP_WORDS[walk.ENDORSED]
    + "” to accept it.",
}
#: t83: what nemo says when a model turn tries to leave a conflict open. Drafted; his to approve.
#: fix 4 (ruling 4): review 4's one line, so it promises the one owner t84 names, not "people".
#: The tap label (`UNRESOLVED_TAP`) is his verbatim ruling and stays as it is.
CHAT_REFERRAL_SAYS = ("Leaving this open refers it to the activity's owner on the record you sign, "
                      "so it is yours to do. Tap “{tap}” and nemo records it.")
#: t93: what nemo asks when his figure and the register's derivation disagree. Drafted; his to
#: approve.
ASK_WHICH_CARRIES = ("You set {kind} {his}. The dependency register derives {derived} from "
                     "{reason}. Which does the record carry?")

# ── stage 3 as a grid and cards (14_nemo / t63) ───────────────────────────────────────────────
#: The skin draws them from the draft, the manager's decisions and the room's method, and prints
#: them as built: the model writes none of their content (M13); its line is the question under
#: them. t115: what a turn draws is `walk.prints`. The live card comes under the answer; the grid
#: and
#: the open decisions come only on the turn he taps "Show the grid" or "Show the open decisions",
#: each as one table. `get_evidence("grid")` is a read: the model gets the rows, nothing is printed.
GRID_HEADING = "**The impact grid"
#: t314: the impact chart, asked for in plain words in a typed line (his wow 3). A code trigger: the
#: words are fixed and read from his line alone, never from a reply, and nemo answers it itself with
#: 255's chart, drawn from the grids (M13). A line about the dependency graph or the process map is
#: not about this chart, nor (314b) an org, flow or Gantt chart, a network, process, supplier or
#: resource graph, what goes dark, or a plot of land. t433 (A3): anything over time, a line asking
#: to visualise, and a graph spelled with an f ("grafic") ask for it too.
CHART_WORDS = re.compile(r"\b(?:graph|chart|plot)s?\b|\bimpact over time\b|\bover time\b"
                         r"|\bvisuali[sz]\w*|\bgrafi[ck]s?\b", re.I)
#: t476 (replay row 24, "Visualise me the email draft"): an e-mail draft named is a message to
#: see, never a chart (`NOT_THIS_CHART`)
NAMED_DRAFT = r"\be-?m(?:ai|ia)l drafts?\b"
NOT_THIS_CHART = re.compile(
    r"\bdependenc|\bprocess(?:es)? (?:map|chart|graph|flow)|\borg\b|\borgani[sz]ation|\bflow ?chart"
    r"|\bgantt|\bnetwork|\bsuppl(?:y|ier)|\bresource|\bgo(?:es)? dark|\bland\b|" + NAMED_DRAFT,
    re.I)
#: t329: 259's meeting slides, asked for in his typed line in the same matcher (`asked_for`):
#: slides, a slide deck, a presentation or a PowerPoint, never a slide rule or the presentation
#: layer. nemo offers them as one tap that opens the room's own copy (`<root>/w/<code>/slides`).
SLIDES_WORDS = re.compile(r"\bslides\b|\bslide ?deck|\bpresentation\b|\bpower ?point\b", re.I)
NOT_THESE_SLIDES = re.compile(r"\bslide rule|\bpresentation layer", re.I)
SLIDES_TAP = "Slides for the BIA meeting"
#: t366: a message to write, asked for in his typed line, beside 329's matcher (`asks_to_write`):
#: a verb of writing or sending with an email, a mail, a message or a letter within one sentence,
#: the draft or drafts folder, "into my drafts", "email the …", and the same in German. The BIA's
#: own draft, a mail server or a dependency on e-mail is not a message to write. t433 (A8): nor
#: is any of these: writing to someone, an e-mail misspelt ("emial"), drafts to someone, and
#: drafts he asks to see or review.
#: t449 r2: what is written, the nouns WRITE_WORDS reads (and the write tap's own reading)
WRITTEN = r"\b(?:e-?m(?:ai|ia)ls?|mails?|messages?|letters?|nachricht(?:en)?)\b"
WRITE_WORDS = re.compile(
    r"\b(?:draft|write|send|compose|prepare|schreib\w*|schick\w*|entwirf)\b[^.?!]{0,40}?"
    + WRITTEN + "|" + NAMED_DRAFT +
    r"|\bdrafts? folder\b|\b(?:in|into) (?:my|your|the) drafts\b|\bentw[üu]rfe\b"
    r"|\be-?m(?:ai|ia)l (?:him|her|them|the|to|it)\b|\bwrite to\b|\bdrafts? to\b"
    r"|\b(?:show|see|review)\b[^.?!]{0,15}\bdrafts\b", re.I)
#: t433 (A8): a write ask addressed to the owners, the people responsible (however spelt) or them
TO_OWNERS = re.compile(r"\bowners?\b|\brespo\w*|\bto (?:them|each|every)\b", re.I)
#: t373 (ADR-0049): the questionnaire or the invitation, asked for in his typed line, beside 329's
#: and 366's matchers (`asks_to_invite`): nemo then draws "Invite to the interview" for the activity
#: whose re-interview the plan has on a day (`invitable`). The label is final for tonight (357).
#: t457 (B9-10): "the invite list" is a thing to check, not an ask to invite
INVITE_WORDS = re.compile(r"\bquestionnaires?\b|\binvit(?:e|es|ation|ations)\b(?! list)"
                          r"|\bcalendar\b|\bblock (?:the|some|that) time\b|\bfrageb[öo]gen|\beinlad"
                          r"|\bkalender", re.I)
#: t475 (his "clearly mark the suggested next steps as an 'E-Mail'"): the end of every tap's label
#: that drafts one, his word; spelt in two parts, as `WRITTEN` reads it, since step 43 bars the
#: word whole from the skin's strings (src/nemo/test_handover.py)
MAIL_MARK = " (E-" + "Mail)"
INVITE_TAP = "Invite to the interview" + MAIL_MARK
#: t406: under the drafts A8 shows first, the one tap that puts them all into the demo mailbox's
#: Drafts (his answer 2026-10-10T16:26:23Z: "Approve in chat, you show the mailbox"); never sent
PUT_DRAFTS_TAP = "Put these in Drafts" + MAIL_MARK
#: t430: where a draft goes, A8's words, said again under the write-pick (`WRITE_ASK`)
INTO_DRAFTS = "into the demo mailbox's Drafts; it never sends it."
#: t366: nemo's own line on that turn, drawn by code, first: where 317's step is drawn, and where
#: it is not (no finding to write about yet). What a draft says stays 317's.
DRAFT_FINDING = ("Yes, nemo can draft that: tap “{tap}” below and pick who it goes to. nemo puts "
                 f"the message about what this answer found {INTO_DRAFTS}")
DRAFT_NO_FINDING = ("nemo drafts a message to an owner about a finding, such as a change since "
                    "last year or a recovery time that does not fit, and puts it into the demo "
                    "mailbox's Drafts; it never sends it. This answer has no finding to write "
                    "about yet: “{tap}” comes under the answer that finds one.")
#: t366: what the model is told on that turn, in chat and in a walk alike: a supplement only (his
#: line is answered by code's own line), and a note, since the chat prompt is at its word cap (t96)
WRITE_NOTE = ("(nemo: he asked for a message to be written. nemo writes it: the “Write to an "
              f"owner{MAIL_MARK}” tap under an answer that found something puts it into the demo "
              "mailbox's Drafts, unsent, and nemo shows him a line saying so.)")
#: t366: a paragraph of the model's on that turn that names e-mail, mail or a draft (a denial or
#: an offer about them); a "can't" that names none of them stands (30_nemo_check's amend)
ABOUT_WRITING = re.compile(r"e-?mail|\bmail|\bdrafts?\b", re.I)
#: t449 r2: a model sentence on the write tap's tool when code draws its line: what 366 reads
#: (`ABOUT_WRITING`) or a written thing his write ask names (`WRITTEN`: a message, a letter)
WRITE_READS = re.compile(f"{ABOUT_WRITING.pattern}|{WRITTEN}", re.I)
#: t391: a paragraph of the model's that is a heading only: one line opening as a heading, bold or
#: a numbered item, with no sentence's end (run 6's A8: "**1. To Henning Barsch** (…)"); one that
#: ends the shown text has nothing under it and is dropped. 377 N6's trim refuses it too.
HEADING_ONLY = re.compile(r"\s*(?:#{1,6}\s|\*\*|\d+\.\s)[^\n]*[^.!?\s]\s*")
#: t391: a draft nemo shows first on his ask (`drafts_first`), never sent: its address line (how it
#: looks is 8_nemo_design's call), the mailbox draft's subject (`drafts.FOLLOW_UP_SUBJECT` is this)
#: and its question. t418 (ADR-0051): the function, never the name; the draft greets it by its
#: title (`DRAFT_DEAR`, his ANSWER 2026-10-10T19:50:31Z)
DRAFT_TO = "To the {function}"
DRAFT_DEAR = "Dear {function},"
DRAFT_SUBJECT = "Quick check: {about}"
DRAFT_ASK = "Could you tell me what has changed, and what we should plan with now?"
#: t476 (spec m15 S3, "Proper letter by code"): how every code-built draft closes (`letter`), the
#: sender the BCM Officer by function (`bcm_officer`); 16_marschkamp reads the words
LETTER_THANKS = "Thank you in advance for your input."
LETTER_REGARDS = "Kind regards,"
LETTER_SIGNED = "{function} (drafted with nemo)"
#: t476: the BCM Officer, as the organisation file names the function (`words.functions`)
BCM_FUNCTION = re.compile(r"\bBCM\b")
#: t418 (34_nemo_check 2026-10-10): a gap's topic in a subject, a short noun phrase drawn by code
#: from the gap's own sentence (391 r2: never a register row's bare name): the words it opens on, up
#: to its first verb, and where that is one word ("Westerkoog"), what the verb is about, up to its
#: first preposition or clause ("Westerkoog contract")
TOPIC_VERBS = ("is are was were has have had can cannot could will would must should need needs "
               "add adds go goes set sets cancel cancels run runs stand stands use uses take takes "
               "fall falls get gets make makes send sends plan plans stay stays change changes")
TOPIC_ENDS = re.compile(rf"\s(?:{'|'.join(TOPIC_VERBS.split())})\b")
#: t418: words between the verb and what it is about ("set up a", "is now"), skipped
TOPIC_SKIPS = frozenset("up down out back not now only also still a an the".split())
#: t418: where what the verb is about ends
TOPIC_STOPS = frozenset("at in on for to from with by if when and but of that which than so as "
                        "we our us".split())
#: t418 r3 (6_nemo_design_phone's 390 read): when a gap's sentence says it happens ("at night and
#: at weekends"), said once in a subject that names its resource (`topic`): "at night and weekends"
TOPIC_WHEN = re.compile(r"\b(at|on|during) (nights?|weekends?|the weekend|holidays)\b", re.I)
#: t377c G3: a paragraph that opens a letter: a header line (To, Cc, Subject), or a greeting
LETTER_OPENS = re.compile(r"\s*(?:\*\*)?(?:To|Cc|Bcc|Subject)(?:\*\*)?\s*:|\s*(?:Dear|Hello|Hi)\b",
                      re.I)
#: t476: a model reply holding a letter (`model_letter`): a header line or a "Dear" line; a "Hi"
#: or "Hello" line only as a letter's greeting (ending on a comma) in a reply about writing
LETTER_HEAD = re.compile(r"\s*(?:\*\*)?(?:To|Cc|Bcc|Subject)(?:\*\*)?\s*:|\s*Dear\b", re.I)
LETTER_HI = re.compile(r"\s*(?:Hello|Hi)\b[^\n.!?]*,\s*", re.I)
#: t367 (spec §13): chart A's one title, the line under it, and the key's words for each year;
#: t403: a line per impact class, no longer the worst of them
CHART_HEADING = ": impact over time, by class**"
CHART_TITLE = "**{activity}" + CHART_HEADING
CHART_UNDER = "The {count} impact classes over time, last year's faint behind"
#: 741 r2: the words of `CHART_UNDER` that `under_with_year` gives the record's year
CHART_FAINT = "last year's faint behind"
#: t741: how a line under a chart opens on a count, and on a count of one
CHART_MANY, CHART_ONE = "The {count} impact classes", "One impact class"
#: t741: the class a euro line speaks to (`EURO_SAID`), so a chart that leaves it out has none
FINANCIAL = "financial"
#: t517 (his TYPED 2026-10-19T05:45:03Z): the line under the title of a chart with no scores this
#: year, in place of `CHART_UNDER`, last year's lines then drawn strong. 49_nemo's amend on
#: 43_nemo_check's order 2026-10-19 11:06:01, in 15_nemo_design's final words: split by the
#: activity's Status cell in the programme plan (`no_scores_line`), its day read from the cell
CHART_NO_SCORES = "{activity}: no scores this year yet — only last year's record is drawn."
CHART_PLANNED = ("{activity}: no scores this year yet. Its re-interview is planned for {date}, so "
                 "only last year's record is drawn.")
CHART_CONFIRMED = ("{activity}: reviewed on {date} and confirmed unchanged, so only last year's "
                   "record is drawn.")
CHART_LAST_KEY = "Last record ({record}, {year})"
CHART_LAST_UNDATED = "Last year's record ({record})"
CHART_THIS_KEY = "This year's interview ({when})"
CHART_THIS_UNDATED = "This year's interview"
CHART_LATER = "The impact chart for {activity} comes at stage 3, once its impact grid is drafted."
#: t367 B: a chart line with no activity to draw. A tap per activity with a grid (in the process
#: map's order, `CHART_TAPS` at most), counted outside ADR-0045's cap as 329 rules
CHART_PER_ACTIVITY = "The impact chart is drawn per activity. Pick one:"
CHART_NONE = "The impact chart comes at stage 3, once an activity's impact grid is drafted."
CHART_TAP = "Chart: {activity}"
CHART_TAPS = 5
#: t485 (R6, 16_marschkamp's defined answer): a chart line naming a resource of the register and no
#: activity. The impact chart is drawn per activity, so nemo answers with the resource's dependency
#: view, drawn by code (`resource_view`): what needs it, what it stands on, its owner by function
#: (ADR-0051), and the room's graph page opened lit on it (`live_graph.html` reads `#chain=<box>`).
#: t488 (his D1): at most three plain lines, then `GRAPH_LINK`, as every dependency ask
RESOURCE_NEEDED = "{name} is needed by {n}: {names}."
RESOURCE_NONE = "No activity needs {name}."
RESOURCE_ON = "It stands on: {names}."
RESOURCE_OWNER = "Owner: {owner}."
#: r2 (40_nemo_check, 2026-10-14): a resource the page draws inside a box of another name (a
#: merged box, `merge_table`): the answer names the box, and the box's count is said as the box's.
#: t488 (13_nemo_design's look read): "part of" the box in plain words, never "drawn in" it
RESOURCE_IN_BOX = "{name} is part of the {box} box. That box is needed by {n}: {names}."
RESOURCE_IN_BOX_NONE = "{name} is part of the {box} box. No activity needs that box."
RESOURCE_BOX_ON = "That box stands on: {names}."
RESOURCE_OWNER_OF = "Owner of {name}: {owner}."
CHAIN_VIEW = "#chain="
#: t524: the page opened on the resources two activities share, and on what a cut reaches
SHARE_VIEW = "#share="
CUT_VIEW = "#cut="
RESOURCE_KIND = "resource"
#: t367: what `CHART_UNDER` calls the method's categories, by how many it has
COUNTS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def chart_under(line: str, count: int) -> str:
    """t741: a line under a chart (`CHART_UNDER`, `led_turn`'s two) for `count` classes: one is
    "One impact class", any other its number word in the line as it stands."""
    if count == 1:
        return line.replace(CHART_MANY, CHART_ONE)
    return line.format(count=COUNTS[count] if count < len(COUNTS) else count)


def under_with_year(line: str, folder: Path, activity: str) -> str:
    """741 r2 (his word, 'Last record (2024)'): a both-years line under a chart (`CHART_FAINT`) says
    what the chart's key says, by the year `activity`'s own record states; as it stands with none,
    and any other line as it stands."""
    if CHART_FAINT not in line:
        return line
    year = _year(str(last_year(folder, activity).get("interview") or ""))
    return line.replace(CHART_FAINT, f"{impact_chart.last_word(year)} faint behind") if year \
        else line


DECISION_HEADING = "**Open decision"
#: t377 D4: a typed question mid-walk points at the open decision the walk raised, never re-posts
#: it; a turn that asked the walk where it stands (`RAISES_CARD`) draws the card as 117 does
RAISES_CARD = frozenset({"get_step", "get_evidence", "open_activity", "list_activities"})
DECISION_POINTER = "The open decision above is still open: its taps are below."
SHOW_GRID = "Show the grid"
#: t115: the one tap the open decisions sit behind, in nemo's fixed words (it was "Show the other N
#: decisions", t77), and the heading of the one table it prints
SHOW_DECISIONS = "Show the open decisions"
OPEN_DECISIONS_HEADING = "**The open decisions"
#: a row, a figure or a side's pick that is nemo's proposal and not yet the manager's
PROPOSED_MARK = "(proposal)"
PROPOSAL_WORD = "nemo's proposal"
#: t79 (routed from t85): the reason under a proposal is usually the DRAFTING MODEL's own
#: sentence. nemo prints it word for word and never rewords it (M13), so the line says whose words
#: it is instead of leaving it to read as nemo's claim — the card's own way of attributing a side
#: ("The draft sums this side up: …"), said for the reason too.
#: t79 fix 1: per item, from the draft object's own `floor` mark, never a blanket line. Some of
#: those reasons are nemo's (`_wrote_it`), and a card that called them the draft's would be making
#: exactly the false attribution this ticket exists to remove. A bare "Why:" is nemo's own voice,
#: which is what every unattributed line on a card already is.
DRAFT_WORDS = "the draft's own words"
NEMO_WORDS = "nemo's own words"
#: t96 (the 91 sentence, his to approve): short enough to read nine times on one card, still on
#: every line it heads, and still saying whose reason it is (the draft's, never nemo's own "Why: ")
DRAFT_SAYS = "The draft's reason: "
WHY_SAYS = "Why: "
#: nemo's note about the model's sentence, on its own line under it and never inside it
CHECK_SAYS = "nemo's check: "
#: t377 G8: how the draft's own reason opens on an interview it dropped (its stored words, never
#: shown); stage 2 folds those rows into one line, NOT_ABOUT_IT, and draws them no tap (t528)
EXCLUDED = "EXCLUDED - "
NOT_ABOUT_IT = "Not about this activity ({n}): {names}"
MORE_TAP = "\u2026 {n} more"
MORE_SAID = "One drop tap for each interview not about this activity."
#: t313 (a): the tap that keeps the interviews the draft marks keep=true; t377 J: his typed analysis
#: ask at stage 2 takes that tap's own call, and nemo's line says what it kept, the tap's names.
#: t439 box 2 (his answer, 2026-10-12): the tap counts them; the card above it lists them
KEEP_THESE = "Keep these {n} interviews"
#: t446 (his answer, 2026-10-12T15:49:43Z): the same tap when it keeps one
KEEP_THIS = "Keep this interview"
KEPT_SAID = "I kept the {n} interviews nemo proposed ({names}). Stage 3 of 5."
#: t446 r2: the same line when it kept one
KEPT_ONE_SAID = "I kept the interview nemo proposed ({names}). Stage 3 of 5."


def excluded(item: dict[str, Any]) -> bool:
    """t377 G8: an interview the draft dropped, by its stored reason's first words."""
    return str(item.get("why") or "").startswith(EXCLUDED)


def kept_by_draft(offer: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """t313 (a), t528: the offered interviews the draft keeps: where it marks any keep=true (its
    field, never its prose: M13), all but those it marks keep=false; else the whole offer. The one
    source of stage 2's "Keep these <n>" tap and stage 1's count of who talks about it."""
    if not any(i.get("keep") is True for i in offer):
        return offer
    return [i for i in offer if i.get("keep") is not False]


def why_said(item: dict[str, Any]) -> str:
    """Which voice a card's `reason` or `why` is in: nemo's own where the draft object marks it
    nemo's, the drafting model's otherwise (t79 fix 1)."""
    return WHY_SAYS if item.get("floor") else DRAFT_SAYS


def check_lines(item: dict[str, Any]) -> list[str]:
    """nemo's own note about the model's sentence, on its own line under it (t79 fix 1). The one
    path every card takes to it, so a second one cannot drift away from this (fix 2, M7)."""
    note = str(item.get("check_note") or "").strip()
    return [CHECK_SAYS + note, ""] if note else []


def why_lines(item: dict[str, Any], key: str = "reason") -> list[str]:
    """A card's reason, said in the voice of whoever wrote it, and nemo's own note about it on its
    own line under it (t79 fix 1). Neither sentence is reworded."""
    out = []
    if str(item.get(key) or "").strip():
        out += [why_said(item) + item[key], ""]
    return out + check_lines(item)


def _reason_attributed(item: dict[str, Any]) -> dict[str, Any]:
    """t79: an open item handed back with the `reason` or `why` it carries said to be whoever
    wrote it — the drafting model's, or nemo's where the draft object marks it nemo's (fix 1).
    The sentence itself is untouched: nothing here rewords a model's words (M13)."""
    whose = {f"{k}_whose_words": NEMO_WORDS if item.get("floor") else DRAFT_WORDS
             for k in ("reason", "why") if str(item.get(k) or "").strip()}
    return {**item, **whose} if whose else item


#: the turns whose taps are stage 3's own, so its cards come with them
STAGE3_MODES = ("step", "grid", "as_is", "all")
#: t115: a show tap's kind, as `walk.prints` names what it prints, and the two taps that go under
#: the table it prints (117's amendment: the decision taps stay on the live card's message)
SHOWS = {"grid": "grid", "all": "decisions"}
SHOW_TAPS = (SHOW_GRID, SHOW_DECISIONS)

# ── guidance as served, and whose a figure is (14_nemo / t65) ─────────────────────────────────
def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


#: The label over a figure the room's own method file gives: fixed words the skin prints.
COMPANY_METHOD = "Your company's method"
#: t477 (D2, replay row 11 "what side?"): a conflict's side as its tap and nemo's proposal name
#: it: who said it and the figure taking it makes the record carry, never "side 1 / side 2"
SIDE_SAYS = "{who} says {figure}"
#: t482 r2 (477's label): a side whose figure is the method's reading of a person's impact grid
#: (its own claim names the method, its quote is an impact row), never a figure that person stated
SIDE_GRID = "{who}'s impact scores give {figure}"
#: t482 r2: a side as nemo's line on an open conflict says it, per side, never its tap pasted: the
#: figure ('>' said as words, `SAID_BOUNDS`), then whose it is
SIDE_SAID = "{figure} ({by})"
SAID_STATED = "the {function}"
SAID_GRID = "the {function}'s impact scores"
SAID_BOUNDS = {">": "more than ", "<": "less than "}


def unit_kept(figure: str) -> str:
    """t477 r2 (14_nemo_design's nit): `figure` with a no-break space between each number and the
    unit after it ("2 h"), so a wrap at 390 never parts them."""
    return re.sub(r"(?<=\d) (?=[^\W\d])", "\u00a0", figure)


#: t552 (site 1 of 549's split): the `_server_reply` kinds whose shown words are code's own and
#: so keep a number with its unit — the plan's due list (t377 D1) and the impact-chart card. A
#: kind carrying the model's words ("interview", the agent's answer) is left exactly as the model
#: wrote it (the kind exclusion); t549 r2 did `_finish`'s two sites the same way.
KEPT_UNIT_KINDS = ("due", "chart")


def card_key(card: str) -> str:
    """t552: the key `Session._charts` / `_phones` holds a card under — the string as composed,
    with ordinary spaces, while the card shown carries `unit_kept`'s no-break ones. A card of the
    plain form is its own key."""
    return card.replace("\u00a0", " ")


#: t477: what a side naming a recovery gap says, in its tap
GAP_SIDE = "a recovery gap"
#: t477: a side that names no figure, or a score row (its scores are on the card), by who said it
SIDE_VIEW = "{who} (no figure)"
#: t477: a side whose speaker the draft does not name
UNNAMED_SIDE = "A view on file"
#: t477: what taking a side does, under its entry on the card (its heading names who said it)
TAKING_SIDE = "Taking this side: {effect}."

#: t79, the owner's sentence on t64's glossary (2026-09-19): "Distinguish human-provided values,
#: deterministic calculations and AI proposals. AI4BCM permits checking recovery values but
#: prohibits AI setting them." Each `origin` the record carries, said in his words and counted on
#: its own: what people said in an interview and what he decided are both human-provided, and the
#: card already tells those two apart; what the method's own rules calculated is neither a person's
#: word nor nemo's proposal; and only `proposed` is nemo's, which he confirmed. The method is named
#: as the rest of the card names it (`COMPANY_METHOD`, fix 1 M1), so there is one spelling of it.
#: `blank`, `rejected` and `none` are counted under none of them: they name a row that sets no
#: figure. Fix 3 makes that a declaration rather than an observation — `NOT_COUNTED` below, and the
#: two sets together are `ORIGINS`, every origin there is. A `blank` row still keeps the model's own
#: scores (`effective`), so a row the draft left kind-none, the model scored and he accepted still
#: reaches the evidence with real scores and this origin; what changed is that it is now declared
#: not to be an authored figure instead of falling out of the count unnoticed.
#: t96 (the 91 sentence, his to approve): the same four kinds, said to be read once. "What people
#: said" for a person's own words; "accepted", the word on the tap he took for a proposal.
WHOSE_WORDS = (
    ("stated", "figure comes from what someone said", "figures come from what people said"),
    ("manager", "is your decision", "are your decisions"),
    (
        "method",
        f"is calculated by {_lower_first(COMPANY_METHOD)}",
        f"are calculated by {_lower_first(COMPANY_METHOD)}",
    ),
    ("proposed", "is my proposal you accepted", "are my proposals you accepted"),
)


#: t79 fix 3: the origins that name a row which SETS no figure, declared here rather than left to
#: be noticed. A rejected row, a row the draft left blank, a row nothing was drafted for: each is
#: evidence, none is a figure anyone authored, so no clause of the line counts one.
NOT_COUNTED = ("blank", "rejected", "none")
#: Every origin an evidence entry may carry, besides the two risk-register rows (`ROW_FLOOR`,
#: `ROW_KEPT`), which the same card counts in a clause of their own. **The invariant (7_nemo_check,
#: 2026-09-20, 23:38:34): the four counted origins and `NOT_COUNTED` partition this, so every
#: figure on the record is in exactly one of the four counts or declared not to be a figure, and
#: nothing is outside both.** A closed set at the boundary (`drafting.MODEL_MAY_PROPOSE_KIND`) stops
#: the MODEL inventing an origin; this stops NEMO'S OWN code adding one with no clause to count it,
#: which the boundary cannot catch because such a kind is legitimate.
ORIGINS = tuple(k for k, *_ in WHOSE_WORDS) + NOT_COUNTED


def uncounted(ev: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The evidence entries no clause of the record card's section 4 accounts for (t79 fix 3).

    The invariant is that this is always empty, and it is asserted in the suite — never rendered.
    A catch-all count on the card would be more accurate and **worse to read**, which is the drift
    the owner named in his tiebreak of 23:30:02 (easyness over jargon; fewer categories beat more).
    So a violation reds the suite; it never becomes a category he has to parse. And there is no
    runtime branch for the mismatch either: the boundary makes it unreachable from the model and
    this makes it unreachable from nemo, so a handler on the document he signs would be a handler
    for a state that cannot arise.
    """
    known = set(ORIGINS) | {ROW_FLOOR, ROW_KEPT}
    return [e for e in ev if e.get("origin") not in known]


def whose_words(ev: list[dict[str, Any]]) -> str:
    """The stage-4 card's fourth line: where the record's figures come from, kind by kind (t79),
    each count with the verb and the noun its number takes."""
    said = []
    for origin, one, many in WHOSE_WORDS:
        # t171: a figure resting on several rows (the register's row per system, his reason's
        # turn beside his figure's) is still one figure: counted by what it stands behind
        n = len({(e.get("label"), e.get(LENS)) if e.get("label") or e.get(LENS) else at
                 for at, e in enumerate(ev) if e.get("origin") == origin})
        said.append(f"{n} {one if n == 1 else many}")
    return ", ".join(said[:-1]) + ", and " + said[-1] + "."

#: The label over a guidance answer (t65b, ticket 78): the ai4bcm chat's three, character for
#: character from `ai4bcm-site/chat/render.py` (EYEBROW_ANSWERED*, `_answered_eyebrow`). nemo
#: picks one from where each served link comes from, never from the model's words: an outside
#: source is never called AI4BCM Guidance, and the release tag is the Guidance's alone.
ANSWERED_GUIDANCE = "Answered from AI4BCM Guidance"
ANSWERED_BOTH = "Answered from AI4BCM Guidance and the literature"
ANSWERED_LITERATURE = "Answered from the literature"
#: what the model is told about the block ask_guidance printed
GUIDANCE_SAY_IT = (
    "nemo prints this to the manager word for word, links included, labelled by where its "
    "links come from: the AI4BCM Guidance, the literature, or both. Do not restate it, "
    "paraphrase it or print its links; add at most one sentence of your own, which in a "
    "walk brings him back to the step."
)  # t96: free chat has no step to go back to

def source_line(index: int, cite: dict[str, str]) -> str:
    """One numbered source as the ai4bcm chat renders it (`ai4bcm-site/chat/render.py`,
    `source_line`): the section title as the link text, backticks stripped, then the unit."""
    title = str(cite.get("title") or cite.get("unit") or "").replace("`", "").strip()
    url = str(cite.get("url") or "").strip()
    unit = str(cite.get("unit") or "").strip()
    named = f"[{title}]({url})" if url and title else (title or url or "—")
    return f"{index}. {named}" + (f" — *{unit}*" if unit else "")


def guidance_label(cited: list[dict[str, str]]) -> str:
    """The chat's label for these citations, read off each one's `source` (the served chunk's)."""
    ours = [c for c in cited if c["source"] == GUIDELINE]
    if not ours:
        return ANSWERED_LITERATURE
    label = ANSWERED_GUIDANCE if len(ours) == len(cited) else ANSWERED_BOTH
    return label + (f" · Release {ours[0]['release']}" if ours[0]["release"] else "")


def guidance_block(text: str, cited: list[dict[str, str]]) -> str:
    """The ask lane's answer as served: under the chat's label with its numbered links, or, with
    no citation (one of the lane's refusals), its words alone."""
    if not cited:
        return text
    # t96: the answer first, then a small source line with its numbered links
    return "\n\n".join([text, f"*{guidance_label(cited)}*\n"
                         + "\n".join(source_line(n, c) for n, c in enumerate(cited, start=1))])


def last_sentence(text: str) -> str:
    """What the model may add beside a guidance answer: its last sentence (structural; no word in
    it is read), the one that hands him back to the step. t435: never inside a quotation."""
    parts = [p for p in _sentences(text.strip(), r"|\n+") if p.strip()]
    return parts[-1].strip() if parts else ""
#: A whole line that starts with the marker (t73 fix 1): dropped with everything on it. The word
#: in the middle of a sentence ("You have two OPTIONS: keep 4 h or accept the gap.") is prose and
#: stays, since cutting there would cut his sentence, not a tap list.
_OPTIONS_LINE = re.compile(r"^[ \t*_]*OPTIONS[*_]*[ \t]*:[*_]*[ \t]*(.*)$\n?", re.M)


def _drop_options(text: str) -> tuple[str, list[str]]:
    """(the text without any OPTIONS line, what those lines offered). Nothing in them is
    rendered."""
    offered = [
        o.strip() for m in _OPTIONS_LINE.finditer(text) for o in m.group(1).split("|") if o.strip()
    ]
    return _OPTIONS_LINE.sub("", text).strip(), offered


def tool_tap(tool: str, **args: Any) -> dict[str, Any]:
    """A tap that makes one tool call, its arguments fixed here from data."""
    return {"kind": "tool", "tool": tool, "args": args}


def ask_tap(tool: str, args: dict[str, Any], field: str, prompt: str,
            horizons: list[str] | None = None) -> dict[str, Any]:
    """A "Change …" tap: nemo asks for the one thing only the manager can give (a figure, scores,
    a scope list), and his next typed line is that argument of exactly one call. Like 72's
    "Another activity…", the line is taken whole, never read for meaning; scores and a scope list
    are
    split structurally (digits 1–5 in horizon order; `;` or a new line)."""
    return {"kind": "ask", "tool": tool, "args": args, "field": field, "prompt": prompt,
            **({"horizons": horizons} if horizons else {})}


def tap_id(action: dict[str, Any]) -> str:
    """The action id a tap's payload carries (the skin sends it back; `Session.turn(action=…)`)."""
    import hashlib
    return hashlib.sha1(json.dumps(action, sort_keys=True, ensure_ascii=False,
                                   default=str).encode()).hexdigest()[:12]


def _unique(pairs: list[tuple[str, dict[str, Any], str]]) -> list[tuple[str, dict[str, Any]]]:
    """(label, action) with every label unique: a label drawn twice gets its own qualifier."""
    seen: dict[str, int] = {}
    for label, _, _ in pairs:
        seen[label] = seen.get(label, 0) + 1
    return [(f"{label} · {qualifier}" if seen[label] > 1 else label, action)
            for label, action, qualifier in pairs]


def ordered_open(state: dict[str, Any]) -> list[dict[str, Any]]:
    """The open items in nemo's order, the live one first (`walk.live_first`, t63's order moved
    into nemo by t117), the draft's order within each kind. The taps, the live card, the
    open-decisions table and every lookup the model reads take this order and no other (t117: his
    walk was served C1 first and his tap recorded C2)."""
    return walk.live_first(open_items(state))


def served_live(open_: list[dict[str, Any]], kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """t117: the items a lookup serves, in nemo's order, the live one (`open_[0]`) marked
    `"live": true` where it is among them. No other item carries the mark."""
    live = open_[0]["id"] if open_ else None
    return [{**i, "live": True} if i["id"] == live else i for i in kept]


def _who(speaker: str) -> str:
    """A side's speaker as a tap names them: the name before any bracketed note."""
    return str(speaker or "").split("(")[0].strip()


def _quoted(quote: Any) -> list[str]:
    """An interviewee's words as a quote block, line by line, as they stand (t63): each line ends
    in a hard break (markdown would join them), and a blank line closes the block (a line after it
    would run into the quote). [] when there are no words."""
    said = [
        f"> {_as_words(line.strip())}" for line in str(quote or "").splitlines() if line.strip()
    ]
    return [line + "  " for line in said[:-1]] + said[-1:] + [""] if said else []


def _as_words(line: str) -> str:
    """t63 fix 1 (b): a line of someone's words, escaped so markdown shows it as the words and never
    as a heading, a list, a rule or a table (a drafted quote can be a heading or a table row). Only
    backslashes are added; the words are unchanged. Inline emphasis stays, as the file has it."""
    line = line.replace("\\", "\\\\").replace("|", "\\|")
    line = re.sub(r"^(#+|[-+*=>]|\d+(?=[.)]))", lambda m: "".join("\\" + c for c in m.group(1))
                  if not m.group(1).isdigit() else m.group(1) + "\\", line)
    return line


#: t96: how a side whose speaker names no person is labelled on its tap
NOTES_SIDE = "From the notes"


def _names_a_person(who: str) -> bool:
    """Whether a speaker names someone: a first and last name somewhere in it."""
    return re.search(r"[A-ZÄÖÜ][\w.-]+ [A-ZÄÖÜ][\w.-]+", who) is not None


def _surname(who: str) -> str:
    """t64: a person as a phone-length tap names them: the last word of a person's name ("Dohm").
    A speaker that is no plain first-and-last name ("Anja Brockmann's team") stays as it is."""
    return (
        who.split()[-1] if re.fullmatch(r"[A-ZÄÖÜ][\w.-]+(?: [A-ZÄÖÜ][\w.-]+){1,2}", who) else who
    )


#: t64: why the record carries another figure than proposed, in the few words a tap has room for
_WHY_SHORT = {"derived from the register": "from the register",
              "the method's rule over the grid": "by the method's rule",
              "as the record will carry it": "as recorded"}


def _date_of(path: str) -> str:
    """An interview's date from its file name (yy_mm_dd_…), as "3 Aug"; "" when it carries none."""
    m = re.match(r"^(\d\d)_(\d\d)_(\d\d)_", Path(path).name)
    if not m or not 1 <= int(m.group(2)) <= 12:
        return ""
    return f"{int(m.group(3))} {time.strftime('%b', time.strptime(m.group(2), '%m'))}"


def _own_interview(folder: Path, path: str) -> str:
    """A transcript's text, "" unless it is one of the room's own. The path can come from the
    model's draft, so only the room's own 07_Interviews is read (27_nemo_check, ADR-0003)."""
    target = (folder / path).resolve()
    own = target.parent == (folder / "07_Interviews").resolve() and target.is_file()
    return interview_text(target) if own else ""


def _interviewee(folder: Path, path: str) -> str:
    """t313: the person a transcript's front matter names (`interviewee:`); "" when none does."""
    front = _own_interview(folder, path).partition("\n---")[0]
    m = re.search(r"^interviewee:[ \t]*(.*?)[ \t]*$", front, re.M)
    return m.group(1) if m else ""


def _subject(folder: Path, path: str) -> str:
    """347: what an interview is about, its own `# ` title less " BIA interview" or ": <year>
    re-interview" (the process map's name, word for word: 9_marschkamp's rule); "" when untitled."""
    m = re.search(r"^# (.+?)[ \t]*$", _own_interview(folder, path), re.M)
    return re.sub(r"(?: BIA interview|: \d{4} re-interview)$", "", m.group(1)) if m else ""


def _interview_who(folder: Path, i: dict[str, Any]) -> str:
    """t64: an interview as a phone-length tap names it, by its interviewee's surname. t313: a
    transcript the draft never read has no speaker; its front matter names the person, and a label
    never shows the file's name. t418 (ADR-0051): by the interviewee's function where the
    organisation file gives one (`words.people`), never the name."""
    who = _who(i.get("speaker") or _interviewee(folder, i["path"]))
    return words.people(folder).get(re.sub(r"^(?:Dr|Prof)\.? ", "", who)) or _surname(who) \
        or " · ".join(filter(None, ["this interview", _date_of(i["path"])]))


def interview_labels(folder: Path, items: list[dict[str, Any]]) -> list[str]:
    """Each interview of a list as its taps name it, every label distinct: the interviewee (t64),
    with the date where two share a name, and with the interview's subject where they share the
    date too (347: "Barsch · 25 Sep · Order picking"); a label that still collides takes its place
    in the list."""
    paths = [i["path"] for i in items]
    labels = [_interview_who(folder, i) for i in items]
    for qualifier in (_date_of, lambda p: _subject(folder, p), lambda p: ""):
        labels = [f"{label} · {qualifier(p) or n}" if labels.count(label) > 1 else label
                  for n, (label, p) in enumerate(zip(labels, paths, strict=True), 1)]
    return labels


def _implied_row(draft: dict[str, Any], implied: dict[str, Any]) -> dict[str, int] | None:
    """A side implying a score row (`<activity id>.<category id>`, PROTOTYPE_draft's prompt): the
    row its value holds, as the JSON object the prompt asks for, one score 1–5 for each of that
    row's horizons (t73b fix 1). None when the value is no such row, so nothing moves."""
    aid, _, lens = str(implied.get("item_id") or "").partition(".")
    act = next((a for a in draft.get("activities") or [] if a.get("id") == aid), None)
    row = (act or {}).get("grid", {}).get(lens)
    if not row:
        return None
    try:
        value = json.loads(str(implied.get("value")))
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != set(row.get("scores") or {}) or not all(
            isinstance(v, int) and 1 <= v <= 5 for v in value.values()):
        return None
    return value


def _why(field: str, meta: dict[str, Any]) -> str:
    """Why the record carries another figure than the one proposed, from the statement's origin."""
    origin = (meta.get(field) or {}).get("origin")
    if field == "RPO" and origin == "method":
        return "derived from the register"
    if field == "MTPD" and origin == "method":
        return "the method's rule over the grid"
    return "as the record will carry it"


# ── the room-state sheet: the room's state, read off its files on every ask (ticket 68) ─────────
#: The model is not the author of room facts (M2, M10; M13 forbids a check on its sentences
#: instead). The sheet is built from the run files, the record file, the prepared drafts and the
#: manager's decisions, never from the conversation, and the skin prints it as it is.
#: Wording rule: a line that names no activity carries no state word (record, signed, accepted…),
#: so every state claim on the sheet sits on its own activity's line.
PROPOSED, ACCEPTED = "proposed", "accepted"
FIGURES = (("MTPD", "mtpd"), ("RTO", "recovery_target"), ("RPO", "rpo"))


def _figures_of(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    by = {e.get("label"): e.get("value") for e in evidence or []}
    return {label: by.get(label) or None for label, _ in FIGURES}


def _says_no_rpo(evidence: list[dict[str, Any]]) -> bool:
    """Whether a run's or a proposal's evidence states no RPO (190): an RPO statement without a
    figure, which only the no-data derivation writes; a figure nobody could derive has none."""
    return any(e.get("label") == "RPO" and not e.get("value") for e in evidence or [])


def _proposed(folder: Path, activity: str, model: str) -> dict[str, Any]:
    """The figures the record will carry, with every open proposal accepted as proposed: read off
    the record's own path (`Session._all_accepted`, `build_proposal`), from the settled draft once
    stage 2 is confirmed, else from the prepared draft at the agreed scope with the interviews it
    offers (t71: the pick card said Slaughter's draft RPO "n/a (physical)", the record carried the
    register's 4 h). `why`: where a figure is not the draft's, why, from the statement's origin."""
    state = load_state(folder, activity)
    method = json.loads((folder / walk.METHOD).read_text())
    if not state.get("draft"):
        draft = draft_for(activity, model, folder)
        if not draft:  # t72: an added activity being drafted holds no figure yet
            return {label: None for label, _ in FIGURES}
        scope = state.get("scope") or scope_from_files(folder, activity)
        state = {"draft": collapse_to_scope(draft, scope["activities"]),
                 "interviews": [i["path"] for i in draft.get("interviews") or [] if i.get("path")]}
    acts = Session(folder, model, lambda *a: None)._all_accepted(state, method)["activities"]
    if not acts:
        return {}
    out: dict[str, Any] = _figures_of(acts[0]["evidence"])
    if _says_no_rpo(acts[0]["evidence"]):
        out[NO_RPO] = True  # 190: read by `room_sheet`, never a figure
    meta = {m["label"]: m for m in acts[0]["evidence_meta"]}
    first = (state["draft"].get("activities") or [{}])[0]
    decided = state.get("decisions") or {}
    for label, key in (("MTPD", "mtpd"), ("RTO", "rto"), ("RPO", "rpo")):
        was = (first.get(key) or {}).get("value")
        if out.get(label) and was and str(was) != str(out[label]) and "gap" not in str(was).lower():
            origin = (meta.get(label) or {}).get("origin")
            why = _why(label, meta) if origin == "method" else \
                "your decision" if f"{first.get('id')}.{key}" in decided else \
                "the side recommended on a conflict" if origin == "manager" else _why(label, meta)
            out.setdefault("why", {})[label] = f"{why}; the draft said {was}"
    return out


#: t309: what a room's files give, as last built: keyed on the room's resolved path, the model and
#: what it is, with the stamp of the files it was built from. A turn asked for the sheet three times
#: (the tool, the taps, the referee), and fifty rooms at once queued those builds behind one
#: process (100's load run).
Stamp = tuple[tuple[str, int, int, int], ...]
_KEPT: dict[tuple[Path, str, str], tuple[Stamp, Any]] = {}


def _stamp(folder: Path) -> Stamp:
    """t309: every file a sheet can read, as (path, inode, mtime, size): the room's own and the
    shared drafts. A file added, rewritten or removed changes it, so the next call sees it (284).
    The two files every turn writes are left out, because no sheet reads them: the turn file, and
    his said log (read by `answer_step` and `sign` alone)."""
    out, said = [], str(folder / SAID)
    for place in (folder, DRAFTS, FIXTURES):
        for root, dirs, files in os.walk(place):
            if root == str(place):
                dirs[:] = [d for d in dirs if d != turn_file.DIR]
            for name in files:
                with contextlib.suppress(FileNotFoundError):
                    if (path := os.path.join(root, name)) != said:
                        st = os.stat(path)
                        out.append((path, st.st_ino, st.st_mtime_ns, st.st_size))
    return tuple(sorted(out))


#: t309 part 2: one build at a time in this process. Fifty rooms' first builds at once shared one
#: interpreter's CPU and all finished together (~55 s on the stubbed bench); one at a time, the
#: first is served after one build. Re-entrant, so a build that asks for a kept value on its own
#: thread never waits on itself. A build takes no other lock and calls no lane
#: (`test_a_build_takes_no_room_lock_and_calls_no_lane`), so the turn path's locks, all taken
#: before it, can never wait in a circle with it.
_BUILDING = threading.RLock()


def kept[T](folder: Path, model: str, what: str, build: Callable[[], T]) -> T:
    """t309: `build()`, kept per room until the room's files change. The stamp is taken before the
    build, so a file landing during it makes the next call build again. Never another room's: the
    key is this room's own path. A copy, so no caller changes the kept one. A kept value is served
    at once; a build waits for any other build, then serves what that one kept if it is this room's
    at this stamp (part 2)."""
    key, stamp = (folder.resolve(), model, what), _stamp(folder)
    held = _KEPT.get(key)
    if held is None or held[0] != stamp:
        with _BUILDING:
            held = _KEPT.get(key)
            if held is None or held[0] != stamp:
                held = _KEPT[key] = (stamp, build())
    return cast(T, copy.deepcopy(held[1]))


def room_sheet(folder: Path, model: str) -> list[dict[str, Any]]:
    """`_built_sheet`, kept per room until the room's files change (t309)."""
    return kept(folder, model, "sheet", lambda: _built_sheet(folder, model))


def _built_sheet(folder: Path, model: str) -> list[dict[str, Any]]:
    """One row per activity the room holds, in the room's order and spelling, from files only.

    A record is accepted when the record file is this activity's, or when its run has answered
    step 4 (the run's status never says so; HANDOVER, Traps). A figure is `accepted` when it comes
    from that record, `proposed` when it comes from the draft, and None when neither holds one."""
    rows = []
    for name in walk.processes(folder):
        record = walk.read_record(folder, walk.record_file(name)) or {}  # type: ignore[attr-defined]  # t235: one per activity; walk re-exports read_record
        draft = draft_for(name, model, folder)
        why = ["no prepared draft"] if draft is None else drafting.walkable(draft, folder)
        # t72: an added activity is never locked out. With no draft, or one that is not walkable
        # yet, it is being drafted and stays pickable: stages 1 and 2 need no draft, stage 2 holds
        # its interview, and the draft is rebuilt from the room once that is filed (fix round 1).
        drafting_now = bool(why) and is_added(folder, name)
        if drafting_now:
            why = []
        run = walk.read_record(folder, walk.run_file(name)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        answered = int(run.get("stage") or 0)
        mine = str(record.get("dept", "")).lower() == name.lower()
        accepted = mine or answered >= walk.STAGE_4
        if mine:
            a = (record.get("activities") or [{}])[0]
            figures, mark = {label: a.get(key) or None for label, key in FIGURES}, ACCEPTED
            none = no_rpo(a)
        elif accepted:
            ev = ((run.get("activities") or [{}])[0]).get("evidence")
            figures, mark, none = _figures_of(ev), ACCEPTED, _says_no_rpo(ev)
        else:
            figures, mark = _proposed(folder, name, model), PROPOSED
            none = bool(figures.pop(NO_RPO, False))
        # Reopened (fix 1, M1): the record file is still this activity's, but the run is back
        # below step 4. The record's figures stay accepted; the settled draft's current ones are
        # shown beside them as proposed, both read from files.
        reopened = mine and answered < walk.STAGE_4 and run.get("status") != walk.CLOSED
        now = _proposed(folder, name, model) if reopened else {}
        whys, _ = figures.pop("why", None) or {}, now.pop("why", None)
        now.pop(NO_RPO, None)
        rows.append({"activity": name, "walkable": not why, "why_not": why,
                     **({"being_drafted": True} if drafting_now else {}),
                     "started": bool(run), "step": answered + 1, "record": accepted,
                     "signed": run.get("status") == walk.CLOSED, "reopened": reopened,
                     "figures": {k: {"value": v, "mark": mark if v else None,
                                     **({"why": whys[k]} if k in whys else {}),
                                     # 190: no dependency holds data, so the method gives no RPO
                                     **({"no_rpo": True} if k == "RPO" and none and not v else {}),
                                     **({"now": now.get(k)} if reopened else {})}
                                 for k, v in figures.items()}})
    return rows


def by_mtpd(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The comparison "which is most critical" gets: by MTPD, the method's measure of how soon an
    activity becomes intolerable. Tightest first; equal MTPDs share a place (a tie); an activity
    with no MTPD is "not known yet". It never picks: the manager does (owner)."""
    known: list[tuple[Any, ...]]
    unknown: list[tuple[Any, ...]]
    known, unknown = [], []
    for r in rows:
        f = r["figures"]["MTPD"]
        minutes = duration.minutes(str(f["value"])) if f["value"] else None
        (unknown if minutes is None else known).append((minutes, r["activity"], f))
    places: list[list[dict[str, Any]]]
    places, last = [], None
    for minutes, name, f in sorted(known, key=lambda x: x[0]):
        if minutes != last:
            places.append([])
            last = minutes
        places[-1].append({"activity": name, "mtpd": f["value"], "mark": f["mark"]})
    return {"measure": "MTPD", "places": places, "not_known_yet": [n for _, n, _ in unknown]}


PICK_HEADING = "Pick an activity"
#: t108: the work tap under a free-chat answer, nemo's words. The activity is `nemo.next_step`'s;
#: the tap is the pick route's (`tool_tap("get_step")`), his pick. ADR-0045 (t276): person-first
#: and short. t516 r2 (15_nemo_design's ruling): "Start the BIA for order picking", or "Open the
#: BIA for order picking" once its run is signed, wherever the tap may not say "its"
NEXT_STEP = "Start the BIA for {activity}"
NEXT_STEP_SIGNED = "Open the BIA for {activity}"
#: t516 (his 2026-10-19): on a card that already names the activity, the tap says "its" for it;
#: one pair for 252's, 475's and 478's start taps alike. r2: only where code's words name it alone
NEXT_STEP_ITS = "Start its BIA"
NEXT_STEP_SIGNED_ITS = "Open its BIA"
#: ADR-0045 (t276): the standing move, drawn only when the answer touched nothing real. t636 (his
#: "Dependency graph", 2026-10-30): the room's dependency graph (`standing_tap`), no longer the
#: process map's page, which went. t475 (S1): "Start a BIA" is never that fallback; it is drawn on
#: his explicit ask only (`START_ASKED`), and later in 478's stage map
START_BIA = "Start a BIA"
START_ASKED = re.compile(r"\bstart\w*\b[^.?!]{0,20}\bBIAs?\b", re.I)
DEPENDENCY_GRAPH_TAP = "Dependency graph"
#: t276: a page tap's press, no model call: the page's workspace link (`<root>/w/<code>/<page>`)
PAGE_SAID = "Here it is: [{label}]({link})"
#: ADR-0045: at most two next steps of one kind (kind 1's gaps), five in all
EACH_KIND = 2
NEXT_STEPS = 5
#: ADR-0045 kind 3 (t277): what nemo can produce, each drawn only where its data exists in the
#: room: 257's drafts, 260's re-interview sheet, the dependency graph stage 4 drew
DRAFTS_TAP = "Drafts to mailbox"
LAST_YEAR_TAP = "Last year's record"
CHAIN_TAP = "Dependency chain"
#: t277: the grouped graph's page, as the workspace serves it (`workspace.GRAPH`)
GRAPH_PAGE = "public/graph-v1/marschkamp/index.html"
#: t292: the current graph page's route in the room's workspace (`<root>/w/<code>/graph-live`);
#: t422 (his "Current graph", 2026-10-11T07:23:46Z): the chain's tap opens it, never the grouped one
LIVE_GRAPH = "graph-live"


def _said_name(folder: Path, activity: str) -> str:
    """252b: the activity as the process map names it, never its slug, mid-sentence: "Goods
    dispatch and delivery" reads "goods dispatch and delivery"; an acronym ("HR service ticketing",
    "IT helpdesk and support") keeps its capitals. A process the map does not list reads as its
    own words, hyphens as spaces (map_name, 255b's helper: one rule, one place)."""
    name = map_name(folder, activity)
    return name if name[1:2].isupper() else name[:1].lower() + name[1:]


def next_step_label(folder: Path, activity: str, card: str = "", said: str = "") -> str:
    """t252: the next-step tap's words, read from the activity's own run: open when signed. t516
    r2: "Start its BIA" ("Open its BIA") only where code's words on the card (`card`) name the
    activity and no other (`named_in`, 252's whole-name rule) and the model's (`said`) name no
    other; else "Start the BIA for <activity>". The model's words alone never make it "its": a
    later pass may drop them."""
    run = walk.read_record(folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
    signed = run.get("status") == walk.CLOSED
    if named_in(folder, card) == [activity] and set(named_in(folder, said)) <= {activity}:
        return NEXT_STEP_SIGNED_ITS if signed else NEXT_STEP_ITS
    return (NEXT_STEP_SIGNED if signed else NEXT_STEP).format(activity=_said_name(folder, activity))


def page_tap(page: str) -> dict[str, Any]:
    """t276: a tap that opens one page the workspace already serves (`workspace._drawn_page`)."""
    return {"kind": "page", "page": page}


def graph_drawn(folder: Path) -> bool:
    """The room has drawn its graph: a regular file, reached through no link on the way."""
    page = folder / GRAPH_PAGE
    return page.is_file() and page.resolve() == folder.resolve() / GRAPH_PAGE


def draw_graph(folder: Path) -> None:
    """t282 (the check seat's correction): the room's grouped graph from its register alone, drawn
    by a turn that offers the chain where stage 4 has drawn none (`PROTOTYPE_v1graph.draw`, as
    stage 4 draws it). Never on a GET, and never through a link: every folder on the page's path is
    a real folder of the room's, or not there yet."""
    path = folder
    for part in GRAPH_PAGE.split("/"):
        path = path / part
        if path.is_symlink() or path.exists() and not path.is_dir():
            return
    import PROTOTYPE_v1graph  # the graph's own module, imported where stage 4 imports it

    PROTOTYPE_v1graph.draw(folder, record={"activities": []})


def standing_tap(folder: Path) -> list[tuple[str, dict[str, Any]]]:
    """t636: ADR-0045's standing move, the room's dependency graph page (`LIVE_GRAPH`); its graph
    is drawn on the tap's press, never on the answer that offers it (r3: t282, t309). None where
    the register does not read, or is not the record the graph draws from (`draw_graph` raised
    AttributeError on "[]"): the page draws from it and would answer 404 (t299), and a turn never
    fails on its next step."""
    try:
        if not isinstance(json.loads((folder / REGISTER).read_text(encoding="utf-8")), dict):
            return []
    except (OSError, ValueError):
        return []
    return [(DEPENDENCY_GRAPH_TAP, page_tap(LIVE_GRAPH))]


def draw_on_press(folder: Path) -> None:
    """t636 example 2: the dependency graph tap draws the room's graph first where none is drawn
    yet, as 282's chain tap draws it; a press never fails on a register that does not draw."""
    if graph_drawn(folder):
        return
    try:
        draw_graph(folder)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass


#: t662: a page 636 took out of the workspace, by what replaced it; a tap an old room stored for it
#: names no process, so it opens the room's dependency graph whole (636's standing tap)
GONE_PAGES = {"process-map": LIVE_GRAPH}
#: t662 example 3: such a tap pressed where the room has no graph to open
PAGE_GONE = "That page is gone, and this room has no dependency graph to open yet."


def current_tap(folder: Path, action: dict[str, Any]) -> dict[str, Any] | None:
    """t662: a tap as it is drawn and pressed now. A page tap on a page that went (`GONE_PAGES`)
    opens what replaced it, or is None where the room has none to open (`standing_tap`: the page
    would answer 404). Every other tap as it is."""
    if action.get("kind") != "page" or action.get("page") not in GONE_PAGES:
        return action
    return page_tap(GONE_PAGES[action["page"]]) if standing_tap(folder) else None


def in_register(folder: Path, activity: str) -> bool:
    """t277: a row of the dependency register names this activity as a consumer, so the graph
    draws its chain."""
    register = drafting.read_register(folder)
    return any(row.get("department") == activity for asset in register.values()
               if isinstance(asset, dict) for row in asset.get("consumers") or [])


def walk_started(folder: Path) -> bool:
    """t276: whether any walk in the room has an answer of his on its run, by 151's rule
    (`greeting`): a run with no decision is not under way. A minted room holds a run for every
    activity at stage 1 with no decision, so a run file alone says nothing. A signed walk counts.
    """
    return any((walk.read_record(folder, walk.run_file(a)) or {}).get(walk.DECISIONS)  # type: ignore[attr-defined]  # walk re-exports read_record and DECISIONS
               for a in walk.processes(folder))


#: t256: the items of a register row a referral may name, as he reads them. The model names one by
#: its key; the words are nemo's.
REFER_RESOURCE_ITEMS = {"rto": "RTO", "rpo": "RPO", "consumer_mtpd": "MTPD",
                        "workaround": "workaround", "need": "need",
                        "confidentiality": "confidentiality", "integrity": "integrity",
                        "authenticity": "authenticity", "staff_normal": "staff in normal operation",
                        "staff_emergency": "staff in an emergency",
                        "provided_within": "provided within", "location": "location"}
#: t267: the items of an activity of the room a referral may name, and the field of its record
#: that holds each now (none for the deputy: no record holds one)
REFER_ACTIVITY_ITEMS = {"owner": "owner", "deputy": "deputy", "mtpd": "MTPD", "rto": "RTO",
                        "rpo": "RPO", "dependencies": "dependencies", "workaround": "workaround"}
REFER_NOW = {"owner": OWNER, "mtpd": MTPD, "rto": "recovery_target", "rpo": "rpo",
             "dependencies": DEPENDENCIES, "workaround": "workaround"}
#: t267: every item the tool offers; which kind of target may name which is `referral`'s check
REFER_ITEMS = {**REFER_RESOURCE_ITEMS, **REFER_ACTIVITY_ITEMS}
#: t256: the item as `refers` carries it: the item, the activity, last year's value from the row
REFER_ITEM = "{item} for {activity} (last year: {value})"
#: t267: an activity's item as `refers` carries it: the item and the value its record holds now
REFER_NOTE = "{item} (now: {value})"
NOT_STATED = "not stated"
#: t256: the tap a referral draws, and what it asks; his next typed line is the referral. t267: a
#: gap an answer named in an activity of the room is noted for its owner. ADR-0045 (t276): the
#: label is person-first, the owner the activity's record names, else the activity's or the
#: asset's owner. A resource's owner written for the demo (ADR-0034 Part D) is never named here.
ASK_PERSON = "Ask the {function}: {item}"
ASK_OWNER = "Ask {name} owner: {item}"
REFER_ASK = "What should the owner look at?"
REFERRED = "Referred to {to}. It is on the follow-up list in Your documents."
REFER_REFUSED = "This BIA is already accepted or signed, so nothing more is referred from it."
#: t256: the room's follow-up list, drawn by code from every run's and record's referrals
FOLLOW_UP = "output/follow-up-list.md"
FOLLOW_UP_HEAD = ("# Follow-up list\n\n"
                  "Every change referred to a resource owner, grouped by recipient.")


def runs_without(folder: Path, resource: str, activity: str) -> bool:
    """t460: the activity's own row of register resource `resource` says it can run without it
    (405 r3's group, `merge_table.RUNS_WITHOUT`): no "Ask <owner>" tap is drawn for it."""
    import merge_table  # here: merge_table imports workspace, which imports this module
    asset = drafting.read_register(folder).get(resource)
    return isinstance(asset, dict) and any(
        row.get("department") == activity
        and merge_table.RUNS_WITHOUT.search(str(row.get("workaround") or ""))
        for row in asset.get("consumers") or [])


def referral(folder: Path, read: list[str], resource: str, item: str, *,
             free: bool) -> dict[str, Any]:
    """t256: the one check on a proposed referral: which resource ids and items it may name, and
    in which turns it is accepted. A register resource id, and an item its row for the activity
    states, in a free-chat turn that read the interview of an activity with last year's record (a
    re-BIA, ADR-0044). The target as code words it, or a wrong call. t267: or an activity of the
    room and an item of its own list, in any free-chat turn, with the value its record holds now."""
    asset = drafting.read_register(folder).get(resource)
    if free and asset is None and item in REFER_ACTIVITY_ITEMS \
            and resource in walk.processes(folder):
        act = ((walk._record_at(folder, resource) or {}).get("activities") or [{}])[0]
        now = act.get(REFER_NOW.get(item, ""))
        said = ", ".join(map(str, now)) if isinstance(now, list) else str(now or "")
        return {"activity": resource, "resource": _said_name(folder, resource),
                "item": REFER_NOTE.format(item=REFER_ACTIVITY_ITEMS[item],
                                          value=said or NOT_STATED),
                "note": REFER_ACTIVITY_ITEMS[item]}
    if not free or item not in REFER_RESOURCE_ITEMS or not isinstance(asset, dict) \
            or "name" not in asset:
        return wrong_call("a referral names one register resource id and one of its items, while "
                          "a re-BIA interview is read in free chat, or an activity of the room "
                          "and one of its items in free chat", items=list(REFER_RESOURCE_ITEMS),
                          activity_items=list(REFER_ACTIVITY_ITEMS))
    for path in read:
        if not path.startswith(interview.HOMES):
            continue
        for activity in interview._named_in(folder / path):
            row = next((r for r in asset.get("consumers") or []
                        if r.get("department") == activity and r.get(item)), None)
            if row and last_year(folder, activity)["found"]:
                if runs_without(folder, resource, activity):  # t460
                    return wrong_call(f"{activity} can run without {asset['name']} (its record "
                                      "says so), so its owner is not asked")
                return {"activity": activity, "resource": asset["name"],
                        "item": REFER_ITEM.format(item=REFER_ITEMS[item],
                                                  activity=_said_name(folder, activity),
                                                  value=row[item])}
    return wrong_call(f"no re-BIA interview read in this turn has {resource}'s {item} on record")


#: t317 (ADR-0043's note of 2026-10-05): the step nemo draws after a comparison or a mismatch it
#: found (kind 1), and what his tap asks; t430 (9_nemo_design): and where the draft goes, in A8's
#: words (`INTO_DRAFTS`), now that owners show by function (ADR-0051)
WRITE_TAP = "Write to an owner" + MAIL_MARK
WRITE_ASK = f"Who should nemo write to about {{activity}}? nemo puts the draft {INTO_DRAFTS}"
#: t318 (ADR-0047): the model's proposal draws his tap; his tap writes, and the map links follow,
#: each its own tap (its note of 2026-10-05). No model on either tap.
ADD_TAP = "Add {resource} as a dependency of {activity}?"
STANDS_ON_TAP = "stands on {item}"
#: t357 (his ANSWER 2026-10-07T14:04:03Z): the site tap says what it does; the echo after it says
#: the site as `AT_SAID`, never the tap's words
AT_TAP = "Link to the {site} site"
AT_SAID = "at {site}"
ADDED_SAID = ("Added: {resource} is a dependency of {activity}, added in chat · {on}; "
              "owner not yet named, Recovery target · not recorded.")
#: t377 M (b): `link` is " <the link's words>" (`AT_SAID` for a site, else the tap's label), or
#: empty where the name already ends with them ("CSB standby at Breitenburg"): the site is said once
LINKED_SAID = "Noted: {resource}{link}, added in chat · {on}."
NOT_ADDED = "Nothing was added: this room's dependency register cannot take it."
#: t703: code's line over the add tap where his typed add takes no model turn; nothing is added yet
ADD_OFFER_SAID = "Tap below to add {resource}. It goes in with no owner and no recovery target yet."
#: t703: the code turn's name in the turn file
ADD_OFFER_KIND = "add offer"
NOT_LINKED = "Nothing changed: {resource}{link} cannot be written in this room."
#: the referral's item, by code: the comparison the turn made, or the mismatch as code found it
WRITE_COMPARED = "{activity} compared with last year's record"
WRITE_MISMATCH = "{who}'s RTO {rto} is not inside the MTPD of {activity} ({mtpd})"
WRITE_FLAGGED = "{resource}: {flag}"
#: t304: a register row's re-BIA finding, as its `quality_flags` entry starts
REBIA_FLAG = "re-BIA finding:"
#: t315: a resource whose register row names no person
NOT_NAMED = "owner not yet named ({resource})"


def holders(folder: Path, activity: str) -> list[tuple[str, list[str]]]:
    """t317: who holds the activity's register resources, as his tap names them, each with the
    resources held: a person once, by the name in `owner_name`'s brackets (315's); any other row
    (a gap, a CFO-only row) on its own, `NOT_NAMED`. In register order."""
    out: dict[str, list[str]] = {}
    for asset in drafting.read_register(folder).values():
        if isinstance(asset, dict) and asset.get("name") and any(
                row.get("department") == activity for row in asset.get("consumers") or []):
            named = re.fullmatch(r".+ \((.+)\)", str(asset.get("owner_name") or ""))
            out.setdefault(named[1] if named else NOT_NAMED.format(resource=asset["name"]),
                           []).append(asset["name"])
    return list(out.items())


def mismatches(folder: Path, model: str, read: list[str], touched: list[str],
               named: list[str], on: str | None = None) -> list[tuple[str, str]]:
    """t317 (S3): the mismatches code found that this turn reached, by `late_gaps`' rule (it read
    the register, named the resource, or touched the activity), as (activity, the mismatch as
    code states it): 263's flags, a resource's RTO or an upstream activity's not inside an
    activity's MTPD (the upstream activity's, for a chain), and 304's re-BIA findings on a
    register row (an activity using it). Never anything the model wrote.

    t340: in the order of what the turn compared: a row it named that carries a re-BIA finding
    first, then a flag on an activity the turn touched, then the rest; so a process chain never
    hides the finding on the row he asked about.

    t411: a mismatch that concerns `on`, the room's activity, is drawn on it, a chain's too."""
    if not (walk.REGISTER in read or named or touched):
        return []
    slug_of = {r.name: r.slug for r in process_map_rows(folder)}
    out: list[tuple[int, tuple[str, str]]] = []
    for aid, need in resource_needs(folder, room_sheet(folder, model)).items():
        for flag in need.get("flags", []):
            bound = slug_of.get(flag["activity"], flag["activity"])
            activity = slug_of.get(flag["who"], bound)
            activity = on if on is not None and on in (activity, bound) else activity  # t411
            if walk.REGISTER in read or aid in named or {activity, bound} & set(touched):
                out.append((1 if {activity, bound} & set(touched) else 2,
                            (activity, WRITE_MISMATCH.format(**flag))))
    rooms = walk.processes(folder)
    for aid, asset in drafting.read_register(folder).items():
        users = [row.get("department") for row in (asset.get("consumers") or [])
                 if row.get("department") in rooms] if isinstance(asset, dict) else []
        for flag in (asset.get("quality_flags") or []) if users else []:
            if str(flag).startswith(REBIA_FLAG) and (walk.REGISTER in read or aid in named
                                                     or set(users) & set(touched)):
                said = str(flag).removeprefix(REBIA_FLAG).strip().split(". ")[0]
                user = on if on is not None and on in users else \
                    next((u for u in users if u in touched), users[0])  # t411: the room's first
                out.append((0 if aid in named else 1 if set(users) & set(touched) else 2,
                            (user, WRITE_FLAGGED.format(resource=asset["name"], flag=said))))
    return [found for _, found in sorted(out, key=lambda x: x[0])]


def write_step(folder: Path, model: str, read: list[str], touched: list[str],
               named: list[str], on: str | None = None) -> dict[str, Any] | None:
    """t317: the one "Write to an owner" step under a free-chat answer, its activity and item
    by code, or None: first a re-BIA interview the turn read (256's condition: an activity with
    last year's record), then a mismatch code found (`mismatches`); only for an activity some
    register resource of which has a holder to pick. t411: with `on`, the room's activity
    (`Session._room_activity`), only a mismatch on it; t428: and an interview on another activity
    is the room's step, never the other's (B6 read production's re-interview on procurement)."""
    for path in read:
        for activity in [a if on in (None, a) else on for a in interview._named_in(folder / path)
                         ] if path.startswith(interview.HOMES) else []:
            if last_year(folder, activity)["found"] and holders(folder, activity):
                found = [d for d in discrepancies(folder, activity) if d["path"] == path]
                return {"activity": activity, "item": WRITE_COMPARED.format(
                    activity=_said_name(folder, activity)), **({"found": True} if found else {})}
    return next(({"activity": activity, "item": item} for activity, item
                 in mismatches(folder, model, read, touched, named, on)
                 if on in (None, activity) and holders(folder, activity)), None)


#: t377 (A, C, D3): a re-BIA interview's findings, read by code from its interviewer's closing
#: summary ("To sum up …"), one a sentence; never a count ("three things changed"), what stayed
#: ("unchanged", "as last year"), what is left open, or the thanks
SUMMED_UP = re.compile(r"^(?P<who>[^:\n]+): To sum up[,:]?\s*(?P<said>.+)$", re.M)
NOT_A_FINDING = re.compile(r"\bunchanged\b|\bas last year\b|\bstays? open\b|\bthank\b"
                           r"|\bthings changed\b", re.I)
COUNTED = re.compile(r"^(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten):\s*")
#: t377: an interview's `owner:` front matter, the process owner it names
INTERVIEW_OWNER = re.compile(r"^owner:\s*(.+?)\s*$", re.M)


def participants(text: str) -> list[tuple[str, str]]:
    """t373, t377: the people on a transcript's Participants line, as (name, role); a sentence
    after the list ("… sent apologies.") is not on it."""
    said = re.search(r"\*\*Participants:\*\* (.+)", text)
    return [(name.strip(), role) for name, role in
            PARTICIPANT.findall(said[1].split(").")[0] + ")" if said else "")]


def _content_words(text: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]{3,}", text.lower()))


#: t429: the words a count from one to ninety-nine is built of ("nine", "twenty-four")
_UNITS = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
          "fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_word(n: int) -> str:
    """t429: `n`, one to ninety-nine, in words (`_UNITS`, `_TENS`)."""
    tens, unit = divmod(n, 10)
    return _UNITS[n - 1] if n < 20 else _TENS[tens - 2] + (f"-{_UNITS[unit - 1]}" if unit else "")


_NUMBER_WORDS = {number_word(n): str(n) for n in range(1, 100)}
#: t429: a number in digits or in words, the longest word first ("twenty-four" before "twenty");
#: t481: a decimal is one figure ("0.9 million" is 0.9, never 0 and 9)
_NUMBER = re.compile(r"\b(?:\d+(?:\.\d+)?|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
                     + r")\b", re.I)


def _figures(text: str) -> set[str]:
    """t377 Q (a): the figures `text` states, digits and number words alike ("six" is "6")."""
    return {_NUMBER_WORDS.get(w.lower(), w) for w in _NUMBER.findall(text)}


def _names_its_head(name: str, text: str) -> bool:
    """t377: `text` names a register resource by its name's first word ("CSB", "technicians")."""
    head = re.match(r"[^\W_]{3,}", name)
    return bool(head and re.search(rf"\b{re.escape(head[0])}s?\b", text, re.I))


#: t421: the record's notation in an interview ("Impact legal: 1 h 1, 2 h 1, …"), never spoken
GRID_LINE = re.compile(r"Impact (?P<lens>\w+):")


def _carries(spoken: list[tuple[int, str, str]], said: str) -> tuple[int, str, str]:
    """t377 Q: the spoken line holding most of `said`'s figures (`_figures`), then sharing most
    words with it."""
    return max(spoken, key=lambda s: (len(_figures(said) & _figures(s[2])),
                                      len(_content_words(said) & _content_words(s[2]))))


def _lens_said(lines: list[str], spoken: list[tuple[int, str, str]],
               said: str) -> list[tuple[int, str, str]]:
    """t421: for each lens `said` names, in its order, the sentence behind the lens's grid line
    (`GRID_LINE`): its speaker's spoken line before it ("Low from eight hours …" for "Impact
    legal: …")."""
    grids = {found["lens"].lower(): (n, who) for n, line in enumerate(lines, 1)
             for who, _, rest in [line.partition(": ")] if (found := GRID_LINE.match(rest))}
    named = sorted((found.start(), lens) for lens in grids
                   if (found := re.search(rf"\b{lens}\b", said, re.I)))
    out: list[tuple[int, str, str]] = []
    for _, lens in named:
        at, who = grids[lens]
        out += [s for s in spoken if s[1] == who and s[0] < at][-1:]
    return out


def discrepancies(folder: Path, activity: str) -> list[dict[str, Any]]:
    """t377: the open discrepancies of the activity's latest interview that sums up (`SUMMED_UP`),
    by code: each summary sentence (`said`), the line of the interview it came from (`path`,
    `line`, `speaker`, `quote`: the participant's line holding most of its figures (`_figures`,
    t377 Q), then sharing most words with it), the register
    resource it names (`resource`, a transcribed row the activity uses, by `_names_its_head` in
    the sentence, else in the line; None) and who it goes to (`to`, `holder`): that resource's
    owner, else the process owner the interview names (`INTERVIEW_OWNER`). Never the model's.

    t421: an "Impact <lens>:" grid line is the record's notation, never a line spoken. `quotes`
    are the lines carrying the sentence's own words: for each lens it names, the sentence its grid
    line's speaker said before it (`_lens_said`); else the line of its last clause (", and …":
    the gap), each (`line`, `speaker`, `quote`) as the whole sentence's own are."""
    for path in sorted(interview.paths_about(folder, interview.INTERVIEWS, activity),
                       key=lambda p: Path(p).name, reverse=True):
        text = (folder / path).read_text(encoding="utf-8")
        if (summed := SUMMED_UP.search(text)):
            break
    else:
        return []
    people = dict(participants(text))
    lines = text.splitlines()
    spoken = [(n, who, said) for n, line in enumerate(lines, 1)
              for who, _, said in [line.partition(": ")]
              if who in people and who != summed["who"] and said and not GRID_LINE.match(said)]
    owner = INTERVIEW_OWNER.search(text)
    register = [a for a in drafting.read_register(folder).values()
                if isinstance(a, dict) and a.get("name") and not a.get("authored")
                and not a.get(walk.ADDED_IN_CHAT)  # t377c G4: a row added in chat is no row read
                and any(r.get("department") == activity for r in a.get("consumers") or [])]
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", summed["said"].strip()):
        said = COUNTED.sub("", sentence)
        if not said or NOT_A_FINDING.search(said):
            continue
        n, who, quote = _carries(spoken, said)
        quotes = _lens_said(lines, spoken, said) or [_carries(spoken, said.split(", and ")[-1])]
        asset = next((a for a in register if _names_its_head(a["name"], said)), None) or \
            next((a for a in register if _names_its_head(a["name"], quote)), None)
        named = re.fullmatch(r"(.+) \((.+)\)", str((asset or {}).get("owner_name") or ""))
        to = named[2] if named else owner[1] if owner else who
        out.append({"said": said[:1].upper() + said[1:], "path": path, "line": n,
                    "speaker": who, "quote": quote,
                    "quotes": [dict(zip(("line", "speaker", "quote"), q, strict=True))
                               for q in quotes],
                    "resource": asset["name"] if asset else None,
                    "to": to, "holder": named[0] if named else f"{people.get(to, '')} ({to})"})
    return out


def finding_step(folder: Path, activities: list[str | None]) -> dict[str, Any] | None:
    """t377 (A): 317's step for the first of `activities` with open `discrepancies`: his line
    asked for a message, and this turn's answer drew none of its own."""
    for activity in dict.fromkeys(a for a in activities if a):
        if discrepancies(folder, activity):
            return {"activity": activity, "found": True,
                    "item": WRITE_COMPARED.format(activity=_said_name(folder, activity))}
    return None


def write_picks(folder: Path, activity: str,
                found: bool) -> list[tuple[str, list[tuple[str, str | None]]]]:
    """t317, t377: whom "Write to an owner" offers, each with (resource, item) pairs to refer: for
    a step `found` on the activity's open `discrepancies`, their recipients, each with theirs (a
    discrepancy with no register resource is about the activity itself); else 317's `holders`,
    the process owner (`_decides`) first, t428 r2. t461: a found step's recipients come first,
    then the activity's other holders, each once, so no owner the room names is missing. t467:
    of those, the activity's own owner and lead functions first (its People box's, `words.leads`),
    then the rest in register order."""
    found_ = discrepancies(folder, activity) if found else []
    held: list[tuple[str, list[tuple[str, str | None]]]] = [
        (label, [(r, None) for r in theirs]) for label, theirs in holders(folder, activity)]
    if not found_:
        owner = _decides(folder, activity)[1]  # t428 r2: the process owner first
        return sorted(held, key=lambda pick: pick[0] != owner)
    picks: dict[str, list[tuple[str, str | None]]] = {}
    for d in found_:
        picks.setdefault(d["to"], []).append((d["resource"] or process_name(folder, activity),
                                              d["said"]))
    leads = [f for f, _, _ in words.leads(folder).get(process_name(folder, activity), [])]
    held_by = words.people(folder)

    def lead_first(pick: tuple[str, Any]) -> int:  # t467
        f = held_by.get(re.sub(r"^(Dr|Prof)\.?\s+", "", pick[0]).strip(), "")
        return leads.index(f) if f in leads else len(leads)
    return list(picks.items()) + sorted([(label, refers) for label, refers in held  # t461
                                         if label not in picks], key=lead_first)


def owner_surname(owner: Any) -> str | None:
    """t276: the surname when a record's owner names a person ("Henning Barsch"), by t64's
    `_surname`, else None ("purchasing management", a list, nothing). What is in brackets after
    the name is not read."""
    name = owner.split("(")[0].strip() if isinstance(owner, str) else ""
    return surname if (surname := _surname(name)) != name else None


def owner_function(folder: Path, owner: Any) -> str | None:
    """t418 r4 (ADR-0051): the function of the person a record's owner names (`owner_surname`'s
    person), as the organisation file gives it (`words.people`); None where it names no person or
    the file gives that person no function."""
    if owner_surname(owner) is None:
        return None
    return words.people(folder).get(re.sub(r"^(?:Dr|Prof)\.? ", "", owner.split("(")[0].strip()))


def refer_tap(folder: Path, target: dict[str, Any], item: str) -> str:
    """t267: the tap a referral draws: a gap noted for an activity's owner, else 256's. t276: the
    stored recipient stays "Owner of <name>" (`walk.REFERRED_TO_SAID`); only the label is short."""
    if "note" not in target:
        return ASK_OWNER.format(name=target["resource"], item=REFER_ITEMS[item])
    act = ((walk._record_at(folder, target["activity"]) or {}).get("activities") or [{}])[0]
    function = owner_function(folder, act.get(OWNER))  # t418 r4: by function, never the name
    return ASK_PERSON.format(function=function, item=target["note"]) if function \
        else ASK_OWNER.format(name=target["resource"], item=target["note"])


def late_gaps(folder: Path, model: str, read: list[str], touched: list[str],
              named: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """t282 (ADR-0045 amended): a resource whose own RTO is not inside the MTPD of an activity
    depending on it (263's flags, `resource_needs`), where the turn read the register, named the
    resource, or touched that activity; each drawn as 256's referral would draw it."""
    if not (walk.REGISTER in read or named or touched):
        return []
    slug_of = {r.name: r.slug for r in process_map_rows(folder)}
    out = []
    for aid, need in resource_needs(folder, room_sheet(folder, model)).items():
        for flag in need.get("flags", []):
            activity = slug_of.get(flag["activity"], flag["activity"])
            if flag["who"] == need["resource"] and not runs_without(folder, aid, activity) \
                    and (walk.REGISTER in read or aid in named or activity in touched):
                target = {"activity": activity, "resource": need["resource"],
                          "item": REFER_ITEM.format(item=REFER_ITEMS["rto"],
                                                    activity=_said_name(folder, activity),
                                                    value=flag["rto"])}
                out.append((refer_tap(folder, target, "rto"), target))
    return out


def gap_of(target: dict[str, Any]) -> tuple[str, str, str]:
    """t282: the gap a referral target names, whoever drew it: its activity, its resource and its
    item ("deputy", "RTO"), so the model's proposal and nemo's reading of one gap draw one tap."""
    return target["activity"], target["resource"], target.get("note") or \
        target["item"].split(" for ")[0]


def owner_person(owner: Any) -> str:
    """t282: the person a record's owner names: the name in brackets after a function
    ("purchasing management (Jens Harder)"), else the owner as written."""
    said = owner if isinstance(owner, str) else ""
    found = re.search(r"\(([^()]+)\)\s*$", said)
    return (found.group(1) if found else said).strip()


def deputy_gaps(folder: Path, read: list[str],
                touched: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """t282 (ADR-0045 amended, the check seat's ruling): an activity the turn touched whose
    process owner (the name in brackets in last year's "Process owner" row) is a row of the
    organisation file, by Name, among the rows whose Records cell holds that record, and no deputy
    is named there (`words.deputies`; never the model's text), as 267's referral: "Ask Harder:
    deputy"."""
    out = []
    for activity in touched:
        person = owner_person(last_year(folder, activity).get("owner"))
        target = referral(folder, read, activity, "deputy", free=True)
        if _no_deputy(folder, activity) is not None and "refusal" not in target:
            function = owner_function(folder, person)  # t418 r4: by function, never the name
            out.append((ASK_PERSON.format(function=function, item="deputy") if function
                        else refer_tap(folder, target, "deputy"), target))
    return out


def _no_deputy(folder: Path, activity: str) -> str | None:
    """t601: the one missing-deputy test: the process owner of last year's record (the name in
    its "Process owner" brackets, `owner_person`) where the organisation file's row holding that
    record names no deputy (`words.deputies`, never the model's text); None where one is named."""
    prior = last_year(folder, activity)
    person = words._person(owner_person(prior.get("owner")))
    return person if words.deputies(folder).get((person, prior.get("record", ""))) == "" else None


def _one_name(said: str) -> str:
    return "".join(said.replace("-", " ").split()).casefold()


def activity_named(folder: Path, said: str) -> str | None:
    """t318: the room's activity a proposal names, by its slug or its map name, case and spacing
    aside; None for one the room does not hold."""
    slugs = dict.fromkeys([*(r.slug for r in process_map_rows(folder)), *walk.processes(folder)])
    return next((a for a in slugs if _one_name(said) in (_one_name(a),
                                                         _one_name(map_name(folder, a)))), None)


def map_links(folder: Path, names: list[str]) -> list[dict[str, Any]] | str:
    """t318 (ADR-0047's note): each item a proposal names, as the tap linking to it: "at" a site
    of the room's Site list, else "stands on" a register item; the first name that is neither is
    returned instead, and nothing is drawn."""
    register = drafting.read_register(folder)
    sites = walk.sites(register)
    links: list[dict[str, Any]] = []
    for said in names:
        site = next((s for s in sites if _one_name(s) == _one_name(said)), None)
        item = next((k for k, a in register.items() if isinstance(a, dict) and a.get("name")
                     and _one_name(str(a["name"])) == _one_name(said)), None)
        if site is not None:
            link = {"label": AT_TAP.format(site=site), "at": site}
        elif item is not None:
            link = {"label": STANDS_ON_TAP.format(item=register[item]["name"]), "stands_on": item}
        else:
            return said
        if link not in links:
            links.append(link)
    return links


def on_the_map(folder: Path, line: str, resource: str) -> list[str]:
    """t318 round 2 (ADR-0047's note, M13): the map items his own typed line names, by code, never
    the model: the register's items (`register_named`) and the room's sites (`walk.sites`), each by
    its whole name, but never the resource itself or (an item) a name inside its name; and t370's
    one Site row its name ends on (`site_at_end`). t512: a site his line names counts even inside
    the proposal's name ("CSB standby Breitenburg"), as the model's wording never decides it."""
    register = drafting.read_register(folder)
    said, own = _name_words(line), _name_words(resource)
    items = [str(register[a]["name"]) for a in register_named(folder, line)]
    sites = walk.sites(register)
    return [n for n in dict.fromkeys([*items, *sites])
            if _name_words(n).strip() and _name_words(n) in said and _name_words(n) != own
            and (n in sites or _name_words(n) not in own)] + site_at_end(register, resource)


def site_at_end(register: dict[str, Any], resource: str) -> list[str]:
    """t370: the site a proposed name ends on, "<X> at <S>", where <S> is, case and spacing aside,
    the WHOLE name of exactly one Site row of the register; matched by code, so a site the register
    does not hold, or holds twice, is never guessed (a bare "Marschkamp" names no Site row)."""
    tails = [_one_name(resource[m.end():]) for m in re.finditer(r"\sat\s", resource, re.I)]
    rows = [str(a["name"]) for a in register.values() if isinstance(a, dict)
            and a.get("asset_type") == walk.SITE_TYPE and _one_name(str(a.get("name"))) in tails]
    return rows if len(rows) == 1 else []


def discrepancy_sites(folder: Path, activity: str, resource: str) -> list[str]:
    """t377 (E, v7-07): where a proposed resource is the subject of one of the activity's open
    `discrepancies` (its whole name in the discrepancy or in its source line), the Site rows whose
    WHOLE name that source line or the discrepancy names, each only where exactly one Site row has
    that name ("Marschkamp" never counts). Code's match; never the model's words."""
    register = drafting.read_register(folder)
    sites = [str(a["name"]) for a in register.values() if isinstance(a, dict)
             and a.get("asset_type") == walk.SITE_TYPE]
    own = _name_words(resource)
    for d in discrepancies(folder, activity) if own.strip() else []:
        said = _name_words(f"{d['quote']} {d['said']}")
        if own in said:
            return list(dict.fromkeys(
                s for s in sites if _name_words(s).strip() and _name_words(s) in said
                and sum(_one_name(x) == _one_name(s) for x in sites) == 1))
    return []


def register_named(folder: Path, line: str) -> list[str]:
    """t282: the register's resources his typed line names, each by its WHOLE name (`named_in`'s
    rule): "the corporate network" names `corporate-network`."""
    register = drafting.read_register(folder)
    said = _name_words(line)
    return [aid for aid, asset in register.items() if isinstance(asset, dict)
            and _name_words(str(asset.get("name") or "")).strip()
            and _name_words(str(asset.get("name") or "")) in said]


#: t417 (after-the-demo row 33): his typed ask to add a resource, read by code so the add tap never
#: waits on the model calling `propose_dependency`: an add word ("add it as a resource"), and the
#: name his line gives ("add the X as a resource", else "needs the X")
ADD_ASKED = re.compile(r"\badd\b[^.?!]*\bas an? (?:resource|dependency)\b", re.I)
ADD_NAMED = re.compile(r"\badd (?:the|an?) ([^.,;!?]+?) as an? (?:resource|dependency)\b", re.I)
NEEDS_NAMED = re.compile(
    r"\bneeds? (?:the|an?) ([^.,;!?]+?)(?:\s+(?:too|as well))?\s*(?:[.,;!?]|$)", re.I)


def asked_to_add(line: str) -> str | None:
    """t417: the resource his typed line asks to add, as he names it; None where his line asks
    for no addition or names nothing ("add it as a resource" alone)."""
    if not ADD_ASKED.search(line):
        return None
    found = ADD_NAMED.search(line) or NEEDS_NAMED.search(line)
    return found.group(1).strip() if found else None


#: t703: the whole of a line that takes the code turn on the led path: his ask to add as one
#: sentence ("as a resource", then at most the activity), after at most one sentence saying what
#: needs it. Any other shape is the led turn's, so a refusal, a question or a second ask keeps its
#: answer, and a read name holding a joining word is more than one resource's or holds the activity
_ASK = r"(?:please\s+|(?:can|could|would|will)\s+you\s+(?:please\s+)?)?add"
_AS_ONE = r"\bas an? (?:resource|dependency)\b"
_ASK_ENDS = r"(?:\s+please)?[.!?]?"
ADD_SENTENCE = re.compile(
    rf"{_ASK}\b[^,;]*?{_AS_ONE}(?:\s+(?:of|for)\s+(?P<on>[^,;]+?))?{_ASK_ENDS}", re.I)
#: t718: his two other wordings, the led path's read alone (`asked_to_add` stays the switch-OFF
#: path's): "add the X to <activity> as a resource", "add X as a resource of <activity>". A bare
#: name holding `NOT_BARE_NAME`'s words is no name of his ("add it", "add our X"), in lower case so
#: his "IT support" and "Line A" are names; `MORE_THAN_ONE` joins two where `NOT_ONE_NAME` does not
ADD_THE_X_TO = re.compile(
    rf"{_ASK}\s+(?:the|an?)\s+(?P<name>[^,;.?!]+?)\s+to\s+(?P<on>[^,;.?!]+?)\s+{_AS_ONE}"
    rf"{_ASK_ENDS}", re.I)
ADD_X_OF = re.compile(
    rf"{_ASK}\s+(?P<name>[^,;.?!]+?)\s+{_AS_ONE}\s+(?:of|for)\s+(?P<on>[^,;.?!]+?){_ASK_ENDS}",
    re.I)
NOT_BARE_NAME = re.compile(
    r"(?<![\w-])(?:the|an?|it|its|this|that|these|those|them|one|some|also|another|more|no|our|my"
    r"|your|their|his|her|all|every|each|both|either|any|what|which|same|other|back|something"
    r"|anything|everything)(?![\w-])")
#: what "the" alone goes before and names nothing of his ("add the one to ...")
NOT_THE_NAME = re.compile(r"(?:new\s+)?(?:one|same|following|rest|others?)", re.I)
MORE_THAN_ONE = re.compile(r"\s[&+/]\s|\n|\bplus\b|\bwith\b|\bas well as\b")
NEEDS_SENTENCE = re.compile(r"[^,;]*\bneeds? (?:the|an?) [^,;]+[.!]", re.I)
NOT_ONE_NAME = re.compile(r"\b(?:and|or|but|not|to|for)\b", re.I)


def _other_add_named(folder: Path, line: str) -> str | None:
    """t718: the resource his whole line asks to add in one of his two other wordings, on the
    activity the line names (`named_in`, as the tap reads it, so the tap is on that one)."""
    found = ADD_THE_X_TO.fullmatch(line) or ADD_X_OF.fullmatch(line)
    if found is None or NOT_ONE_NAME.search(found["name"]) or MORE_THAN_ONE.search(found["name"]):
        return None
    name = found["name"]
    if NOT_THE_NAME.fullmatch(name) if found.re is ADD_THE_X_TO \
            else NOT_BARE_NAME.search(name[0].lower() + name[1:]):
        return None
    return name if activity_named(folder, found["on"]) in named_in(folder, line) else None


def one_add_named(folder: Path, line: str) -> str | None:
    """t703: the resource his whole line asks to add, where it is one ask to add one resource
    (`ADD_SENTENCE`) and an activity it names in the ask itself is one the room holds, or t718's
    other wordings; else None."""
    *stated, ask = re.split(r"(?<=[.?!])\s+", line.strip())
    if not stated and (other := _other_add_named(folder, ask)):
        return other
    name = asked_to_add(line)
    found = ADD_SENTENCE.fullmatch(ask)
    return name if name and found and not NOT_ONE_NAME.search(name) and len(stated) <= 1 \
        and all(NEEDS_SENTENCE.fullmatch(s) for s in stated) \
        and (found["on"] is None or activity_named(folder, found["on"])) else None


def asks_one_add(folder: Path, line: str) -> bool:
    """t703: his whole line is one ask to add one resource (`one_add_named`)."""
    return one_add_named(folder, line) is not None


#: t704: the whole of a line asking to start a BIA or re-BIA, the activity named after it ("for
#: ...") or before it ("the dispatch BIA"). Any other shape is the led turn's, so a question about
#: a BIA, a refusal or a second ask keeps its answer
START_LINE = re.compile(
    r"(?:(?:yes|ok(?:ay)?),?\s+)?(?:please\s+|let['’]?s\s+|let us\s+|i['’]d like to\s+"
    r"|i (?:want|need|would like) to\s+|(?:can|could|shall|may) (?:we|you|i)\s+(?:please\s+)?)?"
    r"(?:start|begin)\s+(?:(?:the|a|our|this year['’]s)\s+)?(?:(?:new|next)\s+)?"
    r"(?:(?P<before>[^,;.?!]+?)\s+)?(?:re-?)?BIA"
    r"(?:\s+(?:for|on|of)\s+(?P<on>[^,;.?!]+?))?(?:,?\s+(?:please|now))?[.!?]?", re.I)


def typed_start(folder: Path, line: str) -> tuple[str, dict[str, Any]] | None:
    """t704: the start tap his whole line stands for (`START_LINE`), label and call: naming no
    activity the pick's, naming one its own, by its whole name or one head word (`named_loosely`).
    A head word of several is the pick's too: code knows it is more than one. Anything else there
    is more than a name ("on Monday", 493's "the Breitenburg backup"): None, the led turn's."""
    found = START_LINE.fullmatch(line.strip())
    if not found or (found["before"] and found["on"]):
        return None
    said = re.sub(r"^the\s+", "", found["on"] or found["before"] or "", flags=re.I)
    if not said:
        return START_BIA, tool_tap("list_activities")
    whole = activity_named(folder, said)
    loose = named_loosely(folder, said) if re.fullmatch(r"\w+", said) else []
    named = whole if whole in walk.processes(folder) else next(iter(loose), None)
    if not named and re.fullmatch(r"\w{6,}", said) and sum(
            said.lower() in _name_heads(process_name(folder, a), 6)
            for a in walk.processes(folder)) > 1:
        import line_reads  # it imports this module, so not at the top; 493 asks of the two by name
        return None if line_reads.meant_question(folder, line) else (
            START_BIA, tool_tap("list_activities"))
    return (next_step_label(folder, named), tool_tap("get_step", activity=named)) if named else None


#: t257: a row still pending after its activity's record landed (23_nemo_check's condition on 256)
NOT_LANDED = " (not in the signed record yet)"


def follow_up(folder: Path) -> list[tuple[str, str, str]]:
    """t256, t257: the follow-up list's rows, drawn by code from this room's runs' pending referrals
    and its records' `risk_referrals`, as (recipient, activity, row): a row on both once, and a row
    still pending after its activity's record landed marked `NOT_LANDED`."""
    rows: dict[tuple[str, str], tuple[str, str]] = {}
    for run_path in sorted((folder / walk.RUNS).glob("*.json")):
        run = walk.read_record(folder, f"{walk.RUNS}/{run_path.name}") or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        record = walk._record_at(folder, run["process"]) if "process" in run else None
        landed = (record or {}).get(REFERRALS) or []
        for row in [*(run.get(PENDING_REFERRALS) or []), *landed]:
            late = record is not None and row not in landed
            rows.setdefault((row["to"], row["refers"]),
                            (run.get("process", run_path.stem), row["refers"] + NOT_LANDED * late))
    return [(to, activity, said) for (to, _), (activity, said) in rows.items()]


#: t371: the story's today, the programme plan's "As of" line ("As of 2 October 2026", a weekday
#: before the day allowed), never the clock
AS_OF = re.compile(r"\bAs of (?:[A-Z][a-z]+,? )?(\d{1,2} [A-Z][a-z]+ \d{4})\b")


def story_today(folder: Path) -> datetime.date | None:
    """t371: the day the room's story is set on, from its programme plan's `AS_OF` line; None
    where the room has no plan or the plan no such line."""
    plan = folder / PROGRAMME_PLAN
    said = AS_OF.search(plan.read_text(encoding="utf-8")) if plan.is_file() else None
    for shape in ("%d %B %Y", "%d %b %Y"):
        with contextlib.suppress(ValueError):
            return datetime.datetime.strptime(said[1], shape).date() if said else None
    return None


#: t544: a day his line names, a weekday ("Monday's", "monday") or a date ("2 October", "9 Nov
#: 2026"), in `calendar`'s English names
_WEEKDAY_SAID = re.compile(r"\b(next\s+)?(" + "|".join(calendar.day_name) + r")", re.I)
_DATE_SAID_ON = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(
    sorted([*calendar.month_name[1:], *calendar.month_abbr[1:]], key=len, reverse=True))
    + r")\b\.?(?:\s+(\d{4}))?", re.I)


#: t633: a line asking for an act still to be done on the day it names, by the act's own word
#: (not "invited", "scheduled" or the noun "meeting", which tell of one done)
_FUTURE_ACT = re.compile(r"\b(invit(?:e|es|ation|ations)|(?:re)?schedule|(?:re)?book(?:ing)?|"
                         r"arrange|set[\s-]?up|meet)\b", re.I)
#: t633: a word telling of what is done: beside a future act, the line keeps t544's reading.
#: t669: a past act on the invitation itself ("the invitation we sent on Thursday") is one, but
#: not "got to" or "be sent", which ask for the act still to be done
_PAST_SAID = re.compile(r"\b(last|happened|was|were|did|had|held|went|said|changed|came|met|"
                        r"decided|agreed|discussed|told|found|reported|took|cancell?ed|"
                        r"(?<!\bbe )sent|invited|got(?!\s+to\b))\b", re.I)


def _future_act(line: str, said: re.Match[str]) -> bool:
    """t633: whether `line` asks for a future act on the weekday `said` names: an act word, no word
    of the past, and the weekday neither "Thursday's" nor "Thursdays" (a thing or a habit). Where
    it cannot tell, it is not one: the line keeps t544's reading."""
    return bool(_FUTURE_ACT.search(line)) and not _PAST_SAID.search(line) \
        and not re.match(r"(['’]s|s)\b", line[said.end():])


def next_weekday(today: datetime.date, weekday: int) -> datetime.date:
    """t633: the first `weekday` (Monday 0) after `today`; today's own the one a week on. The one
    sum for the next weekday: `named_day` and `weekday_date` (`fact_weekday`) both ask it."""
    return today + datetime.timedelta(days=(weekday - today.weekday() - 1) % 7 + 1)


def named_day(folder: Path, line: str) -> datetime.date | None:
    """t544: the day his line names, against the story's today (`story_today`): a weekday is its
    last one on or before today ("Monday" on Wednesday 11 Nov is 9 Nov), "next" and a weekday the
    first one after it (16 Nov, r2), a date without a year is in today's year, or the year before
    where that falls after today. t633: on a line about a future act (`_future_act`), a weekday is
    the next one, as `fact_weekday` gives it. None where it names no day or the room has no
    today."""
    today = story_today(folder)
    if today is None:
        return None
    if said := _DATE_SAID_ON.search(line):
        month = next(n for n in range(1, 13) if said[2].lower() in
                     (calendar.month_name[n].lower(), calendar.month_abbr[n].lower()))
        with contextlib.suppress(ValueError):
            day = datetime.date(int(said[3] or today.year), month, int(said[1]))
            return day.replace(year=day.year - 1) if day > today and not said[3] else day
        return None
    if said := _WEEKDAY_SAID.search(line):
        weekday = [d.lower() for d in calendar.day_name].index(said[2].lower())
        if said[1] or _future_act(line, said):
            return next_weekday(today, weekday)
        return today - datetime.timedelta(days=(today.weekday() - weekday) % 7)
    return None


def weekday_date(folder: Path, said: str) -> dict[str, str] | None:
    """t631 (ADR-0061 d2): the day a weekday in `said` falls on, worked out against the story's
    today: the next one after it, today's own weekday the one a week on. None where `said` names
    no weekday or the room has no today."""
    today, m = story_today(folder), _WEEKDAY_SAID.search(said)
    if today is None or m is None:
        return None
    weekday = [d.lower() for d in calendar.day_name].index(m[2].lower())
    day = next_weekday(today, weekday)
    return {"weekday": calendar.day_name[weekday], "date": day.isoformat(),
            "today": today.isoformat()}


def day_interviews(folder: Path, day: datetime.date) -> list[str]:
    """t544: the room's interviews held on `day`, by the date their file names open with."""
    return [p for p in room_files(folder) if p.startswith(f"{interview.INTERVIEWS}/")
            and Path(p).name.startswith(day.strftime("%y_%m_%d_"))]


#: t544 r4: the word for an interview in a model sentence
INTERVIEW_SAID = re.compile(r"\binterview", re.I)

#: t544 (15_nemo_design's look): the line closing a named day's what-changed answer, this year's
#: other interviews; "both"/"all" where they share one day, each its own date by day where they
#: do not (r2)
OTHERS_SAID = "{count} other interview{s} this year{on}: {names}."


def others_said(folder: Path, shown: list[str]) -> str:
    """t544: `OTHERS_SAID` for this year's interviews up to the story's today other than `shown`,
    their activities in the process map's order; "" where there is none."""
    if (today := story_today(folder)) is None:
        return ""
    others = [p for p in room_files(folder) if p.startswith(f"{interview.INTERVIEWS}/")
              and _DATED_FILE.match(Path(p).name) and p not in shown
              and today.strftime("%y_") <= Path(p).name[:8] <= today.strftime("%y_%m_%d")]
    if not others:
        return ""
    by = {a: p for p in others for a in interview._named_in(folder / p)}
    days = {_date_of(p) for p in others}
    one = len(days) == 1
    order = sorted(process_map_order(folder, list(by)), key=lambda a: Path(by[a]).name[:8])
    names = [_said_name(folder, a) + ("" if one else f" ({_date_of(by[a])})") for a in order]
    on = (f", {days.pop()}" if len(others) == 1 else f", {'both' if len(others) == 2 else 'all'} "
          f"{days.pop()}") if one else ""
    return OTHERS_SAID.format(count=number_word(len(others)).capitalize(),
                              s="s" * (len(others) > 1), on=on, names=_listed(names))


#: t373 (ADR-0049): the invitation's slot: the programme plan's planned re-interview day ("planned
#: for Tue 17 Nov 2026"), at the story's fixed hour for its fixed length, in the story's zone; never
#: the clock, never the model's figures. t405 r3: 45 minutes (his ANSWER 2026-10-12T14:29:43Z, "45
#: min everywhere"; the reviewer's 45 = 39 + 6), no longer his v6 plan's 10:00–11:30
PLANNED_FOR = re.compile(r"\bplanned for (?:[A-Z][a-z]+,? )?(\d{1,2} [A-Z][a-z]+ \d{4})\b")
INTERVIEW_AT = datetime.time(10, 0)
INTERVIEW_LENGTH = datetime.timedelta(minutes=45)
STORY_ZONE = "Europe/Berlin"
#: t373: where an interview was held, as a transcript records it ("Recorded in the meeting room at
#: the Marschkamp plant.")
RECORDED_IN = re.compile(r"\bRecorded in (the [^.\n]+)\.")
#: t373: one person on a transcript's Participants line, "<name> (<role>)"
PARTICIPANT = re.compile(r"([^;()]+?) \(([^)]*)\)")


def planned_day(folder: Path, activity: str) -> datetime.date | None:
    """t373: the day the room's programme plan has the activity's re-interview planned for, from
    its row's `PLANNED_FOR`; None where the plan names no day (a month only, or no plan)."""
    plan = folder / PROGRAMME_PLAN
    name = process_name(folder, activity).lower()
    for line in plan.read_text(encoding="utf-8").splitlines() if plan.is_file() else []:
        cells = [c.strip().lower() for c in line.split("|")]
        said = PLANNED_FOR.search(line) if name in cells else None
        for shape in ("%d %b %Y", "%d %B %Y") if said else ():
            with contextlib.suppress(ValueError):
                return datetime.datetime.strptime(said[1], shape).date()  # type: ignore[index]
    return None


def interview_slot(folder: Path,
                   activity: str) -> tuple[datetime.datetime, datetime.datetime] | None:
    """t373: the invitation's start and end, on `planned_day` at `INTERVIEW_AT` in `STORY_ZONE`."""
    from zoneinfo import ZoneInfo
    day = planned_day(folder, activity)
    if day is None:
        return None
    start = datetime.datetime.combine(day, INTERVIEW_AT, ZoneInfo(STORY_ZONE))
    return start, start + INTERVIEW_LENGTH


def interview_place(folder: Path) -> str:
    """t373: where the room's latest recorded interview was held (`RECORDED_IN`); "" if none."""
    for path in sorted((folder / interview.INTERVIEWS).glob("*.md"), reverse=True):
        if found := RECORDED_IN.search(path.read_text(encoding="utf-8")):
            return found[1]
    return ""


def invitees(folder: Path, activity: str) -> list[tuple[str, str, bool]]:
    """t373: who the invitation goes to, as (name, role, from the register): the people of the
    activity's last interview, its interviewer aside; then each person the register names as
    holding a resource the activity uses on a recorded row (`holders`' rule, never an authored
    asset or row: those are the demo's, ADR-0034 Part D). Each person once."""
    people = [(name, role, False) for name, role in last_participants(folder, activity)
              if "interviewer" not in role]
    for asset in drafting.read_register(folder).values():
        if not isinstance(asset, dict) or asset.get("authored"):
            continue
        named = re.fullmatch(r"(.+) \((.+)\)", str(asset.get("owner_name") or ""))
        if named and named[2] not in [p for p, _, _ in people] and any(
                row.get("department") == activity and not row.get("authored")
                for row in asset.get("consumers") or []):
            people.append((named[2], named[1], True))
    return people


def latest_interview(folder: Path, activity: str) -> str | None:
    """t601: the one "latest interview" lookup: the activity's interview whose file name sorts
    last (its date first); None where it has none."""
    return max(interview.paths_about(folder, interview.INTERVIEWS, activity), default=None,
               key=lambda p: Path(p).name)


def last_participants(folder: Path, activity: str) -> list[tuple[str, str]]:
    """t601 (fact): who was there last time: the people of the activity's latest interview
    (`latest_interview`), as (name, role), its interviewer too."""
    last = latest_interview(folder, activity)
    return participants((folder / last).read_text(encoding="utf-8") if last else "")


def invitable(folder: Path, line: str, activity: str | None) -> str | None:
    """t373: the activity "Invite to the interview" is for: of those his line names, else the one
    under way, else every activity, the one with the earliest `planned_day` on or after the
    story's today; None where none has a day."""
    named = named_in(folder, line) or ([activity] if activity else walk.processes(folder))
    today = story_today(folder)
    days = [(day, a) for a in named if (day := planned_day(folder, a))
            and (today is None or day >= today)]
    return min(days)[1] if days else None


#: t377 (B, D6): his invite line asks who (t418: or which names); nemo then answers with 373's list
#: itself (`invite_said`)
WHO_WORDS = re.compile(r"\bwho\b|\bwer\b|\bwen\b", re.I)
#: t433 (B3): who comes, whatever the words: the participants or invitees (never "to the
#: participants", where an invitation is addressed: B8), who attends, joins, comes or is there,
#: who or which people to ask or invite (a misspelt invite too)
WHO_COMES = re.compile(
    r"(?<!\bto the )(?<!\bproposed )\bparticipants?\b|\binvitees?\b|\battend\w*"
    r"|\bwho\b[^.?!]*\b(?:come|comes|join|be there|ask(?:ed)? to|inv\w*)\b"
    r"|\bwhich people\b[^.?!]*\b(?:ask|inv\w*|interview)\b", re.I)
INVITE_HEAD = "**Who to invite · {name}**"
INVITE_LAST = "- {when} ({on}): {people}{by}."
#: t389 (B3): a person as the function (his "Everywhere"). t418 r2 (14_marschkamp): one function
#: per item, its part in the interview in the brackets ("the Head of Purchasing (process owner)"),
#: the name beside it only where his line asks for names (ADR-0051); an interviewer is "with the
#: BCM Officer as interviewer"
INVITE_WHO = "the {function}{inside}"
INVITE_BY = "{who} as interviewer"
INVITE_ADD = ("- Add the {person}: the register has them holding {held}, which "
              "{activity} uses")
INVITE_CARRIED = "; {other}'s re-interview on {on} found: {said}"
#: t377 (D6): a register resource the activity uses whose row names no person, as nemo says it
OWNER_GAP = "the {resource} has no named owner"
INVITE_GAP = "- Gap: {gaps} (the dependency register)."


def held_on(path: str) -> datetime.date | None:
    """t377: the day an interview was held, by its file name ("26_11_09_…")."""
    with contextlib.suppress(ValueError):
        return datetime.datetime.strptime(Path(path).name[:8], "%y_%m_%d").date()
    return None


def _day(day: datetime.date | None) -> str:
    return f"{day.day} {day:%b %Y}" if day else "undated"


def _listed(names: list[str]) -> str:
    return ", ".join(names[:-1]) + " and " * (len(names) > 1) + (names[-1] if names else "")


#: t393 r2 (his "Middle dots", 2026-10-12): a list of names in the dependency answers, whose
#: names may hold "and" themselves ("Sign-in and authorisation"), is joined by middle dots
MIDDLE_DOT = " · "


def _dot_listed(names: list[str]) -> str:
    return MIDDLE_DOT.join(names)


def _name_heads(name: str, least: int) -> set[str]:
    """t566: the words a name is called by, at least `least` letters long: the last word of each
    part its "and" joins ("dispatch" and "delivery" for "Goods dispatch and delivery"), where the
    thing itself sits. A word that only modifies it ("material" in "Raw material procurement") is
    no head, so a line using that word alone names nothing."""
    return {w for part in re.split(r"\band\b", _map_key(name))
            for w in re.findall(r"\w+", part)[-1:] if len(w) >= least}


def named_loosely(folder: Path, line: str) -> list[str]:
    """t377 (D6): the one activity a head word of six letters or more of his line names alone
    ("the dispatch BIA"), where `named_in`'s whole names find none; none where two would match.
    t566: only the word a part of the name ends on names it; a modifier ("material") does not."""
    said = set(re.findall(r"\w{6,}", line.lower()))
    hits = [a for a in walk.processes(folder)
            if said & _name_heads(process_name(folder, a), 6)]
    return hits if len(hits) == 1 else []


def invite_activity(folder: Path, line: str, activity: str | None) -> str | None:
    """t377 (B): the activity his invite line is about: one it names (`named_in`, else
    `named_loosely`), else 373's `invitable` for the one under way, else for the whole room."""
    named = named_in(folder, line) or named_loosely(folder, line)
    return named[0] if named else invitable(folder, line, activity) or invitable(folder, line, None)


def owner_gaps(folder: Path, activity: str) -> list[str]:
    """t377 (D6): `OWNER_GAP` for each resource of the activity no register row names a person
    for (`holders`' `NOT_NAMED`)."""
    return [OWNER_GAP.format(resource=r[:1].lower() + r[1:]) for r in _unowned(folder, activity)]


def _unowned(folder: Path, activity: str) -> list[str]:
    """t601: the activity's register resources no row names a person for (`holders`' `NOT_NAMED`),
    in register order."""
    return [r for label, theirs in holders(folder, activity) for r in theirs
            if label == NOT_NAMED.format(resource=r)]


def carried(folder: Path, activity: str) -> list[tuple[str, dict[str, Any]]]:
    """t377 (B, D3): the open `discrepancies` of the room's other activities on a register
    resource this activity uses too, each as (that activity, the discrepancy)."""
    uses = {a.get("name") for a in drafting.read_register(folder).values() if isinstance(a, dict)
            and any(r.get("department") == activity for r in a.get("consumers") or [])}
    return [(other, d) for other in walk.processes(folder) if other != activity
            for d in discrepancies(folder, other) if d["resource"] in uses]


def _invited_as(folder: Path, person: str, role: str, names: bool) -> str:
    """t418 r2: an invitee as B3 lists them (`INVITE_WHO`): their function, then in brackets
    their name where `names`, and their part in the interview but an interviewer's."""
    part = role.partition(", ")[2]
    inside = ", ".join(filter(None, [person * names, "" if part == "interviewer" else part]))
    return INVITE_WHO.format(function=holder_function(folder, {"holder": role, "to": person}),
                             inside=f" ({inside})" if inside else "")


def invite_said(folder: Path, activity: str, names: bool = False) -> str:
    """t377 (B, D6): who to invite, by code: each interview of the activity, newest first, with
    its people and its interviewer (`participants`); then 373's `invitees` the register adds, each
    with what they hold that the activity uses (`holders`) and any open discrepancy carried on it
    (`carried`); then the register's owner gaps (`owner_gaps`). Never the model's list. t418 r2:
    each person by function (`_invited_as`), the name beside it only where `names` (his line asks
    for names, ADR-0051)."""
    lines = [INVITE_HEAD.format(name=process_name(folder, activity))]
    paths = sorted(interview.paths_about(folder, interview.INTERVIEWS, activity),
                   key=lambda p: Path(p).name, reverse=True)
    for i, path in enumerate(paths):
        people = participants((folder / path).read_text(encoding="utf-8"))
        by = [INVITE_BY.format(who=_invited_as(folder, n, r, names)) for n, r in people
              if "interviewer" in r]
        lines.append(INVITE_LAST.format(
            when="Last time" if i == 0 else "Before that", on=_day(held_on(path)),
            people=_listed([_invited_as(folder, n, r, names) for n, r in people
                            if "interviewer" not in r]),
            by=f", with {_listed(by)}" if by else ""))
    held = dict(holders(folder, activity))
    for person, role, named in invitees(folder, activity):
        if named:
            theirs = held.get(person, [])
            lines.append(INVITE_ADD.format(person=_invited_as(folder, person, role, names)
                                           .removeprefix("the "),
                                           held=_listed(theirs),
                                           activity=_said_name(folder, activity)) + "".join(
                INVITE_CARRIED.format(other=_said_name(folder, other),
                                      said=d["said"].rstrip("."), on=_day(held_on(d["path"])))
                for other, d in carried(folder, activity) if d["resource"] in theirs) + ".")
    if gaps := owner_gaps(folder, activity):
        lines.append(INVITE_GAP.format(gaps="; ".join(gaps)))
    return "\n".join(lines)


#: t377 (D3, D6): his line asks what to focus on, or for the questionnaire; nemo answers itself
#: t470 (router report R1, B4): or what to concentrate on, or what we asked last year
FOCUS_WORDS = re.compile(r"\bfocus\b|\bquestionnaires?\b|\bfrageb[öo]gen|\bconcentrate\b"
                         r"|\bwhat did we ask\b|\bquestions last year\b", re.I)
QUESTIONNAIRE_WORDS = re.compile(r"\bquestionnaires?\b|\bfrageb[öo]gen", re.I)
#: t457: the word that keeps a line asking what changed on the focus card (B4)
FOCUS_ASKED = re.compile(r"\bfocus\b", re.I)
FOCUS_HEAD = "**{head} · {name}**"
FOCUS_NOW, QUESTIONNAIRE = "Focus now", "Questionnaire"
FOCUS_ON_TOP = "Focus this year:"
CARRIED_FOCUS = "From {other}'s re-interview ({on}; {activity} uses {resource} too): {said}"
DOWNSTREAM_FOCUS = "From {other}'s re-interview ({on}; {activity} feeds it): {said}"
SUPPLIERS_FOCUS = "A key supplier failing in that window: {suppliers}."
GAP_FOCUS = "Gap: {gap} (the dependency register)."
#: t377c G5: the questionnaire's questions, those last year's interview asked
QUESTIONS_SAID = "The questions, as last year's interview asked them:"
THANKS = re.compile(r"thank", re.I)
LAST_YEAR_SAID = "Last year's answers, record {record}{held}:"
#: Q-GRID (M13): the record's own RTO and MTPD, the MTPD with where its grid reaches its top level
FIGURE_SAID = "{key} {value} (the record's own figure{note})"
GRID_NOTE = "; the grid reaches {level} at {horizon}"
GRID_LEVELS = ("none", "low", "medium", "high")
#: a cell last year's record leaves blank, as the record writes it
GRID_BLANK = "–"


def focus_points(folder: Path, activity: str) -> list[str]:
    """t377 (D3, D6): what to focus on in the activity's BIA now, by code (t601: `focus`' data):
    its own open findings, those carried on a register resource it uses too, those of an activity
    it feeds with no register resource and then its suppliers, and its register owner gaps."""
    found, name = focus(folder, activity), _said_name(folder, activity)
    out = [*found["own"]]
    out += [CARRIED_FOCUS.format(other=_said_name(folder, c["other"]), on=_day(held_on(c["path"])),
                                 activity=name, resource=c["resource"], said=c["said"])
            for c in found["carried"]]
    out += [DOWNSTREAM_FOCUS.format(other=_said_name(folder, d["other"]),
                                    on=_day(held_on(d["path"])), activity=name, said=d["said"])
            for d in found["downstream"]]
    if found["suppliers"]:
        out.append(SUPPLIERS_FOCUS.format(suppliers=_listed(found["suppliers"])))
    # t377 N2: a register gap a point above already names (its resource, by its whole name) is
    # said once, by that point
    return out + [GAP_FOCUS.format(gap=OWNER_GAP.format(resource=r[:1].lower() + r[1:]))
                  for r in found["unowned"]
                  if not any(_name_words(r) in _name_words(p) for p in out)]


def focus(folder: Path, activity: str) -> dict[str, Any]:
    """t601 (fact): the focus kinds of the activity's BIA now, as data: its own open
    `discrepancies` (`own`); those `carried` on a register resource it uses too (`other`, `path`,
    `resource`, `said`); those with no register resource of an activity it feeds, the process
    map's downstream (`downstream`), and then its register `suppliers`, any of which failing falls
    in that window (none without a downstream one); and its register resources with no named owner
    (`unowned`)."""
    rows = process_map_rows(folder)
    feeds = [r.slug for r in rows for own in rows if own.slug == activity
             and r.name in (own.downstream or ())]
    loose = [{"other": other, "path": d["path"], "said": d["said"]} for other in feeds
             for d in discrepancies(folder, other) if d["resource"] is None]
    suppliers = [str(a["name"]) for a in drafting.read_register(folder).values()
                 if isinstance(a, dict) and a.get("asset_type") == "External supplier"
                 and any(r.get("department") == activity for r in a.get("consumers") or [])]
    return {"own": [d["said"] for d in discrepancies(folder, activity)],
            "carried": [{"other": other, "path": d["path"], "resource": d["resource"],
                         "said": d["said"]} for other, d in carried(folder, activity)],
            "downstream": loose, "suppliers": suppliers if loose else [],
            "unowned": _unowned(folder, activity)}


def last_year_said(folder: Path, activity: str, people: bool = True) -> list[str]:
    """t377 (Q-GRID, M13): last year's answers as the record states them: its impact grid cell by
    cell as written (a blank stays `GRID_BLANK`), then its RTO and MTPD (`FIGURE_SAID`), the MTPD
    with where the grid first reaches its highest level (`GRID_NOTE`). Never a typed figure.
    t389: without `people`, the heading names no interview and no person (the briefing's)."""
    prior = last_year(folder, activity)
    if not prior["found"]:
        return []
    grid = prior.get("grid") or {}
    horizons = list(dict.fromkeys(h for row in grid.values() for h in row["cells"]))
    held = f" ({prior['interview']}; {prior['participants']})" if people and \
        "interview" in prior and "participants" in prior else ""
    lines = [LAST_YEAR_SAID.format(record=prior.get("record", prior["ref"]), held=held)]
    if grid:
        lines += ["", f"| Category | {' | '.join(horizons)} |", "|---" * (len(horizons) + 1) + "|"]
        lines += [f"| {category} | "
                  + " | ".join(row["cells"].get(h) or GRID_BLANK for h in horizons) + " |"
                  for category, row in grid.items()]
    reached = [(GRID_LEVELS.index(v), -i, v, h) for row in grid.values()
               for i, (h, v) in enumerate(row["cells"].items()) if v in GRID_LEVELS]
    top = max(reached, default=None)
    figures = prior.get("figures") or {}
    said = [FIGURE_SAID.format(key=key, value=figures[key], note=GRID_NOTE.format(
        level=top[2], horizon=top[3]) if key == "MTPD" and top else "")
        for key in ("RTO", "MTPD") if figures.get(key)]
    return [*lines, *([""] + [" · ".join(said)] if said else [])]


def last_years_questions(folder: Path, activity: str) -> list[str]:
    """t377c G5: the questions last year's interview asked, by code: the transcript whose front
    matter names last year's record as its `source:`, each line of its `facilitator:` with the
    thanks left out. None where the room holds no such transcript."""
    prior = last_year(folder, activity)
    for path in interview.paths_about(folder, interview.INTERVIEWS, activity) if prior[
            "found"] else []:
        text = (folder / path).read_text(encoding="utf-8")
        who = re.search(r"^facilitator:\s*(.+?)\s*$", text, re.M)
        if who and re.search(rf"^source:\s*prior BIA record {re.escape(str(prior.get('record')))}"
                             r"\s*$", text, re.M):
            lines = [said for line in text.splitlines()
                     for name, _, said in [line.partition(": ")] if name == who[1]]
            asked = [" ".join(x for x in re.split(r"(?<=[.!?])\s+", said) if not THANKS.match(x))
                     for said in lines]
            return [x for x in asked if x]
    return []


def focus_said(folder: Path, activity: str, head: str) -> str:
    """t377 (D3, D6): the focus points on top, then last year's answers (`last_year_said`);
    t377c G5: the questionnaire then asks last year's questions (`last_years_questions`)."""
    points = focus_points(folder, activity)
    asked = last_years_questions(folder, activity) if head == QUESTIONNAIRE else []
    return "\n".join([FOCUS_HEAD.format(head=head, name=process_name(folder, activity)),
                      *([FOCUS_ON_TOP, *(f"{n}. {p}" for n, p in enumerate(points, 1)), ""]
                        if points else []),
                      *last_year_said(folder, activity),
                      *(["", QUESTIONS_SAID, *(f"{n}. {q}" for n, q in enumerate(asked, 1))]
                        if asked else [])])


#: t389 (B7): his line asks for a briefing; nemo draws it itself from the plan, last year's record,
#: the register and the interviews (`briefing_said`), and the model's words are dropped, so no
#: time, place or figure in it is the model's (M13). Attendees by function, never by name.
#: t470 (router report R1, B7): or a page or paper to print or for the meeting
BRIEFING_WORDS = re.compile(r"\bbriefings?\b|\b(?:to|for) print\b|\bpaper for the meeting\b",
                            re.I)
BRIEFING_KIND = "briefing"
BRIEFING_HEAD = "**Briefing · {name}**"
BRIEFING_WHY = "**Why now** · from the BIA programme plan"
BRIEFING_PLAN = "- Last BIA {last}, review due {due}: {status}."
BRIEFING_DEPENDENCIES = "**Dependencies** · from the dependency register"
BRIEFING_TABLE = ("| Resource | Owner | Workaround |", "|---|---|---|")
BRIEFING_FOCUS = "**Focus questions**"
BRIEFING_ATTENDEES = "**Attendees**"
BRIEFING_ADD = "- {function}: holds {held}, which {activity} uses"
#: t405: under the briefing, its two pages as a PDF (`briefing.pdf`), served at the room's
#: `<root>/w/<code>/briefing/<activity>.pdf` (`workspace.briefing`)
BRIEFING_PDF = "[Download the two-page briefing (PDF)]({link})"


def _function(role: str) -> str:
    """t389: a Participants role as the briefing says it: "Head of Purchasing, process owner" as
    "Head of Purchasing (process owner)"."""
    head, _, rest = role.partition(", ")
    return f"{head} ({rest})" if rest else head


def briefing_facts(folder: Path, activity: str) -> dict[str, Any]:
    """t389 (B7): what the briefing for the activity's re-interview says, by code: why now (its
    programme plan row as it stands, and what it feeds), last year's answers (`last_year_said`, no
    names), its register resources with their owner's function and workaround, the focus points
    (`focus_points`), and the attendees by function: the last interview's, then those 373's
    `invitees` adds from the register, each with what it holds; r2: never for a row of 390's "It
    can run without them" group (`without`). Every figure, date and name is a file's. t405: the
    one source of the chat's text (`briefing_said`) and the PDF (`briefing`)."""
    name = process_name(folder, activity)
    rows = [r for r in _plan_table(folder)[1] if _map_key(r[1]) == _map_key(name)]
    own = next((r for r in process_map_rows(folder) if r.slug == activity), None)
    why = [BRIEFING_PLAN.format(last=r[3], due=r[4], status=r[5]) for r in rows[:1]]
    if own and own.downstream:
        why.append(NEXT_FEEDS.format(feeds=_listed([d[:1].lower() + d[1:]
                                                    for d in own.downstream])))
    import merge_table  # here: merge_table imports workspace, which imports this module
    # r3: 390's rows (`dependency_groups`), so every row B6 shows is here, with B5's owner gaps
    groups = dependency_groups(folder, activity)
    uses = [(str(a["name"]), _owner_function(a.get("owner_name")), use)
            for _, members in groups for a, use in members]
    unowned = [r for r, o, _ in uses if o == NOT_STATED]
    # t405 r2: 390's "It can run without them" rows invite no one
    without = [str(a["name"]) for group, members in groups
               if group == merge_table.RUNS_WITHOUT_RULE for a, _ in members]
    held = {person: [r for r in rows if r not in without]
            for person, rows in holders(folder, activity)}
    attendees: list[tuple[str, list[str] | None]] = [
        (_function(role), None) for _, role in last_participants(folder, activity)]
    attendees += [(role, held[person]) for person, role, named in invitees(folder, activity)
                  if named and held.get(person)]
    return {"name": name, "why": why, "last_year": last_year_said(folder, activity, people=False),
            "uses": uses, "unowned": unowned, "points": focus_points(folder, activity),
            "attendees": attendees, "said_name": _said_name(folder, activity),
            "without": without}


def briefing_said(folder: Path, activity: str) -> str:
    """t389 (B7): the briefing's chat text, drawn from `briefing_facts` (t405: as the PDF is)."""
    said = briefing_facts(folder, activity)
    why, uses, unowned, points = said["why"], said["uses"], said["unowned"], said["points"]
    attendees = [f"- {function}" if held is None else BRIEFING_ADD.format(
        function=function, held=_listed(held), activity=said["said_name"])
        for function, held in said["attendees"]]
    sections = [
        [BRIEFING_WHY, *why] if why else [],
        said["last_year"],
        [BRIEFING_DEPENDENCIES, "", *BRIEFING_TABLE,
         *(f"| {r} | {o} | {row.get('workaround') or NOT_STATED} |" for r, o, row in uses),
         *(["", NO_OWNER.format(names=_listed(unowned))] if unowned else [])] if uses else [],
        [BRIEFING_FOCUS, *(f"{n}. {p}" for n, p in enumerate(points, 1))] if points else [],
        [BRIEFING_ATTENDEES, *attendees] if attendees else []]
    return "\n\n".join([BRIEFING_HEAD.format(name=said["name"]),
                        *("\n".join(s) for s in sections if s)])


#: t390 (A6, B5, B6): his line asks for the activity's dependencies, or for its single points of
#: failure or missing workarounds; nemo draws the table itself (`dependencies_said`) and the
#: model's own table is dropped, so no row, workaround or owner in it is the model's (M13)
#: t433 (B6): a dependency however spelt ("dependancies", "dependecys", "Dependencies?"), what or
#: everything it depends or relies on, its line up- and downstream, and what we need; "does it
#: depend on e-mail?" asks about one resource, not for the table. t457: "depending on …" is a
#: conditional, a dependency only after what or which; "what do you need from me" asks the delegate
#: t470 (router report R1, A6): "depedencies" too, everything a line needs, and what we need after
#: the things named ("What machines, people and systems do we need")
DEPENDENCY_WORDS = re.compile(r"\bdepend(?!s? on\b|ing on\b)\w+|\bdep\w*nc(?:y|ies)\b"
                              r"|\b(?:what|which|everything)\b"
                              r"[^.?!]*\b(?:depends?|depending|rel(?:y|ies)) on\b|\bupstream\b"
                              r"|\beverything\b[^.?!]*\bneeds\b"
                              r"|\bdownstream\b"
                              r"|\bwhat\b[^.?!]*\bdo (?:we|you|I) need\b(?! from me\b)", re.I)
#: t526: a line about AI services or a BIA template is no ask about an activity's dependencies,
#: though "which ... depend on" and "what ... do I need" match `DEPENDENCY_WORDS` in it
NOT_AN_ACTIVITY_ASK = re.compile(r"\bAI (?:services?|tools?)\b|\btemplates?\b|\bfirst BIA\b", re.I)
#: t451 (prompt check run 2, B5): a gap in the workarounds asked outright: a row with none
#: ("No workaround where?"), without one (B5-02) or lacking one ("Which dependencies lack a
#: workaround?", which drew B6's table), the gaps themselves ("Workaround gaps?"), or no plan B
#: (B5-17). Naming a workaround ("What is the workaround for …?") asks for no gap. t470 (router
#: report R1): a single failure, and the rows of a workaround list flagged "with none"
SPOF_WORDS = re.compile(r"\bSPOFs?\b|\bsingle points? of failure\b|\bmissing workarounds?\b"
                        r"|\b(?:no|without|lacks?)(?: an?)? work-?arounds?\b"
                        r"|\bwork-?arounds? gaps?\b|\bno plan B\b"
                        r"|\bsingle failures?\b|\bwork-?arounds?\b[^.?!]*\bwith none\b", re.I)
#: t452 (prompt check run 2, A6-18): "now and before" sets the two years side by side as well;
#: "before" or "now" alone ("before we start", "what is on now") asks for no comparison
YEARS_WORDS = re.compile(r"\b(?:last|this) year\b|\bnow and before\b", re.I)
DEPENDENCY_KIND = "dependencies"
DEPENDENCY_HEAD = "**Dependencies · {name}** · from the dependency register"
DEPENDENCY_YEARS = " against its re-interview on {on}"
#: t393 (his look call "c: rows + gap line", 2026-10-11): a grouped list, never a table that scrolls
#: sideways at 390: each group a heading, its known rows a list, and one line for the rows whose
#: workaround the register does not state; r2: a group of one row is drawn like the others
DEPENDENCY_GROUP = "**{group}**"
DEPENDENCY_NAME = "**{resource}**{staff}"
DEPENDENCY_ROW = "{name}: {workaround} (owner: {owner})"
NOT_STATED_FOR = "- Not stated for: {owners}"
NOT_STATED_OWNER = "{names} (owner: {owner})"
#: t395: a dependency ask in a room on no activity yet: code's plain line, never a guessed table
NO_ACTIVITY_SAID = ("No activity is under way in this room yet, so there is no dependency table "
                    "to show. Name the activity, and nemo draws its table.")
THIS_YEAR_SAID = " This year: {said}"
THROUGH = "{box} (through {boxes})"
#: t486 (12_nemo_design's comma rule): a through-box whose name carries its own bracket
THROUGH_AFTER = "{box}, through {boxes}"
STAFF_SAID = "{normal} in normal operation, {emergency} in an emergency"
UP_DOWN = "Upstream: {up} · Downstream: {down} (the process map)"
NONE_NAMED = "none"
NO_CHANGE = "no change named"
NOT_IN_REGISTER = ("Not in the dependency register: the backup this year's interview names for "
                   "{resource}, “{said}” ({title}); no register row is its backup.")
#: r3: A6 shows only the rows with a this-year finding, and this one line for the rest. The
#: owner's choice of words (5_nemo_design_phone's read: r2's A6 was 44 rows, 8.3 screens at 390)
UNCHANGED_REST = "The other {n} register entries: the interview names no change."
BACKUP_WORDS = re.compile(r"\bbackup\b|\bstandby\b|\bsecond copy\b", re.I)
#: t427: the rows whose cell states there is none (404's "No workaround: …"), by the one stated
#: rule (`workspace.NO_WORKAROUND`, t330). 393 r2 dropped the line before it that listed the rows
#: not stated, which each group's `NOT_STATED_FOR` line already names (his "Drop the repeat")
NO_WORKAROUND_SAID = "The register states no workaround for: {names}."
NO_OWNER = "No owner named in the register: {names}."
NO_DEPUTY = "No deputy named for the {function}, its process owner (the organisation file)."
SPOF_NOTE = "Which of these is a single point of failure is yours to judge: the list says only " \
    "what the files state."
#: t488 (his D1, "3 plain lines + link", 2026-10-13): a dependency ask (A6, B6, any other) answers
#: in at most three short plain lines on what stands out, by code (`dependencies_short`), then one
#: link opening the room's graph page on the activity, in a new tab (Chainlit opens a turn's every
#: link so); the listing lives on the page, never in the chat. B5 keeps its own answer, the link
#: at its end. What changed this year is the interview's (`discrepancies`): a backup it names is
#: new, any other finding on a register row changed
GRAPH_LINK = "[Open the dependency graph]({link})"
SHORT_CHANGED = "Changed this year: {said}"
SHORT_NEW = "New this year: {said}"
NO_CHANGE_SAID = "This year's interview names no change to what it depends on."
#: t510 (14_nemo_design's wording, 475's what-changed sentence word for word): where the activity
#: has no interview since last year's record, A6 says so, never `NO_CHANGE_SAID`
NOT_COMPARED_SAID = ("{activity} has no interview since last year's record, so there is nothing "
                     "yet to compare it with.")
SHORT_NO_WORKAROUND = "{n} still {have} no backup plan in the register: {names}."
NONE_WITHOUT = "The register names nothing {name} depends on as having no backup plan."


def _owner_function(owner: Any) -> str:
    """t390: a register owner as a function: "Head of IT Operations (Marek Sobotta)" as "Head of
    IT Operations"; none named is `NOT_STATED`."""
    return re.sub(r"\s*\([^)]*\)$", "", str(owner or "")) or NOT_STATED


def dependency_groups(folder: Path, activity: str
                      ) -> list[tuple[str, list[tuple[dict[str, Any], dict[str, Any]]]]]:
    """t390: the rows of the activity's dependency table, group by group: the graph's boxes for it
    (`live_graph.g2`, its page data) level by level, then the entries it uses that the graph draws
    no box for, under the graph's own reason; each row a register entry and the activity's use of
    it (its consumers row, or {} where it rides in on a box). t389 r3: the briefing's rows too.
    t486: a box with a member that carries the activity's own consumer row is a direct need: no
    "through", listed with the first level; "through" only for a box reached solely via others."""
    import live_graph  # its page data; both import this module, so not at the top
    import merge_table
    register = drafting.read_register(folder)
    page = live_graph.g2(folder, register, activity)
    order = {c: n for n, c in enumerate(page["cols"])}
    keys = {a.get("name"): k for k, a in register.items() if isinstance(a, dict)}
    direct = {b for b, box in page["boxes"].items()
              if any(r.get("department") == activity for k in box["members"]
                     for r in register[k].get("consumers") or [])}
    groups = []
    for box in sorted(page["boxes"], key=lambda b: (1 if b in direct else page["levels"].get(b, 1),
                                                    order.get(page["boxes"][b]["col"], 0))):
        name = page["boxes"][box]["name"]
        over = [page["boxes"][a]["name"] for a, b in page["deps"] if b == box]
        groups.append(((THROUGH_AFTER if name.endswith(")") else THROUGH).format(
            box=name, boxes=_dot_listed(over)) if over and box not in direct else name,
            page["boxes"][box]["members"]))
    groups += [(rule, [keys[n] for n in names]) for rule, names in page["notDrawn"]
               if rule != merge_table.LINES_RULE]
    return [(group, [(register[k], next((r for r in register[k].get("consumers") or []
                                         if r.get("department") == activity), {}))
                     for k in members]) for group, members in groups]


def dependencies(folder: Path, activity: str) -> dict[str, Any]:
    """t601 (fact): what the activity depends on, as data: `dependency_groups`' rows group by group
    (each `resource`, its `owner` as a function, the `workaround` the register states for the
    activity, its staff figures), and the process map's line `upstream` and `downstream`."""
    here = next((r for r in process_map_rows(folder) if r.slug == activity), None)
    return {"groups": [{"group": group, "rows": [
        {"resource": str(a["name"]), "owner": _owner_function(a.get("owner_name")),
         "workaround": use.get("workaround"), "staff_normal": use.get("staff_normal"),
         "staff_emergency": use.get("staff_emergency")} for a, use in members]}
        for group, members in dependency_groups(folder, activity)],
        "upstream": list(here and here.upstream or ()),
        "downstream": list(here and here.downstream or ())}


def spof(folder: Path, activity: str) -> dict[str, Any]:
    """t601 (fact): the single-point-of-failure verdict for the activity, as data: each register
    row it uses (`resource`, the `workaround` it states, `flagged` by `workspace.flagged`, the one
    stated rule) and the `verdict`, any row flagged."""
    import workspace  # the flagged rule's module, which reads this one
    rows = [{"resource": str(a.get("name") or ""), "workaround": row.get("workaround"),
             "flagged": workspace.flagged(a, row)}
            for a in drafting.read_register(folder).values() if isinstance(a, dict)
            for row in a.get("consumers") or [] if row.get("department") == activity]
    return {"verdict": any(r["flagged"] for r in rows), "rows": rows}


def no_workaround(folder: Path, activity: str) -> set[str]:
    """604: the rows the register states no workaround for: those `spof` flags whose cell says so
    (an empty cell is flagged too, but states nothing). The one reading of "no workaround" the
    dependency answers, the briefing and the check stack share. The cell is read by the same rule,
    so an authored single source whose cell names a workaround is not one."""
    import workspace  # the flagged rule's module, which reads this one
    return {r["resource"] for r in spof(folder, activity)["rows"] if r["flagged"]
            and str(r["workaround"] or "").strip() and workspace.flagged({}, r)}


def no_workaround_cell(folder: Path, activity: str) -> set[str]:
    """649: the rows the register leaves without a workaround cell ("none stated"), never one of
    `no_workaround`'s, whose cell states none."""
    return {r["resource"] for r in spof(folder, activity)["rows"]
            if not str(r["workaround"] or "").strip()}


def risk_controls(folder: Path, activity: str) -> list[dict[str, str]]:
    """724 (fact): what the risk register says of the activity's resources, as data: for each
    resource `dependencies` lists, as the answer does, each risk row naming it in `Assets`, with
    the row's `id`, its `controls` (`Existing controls`), and its `risk`, `activities` and
    `marking`: a row may be about another activity's use of the resource. Empty with no file or no
    such row. It stands beside the dependency register's `workaround`; `spof` and `no_workaround`
    do not read it."""
    path = folder / drafting.RISK_REGISTER
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    head = next((_cells(x) for x in lines if x.startswith("| ID |")), [])
    rows = [dict(zip(head, _cells(x), strict=True)) for x in lines
            if x.startswith("| R-") and len(_cells(x)) == len(head)]
    if not rows:
        return []
    names = dict.fromkeys(r["resource"] for g in dependencies(folder, activity)["groups"]
                          for r in g["rows"] if r["resource"])
    return [{"resource": name, "id": row["ID"], "risk": row.get("Risk", ""),
             "activities": row.get("Activities", ""), "marking": row.get("Marking", ""),
             "controls": row.get("Existing controls", "")}
            for name in names for row in rows
            if name in {a.strip() for a in row.get("Assets", "").split(";")}]


def dependencies_said(folder: Path, activity: str, spof: bool = False,
                      years: bool = False) -> str:
    """t390 (A6, B5, B6): the activity's dependency table, by code: one row per register entry
    `dependency_groups` holds (the graph's boxes, level by level, the page data's): the
    entry with any staff figures, the workaround the register states for the activity or
    `NOT_STATED`, and its owner as a function; then the process map's line up- and downstream.
    t393: drawn as a grouped list, the rows it leaves open in one `NOT_STATED_FOR` line a group;
    r2: every list of names `_dot_listed`.
    `years` (A6) keeps only the rows this year's interview names, with its findings, counts the rest
    in one line (`UNCHANGED_REST`), and flags a backup it names that no register row is
    (`NOT_IN_REGISTER`); `spof` (B5) adds the rows stating no workaround (t427), those with no
    owner, and the process owner's missing deputy, read from the organisation file. Never the
    model's."""
    register = drafting.read_register(folder)
    found = discrepancies(folder, activity) if years else []
    head = DEPENDENCY_HEAD.format(name=process_name(folder, activity)) + (
        DEPENDENCY_YEARS.format(on=_day(held_on(found[0]["path"]))) if found else "")
    lines = [head]
    keys = {a.get("name"): k for k, a in register.items() if isinstance(a, dict)}
    stated = no_workaround(folder, activity)  # 604: `spof`'s
    none, unowned, rest = [], [], 0
    depends = dependencies(folder, activity)  # t601: its data
    for group in depends["groups"]:
        known, shown = [], []  # t393: the rows it states; the rows it leaves open, by owner
        gaps: dict[str, list[str]] = {}
        for row in group["rows"]:
            resource, owner, workaround = row["resource"], row["owner"], row["workaround"]
            staff = STAFF_SAID.format(normal=row["staff_normal"],
                                      emergency=row["staff_emergency"]) \
                if row["staff_normal"] and row["staff_emergency"] else ""
            if resource in stated:
                none.append(resource)
            if owner == NOT_STATED:
                unowned.append(resource)
            said = [d["said"] for d in found if d["resource"] == resource]
            if found and not said:  # r3: A6 names the rest in one line
                rest += 1
                continue
            name = DEPENDENCY_NAME.format(resource=resource, staff=f" ({staff})" if staff else "")
            shown.append(resource)
            if workaround or years:  # A6: each row its finding, stated or not
                known.append(DEPENDENCY_ROW.format(
                    name=name, workaround=workaround or NOT_STATED, owner=owner)
                    + (THIS_YEAR_SAID.format(said=" ".join(said) or NO_CHANGE) if years else ""))
            else:
                gaps.setdefault(owner, []).append(name)
        if shown:
            lines += ["", DEPENDENCY_GROUP.format(group=group["group"]),
                      *(f"- {k}" for k in known),
                      *([NOT_STATED_FOR.format(owners="; ".join(
                          NOT_STATED_OWNER.format(names=_dot_listed(n), owner=o)
                          for o, n in gaps.items()))] if gaps else [])]
    lines.append("")
    backed = {k for a in register.values() if isinstance(a, dict)
              for k in a.get("backup_for") or []}
    lines += [NOT_IN_REGISTER.format(resource=d["resource"], said=d["said"],
                                     title=file_title(folder, d["path"]))
              for d in found if d["resource"] and BACKUP_WORDS.search(d["said"])
              and keys.get(d["resource"]) not in backed]
    lines += [UNCHANGED_REST.format(n=rest)] if rest else []
    lines.append(UP_DOWN.format(up=_dot_listed(depends["upstream"]) or NONE_NAMED,
                                down=_dot_listed(depends["downstream"]) or NONE_NAMED))
    if spof:
        person = _no_deputy(folder, activity)
        lines += ["", *([NO_WORKAROUND_SAID.format(names=_dot_listed(sorted(none)))]
                        if none else []),
                  *([NO_OWNER.format(names=_dot_listed(unowned))] if unowned else []),
                  *([NO_DEPUTY.format(function=words.roles(folder)[person])]
                    if person and person in words.roles(folder) else []),
                  *(CARRIED_FOCUS.format(other=_said_name(folder, other), on=_day(held_on(
                      d["path"])), activity=_said_name(folder, activity),
                      resource=d["resource"], said=d["said"])
                    for other, d in carried(folder, activity)),
                  SPOF_NOTE]
    return "\n".join(lines)


def _findings_said(found: list[dict[str, Any]]) -> str:
    """t488: the interview's findings as one run of sentences, the first mid-line (`_said_name`'s
    rule: an acronym keeps its capitals). t510: so does a proper name, a first word its register
    row's name opens on ("Schlugge Lagerlogistik", never "schlugge")."""
    said = " ".join(d["said"] for d in found)
    named = found and str(found[0]["resource"] or "").startswith(said.split()[0])
    return said if named or said[1:2].isupper() else said[:1].lower() + said[1:]


def dependencies_short(folder: Path, activity: str, years: bool = False) -> str:
    """t488 (D1): what stands out in the activity's dependencies, in at most three plain lines, by
    code: with `years` (A6) what this year's interview changed (`SHORT_CHANGED`, or
    `NO_CHANGE_SAID`; t510: `NOT_COMPARED_SAID` where there is no interview since the record); the
    backup it names (`SHORT_NEW`); and the rows the register states no workaround for (t427's
    rule, through `spof`: 604), less those the interview gives a backup, by name and count."""
    found = [d for d in discrepancies(folder, activity) if d["resource"]]
    new = [d for d in found if BACKUP_WORDS.search(d["said"])]
    changed = [d for d in found if d not in new]
    backed = {d["resource"] for d in new}
    stated = no_workaround(folder, activity)
    none = sorted({row["resource"] for group in dependencies(folder, activity)["groups"]
                   for row in group["rows"] if row["resource"] in stated - backed})
    lines = [SHORT_CHANGED.format(said=_findings_said(changed))] if years and changed else []
    lines += [NO_CHANGE_SAID if this_years_path(folder, activity)
              else NOT_COMPARED_SAID.format(activity=map_name(folder, activity))] \
        if years and not found else []
    lines += [SHORT_NEW.format(said=_findings_said(new))] if new else []
    n = COUNTS[len(none)] if len(none) < len(COUNTS) else str(len(none))
    lines.append(SHORT_NO_WORKAROUND.format(n=n.capitalize(), have="has" if len(none) == 1
                                            else "have", names=_dot_listed(none)) if none
                 else NONE_WITHOUT.format(name=_said_name(folder, activity)))
    return "\n\n".join(lines)


#: t377 (C): his line asks for the analysis of an interview; in a walk nemo's answer leads with
#: what code found (`findings_said`)
FINDINGS_HEAD = "**What changed since last year · {name}** (its re-interview on {on})"
FINDING_SAID = "{n}. {said}"
#: t377 Q (377a F3): the interview by its plain title (`file_title`), never filename:line
THIS_YEAR = "   This year: {who}, “{quote}” ({title})"
#: t418 r2 (6_nemo_design_phone's 390 read): a quote from the interview the head names already
THIS_YEAR_HERE = "   This year: {who}, “{quote}”"
LAST_YEAR_ROW = "   Last year: {resource}, “{said}” (the dependency register, record {record})"
LAST_YEAR_MTPD = "   Last year: MTPD {mtpd} (record {record}{year})"
#: t377 Q (b): an impact finding's side, the record's own cells for the categories it names
LAST_YEAR_GRID = "   Last year: {said} (record {record}{year})"
#: t377 Q (b): a finding no class of last year's record answers (the owner's wording to choose)
LAST_YEAR_NONE = "   Last year: nothing on this in record {record}"
#: t377 Q (b): a finding that states a duration, which last year's MTPD answers
_DURATION = re.compile(r"\b(?:hours?|days?|weeks?)\b|\b\d+\s*h\b", re.I)


def _grid_said(rows: dict[str, Any], said: str) -> str:
    """t377 Q (b): the record's cells for each grid category `said` names, at the horizons it
    names (else every filled one): "financial none at 72 h and 168 h"; "" where it names none."""
    figures = _figures(said)
    out = []
    for name, row in rows.items():
        if not re.search(rf"\b{re.escape(name.split()[0])}\b", said, re.I):
            continue
        cells = [(h, v) for h, v in row["cells"].items() if v]
        cells = [(h, v) for h, v in cells if h.split()[0] in figures] or cells
        values = {v for _, v in cells}
        out.append(f"{name.lower()} {values.pop()} at {_listed([h for h, _ in cells])}"
                   if len(values) == 1 else
                   f"{name.lower()} {_listed([f'{v} at {h}' for h, v in cells])}")
    return "; ".join(out)


def findings_said(folder: Path, activity: str) -> str:
    """t377 (C): the activity's open `discrepancies`, each with both sources: this year's line
    of the interview, and last year's side: the register row's own workaround (else its need) for
    the activity where it names a resource, else the record's MTPD. Code's words only.
    t377 Q (b): last year's side is of the finding's own class: the record's grid where it names
    an impact category (`_grid_said`), else a row whose staff figures it states both, else its
    resource's row, else the MTPD where it states a duration, else `LAST_YEAR_NONE`. t418 r2:
    each line of a finding ends in a hard break, so none runs on at 390, and a quote names its
    interview only where the head does not (`THIS_YEAR_HERE`)."""
    found = discrepancies(folder, activity)
    if not found:
        return ""
    prior = last_year(folder, activity)
    record = prior.get("record", prior.get("ref", ""))
    rows = {str(a.get("name")): r for a in drafting.read_register(folder).values()
            if isinstance(a, dict) for r in a.get("consumers") or []
            if r.get("department") == activity}
    year = _year(str(prior.get("interview") or ""))
    year = f", {year}" if year else ""
    lines = [FINDINGS_HEAD.format(name=process_name(folder, activity),
                                  on=_day(held_on(found[0]["path"])))]
    for n, d in enumerate(found, 1):
        grid = _grid_said(prior.get("grid") or {}, d["said"])
        staffed = next((r for r in rows.values() if "staff_normal" in r
                        and {str(r["staff_normal"]), str(r.get("staff_emergency"))}
                        <= _figures(d["said"])), None)
        row = staffed or rows.get(d["resource"] or "", {})
        said = [FINDING_SAID.format(n=n, said=d["said"]),
                (THIS_YEAR_HERE if d["path"] == found[0]["path"] else THIS_YEAR).format(
                    who=d["speaker"], quote=d["quote"], title=file_title(folder, d["path"]))]
        if grid:
            said.append(LAST_YEAR_GRID.format(said=grid, record=record, year=year))
        elif row.get("workaround") or row.get("need"):
            resource = next(a for a, r in rows.items() if r is row)
            said.append(LAST_YEAR_ROW.format(resource=resource, record=record,
                                             said=row.get("workaround") or row["need"]))
        elif (prior.get("figures") or {}).get("MTPD") and _DURATION.search(d["said"]):
            said.append(LAST_YEAR_MTPD.format(mtpd=prior["figures"]["MTPD"], record=record,
                                              year=year))
        else:
            said.append(LAST_YEAR_NONE.format(record=record))
        lines.append("  \n".join(said))
    return "\n".join(lines)


#: t377 Q r2 (A2): the interview's words behind each finding, asked in his typed line ("Show the
#: interview quote behind each gap"); code answers from `discrepancies` with the block's own quote
#: line (`THIS_YEAR`): the participant's line, the words only, the speaker named once beside them
QUOTE_WORDS = re.compile(r"\bquotes?\b|\bwhere in the interview\b", re.I)
#: t450 (A2, prompt check run 2): the same ask in the words run 2's failing wordings used, which
#: `QUOTE_WORDS` misses; each arm for the wording that needs it, none from the held-back third
SAID_ASKED = re.compile(
    r"\bqoutes?\b"  # A2-20 "show interview qoute each gap": "quote" typed fast
    r"|\bverbatim\b"  # A2-10 "the verbatim statement from Monday's interview"
    r"|\bexact words\b|\bsay exactly\b"  # A2-02 "the exact words", A2-17 "say exactly?"
    r"|\bactually said\b"  # A2-12 "what the interviewee actually said"
    r"|\bwho said\b"  # A2-02 "and who said them"
    r"|\bevidence\b"  # A2-13 "Evidence for the gaps?"
    r"|\bstatements?\b.*\bsupport"  # A2-14 "Which statements in the interview support each gap?"
    r"|\bwords behind\b",  # A2-18 "The words behind the gaps?"
    re.I)
#: t450: what those words are about: the gaps ("each gap", "the gaps"), never a figure or a file
GAPS_NAMED = re.compile(r"\bgaps?\b", re.I)


def asks_for_quotes(line: str, after_changes: bool = False) -> bool:
    """t377 Q r2: his line asks for the interview's words behind the findings (`QUOTE_WORDS`).
    t450 (A2): or it asks for what was said (`SAID_ASKED`) about the gaps: his line names them
    (`GAPS_NAMED`), or nemo's last answer was the changes card (`after_changes`, A2-17's "What
    did they say exactly?")."""
    return bool(QUOTE_WORDS.search(line)) or bool(SAID_ASKED.search(line)) and bool(
        GAPS_NAMED.search(line) or after_changes)
#: t418 (6_nemo_design_phone's 390 read of Move 10): the source named once, for the block
#: (`words.DRAFT` keeps the block as said: no gloss inside it, 397's rule)
QUOTES_HEAD = "**What the interview says · {name}** ({title})"
#: t418: under each finding, its speaker by function (ADR-0051), then the quote on its own line,
#: each after a hard break
QUOTE_SAID = "   {who}:  \n   “{quote}”"


def said_by(folder: Path, person: str, role: str = "") -> str:
    """t418: a person as nemo names them, "<function> (<name>)": the organisation file's function
    (`words.people`), else the `role` given, its first part ("Head of Purchasing, process
    owner"); the name in brackets goes unless his line asks for names (`Session.turn`)."""
    function = words.people(folder).get(re.sub(r"^(?:Dr|Prof)\.? ", "", person)) \
        or role.split(",")[0].strip()
    return f"{function} ({person})" if function else person


def quotes_said(folder: Path, activity: str) -> str:
    """t377 Q r2: each open finding of the activity (`discrepancies`) and the interview line it
    came from. t418: the speaker by function (`said_by`), the quote on its own line (`QUOTE_SAID`),
    the interview named once, in the head; "" where it has none. t421: every line it carries
    (`quotes`), each by its own speaker. t515: the source in brackets drops the activity's name the
    heading carries ("Production and processing (re-interview of 9 Nov 2026)")."""
    if (found := quotes(folder, activity)) is None:
        return ""
    name = process_name(folder, activity)
    title = file_title(folder, found["path"])
    if title.lower().startswith(f"the {name.lower()} "):
        title = title[len(f"the {name} "):]
    lines = [QUOTES_HEAD.format(name=name, title=title)]
    for n, d in enumerate(found["found"], 1):  # t421: each line the finding carries, by speaker
        lines.append("  \n".join([FINDING_SAID.format(n=n, said=d["said"]), *(QUOTE_SAID.format(
            who=said_by(folder, q["speaker"], q["role"]), quote=q["quote"]) for q in d["quotes"])]))
    return "\n".join(lines)


def quotes(folder: Path, activity: str) -> dict[str, Any] | None:
    """t601 (fact): the interview's words behind each open finding of the activity
    (`discrepancies`), as data: the interview (`path`) and each finding's `said` with its `quotes`
    (`line`, `speaker`, the speaker's `role` on its Participants line, `quote`). None where it has
    none."""
    found = discrepancies(folder, activity)
    if not found:
        return None
    roles = dict(participants((folder / found[0]["path"]).read_text(encoding="utf-8")))
    return {"path": found[0]["path"],
            "found": [{"said": d["said"], "quotes": [{**q, "role": roles.get(q["speaker"], "")}
                                                     for q in d["quotes"]]} for d in found]}


#: t377 (B2): what "Invite to the interview" does, said when his line asked for the invitation,
#: in code's words from 373's own reads (`invitees`, `interview_slot`). t389 (B8): the plan's day
#: at the slot's hour and no other time or place; the attendees by function, a name only in its
#: brackets (his "Everywhere"); r2: it is the whole answer, the model's text dropped whole. t468:
#: it names whose re-interview it is, which need not be the activity open
INVITE_SAID = ("“{tap}” puts one invitation to {people} into the demo mailbox's Drafts, for "
               "{name}'s re-interview on {when}, with the calendar file and the questionnaire "
               "attached, and blocks the time in nemo's calendar. Nothing is sent.")


def invite_tap_said(folder: Path, activity: str, text: str) -> tuple[str, list[str]]:
    """t377 (B2): `INVITE_SAID`, and the model's paragraphs dropped, for the turn file. t389 r2:
    every one of them, never a filter of its words (r1's let invented ones through)."""
    start = (interview_slot(folder, activity) or (None, None))[0]
    line = INVITE_SAID.format(
        tap=INVITE_TAP, people=_listed([f"the {role.split(',')[0]} ({p})"
                                        for p, role, _ in invitees(folder, activity)]),
        name=_said_name(folder, activity),
        when=f"{start:%A}, {start.day} {start:%B}, {start:%H:%M}" if start else "the planned day")
    return line, [p for p in text.split("\n\n") if p.strip()]


#: t371 (30_nemo_check's ruling T3): a follow-up row as its draft says it, no code and no hour
#: grid: the item in fixed plain words, its figure as words, the point as the row says it. Code's
#: words only (M13). A row is walk's "<resource>, <item>: <words>", the item `REFER_ITEM`'s or
#: `REFER_NOTE`'s where nemo drew it.
PLAIN_ITEMS = {"RTO": "how soon we need to have it back", "RPO": "how much data we could lose",
               "MTPD": "how long we can manage without it", "workaround": "how we work without it"}
PLAIN_UNTIL = {"RTO": "within ", "RPO": "up to "}
PLAIN_WHEN = {"last year": "last year we said {value}", "now": "today's record says {value}"}
PLAIN_ROW = re.compile(r"(?P<item>.+?)(?P<of> for .+?)?"
                       r"(?: \((?P<when>last year|now): (?P<value>[^)]*)\))?: (?P<point>.*)", re.S)


def _hours_said(value: str, until: str) -> str:
    """t371: "72 h" as "within 3 days" (`until` before a bare figure), "<24 h" as "less than a
    day", ">168 h" as "more than a week"; `NOT_STATED` as "nothing yet", any other value as is."""
    found = re.fullmatch(r"([<>]?)\s*(\d+)\s*h", value.strip())
    if not found:
        return "nothing yet" if value == NOT_STATED else value
    hours = int(found[2])
    unit, count = next((unit, hours // span) for unit, span in
                       (("week", 168), ("day", 24), ("hour", 1)) if hours >= span and not
                       hours % span or span == 1)
    said = f"a{'n' * (unit == 'hour')} {unit}" if count == 1 else f"{count} {unit}s"
    return {"<": "less than ", ">": "more than "}.get(found[1], until) + said


def plain_row(row: str, resource: str) -> str:
    """t371 (rulings T3, T4): `row`, referred to `resource`'s owner, as the draft says it: its
    item in `PLAIN_ITEMS`' words, a figure as words (`_hours_said`), sentence case; no "(last
    year …)" where the value is a register's authored words (`merge_table.MARK`)."""
    import merge_table  # here: merge_table imports workspace, which imports this module
    head = f"{resource}, "
    said = PLAIN_ROW.fullmatch(row.removeprefix(head)) if row.startswith(head) else None
    if said:
        item = said["item"]
        value = _hours_said(said["value"] or "", PLAIN_UNTIL.get(item, ""))
        # 5_nemo_design's read of 2c2c1251: an authored item has no prior record to quote
        authored = (said["value"] or "").startswith(merge_table.MARK)
        when = (f" ({PLAIN_WHEN[said['when']].format(value=value)})"
                if said["when"] and not authored else "")
        row = f"{head}{PLAIN_ITEMS.get(item, item)}{said['of'] or ''}{when}: {said['point']}"
    return row[:1].upper() + row[1:]


def write_follow_up(folder: Path) -> None:
    """t256: the follow-up list (`follow_up`), grouped by recipient, one row each."""
    grouped: dict[str, list[str]] = {}
    for to, _, said in follow_up(folder):
        grouped.setdefault(to, []).append(said)
    write_file(folder, FOLLOW_UP, "\n\n".join(
        [FOLLOW_UP_HEAD, *(f"## {to}\n\n" + "\n".join(f"- {r}" for r in refers)
                           for to, refers in sorted(grouped.items()))]) + "\n")


def _name_words(text: str) -> str:
    """A line or a name as `named_in` compares it: `_map_key`'s, its words alone, space-padded."""
    return " " + " ".join(re.findall(r"\w+", _map_key(text))) + " "


class Asked(NamedTuple):
    """t329: what his typed line asks nemo's code for: 314's chart, 259's slides, or both."""

    chart: bool
    slides: bool


def asked_for(line: str) -> Asked:
    """t314, t329: the one matcher. The chart where his line names it or the impact over time
    (`CHART_WORDS`), the slides where it names slides or a presentation (`SLIDES_WORDS`); "a
    presentation of the impact over time" is both."""
    return Asked(bool(CHART_WORDS.search(line)) and not NOT_THIS_CHART.search(line),
                 bool(SLIDES_WORDS.search(line)) and not NOT_THESE_SLIDES.search(line))


def asks_for_chart(line: str) -> bool:
    """t314: his line asks for the impact chart in plain words (`CHART_WORDS`)."""
    return asked_for(line).chart


class ResourceView(NamedTuple):
    """t485: a resource's dependency view: its name, the Whole company box the graph page draws it
    in and code's lines on it (the page's link is the session's, `Session.page_link`)."""

    name: str
    box: str
    said: str


def resource_view(folder: Path, line: str) -> ResourceView | None:
    """t485: the resource of the register his line names by its whole name (the longest first),
    as the graph page draws it: its Whole company box (never a People box, 467's), the activities
    that need it and the boxes it stands on, read from the page's data (`live_graph.data`). None
    where his line names an activity (`named_in`, `loosely_named`) or no drawn resource."""
    if named_in(folder, line) or loosely_named(folder, line):
        return None
    register = drafting.read_register(folder)
    if not register:
        return None
    import live_graph  # its page data; it imports this module, so not at the top
    data = live_graph.data(folder)
    boxes = {k: b for k, b in data["whole"]["boxes"].items() if not k.startswith("people")}
    rows = sorted(((i, r) for i, r in register.items() if isinstance(r, dict) and r.get("name")),
                  key=lambda ir: -len(str(ir[1]["name"])))
    for i, row in rows:
        name = str(row["name"])
        drawn = [k for k, b in boxes.items() if i in b["members"]]
        if drawn and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", line, re.I):
            box = drawn[0]
            needed = [map_name(folder, a) for a in boxes[box]["neededBy"]]
            on = [boxes[d]["name"] for b, d in data["whole"]["deps"] if b == box and d in boxes]
            owner = words.functions_only(str(row.get("owner_name") or ""), folder)
            n, of = len(needed), str(boxes[box]["name"])
            count = f"{n} {'activity' if n == 1 else 'activities'}"
            if of != name:  # r2: drawn in a merged box of another name, so the box is named
                facts = [RESOURCE_IN_BOX.format(name=name, box=of, n=count, names=", ".join(
                    needed)) if needed else RESOURCE_IN_BOX_NONE.format(name=name, box=of),
                         RESOURCE_BOX_ON.format(names=", ".join(on)) if on else "",
                         RESOURCE_OWNER_OF.format(name=name, owner=owner) if owner else ""]
            else:
                facts = [RESOURCE_NEEDED.format(name=name, n=count, names=", ".join(needed))
                         if needed else RESOURCE_NONE.format(name=name),
                         RESOURCE_ON.format(names=", ".join(on)) if on else "",
                         RESOURCE_OWNER.format(owner=owner) if owner else ""]
            return ResourceView(name, box, "\n\n".join(filter(None, facts)))
    return None


#: t377 D1 (v7-01): which BIAs are due for review, asked in his typed line (`asks_which_due`): a
#: due or overdue with a BIA or a review in the same line. nemo answers it itself from the BIA
#: programme plan (`due_reviews`), never by the model's tool choice; a payment due is not it.
DUE_WORDS = re.compile(r"\b(?:over)?d(?:ue|eu)\b", re.I)
DUE_ABOUT = re.compile(r"\bBIAs?\b|\breview", re.I)
#: t433 (B1): or a BIA with its review, its backlog or doing it again, in one sentence
DUE_REVIEW = re.compile(r"\bBIAs?\b[^.?!]*\b(?:review\w*|backlog|again)\b"
                        r"|\b(?:review\w*|backlog)\b[^.?!]*\bBIAs?\b", re.I)
DUE_HEADING = "**BIAs due for review** · from the BIA programme plan{as_of}"
DUE_LINE = ("- **{process}** (record {record}, owner {owner}): last BIA {last}, review due {due}; "
            "{status}")
DUE_NONE = "None is due for review."
DUE_OTHERS = "The other {n} were reviewed in {years}."
_PLAN_ROW = re.compile(r"^\|\s*\d+\.\d+\s*\|.*\|\s*$", re.M)
_PLAN_AS_OF = re.compile(r"\bAs of ([^.\n]+)")
_PLAN_DUE = re.compile(r"(?:over)?due\b", re.I)
_PLAN_DATE = re.compile(r"\b\d{1,2} [A-Z][a-z]{2} (\d{4})\b")


def asks_which_due(line: str) -> bool:
    """t377 D1: his line asks which BIAs are due for review (`DUE_WORDS` beside `DUE_ABOUT`);
    t433 (B1): or names a BIA's review, backlog or doing it again (`DUE_REVIEW`) and asks no
    which next (`NEXT_WORDS`)."""
    return bool(DUE_WORDS.search(line)) and bool(DUE_ABOUT.search(line)) \
        or bool(DUE_REVIEW.search(line)) and not NEXT_WORDS.search(line)


def due_reviews(folder: Path) -> str | None:
    """t377 D1: the plan's due list, drawn by code from `PROGRAMME_PLAN`: each row whose status
    opens with due or overdue, with its last BIA and due dates, then the years the others were
    reviewed in, read from their status. None where the room has no plan or its table is empty.
    t601: from `due`'s data."""
    if (found := due(folder)) is None:
        return None
    as_of = found["as_of"]
    lines = [DUE_HEADING.format(as_of=f", as of {as_of}" if as_of is not None else ""), ""]
    lines += [DUE_LINE.format(**r) for r in found["due"]] or [DUE_NONE]
    others = _others_said(found)
    return "\n".join([*lines, *(["", others] if others else [])])


#: t601: a programme plan row's six cells, by what each holds
PLAN_KEYS = ("record", "process", "owner", "last", "due", "status")


def _due(rows: list[list[str]]) -> list[list[str]]:
    """t601: the one due rule: the plan's rows whose status opens with due or overdue."""
    return [r for r in rows if _PLAN_DUE.match(r[5])]


def due(folder: Path) -> dict[str, Any] | None:
    """t601 (fact): the due reviews, as data: the plan's "as of" day, its rows due or overdue
    (`_due`), each by `PLAN_KEYS`, how many others it holds, and the years their status names.
    None where the room has no plan or its table is empty."""
    text, rows = _plan_table(folder)
    if not rows:
        return None
    due_ = _due(rows)
    as_of = _PLAN_AS_OF.search(text)
    return {"as_of": as_of.group(1) if as_of else None,
            "due": [dict(zip(PLAN_KEYS, r[:6], strict=True)) for r in due_],
            "others": len(rows) - len(due_), "years": _reviewed_in(rows, due_)}


def _others_said(found: dict[str, Any]) -> str:
    """t377 D1: `DUE_OTHERS` on the rows not due with the years their status names ("" where
    every row is due or no status names a year)."""
    return DUE_OTHERS.format(n=found["others"], years=" and ".join(found["years"])) \
        if found["others"] and found["years"] else ""


def _reviewed_in(rows: list[list[str]], due_: list[list[str]]) -> list[str]:
    """t377 D1: the years the status of the rows not due names."""
    return sorted({m.group(1) for r in rows if r not in due_
                   for m in [_PLAN_DATE.search(r[5])] if m})


def _due_and_others(rows: list[list[str]]) -> tuple[list[list[str]], str]:
    """t377 D1: the plan's rows due or overdue (`_due`), and `DUE_OTHERS` on the rest
    (`_others_said`). t459: the programme line (`programme_line`) says the same, from the same
    rows."""
    due_ = _due(rows)
    return due_, _others_said({"others": len(rows) - len(due_), "years": _reviewed_in(rows, due_)})


#: t459 r2 (M13): a count of the BIA programme in a model sentence: a count before BIAs, reviews
#: or (re-)interviews, or before "were reviewed" or "re-interviewed" ("Three of the five core
#: processes were re-interviewed"). Plain "interviews" count only beside a year, a cycle or
#: "fresh" in the same clause (`_CYCLE_SAID`): an activity's own "four interviews" is no claim.
#: Its figure is compared with the plan's (`_programme_confirms`), never judged by its shape.
_COUNT = (r"(?:\d{1,3}(?![.,:]\d)|none|no|all|every|"
          + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + ")")
PROGRAMME_CLAIM = re.compile(
    rf"\b(?P<n>{_COUNT})\b(?P<mid>(?:\s+[\w'’-]+){{0,3}}?)\s+"
    r"(?P<noun>BIAs|reviews|re-?interviews|interviews)\b"
    rf"|\b(?P<n2>{_COUNT})\b(?P<mid2>(?:\s+[\w'’-]+){{0,5}}?)\s+"
    r"(?:were|was|have been|has been|had been)\s+(?:re-?)?(?:reviewed|interviewed)\b", re.I)
_CYCLE_SAID = re.compile(r"\b20\d\d\b|\bcycle\b|\bfresh\b", re.I)
#: t459 r2: a claim is read in its clause (the sentence cut at ";", a dash or ": "), and the plan's
#: counts it may equal are the ones its clause speaks of: re-interviews held but not analysed,
#: reviews due, reviews done, or else the cycle's interviews (`_plan_counts`)
_CLAUSE = re.compile(r";|\s[—–]\s|:\s")
_SAID_OPEN = re.compile(r"\bnot (?:yet )?analy[sz]ed|\bunanaly[sz]ed|\bno record yet"
                        r"|\bnot yet updated|\bwait\w* for analysis", re.I)
_SAID_DUE = re.compile(r"\b(?:over)?due\b", re.I)
_SAID_REVIEWED = re.compile(r"\breviewed\b", re.I)
#: t459 r2: the day and month of a re-interview or a review, said right after it ("re-interview
#: held Mon 9 Nov", "reviewed 2 Oct") or right before ("the 1 Oct 2026 re-interview"): the plan
#: must name it. A day near no such word (a dry run, next week) is no programme date.
_SAID_DATED = re.compile(r"\b(?i:re-?interview\w*|reviewed)\W+(?:[\w'’]+\W+){0,4}?"
                         r"(?:[A-Z][a-z]{2} )?(\d{1,2}) ([A-Z][a-z]{2})\b"
                         r"|\b(\d{1,2}) ([A-Z][a-z]{2})(?: \d{4})? (?i:re-?interview)")
_DAY_MONTH = re.compile(r"\b(\d{1,2}) ([A-Z][a-z]{2})\b")
_PLAN_REINTERVIEW = re.compile(r"\bre-?interview\b", re.I)
_PLAN_OPEN = re.compile(r"\bnot yet\b", re.I)
PROGRAMME_LINE = "{n} {are} {late} for review"
#: t459: what a dropped claim's place keeps: its bullet or number, and a bold label closing on
#: "." or ":" ("- **The other re-interviews.** …"), a label that is no claim itself
_LEAD = re.compile(r"\s*(?:(?:\d+[.)]|[-*•])\s+)?(?:\*\*[^*]+[.:]\*\*\s+|\*\*[^*]+\*\*[.:]\s+)?")


def _plan_counts(rows: list[list[str]]) -> dict[str, set[int]]:
    """t459 r2: the counts a programme claim may equal, by code from the plan's status column: the
    re-interviews held and not yet analysed ("open"); the reviews due, and of them those whose
    re-interview is held or not ("due"); the reviews done ("reviewed"); the re-interviews held,
    due or not, the records in all, and with the re-interviews held the interviews in all
    ("cycle")."""
    due = _due(rows)
    held = [r for r in rows if _PLAN_REINTERVIEW.search(r[5]) and not _PLAN_PLANNED.search(r[5])]
    both = [r for r in held if r in due]
    return {"open": {sum(bool(_PLAN_OPEN.search(r[5])) for r in held)},
            "due": {len(due), len(both), len(due) - len(both)},
            "reviewed": {len(rows) - len(due)},
            "cycle": {len(held), len(both), len(held) - len(both), len(rows),
                      len(rows) + len(held)}}


def _counted(n: str, mid: str, total: int) -> int:
    """t459 r2: a claim's figure: "none" or "no" is 0, "all" or "every" the figure after it (as
    "all three") or every record; a number in words (`_NUMBER_WORDS`) or digits as it reads."""
    n = n.lower()
    if n in ("all", "every"):
        inner = re.search(rf"\b(?!all\b|every\b|none\b|no\b){_COUNT}\b", mid, re.I)
        return _counted(inner[0], "", total) if inner else total
    return 0 if n in ("none", "no") else int(_NUMBER_WORDS.get(n, n))


def _programme_confirms(sentence: str, plan: str, rows: list[list[str]]) -> bool:
    """t459 r2 (M13): every programme count in `sentence` (`PROGRAMME_CLAIM`) equals one the plan
    gives for what its clause speaks of (`_plan_counts`), and every day and month said of a
    re-interview or a review (`_SAID_DATED`) is one the plan names. A count where the room has no
    plan is never confirmed."""
    counts = _plan_counts(rows) if rows else {}
    for clause in _CLAUSE.split(sentence):
        for m in PROGRAMME_CLAIM.finditer(clause):
            if (m["noun"] or "").lower() == "interviews" and not _CYCLE_SAID.search(clause):
                continue  # an activity's own interviews
            said = "open" if _SAID_OPEN.search(clause) else "due" if _SAID_DUE.search(clause) \
                else "reviewed" if _SAID_REVIEWED.search(clause) else "cycle"
            if _counted(m["n"] or m["n2"], m["mid"] or m["mid2"] or "", len(rows)) \
                    not in counts.get(said, set()):
                return False
    dated = {(m[1] or m[3], m[2] or m[4]) for m in _SAID_DATED.finditer(sentence)}
    return not rows or dated <= set(_DAY_MONTH.findall(plan))


def programme_line(folder: Path) -> str | None:
    """t459 r2 (c): the BIA programme in one short line, counted by code from `PROGRAMME_PLAN` as
    B1's due list reads it (`_plan_table`, `_due_and_others`): how many reviews are overdue (or
    due), then the others and the years they were reviewed in. The due list is B1's alone. None
    where the room has no plan or its table is empty. t601: from `due`'s data."""
    if (found := due(folder)) is None:
        return None
    rows, others = found["due"], _others_said(found)
    if not rows:
        return " ".join(filter(None, [DUE_NONE, others]))
    said = PROGRAMME_LINE.format(n=len(rows), are="BIA is" if len(rows) == 1 else "BIAs are",
                                 late="overdue" if all(r["status"].lower().startswith("overdue")
                                                       for r in rows) else "due")
    return f"{said}; {others[:1].lower()}{others[1:]}" if others else f"{said}."


#: t459 r2 (b): what he still has to check himself, asked in his typed line (A9, B9)
CHECK_WORDS = re.compile(r"\b(?:check|verify|look into)\b", re.I)


def asks_about_programme(line: str) -> bool:
    """t459 r2 (b): his line is a programme turn: which BIAs are due (B1, `asks_which_due`), which
    to do next (B2, `asks_which_next`), or what to check himself (A9, B9: `CHECK_WORDS`)."""
    return asks_which_due(line) or asks_which_next(line) or bool(CHECK_WORDS.search(line))


def drop_programme_claims(text: str, folder: Path, programme: bool = False
                          ) -> tuple[str, list[str]]:
    """t459 r2 (M13): (the model's text without each sentence whose programme count or date the
    plan does not confirm (`_programme_confirms`); those sentences). In a programme turn
    (`asks_about_programme`) the plan's short line (`programme_line`) stands where the first one
    stood, its lead kept (`_LEAD`); elsewhere, or where the room has no plan, nothing does."""
    plan, rows = _plan_table(folder)

    def unconfirmed(sentence: str) -> bool:
        return not _programme_confirms(sentence, plan, rows)

    first = next((x for line in text.split("\n") for x in _sentences(line) if unconfirmed(x)),
                 None)
    line = programme_line(folder) if first and programme else None
    if first is None or line is None:
        return _drop_sentences(text, unconfirmed) if first else (text, [])
    lead = _LEAD.match(first)[0]  # type: ignore[index]  # every part optional: it always matches
    lead = "" if unconfirmed(lead) else lead
    kept, dropped = _drop_sentences(text.replace(first, "￼", 1), unconfirmed)
    return kept.replace("￼", lead + line, 1), [first[len(lead):].strip(), *dropped]


#: t377 H1 (v7-08): which BIA to do next, asked in his typed line (`asks_which_next`): "which BIA"
#: with next or "should I do"; never a due question (`asks_which_due`'s). nemo answers it itself
#: from the BIA programme plan (`next_bia`); the model's words, a room-state sheet too, are dropped.
#: t470 (router report R1, B2): or next and one BIA in one sentence, either way round ("Next week's
#: BIA?", "the BIA I should run next week"), or what to do next week. "BIAs" (a due list) is not it
NEXT_WORDS = re.compile(r"\bwhich BIA\b[^?.!]*\b(?:next|should I do)\b|\bnext\b[^?.!]*\bBIA\b"
                        r"|\bBIA\b[^?.!]*\bnext\b|\bwhat do I do next week\b", re.I)
#: t377 H1, H2: the turn file's `code_said`, naming which of code's answers stood for the model's
NEXT_KIND, DOWN_KIND, KEPT_KIND, QUOTES_KIND = "next_bia", "down_for", "kept", "quotes"
NEXT_HEAD = "**Next: {process}** · from the BIA programme plan{as_of}"
#: t487 (B2): why its review is due, from the plan's row as the briefing's "Why now" reads it
#: (`briefing_facts`), the cycle in the plan's own words (`_PLAN_CYCLE`), and the day the plan
#: schedules it for, never a reason for that day (the plan gives none)
NEXT_DUE = ("- Its review was due on {due}, {cycle}after the last interview on {last}, so it is "
            "{status}.")
NEXT_SCHEDULED = " The programme plan schedules it for {day}."
NEXT_PLANNED = "- Re-interview with {owner}, its process owner."
_PLAN_CYCLE = re.compile(r"\bA review is due (\d+ \w+) after its last interview\b")
NEXT_FEEDS = "- It feeds {feeds} (the process map), so its figures come first."
#: t412 (B2, 399 r2's run): each other review due whose re-interview is held, why not it, with
#: the day and state the plan gives (`_PLAN_HELD_ON`)
NEXT_HELD = "- Not {name}: its re-interview was held {day}{state}."
_PLAN_HELD_ON = re.compile(r"\bheld (?:on )?(?P<day>[^,;]+)(?P<state>[,;][^;]*)?")
_PLAN_PLANNED = re.compile(r"\bplanned for ([^;.]+)")
_PLAN_HELD = re.compile(r"\bheld\b", re.I)


def _plan_day(said: str) -> datetime.date:
    """t377 H1: a plan date ("13 Feb 2026", "Tue 17 Nov 2026"); the latest day where none."""
    found = _PLAN_DATE.search(said)
    return datetime.datetime.strptime(found[0], "%d %b %Y").date() if found else \
        datetime.date.max


def asks_which_next(line: str) -> bool:
    """t377 H1: his line asks which BIA to do next (`NEXT_WORDS`), and is no due question."""
    return bool(NEXT_WORDS.search(line)) and not asks_which_due(line)


def _plan_table(folder: Path) -> tuple[str, list[list[str]]]:
    try:
        text = (folder / PROGRAMME_PLAN).read_text(encoding="utf-8")
    except OSError:
        return "", []
    return text, [r for r in map(_cells, _PLAN_ROW.findall(text)) if len(r) >= 6]


_PLAN_CONFIRMED = re.compile(r"\breviewed and confirmed (\d{1,2} [A-Z][a-z]{2} \d{4})\b")


def no_scores_line(folder: Path, activity: str) -> str:
    """t517: the line under the title of `activity`'s chart with no scores this year, by its plan
    row's Status: the day its re-interview is planned for (`CHART_PLANNED`), or the day its record
    was reviewed and confirmed (`CHART_CONFIRMED`); `CHART_NO_SCORES` where it states neither, or
    where the activity has an interview this year, whatever its Status says (keyed on it first)."""
    name = map_name(folder, activity)
    if this_years_path(folder, activity):
        return CHART_NO_SCORES.format(activity=name)
    said = next((r[5] for r in _plan_table(folder)[1] if _map_key(r[1]) == _map_key(name)), "")
    if (planned := _PLAN_PLANNED.search(said)) and (day := _PLAN_DATE.search(planned[1])):
        return CHART_PLANNED.format(activity=name, date=day[0])
    if found := _PLAN_CONFIRMED.search(said):
        return CHART_CONFIRMED.format(activity=name, date=found[1])
    return CHART_NO_SCORES.format(activity=name)


def _next_row(folder: Path) -> tuple[str, list[list[str]], list[str]] | None:
    """t377 H1: the plan's text, its due rows and the row to do next: of the rows due or overdue,
    the one whose status names a planned re-interview, the earliest planned day first; else the
    earliest due with no interview held. A row whose re-interview is held is never it, however
    early it was due. None where the plan has no such row."""
    text, rows = _plan_table(folder)
    due = _due(rows)
    planned = [(_plan_day(said[1]), r) for r in due if (said := _PLAN_PLANNED.search(r[5]))]
    open_ = [(_plan_day(r[4]), r) for r in due if not _PLAN_HELD.search(r[5])]
    if not (planned or open_):
        return None
    return text, due, min(planned or open_, key=lambda p: p[0])[1]


def next_bia_activity(folder: Path) -> str | None:
    """t377i: the room's activity `next_bia` names (`_next_row`'s process), else None."""
    found = _next_row(folder)
    return next((a for a in walk.processes(folder) if found and
                 _map_key(process_name(folder, a)) == _map_key(found[2][1])), None)


def next_bia(folder: Path) -> str | None:
    """t377 H1: the BIA to do next, by code from `PROGRAMME_PLAN` (t601: `next_review`'s data). Its
    due and last BIA dates, the planned day with its process owner, and what it feeds on the
    process map. None where the plan has no such row. t487: the dates as why its review is due
    (`NEXT_DUE`), with the plan's cycle where it states one, and the planned day without the
    story's own year."""
    if (found := next_review(folder)) is None:
        return None
    as_of, cycle, day = found["as_of"], found["cycle"], found["planned"]
    lines = [NEXT_HEAD.format(process=found["process"],
                              as_of=f", as of {as_of}" if as_of is not None else ""), "",
             NEXT_DUE.format(status=found["status"].split(";")[0].strip().lower(),
                             due=found["due"], last=found["last"],
                             cycle=f"{cycle} " if cycle is not None else "")
             + (NEXT_SCHEDULED.format(day=day) if day is not None else ""),
             *([NEXT_PLANNED.format(owner=found["owner"])] if day is not None else [])]
    if found["feeds"]:
        lines.append(NEXT_FEEDS.format(feeds=_listed([d[:1].lower() + d[1:]
                                                      for d in found["feeds"]])))
    if found["held"]:
        lines += ["", *(NEXT_HELD.format(name=h["process"][:1].lower() + h["process"][1:],
                                         day=h["day"], state=h["state"]) for h in found["held"])]
    return "\n".join(lines)


def next_review(folder: Path) -> dict[str, Any] | None:
    """t601 (fact, "next_bia"): the BIA to do next (`_next_row`), as data: its plan row by
    `PLAN_KEYS`, the plan's "as of" day and cycle, the day its re-interview is planned for (without
    the story's own year; None where none is), what it feeds on the process map, and each other
    review due whose re-interview is held, with the day and state the plan gives. None where the
    plan has no such row."""
    if (found := _next_row(folder)) is None:
        return None
    text, due_, row = found
    own = next((r for r in process_map_rows(folder) if _map_key(r.name) == _map_key(row[1])),
               None)
    as_of, cycle = _PLAN_AS_OF.search(text), _PLAN_CYCLE.search(text)
    said, today = _PLAN_PLANNED.search(row[5]), story_today(folder)
    return {**dict(zip(PLAN_KEYS, row[:6], strict=True)), "as_of": as_of[1] if as_of else None,
            "cycle": cycle[1] if cycle else None,
            "planned": said[1].strip().removesuffix(f" {today.year}" if today else "")
            if said else None,
            "feeds": list(own.downstream or ()) if own else [],
            "held": [{"process": r[1], "day": m["day"].strip(),
                      "state": (m["state"] or "").rstrip(". ")}
                     for r in due_ if r is not row and (m := _PLAN_HELD_ON.search(r[5]))]}


#: t377 D2 (g1-2, g2-3): an analysis of an interview, asked in his typed line (`asks_to_analyse`):
#: analyse, what does not match, or what differs. Outside a walk such a turn opens no walk (D2b:
#: `NOT_ON_ANALYSIS` are neither offered nor run) and its answer leads with what code read from
#: the re-BIA interview's own summary (`changes_block`), the model's words after it.
ANALYSE_WORDS = re.compile(r"\banaly[sz]\w*|\b(?:doesn'?t|does not|didn'?t|did not) match|\bdiffer",
                           re.I)
NOT_ON_ANALYSIS = ("list_activities", "open_activity")
NOT_ON_ANALYSIS_SAYS = ("he asked for an analysis, not to start a BIA: answer it in this chat; the "
                        "walk opens from his pick")
#: t377p: a model's walk step on an activity the walk is not on, as the model reads it
OTHER_ACTIVITY_SAYS = ("the walk is on {walk}; {named}'s BIA opens only when he taps it or asks to "
                       "start it. Answer about {named} in this chat, from the files")
#: the line a 2026 re-BIA interview closes on, the interviewer's summary of what changed
#: t377 D2 reads `SUMMED_UP` (above, 377b's, with named groups) for its "said" group
SUMMED_UNCHANGED = re.compile(r"\bunchanged\b|\bas last year\b", re.I)
SUMMED_SKIP = re.compile(r"^(?:thank you|\w+ things? changed)\.?$", re.I)
#: t430: a no-break space before the "·", so a wrap never starts a line with it
CHANGES_HEADING = "**What changed since last year's record**\u00a0· {who}'s interview of {date}"
CHANGES_UNCHANGED = "**Not changed:**"
#: t377 N4 (g1-2): the categories whose impact the interview leaves as last year's record has it
CHANGES_SAME_GRID = "{categories}: impact as in last year's record (record {record})."
#: t412 (A1, run 7): the block's last line, what matters: the change moving the MTPD (`_matters`)
CHANGES_MATTERS = "**What matters:**"
MATTERS_SAYS = ("{matters} {cause}{lenses} impact reaches {level} at {horizon}, which takes the "
                "MTPD from {was} (record {record}: {figure}) to about {now} ({horizon}).")


def asks_to_analyse(line: str) -> bool:
    """t377 D2: his line asks for an analysis or a comparison of an interview (`ANALYSE_WORDS`)."""
    return bool(ANALYSE_WORDS.search(line))


#: t433 (A1): what changed, asked in other words (a comparison, a diff, deltas, deviations, one
#: thing against another); a line asking how long an activity can be down is A4's, never this
CHANGED_WORDS = re.compile(r"\bchang\w*|\bdiff\w*|\bcompar\w*|\bdeviat\w*|\bdeltas?\b|\bvs\.?\b"
                           r"|\bversus\b", re.I)
DURATION_ASKED = re.compile(r"\bhow long\b|\blongest\b|\bdown\b|\bdowntime\b|\bMTPD\b|\bRTO\b"
                            r"|\btolerable\b|\bstand still\b|\boutage\b", re.I)
#: t433 (A5): the word that keeps a "does not match" line an analysis (t377 D2), not code's list
ANALYSIS_ASKED = re.compile(r"\banaly[sz]\w*", re.I)


def asks_what_changed(line: str) -> bool:
    """t433 (A1): his line asks what changed (`CHANGED_WORDS`), and not for how long
    (`DURATION_ASKED`)."""
    return bool(CHANGED_WORDS.search(line)) and not DURATION_ASKED.search(line)


#: t507 (A9): what he should still check himself, in his words: a check, a verification or a
#: look that falls to him ("I", "me", "my"), or his to-do
CHECK_ASKED = re.compile(r"\b(?:I|me|my)\b[^.?!]*\b(?:check|verify|look at)\w*|\bto-?do\b",
                         re.I)
CHECK_HEAD = "**Still for you to check: this year's changes**\u00a0· {who}'s interview of {date}"


def asks_what_to_check(line: str) -> bool:
    """t507 (A9): his line asks what he should still check himself (`CHECK_ASKED`)."""
    return bool(CHECK_ASKED.search(line))


def check_said(folder: Path, activity: str) -> str:
    """t507 (A9): what changed this year, for him to check: each changed sentence of the summary
    closing `activity`'s interview of this year (`this_years_path`, `summed_up`), as 457's
    changes card lists it, without its count ("One:") and without what is no change (a thing
    left open, `NOT_A_FINDING`). Code's words only; "" where this year has no such interview."""
    path = this_years_path(folder, activity)
    said = summed_up(folder, path) if path else None
    changed = [COUNTED.sub("", x) for x in said or [] if not SUMMED_UNCHANGED.search(x)
               and not NOT_A_FINDING.search(x)]
    if not path or not changed:
        return ""
    return "\n".join([CHECK_HEAD.format(who=_interviewee(folder, path) or Path(path).stem,
                                        date=_date_of(path)), "", *map(_bullet, changed)])


def _bullet(sentence: str) -> str:
    return f"- {sentence[:1].upper()}{sentence[1:]}"


def summed_up(folder: Path, path: str) -> list[str] | None:
    """t377 D2: each sentence of a re-BIA interview's closing summary (`SUMMED_UP`), but a thanks
    or "N things changed" (`SUMMED_SKIP`); None for an interview with no such summary."""
    found = SUMMED_UP.search(_own_interview(folder, path))
    if not found:
        return None
    return [x for x in re.split(r"(?<=\.)\s+", found["said"].strip())
            if x and not SUMMED_SKIP.match(x)]


def changes_block(folder: Path, path: str) -> str | None:
    """t377 D2: what a re-BIA interview says changed since last year's record, read by code: each
    sentence of its closing summary (`SUMMED_UP`), those that keep a figure under "Not changed".
    t377 N4: "Not changed" opens with the categories the interview leaves as the record has them
    (`same_categories`), never a question and its answer as the transcript has them; r2: then the
    facts it keeps "Unchanged" (`unchanged_facts`). None for an interview with no such summary."""
    if (found := _compared(folder, path)) is None:
        return None
    changed, same = found["changed"], found["unchanged"]
    lines = [CHANGES_HEADING.format(who=_interviewee(folder, path) or Path(path).stem,
                                    date=_date_of(path)), ""]
    lines += [_bullet(x) for x in changed]
    grid = _same_said(found)
    facts = _kept_said(found["kept"])
    if same or grid or facts:
        lines += ["", CHANGES_UNCHANGED, *([_bullet(grid)] if grid else []),
                  *(_bullet(x) for x in [*facts, *same])]
    if (matters := _matters(folder, path, changed)):
        lines += ["", matters]
    return "\n".join(lines)


def compare(folder: Path, activity: str) -> dict[str, Any] | None:
    """t601 (fact): what the activity's interview of this year (`this_years_path`) says changed
    since last year's record, as data (`_compared`); None where it has none or it sums up
    nothing."""
    path = this_years_path(folder, activity)
    return _compared(folder, path) if path else None


def _compared(folder: Path, path: str) -> dict[str, Any] | None:
    """t601: a re-BIA interview against last year's record, as data: its closing summary's
    sentences (`summed_up`) that change something (`changed`) and those that keep it
    (`unchanged`); the record grid's categories it leaves as they were (`same`) and moves
    (`moved`), with the `record` (`_categories`); the facts it keeps "Unchanged" (`kept`). None for
    an interview with no such summary."""
    said = summed_up(folder, path)
    if said is None:
        return None
    same = [x for x in said if SUMMED_UNCHANGED.search(x)]
    changed = [x for x in said if x not in same]
    return {"path": path, "changed": changed, "unchanged": same,
            **_categories(folder, path, changed), "kept": _kept(folder, path)}


def _matters(folder: Path, path: str, changed: list[str]) -> str | None:
    """t412 (A1): what matters, one line (`MATTERS_SAYS`): where this year's grid gives an MTPD
    other than last year's record states (`_mtpd_now`), the category that reaches it, its level and
    hour, both MTPDs, and first the changed sentence sharing most words with the interview's own
    reason for that category's score (the line before its "Impact <category>:"). None where the
    MTPD stays, or `path` is not this year's interview."""
    activity = next(iter(interview._named_in(folder / path)), "")
    found = _mtpd_now(folder, activity, walk._method(folder)) if activity else None
    if not found or found["path"] != path or found["same"] or not found["figure"]:
        return None
    lines = [x for x in _own_interview(folder, path).splitlines() if x.strip()]
    heads = [n for n, x in enumerate(lines) for lens in found["lenses"]
             if re.match(rf"[^:]+: Impact {re.escape(lens.split()[0])}\b", x, re.I)]
    reason = _content_words(" ".join(lines[n - 1] for n in heads if n))
    told = [COUNTED.sub("", x).rstrip(".") for x in changed]
    cause = max(told, key=lambda x: len(_content_words(x) & reason), default="")
    shared = cause and _content_words(cause) & reason
    lenses = _listed([x.lower() for x in found["lenses"]])
    return MATTERS_SAYS.format(
        matters=CHANGES_MATTERS, cause=f"{cause}, so " if shared else "",
        lenses=lenses if shared else lenses[:1].upper() + lenses[1:], level=found["level"],
        horizon=found["horizon"], was=_span(found["figure"]), record=found["record"],
        figure=found["figure"], now=_span(found["horizon"]))


#: t377 N4 r2 (12_marschkamp): an answer that opens "Unchanged" and gives its figures after a colon
#: ("Unchanged for picking: eight in the pool, four in emergency."), the line before it the question
_ANSWERED_UNCHANGED = re.compile(r"^[^:\n]+: (?P<asked>[^\n]+\?)\n+[^:\n]+: Unchanged\b[^:\n]*: "
                                 r"(?P<said>[^\n]+?)\.?$", re.M)
CHANGES_SAME_FACT = "{subject}: unchanged, {said}."


def unchanged_facts(folder: Path, path: str) -> list[str]:
    """t377 N4 r2: each fact the interview keeps "Unchanged", one plain line in its own words
    without the question (`CHANGES_SAME_FACT`): "Technicians: unchanged, eight in the pool and four
    in emergency." t601: from `_kept`."""
    return _kept_said(_kept(folder, path))


def _kept_said(kept: list[dict[str, str]]) -> list[str]:
    return [CHANGES_SAME_FACT.format(**x) for x in kept]


def _kept(folder: Path, path: str) -> list[dict[str, str]]:
    """t377 N4 r2, t601: each fact the interview keeps "Unchanged", as its `subject` and its own
    words (`said`). The subject is the question before its first comma or "?" (so not the person
    asked); a question on a grid category ("Operationally?") is `_categories`' and is left out."""
    activity = next(iter(interview._named_in(folder / path)), "")
    lenses = {name.split()[0].lower() for name in
              ((last_year(folder, activity) if activity else {}).get("grid") or {})}
    out = []
    for m in _ANSWERED_UNCHANGED.finditer(_own_interview(folder, path)):
        subject = re.split(r"[,?]", m["asked"])[0].strip()
        if any(subject.lower().startswith(lens) for lens in lenses):
            continue
        parts = [x.strip() for x in m["said"].split(",")]
        said = f"{', '.join(parts[:-1])} and {parts[-1]}" if len(parts) > 1 else parts[0]
        out.append({"subject": subject, "said": said})
    return out


def same_categories(folder: Path, path: str, changed: list[str]) -> str:
    """t377 N4 (11_marschkamp): last year's record's grid categories the interview leaves as they
    were (`_categories`), as `CHANGES_SAME_GRID`; "" where none is or there is no record grid."""
    return _same_said(_categories(folder, path, changed))


def _same_said(found: dict[str, Any]) -> str:
    same = found["same"]
    return CHANGES_SAME_GRID.format(
        categories=_listed([same[0], *(n[:1].lower() + n[1:] for n in same[1:])]),
        record=found["record"]) if same else ""


def _categories(folder: Path, path: str, changed: list[str]) -> dict[str, Any]:
    """t377 N4, t601: last year's record's grid against the interview's, category by category, as
    the categories `same` and `moved`, and the `record`. Where the interview scores a category
    (`standardise`, stage 3's reader) its cells are compared with the record's (a blank record cell
    compares with nothing); else a category is the same unless its name is one of `changed`'s
    words (the summary's changed sentences). Both empty where there is no record grid."""
    activity = next(iter(interview._named_in(folder / path)), "")
    prior = last_year(folder, activity) if activity else {}
    rows = prior.get("grid") or {}
    out: dict[str, Any] = {"same": [], "moved": [],
                           "record": prior.get("record") or prior.get("ref")}
    if not rows:
        return out
    method = walk._method(folder)
    read = standardise(interview_text(folder / path), drafting.read_register(folder),
                       method_lenses(method))
    scored = next((dict(act.impact_grid) for act in read.activities if act.scores), {})
    said = set(re.findall(r"\w+", " ".join(changed).lower()))
    for name, row in rows.items():
        lens = name.split()[0].lower()
        now = scored.get(lens)
        if now is None:
            moved = lens in said
        else:
            moved = any(v in GRID_LEVELS and now.get(h) != GRID_LEVELS.index(v) + 1
                        for h, v in row["cells"].items())
        out["moved" if moved else "same"].append(name)
    return out


def without_stage_name(text: str, name: str) -> str:
    """t377 N5: the model's text without its own copy of the stage's name (`words.stage_name`,
    bold or not, with the stop or colon after it), where code's footer says it below; the next
    word opens capitalised."""
    out, n = re.subn(rf"\**{re.escape(name)}\**[.:]?\**[ \t]*(\w?)",
                     lambda m: m[1].upper(), text)
    return out.strip() if n else text


def one_plain_sentence(text: str) -> tuple[str, list[str]]:
    """t377 N6 (M13): what the model may add after a code block: its first sentence where it is
    plain (one line, a full stop, no bold, table or list, no `MECHANICS`), else nothing; and the
    rest, for the turn file. Structural; no word of it is judged."""
    said = first_sentence(text.strip().split("\n")[0]) if text.strip() else ""
    plain = said[-1:] in (".", "!", "?") and not re.search(r"\*\*|\||\A\s*(?:[-*#>]|\d+\.)", said) \
        and not MECHANICS.search(said)
    kept = said if plain else ""
    rest = text.strip().removeprefix(kept).strip()
    return kept, [rest] if rest else []


def asks_to_write(line: str) -> bool:
    """t366: his line asks nemo to write a message (`WRITE_WORDS`), beside `asked_for`."""
    return bool(WRITE_WORDS.search(line))


def asks_who_comes(line: str) -> bool:
    """t377 (B), t433 (B3): his line asks who to invite (`asks_to_invite` with `WHO_WORDS`, t418:
    or names), or who comes in any other words (`WHO_COMES`)."""
    return asks_to_invite(line) and bool(WHO_WORDS.search(line)
                                         or words.NAMES_ASKED.search(line)) \
        or bool(WHO_COMES.search(line))


def asks_to_invite(line: str) -> bool:
    """t373: his line asks for the questionnaire or the invitation (`INVITE_WORDS`)."""
    return bool(INVITE_WORDS.search(line))


def write_said(text: str, wrote: bool, shown: list[str] | None = None,
               line: str | None = None) -> tuple[str, list[str]]:
    """t366: what is shown when his line asked for a message: nemo's own line first
    (`DRAFT_FINDING` where 317's step is drawn, else `DRAFT_NO_FINDING`), then t391's drafts
    `shown`, then each paragraph of the model's that names no mail or draft (`ABOUT_WRITING`), a
    heading with nothing under it dropped (`HEADING_ONLY`); and the paragraphs dropped, for the
    turn file. The model has no tool for a draft, so its words on one
    are a false "can't" or a promise only the tap keeps. t391 r2: with drafts `shown`, every
    paragraph of the model's is dropped (as 389 r2's invite turn), never a filter of its words.
    t482: `line` stands for nemo's own line where an open conflict's taps are drawn."""
    line = line or (DRAFT_FINDING if wrote else DRAFT_NO_FINDING).format(tap=WRITE_TAP)
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    # t377c G3 (g2-4): the model's own letter, from its first part (`LETTER_OPENS`) to the end
    start = 0 if shown else next((n for n, p in enumerate(paragraphs) if any(  # t476: any line
        LETTER_OPENS.match(x) for x in p.split("\n"))), len(paragraphs))
    gone = {n for n, p in enumerate(paragraphs) if n >= start or ABOUT_WRITING.search(p)}
    kept = [n for n in range(len(paragraphs)) if n not in gone]
    while kept and HEADING_ONLY.fullmatch(paragraphs[kept[-1]]):  # t391: nothing under it
        gone.add(kept.pop())
    # t549 r2: the drafts are code's, so their figures keep their units; the model's paragraphs not
    return ("\n\n".join([line, *(unit_kept(d) for d in shown or []),
                         *(paragraphs[n] for n in kept)]),
            [paragraphs[n] for n in sorted(gone)])


#: t412 (A7, run 7): who decides on the open gaps, asked in his typed line (`asks_who_decides`).
#: nemo answers it itself (`who_decides`): each open discrepancy under the function holding it
#: first, then the name; the MTPD under the process owner, who decides it (`_decides`). t454 (run 2,
#: A7): "decid" alone is A7-20's typo ("who has to decid on the gaps"), never "decided" (last
#: year's); the bare "Who decides?" is A7-03, his whole line, so "Who decides the MTPD?" stays out.
#: t469: the whole line may carry an address or a polite word ("Nemo,", "Please", "Okay", "Could you
#: tell me:") and a trailing ", please". t470 (router report R1): who or which role or function
#: decides, owns, is responsible for, signs off or is the boss of the gaps, or the gaps routed to
#: who decides; "Who is responsible?" is a bare form too
WHO_DECIDES_WORDS = re.compile(r"\b(?:who|which (?:roles?|functions?))\b[^?.!]*"
                               r"\b(?:decid(?:es?)?|decisions?|owns?|responsible|sign off|boss)\b"
                               r"[^?.!]*\bgaps?\b|\bdecision owners?\b[^?.!]*\bgaps?\b"
                               r"|\bgaps?\b[^?.!]*\b(?:who|function|people)\b[^?.!]*"
                               r"\b(?:decide|decision|owns)\b"
                               r"|^\s*(?:(?:nemo|please|okay|ok)\s*,?\s+|could\s+you\s+tell\s+me\s*:?\s*)?"
                               r"who\s+(?:decides|is\s+responsible)\s*(?:,\s*please\s*)?\?*\s*$",
                               re.I)
WHO_DECIDES_KIND = "who_decides"
WHO_DECIDES_HEAD = "**Who decides on the open gaps · {name}**"
WHO_DECIDES_LINE = "- **{function}** ({name}): {gaps}"
WHO_DECIDES_MTPD = "And the MTPD: about {now} ({horizon}) by the method, against {figure} in " \
    "record {record}."


def asks_who_decides(line: str) -> bool:
    """t412: his line asks who decides on the open gaps (`WHO_DECIDES_WORDS`)."""
    return bool(WHO_DECIDES_WORDS.search(line))


def who_decides(folder: Path, activity: str) -> str | None:
    """t412 (A7): the activity's open gaps, one line per holder (`WHO_DECIDES_LINE`): the function
    the holder is listed with, as `drafts_first` reads it, then the name, then each gap as code
    read it (t601: `gap_owners`' data); the process owner's line ends on a moved MTPD
    (`_mtpd_now`). None where the activity has no open discrepancy."""
    found = gap_owners(folder, activity)
    if not found["holders"]:
        return None
    now = _mtpd_now(folder, activity, walk._method(folder))
    mtpd = WHO_DECIDES_MTPD.format(now=_span(now["horizon"]), horizon=now["horizon"],
                                   figure=now["figure"], record=now["record"]) \
        if now and now["figure"] and not now["same"] else ""
    lines = [WHO_DECIDES_HEAD.format(name=process_name(folder, activity)), ""]
    for held in found["holders"]:
        said = held["gaps"] + ([mtpd] if mtpd and held["to"] == found["decides"]["name"] else [])
        lines.append(WHO_DECIDES_LINE.format(function=held["function"], name=held["to"],
                                             gaps=" ".join(said)))
    return "\n".join(lines)


def gap_owners(folder: Path, activity: str) -> dict[str, Any]:
    """t601 (fact): who owns the activity's gaps and who decides, as data: the process owner who
    decides (`decides`: `role`, `name`, by `_decides`); each holder of its open `discrepancies`
    (`holders`: `to`, the `function` it is listed with, the `gaps` as code read them); the register
    resources no row names a person for (`unowned`); and the process owner the organisation file
    names no deputy for (`no_deputy`, `_no_deputy`; None where one is named or no owner is)."""
    by: dict[str, list[dict[str, Any]]] = {}
    for d in discrepancies(folder, activity):
        by.setdefault(d["to"], []).append(d)
    role, owner = _decides(folder, activity)
    return {"decides": {"role": role, "name": owner},
            "holders": [{"to": to, "function": re.split(r"[,(]", theirs[0]["holder"])[0].strip()
                         or to, "gaps": [d["said"] for d in theirs]} for to, theirs in by.items()],
            "unowned": _unowned(folder, activity),
            "no_deputy": _no_deputy(folder, activity) or None}


def topic(d: dict[str, Any]) -> str:
    """t418: a discrepancy's topic as a subject names it (`TOPIC_ENDS`): its sentence's opening
    words up to the first verb, an article dropped and the word after it lower case; where that is
    one word, what the verb is about joins it (`TOPIC_SKIPS`, `TOPIC_STOPS`). t418 r2
    (14_marschkamp): two things it is about, joined by "and", that end on the same word join as
    one ("legal impact from 8 hours and image impact from 2 hours" is "legal and image impact").
    t418 r3 (35_nemo_check): where the sentence names its register resource after a topic that
    does not ("Emergency operation needs six technicians … at night and at weekends"), the topic
    names it: the topic's first word, the resource as the sentence says it, and when
    (`TOPIC_WHEN`), "Emergency technicians at night and weekends"."""
    clause = re.split(r"[,.;]", d["said"])[0]
    head, *rest = TOPIC_ENDS.split(clause, maxsplit=1)
    bare = re.sub(r"^(?:The|A|An) ", "", head)
    said = bare[:1].lower() + bare[1:] if bare != head else head
    if rest and len(said.split()) == 1:
        first, *more = rest[0].split(" and ", maxsplit=1)
        about, also = _topic_about(first), _topic_about(more[0]) if more else []
        if len(about) > 1 and also and about[-1] == also[-1]:
            about = [*about[:-1], "and", *also]
        said = " ".join([said, *about])
    resource = d.get("resource")
    named = resource and re.search(rf"\b{re.escape(resource)}s?\b", d["said"], re.I)
    if named and named.group(0).lower() not in said.lower():
        when = TOPIC_WHEN.findall(d["said"])
        said = " ".join([said.split()[0], named.group(0),
                         *([f"{when[0][0]} {' and '.join(w for _, w in when)}"] if when else [])])
    return said


def _topic_about(said: str) -> list[str]:
    """t418: what a verb is about, its first words up to a preposition or clause (`topic`)."""
    return list(itertools.takewhile(lambda w: w.lower() not in TOPIC_STOPS, itertools.dropwhile(
        lambda w: w.lower() in TOPIC_SKIPS or w.lower() in TOPIC_VERBS.split()
        or w.endswith("ed"), said.split())))


def topics_said(abouts: list[str]) -> str:
    """t418 r2 (14_marschkamp): a draft's topics as its subject joins them, "A, B and C"; a word
    they all open on is said once ("Westerkoog contract, legal and image impact"), and a last topic
    holding "and" itself joins by a comma."""
    heads = {a.split()[0] for a in abouts}
    head = heads.pop() if len(abouts) > 1 and len(heads) == 1 and all(
        len(a.split()) > 1 for a in abouts) else ""
    items = [a.split(maxsplit=1)[1] for a in abouts] if head else abouts
    last = ", " if " and " in items[-1] else " and "
    said = ", ".join(items[:-1]) + last * (len(items) > 1) + items[-1]
    return f"{head} {said}" if head else said


def holder_function(folder: Path, d: dict[str, Any]) -> str:
    """t418: the function a discrepancy goes to: the one its register row lists the holder with,
    else the organisation file's (`words.people`), else the holder as written."""
    listed = re.split(r"[,(]", d["holder"])[0].strip()
    return listed or words.people(folder).get(re.sub(r"^(?:Dr|Prof)\.? ", "", d["to"]), d["to"])


def draft_parts(folder: Path, activity: str) -> list[tuple[str, str, str, list[str]]]:
    """t406: what `drafts_first` shows, each draft as its address line, the person it goes to,
    its subject and its body's lines, so the mailbox's copy (`drafts.shown_drafts`) says what he
    was shown. t418 (ADR-0051): the address line names the function and the greeting greets it
    (`DRAFT_DEAR`); the body is one paragraph, each gap then the question; the subject is each
    gap's `topic`, once (`topics_said`). t418 r2 (his ANSWER 2026-10-11T07:26:47Z): the question
    always follows a gap that states the change, so a gap with no words adds nothing and an owner
    with only such gaps gets no draft."""
    by: dict[str, list[dict[str, Any]]] = {}
    for d in discrepancies(folder, activity):
        if d["said"].strip():
            by.setdefault(d["to"], []).append(d)
    out = []
    for to, found in by.items():
        function = holder_function(folder, found[0])
        about = topics_said(list(dict.fromkeys(topic(d) for d in found)))
        out.append((DRAFT_TO.format(function=function), to,
                    DRAFT_SUBJECT.format(about=about[:1].upper() + about[1:]),
                    letter(function, " ".join([*(d["said"] for d in found), DRAFT_ASK]),
                           bcm_officer(folder))))
    return out


def letter(function: str, body: str, sender: str) -> list[str]:
    """t476 (spec m15 S3): a code-built draft's lines as a letter, "" a blank line: the greeting
    (`DRAFT_DEAR`), the body as given, then the thanks, the regards and the sender's function
    signed as drafted with nemo (`LETTER_SIGNED`). Functions only (ADR-0051); the one template,
    which 495's agent fills with its own gap and ask. t588 (L3): a body's own line breaks are its
    lines."""
    return [DRAFT_DEAR.format(function=function), "", *body.split("\n"), "", *closing(sender)]


def closing(sender: str) -> list[str]:
    """t476: how every code-built draft closes: the thanks, the regards and the sender's function
    signed as drafted with nemo (`LETTER_SIGNED`). t503: 257/371's follow-up note and 373's
    invitation close with these lines too (`drafts.CLOSING`)."""
    return [LETTER_THANKS, LETTER_REGARDS, LETTER_SIGNED.format(function=sender).strip()]


def bcm_officer(folder: Path) -> str:
    """t476: the BCM Officer as the organisation file names the function (`BCM_FUNCTION`), ""
    where it names none."""
    return next((f for f in words.functions(folder) if BCM_FUNCTION.search(f)), "")


def model_letter(text: str) -> bool:
    """t476: the model's reply holds a letter of its own: a line `LETTER_HEAD` opens, or a
    greeting line `LETTER_HI` reads in a reply naming a written thing (`WRITE_READS`)."""
    lines = text.split("\n")
    return any(LETTER_HEAD.match(x) for x in lines) or bool(WRITE_READS.search(text)) and any(
        LETTER_HI.fullmatch(x) for x in lines)


def drafts_first(folder: Path, activity: str) -> list[str]:
    """t391: the drafts his ask is shown first, one per owner of the activity's open
    `discrepancies` (317's picks, in their order), never sent: the address line (`DRAFT_TO`: the
    function the holder is listed with), the subject (`DRAFT_SUBJECT`, t418: each gap's `topic`),
    the greeting, and the body: each gap as code read it, and the question. Every word code's or
    the seed's. t476: the letter's lines (`letter`), one block still (418 r3): each on a hard
    break, a blank one a backslash's, so no paragraph ends inside a draft."""
    return [draft_block(to, subject, lines)
            for to, _, subject, lines in draft_parts(folder, activity)]


#: t747: a line's start that Markdown reads as opening a list: "1. ", "1) ", "- ", "* ", "+ "
_LIST_OPENS = re.compile(r"^ {0,3}(?:\d{1,9}(?=[.)])|(?=[-+*]))(?=[-+*.)](?:[ \t]|$))")
#: t747: that marker as `draft_block` wrote it
_LIST_ESCAPED = re.compile(r"^( {0,3}\d{0,9})\\(?=[-+*.)](?:[ \t]|$))", re.M)


def draft_block(to: str, subject: str, lines: list[str]) -> str:
    """t391's draft as shown, one block (418 r3): the address line, the subject and the letter's
    lines, each on a hard break, a blank one a backslash's. t539: the model's letters show so.
    t747: a line that would open a list keeps its marker escaped, or it ends the block and the
    backslash before it stands as a character; the mailbox's copy never comes through here."""
    shown = [_LIST_OPENS.sub(r"\g<0>\\", x) for x in lines]
    return "\n".join([*(f"{x}  " if x else "\\" for x in [f"**{to}**", "Subject: " + subject,
                                                          *shown][:-1]), shown[-1]])


def no_list_escape(text: str) -> str:
    """t747: a shown draft as the model's history keeps it: "1." with no escape, which it would
    copy into its next letter."""
    return _LIST_ESCAPED.sub(r"\1", text)


def slides_filled(folder: Path) -> bool:
    """t329: 259's slides have a record to fill from: last year's record of a core process."""
    import workspace  # the slides' own module, which reads this one
    return any(last_year(folder, name)["found"] for name in workspace.core_processes(folder))


def named_in(folder: Path, line: str) -> list[str]:
    """t252: the room's activities his typed line names, each by a WHOLE name: its room spelling,
    or its process-map row's name or slug (`_map_key`: hyphens as spaces, case ignored). No part of
    a name and no fuzzy match: "production" names nothing; "production-and-processing" and
    "Production and processing" name the same activity."""
    path = folder / PROCESS_MAP
    rows = _MAP_ROW.findall(path.read_text(encoding="utf-8")) if path.is_file() else []
    said = _name_words(line)
    out = []
    for a in walk.processes(folder):
        names = [a, *(n for row in rows if _map_key(a) in map(_map_key, row) for n in row)]
        if any(_name_words(n).strip() and _name_words(n) in said for n in names):
            out.append(a)
    return out


def loosely_named(folder: Path, line: str) -> list[str]:
    """t367: the room's activities a line names by a word of five letters or more that only that
    activity's name holds ("production" for "Production and processing"). Read for the chart
    alone: a shared word ("management") names none."""
    said = set(re.findall(r"\w+", _map_key(line)))
    own = {a: {w for w in re.findall(r"\w+", _map_key(map_name(folder, a))) if len(w) >= 5}
           for a in walk.processes(folder)}
    return [a for a, words_ in own.items()
            if (words_ - set().union(*(w for b, w in own.items() if b != a))) & said]


def named_by_head(folder: Path, line: str) -> list[str]:
    """t566: the room's activities a line names by a head word of their name that only they are
    called by, five letters or more ("production", "dispatch"); none where the word is the head of
    more than one ("management"). Read where a turn's activity is handed over. A word that only
    modifies a name names nothing here: "Raw material procurement" is not "is it material?"."""
    said = set(re.findall(r"\w+", _map_key(line)))
    own = {a: _name_heads(map_name(folder, a), 5) for a in walk.processes(folder)}
    return [a for a, words in own.items()
            if (words - set().union(*(w for b, w in own.items() if b != a))) & said]


#: t543 r2: the words a naming run never starts or ends on ("procurement and", "and delivery")
NAME_RUN_STOPS = TOPIC_STOPS | {"the", "a", "an"}


def run_named(folder: Path, line: str) -> list[str]:
    """t543 r2: the room's activities a line names by a run of two or more consecutive words of
    the name that no other activity's name holds ("financial management" for "IT financial
    management"), the run never starting or ending on a stop word (`NAME_RUN_STOPS`)."""
    names = {a: re.findall(r"\w+", _map_key(map_name(folder, a))) for a in walk.processes(folder)}
    said = " " + " ".join(re.findall(r"\w+", _map_key(line))) + " "
    runs = {a: {" ".join(w[i:j]) for i in range(len(w)) for j in range(i + 2, len(w) + 1)
                if w[i] not in NAME_RUN_STOPS and w[j - 1] not in NAME_RUN_STOPS}
            for a, w in names.items()}
    return [a for a, own in runs.items()
            if any(f" {r} " in said and not any(f" {r} " in f" {' '.join(w)} "
                                                for b, w in names.items() if b != a) for r in own)]


def classless(folder: Path, line: str) -> str:
    """t533 r2: his line without the method's class words ("financial"): a class word of the
    method never names an activity (t543) and never sets the room's focus."""
    path = folder / walk.METHOD
    classes = set(method_lenses(json.loads(path.read_text(encoding="utf-8")))) \
        if path.is_file() else set()
    return " ".join(w for w in re.findall(r"\w+", line) if w.lower() not in classes)


def chart_named(folder: Path, line: str) -> list[str]:
    """t543: `loosely_named` as the chart route reads his line: a class word of the method
    (`method_lenses`, "financial") names no activity on its own, so "IT financial management" is
    named by its name (`named_in`) or, r2, by a run of it (`run_named`: "financial management")."""
    loose = loosely_named(folder, classless(folder, line))
    runs = run_named(folder, line)
    return [a for a in walk.processes(folder) if a in loose or a in runs]


_DATED_FILE = re.compile(r"\d\d_\d\d_\d\d_")


def this_years_path(folder: Path, activity: str) -> str | None:
    """t367: the activity's newest own interview dated after last year's record's file (any,
    with no record); None where there is none. t412: `_mtpd_now` names it too."""
    prior = last_year(folder, activity)
    source = Path(str(prior.get("source") or "")).name
    since = source[:8] if prior.get("found") and _DATED_FILE.match(source) else ""
    newer = [p for p in drafting.own_interviews(folder, activity)
             if _DATED_FILE.match(Path(p).name) and Path(p).name[:8] > since]
    return max(newer, key=lambda p: Path(p).name) if newer else None


def cited_files(folder: Path, activity: str | None) -> list[str]:
    """t413 r3: the words of the room files a turn on `activity` could quote, this year's
    interview and last year's record, each whitespace- and quote-mark-normalised (`_unquoted`)."""
    if not activity:
        return []
    paths = [this_years_path(folder, activity),
             str(last_year(folder, activity).get("source") or "")]
    return [_unquoted((folder / p).read_text(errors="replace")) for p in paths
            if p and (folder / p).is_file()]


def this_years_interview(folder: Path, activity: str,
                         method: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """t367: this year's interview grid and its date ("1 Oct 2026"), read by code only
    (`nemo.evidence.standardise`, stage 3's reader), never by a model. This year's is
    `this_years_path`'s; a grid it states no score in is `{}`, and the chart draws no line for
    it."""
    if (path := this_years_path(folder, activity)) is None:
        return {}, ""
    read = standardise(interview_text(folder / path), drafting.read_register(folder),
                       method_lenses(method))
    grid = next((act.impact_grid for act in read.activities if act.scores), {})
    when = next((h.when for h in facts.interviews(folder) if h.path == path), "")
    return dict(grid), when


def this_years_scores(folder: Path, activity: str,
                      method: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """t518: this year's scores as the impact chart draws them: `this_years_interview`'s grid, or
    where that interview states none as a grid, the scores it states in words
    (`worded_scores.from_words`, over the hours last year's record rates), read by code only."""
    grid, when = this_years_interview(folder, activity, method)
    if grid or (path := this_years_path(folder, activity)) is None:
        return grid, when
    prior = impact_chart.from_record(last_year(folder, activity).get("grid"), method)
    return worded_scores.from_words(interview_text(folder / path), method, prior), when


#: t377 H2 (v7-05): how long an activity can be down, asked in his typed line at any stage
#: (`asks_how_long_down`); nemo answers it itself (`down_for`), never with the model's figure (M13)
DOWN_WORDS = re.compile(r"\bhow long can (?P<what>.+?) (?:be down|be out|stand still|stop)\b",
                        re.I)
#: t470 (router report R1, A4): the same ask in other words, on the activity the line names or the
#: room is on: how long it can be stopped or down, the longest or how many hours, its tolerable or
#: maximum downtime, its MTPD derived, recomputed or set against last year's
DOWN_ASKED = re.compile(r"\bhow long\b[^.?!]*\b(?:down|out|stopped|stand still)\b"
                        r"|\bstops?\b[^.?!]*\bhow long\b"
                        r"|\b(?:longest|how many hours)\b[^.?!]*\b(?:be down|be out|be stopped"
                        r"|stand still|stop)\b|\b(?:tolerable|max(?:imum)?) downtime\b"
                        r"|\bmax(?:imum)? tolerable period\b"
                        r"|\b(?:derive|recompute)\b[^.?!]*\bMTPD\b"
                        r"|\bMTPD\b[^.?!]*\b(?:now|vs\.?|against)\b", re.I)
DOWN_HEAD = "**How long {name} can be down now** · from this year's interview ({when})"
#: t377 L: each derived MTPD names its grid's year (`_year_in`): this year's interview's, and the
#: one last year's record states its grid was taken at
DOWN_NOW = ("Proposed: about {now} ({horizon}), as the method gives it from this year's "
            "grid{year}{then}.")
DOWN_THEN = "; last year's record said {was} (record {record}: {figure}{reach})"
DOWN_SAME = "; as last year (record {record}: {figure}{reach})"
DOWN_REACH = "; its grid{year} reached {level} at {horizon}"
DOWN_WHY = "Why: {lenses} impact reaches {level} at {horizon}."
DOWN_WHO = "The {role} ({owner}) decides, not nemo."
#: t412 (A4, 399 r2's run): his own words in this year's interview when asked where he stands on
#: the MTPD, after who decides (`_his_stand`)
DOWN_SAID = ' Asked in the interview, the {role} said: "{said}"'
MTPD_ASKED = re.compile(r"\bMTPD\b")


#: t377 L: the last year a date names; impact_chart's, which the draft's rule card reads too (r2)
_year = impact_chart.year


def _year_in(said: str) -> str:
    """t377 L: " (<year>)" for `_year`, "" where there is none."""
    return f" ({year})" if (year := _year(said)) else ""


def last_key(prior: dict[str, Any]) -> str:
    """t377 L: the chart's key for last year's record, with the year its grid was taken in
    (`CHART_LAST_KEY`), or without one where the record states no interview date."""
    record = prior.get("record") or prior.get("ref")
    year = _year(str(prior.get("interview") or ""))
    return CHART_LAST_KEY.format(record=record, year=year) if year else \
        CHART_LAST_UNDATED.format(record=record)


def activity_chart(folder: Path, activity: str, method: dict[str, Any]) -> str:
    """t367: chart A of `activity`, last year's record's grid against this year's interview's, as
    `Session._chart_turn` draws it; `""` where neither holds a score. t399: the prompt check
    redraws the chart a turn showed from this, since the turn file keeps no chart."""
    return activity_charts(folder, activity, method)[0]


def activity_charts(folder: Path, activity: str, method: dict[str, Any],
                    only: Collection[str] | None = None,
                    years: Collection[str] | None = None) -> tuple[str, str]:
    """t403 r6: `activity_chart`'s chart and the phone's split of it (`impact_chart.class_charts`),
    both `""` where neither grid holds a score. t499 r2: `only`, the impact classes (their ids)
    drawn, every class where None. t538: `years`, "last" and/or "this", both where None."""
    prior = last_year(folder, activity)
    this, when = this_years_scores(folder, activity, method)
    last = impact_chart.from_record(prior.get("grid"), method)
    if only is not None:
        last, this = ({c: row for c, row in (grid or {}).items() if c in only}
                      for grid in (last, this))
    if years is not None:
        last, this = (grid if year in years else {} for grid, year in ((last, "last"),
                                                                       (this, "this")))
    return impact_chart.class_charts(
        last, this, method,
        last_said=last_key(prior),
        this_said=CHART_THIS_KEY.format(when=when) if when else CHART_THIS_UNDATED,
        target=(prior.get("figures") or {}).get("RTO"),
        record=prior.get("record") or prior.get("ref"),
        years=(_year(when), _year(str(prior.get("interview") or ""))))


def asks_how_long_down(line: str) -> str | None:
    """t377 H2: what his line asks how long can be down (`DOWN_WORDS`), or None. t470: the whole
    line where it asks in other words (`DOWN_ASKED`)."""
    found = DOWN_WORDS.search(line)
    return found["what"] if found else line if DOWN_ASKED.search(line) else None


def _span(figure: str) -> str:
    """t377 H2: a duration in plain words: "3 days" for 72 h, "a week" for 168 h, "more than a
    week" for >168 h; hours where they make no whole day."""
    hours = (duration.worst_case(figure) or 0) // 60
    more = "more than " if figure.strip().startswith(">") else ""
    if hours and hours % 168 == 0:
        weeks = hours // 168
        return f"{more}{'a week' if weeks == 1 else f'{weeks} weeks'}"
    if hours and hours % 24 == 0:
        return f"{more}{hours // 24} day{'s' * (hours > 24)}"
    return f"{more}{hours} hours"


def _decides(folder: Path, activity: str) -> tuple[str, str]:
    """t377 H2: who decides, as (role, name): the process owner the plan names (else last year's
    record), with the role he had at the activity's newest interview (else "process owner")."""
    prior = last_year(folder, activity)
    _, rows = _plan_table(folder)
    owner = next((r[2] for r in rows if _map_key(r[1]) == _map_key(process_name(folder, activity))),
                 "") or ((re.search(r"\(([^)]+)\)", str(prior.get("owner") or "")) or [""])[-1])
    newest = max(drafting.own_interviews(folder, activity), default=None,
                 key=lambda p: Path(p).name)
    roles = dict(participants((folder / newest).read_text(encoding="utf-8"))) if newest else {}
    # t513: the function as the organisation file writes it ("Plant Manager"), else as before
    return words.people(folder).get(owner) or (
        roles.get(owner) or "process owner").split(",")[0].strip().lower(), owner


def _mtpd_now(folder: Path, activity: str, method: dict[str, Any]) -> dict[str, Any] | None:
    """t377 H2, t412: this year's MTPD by code: this year's interview (`this_years_path`, its
    `path` and date `when`) read by `standardise` (`this_years_interview`), the method's MTPD over
    its grid (`impact.crossing`: `horizon`, `lenses`, their `level`), beside last year's record's
    stated MTPD (`figure`, `record`, `prior`) and whether the two are the `same`. None where this
    year's interview scores no grid or the grid reaches no MTPD within the horizons. t601: the
    reading is `impact.mtpd_reading`'s, the one derivation."""
    grid, when = this_years_interview(folder, activity, method)
    reading = impact.mtpd_reading(grid, method)
    horizon, lenses, score = reading["horizon"], reading["lenses"], reading["score"]
    if horizon == impact.NO_MTPD:
        return None
    prior = last_year(folder, activity)
    figure = (prior.get("figures") or {}).get("MTPD")
    return {"path": this_years_path(folder, activity), "when": when, "horizon": horizon,
            "lenses": lenses, "prior": prior, "figure": figure,
            "record": prior.get("record", prior.get("ref")),
            "level": GRID_LEVELS[score - 1] if 0 < score <= len(GRID_LEVELS) else score,
            "same": bool(figure) and duration.worst_case(figure) == duration.worst_case(horizon)
            and not str(figure).strip().startswith(">")}


def mtpd_reading_now(folder: Path, activity: str) -> dict[str, Any] | None:
    """t601 (fact): the MTPD/RTO reading as data: `_mtpd_now`'s, the record it read left out, with
    the record's RTO. None where `_mtpd_now` is."""
    found = _mtpd_now(folder, activity, walk._method(folder))
    return None if found is None else {**{k: v for k, v in found.items() if k != "prior"},
                                       "rto": (found["prior"].get("figures") or {}).get("RTO")}


#: t481 (M13): the money this year's interview puts on a stop ("about 0.9 million euros" a day,
#: then two days and three), stated by code (`euro_said`); the model's never
EURO_LINE = re.compile(r"\beuros?\b", re.I)
EURO_MILLION = re.compile(r"(\d+(?:\.\d+)?) million\b")
#: r2: what the figures are, as the seed has them ("euros of goods we don't make"), never a loss
EURO_SAID = "From this year's interview: the goods not made would be worth about {figures}."
EURO_DAY = "{figure} after {n} day{s}"
#: t481: a euro figure as a sentence states one ("€5m", "5 million euros"); a model's goes
EURO_FIGURE = re.compile(r"€\s?\d|\d\s*(?:m|million|bn|billion|k|thousand)?\s*(?:euros?|EUR)\b",
                         re.I)


def euro_said(folder: Path, activity: str) -> str:
    """t481: the euro figures this year's interview (`this_years_path`) states on its line naming
    euros, each in millions, the nth for n days down as the line runs ("a day …, two days …,
    three"); "" where it states none."""
    path = this_years_path(folder, activity)
    found = [n for line in (_own_interview(folder, path) if path else "").splitlines()
             if EURO_LINE.search(line) for n in EURO_MILLION.findall(line)]
    return EURO_SAID.format(figures=_listed([
        EURO_DAY.format(figure=f"€{n}m", n=i, s="s" * (i > 1)) for i, n in enumerate(found, 1)
    ])) if found else ""


def down_for(folder: Path, activity: str, method: dict[str, Any]) -> str | None:
    """t377 H2: how long the activity can be down now, by code (`_mtpd_now`), beside last year's
    record's stated MTPD; then who decides (`_decides`) and, t412 (A4), what he said in this
    year's interview when asked where he stands (`_his_stand`). None where `_mtpd_now` is."""
    if (found := _mtpd_now(folder, activity, method)) is None:
        return None
    prior, figure, horizon, when = found["prior"], found["figure"], found["horizon"], found["when"]
    reached = [(GRID_LEVELS.index(v), -i, v, h) for row in (prior.get("grid") or {}).values()
               for i, (h, v) in enumerate(row["cells"].items()) if v in GRID_LEVELS]
    top = max(reached, default=None)
    then = "" if not figure else (DOWN_SAME if found["same"] else DOWN_THEN).format(
        was=_span(figure), record=found["record"], figure=figure,
        reach=DOWN_REACH.format(level=top[2], horizon=top[3],
                                year=_year_in(str(prior.get("interview") or ""))) if top else "")
    role, owner = _decides(folder, activity)
    lines = [DOWN_HEAD.format(name=_said_name(folder, activity), when=when),
             DOWN_NOW.format(now=_span(horizon), horizon=horizon, then=then, year=_year_in(when)),
             DOWN_WHY.format(lenses=_listed([x.lower() for x in found["lenses"]]),
                             horizon=horizon, level=found["level"])]
    if euros := euro_said(folder, activity):  # t481
        lines.append(euros)
    if owner:
        said = _his_stand(folder, found["path"], owner)
        lines.append(DOWN_WHO.format(role=role, owner=owner)
                     + (DOWN_SAID.format(role=role, said=said) if said else ""))
    return "\n\n".join(lines)


def _his_stand(folder: Path, path: str | None, owner: str) -> str | None:
    """t412 (A4): the first sentence of the owner's answer in this year's interview to the
    question that names the MTPD (`MTPD_ASKED`), his line straight after it; None where none."""
    lines = [x for x in (_own_interview(folder, path) if path else "").splitlines() if x.strip()]
    for asked, answer in zip(lines, lines[1:], strict=False):
        who, _, said = answer.partition(": ")
        if MTPD_ASKED.search(asked) and not asked.startswith(f"{owner}:") and who == owner:
            return first_sentence(said.strip())
    return None


#: t413 (A5, run 7): what in this year's interview does not match last year's record, asked in his
#: typed line (`asks_what_mismatches`) outside a D2 analysis; nemo answers it itself
#: (`mismatches_said`): the list and its count are code's, never the model's (M13)
#: t433 (A5): or what contradicts, conflicts, is inconsistent, disagrees, is wrong, or does not fit,
#: add up or line up; what fits or matches the grid or last year
MISMATCH_WORDS = re.compile(
    r"\bnot match|\bmismatch|\b(?:don'?t|doesn'?t|do not|does not) (?:match|fit|add up|line up)"
    r"|\bcontradict\w*|\binconsist\w*|\bconflict\w*|\bdisagree\w*|\bwrong\b|\bfit (?:with|in)\b"
    r"|\bline up\b|\bmatch (?:the|last)\b", re.I)
MISMATCH_KIND = "mismatches"
MISMATCH_HEAD = ("**What does not match last year's record · {name}** · this year's interview "
                 "({when}) against record {record}")
MISMATCH_COUNT = "{n} mismatch{es}:"
MISMATCH_NONE = "No mismatch: this year's interview rates every category as last year's grid does."
MISMATCH_ROW = "- {category}: {now} this year; last year {then} (record {record})."
#: the knock-on where the MTPD this year's grid gives no longer sits above the record's RTO
MISMATCH_KNOCK_ON = ("- Knock-on: this year's grid gives an MTPD of {mtpd}, against {was} in the "
                     "record, so the RTO ({rto}) no longer sits below it.")
MISMATCH_SAME = "Everything else matches last year's grid: {categories}."
#: r2 (34_nemo_check): a band no category of last year's record rates is no change, whatever
#: this year rates it
MISMATCH_UNRATED = ("{band}: this year rates it {now}; last year's record did not rate {band}, so "
                    "it is not a change.")


def asks_what_mismatches(line: str) -> bool:
    """t413: his line asks what does not match (`MISMATCH_WORDS`)."""
    return bool(MISMATCH_WORDS.search(line))


def asks_dependencies(line: str) -> bool:
    """t526: his line asks for the dependency card (`DEPENDENCY_WORDS`, bar `NOT_AN_ACTIVITY_ASK`)
    or for a gap in the workarounds (`SPOF_WORDS`)."""
    return bool((DEPENDENCY_WORDS.search(line) and not NOT_AN_ACTIVITY_ASK.search(line))
                or SPOF_WORDS.search(line))


#: t471: the router's word lists, by the card each asks for, in the order `Session._turn` tries
#: them: the chart before all (its turn ends the chain), the dependency table before "what
#: changed" (R3). Quotes as asked after the changes card, drafts to the owners before a write.
ROUTES: tuple[tuple[str, Callable[[str], object]], ...] = (
    ("chart", asks_for_chart), ("briefing", BRIEFING_WORDS.search),
    ("who comes", asks_who_comes), ("focus", FOCUS_WORDS.search),
    ("dependencies", asks_dependencies),
    ("next", asks_which_next), ("down", asks_how_long_down),
    ("quotes", lambda s: asks_for_quotes(s, after_changes=True)),
    ("who decides", asks_who_decides), ("mismatches", asks_what_mismatches),
    ("due", asks_which_due), ("changed", asks_what_changed),
    ("to owners", lambda s: asks_to_write(s) and TO_OWNERS.search(s)), ("write", asks_to_write),
    ("invite", asks_to_invite))
#: t471: a word one typo can miss: 6+ letters (shorter words are never read as a typo)
TYPO_WORD = re.compile(r"[^\W\d_]{6,}")
#: t471 r2 (13_nemo_design 2026-10-14): two cards or more: nemo asks which, a tap per card naming
#: the answer it draws, in plain words
WHICH_MEANT = "Which did you mean?"
MEANT_LABELS = {
    "chart": "The impact chart", "briefing": "The briefing", "who comes": "Who comes",
    "focus": "What to focus on", "dependencies": "What it depends on",
    "next": "Which BIA is next", "down": "How long it can be down", "quotes": "Their own words",
    "who decides": "Who decides", "mismatches": "What does not match",
    "due": "Which BIAs are due", "changed": "What changed", "to owners": "A draft to the owners",
    "write": "A draft to the owners", "invite": "The invitation"}


def _routes(line: str) -> list[str]:
    return [card for card, asks in ROUTES if asks(line)]


#: t471: the routing lists' words spelled out, as a typo misses them. The lists are patterns
#: (`compar\w*`), and one edit from a pattern is any word that starts the same ("company" reads
#: "compary"), so a typo is read against these words; the patterns still decide the card.
LIST_WORDS = frozenset("""
    chart charts graph graphs visualise visualize visualisation visualization presentation slides
    organisation organization network process resource supply
    briefing briefings meeting print paper
    participant participants invitee invitees attend attendees attending invite invites
    invitation invitations questionnaire questionnaires calendar
    focus concentrate
    dependency dependencies depend depends upstream downstream
    single failure failures missing workaround workarounds
    review reviews backlog overdue
    downtime longest outage tolerable stopped
    quotes interview verbatim evidence exactly actually statement statements support
    decide decides decision decisions responsible function functions owners
    mismatch mismatches conflict conflicts contradict contradicts contradiction contradictions
    inconsistent inconsistency inconsistencies disagree disagrees wrong
    change changed changes compare compared comparison differ difference differences different
    deviation deviations deviate versus deltas
    analyse analyze analysis drafts messages letters compose prepare
""".split())


def _one_off(typed: str, word: str) -> bool:
    """`typed` is one typo from `word`: two neighbours swapped, or one letter of `word` dropped,
    never its last (the practice typo kinds). r2 (40_nemo_check 2026-10-14): a letter changed or
    added is another real word as often as a typo ("chance" is no "change", "outrage" no
    "outage"), so it is never forgiven."""
    t, w = typed.lower(), word.lower()
    at = next((i for i, (x, y) in enumerate(zip(t, w, strict=False)) if x != y), len(t))
    if len(t) == len(w):
        return at < len(t) - 1 and t[at] == w[at + 1] and t[at + 1] == w[at] \
            and t[at + 2:] == w[at + 2:]
    return len(w) - len(t) == 1 and at < len(t) and w[:at] + w[at + 1:] == t


def one_typo_off(line: str) -> dict[str, tuple[str, str]]:
    """t471 (his ANSWER 2026-10-13T13:51:24Z): the cards his line asks for once one typo is put
    right, each with the word as meant and the line as if typed right; empty where none. A word
    of 6+ letters one typo (`_one_off`) from a list word (`LIST_WORDS`), or one swap of two
    neighbours from a word a list's pattern takes (the sheet's own "dependecies" typed with a
    swap), counts as that word only where the line read that way asks first (`ROUTES`) for
    another card than the line as typed (R3: "what changed" for a misspelt dependency). Exact
    matching always wins: a word a list matches, on its own or in his line, is never put right."""
    asked = _routes(line)
    meant: dict[str, tuple[str, str]] = {}
    for found in TYPO_WORD.finditer(line):
        if found[0].lower() in LIST_WORDS or _routes(found[0]) \
                or _routes(line[:found.start()] + line[found.end():]) != asked:
            continue  # a list matches this word as typed, alone or in his line
        typed = found[0]
        swaps = [typed[:i] + typed[i + 1] + typed[i] + typed[i + 2:] for i in range(len(typed) - 1)
                 if typed[i] != typed[i + 1]]
        near = [w.capitalize() if typed[:1].isupper() else w
                for w in sorted(LIST_WORDS) if _one_off(typed, w)]
        for word in dict.fromkeys(near + swaps):
            right = line[:found.start()] + word + line[found.end():]
            cards = _routes(right)
            if cards and cards[:1] != asked[:1]:
                meant.setdefault(cards[0], (word, right))
    return meant


def _cells_said(cells: list[tuple[str, str]], hours: list[str]) -> str:
    """t413: grid cells in words: "high at 72 h and 168 h", or each its own level. t433 r2: a run
    of consecutive `hours` (the record's horizons) with one level reads as a range, "low from 2 h
    to 8 h"; a lone hour stays "low at 2 h"."""
    runs: list[list[tuple[str, str]]] = []
    for h, v in cells:
        if runs and runs[-1][-1][1] == v and hours.index(runs[-1][-1][0]) + 1 == hours.index(h):
            runs[-1].append((h, v))
        else:
            runs.append([(h, v)])
    levels = {v for _, v in cells}
    if len(levels) == 1 and all(len(r) == 1 for r in runs):
        return f"{levels.pop()} at {_listed([h for h, _ in cells])}"
    return _listed([f"{r[0][1]} from {r[0][0]} to {r[-1][0]}" if len(r) > 1
                    else f"{r[0][1]} at {r[0][0]}" for r in runs])


def _scale_words(method: dict[str, Any]) -> dict[int, str]:
    """t433 r2: the method's scale, each level's word (`severity_scale`: 1 none … 5 very high)."""
    return {s["level"]: s["label"] for s in method.get("severity_scale") or []}


def grid_mismatches(folder: Path, activity: str,
                    method: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """t601 (fact, "mismatches"): this year's interview (`this_years_interview`) against last
    year's record, cell by cell, as data: each record category with a rated cell this year rates
    otherwise (`moved`: its cells now, by the method's scale words, and then, and the record's
    `hours`); the categories that match (`same`); the `knock_on` where the MTPD this year's grid
    gives (`impact.mtpd_reading`) no longer sits above the record's RTO; and each band the record
    rates in no category that this year rates (`unrated`). None where either year has no grid."""
    method = walk._method(folder) if method is None else method
    grid, when = this_years_interview(folder, activity, method)
    prior = last_year(folder, activity)
    rows = prior.get("grid") or {}
    if not grid or not rows:
        return None
    moved, same, words = [], [], _scale_words(method)
    for name, row in rows.items():
        now = grid.get(name.split()[0].lower()) or {}
        cells = [(h, v) for h, v in row["cells"].items() if v in GRID_LEVELS
                 and now.get(h) is not None and now[h] != GRID_LEVELS.index(v) + 1]
        if cells:
            moved.append({"category": name, "hours": list(row["cells"]), "then": cells,
                          "now": [(h, words.get(now[h], str(now[h]))) for h, _ in cells]})
        else:
            same.append(name)
    figures = prior.get("figures") or {}
    horizon = impact.mtpd_reading(grid, method)["horizon"]
    rto = figures.get("RTO")
    held, gives = duration.worst_case(rto), duration.worst_case(horizon)
    knock_on = {"mtpd": horizon, "was": figures.get("MTPD"), "rto": rto} \
        if horizon != impact.NO_MTPD and held is not None and gives is not None and held >= gives \
        else None
    bands = [h for h in next(iter(rows.values()))["cells"]
             if not any(row["cells"].get(h) in GRID_LEVELS for row in rows.values())]
    unrated = [(h, [words.get(v, str(v)) for v in now]) for h in bands
               if (now := sorted({r[h] for r in grid.values() if r.get(h) is not None}))]
    return {"when": when, "record": prior.get("record") or prior.get("ref"), "moved": moved,
            "same": same, "knock_on": knock_on, "unrated": unrated}


def mismatches_said(folder: Path, activity: str, method: dict[str, Any]) -> str | None:
    """t413 (A5): what this year's interview does not match in last year's record, by code
    (t601: `grid_mismatches`' data): each moved category (`MISMATCH_ROW`), its count, and the
    knock-on on the record's RTO; then the categories that match; then (r2) each band the record
    rates in no category that this year rates, said to be no change. None where either year has no
    grid. t433 r2: this year's ratings by the method's scale words, runs as ranges
    (`_cells_said`)."""
    if (found := grid_mismatches(folder, activity, method)) is None:
        return None
    record, knock = found["record"], found["knock_on"]
    moved = [MISMATCH_ROW.format(category=m["category"], now=_cells_said(m["now"], m["hours"]),
                                 then=_cells_said(m["then"], m["hours"]), record=record)
             for m in found["moved"]]
    if knock:
        moved.append(MISMATCH_KNOCK_ON.format(mtpd=knock["mtpd"], was=knock["was"] or "none",
                                              rto=knock["rto"]))
    n = len(moved)
    lines = [MISMATCH_HEAD.format(name=_said_name(folder, activity), when=found["when"],
                                  record=record), ""]
    lines += [MISMATCH_COUNT.format(n=drafting.NUMBER_WORDS.get(n, str(n)).capitalize(),
                                    es="es" * (n > 1)), *moved] if moved else [MISMATCH_NONE]
    if found["same"] and moved:
        lines += ["", MISMATCH_SAME.format(categories=_listed([x.lower() for x in found["same"]]))]
    said = [MISMATCH_UNRATED.format(band=h, now=" and ".join(now)) for h, now in found["unrated"]]
    return "\n".join([*lines, *([""] if said else []), *said])


def unrated_last_year(folder: Path, activity: str) -> dict[str, list[str]]:
    """t725 (fact, "unrated_last_year"): the hours of last year's grid whose cell holds "–", by
    class, as the grid heads them ("1 h": 652 reads that form). A cell rated "none" is rated. Empty
    where every cell is rated, or the record states no grid."""
    rows = last_year(folder, activity).get("grid") or {}
    return {name: hours for name, row in rows.items()
            if (hours := [h for h, v in row["cells"].items() if v == ""])}


def _with_risk_rows(fact: Callable[[Path, str], dict[str, Any]]
                    ) -> Callable[[Path, str], dict[str, Any]]:
    """739: the fact as the model gets it, `risk_controls`' rows last. The join is here because
    `risk_controls` calls `dependencies`, and the check stack reads both functions as they stand."""
    return lambda folder, activity: {**fact(folder, activity),
                                     "risk_controls": risk_controls(folder, activity)}


#: t601 (ADR-0061 decision 2, map F4): the facts nemo computes, by the name the ticket gives each:
#: every one returns values (dicts, lists, booleans, numbers, a file's own words), never a sentence
#: of nemo's; the text wrappers above call them. `due` and `next_bia` take the room, the rest the
#: room and an activity; t631's `weekday` the room and the word.
FACTS: dict[str, Callable[..., Any]] = {
    "compare": compare, "mismatches": grid_mismatches, "gap_owners": gap_owners,
    "mtpd_reading": mtpd_reading_now, "last_participants": last_participants, "invitees": invitees,
    "due": due, "next_bia": next_review, "spof": _with_risk_rows(spof),
    "dependencies": _with_risk_rows(dependencies), "quotes": quotes, "focus": focus,
    "weekday": weekday_date, "risk_controls": risk_controls,
    "unrated_last_year": unrated_last_year}


def process_map_order(folder: Path, names: list[str]) -> list[str]:
    """t108 (14_nemo_check's ruling b): the room's order, the process map's. A process the map does
    not list (an added one, or a room with no map) follows, in the order it came."""
    keys = [{_map_key(r.name), _map_key(r.slug)} for r in process_map_rows(folder)]
    at = {n: next((i for i, k in enumerate(keys) if _map_key(n) in k), len(keys)) for n in names}
    return sorted(names, key=lambda n: at[n])


#: t475 (S1, his "Derived from the answer"): what changed, answered from this year's interview
#: (`changes_block`), and the line code says where the activity has none since last year's record
CHANGED_KIND, NOT_COMPARED_KIND = "changed", "not_compared"
NOT_COMPARED_SAID = ("{activity} has no interview since last year's record, so there is nothing "
                     "yet to compare it with.")
#: t475: what changed asks the one interviewed, by function, a referral that drafts a message;
#: and compares with last year, as code's A5 answer does (`mismatches_said`), his line drawn for him
ASK_INTERVIEWEE = "Ask the {function}" + MAIL_MARK
COMPARE_TAP = "Compare with last year"
COMPARE_LINE = "What does not match last year's record for {activity}?"
#: t475: the next BIA's briefing (B7's card) and whom to invite to it (B3's), each his line drawn
#: for him; never the invitation itself, which is B8's own answer (t457's cards)
BRIEF_TAP, BRIEF_LINE = "Its briefing", "Prepare a briefing to print for {activity}."
WHO_TAP, WHO_LINE = "Who to invite", "Who should I invite to {activity}'s interview?"
#: t475 (S1): each code-drawn answer's own next steps, by its card kind, each drawn only where its
#: data holds (`Session._kind_step`); a kind not here draws ADR-0045's kinds, as before
KIND_STEPS: dict[str, tuple[str, ...]] = {
    CHANGED_KIND: ("ask", "compare"),
    NOT_COMPARED_KIND: ("start", "who"),
    DEPENDENCY_KIND: ("chain", "write", "start"),
    NEXT_KIND: ("start", "brief"),
    DOWN_KIND: ("write", "start"),
    WHO_DECIDES_KIND: ("write", "start"),
    MISMATCH_KIND: ("write", "start"),
    QUOTES_KIND: ("write", "start"),
    BRIEFING_KIND: ("start", "who"),
}
#: t478 (38_nemo_check's mockup, the ticket's placement): the sheet's 18 prompts in the walk's five
#: stages (`walk.SHORT_NAMES`), one table: the stage map draws it (`workspace`), and an answer to
#: one of them is at its stage (`Session.answer_stage`)
STAGE_PROMPTS: dict[int, tuple[str, ...]] = {
    walk.STAGE: ("B1", "B2", "B3", "B8"),
    walk.STAGE_2: ("B4", "B7", "A1", "A2"),
    walk.STAGE_3: ("A3", "A4", "A5", "A6", "B5", "B6"),
    walk.STAGE_4: ("A7", "A8"),
    walk.STAGE_5: ("A9", "B9"),
}
#: t478: the sheet prompt a code-drawn answer answers, by its card kind or its server set
ANSWERED: dict[str, str] = {
    "due": "B1", NEXT_KIND: "B2", BRIEFING_KIND: "B7", CHANGED_KIND: "A1", NOT_COMPARED_KIND: "A1",
    QUOTES_KIND: "A2", "chart": "A3", DOWN_KIND: "A4", MISMATCH_KIND: "A5", DEPENDENCY_KIND: "A6",
    RESOURCE_KIND: "B6", WHO_DECIDES_KIND: "A7",
}
#: t478: an answer's next steps by its stage, `KIND_STEPS`'s steps, only for an answer whose kind
#: has no entry there (39_nemo_check's one order)
STAGE_STEPS: dict[int, tuple[str, ...]] = {
    walk.STAGE: ("brief", "start"),
    walk.STAGE_2: ("compare", "start"),
    walk.STAGE_3: ("chain", "write", "start"),
    walk.STAGE_4: ("write", "start"),
    walk.STAGE_5: ("write", "start"),
}
#: t478: the stage map's page, which every answer's stage label opens on its stage; r2
#: (14_nemo_design's nit): the label ends in the mark of a link that opens a page
STAGE_MAP = "stage-map"
STAGE_OPENS = " ›"
#: t482 (R4, his 7 Oct rehearsal 00:13 and 00:17): a conflict he left unresolved waits for its
#: owner's answer. Its two taps, by the owner's function (`owner_said`), replace every other next
#: step until he finishes for now (`Session._taps_now`'s one order); either puts the question to the
#: owner (`walk.refer`), so 372's badge counts it. Finishing is recorded in the activity's state
#: (`PENDING_ANSWERS`, the conflict ids), so the walk goes on as before when he comes back.
PENDING_KIND = "pending"
PENDING_WRITE = "Write to the {function}" + MAIL_MARK
PENDING_FINISH = "Finish for now, pending answer"
PENDING_ANSWERS = "pending_answers"
#: r2: each side said for what it is (`_pending_sides`), the activity by its own name
PENDING_SAID = ("This stays open until the {function} says which figure is right: {sides}. Write "
                "to the {function}, or finish for now; {activity} then shows it is waiting for the "
                "answer.")
#: r2: where the write tap truly puts it (`walk.refer` + `write_follow_up`), no mailbox draft
ON_FOLLOW_UP = "on the follow-up list in Your documents, as a draft; it never sends it."
PENDING_WRITTEN = "Referred to the {function}. nemo put the question " + ON_FOLLOW_UP
#: t482: nemo's own line when he asks for a message while the conflict's taps are drawn (t366's)
PENDING_DRAFT = ("Yes, nemo can draft that: tap “{tap}” below. nemo puts the question "
                 + ON_FOLLOW_UP)
PENDING_FINISHED = ("Finished for now. {activity} is waiting for the {function}'s answer, and its "
                    "BIA shows it. Pick it up here when the answer comes.")
#: the referral each open conflict leaves, as `walk.refer` words it ("<activity>, <item>: <words>")
PENDING_ITEM = "open conflict"
PENDING_ASK = "Which should the record carry: {sides}?"


def owner_said(folder: Path, activity: str) -> str:
    """t482: the activity's owner by function, as the organisation file gives it (`words.people`
    of `_decides`' person), else the role his interview gives him (else "process owner")."""
    role, name = _decides(folder, activity)
    return words.people(folder).get(name) or role


#: t475 (row 35): his line asks for the people responsible or the owners, so a finding the room
#: holds draws the write tap, as his write ask does
PEOPLE_ASKED = re.compile(r"\bresponsible\b|\bowners?\b", re.I)


def next_step_room(folder: Path, model: str) -> list[offer.Activity]:
    """t108: the room as `nemo.next_step` reads it, in the process map's order. Each activity's own
    files are its interviews, its run and its documents; its figures are the room sheet's; its gap
    is the referee's rule (`gap_reading`, t156), never a second reading."""
    method = walk._method(folder)
    rows = {r["activity"]: r for r in room_sheet(folder, model)}
    out = []
    for name in process_map_order(folder, list(rows)):
        mtpd, rto = (rows[name]["figures"].get(k, {}).get("value") for k in ("MTPD", "RTO"))
        own = {p for home in interview.HOMES for p in interview.paths_about(folder, home, name)}
        own |= {walk.run_file(name), f"output/{slug(name)}/"}
        out.append(offer.Activity(name=name, files=frozenset(own), mtpd=mtpd, rto=rto,
                                  gap=needs_gap({"recovery_target": rto, "mtpd": mtpd}, method)))
    return out
#: The pick card's one tap beyond the room's activities (t72), and what the server asks after it.
ANOTHER = "Another activity…"
ASK_NAME = "Which activity? Type its name, the way you want it in the BIA."
#: nemo's own offer at stage 2 when no interview is on file, and the tap that keeps the one held.
HOLD_IT_NOW = walk.HOLD_IT_NOW
KEEP_INTERVIEW = "Confirm this interview"
#: t82 (the owner's "Accept it", 2026-09-21): a draft written on his turn is allowed to be slow, and
#: says so before it starts (`Session._draft`, fix 3). Honest to the saved confirm-time rebuilds,
#: counted per rebuild he waits for (one distinct draft file each, its `meta.seconds`, a redraft
#: included; t82-review.md 08:24): 28 rebuilds, median 74 s, 13 under a minute, 20 under two, 4 at
#: three or more, worst 662 s. So never "a few seconds". The words are for him to rule.
DRAFTING = (
    "Writing the draft for {activity} from your interview: it usually takes a minute or two, "
    "sometimes several."
)
#: fix 3: the same wait with no draft yet to rebuild: what it is drafted from is then whatever the
#: room holds, not always his interview, so this line does not claim it
DRAFTING_FIRST = (
    "Writing the draft for {activity}: it usually takes a minute or two, sometimes several."
)


def drafting_line(activity: str, first: bool = False) -> str:
    return (DRAFTING_FIRST if first else DRAFTING).format(activity=activity)
#: ticket 182 (re-cut): a guidance answer that has not come back yet, said once while he waits.
#: Beside DRAFTING because it is the same kind of line: his question, the plain fact that it is
#: slower than usual, no wait invented and nothing about a model, a provider or a count of tries.
STILL_WORKING = "Still working on your question: this one is taking longer than usual."
#: When it is said. His number, from ADR-0036's dated note of 2026-09-28 ("an answer not back after
#: about 15 s makes the room say, once, that it is still being worked on"), beside the 80 s x 1 wait
#: of ticket 198. A time cap of his is recorded, never tuned: tests patch this rather than wait.
STILL_WORKING_AFTER_SECONDS = 15
#: The server's tap under every interview question: ends it, and is never filed as an answer.
STOP_INTERVIEW = "Stop the interview"


def render_sheet(rows: list[dict[str, Any]], heading: str = "Where the room stands") -> str:
    # every line ends in a full stop, so each is a sentence of its own, about its own activity
    lines = [f"**{heading}** · read from the room's files just now.", ""]
    for r in rows:
        if r["signed"]:
            step, state = "all 5 steps through", "record accepted and signed"
        else:
            step = f"at step {r['step']} of 5" if r["started"] else "not started"
            state = ("record accepted before it was reopened, not signed" if r.get("reopened") else
                     "record accepted, not signed" if r["record"] else "no record yet; not signed")
        walked = "being drafted" if r.get("being_drafted") else "can be walked" if r["walkable"] \
            else f"can't be walked ({'; '.join(r['why_not'])})"
        figs = "; ".join(
            (
                f"{k} {f['value']} ({f['mark']}" + (f" · {f['why']})" if f.get("why") else ")")
                if f["value"]
                else NO_RPO
                if f.get("no_rpo")
                else f"{k} not known yet"
            )
            + (f", {f['now'] or 'not known yet'} now proposed" if "now" in f else "")
            for k, f in r["figures"].items()
        )
        lines.append(f"- **{r['activity']}** · {walked}; {step}; {state}; {figs}.")
    cmp_ = by_mtpd(rows)
    lines += ["", "**By MTPD**, the method's measure of how soon each becomes intolerable, "
                  "tightest first (tied rows share a place)."]
    for place, group in enumerate(cmp_["places"], 1):
        for g in group:
            lines.append(f"{place} · {g['activity']} · MTPD {g['mtpd']} ({g['mark']})"
                         + (" · tied" if len(group) > 1 else "") + ".")
    lines += [f"– · {n} · MTPD not known yet." for n in cmp_["not_known_yet"]]
    lines += ["", "Which one is most critical is your call; this list only orders them."]
    if heading == PICK_HEADING:  # t72: the structural route to an activity the files don't list
        lines += ["", f"To start one the files don't list, tap **{ANOTHER}** and type its name."]
    return "\n".join(lines)


#: t96 (ADR-0023 decision 6): the greeting is one or two sentences, drawn by nemo, the company named
#: from the room's own files. Drafted; his to approve (the report's "For the owner").
GREETING = "I've read {company}'s files. Ask me anything, or say when you want to start a BIA."
#: t253 (his round 2 Q2, "no default"): a room with a process map is greeted with its core
#: processes in the map's order, and he picks; still two sentences (ADR-0023 d6)
GREETING_CORE = (
    "I've read {company}'s files: your core processes are {processes}. "
    "Which shall we start the BIA on, or ask me anything?"
)
GREETING_UNDER_WAY = (
    "I've read {company}'s files, and the BIA for {activity} is at stage {stage} of 5. "
    "Ask me anything, or say when you want to carry on."
)
#: a legal form after a company's name, in the words registers use for one (not any one company's)
_LEGAL_FORM = re.compile(
    r"\s+(?:GmbH|AG|SE|KG|KGaA|OHG|UG|e\.V\.|Ltd\.?|Limited|LLP|LLC|Inc\.?|Corp\.?|plc|"
    r"S\.A\.|S\.p\.A\.|S\.r\.l\.|SARL|B\.V\.|N\.V\.|&\s*Co\.?)(?=\s|,|$).*$"
)


def company_name(folder: Path) -> str:
    """The company as a colleague says it: the method file's `org`, without its legal form."""
    try:
        org = str(json.loads((Path(folder) / walk.METHOD).read_text()).get("org") or "")
    except (OSError, ValueError):
        org = ""
    return _LEGAL_FORM.sub("", org).strip(" ,") or "the company"


def core_processes(folder: Path) -> list[str]:
    """t253: the process map's core processes (its section-1 rows, `1.x`, read through
    `process_map_rows`) in its order, as a sentence says them (a capital is kept where the next
    letter is one too, so "IT ..." stays)."""
    return [_as_said(r.name) for r in process_map_rows(folder) if r.number.startswith("1.")]


def _as_said(name: str) -> str:
    """A process's name as a sentence says it ("IT ..." keeps its capital, t253)."""
    return name if name[1:2].isupper() else name[:1].lower() + name[1:]


def greeting(folder: Path) -> str:
    """t96: nemo's own opening line, from the room's files: the company, and a BIA under way.

    151: a run with no decision is not under way. The seed ships one per process at stage 1 on
    purpose (ADR-0011), so a fresh room greets as fresh until he has decided something."""
    for a in process_map_order(folder, walk.processes(folder)):
        run = walk.read_record(folder, walk.run_file(a)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        if run.get("stage") and run.get(walk.DECISIONS) and run.get("status") != walk.CLOSED:  # type: ignore[attr-defined]  # walk re-exports DECISIONS
            # 347: the process map's name word for word ("One-off …"), never the slug a walk keys
            # it on; a process the map does not list reads as its own words (`map_name`)
            name = named if (named := process_name(folder, a)) != a else map_name(folder, a)
            return GREETING_UNDER_WAY.format(company=company_name(folder), activity=_as_said(name),
                                             stage=walk.current(folder, a).stage)
    if names := core_processes(folder):
        listed = (" and ".join(names) if len(names) < 3
                  else f"{', '.join(names[:-1])}, and {names[-1]}")
        return GREETING_CORE.format(company=company_name(folder), processes=listed)
    return GREETING.format(company=company_name(folder))


def pick_taps(rows: list[dict[str, Any]]) -> list[str]:
    """The activity pick's taps: one per walkable activity, in the room's own spelling."""
    return [r["activity"] for r in rows if r["walkable"]]


def core_pick(folder: Path, names: list[str]) -> list[tuple[str, str]]:
    """t312: the pick where the room's process map has core processes (its section-1 rows, 253):
    those of `names` it lists, in its order, each as (the map's name, the room's spelling). Every
    other activity is his through ANOTHER or its typed name. A room with no core row has none."""
    rows = [r for r in process_map_rows(folder) if r.number.startswith("1.")]
    return [(r.name, n) for r in rows for n in names
            if _map_key(n) in (_map_key(r.name), _map_key(r.slug))]


def pick_entries(folder: Path, names: list[str]) -> list[tuple[str, str]]:
    """t312b: the pick card's entries, its taps and its sheet alike: `core_pick`, or where the map
    has no core row each of `names` by the name the map gives it (a slug only where none does)."""
    return core_pick(folder, names) or [(process_name(folder, n), n) for n in names]


def pick_sheet(folder: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """t312b: the pick card's sheet lists what its taps offer: the room sheet's `rows` for
    `pick_entries`, in their order, each under the name its tap shows."""
    by_name = {r["activity"]: r for r in rows}
    return [{**by_name[n], "activity": label} for label, n in pick_entries(folder, pick_taps(rows))]


def filed_as(folder: Path, name: str) -> str:
    """t312: a typed name the process map gives a row ("IT helpdesk and support") as the row's
    slug, so the room's own activity is opened, never added twice; any other name as typed."""
    key = _map_key(name)
    return next((r.slug for r in process_map_rows(folder) if _map_key(r.name) == key), name)


def drop_untraced(text: str, figures: list[str]) -> tuple[str, list[str]]:
    """t377 F2: (the text without each sentence that holds one of `figures`, those sentences). A
    figure the check cannot trace takes its whole sentence with it, so what is shown never carries
    a marker mid-sentence."""
    if not figures:
        return text, []
    return _drop_sentences(
        text, re.compile("|".join(rf"(?<!\d){re.escape(f)}(?!\d)" for f in figures)))


#: t413 (M13): a model sentence telling him to tap (press, click) a label it quotes, bold or not
TAP_QUOTED = re.compile(r"\b(?:tap|press|click)\w*\W+(?:on\W+)?[\"“‘']\s*"
                        r"(?P<label>[^\"”’'\n]+?)\s*[\"”’']", re.I)


def _counts(text: str) -> set[str]:
    """t413: the counts and figures `text` states (`_figures`), the word "one" aside: it is an
    article or a pronoun as often as a count ("the one tap"). t429: a date ("9 Nov 2026") states
    none, so a card's "9 Nov" never vouches for a model's "Nine others"."""
    return {_NUMBER_WORDS.get(w.lower(), w) for w in _NUMBER.findall(_DATE_SAID.sub(" ", text))
            if w.lower() != "one"}


#: t413 r3: words inside double quotation marks, straight or curly
QUOTED = re.compile(r"[\"“„](?P<words>[^\"“”„\n]+)[\"”“]")


def _unquoted(text: str) -> str:
    """t413 r3: `text` with its whitespace collapsed and every quotation mark made straight."""
    return " ".join(re.sub(r"[“”„]", '"', re.sub(r"[‘’]", "'", text)).split())


def _as_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("*", "")).strip().lower()


#: t413 r4: a rating (a level number, its word, or both: "4 (high)") at one hour or more ("72 h and
#: 168 h")
RATED_AT = re.compile(
    rf"\b(?P<rating>\d(?:\s*\((?:{'|'.join(GRID_LEVELS)})\))?|{'|'.join(GRID_LEVELS)})\s+at\s+"
    r"(?P<hours>\d+\s*h(?:ours?)?\b(?:\s*(?:,|and|or)\s*\d+\s*h(?:ours?)?\b)*)", re.I)


def _rated(text: str, classes: list[str]) -> set[tuple[str, str, str]]:
    """t413 r4: (impact class, rating, hour) for each rating `text` ties to an hour (`RATED_AT`),
    the class the nearest of `classes` named before it in its sentence ("" where none is); a
    rating in both forms ("4 (high)") stands for each."""
    out = set()
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        for m in RATED_AT.finditer(sentence):
            named = max(((n.start(), c) for c in classes
                         for n in re.finditer(rf"\b{re.escape(c)}", sentence[:m.start()], re.I)),
                        default=(-1, ""))[1].lower()
            out |= {(named, r.lower(), h) for r in re.findall(r"\w+", m["rating"])
                    for h in re.findall(r"\d+", m["hours"])}
    return out


def drop_undrawn(text: str, labels: list[str], drawn: list[str],
                 served: list[str] | None = None,
                 cited: list[str] | None = None,
                 classes: list[str] | None = None) -> tuple[str, list[str]]:
    """t413 (M13): (the model's text without each sentence that names a tap code did not draw this
    turn (`TAP_QUOTED`: its quoted words are in none of `labels`), or, where code drew a card or a
    block this turn (`drawn`), a count or figure (`_counts`) that none of it nor of `labels` states;
    those sentences). It compares with what code drew, never with a list of words. With nothing
    drawn but taps, the figure check (`Session._flag`) is the one on figures. As there (t64 fix
    1b), the digits inside a name nemo serves (`served`) count only inside that whole name. r3: a
    figure inside quotation marks counts as drawn only where the quoted words stand verbatim in
    one of the files the turn could cite (`cited`, `cited_files`); never a blanket quote pass. r4: a
    rating tied to an hour (`_rated`) counts as drawn only where code states that rating at that
    hour, for the impact class (of `classes`, the method's) the sentence names; hours and counts
    alone keep the count rule."""
    taps = [_as_label(x) for x in labels]
    have = _counts("\n".join([*drawn, *labels])) if drawn else None
    pairs = _rated("\n".join([*drawn, *labels]), classes or [])
    pairs |= {("", r, h) for _, r, h in pairs}
    names = sorted(served or [], key=len, reverse=True)

    def undrawn(sentence: str) -> bool:
        if any(not any(_as_label(m["label"]) in tap for tap in taps)
               for m in TAP_QUOTED.finditer(sentence)):
            return True
        for name in names:
            sentence = sentence.replace(name, " ")
        sentence = QUOTED.sub(lambda m: " " if any(_unquoted(m["words"]) in f for f in cited or [])
                              else m[0], sentence)
        return have is not None and bool(_counts(sentence) - have
                                         or _rated(sentence, classes or []) - pairs)

    return _drop_sentences(text, undrawn) if text else (text, [])


#: t514 (M13): the scope turn's keep taps (`Session._interview_taps`), and the counts they state
KEEP_TAPS = re.compile(r"^Keep (?:these|all) (\d+) interviews$|^Keep th(?:is|e) interview$")
#: t514: a count of interviews a sentence states: a number before "interviews" ("Three interviews
#: touch …") or after a keep ("I'd keep those three")
INTERVIEW_COUNT = re.compile(rf"(?P<n>{_NUMBER.pattern})(?:\s+[\w'’-]+){{0,3}}?\s+(?:re-?)?"
                             rf"interviews\b|\bkeep\w*\s+(?:(?:those|these|the|all|them)\s+)*"
                             rf"(?P<k>{_NUMBER.pattern})", re.I)


def drop_interview_counts(text: str, labels: list[str]) -> tuple[str, list[str]]:
    """t514 (M13): on the scope turn (a keep tap among `labels`, `KEEP_TAPS`), (the model's text
    without each sentence stating a count of interviews (`INTERVIEW_COUNT`) that no keep tap
    states; those sentences), so only code's "Keep these <n> interviews" count shows. Any other
    turn's text is untouched. As `_counts`, the word "one" is no count ("each one of the
    interviews")."""
    keeps = [m for x in labels if (m := KEEP_TAPS.match(x))]
    if not keeps or not text:
        return text, []
    have = {m[1] or "1" for m in keeps}
    return _drop_sentences(text, lambda x: any(
        (n := (m["n"] or m["k"]).lower()) != "one" and _NUMBER_WORDS.get(n, n) not in have
        for m in INTERVIEW_COUNT.finditer(x)))


#: t377 F3: a room folder no reply ever names (11_marschkamp: the evaluation's synthetic files)
NEVER_NAMED = "09_Evaluation/"
#: an interview's file name opens on its date, YY_MM_DD
_DATED = re.compile(r"(\d\d)_(\d\d)_(\d\d)_")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
#: t429: a date as a card or a reply says it, its year optional ("9 Nov", "24 September 2024")
_DATE_SAID = re.compile(rf"\b\d{{1,2}}\s+(?:{'|'.join(_MONTHS)})[a-z]*\.?(?:\s+\d{{4}})?\b")


#: t434 (M13): a send or reply state a sentence claims: a reply had or missing, a mail sent. nemo
#: never sends and reads no inbox, so only a line code wrote can hold one.
MAIL_STATE = re.compile(r"\b(?:replied|no repl(?:y|ies)|unanswered|heard back|got back|sent)\b",
                        re.I)
#: t434: "nothing is sent", "not been sent": nemo's own rule (it never sends), so never a claim
NOT_SENT = re.compile(r"\b(?:not|never|nothing|no|\w+n['’]t)\b(?:\W+\w+){0,3}?\W+sent\b", re.I)
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
#: t434: a day a sentence sets as a deadline ("by Monday", "before Tuesday, 17 Nov 2026")
DEADLINE = re.compile(
    rf"\b(?:by|before|until|till|no later than)\s+(?:(?:next|this|the coming)\s+)?"
    rf"(?:(?P<weekday>{'|'.join(_WEEKDAYS)})(?:,?\s+(?P<date>{_DATE_SAID.pattern}))?"
    rf"|(?P<on>{_DATE_SAID.pattern})|tomorrow|tonight|today|the weekend"
    r"|the end of (?:the |this |next )?(?:day|week|month))", re.I)
#: t434: a day or a month, whole or short ("Tue", "Nov"): DEADLINE's to judge, never a name
_DAY_WORD = re.compile(rf"\b(?:{'|'.join(d[:3] for d in _WEEKDAYS)}|{'|'.join(_MONTHS)})[a-z]*\b")
#: t434: what a name's first word follows when it opens a sentence, a line, a cell or a clause
_OPENS = re.compile(r"[|:;(—–\"“\n]|\*\*|[.!?]['’\"”]?\s")  # a full stop: inside a quotation
#: t434 r2: what a "sent" is a claim about: a mail, a draft or an invitation ("Barsch sent
#: apologies" is the interview's, never a send state)
_MAILED = re.compile(r"\b(?:e-?mails?|mails?|drafts?|invit(?:ation|e)s?)\b", re.I)
#: t434 r2: a title before a name ("Herr Harder"): the name after it is what the files must hold
_TITLE = re.compile(r"\b(?:Herr|Frau|Mrs?|Ms|Dr|Prof)\b\.?(?=\s+[^\W\d_])")
#: t434 r2: a heading, its words capitalised anyway: a line's "#" heading, or the bold span opening
#: a line ("**BIA Briefing · Raw material procurement** · for printing")
_HEADING = re.compile(r"#+\s.*|\*\*[^*\n]+\*\*")
#: t434 r2: what closes a name standing whole ("**Holger Brüning** —", a cell, a bracket), never
#: a word, a comma or a possessive running on ("Comparing Barsch's", "Dear Mr Sobotta,")
_WHOLE = r"\s*(?:\*\*|\||\(|[—–]|$)"
#: t434: a room file whose words are names the room holds
_TEXT_FILES = (".md", ".json", ".txt", ".csv")


def room_text(folder: Path) -> str:
    """t434: the room's company files (`room_files`), as one text."""
    return "\n".join((folder / r).read_text(errors="replace") for r in room_files(folder)
                     if r.endswith(_TEXT_FILES))


def _day_month(text: str) -> set[tuple[str, str]]:
    """t434: each date `text` states (`_DATE_SAID`), as (day, month's first three letters)."""
    return {(m[0].split()[0], m[0].split()[1][:3].lower()) for m in _DATE_SAID.finditer(text)}


def _edits(a: str, b: str) -> int:
    """t434: how many letters `a` is off `b` (inserted, left out or changed)."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row, last = [i], row
        for j, y in enumerate(b, 1):
            row.append(min(last[j] + 1, row[j - 1] + 1, last[j - 1] + (x != y)))
    return row[-1]


def drop_unheld(text: str, known: str, code: str,
                today: datetime.date | None = None) -> tuple[str, list[str]]:
    """t434 (M13): (the model's text without each sentence that names a firm, a person or a place
    whose name stands nowhere in `known` (the room's files, his lines, the tools' results and
    code's lines), or that claims a send or reply state (`MAIL_STATE`) no line code wrote
    (`code`) states, or a deadline (`DEADLINE`) on a day neither holds; those sentences). A name
    is a word written with a capital, an acronym aside, compared with the words `known` holds,
    never with a list; a word opening a sentence, a line, a cell or a clause (`_OPENS`) is
    capitalised anyway, so there it is a name only one or two letters off one `known` writes
    ("Westergoo" for Westerkoog). A bare weekday is the next one after `today` (the story's day,
    `story_today`). A quotation standing word for word in `known` is the file's (413 r3).
    t434 r2: a title ("Herr") is no name; a heading's words (`_HEADING`) count as opening ones,
    though two unknown capitalised words side by side there are a name ("Ines Thiel"); an unknown
    word before a surname `known` writes after a first name, the two standing whole (`_WHOLE`), is
    an invented first name ("Holger Brüning" where the files hold Kai Brüning); a "sent" claims a
    send state only beside a mail, a draft or an invitation (`_MAILED`), and a question (an offer:
    "Want this sent?") none."""
    written = set(re.findall(r"[^\W\d_]+", known))
    words = {w.lower() for w in written}
    names = {w for w in written if w[0].isupper() and w.lower() not in written}  # never lower case
    surnames = {b for a, b in re.findall(r"([^\W\d_]+) (?=([^\W\d_]+))", known)
                if a in names and b[0].isupper()}  # the second word of a full name the files hold
    plain = _unquoted(known)
    held = {m[0].lower() for m in MAIL_STATE.finditer(NOT_SENT.sub(" ", code))}
    dates = _day_month(f"{known}\n{code}")
    said = f"{known}\n{code}".lower()

    def new(w: str) -> bool:
        return w[0].isupper() and w[2:] != "" and not w.rstrip("s").isupper() \
            and w.lower() not in words

    def unknown(m: re.Match[str]) -> bool:
        w, head = m[0], _HEADING.match(m.string)
        if not new(w):
            return False
        if not (head and m.end() <= head.end()) and re.search(
                r"[^\W\d_]", _OPENS.split(m.string[:m.start()])[-1]):
            return True  # within a clause: a capital there is a name
        after = re.match(r"\s+([^\W\d_]+)", m.string[m.end():])
        if after and after[1] in surnames and re.match(_WHOLE, m.string[m.end() + after.end():]):
            return True  # a first name the files lack on a seed surname, the name standing whole
        if head and m.end() <= head.end() and any(
                new(n[1]) for n in (after, re.search(r"([^\W\d_]+)\s+$", m.string[:m.start()]))
                if n):
            return True  # two unknown capitalised words side by side in a heading: a name
        return w[4:] != "" and any(  # never one of its own forms ("Thanks" for Thank)
            n[:2] == w[:2] and not (w.startswith(n) or n.startswith(w))
            and _edits(w, n) <= len(w) // 4 for n in names)

    def day_held(m: re.Match[str]) -> bool:
        if m["date"] or m["on"]:
            return bool(_day_month(m["date"] or m["on"]) & dates)
        if m["weekday"] and today:
            ahead = (_WEEKDAYS.index(m["weekday"].capitalize()) - today.weekday() - 1) % 7 + 1
            day = today + datetime.timedelta(days=ahead)
            return (str(day.day), _MONTHS[day.month - 1].lower()) in dates
        return m[0].lower() in said

    def unheld(sentence: str) -> bool:
        bare = _TITLE.sub(" ", _DAY_WORD.sub(" ", sentence))
        if any(unknown(m) for m in re.finditer(r"[^\W\d_]+", bare)):
            return True
        sentence = QUOTED.sub(lambda m: " " if _unquoted(m["words"]) in plain else m[0], sentence)
        claims = {m[0].lower() for m in MAIL_STATE.finditer(NOT_SENT.sub(" ", sentence))} - held
        if not _MAILED.search(sentence):
            claims.discard("sent")
        if claims and not sentence.rstrip(" *_\"”").endswith("?"):
            return True
        return not all(day_held(m) for m in DEADLINE.finditer(sentence))

    return _drop_sentences(text, unheld) if text else (text, [])


#: t449 (A8, run 2): a model sentence denying the room a tool it has (an e-mail tool, where the
#: room has the write tap): the room, nemo or "I" named as lacking it (`DENIED_BY`), and a no, none,
#: not, never, can't or n't (`DENIAL`) with, in the five words after it and before any send (nemo
#: never sends: "nemo never sends it" is true), what code's own matcher for one of the room's taps
#: reads (`Session._offered`); code then says the tap exists (`HAS_TAP`, 366's lines for the write)
DENIAL = re.compile(r"\b(?:no|none|not|never|cannot|without)\b|n['’]t\b", re.I)
DENIED_BY = re.compile(r"\b(?i:the|this) (?i:room)\b|\b(?i:nemo)\b|\bI\b")
HAS_TAP = "nemo can do that: tap “{tap}” below."


def drop_denials(text: str, offers: list[tuple[Callable[[str], Any], str]]
                 ) -> tuple[str, list[str], list[str]]:
    """t449: (the model's text without each sentence denying a tool of `offers` (each code's
    matcher for it and its tap's label), those sentences, and the labels denied)."""
    denied: list[str] = []

    def denies(sentence: str) -> bool:
        if not DENIED_BY.search(sentence):
            return False
        after = [re.split(r"\bsen[dt]", " ".join(sentence[m.end():].split()[:5]), flags=re.I)[0]
                 for m in DENIAL.finditer(sentence)]
        labels = [label for reads, label in offers if any(reads(a) for a in after)]
        denied.extend(x for x in labels if x not in denied)
        return bool(labels)

    text, gone = _drop_sentences(text, denies) if text else (text, [])
    return text, gone, denied


#: t530 (his room on Move 18: "Done — the invitation now says …", no tool called): a model sentence
#: claiming an action done (`CLAIMED`) on one of the room's tools, with no proposal, question or
#: no in it (`PROPOSES`, `DENIAL`), unless that tool ran this turn; code then says nothing changed
#: and draws the tap (`NOT_DONE`)
CLAIMED = re.compile(r"\b(?:done|changed|moved|updated|rescheduled|sent|put|placed|added|blocked"
                     r"|booked|drafted|created|saved)\b", re.I)
PROPOSES = re.compile(r"\b(?:can|could|will|would|shall|should|may|might|want|if)\b|['’]ll\b"
                      r"|\?\W*$", re.I)
NOT_DONE = "Nothing was changed: nemo has not done that. You can use “{tap}” below."


def drop_claims(text: str, offers: list[tuple[Callable[[str], Any], str, dict[str, Any] | None]],
                ran: list[str]) -> tuple[str, list[str], list[str]]:
    """t530: (the model's text without each sentence claiming an action on a tool of `offers`
    (code's matcher for it, its tap's label and call) that this turn's tools called (`ran`) does
    not hold, those sentences, and the labels claimed)."""
    claimed: list[str] = []

    def claims(sentence: str) -> bool:
        if not CLAIMED.search(sentence) or PROPOSES.search(sentence) or DENIAL.search(sentence):
            return False
        labels = [label for reads, label, call in offers if call and reads(sentence)
                  and call["kind"] not in ran]
        claimed.extend(x for x in labels if x not in claimed)
        return bool(labels)

    text, gone = _drop_sentences(text, claims) if text else (text, [])
    return text, gone, claimed


#: t548: a model sentence giving the point a class first shows impact ("no legal impact until
#: 168 h", "first impact at 8 h")
_FIRST_IMPACT = re.compile(r"\bno\b[^.!?]*\bimpact until\b|\bfirst impact at\b", re.I)


def first_above_none(row: dict[str, Any]) -> str | None:
    """t548: the first horizon ("8 h") at which a prior-grid row (`_prior_grid`) rates above none,
    in the record's own order; None where it rates none (or leaves blank) at every point."""
    return next((h for h, v in row["cells"].items() if v and v.lower() != "none"), None)


def drop_unheld_thresholds(text: str, grids: dict[str, dict[str, Any]]
                           ) -> tuple[str, list[str]]:
    """t548 (live B12), r2: (the model's text without each sentence 'no <class> impact until <h>'
    (or 'first impact at <h>') that the grid of the year it names does not bear out, those
    sentences). `grids` holds "this" (this year's, `_this_year_rows`) and "last" (last year's
    record, `_prior_grid`) where each exists, a row's first point above none by `first_above_none`.
    A sentence naming no year drops only if false in every grid that rates its class; one naming a
    year whose grid is absent, or naming no class of a grid, stays."""
    def lacks(sentence: str) -> bool:
        if not _FIRST_IMPACT.search(sentence) or not (at := re.search(r"(\d+)\s*h\b", sentence)):
            return False
        named = [y for y, w in (("this", r"\bthis year"), ("last", r"\blast year"))
                 if re.search(w, sentence, re.I)]
        verdicts = []
        for year in named if len(named) == 1 else grids:
            rows = [r for c, r in grids.get(year, {}).items()
                    if re.search(rf"\b{re.escape(c.split()[0])}\b", sentence, re.I)]
            if rows:
                verdicts.append(any(
                    (first_above_none(r) or "").split()[:1] != [at[1]] for r in rows))
        return bool(verdicts) and all(verdicts)

    return _drop_sentences(text, lacks) if text else (text, [])


def _this_year_rows(folder: Path, activity: str) -> dict[str, Any]:
    """t548 r2: this year's grid (`this_years_scores`, the interview's or its worded lines) as
    `first_above_none` reads a row: {class: {"cells": {horizon: "none" | "rated"}}}."""
    grid = this_years_scores(folder, activity, walk._method(folder))[0]
    return {c: {"cells": {h: "none" if v == 1 else "rated" for h, v in row.items()}}
            for c, row in grid.items()}


def drop_offered(text: str, reads: Callable[[str], Any], letters: bool = False
                 ) -> tuple[str, list[str]]:
    """t449 r2: where code draws an offered tap's line, (the model's text without each sentence
    the tool's own matcher `reads`, the tap being the one path; with `letters` (the write tap's)
    every paragraph from the model's first letter (a line `LETTER_OPENS` matches, t377c G3) to the
    end, its closing line with it; then a lead-in left ending on a colon, nothing under it;
    those dropped). Structural beside the matcher; no word list."""
    paragraphs = text.split("\n\n")
    start = next((n for n, p in enumerate(paragraphs) if letters and any(
        LETTER_OPENS.match(x) for x in p.split("\n"))), len(paragraphs))
    text, gone = _drop_sentences("\n\n".join(paragraphs[:start]), reads)
    gone = [*gone, *(p for p in paragraphs[start:] if p.strip())]
    head, _, tail = text.rpartition("\n")
    *kept, last = _sentences(tail)
    if gone and last.rstrip().endswith(":"):
        gone.append(last)
        text = re.sub(r"\n{3,}", "\n\n", f"{head}\n{' '.join(kept)}").strip()
    return text, gone


#: t377 N1: a saved run (`output/.bia-runs/<slug>.json`), titled by its process as the map names it
SAVED_RUNS = "output/.bia-runs/"
SAVED_RUN_TITLE = "the saved BIA run of {process}"


def file_title(folder: Path, relative: str) -> str:
    """t377 F3: a room file's plain title, from the file's own H1 (never the model): cut at ':',
    and at ' — ' only when what follows names the company (`company_name`) or describes the title
    ("the abbreviations in these files": N1, it opens on "the"); any other part after ' — ' is
    kept behind ", " (r3: "the business impact analysis, prior cycle 2024–2025", never the current
    BIA's name); an interview is its whole H1 "of" its date; a file with no H1 is its name in
    words ("the dependency register"), a dated interview's without its date and "of" it (Q); a
    saved run is `SAVED_RUN_TITLE`. N1: behind "the", a name
    (`_title_names`) or an acronym keeps its case and every other word goes lower case, the saved
    run's process too ("of access management"). r2 (12_marschkamp): a dated re-interview drops
    "<year> " ("the order picking re-interview of 2 Oct 2026"); an H1 "<company> — <rest>" reads
    "<company>'s <rest>", with no "the"."""
    name = relative.rpartition("/")[2]
    if relative.startswith(SAVED_RUNS) and name.endswith(".json"):
        try:
            slug = str(json.loads((folder / relative).read_text()).get("process") or "")
        except (OSError, ValueError):
            slug = ""
        first, _, rest = map_name(folder, slug or Path(name).stem).partition(" ")
        return SAVED_RUN_TITLE.format(
            process=f"{_as_titled(first, _title_names(folder))} {rest}".strip())
    lines = (folder / relative).read_text(errors="replace").splitlines()
    h1 = next((x[2:].strip() for x in lines if x.startswith("# ")), "")
    dated = _DATED.match(name)
    when = ""
    if dated and _an_interview(relative):
        yy, mm, dd = dated.groups()
        # r2 (b): the date says the year, so "<year> re-interview" loses its year; Q: with no H1
        # its name after the date, in words
        head = re.sub(r": \d{4} (re-interview)$", r" \1", h1).replace(": ", " ") if h1 \
            else Path(name[dated.end():]).stem.replace("-", " ")
        when = f" of {int(dd)} {_MONTHS[int(mm) - 1]} 20{yy}"
    else:
        first, _, rest = h1.split(":")[0].partition(" — ")
        if rest and f"{company_name(folder)} ".startswith(f"{first} "):
            # r2 (c): "<company> — <rest>" is the company's own: "Marschkamp's company files …"
            return f"{first}'s {rest}"
        if rest and not f"{company_name(folder)} ".startswith(f"{rest} ") \
                and not rest.startswith("the "):
            first = f"{first}, {rest.replace(' — ', ', ')}"
        head = first if h1 else Path(name).stem.replace("-", " ")
    names = _title_names(folder)
    return "the " + " ".join(_as_titled(w, names) for w in head.split()) + when


def _as_titled(word: str, names: set[str]) -> str:
    """t377 N1: a title's word as written where it is one of `names` (`_title_names`) or an
    acronym, else lower case."""
    keep = word.strip("(),.") in names or (len(word) > 1 and word.isupper())
    return word if keep else word.lower()


def _title_names(folder: Path) -> set[str]:
    """t377 N1 (12_marschkamp): the words a title keeps capitalised as names: those of the
    company (`company_name`) and of the register's sites (`walk.sites`), as they are written."""
    named = [company_name(folder), *walk.sites(drafting.read_register(folder))]
    return {w for n in named for w in re.findall(r"[\w-]+", n) if w[:1].isupper()}


def plain_titles(text: str, folder: Path) -> tuple[str, list[str]]:
    """t377 F3: (the text with each room file named by its plain title, the sentences dropped). A
    file name the model writes ("From the bia-programme-plan.md") reads "From the BIA programme
    plan"; a sentence naming `NEVER_NAMED` is dropped whole."""
    named = [r for r in room_files(folder) if "/" in r and r.endswith((".md", ".json"))]
    hidden = [r for r in named if r.startswith(NEVER_NAMED)]
    dropped: list[str] = []
    if hidden:
        names = [NEVER_NAMED.rstrip("/"), *(r.rpartition("/")[2] for r in hidden)]
        text, dropped = _drop_sentences(text, re.compile("|".join(map(re.escape, names))))
    for relative in named:
        if relative in hidden or relative.rpartition("/")[2] not in text:
            continue
        title = file_title(folder, relative)

        def said(m: re.Match[str], title: str = title) -> str:
            opens = m.group(1) == "The" or (not m.group(1) and re.search(
                r"(?:\A|[.!?]\s|\n)\W*\Z", m.string[:m.start()]) is not None)
            return title[0].upper() + title[1:] if opens else title

        text = re.sub(r"(?:\b([Tt]he)\s+)?[`*]*(?:[\w.-]+/)*" + re.escape(
            relative.rpartition("/")[2]) + r"[`*]*", said, text)
    return text, dropped


def _drop_sentences(text: str, pattern: re.Pattern[str] | Callable[[str], Any]
                    ) -> tuple[str, list[str]]:
    """(the text without each sentence `pattern` finds, or a test of it holds for, those
    sentences); lines and paragraphs keep their breaks (structural; no word is read)."""
    found = pattern.search if isinstance(pattern, re.Pattern) else pattern
    kept_lines: list[str] = []
    dropped: list[str] = []
    for line in text.split("\n"):
        sentences = _sentences(line)  # t435: a quotation is kept or dropped whole
        gone = [x for x in sentences if found(x)]
        dropped += gone
        kept = [x for x in sentences if not found(x)]
        if gone and all(re.fullmatch(r"\d+[.)]|[-*•]", x.strip()) for x in kept):
            kept = []  # t434: a list's number or bullet with nothing left after it goes too
        if kept or not line.strip():
            kept_lines.append(" ".join(kept))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip(), dropped


def _sentences(text: str, also: str = "") -> list[str]:
    """t435 (413 r5): `text` cut at each sentence end (or at `also`, a pattern) that no quotation
    (`QUOTED`) spans, so a cut keeps or drops a quote whole and never leaves one unclosed (A4-06:
    "I can't say yet. That's what the BIA is for"). Structural; no word is read."""
    quotes = [m.span() for m in QUOTED.finditer(text)]
    out: list[str] = []
    at = 0
    for m in re.finditer(r"(?<=[.!?])\s+" + also, text):
        if not any(a < m.start() < b for a, b in quotes):
            out, at = [*out, text[at:m.start()]], m.end()
    return [*out, text[at:]]


def first_sentence(text: str) -> str:
    """What the model may add beside a printed sheet: its first sentence (structural; no word in it
    is read). t435: never inside a quotation."""
    return _sentences(text.strip())[0] if text.strip() else ""


# ── the prompt and tools ──────────────────────────────────────────────────────────────────────
SYSTEM = """You are nemo, an experienced BCM analyst and a friendly colleague. You help a BCM \
manager \
do a Business Impact Analysis (BIA) on their phone, in a live chat, over their company's files. \
User experience comes first: you do the work, you propose, you guide. The manager approves, \
corrects or asks.

How you talk:
- Like a person in a chat. At most 3 short sentences, then one clear next step or question. No \
headings, no walls of bullets. A short list is fine only when the manager asked for a ranking or a \
list.
- Say where you are by the step_name a tool gives ("<STAGE_3>").
- Write for a manager new to BCM and new to AI: short sentences and everyday words. Say the plain \
name first and the acronym after it ("how long Slaughter can be down before that becomes \
intolerable, its MTPD"); after that, "the MTPD" is enough.
- Tool results give each id (id, item_id, lens, step…) for your next call and, beside it, the \
words \
for the manager: the same field ending in _name, _names or _role, and step_name. Say those words \
to \
the manager, and pass the id only in your calls. For example, a tool result listed categories the \
interview never reached. Not: "the interview never reached financial, customer-delivery, \
legal-regulatory…". But: "<STAGE_3>: the interviews say nothing about seven kinds of \
impact, Financial among them. So how bad a stop gets there is not known yet."
- His reason for a change reaches the record only as a line he types himself, when nemo asks for \
it \
after he changed a figure. Never say you recorded a reason; nemo says what it recorded.
- The taps under your message are nemo's, drawn from the room's data: one per move a tool can make \
at this step, and tapping one makes that call for the manager. Never write taps or a list of \
choices \
to tap. When you have a view, recommend in your own sentence ("I recommend Louven's side") and let \
the manager tap or type.
- When the manager taps, nemo has already made the one call that tap stands for and tells you what \
it \
did. Say what it did and what comes next, in your own words; that turn has no tools.
- When a tool result says a move is his tap to make, tell him which tap, by the label he reads, in \
one \
sentence ("tap “Yes, agreed” to close it"); nemo keeps the card on his screen.
- Only state figures, names and quotes that a tool result gave you.
- Anything you propose, call it your proposal ("I propose...", "my suggestion") so it is never \
mistaken for what someone said. What an interviewee said, attribute to them by name.

The 5 steps (nemo keeps the order and the checks; you drive it with the tools):
1 Scope: get_step gives the activity list from the room's own files (usually one activity, from \
last cycle's BIA) and where it comes from. Say what it is and where it came from in one sentence, \
and ask whether that is the scope. Only his tap “<SCOPE_TAP>” agrees it: nemo draws it under your \
message, and you never agree the scope for him. If they want a different list, set_scope first. \
Never treat an interview's sub-steps (A1, A2...) as extra activities: they are evidence about the \
activity in scope. If you think the scope should be split, say so as a proposal at step 1.
2 Interviews: get_step shows every interview that talks about this activity (also from other \
departments) and why. Summarise in one or two sentences (how many, whose), let them confirm or \
drop \
some, then confirm_interviews. If no interview for the activity is on file, nemo offers to hold \
one \
here and now: the manager taps it, or call hold_interview when he agrees. nemo asks the questions \
and \
takes his answers; you ask none of them. When it is over he confirms it (confirm_interviews). For \
an activity he added, nemo's card also lists the risk register's rows: those that name it are kept \
already, and he keeps or drops any other (keep_risk_row). A kept row is evidence only, never a \
figure.
3 Evidence: nemo prints the impact grid and one card per decision itself: each card with the item, \
the proposal, and for a conflict \
each side's quote under the number its tap carries. Never write the grid, a table, a figure, the \
quotes or the sides yourself. Your line is one question about the card the taps are for: \
nemo_taps_about names it (its "card"), in get_step, in decide and in nemo's note after a tap. Ask \
about that card only, in a sentence or two; you may recommend a side by its number ("I'd take side \
2"). Record every choice \
with decide, or accept_all_open when they accept the rest; accept_all_open works only once every \
conflict and every proposed MTPD, RTO or RPO is settled one at a time. Before closing step 3, \
get_evidence("check") tells you what nemo's referee would refuse at step 4; fix it with the \
manager \
first (propose a value). When nothing is open, call answer_step: nemo makes it his tap \
“<AGREED_TAP>”, and only his tap closes the step.
   - A RECOVERY GAP is not a formality. Before offering it, say what it means: this activity \
cannot \
be brought back inside the time its own impact makes intolerable, so it is handed to solution \
design \
as a known exposure and management is being told so in writing.
4 Record — THIS IS THE REVIEW. Accepting writes the record into the room and onto the company's \
read-only page, marked as accepted but not yet signed. It is not the point of no return: until \
they \
sign, they can go back to step 3 with every decision kept (call reopen). A five-line card is shown \
automatically: the numbers, what changed since last cycle's BIA, what is worth challenging, whose \
words the record is made of, and where to read it whole. Say in one or two sentences what YOU \
would \
challenge in it, and that accepting writes it into the room. Then ask them to accept (answer_step).
5 Handover and signature — THE SIGNATURE IS THE POINT OF NO RETURN. If they question a figure \
at step 4 or 5, do not talk them past it: say you can go back, call reopen, and settle it. Once \
signed, the BIA is final; if they ask to change, reopen or undo it, call reopen and nemo \
answers. answer_step accepts the handover. Then the signature, and say plainly \
who is signing: the manager signs as the delegate, on behalf of the activity owner nemo names, and \
the certificate says exactly that. Ask them to TYPE their own name — never a tap for a signature — \
then call sign with name = their name, role = "<their role>, on behalf of <owner>, activity \
owner". A certificate card is shown automatically.

If a tool says you made the wrong call, make the right one. When nemo refuses in a way no call can \
change, it tells the manager itself and your turn ends there.
Where the room stands (which activities are finished, which have a record, what is signed) is \
nemo's to show: call room_state and nemo prints its sheet to the manager as it is. Add at most one \
sentence of your own that hands the choice back.
When he asks which activity is most critical, answer from the files: say what they show, such as \
last cycle's ranking, the MTPD each activity has on the room's record or in its interviews, or \
what \
depends on it, and name the file each point comes from. Which one is most critical stays his \
decision; say so in a few words.
The activities are offered by nemo: list_activities shows the manager the activity pick, one tap \
per \
activity in the room's own names. Never offer an activity as a choice yourself. \
If the manager asks for an activity the room does not list, call add_activity with his name for \
it, \
exactly as he wrote it: nemo adds it to the room and its BIA starts at step 1 in the same turn. \
Never \
refuse it, never steer him to a listed one, and never ask him to confirm the name. \
Saved, recorded and signed are said by nemo when the tool does it; do not announce them yourself.
If they ask something else the files can answer (what someone said, compare interviews), read them \
(list_room_files, read_room_file) and answer like an analyst. Then bring them back to the step.
BCM method questions: call ask_guidance; nemo prints its answer and links to the manager as \
served. \
Do not restate it; add one sentence back to the step."""
#: fix 1: a stage has one name, nemo's own heading (t64 review, minor 3)
SYSTEM = SYSTEM.replace("<STAGE_3>", walk.HEADING_3)
#: t392: the frame names the taps he reads, never the gradient's raw word (ADR-0013 took that tap)
SYSTEM = SYSTEM.replace("<SCOPE_TAP>", walk.AGREE).replace("<AGREED_TAP>", TAP_WORDS[walk.ENDORSED])


#: t96: an item left open into the signature, as the model reads it: the words first, and the id the
#: signature accepts it by beside them
OPEN_ITEM = "Open item ({at}): {text}"


def _fn(
    name: str, desc: str, props: dict[str, Any] | None = None, req: list[str] | None = None
) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props or {}, "required": req or []}}}


A = {"activity": {"type": "string"}}
TOOLS = [
    _fn(
        "list_activities",
        "The activities (departments) in this company's room. nemo shows the "
        "manager the activity pick: a card of the room's state with one tap per activity.",
    ),
    _fn(
        "room_state",
        "Where the room stands, read from its files now: per activity whether it can "
        "be walked, its step, whether a record is accepted, whether it is signed, MTPD/RTO/RPO "
        "each "
        "marked proposed or accepted, and the activities ordered by MTPD. nemo prints it to the "
        "manager as it is. Use it for any question about finished, recorded or signed.",
    ),
    _fn("get_step", "Where this activity's BIA stands, and what is needed next.", A, ["activity"]),
    _fn(
        "open_activity",
        "He asked to start or carry on the BIA for one activity: nemo opens its walk "
        "where it stands, as his pick of it does.",
        A,
        ["activity"],
    ),
    _fn(
        "add_activity",
        "The manager asked for an activity the room does not list: add it to the room "
        "under his name for it, exactly as he wrote it, and start its BIA at step 1.",
        {"name": {"type": "string"}},
        ["name"],
    ),
    _fn(
        "hold_interview",
        "Step 2 when no interview for this activity is on file: start nemo's live "
        "interview. nemo asks the questions and the manager answers; your turn ends there.",
        A,
        ["activity"],
    ),
    _fn(
        "set_scope",
        "Step 1 only: the activity list this BIA is about, as the manager agrees it. "
        "An interview's own sub-steps are evidence, not activities.",
        {
            **A,
            "activities": {"type": "array", "items": {"type": "string"}},
            "why": {"type": "string"},
        },
        ["activity", "activities"],
    ),
    _fn(
        "confirm_interviews",
        "Step 2: confirm the interviews this BIA rests on. Pass drop=[paths] "
        "for any the manager removes (default: keep all).",
        {**A, "drop": {"type": "array", "items": {"type": "string"}}},
        ["activity"],
    ),
    _fn(
        "keep_risk_row",
        "Step 2 of an activity the manager added: keep (keep=true) or drop "
        "(keep=false) one row of the room's risk register, by its id, as evidence for it. A kept "
        "row "
        "is quoted word for word from its line and sets no figure. Rows the activity's own name "
        "matches are always kept.",
        {**A, "row": {"type": "string"}, "keep": {"type": "boolean"}},
        ["activity", "row", "keep"],
    ),
    _fn(
        "get_evidence",
        "Step 3 detail. what = summary | proposals | conflicts | stated | check | "
        "grid | <item id>. 'check' = what nemo's referee would refuse at step 4 with the draft as "
        "settled now. 'grid' = the impact grid as the record stands now.",
        {**A, "what": {"type": "string"}},
        ["activity", "what"],
    ),
    # fix 4 (ruling 5): says what the tool does now. On a model turn no decide records (fix 3), so
    # "record the manager's decision" was a stale instruction the live model read every turn.
    _fn(
        "decide",
        "Step 3: proposes a decision on one proposal or conflict to the manager; nemo "
        "shows it as a tap and only his tap records it. decision = accept | reject | change. For a "
        "conflict pass side (index). For a score change pass scores {horizon: 1-5}; for "
        "MTPD/RTO/RPO "
        "change pass value.",
        {
            **A,
            "item_id": {"type": "string"},
            "decision": {"type": "string"},
            "side": {"type": "integer"},
            "value": {"type": "string"},
            "scores": {"type": "object"},
            # t71b fix 1 (M5): steering text for the tool, not a check on prose
            "note": {
                "type": "string",
                "description": (
                    "Optional. Kept only in nemo's log as yours, never shown as his: the record, "
                    "the card, "
                    "the handover and the certificate never carry it. The manager's reason comes "
                    "only "
                    "from his own typed lines."
                ),
            },
        },
        ["activity", "item_id", "decision"],
    ),
    _fn(
        "accept_all_open",
        "Step 3: the manager accepts all remaining proposals as proposed "
        "(conflicts take your recommended side).",
        A,
        ["activity"],
    ),
    # t76 (the owner's ruling, 2026-09-19): only he closes a gap, and only in his own words
    _fn(
        "close_recovery_gap",
        "The manager records that the available arrangements can now meet "
        "the recovery target, which is the one thing that closes a recovery gap he acknowledged: "
        "a target he changes never closes it. You cannot call this: nemo takes the words from the "
        "line he types himself, under its own tap, and refuses it on your turn.",
        {
            **A,
            "item_id": {"type": "string"},
            "said": {
                "type": "string",
                "description": ("His line, word for word as he typed it. Never your words for it."),
            },
        },
        ["activity", "item_id", "said"],
    ),
    _fn(
        "answer_step",
        "Give nemo the manager's answer to the current step (steps 1, 3 close, 4, 5 "
        "handover): endorsed | endorsed with reservations | needs discussion.",
        {**A, "answer": {"type": "string"}},
        ["activity", "answer"],
    ),
    _fn(
        "reopen",
        "Go back to step 3 with every decision kept, when the manager disputes a figure "
        "in the record or the handover, or asks to change, reopen or undo a BIA in any way — also "
        "after the signature, and every time they ask: nemo gives the answer.",
        A,
        ["activity"],
    ),
    _fn(
        "sign",
        "Step 5 signature after the handover is accepted: signer name and role.",
        {**A, "name": {"type": "string"}, "role": {"type": "string"}},
        ["activity", "name", "role"],
    ),
    _fn(
        "ask_guidance",
        "Answer a question about the standard: business continuity method in general. "
        "The company's own method and choices are in its files (read_room_file). nemo labels the "
        "answer by where its links come from: the AI4BCM Guidance, the literature, or both.",
        {"question": {"type": "string"}},
        ["question"],
    ),
    _fn(
        "list_room_files", "List the company's files (interviews, register, method, organisation)."
    ),
    # t106 (M2): a company by name is nemo's fact, served whole; "not found" only when no file names
    # it
    _fn(
        "company",
        "What the company's files say about one customer or supplier, by the name the "
        "manager wrote: nemo finds it (case, legal form or one letter aside) and serves every file "
        "line that names it, or says no file names it.",
        {"name": {"type": "string"}},
        ["name"],
    ),
    _fn(
        "read_room_file",
        "Read one file from the company's room by path: the company's own method, "
        "its choices, interviews, registers and records.",
        {"path": {"type": "string"}},
        ["path"],
    ),
    # t256: the model names a referral and never writes it: a register id and an item, nothing else
    {"type": "function", "function": {
        "name": "propose_referral",
        "description": "While you compare an interview with last year's BIA, propose referring a "
                       "change to the owner of one resource in the dependency register: its "
                       "register id and the item to look at. When your answer names a gap in one "
                       "activity of the room, propose noting it for that activity's owner: its "
                       "slug and the item (owner, deputy, mtpd, rto, rpo, dependencies, "
                       "workaround). At most two per answer. nemo draws him the tap; he says "
                       "what the owner should look at.",
        "parameters": {"type": "object", "properties": {
            "resource": {"type": "string",
                         "description": "the resource's register id, or the activity's slug"},
            "item": {"type": "string", "enum": list(REFER_ITEMS)}},
            "required": ["resource", "item"], "additionalProperties": False}}},
    # t318 (ADR-0047): the model names a dependency and never writes it: a name and an activity,
    # nothing else (no figure, no owner, no description, no map items: code picks those, M13)
    {"type": "function", "function": {
        "name": "propose_dependency",
        "description": "When he says an activity of the room also needs a resource, propose "
                       "adding it to this room's dependency register: the resource's name as he "
                       "said it and the activity. One per answer. nemo draws him the tap; his "
                       "tap adds it, with no figure and no owner.",
        "parameters": {"type": "object", "properties": {
            "resource": {"type": "string", "description": "the resource's name, as he said it"},
            "activity": {"type": "string", "description": "the activity's name or slug"}},
            "required": ["resource", "activity"], "additionalProperties": False}}},
]
#: t377 N6 (7_nemo_design's read of 377 O, g3): model words on how nemo works inside, never shown:
#: a tool's id (`TOOLS`: a snake_case one anywhere, a one-word one as code, `sign` or sign()), a
#: register id, or how a tap is drawn; each sentence holding one is dropped
MECHANICS = re.compile("|".join([
    r"\bregister ids?\b", r"\btaps? (?:is |are |be |gets? )?drawn\b",
    r"\bdraws? (?:the|a|you a) tap\b",
    *(rf"\b{n}\b" if "_" in n else rf"`{n}`|\b{n}\(" for n in (re.escape(t["function"]["name"])
                                                             for t in TOOLS))]))

#: t392 (run 6, S2): a model sentence telling him to tap a raw gradient word or "Agree", taps the
#: skin has not drawn since ADR-0013; the tap drawn under it is the one instruction, so it goes
STALE_TAP = re.compile(r"\btap\W+(?:on\W+)?[\"“‘]\s*(?:"
                       + "|".join(map(re.escape, (*walk.GRADIENT, "endorse", "agree"))) + ")", re.I)


# ── t96: free chat is the default, on a short prompt (ADR-0023 decision 5) ─────────────────────
#: Modelled on the ai4bcm chat's (`/opt/apps/ai4bcm-chat/ask.py:268-294`): answer the question that
#: was asked, in plain words and a few sentences, with no procedure. Positive rules only (M5). The
#: walk's procedure (`SYSTEM`) is put in front of the model only once the conversation is on the
#: walk, which `Session.walking` reads from data, never from anyone's words (M13).
#: t110: one sentence a line, each with the round-2 pair ids it answers (ticket 110's Evidence, the
#: verdict in docs/verdicts/); "96" marks a sentence the owner approved under 96, kept byte for
#: byte, and "96, …" one changed and listed for him. Round 3 (112) is the only test of the shape;
#: nothing asserts on an answer's length (ticket 110, grill Q6).
CHAT_SYSTEM = (
    "You are nemo, a friendly colleague who knows business continuity well. "  # 96
    # 96
    "You are chatting with a business continuity manager on his phone, over his company's files."
    "\n\n"
    "When a question is about the room, read the files first, then answer."  # 96
    "\n\n"
    # 96 said "…asked, first, in plain everyday words": the first sentence is it (r2-14, 22, 34)
    "Answer the question that was actually asked in your first sentence, in plain words. "
    "Write for an entry-level BCM manager: would he understand the answer? "  # 96
    # r2-04, 27, 39, 16, 30 ("shorter, about 30 %"); 96 said "Two to four short sentences suit most
    # questions.", the ticket's own number replaces it
    "100 to 150 words suit most questions. "
    # r2-15, 17, 19, 22, 33, 36, 37, 41 (long unbroken paragraphs)
    # t265: his "skip the introduction such as \"Short version:\"": the clause asking for it cut
    "When it has parts, use at most three short bullets or two short paragraphs. "
    # 96, narrowed to three or more: liked on r2-06, 16; "not always needed" on r2-41, 43
    "Where three or more things are compared, such as several activities, a small table reads best."
    "\n\n"
    # 96, its examples re-aimed at today's seed (Louven has no interview of her own); the tools
    # named in brackets cut, their own descriptions say it
    "Say what the files say, naming each document by its plain name: \"last year's BIA\", "
    "\"Harder's interview on procurement\"; its folder and path mean nothing to him. "
    "Call a system, an asset, a person or an earlier BIA by the name the files give it. "  # 96
    # 96, in one sentence (r2: length doubled under 96's "say what it means"); 110's example,
    # re-aimed for 228's guard (step 43 hunts every string for the mail word): today's risk
    # register, R-IT-07, "Orders placed by phone … and kept in a local order list"
    "Then say what it means: one sentence, such as \"purchasing's fallback for Microsoft 365 is "
    "the phone and a local order list\"."
    "\n\n"
    # 96, "last year's ranking" re-aimed: last year's BIA ranks nothing
    "When he asks which activity is most critical, answer from the files: last year's BIA, how "
    "long each can be down, what depends on it, and which file says so. "
    "Which is most critical stays his decision; say so."  # 96, shortened
    "\n\n"
    "The company's own method, choices and figures are in its files: read those first. "  # 96
    # 96, plus what the one sentence is: the plain answer (r2-14, r2-44: answered, not guidance
    # first)
    "For a question about the standard, call ask_guidance: nemo shows him its answer with its "
    "sources, and your one sentence gives the plain answer."
    "\n\n"
    "State figures, names and quotes exactly as a file or a tool gave them. "  # 96
    # 96, with a first half for "that's not an answer" (r2-12, 14, 36, 44): an answer, never a
    # question back
    "When the files hold the answer, give it; when silent, say so plainly and name what would "
    "tell him."
    "\n\n"
    # 96; "That opens the five-step walk." cut, list_activities' own description says it
    "When he wants to start a BIA or carry one on, call list_activities, or open_activity for the "
    "activity he named."
    "\n\n"
    "Talk about the company, its people and its files, the way a colleague would at his desk: the "
    "answer is what he sees."  # 96
)

#: t265: a lead-in label a free-chat answer opens with anyway ("Short version:", his "etc."): a
#: fixed list, case ignored, bold markers optional. Only at the very start of what is shown; the
#: same words anywhere else stay, and the turn file keeps the model's reply as it came (M13).
LEAD_IN = re.compile(
    r"\A\s*(?:\*\*|__)?(?:the short version|short version|in short|tl;dr|summary)(?:\*\*|__)?"
    r"\s*:(?:\*\*|__)?\s*",
    re.IGNORECASE,
)

#: the tools free chat offers: reading the files, the method, where the room stands, and the two
#: ways into the walk. Every other tool is the walk's, and calling any of them puts the walk's
#: procedure in front of the model (`Session.dispatch`).
_CHAT_SAYS = {
    "list_activities": "He wants to start or carry on a BIA: nemo shows him the activities to pick "
                       "from, and the walk through its five steps begins.",
    "get_step": "Where one activity's BIA stands and what its record says, to answer a question "
                "about it. It opens nothing.",
}
CHAT_TOOL_NAMES = (
    "list_activities",
    "open_activity",
    "get_step",
    "room_state",
    "ask_guidance",
    "list_room_files",
    "read_room_file",
    "company",
    "propose_referral",
    "propose_dependency",
)
CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            **t["function"],
            "description": _CHAT_SAYS.get(t["function"]["name"], t["function"]["description"]),
        },
    }
    for t in TOOLS
    if t["function"]["name"] in CHAT_TOOL_NAMES
]
#: the tools that are the walk itself: the model calling one means the conversation is on the walk
#: t96 fix 2 (95 b): a free-chat call to a tool free chat does not offer, as the model reads it
FREE_CHAT_TOOLS = (
    "{tool} is a step of a BIA, and no BIA is open in this conversation: it opens when he "
    "picks an activity or asks to start one. Here you answer from the files."
)
WALK_TOOL_NAMES = frozenset(t["function"]["name"] for t in TOOLS) - {
    "room_state", "ask_guidance", "list_room_files", "read_room_file", "company",
    "propose_referral", "propose_dependency"}
#: 608 (ADR-0061, map N6): the walk's tools as the led turn is handed them while the conversation
#: is on a walk (`Session._led_model_turn`); its reads and facts stand in for the file tools
LED_WALK_TOOLS = [t for t in TOOLS if t["function"]["name"] in WALK_TOOL_NAMES]

#: t600: the six keys every turn's record carries (`led_fields`, `brake_fields`); 608 Amend 1: the
#: scenario driver's turns copy them
TURN_SHAPE = ("path", "tool_steps", "artefacts_shown", "drops", "must_cover_misses", "clock_s")
#: t532 (ADR-0056): the paths a turn the model led is written under. t600: the brake's turns carry
#: a `path` too (`brake_fields`), never one of these; a record written before 600 has none.
LED_PATHS = ("model-led", "plain line")


def led_fields(path: str, tool_calls: list[dict[str, Any]], artefacts: list[dict[str, Any]],
               drops: list[dict[str, Any]], must_cover_misses: list[str],
               clock_s: float) -> dict[str, Any]:
    """t532: SHARED, the keys a model-led turn's record gains beside today's. `tool_calls` are the
    lane's own (OpenAI-shaped); an argument string that is not JSON is kept as written (GLM's broken
    JSON). `record_turn` adds `billed_cost` from the turn's calls."""
    if path not in LED_PATHS:
        raise ValueError(f"not a model-led path: {path!r}")

    def args(text: str) -> Any:
        try:
            return json.loads(text)
        except ValueError:
            return text
    return {"path": path,
            "tool_steps": [{"name": c["function"]["name"],
                            "arguments": args(c["function"].get("arguments") or "{}")}
                           for c in tool_calls],
            "artefacts_shown": [{k: a[k] for k in ("id", "template", "arguments", "version")}
                                for a in artefacts],
            "drops": [{"text": d["text"], "reason": d["reason"]} for d in drops],
            "must_cover_misses": list(must_cover_misses),
            "clock_s": round(clock_s, 2)}


#: t600: the reason a brake turn's `dropped` paragraph is on file under
BRAKE_DROPPED = "dropped by the brake's checks"


def brake_fields(turn: dict[str, Any]) -> dict[str, Any]:
    """t600 (ADR-0061 F3): SHARED, `led_fields`' six keys for a turn the brake wrote, read from its
    own keys, which stay beside them (610 removes them). Its `path` is never one of `LED_PATHS`:
    code's own reply (`server`), a refusal, a failed turn, code's card (`code_said`), else the
    chat model's. A turn with no `seconds` keeps no `clock_s` (None, unmeasured)."""
    path = ("server" if turn.get("server") else "refusal" if turn.get("refusal")
            else "failed" if turn.get("failed") else "code card" if turn.get("code_said")
            else "chat model")
    return {"path": path,
            "tool_steps": [{"name": n, "arguments": None} for n in turn.get("tools") or []],
            "artefacts_shown": [],
            "drops": [*(kept := turn.get("drops") or []), *(  # 607: the one stack's, as checked
                {"text": d, "reason": BRAKE_DROPPED} for d in turn.get("dropped") or []
                if d not in {x["text"] for x in kept})],
            "must_cover_misses": [],
            "clock_s": turn.get("seconds")}


def _unaccounted(turn: dict[str, Any]) -> float | None:
    """Ticket 69 fix 1: the seconds of a turn that neither the model lane nor a tool accounted for.

    A turn is what the manager waits for, and `seconds` is all of it. On the 497.6 s tap that
    confirmed an interview, `model_seconds` was 7.75 and `tool_seconds` 0.02: ~490 s of his wait
    had no name. What those seconds went on is not in the log and this does not guess — it publishes
    the remainder as what it is, so the thing being measured is not silently lost. None when any of
    the three is missing (a turn that failed has no model or tool time to subtract).

    t82 keeps this number exactly as ticket 69 defined it, so the ceiling reads the same figure it
    always did. What t82 adds is `_accounting` beside it, which NAMES the remainder.
    """
    s, m, k = turn.get("seconds"), turn.get("model_seconds"), turn.get("tool_seconds")
    # why: `None in (s, m, k)` is checked first
    return None if None in (s, m, k) else round(s - m - k, 2)  # type: ignore[operator]


# ── ticket 82: the instrument ─────────────────────────────────────────────────────────────────
#: Sampling the turn's own thread. Off unless asked for: it is a diagnosis, not a product clock.
TRACE = os.environ.get("PROTO_TRACE") == "1"
TRACE_EVERY_S = 1.0
#: 30 minutes of samples at 1 s; a turn longer than that is the defect, not a sampling problem.
_SAMPLES: collections.deque[tuple[float, int, str]] = collections.deque(maxlen=1800)
_SAMPLER_STARTED = [False]
def _ours(frame: Any) -> Any:
    """The deepest frame in code this build owns, or None."""
    while frame is not None:
        f = frame.f_code.co_filename
        if f.rsplit("/", 1)[-1].startswith(("PROTOTYPE_", "bia_figures")) or "/nemo/" in f:
            return frame
        frame = frame.f_back
    return None


def _where(frame: Any) -> str:
    """One sample: the innermost Python line the thread is sitting on, `file:line:function`.

    **It is the LINE that names the wait, not the function.** A lock, a `sleep` and a socket read
    are all C calls with no Python frame of their own, so there is never an `acquire` in the stack
    to read — the innermost Python frame is the `with lock:` or the `time.sleep(...)` or the
    `httpx.post(...)` itself. That line is what separates a lock from a stall from a slow call, and
    it separates one lock from another, which a primitive's name would not.

    When the innermost frame is not ours the line of ours below it is named too, so a stall inside
    a dependency still says which of our calls is sitting in it. A sample is never dropped for
    having no frame of ours at all: a silent drop would let a stall in a dependency read as no
    stall, and a detector that goes quiet where it cannot see is the one thing this must not be.
    """
    if frame is None:
        return "?"
    name = frame.f_code.co_filename.rsplit("/", 1)[-1]
    here = f"{name}:{frame.f_lineno}:{frame.f_code.co_name}"
    ours = _ours(frame)
    if ours is None:
        return f"{here} (none of ours below it)"
    if ours is frame:
        return here
    o = ours.f_code.co_filename.rsplit("/", 1)[-1]
    return f"{here} via {o}:{ours.f_lineno}:{ours.f_code.co_name}"


def _sampler() -> None:
    me = threading.get_ident()
    while True:
        now = time.time()
        for ident, frame in sys._current_frames().items():
            if ident != me:  # the only frame this instrument must never report is its own
                _SAMPLES.append((now, ident, _where(frame)))
        time.sleep(TRACE_EVERY_S)


def start_trace() -> None:
    """Start the sampler once. Called from the first turn, never at import: importing this module
    must not start a thread in a suite that never asked for one."""
    if TRACE and not _SAMPLER_STARTED[0]:
        _SAMPLER_STARTED[0] = True
        threading.Thread(target=_sampler, daemon=True, name="t82-sampler").start()


#: Every key `_accounting` publishes on a turn. One list, because the scenario runner rebuilds each
#: turn record key by key (`PROTOTYPE_scenarios.run_walk`) and a hand-retyped list there would drop
#: a
#: new field in silence — which is exactly how 489.83 s came to have no name in the first place.
#: tests/test_t82_accounting.py::test_no_accounting_field_can_be_dropped_on_the_way_to_the_run_file
#: holds this list to what the function actually returns, and to what the run file carries.
ACCOUNTING_KEYS = ("lane_offturn_s", "lane_inturn_s", "lane_spans", "unexplained_s",
                   "waited_where", "tool_work")

#: What `tool_work` says when a turn booked tool seconds and nothing named them. It is a value, not
#: an absence, because the 489.83 s taught this ticket that a missing field reads as "nothing to
#: report": the worst turn of the baseline run carried `tool_seconds: 662.3` beside `tools: []`, and
#: a reader had 662 seconds with nothing to point at. A path that times work outside `dispatch`
#: passes its own name (`Session._narrate`'s `tool_work`); one that forgets says so here, loudly.
TOOL_WORK_UNNAMED = "unnamed: timed outside any dispatched tool"


def _accounting(turn: dict[str, Any], end: float, ident: int) -> dict[str, Any]:
    """Where a turn's seconds went, including the ones spent outside its own thread.

    Ticket 69's clocks are per-turn and per-thread: `model_seconds` is the lane time the turn's own
    thread spends inside `Session._model_calls`, and `tool_seconds` the time inside `dispatch`. On
    the 497.6 s confirm-interview tap neither could see the seconds, because the turn was BLOCKED on
    a lock held by a background drafting thread, which was itself inside a lane call. Those seconds
    were real — the manager waited every one of them — and no per-turn clock can ever name them.
    So this reads the process-wide lane ledger, clips every span to the turn's own window and says:

    - `lane_offturn_s`  lane seconds in OTHER threads while this turn waited. The 489.83 s lands
    here.
    - `lane_inturn_s`   lane seconds in THIS thread; `model_seconds` plus any lane call a TOOL made,
                        which is why the same defect reads as tool time once the lock is gone.
    - `attempts`        how many tries each of those lane calls took, and what ended them. One very
                        slow call and three tries into a 600 s timeout are the same span otherwise.
    - `unexplained_s`   what is left when the lane is subtracted everywhere it ran. THIS is the
                        number that means "we still cannot see it".
    - `waited_where`    where the turn's own thread actually sat, sampled (`PROTO_TRACE=1`). A lock
                        and a stall both show no lane call in this thread; only this tells them
                        apart.
    - `tool_work`       whose the tool seconds are (fix 1). The confirm-interview tap times
                        `Session._file_held`, which is not a dispatched tool, so the baseline run's
                        worst turn read `tool_seconds: 662.3` beside `tools: []` — 662 seconds with
                        nothing to point at, this ticket's own defect one layer down. A path that
                        times work outside `dispatch` passes its own name; one that does not says
                        `TOOL_WORK_UNNAMED`, because a blank reads as "nothing to report".

    Overlapping background threads can sum past the wall clock, so `lane_offturn_s` is an upper
    bound on what the wait can be blamed on, never a subtraction that must balance. It is reported,
    never used to correct `unaccounted_seconds`, which stays ticket 69's number.
    """
    s = turn.get("seconds")
    if s is None:
        # A turn that failed has no window to measure between, so there is nothing to account for.
        # It still carries every key, set to None: a record that is simply MISSING the fields reads
        # as a turn with nothing to report, and "not measured" and "nothing there" are the two
        # things this instrument exists to keep apart.
        return dict.fromkeys(ACCOUNTING_KEYS)
    start = end - s
    spans = lanes.spans_overlapping(start, end)
    off = [sp for sp in spans if sp["thread"] != ident]
    here = [sp for sp in spans if sp["thread"] == ident]
    off_s = round(sum(sp["in_window_s"] for sp in off), 2)
    m, k = turn.get("model_seconds"), turn.get("tool_seconds")
    out: dict[str, Any] = {
        "lane_offturn_s": off_s,
        "lane_inturn_s": round(sum(sp["in_window_s"] for sp in here), 2),
        "lane_spans": [{"purpose": sp["purpose"], "thread": sp["thread_name"],
                        "in_window_s": sp["in_window_s"], "model": sp["model"],
                        "running": sp["end"] is None,
                        "attempts": [a["outcome"] for a in sp["attempts"]]} for sp in spans],
        "unexplained_s": None if None in (m, k) else round(s - m - k - off_s, 2),
        # Who the tool seconds belong to. `tools` names them when a tool was dispatched; a turn that
        # timed nemo's own work instead passes its own name; and a turn that timed neither says
        # TOOL_WORK_UNNAMED rather than leaving the seconds anonymous.
        "tool_work": (", ".join(turn["tools"]) if turn.get("tools")
                      else turn.get("tool_work") or (TOOL_WORK_UNNAMED if k else None)),
    }
    seen = [w for at, i, w in list(_SAMPLES) if i == ident and start <= at <= end]
    # Always a key, never sometimes-present: a field that appears only when the sampler ran reads as
    # "nothing to report" on every turn that never sampled. None says "not sampled"; [] says
    # "sampled
    # and the thread was never caught waiting anywhere".
    out["waited_where"] = None if not TRACE else [
        {"where": w, "seconds": round(n * TRACE_EVERY_S, 1)}
        for w, n in collections.Counter(seen).most_common(4)]
    return out


#: t152: the most characters of JSON one tool result sends the model. A 20-process room's room_state
#: runs to ~19 800, past the old 14 000 cut; this holds it whole with room to spare. t328: the
#: seed's sites and new IT items (each one a `needs` entry) took it past 32 000; 40 000 holds it.
TOOL_RESULT_CAP = 40000


def _json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def for_model(result: Any) -> str:
    """t152: a tool result as the model receives it, always whole JSON, never cut inside it. Under
    the cap it is sent as it is. Over it, the largest value gives way first (a string loses its end,
    a list its last items, anything else leaves whole) until it fits, and `shortened` says, per key,
    what was left out. A result that is not an object is sent as `result`. Only what is sent
    changes."""
    said = _json(result)
    if len(said) <= TOOL_RESULT_CAP:
        return said
    whole = dict(result) if isinstance(result, dict) else {"result": result}
    left: dict[str, Any]
    kept, left = dict(whole), {}
    while len(said := _json({**kept, "shortened": left})) > TOOL_RESULT_CAP and kept:
        key = max(kept, key=lambda k: len(_json(kept[k])))
        value = kept[key]
        if isinstance(value, (str, list)) and len(value) > 1:
            over = -(-(len(said) - TOOL_RESULT_CAP) * len(value) // len(_json(value)))
            kept[key] = value[:max(1, len(value) - over)]
            n = len(whole[key])
            left[key] = (
                f"the last {n - len(kept[key])} of {n} "
                f"{'characters' if isinstance(value, str) else 'items'}"
            )
        else:
            del kept[key]
            left[key] = "left out whole"
    return said


class Session:
    """One manager, one room, one model."""

    def __init__(self, folder: Path, model: str, log: Callable[[str, Any], None]) -> None:
        self.folder, self.model, self._sink = folder, model, log
        #: t109: the last turn line this session logged, for the caller that writes the turn file
        self.last_turn: dict[str, Any] = {}
        #: t132: this turn's id, minted when it starts, so an act of his names the turn whose line
        #: holds his words; `record_turn` writes the line under it
        self.turn_id = ""
        #: t82 fix 3: how a line reaches his screen while his turn is still running. The skin sets
        #: it; `_draft` calls it before it drafts on his turn. Nothing here shows anything.
        self.say_now: Callable[[str], None] = lambda line: None
        #: t537: how "Checking your files…" reaches his reply bubble (t628: in that bubble)
        #: while a model-led turn runs; the skin sets it. And that turn's clock (`led_turn.Clock`;
        #: None is the spec's).
        self.waiting: Callable[[str], Any] = lambda line: None
        self.led_clock: Any = None
        #: ticket 69: every walk's stage in the room when this turn began, by run file
        self._stages_before: dict[str, int] = {}
        #: room files the model read this turn — a figure quoted out of one of them is traceable
        self._read_this_turn: list[Path] = []
        #: t108: what this turn read (room-relative) and which activities its readings named
        self._turn_read: list[str] = []
        self._turn_named: list[str] = []
        self._line_named: set[str] = set()  # t377p r2: his typed line's names alone
        #: t282: the register's resources his typed line names
        self._turn_assets: list[str] = []
        self._turn_line = ""  # t318: his typed line this turn, "" on a tap
        self._taps_named = False  # t418 r4: the last taps were drawn for a line asking for names
        self._next_step: str | None = None
        #: t106: the facts nemo served (companies, interviews, figures) — a figure said from one is
        #: traceable, as one quoted from a file read
        self._facts_served: list[str] = []
        #: t249: the room's files as nemo last served them (`room_files`); None until it has
        self._files_seen: set[str] | None = None
        self._rows_told: set[str] = set()  # t318: the chat rows nemo has told the model of
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": CHAT_SYSTEM}]
        self.cards: list[str] = []
        #: t255: the charts drawn beside a grid card, by the card as drawn (`impact_charts`)
        self._charts: dict[str, list[str]] = {}
        #: t403 r6: each chart's phone split, by the same card (`phone_charts`)
        self._phones: dict[str, list[str]] = {}
        #: t499: the activity of the last impact chart drawn, for "add X to the same chart"; r2:
        #: and how many of his typed lines there were then (the lines after it may pick classes)
        self._chart_shown: str | None = None
        self._chart_at = 0
        #: a card is drawn once per step, however often the model calls get_step
        self._carded: set[str] = set()
        #: this conversation's standing refusals (ticket 67): (tool, activity) -> the rendered
        #: refusal, what it waits on, and that precondition as it stood. A call that meets one again
        #: gets the same refusal whatever its other arguments, until the precondition changes.
        self._standing: dict[tuple[str, str], dict[str, Any]] = {}
        #: the activity this conversation is on, from data only (ticket 67 fix 1): see `dispatch`
        self._activity: str | None = None
        #: ticket 68: the sheet room_state printed this turn, whether the pick card was drawn this
        #: turn, and every activity-pick tap this session drew (label -> the room's activity)
        self._sheet_text: str | None = None
        self._sheet_drawn = False
        #: t65: the guidance answer ask_guidance printed this turn, as served
        self._guidance_text: str | None = None
        self._picks: dict[str, str] = {}
        #: whether the taps the last turn returned are the server's own (the activity pick, and
        #: t72's action taps); the skin marks them, and only a marked tap is acted on
        self.last_pick = False
        #: t73: every tap this session drew, by action id (what the skin's payload carries) and by
        #: label (the latest drawn under it); the ids of the last turn's taps, in their order; and
        #: the "Change …" tap waiting for the manager's typed value (his next typed line is it)
        self._tap_ids: dict[str, dict[str, Any]] = {}
        self._tap_labels: dict[str, str] = {}
        self.last_actions: list[str] = []
        self._last_taps: list[dict[str, Any]] = []
        #: t440: the taps on screen are "Write to an owner"'s pick set, still unanswered
        self._picking = False
        #: t513: the dependency ask 504's picker was drawn for, and the picker's activity taps
        #: (label: activity); his pick there answers it, never another tap on the same call
        self._asked_for: tuple[str, dict[str, str]] | None = None
        self._meant = False  # t471: this turn is his pick under "Which did you mean?"
        #: t276: the app's root path, which a page tap's link starts with (the app sets it)
        self.root = ""
        #: 314b: this session answers the dependency graph page's Ask nemo (`live_graph.ask`), where
        #: "this graph" is that graph: its lines never draw the impact chart
        self.graph_page = False
        #: t277: the app's 257 mailbox, which the core never names (step 43): whether its tap is
        #: offered now, and its press, which places the drafts and says what he reads
        self.mailbox_offered: Callable[[], bool] = lambda: False
        self.place_drafts: Callable[[], str] = lambda: ""
        #: t373: the app's press of "Invite to the interview" for an activity, and what he reads
        self.place_invite: Callable[[str], str] = lambda activity: ""
        #: t406: the app's press of "Put these in Drafts": the activity's shown drafts placed
        self.place_shown: Callable[[str], str] = lambda activity: ""
        #: t539/t540: the app's press of a model-led letter's tap and of the invitation's move
        self.place_letter: Callable[[dict[str, Any]], str] = lambda tap: ""
        self.place_move: Callable[[dict[str, Any]], str] = lambda tap: ""
        #: t434: every line code wrote this session (a server reply, a card, a block): what holds
        #: a send, reply or day state (`drop_unheld`), never the model's words
        self._code_lines: list[str] = []
        #: t115/117: this turn printed a show tap's table, so the decision taps stay on the message
        #: they are on and only the show taps (`SHOW_TAPS`) go under the table
        self.taps_stay = False
        #: t329: the slides tap his typed line asked for this turn, drawn after the turn's taps
        self._slides_tap: list[tuple[str, dict[str, Any]]] = []
        #: t373: "Invite to the interview", drawn after his taps where his line asked for it
        self._invite_tap: list[tuple[str, dict[str, Any]]] = []
        #: t366: his typed line this turn asked nemo to write a message (`asks_to_write`)
        self._asked_write = False
        #: t377 (B, D3): code's own answer to his typed line, shown in place of the model's words
        self._code_said = ""
        #: t377 H1, H2, Q r2: which of code's answers that is (`NEXT_KIND`, `DOWN_KIND`,
        #: `QUOTES_KIND`), for the turn
        self._code_kind = ""
        #: t478: the sheet prompt a code answer with no kind answers (B3's, B4's), and the server
        #: set this turn drew (`_server_reply`): with `_code_kind`, the answer's stage
        self._answered = self._server_set = ""
        #: t478: the stage the last answer is at (`_answer_stage`), its label's (`stage_line`)
        self.answer_stage = walk.STAGE
        #: t377 H3: the activity his last analysis was about (`_analysed_now`), for the chart
        self._analysed: str | None = None
        #: t377 D2: whether this turn is his analysis of the files (536: code's next steps read
        #: it, and a caller reaching `_kind_steps` before a turn finds it here, not missing)
        self._analysing = False
        #: t377 (C): what code found, leading the model's answer in a walk
        self._lead_said = ""
        #: t507 (A9): this year's changes, leading the model's answer to what he should still check;
        #: outside `drop_undrawn`'s figure rule, so the model's own list stands as it would without
        self._check_said = ""
        #: t516: the model's or the agent's words this turn, beside code's on the card the start
        #: tap sits under (`_card`); r2: they never make it "its" alone
        self._card_said = ""
        self._led_state: Any = None  # t546: the model-led turn's conversation (`led_turn.State`)
        #: t395: the room's last real activity: the last one code answered about (`_about`) or his
        #: typed line named; never a tool's argument, nor a tap on another activity's finding.
        #: t533: as the room kept it (`shown`), so a reconnect, a reopened link or a restart is on
        #: it too; t499's last chart with it
        self._thread: str | None = self._kept_focus()
        self._chart_shown = self._kept_chart()
        #: t377 (B, D3): the activity code last answered about, so "what should I focus on"
        #: after "who should I invite" is about the same BIA
        self._about = None
        #: t377 (A): the activity whose interview with open discrepancies a turn last read, so an
        #: email ask after the analysis writes about them
        self._found_in: str | None = None
        #: t117: where in this turn's cards the live card stands, so the skin puts the turn's taps
        #: on
        #: its message ("the taps sit on the card they act on"); None when no live card was drawn
        self.live_at: int | None = None
        #: t377 D4: the decision the last live card raised (activity, item, how many open), and
        #: whether this turn's answer points at it instead of drawing it again
        self._live_key: tuple[str, str, int] | None = None
        self._pointed = False
        #: t429: this turn drew a stage card that names no stage (stage 3's, the signature's)
        self._staged = False
        self._turn_tools: list[str] = []
        #: t73 fix 1: the message the taps are drawn on, counted, part of each tap's id
        self._message = 0
        self._awaiting_value: dict[str, Any] | None = None
        #: t71: every line the manager typed in this conversation (the signer's name is one of them)
        self._typed: list[str] = []
        #: t459 r2 (b): this turn's typed line asks about the BIA programme (B1, B2, B9, A9)
        self._programme_turn = False
        self._model_turn = False
        #: t71b fix 1: his typed line while the value a "Change …" tap asked for is being recorded
        self._typing: str | None = None
        #: t80/t83: the act a model turn was refused, held so nemo can draw the tap that takes it
        #: and recognise his own tap when it comes back. nemo writes both; no model JSON reaches
        #: them, and neither is read for anything but drawing a tap and marking his confirmation.
        self._chat_figure: dict[str, Any] | None = None
        self._chat_referral: dict[str, Any] | None = None
        #: fix 1 (t80): the conflict side a model turn was refused, and the labels nemo drew for it
        self._chat_proposal: dict[str, Any] | None = None
        #: t134: the signature a model turn was refused for want of his choice, and the taps nemo
        #: drew for it — each one the whole call, with his typed name and role already on it
        self._chat_signature: dict[str, Any] | None = None
        #: t72: whether the server asked for a new activity's name (his next typed line is it); the
        #: live interview underway; and the activity whose stage 2 offered the interview this turn
        self._awaiting_name = False
        self._interview: dict[str, Any] | None = None
        self._hold_offered: str | None = None
        #: t64: his typed value waiting for its reason when it opened a flag (his next typed line
        #: is it; the Skip tap leaves none)
        self._told: set[str] = set()  # t107: terms named in this turn's tool results
        #: t215 (his 2026-09-28T20:43:33Z words: basic terms "must not always be explained in ()"):
        #: the standard's own words (`terms.STANDARD_TERMS`) already named in this conversation,
        #: which are said bare from then on. Never reset by a turn. Two sets, because they have two
        #: readers: what he has read (`drawn_turn`) and what the model has read in a tool result.
        self._standard_said: set[str] = set()
        self._standard_told: set[str] = set()
        self._awaiting_reason: dict[str, Any] | None = None
        #: t256: this answer's accepted referral proposals (t276: two at most, each with its
        #: label), and the referral his tap opened, waiting for his next typed line
        self._referrals: list[tuple[str, dict[str, Any]]] = []
        self._awaiting_refer: dict[str, Any] | None = None
        #: t318: this answer's accepted dependency proposal (one at most), as its tap's action
        self._additions: list[tuple[str, dict[str, Any]]] = []
        #: t63: the card the last turn's side taps name, as logged
        self._card_log: dict[str, Any] | None = None
        #: t115: the show tap just taken ("grid" or "decisions", `walk.prints`'s words), spent by
        #: the
        #: turn it was drawn on: the tap is nemo's own, drawn for this turn's activity
        self._tapped = ""
        self.stats = {"turns": 0, "calls": 0, "seconds": 0.0, "tokens": 0}
        #: t96: the conversation is on the walk once a walk tool ran or he took one of nemo's taps.
        #: Set from data only (`dispatch`, `_turn`), never from his words or the model's (M13).
        self._walk_on = False

    def _kept_focus(self) -> str | None:
        """t533: the room's focus activity as the room kept it, where it is still one of the
        room's; None in a room that kept none."""
        kept = shown.last(self.folder, shown.FOCUS)
        a = kept and kept.get("activity")
        return a if a and a in walk.processes(self.folder) else None

    def _kept_chart(self) -> str | None:
        """t533: the activity of the room's last chart (its card's: the last it names)."""
        kept = shown.last(self.folder, shown.CHART)
        acts = (kept or {}).get("arguments", {}).get("activities") or [None]
        return str(acts[-1]) if acts[-1] else None

    def _keep_focus(self) -> None:
        """t533: the room's focus, kept in the room where this turn moved it."""
        if self._thread and self._thread != self._kept_focus():
            shown.put(self.folder, shown.FOCUS, {"activity": self._thread}, turn=self.turn_id)

    @property
    def _about(self) -> str | None:
        return self._about_is

    @_about.setter
    def _about(self, activity: str | None) -> None:
        """t395: every activity code answers about is where the room's thread is (`_thread`)."""
        self._about_is = activity
        self._thread = activity or self._thread

    @property
    def walking(self) -> bool:
        """t96: whether the walk's procedure is in front of the model: a walk tool ran, he took a
        tap, the conversation is on an activity, or nemo's interview is under way. Else free
        chat."""
        return self._walk_on or self._activity is not None or self._interview is not None

    @property
    def walk_prompt(self) -> bool:
        """t96 fix 1 (M3): the walk's procedure is in front of the model while `walking`, except
        once the conversation's activity is signed (its run file says CLOSED) and no interview is
        under way: then the short chat prompt is back. Data only; a walk tool on another activity
        (the pick) turns it back on. The taps still follow `walking` (the signed set is drawn)."""
        a = self._activity
        signed = a is not None and self._interview is None and self._closed(a)
        return self.walking and not signed

    def _tools_now(self) -> list[dict[str, Any]]:
        """t96: the prompt and tools for the next model call, from `walk_prompt`: the short chat
        prompt by default, the walk's procedure once the conversation is on the walk."""
        on = self.walk_prompt
        self.messages[0] = {"role": "system", "content": SYSTEM if on else CHAT_SYSTEM}
        if not on and self._analysing:  # t377 D2b: an analysis opens no walk
            # why: each tool is a dict naming its function
            return [t for t in CHAT_TOOLS if t["function"]["name"] not in NOT_ON_ANALYSIS]  # type: ignore[index]
        return TOOLS if on else CHAT_TOOLS

    # tools ──────────────────────────────────────────────────────────────────
    def _method(self) -> dict[str, Any]:
        # why: a JSON object
        return json.loads((self.folder / walk.METHOD).read_text())  # type: ignore[no-any-return]

    def list_activities(self) -> Any:
        """The activity pick: the room-state sheet as a card, its taps drawn by the skin (ticket
        68)."""
        rows = room_sheet(self.folder, self.model)
        if not self._sheet_drawn:
            self._sheet_drawn = True
            self.cards.append(render_sheet(pick_sheet(self.folder, rows), PICK_HEADING))
        return {"activities": [r["activity"] for r in rows], "sheet": rows,
                "shown": "nemo shows the manager this as a card with one tap per activity that can "
                         "be walked. Do not list the activities again or offer them as choices."}

    def room_state(self) -> Any:
        """The sheet, printed to the manager as it is; the model may add one sentence (ticket
        68)."""
        rows = room_sheet(self.folder, self.model)
        # t263: per resource, how soon it is needed back and which activity's MTPD sets it; t339:
        # each chain finding once, beside them, not on every resource its activity uses
        found, chains = needs.split(resource_needs(self.folder, rows))
        if not self.walking:  # t96 fix 2 (95 a, ADR-0023 d6): free chat; a result, never his screen
            return {"activities": rows, "by_mtpd": by_mtpd(rows), "needs": found,
                    "chains": chains, **self._room_facts(rows)}
        self._sheet_text = render_sheet(rows)
        return {
            "sheet": self._sheet_text,
            "by_mtpd": by_mtpd(rows),
            "needs": found,
            "chains": chains,
            **self._room_facts(rows),
            "shown": "the manager sees this sheet word for word as nemo's answer. Add at most one "
            "sentence that hands the choice back; do not restate, rank or pick.",
        }

    # t106: served facts (`nemo.facts`), added to what the model already reads ─────────────────
    def _room_facts(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """The companies, the interviews and, per activity, the figure the record carries beside
        each interview's: in the room-state result, never on the sheet he reads. t309: kept per
        room with the sheet, which is all it reads besides the room's files. t309 part 2: the
        interviews are read once a build, and every activity's figures are served from that."""
        served = kept(self.folder, self.model, "facts", lambda: self._facts_built(rows))
        self._facts_served.append(json.dumps(served, ensure_ascii=False))
        # t249: the interviews were served, so the remembered set takes them as they are now
        on, seen = room_files(self.folder), self._files_seen
        self._files_seen = set(on) if seen is None else (
            {p for p in seen if not _an_interview(p)} | {p for p in on if _an_interview(p)})
        return served

    def _facts_built(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        on_file = facts.read(self.folder)
        return {
            "companies": [self._company_said(c) for c in facts.companies(self.folder)],
            "interviews": self._interviews_said(on_file.held),
            "figures": {
                r["activity"]: {
                    label: "; ".join(lines)
                    for label, lines in facts.carried(
                        self.folder,
                        {k: f["value"] for k, f in r["figures"].items() if f["mark"] == ACCEPTED},
                        "signed" if r["signed"] else "accepted, not signed",
                        self._stated(r["activity"]),
                        on_file,
                    ).items()
                }
                for r in rows
            },
        }

    def _stated(self, activity: str) -> list[facts.Stated]:
        """The figures the activity's prepared draft takes from an interview (`kind` stated), each
        with the interview's path and quote. The value is the drafting model's; `nemo.facts` serves
        it only beside a quote the interview file holds verbatim (t106 fix round 1)."""
        draft = draft_for(activity, self.model, self.folder) or {}
        return [facts.Stated(label, str(item["value"]), item["path"], str(item.get("quote") or ""))
                for a in draft.get("activities") or []
                for label, key in (("MTPD", "mtpd"), ("RTO", "rto"), ("RPO", "rpo"))
                for item in [a.get(key)]
                if isinstance(item, dict) and item.get("kind") == "stated" and item.get("value")
                and str(item.get("path") or "").startswith(interview.HOMES)]

    def _company_said(self, c: facts.Company) -> dict[str, Any]:
        return {"name": c.name, "kind": c.kind, **({"share": c.share} if c.share else {}),
                "listed_in": words.file_said(self.folder, c.source)}

    def _interviews_said(self, held: tuple[facts.Held, ...] | None = None) -> dict[str, Any]:
        held = facts.interviews(self.folder) if held is None else held
        return {"count": len(held), "held": [
            {"file": words.file_said(self.folder, h.path), "path": h.path,
             **{k: v for k, v in (("who", h.who), ("about", h.about), ("when", h.when)) if v}}
            for h in held]}

    def company(self, name: str) -> Any:
        """t106 (M2, r2-35/r2-27): a customer or supplier by name, and every line of the room's
        files that names it. "not found" is nemo's answer only when no file names it."""
        found = facts.company(self.folder, name)
        self._turn_read += [m.path for m in found.mentions]  # t108: a served fact quoting its file
        served = {"asked": found.asked, **({"said": found.said} if found.said else {}),
                  "companies": [self._company_said(c) for c in found.companies],
                  **({"matched": found.how} if found.how else {}),
                  "files_say": [{"file": words.file_said(self.folder, m.path), "path": m.path,
                                 "quote": m.quote, **({"row": m.row} if m.row else {})}
                                for m in found.mentions]}
        self._facts_served.append(json.dumps(served, ensure_ascii=False))
        return served

    def open_activity(self, activity: str) -> Any:
        """t96 fix 2 (95 b): the walk opened on his words, as his pick opens it: where it stands."""
        return self.get_step(activity)

    def get_step(self, activity: str) -> Any:
        if not self._model_turn:  # t96 fix 2 (95 b): his act (a tap) or nemo's own call is the walk
            self._walk_on = True
        c = walk.current(self.folder, activity)
        run = c.saved or {}
        out: dict[str, Any] = {"step": c.stage, "status": run.get("status")}
        if c.stage == walk.STAGE:
            with room_lock(self.folder):  # t238 (C7): read, change and save as one
                scope = (load_state(self.folder, activity).get("scope")
                         or scope_from_files(self.folder, activity))
                save_state(self.folder, activity,
                           {**load_state(self.folder, activity), "scope": scope})
            self._once(f"scope:{activity}", self._scope_card, activity, scope)
            out["nemo_says"] = c.body
            if is_added(self.folder, activity) and not walk._where(c.sources):
                # t72: nemo's proposal says where in the files the process stands; no file names
                # an added one, so its own words would name nowhere
                out["nemo_says"] = (
                    f"{activity} is not in the room's files: the manager added it, so "
                    "it is one activity on its own. Agree it and the BIA goes on to "
                    "step 2, the interview."
                )
            out["scope"] = scope
            out["next"] = (
                "say what the BIA is about — the activity list above, from the room's own "
                "files — and let the manager agree it or change it with set_scope. A BIA "
                "activity is what they agree here; an interview's own sub-steps are "
                "evidence about it, never extra activities."
            )
        elif c.stage == walk.STAGE_2:
            if not c.interviews:  # t72: nothing on file, so nemo's live interview is stage 2
                return {**out, **self._hold_offer(activity, c)}
            draft = self._draft(activity)
            if not draft:
                return {**out, **self._no_draft(activity)}
            out["interviews"] = self._offer(activity, draft, c)
            self._once(f"interviews:{activity}", self._interviews_card, activity, out["interviews"])
            out["next"] = "summarise, let the manager confirm or drop, then confirm_interviews."
        elif c.stage == walk.STAGE_3:
            out["evidence"] = self.get_evidence(activity, "summary")
            out["nemo_taps_about"] = self._taps_about(activity)
        elif c.stage == walk.STAGE_4:
            verdict_ok = bool(c.buttons)
            out["referee_passed"] = verdict_ok
            out["nemo_says"] = by_his_tap(c.body)[:3000]
            if "record" in walk.prints(
                c.stage, "", record_due=verdict_ok
            ):  # t115: it stands untapped
                self._once(f"record:{activity}", self._record_card, activity, c)
        else:
            out["nemo_says"] = c.body[:2000]
            self._documents_quietly(activity)  # t71 fix 2: the way out of a NotDrawnYet refusal
            self._documents_reworded(activity)  # t64 fix 1
            if run.get("status") == walk.REVIEWED:
                sc = walk.signature_card(self.folder, activity)
                out["next"] = "the handover is accepted; the manager signs (sign)"
                out["owner_nemo_expects"] = list(handover.owners(sc.proposal[walk.BIA]))
                self._once(f"sign:{activity}", self._signature_card, activity,
                           out["owner_nemo_expects"])
        return out

    # standing refusals ────────────────────────────────────────────────────
    def _heading(self, activity: str) -> str:
        """t377 G7: an activity on a card's heading, as the process map names it, never its slug."""
        return map_name(self.folder, self._room_name(activity))

    def _stage_2_title(self, activity: str) -> str:
        """t432: a stage-2 card's title, its short heading and the activity, and under it the
        stage's long line as its subtitle (`walk.Card.subtitle`), the one place that says it."""
        return (f"**{walk.HEADING_2} \u00b7 {self._heading(activity)}**\n\n"
                f"{walk.LONG_NAMES[walk.STAGE_2 - 1]}")

    def _room_name(self, activity: str) -> str:
        """The room's own spelling of an activity (as `list_activities` gives it), else as given."""
        return next((p for p in walk.processes(self.folder)
                     if p == activity or slug(p) == slug(activity)), activity)

    def _no_draft(self, activity: str) -> dict[str, Any]:
        if activity not in walk.processes(self.folder):  # a name the room does not hold
            return wrong_call(f"no activity named {activity!r}",
                              activities=walk.processes(self.folder))
        return standing(f"There is no prepared draft for {activity} in this prototype, so its "
                        "interviews can't be offered, and nothing in this walk will change that.",
                        ["Pick another activity"], "draft_exists")

    def _referee_refuses(self, activity: str, c: walk.Card) -> dict[str, Any]:
        """Stage 4, the referee refusing the record: nemo's own sentences, wrapped in one line."""
        _, verdict = walk._refereed(self.folder, c.saved or {}, walk._method(self.folder))
        problems = " ".join(walk._refusal_says(r) for r in verdict.rejections) or c.body
        gap = any(r.kind == nemo_refusal.TARGET_OUTSIDE_MTPD for r in verdict.rejections)
        # t154: a record refused for naming no RTO, where a gap left it for him to state: his tap
        # asks for it, and going back to step 3 stays the other way out
        state_rto = any(r.kind == nemo_refusal.NO_RECOVERY_TARGET for r in verdict.rejections) \
            and bool(self._rto_wanted(activity, load_state(self.folder, activity)))
        # t73: each tap is one call from data. The gap names the figure (the RTO), so "Change the
        # figure" asks for its value; any other refusal names no figure a tap could fix, so its one
        # move is back to step 3, where every decision is kept.
        return standing(
            f"nemo's referee won't pass the record for {self._room_name(activity)}, so it can't be "
            f"accepted until this changes: {problems}",
            [ACK_GAP, CHANGE_FIGURE] if gap else [STATE_RTO, GO_BACK] if state_rto else [GO_BACK],
            "record_changes",
        )

    @staticmethod
    def _carry_on(c: walk.Card) -> str:
        """The one move the walk is waiting on, as a tap."""
        if c.stage == walk.STAGE_5:
            return "Accept the handover"
        if c.stage == walk.STAGE_4 and c.buttons:
            return "Accept the record"
        return f"Carry on with step {c.stage}"

    def _precondition(self, waits_on: str, activity: str) -> Any:
        """What a standing refusal waits on, read off the files now."""
        if waits_on == "draft_exists":
            return draft_for(activity, self.model, self.folder) is not None
        run = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        now = [run.get("status"), run.get("stage")]
        if waits_on in ("record_changes", "record_faithful", "question_answered"):
            now.append(load_state(self.folder, activity).get("decisions"))
        if waits_on == "record_faithful":  # fix 2: the documents on file, written again or not
            now.append(
                sorted(
                    (str(p), p.read_text())
                    for p in (self.folder / "output").rglob(handover.HANDOVER)
                )
            )
        return json.dumps(now, sort_keys=True, default=str)

    def dispatch(self, name: str, args: dict[str, Any]) -> tuple[Any, bool]:
        """(result, from_ledger). A move this conversation's ledger holds as refused gets the same
        refusal, whatever its arguments, until what it waits on changes; then it runs again."""
        activity = str(args.get("activity") or "")
        if activity:  # t377c G1: every tool gets the room's spelling, whatever the model wrote
            args = {**args, "activity": (activity := self._room_name(activity))}
        # t96 fix 2 (95 b, the review's M2; 8_nemo_check's ruling): in free chat the model's calls
        # are CHAT_TOOLS only, so no advancing tool runs there, and get_step is a reading that opens
        # nothing. A walk opens through the pick route: his pick tap, list_activities, or
        # open_activity when he asks to start or carry on. Keyed on data (whose turn, whether the
        # conversation is on the walk, which tool), never on anyone's words (M13).
        free = self._model_turn and not self.walking
        if free and name not in CHAT_TOOL_NAMES:
            return wrong_call(FREE_CHAT_TOOLS.format(tool=name), tools=list(CHAT_TOOL_NAMES)), False
        if free and self._analysing and name in NOT_ON_ANALYSIS:  # t377 D2b
            return wrong_call(NOT_ON_ANALYSIS_SAYS), False
        if free and name == "get_step":
            self._turn_named.append(self._room_name(activity))  # t108: a reading touches it
            return self._reading(args), False
        # t377p: the walk is on his activity, and a model call never moves it to another (v7 r5:
        # a `get_step` on the BIA the chat had named drew its stage 1 card over production's open
        # decision). A reading stays a reading; any other step waits on his tap. r2: an activity
        # his own typed line names is his choice ("Helpdesk now", t73), and every walk tool on it
        # moves the walk as before; what the model read this turn never counts as his line.
        if self._model_turn and self._activity and activity and activity != self._activity \
                and activity not in self._line_named:
            if name in ("get_step", "get_evidence"):
                return self._reading(args, name), False
            if name in WALK_TOOL_NAMES:
                return wrong_call(OTHER_ACTIVITY_SAYS.format(
                    walk=self._heading(self._activity), named=self._heading(activity))), False
        # The conversation's activity is the one the last tool call named, in the room's spelling;
        # `list_activities` means the manager is choosing, so it is on none. Read from the call's
        # arguments only, never from the model's or the manager's words.
        if name in WALK_TOOL_NAMES:  # t96: a walk tool ran, so the walk's procedure is in front
            self._walk_on = True
        if name == "list_activities":
            self._activity = None
        # t318: a proposal opens no activity; t377 O: nor a referral's `activity`, which it does
        # not take (v7 r5: its refused call opened stage 1 mid-analysis)
        elif activity and name not in ("propose_dependency", "propose_referral"):
            self._activity = self._room_name(activity)
        key = (name, slug(activity))
        held = self._standing.get(key)
        # fix 1 (the review's finding 9): the ledger exists to stop the MODEL retrying a move it
        # has just been refused. Anyone else calling that tool is not retrying, and his own tap is
        # usually the very act the refusal waits on — so serving it to him deadlocked t76's "The
        # arrangements can now meet the target": the tap was still drawn, and what he read was
        # addressed to the model ("Ask him whether…", since corrected to second person). It
        # never cleared. This is the enumeration rather than the instance: every tool at once, so
        # t71's own hand-written eviction on the reservation route is no longer needed, and a tool
        # added later cannot be silently missed.
        if held and self._model_turn \
                and self._precondition(held["result"]["waits_on"], held["activity"]) == held["now"]:
            return held["result"], True
        self._standing.pop(key, None)
        result = self.call(name, args)
        if (
            isinstance(result, dict)
            and result.get("refusal") == STANDING
            and result.get("hold", True)
        ):
            self._standing[key] = {"result": result, "activity": activity,
                                   "now": self._precondition(result["waits_on"], activity)}
        return result, False

    def _reading(self, args: dict[str, Any], name: str = "get_step") -> Any:
        """t96 fix 2 (95 b): get_step in free chat, served as a reading. It draws nothing (the card
        is drawn when the walk opens, not spent here), opens no walk and leaves out the walk's
        instructions to the model. t377p: so is a reading of an activity the walk is not on."""
        cards, carded = list(self.cards), set(self._carded)
        result = self.call(name, args)
        self.cards, self._carded = cards, carded
        if isinstance(result, dict):
            result = {
                k: v for k, v in result.items() if k not in ("next", "nemo_says", "nemo_taps_about")
                # t477 (replay row 3): the walk's own wait word, which an answer read back to him
                and not (k == "status" and v == walk.AWAITING_HUMAN)
            }
        return result

    def _once(self, key: str, draw: Callable[..., None], *args: Any) -> None:
        if key not in self._carded:
            self._carded.add(key)
            draw(*args)

    def _offer(self, activity: str, draft: dict[str, Any], c: walk.Card) -> list[dict[str, Any]]:
        """Stage 2's offer: the draft's interviews over the floor of nemo's own offer (13_nemo,
        t66).

        nemo's stage-2 card offers the interviews filed under the activity's department; none of
        those can be dropped by the draft, and one from another department comes only with its
        reason (`PROTOTYPE_draft.with_floor`).
        """
        return drafting.with_floor(draft["interviews"], [i.path for i in c.interviews], activity)

    def confirm_interviews(self, activity: str, drop: list[str] | None = None) -> Any:
        iv = self._interview
        if iv and iv["done"] and iv["activity"] == self._room_name(activity) \
                and not self._model_turn:  # t377k: filing it is his keep tap's, never the model's
            # t72: the interview just held is filed first; the offer it joins is then confirmed
            return self._file_held(iv["activity"])
        # t377k: a model turn never rebuilds an added activity's draft, which is a write
        draft = draft_for(activity, self.model, self.folder) if self._model_turn \
            else self._draft(activity)
        if not draft and not (self._model_turn and is_added(self.folder, activity)):
            return self._no_draft(activity)
        c = walk.current(self.folder, activity)
        if (waiting := self._naming_waits(c)):
            # t71 fix 1: nemo would take this confirmation's "endorsed" as the reservation's words
            return waiting
        if c.stage != walk.STAGE_2:
            return wrong_call(
                f"the walk is at step {c.stage}, not step 2", now=self.get_step(activity)
            )
        if self._model_turn:
            # t377k (as 377c G2): the interviews are his to keep. Nothing is written; the stage 2
            # card stands with its own taps, and his Keep or Drop tap is the same call
            return {"confirmed": False, "step": walk.STAGE_2,
                    "next": INTERVIEWS_ARE_HIS.format(activity=_said_name(self.folder, activity))}
        assert draft  # his turn: `_draft` refused above when there is none
        keep = [i["path"] for i in self._offer(activity, draft, c) if i["path"] not in (drop or [])]
        offered = {i.path: i for i in c.interviews}
        primary = next((p for p in keep if p in offered), None)
        if primary is None:
            return wrong_call("none of the kept interviews is filed under this department, so nemo "
                              "has nothing to bind", offered_by_department=list(offered))
        picked = walk.chosen(self.folder, activity, primary)
        # t168: nemo keeps every interview he kept, in his order, on the run record
        cards = walk.answer(self.folder, activity, walk.ENDORSED, picked.revision,
                            picked=picked.interviews[0], confirmed=keep,
                            record_revision=picked.record_revision)
        with room_lock(self.folder):  # t238 (C7): read, change and save as one
            state = load_state(self.folder, activity)
            scope = state.get("scope") or scope_from_files(self.folder, activity)
            # t183: the draft enters the walk with its conflicts and items said by name in its prose
            # (its reasons are on the cards he reads); the ids stay where they are ids
            draft = words.Names(self.folder, activity, self.model).draft_said(
                collapse_to_scope(draft, scope["activities"]))
            added = {}
            if is_added(self.folder, activity):
                # t72: the manager's name on the record, as he gave it, and the room files
                # (beyond the interviews) its draft quotes, which the referee must be able to read
                if len(draft["activities"]) == 1:
                    draft["activities"][0]["name"] = scope["activities"][0]
                added = {
                    "sources": sorted(
                        (quoted_paths(draft) | {r["path"] for r in attached_rows(draft, state)})
                        - set(keep)
                    )
                }
            save_state(self.folder, activity, {**state, "scope": scope, "interviews": keep,
                                               "draft": draft, "decisions": {},
                                               "draft_model": draft["meta"]["model"], **added})
        return {"nemo_did": cards[-1].body if cards else "nothing", "kept": keep,
                "now": self.get_step(activity)}

    # the risk register at stage 2 of an added activity (13_nemo, t72b) ──────────────────────
    def _risk_marks(self, activity: str) -> tuple[list[dict[str, Any]], set[str], set[str]]:
        """(every row of the register, from the file; the ids the name rule keeps; the ids he
        kept)."""
        return (drafting.risk_rows(self.folder),
                {r["id"] for r in drafting.risk_floor(self.folder, activity)},
                {r["id"] for r in load_state(self.folder, activity).get("risk_rows_kept") or []})

    def keep_risk_row(self, activity: str, row: str, keep: bool = True) -> Any:
        """He keeps or drops one risk-register row as evidence for an activity he added. A kept row
        is attached from its file line, word for word, exactly like a floor row; it sets no figure.
        A row the name rule keeps is the floor's and is not dropped here."""
        activity = self._room_name(activity)
        keep = keep is True or str(keep).strip().lower() == "true"  # a model may send "false"
        if not is_added(self.folder, activity):
            return wrong_call("risk-register rows are kept only for an activity the manager added; "
                              "a filed activity's evidence is its draft's")
        c = walk.current(self.folder, activity)
        if c.stage != walk.STAGE_2:
            return wrong_call(f"the walk is at step {c.stage}; rows are kept at step 2")
        rows, floor, _ = self._risk_marks(activity)
        found = next((r for r in rows if r["id"] == str(row).strip()), None)
        if found is None:
            return wrong_call(
                f"no row {row!r} in {drafting.RISK_REGISTER}", rows=[r["id"] for r in rows]
            )
        if found["id"] in floor:
            return {
                "row": found["id"],
                "kept": True,
                "by": "the name rule",
                "note": f"this row names {drafting.added_name(self.folder, activity)!r}, so nemo "
                "attaches it whatever is kept or dropped",
            }
        with room_lock(self.folder):  # t238 (C7): read, change and save as one
            state = load_state(self.folder, activity)
            kept = [r for r in state.get("risk_rows_kept") or [] if r["id"] != found["id"]]
            if keep:
                kept.append({**found, "verified_quote": True, "kept_by": "manager"})
            save_state(self.folder, activity, {**state, "risk_rows_kept": kept})
        self.cards.append("\n".join(
            self._risk_lines(activity, f"**Risk register · {self._heading(activity)}**")))
        return {
            "row": found["id"],
            "kept": bool(keep),
            **(
                {
                    "attached_as": {
                        "path": found["path"],
                        "line": found["line"],
                        "quote": found["quote"],
                    }
                }
                if keep
                else {}
            ),
            "sets_no_figure": True,
            "now": self.get_step(activity),
        }

    def _risk_text(self, r: dict[str, Any]) -> str:
        """t96 fix 1 (I1): a register row's text as he reads it, on the card and on its tap alike:
        each code in it replaced by its name from the room's files (`words.codes_by_name`)."""
        return words.codes_by_name(r["text"], self.folder)

    def _drawn(self, s: Any) -> str:
        """t96 fix 2 (1a): draft-written text on a card he reads, codes said by their names."""
        return words.drawn(str(s), self.folder)

    def _risk_lines(self, activity: str, heading: str) -> list[str]:
        """The register's rows, one line each (category, text, owner), drawn from the file, the
        kept ones marked: the name rule's, and his own. t96 fix 1: no id column he reads; the id
        stays in the data and in each tap's call."""
        rows, floor, kept = self._risk_marks(activity)
        name = drafting.added_name(self.folder, activity)
        lines = [
            heading + f" ({len(rows)} rows, {drafting.RISK_REGISTER}). Rows that name "
            f"\u201c{name}\u201d are kept already. Keep any other row that is about "
            f"{name}: it is quoted word for word from its line, as evidence, and sets "
            "no figure.",
            "",
        ]
        for r in rows:
            mark = ("**kept** (names it) \u00b7 " if r["id"] in floor else
                    "**kept** (yours) \u00b7 " if r["id"] in kept else "")
            lines.append(f"- {mark}{r['category']} \u00b7 {self._risk_text(r)} \u00b7 {r['owner']}")
        return lines + ([] if rows else ["- none"]) + [""]

    def _risk_taps(self, a: str) -> list[tuple[str, dict[str, Any]]]:
        """Stage 2 of an added activity: one tap per row the name rule did not keep — "Keep:
        <text>", or "Drop: <text>" once kept — each its one `keep_risk_row` call. Filed activities:
        none. t96 fix 1 (I1): <text> is the row's own text as its stage-2 card line prints it
        (`_risk_text`), whole and from the same data, so card and tap never disagree; the id is in
        the call's args only (ADR-0023 decision 7: no code reaches him in chat)."""
        if not is_added(self.folder, a):
            return []
        rows, floor, kept = self._risk_marks(a)
        return [(f"{'Drop' if r['id'] in kept else 'Keep'}: {self._risk_text(r)}",
                 tool_tap("keep_risk_row", activity=a, row=r["id"], keep=r["id"] not in kept))
                for r in rows if r["id"] not in floor]

    # an activity the files don't list, and its live interview (13_nemo, t72) ───────────────
    def add_activity(self, name: str) -> Any:
        """The model's route: it calls this with the manager's name for the activity."""
        if not slug(name):
            return wrong_call("no activity name was given: pass the manager's own name for it")
        room_name, new = self._add(name, ROUTE_TOOL)
        return {
            "added": room_name,
            "new_in_room": new,
            "file": ADDED,
            "next": "its BIA is at step 1 now: carry on with it.",
            "now": self.get_step(room_name),
        }

    def _add(self, name: str, route: str) -> tuple[str, bool]:
        room_name, new = add_to_room(self.folder, name, route)
        if new:
            self.log("added", {"model": self.model, "name": room_name, "route": route})
            start_draft(self.folder, room_name, self.model)
        self._activity = room_name
        return room_name, new

    def _hold_offer(self, activity: str, c: walk.Card) -> dict[str, Any]:
        """Stage 2 with no interview on file: nemo's own offer to hold it here and now, as a card
        with one server tap. Never a dead end and never a steer (ticket 72 item 3)."""
        iv = self._interview
        if iv and iv["activity"] == activity:
            return {"interview": "held, waiting to be confirmed" if iv["done"] else "under way",
                    "next": "the manager confirms it (confirm_interviews)" if iv["done"] else
                    "nemo is asking the questions; wait for the manager's answers"}
        self._once(f"hold:{activity}", lambda: self.cards.append(
            f"{self._stage_2_title(activity)}\n\n{c.body}\n\n{c.decision}"))
        self._hold_offered = activity
        self._register(HOLD_IT_NOW, {"kind": "hold", "activity": activity})
        return {
            "no_interview_on_file": True,
            "nemo_says": c.body,
            "next": "nemo offers to hold the interview here and now, with a tap. If the manager "
            "agrees in words, call hold_interview. nemo asks the questions; you ask none.",
        }

    def hold_interview(self, activity: str) -> Any:
        activity = self._room_name(activity)
        c = walk.current(self.folder, activity)
        if self._interview is not None:  # fix round 1: a second start would wipe the answers held
            return wrong_call("an interview is already under way or held, waiting to be confirmed")
        if c.stage != walk.STAGE_2 or c.interviews:
            return wrong_call(
                "the live interview is stage 2's, for an activity with no interview on file",
                now=self.get_step(activity),
            )
        say, next_ = self._start_interview(activity)
        return {"server_turn": True, "say": say, "next": next_, "interview": "started"}

    def _start_interview(self, activity: str) -> tuple[str, list[str]]:
        self._interview = {"activity": activity, "turns": [], "question": "", "say": "",
                           "done": False, "note": ""}
        return self._ask_next()

    def _ask_next(self) -> tuple[str, list[str]]:
        """nemo's next question (`conduct.conduct`), or the end: the held interview whole, as nemo's
        own card, and one tap to confirm it. Nothing of it is on disk until then (nemo's
        contract)."""
        iv = self._interview
        assert iv is not None
        nxt = conduct.conduct(
            iv["activity"], tuple(iv["turns"]), lane=interview_lane(self.model, self.folder)
        )
        if nxt.question:
            iv["question"] = nxt.question
            iv["say"] = (f"*Interview · {iv['activity']} · question {len(iv['turns']) + 1} of "
                         f"{conduct.TURNS}*\n\n{nxt.question}")
            self._register(STOP_INTERVIEW, {"kind": "stop", "activity": iv["activity"]})
            return iv["say"], [STOP_INTERVIEW]
        return self._end_interview(nxt.note)

    def _end_interview(self, note: str = "") -> tuple[str, list[str]]:
        """The interview over, by its length, a quiet lane, or the manager's stop: what was said is
        shown whole with one tap to confirm it; with nothing said, stage 2's offer stands again."""
        iv = self._interview
        assert iv is not None
        iv["done"], iv["note"] = True, note
        if not iv["turns"]:  # nothing was said (a quiet lane, or stopped at once): nothing held
            self._interview = None
            self._register(HOLD_IT_NOW, {"kind": "hold", "activity": iv["activity"]})
            return note or walk.DECISION_NO_INTERVIEW, [HOLD_IT_NOW]
        held = walk.held_interview(self.folder, iv["activity"], tuple(iv["turns"]))
        # t165 (ticket 23 on the phone): the card goes to Chainlit's markdown as it is, so the
        # preview is fenced; its `---` and `# ` then read as the transcript's own characters
        self.cards.append("\n\n".join([self._stage_2_title(iv["activity"]),
                                        *([note] if note else []), held.body,
                                        verbatim.block(held.interviews[0].preview)]))
        self._register(KEEP_INTERVIEW, {"kind": "keep", "activity": iv["activity"]})
        return walk.DECISION_CHOSEN, [KEEP_INTERVIEW]

    def _draft(self, activity: str) -> dict[str, Any] | None:
        """The prepared draft; for an added activity, rebuilt when the room's own interviews for it
        are not the ones it was drafted from (its interview was filed since)."""
        draft = draft_for(activity, self.model, self.folder)
        if is_added(self.folder, activity):
            own = drafting.own_interviews(self.folder, self._room_name(activity))
            if draft is None or (draft.get("meta") or {}).get("own_interviews") != own:
                # t82 fix 3: the one place a draft is written on his turn, so the one place that
                # tells him, before the call: every route that gets here says it, listed or not
                self.say_now(drafting_line(self._room_name(activity), first=draft is None))
                draft = draft_added(self.folder, self._room_name(activity), self.model) or draft
        return draft

    def _file_held(self, activity: str) -> dict[str, Any]:
        """The interview just held goes on file at `walk.interview_path`, in the bytes nemo's own
        card previewed, and stage 2 is NOT answered here (fix round 1): with an interview on file,
        the draft is rebuilt from the room and stage 2 is the ordinary offer, with its drops and
        `confirm_interviews`, exactly as for a filed activity."""
        iv = self._interview
        assert iv is not None and iv["done"]
        held = walk.held_interview(self.folder, activity, tuple(iv["turns"])).interviews[0]
        write_file(self.folder, held.path, held.preview)
        self._interview = None
        self.log("interview_filed", {"activity": activity, "path": held.path,
                                     "answers": len(iv["turns"])})
        return {
            "filed": held.path,
            "now": self.get_step(activity),
            "next": "the interview is on file and the draft is rebuilt; this is step 2's offer: "
            "summarise, let the manager confirm or drop, then confirm_interviews.",
        }

    def _interview_state(self) -> dict[str, Any]:
        iv = self._interview
        return {"interview": {"activity": iv["activity"], "answered": len(iv["turns"]),
                              "done": iv["done"]}} if iv else {}

    @holds_the_room
    def set_scope(self, activity: str, activities: list[str], why: str = "") -> Any:
        """The manager's own scope list. Only at stage 1: a split later would change what they
        signed."""
        c = walk.current(self.folder, activity)
        if c.stage != walk.STAGE:
            # A step-1 tool at a later step: the ticket's own example of a wrong call.
            return wrong_call(
                f"the walk is at step {c.stage}; the scope is set at step 1. To change "
                "it now, the walk has to go back to step 1, which drops what follows it."
            )
        state = load_state(self.folder, activity)
        scope = {"activities": list(activities), "source": "the manager, in chat",
                 "how": why or "set by the manager"}
        save_state(self.folder, activity, {**state, "scope": scope})
        return {"scope": scope}

    def get_evidence(self, activity: str, what: str) -> Any:
        state = load_state(self.folder, activity)
        draft = state.get("draft")
        if not draft:
            return wrong_call("step 2 is not done yet")
        method = self._method()
        eff = effective(draft, state.get("decisions", {}), method)
        open_ = ordered_open(state)  # t117: nemo's order, the one the taps take
        if what == "summary":
            carries = self._record_to_be(state, method)
            rows = attached_rows(draft, state)
            risk = (
                {
                    "risk_register_rows": [
                        {
                            "row": r["id"],
                            "path": r["path"],
                            "line": r["line"],
                            "quote": r["quote"],
                            "attached": "names the activity (nemo's floor)"
                            if r["origin"] == ROW_FLOOR
                            else "kept by the manager at step 2",
                        }
                        for r in rows
                    ],
                    "risk_rows_note": "evidence only, quoted word for word: they set no score "
                                      "and no clock",
                }
                if rows
                else {}
            )
            return {
                **risk,
                "record_will_carry": carries,
                "activities": [
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "owner": (a.get("owner") or {}).get("name"),
                        "mtpd_the_impact_scores_give": a["derived_now"],
                        "mtpd_in_draft": (a.get("mtpd_now") or {}).get("value"),
                        "rto": (a.get("rto_now") or {}).get("value"),
                        "rpo": (a.get("rpo_now") or {}).get("value"),
                        "categories_stated_by_interviewee": sum(
                            o == "stated" for o in a["origin"].values()
                        ),
                        "categories_proposed_by_you": sum(
                            o == "proposed" for o in a["origin"].values()
                        ),
                        "categories_blank": sum(
                            o in ("none", "rejected", "blank") for o in a["origin"].values()
                        ),
                        "drivers_at_mtpd": [
                            lens
                            for lens, r in a["grid_now"].items()
                            if isinstance(r.get(a["derived_now"]), int) and r[a["derived_now"]] >= 4
                        ],
                    }
                    for a in eff
                ],
                "interviews_used": len(state["interviews"]),
                "open_proposals": sum(i["type"] != "conflict" for i in open_),
                "open_conflicts": sum(i["type"] == "conflict" for i in open_),
                "gaps": draft.get("gaps"),
                "note": "Proposals are YOUR proposals: say so.",
                "scope": state.get("scope"),
                "scope_note": draft.get("scope_note"),
            }
        if what == "proposals":
            return {"open": served_live(open_, [i for i in open_ if i["type"] != "conflict"][:12])}
        if what == "conflicts":
            return {"open": served_live(open_, [i for i in open_ if i["type"] == "conflict"])}
        if what == "stated":
            stated = [(a["name"], lens, r) for a in draft["activities"]
                    for lens, r in a["grid"].items() if r.get("kind") == "stated"][:20]
            # t366 (2nd amend): the interviews these rows quote are read, as t108's served facts,
            # where they name this activity (317's write step names the activity its read names)
            self._turn_read += sorted({p for _, _, r in stated if (p := r.get("path"))
                                       and p.startswith(interview.HOMES)
                                       and activity in interview._named_in(self.folder / p)})
            return {"stated": [{"activity": name, "lens": lens, "scores": r["scores"],
                                "quote": r.get("quote"), "speaker": r.get("speaker")}
                               for name, lens, r in stated]}
        if what == "check":
            return self._dry_run(activity, state, method)
        if what == "grid":  # t115: a read. The rows go to the model; nothing is printed
            return {"grid": [{"activity": act["name"], "rows": act.get("impact_grid")} for act in
                             build_proposal(draft, state, method, self.folder)["activities"]],
                    "still_open": len(open_)}
        found = [i for i in items(draft) if i["id"] == what]
        # t183: each open id as an item_id, which `_served` names beside it
        return found[0] if found else wrong_call(f"no item {what!r}",
                                                 ids=[{"item_id": i["id"]} for i in open_][:30])

    def _all_accepted(self, state: dict[str, Any], method: dict[str, Any]) -> dict[str, Any]:
        """The record-to-be with every open proposal accepted as proposed (conflicts: the side
        recommended) and the manager's own decisions over them. t71: each is taken through
        `_apply`, in nemo's tap order, the way a tap on it would take it, so a recommended side
        moves the figure it implies (it did not: Maintenance's C2 and C3 said 0–4 h, and the
        record-to-be kept the draft's 8 h)."""
        trial = json.loads(json.dumps(state, default=str))
        for i in ordered_open(trial):
            if i["id"] not in (trial.get("decisions") or {}):
                self._apply(trial, i["id"], "accept", side=i.get("recommend"))
        return build_proposal(trial["draft"], trial, method, self.folder)

    def _record_to_be(self, state: dict[str, Any], method: dict[str, Any]) -> dict[str, Any]:
        """The figures the record will carry, read from `build_proposal` (13_nemo, t72 fix 1).

        With every open proposal accepted as proposed. The record's RPO is derived from the
        dependency register and replaces a looser one, and a recovery gap is carried as the
        method's RTO with the gap flagged, so these can differ from the draft's own figures; on
        seed 7272 that difference, unseen at step 3, turned into a reopen loop at step 5."""
        proposal = self._all_accepted(state, method)
        out = {}
        for a in proposal["activities"]:
            meta = {m["label"]: m for m in a["evidence_meta"]}
            out[a["name"]] = {"MTPD": meta.get("MTPD", {}).get("value"),
                              "RTO": meta.get("RTO", {}).get("value"),
                              "recovery_gap": any(m.get("gap") for m in meta.values()),
                              "RPO": meta.get("RPO", {}).get("value"),
                              "RPO_where_it_comes_from": meta.get("RPO", {}).get("quote") if
                              meta.get("RPO", {}).get("origin") == "method" else "as settled here"}
        return {
            **out,
            "note": "what the record and the handover will say, with every open proposal "
            "accepted as proposed: say these figures, not the draft's, when they differ",
        }

    def _dry_run(self, activity: str, state: dict[str, Any], method: dict[str, Any]) -> Any:
        saved = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        proposal = self._all_accepted(state, method)
        run = {**saved, **proposal, "method": saved.get("method") or walk._method(self.folder)}
        files = _patched_readable(self.folder, run)
        record = bia.build(run, files)
        # t132: a chat confirmation is held to his turn's line, as the signature holds it; t171: a
        # register row to the room's register. A proposal assumed accepted here has no act of his
        # yet (no turn), so that is no refusal to tell the model: his tap will give it one
        verdict = referee.review(
            record,
            run["method"],
            {**files, **walk.cited_register(self.folder, record)},
            walk.confirmed_turns(self.folder, record),
        )
        # (132's qa fix: a confirmation naming no turn is refused as evidence nothing was checked
        # against, with its empty turn part)
        verdict.rejections = [r for r in verdict.rejections
                              if not (r.kind == nemo_refusal.EVIDENCE_UNCHECKED
                                      and "turn" in r.parts and not r.parts["turn"])]
        # t71 (OPEN-4): what is not refused is not settled; it stays open into the signature
        # t96: the id the signature accepts it by stays, beside the words "open item"
        opened = [OPEN_ITEM.format(at=at, text=text) for at, text in
                  handover.items(record, {"findings": [str(f) for f in verdict.findings]})]
        return {
            "would_refuse": verdict.rejections[:10],
            "would_flag": verdict.findings[:10],
            "open_at_the_signature": opened,
            "open_note": "these are not refused, and not settled either: each stays open into "
            "the signature, where the manager accepts it by id. Say which stay "
            "open; never say nothing is open while this list has an item.",
            "note": "assumes every open proposal is accepted as proposed",
            "how_to_fix": "change a figure with decide(item_id='<activity "
                          "id>.rto|mtpd|rpo|<category>', "
            "decision='change', value=... or scores=...). A recovery gap is the "
            "manager's to acknowledge and never yours: nemo draws him the "
            f"“{ACK_GAP}” tap, and until he takes it the gap is a proposal. "
            "Propose the fix to the manager first.",
            "activity_ids": {a["id"]: a["name"] for a in state["draft"]["activities"]},
        }

    def _apply(self, state: dict[str, Any], item_id: str, decision: str, side: int | None = None,
               value: str | None = None, scores: dict[str, Any] | None = None,
               note: str | None = None) -> dict[str, Any] | None:
        """Write one decision into `state` (in memory), as `decide` records it: a settled
        conflict moves the figure it implies, unless that would loosen the one already carried.
        A wrong call when the item does not exist. `decide` saves the result; a tap reads the
        record-to-be off a copy of it (t73b), so both take the same path."""
        draft = state.get("draft") or {"activities": []}
        known = known_items(draft)
        if item_id not in known:
            return wrong_call(
                f"no item {item_id!r}", open_ids=[i["id"] for i in open_items(state)][:30]
            )
        if known[item_id]["type"] == "conflict" and side is None:
            side = known[item_id].get("recommend") if decision == "accept" else None
        seq = state["seq"] = int(state.get("seq") or 0) + 1  # fix 2: the order decisions came in
        state.setdefault("decisions", {})[item_id] = {
            "decision": decision, "side": side, "value": value, "scores": scores, "note": note,
            "at": time.strftime("%H:%M:%S"), "seq": seq}
        touched = (state.get(REOPENED) or {}).get("touched")
        if touched is not None:  # t71: decided again since the reopen
            touched.append(item_id)
        if known[item_id]["type"] == "conflict" and isinstance(side, int):
            # A settled conflict moves the figure it is about, so the manager's choice lands in the
            # record and not only as a line on the handover. A side that implies no figure says so.
            sides = known[item_id].get("sides") or []
            implied = sides[side].get("implies") if side < len(sides) else None
            if isinstance(implied, dict) and implied.get("item_id") and implied.get("value"):
                # The sub-steps merged into one scoped activity, so several conflicts can point at
                # the same figure. A settled conflict may only TIGHTEN it: the method's MIN
                # principle is the whole reason the merge is conservative, and "last one written
                # wins" produced a 24 h MTPD over a 0-4 h one on 2026-09-17.
                field = str(implied["item_id"]).rsplit(".", 1)[-1]
                now = next((f.get(f"{field}_now", {}).get("value")
                            for f in effective(draft, state.get("decisions", {}), self._method())
                            if f["id"] == str(implied["item_id"]).split(".")[0]), None)
                new_minutes = duration.minutes(str(implied["value"]))
                old_minutes = duration.minutes(str(now)) if now else None
                looser = (field in ("mtpd", "rto") and new_minutes is not None
                          and old_minutes is not None and new_minutes > old_minutes)
                slot = state["decisions"].get(implied["item_id"]) or {}
                his = (
                    slot
                    if field in ("mtpd", "rto") and not slot.get("by") and explicit_change(slot)
                    else None
                )
                # fix 4: a side that acknowledges the recovery gap is a decision about the gap, not
                # a duration that competes with his: taken, it is his latest decision on the RTO and
                # is written over it (his typed one kept underneath, `over`), so the record flags
                # the
                # gap the tap named. An RTO he types after it replaces it in turn (latest wins).
                gap = field == "rto" and is_gap(implied["value"])
                # Exact text is safe for "the figure carried is his": `effective` carries his
                # decision's own value string, unchanged; a parse would make "0–4 h" equal "0 h".
                if not gap and his is not None and str(now) == str(his["value"]) \
                        and not tighter(implied["value"], now):
                    # fix 3: the figure carried is his typed one, and this side is not strictly
                    # tighter by the same rule as everywhere (a band like "0–4 h" is no point to
                    # compare): his figure stays, and nothing is replaced silently
                    state["decisions"][item_id]["note"] = (
                        f"{note or ''} (kept his {now}: this side implies {implied['value']})"
                    ).strip()
                    state["decisions"][item_id]["kept"] = now
                    state["decisions"][item_id]["kept_his"] = True
                elif looser:
                    state["decisions"][item_id]["note"] = (
                        f"{note or ''} (kept {now}: this side implies {implied['value']}, which is "
                        "looser than the figure the merged activity already carries)").strip()
                    state["decisions"][item_id]["kept"] = now
                else:
                    if touched is not None:
                        touched.append(implied["item_id"])
                    under = explicit_change(state["decisions"].get(implied["item_id"]))
                    state["decisions"][implied["item_id"]] = {
                        **({"over": under} if under else {}),  # fix 2c: his change, kept underneath
                        # t85: taking a side that carries the gap IS his acknowledgement, so the
                        # decision records the acknowledgement's own value — the one a room saved
                        # before t85 already holds (t75), whatever spelling the side was said in
                        "decision": "change", "value": GAP if gap else implied["value"],
                        **({"scores": row} if (row := _implied_row(draft, implied)) else {}),
                        "note": f"settled by the manager on conflict {item_id}", "by": item_id,
                        "at": time.strftime("%H:%M:%S"), "seq": seq}
        self._note_gaps(state)
        return None

    def _note_gaps(self, state: dict[str, Any]) -> None:
        """t76: an acknowledged recovery gap written down once, here, wherever it came from — his
        tap, a typed value, a side that carries it, an accepted proposal — because every one of
        them is a DECISION of his on the RTO item that makes the record carry the gap word. Fix 1
        (I1): nemo's own proposal is not one of them. `effective` falls back to the draft's figure
        while he has decided nothing, and on this seed a draft proposes the gap word itself, so
        without the decision below the walk's first score acknowledged a gap he never met.

        It stays until he closes it in his own words. Fix 1 (I3): a closed one stays closed while
        the decision that raised it stands (`on`, its `seq`); a later decision that carries the gap
        word again is a new acknowledgement. Fix 1 (I4): whose account it rests on is resolved
        here, when he acknowledges it, so taking another side of that conflict afterwards — or
        leaving it unresolved — never moves the account the record carries.
        """
        draft = state.get("draft") or {}
        if not draft.get("activities"):
            return
        decisions = state.get("decisions") or {}
        acks = state.setdefault(GAP_ACKS, {})
        for a in effective(draft, decisions, self._method()):
            decision = decisions.get(f"{a['id']}.rto")
            if decision is None or not is_gap((a.get("rto_now") or {}).get("value")):
                continue  # he has decided nothing on this RTO, or what he decided is no gap
            ack, on = acks.get(a["id"]) or {}, int(decision.get("seq") or 0)
            by = decision.get("by") or ""
            if ack and not ack.get("closed"):
                ack["on"] = on  # the same gap, still standing: the latest act that carries it
                if by and not ack.get("account"):
                    # fix 2: he acknowledged it with no side to rest it on (his typed gap word),
                    # and a side that carries it has settled since: an EMPTY account takes the
                    # speaker that act resolves. One already resolved stays as it was (I4).
                    ack["account"] = side_speaker(draft, decisions, by)
                continue
            if ack and int(ack.get("on") or 0) >= on:
                continue  # closed, and nothing decided on the RTO since
            acks[a["id"]] = {"at": time.strftime("%H:%M:%S"), "seq": int(state.get("seq") or 0),
                             "on": on, "by": by,
                             "account": side_speaker(draft, decisions, by) if by else ""}

    @holds_the_room
    def decide(
        self,
        activity: str,
        item_id: str,
        decision: str,
        side: int | None = None,
        value: str | None = None,
        scores: dict[str, Any] | None = None,
        note: str | None = None,
    ) -> Any:
        state = load_state(self.folder, activity)
        draft = state.get("draft") or {"activities": []}

        def figures_now() -> dict[str, Any]:
            return {a["id"]: {"mtpd": (a.get("mtpd_now") or {}).get("value"),
                              "rto": (a.get("rto_now") or {}).get("value"),
                              "mtpd_the_impact_scores_give": a["derived_now"]}
                    for a in effective(draft, state.get("decisions", {}), self._method())} \
                if draft.get("activities") else {}

        if item_id.endswith(f".{referee.ASSERTED_MTPD}"):
            return self._answer_question(activity, item_id, decision)
        kind = item_id.rsplit(".", 1)[-1] if "." in item_id else ""
        # t80/t83/t93, the owner's rule of 2026-09-20 ("Gate it - AI proposes, you act"): the acts
        # that land on the record he signs are refused HERE, before `_apply` writes anything,
        # and each becomes a tap of his. The gate is at the function that writes, not at the tool
        # list: a later tool, a helper or a retry reaching `decide` inside a model turn meets it
        # too.
        if decision == "change" and value is not None and kind in ("mtpd", "rto", "rpo") \
                and not self._figure_word(kind, str(value)):
            # t71 fix 3: nemo's own tool input, checked in one place for every caller (the model's
            # call and his typed route alike); his typed route asks him again before it gets here.
            # fix 1 (the review's minor 4): the form check comes FIRST, so a string that is no
            # figure is a wrong call and never a tap label nemo drew and he can press.
            return wrong_call(
                f"{item_id}: {value!r} is not an {kind.upper()}: {self._figure_says(kind)}"
            )
        if self._model_turn and (gated := self._his_act(activity, item_id, decision, kind, value,
                                                        side, state, scores)):
            # fix 3: the one line the model reads; the manager sees `say` and the taps. fix 4: the
            # item it was drawn for, so each tap is drawn from that item's slot and no other
            return {**gated, "told": PROPOSED_TOLD, "item_id": item_id} \
                if gated.get("refusal") == STANDING else gated
        before = figures_now()
        # t93: handing a figure to the derivation replaces his decision on that item, so his own
        # figure is kept underneath it (`over`, as t71 keeps one a side wrote over) and the record
        # says he set it and chose the register's over it. A decision of his never vanishes.
        over = (state.get("decisions") or {}).get(item_id) if decision == DERIVED else None
        # t71b: the note is never his reason: it goes to the run file's log, marked as whose it was
        error = self._apply(state, item_id, decision, side, value, scores, None)
        if error:
            return error
        if over:
            state["decisions"][item_id]["over"] = over
        # why: typeshed's getattr overloads; the default is a str, as `turn_id` is
        if not self._model_turn and getattr(self, "turn_id", ""):  # type: ignore[arg-type]
            # t171: every act of his names the turn he took it on, whose line holds his words
            # (typed, or the tap he was shown): the one thing his evidence row rests on
            state["decisions"][item_id][TURN_ID] = self.turn_id
        if self._model_turn:
            state["decisions"][item_id]["model"] = True  # the value is the model's, not typed
        elif value is not None and self._typing is not None and str(value) == self._typing.strip():
            # fix 1 (M1): his typed line after a "Change …" tap, already logged as he typed it;
            # a tap's own value (the gap) or a direct call's is never logged as his
            state["decisions"][item_id]["typed"] = True
        elif (p := self._chat_figure) and p["item_id"] == item_id and str(value) == p["value"]:
            # t80: the figure was named in chat, nemo refused to record it, and he has now taken
            # the tap nemo drew for it. The act is his; the record says whose figure it was.
            state["decisions"][item_id]["confirmed"] = True
            self._chat_figure = None
        if (c := self._chat_proposal) and c["item_id"] == item_id:
            self._chat_proposal = None  # he took it; the refusal nemo drew for it is spent
        save_state(self.folder, activity, state)
        if note and str(note).strip():
            self._log_note(activity, item_id, str(note))
        after = figures_now()
        return {
            "recorded": item_id,
            "figures_before": before,
            "figures_now": after,
            "figure_moved": before != after,
            "record_will_carry": self._record_to_be(state, self._method())
            if draft.get("activities")
            else {},
            "say_it": "nemo redraws the grid when a figure moved; do not restate figures: ask "
            "about the card nemo_taps_about names",
            "still_open": len(open_items(state)),
            "must_see_left": len(self.must_see(state)),
            "nemo_taps_about": self._taps_about(activity),
        }

    def _his_act(self, activity: str, item_id: str, decision: str, kind: str,
                 value: str | None, side: int | None = None,
                 state: dict[str, Any] | None = None,
                 scores: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Every `decide` on a model turn, as nemo's standing refusal carrying it back to him as a
        tap — or None only for an item that does not exist (a wrong call, which writes nothing).

        The owner's rule (AskUserQuestion, 2026-09-20T21:09:58Z): "Gate it - AI proposes, you act":
        *"The AI can propose anything but cannot itself record a decision that lands on your signed
        record. Where it would, nemo turns it into a tap for you."* Fix 3 applies it as written
        (8_nemo_check, 2026-09-21): **no** decide on a model turn writes, whatever the word and
        whatever the item. Three shapes of tap, all his:

        - **a figure named in chat** (t80, his ruling of 11:28:01Z: "Refuse, ask me to confirm"):
          "Record … " and his "Change …" tap beside it, so his typed route (t71) is untouched.
        - **leaving a conflict open** (t83): t76's own tap, whatever stray `side` came with it.
        - **everything else** (`_proposal`): the one tap his card draws for that call, so a side,
          an accept, a reject, a score row or a hand-over to the register (t93) comes back to him
          under its card label, which names what the record would carry.

        Nothing here reads a word the model wrote: the gate is `self._model_turn`, which nemo sets
        around `_model_calls` and clears in the same `finally`, and which is in no model JSON.
        Each refusal is `hold=False`: what it waits on is his own call of this very tool.
        """
        a = self._room_name(activity)
        if decision == "change" and value is not None and kind in ("mtpd", "rto", "rpo"):
            confirm = confirm_figure_tap(kind, value)
            self._chat_figure = {"activity": a, "item_id": item_id, "kind": kind,
                                 "value": str(value), "confirm": confirm}
            return standing(
                CHAT_FIGURE_SAYS.format(kind=kind.upper(), value=value, activity=a, confirm=confirm,
                                        change=change_figure_tap(kind)),
                [confirm, change_figure_tap(kind)], "figure_set_by_him", hold=False)
        # fix 3 (83's Minor, review 3): leaving it open is what the model proposed, so the
        # referral is what he is offered, whatever stray `side` came with the call.
        if decision == UNRESOLVED:
            self._chat_referral = {"activity": a, "item_id": item_id}
            return standing(CHAT_REFERRAL_SAYS.format(tap=UNRESOLVED_TAP), [UNRESOLVED_TAP],
                            "referral_made_by_him", hold=False)
        # fix 3 (8_nemo_check's ruling of 2026-09-21): every other decide is refused too, so the
        # gate is TOTAL and needs no predicate. Fix 2's `_writes_beyond` dry run asked `_apply`
        # what a call would write beyond the item it named, and review 3 walked through the item
        # it did name: `accept` on an MTPD he typed restored nemo's 8 h, `reject` deleted it,
        # `accept` on his RPO handed it to the register. Three rounds, three holes, one shape:
        # a list of what the model may not write. There is no list left.
        return self._proposal(a, item_id, decision, side, value, scores, state)

    def _proposal(self, a: str, item_id: str, decision: str, side: int | None,
                  value: str | None, scores: dict[str, Any] | None,
                  state: dict[str, Any] | None) -> dict[str, Any] | None:
        """fix 3: a model's `decide` as nemo's standing refusal carrying the proposal back to him as
        a tap. The tap is the one call his card would draw for it, with its card label, which names
        what the record would carry (t73b, `_item_taps`): so the words are drawn from data and a tap
        of his records exactly what it says. None only for an item that does not exist, which
        `_apply` then answers with a wrong call before it writes anything."""
        draft = (state or {}).get("draft") or {"activities": []}
        item = known_items(draft).get(item_id)
        if item is None:
            return None
        call = {"activity": a, "item_id": item_id}
        kind = item_id.rsplit(".", 1)[-1]
        what, taps, says = None, {}, PROPOSED_SAYS
        if item["type"] == "conflict":
            # why: `state` is set here: its draft held the item
            entries = self._side_entries(a, item, state)  # type: ignore[arg-type]
            taps = {e["label"]: tool_tap("decide", **call, decision="accept", side=e["side"])
                    for e in entries}
            n = (
                side
                if isinstance(side, int)
                else item.get("recommend")
                if decision == "accept"
                else None
            )
            pick = next((e for e in entries if e["side"] == n), None)
            if pick is not None:
                what, says = pick["label"], PROPOSED_SIDE_SAYS  # the card beside it says its effect
            else:
                taps[UNRESOLVED_TAP] = tool_tap("decide", **call, decision=UNRESOLVED)
                # fix 4 (ruling 4): named by its subject in the draft, up to its first colon
                what, says = (
                    str(item.get("about") or item_id).split(":")[0].strip(),
                    PROPOSED_CONFLICT_SAYS,
                )
        else:
            aid = item_id.split(".")[0]
            act: dict[str, Any] = next((x for x in draft["activities"] if x["id"] == aid), {})
            if kind in ("mtpd", "rto", "rpo"):  # a stated figure is drawn as his card draws one
                item = {**item, "type": kind.upper(),
                        "value": item.get("value") or (act.get(kind) or {}).get("value")}
            elif item["type"] == "figure":      # and so is a stated score row
                item = {**item, "type": "score", "lens": kind,
                        "scores": ((act.get("grid") or {}).get(kind) or {}).get("scores") or {}}
            # why: `state` is set here: its draft held the item
            own = self._item_taps(a, item, state)  # type: ignore[arg-type]
            name = kind.upper() if kind in ("mtpd", "rto", "rpo") else self._category(kind)
            if decision == DERIVED and kind in ("mtpd", "rto", "rpo"):
                # why: `state` is set here: its draft held the item
                carried = (self._carried_after(state, aid, item_id, decision=DERIVED)[0]  # type: ignore[arg-type]
                           .get(kind.upper()) or {}).get("value")
                label = derived_figure_tap(kind, carried)
                taps, what = {label: tool_tap("decide", **call, decision=DERIVED)}, \
                    f"{kind.upper()} {carried}, from the register"
            elif decision == "reject" and kind in ("mtpd", "rto", "rpo"):
                label = f"No {name} on the record"
                taps, what = {label: tool_tap("decide", **call, decision="reject")}, \
                    f"no {name} on the record"
            elif decision == "change" and item["type"] == "score" and isinstance(scores, dict) \
                    and scores and set(scores) <= set(item.get("scores") or {}) \
                    and all(isinstance(v, int) and 1 <= v <= 5 for v in scores.values()):
                shown = " · ".join(str(v) for v in scores.values())
                label = f"Use {name} scores ({shown})"
                taps, what = (
                    {label: tool_tap("decide", **call, decision="change", scores=scores)},
                    f"{name} scores {shown}",
                )
            elif decision not in ("change", "reject", DERIVED) and own:
                # `effective` reads every word but these as taking the proposal, so that is the tap
                label, tap = own[0]
                taps = {label: {k: v for k, v in tap.items() if k != "names"}}
                what = (
                    label[len("Accept ") :]
                    if label.startswith("Accept ")
                    else label[0].lower() + label[1:]
                )
            else:
                taps = {label: tap for label, tap in own}
        his = (
            (explicit_change(((state or {}).get("decisions") or {}).get(item_id)) or {}).get(
                "value"
            )
            if kind in ("mtpd", "rto", "rpo") and item["type"] != "conflict"
            else None
        )
        if his and decision == "reject":      # fix 4 (ruling 4): say what happens to HIS figure
            says, what = PROPOSED_REMOVE_HIS_SAYS, what and kind.upper()
        elif his and what and says == PROPOSED_SAYS and decision != DERIVED:
            says = PROPOSED_OVER_HIS_SAYS
        self._chat_proposal = {"activity": a, "item_id": item_id, "taps": taps}
        say = says.format(what=what, about=what, name=what, his=his) if what else PROPOSED_ANY_SAYS
        return standing(say, list(taps), "decided_by_him", hold=False)

    def _log_note(self, activity: str, item_id: str, note: str) -> None:
        """t71b: a note a `decide` call supplied, kept for the audit trail in the run file and
        marked as the model's (or a direct call's). No view reads this key: it is never signed."""
        path = walk.run_file(self._room_name(activity))
        with room_lock(self.folder):  # 241: read, change and save as one, at the run's revision
            run = walk.read_record(self.folder, path)  # type: ignore[attr-defined]  # walk re-exports read_record
            if not run:
                self.log("model_note", {"activity": activity, "item": item_id, "note": note})
                return
            run.setdefault(MODEL_NOTES, []).append({
                "item": item_id, "note": note, "by": BY_MODEL if self._model_turn else BY_CALL,
                "at": time.strftime("%H:%M:%S")})
            write_record(self.folder, path, run, run["revision"])

    @holds_the_room
    def close_recovery_gap(self, activity: str, item_id: str, said: str) -> Any:
        """t76, the owner's ruling (2026-09-19): a recovery gap he acknowledged stays until he
        records, in his own words, that the arrangements can now meet the target. This is that
        record: his line, word for word, and the gap closes on it and on nothing else.

        The model may not call it. Its words would be the model's account of his, which is the
        whole of M14; his own line reaches it through the tap's awaiting route, as a reservation's
        words do (t71), and the model is refused here exactly as it is refused there.
        """
        if self._model_turn:
            return standing(
                # fix 2 (review 2's routing ruling, on the artefact): `_refusal_turn` sets
                # `text = refused["say"]` and RETURNS it as the turn's text, so there is no
                # model-only channel — this prints on HIS screen as nemo's own message. The
                # third person ("Ask him whether…") addressed the model in words only he reads.
                # The four t80/t83/t93/t94 refusals are second person; this one now matches them.
                "nemo closes a recovery gap only in your own words: the next line you type under "
                f"nemo's “{GAP_CLOSE_TAP}” tap is it, word for word. Nothing has changed on the "
                "record.",
                [], "gap_closed_typed")
        if (waiting := self._gap_close_waits(activity)):
            return waiting
        state = load_state(self.folder, activity)
        aid = str(item_id).split(".")[0]
        if not (state.get("draft") or {}).get("activities"):
            return wrong_call(f"no draft for {self._room_name(activity)}")
        if not gap_stands(state, aid):
            return wrong_call(f"no acknowledged recovery gap on {item_id}: nothing to close",
                              gaps_standing=[f"{x['id']}.rto" for x in state["draft"]["activities"]
                                             if gap_stands(state, x["id"])])
        if not str(said).strip():
            return wrong_call("the words are the manager's own, and none were typed")
        state["seq"] = int(state.get("seq") or 0) + 1
        state.setdefault(GAP_ACKS, {}).setdefault(aid, {})["closed"] = {
            "words": str(said).strip(), "at": time.strftime("%H:%M:%S"), "seq": state["seq"]}
        save_state(self.folder, activity, state)
        log_said(self.folder, str(said).strip(), "tool")  # t71b: his own line, held as his
        return {"recovery_gap_closed": item_id, "in_his_words": str(said).strip(),
                "say_it": "the gap is closed, in his words; do not reword them",
                "record_will_carry": self._record_to_be(state, self._method())}

    def _gap_close_waits(self, activity: str) -> dict[str, Any] | None:
        """t76, the check session's (a), reshaped by fix 2: what stops him recording the words that
        close a gap now, as nemo's standing refusal — or None, where nothing does.

        One source for two readers: `close_recovery_gap` refuses on it and `_gap_close_taps` draws
        no tap where it does, so nemo never offers a move it will refuse (ticket 67). At step 4 the
        record is written again from his decisions, so the words land there even with an older
        record on file, and nothing is refused; past it they would change nothing on file and
        report that they had. A signed BIA is final, and the reopen that would mend it is refused
        too, so that refusal names the moves that are left instead of a route that is not.
        """
        c = walk.current(self.folder, activity)
        if (c.saved or {}).get("status") == walk.CLOSED:
            return standing(
                f"The BIA for {self._room_name(activity)} is signed, and a signed BIA is "
                "final: nothing in this walk records words against its recovery gap now.",
                AFTER_SIGNING,
                "run_not_closed",
            )
        if self._has_record(activity) and c.stage >= walk.STAGE_5:
            return standing(
                f"The BIA for {self._room_name(activity)} is written, so the words that "
                "close its recovery gap belong at step 3: go back there and record them.",
                [GO_BACK],
                "record_changes",
            )
        return None

    # t116: the referee's open question, and his three answers to it ─────────────────────────────
    def _question(self, activity: str) -> tuple[str, referee.Question] | None:
        """The first question the referee asks of the record step 3 would close on, and the state
        key his answer goes under; None while a proposal is open (they come first) or none is.

        Asked through `walk.open_questions` over the stage-3 card, the one check nemo's own step 3
        refuses on, so the refusal here and there cannot disagree."""
        state = load_state(self.folder, activity)
        draft = state.get("draft") or {}
        if not draft.get("activities") or open_items(state):
            return None
        questions = walk.open_questions(self.folder, _patched_evidence_card(self.folder, activity))
        ids = {a["name"]: a["id"] for a in draft["activities"]}
        for q in questions:
            aid = ids.get(q.activity) or (q.activity if q.activity in ids.values() else None)
            if aid is not None:
                return question_key(aid), q
        return None

    def _question_taps(self, a: str, asked: tuple[str, referee.Question] | None = None
                       ) -> list[tuple[str, dict[str, Any]]]:
        """t116: the open question's three taps, each `decide` on its id; none when none is open."""
        asked = asked or self._question(a)
        if asked is None:
            return []
        iid, q = asked
        return [(KEEP_ASSERTED_TAP.format(asserted=q.asserted),
                 tool_tap("decide", activity=a, item_id=iid, decision=referee.KEEP)),
                (WITHDRAW_ASSERTED_TAP.format(derived=q.derived),
                 tool_tap("decide", activity=a, item_id=iid, decision=DERIVED)),
                (LEAVE_OPEN_TAP, tool_tap("decide", activity=a, item_id=iid, decision=UNRESOLVED))]

    def _question_says(self, a: str, asked: tuple[str, referee.Question]) -> str:
        q = asked[1]
        return QUESTION_SAYS.format(
            activity=self._room_name(a), asserted=q.asserted, derived=q.derived
        )

    @holds_the_room
    def _typed_reason_answers(self, a: str, item_id: str, reason: str | None) -> None:
        """t116 (a), 14_nemo_check's ruling: his MTPD typed under "Change MTPD", and the reason he
        gave for it when t64 asked, ARE his Keep of the grid question that figure opened. It is
        recorded as such, so nothing asks him the same thing twice. His Skip is a Keep with no
        reason (14_nemo_check, overruling the build: a decline is a pass). Only for that figure:
        a question on another, or none, is left as it is."""
        asked = self._question(a)
        if asked is None or not item_id.endswith(".mtpd") \
                or asked[0] != question_key(item_id.rsplit(".", 1)[0]):
            return
        q = asked[1]
        state = load_state(self.folder, a)
        state["seq"] = int(state.get("seq") or 0) + 1
        state.setdefault("decisions", {})[asked[0]] = {
            "decision": referee.KEEP, "asserted": q.asserted, "derived": q.derived,
            "value": q.asserted, **({"reason": reason} if reason else {}),
            "by_reason": reason is not None, "typed_item": item_id,
            "at": time.strftime("%H:%M:%S"), "seq": state["seq"]}
        (state.get(REOPENED) or {}).get("touched", []).append(asked[0])
        save_state(self.folder, a, state)

    @holds_the_room
    def _answer_question(self, activity: str, item_id: str, decision: str) -> Any:
        """t116: his answer to the open question, stored under its id with the two figures it
        answered (amendment 1: once either moves, the referee asks again). On a model turn it
        writes nothing and becomes his tap, as every `decide` does (t80's rule, fix 3)."""
        asked = self._question(activity)
        if asked is None or asked[0] != item_id:
            return wrong_call(f"no open question {item_id!r}",
                              open_question=asked[0] if asked else None)
        if decision not in (referee.KEEP, DERIVED, UNRESOLVED):
            return wrong_call(f"{item_id}: answer {referee.KEEP} | {DERIVED} | {UNRESOLVED}")
        if self._model_turn:
            return {**standing(self._question_says(activity, asked),
                               [label for label, _ in self._question_taps(activity, asked)],
                               "question_answered", hold=False),
                    "told": PROPOSED_TOLD, "item_id": item_id}
        q = asked[1]
        state = load_state(self.folder, activity)
        state["seq"] = int(state.get("seq") or 0) + 1
        state.setdefault("decisions", {})[item_id] = {
            "decision": decision, "asserted": q.asserted, "derived": q.derived, "value": q.asserted,
            "at": time.strftime("%H:%M:%S"), "seq": state["seq"],
            # t171 on 116: the turn of his tap, which a withdrawn MTPD's evidence row rests on
            **({TURN_ID: self.turn_id} if getattr(self, "turn_id", "") else {})}
        (state.get(REOPENED) or {}).get("touched", []).append(item_id)
        save_state(self.folder, activity, state)
        return {
            "recorded": item_id,
            "answer": decision,
            "asserted": q.asserted,
            "derived": q.derived,
            "record_will_carry": self._record_to_be(state, self._method()),
            "still_open": len(open_items(state)),
        }

    def must_see(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """The open items a reviewer may not wave through: the ones that set a clock.

        Every conflict, and every proposed MTPD, RTO or RPO. A category score can go through with
        the rest; the figure the whole BIA turns on cannot (the reviewer, the BCM-user seat, 2026-09-17).
        """
        return [i for i in open_items(state) if i["type"] in ("conflict", "MTPD", "RTO", "RPO")]

    @holds_the_room
    def accept_all_open(self, activity: str) -> Any:
        """t94, the owner's ruling of 2026-09-21: **"only your tap may accept all."** The model may
        propose it — "shall I accept the rest?" — and the acceptance itself is his.

        Gated, not left unreachable. The first round argued this call "stops being reachable
        anyway" because `must_see` holds the conflicts open; review 2 then walked
        `decide(reject, side=1)` straight through `must_see` to `APPLIED, still_open 0`.
        **Unreachable is a property of one seed's shape; gated is a property of the code.** So the
        refusal is here, at the function that writes, and it stands whether or not anything is
        open. `hold=False`: what it waits on is his own tap of this very tool (t76's repair).
        """
        if self._model_turn:
            return standing(ACCEPT_ALL_SAYS.format(tap=ACCEPT_ALL), [ACCEPT_ALL],
                            "accepted_by_him", hold=False)
        state = load_state(self.folder, activity)
        outstanding = self.must_see(state)
        if outstanding:
            return wrong_call(
                "these set the clocks, so the manager settles them one at a time first",
                show_these_first=[_reason_attributed(i) for i in outstanding[:4]],
                then="call accept_all_open again for whatever is left",
            )
        for i in open_items(state):
            state["seq"] = int(state.get("seq") or 0) + 1
            state.setdefault("decisions", {})[i["id"]] = {
                "decision": "accept", "side": i.get("recommend"), "at": time.strftime("%H:%M:%S"),
                "note": "accept all remaining", "seq": state["seq"],
                # t171: his "accept all" tap is the act each of these rests on
                **({TURN_ID: self.turn_id} if getattr(self, "turn_id", "") else {})}
            (state.get(REOPENED) or {}).get("touched", []).append(i["id"])
        save_state(self.folder, activity, state)
        return {"still_open": 0, "check": self._dry_run(activity, state, self._method())}

    def _snapshot(self, activity: str) -> Path:
        return self.folder / STATE.format(slug=slug(activity)).replace(".json", ".stage3-run.json")

    def reopen(self, activity: str) -> Any:
        """Back into step 3 after the record was accepted. The signature is what does not undo.

        The owner ruled 2026-09-17 that the point of no return is the signature, not step 4: a
        manager reading the handover who spots a wrong figure can fix it and come forward again.
        nemo's `walk.reopen` puts the run back as it stood at the close of step 3 (241); this says
        why when it cannot. The manager's step-3 decisions are untouched, so nothing is
        re-litigated.
        """
        c = walk.current(self.folder, activity)
        run = c.saved or {}
        if (waiting := self._naming_waits(c)):
            return waiting
        if run.get("status") == walk.CLOSED:
            return standing(
                f"The BIA for {self._room_name(activity)} is signed, and a signed BIA is final: "
                "nothing in "
                "this walk will reopen or change it.",
                AFTER_SIGNING,
                "run_not_closed",
            )
        legacy = self._snapshot(activity)  # a step 3 closed before 241 was kept by the skin
        if legacy.exists() and not (self.folder / walk._at_step_3(activity)).exists():
            write_file(self.folder, walk._at_step_3(activity), legacy.read_text())
        if walk.reopen(self.folder, activity) is None:  # a step-4 tool before step 4: a wrong call
            return wrong_call("nothing to go back to: step 3 has not been closed on this walk yet")
        # t71: the decisions are kept as they stand now, so what nobody touches again can be held
        # to them
        with room_lock(self.folder):  # t238 (C7): read, change and save as one
            state = load_state(self.folder, activity)
            state[REOPENED] = {"decisions": json.loads(json.dumps(state.get("decisions") or {})),
                               "touched": [], "at": time.strftime("%H:%M:%S")}
            save_state(self.folder, activity, state)
        self._carded.discard(f"record:{activity}")
        self._carded.discard(f"sign:{activity}")
        return {
            "reopened": activity,
            "kept": "every decision you made at step 3",
            "say_it": "you are back at step 3; change what is wrong, then accept the record again",
            "now": self.get_step(activity),
        }

    def answer_step(self, activity: str, answer: str) -> Any:
        c = walk.current(self.folder, activity)
        # t71 fix 1: while nemo waits for a reservation's words, the answer IS them, whatever the
        # stage the walk has moved on to (step 1's reservation waits at step 2; step 3's at a step 4
        # the referee may refuse), and none of the stage's own rules applies to it
        naming = walk._last_decision(c.saved or {}).get("naming") == walk.UNNAMED  # type: ignore[attr-defined]  # walk re-exports UNNAMED
        if naming and self._model_turn:
            # the reservation is his words, never the model's copy of them; his next typed line
            # reaches answer_step as it is (`turn`), so the model's naming is refused
            return standing(
                f"nemo keeps the reservation on {self._room_name(activity)} in your own words: "
                "the next line you type is kept as it is, word for word, as what you "
                "are reserving.",
                [],
                "reservation_typed",
            )
        if naming:
            pass
        elif c.stage == walk.STAGE_2:
            return wrong_call("step 2 is confirmed with confirm_interviews")
        elif c.stage == walk.STAGE_3:
            state = load_state(self.folder, activity)
            open_ = open_items(state)
            if open_:
                return wrong_call(f"{len(open_)} proposals are still open",
                                  open_ids=[i["id"] for i in open_][:20])
            if (asked := self._question(activity)):
                # t116 (the owner, TYPED, ce2e8d7b): "a step answer such as "endorsed" can never
                # settle a referee question that is still open". nemo's own step 3 refuses it too
                # (`walk.open_questions`); here the refusal carries the question's own taps, for
                # his tap and a model's call alike
                return {**standing(self._question_says(activity, asked),
                                   [label for label, _ in self._question_taps(activity, asked)],
                                   "question_answered"), "item_id": asked[0]}
            if self._rto_wanted(activity, state):
                # t154: never a record with no RTO, which the referee refuses: his tap states it
                return standing(RTO_WANTED_SAYS.format(activity=self._room_name(activity)),
                                [STATE_RTO], "figure_set_by_him", hold=False)
        if c.stage == walk.STAGE_4 and not c.buttons and not naming:
            return self._referee_refuses(activity, c)
        if self._model_turn and not naming and c.stage == walk.STAGE \
                and not walk._a_question(answer) and walk._gradient(answer) == walk.ENDORSED:
            # t377c G2: the scope is his to agree. Nothing is written; the stage 1 card stands
            # with its own taps, and his "Yes, that's the scope" is the same call
            return {"agreed": False, "step": c.stage,
                    "next": SCOPE_IS_HIS.format(activity=_said_name(self.folder, activity),
                                                tap=walk.AGREE)}
        if self._model_turn and not naming and c.stage in ENDORSE_SAYS \
                and not walk._a_question(answer) and walk._gradient(answer) == walk.ENDORSED:
            # fix 4 (ruling 3): a plain endorsement here closes step 3 or accepts the record, and
            # the card would then say "accepted by you". It becomes his tap: the card's own label,
            # the same call. An answer with a reservation already goes through him (his typed
            # words name it), so it is not gated here.
            return standing(ENDORSE_SAYS[c.stage].format(activity=self._room_name(activity),
                                                         tap=walk.ENDORSED),
                            [walk.ENDORSED], "endorsed_by_him", hold=False)
        before = walk.read_record(self.folder, walk.record_file(activity))  # type: ignore[attr-defined]  # walk re-exports read_record
        if c.stage == walk.STAGE_4 and c.buttons and not naming:
            # t71: the fidelity check, before the record is written
            import PROTOTYPE_fidelity as fidelity
            rec, findings = c.proposal.get(walk.BIA) or {}, c.proposal.get(walk.FINDINGS)  # type: ignore[attr-defined]  # walk re-exports FINDINGS
            problems = fidelity.check(
                self.folder,
                activity,
                rec,
                {**(c.saved or {}), "findings": list(findings or [])},
                {fidelity.CARD: self.record_card_text(activity, rec, findings)},
                said=self._said(),
            )
            if problems:
                return self._unfaithful(activity, "write the record", problems)
        if naming:  # t71b: never the model's (refused above): his typed line, or his tools
            log_said(self.folder, answer, "tool")
        drawn_from = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record; t181
        cards = walk.answer(self.folder, activity, answer, c.revision, picked=None,
                            record_revision=c.record_revision)
        if naming:  # t71: his words are in; the stage-4 card is drawn again with them on it
            self._carded.discard(f"record:{activity}")
            self._keep_reservations(activity)
        try:
            if cards:
                self._documents_with_reservations(activity, drawn_from)
        except walk.NotDrawnYet:  # fix 1: what he typed is saved; the documents cannot follow yet
            # t181: owed with the run the documents on file were drawn from, the first one kept
            with room_lock(self.folder):  # t238 (C7): read, change and save as one
                state = load_state(self.folder, activity)
                if not isinstance(state.get(DOCUMENTS_OWED), dict):
                    save_state(self.folder, activity, {**state, DOCUMENTS_OWED: drawn_from})
            return standing(
                f"nemo kept what you typed on {self._room_name(activity)}, but the picture of "
                "its record is not drawn yet, so the handover can't be written again "
                "with it until it is.",
                [f"Carry on with step {c.stage}"],
                "record_faithful",
            )
        if not cards:
            return {
                "nemo_did": "nothing: nemo read that as a question",
                "now": self.get_step(activity),
            }
        if (
            walk.read_record(self.folder, walk.record_file(activity)) != before  # type: ignore[attr-defined]  # walk re-exports read_record
            and self._has_record(activity)
        ):
            # Ticket 68 item 5: "saved" reaches the manager as the tool's own result, from the file
            # t64b (voice §3.1): where the BIA is, in words; a path is for a Source: line only
            self.cards.append(
                f"**Saved · {self._heading(activity)}**\n\nThe BIA is on file in your "
                "room: accepted by you, not yet signed. It can still change until you sign."
            )
        return {"nemo_said": by_his_tap(cards[-1].body)[:2500], "now": self.get_step(activity)}

    @staticmethod
    def _naming_waits(c: walk.Card) -> dict[str, Any] | None:
        """t71 fix 2: while nemo waits for a reservation's words, no move but his typed line: a
        confirmation would be taken as the words, a signature or a reopen would drop them."""
        last = walk._last_decision(c.saved or {})
        if last.get("naming") != walk.UNNAMED:  # type: ignore[attr-defined]  # walk re-exports UNNAMED
            return None
        return wrong_call(
            f"nemo is waiting for the reservation made on step {last.get('stage')}, in "
            "the manager's own words: his next typed line is it. Nothing else moves "
            "this walk until he has typed it."
        )

    def _not_typed(self, name: str) -> list[str]:
        """The signer's name is one the manager typed in this conversation, before any "on behalf
        of" (t71): held against every sign call the model makes. The tools driven directly (no
        model in between) are not."""
        # the owner a delegate names after "on behalf of" is whom he signs for, not the signer
        if not self._model_turn:
            return []
        if not any(norm_name(name) in norm_name(line).split(ON_BEHALF)[0] for line in self._typed):
            return [f"{name} is not a name the manager typed"]
        # t134: whom a delegate signs for used to be read out of the role string he typed, and
        # held against his own typed lines to keep v1's "on behalf of" the absent owner out. It is
        # his tap now — one of the record's own names, taken by him — so there is no typed phrase
        # left to check and no role string left to read. His name is still his to type.
        return []

    def _said(self) -> list[str]:
        """t71b: what manager-origin text may be: a line he typed (the room's log of them, and this
        conversation's), a text his own tool call carried, or a label nemo drew for him to tap."""
        return [*said_lines(self.folder), *self._typed, *self._tap_labels]

    def _unfaithful(self, activity: str, what: str, problems: list[str]) -> dict[str, Any]:
        """The fidelity check's refusal (t71), in ticket 67's shape: the first mismatch named, and
        the one move that can mend it, back to step 3 where every decision is kept."""
        more = f" ({len(problems) - 1} more like it.)" if len(problems) > 1 else ""
        self.log("unfaithful", {"activity": activity, "what": what, "problems": problems})
        return standing(
            f"nemo won't {what} for {self._room_name(activity)}: what it would carry is "
            f"not what was decided in this walk. {problems[0]}.{more}",
            [GO_BACK],
            "record_faithful",
        )

    @holds_the_room
    def _keep_reservations(self, activity: str) -> None:
        """t71: the state file's ledger of the reservations nemo took, word for word, so a record
        that later loses one (a reopen, a rewrite) is caught by the fidelity check."""
        import PROTOTYPE_fidelity as fidelity
        run = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        state = load_state(self.folder, activity)
        ledger = state.setdefault(RESERVATIONS, [])
        for stage, words in fidelity.reservations(run):
            if not any(r["stage"] == stage and r["naming"] == words for r in ledger):
                ledger.append({"stage": stage, "naming": words, "by": "the manager, as he typed it",
                               "at": time.strftime("%H:%M:%S")})
        save_state(self.folder, activity, state)

    def _documents_reworded(self, activity: str) -> None:
        """t64 fix 1: an accepted, unsigned handover whose file is word for word what the code
        before t64 wrote (the raw shared-quote JSON, the repeated full name) is written again in
        today's words before the signature, so the fidelity check compares like with like. Any
        other difference is still the check's to refuse. A signed run is never touched (its status
        is no longer REVIEWED)."""
        run = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        if run.get("status") != walk.REVIEWED:
            return
        record = walk.move_past_stage_4(self.folder, run)
        now = handover.documents(record, run)
        before = handover.documents(record, run, plainly=False)
        for name, text in now.items():
            path = f"{walk.views.folder(record)}/{name}"  # type: ignore[attr-defined]  # walk re-exports views
            if (self.folder / path).is_file() and text != before[name] \
                    and (self.folder / path).read_text() == before[name]:
                walk.write_document(self.folder, path, text)  # type: ignore[attr-defined]  # walk re-exports write_document
                self.log("reworded", {"activity": activity, "document": path})

    @holds_the_room
    def _documents_quietly(self, activity: str) -> None:
        """The documents nemo owes since a NotDrawnYet refusal, written again on any step move at
        step 5 and before a signature (fix 2). Only those: a handover on file that lost a
        reservation any other way is the fidelity check's to refuse, never to mend quietly."""
        state = load_state(self.folder, activity)
        owed = state.get(DOCUMENTS_OWED)
        if not owed:
            return
        try:  # t181: an owe from before t181 names no run, so nothing on file is proven nemo's
            self._documents_with_reservations(activity, owed if isinstance(owed, dict) else {})
        except walk.NotDrawnYet:
            return
        state.pop(DOCUMENTS_OWED, None)
        save_state(self.folder, activity, state)

    def _documents_with_reservations(self, activity: str, drawn_from: dict[str, Any]) -> None:
        """t71: nemo writes the BIA and the handover when the handover is accepted, before the words
        of a reservation made on that answer are typed. Once the run carries them, the two
        documents are written again from the record and the run, so they carry every reservation.

        t181, the rule it keeps: a document is written again only when the file on disk is exactly
        what nemo last drew for this run, i.e. its drawing from `drawn_from`, the run as it stood
        before this answer (so it already carries the earlier reservations). Any other difference
        is left on disk for the fidelity check to refuse at the signature, never mended quietly.
        Every rewrite logs one line naming the activity and the document."""
        run = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        if run.get("status") != walk.REVIEWED:
            return
        record = walk.move_past_stage_4(self.folder, run)
        last = handover.documents(record, drawn_from)
        for name, text in handover.documents(record, run).items():
            path = f"{walk.views.folder(record)}/{name}"  # type: ignore[attr-defined]  # walk re-exports views
            if (self.folder / path).is_file() and text != last[name] \
                    and (self.folder / path).read_text() == last[name]:
                walk.write_document(self.folder, path, text)  # type: ignore[attr-defined]  # walk re-exports write_document
                self.log("redrawn", {"activity": activity, "document": path})

    def sign(self, activity: str, name: str, role: str, signs_as: str = "") -> Any:
        """t134: who he signs as is his own explicit choice, and `signs_as` is that choice — empty
        until he has made it. Where the record names an owner, nemo asks him with the two taps it
        draws from the record's own names (`walk.signing_choices`) rather than signing on a guess;
        where it names none there is nothing to choose and this signs as it always did."""
        if len(name.strip()) < 3 or name.strip().startswith("("):
            return wrong_call(
                "no name was typed. The signature is the one thing the manager types: "
                "ask them for their own name and role, then call sign again."
            )
        c = walk.current(self.folder, activity)
        status = (c.saved or {}).get("status")
        if (waiting := self._naming_waits(c)):
            return waiting
        if status == walk.CLOSED:
            return standing(
                f"The BIA for {self._room_name(activity)} is already signed, and a signed BIA is "
                "final: "
                "nothing in this walk will sign it again.",
                AFTER_SIGNING,
                "run_not_closed",
            )
        if status != walk.REVIEWED:
            # nemo's walk.sign refuses this too since t239; the prototype says it first, with the
            # way on, before it touches a document.
            return standing(
                f"The handover for {self._room_name(activity)} is not accepted yet, so there is "
                "nothing to "
                "sign: it can be signed once the handover is accepted at step 5.",
                [self._carry_on(c)],
                "handover_accepted",
            )
        self._documents_reworded(activity)  # t64 fix 1: a handover on file from before t64
        self._documents_quietly(activity)
        sc = walk.signature_card(self.folder, activity)
        ids = tuple(sc.proposal.get(walk.ITEMS, {}).keys())
        # t71: the fidelity check, before a byte of the signature lands. The certificate is drawn
        # in memory exactly as nemo will write it, and held to the record with the rest.
        import PROTOTYPE_fidelity as fidelity
        record, run = sc.proposal[walk.BIA], sc.saved or {}
        # his own name first: nemo does not ask him who he signs as for a name he never typed
        if typed := self._not_typed(name):
            return wrong_call(f"{typed[0]}. The signature is the one thing the manager types: ask "
                              "him to type his own name and his role, then call sign again with "
                              "what he typed.")
        # t134: the one thing only he can say. nemo refuses the signature until he has, and offers
        # the two taps it drew from the record's own names — never held (`hold=False`), because
        # what it waits on is his own tap through this same tool (t80/t83's shape).
        choices = walk.signing_choices(record)
        if choices and not signs_as:
            self._chat_signature = {"activity": activity, "taps": {
                label: tool_tap("sign", activity=activity, name=name, role=role, signs_as=chose)
                for label, chose in choices}}
            return standing(SIGN_AS_WHICH.format(owner=listed(handover.owners(record))),
                            [label for label, _ in choices], "signed_as_by_him", hold=False)
        try:
            on_behalf_of = "" if signs_as == walk.AS_THE_OWNER else signs_as
            signature = {"name": name, "role": role, "accepted": list(ids),
                         "capacity": handover.capacity(record, name, on_behalf_of or None)}
        except handover.NotAnOwner:
            return wrong_call(f"{signs_as} is not a name this record holds as the owner, so nobody "
                              "can sign on their behalf. Who he signs as is his own choice: show "
                              "him the taps nemo drew and let him take one.")
        wrong = fidelity.signer_named(record, signature, None)
        if wrong:
            return wrong_call(
                f"{wrong[0]}. The signature is the one thing the manager types: ask him "
                "to type his own name, his role and whom he signs for, then call sign "
                "again with what he typed."
            )
        on_file = self.folder / walk.views.folder(record) / handover.HANDOVER  # type: ignore[attr-defined]  # walk re-exports views
        views = {
            fidelity.CARD: self.record_card_text(activity, record, run.get("findings")),
            fidelity.HANDOVER: on_file.read_text() if on_file.is_file() else "",
            fidelity.CERTIFICATE: handover.certificate(record, {**run, "signature": signature}),
        }
        problems = fidelity.check(self.folder, activity, record, run, views, signature,
                                  said=self._said())
        if problems:
            return self._unfaithful(activity, "take the signature", problems)
        done = walk.sign(self.folder, sc, name, role, on_behalf_of)  # t239: it accepts sc's ids
        run = done.saved or {}
        closed = run.get("status") == walk.CLOSED
        if closed:
            certs = sorted(self.folder.rglob(handover.CERTIFICATE), key=lambda p: p.stat().st_mtime)
            try:  # v1's graph, redrawn from the record that was just saved
                import PROTOTYPE_v1graph
                PROTOTYPE_v1graph.draw(self.folder, at=walk.record_file(activity))
            except Exception as e:  # a picture that fails to draw never blocks a signature
                self.log("graph_error", str(e))
            if certs:
                self.cards.append("**Certificate**\n\n" + certs[-1].read_text()[:3000]
                                  + f"\n\n[Dependency graph, redrawn from this record]"
                                  f"({self.page_link(LIVE_GRAPH)})")
        return {"nemo_said": done.body, "status": run.get("status"), "certificate_written": closed,
                "owner_nemo_expects": list(handover.owners(sc.proposal[walk.BIA]))}

    def page_link(self, page: str) -> str:
        """t298: a page of the room's workspace, from the serving app's own root (the phone at
        `/`, the public `/chat`), never a host. t277: on the room's code, as the rail links it:
        the folder is `<code>-<model>` (`_session`), and the tailnet proxy's stamp names the code
        alone, so the folder's name answered 404 there."""
        return f"{self.root}/w/{self.folder.name.removesuffix(f'-{self.model}')}/{page}"

    def view_link(self, view: str, ids: list[str]) -> str:
        """t524: the room's live graph page opened on a view (`CHAIN_VIEW`, `SHARE_VIEW`,
        `CUT_VIEW`) of these ids: one link shape for the dependency answer, 485's and 488's."""
        return self.page_link(f"{LIVE_GRAPH}{view}{','.join(ids)}")

    def _recorded_lane(self) -> Callable[[str], str]:
        """The ask lane, with the one model call it makes kept for this room's turn file (t220).

        ADR-0023 says the turn file holds every model call, and this one was in none of them:
        `nemo.lane.call_lane` never goes through `lanes.chat`, which is where a call is added to
        `lanes.CALLS`. The lane is not rerouted — its model, its 80 s and its one try are
        ADR-0036's — so the call is recorded around it, through the `post` `call_lane` already
        takes: what was sent, the raw reply (or the error), and the seconds, in the shape
        `lanes.chat` writes. `purpose` is "guidance" and `lane` is "ask", nemo's own lane, where a
        room's call names its model key.
        """
        def lane(prompt: str) -> str:
            sent: list[Any] = []
            answered: list[Any] = []
            start = time.time()
            failed: str | None = None

            def post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
                sent.append(payload["messages"])
                reply: dict[str, Any] = nemo_lane.post(url, payload)
                answered.append(reply)
                return reply

            try:
                return call_lane(prompt, post=post)
            except Exception as e:
                failed = f"{type(e).__name__}: {e}"
                raise
            finally:
                reply = answered[0] if answered else None
                lanes.CALLS.add(self.folder, turn_file.call(
                    lane="ask", asked=nemo_lane.MODEL, answered=(reply or {}).get("model"),
                    messages=sent[0] if sent else None, tools=None, reply=reply,
                    usage=(reply or {}).get("usage") or {}, seconds=round(time.time() - start, 2),
                    start=start, purpose="guidance", thread=threading.current_thread().name,
                    attempts=[], error=failed))
        return lane

    def ask_guidance(self, question: str) -> Any:
        """The ask lane's answer, printed by the skin as served (t65): its text and its citations
        as the ai4bcm chat numbers them. Each citation is the chunk the connector served for it
        (title, unit, url and release are the connector's own, and its source is nemo's reading of
        that unit); one naming no chunk fetched here is refused."""
        fetched: dict[str, dict[str, Any]] = {}

        def guidance(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
            result = call_guidance(tool, arguments)
            if tool == "fetch" and isinstance(result, dict) and result.get("url"):
                fetched[str(result["url"])] = result
            return result

        # ticket 182: past his 15 s the room says once that the question is still being worked
        # on, then the answer comes as today. The timer is cancelled whatever the lane does, so a
        # fast answer, the 80 s UNAVAILABLE and the capped key's 402 all read exactly as before.
        # The timer's action runs in a bare thread, which in 3.12 starts with an empty context. The
        # phone's `say_now` sends through chainlit, whose first act is a lookup of its own
        # ContextVar,
        # so without this copy the line raises LookupError into the thread and never reaches the
        # room.
        asking = contextvars.copy_context()
        waited = threading.Timer(STILL_WORKING_AFTER_SECONDS,
                                 lambda: asking.run(self.say_now, STILL_WORKING))
        waited.start()
        try:
            answer = ask(question, guidance=guidance, lane=self._recorded_lane())
        finally:
            waited.cancel()
        cited = []
        for c in answer.citations:
            chunk = fetched.get(c.url)
            if chunk is None:
                self.log(
                    "citation_refused", {"url": c.url, "why": "no chunk with this url was fetched"}
                )
                continue
            meta = chunk.get("metadata") or {}
            unit = str(meta.get("unit") or "")
            cited.append({"id": str(chunk.get("id")),
                          "title": str(chunk.get("title") or "").split(TITLE_SEPARATOR)[-1],
                          "unit": unit,
                          "url": str(chunk["url"]),
                          "source": source_of(unit),
                          "release": str(meta.get("release_tag") or "")})
        self._guidance_text = guidance_block(answer.text, cited)
        return {"shown": self._guidance_text, "citations": cited, "say_it": GUIDANCE_SAY_IT}

    def list_room_files(self) -> Any:
        files = room_files(self.folder)
        self._files_seen = set(files)  # t249: the set as last served
        return {
            "files": files,
            "interviews": self._interviews_said(),
        }  # t106: who, when, about, and the count

    def _files_note(self) -> str | None:
        """t249: what changed in the room's files since nemo last served them, as one note of
        data; None when nothing did, or on the first model-bound turn, which takes the set
        silently. The model is never the one who must remember to look (M13). t318: and the
        register's rows added in chat that nemo has not told it of yet, first turn included."""
        notes = [n for n in (self._changed_files(), self._chat_rows_note()) if n]
        return " ".join(notes) or None

    def _chat_rows_note(self) -> str | None:
        """t318: the register's rows added in chat since nemo last said them, as one note of data
        (the register can be longer than a file read shows)."""
        register = drafting.read_register(self.folder)
        rows = [f"{a.get('name')} for {c.get('activity')} ({c[walk.ADDED_IN_CHAT]})"
                for a in register.values() if isinstance(a, dict)
                for c in a.get("consumers") or [] if c.get(walk.ADDED_IN_CHAT)]
        rows += [f"{a.get('name')} {how} {said}" for a in register.values()
                 if isinstance(a, dict) and a.get(walk.ADDED_IN_CHAT)
                 for how, said in [*(("stands on", (register.get(d) or {}).get("name", d))
                                     for d in a.get("depends_on") or []),
                                   *([("at", a["site"])] if a.get("site") else [])]]
        new, self._rows_told = [r for r in rows if r not in self._rows_told], set(rows)
        return ("(nemo: in this room's dependency register, added in chat, with no owner and no "
                f"recovery target yet: {'; '.join(new)})") if new else None

    def _changed_files(self) -> str | None:
        now, seen = set(room_files(self.folder)), self._files_seen
        self._files_seen = now
        if seen is None or now == seen:
            return None
        held = {h["path"]: h for h in self._interviews_said()["held"]}
        added = [held.get(p, {"path": p}) for p in sorted(now - seen)]
        removed = sorted(seen - now)
        return ("(nemo: the room's files changed since nemo last listed them: "
                + "; ".join([*([f"added {json.dumps(added, ensure_ascii=False)}"] if added else []),
                             *([f"removed {json.dumps(removed, ensure_ascii=False)}"]
                               if removed else [])])
                + ")")

    def propose_referral(self, resource: str, item: str) -> Any:
        """t256: the model's proposal, checked by `referral`; accepted, nemo draws his tap. t276
        (ADR-0045): two per answer; a third in the same turn, or one already proposed, is refused
        and draws nothing."""
        if len(self._referrals) >= EACH_KIND:
            return wrong_call("two referrals are proposed per answer, and this one has them")
        target = referral(self.folder, self._turn_read, resource, item, free=not self.walking)
        if "refusal" in target:
            return target
        label = refer_tap(self.folder, target, item)
        if any(label == drawn for drawn, _ in self._referrals):
            return wrong_call("this referral is proposed already in this answer")
        self._referrals.append((label, target))
        return {"proposed": label, "nemo_says": "nemo draws him the tap; he says "
                "what the owner should look at, and nemo writes it. Do not write the referral "
                "yourself."}

    def propose_dependency(self, resource: str, activity: str) -> Any:
        """t318 (ADR-0047): the model's proposal, a name and an activity, checked here; accepted,
        nemo draws his one tap. It writes nothing. One per answer, in free chat and in a walk (t360:
        his workshop adds one at stage 4); an activity the room does not hold is refused, and so is
        any other key (argument binding). The map links his tap opens are code's: the items THIS
        turn's typed line names (`on_the_map`), only for a resource the register did not hold
        before, checked by `map_links` (round 2)."""
        if self._additions:
            return wrong_call("one dependency is proposed per answer, and this one has it")
        name = str(resource).strip()
        if not name:
            return wrong_call("no resource was named: pass his own name for it")
        slug_ = activity_named(self.folder, str(activity))
        if slug_ is None:
            return wrong_call(f"no activity named {activity!r} in this room", activities=[
                map_name(self.folder, a) for a in walk.processes(self.folder)])
        held = next((a for a in drafting.read_register(self.folder).values()
                     if isinstance(a, dict) and _one_name(str(a.get("name") or "")) == _one_name(
                         name)), None)
        named = [] if held is not None and not held.get(walk.ADDED_IN_CHAT) else on_the_map(
            self.folder, self._turn_line, name)
        if held is None:  # t377 (E): a discrepancy's subject, the site its source line names
            named += [s for s in discrepancy_sites(self.folder, slug_, name) if s not in named]
        links = map_links(self.folder, named)
        links = [] if isinstance(links, str) else links
        label = ADD_TAP.format(resource=name, activity=_said_name(self.folder, slug_))
        self._additions.append((label, {"kind": "add", "resource": name, "activity": slug_,
                                        "links": links}))
        return {"proposed": label, "nemo_says": "nemo draws him the tap; his tap adds it to this "
                "room, with no figure and no owner. Do not say it is added."}

    def _typed_addition(self, line: str, name: str | None) -> None:
        """t417: his typed line asks to add a resource (`name`, as read) the register does not hold
        for the room's activity (t395's `_room_activity`): code draws the add tap itself, by the
        model's own call (`propose_dependency`), so it is the same tap. Where the model proposed
        one this answer, that tap stands and code draws none: one tap, never two."""
        on = self._room_activity(line) if name else None
        if self._additions or name is None or on is None:
            return
        held = any(_one_name(str(a.get("name") or "")) == _one_name(name)
                   and any(c.get("department") == on for c in a.get("consumers") or [])
                   for a in drafting.read_register(self.folder).values() if isinstance(a, dict))
        if not held:
            self.propose_dependency(name, on)

    def _led_add_asked(self, line: str) -> bool:
        """t703: his line names one activity and asks to add a resource it does not hold, so
        `_typed_addition` has drawn the tap. Anything else stays the led turn's: no activity of
        his or two of them (the thread is never code's pick here), 493's question on a name that
        fits two things, and any line that is not one such ask (`one_add_named`)."""
        import line_reads  # it imports this module, so not at the top
        name = one_add_named(self.folder, line)
        if name is None or line_reads.meant_question(self.folder, line) \
                or len(named_in(self.folder, line) or named_loosely(self.folder, line)) != 1:
            return False
        self._typed_addition(line, name)
        return bool(self._additions)

    def _add_offer_turn(self, user_text: str, how: str, t0: float
                        ) -> tuple[str, list[str], list[str]]:
        """t703: his typed add on the led path, code's own turn as 493's question is, no model call:
        the tap `_typed_addition` proposed, first even where t482's pending taps draw none (the
        brake's set stays as it is), then the taps and cards of where he is. The led turn's
        conversation keeps it, so his next line starts from the add. The taps, the cards, then the
        lines over them, in `_led_model_turn`'s order."""
        import led_turn
        pairs, mode = self._taps_now([])
        options = self._draw([*self._additions, *(p for p in pairs if p not in self._additions)])
        self._stage3_cards(mode)
        tap = self._additions[0][1]
        said = ADD_OFFER_SAID.format(resource=tap["resource"])
        state = self._led_state = self._led_state or led_turn.State()
        state.focus = tap["activity"]
        state.lines.append(user_text)
        state.history += [{"role": "user", "content": f"He typed: {user_text}"},
                          {"role": "assistant", "content": said}]
        if self._pointed:  # t377 D4: the card stands above
            said = f"{said}\n\n{DECISION_POINTER}"
        elif mode == "step" and (line := self._step_line(options)):  # t64
            said = f"{said}\n\n{line}"
        reply = self._server_reply(user_text, how, t0, said, options, ADD_OFFER_KIND, redraw=False)
        self.taps_stay = False  # drawn above, so these taps are the turn's own
        return reply

    def _start_turn(self, user_text: str, how: str, t0: float, start: tuple[str, dict[str, Any]]
                    ) -> tuple[str, list[str], list[str]]:
        """t704: his typed start, the start tap's own press (`_tap_turn`, by the tap's label). The
        led turn's conversation keeps it, as t703's add, so his next line starts from the walk it
        opened; its focus and his line before the narration, which may fail with the walk open."""
        import led_turn
        label, tap = start
        state = self._led_state = self._led_state or led_turn.State()
        state.focus = tap["args"].get("activity", state.focus)
        state.lines.append(user_text)
        turn = self._tap_turn(label, how, t0, tap)
        state.history += [{"role": "user", "content": f"He typed: {user_text}"},
                          {"role": "assistant", "content": turn[0]}]
        return turn

    def _add_turn(self, user_text: str, how: str, t0: float,
                  tap: dict[str, Any]) -> tuple[str, list[str], list[str]]:
        """t318: his add tap or a map link's: code writes this room's register (`walk`), and the
        map links still open are drawn, each its own tap. No model call."""
        on = time.strftime("%Y-%m-%d", time.gmtime())
        links = list(tap.get("links") or [])
        if tap["kind"] == "add":
            a = tap["activity"]
            aid = walk.add_dependency(self.folder, a, map_name(self.folder, a), tap["resource"], on)
            said = NOT_ADDED if aid is None else ADDED_SAID.format(
                resource=tap["resource"], activity=_said_name(self.folder, a), on=on)
        else:
            aid, link = tap["asset"], tap["link"]
            links.remove(link)
            written = walk.link_dependency(self.folder, aid, on, stands_on=link.get("stands_on"),
                                           at=link.get("at"))
            words_ = AT_SAID.format(site=link["at"]) if link.get("at") else link["label"]
            said = (LINKED_SAID if written else NOT_LINKED).format(
                resource=tap["resource"], on=on,
                link="" if tap["resource"].endswith(f" {words_}") else f" {words_}")
        for link in links if aid is not None else []:
            self._register(link["label"], {"kind": "link", "asset": aid, "link": link,
                                           "resource": tap["resource"], "links": links})
        return self._server_reply(user_text, how, t0, said,
                                  [link["label"] for link in links if aid is not None], "added")

    def read_room_file(self, path: str) -> Any:
        # t109: a dot-path is nemo's own (the turn file among them), never one of the company's
        # files, so it is refused as the listing hides it, wherever the path climbs to reach it
        if _dotted(jailed_path(self.folder, path).relative_to(self.folder.resolve()).as_posix()):
            return wrong_call(
                f"{path} is not one of the room's files", files=self.list_room_files()["files"]
            )
        self._read_this_turn.append(jailed_path(self.folder, path))
        self._turn_read.append(
            jailed_path(self.folder, path).relative_to(self.folder.resolve()).as_posix()
        )
        return {
            "path": path,
            "text": jailed_path(self.folder, path).read_text(errors="replace")[:60000],
        }

    def _scope_card(self, activity: str, scope: dict[str, Any]) -> None:
        """Card 1 of 3: what the BIA is about, before the step that fixes it.

        The scope is settled at step 1 — `set_scope` refuses afterwards, because a split later
        would change what the manager signed. That makes this a commitment, not a formality, and
        the owner ruled it one of the three card moments (2026-09-17).
        """
        names = scope.get("activities") or [activity]
        prior = last_year(self.folder, names[0])
        draft = draft_for(activity, self.model, self.folder)
        # t528: those the draft keeps, as stage 2's "Keep these <n>" tap counts them
        n = len(kept_by_draft(self._offer(activity, draft, walk.current(self.folder, activity)))
                ) if draft else 0
        lines = [
            f"**What this BIA is about · {self._heading(activity)}**",
            "",
            f"**1 \u00b7 In scope.** {'; '.join(names)}. From {self._drawn(scope.get('source'))} "
            "\u2014 "
            f"{self._drawn(scope.get('how'))}."
            + (
                f" {n} interviews talk about it, and you confirm them at the next step."
                if n > 1
                else " 1 interview talks about it, and you confirm it at the next step."
                if n
                else ""
            ),
            "",
        ]
        if prior.get("found"):
            fig = prior["figures"]
            lines += [
                f"**2 \u00b7 Since last year** ({self._drawn(prior['ref'])}): MTPD "
                f"{fig.get('MTPD', '\u2014')}, "
                f"RTO {fig.get('RTO', '\u2014')}, RPO {fig.get('RPO', '\u2014')}.",
                "",
            ]
        else:
            lines += [f"**2 \u00b7 Since last year:** {prior.get('note')}.", ""]
        lines += [
            "**3 \u00b7 Not activities.** The interviews' own sub-steps (A1, A2\u2026) are "
            "evidence "
            "about this activity, never extra activities.",
            "",
            "**4 \u00b7 Settled here.** The scope is fixed at this step. Changing it later means "
            "starting the BIA again \u2014 everything after it is built on this list.",
            "",
        ]
        self.cards.append("\n".join(lines))

    def _interviews_card(self, activity: str, offer: list[dict[str, Any]]) -> None:
        """Stage 2's card: every interview offered, and why each one is (13_nemo, t66b).

        Drawn from `_offer`'s output, not left to the model to relay: a cross-department interview
        is offered only for its reason, so the reason reaches the manager word for word (M13).
        Own-department interviews come first: the floor always offers them, and the manager may
        still drop any.
        """
        own = [i for i in offer if i.get("own_department")]
        other = [i for i in offer if not i.get("own_department")]
        gone = [i for i in other if excluded(i)]  # t377 G8: one line, never one row each

        def line(i: dict[str, Any], where: str) -> str:
            # t79 fix 1: this `why` is a mix — `PROTOTYPE_draft.FLOOR_WHY` on an interview nemo
            # put back (`floor`), the drafting model's own sentence on the rest — so it is
            # attributed per line, from that mark, and never under one blanket sentence.
            # t377 N3: an interview the floor put back carries no speaker; its front matter names
            # the person (`_interviewee`)
            speaker = i.get("speaker") or _interviewee(self.folder, i["path"])
            who = f"{speaker} \u00b7 " if speaker else ""
            return (f"- {who}{self._drawn(i['path'])} \u00b7 {where}. "
                    f"{why_said(i)}{self._drawn(i.get('why'))}")

        # t429: the stage's own heading, drawn here in place of the card's own title, as stage 2's
        # other cards draw it: the model's words never carry it
        lines = [self._stage_2_title(activity), "",
                 f"**1 \u00b7 Filed under this activity's own department ({len(own)}).** These are "
                 "always offered, because they are filed under this activity's department. You can "
                 "still drop any of them.", ""]
        lines += [line(i, "own department") for i in own] + [""]
        lines += [
            # t377 N3: the count is the rows it heads; the folded rows count on their own line
            f"**2 \u00b7 From other departments ({len(other) - len(gone)}).** Each is offered only "
            "for the reason shown. Keep or drop each one.",
            "",
        ]
        lines += (
            [line(i, "another department: " + (map_name(self.folder, i["department"])
                                                if i.get("department") else "not named"))
             for i in other if i not in gone]
            or ["- none"]
        ) + [""]
        if gone:
            lines += [NOT_ABOUT_IT.format(n=len(gone), names=", ".join(
                f"{i.get('speaker') or self._drawn(i['path'])} \u00b7 "
                f"{map_name(self.folder, i.get('department') or '')}" for i in gone)), ""]
        if is_added(self.folder, activity):  # t72b: the risk register, rows drawn from the file
            lines += self._risk_lines(activity, "**3 \u00b7 The risk register**")
        self.cards.append("\n".join(lines))

    def _record_card(self, activity: str, c: walk.Card) -> None:
        """Stage 4's card: what a reviewer needs before the one tap that does not undo."""
        rec = c.proposal.get(walk.BIA) or {}
        try:  # so "read it whole" is a link that opens, not a 404 (the record is not written yet)
            import PROTOTYPE_v1graph
            PROTOTYPE_v1graph.draw(self.folder, record=rec)
        except Exception as e:  # a picture that fails to draw never blocks the review
            self.log("graph_error", str(e))
        self.cards.append(self.record_card_text(activity, rec, c.proposal.get(walk.FINDINGS)))  # type: ignore[attr-defined]  # walk re-exports FINDINGS

    def record_card_text(
        self, activity: str, rec: dict[str, Any], findings: list[Any] | None
    ) -> str:
        """The stage-4 card, drawn from the record (to be) alone, so it can be drawn again from the
        record on file and compared (t71).

        Five lines, in the order a BCM manager reads them (the reviewer, the BCM-user seat, 2026-09-17):
        the numbers, what changed since last year, what to challenge, where the figures the record
        carries come from, and where to read the whole thing. t71: "worth challenging" names every
        item still open under the id the signature accepts it by (a finding cut at two was OPEN-4 on
        the
        owner's walk, left open into the signature), and every reservation made so far, in his
        words.
        """
        state = load_state(self.folder, activity)
        run = walk.read_record(self.folder, walk.run_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        prior = last_year(self.folder, (state.get("scope") or {}).get("activities", [activity])[0])
        open_ = handover.items(rec, {"findings": list(findings or [])})
        lines = [f"**What you are signing · {self._heading(activity)}**", ""]
        for a in rec.get("activities") or []:
            ev = a.get("evidence") or []
            lines += [f"**1 · The numbers.** {a.get('name')}: MTPD **{a.get('mtpd') or '—'}**, "
                      f"recovery target **{a.get('recovery_target') or '—'}**"
                      # t79 fix 1: the card speaks to him, so the close is said in the second
                      # person here and in the third in every document written for somebody else
                      + (f" — {gap_words(a, rec.get('method'))}" if a.get("recovery_gap_flagged")
                         else f" — {closed_words_to_him(a)}" if a.get(GAP_CLOSED) else "")
                      + f"{rpo_clause(a)}. Owner on file: {a.get('owner') or '—'}.", ""]
            if prior.get("found"):
                fig = prior["figures"]
                lines += [
                    f"**2 · Since last year** ({prior['ref']}): MTPD was {fig.get('MTPD', '—')}, "
                    f"now **{a.get('mtpd')}**. RTO was {fig.get('RTO', '—')}, now "
                    f"**{a.get('recovery_target')}**.",
                    "",
                ]
            else:
                lines += [f"**2 · Since last year:** {prior.get('note')}.", ""]
            # t75: the gap as the record states it, never a reason its own figures contradict;
            # t76: or, where he closed one, that he closed it and the words he closed it in
            challenges = [gap_says(a, rec.get("method"))] if a.get("recovery_gap_flagged") else \
                [closed_says_to_him(a)] if a.get(GAP_CLOSED) else []
            lines += [
                "**3 · Worth challenging.** "
                + (" ".join(challenges) + " " if challenges else "")
                + (
                    "Still open, and accepted at the signature by id: "
                    + "; ".join(handover.ITEM.format(id=at, text=text) for at, text in open_)
                    + "."
                    if open_
                    else "Nothing is left open for the signature to accept."
                ),
                "",
            ]
            rows = sum(1 for e in ev if e.get("origin") in (ROW_FLOOR, ROW_KEPT))
            # t79: the three kinds the owner's sentence distinguishes, never a calculation counted
            # as a proposal of nemo's that he confirmed. Fix 1: and the heading says where they
            # come from, because one of the four is a calculation, which is nobody's words.
            lines += [
                f"**4 · Where the figures come from.** {whose_words(ev)}"
                + (
                    f" {rows} risk-register row{'s are' if rows > 1 else ' is'} quoted as "
                    "evidence and set{} no figure.".format("" if rows > 1 else "s")
                    if rows
                    else ""
                ),
                "",
            ]
        reserved = [r for r in handover._reservations(run) if r != handover.NOTHING_RESERVED]
        if reserved:
            lines += ["**Reserved on the way here.** " + " ".join(reserved), ""]
        lines += [
            f"**5 · Read it whole.** [Dependency graph]({self.page_link(LIVE_GRAPH)}) "
            "· the BIA and the handover are on file in your room.",
            "",  # t64b: §3.1, no path
            "Accepting writes this record and shows it as *accepted, not yet signed*. You can "
            "still come back and change it. **Signing is what does not undo.**",
            "",
        ]
        return "\n".join(lines)

    # the loop ───────────────────────────────────────────────────────────────
    def call(self, name: str, args: dict[str, Any]) -> Any:
        fn = getattr(self, name, None)
        if name.startswith("_") or fn is None or name not in {t["function"]["name"] for t in TOOLS}:
            return wrong_call(f"no tool {name}")
        try:  # tinst fix 1: arguments that do not bind are the model's wrong call, not a crash
            inspect.signature(fn).bind(**args)
        except TypeError as e:
            result = wrong_call(f"wrong arguments for {name}: {e}")
        else:
            try:
                result = fn(**args)
            except Exception as e:  # prototype: the model sees the error and makes another call
                # tinst fix 1: the message the model always had; `crash` names the raise for the
                # instrument, which reds a walk on it (a raise inside a tool is a nemo bug)
                result = wrong_call(f"{type(e).__name__}: {e}", crash=type(e).__name__)
        return self._served(result, str(args.get("activity") or "") or self._activity)

    def drawn_turn(self, text: str, cards: list[str]) -> tuple[str, list[str]]:
        """t107: a turn as he reads it: over the model's own answer as well as nemo's cards, each
        abbreviation and method term followed by its plain name at its first use in the turn, from
        the room's glossary and nemo's method terms. The taps are lookup keys and stay as drawn.
        t183: first, each of nemo's own conflict and item ids in the answer is said by its name
        (`Names.ids_said`), whatever the model wrote; a `>` quote line keeps what it says.
        t215: the standard's own words are named the first time he reads one in this conversation
        (`_standard_said`) and said bare after that; every other term is named once in each turn.
        t377 M: a term inside a register asset name (the item an add-tap echo names among them, once
        his tap has written it) is named after the whole name, never inside it."""
        if self._activity:  # t183: nemo's ids in the model's words, said by their names
            names = words.Names(self.folder, self._room_name(self._activity), self.model)
            text = "\n".join(line if line.lstrip().startswith(">") else names.ids_said(line)
                              for line in text.split("\n"))
        return words.named_turn(text, cards, words.room_terms(self.folder), self._standard_said,
                                words.item_names(self.folder),
                                words.room_categories(self.folder).values())

    def _served(self, result: Any, activity: str | None = None) -> Any:
        """t64: a tool result as the model reads it, every id with its human name beside it, read
        from the room's files now (`PROTOTYPE_words.Names`). The ids stay for the next call."""
        a = self._room_name(activity) if activity else None
        return words.Names(self.folder, a, self.model).served(result)

    def log(self, kind: str, data: Any) -> None:
        """Every event goes to the skin's log. Ticket 69: a turn also says when it ended, where the
        walk stood after it and the room's artefact sizes, so a walk is read from its turns
        alone."""
        if kind == "said":  # t107: the text it holds is the raw text; he read it named (`turn`)
            data = {**data, "text_is": RAW}
        if kind != "turn":
            self._sink(kind, data)
            return
        if "path" not in data:  # t600: the one shape, beside the brake's own keys
            data = {**data, **brake_fields(data)}
        self.last_turn = {
            **data,
            TURN_ID: getattr(self, "turn_id", ""),
            "unaccounted_seconds": _unaccounted(data),
            **_accounting(data, time.time(), threading.get_ident()),
            **self._walk_now(),
        }
        self._sink(kind, self.last_turn)

    def _stages(self) -> dict[str, int]:
        """Every walk's stage in the room, by its run file's name (0 before any card is
        answered)."""
        out = {}
        for f in (self.folder / walk.RUNS).glob("*.json"):
            try:
                out[f.name] = json.loads(f.read_text()).get("stage") or 0
            except (OSError, ValueError):
                continue
        return out

    def _walk_now(self) -> dict[str, Any]:
        a = self._activity
        run, file = {}, Path(walk.run_file(self._room_name(a))) if a else None
        if file:
            try:
                run = json.loads((self.folder / file).read_text())
            except (OSError, ValueError):
                run = {}
        return {
            "at": round(time.time(), 1),
            "activity": a,
            "stage": run.get("stage") or 0,
            # the stage this turn started from: a turn that names the activity and answers its
            # card in one go is not taken for the walk's start (the owner's bar counts cards)
            "stage_before": self._stages_before.get(file.name, 0) if file else 0,
            "signed": run.get("status") == walk.CLOSED,
            # the documents he gets; nemo's working state (dot folders) is not an artefact
            "artefacts": {
                str(f.relative_to(self.folder)): f.stat().st_size
                for top in ("output", "public")
                for f in (self.folder / top).rglob("*")
                if f.is_file()
                and not any(part.startswith(".") for part in f.relative_to(self.folder).parts)
            },
        }

    def turn(self, user_text: str, how: str = "typed", pick: bool = False,
             action: str | None = None) -> tuple[str, list[str], list[str]]:
        """One manager turn (`_turn`). Ticket 69: a turn that fails is logged as a failed turn as it
        happens, then raised as before, so a walk that dies on a lane still says so in the log.
        t418 (ADR-0051): what it shows names every person by function (`words.functions_only`),
        the model's words and code's alike, unless his typed line asks for names."""
        start_trace()  # t82: the first turn arms the sampler; a suite that never turns never does
        self.last_turn = {}
        self._meant = False
        if how == "tapped" and (pick or action is not None):
            tap = self._tap_lookup(user_text, action) or {}
            self._meant = tap.get("kind") == "meant"
            if tap.get("kind") in ("meant", "again"):
                # t471, t536: his pick under "Which did you mean?", and the plain line's "Ask
                # again", are his line as typed right, or as typed
                user_text, how, pick, action = tap["line"], "typed", False, None
        self.turn_id = uuid.uuid4().hex
        if (
            how != "opener"
        ):  # t171: the turn under way, which his acts on it rest on until its line is written
            IN_FLIGHT[str(self.folder)] = (self.turn_id, {
                WORDS: self.shown(user_text) if how == "tapped" else user_text,
                ON: time.strftime("%Y-%m-%d", time.gmtime())})
        lanes.note_purpose("turn")
        t0 = time.time()
        self._stages_before = self._stages()
        # t107: the terms the model's tool results have named in this turn; t215: the standard
        # words it has already read in this conversation start the turn named
        self._told = set(self._standard_told)
        # t297, t299: a room whose register, method or added activities is not JSON answers
        # nemo's note naming the file, and no model
        if (unreadable := walk.unreadable_file(self.folder)) is not None:
            return self._unreadable(user_text, how, t0, *unreadable)
        # t108; t252: his typed line names the activities it holds by whole name
        self._turn_read = []
        self._turn_named = named_in(self.folder, user_text) if how == "typed" else []
        self._line_named = (set(self._turn_named) | set(loosely_named(self.folder, user_text))
                            if how == "typed" else set())
        if self._turn_named and self._about not in self._turn_named:
            self._about = None  # t377i: he named another activity
        if how == "typed" and (named := self._turn_named
                               or named_loosely(self.folder, classless(self.folder, user_text))):
            self._thread = named[0]  # t395: his line names where the room is
        self._turn_assets = register_named(self.folder, user_text) if how == "typed" else []
        self._turn_line = user_text if how == "typed" else ""  # t318: links from THIS line only
        self._referrals = []  # t256: a proposal never outlives the answer it was drawn under
        self._additions = []  # t318: nor does a dependency's
        self.taps_stay = False
        self._slides_tap = []
        self._invite_tap = []
        self._asked_write = False  # t366
        self._analysing = False  # t377 D2
        self._pointed = False  # t377 D4
        self._staged = False  # t429
        self._turn_tools = []  # t377 D4: the tools this turn's model called
        self._code_said = self._lead_said = self._code_kind = self._check_said = ""  # t377
        self._card_said = ""  # t516
        self._answered = self._server_set = ""  # t478
        self.live_at = None
        try:
            text, options, cards = self._turn(user_text, how, pick, action)
        except Exception as e:
            # fix 1: the log line reads the room (`_walk_now`), and a room read can fail too. The
            # exception the turn actually died on is the one the walk must see, so a failure to
            # log the failure is swallowed here: a lost line, never a swapped exception.
            with contextlib.suppress(Exception):
                self.log("turn", {"model": self.model, "how": how,
                                  "seconds": round(time.time() - t0, 1), "model_seconds": None,
                                  "tool_seconds": None, "tools": [],
                                  "failed": f"{type(e).__name__}: {e}"})
            raise
        self.answer_stage = self._answer_stage()
        self.last_turn["answer_stage"] = self.answer_stage  # t478: SHARED, the turn file's too
        self._keep_focus()  # t533
        if how == "typed" and words.NAMES_ASKED.search(user_text):
            return text, options, cards  # t418 (ADR-0051): his line asks for names
        # t418: every person by function, in the answer and its cards (the seed keeps the names);
        # the history keeps what he was shown
        shown = words.functions_only(text, self.folder)
        if self.messages and self.messages[-1] == {"role": "assistant", "content": text}:
            self.messages[-1]["content"] = shown
        named = [words.functions_only(c, self.folder) for c in cards]
        for card, said in zip(cards, named, strict=True):  # t255: its charts, by the card shown
            if said != card and (charts := self.impact_charts(card)):  # t552: by the key too
                self._charts[said] = charts
        return shown, options, named

    def _turn(self, user_text: str, how: str = "typed", pick: bool = False,
              action: str | None = None) -> tuple[str, list[str], list[str]]:
        """One manager turn. `how` is "typed" or "tapped" (ticket 69: the walk counts both).

        t73: a tap carries the action it stands for (`action`, the id the skin's payload holds; or,
        marked with `pick`, the label as last drawn). A tap nemo drew makes its one call directly
        (`_tap_turn`); a typed line goes to the model as before, and the model may call tools."""
        self.log("manager", {"model": self.model, "text": user_text})
        # fix 4 (review 4, claim 2): a proposal slot never outlives the turn it was drawn for. His
        # tap reaches its call through the id it was drawn under (`_tap_ids`), never through these,
        # so nothing he can press needs them once the turn that drew them is over.
        self._chat_proposal = self._chat_referral = self._chat_signature = None
        self._programme_turn = how == "typed" and asks_about_programme(user_text)
        if how == "typed":
            self._typed.append(user_text)
            log_said(self.folder, user_text, "typed")  # t71b: what manager-origin text is held to
        self._sheet_text, self._sheet_drawn = None, False
        self._guidance_text = None
        self._hold_offered = None
        self.last_pick = False
        self.stats["turns"] += 1
        t0 = time.time()
        if how == "opener":
            # t96: the app's opener gets nemo's own greeting, no model call and no taps: he asks,
            # or says when he wants to start. Before every state below, so a waiting state stays.
            return self._server_reply(user_text, how, t0, greeting(self.folder), [], "greeting")
        marked = how == "tapped" and (pick or action is not None)
        tap = self._tap_lookup(user_text, action) if marked else None
        kind = (tap or {}).get("kind")
        if how == "typed" and self._picking:  # t440: a typed line drops an unanswered pick set,
            self._last_taps, self.last_actions = [], []  # so no turn draws it again as its own
        ask_pending, self._asked_for = self._asked_for, None  # t513: only the very next turn's
        if ask_pending and tap is not None and kind == "tool" and tap["tool"] == "get_step" \
                and ask_pending[1].get(user_text) == (picked := tap["args"].get("activity")) \
                and picked in walk.processes(self.folder):
            # t513: his pick in 504's picker answers the ask it was drawn for, by code; a Start
            # tap (the same get_step) still starts the walk
            return self._asked_turn(user_text, how, t0, ask_pending[0], picked)
        if (tapped_on := (tap or {}).get("activity") or ((tap or {}).get("args") or {}).get(
                "activity")) and tapped_on != self._about:
            self._about = None  # t377i: a tap on another activity takes code's out of context
        if tap is not None and kind not in ("refer", "page", "mailbox", "write", "add", "link",
                                            "chart", "chart_grid", "invite",
                                            "put_drafts", "put_letter",
                                            "move_invite"):  # t96: every
            self._walk_on = True  # tap nemo draws is the walk's, but free chat's: a referral's
            # (t256), a page's (t276), the mailbox's (t277) and "Write to an owner" (t317)
        notes: list[str] = []
        # Ticket 72: the server's own states come before the model, and none reads his words for
        # meaning. After "Another activity…" his next typed line IS the name (any tap clears it);
        # while nemo's interview is under way his typed line IS the answer. t73: after a "Change …"
        # tap his next typed line IS the value, the same way.
        if self._awaiting_name:
            self._awaiting_name = False
            if how == "typed" and not slug(user_text):  # nothing a file can be named by: ask again
                self._awaiting_name = True
                return self._server_reply(user_text, how, t0, ASK_NAME, [], "ask_name")
            if how == "typed":
                # t346: the name is his pick, as a pick tap is: it touches nothing (317's step)
                self._turn_named = []
                name, new = self._add(filed_as(self.folder, user_text), ROUTE_TAP)
                notes.append(
                    f"(nemo: the manager typed {user_text.strip()!r} as the name of a new "
                    f"activity when nemo asked for one, so {name!r} is "
                    f"{'now in the room' if new else 'the room activity of that name'}. "
                    f"Its BIA is open; nemo's step, read now: "
                    f"{json.dumps(self.get_step(name), default=str, ensure_ascii=False)[:3000]} "
                    "Carry on with it; do not ask him to confirm the name.)"
                )
        elif self._awaiting_value is not None:
            asked, self._awaiting_value = self._awaiting_value, None
            if how == "typed":
                args = self._value_args(asked, user_text)
                if args is None:  # nothing that argument can be: ask again, nothing is called
                    self._awaiting_value = asked
                    return self._ask_reply(user_text, how, t0, asked)
                self._typing = user_text  # fix 1: the value decide gets is his typed line
                try:
                    return self._tap_turn(
                        user_text,
                        how,
                        t0,
                        tool_tap(asked["tool"], **args),
                        asked,
                        then_reason=self._asks_reason(asked),
                    )
                finally:
                    self._typing = None
        elif self._awaiting_reason is not None:
            # t64: his typed figure opened a flag and nemo asked why; his next typed line IS the
            # reason, word for word, and the Skip tap leaves none. Any other tap: no reason.
            pending, self._awaiting_reason = self._awaiting_reason, None
            if how == "typed" and not user_text.strip():
                self._awaiting_reason = pending
                return self._server_reply(user_text, how, t0, pending["ask"], [words.NO_REASON_TAP],
                                          "ask_reason")
            if how == "typed" or kind == "no_reason":
                return self._reason_turn(
                    user_text, how, t0, pending, user_text if how == "typed" else None
                )
        elif self._awaiting_refer is not None:
            # t256: after his referral tap, his next typed line IS the referral, word for word;
            # any tap leaves it unreferred
            pending, self._awaiting_refer = self._awaiting_refer, None
            if how == "typed" and not user_text.strip():
                self._awaiting_refer = pending
                return self._server_reply(user_text, how, t0, REFER_ASK, [], "refer_ask")
            if how == "typed":
                return self._refer_turn(user_text, how, t0, pending)
        elif self._interview is not None and not self._interview["done"]:
            return self._interview_turn(user_text, how, t0, tap)
        elif how == "typed" and (reserving := self._awaiting_reservation()):
            # t71: after an answer that reserves something, nemo's walk waits for the reservation
            # (its run file says so) and his next typed line IS it, word for word: the one call,
            # never the model's copy of his words. The refusal the model met for naming it
            # itself (fix 1) stands for the model, never for his own line — as it does for every
            # other tool since the ledger became a model-turn ledger (`dispatch`).
            return self._tap_turn(user_text, how, t0,
                                  tool_tap("answer_step", activity=reserving, answer=user_text),
                                  {"prompt": walk.RESERVING})
        if kind == "refer":
            self._awaiting_refer = tap
            return self._server_reply(user_text, how, t0, REFER_ASK, [], "refer_ask")
        if kind == PENDING_KIND:  # t482: his open conflict, to its owner; no model
            return self._pending_turn(user_text, how, t0, tap)  # type: ignore[arg-type]
        if kind == "write":  # t317: the activity's holders, his pick a referral tap; no model
            # why: `tap` is set: `kind` came from it
            a, item = tap["activity"], tap["item"]  # type: ignore[index]
            # t377: on a step found on the open discrepancies, their recipients
            picks = write_picks(self.folder, a, bool(tap.get("found")))  # type: ignore[union-attr]
            for label, refers in picks:  # t475: each drafts one, so its label says so
                theirs = [r for r, _ in refers]
                self._register(label + MAIL_MARK, {
                    "kind": "refer", "activity": a, "resource": theirs[0], "resources": theirs,
                    "item": refers[0][1] or item, "to": label,
                    "pairs": [[r, i or item] for r, i in refers]})
            said = self._server_reply(user_text, how, t0,
                                      WRITE_ASK.format(activity=_said_name(self.folder, a)),
                                      [label + MAIL_MARK for label, _ in picks], "write_ask")
            self._picking = True  # t440
            return said
        if kind in ("add", "link"):  # t318: his tap writes this room's register; no model
            return self._add_turn(user_text, how, t0, tap)  # type: ignore[arg-type]
        if kind == "more":  # t377 G8: the folded drops, drawn beside the taps; no call, no model
            pairs = [(self._held(t["label"], call), call) for t in self._last_taps
                     if t.get("kind") != "more"
                     for call in [{k: v for k, v in t.items() if k != "label"}]]
            pairs += [(said, call) for said, call in tap["taps"]]  # type: ignore[index]
            for label, call in pairs:
                self._register(label, call)
            return self._server_reply(user_text, how, t0, MORE_SAID,
                                      [label for label, _ in pairs], "more")
        if kind == "chart":  # t367 B: the activity's chart, no call and no model
            return self._chart_turn(user_text, how, t0, tap["activity"])  # type: ignore[index]
        if kind == "chart_grid":  # t367: the grid behind chart A
            return self._chart_grid(user_text, how, t0, tap["activity"])  # type: ignore[index]
        if kind == "page":  # t276: the page's link, no call and no model
            # why: `tap` is set: `kind` came from it
            now = current_tap(self.folder, tap)  # type: ignore[arg-type]  # t662: an old room's
            if now is None:
                return self._server_reply(user_text, how, t0, PAGE_GONE, [], "page")
            link = self.page_link(now["page"])
            if now["page"] == LIVE_GRAPH:  # t636: drawn on the press
                draw_on_press(self.folder)
            label = user_text if now is tap else DEPENDENCY_GRAPH_TAP  # t662: the graph's words
            return self._server_reply(user_text, how, t0,
                                      PAGE_SAID.format(label=label, link=link), [], "page")
        if kind == "invite":  # t373: the app places the invitation and the blocker; no model
            return self._server_reply(user_text, how, t0,
                                      self.place_invite(tap["activity"]),  # type: ignore[index]
                                      [], "invite")
        if kind == "put_drafts":  # t406: the drafts he was shown, as the app places them
            return self._server_reply(user_text, how, t0,
                                      self.place_shown(tap["activity"]),  # type: ignore[index]
                                      [], "put_drafts")
        if kind in ("put_letter", "move_invite"):  # t539/t540: the led turn's tap, the app's press
            press = self.place_letter if kind == "put_letter" else self.place_move
            return self._server_reply(user_text, how, t0, press(tap),  # type: ignore[arg-type]
                                      [], kind)
        if kind == "mailbox":  # t277: 257's tap, as the app presses it; no model
            return self._server_reply(user_text, how, t0, self.place_drafts(), [], "mailbox")
        if kind == "another":
            self._awaiting_name = True
            return self._server_reply(user_text, how, t0, ASK_NAME, [], "ask_name")
        if kind == "ask":
            self._awaiting_value = tap
            # why: `tap` is set: `kind` came from it
            return self._ask_reply(user_text, how, t0, tap)  # type: ignore[arg-type]
        # why: `tap` is set: `kind` came from it
        if kind in SHOWS and tap.get("activity"):  # type: ignore[union-attr]  # t115: one table, no answer, no call, no model
            # 117's amendment: nothing is redrawn. The decision taps stay on the live card's
            # message, still current; only the show taps go under the table (`SHOW_TAPS`)
            self._tapped = SHOWS[kind]
            return self._server_reply(
                user_text, how, t0, "", [t["label"] for t in self._last_taps], kind, redraw=False
            )
        if (
            kind == "as_is"
        ):  # the pending change was cleared above (any tap clears it); nothing called
            pairs, _ = self._taps_now([])
            self._draw(pairs)
            return self._server_reply(user_text, how, t0, "Nothing changed: it stays as it is.",
                                      [label for label, _ in pairs], "as_is")
        act = (tap or {}).get("activity")
        if kind == "hold" and act and self._interview is None and self._no_interview_on_file(act):
            self._activity = act
            m0 = time.time()
            say, next_ = self._start_interview(act)
            return self._server_reply(user_text, how, t0, say, next_, "interview", time.time() - m0)
        if kind == "tool":
            # why: `tap` is set: `kind` came from it
            return self._tap_turn(user_text, how, t0, tap)  # type: ignore[arg-type]
        iv = self._interview
        if kind == "keep" and iv and iv["done"] and iv["activity"] == act:
            # fix 1: a tap turn like any other. Its one action files the interview; the model then
            # speaks with no tools, so it cannot confirm stage 2 with a drop of its own. Stage 2's
            # keep/drop taps (and 72b's risk-register rows) are drawn from the files after it.
            self.messages.append({"role": "user", "content": user_text})
            c0 = time.time()
            kept = self._file_held(act)
            self._activity = act
            return self._narrate(
                user_text,
                how,
                t0,
                time.time() - c0,
                [],
                "(nemo: the manager tapped “Confirm this interview”, so nemo filed the interview "
                "he "
                "just gave and rebuilt the draft from the room's files, and did nothing else. "
                "Step 2 "
                "now offers the interviews as for any activity: "
                f"{json.dumps(kept, default=str, ensure_ascii=False)[:3000]} Tell him in your own "
                "sentences; there are no tools this turn: nemo draws the taps under your message.)",
                "Filed: the interview you gave is on file.",
                # t82 fix 1: these seconds are nemo's own, not a dispatched tool's. On the baseline
                # run they were 662.3 of the turn's 663.5, and the run file said `tools: []`.
                tool_work="file the interview and rebuild the draft (Session._file_held)",
            )
        if how == "typed" and not notes and not self.graph_page and not self._meant \
                and (meant := one_typo_off(user_text)):  # t471: one typo, as a fallback
            taps: dict[str, str] = {}  # r2: each tap names the answer it draws
            for card, (_, line) in meant.items():
                taps.setdefault(MEANT_LABELS[card], line)  # "to owners" and "write": one draft
            if len(taps) > 1:  # two answers or more: he picks, no card is drawn, no model
                for label, line in taps.items():
                    self._register(label, {"kind": "meant", "line": line})
                said = self._server_reply(user_text, how, t0, WHICH_MEANT, list(taps), "meant")
                self._picking = True
                return said
            user_text = next(iter(taps.values()))  # one answer: drawn as if typed right
            self._turn_line = user_text
        if how == "typed" and self._led_takes(user_text, notes):  # t546: behind the brake, none
            if self._led_add_asked(user_text):  # t703: the led turn has no tool to propose it
                return self._add_offer_turn(user_text, how, t0)
            if not (self.walk_prompt and (self._activity or self._interview)) \
                    and (start := typed_start(self.folder, user_text)):  # t704: on none he is on
                return self._start_turn(user_text, how, t0, start)
            return self._led_model_turn(user_text, how, t0)
        wants = asked_for(user_text) if how == "typed" and not notes and not self.graph_page \
            else Asked(False, False)
        self._asked_write = how == "typed" and not notes and not self.graph_page \
            and asks_to_write(user_text)
        self._analysing = how == "typed" and not self.walking and asks_to_analyse(user_text)
        if wants.slides and slides_filled(self.folder):  # t329: outside ADR-0045's cap
            self._slides_tap = [(SLIDES_TAP, page_tap("slides"))]
        about = self._about_now(user_text) if how == "typed" and not notes \
            and not self.graph_page else None
        if about and asks_to_invite(user_text) and planned_day(self.folder, about):
            self._invite_tap = [(INVITE_TAP, {"kind": "invite", "activity": about})]  # as 329's
        if how == "typed" and not notes and self.walking and self._activity \
                and asks_to_analyse(user_text) and (keep := self._keep_these(self._activity)):
            # t377 J: at stage 2 his analysis ask is his choice: the "Keep these N" tap's own call,
            # then code's line on what it kept and stage 3's findings; the model's words dropped
            (n, names), tap = keep
            self._code_said = "\n\n".join(filter(None, [
                (KEPT_ONE_SAID if n == "1" else KEPT_SAID).format(n=n, names=names),
                findings_said(self.folder, self._activity)]))
            self._code_kind = KEPT_KIND
            return self._tap_turn(user_text, how, t0, tap)
        if how == "typed" and not notes and self.walking and self._activity \
                and ANALYSE_WORDS.search(user_text):  # t377 (C): in a walk only
            self._lead_said = findings_said(self.folder, self._activity)
        if about and BRIEFING_WORDS.search(user_text):  # t389 (B7): code's, never the model's
            self._code_said, self._code_kind = briefing_said(self.folder, about), BRIEFING_KIND
            import briefing  # t405: it imports this module, so not at the top
            if briefing.chrome():  # the PDF's download only where its print can run
                self._code_said += "\n\n" + BRIEFING_PDF.format(
                    link=self.page_link(f"briefing/{about}.pdf"))
            self._about = about
        elif about and asks_who_comes(user_text):
            self._code_said, self._about = invite_said(  # t377 (B); t418 r2: names if asked
                self.folder, about, bool(words.NAMES_ASKED.search(user_text))), about
            self._answered = "B3"  # t478
        elif about and FOCUS_WORDS.search(user_text) and not (  # t377 (D3, D6)
                asks_what_changed(user_text) and not FOCUS_ASKED.search(user_text)):  # t457
            self._code_said, self._about = focus_said(self.folder, about, QUESTIONNAIRE if
                                                      QUESTIONNAIRE_WORDS.search(user_text)
                                                      else FOCUS_NOW), about
            self._answered = "B4"  # t478
        elif how == "typed" and not notes and not self.graph_page \
                and not wants.chart and not asks_which_next(user_text) \
                and not ADD_ASKED.search(user_text) and (
                asks_dependencies(user_text)):
            # t390 (A6, B5, B6): code's answer, never for an impact-chart ask. t395: on the room's
            # activity (`_room_activity`), never a guess. t488 (D1): three lines and the graph
            # page's link, the dependency graph asked for too; B5 its table, the link at its end;
            # a resource his line names, its view (485's)
            spof = bool(SPOF_WORDS.search(user_text))
            if not spof and (view := resource_view(self.folder, user_text)):
                return self._resource_turn(user_text, how, t0, view)
            on = self._room_activity(user_text)
            self._code_said = self._dependencies(user_text, on) if on else NO_ACTIVITY_SAID
            self._code_kind, self._about = DEPENDENCY_KIND, on
        if how == "typed" and not notes and not self.graph_page and not self._code_said:
            self._code_answer(user_text)  # t377 H1, H2
        if how == "typed" and not notes and not self.graph_page and not self._code_said \
                and not self._asked_write and asks_what_to_check(user_text) \
                and (on := self._sheet_activity(user_text)):
            # t507 (A9): this year's changes lead; the model's words follow, as without them
            self._check_said = check_said(self.folder, on)
        if wants.chart and (view := resource_view(self.folder, user_text)):
            return self._resource_turn(user_text, how, t0, view)  # t485: a resource, no chart
        if wants.chart and (chart_of := self._chart_activity()):
            return self._chart_turn(user_text, how, t0, chart_of)
        if wants.chart:  # t367 B: no activity to draw; code's line and taps, never the model
            return self._chart_pick(user_text, how, t0)
        if (how == "typed" and not notes and not self.graph_page and asks_which_due(user_text)
                and (due := due_reviews(self.folder))):  # t377 D1: the plan's, no model call
            return self._server_reply(user_text, how, t0, due,
                                      [t["label"] for t in self._last_taps], "due", redraw=False)
        if how == "typed" and not notes and not self.walking and not self._code_said \
                and not self._asked_write and asks_what_changed(user_text):  # t433 (A1)
            on = self._sheet_activity(user_text)
            day = named_day(self.folder, user_text)  # t544 r3: a day holding interviews wins
            if on and this_years_path(self.folder, on) is None \
                    and not (day and day_interviews(self.folder, day)):  # t475: none to compare
                self._code_said = NOT_COMPARED_SAID.format(activity=map_name(self.folder, on))
                self._code_kind, self._about = NOT_COMPARED_KIND, on
            else:
                self._analysing = True
                on_day = day_interviews(self.folder, day) if day else []
                if len(owners := {a for p in on_day for a in interview._named_in(
                        self.folder / p)}) == 1:  # t550: the card's activity is the room's focus
                    self._about = next(iter(owners))
        if (changed := self._files_note()):  # t249; t284: a tap turn compares in `_narrate`
            notes.append(changed)
        self.messages.append({"role": "user", "content": user_text})
        self.messages += [{"role": "user", "content": n} for n in notes]
        if self._asked_write:  # t366: the model is told the tap exists
            self.messages.append({"role": "user", "content": WRITE_NOTE})
        # ticket 69 (3_nemo_check / t70): time inside the model lane and inside the tools, kept
        # apart
        tools_called: list[str] = []
        held = {a: load_state(self.folder, a) for a in walk.processes(self.folder)}  # fix 3
        self._model_turn = True  # t71: the calls below are the model's
        try:
            reply, refused, model_s, tool_s = self._model_calls(tools_called)
        finally:
            self._model_turn = False
        if (moved := self._his_figures_moved(held)):
            refused = moved
        if how == "typed" and not refused:
            # t417: after the model, so its own call stands
            self._typed_addition(user_text, asked_to_add(user_text))
        if refused:
            return self._refusal_turn(refused, how, t0, model_s, tool_s, tools_called)
        return self._finish(reply, how, t0, model_s, tool_s, tools_called, self._tools_now())

    def _led_takes(self, line: str, notes: list[str]) -> bool:
        """t546 (ADR-0056, S5a 536a): his typed line goes to the model-led turn (`led_turn`) where
        the brake is off the path: the switch ON (read now; a missing file is the brake set) and the
        module wired in (`led_turn.WIRED`, 536's full build). 608: in a walk too, handed the walk's
        tools. Nothing else reaches it, and a line asking about the standard keeps 506's chat path
        (the guidance lookup is code's, not a tool of this turn)."""
        if notes or self.graph_page:
            return False
        import line_reads  # it imports this module, so not at the top
        return self._one_stack() and not line_reads.about_the_standard(line)

    @staticmethod
    def _one_stack() -> bool:
        """The switch ON and the led turn wired in (546): typed lines go to the led turn, and
        (607) every other answer the model writes goes through its one check stack."""
        import agent_fallback  # they import this module, so not at the top
        import led_turn
        return led_turn.WIRED and agent_fallback.switched_on()

    def _checked(self, text: str, handed: str, ran: list[str],
                 pairs: list[tuple[str, dict[str, Any]]]) -> Any:
        """607 (ADR-0061 d3, map N5): a tap's narration or a guidance answer's sentence through
        `checks.check`, the stack a typed answer meets. A figure in what nemo handed the model (the
        tap's call and its result, the standard's text) stands uncited, as a fact tool's does; a
        tap it names must be one drawn under it. 720: a value from a marked row in what it was
        handed gets the demo mark, by a typed answer's route; on a guidance answer under the
        block, as `_finish` keeps one sentence of the text."""
        import checks  # it imports this module, so not at the top
        room = checks.Room(self.folder, {}, getattr(self, "_turn_line", "") or "",
                           activity=self._activity, ran=ran, offers=self._offered(),
                           taps=[label for label, _ in pairs])
        room.known = set(checks.facts(handed, room.classes, self.folder))
        room.marked = checks.marked_values(handed)
        out = checks.check(text, room)
        mark = checks.mark_line(out.text, checks.stands_marked(out.text, room))
        if self._guidance_text is not None:
            self._guidance_text = "\n\n".join([self._guidance_text, *mark])
        else:
            out.text = "\n\n".join([out.text, *mark])
        return out

    def _led_model_turn(self, user_text: str, how: str, t0: float
                        ) -> tuple[str, list[str], list[str]]:
        """t546: a whole turn the model leads (`led_turn.run`) over the GLM lane, on file with
        t532's keys (`led_fields`): path `model-led`, or `plain line` where it failed. t536: the
        graph answer's link is the room's page (488's), a failure draws code's taps (t546's shape
        keeps them off the record), and 493's question is code's own turn: two taps, no model
        call, no path."""
        import led_turn
        self._led_state = self._led_state or led_turn.State()
        was = self._led_state.focus
        # 608: the walk's taps and cards while the conversation is on one (a signed activity's
        # set too), its tools while its procedure is (`walk_prompt`), and fix 3's net over both
        walking = self.walking
        held = {a: load_state(self.folder, a) for a in walk.processes(self.folder)} \
            if walking else {}
        turn = led_turn.run(
            self.folder, user_text,
            lambda m, t: lanes.chat(led_turn.LANE, m, t, room=self.folder),
            self._led_state,
            graph=lambda a: self.page_link(f"{LIVE_GRAPH}/{a}" if a else LIVE_GRAPH),
            next_taps=self._led_taps, clock=self.led_clock or led_turn.Clock(),
            waiting=self.waiting,
            walking=led_turn.Walk(LED_WALK_TOOLS, self._walk_call) if self.walk_prompt
            else None)
        tools = [c["function"]["name"] for c in turn.tool_calls]
        if (ended := self._his_figures_moved(held) or turn.ended):  # 608: as the brake's (t67)
            self.messages.append({"role": "user", "content": user_text})
            return self._refusal_turn(ended, how, t0, turn.model_s, turn.tool_s, tools,
                                      tapped=True)
        if turn.path == led_turn.MODEL_LED and self._led_state.focus not in (None, was):
            self._thread = self._led_state.focus  # t584: the answer's activity, kept (533)
        if turn.path == led_turn.ASKED:  # t493: one question, two taps, no model call
            for label, action in turn.taps:
                self._register(label, action)
            said = self._server_reply(user_text, how, t0, turn.text,
                                      [label for label, _ in turn.taps], "meant")
            self._picking = True
            return said
        self.messages += [{"role": "user", "content": user_text},
                          {"role": "assistant", "content": self._led_state.history[-1]["content"]
                           if led_turn.cut_for_pdf(turn) else turn.text}]  # 757: its text kept
        text, taps, cards, mode = turn.text, turn.taps, [], ""
        if walking:  # 608: the walk's taps, then its cards, as `_finish` draws them
            pairs, mode = self._taps_now(tools)  # a turn that failed keeps its "Ask again" first
            taps = [*pairs, *taps] if turn.path == led_turn.MODEL_LED else [*taps[:1], *pairs]
        if asked_for(user_text).slides and slides_filled(self.folder):  # t329, outside the cap
            taps = [*taps, (SLIDES_TAP, page_tap("slides"))]
        options = self._draw(taps) if taps else []
        if walking:
            self._turn_tools = tools
            self._stage3_cards(mode)
            cards, self.cards = self.cards, []
        if self._pointed and turn.path == led_turn.MODEL_LED:  # t377 D4: the card stands above
            text = f"{text}\n\n{DECISION_POINTER}"
        elif mode == "step" and turn.path == led_turn.MODEL_LED \
                and (line := self._step_line(options)):
            text = f"{text}\n\n{line}"
        led = led_fields(turn.path, turn.tool_calls, turn.artefacts, turn.drops,
                         turn.must_cover_misses, turn.clock_s)
        if turn.charts:  # t538: code's card over the charts, and the room keeps the chart (533)
            # t588: a card per activity, each over its own chart
            self._charts = {c: [w] for c, w in zip(turn.cards, turn.charts, strict=True)}
            self._phones = {c: [p] for c, p in zip(turn.cards, turn.phones, strict=True)}
            # t745: and which of the turn's cards holds each activity's chart, for `replayed`
            shown.put(self.folder, shown.CHART, {
                "template": turn.template, "arguments": turn.args,
                "cards": list(range(len(cards), len(cards) + len(turn.cards)))},
                turn=self.turn_id)
            return self._led_turn(how, t0, "", options, [*cards, *turn.cards], turn.model_s,
                                  turn.tool_s, led)
        return self._led_turn(how, t0, text, options, cards, turn.model_s, turn.tool_s, led)

    def _walk_call(self, name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        """608: a walk tool the led turn called, through `dispatch` as a model turn (t71), so each
        write is refused at the function that writes (ADR-0006): the result as the model reads it,
        and, where it ends the turn as it ends the brake's (`_model_calls`), the result shown."""
        self._model_turn = True
        try:
            result, from_ledger = self.dispatch(name, args)
        finally:
            self._model_turn = False
        self.log("tool", {"model": self.model, "name": name, "args": args, "result": result})
        # t107: each term named at its first use in the conversation, as `_model_calls` hands it
        told = words.named_result(result, words.room_terms(self.folder), self._told,
                                  words.item_names(self.folder),
                                  words.room_categories(self.folder).values())
        self._standard_told |= words.standing(self._told)  # t215
        ends = isinstance(result, dict) and (result.get("refusal") == STANDING
                                             or result.get("server_turn"))
        return for_model(told), ({**result, "tool": name, "from_ledger": from_ledger,
                                    "turn_ended": True} if ends else None)

    def _led_taps(self) -> list[tuple[str, dict[str, Any]]]:
        """t536: the taps a model-led turn draws where it fails or runs out of time (537): "Ask
        again" first (his line as typed, resent), then at most two of code's next steps for the
        activity."""
        import led_turn
        return [(led_turn.ASK_AGAIN, {"kind": "again", "line": self._turn_line}),
                *self._taps_now([])[0][:2]]

    def _keep_these(self, a: str) -> tuple[tuple[str, str], dict[str, Any]] | None:
        """t377 J: at stage 2, the "Keep these N" tap stage 2 draws (`_interview_taps`): its count
        and names, and its call. None at any other stage, or where stage 2 draws no such tap.
        t439 box 2: the names come from `_kept_these`, as the tap's do, never from its label."""
        c = walk.current(self.folder, a)
        if c.stage != walk.STAGE_2 or not c.interviews:
            return None
        draft = draft_for(a, self.model, self.folder)
        own = {i.path for i in c.interviews}
        if not draft or not (these := self._kept_these(a, self._offer(a, draft, c), own)):
            return None
        names, tap = these
        return (str(len(names)), ", ".join(names)), tap

    def _code_answer(self, line: str) -> None:
        """t377 H1, H2: code's answer to which BIA next (`next_bia`) or to how long an activity
        can be down (`down_for`: one his line names, else the one under way), at any stage and in
        free chat; `_finish` shows it for the model's words and drops those. t413 (A5): to what does
        not match last year's record (`mismatches_said`), on the room's activity. t377 Q r2:
        the quotes behind the findings (`quotes_said`) of the activity his line names, else his
        analysis's; t508: else, in a running room on none yet, `_gaps_activity`'s."""
        if asks_which_next(line) and (said := next_bia(self.folder)):
            # t377i: the BIA it names is the one his next invite, focus or questionnaire is about
            self._code_said, self._code_kind = said, NEXT_KIND
            self._about = next_bia_activity(self.folder) or self._about
        elif (what := asks_how_long_down(line)) is not None:
            # t470: else the room's thread, else the one his last analysis was about
            named = named_in(self.folder, what) or loosely_named(self.folder, what) \
                or named_loosely(self.folder, what) \
                or [a for a in [self._activity, self._thread, self._analysed] if a][:1]
            if named and (said := down_for(self.folder, named[0], walk._method(self.folder))):
                self._code_said, self._code_kind, self._about = said, DOWN_KIND, named[0]
        elif asks_for_quotes(line, self._after_changes()):  # t377 Q r2, t450
            # t508: inside a running room that named, analysed and opened none, the one with
            # open findings; a room's first line still leaves the model to ask (377 Q r2)
            about = next(iter(named_in(self.folder, line)), None) or self._analysed \
                or self._activity or (self._answered_before() and self._gaps_activity(line)) or None
            if about and (said := quotes_said(self.folder, about)):
                self._code_said, self._code_kind, self._about = said, QUOTES_KIND, about
        elif asks_who_decides(line) and (on := self._gaps_activity(line)) \
                and (said := who_decides(self.folder, on)):
            self._code_said, self._code_kind, self._about = said, WHO_DECIDES_KIND, on
        elif asks_what_mismatches(line) and not (self._analysing and ANALYSIS_ASKED.search(line)) \
                and (on := self._room_activity(line)) \
                and (said := mismatches_said(self.folder, on, walk._method(self.folder))):
            self._code_said, self._code_kind, self._about = said, MISMATCH_KIND, on  # t413 (A5)

    def _answered_before(self) -> bool:
        """t508: nemo has answered a line in this room before (a running room)."""
        return any(m.get("role") == "assistant" for m in self.messages)

    def _after_changes(self) -> bool:
        """t450 (A2-17): nemo's last answer opened on the changes card (`CHANGES_HEADING`)."""
        said = next((m.get("content") for m in reversed(self.messages)
                     if m.get("role") == "assistant"), None)
        return isinstance(said, str) and said.startswith(CHANGES_HEADING.split("{")[0])

    def _gaps_activity(self, line: str) -> str | None:
        """t412 (A7): the activity whose open gaps his line asks about: of the one it names, the
        one under way, the room's thread, the one his last analysis was about, then the room's in
        the process map's order, the first with open `discrepancies`; None where none has."""
        named = named_in(self.folder, line) or named_loosely(self.folder, line)
        return next((a for a in dict.fromkeys(
            [*named, self._activity, self._thread, self._analysed,
             *process_map_order(self.folder, walk.processes(self.folder))])
            if a and discrepancies(self.folder, a)), None)

    def _sheet_activity(self, line: str) -> str | None:
        """t433 (A1, A8): the activity a line is about where nothing was read or analysed: one it
        names whole, else the walk's, else the one code last answered about, else, in a room on
        none yet, the first with open findings (`_gaps_activity`), so a room that never opened an
        activity answers as one that did. A loose word ("is it material?") names none here."""
        walked = self._activity if self._walk_on and self._activity in walk.processes(
            self.folder) else None
        return next(iter(named_in(self.folder, line)), None) or walked or self._about \
            or self._gaps_activity(line)

    def _dependencies(self, line: str, on: str) -> str:
        """t390, t488: code's answer to his dependency ask `line` on the activity `on`: B5's table
        for a single-point-of-failure ask, else three plain lines; the graph page's link after."""
        years = bool(YEARS_WORDS.search(line))
        return "\n\n".join([
            dependencies_said(self.folder, on, spof=True, years=years) if SPOF_WORDS.search(line)
            else dependencies_short(self.folder, on, years=years),
            GRAPH_LINK.format(link=self.page_link(f"{LIVE_GRAPH}/{on}"))])

    def _asked_turn(self, user_text: str, how: str, t0: float, line: str,
                    on: str) -> tuple[str, list[str], list[str]]:
        """t513: his pick under 504's picker, drawn for the dependency ask `line`: that ask's answer
        on the picked activity `on`, as if his line had been asked in a room on it, and the room on
        it from now on (t395's thread). No walk starts, no model call."""
        self._thread, self._turn_line = on, line
        self._code_said, self._code_kind, self._about = \
            self._dependencies(line, on), DEPENDENCY_KIND, on
        pairs, _ = self._taps_now([])
        self._draw(pairs)
        return self._server_reply(user_text, how, t0, self._code_said,
                                  [label for label, _ in pairs], DEPENDENCY_KIND)

    def _owners_activity(self) -> list[str | None]:
        """t433 (A8): where his write ask goes to the owners or the people responsible
        (`TO_OWNERS`), the activity whose open findings they own (`_sheet_activity`), read or
        analysed or not; nothing for any other write ask (366's "draft me an email")."""
        return [self._sheet_activity(self._turn_line)] if TO_OWNERS.search(self._turn_line) \
            else []

    def _room_activity(self, line: str) -> str | None:
        """t395: the activity his dependency ask is about: one his line names, else the walk he is
        on, else the room's thread (`_thread`); None where the room has none yet. A model's tool
        argument sets none of them: the walk counts only once a walk tool ran or he tapped into
        it, and only on an activity the room holds."""
        named = named_in(self.folder, line) or named_loosely(self.folder, line)
        walked = self._activity if self._walk_on and self._activity in walk.processes(
            self.folder) else None
        return named[0] if named else walked or self._thread

    def _about_now(self, line: str) -> str | None:
        """t377 (B, D3): the activity his invite, focus or questionnaire line is about: one it
        names (`named_in`, else `named_loosely`), else the one code last answered about, else
        `invite_activity`'s."""
        named = named_in(self.folder, line) or named_loosely(self.folder, line)
        return named[0] if named else self._about or invite_activity(self.folder, line,
                                                                    self._activity)

    def _his_figures_moved(self, held: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        """fix 3, the fidelity net behind the gate: the record's figures before the model's turn
        against after it. A figure he set that the turn moved is put back as he set it (the room's
        state as it was before the turn) and the turn ends on nemo's standing refusal, naming it.
        The gate makes this unreachable today; the report's positive control removes the gate and
        watches this red."""
        import PROTOTYPE_fidelity as fidelity
        for a, before in held.items():
            with room_lock(self.folder):  # t238 (C7): read, change and save as one
                after = load_state(self.folder, a)
                if (found := fidelity.his_figures_kept(self.folder, a, before, after,
                                                       self._method())):
                    self.log("fidelity", {"activity": a, "his_figures_moved": found})
                    save_state(self.folder, a, before)
                    return {**standing(FIGURE_KEPT_SAYS.format(activity=self._room_name(a)),
                                       [], "record_faithful", hold=False),
                            "tool": "decide", "from_ledger": False, "turn_ended": True}
        return None

    def _model_calls(
        self, tools_called: list[str]
    ) -> tuple[dict[str, Any], dict[str, Any] | None, float, float]:
        """The model's turn with tools: it calls until it speaks, or a standing refusal ends it."""
        model_s, tool_s = 0.0, 0.0
        reply: dict[str, Any] = {}
        refused: dict[str, Any] | None = None
        said: list[str] = []  # t377 D2: the words of each call that also called tools
        for _ in range(16):
            m0 = time.time()
            reply = lanes.chat(self.model, self.messages, self._tools_now(), room=self.folder)
            model_s += time.time() - m0
            self.stats["calls"] += 1
            self.stats["tokens"] += int((reply.get("_usage") or {}).get("total_tokens") or 0)
            calls = reply.get("tool_calls") or []
            self.messages.append(
                {k: v for k, v in reply.items() if k in ("role", "content", "tool_calls")})
            if not calls:
                break
            if (words_now := (reply.get("content") or "").strip()):
                said.append(words_now)
            for i, call in enumerate(calls):
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                c0 = time.time()
                result, from_ledger = self.dispatch(name, args)
                tool_s += time.time() - c0
                tools_called.append(name)
                if isinstance(result, dict) and (result.get("refusal") == STANDING
                                                 or result.get("server_turn")):
                    # Ticket 67: the whole reply is the refusal. The model's turn ends here; the
                    # calls after this one are not run and nothing it wrote is shown. Ticket 72:
                    # so is nemo's first interview question, when the model starts the interview.
                    refused = {
                        **result,
                        "tool": name,
                        "from_ledger": from_ledger,
                        "turn_ended": True,
                    }
                    result = refused
                self.log(
                    "tool", {"model": self.model, "name": name, "args": args, "result": result}
                )
                # t107: the model reads each term named at its first use in the turn; the log
                # above holds the result as the tool returned it
                told = words.named_result(result, words.room_terms(self.folder), self._told,
                                          words.item_names(self.folder),
                                          words.room_categories(self.folder).values())
                self._standard_told |= words.standing(self._told)  # t215: once in the conversation
                self.messages.append({"role": "tool", "tool_call_id": call["id"],
                                      "content": for_model(told)})
                if refused:
                    for rest in calls[i + 1:]:
                        self.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": rest["id"],
                                "content": json.dumps({"not_run": "the turn ended on a refusal"}),
                            }
                        )
                    break
            if refused:
                break
        if said and not refused:  # t377 D2: findings are never replaced by the last call's note
            reply = {**reply, "content": "\n\n".join([*said, reply.get("content") or ""]).strip()}
        return reply, refused, model_s, tool_s

    def _refer_turn(self, user_text: str, how: str, t0: float,
                    pending: dict[str, Any]) -> tuple[str, list[str], list[str]]:
        """t256: his line, the referral: nemo's walk writes it (`walk.refer`), code draws the
        follow-up list again, and he is told where it is. No model call. t317: a holder he picked
        is referred each resource of theirs, and he is told the holder's name."""
        to = pending.get("to") or walk.REFERRED_TO_SAID.format(resource=pending["resource"])
        pairs = pending.get("pairs") or [[name, pending["item"]] for name in
                                         pending.get("resources") or [pending["resource"]]]
        if not all([walk.refer(self.folder, pending["activity"], name, item, user_text)
                    for name, item in pairs]):
            return self._server_reply(user_text, how, t0, REFER_REFUSED, [], "refer_refused")
        write_follow_up(self.folder)
        return self._server_reply(user_text, how, t0, REFERRED.format(to=to), [], "referred")

    def _left_open(self, a: str) -> list[dict[str, Any]]:
        """t482: the conflicts on `a` he left unresolved at stage 3 and has not finished for now on
        (`PENDING_ANSWERS`): each waits for its owner's answer."""
        if a not in walk.processes(self.folder) \
                or walk.current(self.folder, a).stage != walk.STAGE_3:
            return []
        state = load_state(self.folder, a)
        decisions = state.get("decisions") or {}
        done = set(state.get(PENDING_ANSWERS) or [])
        return [i for i in items(state.get("draft") or {}) if i["type"] == "conflict"
                and (decisions.get(i["id"]) or {}).get("decision") == UNRESOLVED
                and i["id"] not in done]

    def _pending_sides(self, a: str) -> list[str]:
        """t482: each conflict left open on `a`, each side said for what it is (r2: "MTPD 72 h
        (your company's method) or more than 168 h (the Plant Manager)"), its field said once."""
        state = load_state(self.folder, a)
        out = []
        for c in self._left_open(a):
            entries = self._side_entries(a, c, state)
            first = entries[0]["field"] if entries else None
            out.append(" or ".join(
                (e["said"].removeprefix(f"{first} ") if k and e["field"] == first
                 else e["said"]) or e["label"] for k, e in enumerate(entries)))
        return out

    def _pending_refers(self, a: str) -> list[tuple[str, str, str]]:
        """t482: the referral each conflict left open on `a` puts to its owner, as `walk.refer`'s
        (resource, item, words): about the activity itself, in its sides' words."""
        return [(process_name(self.folder, a), PENDING_ITEM, PENDING_ASK.format(sides=sides))
                for sides in self._pending_sides(a)]

    def _pending_taps(self, a: str) -> list[tuple[str, dict[str, Any]]]:
        """t482: while a conflict he left unresolved is open, "Write to the <function> (E-Mail)"
        (until its question is on the follow-up list) and "Finish for now, pending answer"; else
        none."""
        refers = self._pending_refers(a)
        if not refers:
            return []
        asked = {said for _, activity, said in follow_up(self.folder) if activity == a}
        tap = {"kind": PENDING_KIND, "activity": a}
        write = [] if all(walk.REFERS_SAID.format(resource=r, item=i, words=w) in asked
                          for r, i, w in refers) \
            else [(PENDING_WRITE.format(function=owner_said(self.folder, a)), tap)]
        return [*write, (PENDING_FINISH, {**tap, "finish": True})]

    def _pending_reply(self, user_text: str, how: str, t0: float, a: str,
                       pairs: list[tuple[str, dict[str, Any]]],
                       said: str) -> tuple[str, list[str], list[str]]:
        """t482: code's line on the open conflict, with `pairs` as its taps; no model."""
        for label, action in pairs:
            self._register(label, action)
        text = said.format(function=owner_said(self.folder, a),
                           sides="; ".join(self._pending_sides(a)),
                           activity=process_name(self.folder, a))
        return self._server_reply(user_text, how, t0, text[:1].upper() + text[1:],
                                  [label for label, _ in pairs], PENDING_KIND, heard=True)

    def _pending_turn(self, user_text: str, how: str, t0: float,
                      tap: dict[str, Any]) -> tuple[str, list[str], list[str]]:
        """t482: his tap on an open conflict: its question goes to the owner (`walk.refer`, once
        per conflict), and "Finish for now" records the conflicts as waiting and leaves the walk
        for the activity pick."""
        a = tap["activity"]
        refers = self._pending_refers(a)
        self.messages.append({"role": "user", "content": user_text})
        if not all([walk.refer(self.folder, a, r, i, w) for r, i, w in refers]):
            return self._server_reply(user_text, how, t0, REFER_REFUSED, [], "refer_refused",
                                      heard=True)
        write_follow_up(self.folder)
        if not tap.get("finish"):
            return self._pending_reply(user_text, how, t0, a, self._pending_taps(a),
                                       PENDING_WRITTEN)
        said = PENDING_FINISHED.format(function=owner_said(self.folder, a),
                                       activity=process_name(self.folder, a))
        self._finish_pending(a)
        self._activity = None
        pairs = self._pick_set(None)
        for label, action in pairs:
            self._register(label, action)
        return self._server_reply(user_text, how, t0, said, [label for label, _ in pairs],
                                  PENDING_KIND, heard=True)

    def _pending_drafts(self, pairs: list[tuple[str, dict[str, Any]]]) -> str:
        """t482: t366's line on an open conflict's taps: its write tap, else that it is written."""
        a = str(pairs[0][1]["activity"])
        write = next((label for label, t in pairs if not t.get("finish")), None)
        return PENDING_DRAFT.format(tap=write) if write else \
            PENDING_WRITTEN.format(function=owner_said(self.folder, a))

    @holds_the_room
    def _finish_pending(self, a: str) -> None:
        """t482: the conflicts left open on `a` wait for their owner's answer from now on."""
        state = load_state(self.folder, a)
        ids = [c["id"] for c in self._left_open(a)]
        state[PENDING_ANSWERS] = [*(state.get(PENDING_ANSWERS) or []), *ids]
        save_state(self.folder, a, state)

    def _awaiting_reservation(self) -> str | None:
        """The activity whose walk waits for a reservation in his words, read off its run file
        (nemo's own waiting state: the last answer reserved something not named yet), else None."""
        a = self._activity
        if not a or a not in walk.processes(self.folder):
            return None
        run = walk.read_record(self.folder, walk.run_file(a)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        return a if walk._last_decision(run).get("naming") == walk.UNNAMED else None  # type: ignore[attr-defined]  # walk re-exports UNNAMED

    # the taps (13_nemo, t73) ─────────────────────────────────────────────────
    def _register(self, label: str, action: dict[str, Any]) -> str:
        # fix 1: the id is the message's as well as the call's, so the same call drawn on a later
        # message (answer_step(endorsed) at stages 1, 3, 4 and 5) never makes an old tap current
        aid = f"{self._message}.{tap_id(action)}"
        self._tap_ids[aid] = action
        self._tap_labels[label] = aid
        return aid

    def _draw(self, pairs: list[tuple[str, dict[str, Any]]]) -> list[str]:
        """Register the taps a turn renders; the skin sends each one's id back when it is tapped.
        t662: an old page tap as it is now (`current_tap`), under the graph's own words; none where
        it has nothing to open, or where the turn draws the graph already."""
        pairs = self._current(pairs)
        self._message += 1
        self._card_log = None  # t63: set again by the stage-3 cards drawn with these taps
        self.last_actions = [self._register(label, action) for label, action in pairs]
        self._last_taps = [{"label": label, **action} for label, action in pairs]
        self._picking = False
        self.last_pick = bool(pairs)  # every tap rendered is nemo's own
        # t418 r4: taps drawn for a line asking for names keep them (`shown`)
        self._taps_named = bool(words.NAMES_ASKED.search(self._turn_line))
        return [label for label, _ in pairs]

    def _current(self, pairs: list[tuple[str, dict[str, Any]]]
                 ) -> list[tuple[str, dict[str, Any]]]:
        """t662: the taps `_draw` draws, an old page tap as it is now (`current_tap`)."""
        drawn: list[tuple[str, dict[str, Any]]] = []
        for label, action in pairs:
            now = current_tap(self.folder, action)
            if now is action:
                drawn.append((label, action))
            elif now is not None and now not in [a for _, a in pairs + drawn]:
                drawn.append((DEPENDENCY_GRAPH_TAP, now))
        return drawn

    def _drawn_labels(self) -> list[str]:
        """t413: every tap label this turn drew, those a "… N more" tap holds too."""
        return [x for t in self._last_taps
                for x in [t["label"], *(label for label, _ in (
                    t.get("taps") or [] if t.get("kind") == "more" else []))]]

    def shown(self, label: str) -> str:
        """t96: a tap of the last turn as he reads it. The gradient's answers read in plain words
        (`TAP_WORDS`); the tap's call, its id and the value the record stores are the same. Any
        other tap reads as drawn (a risk-register row is worded where it is built, `_risk_taps`).
        t418 (ADR-0051): a person in it reads as their function ("Ask the Head of IT
        Operations")."""
        tap = next((t for t in self._last_taps if t["label"] == label), {})
        args = tap.get("args") or {}
        if tap.get("tool") == "answer_step" and args.get("answer") == label and label in TAP_WORDS:
            return TAP_WORDS[label]
        if tap and self._taps_named:
            return label  # t418 r4: his line asked for names, and the tap has them beside each
        return words.functions_only(label, self.folder, tap=True)  # t418: a person by function

    def _tap_lookup(self, label: str, action: str | None) -> dict[str, Any] | None:
        """The action a marked tap stands for: by its id, else by its label, and only a tap on the
        current message (`last_actions`). A tap left on an earlier message is stale (fix 1): its id
        can be the same call a later step would mean differently (answer_step(endorsed) is stage
        1's "Yes", stage 3/4's "endorsed" and stage 5's "Accept the handover"), so it is taken as
        an unmarked line of text and dispatches nothing."""
        aid = action if action else self._tap_labels.get(label)
        if not action and aid not in self.last_actions:
            # the label drawn last under another message; the one on this message, if any
            aid = next(
                (
                    i
                    for i, t in zip(self.last_actions, self._last_taps, strict=False)
                    if t["label"] == label
                ),
                None,
            )
        return self._tap_ids.get(aid) if aid in self.last_actions else None

    def _tap_turn(self, user_text: str, how: str, t0: float, tap: dict[str, Any],
                  asked: dict[str, Any] | None = None,
                  then_reason: bool = False) -> tuple[str, list[str], list[str]]:
        """A tap (or the typed value a "Change …" tap asked for): exactly one call, the tap's own,
        with the arguments fixed from data. The model then says what happened, with no tools, so
        nothing else can come of the tap (t73 item 3). A standing refusal ends the turn as
        always."""
        name, args = tap["tool"], dict(tap["args"])
        self.messages.append({"role": "user", "content": user_text})
        opened_before = self._flags(str(args.get("activity") or "")) if then_reason else None
        room = self._room_name(str(args.get("activity") or ""))
        wanted_before = self._rto_wanted(room, load_state(self.folder, room)) \
            if name == "decide" and room in walk.processes(self.folder) else None
        c0 = time.time()
        result, from_ledger = self.dispatch(name, args)
        tool_s = time.time() - c0
        refused = None
        if isinstance(result, dict) and (
            result.get("refusal") == STANDING or result.get("server_turn")
        ):
            refused = result = {
                **result,
                "tool": name,
                "from_ledger": from_ledger,
                "turn_ended": True,
            }
        self.log("tool", {"model": self.model, "name": name, "args": args, "result": result,
                          "tap": user_text, **({"asked": asked["prompt"]} if asked else {})})
        if refused:
            return self._refusal_turn(refused, how, t0, 0.0, tool_s, [name], tapped=True)
        if (rpo := self._rpo_asks(name, args, result)) is not None:
            # t93: he has set an RPO the dependency register disagrees with. nemo shows both and
            # asks which the record carries — his stands meanwhile, so nothing is lost if he walks
            # on. The reason question (t64) is not asked on this turn: one question at a time.
            keep = keep_figure_tap("rpo", rpo["value"])
            take = derived_figure_tap("rpo", rpo["derived"])
            self._register(keep, {"kind": "as_is"})
            self._register(take, tool_tap("decide", activity=args.get("activity"),
                                          item_id=args.get("item_id"), decision=DERIVED))
            return self._server_reply(
                user_text,
                how,
                t0,
                ASK_WHICH_CARRIES.format(
                    kind="RPO",
                    his=rpo["value"],
                    derived=rpo["derived"],
                    reason=", ".join(rpo["derived_reason"]) or "no named system",
                ),
                [keep, take],
                "rpo_choice",
                heard=True,
            )
        if name == "decide" and args.get("decision") == referee.KEEP and isinstance(result, dict) \
                and result.get("answer") == referee.KEEP and not result.get("refusal"):
            # t116: "Keep …, and say why": his answer is recorded, and nemo asks for his reason
            # through t64's reason ask; its Skip tap leaves it kept with no reason given
            ask = ASK_KEEP_REASON.format(value=result["asserted"])
            self._awaiting_reason = {
                "activity": args.get("activity"),
                "item_id": args.get("item_id"),
                "value": result["asserted"],
                "prompt": user_text,
                "ask": ask,
                "call": f"{name}({json.dumps(args, ensure_ascii=False)})",
                "result": json.dumps(result, default=str, ensure_ascii=False)[:6000],
                "tool_s": tool_s,
                "tapped": True,
            }
            self._register(words.NO_REASON_TAP, {"kind": "no_reason"})
            return self._server_reply(user_text, how, t0, ask, [words.NO_REASON_TAP], "ask_reason",
                                      heard=True)
        if wanted_before is not None and isinstance(result, dict) and not result.get("refusal") \
                and (new := [i for i in self._rto_wanted(room, load_state(self.folder, room))
                             if i not in wanted_before]):
            # t154: his act acknowledged a gap the method gives no RTO for, so nemo asks him for
            # it now, in plain words, and his next typed line is its value
            self._awaiting_value = self._rto_ask(room, new[0])
            return self._ask_reply(user_text, how, t0, self._awaiting_value, heard=True)
        if (
            then_reason
            and asked
            and isinstance(result, dict)
            and result.get("refusal") != WRONG_CALL
            and self._flags(str(args.get("activity") or "")) - (opened_before or set())
        ):
            # t64 (owner, 2026-09-18: "only when it opens a flag"): his figure is recorded and it
            # opened an item nemo carries open into the signature; nemo asks why, once
            ask = words.ASK_REASON.format(value=user_text.strip())
            self._awaiting_reason = {
                "activity": args.get("activity"),
                "item_id": args.get("item_id"),
                "value": user_text.strip(),
                "prompt": asked["prompt"],
                "ask": ask,
                "call": f"{name}({json.dumps(args, ensure_ascii=False)})",
                "result": json.dumps(result, default=str, ensure_ascii=False)[:6000],
                "tool_s": tool_s,
            }
            self._register(words.NO_REASON_TAP, {"kind": "no_reason"})
            return self._server_reply(user_text, how, t0, ask, [words.NO_REASON_TAP], "ask_reason",
                                      heard=True)
        if name == "decide" and args.get("decision") == UNRESOLVED and isinstance(result, dict) \
                and not result.get("refusal") and (pending := self._pending_taps(room)):
            # t482: the conflict he left open waits for its owner: code's line and its two taps,
            # never a push to close it (his 7 Oct rehearsal, 00:13)
            return self._pending_reply(user_text, how, t0, room, pending, PENDING_SAID)
        how_came = (
            f"typed {user_text.strip()!r} when nemo asked for it ({asked['prompt']})"
            if asked
            else f"tapped {self.shown(user_text)!r}"
        )
        card = self._card_now()
        note = (
            f"(nemo: the manager {how_came}. nemo made the one call that stands for, with its "
            f"arguments fixed from the room's data, and nothing else: {name}"
            f"({json.dumps(args, ensure_ascii=False)}) returned "
            f"{json.dumps(result, default=str, ensure_ascii=False)[:6000]}. Tell him in your own "
            "sentences what it did and what comes next. There are no tools this turn: nemo draws "
            "the taps under your message."
            + (
                f" nemo's taps and the card above them are about: {card}. Your question is about "
                "that card only; nemo prints its figures and quotes."
                if card
                else ""
            )
            + ")"
        )
        done = (f"Done: {user_text.strip()}." if not asked else
                f"Done: nemo recorded {user_text.strip()!r}, as you typed it.")
        return self._narrate(user_text, how, t0, tool_s, [name], note, done)

    def _rpo_asks(self, name: str, args: dict[str, Any], result: Any) -> dict[str, Any] | None:
        """t93: the RPO statement the record would carry, where his figure and the register's
        derivation disagree and he has just set it — else None.

        Read off the record's own path (`build_proposal`), the same one `_carried_after` takes, so
        the figures the question names are the figures the record carries. Nothing is read from the
        model's words, and the question is asked only after a decision of his on that very item.
        """
        if name != "decide" or not isinstance(result, dict) or result.get("refusal"):
            return None
        item_id = str(args.get("item_id") or "")
        if args.get("decision") != "change" or item_id.rsplit(".", 1)[-1] != "rpo":
            return None
        a = self._room_name(str(args.get("activity") or ""))
        state = load_state(self.folder, a)
        ids = [x["id"] for x in (state.get("draft") or {}).get("activities") or []]
        aid = item_id.split(".")[0]
        if aid not in ids:
            return None
        act = build_proposal(state["draft"], state, self._method(), self.folder)["activities"][
            ids.index(aid)
        ]
        rpo: dict[str, Any] = next((m for m in act["evidence_meta"] if m["label"] == "RPO"), {})
        return rpo if rpo.get("derived") else None

    def _flags(self, activity: str) -> set[str]:
        """t64: the items nemo would carry open into the signature now, by their words (their
        OPEN-n numbers shift as items come and go). Read from nemo's own check, never his words."""
        state = load_state(self.folder, activity)
        if not activity or not state.get("draft"):
            return set()
        opened = self._dry_run(activity, state, self._method())["open_at_the_signature"]
        return {re.sub(r"^Open item \([^)]*\): ", "", str(x), count=1) for x in opened}

    @staticmethod
    def _asks_reason(asked: dict[str, Any]) -> bool:
        """t64: a figure he typed after "Change …" (MTPD, RTO, RPO) is followed by nemo asking
        why."""
        kind = str((asked.get("args") or {}).get("item_id", "")).rsplit(".", 1)[-1]
        return (
            asked.get("tool") == "decide"
            and asked.get("field") == "value"
            and kind in ("mtpd", "rto", "rpo")
        )

    def _reason_turn(self, user_text: str, how: str, t0: float, pending: dict[str, Any],
                     reason: str | None) -> tuple[str, list[str], list[str]]:
        """t64: his reason for the figure he just typed, kept on his decision word for word (the
        record says it after "Set by the manager in chat:"), or none. Only while that decision is
        still his typed value: nothing else is written. The model then says what was recorded,
        with no tools, as after any tap."""
        a = str(pending["activity"] or "")
        with room_lock(self.folder):  # t238 (C7): read, change and save as one
            state = load_state(self.folder, a)
            d = (state.get("decisions") or {}).get(str(pending["item_id"]))
            his = bool(d and d.get("typed") and str(d.get("value")) == pending["value"])
            kept = bool(reason and reason.strip() and d
                        and (d.get("typed") or d.get("decision") == referee.KEEP)  # t116: his Keep
                        and str(d.get("value")) == pending["value"])
            if kept:
                # why: `kept` holds only with `d` and `reason` set
                d["reason"] = reason.strip()  # type: ignore[index, union-attr]
            # why: typeshed's getattr overloads; the default is a str, as `turn_id` is
            if his and getattr(self, "turn_id", ""):  # type: ignore[arg-type]
                # t171: the turn he gave his reason on (or tapped that he gives none): his words on
                # it are a row of the record beside the figure, checked against the turn file
                # why: `his` holds only with `d` set
                d["reason_turn_id"] = self.turn_id  # type: ignore[index]
            if kept or his:
                save_state(self.folder, a, state)
        if d and d.get("typed") and str(d.get("value")) == pending["value"]:
            # t116 (a): his typed figure IS his Keep of the grid question it opened, with his
            # reason or, after Skip, none (14_nemo_check: a decline is a pass)
            # why: `kept` holds only with `reason` set
            self._typed_reason_answers(a, str(pending["item_id"]), reason.strip() if kept else None)  # type: ignore[union-attr]
        self.log(
            "reason", {"activity": a, "item": pending["item_id"], "reason": reason, "kept": kept}
        )
        self.messages.append({"role": "user", "content": user_text})
        then = (
            # why: `kept` holds only with `reason` set
            f"he typed {reason.strip()!r} as his reason, which nemo keeps on the record beside the "  # type: ignore[union-attr]
            "figure, word for word"
            if kept
            else f"he tapped {words.NO_REASON_TAP!r}, so the record says no reason given"
        )
        came = (f"tapped {pending['prompt']!r}" if pending.get("tapped") else
                f"typed {pending['value']!r} when nemo asked for it ({pending['prompt']})")
        note = (
            f"(nemo: the manager {came}. nemo made the one call that stands for, with its "
            "arguments "
            f"fixed from the room's data, and nothing else: {pending['call']} returned "
            f"{pending['result']}. nemo then asked for his reason, and {then}. Tell him in your "
            "own sentences what was recorded and what comes next. There are no tools this turn: "
            "nemo draws the taps under your message.)"
        )
        done = (f"Done: nemo recorded {pending['value']!r}, "
                + ("as you kept it" if pending.get("tapped") else "as you typed it")
                + (", with your reason." if kept else ", with no reason given."))
        return self._narrate(
            user_text, how, t0, float(pending.get("tool_s") or 0.0), ["decide"], note, done
        )

    def _narrate(self, user_text: str, how: str, t0: float, tool_s: float, tools_called: list[str],
                 note: str, fallback: str,
                 tool_work: str | None = None) -> tuple[str, list[str], list[str]]:
        """After a tap's one action: the model says what happened, offered no tools. A tool call it
        returns anyway is not run, and the history says so; if it wrote nothing else, nemo's own
        one-line `fallback` is what the manager sees rather than an empty message (fix 1)."""
        if (changed := self._files_note()):  # t284: a tap turn's model call compares too
            self.messages.append({"role": "user", "content": changed})
        self.messages.append({"role": "user", "content": note})
        m0 = time.time()
        self._tools_now()  # t96: the prompt for where the conversation is; no tools
        reply = lanes.chat(self.model, self.messages, None, room=self.folder)
        model_s = time.time() - m0
        self.stats["calls"] += 1
        self.stats["tokens"] += int((reply.get("_usage") or {}).get("total_tokens") or 0)
        content = reply.get("content") or ""
        if not _drop_options(content)[0]:
            content = fallback + ("\n" + content if content.strip() else "")
        self.messages.append({"role": "assistant", "content": _drop_options(content)[0]})
        if reply.get("tool_calls"):  # offered no tools, so none is run (a tap is its one call)
            names = [c.get("function", {}).get("name") for c in reply["tool_calls"]]
            self.log("not_run", {"model": self.model, "tool_calls": reply["tool_calls"]})
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        f"(nemo: your call to {', '.join(map(str, names))} was not run: a tap's "
                        "turn has no "
                        "tools, and the tap already made its one call.)"
                    ),
                }
            )
        return self._finish({**reply, "content": content}, how, t0, model_s, tool_s, tools_called,
                            None, tool_work, (note, fallback))

    def _value_args(self, asked: dict[str, Any], line: str) -> dict[str, Any] | None:
        """The call's arguments with the manager's typed line in the one field it was asked for.
        Structural only: the value whole; a scope list split on `;` or new lines; scores as the
        digits 1–5 in horizon order. None when the line gives nothing that field can be."""
        line = line.strip()
        if not line:
            return None
        args = dict(asked["args"])
        if asked["field"] == "said":
            return {**args, "said": line}  # t76: his line as he typed it, nothing read out of it
        if asked["field"] == "value":
            kind = str(args.get("item_id", "")).rsplit(".", 1)[-1]
            if kind == "rpo" and RANGE.search(line):
                return None  # t71 fix 1: an RPO range is no point to recover to; asked again
            if kind in ("mtpd", "rto", "rpo") and not self._figure_word(kind, line):
                return None  # t71 fix 2b: not a figure of that kind; asked again, nothing recorded
            return {**args, "value": line}
        if asked["field"] == "activities":
            parts = [p.strip() for p in re.split(r"[;\n]", line) if p.strip()]
            return {**args, "activities": parts, "why": "typed by the manager when nemo asked"} \
                if parts else None
        horizons = asked.get("horizons") or []
        digits = re.findall(r"(?<![\d.])[1-5](?![\d.])", line)
        if len(digits) != len(horizons):
            return None
        return {**args, "scores": {h: int(d) for h, d in zip(horizons, digits, strict=False)}}

    def _figure_word(self, kind: str, line: str) -> bool:
        """t71 fix 2b: a typed figure is a duration, or one of the method's own words for that
        figure: an RPO from its vocabulary, an RTO from its rto_map or the recovery gap nemo's
        own tap records. Never a hand-kept list."""
        if kind == "rpo" and RANGE.search(line):
            return False  # fix 1: an RPO range is no point to recover to
        if duration.minutes(line) is not None:
            return True
        return any(" ".join(line.lower().split()) == " ".join(str(w).lower().split())
                   for w in self._figure_words(kind))

    def _figure_words(self, kind: str) -> list[str]:
        """The method's own words for a figure (fix 2b): the RPO vocabulary; the RTO's rto_map
        values and nemo's recovery-gap word; the MTPD's horizons. What nemo ACCEPTS: his tap
        records `GAP` on an RTO, so `GAP` stays here. What nemo SAYS is `_figure_says`."""
        method = self._method()
        return [str(w) for w in {"rpo": method.get(RPO_VOCABULARY) or [],
                                 "rto": [*(method.get("rto_map") or {}).values(), GAP],
                                 "mtpd": _mtpd_words(method)}[kind]]

    def _figure_says(self, kind: str) -> str:
        """t85: what nemo tells the caller to pass instead, when it won't take a figure.

        It never lists the recovery gap's own value. `GAP` is the acknowledgement itself, and a
        refusal that hands it back is nemo writing the finished claim into its own model's
        context — the same move `PROTOTYPE_draft`'s instruction and `_dry_run`'s `how_to_fix`
        made. Worse after t85: `how_to_fix` now tells the model a gap is a proposal until he
        takes it, so a model that then passes the proposed spelling would be refused here and
        told to write "(acknowledged)" — nemo's two words to its own model contradicting each
        other on the one point this ticket is about. So the RTO's refusal names his tap, and the
        acknowledgement stays an act of his (`_figure_words` still accepts it)."""
        words_ = [w for w in self._figure_words(kind) if not (kind == "rto" and is_gap(w))]
        return (
            f"give a duration, like '8 h', or one of the method's own words for it "
            f"({', '.join(words_) or 'none'})"
            + (
                f". A recovery gap is no figure to pass here: it is the manager's to "
                f"acknowledge, and nemo draws him the “{ACK_GAP}” tap."
                if kind == "rto"
                else ""
            )
        )

    def _kind_steps(self, changed: bool = False) -> list[tuple[str, dict[str, Any]]] | None:
        """t475 (S1): the next steps of a code-drawn answer, by its card kind (`KIND_STEPS`), each
        on the activity the answer is about; None for an answer of no mapped kind. `changed`: what
        changed, the analysis that drew this year's interview's changes block (`_changes_paths`),
        whose taps are ADR-0045's kinds where they draw any (t256, t317), these where none do."""
        kind, a, path = "" if changed else self._code_kind, self._about, None
        if changed and self._analysing and asks_what_changed(self._turn_line):
            read, on = self._changes_paths(), self._sheet_activity(self._turn_line)
            own = this_years_path(self.folder, on) if on else None  # the line's activity first
            path = own if own in read else next((p for p in read
                                                 for b in interview._named_in(self.folder / p)
                                                 if this_years_path(self.folder, b) == p), None)
            kind = CHANGED_KIND if path else ""
            a = on if path and path == own else next(
                (b for b in interview._named_in(self.folder / path)
                 if this_years_path(self.folder, b) == path), None) if path else None
        if kind not in KIND_STEPS or not a or a not in walk.processes(self.folder):
            return None
        return [t for step in KIND_STEPS[kind] if (t := self._kind_step(step, a, path))]

    def _stage_steps(self) -> list[tuple[str, dict[str, Any]]]:
        """t478: an answer whose kind has no `KIND_STEPS` entry, its stage's steps (`STAGE_STEPS`)
        on the activity it is about, each where its data holds; [] on none. One order (39_nemo_
        check's ruling, `_taps_now`): an open conflict's taps first (482's `_pending_taps`), then
        475's map, then this one, then ADR-0045's standing move."""
        a = self._about or self._next_step
        if self._code_kind in KIND_STEPS or not a or a not in walk.processes(self.folder):
            return []
        return [t for step in STAGE_STEPS[self._answer_stage()]
                if (t := self._kind_step(step, a, None))]

    def _answer_stage(self) -> int:
        """t478: the stage this answer is at: a code answer's, its sheet prompt's (`ANSWERED`,
        `STAGE_PROMPTS`); else the walk's card's in a walk; else an analysis's (A1), a write ask's
        (A8) or what he still checks (A9); else the walk's of the room's activity, else scope."""
        a = self._activity or self._thread
        on = a in walk.processes(self.folder)
        pid = ANSWERED.get(self._code_kind) or ANSWERED.get(self._server_set) or self._answered
        if not pid and self.walking and on:
            return self._walk_stage(a)  # type: ignore[arg-type]  # `on`: a is set
        pid = pid or "A1" * self._analysing or "A8" * self._asked_write or "A9" * bool(
            self._programme_turn and CHECK_WORDS.search(self._turn_line))
        if pid:
            return next(n for n, ids in STAGE_PROMPTS.items() if pid in ids)
        return self._walk_stage(a) if on else walk.STAGE  # type: ignore[arg-type]

    def _walk_stage(self, a: str) -> int:
        """t478: the stage of activity `a`'s card (`walk.current`); scope where its run does not
        read as a card (a hand-written record), so a label never costs him his answer."""
        try:
            return walk.current(self.folder, a).stage
        except (KeyError, OSError, ValueError, TypeError):
            return walk.STAGE

    def stage_line(self, text: str, cards: list[str], stage: int | None = None) -> str:
        """t478: the answer's stage label, the walk's own heading for it (`words.STAGES`), as a
        link to the stage map open on that stage; "" where the answer or a card says it already
        (a stage card opens on its heading). t533: `stage`, a replayed answer's, else this one's."""
        stage = self.answer_stage if stage is None else stage
        label = words.STAGES[stage]
        if any(label in said for said in [text, *cards]):
            return ""
        return f"[{label}{STAGE_OPENS}]({self.page_link(STAGE_MAP)}#stage-{stage})"

    def replayed(self, past: turn_file.Past) -> tuple[str, list[str],
                                                      list[tuple[list[str], list[str]]]]:
        """t533 (511): a turn of the room drawn again as he read it live: its reply and cards named
        (t107), the reply on the stage label it had (the turn's `answer_stage`; none on a line
        written before 478, nor on an empty reply, as live), and beside each card the charts the
        room kept for it (`shown`), drawn again by code from what they draw, wide and phone. t745: a
        led record's `cards` holds one chart per card, in its activities; the brake's `card` holds
        them all, the card's first, as live (499 r3); a record with neither stays undrawn."""
        reply, cards = self.drawn_turn(past.reply or "", past.cards)
        if reply and past.stage is not None and (
                stage := self.stage_line(reply, cards, past.stage)):
            reply = f"{stage}\n\n{reply}"
        charts: list[tuple[list[str], list[str]]] = [([], []) for _ in cards]
        for kept in shown.on_turn(self.folder, past.turn_id or ""):
            if kept.get("kind") != shown.CHART:
                continue
            args = kept.get("arguments") or {}
            acts = args.get("activities") or []
            held = dict(zip(kept["cards"], ([a] for a in acts), strict=False)) \
                if "cards" in kept else {kept.get("card", -1): acts[-1:] + acts[:-1]}
            for at, on in held.items():
                if on and 0 <= at < len(cards):
                    drawn = [activity_charts(self.folder, a, self._method(), args.get("classes"),
                                             args.get("years")) for a in on]
                    charts[at] = ([w for w, _ in drawn if w], [p for w, p in drawn if w])
        return reply, cards, charts

    def _kind_step(self, step: str, a: str, path: str | None
                   ) -> tuple[str, dict[str, Any]] | None:
        """t475: one step of `KIND_STEPS` on activity `a`, or None where its data does not hold."""
        if step == "start":
            return next_step_label(self.folder, a, *self._card()), tool_tap("get_step", activity=a)
        if step in ("brief", "who"):
            label, line = (BRIEF_TAP, BRIEF_LINE) if step == "brief" else (WHO_TAP, WHO_LINE)
            return label, {"kind": "meant", "line": line.format(activity=map_name(self.folder, a))}
        if step == "write":
            # as ADR-0045's kind 1 orders them (t317, t411): after code's table against last year
            # its findings, else a re-BIA reading or a mismatch code found, else the findings
            compared = self._code_kind == DEPENDENCY_KIND and YEARS_WORDS.search(self._turn_line)
            found = (finding_step(self.folder, [a]) if compared else None) or write_step(
                self.folder, self.model, self._turn_read, [a], self._turn_assets, a) \
                or finding_step(self.folder, [a])
            return (WRITE_TAP, {"kind": "write", **found}) if found else None
        if step == "chain":
            return CHAIN_TAP, page_tap(f"{LIVE_GRAPH}/{a}")
        if step == "compare":  # t478 r2: only where there is this year's interview to compare
            return (COMPARE_TAP, {"kind": "meant", "line": COMPARE_LINE.format(
                activity=map_name(self.folder, a))}) if last_year(self.folder, a)["found"] \
                and this_years_path(self.folder, a) else None
        who = _interviewee(self.folder, path) if path else ""  # "ask"
        return (ASK_INTERVIEWEE.format(function=words.people(self.folder).get(who, who)), {
            "kind": "refer", "activity": a, "resource": process_name(self.folder, a),
            "item": WRITE_COMPARED.format(activity=_said_name(self.folder, a)), "to": who}) \
            if who else None

    def _card(self) -> tuple[str, str]:
        """t516: what the answer says, for the start tap's label. r2: code's words (its answer, lead
        and check lines, the sheet and cards it drew), then the model's apart (the ask lane's
        guidance answer too)."""
        return "\n".join([self._code_said, self._lead_said, self._check_said,
                          self._sheet_text or "", *self.cards]), \
            "\n".join([self._card_said, self._guidance_text or ""])

    def _held(self, label: str, action: dict[str, Any]) -> str:
        """t516 r2: a tap drawn again under a new card (the chart's, "… N more") keeps its words,
        but a start tap's "its" no longer has its card: it reads in full."""
        if label in (NEXT_STEP_ITS, NEXT_STEP_SIGNED_ITS) and action.get("tool") == "get_step":
            return next_step_label(self.folder, action["args"]["activity"])
        return label

    def _produced(self) -> list[tuple[str, dict[str, Any]]]:
        """ADR-0045 kind 3 (t277), each only where its data exists now: 257's drafts while the
        follow-up list is not placed, 260's re-interview sheet for the activity the turn touched,
        and the graph stage 4 drew, where an activity the answer touched is on the register. t282:
        the chain in any room, where the answer read the register or his line named a resource
        on it; this turn draws the room's graph from its register where none is drawn yet."""
        a = self._next_step
        taps = [(DRAFTS_TAP, {"kind": "mailbox"})] if self.mailbox_offered() else []
        if a and last_year(self.folder, a)["found"]:
            taps.append((LAST_YEAR_TAP, page_tap(f"re-interview/{a}")))
        touched = [a] * bool(a) + [target["activity"] for _, target in self._referrals]
        early = walk.REGISTER in self._turn_read or bool(self._turn_assets)
        if early and len(taps) < EACH_KIND:
            draw_graph(self.folder)
        if graph_drawn(self.folder) and (early or any(in_register(self.folder, t)
                                                      for t in touched)):
            taps.append((CHAIN_TAP, page_tap(LIVE_GRAPH)))
        return taps

    def _on_room(self, turn: offer.Turn, on: str | None) -> offer.Turn:
        """t428 r2: the turn as the next step reads it in a room on `on`: an interview it read on
        another activity touches `on`, 428's rule for the write tap, never the other; what his
        line or a tool named, and an activity's run or documents read, count as before."""
        if on is None:
            return turn
        other = [p for p in turn.read if p.startswith(interview.HOMES)
                 and any(a != on for a in interview._named_in(self.folder / p))]
        return offer.Turn(tuple(p for p in turn.read if p not in other),
                          (*turn.named, on)) if other else turn

    def _taps_now(self, tools_called: list[str]) -> tuple[list[tuple[str, dict[str, Any]]], str]:
        """The taps for this turn, from data only, and which set they are."""
        a = self._activity
        # t482 (39_nemo_check's ruling, 2026-10-13), ONE ORDER for next steps: while a conflict he
        # left unresolved waits for its owner's answer, its two taps replace every other
        # (`_pending_taps`); else 475's card-kind map (`_kind_steps`); 478's stage map only for a
        # card kind with no entry
        if a and (pending := self._pending_taps(a)):
            return pending, PENDING_KIND
        shown =("list_activities" in tools_called and not self._analysing  # t377 D2b: refused
                 or bool(self._sheet_text))  # t96 fix 2 (95 a)
        for path in self._turn_read:
            for read in interview._named_in(self.folder / path) \
                    if path.startswith(interview.HOMES) else []:
                if discrepancies(self.folder, read):
                    self._found_in = read
        if not self.walking and not shown and self._code_said == NO_ACTIVITY_SAID:
            picker = self._pick_set(a)  # t504: it says none is chosen, so B2's pick
            self._asked_for = (self._turn_line, {  # t513: a pick here answers his ask
                label: tap["args"]["activity"] for label, tap in picker
                if tap.get("tool") == "get_step"})
            return picker, "pick"
        if not self.walking and not shown:
            # t96: free chat; no decision of his is open. ADR-0045 (t276): one to five next steps,
            # each a different move, in its order of kinds: the gaps the answer named (t256, t267),
            # the activity it touched (t108, t252), what nemo can produce (t277), else one
            # standing move. t282: kind 1 is nemo's own reading of the records too, after the
            # model's accepted proposals, one tap per gap, two in all. t317: first, nemo's one
            # "Write to an owner" after a comparison or a mismatch it found, inside those two
            turn = offer.Turn(tuple(self._turn_read), tuple(self._turn_named))
            room = next_step_room(self.folder, self.model)
            # t411: on the room's activity (395's `_room_activity`), never another process
            on = self._room_activity(self._turn_line)
            reads = self._turn_read
            if (day := named_day(self.folder, self._turn_line)) and (held := day_interviews(
                    self.folder, day)) and (card := next((
                        b for b in interview._named_in(self.folder / held[0])
                        if this_years_path(self.folder, b) == held[0]), None)):
                # t544 r5: a named day's card, the full taps of its activity, keyed to it: the
                # interviews the model read on other activities touch none of them (`_on_room`)
                on = card
                turn = self._on_room(turn, on)
                reads = list(turn.read)
            self._next_step = offer.next_step(self._on_room(turn, on), room)
            if (mapped := self._kind_steps()) is not None:  # t475: the answer's own steps,
                # after the referrals the model proposed on it (t256, t460: ADR-0045's kind 1)
                return [*self._additions, *self._referrals, *mapped][:NEXT_STEPS] or \
                    standing_tap(self.folder), "chat"
            touched = [t.name for t in offer.touched(turn, room)]
            gaps = [*self._referrals,
                    *late_gaps(self.folder, self.model, reads, touched,
                               self._turn_assets),
                    *deputy_gaps(self.folder, reads, touched)]
            first: dict[str, dict[str, Any]] = {}  # one tap per gap and per label, the first
            for label, target in gaps:
                if label not in first and gap_of(target) not in map(gap_of, first.values()):
                    first[label] = target
            # t411: after code's table against last year (390), that comparison's findings
            compared = self._code_kind == DEPENDENCY_KIND and YEARS_WORDS.search(self._turn_line)
            asked = self._asked_write or bool(PEOPLE_ASKED.search(self._turn_line))  # t475
            step = (finding_step(self.folder, [on]) if compared else None) \
                or write_step(self.folder, self.model, reads, touched,
                              self._turn_assets, on) \
                or asked and finding_step(  # t433 (A8): analysed or not
                    self.folder, [self._found_in, a, *self._owners_activity()])
            taps = [(WRITE_TAP, {"kind": "write", **step})] if step else []
            taps += [(label, {"kind": "refer", **target})
                     for label, target in list(first.items())[:EACH_KIND - len(taps)]]
            taps = [*self._additions, *taps]  # t318: his proposal first, what he asked for
            if self._next_step:
                taps.append((next_step_label(self.folder, self._next_step, *self._card()),
                             tool_tap("get_step", activity=self._next_step)))
            taps += self._produced()[:EACH_KIND]
            if START_ASKED.search(self._turn_line):  # t475: on his explicit ask only
                taps.append((START_BIA, tool_tap("list_activities")))
            # t475: what changed with none of these, its own steps; t478: else its stage's; else
            # ADR-0045 rule 4's standing move, the dependency graph (t636), never "Start a BIA"
            return (taps or self._kind_steps(changed=True) or self._stage_steps()
                    or standing_tap(self.folder))[:NEXT_STEPS], "chat"
        pick = shown or a is None or a not in walk.processes(self.folder)
        if pick:
            return self._pick_set(a), "pick"
        # why: `a` is set here: `pick` covers `a is None`
        closed = self._closed(a)  # type: ignore[arg-type]
        # t360: in a walk too, his one accepted proposal first, what he asked for, and the card's
        # taps after it unchanged; with no proposal every set is as it was
        # why: `a` is set here: `pick` covers `a is None`
        taps = [*self._additions, *self._step_taps(a)]  # type: ignore[arg-type]
        if closed:
            return taps, "signed"
        # t346: 317's one "Write to an owner" on a stage card too, by its own condition, after
        # the card's taps and never in place of one; the signed set (t67) stays as it is
        turn = offer.Turn(tuple(self._turn_read), tuple(self._turn_named))
        touched = [t.name for t in offer.touched(turn, next_step_room(self.folder, self.model))]
        step = write_step(self.folder, self.model, self._turn_read, touched, self._turn_assets) \
            or self._asked_write and finding_step(self.folder, [a, self._found_in])
        return taps + ([(WRITE_TAP, {"kind": "write", **step})] if step else []), "step"

    def _pick_set(self, a: str | None) -> list[tuple[str, dict[str, Any]]]:
        """B2's activity pick: his proposal first, one tap per activity read from the room (t312),
        "Another activity…", and 433's write tap only where his line asked to write. t504: the
        taps of an answer that says no activity is chosen, too: no chain, owner or 317 tap."""
        names = pick_taps(room_sheet(self.folder, self.model))
        picks = pick_entries(self.folder, names)  # t312
        self._picks.update(picks)
        found = self._asked_write and finding_step(  # t433 (A8): analysed or not
            self.folder, [self._found_in, a, *self._owners_activity()])
        return [*self._additions,
                *[(label, tool_tap("get_step", activity=n)) for label, n in picks],
                (ANOTHER, {"kind": "another"}),
                *([(WRITE_TAP, {"kind": "write", **found})] if found else [])]

    def tap_set(self, activity: str) -> list[str]:
        """nemo's tap set for this activity's step, as labels (what a turn about it renders)."""
        return [label for label, _ in self._step_taps(activity)]

    def _step_taps(self, a: str) -> list[tuple[str, dict[str, Any]]]:
        """Per step, the moves a tool can make now, each with its arguments from data (t73 item
        1)."""
        c = walk.current(self.folder, a)
        run = c.saved or {}
        if run.get("status") == walk.CLOSED:
            return [(AFTER_SIGNING[0], tool_tap("get_step", activity=a)),
                    (PICK_ANOTHER, tool_tap("list_activities"))]
        out: list[tuple[str, dict[str, Any]]] = []
        if walk._last_decision(run).get("naming") == walk.UNNAMED:  # type: ignore[attr-defined]  # walk re-exports UNNAMED
            pass  # nemo waits for the reservation in his words: nothing to tap
        elif c.stage == walk.STAGE:
            out = [
                (walk.AGREE, tool_tap("answer_step", activity=a, answer=walk.ENDORSED)),
                (
                    CHANGE_SCOPE,
                    ask_tap(
                        "set_scope",
                        {"activity": a},
                        "activities",
                        f"Which activities is the BIA for {a} about? Type them the way "
                        "they should stand in the BIA, one per line or separated "
                        "by “;”.",
                    ),
                ),
            ]
        elif c.stage == walk.STAGE_2:
            out = self._interview_taps(a, c)
        elif c.stage == walk.STAGE_3:
            out = self._evidence_taps(a, c)
        elif c.stage == walk.STAGE_4:
            # t76: and, where a gap he acknowledged stands, the one tap that closes it in his words
            out = ([(b, tool_tap("answer_step", activity=a, answer=b)) for b in c.buttons]
                   if c.buttons else self._refused_taps(a, c)) \
                + self._gap_close_taps(a, load_state(self.folder, a))
        elif c.stage == walk.STAGE_5:
            # the signature is never a tap: the card asks him to type it (owner's ruling)
            # t71b: the reserving route too, before the plain accept. Offered at every step 5 (step
            # 4 carries nemo's own four answers): whether he has a reservation pending could only
            # be read from his words, and nothing here reads them
            out = (
                []
                if run.get("status") == walk.REVIEWED
                else [
                    (walk.RESERVED, tool_tap("answer_step", activity=a, answer=walk.RESERVED)),
                    (ACCEPT_HANDOVER, tool_tap("answer_step", activity=a, answer=walk.ENDORSED)),
                ]
            ) + [(GO_BACK, tool_tap("reopen", activity=a))]
        return out + [(PICK_ANOTHER, tool_tap("list_activities"))]

    def _interview_taps(self, a: str, c: walk.Card) -> list[tuple[str, dict[str, Any]]]:
        """Stage 2: keep the offered interviews, or drop one (66's offer, one tap per interview).
        A drop is offered only where the rest still holds one filed under the department, which is
        what `confirm_interviews` binds; with nothing on file, 72's hold offer or its keep tap."""
        if not c.interviews:
            iv = self._interview
            if iv and iv["activity"] == a and iv["done"]:
                return [(KEEP_INTERVIEW, {"kind": "keep", "activity": a})]
            return [(HOLD_IT_NOW, {"kind": "hold", "activity": a})]
        draft = draft_for(a, self.model, self.folder)
        if not draft:
            return []
        offer = self._offer(a, draft, c)
        own = {i.path for i in c.interviews}

        # t64: "Drop Louven" on a phone, her interview's date only where she gave several, its
        # subject only where that date is shared too (347)
        droppable = [i for i in offer
                     if any(j["path"] in own for j in offer if j["path"] != i["path"])]
        # t528: a row the card folds as not about the activity (t377 G8) is not offered: no tap
        droppable = [i for i in droppable if not (excluded(i) and not i.get("own_department"))]
        drops = [(f"Drop {label}", tool_tap("confirm_interviews", activity=a, drop=[i["path"]]))
                 for label, i in zip(interview_labels(self.folder, droppable), droppable,
                                     strict=True)]
        kept = self._kept_these(a, offer, own)
        label = KEEP_THESE.format(n=len(kept[0])) if kept and len(kept[0]) > 1 else KEEP_THIS
        these = [(label, kept[1])] if kept else []
        # t528 r2 (15_nemo_design, 2026-10-19): no "Keep all <n>" tap; the keep tap is these
        return these + drops + self._risk_taps(a)

    def _kept_these(self, a: str, offer: list[dict[str, Any]],
                    own: set[str]) -> tuple[list[str], dict[str, Any]] | None:
        """t313 (a): the interviews the draft marks keep=true (its field, never its prose: M13) are
        one tap, where one of them is filed under the department `confirm_interviews` binds; since
        t528 r2 it is stage 2's only keep tap, so a draft that keeps the whole offer drops none.
        It drops ONLY what the draft marks keep=false: a file the draft never listed (this year's
        re-interview, 322) is kept and named (28_nemo_check's ruling, 2026-10-06). Their names, by
        `interview_labels`, and the tap's call; None where stage 2 draws no such tap."""
        kept = {i["path"] for i in kept_by_draft(offer)}
        dropped = {i["path"] for i in offer} - kept
        if not kept & own:
            return None
        return (interview_labels(self.folder, [i for i in offer if i["path"] in kept]),
                tool_tap("confirm_interviews", activity=a,
                         drop=[i["path"] for i in offer if i["path"] in dropped]))

    def _evidence_taps(self, a: str, c: walk.Card) -> list[tuple[str, dict[str, Any]]]:
        """Stage 3: the next open item's moves (conflicts first, then the clocks, then the scores),
        "Accept all open proposals" once only scores are left (`accept_all_open` refuses before),
        then the recovery gap the referee would refuse, then nemo's own buttons to close step 3."""
        state = load_state(self.folder, a)
        if not state.get("draft"):
            return []
        open_ = ordered_open(state)
        grid = [(SHOW_GRID, {"kind": "grid", "activity": a})]  # t63: nemo's own turn, no call
        if open_:
            out = self._item_taps(a, open_[0], state)
            if not self.must_see(state):
                out.append((ACCEPT_ALL, tool_tap("accept_all_open", activity=a)))
            if len(open_) > 1:
                # t77: the card to decide now is printed; the rest sit behind this one tap (t115:
                # one table of every open decision). nemo's own turn, no call, nothing decided
                out.append((SHOW_DECISIONS, {"kind": "all", "activity": a}))
            return out + grid
        if wanted := self._rto_wanted(a, state):
            # t154: the gap leaves the RTO for him to state; no answer closes step 3 until he has
            return self._rto_asks(a, state, wanted) + self._gap_close_taps(a, state) + \
                self._figure_changes(a, state) + grid
        gaps = [
            (ACK_GAP, tool_tap("decide", activity=a, item_id=i, decision="change", value=GAP), i)
            for i in self._gap_items(a, state, refused_only=True)
        ]
        # t116: while the referee's question is open its own taps stand where the step's answers
        # stood; the step's answers come back once he has answered it
        asked = self._question_taps(a)
        answers = (
            [] if asked else [(b, tool_tap("answer_step", activity=a, answer=b)) for b in c.buttons]
        )
        return (
            _unique(gaps)
            + self._gap_close_taps(a, state)
            + asked
            + self._figure_changes(a, state)
            + self._dependency_taps(a, state)
            + answers
            + grid
        )

    def _dependency_taps(self, a: str, state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """195: one "Add …" tap per dependency the model proposed and he has not added.

        Offered where the figures can still be changed — with nothing left open and step 3 not yet
        closed — and never as an open item: a proposal he says nothing about is not on his record,
        so nothing waits on it and the walk is not held up by one.
        """
        register, interviews = _room_facts(self.folder, state, _drafted_activity(state))
        return [tap for item in proposed_dependencies(state.get("draft") or {}, state, register,
                                                      interviews, self.folder)
                if not item["added"]
                for tap in self._item_taps(a, item, state)]

    def _figure_changes(self, a: str, state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """t71: with nothing left open, each clock can still be changed before step 3 closes: a
        "Change …" tap per figure, his next typed line its value (t73's ask). Once a conflict or an
        accepted proposal has settled a figure, there was no tap left to change it with, and the
        owner's own RPO decision on 2026-09-18 went through the model's words instead."""
        acts = (state.get("draft") or {}).get("activities") or []
        # t76: on an activity whose acknowledged gap stands, the RTO tap says so: changing the
        # target is not what closes a gap, and 73b's rule is that a tap names what it will do
        return [
            (
                f"Change {kind}"
                + (f" · {x['name']}" if len(acts) > 1 else "")
                + (GAP_STAYS if kind == "RTO" and gap_stands(state, x["id"]) else ""),
                ask_tap(
                    "decide",
                    {"activity": a, "item_id": f"{x['id']}.{kind.lower()}", "decision": "change"},
                    "value",
                    f"Type the {kind} for {a} as it should stand in the record."
                    + (
                        " The recovery gap you acknowledged stays until you record that the "
                        "arrangements can meet the target."
                        if kind == "RTO" and gap_stands(state, x["id"])
                        else ""
                    ),
                ),
            )
            for x in acts
            for kind in ("MTPD", "RTO", "RPO")
        ]

    def _item_taps(
        self, a: str, item: dict[str, Any], state: dict[str, Any]
    ) -> list[tuple[str, dict[str, Any]]]:
        """One open item's taps. A tap that names a value (a figure, a side's figure, a score set)
        names the value the record will carry once it is taken, read off the record's own path with
        that one decision applied (`_carried_after`), never off the draft item (t73b: on seed 2727
        "Accept RPO 24 h" recorded the register's 4 h). Where that differs from what the draft or
        the side proposed, the label says so, from data. Each such tap carries `names`: what it
        named, so a check can hold the room's files to it after the tap."""
        iid, kind = item["id"], item["type"]
        if kind == DEP:
            # 195: one tap, and it adds. The card beside it says it is a proposal and where it
            # came from (t63's "Short + card"), so the label stays the thing it does.
            now = state or load_state(self.folder, a)
            register, _ = _room_facts(self.folder, now, _drafted_activity(now))
            return [(ADD_DEP_TAP.format(name=dep_name(register, dep_asset(iid))),
                     {**tool_tap("decide", activity=a, item_id=iid, decision="accept"),
                      "names": {"item": iid, "activity_id": iid.split(".")[0],
                                "dependency": dep_asset(iid)}})]
        if kind == "conflict":
            # t63 (owner's "Short + card", 2026-09-18): the tap is short; what it names sits on the
            # conflict's card, from the same entries, so one source still holds
            # t76: and the third choice, which takes no side and names no value (the owner's
            # ruling, 2026-09-19): the record carries it as open, referred to the activity's owner
            # (t84r)
            return [(e["label"], {**tool_tap("decide", activity=a, item_id=iid, decision="accept",
                                             side=e["side"]), "names": e["names"]})
                    for e in self._side_entries(a, item, state)] + \
                [(UNRESOLVED_TAP, tool_tap("decide", activity=a, item_id=iid, decision=UNRESOLVED))]
        aid = iid.split(".")[0]
        if kind in ("MTPD", "RTO", "RPO"):
            value = str(item.get("value"))
            accept = tool_tap("decide", activity=a, item_id=iid, decision="accept")
            if kind == "RTO" and "gap" in value.lower():
                first = (
                    ACK_GAP,
                    {
                        **accept,
                        "names": {"item": iid, "activity_id": aid, "field": kind, "gap": True},
                    },
                )
            else:
                meta, _, _ = self._carried_after(state, aid, iid, decision="accept")
                carried = (meta.get(kind) or {}).get("value")
                if kind == "RPO" and carried is None and no_rpo({"evidence": list(meta.values())}):
                    label = f"Accept {NO_RPO}, not {value}"  # 190: the record will carry none
                elif carried is None or str(carried) == value:
                    label = f"Accept {kind} {value}"
                else:
                    label = f"Accept {kind} {carried}, {_WHY_SHORT[_why(kind, meta)]}, not {value}"
                first = (
                    label,
                    {
                        **accept,
                        **(
                            {
                                "names": {
                                    "item": iid,
                                    "activity_id": aid,
                                    "field": kind,
                                    "value": carried,
                                }
                            }
                            if carried is not None
                            else {}
                        ),
                    },
                )
            return [first, (f"Change {kind}", ask_tap(
                "decide", {"activity": a, "item_id": iid, "decision": "change"}, "value",
                f"Type the {kind} for {a} as it should stand in the record."))]
        lens = item.get("lens")
        _, grid, _ = self._carried_after(state, aid, iid, decision="accept")
        # why: a score item always carries its lens (known_items, _proposal)
        scores = grid.get(lens) or item.get("scores") or {}  # type: ignore[arg-type]
        shown = " · ".join(str(v) if isinstance(v, int) else "–" for v in scores.values())
        horizons = list(item.get("scores") or scores)
        # why: a score item always carries its lens (known_items, _proposal)
        name = self._category(lens)  # type: ignore[arg-type]  # t64: the room's method.json name, never the id
        return [(f"Accept {name} scores ({shown})",
                 {**tool_tap("decide", activity=a, item_id=iid, decision="accept"),
                  "names": {"item": iid, "activity_id": aid, "lens": lens, "scores": scores}}),
                (f"Change {name} scores", ask_tap(
                    "decide", {"activity": a, "item_id": iid, "decision": "change"}, "scores",
                    f"Type the {name} scores for {a}: one number from 1 to 5 per "
                    f"horizon, in this order: {', '.join(horizons)}.", horizons))]

    def _side_entries(
        self, a: str, item: dict[str, Any], state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """t63: each side of an open conflict as its tap and its card entry carry it: the short tap
        label ("Dohm – side 1"), the speaker, quote, file and claim as drafted, what taking it makes
        the record carry (`effect`, in words) and `names`, the value a check holds the files to.
        Read off the record's own path with that one decision applied (`_carried_after`, t73b):
        a side that implies a figure names the figure the record will carry once it is taken, and
        says so where that differs from what the side proposed."""
        iid = item["id"]
        sides = item.get("sides") or []
        rule = iid.endswith("-MTPD-RULE")
        names_ = words.Names(self.folder)
        # t73b fix 2/2b: every side implying one and the same value on one figure, said so
        claims = [(str(s["implies"].get("item_id")), str(s["implies"].get("value")))
                  if isinstance(s.get("implies"), dict) and s["implies"].get("item_id")
                  and s["implies"].get("value") else None for s in sides]
        same = claims[0][1] if len(sides) > 1 and claims[0] and len(set(claims)) == 1 else None
        held = words.people(self.folder)
        named = bool(words.NAMES_ASKED.search(self._turn_line))
        out = []
        for n, side in enumerate(sides):
            implied = side.get("implies")
            value = implied.get("value") if isinstance(implied, dict) else None
            field, aid = ((str(implied["item_id"]).rsplit(".", 1)[-1].upper(),
                           str(implied["item_id"]).split(".")[0])
                          if value and implied.get("item_id") else (None, None))
            grid_line, stated = "", ""
            if rule and not value:  # the method's figure and the draft's, read from data
                value = self._rule_values(state, iid)[n] if n < 2 else None
                field, aid = ("MTPD", iid.split("-")[0]) if value else (None, None)
                if n == 1 and value:
                    grid_line, stated = self._evidence_quote(state, str(aid), value)
            names: dict[str, Any] = {"item": iid, "side": n}
            effect = "no figure moves: this side names none"
            figure: str | None = None  # t477: what its tap names beside who said it
            if field and field.lower() not in ("mtpd", "rto", "rpo"):
                # t73b fix 1: a side implying a score row names the row the record will carry
                lens = str(implied["item_id"]).rsplit(".", 1)[-1]
                # why: `aid` is set whenever `field` is
                _, grid, _ = self._carried_after(state, aid, iid, decision="accept", side=n)  # type: ignore[arg-type]
                row = grid.get(lens)
                effect = "no score moves: the row this side names is not one the method scores"
                if row:
                    moved = _implied_row(state["draft"], implied) == row
                    shown = " · ".join(str(v) if isinstance(v, int) else "–" for v in row.values())
                    effect = (
                        f"{self._category(lens)} scores {'become' if moved else 'stay'} {shown}"
                    )
                    names.update(activity_id=aid, lens=lens, scores=row)
            elif field and "gap" in str(value).lower():
                # the record flags the gap, as the decision this conflict writes on the RTO item;
                # fix 1: the target it carries then, read off the record's own path like any side
                # why: `aid` is set whenever `field` is
                meta, _, _ = self._carried_after(state, aid, iid, decision="accept", side=n)  # type: ignore[arg-type]
                carried = (meta.get(field) or {}).get("value")
                # t85: nothing is acknowledged until he takes it, so the card says what taking it
                # would do, never that it is done
                effect = (
                    f"{field} {carried} (recovery gap)" if carried else f"{field}: a recovery gap"
                ) + ", which taking this side acknowledges, carried as the method's target"
                figure = GAP_SIDE
                names.update(
                    activity_id=aid, field=field, gap=True, figure_item=str(implied["item_id"])
                )
            elif value and field:
                # why: `aid` is set whenever `field` is
                meta, _, kept = self._carried_after(state, aid, iid, decision="accept", side=n)  # type: ignore[arg-type]
                carried = (meta.get(field) or {}).get("value")
                his = (
                    explicit_change(
                        (state.get("decisions") or {}).get(str((implied or {}).get("item_id")))
                    )
                    or {}
                ).get("value")
                if carried is None or str(carried) == str(value):
                    effect = f"{field} {value}" + (
                        f" ({'both' if len(sides) == 2 else f'all {len(sides)}'} sides say {value})"
                        if same else "")
                    if grid_line:
                        # t369 r3 GUARD: the figure is the evidence side he took, so the tap shows
                        # that side's line beside it; the side's own quote states another figure
                        effect += f" from the line you took, “{grid_line}”; this side says {stated}"
                elif kept and his == kept:
                    effect = f"{field} stays your {carried}; this side says {value}"
                elif kept:
                    effect = f"{field} stays {carried}, tighter than this side's {value}"
                else:
                    effect = (f"{field} {carried}, {_WHY_SHORT[_why(field, meta)]}; this side "
                              f"says {value}")
                # t477: what the side says, whatever the record carries ("no MTPD within …" as is)
                figure = str(value) if field.lower() in str(value).lower() else f"{field} {value}"
                figure = unit_kept(figure)
                if carried is not None:
                    names.update(activity_id=aid, field=field, value=carried)
            who = _who(side.get("speaker"))
            # t418 r4 (ADR-0051): a side by its speaker's function, never the surname; two sides of
            # one function by the number alone; the name beside it only when his line asks for it
            function = held.get(re.sub(r"^(?:Dr|Prof)\.? ", "", who))
            short = (
                COMPANY_METHOD if who == "method" else function or _surname(who)
            )  # t65 fix 1: as the card names it
            if function and named:
                short = f"{function} ({who})"
            if short and who != "method" and not _names_a_person(who) and not names_.role(who):
                # t96 (8_nemo_check's note): a side whose speaker names no person, such as a note
                # captured in an interview, is not labelled by its reporter as if it were a person
                # holding the position, and no person is made up for it: it is said plainly
                short = NOTES_SIDE
            grid_read = bool(figure) and who != "method" and figure != GAP_SIDE \
                and bool(re.search(r"\bmethod", str(side.get("claim") or ""))) \
                and "Impact " in str(side.get("quote") or "")
            figure_said = re.sub("[<>] ?", lambda m: SAID_BOUNDS[m[0][0]], figure or "")
            # t478 r2 (14_nemo_design's nit on 482 r2): a stated side's tap says '>' as the
            # sentence does; a grid side's figure is the method's reading, kept as it is
            said = (SIDE_GRID.format(who=short or UNNAMED_SIDE, figure=figure) if grid_read
                    else SIDE_SAYS.format(who=short or UNNAMED_SIDE, figure=figure_said)
                    if figure else SIDE_VIEW.format(who=short or UNNAMED_SIDE))
            by = (_lower_first(COMPANY_METHOD) if who == "method"
                  else (SAID_GRID if grid_read else SAID_STATED).format(function=function)
                  if function else short or UNNAMED_SIDE)
            out.append(
                {
                    "side": n,
                    "label": said if named or not short else words.functions_only(
                        said, self.folder, tap=True),
                    "speaker": str(side.get("speaker") or ""),
                    "quote": str(side.get("quote") or ""),
                    "path": str(side.get("path") or ""),
                    "claim": str(side.get("claim") or ""),
                    "effect": effect,
                    "names": names,
                    # t482 r2: as nemo's line on the open conflict says it, its field apart
                    "said": SIDE_SAID.format(figure=figure_said, by=by) if figure else "",
                    "field": field if figure and figure != GAP_SIDE else None,
                }
            )
        # t477: two sides drawn alike (one function, one figure) are told apart in brackets
        labels = [e["label"] for e in out]
        for k, e in enumerate(out):
            if labels.count(e["label"]) > 1:
                e["label"] = f"{e['label']} ({k + 1})"
        return out

    def _unresolved_effect(self, a: str, item: dict[str, Any], state: dict[str, Any]) -> str:
        """t76: what leaving this conflict unresolved makes the record carry, in words: open, with
        the figure it carries meanwhile — the one it carries now, since no side is taken — and
        whether that is the cautious assumption, then referred to the activity's owner in the
        record's own sentence (t84r). Read off the record's own path (`_carried_after` with no
        decision), never off the draft."""
        figure, values = side_values(item)
        said = "The record keeps it open"  # r2: 14_nemo_design's words, a sentence of its own
        referral = ". " + referred_to(state.get("draft") or {}, self.folder)
        if not figure:
            return said + "; no figure moves" + referral
        aid, field = figure.split(".")[0], figure.rsplit(".", 1)[-1].upper()
        meta, _, _ = self._carried_after(state, aid, item["id"], decision=UNRESOLVED)
        carried = (meta.get(field) or {}).get("value")
        if carried is None:
            return said + f"; {field} stays as it is" + referral
        return (
            said
            + f"; {field} stays {carried}"
            + (
                ", an assumption while unresolved and not a resolution"
                if cautious(carried, values)
                else ""
            )
            + referral
        )

    def _category(self, lens: str) -> str:
        """An impact category by the name in the room's method.json, the id where it has none."""
        return next((c["name"] for c in self._method().get("scenarios") or []
                     if c.get("id") == lens and c.get("name")), lens)

    def _carried_after(self, state: dict[str, Any], aid: str, item_id: str,
                       **decision: Any) -> tuple[dict[str, Any], dict[str, Any], Any]:
        """What the record will carry for draft activity `aid` once this one decision is taken:
        (its statements by label, its impact grid, the figure a looser side left standing or
        None). The same path the record takes: `_apply` on a copy of the state, then
        `build_proposal`, which derives the RPO from the register and carries a gap (t73b)."""
        trial = json.loads(json.dumps(state, default=str))
        self._apply(trial, item_id, **decision)
        proposal = build_proposal(trial["draft"], trial, self._method(), self.folder)
        ids = [x["id"] for x in trial["draft"].get("activities") or []]
        if aid not in ids:
            return {}, {}, None
        act = proposal["activities"][ids.index(aid)]
        return ({m["label"]: m for m in act["evidence_meta"]}, act["impact_grid"],
                trial["decisions"][item_id].get("kept"))

    @staticmethod
    def _evidence_quote(state: dict[str, Any], aid: str, value: str) -> tuple[str, str]:
        """t369 r3: where the rule's side 1 carries a figure an evidence side he took set (C1's
        grid line, not the draft's stated MTPD), that side's quote and the draft's stated MTPD;
        ("", "") where no evidence side sets `value`."""
        draft, decisions = state["draft"], state.get("decisions") or {}
        act: dict[str, Any] = next((x for x in draft.get("activities") or [] if x["id"] == aid), {})
        stated = str((act.get("mtpd") or {}).get("value") or "")
        figure, by = evidence_tightened(draft, decisions, aid, stated)
        if by is None or str(figure) != str(value):
            return "", ""
        sides = next(c for c in draft["conflicts"] if c["id"] == by).get("sides") or []
        side = decisions[by].get("side")
        return str(sides[side].get("quote") or ""), stated

    def _rule_values(self, state: dict[str, Any], iid: str) -> list[str | None]:
        """A method-rule conflict's two figures: the method's MTPD over the grid, the draft's
        MTPD."""
        acts = effective(state["draft"], state.get("decisions", {}), self._method())
        a = next(
            (x for x in acts if f"{x['id']}-MTPD-RULE" == iid), acts[0] if len(acts) == 1 else None
        )
        if a is None:
            return [None, None]
        # fix 3: each side names the MTPD the record carries once it is taken (side 1 after his
        # typed change is the draft's own, with the evidence sides applied), never his figure
        return [(self._carried_after(state, a["id"], iid, decision="accept", side=n)[0].get("MTPD")
                 or {}).get("value") for n in (0, 1)]

    def _gap_items(self, a: str, state: dict[str, Any], refused_only: bool = False) -> list[str]:
        """The RTO items a recovery-gap acknowledgement goes on: each activity with no gap decided.
        With `refused_only`, only when nemo's referee would refuse the record for the gap now."""
        draft = state.get("draft") or {}
        if refused_only:
            check = self._dry_run(a, state, self._method())
            if not any(r.kind == nemo_refusal.TARGET_OUTSIDE_MTPD for r in check["would_refuse"]):
                return []
        # t76: the gap he acknowledged stands whatever target he typed since, so there is none to
        # acknowledge again until he closes it
        return [f"{x['id']}.rto" for x in draft.get("activities") or []
                if not gap_stands(state, x["id"])]

    def _gap_close_taps(self, a: str, state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """t76: the one tap that closes an acknowledged gap, per activity whose gap stands. It asks
        for his words; his next typed line is what nemo records, and the gap closes on it. Fix 2:
        none where the call would refuse (`_gap_close_waits`), so the tap and the move agree."""
        if self._gap_close_waits(a) is not None:
            return []
        acts = (state.get("draft") or {}).get("activities") or []
        return [(GAP_CLOSE_TAP + (f" · {x['name']}" if len(acts) > 1 else ""),
                 ask_tap("close_recovery_gap", {"activity": a, "item_id": f"{x['id']}.rto"}, "said",
                         ASK_GAP_WORDS.format(activity=a)))
                for x in acts if gap_stands(state, x["id"])]

    def _rto_wanted(self, a: str, state: dict[str, Any]) -> list[str]:
        """t154: the RTO items a decision of his has left on the recovery gap's word under a method
        with no rto_map. The record would name no RTO for them, and the referee refuses that
        (`no_recovery_target`); nemo derives none (13_nemo_check's t139 ruling (1)), so he states
        it. A gap only the draft proposes is still an open item, which step 3 holds open anyway.
        With an rto_map, none: the map gives the gap's RTO, as it always did."""
        method = self._method()
        draft = state.get("draft") or {}
        decisions = state.get("decisions") or {}
        if method.get("rto_map") or not draft.get("activities"):
            return []
        return [f"{x['id']}.rto" for x in effective(draft, decisions, method)
                if f"{x['id']}.rto" in decisions and is_gap((x.get("rto_now") or {}).get("value"))]

    @staticmethod
    def _rto_ask(a: str, item_id: str) -> dict[str, Any]:
        """t154: the question for the RTO a gap left open; his next typed line is its value."""
        return ask_tap("decide", {"activity": a, "item_id": item_id, "decision": "change"}, "value",
                       ASK_GAP_RTO.format(activity=a))

    def _rto_asks(
        self, a: str, state: dict[str, Any], wanted: list[str]
    ) -> list[tuple[str, dict[str, Any]]]:
        """t154: one "State the RTO" tap per activity whose gap left its RTO for him to state."""
        acts = {x["id"]: x for x in (state.get("draft") or {}).get("activities") or []}
        return [(STATE_RTO + (f" · {acts[i.split('.')[0]]['name']}" if len(acts) > 1 else ""),
                 self._rto_ask(a, i)) for i in wanted]

    def _refused_taps(self, a: str, c: walk.Card) -> list[tuple[str, dict[str, Any]]]:
        """Stage 4 with the referee refusing: the refusal's own `next`, each as its one call."""
        return [(label, self._named_tap(label, a)) for label in self._referee_refuses(a, c)["next"]]

    def _named_tap(self, label: str, a: str | None, item: str | None = None) -> dict[str, Any]:
        """The one call each of nemo's fixed labels (a standing refusal's `next`) stands for.
        `item` is the item the refusal was drawn for (fix 4): a slot is read only for that item."""
        # t80/t83: the taps a refused model act becomes, from what nemo stored when it refused —
        # the item and the figure, never the label's own words. fix 4 (review 4, claim 2): keyed
        # on the item, so a slot left by another item's refusal can never answer for a label
        if (f := self._chat_figure) and f["item_id"] == item \
                and label in (f["confirm"], change_figure_tap(f["kind"])):
            if label == f["confirm"]:
                return tool_tap("decide", activity=f["activity"], item_id=f["item_id"],
                                decision="change", value=f["value"])
            return ask_tap("decide", {"activity": f["activity"], "item_id": f["item_id"],
                                      "decision": "change"}, "value",
                           f"Type the {f['kind'].upper()} for {f['activity']} as it should stand "
                           "in the record.")
        if (c := self._chat_proposal) and c["item_id"] == item and label in c["taps"]:
            # why: the proposal's taps are tool-tap dicts
            return c["taps"][label]  # type: ignore[no-any-return]
        if (g := self._chat_signature) and g["activity"] == a and label in g["taps"]:
            # why: the signature's taps are tool-tap dicts
            return g["taps"][label]  # type: ignore[no-any-return]
        if (r := self._chat_referral) and r["item_id"] == item and label == UNRESOLVED_TAP:
            return tool_tap("decide", activity=r["activity"], item_id=r["item_id"],
                            decision=UNRESOLVED)
        if label == PICK_ANOTHER or not a:
            return tool_tap("list_activities")
        if label == AFTER_SIGNING[0] or label.startswith("Carry on with step"):
            return tool_tap("get_step", activity=a)
        if label in (ACCEPT_HANDOVER, "Accept the record"):
            return tool_tap("answer_step", activity=a, answer=walk.ENDORSED)
        if label == ACCEPT_ALL:  # fix 4 (review 4, claim 5): t94's refusal, drawn through the turn
            return tool_tap("accept_all_open", activity=a)
        if label == walk.ENDORSED:  # fix 4 (ruling 3): the card's own answer, as his tap
            return tool_tap("answer_step", activity=a, answer=walk.ENDORSED)
        if label == GO_BACK:
            return tool_tap("reopen", activity=a)
        for drawn, action in self._question_taps(a):  # t116: the open question's own answers
            if label == drawn:
                return action
        state = load_state(self.folder, a)
        item = next(iter(self._gap_items(a, state)), None) or \
            next((f"{x['id']}.rto" for x in (state.get("draft") or {}).get("activities") or []), "")
        if label == ACK_GAP:
            return tool_tap("decide", activity=a, item_id=item, decision="change", value=GAP)
        if label == STATE_RTO:  # t154: the RTO a gap left for him to state
            return self._rto_ask(a, next(iter(self._rto_wanted(a, state)), item))
        if label == CHANGE_FIGURE:
            return ask_tap(
                "decide",
                {"activity": a, "item_id": item, "decision": "change"},
                "value",
                f"Type the RTO for {a} as it should stand in the record.",
            )
        raise KeyError(
            f"no call for the label {label!r}"
        )  # a label nemo drew with no call behind it

    def _card_now(self) -> str | None:
        """t63 fix 1: the name of the card nemo's stage-3 taps are about now, else None."""
        a = self._activity
        if (
            not a
            or a not in walk.processes(self.folder)
            or walk.current(self.folder, a).stage != walk.STAGE_3
        ):
            return None
        return (self._taps_about(a) or {}).get("card")

    def _unnamed(self, item: dict[str, Any]) -> str:
        """t63 fix 1 (a): an item the room's files give no name, said from its own data, never by
        id."""
        what = {
            "conflict": "a conflict",
            "score": f"{self._category(str(item.get('lens')))} scores",
        }.get(item["type"], f"a proposed {item['type']}")
        return f"{what} (the room's files give it no name)"

    def _taps_about(self, a: str) -> dict[str, Any] | None:
        """The open item nemo's taps are about now (stage 3), as data for the model's sentence."""
        open_ = ordered_open(load_state(self.folder, a))
        if not open_:
            asked = self._question(
                a
            )  # t116: the referee's open question is what the taps are about
            return {"card": "the open question on the MTPD", "id": asked[0], "type": "question",
                    "asserted": asked[1].asserted, "derived": asked[1].derived} if asked else None
        i = open_[0]
        # t63 fix 1: the card nemo's taps are about, by the name its card carries. t117: it is the
        # live item, marked as every lookup marks it
        return {"card": words.Names(self.folder, a, self.model).item(i["id"]) or self._unnamed(i),
                **{k: i.get(k) for k in ("id", "type", "about", "lens", "value", "scores", "sides",
                                         "recommend", "why") if i.get(k) is not None}, "live": True}

    # stage 3 as a grid and cards (t63) ───────────────────────────────────────────────────────
    def grid_card(self, activity: str) -> str:
        """The impact grid as the record stands now (t63), as nemo prints it."""
        return self._grid_card(
            self._room_name(activity), load_state(self.folder, self._room_name(activity))
        )[0]

    def _grid_card(self, a: str, state: dict[str, Any]) -> tuple[str, str]:
        """(the grid card, what it carries as data). Categories down in the method's order and by
        its names, horizons across as the method lists them, each cell the score the record would
        carry now (`build_proposal`, the record's own path); a row still open marked a proposal.
        Under it: MTPD, RTO and RPO as the record would carry them, the words the MTPD rests on,
        the settled account beside a figure he typed after it, and how many decisions are open."""
        draft = state.get("draft") or {"activities": []}
        method = self._method()
        proposal = build_proposal(draft, state, method, self.folder)
        hors = [str(h) for h in method.get("time_horizons") or []]
        cats = [
            (c["id"], c.get("name") or c["id"])
            for c in method.get("scenarios") or []
            if c.get("id")
        ]
        open_ = open_items(state)
        rows_open = {i["id"] for i in open_ if i["type"] == "score"}
        names = words.Names(self.folder, a, self.model)
        decisions = state.get("decisions") or {}
        acts = draft.get("activities") or []
        lines, carried = [f"{GRID_HEADING} · {a}**", ""], []
        for d, act in zip(acts, proposal["activities"], strict=False):
            if len(acts) > 1:
                lines += [f"**{act['name']}**", ""]
            lines += ["| | " + " | ".join(hors) + " |", "|---" * (len(hors) + 1) + "|"]
            rows = {cid: (act.get("impact_grid") or {}).get(cid) or {} for cid, _ in cats}
            for cid, cname in cats:
                row = rows[cid]
                mark = f" {PROPOSED_MARK}" if f"{d['id']}.{cid}" in rows_open else ""
                lines.append(f"| {cname}{mark} | " + " | ".join(
                    str(row[h]) if isinstance(row.get(h), int) else "–" for h in hors) + " |")
            # t376 (ADR-0050): a band "–" in every category is said, never left to read as blank.
            unrated = unrated_bands(rows, hors)
            if unrated:
                lines += ["", f"{', '.join(unrated)}: {NOT_RATED}"]
            meta = {m["label"]: m for m in act.get("evidence_meta") or []}
            figures = [
                (
                    label,
                    (meta.get(label) or {}).get("value"),
                    bool((meta.get(label) or {}).get("gap")),
                )
                for label in ("MTPD", "RTO", "RPO")
            ]
            # t85: this line is the manager's own screen. A recovery gap he has not acknowledged
            # is a proposal, and says so in the same word the score rows above already use, so
            # the card never states a gap that stands while `recovery_gaps` is empty.
            stands = gap_stands(state, d["id"])
            none = no_rpo({"evidence": list(meta.values())})
            lines += ["", " · ".join(NO_RPO if label == "RPO" and none and not value
                                     else self._grid_figure(label, value, gap, stands)
                                     for label, value, gap in figures), ""]
            lines += self._rests_on(names, draft, decisions, d["id"], meta.get("MTPD") or {})
            lines += self._settled_accounts(names, draft, decisions, d["id"], meta)
            lines += self._dependency_lines(state, act, d["id"])
            carried.append([act.get("impact_grid"), figures])
        kinds = [i["type"] == "conflict" for i in open_]
        lines += [
            f"**{len(open_)} decision{'s' if len(open_) != 1 else ''} still open**"
            + (
                f" · {sum(kinds)} conflict{'s' if sum(kinds) != 1 else ''}, "
                f"{len(kinds) - sum(kinds)} proposal{'s' if len(kinds) - sum(kinds) != 1 else ''}"
                if open_
                else ""
            ),
            "",
        ]
        return "\n".join(lines), json.dumps(
            carried, sort_keys=True, default=str, ensure_ascii=False
        )

    def impact_charts(self, card: str) -> list[str]:
        """t255: the charts that go beside this grid card, one SVG per activity with a score, or
        none. Looked up by the card as drawn, before the turn's words are named. t552: the card's
        shown words keep a figure with its unit, so a card is found by its key too."""
        return self._charts.get(card) or self._charts.get(card_key(card), [])

    def phone_charts(self, card: str) -> list[str]:
        """t403 r6: the phone's split of each of `impact_charts`' charts, in its order, where it has
        one (chart A's, `impact_chart.phone_split`); none for any other chart. t552: as
        `impact_charts`."""
        return self._phones.get(card) or self._phones.get(card_key(card), [])

    def _chart_activity(self) -> str | None:
        """t314: the activity a chart is asked for: the one his line names (t252), else the one
        this conversation is on. t367: in free chat, the one his line names by its own word
        ("production", `loosely_named`; t543: never by a class word, `chart_named`), else the one
        his latest earlier line named. None where his line names more than one, or no line names
        one of the room's. t377 H3: a line naming none takes the activity of his last analysis
        (`_analysed`) before the walk's. t533: a line in a conversation no line of his named one in,
        the room's focus (`_thread`, as the room kept it on a reopened room)."""
        if len(self._turn_named) == 1:
            return self._turn_named[0]
        if self._analysed and self._analysed in walk.processes(self.folder) \
                and not chart_named(self.folder, self._turn_line):
            return self._analysed
        a = self._activity
        if a and a in walk.processes(self.folder):
            return a
        for line in reversed(self._typed):
            if named := named_in(self.folder, line) or chart_named(self.folder, line):
                return named[0] if len(named) == 1 else None
        return self._thread

    def _chart_taps(self, extra: list[tuple[str, dict[str, Any]]]) -> list[str]:
        """His taps on screen, drawn again with the chart's own after them (t329: the slides tap
        too), outside ADR-0045's cap. A "Show the grid" of an earlier chart is not kept."""
        held = [(self._held(t["label"], call), call) for t in self._last_taps
                if t.get("kind") != "chart_grid"  # shown once, or drawn again under a new chart
                for call in [self._tap_ids[self._tap_labels[t["label"]]]]]
        labels = {label for label, _ in held}
        return self._draw(held + [(o, act) for o, act in extra + self._slides_tap
                                  if o not in labels])

    def _chart_turn(self, user_text: str, how: str, t0: float,
                    a: str) -> tuple[str, list[str], list[str]]:
        """t314: the chart he asked for, nemo's own turn with no model call. t367 (spec §13): chart
        A, t403: a line per category for each year: last year's record's grid, and this
        year's interview's grid as code reads it (`this_years_interview`), never the walk's
        model draft. With neither, one line saying when it comes, and nothing drawn. His taps stay,
        with "Show the grid" for the categories behind it."""
        method, name = self._method(), map_name(self.folder, a)
        chart, phone = activity_charts(self.folder, a, method)
        if not chart:
            return self._server_reply(user_text, how, t0, CHART_LATER.format(activity=name),
                                      self._chart_taps([]), "chart")
        taps = self._chart_taps([(SHOW_GRID, {"kind": "chart_grid", "activity": a})])
        count = len(method_lenses(method))
        import agent_fallback  # they import this module, so not at the top
        under = CHART_UNDER.format(count=COUNTS[count] if count < len(COUNTS) else count)
        under = (under_with_year(under, self.folder, a) if agent_fallback.switched_on() else under
                 ) if this_years_scores(self.folder, a, method)[0] else \
            no_scores_line(self.folder, a)  # 741 r2: the switch-OFF card's words are frozen (t599)
        card = (f"{CHART_TITLE.format(activity=name)}\n\n{under}"
                + (f"\n\n{euros}" if (euros := euro_said(self.folder, a)) else ""))  # t481
        charts, phones, path = [chart], [phone], None
        if added := self._chart_template(user_text, card, a, method):  # t499: card + template
            card, charts, phones, path = added
        self.cards.append(card)
        self._charts, self._phones = {card: charts}, {card: phones}
        import line_reads  # it imports this module, so not at the top
        shown.put(self.folder, shown.CHART, {  # t533: the room's last chart, by what it draws
            "template": line_reads.IMPACT_OVER_TIME, "arguments": {
                "activities": (path or {}).get("activities") or [a],
                "classes": (path or {}).get("classes"), "years": shown.YEARS},
            "card": len(self.cards) - 1}, turn=self.turn_id)
        return self._server_reply(user_text, how, t0, "", taps, "chart", agent=path)

    def _chart_template(self, line: str, card: str, a: str, method: dict[str, Any]
                        ) -> tuple[str, list[str], list[str], dict[str, Any]] | None:
        """t499 (ADR-0053 decision 1): with the switch ON, where `line_reads.chart_miss` says the
        chart card holds the facts but not the picture asked ("add order picking to the same
        chart" drawing order picking alone), the card stays and the template draws the chart
        before below it (`line_reads.card_and_template`). None where the card stands alone."""
        before, self._chart_shown = self._chart_shown, a
        since, self._chart_at = self._typed[self._chart_at:], len(self._typed)
        if not before or before == a:
            return None
        import agent_fallback  # they import this module, so not at the top
        import line_reads
        earlier = CHART_TITLE.format(activity=map_name(self.folder, before))
        if not agent_fallback.switched_on() \
                or not (why := line_reads.chart_miss(line, card, earlier)):
            return None
        return line_reads.card_and_template(  # r2: the classes he picked since the chart before
            self.folder, card, [before, a], why, method, line_reads.picked(self.folder, since))

    def _resource_turn(self, user_text: str, how: str, t0: float,
                       view: ResourceView) -> tuple[str, list[str], list[str]]:
        """t485: a chart line naming a resource: its dependency view, code's lines and the graph
        page's link opened lit on it, with no model call and no impact chart. His taps stay.
        t488: a dependency ask naming one too (what it depends on)."""
        link = self.view_link(CHAIN_VIEW, [view.box])
        return self._server_reply(user_text, how, t0, f"{view.said}\n\n" + GRAPH_LINK.format(
            link=link), self._chart_taps([]), RESOURCE_KIND)

    def _chart_pick(self, user_text: str, how: str, t0: float) -> tuple[str, list[str], list[str]]:
        """t367 B: a chart line with no activity to draw. nemo's own line that the chart is per
        activity, and a tap for each activity with a grid (last year's record, or this year's
        interview as code reads it); with none anywhere, when the chart comes. No model call."""
        drawn = self._charted()
        taps = self._chart_taps([(CHART_TAP.format(activity=map_name(self.folder, a)),
                                  {"kind": "chart", "activity": a}) for a in drawn])
        return self._server_reply(user_text, how, t0,
                                  CHART_PER_ACTIVITY if drawn else CHART_NONE, taps, "chart")

    def _charted(self) -> list[str]:
        """t367 B: the activities with a grid to chart (last year's record, or this year's
        interview as code reads it), in the map's order, `CHART_TAPS` at most."""
        method = self._method()
        return [a for a in process_map_order(self.folder, walk.processes(self.folder))
                if impact_chart.from_record(last_year(self.folder, a).get("grid"), method)
                or this_years_interview(self.folder, a, method)[0]][:CHART_TAPS]

    def _offered(self) -> list[tuple[Callable[[str], Any], str, dict[str, Any] | None]]:
        """t449: the tools the room offers now, each as (the matcher code reads his line with for
        it, its tap's label, the tap's usual call, None where none can be drawn now): 317's write
        on a finding (433's step), 373's invitation, 329's slides and 367's chart."""
        line = self._turn_line
        step = finding_step(self.folder, [self._found_in, self._room_activity(line),
                                          *self._owners_activity()])
        offers: list[tuple[Callable[[str], Any], str, dict[str, Any] | None]] = [
            (WRITE_READS.search, WRITE_TAP, {"kind": "write", **step} if step else None)]
        if about := invitable(self.folder, line, self._activity):
            offers.append((INVITE_WORDS.search, INVITE_TAP, {"kind": "invite", "activity": about}))
        if slides_filled(self.folder):
            offers.append((SLIDES_WORDS.search, SLIDES_TAP, page_tap("slides")))
        if charted := self._charted():
            offers.append((lambda w: CHART_WORDS.search(w) and not NOT_THIS_CHART.search(w),
                           CHART_TAP.format(activity=map_name(self.folder, charted[0])),
                           {"kind": "chart", "activity": charted[0]}))
        import briefing  # t405: it imports this module, so not at the top
        if (about := self._about_now(line)) and briefing.chrome():  # r2 (c): 405's PDF, a link
            offers.append((BRIEFING_WORDS.search, BRIEFING_PDF.format(
                link=self.page_link(f"briefing/{about}.pdf")), None))
        return offers

    def _chart_grid(self, user_text: str, how: str, t0: float,
                    a: str) -> tuple[str, list[str], list[str]]:
        """t367: "Show the grid" under chart A: every category at every hour, as each year's grid
        the chart was drawn from states it. No model call."""
        method, name = self._method(), map_name(self.folder, a)
        hors = [str(h) for h in method.get("time_horizons") or []]
        prior = last_year(self.folder, a)
        this, when = this_years_scores(self.folder, a, method)
        grids = [(CHART_THIS_KEY.format(when=when) if when else CHART_THIS_UNDATED, this),
                 (last_key(prior),
                  impact_chart.from_record(prior.get("grid"), method))]
        lines = [f"**{name}: the grid**", ""]
        for said, grid in grids:
            if not impact_chart.worst_points(grid, hors) or not any(
                    v is not None for v in impact_chart.worst_points(grid, hors)):
                continue
            lines += [said, "", "| | " + " | ".join(hors) + " |", "|---" * (len(hors) + 1) + "|"]
            for s in method.get("scenarios") or []:
                row = grid.get(s.get("id")) or {}
                lines.append(f"| {s.get('name') or s.get('id')} | " + " | ".join(
                    str(row[h]) if isinstance(row.get(h), int) else "–" for h in hors) + " |")
            lines.append("")
        self.cards.append("\n".join(lines).rstrip())
        return self._server_reply(user_text, how, t0, "", self._chart_taps([]), "chart_grid")

    def _impact_charts(self, a: str, carried: str, names: list[str]) -> list[str]:
        """Each activity's grid as the card carries it, drawn by code (`impact_chart`); a grid
        with no score draws none. t527: with two or more activities each chart is titled with its
        own, the name `_grid_card` prints above its table; a lone table has no name over it, so
        its chart keeps the walk's."""
        method = self._method()
        grids = [grid for grid, _ in json.loads(carried)]
        titles = [map_name(self.folder, n if len(names) > 1 else a) for n in names]
        charts = [impact_chart.svg(grid, method, t) for grid, t in zip(grids, titles, strict=False)]
        return [c for c in charts if c]

    def _dependency_lines(self, state: dict[str, Any], act: dict[str, Any],
                          aid: str) -> list[str]:
        """195: what this activity depends on, under the figures it holds up.

        The ones on the record first, each once, by the register's own name for them; then each
        one the model proposed and he has not added, marked a proposal in the word the score rows
        already use and saying where it came from. He adds one by its tap, or leaves it off.
        """
        register, interviews = _room_facts(self.folder, state, _drafted_activity(state))
        on_record = [RECORDED_DEP_SAYS.format(name=dep_name(register, d["asset_id"]),
                                              asset_id=d["asset_id"])
                     for d in act.get("dependencies") or [] if d.get("asset_id")]
        # t96's rule: a card he reads says a file by its plain name; the record keeps the path
        proposed = [self._drawn(PROPOSED_DEP_SAYS.format(name=i["name"], asset_id=i["asset_id"],
                                                         mark=PROPOSED_MARK, source=i["source"]))
                    for i in proposed_dependencies(state.get("draft") or {}, state, register,
                                                   interviews, self.folder)
                    if i["activity_id"] == aid and not i["added"]]
        if not on_record and not proposed:
            return []
        return [DEPS_HEADING, "", *(f"- {line}" for line in [*on_record, *proposed]), ""]

    @staticmethod
    def _grid_figure(label: str, value: Any, gap: bool, acknowledged: bool) -> str:
        """One figure on the line under the grid, as the card prints it (t85). A recovery gap
        carries `PROPOSED_MARK` until an act of his acknowledges it — the mark the score rows
        still open already carry, and no second vocabulary beside it."""
        if label == "MTPD":
            return f"**{label} {value or '—'}**"
        gap_says = (
            "" if not gap else " (recovery gap)" + ("" if acknowledged else f" {PROPOSED_MARK}")
        )
        return f"{label} {value or '—'}{gap_says}"

    def _rests_on(self, names: words.Names, draft: dict[str, Any], decisions: dict[str, Any],
                  aid: str, meta: dict[str, Any]) -> list[str]:
        """What the MTPD the record would carry rests on: the side he took, his own figure, the
        method's rule, or the draft's quote and whose it is, as the files hold them."""
        d = decisions.get(f"{aid}.mtpd") or {}
        if not meta.get("value"):
            return []
        if d.get("by"):
            c: dict[str, Any] = next(
                (c for c in draft.get("conflicts") or [] if c.get("id") == d["by"]), {}
            )
            n = (decisions.get(d["by"]) or {}).get("side")
            side = (
                (c.get("sides") or [])[n]
                if isinstance(n, int) and n < len(c.get("sides") or [])
                else {}
            )
            return [
                "The MTPD rests on the side you took, "
                f"{side.get('speaker') or 'side ' + str((n or 0) + 1)}'s, "
                f"on {_lower_first(names.item(d['by']) or '')}"
                + (f" · {self._drawn(side['path'])}" if side.get("path") else "")
                + ":",
                "",
                *(_quoted(side.get("quote")) or ["(no quote on file)", ""]),
            ]
        if meta.get("origin") == "manager":
            reason = (explicit_change(d) or {}).get("reason")
            # t80: since the gate, a figure named in chat reaches the record only when he taps it,
            # so the card says which of the two happened and never guesses between them.
            return [("The MTPD is your figure, typed in chat." if d.get("typed") else
                     "The MTPD is the figure nemo named in chat, and you confirmed it."
                     if d.get("confirmed") else
                     "The MTPD was set in chat, not typed by you.")
                    + (f" Your reason: {reason}" if reason else ""), ""]
        if meta.get("origin") == "method":
            return [
                f"{COMPANY_METHOD}: the MTPD comes from the method's rule over the grid above.",
                "",
            ]
        mine = f" It is {PROPOSAL_WORD}." if meta.get("origin") == "proposed" else ""
        who = " · ".join(
            x
            for x in (
                meta.get("speaker"),
                meta.get("source_path") and self._drawn(meta["source_path"]),
            )
            if x
        )
        return (
            [f"The MTPD rests on {who}:{mine}", "", *(_quoted(meta.get("quote")) or [""])]
            if who
            else [f"The MTPD rests on no quote on file.{mine}", ""]
        )

    def _settled_accounts(
        self,
        names: words.Names,
        draft: dict[str, Any],
        decisions: dict[str, Any],
        aid: str,
        meta: dict[str, Any],
    ) -> list[str]:
        """t63 (71's latest-decision rule): a figure he set after settling a conflict on it carries
        the settled account beside it, from the state file's decisions and their order."""
        out = []
        for key, label in (("mtpd", "MTPD"), ("rto", "RTO"), ("rpo", "RPO")):
            d = decisions.get(f"{aid}.{key}") or {}
            if d.get("by") or not explicit_change(d):
                continue
            for c in draft.get("conflicts") or []:
                taken = decisions.get(c.get("id")) or {}
                n, sides = taken.get("side"), c.get("sides") or []
                side = sides[n] if isinstance(n, int) and n < len(sides) else {}
                implied = side.get("implies") if isinstance(side.get("implies"), dict) else {}
                # why: `implied` is a dict: the isinstance on the line above chose it
                if implied.get("item_id") != f"{aid}.{key}" or int(taken.get("seq") or 0) >= int(  # type: ignore[union-attr]
                    d.get("seq") or 0
                ):
                    continue
                how = (
                    "typed"
                    if d.get("typed")
                    else "confirmed"
                    if d.get("confirmed")
                    else "set in chat"
                )
                # t477: a side by who said it, never its number
                took = f"{side['speaker']}'s side" if side.get("speaker") else "a side"
                out.append(
                    f"{label}: you took {took} on "
                    # why: `implied` is a dict, as above
                    f"{_lower_first(names.item(c['id']) or '')} ({implied.get('value')}), then "  # type: ignore[union-attr]
                    f"{how} {d.get('value')}. The later decision stands: {label} "
                    f"{(meta.get(label) or {}).get('value')}."
                )
        return out + [""] if out else []

    def _decision_card(self, a: str, item: dict[str, Any], state: dict[str, Any], k: int, n: int,
                       names: words.Names) -> str:
        """One open decision as its own card (t63): the item by its human name, the proposal marked
        as one, and for a conflict each side under the number its tap carries: the speaker and the
        quote's file as drafted, the quote as it stands, and what taking it makes the record
        carry."""
        # t183 (16_nemo_check, old rooms): a reason stored before 183 still says its ids; drawn
        # named here, the stored draft untouched. Idempotent, so a new room's is drawn as stored
        item = names.draft_said(item)
        iid, kind = item["id"], item["type"]
        title = self._drawn(names.item(iid) or item.get("about") or self._unnamed(item))
        if kind == "conflict":  # t520: its figures keep their units at 390, as its taps do
            title = unit_kept(title)
        lines = [f"{DECISION_HEADING} {k} of {n} · {title}**", ""]
        if kind == "conflict":
            entries = self._side_entries(a, item, state)
            for e in entries:
                who = COMPANY_METHOD if _who(e["speaker"]) == "method" else e["speaker"]  # t65
                source = self._drawn(e["path"]) if e["path"] else ""
                # r2: a source label repeating the side's name ("method") is said once
                lines += [f"**{e['side'] + 1} · {who or e['label']}**"
                          + (f" · {source}" if source
                             and source.lower() not in (who or e["label"]).lower() else ""), ""]
                lines += _quoted(e["quote"]) or [
                    f"No quote on file. The draft sums this side up: {self._drawn(e['claim'])}", ""]
                lines += [TAKING_SIDE.format(effect=e["effect"]), ""]
            rec = item.get("recommend")
            if isinstance(rec, int) and rec < len(entries):  # t477: the side by what it says
                lines += [f"{PROPOSAL_WORD}: {entries[rec]['label']}"
                          # t79 fix 1: whoever wrote this `why`, said in their voice. The
                          # MTPD-rule conflict is nemo's own, so its reason is nemo's.
                          + (f". {why_said(item)}{item['why']}" if item.get("why") else ""), ""]
                lines += check_lines(item)  # fix 2, M7: the same path to nemo's own note
            # t76: the third choice, and what it does, from the draft's own sides and the record
            lines += [
                f"**{UNRESOLVED_TAP}**",
                "",
                self._unresolved_effect(a, item, state) + ".",
                "",
            ]
        elif kind in ("MTPD", "RTO", "RPO"):
            lines += [f"{PROPOSAL_WORD}: {kind} {item.get('value')}", ""]
            who = " · ".join(
                x
                for x in (item.get("speaker"), item.get("path") and self._drawn(item["path"]))
                if x
            )
            if item.get("quote"):
                lines += [
                    f"It rests on {who}:" if who else "It rests on:",
                    "",
                    *_quoted(item["quote"]),
                ]
            lines += why_lines(item)  # t79 fix 1: the reason in its author's voice
        else:
            scores = item.get("scores") or {}
            lines += [f"{PROPOSAL_WORD}: " + " · ".join(f"{h} {v if isinstance(v, int) else '–'}"
                                                        for h, v in scores.items()), ""]
            if item.get("quote"):
                lines += [
                    f"It rests on {self._drawn(item['path'])}:"
                    if item.get("path")
                    else "It rests on:",
                    "",
                    *_quoted(item["quote"]),
                ]
            lines += why_lines(item)  # t79 fix 1: the reason in its author's voice
        return "\n".join(lines).rstrip() + "\n"

    def _decisions_table(self, a: str, open_: list[dict[str, Any]], state: dict[str, Any],
                         names: words.Names) -> str:
        """t115: every open decision as one table, in nemo's order, a row each: the card's name,
        what it decides, and nemo's recommendation. From the room's open items, never the
        model's."""
        cats = {
            c["id"]: c.get("name") or c["id"]
            for c in self._method().get("scenarios") or []
            if c.get("id")
        }

        def cell(text: Any) -> str:
            return " ".join(str(text).split()).replace("|", "\\|") or "–"

        def row(i: dict[str, Any]) -> str:
            kind = i["type"]
            if kind == "conflict":
                rec = i.get("recommend")
                entries = self._side_entries(a, i, state)  # t477: the side by what it says
                decides, says = i.get("about") or "which side the record takes", \
                    entries[rec]["label"] if isinstance(rec, int) and rec < len(entries) else "–"
            elif kind in ("MTPD", "RTO", "RPO"):
                decides, says = f"the {kind}", f"{kind} {i.get('value')}"
            else:
                decides = f"the {cats.get(i.get('lens'), i.get('lens'))} scores"
                says = " · ".join(
                    f"{h} {v if isinstance(v, int) else '–'}"
                    for h, v in (i.get("scores") or {}).items()
                )
            name = self._drawn(names.item(i["id"]) or i.get("about") or self._unnamed(i))
            return f"| {cell(name)} | {cell(decides)} | {cell(says)} |"

        return "\n".join([f"{OPEN_DECISIONS_HEADING} · {a}**", "",
                          f"| Decision | What it decides | {PROPOSAL_WORD} |", "|---|---|---|",
                          *[row(i) for i in open_], ""])

    def _stage3_cards(self, mode: str) -> None:
        """Stage 3's cards for this turn, drawn after its taps: what `walk.prints` returns and
        nothing else (t115). On a turn with an answer, the one card whose taps are live. On the turn
        he tapped "Show the grid" or "Show the open
        decisions", that one table and nothing else: the live card already stands above it."""
        tapped, self._tapped = self._tapped, ""  # the tap's own turn, and that turn only
        a = self._activity
        if not a or a not in walk.processes(self.folder):
            return
        if walk.current(self.folder, a).stage != walk.STAGE_3:
            return
        state = load_state(self.folder, a)
        if mode not in STAGE3_MODES or not state.get("draft"):
            return
        open_ = ordered_open(state)
        item = open_[0] if open_ else None  # the decision this turn's taps are about
        asked = None if item else self._question(a)  # t116: else the referee's open question
        entries = self._side_entries(a, item, state) if item and item["type"] == "conflict" else []
        names = words.Names(self.folder, a, self.model)
        key = (a, str((item or {}).get("id") or (asked or ("",))[0]), len(open_))
        before = len(self.cards)
        for kind in walk.prints(
            walk.STAGE_3, tapped, decision_open=item is not None or asked is not None
        ):
            if (kind == "live_card" and self._turn_line and key == self._live_key
                    and not RAISES_CARD & set(self._turn_tools)):
                self._pointed = True  # t377 D4: raised already; his question gets a pointer
                continue
            if kind == "live_card":
                self._live_key = key
            if kind == "live_card" and asked is not None:
                q = asked[1]
                self.cards.append(QUESTION_CARD.format(heading=QUESTION_HEADING, activity=a,
                                                       asserted=q.asserted, derived=q.derived))
            if kind == "grid":
                card, carried = self._grid_card(a, state)
                self.cards.append(card)
                own = [act["name"] for act in (state.get("draft") or {}).get("activities") or []]
                self._charts, self._phones = {card: self._impact_charts(a, carried, own)}, {}
            elif kind == "decisions":
                self.cards.append(self._decisions_table(a, open_, state, names))
            elif kind == "live_card" and item is not None:
                # the owner, "Never, button only" (11:22:49Z): the Accept-all tap stays under
                # it, and no list of what it accepts prints; that is "Show the open decisions"
                self.cards.append(self._decision_card(a, item, state, 1, len(open_), names))
                self.live_at = len(self.cards) - 1  # t117: the turn's taps go on this message
        self._staged = len(self.cards) > before  # t429
        if item and item["type"] == "conflict":
            self._card_log = {"item": item["id"], "sides": [
                {"side": e["side"], "label": e["label"], "effect": e["effect"], "names": e["names"]}
                for e in entries]}

    def _signature_card(self, activity: str, owners: list[str]) -> None:
        """The card that asks for the signature in words: it is typed, never tapped (t73). t64b, the
        owner's review: a name and role identify the signer and establish no delegated authority,
        and "does not undo" says what becomes of a correction (nothing records one yet: ticket
        61)."""
        whom = ", ".join(o for o in owners if o) or "the activity owner nemo names"
        self._staged = True  # t429
        self.cards.append(
            f"**Your signature · {self._heading(activity)}**\n\nThe handover is "
            "accepted. The signature is the one thing you type, never tap: type your own "
            "name and your role. Then nemo asks who you are signing as — as the owner "
            f"yourself, or on behalf of {whom} — and your certificate says the one "
            "you picked. Your name and role identify you; they do not show that the owner "
            "delegated this to you, and nemo does not check that. Signing is what does "
            "not undo: nothing in this walk reopens a signed BIA, and nemo has no way "
            "yet to record a correction after signing."
        )

    def _finish(self, reply: dict[str, Any], how: str, t0: float, model_s: float, tool_s: float,
                tools_called: list[str], tools: list[dict[str, Any]] | None,
                tool_work: str | None = None,
                handed: tuple[str, str] | None = None) -> tuple[str, list[str], list[str]]:
        """The end of a turn the model spoke in: the figure check, the model's OPTIONS dropped whole
        and logged, and nemo's taps drawn from data (t73). 607: with the switch ON, a tap's
        narration (what nemo `handed` the model, and code's line where nothing stands) and a
        guidance answer go through the one check stack (`_checked`) instead of the drop stack
        below, which stays the brake's (610)."""
        seconds = round(time.time() - t0, 1)
        one = (handed is not None or self._guidance_text is not None) and self._one_stack()
        # t73: an OPTIONS line the model writes is dropped whole and logged, never rendered and
        # never read (M13): the taps are nemo's, below. Structural: the line's marker, not its
        # words.
        # Dropped before the figure check, so a figure in a line nobody sees never costs a redraft.
        text, model_options = _drop_options(reply.get("content") or "")
        text, unnamed = plain_titles(text, self.folder)  # t377 F3: before the check (digits)
        # t476: a model letter is never shown, tap or no tap: the turn is a write ask, code's
        # letter stands for it (`write_said`)
        lettered = not (self._asked_write or self._code_said or self._invite_tap) \
            and model_letter(text)
        self._asked_write = self._asked_write or lettered
        # t65 fix 1: on a guidance turn only the model's last sentence is shown, so it is cut to
        # that
        # before the figure check: a restatement thrown away anyway never costs a redraft
        if self._guidance_text is not None:
            text = last_sentence(text)
        # nemo's own rule, restored for the chat: `nemo.card.render` refuses a card whose prose
        # states a figure the record does not hold (card.py:211). The chat only logged it, and that
        # is how "animal-welfare 4 at the 2-hour column" reached the owner on 2026-09-17. One
        # redraft naming the figures; a sentence still holding an untraceable figure is dropped
        # whole and logged (t377 F2: never a raw marker mid-sentence).
        struck: list[str] = []
        # Ticket 68: on a turn that showed the room's state (the pick card or the printed sheet),
        # and whenever no activity is chosen yet, the taps are the activity pick. Ticket 67 fix 1:
        # on a signed activity they are AFTER_SIGNING. t73: at every other step, nemo's step taps.
        self._card_said = text  # t516
        pairs, mode = self._taps_now(tools_called)
        checked = self._checked(text, handed[0] if handed else self._guidance_text or "",
                                tools_called, pairs) if one else None
        text = (checked.text or (handed[1] if handed else "")) if checked else text
        wrote = any(label == WRITE_TAP for label, _ in pairs)
        step = next((t for label, t in pairs if label == WRITE_TAP), {})
        shown = drafts_first(self.folder, step["activity"]) \
            if self._asked_write and step.get("found") else None  # t391: drafts first
        # t389: code's answer stands for the model's words, as on an invite turn
        # (`invite_tap_said`), so neither costs a redraft; t391 r3: nor do code's drafts
        flagged = [] if one or self._code_said or (self._invite_tap and not self._asked_write) \
            or (self._asked_write and shown) else self._flag(text)
        if flagged:
            self.log("blocked", {"model": self.model, "flagged": flagged, "text": text})
            self.messages.append({
                "role": "user",
                "content": f"(nemo's figure check blocked that reply: {flagged} trace to no file, "
                           "draft or record. Say it again without those figures, or with the exact "
                           "figures a tool gave you. Same length, same next step.)"})
            m0 = time.time()
            reply = lanes.chat(self.model, self.messages, tools, room=self.folder)
            model_s += time.time() - m0
            self.stats["calls"] += 1
            keep = ("role", "content", "tool_calls") if tools else ("role", "content")
            self.messages.append({k: v for k, v in reply.items() if k in keep})
            text, again = _drop_options(reply.get("content") or "")
            text, unnamed = plain_titles(text, self.folder)
            model_options += again
            if self._guidance_text is not None:
                text = last_sentence(text)
            still = self._flag(text)
            text, struck = drop_untraced(text, still)
            if still:
                self.log("struck", {"model": self.model, "flagged": still, "dropped": struck})
            seconds = round(time.time() - t0, 1)
        self.stats["seconds"] += seconds
        denials: list[str] = []
        has_tap: list[str] = []
        if text and not one and not self._code_said and (lettered or not self._asked_write) \
                and DENIED_BY.search(text) and DENIAL.search(text):  # t366 answers a write ask
            # t449 (A8-17/18): a sentence denying the room a tool it offers goes; code says the
            # tap exists and draws it with its usual call (as t366's, outside the cap)
            offers = self._offered()
            text, denials, labels = drop_denials(text, [(r, label) for r, label, _ in offers])
            for reads, label, call in ((r, x, c) for r, x, c in offers if x in labels):
                if "](" in label:  # r2 (c): 405's PDF link is code's line; only the denial goes
                    has_tap.append(label)
                    continue
                if lettered and label == WRITE_TAP:  # t476: `write_said` draws the write tap's
                    continue
                if call and label not in (x for x, _ in pairs):
                    pairs = [*pairs, (label, call)]
                drawn_now = label in (x for x, _ in pairs)
                has_tap.append(HAS_TAP.format(tap=label) if label != WRITE_TAP else (
                    DRAFT_FINDING if drawn_now else DRAFT_NO_FINDING).format(tap=WRITE_TAP))
                # r2 (a, b): the model's own version of the tool goes; the tap is the one path
                text, own = drop_offered(text, reads, letters=label == WRITE_TAP)
                denials += own
        if text and not (one or self._code_said or self._asked_write or self._invite_tap) \
                and CLAIMED.search(text):  # t530: a claimed action no tool of this turn did
            offers = self._offered()
            text, claims, labels = drop_claims(text, offers, tools_called)
            denials += claims
            for _, label, call in ((r, x, c) for r, x, c in offers if x in labels):
                if call and label not in (x for x, _ in pairs):
                    pairs = [*pairs, (label, call)]
                has_tap.append(NOT_DONE.format(tap=label))
        put = [(PUT_DRAFTS_TAP, {"kind": "put_drafts", "activity": step["activity"]})] \
            if shown else []  # t406: one tap, under the drafts shown, outside 329's cap
        options = self._draw(pairs + self._slides_tap + self._invite_tap + put)
        self._turn_tools = tools_called
        self._stage3_cards(mode)
        # t413 (M13): before code's blocks join them, the model's words lose each sentence naming a
        # tap, count or figure code did not draw this turn; where code's answer or drafts stand for
        # them, every paragraph goes whole below (t377, t391 r2)
        drawn = [*self.cards, *filter(None, (self._sheet_text, self._guidance_text,
                                             self._lead_said, self._code_said)),
                 *(self._changes_read() if self._analysing and mode == "chat" else [])]
        self._code_lines += drawn  # t434: what code drew holds for the turns after this one too
        self._code_lines += [self._check_said] if self._check_said else []  # t507, as t434
        text, undrawn = (text, []) if one or self._code_said or (self._asked_write and shown) else \
            drop_undrawn(text, self._drawn_labels(), drawn,
                         words.served_names(self.folder), cited_files(self.folder, self._activity),
                         method_lenses(walk._method(self.folder)))
        if not (one or self._code_said or (self._asked_write and shown)):
            # t434 (M13): a name the room's files lack, a send or reply state or a day only the
            # model holds; the known words are the room's, his and the tools', never a list
            code = "\n".join([*self._code_lines, *self._drawn_labels()])
            text, unheld = drop_unheld(text, "\n".join([
                room_text(self.folder), code, json.dumps(tools or []), *(
                    m["content"] for m in self.messages if m.get("role") != "assistant"
                    and isinstance(m.get("content"), str))]), code, story_today(self.folder))
            undrawn += unheld
            text, claimed = drop_programme_claims(  # t459: the plan's, by code
                text, self.folder, self._programme_turn)
            undrawn += claimed
        if text and not one and _FIRST_IMPACT.search(text) and (
                about := next((a for a in (self._activity, self._thread, self._analysed) if a),
                              None)):  # t548: a threshold the cited row lacks, by code
            text, lacking = drop_unheld_thresholds(text, {
                "this": _this_year_rows(self.folder, about),
                "last": last_year(self.folder, about).get("grid") or {}})
            undrawn += lacking
        text, euros = _drop_sentences(text, EURO_FIGURE) if text and not one else (text, [])
        undrawn += euros  # t481 (M13)
        text, counted = (text, []) if one else drop_interview_counts(  # t514 (M13)
            text, self._drawn_labels())
        undrawn += counted
        if self._sheet_text or self._guidance_text is not None:
            # the state answer is the sheet as printed, a guidance answer the ask lane's as served
            # (t65), both outside the figure check above; the model's words add one sentence at most
            added = last_sentence(text) if self._guidance_text is not None else first_sentence(text)
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = added
            blocks = [b for b in (self._sheet_text, self._guidance_text) if b]
            # t110: in free chat the model's sentence is the plain answer to a method question, so
            # it comes first and nemo's block, labels kept, after; in a walk it hands him back to
            # the step, after the block
            first = self._guidance_text is not None and not self.walk_prompt
            text = "\n\n".join(([added] if added and first else []) + blocks
                               + ([added] if added and not first else []))
        if not self.walk_prompt:
            text = LEAD_IN.sub("", text, count=1)  # t265: what is shown opens on the answer
        dropped = [*unnamed, *struck, *denials, *undrawn]  # t377 F2/F3, t449, t413; then t366's
        dropped += [d["text"] for d in checked.drops] if checked else []  # 607
        text, inner = _drop_sentences(text, MECHANICS) if text and not one else (text, [])
        dropped += inner  # t377 N6
        text, stale = _drop_sentences(text, STALE_TAP) if text and not one else (text, [])
        dropped += stale  # t392
        if self._asked_write:  # t366: nemo's own line, and the model keeps what he was shown
            text, written = write_said(text, wrote, shown, self._pending_drafts(pairs)
                                       if mode == PENDING_KIND else None)
            dropped += written
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if has_tap:  # t449: code's line on the tap the model denied, first, as t366's
            self._code_lines += has_tap  # t434: code's line, for later turns
            text = "\n\n".join([*has_tap, text] if text else has_tap)
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if self._analysing and mode == "chat" and (blocks := self._changes_read()):
            text, cut = one_plain_sentence(text)  # t377 N6: the block said it; one sentence at most
            dropped += cut
            # t544: a day his line names that holds interviews closes the answer on this year's
            # other interviews (`others_said`), r2: last, after the model's sentence
            day = named_day(self.folder, self._turn_line)
            others = others_said(self.folder, self._changes_paths()) \
                if day and day_interviews(self.folder, day) else ""
            if day and day_interviews(self.folder, day) and text:  # r4: the card names the day;
                # a model sentence naming an interview, a day or an activity is dropped
                text, named = _drop_sentences(text, lambda x: bool(
                    named_in(self.folder, x) or _WEEKDAY_SAID.search(x)
                    or _DATE_SAID_ON.search(x) or INTERVIEW_SAID.search(x)))
                dropped += named
            text = "\n\n".join([*blocks, *[text] * bool(text), *[others] * bool(others)])  # D2
            self._code_lines += [others] * bool(others)  # t434: code's line, for later turns
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if self._analysing and (about := self._analysed_now()):  # t377 H3
            self._analysed = about
        if self._invite_tap and not self._code_said and not self._asked_write:  # t377 (B2)
            text, gone = invite_tap_said(self.folder, self._invite_tap[0][1]["activity"], text)
            dropped += gone
            self._code_lines.append(text)  # t434: code's line on the invitation, for later turns
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if self._lead_said:  # t377 (C): what code found leads; the model's words follow
            text = f"{self._lead_said}\n\n{text}" if text else self._lead_said
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if self._check_said:  # t507 (A9): as t377 (C)'s lead
            text = f"{self._check_said}\n\n{text}" if text else self._check_said
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if self._code_said:  # t377: code's answer; the model's words dropped, for the turn file
            dropped += [p for p in text.split("\n\n") if p.strip()]
            text = unit_kept(self._code_said)  # t549 r2: code's, so figures keep their units
            if self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = text
        if self._pointed:  # t377 D4: the card stands above; one line points at it
            text = f"{text}\n\n{DECISION_POINTER}" if text else DECISION_POINTER
        if not self._sheet_text and mode == "step" and not (self._asked_write and wrote) \
                and (line := self._step_line(options)):  # t377: his email ask is the answer
            # t64: the taps below answer the whole step, not the model's question above them
            text = without_stage_name(text, line.strip("*"))  # t377 N5: said once, by code
            text = f"{text}\n\n{line}" if text else line
        elif mode == "step" and (carded := next((n for n in words.STAGES.values() if any(
                c.startswith(f"**{n}") for c in self.cards)), "")):
            text = without_stage_name(text, carded)  # t429: stage 2's card says it, by code
        cards, self.cards = self.cards, []
        taps = self._taps_log(mode, model_options)
        self.log("said", {"model": self.model, "seconds": seconds, "text": text,
                          "options": options, "cards": len(cards), "redrafted": bool(flagged),
                          "model_options": model_options})
        self.log(
            "turn",
            {
                "model": self.model,
                "how": how,
                "seconds": seconds,
                "model_seconds": round(model_s, 2),
                "tool_seconds": round(tool_s, 2),
                "tools": tools_called,
                "taps": taps,
                "prompt": "walk" if self.walk_prompt else "chat",
                **({"next_step": self._next_step} if mode == "chat" else {}),
                **({"dropped": dropped} if self._asked_write or self._code_said
                   or self._invite_tap or dropped else {}),  # never lost
                **({"code_said": self._code_kind} if self._code_kind else {}),  # t377 H
                **({"drops": checked.drops} if checked else {}),  # 607: with their reasons
                **({"tool_work": tool_work} if tool_work else {}),
                **(
                    {"signed_taps": {"activity": self._activity, "model_options": model_options}}
                    if mode == "signed"
                    else {}
                ),
                **(
                    {
                        "pick_taps": {
                            "sheet_printed": bool(self._sheet_text),
                            "model_options": model_options,
                        }
                    }
                    if mode == "pick"
                    else {}
                ),
                **(
                    {"hold_taps": {"activity": self._hold_offered, "model_options": model_options}}
                    if self._hold_offered and mode != "pick"
                    else {}
                ),
                **self._interview_state(),
            },
        )
        return text, options, cards

    def _analysed_now(self) -> str | None:
        """t377 H3: the one activity this turn's analysis was about: the activities the interviews
        it read name (`interview._named_in`), with those his line names; None where not one."""
        home = self.folder / interview.INTERVIEWS
        about = {a for p in self._turn_read if p.startswith(interview.INTERVIEWS)
                 and (home / Path(p).name).is_file()
                 for a in interview._named_in(home / Path(p).name)} | set(self._turn_named)
        if not about:  # t433 (A1): the one `_changes_read` fell back on
            return self._sheet_activity(self._turn_line)
        return about.pop() if len(about) == 1 else None

    def _changes_read(self) -> list[str]:
        """t377 D2: `changes_block` for each re-BIA interview this turn read or whose activity his
        line names, in file order; t433: else of the room's activity (`_sheet_activity`)."""
        return [b for p in self._changes_paths() if (b := changes_block(self.folder, p))]

    def _changes_paths(self) -> list[str]:
        """t475: the interviews `_changes_read` reads, in file order. t544: a day his line names
        (`named_day`) with interviews held on it (`day_interviews`) reads those alone."""
        home = self.folder / interview.INTERVIEWS
        if (day := named_day(self.folder, self._turn_line)) \
                and (held := day_interviews(self.folder, day)):
            return sorted(held)
        paths = {p for p in self._turn_read if p.startswith(interview.INTERVIEWS)}
        named = set(self._turn_named)
        paths |= {f"{interview.INTERVIEWS}/{f.name}" for f in sorted(home.glob("*.md"))
                  if set(interview._named_in(f)) & named} if home.is_dir() else set()
        if not paths and home.is_dir() and not DURATION_ASKED.search(self._turn_line) \
                and (on := self._sheet_activity(self._turn_line)):
            # t433 (A1, A1-03): none read or named, so the room's (`_sheet_activity`);
            # never on A4's how long, whose answer is the model's or `down_for`
            paths = {f"{interview.INTERVIEWS}/{f.name}" for f in sorted(home.glob("*.md"))
                     if on in interview._named_in(f)}
        return sorted(paths)

    def _step_line(self, options: list[str]) -> str | None:
        """t64: nemo's own line above taps that answer a whole step (stage 1's agree, stage 3's
        close, stage 4's record, stage 5's handover), saying what they decide. t429: and under a
        stage card that names no stage (`_staged`), so every stage is named by code."""
        a = self._activity
        if not a or a not in walk.processes(self.folder):
            return None
        stage = walk.current(self.folder, a).stage
        answers = {walk.STAGE: walk.AGREE, walk.STAGE_3: walk.ENDORSED, walk.STAGE_4: walk.ENDORSED,
                   walk.STAGE_5: ACCEPT_HANDOVER}
        return words.step_line(stage) if answers.get(stage) in options or self._staged else None

    def _taps_log(self, mode: str, model_options: list[str] | None = None) -> dict[str, Any]:
        """nemo's tap set for this turn, as rendered, with the call each stands for (turns file)."""
        taps = self._last_taps
        return {"mode": mode, "activity": self._activity, "set": [t["label"] for t in taps],
                "actions": taps, "ids": list(self.last_actions),
                "model_options": list(model_options or []),
                # t63: the conflict card drawn with these taps, each side's entry as the card
                # names it; the taps verdict reads a side tap's named value from here
                **({"card": self._card_log} if self._card_log else {})}

    def _no_interview_on_file(self, activity: str) -> bool:
        c = walk.current(self.folder, activity)
        return c.stage == walk.STAGE_2 and not c.interviews

    def _interview_turn(self, user_text: str, how: str, t0: float,
                        tap: dict[str, Any] | None = None) -> tuple[str, list[str], list[str]]:
        """A turn while nemo's interview is under way: a typed line is the answer to the question on
        screen (nemo's `walk.answer` docstring: the interview takes the words first). A tap is no
        answer, so the question stands."""
        iv = self._interview
        assert iv is not None
        if (
            how == "tapped"
            and tap
            and tap.get("kind") == "stop"
            and tap.get("activity") == iv["activity"]
        ):
            say, next_ = self._end_interview()  # the stop is not an answer: nothing of it is kept
            return self._server_reply(user_text, how, t0, say, next_, "interview")
        if how != "typed":
            return self._server_reply(user_text, how, t0, iv["say"], [STOP_INTERVIEW], "interview")
        iv["turns"].append(conduct.Turn(iv["question"], user_text))
        m0 = time.time()
        say, next_ = self._ask_next()
        return self._server_reply(user_text, how, t0, say, next_, "interview", time.time() - m0)

    def _ask_reply(self, user_text: str, how: str, t0: float, asked: dict[str, Any],
                   heard: bool = False) -> tuple[str, list[str], list[str]]:
        """A "Change …" question: its prompt, and two taps that leave it: keep it as it is (clears
        the pending change, calls nothing), or pick another activity (fix 1: never a bare prompt
        whose next line of any kind is taken as the value)."""
        self._register(KEEP_AS_IS, {"kind": "as_is"})
        self._register(PICK_ANOTHER, tool_tap("list_activities"))
        return self._server_reply(user_text, how, t0, asked["prompt"], [KEEP_AS_IS, PICK_ANOTHER],
                                  "ask_value", heard=heard)

    def _unreadable(self, user_text: str, how: str, t0: float, path: str,
                    error: str) -> tuple[str, list[str], list[str]]:
        """t297, t299: the turn in a room one of whose files cannot be read. The operator's log
        gets the path and the parse error; he gets the note naming the file, and nothing else.
        The register's turn keeps 297's kind, `unreadable_register`."""
        self.log("manager", {"model": self.model, "text": user_text})
        _LOG.warning("the room file %s cannot be read: %s", self.folder / path, error)
        return self._server_reply(user_text, how, t0,
                                  walk.UNREADABLE.format(what=walk.UNREADABLE_FILES[path],
                                                         path=path), [],
                                  "unreadable_register" if path == walk.REGISTER
                                  else "unreadable_file")

    def _server_reply(self, user_text: str, how: str, t0: float, text: str, options: list[str],
                      kind: str, model_s: float = 0.0, heard: bool = False,
                      redraw: bool = True,
                      agent: dict[str, Any] | None = None) -> tuple[str, list[str], list[str]]:
        """A turn the server answers itself (t72): no chat-model call. The history gets what the
        manager saw, so the model's next turn starts from it (t73: never as an OPTIONS line).
        `heard`: his line is in the history already (t64: the call his typed value made).
        `redraw=False` (a show tap, t115/117): the taps on screen stay current, none is drawn anew,
        and `taps_stay` tells the skin to leave the decision taps where they are."""
        if not heard:
            self.messages.append({"role": "user", "content": user_text})
        self._server_set = kind  # t478: its set says the answer's stage (`ANSWERED`)
        seconds = round(time.time() - t0, 1)
        self.stats["seconds"] += seconds
        # every tap here is the server's own, registered where it was drawn
        if redraw:
            # t662: as drawn, so the labels sent are those registered (`_current`)
            options = self._draw([(o, self._tap_ids[self._tap_labels[o]]) for o in options])
        self.taps_stay = not redraw
        self._stage3_cards(kind)
        cards, self.cards = self.cards, []
        self._code_lines += [text, *cards]  # t434
        if kind in KEPT_UNIT_KINDS:  # t552: the server's own words, never the model's
            text, cards = unit_kept(text), [unit_kept(c) for c in cards]
        # t115: a show tap's turn has no words of its own; the history gets the table he saw
        self.messages.append({"role": "assistant", "content": text or "\n\n".join(cards)})
        self.log("said", {"model": self.model, "seconds": seconds, "text": text, "options": options,
                          "cards": len(cards), "redrafted": False, "server": kind})
        self.log("turn", {"model": self.model, "how": how, "seconds": seconds,
                          "model_seconds": round(model_s, 2), "tool_seconds": 0.0, "tools": [],
                          "server": kind, "taps": self._taps_log(kind), **self._interview_state(),
                          **({"agent": agent} if agent else {})})  # t489: SHARED, its steps
        return text, options, cards

    def _led_turn(self, how: str, t0: float, text: str, options: list[str], cards: list[str],
                  model_s: float, tool_s: float,
                  led: dict[str, Any]) -> tuple[str, list[str], list[str]]:
        """t532 (ADR-0056): a turn the model led, on file with today's keys and `led_fields`
        beside them. S5a's path calls it; the brake's turns never do."""
        seconds = round(time.time() - t0, 1)
        self.stats["seconds"] += seconds
        self.log("said", {"model": self.model, "seconds": seconds, "text": text, "options": options,
                          "cards": len(cards), "redrafted": False})
        self.log("turn", {"model": self.model, "how": how, "seconds": seconds,
                          "model_seconds": round(model_s, 2), "tool_seconds": round(tool_s, 2),
                          "tools": [s["name"] for s in led["tool_steps"]], **led})
        return text, options, cards

    def _refusal_turn(self, refused: dict[str, Any], how: str, t0: float, model_s: float,
                      tool_s: float, tools_called: list[str],
                      tapped: bool = False) -> tuple[str, list[str], list[str]]:
        """A turn that met a standing refusal: `say` and the `next` taps, and nothing the model
        wrote.

        Nothing reads the model's text to decide this; the tool result did (M13). The assistant
        message that made the call keeps its tool calls but loses its words, and the history gets
        the refusal as said, so the next turn starts from what the manager actually saw. t73: each
        `next` is a tap nemo draws, standing for its one call; a tap's own turn has no model words.
        """
        if not tapped:
            self.messages[-1 - len(self._tail_tools())]["content"] = ""
        text = refused["say"]
        self.messages.append({"role": "assistant", "content": text})
        seconds = round(time.time() - t0, 1)
        self.stats["seconds"] += seconds
        if refused.get("server_turn"):  # t72: nemo's interview question; the cards drawn stay
            options = self._draw([(o, self._tap_ids[self._tap_labels[o]]) for o in refused["next"]])
            cards, self.cards = self.cards, []
            self.log("said", {"model": self.model, "seconds": seconds, "text": text,
                              "options": options, "cards": len(cards), "redrafted": False,
                              "server": "interview"})
            self.log("turn", {"model": self.model, "how": how, "seconds": seconds,
                              "model_seconds": round(model_s, 2), "tool_seconds": round(tool_s, 2),
                              "tools": tools_called, "server": "interview",
                              "taps": self._taps_log("interview"), **self._interview_state()})
            return text, options, cards
        options = self._draw([(o, self._named_tap(o, self._activity, refused.get("item_id")))
                              for o in refused["next"]])
        # the whole reply is the refusal: a card drawn earlier in this turn is not shown (fix 1)
        cards, self.cards, self.live_at = [], [], None
        shown = {"tool": refused["tool"], "say": text, "next": options, "turn_ended": True,
                 "from_ledger": refused["from_ledger"], "waits_on": refused["waits_on"]}
        self.log("said", {"model": self.model, "seconds": seconds, "text": text,
                          "options": options, "cards": len(cards), "redrafted": False,
                          "refusal": shown})
        self.log(
            "turn",
            {
                "model": self.model,
                "how": how,
                "seconds": seconds,
                "model_seconds": round(model_s, 2),
                "tool_seconds": round(tool_s, 2),
                "tools": tools_called,
                "refusal": shown,
                "taps": self._taps_log("refusal"),
            },
        )
        return text, options, cards

    def _has_record(self, activity: str) -> bool:
        record = walk.read_record(self.folder, walk.record_file(activity)) or {}  # type: ignore[attr-defined]  # walk re-exports read_record
        return str(record.get("dept", "")).lower() == self._room_name(activity).lower()

    def _closed(self, activity: str) -> bool:
        return (walk.read_record(self.folder, walk.run_file(activity)) or {}).get(  # type: ignore[attr-defined]  # walk re-exports read_record
            "status"
        ) == walk.CLOSED

    def _tail_tools(self) -> list[dict[str, Any]]:
        """The tool messages at the end of the history (the answers to the last assistant
        message)."""
        tail = []
        for m in reversed(self.messages):
            if m.get("role") != "tool":
                break
            tail.append(m)
        return tail

    def _flag(self, text: str) -> list[str]:
        """Figures in a reply that trace to nothing this walk holds.

        Traceable: in the draft and the manager's decisions, in the saved record, in a room file
        the model read this turn, or in the room's planning files (`TRACED_PLANS`, t377 F1). Step
        numbers and the method's 1-5 severity scale are not figures.
        """
        known = [json.dumps(load_state(self.folder, a), ensure_ascii=False)
                 for a in walk.processes(self.folder)]
        known += [record.read_text(errors="replace")  # t235: every activity's record
                  for record in sorted(self.folder.glob(f"output/*/{walk.RECORD_NAME}"))]
        known += [f.read_text(errors="replace") for f in self._read_this_turn if f.exists()]
        known += [(self.folder / p).read_text(errors="replace") for p in TRACED_PLANS
                  if (self.folder / p).is_file()]
        known += self._facts_served
        known.append(
            render_sheet(room_sheet(self.folder, self.model))
        )  # what nemo showed as the room's state
        haystack = " ".join(known)
        # t64 fix 1b/1c: a name nemo serves (a category, an activity, a stage heading, a person's
        # role) is said as served, digits and all; the digits count only inside that whole name,
        # so "1099" on its own is still a figure to trace
        for name in sorted(words.served_names(self.folder), key=len, reverse=True):
            text = text.replace(name, " ")
        return sorted({n for n in re.findall(r"\d+", text)
                       if n not in haystack and n not in {"1", "2", "3", "4", "5"}})


# ── the readiness check: a room opens whole or not at all (13_nemo, t66) ─────────────────────
SETUP_FAULT = (
    "This room isn't ready to be opened yet, so tell whoever is running the session and "
    "they can put it right.\n\nSetup fault: not every activity in this room can be walked "
    "yet ({n} of {m} not ready: {names}). The log says why."
)


def not_walkable(folder: Path, model: str) -> list[str]:
    """One line per activity `list_activities` offers that cannot be walked: name and reasons.

    Reads files and drafts only (`PROTOTYPE_draft.walkable`), never anything the model said.
    """
    faults = []
    for activity in walk.processes(folder):
        draft = draft_for(activity, model, folder)
        if is_added(folder, activity):
            continue  # t72: an added activity is the room's own, never a setup fault (fix round 1)
        why = ["no prepared draft"] if draft is None else drafting.walkable(draft, folder)
        if why:
            faults.append(f"{activity}: {'; '.join(why)}")
    return faults


def refuse_short(folder: Path, model: str, log: Callable[[str, Any], None]) -> str | None:
    """None when every activity in the room is walkable; else log one line and return the message.

    The chat never opens on a shorter list: a room that cannot be walked whole is a setup fault
    for the operator, not a choice for the manager (ticket 66 item 4).
    """
    faults = not_walkable(folder, model)
    if not faults:
        return None
    log("setup_fault", f"room {folder.name} not opened on {model}: " + " | ".join(faults))
    names = [f.split(": ", 1)[0] for f in faults]
    return SETUP_FAULT.format(n=len(faults), m=len(walk.processes(folder)), names=", ".join(names))


def room_files(folder: Path) -> list[str]:
    """The company's files, room-relative: never `output/`, `public/` or a dot-path (t249: the one
    filter `list_room_files` and the Session's remembered set share)."""
    return sorted(
        rel for p in folder.rglob("*")
        if p.is_file()
        and not (rel := p.relative_to(folder).as_posix()).startswith(("output/", "public/"))
        and not _dotted(rel)
    )


def _an_interview(relative: str) -> bool:
    """A room path where `facts.interviews` looks: a `.md` straight under an interview home."""
    return relative.rpartition("/")[0] in interview.HOMES and relative.endswith(".md")


def _dotted(relative: str) -> bool:
    """A room path under a dot-path: nemo's working state and its turn file, never the company's."""
    return "/." in "/" + relative


@functools.cache
def wording() -> str:
    """The wording version in play (t109): the commit of the tree this skin runs from, which holds
    every source of wording at once (prompts, tools, the skin's own lines). Read once a process."""
    return subprocess.run(["git", "-C", str(Path(__file__).parent), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip() or "unknown"


def record_turn(folder: Path, turn: dict[str, Any], index: Path | None = None) -> dict[str, Any]:
    """t109: every caller's turn goes to the room's turn file through nemo's one writer, with every
    model call made for the room since the last turn (a background draft's included)."""
    calls = lanes.CALLS.take(folder)
    if turn.get("path") in LED_PATHS:  # t532: its bill; None when a call reported no cost
        costs: list[float | None] = [c.get("cost") for c in calls]
        billed = None if None in costs else round(sum(c or 0.0 for c in costs), 8)
        turn = {**turn, "billed_cost": billed}
    return turn_file.write(
        folder,
        turn,
        wording=wording(),
        calls=calls,
        index=index,
        # t132: under the id the session minted, which his acts name
        new_id=lambda: str(turn.get(TURN_ID) or uuid.uuid4().hex),
    )


def fresh_room(seed: Path, rooms: Path, code: str, archive: Path) -> Path:
    folder = rooms / code
    if folder.exists():
        archive.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(archive / f"{code}-{time.strftime('%H%M%S')}"))
    walk.mint_room(seed, rooms, code)
    return folder
