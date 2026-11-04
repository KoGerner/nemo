"""Step definitions. One set per story; keep both sides of any merge conflict here.

09 — the card must agree with the record: the steps drive `nemo.card`, whose `render` is the one
door a stage card reaches a human by.

32 — a digit inside a name is not a figure the record must hold: the same steps, now carrying the
names the room supplies. Ticket 09's `a card says "..."` is the step both stories check a card
with, so the name goes in beside the record here rather than in a second copy of it.
"""

from typing import Any

import pytest
from pytest_bdd import given, parsers, then, when

from nemo.card import CardGeneratorBug, render, render_walk, untraceable

#: Goods dispatch and delivery's emergency operation, in Henning Barsch's words (the seed's
#: dispatch-and-delivery interview): a count and a hedged count, so both directions are testable.
MBCO = "Ten fleet staff take over loading and delivery; about 60 internal lorries across all sites"


#: The room these scenarios are set in when no step names a department: ticket 32's own building,
#: which is what makes `The MBCO for Halle 60 is 60 internal lorries` a card with a name *and* a
#: count on it. A step that names a department replaces it, and no scenario of ticket 09's says
#: either name.
ROOM_NAMES = ("Halle 60",)


@pytest.fixture
def walk() -> dict[str, Any]:
    """What the scenario has built so far: the record, the card, and what came of it."""
    # The record holds nothing until a step says what it holds: a card that names no figure at all
    # is checked against an empty record exactly as a stage 1 card is.
    return {"rendered": None, "bug": None, "names": ROOM_NAMES, "record": {}}


def _try_to_render(walk: dict[str, Any], card: str, stage: int = 4) -> None:
    walk["card"] = card
    walk["stage"] = stage
    try:
        walk["rendered"] = render(stage, card, walk["record"], walk["names"])
    except CardGeneratorBug as bug:
        walk["bug"] = bug


# ── the record ───────────────────────────────────────────────────────────────
@given(parsers.parse('a record whose MTPD is "{mtpd}"'))
def _a_record_whose_mtpd_is(walk: dict[str, Any], mtpd: str) -> None:
    walk["record"] = {"revision": 3, "activities": [
        {"id": "BIA-2026-002", "name": "Incident and problem management", "mtpd": mtpd}]}


@given(parsers.parse('a record whose MBCO says "{mbco}"'))
def _a_record_whose_mbco_says(walk: dict[str, Any], mbco: str) -> None:
    assert mbco in MBCO, f"{mbco!r} is not in the record's MBCO"
    walk["record"] = {"revision": 3, "activities": [
        {"id": "BIA-2026-002", "name": "Goods dispatch and delivery", "mbco": MBCO}]}


@given(parsers.parse('my department is called "{name}"'))
@given(parsers.parse('a department called "{name}"'))
def _my_department_is_called(walk: dict[str, Any], name: str) -> None:
    """The one name this room supplies. Nothing else on a card is a name, however it is spelled."""
    walk["names"] = (name,)


@given("a record scoring Incident and problem management 4 of 5 on operational at 24 h")
def _a_record_scoring_incident_management(walk: dict[str, Any]) -> None:
    walk["record"] = {"revision": 3, "activities": [
        {"id": "BIA-2026-002", "name": "Incident and problem management", "mtpd": "24 h",
         "impact_grid": {"operational": {"24 h": 4, "72 h": 5}}}]}


@given("a record whose seven activities are resources and dependencies rather than activities")
def _a_record_of_resources(walk: dict[str, Any]) -> None:
    walk["record"] = {"revision": 2, "activities": [
        {"id": f"BIA-2026-10{n}", "name": name}
        for n, name in enumerate(("refrigeration", "automated warehouse control", "vehicle fleet",
                                  "price-labelling devices", "corporate network", "power supply",
                                  "time-recording system"), 1)]}


@given(parsers.parse('every one of them reads "{mtpd}"'))
def _every_one_of_them_reads(walk: dict[str, Any], mtpd: str) -> None:
    for activity in walk["record"]["activities"]:
        activity["mtpd"] = mtpd
    assert len(walk["record"]["activities"]) == 7


# ── the card ─────────────────────────────────────────────────────────────────
@given("any card")
def _any_card(walk: dict[str, Any]) -> None:
    walk["record"] = {"revision": 3, "activities": [
        {"id": "BIA-2026-002", "name": "Incident and problem management", "mtpd": "24 h"}]}
    walk["card"] = "Incident and problem management's MTPD is 24 h."


@given("a walk that reaches all five stages")
def _a_walk_of_five_stages(walk: dict[str, Any]) -> None:
    _any_card(walk)
    walk["cards"] = [f"Stage {stage} of 5 · Incident and problem management's MTPD is 24 h."
                     for stage in range(1, 6)]


@given("a card whose figures cannot be traced to the record")
def _an_untraceable_card(walk: dict[str, Any]) -> None:
    _any_card(walk)
    walk["card"] = "The MTPD is about a working day."


