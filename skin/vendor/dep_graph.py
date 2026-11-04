"""Dependency-graph derivation + layout + renderer (board Open item 9, DEP-01/OUT-01).

Pure core: build_graph/upstream_chain/downstream_chain/layout/_annotate/render_page do
no I/O. The CLI and the regen hook (graph_files) do the fetching. Spec:
/opt/brain/docs/superpowers/specs/2026-07-28-dependency-graph-design.md
"""
from __future__ import annotations

import datetime
import hashlib
import html as _html
import json
import re
from pathlib import Path

BASE_URL = "https://agent.ai4bcm.org/demo/graph"
PUBLIC = Path(__file__).resolve().parent / "public" / "graph"
# One source of truth: render_page writes the island behind this tag and the publish guard
# in generate() reads the previous page back through it.
_ISLAND_TAG = '<script type="application/json" id="data-graph">'

_ASSET_FIELDS = ("name", "asset_type", "bereich", "owner_name", "criticality", "rto",
                 "rpo", "mtpd", "spof", "redundancy", "supplier", "contract_status")


def resolve_dependency_ids(register: dict, requested_ids: list[str]) -> dict[str, list[str]]:
    """Resolve exact register keys without turning guesses into graph dependencies.

    Metadata and other non-object root values are not assets.  Ordering follows the activity's
    structured proposal so the persisted analysis and its deterministic rendering remain stable.
    """
    assets = {
        asset_id: entry
        for asset_id, entry in register.items()
        if (
            isinstance(asset_id, str)
            and isinstance(entry, dict)
            and entry.get("asset_id") == asset_id
        )
    }
    resolved = [asset_id for asset_id in requested_ids if asset_id in assets]
    unknown = [asset_id for asset_id in requested_ids if asset_id not in assets]
    missing_owners = [
        asset_id
        for asset_id in resolved
        if not str(assets[asset_id].get("owner_name") or "").strip()
    ]
    return {
        "resolved": resolved,
        "unknown": unknown,
        "missing_owners": missing_owners,
    }


# The sha of this module's own source, captured AT IMPORT — deliberately not at render
# time. A long-lived service holds the module it imported at start; if the file on disk
# changes afterwards the process keeps rendering the old code, and reading the file at
# render time would report the NEW sha and hide exactly that. Cost three days on
# 2026-07-31: the fold and canvas-height fixes landed 2h42m after the service started,
# every save-triggered regeneration silently reverted the published page, and the page
# said nothing about which code drew it.
# Since the asset split (2026-08-18) the renderer is three files — the module plus graph.css
# and graph.js — so the stamp hashes all three, or an edited graph.js would ship as "fresh".
_HERE = Path(__file__).resolve().parent


def _source_sha() -> str:
    h = hashlib.sha256()
    for name in ("dep_graph.py", "graph.css", "graph.js"):
        h.update((_HERE / name).read_bytes())
    return h.hexdigest()[:8]


_RENDERER_SHA = _source_sha()


def _renderer_stamp() -> str:
    """Provenance fragment naming the renderer, and shouting when it is stale."""
    try:
        on_disk = _source_sha()
    except OSError:  # source moved or unreadable — the loaded sha is still the truth
        on_disk = _RENDERER_SHA
    if on_disk == _RENDERER_SHA:
        return f' · renderer <code>{_RENDERER_SHA}</code>'
    return (f' · renderer <code>{_RENDERER_SHA}</code> — <strong>STALE: '
            f'<code>{on_disk}</code> is on disk. Restart the service to load it.</strong>')


def build_graph(register: dict, record: dict | None = None) -> dict:
    nodes, edges = [], []
    assets = {k: v for k, v in register.items() if isinstance(v, dict)}
    for aid, a in assets.items():
        node = {"id": aid, "kind": "asset",
                "owner_missing": not a.get("owner_name"),
                "pp4_issue": bool(a.get("pp4_issue")),
                "quality_flag_count": len(a.get("quality_flags") or [])}
        node.update({f: a.get(f) for f in _ASSET_FIELDS})
        nodes.append(node)
        for dep in a.get("depends_on") or []:
            edges.append({"src": aid, "dst": dep, "kind": "depends_on"})
            if dep not in assets and not any(n["id"] == dep for n in nodes):
                # D7: dangling register-side dep — mirror the record-side unmodeled
                # branch below so it's a visible node instead of a silently dropped edge.
                nodes.append({"id": dep, "kind": "unmodeled"})
    seen_procs = {}
    for aid, a in assets.items():
        for c in a.get("consumers") or []:
            key = f"proc:{c.get('dept')}:{c.get('activity')}"
            if key not in seen_procs:
                seen_procs[key] = {"id": key, "kind": "process", "dept": c.get("dept"),
                                   "activity": c.get("activity"), "need": c.get("need"),
                                   "consumer_mtpd": c.get("consumer_mtpd")}
                nodes.append(seen_procs[key])
            edges.append({"src": aid, "dst": key, "kind": "consumes"})
    for act in (record or {}).get("activities", []):
        # Referee-validated records carry name/owner and no id at all — tolerate both
        # vocabularies the way _crit_class does, never degrade to the act:? stub.
        act_id = f"act:{act.get('id') or act.get('name') or '?'}"
        # `dept` is the only field that can line a BIA activity up against the register's
        # own consumers lines, which carry a dept and nothing else in common. Optional:
        # records written before 2026-07-31 have none, and an absent dept must stay absent
        # rather than becoming an empty claim (see _annotate).
        nodes.append({"id": act_id, "kind": "activity", "name": act.get("name"),
                      "owner_name": act.get("owner_name") or act.get("owner"),
                      "dept": act.get("dept"),
                      "mtpd": act.get("mtpd"),
                      "recovery_target": act.get("recovery_target")})
        for dep in act.get("dependencies") or []:
            if isinstance(dep, dict):
                dep = dep.get("id")
            if not isinstance(dep, str):
                continue  # id-less dep = unmodeled BIA finding
            if dep not in assets and not any(n["id"] == dep for n in nodes):
                nodes.append({"id": dep, "kind": "unmodeled"})
            edges.append({"src": act_id, "dst": dep, "kind": "activity_dep"})
    # The register's own data-classification marker, carried through so the page can caption
    # itself honestly. It is a bool at the register root, so the assets comprehension above
    # already skips it; this is the only thing that reads it.
    return {"nodes": nodes, "edges": edges, "synthetic": bool(register.get("synthetic"))}


