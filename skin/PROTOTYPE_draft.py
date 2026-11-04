"""PROTOTYPE, throwaway (2026-09-17). Stage 2 collect + stage 3a draft + stage 3b verify, once per
seed.

    python PROTOTYPE_draft.py Slaughter glm|deepseek|gpt6

The model reads every interview in the seed plus the method and a compact register, and returns a
schema-fixed draft: which interviews count (and why), per activity an impact grid row per category
(stated or proposed, with quote, file and speaker), MTPD/RTO/RPO, dependencies, conflicts, gaps.
Then a deterministic pass checks it: quote verbatim in the named file (nemo.text.norm), a stated
figure appears in its own quote, register ids resolve, the method's MTPD rule is applied to the grid
and compared with what the owner stated. Failures are never silently kept: a stated figure whose
quote does not hold becomes a proposal (clearly marked), a quote that is not in the file is removed.
Writes <activity>.<model>.json in the drafts cache, `DRAFTS` (t176: run state, never the tracked
`drafts/`, which are read-only fixtures).

13_nemo, t66: the verify pass also applies two floors, marked in the draft's `floor` block. The
interview floor: every interview nemo files under the activity's own department is kept (one the
model left out comes back with FLOOR_WHY), and an interview from another department stays only with
its reason. The dependency floor (ticket 01): every register id those interviews name is a
dependency. A draft whose evidence never quotes an own-department interview is re-drafted once with
those interviews named as required. `walkable()` states, as code, when a draft can be walked.
`--reverify` re-runs the verify pass over the saved raw answer without a model call.

13_nemo, t72: an activity a manager added to a room is drafted IN that room (`draft_in_room`), by
the same prompt and verify pass, over the room's own files: its interviews plus the other evidence
folders (risk register, organisation, suppliers, regulatory, prior cycle), because an added
activity has no department on file and those files are where the room's words about it are. The
draft is written under the room's `output/.proto/drafts/`, never to the shared once-per-seed
`drafts/`. Filed activities are drafted exactly as before.

13_nemo, t72b: an added activity's draft also carries the risk-register floor (`risk_floor`): every
row of the room's risk register its own name names (`names_row`) is attached as a verified quote,
file, line and words exactly, whether or not the model quoted it. Evidence only; it sets no figure.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # this tree's own src (135)
sys.path.insert(0, str(Path(__file__).parent))

import impact_chart  # noqa: E402

from nemo import facts, interview, walk  # noqa: E402
from nemo.evidence import MISSING  # noqa: E402
from nemo.impact import NO_MTPD, derive_mtpd, worst_case_row  # noqa: E402
from nemo.method import beyond_horizons  # noqa: E402
from nemo.text import norm  # noqa: E402

import PROTOTYPE_lanes as lanes  # noqa: E402
from bia_figures import (
    deps as figures_deps,  # noqa: E402  (this tree's copy, beside the skin: 189, ADR-0035)
)
from bia_figures import impact as figures_impact  # noqa: E402

#: The seed the demo mints from: `NEMO_SEED`, as `nemo.seed` and the app read it (ADR-0017), with
#: the old path as the default so a run that sets nothing drafts what it always drafted (t139).
SEED = Path(os.environ.get("NEMO_SEED", "/home/user/work/nemo-playground/seed"))
#: t176: the tracked drafts, read-only fixtures. nemo-live is a checkout of this tree, so nothing at
#: runtime writes here; `core.draft_for` reads them after the cache.
FIXTURES = Path(__file__).parent / "drafts"
#: t176: the drafts cache a prepare run writes, run state: `NEMO_DRAFTS`, else `skin/run/drafts`.
#: The one setting `core.DRAFTS` and `PROTOTYPE_scenarios.DRAFTS` read.
DRAFTS = Path(os.environ.get("NEMO_DRAFTS") or Path(__file__).parent / "run" / "drafts")

#: Ticket 187: what one drafting call may generate, reasoning included, reserved against the capped
#: key before generation. The longest real draft call recorded is 15369 tokens (skin/drafts/
#: slaughter.deepseek.json, meta.usage), the longest on glm 14338 with 1519 reasoning; 20000 is that
#: plus 30%. It was 32000, which 402s once the key can afford less
#: (nemo-builds/live-scenarios-report.md).
DRAFT_MAX_TOKENS = 20000

PROMPT = """You are an experienced Business Impact Analysis (BIA) analyst. Draft the BIA evidence \
for \
the process "{activity}" of this company from ALL of the interview transcripts below, the \
company's \
BCM method and its dependency register.

Rules:
1. Collect: include every interview that says something about "{activity}" — its own department's \
interviews AND other departments' interviews that talk about it or about something it depends on. \
For each, one plain line why it counts. Leave out interviews that say nothing about it. Mark \
"keep": true on the ones you recommend this BIA rests on, false on the rest.
2. Activities: draft the sub-steps an interview names (e.g. A1, A2...) separately so their \
evidence \
stays attached to the words that carry it. They are NOT the BIA's activities: the BIA activity \
list \
is fixed with the manager at step 1 (usually one activity, from last cycle's BIA), and the walk \
merges these sub-steps into it — worst score per category, tightest clock.
3. Impact grid: for EVERY activity, one row per method category id ({lenses}) with a score 1-5 for \
EVERY horizon ({horizons}), severity per the method's scale.
   - kind "stated": the interviewee gave these scores themselves (e.g. a scored table row). quote \
= \
the exact row or sentence.
   - kind "proposed": nobody scored it, you propose it from what was said. quote = the exact words \
you base it on (may be from another interview), reason = one short sentence why these scores. If \
nothing at all was said, still propose your best judgement with quote "" and say so in reason.
4. MTPD, RTO, RPO per activity: value, kind stated|proposed, quote, path, speaker, reason. \
MTPD value must be one of the horizons{mtpd_values}. RTO {rto_like} or "RECOVERY GAP (proposed)" \
where no recovery target can sit inside the MTPD — you PROPOSE that gap, you never acknowledge it: \
only the manager does, later in the walk, and never write "(acknowledged)" anywhere.{rto_stated} \
RPO must be one of: {rpo}.
5. Owner per activity: the person who owns it (name as in the files) with a quote.
6. Dependencies: what the activity needs, with asset_id from the register when one clearly matches \
(else ""), and the quote.
7. Conflicts: where interviews (or one interview and a later one) disagree about a figure for an \
activity, list both sides with quotes, recommend one side (index), and why in one sentence. Each \
side must ALSO say which figure it implies, so settling the conflict moves that figure: \
"implies": {{"item_id": "<activity id>.mtpd|.rto|.rpo|.<category id>", "value": "<the figure that \
side means>"}} — or "implies": null when that side changes no figure in this BIA.
8. Every quote must be copied EXACTLY, character for character, from the file you name in "path" \
(a contiguous span, max ~300 chars). Never paraphrase inside "quote". Path is the file path as \
given.

