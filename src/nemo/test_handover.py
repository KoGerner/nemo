"""`nemo.handover` on its own: the two documents, the certificate, and who may sign.

The feature steps walk the real stages to get here, which is what makes them worth having and
also what makes them slow to say *one* thing. These say the one thing: a record in, a string out,
and the sentence that would be a lie if the code drifted.
"""

import ast
import json
import re
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo import figures, handover
from nemo.handover import (
    ACTIVITY,
    ASSERTED,
    BOUNDARY,
    BY,
    DRAFT,
    FOUND,
    GAP_ACCOUNT,
    GAP_CLOSED,
    HANDOVER,
    ITEM,
    LABEL,
    NO_FINDINGS,
    NO_METHOD,
    NOT_APPROVAL,
    NOT_NAMED,
    NOTHING_ACCEPTED,
    NOTHING_OPEN,
    NOTHING_RESERVED,
    ON_BEHALF_OF,
    OPEN,
    OWNED_BY,
    OWNER_OF_THE_ACTIVITY,
    READER,
    REQUIREMENTS,
    RESERVATION,
    SIGNED,
    SPONSOR,
    NotAnOwner,
    _found,
    _per_activity,
    capacity,
    categories_said,
    certificate,
    closed_says,
    closed_words,
    closes,
    documents,
    gap_reading,
    gap_says,
    gap_words,
    items,
    owners,
    plain_finding,
    said_plainly,
    upper_edge,
)
from nemo.record import (
    ACCEPTED,
    ACTIVITIES,
    AT_STAGE,
    CAPACITY,
    DECISIONS,
    DEPENDENCIES,
    DEPT,
    FINDINGS,
    GRADIENT,
    IMPACT_GRID,
    MBCO,
    METHOD,
    MTPD,
    NAME,
    NAMING,
    OPEN_ITEMS,
    OWNER,
    RECOVERY_TARGET,
    REFERRALS,
    REFERRED_TO,
    REFERS,
    ROLE,
    RPO,
    SIGNATURE,
    SIGNER,
    UNNAMED,
)
from nemo.text import norm

METHOD_HELD = {"scenarios": [{"id": "financial", "name": "Financial"}],
               "time_horizons": ["0–4 h", "24 h"],
               "severity_scale": [{"level": 4, "label": "major"}],
               "intolerability_threshold": 4}

RECORD = {
    DEPT: "Slaughter",
    METHOD: METHOD_HELD,
    OPEN_ITEMS: ["the sticking-pen conveyor is not in your register"],
    ACTIVITIES: [{"name": "Slaughter", OWNER: "Torsten Ahlgrim", "mtpd": "24 h",
                  "impact_grid": {"financial": {"0–4 h": 2, "24 h": 4}},
                  "dependencies": ["KA-01"], "recovery_target": "8 h", "rpo": "4 h"}],
}

RUN = {"decisions": [{"stage": 3, "gradient": "endorsed with reservations",
                      "naming": "Torsten gave me 6 h for that line last week, not 8"}],
       "findings": ["the grid's worst case improves with time"]}


def test_the_handover_says_on_its_face_what_it_is_and_who_it_is_for():
    said = documents(RECORD, RUN)[HANDOVER]
    assert LABEL in said and READER in said and NO_METHOD in said


def test_the_management_bia_is_not_the_handover_and_neither_is_labelled_as_the_other():
    both = documents(RECORD, RUN)
    assert set(both) == {DRAFT, HANDOVER}
    assert LABEL not in both[DRAFT], "the management BIA claims to be the handover"


def test_a_reservation_reaches_both_documents_in_the_words_it_was_typed_in():
    for said in documents(RECORD, RUN).values():
        assert RUN["decisions"][0]["naming"] in said


def test_a_reservation_nobody_named_is_carried_as_unnamed_and_not_as_agreement():
    run = {"decisions": [{"stage": 3, "gradient": "needs discussion", "naming": UNNAMED}]}
    said = documents(RECORD, run)[HANDOVER]
    assert "recorded and never named" in said
    assert NOTHING_RESERVED not in said


def test_a_walk_that_reserved_nothing_says_so_rather_than_leaving_the_section_out():
    assert NOTHING_RESERVED in documents(RECORD, {})[HANDOVER]


def test_the_referee_findings_reach_the_handover_in_the_words_they_were_raised_in():
    assert RUN["findings"][0] in documents(RECORD, RUN)[HANDOVER]


def test_a_referral_to_the_risk_assessment_says_what_it_refers_and_to_whom():
    referring = {**RECORD, REFERRALS: [{"refers": "the ammonia leak scenario",
                                        "to": "the risk assessment owner"}]}
    said = documents(referring, RUN)[HANDOVER]
    assert "the ammonia leak scenario" in said and "the risk assessment owner" in said


def test_an_open_item_is_numbered_where_it_stands_so_two_renders_name_it_alike():
    assert items(RECORD, RUN) == items(RECORD, RUN)
    assert [at for at, _text in items(RECORD, RUN)] == ["OPEN-1", "OPEN-2"]


def test_a_record_that_left_nothing_open_says_so_rather_than_showing_an_empty_list():
    assert NOTHING_OPEN in documents({**RECORD, OPEN_ITEMS: []}, {})[HANDOVER]


def test_the_owner_the_record_holds_is_who_a_closing_signature_has_to_come_from():
    assert owners(RECORD) == ("Torsten Ahlgrim",)
    assert capacity(RECORD, "torsten  ahlgrim") == OWNER_OF_THE_ACTIVITY


def test_a_signer_who_is_not_the_owner_is_recorded_as_what_they_are():
    assert capacity(RECORD, "Petra Nolte") == SPONSOR


def test_a_role_that_calls_itself_the_owner_does_not_make_the_signer_one():
    """v1's defect, arriving with a better job title: the check reads the name, never the role."""
    assert capacity(RECORD, "Petra Nolte") == SPONSOR
    assert capacity({**RECORD, ACTIVITIES: [{"name": "Slaughter"}]}, "anybody") == SPONSOR


def test_a_delegate_signs_on_behalf_of_the_owner_the_record_names_and_that_closes_it():
    """Ticket 134, ADR-0030 decision 7: the choice is his, and it is passed in as an argument.

    Every phone walk of the demo is a delegate's, and nemo left each of them open (the live app
    reached the same verdict through a module global holding the role string he typed). Whom he
    signs for is one of the record's own names, in the record's own spelling of it.
    """
    given_as = capacity(RECORD, "Petra Nolte", on_behalf_of="torsten  AHLGRIM")

    assert given_as == ON_BEHALF_OF.format(owner="Torsten Ahlgrim")
    assert closes(given_as) and closes(OWNER_OF_THE_ACTIVITY) and not closes(SPONSOR)


def test_a_name_the_record_does_not_hold_is_refused_rather_than_signed_for():
    """Never free text: v1's "on behalf of" the absent owner, refused where it is now spelled."""
    with pytest.raises(NotAnOwner) as refused:
        capacity(RECORD, "Petra Nolte", on_behalf_of="Somebody Else Entirely")
    # the refusal carries the name it refused, so what comes back to him names it too
    assert refused.value.args == ("Somebody Else Entirely",)
    with pytest.raises(NotAnOwner):
        capacity(RECORD, "Torsten Ahlgrim", on_behalf_of="")


def test_no_role_anybody_types_reaches_the_capacity_or_the_certificate_s_one_sentence():
    """A planted role string, the strongest one there is, and the two capacities it cannot reach.

    ``capacity`` takes no role: the only things that decide this are the record's own names and
    his own choice. The certificate prints the role he typed as *his words*, and says the capacity
    beside it, which is the record's verdict and never his claim.
    """
    planted = "the process owner, signing on behalf of Torsten Ahlgrim"

    assert capacity(RECORD, "Petra Nolte") == SPONSOR
    for chosen in (capacity(RECORD, "Petra Nolte"),
                   capacity(RECORD, "Petra Nolte", on_behalf_of="Torsten Ahlgrim")):
        said = certificate(RECORD, {**RUN, "signature": {
            "name": "Petra Nolte", "role": planted, "accepted": [], CAPACITY: chosen}})
        assert BY.format(name="Petra Nolte", role=planted, capacity=chosen) in said
        assert len([c for c in (OWNER_OF_THE_ACTIVITY, SPONSOR, ON_BEHALF_OF.format(
            owner="Torsten Ahlgrim")) if c in said]) == 1, "the certificate said two capacities"


