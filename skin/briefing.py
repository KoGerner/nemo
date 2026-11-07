"""Ticket 405 (M14, T7): the briefing for a re-interview as two A4 pages, drawn by code for
whichever BIA is asked for, and printed to PDF by chrome-headless-shell.

His answer (2026-10-10T16:24:34Z): *"Two-page PDF as discussed (Recommended)"*; his amend
(21:16:27Z): *"2-pager must be drafted whetever bia is being asked for. we are now just creating he
template around it"*. The template is 8_nemo_design's (`briefing-template-rules.md`, its
prototype `briefing_template.py`), built here on the skin's own readers:

    facts(folder, activity)   what the sheet says: B7's chat briefing (`core.briefing_facts`, so
                              the chat and the PDF never differ), then the rows' marks and columns,
                              the computed checks, last year's risk actions and the supplier
                              register's authored facts
    sheet(folder, activity)   the two pages as HTML
    pdf(folder, activity)     the PDF, printed by the newest chrome-headless-shell (`chrome`)
    pages(data)               each page's size in points, read from the PDF

Page 1 is the reading, in the AI4BCM Guidance look (the website's wordmark, Space Grotesk and
IBM Plex from `skin/harbour`, navy, rust and one peach card): the process with its RTO, MTPD and
RPO, why now, the checks to settle before the interview, last year's results as a heatmap
(ADR-0050: an hour no lens rated is no column), who came last time and who to add (functions
only, ADR-0051), the gaps (N no workaround, O owner missing, S single source, R comes back after
the process must) and the dependencies the gaps do not already list, each with a box to tick, in
four columns of the graph's ISO words (`merge_table.COLUMNS`), what it runs without one line under
them (r4). Page 2 is the interview sheet, its blocks A-E inside the invitation's length
(`core.INTERVIEW_LENGTH`): the RTO is asked after the people and dependencies it comes from.
No notes boxes: he does not need them (2026-11-04). Each page scales its type down (to
`MIN_ZOOM`) until it fits its A4; a page that still does not fit prints a third page, which the
suite fails on, so the print never drops text.

Every figure, name and date is the record's, the register's, the plan's or the seed's; the only
fixed text is the template's own words. No model call, and no PDF library: the print is a
subprocess, and nothing here enters `src/nemo`.
"""
from __future__ import annotations

import html
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import live_graph
import merge_table
import workspace
from merge_table import BUILDINGS, ICT, PEOPLE, PROVIDERS, RELEASE

import PROTOTYPE_core as core

#: the Playwright cache's chrome-headless-shell builds, under the home folder; the newest prints
SHELLS = ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/" \
    "chrome-headless-shell"
SUPPLIERS = "03_Dependencies/supplier-register.md"
RISKS = "06_Risk-and-Incidents/risk-register.md"
#: his Wednesday note: four columns; the fourth keeps the graph's three kinds as its sub-headings
FOUR = ((PEOPLE,), (PROVIDERS,), (ICT,), (RELEASE, merge_table.EQUIPMENT, BUILDINGS))
PER_COLUMN = 3
#: last year's risk actions named in the check card, each with its title and status
RISKS_SHOWN = 3
#: who to add, each with why (his Wednesday note: at most three); the rest by function only
SUGGESTED = 3
#: the header of a process no prior record names (`core.last_year`'s "first assessment")
FIRST = "BIA briefing · no prior record names it: a first BIA"
NO_RECORD = "No prior record: nothing from last year to compare."
NO_ROWS = "The dependency register names nothing it uses yet."
NO_INTERVIEW = "None on file."
#: r2 (15_marschkamp's amber 2): a first BIA has no last interview to repeat or count from
NO_EARLIER = "None: there is no earlier interview."
NO_ONE = "Nobody the files name yet."
RECENT = "recent incidents"
#: r4 (briefing-template-rules.md rule 7): what it runs without is named, never a column's row;
#: the graph's tray words (`live_graph.html`)
RUNS_WITHOUT = "Runs without (the record says so)"
#: the marks, each with its words (the reviewer round 9: letters carry them on a copier)
MARKS = {"N": "no workaround", "O": "owner missing", "S": "single source",
         "R": "comes back after the process must"}
#: the check lines' heads (the tests find each line by its head)
LATE_HEAD = "Comes back after the process must"
TIGHT_HEAD = "No margin"
#: what a re-interview asks that no record holds, each with the word that marks it known when the
#: supplier register's section for the process states it (ADR-0034 Part B point 7)
ASKED = (("incident", "incidents since {since}"), ("stock", "stock or backlog it can live on"),
         ("share", "share of volume per outside provider"), ("peak", "peak weeks"))
