# The nemo walk, stage by stage

**Status: the four [open] calls are answered; the walk itself still awaits the owner's gradient on
question 1 below.** The five-stage walk was agreed with the owner on 2026-09-12 and never written
down, so it existed nowhere. This is the reconstruction, from `docs/research/method-map.md` §1 Lane B
— the shape the walk takes — and the seven ADRs. Where the reconstruction had to choose, the choice
was flagged **[open]**; all four were settled on 2026-09-12 and the answers are inline, each with the
reason, so **no [open] marker should remain in this file**. Tickets 12 onward are sliced against it.

The words are `CONTEXT.md`'s: room, stage, stage card, gradient, record, referee, finding, dependency
graph, handover.

## What a stage is

A stage puts one **stage card** in front of the human. The card carries the server's proposal, the
reason before the figure, its decision rule, and the four-way **gradient** to answer it with —
endorsed, endorsed with reservations, needs discussion, blocked. The human answers; the server writes.
A model never decides on the human's behalf, and a stage never writes anything the card did not show.

There are five stages and only five. The missing-owner loop is not a sixth: in this shape a dependency
with no owner is a **finding**, carried to the signature as an open item the signer accepts by id.

Every card is prose in a competent BCM manager's voice (ADR-0006), generated from the record's figures
rather than written beside them. The decision, the rule and the gradient sit underneath unchanged.

---

## Stage 1 · Identification of scope

**The card shows** the process as one activity, with the register's other activities offered beside it
rather than imposed; the method parameters copied from the room's `02_BCM-Method/method.json`
(categories, horizons, the 1–5 scale, the intolerability threshold, the RPO vocabulary); and the
`Source:` line naming every file the proposal was read from.

**The human does** one thing: answer the gradient. Adding a register activity to the scope is the
amendment path, not the clean run.

**Typed inputs: 0.** One tap.

**To disk:** nothing the human will read. The run's state — scope, method, revision — in
`output/.bia-runs/`, compare-and-set on `revision`. Stage 1's document is rendered later, at Stage 4,
from the saved record.

**The boundary, and it is deliberate — the owner, 2026-09-15.** This walk analyses **one activity**.
It does not run the products-and-services pass that ISO/TS 22317 §5.1 and GPG PP3 sequence ahead of
process and activity analysis, and it does not prioritise across a portfolio. **The register supplies
that ordering**, having been decided before the room was minted. So the honest answer to *"how did
you decide this activity matters most?"* is *"the register said so"* — never *"the BIA showed it"*,
which would be a claim this walk cannot support. Adding the pass is a second workshop, not a ticket;
it is out of scope for 10 November and is written here so nobody discovers it on stage.

## Stage 2 · Structured interview

**The card shows** the transcripts already in the room (`07_Interviews/`,
`output/owner-interviews/`), each with an exact preview so a yes is a yes to bytes somebody has seen.
Where there is no transcript, the card offers to conduct the interview in the room instead, and any
new testimony is shown as a preview with its sha before it is saved.

**The human does** pick the transcript this BIA rests on, and answer the gradient. On the clean run
the transcript is already in the room — an interview conducted live is a longer path, not a more
expensive gate: its preview confirmation folds into the same Stage 2 decision.

**Typed inputs: 0.** One tap: the transcript is chosen from the list.

**To disk:** the binding and the transcript sha in the run state. A live interview also writes the
verbatim Q&A to `output/owner-interviews/<process>-interview-transcript.md` — the evidence the referee
will later hunt quotes in, and the reason ADR-0002 says transcripts are the evidence rather than a
side effect.

## Stage 3 · Standardise the interview evidence

**The card shows** the server's own draft of the standardised evidence, read out of the approved
transcript: an RTO asserted only where a label and a value co-occur; MTPD, RPO and MBCO marked
owner-stated with the quote beside them; register dependencies resolved to their exact asset ids, with
an unmodelled one raised as a finding rather than given an invented id. The worst case is proposed
honestly as all-unknown where the interview did not reach it, with the not-elicited acknowledgement
pre-filled from the transcript header. The card leads with whatever the evidence forces a decision
about.

**The human does** answer the gradient, and nothing else.

