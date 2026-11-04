"""The record stage 4 builds, and the identity a walk may finish over.

Two defects are the whole of this module and each is a test here: a record assembled from anything
but what the human endorsed, and a walk closing over the BIA the room happened to ship with.
"""

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo.bia import (
    NO_RUN_AT_ALL,
    RECORD_SCHEMA,
    StaleRecord,
    _cited,
    build,
    is_ours,
    own,
)
from nemo.evidence import LABELS, standardise
from nemo.record import (
    ACTIVITIES,
    ALSO_IN,
    DEPENDENCIES,
    EVIDENCE,
    MBCO,
    MTPD,
    OWNER,
    QUOTE,
    RECOVERY_TARGET,
    RPO,
    SOURCE_PATH,
    TRANSCRIPT_QUOTE,
    TYPE,
    fingerprint,
)
from nemo.referee import review
from nemo.text import found_in

TRANSCRIPT = """---
department: Slaughter
covered: financial
---

# Slaughter interview

Torsten Ahlgrim: MTPD: 24 h for the slaughter process.
Torsten Ahlgrim: RPO: 4 h (ERP order data).
Petra Nolte: RTO: 8 h for the stunning line.
Torsten Ahlgrim: Impact financial: 0–4 h 2, 8 h 3, 24 h 4.
Torsten Ahlgrim: Depends on: ammonia refrigeration, the sticking-pen conveyor.
"""

PATH = "07_Interviews/26_08_00_interview.md"
#: The room's readable files as the walk hands them over: the confirmed interviews, in the order the
#: run confirmed them. One here; the tests of ticket 131 below hand over two.
FILES = {PATH: TRANSCRIPT}
REGISTER = {"KA-01": {"name": "ammonia refrigeration", "department": "Slaughter"}}
RUN_ID = "1a4f7c6e-0b2d-4e5a-9c3b-8d7e6f5a4b3c"


def run(transcript=TRANSCRIPT, run_id=RUN_ID):
    """A run state as stage 3 leaves it: the endorsed proposal, and the run's own identity."""
    drafted = standardise(transcript, REGISTER, ["financial", "legal-regulatory"])
    return {"run_id": run_id, "process": "Slaughter",
            "transcript": {"path": PATH}, **drafted.proposal}


def activity(**kwargs):
    built, = build(run(**kwargs), FILES)["activities"]
    return built


# ── the record is what was endorsed, and nothing beside it ───────────────────


def test_the_record_carries_this_runs_identity_and_the_department_it_is_about():
    built = build(run(), FILES)
    assert built["run_id"] == RUN_ID
    assert built["dept"] == "Slaughter"
    assert built["record_schema_version"] == RECORD_SCHEMA


def test_every_activity_the_interview_covered_is_in_the_record():
    assert [item["name"] for item in build(run(), FILES)["activities"]] == ["Slaughter"]


def test_the_grid_is_the_one_stage_3_standardised():
    assert activity()["impact_grid"]["financial"] == {"0–4 h": 2, "8 h": 3, "24 h": 4}


def test_each_stated_figure_lands_under_the_field_the_referee_reads_it_from():
    built = activity()
    assert built["mtpd"] == "24 h"
    assert built["recovery_target"] == "8 h"
    assert built["rpo"] == "4 h (ERP order data)"


def test_a_figure_the_interview_never_stated_leaves_its_field_off_the_activity():
    """An absent field is the referee's "nobody said". A None would be a stated nothing."""
    assert "mbco" not in activity()


def test_every_quote_is_cited_to_the_interview_its_words_were_found_in():
    quoted = activity()["evidence"]
    assert {item["source_path"] for item in quoted} == {PATH}
    assert {item["type"] for item in quoted} == {TRANSCRIPT_QUOTE}
    for item in quoted:
        assert item["quote"] in TRANSCRIPT


def test_a_scored_category_carries_the_lens_its_quote_supports():
    tagged = [item for item in activity()["evidence"] if "lens" in item]
    assert [item["lens"] for item in tagged] == ["financial"]
    assert tagged[0]["quote"].endswith("24 h 4.")


# ── a quote names the file its words were found in (ticket 131, ADR-0030 decision 3) ──────────
#
# Every confirmed interview is searched (the owner's 17 September ruling, stage 2 = all interviews
# about the activity), with the referee's own comparison, and the record writes where the words
# were found — never the bound interview by default, and never an empty path.

