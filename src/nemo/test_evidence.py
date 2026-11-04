"""The transcript read as standardised evidence, and everything it may not say.

The three defects this module exists to prevent are each a test here: an RTO asserted from a label
with nothing beside it, an asset id invented for a dependency the register does not model, and a
reason invented for a category the interview never reached.

The examples say what one transcript makes of one register, and the properties under them say what
*any* does. That split matters more here than anywhere else in the package: this module's whole
claim is negative — what it refuses to assert — and a negative claim is exactly the one an example
cannot make. "This register has no id for a sticking-pen conveyor" is a fact about one fixture;
"no dependency ever resolves to an id the register does not hold" is the thing the graph rests on,
and only a generated register says it.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo.evidence import (
    COVERED,
    DEPENDS,
    DISPUTED,
    DURATIONS,
    IMPACT,
    LABELS,
    MISSING,
    NOT_ELICITED,
    NOT_STATED,
    OWNER_STATED,
    UNKNOWN,
    standardise,
)
from nemo.record import DEPARTMENT
from nemo.text import norm

TRANSCRIPT = """---
department: Slaughter
covered: financial
not elicited: we ran out of time before the legal side of it
note: Torsten Ahlgrim: MTPD: 99 h, which nobody said out loud
---

# Slaughter interview

Torsten Ahlgrim: MTPD: 24 h for the slaughter process.
Torsten Ahlgrim: RPO: 4 h (ERP order data).
Torsten Ahlgrim: MBCO: one shift, A-customers only.
Petra Nolte: RTO: 8 h for the stunning line, which we have held to.
Petra Nolte: RTO: for the slaughter line we never settled one.
Torsten Ahlgrim: Depends on: ammonia refrigeration, chilling plant (Cutting).
Torsten Ahlgrim: Depends on: the sticking-pen conveyor.
"""

REGISTER = {
    "KA-01": {"name": "ammonia refrigeration", "department": "Slaughter"},
    "KA-02": {"name": "chilling plant", "department": "Slaughter"},
    "KA-09": {"name": "ammonia refrigeration unit", "department": "Slaughter"},
    "rows": [1, None],
}

LENSES = ["financial", "legal-regulatory"]


def draft(transcript=TRANSCRIPT, register=REGISTER, lenses=LENSES):
    return standardise(transcript, register, lenses)


def stated(label, **kwargs):
    return [item for item in draft(**kwargs).statements if item.label == label]


# ── what the transcript states, and what it does not ─────────────────────────


def test_a_label_with_a_figure_beside_it_is_asserted():
    assert [item.value for item in stated("RTO")] == ["8 h"]


def test_a_label_with_no_figure_beside_it_asserts_nothing():
    """"RTO:" and then a sentence that never gives one. v1 would have asserted the sentence."""
    assert [item.quote for item in stated("RTO") if "slaughter line" in item.quote] == []


def test_the_figure_is_the_string_the_transcript_holds():
    assert stated("MTPD")[0].value == "24 h"
    assert stated("MTPD")[0].value in TRANSCRIPT


def test_the_owners_own_statements_are_marked_and_carry_his_sentence():
    for label in ("MTPD", "RPO", "MBCO"):
        statement = stated(label)[0]
        assert statement.owner_stated
        assert statement.speaker == "Torsten Ahlgrim"
        assert statement.quote in TRANSCRIPT, "the quote is not the file's own characters"


def test_an_rto_is_not_an_owner_statement():
    """It is read off the evidence, so it is not put in anybody's mouth."""
    assert stated("RTO")[0].owner_stated is False
    assert stated("RTO")[0].speaker == "Petra Nolte"


def test_a_stated_value_keeps_the_words_after_the_figure():
    assert stated("RPO")[0].value == "4 h (ERP order data)"
    assert stated("MBCO")[0].value == "one shift, A-customers only"


def test_a_line_nobody_spoke_states_nothing():
    assert standardise("# Slaughter interview\n", {}, []).statements == ()


