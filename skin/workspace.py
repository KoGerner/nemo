"""Ticket 247 (ADR-0042): every room's workspace page, its stages, graph and files beside its chat.

The owner, 2026-10-01T13:16:10Z: *"in bia-workflow v1, I also had a site, where teh chat eas
embedded, and on teh left side, I saw teh BIA-stages, a link to teh isolated dependency-graph, and
teh isolated company files. I need this back, and embedd chainlit."* v1's page is
`/home/user/work/bia-workflow/deploy/bia-live-embed.html`; the layout is his variation A in two
versions, a bar over the chat on a phone (the one used most) and a navy rail beside it on a laptop.

Served by the chat app itself (`PROTOTYPE_conversation_app.py`, GET only), so the page and the chat
it frames share one origin and nothing about framing or cookies is loosened
(`docs/research/chainlit-embedding.md`):

    <root>/w/<code>            the page; its frame opens the room's own link, <root>/r/<code>?frame
    <root>/w/<code>/files      the room's company files 01_…07_ and what nemo wrote under output/,
                               in groups, each by a name a tester reads (ticket 291)
    <root>/w/<code>/documents  "Your documents": only what nemo has written for the room (t291)
    <root>/w/<code>/f/<file>   one of those, as plain text
    <root>/w/<code>/read/<file>  one of those drawn as a page to read (ticket 638)
    <root>/w/<code>/doc/<file>   a document "Your documents" lists, drawn the same way (638)
    <root>/w/<code>/graph      the room's grouped graph as drawn (ticket 248, ADR-0040)
    <root>/w/<code>/slides     three slides for the BIA meeting, filled from the record (ticket 259)
    <root>/w/<code>/re-interview/<activity>
                               a re-BIA's re-interview sheet, from last year's record (ticket 260)
    <root>/w/<code>/stage-map  the five stages with the sheet's 18 prompts in them (ticket 478)
    <root>/w/<code>/impact/<process>.svg   the impact over time, drawn from that process's record
                               on each request, nothing written (ticket 255)
    <root>/w/<code>/graph-live the live graph page with nemo beside it (ticket 292, `live_graph`)
    <root>/w/<code>/stage      the page's stages as JSON, which it re-reads to follow the walk (311)
    <root>/w/<code>/briefing/<activity>.pdf
                               the activity's two-page briefing, printed on request (ticket 405,
                               `briefing`; served by the app, `briefing` below)

**Isolation is the property** (ADR-0042 d2): the code is judged as the door judges a link
(`nemo.room_code.mintable`, `nemo.door.checked_room_folder`, nothing percent-decoded), and a file is
served only if it is, string for string, one the files page lists. The list holds regular files
inside the room's own folder and nothing reached through a link, so `..`, encodings, absolute paths
and symlinks have nothing to match. Every refusal is the same empty 404.

The graph is the one page stage 4 or a chat turn offering the chain (282) drew,
`public/graph-v1/marschkamp/index.html`; the workspace never draws it (a GET stays read-only,
ADR-0042). It is served only if it is a regular file inside the room's own folder with no link
on the way; it needs nothing beside itself. On his tailnet phone origin no read-only site is
there, so the workspace serves it itself (he TYPED 2026-10-01T15:06:45Z *"yes, fix the graph
link in my room too"*). nemo's own page (`public/graph/…`) is never served.

t636 (his C12, 2026-10-30): 261's process map page went; the room's `01_Organisation/process-map.md`
stays, which core, the graph and next_step read.
"""
from __future__ import annotations

import html
import json
import re
from itertools import groupby
from pathlib import Path
from string import Template
from typing import Any, NamedTuple
from urllib.parse import quote, unquote, urlsplit

import impact_chart

from nemo import handover, turn_file, walk
from nemo.door import checked_room_folder, identity_from_link
from nemo.room_code import Refused, mintable
from nemo.room_store import PathRefused, read_record

import PROTOTYPE_core as core
from PROTOTYPE_core import PROCESS_MAP, map_name

#: The sample company every room is minted from, as the read-only site names its graph.
COMPANY = "Marschkamp"
CONTACT = "contact@kgerner.com"
PRIVACY = "https://ai4bcm.org/privacy/"
PLUG_IN = "https://ai4bcm.org/plug-it-in/"
#: t684 (ADR-0063 point 4): the one question "Start over" asks, in his words
START_OVER = "Start over? Your chat is archived, not deleted."
FIRST_PROMPT = f"Start a BIA for {COMPANY}. Take me through it one stage at a time."
#: t319: the five stages in the glossary's words, for the phone's stage bar. t432: the one source
#: of every "Stage N of 5" line, the chat's headings too (`walk.SHORT_NAMES`).
SHORT_STAGES = walk.SHORT_NAMES
#: t432: and the rail and the menu sheet say them as well (the long line is a card's subtitle only)
STAGES = SHORT_STAGES
#: t770: what each stage does, his words of 4 Nov ("Yes, use them"), as
#: `docs/research/five-stages-how-it-must-look.md` "The words a user reads" holds them: the
#: stage's hover on the laptop, a line under it in the phone's menu sheet (`.stages li::after`).
STAGE_LINES = (
    "Decide what this BIA covers: who to talk to and what they are responsible for.",
    "Prepare and invite, then a structured interview: the questions are asked and the answers "
    "challenged.",
    "Turn what was said into a standard template: a table and numbers you can work on.",
    "List the requirements with their RTOs and RPOs: the numbers that count.",
    "Bring the requirements from all departments together and sanity-check them, then hand them "
    "over.")
#: The documents "Your documents" lists once nemo has written them. t256: the follow-up list, the
#: room's referrals by recipient (`PROTOTYPE_core.FOLLOW_UP`).
DOCUMENTS = (handover.HANDOVER, handover.CERTIFICATE, "follow-up-list.md")
#: The grouped graph stage 4 draws (`PROTOTYPE_v1graph`), the only one served (ADR-0040).
GRAPH = core.GRAPH_PAGE
#: t259: "What is BCM", his text word for word (he approved it "as written", AskUserQuestion
#: 2026-10-01T21:36:33Z in 22_nemo_check's session 0a4cb4af).
WHAT_IS_BCM = ("Business continuity management (BCM) keeps the activities your customers depend on "
               "running through a disruption, and gets them back within times you agree in "
               "advance. Today we check last year's business impact analysis: what changed, what "
               "still holds.")
#: Where a results row comes from, as `last_year`'s `source` says: the prior cycle
#: (08_Prior-Cycle/), or a signed walk set aside under ticket 245, which carries no date before
#: 258 and no figures.
PRIOR_LABEL = "from the Feb 2025 BIA (final, approval not recorded)"
SIGNED_LABEL = "from last cycle's signed BIA"
NO_FIGURES = "No figures: the signed record states none"
FIRST_TIME = "No record last cycle: a first assessment"
#: t260: the re-interview sheet (ADR-0044). Each section ends on this question, and space to answer.
CHANGED = "Has anything changed?"
NOT_STATED = "not stated"
#: a grid cell last year's record leaves blank, shown as the record shows it (ADR-0044's note)
BLANK = "–"
NO_GRID = "No impact grid: last year's record states none"
#: The one stated rule for a single point of failure (ADR-0044's notes of 2026-10-02 and
#: 2026-10-05), as the sheet prints it.
SPOF_RULE = ("Flagged: a resource whose row states no workaround (empty, or saying \"no "
             "workaround\" or \"no direct workaround\"), and a supplier written for the demo "
             "pack as the single source. An empty cell on a row written for the demo pack states "
             "nothing, so it is not flagged.")
#: How "Your documents" names a process's impact chart (ticket 255).
IMPACT = "Impact over time · "
#: t291: the files page's groups, in order. A file's group is its top folder's: 02_ is the method,
#: 07_ the interviews, output/ what nemo wrote, and every other 01_…07_ folder the company's own.
GROUPS = ("Organisation", "Method", "Interviews", "Written by nemo")
#: t291: an interview as the seed names it, "<yy>_<mm>_<dd>_<process>-<person>-interview.md".
INTERVIEW = re.compile(r"(\d\d)_(0[1-9]|1[0-2])_(\d\d)_(.+)-([^-]+)-interview\.md")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
#: t291: nemo's documents whose file name, read plainly, would lose a capital or a hyphen.
TITLES = {walk.RECORD_NAME: "BIA record", handover.CERTIFICATE: "Owner sign-off certificate",
          "follow-up-list.md": "Follow-up list"}


class Answer(NamedTuple):
    status: int
    kind: str
    body: str


NOT_FOUND = Answer(404, "text/plain", "")


def answer(rooms: Path, root: str, raw_path: str, model: str, stamped: str | None) -> Answer:
    """What `<root>/w/…` answers. `raw_path` is the request's path as sent, never decoded;
    `stamped` is the tailnet proxy's `X-Room-Link`, which, where present, is the credential."""
    path = urlsplit(raw_path).path
    if not path.startswith(f"{root}/w/"):
        return NOT_FOUND
    code, _, rest = path[len(root) + 3:].partition("/")
    folder = _folder(rooms, code, model, stamped)
    return NOT_FOUND if folder is None else _served(root, code, folder, rest, stamped)


def briefing(rooms: Path, root: str, raw_path: str, model: str, stamped: str | None
             ) -> bytes | None:
    """t405: `<root>/w/<code>/briefing/<activity>.pdf`, the activity's two-page briefing printed
    now (`briefing.pdf`), for a room judged as `answer` judges it and an activity its process
    map names; None (the empty 404) for anything else, or where the print cannot run."""
    path = urlsplit(raw_path).path
    code, _, rest = path[len(root) + 3:].partition("/") if path.startswith(f"{root}/w/") \
        else ("", "", "")
    head, _, name = rest.partition("/")
    folder = _folder(rooms, code, model, stamped) if code and head == "briefing" else None
    activity = name.removesuffix(".pdf") if name.endswith(".pdf") else ""
    if folder is None or activity not in {r.slug for r in core.process_map_rows(folder)}:
        return None
    import subprocess

    import briefing as sheet  # it imports this module, so not at the top
    try:
        return sheet.pdf(folder, activity)
    except (OSError, ValueError, subprocess.SubprocessError) as why:
        print(f"briefing: {folder.name}/{activity} not printed: {type(why).__name__}", flush=True)
        return None


