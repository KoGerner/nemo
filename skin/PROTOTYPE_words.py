"""PROTOTYPE, throwaway (14_nemo / t64). The words a manager new to BCM and to AI reads.

The language is fixed where the words come from (ticket 64, M5), never checked where the model
composes it (M13):

- **Names beside every id** (`Names.served`). Every tool result the model reads carries the human
  name wherever it carries an id: an impact category by the `name` in the room's `method.json`, a
  decision item by what it is ("Slaughter — how soon it must be back at its agreed minimum level
  (RTO)"), a conflict by its subject, a stage by nemo's own heading (`walk.HEADING_n`), a person by
  the role the room's organisation file gives. The id stays in the result for the next call, under
  its own field; the name sits beside it under `<field>_name`. Prose nemo serves has its ids
  replaced by their names. Interviewees' quotes, file paths and file contents are never touched.
- **Plain findings** (`plain_finding`): the referee's shared-quote finding ends in a developer's
  JSON; the stage-4 card, the handover and the certificate say it in words, from the method's names.
  nemo's own since t133 (`nemo.handover`, ADR-0030 decision 5), with the quote-aware category
  naming it needs; the names stay here for the skin's callers.

Names come from the room's files (`method.json`, `01_Organisation/org-and-roles.md`, the draft),
never from a hand-kept table. The only words kept here are nemo's own: the five stage names and
what each of the three clocks measures.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from nemo import handover, terms, walk

#: the room's organisation file: who holds which role (a markdown table, parsed structurally)
ORGANISATION = "01_Organisation/org-and-roles.md"

#: fix 1: a stage has one name, nemo's own card heading ("Stage 3 of 5 · Standardise", t432: its
#: short name), never a second one kept here
STAGES = {
    1: walk.HEADING,
    2: walk.HEADING_2,
    3: walk.HEADING_3,
    4: walk.HEADING_4,
    5: walk.HEADING_5,
}
#: what each clock measures, the plain name first and the acronym after (ticket 64, layer 3).
#: t64b, the owner's review: an RTO is back "at an agreed minimum level of operation", not merely
#: running; an RPO is about the information the activity uses, whether or not it holds data itself
FIGURE_WORDS = {"mtpd": "how long it can be down before that becomes intolerable (MTPD)",
                "rto": "how soon it must be back at its agreed minimum level (RTO)",
                "rpo": "how far back the information it uses may be restored (RPO)"}

#: the terms nemo itself names (MTPD, RTO, …): a company method file's own definition of one is
#: left to nemo (`method_terms`)
TERMS = ["BIA", "activity", "impact", "MTPD", "RTO", "RPO", "recovery gap", "dependency",
         "register", "handover", "signing on behalf of an owner"]

#: t64: when his typed value on a "Change …" tap opens a flag (an item nemo carries open into the
#: signature, owner's ruling 2026-09-18), nemo asks for his reason, once; his next typed line is
#: it, word for word, and this tap leaves none (the record then says "no reason given"). The tap
#: says "continue", so the scripted manager's "go ahead" rule meets it and never types a reason.
ASK_REASON = (
    "Recorded: {value}, as you typed it. Why? Type your reason in one line and it goes on "
    "the record beside the figure, word for word."
)
NO_REASON_TAP = "Skip, continue without a reason"

#: every string under these keys is served as it is: an interviewee's words, a file, a path.
#: t106: `file` and `listed_in` carry a room file's own name (12_nemo_check: a file name stays
#: whole)
VERBATIM = {"quote", "path", "files", "file", "listed_in", "text", "next", "kept", "filed", "drop"}


def stage_name(stage: int) -> str:
    return STAGES.get(stage, f"Stage {stage} of 5")


def step_line(stage: int) -> str:
    """t96 (ADR-0023 decision 6, his exception): the footer is only the stage marker while a walk is
    under way, nemo's own heading for the stage."""
    return f"*{stage_name(stage)}*"


# ── names from the room's files ──────────────────────────────────────────────────────────────────
_ITEM = re.compile(r"^(A\d+)(?:\.([\w-]+))?$")
#: t96: an activity's own id in prose ("Packing's A1"), said by its name like its items are
_BARE_ITEM = re.compile(r"(?<![\w.-])(A\d+)(?![\w.-])")
_ITEM_IN_TEXT = re.compile(r"(?<![\w-])(A\d+(?:\.[a-z][\w-]*|-MTPD-RULE))(?![\w-])")
#: t183: a conflict of the draft in prose ("see conflict C2", "(conflict C1)"), with the word
#: "conflict" before it, which its name ("the conflict about …") already says
_CONFLICT_IN_TEXT = re.compile(r"(?<![\w-])(?:[Cc]onflict\s+)?(C\d+|A\d+-MTPD-RULE)(?![\w-])")
#: t183: an open item of the documents (`handover.ITEM_ID`): said beside its name to the model
_OPEN_ITEM = re.compile(r"(?<![\w(-])" + handover.ITEM_ID.format(number=r"(\d+)") + r"(?![\w-])")
#: t183: where a draft's prose is not his to read renamed: ids, quotes, paths, nemo's own logs
_NOT_PROSE = {"id", "item_id", "about", "verify_log", "meta", "interviews", *VERBATIM}


#: t155: the headers that name a person's role in the organisation file's tables; the table's own
#: header decides which one it uses (the older file says "Role", the newer "Position")
ROLE_HEADERS = ("role", "position")


def roles(folder: Path) -> dict[str, str]:
    """name -> role, from every table in the organisation file whose header names a Role (or a
    Position) and a Name column; a Deputy column gives "deputy to the <role>". The first table
    naming a person wins, and a role a person holds wins over one they deputise."""
    p = Path(folder) / ORGANISATION
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    deputies: dict[str, str] = {}
    head: list[str] | None = None
    for line in p.read_text(errors="replace").splitlines():
        if not line.strip().startswith("|"):
            head = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        said_by = next((h for h in ROLE_HEADERS if h in head), None)
        if said_by is None or "name" not in head:
            continue
        row = dict(zip(head, cells, strict=False))
        role = _clean(row.get(said_by, ""))
        for key, said, into in (("name", role, out), ("deputy", f"deputy to the {role}", deputies)):
            person = _clean(row.get(key, ""))
            if person and person not in ("—", "-") and "vacant" not in person.lower():
                into.setdefault(_person(person), said)
    return {**deputies, **out}  # a person's own role before the one they deputise