FOLLOWUP = "07_Interviews/26_08_20_followup-interview.md"
METHOD = {"time_horizons": ["0–4 h", "8 h", "24 h"], "intolerability_threshold": 4,
          "scenarios": [{"id": "financial"}, {"id": "legal-regulatory"}]}


def quoted_in(files):
    """Every evidence entry of the one activity, built over the room's files as handed over."""
    built, = build(run(), files)[ACTIVITIES]
    return built[EVIDENCE]


def test_a_quote_from_the_second_interview_is_recorded_with_that_interviews_path():
    """The bound interview holds none of these words; the second does, so the record says so."""
    quoted = quoted_in({PATH: "Torsten Ahlgrim opened the meeting.", FOLLOWUP: TRANSCRIPT})
    assert {item[SOURCE_PATH] for item in quoted} == {FOLLOWUP}
    assert not any(ALSO_IN in item for item in quoted)


def test_a_quote_in_two_files_records_the_first_confirmed_and_the_other_as_data():
    quoted = quoted_in({FOLLOWUP: TRANSCRIPT, PATH: TRANSCRIPT})
    assert {item[SOURCE_PATH] for item in quoted} == {FOLLOWUP}
    assert all(item[ALSO_IN] == [PATH] for item in quoted)


def test_a_quote_the_file_holds_only_in_other_typography_is_found_as_the_referee_finds_it():
    """Curly quotes, dashes and spacing: `nemo.text.norm`'s forgiveness, and nothing more."""
    typed = TRANSCRIPT.replace("0–4 h", "0-4  h").replace(": ", ":\u00a0")
    assert typed != TRANSCRIPT
    files = {PATH: typed}
    quoted = quoted_in(files)
    assert {item[SOURCE_PATH] for item in quoted} == {PATH}
    assert not any("possible fabrication" in r
                   for r in review(build(run(), files), METHOD, files).rejections)


def test_a_quote_no_file_holds_is_refused_naming_the_file_it_was_claimed_from():
    """Found nowhere, the quote keeps the file stage 3 read it from, the bound interview, so the
    refusal names the file that does not hold it. It is refused, so it is never signed."""
    files = {PATH: "Nobody said any of it.", FOLLOWUP: "Nor here."}
    quoted = quoted_in(files)
    assert {item[SOURCE_PATH] for item in quoted} == {PATH}
    assert not any(ALSO_IN in item for item in quoted)
    refused = review(build(run(), files), METHOD, files).rejections
    assert any("possible fabrication" in r and PATH in r for r in refused)


def test_an_entry_carrying_its_own_path_keeps_it_when_no_file_holds_its_words():
    """Words no file holds keep the file they were claimed from: the entry's own when it carries
    one, and only otherwise the bound interview stage 3 read."""
    claimed = {TYPE: TRANSCRIPT_QUOTE, QUOTE: "Nobody said any of it.", SOURCE_PATH: FOLLOWUP}
    cited, = _cited({EVIDENCE: [claimed]}, lambda quote: [], PATH)[EVIDENCE]
    assert cited[SOURCE_PATH] == FOLLOWUP
    assert ALSO_IN not in cited


def test_each_file_is_normalised_once_per_build_however_many_quotes_are_sought(monkeypatch):
    """Ticket 131's perf fix: the room's files are folded once per build and every quote is sought
    in the folded text. Folding every file again for every quote doubled the skin suite (770 s to
    1690 s) and timed out the coder gate that tests/ui runs inside itself."""
    import nemo.text

    folded = []
    real = nemo.text.norm

    def counted(value):
        folded.append(value)
        return real(value)

    monkeypatch.setattr(nemo.text, "norm", counted)
    files = {FOLLOWUP: TRANSCRIPT, PATH: "Torsten Ahlgrim opened the meeting."}
    quoted = quoted_in(files)
    assert len(quoted) > 1
    assert [folded.count(text) for text in files.values()] == [1, 1]


def test_a_dependency_the_register_models_is_carried_by_its_own_id():
    assert activity()["dependencies"] == ["KA-01"]


def test_a_dependency_the_register_does_not_model_carries_no_id_at_all():
    """The graph believes an id. An unmodelled dependency is an open item, never an invention."""
    assert "the sticking-pen conveyor" not in str(activity()["dependencies"])