def _drawn_page(root: str, code: str, folder: Path, rest: str, stamped: str | None) -> str | None:
    """The room's own HTML pages (the workspace, its files, then what `_drawn_from_record` draws:
    259's slides, 260's sheet), or None for any other path; 261's process map page went (t636).
    Split from `_served` at 255's merge with 259, 260 and 261 to keep each under ruff's complexity
    cap."""
    if rest == "":
        return _page(root, code, folder, f"{root}/" if stamped else f"{root}/r/{code}?frame")
    if rest == "files":
        return _files_page(root, code, folder)
    if rest == "documents":
        return _documents_page(root, code, folder)
    head, slash, chosen = rest.partition("/")
    # t638: a file to read, only one its list holds, judged as `/f/` judges it
    if head in ("read", "doc") and unquote(chosen) in (_docs(folder) if head == "doc"
                                                      else _files(folder)):
        return _read_page(root, code, folder, unquote(chosen), head == "doc")
    if head == core.LIVE_GRAPH:  # t292: the live graph page, nemo beside it; 332 round 2: on <slug>
        return _live_graph(root, code, folder, chosen if slash else None)
    return _drawn_from_record(root, folder, rest)


def _live_graph(root: str, code: str, folder: Path, chosen: str | None = None) -> str | None:
    """t292's page, on the room's activity or one the process map names (332 round 2); None (the
    empty 404, never a 500) for any other, or where the files it draws from do not read, said in
    the log (t289, the 292 defect)."""
    if not _register_reads(folder):
        return None
    import live_graph
    if chosen is not None and chosen not in {r.slug for r in core.process_map_rows(folder)}:
        return None
    try:
        return live_graph.page(root, code, folder, harbour_link(root), chosen)
    except (OSError, ValueError) as why:  # the record it draws from does not read either
        print(f"graph-live: {folder.name}'s files do not read: {type(why).__name__}",
              flush=True)
        return None


def _served(root: str, code: str, folder: Path, rest: str, stamped: str | None) -> Answer:
    """What the room's own folder answers for the rest of its path."""
    page = _drawn_page(root, code, folder, rest, stamped)
    if page is None and rest == "graph" and _drawn(folder):
        page = (folder / GRAPH).read_bytes().decode("utf-8")
    if page is not None:
        return Answer(200, "text/html", framed(root, code, rest, page))
    if rest == "stage":
        return Answer(200, "application/json", json.dumps(progress(folder)))
    charts = _charts(folder)
    if rest in charts:
        return Answer(200, "image/svg+xml", charts[rest])
    if rest.startswith("f/") and unquote(rest[2:]) in _files(folder):
        return Answer(200, "text/plain", (folder / unquote(rest[2:])).read_text(errors="replace"))
    return NOT_FOUND


def _drawn_from_record(root: str, folder: Path, rest: str) -> str | None:
    """The pages code draws from the record: the meeting slides (t259) and a re-BIA's re-interview
    sheet (t260), and 478's stage map, drawn from code's table; None where the path names none,
    or a sheet a first BIA does not get."""
    if rest == core.STAGE_MAP:
        return _stage_map_page(root)
    if rest == "slides":
        return _slides(folder)
    return re_interview(folder, rest[13:]) if rest.startswith("re-interview/") else None


def _folder(rooms: Path, code: str, model: str, stamped: str | None) -> Path | None:
    """The room's chat folder `<code>-<model>`, or the folder its link names while no chat has
    opened yet; None for anything the door would refuse, or a folder that is not plainly the
    room's."""
    try:
        if not mintable(code) or (stamped and identity_from_link(stamped) != code):
            return None
        bare = checked_room_folder(rooms, code)
    except Refused:
        return None
    chat = rooms / f"{code}-{model}"
    folder = chat if chat.is_dir() else bare
    return None if folder.is_symlink() or folder.resolve().parent != rooms.resolve() else folder


def _files(folder: Path) -> list[str]:
    """The room's company files 01_…07_ and nemo's documents under output/, as room paths: regular
    files only, none behind a link, none hidden (the runs and the written-by notes)."""
    home = folder.resolve()
    tops = [*sorted(folder.glob("0[1-7]_*")), folder / "output"]
    found = []
    for top in tops:
        if not top.is_dir() or top.is_symlink():
            continue
        for f in sorted(top.rglob("*")):
            rel = f.relative_to(folder)
            # resolving to itself is what no link anywhere on the way does
            hidden = any(p.startswith(".") for p in rel.parts)
            if f.is_file() and f.resolve() == home / rel and not hidden:
                found.append(rel.as_posix())
    return found


def _charts(folder: Path) -> dict[str, str]:
    """255: each process record's impact chart, by its route under the room
    (`impact/<process>.svg`), drawn now from the record's own grid and method. Only records the
    files page lists, so none behind a link; a record with no score draws none."""
    charts = {}
    for f in _files(folder):
        top, process, name = (f.split("/") + ["", ""])[:3]
        if top != "output" or name != walk.RECORD_NAME or f.count("/") != 2:
            continue
        try:
            record = read_record(folder, f) or {}
        except (OSError, ValueError, PathRefused):
            continue
        method = record.get("method") or {}
        grids = [(a.get("name") or "", a.get("impact_grid")) for a in record.get("activities") or []
                 if isinstance(a, dict)]
        drawn = [impact_chart.svg(grid, method, _named(folder, name or process))
                 for name, grid in grids if isinstance(method, dict)]
        if drawn := [d for d in drawn if d]:
            charts[f"impact/{quote(process)}.svg"] = impact_chart.stacked(drawn)
    return charts


def _named(folder: Path, process: str) -> str:
    """255b: a process as the room's own process map names it, never its slug. A map the files
    page does not list (a link) is not read: the process reads as its own words, hyphens as
    spaces."""
    if PROCESS_MAP in _files(folder):
        return map_name(folder, process)
    return " ".join(process.split("-"))  # 247 reads a replace call as a write


def _drawn(folder: Path) -> bool:
    """The room has drawn its graph (`core.graph_drawn`)."""
    return core.graph_drawn(folder)


def _register_reads(folder: Path) -> bool:
    """t289 (292 defect): the live graph draws from the room's register, so it is there whenever
    the register reads; a register that does not read is said in the log, room and reason."""
    try:
        json.loads((folder / core.REGISTER).read_text(encoding="utf-8"))
    except (OSError, ValueError) as why:
        print(f"graph-live: {folder.name}'s register does not read: {type(why).__name__}",
              flush=True)
        return False
    return True


def reached(folder: Path) -> int:
    """How far the walk this room moved last has come, off its run file (`walk.stages_done`).

    A minted room ships one run per process; the one written last is the one the chat is walking,
    and among runs no answer has touched, the furthest along. No run at all is stage 1, not done."""
    runs = _room_runs(folder)
    return max(runs)[1] if runs else 0


def _walking(folder: Path) -> str | None:
    """t259: the process `reached` reads, the one the chat is walking; None before any run."""
    runs = _room_runs(folder)
    return max(runs)[2] if runs else None


def _room_runs(folder: Path) -> list[tuple[int, int, str]]:
    """Each run the room holds: when it was written, its stages done, and its process."""
    runs = []
    for run in (folder / walk.RUNS).glob("*.json"):
        if run.is_file() and not run.is_symlink():
            try:
                saved = read_record(folder, f"{walk.RUNS}/{run.name}")
            except (OSError, ValueError, PathRefused):
                continue
            runs.append((run.stat().st_mtime_ns, walk.stages_done(saved), run.stem))
    return runs


def _link(href: str, text: str, item: str = "") -> str:
    data = f' data-item="{item}"' if item else ""
    return f'<a{data} href="{html.escape(href)}" target="_blank" rel="noopener">{text}</a>'


def _in_panel(href: str, text: str, item: str) -> str:
    """t637: a link the chat page opens in its panel over the chat, never in a new tab."""
    return (f'<a data-item="{item}" href="{html.escape(href)}" onclick="return openPanel(this)">'
            f"{text}</a>")


def _group(rel: str) -> str:
    top = rel.split("/")[0]
    return GROUPS[3] if top == "output" else {"02": GROUPS[1], "07": GROUPS[2]}.get(top[:2],
                                                                                    GROUPS[0])


def _capital(words: str) -> str:
    return words[:1].upper() + words[1:]


def _titled(folder: Path, process: str) -> str:
    """t291: a process by the name its room's process map gives it, hyphens kept ("One-off
    payments"); one the map does not list, or a map the files page does not, by its own words."""
    named = core.process_name(folder, process) if PROCESS_MAP in _files(folder) else process
    return _capital(" ".join(named.split("-")) if named == process else named)


def readable(folder: Path, rel: str) -> str:
    """t291: a room file by a name a tester reads, never its path. An interview is its process,
    the person and the day ("Payroll · Brodersen · 20 Jan 2025"); a document nemo wrote for a
    process is its title and the process ("Requirements handover · Payroll"); any other file is
    its own `#` title cut before " — " or ": " (t638: "BIA programme plan"), else its file name,
    hyphens and underscores as spaces."""
    parts = rel.split("/")
    said = INTERVIEW.fullmatch(parts[-1]) if parts[0].startswith("07_") else None
    if said:
        yy, mm, dd, process, person = said.groups()
        return (f"{_titled(folder, process)} · {_capital(person)} · "
                f"{int(dd)} {MONTHS[int(mm) - 1]} 20{yy}")
    own = (_OWN_TITLE.search(_HIDDEN.sub("", (folder / rel).read_text(errors="replace")))
           if parts[0] != "output" and rel.endswith(".md") and (folder / rel).is_file() else None)
    title = TITLES.get(parts[-1]) or (own[1].strip() if own else _capital(
        " ".join(re.split(r"[-_]", Path(parts[-1]).stem))))
    return (f"{title} · {_titled(folder, parts[1])}" if parts[0] == "output"
            and len(parts) > 2 else title)


