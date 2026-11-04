"""Ticket 399 step 1: the prompt check's code checks, its runner and its scorer. No model call here.

At a table of 50, a prompt that works 9 times in 10 fails for someone. So each of the workshop's 18
prompts (the A4 sheet, `prompt-check/prompts.json`) is reworded ~20 ways, each wording is sent 5
times into fresh rooms, and it passes only if all 5 pass (pass^5). The practice behind it is
`docs/research/agent-eval-practice-2026-10.md`: read the failures first, code checks before any AI
judge.

**The checks are code on one turn**, the turn that answered the line, read from the room's turn
file and nothing else. `CHECKS` is the one registry: each named check takes the turn and what the
prompt expects and returns its reasons to fail, none when it passes. His failure types from the
open coding are added later as entries here, one name each, and nothing else changes.

- ``route``: the tool, tap or card the prompt needs fired (`prompt-check/routes.json`).
- ``no-refusal``: nemo's own words decline nothing (quoted words are the room's, not a refusal,
  a quote left open too; "I can't tell … from the files" says what the files hold, r4; so does an
  honest limit, "What I can't see: whether …", "what I can't confirm from the files", r5).
- ``facts``: every expected fact of the prompt's "A good answer" cell in
  `seed-marks-387-m12-399v-m18.md` (Move 18: 488's A6/B6, 481 (r2)'s euro line; -399v beside it)
  (the sheet for the w2 seed M12 swaps in, 418's functions; the W1 one, `-m11`, is kept beside it
  and the pre-W1 one is in `prompt-check/archive/`) is in
  what he sees (`shown`): the reply, the cards and tables, the taps, the chart code drew and the
  files the turn produced (`drawn`). Facts are read from the cell by code, never retyped: its
  hours, dates, times, quoted words, the spellings of `SAME`, the functions of the marks' own
  function table, where the holder's name counts too, and every **bold** word (r5, 14_marschkamp's
  rule: held from a word start, any case, so "technicians" holds **technician**). Each fact keeps
  its cell (`Fact.cell`), so a reason to fail names the prompt, the column and the words of the
  cell it came from.
- ``rating-pairs``: every class nemo rates at a horizon ("financial high at 72 h") is rated as the
  seed's grids for the task's activity rate it, last year's record's or this year's interview's,
  read by the app's own readers (r5: A5-14's "financial low/medium from 72 h" where both say not).
- 474, his notes on 387, each hard: ``options-fit`` (C1) fails a stage's own tap under a typed
  line the model answered without a step, the turn's kind read from its tools and server, never
  its text; ``mail-tap`` (C2 b, c) wants a tap drafting a mail where the turn names a gap needing an
  owner's word, or where his typed line asks for an e-mail (the app's `asks_to_write`);
  ``one-count`` (C3) holds a Keep turn's every count to its card's, across the room too, and a
  count outside it to the interviews' front matter.
- 477 (D2, his "Every answer (Recommended)"), hard: ``plain-words`` fails system talk
  (`SYSTEM_TALK`: "side 1 / side 2", "the method derives …", "the live graph has no …"), a BCM
  term the app's naming leaves with no plain words in that answer, and a list written as one line
  (`one_line_lists`). Never a length: no check counts or flags one. It flags; nothing rewrites.
- ``functions-first`` (soft, `SOFT`): the marks' rule that a function is named, not only the
  person who holds it. It flags a turn and never fails it.
- 498, hard: ``agent-marks``, an agent case's own marks (`AGENT_MARKS`); none for a sheet prompt.
- 557, hard: after a named day's card (544), the ``facts`` check fails a model sentence naming an
  interview, a day or an activity other than the card's (the card's own blocks and closing pointer
  are code's words), and the ``taps`` check fails a tap opening an activity other than the card's.
  Both are the subjects those checks already read, so each keeps its name and axis.

**The runner** (`run`) sends each case into fresh rooms one at a time, k times, and keeps every
room's turn file under the out folder; **the scorer** (`score`) reads only those saved files. The
sender is a parameter: `browser_sender` drives the phone app through a check proxy the way the
run-7 walk did; the tests hand in a fake. A case is its lines: the task's prompts before it as the
sheet words them, then the wording under test, which is the line checked. A sequence case
(out of order, off-script) checks every sheet prompt in it and none of its off-script lines.

**The variants file** (`~/work/nemo-builds/t399-variants.md`, 34_nemo_check signs it) is parsed
here. A third of each prompt's wordings is held back by a fixed seeded rule (`held_back`) and
never used to tune; `mark` writes that column, and `variants` refuses a file whose marks differ.

    prompt_check.py verdicts <turn file>...     every sheet prompt's turn in each file, judged
    prompt_check.py mark <variants.md>          write the held-back column by the rule
    prompt_check.py plan <variants.md>          the cases and their counts, sending nothing
    prompt_check.py score <variants.md> <out>   pass^5 per case, a score per prompt
    prompt_check.py run <variants.md> <room> <out> [--open]   send every case k times (model walk)
    prompt_check.py check-briefs <full variants.md> <dir>...  files holding held-back words
    prompt_check.py redact <full variants.md> <tree variants.md>  the tree's copy, ids only

**455: a case marked to open its activity** (`opens`, `opened`). 10_nemo_design marks a cell
`<br>opens: <activity>` in the tree's `prompt-check/variants.md` (run 2's seven only; a new marker
is his case-design change, never inferred). With `--open` (off by default, so run 2's k=5 resume
sends the cases unchanged) a marked case runs with that activity open, as a delegate on stage
would have it: r2 (his ruling, option c) puts ONE setup line before its lines, the workshop's
start line for the activity (`setup_line`), which opens it through the app's own path. The setup
line is never scored: the case's targets move one line down. `Case.opens` records the activity.

**456: the held-back words stay outside the tree.** The tree's variants file keeps each held-back
case's id, mark and marker only, its words `REDACTED`; the full sheet is the path given to plan,
score or run. A new case is written and marked in the full sheet, outside the tree, and `redact`
writes the tree's copy from it, so a held-back case's words never pass through the tree. Given
the tree's file, plan, score and run take the practice cases only and say so. `leaks` (and
`check-briefs`) names each file holding a held-back case's words by file and case id only.

**498 (ADR-0053 slice 10): the agent cases and the demo's go/no-go.** The 15 prototype asks
(v3's A6, B5 and B6, v4's twelve) are practice cases read from the seed seat's expected answers,
copied into the tree whole (`AGENT_CASES`). v3's three are their sheet prompts and cells; each of
v4's twelve is checked by every check and its own marks (`AGENT_MARKS`), each count in them
counted from the seed by code. A case passes only if all 4 of its runs pass (`AGENT_K`).
`agent_report` gives the code half of the go/no-go; his blind marks on the 12 are the other half
(`HIS_MARKS`), never read here. Nothing here reads or sets the agent's switch: he flips it.

    prompt_check.py agent-plan                  the agent cases, sending nothing
    prompt_check.py agent-run <room> <out>      send each case k=4 times (model walk)
    prompt_check.py agent-score <out>           per agent case, did all 4 runs pass
    prompt_check.py agent-report <out>          the go/no-go's code half, his half a slot

Langfuse is not here: an export publishes the saved turn files later (ADR-0020).
"""
from __future__ import annotations

import datetime
import functools
import hashlib
import html
import json
import os
import re
import shutil
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NamedTuple

DATA = Path(__file__).resolve().with_name("prompt-check")
PROMPTS = DATA / "prompts.json"
#: Move 18: 488's A6/B6 and 481 (r2)'s euro line in A3/A4 on the 399v cells (A4 B2 B4 B5);
#: -399v stays beside it, as -m12 did
MARKS = DATA / "seed-marks-387-m12-399v-m18.md"
ROUTES = DATA / "routes.json"
#: how many times each case runs; it passes only if every run passes (pass^k)
K = 5
#: the held-back rule's seed: change it and every mark in the variants file changes
SEED = "t399"
#: the sheet's one blank (B8), filled by whoever types it
BLANK = "[day and time]"
#: seconds `browser_sender` gives its check proxy to stop on SIGTERM
PROXY_WAIT = 20.0

Turn = Mapping[str, Any]


# ---- what each prompt expects, read by code ------------------------------------------------

#: one fact, several spellings, defined once: an answer holding any spelling holds the fact, and
#: a cell holding any spelling expects it (34_nemo_check's ruling on ticket 399, 2026-10-10)
SAME: tuple[tuple[str, ...], ...] = (
    ("72 h", "3 days"),
    (">168 h", "more than a week"),
)
#: facts a cell writes that an answer need not state, each with why (prompt id, fact as normalised)
NOT_REQUIRED: dict[tuple[str, str], str] = {
    ("B9", "9 nov"): "the cell's \"(production's 9 Nov finding, ...)\" says where the finding came "
                     "from; what B9 asks to check is the switchover, not the date",
}


@dataclass(frozen=True)
class Fact:
    #: the fact as normalised, the first of its spellings
    said: str
    #: every normalised spelling that holds it: `SAME`'s, or a function and its holder's names
    spellings: tuple[str, ...]
    #: "hours", "date", "time", "quote", "same", "function" or "bold"
    kind: str
    #: where the marks write it: (prompt id, column, the words of the cell holding it)
    cell: tuple[str, str, str]
    #: a quote's clauses (split at '.', ';' and ','), each normalised: the quote is also held when
    #: every one of them is said, whole, wherever its punctuation and quote marks fall (r4)
    clauses: tuple[str, ...] = ()


@dataclass(frozen=True)
class Ratings:
    """What the seed rates, read by the app's own readers (r5): the task's activity, and every
    other activity of the process map, which counts where a reply names it."""
    activity: str
    #: each class's words, lower case (its id and its name), with its id
    classes: tuple[tuple[str, str], ...]
    #: the method's scale labels
    scale: tuple[str, ...]
    #: (activity, class id, horizon, label) as last year's record's grid or this year's
    #: interview's rates it, for every activity of the map
    held: frozenset[tuple[str, str, str, str]]
    #: each activity of the map with the words that name it in a reply: its slug as words ("&"
    #: read as "and") and its map number ("1.3")
    names: tuple[tuple[str, tuple[str, ...]], ...]
    #: activities with an interview this year that states no grid code reads (order picking's and
    #: dispatch's of 2 Oct say it in prose): their ratings this year are not known
    blind: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str
    route: str
    facts: tuple[Fact, ...]
    #: the task's grids, for `rating_pairs`; None where the seed holds none (r5)
    ratings: Ratings | None = None
    #: 498: an agent case's own marks, by its id in `AGENT_MARKS`; "" for a sheet prompt
    marks: str = ""


def sheet(path: Path = PROMPTS) -> dict[str, str]:
    """The A4 sheet's prompts by id, A1..A9 and B1..B9."""
    tasks = json.loads(path.read_text(encoding="utf-8"))
    return {f"{task}{n}": text for task, texts in tasks.items()
            for n, text in enumerate(texts, 1)}


def _rows(text: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.strip().strip("|").split("|")]
            for line in text.splitlines() if line.startswith("|")]


def cells(text: str) -> dict[str, str]:
    """Each prompt's corrected "A good answer" cell, its *(…)* notes on the old cell taken out."""
    return {row[0]: re.sub(r"\*\(.*?\)\*", "", row[2]) for row in _rows(text)
            if len(row) >= 3 and re.fullmatch(r"[AB]\d", row[0])}


def column(text: str) -> str:
    """The header of the cells' column, as the marks' first table names it."""
    return _rows(text)[0][2]


def activities(text: str) -> dict[str, str]:
    """Each task's activity, as its marks heading names it: "## Task A: production and processing
    (…)" or "## Task B: next week's BIA = raw material procurement (…)", as a slug."""
    return {task: re.split(r"[:=]", head.split("(")[0])[-1].strip().replace(" ", "-")
            for task, head in re.findall(r"^## Task ([AB]): (.+)$", text, re.M)}


@functools.cache
def _graded(seed: Path) -> Ratings | None:
    """Every map activity's grids, last year's record's and this year's interview's, as the chart
    reads them (`PROTOTYPE_core`); None for a seed without a method."""
    if not (seed / "02_BCM-Method/method.json").is_file():
        return None
    import impact_chart

    import PROTOTYPE_core as core

    method = json.loads((seed / core.walk.METHOD).read_text(encoding="utf-8"))
    label = {s["level"]: s["label"] for s in method["severity_scale"]}
    held, names, blind = set(), [], set()
    for row in core.process_map_rows(seed):
        last = impact_chart.from_record(core.last_year(seed, row.slug).get("grid"), method) or {}
        this, when = core.this_years_interview(seed, row.slug, method)
        if when and not this:
            blind.add(row.slug)
        held |= {(row.slug, c, h, label[v]) for grid in (last, this) for c, cells in grid.items()
                 for h, v in cells.items() if v in label}
        names.append((row.slug, (row.slug.replace("-", " "), row.number)))
    return Ratings(
        "",
        tuple((w, s["id"]) for s in method["scenarios"]
              for w in dict.fromkeys((s["id"], s["name"].lower()))),
        tuple(label.values()), frozenset(held), tuple(names), frozenset(blind))


def ratings(seed: Path, activity: str) -> Ratings | None:
    """`Ratings` for a task's `activity`, from the seed's grids (`_graded`)."""
    graded = _graded(seed)
    return replace(graded, activity=activity) if graded else None


def holders(text: str) -> dict[str, str]:
    """The marks' function table: each function (the text before its first ';' or ','), and the
    person the seed gives it to."""
    table = text.split("## Functions per person", 1)[1]
    return {re.split(r"[;,]", row[1])[0].strip(): row[0] for row in _rows(table)[2:]}


def functions(text: str) -> tuple[str, ...]:
    return tuple(holders(text))


_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH = re.compile(r"\b(" + "|".join(
    ["january", "february", "march", "april", "june", "july", "august", "september", "october",
     "november", "december", "sept", *_MONTHS]) + r")\b\.?")
_HOURS = re.compile(r"(\d+)\s*(?:hours?|hrs?|h)\b")
_DATE = re.compile(r"\b(\d{1,2}) (" + "|".join(_MONTHS) + r")\b")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                         " ": " ", " ": " "})


def norm(text: str) -> str:
    """One spelling for comparing: lower case, straight quotes, "72 hours" as "72 h", a month as
    its first three letters, no markdown emphasis, no sentence stops, single spaces."""
    text = text.translate(_QUOTES).lower().replace("**", "").replace("`", "")
    text = _HOURS.sub(r"\1 h", text)
    text = _MONTH.sub(lambda m: m.group(1)[:3], text)
    return re.sub(r"\s+", " ", re.sub(r"[.,;!?](?=[\s'\"]|$)", " ", text)).strip()


def bare(text: str) -> str:
    """`norm`, its quote marks taken out too: where a clause is looked for."""
    return re.sub(r"\s+", " ", norm(text).replace('"', " ")).strip()


def clauses(quote: str) -> tuple[str, ...]:
    """A quote's clauses, split at '.', ';' and ',', each as `bare` spells it."""
    return tuple(c for c in map(bare, re.split(r"[.;,]", quote)) if c)


def _where(cell: str, spellings: Sequence[str]) -> str:
    """The words of the cell holding a fact: its first clause (cut at '.', ';' or ':') that does."""
    clauses = [c.strip() for c in re.split(r"(?<=[.;:])\s+", cell) if c.strip()]
    return next((c for c in clauses if any(holding(s).search(norm(c)) for s in spellings)),
                cell.strip())


def facts(cell: str, roles: Mapping[str, str] | Iterable[str], pid: str = "",
          head: str = "") -> tuple[Fact, ...]:
    """The facts an answer must hold, each traced to the cell: hours (">168 h" kept apart from
    "168 h"), day-and-month dates, clock times, quoted words of three words or more (a quote ending
    in "…" is a template, held by its words before it; a quote is also held when each of its
    `clauses` is said), the spellings of `SAME`, every function
    the cell names, which its holder's full name or surname also holds, and every **bold** word or
    words (a bold function is its function's fact). `NOT_REQUIRED` takes its facts out."""
    said = norm(cell)
    names = roles if isinstance(roles, Mapping) else dict.fromkeys(roles, "")
    found: list[tuple[str, str, tuple[str, ...]]] = []
    found += [(f"{n} h", "hours", ()) for n in re.findall(r"(>?\d+) h\b", said)]
    found += [(f"{d} {m}", "date", ()) for d, m in _DATE.findall(said)]
    found += [(t, "time", ()) for t in re.findall(r"\b\d{1,2}:\d{2}\b", said)]
    quoted = [q.removesuffix("…") for q in re.findall(r'"([^"]+)"', cell.translate(_QUOTES))
              if len(q.split()) >= 3]
    found += [(norm(q), "quote", clauses(q)) for q in quoted]
    out: dict[str, Fact] = {}
    for fact, kind, parts in found:
        group = next((g for g in SAME if fact in g), (fact,))
        out.setdefault(group[0], Fact(group[0], group, kind, (pid, head, ""), parts))
    for group in SAME:
        if group[0] not in out and any(holding(s).search(said) for s in group):
            out[group[0]] = Fact(group[0], group, "same", (pid, head, ""))
    for role, person in names.items():
        if role in cell:
            spelt = (norm(role), *((norm(person), norm(person.split()[-1])) if person else ()))
            out.setdefault(spelt[0], Fact(spelt[0], spelt, "function", (pid, head, "")))
    out |= {b: Fact(b, (b,), "bold", (pid, head, ""))
            for b in map(norm, re.findall(r"\*\*(.+?)\*\*", cell)) if b not in out}
    return tuple(Fact(f.said, f.spellings, f.kind, (pid, head, _where(cell, f.spellings)),
                      f.clauses)
                 for f in out.values() if (pid, f.said) not in NOT_REQUIRED)


