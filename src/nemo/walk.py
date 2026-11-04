"""The walk: which processes a room holds, Stage 1's scope card, and Stage 2's interview binding.

A room link lands a manager here, the room's own files say which processes are on offer, opening
one gives a card, and a press puts a decision on disk that survives the page closing. Stage 2 is
the same shape over the evidence: the interviews are already in the room, each shown with its own
bytes, and the one the manager presses is bound to the walk with its fingerprint beside it — so
the referee's later claim that no quote was invented is a claim about a file somebody chose after
reading it (ADR-0002). Everything is shaped by three rules this module obeys:

**The server serves state; it never interrogates the human.** ``open_bia`` reads the room and
nothing else, and there is deliberately no way for any caller — a page, a model, an operator — to
name the stage it wants served (ADR-0010). The card that comes back is the card for the state on
disk, so discarding every word of the conversation costs nothing.

**Nothing begins because the model said it would.** Opening a BIA writes not one byte. The run
file appears at the first press and never before, which is what makes walk 15's failure mode —
the model narrating a tool call it never made — leave no trace to be mistaken for work.

**The method is the room's own.** Five parameters are copied verbatim out of the room's
``method.json`` and nothing is supplied for a parameter the file does not carry. A threshold that
reads the same whatever the room says is hard-coding, and hard-coding is the defect. Which five,
and what the file calls them, is ``nemo.method``'s — the referee reads the same names back out of
the record, and a name spelled here as well could drift on one side without a test noticing.

The voice of every string here is ``docs/voice.md``: prose on top, structure underneath. The
decision the card asks for, the rule it is asked under and the four-way gradient sit on the card
as data; the manager reads the paragraph and presses.

**Which controls a card draws is ADR-0011, and the two stages differ on purpose.** Stage 1 offers
one control: it confirms the scope the room read off the company's own files, there is no figure
yet, and nothing to hold a reservation about. Stage 2 binds the evidence the whole BIA rests on
and is answered with the four labels. The labels ride in the record underneath both, so nothing
downstream special-cases a Stage 1 decision — and Stage 1 is not to be "fixed" to match Stage 2.

``Card.screen`` is what a card puts in front of a human, and the skin sends nothing that has not
been through ``nemo.card.render`` first. The two modules are siblings in the layers contract and
neither imports the other: the check belongs on the card path, and the card path is the skin's.

**What a room must carry.** A process is offered under the name its own files give it, because the
manager presses that name rather than typing it. Both sources spell it the same way, under a
``department:`` line in a transcript's front matter and a ``department`` key in the dependency
register — wherever the register names one, owner or consumer. The register's ``owning_dept`` and
``consumers[].dept`` slugs are not that name: they are internal, German and unreadable on a card,
and deriving a display name from one would be inventing it.

**What the room's interviews say is ``nemo.interview``'s and not read twice.** The evidence a room
holds — which interviews are on file, what each says in its own characters, and the digest that
says whether it still says it — is one reader below this module, because the walk is not the only
thing that reads it: Stage 1 names the same files on its ``Source:`` line, a later stage quotes
them and the referee checks the quote against them.

**A walk may only carry forward a record its own run produced.** A minted room ships a BIA
already in progress, deliberately (ticket 02, owner call), and the defence is ticket 15's
``run_id`` binding: a run mints its identity here, carries it on the record it writes, and
``move_past_stage_4`` refuses any other. It rests on run identity and never on a modification
time — ``nemo.bia`` says why a real record has no such field to rest on.

**Stage 5 is where the walk ends, and it ends twice over.** The handover is accepted with one
gradient answer, which moves the run to ``reviewed_pending_owner`` and writes two documents and no
certificate; and then it is signed, which closes the run and writes the certificate **iff** the
signer is the owner the record holds for the activity. The documents themselves are
``nemo.handover``'s, one layer down, because they are a function of the two records on disk and of
nothing in this module. There is no sixth stage: a dependency nobody owns is a finding carried to
the signature and accepted by its id.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nemo import (
    bia,
    conduct,
    evidence,
    figures,
    handover,
    interview,
    referee,
    refusal,
    text,
    turn_file,
    views,
)
from nemo.method import BEYOND_HORIZONS
from nemo.method import ORG as METHOD_ORG
from nemo.method import PARAMETERS as METHOD_PARAMETERS
from nemo.method import lenses as method_lenses

# `Record` is `nemo.record`'s own name. Ticket 09 moved it there and `room_store` only
# re-imports it, so taking it from `room_store` is an implicit re-export mypy refuses.
#
# The run's own fields come from there too, because `nemo.handover` reads back what this module
# writes and sits below it (ticket 18's architect pass). Three of them arrive under a `_FIELD`
# name: this module already says `GRADIENT`, `NAMING` and `ACCEPTED` to a human — the four labels
# on a card, the sentence that asks for a reservation in words, and the sentence that says the BIA
# is written — and a field is not a sentence. The alias is what keeps both spellings honest
# instead of one quietly winning.
from nemo.record import ACCEPTED as ACCEPTED_FIELD
from nemo.record import (
    ACTIVITIES,
    ANSWERS,
    AT_STAGE,
    AT_TIME,
    CAPACITY,
    CARRIED,
    CHAT_CONFIRMATION,
    DECISIONS,
    DEPARTMENT,
    DEPT,
    EVIDENCE,
    FINDINGS,
    KIND,
    MODEL_NOTES,
    ON,
    ON_CARD,
    PARTS,
    PENDING_REFERRALS,
    REFERRED_TO,
    REFERS,
    REFUSALS,
    REGISTER_NO_RPO,
    REGISTER_ROW,
    ROLE,
    SIGNATURE,
    SIGNER,
    SOURCE_PATH,
    STATUS,
    TURN_ID,
    TYPE,
    UNNAMED,
    WORDS,
    Record,
    fingerprint,
)
from nemo.record import GRADIENT as GRADIENT_FIELD
from nemo.record import NAMING as NAMING_FIELD
from nemo.room_code import NO_FOLDER, Refused, mintable
from nemo.room_store import (
    PathRefused,
    StaleWrite,
    jailed_path,
    read_record,
    room_lock,
    write_document,
    write_file,
    write_record,
)

#: Where a room keeps the two files a Stage 1 proposal is read from besides its interviews, and
#: where a walk is kept. The interviews' own two folders are ``nemo.interview``'s.
REGISTER = "03_Dependencies/dependency-register.json"
METHOD = "02_BCM-Method/method.json"
RUNS = "output/.bia-runs"
#: Where a walk keeps its run as it stood when stage 3 closed, which is what `reopen` goes back to.
#: A folder of its own, so a listing of the runs never takes one for a run.
AT_STEP_3 = f"{RUNS}/at-step-3"

#: What the BIA a walk produces is called in its process's own folder (``record_file``).
RECORD_NAME = "bia-record.json"

#: Where a room kept its one record before ticket 235. Read by ``_record_at`` and moved off by
#: ``_land``, and by nothing else.
_LEGACY_RECORD = f"output/{RECORD_NAME}"

#: Which run wrote each of stage 5's documents, in their folder (ticket 245): the run's id under
#: the document's name, written after the document. A dot file, so it is nemo's working state and
#: never an artefact. A document it does not name was written before 245, by the run on file.
WRITTEN_BY = ".written-by.json"

#: Where an earlier walk's signed certificate goes when its process is walked again (ticket 245):
#: beside the new documents, under the id of the run that signed it.
SET_ASIDE = handover.CERTIFICATE.removesuffix(".md") + "-{run}.md"

#: What the run carries to say which record stage 4 bound: the record's fingerprint and its schema
#: version, and nothing about a page (ADR-0040: the grouped graph the skin draws is the only one,
#: and nemo draws none of its own). Read on the way past stage 4 and written by nothing but the
#: second movement. The key keeps its old name so every run saved before ticket 243 still reads.
RECEIPT = "graph_receipt"

#: What the run carries to say which interviews he confirmed at stage 2, as room paths in his
#: order, the bound one among them (ticket 168). Written by stage 2 alone; a run saved before
#: 168 has none and reads as its one bound transcript.
INTERVIEWS_CONFIRMED = "interviews"

#: t432 (his answer, 2026-10-11): each stage's one short name (`CONTEXT.md` "Stage"), which every
#: "Stage N of 5" line says: the phone's strip, the chat's footers and the stage titles
SHORT_NAMES = ("Scope", "Interview", "Standardise", "Requirements", "Handover")
#: t432: each stage's long line, said only as its stage card's subtitle (`Card.subtitle`)
LONG_NAMES = ("Identification of scope", "The interviews this BIA rests on",
              "Your interview, in the method's terms", "What your BIA now says, checked",
              "The requirements handover, and your signature")

STAGE = 1
HEADING = f"Stage {STAGE} of 5 · {SHORT_NAMES[STAGE - 1]}"
AGREE = "Yes, that's the scope"

STAGE_2 = 2
HEADING_2 = f"Stage {STAGE_2} of 5 · {SHORT_NAMES[STAGE_2 - 1]}"

#: The four ways to answer a card, in these words and only these (ADR-0006, docs/voice.md §2).
#: Stage 1 asks for one thing and offers one control to press; the answer it records is the
#: gradient's first label, so the record carries a gradient answer rather than a bare yes.
GRADIENT = ("endorsed", "endorsed with reservations", "needs discussion", "blocked")
ENDORSED = GRADIENT[0]

#: What an answer that holds something back is recorded as where the manager did not name one of
#: the four himself. The middle of the gradient rather than its end: he answered and kept a caveat,
#: which is not a refusal, and the walk asks him to name it (`docs/voice.md` §4.3).
RESERVED = GRADIENT[1]


def _ways(labels: tuple[str, ...]) -> str:
    """The ways to answer a card, as one readable phrase.

    They go **into the card's own words** rather than onto controls beside it: the manager reads
    them and types one back (ADR-0013, the owner's ruling of 2026-09-13). Built from the labels the
    card carries so that a card can never offer a way to answer it that its prose does not say.
    """
    return " or ".join(part for part in (", ".join(labels[:-1]), labels[-1]) if part)


#: The three clauses every card's rule is built from. One spelling of each, because four stages
#: saying the same thing four ways is how they would come to say different things.
IN_WORDS = "Answer it in your own words — {ways} — and nothing is saved until you do."
#: `_ways` read backwards, over the sentence it is put into: the ways a card offers are wherever
#: `IN_WORDS` carries them, so the pattern is built out of `IN_WORDS` rather than spelled again and
#: cannot go stale against a reworded sentence.
_OFFERED = "(.+?)".join(re.escape(part) for part in IN_WORDS.split("{ways}"))
LEFT_ALONE = "A card left unanswered leaves the BIA exactly where it is."
RESERVING = ("Answer anything but endorsed and the next thing you type is taken as what you are "
             "reserving.")

AWAITING_HUMAN = "awaiting_human"
CLOSED = "closed"
#: The day a run closed, UTC, as `sign` writes it (ticket 258): the graph's "BIA done" date. A run
#: closed before that ticket has none, and nothing guesses one.
SIGNED_ON = "signed_on"
SCHEMA = 1

PROPOSAL = (
    "{process} stands on its own in {where}, with its own owner and its own dependencies, so I "
    "have taken it as one activity and drawn nothing wider around it. That is the whole of the "
    "scope for this BIA: {process}, and nothing else. If that is where you would draw the line "
    "too, agree it and I will carry it into the interview."
)
DECISION = "Is {process}, on its own, the scope of this BIA?"
RULE = " ".join([IN_WORDS.format(ways=_ways((AGREE,))), LEFT_ALONE])
CONFIRMED = ("Got it. The scope for {process} is agreed. That's stage 1 of 5 done, and there's "
             "nothing more to do here yet.")
RESUMED = "The scope for {process} is already agreed, from your last visit."
OVERTAKEN = ("Someone else saved this BIA while you were reading, so I have not put your answer "
             "on top of theirs.")

PICK = (
    "The interviews for {process} are already in your room, so there is nothing to fetch and "
    "nothing to type. Each one is below with its own opening lines, exactly as they stand in the "
    "file — read those rather than my description of them. Choose the one this BIA should rest "
    "on, and every figure later in the walk is traced back to the words in it."
)
CHOSEN = (
    "Right — that's the one above, and those are the words every figure later in the BIA gets "
    "traced back to. Answer it and I will hold this BIA to the interview exactly as it stands now."
)
NO_INTERVIEW = (
    "There's no interview for {process} on file, so let's do it now, here in the room. What you "
    "tell me becomes the interview this BIA rests on. It's a longer path to the same place and "
    "nothing else about the walk changes, because what you say is kept word for word either way."
)
HOLD_IT_NOW = "Let's do the interview now"
CONDUCTED = (
    "That is the whole of it below, exactly as the two of us said it: my questions and your "
    "answers, in the order they came, with nothing added and nothing tidied. Read it rather than "
    "my description of it. Answer it and I will keep those exact words as the interview this BIA "
    "rests on, and until you answer nothing of it is kept at all."
)
DECISION_2 = "Which of these interviews should this BIA rest on?"
DECISION_CHOSEN = "Is this the interview this BIA should rest on?"
DECISION_NO_INTERVIEW = "Shall we hold the interview here, now?"
RULE_2 = " ".join([IN_WORDS.format(ways=_ways(GRADIENT)), LEFT_ALONE])

#: The one card whose way to answer is not one of the four: a room with no interview on file is
#: offered one held here and now, and saying so is what starts it.
RULE_HOLD = " ".join([IN_WORDS.format(ways=_ways((HOLD_IT_NOW,))), LEFT_ALONE])
BOUND = ("Got it. That's the interview this BIA rests on, and I have kept its exact words as they "
         "stood when you chose it, so nothing can change underneath us unnoticed. That's stage 2 "
         "of 5 done.")
CHANGED = ("{name} is no longer the interview I read when you chose it: its words have changed "
           "since, so anything drawn from it has to be read against the file as it now stands.")

STAGE_3 = 3
HEADING_3 = f"Stage {STAGE_3} of 5 · {SHORT_NAMES[STAGE_3 - 1]}"

LEAD = "Start here — this is what your evidence leaves you to decide:"
SETTLED = "The rest of it your interview settles, and none of it is mine:"
OWNER_SAYS = ("{speaker} stated the {label} in the interview, so it stands as their own answer "
              "rather than as mine: {value}. Word for word: “{quote}”")
ASSERTED = ("Your interview names the recovery target and a figure for it in one breath, so the "
            "{label} stands at {value}. Word for word: “{quote}”")
RESOLVES = ("You named {heard}, and your dependency register models it as {asset_id}, so that is "
            "what it resolves to and I have looked no further.")
UNREACHED = ("Your interview never reached {lenses}, so I have proposed nothing there: the worst "
             "case stands as unknown across every horizon for it, and the reason it was not "
             "reached is {reason}.")
DECISION_3 = "Is this what your interview says?"
RULE_3 = " ".join([IN_WORDS.format(ways=_ways(GRADIENT)), RESERVING])
STANDARDISED = ("Got it — the evidence stands as it is above. That's stage 3 of 5 done, and "
                "there's nothing here for you to read: it goes into this BIA's own record, and "
                "stage 4 of 5 is where you see it drawn out.")
#: Said wherever a card is answered with something held back — which is now any of the four stages,
#: so it names none of them. It said "stage 3 of 5" until ticket 24, and stage 4 reused stage 3's
#: composer and told a manager who had just answered stage 4 that stage 3 was done
#: (`tests/ui/walk/test_stage_4a_the_refereed_record.py`'s second finding).
NAMING = ("Noted, and that card is answered: I haven't held your BIA up waiting for you to "
          "explain yourself. The next thing you type is what you are reserving, and I keep it "
          "word for word and carry it to the signature. Until you send it the box below belongs "
          "to this BIA rather than to your questions about the method.")
#: 234b: a line with no yes, no label and nothing held back records nothing, and the same card asks
#: once in its own four labels (the owner's ruling of 2026-09-20: nemo carries only what he typed).
NOT_CAUGHT = f"I didn't catch which one: {', '.join(GRADIENT[:-1])}, or {GRADIENT[-1]}?"
TAKEN = ("Kept, word for word, on the answer you gave it against, and it travels to the "
         "signature exactly as you typed it. The box is yours again — ask me anything.")

#: And where he says there was nothing to name after all. The walk read a caveat into a plain
#: answer, which costs him one extra question and costs the record nothing: no reservation is left
#: on it, because `docs/voice.md` §4.3 keeps that pressure for somebody who said nothing.
NOTHING_RESERVED = ("Nothing reserved, then — I have taken it back off that answer, which stands "
                    "as endorsed, and nothing about it travels to the signature. The box is yours "
                    "again — ask me anything.")
ARGUED = ("You argued with {count} of the cards here rather than waving them through, and both "
          "halves of that belong in the report: it makes for a better BIA than one nobody "
          "questioned, and it makes for a longer walk than one nobody questioned.")
UNARGUED = "Every card in this BIA was endorsed as it stood, so it is as short a walk as there is."

STAGE_4 = 4
HEADING_4 = f"Stage {STAGE_4} of 5 · {SHORT_NAMES[STAGE_4 - 1]}"

#: The run state of a walk whose record has landed and whose picture is not drawn yet (ADR-0010).
#: Saved, and not yet finished: stage 5 binds on this and nothing else may be read as closure.
RECORD_SAVED = "record_saved_graph_pending"

ACCEPTING = (
    "Here is the BIA for {process}, put together out of what you endorsed and checked by me "
    "before I put it in front of you. Read it and say whether you accept it as it stands. This is "
    "the one card in the walk that does not undo: what you accept here is written into your room."
)
OPEN_4 = "First, what I will not settle on your behalf, and you would be accepting as it stands:"
DRAWN = "Then the rest of it, which your own evidence settles:"
SCORED_SAYS = ("{speaker} scored {lens} for {activity} in the interview, so those figures stand as "
               "their own rather than as mine. Word for word: “{quote}”")
DECISION_4 = "Do you accept this BIA as it stands?"
RULE_4 = " ".join([IN_WORDS.format(ways=_ways(GRADIENT)), RESERVING])
ACCEPTED = ("Accepted, and your BIA is written into your room exactly as you read it above. "
            "That's stage 4 of 5 done.")
CHECKED_NOTE = "Before I wrote it I {checks}."
SAVED_NOT_FINISHED = ("Your BIA is saved in your room. The picture that goes with it is not drawn "
                      "yet, so there is one thing left before this walk is finished.")
PICTURE_DRAWN = ("Your BIA is saved in your room, and the picture that goes with it is drawn from "
                 "that same record and is in there beside it. That leaves the signature.")
REFUSED = ("I am not going to ask you to accept this BIA, because something in it is wrong rather "
           "than merely open, and no answer of yours would put it right. What I found: {problems}")

#: What each way a record can be refused says to the manager, under the name `nemo.refusal`
#: gives it — the vocabulary below this module and the referee both, so that neither writes
#: the other's half.
#: The referee reports parts — the activity, the impact category, the time bands — and the sentence
#: is written here, where every other string on a card is written. It used to be written there, in
#: an f-string for a developer, and the card printed the lot: *activity Slaughter:
#: impact_grid['legal-regulatory'] missing horizon(s): ['72 h']*, on a card a manager can reach
#: today. A category is named here exactly as the rest of the card names it, which is the id the
#: room's own method gives it; one spelling per card is the rule.
REFUSAL_SAYS = {
    refusal.MISSING_HORIZONS:
        "Nobody scored {lens} for {activity} at {horizons}, and your method asks for a figure at "
        "every one of its time horizons before I can say how long the activity can be down.",
    refusal.UNKNOWN_HORIZONS:
        "{activity} carries {lens} scores at {horizons}, which are not time horizons your method "
        "names, so there is nothing to read them against.",
    refusal.INVALID_SCORE:
        "The {lens} score for {activity} at {horizon} is {score}, which is not a level on the "
        "severity scale your method sets.",
    refusal.UNREADABLE_ROW:
        "I cannot read the {lens} scores for {activity} as a figure against each time horizon.",
    refusal.UNREADABLE_GRID:
        "I cannot read what an outage costs {activity} at all.",
    refusal.UNKNOWN_LENS:
        "{activity} is scored for {lens}, which is not one of the impact categories your method "
        "names.",
    refusal.MISSING_LENSES:
        "{activity} has no scores at all for {lenses}, and those are impact categories your "
        "method asks a BIA to cover.",
    refusal.BAND_UNSCORED:
        "No impact category put a figure on {activity} at {horizon}: it is not rated in the "
        "source. To sign this BIA as it stands, somebody has to accept that in writing: who "
        "accepts it, what was asked and declined, and who gets asked when it is looked at again.",
    refusal.UNRATED_BAND_NEEDS_OWNER:
        "The acceptance that {activity} is not rated at {horizon} in the source does not say "
        "{missing}.",
    refusal.UNSCORED_NEEDS_OWNER:
        "Nothing was scored for {activity} anywhere. Your method allows that, but somebody has to "
        "accept it in writing, and this BIA does not say {missing}.",
    refusal.REVIEW_DATE_UNUSABLE:
        "The acceptance of the unscored assessment for {activity} carries no date to look at it "
        "again, and an acceptance without one is a shrug rather than an acceptance.",
    refusal.REVIEW_DATE_PASSED:
        "The unscored assessment for {activity} was accepted until {date}, and that day has gone "
        "by: it is due to be looked at again, or the figures are due from the owner.",
    refusal.LENS_UNQUOTED:
        "{activity} is scored for {lens}, and no sentence from the interview is marked as what "
        "that score rests on.",
    refusal.UNSIGNED_ACK:
        "The note that one sentence is the evidence for {lenses} on {activity} carries nobody's "
        "name, and a note nobody put their name to is not an acceptance.",
    refusal.QUOTE_NOT_FOUND:
        "No file in your room holds the words “{quote}”, which {activity} rests on.",
    refusal.EVIDENCE_UNCHECKED:
        "The words {activity} rests on could not be held against any file in your room, so "
        "nothing behind it was checked.",
    refusal.UNREADABLE_EVIDENCE:
        "I cannot read one of the pieces of evidence behind {activity} as words somebody said.",
    refusal.NO_RECOVERY_TARGET:
        "Nobody said how long {activity} may take to come back.",
    refusal.UNREADABLE_TARGET:
        "The recovery target for {activity} is {target}, and I cannot read that as a length of "
        "time to hold against how long the activity can be down.",
    refusal.TARGET_OUTSIDE_MTPD:
        "{activity} is to be back within {target}, and being down becomes unacceptable at {mtpd}, "
        "so the target is not inside it. Go back to the owner and either bring the target "
        "forward, or have them say in as many words that they accept the gap.",
    refusal.RPO_NOT_ALLOWED:
        "The data-loss answer for {activity} is {rpo}, and your method allows {allowed}.",
    refusal.BOUNDARY:
        "This BIA carries {what}. A BIA hands over what has to be back and by when, and stops "
        "before either of those is drafted.",
    refusal.HANDOFF_ITEM:
        "One of the things this BIA hands over reads “{item}”, and each one has to say whether it "
        "is a gap, an option, a decision for a human, or evidence nobody has.",
    refusal.OWNER_NOT_A_PERSON:
        "The disagreement over “{issue}” is recorded as owned by {who}, which is me rather than a "
        "person who can settle it.",
    refusal.NO_ACTIVITIES:
        "This BIA records no activity at all, and a BIA is about at least one of them.",
    refusal.MALFORMED_ACTIVITY:
        "I cannot read one of the activities in this BIA.",
}

#: Ticket 132: a chat confirmation refused as words not found was held against his message of
#: that day and never against a file, so its card names the message. A file quote keeps the
#: sentence above.
CHAT_WORDS_NOT_FOUND = ("Your message of {on} doesn't contain the words “{quote}”, which "
                        "{activity} rests on.")
#: The same for a chat confirmation refused as unchecked: a turn the room's conversation does not
#: hold, or a day that is not his turn's. Neither was ever held against a file.
CHAT_TURN_NOT_HELD = ("Your message of {on} that {activity} rests on isn't in this room's "
                      "conversation.")
CHAT_TURN_MISDATED = "Your message that {activity} rests on is dated {on}, not {claimed}."
#: t74: a band MTPD's refusal also says the upper edge the target was held against, in the
#: referee's own `edge` part (241 slice 3, once the phone's patch).
EDGE_SAYS = (
    " {mtpd} counts up to its upper edge, {edge}, and a target of {target} is not before it."
)

#: What a card says where the record put something in a part that is not words at all: a grid
#: where a score belongs, a list where a recovery target belongs. `str()` on one of those is
#: `{'a': 1}` or `[1, 2]` — a data structure printed at a manager, which is the same defect one
#: layer down from the one this ticket took off the card, and it reaches the same screen.
NOT_WORDS = "something nobody wrote in words"

#: The part the referee reports as a list of the acknowledgement's own field names, and what each
#: one is in the words a manager would use. A field name is not a sentence and is not on a card.
MISSING_SAYS = {
    "approved_by": "who accepts it",
    "reason": "what was asked and declined",
    "review_owner": "who gets asked when it is looked at again",
    "next_question": "what answer would produce a figure",
    "owner_informed": "who told the owner that it is on record",
    "review_date": "when it is to be looked at again",
}

STAGE_5 = 5
HEADING_5 = f"Stage {STAGE_5} of 5 · {SHORT_NAMES[STAGE_5 - 1]}"

#: The run state of a walk whose handover the human has accepted and nobody has signed yet.
#: Accepting is not signing: no certificate exists while a run stands here (`docs/stage-model.md`).
REVIEWED = "reviewed_pending_owner"

HANDING_OVER = (
    "Here is the whole of the BIA for {process}, rendered from the record you accepted and from "
    "nothing else. Two documents: the BIA for management, and the requirements handover for "
    "whoever designs the continuity solutions next. Read them and say whether you accept the "
    "handover as it stands. Nothing in them decides how anything is recovered — this BIA hands "
    "over what has to be back and by when, and stops there."
)
DECISION_5 = "Do you accept this handover as it stands?"
ACCEPTED_5 = ("Accepted. The BIA for management and the requirements handover are both on file in "
              "your room, exactly as you read them. That's stage 5 of 5 answered.")
SIGNING = (
    "All that is left is your name against it. Tell me who you are and in what role. Signing "
    "accepts every open item listed below. A sign-off that closes this BIA rests on the person "
    "the record has owning the activity, and that is {owner}."
)
#: Ticket 134 (ADR-0030 decision 7): who he signs as is his own explicit choice, and there are two
#: of it. It is said on the card as well as tapped, because a choice only a control carries is one
#: the prose cannot be held to (ADR-0013).
SIGNING_CHOICE = (
    "Two ways to sign it, and which it is you say yourself: as the owner, or on behalf of {owner}. "
    "Either one closes this BIA, and your certificate says which of them you picked."
)
NOBODY = ("nobody: this BIA records no owner for what it is about, so there is no sign-off here "
          "that closes it")
#: The two taps at the signature, drawn from the record's own names. The choice each one carries
#: is what `sign` takes: never free text, never a setting somewhere else, and never a role string
#: anybody typed about themselves. `AS_THE_OWNER` is the claim "I am the owner", which the record
#: judges by his name exactly as it always did — a claim, said out loud, and not a verdict.
SIGN_AS_THE_OWNER = "Sign as the owner"
SIGN_ON_BEHALF = "Sign on behalf of {owner}"
AS_THE_OWNER = "as the owner"
DECISION_SIGN = "Who is signing this, and in what role?"
RULE_SIGN = ("Your name and your role are the only two things you type in this whole walk. Nothing "
             "is written until you give them, and a general yes is not a signature.")
SIGNED_OFF = ("Signed, and that closes this BIA. Your sign-off is on file beside the handover, in "
              "your name and your role, and it accepts every open item that was listed.")
#: Ticket 239: the two runs nothing signs, said on the signature card in place of the question.
#: A signed BIA is final, and the one way into a signature is a handover he accepted (ADR-0010).
ALREADY_SIGNED = "This BIA is already signed. A signed BIA is final, so it can't be signed again."
NOT_ACCEPTED_YET = ("There is nothing to sign yet. The handover has to be accepted first, and then "
                    "it can be signed.")
NOT_THE_OWNER = (
    "Kept as {capacity}, and this BIA is not closed by it: the person the record has owning the "
    "activity is {owner}, and a sign-off that closes this has to be theirs. Yours stands on the "
    "walk as what it is, and nothing anywhere calls it the owner's."
)

_NOT_A_NAME = re.compile(r"[^a-z0-9]+")

#: The words a manager holds something back with, which is as far as this reads an answer. Rough,
#: and leaning towards asking him to name it rather than towards recording an endorsement he did
#: not give (the owner's 80/20 ruling of 2026-09-13, and `docs/voice.md` §4.3).
_HELD_BACK = re.compile(
    r"\b(but|though|although|however|unless|except|maybe|unsure|doubt|doubtful|disagree|wrong|"
    r"not sure|not certain|not right|reservation|caveat|concern|concerned|worried|queried|"
    r"no|not|blocked|discussion|do not agree)\b")

#: The words a plain yes is said in. Ticket 234: an endorsement is read only where he said one, so
#: an empty or unrelated line asks rather than standing as an endorsement he never typed.
_SAYS_YES = re.compile(
    r"\b(endorsed|yes|yeah|yep|ok|okay|agree|agreed|fine|correct|right|good|sure|accept|"
    r"accepted|approved|confirmed)\b")

#: What waves a reservation off: he was asked to name one and says there is none to name. The same
#: shape of rough reading, and the recovery the walk owes anybody it misread as holding something
#: back — a record saying he reserved something he never reserved is the failure to avoid.
_NOTHING_TO_NAME = re.compile(r"^(nothing|none|no|never mind|nevermind|forget it)[.!]?$")


class NotDrawnYet(Exception):
    """The picture this record's receipt would bind has not been drawn, so stage 5 may not start.

    It says the one sentence the manager is already being told, because there is nothing else to
    say: the record is saved, the picture is not bound yet, and the walk is not finished.
    """

    def __init__(self) -> None:
        super().__init__(SAVED_NOT_FINISHED)


@dataclass(frozen=True)
class Card:
    """What a stage puts in front of the manager: prose on top, structure underneath."""

    stage: int
    #: Which card this is, as a name rather than as its prose: the stage alone does not say what a
    #: manager was looking at, and a heading carries the room's own words. It rides onto every
    #: decision the press appends, and a variant drawn with `replace` keeps the name it started
    #: with — the same card, said differently.
    name: str
    heading: str
    activities: tuple[str, ...]
    body: str
    sources: tuple[str, ...]
    buttons: tuple[str, ...]
    decision: str
    rule: str
    gradient: tuple[str, ...]
    method: Record
    saved: Record | None
    revision: int
    interviews: tuple[interview.Interview, ...] = ()
    proposal: Record = field(default_factory=dict)
    #: The revision of the room's BIA record this card was drawn against, so an acceptance is
    #: conditional on the record not having moved under the manager while they read it.
    record_revision: int = 0
    #: What the referee refused over the record behind this card, kept as the parts it was found
    #: in. It is on the card rather than in `proposal` because `proposal` is merged into
    #: `Card.record` and checked figure by figure: a refusal is not something the card says.
    refused: tuple[refusal.Rejection, ...] = ()

    @property
    def record(self) -> Record:
        """What this card is checked against: the room's record, and what this card proposes.

        A stage that drafts its own evidence says figures the record does not hold **yet** —
        nothing is saved until the press — so the check `nemo.card.render` makes would refuse
        every stage 3 card if it read the disk alone. The proposal is the card's working, it goes
        to the run state verbatim at the press, and the check is exactly as strict against it:
        prose that softens or sharpens a figure the draft holds is still a card generator bug.
        """
        return {**(self.saved or {}), **self.proposal}

    @property
    def ways(self) -> tuple[str, ...]:
        """The answers this card offers, read back out of the sentence it offers them in.

        Since ADR-0013 a card's answers are its own words rather than controls beside it, so "what
        does this card offer?" is a question about its prose and is answered here by reading it —
        never by handing back `buttons`, which would make the sentence unfalsifiable. A card whose
        rule says no way to answer it offers none, whatever it carries underneath, and that is what
        makes the sentence the contract rather than a caption on one.
        """
        said = re.search(_OFFERED, self.rule)
        if said is None:
            return ()
        # The inverse of `_ways`, and in this order: `", "` separates labels only when there is
        # more than one, and stage 1's single answer — "Yes, that's the scope" — has a comma of its
        # own inside it. Splitting on the comma first hands back two answers to a card offering one.
        head, found, tail = said.group(1).rpartition(" or ")
        return (*head.split(", "), tail) if found else (tail,)

    @property
    def source_line(self) -> str:
        """The one element of v1 the owner praised, in the form he praised: a line, not prose."""
        return "Source: " + ", ".join(self.sources)

    @property
    def screen(self) -> str:
        """The prose the manager reads, in ``docs/voice.md`` §2's order — and only the prose.

        This is what goes through ``nemo.card.render``, the one door a card reaches a human by.
        Two things on the screen are deliberately not in it. The ``Source:`` line is provenance
        rather than a claim, and every path on it is asserted to be a file in the room by a test
        of its own. A preview is the interview's own bytes: §4.4 asks whether a figure the card
        **says** is one the record holds, and a verbatim quotation is not the card talking — a
        transcript in which an owner says "roughly a day" would otherwise make the card
        unrenderable for being honest about what he said.

        That preview is one of the two things exempt from `nemo.card`'s rule, and the second one
        rides beside this prose rather than being kept out of it: **a name the room supplies**.
        A room called `Werk 1`, `Halle 45` or `Key Accounts` is not asserting a quantity when it
        says which building the manager works in, so `activities` — the room's own name for what
        this walk is about — goes to `render` with the screen, and a name is never a figure and
        never a vague word, whatever it contains: it is exempt where it stands on this card,
        scoped to that span and no wider (the owner's ruling, 2026-09-14, widening the ruling of
        2026-09-13 from a digit to the whole name). `Werk 1 runs 45 cutters` is still refused for
        the count, and `Key Accounts is the scope and the key risk is staff` for the bare `key`.
        """
        asked = [self.decision, self.rule] if self.decision else []
        return "\n\n".join([self.heading, self.subtitle, self.body, *asked])

    @property
    def subtitle(self) -> str:
        """t432: the stage's long line, under its short heading; the one place it is said."""
        return LONG_NAMES[self.stage - 1]


# ── what the room holds ──────────────────────────────────────────────────────


#: The room's list of the activities a manager added (t72): {"activities": [{"name": <as he gave
#: it>, "route", "added_at"}]}. The demo skin writes it; the walk offers what it names (241).
ADDED = "output/.proto/added-activities.json"


def processes(room_folder: Path) -> list[str]:
    """The processes on file, each once and in alphabetical order, as things to press.

    The transcripts and the dependency register do not name the same departments, and a manager
    is never asked to type one: the union of what the room's two sources name, and of what he
    added to the room (t72), is the whole menu.
    """
    added = {} if _unreadable(room_folder / ADDED) else _read_json(room_folder / ADDED)
    return sorted(interview.departments(room_folder) | _register_departments(room_folder)
                  | {entry["name"] for entry in added.get(ACTIVITIES) or []})


def in_progress(room_folder: Path) -> list[str]:
    """The walks this room already holds and has not finished — what a minted room ships."""
    return sorted(run.stem for run in (room_folder / RUNS).glob("*.json")
                  if _read_json(run).get(STATUS) != CLOSED)


#: What the admission check says about a seed, to the operator who can put it right.
NOTHING_TO_PRESS = "it offers no process to press"
NAMES_NOBODY = "{path} names no department in its front matter, so no stage can bind it"
SEED_FAILED = "the seed at {seed} did not pass the walk's own gates: {problems}"

#: And what the delegate reads instead: one sentence, no path, no field name, no fault. They did
#: nothing wrong and can do nothing about it, so it says who can (`docs/voice.md` §3.1).
SEED_REFUSED = ("This room isn't ready to be opened yet, so tell whoever is running the session "
                "and they can put it right.")

#: The two lines the operator's journal carries about a mint: the one that did not happen because
#: the mount is away, and the one that did. The first ends in ticket 22's own sentence — taken from
#: `nemo.room_code` rather than spelled again, so the two cannot drift — and so an absent mount
#: still reads as a room with no folder and never as a damaged scan.
ABSENT_MOUNT = "the rooms folder {rooms} is not there, so " + NO_FOLDER
MINTED = "the room {room!r} was minted from the seed"


def seed_problems(seed_folder: Path) -> list[str]:
    """What the walk's own gates say about this seed, asked before a room is made of it.

    Ticket 02's admission check, and G4(b): it runs **at mint**, not only at a refresh nobody
    runs. A room that would fail the walk's gates must not be handed to a delegate — it is better
    to refuse a scan than to seat somebody in front of a BIA that cannot reach stage 5.

    Two gates, and they are the walk's own rather than a second list of rules kept beside it: a
    seed that offers nothing to press leaves typing as the only way in, which is no way in at all
    (`processes` is what the room puts on buttons), and a capture the room's evidence reader
    cannot read as evidence is one no stage can bind. Read-only, uncached and deterministic, so
    fifty scans of a broken seed are fifty refusals and none of them is a sampled guess.
    """
    return ([NOTHING_TO_PRESS] if not processes(seed_folder) else []) + [
        NAMES_NOBODY.format(path=path) for path in interview.unreadable(seed_folder)]


def mint_room(seed_folder: Path, rooms_folder: Path, code: str) -> bool:
    """Copy the seed into the room this code names, the first time anybody arrives at it.

    Hands back whether **this** arrival is the one that made the room, which is what the operator
    counts at 09:05 and what proves a second scan cost nothing. Whether there is a room to open
    afterwards is `nemo.door.checked_room_folder`'s answer, exactly as it was before ticket 50:
    minting adds a way for a room to come to exist and takes no refusal away.

    **The mechanism is copy-to-staging-then-rename, and it is not a lock.** The copy lands in a
    staging folder inside the rooms folder and `rename` moves it onto the room's own name in one
    step the kernel will not interleave, so a delegate arriving mid-copy sees no room rather than
    half of one, and the room is whole at the instant it appears. Fifty phones scanning one code
    within a minute of each other are fifty independent copies and exactly one winner: the losers'
    rename fails against a directory that is already there, and each throws its own copy away
    having touched nobody else's. A lock would have to be held across a 0.54 MiB copy by fifty
    processes and then survive the one that died holding it; a rename outlives nothing.

    Three things are never minted, and each keeps a rule ticket 22 paid for:

    - a room that is already there — the first line, before the disk is asked anything else, so a
      delegate who reloads lands back in the room they answered in rather than over the top of it;
    - a room inside a rooms folder that is not there. An absent mount is an absent mount: minting
      creates a room *inside* the rooms folder and never the folder itself, because a mount that
      is away would otherwise hand fifty delegates fifty brand-new rooms and lose the ones they
      had been working in all morning;
    - a code no printed QR carries, or a seed this box has not got. Both leave the door exactly as
      ticket 22 built it — the room has no folder, and `checked_room_folder` says so.

    What keeps the first of those true is who calls this (ticket 186 (c)): on the phone app only a
    door — the stage QR's `/new` and `skin/new_room.py` — and never its login, so a link somebody
    made up opens nothing and makes nothing. `demo_skin/app.py`'s login still mints (ticket 50's
    procedure), until 165 retires that skin from tests/ui.
    """
    if (rooms_folder / code).is_dir():
        return False
    if not rooms_folder.is_dir():
        raise Refused(ABSENT_MOUNT.format(rooms=rooms_folder, room=code))
    if not (seed_folder.is_dir() and mintable(code)):
        return False
    _admitted(seed_folder)
    return _copied_into_place(seed_folder, rooms_folder / code)


def _admitted(seed_folder: Path) -> None:
    """The admission check at the one place a room is made, refusing in two voices at once."""
    problems = seed_problems(seed_folder)
    if problems:
        raise Refused(SEED_REFUSED, SEED_FAILED.format(
            seed=seed_folder, problems="; ".join(problems)))


def _copied_into_place(seed_folder: Path, room: Path) -> bool:
    """The copy, and the one step that publishes it. True iff this copy is the one that landed.

    The staging name is this arrival's own, so two scans never write into one folder, and it is
    hidden so that a listing of the rooms folder mid-copy reads as the rooms that exist. Losing
    the rename is the ordinary path rather than the error path: the room that beat us to it is
    whole by the same argument ours would have been.

    Losing the race is the only failure that is False, and the room being there is what says so
    (ticket 210): every other OSError is this mint's own, and a caller told False would send the
    phone to a room nobody made. The copy is inside the cleanup too, so a copy that broke part
    way leaves no `.minting-*` in the rooms folder. Tidying up never speaks over the failure —
    hence `ignore_errors`, since a copy that failed before it made the folder has none to remove.
    """
    staging = room.parent / f".minting-{uuid.uuid4().hex}"
    try:
        shutil.copytree(seed_folder, staging)
        staging.rename(room)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        if room.is_dir():
            return False
        raise
    return True


def run_file(process: str) -> str:
    """Where a process's walk is kept, relative to the room folder."""
    return f"{RUNS}/{_slug(process)}.json"


def _at_step_3(process: str) -> str:
    """Where `reopen` finds the run as it stood when this process's stage 3 closed."""
    return f"{AT_STEP_3}/{_slug(process)}.json"


def record_file(process: str) -> str:
    """Where the BIA a process's walk produces lands, relative to the room folder.

    One per process, beside its four views, through the same conditional write as the run state
    (ticket 235). One per room let the next walk's stage 4 land over a record already signed, and
    the bytes the signature rests on were gone. A room may still hold a record that is another
    run's (ADR-0011); `nemo.bia` is what keeps this walk from closing over it.
    """
    return f"output/{_slug(process)}/{RECORD_NAME}"


def interview_path(process: str) -> str:
    """Where an interview held in the room is filed, relative to the room folder.

    The room's second home for interviews (ADR-0002), under the process's own name — which is what
    makes it evidence the next walk offers back and the referee hunts quotes in.
    """
    return f"{interview.OWNER_INTERVIEWS}/{_slug(process)}-interview-transcript.md"


def _slug(process: str) -> str:
    """A process's name as a file name: the one spelling both of the room's paths are built from.

    Three lines rather than one so the equivalent mutant on the strip is silenced by itself: a
    pragma silences its whole line, and on one line it would have hidden seven live mutants too.
    """
    slug = _NOT_A_NAME.sub("-", process.lower())
    slug = slug.strip("-")  # pragma: no mutate: nothing after .lower() can lead or trail with X
    return slug


# ── the card ─────────────────────────────────────────────────────────────────


def open_bia(room_folder: Path, process: str) -> Card:
    """The card for the stage this walk has actually reached. Reads the room; writes nothing.

    There is no argument for the stage, on purpose: v1's resume branch rendered whichever stage
    the caller asked for, with no gate in front of it, which walks past every guarantee the
    referee makes. A caller may ask; there is nowhere for the asking to go.
    """
    return _card(room_folder, process, read_record(room_folder, run_file(process)))


# ── the one door ─────────────────────────────────────────────────────────────


def answer(room_folder: Path, process: str, words: str, revision: int,
           *, picked: interview.Interview | None = None,
           confirmed: Sequence[str] = (),
           record_revision: int | None = None,
           turn_id: str | None = None) -> tuple[Card, ...]:
    """What the manager typed, taken as the answer to whatever this walk is waiting for.

    The one way into a walk (ADR-0013, the owner's ruling of 2026-09-13: *"we shifted to having the
    answers as text, like Claude does"*). Which stage it answers is read off disk exactly as
    ``open_bia`` reads it — there is no argument for the stage here either — so the seven things a
    press used to call are private behind this, and a stage nobody wired a control for is a stage
    that cannot exist.

    **The typed box has four claimants and this is where three of them are arbitrated.** In order:

    1. An **interview underway** takes the words first, and it is the caller's: a question is on
       the screen and what is typed answers it, so the words never reach here at all
       (`demo_skin/app.py`, which holds the turns of an interview nothing has kept yet).
    2. A **walk waiting for a reservation to be named** — this walk, named by ``process`` and no
       longer whichever run of the room sorts first (defect 1 of
       `docs/reviews/code-review-2026-09-13.md`). While a naming is awaited the composer belongs to
       the walk (`docs/voice.md` §4.3), so even a question is kept as the naming.
    3. The **ask lane**, whenever nothing of this walk is waiting for the composer —
       ``_for_the_ask_lane``, which is a question typed at any stage and anything typed after the
       handover. It is said here as an empty tuple — nothing of this walk moved, and the words are
       the caller's to put to `nemo.ask` — because `docs/what-good-looks-like.md:201` puts a BCM
       question answered from the corpus inside the release bar, and a build that recorded "what
       does MTPD mean?" as an endorsed stage answer would fail ticket 19 on a lane this door never
       meant to touch.
    4. The **card the walk is waiting on** — everything else, answered in the words that were typed.

    ``revision`` travels in from the page that read the card, and is not read again here. An
    implementation that reloaded it would compare it against itself, the compare-and-set would be a
    no-op, and a test at the store would pass over that (second-opinion finding 5, 2026-09-14).

    ``picked`` is the one thing about a stage 2 answer the room's own disk cannot say: which
    interview the manager chose, where the room holds more than one, and the interview just held
    here that is not filed anywhere yet. Both arrive as an ``Interview`` off a card this module
    built — ``chosen`` or ``held_interview`` — so nothing the caller composes itself reaches a
    binding. Stage 2 in a room with no interview on file is the one card typed words cannot answer
    alone: the card comes back unanswered, because the interview has to be held first.

    ``confirmed`` is the rest of a stage 2 answer: the interviews the manager confirmed this BIA
    rests on besides the one bound, as room paths in the order he confirmed them (ticket 168). The
    run record keeps them, bound one included, and they are the files a quote may come from. Left
    out, the bound interview is the whole list. A path outside the room is refused before anything
    is saved.

    ``record_revision`` travels for the same reason and is the second one a page reads: the room's
    BIA record is shared between the walks in it, so stage 4's acceptance is conditional on that
    file not having moved while the manager read the card drawn against it. Left out, it is read
    off disk like everything else here — which is the right answer for a caller that has no card
    in hand, and a no-op guard for one that has.

    ``turn_id`` is the turn his words arrived on (ticket 232), the id the caller writes his line
    under in the room's turn file once the turn is over. A Withdraw typed here then rests on his
    act on that turn, a chat confirmation, as the skin's Withdraw tap does (171's ruling B); the
    words and the day are read from that line when the record is drawn, never from here. Left out,
    nothing is cited and the record is what it was before 232. Nothing else reads it.
    """
    run = read_record(room_folder, run_file(process)) or {}
    awaited = _awaited(run)
    if awaited is not None:
        return (awaited(room_folder, process, run, words, revision),)
    if _for_the_ask_lane(run, words):
        return ()
    waiting = current(room_folder, process)
    card = replace(waiting, revision=revision, record_revision=(
        waiting.record_revision if record_revision is None else record_revision))
    answered = _pressed(room_folder, card, words, picked, confirmed, turn_id)
    return (answered,) if answered is card else (answered, *onward(room_folder, answered))


def resume(room_folder: Path, process: str) -> Card:
    """The movement a walk stopped inside, done again: the picture, or stage 5's two documents.

    A stop between the record landing and the picture being drawn is the ordinary path rather than
    the crash path (ADR-0010), so getting the second movement again is an ordinary thing to ask
    for and is reachable without reaching past this surface into a private name. It costs the
    movement again and nothing else: everything drawn is a function of the record bytes, so a
    resume over a walk that already drew its picture rewrites the same bytes.

    What it hands back is the card the accepting answer would have handed back, not the card that
    asks to accept again: this record has been accepted, so a resume that returned `record_card`
    itself would put stage 4 back on the screen still asking for an answer the manager has given.
    Where the movement did not run — somebody else's record, or a run that moved under this one —
    the plain card stands, because then there is nothing of this walk's to confirm.

    A run already past stage 4 gets the movement *it* stopped inside instead (ticket 207): the
    acceptance writes the two handover documents after it has moved the run, so a stop between the
    two leaves an accepted run with the documents unwritten, and `_documents_again` renders them
    from the record and the run on disk, as the press would have rendered them. There is nothing of
    stage 4's to redo there, and the card is the one it always was — this asks for the movement
    again and never for an answer again.

    **A closed run gets its certificate here too**, written again from the record and the saved
    signature. ``sign`` closes the run and writes the certificate after it, so a stop between the
    two leaves a closed BIA with no certificate and nothing signs it again: the walk is past the
    signature, and a second press finds a run that moved. It is written for a run that is
    ``CLOSED`` and for no other — which is what makes a certificate on disk still mean a signature
    that had the authority to close this.

    Stage 5's documents and the certificate are written **only where none is on disk** (ticket
    235c): a stop leaves them unwritten, never written wrong, and the bytes on disk are what he
    read and signed in the renderer's words of that day (`_on_disk`). On disk means on disk for
    this run (ticket 245): an earlier walk's are replaced, its signed certificate set aside.
    """
    card = record_card(room_folder, process)
    run = read_record(room_folder, run_file(process)) or {}
    if run.get(STATUS) in (REVIEWED, CLOSED):
        _documents_again(room_folder, run)
    if run.get(STATUS) == CLOSED:
        _certified_again(room_folder, run)
    accepting = _answered(card, STAGE_4, HEADING_4, NAMING if _last_decision(run).get(
        "naming") == UNNAMED else " ".join([ACCEPTED, checked_note(run), SAVED_NOT_FINISHED]), run)
    drawn = _draw_graph(room_folder, accepting)
    return card if drawn is accepting else drawn


#: Ticket 256: what a referral says, written by code: the resource, the item (with last year's
#: value, the caller's), then his line as he typed it. Who it goes to is the register's name,
#: never a person: the room states no owner (`03_Dependencies/asset-inventory.md`).
REFERS_SAID = "{resource}, {item}: {words}"
REFERRED_TO_SAID = "Owner of {resource}"


def refer(room_folder: Path, process: str, resource: str, item: str, words: str) -> bool:
    """His referral of a change to its resource owner, onto the run's pending list (ticket 256).

    Once per row: the same resource, item and words again writes nothing. Refused (False) with no
    run on file, with no words, and on a run at ``REVIEWED`` or ``CLOSED``: its record is what he
    reviewed or signed, so nothing more is carried into it and ``record_sha`` stays as it is.
    `bia.build` carries the list into the record's ``risk_referrals`` when the record lands.
    """
    said = words.strip()
    with room_lock(room_folder):
        run = read_record(room_folder, run_file(process))
        if run is None or not said or run.get(STATUS) in (REVIEWED, CLOSED):
            return False
        row = {REFERS: REFERS_SAID.format(resource=resource, item=item, words=said),
               REFERRED_TO: REFERRED_TO_SAID.format(resource=resource)}
        pending: list[Record] = run.get(PENDING_REFERRALS) or []
        if row in pending:
            return True
        return _save(room_folder, process, _revision(run),
                     {**run, PENDING_REFERRALS: [*pending, row]}) is not None


#: Ticket 318 (ADR-0047): the mark on every register row his tap writes, the ISO date of the tap.
ADDED_IN_CHAT = "added_in_chat"
#: A register item of this type is a site; a resource's own `site` names one too (ADR-0034 16d).
SITE_TYPE = "Site"


def _name_key(name: str) -> str:
    return "".join(name.split()).casefold()


def _same_name(a: str, b: str) -> bool:
    """Two names are one, case and spacing aside ("CSB  erp" is "CSB ERP")."""
    return _name_key(a) == _name_key(b)


def _site_names(row: Record) -> list[str]:
    """The sites one register row names: itself, a Site item, and the site it is at."""
    named = row.get("name") if row.get("asset_type") == SITE_TYPE else None
    return [str(n).strip() for n in (named, row.get("site")) if str(n or "").strip()]


def sites(register: Record) -> list[str]:
    """The room's Site list: its Site items' names and the sites its resources are at, each once."""
    found: dict[str, str] = {}
    for row in register.values():
        for name in _site_names(row) if isinstance(row, dict) else []:
            found.setdefault(_name_key(name), name)
    return sorted(found.values())


#: The room register as ticket 318 writes it back: indented as the seed is, non-ASCII kept. Made
#: once here (turn_file's way): `ensure_ascii=None` would read the same as False as a call argument.
_REGISTER_JSON = json.JSONEncoder(indent=2, ensure_ascii=False)


def _chat_write(room_folder: Path, change: Callable[[Record], Any]) -> Any:
    """The one write of ticket 318: the room's own register, read, changed and saved under its
    lock; `change` edits the register in place and returns what to answer (falsy writes nothing).
    The path is the room's, so the seed and every other room are out of its reach (ADR-0047 2)."""
    with room_lock(room_folder):
        if not (room_folder / REGISTER).is_file() or _unreadable(room_folder / REGISTER):
            return None
        register = _read_json(room_folder / REGISTER)
        before = json.dumps(register)
        said = change(register)
        if said and json.dumps(register) != before:
            write_file(room_folder, REGISTER, _REGISTER_JSON.encode(register) + "\n")
        return said


def add_dependency(room_folder: Path, process: str, name: str, resource: str,
                   on: str) -> str | None:
    """His tap: `process` (its map name `name`) uses `resource`, in this room's register only.

    One consumer row marked ``added_in_chat`` (the date `on`), with no figure and no owner, on the
    asset of that name (case and spacing aside), else on a new asset row of that name, marked the
    same. The same tap again writes nothing. Returns the asset's id; None for no name or no room
    register, which writes nothing.
    """
    said = resource.strip()
    if not said or not process.strip():
        return None

    def change(register: Record) -> str:
        aid = next((k for k, a in register.items() if isinstance(a, dict) and a.get("name")
                    and _same_name(str(a["name"]), said)), None)
        if aid is None:
            base = _slug(said) or "added-in-chat"
            # one name more than the register holds: one of them is free, so the search ends
            aid = next(i for n, _ in enumerate([*register, aid], 1)
                       if (i := base if n == 1 else f"{base}-{n}") not in register)
            register[aid] = {"asset_id": aid, "name": said, ADDED_IN_CHAT: on, "consumers": []}
        if "consumers" not in register[aid]:
            register[aid]["consumers"] = []
        rows = register[aid]["consumers"]
        if not any(isinstance(r, dict) and r.get("department") == process for r in rows):
            rows.append({"department": process, "activity": name, ADDED_IN_CHAT: on})
        return aid

    written = _chat_write(room_folder, change)
    return str(written) if written else None


def link_dependency(room_folder: Path, asset: str, on: str, stands_on: str | None = None,
                    at: str | None = None) -> bool:
    """His tap linking a resource added in chat to the map (ADR-0047's note of 2026-10-05): it
    stands on `stands_on`, a register item, or is at `at`, a site on the room's Site list. Only
    onto the added row, never a new item, and one site only; the same link again writes nothing.
    False, writing nothing, for anything else."""

    def change(register: Record) -> bool:
        row = register.get(asset)
        if not isinstance(row, dict) or not row.get(ADDED_IN_CHAT):
            return False
        if stands_on is not None:
            return _stands_on(register, row, asset, stands_on, on)
        return _at(register, row, at)

    return bool(_chat_write(room_folder, change))


def _stands_on(register: Record, row: Record, asset: str, item: str, on: str) -> bool:
    """The added row stands on `item`, another register item: its edge, marked, once."""
    if item == asset or not isinstance(register.get(item), dict):
        return False
    if item not in row.setdefault("depends_on", []):
        row["depends_on"].append(item)
        row.setdefault("depends_on_evidence", []).append({"asset_id": item, ADDED_IN_CHAT: on})
    return True


def _at(register: Record, row: Record, at: str | None) -> bool:
    """The added row is at `at`, a site on the room's Site list, in the list's spelling; one."""
    site = next((s for s in sites(register) if at is not None and _same_name(s, at)), None)
    if site is None or row.get("site") not in (None, site):
        return False
    row["site"] = site
    return True


def _certified_again(room_folder: Path, run: Record) -> None:
    """The certificate a stop left unwritten for a closed run; nothing where one is on disk already,
    or where its record is not its own.

    The same refusal ``_documents_again`` takes and for the same reason: a record that is not this
    run's, or a picture not drawn from it, is not a certificate's to rest on, and a resume serves
    the state on disk rather than raising out of the door (ticket 235).
    """
    try:
        record = move_past_stage_4(room_folder, run)
    except (bia.StaleRecord, NotDrawnYet):
        return
    if not _on_disk(room_folder, record, handover.CERTIFICATE, run):
        _certified(room_folder, record, run)


def current(room_folder: Path, process: str) -> Card:
    """The card this walk is waiting on, walked to rather than asked for (ADR-0010).

    This is the walk's door alongside ``answer`` and ``sign``: "what does this room ask now?" is
    what every caller across the seam needs, so it carries a public name (ticket 219).

    One stage at a time off the room's own file: each card is whatever follows the one before it,
    and the walk stops where the record stops. There is nowhere for a caller to name a stage, here
    as much as in ``open_bia``.
    """
    card = open_bia(room_folder, process)
    while following := onward(room_folder, card):
        card = following[0]
    return card


def _pressed(room_folder: Path, card: Card, words: str, picked: interview.Interview | None,
             confirmed: Sequence[str] = (), turn_id: str | None = None) -> Card:
    """The words against the stage this card is: one row per stage, and no stage without one.

    The five stages differ in what they save and in nothing else. Stage 1 confirms a scope and has
    no figure to hold a reservation about (ADR-0011), so the gradient its answer earns rides in the
    record underneath and the scope is agreed either way; the others carry it on the card.

    Stage 5 has a row here because a manager reads the handover in the same box he read every card
    before it, and the last row is the one a card with no row of its own falls into: before ticket
    18 landed there were four stages and the fall-through was stage 4's, so typing "yes" at the
    handover ran the record press over a card that has no record proposal on it.
    """
    if card.stage == STAGE_3:
        return _answer_evidence(room_folder, card, words, turn_id)
    answer = _gradient(words)
    if card.stage == STAGE_4:
        return _accept_record(room_folder, card, answer)
    if answer is None:
        return _not_caught(card)
    if card.stage == STAGE:
        return _agree_scope(room_folder, card, answer)
    if card.stage == STAGE_2:
        return _keep_interview(room_folder, card, picked, answer, confirmed)
    return accept_handover(room_folder, card, answer)


def _not_caught(card: Card) -> Card:
    """The same card, asking which of its four labels he meant, with nothing written (234b): a
    line that says none of them is not a decision, and nemo carries only what he typed."""
    return replace(card, body=NOT_CAUGHT, buttons=(), decision="", rule="")


def _for_the_ask_lane(run: Record, words: str) -> bool:
    """Whether the words are the caller's to put to `nemo.ask` rather than this walk's to answer.

    Two ways for that to be true, and they say the same thing about the composer. What reads as a
    question was never an answer to a card at all. And a walk whose handover has been accepted is
    waiting for a signature, which is never typed words: it demands a name and a role by name
    (``sign``, ADR-0003), so at ``REVIEWED`` and at ``CLOSED`` nothing of this walk is waiting for
    the composer either. Reading the status here is what stops a manager's "yes, thanks" after the
    handover from being read as anything at all.
    """
    return _a_question(words) or run.get(STATUS) in (REVIEWED, CLOSED)


def _a_question(words: str) -> bool:
    """Whether what was typed is a question of the manager's own rather than an answer to a card.

    Rough on purpose, and the owner said so: *"this is a demo, we don't have to get it 100%
    correct, the 80/20 principle is totally fine."* A question mark on the end is the whole of it.
    Both ways of being wrong here cost one turn — an answer read as a question costs a paragraph of
    guidance and he answers again — and neither writes anything he did not say.
    """
    return words.rstrip().endswith("?")


def _gradient(words: str) -> str | None:
    """Which of the four ways to answer his own words are, roughly and in one direction.

    A label anywhere in his words, as a whole phrase, is that label: they are on the card as words
    to read and type (ADR-0013), and "This is blocked" uses one. *Endorsed* is not searched for,
    because it sits inside "not endorsed" and "endorsed with reservations" (ticket 234). Anything
    else is an endorsement only where he said yes with no caveat, and **the rough edge leans
    towards asking**: a plain answer misread as a reservation costs one extra question and he waves
    it off, while an endorsement recorded against somebody who refused is what the signature may
    never carry. A line with no yes and nothing held back is ``None``, none of the four: the walk
    records nothing and asks which one (234b).
    """
    said = text.norm(words)
    for label in GRADIENT[1:]:
        if re.search(rf"\b{label}\b", said):
            return label
    if _HELD_BACK.search(said):
        return RESERVED
    return ENDORSED if _SAYS_YES.search(said) else None


def _agree_scope(room_folder: Path, card: Card, answer: str) -> Card:
    """Stage 1 answered: the scope agreed, and the gradient the words earned underneath it.

    The opening fills what the run on file is missing rather than standing in for it: a minted room
    ships a run at stage 1 with nothing decided (ADR-0011), and until ticket 25 that run was never
    opened at all — so it carried no identity for ticket 15's binding to read, no method for stage
    3's lenses and no sources for the `Source:` line. What the file already says wins, so an
    identity is minted once and never minted over.
    """
    process = card.activities[0]
    saved = _save(room_folder, process, card.revision, _advanced(
        _opened_run(room_folder, card) | (card.saved or {}), STAGE,
        {"decided": "yes", **_reserving(answer)}, on_card=card.name))
    if saved is None:
        return _overtaken(_card(room_folder, process, read_record(room_folder, run_file(process))))
    return _answered(card, STAGE, HEADING, CONFIRMED.format(process=process), saved)


def onward(room_folder: Path, card: Card) -> tuple[Card, ...]:
    """The card that follows this one, once the stage it answers is answered on disk.

    The page shows what comes back and decides nothing: which stage a manager has reached is read
    off the room, here, exactly as ``open_bia`` reads it (ADR-0010).
    """
    for stage, answered, following in _WHAT_FOLLOWS:
        if card.stage == stage and answered(card.saved):
            return (following(room_folder, card.activities[0]),)
    return ()


def _answered_at(saved: Record | None, stage: int) -> bool:
    """Whether this walk has answered that stage, read off the room's own file rather than a card.

    The card in hand may be the one that asked the question or the one that confirmed it; what
    decides which stage comes next is what is on disk (ADR-0010).
    """
    return any(decision.get(AT_STAGE) == stage
               for decision in (saved or {}).get(DECISIONS, []))


def _agreed(saved: Record | None) -> bool:
    """Whether the scope is already agreed, read off the room's own file rather than a memory."""
    return any(decision.get(AT_STAGE) == STAGE and decision.get("decided") == "yes"
               for decision in (saved or {}).get(DECISIONS, []))


def _rests_on_an_interview(saved: Record | None) -> bool:
    """Whether stage 2 is behind this walk: an interview is bound to it, with its bytes beside it.

    Stage 2 is answered by the binding rather than by the decision beside it, because the binding
    is what stage 3 reads — a walk that recorded a label and bound nothing has nothing to draft.
    """
    return bool((saved or {}).get("transcript"))


def _evidence_answered(saved: Record | None) -> bool:
    """Whether stage 3's draft has been answered, which is what stage 4 is drawn over."""
    return _answered_at(saved, STAGE_3)


def _record_accepted(saved: Record | None) -> bool:
    """Whether the record has been accepted, which is what stage 5 hands over.

    The receipt is asked for, and that is what ADR-0010's ordinary stop costs here. Stage 4 is two
    movements and the second one may not have run — `_save_record` writes the decision and nulls
    the receipt, `_draw_graph` binds it — so a walk that stopped between them has answered stage 4
    and has no picture for stage 5 to hand over. Reading the decision alone would walk it straight
    into ``handover_card``, whose gate would then raise ``NotDrawnYet`` at a manager who is being
    told *saved, and not yet finished* in the same breath. Nothing follows that card until the
    picture binds; ``resume`` is the second movement on its own.
    """
    return _answered_at(saved, STAGE_4) and bool((saved or {}).get(RECEIPT))


# ── stage 2: the interview this BIA rests on ─────────────────────────────────


def pick_interview(room_folder: Path, process: str) -> Card:
    """Stage 2's card: the interviews already in the room, each with its own bytes beside it.

    Reads the room; writes nothing. Where the room holds no interview for this process the card
    offers to hold one here instead — a longer path to the same decision, never a wall.
    """
    held = interview.held(room_folder, process)
    saved = read_record(room_folder, run_file(process))
    return Card(
        stage=STAGE_2,
        name="interview",
        heading=HEADING_2,
        activities=(process,),
        body=(PICK if held else NO_INTERVIEW).format(process=process),
        sources=tuple(sorted([item.path for item in held] + _room_source(room_folder, METHOD))),
        buttons=GRADIENT if held else (HOLD_IT_NOW,),
        decision=DECISION_2 if held else DECISION_NO_INTERVIEW,
        rule=RULE_2 if held else RULE_HOLD,
        gradient=GRADIENT,
        method=_method(room_folder),
        saved=saved,
        revision=_revision(saved),
        interviews=held,
    )


def chosen(room_folder: Path, process: str, path: str) -> Card:
    """The same card with the pick made: one interview left, and the four labels to answer it.

    The pick is not on disk, because nothing is saved until the label is pressed — so the page
    hands it back the way it hands back the revision it read. A path the card never offered picks
    nothing, and the card comes back as it was.
    """
    card = pick_interview(room_folder, process)
    picked = tuple(item for item in card.interviews if item.path == path)
    if not picked:
        return card
    return replace(card, interviews=picked, body=CHOSEN, decision=DECISION_CHOSEN)


def _bind_interview(
    room_folder: Path, card: Card, picked: interview.Interview, answer: str,
    confirmed: Sequence[str] = (),
) -> Card:
    """The pick and the answer in one save: what this BIA rests on, and the bytes it rested on.

    Beside the one bound, the run keeps every interview he confirmed, in his order (ticket 168):
    the bound one comes first where he left it out, each path only once, and a path outside the
    room raises ``PathRefused`` before anything is saved.
    """
    process = card.activities[0]
    kept = list(dict.fromkeys(confirmed if picked.path in confirmed
                              else (picked.path, *confirmed)))
    for path in kept:
        jailed_path(room_folder, path)
    confirming: Record = {INTERVIEWS_CONFIRMED: kept}
    saved = _save(room_folder, process, card.revision, _advanced(
        card.saved or {}, STAGE_2, _reserving(answer), on_card=card.name,
        transcript={"name": picked.name, "path": picked.path,
                    "fingerprint": picked.fingerprint},
        **confirming))
    if saved is None:
        return _overtaken(pick_interview(room_folder, process))
    return _answered(card, STAGE_2, HEADING_2, BOUND if answer == ENDORSED else NAMING, saved)


def held_interview(
    room_folder: Path, process: str, turns: tuple[conduct.Turn, ...]
) -> Card:
    """Stage 2's card for the interview just held in the room: the whole of it, and one decision.

    Reads the room; writes nothing, which is the story's contract — nothing of a live interview is
    on disk until this card is answered. What is offered is the interview itself, previewed whole
    and carrying the fingerprint of exactly the bytes the press would file, so a yes is a yes to
    named bytes before there are any.

    The four labels and no more: a live interview is a **longer path, not a more expensive gate**
    (`docs/stage-model.md` Stage 2). There is no confirmation card in front of this one, because
    keeping the interview *is* the stage 2 decision.
    """
    kept = interview.about_to_be_filed(
        interview_path(process), conduct.transcript(process, turns))
    return replace(pick_interview(room_folder, process), body=CONDUCTED, buttons=GRADIENT,
                   decision=DECISION_CHOSEN, rule=RULE_2, interviews=(kept,))


def _keep_interview(
    room_folder: Path, card: Card, picked: interview.Interview | None, answer: str,
    confirmed: Sequence[str] = (),
) -> Card:
    """Stage 2 answered: the interview this BIA rests on, filed first where it is not on disk yet.

    One path for both of stage 2's, because they differ in one thing only — whether the bytes the
    manager read are already a file in the room. An interview held here and now is not, so it goes
    down **before** the record: an answer that loses the compare-and-set leaves the manager's own
    words in the room rather than throwing away an interview they gave, and the card that comes
    back offers stage 2 again with this interview now one of the things on it. Which it is, is
    read off the room rather than carried as a flag — the file either already says what the
    preview promised or it does not.

    Nothing to bind is not an answer and saves nothing: a room holding two interviews is waiting
    for the manager to choose between them, and a room holding none is waiting for one to be held.

    The filing is only ever of bytes this card holds whole (``interview.previewed_whole``). An
    interview the company wrote is previewed at its first characters, so a pick read before that
    file moved is a stale card and never a restore: writing its preview back would replace the
    transcript with its own opening, and then bind the fingerprint of bytes nobody has. Stage 2 is
    offered again instead, drawn on the file as it now stands, and nothing is bound.
    """
    kept = picked or (card.interviews[0] if len(card.interviews) == 1 else None)
    if kept is None:
        return card
    if interview.digest(jailed_path(room_folder, kept.path)) != kept.fingerprint:
        if not interview.previewed_whole(kept):
            return pick_interview(room_folder, card.activities[0])
        write_file(room_folder, kept.path, kept.preview)
    return _bind_interview(room_folder, card, kept, answer, confirmed)


def interview_findings(room_folder: Path, process: str) -> list[str]:
    """What a later stage must carry about the interview this walk rests on.

    Empty while the file still holds the bytes it held when it was chosen. A file that has moved
    under the walk is a **finding** — data carried to the card and to the signature, never a wall
    (``CONTEXT.md``) — because the referee's whole claim is that every quote is verbatim in a
    readable file, and it would be making that claim about bytes nobody chose.
    """
    bound = (read_record(room_folder, run_file(process)) or {}).get("transcript")
    if not bound or _still_says_what_it_said(room_folder, bound):
        return []
    return [CHANGED.format(name=bound["name"])]


def _still_says_what_it_said(room_folder: Path, bound: Record) -> bool:
    """Whether the bound interview still holds the bytes it held — read through the room's jail.

    The path is read back out of a file on disk, so by the time it is used it is input, whatever
    wrote it. Every other room path in this module reaches the disk through ``room_store``, which
    sits below both this module and ``nemo.interview`` precisely so that neither has to remember
    the rule; this was the one that joined ``room_folder`` to a string itself, and a walk must not
    digest a file outside its own room to decide whether its own evidence moved.

    A refused path is not a crash: a finding is data carried to the card and to the signature,
    never a wall (``CONTEXT.md``), and a binding that no longer names a file inside the room is
    exactly the thing the manager has to be told about rather than the thing that stops them.
    """
    try:
        target = jailed_path(room_folder, bound["path"])
    except PathRefused:
        return False
    # Pins the bool the comparison hands back: a record's values are `Any`, so `==` against one
    # is `Any` too, and this function's whole answer would leave the type system unchecked.
    unchanged: bool = interview.digest(target) == bound["fingerprint"]
    return unchanged


# ── stage 3: the evidence, standardised ──────────────────────────────────────


def evidence_card(room_folder: Path, process: str) -> Card:
    """Stage 3's card: the server's own draft of the standardised evidence, and its working.

    Reads the room; writes nothing. What may be claimed is ``nemo.evidence``'s — an RTO only where
    a label and a figure stand together, a register dependency by its exact id and an unmodelled
    one as an open item — and the prose around it is here, because prose is what a card is.

    The card leads with whatever the evidence forces a decision about and puts what is already
    settled after it, which is the one thing about this card a reader has to settle rather than a
    test (`archive/qa/stage-3-standardise-the-interview-evidence.md` step 10).
    """
    saved = read_record(room_folder, run_file(process)) or {}
    bound = saved["transcript"]
    draft = evidence.standardise(
        interview.text(jailed_path(room_folder, bound["path"])),
        _read_json(room_folder / REGISTER),
        method_lenses(saved.get("method") or {}))
    return _with_his_answers(room_folder, Card(
        stage=STAGE_3,
        name="evidence",
        heading=HEADING_3,
        activities=(process,),
        body=_drafted(draft),
        sources=tuple(sorted([bound["path"], *_room_source(room_folder, REGISTER),
                              *_room_source(room_folder, METHOD)])),
        buttons=GRADIENT,
        decision=DECISION_3,
        rule=RULE_3,
        gradient=GRADIENT,
        method=_method(room_folder),
        saved=saved,
        revision=_revision(saved),
        proposal=draft.proposal,
    ))


def _answer_evidence(room_folder: Path, card: Card, words: str,
                     turn_id: str | None = None) -> Card:
    """The one press: the draft into the run state, and the label it was answered with.

    The tap is what advances the stage. A label other than *endorsed* reserves something and the
    card says so, but the walk has already moved on — a manager who says nothing further is not
    stuck, and disagreeing costs no more than agreeing (`docs/voice.md` §4.3).
    """
    process = card.activities[0]
    asked = open_questions(room_folder, card)
    if asked:
        return _answer_open(room_folder, card, asked[0], words, turn_id)
    answer = _gradient(words)
    if answer is None:
        return _not_caught(card)
    saved = _save(room_folder, process, card.revision, _advanced(
        card.saved or {}, STAGE_3, _reserving(answer), on_card=card.name, **card.proposal))
    if saved is None:
        return _overtaken(evidence_card(room_folder, process))
    write_file(room_folder, _at_step_3(process), json.dumps(card.saved))
    return _answered(card, STAGE_3, HEADING_3,
                     STANDARDISED if answer == ENDORSED else NAMING, saved)


def _answer_open(room_folder: Path, card: Card, question: referee.Question, words: str,
                 turn_id: str | None = None) -> Card:
    """Stage 3's press while a referee question is still open: the question's own words answer it,
    and anything else answers nothing and saves nothing."""
    # t116 (the owner, TYPED, ce2e8d7b): a step answer never settles an open referee question;
    # t224: the question's own words answer it, through this door
    said = THE_QUESTION_S.get(text.norm(words))
    if said is None:
        return replace(card, body=QUESTION_OPEN, buttons=(), decision="", rule="")
    return _answer_question(room_folder, card, question, said, turn_id)


#: t116: what stage 3 says when an answer meets a referee question still open. No figure: the
#: question's own card, drawn by the skin, carries the figures and his three answers.
QUESTION_OPEN = ("A question the check asked is still open, so this step is not answered and "
                 "nothing is saved. Answer the question first; the step's own answers come back "
                 "then.")


#: t224: his answers to the referee's questions, held on the run by activity until stage 3's
#: proposal carries them (`_with_his_answers`): each is the record's `ANSWERS` entry as it stands.
QUESTIONS_ANSWERED = "questions_answered"
#: t224: the activity whose Keep waits for his reason. His next typed line is it (`_take_reason`).
REASON_FOR = "reason_for"
#: t224: the label `nemo.evidence` states an MTPD under, which a Withdraw gives the grid's figure
MTPD_LABEL = "MTPD"
#: t224: the question card's own words, each the answer it is (116's three).
THE_QUESTION_S = {text.norm(words): said for words, said in (
    (referee.KEEP, referee.KEEP), (referee.WITHDRAW, referee.WITHDRAW),
    ("leave open", referee.LEAVE_OPEN), (referee.LEAVE_OPEN, referee.LEAVE_OPEN))}
#: t116's reason ask after his Keep, moved here from the phone skin by t224 so the door asks it too
ASK_KEEP_REASON = ("Recorded: you keep {value}. Why? Type your reason in one line and it goes on "
                   "the record beside the figure, word for word.")


def _answer_question(room_folder: Path, card: Card, question: referee.Question,
                     said: str, turn_id: str | None = None) -> Card:
    """t224: his answer to the open question, saved on the run through the walk's own save path,
    with the two figures it answered (116's amendment 1: it counts while both still match). A Keep
    then asks his reason, and his next typed line is it."""
    process = card.activities[0]
    saved = _save(room_folder, process, card.revision, _held(card, question, said, turn_id))
    if saved is None:
        return _overtaken(evidence_card(room_folder, process))
    fresh = evidence_card(room_folder, process)
    if said != referee.KEEP:
        return fresh
    return replace(fresh, body=ASK_KEEP_REASON.format(value=question.asserted), buttons=(),
                   decision="", rule="")


def _held(card: Card, question: referee.Question, said: str,
          turn_id: str | None = None) -> Record:
    """The run with his answer held on it by activity, and a Keep waiting for his reason. A
    Withdraw keeps the quote that stated the figure he withdrew (14_nemo_check's ruling (b)); a
    question is only ever asked of an MTPD the interview stated, so there is always one. A Withdraw
    given its turn holds that turn beside it (t232), which its evidence then cites."""
    run = card.saved or {}
    quote = next(s["quote"] for s in _stated(card, question.activity) if s["label"] == MTPD_LABEL)
    entry = referee.his_answers(said, question.asserted, question.derived, quote=quote)
    return {**run, QUESTIONS_ANSWERED: {**run.get(QUESTIONS_ANSWERED, {}),
                                        question.activity: {**entry[ANSWERS],
                                                            **_its_turn(said, turn_id)}},
            **({REASON_FOR: question.activity} if said == referee.KEEP else {})}


def _its_turn(said: str, turn_id: str | None) -> Record:
    """t232: the turn a Withdraw was given, as its held answer keeps it; nothing for any other."""
    return {TURN_ID: turn_id} if turn_id and said == referee.WITHDRAW else {}


def _stated(card: Card, activity: str) -> list[Record]:
    """What the interview states under that activity, as stage 3's proposal carries it."""
    return [s for a in card.proposal["activities"] if a["name"] == activity for s in a["evidence"]]


def _awaited(run: Record) -> Callable[[Path, str, Record, str, int], Card] | None:
    """What this walk waits to hear before any card is answered: the naming of a reservation, or
    his reason for the figure he kept (t224). Either way the composer is the walk's."""
    if _last_decision(run).get("naming") == UNNAMED:
        return _take_naming
    return _take_reason if run.get(REASON_FOR) else None


def _take_reason(room_folder: Path, process: str, run: Record, words: str, revision: int) -> Card:
    """t224: the line after his Keep is his reason, word for word. A manager with nothing to say
    is not made to say it: his Keep stands with no reason, in nemo's fixed words (116)."""
    activity = run[REASON_FOR]
    held = run[QUESTIONS_ANSWERED]
    kept = held[activity][referee.ASSERTED_MTPD]
    if not _NOTHING_TO_NAME.match(text.norm(words)):
        held = {**held, activity: referee.his_answers(
            referee.KEEP, kept["asserted"], kept["derived"], words.strip())[ANSWERS]}
    saved = _save(room_folder, process, revision, {
        **{k: v for k, v in run.items() if k != REASON_FOR}, QUESTIONS_ANSWERED: held})
    if saved is None:
        return _overtaken(evidence_card(room_folder, process))
    return evidence_card(room_folder, process)


def _with_his_answers(room_folder: Path, card: Card) -> Card:
    """t224: stage 3's proposal with his answers on the activities they answer, so the record it
    makes carries them (`ANSWERS`). Each counts only while the question it answered is the one
    asked: both figures for a Keep or a Leave open; for a Withdraw the figure he withdrew, and the
    MTPD then follows the grid (116's amendment 1)."""
    held = (card.saved or {}).get(QUESTIONS_ANSWERED)
    if not held:
        return card
    asked = {q.activity: q for q in open_questions(room_folder, card)}
    acts = [_his_answer_on(activity, asked.get(activity["name"]), held.get(activity["name"]),
                           _his_act(room_folder, held.get(activity["name"])))
            for activity in card.proposal["activities"]]
    return replace(card, proposal={**card.proposal, "activities": acts})


def _without(entry: Record | None, key: str) -> Record:
    """The entry with that one key left off (t232: a held turn, or the act a row cites)."""
    return {k: v for k, v in (entry or {}).items() if k != key}


def _his_act(room_folder: Path, held: Record | None) -> Record | None:
    """t232: his Withdraw typed at the door, as the record carries his act (the skin's `his_act`,
    t132/t171): his words on the turn it held, that turn's day and its id, read from the room's
    turn file. A turn not on the file gives no words, and the referee refuses the row rather than
    guess them. No turn held, no act: the interview's quote stands, as before 232."""
    turn_id = (held or {}).get(TURN_ID)
    if not turn_id:
        return None
    said = next(iter(turn_file.his_turns(room_folder, {turn_id}).values()), {})
    return {TYPE: CHAT_CONFIRMATION, WORDS: said.get("words", ""), ON: said.get("on", ""),
            TURN_ID: turn_id}


def _his_answer_on(activity: Record, question: referee.Question | None,
                   held: Record | None, act: Record | None = None) -> Record:
    entry = (held or {}).get(referee.ASSERTED_MTPD) or {}
    if question is None or not _answers_it(entry, question):
        return activity
    carried = {**activity, ANSWERS: _without(held, TURN_ID)}
    if entry["answer"] != referee.WITHDRAW:
        return carried
    return {**carried, "evidence": _the_grid_s(activity["evidence"], question.derived, act)}


def _answers_it(entry: Record, question: referee.Question) -> bool:
    """Whether his answer answers the question asked now: the figure he answered still asserted,
    and for a Keep or a Leave open the grid's figure unmoved too (116's amendment 1)."""
    return entry.get("asserted") == question.asserted and (
        entry["answer"] == referee.WITHDRAW or entry["derived"] == question.derived)


def _the_grid_s(stated: list[Record], derived: str, act: Record | None = None) -> list[Record]:
    """A withdrawn MTPD: the grid's figure, as it derives now, where the interview stated his;
    and his act, where he withdrew it on a turn (t232), as what the record cites for it."""
    return [{**s, "value": derived, **({bia.HIS_ACT: act} if act else {})}
            if s["label"] == MTPD_LABEL else s for s in stated]


def open_questions(room_folder: Path, card: Card) -> list[referee.Question]:
    """The referee's open questions over the record this stage-3 card would make (t116).

    The record stage 4 builds is the run with this card's proposal on it, so the question is
    asked of that record here, before the answer that would close the stage is saved. Through
    ``_refereed``, so it is the one check over the one set of bytes — the room's readable files
    included, which is what tells an evidence-backed figure from an asserted one.
    """
    run = {**(card.saved or {}), **card.proposal}
    if not run.get("activities"):
        return []
    return _refereed(room_folder, run, card.method or _method(room_folder))[1].questions


def _take_naming(
    room_folder: Path, process: str, run: Record, words: str, revision: int
) -> Card:
    """What was typed, taken as the naming of the reservation **this** walk is waiting to hear.

    It names the BIA it was made on, which is defect 1 of
    `docs/reviews/code-review-2026-09-13.md`: the walk is the one the manager is working through
    and no longer whichever of the room's runs sorts first, so with two walks live in one room — the
    ordinary state, which ``in_progress`` exists to list — a reservation made on one BIA can no
    longer be filed against another and the unreserved one cannot reach the signature carrying
    "unnamed".

    A manager who says there is nothing to record is not made to record one: the walk read a caveat
    into a plain answer, that costs him one extra question, and the answer goes back to standing as
    endorsed with no reservation on it at all (`docs/voice.md` §4.3 — that pressure is for someone
    who said nothing). Only the whole line waves it off, and only off *endorsed with reservations*:
    *needs discussion* and *blocked* are refusals and nothing turns one into an endorsement, so what
    he types after one is its naming (ticket 234).
    """
    stage = int(_last_decision(run)["stage"])
    builds, heading = _RESERVED_AT[stage]
    waved = (_last_decision(run).get(GRADIENT_FIELD) == RESERVED
             and bool(_NOTHING_TO_NAME.match(text.norm(words))))
    saved = _save(room_folder, process, revision,
                  _unreserved(run) if waved else _named(run, words))
    if saved is None:
        return _overtaken(builds(room_folder, process))
    return _answered(builds(room_folder, process), stage, heading,
                     NOTHING_RESERVED if waved else TAKEN, saved)


def namings(record: Record) -> tuple[tuple[int, str], ...]:
    """What each answered card reserved, by stage — what the signature carries forward.

    Verbatim, because a reservation summarised is a reservation answered on behalf of the person
    who made it. A reservation nobody named carries ``UNNAMED`` and reaches the signature as that.
    """
    return tuple((int(decision[AT_STAGE]), str(decision[NAMING_FIELD]))
                 for decision in record.get(DECISIONS, []) if NAMING_FIELD in decision)


def report(record: Record) -> str:
    """What this run cost and what it is worth — both facts, and neither without the other."""
    argued = [decision for decision in record.get(DECISIONS, [])
              if decision.get(GRADIENT_FIELD, ENDORSED) != ENDORSED]
    return ARGUED.format(count=len(argued)) if argued else UNARGUED


def _drafted(draft: evidence.Draft) -> str:
    """The draft as prose: what needs deciding first, and what the interview settles after it."""
    leads = [LEAD, *draft.open_items] if draft.open_items else []
    unreached = [UNREACHED.format(lenses=", ".join(draft.unknown), reason=draft.not_elicited)
                 ] if draft.unknown else []
    return "\n\n".join([
        *leads, SETTLED, *(_states(statement) for statement in draft.statements),
        *(RESOLVES.format(heard=item.heard, asset_id=item.asset_id)
          for item in draft.dependencies if item.asset_id),
        *unreached])


def _states(statement: evidence.Statement) -> str:
    """One statement, reason before figure: why it stands, and only then what it stands at."""
    template = OWNER_SAYS if statement.owner_stated else ASSERTED
    return template.format(speaker=statement.speaker, label=statement.label,
                           value=statement.value, quote=statement.quote)


def _reserving(answer: str) -> Record:
    """The answer as recorded. Anything but *endorsed* reserves something, unnamed until named."""
    return ({GRADIENT_FIELD: answer} if answer == ENDORSED
            else {GRADIENT_FIELD: answer, NAMING_FIELD: UNNAMED})


def _last_decision(record: Record) -> Record:
    """The answer this walk gave last, or nothing at all where it has given none."""
    decisions: list[Record] = [{}, *record.get(DECISIONS, [])]
    return decisions[-1]


def _named(record: Record, words: str) -> Record:
    """The record with the words on the answer that reserved something, exactly as typed."""
    decisions = list(record[DECISIONS])
    return {**record, DECISIONS: [*decisions[:-1], {**decisions[-1], NAMING_FIELD: words}]}


def _unreserved(record: Record) -> Record:
    """The record with the reservation taken back off that answer, because he made none.

    Off the record rather than emptied on it: a naming of nothing at all is a reservation with
    nothing in it, and the signature would carry it as one. The answer stands as endorsed, which
    is what he said when he was asked.
    """
    decisions = list(record["decisions"])
    kept = {key: value for key, value in decisions[-1].items() if key != "naming"}
    return {**record, "decisions": [*decisions[:-1], {**kept, "gradient": ENDORSED}]}


# ── stage 4: the refereed record ─────────────────────────────────────────────

#: What the card proposes: the BIA record itself, and the referee's verdict on it. The record is
#: carried rather than rebuilt at the press, so the bytes that land are the bytes that were read.
#: What the referee found rides under ``FINDINGS``, which is ``nemo.record``'s word because it is
#: the same word the run files them under and the handover reads them back by.
BIA = "bia"
CHECKED = "checked"


def record_card(room_folder: Path, process: str) -> Card:
    """Stage 4's card: the BIA this run has produced, refereed before anybody is asked about it.

    Reads the room; **writes not one byte**. The referee has already run by the time the card is
    drawn, which is the whole shape of this stage: what it will not settle rides on the card as
    findings the human accepts along with the record, and what it refuses outright means there is
    no card to accept at all — a content problem reaches the human *before* the tap rather than as
    a wall behind it, which is v1's sixteen-problem wall the other way up (`docs/voice.md` §4.3).
    """
    saved = read_record(room_folder, run_file(process)) or {}
    method = _method(room_folder)
    drafted, verdict = _refereed(room_folder, saved, method)
    return Card(
        stage=STAGE_4,
        name="record",
        heading=HEADING_4,
        activities=(process,),
        body=(_record_says(process, saved, verdict, method) if verdict.passed
              else refused_says(verdict.rejections)),
        sources=tuple(sorted([saved["transcript"]["path"], *_room_source(room_folder, REGISTER),
                              *_room_source(room_folder, METHOD)])),
        buttons=GRADIENT if verdict.passed else (),
        decision=DECISION_4 if verdict.passed else "",
        rule=RULE_4 if verdict.passed else "",
        gradient=GRADIENT,
        method=method,
        saved=saved,
        revision=_revision(saved),
        proposal={BIA: drafted, CHECKED: verdict.checked, FINDINGS: verdict.findings},
        refused=tuple(verdict.rejections),
        record_revision=_revision(_record_at(room_folder, process)),
    )


def check_draft(room_folder: Path, process: str) -> referee.Verdict:
    """What is wrong with this walk's draft record, asked before anybody has confirmed anything.

    Writes nothing, asks for nothing and answers with the record's own content problems. v1 took
    an unconfirmed draft and answered "approval missing", so the owner said yes and *then* read
    sixteen problems; the rule that no bytes land unconfirmed is unchanged, only the order is.
    """
    saved = read_record(room_folder, run_file(process)) or {}
    _, verdict = _refereed(room_folder, saved, _method(room_folder))
    return verdict


def _accept_record(room_folder: Path, card: Card, answer: str | None) -> Card:
    """The one press: the record onto disk, then the picture drawn from it and the receipt bound.

    Two movements behind one tap and in this order (`docs/stage-model.md`), both synchronous:
    nothing about the picture is left for a later job, because a job that can run late can fail to
    run at all and nobody notices — which is exactly what happened in `adler-stjmed` on
    2026-08-31, where a run declared itself closed while the graph URL showed nothing new.

    A stop between the two is the ordinary path rather than the crash path, and it costs the
    second movement again: `_save_record` is the first on its own, `_draw_graph` the second, and a
    resume calls the second over whatever the first left on disk (ADR-0010).

    **A record the referee refused is never saved, whatever words answered it** (ticket 170). The
    refused card draws no buttons and asks nothing, but typed words reach this press all the same,
    and until then one plain "endorsed" wrote the refused record and bound its receipt. The answer
    gets the card back as it stands — the refusal, and no way to accept it — and not one byte is
    written. `test_every_route_to_the_record_write_passes_the_refusal_check` holds every route to
    the record's write to this one check.

    **A stale answer writes nothing either** (ticket 172). An answer on a card revision the run has
    moved past — a second tap on an old card, a second tab — is refused as overtaken before the
    record is written, not after: the run's compare-and-set in `_save_record` came second, so until
    then the loser landed the record first.
    `test_every_route_to_the_record_write_passes_the_stale_check` holds every route to it too.

    A line that says none of the four writes nothing as well, and the card asks which one (234b);
    it is read after the refusal, because a refused card asks nothing.
    """
    if _refused(card):
        return card
    if answer is None:
        return _not_caught(card)
    if _stale(room_folder, card):
        return _overtaken(record_card(room_folder, card.activities[0]))
    return _draw_graph(room_folder, _save_record(room_folder, card, answer))


def _stale(room_folder: Path, card: Card) -> bool:
    """Whether the run moved on since the page read this card: the revision the answer travelled
    with against the run on disk, read before any byte of the answer is written. The run's own
    compare-and-set in `_save` still stands behind it."""
    return card.revision != _revision(read_record(room_folder, run_file(card.activities[0])))


def _refused(card: Card) -> bool:
    """Whether the referee refused the record this card would save: the one check every route to
    the record's write passes first. It reads the card's own verdict because that verdict is on
    the very bytes the press would write (`card.proposal[BIA]`), not on a record re-read later."""
    return bool(card.refused)


def _save_record(room_folder: Path, card: Card, answer: str) -> Card:
    """The first movement: the record onto disk, and the run at saved-and-not-yet-finished.

    The record lands first and the run state follows it, because the run file is a claim and the
    artefact is the truth (ADR-0010): a stop between the two leaves a record that the next resume
    re-derives identically rather than a claim about a record nobody wrote.

    The receipt goes with it. A receipt is taken over the record that was on disk when the page
    was drawn, so a record write is what makes the old one stop being a receipt for anything —
    leaving it standing is how a walk would open stage 5 over a picture of a record nobody has.

    **Both movements are one write, so the room is held for both** (ticket 211, ticket 208's
    finding B6). The caller's stale check reads the run before this is called, and between that
    read and the land is a window his second tab fits into: a press whose record had not moved but
    whose run had landed the record and was told it had lost *afterwards*, leaving the record he
    signs written by the press that lost. The run's revision is read again here, under the room's
    own lock and before the land, and the lock is held until the run is saved — so the answer to
    "has this run moved?" is still true when the record goes down. It cannot be a reorder: the run
    write carries `record_sha=fingerprint(landed)`, which is a fingerprint of the record the land
    assigns a revision to, so the run cannot be saved first.

    One read of a value that was already there, under a lock that was already there (208), and no
    second guard type (ADR-0007). `room_lock` is reentrant because `_land` and `_save` each take
    it again through `write_record`.
    """
    process = card.activities[0]
    with room_lock(room_folder):
        if _stale(room_folder, card):
            return _overtaken(record_card(room_folder, process))
        landed = _land(room_folder, card)
        if landed is None:
            return _overtaken(record_card(room_folder, process))
        # What the referee raised over this record, kept because stage 5 carries every finding
        # onto the handover and the certificate, and a document rendered from the record and the
        # run may not go back to the transcript for it: a finding re-derived hours later is a
        # finding about whatever the file says then.
        extra: dict[str, Any] = {FINDINGS: list(card.proposal[FINDINGS]), RECEIPT: None}
        saved = _save(room_folder, process, card.revision, _advanced(
            card.saved or {}, STAGE_4, _reserving(answer), on_card=card.name,
            status=RECORD_SAVED, checked=list(card.proposal[CHECKED]),
            record_sha=fingerprint(landed), **extra))
        if saved is None:
            return _overtaken(record_card(room_folder, process))
    views.write(room_folder, landed)
    return _answered(card, STAGE_4, HEADING_4, NAMING if answer != ENDORSED else
                     " ".join([ACCEPTED, checked_note(saved), SAVED_NOT_FINISHED]), saved)


def _draw_graph(room_folder: Path, card: Card) -> Card:
    """The second movement: the receipt that binds the walk to the record on disk, on
    `record_sha`. nemo draws no picture of its own (ADR-0040); the grouped graph is the skin's.

    Everything it writes is a function of the record bytes and of nothing else (ADR-0004), so
    running it again rewrites the same bytes: that is what makes a stop cost the movement again
    rather than a repair. It is also why it does not stop when the receipt already binds — the
    movement again costs nothing and can only agree.

    The four documents are drawn again here for the same reason the picture is. `_save_record`
    writes them one after another, so a stop between them leaves the room holding some of the four
    and, over a second walk, the one before it under the rest — while the run goes on to
    `AWAITING_HUMAN` and stage 5 hands them over. That is v1's G3 family, a delivered document
    disagreeing with the record it claims to come from, and the cure is the movement again rather
    than a ledger of which of the four landed (ADR-0007): they are the same function of the same
    record bytes, so writing them again writes the same bytes.

    It draws over a record this run wrote and no other. A press that lost a race left somebody
    else's record or somebody else's run behind it, and neither is this walk's to draw.
    """
    run = read_record(room_folder, run_file(card.activities[0])) or {}
    record = _ours_to_draw(room_folder, run)
    if record is None:
        return card
    views.write(room_folder, record)
    saved = _save(room_folder, card.activities[0], _revision(run),
                  {**run, STATUS: AWAITING_HUMAN, RECEIPT: _receipt_for(record)})
    if saved is None:
        return card
    return replace(card, body=card.body.replace(SAVED_NOT_FINISHED, PICTURE_DRAWN),
                   saved=saved, revision=_revision(saved))


def _ours_to_draw(room_folder: Path, run: Record) -> Record | None:
    """The record in the room iff it is this run's own work, saved and not yet drawn from.

    A press that lost a race left somebody else's record or somebody else's run behind it, and
    neither is this walk's to draw — so the answer is the record itself or nothing at all, and
    never a claim about a record this walk cannot name.
    """
    record = _record_of(room_folder, run)
    if run.get(AT_STAGE) != STAGE_4 or not bia.is_ours(record, run.get("run_id")):
        return None
    return record


def _record_of(room_folder: Path, run: Record) -> Record | None:
    """The record at this run's process's place in the room; none for a run naming no process."""
    return _record_at(room_folder, run["process"]) if "process" in run else None


def _record_at(room_folder: Path, process: str) -> Record | None:
    """This process's record: at its own place, or at the room's pre-235 place if it names it.

    Rooms walked before ticket 235 hold their one record at ``output/bia-record.json``, signed walks
    among them. That record names its process in its own ``dept`` (``bia.build`` writes the run's
    process there), so it is this process's iff the name is this process's, and never another's.
    Reading it moves nothing: a signed walk's record is never moved by anyone looking at it. The
    process's next record write moves it (``_land``).
    """
    record = read_record(room_folder, record_file(process))
    if record is not None:
        return record
    legacy = read_record(room_folder, _LEGACY_RECORD)
    return legacy if legacy is not None and legacy.get(DEPT) == process else None


def _receipt_for(record: Record) -> Record:
    """The receipt that says which record stage 4 bound: its fingerprint, and its schema version.

    Nothing about a page (ADR-0040). The gate compares `record_sha` and nothing else, so a receipt
    that described a picture would describe something no reader of it checks.
    """
    return {"record_sha": fingerprint(record),
            "record_version": record.get("record_schema_version")}


def move_past_stage_4(room_folder: Path, run: Record) -> Record:
    """The record this walk may carry into stage 5, or the refusal that says why it may not.

    The one gate v1 did not have, and it asks two things. Which run produced the record, because
    a walk may only finish over its own work — `nemo.bia` says why a modification time cannot be
    what that rests on. And whether the receipt was bound over *this* record, which is
    `record_sha` against the record's own fingerprint and nothing else (ADR-0040): on 2026-09-02
    in `adler-yj3477` a gate written against the exact page deadlocked the moment an operator
    re-rendered it, and a deadlock is the false closure wearing the opposite sign.
    """
    record = bia.own(_record_of(room_folder, run), run.get("run_id"))
    if (run.get(RECEIPT) or {}).get("record_sha") != fingerprint(record):
        raise NotDrawnYet
    return record


# ── stage 5: consolidate, hand over, and sign ────────────────────────────────

#: What the stage 5 card proposes: the two documents the acceptance writes, the record they were
#: rendered from, and the open items the signature accepts by id. Carried on the card rather than
#: re-rendered at the press, so the bytes that land are the bytes the manager read.
DOCUMENTS = "documents"
ITEMS = "items"


def handover_card(room_folder: Path, process: str) -> Card:
    """Stage 5's card: the two documents, rendered from the record this walk's receipt binds.

    Reads the room; **writes not one byte**. The gate is ``move_past_stage_4`` and nothing else —
    the record is this run's own work and the picture on disk was drawn from *this* record — so a
    walk whose picture is not bound yet is told it is saved and not yet finished rather than shown
    a handover for a record nobody has.
    """
    run = read_record(room_folder, run_file(process)) or {}
    record = move_past_stage_4(room_folder, run)
    documents = handover.documents(record, run)
    return Card(
        stage=STAGE_5,
        name="handover",
        heading=HEADING_5,
        activities=(process,),
        body="\n\n".join([HANDING_OVER.format(process=process), *documents.values()]),
        sources=(record_file(process),),
        buttons=GRADIENT,
        decision=DECISION_5,
        rule=RULE_4,
        gradient=GRADIENT,
        method=_method(room_folder),
        saved=run,
        revision=_revision(run),
        proposal={BIA: record, DOCUMENTS: documents},
    )


def accept_handover(room_folder: Path, card: Card, answer: str) -> Card:
    """The one gradient answer: the two documents onto disk, and the run at reviewed-pending-owner.

    **Accepting is not signing.** No certificate is written here, no name is asked for here, and
    the run stops at ``REVIEWED`` — which is the state stage 5 stays in for every sign-off that
    does not close it, so a certificate on disk can only ever mean a signature with authority.

    **A stale answer writes nothing at all** (ticket 180, as 172 at stage 4). An answer on a card
    revision the run has moved past — a second tap on an old card, a second tab — is refused as
    overtaken before the run is moved and before a document is written.
    `test_every_route_to_a_handover_document_passes_the_stale_check` holds every route to it.

    **Then the run's revision is asked, and the documents go down after it** (ticket 208, finding
    B6). They used to go down first, for the reason ``save_record`` gives — the artefact is the
    truth and the run file is a claim — and that order let a press that had already lost write its
    documents anyway: with two of his tabs on one room, the stale one replaced the handover and
    the requirements the winning press had just rendered, and *then* learned it was overtaken.
    The manager was left reading a document from a record the room had moved past. Losing at the
    compare has to cost nothing, so the compare comes first. The stale check stands in front of
    both, so the ordinary second tap never reaches either write; the compare-and-set is what
    catches a run that moved in the breath after the check.

    What that trades away is small and re-derivable: a stop between the two now leaves the run at
    ``REVIEWED`` with the documents not yet written, where before it left the documents with the
    run not yet moved. Both documents are a function of the record and the run and of nothing else
    (``handover.documents``), so the second movement is re-renderable from what is on disk — which
    is exactly what ADR-0010 asks of a movement that can be stopped, and is not true of a document
    somebody else's press overwrote. ``resume`` re-renders it (ticket 207), over the run *without*
    the decision this press is landing: what he read was rendered before it existed, and
    ``_on_the_way_here`` is the one line of that.

    So the order is: the stale check, then the run, then the two documents.
    """
    process = card.activities[0]
    if _stale(room_folder, card):
        return _overtaken(handover_card(room_folder, process))
    saved = _save(room_folder, process, card.revision, _advanced(
        card.saved or {}, STAGE_5, _reserving(answer), on_card=card.name, status=REVIEWED))
    if saved is None:
        return _overtaken(handover_card(room_folder, process))
    _hand_over(room_folder, card.proposal[BIA], card.proposal[DOCUMENTS], saved)
    return _answered(card, STAGE_5, HEADING_5,
                     ACCEPTED_5 if answer == ENDORSED else NAMING, saved)


def _hand_over(room_folder: Path, record: Record, documents: Record, run: Record) -> None:
    """The documents stage 5 hands over, under the folder of the record they were rendered from.

    One site, so the bytes the press writes and the bytes a resume writes again cannot land in two
    places or under two names (ticket 207). An earlier walk's signed certificate leaves its name
    first, so this run's documents never stand beside it (ticket 245), and each document is marked
    as this run's once it is down.
    """
    _set_aside(room_folder, record, run)
    for name, document in documents.items():
        write_document(room_folder, f"{views.folder(record)}/{name}", document)
        _mark(room_folder, record, name, run)


def _documents_again(room_folder: Path, run: Record) -> None:
    """Stage 5's movement again, for an acceptance whose documents a stop left unwritten (207).

    `accept_handover` asks the run's revision before it writes the two documents (ticket 208), so a
    stop between the two leaves the run at `REVIEWED` and the room holding the documents of the walk
    before it, or none at all — the torn artefact `_draw_graph` pays for one stage earlier. Both are
    `handover.documents` of the record and of the run as the card had it (`_on_the_way_here`), so
    the movement again writes the bytes the press would have (ADR-0004): nothing to roll back, and
    no ledger of which of the two landed (ADR-0007). It writes only a document that is not on disk
    (`_on_disk`, ticket 235c); one that is stays as it was written.

    A document an earlier walk of this process wrote is not on disk for this run, and is written
    over (ticket 245).

    It writes over a record this run's own receipt binds and no other, and `move_past_stage_4` is
    already that gate. Where it refuses, the room moved under this acceptance and the documents on
    disk are the winning walk's — replacing them is exactly what 208 closed — so a refusal writes
    nothing and is not raised at anybody: a resume serves the state on disk and asks nothing.
    """
    try:
        record = move_past_stage_4(room_folder, run)
    except (bia.StaleRecord, NotDrawnYet):
        return
    rendered = handover.documents(record, _on_the_way_here(run))
    _hand_over(room_folder, record, {name: document for name, document in rendered.items()
                                     if not _on_disk(room_folder, record, name, run)}, run)


def _on_disk(room_folder: Path, record: Record, name: str, run: Record) -> bool:
    """Whether this run's document `name` is in this record's folder: a resume writes only where
    none is.

    ADR-0010 read literally (ticket 235c, 21_nemo_check): the movement again writes what a stop left
    unwritten. A document on disk is what the manager read, or signed, in the words of the renderer
    of that day; today's renderer writing over it would change a signed certificate under him.
    "On disk" is on disk for this run (ticket 245): one `WRITTEN_BY` gives to another run is an
    earlier walk's, and is not.
    """
    return (jailed_path(room_folder, f"{views.folder(record)}/{name}").is_file()
            and _written_by(room_folder, record).get(name, run.get("run_id")) == run.get("run_id"))


def _written_by(room_folder: Path, record: Record) -> Record:
    """Which run wrote each of stage 5's documents in this record's folder (`WRITTEN_BY`)."""
    return read_record(room_folder, f"{views.folder(record)}/{WRITTEN_BY}") or {}


def _mark(room_folder: Path, record: Record, name: str, run: Record) -> None:
    """The document `name`, just written, marked as this run's."""
    write_file(room_folder, f"{views.folder(record)}/{WRITTEN_BY}", json.dumps(
        {**_written_by(room_folder, record), name: run.get("run_id")}))


def _set_aside(room_folder: Path, record: Record, run: Record) -> None:
    """An earlier walk's signed certificate, moved off its name to `SET_ASIDE` (ticket 245).

    The name is this walk's own closing signature's; the bytes are what somebody signed, so they
    are never written over and never deleted, only renamed beside the documents of the walk now.
    """
    by = _written_by(room_folder, record).get(handover.CERTIFICATE, run.get("run_id"))
    certificate = jailed_path(room_folder, f"{views.folder(record)}/{handover.CERTIFICATE}")
    if by != run.get("run_id") and certificate.is_file():
        certificate.replace(jailed_path(room_folder,
                                        f"{views.folder(record)}/{SET_ASIDE.format(run=by)}"))


def _on_the_way_here(run: Record) -> Record:
    """The run as the handover card rendered its documents from: every answer before this handover.

    The press writes the bytes the manager read (`accept_handover`), and he read them before his own
    acceptance was a decision on the run — `handover_card` writes nothing, so the document quoting
    the reservations made *on the way here* cannot quote the answer that is still landing. The
    movement again is held to the same line: it writes what the press would have written and not one
    line more, because a document nobody's press ever wrote is the same disagreement as one drawn
    off the wrong record, and neither is what a stop is supposed to cost.
    """
    decisions: list[Record] = run[DECISIONS]
    return {**run, DECISIONS: [decision for decision in decisions
                               if decision.get(AT_STAGE) != STAGE_5]}


def signature_card(room_folder: Path, process: str) -> Card:
    """What the signature asks for: a name and a role, over the open items signing accepts.

    Identity is demanded at exactly one moment in the whole walk and this is it (ADR-0003), so the
    card says whose signature closes this and lists every open item by the id it is accepted
    under — including a dependency nobody owns, which is a finding carried here rather than a sixth
    stage that goes looking for its owner. Signing accepts every one of them (his ruling on 239).

    Only a run whose handover he accepted is signed (ticket 239): any other gets the card with the
    sentence saying why and nothing to answer, never an exception.
    """
    run = read_record(room_folder, run_file(process))
    if run is None or run.get(STATUS) != REVIEWED:
        return _nothing_to_sign(room_folder, process, run)
    record = move_past_stage_4(room_folder, run)
    open_items = handover.items(record, run)
    return Card(
        stage=STAGE_5,
        name="signature",
        heading=HEADING_5,
        activities=(process,),
        body="\n\n".join([SIGNING.format(owner=figures.listed(handover.owners(record)) or NOBODY),
                          *([SIGNING_CHOICE.format(owner=figures.listed(handover.owners(record)))]
                            if signing_choices(record) else []),
                          *(handover.ITEM.format(id=at, text=text) for at, text in open_items)]),
        sources=(record_file(process),),
        buttons=(),
        decision=DECISION_SIGN,
        rule=RULE_SIGN,
        gradient=(),
        method=_method(room_folder),
        saved=run,
        revision=_revision(run),
        proposal={BIA: record, ITEMS: dict(open_items)},
    )


def _nothing_to_sign(room_folder: Path, process: str, run: Record | None) -> Card:
    """The signature card of a run nothing signs: the reason, and no question under it."""
    return Card(stage=STAGE_5, name="signature", heading=HEADING_5, activities=(process,),
                body=ALREADY_SIGNED if (run or {}).get(STATUS) == CLOSED else NOT_ACCEPTED_YET,
                sources=(record_file(process),), buttons=(), decision="", rule="", gradient=(),
                method=_method(room_folder), saved=run, revision=_revision(run))


def signing_choices(record: Record) -> tuple[tuple[str, str], ...]:
    """Who he can sign as, as the taps nemo draws: the label, and the choice each one carries.

    Two of them where the record names one owner (ADR-0030 decision 7): as the owner, or on behalf
    of them. The second element is what the tap passes into `sign` — `AS_THE_OWNER`, or the
    record's own spelling of an owner's name — so the choice a tap makes can never be free text or
    a hidden setting, and a caller can tell "he chose to sign as the owner" from "nobody has
    chosen yet", which is what lets a skin ask him before it signs anything.

    None at all where the record names no owner (12_nemo_check's amendment to 134): "on behalf of"
    has no name to carry there and "as the owner" would claim an ownership the record does not
    state, so he signs as he did before this ticket and no third tap is invented for it.
    """
    named = handover.owners(record)
    if not named:
        return ()
    return ((SIGN_AS_THE_OWNER, AS_THE_OWNER),
            *((SIGN_ON_BEHALF.format(owner=owner), owner) for owner in named))


def reopen(room_folder: Path, process: str) -> Record | None:
    """Back to stage 3 after the record was accepted: the signature is what does not undo.

    The owner ruled on 2026-09-17 that the point of no return is the signature, not stage 4: a
    manager reading the handover who spots a wrong figure fixes it and comes forward again. The run
    goes back to how it stood when stage 3 closed, saved through its own revision, so a card read
    before the reopen is stale after it and the revision never moves back.

    Two things the stages after that close wrote are kept (t71, t71b): every reservation made since
    is carried under `CARRIED`, each once, and the notes a tool call left stay under
    `MODEL_NOTES`. The run as saved comes back, or None and nothing written where there is nothing
    to reopen: a signed run, a reservation still waiting for his words, a stage 3 never closed, or
    a run that moved while this read it.
    """
    with room_lock(room_folder):
        run = read_record(room_folder, run_file(process)) or {}
        at_close = _reopenable(run, read_record(room_folder, _at_step_3(process)))
        if at_close is None:
            return None
        kept = _reservations(at_close)
        carried = [*at_close.get(CARRIED, []), *(
            {AT_STAGE: stage, NAMING_FIELD: words}
            for stage, words in _reservations(run) if (stage, words) not in kept)]
        notes = {MODEL_NOTES: run[MODEL_NOTES]} if MODEL_NOTES in run else {}
        return _save(room_folder, process, _revision(run), {**at_close, CARRIED: carried, **notes})


def _reopenable(run: Record, at_close: Record | None) -> Record | None:
    """The run as stage 3 closed, or None where a reopen is refused: signed, or naming awaited."""
    if run.get(STATUS) == CLOSED or _last_decision(run).get(NAMING_FIELD) == UNNAMED:
        return None
    return at_close


def _reservations(run: Record) -> list[tuple[int, str]]:
    """Every reservation the run holds in his words: those a reopen carried, then its own."""
    return [*((int(held[AT_STAGE]), str(held[NAMING_FIELD])) for held in run.get(CARRIED, [])),
            *((stage, words) for stage, words in namings(run) if words != UNNAMED)]


def sign(room_folder: Path, card: Card, name: str, role: str, on_behalf_of: str = "") -> Card:
    """The signature: a name and a role over the items shown, and the run closed iff it may be.

    **A signature must identify somebody with authority to give it.** The signer is compared with
    the owner the *record* holds for the activity and never with the role string they typed: in v1
    a sign-off whose signer's role read "explicitly not the process owner" validated cleanly,
    because nothing checked who signed, and a check that read the role would pass that same
    sign-off the moment it called itself something better.

    **Who he signs as is his own explicit choice** (ADR-0030 decision 7, ticket 134), and it comes
    in here as ``on_behalf_of``: empty or `AS_THE_OWNER` is "as the owner", which his name decides
    as it always did, and a name is "on behalf of them", which has to be one of the record's own
    names or
    `handover.NotAnOwner` is raised at it. The live app decided this from a role string it kept in
    a module global, which is the check this walk has never made and never will.

    A signature with authority moves the run to ``CLOSED`` and writes the certificate; anybody
    else's is recorded as the sponsor or reviewer acceptance it is, the run stays at ``REVIEWED``
    and no certificate exists to call it the owner's. The certificate is written after the run
    closes, so the document on disk is only ever there for a run that actually closed.

    The card comes in, as it does at every other press: it carries the record the signer read the
    open items off, and **signing accepts every open item on it, never more and never fewer** (his
    ruling on ticket 239), so what is accepted is exactly what was shown. A press overtaken while
    they were typing their name lands on nothing and comes back current, and a card that asked
    nothing — a signed run, or a handover nobody accepted — is answered with the room's own.
    """
    process = card.activities[0]
    if not _signable(card.saved):
        return signature_card(room_folder, process)
    record = card.proposal[BIA]
    given = _signature(record, name, role, tuple(card.proposal[ITEMS]), on_behalf_of)
    closing = handover.closes(given[CAPACITY])
    saved = _save(room_folder, process, card.revision, {
        **(card.saved or {}), SIGNATURE: given, **_closed_or_reviewed(closing)})
    if saved is None:
        return _overtaken(signature_card(room_folder, process))
    note = (_certified(room_folder, record, saved) if closing
            else _beside_the_owner(record, given[CAPACITY]))
    return _answered(card, STAGE_5, HEADING_5, note, saved)


def _closed_or_reviewed(closing: bool) -> Record:
    """Where a signature leaves the run: closed and dated with the day, or reviewed and undated."""
    return {STATUS: CLOSED, SIGNED_ON: _now()[:10]} if closing else {STATUS: REVIEWED}


def _signable(run: Record | None) -> bool:
    """Whether a signature may land on this run: its handover accepted, and nobody signed yet."""
    return (run or {}).get(STATUS) == REVIEWED


def _signature(record: Record, name: str, role: str, accepted: tuple[str, ...],
               on_behalf_of: str) -> Record:
    """The signature as it lands in the run: what was typed, and the capacity it was given in.

    Two of the four are the signer's own words, and the open items are the card's, accepted whole
    (ticket 239). The fourth is not typed and cannot be: what capacity a signature is given in is
    decided against the owner the record holds and against his own choice of the two the card
    offers, which is why a signer who calls themselves the process owner does not become one by
    saying so.
    """
    return {SIGNER: name, ROLE: role, ACCEPTED_FIELD: list(accepted),
            CAPACITY: handover.capacity(
                record, name, None if on_behalf_of in ("", AS_THE_OWNER) else on_behalf_of)}


def _certified(room_folder: Path, record: Record, saved: Record) -> str:
    """The certificate onto disk for a run that closed, and what the walk says about it.

    Written after the run closes, so a certificate in the room can only ever be there for a
    signature that had the authority to close it. An earlier walk's goes aside first, never under
    this one (ticket 245).
    """
    _set_aside(room_folder, record, saved)
    write_document(room_folder, f"{views.folder(record)}/{handover.CERTIFICATE}",
                   handover.certificate(record, saved))
    _mark(room_folder, record, handover.CERTIFICATE, saved)
    return SIGNED_OFF


def _beside_the_owner(record: Record, capacity: str) -> str:
    """What the walk says to a signer who cannot close it: what they were recorded as, and who can.

    A refusal that named nobody would leave the manager holding a run they cannot finish and no
    way to find out who could, so the owner the record holds is said back to them.
    """
    return NOT_THE_OWNER.format(
        capacity=capacity, owner=figures.listed(handover.owners(record)) or NOBODY)


#: Which card a reservation was named on, by the stage that recorded it: stage 4 reuses stage 3's
#: composer, so the card that takes the naming has to be the stage it was named on and not a
#: literal — a manager who reserved something at stage 4 is not answered by a stage 3 heading.
#: Every stage that can be answered with a reservation has a row, the handover included: without
#: one, the one door raised ``KeyError`` at a manager it had just asked to name what he reserved
#: (ticket 206). It stands here, below the last of the builders, for the reason the table under it
#: gives — a row names the function that serves that stage.
_RESERVED_AT = {STAGE: (open_bia, HEADING), STAGE_2: (pick_interview, HEADING_2),
                STAGE_3: (evidence_card, HEADING_3), STAGE_4: (record_card, HEADING_4),
                STAGE_5: (handover_card, HEADING_5)}


#: Which card follows which, and what has to be true on disk before it does. One row per stage, in
#: the order the walk runs, so adding a stage is a row rather than another branch in ``onward`` —
#: and so the condition each stage is followed under is named for what it means to the walk. It
#: stands here, below the last of them, because a row names the function that serves that stage.
_WHAT_FOLLOWS = (
    (STAGE, _agreed, pick_interview),
    (STAGE_2, _rests_on_an_interview, evidence_card),
    (STAGE_3, _evidence_answered, record_card),
    (STAGE_4, _record_accepted, handover_card),
)


def stages_done(run: Record | None) -> int:
    """How many of the five stages this run has done, read off its own file alone (ticket 247).

    Pure, for the skin's workspace page, which ticks these and marks the next. It asks what
    ``onward`` asks, in the same order, so a later stage's mark with an earlier stage unanswered
    is no progress: the walk never skips one. Stage 5 is done at the signature, which closes the
    run.
    """
    if (run or {}).get(STATUS) == CLOSED:
        return STAGE_5
    done = 0
    for stage, answered, _following in _WHAT_FOLLOWS:
        if stage == done + 1 and answered(run):
            done = stage
    return done


def checked_note(record: Record) -> str:
    """What this run actually checked before it wrote, or nothing at all where it checked nothing.

    Assembled from the referee's own account of which checks ran over this record, so a clause can
    only be here because the check that names it ran. v1's closure note was a literal asserting
    "record validated and saved" whatever the run did, and a literal cannot be made false.
    """
    checks = record.get(CHECKED) or []
    return CHECKED_NOTE.format(checks=figures.listed(checks)) if checks else ""


def where_it_stands(record: Record) -> str:
    """What the walk says about where it is: saved and not yet finished, where that is so."""
    return SAVED_NOT_FINISHED if record.get(STATUS) == RECORD_SAVED else ""


#: The two taps that print a table on their own turn (ticket 115): the grid, and the open decisions.
SHOW_TAPS = ("grid", "decisions")


def prints(stage: int | None, tapped: str, *, decision_open: bool = False,
           record_due: bool = False) -> list[str]:
    """What a turn prints, in order (ticket 115, the owner's "nothing long prints until I ask").

    The answer first; then, at stage 3 with a decision open, the one card whose taps are live; at
    stage 4 with the record due, the record (ADR-0022, the record before the signature). The grid
    and the open decisions print only on the turn their tap was pressed, and that turn has no
    answer: the table is all it draws. Nothing else prints. `tapped` is "" on a turn with no show
    tap.
    """
    if tapped in SHOW_TAPS:
        return [tapped]
    return (["answer"] + ["live_card"] * (stage == STAGE_3 and decision_open)
            + ["record"] * (stage == STAGE_4 and record_due))


#: Ticket 117 (t63's order, moved here from the skin): the open decisions at stage 3 in nemo's
#: order. The figure that sets the MTPD, the conflicts about the MTPD (the method's own rule among
#: them), the other conflicts, the other clocks, the category scores a batch can take. A kind not
#: named here comes after them all.
DECISION_ORDER = ("MTPD", "MTPD conflict", "conflict", "RTO", "RPO", "score")


def _about_the_mtpd(item: dict[str, Any]) -> bool:
    """A conflict is about the MTPD when it is the method's rule, or a side implies an MTPD."""
    return str(item.get("id")).endswith("-MTPD-RULE") or any(
        isinstance(implies := side.get("implies"), dict)
        and str(implies.get("item_id")).endswith(".mtpd")
        for side in item.get("sides") or [])


def _decision_rank(item: dict[str, Any]) -> int:
    """An item naming no kind sorts last with the kinds nemo does not order (ticket 210): the
    stage-3 list draws whatever the draft holds, and one odd item must not take the whole list."""
    kind = item.get("type")
    if kind == "conflict" and _about_the_mtpd(item):
        kind = "MTPD conflict"
    return DECISION_ORDER.index(kind) if kind in DECISION_ORDER else len(DECISION_ORDER)


def live_first(open_items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The open decisions in nemo's order, the live one first; the draft's order within a kind.

    Ticket 117, the owner's ruling: "the narrated card and the tap target are the same object".
    The taps, the live card, the open-decisions table and every lookup the model reads take their
    order from here and nowhere else, so the first item the model is served is the one his tap
    records.
    """
    return sorted(open_items, key=_decision_rank)


def _land(room_folder: Path, card: Card) -> Record | None:
    """The record on disk after this press, or None where the room's record moved on first.

    A movement whose artefact is already correct writes nothing: re-running it after a stop
    rewrites identical bytes by definition (ADR-0010), and identical bytes written twice would
    move the revision under whoever is reading them.
    """
    drafted = card.proposal[BIA]
    with room_lock(room_folder):
        already = _record_at(room_folder, card.activities[0])
        if _already_landed(already, drafted):
            return already
        try:
            if _left_at_the_old_place(room_folder, card, already):
                return None
            return write_record(room_folder, record_file(card.activities[0]), drafted,
                                card.record_revision)
        except StaleWrite:
            return None


def _already_landed(already: Record | None, drafted: Record) -> bool:
    """The record on disk is this draft already, whatever revision it was written at."""
    return already is not None and {key: value for key, value in already.items()
                                    if key != "revision"} == drafted


def _left_at_the_old_place(room_folder: Path, card: Card, already: Record | None) -> bool:
    """The record is still at the room's pre-235 place, and this write does not move it here.

    Nothing on disk, or the record already at this process's own place, is never overtaken: the
    write decides. A record left at the old place is overtaken unless `_moved_in` moves it.
    """
    return already is not None and read_record(room_folder, record_file(
        card.activities[0])) is None and not _moved_in(room_folder, card, already)


def _moved_in(room_folder: Path, card: Card, legacy: Record) -> bool:
    """The record at the room's pre-235 place moved to this process's own, a write about to land.

    Only a write that will land moves it: one answered against another revision moves nothing and
    is told so, and the record stays where every reader still finds it. It is moved and not
    copied, so no second copy of one record is left to drift from the first.
    """
    if _revision(legacy) != card.record_revision:
        return False
    target = jailed_path(room_folder, record_file(card.activities[0]))
    target.parent.mkdir(exist_ok=True)
    jailed_path(room_folder, _LEGACY_RECORD).replace(target)
    return True


def readable(room_folder: Path, saved: Record) -> dict[str, str]:
    """The files a quote in this record may have come from: the interviews this run confirmed.

    Read from the run record, in the order he confirmed them, because that order decides which file
    a quote found in two is cited to (ticket 131). The record keeps them since ticket 168; a run
    saved before that holds its one bound transcript, and that is the whole list for it.
    """
    paths = saved.get(INTERVIEWS_CONFIRMED) or [saved["transcript"]["path"]]
    return {str(path): interview.text(jailed_path(room_folder, str(path))) for path in paths}


def _refereed(
    room_folder: Path, saved: Record, method: Record
) -> tuple[Record, referee.Verdict]:
    """This run's record and the referee's verdict on it, built once out of the run state.

    One place, because the check made before the human is asked and the check the card is drawn
    from have to be the same check over the same bytes: two spellings of it is how a draft could
    come back clean from ``check_draft`` and refused on the card, or the reverse.
    """
    files = readable(room_folder, saved)
    drafted = bia.build(saved, files)
    checked = {**files, **cited_register(room_folder, drafted)}
    return drafted, referee.review(drafted, method, checked, confirmed_turns(room_folder, drafted))


def _evidence_items(record: Record) -> list[Any]:
    """Every evidence item of every activity in `record`, whatever its shape."""
    return [item for activity in record.get(ACTIVITIES) or [] if isinstance(activity, dict)
            for item in activity.get(EVIDENCE) or []]


def _names_the_register(item: Any) -> bool:
    """Whether an evidence item is a register row citing the room's own register."""
    return isinstance(item, dict) and item.get(TYPE) in (REGISTER_ROW, REGISTER_NO_RPO) \
        and item.get(SOURCE_PATH) == REGISTER


def cited_register(room_folder: Path, record: Record) -> dict[str, str]:
    """The room's dependency register, where a register row in `record` names it (ticket 171):
    what the referee holds each register row against. Only the room's own register is read, and
    only for the referee: it is no interview, so a quote is never attributed to it."""
    if not any(_names_the_register(item) for item in _evidence_items(record)):
        return {}
    try:
        return {REGISTER: jailed_path(room_folder, REGISTER).read_bytes().decode()}
    except OSError:
        return {}


#: t171: the turn under way in each room, by the room's folder: its id and his words on it, with
#: its day. A caller writes a turn's line only once the turn is over, and an act of his is refereed
#: in the very turn he takes it, so until then this is the line his act rests on (241).
IN_FLIGHT: dict[str, tuple[str, dict[str, str]]] = {}


def confirmed_turns(room_folder: Path, record: Record) -> dict[str, dict[str, str]]:
    """His words on every turn a chat confirmation in `record` names, read from the room's turn
    file (ticket 132), and from the turn under way (`IN_FLIGHT`) where the file does not hold it
    yet: what the referee holds each confirmation against. None named, none read."""
    wanted = {turn_id for activity in record.get(ACTIVITIES) or []
              for turn_id in _confirmed_turn_ids(activity)}
    turn_id, said = IN_FLIGHT.get(str(room_folder), ("", {}))
    under_way = {turn_id: said} if turn_id in wanted else {}
    return {**under_way, **turn_file.his_turns(room_folder, wanted)} if wanted else {}


def _confirmed_turn_ids(activity: object) -> set[str]:
    """The turn every chat confirmation in one activity's evidence names."""
    if not isinstance(activity, dict):
        return set()
    return {str(item.get(TURN_ID)) for item in activity.get(EVIDENCE) or []
            if isinstance(item, dict) and item.get(TYPE) == CHAT_CONFIRMATION}


def refused_says(rejections: Sequence[refusal.Rejection]) -> str:
    """What stage 4 says where the referee will not pass the record: every refusal, as prose.

    One sentence per refusal, in the order the referee found them, and none of the referee's own
    words among them: what it hands over is parts, and the words are ``REFUSAL_SAYS``'s.
    """
    return REFUSED.format(problems=" ".join(_refusal_says(item) for item in rejections))


def _refusal_says(rejection: refusal.Rejection) -> str:
    """One refusal as a sentence for the manager: the referee's parts, this module's words, and
    for a band MTPD the edge the target was held against (t74)."""
    sentence = _sentence_for(rejection) + (EDGE_SAYS if rejection.parts.get("edge") else "")
    return sentence.format(
        **{name: _part_says(name, value) for name, value in rejection.parts.items()})


def _sentence_for(rejection: refusal.Rejection) -> str:
    """The sentence a refusal is said in: its kind's, unless it is a chat confirmation's (ticket
    132), which was held against his message and never against a file."""
    parts = rejection.parts
    if "turn" not in parts:
        return REFUSAL_SAYS[rejection.kind]
    if "claimed" in parts:
        return CHAT_TURN_MISDATED
    if rejection.kind == refusal.QUOTE_NOT_FOUND:
        return CHAT_WORDS_NOT_FOUND
    return CHAT_TURN_NOT_HELD


def _part_says(name: str, value: Any) -> str:
    """One part as a manager reads it: a list as a list, a field name as what it stands for, and
    anything that is not words as the plain admission that it is not.

    A part is whatever the record put there, and a record the store will hold can carry a grid
    where a score belongs. Printing that is `{'a': 1}` on a stage 4 card — the same data structure
    reaching the same manager the ticket's own `impact_grid['legal-regulatory']` reached, by the
    one door left open. A figure still prints as itself: a score of `6` is refused for being off
    the scale, and a card that would not say which figure it means is worse than one that does.
    """
    if name == refusal.MISSING:
        return figures.listed([MISSING_SAYS[field] for field in value])
    return _value_says(value)


def _value_says(value: Any) -> str:
    """The part where its name has already been read: several of a thing, or one of it.

    Split from `_part_says` rather than recursing into it, because the recursion could only ever
    re-ask a question already answered — an item of a list is not the list's field name — and a
    branch no input can take is a mutant no test can kill.
    """
    if isinstance(value, tuple):
        return figures.listed([_value_says(item) for item in value])
    return _word_for(value)


def _word_for(value: Any) -> str:
    """A part where it already is words or a figure, and `NOT_WORDS` where it is neither.

    `True` is not a figure anybody wrote on a form, whatever Python says about `bool` and `int`.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or not isinstance(value, int | float):
        return NOT_WORDS
    return str(value)


def _record_says(process: str, saved: Record, verdict: referee.Verdict, method: Record) -> str:
    """The refereed record as prose: what is being decided, what is open, then what is settled.

    In that order on purpose. What the referee will not settle comes before what it did settle,
    because on a department with five activities the decision has to be findable from the first
    screen of a phone rather than at the bottom of the card.
    """
    open_items = [*saved.get("open_items", []), *verdict.findings]
    leads = [OPEN_4, *open_items] if open_items else []
    return "\n\n".join([
        ACCEPTING.format(process=process), *leads, DRAWN,
        *(line for activity in saved.get("activities") or []
          for line in _activity_says(activity, method))])


def _activity_says(activity: Record, method: Record) -> list[str]:
    """One activity on the card: the reason before every figure, and the sentence behind each.

    How long it can be down is `nemo.figures.stands`, which is also what stage 4b's worksheet says:
    the card and the document a human reads hours later must not say one figure two ways, and the
    cheapest way to hold that is for there to be one sentence.
    """
    name = activity["name"]
    return [
        figures.stands(activity, method),
        *(SCORED_SAYS.format(speaker=score["speaker"], lens=score["lens"], activity=name,
                             quote=score["quote"]) for score in activity["scores"]),
        # t232: his act cited under a withdrawn MTPD is the record's; the card says the statement
        *(_states(evidence.Statement(**_without(item, bia.HIS_ACT)))
          for item in activity["evidence"]),
        *(RESOLVES.format(heard=item["heard"], asset_id=item["asset_id"])
          for item in activity["dependencies"] if item["asset_id"])]


# ── what a press leaves on disk, and on screen ───────────────────────────────


def _answered(card: Card, stage: int, heading: str, body: str, saved: Record) -> Card:
    """The card of a stage that has just been answered: the confirmation, nothing left to press.

    No button, no decision, no rule and no gradient, at either stage — a card the manager has
    already answered must not read as if it were still asking, and the four labels drawn under a
    confirmation are exactly that. The ``Source:`` line and the method stay as the card carried
    them, because what the stage was decided against does not change by being decided.
    """
    return Card(stage=stage, name=card.name, heading=heading,
                activities=card.activities, body=body,
                sources=card.sources, buttons=(), decision="", rule="", gradient=(),
                method=card.method, saved=saved, revision=_revision(saved))


def _overtaken(card: Card) -> Card:
    """The stage as it now stands, with the news in front of it: somebody else saved first.

    The card is re-read rather than patched, so what the manager sees next is the room's own
    state and not the one their press was written against. Every stage that can be overtaken says
    it in one voice, stage 1 included; a second spelling is how two of them would come to say
    different things.
    """
    return replace(card, body=OVERTAKEN + " " + card.body)


def _now() -> str:
    """This walk's one clock: the moment, UTC, to the second.

    One function so a test pins one name and the deployed walk reads the same seam — the shape
    `nemo.door.sweep` already has for its own `time.time()`. To the second because a decision is a
    human typing a sentence, and a walk that recorded microseconds would be claiming a precision
    about a person that it does not have.
    """
    return datetime.now(UTC).isoformat(timespec="seconds")


def _advanced(opened: Record, stage: int, answer: Record, *, on_card: str,
              refused: Sequence[refusal.Rejection] = (), **fields: Any) -> Record:
    """The record as this press leaves it: the stage reached, and the answer on the end.

    Both stages leave it the same shape, and the shape is the referee's to read later — a second
    spelling of it here is how the two stages would come to disagree about what a decision is.

    A decision carries three things beside the answer, and `nemo.record` says why: the moment, the
    card it was taken on, and what the referee refused over the record it saved. `on_card` has no
    default, so a press that forgets to say which card it was is red rather than silent.
    """
    return {**opened, AT_STAGE: stage, STATUS: AWAITING_HUMAN, **fields,
            DECISIONS: [*opened.get(DECISIONS, []),
                        {AT_STAGE: stage, AT_TIME: _now(), ON_CARD: on_card,
                         REFUSALS: [{KIND: item.kind, PARTS: dict(item.parts)}
                                    for item in refused],
                         **answer}]}


def _save(room_folder: Path, process: str, revision: int, record: Record) -> Record | None:
    """The record as saved, or None where somebody else saved this BIA while it was being read.

    The store's refusal is turned into an answer here, once, because what a stage does about it is
    the stage's: Stage 1 re-reads the room, Stage 2 offers the interviews again. Neither loses the
    other's work, and there is nothing for a caller to forget to catch.
    """
    try:
        return write_record(room_folder, run_file(process), record, revision)
    except StaleWrite:
        return None


def _opened_run(room_folder: Path, card: Card) -> Record:
    """A run's identity is minted once and is not a function of the room's contents (ADR-0010).

    Minted at the press rather than at the opening, because opening a BIA writes nothing at all.
    Binding a finish to this identity is ticket 15's, and is not built here.
    """
    return {"run_id": str(uuid.uuid4()), "schema": SCHEMA, "room": room_folder.name,
            "process": card.activities[0], "method": card.method, "sources": list(card.sources)}


def _card(room_folder: Path, process: str, saved: Record | None) -> Card:
    agreed = _agreed(saved)
    body = RESUMED if agreed else PROPOSAL
    sources = _sources(room_folder, process)
    return Card(
        stage=STAGE,
        name="scope",
        heading=HEADING,
        activities=(process,),
        body=body.format(process=process, where=_where(sources)),
        sources=sources,
        buttons=() if agreed else (AGREE,),
        decision="" if agreed else DECISION.format(process=process),
        rule="" if agreed else RULE,
        gradient=() if agreed else GRADIENT,
        method=_method(room_folder),
        saved=saved,
        revision=_revision(saved),
    )


def _revision(saved: Record | None) -> int:
    return 0 if saved is None else int(saved["revision"])


def _where(sources: tuple[str, ...]) -> str:
    """Which of the room's two sources the process stands in, said in the manager's words."""
    places = [place for path, place in ((interview.INTERVIEWS, "your interview transcripts"),
                                        (REGISTER, "your dependency register"))
              if any(source.startswith(path) for source in sources)]
    return " and ".join(places)


# ── the room's files ─────────────────────────────────────────────────────────


def _sources(room_folder: Path, process: str) -> tuple[str, ...]:
    """Every file this proposal was read from, and nothing the proposal did not read.

    The company's own transcripts only: Stage 1 proposes a scope off what the company brought, and
    an interview the room held itself is evidence for the BIA rather than a source for the scope.
    """
    paths = interview.paths_about(room_folder, interview.INTERVIEWS, process)
    if process in _register_departments(room_folder):
        paths.append(REGISTER)
    return tuple(sorted(paths + _room_source(room_folder, METHOD)))


def _room_source(room_folder: Path, name: str) -> list[str]:
    """One room file for a card's ``Source:`` line, where the room has it.

    A room without the file names nothing rather than naming a path that is not there: the line
    says what this card was drawn against, and a card cannot have been drawn against an absence.
    """
    return [name] if (room_folder / name).is_file() else []


def _method(room_folder: Path) -> Record:
    """The room's own method parameters, copied. A parameter the file omits stays omitted.

    With them the method's word for past the last horizon, where it states one (t139): the
    referee reads it off this copy, so a word left behind here is a word nobody judges by.

    And the company the method names (t143), for the same reason: the record names the company
    it is about, and a record whose method copy left the name behind names nobody.
    """
    stated = _read_json(room_folder / METHOD)
    return {name: stated[name] for name in (*METHOD_PARAMETERS, BEYOND_HORIZONS, METHOD_ORG)
            if name in stated}


#: What a turn answers in a room whose file cannot be read (t297, t299): the file named, in nemo's
#: own words and with no model call, and never a crash nor a file read as empty.
UNREADABLE = ("I can't read {what}, {path}, because the file isn't valid JSON. Once it is put "
              "right, ask me again and I'll carry on.")

#: The room files a turn reads, each by what the note calls it, the register first (t299).
UNREADABLE_FILES = {REGISTER: "your dependency register", METHOD: "your BCM method",
                    ADDED: "the list of activities you added"}

#: 297's note, for the register.
UNREADABLE_REGISTER = UNREADABLE.format(what=UNREADABLE_FILES[REGISTER], path="{path}")


def unreadable_register(room_folder: Path) -> str | None:
    """Why the room's dependency register cannot be read (t297), or None where it can.

    A room with no register has none, as before; a register that is there and is not JSON (or not
    UTF-8) is named by its parse error, which is what whoever re-saves the file needs to read.
    """
    return _unreadable(room_folder / REGISTER)


def unreadable_file(room_folder: Path) -> tuple[str, str] | None:
    """The first of the room's `UNREADABLE_FILES` that cannot be read, and why (t299); None where
    each reads or is missing, for a missing one is none, as before."""
    return next(((path, why) for path in UNREADABLE_FILES
                 if (why := _unreadable(room_folder / path))), None)


def _unreadable(path: Path) -> str | None:
    try:
        _read_json(path)
    except ValueError as e:  # JSONDecodeError and UnicodeDecodeError alike
        return f"{type(e).__name__}: {e}"
    return None


def _register_departments(room_folder: Path) -> set[str]:
    """The departments the register names; none from one `unreadable_register` names instead."""
    if unreadable_register(room_folder):
        return set()
    return set(_named_departments(_read_json(room_folder / REGISTER)))


def _named_departments(value: Any) -> list[str]:
    """Every department the register names, wherever it names one — owner or consumer."""
    return [name for entry in _entries(value) for name in _own_department(entry)]


def _entries(value: Any) -> list[dict[str, Any]]:
    """Every object in the register, however deeply the file nests one inside another."""
    if isinstance(value, dict):
        return [value, *_entries(list(value.values()))]
    if isinstance(value, list):
        return [entry for item in value for entry in _entries(item)]
    return []


def _own_department(value: dict[str, Any]) -> list[str]:
    name = value.get(DEPARTMENT)
    return [name.strip()] if isinstance(name, str) and name.strip() else []


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes()) if path.is_file() else {}