Return ONE JSON object, no prose, in this shape:
{{"interviews": [{{"path": "...", "speaker": "...", "department": "...", "why": "...", \
"keep": true}}],
 "activities": [{{"id": "A1", "name": "...",
   "owner": {{"name": "...", "quote": "...", "path": "..."}},
   "grid": [{{"lens": "<category id>", "scores": {{"<horizon>": 1}}, "kind": "stated|proposed", \
"quote": "...", "path": "...", "speaker": "...", "reason": "..."}}],
   "mtpd": {{"value": "...", "kind": "...", "quote": "...", "path": "...", "speaker": "...", \
"reason": "..."}},
   "rto": {{...same...}}, "rpo": {{...same...}},
   "dependencies": [{{"heard": "...", "asset_id": "...", "quote": "...", "path": "..."}}]}}],
 "conflicts": [{{"id": "C1", "activity": "A1", "about": "...", "sides": [{{"claim": "...", \
"quote": "...", "path": "...", "speaker": "...", "implies": {{"item_id": "A1.mtpd", "value": "8 \
h"}}}}], "recommend": 0, "why": "..."}}],
 "gaps": [{{"activity": "A1", "what": "...", "ask": "one question for the manager"}}]}}

METHOD (02_BCM-Method/method.json):
{method}

DEPENDENCY REGISTER (asset_id: name — owning dept):
{register}

INTERVIEWS:
{interviews}
"""

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
                8: "eight", 10: "ten", 12: "twelve", 24: "twenty-four", 36: "thirty-six",
                48: "forty-eight", 72: "seventy-two"}
ALIASES = {24: ("a day", "one day", "a full day"), 168: ("a week", "one week"),
           48: ("two days",), 72: ("three days",)}


def interviews(seed: Path) -> dict[str, str]:
    out = {}
    for folder in ("07_Interviews", "output/owner-interviews"):
        for p in sorted((seed / folder).glob("*.md")):
            out[p.relative_to(seed).as_posix()] = p.read_text(encoding="utf-8")
    return out


#: The room's evidence folders besides the interviews, read for an added activity (13_nemo, t72).
#: Not the method (it is in the prompt whole), not the root README or approval log, and not
#: 09_Evaluation, which holds evaluation fixtures rather than the company's evidence.
ROOM_FOLDERS = ("01_Organisation", "03_Dependencies", "04_Suppliers", "05_Regulatory",
                "06_Risk-and-Incidents", "08_Prior-Cycle")
ROOM_DRAFTS = "output/.proto/drafts"


def room_files(room: Path) -> dict[str, str]:
    """The interviews and the room's other evidence files, as {room path: text}. 13_nemo, t72."""
    out = interviews(room)
    for folder in ROOM_FOLDERS:
        for p in sorted((room / folder).glob("*.md")):
            out[p.relative_to(room).as_posix()] = p.read_text(encoding="utf-8")
    return out


# ── the risk-register floor for an added activity (13_nemo, t72b) ───────────────────────────
#: The room's risk register, and the room's list of added activities (core's `ADDED`).
RISK_REGISTER = "06_Risk-and-Incidents/risk-register.md"
ADDED_FILE = "output/.proto/added-activities.json"
#: A risk-register table: the header row carries these columns (the file's own words).
RISK_COLUMNS = {"id": "ID", "category": "Cat.", "text": "Risk", "owner": "Owner"}


def added_name(room: Path, activity: str) -> str:
    """The manager's own name for an added activity, exactly as the room's added-activities file
    holds it (matched by the same slug the room uses); the activity as given when the file has
    none."""
    p = Path(room) / ADDED_FILE
    names = (
        [a["name"] for a in (json.loads(p.read_text()).get("activities") or [])]
        if p.exists()
        else []
    )
    key = re.sub(r"[^a-z0-9]+", "-", activity.lower()).strip("-")
    return next(
        (n for n in names if re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-") == key), activity
    )


def risk_rows(room: Path) -> list[dict[str, Any]]:
    """Every row of the room's risk register, read from the file and nothing else.

    A row is a line of a Markdown table whose header names the columns in `RISK_COLUMNS`. Each row
    carries its id, category, text (the "Risk" column) and owner, with `**` emphasis taken off for
    display, and — the evidence — its file path, its 1-based line number and the line exactly as it
    stands in the file (`quote`).
    """
    p = Path(room) / RISK_REGISTER
    if not p.is_file():
        return []
    rows, header = [], None
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("|"):
            header = None  # a table ends where its lines stop
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells
            continue
        if not set(RISK_COLUMNS.values()) <= set(header) or set("".join(cells)) <= set("-: "):
            continue  # another table, or the separator row
        row = dict(zip(header, cells, strict=False))
        out = {k: row.get(col, "").replace("**", "").strip() for k, col in RISK_COLUMNS.items()}
        if out["id"]:
            rows.append({**out, "path": RISK_REGISTER, "line": n, "quote": line})
    return rows


def names_row(name: str, row: dict[str, Any]) -> bool:
    """Whether the manager's name for an activity names this risk-register row.

    The rule (13_nemo, t72b, the brief's own): the name, as stored in the added-activities file,
    appears as a whole word in the row's category or its text ("Risk" column), compared without
    case. A word boundary is any character that is not a letter, digit or underscore — so "/" is
    one, and "HR" matches "People/HR". A name of several words matches them in order, with any
    run of white space between. Nothing else is compared: never the model's text (M13), never a
    synonym ("Human Resources" does not match "People/HR"; the stage-2 card is the route for that).
    """
    words = str(name).split()
    if not words:
        return False
    pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, words)) + r"(?!\w)"
    return any(re.search(pattern, row.get(field) or "", re.I) for field in ("category", "text"))


def risk_floor(room: Path, activity: str) -> list[dict[str, Any]]:
    """The rows of the room's risk register an added activity's own name matches (`names_row`),
    each attached as a verified quote: the file, the line, the row's words as they are. Evidence
    only: no row sets a score or a clock. Applied whether or not the model mentioned the row."""
    name = added_name(room, activity)
    text = norm((Path(room) / RISK_REGISTER).read_text(encoding="utf-8")) \
        if (Path(room) / RISK_REGISTER).is_file() else ""
    return [{**r, "verified_quote": norm(r["quote"]) in text, "floor": True,
             "how": f"names {name!r}"} for r in risk_rows(room) if names_row(name, r)]


def is_interview(path: str) -> bool:
    """Whether a room path is an interview: a file in one of nemo's two interview homes."""
    return str(path).startswith(tuple(f"{home}/" for home in interview.HOMES))


def register_lines(seed: Path) -> str:
    reg = json.loads((seed / "03_Dependencies/dependency-register.json").read_text())
    return "\n".join(f"{k}: {v.get('name')} — {v.get('owning_dept')}"
                     for k, v in reg.items() if isinstance(v, dict))


def _figure_in_quote(value: str, quote: str) -> bool:
    q = norm(quote)
    nums = [int(n) for n in re.findall(r"\d+", str(value))]
    if "week" in str(value).lower():
        nums = [168]
    if not nums:
        return norm(value) in q
    n = max(nums)
    if re.search(rf"(?<!\d){n}(?!\d)", q):
        return True
    if n == 168 and re.search(r"(?<!\d)1\s*(wk|week)", q):
        return True
    return bool((NUMBER_WORDS.get(n) and NUMBER_WORDS[n] in q) or
                any(a in q for a in ALIASES.get(n, ())))


def _quote_holds(item: dict[str, Any], files: dict[str, str]) -> bool:
    quote, path = str(item.get("quote") or ""), str(item.get("path") or "")
    return bool(norm(quote)) and path in files and norm(quote) in norm(files[path])


# ── the interview floor and "walkable" (13_nemo, t66) ─────────────────────────────────────────
METHOD = "02_BCM-Method/method.json"
REGISTER = "03_Dependencies/dependency-register.json"


