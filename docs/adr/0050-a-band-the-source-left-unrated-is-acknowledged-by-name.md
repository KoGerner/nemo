# A time band the source left unrated is acknowledged by name when the record is signed

Status: **the owner's words** (ANSWER 2026-10-10T16:46:25Z in 34_nemo_check's a732e064, *"Named acknowledgement (Recommended)"*, verified by
21_nemo_plan), recorded 2026-10-10 by 21_nemo_plan for ticket 376. Narrows the referee's `BAND_UNSCORED` refusal; extends the
acknowledgement ADR-0007 keeps ("RTO strictly inside its MTPD or an acknowledged …").

## Context

The referee (`src/nemo/referee.py`, `_unscored_rejections`) refuses any time band with no scored lens while other bands are scored:
*"A skipped time band is always blocked … no acknowledgement buys silence for it."* The seed's production interviews leave **1 h as
"–" in every lens** (2024 and 2026), so a grid read by code (M13) can never be signed, and nemo tells the manager that "no answer of
yours would put it right". The existing `not_elicited_ack` (who approved, why, who asks next time) covers only a grid with no
figure at all. Three choices were put to him: (a) keep blocking until someone scores the band, (b) sign with a named acknowledgement
for that band, (c) sign with the band left blank and derive the MTPD from the scored bands.

## Decision

1. **A band the source left "–" in every lens is shown as "not rated in the source"**, never as a score and never as blank.
2. **The record can be signed only with a named acknowledgement for that band**: the same three fields as `not_elicited_ack`
   (`approved_by`, `reason`, `review_owner`), given by the manager at signing. Without it, the referee still refuses, naming the band.
3. **The MTPD and the chart are unchanged by the acknowledgement**: they read the scored bands; the unrated band stays unrated.
4. A band that is scored in some lenses and "–" in others is not affected: today's rules stand.

## Considered and rejected

- **(a) Keep blocking:** every seed and every real interview must score every band, and a manager whose source simply did not ask
  about 1 h has no way to sign. Rejected: the refusal blames the manager for the source.
- **(c) Sign blank, no acknowledgement:** silent; nobody owns the gap and nobody asks next time. Rejected: the method wants a named
  owner for anything left out.

## Consequences

The referee's rejection set gains one acknowledgement kind for an unrated band: a **SHARED** change (the record's shape); the commit
names it and 34_nemo_check and 10_Langfuse are told. Seed workaround 369 (the 2026 interview scores 1 h) can stay; a later seed may
leave 1 h unrated and still be signable.