def test_a_figure_in_the_front_matter_is_not_testimony():
    """The header is what the transcript says *about* itself, and nobody spoke it. A figure in it
    read as evidence would be a target on the card that no one in the room ever gave."""
    assert [item.value for item in draft().statements if item.value == "99 h"] == []
    assert "99 h" in TRANSCRIPT, "the fixture no longer states a figure in its front matter"


def test_a_figure_nobody_is_recorded_as_saying_is_stated_in_nobodys_name():
    """A line with no speaker on it still states what it states — and states it as nobody's."""
    statement, = standardise("RTO:8 h for the stunning line.\n", {}, []).statements
    assert (statement.value, statement.speaker) == ("8 h", "")


def test_a_value_loses_the_full_stop_after_it_and_not_a_letter_of_what_was_said():
    said = TRANSCRIPT.replace("one shift, A-customers only.", "one shift on line X.")
    assert stated("MBCO", transcript=said)[0].value == "one shift on line X"


# ── the dependencies ─────────────────────────────────────────────────────────


def test_a_modelled_dependency_resolves_to_the_registers_exact_id():
    resolved = {item.heard: item.asset_id for item in draft().dependencies}
    assert resolved["ammonia refrigeration"] == "KA-01"
    assert resolved["chilling plant"] == "KA-02"


def test_no_lookalike_id_is_used_for_a_dependency_the_register_does_not_model():
    unmodelled = [item for item in draft().dependencies if item.heard.endswith("conveyor")]
    assert [item.asset_id for item in unmodelled] == [""]
    assert "KA-09" not in str(draft().proposal), "a near-match was resolved to"


def test_a_dependency_is_heard_in_every_letter_of_the_name_it_was_given():
    """Only the full stop that ended the sentence comes off the last one named."""
    said = TRANSCRIPT.replace("the sticking-pen conveyor.", "the conveyor on line X.")
    assert draft(transcript=said).dependencies[-1].heard == "the conveyor on line X"


def test_a_dependency_the_register_does_not_model_is_held_by_nobody():
    """No id, and no department either: the register says nothing about it, so neither do we."""
    unmodelled, = [item for item in draft().dependencies if not item.asset_id]
    assert (unmodelled.asset_id, unmodelled.held_by) == ("", "")


def test_a_dependency_the_register_holds_under_no_department_is_held_by_nobody():
    """The entry is modelled, so it resolves; who holds it the register does not say."""
    silent = {"KA-02": {"name": "chilling plant"}}
    item, = [dep for dep in draft(register=silent).dependencies if dep.asset_id]
    assert (item.asset_id, item.held_by) == ("KA-02", "")


def test_the_contradiction_is_put_in_both_sources_own_words():
    """Who each of the two says holds it, said as each of them says it: the manager settles which
    is right, and a paraphrase of either side is the card settling it for them."""
    assert DISPUTED.format(heard="chilling plant", said="Cutting",
                           held="Slaughter") in draft().open_items


def test_the_unmodelled_dependency_is_an_open_item_in_the_words_it_was_heard_in():
    item = [text for text in draft().open_items if "conveyor" in text]
    assert len(item) == 1
    assert "the sticking-pen conveyor" in item[0]
    assert "does not model" in item[0]


def test_a_contradiction_about_who_owns_a_dependency_leads_the_open_items():
    """Whatever the evidence forces a decision about comes first; the rest can wait."""
    assert "Cutting" in draft().open_items[0] and "chilling plant" in draft().open_items[0]
    assert "conveyor" in draft().open_items[-1]


def test_an_owner_the_register_agrees_with_is_no_open_item():
    agreed = TRANSCRIPT.replace("chilling plant (Cutting)", "chilling plant (Slaughter)")
    assert [text for text in draft(transcript=agreed).open_items if "chilling" in text] == []


