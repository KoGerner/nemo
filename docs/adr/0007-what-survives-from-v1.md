# Three things port from v1; the rest does not

About 2,500 lines move across — roughly 12.9% of the old system's 19,428 — and they are the parts
that are deterministic, carry their own tests, and do no gate bookkeeping:

- **The referee** (~1,090 LOC, 167 tests): grid completeness, worst case non-decreasing over time,
  MTPD derived from the grid rather than asserted, RTO strictly inside its MTPD or an acknowledged
  gap, RPO from the method vocabulary, every quote verbatim in a readable file, the handover boundary.
  This is the product's actual claim.
- **The dependency-graph core** (~568 LOC, 120 tests): pure dict-in, HTML-out.
- **The path jail and the etag-conditional write** (~450 LOC): the two safety properties that never
  caused a stall.

Recorded because a future reader will try to rescue more of it: `bia_service.py` (3,092 LOC with
**130 refusal sites**), the 2,212 LOC of write-lane jaws, the save-token slot, the self-writing
HMAC-tagged findings and the two ledgers of gates checking each other are **deliberately not ported**.
They are why v1 refused so much. The refusals were not the method being strict — they were the write
lane defending itself, and the lane is gone.

## Amended by ADR-0010

A fourth thing survives: the **run protocol** (`bia_run.py` + `bia_run_store.py`, ~793 LOC, 27
tests). It meets all three criteria above — deterministic, carries its own tests, does no gate
bookkeeping — and was simply missed when this was written. Its `uuid5`-over-digests run
identity and its single `in_progress` status do not port; ADR-0010 replaces both. Nothing on the
do-not-port list above changes.