def _docs(folder: Path) -> list[str]:
    """The documents nemo has written (`DOCUMENTS`), as room paths; t638's `/doc/` opens these."""
    files = _files(folder)
    return [f for name in DOCUMENTS for f in files
            if f.startswith("output/") and f.endswith("/" + name)]


def documents(root: str, code: str, folder: Path) -> str:
    """ "Your documents", on its own page (t291), counted on the rail: the slides, a re-BIA's sheet,
    the documents nemo has written and the impact charts. Only what exists is listed. A document
    opens in the reader here (t638); the slides, the sheet and a chart in a new tab."""
    walking = _walking(folder)
    sheet = (f"<li>{_link(f'{root}/w/{code}/re-interview/{quote(walking)}', 'Re-interview sheet: '
                          + html.escape(core.process_name(folder, walking)))}</li>"
             if walking and core.last_year(folder, walking)["found"] else "")
    slides = f"<li>{_link(f'{root}/w/{code}/slides', 'Slides for the BIA meeting')}</li>"
    return _listed([slides, sheet] + [
        f'<li><a href="{root}/w/{code}/doc/{quote(f)}">'
        f"{html.escape(readable(folder, f))}</a></li>" for f in _docs(folder)] + [
        "<li>" + _link(f"{root}/w/{code}/{route}",
                       IMPACT + html.escape(_named(folder, unquote(route[7:-4])))) + "</li>"
        for route in _charts(folder)])


def _listed(entries: list[str]) -> str:
    """t659: the entries, or "None yet from nemo" only when there is none at all; the slides are
    always listed, so a served list never says it under entries it shows."""
    return "".join(entries) or "<li><small>None yet from nemo</small></li>"


def progress(folder: Path) -> dict[str, str]:
    """How far the walk has come, as the page draws it off `reached`: the rail's stages and the
    stage bar as HTML, and the bar's line as text, which 634's stage line over the typing box says.
    t311: `<root>/w/<code>/stage` serves the same, which the page re-reads to follow the walk.
    t445: and "Say this first" (289), the empty chat's suggestion, "" once he has said anything:
    the page drops the card when it reads "" here, so a page already shown loses it too."""
    done = reached(folder)
    now = min(done + 1, 5)
    states = ["done" if n <= done else "now" if n == now else "todo" for n in range(1, 6)]
    return {
        "stages": "".join(f'<li class="{s}"{CURRENT if s == "now" else ""}'
                          f' title="{html.escape(line)}"><span class="no">'
                          f'{"&#10003;" if s == "done" else n}</span>{html.escape(name)}</li>'
                          for n, (s, name, line)
                          in enumerate(zip(states, STAGES, STAGE_LINES, strict=True), 1)),
        "bar": "".join(f'<i class="{s}"></i>' for s in states),
        "where": (f"Stage {now} of 5 · {SHORT_STAGES[now - 1]}" if done < 5
                  else "All five stages done · signed"),
        "first": ("" if turn_file.past(folder, 1)
                  else FIRST.format(prompt=html.escape(FIRST_PROMPT)))}


def _page(root: str, code: str, folder: Path, frame: str) -> str:
    drawn = progress(folder)
    graph = (_link(f"{root}/w/{code}/{core.LIVE_GRAPH}", "Dependency graph",
                   "graph") if _register_reads(folder)
             else '<span data-item="graph">Dependency graph — <small>appears once you ask about'
                  ' dependencies or reach stage 4</small></span>')
    # t291 merge (25_nemo_check): the count is the links of the list /documents serves, drawn
    # here; the app adds 257's drafts to it (`counted`)
    count = documents(root, code, folder).count("<a ")
    return PAGE.format(
        harbour=harbour_link(root), company=COMPANY, code=html.escape(code),
        frame=html.escape(frame), bar=drawn["bar"], stages=drawn["stages"], graph=graph,
        where=html.escape(drawn["where"]),
        follow=json.dumps(f"{root}/w/{code}/stage"),  # the code is `mintable`, nothing to escape
        start_over=json.dumps(f"{root}/start-over/{code}"), asked=json.dumps(START_OVER),
        files=_in_panel(f"{root}/w/{code}/files", "Company files", "files"),
        documents=_in_panel(f"{root}/w/{code}/documents",
                            f'Your documents <small id="docs-count">{count}</small>', "documents"),
        first=drawn["first"], plug_in=_link(PLUG_IN, "Plug it into your AI", "plug-in"),
        privacy=json.dumps(PRIVACY),
        # t634 (C14): "Report a problem", the chat's code already in the mail's subject
        contact=_link(f"mailto:{CONTACT}?subject={quote(f'nemo chat {code}')}",
                      "Report a problem", "contact"))


def counted(page: str, more: int) -> str:
    """t291 merge: the page with `more` added to the count beside "Your documents", for the
    links the app adds to the list /documents serves (257's drafts)."""
    return re.sub(r'(<small id="docs-count">)(\d+)', lambda m: f"{m[1]}{int(m[2]) + more}", page,
                  count=1)


def _top(root: str, code: str, where: str) -> str:
    """t291: nemo's header on the pages beside the chat, and the way back to it."""
    return (f'<header class="top"><span class="wm">AI4<b>BCM</b></span><span class="prod">nemo'
            f'</span><span class="where">{where}</span><a class="back" '
            f'href="{root}/w/{html.escape(code)}/">&#8592; Chat</a></header>')


def _files_page(root: str, code: str, folder: Path) -> str:
    """t291: the room's files in `GROUPS`, each by its `readable` name; the link behind each is
    the file's reader (t638), in the same frame, string for string as `_drawn_page` matches it."""
    files = _files(folder)
    groups = "".join(
        f"<h2>{group}</h2>\n<ul class=\"files\">" + ("".join(
            f'<li><a href="{root}/w/{code}/read/{quote(f)}">'
            f"{html.escape(readable(folder, f))}</a></li>"
            for f in files if _group(f) == group) or "<li>None yet</li>") + "</ul>\n"
        for group in GROUPS)
    return FRAME.format(harbour=harbour_link(root), title="company files",
                        top=_top(root, code, "Company files"),
                        eyebrow=f"{COMPANY} · read-only", heading="Company files",
                        body=groups,
                        hint="Each opens here, as it is in your room.")


#: t638: what `rendered` draws, and no more. Front matter and comments are not shown.
_HIDDEN = re.compile(r"\A---\n.*?\n---\n|<!--.*?-->", re.S)
_BLOCK = re.compile(r"(#{1,6}) (.*)|(-{3,}|\*{3,})\s*|> ?(.*)|[-*] (.*)|(\d+)\. (.*)")
#: an interview's speaker: one to four capitalised words opening the paragraph ("Timo Voß: ")
_SPEAKER = re.compile(r"\A([A-ZÄÖÜ][\w.'-]*(?: [A-ZÄÖÜ][\w.'-]*){0,3}): ")
#: a file's own title, before any " — " or ": " ("BIA programme plan: Marschkamp, 2026 cycle")
_OWN_TITLE = re.compile(r"^# (.+?)(?: — |: |$)", re.M)


def _inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(text, quote=False))
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def _kind(line: str) -> str:
    return ("" if not line.strip() else "table" if line.lstrip().startswith("|")
            else "line" if _BLOCK.fullmatch(line.rstrip()) else "text")


def _para(lines: list[str], interview: bool) -> str:
    said = "".join(_inline(x.strip()) + ("<br>" if x.endswith("  ") else " ")
                   for x in lines).strip().removesuffix("<br>")
    return f"<p>{_SPEAKER.sub(r'<b>\1:</b> ', said, count=1) if interview else said}</p>"


def _table(rows: list[str]) -> str:
    def cells(row: str, tag: str) -> str:
        return "".join(f"<{tag}>{_inline(c.strip())}</{tag}>"
                       for c in row.strip().strip("|").split("|"))
    head, *body = [r for r in rows if not re.fullmatch(r"[\s|:-]+", r)] or [""]
    return (f'<div class="tbl"><table><tr>{cells(head, "th")}</tr>'
            + "".join(f'<tr>{cells(r, "td")}</tr>' for r in body) + "</table></div>")


def _line(line: str) -> str:
    m = _BLOCK.fullmatch(line.rstrip())
    assert m  # `_kind` said so
    if m[1]:
        n = min(max(len(m[1]), 2), 4)  # one h1 a page: its own
        return f"<h{n}>{_inline(m[2])}</h{n}>"
    if m[3]:
        return "<hr>"
    if m[4] is not None:
        return f"<blockquote>{_inline(m[4])}</blockquote>"
    if m[5] is not None:
        return f"<li>{_inline(m[5])}</li>"
    return f'<li value="{m[6]}">{_inline(m[7])}</li>'


def rendered(text: str, interview: bool = False) -> str:
    """t638: a room file's markdown as HTML for the reader, no library: headings, paragraphs,
    lists, quotes, rules and tables (each in a box that slides sideways on its own), bold and
    code, everything escaped first; in an interview the speaker's name is bold."""
    out = []
    # the first `#` line is the file's title, which the page's own h1 names
    shown = re.sub(r"^# .*$", "", _HIDDEN.sub("", text), count=1, flags=re.M)
    for kind, group in groupby(shown.splitlines(), key=_kind):
        lines = list(group)
        out += ([_table(lines)] if kind == "table" else [_para(lines, interview)]
                if kind == "text" else [_line(x) for x in lines] if kind == "line" else [])
    drawn = re.sub(r"((?:<li>.*?</li>)+)", r'<ul class="md">\1</ul>', "".join(out))
    return re.sub(r"((?:<li value=.*?</li>)+)", r'<ol class="md">\1</ol>', drawn)


