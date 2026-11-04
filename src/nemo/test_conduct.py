"""Properties of the interview held in the room: what is asked, and what is written down.

`nemo.conduct` is the second of the demo skin's two model jobs (ADR-0008) and the one that must
not conclude. Everything below is stated against the module rather than through the walk, because
the thing this module owes its caller is narrow and exact: one question at a time, the manager's
own words kept verbatim, and an end that says which of its two ends it is.

Nothing here reaches a model. The lane is a function the caller passes, which is how the cap is
provoked on demand — a 402 and a refused connection are one `LaneUnavailable` (`nemo.lane`), so a
lane that raises it is the cap as far as this module can tell.
"""

import logging
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from nemo.conduct import (
    ANSWERED,
    ASKED,
    CARD,
    FRONT_MATTER,
    HEADING,
    NOT_STARTED,
    STOPPED,
    TURNS,
    Conducted,
    Turn,
    conduct,
    prompt,
    transcript,
)
from nemo.evidence import DURATIONS, OWNER_STATED, standardise
from nemo.interview import _departments_in, text
from nemo.lane import LaneUnavailable

#: A process as a room's files spell one, the shape `nemo.test_interview` draws.
PROCESSES = st.text(alphabet="abcXY Z0,-", min_size=1, max_size=8).map(str.strip).filter(bool)

#: What is said in an interview, on either side of it. Any character a file can hold, because the
#: whole claim of this module is that it writes down what was said rather than a version of it.
SAID = st.text(st.characters(codec="utf-8"), max_size=120)

TURNS_STRATEGY = st.lists(st.builds(Turn, SAID, SAID), max_size=4).map(tuple)

#: An interview in which nobody states a figure. Lower case and a full stop: the four labels and
#: `Depends on` all carry a capital, so no draw from this alphabet can state one by accident, and
#: no colon means no line of it can be read as somebody speaking either. That is what makes the
#: two properties below about `nemo.conduct` rather than about what hypothesis happened to draw.
QUIET = st.text(alphabet="abcdefghijk .", max_size=40)

QUIET_TURNS = st.lists(st.builds(Turn, QUIET, QUIET), max_size=3).map(tuple)


def asking(questions):
    """A lane that asks those questions in order, and records every prompt it was handed."""
    asked = []

    def lane(sent):
        asked.append(sent)
        return questions[(len(asked) - 1) % len(questions)]

    lane.prompts = asked
    return lane


def dead(_prompt):
    """The lane the cap leaves behind: every call fails at once (ADR-0009)."""
    raise LaneUnavailable("the lane did not answer")


# ── what is written down ─────────────────────────────────────────────────────


@given(PROCESSES, TURNS_STRATEGY)
def test_the_transcript_holds_every_question_and_answer_verbatim(process, turns):
    """The referee hunts quotes in this file, so a word rephrased here is a quote it cannot find."""
    written = transcript(process, turns)
    for turn in turns:
        assert turn.question in written
        assert turn.answer in written


@given(PROCESSES, TURNS_STRATEGY)
def test_the_transcript_keeps_them_in_the_order_they_happened(process, turns):
    """A question-and-answer reordered is a different interview, whatever words it holds."""
    written = transcript(process, turns)
    at = -1
    for turn in turns:
        found = written.index(turn.question, at + 1)
        assert found > at
        at = found


@given(PROCESSES, TURNS_STRATEGY)
def test_the_transcript_is_filed_under_the_process_it_is_about(process, turns):
    """The room reads its own evidence back by department, so this is what makes it evidence."""
    assert _departments_in(transcript(process, turns)) == [process]


@given(PROCESSES, TURNS_STRATEGY)
def test_the_transcript_reads_back_off_disk_exactly_as_it_was_shown(process, turns):
    """What is previewed is what is filed, byte for byte — the story's second scenario."""
    written = transcript(process, turns)
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "interview.md"
        target.write_bytes(written.encode())
        assert text(target) == written


