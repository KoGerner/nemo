# BIA-Workflow

A manager scans a code, lands in their own room, and chats with nemo about their company's files. When
they ask for it, nemo walks them through five stages to a signed Business Impact Analysis with a
dependency graph. This glossary fixes the words; the decisions behind them are in
`docs/adr/`.

## The product

**BIA-Workflow**:
The product as the BCM community knows it. The public name.
_Avoid_: the addendum, the agent, BIA-Workflow 2

**nemo**:
The internal project name for the rebuild, and the name of the engine itself. Its interface is MCP,
and no front end is privileged.
_Avoid_: v2, the server, the backend

**Demo skin**:
A front end built to show nemo rather than to run it in production. The Chainlit app for November is
one. A demo skin holds nothing confidential and its transcripts are operator-readable.
_Avoid_: the frontend, the UI, the demo app

## The workspace

**Room**:
One manager's isolated workspace: their files, their walk, their record, their graph. Rooms never see
each other.
_Avoid_: session, workspace, tenant, project

**Room code**:
The secret that both names a room and grants access to it. It decides which files are reachable — the
channel and the person never do.
On the login page, the email typed at Start also opens that email's newest room (ADR-0063); the stage QR
still carries the room code.
_Avoid_: room id, session id, link

**Room folder**:
Where a room's company files and artefacts live. For demo rooms that is a folder on our server; for
production it is the organisation's own store, which we never hold.
_Avoid_: the drive, SharePoint, the bucket

**Seed**:
The one set of company files every demo room is minted from. A room is a copy of the seed at scan
time, so changing the seed changes every room minted after it and none minted before.
_Avoid_: the pack, the company data, the template room

## The walk

**Chat**:
Talking with nemo about a room's files, in the manager's own words. It is the default and the product;
the walk is something the manager asks for from inside it.
_Avoid_: free mode, Q&A, the assistant

**Next step**:
One of up to five taps nemo offers under a chat answer, each a different move that helps the manager answer
his question or move his task forward, such as "Ask Barsch: deputy" or "Start Picking". The model proposes them and code keeps
only those a tool of this room can do now (ADR-0056). It only offers; the manager decides, and a question never opens a walk by
itself.
_Avoid_: suggestion, call to action, follow-up question

**Model-led turn**:
A turn the model answers: it reads the room's files through the file map, writes the whole answer in the template for its kind,
and code checks every figure, date, name, recipient and action claim before anything shows (ADR-0056). It covers chat and the
words of a stage card; the card's figures, rule, gradient and record stay code's. When a tool call fails it is retried once with the error, then the answer shows the part that passed with what is missing, never the plain line ("I couldn't give you a reliable answer to that. Try asking it another way.") while anything passed (ADR-0061 decision 6).
_Avoid_: agent fallback (retired with ADR-0053 decision 1), agent mode, AI mode, the harness

**Brake**:
The one switch, read every turn, that puts every phone back on the code-card path of the M19/M20 build. Only the owner flips it. The switch file present with `on` = brake released = model-led; the file absent = brake set = today's
path. ADR-0061 (accepted 2026-10-29) deletes the switch, with the old answer code, in one ticket (610) on the day the new path passes; until then switch OFF stays frozen as the demo net, and the agent fallback of ADR-0053 is deleted in 599.
_Avoid_: kill switch, go/no-go, fallback switch

**Goal mode**:
A loop for a picture no template draws: code writes the checklist and checks every round, at most 3 (his definition, Q8;
ADR-0054, proposed, after the demo). It never draws dependencies; those get the live graph's link.
_Avoid_: free drawing, ZCode mode, goal loop (as a separate thing)

**Template**:
The fixed structure of one kind of answer that code hands the model: the impact-over-time chart's look, the letter's frame, the
invitation, the dependency-graph link, "verdict, then reasons with their lines". The look never changes; the model supplies the
content and code checks it. A template is never an answer.
_Avoid_: card (a card was a finished answer), free graph, chart type, Mermaid

**Answer shape**:
The approved shape of a good answer for one kind of question (`docs/answer-shapes.md`: 16 kinds and 12 rules): what comes first, the order of the parts, what to name when the files do not say. It is never stored text; every fact comes fresh from code's fact tools and the model writes the words. A shape is what ADR-0061 calls a template per kind of question, so say *answer shape* for the kind-of-question form and *template* for the fixed look (a chart, a letter's frame).
_Avoid_: prepared answer, canned answer, card

**File map**:
The list of the room's files, one line each saying what it holds, that code hands the model every turn so it knows where to read.
_Avoid_: index, file search, context