def prompts(marks: Path = MARKS, sheet_at: Path = PROMPTS, routes_at: Path = ROUTES,
            seed: Path | None = None) -> dict[str, Prompt]:
    """Every sheet prompt with its route, its facts and its task's `ratings` from `seed` (else
    `NEMO_SEED`, as `seed_of`)."""
    text = marks.read_text(encoding="utf-8")
    good, roles, head = cells(text), holders(text), column(text)
    routes = json.loads(routes_at.read_text(encoding="utf-8"))["routes"]
    seed = seed or seed_of(Path("."))
    graded = {task: ratings(seed, activity) for task, activity in activities(text).items()}
    return {pid: Prompt(pid, wording, routes.get(pid, "answer"),
                        facts(good[pid], roles, pid, head), graded.get(pid[0]))
            for pid, wording in sheet(sheet_at).items()}


# ---- the checks: code on one turn ---------------------------------------------------------

def shown(turn: Turn) -> str:
    """What he sees: nemo's reply, the cards and tables code drew, the taps offered, and the
    `elements` `drawn` added (the chart's words, the files the turn produced)."""
    return "\n".join([str(turn.get("reply") or ""), *map(str, turn.get("cards") or []),
                      *map(str, turn.get("options") or []), *map(str, turn.get("elements") or [])])


_TAG = re.compile(r"<style\b.*?</style>|<script\b.*?</script>|<[^>]*>", re.S)


def words_of(markup: str) -> str:
    """The words a page or a chart shows: its tags, styles and scripts taken out."""
    return html.unescape(re.sub(r"\s+", " ", _TAG.sub(" ", markup))).strip()


def model_led(turn: Turn) -> bool:
    """600: a turn the model led. Every chat turn has a `path` now; the brake's is never one of
    t532's `LED_PATHS`, and a turn written before 600 has none."""
    import PROTOTYPE_core as core

    return turn.get("path") in core.LED_PATHS


def chart_of(turn: Turn, seed: Path) -> str:
    """The words of the chart a chart turn showed. The turn file keeps no chart, only its "Show
    the grid" tap naming the activity, so the chart is drawn again from `seed` by the app's own
    code (`PROTOTYPE_core.activity_chart`); "" for a turn that drew none. 534: a model-led turn's
    chart is drawn from its artefact's arguments (`charts_shown`), its activities and classes."""
    import PROTOTYPE_core as core

    if model_led(turn):
        method = json.loads((seed / core.walk.METHOD).read_text(encoding="utf-8"))
        return " ".join(words_of(core.activity_charts(seed, act, method, c["classes"])[0])
                        for c in charts_shown(turn) for act in c["activities"])
    acts = (turn.get("taps") or {}).get("actions") or []
    shown_for = [a["activity"] for a in acts if a.get("kind") == "chart_grid" and a.get("activity")]
    if turn.get("server") != "chart" or not shown_for:
        return ""
    method = json.loads((seed / core.walk.METHOD).read_text(encoding="utf-8"))
    return words_of(core.activity_chart(seed, shown_for[0], method))


def charts_shown(turn: Turn) -> list[dict[str, Any]]:
    """534: each impact chart a turn showed, as its arguments: `activities`, `classes` (None for
    every class) and `years` (None where unsaid). A model-led turn's are its artefacts' (t532's
    `artefacts_shown`, the template `agent_fallback.IMPACT_OVER_TIME`); the brake's chart card
    draws one activity, every class."""
    led = [a.get("arguments") for a in turn.get("artefacts_shown") or []
           if a.get("template") == CHART]
    if model_led(turn):
        return [{"activities": list(args.get("activities") or []), "classes": args.get("classes"),
                 "years": args.get("years")} for args in led if isinstance(args, dict)]
    taps = (turn.get("taps") or {}).get("actions") or []
    shown_for = [a["activity"] for a in taps if a.get("kind") == "chart_grid" and a.get("activity")]
    return [{"activities": shown_for[:1], "classes": None, "years": None}] \
        if turn.get("server") == "chart" and shown_for else []


def drawn(turns: Sequence[Turn], seed: Path | None = None,
          files: Path | None = None) -> list[dict[str, Any]]:
    """Each turn with `elements`, what it showed beyond its reply, cards and taps: the words of
    the chart it drew (from `seed`), and of every file it produced (an artefact new or changed
    since the turn before), read under `files` where they were kept. 474: with `seed`, each turn
    also gets `read`, what code reads of the room (`room_read`), and every turn `kept_before`, the
    count of interviews its activity's last Keep turn kept (`keep_card`), None where none did or
    a Keep or Drop tap since changed it. 477: and `named_before`, the standard words
    (`nemo.terms.STANDARD_TERMS`) an earlier turn already named, which the app says bare (t215).
    534: and `earlier`, each turn before it: its line, its charts (`charts_shown`), its
    artefacts."""
    out: list[dict[str, Any]] = []
    before: dict[str, Any] = {}
    counts: dict[Any, int] = {}
    conversation: set[str] = set()  # 477: the standard words named so far, as the app keeps them
    offered: list[dict[str, Any]] = []
    earlier: list[dict[str, Any]] = []
    for turn in turns:
        made = {k: v for k, v in (turn.get("artefacts") or {}).items() if before.get(k) != v}
        before = dict(turn.get("artefacts") or {})
        elements = [chart_of(turn, seed)] if seed else []
        for name in made if files else ():
            path = files / name
            if path.is_file():
                elements.append(words_of(path.read_text(encoding="utf-8", errors="replace")))
        act = turn.get("activity")
        folded = [{**c, "label": label} for a in offered if a.get("kind") == "more"
                  for label, c in a.get("taps") or []]
        if turn.get("how") == "tapped" and any(
                a.get("tool") == "confirm_interviews" and a["label"] == turn.get("said")
                for a in [*offered, *folded]):
            counts.pop(act, None)
        read = {"read": room_read(seed, str(turn.get("model") or "glm")),
                "seed": str(seed)} if seed else {}  # 477: the room `plain_words` names by
        named_before = sorted(conversation)
        _named_in(turn, seed, conversation)
        out.append({**turn, "elements": [e for e in elements if e], **read,
                    "kept_before": counts.get(act), "named_before": named_before,
                    "earlier": list(earlier)})
        # 534: what a follow-up reads of the turns before it (`ROW_MARKS`)
        earlier.append({"said": turn.get("said"), "how": turn.get("how"),
                        "charts": charts_shown(turn),
                        "artefacts_shown": list(turn.get("artefacts_shown") or [])})
        if card := keep_card(turn):
            counts[act] = card[0]
        offered = actions(turn)
    return out


def seed_of(path: Path) -> Path:
    """The seed a turn file's charts are drawn from: its room where the file sits in one (a room
    is a seed copy), else `NEMO_SEED`, else the playground seed the app mints from."""
    room = path.parent.parent
    if path.parent.name == ".turns" and (room / "02_BCM-Method").is_dir():
        return room
    return Path(os.environ.get("NEMO_SEED", "/home/user/work/nemo-playground/seed"))


def route_fired(turn: Turn, prompt: Prompt) -> list[str]:
    kind, _, label = prompt.route.partition(":")
    if kind == "chart":  # 534: a model-led turn's chart is its artefact
        return [] if turn.get("server") == "chart" or charts_shown(turn) else \
            [f"no chart (server {turn.get('server')})"]
    if kind == "tap":
        options = list(turn.get("options") or [])
        import PROTOTYPE_core as core

        marked = {label, label + core.MAIL_MARK}  # 475: a tap that drafts one says so
        return [] if marked & set(options) else [f"no {label!r} tap (offered {options})"]
    return [] if norm(shown(turn)) else ["nothing shown"]


_REFUSAL = re.compile(
    r"\bi (?:can't|cannot|can not|am unable|'m unable|am not able|'m not able|won't)\b"
    r"|\bi (?:don't|do not) have (?:access|the ability)\b|\bsorry\b|\bas an ai\b"
    r"|\bthe ai did not answer\b")
#: quoted words, a quote left open running to the end of its line (r4: A4-06's cut quote)
_QUOTED = re.compile(r'"[^"]*(?:"|$)')
#: the same in single quotes, for `no_refusal` alone (558: A4-03 quotes the process owner's "I can't
#: say yet."). An apostrophe inside a word is neither end: a single quote opens at a word start and
#: closes at a word end, so "can't" and "that's" stay outside the quote's reach.
_QUOTED_SINGLE = re.compile(r"(?<!\w)'(?:[^']|'(?=\w))*'(?!\w)")
#: saying what the files do not hold is not declining (r4: B3-14), nor is an honest limit (r5:
#: A9-08 "What I can't see: whether …", A9-14 "What I can't confirm from the files")
_FILES_SILENT = re.compile(
    r"\bi (?:can't|cannot|can not) (?:tell|see|confirm)\b[^\n]*?\bfrom the files\b"
    r"|\bwhat i (?:can't|cannot|can not) (?:tell|see|confirm)\b")


def no_refusal(turn: Turn, prompt: Prompt) -> list[str]:
    failed = [c.get("error") or "failed" for c in turn.get("calls") or []
              if c.get("outcome") == "failed"]
    lines = str(turn.get("reply") or "").splitlines()
    said = _FILES_SILENT.sub("", "\n".join(
        _QUOTED_SINGLE.sub("", _QUOTED.sub("", norm(line))) for line in lines))
    return [*(f"call failed: {why}" for why in failed),
            *(f"refuses: {m.group(0)!r}" for m in _REFUSAL.finditer(said))]


def holding(fact: str) -> re.Pattern[str]:
    """The fact as whole words, so "8 h" is not found inside "168 h", nor "168 h" in ">168 h"."""
    return re.compile(r"(?<![\w>])" + re.escape(fact) + r"(?!\w)")


def seeking(fact: Fact, spelling: str) -> re.Pattern[str]:
    """Where an answer holds a spelling of `fact`: whole words (`holding`), a bold word from a word
    start (r5: "technicians" holds **technician**, "untechnician" does not)."""
    bold = fact.kind == "bold"
    return re.compile(r"(?<!\w)" + re.escape(spelling)) if bold else holding(spelling)


def marks_cell(fact: Fact) -> str:
    """The marks cell a fact came from: its prompt, its column and its words."""
    pid, head, words = fact.cell
    return f"marks {pid} {head}: {words!r}"


def missing(fact: Fact) -> str:
    """A reason to fail, naming the fact, its other spellings and the marks cell it came from."""
    others = f" (or {', '.join(map(repr, fact.spellings[1:]))})" if len(fact.spellings) > 1 else ""
    return f"missing {fact.said!r}{others}; {marks_cell(fact)}"


def facts_present(turn: Turn, prompt: Prompt) -> list[str]:
    """Every expected fact of the prompt's cell is in what he sees; 557: after a named day's card,
    no model sentence names an interview, a day or an activity other than the card's."""
    seen = norm(shown(turn))
    loose = bare(seen)
    return [*(missing(fact) for fact in prompt.facts
              if not any(seeking(fact, s).search(seen) for s in fact.spellings)
              and not (fact.clauses and all(holding(c).search(loose) for c in fact.clauses))),
            *day_sentence(turn, prompt)]


def functions_first(turn: Turn, prompt: Prompt) -> list[str]:
    """The marks name functions first: a function only its holder's name stood in for."""
    seen = norm(shown(turn))
    return [f"function {fact.said!r} named only by its holder; {marks_cell(fact)}"
            for fact in prompt.facts if fact.kind == "function"
            and not holding(fact.said).search(seen)
            and any(holding(s).search(seen) for s in fact.spellings[1:])]


def rating_pairs(turn: Turn, prompt: Prompt) -> list[str]:
    """Each class nemo's reply rates at a horizon, outside quotes ("financial low/medium from 72 h",
    "legal low at 8 h, high at 72 h"), that no grid of the task's activity rates so, nor of another
    activity the reply names (A1 sums up order picking's interview too). A rating goes with the
    class named last before it in its sentence; a pair no grid rates at all is not judged, nor is
    a reply naming an activity whose ratings this year are not known (`Ratings.blind`)."""
    if not prompt.ratings:
        return []
    grades = prompt.ratings
    text = _HOURS.sub(r"\1 h", str(turn.get("reply") or "").translate(_QUOTES).lower()
                      .replace("**", "").replace("`", ""))
    about = {grades.activity} | {a for a, words in grades.names if any(
        re.search(rf"(?<![\w.]){re.escape(w)}(?![\w]|\.\d)", text.replace("&", "and"))
        for w in words)}
    out = []
    for cls, said, hours in [] if about & grades.blind else _stated(text, grades):
        right = {lab for a, c, h, lab in grades.held if a in about and (c, h) == (cls, hours)}
        if right and not set(re.split(r"\s*(?:/|or)\s*", said)) & right:
            out.append(f"{cls} {said} at {hours}: the records and this year's interviews rate it "
                       f"{' or '.join(sorted(right))} ({', '.join(sorted(about))})")
    return out


def _stated(text: str, grades: Ratings) -> Iterable[tuple[str | None, str, str]]:
    """(class, rating as said, horizon) for each rating `text` states at an hour outside quotes,
    the class the one named last before it in its sentence (None where none is)."""
    classes = dict(grades.classes)
    names = "|".join(re.escape(w) for w in sorted(classes, key=len, reverse=True))
    labels = "|".join(re.escape(w) for w in sorted(grades.scale, key=len, reverse=True))
    rated = re.compile(rf"\b(?P<said>(?:{labels})(?:\s*(?:/|or)\s*(?:{labels}))*)"
                       rf"\s+(?:at|from)\s+(?P<h>\d+ h)\b")
    for line in text.splitlines():
        for sentence in re.split(r"[.;](?=\s|$)", _QUOTED.sub(" ", line)):
            named = [(m.end(), classes[m.group(0)])
                     for m in re.finditer(rf"\b(?:{names})\b", sentence)]
            for m in rated.finditer(sentence):
                yield (next((c for end, c in reversed(named) if end <= m.start()), None),
                       m["said"], m["h"])


# ---- 474: the taps fit the reply, an e-mail tap where one is due, one interview count ----------

#: C1: the walk tools that are a way into the walk, which fit any answer ("Start a BIA", "Pick
#: another activity", "Start <activity>"); every other walk tool a tap calls is a stage's own
WAYS_IN = frozenset({"list_activities", "get_step", "open_activity"})
#: C1: a stage's own taps that call nothing: its grid, its open decisions, its folded drops
STAGE_SHOWS = frozenset({"grid", "all", "more"})
#: C2: the taps that draft an e-mail: the write tap, the invitation, the drafts he was shown; an
#: owner picked after the write tap (a referral with a `to`); and any tap 475 labels so
MAIL_KINDS = frozenset({"write", "invite", "put_drafts"})
#: 475's label ending, read as `PROTOTYPE_core.WRITTEN` reads the word (step 43 bars it spelt out)
MAIL_LABEL = re.compile(r"\(e-?m(?:ai|ia)l\)\s*$", re.I)
_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
          "eighteen", "nineteen", "twenty")
#: a count as said, never a year, an hour, a date ("9 nov interview") or a record number
#: ("record 1.2", 596)
_N = (r"(?<![\d.])(\d{1,3}(?![.,]\d)|" + "|".join(_WORDS)
      + r")\b(?!\s+(?:h\b|" + "|".join(_MONTHS) + r"\b))")
#: C3: a count of interviews a reply states: "six interviews", "three 2026 re-interviews", "those
#: four", "keeping the six"; the words between a count and "interviews" are its qualifiers, and so
#: is an "other" just before it (559: "the other two re-interviews")
_COUNTED = re.compile(rf"(?:\b(?P<other>other)\s+)?\b{_N}\s+(?P<q>(?:[\w'-]+\s+){{0,3}}?)"
                      rf"(?:re-?)?interviews?\b"
                      rf"|\b(?:those|these|keep|keeping)\s+(?:all\s+|the\s+)?{_N}")
_LAST = re.compile(r"\b(?:last|prior|earlier|older|old|previous)\b")


@functools.cache
def _walk_tools() -> frozenset[str]:
    import PROTOTYPE_core as core

    return core.WALK_TOOL_NAMES


