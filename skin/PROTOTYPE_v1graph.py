"""PROTOTYPE, throwaway (2026-09-17). Draw v1's dependency graph (bia-workflow/dep_graph.py, the
page served under /demo/graph/ in version 1) for each prototype room, from that room's register and
the BIA record nemo wrote. v1's code is imported read-only; nothing in bia-workflow or nemo changes.

    python PROTOTYPE_v1graph.py          # every room that has an output/<activity>/bia-record.json

Writes <room>/public/graph-v1/marschkamp/index.html + evidence.json.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any

import needs

from nemo import record as nemo_record
from nemo import room_store, walk

import PROTOTYPE_core as core
import PROTOTYPE_words as words
from PROTOTYPE_clocks import BAKEOFF

#: v1's graph module, and ONLY that module, from the bia-workflow worktree holding tickets 146, 149
#: and 150
#: (graph-groups/150 at defcdc8): the grouped view, columns = dependency levels, each card counting
#: what stands on it. Pinned by bytes in `external-pins`. Ticket 147 replaces this with the merged
#: checkout. The directory is the home's work/bia-workflow-g150 unless NEMO_DEP_GRAPH names another
#: (ticket 587: the same setting test_live_guard reads).
DEP_GRAPH_PATH = Path(
    os.environ.get("NEMO_DEP_GRAPH", Path.home() / "work/bia-workflow-g150")) / "dep_graph.py"
_spec = importlib.util.spec_from_file_location("dep_graph", DEP_GRAPH_PATH)
assert _spec and _spec.loader
dep_graph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dep_graph)

#: Which platform frames a system is drawn in (tickets 146/147, as 14_nemo_check accepted them). The
#: first
#: four are the vendor in the asset's own name; the last two were grouped for the demo, and the page
#: says so.
#: Applied to the drawing only: the register on disk is not changed.
PLATFORMS = {
    "Microsoft": ("microsoft-365", "microsoft-teams", "sharepoint-online", "active-directory"),
    "Atlassian": ("jira", "jira-service-management"),
    "Cisco": ("cisco-call-manager", "cisco-telephony"),
    "SAP": ("sap-s4hana-finance",),
    "HR systems": (
        "hr-master-data-system",
        "payroll-system",
        "time-recording-system",
        "hr-finance-interface",
    ),
    "Identity and access": ("central-authorisation-system", "keycloak"),
}
AUTHORED = frozenset({"HR systems", "Identity and access"})


def with_platforms(register: dict[str, Any]) -> dict[str, Any]:
    """The register as the drawing reads it: each listed system carries its platform, where it has
    none."""
    for platform, ids in PLATFORMS.items():
        for asset_id in ids:
            asset = register.get(asset_id)
            if isinstance(asset, dict) and not asset.get("platform"):
                asset["platform"] = platform
                asset["platform_authored"] = platform in AUTHORED
    return register

#: Ticket 254's "What if it fails?" click mode: nemo's own script and style, inlined after g150's
#: graph.js and graph.css (both pinned, never edited) so every drawn page carries it.
HERE = Path(__file__).resolve().parent
FAILURE_JS = HERE / "failure_click.js"
FAILURE_CSS = HERE / "failure_click.css"
#: t287: the pinned Harbour colours nemo's own style and marks name, inlined before them: the drawn
#: page is a file in the room that more than one server serves, so it links no stylesheet.
HARBOUR_COLOURS = HERE / "harbour/tokens/colors.css"


def with_failure_click(page: str) -> str:
    """The page with Harbour's colours and the failure mode's style closing its head and its script
    closing its body."""
    head, end, rest = page.partition("</head>")
    body, close, tail = rest.rpartition("</body>")
    style = HARBOUR_COLOURS.read_text(encoding="utf-8") + FAILURE_CSS.read_text(encoding="utf-8")
    return (f"{head}<style>{style}</style>\n{end}{body}"
            f"<script>{FAILURE_JS.read_text(encoding='utf-8')}</script>\n{close}{tail}")


#: Ticket 268: g150 draws an activity card's second line "BIA activity · act:<name>", cut short at
#: 38 characters; the first line already names the activity, so the internal id goes.
ACT_SUB = re.compile(r'(<text class="sub" [^>]*>)BIA activity · [^<]*(</text>)')


def without_act_ids(page: str) -> str:
    """The page with each activity card's second line reading "BIA activity": visible text only,
    every id and attribute as g150 drew it."""
    return ACT_SUB.sub(r"\1BIA activity\2", page)


#: Ticket 270: the room's company profile names each department against its code, one table row
#: each ("| Human resources | `hr` |").
PROFILE = "01_Organisation/company-profile.md"
SLUG_ROW = re.compile(r"^\|\s*([^|`]+?)\s*\|\s*`([^`|]+)`\s*\|\s*$", re.M)
CARD = re.compile(r'<g class="node (\w+)[^"]*" data-id="([^"]*)".*?</g>', re.S)
CARD_SUB = re.compile(r'(<text class="sub" [^>]*>)[^<]*(</text>)')


def with_dept_names(graph: dict[str, Any], room: Path) -> dict[str, Any]:
    """Every card with a department carries `dept_name`: the name the room's company profile
    gives its code, else the code in capitals. Data for the card face and failure_click.js."""
    path = room / PROFILE
    names = {code: name for name, code in SLUG_ROW.findall(
        path.read_text(encoding="utf-8") if path.is_file() else "")}
    for n in graph["nodes"]:
        if n.get("dept"):
            n["dept_name"] = names.get(n["dept"], str(n["dept"]).upper())
    return graph


def with_owner_words(graph: dict[str, Any], register: dict[str, Any]) -> dict[str, Any]:
    """Ticket 274: every resource card carries its register row's `owner_evidence` and
    `owner_gap` as written, for failure_click.js's Owner row. Data only; g150 reads neither."""
    for n in graph["nodes"]:
        row = register.get(n["id"]) if n["kind"] == "asset" else None
        for key in ("owner_evidence", "owner_gap"):
            if isinstance(row, dict) and row.get(key):
                n[key] = row[key]
    return graph


