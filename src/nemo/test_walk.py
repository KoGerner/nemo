import ast
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo import conduct, handover, referee, refusal, views, walk
from nemo.bia import StaleRecord
from nemo.bia import build as build_record
from nemo.card import CardGeneratorBug, render
from nemo.door import Refused
from nemo.evidence import NOT_STATED, UNKNOWN
from nemo.figures import MTPD_SAYS, NO_MTPD_SAYS
from nemo.figures import listed as _listed
from nemo.impact import crossing
from nemo.interview import INTERVIEWS, OWNER_INTERVIEWS, PREVIEW
from nemo.record import (
    AT_STAGE,
    AT_TIME,
    DECISIONS,
    FINDINGS,
    ON_CARD,
    PENDING_REFERRALS,
    REFERRALS,
    REFUSALS,
    STATUS,
    fingerprint,
)
from nemo.referee import (
    BOUNDARY_CHECK,
    GRID_CHECK,
    MTPD_CHECK,
    QUOTES_CHECK,
    RPO_CHECK,
    RTO_CHECK,
)
from nemo.referee import review as referee_review
from nemo.room_store import PathRefused, jailed_path, read_record, write_record

# The records the referee is already held to, borrowed rather than written a second time: this
# module words what that one refuses, so a shape it can refuse and this cannot word is the defect
# these properties are for. The import points the same way the modules do, walk above referee.
from nemo.test_ask import repo_root
from nemo.test_referee import FILES as REFEREE_FILES
from nemo.test_referee import HORIZONS, RECORDS, TRANSCRIPT_PATH, valid_record
from nemo.test_referee import METHOD as REFEREE_METHOD
from nemo.text import found_in
from nemo.walk import (
    ACCEPTED,
    ACCEPTING,
    AGREE,
    ASSERTED,
    AWAITING_HUMAN,
    BIA,
    BOUND,
    CHANGED,
    CHECKED,
    CHECKED_NOTE,
    CHOSEN,
    CLOSED,
    CONDUCTED,
    CONFIRMED,
    DECISION_3,
    DECISION_4,
    DECISION_CHOSEN,
    DRAWN,
    ENDORSED,
    GRADIENT,
    HEADING,
    HEADING_2,
    HEADING_3,
    HEADING_4,
    HOLD_IT_NOW,
    IN_WORDS,
    LEAD,
    METHOD,
    METHOD_PARAMETERS,
    MISSING_SAYS,
    NAMES_NOBODY,
    NAMING,
    NOT_CAUGHT,
    NOT_WORDS,
    NOTHING_RESERVED,
    NOTHING_TO_PRESS,
    OPEN_4,
    OVERTAKEN,
    OWNER_SAYS,
    PICK,
    PICTURE_DRAWN,
    RECEIPT,
    RECORD_SAVED,
    REFUSAL_SAYS,
    REFUSED,
    REGISTER,
    RESERVED,
    RESOLVES,
    RESUMED,
    REVIEWED,
    RULE,
    RULE_2,
    RULE_3,
    RULE_4,
    RUNS,
    SAVED_NOT_FINISHED,
    SCHEMA,
    SCORED_SAYS,
    SEED_REFUSED,
    SETTLED,
    STAGE,
    STAGE_2,
    STAGE_3,
    STAGE_4,
    STANDARDISED,
    TAKEN,
    UNARGUED,
    UNNAMED,
    UNREACHED,
    Card,
    NotDrawnYet,
    _a_question,
    _advanced,
    _for_the_ask_lane,
    _gradient,
    _named,
    _part_says,
    _record_accepted,
    _reserving,
    _ways,
    check_draft,
    checked_note,
    chosen,
    held_interview,
    in_progress,
    interview_findings,
    interview_path,
    mint_room,
    move_past_stage_4,
    namings,
    onward,
    open_bia,
    pick_interview,
    processes,
    record_card,
    record_file,
    refused_says,
    report,
    resume,
    run_file,
    seed_problems,
    where_it_stands,
)

#: The one record these Slaughter walks land (ticket 235: one per process).
RECORD = record_file("Slaughter")

METHOD_FILE = {
    "org": "Marschkamp Fleisch GmbH & Co. KG",
    "time_horizons": ["0–4 h", "8 h", "24 h"],
    "scenarios": [{"id": "financial", "name": "Financial"}],
    "severity_scale": [{"level": level, "label": str(level)} for level in range(1, 6)],
    "intolerability_threshold": 4,
    "rpo_vocabulary": ["0 h (no loss)", "4 h (ERP order data)"],
}

#: What a walk copies out of that file: the five parameters and, since ticket 143, the company it
#: names — the record's only source for the name its dependency page is titled and filed under.
COPIED_METHOD = {name: METHOD_FILE[name] for name in (*METHOD_PARAMETERS, "org")}


def room(tmp_path, transcripts=("Slaughter", "Sales"),
         register=("Slaughter", "Cooling, storage and dispatch"), method=METHOD_FILE):
    """A room folder holding what ticket 02's seed ships: transcripts, a register, a method."""
    folder = tmp_path / "demo-1"
    (folder / INTERVIEWS).mkdir(parents=True)
    for index, department in enumerate(transcripts):
        (folder / INTERVIEWS / f"26_08_0{index}_interview.md").write_text(
            f"---\ndepartment: {department}\n---\n\n# {department} interview\n", encoding="utf-8")
    (folder / REGISTER).parent.mkdir(parents=True)
    (folder / REGISTER).write_text(json.dumps({
        "KA-01": {"asset_id": "KA-01", "department": register[0] if register else None,
                  "consumers": [{"department": name} for name in register[1:]]},
    }), encoding="utf-8")
    if method is not None:
        (folder / METHOD).parent.mkdir(parents=True)
        (folder / METHOD).write_text(json.dumps(method), encoding="utf-8")
    return folder


def prepared_room(tmp_path, **fields):
    """ADR-0011's own room: a chat that arrives at stage 1 with a run on file and nothing decided.

    `room` above ships no `output/.bia-runs/` at all, and every other test in this file walks from
    that — which is why the missing identity went unmeasured until the 2026-09-13 code review.
    """
    folder = room(tmp_path)
    write_record(folder, run_file("Slaughter"), {
        "schema": SCHEMA, "room": folder.name, "process": "Slaughter", "stage": STAGE,
        "status": AWAITING_HUMAN, "decisions": [], **fields}, 0)
    return folder


def without_telemetry(decision):
    """One decision with its telemetry taken off: a test about what a manager decided should not
    have to restate when he decided it, what he was looking at and what the referee refused. Those
    three have tests of their own at the end of this file."""
    return {key: value for key, value in decision.items()
            if key not in (AT_TIME, ON_CARD, REFUSALS)}


def said(folder, card, words=AGREE, **picked):
    """A card answered the way a manager answers one: typed words, through the one door.

    Every test in this file goes through `walk.answer` and none through the stage behind it
    (ADR-0013). The revision travels from the card that was read, which is the whole of the
    compare-and-set — a helper that looked the current revision up here would compare it against
    itself and every guard below would pass over a no-op (second-opinion finding 5, 2026-09-14).
    """
    return walk.answer(folder, card.activities[0], words, card.revision, **picked)[0]


def moved_on(folder, process="Slaughter"):
    """A write that lands in the room after a card was read: the revision moves, the stage does not.

    What the guard is for now that one manager has one chat — a second tab, a re-scan, a walk
    resumed after a half-landed write — and what makes a stale answer testable through the door:
    the words still route to the stage the manager was reading, and lose there.
    """
    run = read_record(folder, run_file(process)) or {
        "process": process, "room": folder.name, "schema": 1, "decisions": []}
    write_record(folder, run_file(process), _without_revision(run), run.get("revision", 0))


#: The record another walk in the same room left behind while this press was being answered.
ANOTHER_WALKS = {"run_id": "somebody else's"}


def overtaken_at_the_record(folder, card, monkeypatch, words=ENDORSED):
    """`said`, with another walk's record landing between this page being drawn and this answer
    being written.

    The race is the whole of what the guard is for and there is no way to sit inside it from
    outside the door: the door re-reads the room, so a record written before the call is simply
    the record the card was drawn against. Standing in for `write_record` is therefore how the
    stranger's bytes get in at the one moment that matters — the press's first write, which is
    the room's BIA record — and the real one goes back before they land, so nothing after that
    first write is intercepted and the press finishes on the product's own lines.
    """
    landing = walk.write_record

    def overtaking(room_folder, path, record, revision):
        assert path == RECORD, f"the press wrote {path} before the record it was drawn against"
        monkeypatch.setattr(walk, "write_record", landing)
        landing(room_folder, RECORD, ANOTHER_WALKS, 0)
        return landing(room_folder, path, record, revision)

    monkeypatch.setattr(walk, "write_record", overtaking)
    return said(folder, card, words)


def typed(folder, words, process="Slaughter"):
    """Words typed into the box with no card of the manager's own in front of him.

    The door arbitrates between the four claimants on that box and this is how the tests below
    watch it do so: an empty answer is the walk saying the words were never its own — nothing of
    it moved, and they are the ask lane's.
    """
    run = read_record(folder, run_file(process)) or {}
    return walk.answer(folder, process, words, run.get("revision", 0))


def saved_only(folder, card, words=ENDORSED):
    """Stage 4 answered and the walk stopped before the picture — ADR-0010's ordinary stop.

    The second movement is the one that does not run, so it is what is held back rather than the
    door that is worked around: the manager types the same words either way.
    """
    with pytest.MonkeyPatch.context() as stopped:
        stopped.setattr(walk, "_draw_graph", lambda _folder, drawn: drawn)
        return said(folder, card, words)


# ── which processes are on file ──────────────────────────────────────────────


def test_both_sources_are_offered_each_once_in_alphabetical_order(tmp_path):
    assert processes(room(tmp_path)) == ["Cooling, storage and dispatch", "Sales", "Slaughter"]


def test_a_room_with_no_files_offers_nothing(tmp_path):
    assert processes(tmp_path / "empty") == []


def test_a_department_named_only_in_the_register_is_still_offered(tmp_path):
    assert "Cooling, storage and dispatch" in processes(room(tmp_path, transcripts=()))


def test_a_department_named_only_in_the_transcripts_is_still_offered(tmp_path):
    assert "Sales" in processes(room(tmp_path, register=()))


