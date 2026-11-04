# An interrupted walk resumes from disk, and the artefacts are the truth

A manager who puts their phone down mid-walk is the ordinary path, not the crash path. This ADR
settles the closed set of run states, a stable run identity, what is checkpointed and when, and what
becomes of a record write, a view render or a graph regeneration that was in flight when the process
stopped. It amends ADR-0007.

Two things were believed when this was written and are not true. **ADR-0001 does not say rooms stop
on idle** — a grep across all nine ADRs for idle, resume, interrupt, restart or recover returns three
hits, none of them about room lifecycle. The sentence "rooms start on claim and stop on idle" is a
capacity observation in `docs/status.md` (15Gi of RAM, ~50 rooms), attributed to a decision that was
never taken. And the run protocol is **not** absent: `bia_run.py` and `bia_run_store.py` in the live
v1 system already hold a five-member status set, an explicit transition table in which `closed` has
exactly one inbound edge, a UUID primary key at `output/.bia-runs/<uuid>.json`, atomic
compare-and-set on `revision`, and a persisted `current_card` — 793 LOC and 27 tests. What the walk
was missing was never the machine. It was the decision about what the machine means when nobody is
watching.

## The room lifecycle is not decided here, and nothing may depend on it

The walk must survive a stop at any instant from any cause: an idle reaper, a `SIGTERM` deploy, an
OOM kill, a closed laptop. A resume model correct for an arbitrary stop is correct for the reaper as
a special case; the reverse does not hold, and the reaper's timeout belongs to whoever writes the
unit file. Recorded so it is not read as settled: **how long a room lives, and what sweeps the disk
after one dies, are open.** `docs/ticket-board.md` records that a `SIGTERM` restart orphans a
session's files directory at the default 3600 s `session_timeout`, and no ADR covers that either.

## The run protocol is the fourth thing that survives from v1

ADR-0007 names three survivors on three criteria: deterministic, carries its own tests, does no gate
bookkeeping. The run protocol meets all three, and it is the part of the typed lane that worked on
the first walk that tested it — walk 15, two BIAs signed in one room, 24 turns, zero server errors.
It ports, and this ADR patches it. It is amended rather than re-derived because re-deriving a state
machine that already exists produces a *second* state machine, which is the failure the ticket exists
to prevent.

## The closed set of run states

Six, exhaustive, a coded value on the run itself and never inferred from the absence of activity:

- **`awaiting_human`** — a stage card is on disk and the walk is waiting for a gradient answer. This
  is a state, not a silence. A room that stopped while waiting and a room that was never asked are
  distinguishable after the fact, by this value and the transition timestamp beside it.
- **`server_working`** — an answer was accepted and the server is between movements. It is never
  trusted on resume; finding it means reconciling against the artefacts and demoting to whatever they
  actually support.
- **`record_saved_graph_pending`** — the record is on disk and the picture generated from it is not
  yet bound. Kept from v1 under its own name because Stage 5 binds on it: saved, and not yet finished.
- **`reviewed_pending_owner`** — the handover was accepted and the signature is outstanding.
- **`closed`** — terminal. One inbound edge, from `reviewed_pending_owner`, and only with a complete
  signature *and* a graph receipt whose `record_sha` is re-verified against the bytes on disk at that
  moment. **The terminal state is reachable only through the write that produces the artefact.** This
  is the rule that makes v1's central failure unreachable: on 2026-08-31 in `adler-stjmed` a run
  declared itself closed while the graph URL showed nothing, because closure was bookkeeping about
  gates rather than a statement about artefacts.
- **`superseded`** — terminal. Reachable from every non-terminal state.

