"""Ticket 116: an open referee question blocks the step; he answers it with its own taps.

The owner, TYPED (ce2e8d7b, 2026-09-22 ~09:03Z): *"a step answer such as "endorsed" can never
settle a referee question that is still open. In the app's logic, not a prompt sentence."*

One finding class asks him something: an MTPD he asserted against the one the grid derives. The
referee now also returns it as a **question** with a stable id, open until the record carries his
answer to exactly those two figures (12_nemo_check's amendment 1). Figures are the new seed's
(order picking: operational 168 h scored 4, "MTPD: >168 h" stated), read off the method fixture.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from nemo import referee, turn_file, walk
from nemo.interview import INTERVIEWS
from nemo.record import ANSWERS, DECISIONS
from nemo.room_store import read_record
from nemo.test_walk import room, said
from nemo.walk import ENDORSED, GRADIENT, STAGE_3, onward, open_bia, run_file

REPO = Path(__file__).resolve().parents[2]
NEW = json.loads((REPO / "tests" / "fixtures" / "seed" / "method.json").read_text(encoding="utf-8"))
HORIZONS = NEW["time_horizons"]
LENSES = [s["id"] for s in NEW["scenarios"]]
BEYOND = NEW["beyond_horizons"]  # ">168 h", what the order-picking interview states
#: order picking's operational row, as the new seed's interview scores it (1 h filled here)
OPERATIONAL = dict(zip(HORIZONS, [1, 1, 1, 1, 1, 2, 4], strict=True))
DERIVED = "168 h"
QID = "order-picking.mtpd.asserted"


def _record(mtpd: str = BEYOND, operational: dict | None = None, **answers) -> dict:
    grid = {lens: dict.fromkeys(HORIZONS, 1) for lens in LENSES}
    grid["operational"] = dict(operational or OPERATIONAL)
    activity = {"id": "order-picking", "name": "Order picking", "impact_grid": grid,
                "mtpd": mtpd, "recovery_target": "72 h", "evidence": [
                    {"type": "transcript_quote", "lens": "operational", "quote": "168 h high",
                     "source_path": "07_Interviews/x.md"}]}
    if answers:
        activity[ANSWERS] = answers
    return {"dept": "Order picking", "activities": [activity]}


def _review(record: dict) -> referee.Verdict:
    return referee.review(record, NEW, {"07_Interviews/x.md": "168 h high"})


# ── the question: data with a stable id ──────────────────────────────────────────────────────
def test_an_asserted_mtpd_the_grid_does_not_derive_is_an_open_question_with_both_figures():
    question, = _review(_record()).questions
    assert (question.id, question.asserted, question.derived) == (QID, BEYOND, DERIVED)
    assert question.key == referee.ASSERTED_MTPD


def test_an_asserted_mtpd_the_grid_agrees_with_asks_nothing():
    assert _review(_record(mtpd=DERIVED)).questions == []
    assert _review(_record(mtpd=BEYOND, operational=dict.fromkeys(HORIZONS, 2))).questions == []


def test_the_finding_text_is_unchanged_beside_the_question():
    """Ruling A: the signed documents say what they said. The question is a new field."""
    finding, = _review(_record()).findings
    assert finding == (f"Gap: activity order-picking: the grid derives an MTPD of '{DERIVED}', not "
                       f"the asserted '{BEYOND}' — the MTPD comes from the grid, so the assertion "
                       "is the thing to explain or withdraw")


def test_the_question_id_is_the_same_on_two_runs_and_after_an_unrelated_finding_before_it():
    first = _review(_record()).questions
    assert first == _review(_record()).questions
    record = _record()
    other = json.loads(json.dumps(record["activities"][0]))
    other.update(id="dispatch", name="Dispatch", mtpd="24 h")  # a finding of its own, first
    record["activities"].insert(0, other)
    verdict = _review(record)
    assert len(verdict.findings) == 2, verdict.findings
    assert [q.id for q in verdict.questions] == ["dispatch.mtpd.asserted", QID]
    assert verdict.questions[1] == first[0]


# ── each answer removes it, and only while both figures still match ──────────────────────────
def _answer(answer: str, asserted: str = BEYOND, derived: str = DERIVED, **more) -> dict:
    return {referee.ASSERTED_MTPD: {"answer": answer, "asserted": asserted, "derived": derived,
                                    **more}}


def test_keep_with_his_reason_answers_it_and_the_line_carries_his_words():
    verdict = _review(_record(**_answer(referee.KEEP, reason="the source record says so")))
    assert verdict.questions == []
    finding, = verdict.findings
    assert finding.endswith(referee.answer_says(referee.KEEP, "the source record says so"))
    assert "the source record says so" in finding


def test_keep_without_a_reason_answers_it_in_nemo_s_fixed_words():
    verdict = _review(_record(**_answer(referee.KEEP)))
    assert verdict.questions == []
    assert verdict.findings[0].endswith(referee.answer_says(referee.KEEP))
    assert "kept, no reason given" in referee.answer_says(referee.KEEP)


def test_leave_it_open_answers_the_question_and_keeps_the_open_item_named_his():
    verdict = _review(_record(**_answer(referee.LEAVE_OPEN)))
    assert verdict.questions == []
    finding, = verdict.findings
    assert finding.startswith("Gap: activity order-picking: the grid derives")
    assert finding.endswith(referee.answer_says(referee.LEAVE_OPEN))
    assert "his decision" in referee.answer_says(referee.LEAVE_OPEN)


def test_withdraw_is_the_grid_s_figure_so_nothing_is_asked():
    assert _review(_record(mtpd=DERIVED)).questions == []


@pytest.mark.parametrize("answer", [referee.KEEP, referee.LEAVE_OPEN])
def test_an_answer_to_other_figures_is_no_answer_and_the_question_opens_again(answer):
    """Amendment 1: a later change that moves the derived MTPD reopens it; so does a changed
    assertion. The stale answer adds nothing to the line."""
    moved = {**OPERATIONAL, "72 h": 4}  # the grid now derives 72 h
    verdict = _review(_record(operational=moved, **_answer(answer)))
    assert [(q.asserted, q.derived) for q in verdict.questions] == [(BEYOND, "72 h")]
    assert verdict.findings[0].endswith("explain or withdraw")
    assert _review(_record(mtpd="24 h", **_answer(answer))).questions[0].asserted == "24 h"


def test_an_answer_word_the_referee_does_not_know_answers_nothing():
    assert _review(_record(**_answer("endorsed"))).questions


# ── walk.answer at stage 3: a gradient answer never settles an open question ─────────────────
TRANSCRIPT = "\n".join([
    "---", "department: Slaughter", "covered: " + ", ".join(LENSES), "---", "",
    "# Slaughter interview", "",
    *[f"Henning Barsch: Impact {lens}: "
      + ", ".join(f"{h} {(OPERATIONAL if lens == 'operational' else dict.fromkeys(HORIZONS, 1))[h]}"
                  for h in HORIZONS) + "." for lens in LENSES],
    "Henning Barsch: RTO: 72 h.",
    f"Henning Barsch: MTPD: {BEYOND}.", ""])


def _at_stage_3(tmp_path):
    folder = room(tmp_path, method=NEW)
    (folder / INTERVIEWS / "26_08_00_interview.md").write_text(TRANSCRIPT, encoding="utf-8")
    stage_2 = onward(folder, said(folder, open_bia(folder, "Slaughter")))[0]
    bound = said(folder, stage_2, ENDORSED, picked=stage_2.interviews[0])
    card = onward(folder, bound)[0]
    assert card.stage == STAGE_3
    return folder, card


def _stage_3_decisions(folder):
    return [d for d in read_record(folder, run_file("Slaughter")).get(DECISIONS, [])
            if d.get("stage") == STAGE_3]


def test_the_stage_3_proposal_asks_the_question(tmp_path):
    folder, card = _at_stage_3(tmp_path)
    assert [q.id for q in walk.open_questions(folder, card)] == ["Slaughter.mtpd.asserted"]


@pytest.mark.parametrize("saved", [None, "the run without its activities"])
def test_a_run_with_no_activities_asks_nothing(tmp_path, saved):
    """No activity on the run: nothing to review, so no question, and no record is built from a
    run that has nothing saved yet (the referee would need its run id)."""
    folder, card = _at_stage_3(tmp_path)
    run = None if saved is None else {**(card.saved or {}), "activities": []}
    assert walk.open_questions(folder, replace(card, saved=run, proposal={})) == []


@pytest.mark.parametrize("answer", GRADIENT)
def test_every_gradient_answer_is_refused_while_the_question_is_open(tmp_path, answer):
    folder, card = _at_stage_3(tmp_path)
    cards = walk.answer(folder, "Slaughter", answer, card.revision)
    assert [c.stage for c in cards] == [STAGE_3]
    assert cards[0].body == walk.QUESTION_OPEN and cards[0].buttons == ()
    assert _stage_3_decisions(folder) == [], "nothing was saved at stage 3"
    assert walk.current(folder, "Slaughter").stage == STAGE_3


def _answered_cards(monkeypatch, answer=referee.KEEP):
    """The stage-3 card with his answer on the proposal, as a skin that stores it would draw it."""
    def answered(room_folder, process):
        card = walk.evidence_card(room_folder, process)
        acts = [{**a, ANSWERS: _answer(answer, derived=DERIVED)}
                for a in card.proposal.get("activities") or []]
        return replace(card, proposal={**card.proposal, "activities": acts})

    monkeypatch.setattr(walk, "_WHAT_FOLLOWS", tuple(
        (s, a, answered if f is walk.evidence_card else f) for s, a, f in walk._WHAT_FOLLOWS))


@pytest.mark.parametrize("answer", GRADIENT)
def test_every_gradient_answer_is_taken_once_the_question_is_answered(
        tmp_path, monkeypatch, answer):
    folder, card = _at_stage_3(tmp_path)
    _answered_cards(monkeypatch)
    assert walk.open_questions(folder, walk.current(folder, "Slaughter")) == []
    walk.answer(folder, "Slaughter", answer, card.revision)
    assert [d["gradient"] for d in _stage_3_decisions(folder)] == [answer]


def test_a_withdrawal_in_the_trail_never_answers_a_figure_still_asserted():
    """Ruling (b): a withdrawal is the grid's figure on the record. Stored against a record that
    still asserts another, it answers nothing: the question stands."""
    assert _review(_record(**_answer(referee.WITHDRAW))).questions
    assert "withdrawn" in referee.answer_says(referee.WITHDRAW)


# ── the refused step card, and the method the question is asked against ──────────────────────
def test_the_refused_step_card_carries_no_decision_and_no_rule_of_its_own(tmp_path):
    """The step is not answered and nothing is saved, so the refused card asks nothing of its
    own and states no rule for answering it: `QUESTION_OPEN` says the question comes first, and
    the question's own card carries the figures and his three answers."""
    folder, card = _at_stage_3(tmp_path)
    assert (card.decision, card.rule) == (walk.DECISION_3, walk.RULE_3)
    assert card.decision and card.rule
    refused, = walk.answer(folder, "Slaughter", ENDORSED, card.revision)
    assert refused.body == walk.QUESTION_OPEN
    assert (refused.buttons, refused.decision, refused.rule) == ((), "", "")


