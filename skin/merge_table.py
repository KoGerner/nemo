"""Ticket 336 (with 326's amend round): the one company-wide merge table, every box of it drawn
(384, his "No cap: draw every box", 2026-10-07T14:04:03Z), and the phone's fold, at most 6 per band
(his answers in 8_marschkamp's grill, e7e4e83d 19:09:33Z; the table is 8_marschkamp's audit, draft
2 §B, with the reviewer's round 7).

A presentation mapping, never a register change (ADR-0034 Part E 16b): every register item is a box,
inside a named merge ("Merged from …"), a line on the box it supplies, a mark, or listed under "Not
drawn, and why" by its rule. The laptop's This BIA (`live_graph.g2`) draws `this_bia`; the
whole-company view and the phone (334, 331, 332) import `company` and `bands`. Everything is
computed from the register at call time:

    this_bia(register, slug)   one activity's boxes
    company(rows, register)    the whole company: activities, bands, people, shared boxes,
                               sites, foundation
    bands(boxes)               the phone's fold, at most BAND_BUDGET per band by kind
    gap_items(register, boxes, inside)
                               each gap's register items company-wide, and the boxes and bands
                               carrying them (345 Q1)
    needed_by(register, keys)  the activities that depend on these, directly or through what
                               stands on them (never through a site, a backup or a service)
    waived(register, k, use)   §9.2 rule 1: the activity does without it; a click lights neither way
    key_roles(register, ...)   the reviewer's rule: up to 3 named, no spare first, then the largest
                               emergency team, never by MTPD
    plant_words(register, boxes, plant, names, slug=None)
                               a plant's words: what runs there, each activity's own takeover

Gaps are exactly three (spec §10.1.2): No workaround and Single source from `workspace.flagged`, its
one home (330 widens it there, and the chips follow by merge alone), a cell stating there is none
No workaround by B5's `workspace.NO_WORKAROUND` (447), and Owner missing from the register's
`owner_gap`.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import workspace

from nemo import walk

#: ADR-0034: how an authored description opens; a box shows the words after it, marked.
MARK = "Written for the demo pack, not in any prior record"
#: 356 (ISO 9001:2015 7.1.2, 7.1.3, 8.4, 8.6; spec §12.13 and §12.14 F1): the columns by kind, left
#: to right after the activity; an empty one is dropped.
PEOPLE, PROVIDERS, RELEASE, EQUIPMENT, ICT, BUILDINGS = (
    "People", "External providers", "Release", "Equipment and transport", "ICT",
    "Buildings and utilities")
COLUMNS = (PEOPLE, PROVIDERS, RELEASE, EQUIPMENT, ICT, BUILDINGS)
#: 354/356: each column's kind, the `--kind-<kind>` token its bars and dot take (nemo's own,
#: `harbour/tokens/nemo-colors.css`)
KIND = {PEOPLE: "people", PROVIDERS: "providers", RELEASE: "release", EQUIPMENT: "equipment",
        ICT: "ict", BUILDINGS: "buildings"}
ROLE, SITE, SUPPLIER = "Role", "Site", "External supplier"
#: Each register type's column (ADR-0034 Part E 16c's types); a type not named here is ICT's. Roles
#: and sites never reach it: they are the People box and the Sites box.
KINDS = {SUPPLIER: PROVIDERS, "Approval": RELEASE, "Equipment and facilities": EQUIPMENT,
         "Utilities": BUILDINGS, "IT infrastructure": BUILDINGS}
#: His number: the phone at most 6 per band, the rest under "+ n more" (384 removed This BIA's 13
#: and Whole company's 30: "No cap: draw every box").
BAND_BUDGET = 6
NO_WORKAROUND, SINGLE, OWNER = "no workaround", "single source", "owner missing"
GAPS = (NO_WORKAROUND, SINGLE, OWNER)
PEOPLE_ID, SITES_ID, FOUNDATION_ID = "people", "sites", "job:power-and-network"
#: The table (draft 2 §B1/§B2, his 19:20 answers): each box's company-wide name, its column, the
#: register names it holds, and its plain "why" (None: the consumer row's own need). A box forms
#: from any one of its names, so every activity using CSB or MAWI shows the same box.
JOBS: tuple[tuple[str, str, tuple[str, ...], str | None], ...] = (
    ("ERP and warehouse control", ICT,
     ("CSB ERP Marschkamp", "MAWI ERP Breitenburg", "Automated warehouse control"),
     "production orders, batches and the chilled warehouse"),
    ("Weighing and labelling", ICT,
     ("Merchandise management and price-labelling system", "Price-labelling devices"),
     "weighs and price-labels every pack"),
    ("Cutting and processing lines", EQUIPMENT, ("Cutting and processing lines",),
     "band saws, deboning, portioning, packing"),
    # 351 N2: the temperature records fold into the box, their own item in the register
    ("Refrigeration", EQUIPMENT, ("Refrigeration", "Cold-chain temperature monitoring"),
     "deep-freeze, 4 °C and 10 °C rooms"),
    ("Vehicle fleet (refrigerated)", EQUIPMENT, ("Vehicle fleet",),
     "refrigerated vehicles take the goods to the customers"),
    ("Plant utilities", BUILDINGS,
     ("Steam and hot water", "Compressed air", "Mains water", "Wastewater treatment"),
     "hot water, air and water for the lines; wastewater taken away"),
    ("Raw material", PROVIDERS,
     ("Raw material suppliers (framework contracts and the open market)",
      "Suppliers (framework contracts and the open market)",
      "Stoer Valley Abattoir GmbH", "Kellinghusen Pork GmbH"),  # 351 N4
     "raw materials and meat products from framework suppliers and the open market"),
    ("Packing materials (film, trays, crates, gases)", PROVIDERS,
     ("PackForm North GmbH", "Industrial gases (nitrogen, carbon dioxide)", "North Gas GmbH",
      "Elbe Industrial Gases GmbH", "North Crate Pool GmbH"),  # 351 N5
     "film, trays and gases for the packs; crates and pallets to ship in"),
    ("By-product collection", PROVIDERS, ("North German Rendering GmbH", "Müllnix GmbH"),
     "takes bones, fat and trim off site"),
    ("Veterinary and QA release", RELEASE, ("Veterinary and QA release",),
     "goods are checked and released by QA and the vet"),  # 351 C2: goods-in and dispatch
    ("Microsoft 365", ICT, ("Microsoft 365", "Microsoft Teams", "Microsoft SharePoint Online"),
     None),
    ("Telephony", ICT, ("Cisco Call Manager", "Cisco telephony"),
     "the phone line for reporting and escalating problems"),
    ("Service desk ticket systems", ICT,
     ("Atlassian Jira Service Management", "BMC Remedy AR System", "Ticket interface"),
     "where every ticket is logged and tracked"),
    ("Sign-in and authorisation", ICT,
     ("Microsoft Active Directory", "Keycloak", "Central authorisation system"),
     "who may log in, and to what"),
    # 351: HR master data is its own box, so Time recording stands on it (E5) and is stood on by
    # payroll without the two boxes standing on each other
    ("HR systems", ICT, ("Payroll system", "HR-to-financial-accounting interface"), None),
    ("HR master data", ICT, ("HR master data system",), None),
    ("Route planner", ICT, ("Route planner",), "plans the delivery routes"),
    ("Power and network", BUILDINGS, ("Corporate network", "Power supply"),
     "the network and the power every system here depends on"),
)
#: A2: the skin's short names for single resources (never a register edit).
NAMES = {"Technician": "Technicians", "Automated warehouse control": "Warehouse control"}
#: A4, 466 I2 (11_nemo_design's "one form"): a supplier's line is "<what it gives>: <its full
#: name>"; the skin's word where the record's own short words are none or too long for a line.
WHAT = {"Marsh Data EDI Services GmbH": "order exchange",
        "North Net Communications GmbH": "carrier", "Grid operator": "electricity"}
#: 466 I3: a register type as a merged box names its part's ("Price-labelling devices
#: (equipment)"); a type not named here is said as the register has it.
TYPE_WORDS = {"IT system": "ICT", "Equipment and facilities": "equipment",
              "Utilities": "utilities", SUPPLIER: "external provider"}
#: The Sites box counts its places in draft 2 §A b1's words (8_marschkamp: "3 plants · logistics
#: centre · HR administration", never "five sites"); a site not named here is a plant.
PLACES = {"Marschkamp logistics centre": "logistics centre",
          "Central HR administration": "HR administration"}
#: §9.2's "Not drawn, and why", by rule.
RUNS_WITHOUT_RULE = "It can run without them (the record says so)"
FIRMS_RULE = "Other firms can step in (the record's workaround)"
LINES_RULE = "A line on the box they supply"
#: 405 r3 (15_marschkamp's tested rule): the record does without it when the cell's FIRST clause
#: says "can run without" or "is possible without" (procurement's 13 Feb 2025 cells), never a
#: second clause ("…; production is possible without an order") or "No workaround: … without …"
RUNS_WITHOUT = re.compile(r"^[^;]*?\b(?:can run|is possible) without\b", re.I)
FIRM = re.compile(r"\s+GmbH(?: & Co\. KG)?$")
REBIA = "re-BIA"
#: Ticket 318 (ADR-0047): a row added in chat, as its box shows it; it has no record figure, so its
#: recovery line says not recorded (N1), where 307's "not stated" stays for every other row.
ADDED_MARK = "added in chat · {on}"
NO_OWNER = "owner not yet named"
NOT_RECORDED = "Recovery target · not recorded"


def own_words(row: dict[str, Any]) -> str:
    """A register row's description as a card shows it: the record's own words, an authored one
    without its opening mark (the card carries "for the demo" instead)."""
    return str(row.get("description") or "").replace(f"{MARK}: ", "")


def authored(row: dict[str, Any], evidence: str) -> bool:
    return row.get("authored") is True or MARK in str(row.get(evidence) or "")


def items(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The register's resources, without its notes."""
    return {k: a for k, a in register.items() if isinstance(a, dict)}