PEAK_KNOWN = "Which weeks hurt most this year?"
PEAK_OPEN = "Which weeks of the year hurt most if it stops?"
#: E: the outside providers' shares, asked, or checked where page 1 states them (r2's amber 3)
SHARE_OPEN = "What share of the volume comes from each outside provider?"
SHARE_KNOWN = "Does the split of the volume on page 1 still hold?"
HIGH = core.GRID_LEVELS.index("high")
FACTS_HEAD = re.compile(r"^- \*\*(.+?)\.\*\* (.+?)(?=^- |\Z)", re.M | re.S)


def chrome() -> Path | None:
    """The newest chrome-headless-shell in the Playwright cache, by its build number; None where
    none is installed (the chat then offers no download)."""
    found = [(int(m[1]), p) for p in Path.home().glob(SHELLS)
             if (m := re.search(r"chromium_headless_shell-(\d+)/", str(p)))]
    return max(found)[1] if found else None


def _hours(said: str) -> int | None:
    """A figure's hours; one beyond the grid (">168 h") counts as more than its hours."""
    found = re.search(r"(>?)\s*(\d+)\s*h\b", said or "")
    return int(found[2]) + bool(found[1]) if found else None


def _plain(rto: str) -> int | None:
    """The process's RTO as the checks compare it: none where it lies beyond the grid."""
    return None if ">" in rto else _hours(rto)


def _kind(asset: dict[str, Any]) -> str:
    """A register entry's column as the graph gives it (`merge_table.KINDS`): roles are People,
    sites Buildings and utilities, any other type not named there ICT."""
    kind = str(asset.get("asset_type"))
    return {merge_table.ROLE: PEOPLE, merge_table.SITE: BUILDINGS}.get(
        kind, merge_table.KINDS.get(kind, ICT))


def _record(folder: Path, prior: dict[str, Any]) -> tuple[str, str]:
    """The record's first sentence of what the process does, and its upstream/downstream line."""
    if not prior.get("found") or "source" not in prior:
        return "", ""
    text = (folder / prior["source"]).read_text(encoding="utf-8")
    section = text.partition(f"### {prior['ref']} — ")[2].split("\n### ")[0]
    first = next((p.strip() for p in section.split("\n\n")[1:]
                  if p.strip() and not p.lstrip().startswith(("|", "#"))), "")
    updown = re.search(r"^\| Upstream / downstream \| (.*?) \|$", section, re.M)
    return re.split(r"(?<=\.)\s", first)[0], updown[1] if updown else ""


def _risks(folder: Path, names: set[str]) -> list[tuple[str, str, str]]:
    """Last year's risk actions for the process: (id, risk, status), read by the table's head."""
    path = folder / RISKS
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    head = next((core._cells(x) for x in lines if x.startswith("| ID |")), [])
    out = []
    for line in lines:
        cells = core._cells(line)
        if line.startswith("| R-") and len(cells) == len(head):
            row = dict(zip(head, cells, strict=True))
            if names & {a.strip() for a in row.get("Activities", "").split(";")}:
                out.append((row["ID"], row["Risk"], row["Status"]))
    return out


def authored(folder: Path, name: str) -> list[tuple[str, str]]:
    """The supplier register's facts a re-interview asks for, from its section for the process
    (`## <process>: …`): each bullet's label and its fact, the demo mark left out."""
    path = folder / SUPPLIERS
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    part = text.partition(f"\n## {name}: ")[2].split("\n## ")[0]
    return [(label, " ".join(fact.split()).removeprefix(merge_table.MARK).lstrip(": "))
            for label, fact in FACTS_HEAD.findall(part)]


def _rows(folder: Path, activity: str, chat: dict[str, Any], rto: int | None
          ) -> tuple[list[dict[str, Any]], list[tuple[str, list[str]]]]:
    """B7's rows (`chat["uses"]`, 390's), each with its graph column and its marks; and the
    graph's lines (`merge_table.LINES_RULE`), named under the columns."""
    register = core.drafting.read_register(folder)
    keys = {a.get("name"): k for k, a in register.items() if isinstance(a, dict)}
    page = live_graph.g2(folder, register, activity)
    col_of = {m: b["col"] for b in page["boxes"].values() for m in b["members"]}
    gaps = {n: g for b in page["boxes"].values() for g, ns in b["gapNames"].items() for n in ns}
    stated = core.no_workaround(folder, activity)  # 604: `spof`'s
    rows = []
    for name, owner, use in chat["uses"]:
        asset = register[keys[name]]
        back = str(use.get("rto") or asset.get("rto") or "")
        said = str(use.get("workaround") or "")
        without = name in chat["without"]  # r2: 390's "It can run without them", never R
        marks = [m for m, on in (
            ("N", name in stated or gaps.get(name) == merge_table.NO_WORKAROUND),
            ("O", owner == core.NOT_STATED or gaps.get(name) == merge_table.OWNER),
            ("S", gaps.get(name) == merge_table.SINGLE
             or "single source" in f"{asset.get('description')} {said}".lower()),
            ("R", bool(not without and rto and _hours(back) and _hours(back) > rto)))  # type: ignore[operator]
            if on]
        rows.append({"name": name, "owner": owner, "col": col_of.get(keys[name]) or _kind(asset),
                     "rto": back, "marks": marks, "direct": bool(use), "said": said,
                     "without": without})
    lines = [(rule, names) for rule, names in page["notDrawn"] if rule == merge_table.LINES_RULE]
    return rows, lines


