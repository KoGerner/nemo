"""The steps behind `features/the-room-door.feature`, `features/the-ask-lane.feature`,
`features/the-walking-skeleton.feature`, `features/the-real-skin-under-test.feature` and
`features/the-transcript-already-in-the-room.feature`.

They live at the root because `features/test_features.py` is the specifier's file and defines no
steps, and pytest-bdd resolves steps from the conftests above the scenario's module.

Every step drives `nemo.door` — the decisions a skin's auth callback, its CONNECT handler and a
sweep timer make — or `nemo.ask` down to its HTTP layer over recorded bodies, or `nemo.walk`,
which is the walk itself, or the phone app itself (`skin/PROTOTYPE_conversation_app.py`) over
`skin_harness.py`'s stand-in for Chainlit and its scripted lane (ticket 164), or reads the
facilitator's note the room-door story delivers (its unit file went to the archive in 166). What a
browser and Chainlit do around those decisions is measured in `tests/isolation/`, against the
scratch venv, because Chainlit is not a nemo dependency (ADR-0001).

The skeleton's steps hold one discipline of their own: **a process name reaching `nemo.walk` may
only ever be a string the room offered as a button.** `_press_process` and `_press_button` are the
only ways a step names one, and both assert it, so "typed inputs: 0" is a property the steps
enforce rather than a claim they make.
"""

import concurrent.futures
import hashlib
import importlib
import importlib.util
import inspect
import json
import os
import re
import shutil
import string
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import uuid
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

import nemo.ask
import nemo.card
import skin_harness
from nemo import bia, figures, handover, impact, referee, refusal, turn_file, views, walk
from nemo.ask import (
    CORPUS_RELEASE,
    GUIDANCE_URL,
    NOT_COVERED,
    NOTHING_MATCHED,
    RELEASE_AGREES,
    SOURCES,
    UNAVAILABLE,
    WRONG_RELEASE,
    Answer,
    ask,
    call_guidance,
    release_note,
    uncovered_standard,
)
from nemo.bia import StaleRecord
from nemo.card import CardGeneratorBug, render, untraceable
from nemo.conduct import CARD, NOT_STARTED, STOPPED, TURNS, Turn, conduct, transcript
from nemo.door import (
    PREFIX_SEGMENT,
    SWEEP_AGE_SECONDS,
    admit,
    authorise,
    identity_from_link,
    sweep,
)
from nemo.evidence import NOT_STATED, UNKNOWN
from nemo.figures import MTPD_SAYS, NO_MTPD_SAYS
from nemo.figures import listed as _listed
from nemo.interview import INTERVIEWS, OWNER_INTERVIEWS, held
from nemo.lane import LANE_URL, LaneUnavailable, call_lane, post
from nemo.record import (
    ACCEPTED,
    ACTIVITIES,
    AT_TIME,
    BY_WHEN,
    CAPACITY,
    DATA_SETS,
    DEPARTMENT,
    DEPENDENCIES,
    DEPT,
    EVIDENCE,
    FINDINGS,
    IMPACT_GRID,
    LENS,
    MBCO,
    MTPD,
    NAME,
    ON_CARD,
    OPEN_ITEMS,
    QUOTE,
    RECOVERY_TARGET,
    REFERRALS,
    REFERRED_TO,
    REFERS,
    REFUSALS,
    RESOURCES,
    RPO,
    SIGNATURE,
    SOURCE_PATH,
    WORKAROUND,
    fingerprint,
)
from nemo.record import METHOD as RECORD_METHOD
from nemo.record import NAMING as NAMING_FIELD
from nemo.room_code import UNAUTHORISED, Refused
from nemo.room_store import Shrunk, read_record, write_document, write_record
from nemo.text import norm
from nemo.walk import (
    ACCEPTING,
    AGREE,
    AWAITING_HUMAN,
    BIA,
    BOUND,
    CHECKED,
    CHECKED_NOTE,
    CLOSED,
    DECISION_4,
    DECISION_CHOSEN,
    DECISION_SIGN,
    DOCUMENTS,
    DRAWN,
    ENDORSED,
    GRADIENT,
    HEADING,
    HOLD_IT_NOW,
    LEAD,
    METHOD,
    METHOD_PARAMETERS,
    NAMING,
    OPEN_4,
    OVERTAKEN,
    PICTURE_DRAWN,
    RECEIPT,
    RECORD_NAME,
    RECORD_SAVED,
    REFUSAL_SAYS,
    REFUSED,
    REGISTER,
    RESUMED,
    REVIEWED,
    RULE_4,
    RUNS,
    SAVED_NOT_FINISHED,
    SCHEMA,
    SETTLED,
    STAGE,
    STAGE_2,
    STAGE_3,
    STAGE_4,
    STAGE_5,
    TAKEN,
    UNNAMED,
    NotDrawnYet,
    answer,
    check_draft,
    checked_note,
    chosen,
    handover_card,
    held_interview,
    in_progress,
    interview_findings,
    interview_path,
    mint_room,
    move_past_stage_4,
    namings,
    onward,
    open_bia,
    processes,
    record_card,
    record_file,
    refused_says,
    report,
    resume,
    run_file,
    sign,
    signature_card,
    where_it_stands,
)

REPO = Path(__file__).parent
FACILITATOR_NOTE = REPO / "docs" / "facilitator-note.md"
SESSION_ID = "1a4f7c6e-0b2d-4e5a-9c3b-8d7e6f5a4b3c"


def without_telemetry(decision):
    """One decision with its telemetry taken off. A scenario about what a manager decided should
    not have to restate when he decided it, what he was looking at and what was refused — those
    have their own tests in `src/nemo/test_walk.py`."""
    return {key: value for key, value in decision.items()
            if key not in (AT_TIME, ON_CARD, REFUSALS)}


@pytest.fixture
def ctx(tmp_path):
    """The narrator is in `demo-1` unless a step moves them, and owns one scratch tree."""
    return {"room": "demo-1", "tmp": tmp_path, "fired": []}


def _attempt(ctx, owner_room, run=None):
    try:
        authorise(ctx["room"], owner_room)
    except Refused as refusal:
        ctx["refusal"] = refusal
        return
    if run is not None:
        run()


# ------------------------------------------------------------------ my room link


@given(parsers.parse('room "{first}" and room "{second}" both hold files'))
def _rooms_hold_files(ctx, first, second):
    for room in (first, second):
        (ctx["tmp"] / room).mkdir()
        (ctx["tmp"] / room / "seed.txt").write_text(f"{room}'s own file")


# Being in a room, arriving in one and opening a second in the same profile are one act: a link is
# scanned, its room code becomes the identity, and whatever the profile held before is replaced.
@given(parsers.parse('I am in room "{room}"'))
@when(parsers.parse('I open the link for "{room}"'))
@when(parsers.parse('I open the link for "{room}" in the same profile'))
@when(parsers.parse('I open the link for "{room}", which has no folder'))
def _i_open_the_link_for(ctx, skin, capsys, room):
    """Claim a room the way a scanned code does: one link in, one identity out, nothing typed.

    How much of the door runs is `_the_rooms_folder_is_on_disk`'s call, and its reason.
    """
    if _the_rooms_folder_is_on_disk(ctx):
        _present(ctx, skin, capsys, f"/demo/r/{room}")
        return
    ctx["profile"] = {"access_token": identity_from_link(f"https://demo.ai4bcm.org/r/{room}")}
    ctx["room"] = ctx["profile"]["access_token"]


@then(parsers.parse('I am in room "{room}" without being asked for an account or a password'))
def _i_am_in_room_with_nothing_typed(ctx, room):
    assert ctx["room"] == room
    assert list(ctx["profile"]) == ["access_token"], "something other than the link was needed"
    authorise(ctx["room"], room)


@then(parsers.parse('the demo skin holds "{room}" as my identity'))
def _the_skin_holds_the_room(ctx, room):
    assert ctx["profile"]["access_token"] == room


# ---------------------------------------------------------- another room's things


@when(parsers.parse('I request a file belonging to room "{room}" over an HTTP GET'))
def _i_request_another_rooms_file(ctx, room):
    _attempt(ctx, room)


@when(parsers.parse('I post an action belonging to room "{room}"'))
def _i_post_another_rooms_action(ctx, room):
    _attempt(ctx, room, run=lambda: ctx["fired"].append(room))


@then(parsers.parse("I am refused with {status:d}"))
def _i_am_refused_with(ctx, status):
    assert ctx["refusal"].status == status


@then(parsers.parse("room \"{room}\"'s callback did not run"))
def _the_callback_did_not_run(ctx, room):
    assert room not in ctx["fired"]


# --------------------------------------------------------------------- the socket


@given(parsers.parse('room "{room}" has a live socket'))
def _room_has_a_live_socket(ctx, room):
    ctx["occupants"] = {SESSION_ID: room}


@when(parsers.parse("I connect carrying room \"{room}\"'s session identifier"))
def _i_connect_carrying_another_rooms_session(ctx, room):
    ctx["auth"] = {"sessionId": SESSION_ID}
    _connect(ctx)


@given(parsers.parse('a connect payload whose session identifier is "{value}"'))
def _a_crafted_connect_payload(ctx, value):
    ctx["auth"] = {"sessionId": value}
    ctx["occupants"] = {}
    (ctx["tmp"] / value.rsplit("/", 1)[-1]).mkdir()


@when("the connect handler runs")
def _the_connect_handler_runs(ctx):
    _connect(ctx)


def _connect(ctx):
    try:
        admit(ctx["room"], ctx["auth"], ctx["occupants"])
    except Refused as refusal:
        ctx["refusal"] = refusal


@then("the connection is refused")
def _the_connection_is_refused(ctx):
    assert "refusal" in ctx


@then(parsers.parse("room \"{room}\"'s occupant is not evicted"))
def _the_occupant_is_not_evicted(ctx, room):
    assert ctx["occupants"] == {SESSION_ID: room}


@then("it is refused because the value is not a UUID")
def _refused_for_not_being_a_uuid(ctx):
    assert "is not a UUID" in str(ctx["refusal"])


@then(parsers.parse('the directory "{name}" still exists'))
def _the_directory_still_exists(ctx, name):
    assert (ctx["tmp"] / name).is_dir()


# ---------------------------------------------------------- one profile, one room


@then(parsers.parse('I am in room "{room}" and no longer in room "{former}"'))
def _i_am_in_the_second_room_only(ctx, room, former):
    assert ctx["profile"] == {"access_token": room}
    authorise(ctx["room"], room)
    with pytest.raises(Refused):
        authorise(ctx["room"], former)


# ---------------------------------------------------------------------- the sweep


def _session_directory(ctx, age_seconds):
    directory = ctx["tmp"] / "sessions" / SESSION_ID
    directory.mkdir(parents=True)
    (directory / "upload.txt").write_text("a file the room uploaded")
    stamp = time.time() - age_seconds
    os.utime(directory, (stamp, stamp))
    ctx["session_dir"] = directory


@given("a session directory left behind by a process that was killed")
def _an_orphaned_session_directory(ctx):
    _session_directory(ctx, SWEEP_AGE_SECONDS + 60)


@given("a session directory younger than the sweep's age")
def _a_young_session_directory(ctx):
    _session_directory(ctx, SWEEP_AGE_SECONDS - 60)


@when("the sweep runs")
def _the_sweep_runs(ctx):
    sweep(ctx["tmp"] / "sessions")


@then("that session directory is gone")
def _the_session_directory_is_gone(ctx):
    assert not ctx["session_dir"].exists()


@then("that session directory still holds its files")
def _the_session_directory_still_holds_its_files(ctx):
    assert (ctx["session_dir"] / "upload.txt").read_text() == "a file the room uploaded"


# ------------------------------------------------- the note delivered, not deployed


@given("the note the facilitator reads before the day")
def _the_facilitator_note(ctx):
    ctx["artefact"] = FACILITATOR_NOTE


@when("I read it")
def _i_read_it(ctx):
    ctx["text"] = ctx["artefact"].read_text()


@then("it says two rooms means two browsers or a private window")
def _it_says_two_browsers(ctx):
    assert "two browsers or a private window" in ctx["text"]


# ============================================================================ the ask lane
#
# `features/the-ask-lane.feature`. Every step drives `nemo.ask` down to its HTTP layer, over a
# `urlopen` that answers from the bodies recorded in `tests/fixtures/ask/` — so the two hosts, the
# absent bearer token and the cap are asserted against real requests rather than against a mock of
# the lane. The live run those fixtures came from is `docs/research/ask-lane-live-run.md`.

ASK_FIXTURES = REPO / "tests" / "fixtures" / "ask"
LANE_ANSWER = ASK_FIXTURES / "lane-answer-mtpd.json"
MTPD_QUESTION = "What does the corpus say about setting an MTPD?"


def _recorded_lane_reply() -> dict:
    """The body the real lane returned on 2026-09-12, parsed from the file it was recorded into."""
    reply: dict = json.loads(LANE_ANSWER.read_text())
    return reply


def _recorded_answer() -> str:
    """The answer inside that body — what an answered question puts on screen, word for word."""
    content: str = _recorded_lane_reply()["choices"][0]["message"]["content"]
    return content


#: The release the local guidance repo already stamps, and so the one a bump lands on first.
STALE_RELEASE = "2026.09"

def _names_release(line, release):
    """Whether `line` spells `release` out as a whole tag: "2026.11" is inside "2026.11.1", so a
    substring check would let the withdrawn release pass as named (675). A tag is digits and
    dots, so only a digit beside it, or a dot and a digit, makes it a different tag: "v2026.11.1",
    "2026.11.1.json" and "Release 2026.11.1." all still name it."""
    return re.search(rf"(?<![\d.]){re.escape(release)}(?!\.?\d)", line) is not None


#: Every line of everything a running skin imports that spells the frozen release out: nemo, and
#: the phone app with every module of `skin/` it imports (ticket 164; it was the demo skin's).
FROZEN_NAMED = [
    (path.name, line.strip())
    for path in [*sorted((REPO / "src").rglob("*.py")), *skin_harness.phone_sources()]
    if not path.name.startswith("test_")
    for line in path.read_text().splitlines()
    if _names_release(line, CORPUS_RELEASE)
]


@pytest.fixture
def asked(tmp_path):
    """One room's asking: every request it made, every answer it got, and its scratch tree.

    `release` is what the connector stamps the chunks it serves with and `matched_nothing` is a
    search that returns no hit — the two ways the release filter can be left with no excerpt to
    hand on. `health_reads` is every URL the start-of-day release check read.
    """
    return {"requests": [], "answers": [], "capped": False, "health_reads": [],
            "release": CORPUS_RELEASE, "matched_nothing": False, "tmp": tmp_path}


class _Recorded:
    """What the fake `urlopen` returns: a recorded body, with only the method `post` uses."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Recorded":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def _recorded_body(asked, request) -> bytes:
    payload = json.loads(request.data)
    if request.full_url != GUIDANCE_URL:
        return LANE_ANSWER.read_bytes()
    params = payload["params"]
    named = params["arguments"].get("id") or "mtpd"
    body = json.loads((ASK_FIXTURES / f"guidance-{params['name']}-{named}.json").read_text())
    return json.dumps(_as_served(asked, params["name"], body)).encode()


def _as_served(asked, tool, body):
    """The recorded body as this scenario's connector serves it: its hits, at its release."""
    content = body["result"]["structuredContent"]
    if tool == "search" and asked["matched_nothing"]:
        content["results"] = []
    if tool == "fetch":
        content["metadata"]["release_tag"] = asked["release"]
    return body


def _ask(asked, question):
    """Ask one question the way the demo skin does, over the recorded lane and connector."""

    def urlopen(request, timeout):
        asked["requests"].append(request)
        if asked["capped"]:
            raise urllib.error.HTTPError(request.full_url, 402, "Payment Required", {}, None)
        return _Recorded(_recorded_body(asked, request))

    def posted(url, payload):
        return post(url, payload, urlopen=urlopen)

    answer = ask(
        question,
        guidance=lambda tool, arguments: call_guidance(tool, arguments, post=posted),
        lane=lambda prompt: call_lane(prompt, post=posted),
    )
    asked["answers"].append(answer)
    return answer


def _answer(asked):
    return asked["answers"][-1]


def _lane_calls(asked):
    """Every request that reached the model itself, as opposed to the guidance connector."""
    return [request for request in asked["requests"] if request.full_url == LANE_URL]


def _lane_prompt(asked):
    """What the model was actually sent, read back out of the recorded request."""
    return json.loads(_lane_calls(asked)[-1].data)["messages"][0]["content"]


# ----------------------------------------------------------------- in my room, asking


@given("I am in my room")
def _i_am_in_my_room(asked):
    asked["room"] = identity_from_link("https://demo.ai4bcm.org/r/demo-1")


@given("the corpus holds nothing on ISO/TS 22317")
def _the_corpus_holds_nothing_on(asked):
    # ADR-0005, an owner call: the three named texts are not in the corpus and are not going in.
    # Spelled out rather than parsed, so it cannot swallow another story's Given.
    assert uncovered_standard("ISO/TS 22317") == "ISO/TS 22317"


@when("I ask what the corpus says about setting an MTPD")
def _i_ask_about_setting_an_mtpd(asked):
    _ask(asked, MTPD_QUESTION)


@when(parsers.parse("I ask what {standard} says about setting an MTPD"))
def _i_ask_what_a_standard_says(asked, standard):
    _ask(asked, f"What does {standard} say about setting an MTPD?")


@when("I ask a BCM question")
@when("I ask a question")
def _i_ask_a_bcm_question(asked):
    _ask(asked, MTPD_QUESTION)


@when("I ask a second question")
def _i_ask_a_second_question(asked):
    _ask(asked, MTPD_QUESTION)
    _ask(asked, "What does the corpus say about an RTO?")


@when("I ask any number of questions")
def _i_ask_any_number_of_questions(asked):
    for question in (MTPD_QUESTION, "What does ISO/TS 22317 say?") * 3:
        _ask(asked, question)


# ------------------------------------------------------- the answer and its citation


@then("I get an answer drawn from the corpus")
def _an_answer_drawn_from_the_corpus(asked):
    answer = _answer(asked)
    assert answer.text == _recorded_answer()
    assert answer.citations, "the answer rests on no corpus chunk"
    prompt = _lane_prompt(asked)
    for citation in answer.citations:
        assert citation.text in prompt, "a chunk was cited that the lane never saw"


@then("the citation is printed on screen where I can see it")
def _the_citation_is_printed_on_screen(asked):
    answer = _answer(asked)
    for citation in answer.citations:
        assert f"Source: {citation}" in answer.on_screen


def _release_in(url):
    """The tag in a citation link's `/blob/<tag>/` segment, whole: "2026.11" is inside
    "/blob/2026.11.1/", so a substring check would let the withdrawn release pass (674)."""
    parts = urllib.parse.urlsplit(url).path.split("/")
    return parts[parts.index("blob") + 1] if "blob" in parts[:-1] else None


@then(parsers.parse('it names one of the ten sources in release "{release}", '
                    "with a locator I can look up"))
def _it_names_one_of_the_ten_sources(asked, release):
    assert release == CORPUS_RELEASE
    assert len(SOURCES) == 10
    for citation in _answer(asked).citations:
        assert citation.source in SOURCES
        assert citation.document and citation.locator
        # A locator I can look up: the link is absolute and points into the frozen release.
        assert citation.url.startswith("https://") and _release_in(citation.url) == release
        assert citation.locator in _answer(asked).on_screen


@then("the answer on screen is the answer")
def _the_answer_on_screen_is_the_answer(asked):
    assert _answer(asked).on_screen.startswith(_answer(asked).text)


@then("none of the model's reasoning is printed with it")
def _no_reasoning_is_printed(asked):
    reply = _recorded_lane_reply()
    message, usage = reply["choices"][0]["message"], reply["usage"]
    assert usage["completion_tokens_details"]["reasoning_tokens"] > 0, "the lane did not think"
    assert "reasoning" not in message, "the recorded body carries thinking; exclude is not on"
    screen = _answer(asked).on_screen
    for field, value in message.items():
        if field != "content":
            assert str(value) not in screen


# ------------------------------------------------------- what the corpus does not cover


@then("I am told the corpus does not cover it")
def _i_am_told_the_corpus_does_not_cover_it(asked):
    assert _answer(asked).text == NOT_COVERED.format(standard="ISO/TS 22317")
    # Decided before both hosts, because the answer is already known: neither was called at all.
    assert asked["requests"] == [], "the corpus was read about a text it does not hold"


@then("nothing is invented to fill the gap")
def _nothing_is_invented(asked):
    """No citation, and the model was never handed the gap to fill — however the gap arose."""
    assert _answer(asked).citations == ()
    assert _lane_calls(asked) == []
    assert "clause" not in _answer(asked).text


# --------------------------------------------------------------- the two hosts, no token


@then(parsers.parse('the corpus is read from "{host}"'))
def _the_corpus_is_read_from(asked, host):
    read = [r for r in asked["requests"] if r.full_url == GUIDANCE_URL]
    assert read, "the corpus was not read at all"
    assert all(r.host == host for r in read)


@then("no bearer token is sent")
def _no_bearer_token_is_sent(asked):
    for request in asked["requests"]:
        assert request.get_header("Authorization") is None


@then(parsers.parse('the BIA session connector "{host}" is never called'))
def _the_session_connector_is_never_called(asked, host):
    assert all(host not in request.full_url for request in asked["requests"])


# ------------------------------------------------------------------ the cap, and the room


@given("the OpenRouter key cap has been reached")
def _the_cap_has_been_reached(asked):
    # The key is capped at OpenRouter and shared across five `ai4bcm/*` lanes (ADR-0009), so the
    # cap is induced at the caller: every call fails at once, the way a 402 arrives.
    asked["capped"] = True


@then("I am told plainly that the lane is unavailable")
def _i_am_told_the_lane_is_unavailable(asked):
    answer = _answer(asked)
    assert answer == Answer(UNAVAILABLE, ())
    assert "402" not in answer.on_screen and "Traceback" not in answer.on_screen


@then("the walk is not left in an unfinished state")
def _the_walk_is_not_left_unfinished(asked):
    assert _answer(asked).text.endswith("the rest of the walk carries on without it.")
    assert _ask(asked, "Can I still ask?") == Answer(UNAVAILABLE, ()), "the room stopped taking"


@then("it fails the same way at once")
def _it_fails_the_same_way_at_once(asked):
    first, second = asked["answers"][-2:]
    assert first == second == Answer(UNAVAILABLE, ())
    assert len(asked["requests"]) == 2, "the second question was not tried, or was answered stale"


@then("I am offered no buttons-only substitute for the answer")
def _no_substitute_is_offered(asked):
    answer = _answer(asked)
    assert answer.citations == ()
    assert "button" not in answer.on_screen.lower()


# --------------------------------------------------------------- asking touches no record


@given("a saved record")
@given("any saved record")
@given("a saved record with an impact grid")
def _a_saved_record(asked, ctx):
    """Three words two stories both say, and a step name is the whole suite's (pytest-bdd).

    The ask lane means a record in a room nobody is walking — it is about to prove that asking
    does not touch one. Ticket 16 means the record its own Background accepted, which is already
    on disk by the time this runs. So both are done: the lane's record is written in the lane's
    own tmp room, and a scenario that walked to stage 4 first picks its record up here.
    """
    saved = write_record(asked["tmp"], "output/bia-record.json",
                         {"company": "Incident and problem management"}, 0)
    asked["fingerprint"] = fingerprint(saved)
    if ctx.get("room_folder") is not None:
        ctx["record"] = _landed(ctx)
        assert ctx["record"] is not None, "this room holds no BIA record"


@then("the record's fingerprint is unchanged")
def _the_fingerprint_is_unchanged(asked):
    record = read_record(asked["tmp"], "output/bia-record.json")
    assert record is not None
    assert fingerprint(record) == asked["fingerprint"]


# ══════════════════════════ the ask lane must refuse rather than answer from nothing ═════════════
#
# `features/the-ask-lane-must-not-answer-from-nothing.feature`. The same recorded connector as
# above, with one thing moved: the release it stamps the chunks it serves with. Nothing here
# deletes the filter — the corpus is wrong, the way it will be wrong on the day the connector's
# tag moves, and the lane is asked the question anyway.


@given("the guidance connector is serving a corpus release that is not the frozen one")
def _the_connector_serves_another_release(asked):
    asked["release"] = STALE_RELEASE
    assert STALE_RELEASE != CORPUS_RELEASE


@given("the guidance connector is serving the frozen release")
def _the_connector_serves_the_frozen_release(asked):
    assert asked["release"] == CORPUS_RELEASE


@given("the corpus holds nothing on what I am about to ask")
def _the_corpus_holds_nothing_on_it(asked):
    asked["matched_nothing"] = True


@when("I ask a question the corpus does not match")
def _i_ask_a_question_the_corpus_does_not_match(asked):
    _ask(asked, "What does the corpus say about the melting point of tungsten?")


@then("I am told the guidance corpus is not the frozen release and the lane cannot vouch for it")
def _i_am_told_the_corpus_is_the_wrong_release(asked):
    assert _answer(asked).text == WRONG_RELEASE.format(expected=CORPUS_RELEASE)


@then("I am told the guidance corpus holds nothing on my question")
def _i_am_told_the_corpus_holds_nothing(asked):
    assert _answer(asked).text == NOTHING_MATCHED


@then("no answer to my question is produced")
def _no_answer_is_produced(asked):
    assert "MTPD" not in _answer(asked).text


@then("the model is never called")
def _the_model_is_never_called(asked):
    assert _lane_calls(asked) == []


@then('no "Source:" line is printed, because there is nothing to cite')
def _no_source_line_is_printed(asked):
    answer = _answer(asked)
    assert answer.citations == ()
    assert "Source:" not in answer.on_screen


@then("it does not read like the refusal for a question nothing in the corpus matched")
def _it_does_not_read_like_the_other_refusal(asked):
    """A facilitator acts on these differently: fix the corpus, versus ask it another way."""
    text = _answer(asked).text
    assert text != NOTHING_MATCHED
    assert "vouch" in text and "vouch" not in NOTHING_MATCHED
    assert CORPUS_RELEASE in text and CORPUS_RELEASE not in NOTHING_MATCHED


# ------------------------------------------------------ the frozen release, in one place


@given("the frozen release the lane expects is named once and nowhere else")
def _the_frozen_release_is_named_once(asked):
    assert FROZEN_NAMED == [("ask.py", f'CORPUS_RELEASE = "{CORPUS_RELEASE}"')]


@when("the corpus moves to a new release and that one name is changed to match")
def _the_corpus_moves_and_that_name_is_changed(asked, monkeypatch):
    asked["release"] = STALE_RELEASE
    assert _ask(asked, MTPD_QUESTION).citations == (), "the moved corpus was answered from"
    monkeypatch.setattr(nemo.ask, "CORPUS_RELEASE", STALE_RELEASE)
    _ask(asked, MTPD_QUESTION)


@then("the lane answers from the new release")
def _the_lane_answers_from_the_new_release(asked):
    answer = _answer(asked)
    assert answer.text == _recorded_answer()
    assert answer.citations


@then("no other place had to be edited to make it stop refusing")
def _no_other_place_had_to_be_edited(asked):
    """The filter followed the one name, and so does `release_note`, which reads the same one."""
    assert len(FROZEN_NAMED) == 1
    assert release_note(get=lambda url: {"release_tag": STALE_RELEASE}) == RELEASE_AGREES.format(
        served=STALE_RELEASE)


# ═══════════════════════════════════════ the walking skeleton ═══════════════════════════════════
#
# A room on disk, the processes its own files name, one Stage 1 card, one press. Nothing here
# reaches for Chainlit: the walk decides, and a skin only draws what `nemo.walk` hands it.

#: The room's own method. Every parameter the walk carries is read from this and from nothing else,
#: so a scenario can move the threshold and watch the card follow it.
METHOD_FILE = {
    "org": "Marschkamp Fleisch GmbH & Co. KG",
    "time_horizons": ["1 h", "2 h", "4 h", "8 h", "24 h", "72 h", "168 h"],
    "scenarios": [{"id": "operational", "name": "Operational"},
                  {"id": "legal", "name": "Legal"}],
    "severity_scale": [{"level": level, "label": label} for level, label in enumerate(
        ("none", "low", "medium", "high", "very high"), start=1)],
    "intolerability_threshold": 4,
    "rpo_vocabulary": ["<1 h", "<24 h", "<168 h", ">168 h"],
}

#: Machine identifiers, and the two file suffixes, that may not appear on a card outside its
#: `Source:` line. `docs/voice.md` §3.1, which is where each of these strings comes from.
BANNED_ON_A_CARD = (
    "prepare_bia_stage", "confirm_bia_stage", "user_confirmed", "save_token", "awaiting_human",
    "stage_incomplete", "record_saved_graph_pending", "run_id", "record_sha", "page_sha",
    "impact_grid", "recovery_target", "pp4_handoff", "StaleRunRevision", "revision",
    "compare-and-set", ".json", ".md", "/",
)


def _files(folder):
    """Every file the room holds, room-relative — what a manager would see if they looked."""
    return {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}


def _saved(ctx, process=None):
    return json.loads(
        (ctx["room_folder"] / run_file(process or ctx["process"])).read_text(encoding="utf-8"))


def _bia_record(ctx):
    """The record `bia.build` makes of this walk's run state, over the files the walk hands it
    (ticket 131: the confirmed interviews, where each quote's words are sought)."""
    saved = _saved(ctx)
    return bia.build(saved, walk.readable(ctx["room_folder"], saved))


def _open_room(ctx):
    """Open the room link. The room code comes out of the link; the processes come off the disk."""
    ctx["room"] = urllib.parse.parse_qs(ctx["link"].lstrip("?"))["room"][0]
    assert ctx["room"] == ctx["room_folder"].name
    ctx["offered"] = processes(ctx["room_folder"])
    ctx["acts"].append(("open", ctx["link"]))


def _press_process(ctx, process):
    """Press one of the processes on screen. A name that was not offered was typed, and fails."""
    assert process in ctx["offered"], f"{process!r} was not one of the buttons on screen"
    ctx["acts"].append(("press", process))
    ctx["process"] = process
    ctx["card"] = open_bia(ctx["room_folder"], process)


def _press_button(ctx, label):
    """Answer the card on screen. Which stage it is decides what the press does, never the step:
    stage 1 has one control to agree the scope with, stage 2 the four labels (ADR-0011)."""
    assert label in ctx["card"].buttons, f"{label!r} is not a button on this card"
    ctx["acts"].append(("press", label))
    if ctx["card"].stage == STAGE_4:
        # Ticket 17 put two movements behind this one press, in this order: the record onto disk,
        # then the picture drawn from it. They are pressed in turn rather than through
        # the one door, which composes the two of them, because what the walk says between
        # them — saved, and not yet finished — is what stage 4a's scenarios watch, and it is gone
        # by the time the press comes back. `_a_record_has_just_been_saved` presses the composition
        # itself, so nothing here is the only path to the picture.
        ctx["saved_card"], ctx["saved_run"] = _watched(ctx, label)
    else:
        ctx["card"] = _said(ctx, label)[0]


def _watched(ctx, label):
    """Stage 4's two movements, with what the walk said between them caught as it went past.

    One answer and one door, as every other stage has: the record onto disk, then the picture
    drawn from it. What the walk says in between — saved, and not yet finished — is what stage 4a
    watches and is gone by the time the answer comes back, so it is read off the card the second
    movement is handed rather than by stopping the walk half way.
    """
    seen = []

    def watching(room_folder, card):
        seen.append((card, _saved(ctx)))
        return drawing(room_folder, card)

    with pytest.MonkeyPatch.context() as between:
        drawing = walk._draw_graph
        between.setattr(walk, "_draw_graph", watching)
        ctx["card"] = _said(ctx, label)[0]
    return seen[0]


def _back_to_stage_2(ctx):
    """This walk put back where it stood before the interview was kept.

    The scenario keeps one interview per length, and every one of them has to be kept *at stage
    2*: the door reads the stage off the room, so a walk left bound would have the next length
    answering stage 3 instead.
    """
    run = read_record(ctx["room_folder"], run_file(ctx["process"]))
    write_record(ctx["room_folder"], run_file(ctx["process"]),
                 {key: held for key, held in run.items()
                  if key not in ("revision", "transcript")}
                 | {"decisions": [one for one in run["decisions"] if one["stage"] == 1]},
                 run["revision"])
    (ctx["room_folder"] / interview_path(ctx["process"])).unlink(missing_ok=True)


def _said(ctx, words):
    """The one door, driven the way the skin drives it (ADR-0013): typed words, and the revision
    the card that is on the screen was read at.

    Which stage they answer is the walk's own business and never the step's — there is no stage
    named here, exactly as there is none in `open_bia`. The interview goes in where the card has
    one, because bytes previewed from a live interview are nowhere on disk for the door to find.
    """
    card = ctx["card"]
    picked = ctx.get("picked") or (card.interviews[0] if card.interviews else None)
    return answer(ctx["room_folder"], card.activities[0], words, card.revision, picked=picked,
                  record_revision=card.record_revision)


def _only_the_record(ctx, words=ENDORSED):
    """Stage 4 answered and the walk stopped before the picture: ADR-0010's ordinary stop.

    The second movement is what is held back, rather than the door worked around — the manager
    types the same words either way — because what the walk says in between, saved and not yet
    finished, is gone by the time the whole answer comes back.
    """
    with pytest.MonkeyPatch.context() as stopped:
        stopped.setattr(walk, "_draw_graph", lambda _folder, drawn: drawn)
        return _said(ctx, words)[0]


def _claim(ctx):
    """A room minted from the seed company, shipping the BIA ticket 02 says it ships."""
    seed = ctx["tmp"] / "seed"
    shutil.copytree(ctx["room_folder"], seed)
    # In progress, and no further. The one door answers whatever stage the room stands at, so a
    # seed copied out of a room already walked to stage 3 would be walked to the end by answering
    # it again. A room with a walk already in it ships that walk; a room with none is given one.
    if not in_progress(seed):
        answer(seed, processes(seed)[0], AGREE, 0)
    rooms = ctx["tmp"] / "rooms"
    rooms.mkdir(exist_ok=True)
    mint_room(seed, rooms, "adler-7ycyet")
    ctx["claimed"] = rooms / "adler-7ycyet"


# ------------------------------------------------------------------ my company's room


@given(parsers.parse("my company's room is \"{room}\""))
def _my_companys_room_is(ctx, room):
    ctx["room"] = room
    ctx["room_folder"] = ctx["tmp"] / room
    (ctx["room_folder"] / INTERVIEWS).mkdir(parents=True)
    (ctx["room_folder"] / METHOD).parent.mkdir(parents=True)
    (ctx["room_folder"] / METHOD).write_text(json.dumps(METHOD_FILE), encoding="utf-8")
    ctx["method_file"] = METHOD_FILE
    ctx["acts"] = []
    ctx["typed"] = ""
    # The link a scanned code lands on. A story that talks about its own link says so and
    # replaces this; one that starts from a stage still has to get through the door.
    ctx["link"] = f"?room={room}"


@given(parsers.parse('our interview transcripts name the departments "{first}" and "{second}"'))
def _transcripts_name_the_departments(ctx, first, second):
    for index, department in enumerate((first, second)):
        (ctx["room_folder"] / INTERVIEWS / f"26_08_0{index}_interview.md").write_text(
            f"---\ndepartment: {department}\n---\n\n# {department} interview\n", encoding="utf-8")


@given(parsers.parse('our dependency register names the departments "{first}" and "{second}"'))
def _the_register_names_the_departments(ctx, first, second):
    register = ctx["room_folder"] / REGISTER
    register.parent.mkdir(parents=True)
    register.write_text(json.dumps({"KA-01": {
        "asset_id": "KA-01", "department": first, "consumers": [{"department": second}]}}),
        encoding="utf-8")


#: The second process ticket 24's room holds. Two walks live in one room is the ordinary state —
#: it is what `walk.in_progress` exists to list — and it is the state defect 1 of the 2026-09-13
#: code review needs: a reservation made on one BIA must not be filed against the other.
OTHER_PROCESS = "helpdesk-and-support"

#: The process ticket 24's room walks first, spelled as the seed's front matter spells a department.
THIS_PROCESS = "incident-and-problem-management"


@given(parsers.parse(
    'the room holds the process register, the method and one interview for "{process}"'))
def _the_room_holds_the_register_the_method_and_one_interview(ctx, process):
    """Everything a walk needs before it starts, and the second process beside it.

    The method is already on disk — the room step wrote it — so what is added here is the register
    naming both processes and one interview for the named one, which is what carries a walk from
    stage 2 to stage 3 without an interview having to be held first.
    """
    ctx["process"] = process
    for named in (process, OTHER_PROCESS):
        _on_the_menu(ctx, named)
    assert (ctx["room_folder"] / METHOD).is_file(), "the room step did not write the method"
    _interview_file(ctx, INTERVIEWS, f"{process}-interview.md", SCORED_TESTIMONY)
    assert held(ctx["room_folder"], process), "the room holds no interview for this process"


@given("no BIA has been started in the room yet")
def _no_bia_has_been_started(ctx):
    assert in_progress(ctx["room_folder"]) == []


@given(parsers.parse('my room link is the page with "{link}"'))
def _my_room_link_is(ctx, link):
    ctx["link"] = link


# ------------------------------------------------------- which processes we have on file


@given("I have opened my room link")
@when("I open my room link")
def _i_open_my_room_link(ctx):
    _open_room(ctx)


@then("I am offered exactly these processes, each once and in alphabetical order:")
def _i_am_offered_exactly(ctx, datatable):
    assert datatable[0] == ["process"]
    assert ctx["offered"] == [row[0] for row in datatable[1:]]


@then("each one is a button I can press")
def _each_one_is_a_button(ctx):
    assert ctx["offered"]
    for process in ctx["offered"]:
        assert open_bia(ctx["room_folder"], process).activities == (process,)


@then("I am not asked to type a process name")
def _i_am_not_asked_to_type_a_process_name(ctx):
    assert ctx["typed"] == ""
    assert ctx["offered"], "a room that offers nothing leaves typing as the only way in"


# ----------------------------------------------------------------- the Stage 1 card


@given(parsers.parse('I have opened the BIA for "{process}"'))
@when(parsers.parse('I open the BIA for "{process}"'))
def _i_open_the_bia_for(ctx, process):
    if "offered" not in ctx:
        _open_room(ctx)
    _press_process(ctx, process)


@then(parsers.parse('the card is headed "{heading}"'))
def _the_card_is_headed(ctx, heading):
    assert ctx["card"].heading == heading


@then(parsers.parse('it proposes one activity, "{process}"'))
def _it_proposes_one_activity(ctx, process):
    assert ctx["card"].activities == (process,)


@then(parsers.parse('it offers one button, "{label}"'))
def _it_offers_one_button(ctx, label):
    assert ctx["card"].buttons == (label,)


@then("it offers me nothing else")
def _it_offers_me_nothing_else(ctx):
    """One control, and no way to hand the card anything but the press of it."""
    assert ctx["card"].buttons == (AGREE,)
    assert list(inspect.signature(answer).parameters)[:4] == [
        "room_folder", "process", "words", "revision"], "the card is answered in words"
    assert ctx["card"].gradient == GRADIENT, "the gradient is structure underneath, not controls"


# ------------------------------------------------------------------------ one press


@when(parsers.parse('I press "{label}"'))
def _i_press(ctx, label):
    _press_button(ctx, label)