def without_codes(page: str, graph: dict[str, Any]) -> str:
    """The page with no id or department code on a card's second line: a resource's reads what
    follows its id, a process's names its department. Visible text only, as `without_act_ids`."""
    by_id = {n["id"]: n for n in graph["nodes"]}

    def sub(card: re.Match[str]) -> str:
        n = by_id.get(html.unescape(card[2]), {})
        if card[1] == "asset":
            crit = (dep_graph._crit_class(n.get("criticality"))
                    if n.get("criticality") is not None else "unrated")
            line = " · ".join([*([n["asset_type"]] if n.get("asset_type") else []), crit])
        elif card[1] == "process" and n.get("dept_name"):
            line = f"{n['dept_name']} · activity"
        else:
            return card[0]
        text = dep_graph._esc(dep_graph._trunc(line, 38))
        return CARD_SUB.sub(lambda m: m[1] + text + m[2], card[0], count=1)

    return CARD.sub(sub, page)


#: Ticket 258: a signed process's mark, on its card's bottom line. t287: Harbour has no green for a
#: thing finished, and rust is the failure mode's alarm, so the mark is navy, set bold.
BIA_DONE = "BIA done"
BIA_DONE_CSS = ".node text.bia-done { fill: var(--color-navy); font-weight: 600; }"


def done_marks(room: Path) -> dict[str, str]:
    """Each CLOSED process's mark by its slug, every run read from this room's own folder. A run
    closed before `signed_on` was kept reads "BIA done" alone: a file's mtime is no signing date."""
    marks = {}
    for path in sorted(room_store.jailed_path(room, walk.RUNS).glob("*.json")):
        try:
            run = room_store.read_record(room, f"{walk.RUNS}/{path.name}") or {}
        except room_store.PathRefused:
            continue  # a run file that leads out of the room is not this room's
        if run.get(nemo_record.STATUS) == walk.CLOSED:
            marks[path.stem] = " · ".join(
                [BIA_DONE, *([run[walk.SIGNED_ON]] if run.get(walk.SIGNED_ON) else [])])
    return marks


def with_signature(graph: dict[str, Any], room: Path, process: str | None) -> dict[str, Any]:
    """The graph with every card of a CLOSED process marked: the drawn record's activity cards
    are `process`'s, a register consumer card is its activity's (ticket 258, 258b)."""
    marks = done_marks(room)
    for n in graph["nodes"]:
        slug = (process if n["kind"] == "activity"
                else Path(walk.run_file(n.get("activity") or "")).stem if n["kind"] == "process"
                else None)
        if slug in marks:
            # g150 draws a People line and `lines` on the same bottom line, so People joins them;
            # its fold band draws every consumer card at one height, so there the mark replaces it
            people = n.pop("people", None)
            n["lines"] = [("bia-done", marks[slug]),
                          *([("people", "People: " + ", ".join(people))]
                            if people and n["kind"] == "activity" else [])]
    return graph


