"""PROTOTYPE, throwaway (3_nemo_check / t70, 2026-09-18). The scripted manager, and how a walk is
scored.

Ticket 70 (nemo-conversation 13) and ticket 69 items 1-2 (nemo-conversation 12). Six named
scenarios, each a short script of what a BCM manager types, with the taps in between named by
what they say — never "the first option". Each runs on a fresh room, writes its turns to disk the
moment each turn ends, and is scored afterwards from the room's files and the rendered transcript
by this module's own code: never from a count a guard or a tool reported.

    python PROTOTYPE_bakeoff.py                       # all six, one after another
    python PROTOTYPE_bakeoff.py --scenario dispute    # one alone
    python PROTOTYPE_bakeoff.py --scripts             # only rewrite SCENARIOS.md in OUT

Writes, per scenario, under OUT (the bakeoff archive): <scenario>.turns.jsonl (one line per turn,
flushed as it happens), <scenario>.md (the transcript), <scenario>.json (scores, verdict,
per-walk numbers) and <scenario>.tripwire.txt (for a person to read; nothing reads it back).

This is the instrument, not the conversation: it changes nothing nemo or the core does.
"""

from __future__ import annotations

import json
import os
import random
import re
import statistics
import time
from pathlib import Path
from typing import Any

from nemo import duration, handover, walk

import PROTOTYPE_core as core
import PROTOTYPE_fidelity as fidelity
from bia_figures.register import recovery_point_for
from PROTOTYPE_clocks import BAKEOFF

#: The seed the scenarios mint from: `NEMO_SEED`, as `PROTOTYPE_draft.SEED` reads it, with the old
#: path as the default so a run that sets nothing walks what it always walked (t139 migrate (c)).
SEED = Path(os.environ.get("NEMO_SEED", "/home/user/work/nemo-playground/seed"))
OUT = BAKEOFF  # the archive outside the repo since ticket 242 step 8
DRAFTS, FIXTURES = core.DRAFTS, core.FIXTURES  # t176: the cache, then the tracked fixtures
#: An instrument input, tracked in the repo: the archive is history, never a live input (242 fix).
MACHINE_IDS = Path(__file__).parent / "instrument" / "machine_ids.txt"
DEFAULT_SEED = 7013
DEFAULT_MODEL = "deepseek"

#: Today's cap (the old driver's MAX_TURNS), per activity walk. Hitting it ends the walk `turn cap`.
TURN_CAP = 30
#: A manager who sees nothing move in the room's files for this many of his own turns gives up:
#: the walk ends `abandoned`. Turns that fire a scripted line do not count (he is asking, not
#: stuck).
STALL = 8

#: What the live app sends when a room opens (PROTOTYPE_conversation_app.start). Not the manager's.
OPENER = "(The manager has just opened the room. Greet them.)"

#: Whose activity each is, from the interviews' own front matter (07_Interviews/*.md `owner:`)
#: and last cycle's BIA (08_Prior-Cycle, "Owner / Deputy"). The manager knows this; he signs for
#: them.
#: t139 contract: the room names a process by its slug (the interviews' `department:`), so the keys
#: are the slugs; the owners are the prior cycle's "Process owner" rows (08_Prior-Cycle).
OWNERS = {
    "incident-and-problem-management": "Marek Sobotta",
    "helpdesk-and-support": "Frerk Sievers",
    "event-management": "Marek Sobotta",
    "order-picking": "Henning Barsch",
}

# ── what the manager types: every line has paraphrases, one picked per run from a seeded RNG ───
LINES: dict[str, list[str]] = {
    # t96 fix 2 (2i): the greeting lists nothing any more, so no line says "which one" or "these";
    # three lines still, in the same order, so every seed picks the same slot it picked before
    "ask_critical": [
        "Which of our activities is the most critical, based on the interview transcripts?",
        "Based on the interviews, which of our activities is most critical?",
        "Going by the interview transcripts, which of our activities matters most?",
    ],
    "pick": [
        "Let's do {activity}",
        "{activity}, please.",
        "I'll start with {activity}.",
    ],
    "conflicts": [
        "Show me the conflicts first",
        "Before anything else, show me the conflicts.",
        "Conflicts first, please.",
    ],
    "go_on": [
        "Go with your recommendation.",
        "Your recommendation is fine, carry on.",
        "Do what you recommend and move on.",
    ],
    "signature": [
        "Konstantin Gerner, BCM manager, signing on behalf of {owner}",
        "Konstantin Gerner - BCM manager - on behalf of {owner}, the activity owner",
        "Signed Konstantin Gerner, BCM manager, on behalf of {owner}",
    ],
    "dispute_rto": [
        "Hold on, that RTO is wrong. Make it two hours.",
        "I don't accept the RTO on this. Make it two hours, please.",
        "Change the RTO - make it two hours, that's what {owner} asked for.",
    ],
    # t71 (rpo-choice): the RPO he types after "Change RPO", tighter than the register's <24 h;
    # typed
    # whole as the value, so it is the method's own word. t139 (14_nemo_check's ruling (b)): "<1 h",
    # the tightest word of the new vocabulary (<1 h, <24 h, <168 h, >168 h); the old "0 h" is none
    "rpo_value": ["<1 h"],
    "reservation": [
        "Add a reservation to the record: the two-hour recovery has never been tested in a drill.",
        "I sign with a reservation - nobody has tested a two-hour restart in a drill yet. Put "
        "that in.",
        "Record my reservation, please: a 2 h recovery is untested, we have never run a drill on "
        "it.",
    ],
    "insist": [
        "No, I want the RTO at two hours. Keep going with that.",
        "Keep my two hours and carry on.",
        "Two hours is my figure. Go on with it.",
    ],
    "term": [
        "What does MBCO mean?",
        "Sorry, what's an MBCO?",
        "Quick one: MBCO - what is that?",
    ],
    "guidance": [
        "What does the guidance say about RPO?",
        "What does the AI4BCM guidance say about setting an RPO?",
        "Is there guidance on RPO I can read?",
    ],
    "grid": [
        "Show me the grid again.",
        "Can I see the impact grid again?",
        "Put the impact grid back up, please.",
    ],
    "critical": [
        "Which is most critical?",
        "Which activity is the most critical one?",
        "Of all of them, which is most critical?",
    ],
    "finished": [
        "Which ones are finished?",
        "Which activities are finished now?",
        "What's finished so far?",
    ],
    "packing": [
        "Does Order picking have a record?",
        "Is there a record for Order picking yet?",
        "Has Order picking got a record?",
    ],
    "reopen_1": [
        "I need to change the RTO on Incident and problem management. Reopen it, please.",
        "Reopen the Incident and problem management BIA, the RTO needs fixing.",
        "Can we reopen Incident and problem management? I want to change the RTO.",
    ],
    "reopen_2": [
        "Go back into Incident and problem management anyway, I have to amend it.",
        "I still want to amend Incident and problem management - take me back into it.",
        "Please just undo the signature so I can correct Incident and problem management.",
    ],
    # ticket 72 (`new-activity`): he asks for an activity the files don't list, names it, and is
    # interviewed about it at stage 2. The answers come in order, whatever nemo asked: six, because
    # nemo's interview is six questions long (`nemo.conduct.TURNS`).
    "ask_new": [
        "No, this time, let's do something with Cleaning.",
        "Not those - I want to start a BIA for Cleaning.",
        "Let's do Cleaning this time, even though it's not in the list.",
    ],
    # t139 contract (14_nemo_check's CORRECTION): the activity the files don't list is CLEANING. The
    # risk register's R-HR-01 names it ("... engineering or cleaning"); no process is filed for it
    "new_name": ["Cleaning", "Hygiene cleaning"],
    "cleaning_1": [
        "Cleaning is the hygiene crew for production, cutting and the chilled stores, under "
        "Henning "
        "Barsch; I'm answering for him. Two contractors do the work: Reinigung & Clar and Fresh "
        "& Clean.",
        "It's Henning Barsch's area and I'm standing in for him. The cleaning of production, "
        "cutting and "
        "the chilled stores is done by two contractors, Reinigung & Clar and Fresh & Clean.",
    ],
    "cleaning_2": [
        "Production and cutting depend on us most: no line starts its shift until it has been "
        "cleaned "
        "and released. Order picking needs the chilled stores kept clean.",
        "Mostly production and cutting - a line only starts once it is cleaned and released. And "
        "order "
        "picking needs clean chilled stores.",
    ],
    "cleaning_3": [
        "One night without cleaning and the lines cannot be released in the morning; after a few "
        "days "
        "the veterinary inspection and our food-safety certification are at stake, so it becomes a "
        "legal question.",
        "A night without cleaning means no line release in the morning; after a few days the "
        "veterinary "
        "inspection and the food-safety certificate are at risk, a legal matter too.",
    ],
    "cleaning_4": [
        "Production's own staff can clean in an emergency for about three days. Beyond 72 hours "
        "without "
        "the contractors, hygiene slips and the lines stop.",
        "Our own production staff can stand in for three days or so. After 72 hours without the "
        "contractors the hygiene standard slips and the lines stop.",
    ],
    "cleaning_5": [
        "We need hot water, the contractors' cleaning agents, and the time-recording system that "
        "books "
        "the contractors' hours.",
        "Hot water, the cleaning agents the contractors bring, and the time-recording system "
        "that books "
        "their hours.",
    ],
    "cleaning_6": [
        "Our fallback is production's own staff under our own responsibility, or another "
        "contractor - "
        "there are enough providers. We have never tested that.",
        "Fallbacks: our own staff, on our own responsibility, or another cleaning provider - "
        "there are "
        "enough of them. Never tested, to be honest.",
    ],
}
#: t139 (15_nemo_check's ruling (h)): the lines that are a VALUE he types, not prose. Each has
#: exactly
#: the method's own spelling (one entry), because a second spelling would be signed as typed; every
#: other line is prose and keeps two or three paraphrases
VALUE_LINES = ("rpo_value",)
#: the interview answers, in the order he gives them (ticket 72)
INTERVIEW_ANSWERS = [f"cleaning_{i}" for i in range(1, 7)]

# ── what the manager taps: named by the option's words, never by its position ─────────────────
#: Moving on, most specific first. The first rule that matches exactly ONE option is tapped. If
#: its best rule matches two or more, the tap is ambiguous and he types `go_on` instead; if none
#: matches, he types `go_on` too. So a tap never depends on where an option sits in the list.
#: t73: the taps are nemo's own words now (`core._step_taps`). "Accept all open proposals" comes
#: beside one score's "Accept …", so "accept all" is tried first; stage 2's keep tap says "Keep
#: these <n> interviews", "Keep this interview" at one (t528 r2: no "Keep all"); stage 1's
#: `walk.AGREE` ("Yes, that's the scope") meets "go ahead"'s "yes". A conflict's sides meet no
#: rule here: since m80 every scenario taps one (`choose_side`, the seed's choice), because on a
#: model turn nemo turns "go with your recommendation" into a side tap he must press (t80) and a
#: typed `go_on` alone stalls the walk at stage 3.
#: m80: a figure tap's shape, read off the core function that builds its label, so a label nemo
#: changes moves this pattern with it. The kind is one of the three figures; the value is the rest.
_KIND, _VALUE = "\x00KIND\x00", "\x00VALUE\x00"


def _label_shape(build: Any) -> str:
    shape = re.escape(build(_KIND, _VALUE)).replace(re.escape(_KIND.upper()), "(?:MTPD|RTO|RPO)")
    # why: `build` is Any (a tap builder), so its result is
    return "^" + shape.replace(re.escape(_VALUE), ".+") + "$"  # type: ignore[no-any-return]


#: fix 3's score-row proposal (`core.Session._proposal`), which core builds inline, not by a named
#: constant: "Use {category} scores ({s} · {s} …)". `test_driver_taps_what_nemo_drew` holds this to
#: the label core draws, so the shape cannot drift from it silently.
SCORE_ROW_TAP = r"^Use .+ scores \([1-5](?: · [1-5])*\)$"

MOVE_ON: list[tuple[str, str]] = [
    ("recovery gap", r"recovery gap"),
    ("as proposed / recommended", r"as (you )?propos|recommend|\bmy rec\b"),
    ("accept all", r"\baccept all\b"),
    ("accept", r"\baccept"),
    ("endorse", r"\bendorse"),
    ("agree", r"\bagree"),
    # t72b: at stage 2 of an added activity he keeps HR's risk-register row, whatever his name for
    # it (the name rule already keeps it for "HR", so no such tap is drawn there); tried before
    # "keep all", which confirms stage 2
    # t96 fix 1: his tap reads the row's text, never its id; R-HR-01's line of the register (t139:
    # the new register's R-HR-01, t158's report)
    ("keep R-HR-01", r"^keep: staff shortage in production, cutting, engineering or cleaning\b"),
    ("keep all", r"\bkeep (them )?all\b|\bkeep th(e|is) interview\b|^keep these \d+ interviews$"),
    ("confirm", r"\bconfirm"),
    ("hold the interview now", r"\binterview now\b"),  # nemo's own offer at stage 2 (t72)
    ("go ahead", r"\bgo ahead\b|\bproceed\b|\bcontinue\b|\byes\b"),
    # m80 (8_nemo_check's ruling, 2026-09-21): on a model turn no `decide` writes; nemo draws it as
    # a
    # tap of his (t80/93, `core._his_act`). These are the shapes nemo draws that no rule above
    # meets, read from core's own label builders (`_label_shape`), never from the model's text.
    # Tried last, so a walk that never meets them taps exactly as before. Not pressed, on purpose:
    # "No MTPD on the record" (a proposal to strike a figure) and UNRESOLVED_TAP (a referral names
    # owners on his certificate); he types `go_on` there, and a stall on one is a finding.
    ("keep the figure he set", _label_shape(core.keep_figure_tap)),  # t93: his own first
    (
        "record the figure nemo named",
        _label_shape(core.confirm_figure_tap),
    ),  # t80: "Record RTO 8 h"
    (
        "hand it to the register",
        _label_shape(core.derived_figure_tap),
    ),  # t93: "Use the register's RPO 4 h …"
    ("use the score row nemo named", SCORE_ROW_TAP),  # fix 3: "Use Financial scores (3 · 3)"
    # t116: the referee's open question on an MTPD he asserted blocks step 3; he keeps his figure,
    # which is what the record carried before t116, and nemo's reason ask then meets "go ahead"
    # through its Skip tap. Withdrawing it and leaving it open are never pressed for him.
    (
        "keep the asserted MTPD",
        "^" + re.escape(core.KEEP_ASSERTED_TAP).replace(re.escape("{asserted}"), ".+") + "$",
    ),
]
#: Never tapped, whatever else they say: the signature (typed, never tapped — owner's ruling
#: 2026-09-17), going back, stopping, reshaping scope or evidence, a retry, a reservation he has
#: not got (a reservation is typed, in his words — `dispute`). And any option that
#: names another activity than the one he chose (M1: he does not follow a steer).
#: Each pair is (label for SCENARIOS.md, pattern); `NEVER` is the patterns alone, so `scripts_md`
#: reads its "never taps" sentence off this same table instead of a hand-typed copy that can drift
#: from it (13_nemo/t70 fix, part d — it missed "with reservations" and the retry wording once).
NEVER_RULES: list[tuple[str, str]] = [
    ("a signature", r"\bsign"),
    ("going back or reopening", r"re-?open|go back|back to step|start over|redo|undo"),
    ("stopping or pausing", r"\bstop\b|\bpause\b|\blater\b|leave it"),
    ("splitting", r"\bsplit\b"),
    ("dropping", r"\bdrop\b"),
    ("'discuss'", r"\bdiscuss"),
    ("a retry", r"retry|\btry\b.*\bagain\b|once more|keep trying|keep fighting"),
    ("'with reservations' unless he has one", r"with reservation"),
]
NEVER: list[str] = [pattern for _, pattern in NEVER_RULES]