@then(parsers.parse('I read "{text}"'))
def _i_read(ctx, text):
    assert text in ctx["card"].body


@then("the button is gone")
def _the_button_is_gone(ctx):
    assert ctx["card"].buttons == ()


@then("nothing further is asked of me")
def _nothing_further_is_asked_of_me(ctx):
    assert ctx["card"].buttons == () and ctx["card"].decision == ""
    assert ctx["card"].gradient == ()


# ------------------------------------------------------------- the decision on file


def _on_the_menu(ctx, process):
    """Put a process on the room's menu the way a room does: its own register names it.

    A story that starts from a later stage names the process without describing the files it came
    off, so the room has to be made to name it — and it has to be named by a file, because
    `_press_process` refuses any name the room did not offer.
    """
    if process in processes(ctx["room_folder"]):
        return
    register = ctx["room_folder"] / REGISTER
    register.parent.mkdir(parents=True, exist_ok=True)
    named = json.loads(register.read_bytes()) if register.is_file() else {}
    register.write_text(json.dumps({**named, process: {DEPARTMENT: process}}), encoding="utf-8")


@given(parsers.parse('I have agreed the scope for "{process}" and nothing more'))
@given(parsers.parse('I have agreed the scope for "{process}"'))
def _i_have_agreed_the_scope_for(ctx, process):
    _on_the_menu(ctx, process)
    _open_room(ctx)
    ctx["before"] = _files(ctx["room_folder"])
    _press_process(ctx, process)
    _press_button(ctx, AGREE)


@when("I look at what the room holds")
@when("the operator looks in my room")
def _i_look_at_what_the_room_holds(ctx):
    ctx["held"] = _files(ctx["room_folder"])


@then(parsers.parse('my decision is on file at "{path}"'))
def _my_decision_is_on_file_at(ctx, path):
    assert path in ctx["held"]
    ctx["on_file"] = json.loads((ctx["room_folder"] / path).read_text(encoding="utf-8"))


@then(parsers.parse('it says stage {stage:d} was decided "{decided}"'))
def _it_says_the_stage_was_decided(ctx, stage, decided):
    assert [entry for entry in ctx["on_file"]["decisions"]
            if entry["stage"] == stage and entry["decided"] == decided]


# --------------------------------------------------------------------- coming back


@given("I have closed the page")
def _i_have_closed_the_page(ctx):
    ctx.pop("card", None)
    ctx.pop("offered", None)


@when(parsers.parse('I open my room link and open the BIA for "{process}" again'))
def _i_open_my_room_link_and_the_bia_again(ctx, process):
    _open_room(ctx)
    _press_process(ctx, process)


@then("I am not asked to agree it a second time")
def _i_am_not_asked_to_agree_it_again(ctx):
    """One definition for two arrivals: a page reopened here, and a code scanned a second time in
    `a-scan-mints-a-room-from-the-seed.feature`. Both arrive at a room whose stage 1 is agreed, so
    both read the card the walk serves off the record already on disk — asking for it again writes
    not one byte (ADR-0010). Ticket 50 wrote this sentence a second time and pytest-bdd let the
    later definition shadow the first, which took the two assertions below out of the skeleton's
    scenario without failing anything; the run's own record and the card it serves are asserted
    together here instead.
    """
    assert _slugs(ctx["process"])[0] in in_progress(ctx["room_folder"])
    served = open_bia(ctx["room_folder"], ctx["process"])
    assert served.revision > 0, "the room holds no agreed scope to come back to"
    assert AGREE not in served.buttons
    assert served.decision == ""


# -------------------------------------------------------------------- the Source: line


@then(parsers.parse('the card carries a "{label}" line'))
def _the_card_carries_a_source_line(ctx, label):
    assert ctx["card"].source_line.startswith(label)
    assert "\n" not in ctx["card"].source_line, "it is a line, not a paragraph"


@then("that line names every file the proposal was read from")
def _that_line_names_every_file_read(ctx):
    folder, process, named = ctx["room_folder"], ctx["process"], set(ctx["card"].sources)
    for path in _files(folder):
        if path.startswith(INTERVIEWS) and process in (folder / path).read_text(encoding="utf-8"):
            assert path in named, f"{path} names {process} and is not on the line"
    if process in (folder / REGISTER).read_text(encoding="utf-8"):
        assert REGISTER in named
    assert METHOD in named, "the method on the card was read from the room's method file"


@then("every file it names is a file in my room")
def _every_file_it_names_is_in_my_room(ctx):
    assert all((ctx["room_folder"] / path).is_file() for path in ctx["card"].sources)


# ------------------------------------------------------------------------- the voice


@when("I read the card")
def _i_read_the_card(ctx):
    card = ctx["card"]
    ctx["prose"] = " ".join((card.heading, card.body, card.decision, card.rule, *card.buttons))


@then("it is written in sentences, not as a numbered list of machine actions")
def _it_is_written_in_sentences(ctx):
    body = ctx["card"].body
    assert not [line for line in body.splitlines() if re.match(r"\s*(\d+[.)]|[-*•])", line)]
    assert body.count(". ") >= 2, "sentences, and more than one of them"


@then(parsers.parse(
    'it names no tool, no field name and no file path anywhere but its "{label}" line'))
def _it_names_no_machine_identifier(ctx, label):
    assert [word for word in BANNED_ON_A_CARD if word in ctx["prose"]] == []
    assert ctx["card"].source_line.startswith(label)


# ------------------------------------------------------------ our method, not an invented one


@given(parsers.parse("our method file sets {parameters}"))
def _our_method_file_sets(ctx, parameters):
    assert parameters
    assert set(METHOD_PARAMETERS) <= set(ctx["method_file"])


@when(parsers.parse('I open the BIA for "{process}" and agree the scope'))
def _i_open_the_bia_and_agree(ctx, process):
    if "offered" not in ctx:
        _open_room(ctx)
    _press_process(ctx, process)
    _press_button(ctx, AGREE)


@then("the method my walk carries is the one in our method file, parameter for parameter")
def _the_method_is_the_rooms_own(ctx):
    # ...and, since ticket 143, the company that file names: the record's only source for the name
    # its dependency page is titled and filed under. Carried for the same reason as the parameters.
    carried = _saved(ctx)["method"]
    assert carried == {name: ctx["method_file"][name]
                       for name in (*METHOD_PARAMETERS, "org") if name in ctx["method_file"]}


@then("nothing appears in it that our method file does not say")
def _nothing_is_invented_in_the_method(ctx):
    carried = _saved(ctx)["method"]
    assert all(carried[name] == ctx["method_file"][name] for name in carried)


# ------------------------------------------------------------------------ typed inputs


@then("every single thing I did was a press")
def _every_single_thing_was_a_press(ctx):
    assert {kind for kind, _what in ctx["acts"]} == {"open", "press"}
    assert ctx["acts"][0][0] == "open", "the link opens the room; everything after it is a press"


@then("I typed nothing at all — not a process name, not a stage, not a number")
def _i_typed_nothing_at_all(ctx):
    assert ctx["typed"] == ""
    assert all(what in ctx["offered"] or what == AGREE
               for kind, what in ctx["acts"] if kind == "press")


# --------------------------------------------------- a stage begins because I pressed something


@when(parsers.parse('the assistant writes that it is opening the BIA for "{process}"'))
def _the_assistant_narrates_opening(ctx, process):
    ctx["narration"] = f"Right — opening the BIA for {process} now."
    ctx["acts"].append(("narrate", ctx["narration"]))


@then(parsers.parse('no BIA has been opened for "{process}"'))
def _no_bia_has_been_opened_for(ctx, process):
    assert process in ctx["narration"]
    assert in_progress(ctx["room_folder"]) == []
    assert "card" not in ctx


@then(parsers.parse('nothing is on file at "{path}"'))
def _nothing_is_on_file_at(ctx, path):
    assert not (ctx["room_folder"] / path).exists()


@then(parsers.parse('the only way to open it is still the button named "{process}"'))
def _the_only_way_to_open_it_is_the_button(ctx, process):
    assert process in ctx["offered"]
    assert list(inspect.signature(open_bia).parameters) == ["room_folder", "process"]


# ------------------------------------------------------------------ a save that was overtaken


@given("the room's record of my walk has moved on since my page read it")
def _the_record_has_moved_on(ctx):
    run = read_record(ctx["room_folder"], run_file(ctx["process"])) or {
        "process": ctx["process"], "room": ctx["room_folder"].name, "schema": 1, "decisions": []}
    ctx["newer"] = write_record(ctx["room_folder"], run_file(ctx["process"]),
                                {key: held for key, held in run.items() if key != "revision"},
                                run.get("revision", 0))


@then("my press does not land on top of the newer record")
def _my_press_does_not_land_on_top(ctx):
    assert _saved(ctx) == ctx["newer"]


@then("the room still holds the newer record")
def _the_room_still_holds_the_newer_record(ctx):
    saved = _saved(ctx)
    assert saved["revision"] == ctx["newer"]["revision"]
    assert saved == ctx["newer"], "the answer that lost the race landed anyway"


@then("I read that someone else saved this BIA while I was reading")
def _i_read_that_someone_else_saved_it(ctx):
    assert ctx["card"].body.startswith("Someone else saved this BIA while you were reading")


# --------------------------------------------------------------- the room remembers for me


@given("everything that was said in the conversation has been thrown away")
def _the_conversation_is_thrown_away(ctx):
    ctx["remembered"] = {"room": ctx["room_folder"], "process": ctx["process"]}
    for key in ("card", "offered", "acts", "on_file", "prose", "held", "process"):
        ctx.pop(key, None)


@when(parsers.parse('the walk is picked up again knowing only my room and "{process}"'))
def _the_walk_is_picked_up_again(ctx, process):
    assert set(ctx["remembered"]) == {"room", "process"}
    ctx["process"] = process
    ctx["card"] = open_bia(ctx["remembered"]["room"], process)


@then("the correct next card comes back")
def _the_correct_next_card_comes_back(ctx):
    assert ctx["card"].heading == HEADING
    assert ctx["card"].stage == 1


@then(parsers.parse('it carries what was saved for "{process}"'))
def _it_carries_what_was_saved_for(ctx, process):
    assert ctx["card"].saved == _saved(ctx, process)


@then("I am asked nothing at all to rebuild it")
def _i_am_asked_nothing_to_rebuild_it(ctx):
    assert ctx["card"].decision == "" and ctx["card"].buttons == ()
    assert ctx["card"].method == {name: METHOD_FILE[name]
                                  for name in (*METHOD_PARAMETERS, "org")}


# ------------------------------------------------------- no stage that has not been earned


@when("a later stage of the BIA is asked for by name")
def _a_later_stage_is_asked_for_by_name(ctx):
    ctx["asked_stage"] = 3
    ctx["card"] = open_bia(ctx["room_folder"], ctx["process"])


@then("that stage is not served")
def _that_stage_is_not_served(ctx):
    assert ctx["card"].stage != ctx["asked_stage"]
    assert "stage" not in inspect.signature(open_bia).parameters, "there is nowhere to ask"


@then("what comes back is the card for the stage my walk has actually reached")
def _the_card_for_the_stage_reached(ctx):
    assert ctx["card"].stage == 1 and ctx["card"].heading == HEADING
    assert ctx["card"].saved["decisions"][-1]["stage"] == 1


# ----------------------------------------------------------- stage 1 leaves nothing to read


def _new_files(ctx):
    """What appeared in the room since this stage began — looked up now if nothing looked yet."""
    return ctx.get("held", _files(ctx["room_folder"])) - ctx["before"]


@then("no document has been written for me to read")
def _no_document_has_been_written(ctx):
    readable = [path for path in _new_files(ctx)
                if path.endswith((".md", ".html", ".pdf", ".docx", ".txt"))]
    assert readable == []


@then("the only new thing on file is my decision")
def _the_only_new_thing_is_my_decision(ctx):
    assert ctx["held"] - ctx["before"] == {run_file(ctx["process"])}


# ------------------------------------------------------------ the room a manager claims


@given("I claim a room of my own")
def _i_claim_a_room_of_my_own(ctx):
    _claim(ctx)


@when("I open it")
def _i_open_the_claimed_room(ctx):
    ctx["offered"] = processes(ctx["claimed"])
    ctx["held"] = _files(ctx["claimed"])


@then("it holds our interview transcripts and our company files")
def _it_holds_our_files(ctx):
    assert [path for path in ctx["held"] if path.startswith(INTERVIEWS)]
    assert {REGISTER, METHOD} <= ctx["held"]


@then("it holds a BIA already in progress")
def _it_holds_a_bia_already_in_progress(ctx):
    assert in_progress(ctx["claimed"])


# ---------------------------------------------------- NOT BUILT: ticket 15's run_id binding


@given("a room that ships a BIA already in progress")
def _a_room_that_ships_a_bia(ctx):
    _claim(ctx)


@given("a walk that has refereed nothing and written nothing")
def _a_walk_that_did_no_work(ctx):
    ctx["bare_walk"] = ctx["run"] = {"run_id": str(uuid.uuid4()), "refereed": [], "written": [],
                                     **({"process": ctx["process"]} if "process" in ctx else {})}


@when("that walk tries to finish over the BIA the room shipped")
def _that_walk_tries_to_finish(ctx):
    """Nothing in nemo refuses this, and pretending otherwise is the finding this scenario is for.

    Ticket 15 owns the binding — a walk may only finish over a record its own run produced or
    advanced. Until it lands, a walk that did no work can close over the record a claimed room
    shipped. The scenario is tagged in the feature and xfails strictly from `conftest.py`, so the
    day the binding is built this step goes red and must be written against it.
    """
    ctx["refusal"] = None


@then("it is refused, because that walk did not produce it")
def _it_is_refused_because_that_walk_did_not_produce_it(ctx):
    assert ctx["bare_walk"]["written"] == []
    assert ctx["refusal"] is not None, "ticket 15's run_id binding is not built"


# ═══════════════════════════════════ 20 — the real demo skin under test ══════════════════════════
# These steps drive the phone app, `skin/PROTOTYPE_conversation_app.py`, over `skin_harness.py`'s
# stand-in for Chainlit and its scripted lane (ticket 164): the scanned code becoming an identity,
# the greeting and a typed turn are the app's own lines rather than a restatement of them. What
# Chainlit does around the app — socket, cookie, routes — is `tests/isolation/`, which launches
# the same file under the scratch Chainlit interpreter, and the last scenario reads that suite.
#
# Retired by ticket 164: "The sweep does not keep a room waiting" and the sweep half of "The first
# manager into a fresh room". The phone app does no sweep; `nemo.door.sweep` itself is the two
# sweep scenarios of `the-room-door.feature` and `src/nemo/test_door.py`.

ISOLATION = REPO / "tests" / "isolation"


@pytest.fixture
def skin(ctx, monkeypatch):
    """The phone app over a rooms folder, a seed and a log this scenario owns."""
    return skin_harness.fresh_skin(monkeypatch, ctx["tmp"])


def _on_screen():
    """What the manager has been shown so far. `SENT` is the record; nothing copies it."""
    return [message.content for message in skin_harness.SENT]


def _seed(ctx, skin, room):
    skin_harness.seed_room(skin.ROOMS, room, "Incident and problem management")
    ctx["rooms_before"] = skin_harness.room_names(skin.ROOMS)


def _open(ctx, link):
    """Scan a link and be greeted, the way a manager is: the callback, then `on_chat_start`.

    The phone opens a chat only on a room whose every activity it can walk, and it mints the
    chat's room from the seed, so the room is opened on the seed the skin's own drafts were made
    for (`skin_harness.walkable_seed`).
    """
    skin_harness.app.SEED = skin_harness.walkable_seed()
    ctx["identity"] = skin_harness.scan(link)
    ctx["error"] = None
    if ctx["identity"] is None:
        return
    ctx["profile"] = {"access_token": ctx["identity"].identifier}
    ctx["room"] = ctx["identity"].identifier
    try:
        skin_harness.open_the_room(ctx["room"])
    except Exception as raised:  # noqa: BLE001 - what would reach the page is what is asserted
        ctx["error"] = raised


def _minted_by_the_door(ctx, skin, room):
    """The room a delegate arrives at, made the one way it now can be: through a door.

    Ticket 186 (c): the login opens a room and never makes one, so a room a scenario arrives at
    must have been minted by the QR's `/new` first (`skin/new_room.py` is the other door and makes
    only `konstantin…`/`check…` rooms, which no scenario here is). The seed is the phone's own, for
    `_open`'s reason: the chat opens only on a room whose every activity it can walk.
    """
    skin_harness.app.SEED = skin_harness.walkable_seed()
    skin_harness.scan_the_qr(room)
    assert (skin.ROOMS / room).is_dir(), f"the door made no room for {room!r}"


def _phone_rooms(room):
    """The folders the phone keeps for one identity: its own, and one per model (`<room>-<model>`,
    the app's docstring: each model gets its own room, so walks never collide)."""
    return {room, *(f"{room}-{model}" for model in skin_harness.app.lanes.LABELS)}


@given(parsers.parse('room "{room}" holds files'))
def _room_holds_files(ctx, skin, room):
    _seed(ctx, skin, room)


@when(parsers.parse('I open the link for "{room}" with "{query}" on the end'))
def _i_open_the_link_with_tracking_on_the_end(ctx, skin, room, query):
    _open(ctx, f"/demo/r/{room}{query}")
    assert ctx["error"] is None, f"the room did not open: {ctx['error']!r}"


@then(parsers.parse('what I write lands in the room folder for "{room}"'))
def _what_i_write_lands_in_the_room_folder(ctx, skin, room):
    """A typed line is a turn, and the turn file is what it writes: in this identity's own room."""
    skin_harness.type_into_the_composer(AGREE)
    folder = skin_harness.session().folder
    assert folder.parent == skin.ROOMS and folder.name in _phone_rooms(room), folder
    assert [turn.said for turn in turn_file.past(folder)] == [AGREE]
    assert skin_harness.LANE_CALLS, "the turn never reached the lane, so nothing was written"


@then(parsers.parse('no room folder named "{name}" is created'))
def _no_room_folder_named(ctx, skin, name):
    """A room code decides storage, so a folder under the query-stringed name is a wrong room."""
    now = skin_harness.room_names(skin.ROOMS)
    assert name not in now
    made = set(now) - set(ctx["rooms_before"])
    assert made <= _phone_rooms(ctx["room"]), f"a room folder nobody minted was written: {made}"


@when("I open a link that carries no room code")
def _i_open_a_link_with_no_room_code(ctx, skin):
    _open(ctx, "/")


@then("I am admitted to no room at all")
def _i_am_admitted_to_no_room(ctx):
    assert ctx["identity"] is None, "the skin made an identity out of a link with no room in it"
    assert skin_harness.SENT == [], "somebody with no room code was greeted by a room"


@then("the demo skin holds no identity for me")
def _the_skin_holds_no_identity(ctx):
    assert ctx["identity"] is None
    assert skin_harness.app.cl.user_session.get("user") is None


@given("a fresh room whose files directory does not exist yet")
def _a_fresh_room(ctx, skin):
    """A room nobody has opened: minted at the QR's door (t186 (c)) and opened by nobody since, so
    there is no `<room>-<model>` chat folder for it and no files directory either."""
    ctx["rooms_before"] = skin_harness.room_names(skin.ROOMS)
    assert not _phone_rooms(ctx["room"]) & set(ctx["rooms_before"]), "the fixture is not fresh"
    _minted_by_the_door(ctx, skin, ctx["room"])


@when("I am the first to open its link")
def _i_am_the_first_to_open_its_link(ctx, skin):
    _open(ctx, f"/demo/r/{ctx['room']}")


@then("I am greeted with what the room holds")
def _i_am_greeted_with_what_the_room_holds(ctx, skin):
    """The phone's greeting (`core.greeting`) is nemo's own and names where the room stands, drawn
    as he reads it; the room's activities are offered by the walk once he starts, not here.

    Drawn with nothing named yet, which is what the greeting is: ticket 215 made the standard's own
    words named once per conversation rather than once per turn, and the session that drew this
    greeting carries them as said from then on. Re-drawing through the same session would therefore
    say "BIA" bare and compare a second turn against a first."""
    words = skin_harness.app.core.words
    folder = skin_harness.session().folder
    greeting, _ = words.named_turn(
        skin_harness.app.core.greeting(folder), [], words.room_terms(folder), set())
    assert _on_screen() == [greeting]
    assert walk.processes(folder), "the room holds nothing to walk"


@then("no error about a missing directory reaches the page")
def _no_error_about_a_missing_directory(ctx):
    """Nothing raised on the way in, and the page carries the greeting, not the setup fault."""
    assert ctx["error"] is None, f"the first manager into the room met {ctx['error']!r}"
    assert skin_harness.app.cl.user_session.get("fault") is None, "the room did not open"
    assert not [line for line in _on_screen() if "Traceback" in line or "Error" in line]


# ---------------------------------------------------------- the suite, as a thing that is read


@given("the isolation suite")
def _the_isolation_suite(ctx):
    ctx["suite"] = {path.name: path.read_text(encoding="utf-8")
                    for path in sorted(ISOLATION.glob("*.py"))}


@when("I read what it launches")
def _i_read_what_it_launches(ctx):
    ctx["launched"] = re.findall(r'"run",\s*str\((\w+)\)', "\n".join(ctx["suite"].values()))
    ctx["app_paths"] = re.findall(r'REPO\s*/\s*"(\w+)"\s*/\s*"(\w+\.py)"',
                                  "\n".join(ctx["suite"].values()))


@then(parsers.parse('it launches "{app}" and nothing else'))
def _it_launches(ctx, app):
    # Ticket 163: the phone app is the app the manager talks to, and the only one the suite attacks:
    # one `chainlit run` target, one app path, no switch back to another app.
    assert ctx["launched"] == ["APP"], f"expected one `chainlit run` target, got {ctx['launched']}"
    assert ["/".join(pair) for pair in ctx["app_paths"]] == [app]
    assert "NEMO_PROBE_APP" not in "\n".join(ctx["suite"].values()), "a switch to another app"
    assert (REPO / app).is_file()


@then("no stand-in app is launched in its place")
def _no_stand_in_app(ctx):
    everything = "\n".join(ctx["suite"].values())
    assert "probe_app" not in everything, "the stand-in is still named in the suite"
    assert not (ISOLATION / "probe_app.py").exists()
    registered = re.findall(r"^\s*@(?:cl|chainlit)\.\w+", everything, re.MULTILINE)
    assert registered == [], f"a file in the suite registers handlers of its own: {registered}"


@then("it runs on the scratch Chainlit interpreter")
def _it_runs_on_the_scratch_interpreter(ctx):
    conftest = ctx["suite"]["conftest.py"]
    assert "/home/user/work/.venvs/chainlit-probe" in conftest
    assert "importorskip" in conftest, "another interpreter would run it and fail rather than skip"


@then("Chainlit is not a dependency of nemo")
def _chainlit_is_not_a_dependency(ctx):
    """The manifest's requirements, not its prose: `pyproject.toml` may say the word and does."""
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    required = [*project.get("dependencies", []),
                *(name for extra in project.get("optional-dependencies", {}).values()
                  for name in extra)]
    assert [name for name in required if "chainlit" in name.lower()] == []
    imports = [f"{path.name}: {line}" for path in sorted((REPO / "src" / "nemo").glob("*.py"))
               for line in path.read_text(encoding="utf-8").splitlines()
               if re.match(r"\s*(import|from)\s+chainlit", line)]
    assert imports == []
# ═════════════════════════ stage 2 — the transcript already in the room ═════════════════════════
#
# `features/the-transcript-already-in-the-room.feature`. The transcripts are already in the room
# and the human presses the one this BIA rests on, so the discipline the skeleton's steps hold is
# the discipline here too: **an interview reaching `nemo.walk` may only ever be one the card
# offered.** `_press_interview` is the only way a step names one and it asserts it, so "typed
# inputs: 0" stays a property the steps enforce rather than a claim they make.
#
# The last two scenarios drive `nemo.card.render` over the real cards this walk serves, because
# that is the door ticket 09 built and ticket 12 put in the live path. They populate ticket 09's
# own `walk` fixture from `features/conftest.py`, which is where the step that reads a refusal
# back lives — one refusal format, checked in one place, whichever story arrives at it.

#: One interview as a company writes one: front matter that names the department, and testimony
#: under it. Real sentences, because the preview is asserted to reach past the front matter.
TESTIMONY = ("---\ndepartment: {process}\n---\n\n# {process} interview\n\n"
             "Tim: if the ticket system stops we take incidents by phone and keep a local incident "
             "log. After that the recovery teams are called through Microsoft Teams.\n")

#: The record ticket 09's refusal step names when it reads a bug report back. A card is checked
#: against the record behind it, and the report says which record that was, so the scenario that
#: reads the report has to be able to name it.
NINE_RECORD = {"revision": 3, "activities": [{"id": "BIA-2026-002"}]}


#: TESTIMONY with the figures a BIA needs to pass the referee: every time band scored for both of
#: `METHOD_FILE`'s impact categories, and a recovery target. Ticket 170: a record the referee
#: refuses is never saved, so the one-door walk, whose point is that stage 4 is answered and saved,
#: needs an interview that yields a record the referee passes. TESTIMONY alone yields none (no
#: scores, no RTO), which the old walk saved anyway. Its Teams sentence is left out so the whole file
#: still fits inside `interview.PREVIEW`, which the binding scenario reads it back through.
SCORED_TESTIMONY = (
    "---\ndepartment: {process}\n---\n\n# {process} interview\n\n"
    "Tim: if the ticket system stops we take incidents by phone and keep a local incident log.\n"
    "Tim: RTO: 8 h for {process}.\n"
    "Tim: Impact operational: 1 h 1, 2 h 1, 4 h 2, 8 h 3, 24 h 4, 72 h 5, 168 h 5.\n"
    "Tim: Impact legal: 1 h 1, 2 h 1, 4 h 1, 8 h 2, 24 h 3, 72 h 4, 168 h 5.\n")


def _interview_file(ctx, home, name, testimony=TESTIMONY):
    target = ctx["room_folder"] / home / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(testimony.format(process=ctx["process"]), encoding="utf-8")
    return target


def _reach_stage_2(ctx):
    """Stage 2 as the walk serves it: whatever follows the card stage 1 left on disk.

    Never by asking for stage 2 — there is nowhere to ask (ADR-0010), and the point of reading it
    off the room is that the manager gets the stage his walk has actually reached.
    """
    following = onward(ctx["room_folder"], open_bia(ctx["room_folder"], ctx["process"]))
    assert [card.stage for card in following] == [2], "the walk does not serve stage 2 yet"
    ctx["before"] = _files(ctx["room_folder"])
    ctx["card"] = following[0]


def _press_interview(ctx, interview):
    """Press one of the interviews on screen. One the card did not offer was typed, and fails."""
    assert interview in ctx["card"].interviews, f"{interview.name!r} was not on screen to press"
    ctx["acts"].append(("press", interview.name))
    ctx["picked"] = interview
    ctx["card"] = chosen(ctx["room_folder"], ctx["process"], interview.path)


def _stage_card(ctx, stage):
    """The real card for that stage of this walk — the one the skin would put on the screen.

    Walked to rather than asked for, one stage at a time, because there is nowhere to ask for a
    stage by name (ADR-0010): each card is whatever follows the one the room's own record says
    this walk has reached.
    """
    card = open_bia(ctx["room_folder"], ctx["process"])
    while card.stage < stage:
        following = onward(ctx["room_folder"], card)
        if following:
            card = following[0]
            continue
        # Nothing follows a stage nobody has answered, so the walk is carried through the one door
        # — typed words, exactly as a manager would (ADR-0013) — rather than by a step reaching
        # for the per-stage call the door made private.
        ctx["card"] = card
        moved = _said(ctx, ENDORSED)
        assert len(moved) > 1, f"stage {card.stage} was answered and the walk stood still"
        card = moved[-1]
    return card


# ------------------------------------------------------- the interviews the room already holds


@given(parsers.parse('my room holds transcripts under "{home}/"'))
def _my_room_holds_transcripts_under(ctx, home):
    assert home == INTERVIEWS
    for name in ("26_09_01_interview.md", "26_09_02_interview.md"):
        _interview_file(ctx, home, name)
    assert [path for path in _files(ctx["room_folder"]) if path.startswith(home)]


@given(parsers.parse('my room also holds an interview it recorded earlier for "{process}"'))
def _my_room_also_holds_an_interview_it_recorded(ctx, process):
    assert process == ctx["process"]
    _interview_file(ctx, OWNER_INTERVIEWS, f"{process.lower()}-interview-transcript.md")


@given(parsers.parse("my room holds no transcript for this process"))
def _my_room_holds_no_transcript_for_this_process(ctx):
    """Emptied of this process's interviews, and of nothing else: the register still names it, so
    it is still a process the room offers and still reaches a stage 2 card."""
    for home in (INTERVIEWS, OWNER_INTERVIEWS):
        for path in (ctx["room_folder"] / home).glob("*.md"):
            if ctx["process"] in path.read_text(encoding="utf-8"):
                path.unlink()
    assert held(ctx["room_folder"], ctx["process"]) == ()
    written = {path for path in _files(ctx["room_folder"]) - ctx["before"] if "/." not in "/" + path}
    assert not written, f"saved as the company's: {written}"


@given("the transcripts are offered")
@when("I reach stage 2")
def _i_reach_stage_2(ctx):
    _reach_stage_2(ctx)


@then("each transcript is offered with an exact preview of its content")
def _each_transcript_is_offered_with_an_exact_preview(ctx):
    offered = ctx["card"].interviews
    assert offered, "nothing was offered, so nothing was previewed"
    for item in offered:
        text = (ctx["room_folder"] / item.path).read_text(encoding="utf-8")
        assert item.preview, f"{item.name} was offered with no preview"
        assert item.preview in text, "the preview is not this file's own characters"
        assert "the ticket system stops" in item.preview, "the preview reaches no testimony"


@then("I am not asked to type a path")
def _i_am_not_asked_to_type_a_path(ctx):
    """v1 asked for `proposal={"transcript_path": "…"}` here. Nothing types a path now: every
    interview is a thing to press, and the only argument naming one takes a path the card gave."""
    assert ctx["typed"] == ""
    assert ctx["card"].interviews or HOLD_IT_NOW in ctx["card"].buttons
    assert list(inspect.signature(chosen).parameters) == ["room_folder", "process", "path"]
    assert chosen(ctx["room_folder"], ctx["process"], "07_Interviews/typed-by-hand.md") == ctx[
        "card"], "a path the card never offered picked something"


@then("both interviews are offered, each with its own preview")
def _both_interviews_are_offered(ctx):
    """Both homes. An interview the room held itself earlier is evidence exactly as one the
    company already had is (ADR-0002), so neither folder wins and neither is skipped."""
    offered = {item.path: item.preview for item in ctx["card"].interviews}
    for home in (INTERVIEWS, OWNER_INTERVIEWS):
        held = [path for path in _files(ctx["room_folder"]) if path.startswith(f"{home}/")]
        assert held, f"{home} holds nothing, so the scenario would prove nothing"
        for path in held:
            assert offered.get(path), f"{path} is an interview in my room and is not on the card"
            assert offered[path] in (ctx["room_folder"] / path).read_text(encoding="utf-8")


@then("neither is offered twice")
def _neither_is_offered_twice(ctx):
    offered = ctx["card"].interviews
    assert len({item.path for item in offered}) == len(offered)
    assert len({item.name for item in offered}) == len(offered), "two buttons under one name"


# --------------------------------------------------------- one press, and the label after it


@when("I pick one and answer the gradient")
def _i_pick_one_and_answer_the_gradient(ctx):
    _press_interview(ctx, ctx["card"].interviews[0])
    _press_button(ctx, ENDORSED)


@then("the walk records which transcript it rests on, and that transcript's fingerprint")
def _the_walk_records_which_transcript_and_its_fingerprint(ctx):
    bound = _saved(ctx)["transcript"]
    assert bound["path"] == ctx["picked"].path
    assert (ctx["room_folder"] / bound["path"]).is_file(), "the binding names no file in my room"
    assert bound["fingerprint"] == hashlib.sha256(
        (ctx["room_folder"] / bound["path"]).read_bytes()).hexdigest()


@then("I have typed nothing")
def _i_have_typed_nothing(ctx):
    assert ctx["typed"] == ""
    offered = [item.name for item in held(ctx["room_folder"], ctx["process"])]
    assert [kind for kind, _what in ctx["acts"]] == ["open"] + ["press"] * (len(ctx["acts"]) - 1)
    assert all(what in ctx["offered"] + offered + list(GRADIENT) + [AGREE]
               for kind, what in ctx["acts"] if kind == "press")


@then("the only new thing on file is which transcript my walk rests on, and its fingerprint")
def _the_only_new_thing_is_the_binding(ctx):
    assert _new_files(ctx) == set(), "stage 2 put a new file in the room"
    assert set(_saved(ctx)["transcript"]) == {"name", "path", "fingerprint"}


# ------------------------------------------------------ a transcript that changed under me


@given("I bound a transcript at stage 2")
def _i_bound_a_transcript_at_stage_2(ctx):
    _reach_stage_2(ctx)
    _i_pick_one_and_answer_the_gradient(ctx)


@when("its bytes change before stage 3 reads it")
def _its_bytes_change_before_stage_3_reads_it(ctx):
    target = ctx["room_folder"] / ctx["picked"].path
    target.write_text(target.read_text(encoding="utf-8") + "\nTim: two recovery teams, actually.\n",
                      encoding="utf-8")


@then("the change is raised as a finding rather than passing unnoticed")
def _the_change_is_raised_as_a_finding(ctx):
    ctx["findings"] = interview_findings(ctx["room_folder"], ctx["process"])
    assert len(ctx["findings"]) == 1, "the change passed unnoticed"
    # A finding is data, never a wall (`CONTEXT.md`): the walk still serves its card.
    assert open_bia(ctx["room_folder"], ctx["process"]).stage == 1


@then("the finding names the interview I bound")
def _the_finding_names_the_interview_i_bound(ctx):
    assert ctx["picked"].name in ctx["findings"][0]


# ------------------------------------------------------------ a room with no transcript


@then("I am offered the interview in the room instead")
def _i_am_offered_the_interview_in_the_room(ctx):
    assert ctx["card"].interviews == ()
    assert ctx["card"].buttons == (HOLD_IT_NOW,)
    assert "let's do it now" in ctx["card"].body


@then("stage 2 is not blocked")
def _stage_2_is_not_blocked(ctx):
    assert ctx["card"].stage == 2
    assert ctx["card"].buttons and ctx["card"].decision, "a card with nothing to press is a wall"


# ------------------------------------------------------------------- the Source: line


@then("that line names every interview the card offered me")
def _that_line_names_every_interview_offered(ctx):
    named = set(ctx["card"].sources)
    for item in ctx["card"].interviews:
        assert item.path in named, f"{item.name} was offered and is not on the line"
        assert item.path in ctx["card"].source_line


# ------------------------------------------------------------------------- the voice


@when("I read the stage 2 card")
def _i_read_the_stage_2_card(ctx):
    _reach_stage_2(ctx)
    _i_read_the_card(ctx)


@then("it asks me for one decision and not two")
def _it_asks_one_decision_and_not_two(ctx):
    decision = ctx["card"].decision
    assert decision.count("?") == 1, f"two questions on one card: {decision!r}"
    assert " and " not in decision, "two asks stacked into one sentence"


# --------------------------------------------------------- the four labels, and stage 1's one


@then("the card offers exactly these four ways to answer it:")
def _the_card_offers_exactly_these_four_ways(ctx, datatable):
    assert [row[0] for row in datatable] == list(GRADIENT)
    assert ctx["card"].buttons == GRADIENT


@then('it offers me no fifth way, and no "not sure"')
def _no_fifth_way_and_no_not_sure(ctx):
    assert len(ctx["card"].buttons) == 4
    assert "not sure" not in " ".join(ctx["card"].buttons).lower()


@given(parsers.parse('I have opened the BIA for "{process}" and not agreed its scope'))
def _i_have_opened_the_bia_and_not_agreed_its_scope(ctx, process):
    _on_the_menu(ctx, process)
    _open_room(ctx)
    _press_process(ctx, process)
    assert AGREE in ctx["card"].buttons, "this scope is already agreed"


@when("I read that card")
def _i_read_that_card(ctx):
    _i_read_the_card(ctx)


@then("the four labels are not drawn on it")
def _the_four_labels_are_not_drawn_on_it(ctx):
    """ADR-0011, the owner's ruling of 2026-09-12. Stage 1 confirms the scope the room read off
    the company's files: there is no figure yet, and nothing to hold a reservation about. The
    labels still ride in the record underneath — `gradient` is structure, not controls."""
    card = ctx["card"]
    assert card.buttons == (AGREE,)
    assert [label for label in GRADIENT if label in card.screen] == []
    assert card.gradient == GRADIENT


@then(parsers.parse('what my walk records underneath is "{label}"'))
def _what_my_walk_records_underneath(ctx, label):
    assert label in GRADIENT
    assert _saved(ctx)["decisions"][-1]["gradient"] == label


# ------------------------------------------ the door ticket 09 built, in the live card path


@given(parsers.parse("the stage {stage:d} card says a figure the record does not hold"))
def _the_stage_card_says_a_figure_the_record_does_not_hold(ctx, walk, stage):
    """The real card for that stage, with one softened figure put into its prose.

    The break is in the prose the generator writes, which is what `render` is asked about: "about
    a working day" is `docs/voice.md` §4.4's own example of a card softening a figure the record
    holds as a figure.
    """
    walk["record"] = NINE_RECORD
    walk["card"] = _stage_card(ctx, stage).screen + " That's about a working day."
    walk["stage"] = stage


@when("that card would be put in front of me")
def _that_card_would_be_put_in_front_of_me(ctx, walk):
    """Exactly what the skin does before it sends anything: the one door, and nothing past it."""
    try:
        walk["rendered"] = render(walk["stage"], walk["card"], walk["record"])
    except CardGeneratorBug as bug:
        walk["bug"] = bug


@then("no card is rendered at all")
def _no_card_is_rendered_at_all(walk):
    assert isinstance(walk["bug"], CardGeneratorBug), "the card was not refused"
    assert walk["rendered"] is None, "a refused card was rendered anyway"


@then("it does not appear as an open item on my card")
def _it_does_not_appear_as_an_open_item_on_my_card(walk):
    """A manager cannot fix a card generator, so it is never put to him as something to resolve."""
    assert walk["rendered"] is None
    assert "finding" not in str(walk["bug"]).lower()


# ═════════════ 22 — a prefix link mints a credential for a room called `r` ═══════════════════════
#
# `features/a-prefix-link-mints-a-credential-for-a-room-called-r.feature`. The door is the real one
# — the phone app's auth callback, `room`, over `skin_harness.py` (ticket 164) — because the two
# refusals this story is about are made in two different places and only the skin runs both:
# `identity_from_link` refuses a link that carries no room code, and `checked_room_folder` refuses
# a room that has none.
# What an operator reads is the app's own console output, captured here as the journal.

#: A room code carrying an encoded separator. Nothing decodes it, so it is one literal segment.
CODE_WITH_ENCODED_SEPARATOR = "..%2F..%2Fetc"

#: What a fault leaking onto the page would read as. `docs/voice.md` §3.1 keeps all of it off.
FAULT_WORDS = ("Traceback", "Refused", "identity_from_link")