def _checks(f: dict[str, Any]) -> list[str]:
    """Page 1's "Check before you go", each line computed from the record and the rows."""
    rto, mtpd, out = f["rto"], f["mtpd"], []
    grid = f["grid"]
    first = next((h for h in f["horizons"] for row in grid.values()
                  if (v := row["cells"].get(h)) == "very high"
                  or v in core.GRID_LEVELS[HIGH:]), None)
    if first and mtpd and mtpd.strip() != first:
        out.append(f"Last year's grid first reaches high at {first}, but the record's MTPD is "
                   f"{mtpd}.")
    if _hours(rto) and _hours(mtpd) and _hours(rto) > _hours(mtpd):  # type: ignore[operator]
        out.append(f"The RTO {rto} is longer than the MTPD {mtpd}.")
    late = [r for r in f["rows"] if "R" in r["marks"]]
    if late:
        out.append(f"{LATE_HEAD} (its RTO {rto}): "
                   + ", ".join(f"{r['name']} ({r['rto']})" for r in late) + ".")
    tight = [r["name"] for r in f["rows"]
             if not r["without"] and _plain(rto) and _hours(r["rto"]) == _plain(rto)]
    if tight:
        out.append(f"{TIGHT_HEAD}: {core._listed(tight)} must be back within {rto}, the "
                   f"process's own RTO.")
    return out + _still_open(f)


def _still_open(f: dict[str, Any]) -> list[str]:
    """The checks' last line: last year's risk actions, each with its title and status (a bare id
    means nothing in the room). What to bring or ask is no check line: the run sheet asks it."""
    shown, more = f["risks"][:RISKS_SHOWN], len(f["risks"]) - RISKS_SHOWN
    return ["Last year's risk actions: " + "; ".join(
        f"{i} {risk} ({status})" for i, risk, status in shown)
        + (f"; and {more} more" if more > 0 else "") + "."] if f["risks"] else []


def _suggested(f: dict[str, Any]) -> list[tuple[str, str]]:
    """Who to add (his Wednesday note): B7's additions from the register, then the owners of the
    marked rows, then of the rows needed back as fast as the process (r2: never one it can run
    without); never a function already in the room. Each with why: what it holds or owns."""
    there = [function for function, held in f["chat"]["attendees"] if held is None]
    out = [(function, "holds " + _short(held)) for function, held in f["chat"]["attendees"]
           if held]
    rto = _plain(f["rto"])
    extra = [(r["owner"], f"owns {r['name']}") for r in f["rows"] if r["marks"]]
    extra += [(r["owner"], f"owns {r['name']}, needed back within {r['rto']}") for r in f["rows"]
              if not r["without"] and rto and _hours(r["rto"])
              and _hours(r["rto"]) <= rto]  # type: ignore[operator]
    for function, why in extra:
        if function != core.NOT_STATED and all(function not in x for x in there) \
                and function not in [o for o, _ in out]:
            out.append((function, why))
    return out


def _short(names: list[str]) -> str:
    return core._listed(names) if len(names) <= 2 else f"{names[0]}, {names[1]} and more"