def read_register(room: str | Path) -> Any:
    """t299: the room's dependency register; a room without one has none, so it names nothing,
    and nor does one that is not JSON, which a turn names before anything reads it (t297)."""
    path = Path(room) / REGISTER
    if not path.is_file() or walk.unreadable_register(Path(room)):
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


FLOOR_WHY = "filed under this activity's department"
#: t79 fix 1: what nemo's verify pass found about a figure the model called stated. nemo's own
#: sentence, so a card prints it on its own line in nemo's voice and never inside the model's.
#: **These exact words are LOAD-BEARING, not a wording choice.** Every draft on file was drawn
#: while the pass welded this note inside the model's own sentence, and `CHECK_NOTE_APPENDED` is
#: the only anchor by which nemo can find its own words in one and split them back out. Change the
#: wording and every cached draft regresses to the welded form on the card and in the record. It
#: can move when the drafts are redrawn, or behind a frozen copy of the old literal, and not before.
CHECK_NOTE = "the model called this stated; the check could not find it in the quote"
#: how a draft drawn before t79 fix 1 carries that note: appended INSIDE the model's own sentence.
#: A saved draft is never rewritten (t75's box), so nemo splits its own words back out at render
#: time instead — by this constant, which nemo wrote the note from.
CHECK_NOTE_APPENDED = f" ({CHECK_NOTE})"
#: the `why` on the MTPD-rule conflict nemo synthesises where the draft's MTPD is not the grid's.
#: t477 (D2): what the method's rule means for him, in plain words, never "the method derives …";
#: r2: seed-true, the method gives its figure no precedence and the activity's owner decides
#: (impact-criteria.md, method.json's rto_rule; 14_nemo_design's words)
RULE_WHY = ("Your company's method works the MTPD out from the impact scores over time, so a "
            "different figure needs a reason; the activity's owner decides.")
#: t477: the same `why` as drafts on file carry it, written before 477. A saved draft is never
#: rewritten (t75's box), so it is said as `RULE_WHY` where it enters the walk (`RETIRED_WHY`)
RULE_WHY_BEFORE_477 = ("The method derives the MTPD from the grid; the other figure is the thing "
                       "to explain.")
RETIRED_WHY = {RULE_WHY_BEFORE_477: RULE_WHY}
#: t377 L r2: that conflict's subject (the decision card's title) and the method's side, each naming
#: the grid's year (`grid_year`) where its rows quote a dated interview
RULE_ABOUT = "MTPD: the grid{year} gives {derived} by the method's rule, the draft says {said}"
RULE_CLAIM = "{derived} (the method's rule over the grid{year})"


def grid_year(rows: dict[str, dict[str, Any]], room: Path) -> str:
    """t377 L r2: the year of each interview a grid's rows quote, by its date (`impact_chart.year`,
    377 L's), joined with "and"; "" where they quote no dated interview."""
    when = {h.path: h.when for h in facts.interviews(room)}
    return " and ".join(sorted({impact_chart.year(when.get(str(r.get("path")), ""))
                                for r in rows.values()} - {""}))
#: the `reason` on the row nemo writes where the draft has none
NOTHING_DRAFTED = "nothing drafted"
#: every sentence nemo itself puts into a draft object, whole and word for word, so nemo can know
#: its own in a draft on file that was drawn before it started marking them `floor`
NEMO_S_OWN = (FLOOR_WHY, RULE_WHY, RULE_WHY_BEFORE_477, NOTHING_DRAFTED)
#: t79 fix 2, and the general rule behind it (6_nemo_check, 2026-09-20): **a mark is only
#: structural if the model cannot write it.** "We read a field, not prose" is not the same claim as
#: "the model cannot set that field" — `floor` and `check_note` were read as nemo's own while the
#: model could put either in its own JSON, which is M13 wearing a new coat. So what comes back from
#: the model is FILTERED here, at the one seam it arrives through, to the fields `PROMPT` asks it
#: for and nothing else; every mark nemo relies on is set by nemo AFTER the filter, on nemo's own
#: object. A later ticket adding a fourth mark is held by this without touching it.
MODEL_MAY_SET = {
    "draft": ("interviews", "activities", "conflicts", "gaps"),
    "interview": ("path", "speaker", "department", "why", "keep"),
    "activity": ("id", "name", "owner", "grid", "mtpd", "rto", "rpo", "dependencies"),
    "owner": ("name", "quote", "path", "speaker"),
    "row": ("lens", "scores", "kind", "quote", "path", "speaker", "reason"),
    "figure": ("value", "kind", "quote", "path", "speaker", "reason"),
    "dependency": ("heard", "asset_id", "quote", "path"),
    "conflict": ("id", "activity", "about", "sides", "recommend", "why"),
    "side": ("claim", "quote", "path", "speaker", "implies"),
    "implies": ("item_id", "value"),
    "gap": ("activity", "what", "ask"),
}
#: nemo's stamp on a draft its own verify pass built, so a reader can tell one from a draft drawn
#: before the marks existed. Not in `MODEL_MAY_SET`, and written after the filter, so the model
#: cannot supply it.
MARKED_BY_NEMO = "authors_marked"
#: t79 fix 3, on 7_nemo_check's ruling (2026-09-20, 23:38:34): the two words `PROMPT` asks the model
#: for, and the whole of what it may propose as a `kind`. `kind` is not one field among the others —
#: the record's `origin` **is** this field (`PROTOTYPE_core.py:620,627`), so what the document he
#: SIGNS says about who authored a number was, until this fix, a string the drafting model chose. A
#: model could mark its own figure `manager` and the card would call it his decision. That is an
#: authorship fault a level above the counting, and it is Important 1's own rule applied to the
#: field that decides attribution: **nemo decides what a kind IS; the model may PROPOSE one, and a
#: proposal nemo does not recognise is not a kind.** An unrecognised (or missing) kind reads as
#: `proposed` — nemo's own, the conservative side, exactly as an out-of-vocabulary RPO already does.
MODEL_MAY_PROPOSE_KIND = ("stated", "proposed")
#: the shapes that carry a `kind` into the record as an `origin`
KINDED = ("row", "figure")


def _kept(x: Any, shape: str) -> dict[str, Any]:
    """One dict from the model's reply, cut to the fields it may set — and to the values it may set.

    t79 fix 3: anything that is not a dict is **dropped**, not passed through. Passing it through
    was not a gap in the whitelist, it was the whitelist trusting the SHAPE of what it was handed:
    `verify`'s own `dict(item or {})` rebuilds from a list of pairs exactly the fields cut here, so
    a figure sent as `[["floor", true], ["check_note", "..."]]` walked in whole and printed the
    model's sentence as nemo's reasoning and under "nemo's check:". A whitelist over keys alone is
    not a boundary; this one asserts the shape and, for `kind`, the vocabulary.
    """
    allowed = MODEL_MAY_SET[shape]
    if not isinstance(x, dict):
        return {}
    # t79 fix 5: cut to the fields the prompt asks for, and to their TYPE. Every field but the few
    # declared structured is asked for as a string, so a container there is not the value asked for
    # and is dropped exactly as an unasked-for field is. See `MODEL_MAY_SET_STRUCTURED`.
    structured = MODEL_MAY_SET_STRUCTURED.get(shape, ())
    out = {k: v for k, v in x.items()
           if k in allowed and (k in structured or isinstance(v, str))}
    if shape in KINDED:
        out["kind"] = out.get("kind") if out.get("kind") in MODEL_MAY_PROPOSE_KIND else "proposed"
    return out