def test_a_room_with_no_register_models_nothing_and_invents_nothing():
    items = draft(register={}).open_items
    assert len(items) == 3, "every dependency is unmodelled, and every one is an open item"
    assert [item.asset_id for item in draft(register={}).dependencies] == ["", "", ""]


def test_a_transcript_that_names_no_dependency_raises_no_open_item():
    heard = "Petra Nolte: we hold orders for one shift.\n"
    assert standardise(heard, REGISTER, []).open_items == ()


# ── what the interview never reached ─────────────────────────────────────────


def test_a_category_the_interview_never_reached_is_proposed_as_unknown():
    assert draft().unknown == ("legal-regulatory",)
    assert draft().proposal["worst_case"] == {"legal-regulatory": UNKNOWN}


def test_a_category_the_interview_reached_is_not_proposed_as_unknown():
    assert "financial" not in draft().unknown


def test_the_reason_is_pre_filled_from_the_transcript_header():
    assert draft().not_elicited == "we ran out of time before the legal side of it"


def test_a_header_that_gives_no_reason_leaves_the_reason_not_stated():
    """Three options to pick the least wrong of would be a reason invented at the card."""
    silent = "\n".join(line for line in TRANSCRIPT.splitlines()
                       if not line.startswith("not elicited:"))
    assert draft(transcript=silent).not_elicited == NOT_STATED


def test_a_transcript_with_no_header_at_all_reaches_no_category():
    bare = standardise("Petra Nolte: MTPD: 8 h.\n", {}, LENSES)
    assert bare.unknown == tuple(LENSES)
    assert bare.not_elicited == NOT_STATED
    assert [(item.speaker, item.value) for item in bare.statements] == [("Petra Nolte", "8 h")], (
        "a transcript with no header is testimony from its first character")


# ── what goes to the record ──────────────────────────────────────────────────


def test_the_proposal_holds_every_string_the_card_will_say():
    proposal = draft().proposal
    assert [item["value"] for item in proposal["evidence"] if item["label"] == "MTPD"] == ["24 h"]
    assert {item["asset_id"] for item in proposal["dependencies"]} == {"KA-01", "KA-02", ""}
    assert proposal["open_items"] == list(draft().open_items)
    assert proposal["not_elicited"] == draft().not_elicited


# ── the same claims over every transcript, not only this one ─────────────────

#: Words a transcript says a thing in. No colon, comma, bracket, digit or newline: those four are
#: the syntax this module reads — a speaker's colon, the separator between two dependencies, the
#: bracket an owner is named in, and the figure a time label needs — so an alphabet without them
#: generates testimony rather than accidental structure.
WORDS = st.text(alphabet="abcdXY Z-", min_size=1, max_size=12).map(str.strip).filter(bool)

#: A duration as the two time labels are said in, in the shapes an interview actually writes:
#: "8 h", "24hrs", "2 weeks". What `_value` must give back is this and never the sentence.
FIGURES = st.builds("{}{}{}".format,
                    st.integers(min_value=0, max_value=99), st.sampled_from((" ", "")),
                    st.sampled_from(("h", "hrs", "hours", "min", "d", "days", "weeks")))

#: An asset id as a register holds one, and the entry it holds under it. The names come from a
#: three-character alphabet on purpose: what a "nearest match" would resolve wrongly is a name that
#: is a prefix, a lengthening or a near-miss of another, and a wide alphabet generates that pair
#: about never. Narrow, and the register and the interview collide by themselves.
IDS = st.text(alphabet="KA-0123456789", min_size=2, max_size=6)
LOOKALIKES = st.text(alphabet="ab ", min_size=1, max_size=4).map(str.strip).filter(bool)
REGISTERS = st.dictionaries(
    IDS, st.builds(lambda name, held: {"name": name, DEPARTMENT: held}, LOOKALIKES, WORDS),
    max_size=3)

#: The method's impact categories, as a room's own method file names them.
LENSES_SAID = st.sampled_from(("financial", "legal-regulatory", "reputational", "operational"))