def layout(graph: dict) -> dict:
    """Variant-A layered columns: providers left of dependents, activities then
    processes right of all assets, rows stable-sorted by (bereich, id)."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    deps: dict[str, list[str]] = {}  # dependent -> providers
    for e in graph["edges"]:
        if e["kind"] == "depends_on" and e["dst"] in by_id:
            # Grouped view: an edge onto the foundation strip is a card's "runs on" mark,
            # not a step of depth, so the columns count depth above the foundation.
            if by_id[e["dst"]].get("foundation") and not by_id[e["src"]].get("foundation"):
                continue
            deps.setdefault(e["src"], []).append(e["dst"])
    assets = [n for n in graph["nodes"] if n["kind"] in ("asset", "unmodeled")]
    # ponytail: O(n²) reachability + SCC-by-mutual-reach — register-scale graphs
    # (dozens of assets); switch to Tarjan if a register ever grows past that.
    reach: dict[str, set[str]] = {}
    for n in assets:
        seen: set[str] = set()
        stack = list(deps.get(n["id"], []))
        while stack:
            p = stack.pop()
            if p not in seen:
                seen.add(p)
                stack.extend(deps.get(p, []))
        reach[n["id"]] = seen

    def scc(aid: str) -> frozenset:
        mutual = {b for b in reach.get(aid, set()) if aid in reach.get(b, set())}
        return frozenset(mutual | {aid})

    depth_cache: dict[frozenset, int] = {}

    def gdepth(group: frozenset) -> int:
        # Condensed over SCCs the graph is a DAG, so plain recursion terminates
        # and every cycle member shares one column.
        if group not in depth_cache:
            providers = {scc(p) for a in group for p in deps.get(a, []) if p not in group}
            depth_cache[group] = 1 + max((gdepth(pg) for pg in providers), default=-1)
        return depth_cache[group]

    for n in assets:
        n["col"] = gdepth(scc(n["id"]))
    max_col = max((n["col"] for n in assets if not n.get("foundation")), default=0)
    for n in graph["nodes"]:
        if n["kind"] == "activity":
            n["col"] = max_col + 1
        elif n["kind"] == "process":
            n["col"] = max_col + 2
    for col in {n["col"] for n in graph["nodes"]}:
        # A foundation card keeps its own depth as its place along the strip (providers
        # left); _geometry puts the strip under the columns.
        members = sorted((n for n in graph["nodes"] if n["col"] == col
                          and not n.get("foundation")),
                         key=lambda n: (n.get("frame_rank", 0), n.get("frame") or "",
                                        n.get("bereich") or "", n["id"]))
        for row, n in enumerate(members):
            n["row"] = row
    return graph


# ── collapsed consumer layout (canonical since 2026-07-29) ───────────────────────────
# Runs AFTER layout() and only moves col/row or adds one derived node. Chosen over the
# full column and the wrapped column in the A/B/C evaluation — the measurements and
# the rejected alternatives are recorded in docs/graph-abc-layout-variants.md (git history,
# retired 2026-08-18).


def collapse_processes(graph: dict) -> dict:
    """The base view answers asset structure; consumers fold out on demand.

    Every process keeps its island entry AND its card: `collapsed` nodes render into a
    dept-sorted fold band below the graph (see _geometry) that CSS hides until the
    active lens keeps them — aufklappen, the expected behaviour named in KG's first
    live review. Focus an asset and its consumers unfold connected by their real
    edges; focus the group card and the whole band opens. The group card stays the
    base view's single stand-in, with one bundled fan edge per feeding asset."""
    procs = [n for n in graph["nodes"] if n["kind"] == "process"]
    if not procs:
        return graph
    gid = "group:processes"
    proc_ids = {p["id"] for p in procs}
    for p in procs:
        p["collapsed"] = True
        # A collapsed process is reached from the facts panel, and its visible answer is
        # the asset→consumers path: chain assets light anyway, keep_extra lights the
        # group card too, which sets the fan edges from its feeders hot.
        p["keep_extra"] = [gid]
    # The bundled fan: one consumes edge per feeding asset, ending at the group card.
    # Without it the consumer side reads as severed — the first live review's actual
    # finding. Feeders keep the group on focus (their fan edge goes hot), and the group
    # keeps its feeders, so clicking the summary answers "what feeds the consumers".
    feeders = sorted({e["src"] for e in graph["edges"]
                      if e["kind"] == "consumes" and e["dst"] in proc_ids})
    for n in graph["nodes"]:
        if n["id"] in feeders:
            n["keep_extra"] = [gid]
    graph["edges"] += [{"src": a, "dst": gid, "kind": "consumes"} for a in feeders]
    depts = {p["dept"] for p in procs if p.get("dept")}
    graph["nodes"].append({
        "id": gid, "kind": "process_group",
        "name": f"{len(procs)} dependent activities",
        "dept_count": len(depts),
        # Dept-sorted so the facts list reads as grouped blocks, not island build order.
        "procs": [p["id"] for p in sorted(procs,
                                          key=lambda p: (p.get("dept") or "", p["id"]))],
        "keep_extra": feeders,
        "col": procs[0]["col"], "row": 0})
    return graph


# ── grouped view (nemo ticket 146; opt-in, runs between build_graph and layout) ──────
# Presentation only: no edge is added, and every register edge stays findable on the page.
# A graph that never passes through group_view renders exactly as before.


def group_view(graph: dict, register: dict) -> dict:
    """Roles leave the canvas and become a People line on the activities they work in, and
    every other asset card sits in a labelled frame. The columns stay the dependency levels
    and every edge stays an arrow: levels win over groups (nemo ticket 149, the owner's
    ruling of 2026-09-23), so a frame holds one group at one level."""
    for n in graph["nodes"]:
        if n["kind"] == "asset" and isinstance(register.get(n["id"]), dict):
            if register[n["id"]].get("platform"):
                n["platform"] = register[n["id"]]["platform"]
                n["platform_authored"] = bool(register[n["id"]].get("platform_authored"))
    # A role with a dependency edge either way stays a card: moving it would hide the edge.
    linked = {x for e in graph["edges"] if e["kind"] == "depends_on" for x in (e["src"], e["dst"])}
    roles = {n["id"]: n for n in graph["nodes"]
             if n["kind"] == "asset" and str(n.get("asset_type") or "").lower() == "role"
             and n["id"] not in linked}
    # The register's consumers line (role → dependent activity) and the record's own
    # dependency list (BIA activity → role) are the only links read; nothing is matched by name.
    people: dict[str, list[str]] = {}
    for e in graph["edges"]:
        if e["kind"] == "consumes" and e["src"] in roles:
            people.setdefault(e["dst"], []).append(roles[e["src"]].get("name") or e["src"])
        elif e["kind"] == "activity_dep" and e["dst"] in roles:
            people.setdefault(e["src"], []).append(roles[e["dst"]].get("name") or e["dst"])
    for n in graph["nodes"]:
        if n["id"] in people:
            n["people"] = people[n["id"]]
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] not in roles]
    graph["edges"] = [e for e in graph["edges"] if e["src"] not in roles and e["dst"] not in roles]
    _mark_frames(graph)
    _mark_what_stands(graph, register)
    graph["grouped"] = True
    return graph


AUTHORED_ASSET_MARK = ("Written for the demo pack,", "not in any prior record")
BACKUP_MARK = "(written for the demo pack)"


def _mark_what_stands(graph: dict, register: dict) -> None:
    """Each asset card's extra lines (nemo ticket 150): how many stand on it, its red flag, the
    marked backup of the asset it backs up, and the plain-words mark on an authored asset. Read
    from stand_on and the register; no edge is added or removed."""
    stands = stand_on(register)
    names = {n["id"]: n.get("name") or n["id"] for n in graph["nodes"]}
    backups: dict[str, list[str]] = {}
    for aid, a in register.items():
        if isinstance(a, dict):
            for b in a.get("backup_for") or []:
                backups.setdefault(b, []).append(a.get("name") or aid)
    for n in graph["nodes"]:
        if n["kind"] != "asset" or not isinstance(register.get(n["id"]), dict):
            continue
        lines = []
        s = stands.get(n["id"])
        if s:
            lines.append(("stand", f"{s['count']} stand on this"))
            f = s["flag"]
            if f:
                who, rto = names.get(f["dependant"], f["dependant"]), f["dependant_rto"]
                # The case and the figure on one line, the dependant's name alone on the next, so
                # the truncation a long name may need never eats the figure.
                lines += [("red-flag", f"⚑ No RTO; {rto} needed by" if f["case"] == "no RTO"
                           else f"⚑ RTO {s['rto']} longer; {rto} for"), ("red-flag", who)]
        for b in backups.get(n["id"], []):
            lines += [("backup", f"backup: {b}"), ("backup", BACKUP_MARK)]
        if register[n["id"]].get("authored"):
            lines += [("authored", t) for t in AUTHORED_ASSET_MARK]
        if lines:
            n["lines"] = lines


STANDALONE = "Standalone"
AUTHORED_MARK = "(grouped for the demo)"


def _mark_frames(graph: dict) -> None:
    """Each asset card's frame: the register's `platform` with its asset_type (sub-category
    within main category), else its asset_type alone; assets with no dependency edge either
    way form one Standalone frame. A frame is a label
    and a box, never an edge."""
    linked = {x for e in graph["edges"] if e["kind"] == "depends_on" for x in (e["src"], e["dst"])}
    for n in graph["nodes"]:
        if n["kind"] != "asset":
            continue
        kind = n.get("asset_type") or ""
        if n.get("platform"):
            n["frame"] = " · ".join(x for x in (n["platform"], kind) if x)
            if n.get("platform_authored"):  # no record states this grouping
                n["frame"] += f" {AUTHORED_MARK}"
            rank = 0
        elif n["id"] not in linked:
            n["frame"], rank = STANDALONE, 2
        else:
            n["frame"], rank = kind or "Other", 1
        n["frame_rank"] = rank