def with_chain(graph: dict[str, Any], room: Path, process: str | None) -> dict[str, Any]:
    """Ticket 262: every process card, and the drawn record's activity cards (`process`'s), carry
    `flows_to`: the process cards the room's process map puts downstream of it, followed to the
    end. Read through 261's reader alone; a row with no Downstream column (HR, IT) leads nowhere,
    and a card the map does not name carries nothing. Data for failure_click.js, never an edge."""
    rows = core.process_map_rows(room)
    down = {r.name: r.downstream or () for r in rows}
    cards: dict[str, list[str]] = {}
    for n in graph["nodes"]:
        if n["kind"] == "process":
            cards.setdefault(n.get("activity") or "", []).append(n["id"])
    own = next((r.name for r in rows if r.slug == process), None)
    for n in graph["nodes"]:
        start = (n.get("activity") if n["kind"] == "process"
                 else own if n["kind"] == "activity" else None)
        if ids := [i for name in needs.followed(down, start) for i in cards.get(name, [])]:
            n["flows_to"] = ids
    return graph


#: the room-sheet key draw reads the drafts under: the phone's default (`draft_for` falls back
#: through the others)
SHEET_MODEL = "glm"


def with_needs(graph: dict[str, Any], room: Path) -> dict[str, Any]:
    """Ticket 263: every resource card some activity depends on carries `needs`, how soon it is
    needed back and its flags (`core.resource_needs`), for failure_click.js's panel. Data only."""
    if not (room / walk.METHOD).is_file():  # a room with no method has no room sheet, no MTPD
        return graph
    found = core.resource_needs(room, core.room_sheet(room, SHEET_MODEL))
    for n in graph["nodes"]:
        if n["id"] in found:
            n["needs"] = found[n["id"]]
    return graph


ROOM_SETS = [Path("/home/user/work/nemo/skin/run/rooms"),
             BAKEOFF / "rooms"]  # t295: the bakeoff root, never main's tree
COMPANY = "marschkamp"


def draw(room: Path, record: dict[str, Any] | None = None, at: str | None = None) -> Path | None:
    """The page for this room's record — or, with `record`, for one not yet accepted.

    The stage-4 card offers the graph link as the way to "read it whole", and the record file does
    not exist until the manager taps accept. Drawn from the card's own proposal, the link works at
    the moment it is offered instead of 404ing; `sign` redraws it from the saved record after.
    `at` is that record's room-relative path (`walk.record_file`, one per activity since t235);
    without it, the record landed last in the room.
    """
    record_file = room / at if at else _landed_last(room)
    if record is None and not record_file.exists():
        return None
    reg_text = (room / "03_Dependencies/dependency-register.json").read_text(encoding="utf-8")
    rec_text = (json.dumps(record, ensure_ascii=False) if record is not None
                else record_file.read_text(encoding="utf-8"))
    reg = with_platforms(json.loads(reg_text))
    graph = with_needs(with_chain(dep_graph.collapse_processes(dep_graph.layout(with_signature(
        dep_graph.group_view(dep_graph.build_graph(reg, json.loads(rec_text)), reg), room,
        None if record is not None else record_file.parent.name))), room,
        record_file.parent.name if record is None or at else None), room)
    graph = with_owner_words(with_dept_names(graph, room), reg)
    graph = words.functions_only_in(graph, room)  # t418 (ADR-0051): every person by function
    out = room / "public/graph-v1" / COMPANY
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    evidence = {"register": {"sha": hashlib.sha256(reg_text.encode()).hexdigest()},
                "record": {"sha": hashlib.sha256(rec_text.encode()).hexdigest()}}
    page = without_codes(without_act_ids(with_failure_click(
        dep_graph.render_page(graph, COMPANY, evidence, generated_at=now))), graph)
    page = page.replace("</head>", f"<style>{BIA_DONE_CSS}</style>\n</head>", 1)
    (out / "index.html").write_text(page, encoding="utf-8")
    acts = sum(1 for n in graph["nodes"] if n["kind"] == "activity")
    (out / "evidence.json").write_text(
        json.dumps(
            {
                **evidence,
                "page": {
                    "activity_count": acts,
                    "generated_at": now,
                    # t298: the read-only site's own path (PROTOTYPE_site), on whichever host
                    "url": f"/graph/{room.name}/{COMPANY}/",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out / "index.html"


def _landed_last(room: Path) -> Path:
    """The room's newest BIA record (t235: one per activity, under output/<activity>/)."""
    landed = sorted(room.glob("output/*/bia-record.json"), key=lambda p: p.stat().st_mtime_ns)
    return landed[-1] if landed else room / "output" / "no-record"


if __name__ == "__main__":
    for base in ROOM_SETS:
        for room in sorted(p for p in base.glob("*") if p.is_dir()):  # a missing set is empty
            page = draw(room)
            if page:
                print(room.name, page.stat().st_size, "bytes")
