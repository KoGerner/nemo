---
status: accepted — ratified by the owner 2026-09-15
---

# The manager answers in his own words, and it is a chat rather than a room

**The owner's calls of 2026-09-13, drafted by a command shift for his ratification.** The reasoning
is his and was given in four parts in one sitting; the wording is a shift's, and the wording is what
an auditor and a BCM manager both read. Nothing here is ratified and nothing downstream may cite it
as settled.

## What he ruled

**One — it arrives knowing the company.** A chat opens already holding Marschkamp's own files: the
process register, the method, the transcripts under `07_Interviews/`. That is the point, not a
seeding accident, and it is what makes a whole BIA cycle cost about two prompts. This confirms the
substance of ADR-0011, which was ratified on 2026-09-15 and unratified on its own wording.

**Two — the four answers are text he replies to, not buttons he presses.** *endorsed*, *endorsed
with reservations*, *needs discussion*, *blocked* are listed in the card's own text, and the manager
types or says which one, the way an ordinary chat works. Asked directly whether he meant clickable
text or typed text, he chose typed.

**Three — the vocabulary is wrong.** "Minted room" is jargon no one understands. It is not a room at
all: **it is a chat.** Every user-facing string and every document should say so.

**Four — the last document hands over to the next step of the AI4BCM guidance.** Asked through the
ask lane against the frozen corpus at release `2026.09.1`, that step is **solutions design**: the
lifecycle runs governance, embedding, analysis, solutions design, implementation, validation, so a
BIA sits in analysis and its MTPD, RTO and RPO feed the choice of recovery strategies. The corpus
cites the AI4BCM glossary and NIST SP 800-34r1, and states its own gap — it holds no step-by-step
method for solutions design itself, so the handover carries figures and decisions, not a method.

## What ruling two costs, measured rather than estimated

The engine is ready for it. `answer_evidence` (`src/nemo/walk.py:438`) and `bind_interview`
(`:349`) already take a plain `answer: str` and never check it against `GRADIENT`; `take_naming`
(`:454`) is already free text. Nothing under `src/nemo/` is button-shaped. The work is in the skin.

Three things do break, and two of them are the owner's to settle rather than a shift's.

**The release bar does not survive as written.** `docs/stage-model.md:154` budgets five taps and at
most three typed inputs — two for the signature's name and role, one held in reserve. If each of
five cards is answered by typing, a clean run costs **seven**, against a bar of three. The owner's
own expectation of "about two prompts" is not reachable at one typed answer per card; it is only
reachable if one typed message answers more than one card, which no code path supports and which
sits against "5 stage cards answered". **This is open and is recorded as a question, not resolved
here.** Ticket 19 exists to measure this bar and must not be launched until it is restated.

**The composer question is settled by implication.** Open question 1 asked whether the chat box
belongs on screen. If the manager types his answer, it does. Two strict xfails escalated this to
the owner by name — `tests/ui/walk/test_the_walking_skeleton.py:140` and
`test_the_transcript_already_in_the_room.py:490` — and are settled against the steps they guard:
the composer stays and is now load-bearing, so those xfails and the steps behind them are deleted
rather than re-aimed.

**The typed box now has three jobs and can only tell two apart.** `demo_skin/app.py:265`'s
`on_message` arbitrates between a stage-3 naming and an ask-lane question, and it does so on room
state, not on what was typed: `take_naming` (`walk.py:515`) hands back a card only while a run is
waiting to name a reservation. A typed *card answer* is a third meaning with no branch at all.
Ordering it first costs the ask lane — a manager could no longer ask "what does MTPD mean?" while a
card is open without it being read as an answer. Matching the typed text against `card.gradient`
and falling through to the ask lane on no match is the natural fix and is unspecified product
design. This is the largest piece of unbuilt work the ruling creates.

Also reversed, and needing the owner rather than a shift because they are ADR-0006's:
`docs/voice.md:84` ("a card never needs it … never 'type your answer below'") and `:238`. The live
copy defect already on file — `demo_skin/app.py:68` and `src/nemo/walk.py:120` telling the manager
"there's nothing to type" beside a visible box — is settled by this ruling as simply false, and
becomes ordinary work rather than an open question.

## What ruling three obliges

"Room" is load-bearing vocabulary across `CONTEXT.md`, the door layer (`src/nemo/door.py`), ADR-0003
and ADR-0011's own title. A shift may rewrite user-facing copy freely. It may not retitle a ratified
ADR or amend ADR-0011, so the vocabulary change is recorded here and executed no further until the
owner says how far it goes — user-facing strings only, or the code's own nouns as well.

## Status

**Drafted 2026-09-13, unratified.** Ratify or correct before ticket 19 is launched, since 19 quotes
the bar and the bar is the part this ADR leaves open.