def test_the_record_has_the_person_the_interview_states_the_figures_owning_the_activity():
    """Whose sign-off closes this BIA is a fact about the record (ticket 18), so it is *in* it.

    The owner-stated figures are the ones stage 3 already puts in a person's mouth, so the person
    the interview has stating them is the person the record has owning the activity — read off the
    record at the signature rather than back out of a transcript somebody could edit meanwhile.
    """
    assert activity()[OWNER] == "Torsten Ahlgrim"


def test_an_activity_whose_figures_nobody_stated_records_no_owner_rather_than_a_guess():
    """An RTO is read off the evidence rather than stated, so a transcript that holds only one
    puts nobody's name to the activity — and stage 5 has nobody to match a signer against."""
    read_only = TRANSCRIPT.replace("Torsten Ahlgrim: MTPD:", "Torsten Ahlgrim: RTO:").replace(
        "Torsten Ahlgrim: RPO:", "Torsten Ahlgrim: RTO:")

    assert activity(transcript=read_only)[OWNER] == ""


def test_the_method_and_what_was_left_open_are_carried_into_the_record_itself():
    """Ticket 16's views are a function of the record bytes, so both have to be *in* the bytes.

    A record that made the four views go to the room for the horizons they lay a grid over, or
    for the items the walk left open, could be rendered twice from one record and come back
    different — which is the v1 defect the four views exist to make impossible.
    """
    method = {"time_horizons": ["0–4 h", "8 h", "24 h"], "intolerability_threshold": 4}
    left_open = ["the sticking-pen conveyor — your register does not model it."]

    built = build({**run(), "method": method, "open_items": left_open}, FILES)

    assert built["method"] == method
    assert built["open_items"] == left_open


def test_a_run_that_named_no_method_and_left_nothing_open_records_an_absence_of_each():
    """An absence of each, in the record, rather than a key the views would have to reach past."""
    built = build({"run_id": RUN_ID, "process": "Slaughter", "transcript": {"path": PATH}}, FILES)

    assert built["method"] == {}
    assert built["open_items"] == []


def test_what_stage_three_left_open_reaches_the_record_without_being_asked_for():
    assert "sticking-pen conveyor" in str(build(run(), FILES)["open_items"])


def test_a_run_that_endorsed_no_activity_records_none():
    assert build({"run_id": RUN_ID, "process": "Slaughter",
                  "transcript": {"path": PATH}}, FILES)["activities"] == []


def test_building_the_same_run_twice_produces_the_same_bytes():
    """The movement is re-executed rather than rolled back (ADR-0010), so it must be a function."""
    assert fingerprint(build(run(), FILES)) == fingerprint(build(run(), FILES))


def test_two_runs_over_the_same_evidence_produce_two_different_records():
    assert fingerprint(build(run(), FILES)) != fingerprint(build(run(run_id="other"), FILES))


# ── a record this run did not produce ────────────────────────────────────────


def test_the_record_this_run_wrote_is_the_record_this_run_may_finish_over():
    assert own({"run_id": RUN_ID}, RUN_ID) == {"run_id": RUN_ID}
    assert is_ours({"run_id": RUN_ID}, RUN_ID) is True


def test_a_record_another_run_produced_is_refused_by_name():
    with pytest.raises(StaleRecord) as refusal:
        own({"run_id": "7abf4990"}, RUN_ID)
    assert refusal.value.found == "7abf4990"
    assert "7abf4990" in str(refusal.value) and RUN_ID in str(refusal.value)
    assert is_ours({"run_id": "7abf4990"}, RUN_ID) is False


def test_a_room_with_no_record_at_all_is_nothing_to_finish_over():
    with pytest.raises(StaleRecord) as refusal:
        own(None, RUN_ID)
    assert NO_RUN_AT_ALL in str(refusal.value)


def test_a_record_carrying_no_run_at_all_is_refused_and_said_to_carry_none():
    with pytest.raises(StaleRecord) as refusal:
        own({"activities": []}, RUN_ID)
    assert NO_RUN_AT_ALL in str(refusal.value)


@given(st.one_of(st.none(), st.text()))
def test_a_record_carrying_no_run_at_all_is_refused_by_every_run_there_is(mine):
    """An absence is an absence rather than a value. A record with no ``run_id`` was produced by
    no run, so there is no identity a walk could carry — the empty string included, and no
    identity at all included — that would make it this walk's own. Two absences read as equal is
    how a record nobody produced comes to be owned by a run nobody identified.
    """
    assert is_ours({"activities": []}, mine) is False