def facts(folder: Path, activity: str) -> dict[str, Any]:
    """What the two pages say, every item drawn from the room's files (see the module's head)."""
    chat = core.briefing_facts(folder, activity)
    prior = core.last_year(folder, activity)
    figures = prior.get("figures") or {}
    rto, mtpd = str(figures.get("RTO") or ""), str(figures.get("MTPD") or "")
    grid = prior.get("grid") or {}
    horizons = list(dict.fromkeys(h for row in grid.values() for h in row["cells"]))
    rows, lines = _rows(folder, activity, chat, _plain(rto))
    does, updown = _record(folder, prior)
    owner = next((function.split(" (")[0] for function, held in chat["attendees"]
                  if held is None and "process owner" in function), "")
    f = {"chat": chat, "name": chat["name"], "record": prior.get("record", ""), "rto": rto,
         "mtpd": mtpd, "rpo": str(figures.get("RPO") or ""), "grid": grid,
         "horizons": horizons, "rows": rows, "lines": lines,
         "does": does, "updown": updown, "owner": owner or core.NOT_STATED,
         "since": (str(prior.get("interview") or "").split(",")[0] or "the last interview")
         if prior.get("record") else "",
         "risks": _risks(folder, {chat["name"], str(prior.get("name") or "")}),
         "authored": authored(folder, chat["name"]),
         "minutes": int(core.INTERVIEW_LENGTH.total_seconds() // 60)}
    f["checks"] = _checks(f)
    f["suggested"] = _suggested(f)
    return f


def _question(r: dict[str, Any], rto: str) -> str:
    """Block D: one open question per marked row, worded by its first mark."""
    if "R" in r["marks"]:
        return f"{r['name']} is back after {r['rto']}; the process needs {rto}. What do you do " \
            "in between?"
    if "N" in r["marks"]:
        return f"{r['name']}: what do you do if it is not available?"
    if "S" in r["marks"]:
        return f"{r['name']}: who else could deliver?"
    return f"{r['name']}: who owns it?"


def blocks(f: dict[str, Any]) -> list[tuple[str, str, int, list[str]]]:
    """Page 2, the reviewer's blocks (rounds 10–12): letter, title, minutes, the questions. Impact is asked
    open before last year's grid is compared; the marked rows each get one question, then Monday
    6 am with the system it needs back first."""
    marked = [r for r in f["rows"] if r["marks"]]
    ict = sorted((r for r in f["rows"] if r["col"] == ICT and r["direct"] and _hours(r["rto"])
                  and not r["without"]),
                 key=lambda r: (_hours(r["rto"]), bool(r["said"])))
    d = [_question(r, f["rto"]) for r in marked][:5]
    if ict:
        d.append(f"Monday, 6 am, {ict[0]['name']} is gone: walk me through it.")
    flagged = any(c.startswith("Last year's grid") for c in f["checks"])
    providers = any(r["col"] == PROVIDERS for r in f["rows"])
    peak = any("peak" in label.lower() for label, _ in f["authored"])
    shared = any("share" in label.lower() for label, _ in f["authored"])
    stock = "What could you live on, and for how long (stock, backlog, manual work)?"
    return [
        ("A", f"Since {f['since']}" if f["since"] else RECENT.capitalize(), 4, [
            "What went wrong since then, and what did you do?" if f["since"]
            else "What went wrong lately, and what did you do?",
            *(["Which of last year's risk actions got done?"] if f["risks"] else []),
            *f["chat"]["points"], "What is missing from page 1?",
            "Who sits across from you, and who is their deputy?"]),
        ("B", "Impact: where did it change?", 12, [
            "For each class (health, financial, legal, image, operational): after how many hours "
            "does it start to hurt, and what happens then?",
            "Compare with last year's grid on page 1; mark every cell that differs.",
            PEAK_KNOWN if peak else PEAK_OPEN,
            *(["Settle the check on page 1: which is right, the grid or the MTPD?"] if flagged
              else [])]),
        ("C", "People and outside help", 6, [
            "Who do you call first, and who after?",
            "Which of the dependencies on page 1 do you use? Which would you miss first?",
            *(["Who else can deliver?", SHARE_KNOWN if shared else SHARE_OPEN] if providers
              else [])]),
        ("D", "Recovery figures", 4, [
            "RTO and MTPD: what would you set today, and why?", stock,
            "Minimum level: how many people, and which systems at half?"]),
        ("E", "Weak spots and close", min(12, 2 * len(d) + 2) + 3,  # r3: rule 6
         [*(d or ["Which dependency would you miss first?"]),
          "Who decides each open point, and by when?"])]


E = html.escape
#: the Harbour fonts the skin already ships (`skin/harbour/assets/fonts`, byte for byte the
#: website's), loaded from disk by the print so nothing is fetched from off the box
FONTS = Path(__file__).resolve().parent / "harbour" / "assets" / "fonts"
FONT_FACES = "".join(
    f'@font-face{{font-family:"{family}";src:url("{(FONTS / file).as_uri()}") format("woff2");'
    f"font-weight:{weight};font-style:normal}}"
    for family, file, weight in (("Space Grotesk", "space-grotesk-var.woff2", "300 700"),
                                 ("IBM Plex Sans", "ibm-plex-sans-var.woff2", "100 700"),
                                 ("IBM Plex Mono", "ibm-plex-mono-400.woff2", "400"),
                                 ("IBM Plex Mono", "ibm-plex-mono-500.woff2", "500")))
#: the AI4BCM Guidance look (Harbour tokens): navy ink, slate text, hairlines, rust accent, amber
#: marker on a key word, one peach card. Sizes in px: A4 is 794 x 1123 at 96 dpi.
CSS_BODY = """@page{size:A4;margin:0}*{box-sizing:border-box}
:root{--z:1;--ink:#0b1f3a;--slate:#4a5a70;--muted:#5c6b80;--hair:#d5dce5;--fog:#eef1f5;--rust:#8a3a14;
--amber:#f2a900;--wm:#9a6700;--mark:#fde7b0;--peach:#fff0e8;--peach-text:#5a3a2c}
body{margin:0;font:15px/1.5 "IBM Plex Sans",system-ui,sans-serif;color:var(--ink);background:#fff}
.pg{width:210mm;height:296mm;padding:40px 52px 28px;position:relative;display:flex;
flex-direction:column;gap:13px;break-after:page}.pg:last-child{break-after:auto}
.top{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:14px;
border-bottom:1px solid var(--hair)}.wm{font:700 24px "Space Grotesk",sans-serif;
letter-spacing:-.01em}.wm span{color:var(--wm)}
.lab{font:400 12px "IBM Plex Mono",monospace;letter-spacing:.08em;text-transform:uppercase;
color:var(--muted)}.eb{color:var(--rust)}
.head{display:flex;justify-content:space-between;align-items:flex-end;gap:20px}.head>div:first-child{min-width:0;flex:1}
h1{margin:0;font:700 40px/1.05 "Space Grotesk",sans-serif;letter-spacing:-.02em}
.tiles{display:flex;gap:8px;flex:none}
.tile{border:1px solid var(--hair);border-radius:8px;padding:8px 14px;
min-width:78px;white-space:nowrap}.tile b{display:block;font:700 26px "Space Grotesk",sans-serif}
.tile.nil{border-style:dashed}.tile.nil b{font:500 18px/35px "Space Grotesk",sans-serif;
color:var(--muted)}
.own{padding:10px 0;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);
font-size:14px}.own .lab{margin-right:6px}
.why{margin:0;color:var(--slate)}mark{background:linear-gradient(var(--mark),var(--mark)) 0 .63em/
100% .36em no-repeat;color:var(--ink);font-weight:500}
.chk{background:var(--peach);border-radius:10px;padding:12px 18px;color:var(--peach-text);
font-size:14px;line-height:1.4}
.chk .lab{color:var(--rust);display:block;margin-bottom:6px}.chk{counter-reset:n}
.chk p{margin:0 0 5px;
display:flex;gap:12px;counter-increment:n}.chk p:last-child{margin:0}.chk p::before{
content:counter(n);flex:none;font:400 15px "IBM Plex Mono",monospace;color:var(--rust)}
h2{margin:0 0 8px;font:400 12px "IBM Plex Mono",monospace;letter-spacing:.08em;
text-transform:uppercase;color:var(--muted)}
table.g{border-collapse:separate;border-spacing:3px;width:100%;margin:-3px}
table.g th{font:400 12px "IBM Plex Mono",monospace;color:var(--muted);padding:0 0 2px}
table.g th.l{font:500 13px "IBM Plex Sans",sans-serif;color:var(--ink);text-align:left;width:116px}
table.g th.rto{color:var(--rust);font-weight:500}
table.g td{font:400 12px/21px "IBM Plex Mono",monospace;text-align:center;border-radius:3px;
background:var(--fog);color:var(--muted)}table.g td.rto{box-shadow:inset 0 0 0 2px var(--rust)}
table.g td.first{font-weight:700}
.lv-low{background:var(--mark)!important;color:var(--ink)!important}
.lv-medium{background:var(--amber)!important;color:var(--ink)!important}
.lv-high{background:var(--rust)!important;color:#fff!important}
.lv-very{background:var(--ink)!important;color:#fff!important}
.fn{margin:4px 0 0;font:400 12px "IBM Plex Mono",monospace;color:var(--slate)}
.who{margin:0;font-size:13.5px;line-height:1.45;color:var(--slate)}
.who b{color:var(--ink);font-weight:600}.who b+*{}
.known p{margin:0 0 4px;font-size:13.5px}
table.r{border-collapse:collapse;width:100%}table.r td{border-top:1px solid var(--hair);
padding:3px 6px 3px 0;font-size:13.5px;vertical-align:middle}table.r td.k{color:var(--muted);
font:400 12px "IBM Plex Mono",monospace;text-align:right}table.r td.m{width:1%;white-space:nowrap}
.bd{display:inline-block;width:22px;height:22px;border:1.5px solid var(--rust);border-radius:4px;
color:var(--rust);font:500 12px/19px "IBM Plex Mono",monospace;text-align:center;margin-right:4px}
.four{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
h4{margin:0 0 5px;font:400 12px "IBM Plex Mono",monospace;letter-spacing:.06em;
text-transform:uppercase;color:var(--muted)}.sub{display:block;margin-top:5px;font:400 12px
"IBM Plex Mono",monospace;color:var(--muted);text-transform:uppercase}
.chip{display:flex;gap:7px;align-items:flex-start;border:1px solid var(--hair);border-radius:4px;
padding:2px 6px;margin:0 0 4px;font-size:12.5px;line-height:1.25}.chip.mk{border-color:var(--rust)}
.bx{flex:none;width:12px;height:12px;border:1.5px solid var(--ink);border-radius:2px;margin-top:1px}
.bd2{color:var(--rust);font:500 11px "IBM Plex Mono",monospace;margin-left:4px}
.ft{margin-top:auto;display:flex;justify-content:space-between;padding-top:12px;
border-top:1px solid var(--hair);font:400 12px "IBM Plex Mono",monospace;color:var(--muted)}
.sheet{display:flex;flex-direction:column}.blk{display:flex;gap:20px;padding:7px 0;
border-top:1px solid var(--hair)}.blk .l{width:84px;flex:none}.ab{display:flex;width:32px;
height:32px;border-radius:50%;background:var(--ink);color:#fff;font:700 16px "Space Grotesk",
sans-serif;align-items:center;justify-content:center;margin-bottom:6px}
.min{font:400 12px "IBM Plex Mono",monospace;color:var(--muted)}.blk .q{flex:1}
h3{margin:0 0 4px;font:500 17px "Space Grotesk",sans-serif;letter-spacing:-.01em}
.ck{display:flex;gap:12px;margin:0 0 3px;font-size:15px;line-height:1.4}.ck .bx{margin-top:4px}
.sp{margin:0;color:var(--slate)}"""
#: every length in px scales with `--z`, which the page's script lowers until a page fits its A4
#: (down to `MIN_ZOOM`); a page that still overflows prints a third page, so a test fails loudly
#: instead of the print dropping text
MIN_ZOOM = 0.78
CSS = FONT_FACES + re.sub(r"(?<![\w#.-])(\d*\.?\d+)px", r"calc(\1px*var(--z))", CSS_BODY)
FIT = """<script>(function(){function fit(){document.querySelectorAll('.pg').forEach(function(p){
var z=1;for(var i=0;i<5;i++){p.style.setProperty('--z',z);var o=p.scrollHeight/p.clientHeight;
if(o<=1.0||z<=MIN_ZOOM)break;z=Math.max(MIN_ZOOM,z/o*0.995)}})}
window.addEventListener('load',function(){(document.fonts&&document.fonts.ready?document.fonts.ready
:Promise.resolve()).then(fit)})})();</script>""".replace("MIN_ZOOM", str(MIN_ZOOM))
LEVEL_CLASS = {"low": "lv-low", "medium": "lv-medium", "high": "lv-high", "very high": "lv-very"}


def _badges(marks: list[str]) -> str:
    return "".join(f'<span class="bd2">{m}</span>' for m in marks)


def _grid(f: dict[str, Any]) -> str:
    """Last year's grid as the record states it; an hour no lens rated is no column (ADR-0050).
    A level is written in its cell (it reads in grey on paper); the RTO's hour is outlined and
    each row's first high is bold."""
    if not f["grid"]:
        return "<p>The record states no impact grid.</p>"
    blank = ("", core.GRID_BLANK, "-")
    unrated = [h for h in f["horizons"] if all(r["cells"].get(h, "") in blank
                                                for r in f["grid"].values())]
    shown = [h for h in f["horizons"] if h not in unrated]
    rto = _plain(f["rto"])

    def is_rto(h: str) -> bool:
        return bool(rto) and _hours(h) == rto

    def row(name: str, r: dict[str, Any]) -> str:
        first = next((h for h in shown if r["cells"].get(h) in
                      ("high", "very high")), None)
        cells = "".join(
            f'<td class="{LEVEL_CLASS.get(r["cells"].get(h, ""), "")}'
            f'{" rto" if is_rto(h) else ""}{" first" if h == first else ""}">'
            f'{E(r["cells"].get(h, "") if r["cells"].get(h, "") not in ("none",) + blank else "–")}'
            "</td>" for h in shown)
        return f"<tr><th class='l'>{E(name)}</th>{cells}</tr>"
    head = "".join(f"<th{' class=\"rto\"' if is_rto(h) else ''}>"
                   f"{E(h)}{' RTO' if is_rto(h) else ''}</th>" for h in shown)
    extra = sorted({v for r in f["grid"].values() for v in r["cells"].values()}
                   - {*core.GRID_LEVELS, "very high", *blank})
    return ("<table class='g'><tr><th></th>" + head + "</tr>"
            + "".join(row(n, r) for n, r in f["grid"].items()) + "</table><p class='fn'>"
            + " · ".join(["– = none", "high = intolerable",
                          *(["outlined column = RTO"] if rto else []), *[E(v) for v in extra]])
            + "".join(f" · {E(h)}: not rated in the source" for h in unrated) + "</p>")


def _column(kinds: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    """One of the four columns: marked rows first, at most `PER_COLUMN`, the rest named. Each
    entry carries a box to tick in the room."""
    mine = sorted((r for r in rows if r["col"] in kinds), key=lambda r: not r["marks"])
    shown, rest = mine[:PER_COLUMN], mine[PER_COLUMN:]
    out = f"<h4>{E(kinds[0])}</h4>" if len(kinds) == 1 else ""
    for kind in kinds:
        these = [r for r in shown if r["col"] == kind]
        if len(kinds) > 1 and these:
            out += f'<span class="sub">{E(kind)}</span>'
        out += "".join(f"<div class='chip{' mk' if r['marks'] else ''}'><span class='bx'></span>"
                       f"<span>{E(r['name'])}{_badges(r['marks'])}</span></div>" for r in these)
    if not mine:
        out += "<p class='fn'>none in the register</p>"
    if rest:
        out += f"<p class='fn'>also: {E(core._listed([r['name'] for r in rest]))}</p>"
    return f"<div>{out}</div>"


def _why(r: dict[str, Any], rto: str) -> str:
    """Three words why (the reviewer round 9), by the row's first mark."""
    return {"R": f"back in {r['rto']}, the process needs {rto}",
            "N": "the register says: no workaround" if workspace.NO_WORKAROUND.search(r["said"])
            else "no workaround stated",  # r2: B5's words for an EMPTY cell
            "O": "no owner named", "S": "the only source"}[r["marks"][0]]


def _tile(label: str, said: str) -> str:
    return (f'<div class="tile"><span class="lab">{label}</span><b>{E(said)}</b></div>' if said
            else f'<div class="tile nil"><span class="lab">{label}</span><b>not stated</b></div>')


def sheet(folder: Path, activity: str) -> str:
    """The two pages as one HTML document, A4 each, in the AI4BCM Guidance look."""
    f = facts(folder, activity)
    chat, rows = f["chat"], f["rows"]
    marked = [r for r in rows if r["marks"]]
    there = [function for function, held in chat["attendees"] if held is None]
    added = "; ".join([f"{E(o)} ({E(why)})" for o, why in f["suggested"][:SUGGESTED]]
                      + ([f"also {E(core._listed([o for o, _ in f['suggested'][SUGGESTED:]]))}"]
                         if f["suggested"][SUGGESTED:] else []))
    used = sorted({m for r in marked for m in r["marks"]}, key=list(MARKS).index)
    gaps = ("<table class='r'>" + "".join(
        f"<tr><td class='m'>{_badges_big(r['marks'])}</td><td><b>{E(r['name'])}</b></td>"
        f"<td>{E(_why(r, f['rto']))}</td><td class='k'>{E(r['owner'])}</td></tr>" for r in marked)
        + "</table><p class='fn'>" + " · ".join(f"{m} {MARKS[m]}" for m in used)
        + "</p>") if marked else "<p class='sp'>The register marks no gap for this process.</p>"
    lines = "".join(f"<p class='fn'>{E(rule)}: {E(core._listed(names))}.</p>"
                    for rule, names in f["lines"])
    known = "".join(f"<p><b>{E(label)}:</b> {E(fact)}</p>" for label, fact in f["authored"])
    plan = blocks(f)
    planned = sum(m for _, _, m, _ in plan)
    checklist = "".join(
        f"<div class='blk'><div class='l'><span class='ab'>{a}</span>"
        f"<span class='min'>{m} min</span></div><div class='q'><h3>{E(t)}</h3>"
        + "".join(f"<div class='ck'><span class='bx'></span><span>{E(q)}</span></div>"
                  for q in qs) + "</div></div>" for a, t, m, qs in plan)
    came = " · ".join(E(x) for x in there) or (NO_INTERVIEW if f["record"] else NO_EARLIER)
    add = ("The same" + (", plus " + added if added else "") + ".") if there \
        else f"{added}." if added else NO_INTERVIEW if f["record"] else NO_ONE
    if f["record"]:
        tiles = _tile("RTO", f["rto"]) + _tile("MTPD", f["mtpd"]) + _tile("RPO", f["rpo"])
        results = f"<h2>Last year's impact, by hour of standstill</h2>{_grid(f)}"
    else:
        tiles, results = "", f"<p class='sp'>{NO_RECORD}</p>"
    drawn = [r for r in rows if not r["without"] and not r["marks"]]  # the gaps list has the rest
    four = f'<div class="four">{"".join(_column(k, drawn) for k in FOUR)}</div>' if rows \
        else f"<p class='sp'>{NO_ROWS}</p>"
    four += (f"<p class='fn'>{RUNS_WITHOUT}: {E(', '.join(chat['without']))}.</p>"
             if chat["without"] else "")
    eyebrow = (f"Record {E(f['record'])} · {f['minutes']} minutes" if f["record"]
               else f"{E(FIRST)} · {f['minutes']} minutes") + f" · owner: {E(f['owner'])}"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Briefing · {E(f['name'])}</title><style>{CSS}</style></head><body>
<div class="pg"><div class="top"><div class="wm">AI4<span>BCM</span></div>
<div class="lab">BIA re-interview briefing</div></div>
<div class="head"><div><div class="lab eb">{eyebrow}</div><h1>{E(f['name'])}</h1></div>
<div class="tiles">{tiles}</div></div>
{''.join(f'<p class="why">{_lead(w)}</p>' for w in chat['why'])}
<div class="chk"><span class="lab">Settle before you go</span>{''.join(
    f'<p>{E(c)}</p>' for c in f['checks']
) or '<p>Nothing to settle: the record and the register agree.</p>'}</div>
<div>{results}</div>
<p class="who"><b>Last interview:</b> {came} <b>Suggested this time:</b> {add}</p>
{f'<div class="known"><h2>From the supplier register · {E(merge_table.MARK)}</h2>{known}</div>'
 if known else ''}
<div><h2>{'Gaps and single points of failure' if 'S' in used else 'Gaps'}</h2>{gaps}</div>
<div><h2>Dependencies: tick the ones it uses</h2>{four}{lines}</div>
<div class="ft"><span>nemo · from the record and the register</span><span>1 / 2</span></div></div>
<div class="pg"><div class="top"><div class="wm">AI4<span>BCM</span></div>
<div class="lab">BIA re-interview briefing</div></div>
<div><div class="lab eb">{E(f['name'])} · {f['minutes']} minutes</div><h1>Interview sheet</h1>
<p class="why">Ask open questions, write down the answer, compare afterwards.</p></div>
<div class="sheet">{checklist}</div>
<p class="fn">{f['minutes']} minutes in the invitation = {planned} planned +
{f['minutes'] - planned} spare (interviews overrun).</p>
<div class="ft"><span>nemo · from the record and the register</span><span>2 / 2</span></div>
</div>{FIT}</body></html>"""


def _lead(line: str) -> str:
    """The why-now line, the word "overdue" marked as the website marks a key word."""
    return E(line.removeprefix("- ")).replace("overdue", "<mark>overdue</mark>")


def _badges_big(marks: list[str]) -> str:
    return "".join(f'<span class="bd">{m}</span>' for m in marks)


def pdf(folder: Path, activity: str) -> bytes:
    """The two pages printed by the newest chrome-headless-shell, in a folder of its own that
    goes when it is done; nothing is written in the room. Raises where no shell is installed."""
    shell = chrome()
    if shell is None:
        raise FileNotFoundError(f"no chrome-headless-shell under ~/{SHELLS}")
    with tempfile.TemporaryDirectory(prefix="nemo-briefing-") as top:
        page, out = Path(top) / "briefing.html", Path(top) / "briefing.pdf"
        page.write_text(sheet(folder, activity), encoding="utf-8")
        subprocess.run([str(shell), "--headless", "--no-sandbox", "--disable-gpu",
                        f"--user-data-dir={top}/profile", "--no-pdf-header-footer",
                        "--virtual-time-budget=4000",
                        f"--print-to-pdf={out}", page.as_uri()],
                       check=True, capture_output=True, timeout=60)
        return out.read_bytes()


def pages(data: bytes) -> list[tuple[float, float]]:
    """Each page's width and height in points, from its page object's MediaBox."""
    out = []
    for obj in data.split(b"endobj"):
        if re.search(rb"/Type\s*/Page(?![a-zA-Z])", obj):
            box = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", obj)
            if box:
                out.append((float(box[3]) - float(box[1]), float(box[4]) - float(box[2])))
    return out