**Typed inputs: 0. One tap** — **settled 2026-09-12: the acknowledgement folds into the gradient
answer**, and where the transcript did not reach a category the reason is recorded as *not stated*.
The walk is five taps, not six.

The reason for folding is `docs/voice.md` §1's **one decision per card**: why a category was not
elicited is not a second decision, it is a property of the transcript, and the card was asking the
manager to ratify a fact about a document he did not write. *Not stated* is the honest record of
that — it loses the reason and says so, rather than offering three options the manager picks the
least wrong of, which is a reason invented at the card.

**This changes `docs/voice.md` §1**, which named Stage 3 as the stage that really needs two answers.
It is edited in the same round; if the fold is ever reversed, §1 comes back with it.

**To disk:** the endorsed proposal in the run state. No document. Stage 3's document is a projection
of the record, rendered at Stage 4.

## Stage 4 · List the requirements

This is where the walk stops being reversible.

**The card shows** the refereed record, and the worksheet rendered from it: per activity the impact
grid across the horizons, MTPD said in words with the reason before the figure ("MTPD 8 h — the
legal/regulatory impact reaches the threshold at 8 h"), the RTO and the RPO per data set, the MBCO,
the minimum resources over time with the workaround per resource, the dependencies by their register
ids, and every scored category's exact quote beside its score with the file it came from. Findings the
**referee** would not resolve on the human's behalf are on the card as findings, not as a wall.

The **referee** has already run, and it is the product's actual claim: the grid complete for every
horizon and lens, the worst case non-decreasing over time, the MTPD **derived** from the grid rather
than accepted, the RTO parseable and strictly inside its MTPD or the gap flagged, the RPO drawn from
the method's vocabulary, every evidence quote found verbatim in a readable file in the room, and no
plan — the handover boundary.

**The human does** approve the record and its views, having seen both. One gradient answer.

**Typed inputs: 0.** One tap.

**To disk, in one movement and in this order:**

1. `output/bia-record.json` — the **record**, written through the save-token lane.
2. Four views under `output/<process>/`, rendered *from the record bytes*, never authored beside them:
   `stage1-scope-and-guide.md`, `stage2-interview-capture.md`, `stage3-dependency-analysis.md`,
   `stage4-worksheet.md`.
3. **The receipt, bound synchronously.** The run's `graph_receipt` records the saved record's
   `record_sha` and its schema version, and nothing about a page (ticket 243, ADR-0040: nemo draws
   no page of its own; the grouped graph the skin draws from the record is the only one). Until the
   receipt binds, the run's status is `record_saved_graph_pending` — saved, and not yet finished.

The graph is read-only (ADR-0004) and a cache of the record, never a source. Clicking a node to edit a
dependency is v2.1.

## Stage 5 · Consolidate and hand over

**Stage 5 cannot start without Stage 4's receipt**, and the binding is on `record_sha` — the
deterministic fingerprint of the record itself, and never a fingerprint of a page, which is
presentation and moves when anything re-renders it (ADR-0040).

**The card shows** the management BIA and the requirements handover, both rendered from the record
bytes: the continuity requirements per prioritised activity, the risk-assessment referrals, the
missing evidence, the reservations and contradictions carried from every earlier gradient answer, the
sanity-check findings, and the decision boundary. It is labelled a requirements handover for
solution-design discussion, and not approved. The method never drafts a continuity plan
and stops here.

**The human does** accept the handover — one gradient answer, moving the run to
`reviewed_pending_owner` — and then signs: name, role, and the ids of the open items they accept.

**Typed inputs: the signature.** Identity is demanded at exactly one moment, and this is it
(ADR-0003). Where an email was given at the door the certificate reads *identity confirmed by email*;
where none was, it reads *identity asserted in session, not verified*, in those words.

**To disk:** `output/<process>/bia-draft.md` and `output/<process>/requirements-handover.md` from the record
bytes, then the run closes and the certificate is written to
`output/<process>/owner-signoff-certificate.md`.

---

## The budget

**Five answers, one signature, at most seven typed replies on a clean run.**

| Stage | Typed |
|---|---|
| 1 Scope | 1 |
| 2 Interview | 1 |
| 3 Standardise | 1 |
| 4 Requirements | 1 |
| 5 Handover | 1 |
| Signature | name, role |

A typed reply is one message the human composes. **Restated by the owner on 2026-09-13**, when he
ruled that a card is answered in the manager's own words rather than by pressing one of four
labels: the taps column went to zero and the typed column carries the walk, so the honest figure
is seven rather than three. Nothing is held in reserve now; a correction still does not count
against the budget.

**Settled 2026-09-12: "typed inputs: 0" means nothing the human is *required* to type, not an
empty screen.** The composer stays on screen at every stage, and
a stage costs zero typed inputs when the card can be answered with a tap alone.

One screen, then, not two: the walk and the ask lane share it. Ticket 12 appeared to forbid the
composer its own walk assumes — the sentence it ships when a room holds no transcript is *"Ask me
anything about the method in the meantime and I'll answer from the guidance, and nothing about your
BIA has moved"*, which only means anything if a manager can type while a card is up. The
contradiction was in the wording of the box, not in the product, so the wording moved. A manager who
taps through five cards still spends no characters and the bar in this table is unchanged; a manager
who wants to ask what an RTO is does not have to leave the walk to do it, and the answer arrives
without moving his BIA. That last clause is the load-bearing half: the ask lane reads, the walk
writes, and typing into the composer never advances a stage.

The tests that assert a walk screen has no text box are true to the old wording and false to this
one. They go from strict xfail to deleted or re-aimed at what the rule actually is — that no stage
*demands* characters — in whichever of 13 or 14 first touches them.

**Settled 2026-09-12: the third slot is one free-text amendment, and the bar stays three.** Not an
email address at the door: ADR-0003 allows one and never requires one, and if the bar spent a slot on
it the bar would be measuring the door instead of the walk. Not nothing either — a clean run is a run
the server proposed right, not a run the human had nothing to add to, and an amendment is the one
thing such a run may legitimately need to say in its own words. It is a slot, not an obligation: a
run that uses none is a cleaner run, not a different one.

The table above summed to six taps while the sentence above it said five, because Stage 3 was carrying
two. The fold makes them agree at five; that arithmetic was the other reason to settle it.

**Corrections are excluded, deliberately.** *Endorsed with reservations*, *needs discussion* and
*blocked* all cost typed characters — a reservation that is not named is not a reservation. That is
the method working, not the budget breaking. The budget measures the path where the server proposed
right the first time, which is the only path a number like this can measure. A run that argues with
three cards is a better BIA and a longer one, and both facts should be reported.

This replaces the `<=15 presses` bar still standing in `docs/what-good-looks-like.md` §3, which the
owner superseded on 2026-09-12. Fixing that file is a separate open job.

**For scale:** Lane A, the YAML journey, costs **12 distinct human confirmations** for one activity
with no missing-owner loop, and one measured walk took 140 turns without reaching Stage 5.

## The binding that fixes v1's worst symptom

Stage 4 writes the record and regenerates the graph with a receipt. Stage 5 cannot proceed without
that receipt. Those two sentences are one rule, and it exists because of a specific failure.

On 2026-08-31, in room `adler-stjmed`, a run declared itself closed while the graph URL showed nothing
new. The record had never gone through the token lane, so no regeneration ever fired, and nothing in
the walk noticed: closure was bookkeeping about gates rather than a statement about artefacts on disk.
The owner saw a finished BIA and an empty graph.

Binding Stage 5 to the receipt makes that state unreachable. A run cannot say it is finished unless
the record is saved *and* the receipt carrying that record's fingerprint is bound to the run.

The second half of the rule is which fingerprint. On 2026-09-02, in room `adler-yj3477`, the gate was
written against the exact page and a benign operator re-render changed `page_sha` — the run could
never reach Stage 5 again. The gate binds on `record_sha`. A deadlock is the same failure wearing the
opposite sign: both are the walk reasoning about itself instead of about the evidence.

## What of this is already built, and what is not

Checked against the live v1 repository at `d6efaf6` (2026-09-10) — it moves, so it was read rather
than remembered.

**Built and running.** The whole Lane B spine is live in `bia-workflow-mcp.service`:
`open_bia` → `prepare_bia_stage` → `confirm_bia_stage` ×5 → `sign_bia`, four of the twelve registered
tools. The four-way gradient is real and its "yes, with reservations" is explicitly never collapsed
into "yes". The server drafts Stage 3 from the transcript. The referee runs before any save, with its
own 167 tests. The record is written by token, the four views are rendered from the record bytes, the
graph is regenerated synchronously with a receipt, and Stage 5 and `sign_bia` both refuse without one,
bound on `record_sha`. Run state is compare-and-set in `output/.bia-runs/`. The signature writes a
certificate that says identity was asserted in session. Six human decisions, by its own test.

So the *skeleton* of this walk is not a rebuild. It exists. What the rebuild is for is everything the
skeleton is wearing.

**Not built.**

- **The colleague's voice.** Today's cards are machine text, and Stage 2's asks the human to type
  `proposal={"transcript_path": "…"}`. ADR-0006 calls the voice the single largest improvement never
  built in v1, and it changes what all five stages emit.
- **Taps.** There is no tap in v1. Every one of the five decisions is typed into a chat box; the
  gradient is a vocabulary of accepted strings, not a control. The tap budget presumes a front end
  that renders the gradient as four things to press — the Chainlit demo skin (ADR-0001), which does
  not exist yet.
- **The typed-input budget itself**, as a measured bar. v1 counts confirmations, not keystrokes.
  Nothing measures this number today, and a bar nothing measures is an intention.
- **The banned-vagueness list.** The jargon half has four worked examples in
  `features/the-walking-skeleton.feature`. The vagueness half — "roughly", "about", "fairly critical",
  "a working day" — does not exist, and ADR-0006 is right that it is the half that breaks the product:
  unreadable is a nuisance, unverifiable is a false claim.
- ~~**Stage 3's acknowledgement as three tappable options.**~~ **Withdrawn 2026-09-12**: the
  acknowledgement folds into the gradient answer and the reason is recorded as *not stated*, so there
  is no affordance left to build. See Stage 3 above.
- **The interview guide as a method artefact.** Lane A produced one and Lane B does not; Stage 1's
  document is a projection of the record. **Settled 2026-09-12: it does not come back.** Every
  document in this walk is a projection of the record, and a guide is the one artefact that would
  have to be written *before* the record exists — so it could not be a projection of anything, and
  it would be the only thing in the walk a human reads that nothing downstream checks. If a
  facilitator wants a guide, the transcript the room already holds is the better input to it.
  **Amended 2026-10-01 for a re-BIA only** (ADR-0044, the owner's words): where last year's record
  exists, a re-interview sheet projected from it goes in "Your documents". A first BIA still gets no guide.
- **Per-activity Stage 4 cards.** Lane A gave each activity its own approve. Lane B approves the
  refereed record in one movement. The single movement is what makes the budget hold; whether it
  holds for a five-activity department is untested. **Settled 2026-09-12: Stage 4 stays one card, and
  tickets 15 and 16 measure it against a multi-activity department rather than deciding it here.**
  Untested is the honest state of this, and splitting the card now would be deciding it from nothing
  — the split costs a tap per activity and there is no evidence yet that it buys anything. If the
  measurement shows one card cannot carry five activities, that is a finding with a number attached
  and the split can be argued from it.

**Deliberately not coming back** (ADR-0007): `bia_service.py`'s 130 refusal sites, the write-lane
jaws, the save-token slot as a gate, the self-writing HMAC-tagged findings, and the two ledgers of
gates checking each other. Those refusals were the write lane defending itself, not the method being
strict, and the lane is gone.

## What this asks the owner

1. Is the walk as described the walk that was agreed? Endorsed, endorsed with reservations, needs
   discussion, or blocked — the same gradient the method uses on everyone else.
2. ~~The **[open]** calls above.~~ **All four came back on 2026-09-12** and are recorded where they
   belong rather than here: the third typed slot is one free-text amendment and the bar stays three;
   Stage 3's acknowledgement folds into the gradient, which also makes the tap table sum to the five
   the heading claims; the interview guide does not return; Stage 4 stays one card and 15/16 measure
   it. A fifth call settled in the same round is not from this list — a Stage 1 card does not draw the
   gradient, and that one has an ADR, 0011, because it amends `what-good-looks-like.md` §G4(c).
3. Confirmation that corrections stay outside the budget — that a run which argues is reported as
   longer and better, not as a failure against the bar.

Nothing is sliced into tickets until 1 comes back endorsed.