def test_the_refusal_rests_on_the_run_and_never_on_when_the_record_was_touched():
    """A live record carries no modification time of any kind, so a check built on one never
    fires. This one fires on a record with nothing but a run id in it."""
    stale = {"run_id": "7abf4990", "modified": "2099-01-01T00:00:00Z"}
    assert is_ours(stale, RUN_ID) is False
    assert is_ours({"run_id": RUN_ID}, RUN_ID) is True


@given(st.text(min_size=1), st.text(min_size=1))
def test_a_record_is_this_runs_exactly_when_the_two_identities_are_the_same(found, mine):
    assert is_ours({"run_id": found}, mine) == (found == mine)


#: A run identity, out of a pool small enough that two draws are often the same one. Generated
#: text would make the agreeing half of the rule below a branch these tests never take: two
#: independent `st.text()` draws are equal about never, and this project's profile is
#: derandomized, so "about never" is "not once, on every run, forever".
IDENTITIES = st.sampled_from([RUN_ID, "7abf4990", "", "0"])

#: A record as a room could hold one, at the four shapes the rule distinguishes: no record at
#: all, a record carrying no run, one carrying a run that is `None`, and one carrying an identity.
#: `modified` is in here because the refusal must not start resting on it — a live record has
#: never carried one, and a check built on a timestamp waves every stale record through.
SAVED = st.none() | st.fixed_dictionaries({}, optional={
    "run_id": IDENTITIES | st.none(),
    "modified": st.text(max_size=4),
    ACTIVITIES: st.just([]),
})


@given(SAVED, IDENTITIES)
def test_the_record_a_walk_may_finish_over_is_the_room_s_own_and_not_a_copy(saved, mine):
    """What `own` hands back is the object it was given, whatever the record holds.

    The properties above are all stated through `is_ours`, which is `own` with the refusal caught
    — so they say everything about the decision and nothing about the value, and the only record
    `own` had ever been asked to hand back was the one-key one written out above. `is` rather than
    `==`: stage 4 closes over the room's own bytes, and a check that returned a copy or a rebuilt
    dict on the way past would put a record nobody saved between the read and the close.

    Nothing is asserted about the record afterwards because there is nothing to assert: `own`
    decides and returns, and the record it was handed is the record it hands on.
    """
    if is_ours(saved, mine):
        assert own(saved, mine) is saved


@given(SAVED, IDENTITIES)
def test_the_refusal_always_names_what_it_found_and_what_this_walk_is(saved, mine):
    """An operator reading the refusal can act on it without reading the code.

    Both sides are in the sentence, and an absence is said as `no run at all` rather than as an
    empty space where a tag should be — a refusal that named nothing would leave a manager with a
    room that will not close and no way to see why.
    """
    if is_ours(saved, mine):
        return
    with pytest.raises(StaleRecord) as refusal:
        own(saved, mine)
    assert str((saved or {}).get("run_id") or NO_RUN_AT_ALL) in str(refusal.value)
    assert str(mine or NO_RUN_AT_ALL) in str(refusal.value)


# ── the builder as properties, over run states nobody wrote out ──────────────
#
# `build` is pure — a function of the run state and of nothing else — so the examples above pin
# what one interview produces and these pin what every run state does. The strategies generate the
# run state as `nemo.evidence.Activity.proposed` spells it, including the shapes a transcript will
# not produce today (a label nothing standardises, an unresolved dependency, an activity with
# nothing under it at all), because stage 4 is handed the run state rather than the transcript and
# a later stage 3 may widen what it puts there.

WORDS = st.text(max_size=8)
_STATEMENTS = st.fixed_dictionaries({
    "label": st.sampled_from([*LABELS, "Note", ""]), "value": WORDS,
    "speaker": WORDS, "quote": WORDS, "owner_stated": st.booleans()})
_SCORES = st.fixed_dictionaries({
    "lens": WORDS, "row": st.dictionaries(WORDS, st.integers(0, 5), max_size=2),
    "speaker": WORDS, "quote": WORDS})
_DEPENDENCIES = st.fixed_dictionaries({
    "heard": WORDS, "owner": WORDS, "asset_id": WORDS, "held_by": WORDS})