#: t79 fix 4, cut to its drop policy by fix 6 (review 5, Minor 3): an object with no id is not an
#: object, so it is dropped. Crash safety does not rest on this: it rests on the typing below.
MODEL_MUST_SET = {"conflict": ("id",), "activity": ("id",)}

#: t79 fix 5, on review 4 and 7_nemo_check's ruling (2026-09-21, 09:24:49). `MODEL_MUST_SET` is a
#: PRESENCE test, and `_kept` type-checked nothing but `kind`, so a `conflict.id` the model sent as
#: `[["a", 1]]` was truthy, was `usable`, and raised `TypeError: unhashable type: 'list'` in
#: `core.build_proposal`. The same fault at `activity.id` and at `dependency.asset_id`.
#:
#: The comment this replaces named **three** consumers of `c["id"]` and there were at least four
#: (`core.py:642`, `known = {d["asset_id"] for d in deps}`) — a hand-kept list written BY the rule
#: against hand-kept lists, and wrong. So the fix does not enumerate consumers at all: `PROMPT` asks
#: for every field below as a **string**, and the model's reply is cut to what it was asked for in
#: TYPE as it is already cut in name. The ones that are not strings are declared here, because they
#: are the few and they are exactly the fields the filter already descends into; everything else a
#: shape allows must be a `str` to survive. A leaf that is not a string is not the leaf the prompt
#: asked for, whoever reads it, including the reader nobody has written yet.
#: **What keeps this honest is the generated corpus** in `tests/test_whose_words.py`
#: (`HOSTILE_FORMS` x `PLACES`, and its `_typed_leaves`): it drives every form at every place and
#: asserts this typing over every leaf of the verified draft. Narrow that corpus on either axis and
#: its own guard reds — which is the coupling review 4 asked to have in the code rather than in a
#: report, since a later reader sees the diff and not the reasoning.
MODEL_MAY_SET_STRUCTURED = {
    "draft": ("interviews", "activities", "conflicts", "gaps"),
    "interview": ("keep",),
    "activity": ("grid", "mtpd", "rto", "rpo", "owner", "dependencies"),
    "row": ("scores",),
    "conflict": ("sides", "recommend"),
    "side": ("implies",),
}
#: every field of every shape that `PROMPT` asks for as a string, from the two mappings above. No
#: field name is structured in one shape and a string in another (asserted in the suite), so this
#: set alone types any leaf of a draft object wherever it sits.
MODEL_MUST_SET_AS_STR = frozenset(
    f for shape, fields in MODEL_MAY_SET.items() for f in fields
    if f not in MODEL_MAY_SET_STRUCTURED.get(shape, ()))


def _usable(kept: dict[str, Any], shape: str) -> bool:
    """An object worth keeping: it holds something the prompt asked for, and everything the code
    that reads this shape takes without asking (`MODEL_MUST_SET`)."""
    return bool(kept) and all(kept.get(k) for k in MODEL_MUST_SET.get(shape, ()))


def _many(x: Any, shape: str) -> list[dict[str, Any]]:
    """The same, where the model was asked for a LIST of objects (t79 fix 3).

    A scalar where a list belongs raised `TypeError` out of the filter, and a dict there iterated
    its keys. The reviewer's standard cuts both ways: a leak and a traceback on the manager's phone
    are both failures, so anything that is not a list of objects is no objects — and (fix 4) an
    object the filter leaves unusable is no object either.
    """
    if not isinstance(x, list):
        return []
    return [k for k in (_kept(i, shape) for i in x if isinstance(i, dict)) if _usable(k, shape)]


def _what_the_boundary_cut(sent: Any, kept: dict[str, Any]) -> list[str]:
    """t79 fix 5, Minor 1 of review 4: the boundary's drops were silent, and `recommend` dropping to
    `None` is a **silent mutation of a surviving object** carrying twelve lines of comment — which
    is, word for word, the shape HANDOVER's own rule names (*when a defence has to be explained in
    a comment next to a silent return, it should have been a refusal*). An object that is simply
    gone is its own refusal and a reader downstream can see the absence; a conflict that still
    reaches his card having quietly lost nemo's view is not. Re-derived here by comparing what the
    model sent with what survived — the boundary itself stays a pure function with no log to pass
    around, and `verify` is the only caller that has both."""
    if not isinstance(sent, dict):
        return ["the model's reply was not an object; nothing of it was kept"]
    out = []
    for k in ("interviews", "activities", "conflicts", "gaps"):
        was = sent.get(k)
        if was is not None and not isinstance(was, list):
            out.append(f"{k}: the model sent no list, so no {k} were kept")
        elif isinstance(was, list) and len(was) > len(kept.get(k) or []):
            out.append(f"{k}: {len(was) - len(kept[k])} of {len(was)} dropped at the boundary "
                       f"(not an object, or holding nothing the prompt asked for)")
    # t79 fix 6 (review 5, Minor 4): said only when a side really went AND the model had
    # recommended one. A `recommend` the model itself sent as null is not a drop.
    was_list = sent.get("conflicts") if isinstance(sent.get("conflicts"), list) else []
    # why: `was_list` is a list: the isinstance on the same line chose it
    sent_c = {c["id"]: c for c in was_list if isinstance(c, dict) and isinstance(c.get("id"), str)}  # type: ignore[union-attr]
    for c in kept.get("conflicts") or []:
        was = sent_c.get(c.get("id")) or {}
        if (isinstance(was.get("sides"), list) and len(was["sides"]) > len(c.get("sides") or [])
                and was.get("recommend") is not None and c.get("recommend") is None):
            out.append(f"{c.get('id')}: a side was dropped at the boundary, so the model's "
                       f"recommendation no longer points at a side and nemo recommends none")
    return out


def only_the_model_s(draft: Any) -> dict[str, Any]:
    """The model's reply with every field it was not asked for removed, shape by shape (t79 fix 2).

    The whole of the boundary: after this, nothing in the object came from anywhere but the model's
    own schema, so a field nemo reads as its own mark can only have been set by nemo.
    """
    d = _kept(draft, "draft")
    # t313 (a): `keep` is asked for as a bool, so anything else is no keep
    ivs = [{k: v for k, v in i.items() if k != "keep" or isinstance(v, bool)}
           for i in _many(d.get("interviews"), "interview")]
    out: dict[str, Any] = {"interviews": ivs,
                           "activities": [], "conflicts": [],
                           "gaps": _many(d.get("gaps"), "gap")}
    for act in _many(d.get("activities"), "activity"):
        grid = act.get("grid")
        if isinstance(grid, dict):
            # a model that keyed its rows by category instead of listing them: the key is its own
            # word for the row, and `verify` reads a list. Its own `lens` wins where it gave one.
            grid = [{"lens": k, **r} if isinstance(r, dict) else r for k, r in grid.items()]
        if "grid" in act:
            act["grid"] = _many(grid, "row")
        for f in ("mtpd", "rto", "rpo"):
            if f in act:
                act[f] = _kept(act[f], "figure")
        if "owner" in act:
            act["owner"] = _kept(act["owner"], "owner")
        act["dependencies"] = _many(act.get("dependencies"), "dependency")
        out["activities"].append(act)
    for c in _many(d.get("conflicts"), "conflict"):
        sent = c.get("sides")
        c["sides"] = [{**s, **({"implies": _kept(s["implies"], "implies")}
                               if isinstance(s.get("implies"), dict) else {})}
                      for s in _many(sent, "side")]
        if not isinstance(sent, list) or len(c["sides"]) != len(sent):
            # t79 fix 4, on 7_nemo_check's ruling: **an index into a list the filter can shorten is
            # meaningless after the filter.** `recommend` is the model's own index into `sides`
            # (`PROMPT`: "recommend one side (index)"), and it is the only positional reference the
            # model gives us — every other cross-reference it writes is a NAME compared by equality
            # (`implies.item_id`, `row.lens`, `dependency.asset_id`, `*.path`, the ids), which a
            # shortened list cannot move. Drop one bad side and the surviving index points at
            # another side: sides `[<scalar>, A, B]` with `recommend: 1` made nemo recommend B
            # where the model meant A, on a card he taps to settle an RTO and that accept-all can
            # take unread. nemo does not invent an empty side to hold the place (that would be nemo
            # writing a side) and does not point at the wrong one: `None` is the state `core.py`
            # already represents — no recommendation. Declining to recommend is honest.
            c["recommend"] = None
        out["conflicts"].append(c)
    return out