def _the_rooms_folder_is_on_disk(ctx):
    """Whether this scenario has minted rooms, which is what decides how much of the door runs.

    A scenario that has put a rooms folder on disk (ticket 22) is asking about the whole door — the
    link, and then the folder behind it — so it goes through the skin, where both checks are. One
    that has not is asking about the link alone, which `nemo.door` answers with no disk at all.
    """
    return "rooms" in ctx


def _present(ctx, skin, capsys, link):
    """Present a scanned link at the door, and keep what came of it: the identity and the journal.

    The journal accumulates because a scenario presents more than one link and the two refusals are
    read against each other. What is on screen is not kept: `SENT` is already the record.
    """
    ctx["identity"] = skin_harness.scan(link)
    ctx["log"] = ctx.get("log", "") + capsys.readouterr().out


def _one_line(ctx, about):
    """The one line of the journal that says this, so "one sentence" is counted, not assumed."""
    lines = [line for line in ctx["log"].splitlines() if about in line]
    assert len(lines) == 1, f"the journal says {about!r} {len(lines)} times: {ctx['log']!r}"
    return lines[0]


def _tree(root):
    """Everything under a folder, by name — what would change if anything were read or written."""
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


@given(parsers.parse('the rooms folder holds "{first}" and "{second}"'))
def _the_rooms_folder_holds(ctx, skin, first, second):
    for room in (first, second):
        _seed(ctx, skin, room)
    ctx["rooms"] = skin.ROOMS


@given("the rooms folder is not there at all")
def _the_rooms_folder_is_not_there(ctx, skin):
    """The mount away, which is the cost of checking the disk and must read as its own event."""
    shutil.rmtree(skin.ROOMS)
    ctx["rooms"] = skin.ROOMS


@when(parsers.re(r'a scan presents the link "(?P<link>.*)"'))
def _a_scan_presents_the_link(ctx, skin, capsys, link):
    _present(ctx, skin, capsys, link)


@when(parsers.parse('a scan presents the room link prefix "{prefix}" with nothing after it'))
def _a_scan_presents_the_prefix(ctx, skin, capsys, prefix):
    assert prefix.rstrip("/").endswith(f"/{PREFIX_SEGMENT}"), f"{prefix!r} is not the prefix"
    _present(ctx, skin, capsys, prefix)


@when("a scan presents a room code with an encoded separator in it")
def _a_scan_presents_an_encoded_separator(ctx, skin, capsys):
    ctx["outside"] = _tree(skin.ROOMS.parent)
    _present(ctx, skin, capsys, f"/demo/r/{CODE_WITH_ENCODED_SEPARATOR}")


@then("I am refused")
def _i_am_refused(ctx):
    assert ctx["identity"] is None, f"the door made an identity: {ctx['identity']}"


@then("no access token is minted for me")
def _no_access_token_is_minted(ctx):
    """The link is the whole credential (ADR-0003), so no identity is no token and no room."""
    assert ctx["identity"] is None
    assert skin_harness.app.cl.user_session.get("user") is None
    assert _on_screen() == [], "a refused scan was greeted by a room"


@then("the operator's log carries one sentence about a link that carries no room code")
def _the_log_carries_the_link_sentence(ctx):
    ctx["link_sentence"] = _one_line(ctx, "carries no room code")


@then("a different sentence about a room that has no folder")
def _the_log_carries_the_folder_sentence(ctx):
    ctx["folder_sentence"] = _one_line(ctx, "has no folder")


@then("neither refusal is worded as the other")
def _neither_refusal_is_worded_as_the_other(ctx):
    """A damaged scan and an absent mount are acted on differently, so they read differently."""
    link, folder = ctx["link_sentence"], ctx["folder_sentence"]
    assert link != folder
    assert "has no folder" not in link and "carries no room code" not in folder


@then("the operator's log says the room has no folder")
def _the_log_says_the_room_has_no_folder(ctx):
    _one_line(ctx, "has no folder")


@then("it does not say my link carries no room code")
def _the_log_does_not_say_the_link_carries_no_room_code(ctx):
    assert "carries no room code" not in ctx["log"]


@then("nothing outside the rooms folder is read or written")
def _nothing_outside_the_rooms_folder(ctx, skin):
    """One segment is the whole property: `%2F` is not decoded, so `ROOMS / room` cannot leave."""
    assert (skin.ROOMS / CODE_WITH_ENCODED_SEPARATOR).parent == skin.ROOMS
    assert _tree(skin.ROOMS.parent) == ctx["outside"]


@then(parsers.parse('the rooms folder still holds exactly "{first}" and "{second}"'))
def _the_rooms_folder_still_holds_exactly(ctx, skin, first, second):
    assert skin_harness.room_names(skin.ROOMS) == sorted([first, second])


@then("what I read carries no stack trace")
def _what_i_read_carries_no_stack_trace(ctx):
    """Chainlit answers 401 with its own page; nemo puts nothing of its own on it."""
    read = "\n".join(_on_screen())
    assert not [word for word in FAULT_WORDS if word in read]
    assert ctx["log"].strip(), "the refusal was silent, so the operator has nothing to read either"


@then("it carries no room code, path or field name")
def _what_i_read_carries_no_machine_identifier(ctx):
    """`docs/voice.md` §3.1. The identifiers go to the journal, which is not a thing a human reads
    on the day: the manager is shown nothing at all rather than shown it carefully."""
    assert _on_screen() == [], "a refused scan was given something to read"
    assert "'/demo/r/'" in ctx["log"], "the link reached nobody at all, operator included"


# ═══════════════════════════ 14 — stage 3, the evidence standardised ════════════════════════════
#
# `features/stage-3-standardise-the-interview-evidence.feature`. The server drafts the evidence out
# of the transcript the manager bound at stage 2 and shows him its own working, so every step below
# is read off the room the earlier stages actually built: the transcript is a file this walk rests
# on and its fingerprint is on the record, and the register the ids resolve against is the room's
# own. Nothing here fabricates a card, because the thing this story is about is the card the walk
# serves without being asked (ADR-0010).
#
# The one exception is `a run that argued with three cards`, which builds a record rather than
# pressing one: `report` is a pure function over a finished run's decisions and there are three
# argued cards only once stages 4 and 5 exist to press.

#: The interview this walk rests on, as a company writes one. Every scenario's Given is a sentence
#: of it, so each of them asserts what it names is really in here rather than assuming it.
EVIDENCE_TRANSCRIPT = """---
department: Incident and problem management
covered: operational
not elicited: we ran out of time before the legal side of it
---

# Incident and problem management interview

Marek Sobotta: MTPD: 24 h for incident and problem management.
Marek Sobotta: RPO: <24 h.
Marek Sobotta: MBCO: two lead incident managers and one manager on duty.
Tim Ohlsen: RTO: 8 h for major incidents, which we have held to.
Tim Ohlsen: RTO: for problem management we never settled one.
Marek Sobotta: Depends on: Atlassian Jira, Cisco Call Manager (IT helpdesk and support).
Marek Sobotta: Depends on: mobile telephony.
"""

EVIDENCE_FILE = "26_08_00_interview.md"

#: What the room's dependency register models. `KA-09` is the lookalike: a name two words longer
#: than the one the interview used, which a nearest-match resolver would happily settle on.
EVIDENCE_ASSETS = {
    "KA-01": {"name": "Atlassian Jira", DEPARTMENT: "Incident and problem management"},
    "KA-02": {"name": "Cisco Call Manager", DEPARTMENT: "Incident and problem management"},
    "KA-09": {"name": "Atlassian Jira Service Management",
              DEPARTMENT: "Incident and problem management"},
}

#: The dependency the register does not model, in the words the interview used for it.
UNMODELLED_DEPENDENCY = "mobile telephony"

#: The one the interview and the register disagree about who owns.
DISPUTED_DEPENDENCY = "Cisco Call Manager"

#: What a manager types when he disagrees. The feature names this sentence, so it is one constant.
NAMED = "Marek gave me 6 h for that line last week, not 8"


def _evidence_in_the_room(ctx):
    """The interview and the register stage 3 reads, put in the room the way a company's are."""
    (ctx["room_folder"] / INTERVIEWS / EVIDENCE_FILE).write_text(
        EVIDENCE_TRANSCRIPT, encoding="utf-8")
    register = ctx["room_folder"] / REGISTER
    register.write_text(json.dumps({**json.loads(register.read_bytes()), **EVIDENCE_ASSETS}),
                        encoding="utf-8")


def _bind_the_transcript(ctx):
    """Stage 2, pressed rather than written: the interview on the card, and one of the labels."""
    _reach_stage_2(ctx)
    _press_interview(ctx, ctx["card"].interviews[0])
    _press_button(ctx, ENDORSED)
    ctx["before"] = _files(ctx["room_folder"])


def _transcript(ctx):
    """The characters the walk rests on, read back off the file its fingerprint was taken over."""
    return (ctx["room_folder"] / _saved(ctx)["transcript"]["path"]).read_text(encoding="utf-8")


def _draft(ctx):
    """The stage 3 card this walk serves — whatever follows the stage the record has reached."""
    ctx["card"] = _stage_card(ctx, STAGE_3)
    return ctx["card"]


def _walk_again(ctx):
    """This walk begun again from stage 1, stopped at the stage 3 card it serves.

    The background walks to stage 4 and accepts it, and the one door answers whatever the walk is
    waiting on rather than whatever card a step happens to hold (ADR-0013) — so there is no longer
    any reaching back for a stage this walk is past, which is the point of the door. A manager who
    wants an earlier card answered differently walks it again, so a step that needs one does too.
    """
    shutil.rmtree(ctx["room_folder"] / RUNS)
    _press_process(ctx, ctx["process"])
    _press_button(ctx, AGREE)
    _bind_the_transcript(ctx)
    return _draft(ctx)


def _rebound_on(ctx, transcript):
    """The same walk again over a different transcript, every stage of it pressed as before.

    A bound transcript whose bytes change is a finding (ticket 12), so a scenario that needs the
    header to say something else cannot edit the file under the walk: it walks a new one.
    """
    shutil.rmtree(ctx["room_folder"] / RUNS)
    (ctx["room_folder"] / INTERVIEWS / EVIDENCE_FILE).write_text(transcript, encoding="utf-8")
    _press_process(ctx, ctx["process"])
    _press_button(ctx, AGREE)
    _bind_the_transcript(ctx)
    return _draft(ctx)


def _proposed(ctx, key):
    """One part of the draft the card is showing, before anything has been pressed."""
    return _draft(ctx).proposal[key]


def _statements(ctx, label=None):
    """What the draft asserts, all of it or only under one of the method's labels."""
    return [item for item in _proposed(ctx, "evidence")
            if label is None or item["label"] == label]


def _endorse(ctx):
    """The one tap that answers the card, with the draft it was showing kept to compare against."""
    _draft(ctx)
    ctx["proposal"] = ctx["card"].proposal
    _press_button(ctx, ENDORSED)


def _type(ctx, words):
    """The composer, driven the way the skin drives it: the walk's box, or the manager's own.

    `nemo.walk.answer` is the whole of that decision — a card back means the walk took the
    words, and an empty answer means nothing in this room was waiting for them and they are a
    question for the ask lane.
    """
    ctx["typed"] = words
    ctx["acts"].append(("type", words))
    answered = _said(ctx, words)
    taken = answered[0] if answered else None
    if taken is not None:
        ctx["card"] = taken
    ctx["taken"] = taken
    return taken


# ------------------------------------------------------------- the transcript this walk rests on


@given("I bound an interview transcript to this walk at stage 2")
def _i_bound_an_interview_transcript_at_stage_2(ctx):
    _evidence_in_the_room(ctx)
    _bind_the_transcript(ctx)


@given("an approved transcript")
def _an_approved_transcript(ctx):
    """Approved is what the stage 2 press means: this is the interview the BIA rests on."""
    bound = _saved(ctx)["transcript"]
    assert bound["fingerprint"] == hashlib.sha256(
        (ctx["room_folder"] / bound["path"]).read_bytes()).hexdigest()
    assert without_telemetry(_saved(ctx)["decisions"][-1]) == {"stage": 2, "gradient": ENDORSED}


@given(parsers.parse('the transcript says "RTO:" for problem management and never gives a figure'))
def _the_transcript_says_rto_with_no_figure(ctx):
    assert "RTO: for problem management we never settled one." in _transcript(ctx)


@given("the transcript holds Marek Sobotta's MTPD for incident and problem management")
def _the_transcript_holds_mareks_mtpd(ctx):
    assert "Marek Sobotta: MTPD: 24 h for incident and problem management." in _transcript(ctx)


@given("the transcript names a dependency the register holds")
def _the_transcript_names_a_dependency_the_register_holds(ctx):
    assert "Depends on: Atlassian Jira" in _transcript(ctx)
    held_names = [entry["name"] for entry in EVIDENCE_ASSETS.values()]
    assert "Atlassian Jira" in held_names


@given("the transcript names a dependency absent from the register")
def _the_transcript_names_a_dependency_absent_from_the_register(ctx):
    assert UNMODELLED_DEPENDENCY in _transcript(ctx)
    register = json.loads((ctx["room_folder"] / REGISTER).read_bytes())
    assert UNMODELLED_DEPENDENCY not in [entry.get("name") for entry in register.values()
                                         if isinstance(entry, dict)]
    _draft(ctx)


@given("the transcript contradicts the register about who owns Cisco Call Manager")
def _the_transcript_contradicts_the_register(ctx):
    assert f"{DISPUTED_DEPENDENCY} (IT helpdesk and support)" in _transcript(ctx)
    assert EVIDENCE_ASSETS["KA-02"][DEPARTMENT] == "Incident and problem management"


@given("the interview did not reach some impact categories")
def _the_interview_did_not_reach_some_categories(ctx):
    """The header says which it covered; what the method asks about and it does not name is what
    the interview never reached, and there is at least one of those or this proves nothing."""
    assert "covered: operational" in _transcript(ctx)
    unreached = _proposed(ctx, "worst_case")
    assert set(unreached) == {"legal"}, unreached


@given("the transcript header gives no reason for it")
def _the_transcript_header_gives_no_reason(ctx):
    silent = "\n".join(line for line in EVIDENCE_TRANSCRIPT.splitlines()
                       if not line.startswith("not elicited:"))
    _rebound_on(ctx, silent)
    assert "not elicited" not in _transcript(ctx)


# ------------------------------------------------------------------------ the card it drafts


@given("the stage 3 card")
@given("I agree with everything on the stage 3 card")
@when("the stage 3 card is drafted")
@when("I reach stage 3")
def _the_stage_3_card(ctx):
    _draft(ctx)


@when("I read the stage 3 card")
def _i_read_the_stage_3_card(ctx):
    _draft(ctx)
    _i_read_the_card(ctx)


@when("I read the open items on my card")
def _i_read_the_open_items(ctx):
    ctx["open_items"] = _proposed(ctx, "open_items")
    assert ctx["open_items"], "the card puts nothing open in front of me"


@then("an RTO is asserted only where a label and a value co-occur")
def _an_rto_is_asserted_only_where_a_label_and_a_value_co_occur(ctx):
    """Two lines say `RTO:` and one of them gives a figure, so exactly one RTO is asserted."""
    assert _transcript(ctx).count("RTO:") == 2
    assert [item["value"] for item in _statements(ctx, "RTO")] == ["8 h"]


@then("MTPD, RPO and MBCO are marked owner-stated with the quote beside them")
def _the_three_are_marked_owner_stated(ctx):
    for label in ("MTPD", "RPO", "MBCO"):
        stated = _statements(ctx, label)
        assert len(stated) == 1, f"{label} is stated {len(stated)} times"
        assert stated[0]["owner_stated"], f"{label} is not put in the owner's mouth"
        assert stated[0]["quote"] in _transcript(ctx), "the quote is not the transcript's own"
        assert stated[0]["quote"] in ctx["card"].body, f"{label}'s quote is not beside it"


@then("it is raised as a finding")
def _it_is_raised_as_a_finding(ctx):
    raised = [item for item in _proposed(ctx, "open_items") if UNMODELLED_DEPENDENCY in item]
    assert len(raised) == 1, "the unmodelled dependency passed unnoticed"
    # A finding is data, never a wall (`CONTEXT.md`): the card is still served and still answerable.
    assert ctx["card"].buttons == GRADIENT


@then("no asset id is invented for it")
def _no_asset_id_is_invented_for_it(ctx):
    unmodelled = [item for item in _proposed(ctx, "dependencies")
                  if item["heard"] == UNMODELLED_DEPENDENCY]
    assert [item["asset_id"] for item in unmodelled] == [""]
    raised = [item for item in _proposed(ctx, "open_items") if UNMODELLED_DEPENDENCY in item]
    assert "KA-" not in raised[0], "an id was put on the dependency the register does not model"


@then("the worst case is proposed as all-unknown for those categories")
def _the_worst_case_is_all_unknown(ctx):
    proposed = _proposed(ctx, "worst_case")
    assert proposed == {"legal": UNKNOWN}
    assert set(proposed.values()) == {UNKNOWN}, "something was proposed where nothing was asked"


@then("the not-elicited acknowledgement is pre-filled from the transcript header")
def _the_acknowledgement_is_pre_filled(ctx):
    reason = "we ran out of time before the legal side of it"
    assert f"not elicited: {reason}" in _transcript(ctx)
    assert _proposed(ctx, "not_elicited") == reason
    assert reason in ctx["card"].body, "the card does not show me what it read"


@then("no RTO is asserted for that activity")
def _no_rto_is_asserted_for_that_activity(ctx):
    assert [item["quote"] for item in _statements(ctx, "RTO")] == [
        "Tim Ohlsen: RTO: 8 h for major incidents, which we have held to."]


@then("nothing on the card reads as though a target had been stated")
def _nothing_reads_as_though_a_target_had_been_stated(ctx):
    body = _draft(ctx).body
    assert "problem management we never settled one" not in body
    assert "never settled" not in body, "the card repeats a non-answer as though it were one"


@then("the figure is marked owner-stated")
def _the_figure_is_marked_owner_stated(ctx):
    assert _statements(ctx, "MTPD")[0]["owner_stated"]


@then("his sentence is beside it, word for word as the transcript holds it")
def _his_sentence_is_beside_it(ctx):
    stated = _statements(ctx, "MTPD")[0]
    assert stated["speaker"] == "Marek Sobotta"
    assert stated["quote"] in _transcript(ctx)
    assert stated["quote"] in ctx["card"].body


@then("the figure is exactly the string the transcript holds, neither rounded nor sharpened")
def _the_figure_is_exactly_the_string_the_transcript_holds(ctx):
    assert _statements(ctx, "MTPD")[0]["value"] == "24 h"
    for softened in ("a day", "about 24", "roughly", "24h", "24 hours"):
        assert softened not in ctx["card"].body, f"the card says {softened!r}"


@then("that dependency resolves to the register's exact asset id")
def _that_dependency_resolves_to_the_exact_asset_id(ctx):
    resolved = [item for item in _proposed(ctx, "dependencies")
                if item["heard"] == "Atlassian Jira"]
    assert [item["asset_id"] for item in resolved] == ["KA-01"]


@then("no near-match or lookalike id is used for it")
def _no_near_match_id_is_used(ctx):
    assert EVIDENCE_ASSETS["KA-09"]["name"].startswith("Atlassian Jira")
    assert "KA-09" not in str(ctx["card"].proposal), "the lookalike was resolved to"


@then("one of them is the dependency, in the words the transcript used for it")
def _one_of_them_is_the_dependency_in_its_own_words(ctx):
    named = [item for item in ctx["open_items"] if UNMODELLED_DEPENDENCY in item]
    assert len(named) == 1
    ctx["open_item"] = named[0]


@then("it says the register does not model it")
def _it_says_the_register_does_not_model_it(ctx):
    assert "does not model it" in ctx["open_item"]


@then("it is an open item I would be accepting at sign-off, not a wall")
def _it_is_an_open_item_not_a_wall(ctx):
    assert "accepting at sign-off" in ctx["open_item"]
    assert _draft(ctx).buttons == GRADIENT, "the card cannot be answered, so it is a wall"


@then("the first thing the card puts in front of me is that contradiction")
def _the_first_thing_is_the_contradiction(ctx):
    body = _draft(ctx).body
    assert body.startswith(LEAD)
    leading = body[len(LEAD):body.index(SETTLED)]
    assert DISPUTED_DEPENDENCY in leading.split("\n\n")[1]
    assert "IT helpdesk and support" in leading and "Incident and problem management" in leading


@then("what is already settled comes after it, or not at all")
def _what_is_settled_comes_after(ctx):
    body = ctx["card"].body
    assert body.index(DISPUTED_DEPENDENCY) < body.index(SETTLED)
    assert body.index(SETTLED) < body.index("24 h"), "a settled figure came before the decision"


# ------------------------------------------------- the fold: one tap, and no invented reason


@then("I am not offered three options for why they were not elicited")
def _i_am_not_offered_three_options(ctx):
    """Withdrawn, not deferred (owner, 2026-09-12). The card offers the four labels and no more,
    so there is no second control on it and nothing to tap about the transcript's own header."""
    assert ctx["card"].buttons == GRADIENT
    assert ctx["card"].decision.count("?") == 1, "the card asks me two things"


@then("I am not asked to ratify a fact about a document I did not write")
def _i_am_not_asked_to_ratify_a_fact(ctx):
    prose = ctx["prose"]
    for asking in ("why", "Why", "choose", "select", "which of"):
        assert asking not in prose.replace("Word for word", ""), f"the card asks me to {asking!r}"


@when("I endorse the card")
@when("I endorse the stage 3 card")
def _i_endorse_the_card(ctx):
    _endorse(ctx)


@then(parsers.parse('what the walk records as the reason is "{reason}"'))
def _what_the_walk_records_as_the_reason(ctx, reason):
    assert reason == NOT_STATED
    assert _saved(ctx)["not_elicited"] == NOT_STATED


@then("no reason is invented at the card to stand in for it")
def _no_reason_is_invented_at_the_card(ctx):
    assert NOT_STATED in ctx["proposal"]["not_elicited"]
    assert "ran out of time" not in str(ctx["proposal"]), "a reason was carried from another run"


@then("stage 3 is answered")
@then("stage 3 is already answered")
def _stage_3_is_answered(ctx):
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_3


@then("I have typed nothing at all")
def _i_have_typed_nothing_at_all(ctx):
    assert ctx["typed"] == ""
    assert [kind for kind, _what in ctx["acts"]] == ["open"] + ["press"] * (len(ctx["acts"]) - 1)


@then("the endorsed proposal is in the run state")
def _the_endorsed_proposal_is_in_the_run_state(ctx):
    saved = _saved(ctx)
    assert {key: saved[key] for key in ctx["proposal"]} == ctx["proposal"]
    assert without_telemetry(saved["decisions"][-1]) == {"stage": STAGE_3, "gradient": ENDORSED}


# --------------------------------------------------- where a reservation is named: the composer


@then("the card says the next thing I type is what I am reserving")
def _the_card_says_the_next_thing_i_type(ctx):
    assert ctx["card"].body == NAMING
    assert "next thing you type is what you are reserving" in ctx["card"].body


@then("it says the box is the walk's for now, not the place I ask questions")
def _it_says_the_box_is_the_walks(ctx):
    assert "belongs to this BIA rather than to your questions" in ctx["card"].body


@when(parsers.parse('I press "{label}" and type nothing'))
def _i_press_and_type_nothing(ctx, label):
    _press_button(ctx, label)
    assert ctx["typed"] == ""


@then("the walk has moved on rather than sitting waiting for characters")
def _the_walk_has_moved_on(ctx):
    assert ctx["typed"] == "", "something was typed, so this proves nothing"
    assert ctx["card"].buttons == (), "the card is still asking to be answered"
    assert _saved(ctx)["decisions"][-1]["naming"] == UNNAMED


@given(parsers.parse('I pressed "{label}" and typed nothing'))
def _i_pressed_and_typed_nothing(ctx, label):
    _draft(ctx)
    _press_button(ctx, label)


@given(parsers.parse('I pressed "{label}" at stage 3'))
@given(parsers.parse('I pressed "{label}" and the card is waiting for the naming'))
def _i_pressed_at_stage_3(ctx, label):
    _draft(ctx)
    _press_button(ctx, label)
    assert ctx["card"].body == NAMING, "the card is not waiting for a naming"


@given("I named a reservation at stage 3")
@given("I typed the naming for my stage 3 reservation")
def _i_named_a_reservation_at_stage_3(ctx):
    _draft(ctx)
    _press_button(ctx, "needs discussion")
    assert _type(ctx, NAMED) is not None
    ctx["record_bytes"] = (ctx["room_folder"] / run_file(ctx["process"])).read_bytes()


@when(parsers.parse('I answer "{label}" and name what I disagree with'))
def _i_answer_and_name_what_i_disagree_with(ctx, label):
    _draft(ctx)
    _press_button(ctx, label)
    assert _type(ctx, NAMED) is not None, "the walk did not take the words as the naming"


@then("my words are kept verbatim and carried forward to the signature")
def _my_words_are_kept_verbatim_and_carried_forward(ctx):
    """Whichever stage the reservation was pressed on: stage 4 reuses stage 3's composer, and a
    scenario that has only pressed it types into it here, which is the whole of the contract."""
    if not ctx["typed"]:
        assert _type(ctx, NAMED) is not None, "the walk is not holding the composer for me"
    assert namings(_saved(ctx)) == ((ctx["card"].stage, NAMED),)


@then("the walk continues rather than refusing")
def _the_walk_continues_rather_than_refusing(ctx):
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_3, "the disagreement was not recorded"
    assert ctx["card"].body == TAKEN, "the walk answered the disagreement with a refusal"
    assert open_bia(ctx["room_folder"], ctx["process"]).stage == 1, "the room stopped serving me"


@when("I reach the signature")
def _i_reach_the_signature(ctx):
    ctx["carried"] = namings(_saved(ctx))


@then("that answer shows as unnamed")
def _that_answer_shows_as_unnamed(ctx):
    assert ctx["carried"] == ((STAGE_3, UNNAMED),)


@then("it has not been rounded up to an endorsement")
def _it_has_not_been_rounded_up(ctx):
    assert _saved(ctx)["decisions"][-1]["gradient"] != ENDORSED
    assert [words for _stage, words in ctx["carried"] if words == ENDORSED] == []


@then("it was not refused either")
def _it_was_not_refused_either(ctx):
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_3, "the answer was not recorded at all"
    assert not _sees_no_naming(ctx), "the naming can no longer be given"


@when(parsers.parse('I type "{words}"'))
def _i_type(ctx, asked, words):
    """The composer with both claimants live: the walk first, and the lane only if it declines.

    One step for the two of them because the box is one box (ADR-0013). Which of them took the
    words is `nemo.walk.answer`'s single decision — an empty answer means nothing in this room was
    waiting for them — so a scenario asserts what it got rather than choosing a lane up front.
    """
    if _type(ctx, words) is None:
        ctx["lane"] = _ask(asked, words)
    ctx["taken"] = ctx.get("taken")


@when("I type my sentence")
def _i_type_my_sentence(ctx, asked):
    _type(ctx, NAMED)


@then("those words are attached to my stage 3 answer")
def _those_words_are_attached_to_my_stage_3_answer(ctx):
    assert namings(_saved(ctx)) == ((STAGE_3, ctx["typed"]),)


@then("they are stored exactly as I typed them, not tidied or summarised")
def _they_are_stored_exactly_as_typed(ctx):
    assert json.dumps(ctx["typed"])[1:-1] in (
        ctx["room_folder"] / run_file(ctx["process"])).read_text(encoding="utf-8")


@then("my sentence appears there verbatim")
def _my_sentence_appears_there_verbatim(ctx):
    assert [words for _stage, words in ctx["carried"]] == [NAMED]


@then("it is attributed to the stage 3 card I pressed it on")
def _it_is_attributed_to_the_stage_3_card(ctx):
    assert [stage for stage, _words in ctx["carried"]] == [STAGE_3]


@then("it is taken as the naming")
def _it_is_taken_as_the_naming(ctx):
    assert ctx["taken"] is not None and ctx["taken"].body == TAKEN
    assert namings(_saved(ctx)) == ((STAGE_3, NAMED),)


@then("the guidance is not searched, and I am not answered as though I had asked a question")
def _the_guidance_is_not_searched(ctx, asked):
    assert asked["requests"] == [], "the lane was called while the walk held the box"
    assert asked["answers"] == []


@when("I ask what MTPD means")
def _i_ask_what_mtpd_means(ctx, asked):
    """The same box, once the walk has let go of it: nothing is waiting, so it is a question."""
    assert _type(ctx, MTPD_QUESTION) is None, "the walk took a question as a naming"
    _ask(asked, MTPD_QUESTION)


@then("I am answered from the guidance")
def _i_am_answered_from_the_guidance(asked):
    assert _answer(asked).citations, "the answer rests on no corpus chunk"
    assert _answer(asked).text == _recorded_answer()


@then("my BIA has not moved because I asked")
def _my_bia_has_not_moved_because_i_asked(ctx):
    assert (ctx["room_folder"] / run_file(ctx["process"])).read_bytes() == ctx["record_bytes"]


# ------------------------------------------------------------- both facts about an argued run


@given("a run that argued with three cards")
def _a_run_that_argued_with_three_cards(ctx):
    """Three argued cards, as a finished run records them. Built rather than pressed: stages 4
    and 5 do not exist to press yet, and `report` reads a record and nothing else."""
    ctx["run"] = {"decisions": [
        {"stage": stage, "gradient": "needs discussion", "naming": NAMED} for stage in (3, 4, 5)]}


@when("the run is reported")
def _the_run_is_reported(ctx):
    ctx["reported"] = report(ctx["run"])


@then("it is reported as a better BIA")
def _it_is_reported_as_a_better_bia(ctx):
    assert "better BIA" in ctx["reported"]
    assert "3" in ctx["reported"], "it does not say how many cards were argued with"


@then("it is reported as a longer one")
def _it_is_reported_as_a_longer_one(ctx):
    assert "longer walk" in ctx["reported"]


@then("neither fact is left out to make the other look tidier")
def _neither_fact_is_left_out(ctx):
    assert ctx["reported"].index("better BIA") < ctx["reported"].index("longer walk")
    assert report({"decisions": []}) != ctx["reported"], "every run is reported the same way"


# ------------------------------------------------------------------ the rest of the rules hold


@then("the reason comes before the figure")
def _the_reason_comes_before_the_figure(ctx):
    """`docs/voice.md`: a figure lands where the sentence has already said why it stands."""
    for stated in _statements(ctx):
        said = [part for part in ctx["card"].body.split("\n\n") if stated["quote"] in part][0]
        assert said.index("so ") < said.index(stated["value"]), said


@then("that line names the transcript I bound and the register it resolved against")
def _that_line_names_the_transcript_and_the_register(ctx):
    named = set(ctx["card"].sources)
    assert _saved(ctx)["transcript"]["path"] in named
    assert REGISTER in named


# ═══════════════════════════ 15 — stage 4a, the refereed record ══════════════════════════════════
#
# `features/stage-4a-the-refereed-record.feature`. Every step walks the real stages: the scope
# agreed, an interview bound, the evidence endorsed, and then the card the walk serves on its own
# (ADR-0010). The record that lands is therefore the one a manager could have pressed his way to,
# which is the whole of what this story is about — a walk may only close over its own work.

#: The interview stage 4's record is built out of. It scores the one impact category the room's
#: method names across every horizon the method names, because a horizon no lens scored is a gap
#: the referee refuses rather than a cell it fills in.
REFEREED_TRANSCRIPT = """---
department: Incident and problem management
covered: operational
not elicited: we ran out of time before the legal side of it
---

# Incident and problem management interview

Marek Sobotta: MTPD: 24 h for incident and problem management.
Marek Sobotta: RPO: <24 h.
Tim Ohlsen: RTO: 8 h for major incidents.
Marek Sobotta: Impact operational: 1 h 1, 2 h 2, 4 h 2, 8 h 3, 24 h 4, 72 h 5, 168 h 5.
Marek Sobotta: Depends on: Atlassian Jira, mobile telephony.
"""

#: The same interview with a grid that never reaches the method's intolerable level, and with no
#: MTPD stated in it either: a run where nobody derived a figure and nobody was told one.
GENTLE_TRANSCRIPT = "\n".join(
    line for line in REFEREED_TRANSCRIPT.replace("24 h 4, 72 h 5, 168 h 5",
                                                 "24 h 3, 72 h 3, 168 h 3").splitlines()
    if not line.startswith("Marek Sobotta: MTPD:"))

#: A grid whose worst case improves with time, which the referee raises as a finding and passes.
FALLING_TRANSCRIPT = "\n".join(
    line for line in REFEREED_TRANSCRIPT.replace("8 h 3, 24 h 4, 72 h 5, 168 h 5",
                                                 "8 h 3, 24 h 5, 72 h 4, 168 h 5"
                                                 ).splitlines()
    if not line.startswith("Marek Sobotta: MTPD:"))

#: Five activities under one department, which is the owner's ruling of 2026-09-12 put to the
#: measurement it asked for: one stage 4 card, and a number for what five does to it.
FIVE_ACTIVITIES = ("---\ndepartment: Incident and problem management\ncovered: operational\n---\n\n"
                   "# Incident and problem management interview\n")
for _name, _rto in (("Detection", "2 h"), ("Classification", "4 h"), ("Handling", "6 h"),
                    ("Resolution", "8 h"), ("Root cause", "12 h")):
    FIVE_ACTIVITIES += f"""
## {_name}

Marek Sobotta: MTPD: 24 h for {_name.lower()}.
Marek Sobotta: RTO: {_rto} for {_name.lower()}.
Marek Sobotta: RPO: <24 h.
Marek Sobotta: Impact operational: 1 h 1, 2 h 2, 4 h 2, 8 h 3, 24 h 4, 72 h 5, 168 h 5.
Marek Sobotta: Depends on: Atlassian Jira, mobile telephony.
"""

#: What a phone screen holds before a thumb has to move, in characters. Measured on the card this
#: ticket draws rather than assumed: the number is asserted below, so it cannot drift silently.
PHONE_SCREEN = 700


def _refereed_room(ctx, transcript=REFEREED_TRANSCRIPT):
    """The interview this walk rests on, and the register its dependencies resolve against."""
    (ctx["room_folder"] / INTERVIEWS / EVIDENCE_FILE).write_text(transcript, encoding="utf-8")
    _on_the_menu(ctx, "Incident and problem management")
    register = ctx["room_folder"] / REGISTER
    register.parent.mkdir(parents=True, exist_ok=True)
    held = json.loads(register.read_bytes()) if register.is_file() else {}
    register.write_text(json.dumps({**held, **EVIDENCE_ASSETS}), encoding="utf-8")


def _rewalk(ctx, transcript):
    """This walk again over a different interview, every stage of it pressed as before.

    A bound transcript whose bytes change is a finding (ticket 12), so a scenario that needs a
    different grid cannot edit the file under the walk: it walks a new one.
    """
    shutil.rmtree(ctx["room_folder"] / RUNS)
    _refereed_room(ctx, transcript)
    _press_process(ctx, ctx["process"])
    _press_button(ctx, AGREE)
    _bind_the_transcript(ctx)
    _endorse_the_evidence(ctx)
    return _record(ctx)


def _endorse_the_evidence(ctx):
    """Stage 3, answered: the standardised evidence endorsed as it stood."""
    if not [entry for entry in _saved(ctx)["decisions"] if entry["stage"] == STAGE_3]:
        _draft(ctx)
        _press_button(ctx, ENDORSED)


def _record(ctx):
    """The stage 4 card this walk serves, with what the room held before it was drawn."""
    _endorse_the_evidence(ctx)
    ctx["bytes_before"] = _bytes(ctx)
    ctx["acts_before"] = list(ctx["acts"])
    ctx["card"] = _stage_card(ctx, STAGE_4)
    return ctx["card"]


def _bytes(ctx):
    """Every byte the room holds, so "nothing was written" is read rather than asserted."""
    folder = ctx["room_folder"]
    return {path.relative_to(folder).as_posix(): path.read_bytes()
            for path in folder.rglob("*") if path.is_file()}


def _accept(ctx, label=ENDORSED):
    """The one tap, with the card it was pressed on kept to compare the bytes against."""
    _record(ctx)
    ctx["accepted"] = ctx["card"]
    ctx["bytes_before"] = _bytes(ctx)
    _press_button(ctx, label)
    return ctx["card"]


def _landed(ctx):
    return read_record(ctx["room_folder"], _record_at(ctx))


def _broken_quote(ctx):
    """One quote in this run's own evidence replaced by a sentence no file in the room holds."""
    _record(ctx)
    saved = _saved(ctx)
    saved["activities"][0]["evidence"][0]["quote"] = FABRICATED
    write_record(ctx["room_folder"], run_file(ctx["process"]), saved, saved["revision"])
    ctx["bytes_before"] = _bytes(ctx)


#: A sentence nobody said, which is the defect the referee will not pass off as a finding.
FABRICATED = "Marek Sobotta: MTPD: 20 minutes for incident and problem management."

#: A record the room was handed rather than one a walk produced, and the run it names.
SEEDED_RUN = "9f1c2b3a-4d5e-6f70-8192-a3b4c5d6e7f8"


# ------------------------------------------------------------------ the stages before this one


@given("I have agreed the scope and bound the interview")
def _i_have_agreed_the_scope_and_bound_the_interview(ctx):
    _refereed_room(ctx)
    _i_have_agreed_the_scope_for(ctx, "Incident and problem management")
    _bind_the_transcript(ctx)


@given("I endorsed the standardised evidence at stage 3")
def _i_endorsed_the_standardised_evidence(ctx):
    _endorse_the_evidence(ctx)


# ------------------------------------------------------------------ the card, and what is on it


@given("a refereed record")
@given("the card has been shown")
@given("the stage 4 card")
@given("I agree with the record on the stage 4 card")
@given("an MTPD derived from the grid")
@when("the stage 4 card is drawn")
@when("I reach stage 4")
def _the_stage_4_card(ctx):
    _record(ctx)


@when("I read the stage 4 card")
def _i_read_the_stage_4_card(ctx):
    _record(ctx)
    _i_read_the_card(ctx)
    # What this scenario is reading. Ticket 16's worksheet answers two of the same Thens, and it
    # has to be the same two: a figure nobody derived must be absent from the document a manager
    # is handed for exactly the reason it is absent from the card.
    ctx["read"] = ctx["card"].body


@then("every scored category shows its exact quote and the file it came from")
def _every_scored_category_shows_its_quote_and_file(ctx):
    scored = [item for activity in ctx["card"].proposal[BIA]["activities"]
              for item in activity["evidence"] if "lens" in item]
    assert scored, "nothing on this record is scored, so this proves nothing"
    for item in scored:
        assert item["quote"] in ctx["card"].body, f"{item['lens']} is scored with no quote by it"
        assert item["source_path"] in ctx["card"].sources
        assert item["quote"] in _transcript(ctx), "the quote is not the bound interview's own"


@then("each finding is shown as a finding rather than a refusal")
def _each_finding_is_shown_as_a_finding(ctx):
    open_items = [*_saved(ctx)["open_items"], *ctx["card"].proposal[FINDINGS]]
    assert open_items, "this record raised nothing, so this proves nothing"
    for item in open_items:
        assert item in ctx["card"].body, f"{item!r} is not on the card at all"
    assert ctx["card"].buttons == GRADIENT, "the card cannot be answered, so it is a wall"