def _signs_as(label: str) -> bool:
    """Whether a label is one of the two taps nemo draws for who he signs as (t134)."""
    return label == walk.SIGN_AS_THE_OWNER or label.startswith(walk.SIGN_ON_BEHALF.format(owner=""))


#: nemo asking him for his signature in words ("type your own name"). Heard only once the record is
#: saved (run file at stage 4 or later); before that the handover has not been put to him.
ASKS_FOR_NAME = re.compile(r"\btype (in )?(your|his) (own )?(full )?name", re.I)

#: Words that name an activity in prose or in an option (first word of each, plus plain aliases).
ALIASES = {
    "incident-and-problem-management": [
        "incident-and-problem-management",
        "incident and problem management",
        "problem management",
    ],
    "helpdesk-and-support": ["helpdesk-and-support", "helpdesk and support", "helpdesk"],
    "event-management": ["event-management", "event management"],
    "order-picking": ["order-picking", "order picking"],
}

# ── the six scenarios ─────────────────────────────────────────────────────────────────────────
#: `moves` fire in order, each once, the first turn its trigger holds (triggers read the room's
#: files, see `trigger`). Between moves the manager taps a conflict's side (m80: every scenario, the
#: seed's choice; `"sides": False` would make one type instead, and none does), else taps by MOVE_ON
#: or types `go_on`, and types his signature when the handover is accepted. `after` changes the
#: rules once a move has fired.
SCENARIOS: dict[str, dict[str, Any]] = {
    "straight": {
        "about": "Today's walk: Order picking to the certificate.",
        "expected": "passes: closed, 0 tool errors nemo did not mark as a refusal (a refused "
                    "call is "
        "a reading note), no call that raised inside its tool, a gap only where the method "
        "needs one, RPO <24 h",
        # t139 (14_nemo_check's ruling (b)): order picking, whose interview states 'RPO <24 h (CSB
        # ERP
        # Marschkamp)' (l.74); the record's own path derives <24 h
        "activities": ["order-picking"],
        "moves": [
            {"when": "start", "say": "ask_critical"},
            {"when": "start", "pick": True},
            {"when": "stage3", "say": "conflicts"},
        ],
    },
    "each-activity": {
        "about": "Picks each of the four activities in turn and walks it to the signature.",
        "expected": "four dead ends at stage 2",
        "activities": "all",
        "moves": [{"when": "start", "pick": True}, {"when": "stage3", "say": "conflicts"}],
    },
    "dispute": {
        "about": "At the handover (stage 5), disputes the RTO with an exact new value and adds a "
        "reservation in words; then signs if the tool lets him.",
        "expected": "no way back",
        # t71b: an activity whose MTPD is a single duration (24 h on the seed since t139,
        # 14_nemo_check's
        # ruling 4), so his exact 2 h is tested inside it without a band MTPD in the way (before t74
        # the referee read a band by its lower edge; since t74 the inside-MTPD check reads its upper
        # edge)
        "activities": ["incident-and-problem-management"],
        "moves": [
            {"when": "start", "pick": True},
            {"when": "stage3", "say": "conflicts"},
            {"when": "stage5", "say": "dispute_rto"},
            {"when": "next", "say": "reservation"},
        ],
        # once he has asked for two hours he does not tap the recovery gap away, and he insists
        "after": {"dispute_rto": {"go_on": "insist", "never": [r"recovery gap"]}},
    },
    "asks": {
        "about": "Mid-stage 3: asks what a term means, what the guidance says about RPO, and to "
        "see the grid again (typed, then the “Show the grid” tap under the answer, t115); "
        "then carries on to the signature.",
        "expected": "dropped links, grid scrolled away (machine ids are measured, not gated: "
                    "tinst)",
        "activities": ["incident-and-problem-management"],
        "moves": [
            {"when": "start", "pick": True},
            {"when": "stage3", "say": "conflicts"},
            {"when": "stage3_decided", "say": "term"},
            {"when": "next", "say": "guidance"},
            {"when": "next", "say": "grid"},
            {"when": "offered", "tap": core.SHOW_GRID},
        ],
    },
    "probe-state": {
        "about": "Straight after the record is saved (stage 4 accepted), asks which is most "
        "critical, which are finished, and whether Order picking has a record; then signs.",
        "expected": "answers composed by the model",
        "activities": ["incident-and-problem-management"],
        "moves": [
            {"when": "start", "pick": True},
            {"when": "stage3", "say": "conflicts"},
            {"when": "record_saved", "say": "critical"},
            {"when": "next", "say": "finished"},
            {"when": "next", "say": "packing"},
        ],
    },
    "refused": {
        "about": "Signs Incident and problem management, then asks to reopen it, twice, in "
                 "different words.",
        "expected": "retry offered as a choice",
        "activities": ["incident-and-problem-management"],
        "moves": [
            {"when": "start", "pick": True},
            {"when": "stage3", "say": "conflicts"},
            {"when": "closed", "say": "reopen_1"},
            {"when": "next", "say": "reopen_2"},
        ],
    },
    "new-activity": {
        "about": "Asks for Cleaning, which the files don't list, answers nemo's interview at "
                 "stage 2, "
        "and walks it to the signature. Twice, one fresh room each: typed (he asks for it in "
        "words, and taps 'Another activity…' only if nothing added it) and tap (he taps "
        "'Another activity…' and types the name).",
        "expected": "a refusal and a steer to a filed activity (M4, M1)",
        "activities": ["Cleaning"],
        "routes": ["typed", "tap"],
        "moves": [{"when": "stage3", "say": "conflicts"}],
    },
    "rpo-choice": {
        "about": "Walks Order picking; before step 3 closes he taps 'Change RPO' and types <1 h, "
                 "tighter "
        "than the <24 h the register derives (t139, 14_nemo_check's ruling (b): the method's "
        "tightest word, where the owner's decision of 2026-09-18 said 0 h, a figure the new "
        "vocabulary has no word for). Then signs. His <1 h must be in the signed record and "
        "the certificate (t71).",
        "expected": "the derivation replaces his <1 h (t71's finding)",
        "activities": ["order-picking"],
        "moves": [
            {"when": "start", "pick": True},
            {"when": "stage3", "say": "conflicts"},
            {"when": "offered", "tap": "Change RPO"},
            {"when": "next", "say": "rpo_value"},
        ],
        # m80: once he has typed his RPO, no tap of nemo's that names an RPO is pressed but the one
        # that keeps his ("Keep RPO <1 h"): not "Use the register's RPO …", not "Record RPO …" (a
        # model's figure over his), not "Accept RPO …" or "No RPO on the record". Where only such a
        # tap is offered he types `go_on`, as before t80, and his <1 h stands (93's live proof).
        "after": {"rpo_value": {"never": [r"^(?!Keep RPO\b).*\bRPO\b"]}},
    },
    "taps": {
        "about": "Walks Incident and problem management to the signature, tapping wherever a tap "
                 "moves "
        "him on, and at each "
        "conflict one of the side taps offered, the seed's choice. Every tap rendered is read "
        "back from the turns file and matched against nemo's tap set for that turn (t73); "
        "every figure, side or score tap made is held to what the room's files record after "
        "it (t73b).",
        "expected": "the model writes the taps: a phantom activity, a phantom move, 'Sign with "
                    "…' (M2, M3)",
        "activities": ["incident-and-problem-management"],
        "moves": [{"when": "start", "pick": True}],
    },
}


# ── reading the room's files ──────────────────────────────────────────────────────────────────
def _json(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text())  # type: ignore[no-any-return]  # a JSON object
    except (OSError, ValueError):
        return {}


def bia_path(folder: Path, activity: str | None = None) -> Path:
    """Where this activity's BIA record is (t235: one per activity, `walk.record_file`); with no
    activity named, the one landed last in the room, which is the walk a verdict is about."""
    if activity is not None:
        return folder / walk.record_file(activity)
    landed = sorted(folder.glob(f"output/*/{walk.RECORD_NAME}"), key=lambda p: p.stat().st_mtime_ns)
    return landed[-1] if landed else folder / "output" / walk.RECORD_NAME


def bia_record(folder: Path, activity: str | None = None) -> dict[str, Any]:
    """The record at `bia_path`, or {} where there is none."""
    return _json(bia_path(folder, activity))


def record_figures(folder: Path, activity: str) -> dict[str, Any]:
    """The figures the record holds for this activity: the saved record, or the one the run is
    carrying to stage 4 (the record-to-be the stage-4 card is drawn from). Empty before that."""
    rec = bia_record(folder, activity)
    if rec and str(rec.get("dept", "")).lower() == activity.lower():
        a = (rec.get("activities") or [{}])[0]
        return {"MTPD": a.get("mtpd"), "RTO": a.get("recovery_target"), "RPO": a.get("rpo"),
                "gap": bool(a.get("recovery_gap_flagged")), "from": walk.record_file(activity)}
    run = _json(folder / walk.run_file(activity))
    acts = run.get("activities") or []
    if acts and (run.get("stage") or 0) >= walk.STAGE_3:
        ev = {e.get("label"): e.get("value") for e in acts[0].get("evidence") or []}
        return {"MTPD": ev.get("MTPD"), "RTO": ev.get("RTO"), "RPO": ev.get("RPO"),
                "from": walk.run_file(activity)}
    return {}


def carried(folder: Path, state: dict[str, Any]) -> dict[str, Any]:
    """t73b: the record-to-be as the room's files hold it now, per draft activity id (its MTPD,
    RTO, RPO, gap flag and grid), and the side each decision took. Built by `core.build_proposal`
    from the state file, the register and the method, which is what the stage-3 record is made
    of, so a tap's named value can be held to it after the tap. Empty before a draft is settled."""
    draft = state.get("draft") or {}
    if not draft.get("activities"):
        return {"carries": {}, "decided": {}, "gaps": {}}
    method = _json(folder / walk.METHOD)
    out = {}
    for d, a in zip(draft["activities"],
                    core.build_proposal(draft, state, method, folder)["activities"], strict=False):
        meta = {m["label"]: m for m in a["evidence_meta"]}
        out[d["id"]] = {**{k: (meta.get(k) or {}).get("value") for k in ("MTPD", "RTO", "RPO")},
                        "gap": bool((meta.get("RTO") or {}).get("gap")), "grid": a["impact_grid"]}
    decisions = state.get("decisions") or {}
    # fix 1: a gap is held to the RTO item's own decision: which conflict wrote it there (`by`)
    return {"carries": out, "decided": {k: d.get("side") for k, d in decisions.items()},
            "gaps": {k: d.get("by") or d.get("decision") for k, d in decisions.items()
                     if "gap" in str(d.get("value") or "").lower()}}


def decision_values(state: dict[str, Any]) -> dict[str, list[Any]]:
    """t71: each decision in the state file as [decision, side, value] (and its scores, if any)."""
    return {
        k: [d.get("decision"), d.get("side"), d.get("value")]
        + ([d["scores"]] if d.get("scores") else [])
        for k, d in (state.get("decisions") or {}).items()
    }


def view(folder: Path, activity: str) -> dict[str, Any]:
    """What the files say about this walk right now. `stage` is the last stage answered."""
    run = _json(folder / walk.run_file(activity))
    state = core.load_state(folder, activity)
    rec = bia_record(folder, activity)
    return {"stage": run.get("stage") or 0, "status": run.get("status"),
            "closed": run.get("status") == walk.CLOSED,
            "record": bool(rec) and str(rec.get("dept", "")).lower() == activity.lower(),
            "decisions": len(state.get("decisions") or {}),
            # t139 (151's rule, S6): the run's own decisions; the seed ships one run per process at
            # stage 1 with none (ADR-0011), and such a run is not a walk under way
            # why: walk takes DECISIONS from nemo.record; reading it there is a code edit
            "run_decisions": len(run.get(walk.DECISIONS) or []),  # type: ignore[attr-defined]
            # t71: nemo waits for a reservation in his words; and every decision as it stands
            # why: walk takes UNNAMED from nemo.record; reading it there is a code edit
            "naming": walk._last_decision(run).get("naming") == walk.UNNAMED,  # type: ignore[attr-defined]
            # t71b: the reservations nemo holds, word for word (the run's, a reopen's carried ones)
            "reservations": [words for _, words in fidelity.reservations(run)],
            "decision_values": decision_values(state),
            "figures": record_figures(folder, activity),
            **carried(folder, state),
            "added": core.added_names(folder),
            "runs": sorted(p.name for p in (folder / "output/.bia-runs").glob("*.json"))}


def owner_on_file(folder: Path, activity: str) -> str:
    """Whom he signs for: OWNERS for a filed activity; for one he added (t72), the owner the
    record-to-be holds (the run's own activity), read from the files."""
    if activity in OWNERS:
        return OWNERS[activity]
    rec = bia_record(folder, activity)
    if str(rec.get("dept", "")).lower() == activity.lower():
        return str((rec.get("activities") or [{}])[0].get("owner") or "")
    run = _json(folder / walk.run_file(activity))
    return str(((run.get("activities") or [{}])[0]).get("owner_name") or "")


def room_state(folder: Path, activities: list[str]) -> dict[str, dict[str, bool]]:
    """Per activity, from the files: has a record (saved, or signed), and is closed (signed)."""
    out = {}
    for a in activities:
        rec = bia_record(folder, a)
        run = _json(folder / walk.run_file(a))
        saved = (bool(rec) and str(rec.get("dept", "")).lower() == a.lower()) or \
            (run.get("stage") or 0) >= walk.STAGE_4
        out[a] = {"record": saved, "closed": run.get("status") == walk.CLOSED}
    return out


def trigger(when: str, v: dict[str, Any], fired_last_turn: bool) -> bool:
    """Whether a move's trigger holds, from the files (`v`) — never from what the model said."""
    # why: the view's values come from the files (Any); each trigger is a bool
    return {  # type: ignore[no-any-return]
        "start": True,
        "next": fired_last_turn,  # the turn straight after the last move
        "stage3": v["stage"] == walk.STAGE_2,  # stage 2 answered: stage 3 is open
        "stage3_decided": v["stage"] == walk.STAGE_2 and v["decisions"] >= 1,
        "record_saved": v["record"] and not v["closed"],
        "stage5": v["stage"] == walk.STAGE_4 and not v["closed"],  # record accepted: the handover
        "closed": v["closed"],
    }[when]


# ── the tap rule ──────────────────────────────────────────────────────────────────────────────
#: t96 fix 1 (I1): a risk-register row's tap reads "Keep: <the row's text>"; the row's text is the
#: register's words (HR's row names Cutting), not a choice of another activity, so only the
#: "Keep:" part is read for another activity's name.
RISK_ROW = re.compile(r"^(?:Keep|Drop):(?= )")


def names_other(option: str, activity: str, activities: list[str] | None = None) -> bool:
    """Whether an option names an activity other than his. t155: the room's own activities when
    the caller knows them (`activities`), read as the scorer reads them (`_named`), his own name
    held out first so a name inside it never counts; else the ones `ALIASES` lists."""
    option = m.group(0) if (m := RISK_ROW.match(option)) else option
    for rx in _names([activity]):
        option = rx.sub(" ", option)
    return bool(_named(option, [a for a in (activities or list(ALIASES)) if a != activity]))


def choose_tap(options: list[str], activity: str, never: list[str],
               activities: list[str] | None = None) -> tuple[str | None, str]:
    """(option to tap, why) or (None, why not). Order of `options` never changes the answer."""
    allowed = [o for o in options if not any(re.search(n, o, re.I) for n in never)
               and not names_other(o, activity, activities)]
    for label, pattern in MOVE_ON:
        hits = sorted(o for o in allowed if re.search(pattern, o, re.I))
        if len(hits) == 1:
            return hits[0], f"tap: {label}"
        if len(hits) > 1:
            return None, f"ambiguous ({label}: {len(hits)} options)"
    return None, "no option to move on"