def _read_page(root: str, code: str, folder: Path, rel: str, document: bool) -> str:
    """t638: a room file to read, in the lists' own frame, formatted and never its raw markdown;
    "← Company files" (or "← Your documents") goes back to its list in the same place, 637's
    panel included, and the foot links the file as it is (`/f/`)."""
    back, named = ("documents", "Your documents") if document else ("files", "Company files")
    text = (folder / rel).read_text(errors="replace")
    body = (f'<pre class="json">{html.escape(text)}</pre>' if rel.endswith(".json")
            else f'<div class="doc">{rendered(text, rel.startswith("07_"))}</div>')
    title = html.escape(readable(folder, rel))
    return FRAME.format(harbour=harbour_link(root), title=title, top=_top(root, code, named),
                        eyebrow=f'<a class="up" href="{root}/w/{code}/{back}">&#8592; {named}</a>'
                                f'</p>\n<p class="eb">{_group(rel)}',
                        heading=title, body=body,
                        hint=f'Read-only. <a href="{root}/w/{code}/f/{quote(rel)}">The file as it '
                             "is</a>")


def _documents_page(root: str, code: str, folder: Path) -> str:
    """t291: "Your documents" on a page of its own; the rail counts its links."""
    return FRAME.format(harbour=harbour_link(root), title="your documents",
                        top=_top(root, code, "Your documents"),
                        eyebrow=f"{COMPANY} · written by nemo", heading="Your documents",
                        body=f'<ul class="docs">{documents(root, code, folder)}</ul>\n',
                        hint="Files open here, slides and charts in a new tab. nemo adds one "
                             "when it writes it.")


def core_processes(folder: Path) -> list[str]:
    """t259: the room's core processes, by the names its process map gives them in the section
    headed "Core processes", in the map's order. A room with no such section has none."""
    path = folder / core.PROCESS_MAP
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    section = re.search(r"^##[^\n]*core processes[^\n]*\n(.*?)(?=^## |\Z)", text,
                        re.I | re.M | re.S)
    return [name for name, _ in core._MAP_ROW.findall(section.group(1))] if section else []


def _slides(folder: Path) -> str:
    """t259: the three meeting slides, a fixed template filled by code, never by a model. The
    figures are `last_year`'s and nothing else's: it reads last cycle's record, `room_sheet` this
    year's, and the second would put a draft on a slide about last year."""
    said = [(name, core.last_year(folder, name)) for name in core_processes(folder)]
    labels = list(dict.fromkeys(k for _, prior in said for k in prior.get("figures", {})))
    width = max(len(labels), 1)
    rows = []
    for name, prior in said:
        figures: dict[str, Any] = prior.get("figures", {})
        if not prior["found"]:
            cells, where = f'<td colspan="{width}">{FIRST_TIME}</td>', ""
        else:
            where = _label(prior)
            cells = ("".join(f"<td>{html.escape(str(figures.get(k, 'not stated')))}</td>"
                             for k in labels) if figures
                     else f'<td colspan="{width}">{NO_FIGURES}</td>')
        source = f"<small>{html.escape(where)}</small>" if where else ""
        rows.append(f"<tr data-process><th scope=\"row\"><b>{html.escape(name)}</b>{source}</th>"
                    f"{cells}</tr>")
    head = "".join(f'<th scope="col">{html.escape(k)}</th>' for k in labels) or \
        '<th scope="col">Figures</th>'
    table = (f'<table><thead><tr><th scope="col">Core process</th>{head}</tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table>' if rows
             else "<p>The process map lists no core processes.</p>")
    walking = _walking(folder)
    goal = (f"Today we walk {core.process_name(folder, walking)} through the five stages: last "
            "year's figures, what changed, what still holds." if walking else
            "Today we choose one activity and walk it through the five stages: last year's "
            "figures, what changed, what still holds.")
    return SLIDES.substitute(harbour=harbour_inline(), company=html.escape(COMPANY),
                             what=html.escape(WHAT_IS_BCM), results=table, goal=html.escape(goal))


def _stage_map_page(root: str) -> str:
    """t478: the walk's five stages, each with its long line and the sheet's prompts placed in it
    (`core.STAGE_PROMPTS`), by id and in the sheet's words. Every answer's stage label opens it on
    its stage (`#stage-<n>`), which the page marks. The same for every room; nothing on it acts."""
    import prompt_check  # the sheet's reader; only this page needs it

    sheet = prompt_check.sheet()
    sections = "\n".join(
        f'<section id="stage-{n}"><h2>{n} · {html.escape(walk.SHORT_NAMES[n - 1])}</h2>'
        f"<p>{html.escape(walk.LONG_NAMES[n - 1])}</p><ul>" + "".join(
            f'<li data-prompt="{pid}"><b>{pid}</b> {html.escape(sheet[pid])}</li>' for pid in ids)
        + "</ul></section>" for n, ids in core.STAGE_PROMPTS.items())
    return STAGE_MAP_PAGE.format(harbour=harbour_link(root), sections=sections)


def _label(prior: dict[str, Any]) -> str:
    """t259: which record a found `last_year` read, in the words a slide or sheet heads it with."""
    return PRIOR_LABEL if prior["source"].startswith(f"{core.PRIOR}/") else SIGNED_LABEL


#: t330: a workaround cell that states the absence, anywhere in it (ADR-0044's note of 2026-10-05).
NO_WORKAROUND = re.compile(r"\bno (direct )?workaround\b", re.IGNORECASE)


def flagged(asset: dict[str, Any], row: dict[str, Any]) -> bool:
    """t260: the one stated rule for a single point of failure (ADR-0044's notes of 2026-10-02 and
    2026-10-05). A transcribed register row is flagged when its workaround is empty or states "no
    workaround" or "no direct workaround" anywhere (case ignored, t330). On an authored row
    (ADR-0034 Part B), or one added in chat (318), an empty cell states nothing and a way round its
    record states (735) changes no flag, so it is flagged only on an authored supplier carrying the
    authored "single source" mark; 604: or on an authored row whose own cell states there is none
    (veterinary and QA release, cold-chain monitoring)."""
    said = str(row.get("workaround") or "").strip()
    if row.get("authored") or row.get(walk.ADDED_IN_CHAT):
        return (asset.get("authored") is True and asset.get("asset_type") == "External supplier"
                and "single source" in str(asset.get("description") or "").lower()) or bool(
            row.get("authored") and NO_WORKAROUND.search(said))
    return not said or bool(NO_WORKAROUND.search(said))


def _activities(folder: Path) -> set[str]:
    """The slugs a sheet may be asked for: the process map's, and the room's walks'."""
    path = folder / core.PROCESS_MAP
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {slug for _, slug in core._MAP_ROW.findall(text)} | {r[2] for r in _room_runs(folder)}


def _changed() -> str:
    return f'<h3>{CHANGED}</h3><div class="answer"></div>'


def re_interview(folder: Path, activity: str) -> str | None:
    """t260: the re-interview sheet for one activity of this room, projected by code from last
    year's record as `last_year` reads it (ADR-0044); None for a first BIA, which gets no sheet.

    Three sections, each ending on "Has anything changed?": last year's figures, its impact grid as
    recorded (none is made where it holds none, ADR-0014), and the room's register rows for the
    activity with the single points of failure flagged by `flagged`."""
    if activity not in _activities(folder):
        return None
    prior = core.last_year(folder, activity)
    if not prior["found"]:
        return None
    points = core.focus_points(folder, activity)  # t377 (D3): on top, above last year's
    focus = ('<section data-section="focus"><h2>Focus this year</h2><ol>'
             + "".join(f"<li>{html.escape(p)}</li>" for p in points) + f"</ol>{_changed()}"
             "</section>") if points else ""
    return SHEET.substitute(
        harbour=harbour_inline(), company=html.escape(COMPANY), focus=focus,
        name=html.escape(core.process_name(folder, activity)), source=html.escape(_label(prior)),
        figures=_figures(prior["figures"]), grid=_grid(prior.get("grid")),
        resources=_resources(folder, activity), changed=_changed())


def _figures(figures: dict[str, Any]) -> str:
    """t260: MTPD, RTO and RPO, then any other figure, as last year's record states them."""
    if not figures:
        return f"<p>{NO_FIGURES}</p>"
    labels = dict.fromkeys(["MTPD", "RTO", "RPO", *figures])
    return "<table><tbody>" + "".join(
        f'<tr><th scope="row">{html.escape(k)}</th>'
        f"<td>{html.escape(str(figures.get(k, NOT_STATED)))}</td></tr>" for k in labels
    ) + "</tbody></table>"


def _grid(grid: dict[str, Any] | None) -> str:
    """t260: the impact grid as last year's record states it; a blank cell shows as the record
    shows it, and none is made where the record holds none (ADR-0044's note, ADR-0014)."""
    if not grid:
        return f"<p>{NO_GRID}</p>"
    horizons = list(dict.fromkeys(h for row in grid.values() for h in row["cells"]))
    head = "".join(f'<th scope="col">{html.escape(h)}</th>' for h in horizons)
    body = "".join(
        f'<tr><th scope="row">{html.escape(category)}</th><td>{html.escape(row["remark"])}</td>'
        + "".join(f"<td>{html.escape(row['cells'].get(h) or BLANK)}</td>" for h in horizons)
        + "</tr>" for category, row in grid.items())
    return (f'<table><thead><tr><th scope="col">Category</th><th scope="col">Remark</th>{head}'
            f"</tr></thead><tbody>{body}</tbody></table>"
            f"<p><small>{BLANK} is a cell last year's record leaves blank.</small></p>")