_ACTIVITIES = st.fixed_dictionaries({
    "name": WORDS,
    "impact_grid": st.dictionaries(WORDS, st.dictionaries(WORDS, st.integers(0, 5), max_size=2),
                                   max_size=2),
    "evidence": st.lists(_STATEMENTS, max_size=3),
    "scores": st.lists(_SCORES, max_size=3),
    "dependencies": st.lists(_DEPENDENCIES, max_size=3)})
RUNS = st.fixed_dictionaries({
    "run_id": st.text(max_size=12), "process": WORDS,
    "transcript": st.fixed_dictionaries({"path": st.text(min_size=1, max_size=12)}),
    "activities": st.lists(_ACTIVITIES, max_size=3)})


@given(RUNS)
def test_every_record_this_walk_builds_is_one_this_walk_may_finish_over(run_state):
    """The two halves of stage 4 agreeing by construction: whatever `build` writes, `own` lets
    this run close over, and no run state produces a record its own walk would call stale."""
    assert is_ours(build(run_state, FILES), run_state["run_id"])


@given(RUNS)
def test_building_the_same_run_state_twice_is_the_same_bytes_and_leaves_it_alone(run_state):
    """What ADR-0010 needs of an interrupted movement: re-running it rewrites what it wrote.

    Purity both ways — the same answer twice, and the run state it was given unchanged, because
    the record lands before the run file follows it and a builder that edited its input would
    make the second attempt a different record.
    """
    before = copy.deepcopy(run_state)

    assert fingerprint(build(run_state, FILES)) == fingerprint(build(run_state, FILES))
    assert run_state == before


@given(RUNS)
def test_no_activity_carries_a_dependency_id_the_run_state_did_not_resolve(run_state):
    """An id the graph believes is never invented here, and an unresolved one is left out."""
    resolved = {item["asset_id"] for activity in run_state["activities"]
                for item in activity["dependencies"]} - {""}

    for built in build(run_state, FILES)[ACTIVITIES]:
        assert set(built[DEPENDENCIES]) <= resolved


@given(RUNS, st.dictionaries(st.text(min_size=1, max_size=6), st.text(max_size=30), max_size=3))
def test_every_quote_names_the_first_file_holding_its_words_and_no_file_that_does_not(
        run_state, files):
    """Ticket 131 over run states and rooms nobody wrote out: the cited file is the first in the
    order handed over that holds the words, every other that does is in `also_in`, and no entry
    anywhere carries an empty path — words found nowhere keep the bound interview, which the
    referee then names in refusing them."""
    bound = run_state["transcript"]["path"]
    for built in build(run_state, files)[ACTIVITIES]:
        for item in built[EVIDENCE]:
            holding = found_in(item[QUOTE], files)
            assert item[SOURCE_PATH] != ""
            assert [item[SOURCE_PATH], *item.get(ALSO_IN, [])] == (holding or [bound])
            assert item[TYPE] == TRANSCRIPT_QUOTE


@given(RUNS)
def test_a_figure_no_statement_carries_leaves_its_field_off_every_activity(run_state):
    """The generalised form of the MBCO example above: absence is absence, never a stated
    nothing, whichever of the four labels the interview happened to miss."""
    records = build(run_state, FILES)[ACTIVITIES]
    for proposed, built in zip(run_state["activities"], records, strict=True):
        stated = {item["label"] for item in proposed["evidence"]}
        assert (RECOVERY_TARGET in built) == ("RTO" in stated)


#: The four fields an activity files a figure under, named by `nemo.record` for the builder here
#: and the referee that reads them back.
FIGURES = (MTPD, RECOVERY_TARGET, RPO, MBCO)


@given(st.sampled_from(LABELS), WORDS)
def test_every_label_stage_three_standardises_lands_on_a_field_the_record_names(label, value):
    """The join between the two vocabularies, asked of each label rather than of one example.

    A label stage 3 knows how to standardise and stage 4 has no field for would drop its figure
    out of the record in silence — the interview states it, the card shows it, and the referee
    reads `None` where it should have read a figure.
    """
    stated = {"label": label, "value": value, "speaker": "", "quote": "", "owner_stated": True}
    run_state = {"run_id": RUN_ID, "process": "Slaughter", "transcript": {"path": PATH},
                 "activities": [{"name": "Slaughter", "impact_grid": {}, "evidence": [stated],
                                 "scores": [], "dependencies": []}]}

    built, = build(run_state, FILES)[ACTIVITIES]

    assert [field for field in FIGURES if field in built and built[field] == value]