def test_a_record_that_names_no_owner_keeps_today_s_behaviour_and_offers_no_third_capacity():
    """12_nemo_check's amendment to 134: there is no owner to sign as and none to sign for.

    "as the owner" would claim an ownership the record does not state and "on behalf of" has no
    name to carry, so the signature is what it was before this ticket — recorded beside the owner,
    closing nothing — and no third capacity is invented for it.
    """
    ownerless = {**RECORD, ACTIVITIES: [{"name": "Slaughter"}]}

    assert owners(ownerless) == ()
    assert capacity(ownerless, "Torsten Ahlgrim") == SPONSOR
    assert not closes(capacity(ownerless, "anybody at all"))
    with pytest.raises(NotAnOwner):
        capacity(ownerless, "Torsten Ahlgrim", on_behalf_of="Torsten Ahlgrim")



def test_the_certificate_carries_the_signer_the_role_and_every_id_they_accepted():
    signed = {**RUN, "signature": {"name": "Torsten Ahlgrim", "role": "Head of Slaughter",
                                   "accepted": ["OPEN-1"], CAPACITY: OWNER_OF_THE_ACTIVITY}}
    said = certificate(RECORD, signed)
    assert "Torsten Ahlgrim" in said and "Head of Slaughter" in said
    assert "OPEN-1 — the sticking-pen conveyor is not in your register" in said
    assert "OPEN-2" not in said, "an item nobody accepted was written up as accepted"
    assert ASSERTED in said and NOT_APPROVAL in said


def test_the_certificate_never_says_an_identity_was_confirmed_checked_or_verified():
    signed = {**RUN, "signature": {"name": "Torsten Ahlgrim", "role": "owner", "accepted": []}}
    said = certificate(RECORD, signed).replace(ASSERTED, "")
    for stronger in ("confirmed", "verified", "checked", "authenticated", "by email"):
        assert stronger not in said.lower(), stronger


def test_nothing_here_says_room():
    for said in (*documents(RECORD, RUN).values(), certificate(RECORD, RUN)):
        assert "room" not in said.lower()


# ── the documents as bytes: the headings, the sections, and what joins them ──
#
# Everything above asks whether a sentence is *somewhere* in a document, and a document is not a
# set of sentences: a finding that reached the open-items list and not the section that says what
# the check found is still findable by `in`. These ask where each sentence lands, which is what a
# manager reads.


def section(said, heading):
    """What one document says under one of its headings, and nothing from the next one."""
    _before, found, after = said.partition(heading + "\n\n")
    assert found, f"the document has no section under {heading!r}"
    return after.split("\n\n## ")[0]


def test_each_document_is_headed_for_the_department_the_record_is_about():
    both = documents(RECORD, RUN)
    assert both[DRAFT].startswith("# The BIA for Slaughter\n\n")
    assert both[HANDOVER].startswith("# Requirements handover — Slaughter\n\n")


def test_a_record_that_names_no_department_heads_them_with_nothing_rather_than_a_word():
    """The default is the empty string, so an absent department is absent rather than *None*."""
    nameless = {name: held for name, held in RECORD.items() if name != DEPT}
    both = documents(nameless, RUN)

    assert both[DRAFT].startswith("# The BIA for \n\n")
    assert both[HANDOVER].startswith("# Requirements handover — \n\n")


def test_each_document_ends_on_the_decision_boundary_and_on_one_newline():
    """Markdown a manager scrolls to the end of: the boundary last, and nothing after it."""
    for said in (*documents(RECORD, RUN).values(), certificate(RECORD, RUN)):
        assert said.endswith("\n") and not said.endswith("\n\n")
    for said in documents(RECORD, RUN).values():
        assert said.endswith(BOUNDARY + "\n")


def test_the_activity_is_headed_by_its_own_name_and_by_who_the_record_has_owning_it():
    said = documents(RECORD, RUN)[HANDOVER]
    requirements = section(said, "## The continuity requirements, activity by activity")

    assert requirements.startswith(ACTIVITY.format(activity="Slaughter"))
    assert OWNED_BY.format(owner="Torsten Ahlgrim", activity="this activity") in requirements


def test_what_the_check_found_is_said_under_the_heading_that_asks_what_it_found():
    """A finding is carried twice — as an open item and as what the check found — and the section
    that says what the check found must be the one that says it, never *nothing to raise*."""
    said = documents(RECORD, RUN)[HANDOVER]

    assert section(said, FOUND) == RUN["findings"][0]
    assert NO_FINDINGS not in said


def test_a_check_that_raised_nothing_says_so_under_that_same_heading():
    assert section(documents(RECORD, {})[HANDOVER], FOUND) == NO_FINDINGS


def test_the_certificate_is_headed_for_the_department_and_says_the_signature_in_one_sentence():
    signed = {**RUN, "signature": {"name": "Torsten Ahlgrim", "role": "Head of Slaughter",
                                   "accepted": [], CAPACITY: OWNER_OF_THE_ACTIVITY}}

    said = certificate(RECORD, signed)

    assert said.startswith(SIGNED.format(dept="Slaughter") + "\n\n")
    assert BY.format(name="Torsten Ahlgrim", role="Head of Slaughter",
                     capacity=OWNER_OF_THE_ACTIVITY) in said


def test_a_certificate_with_nothing_filled_in_says_nothing_rather_than_a_placeholder():
    """Every default here is the empty string: a missing field leaves a gap, never a word."""
    nameless = {name: held for name, held in RECORD.items() if name != DEPT}

    said = certificate(nameless, {**RUN, "signature": {}})

    assert said.startswith(SIGNED.format(dept="") + "\n\n")
    assert BY.format(name="", role="", capacity="") in said


# ── the same three documents, over records and runs nobody chose ─────────────
#
# Everything above renders one hand-built record, and a hand-built record is a record somebody
# chose — the same objection `nemo.test_views`' property section is written against. The documents
# stage 5 hands over are pure functions of two records, so they can be handed records nobody
# arranged: walks that reserved something at every card and walks that reserved nothing, records
# that left ten things open and records that left none, activities somebody owns and activities
# the interview left owner-less. The story's "every reservation and contradiction from every
# earlier gradient answer is carried onto them" is a claim about all of them and is stated as one.

#: Short words from an alphabet that cannot spell "room", "approved" or a comma — so a property
#: may ask whether a document says one of those without a generated word being able to say it for
#: the module. The band is stated rather than left to chance: the profile is derandomized
#: (`conftest.py`), so a strategy that only *could* offer an interesting value may never offer it.
WORDS = st.text(alphabet="abc de-", min_size=1, max_size=8).map(str.strip).filter(bool)

#: The people a record can have owning an activity, and the spellings a signer can type one in.
#: The variants are what `nemo.text.norm` forgives and nothing more — case, spacing, and the
#: markdown a word processor wraps a name in — because the authority check rests on that
#: normalizer and on nobody re-implementing it.
PEOPLE = ["Torsten Ahlgrim", "Petra Nolte", "Bo Ødegård"]
SIGNERS = st.sampled_from([*PEOPLE, *(name.upper() for name in PEOPLE),
                           *(f"  {name.replace(' ', '  ')} " for name in PEOPLE),
                           *(f"*{name}*" for name in PEOPLE)]) | WORDS

BANDS = ["0–4 h", "24 h"]
CELLS = st.sampled_from([1, 4, "MISSING"])