def own_interviews(room: Path, activity: str) -> list[str]:
    """The interviews filed under the activity's own department: nemo's own stage-2 offer.

    Read from nemo (`interview.held`, what `walk.pick_interview` offers), never guessed from a
    file name. 13_nemo, t66.
    """
    return [i.path for i in interview.held(room, activity)]


def floor_texts(room: Path, paths: list[str], activity: str) -> list[str]:
    """The interviews a dependency floor reads for `activity`, as text (ticket 184).

    An interview filed under the activity's own department is read whole. Any other it rests on
    is read `elsewhere`: its "Depends on:" line lists what its own activity needs, not this one's.
    """
    own = set(own_interviews(room, activity))
    return [text if p in own else figures_deps.elsewhere(text)
            for p in paths if p and (room / p).is_file()
            for text in [(room / p).read_text(errors="replace")]]


def with_floor(chosen: list[dict[str, Any]], own: list[str], activity: str) -> list[dict[str, Any]]:
    """The interviews offered for an activity: the draft's choice, over the floor. 13_nemo, t66.

    The rule, applied at draft time (the verify pass) and again at the stage-2 offer:
    - every interview filed under the activity's own department is offered, whatever the draft
      chose; one the draft left out comes back with `why` = FLOOR_WHY and `floor: true`;
    - an interview from another department is offered only with a non-empty reason, which the
      manager sees; without one it is not offered.
    """
    out, seen = [], set()
    for item in chosen:
        if item.get("path") in seen:  # the same interview twice is offered once (fix round 1)
            continue
        seen.add(item.get("path"))
        if item.get("path") in own:
            out.append({**item, "own_department": True})
        elif str(item.get("why") or "").strip():
            out.append({**item, "own_department": False})
    have = {i["path"] for i in out}
    out += [{"path": p, "speaker": "", "department": activity, "why": FLOOR_WHY,
             "own_department": True, "floor": True} for p in own if p not in have]
    return out


def _evidence_paths(act: dict[str, Any]) -> set[str]:
    """The files an activity's evidence quotes: grid rows, the three figures, the dependencies."""
    items = [*(act.get("grid") or {}).values(), *(act.get(f) or {} for f in ("mtpd", "rto", "rpo")),
             *(act.get("dependencies") or [])]
    return {i.get("path") for i in items if i.get("verified_quote") and i.get("quote")}


def unused_floor(draft: dict[str, Any], own: list[str]) -> list[str]:
    """Own-department interviews the draft's evidence never quotes: such a draft is not done."""
    used = set().union(*(_evidence_paths(a) for a in draft.get("activities") or [])) \
        if draft.get("activities") else set()
    return [p for p in own if p not in used]


def _figure(name: str, item: dict[str, Any], allowed: list[str] | None, derived: Any) -> list[str]:
    if item.get("kind") == "stated":
        if not item.get("verified_quote"):
            return [f"{name} is marked stated without a quote verified in its file"]
        if allowed is not None and item.get("value") not in allowed:
            return [f"{name} {item.get('value')!r} is not a value the method allows"]
        return []
    return [] if derived else [f"{name} is neither stated nor derivable by the method's rule"]


def walkable(draft: dict[str, Any], room: Path) -> list[str]:
    """The reasons this draft is NOT walkable in this room; [] when it is. 13_nemo, t66.

    Reads the room's method, register and interviews and nothing else: no model, no chat, no clock.
    The rule (ticket 66 item 3), for every drafted activity:
    1. an impact-grid row for every category of the method, and each cell at every horizon one of:
       a stated score (the row is `stated` and its quote was verified in its file), a proposal
       marked as one (the row is `proposed`), or "not stated" (MISSING);
    2. MTPD, RTO and RPO each stated (marked stated, quote verified, a value the method allows) or
       derived by the method's rule: MTPD from the grid (`derive_mtpd`), RTO from the MTPD
       (`rto_map`, where the method has one; t139), RPO from the dependencies
       (`bia_figures.impact.derive_rpo`);
    and for the draft as a whole:
    3. at least one interview filed under the activity's own department among those it rests on —
       unless none is on file at all: then nemo's stage 2 holds the interview live
       (`walk.pick_interview` offers it, `walk.held_interview` keeps it), and the draft is rebuilt
       from the room once it is filed (13_nemo, t72; no filed activity is without one);
    4. the dependency floor of ticket 01 applied: every register id an interview it rests on names
       (`bia_figures.deps.floor`) is among its dependencies.
    """
    room = Path(room)
    method = json.loads((room / METHOD).read_text())
    register = read_register(room)
    activity = (draft.get("meta") or {}).get("activity", "")
    lenses, horizons = [s["id"] for s in method["scenarios"]], method["time_horizons"]
    why: list[str] = []
    acts = draft.get("activities") or []
    if not acts:
        why.append("no activity drafted")
    rests_on = [i.get("path") for i in draft.get("interviews") or []]
    own = own_interviews(room, activity)
    if own and not set(rests_on) & set(own):
        why.append(
            f"rests on no interview filed under {activity!r} ({', '.join(own) or 'none on file'})"
        )
    need = figures_deps.floor(register, floor_texts(room, rests_on, activity))
    have = {
        d.get("asset_id") for a in acts for d in a.get("dependencies") or [] if d.get("asset_id")
    }
    if need - have:
        why.append(f"dependency floor not applied: {', '.join(sorted(need - have))} missing")
    for a in acts:
        aid, grid = a.get("id") or a.get("name"), a.get("grid") or {}
        for lens in lenses:
            row = grid.get(lens)
            if not row:
                why.append(f"{aid}: no grid row for {lens}")
                continue
            for h in horizons:  # the first bad cell speaks for its row
                cell = (row.get("scores") or {}).get(h)
                bad = "" if cell == MISSING else (
                    f"{cell!r} is neither a score nor not stated"
                    if not (isinstance(cell, int) and 1 <= cell <= 5) else
                    "stated without a quote verified in its file"
                    if row.get("kind") == "stated" and not row.get("verified_quote") else
                    "a score marked neither stated nor proposed"
                    if row.get("kind") not in ("stated", "proposed") else "")
                if bad:
                    why.append(f"{aid}.{lens} at {h}: {bad}")
                    break
        ints = {k: {h: v for h, v in (r.get("scores") or {}).items() if isinstance(v, int)}
                for k, r in grid.items()}
        derived = derive_mtpd(worst_case_row(ints), method)
        mtpd, rto, rpo = (a.get(f) or {} for f in ("mtpd", "rto", "rpo"))
        # t139 (ruling (2)'s word list): the method's word past the last horizon is an MTPD it
        # allows, and the one its rule gives a grid that never crosses; a method without the word
        # allows and derives exactly what it did
        beyond = beyond_horizons(method)
        why += _figure(f"{aid}: MTPD", mtpd, [*horizons, *([beyond] if beyond else [])],
                       (derived != NO_MTPD and derived in horizons)
                       or (derived == NO_MTPD and beyond is not None))
        # t139 (13_nemo_check's ruling (1)): a method with no rto_map derives no RTO, so nothing
        # here holds the RTO to one; the referee's _review_recovery is the guard (RTO strictly
        # inside the MTPD, or the gap flagged). A method with a map is held to it as before.
        rto_map = method.get("rto_map")
        why += _figure(f"{aid}: RTO", rto, None,
                       (rto_map.get(mtpd.get("value")) or rto_map.get(derived))
                       if rto_map is not None else True)
        own_deps = {d.get("asset_id") for d in a.get("dependencies") or [] if d.get("asset_id")}
        # 190 (the owner's "No RPO at all"): where no dependency holds data the method gives no
        # RPO, and that is a settled outcome, not a figure nobody could derive
        rpo_derived = figures_impact.derive_rpo(sorted(own_deps | need), register, method,
                                                activity or None)
        why += _figure(f"{aid}: RPO", rpo, method["rpo_vocabulary"],
                       rpo_derived.figure or rpo_derived.reason == (figures_impact.NO_DATA_HELD,))
    return why