@then("the card says why before it says the number")
def _the_card_says_why_before_the_number(ctx):
    """`docs/voice.md`: the figure lands where the sentence has already said why it stands."""
    derived = [part for part in ctx["card"].body.split("\n\n") if "intolerable" in part]
    assert derived, "no figure on this card was derived from the grid"
    for said in derived:
        assert said.index("reaches") < said.index("stands at"), said


@given("the grid never reaches the threshold within the horizons")
def _the_grid_never_reaches_the_threshold(ctx):
    _rewalk(ctx, GENTLE_TRANSCRIPT)
    assert impact.crossing(ctx["card"].proposal[BIA]["activities"][0]["impact_grid"],
                           ctx["card"].method)[0] == impact.NO_MTPD


@then("it says so in the manager's words")
def _it_says_so_in_the_managers_words(ctx):
    assert NO_MTPD_SAYS.format(activity=ctx["process"]) in ctx["read"]


@then("no MTPD figure is shown for that activity")
def _no_mtpd_figure_is_shown(ctx):
    assert "becomes unacceptable" not in ctx["read"], "a figure nobody derived was printed"
    assert "MTPD" not in ctx["read"]


@given("the referee raised findings on this record")
def _the_referee_raised_findings(ctx):
    _rewalk(ctx, FALLING_TRANSCRIPT)
    assert ctx["card"].proposal[FINDINGS], "the referee found nothing, so this proves nothing"


@then("the findings are on it as open items with what was seen and where")
def _the_findings_are_on_it_as_open_items(ctx):
    leading = ctx["card"].body[ctx["card"].body.index(OPEN_4):ctx["card"].body.index(DRAWN)]
    for finding in ctx["card"].proposal[FINDINGS]:
        assert finding in leading, f"{finding!r} is not among what I am being asked to accept"
        assert ctx["process"] in finding, "the finding does not say what it was seen on"


@then("I can still accept the record with them on it")
def _i_can_still_accept_the_record(ctx):
    assert ctx["card"].buttons == GRADIENT
    _accept(ctx)
    assert _landed(ctx) is not None, "a record with findings on it did not land"


@then("nothing about them stops the stage")
def _nothing_about_them_stops_the_stage(ctx):
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_4


# --------------------------------------------------- a defect, said before anything is asked


@given("the record quotes a sentence no file in my room holds")
@given("a draft record with content problems")
def _the_record_quotes_a_sentence_no_file_holds(ctx):
    _broken_quote(ctx)


@when("the stage 4 card would be drawn")
def _the_stage_4_card_would_be_drawn(ctx):
    ctx["card"] = record_card(ctx["room_folder"], ctx["process"])


@then("the record is not offered for acceptance at all")
def _the_record_is_not_offered_for_acceptance(ctx):
    assert ctx["card"].buttons == (), "a record the referee refuses was put up to be accepted"
    assert ctx["card"].decision == "" and ctx["card"].gradient == GRADIENT


@then("what is wrong with it is said before I am asked for anything")
def _what_is_wrong_is_said_before_i_am_asked(ctx):
    assert ctx["card"].body.startswith(REFUSED.split("{")[0])
    assert FABRICATED in ctx["card"].body, "the card does not say which sentence is wrong"
    assert ctx["card"].decision == "", "it asks me something anyway"


@when("it is checked without anybody having confirmed anything")
def _it_is_checked_without_anybody_confirming(ctx):
    ctx["verdict"] = check_draft(ctx["room_folder"], ctx["process"])


@then("its content problems come back")
def _its_content_problems_come_back(ctx):
    assert not ctx["verdict"].passed
    assert [problem for problem in ctx["verdict"].rejections if FABRICATED in problem]


@then('it is not answered with "approval missing" instead')
def _it_is_not_answered_with_approval_missing(ctx):
    said = " ".join(ctx["verdict"].rejections).lower()
    for instead in ("approval", "confirm", "not confirmed", "sign"):
        assert instead not in said, f"the draft was answered with {instead!r}"


@then("no bytes are written anywhere in my room")
@then("no bytes are written")
def _no_bytes_are_written(ctx):
    assert _bytes(ctx) == ctx["bytes_before"]


@when("I have not answered the gradient")
def _i_have_not_answered_the_gradient(ctx):
    assert ctx["card"].buttons == GRADIENT, "there is nothing to answer, so this proves nothing"
    assert ctx["acts"] == ctx["acts_before"], "the gradient was answered after all"


# ------------------------------------------------------------------------ the voice, at stage 4


@then(parsers.parse('every file the "{label}" line names is a file in my room'))
def _every_file_the_source_line_names_is_in_my_room(ctx, label):
    assert ctx["card"].source_line.startswith(label)
    assert ctx["card"].sources
    for path in ctx["card"].sources:
        assert (ctx["room_folder"] / path).is_file(), f"{path} is not a file in my room"


@then("the figures on it are the ones I endorsed, character for character")
def _the_figures_are_the_ones_i_endorsed(ctx):
    endorsed = {item["label"]: item["value"] for item in _saved(ctx)["evidence"]}
    assert endorsed, "nothing was endorsed, so this proves nothing"
    for label, value in endorsed.items():
        assert value in ctx["card"].body, f"the {label} on the card is not the one I endorsed"
        assert ctx["card"].proposal[BIA]["activities"][0][bia.FIELDS[label]] == value


@then("nothing was re-read from the transcript to produce them a second time")
def _nothing_was_re_read_from_the_transcript(ctx):
    """The figures are a function of the run state: the room's files are handed in only to say
    where each quote's words are (ticket 131), so no figure can enter through them."""
    assert list(inspect.signature(bia.build).parameters) == ["run", "files"]
    assert _bia_record(ctx) == ctx["card"].proposal[BIA]
    blind = bia.build(_saved(ctx), {})
    for seen, unseen in zip(_bia_record(ctx)["activities"], blind["activities"], strict=True):
        assert {key: value for key, value in seen.items() if key != "evidence"} == {
            key: value for key, value in unseen.items() if key != "evidence"}
        assert [item["quote"] for item in seen["evidence"]] == [
            item["quote"] for item in unseen["evidence"]]


# --------------------------------------------------------------------- the one tap, and its cost


@then("stage 4 is answered")
@then("stage 4 is already answered rather than waiting for my characters")
def _stage_4_is_answered(ctx):
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_4
    assert ctx["typed"] == "", "the walk waited for characters before it recorded the answer"


# ------------------------------------------------------------------ what lands, and only then


@given("I accepted the record")
def _i_accepted_the_record(ctx):
    _accept(ctx)


def _record_at(ctx):
    """Where this scenario's process keeps its BIA record (ticket 235: one per process)."""
    return record_file(ctx["process"])


@when("I look at what my room holds")
def _i_look_at_what_my_room_holds(ctx):
    ctx["held"] = _files(ctx["room_folder"])


@then(parsers.parse('"{path}" holds the record I accepted'))
def _the_path_holds_the_record_i_accepted(ctx, path):
    assert path == _record_at(ctx) and path in ctx["held"]
    assert _landed(ctx)["run_id"] == _saved(ctx)["run_id"]


@when("the saved record is read back")
def _the_saved_record_is_read_back(ctx):
    ctx["read_back"] = _landed(ctx)


@then("it matches what the card put in front of me")
def _it_matches_what_the_card_put_in_front_of_me(ctx):
    shown = ctx["accepted"].proposal[BIA]
    assert {key: value for key, value in ctx["read_back"].items() if key != "revision"} == shown


@then("nothing was added to it after I had seen it")
def _nothing_was_added_after_i_had_seen_it(ctx):
    assert set(ctx["read_back"]) - {"revision"} == set(ctx["accepted"].proposal[BIA])


@given("the record in my room moved on after this walk read it")
def _the_record_moved_on_after_this_walk_read_it(ctx):
    _record(ctx)
    ctx["accepted"] = ctx["card"]
    write_record(ctx["room_folder"], _record_at(ctx), {"run_id": SEEDED_RUN}, 0)
    ctx["bytes_before"] = _bytes(ctx)


@when("my acceptance tries to save")
def _my_acceptance_tries_to_save(ctx):
    _press_button(ctx, ENDORSED)


@then("the save is refused as out of date")
def _the_save_is_refused_as_out_of_date(ctx):
    assert ctx["card"].body.startswith(OVERTAKEN)


@then("the record already in the room is left as it is")
def _the_record_already_in_the_room_is_left_as_it_is(ctx):
    assert _bytes(ctx) == ctx["bytes_before"]
    assert _landed(ctx)["run_id"] == SEEDED_RUN


@when("the walk reports where it is")
def _the_walk_reports_where_it_is(ctx):
    """Where the walk stood with the record on disk and the picture not drawn yet — the state
    between stage 4's two movements, which is the one this scenario is about (ticket 17)."""
    ctx["where"] = where_it_stands(ctx["saved_run"])


@then("it says the record is saved and the picture is not bound yet")
def _it_says_saved_and_not_bound_yet(ctx):
    assert ctx["where"] == SAVED_NOT_FINISHED
    assert ctx["where"] in ctx["saved_card"].body, "what it says to me is not what it says itself"
    assert "not drawn yet" in ctx["where"]


@then("it does not report the walk as finished")
def _it_does_not_report_the_walk_as_finished(ctx):
    assert ctx["saved_run"]["status"] == RECORD_SAVED
    assert "one thing left" in ctx["where"]
    assert ctx["where"].index("one thing left") < ctx["where"].index("finished")


@given("the walk stopped just after the record landed")
def _the_walk_stopped_just_after_the_record_landed(ctx):
    _accept(ctx)
    ctx["bytes_before"] = _bytes(ctx)


@when("it resumes and does the movement again")
def _it_resumes_and_does_the_movement_again(ctx):
    ctx["card"] = resume(ctx["room_folder"], ctx["process"])


@then("the record on disk is byte for byte what it was")
def _the_record_on_disk_is_byte_for_byte_what_it_was(ctx):
    at = _record_at(ctx)
    assert (ctx["room_folder"] / at).read_bytes() == ctx["bytes_before"][at]


@then("nothing is written twice into the room for me to read")
def _nothing_is_written_twice(ctx):
    assert _files(ctx["room_folder"]) == set(ctx["bytes_before"])


# ------------------------------------------------------------- the record must be this run's work


@when("I walk to stage 4 and accept the record")
def _i_walk_to_stage_4_and_accept_the_record(ctx):
    ctx["room_folder"] = ctx["claimed"]
    ctx["shipped"] = _landed(ctx)
    _accept(ctx)


@then("the record now in my room is not the one the room shipped")
def _the_record_is_not_the_one_the_room_shipped(ctx):
    assert _landed(ctx) != ctx["shipped"]
    assert ctx["shipped"] is None, "a minted room shipped a record to close over (ADR-0011)"


@then("it carries this walk's own identity")
@then("the record in the room carries that walk's identity")
def _it_carries_this_walks_own_identity(ctx):
    assert _landed(ctx)["run_id"] == _saved(ctx)["run_id"]


@given("a room seeded with a valid record and a worked folder")
def _a_room_seeded_with_a_valid_record(ctx):
    """What v1 shipped, and what it closed over: a referee-clean record nobody in this room made."""
    _record(ctx)
    seeded = {**_bia_record(ctx), "run_id": SEEDED_RUN}
    write_record(ctx["room_folder"], _record_at(ctx), seeded, 0)
    (ctx["room_folder"] / "reference" / "worked-example").mkdir(parents=True)
    assert check_draft(ctx["room_folder"], ctx["process"]).passed, "the seeded record is not valid"


@given("a seeded record with no modification time recorded in it at all")
def _a_seeded_record_with_no_modification_time(ctx):
    _a_room_seeded_with_a_valid_record(ctx)
    assert "modified" not in _landed(ctx), "the record carries a time this refusal could rest on"


@given("a walk that never refereed and never wrote")
def _a_walk_that_never_refereed_and_never_wrote(ctx):
    run = _saved(ctx)
    assert not run.get(CHECKED), "this walk refereed something, so it proves nothing"
    assert run.get("status") != RECORD_SAVED, "this walk wrote a record, so it proves nothing"
    ctx["run"] = run


@when("the walk tries to move past stage 4")
@when("that walk tries to move past stage 4")
@when("that walk moves past stage 4")
def _the_walk_tries_to_move_past_stage_4(ctx):
    ctx["refusal"] = ctx["carried"] = None
    try:
        ctx["carried"] = move_past_stage_4(ctx["room_folder"], ctx["run"])
    except StaleRecord as refused:
        ctx["refusal"] = refused


@then("it is refused, naming the stale record")
@then("it is still refused")
def _it_is_refused_naming_the_stale_record(ctx):
    assert ctx["refusal"] is not None, "a walk that did no work closed over somebody else's record"
    assert ctx["refusal"].found == SEEDED_RUN
    assert SEEDED_RUN in str(ctx["refusal"]) and ctx["carried"] is None


@then("the refusal rests on which run produced the record, not on when it was touched")
def _the_refusal_rests_on_which_run_produced_it(ctx):
    """Touched now, and refused exactly as before: there is no time in this decision to move."""
    os.utime(ctx["room_folder"] / _record_at(ctx), None)
    with pytest.raises(StaleRecord) as again:
        move_past_stage_4(ctx["room_folder"], ctx["run"])
    assert str(again.value) == str(ctx["refusal"])
    assert bia.is_ours(_landed(ctx), str(ctx["run"]["run_id"])) is False


@given("a walk that refereed it and wrote it")
def _a_walk_that_refereed_it_and_wrote_it(ctx):
    ctx["room_folder"] = ctx["claimed"]
    ctx["shipped"] = _landed(ctx)
    _accept(ctx)
    ctx["run"] = _saved(ctx)
    assert ctx["run"][CHECKED], "this walk refereed nothing after all"


@then("it is allowed through")
def _it_is_allowed_through(ctx):
    assert ctx["refusal"] is None, f"a walk was refused its own record: {ctx['refusal']}"
    assert ctx["carried"]["run_id"] == ctx["run"]["run_id"]


# ------------------------------------------------------------ the receipt says what was checked


@when("I read what the walk says about the record being checked")
def _i_read_what_the_walk_says_about_the_record_being_checked(ctx):
    ctx["said"] = checked_note(_saved(ctx))


@then("it names the checks the referee actually ran on this record")
def _it_names_the_checks_that_actually_ran(ctx):
    ran = _saved(ctx)[CHECKED]
    assert ran == list(ctx["accepted"].proposal[CHECKED]) and ran
    for check in ran:
        assert check in ctx["said"] and check in ctx["card"].screen


@then("every clause of it is true of this run")
def _every_clause_of_it_is_true_of_this_run(ctx):
    """Each clause is a check the referee recorded having run over this very record, and a run
    that ran none has no sentence at all — v1's literal could not be made false."""
    assert ctx["said"] == CHECKED_NOTE.format(checks=_listed(_saved(ctx)[CHECKED]))
    assert check_draft(ctx["room_folder"], ctx["process"]).checked == _saved(ctx)[CHECKED]
    assert checked_note({}) == "", "a run that checked nothing still says it checked"


@when("I read everything the walk says about that record")
def _i_read_everything_the_walk_says_about_that_record(ctx):
    ctx["said"] = " ".join([checked_note(ctx["run"]), where_it_stands(ctx["run"])])


@then("no sentence claims the record was checked")
def _no_sentence_claims_the_record_was_checked(ctx):
    assert checked_note(ctx["run"]) == ""
    assert CHECKED_NOTE.split("{")[0] not in ctx["said"]


@then("no sentence claims it was saved")
def _no_sentence_claims_it_was_saved(ctx):
    assert where_it_stands(ctx["run"]) == ""
    assert ctx["said"].strip() == ""


# -------------------------------------------------------- one card, five activities, measured


@given("my department has five activities in scope")
def _my_department_has_five_activities(ctx):
    _rewalk(ctx, FIVE_ACTIVITIES)
    assert len(ctx["card"].proposal[BIA]["activities"]) == 5


@then("there is one card for all five")
def _there_is_one_card_for_all_five(ctx):
    following = onward(ctx["room_folder"], _stage_card(ctx, STAGE_3))
    assert [card.stage for card in following] == [STAGE_4], "stage 4 is more than one card"
    assert len(ctx["card"].activities) == 1, "the walk split the department into several cards"


@then("it is answered with one gradient answer")
def _it_is_answered_with_one_gradient_answer(ctx):
    assert ctx["card"].buttons == GRADIENT
    _accept(ctx)
    assert [without_telemetry(entry) for entry in _saved(ctx)["decisions"]
            if entry["stage"] == STAGE_4] == [{"stage": STAGE_4, "gradient": ENDORSED}]


@then("every one of the five carries its own grid, MTPD sentence, RTO, RPO and dependencies")
def _every_one_of_the_five_carries_its_own(ctx):
    body = ctx["card"].body
    for activity in ctx["card"].proposal[BIA]["activities"]:
        assert activity["impact_grid"]["operational"]
        assert MTPD_SAYS.format(activity=activity["name"], lenses="operational",
                                horizon=activity["mtpd"]) in body
        assert f"the RTO stands at {activity['recovery_target']}" in body
        assert activity["rpo"] in body and activity["dependencies"] == ["KA-01"]


@then("no activity is summarised away or left for a later card")
def _no_activity_is_summarised_away(ctx):
    named = [activity["name"] for activity in ctx["card"].proposal[BIA]["activities"]]
    assert len(named) == 5
    for name in named:
        assert ctx["card"].body.count(name) >= 2, f"{name} is named but not worked through"
    assert onward(ctx["room_folder"], ctx["card"]) == (), "something was left for a later card"


@then("what I am being asked to decide is at the top of it")
def _what_i_am_asked_to_decide_is_at_the_top(ctx):
    """Measured, not assumed — the story's own "Done when" asks for a number, so here it is.

    A department with five activities draws **one card of 7,298 characters**, which is about
    ten screenfuls on a phone (`PHONE_SCREEN`, measured at 700 characters of body text). What
    a thumb has to find is therefore not the card but the ask, and it is in the **first 272
    characters**: the opening paragraph says what is being decided and that the decision does not
    undo, and what the referee will not settle stands above everything already settled. The four
    labels ride at the bottom as they do at every other stage, so the scroll buys the reading, not
    the decision. That is a long card and it is recorded as one; it is not a split, because
    splitting it would cost a tap per activity for no measured gain (owner, 2026-09-12).
    """
    ask = ACCEPTING.format(process=ctx["process"])
    assert ctx["card"].body.startswith(ask)
    assert len(ask) < PHONE_SCREEN, "the ask itself does not fit on the first screen"
    assert 7000 < len(ctx["card"].screen) < 8000, len(ctx["card"].screen)
    assert ctx["card"].decision == DECISION_4 and ctx["card"].rule == RULE_4


@then("what the referee will not settle comes before what is already settled")
def _what_will_not_be_settled_comes_first(ctx):
    body = ctx["card"].body
    assert body.index(OPEN_4) < body.index(DRAWN)
    assert body.index(DRAWN) < body.index("24 h"), "a settled figure came before the decision"
# ═════════════════════════ stage 2 — the live interview path ═════════════════════════
#
# `features/stage-2-the-live-interview-path.feature`. The room holds no interview for this process
# at all, so stage 2 does not send the manager away to find a file: the interview is conducted here
# and now, previewed whole, and kept by the same one gradient that would have bound a transcript
# already in the room.
#
# **Nothing here reaches a model.** The lane is a function `nemo.conduct` takes, so the interview
# is driven as a real one — one question, one answer, and the next question following it — while
# the cap is provoked on demand. A 402 and a refused connection are one `LaneUnavailable`
# (`nemo.lane`), so a lane that raises it is the cap as far as this path can tell.
#
# The one discipline the steps hold: **the manager types answers and nothing else.** `_typed_answer`
# is the only place a step puts characters into this walk, and every press still goes through a
# label the card offered — so "the only typing is the interview" is a property the steps enforce.

#: The interview a stand-in lane conducts. Six, which is `nemo.conduct.TURNS`, and the third is the
#: one the story names: what an outage of this process would cost.
LIVE_QUESTIONS = (
    "What does {process} do for the rest of the plant on an ordinary day?",
    "Who feels it first if it stops, and how soon do they feel it?",
    "What would an outage of it cost you — what goes wrong, and for whom?",
    "How long could you live with that before it stopped being tolerable?",
    "Who else would you have to call while it was down?",
    "Is there anything about it I have not asked you?",
)

#: What the manager says back, in their own words and none of them tidy.
LIVE_ANSWERS = (
    "It's the first to see a fault. Everything downstream waits on it.",
    "Incident management, inside the hour — then the helpdesk, then the users start calling.",
    "We watch the alerts by hand for one shift and no longer; after that the faults go unseen.",
    "A day or so, I'd have to check with Marek before I said that to anybody.",
    "Marek, and then whoever is on call that night.",
    "Only that we've never once had it down in winter, which is the bit that worries me.",
)

#: The question the third one is, once a process's name is in it — the cost question by name.
COST_QUESTION = 2

assert len(LIVE_QUESTIONS) == len(LIVE_ANSWERS) == TURNS


def _lane(ctx, cap_after=None):
    """The stand-in lane: those questions in order, and the cap after however many were asked."""
    def lane(prompt):
        ctx["prompts"].append(prompt)
        if cap_after is not None and len(ctx["prompts"]) > cap_after:
            raise LaneUnavailable("the lane did not answer")
        return LIVE_QUESTIONS[len(ctx["prompts"]) - 1].format(process=ctx["process"])
    return lane


def _typed_answer(ctx, words):
    """The manager typing one answer. The only characters any step here puts into this walk."""
    ctx["typed"] = words
    ctx["acts"].append(("type", words))
    return words


def _press_hold_it_now(ctx):
    """The one button a room with no transcript offers. Pressed, never asked for."""
    assert HOLD_IT_NOW in ctx["card"].buttons, "the room did not offer to hold the interview"
    ctx["acts"].append(("press", HOLD_IT_NOW))
    ctx.update(turns=(), prompts=[], stopped="", asked="")


def _one_more_question(ctx, cap_after=None):
    """Put the next question, if there is one. `False` once the interview is over, either way."""
    next_up = conduct(ctx["process"], ctx["turns"], lane=_lane(ctx, cap_after))
    ctx["asked"] = next_up.question
    ctx["stopped"] = next_up.note
    return bool(next_up.question)


def _preview(ctx):
    """The card the interview so far would be kept by: the whole of it, and one decision."""
    ctx["card"] = held_interview(ctx["room_folder"], ctx["process"], ctx["turns"])
    ctx["shown"] = ctx["card"].interviews[0]


def _answer_the_interview(ctx, cap_after=None):
    """Answer it the way a manager does: read the question, type the answer, read the next one."""
    _reach_stage_2(ctx)
    _press_hold_it_now(ctx)
    while _one_more_question(ctx, cap_after):
        ctx["turns"] += (Turn(ctx["asked"],
                              _typed_answer(ctx, LIVE_ANSWERS[len(ctx["turns"])])),)
    _preview(ctx)


def _answer_the_gradient(ctx, label=ENDORSED):
    """The one press that keeps it. The same four labels stage 2 has always had."""
    assert label in ctx["card"].buttons, f"{label!r} is not a button on this card"
    ctx["acts"].append(("press", label))
    ctx["picked"] = ctx["shown"]
    ctx["card"] = _said(ctx, label)[0]


# ------------------------------------------------------- a room that holds nothing for it


@given(parsers.parse('my room holds no interview for "{process}" in either of its homes'))
def _my_room_holds_no_interview_in_either_home(ctx, process):
    """Both homes empty of this process (ADR-0002), and the register still naming it — so it is
    still a process the room offers and still reaches a stage 2 card."""
    assert process == ctx["process"]
    _my_room_holds_no_transcript_for_this_process(ctx)
    assert process in processes(ctx["room_folder"])


# ------------------------------------------------------------ the interview, and its preview


@given("the interview has been answered in the room")
@when("I answer the interview in the room")
def _i_answer_the_interview_in_the_room(ctx):
    _answer_the_interview(ctx)


@then("I am shown the verbatim question-and-answer with its fingerprint")
def _i_am_shown_the_verbatim_question_and_answer(ctx):
    shown = ctx["shown"]
    assert ctx["turns"], "an interview of no turns previews nothing"
    for turn in ctx["turns"]:
        assert turn.question in shown.preview, "a question I was asked is not in what I was shown"
        assert turn.answer in shown.preview, "an answer I gave is not in what I was shown"
    assert shown.preview == transcript(ctx["process"], ctx["turns"])
    assert shown.fingerprint == hashlib.sha256(shown.preview.encode()).hexdigest()


@then("nothing is on disk until I answer the gradient")
def _nothing_is_on_disk_until_i_answer_the_gradient(ctx):
    assert _new_files(ctx) == set(), "the interview was on disk before I kept it"
    assert not (ctx["room_folder"] / interview_path(ctx["process"])).exists()
    assert "transcript" not in _saved(ctx), "the walk bound something I had not answered"


# ------------------------------------------------------------ what is kept is what I saw


@given("I have answered the gradient on the preview")
def _i_have_answered_the_gradient_on_the_preview(ctx):
    _answer_the_interview(ctx)
    _answer_the_gradient(ctx)


@then("the transcript on disk is byte-identical to the preview")
def _the_transcript_on_disk_is_byte_identical(ctx):
    filed = ctx["room_folder"] / ctx["picked"].path
    assert filed.read_bytes() == ctx["picked"].preview.encode()


@then("it is bound to this walk")
def _it_is_bound_to_this_walk(ctx):
    bound = _saved(ctx)["transcript"]
    assert bound["path"] == ctx["picked"].path
    assert bound["fingerprint"] == ctx["picked"].fingerprint
    assert without_telemetry(_saved(ctx)["decisions"][-1]) == {"stage": 2, "gradient": ENDORSED}


# ------------------------------------------------------------ it cannot write a record


@given("a live interview of any length")
def _a_live_interview_of_any_length(ctx):
    """Every length there is, from an interview that got nowhere to a whole one, each kept."""
    _reach_stage_2(ctx)
    _press_hold_it_now(ctx)
    ctx["lengths"] = []
    while True:
        if ctx["lengths"]:
            _back_to_stage_2(ctx)
        _preview(ctx)
        _answer_the_gradient(ctx)
        ctx["lengths"].append(ctx["turns"])
        if not _one_more_question(ctx):
            break
        ctx["turns"] += (Turn(ctx["asked"],
                              _typed_answer(ctx, LIVE_ANSWERS[len(ctx["turns"])])),)
    assert len(ctx["lengths"]) == TURNS + 1


@then("no record is written and no figure is asserted by the model")
def _no_record_is_written_and_no_figure_asserted(ctx):
    """A record is stage 4's and is not this stage's to write, at any length; and what this stage
    did write names none of the four figures stage 3 will read out of the transcript."""
    written = _files(ctx["room_folder"]) - ctx["before"]
    assert written <= {interview_path(ctx["process"]), run_file(ctx["process"])}, written
    assert not [path for path in _files(ctx["room_folder"]) if path.endswith("bia-record.json")]
    saved = _saved(ctx)
    decided = json.dumps({"decisions": saved["decisions"], "transcript": saved["transcript"]})
    for figure in ("mtpd", "rto", "rpo", "mbco"):
        assert figure not in decided.lower(), f"stage 2 asserted a {figure.upper()}"


# ------------------------------------------------------------------------ the cap


@given("the OpenRouter key cap has been reached mid-interview")
def _the_cap_has_been_reached_mid_interview(ctx):
    """Two questions answered and the third never arrives — the cap is a stop, not a degradation
    (ADR-0009), and it reaches this path as the same `LaneUnavailable` the ask lane meets."""
    _answer_the_interview(ctx, cap_after=2)
    assert len(ctx["turns"]) == 2, "the cap did not land mid-interview"


@then("I am told plainly, and what was already captured is not lost")
def _i_am_told_plainly_and_nothing_is_lost(ctx):
    assert ctx["stopped"] == STOPPED
    for machine in ("402", "OpenRouter", "LaneUnavailable", "Traceback", "127.0.0.1", "cap"):
        assert machine not in ctx["stopped"], f"{machine!r} is on the page"
    for turn in ctx["turns"]:
        assert turn.question in ctx["shown"].preview and turn.answer in ctx["shown"].preview
    assert ctx["card"].buttons == GRADIENT, "the stop cost me the interview I had given"


# ------------------------------------------------------ where the referee will hunt quotes


@then(parsers.parse('the transcript is at "{path}"'))
def _the_transcript_is_at(ctx, path):
    wanted = path.replace("<process>", _slugs(ctx["process"])[0])
    assert wanted in ctx["held"], f"{wanted} is not a file in my room"
    assert interview_path(ctx["process"]) == wanted


@then("it holds the questions and my answers as they were asked and given")
def _it_holds_the_questions_and_my_answers(ctx):
    filed = (ctx["room_folder"] / interview_path(ctx["process"])).read_text(encoding="utf-8")
    for turn in ctx["turns"]:
        assert turn.question in filed and turn.answer in filed
    assert filed.index(ctx["turns"][0].answer) < filed.index(ctx["turns"][1].question)


# --------------------------------------------------- the fingerprint on the preview


@given("I am shown the preview of the interview I just answered")
def _i_am_shown_the_preview_of_the_interview(ctx):
    _answer_the_interview(ctx)
    _i_am_shown_the_verbatim_question_and_answer(ctx)


@when("I keep it and the operator digests the saved file")
def _i_keep_it_and_the_operator_digests_it(ctx):
    _answer_the_gradient(ctx)
    ctx["digest"] = hashlib.sha256(
        (ctx["room_folder"] / interview_path(ctx["process"])).read_bytes()).hexdigest()


@then("the digest is the fingerprint the preview carried")
def _the_digest_is_the_fingerprint_the_preview_carried(ctx):
    assert ctx["digest"] == ctx["shown"].fingerprint


@then("the walk records that same fingerprint against this interview")
def _the_walk_records_that_same_fingerprint(ctx):
    assert _saved(ctx)["transcript"]["fingerprint"] == ctx["digest"]


# ------------------------------------------------------------- one decision, not two


@when("I answer it with one of the four labels")
def _i_answer_it_with_one_of_the_four_labels(ctx):
    assert ctx["card"].buttons == GRADIENT, "the four labels are not what this card offers"
    _answer_the_gradient(ctx)


@then("stage 2 is answered and the interview is bound")
def _stage_2_is_answered_and_the_interview_is_bound(ctx):
    _it_is_bound_to_this_walk(ctx)
    assert _stage_card(ctx, STAGE_3).stage == STAGE_3, "the walk has not moved past stage 2"


@then("I am not asked to confirm the transcript and then answer a second card")
def _i_am_not_asked_to_confirm_and_then_answer_again(ctx):
    """A longer path, not a more expensive gate (`docs/stage-model.md` Stage 2): one press between
    the preview and a bound interview, and one stage 2 decision on file when it is over."""
    pressed = [what for kind, what in ctx["acts"] if kind == "press"]
    assert pressed[-1] == ENDORSED and pressed[-2] == HOLD_IT_NOW
    assert [without_telemetry(entry) for entry in _saved(ctx)["decisions"]
            if entry["stage"] == 2] == [{"stage": 2, "gradient": ENDORSED}]
    assert ctx["card"].buttons == () and ctx["card"].body == BOUND


# ------------------------------------------------ it asks for the reason, never the figure


@given("the interview reaches what an outage of this process would cost")
def _the_interview_reaches_what_an_outage_would_cost(ctx):
    _reach_stage_2(ctx)
    _press_hold_it_now(ctx)
    while _one_more_question(ctx) and len(ctx["turns"]) < COST_QUESTION:
        ctx["turns"] += (Turn(ctx["asked"],
                              _typed_answer(ctx, LIVE_ANSWERS[len(ctx["turns"])])),)
    assert "cost" in ctx["asked"], "the interview never reached what an outage would cost"


@when("I read what it says to me")
def _i_read_what_it_says_to_me(ctx):
    ctx["prose"] = ctx["asked"]


@then("it asks me and waits")
def _it_asks_me_and_waits(ctx):
    assert ctx["prose"].endswith("?"), "it did not ask me anything"
    assert ctx["turns"] == tuple(ctx["turns"][:COST_QUESTION]), "it answered itself and went on"
    assert ctx["card"] is not None and "turns" in ctx


@then("no MTPD, RTO, RPO or MBCO is stated back to me as though I had said it")
def _no_figure_is_stated_back_to_me(ctx):
    """The four by name. The lane is told not to state one and is never told one to state, and
    nothing the room writes down at this stage carries one either (ADR-0007, ADR-0008)."""
    for figure in ("MTPD", "RTO", "RPO", "MBCO"):
        assert figure in CARD, f"the lane is not told to leave the {figure} alone"
        assert figure not in ctx["prose"], f"it put an {figure} in my mouth"
        assert figure.lower() not in transcript(ctx["process"], ctx["turns"]).lower()
    assert "Never state an MTPD, an RTO, an RPO or an MBCO back to them" in CARD
    assert "not concluding it" in CARD


# --------------------------------------------------------- the box, while it is running


@given("the interview has asked me a question")
def _the_interview_has_asked_me_a_question(ctx):
    _reach_stage_2(ctx)
    _press_hold_it_now(ctx)
    assert _one_more_question(ctx), "the interview asked me nothing"


@when("I type my answer")
def _i_type_my_answer(ctx):
    ctx["turns"] += (Turn(ctx["asked"], _typed_answer(ctx, LIVE_ANSWERS[0])),)
    _preview(ctx)


@then("it is taken as my answer to that question")
def _it_is_taken_as_my_answer_to_that_question(ctx):
    """Paired with the question it answered, and with no other — which is what the file has to
    say for the referee to be able to hunt a quote in it."""
    assert ctx["turns"][-1] == Turn(ctx["asked"], ctx["typed"])
    filed = ctx["shown"].preview
    assert filed.index(ctx["asked"]) < filed.index(ctx["typed"])
    assert _sees_no_naming(ctx), "the walk took my answer as a reservation's naming instead"


def _sees_no_naming(ctx):
    """Nothing else in this room was waiting for characters, so nothing else could have them."""
    decisions = (read_record(ctx["room_folder"], run_file(ctx["process"])) or {}).get(
        "decisions") or [{}]
    return decisions[-1].get("naming") != UNNAMED


# --------------------------------------------------- it reads like a colleague conducting


@when("I read what the interview says to me")
def _i_read_what_the_interview_says_to_me(ctx):
    _reach_stage_2(ctx)
    _press_hold_it_now(ctx)
    ctx["questions"] = []
    while _one_more_question(ctx):
        ctx["questions"].append(ctx["asked"])
        ctx["turns"] += (Turn(ctx["asked"],
                              _typed_answer(ctx, LIVE_ANSWERS[len(ctx["turns"])])),)
    _preview(ctx)
    ctx["prose"] = " ".join((ctx["card"].heading, ctx["card"].body, ctx["card"].decision,
                             ctx["card"].rule, *ctx["card"].buttons))


@then("it asks one thing at a time, in sentences")
def _it_asks_one_thing_at_a_time(ctx):
    assert len(ctx["questions"]) == TURNS, "it did not ask me its questions one at a time"
    for question in ctx["questions"]:
        assert question.count("?") == 1, f"more than one thing was asked at once: {question!r}"
        assert not re.match(r"\s*(\d+[.)]|[-*•])", question), "a question came as a list item"
    assert "one question" in CARD and "stop and wait" in CARD


@then("it names no tool, no field name and no file path")
def _the_interview_names_no_machine_identifier(ctx):
    """The card's own prose and every question, but not the preview: a quotation of what the two
    of us said is neither of us naming a tool, and the manager's words are never edited."""
    said = " ".join((ctx["prose"], *ctx["questions"]))
    assert [word for word in BANNED_ON_A_CARD if word in said] == []
    assert "these instructions" in CARD, "the lane is not told to keep itself off the page"


# ═══════════════════════ 16 — stage 4b, the four views from the record bytes ═════════════════════
#
# `features/stage-4b-the-four-views.feature`. The Background walks the real stages and accepts, so
# what these steps read is a record a manager could have pressed their way to. Everything after
# that is `nemo.views.render`, which is handed a record and nothing else: where a scenario needs a
# record the walk does not write yet — data sets, minimum resources — the step edits **the record**
# and renders it, because that is exactly the contract. A step that reached into the room to make a
# document say something would be testing a renderer this ticket does not have.

#: The interview the Background's record is built out of: the refereed one, with the MBCO the
#: worksheet is asked for stated in it. Its own constant rather than an edit to ticket 15's, so
#: nothing here moves a byte of what stage 4a is measured against.
VIEWS_TRANSCRIPT = REFEREED_TRANSCRIPT.replace(
    "Marek Sobotta: Depends on:",
    "Marek Sobotta: MBCO: two lead incident managers and one manager on duty.\n"
    "Marek Sobotta: Depends on:")

#: The four documents, by the names the story spells them.
VIEWS = list(views.FOUR)

#: The data sets a record can name, once a stage writes them. Two, because the defect this closes
#: is one data set's figure printed as though it covered every set of data the activity touches.
DATA_SET_FIGURES = [
    {NAME: "Atlassian Jira Service Management", RECOVERY_TARGET: "8 h", RPO: "<24 h"},
    {NAME: "Cisco Call Manager", RECOVERY_TARGET: "8 h", RPO: ">168 h"},
]

#: The minimum resources over time, each with the workaround for doing without it.
RESOURCE_FIGURES = [
    {NAME: "two lead incident managers", BY_WHEN: "8 h",
     WORKAROUND: "availability from a rotating staff pool"},
    {NAME: "one manager on duty", BY_WHEN: "8 h",
     WORKAROUND: "cover by a named IT Operations manager"},
]

#: What a changed record changes to. A different string, so a view still showing the old one is
#: a view somebody wrote beside the record rather than out of it.
MOVED_MTPD = "36 h"

#: The horizon dropped out of a record's grid to watch the worksheet keep the row anyway.
DROPPED_HORIZON = "24 h"

#: What the four views come to on a department with five activities, measured rather than
#: guessed — the numbers the story's last "Done when" asks somebody to write down. The screen is
#: `PHONE_SCREEN`, the 700 characters of body text stage 4a measured on this same phone.
FIVE_ACTIVITY_VIEWS = {
    "stage1-scope-and-guide.md": 9,
    "stage2-interview-capture.md": 11,
    "stage3-dependency-analysis.md": 9,
    "stage4-worksheet.md": 13,
}


def _views(ctx):
    """The four views this room's saved record says, rendered now. Reads the record; nothing else."""
    ctx["record"] = _landed(ctx)
    ctx["views"] = views.render(ctx["record"])
    return ctx["views"]


def _accepted(ctx):
    """This walk at stage 4 with the record accepted, if the scenario has not accepted it yet."""
    if _saved(ctx)["decisions"][-1]["stage"] != STAGE_4:
        _accept(ctx)


def _worksheet(ctx):
    """The worksheet as it now stands, and what this scenario is reading when a Then says so."""
    _accepted(ctx)
    ctx["read"] = _views(ctx)[views.WORKSHEET]
    return ctx["read"]


def _activities(ctx):
    return ctx["record"][ACTIVITIES]