def spoken(speaker, label, value):
    """One line of testimony: who spoke, what they were asked about, and what they said to it."""
    return f"{speaker}: {label}: {value}"


def transcript(lines=(), header=()):
    """A transcript as a room holds one: front matter, and the testimony under it."""
    return "---\n{}\n---\n\n{}\n".format("\n".join(header), "\n".join(lines))


@given(st.lists(st.tuples(WORDS, st.sampled_from(LABELS), st.one_of(FIGURES, WORDS)), max_size=4))
def test_nothing_is_ever_asserted_that_the_transcript_does_not_hold(said):
    """Every figure on the card is the file's own characters, in the sentence they were said in."""
    lines = [spoken(speaker, label, value) for speaker, label, value in said]
    drafted = standardise(transcript(lines), {}, [])
    assert len(drafted.statements) <= len(lines), "a line stated at most one thing"
    for item in drafted.statements:
        assert item.quote in transcript(lines), "the quote is not the file's own characters"
        assert item.value in item.quote
        assert item.speaker in item.quote


@given(WORDS, st.sampled_from(DURATIONS), WORDS)
def test_a_time_label_with_no_figure_beside_it_asserts_nothing_whatever_was_said(
        speaker, label, said):
    """The v1 defect, stated over every sentence: "RTO: we never settled one" is not a target."""
    assert standardise(transcript([spoken(speaker, label, said)]), {}, []).statements == ()


@given(WORDS, st.sampled_from(DURATIONS), FIGURES, WORDS)
def test_a_time_label_asserts_the_figure_and_not_the_sentence_around_it(
        speaker, label, figure, trailing):
    statement, = standardise(
        transcript([spoken(speaker, label, f"{figure} {trailing}")]), {}, []).statements
    assert (statement.label, statement.value) == (label, figure)
    assert statement.owner_stated == (label in OWNER_STATED), "an RTO is read, never owner-stated"


@given(st.lists(LOOKALIKES, max_size=3), REGISTERS)
def test_no_dependency_ever_resolves_to_an_id_the_register_does_not_hold(heard, register):
    """The graph believes an id. So an id is the register's own or there is none, never a guess."""
    drafted = standardise(transcript([spoken("Torsten Ahlgrim", DEPENDS, ", ".join(heard))]),
                          register, [])
    assert [item.heard for item in drafted.dependencies] == heard
    for item in drafted.dependencies:
        assert item.asset_id in {"", *register}
        assert not item.asset_id or norm(register[item.asset_id]["name"]) == norm(item.heard)


@given(LOOKALIKES, LOOKALIKES, IDS)
def test_a_dependency_resolves_exactly_when_the_register_models_that_very_name(
        heard, modelled, asset_id):
    """The iff the graph rests on, said over the pairs that make it hard: one name a prefix, a
    lengthening or a respacing of the other. Anything short of the same name is no id at all —
    typography may be forgiven (`nemo.text`), a different thing may not."""
    register = {asset_id: {"name": modelled, DEPARTMENT: "Slaughter"}}
    item, = standardise(transcript([spoken("Torsten Ahlgrim", DEPENDS, heard)]),
                        register, []).dependencies
    assert item.asset_id == (asset_id if norm(modelled) == norm(heard) else "")


@given(st.lists(LOOKALIKES, max_size=3), REGISTERS)
def test_a_dependency_with_no_id_is_an_open_item_in_the_words_it_was_heard_in(heard, register):
    """An unmodelled dependency is a finding and not an invention, and it is not a silence either:
    what the human is asked to accept at sign-off is named in their own words, one item each."""
    drafted = standardise(transcript([spoken("Torsten Ahlgrim", DEPENDS, ", ".join(heard))]),
                          register, [])
    unmodelled = [item for item in drafted.dependencies if not item.asset_id]
    assert len(drafted.open_items) == len(unmodelled), "nothing raised that nothing is wrong with"
    for item in unmodelled:
        assert [raised for raised in drafted.open_items if item.heard in raised]


