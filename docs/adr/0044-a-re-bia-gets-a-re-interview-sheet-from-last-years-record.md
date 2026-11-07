# A re-BIA gets a re-interview sheet, projected from last year's record

Status: **the owner's words** (22_nemo_check's session 0a4cb4af, verified by the planner), recorded 2026-10-01 by
10_nemo_plan. Built by ticket 260. **Amends `docs/stage-model.md`'s 2026-09-12 ruling** ("the interview guide does not
come back", lines 273–278) **for a re-BIA only**.

## Context

The 2026-09-12 ruling: *"Every document in this walk is a projection of the record, and a guide is the one artefact
that would have to be written before the record exists — so it could not be a projection of anything."* In his
workshop-prep recording (08:27–20:20) he wants, for a second cycle, a questionnaire with last year's results, the
single points of failure highlighted, and "has anything changed?" under each section.

Round 2 Q6 (put 20:40:22Z): *"(a): one generated document, the same shape every time, so delegates can download it."*
Round 3 Q7 (put 20:53:55Z): *"it amends the 12 Sep ruling 'no interview guide', but only for a re-BIA (last year's
signed record exists), generated from that record. A first BIA still gets no guide. ➡️ Yes, in exactly that scope."*
He answered *"everything else as suggested please"* (20:53:12Z) and *"almost all as recommended"* (20:58:50Z).

## Decision

1. **The ruling's reason holds, so the scope is narrow.** In a re-BIA a record exists before the walk: last year's.
   The sheet is a projection of **that** record, so it is checked like every other projection.
2. **A re-BIA** is an activity whose room holds last year's record for it: the prior-cycle record the seed carries
   (`08_Prior-Cycle/`, rendered per activity in its interview and the register), or an earlier signed nemo record set
   aside under ticket 245. A first BIA has neither and gets no sheet. **The prior cycle counts although it carries no
   signature**: asked, he answered *"Prior-cycle 'final' counts (Recommended)"* (AskUserQuestion
   2026-10-01T21:26:32Z in 22_nemo_check's session 0a4cb4af, verified), whose option read *"A prior BIA in the room's
   files counts as last year's record. The sheet says 'from the Feb 2025 BIA (final, approval not recorded)', so
   nothing pretends it was signed."* The sheet never calls the prior cycle signed.
3. **What the sheet holds**, drawn by code, the model writes none of it: per section of last year's record, its
   figures as recorded (MTPD, RTO, RPO, the impact grid where recorded, the resources); the single points of
   failure highlighted, by a stated code rule (a resource the activity depends on whose record row states no
   workaround); and "Has anything changed?" under each section, with space to answer.
4. It appears in "Your documents" as a download, the same shape every time.

## Consequences

- A first BIA is unchanged: no guide, as 2026-09-12 settled.
- `docs/stage-model.md` gets a dated line under the ruling pointing here (the planner's edit, with this ADR).

## Note, 2026-10-02 (11_nemo_plan, on 23_nemo_check's re-check B1 and M3)

- **The recorded grid does not reopen ADR-0014.** ADR-0014 rules that the *comparative check* compares named figures,
  never grids, and never manufactures one. Decision 3's "the impact grid where recorded" is a **display** of a grid
  last year's record already holds: the Marschkamp prior cycle states one per process
  (`08_Prior-Cycle/25_02_26_prior-bia.md`, "the impact grid as the record states it"), and a blank cell stays blank.
  Nothing compares it and nothing fills it in. The one reader is `skin/PROTOTYPE_core.py::last_year`, extended by
  ticket 256 to return `grid` beside the named figures; the comparative check keeps reading only the figures.
- **"States no workaround" is read per row kind** (ticket 260, on 3_marschkamp's content word, accepted by
  22_nemo_check 2026-10-01 23:36). A **transcribed** consumer row is flagged when its workaround is empty or begins
  "No workaround". An **authored** row (ADR-0034 Part B) carries no workaround by construction, so its silence
  states nothing and is never flagged for it. An authored supplier is flagged only where it carries the authored
  "single source" mark, which ADR-0034 Part B point 4 allows only where no record states an alternative: the mark is
  the authored form of "no workaround".

## Note, 2026-10-05 (14_nemo_plan, ticket 330, on 7_marschkamp's finding, ruled a defect by 27_nemo_check)

- **"States no workaround" reads the stated absence, not only a prefix.** The 2026-10-02 rule flagged a transcribed row only
  when its workaround *began* "No workaround", so Production's price-labelling devices (record 1.2, BIA_2.0 l.69: *"If price
  labelling fails there is no direct workaround …"*) went unflagged although the record states the absence. A transcribed
  row is flagged when its workaround is empty or **states "no workaround" or "no direct workaround"**; a conditional
  workaround (the merchandise system's *"only possible with …"*) states a dependency, not an absence, and stays unflagged.
  Authored rows unchanged.

## Note, 2026-11-02 (28_nemo_plan, ticket 697, on the blind round's leads 3 and 5, ruled by 49_nemo_check)

- **The flagged rule stands.** It says which register rows state no workaround; the risk register's own table lists single points of failure for another reason (what stands on them). They are two readings, and the `spof` fact now carries both: `flagged` by this rule, `listed` from the table. The sheet and every count read `flagged` as before.

## Note, 2026-11-03 (ticket 735, on his seed bundle answers, 2 Nov 2026)

- **An authored row may carry a way round.** The note of 2026-10-02 says an authored row carries no workaround by construction; ADR-0034 Part B point 8 ends that where the activity's own record states one. It changes no flag: an empty cell on an authored row still states nothing. **`listed` was not built.** The note of 2026-11-02 says the `spof` fact carries both readings; it carries `flagged` only, 697 closed as written (his Q13), and the table's reading is in `CONTEXT.md`.

## Note, 2026-11-03 (ticket 733, ruled by 49_nemo_check, tick 12:35:03)

- **One exception to the note of 2026-10-02.** That note says the comparative check keeps reading only the figures and nothing compares the grid. Ticket 733 makes `skin/checks.py` read last year's grid for one purpose: to keep a sentence whose true "was none, now high" the grid shows. It never cuts on the grid. Everything else in that note stands. The docstrings of `_prior_grid` and `last_year` in `skin/PROTOTYPE_core.py` still say display only, a row in `docs/issues/after-the-demo.md`.

## Note, 2026-11-07 (ticket 768, ruled by 49_nemo_check on 56_nemo's STOP)

- **A second exception, and the one place it cuts.** The note of 2026-11-03 (ticket 733) says `skin/checks.py` never cuts on the grid. Ticket 768 adds one cut: a sentence saying every category of last year's record was none is dropped when that record's grid for the activity holds a row that is not none (`checks.EVERY_NONE`, beside `ACROSS`). It is ADR-0034's rule, nothing contradicts a record, applied to a claim about last year's grid itself; it compares no figure with the grid and fills in no cell, so ADR-0014 stands. "all three categories … none", naming categories that are none, stays. Any other cut on the grid is a new note.