@given(PROCESSES, TURNS_STRATEGY)
def test_nothing_is_written_down_but_what_was_said_and_what_files_it(process, turns):
    """Take each turn's own two lines out and what is left is an empty interview's scaffolding:
    the front matter, the heading, and nothing else. No summary, no conclusion, no tidying."""
    written = transcript(process, turns)
    for turn in turns:
        written = written.replace(ASKED.format(question=turn.question), "", 1)
        written = written.replace(ANSWERED.format(answer=turn.answer), "", 1)
    assert written.strip() == transcript(process, ()).strip()


@given(PROCESSES, TURNS_STRATEGY)
def test_the_fence_and_the_heading_each_stand_on_their_own_line_with_a_blank_line_under_it(
        process, turns):
    """The file is markdown a manager reads and the referee quotes out of, and a blank line is
    what makes the top of it that: a fence the first speaker's line is pressed against is front
    matter no reader can take apart, and a heading with a line under it is not a heading at all.
    The heading names this process, because a room holds one interview per process and a file
    headed for another is evidence filed under the wrong name."""
    lines = transcript(process, turns).split("\n")
    fence = FRONT_MATTER.format(process=process).split("\n")
    assert lines[:len(fence)] == fence
    assert lines[len(fence)] == ""
    assert lines[len(fence) + 1] == HEADING.format(process=process)
    assert lines[len(fence) + 2] == ""


# ── what the model is asked for ──────────────────────────────────────────────


@given(PROCESSES, TURNS_STRATEGY)
def test_the_model_is_told_to_conduct_and_never_to_conclude(process, turns):
    """The four figures by name: stage 3 reads those out of a transcript that states them, and a
    figure the model supplied here would be testimony nobody gave."""
    card = prompt(process, turns)
    for figure in ("MTPD", "RTO", "RPO", "MBCO"):
        assert figure in CARD
    assert CARD.format(process=process) in card


@given(PROCESSES, TURNS_STRATEGY)
def test_the_model_is_left_asking_one_thing_and_told_how_to_count_it(process, turns):
    """`docs/voice.md` §1 — one decision per card — for the one card a model writes the words of.

    The live run of 2026-09-13 put a question and then three answers to choose between in the same
    turn, so the rule is spelled as something a model can check about its own sentence: a single
    question mark, last. Read off the prose like the property above it, for the same reason: what
    the lane is asked for is all this module can promise, and section J of
    `archive/qa/stage-2-the-live-interview-path.md` is where a real model is held to it.
    """
    card = prompt(process, turns)
    assert "a single question mark" in CARD and "let it be the last of it" in CARD
    assert "never offer them answers to choose between" in CARD
    assert CARD.format(process=process) in card


@given(PROCESSES, TURNS_STRATEGY)
def test_the_model_is_handed_the_interview_so_far_in_their_own_words(process, turns):
    """It follows what was already said, so what was already said has to reach it unedited."""
    card = prompt(process, turns)
    for turn in turns:
        assert turn.question in card
        assert turn.answer in card


@given(PROCESSES, QUIET_TURNS)
def test_the_interview_reaches_the_model_in_the_lines_the_file_holds_it_in(process, turns):
    """The docstring's promise, stated as an equality: one text, not a private encoding of it.

    The card, one blank line, and then each turn as the two labelled lines the transcript writes,
    a blank line after each. A separator only this module understands would be a second spelling
    of the interview, and the thing the model read would stop being the thing a human reads.
    """
    said = [line for turn in turns
            for line in (ASKED.format(question=turn.question),
                         ANSWERED.format(answer=turn.answer), "")]
    assert prompt(process, turns) == "\n".join([CARD.format(process=process), "", *said])


# ── one question at a time ───────────────────────────────────────────────────


@given(PROCESSES, TURNS_STRATEGY, SAID.filter(bool))
def test_the_question_is_the_lanes_own_words(process, turns, question):
    """The room does not tidy what the model asked any more than it tidies what the manager said."""
    assert conduct(process, turns[:TURNS - 1], lane=asking([question])) == Conducted(
        question=question)