@given(st.lists(LENSES_SAID, unique=True, max_size=4), st.lists(LENSES_SAID, unique=True,
                                                                max_size=4))
def test_only_a_category_the_header_does_not_cover_is_proposed_as_unknown(lenses, covered):
    """In the method's own order: what the interview reached is left alone, and the rest is worst
    case unknown rather than a figure nobody gave."""
    drafted = standardise(transcript(header=[f"{COVERED}: " + ", ".join(covered)]), {}, lenses)
    assert list(drafted.unknown) == [lens for lens in lenses if lens not in covered]
    assert drafted.proposal["worst_case"] == {lens: UNKNOWN for lens in drafted.unknown}


@given(WORDS)
def test_the_reason_is_the_transcripts_own_words_or_the_words_not_stated(reason):
    """Never a fourth thing, and never one of the three options the owner withdrew: why a category
    was not elicited is a property of the transcript, so where it says nothing, so does the card."""
    stated = standardise(transcript(header=[f"{NOT_ELICITED}: {reason}"]), {}, [])
    silent = standardise(transcript(header=[f"{COVERED}: financial"]), {}, [])
    assert stated.not_elicited == reason
    assert silent.not_elicited == NOT_STATED


# ── the grid, and the activities it belongs to (ticket 15) ───────────────────
#
# Stage 4 draws the record out of what stage 3 standardised and never re-reads the transcript, so
# the scores and the activity they belong to are read here, once, beside the figures.

SCORED = TRANSCRIPT + (
    "Torsten Ahlgrim: Impact financial: 0–4 h 2, 8 h 3, 24 h 4, 48 h 5.\n")

FIVE = """---
department: Slaughter
covered: financial
---

# Slaughter interview

## Stunning

Torsten Ahlgrim: MTPD: 8 h for stunning.
Torsten Ahlgrim: Impact financial: 0–4 h 4, 8 h 5.

## Bleeding

Petra Nolte: RTO: 2 h for bleeding.
Petra Nolte: Depends on: ammonia refrigeration.
"""


def test_a_transcript_with_no_headings_is_one_activity_named_by_its_department():
    activity, = draft().activities
    assert activity.name == "Slaughter"
    assert activity.statements == draft().statements


def test_each_heading_under_the_interview_is_an_activity_of_its_own():
    assert [item.name for item in draft(FIVE).activities] == ["Stunning", "Bleeding"]


def test_a_line_belongs_to_the_activity_it_was_said_under():
    stunning, bleeding = draft(FIVE).activities
    assert [item.label for item in stunning.statements] == ["MTPD"]
    assert [item.label for item in bleeding.statements] == ["RTO"]
    assert [item.heard for item in bleeding.dependencies] == ["ammonia refrigeration"]
    assert stunning.dependencies == ()


def test_the_draft_still_reads_as_one_list_across_every_activity():
    """What stage 3's card says is the whole interview, however many activities it covers."""
    drafted = draft(FIVE)
    assert [item.label for item in drafted.statements] == ["MTPD", "RTO"]
    assert [item.heard for item in drafted.dependencies] == ["ammonia refrigeration"]


def test_a_scored_line_becomes_a_row_of_the_grid_in_the_horizons_it_named():
    activity, = draft(SCORED).activities
    assert activity.impact_grid["financial"] == {"0–4 h": 2, "8 h": 3, "24 h": 4, "48 h": 5}


def test_the_score_carries_the_sentence_it_was_said_in():
    score, = draft(SCORED).activities[0].scores
    assert score.lens == "financial"
    assert score.speaker == "Torsten Ahlgrim"
    assert score.quote in SCORED
    assert score.quote.endswith("48 h 5.")


