# A chat answer offers up to five next steps that nemo draws

Status: **the owner's words** (8_Langfuse's session f7a15947, a grill with 14 questions, 2026-10-02 09:30–09:39Z,
verified by the planner), recorded 2026-10-02 by 12_nemo_plan. Built by tickets 276 and 277. **Replaces ADR-0023
decision 6's third point ("taps appear only when one of his decisions is open") for chat answers only.** The walk keeps
it. Supersedes the one-tap rule of tickets 108, 252, 256 and 267 for chat.

## Context

Round 3 of 112 (his marks, tallied on 24_nemo_check's go): on 28 practice answers, "useful next step" was **no on 27**,
and the main problem was "no or wrong next step" on 21. Every answer had exactly **one** tap, and 16 of the 28 were the
same "Open access-management?". On 3 walked conversations, which drew 2–9 decision taps a turn, it was yes on 2.
The answers themselves were fine (21 of 28 "good").

His words (TYPED 2026-10-02T09:16:55Z): *"the suggested next steps are only one suggestion, and there should be a
couple of different logical steps, always thinking, 'How can I help the BCM manager to answer his question, to move his
task forward?' And this is the number one thing which is not working."* Then (09:29:12Z): *"it can even be up to 5
buttons (if the text is just a few words)"*. He answered the grill *"all as recommended"* three times (09:35:48Z,
09:38:20Z, 09:39:03Z) with two notes, and confirmed the package (09:39:23Z, *"confirmed, send it"*).

## Decision

1. **Under every chat answer nemo offers one to five next steps**, each a different move that helps the manager answer
   his question or move his task forward. It only offers; he decides. The walk is unchanged (Q2).
2. **nemo alone draws them, from data**: what the answer touched (an activity, a gap the answer named, a person, a
   document the room holds). The model's own suggested options stay dropped (M13, ticket 73). A next step is never a
   guess; every one is a move a tool or a page of this room can make now (Q4). Kind 1 is the one place the model takes
   part: it may call `propose_referral`, and nemo draws the tap only for a proposal `referral()` accepts (the 256/267
   path he approved: the model names a target and an item from a closed list, never writes text).
3. **Exactly four kinds, in this order** (Q7, Q11):
   1. **Close the gap**: a note to the owner, per gap the answer named (256's and 267's referral).
   2. **Go to the work**: start, or open when signed, the activity the answer touched (252's tap).
   3. **Produce something**, each only where its data exists in the room: the follow-up drafts (257), last year's
      record side by side (260's re-interview sheet), the dependency chain (262).
   4. **A standing move**, true in every room: the process map, or start a BIA.

   **At most two of one kind, five in all.** A new kind needs a ticket.
4. **A standing move appears only to reach the minimum of one**, when the answer touched nothing real. Never as
   padding (Q3, Q9): one repeated tap under every answer trains him to ignore it.
5. **Labels are person-first and as short as possible**, about four words ("Ask Barsch: deputy", "Start Picking",
   "Last year's record", "Process map"). His revision (09:38:20Z): *"Don't make it a very strict rule for the word cap.
   Make it as good as possible … If it doesn't apply, it's also not breaking anything."* So the length is a guideline:
   a long name never breaks, blocks or reds anything. Only nemo's own template words are held short (Q5, Q8, Q12).
6. **How we know** (Q10): suite checks with no model are the Done-when. His re-ask of the same 28 practice questions is
   a follow-up round reported beside the 1-in-28 baseline, with **no target number** (112 sets no threshold, and his
   judgement is never a gate).

## Considered and rejected

- **The model proposes, nemo checks** (Q4 b). It reopens the loop M13 closed after 26 failed prompt fixes, and it can
  only be tested with a model.
- **Zero taps when nothing applies** (Q3 a). That is what plover 03 got, and it did not help him.
- **Standing moves as padding toward five** (Q9 b).
- **A hard four-word cap** (his first reading of Q5, reversed by him under Q8).
- **A new term ("next moves")** (Q1 b): *next step* stays the word, for each of the taps.

## Consequences

- CONTEXT.md's *Next step* means one of up to five taps; 252's "most urgent" fallback, gone since 108, leaves it.
- Kinds 3 and 4 reach pages (the re-interview sheet, the dependency graph, the process map) that today have no tap.
  A next step may therefore open a page. Ticket 276 adds that for the process map; 277 for the rest.
- A label names a person only where the room's records name that person (an activity's process owner). A resource's
  owner written for the demo (ADR-0034 Part D) is never named on a tap, because the tap has no room for the mark. The
  referral's recipient stays "Owner of <asset>" (his answer 2026-10-02T08:13Z in 12_nemo_plan's session aae9fdf6).