#: An activity as the record carries one: a grid, the four figures present or absent, and an owner
#: the interview either put a name to or did not.
ACTIVITY_ST = st.fixed_dictionaries({
    NAME: st.sampled_from(["Stunning", "Chilling", "Boning", "Dispatch"]),
    OWNER: st.just("") | st.sampled_from(PEOPLE),
    IMPACT_GRID: st.fixed_dictionaries(
        {"financial": st.fixed_dictionaries(dict.fromkeys(BANDS, CELLS))}),
    MTPD: st.none() | st.sampled_from(BANDS),
    RECOVERY_TARGET: st.none() | WORDS,
    RPO: st.none() | WORDS,
    MBCO: st.none() | WORDS,
    DEPENDENCIES: st.lists(st.sampled_from(["KA-01", "KA-02"]), max_size=2, unique=True),
})

RECORDS = st.fixed_dictionaries({
    DEPT: WORDS,
    METHOD: st.just(METHOD_HELD),
    OPEN_ITEMS: st.lists(WORDS, max_size=3),
    REFERRALS: st.lists(st.fixed_dictionaries({REFERS: WORDS, REFERRED_TO: WORDS}), max_size=2),
    ACTIVITIES: st.lists(ACTIVITY_ST, min_size=1, max_size=3,
                         unique_by=lambda activity: activity[NAME]),
})

#: A decision as a card leaves one: endorsed and carrying no reservation, or answered some other
#: way and carrying what was reserved — in words, or as the unnamed one nobody came back to name.
DECISION_ST = st.fixed_dictionaries({AT_STAGE: st.sampled_from([1, 2, 3, 4]),
                                     GRADIENT: st.just("endorsed")}) | st.fixed_dictionaries({
    AT_STAGE: st.sampled_from([1, 2, 3, 4]),
    GRADIENT: st.sampled_from(["endorsed with reservations", "needs discussion", "blocked"]),
    NAMING: WORDS | st.just(UNNAMED)})

RUNS = st.fixed_dictionaries({DECISIONS: st.lists(DECISION_ST, max_size=4),
                              FINDINGS: st.lists(WORDS, max_size=3)})


def reserved(run):
    """Every reservation this run carries, in the sentence the handover has to carry it in."""
    return [(NOT_NAMED if decision[NAMING] == UNNAMED else RESERVATION).format(
        stage=decision[AT_STAGE], gradient=decision[GRADIENT], naming=decision[NAMING])
        for decision in run[DECISIONS] if NAMING in decision]


@given(RECORDS, RUNS)
def test_rendering_is_a_function_of_the_two_records_bytes_and_of_nothing_else(record, run):
    """Same bytes in, same documents out — with a JSON round trip between, so it is the bytes.

    The claim the story makes about these documents is that they are rendered *from the record*.
    Nothing here reads a clock, a folder or a transcript, so two renders an hour apart are the
    same bytes and a manager's handover cannot drift away from the record while a file is edited
    underneath it.
    """
    again = json.loads(json.dumps([record, run]))

    assert documents(record, run) == documents(*again)
    assert certificate(record, run) == certificate(*again)


@given(RECORDS, RUNS)
def test_every_reservation_from_every_earlier_answer_reaches_both_documents(record, run):
    """The done-when, over walks nobody arranged: every gradient answer that reserved something.

    Both documents, in the whole sentence rather than in a word of it, because a reservation that
    reached the management BIA and not the handover is one the reader designing the solution never
    sees. A walk that reserved nothing says so, which is the other half: a section silently left
    out reads as one nobody thought about.
    """
    carried = reserved(run)

    for said in documents(record, run).values():
        for sentence in carried:
            assert sentence in said
        assert (NOTHING_RESERVED in said) == (carried == [])


@given(RECORDS, RUNS)
def test_everything_still_open_is_numbered_once_and_carried_onto_both_documents(record, run):
    """What the walk left open and what the check found, each under the id the signature uses.

    One id per item, no id for an item that does not exist, and the ids are a function of the two
    records — which is what lets the signature accept them by id hours later without anything
    having been stored to reproduce them.
    """
    at = items(record, run)
    texts = [*record[OPEN_ITEMS], *run[FINDINGS]]

    assert [identifier for identifier, _text in at] == [
        f"OPEN-{number}" for number in range(1, len(texts) + 1)]
    assert [text for _id, text in at] == texts
    for said in documents(record, run).values():
        for identifier, text in at:
            assert ITEM.format(id=identifier, text=text) in said
        assert (NOTHING_OPEN in said) == (at == ())


@given(RECORDS, RUNS)
def test_the_handover_says_what_it_is_and_the_management_bia_never_claims_to_be_it(record, run):
    """Whatever is in them: labelled a requirements handover, and not approved."""
    both = documents(record, run)

    assert all(sentence in both[HANDOVER] for sentence in (LABEL, READER, NO_METHOD))
    assert LABEL not in both[DRAFT]
    for said in both.values():
        assert "approved" not in said.replace(LABEL, ""), "a document called itself approved"
        assert "room" not in said.lower()


@given(RECORDS, RUNS, SIGNERS, WORDS, st.lists(st.sampled_from(["OPEN-1", "OPEN-2"]), max_size=2))
def test_the_certificate_says_who_signed_what_they_accepted_and_nothing_stronger(
        record, run, name, role, accepting):
    """Every certificate, for every signature: the ids accepted and the one identity sentence.

    An id nobody accepted is absent rather than softened into one they did, and no certificate
    this product can render says anything stronger than *identity asserted in session, not
    verified* — because nothing anywhere in it captures an email, so there is nothing stronger it
    could truthfully say (corrected 2026-09-14).
    """
    signed = {**run, "signature": {SIGNER: name, ROLE: role, ACCEPTED: accepting,
                                   CAPACITY: capacity(record, name)}}
    said = certificate(record, signed)

    for identifier, text in items(record, run):
        assert (ITEM.format(id=identifier, text=text) in said) == (identifier in accepting)
    assert (NOTHING_ACCEPTED in said) == (
        not any(identifier in accepting for identifier, _text in items(record, run)))
    assert ASSERTED in said and NOT_APPROVAL in said
    for stronger in ("confirmed", "verified", "checked", "authenticated", "by email"):
        assert stronger not in said.replace(ASSERTED, "").lower(), stronger
    assert "room" not in said.lower()


@given(RECORDS, SIGNERS)
def test_whom_a_delegate_may_sign_for_is_exactly_whom_the_record_holds(record, name):
    """The property: the record's own names, and nothing else, whatever anybody passes in."""
    for owner in owners(record):
        assert capacity(record, name, on_behalf_of=owner) == ON_BEHALF_OF.format(owner=owner)
    if not any(norm(name) == norm(owner) for owner in owners(record)):
        with pytest.raises(NotAnOwner):
            capacity(record, "anybody", on_behalf_of=name)


@given(RECORDS, SIGNERS)
def test_a_signature_closes_this_only_for_the_name_the_record_itself_holds(record, name):
    """The authority check, stated as the property v1 failed: the name, and never the role.

    ``capacity`` cannot read a role — it is not an argument — so no job title a signer types can
    turn this verdict over, which is exactly v1's defect arriving with a better one. What it does
    forgive is typography, and only what ``nemo.text.norm`` forgives: a name in capitals or double
    spaces is the same person, and a different person is never the same person.
    """
    held = {norm(owner) for owner in owners(record)}

    assert capacity(record, name) == (OWNER_OF_THE_ACTIVITY if norm(name) in held else SPONSOR)
    assert capacity(record, name) in (OWNER_OF_THE_ACTIVITY, SPONSOR)


@given(RECORDS)
def test_a_record_that_owns_nothing_has_nobody_who_can_close_it(record):
    """An activity the interview left owner-less is not a sixth stage: it is a run nobody closes.

    ``owners`` names each person once and in the record's own order, so the card that says whose
    signature closes this says it in the order the record does and never says one of them twice.
    """
    named = owners(record)
    stated = [activity[OWNER] for activity in record[ACTIVITIES] if activity[OWNER]]

    assert named == tuple(dict.fromkeys(stated))
    assert all(name in stated for name in named)
    if not named:
        assert capacity(record, "anybody at all") == SPONSOR