def _record_holds(ctx, **fields):
    """The room's record with something more on every activity — a record, not a room.

    The renderer is a function of the record bytes, so a fact the walk does not write yet is put
    where the story says it belongs: in the record. A step that instead taught the renderer to go
    and find it would have deleted the property this ticket exists for.
    """
    _accepted(ctx)
    saved = _landed(ctx)
    changed = {key: value for key, value in saved.items() if key != "revision"}
    changed[ACTIVITIES] = [{**activity, **fields} for activity in saved[ACTIVITIES]]
    write_record(ctx["room_folder"], _record_at(ctx), changed, saved["revision"])


def _view_path(ctx, name):
    return f"{views.folder(_landed(ctx))}/{name}"


def _offer(ctx, name, text):
    """Offer a replacement for one of the four through the product's own write path."""
    ctx["refusal"] = None
    ctx["offered"] = text
    try:
        write_document(ctx["room_folder"], _view_path(ctx, name), text)
    except Shrunk as refused:
        ctx["refusal"] = refused


# ------------------------------------------------------------------ the walk behind every scenario


@given("I walked to stage 4 and accepted the record")
def _i_walked_to_stage_4_and_accepted_the_record(ctx):
    _refereed_room(ctx, VIEWS_TRANSCRIPT)
    _i_have_agreed_the_scope_for(ctx, "Incident and problem management")
    _bind_the_transcript(ctx)
    _accept(ctx)
    assert _landed(ctx) is not None, "the walk ended with no record to render from"


@given(parsers.parse('I accepted the record for the process "{process}"'))
def _i_accepted_the_record_for_the_process(ctx, process):
    assert views.folder(_landed(ctx)) == f"output/{process}"


# ------------------------------------------------------------------ rendered from the record


@given("the four views have been rendered")
@when("the four views are rendered")
@when("the four views are rendered again")
def _the_four_views_are_rendered(ctx):
    _accepted(ctx)
    views.write(ctx["room_folder"], _landed(ctx))
    _views(ctx)


@then("every figure in them is a string the record holds")
def _every_figure_is_a_string_the_record_holds(ctx):
    """`docs/voice.md` §4.4, applied to a document instead of to a card: the same one-line test,
    over the same checker the card path uses, so neither can be softened without the other."""
    for name, view in ctx["views"].items():
        assert untraceable(view, ctx["record"]) == [], f"{name} says what the record does not hold"
    assert ctx["record"][ACTIVITIES], "this record is about nothing, so this proves nothing"


@when("the record changes and they are rendered again")
def _the_record_changes_and_they_are_rendered_again(ctx):
    ctx["rendered_before"] = ctx["views"]
    _record_holds(ctx, **{MTPD: MOVED_MTPD})
    _views(ctx)


@then("they change with it")
def _they_change_with_it(ctx):
    for name, view in ctx["views"].items():
        assert view != ctx["rendered_before"][name], f"{name} did not follow the record"
        assert MOVED_MTPD in view, f"{name} still shows the figure the record no longer holds"


@then("the worksheet, the capture, the analysis and the scope guide agree on MTPD, RTO, RPO, "
      "MBCO, resources and open items")
def _the_four_agree_on_every_figure(ctx):
    """Not four documents compared: one set of sentences, quoted by four. Every figure the record
    holds stands in **all** four or the four have come apart, which is v1's package exactly."""
    _record_holds(ctx, **{RESOURCES: RESOURCE_FIGURES})
    _views(ctx)
    said = [*_figures_of(ctx), *ctx["record"][OPEN_ITEMS]]
    assert len(said) > 6, said
    for name, view in ctx["views"].items():
        for figure in said:
            assert figure in view, f"{name} does not hold {figure!r} and another view does"


def _figures_of(ctx):
    """Every figure and every resource the record holds, as the strings a view has to show."""
    return [str(activity[field])
            for activity in _activities(ctx)
            for field in (MTPD, RECOVERY_TARGET, RPO, MBCO) if field in activity] + [
        item[NAME] for activity in _activities(ctx) for item in activity[RESOURCES]]


# ------------------------------------------------------------------ where the four land


@then(parsers.parse('"{at}" holds "{first}", "{second}", "{third}" and "{fourth}"'))
def _the_folder_holds_the_four(ctx, at, first, second, third, fourth):
    assert [first, second, third, fourth] == VIEWS
    assert {path[len(at):] for path in ctx["held"]
            if path.startswith(at) and not path.endswith(RECORD_NAME)} == set(VIEWS)


@then("no view was written anywhere else in my room")
def _no_view_was_written_anywhere_else(ctx):
    at = views.folder(_landed(ctx))
    elsewhere = [path for path in ctx["held"]
                 if path.endswith(".md") and not path.startswith((at, INTERVIEWS))]
    assert elsewhere == [], f"a document was written outside the process's own folder: {elsewhere}"


# ------------------------------------------------------------------ the worksheet, clause by clause


@when("I read the worksheet")
def _i_read_the_worksheet(ctx):
    _worksheet(ctx)


@then("each activity's grid is there across every horizon the method covers")
def _each_grid_is_there_across_every_horizon(ctx):
    rows = [line for line in ctx["read"].splitlines() if line.startswith("| ")]
    assert rows, "there is no grid on the worksheet at all"
    for horizon in ctx["method_file"]["time_horizons"]:
        assert [row for row in rows if row.startswith(f"| {horizon} |")], f"{horizon} is not there"


@then("no horizon is dropped because nothing was scored in it")
def _no_horizon_is_dropped(ctx):
    """Taken out of the record on purpose: the grid the walk produced scored every horizon, so a
    worksheet that dropped unscored ones would pass the step above and fail a real room."""
    thinned = [{**activity, IMPACT_GRID: {
        lens: {band: score for band, score in row.items() if band != DROPPED_HORIZON}
        for lens, row in activity[IMPACT_GRID].items()}} for activity in _activities(ctx)]
    said = views.render({**ctx["record"], ACTIVITIES: thinned})[views.WORKSHEET]

    assert f"| {DROPPED_HORIZON} |" in said, "a horizon nobody scored was left out of the grid"
    assert views.NOT_SCORED in said


@then("it says why before it says the number")
def _it_says_why_before_the_number(ctx):
    derived = [line for line in ctx["read"].splitlines() if "intolerable" in line]
    assert derived, "no figure on this worksheet was derived from the grid"
    for said in derived:
        assert said.index("reaches") < said.index("stands at"), said


@given("a record whose activity names more than one data set")
def _a_record_naming_more_than_one_data_set(ctx):
    _record_holds(ctx, **{DATA_SETS: DATA_SET_FIGURES})


@then("the RTO and the RPO are shown for each data set by name")
def _the_rto_and_rpo_are_shown_per_data_set(ctx):
    for item in DATA_SET_FIGURES:
        assert figures.TARGETS.format(name=item[NAME], rto=item[RECOVERY_TARGET],
                                    rpo=item[RPO]) in ctx["read"]


@then("one data set's figure is never shown as though it covered them all")
def _one_data_sets_figure_is_not_shown_as_covering_all(ctx):
    for activity in _activities(ctx):
        assert f"For {activity[NAME]}:" not in ctx["read"], "a figure was printed for all of it"
    assert "as a whole" not in ctx["read"]


@then("the MBCO is there, character for character as the record has it")
def _the_mbco_is_there_character_for_character(ctx):
    for activity in _activities(ctx):
        assert activity[MBCO] in ctx["read"], "the record's own words are not on the worksheet"
        assert figures.MBCO_SAYS.format(activity=activity[NAME], mbco=activity[MBCO]) in ctx["read"]


@given("a record that names the minimum resources over time")
def _a_record_that_names_the_minimum_resources(ctx):
    _record_holds(ctx, **{RESOURCES: RESOURCE_FIGURES})


@then("each resource is there with what is needed by when")
def _each_resource_is_there_with_what_is_needed_by_when(ctx):
    for item in RESOURCE_FIGURES:
        assert f"{item[NAME]} — needed by {item[BY_WHEN]}." in ctx["read"]


@then("each one carries the workaround for doing without it")
def _each_resource_carries_its_workaround(ctx):
    for item in RESOURCE_FIGURES:
        assert f"Without it: {item[WORKAROUND]}." in ctx["read"]


@given("a record whose activity depends on register entries")
def _a_record_whose_activity_depends_on_register_entries(ctx):
    _accepted(ctx)
    assert [activity for activity in _views(ctx) and _activities(ctx) if activity[DEPENDENCIES]]


@then("each dependency is named by the register id the record holds")
def _each_dependency_is_named_by_its_register_id(ctx):
    for activity in _activities(ctx):
        for asset_id in activity[DEPENDENCIES]:
            assert asset_id in ctx["read"], f"{asset_id} is not on the worksheet"


@then("no id appears that the record does not hold")
def _no_id_appears_that_the_record_does_not_hold(ctx):
    held = {asset_id for activity in _activities(ctx) for asset_id in activity[DEPENDENCIES]}
    printed = set(re.findall(r"\b[A-Z]{2}-\d+\b", ctx["read"]))
    assert printed == held, f"the worksheet names ids the record does not hold: {printed - held}"
    assert "KA-09" not in ctx["read"], "the register's lookalike id reached the worksheet"


@then("each scored category shows the exact quote the score rests on")
def _each_scored_category_shows_its_exact_quote(ctx):
    scored = [item for activity in _activities(ctx)
              for item in activity[EVIDENCE] if item.get(LENS)]
    assert scored, "nothing on this record is scored, so this proves nothing"
    for item in scored:
        assert views.SCORED.format(lens=item[LENS], quote=item[QUOTE],
                                   path=item[SOURCE_PATH]) in ctx["read"]


@then("the file that quote came from is beside it")
def _the_file_that_quote_came_from_is_beside_it(ctx):
    for activity in _activities(ctx):
        for item in activity[EVIDENCE]:
            said = ctx["read"]
            assert f"“{item[QUOTE]}” ({item[SOURCE_PATH]})" in said
            assert (ctx["room_folder"] / item[SOURCE_PATH]).is_file()


# ------------------------------------------------------------------ nothing but the record is read


@when("the transcripts, the dependency register and the method file are taken out of my room")
def _the_room_s_own_files_are_taken_out(ctx):
    """Whatever the scenario had rendered before its sources went, kept to compare against:
    ticket 16's four views, or ticket 18's three documents."""
    ctx["rendered_before"] = ctx.get("three") or ctx["views"]
    for path in (INTERVIEWS, REGISTER, METHOD):
        shutil.move(ctx["room_folder"] / path, ctx["tmp"] / "taken-out" / path.replace("/", "-"))
    assert not (ctx["room_folder"] / REGISTER).exists()


@then("they are byte for byte what they were")
def _they_are_byte_for_byte_what_they_were(ctx):
    """What the scenario rendered again, against what it held before. Ticket 16's four views are
    compared against the copies on disk as well; ticket 18's three documents are held in
    `again` by the step that re-rendered them, the room's own copies having been read into
    `three` before anything was taken out of it."""
    if "again" in ctx:
        assert ctx["again"] == ctx["rendered_before"]
        return
    assert ctx["views"] == ctx["rendered_before"]
    for name, view in ctx["views"].items():
        assert (ctx["room_folder"] / _view_path(ctx, name)).read_bytes() == view.encode()


@given("a record that says nothing about the minimum resources")
def _a_record_that_says_nothing_about_the_resources(ctx):
    _accepted(ctx)
    for activity in _activities(_views(ctx) and ctx):
        assert RESOURCES not in activity, "this record names resources, so this proves nothing"


@then("it says that was not established")
def _it_says_that_was_not_established(ctx):
    for activity in _activities(ctx):
        assert figures.NO_RESOURCES.format(activity=activity[NAME]) in ctx["read"]
        assert "were not established" in ctx["read"]


@then("no resource appears that the record does not name")
def _no_resource_appears_that_the_record_does_not_name(ctx):
    assert "Without it" not in ctx["read"], "a resource nobody wrote down is on the worksheet"


# ------------------------------------------------------------------ the shrink refusal


@given(parsers.parse('"{at}" holds {size:d} bytes'))
def _a_view_holds_so_many_bytes(ctx, at, size):
    """v1's own numbers: the capture that went 10,514 -> 2,099 bytes with its headings intact."""
    assert at == _view_path(ctx, views.CAPTURE)
    write_document(ctx["room_folder"], at, "x" * size)
    ctx["saved_bytes"] = (ctx["room_folder"] / at).read_bytes()
    assert len(ctx["saved_bytes"]) == size


@when(parsers.parse("something tries to overwrite it with {size:d} bytes"))
def _something_tries_to_overwrite_it(ctx, size):
    _offer(ctx, views.CAPTURE, "y" * size)


@then("the write is refused")
@then("it is refused just the same")
def _the_write_is_refused(ctx):
    assert ctx["refusal"] is not None, "the document was overwritten with a fraction of itself"


@then("the refusal names the document and both byte counts, so a human decides whether the "
      "record lost something")
def _the_refusal_names_the_document_and_both_counts(ctx):
    said = str(ctx["refusal"])
    assert views.CAPTURE in said, "the refusal does not say which document it is about"
    assert str(len(ctx["saved_bytes"])) in said and str(len(ctx["offered"])) in said
    assert ctx["refusal"].saved == len(ctx["saved_bytes"])
    assert ctx["refusal"].offered == len(ctx["offered"])


@given('a saved view and a replacement carrying exactly the same "##" headings')
def _a_saved_view_and_a_replacement_with_the_same_headings(ctx):
    saved = (ctx["room_folder"] / _view_path(ctx, views.WORKSHEET)).read_text(encoding="utf-8")
    ctx["headings"] = [line for line in saved.splitlines() if line.startswith("##")]
    assert ctx["headings"], "this document has no headings, so this proves nothing"
    ctx["saved_bytes"] = saved.encode()


@when("the replacement is a fraction of the saved size")
def _the_replacement_is_a_fraction_of_the_saved_size(ctx):
    gutted = "\n\n".join(ctx["headings"]) + "\n"
    assert len(gutted.encode()) * 2 < len(ctx["saved_bytes"]), "the replacement is not a fraction"
    _offer(ctx, views.WORKSHEET, gutted)


@then("the refusal is about the bytes, not about the headings")
def _the_refusal_is_about_the_bytes(ctx):
    said = str(ctx["refusal"])
    assert "bytes" in said and str(len(ctx["saved_bytes"])) in said
    for about in ("##", "heading", "section", "title"):
        assert about not in said.lower(), f"the refusal talks about {about!r}"
    saved_now = (ctx["room_folder"] / _view_path(ctx, views.WORKSHEET)).read_bytes()
    assert saved_now == ctx["saved_bytes"]


@given("each of the four views has been saved")
def _each_of_the_four_views_has_been_saved(ctx):
    _the_four_views_are_rendered(ctx)
    assert {path.name for path in (ctx["room_folder"] / views.folder(ctx["record"])).iterdir()
            if path.name != RECORD_NAME} == set(VIEWS)


@when("each in turn is offered a replacement a fraction of its size")
def _each_in_turn_is_offered_a_fraction(ctx):
    ctx["refusals"] = {}
    for name in VIEWS:
        _offer(ctx, name, "y" * 20)
        ctx["refusals"][name] = ctx["refusal"]


@then("every one of the four is refused")
def _every_one_of_the_four_is_refused(ctx):
    for name in VIEWS:
        assert ctx["refusals"][name] is not None, f"{name} was overwritten with a fraction"
        assert name in str(ctx["refusals"][name])


@given("a saved view")
def _a_saved_view(ctx):
    ctx["saved_bytes"] = (ctx["room_folder"] / _view_path(ctx, views.WORKSHEET)).read_bytes()
    assert ctx["saved_bytes"], "there is no saved view to shrink"


@when("an overwrite is refused for shrinking it")
def _an_overwrite_is_refused_for_shrinking_it(ctx):
    _offer(ctx, views.WORKSHEET, "y" * 20)
    assert ctx["refusal"] is not None


@then("the bytes on disk are the ones that were there before")
def _the_bytes_on_disk_are_the_ones_that_were_there_before(ctx):
    saved = (ctx["room_folder"] / _view_path(ctx, views.WORKSHEET)).read_bytes()
    assert saved == ctx["saved_bytes"], "the refusal truncated the document it refused"


@then("the refusal is reported rather than swallowed")
def _the_refusal_is_reported_rather_than_swallowed(ctx):
    assert isinstance(ctx["refusal"], Shrunk)
    with pytest.raises(Shrunk):
        write_document(ctx["room_folder"], _view_path(ctx, views.WORKSHEET), "y" * 20)


@when("a re-render is the same size or larger")
def _a_re_render_is_the_same_size_or_larger(ctx):
    for text in ("z" * len(ctx["saved_bytes"]), "z" * (len(ctx["saved_bytes"]) + 500)):
        _offer(ctx, views.WORKSHEET, text)
        assert ctx["refusal"] is None, f"an honest re-render was refused: {ctx['refusal']}"


@then("it is written without argument")
def _it_is_written_without_argument(ctx):
    saved = (ctx["room_folder"] / _view_path(ctx, views.WORKSHEET)).read_bytes()
    assert saved == ctx["offered"].encode()


@given("my room holds no view for this process yet")
def _my_room_holds_no_view_for_this_process_yet(ctx):
    _accepted(ctx)
    for name in VIEWS:  # the record lives beside them since ticket 235, and stays
        (ctx["room_folder"] / views.folder(_landed(ctx)) / name).unlink()
    assert not [path for path in _files(ctx["room_folder"]) if path.endswith(tuple(VIEWS))]


@then("all four are written")
@then("all four views are written")
def _all_four_are_written(ctx):
    for name in VIEWS:
        written = ctx["room_folder"] / _view_path(ctx, name)
        assert written.is_file(), f"{name} was not written"
        assert written.read_text(encoding="utf-8") == ctx["views"][name]


# ------------------------------------------------------------------ five activities, measured


@when("I accept the record")
def _i_accept_the_record(ctx):
    _accept(ctx)
    _views(ctx)