def test_a_card_carrying_no_method_copy_is_asked_against_the_room_s_own(tmp_path):
    """A card drawn without a method copy is still checked: `open_questions` falls back to the
    room's method file, so the question is asked of the same parameters either way."""
    folder, card = _at_stage_3(tmp_path)
    assert [q.id for q in walk.open_questions(folder, replace(card, method={}))] == [
        "Slaughter.mtpd.asserted"]


def test_the_card_is_asked_against_the_method_copy_it_was_drawn_with(tmp_path):
    """One check over one set of bytes: the card carries the method it was drawn with, so a
    method file rewritten under the walk does not move what this card is asked against."""
    folder, card = _at_stage_3(tmp_path)
    (folder / walk.METHOD).write_text(
        json.dumps({**NEW, "time_horizons": HORIZONS[:3]}), encoding="utf-8")
    assert [q.id for q in walk.open_questions(folder, card)] == ["Slaughter.mtpd.asserted"]
    assert walk.open_questions(folder, replace(card, method={})) == [], (
        "the rewritten file leaves the grid unreadable, so the fallback asks nothing")


# ── t224: the door answers the question itself, no skin in front of it ───────────────────────
REASON = "Our buyers stop taking carcasses after a week, so >168 h stands"
QUOTE = f"Henning Barsch: MTPD: {BEYOND}."
#: The entries the phone skin writes for the same answers (`skin/PROTOTYPE_core.py::_answers`,
#: t116), recorded byte for byte: the walk's door has to write exactly these.
SKIN_WRITES = {
    "keep": {"answer": "keep", "asserted": BEYOND, "derived": DERIVED, "reason": REASON,
             "says": f"The manager's answer: kept, with his reason, word for word: {REASON}"},
    "keep, no reason": {"answer": "keep", "asserted": BEYOND, "derived": DERIVED,
                        "says": "The manager's answer: kept, no reason given"},
    "withdraw": {"answer": "withdraw", "asserted": BEYOND, "derived": DERIVED, "quote": QUOTE,
                 "says": "The manager's answer: withdrawn, the grid's figure stands"},
    "leave open": {"answer": "leave_open", "asserted": BEYOND, "derived": DERIVED,
                   "says": "The manager's answer: left open for the owners, his decision"},
}