**Brief**:
What code hands the model before its first call: the file map, the method's rules, the story's today, what was last shown, the
template for the answer's kind, its must-cover list, and the focus activity's raw rows, numbered by file and line: facts,
never sentences.
_Avoid_: context, system prompt, briefing (the briefing is B7's card)

**Must-cover list**:
The items code says an answer of a kind has to contain (every listed gap, every asked activity). An item still missing after
one send-back is recorded and scored as a miss, never added by code.
_Avoid_: plan, todo, rubric

**Last shown**:
The room's memory of the last chart (its activities, classes and years), the last drafts and the last invitation, kept in the room
folder. A follow-up edits the last one of its kind.
_Avoid_: history, state, cache, memory (unqualified)

**Claim check**:
Code's check that each sentence of a model-led answer carrying a figure, date, count, class, name or recipient cites a
`[file:line]` the model read this turn, and that the line holds it (in its own column where two columns are easily confused). A failing sentence goes back once with the reason, then is dropped.
_Avoid_: validator, fact check, judge, the checker (the check seat is also "checker")

**Quality branch**:
The throwaway branch `quality-prototype`, built to show what he likes in an answer. A reference for ideas and evidence: it never lands, and no diff is copied from it (ADR-0065).
_Avoid_: the prototype (`skin/PROTOTYPE_*` is something else), the quality build

**Action claim**:
A sentence saying nemo did something ("done", "moved", "is in Drafts"). It stands only if a tool did it this turn.
_Avoid_: confirmation, status message

**Walk**:
The five stages taken in order, from scope to a signed record. An output the manager asks for, never a
path he is marched down.
_Avoid_: flow, wizard, process

**Stage**:
One of the five steps of the method: scope, interview, standardise, requirements, handover. There are
five and only five; the missing-owner loop is not a sixth.
_Avoid_: step, phase, turn

**Stage card**:
What a stage puts in front of the human: the server's proposal, the reason before the figure, the
decision rule, and the gradient to answer it with.
_Avoid_: prompt, message, screen

**Gradient**:
The four ways to answer a stage card — endorsed, endorsed with reservations, needs discussion,
blocked. Hesitation is recorded rather than flattened into yes or no.
The manager sees them in plain words; the record keeps the four values.
_Avoid_: approval, vote, confirmation

**Decision**:
One answer to one stage card, appended to the run and never rewritten. It carries the stage, the
moment it was taken, the card it was taken on, and the gradient. The decisions list is how a walk
is read after the fact by somebody who was not watching it, and it records what happened rather
than checking it.
_Avoid_: the log, the audit trail, the turnlog, the ledger

**Handover**:
Where the BIA ends: the requirements passed to solution design. The method never drafts a continuity
plan and stops here deliberately, at the **handover boundary**.
_Avoid_: the plan, the output, delivery, PP4, the PP4 boundary, GPG, professional practice

## The evidence

**Activity**:
A piece of work the company does, such as production or raw material procurement, with its owner and its sites. It is what a
BIA is about, never the BIA itself.
_Avoid_: calling an activity "a BIA"

**BIA**:
One business impact analysis of one activity in one cycle, kept as a record. An activity has a BIA per cycle (last year's, this
year's), so picking a BIA is not picking an activity.
_Avoid_: the activity, the assessment

**Record**:
The machine-readable BIA. The single source every view, figure and graph is generated from.
_Avoid_: the data, the JSON, the document

**Referee**:
The deterministic check that must pass before anything is saved. It derives MTPD rather than
accepting one, refuses an RTO that is not strictly inside its MTPD unless the gap is flagged, and
rejects any quote it cannot find verbatim in a file in the room.
_Avoid_: validator, gate, linter

**Finding**:
Something the referee will not resolve on the human's behalf — a missing owner, an unflagged gap, a
contradiction between two owners. A finding is data, never a wall.
_Avoid_: error, refusal, warning

**Served fact**:
A fact about the room that nemo works out from the files and hands to the chat finished: a company
and its share of revenue, who was interviewed and how many, the figure the record carries. The model
repeats it and never re-derives it. Where an interview and the record disagree, the record's figure
leads and the interview's is named as said.
_Avoid_: context, grounding, retrieved fact

**Dependency graph**:
The one page that shows a room's resources, grouped, and which activities depend on them. It is drawn
from the room's register and its BIA record (or the record proposed for acceptance), and carries that
record's fingerprint. It is a picture of those two, never a source: nothing reads a figure from it.
There is only this one (ADR-0040). The process map is not a dependency graph.
_Avoid_: the diagram, the map, the visualisation, the grouped graph (there is no other)

**Graph scope**:
One of the two views of the one dependency graph: **This BIA** (the resources one activity's BIA stands on) or **Whole
company** (every activity and resource in the room). Two scopes of one graph, never two graphs.
_Avoid_: the company graph, the BIA graph, view

**Seed merge**:
Two resources in the seed that come from one record row become one, keeping the record's quote; the retired one is archived,
never dropped (ADR-0034 Part E 14).
_Avoid_: dedupe, cleanup

**Page merge**:
Look-alike resources drawn as one box on the dependency graph, saying what they were merged from; the register keeps each one
(ADR-0034 Part E 16b). A page merge never changes the seed.
_Avoid_: merge (unqualified), grouping

**Key role**:
A role named inside an activity's one People box on the dependency graph, up to three for every activity: a role with no
spare first, then the largest emergency team (the reviewer's rule, which he took). Never ranked by the MTPD. The other roles show as a
count.
_Avoid_: key person, critical role, top role

**Resource kind**:
One of the graph's resource columns, in ISO 9001:2015 / ISO 22301 words (356, final check §12.14): **People**, **External
providers**, **Release** (the veterinary and QA release, ISO 9001 8.6), **Equipment and transport**, **ICT**, and **Buildings
and utilities** (plant utilities, sites, power and network). The activities split into **Core processes** and **Support
processes**. The register's own `asset_type` values are not these words.
_Avoid_: from outside, plant, IT (as a column), foundation

**Support band**:
On the Whole company scope, the HR support or IT support activities drawn as one band with the resources they share; opening
it shows its activities.
_Avoid_: support cluster, swimlane

**Gap**:
Something the register states is missing, of four kinds: **no workaround** (a transcribed workaround that is empty or states
none, ADR-0044; an authored "single source" mark is its authored form, shown as Single source), **owner missing** (`owner_gap`;
a CFO-only owner reads "owner not yet named" in a draft and shows as owner missing on the graph), **a missing kind** on an
activity (327), and **a missing link** (327). The graph's gap chips are No workaround · Single source · Owner missing; a missing kind or a missing link shows as a
"missing: …" line, never a chip. A re-BIA
finding is a line, not a gap. The referee's "RTO gap" keeps its own name.
_Avoid_: risk, weakness, issue, SPOF (in the product's words)

**Needed by**:
On a box, the activities that depend on it, directly or through boxes that stand on it. Never "stop": the graph says
"depend on".
_Avoid_: used by, dependants, impact count

**Source-stated**:
Said by one sentence of a prior BIA record in the vault; the seed carries its faithful English
translation, except that a real brand a record names is replaced by an invented name and flagged
(ADR-0034). Every edge, figure and name in the seed's register is
source-stated or authored, and says which (ADR-0034).
_Avoid_: sourced, evidenced, verified

**Authored sentence**:
A dependency sentence written for the demo pack and stated by no prior record. It lives in the seed's
`resource-dependencies.md`, never in the vault originals. Every line opens "Written for the demo
pack, not in any prior record:", and its edge's ref reads `authored for the pack A<k>` (ADR-0034).
It carries no figure.
_Avoid_: inferred edge, judgement edge, synthetic fact

**Guidance corpus**:
The frozen AI4BCM body of method and literature served by the open connector. It ships the method and
holds no company facts.
_Avoid_: the knowledge base, the KB, the docs

**Score**:
One cell of the impact grid: how badly a named consequence bites at a given elapsed time, on the
method's own scale. It is a figure the method defines, never a judgement about how a walk went or
how well a wording worked.
_Avoid_: rating, grade, the number — and never a quality score, a rubric or an eval

**Trace**:
A turn as the review workbench holds it: a copy made after the walk, for reading and comparing. It is
never written during a walk, never read by one, and nothing is judged by it. It says which wording was
in play, never how the walk went.
_Avoid_: session, log, span, telemetry

**Turn file**:
One line per turn of a walk, written as the turn ends: what was said, what nemo sent the model and
what came back, what each tool returned, and which wording was in play. It is the evidence of how a
walk ran, kept after the walk; it is never the record, which is what the manager signs.
_Avoid_: the record, the log, the trace, the sidecar

**Flagged**: a register row the one stated rule marks for an activity: it states no workaround, or is an authored single source (ADR-0044). The list an activity's single-point answer gives.

**Stands-on table**: the risk register's "Single points of failure" table: resources much else stands on, listed per asset and not per activity. A resource in it need not be flagged for a given activity.