def verify(draft: dict[str, Any], seed: Path, activity: str | None = None,
           files: dict[str, str] | None = None) -> dict[str, Any]:
    """`files`: the room files a quote may come from; the interviews unless given (t72).

    t79 fix 2: the model's reply is cut to the fields it may set (`only_the_model_s`) before
    anything here reads it, so every mark this pass writes is nemo's by construction.
    """
    sent_by_model, draft = draft, only_the_model_s(draft)
    method = json.loads((seed / "02_BCM-Method/method.json").read_text())
    register = json.loads((seed / "03_Dependencies/dependency-register.json").read_text())
    files = interviews(seed) if files is None else files
    lenses = [s["id"] for s in method["scenarios"]]
    horizons = method["time_horizons"]
    log: list[str] = []
    log += _what_the_boundary_cut(sent_by_model, draft)

    def check(where: str, item: dict[str, Any], figure: str | None) -> dict[str, Any]:
        item = dict(item or {})
        item["verified_quote"] = _quote_holds(item, files)
        if item.get("quote") and not item["verified_quote"]:
            log.append(f"{where}: quote not found verbatim in {item.get('path')!r}, removed: "
                       f"{str(item.get('quote'))[:120]!r}")
            item["dropped_quote"] = item.get("quote")
            item["quote"] = ""
        if item.get("kind") == "stated":
            ok = item["verified_quote"] and (
                figure is None or _figure_in_quote(figure, item["quote"])
            )
            if not ok:
                log.append(f"{where}: marked stated but the figure {figure!r} is not in a verified "
                           "quote, so it is now a proposal")
                item["kind"] = "proposed"
                # t79 fix 1: nemo's note about the model's sentence goes beside it, never inside
                # it. Appending here put nemo's own words in the middle of a quote the card then
                # printed as the model's, which is the defect ticket 79 exists to fix.
                item["check_note"] = CHECK_NOTE
        return item

    out: dict[str, Any] = {"interviews": [], "activities": [], "conflicts": [],
                           "gaps": draft.get("gaps") or [], "verify_log": log}
    for iv in draft.get("interviews") or []:
        # t79 fix 4: `path` is a file name nemo looks a room file up BY, so a model that sends a
        # list there is `TypeError: unhashable type: 'list'` out of this line — the same class as
        # the conflict with no `id`, one level down: a leaf the prompt asks for as a string, used
        # as a key. Not a string, not a path; the interview is dropped and said so, which is what
        # this loop already does with a path that is not a room file.
        if isinstance(iv.get("path"), str) and iv["path"] in files and is_interview(iv["path"]):
            out["interviews"].append(iv)
        else:
            log.append(
                f"interview {iv.get('path')!r} is not an interview file in the seed, dropped"
            )
    for act in draft.get("activities") or []:
        aid = act.get("id") or act.get("name")
        rows = {}
        for row in act.get("grid") or []:
            lens = row.get("lens")
            if lens not in lenses:
                log.append(f"{aid}: category {lens!r} is not a method id, dropped")
                continue
            # t79 fix 4: the prompt asks for `scores` as an object keyed by horizon, and this
            # line reads it with `.get` — a list (or a list of pairs, or a scalar) raised
            # `AttributeError` here. A row whose scores are no object has no score at any horizon,
            # which is the state `MISSING` below already says and the log already reports.
            sent = row.get("scores")
            scores = {h: (sent.get(h) if isinstance(sent, dict) else None) for h in horizons}
            bad = [h for h, v in scores.items() if not (isinstance(v, int) and 1 <= v <= 5)]
            for h in bad:
                scores[h] = MISSING
            if bad:
                log.append(f"{aid}.{lens}: no valid score at {bad}")
            digits = " ".join(str(v) for v in scores.values() if isinstance(v, int))
            checked = check(f"{aid}.{lens}", {**row, "scores": scores}, None)
            if checked.get("kind") == "stated" and not all(
                re.search(rf"(?<!\d){d}(?!\d)", norm(checked["quote"])) for d in digits.split()
            ):
                log.append(f"{aid}.{lens}: stated scores not all in the quote, now a proposal")
                checked["kind"] = "proposed"
            rows[lens] = checked
        for lens in lenses:
            # t79 fix 1: `floor` marks a reason nemo composed, the way `with_floor` marks an
            # interview nemo put back, so a card attributes it to nemo and not to the draft
            rows.setdefault(lens, {"lens": lens, "scores": dict.fromkeys(horizons, MISSING),
                                   "kind": "none", "quote": "", "reason": NOTHING_DRAFTED,
                                   "floor": True})
        grid = {lens: rows[lens]["scores"] for lens in lenses}
        derived = derive_mtpd(worst_case_row({k: {h: v for h, v in r.items() if isinstance(v, int)}
                                              for k, r in grid.items()}), method)
        mtpd = check(f"{aid}.mtpd", act.get("mtpd"), (act.get("mtpd") or {}).get("value"))
        rto = check(f"{aid}.rto", act.get("rto"), (act.get("rto") or {}).get("value"))
        rpo = check(f"{aid}.rpo", act.get("rpo"), None)
        if rpo.get("value") not in method["rpo_vocabulary"]:
            log.append(f"{aid}.rpo: {rpo.get('value')!r} is not in the method vocabulary")
            rpo["kind"] = "proposed"
        deps = []
        for d in act.get("dependencies") or []:
            d = check(f"{aid}.dep", d, None)
            # t79 fix 4: `asset_id` is looked up in the register, so a list there is
            # `TypeError: unhashable type` — an id that is no string resolves to no asset, and
            # takes the branch this line already has for an id the register does not name.
            if d.get("asset_id") and (not isinstance(d["asset_id"], str)
                                      or d["asset_id"] not in register):
                log.append(f"{aid}.dep: asset id {d['asset_id']!r} not in the register, cleared")
                d["asset_id"] = ""
            deps.append(d)
        conflicts_extra = []
        if mtpd.get("value") and derived and mtpd["value"] != derived:
            year = grid_year(rows, seed)
            conflicts_extra.append(
                {
                    "id": f"{aid}-MTPD-RULE",
                    "activity": aid,
                    "about": RULE_ABOUT.format(year=f" ({year})" if year else "",
                                               derived=derived, said=mtpd["value"]),
                    "sides": [
                        {
                            "claim": RULE_CLAIM.format(derived=derived,
                                                       year=f", {year}" if year else ""),
                            "quote": "",
                            "path": "02_BCM-Method/method.json",
                            "speaker": "method",
                        },
                        {
                            "claim": f"{mtpd['value']} ({mtpd.get('kind')})",
                            "quote": mtpd.get("quote", ""),
                            "path": mtpd.get("path", ""),
                            "speaker": mtpd.get("speaker", ""),
                        },
                    ],
                    # t79 fix 1: nemo's own conflict, so `floor` and nemo's own `why`
                    "recommend": 0,
                    "floor": True,
                    "why": RULE_WHY,
                }
            )
        out["activities"].append(
            {
                # t79 fix 5: `""`, not `None` — a model that sent no name (or one the filter dropped
                # for not being a string) otherwise put `None` on the card he signs, where it
                # prints.
                "id": aid,
                "name": act.get("name") or "",
                "owner": check(f"{aid}.owner", act.get("owner"), None),
                "grid": rows,
                "derived_mtpd": derived,
                "mtpd": mtpd,
                "rto": rto,
                "rpo": rpo,
                "dependencies": deps,
            }
        )
        out["conflicts"] += conflicts_extra
    for c in draft.get("conflicts") or []:
        c = dict(c)
        c["sides"] = [check(f"conflict {c.get('id')}", s, None) for s in c.get("sides") or []]
        out["conflicts"].append(c)
    if activity:
        _apply_floors(out, seed, activity, log)
    out[MARKED_BY_NEMO] = True  # t79 fix 2: nemo's stamp, written after the filter
    return out