_RTO = re.compile(r"^\s*([<>]?)\s*(\d+(?:[.,]\d+)?)\s*(h|hours?|d|days?|w|weeks?)\s*$", re.I)
_RTO_HOURS = {"h": 1, "d": 24, "w": 168}


def _rto_hours(value) -> float | None:
    """A record's RTO in hours, for ordering only ('>168 h' sorts just past 168 h, '<24 h' just
    short of 24 h); None when there is none or it does not read as a time."""
    m = _RTO.match(str(value or ""))
    if not m:
        return None
    hours = float(m[2].replace(",", ".")) * _RTO_HOURS[m[3][0].lower()]
    return hours + {">": 0.5, "<": -0.5}.get(m[1], 0)


def _shortest_rto(entry: dict) -> str | None:
    """The shortest RTO any record gives the asset: its own, or a consumer row's where records differ."""
    stated = [entry.get("rto")] + [c.get("rto") for c in entry.get("consumers") or [] if isinstance(c, dict)]
    timed = [(_rto_hours(v), v) for v in stated if _rto_hours(v) is not None]
    return min(timed)[1] if timed else None


def stand_on(register: dict) -> dict[str, dict]:
    """What stands on each non-role asset (nemo ticket 150), from the register alone.

    `count`: the non-role assets that depend on it, directly or through others, over the
    register's `depends_on` edges. `rto`: the shortest RTO a record gives it, or None. `flag`, on a
    provider (count > 0) only: {"case": "no RTO"} when some asset standing on it has an RTO and it
    has none, else {"case": "longer RTO"} when its RTO is longer than a dependant's; either names
    the dependant with the shortest RTO as the one that triggers it. Shown, never fixed: no figure
    is changed. A backup (`backup_for`) is not in the edges, so it gets no entry, and neither does a role."""
    assets = {k: v for k, v in register.items() if isinstance(v, dict)}
    counted = {k for k, v in assets.items()
               if str(v.get("asset_type") or "").lower() != "role" and not v.get("backup_for")}
    above: dict[str, set[str]] = {k: set() for k in assets}  # provider -> direct dependants
    for k, v in assets.items():
        for d in v.get("depends_on") or []:
            above.setdefault(d, set()).add(k)
    out = {}
    for aid in sorted(counted):
        seen, stack = set(), list(above.get(aid, ()))
        while stack:
            x = stack.pop()
            if x not in seen:
                seen.add(x)
                stack.extend(above.get(x, ()))
        dependants = seen & counted
        own = _shortest_rto(assets[aid])
        timed = sorted((_rto_hours(_shortest_rto(assets[d])), d) for d in dependants
                       if _shortest_rto(assets[d]) is not None)
        flag = None
        if timed and own is None:
            flag = {"case": "no RTO", "dependant": timed[0][1]}
        elif timed and timed[0][0] < _rto_hours(own):
            flag = {"case": "longer RTO", "dependant": timed[0][1]}
        if flag:
            flag["dependant_rto"] = _shortest_rto(assets[flag["dependant"]])
        out[aid] = {"count": len(dependants), "rto": own, "flag": flag}
    return out


def upstream_chain(graph: dict, asset_id: str) -> list[dict]:
    by_id = {n["id"]: n for n in graph["nodes"]}
    dep_edges = [(e["src"], e["dst"]) for e in graph["edges"] if e["kind"] == "depends_on"]
    chain, seen, frontier, depth = [], {asset_id}, [asset_id], 0
    while frontier:
        depth += 1
        frontier = [d for s, d in dep_edges if s in frontier and d not in seen]
        for d in dict.fromkeys(frontier):  # stable order, dedupe within level
            seen.add(d)
            n = by_id.get(d, {})
            chain.append({"id": d, "depth": depth, "spof": bool(n.get("spof")),
                          "owner_missing": bool(n.get("owner_missing"))})
    return chain