@functools.cache
def room_read(seed: Path, model: str) -> dict[str, tuple[Any, ...]]:
    """What code reads of a room for C2 and C3: each figure its room-state sheet marks proposed,
    as "mtpd 72 h" (`PROTOTYPE_core._built_sheet`), and each interview's department and cycle
    (its `cycle:`, else its date's year) from its front matter, 16_marschkamp's rule."""
    if not (seed / "02_BCM-Method").is_dir():
        return {"proposed": (), "interviews": ()}
    import PROTOTYPE_core as core

    proposed = dict.fromkeys(norm(f"{k} {v['value']}") for row in core._built_sheet(seed, model)
                             for k, v in row["figures"].items()
                             if v["mark"] == core.PROPOSED and v["value"])
    interviews = []
    for path in sorted((seed / "07_Interviews").glob("*.md")):
        head = core._FRONT_MATTER.match(path.read_text(encoding="utf-8"))
        said = dict(re.findall(r"^(\w+):[ \t]*(.+?)[ \t]*$", head.group(1), re.M)) if head else {}
        interviews.append((said.get("department", ""),
                           said.get("cycle") or said.get("date", "")[:4]))
    return {"proposed": tuple(proposed), "interviews": tuple(interviews)}


def actions(turn: Turn) -> list[dict[str, Any]]:
    """The taps a turn offered, each with the call it stands for (the turn file's `taps`)."""
    return list((turn.get("taps") or {}).get("actions") or [])


def stage_tap(action: Mapping[str, Any]) -> bool:
    tool = action.get("tool")
    return action.get("kind") in STAGE_SHOWS or (tool in _walk_tools() and tool not in WAYS_IN)


def on_the_walk(turn: Turn) -> bool:
    """C1: the turn's kind as code says it. A tap, code's own reply (`server`) or a walk tool the
    model called is a stage's turn; a typed line the model answered calling none is an answer."""
    return (turn.get("how") != "typed" or bool(turn.get("server"))
            or bool(set(turn.get("tools") or []) & _walk_tools()))


def options_fit(turn: Turn, prompt: Prompt) -> list[str]:
    """C1, his 'make sure options suggested are ALWAYS fitting the reply': a stage's own tap
    (`stage_tap`) offered under an answer that took no step of it (`on_the_walk`)."""
    if on_the_walk(turn):
        return []
    tools = list(turn.get("tools") or [])
    return [f"stage tap {a['label']!r} under an answer that took no step (tools {tools})"
            for a in actions(turn) if stage_tap(a)]


def drafts_mail(action: Mapping[str, Any]) -> bool:
    """A tap whose call drafts one: a mail kind, or a referral to someone (a `to`)."""
    return action.get("kind") in MAIL_KINDS or action.get("kind") == "refer" and "to" in action


def mail_tap(action: Mapping[str, Any]) -> bool:
    return drafts_mail(action) or bool(MAIL_LABEL.search(str(action.get("label", ""))))


def letter_row(prompt: Prompt) -> bool:
    """611: a walk row line that asks for a letter (its marks are a letter's, `ROW_MARKS`)."""
    return ROW_MARKS.get(prompt.marks) in (_letter_asked, _new_letter)


def letter_tap(action: Mapping[str, Any]) -> bool:
    """611, 49_nemo_check's ruling: on a letter row only a tap that drafts that letter is the mail
    tap; an invitation (its kind, or its label: `INVITE_TAP`, `led_turn.MOVE_TAP`) is not."""
    import led_turn

    import PROTOTYPE_core as core

    return mail_tap(action) and action.get("kind") not in ("invite", led_turn.MOVE_INVITE) and str(
        action.get("label", "")) not in (core.INVITE_TAP, led_turn.MOVE_TAP)


def owner_gaps(turn: Turn) -> list[str]:
    """C2 (b): the gaps a turn names that need an owner's word, each read by code: a referral tap
    (an open finding with a holder), the conflict card drawn with the taps, a line of the reply
    saying "proposed" beside a figure the room's sheet marks proposed (`room_read`, under the
    turn's `read`), and "owner missing" (`merge_table.OWNER`)."""
    import merge_table

    import PROTOTYPE_core as core

    gaps = [f"an open finding with a holder ({a['label']!r})" for a in actions(turn)
            if a.get("kind") == "refer" and "to" not in a]
    card = (turn.get("taps") or {}).get("card") or {}
    if card.get("sides"):
        gaps.append(f"an unresolved conflict ({card.get('item')})")
    proposed = (turn.get("read") or {}).get("proposed") or ()
    for line in str(turn.get("reply") or "").splitlines():
        said = norm(line)
        named = [f for f in proposed if holding(f).search(said)]
        if named and holding(core.PROPOSED).search(said):
            gaps.append(f"figures at proposed ({', '.join(named)})")
    if holding(merge_table.OWNER).search(norm(shown(turn))):
        gaps.append(merge_table.OWNER)
    return gaps


def mail_taps(turn: Turn, prompt: Prompt) -> list[str]:
    """C2, his 'include it to the option such as (E-Mail)': (b) a turn naming a gap that needs an
    owner's word (`owner_gaps`), and (c) his typed ask to draft one (the app's own reader,
    `PROTOTYPE_core.asks_to_write`), each offer a tap that drafts one (`mail_tap`). 596: a
    model-led turn records its taps only as `options`, read by their label. 611: on a letter row
    the tap drafts that letter (`letter_tap`)."""
    offered = list(turn.get("options") or [])
    tap = letter_tap if letter_row(prompt) else mail_tap
    if any(tap(a) for a in [*actions(turn), *({"label": o} for o in offered)]):
        return []
    import PROTOTYPE_core as core

    why = [f"names {gap} and offers no mail tap (offered {offered})" for gap in owner_gaps(turn)]
    if turn.get("how") == "typed" and core.asks_to_write(str(turn.get("said") or "")):
        why.append(f"a typed ask to draft a mail offers no mail tap (offered {offered})")
    return why


def mail_label(turn: Turn, prompt: Prompt) -> list[str]:
    """C2 (a), 475's, his 'clearly mark the suggested next steps as an E-Mail': every tap whose
    call drafts one (`drafts_mail`) ends its label with his word (`PROTOTYPE_core.MAIL_MARK`)."""
    import PROTOTYPE_core as core

    return [f"tap {a['label']!r} drafts one and its label does not say so"
            for a in actions(turn) if drafts_mail(a)
            and not str(a.get("label", "")).endswith(core.MAIL_MARK)]


def keep_card(turn: Turn) -> tuple[int, int, str] | None:
    """C3: a stage-2 Keep turn's card, from its taps (`_interview_taps`): how many interviews its
    "Keep these N" keeps (the offer "Keep all N" binds, less what "Keep these" drops), the offer,
    and the Keep these tap's label. None for a turn drawing no such tap. Since t528 r2 stage 2
    draws no "Keep all N": the card's count is then the tap's own, and the offer counts no more."""
    import PROTOTYPE_core as core

    calls = [a for a in actions(turn) if a.get("tool") == "confirm_interviews"]
    every = next((a for a in calls if not (a.get("args") or {}).get("drop")), None)
    these = next((a for a in calls if str(a["label"]).startswith(
        (core.KEEP_THESE.split("{")[0], core.KEEP_THIS))), None)
    if these is None:
        return None
    if every is None or every is these:
        n = int(m.group()) if (m := re.search(r"\d+", str(these["label"]))) else 1
        return n, n, str(these["label"])
    offer = int(m.group()) if (m := re.search(r"\d+", every["label"])) else 1
    return offer - len(these["args"]["drop"]), offer, str(these["label"])


def _number(said: str) -> int:
    return int(said) if said.isdigit() else _WORDS.index(said)


def _counts(text: str) -> list[tuple[str, int, str]]:
    """(the words, the count, its qualifiers) for each count of interviews `text` states."""
    return [(m.group(0), _number(m.group(2) or m.group(4)),
             f"{m.group('other') or ''} {m.group('q') or ''}")
            for m in _COUNTED.finditer(norm(text))]


def one_count(turn: Turn, prompt: Prompt) -> list[str]:
    """C3, his 'it must always be the same open interviews'. In a Keep turn (`keep_card`) the
    reply's every count, the N of "Keep these N" and its name list are the card's, and so is the
    count the room held before (`kept_before`, `drawn`) where no Keep or Drop tap changed it.
    Outside a Keep turn a count qualified own, of a cycle or of the last cycle is the front matter's
    (`room_read`): the room's or the turn's activity's own, less one where "other" qualifies it
    (559: "the other two re-interviews" are all but the one at hand); an unqualified count is not
    judged."""
    reply = str(turn.get("reply") or "")
    card = keep_card(turn)
    if card is None:
        return _cycle_counts(turn, reply)
    n, offer, label = card
    out = [f"the reply says {said!r}: the card keeps {n}" for said, k, _ in _counts(reply)
           if k not in (n, offer)]
    if (m := re.search(r"\d+", label)) and int(m.group()) != n:
        out.append(f"the tap says {label.split(':')[0]!r}: the card keeps {n}")
    if ":" in label and len(label.split(":", 1)[1].split(",")) != n:
        out.append(f"the tap names {len(label.split(':', 1)[1].split(','))}: the card keeps {n}")
    if (before := turn.get("kept_before")) is not None and before != n:
        out.append(f"the room kept {before} before and no Keep or Drop tap changed it: "
                   f"the card keeps {n}")
    return out


def _cycle(said: str, qualifiers: str, now: str) -> tuple[str, bool] | None:
    """The cycle a count's qualifiers name, and whether it is that cycle (True) or any other: a
    year, the last cycle, or this one ("this", "new", a re-interview); None for none."""
    if year := re.search(r"\b\d{4}\b", qualifiers):
        return year.group(), True
    if _LAST.search(qualifiers):
        return now, False
    if "re-" in said or re.search(r"\b(?:this|new)\b", qualifiers):
        return now, True
    return None


def _cycle_counts(turn: Turn, reply: str) -> list[str]:
    files = (turn.get("read") or {}).get("interviews") or ()
    if not files:
        return []
    now = max(c for _, c in files)
    act = turn.get("activity") or (turn.get("taps") or {}).get("activity")
    out = []
    for said, k, q in _counts(reply):
        cycle, own = _cycle(said, q, now), bool(re.search(r"\bown\b", q))
        if own and not act or not own and cycle is None:
            continue
        held = [d for d, c in files if cycle is None or (c == cycle[0]) == cycle[1]]
        right = {held.count(act)} if act else set()
        if not own:
            right.add(len(held))
        if re.search(r"\bother\b", q):  # 559: the others, all but the one the reply is on
            right = {r - 1 for r in right}
        if k not in right:
            out.append(f"the reply says {said!r}: the interviews' front matter holds "
                       f"{' or '.join(map(str, sorted(right)))}")
    return out


# ---- 477 (D2, his "Every answer (Recommended)"): plain words for a junior BCM manager ---------
#: system talk: how nemo works inside, said to him (D2's three, one place: the check and the tests
#: read them here). No length rule of any kind (his TYPED 2026-10-13T20:41:18Z).
SYSTEM_TALK: dict[str, re.Pattern[str]] = {
    "side 1 / side 2": re.compile(r"\bside \d+\b", re.I),
    "the method derives …": re.compile(r"\bthe method derives\b", re.I),
    "the live graph has no …": re.compile(
        r"\bthe (?:live |dependency )?graph (?:itself )?(?:has no|is not|isn't|hasn't|does not|"
        r"doesn't|cannot|can't)\b", re.I),
}
#: a list written as one line: this many items or more in one run "a, b, c and d" (row 35)
LIST_AT = 4
#: an item of such a run: a few words at most, so a clause is never taken for one
ITEM_WORDS = 4
#: r2 (41_nemo_check's ruling 2026-10-18 08:01:54, 18_marschkamp's fix on practice A9-05 and
#: B9-04): a run inside one sentence whose items are each this many words or fewer is prose
#: ("no check, approval, date of approval or signature"), not a one-line list
SHORT_ITEM = 2
#: words an item's length does not count ("date of approval" is two)
_SMALL = frozenset({"a", "an", "the", "of"})
#: r3 (41_nemo_check's ruling 2026-10-18 12:43:52, his "Lists are lists"): items nemo writes bold
#: are names to scan, so their run is a list however short; the r2 exemption is for plain runs
_BOLD_ITEM = r"\*\*[^*]+\*\*"
_BOLD = re.compile(rf"{_BOLD_ITEM}(?:\s*,\s*{_BOLD_ITEM}){{{LIST_AT - 2},}}\s*,?\s+(?:and|or)\s+"
                   rf"{_BOLD_ITEM}")
_CLAUSE = re.compile(r"(?<=[.!?])\s+|[:;—–]")
#: a bracket inside a run is the item's ("Marschkamp (headquarters)"), never a clause break (r2)
_BRACKET = re.compile(r"\([^()]*\)")
_LAST_JOIN = re.compile(r"^(?:and|or)\s|\s(?:and|or)\s")


def _plain_run(clause: str) -> bool:
    """Whether a clause ends on a run of plain items `one_line_lists` counts as a list."""
    parts = [p.strip() for p in clause.split(",")]
    if len(parts) < 3 or not _LAST_JOIN.search(parts[-1]):
        return False
    items = [*parts[:-1], *re.split(r"^(?:and|or)\s+|\s+(?:and|or)\s+", parts[-1])]
    items = [i.strip(" *") for i in items if i.strip(" *")]
    rest = items[1:]
    return (len(items) >= LIST_AT and all(len(i.split()) <= ITEM_WORDS for i in rest)
            and any(len([w for w in i.lower().split() if w not in _SMALL]) > SHORT_ITEM
                    for i in rest))


