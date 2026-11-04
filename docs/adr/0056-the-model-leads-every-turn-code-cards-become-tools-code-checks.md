# The model leads every turn; code gives the structure and checks, never the content

> **Superseded in part by ADR-0061** (accepted 2026-10-29): the old code path as the model's fallback no longer holds; no prepared answers, one path at the end.

Status: **accepted: the owner's decisions**, from a grill-with-docs in 1_nemo_rework's window (session 88e66808, 2026-10-19,
six AskUserQuestion rounds, 15:44–15:57Z) and his typed line 2026-10-19T15:48:15Z (below). Drafted PROPOSED by 25_nemo_plan
the same day from his answers in 43_nemo_check's 141bc1f8 (15:34:28Z, *"Yes, that's it (Recommended)"* to the problem
statement and *"Full rework now"* to the scope). **Supersedes** ADR-0053 decision 1 (fallback only, code-first routing) and
answer 2's go/no-go (row 0053g), ADR-0045 decision 2 (next steps drawn by nemo alone) for chat, and the part of ADR-0006 that
has stage-card prose written by code. **Carries over:** ADR-0053's own loop with no library (decision 2), templates with a
fixed look and swappable data (decision 3), the claim check (loop step 6) and functions, not names (ADR-0051); ADR-0043 and
ADR-0049 (nothing is ever sent; one calendar event); ADR-0052 (several copies, each room on one); ADR-0055 (the cheapest
route, measured).

Source: `~/work/nemo-builds/rework-2026-10-19/problem.md` (his walk 19 Oct 17:03–17:22 on c7daf1d6), `code-review.md`,
`package-map.md`, `fact-map.md`, `fact-checks-per-kind.md` in the same folder. Spec: `docs/issues/nemo-walk/spec-rework-model-leads.md`.

His typed line (15:48:15Z): *"I want to reduce the method of having a prompt and then the LLM answering via saved code. The
code should only inform the structure of the answers like a template, not generate answers out of the code. Because if I do
that, then if I swap markdown files or ask a little bit differently, the answer will never be correct. So, the model should
always lead, and the code should only inform the model how to structure it."*

## Context

On his walk nemo answered by keywords: "same graph but without the image" drew the same 5-class chart twice; "write an e-mail to
the people responsible" gave three fixed gap drafts, twice; "does this process have SPOF?" gave the dependency register twice and
never a yes or no; "do it on November 20" got "Done — the invitation now says Friday, 20 November" when no tool had run. The code
review found that on most card turns the model had already written a fitting answer, and `_finish` threw it away for the card.
Every card answer comes from one 340-line cascade of keyword tests, and its readers are tied to today's file layout, so a swapped
file or a reworded question breaks it.

ADR-0053 rejected "agent first, code as backup" as slower and riskier, and the measures so far point that way (the 18 workshop
prompts: nemo 16/2/0, Claude Code + GLM 14/4, ZCode + GLM 12/6; the agent loop 4 of 15). He was shown those figures (round 1,
Q1) and chose the model to lead anyway, on the condition below that each move keeps today's floor on the 18 (Q21). What the
harnesses missed were method facts nobody handed them; here code hands the model the file map and the method's rules each turn
and checks every figure afterwards, which the harness arms did not have.

## Decision (his answers; Q numbers are the grill's)

1. **The model leads every turn** (Q1), **chat and the words of the walk's stage cards** (Q3, Q5). It decides what to answer and
   how, and composes and changes the result: answers, charts (through the chart template), e-mails, invitations, yes/no
   judgements, next steps. A follow-up changes what nemo showed last; it is not matched again as a new question.
2. **Code gives the structure, never the content** (his typed line; Q9). Code hands the model, each turn: a **file map** of the
   room (one line per file: what it holds), the method's rules, the story's today, what was **last shown** in the room, the
   **template** for the answer's kind, a **must-cover list** where the kind has one, and **the focus activity's raw rows**
   (its interview lines, record figures and register rows, numbered by file and line: facts, never sentences; Q25). Today's code cards stop being answers;
   their structure survives as templates, and their file readers survive as the checker's evidence.
3. **The model reads the files itself** (Q10), through the file map, **a capped piece at a time**, every line numbered, by line
   range, with a line saying where it was cut and how to read on (Q17; Anthropic's text-editor tool reads the same way). Each
   template is a tool whose arguments are its slots (GLM takes `tool_choice` auto only).
4. **Stage cards** (Q5): the model writes the card's sentences. The figures, the decision rule, the four-way gradient and the
   record he signs stay code's (ADR-0006's rule that a model cannot decide on his behalf stands). Every figure in the card's
   sentences is checked against the record.