def _resources(folder: Path, activity: str) -> str:
    """t260: this room's register rows for the activity, each flagged or not by `flagged`."""
    if walk.unreadable_register(folder):  # t299: named, as a turn names it (t297)
        return f"<p>{html.escape(walk.UNREADABLE_REGISTER.format(path=walk.REGISTER))}</p>"
    register = core.drafting.read_register(folder)
    rows = [(asset, row) for asset in register.values() if isinstance(asset, dict)
            for row in asset.get("consumers") or [] if row.get("department") == activity]
    if not rows:
        return "<p>The register names no resource for this activity.</p>"
    body = "".join(
        f"<tr data-resource{' data-spof' if spof else ''}>"
        f'<th scope="row">{html.escape(str(asset.get("name") or ""))}</th>'
        f"<td>{html.escape(str(row.get('need') or NOT_STATED))}</td>"
        f"<td>{html.escape(str(row.get('workaround') or NOT_STATED))}</td>"
        f"<td>{'Yes' if spof else 'No'}</td></tr>"
        for asset, row in rows for spof in [flagged(asset, row)])
    return (f'<p>{html.escape(SPOF_RULE)}</p><table><thead><tr><th scope="col">Resource</th>'
            '<th scope="col">Need</th><th scope="col">Workaround</th>'
            f'<th scope="col">Single point of failure</th></tr></thead><tbody>{body}</tbody>'
            "</table>")


_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex, nofollow">
"""

#: t287: every page links the one Harbour stylesheet the skin serves (`skin/harbour/`, with its
#: fonts) and names no colour of its own; nothing is fetched from off the box. The room code is in
#: this page's URL, which no request to the stylesheet carries.
HARBOUR = Path(__file__).resolve().parent / "harbour"
HARBOUR_KINDS = {".css": "text/css", ".woff2": "font/woff2"}


def harbour_link(root: str) -> str:
    return f'<link rel="stylesheet" href="{root}/harbour/harbour.css">\n'


#: What the two pages he saves into a meeting (259's slides, 260's sheet) carry instead of the
#: link, which is dead in a saved copy: the tokens themselves. fonts.css stays out, its url()s are
#: relative to the skin, so offline the fonts fall back to the system's.
INLINED = ("colors", "typography", "spacing", "shape")


def harbour_inline() -> str:
    css = "".join((HARBOUR / "tokens" / f"{name}.css").read_text(encoding="utf-8")
                  for name in INLINED)
    return f"<style>\n{css}</style>\n"


#: t293: nemo's frame on the four pages a room opens beside its chat, as 292's live graph page
#: draws it: the wordmark, the page's name and "← Chat" back to the room's workspace (his Q9,
#: 2026-10-02T21:22:33Z). Added as the page is served, after its own <body>: the drawn graph is
#: a file in the room that other servers serve as drawn, and a page with no <body> is left as it is.
#: The frame is the screen's, never the paper's. g150's own header line, "BIA Workflow" to v1's
#: knowledge base, gives way to it on the graph.
FRAMED = {"slides": "Slides for the BIA meeting", "re-interview": "Re-interview sheet",
          "graph": "Dependency graph", core.STAGE_MAP: "Stage map"}
FRAME_CSS = """
header.frame { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; margin: 0;
               padding: 14px 20px; background: var(--color-white);
               border: 0; border-bottom: 1px solid var(--color-hairline);
               font: 16px/1.5 var(--font-body, sans-serif); }
header.frame .wm { font: 700 18px/1 var(--font-display, sans-serif); letter-spacing: -.03em;
                   color: var(--color-navy); }
header.frame .wm b { color: var(--color-amber-wordmark); font-weight: 700; }
header.frame .prod { font: 500 18px/1 var(--font-display, sans-serif); color: var(--color-navy); }
header.frame .where { color: var(--color-muted); margin-left: 8px; }
header.frame .back { margin-left: auto; color: var(--color-navy); font-weight: 500;
                     text-decoration: none; }
header.frame .back:hover { color: var(--color-rust); text-decoration: underline; }
header:not(.frame) > .home { display: none; }
@media (max-width: 30rem) { header.frame { padding: 12px 16px; }
                            header.frame .where { display: none; } }
@media print { header.frame { display: none; } }
"""


def framed(root: str, code: str, rest: str, page: str) -> str:
    where = FRAMED.get(rest.partition("/")[0])
    head, closed, body = page.partition("</head>")
    top, opened, rest = body.partition("<body>\n")
    if where is None or not (closed and opened):
        return page
    frame = (f'<header class="frame"><span class="wm">AI4<b>BCM</b></span>'
             f'<span class="prod">nemo</span><span class="where">{where}</span>'
             f'<a class="back" href="{root}/w/{html.escape(code)}/">&#8592; Chat</a></header>\n')
    return f"{head}<style>{FRAME_CSS}</style>\n{closed}{top}{opened}{frame}{rest}"


def harbour_file(rest: str) -> tuple[str, bytes] | None:
    """What `<root>/harbour/<rest>` serves: a pinned stylesheet or font, by its exact name under
    `skin/harbour/`, or None for any other name."""
    files = {p.relative_to(HARBOUR).as_posix(): p for p in HARBOUR.rglob("*")
             if p.suffix in HARBOUR_KINDS and p.is_file()}
    path = files.get(rest)
    return None if path is None else (HARBOUR_KINDS[path.suffix], path.read_bytes())


#: t289: the current stage, as a screen reader is told it.
CURRENT = ' aria-current="step"'
#: t289 (ADR-0042's note of 2026-10-03): "Say this first", the empty chat's tappable suggestion. A
#: tap puts the prompt into the chat's own composer and sends it (the frame is this page's origin),
#: or, where the frame cannot be reached, copies it.
FIRST = """<div class="first" data-item="say-this-first"><small>Say this first</small>
<button class="say" type="button" onclick="sayFirst(this)">{prompt}</button></div>
"""

#: t289: direction C on the phone (the chat in white, the menu as a full-screen sheet), direction B
#: on the laptop (a white page, the rail as plain text on one left edge, a rust stroke on the
#: current stage). Every value is a Harbour token; the phone's "fog" for the current stage is the
#: page's grey, the nearest pinned shade, since Harbour pins no fog.
#: t634 (his chat-page choices, 2026-10-30): the chat has the whole screen. No header row: the mark
#: tops the rail on the laptop and a floating "☰ nemo" opens the menu on the phone, stepping aside
#: while he reads down. The stage line and "Say this first" sit over the typing box, inside the
#: frame (`dress`); the page's own `.stepline` and `.first` stay undrawn as what that line says,
#: and what `follow` keeps current.
PAGE = _HEAD + """<title>nemo · BIA working session</title>
{harbour}<style>
* {{ box-sizing: border-box; }}
html, body {{ height: 100%; margin: 0; }}
body {{ font: 16px/1.5 var(--font-body); color: var(--color-slate);
        background: var(--color-white);
        display: flex; flex-direction: column; height: 100dvh; -webkit-text-size-adjust: 100%; }}
a {{ color: var(--color-navy); }}
:focus-visible {{ outline: 3px solid var(--color-amber); outline-offset: 2px; }}
.mark {{ font: 700 18px/1 var(--font-display); letter-spacing: -.03em; color: var(--color-navy);
         white-space: nowrap; }}
.mark b {{ color: var(--color-amber-wordmark); font-weight: 700; }}
.mark span {{ font-weight: 500; letter-spacing: -.02em; }}
.top {{ display: flex; align-items: center; gap: 10px; padding: 14px 16px; flex: none;
        border-bottom: 1px solid var(--color-hairline); }}
.close, .fab, .shut {{ font: 500 14px var(--font-body); color: var(--color-navy);
                background: var(--color-white); border: 1.5px solid var(--color-navy);
                border-radius: var(--radius-buttons); padding: 8px 18px; min-height: 44px;
                cursor: pointer; }}
.close {{ margin-left: auto; }}
.fab {{ position: fixed; top: 8px; left: 8px; z-index: 4; padding: 6px 14px;
        box-shadow: 0 1px 4px var(--color-hairline); transition: transform .2s; }}
.fab.tucked {{ transform: translateY(-64px); }}
.stepline, .first {{ display: none; }}
.eb {{ font: 500 12px/1.2 var(--font-mono); letter-spacing: .12em; text-transform: uppercase;
       color: var(--color-muted); margin: 0 0 12px; }}
main {{ flex: 1; display: flex; flex-direction: column; min-height: 0; position: relative; }}
/* t637: Company files and Your documents in a sheet from the bottom on the phone, over the chat */
.panel {{ display: none; position: fixed; inset: 10vh 0 0; z-index: 6; flex-direction: column;
          background: var(--color-white); box-shadow: 0 -2px 12px var(--color-hairline);
          border-radius: var(--radius-cards) var(--radius-cards) 0 0; }}
.panel:not([hidden]) {{ display: flex; }}
.shut {{ align-self: flex-end; margin: 8px 12px; }}
.card {{ flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden;
         background: var(--color-white); }}
iframe {{ flex: 1; width: 100%; border: 0; background: var(--color-white); min-height: 0; }}
/* the menu: a full-screen sheet on the phone */
.rail {{ display: none; position: fixed; inset: 0; z-index: 5; overflow-y: auto;
         padding: 0 20px 24px; background: var(--color-white); color: var(--color-navy); }}
body.open .rail {{ display: block; }}
.rail .top {{ margin: 0 -20px 20px; padding: 14px 20px; }}
.rail ol, .rail ul {{ list-style: none; margin: 0; padding: 0; }}
.stages {{ margin-bottom: 20px !important; }}
.stages li {{ display: flex; flex-wrap: wrap; gap: 2px 12px; padding: 8px 0; font-size: 16px;
              line-height: 1.35; }}
.stages .no {{ font: 500 14px var(--font-mono); color: var(--color-muted); width: 16px; flex: none;
               padding-top: 1px; }}
.stages li.done .no, .stages li.now .no {{ color: var(--color-navy); }}
.stages li.now {{ font-weight: 500; background: var(--color-harbour-grey);
                  border-radius: var(--radius-inputs); padding: 8px; margin: 0 -8px; }}
.stages li.todo {{ color: var(--color-muted); }}
/* t770: no hover on the phone, so each stage's line sits under its name in the menu sheet */
.stages li::after {{ content: attr(title); flex: 0 0 100%; box-sizing: border-box;
                     padding-left: 28px; font: 400 14px/1.4 var(--font-body);
                     color: var(--color-muted); }}
.go a, .go > span {{ display: block; padding: 12px 0; font-weight: 500;
                     border-top: 1px solid var(--color-hairline);
                     color: var(--color-navy); text-decoration: none; }}