def test_a_category_nobody_scored_is_missing_across_the_horizons_the_others_named():
    """MISSING is what the referee reads as "nobody said", and it is not a zero and not a gap."""
    activity, = draft(SCORED).activities
    assert activity.impact_grid["legal-regulatory"] == {
        horizon: MISSING for horizon in ("0–4 h", "8 h", "24 h", "48 h")}


def test_a_grid_nobody_scored_at_all_names_no_horizon_rather_than_inventing_one():
    activity, = draft().activities
    assert activity.impact_grid == {"financial": {}, "legal-regulatory": {}}


def test_a_cell_that_does_not_say_a_score_is_not_read_as_one():
    """A missed cell leaves a horizon out, which the referee refuses. It is never filled in."""
    activity, = draft(TRANSCRIPT + "T: Impact financial: 0–4 h 2, 8 h later, 24 h 9.\n").activities
    assert activity.impact_grid["financial"] == {"0–4 h": 2}


def test_the_grid_reaches_stage_4_through_the_proposal_and_not_the_transcript():
    """The endorsed proposal is all stage 4 gets: the activity, its grid and the quote behind it."""
    proposed, = draft(SCORED).proposal["activities"]
    assert proposed["name"] == "Slaughter"
    assert proposed["impact_grid"]["financial"]["24 h"] == 4
    assert proposed["scores"][0]["quote"] in SCORED
    assert [item["label"] for item in proposed["evidence"]] == [
        item.label for item in draft(SCORED).activities[0].statements]


@given(st.lists(st.tuples(LENSES_SAID, st.integers(1, 5)), max_size=4, unique_by=lambda p: p[0]))
def test_a_score_is_the_number_the_interview_said_and_only_where_it_said_one(scored):
    lines = [spoken("Torsten Ahlgrim", f"{IMPACT} {lens}", f"8 h {score}")
             for lens, score in scored]
    activity, = standardise(transcript(lines, header=[f"{DEPARTMENT}: Slaughter"]),
                            {}, [lens for lens, _ in scored]).activities
    assert activity.impact_grid == {lens: {"8 h": score} for lens, score in scored}


# ── purity ───────────────────────────────────────────────────────────────────
# "Nothing here reaches the disk, the clock or the network" is this module's first docstring
# paragraph, and until ticket 28 nothing held it to that: the layers contract did not name
# `nemo.evidence` at all, so an import of the package's one socket passed every gate. The contract
# names it now, and the seal below — `nemo.test_purity`'s — says the same thing about the process
# rather than about the imports.


def test_the_transcript_is_standardised_without_reading_anything(seal, tmp_path):
    room = tmp_path / "room"
    room.mkdir()
    for name in ("dependency-register.json", "COMPANY-BIBLE.md", "transcript.md"):
        (room / name).write_text("unrelated", encoding="utf-8")
    seal()
    assert draft().activities


def test_the_proposal_is_built_without_reading_anything(seal):
    seal()
    assert draft().proposal["activities"]


def test_an_open_item_is_raised_without_reading_anything(seal):
    """The unmodelled dependency is the one place evidence is tempted to go looking for an id."""
    seal()
    assert draft().open_items


# ── a comparator beside the figure is part of the figure (t139, F1) ──────────────────────────
@pytest.mark.parametrize("said", [">168 h", "<1 h", "≥ 24 h", "≤ 4 h"])
def test_a_figure_keeps_the_comparator_it_was_stated_with(said):
    """">168 h" is past the last horizon, not 168 h: the reader used to drop the ">" and the card
    said the owner stated 168 h (t138's showcase)."""
    stated = standardise(f"Frerk Sievers: MTPD: {said}.\nFrerk Sievers: RTO: {said}.\n", {}, LENSES)
    assert [(item.label, item.value) for item in stated.statements] == [
        ("MTPD", said), ("RTO", said)]


def test_a_bare_figure_still_reads_bare():
    stated = standardise("Petra Nolte: MTPD: 8 h for stunning, > not a comparator here.\n", {},
                         LENSES)
    assert [item.value for item in stated.statements] == ["8 h"]
