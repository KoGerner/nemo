# No prepared answers: code computes the facts, the model writes every answer to a shape, one path at the end

Status: **accepted: the owner's decisions**, approved by him ("Approve it", button in 49_nemo_check's window, 2026-10-29T16:03:03Z, on abbf76cc). Drafted PROPOSED by 28_nemo_plan on 49_nemo_check's order (2026-10-29), from his four grill rounds typed in
49_nemo_check's window (tick log, "GRILL round 1" to "round 4", 2026-10-29 16:41:03 to 16:54:30). **Supersedes** the parts of ADR-0056 that keep the old code path as the model's fallback ("model leads with the old path
as fallback"), and ADR-0053 decision 1 (fallback only, code-first routing). **Carries over:** ADR-0056's claim check and functions,
not names (ADR-0051); ADR-0043 and ADR-0049 (nothing is ever sent); ADR-0053's own loop with no library (decision 2) and the M13 box.

His words (verified in the tick log):
- "in general there shouldn't be ANY prepared answers at ALL (they only exist to show what good looks like)"
- "the code answers can be seen as templates for how a good answer should look, depending on which question is being asked … not to
  save the answer word for word … files will change, the environment will change"
- "nemo code is not quite long; everything we decide now has to override and basically delete all of the wrong and old mechanisms
  … no conflicting process workflows and question-to-answer mechanisms"
- "the foundation of nemo [must be] safe enough for these changes"
- Q2–Q5 and Q6–Q18: "the rest as suggested", "perfect, as you suggested", "yes, all as suggested".

## Context

Nemo answers a question by two mechanisms that can disagree: keyword cards and prepared answers in code (switch OFF), and the model
with tools (switch ON). On 29 Oct, on the 18 workshop prompts, switch OFF scored 14 good / 4 partly / 0 bad and the model path 10 / 3 / 5: the model
path broke on failed tool calls, a wrong tool and a missed fact, and showed raw file markers, but was better at yes/no answers and
at changing what was shown (nemo-builds/sidebyside-1029/side-by-side-report.md). The run-5 fixes (tickets 590–595) patch the seam between the two. A reworded question or a changed file breaks a prepared answer.
Two answer paths in one product is the fault; a third patch is not the cure.

## Decision

1. **No prepared answers at all.** A code answer exists only to show what a good one looks like (a worked example for a shape),
   never as text nemo says.
2. **Code computes the facts and returns them to the model as tools, never as sentences:** changes, mismatches, owners, the MTPD/RTO
   reading, due reviews, who was there last time, dependencies, and the yes/no.
3. **The model writes every answer, to a template per kind of question:** the shape of a good answer (first line, order of parts,
   what to name when something is not stated), drawn from the best answers of both switches, never stored text. The set of shapes
   is approved by him on one page: `docs/answer-shapes.md` (16 kinds and 6 rules, approved 2026-10-29T16:09:10Z). The model picks the shape; when none fits it answers freely, checked the same way.
4. **Code computes the yes/no and the model opens with it.**
   *Note (2026-11-02, the planner, 49_nemo_check's ruling at tick 13:37:00, ticket 700 landed d4b7782b):* this binds the model's first line. Where that line was cut or never came, code writes no opening: the first passing point of the model's body opens, whole, unless it is a bare label or a point right under a lone label; on code's yes it must name a row behind that yes. That is a partial answer under point 6. No such point: the plain line (603), and 2_nemo_quality_coordinator counts how often.
5. **The model leads every change to what is shown** (the change, then what it affects on screen).
6. **A failed tool call gets one retry with the error text, then a partial answer from what exists** — never "I couldn't answer".
   *Note (2026-11-02, the planner, his word typed 21:57:22 CET, read raw by 49_nemo_check, ticket 743):* where nothing passed, the plain line now reads "I couldn't give you a reliable answer to that. Try asking it another way."
7. **Steadiest model setting;** three runs per prompt measure what variation is left.
8. **Every answer carries clickable numbered references** to `/w/<room>/f/<file>`.
   *Note (2026-11-02, the planner, his word in nemo_quality_integration, Q16 of `~/work/nemo-builds/integration-rulings-1102.md`):* for the briefing only: no source links in the chat answer or the PDF, the cost (no tap to the file line from there) put to him first. Other answers keep one link per point (721); every cite stays in the turn file, and the briefing's PDF link comes back.
9. **Proof:** the 18 workshop prompts, the same 18 reworded, three runs each. The floor is "no worse than switch OFF" (14/4/0 on 29 Oct).
10. **One path at the end.** The old code (keyword cards, prepared answers, the switch, the agent fallback) is deleted in ONE ticket on
    the day the new path passes. Switch OFF stays frozen as the demo net until then; no new work lands in it.
    **Correction 2026-10-29 21:14:16 (his answer "After the demo", AskUserQuestion in 49_nemo_check's window, tick 21:14:16):** "the day the new path passes" becomes "the day after the 10 Nov demo, once 609 has passed". If 609 passes by the 3 Nov rehearsal, the new path is on stage and switch OFF stays as the demo-day brake; 610 deletes it on 11 Nov. If 609 has not passed by 3 Nov, the demo runs on switch OFF.
    **Amendment 2026-11-01 23:20 (his word, typed in 2_nemo_quality's window at 23:20 CET, tick 23:20:22; ruled by 49_nemo_check, tick 23:21:02):** "no, i want the switch to be ON, and based on teh ON nemo MUST provide good answers, because OFF is just fake". **Switch ON is the product from tonight.** The bar is ON's own answers on the 18 prompts × 3, not "no worse than OFF": this replaces the floor in point 9 (14/4/0 on 29 Oct is a history, no longer the bar). It supersedes the clause above, "if 609 has not passed by 3 Nov, the demo runs on switch OFF": the demo runs on ON. The correction above stands as dated text. 49_nemo_check flips `~/.config/nemo/agent-fallback` to `on` after the night move's OFF line and its live-verify; 2_nemo_quality measures the phone's ON answers after the flip.
11. **Every rebuild ticket leaves the answer path shorter.** Target: every ticket shrinks the code; "half" (skin/ under half of 36,394 lines) is the target of a second clean-up of the walk and tooling after the demo, with its own map (his answer Q19, tick 2026-10-29 17:06:15).
12. **A read-only foundation map comes first:** a separate session maps the answer path's foundation; 49_nemo_check checks it; he
    approves it; only then are rebuild tickets written. No rebuild ticket exists before that.

## Consequences

- Tickets 590–595 (all fixes to the seam) stop and are re-judged against the map. Only work outside the answer path lands
  (596, 537, 572, 587, 597, 598).
- A reworded question and a swapped file stay correct, because only the facts come from files and the wording comes from the model.
- The model carries more of each answer, so the proof (decision 9) and the claim check are the safety, and the retry (decision 6)
  is how a bad tool call stays visible without a dead end.
- ADR-0056's "old path as fallback" and ADR-0053's "fallback only" no longer hold; both ADRs get a one-line pointer here once approved.

## Open until the map

Settled by his answers on the map (tick log 2026-10-29 17:06:15, Q19 to Q22) and on the shapes (17:09:10):

- The answer shapes are approved: `docs/answer-shapes.md`.
- The line target: every ticket shrinks the code; "half" is the target of a second clean-up of the walk and tooling after the demo, with its own map (Q19). The map's estimate for this rebuild is about −3,800 net lines (10 %), not half.
- Walk lines join the one path, after free chat works and before the deletion ticket (Q21).
- The steadiest model setting lives in the gateway route, through the coordinator (Q22); it is not a nemo ticket.
- The rebuild tickets are 599 to 610 (F2 to F5, N1 to N7, D), in the order of the map's section 6.
