"""Ticket 292: the live graph page with nemo beside it, the prototype the owner approved, on the
room's own register.

The owner, 2026-10-02T23:21:18Z (nemo_design's session e44eeb9b): *"lets make a live prototype, so I
can see teh final results fully working including nemo"*. The behaviour is nemo_design's
`~/work/nemo-builds/design-2026-10-02/prototype/PROTOTYPE-graph-chat.html`, ported as it is into
`live_graph.html`; what changes is where its data and its answers come from:

- **Data** (`data`): g150's grouped graph built from the room's register, as stage 4 draws it
  (`PROTOTYPE_v1graph`), in memory, never written. The BIA activity in the middle is the room's
  newest record's, else the walk under way, else the prototype's, IT helpdesk and support. A room
  with no record gets a stand-in holding only what the register and last year's record say: its
  needs are the register rows that name it as a consumer, its figures last year's.
- **nemo** (`ask`): a real turn of the room's chat (`core.Session`, the turn file through
  `core.record_turn` as the chat writes it). The cards added from the graph ride in the turn's own
  text, so the turn file's shape is unchanged. What it lights is never the model's to say (M13):
  what goes down with the cards added is the register's chain (`affected`), as g150's failure
  click draws it; the cards nemo's answer names only get a weaker mark (`named`). SHARED (new
  surface): name it in the commit.

    <root>/w/<code>/graph-live   the page, served by the workspace (GET, read-only)
    <root>/ask/<code>            the question, POSTed as JSON by the page (the app's route)
"""
from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import merge_table
import workspace

from nemo import impact, walk
from nemo import method as methods
from nemo.method import SEVERITY_SCALE
from nemo.room_store import PathRefused, read_record

import PROTOTYPE_core as core
import PROTOTYPE_lanes as lanes
import PROTOTYPE_v1graph as v1graph
import PROTOTYPE_words as words
import stage_door

HERE = Path(__file__).resolve().parent
TEMPLATE = (HERE / "live_graph.html").read_text(encoding="utf-8")
#: The prototype's BIA activity, the middle column of a room that walks nothing yet.
DEFAULT_ACTIVITY = "helpdesk-and-support"
#: ADR-0034: how an authored description opens; the card shows the words after it, marked.
MARK = merge_table.MARK
ACT = "act"
#: A process card's department where the register names none: the process map's core processes.
#: The card names a department by its code, as the prototype does ("IT · USES 6").
CORE = "core"
Log = Callable[[str, Any], None]
#: Each room's session on this page, and the lock that keeps its turns one at a time.
Sessions = dict[Path, tuple[core.Session, threading.Lock]]


def room_chat(rooms: Path, seed: Path, code: str, model: str, stamped: str | None) -> Path | None:
    """The room's chat folder, minted from the seed on its first question as the chat's own first
    turn mints it; None for a room the workspace would not serve."""
    if workspace._folder(rooms, code, model, stamped) is None:
        return None
    walk.mint_room(seed, rooms, f"{code}-{model}")
    chat = rooms / f"{code}-{model}"
    return chat if chat.is_dir() else None


own_words = merge_table.own_words


