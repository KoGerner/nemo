# A tap adds a dependency to this room only, marked "added in chat"

Status: **the owner's words**: his *"Tap adds it to this room (Recommended)"* to *"Wow 2: when someone types 'order picking also needs the label printer', what should happen?"* (AskUserQuestion 2026-10-05T10:30:03Z in 27_nemo_check's 411564c3, verified). Recorded 2026-10-05 by 14_nemo_plan. Built by ticket 318. Adds one write path into a
room's copy of the dependency register; ADR-0032 (the live seed is changed only by a seed ticket) and ADR-0034's marks
stand.

## Context

His wow 2 for the 11 November workshop: *"you can also add certain items through the chat box to Nemo itself"*, and a new
BIA activity shown on the dependency graph (TYPED 2026-10-05T09:39:46Z in 411564c3; asked "add what?", he ticked a new
activity, a resource or dependency, a file, and the finished BIA, 09:44:05Z). A new activity (72), a file (249/284) and
the finished BIA's mark (258) exist. A resource or dependency added by chat does not: the register is read, never
written, by a turn.

Asked what should happen when someone types "order picking also needs the label printer", he chose: *"nemo proposes
'Add label printer as a dependency of order picking?'. Your tap writes one row into THIS room's data only (never the
shared seed), marked 'added in chat · date', and it shows on the graph next turn. A new write path, so an ADR
follows."* He passed over "Only via a dropped file" (no new write path).

## Decision

1. **The model proposes, his tap writes.** One model tool proposes **a resource name and an activity** and nothing else
   (no figure, no owner, no description). The skin draws one tap: "Add <resource> as a dependency of <activity>?".
   The proposal alone writes nothing.
2. **Code writes one row, in this room only.** On his tap, code writes to the room's own
   `03_Dependencies/dependency-register.json`: a consumer row linking the activity to the resource; if the register has
   no resource of that name, a new asset row with that name. Never the live seed, never another room (the path is the
   room's folder; a test pins both).
3. **Marked, with no figure.** The written rows carry `added_in_chat` (the ISO date) and show **"added in chat · <date>"**
   wherever they show (graph card, focus strip, the chat's reading of the register). They hold **no RTO, MTPD, RPO or
   owner**: an added resource shows "owner not yet named" and "Recovery target · not stated" (307's rule). A figure for
   it comes only from his own later answer in a walk, never from the model (M13).
4. **Seen next turn.** The graph and every reader see the row on the next turn without a restart (284's rule).
5. **One per tap, once.** The same resource and activity again writes nothing. A name that matches an existing asset
   (case and spacing aside) links to it, never duplicates it.
6. **Undo is a file edit, not a feature.** No delete tap: the room is a demo copy, and a wrong row is gone with the room.

## Consequences

- **SHARED: the register shape** gains `added_in_chat` on a room's rows. Every register reader tolerates it; 9_Langfuse
  is told; 7_marschkamp content-reads the FINAL.
- The model gains one proposal tool (the tool list changes: SHARED).
- Seed tests are untouched: the live seed never carries `added_in_chat`.

## Considered options

- **Only via a dropped file** (no new write path): rejected by him.
- **The model writes the row**: never (M13; ADR-0023): the model proposes, his tap acts.

## Note, 2026-10-05 (14_nemo_plan, ticket 318), on his *"Let the tap pick from the map (Recommended)"* (AskUserQuestion 2026-10-05T16:26:58Z in 27_nemo_check's 411564c3, verified; option: *"after the tap, nemo may also offer 'stands on <network>' and 'at <plant>', but only things already on the map, each with its own tap. Then clicking Breitenburg darkens the standby. One extra tap on stage."*)

- **After his add tap, nemo may offer further taps that link the new row to the map:** "stands on <item>" and "at <plant>",
  **only for items already in this room's register or its Site list**, each its own tap. His tap on one makes code write the
  matching row, marked `added_in_chat`; never a figure, never a new item beyond the one he named (decision 1 still: the model
  proposes a name, nothing else). So the workshop's close works: add the CSB standby, tap "at Breitenburg", and clicking
  Breitenburg darkens it (a site tag, ADR-0034 Part E 16d / 328).
- Rows written this way are chat rows for every other rule: never a 327 finding, never a NO WORKAROUND badge (R1, R2).
- **2026-10-06 (16_nemo_plan, on 29_nemo_check's ruling after 343's first live walk):** the proposal is offered **in free chat and in a
  walk**. 318 refused it in a walk by a builder's choice; neither 318 nor this ADR restricted it, and his workshop takes it at stage 4
  (runs.md run 7, Wow 2a). Built by 360.