def _typed(folder, *lines):
    """Each line through `walk.answer` alone, at the revision of the card the last one left."""
    cards = ()
    for line in lines:
        cards = walk.answer(folder, "Slaughter", line, walk.current(folder, "Slaughter").revision)
    return cards


def _stage_3_answers(folder):
    """His answers as stage 3 saved them onto the run, and as stage 4's record carries them."""
    run = read_record(folder, run_file("Slaughter"))
    record = read_record(folder, walk.record_file("Slaughter"))
    return run["activities"][0].get(ANSWERS), record["activities"][0].get(ANSWERS)


@pytest.mark.parametrize(("lines", "entry"), [
    (("keep", REASON), "keep"), (("keep", "no"), "keep, no reason"),
    (("withdraw",), "withdraw"), (("leave open",), "leave open")])
def test_the_door_answers_the_question_and_the_record_carries_what_the_skin_writes(
        tmp_path, lines, entry):
    folder, card = _at_stage_3(tmp_path)
    assert [c.body for c in walk.answer(folder, "Slaughter", ENDORSED, card.revision)] == [
        walk.QUESTION_OPEN], "the walk stops at stage 3 on the question"
    _typed(folder, *lines)
    assert walk.open_questions(folder, walk.current(folder, "Slaughter")) == []
    assert walk.current(folder, "Slaughter").stage == STAGE_3, "his answer is not the step's"
    assert _typed(folder, ENDORSED)[-1].stage == walk.STAGE_4, "stage 3 proceeds"
    _typed(folder, ENDORSED)
    carried = {referee.ASSERTED_MTPD: SKIN_WRITES[entry]}
    assert _stage_3_answers(folder) == (carried, carried)
    assert json.dumps(_stage_3_answers(folder)[1]) == json.dumps(carried), "byte for byte"


