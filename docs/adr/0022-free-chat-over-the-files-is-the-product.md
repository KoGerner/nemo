---
status: accepted — decided by the owner 2026-09-21, grill Q1–Q9
---

# Free chat over the files is the product, and the walk is an output you ask for

## Context

The owner said it twice in twelve hours, in his own words. Late on 2026-09-20:

> "dont make it too complicated - easyness over jargon and vocabulary used and prompted and
> presented by nemo is being avoided. goal is user-experience and not perfection of nemo-prototype
> and nemo itself"

And on the morning of 2026-09-21:

> "its important to chat freely, like I would if I ask marschkamp files right now with the plugin
> ask-ai4bcm included. not all what-if, MTPD, RTO, etc questions must be answerred"

Thirty of the thirty-two tickets on `proto/board.py` describe the structured walk: stage cards, taps,
the grid, the signed record. The build had been optimising *completeness* — every question shape
handled, every room layout covered — and the cost was visible. Ticket 82's diagnosis on the same
morning found the manager waiting **662 seconds** on a single lane call, because the confirm tap
rebuilds the entire structured draft with the filed interview in the prompt; the *background* draft of
the same activity in the same run took **8.9 seconds**. A 75× cost to regenerate a document he may
never read is completeness bought with his time.

## Decision

**Chatting freely over a company's files is the product. The structured walk is an output he asks
for, not a path he is marched down.** The five stages remain nemo's internal spine — nemo keeps its
stage state and the method's shape — but the conversation, not the stage pointer, drives.

Nine decisions, taken in one grilling session:

1. **The walk is an output, not the spine of the experience** (Q1b). A spine must be completed; an
   output need not be.
2. **The 10 November demo is a conversation** (Q2b) — talking to nemo about Marschkamp, with a record
   produced on demand at the end, not a walk-and-sign.
3. **The relaxation stops at the record** (Q3a). nemo may decline to answer anything; a figure that
   reaches the certificate still says honestly where it came from. The owner's gate rulings of
   2026-09-21 (80, 93, 83, 94) are untouched by this ADR.