@given(RECORDS, RUNS)
def test_every_figure_these_documents_state_is_a_sentence_the_record_holds(record, run):
    """The v1 defect, asked across the layer boundary rather than inside one module (ADR-0030, 5).

    v1's closed package said MTPD `24 h` in the record, `8 h` in the handover and `0–4 hours` in
    the worksheet, and nothing compared them. The figures in these two documents are
    ``nemo.figures``' sentences over the record, said plainly — the activity named once in its
    heading and "this activity" after it, a category by its method's name (t64) — so each one is
    the record's figure in the record's sentence, and the same in both documents. Said the way the
    code before t64 said them, they are ``nemo.figures``' sentences word for word.
    """
    both = documents(record, run)
    before = documents(record, run, plainly=False)

    for activity in record[ACTIVITIES]:
        said = figures.requirements(activity, record[METHOD])
        assert said, "the activity stated no requirement at all, so this proves nothing"
        for sentence in said:
            for name, text in both.items():
                assert said_plainly(sentence, activity[NAME], record[METHOD]) in text, \
                    f"{name} states a figure in words of its own"
            for text in before.values():
                assert sentence in text, "the wording before t64 lost a figure sentence"


# ── the signed sentences he approved, in their words (ticket 133, ADR-0030 decision 5) ──
#
# The live app wrote these through a runtime patch over this module (t64, t71, t75, t76, t79 fix 1)
# and he walked and ruled on them there. They are this module's now, so these pin them by the words
# themselves: a rewording is a change to what he signs, and it goes red here first.

GAPPED = {NAME: "Slaughter", OWNER: "Torsten Ahlgrim", MTPD: "8 h", RECOVERY_TARGET: "12 h",
          RPO: "4 h", "recovery_gap_flagged": True}


def requirements_of(record):
    """The requirements section of the handover, one sentence per paragraph."""
    return section(documents(record, {})[HANDOVER], REQUIREMENTS).split("\n\n")


def test_the_activity_is_named_once_in_its_heading_and_this_activity_after_it():
    assert requirements_of(RECORD) == [
        "### Slaughter",
        "The record has Torsten Ahlgrim stating this activity's own figures, so this activity is "
        "theirs.",
        "Your interview puts the longest this activity can be down at 24 h, and the grid was read "
        "beside it rather than instead of it.",
        "Your grid for this activity first reaches the level your method calls intolerable under "
        "Financial, and it reaches it at 24 h, so the longest this activity can be down before "
        "that becomes unacceptable stands at 24 h.",
        "No data set is named for this activity in this BIA, so what stands below stands for the "
        "activity as a whole rather than for one set of its data.",
        "For this activity: the recovery target is 8 h, and the recovery point is 4 h.",
        "The minimum acceptable service for this activity is not established.",
        "The minimum resources over time for this activity were not established, so this document "
        "names none rather than one nobody wrote down.",
        "This activity depends on KA-01, by the ids your dependency register holds for them.",
    ]


def test_a_category_is_said_by_its_method_name_but_never_inside_somebodys_quoted_words():
    method = {"scenarios": [{"id": "financial", "name": "Financial loss"}]}
    assert categories_said("under financial, “financial” as he said", method) == \
        "under Financial loss, “financial” as he said"
    assert categories_said("under financial-ish", method) == "under financial-ish"
    assert categories_said("under financial", None) == "under financial"


def test_a_gap_whose_target_is_outside_its_mtpd_says_so_and_that_he_acknowledged_it():
    assert gap_says(GAPPED) == (
        "Slaughter's recovery target 12 h is not inside its MTPD of 8 h: a recovery gap, "
        "acknowledged by the manager and handed to solution design as a known exposure.")
    assert requirements_of({ACTIVITIES: [GAPPED]})[-1] == (
        "This activity's recovery target 12 h is not inside its MTPD of 8 h: a recovery gap, "
        "acknowledged by the manager and handed to solution design as a known exposure.")


def test_a_gap_on_figures_that_put_the_target_inside_says_his_acknowledgement_only():
    inside = {**GAPPED, RECOVERY_TARGET: "4 h", GAP_ACCOUNT: "Torsten Ahlgrim"}
    assert requirements_of({ACTIVITIES: [inside]})[-1] == (
        "For this activity the manager acknowledged a recovery gap on Torsten Ahlgrim's account, "
        "handed to solution design as a known exposure; the recovery target 4 h is inside its "
        "MTPD of 8 h.")


def test_a_gap_on_figures_that_cannot_be_compared_says_the_figures_as_carried():
    carried = {**GAPPED, RECOVERY_TARGET: "as soon as possible"}
    assert gap_reading(carried) is None
    assert requirements_of({ACTIVITIES: [carried]})[-1] == (
        "For this activity the manager acknowledged a recovery gap, handed to solution design as "
        "a known exposure; the record carries recovery target as soon as possible, MTPD 8 h.")


def test_a_gap_he_closed_is_said_in_his_own_words_which_are_never_reworded():
    closed = {**GAPPED, "recovery_gap_flagged": False, RECOVERY_TARGET: "4 h",
              GAP_CLOSED: "Slaughter now runs on the spare line within 4 h"}
    assert requirements_of({ACTIVITIES: [closed]})[-1] == (
        "For Slaughter the record carries a recovery gap he closed: he recorded, in his own words, "
        "that the arrangements can now meet the recovery target — “Slaughter now runs on the "
        "spare line within 4 h”.")


def test_a_band_mtpd_is_read_at_its_upper_edge():
    assert upper_edge("0–4 h") == "4 h" and upper_edge("0-4 hours (the grid)") == "4 hours"
    assert upper_edge("4 h") is None and upper_edge("0–4 fortnights") is None
    assert upper_edge(None) is None
    assert gap_reading({MTPD: "0–4 h", RECOVERY_TARGET: "6 h"}) is True
    assert gap_reading({MTPD: "0–4 h", RECOVERY_TARGET: "2 h"}) is False
    assert gap_reading({MTPD: "4 h", RECOVERY_TARGET: "4 h"}) is True
    assert gap_reading({RECOVERY_TARGET: "4 h"}) is None


@pytest.mark.parametrize("target, outside", [("2-6 hours", True), ("2–4 h", True),
                                             ("2-3 h", False), ("3 h", False), ("4 h", True)])
def test_a_banded_target_is_read_at_its_upper_edge_against_the_mtpd(target, outside):
    """ADR-0039 (ticket 240): the signed gap sentence says outside where the worst case is."""
    assert gap_reading({MTPD: "4 h", RECOVERY_TARGET: target}) is outside


def test_both_past_the_last_horizon_is_inside_by_the_referee_s_own_rule():
    """t156, merged into nemo's reading: an RTO and an MTPD that are both the method's word past
    the last horizon are inside; against a finite MTPD, or with a method that has no such word,
    the target is still outside."""
    beyond = {"beyond_horizons": ">168 h"}
    both = {**GAPPED, RECOVERY_TARGET: ">168 h", MTPD: ">168 h"}
    assert gap_reading(both, beyond) is False
    assert gap_reading({**both, MTPD: "72 h"}, beyond) is True
    assert gap_reading(both) is True and gap_reading(both, {}) is True
    assert gap_says(both, beyond).endswith("target >168 h is inside its MTPD of >168 h.")
    assert gap_words(both, beyond).endswith("with the target inside the MTPD")
    assert requirements_of({ACTIVITIES: [both], "method": beyond})[-1] == (
        "For this activity the manager acknowledged a recovery gap, handed to solution design as a "
        "known exposure; the recovery target >168 h is inside its MTPD of >168 h.")


def test_the_figure_line_carries_the_gap_in_a_few_words():
    assert gap_words(GAPPED) == "a recovery gap, acknowledged, with the target not inside the MTPD"
    assert gap_words({**GAPPED, RECOVERY_TARGET: "soon", GAP_ACCOUNT: "Petra Nolte"}) == \
        "a recovery gap, acknowledged on Petra Nolte's account"
    assert closed_words({GAP_CLOSED: "done"}) == \
        "a recovery gap he closed, in his own words: “done”"
    assert closed_says({NAME: "Chilling", GAP_CLOSED: "done"}).startswith(
        "For Chilling the record carries a recovery gap he closed")