def _apply_floors(out: dict[str, Any], seed: Path, activity: str, log: list[str]) -> None:
    """The interview floor and the dependency floor, after the checks. 13_nemo, t66.

    Marked in `out["floor"]` so a floor addition is visible: the interviews added back, the
    register ids added from the interviews' own words, and the own-department interviews the
    evidence still never quotes (a draft with any of those is not done).
    """
    own = own_interviews(seed, activity)
    before = {i["path"] for i in out["interviews"]}
    out["interviews"] = with_floor(out["interviews"], own, activity)
    after = {i["path"] for i in out["interviews"]}
    added = [p for p in own if p not in before]
    for p in sorted(before - after):
        log.append(f"interview {p!r} is from another department and gives no reason, dropped")
    for p in added:
        log.append(
            f"interview {p!r} is filed under {activity!r} and was left out: added back (floor)"
        )
    register = json.loads((seed / REGISTER).read_text())
    have = {
        d.get("asset_id") for a in out["activities"] for d in a["dependencies"] if d.get("asset_id")
    }
    need = figures_deps.floor(register, floor_texts(seed, sorted(after), activity))
    deps_added = sorted(need - have)
    if out["activities"] and deps_added:
        out["activities"][0]["dependencies"] += [
            {"heard": "named in an interview this draft rests on", "asset_id": asset, "quote": "",
             "path": "", "floor": True} for asset in deps_added]
        log.append(
            f"dependency floor: {', '.join(deps_added)} added from the interviews' own words"
        )
    out["floor"] = {"interviews_added": added, "dependencies_added": deps_added,
                    "unused_own_interviews": unused_floor(out, own)}


def _apply_risk_floor(out: dict[str, Any], room: Path, activity: str) -> None:
    """An added activity's draft: the risk-register floor (t72b), shown where the dependency floor
    shows — the `floor` block and the verify log — and held in `risk_rows` at the draft's top level,
    so merging sub-steps at the agreed scope (`collapse_to_scope`) keeps it."""
    out["risk_rows"] = risk_floor(room, activity)
    ids = [r["id"] for r in out["risk_rows"]]
    out.setdefault("floor", {})["risk_rows_added"] = ids
    if ids:
        out["verify_log"].append(f"risk-register floor: {', '.join(ids)} attached from "
                                 f"{RISK_REGISTER} (the row names {added_name(room, activity)!r})")


REQUIRED = """

REQUIRED (the previous draft left these out of its evidence): the interviews below are filed under \
"{activity}"'s own department. Use EACH of them: quote it, verbatim, in at least one grid row, \
figure or dependency of this activity.
{paths}
"""

#: What an added activity's prompt carries besides the unchanged PROMPT (13_nemo, t72): where it
#: came
#: from, and the room's other files, which count as evidence exactly as the interviews do.
ADDED = """

"{activity}" is not filed under any department in this room: the BCM manager named it. Besides the \
interviews, the room's other files are below. They are evidence exactly as the interviews are: \
quote them verbatim, with the path as given. Under "interviews" list only files from \
07_Interviews/ \
or output/owner-interviews/.

ROOM FILES:
{files}
"""


def _ask(model: str, prompt: str, room: Path | None = None) -> tuple[str, dict[str, Any], float]:
    t0 = time.time()
    msg = lanes.chat(
        model,
        [{"role": "user", "content": prompt}],
        max_tokens=DRAFT_MAX_TOKENS,
        json_mode=True,
        room=room,
    )  # t109: a draft built in a room is on that room's turn file
    return msg.get("content") or "", msg.get("_usage") or {}, round(time.time() - t0, 1)


def _parse(text: str) -> dict[str, Any]:
    # why: a JSON object
    return json.loads(text[text.index("{"): text.rindex("}") + 1])  # type: ignore[no-any-return]


#: What the drafting prompt says an RTO looks like (t139, 13_nemo_check's ruling (3)). A method with
#: an `rto_map` is named as the place its RTO words come from, exactly as before; a method without
#: one has no RTO words to name, so the RTO is a duration strictly inside the MTPD and nothing is
#: said about a map it does not have.
RTO_LIKE_MAP = 'like "< 8 h" (method rto_map)'
RTO_LIKE_DURATION = 'a duration strictly inside the MTPD, like "8 h",'


def mtpd_values(method: dict[str, Any]) -> str:
    """t139 (a): what the prompt adds to "MTPD value must be one of the horizons": the method's own
    word past the last horizon where it states one, so a >168 h record is not steered to "168 h".
    Nothing for a method without the word, whose prompt stays byte for byte what it was."""
    beyond = beyond_horizons(method)
    return f', or {json.dumps(beyond, ensure_ascii=False)} where the grid never reaches the ' \
        'intolerable level at any horizon' if beyond else ""


def rto_like(method: dict[str, Any]) -> str:
    """The prompt's words for an RTO: the method's rto_map only where the method has one. t139
    (the owner's rulings (b), (c)): a method with a beyond word also allows that word as the RTO
    where the MTPD is past the last horizon too, so the draft is not steered to a gap."""
    if method.get("rto_map"):
        return RTO_LIKE_MAP
    beyond = beyond_horizons(method)
    if not beyond:
        return RTO_LIKE_DURATION
    word = json.dumps(beyond, ensure_ascii=False)
    return f'{RTO_LIKE_DURATION.rstrip(",")}; {word} where the MTPD is {word} too (past the last ' \
        'horizon);'