4. **The bar is measurable** (Q4a): about twenty questions a BCM manager would really ask of the
   files, scored on **three columns only** — answered from the files or honestly declined; no invented
   figure; a reply inside **30 s** (ticket 69's existing ceiling, not a second number). Three columns,
   never more: an eight-column bar is a completeness checklist wearing a new hat.
5. **The stages stay as the internal spine** (Q5a, emphatically the owner's). This ADR does not touch
   the method.
6. **nemo blocks only where the record would lie** (Q5b-c), and mentions the rest. `must_see`-style
   forcing survives exactly where skipping would make a signed document dishonest.
7. **A record may be partial** (Q6a), covering what was actually discussed and saying plainly what it
   does not cover. Honest and partial beats complete and padded — the same rule as (3), one level up.
8. **Every existing ticket is re-evaluated against this goal** (Q6b), in its own session, because that
   is thirty-two judgements and the scope of a ticket is the owner's.
9. **The bar is built as a ticket immediately after 82** (Q8a), drafted by the line and edited by the
   owner (Q9b), from the Marschkamp files.

## What this does not relax

- **The signed record.** Provenance, the gates, 75's box, the guard on the owner's phone.
- **The method.** Stages, the grid, the derivations, the referee.
- **The no-company-bound-code rule.** A bar tuned to Marschkamp's wording is still a rule written
  generally and proven on one seed.

## Ticket disposition — decided by the owner, 2026-09-21

Six finish, six pause. This is the **ordering** decision ADR-0022 anticipated, not the full scope
pass: decision 8 above still sends all thirty-two tickets to their own re-evaluation session, and
**cutting remains the owner's**. Nothing below is cancelled.

**Finish — these protect the signed record, which this ADR does not relax**

| | why it is not completeness |
|---|---|
| **79** | each line says who wrote it; the signing card stops counting a calculated figure as an AI proposal he confirmed |
| **80 + 94** | the AI proposes; a figure lands only on his tap. 94 folds into 80's fix 2 — same hole from two ends |
| **93** | his typed figure is no longer silently replaced by the derivation; nemo shows both and asks |
| **83** | leaving a conflict unresolved puts named people on his certificate; that act is his |
| **84** | rebuilt as his removal — a referral names the activity's owner, never a capture note |

The demo argument decided it: the first hard question a BCM audience asks is *"where did that number
come from?"*, and "the AI set it, recorded as the manager's decision" ends the conversation. These
five are the answer. They are also all mid-review — pausing loses findings already in hand and leaves
**half-gates**, the AI blocked on one route and not another, which is worse than either state.

**82 finishes as goal work, not as a distraction.** A 662-second reply fails the chat bar by itself.

**Pause — the walk's mechanics**

- **89, 90** — who each document addresses.
- **63's last box** — stage 3 read on a real phone.
- **91**, except his own first item (plain system names) and **its precondition**: the fidelity checks
  must stop keying on prose. That precondition is **infrastructure, not polish** — rewording
  `GAP_WORDS` reds 21 of 80 walks today, so *any* wording change needs it, chat included.
- **62** — *"you can go back into stage 3 until you sign"* was designed because the walk only moves
  forward. **In a conversation he simply says the figure is wrong.** Not built, not deleted: it goes to
  the re-evaluation session as the clearest case of a ticket this focus may dissolve.
- **61**, the ADR behind 62, waits with it.

**69 becomes more important, not less.** Its 30-second ceiling is the chat bar's third column: it was
a walk metric and is now the product's responsiveness. Still blocked on 82.

**64 unchanged** — 64c last, written once against behaviour that exists.

## Consequences

- **Coverage gaps stop being findings.** The check session does not send work back because a question
  shape or an unusual room layout is unhandled. A defect that needs a contrived scenario to appear is
  registered, not built.
- **82's fix aims at the prompt.** Not at moving the wait: a background rebuild buys one turn's cover,
  since `confirm_interviews` reads the draft 32.5 s later. The first question the fix asks is whether
  the full rebuild is needed on confirm at all.
  **Corrected 2026-09-21, the owner's approval (AskUserQuestion in 17_nemo, 2fc2092b):** the premise
  above is false. The 8.9 s draft drafted nothing: 0 activities, 228 completion tokens, and `walkable`
  rejects it. Its prompt differs from the 662 s one by 490 of 75,550 tokens. Across 35 real drafts the
  prompt is constant to 0.7% while the time varies 66×. The median is 44.5 s and 23 are over 30 s. So
  the prompt is not the lever, and the full rebuild on confirm is needed: it is the only draft that
  exists. Recipes are in proto `.build/t82-report.md` §F1–F2. **The owner's ruling that replaces this
  bullet:** the confirm tap is allowed to be slow; nemo tells him plainly that it is drafting and
  roughly how long; 69 names this tap as its one exception.
- **Ticket 95** (the chat bar) is registered and built after 82.
- **Ordering changes, cutting does not** — until the re-evaluation session. Any ticket whose only
  justification is covering a rare case goes behind the chat work.

## Scope pass — ruled by the owner, 2026-09-21

Decision 8's re-evaluation, proposed in `docs/issues/nemo-walk/briefs/scope-pass-2026-09-21.md` and
ruled by the owner as proposed, on all four questions. **Nothing proven is reopened; the six finishing
tickets and 95 stand; the hold order (six → 95 → 69 → HOLD) is unchanged.**

- **62 closes on what exists**; nothing is built. The route predates it (proto `a181f61`).
- **61 is folded here** instead of being its own ADR. **The signature is the point of no return:**
  before signing, anything the manager says can change the record; a signed BIA is final; changing a
  signed BIA is a new cycle; changing the scope is a new BIA.
- **63 closes**; its real-phone box is dropped.
- **64 closes on 64b; 64c (the glossary) and the beginner gate are cut.** Term questions go to the
  guidance lane.
- **69 shrinks to the turn ceiling** (30 s worst, 10 s median). The full-walk bar is dropped, and
  `docs/what-good-looks-like.md` §3 carries the same note.
- **89 and 90 are cut**; one addressee per document stays a rule, applied only when a sentence is
  touched anyway.
- **91 shrinks to three wording changes** he sees first: plain system names, a plain section-4
  sentence, a shorter "Why" prefix. Its second finding is cut.
- **84's ticket file** now carries his rebuilt Done-when (the activity's owner, `sc.OWNERS`).

After the hold, the backlog is **91's three strings**, plus a closing verdict line each for 62 and 63.
