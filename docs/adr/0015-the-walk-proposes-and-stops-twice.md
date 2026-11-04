---
status: accepted — ratified by the owner 2026-09-15 — superseded by ADR-0022 (the walk is an output, not the spine), recorded 2026-09-21 in ADR-0023
---

# The walk proposes, and stops twice

**The owner's calls of 2026-09-14, drafted by a command shift for his ratification.** **Ratified by the owner on 2026-09-15**; it may be cited as settled. It **supersedes ADR-0014** in substance
and replaces it as the decision of record for how a walk progresses. The wording is a shift's, and
the wording is what an auditor reads.

## What was asked

ADR-0014 and tickets 35–44 designed a per-activity **refresh / first assessment** policy: each
activity would carry provenance, the walk would match it against last year, the record would gain
fields and a schema bump, and a stage would decide from that whether to ask or to proceed.

The owner called that over-engineering. A `ponytail` pass replaced the whole ten-ticket slice with
one ticket, 45, and the ten were moved to `docs/issues/nemo-walk/superseded/`.

## The decision

**Stages 1, 2 and 3 are the machine proposing from what is already in the room.** They are answered
with each card's own proposal. **Stage 4 is where a human judgement first enters, and stage 5 is
where he signs.** Five stops become two.

- Stage 1: `agree_scope` over `open_bia`.
- Stage 2 reads the room, and the **folder is the branch, not a policy**. Exactly one transcript →
  bind it. None → return the card that already offers to conduct the interview. Several → return the
  card that already offers the choice. A BIA can never run unattended over evidence that does not
  exist, and where there is a choice of evidence the pick is the manager's.
- Stage 3: `answer_evidence`, which already writes the card's proposal.
- It returns the stage-4 card and writes not one byte.

**Nothing is derived.** No refresh, no first assessment, no prior cycle, no matching against last
year, no policy field, no schema change. The only branch is how many transcripts sit on disk.

**The referee is untouched.** Every quote still resolves or the record is refused.

**The safety is that the review is total.** Nothing is signed without the manager reading the whole
refereed record at stage 4 and accepting it at stage 5. That is why no per-activity policy is
needed: attention is not rationed, it is moved to the end.

**Both walks are offered, and the manager chooses at the door.** The five-stop attended walk stays
exactly as it is; the two-stop walk is a second button beside it. The fourteen existing feature
files remain the regression pin for the attended path, and ticket 45 writes no new one.

## Why this rather than ADR-0014

- **The evidence does not carry the policy.** `findings/evidence-base.md`: Aguinis (2026) is an
  editorial with no empirical test and no BCM domain authority, and its own Principle 2 cuts
  against unattended progression. BCI GPG 2018 already distinguishes a first-time BIA from later
  cycles, which is the real basis for doing less on a later cycle — and it is a statement about
  practice, not a instruction to derive a per-activity flag.
- **Explanations do not fix over-reliance and may worsen it.** A disclosure message is a
  transparency artefact, not a mitigation. Accountability for accuracy is the one intervention with
  positive evidence, which is a claim about the certificate's wording and not about a policy field.
- **A schema bump is a cost paid by every saved record, forever**, to encode a distinction the room
  already makes by what it contains.

## What is kept from ADR-0014

Its reasoning, not its decision: the three shapes in the seed, the prose-not-scores rule, and the
argument for why a second workflow was rejected. Read 0014 for those. **Do not read it as the
plan.**

## Status of ADR-0014

Superseded by this ADR, in substance, from 2026-09-14. It is not deleted: its reasoning is still
the best written account of why a second workflow was rejected.