def one_line_lists(text: str) -> list[str]:
    """D2: each run of `LIST_AT` or more items written inside one line: two commas or more and an
    "and" or "or" before the last, every item after the first `ITEM_WORDS` words or fewer and one
    of them more than `SHORT_ITEM` (r2: "no check, approval or signature" is prose). A run of
    `LIST_AT` or more bold items is a list however short they are (r3: "**cutting staff**,
    **production staff**, **technician** and **production supervisors**"). A bracket stays with its
    item. A table row is a list already."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            continue
        for clause in _CLAUSE.split(_BRACKET.sub("", line)):
            if runs := _BOLD.findall(clause):
                out += runs
            elif _plain_run(clause):
                out.append(clause.strip())
    return out


def system_talk(text: str) -> list[str]:
    """D2: each piece of system talk (`SYSTEM_TALK`) the text holds, by its name and words."""
    return [f"system talk ({name}): {m.group()!r}" for name, pattern in SYSTEM_TALK.items()
            for m in pattern.finditer(text)]


def _term(term: str) -> re.Pattern[str]:
    """A method term where it stands as one (`nemo.terms`' joints); a lower-case one in any case."""
    return re.compile(rf"(?<![\w/.+-]){re.escape(term)}(?![\w+-])",
                      re.I if term.islower() else 0)


def unglossed(parts: Sequence[str], table: Mapping[str, str], names: Iterable[str] = (),
              categories: Iterable[str] = (), named_before: Iterable[str] = ()) -> list[str]:
    """D2: each BCM term (`nemo.terms.METHOD_TERMS`, the method's own words) one of `parts` uses
    that the app's naming (`PROTOTYPE_words.named_turn`'s pass, on the answer alone) never says in
    plain words: one standing only in a heading, someone's words or beside another bracket. A
    draft's body is the e-mail as sent (t397) and is not judged, nor a term inside one of `names`
    (the room's item names: "BCM Officer" is a function)."""
    from nemo import terms

    import PROTOTYPE_words as words

    used: frozenset[str] = frozenset(named_before)
    present: list[str] = []
    names = tuple(sorted(names, key=len, reverse=True))
    # a term inside a name ("BCM Officer", a function) is the name's, as a product's is (477)
    named = re.compile("|".join(map(re.escape, names))) if names else None
    for part in parts:
        for n, piece in enumerate(words.DRAFT.split(part)):
            if n % 2:
                continue
            bare = named.sub(" ", piece) if named else piece
            present += [t for t in terms.METHOD_TERMS if t not in present and _term(t).search(bare)]
            _, used = words._named(piece, dict(table), used, tuple(names), tuple(categories))
    return [f"{t!r} with no plain words in the answer" for t in present if t not in used]


@functools.lru_cache(maxsize=8)
def _table(seed: Path | None) -> tuple[Mapping[str, str], tuple[str, ...], tuple[str, ...]]:
    """The app's naming table, item names and category names for `seed`'s room; nemo's method
    terms alone where there is no room. Read once per seed: a scored run draws every turn."""
    from nemo import terms

    if seed is None or not (seed / "02_BCM-Method").is_dir():
        return terms.METHOD_TERMS, (), ()
    import PROTOTYPE_words as words

    return (words.room_terms(seed), tuple(words.item_names(seed)),
            tuple(words.room_categories(seed).values()))


def _named_in(turn: Turn, seed: Path | None, conversation: set[str]) -> None:
    """t215 as the app keeps it: `conversation` gains the standard words this turn names."""
    import PROTOTYPE_words as words

    table, names, categories = _table(seed)
    words.named_turn(str(turn.get("reply") or ""), list(map(str, turn.get("cards") or [])),
                     dict(table), conversation, names, categories)


def plain_words_in(reply: str, cards: Sequence[str] = (), options: Sequence[str] = (),
                   seed: Path | None = None, named_before: Iterable[str] = ()) -> list[str]:
    """D2's check on one answer: system talk in what he reads (taps too), and in the reply and its
    cards a BCM term with no plain words and a list written as one line. The room's table is the
    app's (`PROTOTYPE_words.room_terms`) where `seed` is given, nemo's method terms otherwise. It
    flags; it never rewrites. `named_before`: the standard words an earlier turn of the
    conversation named, which the app says bare after that (t215, his rule), so they count as
    said; every other method term is said in plain words in each answer (D2)."""
    written = [reply, *cards]
    found = unglossed(written, *_table(seed), named_before)
    return [*system_talk("\n".join([*written, *options])), *found,
            *(f"a list written as one line: {run!r}" for part in written
              for run in one_line_lists(part))]


def plain_words(turn: Turn, prompt: Prompt) -> list[str]:
    """D2 on a turn: `plain_words_in` over its reply, cards and taps, on the room `drawn` read."""
    seed = turn.get("seed")
    return plain_words_in(str(turn.get("reply") or ""), list(map(str, turn.get("cards") or [])),
                          list(map(str, turn.get("options") or [])),
                          Path(seed) if seed else None, turn.get("named_before") or ())


def agent_marks(turn: Turn, prompt: Prompt) -> list[str]:
    """498: an agent case's own marks (`AGENT_MARKS`, named by `Prompt.marks`), on the seed its room
    was minted from (`drawn`'s `seed`, else `seed_of`); none for a sheet prompt."""
    if prompt.marks not in AGENT_MARKS:  # a sheet prompt, or a walk row's (`row_marks`)
        return []
    seed = Path(turn["seed"]) if turn.get("seed") else seed_of(Path("."))
    mark = AGENT_MARKS[prompt.marks].mark
    return mark(turn, seed, prompt.marks) if mark else []


# ---- 534: action claims (U5), taps and his walk rows' own marks ------------------------------

#: U5: words that say nemo did something ("done", "moved", "now says", "put in Drafts"), as `norm`
#: spells them
_DID = r"(?:moved|changed|updated|rescheduled|put|placed|saved|booked|blocked|drafted|created)"
_CLAIMED = re.compile(
    r"^done\b|\b(?:it's|it is|all|that's|that is) done\b"
    rf"|(?:^|, |\band )i(?:'ve| have)? (?:now |just )?{_DID}\b"
    rf"|\b(?:has|have) been {_DID}\b|\b(?:it|this|the \w+) now (?:says|reads|shows)\b"
    r"|\b(?:moved|rescheduled) (?:it )?to\b|\bput (?:it |them )?in(?:to)? (?:your )?drafts\b")
#: U5: only his tap sends a mail; nemo never may say it sent one
_SENT_CLAIM = re.compile(
    r"(?:^|, |\band )i(?:'ve| have)? (?:now |just |already )?(?:sent|e-?mailed)\b"
    r"|\b(?:it|this|they|the (?:draft|e-?mail|mail|letter|invitation)s?) (?:has |have |was |were )?"
    r"(?:been )?sent\b")
#: probe finding 4: "Nothing has been sent" says what was not done, no claim
_NEGATED_CLAIM = re.compile(r"\b(?:not|no|nothing|never|none|until|once|when|before|after|if|"
                            r"will)\b|n't\b")
#: a claim is read per clause: "Moved to Friday; nothing has been sent" claims the move
_CLAUSES = re.compile(r"[;—–]|\s-\s")
#: a model-led tool that only reads: it does nothing he could be told is done
_READS = re.compile(r"^(?:read|list|get|find|search|ask)_")


def _acted(turn: Turn) -> bool:
    """U5: the turn did something a claim may name: a model-led turn's tool that is no read, or an
    artefact shown; on the brake's path, any tool or code's own answer (`server`)."""
    if model_led(turn):
        return bool(turn.get("artefacts_shown")) or any(
            not _READS.match(str(s.get("name") or "")) for s in turn.get("tool_steps") or [])
    return bool(turn.get("tools") or turn.get("server"))


def action_claims(turn: Turn, prompt: Prompt) -> list[str]:
    """534, U5 (fact-checks-per-kind.md): "done / changed / moved / sent / now says / put in
    Drafts" only where a tool of that turn did it (`_acted`), and "sent" never: only his tap sends.
    A sentence that says what was not, or will be, done claims nothing (`_NEGATED_CLAIM`)."""
    out = []
    for sentence in (norm(c) for s in _SENTENCE.split(str(turn.get("reply") or ""))
                     for c in _CLAUSES.split(s) if c.strip()):
        if _NEGATED_CLAIM.search(sentence):
            continue
        if sent := _SENT_CLAIM.search(sentence):
            out.append(f"says it {sent[0]}: only his tap sends ({sentence[:60]!r})")
        elif (did := _CLAIMED.search(sentence)) and not _acted(turn):
            out.append(f"claims {did[0]!r} with no tool in the turn ({sentence[:60]!r})")
    return out


def tap_activities(turn: Turn, prompt: Prompt) -> list[str]:
    """534: each tap that names an activity in its label opens that activity: its call's
    `activity` is one the label names (the app's own reader, `PROTOTYPE_core.named_in`). 557:
    under a named day's card, each tap that opens an activity opens the card's (`day_taps`)."""
    import PROTOTYPE_core as core

    seed = Path(turn["seed"]) if turn.get("seed") else seed_of(Path("."))
    out = []
    for a in actions(turn):
        if not a.get("activity"):
            continue
        named = core.named_in(seed, str(a.get("label") or ""))
        if named and a["activity"] not in named:
            out.append(f"tap {a.get('label')!r} opens {a['activity']}, its label names "
                       f"{', '.join(named)}")
    return [*out, *day_taps(turn, prompt)]


# ---- 557: a named day's card (544) owns the answer after it ---------------------------------

#: 557: the pointer code's named-day card closes on: this year's other interviews (`OTHERS_SAID`)
_POINTER = re.compile(r"^\w+ other interviews? this year\b")


@functools.cache
def _card_head() -> str:
    """557: the words code's named-day changes card opens on, before the "·" (`CHANGES_HEADING`,
    with t430's no-break space or the plain one older turns carry)."""
    import PROTOTYPE_core as core

    return core.CHANGES_HEADING.split("{")[0].split("·")[0].strip()


def _named_day(seed: Path, turn: Turn) -> tuple[datetime.date, list[str]] | None:
    """557: the day his line names and the interviews the room holds on it, by the app's own
    readers (`named_day`, `day_interviews`); None where it names no day or the day holds none.
    A weekday or a date is looked for first: `named_day` reads the room's plan before it looks,
    and most lines name no day."""
    import PROTOTYPE_core as core

    said = str(turn.get("said") or "")
    if not (core._WEEKDAY_SAID.search(said) or core._DATE_SAID_ON.search(said)):
        return None
    day = core.named_day(seed, said)
    held = core.day_interviews(seed, day) if day else []
    return (day, held) if day and held else None


def _card_acts(seed: Path, held: Sequence[str]) -> list[str]:
    """557: the activities a named-day card's taps follow: the ones the day's interviews name
    (`interview._named_in`, the card's every block, 544 r5), none where they name none."""
    from nemo import interview

    return list(dict.fromkeys(a for path in held for a in interview._named_in(seed / path)))


def _card_shown(turn: Turn) -> bool:
    """557: whether the reply carries code's named-day changes card (its heading)."""
    head = _card_head()
    return any(para.startswith(head) for para in str(turn.get("reply") or "").split("\n\n"))


def _off_card(turn: Turn, seed: Path, held: Sequence[str]) -> list[str]:
    """557: the reply's paragraphs that are not code's card: not a paragraph the seed's
    `changes_block` writes whole, not one of the card's own headings, not a bullet run, and not
    the closing pointer (`others_said`, whose wording may differ from the turn's only at the end
    of the reply)."""
    import PROTOTYPE_core as core

    paras = [p for p in str(turn.get("reply") or "").split("\n\n") if p.strip()]
    code = {block for path in held if (block := core.changes_block(seed, path))}
    pointer = core.others_said(seed, list(held))
    heads = (_card_head(), core.CHANGES_UNCHANGED, core.CHANGES_MATTERS)
    return [para for n, para in enumerate(paras)
            if para not in code and not para.startswith(heads)
            and not para.lstrip().startswith("- ") and para != pointer
            and not (n == len(paras) - 1 and _POINTER.match(para.strip()))]


def _sentence_names(seed: Path, sentence: str, day: datetime.date,
                    acts: Sequence[str]) -> list[str]:
    """557: what a sentence names that the day's card does not: an activity by its whole name
    (`named_in`) other than the card's, a day (`named_day`) other than the card's, and an
    interview placed elsewhere (the word, `INTERVIEW_SAID`, where the sentence names another
    activity or day). The card's own day, activity and interview are the card's: a sentence
    naming only those names none of the card's kinds."""
    import PROTOTYPE_core as core

    out = [a for a in core.named_in(seed, sentence) if a not in acts]
    if core._WEEKDAY_SAID.search(sentence) or core._DATE_SAID_ON.search(sentence):
        if (said := core.named_day(seed, sentence)) and said != day:
            out.append(f"{said.day} {said:%B}")
    if out and core.INTERVIEW_SAID.search(sentence):
        out.append("an interview")
    return out


def day_sentence(turn: Turn, prompt: Prompt) -> list[str]:
    """557, the `facts` check's named-day rule: after a named-day card, no model sentence names an
    interview, a day or an activity other than the card's (544 r4 drops such a sentence): the card
    is code's, so a reply that kept one kept a false sentence. The card's own blocks and closing
    pointer are code's words and are never read."""
    if not _card_shown(turn):
        return []
    seed = Path(turn["seed"]) if turn.get("seed") else seed_of(Path("."))
    card = _named_day(seed, turn)
    if card is None:
        return []
    day, held = card
    acts = _card_acts(seed, held)
    return [f"after the card for {day.day} {day:%B}, a sentence names "
            f"{', '.join(names)}: {sentence[:60]!r}"
            for para in _off_card(turn, seed, held)
            for sentence in _sentences_in(para)
            if (names := _sentence_names(seed, sentence, day, acts))]


def day_taps(turn: Turn, prompt: Prompt) -> list[str]:
    """557, the `taps` check's named-day rule: under a named-day card, each tap that opens an
    activity opens the card's own: its `activity`, its call's, or the re-interview page it opens
    (the app keys the full set to it, 544 r5)."""
    seed = Path(turn["seed"]) if turn.get("seed") else seed_of(Path("."))
    card = _named_day(seed, turn)
    if card is None or not (acts := _card_acts(seed, card[1])):
        return []
    day = card[0]
    out = []
    for a in actions(turn):
        args = a.get("args")
        act = a.get("activity") or (args.get("activity") if isinstance(args, Mapping) else None)
        if not act and str(a.get("page", "")).startswith("re-interview/"):
            act = str(a["page"]).removeprefix("re-interview/")
        if act and act not in acts:
            out.append(f"tap {a.get('label')!r} opens {act}: the card for {day.day} {day:%B} is "
                       f"{', '.join(acts)}")
    return out


def row_marks(turn: Turn, prompt: Prompt) -> list[str]:
    """534: a walk row's own marks (`ROW_MARKS`, by `Prompt.marks`); none for any other prompt."""
    mark = ROW_MARKS.get(prompt.marks)
    if mark is None:
        return []
    seed = Path(turn["seed"]) if turn.get("seed") else seed_of(Path("."))
    return mark(turn, seed, prompt.marks)


Check = Callable[[Turn, Prompt], list[str]]
#: the registry: one entry per named check; his failure codes add entries here
CHECKS: dict[str, Check] = {
    "route": route_fired,
    "no-refusal": no_refusal,
    "facts": facts_present,
    "rating-pairs": rating_pairs,
    "functions-first": functions_first,
    "options-fit": options_fit,
    "mail-tap": mail_taps,
    "mail-label": mail_label,
    "one-count": one_count,
    "plain-words": plain_words,
    "agent-marks": agent_marks,
    "claims": action_claims,
    "taps": tap_activities,
    "row-marks": row_marks,
}
#: checks that flag a turn and never fail it
SOFT = frozenset({"functions-first"})
#: 534 (his round 4, Q13; fact-checks-per-kind.md's scoring hook): every check scores one of the
#: four things a run is scored on. Wording may vary: no check scores it.
AXES: dict[str, str] = {
    "route": "shape", "no-refusal": "shape", "facts": "facts", "rating-pairs": "facts",
    "functions-first": "facts", "options-fit": "taps", "mail-tap": "taps", "mail-label": "taps",
    "one-count": "facts", "plain-words": "shape", "agent-marks": "facts", "claims": "claims",
    "taps": "taps", "row-marks": "shape",
}
_REASON = re.compile(r"^line \d+ \(([\w-]+)\) ([\w-]+): ")


def axis_of(reason: str) -> str:
    """534: the axis a scored reason to fail ("line 4 (A3) route: …") falls on."""
    m = _REASON.match(reason)
    return AXES.get(m[2], "facts") if m else "facts"


def judge(turn: Turn, prompt: Prompt,
          checks: Mapping[str, Check] = CHECKS) -> dict[str, list[str]]:
    """Each check's reasons to fail, by name; the turn passes when every list is empty."""
    return {name: check(turn, prompt) for name, check in checks.items()}


def passed(verdict: Mapping[str, list[str]]) -> bool:
    return not any(why for name, why in verdict.items() if name not in SOFT)


def read(path: Path) -> list[dict[str, Any]]:
    """A turn file's turns; a broken last line (a walk that died mid-write) is skipped."""
    turns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            turns.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return turns


def typed(turns: Iterable[Turn]) -> list[Turn]:
    return [t for t in turns if t.get("how") == "typed"]


def which(said: str, by_id: Mapping[str, Prompt], task: str = "") -> str | None:
    """The sheet prompt a typed line is, its blank matching whatever was typed there. A9 and B9
    are the same words, so a line both match is the one of `task`, the task typed before it."""
    hits = [pid for pid, prompt in by_id.items()
            if re.fullmatch(re.escape(prompt.text).replace(re.escape(BLANK), ".+"), said.strip())]
    return next((pid for pid in hits if pid.startswith(task)), hits[0] if hits else None)


# ---- the variants file ---------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    id: str
    #: "wording" for one reworded sheet prompt, else the sequence's kind (out of order, off-script)
    kind: str
    lines: tuple[str, ...]
    #: (index into lines, prompt id) for every line that is checked
    targets: tuple[tuple[int, str], ...]
    held_back: bool
    #: 455: the activity opened by code before the first line; "" for none (`opened`)
    opens: str = ""


def held_back(ids: Sequence[str], seed: str = SEED) -> set[str]:
    """A third of the ids, rounded down, chosen by the order of sha256(seed:id): fixed, seeded,
    and blind to the wording, so nobody picks which ones are kept back."""
    ranked = sorted(ids, key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest())
    return set(ranked[: len(ids) // 3])


_HEAD = re.compile(r"^## ([AB]\d) ", re.M)
_SEQ = "## Sequences"
#: 455: a cell's marker that its case opens an activity by code before its first line
_OPENS = re.compile(r"<br>opens: ([\w-]+)\s*$")
#: 456: a held-back case's words in the tree: kept outside it, in the full sheet
REDACTED = "(held back: kept outside the tree)"
#: 455 r2: the workshop's start line (`move_walk.PROMPTS["stage 1"]`), the activity in words
SETUP = "Start the re-BIA for {}."
#: 456: the fewest words a held-back line has of its own; shorter is common speech
OWN_WORDS = 4


def _groups(text: str) -> dict[str, list[list[str]]]:
    """Each section's table rows below its header line, keyed by prompt id or "SEQ"."""
    groups: dict[str, list[list[str]]] = {}
    for block in re.split(r"(?m)^(?=## )", text):
        head = _HEAD.match(block)
        key = head.group(1) if head else ("SEQ" if block.startswith(_SEQ) else None)
        if key:
            groups[key] = [row for row in _rows(block)[2:] if row and row[0]]
    return groups


def _marks_wrong(rows: list[list[str]]) -> list[str]:
    keep = held_back([row[0] for row in rows])
    return [row[0] for row in rows if (row[-1] == "held back") != (row[0] in keep)]


def variants(text: str, by_id: Mapping[str, Prompt]) -> list[Case]:
    """Every case in a variants file. A wording row is `| id | who | how | wording | mark |`; a
    sequence row is `| id | kind | lines | mark |`, its lines split on " -> ", each a prompt id
    (the sheet's words, checked) or quoted words (off-script, not checked). A cell's `opens`
    marker is not its words (455); a `REDACTED` row is no case here (456: `redacted` lists it)."""
    groups = _groups(text)
    wrong = [i for rows in groups.values() for i in _marks_wrong(rows)]
    if wrong:
        raise ValueError(f"held-back marks differ from the rule (run mark): {wrong}")
    order = list(by_id)
    cases = []
    for pid, rows in groups.items():
        if pid == "SEQ":
            cases += [_sequence(row, by_id) for row in rows
                      if _OPENS.sub("", row[2]).strip() != REDACTED]
            continue
        lead = [by_id[p].text for p in order[: order.index(pid)] if p[0] == pid[0]]
        cases += [Case(row[0], "wording", (*lead, said), ((len(lead), pid),),
                       row[-1] == "held back") for row in rows
                  if (said := _OPENS.sub("", row[3]).strip()) != REDACTED]
    return cases


def _sequence(row: list[str], by_id: Mapping[str, Prompt]) -> Case:
    lines, targets = [], []
    for i, part in enumerate(p.strip() for p in _OPENS.sub("", row[2]).split("->")):
        if part in by_id:
            targets.append((i, part))
            lines.append(by_id[part].text)
        else:
            lines.append(part.strip('"'))
    return Case(row[0], row[1], tuple(lines), tuple(targets), row[-1] == "held back")


def opens(text: str) -> dict[str, str]:
    """455: the activity each marked case opens, by id: the `<br>opens: <activity>` its cell
    carries (10_nemo_design's markers, on the cells of run 2's seven only). Never inferred."""
    return {row[0]: m.group(1) for rows in _groups(text).values() for row in rows
            if (m := _OPENS.search(row[-2]))}


def setup_line(activity: str) -> str:
    """455 r2: the untested line that opens `activity` (a slug) through the app's own path."""
    return SETUP.format(activity.replace("-", " "))


def opened(cases: Iterable[Case], text: str) -> list[Case]:
    """455: each case `text` marks (`opens`) gains its activity's `setup_line` first, its targets
    one line down so the setup line is never scored (r2); every other case is unchanged."""
    marked = opens(text)
    return [replace(c, opens=marked[c.id], lines=(setup_line(marked[c.id]), *c.lines),
                    targets=tuple((i + 1, p) for i, p in c.targets))
            if c.id in marked else c for c in cases]


def redacted(text: str) -> list[str]:
    """456: the ids of the cases whose words a variants file keeps outside the tree."""
    return [row[0] for rows in _groups(text).values() for row in rows
            if _OPENS.sub("", row[-2]).strip() == REDACTED]


def redact(text: str) -> str:
    """456: the file with every held-back case taken down to its id: its id, its mark and any
    `opens` marker stay, its wording or lines become `REDACTED` and every other cell is empty
    (37_nemo_check: the tree carries held-back ids only)."""
    out = []
    for line in text.splitlines(keepends=True):
        row = (_rows(line) or [[]])[0]
        if len(row) >= 4 and row[-1] == "held back" and row[0] != "id":
            marker = m.group(0) if (m := _OPENS.search(row[-2])) else ""
            line = "| " + " | ".join([row[0], *[""] * (len(row) - 3), f"{REDACTED}{marker}",
                                      row[-1]]) + " |\n"
        out.append(line)
    return "".join(out)


def _words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[\w']+", text.lower().translate(_QUOTES)))


def _spoken(words: Iterable[str]) -> str:
    """Words as one string with a space at each end, so a line is found only as whole words."""
    return f" {' '.join(words)} "


def held_back_words(text: str, sheet_at: Path = PROMPTS) -> dict[str, list[str]]:
    """456: each held-back case's own lines in a full variants file, by id, each as `_spoken`
    words: its wording, or a sequence's off-script lines (its prompt ids are the sheet's). A line
    a practice case or the sheet also says is the tree's by right (A9 and B9 are one prompt, so a
    wording can be held back under one and practice under the other; B1-03 is the sheet's own
    words), and a line under `OWN_WORDS` words is common speech, never a holdout's own."""
    said: dict[str, list[str]] = {}
    known = [_spoken(_words(t)) for t in sheet(sheet_at).values()]
    for key, rows in _groups(text).items():
        for row in rows:
            cell = _OPENS.sub("", row[-2]).strip()
            lines = [_words(w) for w in (re.findall(r'"([^"]+)"', cell) if key == "SEQ"
                                         else [cell]) if w != REDACTED]
            if row[-1] == "held back":
                said[row[0]] = [_spoken(w) for w in lines if len(w) >= OWN_WORDS]
            else:
                known += [_spoken(w) for w in lines]
    return {cid: [w for w in lines if not any(w in k for k in known)]
            for cid, lines in said.items()}


def leaks(full: str, paths: Iterable[Path]) -> list[tuple[str, str]]:
    """456: (file, case id) for every file holding one of a held-back case's own lines
    (`held_back_words`), whole, from the full variants text `full`. Only the file and the id are
    named, never the words."""
    own = held_back_words(full)
    out = []
    for path in paths:
        try:
            said = _spoken(_words(path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
        out += [(str(path), cid) for cid, lines in own.items() if any(w in said for w in lines)]
    return out


def mark(text: str) -> str:
    """The file with each table row's last cell set by the held-back rule."""
    out = []
    for block in re.split(r"(?m)^(?=## )", text):
        keep = held_back([r[0] for r in _rows(block)[2:] if r and r[0]])
        lines = []
        for line in block.splitlines(keepends=True):
            row = (_rows(line) or [[]])[0]
            if row and row[0] and not set(row[0]) <= set("-") and row[0] != "id":
                cells_ = line.rstrip("\n").rstrip().rstrip("|").split("|")
                cells_[-1] = " held back " if row[0] in keep else " "
                line = "|".join(cells_) + "|\n"
            lines.append(line)
        out.append("".join(lines))
    return "".join(out)


# ---- 498: the agent cases and the demo's go/no-go (ADR-0053 slice 10) -------------------------

#: the seed seat's expected answers for the 15 prototype asks, copied into the tree whole: v3's
#: A6, B5 and B6 point to their sheet cells, v4's twelve are rows `| id | ask | required | must
#: not | source |`. Practice cases all (498: none of the 15 is held back)
AGENT_CASES = DATA / "agent-cases-15-expected.md"
#: the demo's go/no-go: an agent case passes only if all of its runs pass (pass^4)
AGENT_K = 4
#: the go/no-go's other half, never read here: its items carry held-back lines
HIS_MARKS = ("His blind marks on the 12 (win more than today, lose none): from 13_Langfuse, "
             "not read here")
_SHEET_ROW = re.compile(r"[AB]\d")
_ASK_ROW = re.compile(r"k\d+-\d+")


def agent_asks(text: str) -> dict[str, str]:
    """v4's asks by id, in the file's order."""
    return {row[0]: row[1] for row in _rows(text) if _ASK_ROW.fullmatch(row[0])}


def agent_cases(text: str, by_id: Mapping[str, Prompt]) -> list[Case]:
    """The 15 as cases, practice all: v3's three as a wording case types its prompt (the task's
    sheet prompts before it, then the sheet's own words), v4's each after its group's asks before
    it ("k1-2" after "k1-1"), as the prototype typed each group into one room."""
    order, cases = list(by_id), []
    for pid in (row[0] for row in _rows(text) if _SHEET_ROW.fullmatch(row[0])):
        lead = [by_id[p].text for p in order[: order.index(pid)] if p[0] == pid[0]]
        cases.append(Case(pid, "agent", (*lead, by_id[pid].text), ((len(lead), pid),), False))
    asks = list(agent_asks(text).items())
    for n, (cid, _) in enumerate(asks):
        lines = tuple(a for c, a in asks[: n + 1] if c.split("-")[0] == cid.split("-")[0])
        cases.append(Case(cid, "agent", lines, ((len(lines) - 1, cid),), False))
    return cases


def agent_by_id(seed: Path | None = None, text: str | None = None) -> dict[str, Prompt]:
    """Every sheet prompt (`prompts`) and each v4 ask as a prompt checked by every check and its
    own marks (`Prompt.marks`), its ratings judged against every activity it names."""
    text = text if text is not None else AGENT_CASES.read_text(encoding="utf-8")
    seed = seed or seed_of(Path("."))
    graded = ratings(seed, "")
    return {**prompts(seed=seed), **{cid: Prompt(cid, ask, "answer", (), graded, cid)
                                     for cid, ask in agent_asks(text).items()}}


#: a draft as the app writes one: its "**To …**" line, then its subject
_DRAFT_TO = re.compile(r"^\*\*To (?P<to>[^\n]*)\*\*  \nSubject: ", re.M)
_TABLE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_BULLET = re.compile(r"^\s*(?:\\?[-*•]|\d+\\?[.)])\s+", re.M)  # 747: a letter's are escaped
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n")
_NUMBER = re.compile(r"\b(\d+|" + "|".join(_WORDS) + r")\b")
_NEGATED = re.compile(r"\b(?:not|no|never|nor|isn't|aren't|none)\b")
_RISES = re.compile(r"\b(?:rises?|goes up|increases?|climbs?|jumps?)\b")
_DECIDED = re.compile(r"\b(?:rto|mtpd|recovery (?:time|target|figures?)|longest tolerable outage)\b"
                      r"[^.\n]*\b(?:(?:is|are|was|were) (?:set|fixed|now)|decided|agreed|confirmed"
                      r"|(?:is|are|was|were)\s+(?:at\s+)?\d)")
_STILL_COVERED = re.compile(r"\bstill (?:has|have|had|is|are) (?:cover|covered|enough)\b"
                            r"|\bstill covered\b|\benough technicians\b")
_NAMED_OWNER = re.compile(r"\b(?:[Oo]wner(?: is|:)|owned by)\s+(?:the\s+)?[A-Z]")
_GREETING = re.compile(r"^(?:dear|hello|hi)\s+([^,\n]+)", re.M | re.I)
_HEADCOUNT = re.compile(rf"\b{_N}\s+(?:more\s+)?(?:shifts?|staff|people|employees|workers)\b")
_WEEKDAY = re.compile(r"\b(?:mon|tues|wednes|thurs|fri|satur)day\b")
_SENT = re.compile(r"\b(?:i(?:'ve| have)? sent|has been sent|was sent|have sent)\b")
#: k3-1: where the files say how procurement orders when the systems fail
_ORDERS_BY = re.compile(r"orders are placed by ([\w-]+) and ([\w-]+)")


def _sentences_in(text: str) -> list[str]:
    """Each sentence or line of `text`, as `norm` spells it (split first: `norm` joins lines)."""
    return [norm(s) for s in _SENTENCE.split(text) if s.strip()]


def _spelt(n: int) -> tuple[str, ...]:
    """A count as an answer may say it: its digits, or its word up to twenty."""
    return (str(n), *((_WORDS[n],) if n < len(_WORDS) else ()))


def _holds(seen: str, spellings: Iterable[str]) -> bool:
    return any(holding(norm(s)).search(seen) for s in spellings)


def _need(seen: str, what: str, spellings: Iterable[str]) -> list[str]:
    return [] if _holds(seen, spellings) else [f"missing {what}"]


def _bare_name(cell: str) -> str:
    """A name without its bracket ("Plant Manager (process owner)" is Plant Manager)."""
    return re.split(r"\s*\(", cell)[0].strip()


def _short(name: str) -> str:
    """A company as an answer names it: its first two words ("Marsh Data")."""
    return " ".join(_bare_name(name).split()[:2])


def _asks_of(cid: str) -> list[str]:
    """The case's lines: its group's asks up to its own."""
    asks = agent_asks(AGENT_CASES.read_text(encoding="utf-8"))
    ids = list(asks)
    return [asks[c] for c in ids[: ids.index(cid) + 1] if c.split("-")[0] == cid.split("-")[0]]


def _activities(seed: Path, lines: Iterable[str]) -> list[str]:
    """The activities the lines name, by the app's own reader (t252), in the order said; the first
    line's by one word of their own too (t367: "production"), never a later line's ("Now only legal
    and financial." names classes, not IT financial management)."""
    import PROTOTYPE_core as core

    out: list[str] = []
    for n, line in enumerate(lines):
        out += core.named_in(seed, line) or (core.loosely_named(seed, line) if n == 0 else [])
    return list(dict.fromkeys(out))


def _register(seed: Path) -> dict[str, dict[str, Any]]:
    import PROTOTYPE_draft as drafting

    return {k: r for k, r in drafting.read_register(seed).items() if isinstance(r, dict)}


def _row_named(seed: Path, line: str) -> tuple[str, dict[str, Any]]:
    """The register row whose name (its bracket aside, plural or not) the line says."""
    said = norm(line)
    return next((k, r) for k, r in _register(seed).items()
                if holding(norm(_bare_name(str(r.get("name", ""))))).search(said)
                or holding(norm(_bare_name(str(r.get("name", "")))) + "s").search(said))


def _gist(workaround: str) -> tuple[str, ...]:
    """What an answer holds of a stated workaround: its figures, else its last word."""
    return tuple(re.findall(r"\d+", workaround)) or (re.findall(r"[\w-]+", workaround)[-1],)


def _map_names(seed: Path) -> dict[str, str]:
    import PROTOTYPE_core as core

    return {r.slug: r.name for r in core.process_map_rows(seed)}


def _changes(seed: Path, activity: str) -> tuple[list[str], str]:
    """The activity's newest interview: each change its summary counts ("One: …"), and its text."""
    import PROTOTYPE_core as core

    path = core.this_years_path(seed, activity)
    said = core.summed_up(seed, path) or [] if path else []
    text = (seed / path).read_text(encoding="utf-8") if path else ""
    return [core.COUNTED.sub("", s) for s in said if core.COUNTED.match(s)], text


def _stays(seed: Path, activity: str) -> list[str]:
    """The summary's sentences that are no change: what stays, and what is left open."""
    import PROTOTYPE_core as core

    path = core.this_years_path(seed, activity)
    return [s for s in (core.summed_up(seed, path) or [] if path else [])
            if not core.COUNTED.match(s)]


def _facts_of(change: str, interview: str) -> list[tuple[str, ...]]:
    """What an answer must hold of one change, each with its spellings: its counts (digits or
    words; "three days" also as hours), but a count after "not" (the old figure), and its names
    (a capitalised word the interview never writes in lower case)."""
    said, out = norm(change), []
    for m in _NUMBER.finditer(said):
        if said[: m.start()].endswith("not "):
            continue
        n = _number(m.group(1))
        days = said[m.end():].lstrip().startswith("day")
        out.append((*_spelt(n), *((f"{n * 24} h",) if days else ())))
    lower = set(re.findall(r"\b[a-z][\w-]*", interview))
    out += [(w,) for w in dict.fromkeys(re.findall(r"\b[A-Z][a-z][\w-]+", change))
            if w.lower() not in lower]
    return out


def _changes_held(seen: str, seed: Path, activity: str) -> list[str]:
    changes, text = _changes(seed, activity)
    return [f"missing {fact[0]!r} of this year's change {change!r}" for change in changes
            for fact in _facts_of(change, text) if not _holds(seen, fact)]


def _drafts(turn: Turn) -> list[tuple[str, str]]:
    """Each draft the turn shows: (whom its To line names, the draft to the end of its part)."""
    text = "\n\n".join([str(turn.get("reply") or ""), *map(str, turn.get("cards") or [])])
    found = list(_DRAFT_TO.finditer(text))
    return [(m["to"], text[m.start(): found[i + 1].start() if i + 1 < len(found) else None])
            for i, m in enumerate(found)]


def _method(seed: Path) -> dict[str, Any]:
    import PROTOTYPE_core as core

    method: dict[str, Any] = json.loads((seed / core.walk.METHOD).read_text(encoding="utf-8"))
    return method


def _classes(seed: Path) -> dict[str, str]:
    """The method's impact classes: id -> name, lower case."""
    return {s["id"]: s["name"].lower() for s in _method(seed)["scenarios"]}


def _grids(seed: Path, activity: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(this year's interview's grid, last year's record's) for the activity, as the chart reads
    them: {class: {"72 h": level}}."""
    import impact_chart

    import PROTOTYPE_core as core

    method = _method(seed)
    this, _ = core.this_years_interview(seed, activity, method)
    return this, impact_chart.from_record(core.last_year(seed, activity).get("grid"), method) or {}


def _label(seed: Path) -> dict[int, str]:
    return {s["level"]: s["label"] for s in _method(seed)["severity_scale"]}


# -- each case's marks: (turn, seed, case id) -> reasons to fail -----------------------------------

def _risen(sentence: str, name: str, row: list[tuple[str, int]], label: Mapping[int, str]
           ) -> list[str]:
    """A class said to rise at an hour where this year's grid holds it as at the hour before."""
    if not _RISES.search(sentence):
        return []
    hours = [h for h, _ in row]
    return [f"{name} said to rise at {h}: this year's grid has it {label[row[i][1]]} as before"
            for h in re.findall(r"\b(\d+ h)\b", sentence) if h in hours[1:]
            and row[(i := hours.index(h))][1] <= row[i - 1][1]]


def _last_said(sentence: str, name: str, last: Mapping[str, int], label: Mapping[int, str]
               ) -> list[str]:
    """Last year's class rated as its record never rates it."""
    if "last year" not in sentence:
        return []
    held = {label[v] for v in last.values()}
    return [f"last year's {name} said {lab}: the record has it {' or '.join(sorted(held))}"
            for lab in label.values() if lab not in held and holding(lab).search(sentence)]


def _rated(reply: str, seed: Path, act: str, classes: Mapping[str, str]) -> list[str]:
    """`_risen` and `_last_said` on each sentence of the reply naming a class."""
    label, (this, last), out = _label(seed), _grids(seed, act), []
    for sentence in _sentences_in(reply):
        for c, name in classes.items():
            if holding(name).search(sentence):
                out += _risen(sentence, name, list((this.get(c) or {}).items()), label)
                out += _last_said(sentence, name, last.get(c) or {}, label)
    return out


def _charts(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k1: nemo's own impact chart for every activity the asks name (an added one beside, never
    instead), last year's behind it; no text table instead; where the asks pick classes, no other
    class in what he reads; no class said to rise where this year's grid does not, and last year
    rated only as its record rates it (`_rated`)."""
    import PROTOTYPE_core as core

    asks, names = _asks_of(cid), _map_names(seed)
    acts = _activities(seed, asks)
    reply = str(turn.get("reply") or "")
    cards = [str(c) for c in turn.get("cards") or []]
    charts = {c.split(core.CHART_HEADING)[0].strip("* \n"): c for c in cards
              if core.CHART_HEADING in c}
    out = [f"no impact chart for {names[a]}" for a in acts if names[a] not in charts]
    out += [f"the chart for {n} has no last year behind it" for n, c in charts.items()
            if "last year" not in norm(c)]
    out += ["a text table instead of the chart"] if _TABLE.search(reply) else []
    classes = _classes(seed)
    picked = {c for c, name in classes.items() for line in asks[1:]
              if holding(name).search(norm(line))}
    read = norm("\n".join([reply, *cards]))
    out += [f"names {name}: the asks keep {', '.join(sorted(picked))} only"
            for c, name in classes.items()
            if picked and c not in picked and holding(name).search(read)]
    out += [why for act in acts for why in _rated(reply, seed, act, classes)]
    return list(dict.fromkeys(out))


def _single_source(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k2-1: every supplier the register states as single source, and only those called one; for
    the rest, that the files name no alternative and whom to ask (an owner function of the
    supplier register)."""
    rows = [r for r in _rows((seed / "03_Dependencies/supplier-register.md").read_text(
        encoding="utf-8")) if len(r) >= 6 and r[0] not in ("Supplier", "---")]
    stated = [_bare_name(r[0]) for r in rows if "single source" in norm(" ".join(r[1:4]))]
    seen = norm(shown(turn))
    out = [f"missing {s!r}, the single source the supplier register states" for s in stated
           if not holding(norm(_short(s))).search(seen)]
    if not re.search(r"\bno alternatives?\b", seen):
        out.append("missing that the files name no alternative for the others")
    owners = {_bare_name(r[4]) for r in rows if r[4] and not r[4].startswith("—")}
    out += _need(seen, f"whom to ask ({' or '.join(sorted(owners))})", owners)
    for sentence in _sentences_in(shown(turn)):
        if "single source" in sentence and not _NEGATED.search(sentence):
            out += [f"calls {_bare_name(r[0])!r} a single source: the register does not"
                    for r in rows if _bare_name(r[0]) not in stated
                    and holding(norm(_short(r[0]))).search(sentence)]
    return out


def _dependents(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k2-2: every activity the register row has as a consumer, by name or counted; what it stands
    on; each stated workaround and none made up; no activity of another group; at most three lines
    before the graph link (D1)."""
    import agent_fallback as af
    import live_graph

    import PROTOTYPE_core as core

    _, row = _row_named(seed, _asks_of(cid)[-1])
    reg = _register(seed)
    users = list(row.get("consumers") or [])
    reply = str(turn.get("reply") or "")
    seen = norm(shown(turn))
    out = []
    if not all(holding(norm(c["activity"])).search(seen) for c in users):
        out += _need(seen, f"the {len(users)} activities that use it",
                     [f"{s} activities" for s in _spelt(len(users))])
    boxes = live_graph.data(seed)["whole"]["boxes"].values()
    for d in row.get("depends_on") or []:
        held = [str(reg[d]["name"]), *(str(b["name"]) for b in boxes if d in b["members"])]
        out += _need(seen, f"what it stands on ({reg[d]['name']})", held)
    link = af.GRAPH_LINK.split("](")[0].lstrip("[")
    out += _need(seen, f"{link!r}", [link])
    out += [f"missing {c['activity']}'s workaround ({c['workaround']})" for c in users
            if c.get("workaround") and not _holds(seen, _gist(c["workaround"]))]
    group = {r.group for r in core.process_map_rows(seed)
             if r.name in {c["activity"] for c in users}}
    out += [f"names {r.name}, an activity outside {', '.join(sorted(group))}"
            for r in core.process_map_rows(seed)
            if r.group not in group and holding(norm(r.name)).search(seen)]
    bare = [c["activity"] for c in users if not c.get("workaround")]
    out += [f"a workaround for {a}, where the register states none"
            for s in _sentences_in(shown(turn))
            if "workaround" in s and not _NEGATED.search(s)
            for a in bare if holding(norm(a)).search(s)]
    lines = [x for x in reply.splitlines() if x.strip() and link not in x]
    if len(lines) > af.MOST:
        out.append(f"{len(lines)} lines before the graph link: at most {af.MOST}")
    return out


def _owners(seed: Path) -> tuple[list[str], list[str], list[str]]:
    """(the plan's process owners with no deputy named, those with one, each by function; and
    every other position of the records with no deputy named), from the plan and the org table."""
    plan = (seed / "01_Organisation/bia-programme-plan.md").read_text(encoding="utf-8")
    owners = list(dict.fromkeys(r[2] for r in _rows(plan) if re.fullmatch(r"[\d.]+", r[0])))
    org = [r for r in _rows((seed / "01_Organisation/org-and-roles.md").read_text(
        encoding="utf-8")) if len(r) >= 3 and r[1] and r[0] not in ("Position", "---")]
    held: dict[str, tuple[str, str]] = {}
    for r in org:
        if r[1] in owners:
            held.setdefault(r[1], (_bare_name(r[0]), r[2]))
    others = [_bare_name(r[0]) for r in org if len(r) >= 4 and re.fullmatch(r"[\d.,\s]+", r[3])
              and r[1] not in owners and r[2] == "—"]
    return ([f for f, d in held.values() if d == "—"], [f for f, d in held.values() if d != "—"],
            others)


def _deputies(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k2-3: the count of process owners with no deputy named, each by function, and those with
    one; "none named", never "no deputy" as a fact; no position that owns no process."""
    none, some, others = _owners(seed)
    seen = norm(shown(turn))
    out = _need(seen, f"the count of process owners with no deputy named ({len(none)})",
                _spelt(len(none)))
    out += [f"missing {f!r}, a process owner" for f in [*none, *some]
            if not holding(norm(f)).search(seen)]
    out += [f"says {m.group(0)!r}: the files name none, which is not that none exists"
            for m in re.finditer(r"\bno deput(?:y|ies)\b(?!\s+(?:is\s+|are\s+|was\s+)?named)"
                                 r"|\bno deputy exists\b", seen)]
    out += [f"names {f!r}, who owns no process" for f in others if holding(norm(f)).search(seen)]
    return out


def _backup(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k3-1: names what is meant, this year's backup system, and what is left if both fail (the
    activities with no workaround for it, how procurement orders), or asks which with two taps."""
    ask = _asks_of(cid)[-1]
    acts = [a for a in _map_names(seed) if any("backup" in c for c in _changes(seed, a)[0])]
    change = next(c for a in acts for c in _changes(seed, a)[0] if "backup" in c)
    text = _changes(seed, acts[0])[1]
    meant = re.search(r"\b(backup [\w ]+? system)\b", change)[1]  # type: ignore[index]
    place = next(w for w in re.findall(r"\b[A-Z][a-z]\w+", ask) if w in change)
    options = [norm(str(o)) for o in turn.get("options") or []]
    if "?" in str(turn.get("reply") or "") and any(norm(meant) in o for o in options) and any(
            norm(place) in o and norm(meant) not in o for o in options):
        return []
    seen = norm(shown(turn))
    out = _need(seen, f"what is meant ({meant!r})", [meant])
    system = re.search(rf"{meant.removeprefix('backup ')},\s+([A-Z]\w+)", text)
    rows = [r for r in _register(seed).values() if system
            and str(r.get("name", "")).startswith(system[1])]
    blocked = [c["activity"] for r in rows for c in r.get("consumers") or []
               if str(c.get("workaround", "")).lower().startswith("no workaround")]
    if blocked:
        out += _need(seen, "that there is no workaround", ["no workaround"])
        out += [f"missing {a}, which has no workaround" for a in blocked
                if not holding(norm(a)).search(seen)]
    ways = {w for r in _register(seed).values()
            for m in _ORDERS_BY.finditer(json.dumps(r, ensure_ascii=False)) for w in m.groups()}
    out += [f"missing how procurement orders ({w})" for w in sorted(ways)
            if not _holds(seen, {w, w.replace("-", "")})]
    return out


def _technicians(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k3-2: this year's technicians (the change's counts), never last year's as today's, no cover
    left; external technicians; the owner by function."""
    acts = [a for a in _map_names(seed) if any("technician" in c for c in _changes(seed, a)[0])]
    change = next(c for c in _changes(seed, acts[0])[0] if "technician" in c)
    text = _changes(seed, acts[0])[1]
    seen = norm(shown(turn))
    out = [f"missing {f[0]!r} of this year's change {change!r}"
           for f in _facts_of(change, text) if not _holds(seen, f)]
    old = re.search(r"\bnot (\w+)", norm(change))
    for sentence in _sentences_in(shown(turn)):
        if old and "technician" in sentence and _holds(sentence, _spelt(_number(old[1]))) and not (
                re.search(rf"\bnot (?:{'|'.join(_spelt(_number(old[1])))})\b", sentence)
                or re.search(r"\b(?:last year|before|was|were|instead)\b", sentence)):
            out.append(f"says {old[1]} technicians as today's: this year's change says not "
                       f"{old[1]}")
    out += [f"says {m.group(0)!r}: two lost at night leave none" for m in
            _STILL_COVERED.finditer(seen)]
    reg = _register(seed)
    rows = [r for r in reg.values() if norm(str(r.get("name"))) in ("technician", "technicians")]
    out += [f"missing the owner, by function ({_bare_name(str(r['owner_name']))})" for r in rows
            if r.get("owner_name") and not holding(norm(_bare_name(str(r["owner_name"])))).search(
                seen)]
    if any("external" in norm(str(r.get("name"))) and "technician" in norm(str(r.get("name")))
           for r in reg.values()):
        out += _need(seen, "the external technicians", ["external"])
    return out


def _reached(reg: Mapping[str, Mapping[str, Any]], key: str) -> tuple[list[str], set[str]]:
    """(the rows that stand on `key` directly, every activity using it or a row on it at any
    depth)."""
    over = [k for k, r in reg.items() if key in (r.get("depends_on") or [])]
    seen, todo = {key}, [key]
    while todo:
        k = todo.pop()
        for j, r in reg.items():
            if k in (r.get("depends_on") or []) and j not in seen:
                seen.add(j)
                todo.append(j)
    return over, {c["activity"] for k in seen for c in reg[k].get("consumers") or []}


def _outage(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k3-3: how many rows run on it and how many activities that reaches (counted), its direct
    users and their workarounds, what it stands on, no single owner (never "no owner", never a
    named one) and no recovery target made up."""
    key, row = _row_named(seed, _asks_of(cid)[-1])
    reg = _register(seed)
    over, acts = _reached(reg, key)
    reply = str(turn.get("reply") or "")
    seen = norm(shown(turn))
    out = _need(seen, f"how many rows run on it ({len(over)})", _spelt(len(over)))
    out += _need(seen, f"how many activities that reaches ({len(acts)})", _spelt(len(acts)))
    for c in row.get("consumers") or []:
        out += _need(seen, f"its direct user {c['activity']!r}", [c["activity"]])
        if c.get("workaround"):
            out += _need(seen, f"{c['activity']}'s workaround ({c['workaround']})",
                         _gist(c["workaround"]))
    out += [f"missing what it stands on ({reg[d]['name']})" for d in row.get("depends_on") or []
            if not holding(norm(_bare_name(str(reg[d]["name"])))).search(seen)]
    if not row.get("owner_name"):
        out += _need(seen, "that no single owner is named", ["no single owner"])
        out += [f"says {m.group(0)!r}" for m in re.finditer(r"\bno owner\b", seen)]
        out += [f"names an owner: {m.group(0)!r}" for m in _NAMED_OWNER.finditer(reply)]
    if not row.get("rto"):
        own = (norm(_bare_name(str(row["name"]))), "itself", "its own")
        out += [f"a recovery target the register does not state: {s!r}"
                for s in _sentences_in(shown(turn)) if any(o in s for o in own)
                and re.search(r"\b(?:recovery target|rto)\b", s) and re.search(r"\d+ h\b", s)
                and not _NEGATED.search(s)]
    return out


def _letter(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k4-1: a draft to the role the ask names, by its role, asking its consent; why: every
    activity the register has needing it, counted; no date, no headcount, no agreement said, no
    other name, never sent."""
    _, row = _row_named(seed, _asks_of(cid)[-1])
    role = _bare_name(str(row["name"]))
    letters = [(to, d) for to, d in _drafts(turn) if holding(norm(role)).search(norm(to))]
    if not letters:
        return [f"no draft to the {role.lower()}"]
    body = norm(letters[0][1])
    asked = norm(_asks_of(cid)[-1])
    wants = re.search(r"\(([^)]*)\)", str(row["name"]))
    words = [w for w in re.findall(r"\w+", norm(wants[1]) if wants else "")
             if holding(w).search(asked)]
    out = [f"missing {w!r}" for w in ["consent", *words] if not holding(w).search(body)]
    users = row.get("consumers") or []
    if not re.search(r"\bevery (?:core )?activit|\ball (?:core )?activit", body):
        out += _need(body, f"why: the {len(users)} activities that need it",
                     [f"{s} {k}activities" for s in _spelt(len(users)) for k in ("", "core ")])
    out += [f"a date: {m.group(0)!r}" for m in [*_DATE.finditer(body), *_WEEKDAY.finditer(body)]]
    out += [f"a headcount: {m.group(0)!r}" for m in _HEADCOUNT.finditer(body)]
    out += [f"an agreement: {m.group(0)!r}" for m in re.finditer(r"\b(?:agreed|approved)\b", body)]
    out += [f"says it was sent: {m.group(0)!r}" for m in _SENT.finditer(norm(shown(turn)))]
    out += [f"greets {m[1]!r}: the register names no holder" for m in _GREETING.finditer(
        letters[0][1]) if not holding(norm(role)).search(norm(m[1]))]
    return out


def _board(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k4-2: as many bullets as asked, to the board by function: this year's changes, where the
    grid turns high, the recovery figures still open and never as decided."""
    ask = _asks_of(cid)[-1]
    act = _activities(seed, [ask])[0]
    reply = str(turn.get("reply") or "")
    seen = norm(shown(turn))
    want = _number(next(m[1] for m in _NUMBER.finditer(norm(ask))))
    out = [] if len(_BULLET.findall(reply)) == want else [
        f"{len(_BULLET.findall(reply))} bullets: {want} asked"]
    out += _need(seen, "the board, by function", ["board"])
    out += _changes_held(seen, seed, act)
    this, _ = _grids(seed, act)
    high = next(lv for lv, lab in _label(seed).items() if lab == "high")
    hours = sorted({int(h.split()[0]) for c in this.values() for h, v in c.items() if v >= high})
    if hours:
        at = f"{hours[0]} h"
        out += _need(seen, f"high from {at}", next((g for g in SAME if at in g), (at,)))
        out += _need(seen, "the rating high", ["high"])
    out += _need(seen, "that the recovery figures are still open", ["open"])
    out += [f"recovery figures as decided: {m.group(0)!r}" for m in _DECIDED.finditer(seen)]
    return out


def _summary_mail(turn: Turn, seed: Path, cid: str) -> list[str]:
    """k4-3: one draft, to the function the ask names: this year's changes, all of them and no
    other count of them, what stays as last year, the analysis still open, nothing decided."""
    ask = _asks_of(cid)[-1]
    to = next(f for group in _owners(seed) for f in group if holding(norm(f)).search(norm(ask)))
    letters = _drafts(turn)
    if len(letters) != 1 or not holding(norm(to)).search(norm(letters[0][0])):
        return [f"{len(letters)} drafts ({', '.join(t for t, _ in letters) or 'none'}): one to "
                f"the {to} asked"]
    body = norm(letters[0][1])
    act = next(a for a in _map_names(seed) if _changes(seed, a)[0]
               and holding(norm(to)).search(norm(_changes(seed, a)[1])))
    out = _changes_held(body, seed, act)
    stay = [s for s in _stays(seed, act) if "as last year" in norm(s)]
    out += [f"missing what stays: {s!r}" for s in stay if "as last year" not in body]
    out += _need(body, "that the analysis is still open", ["open"])
    n = len(_changes(seed, act)[0])
    out += [f"says {m.group(0)!r}: this year's interview counts {n}"
            for m in re.finditer(rf"\b{_N}\s+(?:\w+\s+)?changes?\b", body)
            if _number(m.group(1)) != n]
    out += [f"recovery figures as decided: {m.group(0)!r}" for m in _DECIDED.finditer(body)]
    return out


Mark = Callable[[Turn, Path, str], list[str]]


class Marked(NamedTuple):
    """An agent case's topic, as the report shows it beside its id, and its own marks."""
    topic: str
    mark: Mark | None


#: each of the 15 by its topic; v4's twelve with their own marks, v3's three the sheet's prompts
#: and their cells (no marks of their own)
AGENT_MARKS: dict[str, Marked] = {
    "A6": Marked("dependency changes", None), "B5": Marked("failure points", None),
    "B6": Marked("process dependencies", None),
    "k1-1": Marked("impact over time", _charts), "k1-2": Marked("legal and financial", _charts),
    "k1-3": Marked("adds order picking", _charts),
    "k2-1": Marked("single-source suppliers", _single_source),
    "k2-2": Marked("refrigeration dependents", _dependents),
    "k2-3": Marked("deputies named?", _deputies),
    "k3-1": Marked("backup failure", _backup), "k3-2": Marked("night technicians", _technicians),
    "k3-3": Marked("network outage", _outage),
    "k4-1": Marked("works council letter", _letter), "k4-2": Marked("board bullets", _board),
    "k4-3": Marked("changes summary", _summary_mail),
}


def agent_report(scored: Mapping[str, Any]) -> str:
    """The demo's go/no-go as code can give it: each agent case by its topic, whether all k runs
    passed and why one failed, the code half GO only when every case passes, his half a named
    slot. It reports; the switch is his, and nothing here reads or sets it."""
    cases = scored["cases"]
    k = scored["k"]
    passed = sum(c["pass_k"] for c in cases.values())
    lines = [f"Agent cases (ADR-0053's go/no-go): {passed} of {len(cases)} passed all {k} runs",
             ""]
    for cid, c in cases.items():
        why = f": {c['why'][0]}" if c["why"] else ""
        lines.append(f"- {cid} ({AGENT_MARKS[cid].topic}): {'pass' if c['pass_k'] else 'FAIL'}"
                     f" ({c['passes']}/{c['of']}){'' if c['pass_k'] else why}")
    lines += ["", f"Code half: {'GO' if passed == len(cases) else 'NO-GO'}", HIS_MARKS,
              "For the demo the agent stays ON only if both halves are GO; otherwise OFF. He "
              "flips the switch; this report never does."]
    return "\n".join(lines)


# ---- 534: his walk rows of 19 Oct as two-turn cases, and the floor ---------------------------

#: a walk row's `Case.kind`
ROW = "walk row"
#: the slot B8 is typed with in a row: the S0 probe's, the plan's Status cell day (l.15)
SLOT = "Tuesday 17 November 2026 at 10:00"
#: the artefact templates a model-led turn shows (t532's `artefacts_shown`): the chart is 499's,
#: the letter and the invitation the S0 probe's (t531), which S7 and S8 build on
CHART, LETTER, INVITATION = "impact_over_time", "letter", "invitation"
#: his 5 walk rows of 19 Oct (problem.md "What he saw"; the S0 probe's R1-R5, t531), practice all,
#: kept as data (`prompt-check/walk-rows.json`): the task's sheet prompts up to the one named lead
#: in (its blank filled with `SLOT`), then the row's two lines, each a sheet prompt by its id or his
#: own words, both checked
WALK_ROWS: dict[str, tuple[str, tuple[str, str]]] = {
    rid: (last, (lines[0], lines[1])) for rid, (last, lines) in json.loads(
        (DATA / "walk-rows.json").read_text(encoding="utf-8"))["rows"].items()}
#: ADR-0056 decision 15: the 18 at 16 good or more in the seed seat's content read, the rest
#: partly, none wrong
FLOOR_GOOD = 16


def _row_ids(rid: str) -> tuple[str, str]:
    return f"{rid}a", f"{rid}b"


def walk_rows(by_id: Mapping[str, Prompt]) -> list[Case]:
    """His 5 walk rows as two-turn cases (`WALK_ROWS`), each checked on its two lines by the
    prompts `row_by_id` gives them."""
    order, cases = [p for p in by_id if _SHEET_ROW.fullmatch(p)], []
    for rid, (last, lines) in WALK_ROWS.items():
        lead = [by_id[p].text.replace(BLANK, SLOT) for p in order[: order.index(last) + 1]
                if p[0] == last[0]]
        said = [by_id[x].text if x in by_id else x for x in lines]
        cases.append(Case(rid, ROW, (*lead, *said),
                          tuple((len(lead) + n, pid) for n, pid in enumerate(_row_ids(rid))),
                          False))
    return cases


def sheet_cases(by_id: Mapping[str, Prompt]) -> list[Case]:
    """534: the 18 sheet prompts as the floor's cases, each after its task's prompts before it (the
    sheet's words, B8's blank filled with `SLOT`), only its own line checked."""
    order, cases = [p for p in by_id if _SHEET_ROW.fullmatch(p)], []
    for pid in order:
        lead = [by_id[p].text.replace(BLANK, SLOT) for p in order[: order.index(pid) + 1]
                if p[0] == pid[0]]
        cases.append(Case(pid, "sheet", tuple(lead), ((len(lead) - 1, pid),), False))
    return cases


def row_by_id(seed: Path | None = None) -> dict[str, Prompt]:
    """Every sheet prompt (`prompts`) and each walk row's line as a prompt checked by every check
    and its row's marks (`ROW_MARKS`). A row line that is a sheet prompt of the row's own task
    keeps that prompt's route and facts (R3's A7); in another task's room it keeps neither."""
    sheet_ = prompts(seed=seed)
    out = dict(sheet_)
    for rid, (last, lines) in WALK_ROWS.items():
        for pid, x in zip(_row_ids(rid), lines, strict=True):
            own = sheet_.get(x) if x in sheet_ and x[0] == last[0] else None
            out[pid] = Prompt(pid, sheet_[x].text if x in sheet_ else x,
                              own.route if own else "answer", own.facts if own else (),
                              own.ratings if own else None, pid)
    return out


def _task_activity(cid: str) -> str:
    """The activity of the task a row's lead types (the marks' own table)."""
    return activities(MARKS.read_text(encoding="utf-8"))[WALK_ROWS[cid[:-1]][0][0]]


#: a line that takes classes off a chart ("without the image", "do not keep … financials")
_DROPS = re.compile(r"\b(?:without|not keep|don't keep|drop|remove|leave out|except|take out"
                    r"|minus|no more)\b")


def _class_edit(line: str, classes: list[str], seed: Path) -> list[str]:
    """The classes a chart keeps after his line: those it names taken off where it says so, those
    alone where it names them plainly, unchanged where it names none ("that did not work")."""
    said, every = norm(line), _classes(seed)
    named = [c for c, name in every.items()  # "financials" names financial
             if any(holding(w).search(said) for w in (norm(c), name, f"{norm(c)}s", f"{name}s"))]
    if not named:
        return classes
    if _DROPS.search(said):
        return [c for c in classes if c not in named]
    return [c for c in every if c in named]


def _asked_chart(turn: Turn, seed: Path) -> tuple[list[str], list[str], Any] | None:
    """The chart his lines ask for: the first chart shown before them, its activities and years,
    with the classes his typed lines since leave (`_class_edit`); None where none was shown."""
    earlier = list(turn.get("earlier") or [])
    start = next((n for n, e in enumerate(earlier) if e["charts"]), None)
    if start is None:
        return None
    first = earlier[start]["charts"][0]
    classes = list(first["classes"] or _classes(seed))
    for e in [*earlier[start + 1:], {"said": turn.get("said"), "how": "typed"}]:
        if e.get("how") == "typed":
            classes = _class_edit(str(e.get("said") or ""), classes, seed)
    return first["activities"], classes, first["years"]


def _chart_follow_up(turn: Turn, seed: Path, cid: str) -> list[str]:
    """R1, R2: the chart shown before his lines, drawn again for the same activities and years with
    the classes his lines leave (`_asked_chart`), read from the artefact's arguments."""
    asked = _asked_chart(turn, seed)
    if asked is None:
        return ["no chart before his line to change"]
    acts, classes, years = asked
    charts = charts_shown(turn)
    if not charts:
        return [f"no chart drawn again: his lines leave {', '.join(classes)} of "
                f"{', '.join(acts)}"]
    out = []
    for c in charts:
        drawn_ = list(c["classes"] or _classes(seed))
        out += [f"draws {', '.join(c['activities']) or 'no activity'}: the chart he changes is "
                f"{', '.join(acts)}"] if c["activities"] != acts else []
        out += [f"draws {', '.join(drawn_)}: his lines leave {', '.join(classes)}"] \
            if set(drawn_) != set(classes) else []
        out += [f"draws the years {c['years']}: the chart he changes has {years}"] \
            if years and c["years"] and c["years"] != years else []
    return out


def _by_function(turn: Turn, seed: Path, cid: str) -> list[str]:
    """R3's first line ("Who has to decide …"): answered by function (U3)."""
    seen = norm(shown(turn))
    named = [f for f in functions(MARKS.read_text(encoding="utf-8"))
             if holding(norm(f)).search(seen)]
    return [] if named else ["names no function of the organisation file"]


def _letters(turn: Turn) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    """The drafts he sees (`_drafts`) and the letter artefacts the turn showed."""
    return _drafts(turn), [a for a in turn.get("artefacts_shown") or []
                           if a.get("template") == LETTER]


def _letter_shape(turn: Turn) -> list[str]:
    """A letter, not code's fixed gap drafts (one "Quick check" per open gap), to functions of the
    organisation file and with no address in it (code maps a function to its address)."""
    import PROTOTYPE_core as core

    seen, led = _letters(turn)
    if not seen and not led:
        return ["no draft"]
    fixed = core.DRAFT_SUBJECT.split("{")[0]
    out = ["code's fixed gap drafts, not a letter"] if seen and all(
        fixed in d for _, d in seen) else []
    names = functions(MARKS.read_text(encoding="utf-8"))
    out += [f"to {to!r}: no function of the organisation file" for to, _ in seen
            if not any(holding(norm(f)).search(norm(to)) for f in names)]
    out += ["an address in a draft: code maps a function to its address" for _, d in seen
            if "@" in d][:1]
    return out


def _letter_asked(turn: Turn, seed: Path, cid: str) -> list[str]:
    """R3's write ask: a letter to the people responsible, by function (`_letter_shape`)."""
    return _letter_shape(turn)


#: 580: what the calendar server holds after a turn, as a night journey read it where he would
#: look (`night_journeys`): each event's id and day, [{"uid": …, "day": "YYYY-MM-DD"}]
SERVER = "calendar"

_ON_DAY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)? (" + "|".join(_MONTHS) + r")\b|\b("
                     + "|".join(_MONTHS) + r") (\d{1,2})(?:st|nd|rd|th)?\b")


def _invitations(turns: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [a for t in turns for a in t.get("artefacts_shown") or []
            if a.get("template") == INVITATION and isinstance(a.get("arguments"), dict)]


def _asked_day(turn: Turn) -> datetime.date | None:
    """The day his line names, in the year of the invitation shown before it, else of the last
    year an earlier line typed; None where it names no day or no year is known."""
    m = _ON_DAY.search(norm(str(turn.get("said") or "")))
    earlier = list(turn.get("earlier") or [])
    years = [str(a["arguments"].get("date") or "")[:4] for a in _invitations(earlier)]
    years += [y for e in earlier for y in re.findall(r"\b(20\d\d)\b", str(e.get("said") or ""))]
    if not m or not years or not years[-1].isdigit():
        return None
    day, month = (m[1], m[2]) if m[1] else (m[4], m[3])
    try:
        return datetime.date(int(years[-1]), _MONTHS.index(month) + 1, int(day))
    except ValueError:
        return None


def _says_day(seen: str, day: datetime.date) -> bool:
    month = _MONTHS[day.month - 1]
    return bool(re.search(rf"\b(?:{day.day} {month}|{month} {day.day})\b", seen))


#: 723: a span of hours: no file holds an end hour, so no card over a move may state one
_END_HOUR = re.compile(r"\b\d\d?:\d\d\s*(?:[–—-]|to\b|until\b|till\b)\s*\d\d?:\d\d\b", re.I)


def _card_states_end_hour(seen: str) -> bool:
    """723: a line of code's card over a move (`led_turn.INVITE_MOVE`) states a span of hours."""
    import led_turn

    opening, rest = led_turn.INVITE_MOVE.split("{activity}")
    head = rest.split("{when}")[0]
    return any(line.startswith(opening) and head in line and _END_HOUR.search(line)
               for line in seen.splitlines())


def _planned_for(seen: str, day: datetime.date) -> bool:
    """596: code's card over a move before his tap (`led_turn.INVITE_MOVE`) would move it to `day`.
    723: the day in its {when}; its "It is planned for" holds the day it leaves. A card stating
    an end hour is refused."""
    import led_turn

    opening, rest = led_turn.INVITE_MOVE.split("{activity}")
    head, rest = rest.split("{when}")
    tail = rest.split("{was}")[0]
    return any(_says_day(norm(line.partition(head)[2].partition(tail)[0]), day)
               for line in seen.splitlines()
               if line.startswith(opening) and not _card_states_end_hour(line))


def _on_server(turn: Turn, day: datetime.date) -> list[str]:
    """580: R4 read where he would look, the calendar server (`SERVER`, read after his tap): the
    one event the server held before his line now on `day`, its id kept; never a second event
    beside the one left where it was. Nemo's record and its card say nothing here."""
    earlier = [e[SERVER] for e in turn.get("earlier") or [] if e.get(SERVER) is not None]
    held = {e["uid"]: e["day"] for e in turn[SERVER]}
    was = {e["uid"]: e["day"] for e in earlier[-1]} if earlier else {}
    on_day = [u for u, d in held.items() if d == day.isoformat()]
    if on_day and any(u in was for u in on_day):
        return []
    if on_day and not was:  # 580 review: nothing on the server before his line, so no move
        return [f"the calendar server held no event before his line: {', '.join(on_day)} on "
                f"{day.isoformat()} is a new one, not the one moved"]
    if on_day:
        return [f"a second event on {day.isoformat()} ({', '.join(on_day)}), not the one moved"]
    kept = [f"{u} on {held[u]}" for u in was if u in held] or [
        f"{u} on {d}" for u, d in held.items()]
    return [f"the calendar server holds {', '.join(kept) or 'no event'}, not {day.isoformat()}: "
            "nothing moved"]


def _moved_invitation(turn: Turn, seed: Path, cid: str) -> list[str]:
    """R4's "do it on <day>": the one event moved (the invitation shown before, its id kept) to
    the day his line names; every weekday said is that day's, as code computes it. 596: code's
    card planning the move to that day (`_planned_for`) meets it; nothing moves before his tap.
    580: where the calendar server was read after his tap (`SERVER`, every night journey reads
    it), the server decides the move (`_on_server`), not what nemo recorded or showed; a run
    with no server read (the move check's) reads nemo's record as before."""
    day = _asked_day(turn)
    if day is None:
        return ["no day in his line to move the invitation to"]
    shown_ = _invitations([turn])
    before = _invitations(turn.get("earlier") or [])
    out = []
    moved = [a for a in shown_ if a["arguments"].get("date") == day.isoformat()]
    if turn.get(SERVER) is not None:
        out += _on_server(turn, day)
    elif not moved and not _planned_for(shown(turn), day):
        out.append(f"no invitation moved to {day:%A} {day.day} {day:%B %Y}")
    elif moved and before and not any(a.get("id") == before[-1].get("id") for a in moved):
        out.append("a second invitation, not the one event moved")
    if _card_states_end_hour(shown(turn)):
        out.append("the card states an end hour no file holds")
    weekday = f"{day:%A}".lower()
    out += [f"says {w}: {day.day} {day:%B %Y} is a {weekday}"
            for w in dict.fromkeys(_WEEKDAY.findall(norm(shown(turn)))) if w != weekday]
    return out


def _new_letter(turn: Turn, seed: Path, cid: str) -> list[str]:
    """R4's "create a new email draft" after the move: a new letter (no earlier draft's id
    rewritten) naming the day the invitation moved to; not code's fixed gap drafts."""
    out = _letter_shape(turn)
    if out == ["no draft"]:
        return out
    earlier = list(turn.get("earlier") or [])
    dates = [str(a["arguments"].get("date") or "") for a in _invitations(earlier)]
    day = next((d for d in reversed(dates) if re.fullmatch(r"\d{4}-\d\d-\d\d", d)), "")
    if day and not _says_day(norm(shown(turn)), datetime.date.fromisoformat(day)):
        out.append(f"the draft does not name the day the interview moved to ({day})")
    before = {a.get("id") for e in earlier for a in e.get("artefacts_shown") or []
              if a.get("template") == LETTER}
    out += ["rewrites an earlier draft: a new one was asked"
            for a in _letters(turn)[1] if a.get("id") in before][:1]
    return out


def spof_rows(seed: Path, activity: str) -> list[str]:
    """The register rows of `activity` flagged as a single point of failure by the one stated rule
    (`workspace.flagged`, no workaround stated), by resource name."""
    import workspace

    name = _map_names(seed)[activity]
    return [str(asset.get("name")) for asset in _register(seed).values()
            for row in asset.get("consumers") or []
            if isinstance(row, dict) and row.get("activity") == name
            and workspace.flagged(asset, row)]


_SPOF = r"(?:spofs?|single points? of failure)"
#: a yes: "yes", "has / there are … SPOFs", and (619) "no — the opposite", "the SPOFs stand",
#: "is still a SPOF"
_HAS_SPOF = re.compile(rf"^yes\b|\b(?:does|do|has|have|there (?:is|are))\b[^\n]{{0,40}}?\b{_SPOF}"
                       rf"|^no\W+the opposite\b|\bthe {_SPOF} (?:stand|exist)s?\b"
                       rf"|\bis (?:still )?an? {_SPOF}")
_NO_SPOF = re.compile(rf"\b(?:no|not any|none of|nothing)\s+(?:\w+\s+){{0,2}}?{_SPOF}")
#: (619, Amend 2) a negation that denies the SPOF itself: such a line is never a yes. "none …" or
#: "nothing …" before it, "not / no longer" up to two words before it, "no more / any more /
#: no longer" right after it; a "not" in another clause leaves the yes
_DENY_SPOF = re.compile(rf"\b(?:none|nothing)\b[^\n]{{0,40}}?\b{_SPOF}"
                        rf"|\b(?:not|no longer)\s+(?:\w+\s+){{0,2}}?{_SPOF}"
                        rf"|\b{_SPOF}\s+(?:\w+\s+)?(?:no more|any ?more|no longer)\b")


def _spof_verdict(turn: Turn, seed: Path, cid: str) -> list[str]:
    """R5: a yes/no on single points of failure that agrees with the register's flagged rows for
    the row's activity (`spof_rows`): never "no" where it flags any, never "yes" where it flags
    none; a list of the register with no verdict is no answer (his walk: the card, twice)."""
    act = _task_activity(cid)
    rows = spof_rows(seed, act)
    seen = [norm(s) for s in _SENTENCE.split(shown(turn)) if s.strip()]
    yes = any(_HAS_SPOF.search(s) and not _DENY_SPOF.search(s) for s in seen)
    no = any(_NO_SPOF.search(s) for s in seen)
    if rows and (no or not yes):
        return [f"no yes where the register flags {len(rows)} rows with no workaround "
                f"({_map_names(seed)[act]})"]
    if not rows and (yes or not no):
        return [f"no plain no: the register flags no row of {_map_names(seed)[act]}"]
    return []


#: each walk row line's own marks, by its id (`row_marks`)
ROW_MARKS: dict[str, Mark] = {
    "R1a": _chart_follow_up, "R1b": _chart_follow_up, "R2a": _chart_follow_up,
    "R2b": _chart_follow_up, "R3a": _by_function, "R3b": _letter_asked,
    "R4a": _moved_invitation, "R4b": _new_letter, "R5a": _spof_verdict, "R5b": _spof_verdict,
}


def floor(scored: Mapping[str, Any], content_read: tuple[int, int, int] | None
          ) -> tuple[bool, str]:
    """ADR-0056 decision 15 for a move carrying the model-led path: his 5 walk rows pass (by most
    runs where the move check scored `pass_most`, else every run) and the seed seat's content read
    of the 18 is `FLOOR_GOOD` good or more, the rest partly, none wrong. Code scores the rows; the
    read is the seed seat's (good, partly, wrong), its slot "not read" until given. Each failing
    row names the axis of each reason (`AXES`)."""
    cases = scored["cases"]
    lines, passing = [], 0
    for rid in WALK_ROWS:
        c = cases.get(rid)
        if c is None:
            lines.append(f"  - {rid} NOT RUN")
        elif c.get("pass_most", c["pass_k"]):
            passing += 1
        else:
            lines.append(f"  - {rid} FAIL ({c['passes']}/{c['of']}): " + "; ".join(
                f"{axis_of(w)}: {w}" for w in dict.fromkeys(c["why"])))
    n = len(sheet())
    sheet_ran = [c for i, c in cases.items() if _SHEET_ROW.fullmatch(i)]
    by_code = [f"- the {n} workshop prompts by code (information; the content read decides): "
               f"{sum(bool(c.get('pass_most', c['pass_k'])) for c in sheet_ran)} of "
               f"{len(sheet_ran)} pass"] if sheet_ran else []
    if content_read is None:
        read_ok, said = False, "not read yet (the seed seat's slot)"
    else:
        good, partly, wrong = content_read
        read_ok = good >= FLOOR_GOOD and wrong == 0 and good + partly == n
        said = f"{good} good / {partly} partly / {wrong} wrong: {'met' if read_ok else 'NOT MET'}"
    met = read_ok and passing == len(WALK_ROWS)
    return met, "\n".join([
        "Floor (ADR-0056 decision 15; a move carrying the model-led path):",
        f"- his {len(WALK_ROWS)} walk rows: {passing} of {len(WALK_ROWS)} pass", *lines,
        f"- the {n} workshop prompts, the seed seat's content read (floor {FLOOR_GOOD}/"
        f"{n - FLOOR_GOOD}/0): {said}", *by_code,
        f"Floor: {'MET' if met else 'NOT MET'}"])


# ---- the runner and the scorer -------------------------------------------------------------

#: given a fresh room's code and the lines to type in order, type them and return its turn file
Sender = Callable[[str, Sequence[str]], Path]


def room_code(room: str, case: Case, run: int) -> str:
    return f"{room}-{case.id.lower()}-{run}"


def saved(out: Path, case: Case, run: int) -> Path:
    return out / case.id / f"{run}.jsonl"


def files(keep: Path) -> Path:
    """Where the files a saved run's turns produced are kept, beside its turn file."""
    return keep.with_suffix("")


def run(cases: Iterable[Case], room: str, send: Sender, out: Path, k: int = K,
        say: Callable[[str], None] = print) -> None:
    """Each case k times, each time into a fresh room, one at a time; every turn file is kept, and
    beside it (`files`) every file its turns produced. A run already saved is not sent again, so a
    stopped walk resumes where it stopped."""
    for case in cases:
        for n in range(1, k + 1):
            keep = saved(out, case, n)
            if keep.exists():
                continue
            turns = send(room_code(room, case, n), case.lines)
            keep.parent.mkdir(parents=True, exist_ok=True)
            made = turns.parent.parent
            for name in {a for t in read(turns) for a in t.get("artefacts") or {}}:
                if (made / name).is_file():
                    (files(keep) / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(made / name, files(keep) / name)
            shutil.copyfile(turns, keep)
            say(f"{case.id} run {n}/{k}: saved {keep}")


def judge_run(path: Path, case: Case, by_id: Mapping[str, Prompt]) -> dict[str, Any]:
    """One saved room against its case: the i-th typed turn answers the i-th line."""
    if not path.exists():
        return {"passed": False, "why": ["not run"]}
    turns = typed(drawn(read(path), seed_of(path), files(path)))
    why: list[str] = []
    flags: list[str] = []
    for i, pid in case.targets:
        if i >= len(turns) or turns[i].get("said") != case.lines[i]:
            why.append(f"line {i + 1} ({pid}): no turn answered it")
            continue
        for name, rs in judge(turns[i], by_id[pid]).items():
            (flags if name in SOFT else why).extend(f"line {i + 1} ({pid}) {name}: {r}"
                                                    for r in rs)
    return {"passed": not why, "why": why, "flags": flags}


def score(cases: Sequence[Case], out: Path, by_id: Mapping[str, Prompt],
          k: int = K) -> dict[str, Any]:
    """pass^k per case and, per prompt, the share of its wording cases that passed all k; read
    from the saved turn files only. Each case keeps every run's verdict (`runs`), so a k>1 run
    shows which run failed (r4)."""
    per_case = {}
    for case in cases:
        runs = []
        for n in range(1, k + 1):
            r = judge_run(saved(out, case, n), case, by_id)
            runs.append({"run": n, "passed": r["passed"], "why": r["why"],
                         "flags": r.get("flags", [])})
        per_case[case.id] = {"passes": sum(r["passed"] for r in runs), "of": k,
                             "pass_k": all(r["passed"] for r in runs), "held_back": case.held_back,
                             "why": [w for r in runs for w in r["why"]],
                             "flags": [f for r in runs for f in r["flags"]], "runs": runs}
    per_prompt: dict[str, dict[str, int]] = {}
    for case in cases:
        for pid in {p for _, p in case.targets}:
            tally = per_prompt.setdefault(pid, {"cases": 0, "pass_k": 0})
            tally["cases"] += 1
            tally["pass_k"] += per_case[case.id]["pass_k"]
    return {"k": k, "cases": per_case, "prompts": per_prompt}


def browser_sender(rooms: Path, port: int = 8493) -> Sender:  # pragma: no cover - a model walk
    """Type the lines into a fresh check room on the phone app, through a check proxy on `port`
    (never 8474), the way run 7's walk did (`move_walk.Walk`); waits for each turn. t458, walk
    v7's way (`walk_live_full.py`'s V7_UPSTREAM and V7_ROOMS): the proxy fronts `move_walk.UPSTREAM`
    as it is when a room is sent, which a candidate run points at its app, and each room is minted
    in `rooms` (new_room.py reads NEMO_ROOMS)."""
    import subprocess

    import move_walk as mw
    from playwright.sync_api import sync_playwright

    def send(code: str, lines: Sequence[str]) -> Path:
        here = Path(__file__).resolve().parent
        made = subprocess.run([str(mw.APP_PYTHON), str(here / "new_room.py"), code],
                              capture_output=True, text=True, timeout=120,
                              env={**os.environ, "NEMO_ROOMS": str(rooms)})
        if made.returncode or "already there" in made.stdout:
            raise RuntimeError(f"{code}: not a fresh room: {made.stdout}{made.stderr}")
        proxy = subprocess.Popen([str(mw.APP_PYTHON), str(mw.PROXY), mw.UPSTREAM, f"/r/{code}",
                                  "127.0.0.1", str(port)])
        turns = rooms / f"{code}-{mw.MODEL}" / ".turns/turns.jsonl"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                base = f"http://127.0.0.1:{port}"
                walk = mw.Walk(browser, f"{base}/", f"{base}/w/{code}/", turns, rooms / code)
                page = browser.new_context(**mw.PHONE).new_page()
                before = walk.turned()
                page.goto(walk.chat)
                walk.wait_turn(page, before)
                for line in lines:
                    walk.type(page, line)
                browser.close()
        finally:
            proxy.terminate()
            try:
                proxy.wait(timeout=PROXY_WAIT)
            except subprocess.TimeoutExpired:  # 509: a proxy that ignores SIGTERM
                proxy.kill()
                proxy.wait()
        return turns

    return send


# ---- the command line ----------------------------------------------------------------------

def _verdicts(paths: Sequence[str], by_id: Mapping[str, Prompt]) -> int:
    for path in paths:
        task = ""
        room = Path(path).parent.parent if Path(path).parent.name == ".turns" else None
        for turn in typed(drawn(read(Path(path)), seed_of(Path(path)), room)):
            pid = which(str(turn.get("said", "")), by_id, task)
            if pid is None:
                print(f"{Path(path).name}: {turn.get('said', '')[:60]!r}: no sheet prompt")
                continue
            task = pid[0]
            verdict = judge(turn, by_id[pid])
            reasons = "; ".join(f"{n}: {r}" for n, rs in verdict.items() for r in rs)
            print(f"{Path(path).name} {pid}: {'PASS' if passed(verdict) else 'FAIL'}"
                  f"{' - ' + reasons if reasons else ''}")
            # a soft check's reasons are printed too: they flag the turn and never fail it
    return 0


def _practice_only(text: str) -> None:
    """456: say so where the file given holds no held-back case's words."""
    if hidden := redacted(text):
        print(f"practice cases only: {len(hidden)} held-back cases are kept outside the tree and "
              "not run here; give the full variants file", file=sys.stderr)


def _check_briefs(full: Path, dirs: Sequence[str]) -> int:
    """456: each file under `dirs` holding a held-back case's words, by file and case id."""
    found = leaks(full.read_text(encoding="utf-8"),
                  (f for d in dirs for f in sorted(Path(d).rglob("*")) if f.is_file()))
    for path, cid in found:
        print(f"{path}: holds held-back case {cid}")
    return 1 if found else 0


def _read(path: str, by_id: Mapping[str, Prompt]) -> list[Case]:
    """The cases of the variants file at `path`, saying so where it holds the practice ones only."""
    text = Path(path).read_text(encoding="utf-8")
    _practice_only(text)
    return variants(text, by_id)


def _run(argv: list[str], by_id: Mapping[str, Prompt]) -> int:  # pragma: no cover - a model walk
    """`run <variants.md> <room> <out> [--open]`: 455's `--open` opens the marked cases."""
    cases = _read(argv[0], by_id)
    if argv[3:] == ["--open"]:
        cases = opened(cases, (DATA / "variants.md").read_text(encoding="utf-8"))
    run(cases, argv[1], browser_sender(Path.home() / "work/nemo/skin/run/rooms"), Path(argv[2]))
    return 0


def _agent(argv: list[str]) -> int:
    """498: the agent cases' commands, on the tree's copy of the expected answers."""
    by_id = agent_by_id()
    cases = agent_cases(AGENT_CASES.read_text(encoding="utf-8"), by_id)
    if argv == ["agent-plan"]:
        print(f"{len(cases)} agent cases, practice all: {', '.join(c.id for c in cases)}; "
              f"{sum(len(c.lines) for c in cases) * AGENT_K} lines to type at k={AGENT_K}")
        return 0
    if len(argv) == 2 and argv[0] in ("agent-score", "agent-report"):
        scored = score(cases, Path(argv[1]), by_id, AGENT_K)
        print(json.dumps(scored, indent=1) if argv[0] == "agent-score" else agent_report(scored))
        return 0
    if len(argv) == 3 and argv[0] == "agent-run":  # pragma: no cover - a model walk
        run(cases, argv[1], browser_sender(Path.home() / "work/nemo/skin/run/rooms"),
            Path(argv[2]), AGENT_K)
        return 0
    print(__doc__)
    return 2


def main(argv: list[str]) -> int:
    if argv and argv[0].startswith("agent-"):
        return _agent(argv)
    if len(argv) >= 3 and argv[0] == "check-briefs":
        return _check_briefs(Path(argv[1]), argv[2:])
    if len(argv) == 3 and argv[0] == "redact":
        Path(argv[2]).write_text(redact(Path(argv[1]).read_text(encoding="utf-8")),
                                 encoding="utf-8")
        return 0
    return _command(argv, prompts())


def _command(argv: list[str], by_id: Mapping[str, Prompt]) -> int:
    if len(argv) >= 2 and argv[0] == "verdicts":
        return _verdicts(argv[1:], by_id)
    if len(argv) == 2 and argv[0] == "mark":
        path = Path(argv[1])
        path.write_text(mark(path.read_text(encoding="utf-8")), encoding="utf-8")
        argv = ["plan", argv[1]]
    if len(argv) == 2 and argv[0] == "plan":
        cases = _read(argv[1], by_id)
        wordings = [c for c in cases if c.kind == "wording"]
        print(f"{len(cases)} cases: {len(wordings)} wordings over "
              f"{len({c.targets[0][1] for c in wordings})} prompts, "
              f"{len(cases) - len(wordings)} sequences; {sum(c.held_back for c in cases)} held "
              f"back; {sum(len(c.lines) for c in cases) * K} lines to type at k={K}")
        return 0
    if len(argv) == 3 and argv[0] == "score":
        print(json.dumps(score(_read(argv[1], by_id), Path(argv[2]), by_id), indent=1))
        return 0
    if len(argv) in (4, 5) and argv[0] == "run" and argv[4:] in ([], ["--open"]):
        return _run(argv[1:], by_id)  # pragma: no cover - a model walk
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