def downstream_chain(graph: dict, asset_id: str) -> list[dict]:
    """Mirror of upstream_chain over reversed depends_on edges: the transitive
    dependents of asset_id (its blast radius) instead of the providers it needs."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    dep_edges = [(e["src"], e["dst"]) for e in graph["edges"] if e["kind"] == "depends_on"]
    chain, seen, frontier, depth = [], {asset_id}, [asset_id], 0
    while frontier:
        depth += 1
        frontier = [s for s, d in dep_edges if d in frontier and s not in seen]
        for d in dict.fromkeys(frontier):  # stable order, dedupe within level
            seen.add(d)
            n = by_id.get(d, {})
            chain.append({"id": d, "depth": depth, "spof": bool(n.get("spof")),
                          "owner_missing": bool(n.get("owner_missing"))})
    return chain


def _annotate(graph: dict) -> dict:
    """Precompute per-node island fields — id-lists only, no dicts, so the JSON island
    stays small. The JS reads these directly; it never re-derives edges or re-maps the
    criticality vocabulary itself. assets: chain (upstream ids), impact (downstream ids,
    via downstream_chain), procs + acts (direct consumers/activity dependents), crit
    (canonical _crit_class word). processes: feeds (direct assets) + chain (feeds then
    their upstream, deduped). activities: chain (unchanged). unmodeled: impact + acts."""
    # procs means consuming PROCESSES: variant B's bundled fan edges are also kind
    # "consumes" but end at the group card, and without this filter every feeding
    # asset listed the group as one of its own consumers in the facts panel.
    process_ids = {n["id"] for n in graph["nodes"] if n["kind"] == "process"}
    for n in graph["nodes"]:
        kind = n["kind"]
        if kind == "asset":
            n["chain"] = [c["id"] for c in upstream_chain(graph, n["id"])]
            n["impact"] = [c["id"] for c in downstream_chain(graph, n["id"])]
            n["procs"] = [e["dst"] for e in graph["edges"]
                          if e["kind"] == "consumes" and e["src"] == n["id"]
                          and e["dst"] in process_ids]
            n["acts"] = [e["src"] for e in graph["edges"]
                        if e["kind"] == "activity_dep" and e["dst"] == n["id"]]
            n["crit"] = _crit_class(n.get("criticality"))
        elif kind == "activity":
            direct = [e["dst"] for e in graph["edges"]
                      if e["kind"] == "activity_dep" and e["src"] == n["id"]]
            chain = list(dict.fromkeys(direct))
            for d in direct:
                chain += [c["id"] for c in upstream_chain(graph, d) if c["id"] not in chain]
            n["chain"] = chain
            # The reconciliation the missing dept used to make impossible: the register's
            # consumers lines for this activity's own department. A ROLLUP, not a
            # dependency — the same operation described once per resource it needs — so it
            # gets a facts-panel section and no edge. The canvas axis promises dependency
            # depth (see _column_labels), and part-of does not belong on it.
            if n.get("dept"):
                n["dept_acts"] = [p["id"] for p in graph["nodes"]
                                  if p["kind"] == "process" and p.get("dept") == n["dept"]]
        elif kind == "process":
            feeds = list(dict.fromkeys(e["src"] for e in graph["edges"]
                                       if e["kind"] == "consumes" and e["dst"] == n["id"]))
            n["feeds"] = feeds
            chain = list(feeds)
            for f in feeds:
                chain += [c["id"] for c in upstream_chain(graph, f) if c["id"] not in chain]
            n["chain"] = chain
        elif kind == "unmodeled":
            n["impact"] = [c["id"] for c in downstream_chain(graph, n["id"])]
            n["acts"] = [e["src"] for e in graph["edges"]
                        if e["kind"] == "activity_dep" and e["dst"] == n["id"]]
    return graph


# ── renderer ─────────────────────────────────────────────────────────────────────────
_NODE_W, _COL_GAP, _SPACER, _MARGIN = 200, 40, 48, 24
_KIND_H = {"asset": 64, "unmodeled": 64, "activity": 56, "process": 44}
_KIND_PITCH = {"asset": 88, "unmodeled": 88, "activity": 72, "process": 54}
_HEAD_BAND, _HEAD_BASE = 32, 13  # strip reserved above row 0, and the header baseline in it
# The grouped view's cards carry one more line (People on activities, "runs on" on assets).
_GROUPED_H = {"asset": 78, "unmodeled": 64, "activity": 70, "process": 58}
_GROUPED_PITCH = {"asset": 100, "unmodeled": 88, "activity": 86, "process": 68}
_STRIP_HEAD = 44  # the gap above the foundation strip that holds its label
_FRAME_HEAD, _FRAME_PAD = 24, 6  # a frame's label band, and its margin round the cards


def _crit_class(v) -> str:
    """Status mapping for both register vocabularies: 'critical'/'high' and 1/2."""
    s = str(v).strip().lower()
    if s in ("critical", "1"):
        return "critical"
    if s in ("high", "2"):
        return "high"
    return "standard"


def _geometry(graph: dict) -> dict:
    """Pixel geometry from the abstract grid — presentation only. Empty reserved
    columns collapse to a thin spacer and the dense consumer column gets a tighter
    pitch; the layout()-assigned cols/rows never change."""
    if not graph["nodes"]:
        return {}
    kind_h, pitch = ((_GROUPED_H, _GROUPED_PITCH) if graph.get("grouped")
                     else (_KIND_H, _KIND_PITCH))
    strip = sorted((n for n in graph["nodes"] if n.get("foundation")),
                   key=lambda n: (n["col"], n["id"]))
    occupied = {n["col"] for n in graph["nodes"] if not n.get("foundation")}
    col_x, x = {}, _MARGIN
    for c in range(max(occupied) + 1):
        col_x[c] = x
        x += (_NODE_W + _COL_GAP) if c in occupied else _SPACER
    # Grouped view: each frame in a column opens with a band for its label.
    frame_gap = {}
    if graph.get("grouped"):
        for c in occupied:
            seen: list[str] = []
            for n in sorted((n for n in graph["nodes"] if n["col"] == c and n.get("frame")
                             and not n.get("foundation")), key=lambda n: n["row"]):
                if n["frame"] not in seen:
                    seen.append(n["frame"])
                frame_gap[n["id"]] = sum(_frame_head(f) for f in seen)
    # Grouped view: a card with extra lines (ticket 150) is taller, and pushes the cards below it down.
    line_gap = {}
    if graph.get("grouped"):
        for c in occupied:
            below = 0
            for n in sorted((n for n in graph["nodes"] if n["col"] == c and not n.get("foundation")),
                            key=lambda n: n["row"]):
                line_gap[n["id"]] = below
                below += _extra_h(n)
    geo = {n["id"]: (col_x[n["col"]],
                     _MARGIN + _HEAD_BAND + n["row"] * pitch.get(n["kind"], 88)
                     + frame_gap.get(n["id"], 0) + line_gap.get(n["id"], 0),
                     _NODE_W, kind_h.get(n["kind"], 64) + _extra_h(n))
           for n in graph["nodes"] if not n.get("collapsed") and not n.get("foundation")}
    if strip:  # one row under every column, headed by its own label (_strip_svg)
        strip_y = max((y + h for _x, y, _w, h in geo.values()), default=_MARGIN) + _STRIP_HEAD
        for i, n in enumerate(strip):
            geo[n["id"]] = (_MARGIN + i * (_NODE_W + _COL_GAP), strip_y, _NODE_W,
                            kind_h["asset"])
    # Collapsed nodes fold out (aufklappen) into a static band hanging RIGHT-ALIGNED
    # below the group card's region — never under the depth columns, which read as part
    # of the left-to-right dependency axis (KG's third live review). Two columns filling
    # top-down keep the dept-sorted order contiguous, the band's left edge stays right
    # of the asset block, and the canvas width never grows, so the base view keeps its
    # scale. The cards ship in the SVG and CSS hides them until the active lens keeps
    # them — geometry stays Python's, visibility the lens's.
    folded = sorted((n for n in graph["nodes"] if n.get("collapsed")),
                    key=lambda n: (n.get("dept") or "", n["id"]))
    if folded:
        right_edge = max((x + w for x, _y, w, _h in geo.values()),
                         default=_MARGIN + _NODE_W)
        x0 = right_edge - 2 * _NODE_W - _COL_GAP
        # The band docks directly under the group card (KG: the cards unfold as if they
        # were part of it) — so it clears only the cards it actually sits under, the
        # ones overlapping its own x-range, not the whole asset block. Anchoring on the
        # global bottom left a huge empty gap between card and content.
        band_y = max((y + h for x, y, w, h in geo.values() if x + w > x0),
                     default=_MARGIN) + 16
        per = -(-len(folded) // 2)  # ceil: left column takes the odd card
        for i, n in enumerate(folded):
            c, r = divmod(i, per)
            geo[n["id"]] = (x0 + c * (_NODE_W + _COL_GAP),
                            band_y + r * pitch["process"],
                            _NODE_W, kind_h["process"])
    return geo


_LINE_H = 14


def _extra_h(n: dict) -> int:
    """The height a card's extra lines add: the grouped asset card already holds one line."""
    return _LINE_H * max(len(n.get("lines") or ()) - 1, 0)


def _column_labels(graph: dict) -> dict[int, str]:
    """The horizontal axis, said out loud — one header per OCCUPIED column, read off the
    cols layout() already assigned and never recomputed.

    Position encodes dependency depth and nothing else, which is exactly what a reader
    cannot see: SPOF cards sit in the leftmost column and in the middle, so the axis gets
    read as a category and then contradicted. For an asset the column index IS the depth by
    construction (layout() sets col = gdepth), so the label is the depth; activities and
    processes get columns of their own, so those are named for what they hold.

    A column is labelled for the kind that dominates it. asset and unmodeled cards share the
    depth label, and layout() puts every activity and process strictly right of every asset
    column, so a column can never mix two label FAMILIES — there is no mixed case for the
    legend to explain."""
    labels = {}
    above = any(n.get("foundation") for n in graph["nodes"])  # grouped view with a strip
    for col in sorted({n["col"] for n in graph["nodes"] if not n.get("foundation")}):
        kinds = [n["kind"] for n in graph["nodes"] if n["col"] == col
                 and not n.get("foundation")]
        top = max(set(kinds), key=lambda k: (kinds.count(k), k))  # ties break deterministically
        labels[col] = ("Dependent activities" if top in ("process", "process_group")
                       else "BIA activities" if top == "activity"
                       else ("Nothing above the foundation" if above
                             else "No upstream dependencies") if col == 0
                       else f"{col} level{'s' if col > 1 else ''} above the foundation" if above
                       else f"Depends on {col} level{'s' if col > 1 else ''}")
    return labels

# The page's CSS and JS are asset files beside this module, inlined at import so the
# rendered page stays self-contained (no external request — pinned by
# test_render_page_is_self_contained_and_noindex). Edit graph.css / graph.js, not this file.
_CSS = (_HERE / "graph.css").read_text(encoding="utf-8")
_JS = (_HERE / "graph.js").read_text(encoding="utf-8")
# The grouped view's own rules, appended only to a page group_view drew, so every other page
# keeps exactly the CSS it had. Kept here, not in graph.css, for that reason.
_GROUPED_CSS = """
.frame rect { fill: #f8fafc; stroke: #cbd5e1; stroke-width: 1; stroke-dasharray: 4 3; }
.frame text { fill: #475569; font-size: 11px; font-weight: 600; pointer-events: none; }
.node.foundation rect.box { fill: #f1f5f9; }
.node text.runs-on, .node text.people { fill: #334155; font-size: 11px; }
.node text.stand, .node text.backup, .node text.authored { fill: #334155; font-size: 11px; }
.node text.backup, .node text.authored { font-style: italic; }
.node text.red-flag { fill: #b91c1c; font-size: 11px; font-weight: 600; }
"""