def test_keep_asks_his_reason_and_the_next_line_is_it_word_for_word(tmp_path):
    folder, _ = _at_stage_3(tmp_path)
    asked, = _typed(folder, referee.KEEP)
    assert asked.stage == STAGE_3 and asked.body == walk.ASK_KEEP_REASON.format(value=BEYOND)
    assert (asked.buttons, asked.decision, asked.rule) == ((), "", "")
    said, = _typed(folder, f"  {REASON}? ")
    assert said.stage == STAGE_3 and said.buttons == GRADIENT, "the step's own answers come back"
    held = read_record(folder, run_file("Slaughter"))
    kept = held[walk.QUESTIONS_ANSWERED]["Slaughter"][referee.ASSERTED_MTPD]
    assert kept["reason"] == f"{REASON}?"
    assert walk.REASON_FOR not in held, "one line is his reason, and the next is the step's again"


@pytest.mark.parametrize("line", ["no", "nothing", "nothing.", "none", "never mind"])
def test_nothing_to_say_after_keep_keeps_it_with_no_reason(tmp_path, line):
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, referee.KEEP, line)
    held = read_record(folder, run_file("Slaughter"))
    assert held[walk.QUESTIONS_ANSWERED]["Slaughter"] == {
        referee.ASSERTED_MTPD: SKIN_WRITES["keep, no reason"]}
    assert walk.REASON_FOR not in held


@pytest.mark.parametrize("line", ["None of the night shift was asked",
                                  "No idea why, but the plant manager set it"])
