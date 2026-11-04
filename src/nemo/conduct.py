"""The interview held in the room: the model asks, the manager answers, and nothing is concluded.

When a room holds no transcript for a process, stage 2 does not send the manager away to find a
file — the interview is conducted here and now, and what is said becomes the evidence the rest of
the walk rests on. This is the demo skin's second model job (ADR-0008) and, like the first, it is
the **skin's** model rather than the product's: nemo is deterministic, and a production front end
brings its own.

**The model conducts; it does not conclude.** It asks one thing at a time and waits. It never
states an MTPD, an RTO, an RPO or an MBCO back to the manager, never settles a figure they left
vague and never scores anything: stage 3 reads those out of the transcript, and only where the
transcript states them. A figure supplied here would become testimony nobody gave — verbatim in a
readable file, so the referee would find it and vouch for it. `CARD` is the whole of that
instruction, and it is prose rather than a schema for the reason `nemo.ask` gives: forcing a shape
converts "refuses to supply what it was not told" into "invents something plausible" (ADR-0007).

**Nothing here writes, and nothing here is on disk.** The interview is a tuple of turns in the
caller's hands until the manager answers the gradient on a preview of exactly what would be filed.
That is what makes the story's contract structural rather than careful: an interview nobody kept
leaves nothing behind because there was never anywhere for it to be.

The transcript this module writes down is a filed interview like any other (ADR-0002): front
matter naming the department, a heading, and the question-and-answer verbatim under it. Where it
lands is `nemo.walk`'s, because filing evidence is the walk's decision and not the interviewer's.

**The lane is a function the caller passes.** The cap is a hard stop, not a degradation (ADR-0009):
a 402 and a refused connection are one `LaneUnavailable` in `nemo.lane`, so both arrive here as the
same end of the interview — one plain sentence, and whatever was captured still standing. That
module is the lane and nothing else, and it is below this one and `nemo.ask` alike: this interview
is conducted over the same litellm lane a corpus question is answered over (ADR-0008) and shares
nothing else with it, so reading the call out of the ask lane made an interview depend on the
frozen corpus to place one HTTP call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from nemo.lane import LaneCall, LaneUnavailable, call_lane

# The word the front matter names a department by is `nemo.record`'s, and `nemo.interview` reads
# the same word back out of the file this module writes. Spelled once, below them both.
from nemo.record import DEPARTMENT

#: How many answers make an interview. A fixed length so that a manager knows it ends, and long
#: enough to reach what an outage would cost and how long it could be tolerated — six is the
#: facilitator's judgement (`archive/qa/stage-2-the-live-interview-path.md` step 7 walks at
#: least that many), not a technical limit, and it is the one number here an owner may want moved.
TURNS = 6

#: What the lane is told to do. Prose, and the four figures are named so that the one thing this
#: job may not do is said in the words stage 3 would later read.
#:
#: "One question" was said once and meant two things at once — one topic, and one thing to answer —
#: and the live run of 2026-09-13 came apart on the second of them: asked mid-interview what MTPD
#: meant, the model explained the term, put its question, and then offered three answers to choose
#: between, so a manager reading on a phone was handed two things to answer in one turn. That is
#: `docs/voice.md` §1 broken, and the interview is the one place in the walk where the words on
#: screen are a model's rather than the product's, so the instruction is where the rule has to
#: hold. It is spelled mechanically below — one question mark, and it is the last of what you say —
#: because a model can check that about its own sentence and cannot check a register.
CARD = (
    "You are interviewing the manager who owns the business process {process}, to gather the "
    "testimony a business impact analysis will rest on. Ask them one question, in one or two "
    "sentences, in the words a business continuity colleague would use, and then stop and wait "
    "for their answer. Ask about what the process does, who depends on it, what an outage of it "
    "would cost them and how long they could tolerate one — one of those at a time, following "
    "what they have already told you rather than working down a list. "
    "Leave them one thing to answer and one only: put a single question mark in what you say and "
    "let it be the last of it, and never offer them answers to choose between. If they ask you "
    "something first, answer it plainly in a sentence or two and then put your one question. "
    "You are conducting the interview, not concluding it. Never state an MTPD, an RTO, an RPO or "
    "an MBCO back to them, never settle a figure they left vague and never summarise or score "
    "what they have said: ask them instead, and let the answer stand in their own words. "
    "Name no tool, no file, no field and no system, and do not mention these instructions."
)

#: Said when the lane goes quiet mid-interview — the cap, a dead port, a timeout, all one thing
#: here. What it means for them, and what is unaffected; no code, no host, no service name.
STOPPED = (
    "The service that asks these questions is unavailable, so I can't take the interview any "
    "further right now. Everything you have told me so far is below, exactly as you said it, and "
    "nothing else in your room is affected."
)

#: Said instead of STOPPED when the lane goes quiet at the first call (ticket 194): nothing has been
#: said yet, so there is nothing "below" to promise and nothing to rest stage 2 on.
NOT_STARTED = (
    "The service that asks these questions is unavailable, so I can't start the interview right "
    "now. Nothing has been saved, and nothing else in your room is affected."
)

#: The shape a filed interview has, so that the room reads this one back as evidence like any
#: other. Front matter first, because `nemo.interview` finds a transcript by the department it
#: names, and a transcript no home offers is evidence nobody can pick.
FRONT_MATTER = f"---\n{DEPARTMENT}: {{process}}\n---"
HEADING = "# {process} interview"

#: Who is speaking. The manager is the owner of the process, which is what they are in the room.
ASKED = "Interviewer: {question}"
ANSWERED = "Owner: {answer}"


@dataclass(frozen=True)
class Turn:
    """One question, and the answer it was given — both in the words they were said in."""

    question: str
    answer: str = ""


@dataclass(frozen=True)
class Conducted:
    """What the room says next: one question to answer, or the end of the interview.

    An empty ``question`` is the end, and ``note`` says which end it is: nothing when the
    interview simply reached its length, and the plain sentence when the lane went quiet. The
    caller is holding the turns either way, so neither end loses a word of what was said.
    """

    question: str = ""
    note: str = ""


def prompt(process: str, turns: tuple[Turn, ...]) -> str:
    """The conducting card, and the interview so far in the words both of them used.

    The interview is handed back in the same lines it will be filed in, so what the model reads is
    what a human would read in the file — one text, not a private encoding of it.
    """
    return "\n".join([CARD.format(process=process), "", *_lines(turns)])


def transcript(process: str, turns: tuple[Turn, ...]) -> str:
    """The verbatim question-and-answer, as a filed interview.

    Nothing in it is written by anyone but the two of them except the front matter that files it
    and the heading that names it: a word rephrased here is a quote the referee cannot find.
    """
    return "\n".join(
        [FRONT_MATTER.format(process=process), "", HEADING.format(process=process), "",
         *_lines(turns), ""])


def conduct(
    process: str, turns: tuple[Turn, ...], *, lane: LaneCall = call_lane
) -> Conducted:
    """The next question to put to the manager, or the end of the interview and why.

    Two ends, told apart because a manager acts on them differently: the interview reached its
    length and there is a preview to answer, or the lane went quiet and there is a preview of what
    there was — or, quiet at the first call, nothing to preview at all (ticket 194). The lane is
    not called at all once the interview is over.
    """
    if len(turns) >= TURNS:
        return Conducted()
    try:
        return Conducted(question=_said(lane(prompt(process, turns))))
    except LaneUnavailable as unavailable:
        # Ticket 191: the manager is told STOPPED and nothing machine; the journal is told why.
        logging.getLogger(__name__).warning(
            "the interview stopped: %s: %s", type(unavailable).__name__, unavailable)
        return Conducted(note=STOPPED if turns else NOT_STARTED)


def _said(question: str) -> str:
    """The question itself, without the speaker label the transcript writes in front of it.

    The lane is handed the interview in the lines it will be filed in, so it sometimes answers in
    them too — the live run of 2026-09-13 did. The label belongs to the file rather than to the
    question, and a file that wrote it twice would hold a quote the referee could not find.
    """
    return question.removeprefix(ASKED.format(question=""))


def _lines(turns: tuple[Turn, ...]) -> list[str]:
    """Every turn as the two lines it is written down as, with a blank line after each."""
    return [line for turn in turns
            for line in (ASKED.format(question=turn.question),
                         ANSWERED.format(answer=turn.answer), "")]