REUSED = ("Human decisions: activity A0 — the same quote is the evidence for "
          "['financial', 'customer-delivery']. Confirm it, or record "
          '{"shared_quote_ack": {"lenses": ["financial", "customer-delivery"]}}')
SAID_PLAINLY = ("Human decisions: one quote is the only evidence for 2 impact categories "
                "(Financial; customer-delivery). A person has to confirm that it supports each of "
                "them; accepting this item at the signature is that confirmation.")


def test_the_shared_quote_finding_is_said_in_words_wherever_an_open_item_is_said():
    run = {FINDINGS: [REUSED]}
    assert plain_finding(REUSED, METHOD_HELD) == SAID_PLAINLY
    assert plain_finding("anything else", METHOD_HELD) == "anything else"
    assert plain_finding(REUSED.replace("['financial'", "[financial"), METHOD_HELD) == \
        REUSED.replace("['financial'", "[financial")
    assert items(RECORD, run)[-1] == ("OPEN-2", SAID_PLAINLY)
    said = documents(RECORD, run)[HANDOVER]
    assert ITEM.format(id="OPEN-2", text=SAID_PLAINLY) in section(said, OPEN)
    # t196: what the check found reads the method the RECORD holds, the one he signs, so this
    # section and the open-items list above say the categories one way. Until t196 it read the
    # run's, as the live app did (t133 kept that byte-identical), and a run that carries none —
    # the usual case — said a category by its id here and by its name there.
    assert section(said, FOUND) == SAID_PLAINLY
    assert section(documents(RECORD, {**run, METHOD: METHOD_HELD})[HANDOVER], FOUND) == SAID_PLAINLY
    assert "shared_quote_ack" not in said
    signed = {**run, SIGNATURE: {ACCEPTED: ["OPEN-2"]}}
    assert ITEM.format(id="OPEN-2", text=SAID_PLAINLY) in certificate(RECORD, signed)


def test_both_sections_say_the_shared_quote_finding_by_the_method_he_signs():
    """t196 (169 folded in): the run usually carries no method, and both the live section and the
    open-items list say the finding's categories by the **record's** method — the one he signs —
    so one document never names a category by its id in one section and by its name in the other.
    """
    run = {FINDINGS: [REUSED]}
    said = documents(RECORD, run)[HANDOVER]
    assert section(said, FOUND) == SAID_PLAINLY
    assert ITEM.format(id="OPEN-2", text=SAID_PLAINLY) in section(said, OPEN)


def test_a_run_carrying_another_method_is_still_said_by_the_records_own():
    """Where the two differ, the record's wins in both sections: what he signs is the record."""
    other = {"scenarios": [{"id": "financial", "name": "Money"},
                           {"id": "customer-delivery", "name": "Deliveries"}]}
    said = documents(RECORD, {FINDINGS: [REUSED], METHOD: other})[HANDOVER]
    assert section(said, FOUND) == SAID_PLAINLY
    assert "Money" not in said and "Deliveries" not in said


def test_a_record_holding_no_method_says_the_finding_by_the_runs_one_in_both_sections():
    """Nothing is lost where the record holds none: both sections fall back together, so they
    still say it one way."""
    record = {k: v for k, v in RECORD.items() if k != METHOD}
    said = documents(record, {FINDINGS: [REUSED], METHOD: METHOD_HELD})[HANDOVER]
    assert section(said, FOUND) == SAID_PLAINLY
    assert ITEM.format(id="OPEN-2", text=SAID_PLAINLY) in section(said, OPEN)
    both = documents(record, {FINDINGS: [REUSED]})[HANDOVER]
    assert section(both, FOUND) == SAID_PLAINLY.replace("(Financial;", "(financial;")


def test_the_wording_before_t64_is_still_rendered_so_a_handover_on_file_is_recognised():
    """t64 fix 1: an accepted, unsigned handover on file in the old words is known for that."""
    run = {FINDINGS: [REUSED]}
    before = documents({**RECORD, ACTIVITIES: [GAPPED]}, run, plainly=False)[HANDOVER]
    assert section(before, FOUND) == REUSED
    assert section(before, REQUIREMENTS).split("\n\n")[1:2] == [
        OWNED_BY.format(owner="Torsten Ahlgrim", activity="Slaughter")]
    assert gap_says(GAPPED) in before


def test_the_longest_category_id_is_said_first_so_a_shorter_one_never_splits_it():
    method = {"scenarios": [{"id": "fin", "name": "F"}, {"id": "fin loss", "name": "FL"},
                            {"name": "an unnamed id is skipped"}]}
    assert categories_said("under fin loss and fin", method) == "under FL and F"


def test_this_activity_opens_every_sentence_it_starts_and_a_nameless_line_is_left_alone():
    assert said_plainly("Done. Slaughter runs; Slaughter's too, not Slaughterhouse",
                        "Slaughter", None) == \
        "Done. This activity runs; This activity's too, not Slaughterhouse"
    assert said_plainly("Slaughter under financial", "", METHOD_HELD) == \
        "Slaughter under Financial"


def test_a_name_inside_a_longer_word_is_left_alone_and_the_whole_word_is_still_said_plainly():
    """The name is swapped only as a whole word, with '-' a word character like a letter."""
    assert said_plainly("order-picking-station feeds order-picking", "order-picking", None) == \
        "order-picking-station feeds this activity"
    assert said_plainly("Kühlung's line, not Kühlungsanlage, and Kühlung runs", "Kühlung",
                        None) == \
        "This activity's line, not Kühlungsanlage, and this activity runs"


def test_the_readings_a_gap_sentence_rests_on_at_their_edges():
    assert upper_edge("0–4 H") == "4 h"
    assert gap_reading({MTPD: "4 h"}) is None
    assert gap_says({NAME: "Chilling", "recovery_gap_flagged": True}) == (
        "For Chilling the manager acknowledged a recovery gap, handed to solution design as a "
        "known exposure; the record carries recovery target —, MTPD —.")
    assert gap_words({**GAPPED, RECOVERY_TARGET: "4 h"}) == \
        "a recovery gap, acknowledged, with the target inside the MTPD"


def test_a_finding_is_said_by_the_runs_method_where_the_record_carries_none():
    record = {name: held for name, held in RECORD.items() if name != METHOD}
    assert items(record, {FINDINGS: [REUSED], METHOD: METHOD_HELD})[-1][1] == SAID_PLAINLY
    before = documents(RECORD, {FINDINGS: [REUSED]}, plainly=False)[HANDOVER]
    assert ITEM.format(id="OPEN-2", text=REUSED) in section(before, OPEN)


def test_the_requirements_are_said_plainly_unless_the_wording_before_t64_is_asked_for():
    """Said plainly (t64) is what these documents say: the activity named in full once, in its
    heading, and "this activity" after it. The wording before t64 is the one a caller asks for."""
    assert _per_activity(RECORD)[1] == OWNED_BY.format(
        owner="Torsten Ahlgrim", activity="this activity")
    assert _per_activity(RECORD, plainly=False)[1] == OWNED_BY.format(
        owner="Torsten Ahlgrim", activity="Slaughter")


def test_what_the_check_found_is_said_in_words_unless_the_wording_before_t64_is_asked_for():
    """The findings section, the same way: said in words (t64) by the method the run carries, and
    the referee's own JSON-tailed sentence only where the older wording is asked for."""
    run = {FINDINGS: [REUSED], METHOD: METHOD_HELD}
    assert _found(RECORD, run) == [SAID_PLAINLY]
    assert _found(RECORD, run, False) == [REUSED]


def test_an_activity_the_record_holds_no_name_for_has_its_sentences_left_as_typed():
    """The name is said as "this activity" only where the record holds one, so an activity it
    names nothing for keeps the words the record states — his own among them — exactly as typed,
    down to the capital a sentence of his starts with (t64 fix 1)."""
    nameless = {NAME: "", OWNER: "", MBCO: "the line runs on paper. this activity is chilled"}
    assert ("The minimum acceptable service for  is the line runs on paper. this activity is "
            "chilled.") in requirements_of({ACTIVITIES: [nameless]})