def _figure(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("value")
    return None if value in (None, "") else str(value)


def _walked(folder: Path) -> str | None:
    """The process the room's walk has moved furthest on, None where no walk has started."""
    runs = []
    for run in (folder / walk.RUNS).glob("*.json"):
        try:
            saved = read_record(folder, f"{walk.RUNS}/{run.name}")
        except (OSError, ValueError, PathRefused):
            continue
        if done := walk.stages_done(saved):
            runs.append((done, run.stat().st_mtime_ns, run.stem))
    return max(runs)[2] if runs else None


def _purpose(folder: Path, slug: str) -> str:
    """The first sentence of the process map's own paragraph on the activity."""
    name = core.map_name(folder, slug)
    path = folder / core.PROCESS_MAP
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    found = re.search(rf"^\*\*[\d.]+ {re.escape(name)}\.\*\* (.+?\.)(?:\s|$)", text, re.M)
    return found[1] if found else ""


def _stand_in(folder: Path, slug: str, register: dict[str, Any]) -> dict[str, Any]:
    """A record holding only what the room's files say of an activity no record covers yet."""
    rows = [(k, c) for k, a in register.items() if isinstance(a, dict)
            for c in a.get("consumers") or [] if c.get("department") == slug]
    figures = core.last_year(folder, slug).get("figures") or {}
    return {"activities": [{"name": core.map_name(folder, slug),
                            "dept": next((c.get("dept") for _, c in rows), None),
                            "dependencies": [k for k, _ in rows],
                            "mtpd": figures.get("MTPD"), "recovery_target": figures.get("RTO")}]}


def _activity(folder: Path, register: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
    """The BIA activity, the record it is drawn from, and whether that is a stand-in."""
    records = sorted(folder.glob("output/*/bia-record.json"), key=lambda p: p.stat().st_mtime_ns)
    if records:
        return records[-1].parent.name, json.loads(records[-1].read_text(encoding="utf-8")), False
    slug = _walked(folder) or DEFAULT_ACTIVITY
    return slug, _stand_in(folder, slug, register), True


def _graph(folder: Path, register: dict[str, Any], slug: str,
           record: dict[str, Any]) -> dict[str, Any]:
    """g150's grouped graph, as `PROTOTYPE_v1graph.draw` builds it, in memory."""
    dg = v1graph.dep_graph
    graph = dg.collapse_processes(dg.layout(dg.group_view(dg.build_graph(register, record),
                                                          register)))
    return v1graph.with_chain(graph, folder, slug)


def _stand(lines: Iterable[Any]) -> int:
    said = next((text for kind, text in lines if kind == "stand"), "")
    return int(said.split()[0]) if said[:1].isdigit() else 0


def _asset(n: dict[str, Any], row: dict[str, Any], slug: str) -> dict[str, Any]:
    use: dict[str, Any] = next((c for c in row.get("consumers") or []
                                if c.get("department") == slug), {})
    return {"name": n["name"], "depth": n["col"], "type": n.get("asset_type"),
            "desc": own_words(row),
            "authored": row.get("authored") is True or MARK in str(row.get("description") or ""),
            "owner": row.get("owner_name"), "gap": row.get("owner_gap"),
            "added": bool(row.get(walk.ADDED_IN_CHAT)),
            "rto": _figure(row.get("rto")), "stand": _stand(n.get("lines") or []),
            "need": use.get("need"), "work": use.get("workaround"),
            "needed": _figure(use.get("rto")), "targets": _targets(row),
            "authoredUses": [str(c.get("activity") or c.get("department"))
                             for c in row.get("consumers") or [] if _authored(c, "need")]}


def _targets(row: dict[str, Any]) -> list[list[str]]:
    """Ticket 307: each activity's own target for the resource, as its register row gives it,
    in the register's order; nothing is chosen or ranked."""
    return [[str(c.get("activity") or c.get("department")), f]
            for c in row.get("consumers") or [] if (f := _figure(c.get("rto")))]


_authored = merge_table.authored
_marks = merge_table.marks


def _only_marks(register: dict[str, Any]) -> set[str]:
    """The firms and machines that are only a mark: they serve or back up a resource, and no
    activity uses them and no resource stands on them (the emergency generator, Frostmark)."""
    stood_on = {d for a in register.values() if isinstance(a, dict)
                for d in a.get("depends_on") or []}
    return {k for k, a in register.items() if isinstance(a, dict)
            and (a.get("backup_for") or a.get("service_for"))
            and not a.get("consumers") and k not in stood_on}


# ── ticket 326: G2, the simplified laptop graph for one BIA (1_nemo_design's spec §9), cut by 336 ─
#: The boxes and their merges are the one company-wide table's (`merge_table`, 336);
#: here are only the page's own parts: the handoffs, the BIA card's finding.
COLUMNS = merge_table.COLUMNS
SUPPLIER = merge_table.SUPPLIER
RUNS_WITHOUT_RULE = merge_table.RUNS_WITHOUT_RULE
SINGLE = merge_table.SINGLE
FIRM = merge_table.FIRM
PROFILE = "01_Organisation/company-profile.md"
#: the reviewer round 7, his "From existing text, no new item": the flow ends at the customers the company
#: profile names ("It supplies retail chains, bulk consumers and restaurants in …").
SUPPLIES = re.compile(r"\bIt supplies ([^.]+?) in the\b")


def _uses(register: dict[str, Any], slug: str) -> dict[str, dict[str, Any]]:
    """The activity's own consumer row on each resource it uses, in the register's order."""
    return {k: c for k, a in register.items() if isinstance(a, dict)
            for c in a.get("consumers") or [] if c.get("department") == slug}


_beneath = merge_table.beneath


def _customers(folder: Path) -> str | None:
    """"Customers (retail chains, bulk consumers, restaurants)", from the company profile's own
    sentence; a pill, never a register item or an edge. None where the profile names none."""
    path = folder / PROFILE
    found = SUPPLIES.search(path.read_text(encoding="utf-8")) if path.is_file() else None
    if not found:
        return None
    parts = re.split(r",\s*|\s+and\s+", " ".join(found[1].split()))
    return f"Customers ({', '.join(parts)})"


def _handoffs(folder: Path, slug: str) -> dict[str, list[dict[str, Any]]]:
    """§9.9: the activity that hands work to this one (above the BIA card) and the one it hands work
    to (below), read from the process map's Upstream and Downstream cells (333's, for the support
    pair), never its prose; the core chain's last stop hands work to the customers."""
    rows = core.process_map_rows(folder)
    here = next((r for r in rows if r.slug == slug), None)
    if here is None:
        return {"up": [], "down": []}
    up: list[dict[str, Any]] = [{"id": f"up:{_slug(n)}", "name": n,
                                 "why": f"hands work to {here.name}"}
          for n in here.upstream or ()]
    down: list[dict[str, Any]] = [{"id": f"down:{_slug(n)}", "name": n,
                                   "why": f"takes work from {here.name}"}
            for n in here.downstream or ()]
    customers = _customers(folder)
    if customers and here.upstream and not here.downstream and here.group == rows[0].group:
        down.append({"id": "down:customers", "name": customers, "customers": True,
                     "why": f"takes the goods from {here.name}"})
    return {"up": up, "down": down}


def _flow(folder: Path, slug: str) -> dict[str, Any]:
    """§9.1: the BIA's place in the process chain, as the process map's upstream and downstream
    say it, to the customers where the core chain ends (Whole company's arrows and pill; 352
    dropped the flow row, and with it "alongside")."""
    rows = core.process_map_rows(folder)
    by_name = {r.name: r for r in rows}
    here = next((r for r in rows if r.slug == slug), None)
    if here is None:
        return {"up": [], "here": core.map_name(folder, slug), "down": [], "customers": None}
    up: list[str] = []
    down: list[str] = []
    for out, step in ((up, "upstream"), (down, "downstream")):
        row = here
        while (nxt := getattr(row, step)) and nxt[0] in by_name and nxt[0] not in out:
            out.append(nxt[0])
            row = by_name[nxt[0]]
    # 336, the reviewer round 7: the core chain ends at the customers
    last = by_name[down[-1]] if down else here
    ends = here.group == rows[0].group and bool(up or down) and not last.downstream
    return {"up": up[::-1], "here": here.name, "down": down,
            "customers": _customers(folder) if ends else None}


def _waiting(folder: Path, register: dict[str, Any]) -> dict[str, list[str]]:
    """372 (spec §12.23): whom each activity's open follow-ups wait on, one name per draft nemo
    writes for it (317: one per named holder and activity, else one per resource), each as the
    draft addresses it (t418: "<position>", ADR-0051; else the owner not yet named, else the
    stored `to`); an activity with none is absent."""
    owners = {str(a.get("name")): str(a.get("owner_name") or "")
              for a in register.values() if isinstance(a, dict)}
    # t482: a referral about the activity itself (t377's, or a conflict left open) as its draft
    # addresses it: the process owner its open discrepancies name (`drafts.follow_up_drafts`)
    owners.update({core.process_name(folder, a): d["holder"] for a in walk.processes(folder)
                   for d in core.discrepancies(folder, a) if d["resource"] is None})
    out: dict[str, dict[str, None]] = {}
    for to, activity, _ in core.follow_up(folder):
        resource = to.removeprefix(walk.REFERRED_TO_SAID.format(resource=""))
        owner = owners.get(resource)
        named = re.fullmatch(r"(.+) \((.+)\)", owner or "")
        shown = (named[1].split(",")[0].strip() if named else to if owner is None  # t418
                 else core.NOT_NAMED.format(resource=resource))
        out.setdefault(activity, {})[shown] = None
    return {a: list(ns) for a, ns in out.items()}


def _rebia(folder: Path, slug: str) -> str | None:
    """§8.6, §9.3: last year's MTPD set against the first horizon its own grid reaches the
    method's intolerability threshold in (impact-criteria.md:48), as the referee derives it."""
    said = _rebia_parts(folder, slug)
    if said is None:
        return None
    mtpd, derived, high = said
    reach = f"reaches {high} at {derived}" if derived != impact.NO_MTPD else f"never reaches {high}"
    return f"re-BIA: MTPD {mtpd}, but the record's own grid {reach}"


def _rebia_face(folder: Path, slug: str) -> str | None:
    """355 (spec §12.9): the card face's re-BIA line, both figures stated, no side taken
    (ADR-0032 d6): "re-BIA: its grid gives MTPD <x>, record <y>"."""
    said = _rebia_parts(folder, slug)
    if said is None:
        return None
    mtpd, derived, _ = said
    grid = f"MTPD {derived}" if derived != impact.NO_MTPD else "no MTPD"
    return f"re-BIA: its grid gives {grid}, record {mtpd}"


def _rebia_parts(folder: Path, slug: str) -> tuple[str, str, str] | None:
    """Last year's MTPD, the one its grid gives, and the method's threshold's label, where they
    differ; None where they agree or a figure is missing."""
    last = core.last_year(folder, core.map_name(folder, slug))
    grid, mtpd = last.get("grid"), (last.get("figures") or {}).get("MTPD")
    if not grid or not mtpd:
        return None
    method = walk._method(folder)
    level = {s.get("label"): s.get("level") for s in method.get(SEVERITY_SCALE) or []}
    worst = impact.worst_case_row({c: {h: level.get(v) for h, v in row["cells"].items()}
                                   for c, row in grid.items()})
    derived = impact.derive_mtpd(worst, method)
    beyond = methods.beyond_horizons(method)
    if (derived == impact.NO_MTPD) if mtpd == beyond else derived == mtpd:
        return None
    high = next((str(label) for label, n in level.items() if n == methods.threshold(method)),
                str(methods.threshold(method)))
    return str(mtpd), str(derived), high


# ── ticket 327: the linkage census, the code half of his consistency and linkage scan ─────────
#: (b): the kinds the method expects of every activity, each the register types it counts (ADR-0034
#: Part E 16c). An "Approval" or a "Communication channel" is none of them: what an approval stands
#: on counts by its own type.
#: 356 F18 (spec §12.18): each kind in the graph's ISO 9001 words.
EXPECTED = {"people": ("Role",), "ICT": ("IT system", "IT infrastructure"),
            "equipment and transport, buildings": ("Equipment and facilities", "Site"),
            "buildings and utilities": ("Utilities",), "external providers": (SUPPLIER,)}
LINKS = ("consumers", "depends_on", "service_for", "backup_for")
A_LINES = f"{core.PRIOR}/resource-dependencies.md"
A_LINE = re.compile(r"^(A\d+)\. (.+)$", re.M)
AUTHORED_FOR = re.compile(r"authored for the pack (A\d+)")
TRANSCRIBED = "prior BIA record "


def unlinked(register: dict[str, Any]) -> list[str]:
    """(a): the items no link reaches: nothing uses one, it stands on nothing, nothing stands on
    it, and no service or backup mark ties it to anything."""
    rows = {k: a for k, a in register.items() if isinstance(a, dict)}
    tied = {d for a in rows.values() for f in LINKS[1:] for d in a.get(f) or []}
    return sorted(str(a.get("name")) for k, a in rows.items()
                  if k not in tied and not any(a.get(f) for f in LINKS))


def missing(register: dict[str, Any], slug: str) -> list[str]:
    """(b): the kinds that nothing the activity uses, or stands on all the way down, is. No record
    in the room says an activity needs none of a kind (the prior records carry no resource
    tables), so none is excused: a gap is said, never filled with a guessed resource."""
    types = {register[k].get("asset_type") for k in _beneath(register, _uses(register, slug))}
    return [kind for kind, of in EXPECTED.items() if not types.intersection(of)]


def _founded_edge(row: dict[str, Any], on: str, lines: dict[str, str]) -> bool:
    """(c): a resource stands on another by the record it was transcribed from, by the A-line its
    quote is word for word, or by his tap in the chat (318)."""
    said: dict[str, Any] = next((e for e in row.get("depends_on_evidence") or []
                                 if e.get("asset_id") == on), {})
    quote = str(said.get("quote") or "")
    return walk.ADDED_IN_CHAT in row or any(
        str(r).startswith(TRANSCRIBED)
        or bool((a := AUTHORED_FOR.fullmatch(str(r))) and quote and quote in lines.get(a[1], ""))
        for r in said.get("evidence_refs") or [])


def _founded_use(row: dict[str, Any], use: dict[str, Any], record: str | None) -> bool:
    """(c): an activity uses a resource by its own record among the resource's evidence
    (transcribed), by an authored mark, or by his tap in the chat."""
    return (walk.ADDED_IN_CHAT in use or walk.ADDED_IN_CHAT in row or _authored(use, "need")
            or (record is not None
                and f"{TRANSCRIBED}{record}" in (row.get("evidence_refs") or [])))


def _unfounded(folder: Path, register: dict[str, Any]) -> list[tuple[str | None, str, str]]:
    """(c): each link nothing founds, as (the activity using, if a use; the resource; the words)."""
    path = folder / A_LINES
    lines = dict(A_LINE.findall(path.read_text(encoding="utf-8"))) if path.is_file() else {}
    records: dict[str, str | None] = {}
    out: list[tuple[str | None, str, str]] = []
    for row in register.values():
        if not isinstance(row, dict):
            continue
        name = str(row.get("name"))
        out += [(None, name, f"{name} → {(register.get(d) or {}).get('name') or d}")
                for d in row.get("depends_on") or [] if not _founded_edge(row, d, lines)]
        for use in row.get("consumers") or []:
            slug = str(use.get("department"))
            if slug not in records:
                records[slug] = core.last_year(folder, core.map_name(folder, slug)).get("record")
            if not _founded_use(row, use, records[slug]):
                out.append((slug, name, f"{use.get('activity')} uses {name}"))
    return out


def census(folder: Path, register: dict[str, Any]) -> dict[str, Any]:
    """Ticket 327: what the map leaves unlinked (a), each process map activity's missing kinds (b),
    and the links nothing founds (c), from the room's register and its A-lines alone (M13)."""
    return {"unlinked": unlinked(register),
            "unfounded": sorted(t for _, _, t in _unfounded(folder, register)),
            "missing": {r.slug: missing(register, r.slug) for r in core.process_map_rows(folder)}}


def _census_line(folder: Path, register: dict[str, Any], slug: str) -> list[str]:
    """The activity's findings in plain words: the kinds it misses, the uses nothing founds."""
    kinds = missing(register, slug)
    bare = sorted(n for s, n, _ in _unfounded(folder, register) if s == slug)
    return ([f"missing: {', '.join(kinds)}"] if kinds else []) + (
        [f"no basis: {', '.join(bare)}"] if bare else [])


#: 408 (34_nemo_check, 2026-10-10): the scopes where a Sites click lights the activities run at its
#: sites; 425: Whole company too, at 1440 and on the phone (his "Light, no line", 2026-10-11)
SITES_LIGHT_ACTIVITIES = ("This BIA", "Whole company")
#: 383 row 17: the Sites tray's why at one site and at more
SITE_WHY, SITES_WHY = "Runs at this site.", "Runs at these sites."


def _sites_why(register: dict[str, Any], boxes: dict[str, Any], slug: str) -> str:
    """359 (§12.11, 10_marschkamp's content ruling e90e6242): the Sites box's own why, the
    activity's `need` on its site rows, each once, in the register's words; never a site's own
    description. "" where the activity has no site row. 383 row 17 (12_marschkamp): "Runs at this
    site." said on more than one of them reads "Runs at these sites." (the tray name counts
    them). Row 27 (12_marschkamp): where the box holds more sites than those rows name, "Runs at
    this site." names them ("Runs at Central HR administration.")."""
    members = (boxes.get(merge_table.SITES_ID) or {}).get("members") or []
    rows = [(k, n) for k in members for c in register[k].get("consumers") or []
            if c.get("department") == slug and (n := own_words({"description": c.get("need")}))]
    needs = [n for _, n in rows]
    here = [str(register[k]["name"]) for k in dict.fromkeys(k for k, n in rows if n == SITE_WHY)]
    named = f"Runs at {', '.join(here[:-1])}{' and ' if len(here) > 1 else ''}{here[-1]}." \
        if here and len(here) < len(members) else ""
    return " ".join(dict.fromkeys(named if n == SITE_WHY and named
                                  else SITES_WHY if n == SITE_WHY and needs.count(n) > 1 else n
                                  for n in needs))


def _site_acts(register: dict[str, Any], boxes: dict[str, Any], slug: str,
               hands: dict[str, list[dict[str, Any]]], rows: list[Any]) -> dict[str, list[str]]:
    """408: each site of This BIA's Sites box with the activities drawn that run there (its site
    row's consumers): the BIA card, a handoff; none while `SITES_LIGHT_ACTIVITIES` leaves This BIA
    out."""
    if "This BIA" not in SITES_LIGHT_ACTIVITIES:
        return {}
    of = {r.name: r.slug for r in rows}
    drawn = {ACT: slug} | {h["id"]: of.get(h["name"]) for side in hands.values() for h in side}
    return {k: [i for i, s in drawn.items() if s in {c.get("department") for c in
                                                     register[k].get("consumers") or []}]
            for k in (boxes.get(merge_table.SITES_ID) or {}).get("members") or []}


def _company_site_acts(register: dict[str, Any], boxes: dict[str, Any]) -> dict[str, list[str]]:
    """425: each site of Whole company's Sites box with the activities run there (its site row's
    consumers, every `merge_table.waived` row left out); none while `SITES_LIGHT_ACTIVITIES` leaves
    Whole company out. The page lights those it draws and draws no line to them."""
    if "Whole company" not in SITES_LIGHT_ACTIVITIES:
        return {}
    return {k: sorted({str(c.get("department")) for c in register[k].get("consumers") or []
                       if not merge_table.waived(register, k, c)})
            for k in (boxes.get(merge_table.SITES_ID) or {}).get("members") or []}


def g2(folder: Path, register: dict[str, Any], slug: str) -> dict[str, Any]:
    """Ticket 326, cut by 336: what the laptop draws for one BIA by the one company-wide table
    (`merge_table.this_bia`, the same rules for every BIA), with the handoffs above and below the
    BIA card and the BIA card's computed re-BIA finding (352: no flow row, so no `flow`)."""
    drawn = merge_table.this_bia(register, slug)
    drawn.pop("box_of")
    names = {r.slug: r.name for r in core.process_map_rows(folder)}
    rows = core.process_map_rows(folder)
    merge_table.name_folds(register, drawn["boxes"], merge_table.company(rows, register)["boxes"])
    for b in drawn["boxes"].values():  # 355 F7: who else needs a shared role, by name
        b["also"] = {r: [names.get(s, s) for s in ss] for r, ss in (b.get("also") or {}).items()}
    _people_column(folder, register, drawn["boxes"], slug, [])  # 467
    left = dict(drawn["notDrawn"])
    hands = _handoffs(folder, slug)
    return {**drawn, "finding": _rebia(folder, slug),
            "rebiaFace": _rebia_face(folder, slug),
            # 355 (§12.12): the record's own lists, in the card's strip and tooltip
            "runsWithout": left.get(RUNS_WITHOUT_RULE, []),
            "stepIn": left.get(merge_table.FIRMS_RULE, []),
            "census": _census_line(folder, register, slug), "handoffs": hands,
            "sitesWhy": _sites_why(register, drawn["boxes"], slug),
            "siteActs": _site_acts(register, drawn["boxes"], slug, hands, rows),
            "actNames": names, "plantWords": {
                p["id"]: merge_table.plant_words(register, drawn["boxes"], p["id"], names, slug)
                for p in drawn["boxes"].get(merge_table.SITES_ID, {}).get("plants", [])},
            "example": next((f"What happens if {FIRM.sub('', b['gapNames'][SINGLE][0])} stops?"
                             for b in drawn["boxes"].values() if SINGLE in b["gaps"]), None)}


# ── ticket 334: the laptop's Whole company, the one table's page (spec §11 as 336 amends it) ──
#: The boxes and the bands are `merge_table.company`'s; here are only what this page
#: lights on a click, the strips' lists, a box's why and fact here, and "Not drawn, and why".
PEOPLE_OF = "people:"
DIFFERS = "Recovery target differs by activity"
UNLINKED_RULE = "Nothing links it to an activity"
TITLED = re.compile(r"^# .*?—\s*(.+)$", re.M)


def _company_name(folder: Path) -> str:
    """The company as its profile's heading names it ("Marschkamp Fleisch")."""
    path = folder / PROFILE
    found = TITLED.search(path.read_text(encoding="utf-8")) if path.is_file() else None
    return found[1].strip() if found else ""


def _needs_it(use: dict[str, Any]) -> bool:
    return not merge_table.RUNS_WITHOUT.search(str(use.get("workaround") or ""))


class _Table:
    """The company-wide table drawn, and where each register item sits in it."""

    def __init__(self, register: dict[str, Any], co: dict[str, Any], core_: list[str]) -> None:
        self.register, self.co, self.boxes = register, co, co["boxes"]
        self.held: dict[str, list[str]] = {}
        for i, b in self.boxes.items():
            for k in b["members"]:
                self.held.setdefault(k, []).append(i)
        self.bia = {s: merge_table.this_bia(register, s)
                    for s in [r for b in co["bands"] for r in b["slugs"]] + core_}
        self.box_of = {s: b["box_of"] for s, b in self.bia.items()}
        self.owner = {s: f"act:{s}" for s in core_} | {
            s: b["id"] for b in co["bands"] for s in b["slugs"]}
        self.users: dict[str, list[str]] = {}  # what stands on each item, never a site row
        for k, a in merge_table.items(register).items():
            for d in a.get("depends_on") or [] if a.get("asset_type") != merge_table.SITE else []:
                self.users.setdefault(d, []).append(k)

    def holder(self, k: str, who: str) -> str | None:
        """The drawn box holding an item for one activity (a band for its group's): a role is in
        that one's People box, anything else in the one box the table puts it in."""
        if self.register[k].get("asset_type") == merge_table.ROLE:
            i = f"{PEOPLE_OF}{who}"
            return i if i in self.held.get(k, []) else None
        return next((i for i in self.held.get(k, []) if not i.startswith(PEOPLE_OF)), None)

    def lights(self, slugs: list[str], who: str, me: str) -> dict[str, Any]:
        """An activity click (§11.2): the boxes holding what this_bia ties to it, dashed lines to
        what it uses itself, solid lines down what those stand on; 462 G3 (his "Direct only"): the
        boxes it uses itself (`uses`), and how many of those have a gap."""
        chain = {k for s in slugs for k in self.box_of[s]}
        # 408 E: the firms this_bia draws as a line, a box of their own by level, light too
        lined = merge_table.beneath(self.register, chain) - chain

        def box(k: str) -> str | None:
            return self.holder(k, who)
        lit = sorted(set(merge_table.boxes_used(self.register, self.boxes, slugs,
                                                f"{PEOPLE_OF}{who}"))
                     | {b for k in lined if (b := box(k))})
        chain |= lined
        edges = {(me, b, True) for k in chain if (b := box(k)) and any(
            c.get("department") in slugs for c in self.register[k].get("consumers") or [])}
        edges |= {(a, b, False) for k in chain for d in self.register[k].get("depends_on") or []
                  if d in chain and (a := box(k)) and (b := box(d)) and a != b}
        uses = sorted({b for s in slugs for k in self.box_of[s] if (b := box(k)) and any(
            c.get("department") == s for c in self.register[k].get("consumers") or [])})
        return {"lit": lit, "edges": sorted([a, b, u] for a, b, u in edges), "uses": uses,
                "gaps": sum(bool(self.boxes[i]["gaps"]) for i in uses)}

    def above(self, members: list[str]) -> set[str]:
        """What stands on the members, all the way up, never through a site row."""
        out, todo = set(), list(members)
        while todo:
            for k in self.users.get(todo.pop(), []):
                if k not in out:
                    out.add(k)
                    todo.append(k)
        return out - set(members)


def _member_said(row: dict[str, Any]) -> str | None:
    """One resource's target: its own, else the one its activities agree on, else that they
    differ (307); None where nothing states one."""
    if own := _figure(row.get("rto")):
        return own
    figures = {f for c in row.get("consumers") or [] if (f := _figure(c.get("rto")))}
    return DIFFERS if len(figures) > 1 else figures.pop() if figures else None


def _box_fact(register: dict[str, Any], members: list[str]) -> str:
    """§11.1 item 5: "Recovery target …" where the members' records state one, never computed;
    nothing where none does."""
    said = {x for m in members if (x := _member_said(register[m]))}
    if DIFFERS in said or len(said) > 1:
        return DIFFERS
    return f"Recovery target {said.pop()}" if said else ""


def _needed(t: _Table, members: list[str], names: dict[str, str],
            aims: dict[str, str | None]) -> list[str]:
    """308 on this page: each activity the box's "Needed by" counts, with its own row's target
    (the member named where the box holds several), else (502) its record's recovery target or
    that none is recorded, else the resources it reaches the box through; nothing chosen or
    ranked."""
    needing = merge_table.needed_by(t.register, members)
    out, direct = [], set()
    for m in members:
        for c in t.register[m].get("consumers") or []:
            if c.get("department") in needing and _needs_it(c):
                aim = aims.get(c["department"])  # ADR-0048: no demo mark
                said = _figure(c.get("rto")) or (f"recovery target {aim}" if aim
                                                 else "no recovery target recorded")
                of = f" ({merge_table.shown(t.register, m)})" if len(members) > 1 else ""
                out.append(f"{names[c['department']]}: {said}{of}")
                direct.add(c["department"])
    above = t.above(members)
    for s in needing:
        if s not in direct:
            via = sorted({merge_table.shown(t.register, x) for x in above if any(
                c.get("department") == s and _needs_it(c)
                for c in t.register[x].get("consumers") or [])})
            out.append(f"{names[s]}: through {', '.join(via)}")
    return out


def _hot(t: _Table, i: str, members: list[str], band_rows: dict[str, str]) -> list[str]:
    """A box click (§11.2): the box, what it stands on, what stands on it, every activity that
    needs it (its band, and the band's row of it), none whose record does without it (408)."""
    near = (merge_table.beneath(t.register, members) - set(members)) | t.above(members)
    boxes = {b for k in near for b in t.held.get(k, [])}
    acts = {x for s in merge_table.needed_by(t.register, members, lit=True)
            for x in (t.owner.get(s), band_rows.get(s)) if x}
    return sorted({i} | boxes | acts)


def _page_box(t: _Table, i: str, names: dict[str, str], who: dict[str, str],
              band_rows: dict[str, str], aims: dict[str, str | None]) -> dict[str, Any]:
    """A box as this page shows it: People named with its activity; a why that is the record's
    own short clause or none (the strip counts), never a This-BIA why line (§11.1 item 7); the
    members' recovery target; its title naming what it holds; its strip's list and what it
    lights."""
    b, reg = t.boxes[i], t.register
    box = {**b, "title": "\n".join(
        [f"Members: {'; '.join(sorted(str(reg[k]['name']) for k in b['members']))}"]
        + ([f"Lines: {'; '.join(b['lines'])}"] if b["lines"] else []))}
    if i.startswith(PEOPLE_OF):
        box["name"] = f"People · {who[i.removeprefix(PEOPLE_OF)]}"
        box["also"] = {r: [names.get(s, s) for s in ss] for r, ss in b["also"].items()}
    elif i != merge_table.SITES_ID:
        # 383 row 20: no count as the why; the strip's "<n> …, <d> directly" says it once
        one = merge_table.short_why(b["desc"]) if len(b["members"]) == 1 else ""
        box["why"] = one if one != b["name"] else ""
        box["fact"] = _box_fact(reg, b["members"])
    else:
        box["why"] = ""
    box["list"] = [] if i == merge_table.SITES_ID else _needed(t, b["members"], names, aims)
    # 524 r2: the rows each activity consumes here (a shared row, not a shared box)
    box["rowsBy"] = {} if i == merge_table.SITES_ID or i.startswith(PEOPLE_OF) else {
        s: sorted(k for k, j in bo.items() if j == i) for s, bo in t.box_of.items()
        if i in bo.values()}
    box["hot"] = [i] if i == merge_table.SITES_ID else _hot(t, i, b["members"], band_rows)
    if i.startswith(PEOPLE_OF):  # 355 F7: a People box lights its own activity (its band); 467
        # (465, his "Light them too"): and every activity and People box sharing one of its roles
        serves = _serves(reg, b["members"])
        box["hot"] = sorted({i, *_peers(t.boxes, i), *(x for s in serves for x in (
            t.owner.get(s), band_rows.get(s)) if x)})
        box["list"] = [x for x in box["list"] if x.split(": ")[0] in {names.get(s, s)
                                                                      for s in b["neededBy"]}]
    return box


def _serves(register: dict[str, Any], members: list[str]) -> list[str]:
    """467: every activity a box's roles serve, its own and those sharing one of them."""
    return sorted({str(c.get("department")) for k in members
                   for c in register[k].get("consumers") or []})


def _peers(boxes: dict[str, dict[str, Any]], i: str) -> list[str]:
    """467: the other People boxes holding one of this one's roles."""
    mine = set(boxes[i]["members"])
    return sorted(j for j, b in boxes.items() if j != i and b["col"] == merge_table.PEOPLE
                  and mine & set(b["members"]))


def _level(t2: _Table, box: dict[str, Any], i: str, band_rows: dict[str, str]) -> dict[str, Any]:
    """378 r3: what a table box lights and reaches in the level view, over that view's boxes
    (`t2`), the level-only ones too; Sites and a People box light as on the other views."""
    lv = t2.boxes[i]
    hot = box["hot"] if i == merge_table.SITES_ID or i.startswith(PEOPLE_OF) else _hot(
        t2, i, lv["members"], band_rows)
    return {"hot": hot, "reach": lv["reach"], "gapReach": lv["gapReach"]}


def _lines(t: _Table) -> list[list[str]]:
    """The lines among a table's boxes: box a stands on box b where a member of a depends on a
    member of b."""
    return [list(e) for e in sorted({(i, b) for i, bx in t.boxes.items() for k in bx["members"]
                                     for d in t.register[k].get("depends_on") or []
                                     for b in t.held.get(d, []) if i != b})]


def _not_drawn(t: _Table) -> list[list[Any]]:
    """"Not drawn, and why", company-wide: each register item that is in no box, held by no band,
    a line on no box and a mark on none, by the rule its activities' pages list it under, else
    because nothing links it to an activity."""
    reg = t.register
    placed = set(t.held) | {k for ks in t.co["inside"].values() for k in ks}
    lines = {n for b in t.boxes.values() for n in b["lines"]}
    rules = {n: rule for b in t.bia.values() for rule, ns in b["notDrawn"] for n in ns}
    out: dict[str, list[str]] = {}
    for k, a in merge_table.items(reg).items():
        name = str(a.get("name"))
        if k in placed or name in lines or a.get("backup_for") or a.get("service_for"):
            continue
        rule = rules.get(name) or UNLINKED_RULE
        out.setdefault(rule, []).append(name)
    return [[rule, sorted(ns)] for rule, ns in out.items()]


def _bands(t: _Table, rows: list[Any], names: dict[str, str]) -> list[dict[str, Any]]:
    """Each band with its activities as rows, the stated handoff pair first (333), each row
    lighting its own chain; what the band holds on its own."""
    by = {r.slug: r for r in rows}
    out = []
    for b in t.co["bands"]:
        pairs = [[by[s].name, d] for s in b["slugs"] for d in by[s].downstream or ()
                 if d in b["activities"]]
        first = [s for p in pairs for n in p for s in b["slugs"] if by[s].name == n]
        order = list(dict.fromkeys(first + b["slugs"]))
        acts = [{"id": f"act:{s}", "name": names[s], "slug": s, "number": by[s].number,
                 "area": by[s].group, **t.lights([s], b["id"], f"act:{s}")} for s in order]
        holds = sorted(str(t.register[k]["name"]) for k in t.co["inside"][b["id"]])
        out.append({"id": b["id"], "name": b["name"], "slugs": b["slugs"], "nobia": b["nobia"],
                    "activities": b["activities"], "rows": acts, "pairs": pairs,
                    "pair": len(first), "holds": holds, "title": f"Holds: {'; '.join(holds)}",
                    **t.lights(b["slugs"], b["id"], b["id"])})
    return out


def _by_level(t2: _Table, slugs: list[str], who: str, me: str) -> dict[str, Any]:
    """What an activity lights by level; no `uses`: the count is the table's on every view (462
    G3)."""
    return {k: v for k, v in t2.lights(slugs, who, me).items() if k != "uses"}


def whole(folder: Path, register: dict[str, Any]) -> dict[str, Any]:
    """Ticket 334: what the laptop draws under Whole company, `merge_table.company` (336) as it
    stands: the core activities in flow order and the two bands in the activity column, every
    box of the table, the gaps' counts, the flow, and what each click lights; "Not drawn, and
    why" company-wide."""
    rows = core.process_map_rows(folder)
    co = merge_table.company(rows, register)
    core_rows = [r for r in rows if r.name in co["core"]]
    t = _Table(register, co, [r.slug for r in core_rows])
    names = {r.slug: r.name for r in rows}
    bands_ = _bands(t, rows, names)
    who = {r.slug: r.name for r in core_rows} | {b["id"]: b["name"].split(" (")[0]
                                                 for b in co["bands"]}
    band_rows = {a["slug"]: a["id"] for b in bands_ for a in b["rows"]}
    # 502: each activity's recovery target as its record (last year's) gives it
    aims = {r.slug: _figure((core.last_year(folder, r.slug).get("figures") or {}).get("RTO"))
            for r in rows}
    acts = [{"id": f"act:{r.slug}", "name": r.name, "slug": r.slug, "number": r.number,
             "area": r.group, "down": [d for d in r.downstream or () if d in co["core"]],
             **t.lights([r.slug], r.slug, f"act:{r.slug}")} for r in core_rows]
    boxes = {i: _page_box(t, i, names, who, band_rows, aims) for i in co["boxes"]}
    # 378: the level view's boxes past the table's (each band's own system, each outside firm),
    # `levelOnly`, drawn by level only
    t2 = _Table(register, {**co, "boxes": co["levelBoxes"]}, [r.slug for r in core_rows])
    more = {i: {**_page_box(t2, i, names, who, band_rows, aims), "levelOnly": True,
                **_folded(co, i)} for i in co["levelBoxes"] if i not in boxes}
    # 378 r3: the table's boxes light and reach by level over the level view's boxes (`level`)
    for i, b in boxes.items():
        b["level"] = _level(t2, b, i, band_rows)
    for b in more.values():
        b["level"] = {k: b[k] for k in ("hot", "reach", "gapReach")}
    _people_column(folder, register, boxes, None, co["bands"])  # 467
    # 408 E: an activity, a band and a band's row light by level over the level view's boxes too
    for a in acts:
        a["level"] = _by_level(t2, [a["slug"]], a["slug"], a["id"])
    for band in bands_:
        band["level"] = _by_level(t2, band["slugs"], band["id"], band["id"])
        for a in band["rows"]:
            a["level"] = _by_level(t2, [a["slug"]], band["id"], a["id"])
    total = len(core_rows) + sum(len(b["slugs"]) for b in co["bands"])
    plants = co["boxes"].get(merge_table.SITES_ID, {}).get("plants", [])
    return {"company": _company_name(folder), "total": total, "acts": acts, "bands": bands_,
            "boxes": boxes | more,
            # 378 r3: the default view's lines among its own boxes; the level view's (r2) its own
            "deps": _lines(t), "levelDeps": _lines(t2),
            "cols": [c for c in merge_table.COLUMNS if any(b["col"] == c for b in boxes.values())],
            "levelCols": [c for c in merge_table.COLUMNS
                          if any(b["col"] == c for b in co["levelBoxes"].values())],
            "flow": _flow(folder, core_rows[0].slug) if core_rows else None,
            "notDrawn": _not_drawn(t), "gapItems": co["gaps"], "levels": co["levels"],
            "plantWords": {p["id"]: merge_table.plant_words(register, co["boxes"], p["id"], names)
                           for p in plants},
            "siteActs": _company_site_acts(register, co["boxes"])}


def _folded(co: dict[str, Any], i: str) -> dict[str, str]:
    """462 K1: a level-only box a band holds inside it, with that band (`band`), so a plant it is
    tagged to lights the band where By resource type draws no box of it; else nothing."""
    held = {k: b["id"] for b in co["bands"] for k in co["inside"][b["id"]]}
    return next(({"band": held[k]} for k in co["levelBoxes"][i]["members"] if k in held), {})


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ── ticket 332: the phone's Whole company (spec §10.3, as 336 tightens it in §10.10) ───────────
#: An activity's tile on the whole company: "a:<slug>", never a box's id.
ACT_TILE = "a:"


def _chained(rows: list[Any]) -> list[Any]:
    """A group's rows in flow order: each chain by its Downstream cells, from the row no other
    hands work to; a row in no chain stays where the map has it, after the chains."""
    by_name = {r.name: r for r in rows}
    out: list[Any] = []
    for r in rows:
        if r.downstream and not (r.upstream and r.upstream[0] in by_name) and r not in out:
            while r is not None and r not in out:
                out.append(r)
                r = by_name.get(r.downstream[0]) if r.downstream else None
    return out


def _activity_tile(register: dict[str, Any], slug: str, people: str, at: dict[str, str],
                   boxes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """An activity on the whole company: the boxes it uses there, split into those it uses itself
    and those under them (its roles in its own People box; its band's own systems stay inside the
    band); 462 G3 (his "Direct only"): "Uses n", "n with gaps" and their names count those it uses
    itself, the laptop's count too; what sits beneath shows on a tap."""
    drawn = merge_table.this_bia(register, slug)
    direct = {k for k in drawn["box_of"] if any(c.get("department") == slug for c in
                                                register[k].get("consumers") or [])}
    held = {k: people if register[k].get("asset_type") == merge_table.ROLE else at.get(k)
            for b in drawn["boxes"].values() for k in b["members"]}
    # 408 E: the firms this_bia draws as a line, a box of their own by level, are under it too
    held |= {k: at.get(k) for k in merge_table.beneath(register, drawn["box_of"])
             if k not in held}
    uses = {i for k, i in held.items() if i and k in direct}
    used = [boxes[i] for i in sorted(uses)]
    return {"uses": sorted(uses), "under": sorted({i for i in held.values() if i} - uses),
            "usesN": len(used), "gapsN": sum(1 for b in used if b["gaps"]),
            "needs": [[b["name"], b["gaps"]] for b in used]}


def _stood_on(register: dict[str, Any], at: dict[str, str]) -> list[list[str]]:
    """The whole company's lines: a box stands on another where one of its resources does."""
    return [list(e) for e in sorted({(at[a], at[d]) for a in at
                                     for d in register[a].get("depends_on") or []
                                     if d in at and at[a] != at[d]})]


def company(folder: Path, register: dict[str, Any]) -> dict[str, Any]:
    """Ticket 332: what the phone draws under Whole company, from the one table
    (`merge_table.company`, 336): its boxes and bands, the lines between its boxes, the activities
    in groups (the core in flow order to the customers, each support band with its handoff pair
    first and the systems only it uses), each activity's tile and the "Not drawn" rows; "Open its
    BIA graph" opens 334's `bias`."""
    rows = core.process_map_rows(folder)
    co = merge_table.company(rows, register)
    at = {k: i for i, b in co["boxes"].items() if b["col"] != merge_table.PEOPLE
          for k in b["members"]}
    core_rows = [r for r in rows if r.name in co["core"]]
    flow = _chained(core_rows)
    # each group: its chain one per row with the flow arrows, then the rest (the core's alongside);
    # a room whose map names none of its register's activities has none
    groups = [{"id": None, "name": r.group, "flow": [r.slug for r in flow],
               "rest": [r.slug for r in core_rows if r not in flow], "side": True,
               "customers": _customers(folder) if flow else None, "own": [], "nobia": []}
              for r in core_rows[:1]]
    for b in co["bands"]:
        mine = [r for r in rows if r.slug in b["slugs"]]
        paired = _chained(mine)
        groups.append({"id": b["id"], "name": b["name"], "flow": [r.slug for r in paired],
                       "rest": [r.slug for r in mine if r not in paired], "side": False,
                       "customers": None, "own": [_own_name(register, i) for i in b["own"]],
                       "nobia": b["nobia"]})  # 375 B: its processes with no BIA, greyed
    people = {r.slug: f"people:{r.slug}" for r in core_rows} | {
        s: f"people:{b['id']}" for b in co["bands"] for s in b["slugs"]}
    names = {r.slug: r.name for r in rows}
    acts = {s: {"name": names[s], **_activity_tile(register, s, p, at, co["boxes"])}
            for s, p in people.items()}
    # 408 E: what a tile lights by level, over the level view's boxes (its band's own systems, the
    # outside firms)
    at2 = {k: i for i, b in co["levelBoxes"].items() if b["col"] != merge_table.PEOPLE
           for k in b["members"]}
    for s, p in people.items():
        tile = _activity_tile(register, s, p, at2, co["levelBoxes"])
        acts[s]["level"] = {"uses": tile["uses"], "under": tile["under"]}
    inside = [[f"Inside {b['name']}", sorted(merge_table.shown(register, k)
                                             for k in co["inside"][b["id"]])] for b in co["bands"]]
    # 378: the level view's bands draw boxes past the table's, so they are here too
    # the table's boxes keep the drawn set's reach (375's member walk), the rest are `levelOnly`
    # 378 r3: and each reaches by level over the level view's boxes (`level`)
    lvl = {i: {**b, "level": {k: co["levelBoxes"][i][k] for k in ("reach", "gapReach")}}
           for i, b in co["boxes"].items()} | {
        i: {**b, "levelOnly": True, **_folded(co, i)} for i, b in co["levelBoxes"].items()
        if i not in co["boxes"]}
    for b in lvl.values():  # 408 r2: the phone tray's shared roles name their others, as 355 F7
        if b.get("also"):
            b["also"] = {r: [names.get(s, s) for s in ss] for r, ss in b["also"].items()}
    _people_column(folder, register, lvl, None, co["bands"])  # 467
    # 462 B6: the company as its profile names it, as the laptop's Whole company does
    return {"name": _company_name(folder), "boxes": lvl, "phone": co["phone"],
            "groups": groups,
            # 378 r3: the default view's lines among its own boxes; the level view's (r2) its own
            "deps": _stood_on(register, at),
            "levelDeps": _stood_on(register, {k: i for i, b in co["levelBoxes"].items()
                                              if b["col"] != merge_table.PEOPLE
                                              for k in b["members"]}),
            "acts": acts, "needs": [], "census": [], "finding": None, "shared": 0,
            "gapItems": co["gaps"],  # 345 Q1: the counts count register items, bands included
            "levels": co["levels"], "phoneLevels": co["phoneLevels"],  # 374: by level here too
            "cols": [c for c in COLUMNS if c in co["phone"]],
            "notDrawn": inside, "actNames": names,  # its plants' words: `whole`'s (P1)
            "handoffs": {"up": [], "down": []}}


def _own_name(register: dict[str, Any], i: str) -> str:
    """A band's own box by the table's name for it, else the resource's shown name."""
    job = next((j[0] for j in merge_table.JOBS if f"job:{merge_table.slug(j[0])}" == i), None)
    return job or merge_table.shown(register, i)


def data(folder: Path, chosen: str | None = None) -> dict[str, Any]:
    """What the page draws, in the prototype's own shape (`make_data.py`), from the room's files;
    the page gets `shipped` of it (344). Ticket 305 adds to it each resource's marks; a firm or
    machine that is only a mark has no card. Ticket 326 adds `g2`,
    what the laptop draws under This BIA; its re-BIA finding is last year's record's, so a BIA
    drawn from a record of its own carries none."""
    register = v1graph.with_platforms(json.loads((folder / walk.REGISTER).read_text()))
    slug, record, stand_in = _activity(folder, register)
    if chosen and chosen != slug:  # 332 round 2: "Open its BIA graph" opens this page on it
        slug, record, stand_in = chosen, _stand_in(folder, chosen, register), True
    graph = _graph(folder, register, slug, record)
    marks, only = _marks(register), _only_marks(register)
    nodes = {n["id"]: {**_asset(n, register.get(n["id"]) or {}, slug),
                       "marks": marks.get(n["id"], [])}
             for n in graph["nodes"] if n["kind"] == "asset" and n["id"] not in only}
    edges = graph["edges"]
    procs = {n["id"]: {"name": n.get("activity") or n.get("name"),
                       "dept": str(n.get("dept") or CORE).upper(),
                       "flows": list(n.get("flows_to") or []),
                       "uses": sorted({e["src"] for e in edges if e["kind"] == "consumes"
                                       and e["dst"] == n["id"] and e["src"] in nodes}
                                      | {f for f in n.get("feeds") or [] if f in nodes})}
             for n in graph["nodes"] if n["kind"] == "process"}
    act = next(n for n in graph["nodes"] if n["kind"] == "activity")
    deps = [[e["src"], e["dst"]] for e in edges
            if e["kind"] == "depends_on" and e["src"] in nodes and e["dst"] in nodes]
    needs = [e["dst"] for e in edges if e["kind"] == "activity_dep" and e["dst"] in nodes]
    # t418 (ADR-0051, his "drop names on the graph pages too"): owner lines, strips, trays, Sites,
    # phone and laptop alike, every person by function (the register keeps the names)
    out = {"nodes": nodes,
           "deps": deps,
           "procs": procs,
           "actNeeds": needs,
           "g2": {**(drawn := g2(folder, register, slug)),
                  "finding": drawn["finding"] if stand_in else None},
           "company": company(folder, register),
           "act": {"name": act["name"], "desc": _purpose(folder, slug),
                   "flows": list(act.get("flows_to") or []),
                   "mtpd": _figure(act.get("mtpd")), "target": _figure(act.get("recovery_target")),
                   "lastYear": stand_in},
           "slug": slug, "whole": _with_cards(whole(folder, register), procs, act["name"]),
           "waiting": _waiting(folder, register),  # 372: SHARED page data
           "plan": _bias(folder),  # 375: SHARED page data, the plan's BIA rows
           "firms": merge_table.step_in(register),  # 466: SHARED page data, who can step in
           # 354/356: each column's kind token, and the boxes drawn deepest last in theirs
           "kinds": merge_table.KIND, "base": list(merge_table.DEEPEST)}
    shown: dict[str, Any] = words.functions_only_in(out, folder)
    return shown


def _people_column(folder: Path, register: dict[str, Any], boxes: dict[str, dict[str, Any]],
                   mine: str | None, bands: list[dict[str, Any]]) -> None:
    """467 (his "B · Owner + leads only", D1, H3/P2, "'n process owners' + hover"): each People
    box of This BIA (`mine`, its activity), Whole company or the phone's company (`bands`, the
    table's), named by what its face says, never
    "People · …": an activity's by its owner and lead functions (`words.leads`), a band's by its
    process owners counted from the plan (its Process owner cells, distinct, per band). Its
    `people`: the face's functions ([function, owner?, deputy's function or None]), whose they
    are (`of`), its roles' names, the shared ones with how many other activities need each, the
    activities its roles serve and the other People boxes holding one (465's lighting), a band's
    owners."""
    rows = core.process_map_rows(folder)
    slug_of, names = {r.name: r.slug for r in rows}, {r.slug: r.name for r in rows}
    faces = {slug_of[p]: fs for p, fs in words.leads(folder).items() if p in slug_of}
    plan_rows = _bias(folder)["rows"]
    by_id = {b["id"]: b for b in bands}
    for i, b in boxes.items():
        if b["col"] != merge_table.PEOPLE:
            continue
        who = mine or i.removeprefix(PEOPLE_OF)
        band = by_id.get(who)
        people: dict[str, Any] = {
            "of": names.get(who) or (band["name"].split(" (")[0] if band else who),
            "roles": sorted(str(register[k]["name"]) for k in b["members"]),
            "shared": [[r, len(others)] for r, others in (b.get("also") or {}).items()],
            "serves": _serves(register, b["members"]),
            "peers": [] if mine else _peers(boxes, i)}
        if band:
            held = [r for r in plan_rows if r["slug"] in band["slugs"]]
            n = len({r["owner"] for r in held})  # the plan's Process owner cells, distinct
            people |= {"owners": [[r["name"], faces[r["slug"]][0][0]] for r in held],
                       "acts": len(held), "n": n}
            b["name"] = f"{people['of']} · {n} process owner{'' if n == 1 else 's'}"
        elif who in faces:
            people["fns"] = faces[who]
            b["name"] = " · ".join(f for f, _, _ in faces[who])
        b["people"] = people


#: 375 (spec §12.25): the BIA programme plan, one row per BIA record
PLAN = words.PLAN


def _bias(folder: Path) -> dict[str, Any]:
    """375 A and B: the plan's BIA rows, in record order, each with its process's slug and group
    from the map, its "Last interview" (the badge's year, B) and its status cell; and the map's
    processes with no BIA (Walkable = no), named, never rows. Read from the files, nothing typed."""
    rows = core.process_map_rows(folder)
    by = {r.name: r for r in rows}
    path = folder / PLAN
    out, head = [], []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|"):
            continue
        if cells[0] == "Record":
            head = cells
        elif head and re.fullmatch(r"\d+\.\d+", cells[0]) and cells[1] in by:
            cell, status = dict(zip(head, cells, strict=False)), cells[-1]
            overdue = status.lower().startswith("overdue")
            date = re.search(r"\d{1,2} \w{3} \d{4}", status)
            out.append({"no": cells[0], "name": cells[1], "slug": by[cells[1]].slug,
                        "group": by[cells[1]].group, "owner": cell.get("Process owner", ""),
                        "last": cell.get("Last interview", ""), "status": status,
                        "kind": "overdue" if overdue else "ok",
                        "short": f"Overdue · {status.split(';', 1)[-1].strip()}" if overdue
                        else f"Reviewed {date[0]}" if date else status})
    return {"rows": out, "nobia": [r.name for r in rows if not r.walkable]}


def _acts(w: dict[str, Any]) -> list[dict[str, Any]]:
    """Ticket 334: everything in the Whole company's activity column: the core activities, the
    bands, and each band's rows."""
    return [*w["acts"], *w["bands"], *(r for b in w["bands"] for r in b["rows"])]


def _with_cards(w: dict[str, Any], procs: dict[str, dict[str, Any]],
                act: str) -> dict[str, Any]:
    """Each activity of the column with the page's cards it stands for (a band for its
    activities'), so Ask nemo lights it as it lights them."""
    by: dict[str, list[str]] = {act: [ACT]}
    for p, v in procs.items():
        by.setdefault(str(v["name"]), []).append(p)
    for a in _acts(w):
        a["cards"] = sorted(c for n in a.get("activities") or [a["name"]] for c in by.get(n, []))
    return w


def down(data_: dict[str, Any], starts: Iterable[str]) -> set[str]:
    """Every card the starting cards stand on, all the way down (the page's own `down`)."""
    out: set[str] = set()
    todo = list(starts)
    while todo:
        x = todo.pop()
        if x not in out:
            out.add(x)
            todo += [d for s, d in data_["deps"] if s == x]
    return out


def affected(data_: dict[str, Any], cards: Iterable[str]) -> set[str]:
    """What goes down with the cards added, by the register alone, as g150's failure click draws
    it (failure_click.js): each resource and every resource standing on it, the activities using
    any of them, and the process cards those hand work on to. An activity added goes down alone,
    with what it hands work on to."""
    hit = up(data_, [c for c in cards if c in data_["nodes"]])
    acts = {c for c in cards if c in data_["procs"] or c == ACT}
    acts |= {p for p, v in data_["procs"].items() if hit.intersection(v["uses"])}
    if hit.intersection(data_["actNeeds"]):
        acts.add(ACT)
    flows = {f for a in acts for f in (data_["act"] if a == ACT else data_["procs"][a])["flows"]}
    return hit | acts | flows


def up(data_: dict[str, Any], starts: Iterable[str]) -> set[str]:
    """The starting cards and every card standing on them, all the way up (dep_graph's own
    `downstream_chain`, the page's `up`)."""
    out: set[str] = set()
    todo = list(starts)
    while todo:
        x = todo.pop()
        if x not in out:
            out.add(x)
            todo += [s for s, d in data_["deps"] if d == x]
    return out


def page(root: str, code: str, folder: Path, harbour: str, chosen: str | None = None) -> str:
    """The page for this room, on its own activity or the one `chosen` (332 round 2: "Open its
    BIA graph" goes to `bia` + its slug). Its data rides in a JSON island no script tag can end
    early."""
    island = json.dumps({"ask": f"{root}/ask/{code}", "back": f"{root}/w/{code}/",
                         "bia": f"{root}/w/{code}/graph-live/",
                         "data": shipped(data(folder, chosen)),
                         "priv": stage_door.NOT_PRIVATE},  # 639 S3: the chat's line, one source
                        ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("{{harbour}}", harbour).replace("{{island}}", island)


#: 344: what only the server reads (`affected`, `down`, `up`, `_names`), never the page's script
SERVER_ONLY = ("nodes", "procs", "deps", "actNeeds")


def shipped(data_: dict[str, Any]) -> dict[str, Any]:
    """344: the page's data: the keys its script reads, and for `name()` each card's name (a
    resource's over a process's of the same id, as it read the resources first), never the cards."""
    names = {**{p: v["name"] for p, v in data_["procs"].items()},
             **{i: n["name"] for i, n in data_["nodes"].items()}}
    return {**{k: v for k, v in data_.items() if k not in SERVER_ONLY}, "names": names}


WHOLE = "all"


def _boxes(data_: dict[str, Any], scope: Any = None) -> dict[str, list[str]]:
    """Each box of the scope asked from as what it stands for: a box its register resources; under
    Whole company (334) also an activity its cards (a band its activities')."""
    if scope != WHOLE:
        return {i: b["members"] for i, b in data_["g2"]["boxes"].items()}
    w = data_["whole"]
    return {i: b["members"] for i, b in w["boxes"].items()} | {a["id"]: a["cards"]
                                                               for a in _acts(w)}


def _names(data_: dict[str, Any], scope: Any = None) -> dict[str, str]:
    """Every id the page may send by its name; under Whole company the table's boxes, 334's
    activity column and the phone's activity tiles (332)."""
    whole = scope == WHOLE
    boxes = data_["whole"]["boxes"] if whole else data_["g2"]["boxes"]
    return {**{p: v["name"] for p, v in data_["procs"].items()},
            **{i: b["name"] for i, b in boxes.items()},
            **({a["id"]: a["name"] for a in _acts(data_["whole"])} if whole else {}),
            **({f"{ACT_TILE}{s}": a["name"] for s, a in data_["company"]["acts"].items()}
               if whole else {}),
            **{i: n["name"] for i, n in data_["nodes"].items()}, ACT: data_["act"]["name"]}


def members(data_: dict[str, Any], cards: Iterable[str], scope: Any = None) -> list[str]:
    """Ticket 326: the cards, each G2 box as the register resources it holds; 334: under Whole
    company, the table's boxes and the activity column's."""
    boxes = _boxes(data_, scope)
    return [m for c in cards for m in (boxes[c] if c in boxes else [c])]


def named(data_: dict[str, Any], said: str) -> set[str]:
    """The cards an answer names, each by its whole name, the longest name first so "Payroll
    system" marks the system and not the Payroll activity as well."""
    left, hit = said.lower(), set()
    for name, ids in sorted(_by_name(data_).items(), key=lambda kv: -len(kv[0])):
        pattern = rf"(?<!\w){re.escape(name)}(?!\w)"
        if re.search(pattern, left):
            hit |= ids
            left = re.sub(pattern, " ", left)
    return hit


def _by_name(data_: dict[str, Any]) -> dict[str, set[str]]:
    """The cards by name; a G2 box is marked by its members, so it is not one of them."""
    by: dict[str, set[str]] = {}
    for i, name in _names(data_).items():
        if i not in data_["g2"]["boxes"]:
            by.setdefault(name.lower(), set()).add(i)
    return by


def asked(data_: dict[str, Any], body: dict[str, Any]) -> tuple[str, str, bool, str | None]:
    """The turn the page asks for: his question with the cards he added named before it, or a
    next step he tapped, as the chat's own tap sends it (its words, pick and action id)."""
    tap = body.get("tap")
    if isinstance(tap, dict):
        action = tap.get("action")
        return (str(tap.get("text") or ""), "tapped", bool(tap.get("pick")),
                str(action) if action else None)
    names = _names(data_, body.get("scope"))
    cards = [names[i] for i in body.get("cards") or [] if isinstance(i, str) and i in names]
    question = str(body.get("question") or "").strip()
    text = f"About {', '.join(cards)}, on the dependency graph: {question}" if cards else question
    return text, "typed", False, None


def ask(folder: Path, model: str, sessions: Sessions, log: Log, body: dict[str, Any],
        root: str = "", waited: float = 0.0) -> dict[str, Any]:
    """One turn of the room's chat from the page: what nemo said, what goes down with the cards
    added (the register's chain, lit), the other cards its answer names (marked, never lit), and
    the next steps it drew under the answer. `waited`: how long it queued behind a running turn
    of the room (t409), counted in its line's `seconds` as the chat's are (t310)."""
    if folder not in sessions:
        fault = core.refuse_short(folder, model, log)
        if fault:
            return {"reply": fault, "lit": [], "named": [], "next": []}
        s = core.Session(folder, model, log)
        s.root, s.graph_page = root, True
        sessions.setdefault(folder, (s, threading.Lock()))
    s, lock = sessions[folder]
    drawn = data(folder)
    with lock:
        said = _turn(s, drawn, *asked(drawn, body), waited=waited)
    gone = affected(drawn, members(drawn, [i for i in body.get("cards") or []
                                           if isinstance(i, str)], body.get("scope")))
    return {**said, "lit": sorted(gone), "named": sorted(set(said["named"]) - gone)}


def _turn(s: core.Session, data_: dict[str, Any], text: str, how: str, pick: bool,
          action: str | None, waited: float = 0.0) -> dict[str, Any]:
    """The chat's own `_turn`, without Chainlit: the turn, its line on the turn file whatever
    happens, then what he reads (107's naming) with its cards."""
    said: dict[str, Any] = {"said": text}
    if how == "tapped" and (shown := s.shown(text)) != text:
        said["shown"] = shown
    try:
        reply, options, cards = s.turn(text, how=how, pick=pick, action=action)
        said.update(reply=reply, options=options, cards=cards)
    except lanes.LaneDown as down_:
        return {"reply": down_.said, "named": [], "next": []}
    finally:
        line = {**s.last_turn, **said}
        if waited and isinstance(line.get("seconds"), (int, float)):  # t409: it queued
            line["seconds"] = round(line["seconds"] + waited, 1)
        core.record_turn(s.folder, line)
    return answered(s, data_, reply, cards,
                    [{"label": s.shown(o), "text": o, "action": aid, "pick": s.last_pick}
                     for o, aid in zip(options, s.last_actions, strict=False)])


def answered(s: core.Session, data_: dict[str, Any], reply: str, cards: list[str],
             next_steps: list[dict[str, Any]]) -> dict[str, Any]:
    """What the page shows of a turn: the answer as he reads it (107's naming) with its cards,
    the cards it names, found by nemo's own words as well as the shown ones, since a gloss can
    fall inside a name ("SAP (the maker of the finance software) S/4HANA Finance"), and its next
    steps."""
    shown_reply, shown_cards = s.drawn_turn(reply, cards)
    shown = "\n\n".join([shown_reply, *shown_cards]).strip()
    return {"reply": shown, "named": sorted(named(data_, "\n".join([reply, *cards, shown]))),
            "next": next_steps}