- **Q6 (the turn file records the text he was shown) needs no ticket**: since 265 (019bc790) the turn-level `reply` is
  the shown text, and 8_Langfuse confirmed its export and blind items read that field (`export.py:308`, `:1045`).
  Round 3 showed "Short version:" because it was recorded at bc936ed4, before 265 landed.

## Amendment, 2026-10-02 (12_nemo_plan, ticket 282): nemo draws the gap itself, and the chain shows early

His answers (AskUserQuestion 2026-10-02T20:35:50Z in 24_nemo_check's session ee65bd7e, verified), on 278's first half
(14 answers on the new build: the gap tap never appeared, because the model never called `propose_referral`, not
even where its own answer named a missing deputy):

- *"nemo draws it (Recommended)"*. The option read: *"gaps found in the records the answer read become 'Ask <owner>:
  <gap>' taps (max 2), no AI call needed. The deputy needs a small reader of last year's record. Tests with an AI that
  never calls the tool."* **Decision 2 changes:** kind 1 is drawn **by nemo from the records the answer read**: a
  resource whose RTO is not inside an activity's MTPD, and a process owner for whom no deputy is named
  (`org-and-roles.md`'s Deputy column reads "—"). *Corrected 2026-10-03 on 24_nemo_check's review:* the question named
  last year's record as the deputy's source, but that record holds no deputy or workaround field and names every
  owner, so the org chart is the record that shows the gap; his rule, "gaps the records show", is unchanged. The owner
  is the record's own "Process owner" name in last year's record, found in the org chart by name among the rows whose
  Records cell holds the record, never by position (6_marschkamp's content read, 25_nemo_check's ruling). A tap or
  answer says "no deputy is named", never "has no deputy" (ADR-0034). The model's `propose_referral` stays, as an
  extra source under the same two-per-kind cap. A gap tap no longer depends on the model.
- *"Offer it early (Recommended)"*. The option read: *"The tap shows whenever the answer read the dependency register
  or named an asset there; it opens /w/<room>/graph like the workspace link."* **Kind 3's dependency chain** no
  longer waits for stage 4's drawn graph. *Corrected 2026-10-03:* the workspace serves only a drawn graph, so the
  chat turn that offers the tap draws the room's graph (stage 4's drawer, into the room's own folder); a GET never
  draws.

## Amendment, 2026-10-19 (ADR-0056)

His answer Q12 in 1_nemo_rework's grill (88e66808, 15:50:10Z, *"Model proposes, code checks (Recommended)"*): in chat the model
proposes up to five next steps fitting its answer, and code keeps only those a tool of this room can do now. **Decision 2
("nemo alone draws them … the model's own suggested options stay dropped") is superseded for chat.** One to five, the four kinds
and the labels' guideline stand.

## Dated note (28_nemo_plan, 2026-10-30; the decision above is not reworded)

The fallback next step, offered when an answer touches nothing real, was "Process map". On 2026-10-30 he asked for the Process map page and its link to go ("please delete the link, and the site of "Process map" its not needed on teh nemo.ai4bcm site anymore"; tick log, `status: nemo-chat-redesign — HIS ANSWERS`, 10:09:43Z) and picked **"Dependency graph"** as the fallback instead. The standing tap now opens the dependency graph, drawing it first if it is not drawn yet (49_nemo_check's ruling; 282 allows a tap that draws). The room's `01_Organisation/process-map.md` stays: it is data that core, the graph and next_step read. Built by ticket 636.