def test_a_category_said_after_somebodys_quote_is_still_said_by_its_method_name():
    """Outside *every* quoted span: the prose before a quote and the prose after it both, with
    the quote between them left as he said it."""
    assert categories_said("financial, “financial”, and financial again", METHOD_HELD) == \
        "Financial, “financial”, and Financial again"


def test_a_record_that_carries_no_mtpd_reads_as_no_band_whatever_stands_there_instead():
    """None for anything that is not a band (t74), and a record that carries nothing where an
    MTPD would stand carries no band either — whichever empty thing it carries."""
    assert [upper_edge(nothing) for nothing in (None, "", 0, False, [], {})] == [None] * 6
    assert gap_reading({RECOVERY_TARGET: "4 h", MTPD: ""}) is None


# ── No email identity branch, and ticket 228's kept email is off the signature ──────────────────
# Moved whole from `tests/ui/walk/test_stage_5_consolidate_hand_over_and_sign.py` step 43 (last held
# at 4ffe6783), which ticket 165 slice 4 retired with that walk file. The hunt reads source, so it
# lives where it reds early, in the coder gate; nothing in it drives a screen. Why the branch does
# not exist is `nemo.handover`'s docstring: the third typed slot is one free-text amendment and not
# an email at the door, so the certificate asserts identity and claims nothing stronger (ADR-0003:
# the signature is the only identity moment).

#: Ticket 228's contact email, and ticket 179's wipe of it, the places step 43's hunt may meet the
#: word: named by file and by top-level name, never a whole file, and red the day a name here no
#: longer exists. ADR-0003's property is kept by step 43's second half: none of these is reachable
#: from the signature.
KEPT_FOR_FOLLOW_UP = {
    "skin/stage_door.py": ("kept_email", "keep_contact", "newest_room", "LANDING", "CONTACTS"),
    "skin/PROTOTYPE_conversation_app.py": ("landing",),
    "skin/demo_rooms.py": ("_finish_the_wipe",),
    # Ticket 257 (ADR-0043 d4): the follow-up drafts, the only mail code, every top-level name.
    "skin/drafts.py": ("MAILBOX_HOST", "MAILBOX_USER", "MAILBOX_PASSWORD", "OWNER_DOMAIN",
                       "FOLLOW_UP_SUBJECT", "LISTED_FOLDER", "owner_address", "follow_up_drafts",
                       "follow_up_folder", "put_in_mailbox",
                       # Ticket 373 (ADR-0049): the invitation, its .ics and its one append
                       "INVITE_SUBJECT", "INVITE_FROM", "CLOSING",  # t418: the sender by function
                       "INVITE_AGENDA", "_ics_text", "_ics",
                       "invitation", "appended", "CALENDAR_ENV", "put_in_calendar",
                       "put_invitation",
                       # Ticket 406: the drafts A8 showed, marked with their room, one tap
                       "ROOM_MARKER", "room_mark", "shown_drafts", "put_shown",
                       # Ticket 418 r2 (ADR-0051 d5): the function mailboxes
                       "gap_mailbox", "invitee_address",
                       # Ticket 533 (ADR-0056 S2): placed or not, read from the room's store
                       "invited", "shown_placed", "follow_up_placed",
                       # Ticket 539+540 (ADR-0056 S7, S8): the model's letter, placed by his tap
                       # at code's function mailbox; the one calendar event moved, its id kept
                       "function_address", "letter_draft", "move_invitation"),
}

#: A name that puts a module on the signature's path: sign, signature, certificate, handover.
ON_THE_SIGNATURE = re.compile(r"(?:^|_)(?:sign|certificate|handover)", re.I)


def repo_root() -> Path:
    """The real checkout, found by walking up to it rather than by counting parents.

    `mutmut` runs the suite from a copy of `src/` and `tests/` under `mutants/` and copies nothing
    else, so a test that reads the skin off a fixed number of parents raises there and takes the
    whole mutation run down with it (`docs/status.md`, and `gate.sh`'s hardener block). Ticket 161:
    the skin walked up to is the phone app's, `skin/PROTOTYPE_conversation_app.py`. From the copy
    the walk-up lands on the real tree, so the hunt reads the source unmutated there too.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "skin" / "PROTOTYPE_conversation_app.py").is_file():
            return parent
    raise AssertionError(  # pragma: no cover - every checkout and mutmut's copy has the skin
        "no ancestor of this file holds skin/PROTOTYPE_conversation_app.py")


def test_the_email_branch_is_not_in_the_product_and_the_kept_email_is_off_the_signature():
    """43. The email branch is not in the product, as code or as a flag that would select it.

    Nothing in `src/nemo` or the phone app's `skin/` says `identity confirmed by email`, and no
    identifier or non-docstring string in either tree mentions an email or a second identity
    sentence, outside ticket 228's contact email at `KEPT_FOR_FOLLOW_UP`. None of those is imported
    or referenced from `src/nemo`, `skin/PROTOTYPE_core.py` or any skin module on the signature's
    path: the signature stays the only identity moment (ADR-0003).
    """
    #     The hunt is shown to find one first, over a module that has what the product must not:
    #     a check nothing can fail says nothing about what it looked at.
    planted = _emailed("planted.py", ast.parse(
        '"""A docstring saying why there is no email branch."""\n'
        'BY_EMAIL = "identity confirmed by email"\n'
        'def certificate(email_given):\n    return BY_EMAIL if email_given else ""\n'))
    assert len(planted) >= 2, f"step 43: the hunt does not find a planted branch: {planted}"
    written = branch_selecting_an_identity_sentence()
    assert written == [], f"step 43: the email branch is written after all: {written}"
    #     And the email ticket 228 keeps is unreachable from the signature: the same kind of check,
    #     shown to find a planted reference first.
    planted = _reaching("planted.py", ast.parse(
        "from stage_door import kept_email\ndef sign(said):\n    return stage_door.LANDING\n"))
    assert len(planted) >= 2, f"step 43: the reach check does not find a planted one: {planted}"
    reached = reaching_the_kept_email()
    assert reached == [], f"step 43: the signature's path reaches the kept email: {reached}"


def branch_selecting_an_identity_sentence() -> list[str]:
    """Anywhere in the product a second identity sentence could come from, as file:line.

    The literal first, and then every identifier and every string that is not a docstring: a flag
    nothing sets is still a claim no code here can make true, and the procedure asks for it to be
    reported whether or not anything reaches it. The word alone is spared inside
    `KEPT_FOR_FOLLOW_UP`'s names, and nowhere else; the literal is spared nowhere.
    """
    root = repo_root()
    gone = [relative for relative in KEPT_FOR_FOLLOW_UP if not (root / relative).is_file()]
    assert gone == [], f"step 43: the allow-list names files that are gone: {gone}"
    found: list[str] = []
    for path in sorted([*(root / "src" / "nemo").glob("*.py"), *(root / "skin").glob("*.py")]):
        if path.name.startswith("test_"):
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        found += [f"{path.name}:{number}: {line.strip()}"
                  for number, line in enumerate(source.splitlines(), 1)
                  if "identity confirmed by email" in line]
        found += _emailed(path.name, tree, spared=_kept(path.relative_to(root).as_posix(), tree))
    return found


def _kept(relative: str, tree: ast.Module) -> list[range]:
    """The lines of `KEPT_FOR_FOLLOW_UP`'s names in one file, raising if a name has gone."""
    named = {node.name if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
             else node.targets[0].id: range(node.lineno, node.end_lineno + 1)
             for node in tree.body
             if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
             or isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    kept = KEPT_FOR_FOLLOW_UP.get(relative, ())
    gone = [name for name in kept if name not in named]
    assert gone == [], f"step 43: {relative} no longer has {gone}; the allow-list is stale"
    return [named[name] for name in kept]


def reaching_the_kept_email() -> list[str]:
    """Every reference to the kept email's names or modules from where the signature is made.

    That is all of `src/nemo`, `skin/PROTOTYPE_core.py`, and every other skin module that names a
    sign, signature, certificate or handover, found by that name rather than listed.
    """
    root = repo_root()
    on_the_path: list[Path] = [path for path in (root / "src" / "nemo").glob("*.py")
                               if not path.name.startswith("test_")]
    on_the_path.append(root / "skin" / "PROTOTYPE_core.py")
    for path in (root / "skin").glob("*.py"):
        if path not in on_the_path and any(ON_THE_SIGNATURE.search(name)
                                           for _, name in _names(ast.parse(path.read_text()))):
            on_the_path.append(path)
    assert root / "src" / "nemo" / "handover.py" in on_the_path, "step 43: no handover to check"
    found: list[str] = []
    for path in sorted(on_the_path):
        found += _reaching(path.name, ast.parse(path.read_text(encoding="utf-8")))
    return found


def _names(tree: ast.Module) -> list[tuple[int, str]]:
    """Every name a module uses, imports or defines, and the module every import names, by line."""
    return [(node.lineno, name) for node in ast.walk(tree) for name in (
        [node.id] if isinstance(node, ast.Name)
        else [node.attr] if isinstance(node, ast.Attribute)
        else [node.name] if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        else [*(alias.name for alias in node.names), node.module or ""]
        if isinstance(node, ast.ImportFrom)
        else [alias.name for alias in node.names] if isinstance(node, ast.Import)
        else [])]


def _reaching(name: str, tree: ast.Module) -> list[str]:
    """Where one module names a kept name, or the module that keeps it."""
    kept = {Path(relative).stem for relative in KEPT_FOR_FOLLOW_UP}
    kept |= {each for names in KEPT_FOR_FOLLOW_UP.values() for each in names}
    return [f"{name}:{number}: {said!r}" for number, said in sorted(_names(tree))
            if set(said.split(".")) & kept]


def _emailed(name: str, tree: ast.Module, *, spared: list[range] | None = None) -> list[str]:
    """Every identifier and every string that is not a docstring, where it mentions an email.

    A docstring is prose about the code and `nemo.handover`'s says why this branch does not exist;
    a string constant or a name is the flag the procedure is hunting for. The docstrings are found
    as the nodes they are rather than by their text: `ast.get_docstring` hands back a cleaned copy
    of a docstring, which never equals the constant it was taken from once it spans two lines.
    """
    documented = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)}
    said = [(node.lineno, f"string {node.value!r}") for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in documented and re.search(r"e-?mail", node.value, re.I)]
    spelled = [(node.lineno, f"name {node.id if isinstance(node, ast.Name) else node.attr!r}")
               for node in ast.walk(tree) if isinstance(node, ast.Name | ast.Attribute)
               and re.search(r"e_?mail", node.id if isinstance(node, ast.Name) else node.attr,
                             re.I)]
    return [f"{name}:{number}: {what}" for number, what in sorted(said + spelled)
            if not any(number in lines for lines in spared or ())]