def test_a_reason_that_starts_with_no_is_kept_word_for_word(tmp_path, line):
    """t236: only the whole line waves a reason off; one that merely starts "No" or "None" is his
    reason, and it reaches the record as he typed it."""
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, referee.KEEP, line)
    kept = read_record(folder, run_file("Slaughter"))[walk.QUESTIONS_ANSWERED]["Slaughter"]
    assert kept[referee.ASSERTED_MTPD]["reason"] == line
    assert kept[referee.ASSERTED_MTPD]["says"].endswith(f"word for word: {line}")


@pytest.mark.parametrize(("words", "answer"), [
    ("Keep", referee.KEEP), ("WITHDRAW", referee.WITHDRAW), ("Leave open", referee.LEAVE_OPEN),
    (referee.LEAVE_OPEN, referee.LEAVE_OPEN)])
def test_the_question_s_own_words_are_its_answers(tmp_path, words, answer):
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, words)
    held = read_record(folder, run_file("Slaughter"))[walk.QUESTIONS_ANSWERED]
    assert held["Slaughter"][referee.ASSERTED_MTPD]["answer"] == answer
    assert _stage_3_decisions(folder) == [], "his answer is not the step's answer"


@pytest.mark.parametrize("words", ["perhaps later", "keep it", "yes"])
def test_any_other_word_is_refused_while_the_question_is_open(tmp_path, words):
    folder, _ = _at_stage_3(tmp_path)
    before = read_record(folder, run_file("Slaughter"))
    refused, = _typed(folder, words)
    assert refused.body == walk.QUESTION_OPEN and refused.buttons == ()
    assert read_record(folder, run_file("Slaughter")) == before, "nothing is saved"


def test_withdraw_puts_the_grid_s_figure_on_the_record(tmp_path):
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, referee.WITHDRAW, ENDORSED, ENDORSED)
    record = read_record(folder, walk.record_file("Slaughter"))["activities"][0]
    assert record["mtpd"] == DERIVED


def _threshold(folder, threshold):
    """The room's method moved under the walk: the grid now derives 72 h at threshold 2."""
    (folder / walk.METHOD).write_text(
        json.dumps({**NEW, "intolerability_threshold": threshold}), encoding="utf-8")


@pytest.mark.parametrize("lines", [("keep", REASON), ("leave open",)])
def test_a_changed_figure_after_the_answer_opens_the_question_again(tmp_path, lines):
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, *lines)
    _threshold(folder, 2)
    asked = walk.open_questions(folder, walk.current(folder, "Slaughter"))
    assert [(q.asserted, q.derived) for q in asked] == [(BEYOND, "72 h")]
    assert _typed(folder, ENDORSED)[-1].body == walk.QUESTION_OPEN
    _threshold(folder, NEW["intolerability_threshold"])
    assert walk.open_questions(folder, walk.current(folder, "Slaughter")) == [], (
        "the figures he answered are back, so his answer answers them again")


def test_after_withdraw_the_mtpd_follows_the_grid_and_nothing_is_asked(tmp_path):
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, referee.WITHDRAW)
    _threshold(folder, 2)
    card = walk.current(folder, "Slaughter")
    assert walk.open_questions(folder, card) == []
    mtpd, = [s["value"] for s in card.proposal["activities"][0]["evidence"] if s["label"] == "MTPD"]
    assert mtpd == "72 h"
    assert card.proposal["activities"][0][ANSWERS] == {
        referee.ASSERTED_MTPD: SKIN_WRITES["withdraw"]}


def test_an_answer_on_a_card_somebody_else_saved_over_is_not_taken(tmp_path):
    folder, card = _at_stage_3(tmp_path)
    _typed(folder, "leave open")
    _threshold(folder, 2)  # the question is asked again, of other figures
    late, = walk.answer(folder, "Slaughter", referee.WITHDRAW, card.revision)
    assert late.body.startswith(walk.OVERTAKEN)
    held = read_record(folder, run_file("Slaughter"))
    assert held[walk.QUESTIONS_ANSWERED]["Slaughter"][referee.ASSERTED_MTPD]["answer"] == (
        referee.LEAVE_OPEN)


def test_a_reason_on_a_card_somebody_else_saved_over_is_not_taken(tmp_path):
    folder, card = _at_stage_3(tmp_path)
    _typed(folder, referee.KEEP)
    late, = walk.answer(folder, "Slaughter", REASON, card.revision)
    assert late.body.startswith(walk.OVERTAKEN)
    assert walk.REASON_FOR in read_record(folder, run_file("Slaughter"))