def rto_stated(method: dict[str, Any]) -> str:
    """t139 (b): a stated RTO is carried as stated. Said only to a method with a beyond word, so the
    old method's prompt stays byte for byte what it was."""
    beyond = beyond_horizons(method)
    if not beyond:
        return ""
    word = json.dumps(beyond, ensure_ascii=False)
    return (' An RTO the interviewee states is carried as stated: kind "stated", the exact words '
            f'quoted; a stated {word} over an MTPD past the last horizon is such an RTO, never a '
            'recovery gap.')


def _draft(
    activity: str, model: str, seed: Path, out_dir: Path, added: bool = False
) -> dict[str, Any] | None:
    """Draft one activity and verify it; write `<slug>.<model>.{raw.txt,json}` into `out_dir`.

    `added` (13_nemo, t72): the activity is one a manager added to this room, so the room's other
    evidence files go into the prompt (`ADDED`) and a quote may come from any of them. Otherwise
    this is the once-per-seed draft exactly as before. An added activity's draft whose own
    interviews changed while the model was answering (its interview was filed meanwhile) is stale:
    it is dropped and None comes back, because a later draft already reads the room as it is now.
    """
    own_at_start = own_interviews(seed, activity) if added else None
    slug = re.sub(r"[^a-z0-9]+", "-", activity.lower()).strip("-")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path, out_path = out_dir / f"{slug}.{model}.raw.txt", out_dir / f"{slug}.{model}.json"
    method = json.loads((seed / "02_BCM-Method/method.json").read_text())
    files = interviews(seed)
    sources = room_files(seed) if added else files
    prompt = PROMPT.format(
        rto_like=rto_like(method), mtpd_values=mtpd_values(method), rto_stated=rto_stated(method),
        activity=activity, lenses=", ".join(s["id"] for s in method["scenarios"]),
        horizons=", ".join(method["time_horizons"]), rpo=json.dumps(method["rpo_vocabulary"]),
        method=json.dumps(method, ensure_ascii=False), register=register_lines(seed),
        interviews="\n\n".join(f"=== FILE: {p} ===\n{t}" for p, t in files.items()))
    if added:
        prompt += ADDED.format(activity=activity, files="\n\n".join(
            f"=== FILE: {p} ===\n{t}" for p, t in sources.items() if p not in files))
    text, usage, seconds = _ask(model, prompt, room=seed if added else None)
    if added and own_interviews(seed, activity) != own_at_start:
        return None  # stale (t72 fix 2): the room gained an interview while this one was drafted
    raw_path.write_text(text)
    verified = verify(_parse(text), seed, activity, sources)
    calls: list[dict[str, Any]] = [{"seconds": seconds, "usage": usage}]
    missing = verified["floor"]["unused_own_interviews"]
    if missing:  # the smallest honest remedy: once more, naming what it left out
        first = out_dir / f"{slug}.{model}.raw-first.txt"
        first.write_text(text)
        text, usage, seconds = _ask(
            model,
            prompt + REQUIRED.format(activity=activity, paths="\n".join(f"- {p}" for p in missing)),
            room=seed if added else None,
        )
        if added and own_interviews(seed, activity) != own_at_start:
            return None
        raw_path.write_text(text)
        verified = verify(_parse(text), seed, activity, sources)
        calls.append({"seconds": seconds, "usage": usage, "redraft_for": missing})
    verified["meta"] = {
        "activity": activity,
        "model": model,
        "lane": lanes.MODELS[model],
        "seconds": round(sum(c["seconds"] for c in calls), 1),
        "usage": calls[-1]["usage"],
        "calls": calls,
        "cost": round(sum(float((c["usage"] or {}).get("cost") or 0) for c in calls), 4),
        "made": time.strftime("%Y-%m-%d %H:%M"),
    }
    if added:
        verified["meta"].update(added=True, own_interviews=own_interviews(seed, activity),
                                sources=sorted(p for p in sources if p not in files))
        _apply_risk_floor(verified, seed, activity)
    tmp = out_path.with_suffix(
        ".json.tmp"
    )  # a reader never sees half a draft (t72: drafted in the background)
    tmp.write_text(json.dumps(verified, indent=1, ensure_ascii=False))
    if added and out_path.exists():  # the draft it replaces is kept beside it, never lost
        out_path.replace(
            out_dir / f"{slug}.{model}.superseded-{time.strftime('%Y%m%d-%H%M%S')}.json"
        )
    tmp.replace(out_path)
    return verified


def draft_in_room(room: Path, activity: str, model: str) -> dict[str, Any] | None:
    """An added activity's draft, built in this room from this room's files. 13_nemo, t72."""
    return _draft(activity, model, room, room / ROOM_DRAFTS, added=True)


def main() -> None:
    """python PROTOTYPE_draft.py <activity> <model> [seed] [--reverify]

    --reverify runs the verify pass (and the floors) again over the saved raw answer, no model call.
    A draft whose evidence never quotes an own-department interview is re-drafted once with those
    interviews named as required (13_nemo, t66); if it still misses one, it is written and marked.
    """
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    activity, model = args[0], args[1]
    seed = Path(args[2]) if len(args) > 2 else SEED
    slug = re.sub(r"[^a-z0-9]+", "-", activity.lower()).strip("-")
    DRAFTS.mkdir(parents=True, exist_ok=True)
    raw_path, out_path = DRAFTS / f"{slug}.{model}.raw.txt", DRAFTS / f"{slug}.{model}.json"
    if "--reverify" in sys.argv:
        if not out_path.exists():  # a fixture is reverified into the cache, never in place (t176)
            raw_path, out_path = FIXTURES / raw_path.name, FIXTURES / out_path.name
        meta = json.loads(out_path.read_text())["meta"]
        verified = verify(_parse(raw_path.read_text()), seed, activity)
        verified["meta"] = {**meta, "reverified": time.strftime("%Y-%m-%d %H:%M")}
        out_path = DRAFTS / out_path.name
        out_path.write_text(json.dumps(verified, indent=1, ensure_ascii=False))
    else:
        lanes.note_purpose("draft")  # t33 fix 1: the one purpose that is not capped at 30 s a try
        # why: the CLI drafts with added=False, and _draft returns None only for added=True
        verified = _draft(activity, model, seed, DRAFTS)  # type: ignore[assignment]
    acts = verified["activities"]
    stated = sum(1 for a in acts for r in a["grid"].values() if r.get("kind") == "stated")
    proposed = sum(1 for a in acts for r in a["grid"].values() if r.get("kind") == "proposed")
    print(
        json.dumps(
            {
                "model": model,
                "seconds": verified["meta"]["seconds"],
                "cost": verified["meta"].get("cost"),
                "calls": len(verified["meta"].get("calls") or [1]),
                "interviews": len(verified["interviews"]),
                "activities": [a["name"] for a in acts],
                "rows_stated": stated,
                "rows_proposed": proposed,
                "conflicts": len(verified["conflicts"]),
                "gaps": len(verified["gaps"]),
                "verify_problems": len(verified["verify_log"]),
                "floor": verified["floor"],
                "walkable": walkable(verified, seed) or "yes",
            },
            indent=1,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