# ── Where the authority check is, and what it compares: one place, and never the role ───────────
# From `tests/ui/walk/test_stage_5_consolidate_hand_over_and_sign.py` step 33 (ticket 18; ticket 134
# added `on_behalf_of`), last held at 4ffe6783, which ticket 165 slice 4 retired with that walk
# file. The behaviour is pinned above; these pin what the code can do, read off the real source.


def _source_of(name: str) -> str:
    return (repo_root() / "src" / "nemo" / name).read_text(encoding="utf-8")


def test_the_signer_is_compared_with_the_owner_on_exactly_one_line_of_handover():
    comparisons = [line for line in _source_of("handover.py").splitlines()
                   if "norm(name) == norm(owner)" in line]
    assert len(comparisons) == 1, f"step 33: the comparison is made in {len(comparisons)} places"


def test_the_authority_check_takes_no_role():
    """The list stays exact, so any new parameter reds it, and no parameter may be a role."""
    [capacity] = [node for node in ast.parse(_source_of("handover.py")).body
                  if isinstance(node, ast.FunctionDef) and node.name == "capacity"]
    arguments = capacity.args
    parameters = [each.arg for each in (*arguments.posonlyargs, *arguments.args,
                                        *filter(None, (arguments.vararg,)),
                                        *arguments.kwonlyargs,
                                        *filter(None, (arguments.kwarg,)))]
    assert parameters == ["record", "name", "on_behalf_of"], (
        f"step 33: the authority check is handed something it must not read: {parameters}")
    assert not [name for name in parameters if "role" in name], (
        f"step 33: the authority check takes a role parameter: {parameters}")


def test_the_role_string_is_defined_written_and_rendered_and_read_nowhere_else():
    """The role is defined, written onto the signature and rendered onto the certificate, and that
    is the whole of what the product does with it."""
    reading = [f"{path.name}:{number}: {line.strip()}"
               for path in sorted((repo_root() / "src" / "nemo").glob("*.py"))
               if not path.name.startswith("test_")
               for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
               if re.search(r"\bROLE\b", line)
               and not re.match(r"\s*(ROLE = |ROLE,|from |import )", line)
               and "role=signature.get(ROLE" not in line and "ROLE: role," not in line]
    assert reading == [], f"step 33: the role string is read somewhere else too: {reading}"


# ── the certificate he signs on the phone, nemo's own (ticket 241 slice 2, ADR-0030 d5) ──
#
# The live app wrote what follows through a runtime patch over `certificate` and `_reservations`
# (t71, t79 fix 1, t132, t134, 190). It is this module's now, so one source writes the document
# he signs. The bytes below are what the phone wrote for this record and run before the move.

PHONE_RECORD = {
    DEPT: "Slaughter", METHOD: METHOD_HELD,
    OPEN_ITEMS: ["the sticking-pen conveyor is not in your register"],
    ACTIVITIES: [
        {NAME: "Slaughter", OWNER: "Torsten Ahlgrim", MTPD: "24 h", RECOVERY_TARGET: "48 h",
         RPO: "4 h", "recovery_gap_flagged": True, GAP_ACCOUNT: "Torsten Ahlgrim",
         "evidence": [{"type": "chat_confirmation", "on": "2026-09-30", "words": "8 h is right",
                       "label": "Recovery target"}]},
        {NAME: "Chilling", OWNER: "Bo Ødegård", MTPD: "4 h", RECOVERY_TARGET: "2 h",
         GAP_CLOSED: "a second chiller is on order",
         "evidence": [{"label": "RPO", "origin": "method"}]},
        {NAME: "Boning"}]}
PHONE_RUN = {
    DECISIONS: [{AT_STAGE: 4, GRADIENT: "endorsed with reservations",
                 NAMING: "the boning line is shared"}],
    "carried_reservations": [{AT_STAGE: 3, NAMING: "Torsten gave me 6 h, not 8"}],
    FINDINGS: ["the grid's worst case improves with time"],
    SIGNATURE: {SIGNER: "Petra Nolte", ROLE: "Shift lead", ACCEPTED: ["OPEN-1"],
                CAPACITY: ON_BEHALF_OF.format(owner="Torsten Ahlgrim")}}