.go > a::after {{ content: " \\2192"; }}
.go small {{ font-weight: 400; color: var(--color-muted); }}
.go a small {{ font: 400 14px var(--font-mono); }}
.foot {{ font-size: 14px; color: var(--color-muted); margin: 16px 0 0;
         border-top: 1px solid var(--color-hairline); padding-top: 4px; }}
.foot code {{ font: 14px var(--font-mono); color: var(--color-navy); }}
.foot a, .foot button {{ display: inline-flex; align-items: center; min-height: 44px;
                         font: inherit; color: var(--color-muted); background: none; border: 0;
                         padding: 0; text-decoration: underline; cursor: pointer; }}
/* the laptop: a white page, the rail as plain text on one left edge, the chat beside it */
@media (min-width: 60rem) {{
  body {{ display: grid; grid-template-columns: 20rem minmax(0, 1fr);
          grid-template-rows: minmax(0, 1fr); }}
  .fab, .rail .close {{ display: none; }}
  .rail {{ display: block; position: static; grid-row: 1; min-height: 0; overflow-y: auto;
           padding: 16px 24px 24px; border-right: 1px solid var(--color-hairline); }}
  .rail .top {{ border: 0; margin: 0 0 16px; padding: 0; }}
  .stages li.now {{ background: none; border-radius: 0; margin: 0 0 0 -12px;
                    padding: 8px 0 8px 10px; box-shadow: inset 1.5px 0 0 var(--color-rust); }}
  main {{ grid-column: 2; grid-row: 1; padding: 0 16px; }}
  .panel {{ position: absolute; inset: 0; border-radius: 0; box-shadow: none; }}
}}
/* t770: where a mouse can hover, the laptop's line is the stage's hover; a touch tablet keeps it */
@media (min-width: 60rem) and (hover: hover) {{
  .stages li::after {{ display: none; }}
}}
</style></head>
<body>
<button class="fab" type="button" aria-controls="rail" aria-expanded="false"
 onclick="rail(true)">&#9776; nemo</button>
<div class="stepline"><div class="seg" aria-hidden="true">{bar}</div>
<p class="where">{where}</p></div>
<nav class="rail" id="rail" aria-label="Your BIA">
<div class="top"><span class="mark">AI4<b>BCM</b> <span>· nemo</span></span>
<button class="close" type="button" onclick="rail(false)">Close</button></div>
<p class="eb" data-item="stages">Your BIA · {company}</p>
<ol class="stages">{stages}</ol>
<div class="go">{graph}{files}{documents}{plug_in}</div>
<p class="foot"><span data-item="room-code">Chat ID <code class="room">{code}</code></span>
<button data-item="copy" type="button" onclick="copyCode(this)">Copy</button><br>
<button data-item="reload" type="button" onclick="reloadChat()">Reload</button> ·
<button data-item="start-over" type="button" onclick="startOver()">Start over</button><br>
{contact}</p>
</nav>
<main>
<div class="card">
{first}<iframe id="chat" title="nemo chat" src="{frame}" allow="clipboard-write"
 onload="dress(this)"></iframe>
</div>
<div class="panel" id="panel" hidden>
<button class="shut" type="button" onclick="shut()">&#10005; Close</button>
<iframe name="panel" title="Company files or your documents"></iframe>
</div>
</main>
<script>
/* t311: the stages follow the walk, re-read from the room's own route while the page is shown */
var FOLLOWS = {{bar: ".seg", stages: ".stages", where: ".stepline .where"}};
function follow() {{
  if (document.hidden) return;
  fetch({follow}, {{ cache: "no-store" }}).then(function (r) {{ return r.ok ? r.json() : {{}}; }})
    .then(function (s) {{
      for (var k in FOLLOWS) {{
        var e = document.querySelector(FOLLOWS[k]);
        if (!e || !(k in s)) continue;
        if (k === "bar" || k === "stages") e.innerHTML = s[k]; else e.textContent = s[k];
      }}
      var first = document.querySelector(".first");  // t445: gone once he has said anything
      if (first && s.first === "") first.remove();
      dressed();
    }}, function () {{}});
}}
setInterval(follow, 10000);  // 27_nemo_check: one worker serves every page; a turn is ~12 s
function rail(open) {{
  document.body.classList.toggle("open", open);
  document.querySelector(".fab").setAttribute("aria-expanded", open);
}}
/* t643: the graph opens in a tab of its own; the mark in its address tells it the chat opened
 * it, so its "← Chat" closes that tab (nginx sends no referrer to say so) */
[].forEach.call(document.querySelectorAll('.go a[data-item="graph"]'),
                function (a) {{ a.hash = "from-chat"; }});
function reloadChat() {{
  var f = document.getElementById("chat"); f.src = f.getAttribute("src"); rail(false);
}}
/* t684 (ADR-0063 point 4): one confirm, then the app does what /reset does: the old chat into
 * the archive, a fresh one under the same Chat ID; the page comes back on it */
function startOver() {{
  if (!confirm({asked})) return;
  fetch({start_over}, {{ method: "POST", headers: {{ "Content-Type": "application/json" }},
                       body: "{{}}" }})
    .then(function (r) {{ if (r.ok) location.reload(); else alert(NOT_STARTED); }},
          function () {{ alert(NOT_STARTED); }});
}}
var NOT_STARTED = "Start over did not work. Nothing was deleted.";
function copyCode(b) {{
  var code = document.querySelector(".foot .room"), done = function () {{
    b.textContent = "Copied"; setTimeout(function () {{ b.textContent = "Copy"; }}, 1500);
  }};
  var old = function () {{  // plain http, or the clipboard refused: the old way
    var range = document.createRange(), sel = getSelection();
    range.selectNodeContents(code); sel.removeAllRanges(); sel.addRange(range);
    document.execCommand("copy"); sel.removeAllRanges(); done();
  }};
  if (navigator.clipboard && window.isSecureContext) {{
    navigator.clipboard.writeText(code.textContent).then(done, old);
  }} else old();
}}
function sayFirst(b) {{
  var t = b.textContent, w = document.getElementById("chat").contentWindow;
  try {{
    var input = w.document.getElementById("chat-input");
    Object.getOwnPropertyDescriptor(w.HTMLTextAreaElement.prototype, "value").set.call(input, t);
    input.dispatchEvent(new w.Event("input", {{ bubbles: true }}));
    input.focus();
    setTimeout(function () {{
      var send = w.document.getElementById("chat-submit"); if (send) send.click();
    }}, 100);
    b.parentNode.remove();
  }} catch (e) {{
    if (navigator.clipboard) {{ navigator.clipboard.writeText(t); }}
  }}
  dressed();
}}
/* t637: Company files and Your documents open in a panel over the chat (a sheet on the phone),
 * the chat frame left loaded under it; the hash keeps the back button working.
 * t663: the panel pushes one entry, marked "panel", once; Close turns it bare, a reopen takes it */
function openPanel(a) {{  // not "panel": inline handlers read document.panel, the iframe
  var item = a.getAttribute("data-item"), open = !document.getElementById("panel").hidden;
  rail(false);
  show(item);
  if (open || history.state === "panel") history.replaceState("panel", "", "#" + item);
  else history.pushState("panel", "", "#" + item);
  return false;
}}
function shut() {{  // never history.back(): a file opened in the panel is a step of its own
  if (document.getElementById("panel").hidden) return;
  history.replaceState(history.state, "", location.pathname + location.search);
  show("");
}}
function show(item) {{
  var p = document.getElementById("panel"), f = p.querySelector("iframe"),
      a = /^(files|documents)$/.test(item) &&
          document.querySelector('.go [data-item=' + item + ']'), was = p.hidden;
  p.hidden = !a;
  if (!a) return;
  if (was || f.dataset.href !== a.getAttribute("href")) {{  // a fresh frame each opening and
    var g = f.cloneNode();  // page: its first load is no history entry, and shows the page anew
    g.dataset.href = g.src = a.getAttribute("href"); g.onload = f.onload;
    f.parentNode.insertBefore(g, f); f.remove();
  }}
  p.querySelector(".shut").focus();
}}
function inPanel(f) {{  // the page as it is, without its header and "← Chat"; Esc inside shuts it
  var d = f.contentDocument, style;
  if (!d || !d.head) return;
  style = d.createElement("style"); style.textContent = "header.top {{ display: none; }}";
  d.head.appendChild(style);
  d.addEventListener("keydown", esc);
}}
addEventListener("popstate", function () {{ show(location.hash.slice(1)); }});
function esc(e) {{
  if (e.key !== "Escape") return;
  shut();
  if (document.body.classList.contains("open")) {{  // t643: the phone menu too, back to its button
    rail(false); document.querySelector(".fab").focus();
  }}
}}
addEventListener("keydown", esc);
document.querySelector("#panel iframe").onload = function () {{ inPanel(this); }};
show(location.hash.slice(1));
/* t634: the frame is this page's origin, so the page dresses it (Chainlit 2.12.0's hooks, read
 * 2026-10-30): Chainlit's top row goes, the stage line and "Say this first" go over the typing box,
 * Privacy beside the line under it; on the phone the list keeps the menu button's room at its top,
 * and the button steps aside while he scrolls down by hand, not while Chainlit scrolls to a line.
 * t635: Chainlit's round down button goes for one "New answer" on the stage line, shown only when
 * an answer came while he had scrolled up by hand; a new answer opens at its first line; the stage
 * link shows only where the stage changes (478's rule as amended); neighbouring cites keep a gap
 * (602). t653: no label for the thinking row (C7 dropped); live `cot = "hidden"` never draws it,
 * and the rule below hides it where cot is not set. The typing box is an .overflow-y-auto too. */