@given(PROCESSES, TURNS_STRATEGY, SAID.filter(bool))
def test_a_lane_that_answers_in_the_transcripts_own_lines_is_not_labelled_twice(
        process, turns, question):
    """Seen on the live lane of 2026-09-13: handed the interview in the lines it is filed in, the
    model answered in them too, and the file read "Interviewer: Interviewer: …" — a quote the
    referee would hunt and not find. The label is the transcript's to write, and it writes it once.
    """
    echoed = asking([ASKED.format(question=question)])
    assert conduct(process, turns[:TURNS - 1], lane=echoed) == Conducted(question=question)
    assert transcript(process, (Turn(question, "yes"),)).count(ASKED.format(question="")) == 1


@given(PROCESSES, QUIET_TURNS)
def test_the_lane_is_handed_the_card_and_the_interview_so_far_and_nothing_else(process, turns):
    """What reaches the lane is the whole of the prompt: the instruction not to conclude and the
    process it is about are both inside it, so a call that dropped either would be a model asking
    whatever it liked about it knows not what — and every property above would stay green, because
    they all read the prompt rather than what was sent."""
    lane = asking(["and then?"])
    conduct(process, turns, lane=lane)
    assert lane.prompts == [prompt(process, turns)]


@given(PROCESSES)
def test_the_interview_ends_once_it_has_asked_what_it_asks(process):
    """A fixed length, so a manager knows it ends — and the lane is not called again after it."""
    lane = asking(["one more?"])
    turns = tuple(Turn(f"q{index}", f"a{index}") for index in range(TURNS))
    assert conduct(process, turns, lane=lane).question == ""
    assert lane.prompts == [], "the lane was called about an interview that was already over"


@given(PROCESSES, st.integers(min_value=0, max_value=TURNS - 1))
def test_it_keeps_asking_until_then(process, answered):
    turns = tuple(Turn(f"q{index}", f"a{index}") for index in range(answered))
    assert conduct(process, turns, lane=asking(["and then?"])).question == "and then?"


# ── the lane goes quiet ──────────────────────────────────────────────────────


#: At least one answer given: a stop then has something "below" to point at.
ANSWERED_TURNS = st.lists(st.builds(Turn, SAID, SAID), min_size=1, max_size=4).map(tuple)


@given(PROCESSES, ANSWERED_TURNS)
def test_a_lane_that_does_not_answer_ends_the_interview_in_one_plain_sentence(process, turns):
    """The cap arrives here exactly as it does in the ask lane, and stops rather than degrades."""
    assert conduct(process, turns[:TURNS - 1], lane=dead) == Conducted(note=STOPPED)


@given(PROCESSES)
def test_a_lane_that_stops_at_the_first_call_says_the_interview_could_not_start(process):
    """Ticket 194: nothing has been said yet, so STOPPED's "everything you have told me so far is
    below" would be untrue; the manager is told it could not start, and promised nothing below."""
    assert conduct(process, (), lane=dead) == Conducted(note=NOT_STARTED)


def test_what_it_says_about_it_names_no_status_code_service_or_exception():
    """`docs/voice.md` §3: what it means for you, and what is unaffected. Nothing machine."""
    for said in (STOPPED, NOT_STARTED):
        for machine in ("402", "OpenRouter", "openrouter", "LaneUnavailable", "Traceback",
                        "127.0.0.1", "4000", "http", "cap", "key"):
            assert machine not in said
        assert said.count(".") >= 1 and "\n" not in said
    assert "below" not in NOT_STARTED and "start" in NOT_STARTED


@given(PROCESSES, ANSWERED_TURNS)
def test_what_was_already_captured_is_not_lost_when_it_stops(process, turns):
    """The turns are the caller's and were never this module's to drop: what there is of the
    interview reads back after the stop exactly as it read before it."""
    captured = transcript(process, turns[:TURNS - 1])
    stopped = conduct(process, turns[:TURNS - 1], lane=dead)
    assert stopped.question == "" and stopped.note == STOPPED
    assert transcript(process, turns[:TURNS - 1]) == captured