5. **Code checks every turn before anything shows:** each fact sentence ends with its `[file:line]` cite; every figure, date,
   count, name and recipient must be on a cited line the model read this turn, or it is dropped (the claim check, widened, as
   Instructor's exact-substring validator; one send-back, then drop, as Pydantic AI's default retry of 1). The column check covers
   only the pairs the seed seat names (RTO / RPO / MTPD / `consumer_mtpd`; Status cell / Last interview / Review due). A chart,
   letter or invitation call is checked against the room's data and last shown, **never against his words** (that would be the
   keyword layer again); an absence is said as "not named" /
   "not stated" unless a file states it; **a sentence saying something was done stands only if a tool did it this turn** (530's
   rule, on every turn); a next step stands only if a tool of this room can do it. An item of the must-cover list still missing
   after the send-back is **not** added by code: the answer shows as written and the miss is recorded and scored (Q26). **No
   model judges the model** (Q18).
5a. **Ask, don't guess:** where a name fits two things (493), or a recipient or a date is missing, the model asks one short
   question with taps instead of choosing.
6. **Judgements** (Q18): the model answers yes or no first, then each reason with the line it stands on, then what the files do
   not state.
7. **The model only proposes** (Q4): drafts into Drafts, the calendar event, decisions, signing, accepting and reopening need his
   tap. Nothing is ever sent (ADR-0043). Functions, not names, unless his line asks (ADR-0051).
8. **E-mails** (Q14): the model picks the recipients **by function** from the room's people and writes subject and body inside
   the fixed letter frame (476). Code maps each function to an address from config; the seed holds no address, and the model
   never types one. A follow-up edits the last draft shown; once a draft is in Drafts, a change adds a new draft and the old one
   stays.
9. **Invitations** (Q15): a follow-up that moves the date rewrites the invitation in chat; on his tap nemo **moves its one
   calendar event** (ADR-0049) and puts a new draft in Drafts; the old draft stays (archive, never delete), and nemo says so.
   Code checks the date is real, its weekday, and not before the story's today.
10. **Artefact memory per room** (Q16): the last chart (activities, classes, years), the last drafts and the last invitation are
    kept in the room's own folder, so they survive a reconnect, a reopened room (511) and a restart. A follow-up edits the last
    one of its kind; an older one is reached by its tap.
11. **Next steps** (Q12): the model proposes up to five; code keeps only those a tool of this room can do now. Replaces ADR-0045
    decision 2 for chat; its count (one to five) and kinds stay.
12. **On failure** (Q11): a timeout, an error, a broken tool call, or every sentence dropped gives one plain line ("I couldn't
    answer that from your files…") with 2–3 taps. Never empty, never unchecked text, and **not today's card**.
    *Note (2026-11-02, the planner, his word typed 21:57:22 CET, read raw by 49_nemo_check, ticket 743):* the plain line's words are now "I couldn't give you a reliable answer to that. Try asking it another way."
13. **Time** (Q7): a turn clock of **20 s for questions** and **up to 30 s for e-mails, invitations and chart edits**, with
    "Checking your files…" shown while it works. The 50-phone p95 is measured on the new path before the demo (ADR-0052).
14. **The brake** (Q6, Q2): the model-led path is **ON for the demo**. One switch, read every turn, puts every phone back on
    today's path (the M19/M20 build's cards). It is a brake, not a gate: **only he flips it**. Row 0053g's go/no-go is retired;
    the ~3 Nov rehearsal's results go to him as information.
15. **The floor per move** (Q21): a move reaches his phone only if the 18 workshop prompts stay at **16 good / 2 partly or
    better** in the seed seat's content read and **his 5 walk rows of 19 Oct pass**.
16. **Scoring** (Q13): every run is scored on **facts, shape, action claims and taps**; wording may vary. The prompt check scores
    those, not which card answered. His walk rows become **two-turn follow-up cases**. The move check runs each case **3
    times**. Held-back cases stay unseen by builders, as now.
17. **Model and key** (Q8, Q19): **GLM 5.3 Flash** on ADR-0055's cheapest route; the first model-led measure checks its speed,
    and if 50 phones go over the limit the route goes back to the fastest, with his OK. No GPT model through litellm, ever. He
    raises the key's monthly limit for October–November (his money, his step); nemo limits the model calls each copy has open at
    once, so a burst waits in line instead of failing with a 402.
18. **Where and how** (Q24, Q22, Q23, Q20): the code lives in the **skin** (ADR-0053 decision 2; the MCP door stays after the
    demo). A half-day **probe** of GLM leading turns with the file map, capped reads and templates on the 18 and his 5 rows comes
    first; if it scores below today it goes back to him before the model-led slices start. Slices with no model in them start at
    once. **Up to 4 builders**, split by file. **Nothing slips** past the 4 Nov freeze.
19. **Tests** (confirm round): one seam, a whole turn driven by a scripted fake model; no model call in any gate.

## Research behind the choices (19 Oct, read-only, sources with URLs)