# ponytail: vanilla JS, no layout logic — Python precomputed cols/rows/chains; the JS
# only toggles classes and fills the facts panel from the JSON island.



def _esc(v) -> str:
    return _html.escape(str(v)) if v is not None else ""


def _trunc(s: str, n: int = 26) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"  # never a space before the ellipsis


def _node_svg(n: dict, geo: dict) -> str:
    x, y, w, h = geo[n["id"]]
    kind = n["kind"]
    classes = ["node", kind]
    if n.get("collapsed"):
        classes.append("folded")  # hidden until the active lens keeps it
    label = n.get("name") or n.get("activity") or n["id"]
    sub = n["id"]
    if kind == "asset":
        crit = _crit_class(n.get("criticality"))
        classes.append(crit)
        if n.get("foundation"):
            classes.append("foundation")
        crit_label = crit if n.get("criticality") is not None else "unrated"
        # The id and the criticality decide an action, so neither may be what the 38-char
        # ellipsis eats. asset_type is the optional one: rendered when the whole line fits,
        # dropped whole when it doesn't (and skipped entirely when the register omits it,
        # never a literal None).
        sub = f'{n["id"]} · {crit_label}'
        if n.get("asset_type"):
            typed = f'{n["id"]} · {n["asset_type"]} · {crit_label}'
            if len(typed) <= 38:
                sub = typed
    elif kind == "process":
        sub = f"{n.get('dept') or ''} · activity"
    elif kind == "process_group":
        # The name already carries the count; the sub line says what pressing it does.
        sub = f"{n.get('dept_count') or 0} departments · select for the list"
    elif kind == "activity":
        # Classifier FIRST, id second: same rule the asset branch states above, that what
        # decides an action must not be what the 38-char ellipsis eats. Measured 2026-08-27 on
        # the minted rooms — `act:Slaughter process (stunning → dressing) · BIA activity` is 58
        # chars, so the trailing form lost the two words that say what the card is and left
        # `act:Slaughter process (stunning → dre…`. It read as a missing activity rather than a
        # clipped label. marschkamp kept the words only because its `act:Cutting / deboning ·
        # BIA activity` is 37 and fitted, which is why this survived until a longer name shipped.
        sub = f"BIA activity · {n['id']}"
    elif kind == "unmodeled":
        sub = "unmodeled dependency"
    name_y, sub_y = (22, 38) if h >= 64 else ((20, 36) if h >= 56 else (17, 32))
    badges = []
    if n.get("spof"):
        badges.append('<tspan class="b-spof">SPOF</tspan>')
    if n.get("owner_missing"):
        badges.append('<tspan class="b-owner">OWNER MISSING</tspan>')
    if n.get("pp4_issue"):
        badges.append('<tspan class="b-pp4">PP4</tspan>')
    if n.get("quality_flag_count"):
        badges.append(f'<tspan class="b-flags">⚑{n["quality_flag_count"]}</tspan>')
    badge_text = ""
    # Grouped view only: one more line, the card's own edges onto the strip ("runs on")
    # or the roles that work in the activity ("People"). The tooltip carries it untruncated.
    tip = str(label)
    for cls, line in (("runs-on", "runs on: " + " · ".join(n.get("runs_on") or [])),
                      ("people", "People: " + ", ".join(n.get("people") or []))):
        if n.get(cls.replace("-", "_")):
            badge_text += (f'<text class="{cls}" x="{x + 10}" y="{y + h - 10}">'
                           f'{_esc(_trunc(line, 38))}</text>')
            tip = f"{tip} — {line}"
    first = y + h - 10 - _LINE_H * (len(n.get("lines") or ()) - 1)
    for i, (cls, line) in enumerate(n.get("lines") or ()):
        badge_text += (f'<text class="{cls}" x="{x + 10}" y="{first + _LINE_H * i}">'
                       f'{_esc(_trunc(line, 34))}</text>')
    if n.get("lines"):
        tip = tip + " — " + " ".join(t for _c, t in n["lines"])
    if badges and h >= 64:
        badge_text += (f'<text x="{x + 10}" y="{y + 54}">' + '<tspan> </tspan>'.join(badges)
                       + "</text>")
    # The group card's stacked-cards affordance: two offset sheets behind the box say
    # "there are more inside" without a word. Own class, not `box`, so the focus ring's
    # stroke-width bump reaches only the front card.
    stack = ""
    if kind == "process_group":
        stack = (f'<rect class="stack s2" x="{x + 10}" y="{y + 10}" width="{w}" '
                 f'height="{h}" rx="8"/>'
                 f'<rect class="stack s1" x="{x + 5}" y="{y + 5}" width="{w}" '
                 f'height="{h}" rx="8"/>')
    return (f'<g class="{" ".join(classes)}" data-id="{_esc(n["id"])}" '
            f'tabindex="0" role="button">'
            f'<title>{_esc(tip)}</title>'
            f'{stack}<rect class="box" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>'
            f'<text class="name" x="{x + 10}" y="{y + name_y}">{_esc(_trunc(str(label)))}</text>'
            f'<text class="sub" x="{x + 10}" y="{y + sub_y}">{_esc(_trunc(sub, 38))}</text>'
            f"{badge_text}</g>")


def _frame_head(label: str) -> int:
    """A frame's label band: one line, or two when the authored mark takes its own line
    (with the platform and type it is wider than a column)."""
    return _FRAME_HEAD + (14 if label.endswith(AUTHORED_MARK) else 0)


def _frames_svg(graph: dict, geo: dict) -> str:
    """Grouped view: one labelled box round each run of cards sharing a frame in a column
    (and round the strip). Drawn under the cards; it carries no data-src/data-dst, so the
    lens never reads it as an edge."""
    runs: list[tuple[str, list[str]]] = []
    key = None
    for n in sorted((n for n in graph["nodes"] if n.get("frame") and n["id"] in geo),
                    key=lambda n: (bool(n.get("foundation")), geo[n["id"]][0], geo[n["id"]][1])):
        k = (geo[n["id"]][0] if not n.get("foundation") else "strip", n["frame"])
        if k != key:
            runs.append((n["frame"], []))
            key = k
        runs[-1][1].append(n["id"])
    out = []
    for label, ids in runs:
        boxes = [geo[i] for i in ids]
        x0 = min(b[0] for b in boxes) - _FRAME_PAD
        y0 = min(b[1] for b in boxes) - _frame_head(label) + 2
        x1 = max(b[0] + b[2] for b in boxes) + _FRAME_PAD
        y1 = max(b[1] + b[3] for b in boxes) + _FRAME_PAD
        lines = ([label.removesuffix(AUTHORED_MARK).rstrip(), AUTHORED_MARK]
                 if label.endswith(AUTHORED_MARK) else [label])
        text = "".join(f'<text x="{x0 + 8}" y="{y0 + 15 + 14 * i}">{_esc(t)}</text>'
                       for i, t in enumerate(lines))
        out.append(f'<g class="frame" data-members="{_esc(" ".join(ids))}">'
                   f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10"/>'
                   f'{text}</g>')
    return "".join(out)


def _header_svg(graph: dict, geo: dict) -> str:
    """One label per occupied column, left-aligned on that column's cards. Every node in a
    column shares an x, so the position comes straight from the geometry — no second copy
    of the column maths."""
    x_of: dict[int, int] = {}
    for n in graph["nodes"]:
        # A folded card's x is its fold-band slot, not its column — anchoring a header
        # there put "Processes (consumers)" on top of column 0's header. Headers anchor
        # on the cards that are actually in their column.
        if n["id"] in geo and not n.get("collapsed") and not n.get("foundation"):
            x_of.setdefault(n["col"], geo[n["id"]][0])
    heads = "".join(f'<text class="col-head" x="{x_of[col]}" y="{_MARGIN + _HEAD_BASE}">'
                    f"{_esc(label)}</text>"
                    for col, label in _column_labels(graph).items() if col in x_of)
    # No separate fold-band header: the band docks directly under the group card, and
    # that card — "33 consuming processes · select for the list" — IS its label.
    return heads