def functions(folder: Path) -> list[str]:
    """t397: every function the organisation file names, each once: the Role (or Position) cell
    of every row of its tables, its bracket dropped ("Plant Manager (process owner)" is the Plant
    Manager), held or vacant."""
    p = Path(folder) / ORGANISATION
    out: list[str] = []
    head: list[str] | None = None
    for line in p.read_text(errors="replace").splitlines() if p.is_file() else []:
        if not line.strip().startswith("|"):
            head = None
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif (said_by := next((h for h in ROLE_HEADERS if h in head), None)) \
                and not set("".join(cells)) <= set("-: "):
            role = dict(zip(head, cells, strict=False)).get(said_by, "")
            out.append(re.split(r"\s*\(", role)[0].strip())
    return [r for r in dict.fromkeys(out) if r]


def deputies(folder: Path) -> dict[tuple[str, str], str]:
    """t282: (person as `roles` keys them, prior record number) -> the deputy the organisation
    file's Deputy column names, "" where no deputy is named ("—"), for each row whose Records cell
    holds that record. A row is matched by its Name, never its position; a table with no Deputy
    or Records column says nothing."""
    p = Path(folder) / ORGANISATION
    out: dict[tuple[str, str], str] = {}
    head: list[str] | None = None
    for line in p.read_text(errors="replace").splitlines() if p.is_file() else []:
        if not line.strip().startswith("|"):
            head = None
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif not set("".join(cells)) <= set("-: ") and {"name", "deputy", "records"} <= set(head):
            row = dict(zip(head, cells, strict=False))
            deputy = "" if row["deputy"] in ("—", "-", "") else row["deputy"]
            for record in re.findall(r"\d+\.\d+", row["records"]):
                out.setdefault((_person(row["name"]), record), deputy)
    return out


#: t467: the BIA programme plan, one row per BIA record (its Record, Process and Process owner)
PLAN = "01_Organisation/bia-programme-plan.md"


def _table_rows(path: Path) -> Iterable[dict[str, str]]:
    """Each body row of every markdown table in a file, by its table's lowercased headers."""
    head: list[str] | None = None
    for line in path.read_text(errors="replace").splitlines() if path.is_file() else []:
        if not line.strip().startswith("|"):
            head = None
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif not set("".join(cells)) <= set("-: "):
            yield dict(zip(head, cells, strict=False))


def leads(folder: Path) -> dict[str, list[tuple[str, bool, str | None]]]:
    """t467: each BIA's process, as the plan names it, with the functions its People box names:
    the process owner first (the plan's Process owner, by the function the organisation file gives
    them), then each function whose row's Records cell holds that record, in the file's order;
    each with whether it is the owner and its deputy's function, None where the Deputy cell names
    none ("—"). Functions only, never names (ADR-0051)."""
    held = people(folder)
    org = [r for r in _table_rows(Path(folder) / ORGANISATION)
           if "records" in r and "position" in r]

    def fn(row: dict[str, str]) -> str:
        return re.split(r"\s*\(", row["position"])[0].strip()

    def deputy(row: dict[str, str]) -> str | None:
        who = re.sub(r"^(Dr|Prof)\.?\s+", "", row.get("deputy", "")).strip()
        return None if who in ("—", "-", "") else held.get(who, f"Deputy {fn(row)}")
    out: dict[str, list[tuple[str, bool, str | None]]] = {}
    for p in _table_rows(Path(folder) / PLAN):
        record, owner = p.get("record", ""), p.get("process owner", "")
        if not re.fullmatch(r"\d+\.\d+", record) or not p.get("process"):
            continue
        mine = [r for r in org if record in re.findall(r"\d+\.\d+", r["records"])]
        first = held.get(re.sub(r"^(Dr|Prof)\.?\s+", "", owner).strip(), owner)
        rows = {fn(r): r for r in reversed(mine)}
        fns = list(dict.fromkeys([first, *(fn(r) for r in mine)]))
        out[p["process"]] = [(f, f == first, deputy(rows[f]) if f in rows else None) for f in fns]
    return out


def _clean(cell: str) -> str:
    return re.sub(r"[¹²³⁴]", "", cell.replace("**", "")).strip()


def _person(name: str) -> str:
    return " ".join(re.sub(r"^(Dr|Prof)\.?\s+", "", name.strip()).lower().split())


# ── t418 (ADR-0051): functions, never names, unless his line asks for names ─────────────────────
#: his typed line asks for names: only then does a person's name show, beside the function. The
#: noun only (t470 r2): "name the function" asks for a function, not a name
NAMES_ASKED = re.compile(r"\b(?:names|(?:whose|their|his|her|the|by) names?|name of)\b", re.I)
#: a person's title before the name, dropped with it
_TITLE = r"(?:(?:Dr|Prof|Mr|Ms|Mrs|Herr|Frau)\.? )?"
#: a fenced block (`nemo.verbatim.fence`): someone's words, kept as they are
_FENCED = re.compile(r"^(`{3,})\n.*?\n\1$", re.M | re.S)
#: t448 r2: words after an appositive whose comma stays: a list, a second appositive, a clause
_KEEPS_COMMA = ("(?:and|or|but|nor|the|a|an|his|her|their|its|our|your|who|whom|whose|which"
                "|that|then|so|yet)")
#: t714: the words before a function that make it another one: "Deputy <function>", "assistant to
#: the <function>"; any capitalised word but "The", so a doubt keeps the name
_TITLED = re.compile(r"(?:(?<![\w-])(?!The\b)[A-Z][\w-]*"
                     r"|\b(?i:deputy|acting|interim|assistant|vice|former)(?: to| of)?(?: the)?)"
                     r"[\s*_]*\Z")
#: where a word opens a sentence or a line ("- ", "1. ", "**" before it), so "the" is "The"
_OPENS = re.compile(r"(?:\A|[.!?]\s+|\n)[\s>*_#\d.)-]*\Z")
#: t762: an address. A markdown link's target, whole with no space, that reads as one: `[x](Name)`
#: and `[x](Mr. Name)` do not. Or a bare URL or room path, which ends before a quote mark, a table's
#: bar, a closing bracket or a sentence's stop. A comma inside it stays: a fragment's range has one.
_ADDRESS = re.compile(r"(?<=\]\()(?=[^\s)]*[/#?.]|[a-z+.-]+:)(?:[^\s()]|\([^\s()]*\))+(?=\))"
                      r"|(?<![\w/.-])(?:(?i:[a-z][a-z+.-]*://|www\.|mailto:)|(?:/chat)?/w/)"
                      r"(?:[^\s()<>\[\]|\"“”]|\([^\s()]*\))+(?<![.,;:!?])")


