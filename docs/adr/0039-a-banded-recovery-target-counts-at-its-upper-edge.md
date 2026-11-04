# A banded recovery target counts at its upper edge

Status: **accepted by the owner** (AskUserQuestion answer 2026-10-01T08:00:41Z in 21_nemo_check's session 63c012d0,
*"Upper edge (Recommended)"*). Drafted 2026-10-01 by the planner (9_nemo_plan) on 21_nemo_check's relay; the answer
and its option text are verified in that transcript. Built by ticket 240.

## Context

A recovery target can be a band ("2–6 hours"). nemo's referee reads a band at its lower edge (`nemo.duration`), so a
"2–6 hours" target passes against an MTPD of 4 h, and the signed sentences say the target is inside. The MTPD band is
already read the other way: since t74 (his ruling, 2026-09-18) a band MTPD counts at its **upper** edge. The
referee's own refusal text suggests a band as a target format, so the case is invited, not exotic. Found by the
check session's review of main 7028c448 (C6).

He was asked which edge counts. The option he chose read: *"A band is only inside the MTPD if its worst case is. This
is stricter, and it matches how the band MTPD is already read (t74, its upper edge)."* The other was "Lower edge: as
it is today."

## Decision

**A banded recovery target is held against the MTPD at its upper edge**, its worst case. "2–6 hours" against MTPD 4 h
is refused as outside; **"2–4 hours" against 4 h is refused too** (its worst case, 4 h, is not inside a 4 h MTPD);
"3 h" passes and "4 h" is refused, as today. **One strict comparison** for a band's upper edge and a plain value
alike. The one comparison changes; how a duration is read elsewhere
does not.

## Correction

**Corrected 2026-10-01** (9_nemo_plan, on 21_nemo_check's ruling after 240's builder STOPPED,
`~/work/nemo-builds/t240-report.md`): the first draft said "2–4 hours" against 4 h passes. That was the planner's
drafting slip, not his words. The referee's pinned rule is strict (`minutes >= limit` is outside,
`referee.py:864`; `test_referee.py` refuses 8 h against 8 h), and his option said a band is inside only if its worst
case is, so a band's upper edge and a plain value take the same strict comparison.

## Consequences

- The referee refuses records it used to pass, and the signed gap sentences say "outside" where they said "inside".
  A record already signed keeps its signature; only new verdicts change.
- Both bands now read the same way: an MTPD at its upper edge (t74), a target at its upper edge (this ADR).
- The phone patches `referee._review_recovery` today (t74's MTPD edge, `skin/PROTOTYPE_core.py`); ticket 240 shows the
  phone's verdict matches nemo's, and ticket 241 moves the patch into nemo.