PHONE_CERTIFICATE = (
    "# The sign-off for Slaughter\n\n"
    "Signed by Petra Nolte, Shift lead, as on behalf of Torsten Ahlgrim, whom the record holds as "
    "the owner.\n\n"
    "How this signature stands: identity asserted in session, not verified. Nobody was asked for a "
    "password and nothing was sent anywhere to establish who signed, so this says exactly as much "
    "as it says.\n\n"
    "Petra Nolte signs on behalf of Torsten Ahlgrim, Bo Ødegård, whom the record holds as the "
    "owner.\n\n"
    "## What was signed\n\n"
    "Slaughter: MTPD 24 h, recovery target 48 h — a recovery gap, acknowledged on Torsten "
    "Ahlgrim's account, with the target not inside the MTPD, RPO 4 h. Owner on file: Torsten "
    "Ahlgrim.\n\n"
    "Chilling: MTPD 4 h, recovery target 2 h — a recovery gap he closed, in his own words: “a "
    "second chiller is on order”, no RPO: none of the systems it depends on gives one for this "
    "activity. Owner on file: Bo Ødegård.\n\n"
    "Boning: MTPD —, recovery target —, RPO —. Owner on file: —.\n\n"
    "The manager's confirmation in chat on 2026-09-30: 8 h is right\n\n"
    "## What was reserved on the way here\n\n"
    "Before the BIA was reopened, step 3 carried this reservation, and it stands: Torsten gave me "
    "6 h, not 8\n\n"
    "Stage 4 was answered “endorsed with reservations”, and what was reserved is: the boning line "
    "is shared\n\n"
    "## What was accepted at this signature\n\n"
    "OPEN-1 — the sticking-pen conveyor is not in your register\n\n"
    "## What this sign-off does not say\n\n"
    "It is a signature on a requirements handover for solution-design discussion. It is not an "
    "approval of a continuity plan, and no plan was drafted: this BIA hands over the requirements "
    "above and stops.\n")


def test_the_certificate_is_the_one_the_phone_writes_byte_for_byte():
    assert certificate(PHONE_RECORD, PHONE_RUN) == PHONE_CERTIFICATE


def test_the_signed_figures_and_the_reservations_stand_before_what_was_accepted():
    said = certificate(PHONE_RECORD, PHONE_RUN)
    assert said.index(handover.SIGNED_FIGURES) < said.index(handover.RESERVED) < said.index(
        handover.ACCEPTED_HERE)


def test_only_a_signature_on_behalf_of_the_owner_says_whom_it_signs_for():
    for chosen in (OWNER_OF_THE_ACTIVITY, SPONSOR, ""):
        run = {**PHONE_RUN, SIGNATURE: {**PHONE_RUN[SIGNATURE], CAPACITY: chosen}}
        assert " signs on behalf of " not in certificate(PHONE_RECORD, run), chosen
    ownerless = {**PHONE_RECORD, ACTIVITIES: [{NAME: "Boning"}]}
    assert " signs on behalf of " not in certificate(ownerless, PHONE_RUN)
    assert handover.SIGNED_FOR.format(name="Petra Nolte", owners="Torsten Ahlgrim, Bo Ødegård") \
        in certificate(PHONE_RECORD, PHONE_RUN)


def test_a_delegate_signature_with_no_name_leaves_the_name_out_rather_than_a_word():
    run = {**PHONE_RUN, SIGNATURE: {CAPACITY: ON_BEHALF_OF.format(owner="Torsten Ahlgrim")}}
    assert "\n\n signs on behalf of Torsten Ahlgrim, Bo Ødegård, whom" in certificate(
        PHONE_RECORD, run)


def test_the_certificate_reads_each_gap_by_the_method_the_record_holds():
    """t156 on the certificate: both past the last horizon is inside under a method with that
    word, and the record's own method is the one the figure line is read by."""
    both = {**GAPPED, RECOVERY_TARGET: ">168 h", MTPD: ">168 h"}
    record = {**PHONE_RECORD, METHOD: {"beyond_horizons": ">168 h"}, ACTIVITIES: [both]}
    assert "with the target inside the MTPD" in certificate(record, PHONE_RUN)
    assert "with the target not inside the MTPD" in certificate(
        {**record, METHOD: METHOD_HELD}, PHONE_RUN)


def test_a_figure_he_confirmed_in_chat_is_said_as_his_confirmation_and_no_other_evidence_is():
    quote = {"type": "interview_quote", "on": "2026-09-01",
             "words": "a quote, not his confirmation"}
    record = {**PHONE_RECORD, ACTIVITIES: [{NAME: "Boning", "evidence": [quote]}]}
    said = certificate(record, PHONE_RUN)
    assert "a quote, not his confirmation" not in said
    assert "confirmation in chat" not in said
    assert certificate({**PHONE_RECORD, ACTIVITIES: [{NAME: "Boning"}]}, PHONE_RUN) == said


def test_a_figure_line_says_each_figure_or_a_dash_and_the_owner_on_file():
    assert handover.figure_line({NAME: "Boning", MTPD: "8 h", RECOVERY_TARGET: "4 h", RPO: "1 h",
                                 OWNER: "Bo Ødegård"}) == (
        "Boning: MTPD 8 h, recovery target 4 h, RPO 1 h. Owner on file: Bo Ødegård.")
    assert handover.figure_line({}) == (
        "None: MTPD —, recovery target —, RPO —. Owner on file: —.")


def test_a_figure_line_says_a_gap_in_the_third_person_with_the_method_he_signs():
    beyond = {"beyond_horizons": ">168 h"}
    both = {**GAPPED, RECOVERY_TARGET: ">168 h", MTPD: ">168 h"}
    assert handover.figure_line(both, beyond) == (
        f"Slaughter: MTPD >168 h, recovery target >168 h — {gap_words(both, beyond)}, RPO 4 h. "
        "Owner on file: Torsten Ahlgrim.")
    assert "with the target inside the MTPD" in handover.figure_line(both, beyond)
    closed = {**GAPPED, "recovery_gap_flagged": False, GAP_CLOSED: "done"}
    assert handover.figure_line(closed) == (
        "Slaughter: MTPD 8 h, recovery target 12 h — a recovery gap he closed, in his own words: "
        "“done”, RPO 4 h. Owner on file: Torsten Ahlgrim.")
    flagged_and_closed = {**GAPPED, GAP_CLOSED: "done"}
    assert gap_words(GAPPED) in handover.figure_line(flagged_and_closed)
    assert "done" not in handover.figure_line(flagged_and_closed)


def test_no_rpo_is_said_only_where_the_method_gives_none_and_the_record_carries_no_figure():
    """190: the method's own statement behind the RPO, and no figure; anything else is a figure."""
    by_method = {"evidence": [{"label": "RPO", "origin": "method"}]}
    assert handover.no_rpo(by_method)
    assert handover.rpo_clause(by_method) == f", {handover.NO_RPO}"
    assert handover.NO_RPO == (
        "no RPO: none of the systems it depends on gives one for this activity")
    assert not handover.no_rpo({**by_method, RPO: "4 h"})
    assert handover.rpo_clause({**by_method, RPO: "4 h"}) == ", RPO 4 h"
    for other in ({"label": "RPO", "origin": "interview"}, {"label": "MTPD", "origin": "method"},
                  {"origin": "method"}, {"label": "RPO"}):
        assert not handover.no_rpo({"evidence": [other]}), other
    assert not handover.no_rpo({}) and not handover.no_rpo({"evidence": None})
    assert handover.no_rpo({"evidence": [{"label": "MTPD"}, {"label": "RPO", "origin": "method"}]})
    assert handover.rpo_clause({}) == ", RPO —"


def test_a_reservation_a_reopen_carried_is_said_first_and_nothing_reserved_is_not_said_beside_it():
    carried = {"carried_reservations": [{AT_STAGE: 3, NAMING: "x"}, {AT_STAGE: 4, NAMING: "y"}]}
    assert handover._reservations(carried) == [
        "Before the BIA was reopened, step 3 carried this reservation, and it stands: x",
        "Before the BIA was reopened, step 4 carried this reservation, and it stands: y"]
    assert handover._reservations({}) == [NOTHING_RESERVED]
    assert handover._reservations({"carried_reservations": None}) == [NOTHING_RESERVED]
    both = {**carried, **RUN}
    assert handover._reservations(both) == [
        *handover._reservations(carried), *handover._reservations(RUN)]
    assert handover._reservations(RUN) == [RESERVATION.format(
        stage=3, gradient="endorsed with reservations", naming=RUN[DECISIONS][0][NAMING])]


def test_a_carried_reservation_reaches_both_documents_and_the_certificate():
    carried = handover.CARRIED_SAYS.format(stage=3, naming="Torsten gave me 6 h, not 8")
    for said in (*documents(PHONE_RECORD, PHONE_RUN).values(),
                 certificate(PHONE_RECORD, PHONE_RUN)):
        assert carried in said and NOTHING_RESERVED not in said