#: A conflict's side as nemo draws it (`core._side_entries`, t63's short tap; t477: who said it and
#: its figure, "Plant Manager says MTPD >168 h", or "Plant Manager (no figure)", two alike told
#: apart by "(2)"; t482 r2: "Plant Manager's impact scores give MTPD 168 h"). nemo's own label
#: shapes (`core.SIDE_SAYS`, `core.SIDE_GRID`, `core.SIDE_VIEW`), never the model's.
SIDE = re.compile("^(?:" + "|".join(
    re.escape(shape).replace(re.escape("{who}"), ".+").replace(re.escape("{figure}"), ".+")
    for shape in (core.SIDE_SAYS, core.SIDE_GRID, core.SIDE_VIEW)) + r")(?: \(\d+\))?$")


def choose_side(options: list[str], activity: str, never: list[str], seed: Any,
                activities: list[str] | None = None) -> str | None:
    """t73b: the side tap he makes, by the scenario's seeded random choice among the side taps
    offered. The options are sorted first and the choice is seeded by the seed and that sorted set,
    so their order never changes it (not positional); it reads neither the model's text nor its
    recommendation, and never prefers the method's rule or the side the record already holds."""
    sides = sorted(o for o in options if SIDE.match(o) and not names_other(o, activity, activities)
                   and not any(re.search(n, o, re.I) for n in never))
    if not sides:
        return None
    return random.Random(f"{seed}:{activity}:{'|'.join(sides)}").choice(sides)


def pick_tap(options: list[str], activity: str) -> str | None:
    """The option that names the chosen activity, if exactly one does."""
    hits = [o for o in options if any(re.search(rf"\b{re.escape(w)}\b", o, re.I)
                                      for w in ALIASES.get(activity, [activity.lower()]))]
    return hits[0] if len(hits) == 1 else None


def choose_paraphrases(rng: random.Random) -> dict[str, str]:
    return {key: rng.choice(options) for key, options in sorted(LINES.items())}


# ── the driver ────────────────────────────────────────────────────────────────────────────────
class Driver:
    """One walk of one activity: says the opener, then decides each manager turn from the files."""

    def __init__(self, sc: dict[str, Any], activity: str, chosen: dict[str, str],
                 folder: Path | None = None, route: str | None = None, seed: Any = None) -> None:
        self.sc, self.activity, self.chosen, self.seed = sc, activity, chosen, seed
        self.folder, self.route = folder, route
        self.moves = list(sc["moves"])
        self.fired: list[str] = []
        self.fired_last = False
        self.go_on, self.never = "go_on", list(NEVER)
        self.progress: tuple[Any, ...] | None
        self.stall, self.progress = 0, None
        #: t72: how far he got towards adding the activity (asked in words, tapped, typed the name)
        self.new_steps: list[str] = []
        #: t312: he tapped "Another activity…" to reach his activity, and types its name next
        self.naming = False

    def line(self, key: str) -> str:
        owner = (
            owner_on_file(self.folder, self.activity)
            if self.folder
            else OWNERS.get(self.activity, "")
        )
        return self.chosen[key].format(activity=self.activity, owner=owner)

    def _say(self, key: str, how: str, why: str) -> tuple[str, str, str]:
        self.fired.append(key)
        self.fired_last = True
        return (core.ANOTHER if key == "another" else self.line(key)), how, why

    def _new_activity(self, v: dict[str, Any], options: list[str]) -> tuple[str, str, str] | None:
        """Ticket 72: until the room lists an activity he added, he gets it added. Typed route: he
        asks in words once; if nothing added it, he taps "Another activity…". Tap route: he taps
        it. After the tap he types the name. Read from the files and the taps offered, never from
        what the model said."""
        if v.get("added"):
            return None
        if self.route == "typed" and "ask_new" not in self.new_steps:
            self.new_steps.append("ask_new")
            return self._say(
                "ask_new", "typed", "script: ask_new (asks for an activity the files don't list)"
            )
        if self.new_steps and self.new_steps[-1] == "another":
            self.new_steps.append("new_name")
            return self._say("new_name", "typed", "new: types the name nemo asked for")
        if core.ANOTHER in options:
            self.new_steps.append("another")
            return self._say("another", "tapped", f"new: taps {core.ANOTHER}")
        return None

    def next(
        self, v: dict[str, Any], options: list[str], reply: str = ""
    ) -> tuple[str, str, str] | None:
        """(what he says, typed|tapped, why) — or None when the walk is over."""
        iv = v.get("interview") or {}
        if iv and not iv.get("done"):  # t72: nemo's interview is under way; he answers it, in order
            n = int(iv.get("answered") or 0)
            key = INTERVIEW_ANSWERS[min(n, len(INTERVIEW_ANSWERS) - 1)]
            self.fired_last = False
            self.fired.append(key)
            return self.line(key), "typed", f"interview: answer {n + 1}"
        if self.naming:
            self.naming = False
            return self.activity, "typed", "pick: types its name, as nemo asked"
        if self.route:
            fired_last, self.fired_last = self.fired_last, False
            said = self._new_activity(v, options)
            if said:
                return said
            self.fired_last = fired_last
        pending = self.moves[0] if self.moves else None
        if "pick" in self.fired and not (v["stage"] and v.get("run_decisions", 1)) \
                and not v["closed"]:
            # t96: the greeting draws no taps, so his pick is typed first; when nemo then shows the
            # activity pick (the model called list_activities on his line), he taps his activity
            if tap := pick_tap(options, self.activity):
                self.fired_last = True
                return tap, "tapped", "pick: the option naming it, after asking in words"
            if core.ANOTHER in options and not self.route:
                # t312: the card offers the core processes alone; the rest he reaches by name
                self.fired_last = self.naming = True
                return core.ANOTHER, "tapped", "pick: his activity is not on the card"
        if v["closed"] and (pending is None or pending["when"] not in ("closed", "next")):
            return None
        if v.get("naming") and any(m.get("say") == "reservation" for m in self.sc["moves"]):
            # t71: nemo's walk waits for the reservation in his words (its run file says so), and a
            # scenario that reserves something types it, word for word, as the line it has for it
            self.fired_last = False
            return self._say("reservation", "typed", "reservation: nemo waits for it in his words")
        if walk.RESERVED in options and "reservation" in self.fired \
                and self.line("reservation") not in (v.get("reservations") or []):
            # t71b: he has typed a reservation and nemo holds no naming of it yet: he takes nemo's
            # reserving route before any "endorse", and types it again when nemo waits for it
            self.fired_last = False
            self.fired.append(f"tap:{walk.RESERVED}")
            return walk.RESERVED, "tapped", "reservation pending: taps the reserving answer first"
        if pending and pending.get("tap"):
            # t71: a tap move fires as soon as nemo offers that tap; until then he walks on
            if pending["tap"] in options:
                self.moves.pop(0)
                self.fired.append(f"tap:{pending['tap']}")
                self.fired_last = True
                return pending["tap"], "tapped", f"script: taps {pending['tap']}"
            pending = None
        fired_last, self.fired_last = self.fired_last, False
        if pending and trigger(pending["when"], v, fired_last):
            self.moves.pop(0)
            self.fired_last = True
            key = "pick" if pending.get("pick") else pending["say"]
            self.fired.append(key)
            if key in (self.sc.get("after") or {}):
                rule = self.sc["after"][key]
                self.go_on = rule.get("go_on", self.go_on)
                self.never += rule.get("never", [])
            if pending.get("pick"):
                tap = pick_tap(options, self.activity)
                return (tap, "tapped", "pick: the option naming it") if tap else \
                    (self.line("pick"), "typed", "pick: typed, no option names it")
            return self.line(key), "typed", f"script: {key}"
        if v["closed"]:
            return None
        if v["stage"] == walk.STAGE_5 and v["status"] == walk.REVIEWED:
            # t134: after his name and role, nemo asks who he is signing as and draws the two taps
            # from the record's own names. He is the deputy the files make him (SIGNS_FOR), so he
            # takes "on behalf of" where it is offered; the choice is a tap and never his prose.
            behalf = [o for o in options if o.startswith(walk.SIGN_ON_BEHALF.format(owner=""))]
            if behalf:
                return behalf[0], "tapped", "signature: on behalf of the owner the record names"
            if walk.SIGN_AS_THE_OWNER in options:
                return walk.SIGN_AS_THE_OWNER, "tapped", "signature: as the owner"
            return (
                self.line("signature"),
                "typed",
                "signature: the handover is accepted (typed, never tapped)",
            )
        if v["stage"] >= walk.STAGE_4 and ASKS_FOR_NAME.search(reply or ""):
            # a manager asked for his name once the record is saved gives it, whatever the files say
            return self.line("signature"), "typed", "signature: nemo asked him to type his name"
        if self.sc.get("sides", True):  # t73b; m80 made it every scenario's default
            # t155: the room's own activities, so an option naming any of them is another's
            acts = walk.processes(self.folder) if self.folder else None
            side = choose_side(options, self.activity, self.never, self.seed, acts)
            if side:
                return side, "tapped", "side: the seed's choice among the side taps offered"
        tap, why = choose_tap(options, self.activity, self.never,
                              walk.processes(self.folder) if self.folder else None)
        if tap:
            return tap, "tapped", why
        return self.line(self.go_on), "typed", f"continuation: {why}"

    def stalled(self, v: dict[str, Any], scripted: bool) -> bool:
        """True once the files have not moved for STALL of his turns (scripted lines not
        counted)."""
        key = (v["stage"], v["status"], v["decisions"], v["record"], tuple(v.get("added") or ()))
        if key != self.progress:
            self.progress, self.stall = key, 0
            return False
        if not scripted:
            self.stall += 1
        return self.stall >= STALL


def _truncate(result: Any, name: str) -> Any:
    if name == "ask_guidance":
        return result
    text = json.dumps(result, default=str, ensure_ascii=False)
    return result if len(text) <= 2000 else text[:2000] + "…"


def run_walk(sc_name: str, sc: dict[str, Any], activity: str, folder: Path, model: str,
             chosen: dict[str, str], turns_file: Path, cap: int = TURN_CAP,
             route: str | None = None, seed: Any = None) -> dict[str, Any]:
    """Drive one activity to its end. Every turn goes to `turns_file` the moment it ends.

    `route` (t72, `new-activity`): the activity is one he adds; which one is read from the room's
    list of added activities once it is there (the name as the room holds it)."""
    events: list[tuple[str, Any]] = []
    session = core.Session(folder, model, lambda kind, data: events.append((kind, data)))
    driver = Driver(sc, activity, chosen, folder, route, seed)
    turns: list[dict[str, Any]] = []
    said, how, why = OPENER, "opener", "the app's opener"
    started = time.time()
    end = "turn cap"
    for n in range(cap):
        before = view(folder, activity)
        mark = len(events)
        error = None
        # a tap carries the server's mark when the server drew it, as the app sends it (t72)
        marked = how == "tapped" and session.last_pick
        shown = session.shown(said) if how == "tapped" else said  # t132, as the app writes it
        try:
            reply, options, cards = session.turn(said, how=how, pick=marked)
        except Exception as e:  # noqa: BLE001 — a lane that fails after its retries ends the walk
            reply, options, cards, error = "", [], [], f"{type(e).__name__}: {e}"
        reply, cards = session.drawn_turn(reply, cards)  # t107: as he reads it (`core.NAMED`)
        if route and core.added_names(folder):  # the activity he added, as the room holds it
            activity = driver.activity = core.added_names(folder)[-1]
        after = view(folder, activity)
        new = events[mark:]
        timing: dict[str, Any] = next((d for k, d in new if k == "turn"), {})
        tools = [d for k, d in new if k == "tool"]
        turn = {
            "scenario": sc_name,
            "activity": activity,
            "n": n,
            "how": how,
            "why": why,
            **({"route": route} if route else {}),
            "key": driver.fired[-1] if driver.fired_last and driver.fired else None,
            "said": said,
            **({"shown": shown} if shown != said else {}),
            # t132: the id the session minted for this turn, which his acts on it name
            "turn_id": session.turn_id,
            "reply": reply,
            "options": options,
            "cards": cards,
            # t107: reply and cards are as he read them, each term named at its first use
            "text_is": core.NAMED,
            "model_seconds": timing.get("model_seconds"),
            "tool_seconds": timing.get("tool_seconds"),
            # ticket 69 fix 1: the rest of the wait, named as unaccounted (PROTOTYPE_core)
            "unaccounted_seconds": timing.get("unaccounted_seconds"),
            # ticket 82: and where those seconds actually went. Taken from `core.ACCOUNTING_KEYS`
            # rather than retyped, because this dict is built key by key and a field left out here
            # never reaches the run file the ceiling is read from — silently, and looking like a
            # turn that had nothing to report.
            **{k: timing.get(k) for k in core.ACCOUNTING_KEYS},
            # 608 Amend 1: and 600's one shape, the six keys every turn's record carries
            **{k: timing.get(k) for k in core.TURN_SHAPE},
            "seconds": timing.get("seconds"),
            "tools": [t["name"] for t in tools],
            # tinst: with nemo's refusal mark (`core.WRONG_CALL`, `core.STANDING`; None unmarked),
            # and fix 1: the exception's type when the call raised inside the tool (None otherwise)
            "tool_errors": [
                {
                    "name": t["name"],
                    "error": t["result"]["error"],
                    "refusal": t["result"].get("refusal"),
                    "crash": t["result"].get("crash"),
                }
                for t in tools
                if isinstance(t["result"], dict) and "error" in t["result"]
            ],
            "tool_calls": [
                {"name": t["name"], "args": t["args"], "result": _truncate(t["result"], t["name"])}
                for t in tools
            ],
            "before": {k: v for k, v in before.items() if k != "runs"},
            "after": {k: v for k, v in after.items() if k != "runs"},
            "runs_after": after["runs"],
            "state_after": room_state(folder, list(OWNERS)),
            # the exception that ended this turn, if any. `error` here, but `failed` on the core's
            # own turn line for the same event (ticket 69), and the two must not be made to match:
            # tests/test_refusals.py:301 pins the core to exactly two lines containing "error",
            # its two tool-result constructors, so in the core an "error" is a tool result and
            # nothing else. PROTOTYPE_clocks._failed reads both spellings.
            "error": error,
            # ticket 67: a turn that met a standing refusal — the rendered say, the next taps, and
            # that the model's turn was ended there. None on every other turn. Logging only.
            "refusal": timing.get("refusal"),
            # ticket 67 fix 1: on a signed activity the taps are the server's; the model's own
            # OPTIONS for that turn, kept here for reading. None on every other turn. Logging only.
            "signed_taps": timing.get("signed_taps"),
            # ticket 72: a turn the server answered itself (asked for a name, an interview
            # question), and the interview's state after it. None on every other turn.
            "server": timing.get("server"),
            "interview": timing.get("interview"),
            "marked": marked,
            # ticket 73: nemo's tap set for this turn, drawn from data, with the call each tap
            # stands for, and the OPTIONS the model wrote (logged, never rendered)
            "taps": timing.get("taps"),
            "elapsed": round(time.time() - started, 1),
            # ticket 69: when the turn ended (epoch), and on a walk's last line how the walk ended
            "at": round(time.time(), 1),
        }
        turns.append(turn)
        ended = None
        try:
            if error:
                ended = "error"
            elif (nxt := driver.next({**after, "interview": timing.get("interview")}, options,
                                     reply)) is None:
                ended = "signed" if after["closed"] else "abandoned"
            else:
                said, how, why = nxt
                if driver.stalled(
                    after, scripted=why.startswith(("script", "pick", "interview", "new"))
                ):
                    ended = "abandoned"
                elif n == cap - 1:
                    ended = "turn cap"
        finally:
            turn["end"] = ended
            # written as it happens: a crashed walk keeps its turns. t109: through nemo's one
            # writer,
            # to the room's turn file with every call, and to this batch file without them
            core.record_turn(folder, turn, index=turns_file)
        if ended:
            end = ended
            break
    final = view(folder, activity)
    return {"activity": activity, "room": folder.name, "end": end, "turns": turns,
            "wall_clock_s": round(time.time() - started, 1), "final": final,
            "stage_reached": final["stage"],
            # the stage the walk was waiting on when it ended (the run file holds the last one
            # answered)
            "waiting_at": None if final["closed"] else final["stage"] + 1,
            "moves_fired": driver.fired,
            "moves_unfired": [m.get("say", "pick") for m in driver.moves],
            **({"route": route, "new_steps": driver.new_steps,
                "add_activity_called": any(t["name"] == "add_activity" for u in turns
                                           for t in u["tool_calls"])} if route else {}),
            "typed": sum(t["how"] == "typed" for t in turns),
            "taps": sum(t["how"] == "tapped" for t in turns)}


