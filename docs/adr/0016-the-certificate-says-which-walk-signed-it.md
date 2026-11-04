---
status: accepted — ratified by the owner 2026-09-15 — superseded by ADR-0022 (the walk is an output, not the spine), recorded 2026-09-21 in ADR-0023
---

# The certificate says which walk signed it

**Drafted by a command shift on 2026-09-15, for the owner's ratification.** It amends **ADR-0015**
and does not supersede it: the two-stop walk, the folder-is-the-branch rule and the total review at
stage 4 all stand exactly as ratified. A shift drafts an ADR and never ratifies one; the owner
**ratified this on 2026-09-15**, choosing both sentences over the certificate line alone. It may be
cited as settled, and ticket 45's Done-when now carries it.

## What was asked

ADR-0014, which 0015 superseded, was titled *"a stage asks or proceeds and **the record says
which**"*. 0015 threw away the mechanism that would have recorded it — the per-activity policy
field, the schema bump, the derivation from last year's cycle — and was right to: the evidence did
not carry that policy, and a schema bump is a cost every saved record pays forever.

But the property went out with the mechanism. Ticket 45's first Done-when box requires the
unattended record to be **byte-identical** to the same walk answered by hand with `ENDORSED` at each
stage. Read together with 0015, that means: once 45 lands, **nothing on disk distinguishes a BIA
whose scope a manager endorsed and whose evidence he chose from one where the machine did both.**

## Why that is worth one sentence

- **The endorsement is the artefact.** ISO/TS 22317 §5.7.4 makes documented endorsement the terminal
  gate of a BIA, and GPG's Consolidated Analysis says the same. A signature that cannot say what it
  is a signature *over* is weaker than the walk that produced it.
- **It is the one place this project's own evidence applies.** `findings/evidence-base.md` concluded
  that explanations do not fix over-reliance and may worsen it, and that **accountability for
  accuracy is the single intervention with positive evidence — a claim about the certificate's
  wording.** This is that claim, at that wording, and nowhere else.
- **The walk already does this for identity.** The certificate reads *identity confirmed by email*
  or *identity asserted in session, not verified*, in those words (ADR-0003). Saying which walk was
  taken is the same move, made once more.

## The decision

**One flag in the run state. Two sentences. No schema bump, and the record is untouched.**

1. The run state — `output/.bia-runs/`, which is not the record and which no saved BIA carries —
   records that stages 1, 2 and 3 were answered from the room's contents rather than by a human.
2. **The certificate names it.** `_certified()` already calls `handover.certificate(record, saved)`
   and `saved` is the run, so the certificate can read it without the record changing by one byte.
   Wording, to be exact where ADR-0003's identity line is exact: *scope, evidence and standardisation
   were proposed from the room's contents and endorsed by the signer at stage 4.*
3. **The stage-4 card says it before he answers, not after.** On an unattended walk the card names
   what it is ratifying — three stages, not one. This is the meta-decision stated rather than
   sensed: on the two-stop walk the gradient exists only at stages 4 and 5, so *endorsed with
   reservations* is unreachable at scope and at evidence, and a manager must be told that the
   endorsement he is about to give covers all three.

**Ticket 45's byte-identity box survives, reworded to say what it always meant:** the **record** is
byte-identical. The certificate is not the record, and the run state never was.

## The two sentences, literally

Ratifying this ADR is approving these strings, not a concept. They are written here so the decision
is a reading rather than an argument, and so a walk cannot paraphrase them into something softer.

**On the certificate**, beside ADR-0003's identity line, and only on a walk that was not answered by
hand:

> Stages 1 to 3 were proposed from the room's own contents — the register, the transcript and the
> method — and were not answered separately. The signer endorsed them with the refereed record at
> stage 4.

**On the stage-4 card**, before he answers rather than after, and only on that same walk:

> Scope, the evidence this rests on, and how it was standardised were taken from what is already in
> this room. You have not been asked about them separately. Endorsing this record endorses all three.

The attended walk shows neither sentence, and its certificate is unchanged.

## What this is not

- Not a policy field, not a derivation, not a refresh-versus-first-assessment distinction, and not a
  schema change. Everything ADR-0015 rejected stays rejected.
- Not a disclosure message. The evidence says an explanation does not mitigate over-reliance; this
  is an audit trail on a signed document, which is a different claim with different evidence.
- Not a reason to make the two walks produce different records. They must not.

## Consequences

- One field in the run state; two strings; one test each. Ticket 45 carries it, since it is the
  ticket that creates the condition.
- An auditor reading a signed BIA can tell which walk produced it. Today, after 45, they could not.
- **The stage-4 sentence is visible on 10 November.** It is a product change and not only an audit
  artefact: a manager on the two-stop walk is told, before he answers, that endorsing the record
  endorses scope and evidence with it. That is the design becoming legible rather than a disclaimer.
- The rejected alternative is recorded because it was weighed: ratifying the certificate line
  **alone** was available and was refused, and rightly — it would have had the certificate assert
  *"the signer endorsed them at stage 4"* while the card never told him he was. A claim the product
  does not back is the exact failure this rebuild exists to prevent.