def shown(register: dict[str, Any], k: str) -> str:
    """A resource's name as a box says it (A2)."""
    name = str(register[k].get("name"))
    return NAMES.get(name, name)


def supplies(register: dict[str, Any], k: str) -> str:
    """466 I2: a supplier's line on the box it supplies, "diesel: Marshland Fuels GmbH"."""
    name = str(register[k].get("name"))
    what = WHAT.get(name) or short_why(own_words(register[k])) or "supplier"
    return f"{what[:1].lower()}{what[1:]}: {name}"


def _types(register: dict[str, Any], members: list[str]) -> dict[str, str]:
    """466 I3: each part's type, by name, where the parts of a merge differ in type; else none."""
    types = {str(register[k]["name"]): str(register[k].get("asset_type")) for k in members}
    return {n: TYPE_WORDS.get(t, t) for n, t in types.items()} if len(set(types.values())) > 1 \
        else {}


def _work(register: dict[str, Any], members: list[str],
          slugs: set[str] | None) -> list[list[Any]]:
    """466 H2/I1: each workaround the members' records give, in the record's words, once, with
    the activities whose rows give it, in the register's order, and (r2) the parts that give it."""
    out: dict[str, tuple[list[str], list[str]]] = {}
    for k in members:
        for c in register[k].get("consumers") or []:
            said = " ".join(own_words({"description": c.get("workaround")}).split())
            if said and (slugs is None or c.get("department") in slugs):
                ss, parts = out.setdefault(said, ([], []))
                for x, at in ((str(c.get("department")), ss), (str(register[k]["name"]), parts)):
                    if x not in at:
                        at.append(x)
    return [[w, ss, parts] for w, (ss, parts) in out.items()]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def marks(register: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Ticket 305: each resource's "service:" and "backup:" marks (300), read from the rows of the
    firms and machines that serve or back it up; a backup says what it runs on, in the words of the
    row it stands on ("backup: Emergency generator (diesel: Marshland Fuels GmbH)")."""
    out = _chat_marks(register)
    for row in items(register).values():
        runs = []
        for d in row.get("depends_on") or []:
            what = own_words(register.get(d) or {}).rstrip(".")
            name = (register.get(d) or {}).get("name") or d
            runs.append(f"{what.lower()}: {name}" if what and " " not in what else name)
        backup = f"{row.get('name')} ({', '.join(runs)})" if runs else str(row.get("name"))
        for kind, said in (("backup", backup), ("service", row.get("name"))):
            for served in row.get(f"{kind}_for") or []:
                out.setdefault(served, []).append(
                    {"text": f"{kind}: {said}", "authored": authored(row, f"{kind}_evidence")})
    return out


def _chat_marks(register: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Ticket 318 (ADR-0047 3): a resource added in chat says so, with its date, and that its owner
    is not yet named; its own words, so never "for the demo"."""
    return {k: [{"text": ADDED_MARK.format(on=row[walk.ADDED_IN_CHAT]), "authored": False},
                *([{"text": NO_OWNER, "authored": False}] * (not row.get("owner_name")))]
            for k, row in items(register).items() if row.get(walk.ADDED_IN_CHAT)}


def beneath(register: dict[str, Any], starts: Iterable[str]) -> set[str]:
    """The resources given and all they stand on, all the way down."""
    out: set[str] = set()
    todo = list(starts)
    while todo:
        x = todo.pop()
        if x not in out and isinstance(register.get(x), dict):
            out.add(x)
            todo += register[x].get("depends_on") or []
    return out


def _depends(c: dict[str, Any]) -> bool:
    """A use the activity depends on: not one whose record says it can run without it."""
    return not RUNS_WITHOUT.search(str(c.get("workaround") or ""))


def waived(register: dict[str, Any], k: str, c: dict[str, Any]) -> bool:
    """§9.2 rule 1, one rule for both views and both screens (8_nemo_design, 2026-10-10; 408): the
    activity of consumer row `c` of resource `k` does without it, its record saying it can run
    without it or that other firms can step in (`this_bia` lists it under "Not drawn, and why");
    a click on that activity lights none of it, and a click on it lights none of that activity."""
    return not _depends(c) or (not _job(register, k) and _replaceable(register[k], c))


def needed_by(register: dict[str, Any], keys: Iterable[str], lit: bool = False) -> list[str]:
    """§10.1.3: the activities that depend on these resources, directly or through the resources
    standing on them, on the register (rule 7: never on what is drawn after the cut). A site row is
    a tag, a backup or a service a mark, so none of them is counted through. `lit` (408): those a
    click on them lights, every `waived` row left out."""
    rows = {k: a for k, a in items(register).items() if a.get("asset_type") != SITE}
    users: dict[str, list[str]] = {}
    for k, a in rows.items():
        for d in a.get("depends_on") or []:
            users.setdefault(d, []).append(k)
    hit = {k for k in keys if k in rows}
    todo = list(hit)
    while todo:
        for k in users.get(todo.pop(), []):
            if k not in hit:
                hit.add(k)
                todo.append(k)
    return sorted({str(c.get("department")) for k in hit for c in rows[k].get("consumers") or []
                   if (not waived(register, k, c) if lit else _depends(c))})


def _figure(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def key_roles(register: dict[str, Any], roles: Iterable[str], slugs: set[str]
              ) -> tuple[list[dict[str, Any]], int]:
    """the reviewer's rule (his 19:20:09Z "Take the reviewer's rule"): a role is key when the record needs it in
    emergency operation (a figure of 1 or more, or "as needed") or it carries a gap or a re-BIA
    flag; up to 3 are named, no spare first (the emergency need is the whole headcount), then the
    largest emergency team; never by MTPD. The rest are counted, never summed."""
    ranked = []
    roles = list(roles)
    for k in roles:
        row = register[k]
        uses = [c for c in row.get("consumers") or [] if c.get("department") in slugs]
        team = max((f for c in uses if (f := _figure(c.get("staff_emergency"))) is not None),
                   default=None)
        needed = (team is not None and team >= 1) or any(
            "as needed" in str(c.get("staff_emergency") or "").lower() for c in uses)
        flagged = bool(row.get("owner_gap")) or any(str(q).startswith(REBIA)
                                                     for q in row.get("quality_flags") or [])
        if not (needed or flagged):
            continue
        spare = not any(_figure(c.get("staff_emergency")) is not None
                        and c.get("staff_emergency") == c.get("staff_normal") for c in uses)
        ranked.append(((spare, -(team or 0), shown(register, k)), k, uses))
    named = []
    for _, k, uses in sorted(ranked)[:3]:
        figures = [f"{c.get('staff_normal')} → {c.get('staff_emergency')}"
                   + (f" in {c['provided_within']}" if c.get("provided_within") else "")
                   for c in uses if c.get("staff_emergency") is not None]
        named.append({"id": k, "name": shown(register, k),
                      "figures": figures or ["no figure stated"]})
    return named, len(roles) - len(named)


def _gaps(register: dict[str, Any], members: list[str], slugs: set[str] | None
          ) -> dict[str, list[str]]:
    """The three gaps, each naming the members that carry it: a use `workspace.flagged` flags is
    No workaround, or Single source where the row is authored (its single source mark); a use
    whose cell states there is none is No workaround, authored or not, by B5's rule (447,
    `workspace.NO_WORKAROUND`); an owner the register says nobody holds is Owner missing."""
    found: dict[str, list[str]] = {}
    for k in members:
        row = register[k]
        for c in row.get("consumers") or []:
            said = bool(workspace.NO_WORKAROUND.search(str(c.get("workaround") or "")))
            if (slugs is None or c.get("department") in slugs) and (
                    said or workspace.flagged(row, c)):
                kind = SINGLE if c.get("authored") and not said else NO_WORKAROUND
                if shown(register, k) not in found.get(kind, []):
                    found.setdefault(kind, []).append(shown(register, k))
        if row.get("owner_gap"):
            found.setdefault(OWNER, []).append(shown(register, k))
    return {g: found[g] for g in GAPS if g in found}


def gap_items(register: dict[str, Any], boxes: dict[str, dict[str, Any]],
              inside: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    """345 Q1 (spec §10.10): each gap's register items company-wide, the drawn boxes' members and
    what the bands hold inside them, never the boxes drawn; with the boxes and the bands that
    carry one, so a count's tap lights them; and 359 D6's `rows`, each item [its name, the box
    holding it, else the band holding it inside], the gap tray's one line per item."""
    held = {k: b for b, ks in inside.items() for k in ks}
    box: dict[str, str] = {}
    for i, b in boxes.items():
        for m in b["members"]:
            box.setdefault(m, i)
    out: dict[str, dict[str, Any]] = {}
    for g in GAPS:
        found = sorted(k for k in held.keys() | box.keys() if g in _gaps(register, [k], None))
        out[g] = {"items": found,
                  "boxes": sorted(i for i, b in boxes.items() if set(found) & set(b["members"])),
                  "bands": sorted({held[k] for k in found if k in held}),
                  "rows": [[shown(register, k), box.get(k) or held[k]] for k in found]}
    return out


def _job(register: dict[str, Any], k: str) -> str | None:
    name = register[k].get("name")
    return next((j[0] for j in JOBS if name in j[2]), None)


def box_id(register: dict[str, Any], k: str, people: str = PEOPLE_ID) -> str:
    """The box a resource is drawn in, the same id company-wide (the People box is one per
    activity, so its id is given)."""
    kind = register[k].get("asset_type")
    if kind == ROLE:
        return people
    if kind == SITE:
        return SITES_ID
    job = _job(register, k)
    return f"job:{slug(job)}" if job else k


def _replaceable(row: dict[str, Any], use: dict[str, Any]) -> bool:
    """A firm the record's workaround replaces: a supplier whose (transcribed) row states one the
    one rule does not flag."""
    return (row.get("asset_type") == SUPPLIER and bool(use.get("workaround"))
            and not authored(use, "need") and not workspace.flagged(row, use))


def step_in(register: dict[str, Any]) -> dict[str, list[list[str]]]:
    """466 H1/H2: each activity's firms its record's workaround replaces (`this_bia`'s "Other firms
    can step in"), each [its full name, the record's words]; an activity with none is absent."""
    out: dict[str, list[list[str]]] = {}
    for k, a in items(register).items():
        for c in a.get("consumers") or []:
            if _depends(c) and not _job(register, k) and _replaceable(a, c):
                said = " ".join(own_words({"description": c["workaround"]}).split())
                out.setdefault(str(c.get("department")), []).append([str(a.get("name")), said])
    return {s: sorted(fs) for s, fs in out.items()}


def _place(name: str) -> str:
    return PLACES.get(name, "plant")


def place_words(names: Iterable[str]) -> str:
    """"3 plants · logistics centre · HR administration": the sites counted in his words."""
    kinds = [_place(n) for n in names]
    plants = kinds.count("plant")
    head = [f"{plants} plant{'s' if plants != 1 else ''}"] if plants else []
    return " · ".join(head + [p for p in PLACES.values() if p in kinds])


#: W1 (8_marschkamp, 2026-10-06): "site", as the records say it ("anderen Standort", BIA_2.0;
#: "alternativen Unternehmensstandort", HR 05.0), never "plant"
MOVES = "can move to another site"


def plant_words(register: dict[str, Any], boxes: dict[str, dict[str, Any]], plant: str,
                names: dict[str, str], slug: str | None = None) -> str:
    """A plant's words, the one copy (331 round 3; 334's Whole company imports it). Takeover is a
    property of an activity at a plant, its own site row's `takeover`, never of the plant. On This
    BIA (`slug`): "Runs: <it> and n other activities · <it> can move to another site: <its own>";
    on Whole company grouped by value (`_by_value`, 8_marschkamp's, t334b). Then
    "Site of: …", only where a drawn box's members are tagged there. `names`: the process map's."""
    said: dict[str, set[str]] = {}
    for c in register[plant].get("consumers") or []:
        said.setdefault(str(c.get("department")), set()).add(str(c.get("takeover") or "not stated"))
    own = {s: " / ".join(sorted(t)) for s, t in said.items()}
    if slug is None:
        head = [f"{MOVES.capitalize()}: {_by_value(own, names)}"]
    else:
        this, n = names.get(slug, slug), len(own.keys() - {slug})
        others = f" and {n} other activit{'y' if n == 1 else 'ies'}" if n else ""
        head = [f"Runs: {this}{others}",
                f"{this} {MOVES}: {own.get(slug, 'not stated')}"]
    tagged = [m for b in boxes.values() for m in b["sites"].get(plant, [])]
    return " · ".join(head + ([f"Site of: {', '.join(tagged)}"] if tagged else []))


def _by_value(own: dict[str, str], names: dict[str, str]) -> str:
    """Activities grouped by their own takeover, stated values first: "partly for Production and
    processing; not stated for the other 13". A group of three or fewer names its activities;
    a larger one counts them ("the other n" when last, "all n" when alone, else "n activities"),
    so each activity is counted exactly once."""
    groups: dict[str, list[str]] = {}
    for s, t in own.items():
        groups.setdefault(t, []).append(names.get(s, s))
    order = sorted(groups, key=lambda t: t == "not stated")

    def who(i: int, acts: list[str]) -> str:
        if len(acts) <= 3:
            return ", ".join(acts)
        n = len(acts)
        return f"all {n}" if len(order) == 1 else f"the other {n}" if i == len(order) - 1 \
            else f"{n} activities"
    return "; ".join(f"{t} for {who(i, groups[t])}" for i, t in enumerate(order))


def _tagged(register: dict[str, Any], members: list[str]) -> dict[str, list[str]]:
    """Each site a box's members are tagged to (their `site`), with the members tagged there: a
    site row is a tag, never an edge (spec §10.1.4); the strip names only the members of that
    site, never one claim for the box."""
    sites = {k: str(a.get("name")) for k, a in items(register).items()
             if a.get("asset_type") == SITE}
    out: dict[str, list[str]] = {}
    for k in members:
        at = register[k].get("site")
        for s, name in sites.items():
            if at and (name == at or name.split(" (")[0] == at):
                out.setdefault(s, []).append(shown(register, k))
    return out


def _fact(register: dict[str, Any], members: list[str], uses: dict[str, dict[str, Any]],
          name: str) -> str:
    """One mono fact: the recovery target the activity's own rows agree on, else "not recorded"
    for a box only of rows added in chat (318). 466 I2: a merge no longer shows itself here (A3):
    its "Merged from" names each record once."""
    targets = {str(f) for k in members if (f := (uses.get(k) or {}).get("rto"))}
    if len(targets) == 1 and name:
        return f"Recovery target {targets.pop()}"
    return NOT_RECORDED if not targets and all(
        register[k].get(walk.ADDED_IN_CHAT) for k in members) else ""


#: 3_nemo_design's read of 336 (C2, A1 as a rule): a box's why is one short line. A job the table
#: names carries its own authored why; any other box takes the first clause of its consumer row's
#: need, else of the record's description, when that clause is short, else no why line at all (the
#: record's own words stay whole in the strip). Never cut mid-sentence.
WHY_MAX = 45


def short_why(*texts: str) -> str:
    """The first short clause among the texts, whole, or "" when none is short."""
    for text in texts:
        text = " ".join(str(text or "").split())
        first = re.split(r"(?<=\w)[.;:,]\s|\s[–-]\s|\s\(", text, maxsplit=1)[0].rstrip(".")
        if first and len(first) <= WHY_MAX:
            return first
    return ""


def make_box(register: dict[str, Any], i: str, members: list[str], lines: list[str],
             uses: dict[str, dict[str, Any]], slugs: set[str] | None,
             all_marks: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """One box of the table: its name, column and plain why, one fact, its lines and marks, its
    gaps naming their members, its re-BIA lines, its sites and its "Needed by", and what it was
    merged from."""
    first = register[members[0]]
    job = next((j for j in JOBS if f"job:{slug(j[0])}" == i), None)
    why: str | None
    if i.startswith(PEOPLE_ID):
        name, col, why = "People", PEOPLE, "the people the work needs"
    elif i == SITES_ID:
        name, col, why = "Sites", BUILDINGS, "the buildings it runs at"
    elif job:
        name, col, why = job[0], job[1], job[3]
    else:
        name, col, why = shown(register, members[0]), KINDS.get(
            str(first.get("asset_type")), ICT), None
    need = (uses.get(members[0]) or {}).get("need")
    names = sorted(str(register[k]["name"]) for k in members)
    box: dict[str, Any] = {
        "name": name, "col": col,
        "why": why or short_why(own_words({"description": need}), own_words(first)),
        "desc": own_words(first) if len(members) == 1 else "",
        "fact": "" if col in (PEOPLE,) or i == SITES_ID else _fact(register, members, uses, name),
        "lines": sorted(str(register[k]["name"]) for k in lines),
        "said": sorted(supplies(register, k) for k in lines),
        # ADR-0048: the graph carries no demo mark; the register keeps `authored`
        "marks": [m["text"] for k in members for m in all_marks.get(k, [])],
        "gapNames": (gaps := _gaps(register, members, slugs)), "gaps": list(gaps),
        "rebia": [str(q) for k in members for q in register[k].get("quality_flags") or []
                  if str(q).startswith(REBIA)],
        # 359 (§12.20): the members a re-BIA finding names, the face's "re-BIA: <member>"
        "rebiaOf": sorted(shown(register, k) for k in members if any(
            str(q).startswith(REBIA) for q in register[k].get("quality_flags") or [])),
        "authored": all(authored(register[k], "description") for k in members),
        # 351 C1: a box of outside firms only, whose strip says so where it stands on nothing
        "outside": all(register[k].get("asset_type") == SUPPLIER for k in members),
        "merged": [] if names == [name] else names, "members": members,
        "types": _types(register, members),  # 466 I3
        "work": [] if i.startswith(PEOPLE_ID) or i == SITES_ID else _work(register, members, slugs),
        "sites": _tagged(register, members),
        "neededBy": [] if i == SITES_ID else needed_by(register, members),
        # §12.14's content read: "<n> activities depend on it, <d> directly"
        "direct": [] if i == SITES_ID else sorted({str(c.get("department")) for k in members
                                                  for c in register[k].get("consumers") or []
                                                  if _depends(c)})}
    if i.startswith(PEOPLE_ID):
        box["named"], box["more"] = key_roles(register, members, slugs or set())
        # 355 F7: a People box is its own activity's (a band's, its band's); a role others need
        # too says so, by their slugs
        own = slugs or set()
        box["neededBy"] = box["direct"] = sorted(own)
        box["also"] = {shown(register, k): others for k in members
                       if (others := sorted({str(c.get("department"))
                                             for c in register[k].get("consumers") or []}
                                            - own))}
    if i == SITES_ID:
        box["fact"] = place_words(str(register[k]["name"]) for k in members)
        box["plants"] = [{"id": k, "name": str(register[k]["name"]),
                          "takeover": sorted({str(c.get("takeover") or "not stated")
                                              for c in register[k].get("consumers") or []
                                              if slugs is None or c.get("department") in slugs}
                                             or {"not stated"})}
                         for k in members]
    return box


#: §12.14 F1: inside Buildings and utilities, Plant utilities, then Sites, then Power and network,
#: the deepest last; every other box keeps its place.
DEEPEST = (SITES_ID, FOUNDATION_ID)


def depth_rank(i: str) -> int:
    return DEEPEST.index(i) + 1 if i in DEEPEST else 0


def in_columns(boxes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The boxes column by column, the deepest last in their column (a stable sort, so the rest
    keep the table's order)."""
    return dict(sorted(boxes.items(), key=lambda kv: (COLUMNS.index(kv[1]["col"]),
                                                      depth_rank(kv[0]))))


def name_folds(register: dict[str, Any], boxes: dict[str, dict[str, Any]],
               company_boxes: dict[str, dict[str, Any]]) -> None:
    """355 F6 (spec §12.14, narrowed by §12.18 item 3): a fold, a job holding more than one member
    in the company's table, that holds one here shows that member's name and says what it is
    part of; an External providers' job names its supply and keeps its name ("Raw material")."""
    for i, b in boxes.items():
        job = next((j for j in JOBS if f"job:{slug(j[0])}" == i), None)
        if (job and job[1] != PROVIDERS and len(b["members"]) == 1
                and shown(register, b["members"][0]) != job[0]
                and len((company_boxes.get(i) or {}).get("members") or []) > 1):
            b["partOf"], b["name"], b["merged"] = b["name"], shown(register, b["members"][0]), []


def this_bia(register: dict[str, Any], slug_: str) -> dict[str, Any]:
    """What the laptop draws for one BIA, the same rules for every BIA (§9.2 as 336 re-cuts them):
    what the activity runs without and the firms its workaround replaces are listed, never drawn; a
    supplier nothing uses is a line on the box it supplies; every other resource it uses or stands
    on is drawn in its box of the table, every box (384)."""
    rows = items(register)
    uses = {k: c for k, a in rows.items() for c in a.get("consumers") or []
            if c.get("department") == slug_}
    left: dict[str, list[str]] = {RUNS_WITHOUT_RULE: [k for k, c in uses.items()
                                                      if not _depends(c)]}
    kept = [k for k in uses if k not in left[RUNS_WITHOUT_RULE]]
    left[FIRMS_RULE] = [k for k in kept if not _job(register, k)
                        and _replaceable(rows[k], uses[k])]
    kept = [k for k in kept if k not in left[FIRMS_RULE]]
    chain = beneath(register, kept)
    lined = {k for k in chain - set(kept) if rows[k].get("asset_type") == SUPPLIER
             and not _job(register, k)}
    left[LINES_RULE] = sorted(lined)
    box_of = {k: box_id(register, k) for k in sorted(chain - lined,
                                                     key=lambda k: str(rows[k].get("name")))}
    all_marks = marks(register)
    boxes = {}
    for i in dict.fromkeys(box_of.values()):
        members = [k for k, b in box_of.items() if b == i]
        lines = sorted({d for k in members for d in rows[k].get("depends_on") or [] if d in lined})
        boxes[i] = make_box(register, i, members, lines, uses, {slug_}, all_marks)
    drawn = in_columns(boxes)
    used = {box_of[k] for k in kept}
    level = levels(register, box_of, kept)
    reaches(register, drawn, {k: i for k, i in box_of.items() if i in drawn}, {slug_})
    by_level = level_bands(level, drawn)
    # A6, §10.1.3: the other activities that use (directly) a resource of a box this one draws
    others = {str(c.get("department")) for i, b in boxes.items() if i != SITES_ID
              for k in b["members"] for c in rows[k].get("consumers") or []}
    return {"boxes": drawn, "box_of": box_of,
            "cols": [c for c in COLUMNS if any(b["col"] == c for b in drawn.values())],
            "needs": sorted(used & set(drawn)),
            "deps": sorted({(box_of[a], box_of[d]) for a in box_of
                            for d in rows[a].get("depends_on") or []
                            if d in box_of and box_of[a] != box_of[d]
                            and box_of[a] in drawn and box_of[d] in drawn}),
            "notDrawn": [[rule, sorted(str(rows[k]["name"]) for k in ks)]
                         for rule, ks in left.items() if ks],
            "shared": len(others - {slug_}),
            "phone": bands(drawn), "levels": {i: level[i] for i in drawn},
            "phoneLevels": bands(drawn, by=by_level)}


def boxes_used(register: dict[str, Any], boxes: dict[str, dict[str, Any]], slugs: Iterable[str],
               people: str) -> list[str]:
    """332 round 2: the Whole company's boxes an activity (or a band, its activities) uses, one
    count at every width ("Uses n", "n with gaps"): each box of `boxes` holding what `this_bia`
    ties to it, its roles in its own People box `people`; Sites and the Foundation where its
    chain reaches them; a band's own systems are no box of the table, so they are not counted."""
    tied = {k for s in slugs for k in this_bia(register, s)["box_of"]}
    return sorted(i for i, b in boxes.items() if any(
        k in tied and (i == people if register[k].get("asset_type") == ROLE
                       else not i.startswith(PEOPLE_ID)) for k in b["members"]))


def _walk(at: dict[str, str], starts: list[str], nxt: Any) -> tuple[dict[str, str], list[str]]:
    """A breadth-first walk from the items along `nxt`: each drawn box first reached, with the
    nearest drawn box below it on that path; and every item reached, in order."""
    home = {at.get(k) for k in starts}
    via, said = {k: at.get(k, "") for k in starts}, {}
    todo = list(starts)
    while todo:
        x = todo.pop(0)
        for k in nxt(x):
            if k not in via:
                via[k], i = at.get(k) or via[x], at.get(k)
                todo.append(k)
                if i and i not in home and i not in said:
                    said[i] = via[x]
    return said, list(via)


def reach(register: dict[str, Any], at: dict[str, str], starts: Iterable[str]) -> dict[str, Any]:
    """Part D (D7): what these items reach, member by member along the register's edges, never
    box to box through a fold (a site row is a tag, never an edge): `up`, each drawn box (`at`, an
    item's box) holding an item that stands on one of them, with the box it is reached through;
    `down`, each one holding an item they stand on, likewise; `acts`, each activity depending on
    one of them, with the box of the item it uses ("" where that item is in no drawn box)."""
    rows = {k: a for k, a in items(register).items() if a.get("asset_type") != SITE}
    users: dict[str, list[str]] = {}
    for k, a in rows.items():
        for d in a.get("depends_on") or []:
            users.setdefault(d, []).append(k)
    starts = [k for k in starts if k in rows]
    up, above = _walk(at, starts, lambda x: users.get(x, []))
    down, below = _walk(at, starts, lambda x: [d for d in rows[x].get("depends_on") or []
                                           if d in rows])
    acts: dict[str, str] = {}
    for k in above:  # in the order reached, so each activity by its nearest path
        for c in rows[k].get("consumers") or []:
            if not waived(register, k, c):  # 408: what a click lights, by the one rule
                acts.setdefault(str(c.get("department")), at.get(k, ""))
    return {"up": _named(register, at, up, above), "down": _named(register, at, down, below),
            "acts": acts}


def _named(register: dict[str, Any], at: dict[str, str], said: dict[str, str],
           seen: list[str]) -> dict[str, list[str]]:
    """11_marschkamp: a fold reached through some of its members names them ("via Cold-chain
    temperature monitoring"), so a member it holds that stands on nothing here is never the path:
    each box, [the box it is reached through, those members or ""]."""
    part = {i: [shown(register, k) for k in seen if at.get(k) == i] for i in said}
    size = {i: sum(1 for j in at.values() if j == i) for i in said}
    return {i: [v, ", ".join(part[i]) if len(part[i]) < size[i] else ""] for i, v in said.items()}


def reaches(register: dict[str, Any], boxes: dict[str, dict[str, Any]], at: dict[str, str],
            slugs: set[str] | None) -> None:
    """Part D: each box's `reach` from all its members (a tap), and `gapReach` from the members
    carrying each of its gaps (a gap tile), both member by member (`reach`)."""
    for b in boxes.values():
        b["reach"] = reach(register, at, b["members"])
        b["gapReach"] = {g: reach(register, at, [k for k in b["members"]
                                                 if g in _gaps(register, [k], slugs)])
                         for g in b["gaps"]}


def bands(boxes: dict[str, dict[str, Any]], cap: int = BAND_BUDGET,
          by: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """The phone's cut (336, spec §10.10): bands by kind (or by `by`, each box's band, in the order
    first given), each at most `cap` tiles, gaps first, then the highest "Needed by"; the rest open
    under "+ n more". A gap tile is never the one cut: where a band's gap tiles alone pass the cap,
    the band shows them all and says by how much."""
    by = by or {i: b["col"] for i, b in boxes.items()}
    out: dict[str, dict[str, Any]] = {}
    for band in [*COLUMNS, *dict.fromkeys(by.values())]:
        ranked = sorted((i for i in boxes if by[i] == band),
                        key=lambda i: (depth_rank(i), not boxes[i]["gaps"],
                                       -len(boxes[i]["neededBy"]), boxes[i]["name"]))
        if not ranked or band in out:
            continue
        gapped = [i for i in ranked if boxes[i]["gaps"]]
        room = max(cap, len(gapped))
        over = len(gapped) - cap
        # 351r: the deepest box ranks last, so a cut never reaches it if it has a gap
        clear = [i for i in ranked if i not in gapped][:room - len(gapped)]
        shown = [i for i in ranked if i in gapped or i in clear]
        out[band] = {"shown": shown, "more": [i for i in ranked if i not in shown],
                     "overrun": max(0, over),
                     "reason": f"{over} gap boxes over budget" if over > 0 else None}
    return out


def item_levels(register: dict[str, Any], box_of: dict[str, str],
                starts: Iterable[str]) -> dict[str, int]:
    """374 (§12.24) and part D: each item's level, the longest chain from the activity to it,
    member by member along the register's own edges, never box to box through a fold: the items
    it uses at 1, a step into another box one deeper, a step inside one box none. A path never
    revisits an item, so a cycle ends it."""
    level: dict[str, int] = {}

    def walk(k: str, n: int, path: frozenset[str]) -> None:
        if level.get(k, 0) >= n:
            return
        level[k] = n
        for d in register[k].get("depends_on") or []:
            if d in box_of and d not in path:
                walk(d, n + (box_of[d] != box_of[k]), path | {d})
    for k in starts:
        walk(k, 1, frozenset([k]))
    return level


def levels(register: dict[str, Any], box_of: dict[str, str],
           starts: Iterable[str]) -> dict[str, int]:
    """Each box's level, the deepest of its members' (`item_levels`), over every box the table
    puts the chain in."""
    out: dict[str, int] = {}
    for k, n in item_levels(register, box_of, starts).items():
        out[box_of[k]] = max(out.get(box_of[k], 0), n)
    return out


def level_band(n: int) -> str:
    """A level's heading, the laptop's column and the phone's band (§12.24: plain "Level n", the
    strip's "<n> activities depend on it, <d> directly" carries the direct count)."""
    return f"Level {n}"


def level_bands(level: dict[str, int], ids: Iterable[str]) -> dict[str, str]:
    """Each drawn box's band, shallowest first, the drawn levels numbered without gaps (§12.24,
    6_nemo_design 2026-10-07: a level no drawn box sits at is skipped, so computed 1, 2, 4 read
    "Level 1", "Level 2", "Level 3")."""
    rank = {n: k for k, n in enumerate(sorted({level[i] for i in ids}), 1)}
    return {i: level_band(rank[level[i]]) for i in sorted(ids, key=lambda i: level[i])}


STRUCTURAL = (PEOPLE_ID, SITES_ID, FOUNDATION_ID)


def _groups(map_rows: list[Any],
            register: dict[str, Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """The core activities (the map's first group) and each other group as one band, named with
    its count; only the activities the register names."""
    used = {str(c.get("department")) for a in items(register).values()
            for c in a.get("consumers") or []}
    acts = [r for r in map_rows if r.slug in used]
    head = acts[0].group if acts else ""
    # 375 B (§12.25): all the map's processes are listed, a band's with no BIA (Walkable = no,
    # never in the register) after its BIAs, counted in its name
    bands_ = [{"id": f"band:{slug(g)}", "name": f"{g} ({len(rs) + len(none)})",
               "activities": [r.name for r in rs], "slugs": [r.slug for r in rs],
               "nobia": [r.name for r in none]}
              for g in dict.fromkeys(r.group for r in acts if r.group != head)
              for rs in [[r for r in acts if r.group == g]]
              for none in [[r for r in map_rows if r.group == g and not r.walkable
                            and r.slug not in used]]]
    return [r for r in acts if r.group == head], bands_


def _holders(register: dict[str, Any], drawn: dict[str, dict[str, str]],
             owner: dict[str, str]) -> dict[str, set[str]]:
    """Who holds each box: the activities (a band for its group's) that use one of its resources
    directly; a box only stood on (Sign-in under Microsoft 365) is held by those standing on it."""
    direct: dict[str, set[str]] = {}
    chained: dict[str, set[str]] = {}
    for s, box_of in drawn.items():
        for k, i in box_of.items():
            uses = any(c.get("department") == s for c in register[k].get("consumers") or [])
            (direct if uses else chained).setdefault(i, set()).add(owner[s])
    return {i: direct.get(i) or chained[i] for i in chained.keys() | direct.keys()}


def _company_levels(register: dict[str, Any], drawn: dict[str, dict[str, str]],
                    boxes: dict[str, dict[str, Any]]) -> dict[str, int]:
    """374 (§12.24): Whole company's levels, across all activities: each item at the deepest any
    activity's own chain reaches it (`item_levels`), a box at its deepest member's."""
    deepest: dict[str, int] = {}
    for s, box_of in drawn.items():
        starts = [k for k in box_of for c in register[k].get("consumers") or []
                  if c.get("department") == s and _depends(c)]
        for k, n in item_levels(register, box_of, starts).items():
            deepest[k] = max(deepest.get(k, 0), n)
    return {i: max(deepest[k] for k in b["members"]) for i, b in boxes.items()}


def _stood_on(rows: dict[str, Any], bands_: list[dict[str, Any]], every: dict[str, str],
              shared: list[str]) -> list[str]:
    """462 G1 (11_nemo_design's ruling, "never hide an edge"): the boxes drawn, and each band's own
    system a drawn box stands on, all the way down, drawn as its own box with its lines (Microsoft
    365 -> Sign-in), never a firm (a line on its box); the bands keep the rest as their own."""
    held = {i: [k for k, j in every.items() if j == i] for i in set(every.values())}
    drawn = {*shared, *STRUCTURAL}
    own = {i for b in bands_ for i in b["own"]
           if not all(rows[k].get("asset_type") == SUPPLIER for k in held[i])}
    while more := {j for j in own - drawn if set(held[j]) & {
            d for i in drawn for k in held.get(i, []) for d in rows[k].get("depends_on") or []}}:
        drawn |= more
    for b in bands_:
        b["own"] = [i for i in b["own"] if i not in drawn]
    return sorted(drawn - set(STRUCTURAL))


def company(map_rows: list[Any], register: dict[str, Any]) -> dict[str, Any]:
    """The whole company as the table draws it (draft 2 §B2): the core activities in flow order
    and each support group one band ("HR support processes (6)") holding the resources only it
    uses; one
    People box per core activity and per band; every box a core activity uses, or two bands share,
    drawn once; the Sites box and the Foundation; every box (384)."""
    rows = items(register)
    core, bands_ = _groups(map_rows, register)
    drawn = {r.slug: this_bia(register, r.slug)["box_of"] for r in core}
    drawn |= {s: this_bia(register, s)["box_of"] for b in bands_ for s in b["slugs"]}
    owner = {r.slug: r.slug for r in core} | {s: b["id"] for b in bands_ for s in b["slugs"]}
    holders = _holders(register, drawn, owner)
    every = {k: i for box_of in drawn.values() for k, i in box_of.items()}
    for b in bands_:
        b["own"] = sorted(i for i, h in holders.items() if h == {b["id"]} and i not in STRUCTURAL)
    all_marks = marks(register)
    boxes: dict[str, dict[str, Any]] = {}
    # 331 (28_nemo_check's ruling): each People box is named with its activity or band, never
    # several identical "People"
    for who, slugs, of in [(r.slug, {r.slug}, r.name) for r in core] + [
            (b["id"], set(b["slugs"]), re.sub(r" \(\d+\)$", "", b["name"])) for b in bands_]:
        roles = [k for k, i in every.items() if i == PEOPLE_ID
                 and any(c.get("department") in slugs for c in rows[k]["consumers"])]
        if not roles:  # 334: a box holds something, or it is not drawn
            continue
        boxes[f"people:{who}"] = make_box(register, f"people:{who}", roles, [], {}, slugs,
                                          all_marks)
        boxes[f"people:{who}"]["name"] = f"People · {of}"
    shared = sorted(i for i, h in holders.items() if i not in STRUCTURAL
                    and (any(not o.startswith("band:") for o in h) or len(h) > 1))
    shared = _stood_on(rows, bands_, every, shared)
    # 332: a room whose map names none of its activities draws no empty Sites or Foundation box
    for i in [*shared, *(s for s in (SITES_ID, FOUNDATION_ID) if s in every.values())]:
        members = [k for k, j in every.items() if j == i]
        if not members:  # 334: a room whose map names no activity, or that reaches no site
            continue
        lines = sorted({d for k in members for d in rows[k].get("depends_on") or []
                        if d not in every and rows.get(d, {}).get("asset_type") == SUPPLIER})
        boxes[i] = make_box(register, i, members, lines, {}, None, all_marks)
    inside = {b["id"]: [k for k, j in every.items() if j in b["own"]] for b in bands_}
    reaches(register, boxes, {k: i for i, b in boxes.items() if b["col"] != PEOPLE
                             for k in b["members"]}, None)
    lv = level_boxes(register, drawn, boxes, all_marks)
    by_level = level_bands(lv["levels"], lv["boxes"])
    return {"core": [r.name for r in core], "bands": bands_, "boxes": boxes, "inside": inside,
            "phone": bands(boxes), "gaps": gap_items(register, boxes, inside),
            "levelBoxes": lv["boxes"], "levels": lv["levels"],
            "phoneLevels": bands(lv["boxes"], by=by_level)}


def level_boxes(register: dict[str, Any], drawn: dict[str, dict[str, str]],
                boxes: dict[str, dict[str, Any]],
                all_marks: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """378 (his "Level by the longest chain", 2026-10-07): Whole company's level view draws every
    box, never cut: the table's boxes, each band's own system, and each outside firm a chain
    stands on its own box (on the other views a line on its box), at the longest chain
    (`item_levels`) across all activities."""
    rows = items(register)
    # a firm the activity uses itself (one its workaround replaces) is a box here too
    firms = {s: [k for k, a in rows.items() if a.get("asset_type") == SUPPLIER
                 and any(c.get("department") == s and _depends(c)
                         for c in a.get("consumers") or [])]
             for s in drawn}
    ext = {s: box_of | {k: box_id(register, k) for k in beneath(register, [*box_of, *firms[s]])
                        if k not in box_of and rows[k].get("asset_type") == SUPPLIER}
           for s, box_of in drawn.items()}
    every = {k: i for box_of in ext.values() for k, i in box_of.items()}
    out = {i: dict(b) for i, b in boxes.items()}
    for i in dict.fromkeys(sorted(every.values())):
        if i not in out and i != PEOPLE_ID:
            out[i] = make_box(register, i, [k for k, j in every.items() if j == i], [], {}, None,
                              all_marks)
    out = in_columns(out)
    reaches(register, out, {k: i for i, b in out.items() if b["col"] != PEOPLE
                            for k in b["members"]}, None)
    return {"boxes": out, "levels": _company_levels(register, ext, out)}