# ── scoring: the room's files and the rendered transcript, read by this code ──────────────────
_NUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "eight": "8",
        "twelve": "12", "twenty-four": "24"}
_DUR = (r"(?:(?:[<≤~]|under|below|less than)\s*)?(?:\d+|one|two|three|four|five|six|eight|twelve)"
        r"(?:\s*[–—-]\s*\d+)?\s*(?:h|hrs?|hours?|min(?:utes)?|days?|weeks?|wk)\b(?:\s*\([^)\n]{1,40}\))?"
        r"|n/a\s*\(physical\)")
#: A label, then at most two short words or connectors ("MTPD anchor at 8 h", "RPO is **4 h**"),
#: then the figure. Nothing across a sentence end, a dash or a comma.
_FIG = re.compile(
    r"\b(MTPD|RTO|RPO|recovery target)\b[*_ ]*"
    r"(?:(?:(?!under\b|below\b|less\b)[a-z]+|:|=)[*_ ]+){0,2}[*_ ]*("
    + _DUR
    + ")",
    re.I,
)


def norm(value: Any) -> str:
    """A figure as a comparable string: '< 4 h' == 'under 4 hours' == '<4h'."""
    v = str(value or "").lower().replace("*", "")
    v = re.sub(r"[–—]", "-", v)
    v = re.sub(r"\b(under|below|less than)\b", "<", v)
    for word, digit in _NUM.items():
        v = re.sub(rf"\b{word}\b", digit, v)
    v = re.sub(r"\b(hours?|hrs?)\b", "h", v)
    v = re.sub(r"\bweeks?\b", "week", v)
    return re.sub(r"\s+", "", v)


def seen_figures(text: str) -> list[tuple[str, str, str]]:
    """(label, normalised value, raw) for each MTPD/RTO/RPO a rendered text states."""
    out = []
    for m in _FIG.finditer(text):
        label = "RTO" if m.group(1).lower() in ("rto", "recovery target") else m.group(1).upper()
        out.append((label, norm(m.group(2)), m.group(0)))
    return out


def _same(seen: str, allowed: set[str]) -> bool:
    """Equal, or equal before any bracketed note on either side ("4 h (ERP order data)" == "4 h",
    "0–4 h (method rule)" == "0–4 h"). The RPO vocabulary's figures all differ before the
    bracket."""
    head = seen.split("(")[0]
    return any(seen == a or head == a.split("(")[0] for a in allowed if a)


def draft_pool(activity: str, model: str, folder: Path) -> dict[str, set[str]]:
    """Every figure the prepared draft, the manager's decisions and last cycle's BIA hold."""
    pool: dict[str, set[str]] = {"MTPD": set(), "RTO": set(), "RPO": set()}
    # an added activity's draft is the room's own (t72); a filed one's is the shared one
    draft = _json(folder / core.drafting.ROOM_DRAFTS / f"{core.slug(activity)}.{model}.json") or \
        _json(DRAFTS / f"{core.slug(activity)}.{model}.json") or \
        _json(FIXTURES / f"{core.slug(activity)}.{model}.json")
    for a in draft.get("activities") or []:
        for f in ("mtpd", "rto", "rpo"):
            pool[f.upper()].add(norm((a.get(f) or {}).get("value")))
    for c in draft.get("conflicts") or []:
        for s in c.get("sides") or []:
            imp = s.get("implies") or {}
            if isinstance(imp, dict) and imp.get("item_id"):
                pool.setdefault(str(imp["item_id"]).rsplit(".", 1)[-1].upper(), set()).add(
                    norm(imp.get("value"))
                )
    for item, d in (core.load_state(folder, activity).get("decisions") or {}).items():
        field = item.rsplit(".", 1)[-1].upper()
        if field in pool and d.get("value"):
            pool[field].add(norm(d["value"]))
    for label, value in prior_pool(folder, activity).items():
        pool[label] |= value
    return pool


def prior_pool(folder: Path, activity: str) -> dict[str, set[str]]:
    scope = (core.load_state(folder, activity).get("scope") or {}).get("activities") or [activity]
    prior = core.last_year(folder, scope[0])
    out: dict[str, set[str]] = {"MTPD": set(), "RTO": set(), "RPO": set()}
    for label, value in (prior.get("figures") or {}).items():
        if label in out:
            out[label] |= {norm(v) for v in re.findall(_DUR, str(value), re.I)} | {norm(value)}
    return out


def _own_text(text: str, activity: str, activities: list[str], card: bool) -> str:
    """The part of a rendered text that speaks about `activity`: a card headed with another activity
    is dropped whole, and so is a sentence that names only other activities. Their figures have no
    record of this walk to be compared with."""
    others = [a for a in activities if a != activity]
    if card:
        head = text.split("\n", 1)[0]
        return "" if _named(head, others) and not _named(head, [activity]) else text
    # t71: a sentence naming no activity speaks about the one the sentence before it named ("No —
    # Packing … is not started. Its MTPD 24 h …"), so it goes with that sentence
    keep, last = [], None
    for s in re.split(r"(?<=[.!?\n])\s+", text):
        named = _named(s, activities)
        last = named or last
        about = named or last or [activity]
        if activity in about or not any(a in others for a in about):
            keep.append(s)
    return " ".join(keep)


def score_values(turns: list[dict[str, Any]], pool: dict[str, set[str]],
                 prior: dict[str, set[str]], activities: list[str] | None = None) -> dict[str, Any]:
    """Every MTPD/RTO/RPO the manager saw (reply and cards) against the files.

    Rule: once the run carries a record (stage 3 closed) the figure must equal the record's own
    for that label, or last cycle's (the card compares against it); before that, any figure in the
    prepared draft, the manager's decisions or last cycle's BIA. Figures said about another
    activity (a sentence or card naming only it) are not this walk's to check, and are skipped."""
    checked, wrong = 0, []
    for t in turns:
        figs = t["after"].get("figures") or {}
        texts = [_own_text(t["reply"], t["activity"], activities or [], False)] + \
            [_own_text(c, t["activity"], activities or [], True) for c in t["cards"]]
        for text in texts:
            for label, value, raw in seen_figures(text):
                checked += 1
                allowed = (
                    ({norm(figs.get(label))} | prior[label]) if figs.get(label) else pool[label]
                )
                if not _same(value, allowed):
                    wrong.append({"turn": t["n"], "activity": t["activity"], "label": label,
                                  "seen": raw, "files": sorted(allowed)})
    return {"checked": checked, "not_in_files": wrong}


def score_decisions(folder: Path, activity: str) -> dict[str, Any]:
    """The manager's decisions (output/.proto/<activity>.json) against the signed record.

    Rule: a changed MTPD/RTO/RPO must be the record's figure (a value naming a recovery gap must
    show as `recovery_gap_flagged`); a changed score must be the record's grid cell; a settled
    conflict's chosen side must appear in the record's open items. Accepts of a proposal are not
    checked: they change nothing the record could show differently."""
    state = core.load_state(folder, activity)
    rec = bia_record(folder, activity)
    if not rec or str(rec.get("dept", "")).lower() != activity.lower():
        return {"checked": 0, "missing": [], "note": "no record for this activity"}
    a = (rec.get("activities") or [{}])[0]
    fields = {"mtpd": "mtpd", "rto": "recovery_target", "rpo": "rpo"}
    conflicts = {c["id"]: c for c in (state.get("draft") or {}).get("conflicts") or []}
    items = " ".join(str(i) for i in rec.get("open_items") or [])
    checked, missing = 0, []
    for item, d in (state.get("decisions") or {}).items():
        field = item.rsplit(".", 1)[-1]
        if item in conflicts and isinstance(d.get("side"), int):
            checked += 1
            sides = conflicts[item].get("sides") or []
            claim = sides[d["side"]].get("claim", "") if d["side"] < len(sides) else ""
            if not claim or claim not in items:
                missing.append({"decision": item, "wanted": claim, "record": "not in open_items"})
        elif d.get("decision") == "change" and field in fields and d.get("value"):
            checked += 1
            if "gap" in str(d["value"]).lower():
                if not a.get("recovery_gap_flagged"):
                    missing.append(
                        {"decision": item, "wanted": d["value"], "record": "no gap flag"}
                    )
            elif norm(a.get(fields[field])) != norm(d["value"]):
                missing.append(
                    {"decision": item, "wanted": d["value"], "record": a.get(fields[field])}
                )
        elif d.get("decision") == "change" and d.get("scores"):
            grid = (a.get("impact_grid") or {}).get(field) or {}
            for h, v in d["scores"].items():
                checked += 1
                if str(grid.get(h)) != str(v):
                    missing.append({"decision": f"{item}@{h}", "wanted": v, "record": grid.get(h)})
    return {"checked": checked, "missing": missing}


_URL = re.compile(r"https?://[^\s)\]>\"'*`]+")


def urls(text: str) -> list[str]:
    return [u.rstrip(".,;:") for u in _URL.findall(text or "")]


def _strings(x: Any) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _strings(v)]
    if isinstance(x, list):
        return [s for v in x for s in _strings(v)]
    return []


#: the published guidance corpus: a served citation's url must be the one it holds for that chunk id
CHUNKS_JSON = Path(
    os.environ.get("NEMO_GUIDANCE_CHUNKS") or "/opt/apps/ai4bcm-guidance/data/chunks.json"
)
#: t65: a citation as the ai4bcm chat renders it (the skin's own rendering, checked in the reply)
guidance_line = core.source_line


def _corpus_urls() -> dict[str, str]:
    return {c["id"]: c["url"] for c in json.loads(CHUNKS_JSON.read_text())}