ASKED = referee.Question("Slaughter", referee.ASSERTED_MTPD, BEYOND, DERIVED)
STATED = {"name": "Slaughter", "evidence": [
    {"label": "RTO", "value": "72 h", "quote": "RTO: 72 h."},
    {"label": "MTPD", "value": BEYOND, "quote": QUOTE}]}


def _held(entry, **moved):
    return {referee.ASSERTED_MTPD: {**SKIN_WRITES[entry], **moved}}


@pytest.mark.parametrize(("question", "held"), [
    (None, _held("keep")), (ASKED, None), (ASKED, {}),
    (ASKED, _held("keep", asserted="24 h")), (ASKED, _held("withdraw", asserted="24 h")),
    (ASKED, _held("keep", derived="72 h")), (ASKED, _held("leave open", derived="72 h"))])
def test_an_answer_to_another_question_or_to_none_leaves_the_activity_as_it_is(question, held):
    assert walk._his_answer_on(STATED, question, held) == STATED


@pytest.mark.parametrize("entry", ["keep", "keep, no reason", "leave open"])
def test_an_answer_to_the_question_asked_is_carried_and_the_figure_stays_his(entry):
    assert walk._his_answer_on(STATED, ASKED, _held(entry)) == {**STATED, ANSWERS: _held(entry)}


def test_a_withdrawal_gives_the_mtpd_the_grid_s_figure_as_it_derives_now():
    moved = replace(ASKED, derived="72 h")
    assert walk._his_answer_on(STATED, moved, _held("withdraw")) == {
        "name": "Slaughter", ANSWERS: _held("withdraw"), "evidence": [
            {"label": "RTO", "value": "72 h", "quote": "RTO: 72 h."},
            {"label": "MTPD", "value": "72 h", "quote": QUOTE}]}


def test_an_answer_for_one_activity_keeps_the_answers_held_for_the_others(tmp_path):
    folder, card = _at_stage_3(tmp_path)
    other = {"Sales": {referee.ASSERTED_MTPD: SKIN_WRITES["leave open"]}}
    run = walk._held(replace(card, saved={**card.saved, walk.QUESTIONS_ANSWERED: other}),
                     walk.open_questions(folder, card)[0], referee.WITHDRAW)
    assert run[walk.QUESTIONS_ANSWERED] == {
        **other, "Slaughter": {referee.ASSERTED_MTPD: SKIN_WRITES["withdraw"]}}
    assert walk.REASON_FOR not in run


# ── ticket 232: a Withdraw typed at the door cites his act on the turn it arrived on ─────────────
#: the record row his act is, as the skin's `_rows` writes it for `his_act` (t132/t171 ruling B)
HIS_ACT_KEYS = {"type", "words", "on", "turn_id"}


def _his_turn(folder, words):
    """The caller's line for the turn his words arrived on, written once the turn is over."""
    return turn_file.write(folder, {"said": words, "how": "typed"}, wording="w", calls=[],
                           clock=lambda: 1_800_000_000.0, new_id=lambda: "t-232")["turn_id"]


def _mtpd_rows(folder):
    evidence = read_record(folder, walk.record_file("Slaughter"))["activities"][0]["evidence"]
    return ([e for e in evidence if e.get("type") == "chat_confirmation"],
            [e for e in evidence if e.get("quote") == f"Henning Barsch: MTPD: {BEYOND}."])


def test_a_withdraw_typed_at_the_door_cites_his_act_on_the_turn_it_arrived_on(tmp_path):
    folder, _ = _at_stage_3(tmp_path)
    walk.answer(folder, "Slaughter", referee.WITHDRAW,
                walk.current(folder, "Slaughter").revision, turn_id="t-232")
    _his_turn(folder, referee.WITHDRAW)
    _typed(folder, ENDORSED, ENDORSED)
    acts, quotes = _mtpd_rows(folder)
    assert acts == [{"type": "chat_confirmation", "words": referee.WITHDRAW, "on": "2027-01-15",
                     "turn_id": "t-232"}], "his act on his turn, no nemo sentence on it"
    assert set(acts[0]) == HIS_ACT_KEYS, "the row shape the skin's Withdraw tap gives"
    assert quotes == [], "the interview's quote of the figure he withdrew is in the trail only"
    record = read_record(folder, walk.record_file("Slaughter"))["activities"][0]
    assert record["mtpd"] == DERIVED
    assert record[ANSWERS] == {referee.ASSERTED_MTPD: SKIN_WRITES["withdraw"]}, "trail unchanged"


