# A minted room ships a BIA in progress, on purpose

A fresh room is not empty. It carries the company's own files — the process register, the method,
the transcripts — and a run already at Stage 1 with nothing decided. That is the product, not a
seeding accident, and this ADR records it because `docs/what-good-looks-like.md` §G4(c) currently
says the opposite and an auditor reading it would fail the product for doing what it was designed
to do.

The owner's call, 2026-09-12. It was recorded inside tickets 02 and 10 and in no ADR, which is the
gap this closes. The number was left free deliberately: ticket 05's sweep ADR was renumbered to
0012 to make room for it.

## What G4(c) says, and what replaces it

G4 was written against v1, where **every minted room carried an `output/bia-record.json` that
passed the referee out of the box** — a finished BIA, referee-clean, in a room nobody had worked
in. That is what made G1 reachable: a run could be closed over a record no human had seen. G4(c)
was the right defence against it, and it reads:

> (c) A newly claimed room contains no terminal-eligible record or stage package; any worked
> example lives read-only outside active output.

**The half that stands:** no *terminal-eligible* record. A fresh room must hold nothing a signature
could close over. That is the whole of what G4(c) was defending and it is not weakened here.

**The half that is replaced:** "contains no … record" read as "contains nothing". A room that holds
nothing has to ask the manager what his company does, and the walk's entire premise is that it
already knows — ADR-0003 makes the link the credential precisely so that nothing is asked at the
door, and the release bar is ≤ 3 typed inputs. A room that starts empty cannot meet that bar,
because the first thing it would have to do is interrogate.

So G4(c) is amended to read: **a newly claimed room contains a run at Stage 1 with no decision
recorded, over source files it did not write.** Terminal-eligibility is the test, not emptiness.

## What a minted room holds, and what it must not

Holds, and is expected to:

- the company's source files — the process register, `02_BCM-Method/method.json`, the transcripts
  under `07_Interviews/`;
- a run whose stage is 1 and whose `decisions` list is empty;
- a worked example, read-only, outside active output.

Must not hold, and this is the part G4 was right about:

- any record a signature could close over — no referee-clean `bia-record.json`, no stage package;
- any document a human is meant to read as output. Stage 1 writes none; the first document is a
  projection of the record, rendered at Stage 4.

The evidence that the mint path already behaves this way: the two rooms created since the freeze,
`recovery-acceptance-1` and `recovery-canary-1`, carry real transcripts under `07_Interviews/`, a
`reference/worked-example/` folder, and **no `output/` directory at all**.

## A Stage 1 card does not draw the gradient

Ratified with the above, because it is the same question asked at the card layer: if a fresh room
arrives already at Stage 1 with nothing decided, what is Stage 1 actually asking?

It is asking the manager to confirm the scope the room read off his own files. There is no figure
yet, and so nothing to hold a reservation about. The four-way gradient — *endorsed*, *endorsed with
reservations*, *needs discussion*, *blocked* — answers **a judgement on a figure**, and offering it
where no figure exists teaches the manager within one tap that it is decoration. That is a worse
outcome than one control, because it is the gradient that has to carry Stages 2 through 5.

So: Stage 1's card offers one control. `docs/voice.md` §2 stands unchanged for every card that
proposes a figure — four controls, never three, never a fifth "not sure". The gradient labels still
ride in the record underneath Stage 1 as the answer that was given, so nothing downstream has to
special-case the shape of a Stage 1 decision.

**This makes the release bar five cards answered, of which one is a press and four are gradients.**
The bar's wording follows from that and is fixed in the same round: *5 stage cards answered*, not
"5 stage approvals" — `CONTEXT.md` lists *approval* under **Avoid** for **gradient** and
`docs/voice.md` §4.3 bans it, and "cards answered" is the only phrasing that stays true whether a
card is answered by one press or by four labels.

## What this obliges

- `docs/what-good-looks-like.md` §G4(c) is rewritten to the sentence above, citing this ADR.
- The mint path keeps its admission check — G4(a), (b) and (d) are untouched. Nothing here excuses
  a seed that fails the product's own contract; that is a separate defect and still open.
- Ticket 12 carries the Stage 1 card ruling into code, and must not "fix" Stage 1 to match Stage 2.

## Status

**Accepted — ratified by the owner 2026-09-15.** Drafted 2026-09-12 from his call of the same day. The reasoning
is his; the wording is not, and the wording is what an auditor will read. Ratify or correct it
before ticket 19 measures the bar, because §G4(c) and the bar's own phrasing are both quoted in
what 19 reports.