def people(folder: Path) -> dict[str, str]:
    """t418: every person the organisation file names, as written there (a leading "Dr" or "Prof"
    dropped), with their function: the Role, Position or Function cell of the row naming them, its
    bracket dropped ("Plant Manager (process owner)" is the Plant Manager). A function a person
    holds wins over one they deputise; a deputy and nothing else is "Deputy <function>"."""
    p = Path(folder) / ORGANISATION
    held: dict[str, str] = {}
    deputising: dict[str, str] = {}
    head: list[str] | None = None
    for line in p.read_text(errors="replace").splitlines() if p.is_file() else []:
        if not line.strip().startswith("|"):
            head = None
            continue
        cells = [_clean(c) for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
            continue
        said_by = next((h for h in (*ROLE_HEADERS, "function") if h in head), None)
        if said_by is None or "name" not in head or set("".join(cells)) <= set("-: "):
            continue
        row = dict(zip(head, cells, strict=False))
        role = re.split(r"\s*\(", row.get(said_by, ""))[0].strip()
        for key, said, into in (("name", role, held), ("deputy", f"Deputy {role}", deputising)):
            person = re.sub(r"^(Dr|Prof)\.?\s+", "", row.get(key, "")).strip()
            if role and person and person not in ("—", "-") and "vacant" not in person.lower():
                into.setdefault(person, said)
    return {**deputising, **held}


def surnames(held: dict[str, str]) -> dict[str, str]:
    """t418: each surname of `people` that no one else there shares, with its holder's function."""
    last = [name.split()[-1] for name in held]
    return {name.split()[-1]: role for name, role in held.items()
            if last.count(name.split()[-1]) == 1}


@functools.lru_cache(maxsize=8)
def _person_patterns(full: tuple[str, ...], last: tuple[str, ...]) -> tuple[str, re.Pattern[str]]:
    """t418: a person, by whole name or surname, as a pattern; and a quick test for any of them."""
    names = "|".join(re.escape(n) for n in sorted(full, key=len, reverse=True))
    bare = "|".join(re.escape(n) for n in sorted(last, key=len, reverse=True))
    person = rf"{_TITLE}(?:(?P<full>{names})" + (rf"|(?P<last>{bare})" if bare else "") + ")"
    return person, re.compile("|".join(filter(None, [names, bare])))


def functions_only(text: str, folder: Path, tap: bool = False,
                   held: dict[str, str] | None = None) -> str:
    """t418 (ADR-0051): what nemo shows with every person the organisation file names said by
    their function: "Head of IT Operations (Marek Sobotta)" is the Head of IT Operations, "Marek
    Sobotta (Head of IT Operations)", "Marek Sobotta, Head of IT Operations" (t448) and "Marek
    Sobotta" the Head of IT Operations, "Mr Sobotta" and "Sobotta's" too; "Head of IT Operations
    (Marek Sobotta, process owner)" is the Head of IT Operations (process owner) (t714). Never
    inside a quote, a `>` quote line or a fenced block: someone's words stay as said. A tap's label
    (`tap`) names people by surname alone ("Ask Sobotta: RTO", "Barsch · 25 Sep") and loses them the
    same way. The seed keeps every name; this is what nemo shows."""
    held = people(folder) if held is None else held
    if not held or not text:
        return text
    last = surnames(held)
    person, anyone = _person_patterns(tuple(held), tuple(last))
    if not anyone.search(text):
        return text
    functions = "|".join(re.escape(f) for f in sorted(set(held.values()), key=len, reverse=True))

    def role(m: re.Match[str]) -> str:
        return held[m["full"]] if m["full"] else last[m["last"]]

    def said(m: re.Match[str]) -> str:
        function = role(m)
        before = m.string[:m.start()]
        if not before.strip() and not m.string[m.end():].strip():
            return function  # a value that is the person alone: an owner cell, a To line
        if tap and not re.search(r"[^\W\d_]\s*\Z", before) or before.endswith(" · ") \
                or m.string.startswith(" · ", m.end()):  # a label's head, a list, "<who> · <what>"
            return function
        the = "The" if _OPENS.search(before) else "the"
        return f"{the} {function}" if not re.search(r"\bthe\s*\Z", before, re.I) else function

    def once(m: re.Match[str]) -> str:
        """t714: "<function> (<name>, <beside>)": the name goes, what stands beside it stays. Under
        another function (`_TITLED`) it stays, for `said` to name by function."""
        before = m.string[:m.start()]

        def own(part: str) -> bool:
            who = re.fullmatch(person, part)
            at = who and re.search(rf"(?i)(?<![\w-]){re.escape(role(who))}[*_]*\Z", before)
            return bool(at and not _TITLED.search(before[:at.start()]))
        parts = m["inside"].split(", ")
        beside = [p for p in parts if not own(p)]
        if len(beside) == len(parts):
            return m[0]
        return f" ({', '.join(beside)})" if beside else ""

    def changed(part: str) -> str:
        # "<function> (<name>)": the function stands alone
        part = re.sub(rf" ?\({person}\)", "", part)
        part = re.sub(r" ?\((?P<inside>[^()\n]+, [^()\n]+)\)", once, part)
        # "<function>, <name>": the function stands alone
        part = re.sub(rf",? (?<![\w-]){person}(?![\w-])", lambda m: "" if m.string[:m.start()]
                      .lower().endswith(role(m).lower()) else m[0], part)
        # "<name> (<its function>)": the function, said once
        part = re.sub(rf"(?<![\w-]){person} \((?:the )?(?P<said>[^()\n]*)\)",
                      lambda m: said(m) if m["said"].lower().startswith(role(m).lower())
                      else f"{said(m)} ({m['said']})", part)
        # t448: "<name>, <its function>": the function, said once; another function stays beside.
        # r2: an appositive's closing comma goes with the name ("the <function> owns it"); one
        # before a list's "and", a second appositive or a relative clause stays
        part = re.sub(rf"(?<![\w-]){person}, (?:the )?(?P<said>(?i:{functions}))(?![\w-])"
                      rf"(?:,(?= (?!{_KEEPS_COMMA}\b)[a-z]))?",
                      lambda m: said(m) if m["said"].lower() == role(m).lower() else m[0], part)
        part = re.sub(rf"(?<![\w-]){person}(?P<s>'s)?(?![\w-])", lambda m: said(m) + (
            ("'" if role(m).endswith("s") else "'s") if m["s"] else ""), part)
        return part

    def line_said(line: str) -> str:
        """t762: an address is held out as a mark, so a name's "the <function>" never lands in it
        and what stands before a name still reads as text; the mark goes back as it went in."""
        kept: list[str] = []

        def mark(m: re.Match[str]) -> str:
            kept.append(m[0])
            return f"\0{len(kept) - 1}\0"
        out = handover.outside_quotes(_ADDRESS.sub(mark, line), changed)
        for n, address in enumerate(kept):
            out = out.replace(f"\0{n}\0", address)
        return out

    def lines(part: str) -> str:
        return "\n".join(line if line.lstrip().startswith(">") else line_said(line)
                         for line in part.split("\n"))

    out, at = [], 0
    for fenced in _FENCED.finditer(text):  # a transcript in its fence: his words, as he said them
        out += [lines(text[at:fenced.start()]), fenced[0]]
        at = fenced.end()
    return "".join([*out, lines(text[at:])])


def functions_only_in(value: Any, folder: Path) -> Any:
    """t418: `functions_only` over every string a page's data holds, its keys as they are."""
    held = people(folder)

    def only(x: Any) -> Any:
        if isinstance(x, dict):
            return {k: only(v) for k, v in x.items()}
        if isinstance(x, list):
            return [only(v) for v in x]
        return functions_only(x, folder, held=held) if isinstance(x, str) else x
    return only(value)


# ── t96: the codes the room's files use, each with the name the files give it ───────────────────
#: A code is an id a file uses for a thing: a system or asset (IT-ERP-01), a risk (R-OPS-01), an
#: incident or its review (PIR-2025-004), an earlier BIA (BIA-2025-02), a document (RA-OPS-2026).
CODE = re.compile(r"(?<![\w/.-])([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z0-9]*)(?![\w-])")
#: a room folder (08_Prior-Cycle), and a path inside the room (08_Prior-Cycle/25_04_15_prior-bia.md)
FOLDER = re.compile(r"(?<![\w/.-])(\d\d_[A-Z][\w-]*)(?![\w-])")
PATH = re.compile(
    r"(?<![\w/.-])((?:\d\d_[A-Z][\w-]*|output)(?:/[\w.-]+)+\.(?:md|json|jsonl))(?![\w-])"
)
#: the words a table header uses for the column that names what a row's code stands for
_TITLE_COLUMN = re.compile(r"title|name|designation|description|risk|subject|finding", re.I)
_HEADING = re.compile(r"^#+\s+(.+?)\s*$", re.M)


def _short(name: str) -> str:
    """A name as it is said: bold and notes dropped, cut at its first bracket or comma."""
    name = re.sub(r"\*\(.*?\)\*|[*_`]", "", str(name)).strip()
    return re.split(r"\s+\(|,\s|;\s|:\s", name, maxsplit=1)[0].strip(" .—-:")


def _title(path: Path) -> str:
    """A room file's own name: its first markdown heading, else its file name in words."""
    if path.suffix == ".md":
        m = _HEADING.search(path.read_text(errors="replace"))
        if m:
            return _short(m.group(1).split(" — ")[0]) if " — " in m.group(1) else _short(m.group(1))
    return re.sub(r"^[\d_]+", "", path.stem).replace("-", " ").replace("_", " ").strip()


def room_codes(folder: Path) -> dict[str, str]:
    """code -> its name, from the room's own files (t96). A heading "CODE — title" names it; so
    does a table row led by the code, by the column its header calls a title, name, designation,
    description or risk; a JSON entry keyed by it, by its "name"; a document's reference number,
    by the document's title. Nothing is kept here by hand, and a code no file names stays
    unnamed."""
    out: dict[str, str] = {}
    #: weaker names, used only for a code no title names: a code alone in a table's other column,
    #: and the words the files put directly before a code ("discharge permit UW-2022-14")
    later: dict[str, str] = {}
    before: dict[str, dict[str, int]] = {}
    for p in _room_inputs(Path(folder)):
        if p.suffix == ".json":
            try:
                data = json.loads(p.read_text())
            except ValueError:
                continue
            if isinstance(data, dict):
                for k, v in data.items():
                    if CODE.fullmatch(k) and isinstance(v, dict) and v.get("name"):
                        out.setdefault(k, _short(v["name"]))
            continue
        if p.suffix != ".md":
            continue
        text = p.read_text(errors="replace")
        for m in re.finditer(
            r"^#+\s+.*?\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z0-9]*)\s+[—-]\s+(.+?)\s*$",
            text,
            re.M,
        ):
            out.setdefault(m.group(1), _short(m.group(2)))
        head: list[str] | None = None
        for line in text.splitlines():
            if not line.strip().startswith("|"):
                head = None
                continue
            cells = [_clean(c).strip("* ") for c in line.strip().strip("|").split("|")]
            if head is None:
                head = cells
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            if not cells:
                continue
            if CODE.fullmatch(cells[0]):
                # the column its header calls a title, else the one beside the code
                col = next((i for i, h in enumerate(head) if i and _TITLE_COLUMN.search(h)), 1)
                if col is not None and col < len(cells) and re.search(r"[A-Za-z]{3}", cells[col]):
                    out.setdefault(cells[0], _short(cells[col]))
                continue
            # a code standing alone in another column: that column's thing, for the row's first cell
            for i, cell in enumerate(cells[1:len(head)], 1):
                if CODE.fullmatch(cell) and re.search(r"[A-Za-z]{3}", cells[0]) and head[i]:
                    later.setdefault(cell, f"the {head[i].lower()} for {_short(cells[0])}")
        for m in re.finditer(
            r"\b([a-z][a-z]+(?: [a-z][a-z]+)?) \**([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z0-9]*)\b",
            text,
        ):
            words_ = m.group(1).split()
            while words_ and words_[0] in _LEAD:
                words_.pop(0)
            if words_ and words_[-1] not in _LEAD:
                seen = before.setdefault(m.group(2), {})
                seen[" ".join(words_)] = seen.get(" ".join(words_), 0) + 1
        # a document's own reference number, in the block before its first section
        top = text.split("\n## ", 1)[0]
        for m in re.finditer(
            r"(?:Reference (?:number|no\.?)|Document No\.?)\**:?\**\s*\|?\s*\**:?\**\s*"
            r"([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z0-9]*)",
            top,
        ):
            out.setdefault(m.group(1), _title(p))
    for code, name in later.items():
        out.setdefault(code, name)
    for code, seen in before.items():
        out.setdefault(code, "the " + max(seen, key=lambda w: (seen[w], w)))
    # t96 fix 1 (M5): a "name" that is itself a code, a folder or a path, or that stands for a file
    # ("the ref code for haccp-plan.md"), is no name: dropped, so the code is served bare
    return {code: name for code, name in out.items() if not _no_name(name)}


_FILE = re.compile(r"[\w-]+\.(?:md|json|jsonl)\b")


def _no_name(name: str) -> bool:
    return bool(
        CODE.fullmatch(name) or FOLDER.fullmatch(name) or PATH.fullmatch(name) or _FILE.search(name)
    )


#: words that lead into a noun and name nothing themselves
_LEAD = {"the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "from", "with", "by", "at",
         "under", "against", "see", "per", "as", "is", "are", "was", "its", "their", "his", "her",
         "our", "this", "that", "no", "not", "incl", "via", "into", "after"}


def _room_inputs(folder: Path) -> list[Path]:
    """The files `room_codes` reads: the room's inputs, never output/, public/ or a dot-path."""
    return sorted(p for p in folder.rglob("*") if p.is_file()
                  and not p.relative_to(folder).as_posix().startswith(("output/", "public/"))
                  and "/." not in "/" + p.relative_to(folder).as_posix())


def _stamp(files: list[Path]) -> tuple[tuple[str, int], ...]:
    """t284: a cache key for what `files` hold, by their names and mtimes."""
    return tuple((p.as_posix(), p.stat().st_mtime_ns) for p in files)


def _room_codes(folder: str) -> dict[str, str]:
    """`room_codes`, read again only when the room's inputs change (t284: an upload or a new
    transcript is named on the next turn, without a restart; an unchanged room is not re-read)."""
    return _codes_read(folder, _stamp(_room_inputs(Path(folder))))


@functools.lru_cache(maxsize=64)
def _codes_read(folder: str, stamp: tuple[tuple[str, int], ...]) -> dict[str, str]:
    return room_codes(Path(folder))


#: a term the company's method file defines, as a bullet: "- **MIN principle:** …" or "- **MTPD** =
#: …"
_DEFINED = re.compile(
    r"^\s*[-*]\s+\*\*(?P<term>[^*]+?)(?::\*\*|\*\*\s*(?::|=))\s*(?P<meaning>.+?)\s*$", re.M
)


def method_terms(folder: str) -> dict[str, str]:
    """t96 fix 1 (M6): term -> its meaning, as the company's own method files word it (the .md files
    beside the room's method.json; on the seed, impact-criteria.md §7). Terms nemo's glossary
    already carries (`TERMS`: MTPD, RTO, …) are left to it. A term no file defines gets nothing:
    nothing here is written by hand. t284: read again only when those files change."""
    return _terms_read(_stamp(sorted((Path(folder) / walk.METHOD).parent.glob("*.md"))))


@functools.lru_cache(maxsize=64)
def _terms_read(stamp: tuple[tuple[str, int], ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path, _ in stamp:
        for m in _DEFINED.finditer(Path(path).read_text(errors="replace")):
            if m.group("term").strip() not in TERMS:
                out.setdefault(m.group("term").strip(), m.group("meaning"))
    return out


def terms_in(s: str, terms: dict[str, str]) -> dict[str, str]:
    """The method terms `s` says outside a quote, each with its meaning."""
    said = _QUOTED.sub(" ", s)
    return {
        t: m for t, m in terms.items() if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", said)
    }


def folder_name(code: str) -> str:
    """A room folder in words: 08_Prior-Cycle is "the Prior Cycle folder"."""
    return "the " + re.sub(r"^\d\d_", "", code).replace("-", " ").replace("_", " ") + " folder"


def path_name(folder: Path, path: str) -> str:
    """A room file in words, by its own title."""
    p = Path(folder) / path
    return _title(p) if p.is_file() else Path(path).name


def _beside(name: str, code: str) -> str:
    return f"{name} ({code})"


def named_codes(s: str, folder: Path, codes: dict[str, str]) -> str:
    """Prose with each room code said by its name, the code kept beside it in brackets for the next
    call: "IT-ERP-01" is "ERP system (IT-ERP-01)". A code already named that way is left alone."""
    def one(part: str) -> str:
        def sub(pattern: re.Pattern[str], name_of: Any, text: str) -> str:
            def rep(m: re.Match[str]) -> str:
                code = m.group(1)
                before, after = text[:m.start()], text[m.end():]
                if before.endswith("(") and after.startswith(")"):
                    return code  # already beside its name
                name = name_of(code)
                return _beside(name, code) if name else code
            return pattern.sub(rep, text)
        part = sub(PATH, lambda c: path_name(folder, c), part)
        # a folder or code inside a path is the path's, which is named whole above
        pieces = re.split(r"(\([^()]*/[^()]*\))", part)
        return "".join(x if n % 2 else sub(CODE, codes.get, sub(FOLDER, folder_name, x))
                       for n, x in enumerate(pieces))
    return _outside_quotes(s, one)


def codes_by_name(s: str, folder: Path) -> str:
    """t96 fix 1 (I1, 8_nemo_check's re-ruling): text he reads with each room code REPLACED by the
    name the room's files give it ("(UV-STROM-01)" is "(Grid connection 20 kV + transformer
    station)"). A code no file names (after M5, never a code-as-name) stays bare, to be counted."""
    codes = _room_codes(str(Path(folder)))
    return CODE.sub(lambda m: codes.get(m.group(1)) or m.group(1), s)


_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def file_said(folder: Path, path: str) -> str:
    """t96 fix 2 (the owner's round 1: "nobody is interested where the files are exactly located"):
    a room file on a card by its own title, with the date its file name carries, never its path."""
    m = re.match(r"^(\d\d)_(\d\d)_(\d\d)_", Path(path).name)
    when = f", {int(m.group(3))} {_MONTHS[int(m.group(2)) - 1]} 20{m.group(1)}" \
        if m and 1 <= int(m.group(2)) <= 12 else ""
    return path_name(folder, path) + when


def drawn(s: str, folder: Path) -> str:
    """t96 fix 2 (1a, 8_nemo_check): text the app draws on a card he reads, each code replaced by
    its name (`codes_by_name`) and each room path by the file's plain name (`file_said`), never
    inside a quote: a quote is someone's words from a file and stays byte for byte. The signed
    documents keep their ids and never come through here."""
    return _outside_quotes(str(s), lambda part: codes_by_name(
        PATH.sub(lambda m: file_said(folder, m.group(1)), part), folder))


class Names:
    """The human names of the ids one activity's walk serves, read from the room now."""

    def __init__(self, folder: Path, activity: str | None = None, model: str = "deepseek") -> None:
        import PROTOTYPE_core as core  # the core imports this module; the room's reads live there
        self.folder, self.activity = Path(folder), activity
        method = json.loads((self.folder / walk.METHOD).read_text())
        self.categories = {c["id"]: c["name"] for c in method.get("scenarios") or [] if c.get("id")}
        state = core.load_state(self.folder, activity) if activity else {}
        prepared = (core.draft_for(activity, model, self.folder) if activity else None) or {}
        draft = state.get("draft") or prepared
        self.acts: dict[str, str] = {}
        self.conflicts: dict[str, str] = {}
        for d in (prepared, draft):  # the settled draft's names win (its merged A0)
            self.acts.update({a["id"]: a["name"] for a in d.get("activities") or [] if a.get("id")})
            # t96 fix 2 (1a/1b): a conflict's subject as he reads it on its card, codes by their
            # names
            self.conflicts.update({c["id"]: drawn(str(c.get("about") or c["id"]), self.folder)
                                   for c in d.get("conflicts") or [] if c.get("id")})
        self.single = len(draft.get("activities") or []) <= 1
        self.people = roles(self.folder)
        #: t96: the codes the room's files use, each by the name the files give it
        self.codes = _room_codes(str(self.folder))
        #: t96 fix 1 (M6): the company's method terms, each with its meaning from its own files
        self.terms = method_terms(str(self.folder))

    def _activity_name(self, aid: str) -> str:
        if self.activity and (self.single or aid not in self.acts):
            return self.activity
        return self.acts.get(aid, self.activity or aid)

    def item(self, iid: str) -> str | None:
        """What an id is, in words: a conflict by its subject, a figure by what it measures, a
        category's scores by the method's name, an activity by its name. None: no such id here."""
        if iid in self.conflicts:
            return f"The conflict about {self.conflicts[iid]}"
        if iid in self.categories:
            # why: the method file is JSON, so its names are Any
            return self.categories[iid]  # type: ignore[no-any-return]
        m = _ITEM.match(iid)
        if not m or (m.group(1) not in self.acts and not self.activity):
            return None
        act, key = self._activity_name(m.group(1)), m.group(2)
        if key is None:
            return act if m.group(1) in self.acts else None
        if key in FIGURE_WORDS:
            return f"{act} — {FIGURE_WORDS[key]}"
        if key in self.categories:
            return f"{act} — {self.categories[key]} impact scores"
        return None

    def role(self, speaker: Any) -> str | None:
        """A person's role, by the name before any bracketed note; several people "a / b" each."""
        parts = [p.split("(")[0].strip() for p in str(speaker or "").split("/")]
        found = [self.people.get(_person(p)) for p in parts if p]
        return "; ".join(r for r in found if r) or None

    def ids_said(self, s: str) -> str:
        """t183: prose he reads with each of the draft's conflict and item ids said by its name, the
        id gone: "see conflict C2" is "see the conflict about …". Never inside a quote; an id this
        draft does not hold is not nemo's and stays."""
        def conflict(m: re.Match[str]) -> str:
            about = self.conflicts.get(m.group(1))
            return f"the conflict about {about.rstrip('.')}" if about else m.group(0)
        return _outside_quotes(s, lambda part: _ITEM_IN_TEXT.sub(
            lambda m: self.item(m.group(1)) or m.group(1), _CONFLICT_IN_TEXT.sub(conflict, part)))

    def draft_said(self, x: Any) -> Any:
        """t183: a draft as it enters the walk, its prose (a reason, a gap's what) with its ids said
        by their names (`ids_said`), so no card drawn from it can show one. Every id stays where it
        is an id; quotes, paths and nemo's own logs are left as they are. t477: a sentence of
        nemo's own that 477 reworded is said as it reads now (`PROTOTYPE_draft.RETIRED_WHY`)."""
        import PROTOTYPE_draft as drafting

        if isinstance(x, dict):
            return {k: v if k in _NOT_PROSE else self.draft_said(v) for k, v in x.items()}
        if isinstance(x, list):
            return [self.draft_said(v) for v in x]
        if isinstance(x, str) and x in drafting.RETIRED_WHY:
            return drafting.RETIRED_WHY[x]
        return self.ids_said(x) if isinstance(x, str) and " " in x else x

    def text(self, s: str) -> str:
        """Served prose with each item, conflict and category id said by its name, and an open item
        of the documents beside its name (t183)."""
        said = _outside_quotes(self.ids_said(s), lambda part: _said(_OPEN_ITEM.sub(
            lambda m: f"open item {m.group(1)} ({m.group(0)})", _BARE_ITEM.sub(
                lambda m: self.item(m.group(1)) or m.group(1), part)), self.categories))
        return named_codes(said, self.folder, self.codes)  # t96: every room code beside its name

    def code(self, value: str) -> str | None:
        """t96: the name of a bare code, folder or room path served as a value, else None."""
        if PATH.fullmatch(value):
            return path_name(self.folder, value)
        if FOLDER.fullmatch(value):
            return folder_name(value)
        return self.codes.get(value) if CODE.fullmatch(value) else None

    #: Prose with each of the method's category ids said by its name (nemo's own, t133).
    categories_said = staticmethod(handover.categories_said)

    def served(self, result: Any, key: str | None = None) -> Any:
        """The tool result as the model reads it: every id with its name beside it (t64)."""
        if isinstance(result, dict):
            out: dict[str, Any] = {}
            for k, v in result.items():
                if k in VERBATIM:
                    out[k] = v
                    continue
                if (
                    isinstance(v, str) and v in self.conflicts and k != "item_id"
                ):  # item_id: the call's own
                    # t96 fix 2 (1b): a conflict is its subject; its id only as the call's argument
                    if k == "id":
                        out["item_id"], out["item_id_name"] = v, self.text(self.item(v) or v)
                    else:
                        out[k] = self.text(self.item(v) or v)
                    continue
                named =(self.item(k) or self.code(k)) if isinstance(k, str) else None
                v2 = self.served(v, k)
                if named and isinstance(v2, dict) and not v2.get("name"):
                    v2 = {"name": self.text(named), **v2}
                out[k] = v2
                if isinstance(v, str) and (name := self.item(v) or self.code(v)):
                    out[f"{k}_name"] = self.text(name)
                elif (
                    isinstance(v, list)
                    and v
                    and all(isinstance(x, str) and (self.item(x) or self.code(x)) for x in v)
                ):
                    out[f"{k}_names"] = [self.item(x) or self.code(x) for x in v]
                elif k == "step" and isinstance(v, int):
                    out["step_name"] = stage_name(v)
                if said := {t: m for x in (v if isinstance(v, list) else [v]) if isinstance(x, str)
                            for t, m in terms_in(x, self.terms).items()}:
                    out[f"{k}_terms"] = (
                        said  # t96 fix 1 (M6): the method's word, its meaning beside it
                    )
                if k in ("speaker", "owner", "owner_name") and (r := self.role(v)):
                    out[f"{k}_role"] = r
                elif k == "owner_nemo_expects" and isinstance(v, list):
                    out[f"{k}_roles"] = [self.role(x) or "" for x in v]
            return out
        if isinstance(result, (list, tuple)):
            return [self.served(v, key) for v in result]
        if isinstance(result, str):
            # an id served whole stays as it is, for the next call; its name is beside it
            return result if self.item(result) or self.code(result) else self.text(result)
        if result is None or isinstance(result, (bool, int, float)):
            return result
        return self.text(str(result))  # a referee object: served as the sentence it says


#: fix 1 (I1): a span nemo quotes, “…” or "…", is someone's words (walk's "Word for word:
#: “{quote}”"):
#: never reworded, so "That'll bite us on reputation." stays his. nemo's own since t133.
_QUOTED, _outside_quotes = handover.QUOTED, handover.outside_quotes


def _said(s: str, categories: dict[str, str]) -> str:
    if not categories:
        return s
    ids = "|".join(map(re.escape, sorted(categories, key=len, reverse=True)))
    return _outside_quotes(s, lambda part: re.sub(rf"(?<![\w-])({ids})(?![\w-])",
                                                  lambda m: categories[m.group(1)], part))


def served_names(folder: Path) -> list[str]:
    """t64 fix 1b/1c: the human names nemo serves beside the ids, which the figure check reads as
    whole names: the method's category names, the room's activity names (and each draft's, as
    served), the stage headings and the roles `roles` serves beside people. Never the method's
    rules, bands or thresholds, nor any other number in the organisation file. t296: each asset's
    `name` in the room's own dependency register ("Microsoft 365"), never any other field of it."""
    import PROTOTYPE_core as core
    folder = Path(folder)
    method = json.loads((folder / walk.METHOD).read_text())
    out = [str(c.get("name") or "") for c in method.get("scenarios") or []] + list(STAGES.values())
    for a in walk.processes(folder):
        out.append(a)
        out += [str(x.get("name") or "") for x in
                (core.load_state(folder, a).get("draft") or {}).get("activities") or []]
    out += list(roles(folder).values())
    out += list(_room_codes(str(folder)).values())  # t96: a code's name, served beside it
    out += _register_names(folder)
    return [n for n in out if n]


def item_names(folder: Path) -> list[str]:
    """t377 M, t397: the names a gloss never splits: the register's asset names and every
    function the organisation file names ("Head of IT Operations")."""
    return [*_register_names(folder), *functions(folder)]


def _register_names(folder: Path) -> list[str]:
    """t296: the room's register asset names, none for a blank one (a blank name would blank every
    gap of a reply in `_flag`); none for one that is not JSON (t297), which every turn names."""
    register = folder / walk.REGISTER
    if not register.is_file() or walk.unreadable_register(folder):
        return []
    return [n for e in json.loads(register.read_text()).values() if isinstance(e, dict)
            for n in [str(e.get("name") or "").strip()] if n]


# ── t107: abbreviations and method terms, named on first use ────────────────────────────────────
#: t473 (his ANSWER 2026-10-13T15:41:12Z: "Gloss on first use"): two of the method's impact
#: categories hide what they cover, so nemo names them, by category id. The seed keeps its names.
GLOSS = {"image": "reputation", "legal": "incl. regulatory"}
#: t477 (14_nemo_design 2026-10-18 02:23:24, routed by 41_nemo_check): a room glossary line whose
#: plain words name a maker or a product ("part of the product name of …", "the maker of …",
#: "named after its maker", "the name of the business software …", "software from <maker>"). A
#: product name carries no gloss in an answer: D2's gloss list explains BCM terms, not products.
PRODUCT_NAME = re.compile(r"\bproduct name\b|\bmaker\b|\bthe name of\b|\bsoftware from [A-Z]")
#: t473 r2: a category word in the category's sense carries this mark through `terms`' gloss path,
#: so a table key only it matches names it there; the mark is taken out again before anyone reads it
_SENSE = "\ue473"


def room_terms(folder: Path) -> dict[str, str]:
    """t107: what a first use is named by: the room's own glossary file (room content, never code)
    and nemo's method terms (`nemo.terms`), which win for a method's own word.

    t473: and `GLOSS`, under the room's own name for each category, matched only where
    `in_category_sense` marks it.

    t477: never a product or maker name (`PRODUCT_NAME`): it is said bare in every answer."""
    room = {k: v for k, v in room_glossary(folder).items() if not PRODUCT_NAME.search(v)}
    sensed = {f"{name.lower()}{_SENSE}": GLOSS[cid]
              for cid, name in room_categories(folder).items() if cid in GLOSS}
    return {**room, **terms.METHOD_TERMS, **sensed}


def room_glossary(folder: Path) -> dict[str, str]:
    """The room's own glossary file, every line of it (`terms.glossary`); {} where it has none."""
    p = Path(folder) / terms.GLOSSARY
    return terms.glossary(p.read_text(errors="replace")) if p.is_file() else {}


def room_categories(folder: Path) -> dict[str, str]:
    """t473: the method's impact category names by id, as the room's method.json holds them."""
    p = Path(folder) / walk.METHOD
    try:
        method = json.loads(p.read_text()) if p.is_file() else {}
    except ValueError:
        return {}
    return {c["id"]: c["name"] for c in method.get("scenarios") or []
            if c.get("id") and c.get("name")}


#: t473 r2 (40_nemo_check 2026-10-14 00:13:43): what joins two names in a run of categories
_JOIN = r"(?:\*\*)?\s*(?:,\s*(?:and\s+|or\s+)?|\s(?:and|or)\s+|&\s*|/\s*)(?:\*\*)?"


@functools.lru_cache(maxsize=16)
def _sense(glossed: tuple[str, ...],
           names: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    """The word; what follows or precedes it in the category's sense; a table cell's two sides."""
    def alt(words: tuple[str, ...]) -> str:
        return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    others = rf"(?<!\w)(?:{alt(names)})(?!\w)" if names else r"(?!)"
    return (re.compile(rf"(?<![\w/.+-])(?:{alt(glossed)})(?![\w+-])", re.I),
            re.compile(rf"[ \t]+impacts?\b|(?:\*\*)?[ \t]*:|{_JOIN}{others}", re.I),
            re.compile(rf"{others}{_JOIN}\Z", re.I),
            re.compile(r"\|[ \t]*(?:\*\*)?\Z"), re.compile(r"(?:\*\*)?[ \t]*\|"))


def in_category_sense(text: str, table: dict[str, str], categories: Iterable[str] = ()) -> str:
    """t473 r2 (40_nemo_check's ruling): `text` with each glossed category word marked where it
    names the impact category: "legal impact(s)", a run listing it with another of `categories`
    ("Legal and Image"), a label ("Image: low") or a table cell. Never as an adjective before
    another noun ("a legal question") nor a picture ("an image of the plan"): those stay bare."""
    glossed = tuple(k[:-1] for k in table if k.endswith(_SENSE))
    if not glossed or _SENSE in text:
        return text
    word, after, before, cell_before, cell_after = _sense(glossed, tuple(categories))
    out, at = [], 0
    for m in word.finditer(text):
        ahead = text[max(0, m.start() - 80):m.start()]
        if (after.match(text, m.end()) or before.search(ahead)
                or (cell_before.search(ahead) and cell_after.match(text, m.end()))):
            out += [text[at:m.end()], _SENSE]
            at = m.end()
    return "".join([*out, text[at:]])


def _named(text: str, table: dict[str, str], used: frozenset[str], names: Iterable[str],
           categories: Iterable[str]) -> tuple[str, frozenset[str]]:
    """`terms.name_first_uses` on `text` with its category words marked, the marks taken out."""
    said, used = terms.name_first_uses(in_category_sense(text, table, categories), table, used,
                                       names)
    return said.replace(_SENSE, ""), used


def room_texts(folder: Path) -> list[str]:
    """t107: the text of every file the room holds as its own (markdown and JSON), never nemo's
    output, the public pages or a dot folder: what a manager may meet an abbreviation in."""
    folder = Path(folder)
    return [p.read_text(errors="replace") for p in sorted(folder.rglob("*"))
            if p.is_file() and p.suffix in (".md", ".json")
            and not p.relative_to(folder).as_posix().startswith(("output/", "public/"))
            and "/." not in "/" + p.relative_to(folder).as_posix()]


def undefined_in_room(folder: Path) -> list[str]:
    """t107: every abbreviation the room's files use that neither its glossary nor nemo names."""
    return terms.undefined(room_texts(folder), {**room_glossary(folder), **room_terms(folder)})


def standing(used: Iterable[str]) -> set[str]:
    """t215: the standard's own words among `used` (`terms.STANDARD_TERMS`): the ones that stay
    named for the rest of the conversation. Every other term is named again in the next turn."""
    return set(used) & terms.STANDARD_TERMS


#: t397: a draft nemo shows (`core.drafts_first`): a paragraph opening with its bold address line
#: and then its subject line, to the paragraph's end. t418: A2's quote block (`core.quotes_said`)
#: too, from its head to the paragraph's end: the findings and quotes as said. t418 r3
#: (35_nemo_check): a speaker's own words are a quote with or without quote marks, so A2's list of
#: what changed (`core.changes_block`), the interview's own summary its head attributes to it, too
DRAFT = re.compile(r"(^\*\*(?:To [^\n]*\*\*  \nSubject: |What the interview says · ).*?(?=\n\n|\Z)"
                   r"|^\*\*What changed since last year's record\*\*\s· [^\n]*\n\n.*?(?=\n\n|\Z))",
                   re.M | re.S)


def named_turn(text: str, cards: list[str], table: dict[str, str],
               conversation: set[str] | None = None,
               names: Iterable[str] = (), categories: Iterable[str] = ()) -> tuple[str, list[str]]:
    """t107: a turn as he reads it: the cards first (the app sends them first), then the answer,
    each term followed by its plain name at its first use in the turn, never inside a quote.

    t215: `conversation` holds the standard words already named in this conversation. They are
    handed in as already used, so they are said bare, and the set gains the ones this turn names.
    Without it a turn is named on its own, as 107 had it.

    t377 M: `names` are the item names a term stands inside, never broken
    (`terms.name_first_uses`).

    t397: a draft (`DRAFT`) is the email as it would be sent, kept as it is like a quote: no gloss
    inside it, and a use there is no first use.

    t473 r2: `categories` are the room's category names (`in_category_sense`)."""
    used: frozenset[str] = frozenset(conversation or ())
    names, categories = tuple(names), tuple(categories)

    def named(part: str) -> str:
        nonlocal used
        pieces = DRAFT.split(part)
        for n in range(0, len(pieces), 2):
            pieces[n], used = _named(pieces[n], table, used, names, categories)
        return "".join(pieces)

    out = [named(c) for c in cards]
    said = named(text)
    if conversation is not None:
        conversation |= standing(used)
    return said, out


def named_result(result: Any, table: dict[str, str], used: set[str],
                 names: Iterable[str] = (), categories: Iterable[str] = ()) -> Any:
    """t107: a tool result as the model reads it, each term named at its first use in the turn
    (`used` carries the turn's). Prose only, a string with a space in it: a bare value is an id
    for the next call. Nothing under a verbatim key: a quote, a path, a file is served as it is.
    t377 M: `names` as in `named_turn`, so the model reads an item's name whole; t473 r2:
    `categories` too."""
    if isinstance(result, dict):
        return {k: v if k in VERBATIM else named_result(v, table, used, names, categories)
                for k, v in result.items()}
    if isinstance(result, list):
        return [named_result(v, table, used, names, categories) for v in result]
    if isinstance(result, str) and " " in result:
        said, now = _named(result, table, frozenset(used), names, categories)
        used |= now
        return said
    return result


# ── the referee's shared-quote finding, in words: nemo's own since t133 ─────────────────────────
plain_finding = handover.plain_finding