def _edge_svg(e: dict, geo: dict, folded: frozenset = frozenset()) -> str:
    ga, gb = geo.get(e["src"]), geo.get(e["dst"])
    if ga is None or gb is None:  # dangling register reference — nothing to draw
        return ""
    fold_cls = " to-folded" if (e["src"] in folded or e["dst"] in folded) else ""
    ax, ay, aw, ah = ga
    bx, by, bw, bh = gb
    ya, yb = ay + ah // 2, by + bh // 2
    if bx < ax:  # provider left of dependent
        d = f"M{ax},{ya} C{ax - 60},{ya} {bx + bw + 60},{yb} {bx + bw},{yb}"
    elif bx > ax:
        d = f"M{ax + aw},{ya} C{ax + aw + 60},{ya} {bx - 60},{yb} {bx},{yb}"
    else:  # same column (cycle members): arc out on the right
        d = f"M{ax + aw},{ya} C{ax + aw + 70},{ya} {bx + bw + 70},{yb} {bx + bw},{yb}"
    return (f'<path class="edge {e["kind"]}{fold_cls}" data-src="{_esc(e["src"])}" '
            f'data-dst="{_esc(e["dst"])}" d="{d}"/>')


def _data_age(reg_ev: dict | None, rec_ev: dict | None) -> str:
    """When the page's SOURCES were last written — never when the page was rendered.

    Both stamps are banked per write in evidence.json; before 2026-08-04 they were only
    visible inside the collapsed Provenance fold while the headline showed the render
    clock. A reader could not tell a fresh page from a stale one without opening the fold.
    """
    parts = []
    for label, ev in (("BIA record", rec_ev), ("register", reg_ev)):
        at = (ev or {}).get("written_at")
        if not at:
            continue
        try:
            when = datetime.datetime.fromisoformat(at).strftime("%d %b %Y")
        except ValueError:  # a banked stamp we cannot parse is shown raw, never dropped
            when = at
        parts.append(f"{label} {when}")
    return " · ".join(parts) if parts else "read live at generation"


def _ev_row(label: str, ev: dict | None, absent_line: str) -> str:
    if not ev:
        return (f'<div class="ev"><span class="src">{label}</span>'
                f'<span class="absent">{absent_line}</span></div>')
    bits = [f'<span class="src">{label}</span>']
    if ev.get("sha"):
        bits.append(f'<code>{_esc(ev["sha"])}</code>')
    if ev.get("written_at"):
        bits.append(f'<span class="when">{_esc(ev["written_at"])}</span>')
    if ev.get("human_line"):
        bits.append(f'<span class="line">{_esc(ev["human_line"])}</span>')
    elif not ev.get("written_at"):
        bits.append('<span class="absent">read live at generation — no banked write '
                    "evidence</span>")
    out = '<div class="ev">' + " ".join(bits)
    return out + "</div>"


def render_page(graph: dict, company: str, evidence: dict | None = None,
                generated_at: str | None = None) -> str:
    _annotate(graph)  # precompute island fields; the JS never derives edges itself
    geo = _geometry(graph)
    width = max((x + w for x, _y, w, _h in geo.values()), default=360) + _MARGIN
    height = max((y + h for _x, y, _w, h in geo.values()), default=160) + _MARGIN
    # Collapsed nodes render as `folded` cards in a band below the graph, hidden by CSS
    # until the active lens keeps them; their edges carry to-folded and hide with them.
    folded_ids = frozenset(n["id"] for n in graph["nodes"] if n.get("collapsed"))
    # Grouped view: an edge from a column card onto the strip is drawn as that card's
    # "runs on" line, not as an arrow; edges between two strip cards stay arrows.
    strip_ids = frozenset(n["id"] for n in graph["nodes"] if n.get("foundation"))
    edges_svg = "".join(_edge_svg(e, geo, folded_ids) for e in graph["edges"]
                        if not (e["kind"] == "depends_on" and e["dst"] in strip_ids
                                and e["src"] not in strip_ids))
    nodes_svg = "".join(_node_svg(n, geo) for n in graph["nodes"] if n["id"] in geo)
    heads_svg = _header_svg(graph, geo)
    frames_svg = _frames_svg(graph, geo)  # empty unless group_view ran
    # The island is exactly the model a later Cytoscape-class explorer would consume
    # (spec D2) — keep it a faithful {nodes, edges} dump, build nothing else for it.
    island = json.dumps({"nodes": graph["nodes"], "edges": graph["edges"]},
                        ensure_ascii=False).replace("</", "<\\/")
    # With a fold band the element's aspect is state-dependent: the page opens at the
    # folded height and grows (aufklappen) when the lens keeps folded cards — homeView()
    # reads the element box, so the view follows without any JS layout. Pages without
    # folded content get no style attribute and keep their attribute-intrinsic aspect.
    fold_style = ""
    if folded_ids:
        folded_h = max(y + h for nid, (_x, y, _w, h) in geo.items()
                       if nid not in folded_ids) + _MARGIN
        fold_style = (f' style="--ar-folded:{width}/{folded_h};'
                      f'--ar-unfolded:{width}/{height}"')
    reg_ev = (evidence or {}).get("register")
    rec_ev = (evidence or {}).get("record")
    # Direct render calls read the clock once; generate() passes the exact stamp it binds into
    # evidence.json so the page and its receipt name one generation.
    generated_at = generated_at or datetime.datetime.now(datetime.UTC).isoformat(
        timespec="seconds")
    sha_bit = f' · register sha <code>{_esc(reg_ev["sha"])}</code>' if reg_ev and reg_ev.get("sha") else ""
    # Data classification is read off the register, never hardcoded: this caption used to print
    # unconditionally, so a real company's page would have carried "synthetic demonstration
    # data" over live data — the one caption you must not show a room. Absent marker = no
    # claim; the Provenance fold below already carries the write evidence either way.
    renderer_bit = _renderer_stamp()
    data_note = " · synthetic demonstration data" if graph.get("synthetic") else ""
    # The header leads with the one line a reader acts on; the ISO stamp, the sha and the
    # evidence rows are provenance, and provenance folds away (KG front-end review 4).
    # That headline used to carry the RENDER clock ("Updated <today>"), which is the one
    # thing a reader must not confuse with data age: the page rebuilds on every write, so
    # a three-day-old register still read as today's date (2026-08-03 — an applied owner
    # change looked un-applied, and the only contradicting stamp was inside the fold).
    data_age = _data_age(reg_ev, rec_ev)
    headline = (f"Synthetic demonstration data · {data_age}"
                if graph.get("synthetic") else data_age)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(company)} — resource dependency graph</title>