@when(parsers.parse('a card says "{body}"'))
def _a_card_says(walk: dict[str, Any], body: str) -> None:
    _try_to_render(walk, body)


@when("each stage puts a card in front of the manager")
def _each_stage_puts_a_card(walk: dict[str, Any]) -> None:
    walk["rendered"] = render_walk(walk["cards"], walk["record"])


@when("the check refuses it")
def _the_check_refuses_it(walk: dict[str, Any]) -> None:
    _try_to_render(walk, walk["card"], stage=2)
    assert walk["bug"] is not None


# ── what came of it ──────────────────────────────────────────────────────────
@then("the card is refused")
@then("the card is refused before a human sees it")
def _the_card_is_refused(walk: dict[str, Any]) -> None:
    assert isinstance(walk["bug"], CardGeneratorBug)
    assert walk["rendered"] is None, "a refused card was rendered anyway"


@then(parsers.parse('the card is refused, because nothing in this room is called "{name}"'))
def _refused_because_nothing_is_called(walk: dict[str, Any], name: str) -> None:
    """A carve-out that matched a shape — a word and some digits — would mint this name itself."""
    _the_card_is_refused(walk)
    assert name not in walk["names"]
    assert walk["bug"].strings == [name.split()[-1]], f"{name!r} was read as a name of this room"


@then("the refusal names the count the record does not hold, not the building")
def _the_refusal_names_the_count(walk: dict[str, Any]) -> None:
    """Both are `60`, so the count is named once: the building's own `60` is not refused twice."""
    assert walk["bug"].strings == ["60"]


@then(parsers.parse('the refusal names "{text}" as the string the record does not hold'))
def _the_refusal_names(walk: dict[str, Any], text: str) -> None:
    assert text in walk["bug"].strings
    assert text in str(walk["bug"])


@then("the card passes")
@then("the card passes, because the card and the record agree")
def _the_card_passes(walk: dict[str, Any]) -> None:
    assert walk["bug"] is None, f"the card was refused: {walk['bug']}"
    assert walk["rendered"] == walk["card"]


@then("it is checked against the record before it is rendered")
def _checked_before_rendered(walk: dict[str, Any]) -> None:
    # There is one door and the check is the first thing behind it: the same card with one
    # untraceable figure added renders nothing at all, rather than rendering with a warning.
    assert untraceable(walk["card"], walk["record"]) == []
    assert render(1, walk["card"], walk["record"]) == walk["card"]
    with pytest.raises(CardGeneratorBug):
        render(1, walk["card"] + " That's roughly a working day.", walk["record"])


@then("every one of the five was checked against the record first")
def _every_one_of_the_five(walk: dict[str, Any]) -> None:
    assert walk["rendered"] == walk["cards"]
    for stage in range(1, 6):
        broken = list(walk["cards"])
        broken[stage - 1] = "The MTPD is about a working day."
        with pytest.raises(CardGeneratorBug) as refusal:
            render_walk(broken, walk["record"])
        assert refusal.value.stage == stage


@then("no card reached the manager unchecked")
def _no_card_unchecked(walk: dict[str, Any]) -> None:
    broken = ["The MTPD is about a working day.", *walk["cards"][1:]]
    with pytest.raises(CardGeneratorBug):
        render_walk(broken, walk["record"])  # no list comes back, so no card is shown


@then("the failure is reported as a bug in the card generator")
def _reported_as_a_bug(walk: dict[str, Any]) -> None:
    message = str(walk["bug"])
    # The stage the card was refused at, not a literal: ticket 14 brought a second stage through
    # this same step, and a hard-coded 2 would have had to be satisfied by a lie about which door
    # the card went through. `walk["stage"]` is set wherever the render is attempted.
    assert f"bug in the card generator at stage {walk['stage']}" in message
    assert "'a working day'" in message
    assert "revision 3" in message and "BIA-2026-002" in message


@then("it does not appear as an open item on the manager's card")
def _not_an_open_item(walk: dict[str, Any]) -> None:
    assert walk["rendered"] is None  # there is no card, so there is nothing on one
    assert "finding" not in str(walk["bug"]).lower()


@then("it does not travel to the sign-off as something the manager accepts")
def _does_not_travel_to_sign_off(walk: dict[str, Any]) -> None:
    with pytest.raises(CardGeneratorBug):
        render_walk([walk["card"]], walk["record"])  # the walk stops; nothing reaches a signature


@then("it names it once, for the bare word and not for the one inside the name")
def _it_names_it_once(walk: dict[str, Any]) -> None:
    """The decider of ticket 47: two `key`s means the spans are not read, one that is not the
    bare one would mean the name was refused and the card's own vagueness let through."""
    assert walk["bug"].strings == ["key"]
    assert walk["card"].lower().count("key") == 2, "this card does not say the word twice"