def score_guidance(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rule: every link an ask_guidance result served appears whole in that turn's reply. t65: where
    the result carries its citations, each must appear as the chat's numbered line, and its url must
    be chunks.json's for the same chunk id (`not_the_corpus` lists the ids that are not)."""
    out = []
    for t in turns:
        calls = [c for c in t["tool_calls"] if c["name"] == "ask_guidance"]
        if not calls:
            continue
        served = [u for c in calls for s in _strings(c["result"]) for u in urls(s)]
        shown = set(urls(t["reply"]))
        row: dict[str, Any] = {"turn": t["n"], "served": sorted(set(served)),
                               "missing": sorted({u for u in served if u not in shown})}
        cites = [
            list(c["result"].get("citations") or []) for c in calls if isinstance(c["result"], dict)
        ]
        if any(cites):
            corpus = _corpus_urls()
            row["missing"] = sorted({x["url"] for per in cites for n, x in enumerate(per, start=1)
                                     if guidance_line(n, x) not in t["reply"]})
            row["not_the_corpus"] = sorted({x["id"] for per in cites for x in per
                                            if corpus.get(x["id"]) != x["url"]})
        out.append(row)
    return out


#: t115: the turn his tap on "Show the grid" made, as the driver keys a tap move
GRID_TAP_KEY = f"tap:{core.SHOW_GRID}"


def score_grid_again(turns: list[dict[str, Any]], method: dict[str, Any],
                     reference: dict[str, Any] | None) -> dict[str, Any] | None:
    """t115: "asks" asks for the grid in two steps. His typed request prints no grid; the answer
    must carry the "Show the grid" tap. His tap on it prints the grid, and that turn's table is what
    `grid_shown` reads. None when the scenario never asked."""
    typed = next((t for t in turns if t["key"] == "grid"), None)
    if typed is None:
        return None
    tapped = next((t for t in turns if t["key"] == GRID_TAP_KEY), None)
    shown = grid_shown(
        "\n".join([tapped["reply"], *tapped["cards"]]) if tapped else "", method, reference
    )
    tap = core.SHOW_GRID in typed["options"]
    return {
        **shown,
        "shown": bool(shown["shown"] and tap),
        "tap_under_answer": tap,
        "tapped": tapped is not None,
    }


def grid_shown(
    text: str, method: dict[str, Any], reference: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Rule: the grid is shown when every one of the method's categories has a row (a line starting
    with the first word of its name, then its scores) and all its time horizons are named; and,
    when the room's grid is known (`reference`, {category id: {horizon: score}}), every row's first
    scores equal the room's, in horizon order."""
    hors = list(method.get("time_horizons") or [])
    flat = norm(text).replace("1week", "1w")
    h = sum(1 for x in hors if norm(x).replace("1week", "1w") in flat)
    rows, wrong = {}, []
    for s in method.get("scenarios") or []:
        word = re.split(r"[ /&]", s["name"])[0]
        # a row: the category's first word or an abbreviation of it (three letters or more: "Fin",
        # "Cust", "Env") at the start of a line or after "·", ";", ":" or "|", followed by one score
        # per horizon before the next "·", ";" or line end. Prose that names the category is not a
        # row.
        head = rf"(?:^|[\n·;:|]|[-•*]\s)[\s*_|]*({re.escape(word[:3])}[a-z]*)\b([^\n·;]*)"
        scores = None
        for m in re.finditer(head, text, re.I):
            if not word.lower().startswith(m.group(1).lower()):
                continue
            found = [int(n) for n in re.findall(r"(?<![\d.–-])[1-5](?![\d–-]|\.\d)",
                                                re.sub(r"\d+\s*h\b|1 ?week", "", m.group(2)))]
            if len(found) >= len(hors):
                scores = found
                break
        if scores is None:
            continue
        rows[s["id"]] = scores
        want = [(reference or {}).get(s["id"], {}).get(x) for x in hors]
        if reference and s["id"] in reference and scores[:len(hors)] != want:
            wrong.append({"category": s["id"], "shown": scores, "room": want})
    missing = [s["id"] for s in method.get("scenarios") or [] if s["id"] not in rows]
    return {"rows": len(rows), "missing_rows": missing, "horizons": h, "wrong_rows": wrong,
            "shown": not missing and h == len(hors) and not wrong}


def load_machine_ids(path: Path = MACHINE_IDS) -> list[str]:
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def find_machine_ids(text: str, ids: list[str]) -> list[str]:
    """Entries of the instrument's own list found in a text. `re:` entries are regexes; others
    are literal, case-sensitive, and must stand alone (not inside a longer identifier)."""
    found = []
    for entry in ids:
        if entry.startswith("re:"):
            pattern = entry[3:]
        else:  # a word edge only where the entry itself begins or ends with a word character
            pattern = (
                (r"(?<![A-Za-z0-9_])" if re.match(r"\w", entry) else "")
                + re.escape(entry)
                + (r"(?![A-Za-z0-9_])" if re.search(r"\w$", entry) else "")
            )
        found += re.findall(pattern, text)
    return sorted(set(str(f) if not isinstance(f, tuple) else f[0] for f in found))


def score_machine_ids(turns: list[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    """Machine identifiers the manager saw, per turn, kept apart by who wrote the text (tinst):
    `nemo` (its cards, the taps offered, and the reply on a turn nemo answered without the model's
    words: a server turn, or a standing refusal's `say`) and `model` (the reply otherwise). A
    measurement (ticket 64); no verdict gates on it."""
    out = []
    for t in turns:
        nemo_said = bool(t.get("server") or t.get("refusal"))  # fix 1: nemo wrote this reply
        row = {"nemo": find_machine_ids("\n".join([*t["cards"], *t["options"],
                                                    *([t["reply"]] if nemo_said else [])]), ids),
               "model": [] if nemo_said else find_machine_ids(t["reply"], ids)}
        if any(row.values()):
            out.append({"turn": t["n"], "activity": t["activity"], **row})
    return out


_REOPEN = re.compile(r"re-?open|go back|back (in)?to (step|stage)|amend|undo|change the rto|"
                     r"retry|try again|unsign", re.I)

#: The rule for an option offered after a refusal (fix 4: one gate for every exemption).
#: 1. Strike out negated phrases ("don't reopen", "no new cycle"). What is left PROPOSES a move if
#: it
#:    names an action word, a real tool move, or the refused move -- unless the option OPENS by
#:    asking about something: a why/what-does/is question ("Why can't it reopen?", "What does a new
#:    cycle mean?"), or "explain" / "tell me why" with or without a "?" ("Explain new cycle",
#:    "Explain why you can't start a new cycle"; orchestrator's ruling, round 5). There its words
#: are
#:    the subject, not a request. "Why not ..." / "Why don't we ..." and "What about/if ..." are
#:    suggestions, not about-openers ("why don't" negates nothing); an option that opens with the
#:    action ("Start a new cycle, please explain") proposes it.
#: 2. A proposing option is what it proposes: the refused move again (repeat), a new cycle
#:    (phantom, however it is named or phrased), a real tool move (known), anything else (phantom).
#: 3. An option proposing nothing is exempt if it is a question or a decline ("Is it final?",
#:    "Explain the refusal", "We're done", "Don't reopen it"), and phantom otherwise: matching
#:    nothing is the only net for a fabrication nobody foresaw.
#: The owner's ruling: a false positive harms as much as a missed phantom.
_ACTION = re.compile(
    r"\b(start|open|create|begin|restart|redo|amend|change|edit|reopen|undo)\w*|\bnew\b", re.I
)
_NEGATED = re.compile(r"(?<!why )\b(don['’]?t|do not|never|no)\s+(\w+\s+)?\w+", re.I)
_ABOUT = re.compile(
    r"^\s*((why\b(?!\s+(not|don['’]?t)\b)|what\s+(does|do|is|are)\b|what['’]s\b).*\?\s*$"
    r"|(explain|tell me why)\b)",
    re.I,
)
_INQUIRY = re.compile(r"\?\s*$|^\s*(explain|tell me)\b", re.I)
_DECLINE = re.compile(r"\bleave it\b|\bkeep it\b|we.?re done|that.?s all|\bstop here\b|"
                      r"\bnothing else\b", re.I)
_NEW_CYCLE = re.compile(r"\bnew\b.{0,20}\bcycle\b|\bcycle\b.{0,20}\bnew\b", re.I)


def classify_offer(
    option: str, repeat_rx: re.Pattern[str], activities: list[str] | None = None
) -> str:
    """'exempt', 'repeat', 'known' or 'phantom', by the rule written above."""
    text = _NEGATED.sub(" ", option)
    proposes = not _ABOUT.search(option) and bool(
        _ACTION.search(text) or repeat_rx.search(text) or names_a_tool_move(text, activities))
    if not proposes:
        declines = _DECLINE.search(option) or _NEGATED.search(option)
        return "exempt" if _INQUIRY.search(option) or declines else "phantom"
    if repeat_rx.search(text):
        return "repeat"
    if _NEW_CYCLE.search(text):
        return "phantom"
    return "known" if names_a_tool_move(text, activities) else "phantom"


#: Outside the tool set (13_nemo/t70 fix): an offered option after a refusal proposing a move no
#: prototype tool can make — the seed-7013/seed-4040 "Start a new cycle" / "Open a new cycle", a
#: fabricated capability. The set of real moves is `core.TOOLS` itself, never a hand-kept list of
#: phrases, so a tool added, renamed or dropped there changes what this allows without touching this
#: table. Reading an option's words to tell which move (if any) it names is still unavoidable — the
#: options are text — so this is the one explicit, small, commented mapping that does that reading:
#: tool name (asserted against `core.TOOLS` below) -> words in an option that plausibly ask for it.
_TOOL_NAMES = {t["function"]["name"] for t in core.TOOLS}
_OPTION_NAMES_TOOL: list[tuple[str, str]] = [
    ("reopen", r"re-?open|go back|back to step|amend|undo|unsign"),
    ("sign", r"\bsign(ing)?\b"),
    ("confirm_interviews", r"confirm.*interview"),
    ("accept_all_open", r"accept all|keep (them )?all"),
    # t76: leaving a conflict unresolved is a decision like taking a side, and recording that the
    # arrangements can meet the target is its own tool: neither is a fabricated capability
    ("decide", r"\baccept\b|\breject\b|change (the|this|a) figure|leave (it |this )?unresolved"),
    ("close_recovery_gap", r"arrangements .*meet the (recovery )?target|close the (recovery )?gap"),
    ("answer_step", r"\bendorse\b|needs discussion"),
    ("ask_guidance", r"\bguidance\b"),
    ("get_evidence", r"\bconflicts?\b|\bproposals?\b|\bevidence\b"),
    # "Show me the record" (seed 8001, fix 1) / "How do I see the record?" (fix 3): a bare request
    # to see it, not just "signed record".
    ("get_step", r"certificate|\bstatus\b|where.*stands?|signed record|"
                r"(show|see) (me )?(the )?record\b"),
    ("list_room_files", r"\bfiles\b"),
    ("read_room_file", r"\bread\b.*\bfile\b"),
    # orchestrator's ruling, round 0: moving to or opening another activity is a tool move
    # (list_activities, or get_step on that activity), never a phantom one.
    ("list_activities", r"\bactivities\b|another activit|other activit"),
    ("set_scope", r"\bscope\b"),
]
assert all(name in _TOOL_NAMES for name, _ in _OPTION_NAMES_TOOL), (
    "a tool name drifted from core.TOOLS"
)


#: Moving to or opening one of the room's own activities is list_activities/get_step, a real tool
#: move (orchestrator's ruling, round 0, sharpened in round 2 with real activity names: "Move to
#: Cutting", "Open Packing / Labelling", "Go to Maintenance"). The activity words come from
#: `ALIASES` — the same data the driver itself uses to recognise an activity in an option
#: (`names_other`, `pick_tap`) and that in turn names the five activities `list_activities` /
#: `walk.processes` returns — never a second, hand-kept list of activity names.
_MOVE_WORD = re.compile(r"\b(move to|open|go to|switch to|walk|start on)\b", re.I)
_ACTIVITY_WORD = re.compile(
    r"\b(" + "|".join(re.escape(w) for words in ALIASES.values() for w in words) + r")\b", re.I)
#: A new cycle is never this, however it is named: `classify_offer` checks `_NEW_CYCLE` first.


def moves_to_an_activity(option: str, activities: list[str] | None = None) -> bool:
    """t155: with the room's own activities (`activities`) an activity is any of them, read as the
    scorer reads them (`_named`); without, the words `ALIASES` lists."""
    named = bool(_named(option, activities)) if activities else bool(_ACTIVITY_WORD.search(option))
    return bool(_MOVE_WORD.search(option)) and named


def names_a_tool_move(option: str, activities: list[str] | None = None) -> bool:
    return moves_to_an_activity(option, activities) or any(re.search(rx, option, re.I)
                                                           for _, rx in _OPTION_NAMES_TOOL)


def score_refusals(
    turns: list[dict[str, Any]], activities: list[str] | None = None
) -> list[dict[str, Any]]:
    """Refusal turns, the taps offered after them that repeat the refused move, and any offered
    option that proposes a move outside the prototype's tool set.

    A refusal turn, from the files: the manager asked to go back (`reopen_*` lines) while the run
    file said closed, or a tool the turn called answered with an error. Every option offered in
    that turn's reply or any later one is read by `classify_offer` (the rule is written above it).
    For a closed run the refused move is going back (re-open, go back, amend, undo, retry); for any
    other refused tool, a retry of that tool (retry, try again, its name)."""
    out = []
    for i, t in enumerate(turns):
        refused = []
        if (t["key"] or "").startswith("reopen") and t["before"]["closed"]:
            refused.append(("reopen", _REOPEN))
        for e in t["tool_errors"]:
            refused.append((e["name"], _REOPEN if e["name"] == "reopen" else
                            re.compile(rf"retry|try again|{re.escape(e['name'])}", re.I)))
        for move, rx in refused:
            later = [
                {"turn": u["n"], "option": o}
                for u in turns[i:]
                if u["activity"] == t["activity"]
                for o in u["options"]
            ]
            offers = [o for o in later if classify_offer(o["option"], rx, activities) == "repeat"]
            phantom = [o for o in later if classify_offer(o["option"], rx, activities) == "phantom"]
            out.append({"turn": t["n"], "activity": t["activity"], "refused": move,
                        "offered_again": offers, "phantom": phantom})
    return out


_CLAUSE = re.compile(r"(?<=[.;!?\n])\s+|\s+(?:but|while|whereas)\s+|\s+[—–-]\s+|,\s+(?=and\b)")
_NEG = re.compile(
    r"\b(no|not|none|nothing|never|without|neither|nor|yet to|outstanding|missing|lacks?|"
    r"lacking)\b|n't",
    re.I,
)
_FINISHED = re.compile(r"\b(finished|signed|done|complete|completed|closed|signed off)\b", re.I)
_RECORD = re.compile(r"\b(records?|saved|accepted|written)\b", re.I)  # t71 fix 1: "no records yet"
_PRIOR = re.compile(r"\bprior\b|\blast (year|cycle)\b|\b2025\b", re.I)
#: The parts of a clause: at a comma, an "and" or a "but" ("a record accepted and not signed": the
#: "not" is the signature's). A part is the scope of a negation and of the state word beside it.
#: t155: never inside one of the room's activity names ("Incident and problem management" is one
#: name): `_parts` holds the names whole, longest first, before it cuts.
_PART = re.compile(r",\s+|\s+(?:and|but)\s+")
#: t155: a count of activities, however many the room has ("all twenty", "none of the 20")
_COUNT = (
    r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
    r"sixteen|seventeen|eighteen|nineteen|twenty|\d+)"
)
_OTHERS = re.compile(r"\b(others?|rest|remaining)\b", re.I)
#: fix 5: a group that is every activity, and can be scored as every activity (the apart ones taken
#: out). "every" and "each" are not: "it carries the record status for every activity" is about the
#: sheet (4545), and scoring it would red a correct answer.
_ALL = re.compile(rf"\b(all (the )?{_COUNT}( activities)?|all (the )?activities|"
                  rf"none of the ({_COUNT} )?activities|no activity)\b", re.I)
#: a quantifier in a part with no subject ("nothing else", "any activity", "every"): whose state it
#: is can't be settled, so the part is never given the last subject
_QUANT = re.compile(r"\b(else|any|anything|anyone|nobody|no one|every|each|all|none)\b", re.I)
#: "unlike X", "except X": X, and every bare name after it, is set apart and given nothing
_APART = re.compile(r"\b(unlike|except( for)?|apart from|other than|save for)\b", re.I)
#: a relative pronoun opening a part points at a noun this rule does not parse
_RELATIVE = re.compile(r"^\W*(which|who|whose)\b", re.I)
#: fix 5: the words a bare subject may hold besides the activities' names: it waits for its state
_BARE = re.compile(r"\b(the|a|an|and|or|both|like|as well as|only|other|others|rest|remaining|"
                   rf"{_COUNT})\b|'s\b|[^\w\s]", re.I)
#: t71: a line of nemo's sheet ("- **Packing / Labelling** · …") is about its own activity only.
_SHEET_LINE = re.compile(r"^\s*-\s+\*\*(.+?)\*\*")


def _aliases(a: str) -> list[str]:
    """t155: an activity is always named by its own name as well as by any plain alias; the room's
    slug and its prose are one name ("incident-and-problem-management", "Incident and problem
    management"), because `_name` reads a space and a hyphen alike."""
    return [*ALIASES.get(a, []), a.lower()]


def _name(w: str) -> re.Pattern[str]:
    """One name, whole, in any case, a space and a hyphen read alike ("by-product", "by
    product")."""
    return re.compile(
        r"\b" + r"[\s-]+".join(re.escape(t) for t in re.split(r"[\s-]+", w.strip())) + r"\b", re.I
    )


def _names(activities: list[str]) -> list[re.Pattern[str]]:
    """Every name of the room's activities, longest first, so a name inside another never wins."""
    return [
        _name(w)
        for w in sorted({w for a in activities for w in _aliases(a)}, key=len, reverse=True)
    ]


def _named(text: str, activities: list[str]) -> list[str]:
    return [a for a in activities if any(_name(w).search(text) for w in _aliases(a))]


def _bare(part: str, activities: list[str]) -> bool:
    """Whether a part holds nothing but activity names, "the others", articles, "and / or / both /
    like / as well as" and punctuation (fix 5: an allow-list, never a verb list)."""
    rest = part
    for rx in _names(activities):
        rest = rx.sub(" ", rest)
    return not _BARE.sub(" ", rest).strip()


def _parts(clause: str, activities: list[str]) -> list[str]:
    """t155: a clause cut at `_PART`, never inside one of the room's activity names, longest
    first."""
    held: list[str] = []

    def hold(m: re.Match[str]) -> str:
        held.append(m.group(0))
        return f"\x00{len(held) - 1}\x00"

    for rx in _names(activities):
        clause = rx.sub(hold, clause)
    return [
        re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], p) for p in _PART.split(clause)
    ]


def state_claims(text: str, activities: list[str], subject: str | None = None,
                 unscored: list[str] | None = None) -> list[dict[str, Any]]:
    """What a reply says about each activity's record and signature (t71 fixes 4 and 5: one rule,
    not a patch per sentence the model wrote).

    The rule:
    - **A clause** is a sentence cut at ";", a dash, "but", "while", "whereas" and ", and". A clause
      about last cycle (prior, last year, 2025) is skipped. **A part** is a clause cut at a comma,
      "and" or "but", never inside an activity's name (t155: "Incident and problem management").
    - **A part's subjects** are every activity it names; "the others / the rest" as the complement
      of every activity named anywhere in the answer (and the question's own activity); "all five",
      "all twenty", "all activities", "none of the activities", "no activity" as every activity the
      room has, however many (t155).
    - **Set apart:** "unlike", "except", "apart from" set apart the activity or group after them,
      and every bare part after that, up to the next part that is not bare. What is set apart is
      given nothing.
    - **A part's state** is each state word in it (a record: saved, accepted, written, record; a
      signature: signed, finished, done, closed), negated when the part carries a negation.
    - **Only a bare subject waits.** A part holding nothing but names, "the others", articles, "and
      / or / both / like / as well as" and punctuation ("Packing", "like Slaughter") holds its
      subjects for the next part, so "Packing, like Slaughter, has a record" is one claim about
      both. Any other word makes a part stand alone ("The others seem idle", "Maintenance: nothing
      yet"): it is scored on its own state words, or says nothing, and its subjects never join
      another part's.
    - **A part naming no subject** speaks of the subjects waiting, else of the ones the sentence
      spoke of last, else of the question's activity (`subject`). One opening with "which / who",
      or carrying a quantifier ("nothing else", "any", "every", "none", "nobody"), is unscored and
      never given the last subject. A bare "nothing" is not such a quantifier: "nothing has been
      written yet" speaks of the activity in focus.
    - **Unscored, never guessed:** a part whose subjects can't be settled ("every", "each", "none"
      of a group nobody named, or "the others" in an answer naming no activity), and a clause saying
      both yes and no about one activity's one state. Each such clause that carries a state word is
      listed in `unscored`.
    - nemo's sheet line ("- **Packing / Labelling** · …") speaks of its own activity only."""
    claims: list[dict[str, Any]] = []
    everyone = [a for a in activities if _named(text or "", [a])]
    if subject and subject not in everyone:
        everyone.append(subject)
    others = [a for a in activities if a not in everyone] if everyone else None

    def skip(clause: str) -> None:
        if unscored is not None and (_RECORD.search(clause) or _FINISHED.search(clause)) \
                and clause.strip() not in unscored:
            unscored.append(clause.strip())

    def states(part: str) -> list[tuple[str, bool]]:
        neg = bool(_NEG.search(part))
        return [(about, not neg) for about, rx in (("closed", _FINISHED), ("record", _RECORD))
                if rx.search(part)]

    def group(words: str) -> list[str] | None:
        """The subjects a part names; None when it names a group that can't be settled."""
        found = list(_named(words, activities))
        if _OTHERS.search(words):
            if others is None:
                return None
            found += [a for a in others if a not in found]
        elif _ALL.search(words):
            found = list(activities)
        return found

    for sentence in re.split(r"(?<=[.!?\n])\s+", text or ""):
        last: list[str] | None = [subject] if subject else []
        line = _SHEET_LINE.match(sentence)
        own = [line.group(1)] if line and line.group(1) in activities else None
        for clause in _CLAUSE.split(sentence):
            if not clause or not clause.strip():
                continue
            if _PRIOR.search(clause):
                last = own or _named(clause, activities) or last
                continue
            found: list[dict[str, Any]] = []
            waiting: list[str] = []
            apart: set[str] = set()
            setting_apart = False
            unsettled = False
            for part in _parts(clause, activities):
                if own is not None:
                    found += [
                        {"activity": a, "about": b, "says": s} for a in own for b, s in states(part)
                    ]
                    continue
                if setting_apart and _bare(part, activities):
                    apart |= set(group(part) or [])  # the list after "except" goes on
                    continue
                setting_apart = False
                cut = _APART.search(part)
                head = part
                if cut:
                    head, tail = part[:cut.start()], part[cut.end():]
                    apart |= set(group(tail) or [])
                    setting_apart = _bare(tail, activities)
                    if not head.strip():
                        continue  # "unlike Slaughter", "Except for Slaughter": nothing said yet
                said = states(part)
                subjects = group(head)
                if subjects is None:
                    unsettled, waiting = True, []
                    continue
                if subjects and not said and _bare(head, activities):
                    waiting += [a for a in subjects if a not in waiting]
                    continue  # a bare subject, waiting for its state
                if subjects:
                    who: list[str] | None = waiting + [a for a in subjects if a not in waiting]
                elif waiting:
                    who = waiting
                elif _RELATIVE.search(head) or _QUANT.search(head):
                    who = None  # never the last subject
                else:
                    who = last
                waiting = []
                if who is None:
                    unsettled = unsettled or bool(said)
                    continue
                last = who
                found += [{"activity": a, "about": b, "says": s} for a in who for b, s in said]
            found = [c for c in found if c["activity"] not in apart]
            both = {(c["activity"], c["about"]) for c in found if not c["says"]} & \
                {(c["activity"], c["about"]) for c in found if c["says"]}
            if unsettled or both:
                skip(clause)
            claims += [{**c, "clause": clause.strip()} for c in found
                       if (c["activity"], c["about"]) not in both]
    return claims


def score_state(turns: list[dict[str, Any]], activities: list[str]) -> list[dict[str, Any]]:
    """The probe answers (`critical`, `finished`, `packing`) against the room's files at that turn.

    Rules: every claim a probe answer makes about an activity's record or signature must match the
    files. `finished` must also name every closed activity as finished, or, when none is, say so
    (a negation and no positive claim). `packing` must make a claim about Order picking's record."""
    out = []
    for t in turns:
        if t["key"] not in ("critical", "finished", "packing"):
            continue
        truth = t["state_after"]  # the files as they stood when he read the answer
        unscored: list[str] = []
        claims = state_claims(t["reply"], activities,
                              "order-picking" if t["key"] == "packing" else None, unscored)
        wrong = [c for c in claims if truth.get(c["activity"], {}).get(c["about"]) != c["says"]]
        problems = [f"{c['activity']}: says {c['about']}={c['says']}, files say "
                    f"{truth.get(c['activity'], {}).get(c['about'])}" for c in wrong]
        if t["key"] == "finished":
            closed = {a for a, s in truth.items() if s["closed"]}
            said = {c["activity"] for c in claims if c["about"] == "closed" and c["says"]}
            if closed - said:
                problems.append(f"not named as finished: {sorted(closed - said)}")
            if not closed and not said and not _NEG.search(t["reply"]):
                problems.append("does not say that nothing is finished")
        if t["key"] == "packing" and not any(
            c["activity"] == "order-picking" and c["about"] == "record" for c in claims
        ):
            problems.append("makes no claim about Order picking's record")
        out.append({"turn": t["n"], "question": t["key"], "truth": truth, "claims": claims,
                    "ok": not problems, "problems": problems, "unscored": unscored})
    return out


def tripwire(turns: list[dict[str, Any]], activities: list[str]) -> list[str]:
    """Every sentence the model wrote that names an activity next to a state word. Log only."""
    words = re.compile(r"\b(draft|record|signed|saved|done|finished)\b", re.I)
    out = []
    for t in turns:
        for sentence in re.split(r"(?<=[.!?\n])\s+", t["reply"] or ""):
            if words.search(sentence) and _named(sentence, activities):
                out.append(f"[{t['activity']} · turn {t['n']}] {sentence.strip()}")
    return out


def clocks(walks: list[dict[str, Any]]) -> dict[str, Any]:
    """Ticket 69 item 2: three clocks, reported apart and never summed together."""
    per_turn = [
        t["model_seconds"] for w in walks for t in w["turns"] if t["model_seconds"] is not None
    ]
    return {
        "model_latency": {
            "what": "seconds inside the model lane per turn (the skin's own clock)",
            "median_s": round(statistics.median(per_turn), 1) if per_turn else None,
            "worst_s": max(per_turn) if per_turn else None,
            "turns": len(per_turn),
        },
        "scripted_elapsed": {
            "what": "this run's own wall-clock; the script answers instantly, so this "
            "proves nothing about how long a person takes",
            "seconds": round(sum(w["wall_clock_s"] for w in walks), 1),
        },
        "human": None,
        "human_note": "only a person walking it on a phone fills this in (ticket 69)",
    }


# ── verdicts: one rule per scenario, for the "Turned green by" column ────────────────────────
def _record(folder: Path) -> dict[str, Any]:
    rec = bia_record(folder)
    return (rec.get("activities") or [{}])[0] if rec else {}


def _saved_result(result: Any) -> dict[str, Any]:
    """A tool result as a turns file saved it (`_truncate`): the dict, or, where its JSON was cut
    at 2000 characters, the top-level keys written before the cut: each with its value when the
    value was written whole, None when the cut fell inside it."""
    if isinstance(result, dict):
        return result
    out: dict[str, Any]
    text, out, i = str(result), {}, 1
    if not text.startswith("{"):
        return out
    try:
        while text.startswith('"', i):
            # why: json.decoder.scanstring exists at runtime, and typeshed leaves it out
            key, i = json.decoder.scanstring(text, i + 1)  # type: ignore[attr-defined]
            out[key] = None  # fix 1: the key was written, whatever becomes of its value
            out[key], i = json.JSONDecoder().raw_decode(
                # why: no match raises AttributeError, which the except below takes as the end
                text, re.compile(r"\s*:\s*").match(text, i).end()  # type: ignore[union-attr]
            )
            # why: no match raises AttributeError, which the except below takes as the end
            i = re.compile(r"\s*,\s*").match(text, i).end()  # type: ignore[union-attr]
    except (ValueError, AttributeError):  # the cut, or the object's end
        pass
    return out


def tool_errors(turn: dict[str, Any]) -> list[dict[str, Any]]:
    """The turn's tool errors, each with nemo's refusal mark: `refusal` is `core.WRONG_CALL` or
    `core.STANDING`, or None for an error nemo did not mark (tinst); and `crash`, the exception's
    type when the call raised inside the tool (fix 1). A turns file written before tinst has no
    `refusal` on its errors; there the mark is read off the same call's saved result, never off
    the error's words. Fix 1: the k-th error is the k-th call whose saved result carries an error
    (the order `run_walk` wrote both in), and only when those calls pair one to one with the
    errors, name for name; otherwise no old error gets a mark. A result cut before its mark was
    written has none to read. An error with no mark counts unmarked. Before fix 1 no turns file
    says whether a call raised, so an old file's errors carry no crash."""
    calls = [(c["name"], r) for c in turn.get("tool_calls") or []
             if "error" in (r := _saved_result(c["result"]))]
    errors = turn["tool_errors"]
    paired = len(calls) == len(errors) and all(
        n == e["name"] for (n, _), e in zip(calls, errors, strict=False)
    )
    marks = [r.get("refusal") for _, r in calls] if paired else [None] * len(errors)
    return [
        e if "refusal" in e else {**e, "refusal": m} for e, m in zip(errors, marks, strict=False)
    ]


def verdict_straight(w: dict[str, Any], folder: Path) -> tuple[bool, str]:
    # Green = the run file is closed, no tool result in the walk carried an error nemo did not
    # mark as a refusal (tinst: a refused call, `core.wrong_call` or a standing refusal, is nemo
    # keeping the rule out of the model's hands; it is counted and named here, never red), no
    # call raised inside its tool (fix 1: `crash`, a nemo bug; named here, and red), the
    # record flags a recovery gap exactly where the method needs one (t74: its own target outside
    # its own MTPD, a band read at its upper edge, `core.needs_gap`), and its RPO reads
    # "<24 h", what order picking's record derives on its own path (t139: 14_nemo_check's ruling
    # (b);
    # its interview states 'RPO <24 h (CSB ERP Marschkamp)', l.74). A turns file from before fix 1
    # cannot say a call raised: no crash red.
    a = _record(folder)
    errors = [(t["n"], e) for t in w["turns"] for e in tool_errors(t)]
    unmarked = sum(not e["refusal"] for _, e in errors)
    crashes = [
        f"turn {n} {e['name']} ({e['crash']}): {e['error']}" for n, e in errors if e.get("crash")
    ]
    refused = [f"turn {n} {e['name']} ({e['refusal']}): {e['error']}" for n, e in errors
               if e["refusal"] and not e.get("crash")]
    flagged = bool(a.get("recovery_gap_flagged"))
    needed = core.needs_gap(a, bia_record(folder).get("method"))
    ok = w["final"]["closed"] and unmarked == 0 and not crashes and flagged is needed \
        and a.get("rpo") == "<24 h"
    return ok, (f"closed={w['final']['closed']}, unmarked tool errors={unmarked}, "
                + (f"tool crashes={len(crashes)}: {'; '.join(crashes)}, " if crashes else "") +
                f"gap flagged={flagged}, gap needed={needed} (target {a.get('recovery_target')!r}, "
                f"MTPD {a.get('mtpd')!r}), RPO={a.get('rpo')!r}, end={w['end']}; "
                f"refused calls={len(refused)} (a reading note, never red)"
                + (f": {'; '.join(refused)}" if refused else ""))


def verdict_each(walks: list[dict[str, Any]]) -> tuple[bool, str]:
    # Green = every one of the five activities' run files is closed.
    closed = [w["activity"] for w in walks if w["final"]["closed"]]
    stuck = [f"{w['activity']} stuck at stage {w['waiting_at']} ({w['end']})" for w in walks
             if not w["final"]["closed"]]
    return len(closed) == len(walks), f"{len(closed)}/{len(walks)} closed" + \
        (f"; not closed: {'; '.join(stuck)}" if stuck else "")


def _certificate(folder: Path) -> str:
    found = (
        sorted((folder / "output").rglob(handover.CERTIFICATE))
        if (folder / "output").is_dir()
        else []
    )
    return found[0].read_text() if found else ""


def is_duration(recorded: Any, want: str) -> bool:
    """Whether a recorded figure is the duration `want`, read by the referee's own parser (minutes),
    so the method's RTO spelling "< 2 h" is the "2 h" he asked for and a wrong reading ("< 4 h", a
    band, the gap word) is not (14_nemo, on 5_Nemo_check's ruling after dispute 9090). The
    spelling's "<" is dropped before reading: the referee reads "< 2 h" as just under 2 h (t130), a
    minute the
    scenario's "the duration he asked for" never meant."""
    got = duration.minutes(str(recorded).strip().lstrip("<")) if recorded else None
    return got is not None and got == duration.minutes(want.strip().lstrip("<"))


def verdict_dispute(w: dict[str, Any], folder: Path) -> tuple[bool, str]:
    # Green (t71) = the run is closed; the signed record's recovery target is the duration he
    # asked for (two hours: "2 h", or the method's "< 2 h", read as durations by `is_duration`)
    # and the certificate states it; every reservation line he typed is in the run file (nemo's
    # record of the walk's reservations, a reopen's carried ones
    # included) word for word, and in the certificate word for word; and every decision the state
    # file held when he disputed, other than the RTO, is as it was.
    a = _record(folder)
    cert = _certificate(folder)
    run = _json(folder / walk.run_file(w["activity"]))
    held = {words for _, words in fidelity.reservations(run)}
    typed = list(dict.fromkeys(t["said"] for t in w["turns"] if t["key"] == "reservation"))
    rto = a.get("recovery_target")
    rto_ok = is_duration(rto, "2 h") and fidelity.says(cert, rto)
    words_ok = bool(typed) and all(x in held for x in typed)
    cert_ok = bool(typed) and all(x in cert for x in typed)
    at = next((t for t in w["turns"] if t["key"] == "dispute_rto"), None)
    before = ((at or {}).get("before") or {}).get("decision_values") or {}
    now = decision_values(core.load_state(folder, w["activity"]))
    moved = sorted(k for k, v in before.items() if not k.endswith(".rto") and now.get(k) != v)
    # t71b: no manager-origin text in the signed record is the model's: each is a line he said or
    # tapped on this walk, or nemo's own (fidelity.his_words, the check nemo runs itself)
    not_his = fidelity.his_words(
        core.load_state(folder, w["activity"]),
        bia_record(folder, w["activity"]),
        run,
        [str(t.get("said") or "") for t in w["turns"]],
    )
    ok = w["final"]["closed"] and rto_ok and words_ok and cert_ok and not moved and at is not None \
        and not not_his
    return ok, (f"closed={w['final']['closed']} (end {w['end']}), record RTO={rto!r} "
                f"(in the certificate: {fidelity.says(cert, rto) if rto else False}), "
                f"his words in the record={words_ok}, in the certificate={cert_ok} "
                f"({len(typed)} reservation line(s) typed), decisions moved besides the RTO: "
                f"{moved or 'none'}, manager-origin text not his: {not_his or 'none'}"
                f"{'' if at else ', the dispute never fired'}")


def verdict_rpo_choice(w: dict[str, Any], folder: Path) -> tuple[bool, str]:
    # Green (t71) = the run is closed; the state file holds his change of the RPO to the value he
    # typed (t139: "<1 h", the new method's tightest word, `LINES["rpo_value"]`; was 0 h); the
    # signed
    # record's RPO is that word; and the certificate states the record's RPO. The register derives
    # <24 h for Order picking, so a derivation that replaced his choice is red.
    a = _record(folder)
    cert = _certificate(folder)
    rpo = a.get("rpo")
    mine = [
        d.get("value")
        for k, d in (core.load_state(folder, w["activity"]).get("decisions") or {}).items()
        if k.endswith(".rpo") and d.get("decision") == "change"
    ]
    typed = set(LINES["rpo_value"])
    chose = any(str(v) in typed for v in mine)
    in_record = rpo in typed
    in_cert = bool(rpo) and f"RPO {rpo}" in cert
    ok = w["final"]["closed"] and chose and in_record and in_cert
    return ok, (
        f"closed={w['final']['closed']} (end {w['end']}), his RPO decision={mine or 'none'}, "
        f"record RPO={rpo!r}, in the certificate={in_cert}"
    )


def verdict_asks(w: dict[str, Any], guidance: list[dict[str, Any]], grid: dict[str, Any] | None,
                 machine: list[dict[str, Any]]) -> tuple[bool, str]:
    # Green = guidance was served at least once and every served link is in the reply whole, none
    # outside the corpus (t65), and the reply to "show me the grid again" shows the grid
    # (grid_shown). The machine identifiers from MACHINE_IDS seen in the walk are
    # published beside it, counted by who wrote the text (`score_machine_ids`), and gate
    # nothing (tinst): ticket 64 made the count a measurement, and nemo's own cards are fixed in
    # the product with a product test (64b).
    served = sum(len(g["served"]) for g in guidance)
    dropped = sum(len(g["missing"]) for g in guidance)
    wrong = sorted({i for g in guidance for i in g.get("not_the_corpus") or []})  # t65
    grid_ok = bool(grid and grid["shown"])
    ok = served > 0 and dropped == 0 and not wrong and grid_ok
    why_grid = (
        ""
        if grid is None
        else (
            f" (rows missing: {grid['missing_rows']}, rows wrong: "
            f"{[w['category'] for w in grid['wrong_rows']]})"
            if not grid_ok
            else ""
        )
    )
    if grid is not None and grid.get("tap_under_answer") is False:  # t115: amendment 1, live
        why_grid += " (no “Show the grid” tap under the typed request)"
    seen = {src: sorted({i for m in machine for i in m[key]})
            for src, key in (("nemo's text", "nemo"), ("the model's reply", "model"))}
    return ok, (
        f"links served {served}, dropped {dropped}"
        + (f", not chunks.json's url: {wrong}" if wrong else "")
        + f"; grid shown again={grid_ok}"
        f"{' (never asked)' if grid is None else why_grid}; machine ids seen (measured, not "
        "gated): "
        + ", ".join(f"{src} {len(i)}" + (f" {i}" if i else "") for src, i in seen.items())
    )


def verdict_probe(
    # why: `figures` is only iterated, so the empty tuple stands for no figures
    state: list[dict[str, Any]], figures: list[dict[str, Any]] = ()  # type: ignore[assignment]
) -> tuple[bool, str]:
    # Green = all three probe questions were asked, every answer's claims about records and
    # signatures match the files (score_state), and no figure an answer states disagrees with the
    # record as it stood (score_values rows on the probe turns, passed in as `figures`).
    asked = {s["question"] for s in state}
    bad = [f"{s['question']}: {'; '.join(s['problems'])}" for s in state if not s["ok"]]
    probe_turns = {s["turn"]: s["question"] for s in state}
    bad += [f"{probe_turns[f['turn']]}: {f['seen']!r} but the record holds {f['files']}"
            for f in figures if f["turn"] in probe_turns]
    missing = {"critical", "finished", "packing"} - asked
    ok = not bad and not missing
    return ok, ("; ".join(bad) or "all answers match the files") + \
        (f"; never asked: {sorted(missing)}" if missing else "")


def verdict_refused(w: dict[str, Any], refusals: list[dict[str, Any]]) -> tuple[bool, str]:
    # Green = the walk was signed, both reopen lines were said after it, no option offered in or
    # after a refusal turn repeats the refused move, and none proposes a move outside the tool set
    # (score_refusals, closed-run rows: `offered_again`, `phantom`). A question ("Why can't it
    # reopen?") is neither (owner's ruling, 2026-09-18).
    rows = [r for r in refusals if r["refused"] == "reopen"]
    offers = [o for r in rows for o in r["offered_again"]]
    phantom = [o for r in rows for o in r["phantom"]]
    asked = sum(
        1 for t in w["turns"] if (t["key"] or "").startswith("reopen") and t["before"]["closed"]
    )
    ok = w["final"]["closed"] and asked == 2 and not offers and not phantom
    return ok, (f"signed={w['final']['closed']}, reopen asked after signing {asked}x, "
                f"offered again as a tap: {[o['option'] for o in offers] or 'never'}, "
                f"offered a move no tool has: {[o['option'] for o in phantom] or 'never'}")


def record_marks(folder: Path) -> list[str]:
    """Every figure in the record without a quote found in its file or a proposal mark (t72), or
    (t171-shape) a no-RPO row the register does not bear out.

    A figure carries a quote when its evidence is a transcript quote found verbatim (nemo's `norm`)
    in the room file it names (t171: a register row's, in the register); it carries a proposal
    mark when its evidence is his act on a turn (t132/t171: `chat_confirmation`, his words and the
    turn's id), or on a record signed before t171 the prototype's `manager_confirmed`."""
    from nemo.text import norm as nemo_norm
    bad = []
    for item in (_record(folder).get("evidence") or []):
        quote, path, kind = item.get("quote") or "", item.get("source_path") or "", item.get("type")
        if kind == core.MANAGER and quote or \
                kind == core.CHAT_CONFIRMATION and item.get("words") and item.get("turn_id"):
            continue
        if (
            kind == core.REGISTER_NO_RPO
        ):  # t171-shape (DRAFT): the register gives it no RPO, read back
            register = (
                json.loads((folder / path).read_text())
                if path and (folder / path).is_file()
                else {}
            )
            named = [x for x in item.get("asset_ids") or []
                     if recovery_point_for(register, x, item.get("activity")) is not None]
            if register and not named:
                continue
        text = (
            (folder / path).read_text(errors="replace")
            if path and (folder / path).is_file()
            else ""
        )
        if not (quote and text and nemo_norm(quote) in nemo_norm(text)):
            bad.append(
                f"{item.get('lens') or item.get('origin')}: {quote[:60]!r} from {path or 'no file'}"
            )
    return bad


def risk_row_quoted(folder: Path, row_id: str) -> str | None:
    """How the signed record quotes one risk-register row (t72b): the evidence item's origin, when
    its quote is that row's line of the room's risk register, word for word; else None."""
    rows = {r["id"]: r for r in core.drafting.risk_rows(folder)}
    row = rows.get(row_id)
    for item in (_record(folder).get("evidence") or []) if row else []:
        # why: `row` is not None here: the loop runs only `if row`
        if item.get("source_path") == row["path"] and item.get("quote") == row["quote"]:  # type: ignore[index]
            return str(item.get("origin") or "quoted")
    return None


def verdict_new(walks: list[dict[str, Any]], folders: list[Path]) -> tuple[bool, str]:
    # Green = on every route, from the room's files: the activity is in the room's list of added
    # activities; the interview nemo held is filed at walk.interview_path and the BIA rests on it;
    # the record is that activity's, and signed (the run file closed); and every figure in the
    # record carries a quote found in its file or a proposal mark (record_marks). How often the
    # model's add_activity fired on the typed route is reported, not scored (t72 addition).
    # t72b: and the record quotes R-HR-01's line of the risk register word for word (by the name
    # rule's floor on the typed route's "HR", by his keep on the card for "Human Resources").
    parts, ok = [], True
    for w, folder in zip(walks, folders, strict=False):
        a = w["activity"]
        added = a in core.added_names(folder)
        filed = (folder / walk.interview_path(a)).is_file() and \
            walk.interview_path(a) in (core.load_state(folder, a).get("interviews") or [])
        rec = bia_record(folder, a)
        mine = str(rec.get("dept", "")).lower() == a.lower()
        unmarked = record_marks(folder) if mine else ["no record"]
        hr_row = risk_row_quoted(folder, "R-HR-01") if mine else None
        green = added and filed and mine and w["final"]["closed"] and not unmarked and bool(hr_row)
        ok = ok and green
        parts.append(
            f"{w.get('route')}: {a!r} added={added}, interview filed={filed}, record={mine}, "
            f"signed={w['final']['closed']} (end {w['end']}), figures without quote or "
            f"mark={unmarked or 'none'}, R-HR-01 quoted={hr_row or False}, "
            f"add_activity called={w.get('add_activity_called')}, "
            f"steps={w.get('new_steps')}"
        )
    return ok, "; ".join(parts)


def score_taps(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Ticket 73, from the turns file alone: every rendered tap against nemo's tap set for its turn.

    Rule: each turn logs nemo's set (`taps.set`, drawn from data) and it equals the taps rendered,
    in order; a rendered tap outside that set is the model's (its OPTIONS line is logged beside it
    as `taps.model_options`); no tap stands for `sign` but the two that say who he signs as (t134:
    the signature itself is still typed, and the choice is his own); and each tap he
    made that stands for a call is that call, alone, in the next turn: the same tool with the same
    arguments (a "Change …" tap: the turn after, with his typed value in the one field it asked).

    t73b: and each tap he made that named a value (`names`: a figure, a side, a score set) named
    what the room's files hold after it (t63: a side tap's value as its conflict card names it, the
    card's entry for the tapped side number, logged with the taps as `taps.card`): the decision's
    side in the state file, and the figure, gap flag or scores in the record-to-be built from those
    files (`carried`, logged in the turn's
    `after`). nemo's output against nemo's output; no model text is read (M13)."""
    unlogged, unequal, model_taps, sign_taps, wrong_calls, calls_checked = [], [], [], [], [], 0
    named_checked, side_taps, not_recorded = 0, 0, []
    for i, t in enumerate(turns):
        log = t.get("taps")
        if log is None:
            unlogged.append(t["n"])
            continue
        if list(t["options"]) != list(log["set"]):
            unequal.append({"turn": t["n"], "rendered": t["options"], "nemo": log["set"]})
        model_taps += [{"turn": t["n"], "tap": o} for o in t["options"] if o not in log["set"]]
        # t134: the only tap that may stand for `sign` is one of the two nemo draws from the
        # record's own names once he has typed his. Everything else about the signature is typed.
        sign_taps += [{"turn": t["n"], "tap": a["label"]} for a in log["actions"]
                      if a.get("tool") == "sign" and not _signs_as(a["label"])]
        nxt = turns[i + 1] if i + 1 < len(turns) else None
        if not nxt or nxt["how"] != "tapped" or nxt["activity"] != t["activity"]:
            continue
        action = next((a for a in log["actions"] if a["label"] == nxt["said"]), None)
        if action is None or action.get("kind") not in ("tool", "ask"):
            continue
        if action.get("names") and "side" in action["names"]:
            # t63 (owner's "Short + card"): a side tap is short; the value it names is on the
            # conflict card drawn with it, the entry under the tapped side's number
            named_checked += 1
            side_taps += 1
            entry = next((e for e in ((log.get("card") or {}).get("sides") or [])
                          if (log.get("card") or {}).get("item") == action["names"]["item"]
                          and e.get("side") == action["names"]["side"]), None)
            not_recorded += (
                _not_recorded({"label": action["label"], "names": entry["names"]}, nxt)
                if entry
                else [
                    {
                        "turn": nxt["n"],
                        "tap": action["label"],
                        "named": "no card entry for this side",
                        "recorded": None,
                    }
                ]
            )
        elif action.get("names"):
            named_checked += 1
            not_recorded += _not_recorded(action, nxt)
        made = [(c["name"], c["args"]) for c in nxt["tool_calls"]]
        if action["kind"] == "ask":
            nxt = turns[i + 2] if i + 2 < len(turns) else None
            if not nxt or nxt["how"] != "typed":
                continue
            made = [(c["name"], c["args"]) for c in nxt["tool_calls"]]
            fixed = {k: v for k, v in (made[0][1] if made else {}).items() if k in action["args"]}
            ok = len(made) == 1 and made[0][0] == action["tool"] and fixed == action["args"]
        else:
            ok = made == [(action["tool"], action["args"])]
        calls_checked += 1
        if not ok:
            wrong_calls.append({"turn": nxt["n"], "tap": action["label"], "made": made,
                                "stands_for": [action.get("tool"), action.get("args")]})
    return {
        "turns": len(turns),
        "unlogged": unlogged,
        "unequal": unequal,
        "model_taps": model_taps,
        "sign_taps": sign_taps,
        "calls_checked": calls_checked,
        "wrong_calls": wrong_calls,
        "named_checked": named_checked,
        "side_taps": side_taps,
        "named_not_recorded": not_recorded,
        "tapped": sum(t["how"] == "tapped" for t in turns),
        "model_options_dropped": sum(
            len((t.get("taps") or {}).get("model_options") or []) for t in turns
        ),
    }


def _not_recorded(action: dict[str, Any], turn: dict[str, Any]) -> list[dict[str, Any]]:
    """Where the files after `turn` hold another value than `action` named (t73b); [] when equal."""
    named, after = action["names"], turn.get("after") or {}
    out = []
    if "side" in named and (after.get("decided") or {}).get(named["item"], "none") != named["side"]:
        out.append({"turn": turn["n"], "tap": action["label"], "named": f"side {named['side']}",
                    "recorded": (after.get("decided") or {}).get(named["item"], "no decision")})
    carries = (after.get("carries") or {}).get(named.get("activity_id"), {})
    if named.get("gap") and "side" in named:
        # fix 1: the RTO item's own decision is the gap this conflict wrote, not a gap carried
        # before
        by = (after.get("gaps") or {}).get(named.get("figure_item"))
        if by != named["item"] or carries.get("gap") is not True:
            out.append(
                {
                    "turn": turn["n"],
                    "tap": action["label"],
                    "named": "recovery gap",
                    "recorded": f"{named.get('figure_item')} decided by {by}, "
                                f"gap={carries.get('gap')}",
                }
            )
    elif named.get("gap") and (named["item"] not in (after.get("decided") or {})
                               or carries.get("gap") is not True):
        out.append({"turn": turn["n"], "tap": action["label"], "named": "recovery gap",
                    "recorded": carries.get(named["field"])})
    elif "value" in named and carries.get(named["field"]) != named["value"]:
        out.append({"turn": turn["n"], "tap": action["label"], "named": named["value"],
                    "recorded": carries.get(named["field"])})
    if "scores" in named and (carries.get("grid") or {}).get(named["lens"]) != named["scores"]:
        out.append({"turn": turn["n"], "tap": action["label"], "named": named["scores"],
                    "recorded": (carries.get("grid") or {}).get(named["lens"])})
    return out


def verdict_taps(w: dict[str, Any], taps: dict[str, Any]) -> tuple[bool, str]:
    # Green = the run is closed (signed), every turn logged nemo's tap set, every turn rendered
    # exactly that set, zero rendered taps are the model's, no tap stands for the signature, and
    # every tap he made dispatched exactly the one call it stands for (score_taps), and (t73b) every
    # figure, side or score tap he made named what the room's files record after it.
    ok = w["final"]["closed"] and not (taps["unlogged"] or taps["unequal"] or taps["model_taps"]
                                       or taps["sign_taps"] or taps["wrong_calls"]
                                       or taps.get("named_not_recorded"))
    return ok, (
        f"closed={w['final']['closed']} (end {w['end']}), turns={taps['turns']}, "
        f"taps made={taps['tapped']}, calls checked={taps['calls_checked']}, "
        f"unlogged={taps['unlogged'] or 'none'}, rendered != nemo's set="
        f"{[u['turn'] for u in taps['unequal']] or 'none'}, model's taps rendered="
        f"{taps['model_taps'] or 'none'}, signature taps={taps['sign_taps'] or 'none'}, "
        f"wrong calls={taps['wrong_calls'] or 'none'}, named taps checked="
        f"{taps.get('named_checked', 0)} (sides {taps.get('side_taps', 0)}), named != recorded="
        f"{taps.get('named_not_recorded') or 'none'}, model OPTIONS dropped="
        f"{taps['model_options_dropped']}"
    )


# ── the run ───────────────────────────────────────────────────────────────────────────────────
def _render(
    sc_name: str, sc: dict[str, Any], walks: list[dict[str, Any]], result: dict[str, Any]
) -> str:
    v = result["verdict"]
    lines = [
        f"# Scenario `{sc_name}` — {sc['about']}",
        "",
        f"Model {result['model']} · seed {result['seed']} · verdict "
        f"**{'GREEN' if v['green'] else 'RED'}**: "
        f"{v['reason']}",
        "",
        f"Expected today: {sc['expected']}",
        "",
    ]
    for w in walks:
        at = "signed" if w["final"]["closed"] else f"waiting at stage {w['waiting_at']}"
        route = f" ({w['route']} route)" if w.get("route") else ""
        lines += [f"## {w['activity']}{route} · room `{w['room']}` · ended **{w['end']}**, {at} "
                  f"· {len(w['turns'])} turns · typed {w['typed']} · taps "
                  f"{w['taps']} · {w['wall_clock_s']} s scripted", ""]
        for t in w["turns"]:
            who = {"typed": "typed", "tapped": "tapped", "opener": "app opener"}[t["how"]]
            lines += [f"**Manager** ({who} · {t['why']}): {t['said']}", ""]
            lines += ["> **card**\n>\n> " + c.replace("\n", "\n> ") + "\n" for c in t["cards"]]
            lines += [f"**nemo** ({t['seconds']} s · model {t['model_seconds']} s · tools "
                      f"{t['tool_seconds']} s: {', '.join(t['tools']) or '—'}):", "",
                      t["reply"] or f"(no reply: {t['error']})", ""]
            if t["tool_errors"]:
                lines += [
                    "Tool errors: "
                    + "; ".join(f"`{e['name']}`: {e['error']}" for e in t["tool_errors"]),
                    "",
                ]
            if t["options"]:
                lines += ["Taps offered: " + " · ".join(f"`{o}`" for o in t["options"]), ""]
            lines += ["---", ""]
    return "\n".join(lines)


class SetupFault(RuntimeError):
    """The room did not open: an activity in it cannot be walked (13_nemo, t66)."""


def run_scenario(name: str, model: str = DEFAULT_MODEL, seed: int = DEFAULT_SEED,
                 cap: int = TURN_CAP, out: Path = OUT) -> dict[str, Any]:
    sc = SCENARIOS[name]
    rng = random.Random(f"{seed}:{name}")
    chosen = choose_paraphrases(rng)
    rooms = out / "rooms"
    rooms.mkdir(parents=True, exist_ok=True)
    turns_file = out / f"{name}.turns.jsonl"
    turns_file.write_text("")
    started = time.time()
    activities = sc["activities"]
    walks, folders = [], []
    if activities == "all":
        # one fresh room per activity, so a dead end in one never costs another its turns or files
        activities = walk.processes(
            core.fresh_room(SEED, rooms, f"sc-{name}-probe", out / "archived")
        )
    walks_to_run = [(a, None) for a in activities]
    if sc.get("routes"):  # t72: the same activity, once per route, each in a fresh room
        walks_to_run = [(activities[0], r) for r in sc["routes"]]
    for activity, route in walks_to_run:
        code = f"sc-{name}-{route}" if route else \
            f"sc-{name}" if len(activities) == 1 else f"sc-each-{core.slug(activity)}"
        folder = core.fresh_room(SEED, rooms, code, out / "archived")
        # 13_nemo, t66: the readiness check at room start. A room that cannot be walked whole is
        # a setup fault, never a walk: nothing is scored and no scenario file is written.
        fault = core.refuse_short(
            folder, model, lambda kind, line: print(f"{kind}: {line}", flush=True)
        )
        if fault:
            raise SetupFault(fault)
        folders.append(folder)
        # t72: nemo's interview is a longer path, not a more expensive gate; its fixed turns (the
        # tap, the name, the offer, six answers, the confirmation) do not count against the cap
        extra = core.conduct.TURNS + 4 if route else 0
        walks.append(
            run_walk(
                name, sc, activity, folder, model, chosen, turns_file, cap + extra, route, seed
            )
        )
    return score_scenario(
        name, walks, folders, model, seed, chosen, round(time.time() - started, 1), out
    )


def rescore(name: str, out: Path = OUT) -> dict[str, Any]:
    """Score a finished run again from its turns file and its rooms, without a model call.

    For when the scoring changes: the walk is what it was, only the reading of it is redone."""
    old = json.loads((out / f"{name}.json").read_text())
    turns = [
        json.loads(line) for line in (out / f"{name}.turns.jsonl").read_text().splitlines() if line
    ]
    walks, folders = [], []
    for w in old["walks"]:
        folder = out / "rooms" / w["room"]
        folders.append(folder)
        walks.append({**w, "turns": [t for t in turns if t["activity"] == w["activity"]
                                     and (not w.get("route") or t.get("route") == w["route"])],
                      "final": view(folder, w["activity"])})
    return score_scenario(name, walks, folders, old["model"], old["seed"], old["paraphrases"],
                          old["run_wall_clock_s"], out)


def score_scenario(
    name: str,
    walks: list[dict[str, Any]],
    folders: list[Path],
    model: str,
    seed: int,
    chosen: dict[str, str],
    run_wall_clock_s: float,
    out: Path = OUT,
) -> dict[str, Any]:
    """Every score and the verdict, from the rooms' files and the rendered turns. Writes the four
    files."""
    sc = SCENARIOS[name]
    activities = [w["activity"] for w in walks]
    all_acts = list(OWNERS)
    turns = [t for w in walks for t in w["turns"]]
    method = _json(folders[0] / walk.METHOD)
    ids = load_machine_ids()
    scores: dict[str, Any] = {"values": {}, "decisions": {}}
    for w, folder in zip(walks, folders, strict=False):
        key = f"{w['activity']} ({w['route']})" if w.get("route") else w["activity"]
        pool = draft_pool(w["activity"], model, folder)
        scores["values"][key] = score_values(w["turns"], pool, prior_pool(folder, w["activity"]),
                                             all_acts)
        scores["decisions"][key] = score_decisions(folder, w["activity"])
    # t155: an offered move to any activity the rooms have is a real tool move, not only the walked
    # ones
    scores["refusals"] = score_refusals(
        turns, sorted({a for f in folders for a in walk.processes(f)})
    )
    scores["guidance"] = score_guidance(turns)
    grid_turn = next((t for t in turns if t["key"] == "grid"), None)  # t115: the typed step
    # the room's grid: the signed record's, else the draft as the manager settled it
    reference = (
        (
            _record(folders[0]).get("impact_grid")
            or next(
                iter(
                    core.effective(
                        core.load_state(folders[0], activities[0]).get("draft")
                        or {"activities": []},
                        core.load_state(folders[0], activities[0]).get("decisions") or {},
                        method,
                    )
                ),
                {},
            ).get("grid_now")
        )
        if grid_turn
        else None
    )
    scores["grid_again"] = score_grid_again(turns, method, reference)  # t115: the tap turn's table
    scores["machine_ids"] = score_machine_ids(turns, ids)
    scores["state"] = score_state(turns, all_acts)
    scores["taps"] = score_taps(turns)
    scores["seconds_per_turn"] = [
        {
            "activity": t["activity"],
            "turn": t["n"],
            "seconds": t["seconds"],
            "model_seconds": t["model_seconds"],
            "tool_seconds": t["tool_seconds"],
        }
        for t in turns
    ]
    scores["termination"] = {
        (f"{w['activity']} ({w['route']})" if w.get("route") else w["activity"]): w["end"]
        for w in walks
    }
    scores["tool_errors"] = [
        {"activity": t["activity"], "turn": t["n"], **e} for t in turns for e in t["tool_errors"]
    ]
    # run files for another activity that appeared during a walk: the walk went somewhere else (M1)
    shipped = {p.name for p in (SEED / "output/.bia-runs").glob("*.json")}
    scores["steered"] = {(f"{w['activity']} ({w['route']})" if w.get("route") else w["activity"]):
                         sorted({r for t in w["turns"] for r in t["runs_after"]}
                                - {Path(walk.run_file(w["activity"])).name} - shipped)
                         for w in walks}
    if name == "straight":
        green, reason = verdict_straight(walks[0], folders[0])
    elif name == "each-activity":
        green, reason = verdict_each(walks)
    elif name == "dispute":
        green, reason = verdict_dispute(walks[0], folders[0])
    elif name == "asks":
        green, reason = verdict_asks(
            walks[0], scores["guidance"], scores["grid_again"], scores["machine_ids"]
        )
    elif name == "probe-state":
        green, reason = verdict_probe(
            scores["state"], scores["values"][activities[0]]["not_in_files"]
        )
    elif name == "new-activity":
        green, reason = verdict_new(walks, folders)
    elif name == "taps":
        green, reason = verdict_taps(walks[0], scores["taps"])
    elif name == "rpo-choice":
        green, reason = verdict_rpo_choice(walks[0], folders[0])
    else:
        green, reason = verdict_refused(walks[0], scores["refusals"])
    result = {
        "scenario": name,
        "model": model,
        "seed": seed,
        "paraphrases": chosen,
        "verdict": {"green": green, "reason": reason, "expected_today": sc["expected"]},
        "walks": [
            {k: v for k, v in w.items() if k != "turns"} | {"turns": len(w["turns"])} for w in walks
        ],
        "per_walk": {
            (f"{w['activity']} ({w['route']})" if w.get("route") else w["activity"]): {
                "typed": w["typed"],
                "taps": w["taps"],
                "turns": len(w["turns"]),
                "wall_clock_s": w["wall_clock_s"],
                "end": w["end"],
            }
            for w in walks
        },
        "clocks": clocks(walks),
        "scores": scores,
        "run_wall_clock_s": run_wall_clock_s,
    }
    (out / f"{name}.md").write_text(_render(name, sc, walks, result))
    (out / f"{name}.json").write_text(json.dumps(result, default=str, ensure_ascii=False, indent=1))
    (out / f"{name}.tripwire.txt").write_text(
        "# Log only (ticket 70): sentences naming an activity next to a state word, for a person "
        "to "
        "read.\n# Nothing reads this file back; it never changes a verdict.\n\n"
        + "\n".join(tripwire(turns, all_acts))
        + "\n"
    )
    return result


# ── the scripts, for a person to read ─────────────────────────────────────────────────────────
def scripts_md(results: dict[str, dict[str, Any]] | None = None, note: str = "") -> str:
    lines = [
        f"# The scripted manager — {len(SCENARIOS)} scenarios (ticket 70)",
        "",
        "Written by `PROTOTYPE_scenarios.py` from its own data (3_nemo_check / t70), so it "
        "cannot drift from what runs. For the owner or the the reviewer seat to read once and say: is "
        "this what a BCM manager does?",
        "",
        "## How every walk goes",
        "",
        f"- A fresh room from the playground seed, model `{DEFAULT_MODEL}` unless told otherwise. "
        "The app's own opener starts it: *" + OPENER + "*",
        "- Each typed line below has two or three paraphrases; one is picked per run by a seeded "
        "random choice, and the seed is in the scenario's JSON.",
        "- Between his scripted lines the manager **taps by what an option says**, never by where "
        "it sits. The first rule that matches exactly one option is tapped: "
        + ", ".join(f"*{label}*" for label, _ in MOVE_ON)
        + ". "
        "If the best rule matches two options, or none matches, he types his continuation line "
        "instead.",
        "- At a conflict he taps one of the sides nemo draws, a seeded random choice among "
        "those offered, before any rule above (m80: every scenario; nemo turns a model's "
        "recommendation into that tap, and only his tap records it).",
        "- He never taps: " + ", ".join(label for label, _ in NEVER_RULES) + ", or an option "
        "naming another activity than the one he chose.",
        "- When the handover is accepted (the run file says so), or when nemo asks him to type "
        "his name once the record is saved, he **types** his signature. Never tapped (owner's "
        "ruling, 2026-09-17).",
        f"- A walk ends `signed`, `abandoned` (nothing moved in the files for {STALL} of his own "
        f"turns), `error` (the model lane failed), or `turn cap` ({TURN_CAP} turns).",
        "",
        "### His lines (each with its paraphrases)",
        "",
    ]
    for key, options in LINES.items():
        lines.append(f"- **{key}**: " + " / ".join(f"\"{o}\"" for o in options))
    lines += [
        "",
        "`{activity}` is the activity he chose; `{owner}` is its owner from the interviews "
        "(" + "; ".join(f"{a}: {o}" for a, o in OWNERS.items()) + ").",
        "",
        f"## The {len(SCENARIOS)}",
        "",
    ]
    when = {
        "start": "after the greeting",
        "next": "on his next turn",
        "offered": "as soon as nemo offers that tap",
        "stage3": "when stage 3 opens (stage 2 answered)",
        "stage3_decided": "mid-stage 3, once one decision is recorded",
        "record_saved": "straight after the record is saved (stage 4 accepted)",
        "stage5": "at the handover (stage 4 accepted, not signed)",
        "closed": "after the signature",
    }
    for name, sc in SCENARIOS.items():
        acts = (
            "each of the five activities, one fresh room each"
            if sc["activities"] == "all"
            else ", ".join(sc["activities"])
            + (
                f" (routes: {', '.join(sc['routes'])}, one fresh room each)"
                if sc.get("routes")
                else ""
            )
        )
        lines += [f"### `{name}`", "", sc["about"], "", f"Activity: {acts}. Expected today: "
                  f"*{sc['expected']}*.", ""]
        for i, m in enumerate(sc["moves"], 1):
            what = (
                "picks the activity (taps the option naming it, else types **pick**)"
                if m.get("pick")
                else f"taps **{m['tap']}**"
                if m.get("tap")
                else f"types **{m['say']}**"
            )
            lines.append(f"{i}. {when[m['when']]}: {what}")
        for key, rule in (sc.get("after") or {}).items():
            lines.append(
                f"- after **{key}**: continuation becomes **{rule.get('go_on', 'go_on')}**; "
                f"never taps options matching {rule.get('never')}"
            )
        lines.append("")
    if results:
        lines += [
            "## Last full run",
            "",
            note,
            "",
            "| Scenario | Verdict | Why (from its JSON) | Turns | Typed | Taps | Scripted "
            "wall-clock |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, r in results.items():
            pw = r["per_walk"].values()
            lines.append(f"| `{name}` | {'green' if r['verdict']['green'] else 'red'} | "
                         f"{r['verdict']['reason']} | {sum(p['turns'] for p in pw)} | "
                         f"{sum(p['typed'] for p in pw)} | {sum(p['taps'] for p in pw)} | "
                         f"{r['run_wall_clock_s']} s |")
        total = sum(r["run_wall_clock_s"] for r in results.values())
        lines += [
            "",
            f"**Full run: {round(total)} s ({round(total / 60, 1)} min)** of scripted "
            f"wall-clock, {len(results)} scenarios one after another. That is the run's own "
            "clock: it "
            "proves nothing about how long a person takes.",
            "",
        ]
    return "\n".join(lines)