`~/work/nemo-builds/rework-2026-10-19/research-proven-patterns.md` and `research-similar-projects.md`: the loop "model answers,
code checks, the reason goes back once, the failing part is dropped, else a plain line" is Claude Code's Stop hook, Pydantic AI's
output validator and Guardrails AI's reask/filter/refrain. Approval before a write is LangGraph's, the Agents SDK's and Claude
Code's (nemo's simpler form: write tools are never offered; a tap runs plain code). A fixed chart template with parameters is
LIDA's and Data Formulator's; last shown is Data Formulator's data thread. A file map with capped reads is Anthropic's advice for a
corpus too big to hand whole at 50 phones (the seed is ~110-140k tokens). Checking figures by code is ahead of the open projects
(they cite, but do not check); the action-claim check is nemo's own. Overbuilt and dropped: chart arguments matched against his
words; a general column engine; code appending missing items.

## Consequences

- Two model loops and two check stacks (free chat's `_model_calls` + `_finish`; the agent fallback's loop + checks) end as one
  turn path with one check stack. The keyword cascade survives only behind the brake.
- Many skin tests pin today's routing (`code_said`, `server`, the matchers). They go red by design; each is read, then retired to
  the brake's suite or rewritten, never silently dropped.
- The chat turn's record changes shape (SHARED): the tools called with their arguments, the artefacts shown, what the checks
  dropped and why, the clock. The check seat and 13_Langfuse are told before the first commit. `walk.Card` keeps its shape: the
  model writes the card's sentences into it, the fields stay.
- The prompt check's route check, `chart_of` and the move baseline change, so `checker_sha` moves and every move re-records its
  baseline on the new checker.
- On-screen wording and the look at 390/1440 (the plain line, "Checking your files…", draft and invitation cards) are pending
  15_nemo_design's look; content truth (expected answers, fact checks) is 20_marschkamp's.
- The agent-fallback chain (494, 495, 496 + 500, 497, 521, 522, 523, 525) is absorbed, re-scoped or kept held, per the spec.

## Considered and rejected

- **Code first, the model only for edits** (Q1 option 2): a first question would still get a fixed card, and a swapped file breaks it.
- **Today's card as the failure answer** (Q11 option 2): keeps the code-written answers alive; his line rules it out.
- **Code readers as the model's tools** (Q10 option 2): exact today, but each breaks when a file's layout changes.
- **A code rule for SPOF** (Q18 option 2): code generating the answer.
- **Earning the switch by ~3 Nov** (Q2 option 1): he wants it ON for the demo; the brake and the per-move floor carry the risk.
- **A model judge deciding "done"** (ADR-0053, ADR-0054): code checks.

## Amendments

- **2026-10-20 (26_nemo_plan, on his ANSWERS 2026-10-19T22:42:20Z in 44_nemo_check's 76fae7c3 (verified by 26_nemo_plan); the open rows O1-O3 of 43_nemo_check's review-2026-10-20):**
  - **Decision 15 binds model-led moves only** (*"Model-led moves only (Recommended)"*): the floor (the 18 at ≥ 16/2/0 and his 5
    walk rows right) applies to a move that carries the model-led path. A move on the brake's path only (bug fixes on today's
    cards: 543, 544, 520, 524, 526, 527) keeps the usual move check (the 458-subset guard) and may cut at night.
  - **The first model-led move lands with the brake set** (*"Brake set; I flip it (Recommended)"*): the move carrying the
    model-led path arrives with the brake set (today's behaviour), the floor is read on the live build, and he flips the brake
    himself. Decision 14 stands: only he flips it.
  - **If the re-probe fails** (*"Fix + retry until 1 Nov (Recommended)"*): fix and re-probe (545) until it passes. If it has not
    passed by **1 Nov**, the 10 Nov demo runs on today's path (M20 + fixes) with the brake set, and the rework continues after
    the demo. **Superseded 2026-10-29 (ADR-0061; his "After the demo", tick 21:14:16): the cut-off is now 609 passed by the 3 Nov rehearsal; if not, the demo runs on switch OFF.**
- **2026-10-20 (27_nemo_plan, on his ANSWER 2026-10-20T13:35:09Z in 45_nemo_check's 69833ce3 (verified in the transcript); closes review-2026-10-20b row 15):** **if 545 passes late, the demo's minimum model-led set is 546 + 536 + 537** (*"546 + 536 + 537 (Recommended)"*): the turn, the full model-led build and the clock/key guard. **538-541 drop first**, in the chain's reverse order. **542's own 50-phone test is replaced by today's 529 figures** (p50 11.0 s, p95 29.7 s, max 36.0 s, measured on today's path; ADR-0055's amendment of the same day). The freeze on 4 Nov and the 1 Nov deadline for 545 stand.
- **2026-10-27 (28_nemo_plan, on his "Both merges", AskUserQuestion in 49_nemo_check, logged on the tick log ~09:5x, verified by 49_nemo_check; row O7 of review-2026-10-27):** slices S7 (539) and S8 (540) are one build: ticket 539 absorbs 540, and the chain reads 536 → 537 → 538 → 539+540 → 541 → 542. The drop order under a late 545 is unchanged in spirit: 538-541 drop first. (The 545 hold on the chain was lifted by his 2026-10-27T01:10:54Z answer: the chain is built now, each slice landing with the brake set.)