# ── what stage 3 reads back out of it ────────────────────────────────────────
#
# `nemo.conduct` writes a filed interview and `nemo.evidence` reads one, and the two never meet:
# neither imports the other, and the shape they agree on — a `---` fence, a `department:` line
# under it, one speaker to a line — is spelled separately in each. That is the right direction for
# the edges (the word they share is `nemo.record`'s `DEPARTMENT`, below them both) and it leaves
# the agreement itself unpinned: the writer could grow a second fence or a bolded label and every
# test in either module would stay green while stage 3 quietly read a different file.
#
# So the two properties below compose the pure halves rather than restating either. They are also
# where the story's "the model conducts; it does not conclude" is actually observable: the test
# above it reads that promise off `CARD`'s prose, which says only what the lane was asked for.


@given(PROCESSES, QUIET_TURNS)
def test_an_interview_that_states_no_figure_has_none_read_out_of_it(process, turns):
    """The done-when box, at the place a card would read it rather than in the prompt.

    Nobody in this interview says a figure, so stage 3 asserts none — and the front matter and the
    heading the *room* wrote do not become testimony either, which is the whole job of the fence.
    """
    draft = standardise(transcript(process, turns), {}, ())
    assert draft.statements == ()
    assert draft.dependencies == ()


@given(PROCESSES, QUIET_TURNS, st.sampled_from(DURATIONS), st.integers(min_value=1, max_value=99))
def test_a_figure_the_owner_states_is_read_back_as_theirs_and_verbatim(
        process, quiet, label, hours):
    """The evidence the referee will later hunt quotes in, hunted once here.

    One answer states a time. Stage 3 has to find it, attribute it to the person `nemo.conduct`
    labelled the line with, and quote the line as it stands — the quote is what the referee checks
    against the file, so a label either module reworded is a quote that is no longer in it.
    """
    answer = f"{label}: {hours} h"
    turns = (*quiet, Turn("and how long could you tolerate an outage of it.", answer))
    draft = standardise(transcript(process, turns), {}, ())
    assert [(found.label, found.value, found.speaker) for found in draft.statements] == [
        (label, f"{hours} h", "Owner")]
    assert draft.statements[0].quote == ANSWERED.format(answer=answer)
    assert draft.statements[0].owner_stated == (label in OWNER_STATED)


def test_the_stop_is_one_warning_on_this_module_s_own_logger(caplog):
    """Ticket 191 again, read as the journal reads it: "the journal is told why" means one
    warning on `nemo.conduct` — the module a human greps the unit's journal for — saying that
    the interview stopped, with the exception's type and its text after it."""
    with caplog.at_level(logging.WARNING):
        assert conduct("Payroll", (Turn("What does it do?", "Pays people."),),
                       lane=dead) == Conducted(note=STOPPED)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [r.name for r in warnings] == ["nemo.conduct"], "not on the module's own logger"
    assert warnings[0].getMessage() == (
        "the interview stopped: LaneUnavailable: the lane did not answer")


def test_why_it_stopped_reaches_the_log_and_never_the_screen(caplog):
    """Ticket 191: the stop used to be swallowed without a word, and finding its cause took an
    instrumented clone. The log gets the exception's type and text; the manager gets STOPPED (or,
    at the first call, NOT_STARTED: ticket 194)."""

    def timed_out(_prompt):
        raise LaneUnavailable("http://127.0.0.1:4000 did not answer in 2 tries: timed out")

    with caplog.at_level(logging.WARNING, logger="nemo.conduct"):
        said = conduct("Payroll", (Turn("What does it do?", "Pays people."),), lane=timed_out)

    assert said == Conducted(note=STOPPED)
    assert "LaneUnavailable" in caplog.text
    assert "did not answer in 2 tries: timed out" in caplog.text
