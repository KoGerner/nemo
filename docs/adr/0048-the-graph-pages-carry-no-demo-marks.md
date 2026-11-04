# The graph pages carry no "for the demo" marks

Status: **the owner's words**: asked *"What should a graph box show before you click it?"*, he answered under the
recommended option *"as recommended, but dro pthe "for teh demo", there is no for the demo dataset, that doesnt make
sense, as all marschkamp files are syntehitc anayways"* (AskUserQuestion 2026-10-06T08:51:45Z in 4_nemo_design's 81e6d5cd,
verified by 16_nemo_plan; his 08:50:18Z *"no keep all decicions to there"* puts graph design rulings in that window).
Recorded 2026-10-06 by 16_nemo_plan. Built by ticket 354. **Amends ADR-0034 for the graph pages only**: Part C's "the same
plain-words mark on the page as an authored line" (l.176) and Part D 10 ("the mark shows wherever the owner or the reason
shows", ticket 274) no longer hold on the graph, and ADR-0043's note that a derived address "keeps Part D's mark ('· for the
demo') wherever the owner shows" holds everywhere except the graph.

## Context

ADR-0034 lets the seed carry authored rows (`authored: true`, the "Written for the demo pack, not in any prior record"
text, no figure) and has the mark show on the page, so an authored line never passes for a record fact. Tickets 274, 326
and 336 drew it on the graph as a "FOR THE DEMO" badge, and a new authored box with a dashed border.

Every Marschkamp file is synthetic (the room is D5 synthetic in whole, ADR-0034's Consequences). His point: a demo badge
on a synthetic dataset separates nothing for the person looking at the graph. The box face is being cut to a name, one
"why" line and the gap badges (354) (2026-10-06: the box face carries no why line since spec §12.11, his 09:05:33Z in
81e6d5cd; spec §12.21), and the badge was the first thing his question offered to move off it.

## Decision

1. **The graph pages show no demo mark**: no "FOR THE DEMO" badge or line, and no dashed border for an authored box, on
   laptop This BIA, laptop Whole company, the phone graph, and their strips and hover tooltips.
2. **The data keeps it.** `authored: true`, `owner_evidence` and every "Written for the demo pack, not in any prior
   record" text stay in the seed as ADR-0034 writes them. The seed rules (no figure on an authored row, a basis cited,
   records never edited) are unchanged.
3. **Everywhere else keeps its mark** until he says otherwise: the chat's excerpts and citations of the register and the
   seed files (ADR-0034 Part D's choice (i): a quoted authored line must not pass for a record), chat cards, the follow-up
   drafts (ADR-0043), and the slides. His words cover the graph only; whether they reach the chat or the drafts is his to
   say, asked through the check seat (9_marschkamp's content proposal, 2026-10-06). **He answered: keep it there**:
   *"No, keep it there (Recommended)"* to *"Should the chat's quoted excerpts and the follow-up e-mail drafts also drop it?"*
   (AskUserQuestion 2026-10-06T09:24:11Z in 29_nemo_check's 40dbea40, verified by 16_nemo_plan).

## Considered

- **Keep the mark, move it to the strip and the tooltip** (the recommended option's own text): he set it aside in the
  same answer.
- **Drop the mark everywhere, data included**: his words name the graph, and the data's mark is what keeps an authored
  row from being cited as a record's own in the chat. Not taken without his word.

## Consequences

- An authored owner or reason on the graph now reads like a transcribed one. That is accepted on his word: the whole
  dataset is synthetic.
- Ticket 274's graph behaviour, and the graph marks of 326 and 336, are superseded on the graph; those tickets get a
  note, no new box. Tests that assert the badge or the dashed border on graph pages are re-aimed by 354 to assert its
  absence, and the data's mark is still tested.
- If he later drops the mark from the chat or the slides too, that is a new ADR.