def test_a_transcript_is_utf_8_wherever_the_skin_runs(tmp_path):
    """The room's files are UTF-8 because a company wrote them, not because this box is set up
    that way.

    **This test runs in a subprocess, and that is the whole point of it.** The obvious version —
    `locale.setlocale(locale.LC_CTYPE, "C")` around the call — passes against code that reads on
    the machine's default, because the interpreter has already fixed its filesystem and default
    encodings by the time a test can move the locale. It therefore proved nothing, and the mutant
    it was supposed to kill (`nemo.interview.text` reading at the locale's discretion) survived it.
    It is driven from here, through `processes`, because a room's own files are what a walk reads.
    A child
    interpreter started under `LC_ALL=C` with UTF-8 mode and PEP 538 coercion both off really does
    have `locale.getencoding() == "ANSI_X3.4-1968"`, and there a default-encoding read of this
    transcript raises `UnicodeDecodeError`. The child prints the process names as a JSON array
    with `ensure_ascii`, because its stdout is ASCII too.
    """
    name = "Kühlung, Lager und Versand"
    folder = room(tmp_path, transcripts=(name,), register=())
    child = subprocess.run(
        [sys.executable, "-c",
         "import json,pathlib,sys;from nemo.walk import processes;"
         "print(json.dumps(processes(pathlib.Path(sys.argv[1]))))", str(folder)],
        capture_output=True, text=True,
        env={**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0",
             "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    assert child.returncode == 0, f"an ASCII-locale box cannot read the room:\n{child.stderr}"
    assert json.loads(child.stdout) == [name]


def test_a_transcript_that_is_not_utf_8_is_a_finding_naming_it_and_never_a_crash(tmp_path):
    """Ticket 237: one Windows-1252 file in the customer's own store is ordinary input.

    The rest of the room still walks, and the file is named to the operator who can re-save it.
    No encoding is guessed: bytes that are not UTF-8 are not evidence this reader can quote.
    """
    seed = room(tmp_path)
    bad = f"{INTERVIEWS}/26_08_09_interview.md"
    (seed / bad).write_bytes("---\ndepartment: Kühlung\n---\n\n# Kühlung\n".encode("cp1252"))

    assert processes(seed) == ["Cooling, storage and dispatch", "Sales", "Slaughter"]
    assert open_bia(seed, "Sales").activities == ("Sales",)
    assert seed_problems(seed) == [NAMES_NOBODY.format(path=bad)]
    with pytest.raises(Refused) as refusal:
        mint_room(seed, rooms_folder(tmp_path), "adler-7ycyet")
    assert bad in refusal.value.operator


def test_a_register_entry_naming_nothing_contributes_no_process(tmp_path):
    folder = room(tmp_path, register=())
    (folder / REGISTER).write_text(json.dumps({"KA-01": {"department": "  "}, "rows": [1, None]}),
                                   encoding="utf-8")
    assert processes(folder) == ["Sales", "Slaughter"]


@pytest.mark.parametrize(("garbage", "error"), [
    (b"{not json", "JSONDecodeError: "), (b"", "JSONDecodeError: "),
    ('{"K": "K\u00e4lte"}'.encode("cp1252"), "UnicodeDecodeError: ")])
def test_an_unreadable_register_is_named_and_the_interviews_still_offered(tmp_path, garbage,
                                                                          error):
    """Ticket 297: a register that is not valid JSON is named, never read as an empty one.

    The menu is what the room's other sources name, and why the register cannot be read is the
    parse error itself, which is what the operator who re-saves the file needs.
    """
    folder = room(tmp_path)
    (folder / REGISTER).write_bytes(garbage)
    assert processes(folder) == ["Sales", "Slaughter"]
    assert (walk.unreadable_register(folder) or "").startswith(error)


def test_a_missing_or_valid_register_is_not_unreadable(tmp_path):
    folder = room(tmp_path)
    assert walk.unreadable_register(folder) is None
    (folder / REGISTER).unlink()
    assert walk.unreadable_register(folder) is None
    assert processes(folder) == ["Sales", "Slaughter"]


def test_the_unreadable_register_note_names_the_file():
    assert REGISTER in walk.UNREADABLE_REGISTER.format(path=REGISTER)


@pytest.mark.parametrize("path", [REGISTER, METHOD, walk.ADDED])
@pytest.mark.parametrize(("garbage", "error"), [
    (b"{not json", "JSONDecodeError: "), (b"", "JSONDecodeError: "),
    ('{"K": "Kälte"}'.encode("cp1252"), "UnicodeDecodeError: ")])
def test_an_unreadable_room_file_is_named_with_its_parse_error(tmp_path, path, garbage, error):
    """Ticket 299: the register, the method and the added activities, as 297 did the register."""
    folder = room(tmp_path)
    (folder / path).parent.mkdir(parents=True, exist_ok=True)
    (folder / path).write_bytes(garbage)
    named, why = walk.unreadable_file(folder) or ("", "")
    assert named == path
    assert why.startswith(error)
    assert walk.UNREADABLE.format(what=walk.UNREADABLE_FILES[path], path=path).count(path) == 1


def test_missing_or_valid_room_files_are_not_unreadable(tmp_path):
    folder = room(tmp_path)
    assert walk.unreadable_file(folder) is None
    (folder / walk.ADDED).parent.mkdir(parents=True)
    (folder / walk.ADDED).write_text('{"activities": []}', encoding="utf-8")
    assert walk.unreadable_file(folder) is None
    for path in (REGISTER, METHOD, walk.ADDED):
        (folder / path).unlink()
    assert walk.unreadable_file(folder) is None


def test_the_register_is_named_first_and_its_note_is_297s():
    assert next(iter(walk.UNREADABLE_FILES)) == REGISTER
    assert walk.UNREADABLE_REGISTER == walk.UNREADABLE.format(
        what=walk.UNREADABLE_FILES[REGISTER], path="{path}")


def test_an_unreadable_added_activities_file_offers_what_the_room_else_names(tmp_path):
    """t299 (b): the menu is what the interviews and the register name, as with no such file."""
    folder = room(tmp_path)
    (folder / walk.ADDED).parent.mkdir(parents=True)
    (folder / walk.ADDED).write_bytes(b"{not json")
    assert processes(folder) == ["Cooling, storage and dispatch", "Sales", "Slaughter"]


# ── 241 slice 4 (t72): an activity a manager added is on the menu, as the phone offers it ────────
#: The room file the phone writes an added activity to (13_nemo, t72), in the shape it writes.
ADDED_ON_THE_PHONE = "output/.proto/added-activities.json"


def added(folder, *names):
    """The room as the phone leaves it after he added `names`, by either of its two routes."""
    (folder / "output/.proto").mkdir(parents=True, exist_ok=True)
    (folder / ADDED_ON_THE_PHONE).write_text(json.dumps({"activities": [
        {"name": name, "route": "add_activity", "added_at": "2026-10-02T09:00:00"}
        for name in names]}), encoding="utf-8")
    return folder


def test_an_activity_he_added_is_offered_beside_the_room_s_two_sources(tmp_path):
    folder = added(room(tmp_path), "Payroll", "Sales", "Bottling")
    assert processes(folder) == [
        "Bottling", "Cooling, storage and dispatch", "Payroll", "Sales", "Slaughter"]


def test_an_activity_he_added_to_a_room_with_no_files_is_its_whole_menu(tmp_path):
    assert processes(added(tmp_path / "empty", "Payroll")) == ["Payroll"]


@pytest.mark.parametrize("held", [{}, {"activities": None}, {"activities": []}])
def test_an_added_list_holding_no_activity_adds_nothing(tmp_path, held):
    folder = added(room(tmp_path))
    (folder / ADDED_ON_THE_PHONE).write_text(json.dumps(held), encoding="utf-8")
    assert processes(folder) == ["Cooling, storage and dispatch", "Sales", "Slaughter"]


def test_the_added_list_is_the_one_room_file_the_phone_writes_it_to():
    assert walk.ADDED == ADDED_ON_THE_PHONE


# ── the stage 1 card ─────────────────────────────────────────────────────────


def test_the_card_is_headed_for_stage_one_of_five(tmp_path):
    card = open_bia(room(tmp_path), "Slaughter")
    assert card.heading == "Stage 1 of 5 · Scope"  # t432: the short name
    assert card.subtitle == "Identification of scope"  # t432: the long line, the subtitle only


def test_the_card_proposes_exactly_one_activity(tmp_path):
    assert open_bia(room(tmp_path), "Slaughter").activities == ("Slaughter",)


def test_the_card_offers_one_button_and_nothing_else(tmp_path):
    assert open_bia(room(tmp_path), "Sales").buttons == (AGREE,)


def test_the_card_carries_the_four_way_gradient_underneath(tmp_path):
    assert open_bia(room(tmp_path), "Sales").gradient == GRADIENT
    assert GRADIENT == ("endorsed", "endorsed with reservations", "needs discussion", "blocked")


def test_the_card_asks_for_one_decision_and_states_its_rule(tmp_path):
    card = open_bia(room(tmp_path), "Slaughter")
    assert "Slaughter" in card.decision and card.rule


def test_no_caller_can_name_the_stage_it_wants_served(tmp_path):
    assert list(inspect.signature(open_bia).parameters) == ["room_folder", "process"]


def test_the_card_says_which_stage_it_is_as_a_number_the_referee_can_read(tmp_path):
    """The heading is for the manager; `stage` is the same fact where a later stage reads it."""
    assert open_bia(room(tmp_path), "Slaughter").stage == STAGE == 1


def test_a_decision_recorded_against_stage_one_that_is_not_yes_agrees_nothing(tmp_path):
    """Agreed is stage one *and* yes. Either half alone is a card still waiting to be pressed."""
    folder = room(tmp_path)
    write_record(folder, run_file("Slaughter"),
                 {"decisions": [{"stage": STAGE, "decided": "no", "gradient": "blocked"}]}, 0)
    card = open_bia(folder, "Slaughter")
    assert card.buttons == (AGREE,) and card.gradient == GRADIENT


# ── the Source: line ─────────────────────────────────────────────────────────


def test_the_source_line_names_every_file_the_proposal_was_read_from(tmp_path):
    card = open_bia(room(tmp_path), "Slaughter")
    assert card.source_line == (
        f"Source: {METHOD}, {REGISTER}, {INTERVIEWS}/26_08_00_interview.md")


def test_the_source_line_names_no_file_the_proposal_did_not_read(tmp_path):
    card = open_bia(room(tmp_path), "Sales")
    assert REGISTER not in card.sources
    assert f"{INTERVIEWS}/26_08_00_interview.md" not in card.sources


def test_every_file_the_source_line_names_is_a_file_in_the_room(tmp_path):
    folder = room(tmp_path)
    assert all((folder / path).is_file() for path in open_bia(folder, "Slaughter").sources)


def test_a_room_without_a_method_file_names_none(tmp_path):
    folder = room(tmp_path, method=None)
    assert METHOD not in open_bia(folder, "Slaughter").sources


# ── the method is the room's own ─────────────────────────────────────────────


def test_the_method_is_copied_from_the_rooms_own_file_parameter_for_parameter(tmp_path):
    card = open_bia(room(tmp_path), "Slaughter")
    # ...and the company it names (ticket 143), which the page the record draws is filed under.
    assert card.method == COPIED_METHOD


def test_nothing_appears_in_the_method_that_the_file_does_not_say(tmp_path):
    thin = {"time_horizons": ["8 h"], "intolerability_threshold": 3}
    assert open_bia(room(tmp_path, method=thin), "Slaughter").method == thin


def test_the_method_copy_carries_the_company_the_file_names(tmp_path):
    """Ticket 143: the record names the company it is about, and its only source for the name is
    this copy. Left behind, every record names nobody."""
    named = {**METHOD_FILE, "org": "Marschkamp Fleisch GmbH & Co. KG"}
    assert open_bia(room(tmp_path, method=named), "Slaughter").method[
        "org"] == "Marschkamp Fleisch GmbH & Co. KG"


def test_a_method_file_that_names_no_company_puts_none_in_the_copy(tmp_path):
    anonymous = {name: value for name, value in METHOD_FILE.items() if name != "org"}
    assert "org" not in open_bia(room(tmp_path, method=anonymous), "Slaughter").method


def test_the_threshold_is_read_rather_than_assumed(tmp_path):
    method = {**METHOD_FILE, "intolerability_threshold": 2}
    assert open_bia(room(tmp_path, method=method), "Slaughter").method[
        "intolerability_threshold"] == 2


# ── one press ────────────────────────────────────────────────────────────────


def test_one_press_puts_the_decision_on_file_with_the_companys_files(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert (folder / "output/.bia-runs/slaughter.json").is_file()


def test_the_run_file_says_stage_one_was_decided_yes(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    saved = read_record(folder, run_file("Slaughter"))
    assert [without_telemetry(each) for each in saved["decisions"]] == [
        {"stage": 1, "decided": "yes", "gradient": "endorsed"}]


def test_the_run_file_names_the_room_the_process_and_its_own_identity(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["room"] == "demo-1" and saved["process"] == "Slaughter"
    assert saved["run_id"] and saved["revision"] == 1


def test_the_run_file_says_the_walk_is_waiting_on_the_human(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert read_record(folder, run_file("Slaughter"))["status"] == AWAITING_HUMAN


def test_the_run_files_identity_is_a_minted_uuid_and_not_a_placeholder(tmp_path):
    """A run mints its own identity, which is the half ticket 15's binding will later check."""
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    said(folder, open_bia(folder, "Sales"))
    minted = [read_record(folder, run_file(name))["run_id"] for name in ("Slaughter", "Sales")]
    assert [uuid.UUID(run_id).version for run_id in minted] == [4, 4]
    assert minted[0] != minted[1]


def test_the_run_file_says_which_schema_it_was_written_under(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert read_record(folder, run_file("Slaughter"))["schema"] == SCHEMA == 1


def test_the_run_file_keeps_the_files_the_proposal_was_read_from(tmp_path):
    """The Source: line is on the record too, so a later stage need not re-read the room to say
    where its scope came from."""
    folder = room(tmp_path)
    card = open_bia(folder, "Slaughter")
    said(folder, card)
    assert read_record(folder, run_file("Slaughter"))["sources"] == list(card.sources)
    assert card.sources


def test_a_press_carries_every_decision_already_on_the_record_forward(tmp_path):
    """A record is added to, never replaced: an earlier answer is not lost by a later press."""
    folder = room(tmp_path)
    earlier = {"stage": STAGE, "decided": "no", "gradient": "blocked"}
    write_record(folder, run_file("Slaughter"), {"decisions": [earlier]}, 0)
    said(folder, open_bia(folder, "Slaughter"))
    assert [without_telemetry(each) for each in
            read_record(folder, run_file("Slaughter"))["decisions"]] == [
        earlier, {"stage": STAGE, "decided": "yes", "gradient": GRADIENT[0]}]


def test_a_run_that_was_already_on_file_is_given_an_identity_at_the_first_press(tmp_path):
    folder = prepared_room(tmp_path)
    assert "run_id" not in read_record(folder, run_file("Slaughter"))
    said(folder, open_bia(folder, "Slaughter"))
    minted = read_record(folder, run_file("Slaughter"))["run_id"]
    assert uuid.UUID(minted).version == 4


def test_a_run_that_was_already_on_file_is_given_the_method_and_the_sources_too(tmp_path):
    """The same cause: a run reaching stage 3 with no lenses drafts over an empty grid."""
    folder = prepared_room(tmp_path)
    card = open_bia(folder, "Slaughter")
    said(folder, card)
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["method"] == card.method and saved["sources"] == list(card.sources)


def test_an_identity_a_run_already_carries_is_not_minted_over(tmp_path):
    """A second minting would break the binding this repairs: the record on disk would name a run
    the walk is no longer called."""
    folder = prepared_room(tmp_path, run_id="already its own")
    said(folder, open_bia(folder, "Slaughter"))
    assert read_record(folder, run_file("Slaughter"))["run_id"] == "already its own"


def test_the_confirming_card_is_the_same_stage_heading_and_activity(tmp_path):
    folder = room(tmp_path)
    opened = open_bia(folder, "Slaughter")
    confirmed = said(folder, opened)
    assert confirmed.stage == STAGE
    assert confirmed.heading == HEADING
    assert confirmed.activities == ("Slaughter",)
    assert confirmed.sources == opened.sources
    assert confirmed.method == opened.method


def test_the_confirming_card_states_no_rule_because_nothing_is_left_to_press(tmp_path):
    folder = room(tmp_path)
    assert said(folder, open_bia(folder, "Slaughter")).rule == ""


def test_the_confirming_card_carries_the_revision_it_has_just_written(tmp_path):
    """The next press compares against this, so a card handing back a stale number loses a walk."""
    folder = room(tmp_path)
    confirmed = said(folder, open_bia(folder, "Slaughter"))
    assert confirmed.revision == 1 == confirmed.saved["revision"]


def test_the_run_file_carries_the_method_the_walk_is_walking_to(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert read_record(folder, run_file("Slaughter"))["method"] == open_bia(
        folder, "Slaughter").method


def test_the_press_says_so_in_a_colleagues_sentence(tmp_path):
    folder = room(tmp_path)
    card = said(folder, open_bia(folder, "Slaughter"))
    assert card.body == ("Got it. The scope for Slaughter is agreed. That's stage 1 of 5 done, "
                         "and there's nothing more to do here yet.")
    assert card.body == CONFIRMED.format(process="Slaughter")


def test_after_the_press_the_button_is_gone_and_nothing_is_asked(tmp_path):
    folder = room(tmp_path)
    card = said(folder, open_bia(folder, "Slaughter"))
    assert card.buttons == () and card.decision == "" and card.gradient == ()


def test_the_run_file_is_named_for_the_process(tmp_path):
    assert run_file("Slaughter") == "output/.bia-runs/slaughter.json"
    assert run_file("Cooling, storage and dispatch") == (
        "output/.bia-runs/cooling-storage-and-dispatch.json")


def test_stage_one_writes_no_document_for_the_human_to_read(tmp_path):
    folder = room(tmp_path)
    before = {path for path in folder.rglob("*") if path.is_file()}
    said(folder, open_bia(folder, "Slaughter"))
    after = {path for path in folder.rglob("*") if path.is_file()}
    assert after - before == {folder / run_file("Slaughter")}


# ── coming back ──────────────────────────────────────────────────────────────


def test_coming_back_is_told_as_a_fact_about_my_work(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert open_bia(folder, "Slaughter").body == RESUMED.format(process="Slaughter")


def test_coming_back_does_not_ask_for_the_scope_a_second_time(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    card = open_bia(folder, "Slaughter")
    assert card.heading == HEADING
    assert card.buttons == () and card.decision == "" and card.rule == ""


def test_coming_back_carries_what_was_saved(tmp_path):
    folder = room(tmp_path)
    saved = said(folder, open_bia(folder, "Slaughter")).saved
    assert open_bia(folder, "Slaughter").saved == saved


def test_a_process_nobody_has_walked_is_untouched_by_another_processs_decision(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert open_bia(folder, "Sales").buttons == (AGREE,)


# ── two writers ──────────────────────────────────────────────────────────────


def test_a_press_that_was_overtaken_does_not_land_on_top_of_the_newer_record(tmp_path):
    folder = room(tmp_path)
    stale = open_bia(folder, "Slaughter")
    moved_on(folder)
    newer = read_record(folder, run_file("Slaughter"))
    said(folder, stale)
    assert read_record(folder, run_file("Slaughter")) == newer


def test_the_overtaken_writer_is_told_in_a_colleagues_sentence(tmp_path):
    folder = room(tmp_path)
    stale = open_bia(folder, "Slaughter")
    moved_on(folder)
    body = said(folder, stale).body
    assert body.startswith("Someone else saved this BIA while you were reading")
    assert "revision" not in body and "StaleRunRevision" not in body


def test_the_overtaken_press_leaves_one_decision_for_stage_one_not_two(tmp_path):
    folder = room(tmp_path)
    stale = open_bia(folder, "Slaughter")
    moved_on(folder)
    said(folder, stale)
    assert [without_telemetry(each) for each in
            read_record(folder, run_file("Slaughter"))["decisions"]] == []


def test_the_overtaken_writer_is_shown_the_record_that_won(tmp_path):
    """Being told you lost is no use without the newer record: the card comes back current."""
    folder = room(tmp_path)
    stale = open_bia(folder, "Slaughter")
    moved_on(folder)
    newer = read_record(folder, run_file("Slaughter"))
    overtaken = said(folder, stale)
    assert overtaken.saved == newer
    assert overtaken.revision == 1
    assert overtaken.buttons == (AGREE,), "the card that won is the one still to be answered"


def test_the_overtaken_card_still_names_the_process_it_was_about(tmp_path):
    folder = room(tmp_path)
    stale = open_bia(folder, "Slaughter")
    moved_on(folder)
    overtaken = said(folder, stale)
    assert overtaken.activities == ("Slaughter",)
    assert overtaken.body == OVERTAKEN + " " + open_bia(folder, "Slaughter").body


def test_a_second_press_on_a_current_card_advances_the_record(tmp_path):
    """The compare-and-set is on the revision the card read, not on the decision it carries."""
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    card = open_bia(folder, "Slaughter")
    assert card.revision == 1


# ── the room a scan mints ────────────────────────────────────────────────────
# Ticket 50. A scan of a code nobody has used mints a room out of the seed, once, whole; every
# arrival after the first is a no-op. Fifty phones do this within a minute of each other, so the
# race is the story rather than a caveat on it.

#: How many scans arrive at once in the race tests. Fifty is ADR-0017's number and the QA's loop.
SCANS = 50


def rooms_folder(tmp_path):
    """The rooms folder a mint may put a room **inside** and may never create itself (ticket 22)."""
    folder = tmp_path / "rooms"
    folder.mkdir()
    return folder


def tree(folder):
    """Every path under a folder, relative — what "whole, file for file" is measured as."""
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def scanned_at_once(codes, mint):
    """Every code scanned at one moment: a thread each, all released off the same barrier.

    The race is run rather than argued, so the barrier is the whole point — a pool that let the
    first scan finish before the second started would prove nothing about fifty phones in a hall.
    What comes back is one answer per code, in the order given.
    """
    ready = threading.Barrier(len(codes))

    def scan(code):
        ready.wait()
        return mint(code)

    with ThreadPoolExecutor(len(codes)) as pool:
        return list(pool.map(scan, codes))


def test_a_scan_of_an_unknown_code_mints_the_whole_seed(tmp_path):
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    assert mint_room(seed, folder, "adler-7ycyet") is True
    minted = folder / "adler-7ycyet"
    assert tree(minted) == tree(seed), "the room is not the seed, file for file"
    assert processes(minted) == processes(seed)
    assert (minted / METHOD).is_file()


def test_a_freshly_minted_room_ships_a_bia_in_progress_and_output_with_it(tmp_path):
    """**ADR-0011: a minted room ships a BIA in progress on purpose**, and `output/` is where that
    record lives — it is seeded deliberately, not seeding debris somebody forgot to delete.

    Emptiness was never the test and cannot be: a room that holds nothing has to interrogate the
    manager about his own company, and the bar is three typed inputs. Terminal-eligibility is the
    test — nothing here is a thing a signature could close over — and the defence against a walk
    closing over work nobody did is ticket 15's `run_id` binding, not an empty room. Deleting
    `output/` from the seed to make a minted room look safer breaks the product instead.
    """
    seed = room(tmp_path)
    said(seed, open_bia(seed, "Slaughter"))
    mint_room(seed, rooms_folder(tmp_path), "adler-7ycyet")
    minted = tmp_path / "rooms" / "adler-7ycyet"

    assert (minted / "output").is_dir(), "a minted room ships no output/ (ADR-0011)"
    assert in_progress(minted) == ["slaughter"]
    assert not (minted / RECORD).exists(), "a minted room ships something a signature could close"


def test_a_second_scan_is_a_no_op_and_keeps_what_the_delegate_answered(tmp_path):
    """The reload on stage: the delegate lands back in the room they have, answers and all."""
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    mint_room(seed, folder, "adler-7ycyet")
    minted = folder / "adler-7ycyet"
    said(minted, open_bia(minted, "Slaughter"))
    answered = read_record(minted, run_file("Slaughter"))

    assert mint_room(seed, folder, "adler-7ycyet") is False
    assert read_record(minted, run_file("Slaughter")) == answered, "the seed was copied over it"
    assert [path.name for path in folder.iterdir()] == ["adler-7ycyet"]


def test_fifty_scans_of_one_code_at_the_same_moment_make_one_whole_room(tmp_path):
    """The race, run rather than argued: fifty threads, one room, and nothing half-copied left.

    One `True` is the proof that the mechanism decides a winner — the other forty-nine copied the
    seed too and threw their copy away. The listing is what says no staging folder survives.
    """
    seed, folder = room(tmp_path), rooms_folder(tmp_path)

    minted = scanned_at_once(["adler-7ycyet"] * SCANS, lambda code: mint_room(seed, folder, code))

    assert minted.count(True) == 1, f"{minted.count(True)} scans of one code each made a room"
    assert [path.name for path in folder.iterdir()] == ["adler-7ycyet"]
    assert tree(folder / "adler-7ycyet") == tree(seed)


def test_fifty_codes_in_a_tight_loop_give_fifty_whole_rooms(tmp_path):
    """ADR-0017's demo in one process: fifty codes at once, fifty whole rooms, no partial one."""
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    codes = [f"qa-room-{number:02d}" for number in range(1, SCANS + 1)]

    started = time.monotonic()
    minted = scanned_at_once(codes, lambda code: mint_room(seed, folder, code))
    took = time.monotonic() - started

    assert minted == [True] * SCANS
    assert sorted(path.name for path in folder.iterdir()) == codes, "a staging folder was left"
    partial = [code for code in codes if tree(folder / code) != tree(seed)]
    print(f"{len(codes)} rooms minted in {took:.2f}s, {len(partial)} partial")
    assert partial == []


def test_an_absent_rooms_folder_is_an_absent_mount_and_is_never_created(tmp_path):
    """The worst outcome in the ticket: fifty delegates each handed a brand-new room, having lost
    the one they worked in all morning. Minting puts a room *inside* the rooms folder and never
    makes the folder itself, so a mount that is away refuses exactly as it did before ticket 50."""
    with pytest.raises(Refused) as refusal:
        mint_room(room(tmp_path), tmp_path / "rooms", "adler-7ycyet")

    assert not (tmp_path / "rooms").exists(), "the mount was away and the door recreated it"
    assert "is not there" in str(refusal.value), "the mount is not named as the mount"
    assert "has no folder" in str(refusal.value), "ticket 22's operator sentence went missing"
    assert "carries no room code" not in str(refusal.value)


def test_the_absent_mount_names_the_mount_and_the_code_that_arrived(tmp_path):
    """One line in the journal has to be enough to act on. `the rooms folder is not there, so the
    room has no folder` names neither the mount to remount nor the delegate left standing in the
    hall, and an operator reading it at 09:05 learns only that something happened."""
    rooms = tmp_path / "rooms"

    with pytest.raises(Refused) as refusal:
        mint_room(room(tmp_path), rooms, "adler-7ycyet")

    assert str(rooms) in refusal.value.operator, "the mount that is away is not named"
    assert "'adler-7ycyet'" in refusal.value.operator, "the code that arrived is not named"


@pytest.mark.parametrize("code", ["..%2F..%2Fetc", ".", "..", ".minting-1", "a/b", "", "Adler"])
def test_a_code_that_is_not_a_room_code_mints_nothing(tmp_path, code):
    """Reading asks nothing of a code — a folder on disk is a room whatever it is called — but
    creating one joins the code to a path that does not exist yet, so the mint judges the shape."""
    folder = rooms_folder(tmp_path)
    assert mint_room(room(tmp_path), folder, code) is False
    assert list(folder.iterdir()) == [], f"{code!r} made something"


def test_a_mint_that_failed_for_any_other_reason_says_so_instead_of_a_lost_race(tmp_path):
    """Ticket 210 (2): `False` means another arrival won and the room is there to open. When the
    rename fails for any other reason there is no room, and the caller — the stage QR — would send
    the phone to a link that opens nothing. The error comes out instead, and nothing is left."""
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    (folder / "adler-7ycyet").write_text("a stray file where a room would go")

    with pytest.raises(OSError):
        mint_room(seed, folder, "adler-7ycyet")

    assert [path.name for path in folder.iterdir()] == ["adler-7ycyet"], "staging was left behind"
    assert (folder / "adler-7ycyet").is_file(), "the stray file was taken for a room"


def test_a_copy_that_failed_part_way_leaves_no_staging_folder_behind(tmp_path):
    """The copy runs inside the cleanup, not outside it: a seed file the box cannot read fails
    `copytree` with a partial `.minting-*` on disk, and the rooms folder keeps none of it."""
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    unreadable = seed / "08_Prior-Cycle" / "unreadable.md"
    unreadable.parent.mkdir(parents=True, exist_ok=True)
    unreadable.write_text("x")
    unreadable.chmod(0o000)
    try:
        with pytest.raises(OSError):
            mint_room(seed, folder, "adler-7ycyet")
    finally:
        unreadable.chmod(0o600)

    assert list(folder.iterdir()) == [], "a partial staging folder was left in the rooms folder"


def test_a_rooms_folder_nothing_can_be_written_to_says_what_actually_went_wrong(tmp_path):
    """The cleanup never speaks over the failure: with no staging folder made, tidying it away
    must not raise a FileNotFoundError of its own in place of the refusal that matters."""
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    folder.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            mint_room(seed, folder, "adler-7ycyet")
    finally:
        folder.chmod(0o700)

    assert list(folder.iterdir()) == []


def test_a_seed_that_is_not_there_mints_nothing_and_says_nothing(tmp_path):
    """A box with no seed keeps the door ticket 22 built: a well-formed code for a room nobody
    minted is refused, by `checked_room_folder`, because there was never anything to mint from."""
    folder = rooms_folder(tmp_path)
    assert mint_room(tmp_path / "no-seed", folder, "adler-7ycyet") is False
    assert list(folder.iterdir()) == []


# ── the admission check, which runs at mint ──────────────────────────────────


def test_the_seed_ticket_02_ships_passes_the_walks_own_gates(tmp_path):
    """G4(a): the seed passes every gate the walk applies, so admission returns zero problems."""
    assert seed_problems(room(tmp_path)) == []


def test_a_capture_the_walk_cannot_read_as_evidence_refuses_the_scan(tmp_path):
    """The Stage 2 capture with the sections the walk's gates require taken out of it: its front
    matter names no department, so no stage can bind it and the delegate cannot reach stage 5.

    Better to refuse a scan than to seat somebody in front of a BIA that stops at stage 2. What
    the two audiences read is the second half of this: the operator is told enough to find the
    file, and the delegate reads one sentence with no path, no field name and no fault in it.
    """
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    capture = sorted((seed / INTERVIEWS).glob("*.md"))[0]
    capture.write_text("# Slaughter interview\n", encoding="utf-8")

    with pytest.raises(Refused) as refusal:
        mint_room(seed, folder, "adler-7ycyet")

    assert list(folder.iterdir()) == [], "a refused scan left a folder behind"
    assert capture.name in refusal.value.operator
    for machine in (capture.name, "department", "/", "Traceback"):
        assert machine not in str(refusal.value), f"the delegate reads {machine!r}"


def test_a_seed_with_nothing_to_press_refuses_the_scan(tmp_path):
    """A room offering no process leaves typing as the only way in, which is no way in at all."""
    seed = tmp_path / "bare-seed"
    (seed / INTERVIEWS).mkdir(parents=True)
    assert seed_problems(seed)
    with pytest.raises(Refused):
        mint_room(seed, rooms_folder(tmp_path), "adler-7ycyet")


def test_a_refused_seed_says_one_thing_to_the_delegate_and_another_to_the_operator(tmp_path):
    """The two audiences of one refusal, read side by side over a seed that fails both gates.

    The delegate gets exactly the sentence `docs/voice.md` §3.1 allows and nothing assembled
    around it — a bare `None` where that sentence should be is still path-free and fault-free, so
    only reading the whole line catches it. The operator gets the seed to open and every problem
    with it, run together in one readable line rather than concatenated into one word.
    """
    seed = tmp_path / "bare-seed"
    (seed / INTERVIEWS).mkdir(parents=True)
    (seed / INTERVIEWS / "nobody.md").write_text("# a capture of nothing\n", encoding="utf-8")
    problems = seed_problems(seed)
    assert problems == [NOTHING_TO_PRESS, NAMES_NOBODY.format(path=f"{INTERVIEWS}/nobody.md")]

    with pytest.raises(Refused) as refusal:
        mint_room(seed, rooms_folder(tmp_path), "adler-7ycyet")

    assert str(refusal.value) == SEED_REFUSED, "the delegate reads something other than the line"
    assert str(seed) in refusal.value.operator, "the seed to go and open is not named"
    assert "; ".join(problems) in refusal.value.operator, "the problems do not read as a list"


def test_admission_runs_at_every_mint_and_never_at_a_second_arrival(tmp_path):
    """Deterministic and uncached, which is why fifty broken scans are fifty refusals — and why
    the fifty-first scan of a room that already exists pays nothing for the check."""
    seed, folder = room(tmp_path), rooms_folder(tmp_path)
    mint_room(seed, folder, "adler-7ycyet")
    sorted((seed / INTERVIEWS).glob("*.md"))[0].write_text("nothing", encoding="utf-8")

    assert mint_room(seed, folder, "adler-7ycyet") is False, "a broken seed refused an old room"
    for code in (f"qa-broken-{number}" for number in range(1, 4)):
        with pytest.raises(Refused):
            mint_room(seed, folder, code)
    assert [path.name for path in folder.iterdir()] == ["adler-7ycyet"]


def test_a_finished_walk_is_not_in_progress(tmp_path):
    folder = room(tmp_path)
    write_record(folder, run_file("Slaughter"), {"status": "closed"}, 0)
    assert in_progress(folder) == []


# ── the voice ────────────────────────────────────────────────────────────────

BANNED = ("prepare_bia_stage", "user_confirmed", "save_token", "awaiting_human", "run_id",
          "revision", "record", "referee", "finding", "gradient", "nemo", ".json", ".md", "/")


@pytest.mark.parametrize("process", ["Slaughter", "Sales"])
def test_the_card_names_no_machine_identifier_outside_its_source_line(tmp_path, process):
    card = open_bia(room(tmp_path), process)
    prose = " ".join((card.body, card.heading, card.decision, card.rule, *card.buttons))
    assert not [word for word in BANNED if word in prose]


def test_the_card_is_prose_rather_than_a_numbered_list_of_machine_actions(tmp_path):
    body = open_bia(room(tmp_path), "Slaughter").body
    assert not [line for line in body.splitlines() if line.strip()[:2] in ("1.", "2.", "1)")]
    assert body.count(". ") >= 2


def test_the_proposal_says_which_of_the_two_sources_the_process_stands_in(tmp_path):
    folder = room(tmp_path)
    assert "your interview transcripts and your dependency register" in open_bia(
        folder, "Slaughter").body
    assert "your dependency register, with" in open_bia(
        folder, "Cooling, storage and dispatch").body
    assert "your interview transcripts, with" in open_bia(folder, "Sales").body


# ── properties ───────────────────────────────────────────────────────────────
#
# The examples above walk the room ticket 02 ships. These say what holds for any process a room
# might name — because the manager never types one, so the name on the card is whatever the
# company's own files spell, and a German department name with a comma in it is the normal case.

#: A department name as a room's files spell one: no newline, and nothing the register's `.strip()`
#: or the front matter's `[ \t]*` would have taken off before it became a process.
PROCESS_NAMES = (st.text(alphabet="abcXY Z0,-", min_size=1, max_size=8)
                 .map(str.strip).filter(bool))


def scratch_room(scratch, **over):
    """`room` again, against a temporary directory: a function-scoped `tmp_path` is made once and
    then shared by every example hypothesis draws, so one example's room would be the next's."""
    return room(Path(scratch), **over)


# ── the menu ─────────────────────────────────────────────────────────────────


@given(st.lists(PROCESS_NAMES, max_size=3), st.lists(PROCESS_NAMES, max_size=3))
def test_every_process_on_file_is_offered_once_and_nothing_else_is(transcripts, register):
    """The union of the room's two sources, each once, in order — and never a name it invented."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch, transcripts=transcripts, register=tuple(register))
        assert processes(folder) == sorted(set(transcripts) | set(register))


@given(st.lists(PROCESS_NAMES, max_size=3))
def test_no_process_is_offered_under_a_name_a_manager_could_not_press(transcripts):
    """A blank button is a button nobody can read, so an empty name is not a process."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch, transcripts=transcripts, register=())
        assert all(name.strip() for name in processes(folder))


# ── where a walk is kept ─────────────────────────────────────────────────────


@given(st.text(max_size=12))
def test_a_run_file_never_leaves_the_room_whatever_the_process_is_called(process):
    """The process name comes out of a company's files, so it is input, and it names a path."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = Path(scratch).resolve() / "demo-1"
        folder.mkdir()
        target = jailed_path(folder, run_file(process))
        assert folder in target.parents


@given(st.text(max_size=12))
def test_a_run_file_is_always_one_json_file_under_the_runs_folder(process):
    stem = run_file(process).removeprefix(f"{RUNS}/").removesuffix(".json")
    assert run_file(process) == f"{RUNS}/{stem}.json"
    assert set(stem) <= set("abcdefghijklmnopqrstuvwxyz0123456789-")
    assert stem == stem.strip("-")


# ── the card is a function of the room, and of nothing else ──────────────────


@given(PROCESS_NAMES)
def test_opening_a_bia_writes_not_one_byte(process):
    """Nothing begins because a model said it would: the run file appears at the press, never
    before, so a narrated tool call leaves no trace to be mistaken for work."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch)
        before = sorted(path for path in folder.rglob("*") if path.is_file())
        open_bia(folder, process)
        assert sorted(path for path in folder.rglob("*") if path.is_file()) == before


@given(PROCESS_NAMES)
def test_the_same_room_always_serves_the_same_card(process):
    """Discard every word of the conversation and the card is unchanged — it was never in it."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch)
        assert open_bia(folder, process) == open_bia(folder, process)


@given(PROCESS_NAMES)
def test_the_source_line_names_files_the_room_actually_holds(process):
    """The one element of v1 the owner praised. A path on it that is not there is a false claim."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch)
        card = open_bia(folder, process)
        assert card.source_line.startswith("Source: ")
        assert all(source in card.source_line and (folder / source).is_file()
                   for source in card.sources)


# ── one press, and coming back ───────────────────────────────────────────────


@given(PROCESS_NAMES)
def test_one_press_decides_stage_one_whatever_the_process_is_called(process):
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch, transcripts=(process,), register=())
        said(folder, open_bia(folder, process))
        saved = read_record(folder, run_file(process))
        assert saved["stage"] == 1
        assert [without_telemetry(each) for each in saved["decisions"]] == [
            {"stage": 1, "decided": "yes", "gradient": GRADIENT[0]}]


@given(PROCESS_NAMES)
def test_a_scope_already_agreed_is_never_asked_for_again(process):
    """Resume serves state. It does not interrogate the human for what the room already holds."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch, transcripts=(process,), register=())
        said(folder, open_bia(folder, process))
        resumed = open_bia(folder, process)
        assert (resumed.buttons, resumed.decision, resumed.rule, resumed.gradient) == ((), "", "",
                                                                                       ())
        assert resumed.body == RESUMED.format(process=process)


@given(PROCESS_NAMES)
def test_pressing_twice_never_records_the_decision_twice(process):
    """The second press is over a card the first one moved, so it loses on the revision."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch, transcripts=(process,), register=())
        card = open_bia(folder, process)
        said(folder, card)
        said(folder, card)
        assert len(read_record(folder, run_file(process))["decisions"]) == 1


# ── 25's pure core: the record a press leaves ────────────────────────────────
#
# A run that is already on file when the first press lands (ADR-0011) is **filled**, not stood in
# for: `_opened_run(...) | (card.saved or {})`, and what that merge produces goes to `_advanced` —
# the one pure function all five stages leave their record through. The examples above press one
# prepared room; these say what holds for any run a room could already be carrying, and for any
# stage pressing over it. A second spelling of the shape is what `_advanced` exists to prevent,
# so a property here is a property of every stage at once.

#: A run as one arrives on file, each field optional because what ADR-0011 mints and what a walk
#: has since written are the same shape seen at different ages. None of the three keys `_advanced`
#: writes for itself is drawn — those are what the properties below are about.
ON_FILE = st.fixed_dictionaries({}, optional={
    "run_id": st.text(alphabet="abc0-", min_size=1, max_size=6),
    "room": st.text(alphabet="abc0-", min_size=1, max_size=6),
    "process": PROCESS_NAMES,
    "method": st.sampled_from([{}, {"org": "Marschkamp"}]),
    "schema": st.sampled_from([SCHEMA, SCHEMA + 1]),
})

#: The decisions a run already carries. The length is sampled rather than drawn because this suite
#: is derandomized (`conftest.py`) and a band whose edges are never offered leaves both the run
#: with nothing decided — which is the whole of ADR-0011's room — and the full one unvisited.
EARLIER = st.sampled_from([0, 1, 2, 3]).flatmap(lambda size: st.lists(
    st.fixed_dictionaries({AT_STAGE: st.sampled_from([STAGE, STAGE_2, STAGE_3]),
                           "decided": st.sampled_from(["yes", "no"])}),
    min_size=size, max_size=size))

#: The answer the press adds. Its stage is never drawn: `_advanced` stamps that on, and a stage the
#: caller chose here would be the test agreeing with itself.
ANSWER = st.fixed_dictionaries({}, optional={
    "decided": st.just("yes"), "gradient": st.sampled_from(GRADIENT)})

#: What a stage names over the top. Stages 4 and 5 both name a status, which makes `status` the one
#: field of `_advanced`'s own three a caller is allowed the last word on.
NAMED_BY_THE_STAGE = st.sampled_from([{}, {"status": RECORD_SAVED}, {"status": REVIEWED},
                                      {"record_sha": "abc"}])
STAGES = st.sampled_from([STAGE, STAGE_2, STAGE_3, STAGE_4])


@given(ON_FILE, EARLIER, STAGES, ANSWER, NAMED_BY_THE_STAGE)
def test_a_press_writes_three_fields_and_leaves_every_other_one_exactly_as_it_found_it(
        on_file, earlier, stage, answer, named):
    """What the run already says is the run's, and a press may not quietly restate it.

    This is the property ticket 25's defect was on the other side of: the identity, the method and
    the sources a run arrives carrying survive the press that finds them, and a press invents no
    field of its own beyond the stage it reached, the status it left and the decision it added.
    """
    left = _advanced({**on_file, DECISIONS: earlier}, stage, answer, on_card="record", **named)

    assert all(left[key] == value for key, value in on_file.items() if key not in named)
    assert set(left) == set(on_file) | set(named) | {AT_STAGE, STATUS, DECISIONS}
    assert left[AT_STAGE] == stage


@given(ON_FILE, EARLIER, STAGES, ANSWER, NAMED_BY_THE_STAGE)
def test_a_press_appends_one_decision_and_rewrites_none_of_the_ones_before_it(
        on_file, earlier, stage, answer, named):
    """The decisions list is the referee's evidence later, so it only ever grows, and only at the
    end. A run whose file carries no list at all is started one rather than crashed on — that is
    the same missing-field case as the missing identity, one key along."""
    left = _advanced({**on_file, DECISIONS: earlier}, stage, answer, on_card="record", **named)
    appended = {AT_STAGE: stage, AT_TIME: left[DECISIONS][-1][AT_TIME], ON_CARD: "record",
                REFUSALS: [], **answer}

    bare = _advanced(on_file, stage, answer, on_card="record")[DECISIONS]

    assert left[DECISIONS] == [*earlier, appended]
    assert bare == [{**appended, AT_TIME: bare[-1][AT_TIME]}]


def test_a_decision_keeps_each_refusal_as_its_kind_and_the_parts_it_was_found_in():
    """`_advanced`'s own words: a decision carries, beside the answer, "the moment, the card it
    was taken on, and what the referee refused over the record it saved". A refusal is kept in
    the parts `nemo.refusal` found it in — the kind, and what the record put against it — and
    never as the developer's sentence, which is the one thing a manager never reads."""
    rejection = refusal.Rejection(
        refusal.TARGET_OUTSIDE_MTPD, "activity A1: recovery target 8 h is not strictly inside "
        "the MTPD 8 h", activity="A1", target="8 h", mtpd="8 h")

    left = _advanced({}, STAGE_4, {}, on_card="record", refused=(rejection,))

    assert left[DECISIONS][-1][REFUSALS] == [
        {"kind": rejection.kind, "parts": {"activity": "A1", "target": "8 h", "mtpd": "8 h"}}]


@given(ON_FILE, EARLIER, STAGES, ANSWER, NAMED_BY_THE_STAGE)
def test_a_press_leaves_the_walk_awaiting_the_human_unless_its_own_stage_says_otherwise(
        on_file, earlier, stage, answer, named):
    """ADR-0014: a stage asks or proceeds and the record says which. Awaiting is the default, and
    the two stages that leave something else say so themselves rather than by the shape of what
    they wrote."""
    left = _advanced({**on_file, DECISIONS: earlier}, stage, answer, on_card="record", **named)

    assert left[STATUS] == named.get("status", AWAITING_HUMAN)


#: What a run can already be carrying when the first press lands, over the fields ADR-0011's mint
#: writes. `run_id` is drawn as present and as absent, which is the two sides of ticket 25.
ALREADY_CARRIED = st.fixed_dictionaries({}, optional={
    "run_id": st.text(alphabet="abc0-", min_size=1, max_size=6),
    "method": st.sampled_from([{}, {"org": "Marschkamp"}]),
    "note": st.text(alphabet="abc ", max_size=6),
})


@given(ALREADY_CARRIED)
def test_the_first_press_fills_a_run_already_on_file_and_mints_an_identity_only_if_none_is_there(
        already):
    """The binding, over any run a prepared chat could arrive with, not only the one example room.

    An identity is minted once and never minted over: a second minting would leave the record on
    disk naming a run the walk is no longer called, which is the binding ticket 15 reads backwards.
    """
    with tempfile.TemporaryDirectory() as scratch:
        folder = scratch_room(scratch)
        write_record(folder, run_file("Slaughter"), {
            "schema": SCHEMA, "room": folder.name, "process": "Slaughter", "stage": STAGE,
            "status": AWAITING_HUMAN, "decisions": [], **already}, 0)

        said(folder, open_bia(folder, "Slaughter"))

        saved = read_record(folder, run_file("Slaughter"))
        assert all(saved[key] == value for key, value in already.items())
        assert {"run_id", "method", "sources"} <= set(saved)
        if "run_id" not in already:
            assert uuid.UUID(saved["run_id"]).version == 4


# ══════════════════════════════════════ stage 2 ══════════════════════════════════════════════
#
# The transcripts are already in the room and the human picks the one this BIA rests on. The
# fixtures below are what a room holds: an interview we already had under `07_Interviews/`, and
# one the room held itself earlier under `output/owner-interviews/`.

TESTIMONY = ("---\ndepartment: {department}\n---\n\n# {department} interview\n\n"
             "Petra: if the line stops we can hold orders for a shift, no longer. After that the "
             "A-customers start calling and the day is lost.\n")


def interviewed(folder, department="Slaughter", home=INTERVIEWS, name="26_09_01_interview.md",
                text=None):
    """One interview in one of the room's two homes, written with its own testimony in it."""
    target = folder / home / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text or TESTIMONY.format(department=department), encoding="utf-8")
    return target


def at_stage_2(tmp_path, **over):
    """A room whose scope is agreed for Slaughter, which is how stage 2 is reached at all."""
    folder = room(tmp_path, **over)
    said(folder, open_bia(folder, "Slaughter"))
    return folder


# ── what is offered ──────────────────────────────────────────────────────────


def test_every_interview_the_room_holds_for_the_process_is_offered(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md")
    offered = pick_interview(folder, "Slaughter").interviews
    assert [item.path for item in offered] == [
        f"{INTERVIEWS}/26_08_00_interview.md",
        f"{OWNER_INTERVIEWS}/slaughter-interview-transcript.md",
    ]


def test_an_interview_about_another_process_is_not_offered(tmp_path):
    folder = at_stage_2(tmp_path)
    assert [item.path for item in pick_interview(folder, "Sales").interviews] == [
        f"{INTERVIEWS}/26_08_01_interview.md"]


def test_no_interview_is_offered_twice(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md")
    paths = [item.path for item in pick_interview(folder, "Slaughter").interviews]
    assert len(paths) == len(set(paths)) == 3


def test_the_preview_is_the_files_own_bytes(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    for item in pick_interview(folder, "Slaughter").interviews:
        text = (folder / item.path).read_text(encoding="utf-8")
        assert item.preview and item.preview in text


def test_the_preview_reaches_the_testimony_and_not_only_the_front_matter(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    previews = [item.preview for item in pick_interview(folder, "Slaughter").interviews]
    assert any("A-customers start calling" in preview for preview in previews)


def test_a_preview_is_cut_at_a_fixed_length_and_not_otherwise_touched(tmp_path):
    folder = at_stage_2(tmp_path)
    long_one = TESTIMONY.format(department="Slaughter") + "Petra: " + "and again. " * 200
    interviewed(folder, name="26_09_02_interview.md", text=long_one)
    offered = {item.path: item for item in pick_interview(folder, "Slaughter").interviews}
    preview = offered[f"{INTERVIEWS}/26_09_02_interview.md"].preview
    assert preview == long_one[:PREVIEW]
    assert len(preview) == PREVIEW


def test_an_interview_is_named_by_its_file_name_said_in_words(tmp_path):
    folder = at_stage_2(tmp_path)
    names = [item.name for item in pick_interview(folder, "Slaughter").interviews]
    assert names == ["26 08 00 interview"]
    assert not [name for name in names if "/" in name or ".md" in name]


def test_two_interviews_about_one_process_are_not_named_the_same_thing(tmp_path):
    """Both are titled after the department, so a title would make two buttons read as one."""
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    names = [item.name for item in pick_interview(folder, "Slaughter").interviews]
    assert len(set(names)) == len(names) == 2


def test_the_fingerprint_is_the_digest_of_the_files_own_bytes(tmp_path):
    folder = at_stage_2(tmp_path)
    item = pick_interview(folder, "Slaughter").interviews[0]
    assert item.fingerprint == hashlib.sha256((folder / item.path).read_bytes()).hexdigest()


# ── the stage 2 card ─────────────────────────────────────────────────────────


def test_the_card_is_headed_for_stage_two_of_five(tmp_path):
    card = pick_interview(at_stage_2(tmp_path), "Slaughter")
    assert card.heading == HEADING_2 == "Stage 2 of 5 · Interview"  # t432: the short name
    assert card.subtitle == "The interviews this BIA rests on"  # t432: plural, the subtitle only
    assert card.stage == 2


def test_the_card_offers_exactly_the_four_labels_and_no_fifth_way(tmp_path):
    card = pick_interview(at_stage_2(tmp_path), "Slaughter")
    assert card.buttons == GRADIENT == ("endorsed", "endorsed with reservations",
                                        "needs discussion", "blocked")


def test_the_card_carries_the_four_labels_as_data_and_not_only_as_controls(tmp_path):
    """`buttons` is what is drawn, `gradient` is what a later reader judges the answer against.

    ADR-0011 fixes both on a Stage 2 card, and a card that drew the labels while carrying none
    would leave every downstream reader to guess which vocabulary the press came from.
    """
    assert pick_interview(at_stage_2(tmp_path), "Slaughter").gradient == GRADIENT


def test_the_card_carries_the_rooms_own_method_and_not_a_hard_coded_one(tmp_path):
    card = pick_interview(at_stage_2(tmp_path), "Slaughter")
    assert card.method == COPIED_METHOD


def test_the_card_names_the_process_it_is_about_in_its_own_prose(tmp_path):
    body = pick_interview(at_stage_2(tmp_path), "Slaughter").body
    assert body == PICK.format(process="Slaughter")
    assert "Slaughter" in body


def test_the_no_interview_card_names_the_process_it_found_nothing_for(tmp_path):
    folder = at_stage_2(tmp_path, transcripts=())
    body = pick_interview(folder, "Cooling, storage and dispatch").body
    assert "Cooling, storage and dispatch" in body


def test_the_card_asks_one_decision_and_not_two(tmp_path):
    decision = pick_interview(at_stage_2(tmp_path), "Slaughter").decision
    assert decision.count("?") == 1 and " and " not in decision


def test_the_card_names_every_interview_it_offered_on_its_source_line(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md")
    card = pick_interview(folder, "Slaughter")
    assert all(item.path in card.sources for item in card.interviews)
    assert all((folder / source).is_file() for source in card.sources)


def test_the_stage_two_card_names_no_machine_identifier_outside_its_source_line(tmp_path):
    card = pick_interview(at_stage_2(tmp_path), "Slaughter")
    prose = " ".join((card.body, card.heading, card.decision, card.rule, *card.buttons))
    assert not [word for word in BANNED if word in prose]


def test_the_stage_two_card_is_prose_rather_than_a_numbered_list(tmp_path):
    body = pick_interview(at_stage_2(tmp_path), "Slaughter").body
    assert not [line for line in body.splitlines() if line.strip()[:2] in ("1.", "2.", "1)")]
    assert body.count(". ") >= 2


def test_reaching_stage_two_writes_not_one_byte(tmp_path):
    folder = at_stage_2(tmp_path)
    before = sorted((path, path.read_bytes()) for path in folder.rglob("*") if path.is_file())
    pick_interview(folder, "Slaughter")
    assert sorted((path, path.read_bytes()) for path in folder.rglob("*")
                  if path.is_file()) == before


# ── the walk decides which card comes next, never the page ───────────────────


def test_an_unanswered_stage_one_card_is_followed_by_nothing(tmp_path):
    folder = room(tmp_path)
    assert onward(folder, open_bia(folder, "Slaughter")) == ()


def test_an_agreed_stage_one_card_is_followed_by_stage_two(tmp_path):
    folder = room(tmp_path)
    following = onward(folder, said(folder, open_bia(folder, "Slaughter")))
    assert [card.stage for card in following] == [2]


def test_coming_back_to_an_agreed_scope_is_followed_by_stage_two(tmp_path):
    folder = at_stage_2(tmp_path)
    assert onward(folder, open_bia(folder, "Slaughter")) == (
        pick_interview(folder, "Slaughter"),)


def test_an_answered_stage_two_card_is_followed_by_the_stage_three_card(tmp_path):
    """What ticket 14 changed: binding the evidence is what serves the draft made out of it."""
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    following = onward(folder, said(folder, card, ENDORSED, picked=card.interviews[0]))
    assert [item.stage for item in following] == [STAGE_3]


def test_a_stage_two_card_nobody_answered_is_followed_by_nothing(tmp_path):
    folder = at_stage_2(tmp_path)
    assert onward(folder, pick_interview(folder, "Slaughter")) == ()


# ── the pick ─────────────────────────────────────────────────────────────────


def test_pressing_one_interview_leaves_that_one_on_the_card(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    card = pick_interview(folder, "Slaughter")
    picked = chosen(folder, "Slaughter", card.interviews[1].path)
    assert picked.interviews == (card.interviews[1],)
    assert picked.buttons == GRADIENT


def test_the_picked_card_says_which_one_it_is_and_asks_about_that_one(tmp_path):
    """The pick changes the question as well as the list: 'which of these' becomes 'is this'."""
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    picked = chosen(folder, "Slaughter", card.interviews[0].path)
    assert picked.body == CHOSEN
    assert picked.decision == DECISION_CHOSEN
    assert (picked.body, picked.decision) != (card.body, card.decision)


def test_pressing_an_interview_the_card_did_not_offer_picks_nothing(tmp_path):
    folder = at_stage_2(tmp_path)
    assert chosen(folder, "Slaughter", "07_Interviews/invented.md") == pick_interview(
        folder, "Slaughter")


def test_the_pick_writes_not_one_byte(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    before = sorted(path for path in folder.rglob("*") if path.is_file())
    chosen(folder, "Slaughter", card.interviews[0].path)
    assert sorted(path for path in folder.rglob("*") if path.is_file()) == before


# ── the binding, and nothing else, to disk ───────────────────────────────────


def test_the_binding_names_the_interview_and_its_fingerprint(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    item = card.interviews[0]
    said(folder, card, ENDORSED, picked=item)
    assert read_record(folder, run_file("Slaughter"))["transcript"] == {
        "name": item.name, "path": item.path, "fingerprint": item.fingerprint}


def test_the_label_is_recorded_by_name_rather_than_flattened_into_a_yes(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    said(folder, card, "endorsed with reservations", picked=card.interviews[0])
    assert without_telemetry(read_record(folder, run_file("Slaughter"))["decisions"][-1]) == {
        "stage": 2, "gradient": "endorsed with reservations", "naming": UNNAMED}


def test_the_binding_carries_stage_one_forward_and_advances_the_stage(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    said(folder, card, ENDORSED, picked=card.interviews[0])
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["stage"] == 2 and saved["status"] == AWAITING_HUMAN and saved["revision"] == 2
    assert [entry["stage"] for entry in saved["decisions"]] == [1, 2]


def test_stage_two_writes_no_document_for_the_human_to_read(tmp_path):
    folder = at_stage_2(tmp_path)
    before = {path for path in folder.rglob("*") if path.is_file()}
    card = pick_interview(folder, "Slaughter")
    said(folder, card, ENDORSED, picked=card.interviews[0])
    assert {path for path in folder.rglob("*") if path.is_file()} == before


def test_the_binding_says_so_in_a_colleagues_sentence_and_asks_nothing_further(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    bound = said(folder, card, ENDORSED, picked=card.interviews[0])
    assert bound.body == BOUND
    assert (bound.buttons, bound.decision, bound.rule, bound.interviews) == ((), "", "", ())


def test_a_binding_that_was_overtaken_does_not_land_on_top_of_the_newer_record(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    moved_on(folder)
    overtaken = said(folder, card, "blocked", picked=card.interviews[0])
    assert read_record(folder, run_file("Slaughter"))["decisions"][-1]["stage"] == STAGE
    assert overtaken.body.startswith(OVERTAKEN)


def test_the_overtaken_card_reads_as_one_paragraph_and_then_offers_the_interviews_again(tmp_path):
    """The apology is joined to the offer by a single space — one paragraph a human reads."""
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    moved_on(folder)
    overtaken = said(folder, card, "blocked", picked=card.interviews[0])
    assert overtaken.body == OVERTAKEN + " " + pick_interview(folder, "Slaughter").body


def test_the_binding_card_is_the_stage_it_answered_and_carries_the_record_it_saved(tmp_path):
    """`_answered` is told both, and a card that got either wrong would still read correctly."""
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    bound = said(folder, card, ENDORSED, picked=card.interviews[0])
    saved = read_record(folder, run_file("Slaughter"))
    assert bound.stage == 2
    assert bound.saved == saved
    assert bound.revision == saved["revision"] == card.revision + 1


# ── the interview held in the room ───────────────────────────────────────────
#
# Ticket 13. The room holds no interview for the process at all, so stage 2 conducts one — and
# what the walk owes that path is narrow: where the words are filed, that the preview is exactly
# those bytes, and that the one press files and binds them together. What is asked and what is
# written down is `nemo.conduct`'s, and is stated against that module.

LIVE = (conduct.Turn("What does Slaughter do for the rest of the plant on an ordinary day?",
                     "It's the front of the line. Everything downstream waits on it."),
        conduct.Turn("Who notices first if it stops?",
                     "Cutting, inside the hour — then dispatch, then the A-customers."))


def at_the_live_interview(tmp_path):
    """A room whose scope is agreed for a process it holds no interview for, in either home."""
    folder = at_stage_2(tmp_path, transcripts=())
    assert pick_interview(folder, "Slaughter").buttons == (HOLD_IT_NOW,)
    return folder


def test_the_interview_is_filed_where_the_referee_will_hunt_quotes():
    """The path the story names, under the process's own name and the room's second home."""
    assert interview_path("Slaughter") == f"{OWNER_INTERVIEWS}/slaughter-interview-transcript.md"


@given(st.text(alphabet="abcXY Z0,-/", min_size=1, max_size=12).map(str.strip).filter(bool))
def test_the_interviews_file_name_is_a_name_and_not_a_path(process):
    """A process is a sentence a company wrote, so the file it is filed under is built, never
    pasted: the same slug the run file is named by, and it cannot leave the folder."""
    assert interview_path(process).startswith(f"{OWNER_INTERVIEWS}/")
    assert interview_path(process).count("/") == OWNER_INTERVIEWS.count("/") + 1


def test_the_preview_is_the_whole_interview_and_carries_its_fingerprint(tmp_path):
    """The story's first scenario: shown the verbatim question-and-answer, with its fingerprint."""
    card = held_interview(at_the_live_interview(tmp_path), "Slaughter", LIVE)
    shown = card.interviews[0]
    assert shown.preview == conduct.transcript("Slaughter", LIVE)
    for turn in LIVE:
        assert turn.question in shown.preview and turn.answer in shown.preview
    assert shown.fingerprint == hashlib.sha256(shown.preview.encode()).hexdigest()


def test_the_card_the_preview_arrives_on_says_what_the_manager_is_looking_at(tmp_path):
    """The card the interview was offered *on* asked whether there was an interview at all, and
    this one answers that: the words are below, unedited, and nothing of them is kept until the
    gradient is answered. A preview that arrived under the invitation to hold an interview would
    tell a manager there is nothing on file while showing them the thing they just said."""
    folder = at_the_live_interview(tmp_path)
    before = pick_interview(folder, "Slaughter")
    card = held_interview(folder, "Slaughter", LIVE)
    assert card.body == CONDUCTED and card.body != before.body


def test_the_preview_is_answered_with_the_four_labels_and_no_second_card(tmp_path):
    """A longer path, not a more expensive gate: the same one decision the transcript path costs."""
    card = held_interview(at_the_live_interview(tmp_path), "Slaughter", LIVE)
    assert card.buttons == GRADIENT
    assert card.stage == 2 and card.heading == HEADING_2
    assert card.decision == DECISION_CHOSEN and card.decision.count("?") == 1


def test_reaching_the_preview_writes_not_one_byte(tmp_path):
    """Nothing is on disk until the gradient is answered — the first scenario's second half."""
    folder = at_the_live_interview(tmp_path)
    before = {path for path in folder.rglob("*") if path.is_file()}
    held_interview(folder, "Slaughter", LIVE)
    assert {path for path in folder.rglob("*") if path.is_file()} == before


def test_what_is_kept_is_byte_for_byte_what_was_shown(tmp_path):
    """The manager endorsed bytes; a save that tidied one of them kept something else."""
    folder = at_the_live_interview(tmp_path)
    card = held_interview(folder, "Slaughter", LIVE)
    said(folder, card, ENDORSED, picked=card.interviews[0])
    assert (folder / card.interviews[0].path).read_bytes() == card.interviews[0].preview.encode()


def test_the_saved_files_digest_is_the_fingerprint_the_preview_carried(tmp_path):
    """Checkable no other way, and the one thing `sha256sum` proves for an operator."""
    folder = at_the_live_interview(tmp_path)
    card = held_interview(folder, "Slaughter", LIVE)
    said(folder, card, ENDORSED, picked=card.interviews[0])
    on_disk = hashlib.sha256((folder / card.interviews[0].path).read_bytes()).hexdigest()
    assert on_disk == card.interviews[0].fingerprint
    assert read_record(folder, run_file("Slaughter"))["transcript"]["fingerprint"] == on_disk


def test_keeping_it_binds_it_to_this_walk_and_answers_stage_two(tmp_path):
    folder = at_the_live_interview(tmp_path)
    card = held_interview(folder, "Slaughter", LIVE)
    kept = said(folder, card, "endorsed with reservations", picked=card.interviews[0])
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["transcript"] == {"name": card.interviews[0].name,
                                   "path": card.interviews[0].path,
                                   "fingerprint": card.interviews[0].fingerprint}
    assert without_telemetry(saved["decisions"][-1]) == {
        "stage": 2, "gradient": "endorsed with reservations", "naming": UNNAMED}
    assert kept.body == NAMING and kept.buttons == ()


def test_the_only_new_things_on_file_are_the_transcript_and_the_decision(tmp_path):
    """The story's third scenario: a live interview never writes a record, of any length."""
    for length in range(len(LIVE) + 1):
        folder = at_the_live_interview(tmp_path / str(length))
        card = held_interview(folder, "Slaughter", LIVE[:length])
        before = {path for path in folder.rglob("*") if path.is_file()}
        said(folder, card, ENDORSED, picked=card.interviews[0])
        new = {path.relative_to(folder).as_posix()
               for path in folder.rglob("*") if path.is_file()} - {
            path.relative_to(folder).as_posix() for path in before}
        assert new <= {card.interviews[0].path, run_file("Slaughter")}
        assert not (folder / RECORD).exists()


def test_no_figure_of_the_methods_is_asserted_anywhere_the_walk_carries(tmp_path):
    """The model conducts; it does not conclude. Stage 3 reads these out of the transcript, and
    this stage puts none of them on the record on the model's word."""
    folder = at_the_live_interview(tmp_path)
    card = held_interview(folder, "Slaughter", LIVE)
    said(folder, card, ENDORSED, picked=card.interviews[0])
    saved = read_record(folder, run_file("Slaughter"))
    # The method's own `rpo_vocabulary` is the room's file copied verbatim and is not an assertion
    # about this process; what this stage decided and what it bound are where one would show.
    decided = json.dumps({"decisions": saved["decisions"], "transcript": saved["transcript"]})
    for figure in ("mtpd", "rto", "rpo", "mbco"):
        assert figure not in decided.lower()


def test_an_interview_held_in_the_room_is_then_offered_like_any_other(tmp_path):
    """ADR-0002: the room has two homes for interviews and neither wins. A later walk picks it."""
    folder = at_the_live_interview(tmp_path)
    said(folder, held_interview(folder, "Slaughter", LIVE), ENDORSED,
         picked=held_interview(folder, "Slaughter", LIVE).interviews[0])
    offered = pick_interview(folder, "Slaughter").interviews
    assert [item.path for item in offered] == [interview_path("Slaughter")]
    assert offered[0].preview and offered[0].preview in conduct.transcript("Slaughter", LIVE)


def test_an_interview_nobody_kept_leaves_nothing_behind(tmp_path):
    folder = at_the_live_interview(tmp_path)
    held_interview(folder, "Slaughter", LIVE)
    assert not (folder / interview_path("Slaughter")).exists()
    assert "transcript" not in read_record(folder, run_file("Slaughter"))


def test_a_press_that_was_overtaken_keeps_the_words_and_binds_nothing(tmp_path):
    """Losing the compare-and-set must not cost the manager the interview they just gave: the
    words are in the room and stage 2 is offered again with this interview on it."""
    folder = at_the_live_interview(tmp_path)
    card = held_interview(folder, "Slaughter", LIVE)
    moved_on(folder)
    overtaken = said(folder, card, "blocked", picked=card.interviews[0])
    assert overtaken.body.startswith(OVERTAKEN)
    assert read_record(folder, run_file("Slaughter"))["decisions"][-1]["stage"] == STAGE
    assert (folder / interview_path("Slaughter")).is_file()


def test_an_interview_held_here_is_filed_even_where_that_path_holds_older_bytes(tmp_path):
    """The write-back is for the interview just given, and it is the whole of it: the preview
    digests to the fingerprint the manager endorsed, so filing it files exactly what was shown.
    An earlier capture sitting at the same path is not a reason to throw their words away."""
    folder = at_the_live_interview(tmp_path)
    card = held_interview(folder, "Slaughter", LIVE)
    filed = folder / interview_path("Slaughter")
    filed.parent.mkdir(parents=True, exist_ok=True)
    filed.write_text("---\ndepartment: Slaughter\n---\n\nan earlier capture\n", encoding="utf-8")
    kept = said(folder, card, ENDORSED, picked=card.interviews[0])
    assert filed.read_bytes() == card.interviews[0].preview.encode()
    assert read_record(folder, run_file("Slaughter"))["transcript"][
        "fingerprint"] == card.interviews[0].fingerprint
    assert kept.body == BOUND


def test_the_live_card_names_no_machine_identifier_outside_its_source_line(tmp_path):
    card = held_interview(at_the_live_interview(tmp_path), "Slaughter", LIVE)
    prose = " ".join((card.body, card.heading, card.decision, card.rule, *card.buttons))
    assert not [word for word in BANNED if word in prose]
    assert card.body.count(". ") >= 2


def test_the_preview_is_not_in_the_prose_the_card_check_reads(tmp_path):
    """`Card.screen` is what goes through `nemo.card.render`, and a verbatim quotation is not the
    card talking: an owner who said "a day or so" must not make his own interview unrenderable."""
    folder = at_the_live_interview(tmp_path)
    vague = (conduct.Turn("How long could you live without it?",
                          "A day or so, I'd have to check."),)
    card = held_interview(folder, "Slaughter", vague)
    assert "a day or so" not in card.screen.lower()
    assert render(card.stage, card.screen, card.record) == card.screen


# ── a transcript that changed under the walk ─────────────────────────────────


def test_a_walk_that_has_bound_nothing_carries_no_open_item(tmp_path):
    assert interview_findings(at_stage_2(tmp_path), "Slaughter") == []


def test_a_bound_interview_that_still_holds_its_bytes_carries_no_open_item(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    said(folder, card, ENDORSED, picked=card.interviews[0])
    assert interview_findings(folder, "Slaughter") == []


def test_a_bound_interview_whose_bytes_changed_is_raised_as_a_finding(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    item = card.interviews[0]
    said(folder, card, ENDORSED, picked=item)
    (folder / item.path).write_text("---\ndepartment: Slaughter\n---\n\nPetra: two shifts.\n",
                                    encoding="utf-8")
    findings = interview_findings(folder, "Slaughter")
    assert len(findings) == 1
    assert item.name in findings[0]


def test_a_bound_interview_that_has_gone_is_raised_as_a_finding(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    item = card.interviews[0]
    said(folder, card, ENDORSED, picked=item)
    (folder / item.path).unlink()
    assert len(interview_findings(folder, "Slaughter")) == 1


#: A path segment a record could carry, in the characters a room's own files use. Nothing here
#: spells `demo-1`, so `../<segments>` never resolves back into the room by accident.
SEGMENTS = st.lists(st.text(alphabet="abc0-", min_size=1, max_size=4), min_size=1, max_size=3)


@given(SEGMENTS)
def test_a_binding_that_leaves_the_room_is_a_finding_and_never_a_read(segments):
    """The bound path is read back off a file on disk, so by then it is input, whoever wrote it.

    The file outside is real and the fingerprint on the record is its own, so a walk that joined
    `room_folder` to the path itself would digest it, match, and report nothing — this passes only
    because the read goes through `room_store`'s jail, which sits below both `nemo.walk` and
    `nemo.interview` so that neither has to remember the rule separately. The refusal comes back
    as the finding it is, because a finding is data carried onward and never a wall.
    """
    with tempfile.TemporaryDirectory() as scratch:
        outside = Path(scratch) / "/".join(segments)
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_bytes(b"---\ndepartment: Slaughter\n---\n\nanother room's evidence\n")
        folder = at_stage_2(Path(scratch))
        card = pick_interview(folder, "Slaughter")
        item = card.interviews[0]
        said(folder, card, ENDORSED, picked=item)
        record = read_record(folder, run_file("Slaughter"))
        record["transcript"] = {
            **record["transcript"],
            "path": "../" + "/".join(segments),
            "fingerprint": hashlib.sha256(outside.read_bytes()).hexdigest(),
        }
        write_record(folder, run_file("Slaughter"), record, record["revision"])
        assert interview_findings(folder, "Slaughter") == [CHANGED.format(name=item.name)]


# ── a stale pick of somebody else's transcript ───────────────────────────────


LONG_TESTIMONY = TESTIMONY.format(department="Slaughter") + "".join(
    f"Petra: and on a {day} the second shift picks up whatever the first one could not finish, "
    "which is why a stoppage before noon costs the whole day rather than the hour it took.\n"
    for day in ("Monday", "Tuesday", "Wednesday"))


def test_a_stale_pick_never_rebuilds_somebody_elses_transcript_from_its_preview(tmp_path):
    """The preview of an interview the company wrote is its first characters and no more, so a
    press against a card read before the file moved must never write those characters back: that
    is the transcript replaced by its own opening, and the referee hunting quotes in the stump.

    The bytes on disk are not this walk's to restore. A file that moved under a pick nobody has
    bound yet makes the card stale, and a stale card is offered again.
    """
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md", text=LONG_TESTIMONY)
    card = pick_interview(folder, "Slaughter")
    picked = [item for item in card.interviews
              if item.path == f"{INTERVIEWS}/26_09_02_interview.md"][0]
    assert len(picked.preview) == PREVIEW < len(LONG_TESTIMONY)
    target = folder / picked.path
    moved = LONG_TESTIMONY + "Petra: and since Tuesday we hold orders for two shifts, not one.\n"
    target.write_text(moved, encoding="utf-8")

    answered = said(folder, card, ENDORSED, picked=picked)

    assert target.read_bytes() == moved.encode()
    assert "transcript" not in read_record(folder, run_file("Slaughter"))
    assert answered.decision == pick_interview(folder, "Slaughter").decision
    assert answered.body != BOUND

# ── a room with no interview for this process ────────────────────────────────


def test_a_room_with_no_interview_offers_to_hold_it_now(tmp_path):
    folder = at_stage_2(tmp_path, transcripts=())
    card = pick_interview(folder, "Cooling, storage and dispatch")
    assert card.interviews == ()
    assert card.buttons == (HOLD_IT_NOW,)
    assert "let's do it now" in card.body


def test_the_no_interview_branch_is_not_blocked(tmp_path):
    folder = at_stage_2(tmp_path, transcripts=())
    card = pick_interview(folder, "Cooling, storage and dispatch")
    assert card.buttons and card.decision and card.stage == 2


def test_the_no_interview_card_still_names_what_it_read(tmp_path):
    folder = at_stage_2(tmp_path, transcripts=())
    card = pick_interview(folder, "Cooling, storage and dispatch")
    assert card.sources == (METHOD,)


@pytest.mark.parametrize("held", [0, 2])
def test_a_yes_at_stage_two_with_no_interview_chosen_binds_nothing(tmp_path, held):
    """Nothing to bind is not an answer: with no interview in the room, or two and neither picked,
    a typed yes gets stage 2 back as it stands and not one byte lands in the room."""
    folder = at_stage_2(tmp_path, **({} if held else {"transcripts": ()}))
    if held:
        interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md")
    card = pick_interview(folder, "Slaughter")
    assert len(card.interviews) == held
    before = on_disk(folder)

    unanswered = said(folder, card, ENDORSED)

    assert (unanswered.stage, unanswered.body, unanswered.buttons) == (
        card.stage, card.body, card.buttons)
    assert on_disk(folder) == before, "a yes with nothing chosen wrote into the room"


def _files(folder):
    return sorted((path, path.read_bytes()) for path in folder.rglob("*") if path.is_file())


def test_a_yes_to_a_room_with_no_interview_binds_nothing_and_writes_nothing(tmp_path):
    """Nothing to bind is not an answer: the card comes back unanswered, the room untouched."""
    folder = at_stage_2(tmp_path, transcripts=())
    card = pick_interview(folder, "Slaughter")
    before = _files(folder)
    assert walk.answer(folder, "Slaughter", ENDORSED, card.revision) == (card,)
    assert _files(folder) == before


def test_a_yes_to_two_interviews_with_neither_picked_binds_neither(tmp_path):
    """Two on the card and none chosen: the room waits for the manager to choose between them."""
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    card = pick_interview(folder, "Slaughter")
    assert len(card.interviews) == 2
    before = _files(folder)
    assert walk.answer(folder, "Slaughter", ENDORSED, card.revision) == (card,)
    assert _files(folder) == before


# ── the one door every card reaches a human by ───────────────────────────────


def test_what_the_manager_reads_is_the_prose_and_not_the_evidence_beside_it(tmp_path):
    card = pick_interview(at_stage_2(tmp_path), "Slaughter")
    assert card.screen == "\n\n".join((card.heading, card.subtitle, card.body, card.decision,
                                        card.rule))
    assert card.source_line not in card.screen


def test_an_answered_card_shows_no_decision_and_no_rule(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    bound = said(folder, card, ENDORSED, picked=card.interviews[0])
    assert bound.screen == f"{bound.heading}\n\n{bound.subtitle}\n\n{bound.body}"


@pytest.mark.parametrize("stage", [1, 2])
def test_every_stage_card_this_walk_serves_goes_through_the_door_unrefused(tmp_path, stage):
    """The check is invisible when the cards are honest: nothing on screen says it ran."""
    folder = at_stage_2(tmp_path)
    card = open_bia(folder, "Slaughter") if stage == 1 else pick_interview(folder, "Slaughter")
    assert render(card.stage, card.screen, card.saved or {}) == card.screen


@pytest.mark.parametrize("stage", [1, 2])
def test_a_card_that_softens_a_figure_is_refused_at_either_stage(tmp_path, stage):
    folder = at_stage_2(tmp_path)
    card = open_bia(folder, "Slaughter") if stage == 1 else pick_interview(folder, "Slaughter")
    with pytest.raises(CardGeneratorBug):
        render(card.stage, card.screen + " That's about a working day.", card.saved or {})


def test_the_four_labels_are_not_drawn_on_a_stage_one_card(tmp_path):
    """ADR-0011, the owner's ruling: stage 1 confirms scope and has no figure to judge."""
    card = open_bia(room(tmp_path), "Slaughter")
    assert card.buttons == (AGREE,)
    assert not [label for label in GRADIENT if label in card.screen]


def test_stage_ones_one_press_is_still_recorded_as_one_of_the_four_labels(tmp_path):
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    assert read_record(folder, run_file("Slaughter"))["decisions"][-1]["gradient"] == ENDORSED


def test_the_card_the_walk_waits_on_is_reached_by_a_public_name(tmp_path):
    """Ticket 219: `current` is the door alongside `answer` and `sign`, and the callers across the
    seam name it. The private `_waiting` it was called by is gone, with no alias left behind."""
    folder = room(tmp_path)
    said(folder, open_bia(folder, "Slaughter"))
    walked = open_bia(folder, "Slaughter")
    while following := onward(folder, walked):
        walked = following[0]

    assert walk.current(folder, "Slaughter") == walked
    assert not hasattr(walk, "_waiting"), "the private name is still reachable"


# Retired by ticket 161: `test_the_skin_shows_no_card_except_through_the_one_door` read demo_skin's
# `_show`; the phone app has no `_show` and never calls `nemo.card.render` (its figure check is
# `PROTOTYPE_core.Session._flag`, a different door), so the property has no phone source to read.


# ── ADR-0013's pure core: the ways a card offers, and how a typed answer reads ───
#
# Three pure functions carry the whole of the owner's 2026-09-13 ruling. `_ways` puts the ways to
# answer into the card's own prose, where the four buttons used to be; `_a_question` and `_gradient`
# read back what the manager types instead of pressing. Every other test in this file reaches them
# through a room and a record, so what they are held to is whatever one fixture happened to type.
# Here they are held to a property over every string, which is the only way a rough reading can be
# said to lean in one direction rather than merely to have leaned once.

#: A label carrying neither separator `_ways` uses, so counting them in the phrase is honest. The
#: alphabet has no `o` and no `r` on purpose: a label spelling ` or ` of its own would make the
#: round trip below pass for the wrong reason.
LABEL = st.text(alphabet="abcdefghij ", min_size=1).map(str.strip).filter(bool)

#: One to four of them. The count is sampled rather than drawn from a range, because this suite is
#: derandomized (`conftest.py`) and a band whose edges are never offered leaves the one-label case
#: to luck — and one label is the only shape with nothing at all to separate.
LABEL_SETS = st.sampled_from([1, 2, 3, 4]).flatmap(
    lambda size: st.lists(LABEL, min_size=size, max_size=size))

#: The words a manager trails an answer off with. Each one is a `_HELD_BACK` match, said the way
#: somebody would actually say it rather than as the bare keyword the pattern looks for.
CAVEATS = st.sampled_from(["but I am not sure", "although the night shift differs",
                           "I have a concern", "maybe", "that seems wrong"])


@given(LABEL_SETS)
def test_a_card_offers_back_exactly_the_ways_it_was_given_in_that_order(labels):
    """A manager reads the phrase and types one of them back, so a label that fell out of it on the
    way is a way to answer the card that nobody can reach, and a label that arrived twice is one he
    cannot tell apart. Order is the card's meaning: the gradient runs from endorsed to blocked.

    The `or` is asserted separately from the round trip because the round trip alone does not carry
    it: fold the last separator into `, ` as well and the recovery still succeeds, over a phrase
    that has stopped being English. The alphabet holds no `o` and no `r`, so the one ` or ` found
    here can only be the separator."""
    phrase = _ways(tuple(labels))
    assert phrase.replace(" or ", ", ").split(", ") == labels
    assert phrase.count(" or ") == (1 if len(labels) > 1 else 0)


@given(LABEL)
def test_the_only_way_to_answer_is_said_with_no_separator_hanging_off_it(label):
    """One label is the case with nothing to separate, and the one a stray `, ` or a trailing ` or `
    would disfigure. Stage 1 offers exactly one way (ADR-0011), so this is not a corner."""
    assert _ways((label,)) == label


def test_the_four_ways_read_as_one_english_phrase_a_manager_can_answer_from():
    """The prose the four buttons became. Pinned literally because this is what is on the screen."""
    assert _ways(GRADIENT) == "endorsed, endorsed with reservations, needs discussion or blocked"


def _asking(rule: str) -> Card:
    """A card carrying nothing but the rule under test, so what `ways` reads is only that rule."""
    return Card(stage=1, name="scope", heading=HEADING, activities=(), body="", sources=(),
                buttons=GRADIENT,
                decision="", rule=rule, gradient=GRADIENT, method={}, saved=None, revision=0)


@given(LABEL_SETS)
def test_a_card_says_back_exactly_the_ways_it_was_built_to_offer(labels):
    """The round trip a manager makes: the card says its answers, he reads them and types one back.
    A label that fell out of the sentence on the way is a way to answer nobody can reach."""
    asking = _asking(IN_WORDS.format(ways=_ways(tuple(labels))))
    assert list(asking.ways) == labels


def test_a_card_that_says_no_way_to_answer_it_offers_none():
    """A refused record's card carries no rule at all (`record_card`), and the four labels it still
    holds underneath decide nothing: what is not in the prose is not offered."""
    assert _asking("").ways == ()
    assert _asking("Got it. That's stage 1 of 5 done.").ways == ()
    assert _asking(RULE_4).ways == GRADIENT


def test_the_one_way_stage_one_offers_is_read_whole_and_not_split_at_its_own_comma():
    """`Yes, that's the scope` carries a comma of its own, and splitting on it would hand back two
    answers to a card that offers one."""
    assert _asking(RULE).ways == (AGREE,)


@given(st.text(max_size=40), st.text(alphabet=" \t\r\n", max_size=5))
def test_trailing_whitespace_never_decides_whether_something_is_a_question(words, trailing):
    """A chat box hands the walk whatever the manager's Enter left on the end. If that settled the
    reading, one sentence would be a question in one client and an answer in the next."""
    assert _a_question(words + trailing) == _a_question(words)


@given(st.text(max_size=20), st.text(alphabet=" \t\n", max_size=4))
def test_anything_ending_in_a_question_mark_is_read_as_a_question(words, trailing):
    """The whole of the 80/20 rule the owner ruled for, from the side that says yes."""
    assert _a_question(f"{words}?{trailing}")


@given(st.text(max_size=20),
       st.text(max_size=20).filter(lambda rest: rest.rstrip() and not rest.rstrip().endswith("?")))
def test_a_question_mark_anywhere_but_the_end_is_not_a_question(before, after):
    """"Why? Because the plant runs two shifts." is an answer with a question mark inside it.
    Read as a question it costs the manager a paragraph of guidance he did not ask for."""
    assert not _a_question(f"{before}?{after}")


@given(st.text(max_size=40))
def test_every_answer_is_recorded_as_one_of_the_four_ways_the_card_offers(words):
    """Total over every string a manager could type. A fifth value reaching `gradient` would be a
    figure no view, no referee and no later reader of the record knows how to read. ``None`` is
    the line that says none of them, and it never reaches the record: the walk asks (234b)."""
    assert _gradient(words) in (*GRADIENT, None)


@given(st.sampled_from(GRADIENT), st.sampled_from(["", "*", "**", "_", "`"]),
       st.text(alphabet=" \t\n", max_size=3), st.text(alphabet=" \t\n", max_size=3))
def test_a_label_typed_back_however_it_arrives_is_recorded_as_that_label(
        label, wrap, before, after):
    """ADR-0013 put the four labels into the card's prose to be read and typed back, so what returns
    carries whatever the chat box did to it on the way — a capital, an emphasis, a stray newline.
    Any of those recorded as a different answer is the certainty the buttons had, lost."""
    assert _gradient(f"{before}{wrap}{label.upper()}{wrap}{after}") == label


@given(st.text(alphabet="abcdefghij ", max_size=20), CAVEATS)
def test_words_that_hold_something_back_are_never_recorded_as_an_endorsement(words, caveat):
    """`docs/voice.md` §4.3: a reservation recorded against somebody who never made one is the
    failure to avoid, so the rough edge leans towards asking. Being wrong this way costs one
    question he waves off; being wrong the other way puts an endorsement he never gave on a record.

    The alphabet spells none of the four labels — none of `n`, `o`, `r`, `s` is in it — so the
    label branch can never be what carries this, and the lean is what is under test."""
    recorded = _gradient(f"{words} {caveat}")
    assert recorded != ENDORSED and recorded == RESERVED


#: Ticket 234 (review C1): what a manager types to refuse, each of which read *endorsed* before.
REFUSALS_TYPED = ["No", "blocked!", "This is blocked", "needs discussion with Anja", "not endorsed",
                  "I do not agree"]


@pytest.mark.parametrize("words", REFUSALS_TYPED)
def test_a_refusal_typed_in_his_own_words_is_never_recorded_as_an_endorsement(words):
    """A refusal he typed and the record calling it an endorsement is the one misreading this
    reading may never make: the signed run and both handover documents would carry it."""
    assert _gradient(words) != ENDORSED


@pytest.mark.parametrize(("words", "label"), [
    ("blocked!", GRADIENT[3]), ("This is blocked", GRADIENT[3]),
    ("needs discussion with Anja", GRADIENT[2]), ("endorsed with reservations, the RTO", RESERVED)])
def test_a_label_inside_his_sentence_is_that_label(words, label):
    """A label is found as a whole phrase inside his words, the longest first, so "needs
    discussion with Anja" is the label he used and not a caveat the walk read into it."""
    assert _gradient(words) == label


@pytest.mark.parametrize("words", ["", "   ", "the weather in Vechta", "Slaughter"])
def test_a_line_that_says_neither_yes_nor_no_is_never_an_endorsement_by_default(words):
    """Before 234 an empty or unrelated line read *endorsed*. It now reads as none of the four, so
    the walk asks which one rather than recording a decision he never typed (234b)."""
    assert _gradient(words) is None


#: 234b: lines that say no yes, no label and nothing held back.
NEITHER_SAID = ["", "   ", "the weather in Vechta", "Slaughter"]


def stage_1_card(tmp_path):
    folder = room(tmp_path)
    return folder, open_bia(folder, "Slaughter")


def stage_2_card(tmp_path):
    folder = at_stage_2(tmp_path)
    return folder, walk.current(folder, "Slaughter")


def stage_3_card(tmp_path):
    return reached(tmp_path)


def stage_4_card(tmp_path):
    folder, stage_2 = bound(tmp_path, SCORED)
    card = onward(folder, said(folder, onward(folder, stage_2)[0], ENDORSED))[0]
    assert card.stage == STAGE_4 and not card.refused
    return folder, card


def stage_5_card(tmp_path):
    return handed_over(tmp_path)


@pytest.mark.parametrize("words", NEITHER_SAID)
@pytest.mark.parametrize("at", [stage_1_card, stage_2_card, stage_3_card, stage_4_card,
                                stage_5_card])
def test_a_line_that_says_none_of_the_four_writes_nothing_and_asks_which(tmp_path, at, words):
    """The owner's ruling that nemo carries only what he typed (2026-09-20): a line with no yes,
    no label and nothing held back records no decision. The run stays byte for byte as it was, and
    the same card asks once, in the card's own four labels."""
    folder, card = at(tmp_path)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    replies = walk.answer(folder, "Slaughter", words, card.revision)

    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before
    assert [(each.stage, each.body, each.buttons, each.decision, each.rule)
            for each in replies] == [(card.stage, NOT_CAUGHT, (), "", "")]
    assert NOT_CAUGHT == ("I didn't catch which one: endorsed, endorsed with reservations, "
                          "needs discussion, or blocked?")


@pytest.mark.parametrize("words", NEITHER_SAID)
def test_a_label_typed_after_the_ask_lands_as_typed_and_asks_for_its_naming(tmp_path, words):
    """The ask costs one line and nothing else: "blocked" after it is blocked, waiting on his
    naming exactly as a first "blocked" would be."""
    folder, card = stage_2_card(tmp_path)
    walk.answer(folder, "Slaughter", words, card.revision)

    answered = walk.answer(folder, "Slaughter", "blocked", card.revision)

    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": STAGE_2, "gradient": GRADIENT[3], "naming": UNNAMED}
    assert answered[0].body == NAMING


@pytest.mark.parametrize("words", ["endorsed", "Endorsed.", "yes", "Yes, that's the scope", "ok",
                                   "agreed", "looks good"])
def test_a_plain_yes_still_reads_as_endorsed(words):
    """The other direction, held as it was: a plain yes is an endorsement."""
    assert _gradient(words) == ENDORSED


# ── the door's third rule: which typed words are not this walk's at all ──────
#
# `_for_the_ask_lane` is the pure reading behind rule 3 of `answer`'s docstring, and it is the one
# of these functions that reads the run file as well as the words. Every other test in this file
# reaches it through a room, where one fixture's status and one fixture's sentence stand in for all
# of them — so what is held here is every status a run can carry against every way of typing.

#: What a manager types that is not a question. The alphabet spells no `?`, so the question reading
#: can never be what carries a case; the four labels are in because a label typed back after the
#: handover is the "yes, thanks" this rule exists to leave unrecorded.
TYPED = st.text(alphabet="abcdefghij ,.", max_size=20) | st.sampled_from(GRADIENT)

#: A walk with a card still waiting for the composer, and one whose handover has been accepted.
#: `None` is the run file of a walk that has written no status yet, and it belongs on the first
#: side. Sampled rather than drawn, because this suite is derandomized (`conftest.py`) and a status
#: only *offered* by a range may never be offered at all.
STILL_ASKING = st.sampled_from([None, AWAITING_HUMAN, RECORD_SAVED])
PAST_ASKING = st.sampled_from([REVIEWED, CLOSED])


def run_at(status):
    """A run file standing at that status, and one that has not written a status at all."""
    return {} if status is None else {STATUS: status}


@given(PAST_ASKING, TYPED)
def test_after_the_handover_nothing_typed_is_this_walks_to_read(status, words):
    """What follows an accepted handover is a signature, and a signature is never typed words: it
    demands a name and a role by name (`sign`, ADR-0003). So a manager's "yes, thanks" at the end
    is the ask lane's whatever it says — including one of the four labels, which is the answer
    shape that would otherwise be recorded as a fifth decision nobody was asked for."""
    assert _for_the_ask_lane(run_at(status), words)


@given(STILL_ASKING, st.text(max_size=30))
def test_while_a_card_is_waiting_the_question_mark_is_the_whole_of_the_reading(status, words):
    """Before the handover the rule is `_a_question` and nothing else — which is what keeps a plain
    answer the walk's to record. Said as an equality rather than as two examples: any second
    condition creeping in here is a stage answer dropped into a lane that writes nothing."""
    assert _for_the_ask_lane(run_at(status), words) == _a_question(words)


@given(STILL_ASKING | PAST_ASKING, st.text(max_size=20))
def test_a_question_is_the_ask_lanes_at_every_stage_a_walk_can_stand_at(status, words):
    """`docs/what-good-looks-like.md:201` puts a BCM question inside the release bar, so there is
    no status at which "what does MTPD mean?" is filed as an endorsed stage answer."""
    assert _for_the_ask_lane(run_at(status), f"{words}?")


@given(STILL_ASKING | PAST_ASKING, TYPED,
       st.lists(st.sampled_from([STAGE, STAGE_2, STAGE_3, STAGE_4]), max_size=4),
       st.lists(st.text(alphabet="abc ", max_size=8), max_size=2))
def test_nothing_in_the_run_but_its_status_decides_whose_words_these_are(
        status, words, stages, findings):
    """The status and the words, and nothing else the run happens to be carrying.

    A run file grows: decisions at every stage, findings from the referee, a receipt, a signature.
    A reading that drifted onto any of them would route a manager's sentence by how far along he
    is rather than by what is waiting for it, and it would do so silently — the ask lane writes
    nothing, so the walk that swallowed an answer looks exactly like the walk that answered it.
    """
    carrying = {**run_at(status), DECISIONS: [{AT_STAGE: stage} for stage in stages],
                FINDINGS: findings, RECEIPT: {"record_sha": "x"}}

    assert _for_the_ask_lane(carrying, words) == _for_the_ask_lane(run_at(status), words)


# ── stage 3: the evidence, standardised ──────────────────────────────────────

EVIDENCE = """---
department: Slaughter
covered: financial
not elicited: we ran out of time before the legal side of it
---

# Slaughter interview

Torsten Ahlgrim: MTPD: 24 h for the slaughter process.
Petra Nolte: RTO: 8 h for the stunning line.
Petra Nolte: RTO: for the slaughter line we never settled one.
Torsten Ahlgrim: Depends on: ammonia refrigeration, the sticking-pen conveyor.
"""

ASSETS = {"KA-01": {"name": "ammonia refrigeration", "department": "Slaughter"}}

#: A method naming three impact categories where `METHOD_FILE` names one, so that the interview
#: above — which covers the financial one — leaves two of them unreached and the card has to say
#: which two. The lenses are the room's own: a card that named the same two whatever the method
#: said would be hard-coding the method the walk is walking to.
THREE_LENSES = {**METHOD_FILE, "scenarios": [{"id": "financial"}, {"id": "legal-regulatory"},
                                             {"id": "reputational"}]}

NAMED = "Torsten gave me 6 h for that line last week, not 8"


def bound(tmp_path, transcript=EVIDENCE, method=METHOD_FILE):
    """A room walked to stage 3: the scope agreed, and an interview with evidence in it bound."""
    folder = room(tmp_path, method=method)
    (folder / INTERVIEWS / "26_08_00_interview.md").write_text(transcript, encoding="utf-8")
    held = json.loads((folder / REGISTER).read_bytes())
    (folder / REGISTER).write_text(json.dumps({**held, **ASSETS}), encoding="utf-8")
    stage_2 = onward(folder, said(folder, open_bia(folder, "Slaughter")))[0]
    return folder, said(folder, stage_2, ENDORSED, picked=stage_2.interviews[0])


def reached(tmp_path, answer=None):
    """The stage 3 card the walk serves, and the room it was served from."""
    folder, stage_2 = bound(tmp_path)
    card = onward(folder, stage_2)[0]
    return folder, (card if answer is None else said(folder, card, answer))


def test_answering_stage_two_is_what_serves_stage_three(tmp_path):
    """Read off the room, never asked for by name (ADR-0010)."""
    folder, card = reached(tmp_path)
    assert (card.stage, card.heading) == (STAGE_3, HEADING_3)
    assert card.buttons == GRADIENT


def test_the_card_leads_with_what_the_evidence_forces_a_decision_about(tmp_path):
    _folder, card = reached(tmp_path)
    assert card.body.startswith(LEAD)
    assert card.body.index("sticking-pen conveyor") < card.body.index(SETTLED)


def test_a_card_with_nothing_to_decide_leads_with_what_is_settled(tmp_path):
    settled = EVIDENCE.replace(", the sticking-pen conveyor", "")
    _folder, card = reached_with(tmp_path, settled)
    assert card.body.startswith(SETTLED)
    assert LEAD not in card.body


def reached_with(tmp_path, transcript):
    folder, stage_2 = bound(tmp_path, transcript)
    return folder, onward(folder, stage_2)[0]


def test_the_stage_three_card_asks_one_decision_and_states_the_rule_it_is_asked_under(tmp_path):
    _folder, card = reached(tmp_path)
    assert (card.decision, card.rule) == (DECISION_3, RULE_3)
    assert card.screen.endswith(f"{DECISION_3}\n\n{RULE_3}"), "the ask is what the card ends on"


def test_the_stage_three_card_carries_the_four_labels_as_data_and_not_only_as_controls(tmp_path):
    _folder, card = reached(tmp_path)
    assert card.gradient == GRADIENT == card.buttons


def test_the_stage_three_card_carries_the_rooms_own_method_and_not_a_hard_coded_one(tmp_path):
    _folder, card = reached(tmp_path)
    assert card.method == COPIED_METHOD


def test_the_card_says_which_categories_the_interview_never_reached_and_why(tmp_path):
    """The method's own categories, in the method's order, and the transcript's own reason."""
    folder, stage_2 = bound(tmp_path, method=THREE_LENSES)
    card = onward(folder, stage_2)[0]
    assert UNREACHED.format(lenses="legal-regulatory, reputational",
                            reason="we ran out of time before the legal side of it") in card.body
    assert card.proposal["worst_case"] == {"legal-regulatory": UNKNOWN, "reputational": UNKNOWN}


def test_the_settled_evidence_is_said_in_the_words_it_was_settled_in(tmp_path):
    """Each figure with the sentence it was said in, and the owner's own marked as his."""
    _folder, card = reached(tmp_path)
    assert OWNER_SAYS.format(
        speaker="Torsten Ahlgrim", label="MTPD", value="24 h",
        quote="Torsten Ahlgrim: MTPD: 24 h for the slaughter process.") in card.body
    assert ASSERTED.format(label="RTO", value="8 h",
                           quote="Petra Nolte: RTO: 8 h for the stunning line.") in card.body
    assert RESOLVES.format(heard="ammonia refrigeration", asset_id="KA-01") in card.body
    assert f"{SETTLED}\n\n" in card.body, "one blank line between paragraphs, and nothing else"


def test_the_card_goes_through_the_one_door_a_card_reaches_a_human_by(tmp_path):
    """Its own draft is what it is checked against: the figures are not on disk until the press."""
    _folder, card = reached(tmp_path)
    assert render(STAGE_3, card.screen, card.record) == card.screen
    with pytest.raises(CardGeneratorBug):
        render(STAGE_3, card.screen + " That's about a working day.", card.record)


def test_the_source_line_names_the_transcript_and_the_register(tmp_path):
    folder, card = reached(tmp_path)
    assert set(card.sources) == {f"{INTERVIEWS}/26_08_00_interview.md", REGISTER, METHOD}
    assert all((folder / path).is_file() for path in card.sources)


def test_a_room_with_no_register_names_none_on_its_source_line(tmp_path):
    folder, stage_2 = bound(tmp_path)
    (folder / REGISTER).unlink()
    assert REGISTER not in onward(folder, stage_2)[0].sources


def test_the_endorsed_proposal_goes_to_the_run_state_and_no_document_is_written(tmp_path):
    folder, card = reached(tmp_path)
    before = {path for path in folder.rglob("*") if path.is_file()}

    answered = said(folder, card, ENDORSED)

    saved = read_record(folder, run_file("Slaughter"))
    assert saved["evidence"] == card.proposal["evidence"]
    assert saved["not_elicited"] == "we ran out of time before the legal side of it"
    assert without_telemetry(saved["decisions"][-1]) == {"stage": STAGE_3, "gradient": ENDORSED}
    # 241: and the run as it stood before the close, which a reopen goes back to; run state too
    at_close = folder / walk.AT_STEP_3 / "slaughter.json"
    assert {path for path in folder.rglob("*") if path.is_file()} == before | {at_close}
    assert json.loads(at_close.read_bytes()) == card.saved
    assert answered.buttons == () and STANDARDISED in answered.body


def test_the_answered_card_is_the_stage_it_answered_and_carries_the_record_it_saved(tmp_path):
    folder, answered = reached(tmp_path, answer=ENDORSED)
    saved = read_record(folder, run_file("Slaughter"))
    assert (answered.stage, answered.heading) == (STAGE_3, HEADING_3)
    assert answered.saved == saved
    assert answered.revision == saved["revision"], "a page that presses again knows what it read"


def test_a_transcript_that_reached_every_category_records_no_unknown(tmp_path):
    covered = EVIDENCE.replace("covered: financial", "covered: financial, legal-regulatory")
    folder, card = reached_with(tmp_path, covered)
    assert card.proposal["worst_case"] == {}
    assert UNREACHED.split("{")[0] not in card.body


def test_where_the_transcript_gives_no_reason_the_reason_is_not_stated(tmp_path):
    silent = "\n".join(line for line in EVIDENCE.splitlines()
                       if not line.startswith("not elicited:"))
    folder, card = reached_with(tmp_path, silent)
    said(folder, card, ENDORSED)
    assert read_record(folder, run_file("Slaughter"))["not_elicited"] == NOT_STATED


def test_a_press_that_lost_the_race_does_not_land_on_the_newer_record(tmp_path):
    """The stale answer reaches stage 4, so the room is one whose record the referee passes: over a
    refused one the refusal answers first and nothing reaches the race at all (ticket 170)."""
    folder, stage_2 = bound(tmp_path, SCORED)
    card = onward(folder, stage_2)[0]
    said(folder, card, ENDORSED)

    overtaken = said(folder, card, "blocked")

    assert overtaken.body.startswith(OVERTAKEN)
    assert read_record(folder, run_file("Slaughter"))["decisions"][-1]["gradient"] == ENDORSED


# ── ticket 172: a stale answer at stage 4 writes nothing, even when the record would pass ──
#
# Two answers on one card revision, applied in turn. The winner answers stage 3; the loser, still
# holding that revision, is routed to stage 4 (the stage the room now waits on) and loses there.
# Until 172 it lost only after `_land` had written the record the referee passed: the stale check
# was the run's compare-and-set, which came second.


def two_answers_on_one_revision(tmp_path, loser="blocked"):
    """The winner's answer, then the room's bytes, then the loser's answer on the same revision."""
    folder, stage_2 = bound(tmp_path, SCORED)
    card = onward(folder, stage_2)[0]
    winner = said(folder, card, ENDORSED)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    return folder, winner, before, said(folder, card, loser)


@pytest.mark.parametrize("loser", [*GRADIENT, "yes, that's fine"])
def test_the_losing_answer_writes_nothing_and_is_told_it_lost(tmp_path, loser):
    """Red on main at b76e4dd: the loser wrote the room's record (and the record passes, so 170's
    refusal check never stood in its way) before the run's compare-and-set refused it."""
    folder, _winner, before, lost = two_answers_on_one_revision(tmp_path, loser)

    assert lost.body.startswith(OVERTAKEN), "the stale answer was not refused as stale"
    assert (lost.stage, lost.heading) == (STAGE_4, HEADING_4)
    assert read_record(folder, RECORD) is None, "the losing answer wrote the record"
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before


def test_a_run_that_moves_after_the_stale_check_still_loses_at_the_run_write(tmp_path, monkeypatch):
    """The compare-and-set behind `_stale`: a run that moves between the land and the run's write
    still refuses this answer as overtaken, and draws no views and no stage 5 over a run this
    answer never saved.

    Since ticket 211 the press holds the room's lock from before it reads the run's revision until
    after it has saved it, so no other tab can move the run in this window: the plant is the
    press's own thread, and what it pins is the store's compare-and-set behind the check rather
    than a race that is still open."""
    folder, card = refereed(tmp_path)
    landing = walk._land

    def then_the_run_moves(room_folder, drawn):
        landed = landing(room_folder, drawn)
        moved_on(room_folder)
        return landed

    monkeypatch.setattr(walk, "_land", then_the_run_moves)
    handed = walk.answer(folder, "Slaughter", ENDORSED, card.revision,
                         record_revision=card.record_revision)

    assert [each.stage for each in handed] == [STAGE_4]
    assert handed[0].body.startswith(OVERTAKEN)
    assert read_record(folder, run_file("Slaughter"))["decisions"][-1]["stage"] == STAGE_3
    assert not [view for view in views.FOUR
                if (folder / views.folder(card.proposal[BIA]) / view).exists()], (
        "views drawn over a lost run")


def test_a_run_that_moved_before_the_land_leaves_no_record_behind(tmp_path, monkeypatch):
    """Ticket 211, ticket 208's finding B6: the window between the stale check and the land.

    A press whose *record* has not moved but whose *run* has — two of his tabs, one of them back
    at stage 2 — used to land the BIA record and be told it had lost afterwards, because the only
    thing that refused it was the run's compare-and-set in `_save`, after the write. The record it
    signed was then the losing press's. The plant is the other tab arriving in that window: the run
    moves in the breath after the door's own stale check has passed, and before the land, so the
    only thing that can still refuse this answer is the press's second read of the run under the
    room's lock. The seam is `_stale` itself, the way ticket 208's own race is planted below.
    """
    folder, card = refereed(tmp_path)
    checking, checks = walk._stale, []

    def then_the_other_tab_moves(room_folder, read):
        checks.append(checking(room_folder, read))
        if len(checks) == 1:
            moved_on(room_folder)
        return checks[-1]

    monkeypatch.setattr(walk, "_stale", then_the_other_tab_moves)
    handed = walk.answer(folder, "Slaughter", ENDORSED, card.revision,
                         record_revision=card.record_revision)

    assert checks[0] is False, "the door's own check refused this answer before the window opened"
    assert [each.stage for each in handed] == [STAGE_4]
    assert handed[0].body.startswith(OVERTAKEN)
    assert read_record(folder, RECORD) is None, "the press that lost wrote the BIA record"
    assert not [view for view in views.FOUR
                if (folder / views.folder(card.proposal[BIA]) / view).exists()], (
        "views drawn over a lost run")


def test_the_winning_answer_writes_exactly_what_it_wrote_before(tmp_path):
    """The winner of the race answered stage 3 and the stage 4 answer after it still lands whole:
    the record the card drafted, the run saved and drawn, the receipt bound, stage 5 served."""
    folder, winner, _before, _lost = two_answers_on_one_revision(tmp_path)
    card = onward(folder, winner)[0]
    assert card.stage == STAGE_4 and not card.refused

    handed = walk.answer(folder, "Slaughter", ENDORSED, card.revision,
                         record_revision=card.record_revision)

    run = read_record(folder, run_file("Slaughter"))
    assert _without_revision(read_record(folder, RECORD)) == card.proposal[BIA]
    assert without_telemetry(run["decisions"][-1]) == {"stage": STAGE_4, "gradient": ENDORSED}
    assert run[RECEIPT]["record_sha"] == fingerprint(read_record(folder, RECORD))
    assert [each.stage for each in handed] == [STAGE_4, walk.STAGE_5]


# ── a reservation is named in the composer ───────────────────────────────────


def test_a_label_other_than_endorsed_answers_the_stage_and_asks_for_the_naming(tmp_path):
    folder, answered = reached(tmp_path, answer="needs discussion")
    saved = read_record(folder, run_file("Slaughter"))
    assert without_telemetry(saved["decisions"][-1]) == {
        "stage": STAGE_3, "gradient": "needs discussion", "naming": UNNAMED}
    assert answered.body == NAMING
    assert answered.buttons == (), "the stage is answered, so nothing is left to press"


def test_the_naming_is_kept_exactly_as_it_was_typed(tmp_path):
    folder, _answered = reached(tmp_path, answer="needs discussion")

    taken = typed(folder, NAMED)[0]

    assert namings(read_record(folder, run_file("Slaughter"))) == ((STAGE_3, NAMED),)
    assert taken.body == TAKEN


def test_the_card_that_takes_the_naming_is_the_stage_it_was_named_on(tmp_path):
    folder, _answered = reached(tmp_path, answer="needs discussion")

    taken = typed(folder, NAMED)[0]

    saved = read_record(folder, run_file("Slaughter"))
    assert (taken.stage, taken.heading) == (STAGE_3, HEADING_3)
    assert taken.saved == saved
    assert taken.revision == saved["revision"], "the naming is a write, and it moved the revision"


def test_a_naming_that_lost_the_race_leaves_the_newer_run_standing(tmp_path):
    """A naming is a write and goes through the same compare-and-set as every other answer.

    What the manager gets back is the stage they reserved something on, re-read and carrying the
    news — not a stage 3 heading over a stage they have moved past — and the reservation is still
    sitting there unnamed for them to type again.
    """
    folder, _answered = reached(tmp_path, answer="needs discussion")
    read_at = read_record(folder, run_file("Slaughter"))["revision"]
    moved_on(folder)

    overtaken = walk.answer(folder, "Slaughter", NAMED, read_at)[0]

    assert overtaken.body.startswith(OVERTAKEN)
    assert (overtaken.stage, overtaken.heading) == (STAGE_3, HEADING_3)
    assert namings(read_record(folder, run_file("Slaughter"))) == ((STAGE_3, UNNAMED),)


def test_the_naming_lands_on_the_answer_it_was_typed_against_and_on_no_other():
    """A record is the walk's whole memory: an earlier card silently dropped by the write that
    takes a naming would take a stage's answer out of the signature with it."""
    walk = {"decisions": [{"stage": STAGE, "gradient": ENDORSED},
                          {"stage": 2, "gradient": ENDORSED},
                          {"stage": STAGE_3, "gradient": "blocked", "naming": UNNAMED}]}

    named = _named(walk, NAMED)

    assert [decision["stage"] for decision in named["decisions"]] == [STAGE, 2, STAGE_3]
    assert named["decisions"][:-1] == walk["decisions"][:-1]
    assert named["decisions"][-1]["naming"] == NAMED


def test_a_walk_that_has_answered_nothing_is_not_waiting_for_a_naming(tmp_path):
    """The composer is the manager's until a card of theirs reserves something."""
    folder = room(tmp_path)
    write_record(folder, run_file("Slaughter"), {"process": "Slaughter"}, 0)
    assert typed(folder, "What does MTPD actually mean?") == ()


def test_once_the_naming_is_taken_the_composer_is_the_managers_again(tmp_path):
    folder, _answered = reached(tmp_path, answer="endorsed with reservations")
    typed(folder, NAMED)
    assert typed(folder, "What does MTPD actually mean?") == ()


def test_an_endorsement_never_holds_the_composer(tmp_path):
    folder, _answered = reached(tmp_path, answer=ENDORSED)
    assert typed(folder, "What does MTPD actually mean?") == ()


def test_a_room_with_no_walk_in_it_never_holds_the_composer(tmp_path):
    assert typed(room(tmp_path), "What does MTPD actually mean?") == ()


def test_a_reservation_nobody_names_reaches_the_signature_as_unnamed(tmp_path):
    folder, _answered = reached(tmp_path, answer="endorsed with reservations")
    carried = namings(read_record(folder, run_file("Slaughter")))
    assert carried == ((STAGE_3, UNNAMED),)
    assert [stage for stage, words in carried if words == ENDORSED] == []


def test_an_endorsed_answer_reserves_nothing_and_carries_nothing(tmp_path):
    folder, _answered = reached(tmp_path, answer=ENDORSED)
    assert namings(read_record(folder, run_file("Slaughter"))) == ()


def test_both_facts_about_an_argued_run_are_reported(tmp_path):
    folder, _answered = reached(tmp_path, answer="needs discussion")
    record = read_record(folder, run_file("Slaughter"))

    said = report(record)

    assert "better BIA" in said and "longer walk" in said


def test_a_run_nobody_argued_with_is_reported_as_the_short_walk_it_was(tmp_path):
    folder, _answered = reached(tmp_path, answer=ENDORSED)
    assert report(read_record(folder, run_file("Slaughter"))) == UNARGUED


def test_a_walk_that_has_answered_no_card_carries_nothing_and_argued_with_nothing():
    """A run opened and not yet pressed is not a walk that argued, and not a walk with a
    reservation on it either — both are read off the decisions, and it has none."""
    assert namings({}) == ()
    assert report({}) == UNARGUED


def test_a_decision_recorded_under_no_label_is_not_counted_as_an_argument():
    assert report({"decisions": [{"stage": STAGE, "decided": "yes"}]}) == UNARGUED


# ── what the signature carries, over every answer a manager could give ───────

#: The answers a walk can hold: one decision per card answered, each under the label it was pressed
#: with. `namings`, `report` and `_reserving` are pure functions of this record and of nothing else,
#: so the properties below are stated against the record rather than through a room. What they pin
#: is the one thing this ticket is about: disagreeing is answered, never softened.
ANSWERS = st.lists(st.sampled_from(GRADIENT), min_size=1, max_size=5)


def walked(answers):
    """The record a walk that answered these cards in this order leaves behind."""
    return {"decisions": [{"stage": stage, **_reserving(answer)}
                          for stage, answer in enumerate(answers, start=1)]}


@given(ANSWERS, st.text(max_size=40))
def test_whatever_is_typed_as_a_naming_is_carried_forward_character_for_character(answers, words):
    """Verbatim over every string, not only over the one a fixture thought of: a correction that
    came back paraphrased would be the manager's disagreement answered on their behalf."""
    assert namings(_named(walked(answers), words))[-1] == (len(answers), words)


@given(st.sampled_from(GRADIENT))
def test_no_label_but_endorsed_is_ever_recorded_as_an_endorsement(answer):
    """And a reservation nobody has named yet is `unnamed` — never rounded up, never refused."""
    recorded = _reserving(answer)
    assert recorded["gradient"] == answer
    assert ("naming" in recorded) == (answer != ENDORSED)
    assert recorded.get("naming", UNNAMED) == UNNAMED


@given(ANSWERS)
def test_a_run_reports_exactly_the_cards_it_was_argued_with(answers):
    """Both facts or neither: a longer walk is only worth reporting beside what bought it."""
    argued = [answer for answer in answers if answer != ENDORSED]
    said = report(walked(answers))
    assert (said == UNARGUED) == (argued == [])
    assert said == UNARGUED or str(len(argued)) in said


# ── stage 4: the refereed record ─────────────────────────────────────────────
#
# The walk stops being reversible here, so every test below drives the real stages that come
# before it: the record that lands is the one a manager could have pressed their way to.

SCORED = EVIDENCE.replace(
    "Petra Nolte: RTO: 8 h for the stunning line.\n",
    "Petra Nolte: RTO: 8 h for the stunning line.\n"
    "Torsten Ahlgrim: Impact financial: 0–4 h 2, 8 h 3, 24 h 5.\n")


def refereed(tmp_path, transcript=SCORED):
    """A room walked to stage 4: stage 3 endorsed, and the card the walk serves after it."""
    folder, stage_2 = bound(tmp_path, transcript)
    stage_3 = onward(folder, stage_2)[0]
    answered = said(folder, stage_3, ENDORSED)
    following = onward(folder, answered)
    assert [card.stage for card in following] == [STAGE_4], "the walk does not serve stage 4 yet"
    return folder, following[0]


def test_answering_stage_three_is_what_serves_stage_four(tmp_path):
    _folder, card = refereed(tmp_path)
    assert (card.stage, card.heading) == (STAGE_4, HEADING_4)
    assert card.buttons == GRADIENT


def test_the_stage_four_card_is_drawn_without_writing_a_byte(tmp_path):
    folder, _card = refereed(tmp_path)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}
    record_card(folder, "Slaughter")
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before


def test_the_record_lands_where_the_walk_says_it_lands(tmp_path):
    folder, card = refereed(tmp_path)
    answered = said(folder, card, ENDORSED)
    landed = read_record(folder, RECORD)
    assert landed["run_id"] == read_record(folder, run_file("Slaughter"))["run_id"]
    assert answered.stage == STAGE_4 and answered.buttons == ()
    assert PICTURE_DRAWN in answered.body


def test_the_bytes_on_disk_are_the_record_the_card_showed(tmp_path):
    folder, card = refereed(tmp_path)
    said(folder, card, ENDORSED)
    landed = read_record(folder, RECORD)
    assert {key: value for key, value in landed.items() if key != "revision"} == card.proposal[BIA]


def test_doing_the_movement_again_after_a_stop_rewrites_nothing(tmp_path):
    """ADR-0010: a re-executed movement whose artefact is already right writes no second copy."""
    folder, card = refereed(tmp_path)
    said(folder, card, ENDORSED)
    was = (folder / RECORD).read_bytes()

    said(folder, record_card(folder, "Slaughter"), ENDORSED)

    assert (folder / RECORD).read_bytes() == was


def test_the_resume_after_the_ordinary_stop_leaves_the_record_at_the_revision_it_landed_on(
        tmp_path):
    """The re-run of the record movement itself, which is the stop ADR-0010 calls ordinary.

    The test above presses again after a *finished* walk, and that press routes past stage 4
    altogether — so it never reaches the guard it is named for. The stop before the picture
    (`saved_only`) is the one that costs the record movement a second time, and there the guard is
    the only thing standing between an identical record and a second write of it. The revision is
    what proves the guard held: identical bytes written twice would still move it under whoever is
    reading them, which is the one thing a re-run must not do.
    """
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)
    landed = read_record(folder, RECORD)
    was = (folder / RECORD).read_bytes()

    resumed = said(folder, record_card(folder, "Slaughter"), ENDORSED)

    assert (folder / RECORD).read_bytes() == was
    assert read_record(folder, RECORD)["revision"] == landed["revision"] == 1
    assert not resumed.body.startswith(OVERTAKEN)


def test_a_record_the_room_moved_on_from_is_not_overwritten_blind(tmp_path, monkeypatch):
    folder, card = refereed(tmp_path)

    overtaken = overtaken_at_the_record(folder, card, monkeypatch)

    assert overtaken.body.startswith(OVERTAKEN)
    assert read_record(folder, RECORD)["run_id"] == ANOTHER_WALKS["run_id"]


def test_a_run_state_that_lost_the_race_leaves_the_newer_decision_standing(tmp_path):
    folder, card = refereed(tmp_path)
    said(folder, onward(folder, open_bia(folder, "Slaughter"))[0], ENDORSED)

    overtaken = said(folder, card, "blocked")

    assert overtaken.body.startswith(OVERTAKEN)


def test_the_walk_is_saved_and_not_yet_finished(tmp_path):
    """The record movement on its own, which is where the walk stands until the receipt binds:
    ticket 17 put the picture behind the same press, so the press itself no longer stops here."""
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["status"] == RECORD_SAVED
    assert where_it_stands(saved) == SAVED_NOT_FINISHED
    assert where_it_stands({}) == ""


def test_a_walk_may_only_move_past_stage_four_over_the_record_it_produced(tmp_path):
    folder, _card = refereed(tmp_path)
    run = read_record(folder, run_file("Slaughter"))
    write_record(folder, RECORD, {"run_id": "another walk's"}, 0)
    with pytest.raises(StaleRecord) as refusal:
        move_past_stage_4(folder, run)
    assert "another walk's" in str(refusal.value)

    said(folder, record_card(folder, "Slaughter"), ENDORSED)
    carried = move_past_stage_4(folder, read_record(folder, run_file("Slaughter")))
    assert carried["run_id"] == run["run_id"]


def test_a_draft_is_checkable_before_anybody_confirms_anything(tmp_path):
    """v1 answered an unconfirmed draft with "approval missing" and showed the content problems
    only after the owner had said yes. The order is the fix; the rule is unchanged."""
    folder, _card = refereed(tmp_path)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    verdict = check_draft(folder, "Slaughter")

    assert verdict.passed and verdict.checked
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before


def test_a_draft_with_a_content_problem_answers_with_the_problem(tmp_path):
    """A quote no file in the room holds: the referee refuses it, and says which."""
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    activity, = saved["activities"]
    activity["evidence"][0]["quote"] = "a sentence nobody ever said"
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])

    verdict = check_draft(folder, "Slaughter")

    assert not verdict.passed
    assert [problem for problem in verdict.rejections if "nobody ever said" in problem]


def test_a_record_the_referee_refuses_is_not_offered_for_acceptance_at_all(tmp_path):
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    saved["activities"][0]["evidence"][0]["quote"] = "a sentence nobody ever said"
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])

    card = record_card(folder, "Slaughter")

    assert card.buttons == () and card.decision == ""
    assert card.body.startswith(REFUSED.split("{")[0])


def test_the_receipt_names_the_checks_that_actually_ran(tmp_path):
    folder, card = refereed(tmp_path)
    answered = said(folder, card, ENDORSED)
    saved = read_record(folder, run_file("Slaughter"))
    assert saved[CHECKED] == list(card.proposal[CHECKED])
    for check in saved[CHECKED]:
        assert check in answered.body
    assert checked_note({}) == "", "a run that checked nothing says nothing about checking"


def test_the_reason_comes_before_the_figure_on_the_stage_four_card(tmp_path):
    _folder, card = refereed(tmp_path)
    said = [part for part in card.body.split("\n\n") if "longest" in part][0]
    assert said.index("reaches") < said.index("stands at")


def test_a_grid_that_reaches_nothing_is_given_no_mtpd_at_all(tmp_path):
    gentle = "\n".join(line for line in SCORED.replace("24 h 5", "24 h 3").splitlines()
                       if "MTPD:" not in line)
    _folder, card = refereed(tmp_path, gentle)
    assert NO_MTPD_SAYS.format(activity="Slaughter") in card.body
    assert "becomes unacceptable" not in card.body, "a figure nobody derived was printed"
    assert "MTPD" not in card.body


def test_a_finding_rides_on_the_card_and_stops_nothing(tmp_path):
    _folder, card = refereed(tmp_path)
    assert card.proposal[FINDINGS] == [] or card.buttons == GRADIENT


def test_the_stage_four_card_goes_through_the_one_door_a_card_reaches_a_human_by(tmp_path):
    _folder, card = refereed(tmp_path)
    assert render(STAGE_4, card.screen, card.proposal[BIA]) == card.screen


#: Every check the referee can run, which is the whole vocabulary a receipt may draw on.
EVERY_CHECK = (QUOTES_CHECK, GRID_CHECK, MTPD_CHECK, RTO_CHECK, RPO_CHECK, BOUNDARY_CHECK)


@given(st.lists(st.sampled_from(EVERY_CHECK), unique=True))
def test_the_receipt_can_only_name_a_check_that_ran(ran):
    """`checked_note` is pure, so the sentence is false-impossible rather than merely unforged.

    Over every subset of the referee's checks, a clause is in the note exactly when its check is
    in the record — there is no run whose receipt claims a check the run did not make, and a run
    that checked nothing says nothing at all. v1's note was a literal asserting "record validated
    and saved" whatever happened, which no input could make false.
    """
    note = checked_note({CHECKED: ran})

    for check in EVERY_CHECK:
        assert (check in note) == (check in ran)
    assert (note == "") == (ran == [])


# ── the card's exact words, and what the press leaves behind ─────────────────
#
# Stage 4 is the movement that does not undo, so what is said on the card and what is left on
# disk are both pinned here word for word: a sentence that reads as prose at a glance can still
# be about the wrong activity, and a run file that looks complete can still carry a fingerprint
# of nothing.


def test_the_stage_four_card_names_the_files_the_bia_was_drawn_from(tmp_path):
    folder, card = refereed(tmp_path)
    assert set(card.sources) == {f"{INTERVIEWS}/26_08_00_interview.md", REGISTER, METHOD}
    assert all((folder / path).is_file() for path in card.sources)


def test_the_stage_four_card_carries_the_four_labels_and_the_rooms_own_method(tmp_path):
    _folder, card = refereed(tmp_path)
    assert card.gradient == GRADIENT == card.buttons
    assert card.method == COPIED_METHOD


def test_the_stage_four_card_asks_one_decision_and_states_the_rule_it_is_asked_under(tmp_path):
    _folder, card = refereed(tmp_path)
    assert (card.decision, card.rule) == (DECISION_4, RULE_4)


def test_the_card_opens_by_naming_the_bia_it_is_about(tmp_path):
    _folder, card = refereed(tmp_path)
    assert card.body.startswith(ACCEPTING.format(process="Slaughter") + "\n\n")


def test_what_the_referee_will_not_settle_is_read_before_what_it_settled(tmp_path):
    """The open items first and the settled record after, so the decision is findable from the
    first screen of a phone rather than from the bottom of the card."""
    folder, card = refereed(tmp_path)
    open_item, = read_record(folder, run_file("Slaughter"))["open_items"]

    assert card.body.index(OPEN_4) < card.body.index(open_item) < card.body.index(DRAWN)


def test_a_run_that_left_nothing_open_leads_straight_to_what_is_settled(tmp_path):
    """A run state that never recorded an open item is a card, not a crash."""
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    was = saved.pop("open_items")
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])

    card = record_card(folder, "Slaughter")

    assert was and was[0] not in card.body
    assert OPEN_4 not in card.body
    assert card.body.index(DRAWN) < card.body.index("Slaughter first reaches")


def test_every_scored_category_shows_its_exact_quote_and_the_activity_it_scored(tmp_path):
    folder, card = refereed(tmp_path)
    activity, = read_record(folder, run_file("Slaughter"))["activities"]

    assert activity["scores"], "the room this is drawn from scores nothing"
    for score in activity["scores"]:
        assert SCORED_SAYS.format(speaker=score["speaker"], lens=score["lens"],
                                  activity=activity["name"], quote=score["quote"]) in card.body


def test_the_mtpd_is_said_with_the_grid_and_the_categories_that_derived_it(tmp_path):
    folder, card = refereed(tmp_path)
    activity, = read_record(folder, run_file("Slaughter"))["activities"]
    horizon, lenses = crossing(activity["impact_grid"], card.method)

    assert MTPD_SAYS.format(activity=activity["name"], lenses=_listed(lenses),
                            horizon=horizon) in card.body


def test_a_dependency_the_register_models_is_resolved_by_name_on_the_card(tmp_path):
    folder, card = refereed(tmp_path)
    activity, = read_record(folder, run_file("Slaughter"))["activities"]
    modelled = [item for item in activity["dependencies"] if item["asset_id"]]

    assert modelled, "the room this is drawn from models no dependency"
    for item in modelled:
        assert RESOLVES.format(heard=item["heard"], asset_id=item["asset_id"]) in card.body


def refused(tmp_path):
    """A room whose draft the referee refuses on two counts: two quotes no file in it holds."""
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    activity, = saved["activities"]
    activity["evidence"][0]["quote"] = "a sentence nobody ever said"
    activity["scores"][0]["quote"] = "another sentence nobody ever said"
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])
    return folder


def test_a_refused_card_says_every_problem_the_referee_found_and_asks_nothing(tmp_path):
    folder = refused(tmp_path)
    verdict = check_draft(folder, "Slaughter")

    card = record_card(folder, "Slaughter")

    assert len(verdict.rejections) > 1, "this room was meant to be wrong twice over"
    assert card.body == refused_says(verdict.rejections)
    assert card.body.count("nobody ever said") == 2, "one sentence per refusal, and both of them"
    assert (card.buttons, card.decision, card.rule) == ((), "", "")


# ── the refusal in the manager's words (ticket 26) ───────────────────────────
#
# The card a manager reaches today reads `activity Slaughter: impact_grid['legal-regulatory']
# missing horizon(s): ['72 h']`, because the body was the referee's own rejections joined end to
# end and every one of those was written for a developer. The referee reports parts now; the
# sentence is written here, where every other string on a card is written.


def test_the_refusal_a_manager_reads_names_no_machine_identifier(tmp_path):
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    del saved["activities"][0]["impact_grid"]["financial"]["24 h"]
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])

    body = record_card(folder, "Slaughter").body

    assert "24 h" in body and "financial" in body and "Slaughter" in body
    for machine in ("impact_grid", "horizon(s)", "['", "']", "activity Slaughter:"):
        assert machine not in body, f"{machine!r} reached the card"


def test_every_way_the_referee_can_refuse_has_words_of_its_own_here() -> None:
    """A kind nothing can word is a card nobody can read, so the two lists are one list."""
    assert set(REFUSAL_SAYS) == set(refusal.KINDS)


def test_a_refusal_is_the_walks_words_and_never_the_referees(tmp_path):
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    rto, = [item for item in saved["activities"][0]["evidence"] if item["label"] == "RTO"]
    rto["value"] = "48 h"
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])
    verdict = check_draft(folder, "Slaughter")

    body = record_card(folder, "Slaughter").body

    rejection, = verdict.rejections
    assert str(rejection) not in body, "the referee's own line was passed through untouched"
    assert "48 h" in body and "24 h" in body, "the figures the record holds are not on it"


def test_a_field_name_is_read_out_as_the_thing_it_stands_for() -> None:
    """The one part that is a list of the acknowledgement's own field names."""
    said = refused_says([refusal.Rejection(
        refusal.UNSCORED_NEEDS_OWNER, "developer's line", activity="Slaughter",
        missing=("approved_by", "review_date"))])

    assert "who accepts it and when it is to be looked at again" in said
    assert "approved_by" not in said and "review_date" not in said


# ── the other door §3 was open by: a part that is not words at all ──────────
#
# A part is whatever the record put where the refusal looked, and `nemo.room_store` holds any JSON
# a stage card can produce — a `null` where a score belongs, a flag, a list. `str()` on one of
# those is `None`, `True`, `{'a': 1}`: Python in front of a manager, which is `docs/voice.md` §3
# by the one door the ticket's own `impact_grid['legal-regulatory']` did not come through.

#: Everything the store will hold in a field a refusal reports, at every shape JSON has.
PARTS = st.recursive(
    st.text(max_size=6) | st.integers(min_value=-2, max_value=9) | st.none() | st.booleans(),
    lambda inner: (st.lists(inner, max_size=2)
                   | st.dictionaries(st.text(max_size=2), inner, max_size=2)),
    max_leaves=3)


@given(PARTS)
def test_a_part_a_manager_reads_is_words_or_a_figure_and_never_python(value):
    """Words as they stand, a figure as itself, and everything else not printed at all.

    A figure keeps printing on purpose: a score of 6 is refused for being off the scale your
    method sets, and a card that would not say *which* figure it means is worse than one that
    does. `True` is not one of those figures, whatever Python says about `bool` and `int`.
    """
    said = _part_says("lens", value)

    assert isinstance(said, str)
    if isinstance(value, str):
        assert said == value
    elif isinstance(value, bool) or not isinstance(value, int | float):
        assert said == NOT_WORDS
    else:
        assert said == str(value)


@given(PARTS.filter(lambda value: value != ""))
def test_a_list_of_parts_is_read_out_one_by_one_and_never_as_a_list(value):
    """A tuple is what the referee reports several of a thing in — bands, categories, allowances.

    The punctuation of a data structure is the whole of what the story is about: `['72 h']` is a
    list printed, and `72 h and 1 week` is two bands said. The empty word is left out because
    what becomes of it is `nemo.figures.listed`'s ruling and not this module's: it drops one, so
    `("", "")` is `""` rather than `" and "`, and that is the same sentence either way.
    """
    said = _part_says("horizons", (value, value))

    assert said == f"{_part_says('horizons', value)} and {_part_says('horizons', value)}"
    assert not set(said) & set("[]{}") or set(str(value)) & set("[]{}")


@given(RECORDS)
def test_no_refusal_of_any_record_the_store_can_hold_prints_python_at_a_manager(record):
    """End to end, over the same records the referee is held to: nothing Python reaches the card.

    `_part_says` is pinned above on its own; this is the pin that the referee cannot report a part
    the walk does not word — a kind whose parts and whose sentence disagree raises here rather
    than on a manager's screen, and a part that is not words is admitted to instead of printed.
    """
    for rejection in referee_review(record, REFEREE_METHOD, REFEREE_FILES).rejections:
        said = refused_says([rejection])
        for name, value in rejection.parts.items():
            for part in value if isinstance(value, tuple) else (value,):
                if isinstance(part, bool) or not isinstance(part, str | int | float):
                    assert str(part) not in said, f"{name} put {part!r} in front of a manager"
                    assert NOT_WORDS in said, f"{name} was dropped rather than admitted to"


@given(RECORDS)
def test_no_refusal_of_any_record_is_the_referees_own_line_passed_through(record):
    """The developer's line is for a log and for a test, and it never reaches a card.

    The BDD scenario proves this over one stand-in line for all 25 kinds; this proves it over the
    lines the referee actually writes, whatever a record the store will hold provokes.
    """
    for rejection in referee_review(record, REFEREE_METHOD, REFEREE_FILES).rejections:
        assert str(rejection) not in refused_says([rejection])


def test_a_score_the_record_left_null_is_admitted_to_and_never_printed(tmp_path):
    """The reachable one, named: `impact_grid[...][...] = null` is a score nobody wrote."""
    folder, _card = refereed(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    saved["activities"][0]["impact_grid"]["financial"]["24 h"] = None
    write_record(folder, run_file("Slaughter"), saved, saved["revision"])

    body = record_card(folder, "Slaughter").body

    assert NOT_WORDS in body
    assert "None" not in body and "financial" in body and "24 h" in body


def test_every_acknowledgement_field_the_referee_can_report_has_words_here() -> None:
    """The second pair of lists that must not drift, the other being `REFUSAL_SAYS` and `KINDS`.

    The referee reports the acknowledgement's own field names; a field with no words here is a
    `KeyError` where a manager's sentence should be.
    """
    said = refused_says([refusal.Rejection(
        refusal.UNSCORED_NEEDS_OWNER, "developer's line", activity="Slaughter",
        missing=tuple(MISSING_SAYS))])

    for words in MISSING_SAYS.values():
        assert words in said


# ── every way of refusing, in the words the manager actually gets ────────────
#
# `REFUSAL_SAYS` and `KINDS` being one list says a sentence exists for every kind; it does not say
# the referee reports the parts that sentence asks for, nor that it reports the record's own
# figures in them. A kind reported with the wrong activity, or with a part left out, is either a
# `KeyError` where the card should be or a card naming the wrong thing — and both of those are the
# story's defect wearing the new mechanism. So: one record per way of refusing, put to the real
# referee, and the whole sentence the manager reads held against a literal.


def _grid_of(record: dict) -> dict:
    return record["activities"][0]["impact_grid"]


def _only_activity(record: dict) -> dict:
    return record["activities"][0]


def _unscore_everything(record: dict) -> None:
    """Every cell 'MISSING' — the grid an owner declined outright, which needs an owner instead."""
    for row in _grid_of(record).values():
        for horizon in row:
            row[horizon] = "MISSING"


#: An acknowledgement of a wholly unscored grid with every field but the review date filled in,
#: so that what a case leaves wrong is the one thing that case is about.
_ACK = {
    "approved_by": "Hilde Ahlgrim", "reason": "the owner declined every figure",
    "review_owner": "Hilde Ahlgrim", "next_question": "what a day off the line costs",
    "owner_informed": "Hilde Ahlgrim",
}


def _accepted_until(record: dict, review_date: str) -> None:
    _unscore_everything(record)
    _only_activity(record)["not_elicited_ack"] = dict(_ACK, review_date=review_date)


def _two_lenses_on_one_quote(record: dict) -> None:
    """One sentence carrying two impact categories, with nobody's name against the reuse."""
    _grid_of(record)["reputation"]["24 h"] = 3
    _only_activity(record)["evidence"].append({
        "type": "transcript_quote", "lens": "reputation",
        "quote": "The line has to keep moving", "source_path": TRANSCRIPT_PATH})
    _only_activity(record)["shared_quote_ack"] = {"lenses": ["financial", "reputation"]}


def _fabricated_quote(record: dict) -> None:
    _only_activity(record)["evidence"][0]["quote"] = "we would be back in five minutes"


def _fabricated_quote_citing_nothing(record: dict) -> None:
    _fabricated_quote(record)
    del _only_activity(record)["evidence"][0]["source_path"]


#: `(what it is about, what the record does, the kind, the sentence a manager reads)`. The third
#: column is what the referee reports and the fourth is what this module words it as — the two
#: halves of the seam, held apart on purpose so neither can be read out of the other.
_REFUSALS = [
    ("a time band nobody scored",
     lambda record: _grid_of(record)["legal-regulatory"].pop("72 h"),
     refusal.MISSING_HORIZONS,
     "Nobody scored legal-regulatory for slaughter at 72 h, and your method asks for a figure at "
     "every one of its time horizons before I can say how long the activity can be down."),
    ("a time band the method does not name",
     lambda record: _grid_of(record)["legal-regulatory"].update({"9 h": 1}),
     refusal.UNKNOWN_HORIZONS,
     "slaughter carries legal-regulatory scores at 9 h, which are not time horizons your method "
     "names, so there is nothing to read them against."),
    ("a score off the severity scale",
     lambda record: _grid_of(record)["legal-regulatory"].update({"72 h": 9}),
     refusal.INVALID_SCORE,
     "The legal-regulatory score for slaughter at 72 h is 9, which is not a level on the severity "
     "scale your method sets."),
    ("a row that is not scores against time bands",
     lambda record: _grid_of(record).update({"legal-regulatory": "badly hit"}),
     refusal.UNREADABLE_ROW,
     "I cannot read the legal-regulatory scores for slaughter as a figure against each time "
     "horizon."),
    ("a grid that is not a grid",
     lambda record: _only_activity(record).update({"impact_grid": "badly hit"}),
     refusal.UNREADABLE_GRID,
     "I cannot read what an outage costs slaughter at all."),
    ("an impact category the method does not name",
     lambda record: _grid_of(record).update({"brand-value": dict.fromkeys(HORIZONS, 1)}),
     refusal.UNKNOWN_LENS,
     "slaughter is scored for brand-value, which is not one of the impact categories your method "
     "names."),
    ("an impact category with no row at all",
     lambda record: _grid_of(record).pop("reputation"),
     refusal.MISSING_LENSES,
     "slaughter has no scores at all for reputation, and those are impact categories your method "
     "asks a BIA to cover."),
    ("a time band no category put a figure on",
     lambda record: [row.update({"72 h": "MISSING"}) for row in _grid_of(record).values()],
     refusal.BAND_UNSCORED,
     "No impact category put a figure on slaughter at 72 h: it is not rated in the source. To "
     "sign this BIA as it stands, somebody has to accept that in writing: who accepts it, what "
     "was asked and declined, and who gets asked when it is looked at again."),
    ("an acceptance of an unrated time band with a field blank",
     lambda record: [row.update({"72 h": "MISSING"}) for row in _grid_of(record).values()]
     and _only_activity(record).update({"unrated_band_ack": {"72 h": {
         "approved_by": "Hilde Ahlgrim", "reason": "", "review_owner": "Hilde Ahlgrim"}}}),
     refusal.UNRATED_BAND_NEEDS_OWNER,
     "The acceptance that slaughter is not rated at 72 h in the source does not say what was "
     "asked and declined."),
    ("nothing scored anywhere and nobody accepting it",
     _unscore_everything,
     refusal.UNSCORED_NEEDS_OWNER,
     "Nothing was scored for slaughter anywhere. Your method allows that, but somebody has to "
     "accept it in writing, and this BIA does not say who accepts it, what was asked and "
     "declined, who gets asked when it is looked at again, what answer would produce a figure, "
     "who told the owner that it is on record and when it is to be looked at again."),
    ("an acceptance with two of its fields blank",
     lambda record: _accepted_until(record, "2099-01-01") or _only_activity(record)[
         "not_elicited_ack"].update({"reason": "", "owner_informed": ""}),
     refusal.UNSCORED_NEEDS_OWNER,
     "Nothing was scored for slaughter anywhere. Your method allows that, but somebody has to "
     "accept it in writing, and this BIA does not say what was asked and declined and who told "
     "the owner that it is on record."),
    ("an acceptance whose review date is not a date",
     lambda record: _accepted_until(record, "soon"),
     refusal.REVIEW_DATE_UNUSABLE,
     "The acceptance of the unscored assessment for slaughter carries no date to look at it "
     "again, and an acceptance without one is a shrug rather than an acceptance."),
    ("an acceptance whose review date has gone by",
     lambda record: _accepted_until(record, "2020-01-01"),
     refusal.REVIEW_DATE_PASSED,
     "The unscored assessment for slaughter was accepted until 2020-01-01, and that day has gone "
     "by: it is due to be looked at again, or the figures are due from the owner."),
    ("a scored category nothing said is marked against",
     lambda record: _grid_of(record)["reputation"].update({"24 h": 3}),
     refusal.LENS_UNQUOTED,
     "slaughter is scored for reputation, and no sentence from the interview is marked as what "
     "that score rests on."),
    ("one sentence carrying two categories and nobody's name",
     _two_lenses_on_one_quote,
     refusal.UNSIGNED_ACK,
     "The note that one sentence is the evidence for financial and reputation on slaughter "
     "carries nobody's name, and a note nobody put their name to is not an acceptance."),
    ("words that are not in the file they cite",
     _fabricated_quote,
     refusal.QUOTE_NOT_FOUND,
     "No file in your room holds the words “we would be back in five minutes”, which slaughter "
     "rests on."),
    ("words that are in no file and cite none",
     _fabricated_quote_citing_nothing,
     refusal.QUOTE_NOT_FOUND,
     "No file in your room holds the words “we would be back in five minutes”, which slaughter "
     "rests on."),
    ("a cited file the room has not got",
     lambda record: _only_activity(record)["evidence"][0].update(
         {"source_path": "07_Interviews/nobody-said-this.md"}),
     refusal.EVIDENCE_UNCHECKED,
     "The words slaughter rests on could not be held against any file in your room, so nothing "
     "behind it was checked."),
    ("a kind of evidence the method does not allow",
     lambda record: _only_activity(record)["evidence"][0].update({"type": "hearsay"}),
     refusal.UNREADABLE_EVIDENCE,
     "I cannot read one of the pieces of evidence behind slaughter as words somebody said."),
    ("a file path filed where the words belong",
     lambda record: _only_activity(record).update(
         {"evidence": [{"type": "company_file", "ref": "05_Files/register.md"}]}),
     refusal.UNREADABLE_EVIDENCE,
     "I cannot read one of the pieces of evidence behind slaughter as words somebody said."),
    ("evidence whose quote is blank",
     lambda record: _only_activity(record)["evidence"][0].update({"quote": "   "}),
     refusal.UNREADABLE_EVIDENCE,
     "I cannot read one of the pieces of evidence behind slaughter as words somebody said."),
    ("evidence that is not an item at all",
     lambda record: _only_activity(record).update({"evidence": ["just a string"]}),
     refusal.UNREADABLE_EVIDENCE,
     "I cannot read one of the pieces of evidence behind slaughter as words somebody said."),
    ("a quote tagged with a category the method does not name",
     lambda record: _only_activity(record)["evidence"][0].update({"lens": "brand-value"}),
     refusal.UNKNOWN_LENS,
     "slaughter is scored for brand-value, which is not one of the impact categories your method "
     "names."),
    ("no recovery target at all",
     lambda record: _only_activity(record).pop("recovery_target"),
     refusal.NO_RECOVERY_TARGET,
     "Nobody said how long slaughter may take to come back."),
    ("a recovery target that is not a length of time",
     lambda record: _only_activity(record).update({"recovery_target": "as soon as we can"}),
     refusal.UNREADABLE_TARGET,
     "The recovery target for slaughter is as soon as we can, and I cannot read that as a length "
     "of time to hold against how long the activity can be down."),
    ("a recovery target later than the MTPD",
     lambda record: _only_activity(record).update({"recovery_target": "48 h"}),
     refusal.TARGET_OUTSIDE_MTPD,
     "slaughter is to be back within 48 h, and being down becomes unacceptable at 24 h, so the "
     "target is not inside it. Go back to the owner and either bring the target forward, or have "
     "them say in as many words that they accept the gap."),
    ("a data-loss answer the method does not allow",
     lambda record: _only_activity(record).update({"rpo": "3 h"}),
     refusal.RPO_NOT_ALLOWED,
     "The data-loss answer for slaughter is 3 h, and your method allows 0 h (no loss), 4 h (ERP "
     "order data), 24 h (batch/traceability) and n/a (physical)."),
    ("a continuity plan carried in the BIA",
     lambda record: record.update({"plan": {"immediate actions": "call the plant"}}),
     refusal.BOUNDARY,
     "This BIA carries a continuity plan. A BIA hands over what has to be back and by when, and "
     "stops before either of those is drafted."),
    ("a handed-over item that says which kind it is",
     lambda record: record.update({"pp4_handoff": ["buy a generator"]}),
     refusal.HANDOFF_ITEM,
     "One of the things this BIA hands over reads “buy a generator”, and each one has to say "
     "whether it is a gap, an option, a decision for a human, or evidence nobody has."),
    ("a disagreement handed to the AI",
     lambda record: record.update(
         {"comparison": [{"issue": "the RTO", "escalated_to": "the assistant"}]}),
     refusal.OWNER_NOT_A_PERSON,
     "The disagreement over “the RTO” is recorded as owned by the assistant, which is me rather "
     "than a person who can settle it."),
    ("a BIA about no activity",
     lambda record: record.update({"activities": []}),
     refusal.NO_ACTIVITIES,
     "This BIA records no activity at all, and a BIA is about at least one of them."),
    ("an activity that is not an activity",
     lambda record: record.update({"activities": ["not an activity"]}),
     refusal.MALFORMED_ACTIVITY,
     "I cannot read one of the activities in this BIA."),
]


@pytest.mark.parametrize(("about", "spoil", "kind", "sentence"), _REFUSALS,
                         ids=[case[0] for case in _REFUSALS])
def test_a_way_of_refusing_reaches_the_manager_as_this_sentence(about, spoil, kind, sentence):
    """The referee's parts, this module's words, and the record's own figures in them.

    `about` is the parametrize id and is not read: what a case is about is what it is called.
    """
    record = valid_record()
    spoil(record)

    rejection, = [item for item in referee_review(record, REFEREE_METHOD, REFEREE_FILES).rejections
                  if item.kind == kind]

    assert refused_says([rejection]) == REFUSED.format(problems=sentence)


def test_evidence_nothing_in_the_room_can_be_held_against_says_so(tmp_path):
    """The other door into *unchecked*: not a missing file, but a room with no readable file.

    The table above reaches this kind through a `source_path` the room has not got. This reaches
    it through the room itself, which is a different branch and a different developer's line.
    """
    rejection, = referee_review(valid_record(), REFEREE_METHOD, {}).rejections

    assert rejection.kind == refusal.EVIDENCE_UNCHECKED
    assert refused_says([rejection]) == REFUSED.format(
        problems="The words slaughter rests on could not be held against any file in your room, "
                 "so nothing behind it was checked.")


def test_a_chat_confirmation_not_in_his_words_names_his_message_and_no_file() -> None:
    """Ticket 132: his confirmation is refused as words not found, and the card says where they
    were looked for — his message of that day, never a file, which it was never held against.
    A file quote's sentence stays as the table above pins it."""
    record = valid_record()
    _only_activity(record)["evidence"].append(
        {"type": "chat_confirmation", "words": "Record RTO 2 h", "on": "2026-09-23",
         "turn_id": "t-7"})
    turns = {"t-7": {"words": "Record RTO 8 h", "on": "2026-09-23"}}

    rejection, = referee_review(record, REFEREE_METHOD, REFEREE_FILES, turns).rejections
    said = refused_says([rejection])

    assert rejection.kind == refusal.QUOTE_NOT_FOUND
    assert said == REFUSED.format(
        problems="Your message of 2026-09-23 doesn't contain the words “Record RTO 2 h”, which "
                 "slaughter rests on.")
    assert "file" not in said


_CHAT_UNCHECKED = [
    ("a turn the room's conversation does not hold", {"turn_id": "t-99"},
     "Your message of 2026-09-23 that slaughter rests on isn't in this room's conversation."),
    ("a day that is not his turn's", {"on": "2026-09-01"},
     "Your message that slaughter rests on is dated 2026-09-23, not 2026-09-01."),
]


@pytest.mark.parametrize(("about", "spoil", "sentence"), _CHAT_UNCHECKED,
                         ids=[case[0] for case in _CHAT_UNCHECKED])
def test_a_chat_confirmation_nothing_could_be_checked_against_names_his_message(
        about, spoil, sentence):
    """Ticket 132: a chat confirmation refused as unchecked was never held against a file either,
    so its card names his message, as the table above's file cases do not."""
    record = valid_record()
    _only_activity(record)["evidence"].append(
        {"type": "chat_confirmation", "words": "Record RTO 8 h", "on": "2026-09-23",
         "turn_id": "t-7", **spoil})
    turns = {"t-7": {"words": "Record RTO 8 h", "on": "2026-09-23"}}

    rejection, = referee_review(record, REFEREE_METHOD, REFEREE_FILES, turns).rejections
    said = refused_says([rejection])

    assert rejection.kind == refusal.EVIDENCE_UNCHECKED
    assert said == REFUSED.format(problems=sentence)
    assert "file" not in said


def test_an_acceptance_missing_two_fields_is_one_refusal_in_the_developers_line_too() -> None:
    """The line a log holds keeps every field, joined by a space and not by anything else."""
    record = valid_record()
    _accepted_until(record, "2099-01-01")
    _only_activity(record)["not_elicited_ack"].update({"reason": "", "owner_informed": ""})

    rejection, = referee_review(record, REFEREE_METHOD, REFEREE_FILES).rejections

    assert str(rejection) == (
        'activity slaughter: not_elicited_ack needs a "reason" naming what was asked and declined '
        "— an acceptance that does not say what it accepted cannot be audited later "
        'activity slaughter: not_elicited_ack needs "owner_informed" — the owner who declined is '
        "told that a document records their declining, and who told them is part of the record")


def test_a_record_wrong_twice_over_says_both_things_in_the_order_they_were_found() -> None:
    """Two refusals from two different reviews of the record, joined by one space and nothing else.

    The boundary refusal is appended by the check that runs last, over the whole record rather
    than over an activity, so this also pins that the boundary adds to what the activities found
    instead of replacing it — a record that carried a plan would otherwise say only the plan.
    """
    record = valid_record()
    del _only_activity(record)["recovery_target"]
    record["plan"] = {"immediate actions": "call the plant"}

    verdict = referee_review(record, REFEREE_METHOD, REFEREE_FILES)

    assert [item.kind for item in verdict.rejections] == [
        refusal.NO_RECOVERY_TARGET, refusal.BOUNDARY]
    assert refused_says(verdict.rejections) == REFUSED.format(
        problems="Nobody said how long slaughter may take to come back. This BIA carries a "
                 "continuity plan. A BIA hands over what has to be back and by when, and stops "
                 "before either of those is drafted.")


def test_the_press_is_recorded_as_the_stage_four_answer_it_was(tmp_path):
    folder, card = refereed(tmp_path)

    said(folder, card, "blocked")

    decision = read_record(folder, run_file("Slaughter"))["decisions"][-1]
    assert without_telemetry(decision) == {"stage": STAGE_4, **_reserving("blocked")}


def test_the_run_file_carries_the_fingerprint_of_the_record_that_landed(tmp_path):
    folder, card = refereed(tmp_path)

    said(folder, card, ENDORSED)

    saved = read_record(folder, run_file("Slaughter"))
    assert saved["record_sha"] == fingerprint(read_record(folder, RECORD))


def test_the_answered_card_is_the_stage_four_card_carrying_what_it_saved(tmp_path):
    folder, card = refereed(tmp_path)

    answered = said(folder, card, ENDORSED)

    saved = read_record(folder, run_file("Slaughter"))
    assert (answered.stage, answered.heading) == (STAGE_4, HEADING_4)
    assert answered.saved == saved and answered.revision == saved["revision"]


def test_a_run_already_on_file_walks_from_stage_one_to_a_landed_record(tmp_path):
    """ADR-0011's own room, end to end: a prepared chat that arrives at stage 1 with a run on file
    and nothing decided, pressed through to the record.

    This is the shape the 2026-09-13 review measured `KeyError('run_id')` on at stage 4, and the
    walk is driven rather than the press asserted about because the identity, the method and the
    sources the first press fills in are read by the three stages after it — `refereed` above walks
    from `room`, which ships no run at all and therefore mints one on the way past the defect.
    """
    folder = prepared_room(tmp_path)
    (folder / INTERVIEWS / "26_08_00_interview.md").write_text(SCORED, encoding="utf-8")
    held = json.loads((folder / REGISTER).read_bytes())
    (folder / REGISTER).write_text(json.dumps({**held, **ASSETS}), encoding="utf-8")

    stage_2 = onward(folder, said(folder, open_bia(folder, "Slaughter")))[0]
    stage_3 = onward(folder, said(folder, stage_2, ENDORSED, picked=stage_2.interviews[0]))[0]
    stage_4 = onward(folder, said(folder, stage_3, ENDORSED))[0]
    answered = said(folder, stage_4, ENDORSED)

    run = read_record(folder, run_file("Slaughter"))
    assert (stage_4.stage, answered.stage) == (STAGE_4, STAGE_4)
    assert read_record(folder, RECORD)["run_id"] == run["run_id"]
    assert stage_3.method == COPIED_METHOD
    assert run["sources"] == list(stage_3.sources) and stage_3.source_line.startswith("Source: ")


def test_the_acceptance_says_what_was_written_what_was_checked_and_what_is_left(tmp_path):
    folder, card = refereed(tmp_path)

    answered = said(folder, card, ENDORSED)

    saved = read_record(folder, run_file("Slaughter"))
    assert answered.body == " ".join([ACCEPTED, checked_note(saved), PICTURE_DRAWN])


def test_the_receipt_reads_as_one_sentence_however_many_checks_it_names():
    """Commas between them and an *and* before the last, at one check and at three."""
    one, two, three = EVERY_CHECK[:3]
    assert checked_note({CHECKED: [one]}) == CHECKED_NOTE.format(checks=one)
    assert checked_note({CHECKED: [one, two]}) == CHECKED_NOTE.format(checks=f"{one} and {two}")
    assert checked_note({CHECKED: [one, two, three]}) == CHECKED_NOTE.format(
        checks=f"{one}, {two} and {three}")


def test_a_stage_three_card_nobody_answered_is_followed_by_nothing(tmp_path):
    """Stage 4 follows the answer on disk, not the stage the card in hand happens to be at."""
    folder, card = reached(tmp_path)
    assert onward(folder, card) == ()


def test_a_stage_three_card_with_no_run_behind_it_is_followed_by_nothing(tmp_path):
    folder, card = reached(tmp_path)
    assert onward(folder, replace(card, saved=None)) == ()


def test_a_run_with_no_identity_at_all_carries_nothing_past_stage_four(tmp_path):
    folder, card = refereed(tmp_path)
    said(folder, card, ENDORSED)

    with pytest.raises(StaleRecord):
        move_past_stage_4(folder, {})


# ── 17: stage 4c, the receipt that binds the record (ticket 243: no page of nemo's own) ─────


def drawn(tmp_path):
    """A room walked to stage 4 and accepted: the record landed and its receipt bound."""
    folder, card = refereed(tmp_path)
    return folder, said(folder, card, ENDORSED)


def receipt_binds(folder):
    """Whether the run's receipt binds the record now in this room."""
    run = read_record(folder, run_file("Slaughter"))
    return (run[RECEIPT] or {}).get("record_sha") == fingerprint(read_record(folder, RECORD))


def test_the_press_speaks_only_once_the_receipt_binds(tmp_path):
    folder, card = refereed(tmp_path)

    answered = said(folder, card, ENDORSED)

    saved = read_record(folder, run_file("Slaughter"))
    assert answered.body == " ".join([ACCEPTED, checked_note(saved), PICTURE_DRAWN])
    assert SAVED_NOT_FINISHED not in answered.body
    assert receipt_binds(folder), "the walk spoke before the receipt bound"


def test_a_record_write_draws_no_page_of_nemos_own(tmp_path):
    """Ticket 243 (ADR-0040): the grouped graph the skin draws is the only one; nemo's own page,
    which nobody was ever shown, is not written, and the receipt binds the record alone."""
    folder, _answered = drawn(tmp_path)
    record = read_record(folder, RECORD)

    assert not (folder / "public" / "graph").exists(), "nemo drew a page of its own"
    assert read_record(folder, run_file("Slaughter"))[RECEIPT] == {
        "record_sha": fingerprint(record), "record_version": record["record_schema_version"]}
    assert move_past_stage_4(folder, read_record(folder, run_file("Slaughter"))) == record


def test_a_stop_before_the_picture_leaves_the_walk_saved_and_not_yet_finished(tmp_path):
    folder, card = refereed(tmp_path)

    answered = saved_only(folder, card, ENDORSED)

    run = read_record(folder, run_file("Slaughter"))
    assert run["status"] == RECORD_SAVED and run[RECEIPT] is None
    assert where_it_stands(run) == SAVED_NOT_FINISHED and SAVED_NOT_FINISHED in answered.body
    assert not (folder / PUBLIC).exists(), "the picture was drawn by a movement that did not run"
    with pytest.raises(NotDrawnYet) as refused:
        move_past_stage_4(folder, run)
    assert str(refused.value) == SAVED_NOT_FINISHED


def test_the_card_a_saved_record_hands_back_carries_the_run_it_just_wrote(tmp_path):
    """The first movement's card is the second movement's input, so it carries the run state.

    `draw_graph` hands this card straight back where there is nothing of this run's to draw — an
    overtaken press, or a record another walk replaced — and a page then reads `saved` and
    `revision` off it. A card that said "saved" while carrying no run at all would put the walk's
    next press on revision 0, which is the compare-and-set the whole stage rests on.
    """
    folder, card = refereed(tmp_path)

    answered = saved_only(folder, card, ENDORSED)

    run = read_record(folder, run_file("Slaughter"))
    assert answered.saved == run
    assert answered.revision == run["revision"] and answered.revision > 0


def test_a_stop_between_the_four_documents_is_paid_for_by_the_resume(tmp_path, monkeypatch):
    """ADR-0010 again, one level down: the stop inside the first movement's four documents.

    The four land one after another, so a box that stops between them leaves the room holding some
    of them and none of the rest — or, over a second walk, the one before it — while the run goes
    on to `AWAITING_HUMAN` and stage 5 hands over. That is v1's G3 family: a delivered document
    that disagrees with the record it claims to be rendered from, and nobody reading it can see it.
    The documents are a function of the record bytes and of nothing else (ADR-0004), so the second
    movement writes them again and they land identically (ADR-0010).
    """
    folder, card = refereed(tmp_path)
    landing, written = views.write_document, []

    def stopping(room_folder, path, text):
        if written:
            raise KeyboardInterrupt("the box stopped between the documents")
        written.append(path)
        return landing(room_folder, path, text)

    monkeypatch.setattr(views, "write_document", stopping)
    with pytest.raises(KeyboardInterrupt):
        said(folder, card, ENDORSED)
    monkeypatch.setattr(views, "write_document", landing)
    record = read_record(folder, RECORD)
    at = folder / views.folder(record)
    assert sorted(path.name for path in at.iterdir()
                  if path.name != walk.RECORD_NAME) == sorted(views.FOUR[:1])

    resume(folder, "Slaughter")

    assert read_record(folder, run_file("Slaughter"))[STATUS] == AWAITING_HUMAN
    for name, text in views.render(record).items():
        assert (at / name).read_text(encoding="utf-8") == text


def test_the_movement_run_again_after_a_stop_binds_and_waits_for_the_manager(tmp_path):
    """ADR-0010: an interrupted movement is re-executed, and nothing is asked of the manager."""
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)

    resume(folder, "Slaughter")

    run = read_record(folder, run_file("Slaughter"))
    assert run["status"] == AWAITING_HUMAN and where_it_stands(run) == ""
    assert move_past_stage_4(folder, run) == read_record(folder, RECORD)
    assert receipt_binds(folder)


def test_the_card_a_resume_hands_back_says_the_picture_is_drawn_and_asks_nothing(tmp_path):
    """A record already accepted must not come back still asking to be accepted.

    `resume` runs the second movement over a walk whose first one landed, so what the manager
    reads is the confirmation the accepting answer would have given him — the picture drawn, and
    nothing on the card to answer.
    """
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)

    resumed = resume(folder, "Slaughter")

    assert resumed.body.endswith(PICTURE_DRAWN)
    assert (resumed.buttons, resumed.decision, resumed.rule) == ((), "", "")


def test_running_the_movement_again_rewrites_the_same_bytes(tmp_path):
    folder, _answered = drawn(tmp_path)
    before = _written(folder)

    resume(folder, "Slaughter")

    assert _written(folder) == before


def test_a_receipt_does_not_open_stage_five_over_a_record_it_was_never_taken_over(tmp_path):
    folder, _answered = drawn(tmp_path)
    run = read_record(folder, run_file("Slaughter"))
    replaced = read_record(folder, RECORD)
    write_record(folder, RECORD, {**_without_revision(replaced), "dept": "Cutting"},
                 replaced["revision"])

    with pytest.raises(NotDrawnYet):
        move_past_stage_4(folder, run)

    resume(folder, "Slaughter")
    run = read_record(folder, run_file("Slaughter"))
    assert move_past_stage_4(folder, run)["dept"] == "Cutting"
    assert receipt_binds(folder)


def test_an_overtaken_press_draws_no_picture(tmp_path, monkeypatch):
    folder, card = refereed(tmp_path)

    overtaken = overtaken_at_the_record(folder, card, monkeypatch)

    assert overtaken.body.startswith(OVERTAKEN)
    assert not (folder / PUBLIC).exists()


def test_a_run_that_moved_after_the_record_landed_is_told_it_was_overtaken(tmp_path, monkeypatch):
    """The stale check reads the run before the record is written, and the run's own
    compare-and-set in `_save` still stands behind it: a second tab that moves the run between
    the record landing and the run being saved is refused there, and no picture is drawn."""
    folder, card = refereed(tmp_path)
    landing, moved = walk._land, {}

    def moving(room_folder, pressed):
        landed = landing(room_folder, pressed)
        moved_on(room_folder)
        moved.update(read_record(room_folder, run_file("Slaughter")))
        return landed

    monkeypatch.setattr(walk, "_land", moving)
    overtaken = said(folder, card, ENDORSED)

    assert overtaken.body.startswith(OVERTAKEN), "the run's compare-and-set was passed over"
    assert read_record(folder, run_file("Slaughter")) == moved
    assert not (folder / PUBLIC).exists()


def test_no_picture_is_drawn_from_a_record_this_run_did_not_produce(tmp_path):
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)
    record = read_record(folder, RECORD)
    write_record(folder, RECORD, {**_without_revision(record), "run_id": "another walk's"},
                 record["revision"])

    resume(folder, "Slaughter")

    assert not (folder / PUBLIC).exists()


def test_a_run_overtaken_while_the_picture_was_drawn_binds_no_receipt(tmp_path, monkeypatch):
    """The movement reads the run, then writes the documents, then the receipt onto it, so another
    press can land in between. The losing writer drops its receipt: a receipt over a run somebody
    else moved would bind nothing."""
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)
    drawing, stale = walk._receipt_for, record_card(folder, "Slaughter")

    def overtaking(record):
        run = read_record(folder, run_file("Slaughter"))
        write_record(folder, run_file("Slaughter"), _without_revision(run), run["revision"])
        return drawing(record)

    monkeypatch.setattr(walk, "_receipt_for", overtaking)
    unchanged = resume(folder, "Slaughter")

    assert unchanged == stale
    assert read_record(folder, run_file("Slaughter"))[RECEIPT] is None


#: The room folder a picture would live under. nemo writes nothing into it (ADR-0040); the
#: grouped graph the skin draws is the only picture.
PUBLIC = "public"


def _written(folder):
    """The record's documents and the run's receipt: everything the second movement writes."""
    at = folder / views.folder(read_record(folder, RECORD))
    return ({path: path.read_bytes() for path in at.rglob("*") if path.is_file()},
            read_record(folder, run_file("Slaughter"))[RECEIPT])


def _without_revision(record):
    """A record as a writer hands it over: the store owns the revision and adds it back."""
    return {key: value for key, value in record.items() if key != "revision"}


# ── 17's pure functions, as properties ───────────────────────────────────────


@given(st.text(max_size=20))
def test_the_walk_says_saved_and_not_yet_finished_for_exactly_one_status(status):
    """Saved is not finished, and no other state may borrow the sentence that says so."""
    said = where_it_stands({"status": status})

    assert (said == SAVED_NOT_FINISHED) == (status == RECORD_SAVED)
    assert said == "" or status == RECORD_SAVED


@given(st.lists(st.sampled_from([STAGE, STAGE_2, STAGE_3, STAGE_4]), max_size=4),
       st.sampled_from([None, {}, {"record_sha": "abc"}]))
def test_no_record_is_handed_over_until_the_picture_it_binds_has_been_drawn(stages, receipt):
    """Stage 4 is two movements, and the stop between them is ADR-0010's ordinary one.

    The first writes the decision and nulls the receipt; the second draws the picture and binds it.
    A walk stopped in between has answered stage 4 and has nothing for stage 5 to hand over, so the
    decision alone must not open it — reading it alone is how a manager who is being told *saved,
    and not yet finished* gets `NotDrawnYet` in the same breath. Over every order the stages can
    have been answered in, and over the nulled receipt as well as the absent one, because a null
    is what the first movement actually leaves behind.
    """
    saved = {DECISIONS: [{AT_STAGE: stage} for stage in stages], RECEIPT: receipt}

    assert _record_accepted(saved) == (STAGE_4 in stages and bool(receipt))
    assert not _record_accepted({RECEIPT: receipt}), "a picture with no stage 4 answered it"
    assert not _record_accepted(None), "a walk with no run file at all handed something over"


# ── 18: stage 5, consolidate, hand over and sign ─────────────────────────────
#
# The feature steps walk a manager to the signature and watch what lands. These take the two
# presses apart: the one that is overtaken while somebody reads, and the one where the record
# has nobody to match a signer against.


def handed_over(tmp_path):
    """A room walked to the last card there is: the record drawn, bound, and handed over."""
    folder, _answered = drawn(tmp_path)
    return folder, walk.handover_card(folder, "Slaughter")


def test_an_acceptance_that_was_overtaken_does_not_land_on_top_of_the_newer_run(tmp_path):
    """Two screens on one BIA: the second accepts, the first's press finds a newer run and is
    told so in a colleague's sentence rather than writing the handover over it twice."""
    folder, stale = handed_over(tmp_path)
    walk.accept_handover(folder, walk.handover_card(folder, "Slaughter"), ENDORSED)
    before = read_record(folder, run_file("Slaughter"))

    overtaken = walk.accept_handover(folder, stale, ENDORSED)

    assert overtaken.body.startswith(OVERTAKEN.split("{")[0])
    assert read_record(folder, run_file("Slaughter")) == before


def test_an_acceptance_that_was_overtaken_writes_not_one_byte_of_a_document(tmp_path):
    """Ticket 208, finding B6: two of his tabs on one room, and the stale one loses for free.

    The documents used to go down before the run's revision was asked for, so the press that had
    already lost replaced the handover and the requirements first and was told second — leaving
    the manager reading a document rendered from a room state nobody is in. `moved_on` is the
    other tab: the run moves while this card is being read.
    """
    folder, stale = handed_over(tmp_path)
    moved_on(folder)
    out = output_folder(folder)
    before = {path: path.read_bytes() for path in out.rglob("*") if path.is_file()}

    overtaken = walk.accept_handover(folder, stale, ENDORSED)

    assert overtaken.body.startswith(OVERTAKEN.split("{")[0])
    assert {path: path.read_bytes() for path in out.rglob("*") if path.is_file()} == before
    assert not (out / handover.HANDOVER).is_file(), "the press that lost wrote the handover"


def test_a_signature_that_was_overtaken_writes_no_certificate(tmp_path):
    folder, card = handed_over(tmp_path)
    walk.accept_handover(folder, card, ENDORSED)
    stale = walk.signature_card(folder, "Slaughter")
    walk.accept_handover(folder, walk.handover_card(folder, "Slaughter"), ENDORSED)

    overtaken = walk.sign(folder, stale, "Torsten Ahlgrim", "Head of Slaughter")

    assert overtaken.body.startswith(OVERTAKEN.split("{")[0])
    assert handover.SIGNATURE not in read_record(folder, run_file("Slaughter"))
    assert not (folder / views.folder(read_record(folder, RECORD))
                / handover.CERTIFICATE).is_file()


# ── ticket 180: a stale answer at the handover writes no document ────────────
#
# Two answers on one stage-5 card revision. Until 180 the loser wrote both handover documents and
# only then met the run's compare-and-set in `_save`, which told it it was overtaken.


def on_disk(folder):
    """Every file in the room with its bytes and its inode: every write lands by a rename
    (`room_store._written`), so a document written again with the very same bytes is still seen."""
    return {path: (path.read_bytes(), path.stat().st_ino)
            for path in folder.rglob("*") if path.is_file()}


def documents_of(folder):
    return {path.name: path.read_bytes() for path in output_folder(folder).iterdir()
            if path.name in (handover.DRAFT, handover.HANDOVER)}


@pytest.mark.parametrize("loser", GRADIENT)
def test_the_losing_acceptance_writes_no_document_and_is_told_it_lost(tmp_path, loser):
    """Red on t172 at 8933fc1: the loser wrote both documents before `_save` refused it."""
    folder, card = handed_over(tmp_path / "race")
    walk.accept_handover(folder, card, ENDORSED)
    before = on_disk(folder)

    lost = walk.accept_handover(folder, card, loser)

    assert lost.body.startswith(OVERTAKEN.split("{")[0]), "the stale answer was not refused"
    assert (lost.stage, lost.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert on_disk(folder) == before, "the losing answer wrote the handover documents"
    solo, alone = handed_over(tmp_path / "solo")
    walk.accept_handover(solo, alone, ENDORSED)
    assert documents_of(folder) == documents_of(solo) and len(documents_of(solo)) == 2


@pytest.mark.parametrize("words", ["yes, that's fine", "Yes, but the cooling line is still open"])
def test_a_stale_answer_typed_at_the_handover_writes_no_document(tmp_path, words):
    """The same race through the door: the run moved while the handover was read, and the typed
    answer on the old revision is refused before a document is written, not after."""
    folder, card = handed_over(tmp_path)
    moved_on(folder)
    before = on_disk(folder)

    lost = said(folder, card, words)

    assert lost.body.startswith(OVERTAKEN.split("{")[0]), "the stale answer was not refused"
    assert on_disk(folder) == before, "the stale answer wrote the handover documents"
    assert documents_of(folder) == {}


def test_a_run_that_moved_after_the_stale_check_is_told_it_was_overtaken(tmp_path, monkeypatch):
    """The stale check passed, and the run moved in the breath after it: the run's own
    compare-and-set in `_save` still refuses the acceptance, and the other tab's run stands.

    180 showed this with the run moving while the documents went down. 208 put the documents after
    the run, so the window between the check and the compare is the whole of what is left — and
    losing in it now costs not one document either.
    """
    folder, card = handed_over(tmp_path)
    checking, moved = walk._stale, {}

    def checking_then_moving(room_folder, read):
        answer = checking(room_folder, read)
        moved_on(room_folder)
        moved.update(read_record(room_folder, run_file("Slaughter")))
        return answer

    monkeypatch.setattr(walk, "_stale", checking_then_moving)
    lost = walk.accept_handover(folder, card, ENDORSED)

    assert lost.body.startswith(OVERTAKEN.split("{")[0]), "the run's compare-and-set was skipped"
    assert (lost.stage, lost.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert read_record(folder, run_file("Slaughter")) == moved
    assert documents_of(folder) == {}, "the press that lost the compare wrote a document"


def test_a_record_with_nobody_owning_an_activity_says_so_rather_than_naming_a_signer(tmp_path):
    """An activity nobody stated the figures of has no owner, so no sign-off closes it — and the
    card says who it would have to be rather than leaving the sentence half-written."""
    folder, card = handed_over(tmp_path)
    unowned = {**card.proposal[BIA], "activities": [
        {**activity, "owner": ""} for activity in card.proposal[BIA]["activities"]]}

    said = handover.documents(unowned, card.saved)[handover.HANDOVER]

    # the activity is named in its heading and "this activity" after it (t64, nemo's own since t133)
    assert handover.NO_OWNER.format(activity=handover.THIS_ACTIVITY) in said
    assert handover.owners(unowned) == ()


def accepted_handover(tmp_path):
    """A room whose handover the manager has accepted: two documents on file, nobody signed yet."""
    folder, card = handed_over(tmp_path)
    return folder, walk.accept_handover(folder, card, ENDORSED)


def run_of(folder):
    return read_record(folder, run_file("Slaughter"))


def output_folder(folder):
    """Where this room's BIA documents are written, read off the record they are rendered from."""
    return folder / views.folder(read_record(folder, RECORD))


def documents_on_disk(folder):
    """The two documents stage 5 writes, as bytes, read off the record they are rendered from."""
    out = output_folder(folder)
    return {name: (out / name).read_bytes()
            for name in (handover.DRAFT, handover.HANDOVER) if (out / name).is_file()}


#: The two documents an uninterrupted acceptance writes, as `sha256` over their bytes, taken from
#: main at 5e3c3fe — before ticket 208 moved the run's compare-and-set in front of the writes and
#: before 207 taught the resume to do them again. Pinned rather than rendered again here, because
#: rendering them again is the thing under test: what the manager reads on the path where nothing
#: stopped has to be what he read before either change. A wording change in `nemo.handover` moves
#: these on purpose, and then the new digests are read off this test's own failure and pinned.
#: Re-derived in bundle C' for 133's wording ("this activity" after the heading, t64); 207/208 add
#: no byte to it.
ACCEPTED_DOCUMENTS = {
    handover.DRAFT: "ba85f654f53426058416b482fa6664cc4ba353e1d38019a2701489f040e935fd",
    handover.HANDOVER: "e695f70e6ba0296cacd6838879503ece7b6ac2737e74c1e342a9c8b1fb67caee",
}


def test_a_run_signed_after_that_stop_still_gets_the_documents_on_its_resume(tmp_path):
    """The window does not close at the signature, so the resume does not stop at ``REVIEWED``.

    Nothing in stage 5 asks whether the two documents landed — the signature card is read off the
    record and the run — so the manager can sign over a torn handover and close the run. Then
    ``CLOSED`` is the status the resume finds, and the movement it stopped inside is still owed.
    """
    uninterrupted, _accepted = accepted_handover(tmp_path / "uninterrupted")
    expected = documents_on_disk(uninterrupted)
    folder, card = handed_over(tmp_path / "stopped")

    def killed(*_args, **_kwargs):
        raise SystemExit("killed between the run's write and the first document's")

    with pytest.MonkeyPatch.context() as planted:
        planted.setattr(walk, "write_document", killed)
        with pytest.raises(SystemExit):
            walk.accept_handover(folder, card, ENDORSED)
    walk.sign(folder, walk.signature_card(folder, "Slaughter"),
              "Torsten Ahlgrim", "Head of Slaughter")
    assert run_of(folder)[STATUS] == CLOSED, "the signature did not close the run"
    assert documents_on_disk(folder) == {}, "a document landed after all; the plant missed"

    resume(folder, "Slaughter")

    assert documents_on_disk(folder) == expected


def another_walks_record(folder):
    """The record another walk in this room saved while this acceptance was stopped."""
    write_record(folder, RECORD, ANOTHER_WALKS, read_record(folder, RECORD)["revision"])


def the_record_rewritten(folder):
    """This walk's own record moved on, so the receipt on the run no longer binds what is there."""
    replaced = read_record(folder, RECORD)
    write_record(folder, RECORD, {**_without_revision(replaced), "dept": "Cutting"},
                 replaced["revision"])


def stopped_before_the_documents(folder, card, answer):
    """That acceptance killed the way a process is killed: the run moved, no document landed."""
    def killed(*_args, **_kwargs):
        raise SystemExit("killed between the run's write and the first document's")

    with pytest.MonkeyPatch.context() as planted:
        planted.setattr(walk, "write_document", killed)
        with pytest.raises(SystemExit):
            walk.accept_handover(folder, card, answer)
    assert documents_on_disk(folder) == {}, "a document landed after all; the plant missed"


def handed_over_with_a_reservation(tmp_path, named="the night shift figures are a guess"):
    """A room walked to the handover whose stage 3 was answered *endorsed with reservations*.

    The reservation lives on the run and both documents quote it in the words it was named in, so
    what they say here is a function of the run and not of the record alone.
    """
    folder, stage_2 = bound(tmp_path, SCORED)
    reserved = said(folder, onward(folder, stage_2)[0], RESERVED)
    stage_4 = onward(folder, said(folder, reserved, named))[0]
    said(folder, stage_4, ENDORSED)
    return folder, walk.handover_card(folder, "Slaughter")


def test_the_resume_writes_the_reservation_the_run_carries_and_not_the_record_alone(tmp_path):
    """The documents are a function of the record **and** the run, and the movement again is both.

    He answered stage 3 *endorsed with reservations* and named what he was reserving; both documents
    say it back in his words (`handover`). A resume that rendered the record alone would hand him a
    handover with his own reservation gone out of it, which is a document disagreeing with the run
    it claims to come from — the same family as one disagreeing with the record.
    """
    uninterrupted, card = handed_over_with_a_reservation(tmp_path / "uninterrupted")
    walk.accept_handover(uninterrupted, card, ENDORSED)
    expected = documents_on_disk(uninterrupted)
    reserved = handover.RESERVATION.format(
        stage=STAGE_3, gradient=RESERVED, naming="the night shift figures are a guess")
    assert all(reserved in document.decode("utf-8") for document in expected.values()), (
        "this room was meant to carry a named reservation into both documents")
    folder, card = handed_over_with_a_reservation(tmp_path / "stopped")
    stopped_before_the_documents(folder, card, ENDORSED)

    resume(folder, "Slaughter")

    assert documents_on_disk(folder) == expected


def test_the_resume_does_not_quote_the_acceptance_that_was_still_landing(tmp_path):
    """What the press would have written, and not one line more (`_on_the_way_here`).

    He accepted the handover *with reservations*, and the two documents he read were rendered before
    that answer was a decision on the run — so no press has ever written a document that quotes it.
    The movement again renders from the run that now carries it, so it has to leave that one answer
    out or hand him back a document nothing else in the product would ever produce.
    """
    uninterrupted, card = handed_over(tmp_path / "uninterrupted")
    walk.accept_handover(uninterrupted, card, RESERVED)
    expected = documents_on_disk(uninterrupted)
    landing = handover.NOT_NAMED.format(stage=walk.STAGE_5, gradient=RESERVED)
    assert all(landing not in document.decode("utf-8") for document in expected.values()), (
        "the press quoted the answer it was still landing")
    folder, card = handed_over(tmp_path / "stopped")
    stopped_before_the_documents(folder, card, RESERVED)

    resume(folder, "Slaughter")

    assert documents_on_disk(folder) == expected


@pytest.mark.parametrize("moves_the_record", [another_walks_record, the_record_rewritten])
def test_a_resume_writes_no_document_over_a_room_that_moved_under_the_acceptance(
        tmp_path, moves_the_record):
    """The other half of ticket 208's B6: losing at the compare has to cost the manager nothing.

    Writing the documents again is right only while the record the run's receipt binds is still the
    record in the room. Where it is not — another walk saved over it, or this walk's own record
    moved on — the documents on disk are the winning walk's, and a resume that rendered these
    bytes over them would put back exactly what 208 stopped the press from doing. So the gate stage
    5 already has answers here too, and a refusal writes nothing at all rather than raising at a
    manager who only came back to a room.
    """
    folder, _accepted = accepted_handover(tmp_path)
    moves_the_record(folder)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    resume(folder, "Slaughter")

    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before


def test_an_uninterrupted_acceptance_writes_what_main_wrote_and_a_resume_moves_no_byte(tmp_path):
    """The ordinary path, on the tree that carries 208's reorder and 207's heal together.

    Neither change may be visible to a manager who was never interrupted: the press writes the same
    two documents main wrote for this room, byte for byte, and the resume that now re-executes
    stage 5's movement writes them again over themselves and moves nothing.
    """
    folder, _accepted = accepted_handover(tmp_path)
    written = documents_on_disk(folder)

    assert {name: hashlib.sha256(data).hexdigest() for name, data in written.items()} == (
        ACCEPTED_DOCUMENTS), "the ordinary path no longer writes the documents main wrote"

    resume(folder, "Slaughter")

    assert documents_on_disk(folder) == written, "the resume moved a byte on the ordinary path"


def test_a_stop_before_the_documents_leaves_a_resume_that_writes_them_both(tmp_path):
    """Ticket 208's B6 reorder against ADR-0010's "the artefacts are the truth" (17_nemo_check).

    The reorder moved the run's compare-and-set in front of the document writes, which opens a
    window the old order did not have: the run at ``REVIEWED`` with neither document on disk. ADR
    0010 permits that only because both documents are a pure function of the record and the run,
    so the movement is re-executable — and re-executable means a resume actually re-executes it.

    The plant is the kill: the first ``write_document`` raises the way a process killed between
    the two movements leaves them, so the run has moved and no document has landed. Then the
    resume, and the two documents have to be there and be the bytes an uninterrupted acceptance
    writes — the same room, walked the same way, with nothing stopped.
    """
    uninterrupted, _accepted = accepted_handover(tmp_path / "uninterrupted")
    expected = documents_on_disk(uninterrupted)
    assert set(expected) == {handover.DRAFT, handover.HANDOVER}, "the baseline wrote no documents"
    folder, card = handed_over(tmp_path / "stopped")

    def killed(*_args, **_kwargs):
        raise SystemExit("killed between the run's write and the first document's")

    with pytest.MonkeyPatch.context() as planted:
        planted.setattr(walk, "write_document", killed)
        with pytest.raises(SystemExit):
            walk.accept_handover(folder, card, ENDORSED)
    assert run_of(folder)[STATUS] == REVIEWED, "the run did not move before the documents"
    assert documents_on_disk(folder) == {}, "a document landed after all; the plant missed"

    resume(folder, "Slaughter")

    assert documents_on_disk(folder) == expected


def test_a_stage_four_card_answered_on_disk_is_followed_by_the_handover(tmp_path):
    """Stage 5 follows the answer on file, exactly as every other stage does (ADR-0010)."""
    folder, answered = drawn(tmp_path)

    following, = onward(folder, answered)

    assert (following.stage, following.heading) == (walk.STAGE_5, walk.HEADING_5)


def test_a_stage_four_card_nobody_has_accepted_is_followed_by_nothing(tmp_path):
    folder, card = refereed(tmp_path)
    assert onward(folder, card) == ()


def test_the_handover_card_is_the_fifth_of_five_and_asks_the_one_gradient_question(tmp_path):
    folder, card = handed_over(tmp_path)

    assert (card.stage, card.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert card.activities == ("Slaughter",) and card.sources == (RECORD,)
    assert card.buttons == GRADIENT and card.gradient == GRADIENT
    assert (card.decision, card.rule) == (walk.DECISION_5, RULE_4)
    assert card.method == COPIED_METHOD
    assert card.saved == run_of(folder) and card.revision == run_of(folder)["revision"]


def test_the_handover_card_shows_both_documents_whole_under_what_they_are_for(tmp_path):
    folder, card = handed_over(tmp_path)

    assert card.body == "\n\n".join([
        walk.HANDING_OVER.format(process="Slaughter"),
        *handover.documents(card.proposal[BIA], run_of(folder)).values()])


def test_the_handover_card_writes_not_one_byte(tmp_path):
    """It is a card, and a card is read. The documents land at the press and never before it."""
    folder, _answered = drawn(tmp_path)
    before = run_of(folder)

    walk.handover_card(folder, "Slaughter")

    assert run_of(folder) == before
    assert not (output_folder(folder) / handover.DRAFT).exists()


def test_accepting_writes_both_documents_from_the_bytes_the_manager_read(tmp_path):
    folder, card = handed_over(tmp_path)

    walk.accept_handover(folder, card, ENDORSED)

    for name, text in card.proposal[walk.DOCUMENTS].items():
        assert (output_folder(folder) / name).read_text(encoding="utf-8") == text
    assert {handover.DRAFT, handover.HANDOVER} <= {
        path.name for path in output_folder(folder).iterdir()}


def test_accepting_is_not_signing_so_the_run_is_reviewed_and_no_certificate_exists(tmp_path):
    folder, _answered = accepted_handover(tmp_path)
    saved = run_of(folder)

    assert saved["status"] == walk.REVIEWED
    assert without_telemetry(saved["decisions"][-1]) == {
        "stage": walk.STAGE_5, **_reserving(ENDORSED)}
    assert handover.SIGNATURE not in saved
    assert not (output_folder(folder) / handover.CERTIFICATE).exists()


def test_the_accepted_card_is_the_stage_five_card_carrying_what_it_saved(tmp_path):
    folder, answered = accepted_handover(tmp_path)
    saved = run_of(folder)

    assert (answered.stage, answered.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert answered.body == walk.ACCEPTED_5
    assert answered.saved == saved and answered.revision == saved["revision"]


def test_a_handover_answered_any_other_way_reserves_something_and_is_asked_to_name_it(tmp_path):
    folder, card = handed_over(tmp_path)

    answered = walk.accept_handover(folder, card, "needs discussion")

    assert answered.body == NAMING
    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": walk.STAGE_5, **_reserving("needs discussion")}


def test_the_handover_is_pressed_through_the_door_in_the_words_the_manager_typed(tmp_path):
    """The door's fifth row, reached the way a manager reaches it: by typing into the box.

    Every test above presses stage 5 by calling `accept_handover` itself, so the row that routes a
    stage 5 card to it was reached only from `tests/` and `features/` — and a door that handed the
    stage its own words as anything else would still pass all of them. Both readings are held here
    because a handover recorded without the manager's words is a handover recorded as a
    reservation nobody made, which is what `docs/voice.md` §4.3 forbids.
    """
    folder, card = handed_over(tmp_path)

    answered = said(folder, card, ENDORSED)

    assert answered.body == walk.ACCEPTED_5
    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": walk.STAGE_5, **_reserving(ENDORSED)}
    assert run_of(folder)["status"] == walk.REVIEWED


def test_a_caveat_typed_at_the_handover_is_read_for_one_through_the_door_too(tmp_path):
    """The other half of the same row: the words are read, not merely passed on.

    Said as the gradient the words earn rather than as a label, so a door that handed stage 5 a
    fixed answer — or nothing at all — is red here whichever fixed answer it picked.
    """
    folder, card = handed_over(tmp_path)

    answered = said(folder, card, "Yes, but the cooling line is still an open question")

    assert answered.body == NAMING
    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": walk.STAGE_5, **_reserving(RESERVED)}


def test_a_reservation_made_on_the_handover_can_be_named_in_nemo_itself(tmp_path):
    """The naming of a stage 5 reservation, taken by nemo alone with no skin in the process.

    `_RESERVED_AT` stopped at stage 4, so the one door raised `KeyError: 5` at a manager who had
    just been asked to name what he reserved on the handover — the last card there is. The skin
    repaired it at runtime, so the defect only ever showed where the engine stands on its own,
    which is what the MCP door will be (ticket 206).
    """
    folder, card = handed_over(tmp_path)
    answered = said(folder, card, "needs discussion")
    assert answered.body == NAMING, "the handover has to be asking for a naming first"

    taken = said(folder, answered, NAMED)

    assert (taken.stage, taken.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert taken.name == "handover", "the card that took it is the one it was named on"
    assert taken.body == TAKEN
    assert namings(run_of(folder)) == ((walk.STAGE_5, NAMED),)
    assert taken.saved == run_of(folder)


def test_the_signature_card_asks_for_a_name_a_role_and_the_ids_and_offers_no_button(tmp_path):
    folder, _answered = accepted_handover(tmp_path)

    card = walk.signature_card(folder, "Slaughter")

    assert (card.stage, card.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert card.activities == ("Slaughter",) and card.sources == (RECORD,)
    assert card.buttons == () and card.gradient == ()
    assert (card.decision, card.rule) == (walk.DECISION_SIGN, walk.RULE_SIGN)
    assert card.method == COPIED_METHOD
    assert card.saved == run_of(folder) and card.revision == run_of(folder)["revision"]


def test_the_signature_card_names_whose_sign_off_closes_this_and_every_item_by_its_id(tmp_path):
    folder, _answered = accepted_handover(tmp_path)

    card = walk.signature_card(folder, "Slaughter")

    open_items = handover.items(card.proposal[BIA], run_of(folder))
    assert open_items, "this room was meant to leave something open to accept by id"
    assert card.body == "\n\n".join([
        walk.SIGNING.format(owner="Torsten Ahlgrim"),
        walk.SIGNING_CHOICE.format(owner="Torsten Ahlgrim"),
        *(handover.ITEM.format(id=at, text=text) for at, text in open_items)])
    assert card.proposal[walk.ITEMS] == dict(open_items)


def test_the_signature_card_offers_the_two_ways_to_sign_and_never_a_third(tmp_path):
    """Ticket 134: who he signs as is his explicit choice, and nemo draws it from the record.

    The two taps and the sentence beside them say the same thing, which is what makes the choice
    checkable: the label is the record's own name and the second half of each pair is the argument
    `sign` takes, so nothing anybody types can reach the capacity.
    """
    folder, _answered = accepted_handover(tmp_path)

    card = walk.signature_card(folder, "Slaughter")

    assert walk.signing_choices(card.proposal[BIA]) == (
        (walk.SIGN_AS_THE_OWNER, walk.AS_THE_OWNER),
        (walk.SIGN_ON_BEHALF.format(owner="Torsten Ahlgrim"), "Torsten Ahlgrim"))
    assert walk.SIGNING_CHOICE.format(owner="Torsten Ahlgrim") in card.body
    assert walk.sign(folder, card, "Petra Nolte", "Deputy",
                     on_behalf_of=walk.AS_THE_OWNER).saved[handover.SIGNATURE][
                         "capacity"] == handover.SPONSOR, \
        "the claim is his; the verdict on it stays the record's"


def test_a_record_that_names_no_owner_offers_no_way_to_sign_as_one_and_no_third_tap(tmp_path):
    """12_nemo_check's amendment to 134: today's behaviour, pinned, and nothing invented for it.

    "on behalf of" has no name to carry here and "as the owner" would claim an ownership the
    record does not state, so there is no choice to offer — and with none offered the card says
    nothing about one either, because the same call decides both.
    """
    folder, drawn = signing(tmp_path)
    ownerless = {**drawn.proposal[BIA], "activities": [
        {**a, "owner": ""} for a in drawn.proposal[BIA]["activities"]]}
    card = replace(drawn, proposal={**drawn.proposal, BIA: ownerless})

    answered = walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")

    assert walk.signing_choices(ownerless) == (), "a third way to sign was invented"
    assert run_of(folder)["status"] == walk.REVIEWED
    assert run_of(folder)[handover.SIGNATURE]["capacity"] == handover.SPONSOR
    assert answered.body == walk.NOT_THE_OWNER.format(
        capacity=handover.SPONSOR, owner=walk.NOBODY)
    assert not (output_folder(folder) / handover.CERTIFICATE).exists()


def signing(tmp_path):
    """The signature card of a room whose handover is accepted, and the room it stands in."""
    folder, _answered = accepted_handover(tmp_path)
    return folder, walk.signature_card(folder, "Slaughter")


def test_the_owners_signature_closes_the_run_and_writes_the_certificate(tmp_path):
    """The positive transition: a signature with authority actually finishes the walk."""
    folder, card = signing(tmp_path)

    answered = walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")

    saved = run_of(folder)
    assert saved["status"] == walk.CLOSED
    assert saved[handover.SIGNATURE] == {
        "name": "Torsten Ahlgrim", "role": "Head of Slaughter",
        "accepted": list(card.proposal[walk.ITEMS]),
        "capacity": handover.OWNER_OF_THE_ACTIVITY}
    assert saved["decisions"] == card.saved["decisions"], "signing invented a sixth stage"
    assert (answered.stage, answered.heading) == (walk.STAGE_5, walk.HEADING_5)
    assert answered.body == walk.SIGNED_OFF
    assert answered.saved == saved and answered.revision == saved["revision"]
    assert (output_folder(folder) / handover.CERTIFICATE).read_text(
        encoding="utf-8") == handover.certificate(card.proposal[BIA], saved)


def test_the_owners_signature_dates_the_run_with_the_day_it_closed(tmp_path, monkeypatch):
    """Ticket 258: the graph's "BIA done" carries the signing date, so the run keeps it — the
    date part of the walk's one clock, UTC, and never a file's modification time."""
    folder, card = signing(tmp_path)
    monkeypatch.setattr(walk, "_now", lambda: "2026-09-20T23:59:59+00:00")

    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")

    assert run_of(folder)["signed_on"] == "2026-09-20"  # the run file's key, as shared


def test_a_certificate_the_close_could_not_write_is_written_by_the_next_resume(tmp_path):
    """A stop between the closure and the certificate, and what repairs it.

    The run closes first and the certificate is written after, so an I/O error, a stop or the
    store's shrink guard in between leaves a CLOSED run with no certificate — and nothing signs it
    again, because the walk is past the signature and the skin says so. The certificate is a
    function of the record and the saved signature, so the resume that already costs the second
    movement again writes the same bytes rather than repairing anything (ADR-0004).
    """
    folder, card = signing(tmp_path)
    with pytest.MonkeyPatch.context() as stopped:
        stopped.setattr(walk, "write_document", _write_that_fails)
        with pytest.raises(OSError):
            walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    saved = run_of(folder)
    assert saved["status"] == walk.CLOSED, "the plant did not leave the run closed"
    assert not (output_folder(folder) / handover.CERTIFICATE).exists(), "nothing was lost to plant"
    again = walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    assert again.body.startswith(OVERTAKEN.split("{")[0]), "signing again is not the way back"

    resume(folder, "Slaughter")

    assert (output_folder(folder) / handover.CERTIFICATE).read_text(
        encoding="utf-8") == handover.certificate(card.proposal[BIA], saved)


#: What a closed run leaves under its folder: the two handover documents and the certificate.
SIGNED_DOCUMENTS = (handover.DRAFT, handover.HANDOVER, handover.CERTIFICATE)


def signed_by_an_older_renderer(tmp_path):
    """A closed run whose three documents on disk say what an older renderer wrote, and what today's
    renderer writes for each of them."""
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    out = output_folder(folder)
    rendered = {name: (out / name).read_bytes() for name in SIGNED_DOCUMENTS}
    for name in SIGNED_DOCUMENTS:
        (out / name).write_bytes(rendered[name] + b"\nWhat an older renderer also said.\n")
    return folder, out, rendered


def test_a_resume_never_renders_a_closed_runs_documents_over_the_bytes_on_disk(tmp_path):
    """Ticket 235c (21_nemo_check's ruling, ADR-0010 read literally): resume writes what a stop left
    unwritten and nothing else. check-showcase-4-glm's certificate, signed on 23 Sept, carried
    "Franziska Dohm signs on behalf of Frerk Sievers"; today's renderer drops that line, and the
    resume re-rendered it away."""
    folder, _out, _rendered = signed_by_an_older_renderer(tmp_path)
    before = _tree(folder)

    resume(folder, "Slaughter")

    assert _tree(folder) == before


@pytest.mark.parametrize("missing", SIGNED_DOCUMENTS)
def test_a_resume_writes_the_one_document_a_stop_left_unwritten_and_only_that_one(tmp_path,
                                                                                    missing):
    folder, out, rendered = signed_by_an_older_renderer(tmp_path)
    (out / missing).unlink()
    before = _tree(folder)

    resume(folder, "Slaughter")

    assert (out / missing).read_bytes() == rendered[missing]
    after = _tree(folder)
    assert {path: sha for path, sha in after.items() if not path.endswith(f"/{missing}")} == before


def test_a_room_walked_before_245_marks_nothing_and_its_documents_are_the_run_on_files(tmp_path):
    """Ticket 245's one reading of an existing room: no `WRITTEN_BY` beside the documents means they
    were written before it, by the run on file, so a resume keeps every byte (235c) and sets
    nothing aside."""
    folder, out, _rendered = signed_by_an_older_renderer(tmp_path)
    (out / walk.WRITTEN_BY).unlink()
    before = _tree(folder)

    resume(folder, "Slaughter")

    assert _tree(folder) == before


def walked_again_and_stopped_between_its_documents(tmp_path):
    """Ticket 245's room: Slaughter walked and signed, then walked again, the second acceptance
    stopped between its two documents. The first walk's three documents carry an older renderer's
    bytes, so nothing the second walk renders can be mistaken for them."""
    folder, out, _rendered = signed_by_an_older_renderer(tmp_path)
    signed = {name: (out / name).read_bytes() for name in SIGNED_DOCUMENTS}
    first = run_of(folder)["run_id"]
    (folder / run_file("Slaughter")).unlink()
    for _ in range(8):
        waiting = walk.current(folder, "Slaughter")
        if waiting.stage != walk.STAGE_5:
            walk.answer(folder, "Slaughter", ENDORSED, waiting.revision)
    card = walk.handover_card(folder, "Slaughter")
    assert run_of(folder)["run_id"] != first, "the second walk is the first one again"
    landing, written = walk.write_document, []

    def stopping(room_folder, path, text):
        if written:
            raise KeyboardInterrupt("the box stopped between the two documents")
        written.append(path)
        return landing(room_folder, path, text)

    with pytest.MonkeyPatch.context() as stopped:
        stopped.setattr(walk, "write_document", stopping)
        with pytest.raises(KeyboardInterrupt):
            walk.accept_handover(folder, card, ENDORSED)
    assert (out / handover.HANDOVER).read_bytes() == signed[handover.HANDOVER], "nothing stopped"
    return folder, out, signed, card.proposal[walk.DOCUMENTS], first


def test_a_resumed_second_walk_shows_its_own_handover_never_the_walk_before_its(tmp_path):
    """Ticket 245: "on disk" means on disk for this run. The first walk's handover is replaced by
    the one the second walk's acceptance would have written; its own draft, already down, stays."""
    folder, out, _signed, documents, _first = walked_again_and_stopped_between_its_documents(
        tmp_path)
    draft = (out / handover.DRAFT).read_bytes()

    resume(folder, "Slaughter")

    assert (out / handover.HANDOVER).read_text(encoding="utf-8") == documents[handover.HANDOVER]
    assert (out / handover.DRAFT).read_bytes() == draft


def test_a_resumed_second_walk_sets_the_earlier_signed_certificate_aside_byte_for_byte(tmp_path):
    """Ticket 245: the earlier walk's signed certificate is never overwritten and never deleted. It
    leaves its name, which a certificate holds only for this walk's own closing signature, and
    stays beside the new documents under a name carrying the run that signed it."""
    folder, out, signed, _documents, first = walked_again_and_stopped_between_its_documents(
        tmp_path)

    resume(folder, "Slaughter")

    assert not (out / handover.CERTIFICATE).exists()
    assert [path.name for path in out.iterdir()
            if path.read_bytes() == signed[handover.CERTIFICATE]] == [
        f"owner-signoff-certificate-{first}.md"]


def test_a_second_walk_signed_sets_the_earlier_certificate_aside_and_a_resume_moves_nothing(
        tmp_path):
    """Ticket 245 on the press's path: the second walk's signature never writes over the first's
    certificate, and its own, marked as its own, is what a resume after it finds on disk."""
    folder, out, signed, _documents, first = walked_again_and_stopped_between_its_documents(
        tmp_path)
    resume(folder, "Slaughter")
    card = walk.signature_card(folder, "Slaughter")
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    before = _tree(folder)

    resume(folder, "Slaughter")

    assert _tree(folder) == before
    assert (out / f"owner-signoff-certificate-{first}.md").read_bytes() == signed[
        handover.CERTIFICATE]
    assert (out / handover.CERTIFICATE).read_text(encoding="utf-8") == handover.certificate(
        card.proposal[BIA], run_of(folder))


def walked_sales_after_signing_slaughter(tmp_path):
    """Review C3's path (probe p5): Slaughter signed, then Sales walked to stage 5 in the same room.

    The skin offers another activity straight after the signature, and Sales carries the same
    testimony under its own department line, so it walks without one stage of its own being new.
    """
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    held = (folder / INTERVIEWS / "26_08_00_interview.md").read_text(encoding="utf-8")
    (folder / INTERVIEWS / "26_08_01_interview.md").write_text(
        held.replace("department: Slaughter", "department: Sales"), encoding="utf-8")
    for _ in range(8):
        waiting = walk.current(folder, "Sales")
        if waiting.stage != walk.STAGE_5:
            walk.answer(folder, "Sales", ENDORSED, waiting.revision)
    assert walk.current(folder, "Sales").stage == walk.STAGE_5, "Sales never reached its handover"
    return folder


def _records_in(folder):
    """Every BIA record the room holds, wherever under output/ it was put."""
    return [json.loads(path.read_bytes()) for path in (folder / "output").rglob("bia-record.json")]


def test_a_second_walk_in_the_room_leaves_the_signed_record_where_it_was(tmp_path):
    """Ticket 235: the bytes his signature rests on stay in the room after the next walk lands.

    One record per room let Sales' stage 4 land over Slaughter's signed record: the receipt's
    `record_sha` then matched nothing on disk, and the signed walk could not be resumed.
    """
    folder = walked_sales_after_signing_slaughter(tmp_path)
    signed = run_of(folder)

    assert signed["status"] == walk.CLOSED
    assert signed[RECEIPT]["record_sha"] in [fingerprint(record) for record in _records_in(folder)]
    assert {record["dept"] for record in _records_in(folder)} == {"Slaughter", "Sales"}
    assert resume(folder, "Slaughter").activities == ("Slaughter",)


def test_resume_of_a_closed_run_whose_record_is_not_its_own_answers_and_raises_nothing(tmp_path):
    """Ticket 235 box 3: a CLOSED run over a record it did not produce is resumed as the documents
    are (`_documents_again`): the state on disk is served, nothing is written, nothing is raised."""
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    [path] = (folder / "output").rglob("bia-record.json")
    landed = json.loads(path.read_bytes())
    write_record(folder, str(path.relative_to(folder)), {**{k: v for k, v in landed.items()
                                                             if k != "revision"},
                                                          "run_id": "somebody-else"},
                 landed["revision"])
    certificate = output_folder(folder) / handover.CERTIFICATE
    certificate.unlink()

    assert resume(folder, "Slaughter").activities == ("Slaughter",)
    assert not certificate.exists(), "a certificate was written over a record that is not its own"


#: Where a room kept its one record before ticket 235 (check-showcase-4-glm's signed walk is there).
LEGACY = "output/bia-record.json"


def signed_before_235(tmp_path, dept="Slaughter"):
    """A signed Slaughter walk whose record sits at the room's old place, naming `dept`, with its
    certificate gone: only the record being found again writes it back."""
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    certificate = output_folder(folder) / handover.CERTIFICATE
    certificate.unlink()
    record = json.loads((folder / RECORD).read_bytes())
    (folder / LEGACY).write_text(json.dumps({**record, "dept": dept}), encoding="utf-8")
    (folder / RECORD).unlink()
    return folder, card, certificate


def _tree(folder):
    """Every file in the room and the sha256 of its bytes."""
    return {path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob("*")) if path.is_file()}


def test_a_signed_walk_whose_record_is_at_the_old_place_resumes_closed_with_its_certificate(
        tmp_path):
    """Ticket 235b: a room walked before 235 keeps its signed walk. The record at the old place
    names this process in its own `dept`, so it is read as this process's record — and left where
    it is: looking at a signed walk moves nothing (21_nemo_check's ruling)."""
    folder, card, certificate = signed_before_235(tmp_path)
    before = (folder / LEGACY).read_bytes()

    assert resume(folder, "Slaughter").activities == ("Slaughter",)

    assert run_of(folder)["status"] == walk.CLOSED
    assert certificate.read_text(encoding="utf-8") == handover.certificate(
        card.proposal[BIA], run_of(folder))
    assert (folder / LEGACY).read_bytes() == before
    assert not (folder / RECORD).exists()


def test_opening_a_room_with_a_record_at_the_old_place_changes_not_one_byte(tmp_path):
    folder, card, certificate = signed_before_235(tmp_path)
    certificate.write_text(handover.certificate(card.proposal[BIA], run_of(folder)),
                           encoding="utf-8")
    before = _tree(folder)

    for process in processes(folder):
        walk.current(folder, process)
    resume(folder, "Slaughter")

    assert _tree(folder) == before


def test_a_record_at_the_old_place_naming_another_process_is_never_this_ones(tmp_path):
    folder, _card, certificate = signed_before_235(tmp_path, dept="Sales")

    resume(folder, "Slaughter")

    assert not certificate.exists(), "Sales' record was read as Slaughter's"
    assert not (folder / RECORD).exists()
    assert read_record(folder, LEGACY)["dept"] == "Sales"


@pytest.mark.parametrize("documents_there", [False, True])
def test_the_next_record_write_moves_the_old_place_to_the_process_own(tmp_path, documents_there):
    """The record at the old place is this process's at its revision, so the next stage 4 press is
    answered against it and lands at the process's own place; the old file is gone, because two
    copies of one record are two places to read it from and one of them would drift. A walk signed
    before 235 has its certificate in the process's folder already."""
    folder, _card = refereed(tmp_path)
    if documents_there:
        (folder / RECORD).parent.mkdir()
    (folder / LEGACY).write_text(json.dumps({"dept": "Slaughter", "revision": 3}),
                                 encoding="utf-8")
    card = record_card(folder, "Slaughter")

    said(folder, card, ENDORSED)

    assert card.record_revision == 3
    assert read_record(folder, RECORD)["revision"] == 4
    assert not (folder / LEGACY).exists()


def test_a_press_overtaken_at_the_old_place_moves_nothing(tmp_path):
    folder, card = refereed(tmp_path)
    (folder / LEGACY).write_text(json.dumps({"dept": "Slaughter", "revision": 3}),
                                 encoding="utf-8")

    answered = walk.answer(folder, "Slaughter", ENDORSED, card.revision,
                           record_revision=card.record_revision)[0]

    assert answered.body.startswith(OVERTAKEN)
    assert read_record(folder, LEGACY) == {"dept": "Slaughter", "revision": 3}
    assert not (folder / RECORD).exists()


def test_a_record_at_the_old_place_naming_another_process_stays_on_this_ones_write(tmp_path):
    folder, card = refereed(tmp_path)
    (folder / LEGACY).write_text('{"dept": "Sales", "revision": 3}', encoding="utf-8")

    said(folder, card, ENDORSED)

    assert read_record(folder, RECORD)["revision"] == 1
    assert read_record(folder, LEGACY) == {"dept": "Sales", "revision": 3}


def _write_that_fails(*_args, **_kwargs):
    """A document write that does not land: the disk full, the room gone, the process stopped."""
    raise OSError("the certificate did not land")


def test_a_run_that_is_not_closed_gets_no_certificate_from_a_resume(tmp_path):
    """The repair is the closure's own, not every resume's: a run nobody signed stays uncertified.

    Stage 4's ordinary stop resumes constantly (ADR-0010), and a certificate written on any of
    those would mean the document on disk no longer says a signature with authority closed this.
    """
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Petra Nolte", "sponsor")
    assert run_of(folder)["status"] == walk.REVIEWED

    resume(folder, "Slaughter")

    assert not (output_folder(folder) / handover.CERTIFICATE).exists()


def test_a_closed_run_is_no_longer_one_this_room_has_in_progress(tmp_path):
    folder, card = signing(tmp_path)
    assert in_progress(folder) == ["slaughter"]

    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")

    assert in_progress(folder) == []


def test_a_delegate_who_signs_on_behalf_of_the_owner_closes_it_and_is_named_as_that(tmp_path):
    """The owner's ruling of 2026-09-17, now nemo's own: every phone walk of the demo is this one.

    The choice arrives as the argument his tap carries, so the signature records the capacity it
    was actually given in — not the one a role string claimed, which is what the live app's module
    global read.
    """
    folder, card = signing(tmp_path)

    answered = walk.sign(folder, card, "Petra Nolte", "Deputy",
                         on_behalf_of="Torsten Ahlgrim")

    saved = run_of(folder)
    assert saved["status"] == walk.CLOSED
    assert saved[handover.SIGNATURE]["capacity"] == handover.ON_BEHALF_OF.format(
        owner="Torsten Ahlgrim")
    assert answered.body == walk.SIGNED_OFF
    certificate = (output_folder(folder) / handover.CERTIFICATE).read_text()
    assert handover.ON_BEHALF_OF.format(owner="Torsten Ahlgrim") in certificate
    assert handover.OWNER_OF_THE_ACTIVITY not in certificate


def test_a_signature_on_behalf_of_a_name_the_record_does_not_hold_is_refused(tmp_path):
    """Never free text: the run is untouched and no certificate is written for the claim."""
    folder, card = signing(tmp_path)

    with pytest.raises(handover.NotAnOwner):
        walk.sign(folder, card, "Petra Nolte", "Deputy", on_behalf_of="Somebody Else")

    assert run_of(folder)["status"] == walk.REVIEWED
    assert not (output_folder(folder) / handover.CERTIFICATE).exists()


def test_a_signature_from_anybody_else_is_kept_as_what_it_is_and_closes_nothing(tmp_path):
    """v1 validated a sign-off whose signer's role read "explicitly not the process owner"."""
    folder, card = signing(tmp_path)

    answered = walk.sign(folder, card, "Petra Nolte", "explicitly not the process owner")

    saved = run_of(folder)
    assert saved["status"] == walk.REVIEWED
    assert walk.SIGNED_ON not in saved, "nothing closed, so nothing is dated (ticket 258)"
    assert saved[handover.SIGNATURE]["capacity"] == handover.SPONSOR
    assert answered.body == walk.NOT_THE_OWNER.format(
        capacity=handover.SPONSOR, owner="Torsten Ahlgrim")
    assert not (output_folder(folder) / handover.CERTIFICATE).exists()


def test_a_signed_bia_is_final_and_a_second_signature_lands_on_nothing(tmp_path):
    """Ticket 239 (C4, probe p1): a CLOSED run is never signed again, by anybody.

    Before 239 a sponsor's signature on a closed run overwrote the owner's and moved the run back
    to ``REVIEWED``, with the owner's certificate left on disk saying the opposite.
    """
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    closed = run_of(folder)
    certificate = (output_folder(folder) / handover.CERTIFICATE).read_bytes()

    again = walk.signature_card(folder, "Slaughter")
    refused = walk.sign(folder, again, "Petra Nolte", "sponsor")

    assert run_of(folder) == closed, "a second signature reopened a signed BIA"
    assert (output_folder(folder) / handover.CERTIFICATE).read_bytes() == certificate
    assert again == refused == nothing_to_sign(walk.ALREADY_SIGNED, closed)
    assert walk.ALREADY_SIGNED == (
        "This BIA is already signed. A signed BIA is final, so it can't be signed again.")


def test_a_handover_nobody_accepted_is_not_signed(tmp_path):
    """Ticket 239 (C4, probe p2): the one edge into CLOSED runs through an accepted handover.

    Before 239 a signature on a handover still waiting for his answer closed the run with no
    stage 5 decision and no documents on file (ADR-0010).
    """
    folder, _card = handed_over(tmp_path)
    before = run_of(folder)

    card = walk.signature_card(folder, "Slaughter")
    refused = walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")

    assert run_of(folder) == before, "a signature landed on a handover nobody accepted"
    assert not (output_folder(folder) / handover.CERTIFICATE).exists()
    assert card == refused == nothing_to_sign(walk.NOT_ACCEPTED_YET, before)


def test_a_room_with_no_walk_yet_is_told_there_is_nothing_to_sign(tmp_path):
    """The refusal is a card with a sentence, never an exception out of the door."""
    folder = room(tmp_path)

    card = walk.signature_card(folder, "Slaughter")

    assert card == nothing_to_sign(walk.NOT_ACCEPTED_YET, None, method=walk._method(folder))
    assert walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter") == card
    assert walk.read_record(folder, run_file("Slaughter")) is None


def nothing_to_sign(body, run, method=COPIED_METHOD):
    """The signature card of a run nothing signs: the sentence why, and nothing to answer."""
    return walk.Card(stage=walk.STAGE_5, name="signature", heading=walk.HEADING_5,
                     activities=("Slaughter",), body=body, sources=(RECORD,), buttons=(),
                     decision="", rule="", gradient=(), method=method, saved=run,
                     revision=(run or {}).get("revision", 0))


def test_signing_accepts_every_open_item_on_the_card_and_nothing_else(tmp_path):
    """Ticket 239 (C2, his ruling "Signing accepts all shown"): never more, never fewer.

    Before 239 the ids came in beside the card and were stored as given: "OPEN-99", shown to
    nobody, landed in the run. Now there is no way to hand `sign` an id at all.
    """
    folder, card = signing(tmp_path)
    shown = list(card.proposal[walk.ITEMS])
    assert shown, "this room was meant to leave something open to accept"

    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")

    assert run_of(folder)[handover.SIGNATURE]["accepted"] == shown
    assert list(inspect.signature(walk.sign).parameters) == [
        "room_folder", "card", "name", "role", "on_behalf_of"], "an id can be handed in again"

# ── a department a real plant would name (ticket 32) ─────────────────────────
def test_a_department_with_a_digit_in_its_name_reaches_a_stage_one_card(tmp_path):
    """`Werk 1`, `Linie 2`, `Halle 45`: the digit is inside the name, and the empty stage 1 record
    holds nothing at all. The names the card is checked with are the room's own (`activities`)."""
    folder = room(tmp_path, transcripts=("Werk 1",), register=("Werk 1",))
    card = open_bia(folder, "Werk 1")
    assert render(card.stage, card.screen, card.record, card.activities) == card.screen


def test_the_name_exempts_its_own_span_on_that_card_and_nothing_wider(tmp_path):
    """The room supplying a name with a digit in it licenses no figure standing beside it."""
    folder = room(tmp_path, transcripts=("Werk 1",), register=("Werk 1",))
    card = open_bia(folder, "Werk 1")
    with pytest.raises(CardGeneratorBug):
        render(card.stage, card.screen + " Werk 1 runs 45 cutters.", card.record, card.activities)


# ── 46: the door's own seams, pinned where only a feature file stood (ticket 46) ─────────────
#
# Ticket 24 put the seven presses behind `answer` and `resume`, and the scenarios that walk the
# new door live in `features/`. `mutmut` selects its tests out of `src/` only, so a line only a
# feature file reaches is a line no mutant of it has to survive. These tests say the same things
# here, at the unit the door is.


def test_the_door_hands_back_the_confirmation_and_the_card_that_follows_it(tmp_path):
    """One answer, two cards: what the stage now says, and the stage that follows it.

    The page draws what comes back and decides nothing (ADR-0010), so a door that handed back the
    confirmation alone would stop the walk dead at every stage it answered — the manager would
    read "that's stage 1 of 5 done" with nothing behind it to answer next.
    """
    folder = room(tmp_path)
    card = open_bia(folder, "Slaughter")

    handed = walk.answer(folder, "Slaughter", AGREE, card.revision)

    assert [each.stage for each in handed] == [STAGE, STAGE_2]
    assert handed[0].buttons == () and handed[1].buttons == GRADIENT


def test_a_scope_agreed_with_something_held_back_is_recorded_as_a_reservation(tmp_path):
    """Stage 1 reads the manager's own words for a caveat exactly as the other three stages do.

    Stage 1 has no figure to hold a reservation about (ADR-0011), so the gradient rides in the
    record underneath rather than on the card — which is precisely why a stage 1 that took the
    words as endorsed regardless would leave nothing on screen to notice.
    """
    folder = room(tmp_path)

    said(folder, open_bia(folder, "Slaughter"), "Yes, but the cooling line belongs in it too")

    decided = read_record(folder, run_file("Slaughter"))["decisions"][-1]
    assert without_telemetry(decided) == {"stage": STAGE, "decided": "yes",
                                          "gradient": RESERVED, "naming": UNNAMED}


def test_the_record_revision_the_page_read_is_the_one_the_press_is_answered_against(tmp_path):
    """The room's BIA record is shared between the walks in it, so stage 4's acceptance is
    conditional on that file not having moved while the manager read the card drawn against it.

    The revision therefore travels in from the page and is not read again here: a door that
    re-read it would compare the room's record against itself, the compare-and-set would be a
    no-op, and this walk would write over a record another walk in the room had just landed
    (second-opinion finding 5, 2026-09-14).
    """
    folder, card = refereed(tmp_path)
    write_record(folder, RECORD, ANOTHER_WALKS, card.record_revision)

    answered = walk.answer(folder, "Slaughter", ENDORSED, card.revision,
                           record_revision=card.record_revision)[0]

    assert answered.body.startswith(OVERTAKEN)
    assert read_record(folder, RECORD)["run_id"] == ANOTHER_WALKS["run_id"]


def test_the_one_interview_on_the_card_is_bound_without_being_picked(tmp_path):
    """A room holding one interview for the process is not asking the manager to choose.

    Which interview the manager chose is the one thing about a stage 2 answer the room's own disk
    cannot say — except where the room holds exactly one, and then it can. A door that insisted on
    a pick would leave the ordinary room unanswerable.
    """
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    assert len(card.interviews) == 1, "the room this test is about holds one interview"

    said(folder, card, ENDORSED)

    bound_to = read_record(folder, run_file("Slaughter"))["transcript"]
    assert bound_to["path"] == card.interviews[0].path


def test_the_preview_is_answered_under_the_stage_two_rule(tmp_path):
    """An interview held in the room is a longer path to stage 2's decision, not a different one.

    The four labels are on the card either way, so the sentence saying what answering with one of
    them costs has to be on it either way too — a preview that dropped it would put the labels in
    front of a manager with nothing beside them saying what happens next.
    """
    folder = at_the_live_interview(tmp_path)

    assert held_interview(folder, "Slaughter", LIVE).rule == RULE_2


def test_an_evidence_answer_that_lost_the_race_offers_stage_three_again(tmp_path):
    """Stage 3 is overtaken the same way stages 1, 2 and 4 are, and says so in the one voice.

    The card is re-read rather than patched, so what comes back is the room's own state and not
    the one the press was written against — still stage 3, still asking, with the news in front.
    """
    folder, card = reached(tmp_path)
    moved_on(folder)

    answered = said(folder, card, ENDORSED)

    assert answered.body.startswith(OVERTAKEN)
    assert (answered.stage, answered.heading) == (STAGE_3, HEADING_3)
    assert answered.buttons == GRADIENT
    assert namings(read_record(folder, run_file("Slaughter"))) == (), "the losing press saved"


def test_a_reservation_the_manager_waves_off_is_taken_back_off_the_answer(tmp_path):
    """`docs/voice.md` §4.3: the pressure to explain yourself is for somebody who said nothing.

    The walk leans towards asking, so it reads a caveat into plain answers it should not have;
    the recovery it owes for that is this. The reservation comes off the answer rather than being
    emptied on it — a naming of nothing at all is a reservation with nothing in it, and the
    signature would carry it as one.
    """
    folder, _answered = reached(tmp_path, answer="endorsed with reservations")

    waved = typed(folder, "Nothing.")

    run = read_record(folder, run_file("Slaughter"))
    assert [each.body for each in waved] == [NOTHING_RESERVED]
    assert [each["stage"] for each in run["decisions"]] == [STAGE, STAGE_2, STAGE_3]
    assert without_telemetry(run["decisions"][-1]) == {"stage": STAGE_3, "gradient": ENDORSED}
    assert namings(run) == ()


def test_a_blocked_answer_named_with_a_no_keeps_blocked_and_his_words(tmp_path):
    """Review C1 (b), probe p3 end to end: blocked at stage 2, then a naming that opens with "No".
    Before 234 the "No" waved the reservation off and the answer was rewritten to *endorsed*."""
    folder = at_stage_2(tmp_path)
    card = walk.current(folder, "Slaughter")
    walk.answer(folder, "Slaughter", "blocked", card.revision)
    naming = "No, this interview is from the wrong shift"

    typed(folder, naming)

    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": STAGE_2, "gradient": GRADIENT[3], "naming": naming}


@pytest.mark.parametrize("answer", GRADIENT[2:])
def test_a_refusal_is_never_waved_back_to_an_endorsement(tmp_path, answer):
    """Nothing turns *needs discussion* or *blocked* into *endorsed*: a bare "Nothing." after one
    is his naming, kept as he typed it."""
    folder, _answered = reached(tmp_path, answer=answer)

    typed(folder, "Nothing.")

    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": STAGE_3, "gradient": answer, "naming": "Nothing."}


def test_a_naming_that_only_opens_with_nothing_is_his_naming(tmp_path):
    """The wave-off is the whole line and nothing more (234): "None of the night shift was asked"
    names a reservation, and a reading that stopped at its first word would erase it."""
    folder, _answered = reached(tmp_path, answer="endorsed with reservations")
    naming = "None of the night shift was asked"

    typed(folder, naming)

    assert without_telemetry(run_of(folder)["decisions"][-1]) == {
        "stage": STAGE_3, "gradient": RESERVED, "naming": naming}


def test_the_card_a_resume_hands_back_is_stage_four_confirmed_in_its_own_words(tmp_path):
    """What the manager reads after a stop is the card the accepting answer would have given him:
    stage 4, its own heading, and the confirmation with the picture now drawn in it."""
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)
    run = read_record(folder, run_file("Slaughter"))

    resumed = resume(folder, "Slaughter")

    assert (resumed.stage, resumed.heading) == (STAGE_4, HEADING_4)
    assert resumed.body == " ".join([ACCEPTED, checked_note(run), PICTURE_DRAWN])


def test_a_resume_over_a_reservation_nobody_named_still_asks_for_the_naming(tmp_path):
    """A stop between the record landing and the picture being drawn must not eat the question.

    The walk was waiting to be told what was reserved when it stopped, and it is still waiting
    when it comes back: a resume that read the accepting confirmation over it would tell the
    manager the stage was endorsed and drop the reservation on the way to the signature.
    """
    folder, card = refereed(tmp_path)
    saved_only(folder, card, "endorsed with reservations")

    resumed = resume(folder, "Slaughter")

    assert resumed.body == NAMING
    assert namings(read_record(folder, run_file("Slaughter"))) == ((STAGE_4, UNNAMED),)


def test_the_second_movement_is_handed_the_run_the_first_one_left_on_disk(tmp_path, monkeypatch):
    """The first movement's card is the second movement's input, and it carries the run state.

    `_draw_graph` hands its card straight back where there is nothing of this walk's to draw, and
    a page then reads `saved` and `revision` off whatever comes back. A card that said "saved"
    while carrying no run at all would put the walk's next press on revision 0, which is the
    compare-and-set the whole stage rests on.
    """
    folder, card = refereed(tmp_path)
    saved_only(folder, card, ENDORSED)
    run = read_record(folder, run_file("Slaughter"))
    drawing, handed = walk._draw_graph, []

    def watching(room_folder, given):
        handed.append(given)
        return drawing(room_folder, given)

    monkeypatch.setattr(walk, "_draw_graph", watching)
    resume(folder, "Slaughter")

    assert [each.saved for each in handed] == [run]
    assert [each.revision for each in handed] == [run["revision"]]


# ── the walk's own telemetry: when, on what, and what was refused (work item 2) ───
#
# Every answer to the four questions a real walk has to be readable for afterwards — where did he
# stall, what did nemo refuse him, what was he looking at, how long did it take — is either in the
# decisions list or nowhere. v1 answered them with an operator's handwritten turnlog, which is why
# walk 15's "47 ledger rows, 24 turns, 13.1 minutes" is a person's note and not the system's
# output. These are a record of what happened and never a check on it.


def test_the_moment_a_decision_carries_is_the_clock_in_utc_to_the_second():
    """One clock, in one function, so a pinned test and the deployed walk read the same seam."""
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", walk._now())


def test_every_decision_carries_the_moment_it_was_taken(tmp_path, monkeypatch):
    """ADR-0010 says the run carries the timestamp of its transition and no code ever wrote one."""
    monkeypatch.setattr(walk, "_now", lambda: "2026-09-20T15:04:05+00:00")
    folder, card = refereed(tmp_path)

    said(folder, card, ENDORSED)

    run = read_record(folder, run_file("Slaughter"))
    assert [decision[AT_TIME] for decision in run[DECISIONS]] == [
        "2026-09-20T15:04:05+00:00"] * len(run[DECISIONS])


def test_every_decision_carries_the_card_it_was_taken_on(tmp_path):
    """The stage alone does not say what was in front of him: a name, not a sentence."""
    folder, card = refereed(tmp_path)

    said(folder, card, ENDORSED)

    run = read_record(folder, run_file("Slaughter"))
    assert [decision[ON_CARD] for decision in run[DECISIONS]] == [
        "scope", "interview", "evidence", "record"]


#: The run a stage-4 press leaves on disk, byte for byte, with the two seams that are not a
#: function of the room held still: the clock and the run's minted identity. Every other byte —
#: the method copied out of the file, the evidence, the decisions, the record's fingerprint and the
#: receipt bound to it — is derived from the room, so the digest moves only when the shape does.
#: Re-derived for ticket 168 (run record gains the confirmed interviews, `"interviews"`), bundle B'.
#: Re-derived for ticket 243 (the receipt drops `page_sha`, `url` and `build_version`).
STAGE_4_RUN_BYTES = "b24c2c7ba4f6a72e28fab867dd2da6f4f5a40e65aeeb044c44c0c7254df239b7"


def test_the_run_a_stage_four_press_writes_is_the_same_bytes_every_time(tmp_path, monkeypatch):
    """The record's shape is read by the referee, by stage 5 and by the skin, so a press that
    writes one byte differently is a change to a shape other code depends on and is never a side
    effect of tidying the call that writes it. Pinned whole rather than key by key: a key that
    stopped being written, or one that started, is exactly what the other tests here would pass
    over. A deliberate shape change re-derives the digest in the same commit as the change.
    """
    monkeypatch.setattr(walk, "_now", lambda: "2026-09-20T15:04:05+00:00")
    monkeypatch.setattr(walk.uuid, "uuid4", lambda: uuid.UUID(int=0))
    folder, card = refereed(tmp_path)

    said(folder, card, ENDORSED)

    written = (folder / run_file("Slaughter")).read_bytes()
    assert json.loads(written)[DECISIONS][-1] == {
        AT_STAGE: STAGE_4, AT_TIME: "2026-09-20T15:04:05+00:00", ON_CARD: "record",
        REFUSALS: [], "gradient": ENDORSED}
    assert hashlib.sha256(written).hexdigest() == STAGE_4_RUN_BYTES


def test_a_press_over_a_refused_record_keeps_nothing_and_the_card_keeps_the_refusal(tmp_path):
    """Until ticket 170 a press over a refused record saved it and kept the refusal's parts on the
    decision it wrote. A refused record is never saved now, so there is no decision to keep them
    on: the refusal stays where the manager reads it, on the card, as the parts the referee handed
    over (`nemo.refusal`), and the run is exactly as it was."""
    folder = refused(tmp_path)
    verdict = check_draft(folder, "Slaughter")
    card = record_card(folder, "Slaughter")
    run = read_record(folder, run_file("Slaughter"))

    said(folder, card, ENDORSED)

    assert read_record(folder, run_file("Slaughter")) == run
    assert [(item.kind, dict(item.parts)) for item in card.refused] == [
        (item.kind, dict(item.parts)) for item in verdict.rejections]


def test_the_card_a_press_answers_with_keeps_the_name_of_the_card_it_answered(tmp_path):
    """A press hands back the same card, said differently — so the answered card is still the
    record card, and a stage that read a name off it would read the one the manager pressed."""
    folder, card = refereed(tmp_path)

    assert said(folder, card, ENDORSED).name == card.name == "record"


def test_the_handover_names_itself_on_the_decision_it_takes(tmp_path):
    """The last two cards are both stage 5, so the stage alone cannot tell them apart and the
    name is the only thing that does."""
    folder, card = handed_over(tmp_path)

    said(folder, card, ENDORSED)

    assert run_of(folder)[DECISIONS][-1][ON_CARD] == "handover"


def test_the_signature_card_is_the_one_card_that_takes_no_decision(tmp_path):
    """Signing writes a signature and a certificate, not a sixth decision — so the name it carries
    is never appended, and the handover stays the last card the decisions list names."""
    folder, card = handed_over(tmp_path)
    said(folder, card, ENDORSED)

    signing = walk.signature_card(folder, "Slaughter")

    assert signing.name == "signature"
    assert run_of(folder)[DECISIONS][-1][ON_CARD] == "handover"


def test_a_press_over_a_record_the_referee_passes_refuses_nothing(tmp_path):
    """The other half: a clean press carries an empty list, not a missing key."""
    folder, card = refereed(tmp_path)

    said(folder, card, ENDORSED)

    run = read_record(folder, run_file("Slaughter"))
    assert run[DECISIONS][-1][REFUSALS] == []


# ── ticket 115: what a turn prints, and in what order ────────────────────────────────────────────
# The owner, typed 2026-09-22: "nothing long prints by default; the answer comes first; the grid,
# the open decisions and the record appear only when I choose." Two things stand without a tap:
# the one card whose taps are live, and the record before the signature (ADR-0022).
EVERY_STAGE = [None, walk.STAGE, walk.STAGE_2, walk.STAGE_3, walk.STAGE_4, walk.STAGE_5]
SHOW_TAPS = ["grid", "decisions"]


def test_a_free_chat_answer_prints_the_answer_alone():
    assert walk.prints(None, "") == ["answer"]


def test_stage_3_with_a_decision_open_prints_the_answer_then_the_live_card():
    assert walk.prints(walk.STAGE_3, "", decision_open=True) == ["answer", "live_card"]


def test_stage_3_with_nothing_open_prints_the_answer_alone():
    assert walk.prints(walk.STAGE_3, "") == ["answer"]


def test_an_open_decision_draws_no_live_card_outside_stage_3():
    assert walk.prints(walk.STAGE_4, "", decision_open=True) == ["answer"]


def test_stage_4_with_the_record_due_prints_the_answer_then_the_record():
    assert walk.prints(walk.STAGE_4, "", record_due=True) == ["answer", "record"]


def test_the_record_is_drawn_at_stage_4_only():
    assert walk.prints(walk.STAGE_3, "", record_due=True) == ["answer"]


@pytest.mark.parametrize("tapped", SHOW_TAPS)
def test_a_show_tap_prints_its_table_alone(tapped):
    """The tap turn has no answer, and the live card already stands above it."""
    assert walk.prints(walk.STAGE_3, tapped, decision_open=True) == [tapped]


@given(st.sampled_from(EVERY_STAGE), st.sampled_from(["", "as_is", "step", "all"]),
       st.booleans(), st.booleans())
def test_no_turn_without_a_show_tap_prints_the_grid_or_the_decisions(stage, tapped, open_, due):
    shown = walk.prints(stage, tapped, decision_open=open_, record_due=due)
    assert shown[0] == "answer"
    assert not {"grid", "decisions"} & set(shown)


@given(st.sampled_from(EVERY_STAGE), st.sampled_from(SHOW_TAPS), st.booleans(), st.booleans())
def test_a_show_tap_prints_its_table_and_nothing_else_at_any_stage(stage, tapped, open_, due):
    assert walk.prints(stage, tapped, decision_open=open_, record_due=due) == [tapped]


# ── 168: the run record holds the interviews he confirmed ────────────────────
#
# Stage 2 binds one interview, and the manager may confirm more beside it (the demo skin offers
# every interview about the activity). Which files a quote may have come from is the run record's
# to say, in the order he confirmed them, and never a skin's own state file's (ticket 168).

ONLY_IN_THE_THIRD = "Jonas: the label printer is the one thing we cannot borrow from Sales."


def confirmed_three(tmp_path):
    """A room at stage 2 holding three Slaughter interviews, all three confirmed, the first bound;
    the words ONLY_IN_THE_THIRD sit in the third file and nowhere else."""
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md",
                text=TESTIMONY.format(department="Slaughter") + ONLY_IN_THE_THIRD + "\n")
    card = pick_interview(folder, "Slaughter")
    paths = [item.path for item in card.interviews]
    said(folder, card, ENDORSED, picked=card.interviews[0], confirmed=paths)
    return folder, paths


def test_the_run_record_holds_every_interview_he_confirmed_in_his_order(tmp_path):
    folder, paths = confirmed_three(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["interviews"] == paths and len(paths) == 3
    assert saved["transcript"]["path"] == paths[0], "stage 2 still binds one interview"


def test_words_only_in_the_third_confirmed_interview_are_readable_without_the_skin(tmp_path):
    """Done-when 1: nemo's own reader, no skin patch, finds a quote from the third interview."""
    folder, paths = confirmed_three(tmp_path)
    files = walk.readable(folder, read_record(folder, run_file("Slaughter")))
    assert list(files) == paths
    assert found_in(ONLY_IN_THE_THIRD, files) == [paths[2]]


def test_a_run_of_the_new_shape_is_read_by_its_confirmed_list_and_not_its_one_transcript(tmp_path):
    """Done-when 1 as a reader alone: a run saved with three confirmed interviews, the words in the
    third, read by nemo's reader with no skin in the process."""
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md",
                text=TESTIMONY.format(department="Slaughter") + ONLY_IN_THE_THIRD + "\n")
    card = pick_interview(folder, "Slaughter")
    paths = [item.path for item in card.interviews]
    said(folder, card, ENDORSED, picked=card.interviews[0])
    saved = {**read_record(folder, run_file("Slaughter")), "interviews": paths}
    assert found_in(ONLY_IN_THE_THIRD, walk.readable(folder, saved)) == [paths[2]]


def test_the_bound_interview_is_confirmed_even_where_the_caller_left_it_out(tmp_path):
    folder = at_stage_2(tmp_path)
    interviewed(folder, name="26_09_02_interview.md")
    card = pick_interview(folder, "Slaughter")
    first, second = (item.path for item in card.interviews)
    said(folder, card, ENDORSED, picked=card.interviews[0], confirmed=[second])
    assert read_record(folder, run_file("Slaughter"))["interviews"] == [first, second]


def test_nemos_own_stage_two_confirms_the_one_interview_it_binds(tmp_path):
    folder, _card = bound(tmp_path)
    saved = read_record(folder, run_file("Slaughter"))
    assert saved["interviews"] == [saved["transcript"]["path"]]


def test_a_confirmed_path_outside_the_room_is_refused_and_nothing_is_bound(tmp_path):
    folder = at_stage_2(tmp_path)
    card = pick_interview(folder, "Slaughter")
    with pytest.raises(PathRefused):
        said(folder, card, ENDORSED, picked=card.interviews[0], confirmed=["../../etc/passwd"])
    assert "transcript" not in read_record(folder, run_file("Slaughter"))


def _old_shape(folder):
    """The run as a walk saved before 168: its one bound transcript, no confirmed list."""
    run = read_record(folder, run_file("Slaughter"))
    old = {key: value for key, value in _without_revision(run).items() if key != "interviews"}
    write_record(folder, run_file("Slaughter"), old, run["revision"])


def test_an_old_shape_run_reads_as_its_one_bound_transcript(tmp_path):
    folder, _card = bound(tmp_path)
    _old_shape(folder)
    saved = read_record(folder, run_file("Slaughter"))
    path = saved["transcript"]["path"]
    assert walk.readable(folder, saved) == {path: (folder / path).read_text(encoding="utf-8")}


def test_an_old_shape_run_is_refereed_and_signed_as_a_new_one_is(tmp_path):
    """Done-when 2: the saved run of the old shape still reads and signs, to the same record."""
    new_folder, new_card = refereed(tmp_path / "new")
    old_folder, _ = refereed(tmp_path / "old")
    _old_shape(old_folder)
    old_card = record_card(old_folder, "Slaughter")
    assert old_card.stage == STAGE_4 and old_card.buttons == GRADIENT
    assert old_card.proposal[walk.BIA]["activities"] == new_card.proposal[walk.BIA]["activities"]
    said(old_folder, old_card, ENDORSED)
    signed = read_record(old_folder, RECORD)["activities"]
    assert signed == new_card.proposal[walk.BIA]["activities"]


# ── ticket 132: the referee holds a chat confirmation against the room's turn file ────────────────
def test_the_turns_a_record_s_chat_confirmations_name_are_read_from_the_room(tmp_path):
    from nemo import turn_file

    turn_file.write(tmp_path, {"said": "Record RTO 8 h", "how": "tapped"}, wording="w", calls=[],
                    clock=lambda: 1_800_000_000.0, new_id=lambda: "t-7")
    turn_file.write(tmp_path, {"said": "other", "how": "typed"}, wording="w", calls=[],
                    new_id=lambda: "t-8")
    record = {"activities": [{"evidence": [
        {"type": "transcript_quote", "quote": "q", "turn_id": "t-8"},
        {"type": "chat_confirmation", "words": "Record RTO 8 h", "on": "2027-01-15",
         "turn_id": "t-7"}]}]}
    assert walk.confirmed_turns(tmp_path, record) == {
        "t-7": {"words": "Record RTO 8 h", "on": "2027-01-15"}}
    assert walk.confirmed_turns(tmp_path, {"activities": [{"evidence": []}]}) == {}


# ── 241 slice 4 (t171): the turn under way is his too, until its line is written ─────────────────
UNDER_WAY = ("t-now", {"words": "Withdraw", "on": "2026-10-02"})


def confirming(*turn_ids):
    """A record whose chat confirmations name `turn_ids`, and a quote naming one it never reads."""
    return {"activities": [{"evidence": [
        {"type": "transcript_quote", "quote": "q", "turn_id": "t-quote"},
        *({"type": "chat_confirmation", "words": "w", "on": "2026-10-02", "turn_id": turn_id}
          for turn_id in turn_ids)]}]}


def test_the_turn_under_way_is_read_where_a_confirmation_names_it(tmp_path, monkeypatch):
    monkeypatch.setitem(walk.IN_FLIGHT, str(tmp_path), UNDER_WAY)
    assert walk.confirmed_turns(tmp_path, confirming("t-now")) == {"t-now": UNDER_WAY[1]}


def test_the_turn_under_way_is_not_read_where_no_confirmation_names_it(tmp_path, monkeypatch):
    monkeypatch.setitem(walk.IN_FLIGHT, str(tmp_path), ("t-quote", UNDER_WAY[1]))
    assert walk.confirmed_turns(tmp_path, confirming()) == {}
    assert walk.confirmed_turns(tmp_path, confirming("t-other")) == {}


def test_another_room_s_turn_under_way_is_never_read(tmp_path, monkeypatch):
    monkeypatch.setitem(walk.IN_FLIGHT, str(tmp_path / "other"), UNDER_WAY)
    assert walk.confirmed_turns(tmp_path, confirming("t-now")) == {}


def test_a_turn_on_file_and_under_way_reads_as_the_file_says_it(tmp_path, monkeypatch):
    from nemo import turn_file

    turn_file.write(tmp_path, {"said": "Record RTO 8 h", "how": "typed"}, wording="w", calls=[],
                    clock=lambda: 1_800_000_000.0, new_id=lambda: "t-now")
    monkeypatch.setitem(walk.IN_FLIGHT, str(tmp_path), UNDER_WAY)
    assert walk.confirmed_turns(tmp_path, confirming("t-now", "t-7")) == {
        "t-now": {"words": "Record RTO 8 h", "on": "2027-01-15"}}


def test_a_confirmation_naming_the_empty_turn_reads_an_empty_turn_with_nothing_under_way(tmp_path):
    """What the phone has done since t171: with no turn under way the room's is the empty turn,
    so a confirmation naming the turn "" finds it, holding no words, and is refused as words that
    are not his rather than as a turn not held."""
    assert walk.confirmed_turns(tmp_path, confirming("")) == {"": {}}


# ── ticket 171: the referee reads the room's register for a register row, and nothing else ──────
def test_the_register_a_record_s_register_rows_name_is_read_from_the_room(tmp_path):
    (tmp_path / "03_Dependencies").mkdir()
    (tmp_path / walk.REGISTER).write_text('{"erp": {"recovery_point": "4 h"}}')
    (tmp_path / "other.json").write_text("{}")
    row = {"type": "register_row", "asset_id": "erp", "quote": "4 h", "source_path": walk.REGISTER}
    record = {"activities": [{"evidence": [row, {**row, "source_path": "other.json"},
                                           {"type": "transcript_quote", "quote": "q",
                                            "source_path": walk.REGISTER}]}]}
    assert walk.cited_register(tmp_path, record) == {
        walk.REGISTER: '{"erp": {"recovery_point": "4 h"}}'}
    assert walk.cited_register(tmp_path, {"activities": [{"evidence": [
        {**row, "source_path": "other.json"}]}]}) == {}
    assert walk.cited_register(tmp_path / "nowhere", record) == {}



def test_a_no_rpo_row_has_the_room_s_register_read_for_it_too(tmp_path):
    """t171-shape (DRAFT): the register saying no RPO is checked against the same file."""
    (tmp_path / "03_Dependencies").mkdir()
    (tmp_path / walk.REGISTER).write_text("{}")
    row = {"type": "register_no_rpo", "activity": "a", "asset_ids": [],
           "source_path": walk.REGISTER}
    assert walk.cited_register(tmp_path, {"activities": [{"evidence": [row]}]}) == {
        walk.REGISTER: "{}"}


def test_the_register_is_read_as_utf_8_wherever_the_skin_runs(tmp_path):
    """171h: the register the referee holds a row against reads the same from a child interpreter
    under an ASCII locale as it does here, as `test_a_transcript_is_utf_8_wherever_the_skin_runs`
    reads a transcript. The read here is also what ties this test to `cited_register` for
    mutmut, which maps a test to the functions it calls in its own process only."""
    (tmp_path / "03_Dependencies").mkdir()
    text = '{"kühl": {"rpo": "4 h"}}'
    (tmp_path / walk.REGISTER).write_text(text, encoding="utf-8")
    record = {"activities": [{"evidence": [
        {"type": "register_row", "asset_id": "kühl", "source_path": walk.REGISTER}]}]}
    child = subprocess.run(
        [sys.executable, "-c",
         "import json,pathlib,sys;from nemo.walk import cited_register;"
         "print(json.dumps(cited_register(pathlib.Path(sys.argv[1]), json.loads(sys.argv[2]))))",
         str(tmp_path), json.dumps(record)],
        capture_output=True, text=True,
        env={**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0",
             "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    assert child.returncode == 0, f"an ASCII-locale box cannot read the register:\n{child.stderr}"
    here = walk.cited_register(tmp_path, record)
    assert json.loads(child.stdout) == here == {walk.REGISTER: text}


def test_stage_four_holds_a_register_row_against_the_register_of_the_room_it_referees(
        tmp_path, monkeypatch):
    """171h, the seam `_refereed` owns: the room's register is read for a record's register row,
    so a row quoting what the room's register holds for its asset passes stage 4. Unread, the
    same row is evidence nothing could be checked against, and refused."""
    folder, _card = refereed(tmp_path)
    built = walk.bia.build
    row = {"type": "register_row", "activity": "Slaughter", "asset_id": "KA-01",
           "quote": "ammonia refrigeration", "source_path": walk.REGISTER}

    def with_a_register_row(run, files):
        record = built(run, files)
        first, *rest = record["activities"]
        return {**record, "activities": [{**first, "evidence": [*first["evidence"], row]}, *rest]}

    monkeypatch.setattr(walk.bia, "build", with_a_register_row)

    card = record_card(folder, "Slaughter")

    assert (card.stage, card.buttons) == (STAGE_4, GRADIENT), card.body
    assert row in card.proposal[BIA]["activities"][0]["evidence"]


def test_stage_four_holds_a_confirmation_against_the_turn_file_of_the_room_it_referees(
        tmp_path, monkeypatch):
    """132 over 168 (the merge seam): `_refereed` hands the referee this room's confirmed files
    AND this room's turns, so a confirmation that is his on the turn the room holds passes stage 4.
    Handed no turns, the same record is refused as evidence nothing could be checked against.

    nemo's own stage 3 drafts interview quotes alone (`bia._evidence`), so the confirmation is put
    into the built record here, where the skin's own draft puts one.
    """
    from nemo import turn_file

    folder, _card = refereed(tmp_path)
    turn_file.write(folder, {"said": "Record RTO 8 h", "how": "typed"}, wording="w", calls=[],
                    clock=lambda: 1_800_000_000.0, new_id=lambda: "t-7")
    confirmation = {"type": "chat_confirmation", "words": "Record RTO 8 h",
                    "on": "2027-01-15", "turn_id": "t-7"}
    built = walk.bia.build

    def with_his_confirmation(run, files):
        record = built(run, files)
        first, *rest = record["activities"]
        return {**record, "activities": [
            {**first, "evidence": [*first["evidence"], confirmation]}, *rest]}

    monkeypatch.setattr(walk.bia, "build", with_his_confirmation)

    card = record_card(folder, "Slaughter")

    assert (card.stage, card.buttons) == (STAGE_4, GRADIENT), card.body
    assert confirmation in card.proposal[BIA]["activities"][0]["evidence"]


# ── ticket 117: the card nemo talks about is the card his tap records ─────────────────────────────
# The owner, typed 2026-09-22: "the narrated card and the tap target are the same object". One
# order of the open decisions, nemo's, read by the taps, the live card and every model lookup.
def _conflict(cid: str, *implied: object) -> dict[str, object]:
    return {"id": cid, "type": "conflict",
            "sides": [{"speaker": "X", "implies": i} for i in implied]}


def _about(item_id: str) -> dict[str, str]:
    return {"item_id": item_id, "value": "8 h"}


def _ids(items: list[dict[str, object]]) -> list[object]:
    return [i["id"] for i in items]


def test_the_live_decision_comes_first_in_nemo_s_order_not_the_draft_s():
    # his room's shape: the draft lists C1 (about another clock) before C2 and C3 (about the MTPD)
    draft = [_conflict("C1", _about("A1.rto")), _conflict("C2", _about("A1.mtpd")),
             _conflict("C3", None, _about("A1.mtpd"))]
    assert _ids(walk.live_first(draft)) == ["C2", "C3", "C1"]


def test_nemo_s_order_is_the_mtpd_its_conflicts_the_other_conflicts_the_clocks_the_scores():
    draft = [{"id": "A1.financial", "type": "score"}, {"id": "A1.rpo", "type": "RPO"},
             {"id": "A1.rto", "type": "RTO"}, _conflict("C1", _about("A1.rto")),
             _conflict("A1-MTPD-RULE"), {"id": "A1.mtpd", "type": "MTPD"}]
    assert _ids(walk.live_first(draft)) == ["A1.mtpd", "A1-MTPD-RULE", "C1", "A1.rto", "A1.rpo",
                                           "A1.financial"]


def test_a_kind_nemo_does_not_order_comes_after_every_kind_it_does():
    draft = [{"id": "X", "type": "figure"}, {"id": "A1.financial", "type": "score"}]
    assert _ids(walk.live_first(draft)) == ["A1.financial", "X"]


def test_the_method_s_rule_is_about_the_mtpd_by_its_id_alone():
    rule = _conflict("A1-MTPD-RULE")
    assert _ids(walk.live_first([_conflict("C1"), rule])) == ["A1-MTPD-RULE", "C1"]
    # the rule's mark is the id's end, not anywhere in it
    later = _conflict("A1-MTPD-RULE-2")
    assert _ids(walk.live_first([_conflict("C1"), later])) == ["C1", "A1-MTPD-RULE-2"]


def test_a_side_is_about_the_mtpd_only_when_the_figure_it_implies_is_an_mtpd():
    draft = [_conflict("C1", _about("A1.mtpd.note")), _conflict("C2", "A1.mtpd"),
             _conflict("C3", {"value": "8 h"}), _conflict("C4", {"item_id": None}),
             _conflict("C5", _about("A1.mtpd"))]
    assert _ids(walk.live_first(draft)) == ["C5", "C1", "C2", "C3", "C4"]


def test_a_conflict_with_no_sides_is_an_ordinary_conflict():
    draft = [{"id": "C1", "type": "conflict"}, {"id": "C2", "type": "conflict", "sides": None},
             _conflict("C3", _about("A1.mtpd"))]
    assert _ids(walk.live_first(draft)) == ["C3", "C1", "C2"]


def test_an_open_item_with_no_kind_or_no_id_sorts_last_rather_than_stopping_the_list():
    """Ticket 210 (4): the stage-3 list is drawn from whatever the draft holds, and one odd item
    raised a KeyError inside `live_first` — so no open decision printed at all rather than one
    printing out of order. An unknown kind sorts last, which is what the function already says."""
    draft = [{"id": "X"}, {"type": "conflict"}, {"id": "A1.mtpd", "type": "MTPD"}, {}]
    assert [i.get("id") for i in walk.live_first(draft)] == ["A1.mtpd", None, "X", None]


def test_live_first_leaves_the_items_it_was_given_as_they_were():
    draft = [_conflict("C1", _about("A1.rto")), _conflict("C2", _about("A1.mtpd"))]
    before = [dict(i) for i in draft]
    walk.live_first(draft)
    assert draft == before and _ids(draft) == ["C1", "C2"]


_KINDS = st.sampled_from(["MTPD", "RTO", "RPO", "score", "conflict", "mtpd conflict", "rule"])


def _item(k: int, kind: str) -> dict[str, object]:
    if kind == "mtpd conflict":
        return _conflict(f"C{k}", _about(f"A{k}.mtpd"))
    if kind == "rule":
        return _conflict(f"A{k}-MTPD-RULE")
    if kind == "conflict":
        return _conflict(f"C{k}", _about(f"A{k}.rto"))
    return {"id": f"A{k}.{kind.lower()}", "type": kind}


_RANK = {"MTPD": 0, "mtpd conflict": 1, "rule": 1, "conflict": 2, "RTO": 3, "RPO": 4, "score": 5}


@given(st.lists(_KINDS, max_size=12))
def test_for_any_open_set_the_live_one_is_the_first_of_the_best_kind_in_draft_order(kinds):
    draft = [_item(k, kind) for k, kind in enumerate(kinds)]
    out = walk.live_first(draft)
    assert sorted(_ids(out), key=str) == sorted(_ids(draft), key=str)  # the same items
    ranks = [_RANK[kinds[_ids(draft).index(i)]] for i in _ids(out)]
    assert ranks == sorted(ranks)  # nemo's order
    for r in set(ranks):  # the draft's order within a kind
        same = [i for i in _ids(out) if _RANK[kinds[_ids(draft).index(i)]] == r]
        assert same == [i for i in _ids(draft) if i in same]


# ── ticket 170: a record the referee refused is never saved, whatever route the answer takes ──
#
# 21_nemo's reproduction (`~/work/nemo-builds/scratch-137/box3/drive.py`, steps 20-29, no model
# call): on the t137 walk the stage 4 card refused the record for a time band nobody scored
# (BAND_UNSCORED), drew no buttons, and one `walk.answer(..., ENDORSED, ...)` still saved it, bound
# a receipt and served stage 5. The room below is the same shape on this file's own fixture: the
# first time band left blank in the interview, so the referee refuses the record for it (here as
# `missing-horizons`: which refusal it is is not this ticket's, only that it is one).

BLANK_FIRST_BAND = EVIDENCE.replace(
    "Petra Nolte: RTO: 8 h for the stunning line.\n",
    "Petra Nolte: RTO: 8 h for the stunning line.\n"
    "Torsten Ahlgrim: Impact financial: 8 h 3, 24 h 5.\n")


def refused_at_stage_4(tmp_path):
    """drive.py's steps: the waiting stage 2 card, its interview endorsed, stage 3 endorsed, and
    the stage 4 card the walk serves after that, which the referee refuses."""
    folder = room(tmp_path)
    (folder / INTERVIEWS / "26_08_00_interview.md").write_text(BLANK_FIRST_BAND, encoding="utf-8")
    held = json.loads((folder / REGISTER).read_bytes())
    (folder / REGISTER).write_text(json.dumps({**held, **ASSETS}), encoding="utf-8")
    said(folder, open_bia(folder, "Slaughter"))
    card = walk.current(folder, "Slaughter")
    assert card.stage == STAGE_2
    card = walk.answer(folder, "Slaughter", ENDORSED, card.revision, picked=card.interviews[0])[-1]
    card = walk.answer(folder, "Slaughter", ENDORSED, card.revision)[-1]
    assert card.stage == STAGE_4 and card.buttons == ()
    assert card.refused, "the referee passed this record, so it tests nothing"
    assert card.body.startswith(REFUSED.split("{")[0])
    return folder, card


def test_an_endorsed_answer_to_a_refused_record_saves_nothing_and_says_the_refusal(tmp_path):
    """The t137 case, red on main at 01a78f7: this answer wrote the record and a receipt and
    moved the walk to stage 5."""
    folder, card = refused_at_stage_4(tmp_path)
    run = read_record(folder, run_file("Slaughter"))

    handed = walk.answer(folder, "Slaughter", ENDORSED, card.revision,
                         record_revision=card.record_revision)

    assert [each.stage for each in handed] == [STAGE_4]
    assert handed[0].body == refused_says(card.refused) and handed[0].buttons == ()
    assert read_record(folder, RECORD) is None, "the refused record was written"
    assert read_record(folder, run_file("Slaughter")) == run, "the run moved"
    assert not read_record(folder, run_file("Slaughter")).get(RECEIPT)
    assert walk.current(folder, "Slaughter").stage == STAGE_4


@pytest.mark.parametrize("words", [*GRADIENT, "yes, that's fine", "fine, but I doubt the RTO",
                                   "accept it", "the weather in Vechta"])
def test_no_answer_of_any_kind_saves_a_refused_record(tmp_path, words):
    """Every word a manager can type at the refused card, the four labels and his own alike: the
    walk hands back the refusal and writes nothing — not the record, not a reservation to name."""
    folder, card = refused_at_stage_4(tmp_path)
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    handed = walk.answer(folder, "Slaughter", words, card.revision,
                         record_revision=card.record_revision)

    assert [(each.stage, each.body) for each in handed] == [(STAGE_4, refused_says(card.refused))]
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before


# The census: every route in this module that reaches a write of the record passes the one refusal
# check first. Derived from the code, not typed as a list: the writers are found by what they call,
# the routes by who calls whom, and the entries by who can call in from outside.

#: The two checks every route passes before the record he signs is written: the referee's refusal
#: (`walk._refused`, ticket 170) and the stale answer (`walk._stale`, ticket 172).
REFUSAL_CHECK = "_refused"
STALE_CHECK = "_stale"
#: The readers that hand back a record this run itself saved: `_ours_to_draw` at stage 4, and
#: `move_past_stage_4`, the gate stage 5 carries the same record through. Bytes either returns went
#: past both checks when they were written, so rendering them again is the second movement
#: (ADR-0010, ticket 207) and not a route to a write of them.
READ_BACK = ("_ours_to_draw", "move_past_stage_4")
SKIN = Path(__file__).resolve().parents[2] / "skin"


def _names_in(node):
    return {each.id for each in ast.walk(node) if isinstance(each, ast.Name)}


def _bound_in(function):
    """The names a function binds for itself, its arguments and what it assigns, which shadow a
    module function of the same name (`accept_handover`'s `answer` is not `walk.answer`)."""
    return ({each.arg for each in ast.walk(function) if isinstance(each, ast.arg)}
            | {each.id for each in ast.walk(function)
               if isinstance(each, ast.Name) and isinstance(each.ctx, ast.Store)})


def _read_back_in(function):
    """The names `function` binds to a record a `READ_BACK` reader handed it, which are the record
    this run already wrote rather than bytes a caller supplied."""
    return {node.targets[0].id for node in ast.walk(function)
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name) and node.value.func.id in READ_BACK}


def _hands_read_back(call, read_back):
    """Whether a call carries bytes a `READ_BACK` reader handed this function.

    The one exemption, and it is over the **bytes and not over the call** (ticket 207): the same
    write reached holding a card's own proposal is still a route, and only the record this run
    itself already saved past the checks is passed over. It is read at the write itself
    (`views.write(room_folder, record)` in `_draw_graph`) and at the one call that hands those
    bytes on to a writer (`_hand_over(room_folder, record, ...)` in `_documents_again`).
    """
    return any(isinstance(arg, ast.Name) and arg.id in read_back for arg in call.args)


def _second_movement(function, read_back):
    """The functions this one only ever names holding read-back bytes: writing those again is the
    second movement (ADR-0010), so the edge is not a route to a write. A function also called with
    anything else is still a route, which is what keeps the exemption over the bytes."""
    handed, otherwise = set(), set()
    for call in _calls(function):
        if isinstance(call.func, ast.Name):
            (handed if _hands_read_back(call, read_back) else otherwise).add(call.func.id)
    return handed - otherwise


def _writes_the_record(call):
    """A call to `write_record(<room>, record_file(...), ...)`, or to `views.write` (the record's
    views)."""
    target = call.func
    if isinstance(target, ast.Name):
        return (target.id == "write_record" and len(call.args) > 1
                and isinstance(call.args[1], ast.Call)
                and isinstance(call.args[1].func, ast.Name)
                and call.args[1].func.id == "record_file")
    return (isinstance(target, ast.Attribute) and target.attr == "write"
            and isinstance(target.value, ast.Name) and target.value.id == "views")


def _calls(node):
    return [each for each in ast.walk(node) if isinstance(each, ast.Call)]


def _called_from_outside():
    """Every `walk.<name>` another module of nemo or of the skin reaches for, private or not."""
    files = [*Path(__file__).resolve().parent.glob("*.py"), *SKIN.glob("*.py")]
    return {match for path in files if not path.name.startswith("test_") and path.name != "walk.py"
            for match in re.findall(r"\bwalk\.(\w+)", path.read_text(encoding="utf-8"))}


def _call_graph(tree):
    """Each module function and the module functions it names, a table of functions standing for
    whatever it holds (`_RESERVED_AT` is how a reservation's naming reaches four card builders)."""
    functions = {node.name: node for node in tree.body
                 if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}
    tables = {target.id: _names_in(node.value) & functions.keys()
              for node in tree.body if isinstance(node, ast.Assign)
              for target in node.targets if isinstance(target, ast.Name)}
    graph = {}
    for name, function in functions.items():
        named = _names_in(function) - {name} - _bound_in(function)
        graph[name] = (named & functions.keys()) | set().union(
            *(tables[table] for table in named & tables.keys()))
    return functions, graph


def _reaching(graph, writers, guards, second_movement=None):
    """Every function with a path to a writer that does not run through a guard, and does not get
    there by handing the read-back bytes on (`_second_movement`)."""
    onward = {name: called - (second_movement or {}).get(name, set())
              for name, called in graph.items()}
    reaching = set(writers)
    while grown := {name for name, called in onward.items()
                    if name not in reaching | guards and called & reaching}:
        reaching |= grown
    return reaching


def _checks_late(function, reaching, check):
    """Whether a guard calls onward to the write on a line before its check."""
    lines = [(call.lineno, call.func.id) for call in _calls(function)
             if isinstance(call.func, ast.Name)]
    checked = min(line for line, called in lines if called == check)
    return any(line <= checked for line, called in lines if called in reaching)


#: How mutmut spells a copy it generates: `x_<name>__mutmut_orig` and `x_<name>__mutmut_<n>` for a
#: module function, `xǁ<Class>ǁ<method>__mutmut_<n>` for a method — read off a real
#: `mutants/src/nemo/walk.py`. Only the whole spelling counts, never the `x_` alone.
MUTMUT_COPY = re.compile(r"x[_\u01c1]\w*__mutmut_(orig|\d+)\Z")


def unguarded_routes(source, outside, check=REFUSAL_CHECK, writes=_writes_the_record):
    """The entries into `source` that reach a write (`writes`, the record's by default) without
    passing `check`, and any guard that calls onward to the write before it has checked. An entry
    is a public function, one another module reaches for, or one nothing in the module calls."""
    functions, graph = _call_graph(ast.parse(source))
    copies = {name for name in functions if MUTMUT_COPY.match(name)}
    read_back = {name: _read_back_in(function) for name, function in functions.items()}
    writers = {name for name, function in functions.items()
               if any(writes(call) and not _hands_read_back(call, read_back[name])
                      for call in _calls(function))}
    assert writers, "no function makes the write, so the census would pass over nothing"
    guards = {name for name, called in graph.items() if check in called}
    reaching = _reaching(graph, writers, guards, {
        name: _second_movement(function, read_back[name])
        for name, function in functions.items()})
    called = set().union(*graph.values())
    entries = {name for name in functions
               if not name.startswith("_") or name in outside or name not in called}
    entries -= copies
    return sorted(reaching & entries) + [f"{name} (writes before it checks)"
                                         for name in sorted(guards - copies)
                                         if _checks_late(functions[name], reaching, check)]


def test_every_route_to_the_record_write_passes_the_refusal_check():
    source = Path(walk.__file__).read_text(encoding="utf-8")
    assert unguarded_routes(source, _called_from_outside()) == []


def test_the_census_counts_documents_rendered_off_a_card_and_not_the_record_read_back():
    """Shown red against both plants: the exemption is over the bytes and not over the call.

    `_draw_graph` renders the four again over the record `_ours_to_draw` handed it, which is the
    one this run already wrote past the check — so `resume` is not a route to the record's write,
    and a route that renders a card's own proposal into the room still is.
    """
    source = Path(walk.__file__).read_text(encoding="utf-8")
    off_a_card = source + ("\n\ndef deliver_it_anyway(room_folder, card):\n"
                           "    return views.write(room_folder, card.proposal[BIA])\n")
    assert unguarded_routes(off_a_card, set()) == ["deliver_it_anyway"]
    read_back = source + (f"\n\ndef draw_it_anyway(room_folder, run):\n"
                          f"    record = {READ_BACK[0]}(room_folder, run)\n"
                          "    return views.write(room_folder, record)\n")
    assert unguarded_routes(read_back, set()) == []


def test_the_census_counts_a_handover_document_off_a_card_and_not_the_record_read_back():
    """The same exemption at 180's census, shown red against both plants: `_documents_again` hands
    `_hand_over` the record `move_past_stage_4` read back, so `resume` is not a route to a handover
    document's write, while a plant that hands it a card's own proposal still is."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    off_a_card = source + ("\n\ndef hand_it_over_anyway(room_folder, card):\n"
                           "    _hand_over(room_folder, card.proposal[BIA], "
                           "card.proposal[DOCUMENTS])\n")
    assert unguarded_routes(off_a_card, set(), STALE_CHECK,
                            _writes_a_handover_document) == ["hand_it_over_anyway"]
    read_back = source + (f"\n\ndef hand_it_over_again(room_folder, run):\n"
                          f"    record = {READ_BACK[1]}(room_folder, run)\n"
                          "    _hand_over(room_folder, record, handover.documents(record, run))\n")
    assert unguarded_routes(read_back, set(), STALE_CHECK, _writes_a_handover_document) == []
    both = source + (f"\n\ndef hand_it_over_both_ways(room_folder, card, run):\n"
                     f"    record = {READ_BACK[1]}(room_folder, run)\n"
                     "    _hand_over(room_folder, record, handover.documents(record, run))\n"
                     "    _hand_over(room_folder, card.proposal[BIA], card.proposal[DOCUMENTS])\n")
    assert unguarded_routes(both, set(), STALE_CHECK,
                            _writes_a_handover_document) == ["hand_it_over_both_ways"], (
        "a route that also hands the writer a card's own proposal is exempted")


def test_every_route_to_the_record_write_passes_the_stale_check():
    """Ticket 172: no route writes the record before a stale answer is refused. Red on main at
    b76e4dd, where the only stale check was the run's compare-and-set, after the record's write."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    assert unguarded_routes(source, _called_from_outside(), STALE_CHECK) == []


def test_the_census_finds_a_route_planted_past_the_stale_check():
    """The stale check's census shown red the same two ways: a planted entry, and the door with its
    stale check taken out."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    planted = source + ("\n\ndef save_it_anyway(room_folder, card):\n"
                        "    return _land(room_folder, card)\n")
    assert unguarded_routes(planted, set(), STALE_CHECK) == ["save_it_anyway"]
    unchecked = source.replace(f"if {STALE_CHECK}(room_folder, card):", "if False:")
    assert unchecked != source, "the stale check is not spelled where this test expects it"
    assert "answer" in unguarded_routes(unchecked, _called_from_outside(), STALE_CHECK)


# Ticket 180, the census's twin at stage 5: the writes are the two handover documents, found as a
# `write_document` call that is not the certificate's (`sign` writes that after the run closes, a
# separate path and not this ticket's), and every route to them passes the same `_stale` check.


def _writes_a_handover_document(call):
    """A call to `write_document(...)` that is not the certificate's."""
    return (isinstance(call.func, ast.Name) and call.func.id == "write_document"
            and "CERTIFICATE" not in {each.attr for each in ast.walk(call)
                                      if isinstance(each, ast.Attribute)})


def test_every_route_to_a_handover_document_passes_the_stale_check():
    """Red on t172 at 8933fc1, where `accept_handover` wrote both documents before its only stale
    check, the run's compare-and-set in `_save`."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    assert unguarded_routes(source, _called_from_outside(), STALE_CHECK,
                            _writes_a_handover_document) == []


def test_the_census_finds_a_route_planted_past_the_handover_stale_check():
    """Shown red the same two ways as 172's: a planted entry that writes a handover document, and
    the handover with its stale check taken out."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    planted = source + ("\n\ndef hand_it_over_anyway(room_folder, card):\n"
                        "    write_document(room_folder, 'x.md', card.proposal[DOCUMENTS]['y'])\n")
    assert unguarded_routes(planted, set(), STALE_CHECK,
                            _writes_a_handover_document) == ["hand_it_over_anyway"]
    unchecked = source.replace(f"if {STALE_CHECK}(room_folder, card):", "if False:")
    assert unchecked != source, "the stale check is not spelled where this test expects it"
    assert {"accept_handover", "answer"} <= set(unguarded_routes(
        unchecked, _called_from_outside(), STALE_CHECK, _writes_a_handover_document))


def test_the_handover_checks_then_moves_the_run_then_writes_the_documents():
    """The order `accept_handover`'s docstring gives, both tickets held in one line of calls: 180's
    stale check first, so an answer on a revision the run moved past writes nothing at all; then
    208's compare-and-set on the run, so a press that lost the race writes no document either; then
    the two documents, the only movement a stop can now leave undone (207 re-renders it)."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    functions, _ = _call_graph(ast.parse(source))
    writers = {name for name, function in functions.items()
               if any(_writes_a_handover_document(call) for call in _calls(function))}
    order = [call.func.id for call in sorted(_calls(functions["accept_handover"]),
                                             key=lambda call: call.lineno)
             if isinstance(call.func, ast.Name)
             and call.func.id in {STALE_CHECK, "_save", "write_document", *writers}]
    assert len(order) == 3, order
    assert order[0] == STALE_CHECK, order
    assert order[1] == "_save", order
    assert order[2] in writers, order


def test_the_census_finds_a_route_planted_past_the_check():
    """Shown red against a planted route: a new entry that saves the record without the check, and
    the real door with its check taken out, are both named — neither was typed into the census."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    planted = source + ("\n\ndef save_it_anyway(room_folder, card):\n"
                        "    return _land(room_folder, card)\n")
    assert unguarded_routes(planted, set()) == ["save_it_anyway"]
    unchecked = source.replace(f"if {REFUSAL_CHECK}(card):", "if False:")
    assert unchecked != source, "the check is not spelled where this test expects it"
    assert "answer" in unguarded_routes(unchecked, _called_from_outside())


#: A copy mutmut generates, in mutmut's own spelling: the untouched `..._orig`, a numbered mutant,
#: and one of the numbered copies of a guard, which reorders the very check this census reads.
MUTMUT_COPIES = (
    "\n\ndef x__land__mutmut_orig(room_folder, card):\n"
    "    return _land(room_folder, card)\n"
    "\n\ndef x__land__mutmut_1(room_folder, card):\n"
    "    return _land(room_folder, card)\n"
    "\n\ndef x_answer__mutmut_9(room_folder, card):\n"
    "    _land(room_folder, card)\n"
    f"    if {REFUSAL_CHECK}(card):\n"
    "        return None\n"
    "    return None\n")


def test_the_census_passes_over_mutmuts_generated_copies():
    """Shown red against mutmut's `mutants/` tree, where every function is trampolined and its
    copies carry the write: the copies are mutmut's spelling of a route already censused under its
    real name, so naming them again failed the census on every branch and checked no mutant."""
    source = Path(walk.__file__).read_text(encoding="utf-8")

    assert unguarded_routes(source + MUTMUT_COPIES, _called_from_outside()) == []


def test_the_census_still_finds_a_real_route_beside_mutmuts_copies():
    """And the skip is mutmut's names alone: a real unguarded entry standing among them is named."""
    source = Path(walk.__file__).read_text(encoding="utf-8")
    planted = source + MUTMUT_COPIES + ("\n\ndef save_it_anyway(room_folder, card):\n"
                                        "    return _land(room_folder, card)\n")

    assert unguarded_routes(planted, set()) == ["save_it_anyway"]


def test_an_answer_that_picks_none_of_two_interviews_binds_nothing_and_writes_nothing(tmp_path):
    """Stage 2 with two interviews offered is waiting for the manager to choose between them, so an
    answer that names neither is not a choice: the same card comes back and nothing is written.

    Ticket 164: this branch of stage 2's answer was reached only by the demo skin's features
    scenarios, which that ticket retired; it is pinned here, where the walk is."""
    folder = at_stage_2(tmp_path)
    interviewed(folder, home=OWNER_INTERVIEWS, name="slaughter-interview-transcript.md")
    card = walk.current(folder, "Slaughter")
    assert card.stage == STAGE_2 and len(card.interviews) == 2, "not the choice this test needs"
    before = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}

    handed = walk.answer(folder, "Slaughter", ENDORSED, card.revision)

    assert handed == (card,), "an answer that chose nothing moved the walk"
    assert {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()} == before


def test_an_activity_that_is_not_an_object_names_no_turn(tmp_path):
    """The referee refuses a malformed activity; reading its turns first must not crash on it."""
    assert walk.confirmed_turns(tmp_path, {"activities": ["not an activity"]}) == {}


# ── Read off the real tree: what reads the page, and who writes the manager's sentence ───────────
# From two walk files ticket 165's last slice retired, last held at 602cc648:
# `tests/ui/walk/test_stage_4c_the_graph_and_its_receipt.py` step 41 (ticket 17) and
# `tests/ui/walk/test_the_referee_reports_data_and_the_walk_writes_the_prose.py` step 16
# (ticket 26). Found by walking up, so mutmut's rewritten copy is never what is read.


def _product_sources():
    return [path for path in sorted((repo_root() / "src" / "nemo").glob("*.py"))
            if not path.name.startswith("test_")]


def test_nothing_in_the_product_reads_the_page_it_writes():
    reaching = [f"{path.name}:{number}: {line.strip()}"
                for path in _product_sources()
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                if re.search(r"\b(PAGE|PAGE_EVIDENCE)\b|index\.html|graph-v1", line)
                and "write_file" not in line and not line.lstrip().startswith(("#", '"', "PAGE"))]
    assert reaching == [], (
        f"step 41: the source reaches the page other than to write it: {reaching}")


def test_the_walk_holds_the_managers_sentence_and_the_referee_holds_none_of_it():
    source = repo_root() / "src" / "nemo"
    assert "REFUSAL_SAYS" in (source / "walk.py").read_text(encoding="utf-8"), (
        "step 16: the refusal's wording does not live in `nemo.walk`")
    said_by_referee = (source / "referee.py").read_text(encoding="utf-8")
    for kind, sentence in REFUSAL_SAYS.items():
        long = [part.strip() for part in re.split(r"\{[a-z_]+\}", sentence)
                if len(part.strip()) > 15]
        assert long, f"step 16: {kind}'s sentence is all parts, so there is nothing to compare"
        for part in long:
            assert part not in said_by_referee, (
                f"step 16: `nemo.referee` still holds the manager's wording for {kind}: {part!r}")


# ── 247: how many of the five stages a run has done, for the workspace page ──


def signed(tmp_path):
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    return folder, None


@pytest.mark.parametrize(("at", "done"), [
    (stage_1_card, 0), (stage_2_card, 1), (stage_3_card, 2), (stage_4_card, 3), (stage_5_card, 4),
    (accepted_handover, 4), (signed, 5)])
def test_stages_done_reads_a_real_walk_off_its_own_run_file(tmp_path, at, done):
    """Ticket 247: the workspace ticks what is done and marks the next stage, read off the run the
    walk itself wrote. Accepting the handover is not signing it: stage 5 is done at the
    signature."""
    folder, _card = at(tmp_path)
    assert walk.stages_done(read_record(folder, run_file("Slaughter"))) == done


AGREED_1 = {AT_STAGE: walk.STAGE, "decided": "yes"}


@pytest.mark.parametrize(("run", "done"), [
    (None, 0),
    ({}, 0),
    ({STATUS: walk.AWAITING_HUMAN, DECISIONS: []}, 0),
    ({DECISIONS: [{AT_STAGE: walk.STAGE, "decided": "no"}]}, 0),
    ({DECISIONS: [AGREED_1]}, 1),
    # a later stage's mark without the one before it is not progress: the walk never skips one
    ({DECISIONS: [{AT_STAGE: walk.STAGE_3}], "transcript": {"path": "x"}}, 0),
    ({DECISIONS: [AGREED_1, {AT_STAGE: walk.STAGE_3}]}, 1),
    ({DECISIONS: [AGREED_1], "transcript": {"path": "x"}}, 2),
    ({DECISIONS: [AGREED_1, {AT_STAGE: walk.STAGE_3}], "transcript": {"path": "x"}}, 3),
    # stage 4 is done when the picture is bound, not when the record is merely saved (ADR-0010)
    ({DECISIONS: [AGREED_1, {AT_STAGE: walk.STAGE_3}, {AT_STAGE: walk.STAGE_4}],
      "transcript": {"path": "x"}, walk.RECEIPT: None}, 3),
    ({DECISIONS: [AGREED_1, {AT_STAGE: walk.STAGE_3}, {AT_STAGE: walk.STAGE_4}],
      "transcript": {"path": "x"}, walk.RECEIPT: {"record_sha": "x"}}, 4),
    ({STATUS: walk.REVIEWED,
      DECISIONS: [AGREED_1, {AT_STAGE: walk.STAGE_3}, {AT_STAGE: walk.STAGE_4}],
      "transcript": {"path": "x"}, walk.RECEIPT: {"record_sha": "x"}}, 4),
    ({STATUS: CLOSED, DECISIONS: []}, 5),
])
def test_stages_done_counts_only_stages_answered_in_order(run, done):
    assert walk.stages_done(run) == done


# ── reopen: back to step 3 until the signature (ticket 241 slice 1, D3) ──────
#
# The owner's ruling of 2026-09-17: the point of no return is the signature, not step 4. The phone
# has reopened walks since t71 by writing the run file itself; these pin what it does, now that
# the walk is the one writer of its own run.

#: What the manager typed to name his reservation at step 3.
REOPENED_NAMING = "the RTO assumes the second line is staffed"


def closed_step_3(tmp_path, answer=ENDORSED, naming=None):
    """A room past the close of step 3, and the run as it stood just before that close."""
    folder, stage_2 = bound(tmp_path, SCORED)
    stage_3 = onward(folder, stage_2)[0]
    at_close = run_of(folder)
    said(folder, stage_3, answer)
    if naming is not None:
        typed(folder, naming)
    return folder, at_close


def accepted_again(folder):
    """Step 4 accepted on the card the walk serves now."""
    return said(folder, walk.current(folder, "Slaughter"), ENDORSED)


def test_a_reopen_puts_the_run_back_as_it_stood_when_step_3_closed(tmp_path):
    folder, at_close = closed_step_3(tmp_path)
    accepted_again(folder)
    before = run_of(folder)
    assert _record_accepted(before)

    reopened = walk.reopen(folder, "Slaughter")

    saved = run_of(folder)
    assert reopened == saved
    assert _without_revision(saved) == {**_without_revision(at_close), walk.CARRIED: []}
    assert walk.current(folder, "Slaughter").stage == STAGE_3


def test_a_reopen_moves_the_revision_on_and_never_back(tmp_path):
    """The run is saved through its own compare-and-set, so a card read before the reopen is stale
    after it, as after any other write."""
    folder, _at_close = closed_step_3(tmp_path)
    accepted_again(folder)
    before = run_of(folder)["revision"]

    walk.reopen(folder, "Slaughter")

    assert run_of(folder)["revision"] == before + 1


def test_a_reopen_after_the_handover_was_accepted_still_goes_back(tmp_path):
    folder, _answered = accepted_handover(tmp_path)
    assert run_of(folder)["status"] == REVIEWED

    walk.reopen(folder, "Slaughter")

    assert walk.current(folder, "Slaughter").stage == STAGE_3
    assert run_of(folder)["status"] == AWAITING_HUMAN


def test_the_reservations_a_reopen_undoes_are_carried_and_the_snapshots_own_are_not(tmp_path):
    """t71: restoring the run to step 3 would drop every reservation made at steps 3 to 5."""
    folder, at_close = closed_step_3(tmp_path, "needs discussion", REOPENED_NAMING)
    accepted_again(folder)

    walk.reopen(folder, "Slaughter")

    saved = run_of(folder)
    assert saved[walk.CARRIED] == [{AT_STAGE: STAGE_3, "naming": REOPENED_NAMING}]
    assert saved[DECISIONS] == at_close[DECISIONS]


def test_a_second_reopen_keeps_what_the_first_one_carried_once(tmp_path):
    """The reservation stands until he signs, however often he goes back: never dropped, never
    doubled. (The phone's own reopen dropped it on the second go, because the snapshot it restored
    already carried it and it was counted as the snapshot's own.)"""
    folder, _at_close = closed_step_3(tmp_path, "needs discussion", REOPENED_NAMING)
    accepted_again(folder)
    walk.reopen(folder, "Slaughter")
    said(folder, walk.current(folder, "Slaughter"), ENDORSED)
    accepted_again(folder)

    walk.reopen(folder, "Slaughter")

    assert run_of(folder)[walk.CARRIED] == [{AT_STAGE: STAGE_3, "naming": REOPENED_NAMING}]


def test_a_reopen_straight_after_a_reopen_still_carries_the_reservation(tmp_path):
    """Back at step 3 and nothing closed since: the run carries what the first reopen undid, and
    the second one must not lose it to the older snapshot."""
    folder, _at_close = closed_step_3(tmp_path, "needs discussion", REOPENED_NAMING)
    accepted_again(folder)
    walk.reopen(folder, "Slaughter")

    walk.reopen(folder, "Slaughter")

    assert run_of(folder)[walk.CARRIED] == [{AT_STAGE: STAGE_3, "naming": REOPENED_NAMING}]


def test_a_reopen_never_undoes_the_notes_a_tool_call_left(tmp_path):
    """t71b: the audit trail of the notes the model supplied is kept whatever is undone."""
    folder, _at_close = closed_step_3(tmp_path)
    accepted_again(folder)
    run = run_of(folder)
    notes = [{"item": "c1", "note": "the register is older", "by": "the model", "at": "10:00:00"}]
    write_record(folder, run_file("Slaughter"), {**run, walk.MODEL_NOTES: notes}, run["revision"])

    walk.reopen(folder, "Slaughter")

    assert run_of(folder)[walk.MODEL_NOTES] == notes


def test_a_reopen_with_no_notes_adds_no_notes(tmp_path):
    folder, _at_close = closed_step_3(tmp_path)
    accepted_again(folder)

    walk.reopen(folder, "Slaughter")

    assert walk.MODEL_NOTES not in run_of(folder)


def _reopened_nothing(folder):
    before = sorted((path, path.read_bytes()) for path in folder.rglob("*") if path.is_file())
    assert walk.reopen(folder, "Slaughter") is None
    assert sorted((path, path.read_bytes()) for path in folder.rglob("*") if path.is_file()) \
        == before


def test_a_signed_walk_does_not_reopen(tmp_path):
    folder, _none = signed(tmp_path)
    _reopened_nothing(folder)


def test_a_walk_whose_step_3_never_closed_has_nothing_to_go_back_to(tmp_path):
    folder, _card = reached(tmp_path)
    _reopened_nothing(folder)


def test_a_reopen_waits_while_a_reservation_waits_for_its_words(tmp_path):
    """t71 fix 2: a reopen then would drop the reservation he is about to name."""
    folder, _at_close = closed_step_3(tmp_path, "needs discussion")
    _reopened_nothing(folder)


def test_a_room_nobody_walked_has_nothing_to_reopen(tmp_path):
    _reopened_nothing(room(tmp_path))


# ── ticket 256: a change referred to its resource owner ─────────────────────────────────────────
#: his referral as `walk.refer` writes it: the resource, the item with last year's value, his line
REFERRAL_ROW = {
    "refers": "Microsoft 365, RTO for slaughter (last year: 72 h): the new cloud contract",
    "to": "Owner of Microsoft 365"}


def referred(folder, words="the new cloud contract", resource="Microsoft 365",
             item="RTO for slaughter (last year: 72 h)"):
    return walk.refer(folder, "Slaughter", resource, item, words)


def test_a_refer_writes_one_pending_referral_in_the_resource_item_and_his_words(tmp_path):
    folder = prepared_room(tmp_path)
    assert referred(folder) is True
    assert run_of(folder)[PENDING_REFERRALS] == [REFERRAL_ROW]


def test_the_same_referral_twice_writes_one_row(tmp_path):
    folder = prepared_room(tmp_path)
    referred(folder)
    revision = run_of(folder)["revision"]
    assert referred(folder) is True
    assert run_of(folder)[PENDING_REFERRALS] == [REFERRAL_ROW]
    assert run_of(folder)["revision"] == revision, "a repeat moved the run"


def test_a_second_referral_is_appended_after_the_first(tmp_path):
    folder = prepared_room(tmp_path)
    referred(folder)
    referred(folder, words="the backup site")
    assert [row["refers"] for row in run_of(folder)[PENDING_REFERRALS]] == [
        REFERRAL_ROW["refers"],
        REFERRAL_ROW["refers"].replace("the new cloud contract", "the backup site")]


def test_his_words_are_kept_as_typed_inside_and_trimmed_at_the_ends(tmp_path):
    folder = prepared_room(tmp_path)
    referred(folder, words="  the new  cloud contract \n")
    assert run_of(folder)[PENDING_REFERRALS][0]["refers"].endswith(": the new  cloud contract")


@pytest.mark.parametrize("words", ["", "   \n"])
def test_a_refer_with_no_words_writes_nothing(tmp_path, words):
    folder = prepared_room(tmp_path)
    before = run_of(folder)
    assert referred(folder, words=words) is False
    assert run_of(folder) == before


def test_a_refer_with_no_run_on_file_writes_nothing(tmp_path):
    folder = prepared_room(tmp_path)
    assert walk.refer(folder, "Sales", "Microsoft 365", "RTO", "words") is False
    assert read_record(folder, run_file("Sales")) is None


@pytest.mark.parametrize("status", [REVIEWED, CLOSED])
def test_a_refer_on_a_reviewed_or_closed_run_is_refused(tmp_path, status):
    folder = prepared_room(tmp_path, status=status)
    before = run_of(folder)
    assert referred(folder) is False
    assert run_of(folder) == before


def test_a_refer_after_acceptance_leaves_the_record_sha_alone(tmp_path):
    folder, _card = accepted_handover(tmp_path)
    before, record = run_of(folder), read_record(folder, walk.record_file("Slaughter"))
    assert before[STATUS] == REVIEWED
    assert referred(folder) is False
    assert run_of(folder) == before
    assert fingerprint(read_record(folder, walk.record_file("Slaughter"))) == fingerprint(record)


def test_a_refer_after_the_signature_is_refused(tmp_path):
    folder, card = signing(tmp_path)
    walk.sign(folder, card, "Torsten Ahlgrim", "Head of Slaughter")
    before = run_of(folder)
    assert before[STATUS] == CLOSED
    assert referred(folder) is False
    assert run_of(folder) == before


def test_a_refer_that_lost_the_race_writes_nothing(tmp_path, monkeypatch):
    folder = prepared_room(tmp_path)
    monkeypatch.setattr(walk, "_save", lambda *_args: None)
    assert referred(folder) is False


def test_pending_referrals_land_in_risk_referrals_with_the_record(tmp_path):
    folder, card = stage_4_card(tmp_path)
    referred(folder)
    card = walk.current(folder, "Slaughter")
    walk.answer(folder, "Slaughter", walk.ENDORSED, card.revision)
    assert read_record(folder, walk.record_file("Slaughter"))[REFERRALS] == [REFERRAL_ROW]


def test_a_run_with_no_pending_referral_builds_the_record_it_always_did(tmp_path):
    run = {"run_id": "r", "process": "P", "transcript": {"path": "t"}}
    assert REFERRALS not in build_record(run, {})
    assert build_record({**run, PENDING_REFERRALS: [REFERRAL_ROW]}, {})[REFERRALS] == [REFERRAL_ROW]
    assert build_record({**run, PENDING_REFERRALS: []}, {}) == build_record(run, {})


def test_the_record_holds_a_copy_of_the_pending_list(tmp_path):
    pending = [REFERRAL_ROW]
    built = build_record({"run_id": "r", "process": "P", "transcript": {"path": "t"},
                       PENDING_REFERRALS: pending}, {})
    pending.append({"refers": "x", "to": "y"})
    assert built[REFERRALS] == [REFERRAL_ROW]


def test_a_refer_never_touches_another_rooms_run(tmp_path):
    first = prepared_room(tmp_path / "a")
    second = prepared_room(tmp_path / "b")
    referred(first)
    assert PENDING_REFERRALS not in run_of(second)


# ── a band MTPD's refusal says its edge, as the phone says it (t74, 241 slice 3) ─────────────
#: What the phone's `_patched_refusal_says` said on 3c9b6779 for the referee's own refusal.
PHONE_BAND_REFUSAL = (
    "A0 is to be back within 4 h, and being down becomes unacceptable at 0–4 h, so the target is "
    "not inside it. Go back to the owner and either bring the target forward, or have them say in "
    "as many words that they accept the gap. 0–4 h counts up to its upper edge, 4 h, and a target "
    "of 4 h is not before it.")
PHONE_SINGLE_REFUSAL = (
    "A0 is to be back within 25 h, and being down becomes unacceptable at 24 h, so the target is "
    "not inside it. Go back to the owner and either bring the target forward, or have them say in "
    "as many words that they accept the gap.")


@pytest.mark.parametrize("target, mtpd, says", [("4 h", "0–4 h", PHONE_BAND_REFUSAL),
                                                ("25 h", "24 h", PHONE_SINGLE_REFUSAL)])
def test_a_band_mtpd_refusal_says_the_edge_the_target_was_held_against(target, mtpd, says):
    """The referee's refusal, worded in-process: a band names its upper edge, a single duration
    has no edge to name."""
    verdict = referee.Verdict()
    referee._review_recovery(verdict, "A0", {"recovery_target": target}, mtpd)
    [rejection] = verdict.rejections
    assert walk._refusal_says(rejection) == says


def test_the_edge_sentence_reads_each_part_as_the_manager_reads_it():
    rejection = refusal.Rejection(refusal.TARGET_OUTSIDE_MTPD, "", activity="A0",
                                  target=("2 h", "6 h"), mtpd="0–4 h", edge="4 h")
    assert walk._refusal_says(rejection).endswith(
        f" 0–4 h counts up to its upper edge, 4 h, and a target of {_listed(['2 h', '6 h'])} is "
        "not before it.")


# ── ticket 318 (ADR-0047): his tap adds a dependency to this room's register only ──────────────
ON = "2026-10-05"


def _chat_room(tmp_path: Path, register: dict | None = None) -> Path:
    """A room holding only a register: two resources, one at a site, one Site item."""
    room = tmp_path / "room"
    (room / "03_Dependencies").mkdir(parents=True)
    (room / walk.REGISTER).write_text(json.dumps(register if register is not None else {
        "synthetic": True,
        "csb-erp": {"asset_id": "csb-erp", "name": "CSB ERP", "site": "Marschkamp", "rto": "72 h",
                    "consumers": [{"department": "production", "activity": "Production",
                                   "rto": "72 h"}]},
        "corporate-network": {"asset_id": "corporate-network", "name": "Corporate network",
                              "consumers": []},
        "wilster": {"asset_id": "wilster", "name": "Wilstermarsch", "asset_type": "Site",
                    "consumers": []}}, indent=2), encoding="utf-8")
    return room


def _reg(room: Path) -> dict:
    return json.loads((room / walk.REGISTER).read_text(encoding="utf-8"))


def test_318_a_new_name_writes_one_asset_and_one_consumer_row_marked_with_no_figure(tmp_path):
    room = _chat_room(tmp_path)
    before = _reg(room)
    assert walk.add_dependency(room, "order-picking", "Order picking", "  label printer ", ON) \
        == "label-printer"
    after = _reg(room)
    assert after["label-printer"] == {
        "asset_id": "label-printer", "name": "label printer", walk.ADDED_IN_CHAT: ON,
        "consumers": [{"department": "order-picking", "activity": "Order picking",
                       walk.ADDED_IN_CHAT: ON}]}
    assert {k: v for k, v in after.items() if k != "label-printer"} == before
    assert list(after)[-1] == "label-printer"


def test_318_a_name_matching_an_asset_case_and_spacing_aside_links_to_it(tmp_path):
    room = _chat_room(tmp_path)
    assert walk.add_dependency(room, "order-picking", "Order picking", "csb   erp", ON) == "csb-erp"
    after = _reg(room)
    assert after["csb-erp"]["consumers"][-1] == {
        "department": "order-picking", "activity": "Order picking", walk.ADDED_IN_CHAT: ON}
    assert len(after["csb-erp"]["consumers"]) == 2 and len(after) == 4
    assert walk.add_dependency(room, "order-picking", "Order picking", "CSBERP", ON) == "csb-erp"
    assert len(_reg(room)["csb-erp"]["consumers"]) == 2


def test_318_the_same_add_twice_writes_once(tmp_path):
    room = _chat_room(tmp_path)
    walk.add_dependency(room, "order-picking", "Order picking", "label printer", ON)
    once = (room / walk.REGISTER).read_bytes()
    assert walk.add_dependency(room, "order-picking", "Order picking", "Label Printer",
                               "2026-10-06") == "label-printer"
    assert (room / walk.REGISTER).read_bytes() == once


def test_318_an_activity_already_using_the_asset_is_not_written_again(tmp_path):
    room = _chat_room(tmp_path)
    before = (room / walk.REGISTER).read_bytes()
    assert walk.add_dependency(room, "production", "Production", "CSB ERP", ON) == "csb-erp"
    assert (room / walk.REGISTER).read_bytes() == before


def test_318_an_empty_name_or_activity_writes_nothing(tmp_path):
    room = _chat_room(tmp_path)
    before = (room / walk.REGISTER).read_bytes()
    assert walk.add_dependency(room, "order-picking", "Order picking", "   ", ON) is None
    assert walk.add_dependency(room, " ", "Order picking", "label printer", ON) is None
    assert (room / walk.REGISTER).read_bytes() == before


def test_318_a_new_id_never_takes_another_assets_id(tmp_path):
    room = _chat_room(tmp_path, {"label-printer": {"asset_id": "label-printer",
                                                   "name": "Label printer (old)"}})
    assert walk.add_dependency(room, "a", "A", "Label printer", ON) == "label-printer-2"
    assert walk.add_dependency(room, "a", "A", "Label-printer!", ON) == "label-printer-3"
    assert _reg(room)["label-printer"] == {"asset_id": "label-printer",
                                           "name": "Label printer (old)"}


def test_318_a_name_with_no_letters_takes_an_id_of_its_own(tmp_path):
    room = _chat_room(tmp_path)
    assert walk.add_dependency(room, "a", "A", "%%", ON) == "added-in-chat"
    assert _reg(room)["added-in-chat"]["name"] == "%%"


def test_318_the_register_is_written_as_the_seed_writes_it(tmp_path):
    room = _chat_room(tmp_path)
    walk.add_dependency(room, "a", "A", "Kühlhaus", ON)
    text = (room / walk.REGISTER).read_text(encoding="utf-8")
    assert text == json.dumps(_reg(room), indent=2, ensure_ascii=False) + "\n"
    assert "Kühlhaus" in text


def test_318_a_room_with_no_register_gets_none_written(tmp_path):
    room = tmp_path / "bare"
    room.mkdir()
    assert walk.add_dependency(room, "a", "A", "label printer", ON) is None
    assert not (room / walk.REGISTER).exists()


def test_318_the_sites_are_the_site_items_and_the_site_fields(tmp_path):
    assert walk.sites(_reg(_chat_room(tmp_path))) == ["Marschkamp", "Wilstermarsch"]
    assert walk.sites({"x": "not a row", "y": {"site": " "}, "z": {"asset_type": "Site"}}) == []


def test_318_stands_on_and_at_write_onto_the_added_row_only(tmp_path):
    room = _chat_room(tmp_path)
    aid = walk.add_dependency(room, "production", "Production", "CSB standby", ON)
    assert walk.link_dependency(room, aid, ON, stands_on="corporate-network")
    assert walk.link_dependency(room, aid, ON, at="wilstermarsch")
    row = _reg(room)[aid]
    assert row["depends_on"] == ["corporate-network"]
    assert row["depends_on_evidence"] == [{"asset_id": "corporate-network",
                                           walk.ADDED_IN_CHAT: ON}]
    assert row["site"] == "Wilstermarsch"
    assert row[walk.ADDED_IN_CHAT] == ON


def test_318_a_link_tapped_twice_writes_once(tmp_path):
    room = _chat_room(tmp_path)
    aid = walk.add_dependency(room, "production", "Production", "CSB standby", ON)
    walk.link_dependency(room, aid, ON, stands_on="corporate-network")
    walk.link_dependency(room, aid, ON, at="Marschkamp")
    once = (room / walk.REGISTER).read_bytes()
    assert walk.link_dependency(room, aid, ON, stands_on="corporate-network")
    assert walk.link_dependency(room, aid, ON, at="marschkamp")
    assert (room / walk.REGISTER).read_bytes() == once


def test_318_a_link_off_the_map_or_onto_a_seed_row_is_refused(tmp_path):
    room = _chat_room(tmp_path)
    aid = walk.add_dependency(room, "production", "Production", "CSB standby", ON)
    walk.link_dependency(room, aid, ON, at="Marschkamp")
    before = (room / walk.REGISTER).read_bytes()
    assert not walk.link_dependency(room, aid, ON, stands_on="the moon")
    assert not walk.link_dependency(room, aid, ON, stands_on="synthetic")
    assert not walk.link_dependency(room, aid, ON, stands_on=aid)
    assert not walk.link_dependency(room, aid, ON, at="Hamburg")
    assert not walk.link_dependency(room, aid, ON, at="Wilstermarsch")  # one site, never two
    assert not walk.link_dependency(room, aid, ON)
    assert not walk.link_dependency(room, "csb-erp", ON, stands_on="corporate-network")
    assert not walk.link_dependency(room, "nothing-here", ON, at="Marschkamp")
    assert (room / walk.REGISTER).read_bytes() == before


def test_318_an_asset_with_no_consumers_list_gets_one_with_his_row(tmp_path):
    """An asset row the register holds without a `consumers` list (a hand-written row) gets one,
    holding his row, and a row with no name is never the one matched."""
    room = _chat_room(tmp_path, {
        "label-printer": {"asset_id": "label-printer", "name": "Label printer"},
        "nameless": {"asset_id": "nameless"}})
    assert walk.add_dependency(room, "order-picking", "Order picking", "label printer",
                               ON) == "label-printer"
    assert _reg(room)["label-printer"]["consumers"] == [
        {"department": "order-picking", "activity": "Order picking", walk.ADDED_IN_CHAT: ON}]
    assert "consumers" not in _reg(room)["nameless"]


def test_318_a_new_assets_id_is_its_slug_when_free(tmp_path):
    room = _chat_room(tmp_path)
    assert walk.add_dependency(room, "order-picking", "Order picking", "Label printer",
                               ON) == "label-printer"
    assert "label-printer-2" not in _reg(room)