def test_a_withdraw_at_the_door_with_no_turn_keeps_the_interview_s_quote_as_today(tmp_path):
    """171m6's reading: with no turn to cite, the row behind the MTPD is the interview's quote."""
    folder, _ = _at_stage_3(tmp_path)
    _typed(folder, referee.WITHDRAW, ENDORSED, ENDORSED)
    acts, quotes = _mtpd_rows(folder)
    assert acts == [] and [q["type"] for q in quotes] == ["transcript_quote"]
    evidence = read_record(folder, walk.record_file("Slaughter"))["activities"][0]["evidence"]
    assert {e["type"] for e in evidence} == {"transcript_quote"}


@pytest.mark.parametrize(("lines", "entry"), [
    (("keep", REASON), "keep"), (("leave open",), "leave open")])
def test_a_turn_given_with_keep_or_leave_open_changes_nothing(tmp_path, lines, entry):
    folder, _ = _at_stage_3(tmp_path)
    first, *rest = lines
    walk.answer(folder, "Slaughter", first, walk.current(folder, "Slaughter").revision,
                turn_id="t-232")
    _typed(folder, *rest, ENDORSED, ENDORSED)
    acts, quotes = _mtpd_rows(folder)
    assert acts == [] and len(quotes) == 1
    carried = {referee.ASSERTED_MTPD: SKIN_WRITES[entry]}
    assert _stage_3_answers(folder) == (carried, carried)


@pytest.mark.parametrize(("said", "held"), [(referee.WITHDRAW, True), (referee.KEEP, False),
                                            (referee.LEAVE_OPEN, False)])
def test_only_a_withdraw_holds_the_turn_it_was_given(tmp_path, said, held):
    folder, card = _at_stage_3(tmp_path)
    question = walk.open_questions(folder, card)[0]
    entry = walk._held(card, question, said, "t-232")[walk.QUESTIONS_ANSWERED]["Slaughter"]
    assert (entry.get("turn_id") == "t-232") is held
    assert walk._held(card, question, said) == walk._held(card, question, said, None)


def test_a_turn_not_on_the_room_s_file_gives_no_words_and_no_turn_gives_no_act(tmp_path):
    assert walk._his_act(tmp_path, {"turn_id": "t-9"}) == {
        "type": "chat_confirmation", "words": "", "on": "", "turn_id": "t-9"}
    assert walk._his_act(tmp_path, None) is None
    assert walk._his_act(tmp_path, _held("withdraw")) is None


def test_his_act_reads_the_turn_it_held_and_not_his_first_on_the_file(tmp_path):
    """t232d: with two turns of his on the file, the act is the held one's, never the first's."""
    for turn_id, words, at in (("t-1", "keep", 1_800_000_000.0),
                               ("t-2", "withdraw", 1_800_100_000.0)):
        turn_file.write(tmp_path, {"said": words, "how": "typed"}, wording="w", calls=[],
                        clock=lambda at=at: at, new_id=lambda turn_id=turn_id: turn_id)
    assert walk._his_act(tmp_path, {"turn_id": "t-2"}) == {
        "type": "chat_confirmation", "words": "withdraw", "on": "2027-01-16", "turn_id": "t-2"}
    assert walk._his_act(tmp_path, {"turn_id": "t-9"}) == {
        "type": "chat_confirmation", "words": "", "on": "", "turn_id": "t-9"}, "not on the file"


def test_a_withdrawal_with_his_act_cites_it_under_the_mtpd_alone_and_the_trail_drops_the_turn():
    act = {"type": "chat_confirmation", "words": "withdraw", "on": "2027-01-15", "turn_id": "t-2"}
    held = {**_held("withdraw"), "turn_id": "t-2"}
    assert walk._his_answer_on(STATED, ASKED, held, act) == {
        "name": "Slaughter", ANSWERS: _held("withdraw"), "evidence": [
            {"label": "RTO", "value": "72 h", "quote": "RTO: 72 h."},
            {"label": "MTPD", "value": DERIVED, "quote": QUOTE, walk.bia.HIS_ACT: act}]}