<style>{_CSS}{_GROUPED_CSS if graph.get("grouped") else ""}</style>
</head>
<body>
<header>
<p class="home"><a href="/demo/kb/">BIA Workflow</a></p>
<h1>{_esc(company)} — resource dependency graph</h1>
<div class="meta">{headline}</div>
</header>
<details class="provenance">
<summary class="meta">Provenance</summary>
<div class="meta">Generated {generated_at}{sha_bit}{renderer_bit}{data_note}</div>
<div id="evidence">
{_ev_row("Register", reg_ev, "no banked write evidence")}
{_ev_row("BIA record", rec_ev, "no run overlay — register base view")}
</div>
<div class="legend">Left = no recorded upstream dependencies; horizontal distance =
dependency depth, and each column is headed on the canvas with what it means. The two
rightmost columns are both activities: <em>BIA activities</em> were assessed in the BIA record
(impact grid, MTPD, owner); <em>dependent activities</em> are the register's note on each asset
of whose work needs it — one line per asset, so one operation appears once per resource it
needs. A column says only how deep an asset sits — SPOF and
missing ownership are properties of the asset, not of a column, so they turn up at any depth.
Other badges: PP4 (handoff issue), ⚑n (quality flags).</div>
<div class="meta">Register-derived view · the Provenance fold holds the latest verified write per source
· location.hash deep-links a node (e.g. #KA-01)</div>
</details>
<div id="toolbar"><span class="tb-end">Esc clears
<button type="button" id="reset-view">Reset view</button></span></div>
<main>
<div id="canvas"><svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"{fold_style}>
{heads_svg}
{frames_svg}{edges_svg}
{nodes_svg}
</svg></div>
<aside id="facts"></aside>
</main>
{_ISLAND_TAG}{island}</script>
<script>{_JS}</script>
</body>
</html>
"""


def answer(company: str, asset: str, fetch) -> dict:
    """Deterministic dependency answer for the MCP tool — live reads, stores nothing.

    Resolution: exact asset_id → unique case-insensitive substring over id+name →
    else an error listing candidates. All derivation goes through build_graph /
    upstream_chain; this never derives edges itself."""
    reg = fetch(company, "03_Dependencies/dependency-register.json")
    if "error" in reg:
        return {"error": f"cannot read register for {company}: {reg['error']}"}
    try:
        register = json.loads(reg["content"])
    except ValueError:
        return {"error": f"register for {company} is not valid JSON"}
    record = None
    rec = fetch(company, "output/bia-record.json")
    if "error" not in rec:
        try:
            record = json.loads(rec["content"])
        except ValueError:
            record = None  # corrupt overlay never breaks the register answer
    assets = {k: v for k, v in register.items() if isinstance(v, dict)}
    q = (asset or "").strip()
    if q in assets:
        aid = q
    else:
        ql = q.casefold()
        hits = [k for k, v in assets.items()
                if ql in k.casefold() or ql in str(v.get("name") or "").casefold()]
        if len(hits) == 1:
            aid = hits[0]
        elif hits:
            return {"error": f"ambiguous asset '{asset}' — offer the candidates back",
                    "candidates": [{"id": k, "name": assets[k].get("name")} for k in hits]}
        else:
            return {"error": f"no asset matches '{asset}' in the {company} register",
                    "candidates": [{"id": k, "name": v.get("name")}
                                   for k, v in assets.items()]}
    g = build_graph(register, record)
    node = next(n for n in g["nodes"] if n["id"] == aid)
    chain = upstream_chain(g, aid)
    dependents = downstream_chain(g, aid)
    consumers = [{"dept": c.get("dept"), "activity": c.get("activity"),
                  "need": c.get("need"), "consumer_mtpd": c.get("consumer_mtpd")}
                 for c in assets[aid].get("consumers") or []]
    acts = [e["src"] for e in g["edges"]
            if e["kind"] == "activity_dep" and e["dst"] == aid]
    overlay = ({"activities": [a.split("act:", 1)[1] for a in dict.fromkeys(acts)]}
               if acts else None)
    n_spof = sum(1 for c in chain if c["spof"])
    counts = {"depends_on": len(chain), "dependents": len(dependents),
              "consumers": len(consumers)}
    human_line = (f"{node.get('name') or aid} depends on {len(chain)} upstream asset"
                  f"{'s' if len(chain) != 1 else ''}"
                  + (f" ({n_spof} SPOF)" if n_spof else "")
                  + f"; {len(dependents)} downstream asset"
                  f"{'s' if len(dependents) != 1 else ''} depend on it"
                  + f"; {len(consumers)} process{'es' if len(consumers) != 1 else ''}"
                  " consume it — see the graph link.")
    return {"asset": node, "depends_on_chain": chain, "dependents": dependents,
            "consumers": consumers, "counts": counts, "overlay": overlay,
            "deep_link": f"{BASE_URL}/{company}/#{aid}",
            "register_sha": hashlib.sha256(reg["content"].encode("utf-8")).hexdigest()[:8],
            "human_line": human_line}


def bank_and_regen(company: str, rel: str, data: bytes, result: dict, fetch) -> None:
    """Post-verified-write hook body: bank the write's own verification evidence,
    then regenerate the company page. Called from graph_files under a never-blocks
    boundary — raising here only produces a logged warning there."""
    import graph_files  # lazy: graph_files lazy-imports this module's hook target

    out_dir = PUBLIC / company
    out_dir.mkdir(parents=True, exist_ok=True)
    ev_file = out_dir / "evidence.json"
    evidence = json.loads(ev_file.read_text(encoding="utf-8")) if ev_file.exists() else {}
    key = "register" if rel == graph_files.REGISTER_PATH else "record"
    verification = result.get("verification") or {}
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    evidence[key] = {
        "sha": hashlib.sha256(data).hexdigest(),
        "written_at": now,
        "human_line": verification.get("human_line"),
    }
    if result.get("amendment"):
        # Correction audit (update_bia_activity): a durable list — per-key banking above
        # is replaced on every save, amendments only ever append.
        evidence.setdefault("amendments", []).append({**result["amendment"], "at": now})
    ev_file.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    generate(company, fetch)  # never force: a write that loses the record IS the incident


def _receipt_error(message: str) -> dict:
    return {"error": "graph receipt unavailable: " + message}


def _full_sha(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def _rendered_value(page: str, prefix: str, suffix: str) -> str:
    start = page.index(prefix) + len(prefix)
    return page[start:page.index(suffix, start)].strip()


def _valid_generation_time(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return False
    return (parsed.tzinfo is not None
            and parsed.utcoffset() == datetime.timedelta(0)
            and parsed.isoformat(timespec="seconds") == value)


def read_receipt(company: str) -> dict:
    """Read and verify the current graph page's full evidence binding."""
    company = str(company or "").strip().lower()
    if (not company or Path(company).name != company
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in company)):
        return _receipt_error("invalid company")
    out_dir = PUBLIC / company
    ev_file = out_dir / "evidence.json"
    index = out_dir / "index.html"
    try:
        evidence = json.loads(ev_file.read_text(encoding="utf-8"))
        page_bytes = index.read_bytes()
        page_text = page_bytes.decode("utf-8")
    except (OSError, ValueError, UnicodeError):
        return _receipt_error("evidence or page is absent or unreadable")
    if not isinstance(evidence, dict):
        return _receipt_error("evidence is not an object")
    register = evidence.get("register")
    record = evidence.get("record")
    page = evidence.get("page")
    if not all(isinstance(x, dict) for x in (register, record, page)):
        return _receipt_error("record, register or page evidence is absent")
    record_sha = record.get("sha")
    register_sha = register.get("sha")
    page_sha = page.get("sha")
    if not all(_full_sha(x) for x in (record_sha, register_sha, page_sha)):
        return _receipt_error("record, register and page hashes must be full SHA-256")
    actual_page_sha = hashlib.sha256(page_bytes).hexdigest()
    if page_sha != actual_page_sha:
        return _receipt_error("page hash does not match the current page")
    if page.get("record_sha") != record_sha or page.get("register_sha") != register_sha:
        return _receipt_error("page evidence does not match the current record/register evidence")
    generated_at = page.get("generated_at")
    url = page.get("url")
    activity_count = page.get("activity_count")
    if (not _valid_generation_time(generated_at) or url != f"{BASE_URL}/{company}/"
            or not isinstance(activity_count, int) or isinstance(activity_count, bool)):
        return _receipt_error("page generation fields are absent or invalid")
    try:
        rendered_register_sha = _rendered_value(
            page_text, '<span class="src">Register</span> <code>', "</code>")
        rendered_record_sha = _rendered_value(
            page_text, '<span class="src">BIA record</span> <code>', "</code>")
        rendered_at = _rendered_value(
            page_text, '<div class="meta">Generated ', " · register sha <code>")
        start = page_text.index(_ISLAND_TAG) + len(_ISLAND_TAG)
        nodes = json.loads(page_text[start:page_text.index("</script>", start)])["nodes"]
        if not isinstance(nodes, list) or not all(isinstance(node, dict) for node in nodes):
            raise TypeError("nodes are not an object list")
        actual_count = sum(1 for node in nodes if node.get("kind") == "activity")
    except (ValueError, KeyError, TypeError):
        return _receipt_error("page receipt evidence is unreadable")
    if rendered_record_sha != record_sha:
        return _receipt_error("record hash does not match the current page")
    if rendered_register_sha != register_sha:
        return _receipt_error("register hash does not match the current page")
    if rendered_at != generated_at or not _valid_generation_time(rendered_at):
        return _receipt_error("generation time does not match the current page")
    if activity_count != actual_count:
        return _receipt_error("page activity count does not match the current page")
    return {"record_sha": record_sha, "register_sha": register_sha,
            "page_sha": page_sha, "activity_count": activity_count,
            "generated_at": generated_at, "url": url}