Every other edge: `awaiting_human` → `server_working`; `server_working` → `awaiting_human` (the next
card is written), → `record_saved_graph_pending` (Stage 4's record landed), or →
`reviewed_pending_owner` (Stage 5's handover accepted); `record_saved_graph_pending` →
`awaiting_human` once the receipt binds. Nothing else is legal, and an illegal transition is a bug,
not a finding.

## The run identity is minted once, and is not a function of the room's contents

Today `run_id` is `uuid5(company, process, sorted(source_digests))`. That names the run after what it
was read from, so **the identity changes when the room's files change**: dropping one transcript into
`07_Interviews/` mid-walk sends the next bare call to a key that holds nothing, which mints a second
Stage-1 run beside the one in flight and then answers `ambiguous_run` forever after. The identity
breaks on the most ordinary act in a BIA.

A run's identity is a **UUIDv4 minted once**, when the run is first opened, and persisted. Source
digests stay on the run as evidence of what it was read from. A digest that has changed since the run
opened is a **finding** carried onto the next card — the human is told the ground moved and by which
file — never a rename and never a silent re-read. The record already carries this same `run_id`, so
the record and its run are one identity and always were.

## What is checkpointed, and when

The run file is the checkpoint, written at **every state transition** and at no other time:
atomically (temp file, `fsync`, `rename`), compare-and-set on `revision`.

**Amended 2026-09-20: the directory `fsync` and the exclusive lock are struck, and the temp file,
`fsync` and `rename` are built.** This paragraph originally asked for five things and the code did
one — `nemo.room_store._written` was a bare `write_bytes`, which truncates the file first, so a
`SIGTERM` deploy or an OOM kill between the truncation and the last byte left an unparseable run
file exactly where the resume checkpoint should be. That is now a staged file beside the target,
`fsync`ed and renamed onto it, and `src/nemo/test_room_store.py` kills the write twelve bytes in
and reads the previous record back whole.

The other two are struck rather than deferred, for one reason each. The **directory `fsync`** makes
the *name* durable across a power loss; the file `fsync` already makes the *bytes* durable, and
without the directory one a power loss can only serve the previous record — which is a whole,
loadable record that this ADR's own reconciliation path then resumes from. It buys nothing this
ADR promises, and nothing in a test can observe it, so the mutation gate cannot certify it: it
would ship as a line no test can defend. The **exclusive lock** would make compare-and-set atomic
across processes, and there is no second process — the demo skin is one `chainlit run` (no
workers, `deploy/nemo-demo-skin.service`), `write_record` is synchronous with no `await` between
the read and the write, so within that process the check and the write cannot interleave. A lock
belongs in this file again the day a second writer does. What the ADR asked for that is genuinely
missing is nothing else: the compare-and-set was already there. It carries the run id, schema version, company, process, revision, stage, status, the
timestamp of that transition, source digests, the proposal, every gradient decision and reservation,
the referee result, `record_sha`, the view shas, the graph receipt, the sign-off result, and the
current card.

The standard it is written to: **discard all conversation memory, and the walk reconstitutes from the
room and the process alone.** No fact the walk needs may live only in a conversation. The worst
exchange in the corpus is the counter-example — after a browser refresh, v1 asked the owner for a
stage number and then for the body of a Stage-1 document it had written itself minutes earlier and
which was sitting readable on disk.

## The run file is a claim; the artefacts are the truth

On every resume the server re-reads the artefacts the run file names — the record bytes, the four
views, the graph page and its `evidence.json` — and re-derives their fingerprints before serving any
card that stands on them. Agreement means the state is real. Disagreement demotes the run to the last
state the artefacts actually support, and says so on the card.

This is the cost of the product's own claim. Everything downstream of the record is a pure function of
the record bytes — the four views are rendered from them, and the graph is rebuilt wholesale from them
and is a cache, never a source (ADR-0004). A resume that took the ledger's word for it would
reintroduce, at the one moment nobody is watching, exactly the failure the receipt binding exists to
close.

## An interrupted side effect is re-executed, never rolled back

Stage 4 is three movements in one order — the record, then the four views, then the graph and its
receipt — and a stop can land between any two. There is no two-phase commit and no intent log,
because none is needed: **every one of the three is a deterministic function of state that is already
in the checkpoint.** Recovery is to re-run the movements whose artefacts are missing or whose
fingerprints disagree, in the same order, and stop when the receipt binds. Re-running a movement whose
output is already correct rewrites identical bytes.

Two properties make that safe, and both are required of the implementation. Every artefact write is an
atomic replace, so a reader sees the old bytes or the new bytes and never half of either. And the
graph regeneration is idempotent on the record fingerprint: the same record produces the same page,
which is what lets the receipt bind on `record_sha` rather than on `page_sha` — a lesson already paid
for on 2026-09-02 in `adler-yj3477`, where a gate written against the exact page deadlocked when a
benign operator re-render moved it.

## Resume serves the state on disk, and asks the human nothing

Resume is **announced, in one sentence, in the colleague's voice of ADR-0006** — what was last
decided, when, and what is in front of them now — and it carries no gradient and no question. Where
reconciliation demoted the run, or a source digest moved, that is the same sentence's second half,
said plainly.

No resume path may name its own stage. The server serves the card for the state on disk and nothing
else. Recorded because v1 had the opposite: a numeric resume branch that rendered any stage the caller
asked for with no advance gate at all, which is a way of walking past every guarantee the referee
makes.

## Consequences

- **ADR-0007 is amended**: `bia_run.py` and `bia_run_store.py` port as the fourth survivor, ~793 LOC
  and 27 tests on top of the ~2,500 already moving. The `uuid5` identity and the single `in_progress`
  status do not port; they are replaced as above. Nothing else about ADR-0007's do-not-port list
  changes — the write-lane jaws, the 130 refusal sites and the two ledgers of gates stay gone.
- **The status enum ships with this ADR, not with a stage ticket.** Written after the stages, it would
  be written twice.
- Compare-and-set on `revision` remains what it is: concurrency control, so two answers to the same
  card cannot both land. It says nothing about resume, and this ADR is what says something about
  resume.
- Reconciliation costs a handful of fingerprint reads over files already on the room's disk, once per
  resume. That is the whole price, and it buys the acceptance standard as something verifiable rather
  than asserted.
- **Every stage ticket is now sliceable against a decided resume model.** Tickets 15, 16 and 17 —
  Stage 4's three movements — inherit the re-execution rule rather than each inventing one.