var PRIVACY = {privacy}, dressed = function () {{}};
var DRESS = [
  "#header {{ display: none !important; }}",
  "#nemo-bar {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; width: 100%;",
  "  font: 14px/1.4 var(--font-body); color: var(--color-navy); }}",
  "#nemo-bar b {{ font-weight: 600; }}",
  "#nemo-bar button {{ font: 500 14px/1.35 var(--font-body); color: var(--color-navy);",
  "  background: var(--color-white); border: 1.5px solid var(--color-navy); cursor: pointer;",
  "  border-radius: var(--radius-buttons); padding: 6px 14px; min-height: 44px;",
  "  text-align: left; }}",
  "#nemo-bar button:hover {{ color: var(--color-on-navy); background: var(--color-navy); }}",
  ".watermark a {{ margin-left: 8px; padding-block: 13px; color: inherit;",
  "  text-decoration: underline; }}",
  ".nemo-phone .overflow-y-auto > .mx-auto.flex-grow.p-4 {{ padding-top: 60px !important; }}",
  ".absolute.bottom-4.left-0.right-0 {{ display: none !important; }}",
  "#nemo-bar [data-item=new-answer] {{ margin-left: auto; color: var(--color-on-navy);",
  "  background: var(--color-navy); }}",
  "[data-step-type=run], .nemo-same {{ display: none !important; }}",
  ".message-content a[href*='/f/'] + a[href*='/f/'],",
  ".message-content a[href*='/read/'] + a[href*='/read/'] {{ margin-left: 10px; }}"
].join("\\n");
function dress(frame) {{
  var w = frame.contentWindow, d;
  try {{ d = w.document; }} catch (e) {{ return; }}
  if (!d || !d.head || d.getElementById("nemo-dress")) return;
  var style = d.createElement("style"); style.id = "nemo-dress"; style.textContent = DRESS;
  d.head.appendChild(style);
  function bar() {{
    var c = d.getElementById("message-composer"), b = d.getElementById("nemo-bar");
    if (!c || b) return b;
    b = d.createElement("div"); b.id = "nemo-bar";
    b.innerHTML = '<span data-item="stage"></span>' +
                  '<button data-item="say-this-first" type="button" hidden></button>' +
                  '<button data-item="new-answer" type="button" hidden>&#8595; New answer</button>';
    c.parentNode.insertBefore(b, c);
    b.querySelector("[data-item=say-this-first]").onclick = function () {{
      var s = document.querySelector(".first .say"); if (s) sayFirst(s);
    }};
    b.querySelector("[data-item=new-answer]").onclick = function () {{
      if (pending) opened(pending);
      pending = null; away = false; sync();
    }};
    return b;
  }}
  function list() {{
    var e = d.querySelector("[data-step-type]"); return e && e.closest(".overflow-y-auto");
  }}
  function opened(answer) {{  // its first line at the top of the list, clear of the menu button
    var s = list(), clear = d.documentElement.classList.contains("nemo-phone") ? 60 : 8;
    if (s) s.scrollTop += answer.getBoundingClientRect().top - s.getBoundingClientRect().top -
                          clear;
  }}
  function tidy() {{
    // t628: the wait line stands in the bubble its answer takes, and is no answer until then
    var stage = "", answers = [].filter.call(
      d.querySelectorAll('[data-step-type="assistant_message"]'), function (e) {{
        var said = e.querySelector(".message-content");
        return !said || said.textContent.trim() !== "Checking your files…";
      }});
    answers.forEach(function (e) {{
      var link = e.querySelector('.ai-message a[href*="/stage-map#stage-"]');
      if (link) {{
        var said = link.textContent.trim();
        (link.closest("[role=article]") || link).classList.toggle("nemo-same", said === stage);
        stage = said;
      }}
    }});
    if (answers.length > seen && seen) {{
      var answer = answers[seen];
      if (away) pending = pending || answer;
      else setTimeout(function () {{
        var s = list();
        if (s && answer.getBoundingClientRect().top < s.getBoundingClientRect().top + 60) {{
          opened(answer);
        }}
      }}, 300);
    }}
    seen = answers.length;
  }}
  function sync() {{
    var b = bar(), mark = d.querySelector(".watermark");
    if (mark && !mark.querySelector("[data-item=privacy]")) {{  // inline, after the line itself
      var a = d.createElement("a"); a.href = PRIVACY; a.target = "_blank"; a.rel = "noopener";
      a.setAttribute("data-item", "privacy"); a.textContent = "Privacy";
      (mark.querySelector("[role=article]") || mark).appendChild(a);
    }}
    d.documentElement.classList.toggle("nemo-phone",
      getComputedStyle(document.querySelector(".fab")).display !== "none");
    tidy();
    if (!b) return;
    b.querySelector("[data-item=new-answer]").hidden = !pending;
    // written only when it changed: each write is a mutation the observer above would answer
    var where = document.querySelector(".stepline .where").textContent,
        m = where.match(/^(Stage \\d+ of \\d+)(.*)$/), st = b.querySelector("[data-item=stage]");
    if (st.textContent !== where) {{
      st.textContent = m ? m[2] : where;
      if (m) {{ var bold = d.createElement("b"); bold.textContent = m[1]; st.prepend(bold); }}
    }}
    var first = document.querySelector(".first .say"),
        say = b.querySelector("[data-item=say-this-first]"),
        said = first ? "Say this first: " + first.textContent : "";
    say.hidden = !first || !!d.querySelector('[data-step-type="user_message"]');
    if (first && say.textContent !== said) say.textContent = said;
  }}
  var hand = 0, last = 0, wait = null, away = false, pending = null, seen = 0;
  new w.MutationObserver(function () {{ clearTimeout(wait); wait = setTimeout(sync, 100); }})
    .observe(d.body, {{ childList: true, subtree: true }});
  ["wheel", "touchmove", "keydown"].forEach(function (k) {{
    d.addEventListener(k, function (e) {{
      if (e.target.id !== "chat-input") hand = Date.now();
      else if (e.key === "Enter" && !e.shiftKey) {{ away = false; pending = null; }}
    }}, true);
  }});
  d.addEventListener("keydown", esc);  // t637
  /* t654: every way into the graph from an answer carries 643's mark (a tap's "Here it is", a
   * chain or view link) for the press alone, so a copied link never carries it */
  function marked(e) {{
    var a = e.target.closest && e.target.closest('a[href*="graph-live"]'),
        was = a && a.getAttribute("href"), at = was ? was.indexOf("#") : -1;
    if (!a || (e.type === "auxclick" && e.button !== 1) ||  // a middle press; never the menu's
        (at >= 0 && was.slice(at + 1).split("&").indexOf("from-chat") >= 0)) return;
    a.setAttribute("href", was + (at >= 0 ? "&" : "#") + "from-chat");
    setTimeout(function () {{ a.setAttribute("href", was); }}, 0);
  }}
  d.addEventListener("click", marked, true);
  d.addEventListener("auxclick", marked, true);
  d.addEventListener("click", function (e) {{
    if (e.target.closest && e.target.closest("#chat-submit")) {{ away = false; pending = null; }}
  }}, true);
  d.addEventListener("scroll", function (e) {{
    var s = e.target, fab = document.querySelector(".fab");
    if (!s.classList || !s.classList.contains("overflow-y-auto") || s !== list()) return;
    var mine = Date.now() - hand < 800, end = s.scrollHeight - s.scrollTop - s.clientHeight < 80;
    if (s.scrollTop < 40 || s.scrollTop < last - 4) fab.classList.remove("tucked");
    else if (s.scrollTop > last + 4 && mine) fab.classList.add("tucked");
    if (mine) away = !end;
    if (pending && end) {{ pending = null; away = false; sync(); }}
    last = s.scrollTop;
  }}, true);
  w.addEventListener("resize", sync);
  dressed = sync;
  sync();
}}
</script>
</body></html>
"""

#: t291: the frame the files page and "Your documents" share: nemo's header with "← Chat", an
#: eyebrow, a title and the list. Direction C of nemo_design's pick, on the phone and the laptop.
FRAME = _HEAD + """<title>nemo · {title}</title>
{harbour}<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; font: 16px/1.55 var(--font-body); color: var(--color-slate);
        background: var(--color-harbour-grey); -webkit-text-size-adjust: 100%; }}
:focus-visible {{ outline: 3px solid var(--color-amber); outline-offset: 2px; }}
.top {{ display: flex; align-items: center; gap: 10px; padding: 6px 20px;
        border-bottom: 1px solid var(--color-hairline); }}
.wm {{ font: 700 18px/1 var(--font-display); letter-spacing: -.03em; color: var(--color-navy);
       white-space: nowrap; }}
.wm b {{ color: var(--color-amber-wordmark); }}
.prod {{ font: 500 18px/1 var(--font-display); letter-spacing: -.02em; color: var(--color-navy); }}
.where {{ color: var(--color-muted); margin-left: 12px; }}
.back {{ margin-left: auto; color: var(--color-navy); text-decoration: none; font-weight: 500;
         white-space: nowrap; display: inline-flex; align-items: center; min-height: 44px; }}
main {{ max-width: 46rem; margin: 0 auto; padding: 24px 20px 40px; }}
.eb, h2 {{ font: 500 12px/1.2 var(--font-mono); letter-spacing: .12em; text-transform: uppercase;
           color: var(--color-muted); margin: 0 0 12px; }}
h2 {{ margin-top: 28px; }}
h1 {{ font: 500 28px/1.2 var(--font-display); letter-spacing: -.02em; color: var(--color-navy);
      margin: 0 0 8px; }}
ul {{ list-style: none; margin: 0; padding: 0; }}
li {{ padding: 8px 0; border-top: 1px solid var(--color-hairline); }}
li a {{ color: var(--color-navy); text-decoration: none; }}
li a:hover, .back:hover {{ color: var(--color-rust); }}
.files a::after {{ content: " \\2192"; color: var(--color-muted); }}
.docs a::after {{ content: " \\2197"; color: var(--color-muted); }}
.docs a:not([target])::after {{ content: " \\2192"; }}
li small, .hint {{ color: var(--color-muted); font-size: 14px; }}
li:has(> a) {{ padding: 0; }}
li > a {{ display: block; padding: 10px 0; min-height: 44px; }}
.hint a {{ display: inline-block; min-height: 44px; line-height: 44px; color: var(--color-muted); }}
/* t638: the reader, a room file drawn in this frame */
.eb .up {{ display: inline-flex; align-items: center; min-height: 44px; color: var(--color-navy);
          text-decoration: none; font: 500 15px var(--font-body); letter-spacing: 0;
          text-transform: none; }}