def regenerate_record_graph(
    company: str,
    record_bytes: bytes,
    write_receipt: dict,
    fetch,
    *,
    record_snapshot: dict,
) -> dict:
    """Regenerate and read back one graph bound to the verified record write."""
    import graph_files

    expected_sha = hashlib.sha256(record_bytes).hexdigest()
    if (
        record_snapshot.get("status") != "present"
        or record_snapshot.get("sha256") != expected_sha
        or not record_snapshot.get("version")
    ):
        raise RuntimeError("saved record snapshot is not version-bound")

    def version_bound_fetch(target_company: str, path: str) -> dict:
        if path != graph_files.RECORD_SAVE_PATH:
            return fetch(target_company, path)
        current = graph_files.file_snapshot(target_company, path)
        if current != record_snapshot:
            raise RuntimeError("saved record version changed before graph generation")
        return {
            "path": f"{target_company}/{path}",
            "content": record_bytes.decode("utf-8"),
            "size": len(record_bytes),
        }

    bank_and_regen(
        company,
        graph_files.RECORD_SAVE_PATH,
        record_bytes,
        write_receipt,
        version_bound_fetch,
    )
    receipt = read_receipt(company)
    if "error" in receipt:
        raise RuntimeError(receipt["error"])
    if receipt.get("record_sha") != expected_sha:
        raise RuntimeError("graph receipt does not match the saved record")
    current = graph_files.file_snapshot(company, graph_files.RECORD_SAVE_PATH)
    if current != record_snapshot:
        raise RuntimeError("saved record version changed before graph receipt persistence")
    return {**receipt, "record_snapshot": dict(record_snapshot)}


def _published_activities(index: Path) -> int:
    """How many BIA activity nodes the page already on disk carries — read back out of the
    page's own data island. render_page escapes `</` inside the island, so the first
    `</script>` after the tag is always the real close. A missing, unreadable or
    unparseable page counts zero: it is not the good page this guard exists to protect,
    and failing closed on it would wedge every future regen of that room."""
    try:
        html = index.read_text(encoding="utf-8")
        start = html.index(_ISLAND_TAG) + len(_ISLAND_TAG)
        nodes = json.loads(html[start:html.index("</script>", start)])["nodes"]
    except (OSError, ValueError, KeyError):
        return 0
    return sum(1 for n in nodes if n.get("kind") == "activity")


def generate(company: str, fetch, force: bool = False) -> str:
    # Same relative path as graph_files.REGISTER_PATH — literal here so the pure core
    # never imports the Graph lane.
    reg = fetch(company, "03_Dependencies/dependency-register.json")
    if "error" in reg:
        raise RuntimeError(f"cannot read register for {company}: {reg['error']}")
    record = None
    rec = fetch(company, "output/bia-record.json")
    if "error" not in rec:
        record = json.loads(rec["content"])
    elif "not found" not in rec["error"]:
        # A genuine 404 means this room has not run a BIA yet — a register-only page is
        # the correct output. ANY other read error (throttle, expiry, size cap) must not
        # publish an activity-less page over a good one: the write that triggered this
        # regen already reported success, so a silently gutted page is the one failure
        # nobody would notice. Raising leaves the previous page in place; the caller's
        # never-blocks boundary logs it. Contract: read_file's 404 says "file not found".
        raise RuntimeError(f"cannot read bia-record for {company}: {rec['error']}")
    out_dir = PUBLIC / company
    out_dir.mkdir(parents=True, exist_ok=True)
    ev_file = out_dir / "evidence.json"
    evidence = json.loads(ev_file.read_text(encoding="utf-8")) if ev_file.exists() else None
    if not (evidence or {}).get("register"):
        # CLI-generated view (e.g. the write-refused demo company): carry the live
        # register sha so the Provenance fold stays honest without banked write evidence.
        evidence = dict(evidence or {})
        evidence["register"] = {
            "sha": hashlib.sha256(reg["content"].encode("utf-8")).hexdigest()}
    # Canonical since the 2026-07-29 A/B/C evaluation: consumers collapse into the
    # group card and fold out under the lens (decision record in git history).
    g = collapse_processes(layout(build_graph(json.loads(reg["content"]), record)))
    index = out_dir / "index.html"
    acts = sum(1 for n in g["nodes"] if n["kind"] == "activity")
    was = 0 if force else _published_activities(index)
    if acts < was:
        # The 404 branch above is right about a room that never ran a BIA and blind to one
        # whose record just went missing. On 2026-08-10 the room's `output` folder was
        # renamed for a pre-beta reset; the regen two minutes later read a perfectly
        # legitimate 404 and republished the public page with zero activities over two —
        # twice that evening, unnoticed for two days. The published page is the second
        # witness the 404 alone cannot be: losing activities against it is an accident
        # until a human says otherwise.
        raise RuntimeError(
            f"refusing to publish {company}: BIA activity count would drop from {was} "
            f"to {acts}. Check the record is really gone (renamed or archived folder?) "
            "before re-running with --force.")
    generated_at = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    page = render_page(g, company, evidence, generated_at=generated_at)
    page_bytes = page.encode("utf-8")
    index.write_bytes(page_bytes)
    evidence = dict(evidence or {})
    evidence["page"] = {
        "sha": hashlib.sha256(page_bytes).hexdigest(),
        "record_sha": (hashlib.sha256(rec["content"].encode("utf-8")).hexdigest()
                       if "error" not in rec else None),
        "register_sha": hashlib.sha256(reg["content"].encode("utf-8")).hexdigest(),
        "activity_count": acts,
        "generated_at": generated_at,
        "url": f"{BASE_URL}/{company}/",
    }
    ev_file.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return str(index)


def cli_targets(arg: str, companies) -> tuple[tuple, str | None]:
    """Which rooms a CLI run regenerates, plus a warning when `all` silently means one.

    `all` resolves through BIA_WORKFLOW_COMPANIES, which only systemd sets — so `all` from
    an interactive shell regenerated marschkamp alone and said nothing about the other
    served room (found 2026-08-04). No silent scope reduction: say what was skipped.
    """
    if arg and arg != "all":
        return (arg,), None
    if len(companies) > 1:
        return tuple(companies), None
    return tuple(companies), (
        "WARNING: 'all' resolved to " + ", ".join(companies) + " only — "
        "BIA_WORKFLOW_COMPANIES is unset or single-valued, so any other served room was "
        "NOT regenerated. Re-run as BIA_WORKFLOW_COMPANIES=room1,room2 dep_graph.py all")


if __name__ == "__main__":  # ponytail: thin CLI, logic lives above
    import sys

    import graph_files

    # --force publishes a page carrying fewer BIA activities than the live one — the
    # deliberate "retire this room's BIA" case. Without it generate() refuses; see there.
    force = "--force" in sys.argv[1:]
    rooms = [a for a in sys.argv[1:] if a != "--force"]
    targets, warning = cli_targets(rooms[0] if rooms else "all", graph_files.COMPANIES)
    if warning:
        print(warning, file=sys.stderr)
    for comp in targets:
        print(generate(comp, graph_files.read_file, force=force))