@then("every one of the five is in the worksheet in full")
def _every_one_of_the_five_is_in_the_worksheet_in_full(ctx):
    """And what five does to each view on a phone, which is the measurement the story asks for.

    Measured on this record, in screenfuls of `PHONE_SCREEN` (700 characters, stage 4a's own
    number for what a phone holds before a thumb moves), five activities against the same room's
    one-activity department:

        scope and guide        9 screens, against 2      (5,702 characters, against 1,400)
        interview capture     11 screens, against 3      (7,219, against 1,796)
        dependency analysis    9 screens, against 2      (5,643, against 1,321)
        worksheet             13 screens, against 3      (8,756, against 2,094)

    So five activities cost between four and five times the scrolling, and the longest of the four
    is thirteen phone screens with no index in it. That is the number the story asked somebody to
    write down; it is recorded rather than acted on, because whether thirteen screens is usable is
    a claim only a reader settles — QA section H puts the worksheet in a stranger's hands and
    times them finding one activity's figure, and the owner decides from that.
    """
    said = ctx["views"][views.WORKSHEET]
    assert len(_activities(ctx)) == 5
    for activity in _activities(ctx):
        assert figures.stands(activity, ctx["record"]["method"]) in said
        assert figures.MBCO_SAYS.format(activity=activity[NAME],
                                      mbco=activity.get(MBCO) or figures.NOTHING) in said
        assert f"| {DROPPED_HORIZON} |" in said
        for item in activity[EVIDENCE]:
            assert f"“{item[QUOTE]}” ({item[SOURCE_PATH]})" in said
        assert figures.TARGETS.format(name=activity[NAME], rto=activity[RECOVERY_TARGET],
                                    rpo=activity[RPO]) in said
        assert figures.DEPENDS.format(activity=activity[NAME],
                                    ids=figures.listed(activity[DEPENDENCIES])) in said
    screens = {name: -(-len(view) // PHONE_SCREEN) for name, view in ctx["views"].items()}
    assert screens == FIVE_ACTIVITY_VIEWS, screens
# ══════════════════════ 17 — stage 4c, the receipt that binds the record ═══════════════════════
#
# `features/stage-4c-the-graph-and-its-receipt.feature`. The background walks the real stages and
# presses endorsed's **first** movement, the record onto disk. Every scenario below names what
# follows it: the receipt binding the record, or the stop before it did — which is a state on disk
# here rather than a state a step pretends to, because ADR-0010 makes it the ordinary path and not
# the crash path. Ticket 243 (ADR-0040): nemo draws no page of its own, so nothing here reads one.


@given("I walked to stage 4 and accepted the record the server refereed")
def _i_walked_to_stage_4_and_accepted_the_refereed_record(ctx):
    _i_have_agreed_the_scope_and_bound_the_interview(ctx)
    _record(ctx)
    assert ENDORSED in ctx["card"].buttons, "there was nothing to accept the record with"
    ctx["acts"].append(("press", ENDORSED))
    ctx["saved_card"] = ctx["card"] = _only_the_record(ctx)
    ctx["saved_run"] = _saved(ctx)


def _press_endorsed(ctx):
    """The whole answer, over whatever the room holds: both of stage 4's movements, one door."""
    ctx["acts"].append(("press", ENDORSED))
    ctx["card"] = _said(ctx, ENDORSED)[0]
    return ctx["card"]


def _receipt(ctx):
    return _saved(ctx)[RECEIPT]


def _receipt_binds(ctx):
    assert _receipt(ctx)["record_sha"] == fingerprint(_landed(ctx)), "the receipt is not bound"


# --------------------------------------------------------------------- saved is not finished


@given("a record has just been saved")
@given("a receipt exists")
def _a_record_has_just_been_saved(ctx):
    _press_endorsed(ctx)
    assert _landed(ctx)["run_id"] == _saved(ctx)["run_id"], "the record is not this walk's"


@given("a record has been saved and the receipt has not yet bound")
def _a_record_has_been_saved_and_the_receipt_not_bound(ctx):
    """The stop between the two movements, as the background left it: the record on disk and the
    run carrying no receipt to bind it."""
    assert _landed(ctx) is not None and _receipt(ctx) is None
    ctx["run"] = ctx["saved_run"]


@then(parsers.parse("the walk's status is \"{status}\""))
def _the_walks_status_is(ctx, status):
    assert status == RECORD_SAVED, f"the story asks for {status!r}, which the walk does not have"
    assert ctx["saved_run"]["status"] == status


@then("stage 5 cannot start")
def _stage_5_cannot_start(ctx):
    with pytest.raises(NotDrawnYet) as refused:
        move_past_stage_4(ctx["room_folder"], ctx["saved_run"])
    assert str(refused.value) == SAVED_NOT_FINISHED


# ------------------------------------------------------- no page of nemo's own, and the receipt


@then(parsers.parse('nothing is under "{folder}"'))
def _nothing_is_under(ctx, folder):
    assert ctx["held"], "the room holds nothing at all, so this proves nothing"
    assert not [path for path in ctx["held"] if path.startswith(folder)], ctx["held"]


@then("it carries the fingerprint of the record on disk and the record's version, and nothing else")
def _the_receipt_carries_the_record_and_nothing_else(ctx):
    assert _receipt(ctx) == {"record_sha": fingerprint(_landed(ctx)),
                             "record_version": _landed(ctx)["record_schema_version"]}


@given(parsers.parse('I press "{label}" at stage 4'))
def _i_press_at_stage_4(ctx, label):
    assert label == ENDORSED and label in record_card(ctx["room_folder"], ctx["process"]).buttons
    ctx["threads_before"] = threading.active_count()


@when("the walk answers me")
def _the_walk_answers_me(ctx):
    _press_endorsed(ctx)


@then("nothing about the receipt is left for a later job to finish")
def _nothing_is_left_for_a_later_job(ctx):
    """The press returns the card that speaks to me, so anything true when it returns was true
    before I was spoken to."""
    assert ctx["card"].body.endswith(PICTURE_DRAWN)
    assert threading.active_count() == ctx["threads_before"], "the press left something running"
    _receipt_binds(ctx)
    assert where_it_stands(_saved(ctx)) == "", "the walk is still waiting for the receipt"


# ------------------------------------------------------------------ binding, both signs


@when("the receipt binds")
def _the_receipt_binds(ctx):
    _receipt_binds(ctx)


@then(parsers.parse('the walk is no longer at "{status}"'))
def _the_walk_is_no_longer_at(ctx, status):
    assert status == RECORD_SAVED
    assert _saved(ctx)["status"] == AWAITING_HUMAN != status
    assert where_it_stands(_saved(ctx)) == ""


@then("stage 5 can start")
def _stage_5_can_start(ctx):
    assert move_past_stage_4(ctx["room_folder"], _saved(ctx)) == _landed(ctx)


@when("the record in my room is replaced by one that receipt was never taken over")
def _the_record_is_replaced_by_one_the_receipt_was_never_taken_over(ctx):
    replaced = _landed(ctx)
    ctx["run"] = _saved(ctx)
    write_record(ctx["room_folder"], _record_at(ctx),
                 {**{key: value for key, value in replaced.items() if key != "revision"},
                  "dept": "IT helpdesk and support"}, replaced["revision"])
    assert fingerprint(_landed(ctx)) != ctx["run"][RECEIPT]["record_sha"]


@then("the walk is back at saved and not yet finished")
def _the_walk_is_back_at_saved_and_not_yet_finished(ctx):
    with pytest.raises(NotDrawnYet) as refused:
        move_past_stage_4(ctx["room_folder"], ctx["run"])
    assert str(refused.value) == SAVED_NOT_FINISHED


@then("the receipt binds again to the record now on disk before stage 5 can start")
def _the_receipt_binds_again_before_stage_5(ctx):
    resume(ctx["room_folder"], ctx["process"])

    _receipt_binds(ctx)
    _stage_5_can_start(ctx)


# ------------------------------------------------------- a stop between the two movements


@given("the walk stopped after the record landed and before the receipt bound")
def _the_walk_stopped_after_the_record_landed(ctx):
    _a_record_has_been_saved_and_the_receipt_not_bound(ctx)


@then("the receipt binds and the walk is waiting for me again")
def _the_receipt_binds_and_the_walk_waits_for_me(ctx):
    _receipt_binds(ctx)
    assert _saved(ctx)["status"] == AWAITING_HUMAN
    assert ctx["card"].body.endswith(PICTURE_DRAWN) and ctx["card"].buttons == ()


# ----------------------------------------------- what may never be said while nothing is bound


@when("I read everything the walk says about where it stands")
def _i_read_everything_the_walk_says_about_where_it_stands(ctx):
    ctx["where"] = where_it_stands(ctx["saved_run"])
    card = ctx["saved_card"]
    ctx["prose"] = " ".join((card.heading, card.body, card.decision, card.rule, ctx["where"]))


@then("no sentence says my BIA is finished")
def _no_sentence_says_my_bia_is_finished(ctx):
    """The word may appear — it is how the walk says what is *not* so — but only ever in the
    clause that names the thing still left. Everything else it might be said with is checked as
    the words themselves, because a manager reads "all done" as finished too."""
    for sentence in re.split(r"(?<=[.?!]) ", ctx["prose"]):
        assert "finish" not in sentence or "one thing left before this walk is finished" in \
            sentence, sentence
    for claim in ("is complete", "is closed", "all done", "nothing left", "that is everything"):
        assert claim not in ctx["prose"].lower(), claim
    assert SAVED_NOT_FINISHED in ctx["prose"], "it says nothing about where it stands at all"


# ═════════════════════ 24 — the one door: a walk is answered with words ══════════════════════
#
# `features/the-one-door-a-walk-is-answered-with-words.feature`. Every step below answers a card
# the way a manager does: typed words into `nemo.walk.answer`, with the revision the card on the
# screen was read at. None of them names a stage to the door and none of them calls a per-stage
# function — that is the whole of ADR-0013 and the scenarios are written to catch either.

#: The seven things a press used to call, each now private behind the one door. Named here rather
#: than discovered, because the scenario that reads the tree for them has to fail when one comes
#: back under its old public name, and a discovered list would come back empty and pass.
#:
#: This file is one of the files that scenario reads, so this declaration is the one place in the
#: tree allowed to spell them: `_sources` cuts exactly these two lines out of this file's text
#: before looking, by the marker below and nothing wider. Anywhere else, in any file, a mention is
#: a hit — a comment that still calls the stage 4 answer by its old public name is stale prose.
PRESS_FUNCTIONS = ("agree_scope", "keep_interview", "bind_interview", "answer_evidence",  # named
                   "accept_record", "save_record", "take_naming")                         # named

#: The words a manager answers a card with when he means it and holds nothing back.
PLAIN = "Yes, that reads right to me."

#: The same answer with something held back in it — one word, "but", which is as far as the rough
#: reading goes and as far as the owner's 80/20 ruling asks it to go.
CAVEAT = "Yes, but the Cisco Call Manager figure looks optimistic to me."

#: A BCM question, which is what the ask lane exists for and what must never be filed as an answer.
BCM_QUESTION = "what does MTPD mean?"


def _walk_to(ctx, stage, process=None):
    """This walk driven to that stage through the one door and nothing else (ADR-0013).

    Typed words at every stage on the way, never a press and never a per-stage call: what these
    scenarios are about is exactly what a manager can reach, so a step that got to stage 4 by any
    other route would prove nothing about the stage he cannot reach.
    """
    if process is not None:
        _on_the_menu(ctx, process)
        ctx["process"] = process
    ctx.pop("picked", None)
    ctx["card"] = open_bia(ctx["room_folder"], ctx["process"])
    ctx.setdefault("stages", []).append(ctx["card"].stage)
    while ctx["card"].stage < stage:
        ctx["before"] = _files(ctx["room_folder"])
        moved = _said(ctx, ENDORSED)
        assert len(moved) > 1, f"stage {ctx['card'].stage} was answered and the walk stood still"
        ctx["card"] = moved[-1]
        ctx["stages"].append(ctx["card"].stage)
    assert ctx["card"].stage == stage, f"this walk stands at stage {ctx['card'].stage}"
    return ctx["card"]


def _sources(kind):
    """Every Python file in the tree, minus the walk itself, as (name, text) to read for a name.

    A line ending in the `# named` marker is dropped: that is `PRESS_FUNCTIONS` above, the one
    declaration in the tree that has to spell the seven in order to look for them. Nothing else
    carries the marker, and a line that grew one would be doing so to hide a call.
    """
    return [(str(path.relative_to(REPO)), _DECLARED.sub("", path.read_text(encoding="utf-8")))
            for path in sorted(REPO.rglob("*.py"))
            if ".venv" not in path.parts and "mutants" not in path.parts
            and (path != REPO / "src" / "nemo" / "walk.py") == (kind == "outside")]


#: The marker `_sources` cuts: a whole line, so a call cannot ride along on the end of one.
_DECLARED = re.compile(r"^.*# named$\n?", re.MULTILINE)


# ------------------------------------------------------------------ the blocker itself


@given(parsers.parse('I have walked "{process}" to the stage {stage:d} card'))
def _i_have_walked_to_the_stage_card(ctx, process, stage):
    _walk_to(ctx, stage, process)


@when("I answer it in words")
@when("I type an ordinary answer")
def _i_answer_it_in_words(ctx):
    assert _type(ctx, PLAIN) is not None, "the walk did not take my words"


@then("my BIA is saved in my room, the four views are written and the receipt binds it")
def _my_bia_is_saved_the_views_are_written_and_the_receipt_binds(ctx):
    record = _landed(ctx)
    assert record, "no BIA is in my room"
    written = _files(ctx["room_folder"])
    for name in views.FOUR:
        assert any(path.endswith(name) for path in written), f"{name} was not written"
    assert not [path for path in written if path.startswith("public/graph/")], (
        "nemo drew a page of its own")
    _receipt_binds(ctx)


@then("nothing on the way there failed on a stage nobody built an answer for")
def _nothing_failed_on_a_stage_nobody_built_an_answer_for(ctx):
    """The `KeyError: 4` this ticket exists to end, read off the walk rather than off a traceback.

    Every stage the walk stood at was answered through the one door — there is no per-stage table
    to be missing a row — so what is asserted is that the walk went through all four of them.
    """
    assert ctx["stages"] == [1, 2, 3, 4], f"this walk stood at {ctx['stages']}"
    assert [decision["stage"] for decision in _saved(ctx)["decisions"]] == [1, 2, 3, 4]


@then("nothing here signs anything, because the signature is ticket 18's")
def _nothing_here_signs_anything(ctx):
    saved = _saved(ctx)
    assert saved["status"] == AWAITING_HUMAN, f"this walk says {saved['status']}"
    assert "signature" not in json.dumps(saved), "something was signed"
    assert _landed(ctx).get("signature") is None, "the record carries a signature"


# ---------------------------------------------------------------- one door, every stage


@given("a card at stage 1, at stage 2, at stage 3 and at stage 4 in turn")
def _a_card_at_each_stage_in_turn(ctx):
    ctx["card"] = open_bia(ctx["room_folder"], ctx["process"])
    ctx["stages"] = [ctx["card"].stage]


@when("each is answered with typed words")
def _each_is_answered_with_typed_words(ctx):
    """Four answers, one call apiece, and the same call every time: which stage each of them
    answers is read off the room inside the door, never named out here (ADR-0010)."""
    ctx["doors"] = []
    while ctx["card"].stage < STAGE_4:
        ctx["doors"].append(answer)
        following = answer(ctx["room_folder"], ctx["process"], PLAIN, ctx["card"].revision,
                           record_revision=ctx["card"].record_revision)
        ctx["card"] = following[-1]
        ctx["stages"].append(ctx["card"].stage)
    ctx["doors"].append(answer)
    answer(ctx["room_folder"], ctx["process"], PLAIN, ctx["card"].revision,
           record_revision=ctx["card"].record_revision)


@then("every one of them is answered through the same entry point")
def _every_one_is_answered_through_the_same_entry_point(ctx):
    assert ctx["stages"] == [1, 2, 3, 4], f"this walk stood at {ctx['stages']}"
    assert set(ctx["doors"]) == {answer}, "more than one thing answered a card"
    assert [decision["stage"] for decision in _saved(ctx)["decisions"]] == [1, 2, 3, 4]


@then("the seven per-stage press functions are private behind it")
def _the_seven_press_functions_are_private(ctx):
    for name in PRESS_FUNCTIONS:
        assert hasattr(walk, f"_{name}"), f"{name} is not behind the door at all"
        assert not hasattr(walk, name), f"{name} is still public on the walk"


# ------------------------------------------- nothing outside the walk names one of them


@given("the demo skin, the step bodies and every test in the tree")
def _the_skin_the_steps_and_every_test(ctx):
    ctx["outside"] = _sources("outside")
    assert len(ctx["outside"]) > 10, "this read almost nothing, so it proves nothing"


@when("I read what they call to answer a card")
def _i_read_what_they_call_to_answer_a_card(ctx):
    ctx["names"] = [(where, name) for where, source in ctx["outside"]
                    for name in PRESS_FUNCTIONS if name in source]


@then("it is the one public entry point, in all of them")
def _it_is_the_one_public_entry_point(ctx):
    answering = [where for where, source in ctx["outside"] if "walk.answer" in source
                 or "import answer" in source or "    answer,\n" in source]
    assert answering, "nothing in the tree answers a card at all, so this proves nothing"


@then("no per-stage press function is named anywhere outside the walk itself")
def _no_per_stage_press_function_is_named_outside(ctx):
    assert ctx["names"] == [], f"the press protocol is still named: {ctx['names']}"
    inside = dict(_sources("inside"))
    assert len(inside) == 1 and all(
        f"_{name}" in next(iter(inside.values())) for name in PRESS_FUNCTIONS)


# -------------------------------------------------------------- a stage at a time, in words


@given(parsers.parse('the stage 1 card proposing "{process}"'))
def _the_stage_1_card_proposing(ctx, process):
    card = _walk_to(ctx, STAGE, process)
    assert card.activities == (process,), f"this card proposes {card.activities}"


@when("I type that the scope is right")
def _i_type_that_the_scope_is_right(ctx):
    assert _type(ctx, "Yes, that is exactly the scope of it.") is not None


@then("the scope is agreed on disk with the answer I gave")
def _the_scope_is_agreed_on_disk_with_the_answer_i_gave(ctx):
    agreed = _saved(ctx)["decisions"][0]
    assert without_telemetry(agreed) == {
        "stage": STAGE, "decided": "yes", "gradient": ENDORSED}, agreed


@then(parsers.parse("the walk moves to stage {stage:d}"))
def _the_walk_moves_to_stage(ctx, stage):
    """Read off the room rather than off the card in hand: what came back is the confirmation of
    the stage just answered, and which stage follows it is the walk's own business (ADR-0010)."""
    following = onward(ctx["room_folder"], ctx["card"])
    assert following and following[0].stage == stage, f"nothing at stage {stage} follows"


@given("the stage 2 card offering the interview in my room")
def _the_stage_2_card_offering_the_interview(ctx):
    card = _walk_to(ctx, STAGE_2)
    assert len(card.interviews) == 1, f"the card offers {len(card.interviews)} interviews"
    ctx["picked"] = card.interviews[0]


@when("I type that this is the interview my BIA should rest on")
def _i_type_that_this_is_the_interview(ctx):
    assert _type(ctx, "Yes, that's the interview this should rest on.") is not None


@then("that interview is bound to my BIA with its own bytes beside it")
def _that_interview_is_bound_with_its_own_bytes(ctx):
    bound = _saved(ctx)["transcript"]
    assert bound["path"] == ctx["picked"].path
    assert bound["fingerprint"] == ctx["picked"].fingerprint
    assert (ctx["room_folder"] / bound["path"]).read_bytes() == ctx["picked"].preview.encode()


# Ticket 194's scenario, re-aimed onto the phone app by ticket 164 (16_nemo_check's ruling (a)): the
# phone holds the interview, so it is the phone that must say it could not start. The room is the
# phone's own, minted from the seed its drafts were made for; the scenario plants one activity with
# no interview on file (every activity of that seed has one), and the model's move on his words is
# scripted as the tool call it makes (`hold_interview`), never inferred.


@given("a process my room holds no interview for")
def _a_process_my_room_holds_no_interview_for(ctx, skin):
    _minted_by_the_door(ctx, skin, ctx["room"])
    _open(ctx, f"/demo/r/{ctx['room']}")
    assert ctx["error"] is None, f"the room did not open: {ctx['error']!r}"
    s = skin_harness.session()
    ctx["room_folder"], ctx["process"] = s.folder, walk.processes(s.folder)[0]
    for interview in held(s.folder, ctx["process"]):  # the plant
        (s.folder / interview.path).unlink()
    assert held(s.folder, ctx["process"]) == (), "the room holds one after all"
    s.dispatch("get_step", {"activity": ctx["process"]})
    s.dispatch("answer_step", {"activity": ctx["process"], "answer": "endorsed"})
    card = walk.current(s.folder, ctx["process"])
    assert card.stage == STAGE_2 and HOLD_IT_NOW in card.buttons, card


@when("I type that we should hold the interview now")
def _i_type_that_we_should_hold_the_interview_now(ctx, skin):
    """His words go to the model, and the model's move on them is to start nemo's interview."""
    ctx["before"] = _files(ctx["room_folder"])
    skin_harness.SCRIPTED.append(skin_harness.tool_call("hold_interview", activity=ctx["process"]))
    del skin_harness.SENT[:]
    skin_harness.type_into_the_composer("Let's do the interview now")
    assert not skin_harness.SCRIPTED, "the model was never asked about his words"


@given("the service that asks the interview's questions refuses every call")
def _the_interview_lane_refuses_every_call(skin, monkeypatch):
    """Ticket 194: the phone's interview lane (`core.interview_lane`) refuses at every call, as a
    dead port reaches it: `LaneUnavailable`. No socket, so the harness's no-network guard stands."""
    def refusing(model, room=None):
        def lane(prompt):
            raise LaneUnavailable("the lane did not answer")
        return lane
    monkeypatch.setattr(skin.core, "interview_lane", refusing)


@then("I am told plainly the interview could not start, no interview card is offered, nothing is saved")
def _i_am_told_the_interview_could_not_start(ctx):
    on_screen = "\n".join(_on_screen())
    assert NOT_STARTED in on_screen, on_screen
    assert DECISION_CHOSEN not in on_screen and STOPPED not in on_screen, (
        "an empty interview was offered to rest on")
    assert skin_harness.session()._interview is None, "an empty interview is still under way"
    assert not (ctx["room_folder"] / interview_path(ctx["process"])).exists(), (
        "an interview nobody gave is on disk")
    assert held(ctx["room_folder"], ctx["process"]) == ()


@given("an interview held in this room and previewed whole")
def _an_interview_held_in_this_room_and_previewed_whole(ctx):
    """The interview conducted here and shown back whole, with nothing of it on disk yet: the
    bytes the manager read exist only on the card until his answer keeps them."""
    _walk_to(ctx, STAGE_2, OTHER_PROCESS)
    turns = (Turn("What does this process do?", "It resolves the IT faults users report."),)
    ctx["picked"] = held_interview(ctx["room_folder"], ctx["process"], turns).interviews[0]
    ctx["before"] = _files(ctx["room_folder"])
    ctx["card"] = held_interview(ctx["room_folder"], ctx["process"], turns)


@when("I type my answer to the preview")
def _i_type_my_answer_to_the_preview(ctx):
    assert _type(ctx, PLAIN) is not None


@then("exactly the previewed bytes are filed and bound in one save")
def _exactly_the_previewed_bytes_are_filed_and_bound(ctx):
    filed = ctx["room_folder"] / ctx["picked"].path
    assert filed.read_bytes() == ctx["picked"].preview.encode()
    bound = _saved(ctx)["transcript"]
    assert (bound["path"], bound["fingerprint"]) == (ctx["picked"].path, ctx["picked"].fingerprint)
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_2


# ---------------------------------------------------------- what words become, in the record


@when("I type a plain answer that holds nothing back")
def _i_type_a_plain_answer(ctx):
    assert _type(ctx, PLAIN) is not None


@then("the record carries it as endorsed")
def _the_record_carries_it_as_endorsed(ctx):
    assert _saved(ctx)["decisions"][-1]["gradient"] == ENDORSED


@then("I am not asked to name anything")
def _i_am_not_asked_to_name_anything(ctx):
    assert "naming" not in _saved(ctx)["decisions"][-1]
    assert ctx["card"].body != NAMING, "the card is asking me to name something"


@when("I type an answer that holds something back")
def _i_type_an_answer_that_holds_something_back(ctx):
    assert _type(ctx, CAVEAT) is not None


@then("the record carries an answer other than endorsed, with the reservation unnamed")
def _the_record_carries_an_answer_other_than_endorsed(ctx):
    decided = _saved(ctx)["decisions"][-1]
    assert decided["gradient"] != ENDORSED and decided["naming"] == UNNAMED, decided


@then("the card asks me to name it, in plain words, so I know the box is the walk's")
def _the_card_asks_me_to_name_it_in_plain_words(ctx):
    assert ctx["card"].body == NAMING
    assert "belongs to this BIA rather than to your questions" in ctx["card"].body


@then("the stage has moved on anyway, so disagreeing cost me no more than agreeing")
def _the_stage_has_moved_on_anyway(ctx):
    assert _saved(ctx)["decisions"][-1]["stage"] == STAGE_3
    assert ctx["card"].buttons == (), "the card is still holding the walk up to be answered"


@given("a plain answer the walk read as a caveat")
def _a_plain_answer_the_walk_read_as_a_caveat(ctx):
    _the_stage_3_card(ctx)
    assert _type(ctx, CAVEAT) is not None
    assert _saved(ctx)["decisions"][-1]["naming"] == UNNAMED


@when("I say there is nothing I want to record")
def _i_say_there_is_nothing_i_want_to_record(ctx):
    assert _type(ctx, "Nothing.") is not None


@then("no reservation is left on that stage's answer")
def _no_reservation_is_left_on_that_stages_answer(ctx):
    decided = _saved(ctx)["decisions"][-1]
    assert decided.get("naming") is None and decided["gradient"] == ENDORSED, decided


@then("nothing reaches the signature saying I reserved something")
def _nothing_reaches_the_signature_saying_i_reserved(ctx):
    assert namings(_saved(ctx)) == (), f"the walk still carries {namings(_saved(ctx))}"


# -------------------------------------------------------------- the four claimants, in order


@given("a walk waiting for me to name a reservation")
def _a_walk_waiting_for_me_to_name_a_reservation(ctx):
    _a_plain_answer_the_walk_read_as_a_caveat(ctx)
    assert ctx["card"].body == NAMING


@when("I type words that would read as a BCM question")
def _i_type_words_that_would_read_as_a_bcm_question(ctx):
    assert BCM_QUESTION.rstrip().endswith("?"), "these words would not reach the ask lane"
    assert _type(ctx, BCM_QUESTION) is not None, "the walk let the ask lane have them"


@then("they are kept as the naming, verbatim")
def _they_are_kept_as_the_naming_verbatim(ctx):
    assert _saved(ctx)["decisions"][-1]["naming"] == BCM_QUESTION


@then("no answer from the guidance corpus reaches the page")
def _no_answer_from_the_corpus_reaches_the_page(ctx):
    assert ctx["card"].body == TAKEN, ctx["card"].body


@given("the stage 3 card, open and waiting")
def _the_stage_3_card_open_and_waiting(ctx):
    _the_stage_3_card(ctx)
    ctx["waiting"] = ctx["card"]
    ctx["decisions_before"] = _saved(ctx)["decisions"]


@then("it is answered from the frozen guidance corpus, citation and all")
def _it_is_answered_from_the_frozen_corpus(ctx):
    assert ctx["taken"] is None, "the walk swallowed a BCM question"
    assert ctx["lane"].text == _recorded_answer()
    assert ctx["lane"].citations, "the answer rests on no corpus chunk"


@then("nothing is recorded as my answer to that card")
def _nothing_is_recorded_as_my_answer_to_that_card(ctx):
    assert _saved(ctx)["decisions"] == ctx["decisions_before"]


@then("the card is still waiting for me afterwards")
def _the_card_is_still_waiting_for_me_afterwards(ctx):
    assert _stage_card(ctx, ctx["waiting"].stage) == ctx["waiting"]


@given("the stage 4 card, open and waiting")
def _the_stage_4_card_open_and_waiting(ctx):
    _walk_to(ctx, STAGE_4)
    ctx["decisions_before"] = _saved(ctx)["decisions"]


@given("no interview underway and no reservation to name")
def _no_interview_underway_and_no_reservation_to_name(ctx):
    assert _last_named(ctx) is None, "a naming is still awaited"


@then("it answers that card")
def _it_answers_that_card(ctx):
    decided = _saved(ctx)["decisions"][-1]
    assert decided["stage"] == STAGE_4 and _saved(ctx)["decisions"] != ctx["decisions_before"]


def _last_named(ctx, process=None):
    """What this walk's last answer left to be named, or nothing if it left nothing."""
    return _saved(ctx, process)["decisions"][-1].get("naming")


# --------------------------------------------- a reservation names the BIA it was made on


@given(parsers.parse('walks in progress for "{first}" and for "{second}" in the same room'))
def _walks_in_progress_for_both(ctx, first, second):
    """Two walks live in one room, which is the ordinary state and the one defect 1 of the
    2026-09-13 code review is about: a naming taken off the room picks whichever sorts first."""
    for process in (first, second):
        _interview_file_for(ctx, process)
        _walk_to(ctx, STAGE_3, process)
    ctx["walks"] = (first, second)
    assert sorted(in_progress(ctx["room_folder"])) == sorted(_slugs(first, second))


def _interview_file_for(ctx, process):
    """One interview for that process, so the walk can be carried past stage 2 in words."""
    was, ctx["process"] = ctx.get("process"), process
    _on_the_menu(ctx, process)
    if not held(ctx["room_folder"], process):
        _interview_file(ctx, INTERVIEWS, f"{process}-interview.md")
    ctx["process"] = was or process


def _slugs(*processes_named):
    return [run_file(process).rsplit("/", 1)[1].removesuffix(".json")
            for process in processes_named]


@given(parsers.parse('I answer "{process}" with something held back'))
def _i_answer_with_something_held_back(ctx, process):
    ctx["process"] = process
    ctx["card"] = _stage_card(ctx, STAGE_3)
    assert _type(ctx, CAVEAT) is not None
    assert _last_named(ctx, process) == UNNAMED


@when("I name the reservation")
def _i_name_the_reservation(ctx):
    ctx["named"] = "the Cisco Call Manager figure"
    assert _type(ctx, ctx["named"]) is not None


@then(parsers.parse("it is attached to \"{process}\"'s answer"))
def _it_is_attached_to_that_processs_answer(ctx, process):
    assert _last_named(ctx, process) == ctx["named"], _saved(ctx, process)["decisions"]


@then(parsers.parse("\"{process}\"'s walk carries no reservation at all"))
def _that_walk_carries_no_reservation_at_all(ctx, process):
    assert namings(_saved(ctx, process)) == (), f"{process} carries {namings(_saved(ctx, process))}"
    assert UNNAMED not in json.dumps(_saved(ctx, process)), f"{process} carries an unnamed one"


@given("two walks in one room, both waiting for a naming")
def _two_walks_both_waiting_for_a_naming(ctx):
    ctx["walks"] = (THIS_PROCESS, OTHER_PROCESS)
    for process in ctx["walks"]:
        _interview_file_for(ctx, process)
        _walk_to(ctx, STAGE_3, process)
        assert _type(ctx, CAVEAT) is not None
        assert _last_named(ctx, process) == UNNAMED


@when("I name the reservation on the one I am working through")
def _i_name_the_reservation_on_the_one_i_am_working_through(ctx):
    ctx["mine"], ctx["other"] = ctx["walks"]
    ctx["process"] = ctx["mine"]
    ctx["card"] = _stage_card(ctx, STAGE_3)
    ctx["named"] = "the Cisco Call Manager figure"
    assert _type(ctx, ctx["named"]) is not None


@then("the other walk is still waiting for its own")
def _the_other_walk_is_still_waiting_for_its_own(ctx):
    assert _last_named(ctx, ctx["other"]) == UNNAMED


@then("neither naming was filed against the other's BIA")
def _neither_naming_was_filed_against_the_others_bia(ctx):
    assert _last_named(ctx, ctx["mine"]) == ctx["named"]
    assert ctx["named"] not in json.dumps(_saved(ctx, ctx["other"]))


# ------------------------------------------- the compare-and-set, through the public door


@given("the stage 3 card I read, and a write that landed after I read it")
def _the_stage_3_card_i_read_and_a_write_after_it(ctx):
    """The card in hand, and then the room moved on underneath it — the second tab, the re-scan,
    the resumed walk after a half-landed write, which is why the guard stays."""
    ctx["card"] = _draft(ctx)
    run = read_record(ctx["room_folder"], run_file(ctx["process"]))
    write_record(ctx["room_folder"], run_file(ctx["process"]), run, run["revision"])
    ctx["before_answer"] = _saved(ctx)


@when("I answer with the revision that card carried")
def _i_answer_with_the_revision_that_card_carried(ctx):
    assert ctx["card"].revision < _saved(ctx)["revision"], "the room did not move on"
    ctx["taken"] = _type(ctx, PLAIN)


@then("my answer is not recorded")
def _my_answer_is_not_recorded(ctx):
    assert _saved(ctx)["decisions"] == ctx["before_answer"]["decisions"]


@then("what comes back is that stage's card again, in the walk's own words about being overtaken")
def _what_comes_back_is_that_stages_card_again(ctx):
    """The refusal is the walk's, word for word — whatever ticket 29 makes those words. Nothing
    here reads the sentence, only that the card came back saying it (second-opinion finding 8)."""
    assert ctx["taken"] is not None, "nothing came back at all"
    assert ctx["taken"].stage == STAGE_3, f"stage {ctx['taken'].stage} came back"
    assert ctx["taken"].body.startswith(OVERTAKEN), ctx["taken"].body


@then("the answer already on disk is untouched")
def _the_answer_already_on_disk_is_untouched(ctx):
    assert _saved(ctx)["revision"] == ctx["before_answer"]["revision"]


# --------------------------------------------------- what is left of the press protocol


def _an_interview_the_referee_passes(ctx, process):
    """This room's interview swapped for one the referee has nothing to refuse.

    A card the referee refuses is not a card a manager answers at all — stage 4 says so in its own
    words and offers nothing — so a scenario about *how* a card is answered has to stand on a walk
    that reaches an answerable one. The background's testimony is a paragraph with no grid in it.
    """
    was, ctx["process"] = ctx.get("process"), process
    _on_the_menu(ctx, process)
    _interview_file(ctx, INTERVIEWS, f"{process}-interview.md").write_text(
        REFEREED_TRANSCRIPT.replace("Incident and problem management", process),
        encoding="utf-8")
    register = ctx["room_folder"] / REGISTER
    held = json.loads(register.read_bytes()) if register.is_file() else {}
    register.write_text(json.dumps({**held, **EVIDENCE_ASSETS}), encoding="utf-8")
    ctx["process"] = was or process


@given("a room offering three processes and a process with two interviews on file")
def _a_room_offering_three_processes_and_two_interviews(ctx):
    for process in (THIS_PROCESS, OTHER_PROCESS, "event-management"):
        _on_the_menu(ctx, process)
    was, ctx["process"] = ctx["process"], THIS_PROCESS
    _interview_file(ctx, OWNER_INTERVIEWS, f"{THIS_PROCESS}-interview-transcript.md")
    ctx["process"] = was
    assert len(processes(ctx["room_folder"])) == 3
    assert len(held(ctx["room_folder"], THIS_PROCESS)) == 2


@when("I open a BIA and choose between the interviews")
def _i_open_a_bia_and_choose_between_the_interviews(ctx):
    _open_room(ctx)
    _press_process(ctx, THIS_PROCESS)
    ctx["card"] = _walk_to(ctx, STAGE_2)
    _press_interview(ctx, ctx["card"].interviews[1])


@then("both are still a choice I make from what the room holds")
def _both_are_still_a_choice_from_what_the_room_holds(ctx):
    assert ("press", THIS_PROCESS) in ctx["acts"] and ("press", ctx["picked"].name) in ctx["acts"]
    assert ctx["picked"] in _stage_card(ctx, STAGE_2).interviews


@then("neither asks me to type a name")
def _neither_asks_me_to_type_a_name(ctx):
    assert ctx["typed"] == "", f"something was typed: {ctx['typed']!r}"


# ------------------------------------------------- the slice, and the movement a resume owes


@given("a walk that saved its record and stopped before the receipt bound")
def _a_walk_that_saved_and_stopped_before_the_receipt(ctx):
    _walk_to(ctx, STAGE_4)
    ctx["card"] = _only_the_record(ctx, PLAIN)
    assert _saved(ctx)["status"] == RECORD_SAVED and not _saved(ctx)[RECEIPT]


@when("it is resumed")
def _it_is_resumed(ctx):
    ctx["card"] = resume(ctx["room_folder"], ctx["process"])


@then("the receipt binds the record on disk")
def _the_receipt_binds_the_record_on_disk(ctx):
    _receipt_binds(ctx)
    assert ctx["card"].body.endswith(PICTURE_DRAWN) and ctx["card"].buttons == ()


@then("that second movement is still reachable without calling a private function")
def _the_second_movement_is_reachable_without_a_private_function(ctx):
    assert not resume.__name__.startswith("_")
    assert getattr(walk, "resume", None) is resume
# ══════════════════════ 18 — stage 5, consolidate, hand over and sign ════════════════════════════
#
# `features/stage-5-consolidate-hand-over-and-sign.feature`. The background leaves the record on
# disk with no picture drawn over it, which is where ticket 17 stops; every step below either
# names that stop or draws the picture and walks the last stage over it. Nothing here builds a
# record by hand: the documents are a function of the record bytes, so a record a step wrote
# would be a document about a step.

#: Who the interview has stating the process's own figures, and who it has stating somebody else's.
#: Both come out of `REFEREED_TRANSCRIPT` rather than being chosen here: the owner check compares
#: a signer with the name the record holds, so a name invented in a step would prove nothing.
THE_OWNER = "Marek Sobotta"
NOT_THE_OWNER = "Tim Ohlsen"
MY_ROLE = "Head of IT Operations"

#: The role v1 validated a sign-off under, in v1's own words. The check reads the name, so this
#: string is here to be ignored — which is the whole of what the scenario watches.
DISCLAIMED = "explicitly not the process owner"

#: An interview whose modelled dependency the register puts under another department, which is
#: the contradiction stage 3 raises in both sources' own words and stage 5 carries to the
#: signature without settling.
DISPUTED_TRANSCRIPT = REFEREED_TRANSCRIPT.replace(
    "Depends on: Atlassian Jira,", "Depends on: Cisco Call Manager (IT helpdesk and support), "
    "Atlassian Jira,")

#: Words a document that picked a recovery solution would have to use. Each one is allowed
#: exactly where the method says it chooses none — the sentence, not the word, is what is
#: checked, because "no site, no supplier, no system" is the refusal itself.
CHOOSING = ("site", "supplier", "system", "vendor", "failover", "standby", "provider")
PLANNING = ("plan", "planning")


def _sentences(text):
    """The text as a reader meets it: one sentence at a time, headings included."""
    return [part for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _refusals(record, run):
    """The sentences this method uses to say it chose nothing — the only ones allowed a word
    from `CHOOSING` or `PLANNING`. They are the module's own constants rather than copies, so a
    sentence reworded upstream cannot quietly widen what a document may say."""
    return set(_sentences(handover.BOUNDARY)) | set(_sentences(handover.NOT_APPROVAL)) | set(
        _sentences(handover.NO_METHOD)) | set(_sentences(handover.READER)) | set(
        _sentences(handover.LABEL)) | {
        text for _at, text in handover.items(record, run)} | set(run.get("findings") or [])


def _receipted(ctx):
    """The background's record with the picture drawn over it and the receipt binding the two.

    The second movement is asked for by the one name that is still public for it — `resume`, the
    walk's own way of getting a stop between the two movements finished (ADR-0010) — rather than
    by reaching behind the door for the movement itself.
    """
    if _receipt(ctx) is None:
        ctx["card"] = resume(ctx["room_folder"], ctx["process"])
    ctx["record"], ctx["run"] = _landed(ctx), _saved(ctx)
    assert _receipt(ctx)["record_sha"] == fingerprint(ctx["record"])
    return ctx["record"]


def _walk_over(ctx, transcript):
    """This walk again over a different interview, to the record and the receipt that binds it."""
    _rewalk(ctx, transcript)
    _press_button(ctx, ENDORSED)
    return _receipted(ctx)


def _rendered(ctx):
    """The two documents for the record and run this scenario has in hand. Writes nothing."""
    return handover.documents(ctx["record"], ctx["run"])


def _accept_the_handover(ctx):
    """Stage 5's one gradient answer, pressed on the card the walk serves of its own accord."""
    if _saved(ctx)["status"] != REVIEWED:
        _receipted(ctx)
        ctx["handed"] = ctx["card"] = _stage_card(ctx, STAGE_5)
        _press_button(ctx, ENDORSED)
        ctx["record"], ctx["run"] = _landed(ctx), _saved(ctx)
    return ctx["card"]


def _sign_as(ctx, name, role):
    """The signature: two typed replies, and every open item this BIA left, accepted by its id."""
    _accept_the_handover(ctx)
    ctx["asked_to_sign"] = signature_card(ctx["room_folder"], ctx["process"])
    ctx["ids"] = tuple(at for at, _text in handover.items(ctx["record"], ctx["run"]))
    ctx["typed_at_signature"] = (name, role)
    ctx["card"] = sign(ctx["room_folder"], ctx["asked_to_sign"], name, role)
    ctx["run"] = _saved(ctx)
    return ctx["card"]


def _certificate_path(ctx):
    return ctx["room_folder"] / views.folder(ctx["record"]) / handover.CERTIFICATE


def _three(ctx):
    """The three documents as they lie on disk, which is the only place a reader meets them."""
    folder = ctx["room_folder"] / views.folder(ctx["record"])
    return {name: (folder / name).read_text(encoding="utf-8")
            for name in (handover.DRAFT, handover.HANDOVER, handover.CERTIFICATE)}


# ------------------------------------------------------------ the receipt is the gate


@given("a record saved with no graph receipt")
def _a_record_saved_with_no_graph_receipt(ctx):
    assert _landed(ctx) is not None, "there is no record here to be refused over"
    assert _receipt(ctx) is None, "the picture was drawn already"
    ctx["run"] = ctx["saved_run"]


@when("I try to reach stage 5")
def _i_try_to_reach_stage_5(ctx):
    ctx["refusal"] = None
    try:
        handover_card(ctx["room_folder"], ctx["process"])
        ctx["onward"] = onward(ctx["room_folder"], ctx["saved_card"])
    except NotDrawnYet as refused:
        ctx["refusal"] = refused


@then("I cannot, and the walk says it is not finished")
def _i_cannot_and_the_walk_says_it_is_not_finished(ctx):
    assert isinstance(ctx["refusal"], NotDrawnYet)
    assert str(ctx["refusal"]) == SAVED_NOT_FINISHED
    assert where_it_stands(ctx["run"]) == SAVED_NOT_FINISHED
    assert _files(ctx["room_folder"]) & {
        f"{views.folder(_landed(ctx))}/{name}"
        for name in (handover.DRAFT, handover.HANDOVER, handover.CERTIFICATE)} == set()


# ------------------------------------------------------------ rendered from the record bytes


@given("a record and its receipt")
@given("a record carrying an open risk")
def _a_record_and_its_receipt(ctx):
    _receipted(ctx)
    assert ctx["record"][OPEN_ITEMS], "this record leaves nothing open to carry"


@then("the management BIA and the requirements handover are rendered from the record bytes")
def _both_are_rendered_from_the_record_bytes(ctx):
    """Rendered *from the bytes*: the same record twice gives the same two documents, and one
    byte of it changed gives different ones. Nothing else in the room is consulted."""
    assert set(_rendered(ctx)) == {handover.DRAFT, handover.HANDOVER}
    assert _rendered(ctx) == handover.documents(_landed(ctx), _saved(ctx))
    edited = {**ctx["record"], DEPT: "IT helpdesk and support"}
    assert handover.documents(edited, ctx["run"]) != _rendered(ctx)
    assert _stage_card(ctx, STAGE_5).proposal[DOCUMENTS] == _rendered(ctx)


@then("every reservation and contradiction from every earlier gradient answer is carried onto them")
def _every_reservation_and_contradiction_is_carried(ctx):
    """Every earlier answer, so the run this asserts over carries one at each of them: the walk
    the background pressed endorsed all the way down, and a document that carried a reservation
    only from the stage a scenario happened to reserve at would say nothing about the others."""
    reserved = {**ctx["run"], "decisions": [
        {"stage": stage, "gradient": GRADIENT[2], "naming": f"what I reserved at stage {stage}"}
        for stage in (1, 2, STAGE_3, STAGE_4)]}
    for said in handover.documents(ctx["record"], reserved).values():
        for _stage, words in namings(reserved):
            assert words in said, words
        for contradiction in ctx["record"][OPEN_ITEMS]:
            assert contradiction in said, contradiction


# ------------------------------------------------------------ accepting is not signing


@given("I have accepted the handover")
def _i_have_accepted_the_handover(ctx):
    _accept_the_handover(ctx)


@then(parsers.parse("the walk is `{status}`"))
@then(parsers.parse("the walk is still `{status}`"))
def _the_walk_is(ctx, status):
    assert status in (REVIEWED, CLOSED), f"the walk has no state called {status!r}"
    assert _saved(ctx)["status"] == status


@then("no certificate has been written")
def _no_certificate_has_been_written(ctx):
    assert not _certificate_path(ctx).exists(), "accepting wrote a certificate"
    assert SIGNATURE not in _saved(ctx)


# ------------------------------------------------------------ a yes is not a signature


@given(parsers.parse('a chat message saying "{message}"'))
def _a_chat_message_saying(ctx, message):
    """Typed into the same box every card before it was answered in, through the one door.

    Nothing of this walk is waiting for the composer once the handover is accepted — what is left
    is the signature, and a signature demands a name and a role by name — so the door hands the
    words straight back as nobody's, which is what `_type` reads as `None`.
    """
    _accept_the_handover(ctx)
    ctx["message"] = message
    _type(ctx, message)


@then("no named person's signature is recorded")
def _no_named_persons_signature_is_recorded(ctx):
    """Nothing in the room was waiting for those words, so they are a question and not an answer.
    The only door a signature comes through demands a name and a role by name."""
    assert ctx["taken"] is None, "a general message was taken as an answer to the walk"
    assert SIGNATURE not in _saved(ctx)
    assert not _certificate_path(ctx).exists()
    assert _saved(ctx)["status"] == REVIEWED
    assert {"name", "role"} <= set(inspect.signature(sign).parameters)


# ------------------------------------------------------------ the certificate does not overclaim


@given("I signed, and nothing anywhere captured an email")
def _i_signed_and_nothing_captured_an_email(ctx):
    """Nothing captured an email anywhere, read off the room rather than asserted: no file this
    walk wrote holds an address, and the door never asked for one (`docs/stage-model.md:189`)."""
    _sign_as(ctx, THE_OWNER, MY_ROLE)
    for path, raw in _bytes(ctx).items():
        assert not re.search(rb"[\w.]+@[\w.]+", raw), f"{path} captured an email"


@then(parsers.parse('the certificate reads "{words}", in those words'))
def _the_certificate_reads_in_those_words(ctx, words):
    assert words == handover.ASSERTED
    assert words in _certificate_path(ctx).read_text(encoding="utf-8")


# ------------------------------------------------------------ what the handover says on its face


@when("I read the requirements handover")
def _i_read_the_requirements_handover(ctx):
    ctx["handover"] = _rendered(ctx)[handover.HANDOVER]


@then("it says on its face that it is a requirements handover for solution-design discussion")
def _it_says_it_is_a_requirements_handover(ctx):
    assert handover.LABEL in ctx["handover"]
    assert "requirements handover for solution-design discussion" in ctx["handover"]


@then("it says it is not approved")
def _it_says_it_is_not_approved(ctx):
    assert "It is not approved" in ctx["handover"]
    assert "approved" not in ctx["handover"].replace("It is not approved", "")


@then("it is addressed to whoever designs the continuity solutions next")
def _it_is_addressed_to_whoever_designs_the_solutions(ctx):
    assert handover.READER in ctx["handover"]


@then("it tells the reader nothing about how to design a continuity solution")
def _it_tells_the_reader_nothing_about_how(ctx):
    assert handover.NO_METHOD in ctx["handover"]
    allowed = _refusals(ctx["record"], ctx["run"])
    for sentence in _sentences(ctx["handover"]):
        if sentence not in allowed:
            for word in CHOOSING + PLANNING:
                assert not re.search(rf"\b{word}s?\b", sentence, re.IGNORECASE), sentence


# ------------------------------------------------------------ what it carries, item by item


@given("a record whose department has more than one prioritised activity")
def _a_record_with_more_than_one_activity(ctx):
    _walk_over(ctx, FIVE_ACTIVITIES)
    assert len(ctx["record"][ACTIVITIES]) > 1


@then("every one of them carries its own MTPD, recovery target, recovery point, MBCO, "
      "minimum resources and dependencies")
def _every_activity_carries_its_own_figures(ctx):
    """Under its own heading, said plainly: named there and "this activity" after it (t64; nemo's
    own wording since t133), so each sentence is read in its own activity's section."""
    method = ctx["record"][RECORD_METHOD]
    for activity in ctx["record"][ACTIVITIES]:
        heading = handover.ACTIVITY.format(activity=activity[NAME]) + "\n\n"
        assert heading in ctx["handover"], activity[NAME]
        own = ctx["handover"].split(heading, 1)[1].split("\n\n#")[0]
        for sentence in figures.requirements(activity, method):
            said = handover.said_plainly(sentence, activity[NAME], method)
            assert said in own, said


@given("a record that refers something to the risk assessment")
def _a_record_that_refers_something_to_the_risk_assessment(ctx):
    """No stage writes a referral yet, so this one is put on the record the walk produced. The
    document is a function of the record bytes, which is exactly what lets a step do that."""
    _receipted(ctx)
    ctx["referral"] = {REFERS: "whether Cisco Call Manager can fail closed",
                       REFERRED_TO: "the risk assessment owner"}
    ctx["record"] = {**ctx["record"], REFERRALS: [ctx["referral"]]}


@then("the referral is there, said as what it refers and to whom")
def _the_referral_is_there(ctx):
    assert handover.REFERRAL.format(refers=ctx["referral"][REFERS],
                                    to=ctx["referral"][REFERRED_TO]) in ctx["handover"]
    assert handover.NO_REFERRALS not in ctx["handover"]


@given("a record whose activity has evidence missing")
def _a_record_whose_activity_has_evidence_missing(ctx):
    _receipted(ctx)
    activity, = ctx["record"][ACTIVITIES]
    ctx["gaps"] = [handover.said_plainly(gap, activity[NAME], ctx["record"][RECORD_METHOD])
                   for gap in (figures.MBCO_SAYS.format(activity=activity[NAME],
                                                        mbco=figures.NOTHING),
                               figures.NO_RESOURCES.format(activity=activity[NAME]))]
    assert not activity.get(MBCO) and not activity.get(RESOURCES), "nothing is missing here"


@then("it says what is missing")
def _it_says_what_is_missing(ctx):
    for gap in ctx["gaps"]:
        assert gap in ctx["handover"], gap


@then("no figure is shown in the gap's place")
def _no_figure_is_shown_in_the_gaps_place(ctx):
    for gap in ctx["gaps"]:
        assert not re.search(r"\d", gap), gap


@given("a record the referee raised findings on")
def _a_record_the_referee_raised_findings_on(ctx):
    _walk_over(ctx, FALLING_TRANSCRIPT)
    assert ctx["run"][FINDINGS], "the referee raised nothing over this record"


@then("every finding is there, in the words the referee raised it in")
def _every_finding_is_there_verbatim(ctx):
    for finding in ctx["run"][FINDINGS]:
        assert finding in ctx["handover"], finding
    assert handover.NO_FINDINGS not in ctx["handover"]


@then("it says where the BIA stops and what the reader decides after it")
def _it_says_where_the_bia_stops(ctx):
    assert handover.BOUNDARY in ctx["handover"]


# ------------------------------------------------------------ every earlier gradient answer


@given(parsers.parse('I answered stage 3 with "{label}" and typed what I was reserving'))
def _i_answered_stage_3_with_and_typed(ctx, label):
    """Stage 3 answered on the way up, on a walk begun again for it — see `_walk_again`."""
    _walk_again(ctx)
    _press_button(ctx, label)
    assert _type(ctx, NAMED) is not None, "the walk was not holding the composer for me"
    _accept(ctx)
    _receipted(ctx)


@then("my words are there exactly as I typed them, against the card I typed them on")
def _my_words_are_there_exactly(ctx):
    """Against the card they were typed on: the stage the run files them under, not a stage the
    step chose — a reservation carried onto the wrong card is a reservation about something else."""
    reserved, = [entry for entry in ctx["run"]["decisions"] if entry.get(NAMING_FIELD)]
    assert reserved["stage"] == STAGE_3 and reserved["gradient"] == GRADIENT[1]
    assert handover.RESERVATION.format(stage=reserved["stage"], gradient=reserved["gradient"],
                                       naming=NAMED) in ctx["handover"]
    assert namings(ctx["run"]) == ((STAGE_3, NAMED),)


@given(parsers.parse('I answered a card with something other than "{label}" and typed nothing '
                     "after it"))
def _i_answered_with_something_other_than_and_typed_nothing(ctx, label):
    """The reservation nobody named, made on the stage 4 card — the one card it survives on.

    While a naming is awaited the composer belongs to the walk (`docs/voice.md` §4.3), so a
    reservation left unnamed at stage 1, 2 or 3 stops the walk where it was made: the next thing
    typed is the naming, whatever it is, and nothing else can be answered until it is. Stage 4 is
    the card whose record is already saved and whose picture is already drawn by the time the
    asking goes up, so it is the one answer that reaches the handover still carrying `unnamed`.
    """
    assert label == ENDORSED
    _walk_again(ctx)
    _press_button(ctx, ENDORSED)
    assert ctx["typed"] == "", "something was typed, so this proves nothing"
    _accept(ctx, GRADIENT[2])
    _receipted(ctx)


@then("it says a reservation was recorded and never named")
def _it_says_a_reservation_was_recorded_and_never_named(ctx):
    assert handover.NOT_NAMED.format(stage=STAGE_4, gradient=GRADIENT[2]) in ctx["handover"]


@then("that answer is not shown as an endorsement")
def _that_answer_is_not_shown_as_an_endorsement(ctx):
    assert handover.RESERVATION.format(stage=STAGE_4, gradient=ENDORSED,
                                       naming=UNNAMED) not in ctx["handover"]
    assert namings(ctx["run"]) == ((STAGE_4, UNNAMED),)


@given("a record carrying a contradiction between what the interview said and what the register "
       "holds")
def _a_record_carrying_a_contradiction(ctx):
    _walk_over(ctx, DISPUTED_TRANSCRIPT)
    ctx["contradiction"], = [text for text in ctx["record"][OPEN_ITEMS]
                             if DISPUTED_DEPENDENCY in text]


@then("both sides of it are there, and neither has been settled on my behalf")
def _both_sides_are_there_and_neither_settled(ctx):
    assert ctx["contradiction"] in ctx["handover"]
    assert "IT helpdesk and support" in ctx["contradiction"]
    assert "Incident and problem management" in ctx["contradiction"]
    assert "Both cannot be right" in ctx["handover"]


# ------------------------------------------------------------ accepting, and then signing


@when("I accept the handover")
def _i_accept_the_handover(ctx):
    ctx["acts_before"] = list(ctx["acts"])
    _accept_the_handover(ctx)


@then("that is one answer and nothing else was demanded of me")
def _that_is_one_answer_and_nothing_else(ctx):
    assert ctx["acts"][len(ctx["acts_before"]):] == [("press", ENDORSED)]
    assert ctx["typed"] == "", "accepting the handover asked me to type something"
    assert ctx["handed"].buttons == GRADIENT
    assert _saved(ctx)["status"] == REVIEWED


@when("I am asked to sign")
def _i_am_asked_to_sign(ctx):
    ctx["asked_to_sign"] = signature_card(ctx["room_folder"], ctx["process"])


@then("it asks for my name and my role, and says signing accepts every open item listed")
def _it_asks_for_my_name_and_my_role_over_the_items(ctx):
    card = ctx["asked_to_sign"]
    assert card.decision == DECISION_SIGN
    for wanted in ("who is signing", "in what role"):
        assert wanted in card.decision.lower(), wanted
    assert "signing accepts every open item listed" in card.body.lower()
    for at, _text in handover.items(ctx["record"], ctx["run"]):
        assert at in card.body, at
    assert ("name", "role") == tuple(list(inspect.signature(sign).parameters)[2:4])


@given("a clean run where the server proposed right every time")
def _a_clean_run_where_the_server_proposed_right(ctx):
    _receipted(ctx)
    assert [entry["gradient"] for entry in ctx["run"]["decisions"]] == [ENDORSED] * len(
        ctx["run"]["decisions"]), "something on the way here was not endorsed as it stood"
    assert ctx["typed"] == ""


@when("I reach the end of it")
def _i_reach_the_end_of_it(ctx):
    _sign_as(ctx, THE_OWNER, MY_ROLE)


@then("the name and the role are the only two things I typed at the signature")
def _the_name_and_the_role_are_the_only_two_typed(ctx):
    assert ctx["typed_at_signature"] == (THE_OWNER, MY_ROLE)
    assert len(ctx["typed_at_signature"]) == 2
    assert ctx["card"].buttons == () and where_it_stands(ctx["run"]) == ""


@then("the whole walk cost no more than seven typed replies")
def _the_whole_walk_cost_no_more_than_seven(ctx):
    typed = [act for act in ctx["acts"] if act[0] not in ("press", "open")]
    assert typed == [], "something before the signature was typed rather than pressed"
    assert len(typed) + len(ctx["typed_at_signature"]) <= 7


@given("a record carrying a dependency with no owner")
def _a_record_carrying_a_dependency_with_no_owner(ctx):
    _receipted(ctx)
    ctx["unowned"], = [text for text in ctx["record"][OPEN_ITEMS]
                       if UNMODELLED_DEPENDENCY in text]


@when("I sign")
def _i_sign(ctx):
    _sign_as(ctx, THE_OWNER, MY_ROLE)


@then("I accept that finding by its id, at this signature")
def _i_accept_that_finding_by_its_id(ctx):
    at, = [at for at, text in handover.items(ctx["record"], ctx["run"])
           if text == ctx["unowned"]]
    assert at in ctx["ids"] and at in _saved(ctx)[SIGNATURE][ACCEPTED]
    assert f"{at} — {ctx['unowned']}" in _certificate_path(ctx).read_text(encoding="utf-8")


@then("no further stage is opened to chase the owner")
def _no_further_stage_is_opened(ctx):
    assert _saved(ctx)["stage"] == STAGE_5 and _saved(ctx)["status"] == CLOSED
    assert onward(ctx["room_folder"], ctx["card"]) == ()
    assert ctx["card"].heading.startswith(f"Stage {STAGE_5} of {STAGE_5}")


# ------------------------------------------------------------ who is allowed to sign this


@given("I have accepted the handover and I am the owner of the activity")
def _i_have_accepted_and_i_am_the_owner(ctx):
    _accept_the_handover(ctx)
    ctx["signer"] = THE_OWNER
    assert handover.owners(ctx["record"]) == (THE_OWNER,)


@given("I have accepted the handover and I am not the owner of the activity")
def _i_have_accepted_and_i_am_not_the_owner(ctx):
    _accept_the_handover(ctx)
    ctx["signer"] = NOT_THE_OWNER
    assert NOT_THE_OWNER not in handover.owners(ctx["record"])


@when("I sign with my name and my role")
def _i_sign_with_my_name_and_my_role(ctx):
    _sign_as(ctx, ctx["signer"], MY_ROLE)


@then("the certificate is written")
def _the_certificate_is_written(ctx):
    assert _certificate_path(ctx).read_text(encoding="utf-8") == handover.certificate(
        ctx["record"], _saved(ctx))


@then("it is either refused or recorded as sponsor acceptance")
def _it_is_either_refused_or_recorded_as_sponsor_acceptance(ctx):
    assert _saved(ctx)[SIGNATURE][CAPACITY] == handover.SPONSOR
    assert not _certificate_path(ctx).exists(), "a sponsor's acceptance wrote a certificate"
    assert handover.SPONSOR in ctx["card"].body


@given(parsers.parse('a signer whose role reads "{role}"'))
def _a_signer_whose_role_reads(ctx, role):
    assert role == DISCLAIMED
    _accept_the_handover(ctx)
    ctx["signer"], ctx["role"] = NOT_THE_OWNER, role


@when("they sign")
def _they_sign(ctx):
    _sign_as(ctx, ctx["signer"], ctx["role"])


@then("nothing anywhere calls that sign-off valid")
def _nothing_anywhere_calls_that_signoff_valid(ctx):
    assert not _certificate_path(ctx).exists()
    said = " ".join((ctx["card"].body, ctx["card"].heading, json.dumps(_saved(ctx))))
    for claim in ("valid", "approved", "signed off", "accepted as the owner"):
        assert claim not in said.lower(), claim
    assert _saved(ctx)[SIGNATURE][CAPACITY] == handover.SPONSOR
    assert handover.OWNER_OF_THE_ACTIVITY not in said
    assert _saved(ctx)["status"] == REVIEWED != CLOSED


# ------------------------------------------------------------ the three documents on disk


@given(parsers.parse('I signed with authority for the process "{process}"'))
def _i_signed_with_authority_for_the_process(ctx, process):
    _sign_as(ctx, THE_OWNER, MY_ROLE)
    assert views.folder(ctx["record"]) == f"output/{process}"


@given("I signed with authority")
@given("the three documents have been written")
def _i_signed_with_authority(ctx):
    _sign_as(ctx, THE_OWNER, MY_ROLE)
    ctx["three"] = _three(ctx)


#: Three quoted names and no more. `parsers.parse` would read ticket 16's four-name line as this
#: one, with two filenames swallowed into the middle capture, so the quotes are spelled out.
THREE_NAMED = r'"(?P<folder>[^"]+)" holds "(?P<first>[^"]+)", "(?P<second>[^"]+)" and ' \
              r'"(?P<third>[^"]+)"$'


@then(parsers.re(THREE_NAMED))
def _the_folder_holds_the_three(ctx, folder, first, second, third):
    assert (first, second, third) == (handover.DRAFT, handover.HANDOVER, handover.CERTIFICATE)
    assert {f"{folder}{name}" for name in (first, second, third)} <= ctx["held"]


@when("they are rendered again from the same record")
def _they_are_rendered_again_from_the_same_record(ctx):
    record, run = _landed(ctx), _saved(ctx)
    ctx["again"] = {**handover.documents(record, run),
                    handover.CERTIFICATE: handover.certificate(record, run)}


@then(parsers.parse('not one of them uses the word "{word}"'))
def _not_one_of_them_uses_the_word(ctx, word):
    for name, text in ctx["three"].items():
        assert not re.search(rf"\b{word}", text, re.IGNORECASE), name


# ------------------------------------------------------------ the certificate


@when("I read the certificate")
def _i_read_the_certificate(ctx):
    ctx["certificate"] = _certificate_path(ctx).read_text(encoding="utf-8")


@then("it carries my name, my role, and the id of every open item I accepted")
def _it_carries_my_name_my_role_and_every_id(ctx):
    assert handover.BY.format(name=THE_OWNER, role=MY_ROLE,
                              capacity=handover.OWNER_OF_THE_ACTIVITY) in ctx["certificate"]
    for at in ctx["ids"]:
        assert at in ctx["certificate"], at
    assert ctx["ids"], "this run accepted nothing, so this proves nothing"


@then("it never says an identity was confirmed, checked or verified by anything")
def _it_never_says_an_identity_was_verified(ctx):
    said = ctx["certificate"].replace(handover.ASSERTED, "")
    for stronger in ("confirmed", "verified", "checked", "authenticated", "email", "@"):
        assert stronger not in said.lower(), stronger
    assert handover.ASSERTED in ctx["certificate"]


# ------------------------------------------------------------ where the method stops


@when("I read all three documents")
def _i_read_all_three_documents(ctx):
    _sign_as(ctx, THE_OWNER, MY_ROLE)
    ctx["three"] = _three(ctx)
    ctx["handover"] = ctx["three"][handover.HANDOVER]


@then("not one of them picks a site, a supplier, a system or a way of recovering")
def _not_one_of_them_picks_a_solution(ctx):
    allowed = _refusals(ctx["record"], _saved(ctx))
    for name, text in ctx["three"].items():
        for sentence in _sentences(text):
            if sentence in allowed:
                continue
            for word in CHOOSING:
                assert not re.search(rf"\b{word}s?\b", sentence, re.IGNORECASE), (name, sentence)


@then("the risk is stated and left open for a human to accept")
def _the_risk_is_stated_and_left_open(ctx):
    for at, text in handover.items(ctx["record"], _saved(ctx)):
        assert f"{at} — {text}" in ctx["handover"]
        assert f"{at} — {text}" in ctx["three"][handover.DRAFT]
        assert f"{at} — {text}" in ctx["three"][handover.CERTIFICATE]
    assert THE_OWNER in ctx["three"][handover.CERTIFICATE], "nobody is named as accepting it"
    assert handover.NOTHING_OPEN not in ctx["handover"]


@then("there is no plan in any of them, and the handover says the BIA stops here")
def _there_is_no_plan_in_any_of_them(ctx):
    allowed = _refusals(ctx["record"], _saved(ctx))
    for name, text in ctx["three"].items():
        for sentence in _sentences(text):
            if sentence in allowed:
                continue
            for word in PLANNING:
                assert not re.search(rf"\b{word}s?\b", sentence, re.IGNORECASE), (name, sentence)
    assert handover.BOUNDARY in ctx["handover"]
# ═══════════════ 32 — a digit inside a name is not a figure the record must hold ══════════════════
# The dead screen and the reading of the repo. The rest of this story — what is *still* refused —
# is checked a card and a record at a time in `features/conftest.py`, beside ticket 09's own steps,
# because the carve-out is one rule inside that one check.

TICKET_09 = REPO / "docs" / "issues" / "nemo-walk" / "issues" / (
    "09-the-card-must-agree-with-the-record.md")

#: The two exemptions, in the words the shipped code uses for them. `nemo.card`'s module docstring
#: is where they are stated; ticket 09 must state them wherever it states the rule.
EXEMPTIONS = ("verbatim interview preview", "a name the room supplies")


def _rule_statements(text):
    """Every paragraph of ticket 09 that states the rule — what a reader would read and believe."""
    said = [norm(block) for block in text.split("\n\n")]
    said = [block for block in said if "string the" in block and "holds" in block]
    assert said, "ticket 09 no longer states the rule at all"
    return said


@given(parsers.parse('my company\'s department is called "{name}"'))
def _my_companys_department_is_called(ctx, skin, name):
    """A room naming one department, the way a shop floor names one: with a number in it."""
    skin_harness.seed_room(skin.ROOMS, ctx["room"], name)
    ctx["department"] = name


@when("I open the BIA for it and reach the stage 1 card")
def _i_open_the_bia_and_reach_the_stage_1_card(ctx, skin):
    """Ticket 164: re-aimed from the demo skin's process button to the walk itself. The phone app
    draws no process buttons and no stage card through `render` (ticket 162, row 33); the dead
    screen was `nemo.walk.open_bia` refusing the card it drew, so that is what is opened here."""
    ctx["offered"] = processes(skin.ROOMS / ctx["room"])
    assert list(ctx["offered"]) == [ctx["department"]], "the room offered something else"
    ctx["pressed"] = open_bia(skin.ROOMS / ctx["room"], ctx["department"])


@then("the card is on my screen")
def _the_card_is_on_my_screen(ctx):
    """What a dead screen is: the BIA was opened and no card came back to show."""
    assert ctx["pressed"].heading == HEADING, ctx["pressed"].screen
    assert ctx["department"] in ctx["pressed"].screen


def _refused_without_the_names(card):
    """What this card would be refused for if the room's own names did not ride with it.

    The exemption is the difference between the two calls, so the card is asserted clean with the
    names first: what comes back is the whole of what the exemption carried, and nothing else.
    """
    assert untraceable(card.screen, card.record, card.activities) == []
    return set(untraceable(card.screen, card.record))


def _the_name_carried_the_whole_refusal(ctx):
    """The exemption did all of the work and none of the card's own prose was let through: every
    string this card would otherwise be refused for is a word of the name itself."""
    assert ctx["untraced"] == []
    card = ctx["card"]
    without_the_name = set(untraceable(card.screen, card.record))
    assert without_the_name and without_the_name <= set(card.activities[0].lower().split()), (
        f"something other than the name's own words was on the card: {without_the_name}")


@then(parsers.parse('nothing was refused over the "{digit}" in the name of my own department'))
def _nothing_was_refused_over_the_digit(ctx, skin, digit):
    card = open_bia(skin.ROOMS / ctx["room"] / "", ctx["department"])
    assert _refused_without_the_names(card) == {digit}


@given(parsers.parse('a stage 1 card for "{name}" whose record holds nothing at all yet'))
def _a_stage_one_card_for(ctx, name):
    folder = ctx["tmp"] / ctx["room"]
    (folder / INTERVIEWS).mkdir(parents=True)
    (folder / INTERVIEWS / "26_08_01_interview.md").write_text(
        f"---\ndepartment: {name}\n---\n\n# {name} interview\n", encoding="utf-8")
    ctx["card"] = open_bia(folder, name)
    assert ctx["card"].record == {}, "this room has walked something already"


@when("the card is checked against that record")
def _the_card_is_checked_against_that_record(ctx):
    card = ctx["card"]
    ctx["untraced"] = untraceable(card.screen, card.record, card.activities)


@then("it is not refused, because the only digit on it sits inside the name")
def _not_refused_the_only_digit_is_in_the_name(ctx):
    _the_name_carried_the_whole_refusal(ctx)


@given("ticket 09 says every figure on a card is a string the record holds, with no exemptions")
def _ticket_09_states_the_rule(ctx):
    """How ticket 09 read before this story: the rule, stated flat. The scenario closes that."""
    ctx["ticket"] = TICKET_09.read_text(encoding="utf-8")
    _rule_statements(ctx["ticket"])


@when("a reader looks for the exemptions the shipped code actually makes")
def _a_reader_looks_for_the_exemptions(ctx):
    """The code's own words are the measure — the ticket is being checked against them."""
    ctx["code"] = (REPO / "src" / "nemo" / "card.py").read_text(encoding="utf-8")
    for exemption in EXEMPTIONS:
        assert exemption in norm(ctx["code"]), f"the code no longer names {exemption!r}"


@then(parsers.parse("ticket 09's own text names them — {which}"))
def _ticket_09_names_the_exemptions(ctx, which):
    assert "verbatim preview" in which and "a name the room supplies" in which
    for exemption in EXEMPTIONS:
        assert exemption in norm(ctx["ticket"]), f"ticket 09 does not name {exemption!r}"


@then("it does so where the rule is stated, not as a footnote somewhere else")
def _where_the_rule_is_stated(ctx):
    for block in _rule_statements(ctx["ticket"]):
        for exemption in EXEMPTIONS:
            assert exemption in block, f"the rule is stated here without {exemption!r}:\n{block}"


# ══════════ 46: the call sites move to the door ═════════════════════════════════════════════════
#
# Nothing below runs a test suite. This file is collected by `pytest -q`, which the coder, cleaner
# and hardener gates each run, the last of them once per mutant — so every step here reads the tree
# with `pathlib` and `in` and costs milliseconds. What `tests/ui` and `tests/isolation` cost to
# *run* (31 minutes, and a second interpreter) is proven in the qa procedure instead.

#: The files the sweep's checklist names, each with the number of tests it held before the
#: migration and the number of skip/xfail markers on them. Written as literals per file, counted on
#: this branch at `f5f6da1`: a step that read these back out of git would be a harness for a number
#: that changes once. 12 + 11 + 11 stage-4, 10 stage-5, 12 + 15 + 16 stage-3, skeleton and
#: transcript, and 7 isolation — 94 tests. `conftest.py` holds none of its own and is on the list
#: because it is the danger surface, not because it is a test module.
#:
#: Stage 5 joined the list after ticket 18 merged on 2026-09-15, which is why the story says twenty
#: sites and the sweep found twenty-six.
#:
#: Five since 165 slice 4 retired the stage-3, stage-5, transcript and skeleton files (git holds
#: them). Two since 165's last slice retired the stage-4 trio (last held at 602cc648).
CHECKLIST = {
    "tests/isolation/conftest.py": (0, 0),
    "tests/isolation/test_room_isolation.py": (7, 1),
}

#: How a file names the one door: on its own import line, or through the module. A file that
#: answers a card spells one of these and a file that does not spells none of them.
DOOR = ("    answer,\n", "import answer", "walk.answer")

#: `from nemo.x import a, b` and its parenthesised form, which is how a module in `tests/` reaches
#: the product. A name in one of these that the product has not got is exactly the ImportError that
#: keeps a module out of the collection.
_IMPORTS = re.compile(r"^from (nemo(?:\.\w+)*) import (\([^)]*\)|[^\n(]+)$", re.MULTILINE)

#: A test function, at the left margin, sync or async.
_A_TEST = re.compile(r"^(?:async )?def (test_\w+)", re.MULTILINE)

#: A test the collection would keep but never judge.
_NOT_JUDGED = re.compile(r"mark\.(?:skip|skipif|xfail)")


def _test_modules():
    """Every module under `tests/`, by name, in the order a reader would walk them."""
    return sorted(str(path.relative_to(REPO)) for path in (REPO / "tests").rglob("*.py")
                  if "__pycache__" not in path.parts)


def _retired(text):
    """The per-stage press names this file still spells, if any."""
    return [name for name in PRESS_FUNCTIONS if name in text]


def _unresolved(text):
    """Every name this module imports from the product that the product has not got.

    Read rather than imported as a module: importing a `tests/ui` module pulls in its whole
    procedure harness, and what makes a module un-collectable is only ever a name on one of these
    lines. A submodule counts as present if it imports.
    """
    missing = []
    for module, imported in _IMPORTS.findall(text):
        product = importlib.import_module(module)
        for name in imported.strip("()").split(","):
            name = name.split(" as ")[0].strip()
            if not name or hasattr(product, name):
                continue
            try:
                importlib.import_module(f"{module}.{name}")
            except ImportError:
                missing.append(f"{module}.{name}")
    return missing


@given("the files the sweep's checklist names")
def _the_files_the_checklist_names(ctx):
    ctx["checklist"] = {name: (REPO / name).read_text(encoding="utf-8") for name in CHECKLIST}
    assert len(ctx["checklist"]) == 2, "the checklist is not two files any more"


# ------------------------------------------------- the tree loads


@given("every test module in the tree, including the ones no gate collects")
def _every_test_module_in_the_tree(ctx):
    """Every `*.py` under `tests/`, and the reason this scenario exists at all: `testpaths` does
    not name `tests`, so **no gate in this line collects `tests/`**. A module there that does not
    import is invisible to the coder, the cleaner and the hardener alike, and reaches a human as
    one line at the end of a 31-minute browser run.

    Named by no module on purpose. Walk 2's version named the stage-5 file, `main` was merged again
    and the module that did not load was the scan slice's instead; the next merge will pick a
    third. Ask the tree.
    """
    testpaths = re.search(r"^testpaths = \[(.*)\]$",
                          (REPO / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    assert testpaths is not None, "pyproject names no testpaths, so nothing here reads what it says"
    assert "tests" not in re.findall(r'"([^"]+)"', testpaths.group(1)), (
        f"a gate collects `tests` now, so this scenario is reading around something: {testpaths[1]}")
    ctx["tree"] = _test_modules()
    missing = sorted(set(CHECKLIST) - set(ctx["tree"]))
    assert missing == [], f"the checklist names files the tree has not got: {missing}"


@when("the whole tree is collected")
def _the_whole_tree_is_collected(ctx):
    """Collected by reading, not by a second pytest: `testpaths` does not name `tests`, so no gate
    imports `tests` at all, and a subprocess here would cost the hardener a second interpreter per
    mutant. What keeps a module out of the collection is a name on one of its
    product import lines, and that is a thing to read.
    """
    ctx["modules"] = {str(path.relative_to(REPO)): path.read_text(encoding="utf-8")
                      for path in sorted((REPO / "tests").rglob("*.py"))
                      if "__pycache__" not in path.parts}
    ctx["collection_errors"] = {name: missing for name, text in ctx["modules"].items()
                                if (missing := _unresolved(text))}


@then("no module is reported as a collection error")
def _no_module_is_a_collection_error(ctx):
    # A named reach rather than a floor (`> 10` until 165's last slice emptied tests/ui, the
    # same ruling 20_nemo_check gave the controls read): the read must reach every file the
    # checklist names, whichever others leave.
    unread = sorted(set(CHECKLIST) - set(ctx["modules"]))
    assert unread == [], f"this read missed {unread}, so it proves nothing about them"
    assert ctx["collection_errors"] == {}, (
        f"these modules do not load, so nothing in them is judged: {ctx['collection_errors']}")


@then("every module the checklist names is collected, with its tests in it")
def _every_checklist_module_is_collected(ctx):
    """Named on its own because "no collection error" is satisfied by a module that is no longer
    there at all: the way this ticket goes wrong is a file emptied or deleted to get the tree
    loading, so the tests are read back out of every module the migration touched."""
    for name, (held, _) in CHECKLIST.items():
        assert name in ctx["modules"], f"{name} is not in the tree at all"
        found = _A_TEST.findall(ctx["modules"][name])
        assert len(found) == held, f"{name} collects {len(found)} tests, not {held}"


# ------------------------------------------------- the seam: the door meeting stage 5


#: A manager's own words, and neither of the labels on the card: the door reads them for a caveat,
#: finds none, and they accept the record exactly as the label typed back does (ADR-0013). That is
#: what "in my own words" means here, so the scenario is not quietly a scenario about a label.
MY_OWN_WORDS = "Yes, that's our record — go ahead."


@given("a walk standing at stage 4 with its record refereed")
def _a_walk_standing_at_stage_4_refereed(ctx):
    """The one step in this file that walks rather than reads. It costs a few hundred milliseconds
    and no test suite: the stages are answered in turn, through the same door, exactly as every
    other feature in this tree drives them."""
    _my_companys_room_is(ctx, "demo-1")
    _i_have_agreed_the_scope_and_bound_the_interview(ctx)
    _record(ctx)
    assert ctx["card"].stage == STAGE_4, f"this walk stands at stage {ctx['card'].stage}"
    assert ENDORSED in ctx["card"].buttons, "there is nothing here to accept a record with"


@when("I answer that card in my own words, through the door")
def _i_answer_that_card_in_my_own_words(ctx):
    """Once into this room, and once into a byte-identical copy of it where the second movement is
    held back — the same card, the same words, and the stop ADR-0010 calls ordinary rather than a
    crash. Both go through `answer`; nothing here reaches for a movement by name.

    Whatever the walk raises is caught and carried rather than allowed to fail this step, because
    the last Then of this scenario is that a manager is handed a card and never a traceback. A step
    that died here would red on the same fault under a worse name.
    """
    stopped_folder = ctx["tmp"] / "stopped-between-the-two"
    shutil.copytree(ctx["room_folder"], stopped_folder)
    walked, standing = ctx["room_folder"], ctx["card"]
    ctx["raised"], ctx["handed"], ctx["follows"] = None, (), ()
    try:
        ctx["handed"] = _said(ctx, MY_OWN_WORDS)
        ctx["follows"] = onward(ctx["room_folder"], ctx["handed"][0])
    except Exception as raised:
        ctx["raised"] = raised
    ctx["room_folder"], ctx["card"] = stopped_folder, standing
    ctx["stopped_card"] = _only_the_record(ctx, MY_OWN_WORDS)
    ctx["stopped_folder"], ctx["room_folder"], ctx["card"] = stopped_folder, walked, standing


@then("the record I just accepted is the one in my room, and its receipt binds it")
def _the_record_i_accepted_is_in_my_room_and_bound(ctx):
    assert ctx["raised"] is None, f"answering the stage 4 card raised {ctx['raised']!r}"
    assert _landed(ctx)["run_id"] == _saved(ctx)["run_id"], (
        "the record in the room is not the one this run just wrote")
    _receipt_binds(ctx)


@then("if the walk stopped between the two, the card I get says my BIA is saved and not finished")
def _the_stopped_card_says_saved_and_not_finished(ctx):
    stopped = read_record(ctx["stopped_folder"], run_file(ctx["process"])) or {}
    assert not stopped.get(RECEIPT), "this walk drew its picture after all, so it never stopped"
    assert where_it_stands(stopped) == SAVED_NOT_FINISHED
    assert SAVED_NOT_FINISHED in ctx["stopped_card"].body, (
        f"the card a stopped walk hands back says {ctx['stopped_card'].body!r}")


@then("nothing that happens on my screen is an exception out of the walk")
def _nothing_on_my_screen_is_an_exception(ctx):
    assert ctx["raised"] is None, f"the walk raised {type(ctx['raised']).__name__}: {ctx['raised']}"
    assert ctx["handed"], "the door handed a manager nothing at all"
    for card in (*ctx["handed"], *ctx["follows"], ctx["stopped_card"]):
        assert card.body, f"a card with nothing on it is not a screen: {card}"
        assert NotDrawnYet.__name__ not in card.body, f"the card names an exception: {card.body}"
    reached = [card.stage for card in (*ctx["handed"], *ctx["follows"])]
    assert STAGE_5 in reached, (
        f"nothing after this answer is stage 5, which is where {NotDrawnYet.__name__} was raised; "
        f"the stages handed back are {reached}")


# ═══════════ 47 — a room-supplied name is exempt for its whole span ══════════════════════════════
# The dead screen and the reading of the repo, exactly as ticket 32 above: what is *still* refused
# is checked a card and a record at a time in `features/conftest.py`, beside ticket 09's own steps.

#: What each docstring must say now the exemption is the whole name and not a digit inside it, and
#: the scoping sentence that must survive the widening unchanged.
NAME_EXEMPTION = "a name the room supplies"
WHOLE_SPAN = "never a figure and never a vague word"
SCOPING = "never added to what the record holds"


@then(parsers.parse('nothing was refused over the word "{word}" in the name of my own department'))
def _nothing_was_refused_over_the_word(ctx, skin, word):
    card = open_bia(skin.ROOMS / ctx["room"] / "", ctx["department"])
    assert _refused_without_the_names(card) == {word}


@then("it is not refused, because the only vague word on it sits inside the name")
def _not_refused_the_only_vague_word_is_in_the_name(ctx):
    _the_name_carried_the_whole_refusal(ctx)


@given("`nemo.card`'s module docstring and `untraceable`'s docstring state the name exemption")
def _both_docstrings_state_the_name_exemption(ctx):
    """The two places a reader meets the rule: the module's own account and the check's."""
    ctx["docstrings"] = {"nemo.card": nemo.card.__doc__, "untraceable": untraceable.__doc__}
    assert NAME_EXEMPTION in ctx["docstrings"]["nemo.card"], "the module no longer names it"
    assert "`names`" in ctx["docstrings"]["untraceable"], "`untraceable` no longer states it"


@when("a reader looks for what a name the room supplies is exempt from")
def _a_reader_looks_for_what_a_name_is_exempt_from(ctx):
    """One line each, as a reader reads it: the sentences that say what the exemption covers."""
    ctx["exemption"] = {where: " ".join(said.split())
                        for where, said in ctx["docstrings"].items()}


@then("both say a name and not a digit, so the whole span is exempt whatever it contains")
def _both_say_a_name_and_not_a_digit(ctx):
    for where, said in ctx["exemption"].items():
        assert WHOLE_SPAN in said, f"{where} does not say the whole span is exempt: {said}"
        assert "a digit is skipped" not in said, f"{where} still states the narrower rule"


@then("the scoping rule is stated unchanged: never added to what the record holds")
def _the_scoping_rule_is_stated_unchanged(ctx):
    for where, said in ctx["exemption"].items():
        assert SCOPING in said, f"{where} no longer states the scoping rule: {said}"
        assert "inside an occurrence" in said, f"{where} no longer scopes it to the span"


# ═══════════════════════ 50 — a scan mints a room from the seed ═════════════════════════════════
#
# `features/a-scan-mints-a-room-from-the-seed.feature`. The doors are the real ones, over
# `skin_harness.py` — for ticket 22's reason: a step that called `mint_room` itself would prove
# nothing about the door fifty delegates scan. **Since ticket 186 (c) that door is the stage QR's
# `/new` (`stage_qr`) and no longer the login**: a room link opens a room that exists and makes
# none, so a scan is `/new` — it draws the code, mints its room, and answers with the link the
# phone then presents at the login (`room`), which is the other half of every scan below.
#
# **The mechanism is copy-to-staging-then-rename** (`nemo.walk.mint_room` says so where the choice
# is made). The races below are run rather than argued: fifty threads on one barrier, and what is
# on disk afterwards is the verdict.

#: The seed's own folders: `01_Organisation` through `09_Evaluation`, plus `output/` (ADR-0011).
SEED_FOLDERS = ("01_Organisation", "02_BCM-Method", "03_Dependencies", "04_Processes",
                "05_Impacts", "06_Recovery", INTERVIEWS, "08_Continuity", "09_Evaluation")

#: How many phones scan at once. ADR-0017's fifty delegates, and QA's loop.
SCANS = 50

#: What the fifty-code run has to say for itself: how many rooms it made, and how long it took.
MINTED_COUNT = "{count} rooms minted in {seconds:.2f}s"


def _scan(ctx, skin, capsys, code):
    """Scan one printed code, and keep everything that came of it.

    A scan is the QR's `/new` door (t186 (c): the one place a delegate's room comes from), and then
    the link it answers with, presented at the login exactly as the phone presents it. So both
    halves of the real arrival run here, in the order the phone runs them.

    The delegate's own sentence is kept beside the operator's journal. The door refuses in two
    voices (`nemo.door.Refused.operator`) and the skin can only put one of them in the journal,
    because the door prints the operator's and answers with a link that opens nothing. So what the
    delegate would be shown is read here by asking the same door again: admission is deterministic
    and read-only, which is why fifty broken scans are fifty identical refusals. A scan the door
    refused is not carried on to the login, because there is nothing there to open: that the link
    of a room nobody minted opens none is `a-prefix-link…`'s own scenario.
    """
    link = skin_harness.scan_the_qr(code)
    ctx["log"] = ctx.get("log", "") + capsys.readouterr().out
    ctx["identity"] = None
    ctx["refusal"] = None
    ctx["minted"] = code not in ctx["rooms_before"] and (skin.ROOMS / code).is_dir()
    if not (skin.ROOMS / code).is_dir():
        try:
            mint_room(skin.SEED, skin.ROOMS, code)
        except Refused as refusal:
            ctx["refusal"] = refusal
        return
    _present(ctx, skin, capsys, link)
    assert ctx["identity"] is not None, "the room the door minted opens to nobody"
    # A room that is open is the room every walking step already knows how to drive: `claimed` is
    # ticket 02's name for the room a manager is handed, and a minted room is exactly that.
    ctx["room"] = code
    ctx["claimed"] = ctx["room_folder"] = skin.ROOMS / code
    ctx["offered"] = processes(ctx["room_folder"])
    ctx["acts"] = ctx.get("acts", [])


def _scan_all(ctx, skin, capsys, codes):
    """Every code scanned at one moment: one thread each through the QR's door, all released off
    the same barrier.

    The barrier is waited on **after the door's `taken` check**, inside the door: every scan holds
    its code, and has asked whether a room holds it, before any of them has a room (ticket 231), so
    what happens at one moment is the minting — which is what this story's race is about
    (`walk.mint_room`'s copy-to-staging-then-rename). Each scan then presents the link its own door
    answered with, as the phone does.
    """
    ready = threading.Barrier(len(codes))

    def scanned(code):
        return skin_harness.scan_the_qr(code, drawing=ready.wait)

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(len(codes)) as pool:
        links = list(pool.map(scanned, codes))
    ctx["took"] = time.monotonic() - started
    ctx["identities"] = [skin_harness.scan(link) for link in links]
    ctx["log"] = ctx.get("log", "") + capsys.readouterr().out


def _whole_seed(ctx, skin, code):
    """The room this code names, holding the seed file for file — the "not partial" measurement."""
    folder = skin.ROOMS / code
    assert _tree(folder) == ctx["seed_tree"], f"{code} is not the seed, file for file"
    return folder


@given("the rooms folder is there")
def _the_rooms_folder_is_there(ctx, skin):
    """The mount that is present, which is the ordinary morning. Minting puts rooms inside it."""
    ctx["rooms"] = skin.ROOMS
    ctx["rooms_before"] = skin_harness.room_names(skin.ROOMS)


@given(parsers.parse('the seed holds "{first}" through "{last}" and "output/"'))
def _the_seed_holds(ctx, skin, first, last):
    """The marschkamp files a room is minted from: nine folders, `output/`, and a BIA in progress.

    `output/` is seeded **deliberately** (ADR-0011): a minted room ships a BIA in progress, and
    emptiness was never the test — a room that holds nothing has to interrogate the manager about
    his own company. Terminal-eligibility is the test, and nothing here is a thing a signature
    could close over.
    """
    seed = skin.SEED
    for folder in SEED_FOLDERS:
        (seed / folder).mkdir(parents=True)
    (seed / "output").mkdir()
    for index, department in enumerate(("Incident and problem management", "Access management")):
        (seed / INTERVIEWS / f"26_08_0{index}_interview.md").write_text(
            f"---\ndepartment: {department}\n---\n\n# {department} interview\n", encoding="utf-8")
    (seed / REGISTER).write_text(json.dumps(
        {"KA-01": {"asset_id": "KA-01", "department": "Incident and problem management",
                   "consumers": []}}),
        encoding="utf-8")
    (seed / METHOD).write_text(json.dumps(METHOD_FILE), encoding="utf-8")
    scope = open_bia(seed, "Access management")
    answer(seed, scope.activities[0], AGREE, scope.revision)
    assert {first, last} <= set(SEED_FOLDERS), f"the seed holds no {first} and no {last}"
    ctx["seed"], ctx["seed_tree"] = seed, _tree(seed)


@given(parsers.parse('the rooms folder holds no room called "{code}"'))
def _the_rooms_folder_holds_no_room_called(ctx, skin, code):
    assert code not in skin_harness.room_names(skin.ROOMS)


@given("the rooms folder holds no rooms")
def _the_rooms_folder_holds_no_rooms(ctx, skin):
    assert skin_harness.room_names(skin.ROOMS) == []


@given(parsers.parse('a room "{code}" that has been there all along'))
def _a_room_that_has_been_there_all_along(ctx, skin, code):
    """A room nobody minted this morning. ADR-0003 holds over it before and after the mint."""
    skin_harness.seed_room(skin.ROOMS, code, "Incident and problem management")
    ctx["rooms_before"] = skin_harness.room_names(skin.ROOMS)


@given(parsers.parse('a seed whose Stage 2 capture is missing the sections the walk\'s gates '
                     'require'))
def _a_seed_whose_capture_is_broken(ctx, skin):
    """The capture with its front matter gone: it names no department, so no stage can bind it."""
    sorted((skin.SEED / INTERVIEWS).glob("*.md"))[0].write_text(
        "# Incident and problem management interview\n", encoding="utf-8")


@given(parsers.parse('I scanned the code for "{code}"'))
@when(parsers.parse('I scan the code for "{code}"'))
def _i_scan_the_code_for(ctx, skin, capsys, code):
    _scan(ctx, skin, capsys, code)


@given(parsers.parse('another delegate scanned the code for "{code}"'))
def _another_delegate_scanned_the_code_for(ctx, skin, capsys, code):
    """Somebody else's scan, at the same door mine came through, which must leave mine and the seed
    exactly as they were. Their room is minted, so what my answer must not reach is a real room."""
    mine = {key: ctx.get(key) for key in ("room", "claimed", "room_folder", "offered", "identity")}
    _scan(ctx, skin, capsys, code)
    assert (skin.ROOMS / code).is_dir(), "the other delegate's scan made them no room"
    ctx.update(mine)


@given(parsers.parse('I scanned the code for "{code}" and agreed the scope for "{process}"'))
def _i_scanned_and_agreed_the_scope(ctx, skin, capsys, code, process):
    _scan(ctx, skin, capsys, code)
    _press_process(ctx, process)
    _press_button(ctx, AGREE)
    ctx["answered"] = _saved(ctx, process)
    ctx["my_files"] = _tree(ctx["room_folder"])


@when(parsers.parse('I scan the code for "{code}" and open the BIA for "{process}"'))
def _i_scan_and_open_the_bia_for(ctx, skin, capsys, code, process):
    _scan(ctx, skin, capsys, code)
    _press_process(ctx, process)


@when(parsers.parse('I scan the code for "{code}" and request a file belonging to "{other}"'))
def _i_scan_and_request_another_rooms_file(ctx, skin, capsys, code, other):
    _scan(ctx, skin, capsys, code)
    ctx["other"] = other
    _attempt(ctx, other)


@when("I scan the same code again")
def _i_scan_the_same_code_again(ctx, skin, capsys):
    """The same code, which is its link: the QR's door never hands one code out twice (`fresh_code`
    draws a code no room holds), so a second arrival at the code I already have is the link I hold
    presented again — the delegate who reloads. Since t186 (c) that login mints nothing, which is
    what "no second room was made" now reads off."""
    ctx["rooms_before"] = skin_harness.room_names(skin.ROOMS)
    _present(ctx, skin, capsys, f"/demo/r/{ctx['room']}")


@when(parsers.parse('the code for "{code}" is scanned twice at the same moment'))
def _the_code_is_scanned_twice_at_the_same_moment(ctx, skin, capsys, code):
    _scan_all(ctx, skin, capsys, [code, code])


@when("fifty different codes are scanned within a minute of each other")
def _fifty_different_codes_are_scanned(ctx, skin, capsys):
    ctx["codes"] = [f"scan-{number:02d}" for number in range(1, SCANS + 1)]
    _scan_all(ctx, skin, capsys, ctx["codes"])
    ctx["report"] = MINTED_COUNT.format(
        count=len(skin_harness.room_names(skin.ROOMS)), seconds=ctx["took"])
    print(ctx["report"])
    ctx["log"] += capsys.readouterr().out


@when(parsers.parse('I agree the scope for "{process}"'))
def _i_agree_the_scope_for(ctx, process):
    _press_process(ctx, process)
    _press_button(ctx, AGREE)


@then(parsers.parse('I am in room "{code}"'))
def _i_am_in_room(ctx, skin, code):
    assert ctx["identity"] is not None, "the scan was refused"
    assert ctx["identity"].identifier == code
    assert (skin.ROOMS / code).is_dir()


@then(parsers.parse('it holds every folder the seed holds, "{first}" through "{last}"'))
def _it_holds_every_folder_the_seed_holds_named(ctx, skin, first, last):
    held = sorted(path.name for path in ctx["room_folder"].iterdir() if path.is_dir())
    assert held == sorted(SEED_FOLDERS + ("output",))
    assert held[0] == first and held[-2] == last, f"{first} through {last} is not what is there"


@then("it holds every folder the seed holds")
def _it_holds_every_folder_the_seed_holds(ctx, skin):
    assert sorted(path.name for path in (skin.ROOMS / ctx["room"]).iterdir()) == sorted(
        path.name for path in ctx["seed"].iterdir())


@then("what is in them is what is in the seed, file for file")
def _what_is_in_them_is_what_is_in_the_seed(ctx, skin):
    _whole_seed(ctx, skin, ctx["room"])


@then(parsers.parse('the room holds "{folder}"'))
def _the_room_holds(ctx, folder):
    """**ADR-0011**: `output/` is in a minted room on purpose. Deleting that pre-loaded record to
    make the room look safer breaks the product; the defence against closing over work nobody did
    is ticket 15's run binding on `run_id`, not an empty room."""
    assert (ctx["room_folder"] / folder.rstrip("/")).is_dir()


@then("it holds nothing a signature could close over")
def _it_holds_nothing_a_signature_could_close_over(ctx):
    """Terminal-eligibility, which is the test emptiness never was: there is a BIA in progress in
    there, and no finished record for a walk that did no work to sign (ADR-0011)."""
    assert not list(ctx["room_folder"].rglob(RECORD_NAME))


@then(parsers.parse('I read a Stage 1 card for "{process}"'))
def _i_read_a_stage_1_card_for(ctx, process):
    assert ctx["card"].stage == STAGE
    assert ctx["card"].heading == HEADING
    assert ctx["card"].activities == (process,)


@then("nothing was set up between my scan and that card")
def _nothing_was_set_up_between_my_scan_and_that_card(ctx):
    """The scan made the room and the walk did the rest: nothing was put in it by hand."""
    assert ctx["minted"] is True, "the room was already there, so somebody set it up first"
    assert ctx.get("typed", "") == ""
    added = set(_tree(ctx["room_folder"])) - set(ctx["seed_tree"])
    assert all(path.startswith("output/") for path in added), f"{sorted(added)} was put there"


@then("I am in the same room, with the same files")
def _i_am_in_the_same_room_with_the_same_files(ctx, skin):
    assert ctx["identity"].identifier == ctx["room"]
    assert _tree(skin.ROOMS / ctx["room"]) == ctx["my_files"], "the seed was copied over my work"


@then(parsers.parse('my agreed scope for "{process}" is still there'))
def _my_agreed_scope_is_still_there(ctx, process):
    assert _saved(ctx, process) == ctx["answered"]


# "I am not asked to agree it a second time" is `_i_am_not_asked_to_agree_it_again`, written for
# the skeleton's reopened page and shared with the second scan here: one sentence, one definition.


@then("no second room was made")
def _no_second_room_was_made(ctx, skin):
    assert skin_harness.room_names(skin.ROOMS) == ctx["rooms_before"]


@then(parsers.parse('exactly one room called "{code}" exists'))
def _exactly_one_room_called_exists(ctx, skin, code):
    """Fifty copies, one winner, and no staging folder left: the listing is the whole proof."""
    assert skin_harness.room_names(skin.ROOMS) == [code]
    ctx["room"] = code
    ctx["room_folder"] = skin.ROOMS / code


@then("neither scan was refused")
def _neither_scan_was_refused(ctx):
    assert [identity for identity in ctx["identities"] if identity is None] == []


@then("there are exactly fifty rooms")
def _there_are_exactly_fifty_rooms(ctx, skin):
    assert skin_harness.room_names(skin.ROOMS) == sorted(ctx["codes"])
    assert len(ctx["codes"]) == SCANS


@then("every one of them holds the whole seed")
def _every_one_of_them_holds_the_whole_seed(ctx, skin):
    for code in ctx["codes"]:
        _whole_seed(ctx, skin, code)


@then("not one of them is partial")
def _not_one_of_them_is_partial(ctx, skin):
    partial = [code for code in ctx["codes"] if _tree(skin.ROOMS / code) != ctx["seed_tree"]]
    assert partial == [], f"{partial} were handed over half-copied"


@then("the run says how many rooms it made and how long it took")
def _the_run_says_how_many_rooms_and_how_long(ctx):
    assert re.fullmatch(rf"{SCANS} rooms minted in \d+\.\d\ds", ctx["report"]), ctx["report"]
    assert ctx["report"] in ctx["log"], "the count was never said where anybody reads it"


@then("my decision is on file in my own room")
def _my_decision_is_on_file_in_my_own_room(ctx, skin):
    assert (skin.ROOMS / ctx["room"] / run_file(ctx["process"])).is_file()


@then("the seed is exactly as it was")
def _the_seed_is_exactly_as_it_was(ctx):
    assert _tree(ctx["seed"]) == ctx["seed_tree"], "a delegate's answer landed in the seed"


@then("I am refused with 401")
def _i_am_refused_with_401(ctx):
    assert ctx["refusal"] is not None, "another room's file was handed over"
    assert ctx["refusal"].status == UNAUTHORISED


@then(parsers.parse('a delegate in "{other}" requesting a file of mine is refused the same way'))
def _a_delegate_in_the_other_room_is_refused_the_same_way(ctx, other):
    with pytest.raises(Refused) as refusal:
        authorise(other, ctx["room"])
    assert refusal.value.status == UNAUTHORISED


@then("what I read is one sentence I can understand")
def _what_i_read_is_one_sentence_i_can_understand(ctx):
    """What the delegate is told: that nobody could be seated, and who can put it right. They did
    nothing wrong and can do nothing about it, so it names no fault (`docs/voice.md` §3.1)."""
    read = str(ctx["refusal"])
    assert read.count(".") == 1 and read.endswith("."), f"{read!r} is not one sentence"
    assert "room isn't ready" in read and "they can put it right" in read


@then("it carries no file path, no field name and no stack trace")
def _it_carries_no_path_no_field_name_and_no_stack_trace(ctx):
    read = str(ctx["refusal"])
    for machine in ("/", "department", "Traceback", "Refused", "interview", ".md"):
        assert machine not in read, f"the delegate reads {machine!r}: {read}"
    assert ctx["refusal"].operator != read, "the operator was told no more than the delegate"


@then(parsers.parse('no room called "{code}" was made'))
def _no_room_called_was_made(ctx, skin, code):
    assert code not in skin_harness.room_names(skin.ROOMS)


@then("the rooms folder was not created")
def _the_rooms_folder_was_not_created(ctx, skin):
    """The worst outcome in the ticket: fifty delegates each handed a brand-new room, having lost
    the one they had worked in all morning. An absent mount is an absent mount."""
    assert not skin.ROOMS.exists()


@then("the operator's log says the rooms folder is not there")
def _the_log_says_the_rooms_folder_is_not_there(ctx):
    _one_line(ctx, "is not there")


@then("the operator's log says the link carries no room code")
def _the_log_says_the_link_carries_no_room_code(ctx):
    _one_line(ctx, "carries no room code")


@then("nothing was created outside the rooms folder")
def _nothing_was_created_outside_the_rooms_folder(ctx, skin):
    assert _tree(skin.ROOMS.parent) == ctx["outside"]


@then("the rooms folder still holds no rooms")
def _the_rooms_folder_still_holds_no_rooms(ctx, skin):
    assert skin_harness.room_names(skin.ROOMS) == []
# ═══════════ 48 — `tests/ui` costs half an hour, and one file is most of it ══════════════════════
# A ratchet, and that is the whole of what a scenario here may be. This ticket makes a suite
# cheaper, and the one thing it must not do is make it cheaper by asking less — so what the
# meta-suite demanded at the commit the branch was cut from is pinned below, and every scenario
# measures the file as it stands now against it.
#
# **Pinned as data, not read back out of git**, which is the one decision in this section worth
# arguing. `test_steps_29_and_30_the_gate_notices_a_broken_skin` runs `./gate.sh cleaner` inside a
# tar copy of the tracked tree, and that copy has no `.git` anywhere above it; `features` is in
# `testpaths`, so these scenarios are collected there too. A `git show` would turn that gate red for
# want of a repository, and the test that reads the gate's colour would call the tree broken.
#
# The numbers were taken at `0de2a0f`, the cut point, with `ast.parse` over the file and
# `git diff 0de2a0f -- tests/ gate.sh demo_skin/` empty — so the working tree was the baseline when
# they were written down, and a later `git show` will agree with them.
#
# Since 165's last slice retired the meta-suite (last held at 602cc648), what is left here is the
# hardener's exemption count and a check that `gate.sh acceptance` counts skips and xfails (585).

UI = REPO / "tests" / "gate"  # the ratchet followed branch.py here from tests/ui (165's last slice)
GATE_SH = REPO / "gate.sh"

#: The skip and xfail ratchets `WAS_DUCKED` and `WAS_XFAILED` that stood here counted the text of
#: every `tests/gate` file (1 and 0 when retired); since 585 `gate.sh` holds the ceilings,
#: `WAS_SKIPPED` and `WAS_XFAILED`, and its acceptance run counts them from pytest's own report.

#: `gate.sh`'s lint set at the cut. The ticket puts it out of scope, so it is compared literally.
#: Without `demo_skin` since 166 archived it (the owner's yes, 2026-09-26T19:37:22Z); with `skin`
#: since 128's last slice (the owner's yes, 7c55da87, 2026-09-22: "Yes, both").
WAS_LINTED = 'LINT="$SRC skin tests"'


def _ui_module(path, name):
    """One file under `tests/ui` as a module, so a scenario reads its own tables rather than a
    regex of them.

    Under a name of its own so nothing collides with pytest's copy of the same file in a `tests/ui`
    run. Its own directory goes on the path for the length of the load: under `pytest tests/ui` a
    file's siblings are importable because pytest puts that directory there, and these files have
    siblings — ticket 34 gave the meta-suite `import probes`, ticket 53 gave the guarded files
    `import branch`. Loading one from out here by path does not, so without this the module raises
    `ModuleNotFoundError` and a scenario about what the file holds reds on an import.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses resolve their annotations through here
    beside = str(path.parent)
    sys.path.insert(0, beside)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(beside)
    return module


@then("its acceptance run counts the skips and the xfails from pytest's own report")
def _acceptance_counts_from_the_report(ctx):
    """The acceptance case copies its stdout from its first pytest run and counts at its end, before
    its verdict; tests/gate/test_t585_skips_counted_from_the_report.py runs it on planted tests."""
    case = ctx["gate"].split("\n  acceptance)\n", 1)[1].split("\n    ;;\n", 1)[0]
    lines = [line.strip() for line in case.splitlines()]
    first = next(i for i, line in enumerate(lines) if "-m pytest" in line)
    assert lines[first - 1] == "report_start", "the report is not copied from the first pytest run"
    verdict = next(i for i, line in enumerate(lines) if line.startswith('echo "### acceptance'))
    assert lines[verdict - 1] == "report_ducked || fail=1", "the count does not decide the verdict"
    for ceiling in ("WAS_SKIPPED", "WAS_XFAILED"):
        assert re.search(rf"^{ceiling}=\d+$", ctx["gate"], re.M), f"gate.sh sets no {ceiling}"


@then("`./gate.sh hardener`'s exemption count is still 1 of a ceiling of 1")
def _the_exemption_count_is_still_one(ctx):
    assert "\nEXEMPTIONS=1\n" in GATE_SH.read_text(encoding="utf-8"), "the ceiling moved"
    pragmas = [path for path in (REPO / "src").rglob("*.py")
               if "pragma: no mutate" in path.read_text(encoding="utf-8")
               and not path.name.startswith("test_")]
    assert len(pragmas) == 1, f"{len(pragmas)} exempted files under src/, not one: {pragmas}"


@given("`gate.sh`")
def _gate_sh(ctx):
    ctx["gate"] = GATE_SH.read_text(encoding="utf-8")


@then("its LINT set is unchanged")
def _its_lint_set_is_unchanged(ctx):
    assert WAS_LINTED in ctx["gate"], "the LINT set moved, and this ticket does not touch it"


# ════════ 26 — the referee reports findings as data; the walk writes the prose ═══════════════════
#
# `features/the-referee-reports-data-and-the-walk-writes-the-prose.feature`. Two halves.
#
# The card a manager could reach this afternoon read *activity Slaughter:
# impact_grid['legal-regulatory'] missing horizon(s): ['72 h']*, because the refused body was the
# referee's own rejections joined end to end and every one of those is an f-string written for a
# developer. The referee hands back parts now — the activity, the category, the bands — and
# `nemo.walk` writes the sentence, where every other string on a card is written. So the steps
# below read the **refused** card, which is the card the voice scenario never covered.
#
# The second half is the clause that could not be false: `_review_boundary` recorded itself as
# having run before it looked, over keys `nemo.bia` does not write. A check claims itself where it
# had something of the manager's to judge, and on today's record shape that clause is gone.

#: The same interview, with one of the method's time bands left out of the scored category.
BAND_LEFT_UNSCORED = REFEREED_TRANSCRIPT.replace("24 h 4, 72 h 5, 168 h 5", "24 h 4, 168 h 5")

#: The same interview again, with a recovery target outside the MTPD the grid derives (24 h).
TARGET_OUTSIDE_THE_MTPD = REFEREED_TRANSCRIPT.replace("RTO: 8 h", "RTO: 72 h")

#: What a manager could read for each part a refusal is written from. The parts are the referee's;
#: a scenario that puts every kind of refusal through the card's words needs one reading of each.
A_PART = {
    "activity": "Incident and problem management", "lens": "legal", "horizon": "72 h",
    "score": "9", "horizons": ("24 h", "72 h"), "lenses": ("operational", "legal"),
    "missing": ("approved_by", "review_date"), "date": "2026-01-31",
    "quote": "we never said that", "target": "72 h", "mtpd": "24 h", "rpo": "one shift",
    "allowed": ("<1 h", "<24 h"), "what": "a continuity plan", "item": "buy a generator",
    "issue": "who owns Cisco Call Manager", "who": "the assistant",
}

#: The developer's line every stand-in rejection below carries, so that "passed through untouched"
#: is read off the card rather than argued about.
A_DEVELOPERS_LINE = ("activity Incident and problem management: impact_grid['legal'] missing "
                     "horizon(s)")

#: What each check the referee records had to have found on the record before it could claim it.
CHECK_NEEDS = {
    referee.QUOTES_CHECK: lambda record: [
        item for activity in record[ACTIVITIES] for item in activity.get(EVIDENCE) or []],
    referee.GRID_CHECK: lambda record: [
        activity[IMPACT_GRID] for activity in record[ACTIVITIES] if activity.get(IMPACT_GRID)],
    referee.MTPD_CHECK: lambda record: [
        activity[MTPD] for activity in record[ACTIVITIES] if activity.get(MTPD)],
    referee.RTO_CHECK: lambda record: [activity[RECOVERY_TARGET] for activity in record[ACTIVITIES]
                                       if activity.get(RECOVERY_TARGET)],
    referee.RPO_CHECK: lambda record: [
        activity[RPO] for activity in record[ACTIVITIES] if activity.get(RPO)],
    referee.BOUNDARY_CHECK: lambda record: [
        record[key] for key in BEYOND_THE_BOUNDARY if record.get(key)],
}

#: The two keys `_review_boundary` reads, which `nemo.bia` does not write and never wrote.
BEYOND_THE_BOUNDARY = ("plan", "recovery_solution")

#: A continuity plan, which is the one thing that gives that check something of mine to look at.
A_CONTINUITY_PLAN = {"immediate actions": "call the plant and start the generator"}


def _not_passed(ctx):
    """What the referee will not pass on this room's draft, as the parts it found them in."""
    return check_draft(ctx["room_folder"], ctx["process"]).rejections


def _one_refusal(ctx, kind, **parts):
    """The one refusal of this kind over these parts."""
    found, = [refusal for refusal in _not_passed(ctx) if refusal.kind == kind
              and all(refusal.parts.get(name) == part for name, part in parts.items())]
    return found


#: The category the interview scores. The one it leaves out is refused for the same band, so a
#: step that means the scored one says which.
SCORED_LENS = "operational"


def _the_band_refusal(ctx):
    """The refusal over the scored category's missing time band — the story's own card."""
    return _one_refusal(ctx, refusal.MISSING_HORIZONS, lens=SCORED_LENS)


def _longest_wording(says):
    """The longest stretch of a card's sentence that carries no part of the record in it."""
    return max((literal for literal, *_rest in string.Formatter().parse(says)), key=len)


def _the_wording_is_the_walks_alone():
    """No sentence a card says is written anywhere below the walk as well.

    Two scenarios lean on this from opposite ends — the card's, and the referee's — and one place
    a card string is written is the whole of what this ticket moved. `nemo.refusal` is read too:
    the vocabulary below both of them is names, and a name that grew a sentence would be the same
    defect wearing the new module.
    """
    for module in ("referee", "refusal"):
        source = (REPO / "src" / "nemo" / f"{module}.py").read_text(encoding="utf-8")
        for kind, says in REFUSAL_SAYS.items():
            assert _longest_wording(says) not in source, f"{kind} is worded at {module} too"


# ------------------------------------------------------ the refusal, in the manager's language


@given("the interview I bound leaves one of my method's time bands unscored for a category")
@given("the referee refuses a record for a category that is missing time bands")
def _the_interview_leaves_a_band_unscored(ctx):
    ctx["passing"] = _record(ctx).body
    _rewalk(ctx, BAND_LEFT_UNSCORED)
    assert _the_band_refusal(ctx), "no band was left unscored after all"


@then("I am told what is wrong with the BIA")
def _i_am_told_what_is_wrong_with_the_bia(ctx):
    assert ctx["card"].body.startswith(REFUSED.split("{")[0])
    assert ctx["card"].buttons == (), "a record the referee refuses was put up to be accepted"
    _i_read_the_card(ctx)


@then("it names the activity the way the rest of the card names it")
def _it_names_the_activity_as_the_card_does(ctx):
    named = _the_band_refusal(ctx).parts["activity"]
    assert named == ctx["process"] and named in ctx["card"].body
    assert named in ctx["passing"], "the refusal spells the activity a second way"


@then("it names the impact category the way the rest of the card names it")
def _it_names_the_impact_category_as_the_card_does(ctx):
    lens = _the_band_refusal(ctx).parts["lens"]
    assert lens in ctx["card"].body
    assert lens in ctx["passing"], "the refusal spells the category a second way"


@then("it names the time bands nobody scored, as my method names them")
def _it_names_the_time_bands_as_my_method_does(ctx):
    bands = _the_band_refusal(ctx).parts["horizons"]
    assert bands, "nothing was reported missing, so this proves nothing"
    for band in bands:
        assert band in ctx["method_file"]["time_horizons"], f"{band!r} is not my method's word"
        assert band in ctx["card"].body


@then("no bracket, quote mark or list punctuation stands around any of them")
def _no_bracket_or_quote_stands_around_them(ctx):
    """`['72 h']` is the whole of what this ticket is about: the punctuation of a data structure."""
    refusal = _the_band_refusal(ctx)
    body = ctx["card"].body
    assert not set(body) & set('[]{}"*'), f"a data structure's punctuation is on the card: {body}"
    for named in (refusal.parts["activity"], refusal.parts["lens"], *refusal.parts["horizons"]):
        for at in re.finditer(re.escape(named), body):
            around = body[max(at.start() - 1, 0):at.start()] + body[at.end():at.end() + 1]
            assert not set(around) & set('[]{}"•'), f"{named!r} stands in {around!r}"


# ------------------------------------------------------ every refusal, in the same voice


@given("every way the referee can refuse a record")
def _every_way_the_referee_can_refuse(ctx):
    """One stand-in refusal per kind, carrying parts a manager could read and one line they
    could not. The kinds are `nemo.refusal`'s list, below the referee that raises one and the walk
    that words it, and `test_referee` pins every rejection the referee raises to that list — so
    this ranges over all of them without reproducing 25 broken rooms."""
    ctx["every_refusal"] = [
        refusal.Rejection(kind, A_DEVELOPERS_LINE, **{
            part: A_PART[part] for _t, part, _s, _c in string.Formatter().parse(says) if part})
        for kind, says in REFUSAL_SAYS.items()]
    assert set(REFUSAL_SAYS) == set(refusal.KINDS), "a way of refusing has no words on the card"


@when("each of those refusals reaches the stage 4 card")
def _each_of_those_refusals_reaches_the_card(ctx):
    ctx["voiced"] = {refusal.kind: refused_says([refusal]) for refusal in ctx["every_refusal"]}


@then("not one of them puts a machine identifier in front of me")
def _not_one_puts_a_machine_identifier_in_front_of_me(ctx):
    for kind, said in ctx["voiced"].items():
        assert [word for word in BANNED_ON_A_CARD if word in said] == [], kind
        assert not set(said) & set('[]{}"_'), f"{kind}: {said}"


@then("not one of them is the referee's own words passed through untouched")
def _not_one_is_the_referees_own_words(ctx):
    """The words a manager reads exist in `nemo.walk` and nowhere else, which is what stops a
    card and a handover wording one open item two ways."""
    for kind, said in ctx["voiced"].items():
        assert A_DEVELOPERS_LINE not in said, f"{kind} printed the line it was handed"
    _the_wording_is_the_walks_alone()


# ------------------------------------------------------ a refusal asks something of a person


@given("the recovery target my interview states is not inside the MTPD the grid derives")
def _the_recovery_target_is_not_inside_the_mtpd(ctx):
    _rewalk(ctx, TARGET_OUTSIDE_THE_MTPD)
    ctx["gap"] = _one_refusal(ctx, refusal.TARGET_OUTSIDE_MTPD)


@when("that refusal reaches the stage 4 card")
def _that_refusal_reaches_the_stage_4_card(ctx):
    _record(ctx)


@then("it says which target and which MTPD, in the figures the record holds")
def _it_says_which_target_and_which_mtpd(ctx):
    activity, = ctx["card"].proposal[BIA][ACTIVITIES]
    assert ctx["gap"].parts["target"] == activity[RECOVERY_TARGET]
    assert ctx["gap"].parts["mtpd"] == activity[MTPD]
    for figure in (activity[RECOVERY_TARGET], activity[MTPD]):
        assert figure in ctx["card"].body, figure


@then("what it asks of me is something I could do by talking to a person")
def _what_it_asks_is_something_i_could_do_by_talking(ctx):
    said = ctx["card"].body
    assert "owner" in said, "it does not say who to go to"
    for instruction in ("set ", "flag", "field", "acknowledge it deliberately"):
        assert instruction not in said, f"it asks me to {instruction!r}, which is not a sentence"


# ------------------------------------------------------ one open item, worded once


@given("I accepted the record with an open item on it")
def _i_accepted_the_record_with_an_open_item(ctx):
    card = _rewalk(ctx, FALLING_TRANSCRIPT)
    ctx["open_on_the_card"] = list(card.proposal[FINDINGS])
    assert ctx["open_on_the_card"], "this record leaves nothing open, so it proves nothing"
    ctx["card_body"] = card.body
    _press_button(ctx, ENDORSED)
    _receipted(ctx)


@when("I reach the handover and the signature")
def _i_reach_the_handover_and_the_signature(ctx):
    _sign_as(ctx, THE_OWNER, MY_ROLE)
    ctx["three"] = _three(ctx)


@then("that item is worded there exactly as it was worded on the card")
def _that_item_is_worded_there_exactly(ctx):
    for item in ctx["open_on_the_card"]:
        assert item in ctx["card_body"], item
        for name, said in ctx["three"].items():
            assert item in said, f"{name} words it differently: {item!r}"


@then("no field name reached the handover documents either")
def _no_field_name_reached_the_handover(ctx):
    for name, said in ctx["three"].items():
        for item in ctx["open_on_the_card"]:
            assert [word for word in BANNED_ON_A_CARD if word in item] == [], f"{name}: {item}"
        assert "impact_grid" not in said and "recovery_target" not in said, name


# ------------------------------------------------------ what the referee hands back


@when("what the referee reports is read")
def _what_the_referee_reports_is_read(ctx):
    ctx["reported"] = _not_passed(ctx)


@then("the activity, the category and the missing time bands are separate parts of it")
def _the_activity_category_and_bands_are_separate_parts(ctx):
    refusal = _the_band_refusal(ctx)
    assert set(refusal.parts) == {"activity", "lens", "horizons"}
    assert refusal.parts["activity"] == ctx["process"]
    assert refusal.parts["lens"] in _listed_lenses(ctx)
    assert all(band in ctx["method_file"]["time_horizons"] for band in refusal.parts["horizons"])


def _listed_lenses(ctx):
    return [scenario["id"] for scenario in ctx["method_file"]["scenarios"]]


@then("no sentence of it is addressed to a manager")
def _no_sentence_of_it_is_addressed_to_a_manager(ctx):
    """What it hands back is the developer's line, and none of those reach the card."""
    for reported in ctx["reported"]:
        assert str(reported) not in record_card(ctx["room_folder"], ctx["process"]).body
    _the_wording_is_the_walks_alone()


# ------------------------------------------------------ the receipt, and the clause that was not


@given("I accepted my BIA")
def _i_accepted_my_bia(ctx):
    _accept(ctx)


@when("I read what the walk says it checked before writing")
def _i_read_what_the_walk_says_it_checked(ctx):
    ctx["said"] = checked_note(_saved(ctx))
    ctx["claimed"] = list(_saved(ctx)[CHECKED])


@then("every clause names a check that ran over something my BIA actually carries")
def _every_clause_names_a_check_that_had_something(ctx):
    record = _landed(ctx)
    assert ctx["claimed"] and ctx["said"] == CHECKED_NOTE.format(checks=_listed(ctx["claimed"]))
    for check, needs in CHECK_NEEDS.items():
        if check in ctx["claimed"]:
            assert check in ctx["said"] and needs(record), f"{check!r} had nothing to examine"
        else:
            assert not needs(record), f"{check!r} had something to examine and claimed nothing"


@then("it does not tell me it confirmed this is still a BIA and not a continuity plan")
def _it_does_not_tell_me_it_confirmed_the_boundary(ctx):
    assert [key for key in BEYOND_THE_BOUNDARY if key in _landed(ctx)] == []
    assert referee.BOUNDARY_CHECK not in ctx["said"]
    assert referee.BOUNDARY_CHECK not in ctx["card"].screen


@then("it says it found every quote word for word in a file in my room")
def _it_says_it_found_every_quote(ctx):
    assert referee.QUOTES_CHECK in ctx["said"]


@then("it says it read the grid and derived the MTPD from it rather than taking the one I stated")
def _it_says_it_read_the_grid_and_derived_the_mtpd(ctx):
    assert referee.GRID_CHECK in ctx["said"] and referee.MTPD_CHECK in ctx["said"]


@then("it says it held the recovery target against the MTPD and checked the data-loss answer")
def _it_says_it_held_the_target_and_checked_the_rpo(ctx):
    assert referee.RTO_CHECK in ctx["said"] and referee.RPO_CHECK in ctx["said"]


# ------------------------------------------------------ a check with nothing to look at


@given("the things a BIA this walk builds can carry")
def _the_things_a_bia_this_walk_builds_can_carry(ctx):
    _record(ctx)
    ctx["carries"] = set(_bia_record(ctx))


@when("the referee's checks are read against them")
def _the_referees_checks_are_read_against_them(ctx):
    ctx["verdict"] = check_draft(ctx["room_folder"], ctx["process"])


@then("a check with nothing of mine to look at records no clause for me to read")
def _a_check_with_nothing_to_look_at_records_no_clause(ctx):
    assert set(BEYOND_THE_BOUNDARY) & ctx["carries"] == set(), ctx["carries"]
    assert referee.BOUNDARY_CHECK not in ctx["verdict"].checked


@then("no clause is recorded before the thing it judges has been looked at")
def _no_clause_is_recorded_before_the_thing_is_looked_at(ctx):
    """The same record with a plan on it earns the clause, which is what makes it falsifiable."""
    drafted = _bia_record(ctx)
    carried = referee.review({**drafted, "plan": A_CONTINUITY_PLAN}, ctx["card"].method, {})
    assert referee.BOUNDARY_CHECK in carried.checked
    assert referee.BOUNDARY_CHECK not in referee.review(drafted, ctx["card"].method, {}).checked


@given("a record that carries a continuity plan")
def _a_record_that_carries_a_continuity_plan(ctx):
    _record(ctx)
    ctx["planned"] = {**_bia_record(ctx), "plan": A_CONTINUITY_PLAN}


@when("the referee reviews that record")
def _the_referee_reviews_that_record(ctx):
    ctx["verdict"] = referee.review(ctx["planned"], ctx["card"].method, {})


@then("it refuses it for standing over the handover boundary")
def _it_refuses_it_for_standing_over_the_boundary(ctx):
    over, = [item for item in ctx["verdict"].rejections if item.kind == refusal.BOUNDARY]
    assert over.parts == {"what": "a continuity plan"}
    assert not ctx["verdict"].passed


@then("the check of that boundary is one it may then say it ran")
def _the_check_of_that_boundary_is_one_it_may_say_it_ran(ctx):
    assert referee.BOUNDARY_CHECK in ctx["verdict"].checked


# ═══════════ 53 — `tests/ui` is judged per test, and runs no suite twice ═════════════════════════
#
# Two halves, and both are read off the files rather than off a run: `features/` is in `testpaths`,
# so every scenario here is collected by the coder's, the cleaner's and the hardener's gates, and a
# scenario that ran `pytest -q tests/ui` to learn what a test costs would charge a half-hour suite
# to three gates that do not pay it today — the very thing this ticket exists to stop. The measured
# figures are section A and B of `archive/qa/tests-ui-is-judged-per-test-and-runs-no-suite-twice.md`.
#
# **Pinned as data, not read back out of git**, for ticket 48's reason above: these scenarios are
# collected inside the tar copy `test_steps_29_and_30_the_gate_notices_a_broken_skin` runs
# `./gate.sh cleaner` in, and that copy is a fresh repository with no `main` in it. A `git
# merge-base` here would turn that gate red for want of a branch. `WAS_ASKED` below was taken with
# `ast.parse` over `git show <merge-base>:<file>` at 3909ec8, the commit this branch was cut from.
#
# Since 165's last slice what is left is the owner's caps in `roles/` and the guard's three
# skip/run scenarios, which drive `tests/gate/branch.py` itself (moved from tests/ui with test_branch.py).

#: `pytest.skip`'s own exception, which is what a guarded step raises when it declines.
SKIPPED = pytest.skip.Exception

ROLES = REPO / "roles"

#: The numbers this ticket says are the owner's, read where they are written rather than out of a
#: diff — a git-free scenario cannot read a diff, and a literal that moved is the same finding.
THE_OWNERS_CAPS = {
    "10-specifier.md": {"maxTurns": 30},
    "15-ponytail.md": {"maxTurns": 40},
    "20-coder.md": {"maxTurns": 60},
    "30-cleaner.md": {"maxTurns": 60},
    "35-architect.md": {"maxTurns": 80},
    "40-hardener.md": {"maxTurns": 80},
    "15-builder.md": {"maxTurns": 300, "gateTimeout": 4200},
}

def _guard():
    """`tests/gate/branch.py`, the one guard a step declines through, as a module of its own."""
    return _ui_module(UI / "branch.py", "branch")


# ── the owner's numbers ──────────────────────────────────────────────────────


@given("every role's caps in `roles/`")
def _t53_the_owners_numbers(ctx):
    """The roles alone since 165's last slice retired `tests/ui/conftest.py` and with it
    `LOCK_WAIT_SECONDS` (last held at dfa2d5ce)."""
    ctx["roles"] = {path.name: path.read_text(encoding="utf-8")
                    for path in sorted(ROLES.glob("*.md"))}


@when("I read this branch's own diff for them")
def _t53_i_read_the_diff_for_them(ctx):
    """Read where they are written rather than out of a diff: these scenarios run inside a tar
    copy with no repository above it (see this section's heading), and a literal that moved is the
    same finding either way."""
    ctx["caps"] = {name: {cap: int(found.group(1))
                          for cap in ("maxTurns", "gateTimeout")
                          for found in [re.search(rf"^{cap}: (\d+)", said, re.M)] if found}
                   for name, said in ctx["roles"].items()}


@then("no role's `gateTimeout` or `maxTurns` moved")
def _t53_no_role_cap_moved(ctx):
    assert ctx["caps"] == THE_OWNERS_CAPS, (
        f"a role's caps moved, and they are the owner's:\n{ctx['caps']}\n{THE_OWNERS_CAPS}")


# ── a step that judges this branch against main ──────────────────────────────


@given("a branch-vs-main step and a run standing on `main`")
def _t53_a_step_on_main(ctx):
    ctx["standing_on"] = "main"


@given("a branch-vs-main step owned by one ticket and a run standing on a different ticket's "
       "branch")
def _t53_a_step_on_another_branch(ctx):
    ctx["standing_on"] = "ticket-99"


@given("a branch-vs-main step and a run standing on the branch of the ticket that owns it")
def _t53_a_step_on_its_own_branch(ctx):
    ctx["standing_on"] = "ticket-34"


def _step_28_as_ticket_34_wrote_it(guard, git):
    """Ticket 34's step 28 as it stood (last held at 602cc648), around the guard it declined
    through: the one claim it made of this branch's diff, read with the `git` it is handed."""
    guard.owned_by("34", "step 28")
    assert git("diff", "main...HEAD", "--", "gate.sh") == "", "step 28: gate.sh moved"


@when("the step is reached")
def _t53_the_step_is_reached(ctx, monkeypatch):
    """`branch.owned_by` itself, over a planted branch and a planted diff (165's last slice
    re-aimed this here from the reaps file's own step 28, which it retired).

    `branch.here` is the one place the guard reads git, so standing the run on a branch is
    monkeypatching that; the step's diff is what it is handed, so a violation is planted by
    handing it a diff that says `gate.sh` moved.
    """
    guard = _guard()
    monkeypatch.setattr(guard, "here", lambda: ctx["standing_on"])
    ctx["declined_before"] = set(guard.DECLINED)
    ctx["guard"] = guard
    try:
        _step_28_as_ticket_34_wrote_it(
            guard, lambda *command: "+ a line of gate.sh this branch moved")
    except BaseException as ended:  # noqa: BLE001 — what it is, is the whole of the scenario
        ctx["ended"] = ended
    else:
        ctx["ended"] = None


@then("it skips rather than passes")
def _t53_it_skips_rather_than_passes(ctx):
    assert isinstance(ctx["ended"], SKIPPED), (
        f"the step did not skip; it ended {ctx['ended']!r} over a planted violation, so an empty "
        "or a stranger's diff would have passed every assertion it makes")
    ctx["why"] = str(ctx["ended"].msg)


@then("the skip names the ticket that owns it and says the diff it judges is empty here")
def _t53_the_skip_names_its_ticket(ctx):
    assert "ticket 34's" in ctx["why"], f"the skip does not say whose step it is: {ctx['why']}"
    assert "step 28" in ctx["why"], f"the skip does not say which step it is: {ctx['why']}"
    assert "empty" in ctx["why"] and "main" in ctx["why"], (
        f"the skip does not say the diff it judges is empty here: {ctx['why']}")


@then("the skip says it would otherwise be reading another ticket's diff as its own")
def _t53_the_skip_says_another_tickets_diff(ctx):
    assert "ticket 34's" in ctx["why"], f"the skip does not say whose step it is: {ctx['why']}"
    assert "another ticket's diff as its own" in ctx["why"], (
        f"the skip does not say what it is declining to read: {ctx['why']}")
    assert ctx["standing_on"] in ctx["why"], (
        f"the skip does not name the branch this run stands on: {ctx['why']}")


@then("it runs")
def _t53_it_runs(ctx):
    assert not isinstance(ctx["ended"], SKIPPED), (
        "the step skipped on the branch of the ticket that owns it, and a step that skips "
        "everywhere is a deleted step wearing a skip")
    assert ctx["guard"].DECLINED == ctx["declined_before"], (
        "the step recorded itself as having declined, on its own branch")


@then("it goes red on a violation planted in that branch's own diff")
def _t53_it_goes_red_on_a_planted_violation(ctx):
    assert isinstance(ctx["ended"], AssertionError), (
        f"the planted `gate.sh` move did not turn the step red; it ended {ctx['ended']!r}")
    assert "gate.sh moved" in str(ctx["ended"]), (
        f"the step went red without naming what moved: {ctx['ended']}")


# ════════════ 25 — a run that already exists gets an identity too ════════════════════════════════
#
# `features/a-run-that-already-exists-gets-an-identity-too.feature`. The room here is the one
# ADR-0011 describes and no test room was: minted from the seed, so it arrives with a run already
# on file at stage 1 with nothing decided. Every other room in this file is built empty and walked
# from the first press, which is exactly why the missing identity went unmeasured until the
# 2026-09-13 code review measured it.


@given("my room is the one ADR-0011 describes")
def _my_room_is_the_one_adr_0011_describes(ctx):
    """A minted room: the company's files, the method, and evidence a walk can be finished over."""
    _my_companys_room_is(ctx, "adler-7ycyet")
    ctx["process"] = "Incident and problem management"
    _refereed_room(ctx)
    _open_room(ctx)


@given(parsers.parse(
    'it ships a run for "{process}" whose stage is 1 and whose decisions are empty'))
def _it_ships_a_run_at_stage_1_with_nothing_decided(ctx, process):
    """The run the ADR's own room arrives with, in the shape the code review read off disk."""
    ctx["process"] = process
    write_record(ctx["room_folder"], run_file(process), {
        "schema": SCHEMA, "room": ctx["room"], "process": process, "stage": STAGE,
        "status": AWAITING_HUMAN, "decisions": []}, 0)
    assert _slugs(process)[0] in in_progress(ctx["room_folder"]), "the room ships no run at all"


@given("that run carries no identity of its own")
def _that_run_carries_no_identity_of_its_own(ctx):
    assert "run_id" not in _saved(ctx), "this run is already identified, so it proves nothing"


def _room_with_no_run_at_all(ctx, name):
    """The same room with the shipped run taken out of it: the room every other test builds."""
    folder = Path(shutil.copytree(ctx["room_folder"], ctx["tmp"] / name))
    shutil.rmtree(folder / RUNS)
    return folder


@then("I am asked to agree the scope, the way a room with no run at all asks me")
def _i_am_asked_to_agree_the_scope_the_same_way(ctx):
    served, plain = ctx["card"], open_bia(_room_with_no_run_at_all(ctx, "no-run"), ctx["process"])
    assert served.buttons == plain.buttons == (AGREE,)
    assert (served.body, served.decision, served.rule, served.gradient) == (
        plain.body, plain.decision, plain.rule, plain.gradient)


@then("nothing tells me the scope is already agreed")
def _nothing_tells_me_the_scope_is_already_agreed(ctx):
    assert ctx["card"].body != RESUMED.format(process=ctx["process"])
    assert "already agreed" not in ctx["card"].body


@then("the run on file carries an identity of its own")
def _the_run_on_file_carries_an_identity_of_its_own(ctx):
    ctx["identity"] = _saved(ctx).get("run_id")
    assert ctx["identity"], "the run this room shipped was given no identity"


@then("it is the same shape of identity a run created at that press would have got")
def _it_is_the_same_shape_of_identity(ctx):
    """Against a run this very press creates, rather than against a remembered shape: the two runs
    differ in the room they stand in and in nothing else."""
    folder = _room_with_no_run_at_all(ctx, "created-at-the-press")
    answer(folder, ctx["process"], AGREE, 0)
    created = read_record(folder, run_file(ctx["process"]))
    assert uuid.UUID(ctx["identity"]).version == uuid.UUID(created["run_id"]).version == 4
    assert set(_saved(ctx)) == set(created), "the two runs are not the same shape"


@then("the evidence is laid over the lenses my room's method names")
def _the_evidence_is_laid_over_my_rooms_lenses(ctx):
    named = [scenario["id"] for scenario in ctx["method_file"]["scenarios"]]
    assert list(_grid(ctx)) == named
    assert _saved(ctx)["method"]["scenarios"] == ctx["method_file"]["scenarios"]


@then("the grid is not empty")
def _the_grid_is_not_empty(ctx):
    assert _grid(ctx), "stage 3 drafted a grid with no lens in it at all"


def _grid(ctx):
    """The impact grid on the stage 3 card, which is empty for a run carrying no method."""
    return ctx["card"].proposal["activities"][0][IMPACT_GRID]


@then(parsers.parse('it carries a "{label}" line'))
def _it_carries_a_source_line(ctx, label):
    """The card's line, and the same files on the run: what the walk says it read and what it
    carries forward are one thing, and it was the run's copy this defect lost."""
    _the_card_carries_a_source_line(ctx, label)
    assert _saved(ctx)["sources"] == list(ctx["card"].sources)


@given(parsers.parse('I have agreed the scope for "{process}" and walked on to stage 4'))
def _i_have_agreed_the_scope_and_walked_on_to_stage_4(ctx, process):
    _i_have_agreed_the_scope_for(ctx, process)
    ctx["raised"] = None
    try:
        ctx["card"] = _stage_card(ctx, STAGE_4)
    except Exception as raised:  # noqa: BLE001 — what reaches the screen is the scenario's subject
        ctx["raised"] = raised


@when("the record for that walk is built and accepted")
def _the_record_for_that_walk_is_built_and_accepted(ctx):
    if ctx["raised"] is not None:
        return
    try:
        _press_button(ctx, ENDORSED)
    except Exception as raised:  # noqa: BLE001 — as above
        ctx["raised"] = raised


@then("it is built, and it carries that run's identity")
def _it_is_built_and_carries_that_runs_identity(ctx):
    assert _landed(ctx) is not None, f"no record was written at all ({ctx['raised']!r})"
    assert _landed(ctx)["run_id"] == _saved(ctx)["run_id"]


@then("nothing on my screen is an exception out of the walk")
def _nothing_on_my_screen_is_an_exception(ctx):
    assert ctx["raised"] is None, f"the walk raised {ctx['raised']!r}"
    assert "Traceback" not in ctx["card"].screen


@then("the walk may go on to stage 5, because that record is its own work")
def _the_walk_may_go_on_to_stage_5(ctx):
    carried = move_past_stage_4(ctx["room_folder"], _saved(ctx))
    assert carried["run_id"] == _saved(ctx)["run_id"]
    assert [card.stage for card in onward(ctx["room_folder"], ctx["card"])] == [STAGE_5]


@when("I answer the stages that follow, one after another")
def _i_answer_the_stages_that_follow(ctx):
    ctx["identities"] = [_saved(ctx)["run_id"]]
    for stage in (STAGE_2, STAGE_3, STAGE_4, STAGE_5):
        ctx["card"] = _stage_card(ctx, stage)
        ctx["identities"].append(_saved(ctx)["run_id"])


@then("the identity on the run is the one it was given at the first answer, every time")
def _the_identity_is_the_one_it_was_given_at_the_first_answer(ctx):
    assert len(ctx["identities"]) == 5
    assert set(ctx["identities"]) == {ctx["identities"][0]}


@given("my room also holds a BIA record produced by some other run")
def _my_room_also_holds_another_runs_record(ctx):
    write_record(ctx["room_folder"], _record_at(ctx), {"run_id": SEEDED_RUN}, 0)


@when(parsers.parse('I agree the scope for "{process}" and walk on to stage 4'))
def _i_agree_the_scope_and_walk_on_to_stage_4(ctx, process):
    _i_have_agreed_the_scope_for(ctx, process)
    ctx["card"] = _stage_card(ctx, STAGE_4)
    ctx["run"] = _saved(ctx)
    _the_walk_tries_to_move_past_stage_4(ctx)


@then("the walk refuses to finish over that record")
def _the_walk_refuses_to_finish_over_that_record(ctx):
    assert ctx["refusal"] is not None, "this walk closed over somebody else's record"
    assert ctx["carried"] is None


@then("it says the record was not produced by this walk")
def _it_says_the_record_was_not_produced_by_this_walk(ctx):
    assert ctx["refusal"].found == SEEDED_RUN
    assert SEEDED_RUN in str(ctx["refusal"]) and str(ctx["run"]["run_id"]) in str(ctx["refusal"])