.eb .up:hover {{ color: var(--color-rust); }}
.doc {{ overflow-wrap: anywhere; }}
.doc h2 {{ font: 500 20px/1.3 var(--font-display); letter-spacing: -.01em; text-transform: none;
          color: var(--color-navy); margin: 28px 0 8px; }}
.doc h3, .doc h4 {{ font: 600 16px/1.4 var(--font-body); color: var(--color-navy);
                    margin: 20px 0 4px; }}
.doc p, .doc blockquote {{ margin: 0 0 12px; }}
.doc blockquote {{ color: var(--color-muted); font-size: 14px; }}
.doc hr {{ border: 0; border-top: 1px solid var(--color-hairline); margin: 20px 0; }}
.doc ul.md {{ list-style: disc; padding-left: 20px; margin: 0 0 12px; }}
.doc ol.md {{ padding-left: 24px; margin: 0 0 12px; }}
.doc .md li {{ border: 0; padding: 2px 0; }}
.doc code {{ font: 14px var(--font-mono); }}
/* a table slides sideways in its own box, a shade at an edge with more table behind it: the white
   covers move with the rows (local), the shades stay at the box's edges (scroll); no script */
.tbl {{ overflow-x: auto; margin: 0 0 16px; border: 1px solid var(--color-hairline);
        border-radius: var(--radius-cards, 8px); background-color: var(--color-white);
        background-image: linear-gradient(to right, var(--color-white) 30%, transparent),
          linear-gradient(to left, var(--color-white) 30%, transparent),
          linear-gradient(to right, var(--color-hairline), transparent),
          linear-gradient(to left, var(--color-hairline), transparent);
        background-position: left, right, left, right; background-repeat: no-repeat;
        background-size: 40px 100%, 40px 100%, 16px 100%, 16px 100%;
        background-attachment: local, local, scroll, scroll; }}
.tbl table {{ border-collapse: collapse; font-size: 14px; line-height: 1.45; min-width: 100%; }}
.tbl th, .tbl td {{ text-align: left; vertical-align: top; padding: 8px 12px;
                    border-top: 1px solid var(--color-hairline); min-width: 8rem; }}
.tbl th {{ border-top: 0; color: var(--color-navy); font-weight: 600;
           background: var(--color-harbour-grey); }}
pre.json {{ white-space: pre-wrap; overflow-wrap: anywhere; font: 13px/1.5 var(--font-mono); }}
@media (max-width: 30rem) {{ .where {{ margin-left: 0; }} .top {{ flex-wrap: wrap; }} }}
</style></head>
<body>
{top}
<main>
<p class="eb">{eyebrow}</p>
<h1>{heading}</h1>
{body}<p class="hint">{hint}</p>
</main>
</body></html>
"""

#: t259: the meeting slides, one `.blatt` sheet per slide and one sheet per printed page (the
#: estate's html-artefact checker counts them). Sizes are the deck's five steps
#: (`bc-consulting/praesentation.html`), never a new one; the page count is an output.
SLIDES = Template(_HEAD + """<title>nemo · slides for the BIA meeting</title>
$harbour<style>
:root { --sans: var(--font-body);
        --t-gross: 1.25rem; --t-titel: 1.05rem; --t-text: 0.92rem;
        --t-klein: 0.8rem; --t-label: 0.7rem; }
@page { size: A4 landscape; margin: 12mm; }
* { box-sizing: border-box; }
body { margin: 0; font: var(--t-text)/1.5 var(--sans); color: var(--color-navy);
       background: var(--color-harbour-grey); -webkit-text-size-adjust: 100%; }
main { padding: 1rem; }
.blatt { max-width: 60rem; margin: 0 auto 1rem; background: var(--color-white);
         border: 1px solid var(--color-hairline);
         border-radius: 14px; overflow: hidden; break-inside: avoid; break-after: page; }
.blatt:last-child { break-after: auto; }
/* t293: no navy fill. The band is the slide's white head over a hairline, as the frame is. */
.band { color: var(--color-navy); padding: 0.6rem 1.25rem;
        border-bottom: 1px solid var(--color-hairline);
        font: 700 var(--t-klein) var(--font-display); letter-spacing: -.01em; }
.band b { color: var(--color-amber-wordmark); font-weight: 700; }
.body { padding: 1.25rem 1.25rem 1.5rem; }
h1 { font: 500 var(--t-gross)/1.3 var(--font-display); margin: 0 0 0.9rem; }
.lead { font-size: var(--t-titel); max-width: 44rem; margin: 0; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 0.45rem 0.5rem;
         border-bottom: 1px solid var(--color-hairline); }
thead th { font-size: var(--t-klein); font-weight: 500; color: var(--color-slate); }
tbody th { font-weight: 400; }
tbody th small { display: block; font-size: var(--t-label); color: var(--color-slate); }
td { white-space: nowrap; }
td[colspan] { white-space: normal; color: var(--color-slate); }
@media print {
  body, main { padding: 0; background: var(--color-white); }
  .blatt { max-width: none; margin: 0; border: 0; border-radius: 0; }
}
</style></head>
<body>
<main>
<section class="blatt" data-slide="what">
<div class="band">AI4<b>BCM</b> · BIA meeting · $company</div>
<div class="body"><h1>What is BCM</h1>
<p class="lead">$what</p></div>
</section>
<section class="blatt" data-slide="results">
<div class="band">AI4<b>BCM</b> · BIA meeting · $company</div>
<div class="body"><h1>Last year&#x27;s BIA results</h1>
$results</div>
</section>
<section class="blatt" data-slide="goal">
<div class="band">AI4<b>BCM</b> · BIA meeting · $company</div>
<div class="body"><h1>Today&#x27;s goal</h1>
<p class="lead">$goal</p></div>
</section>
</main>
</body></html>
""")

#: t260: the re-interview sheet, HTML that prints (A4 portrait), in the workspace's token block.
SHEET = Template(_HEAD + """<title>nemo · re-interview sheet</title>
$harbour<style>
* { box-sizing: border-box; }
@page { size: A4; margin: 12mm; }
body { margin: 0; font: 0.92rem/1.5 var(--font-body);
       color: var(--color-navy); background: var(--color-white); -webkit-text-size-adjust: 100%; }
main { margin: 0 auto; padding: 1rem; max-width: 60rem; }
/* t293: no navy fill. The band is the sheet's white head over a hairline, as the frame is. */
.band { color: var(--color-navy); padding: 0.6rem 0; border-bottom: 1px solid var(--color-hairline);
        font: 700 0.8rem var(--font-display); letter-spacing: -.01em; }
.band b { color: var(--color-amber-wordmark); font-weight: 700; }
h1 { font: 500 1.25rem/1.3 var(--font-display); margin: 1rem 0 0.2rem; }
h2 { font: 500 1.05rem var(--font-display); margin: 0 0 0.6rem; }
h3 { font: 500 0.92rem var(--font-display); margin: 1rem 0 0.3rem; }
section { border-top: 1px solid var(--color-hairline); padding: 1rem 0; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 0.35rem 0.45rem;
         border-bottom: 1px solid var(--color-hairline); }
thead th { font-size: 0.8rem; font-weight: 500; color: var(--color-slate); }
tbody th { font-weight: 400; }
/* t293: a single point of failure is the failure pair, rust on peach, as the failed resource is */
tr[data-spof] { background: var(--color-peach); }
tr[data-spof] td:last-child { font-weight: 600; color: var(--color-rust); }
small, .source { color: var(--color-slate); }
.answer { min-height: 6rem; border: 1px solid var(--color-hairline); border-radius: 8px; }
@media print { main { padding: 0; } }
</style></head>
<body>
<main>
<div class="band">AI4<b>BCM</b> · Re-interview sheet · $company</div>
<h1>$name</h1>
<p class="source">Last year&#x27;s figures $source</p>
$focus
<section data-section="figures"><h2>Last year&#x27;s figures</h2>
$figures
$changed</section>
<section data-section="grid"><h2>Last year&#x27;s impact grid</h2>
$grid
$changed</section>
<section data-section="resources"><h2>Resources and single points of failure</h2>
$resources
$changed</section>
</main>
</body></html>
""")
#: t478: the stage map, in the process map's type and Harbour's colours; the stage an answer's label
#: opened it on gets an amber rule
STAGE_MAP_PAGE = _HEAD + """<title>nemo · stage map</title>
{harbour}<style>
body {{ font: 16px/1.5 var(--font-body); color: var(--color-slate); background: var(--color-white);
        margin: 0; -webkit-text-size-adjust: 100%; }}
main {{ max-width: 46rem; margin: 0 auto; padding: 1.25rem 1rem 2rem; }}
h1 {{ font: 500 1.6rem/1.2 var(--font-display); color: var(--color-navy); margin: .5rem 0 .75rem; }}
h2 {{ font: 500 12px/1.2 var(--font-mono); letter-spacing: .12em; text-transform: uppercase;
      color: var(--color-navy); margin: 0 0 .25rem; }}
p {{ color: var(--color-muted); font-size: .9rem; margin: 0 0 .5rem; }}
section {{ border-left: 3px solid var(--color-hairline); padding: .25rem 0 .25rem .9rem;
           margin: 1.25rem 0; scroll-margin-top: 1rem; }}
section:target {{ border-left-color: var(--color-amber-wordmark); }}
ul {{ list-style: none; margin: 0; padding: 0; }}
li {{ font-size: 15px; margin: .35rem 0; }}
li b {{ font: 500 13px/1 var(--font-mono); color: var(--color-navy); margin-right: .4rem; }}
</style></head>
<body>
<main>
<h1>The five stages of a BIA</h1>
<p>Every answer says its stage. The workshop prompts sit in the stage they belong to. Read-only.</p>
{sections}
</main>
</body></html>
"""
