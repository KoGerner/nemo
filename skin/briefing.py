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

Page 1 is the reading: the process, why now, who came last time and who to add (functions only,
ADR-0051), the checks, last year's results (ADR-0050: an hour no lens rated is no column), the
gaps (N no workaround, O owner missing, S single source, R comes back after the process must) and
the dependencies in four columns of the graph's ISO words (`merge_table.COLUMNS`), what it runs
without one line under them (r4). Page 2 is the interview checklist, its minutes inside the
invitation's length (`core.INTERVIEW_LENGTH`).

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
PER_COLUMN = 6
#: who to add, each with why (his Wednesday note: at most three); the rest by function only
SUGGESTED = 3
#: last year's risk actions named with their risk while there are at most this many
RISKS_NAMED = 2
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
ASK_HEAD = "Not in the record, bring or ask"
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
    """The checks' last two lines: last year's risk actions, and what to bring or ask."""
    out = ["Last year's risk actions: " + "; ".join(  # named in full while they fit
        f"{i} {risk} ({status})" if len(f["risks"]) <= RISKS_NAMED else f"{i} ({status})"
        for i, risk, status in f["risks"]) + "."] if f["risks"] else []
    known = [label.lower() for label, _ in f["authored"]]
    ask = [item.format(since=f["since"]) if f["since"] else RECENT if key == "incident" else item
           for key, item in ASKED
           if not any(key in label for label in known)]
    return out + ([f"{ASK_HEAD}: " + " · ".join(ask) + "."] if ask else [])


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
         "mtpd": mtpd, "grid": grid, "horizons": horizons, "rows": rows, "lines": lines,
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
    return [
        ("A", f"Since {f['since']}" if f["since"] else RECENT.capitalize(), 4, [
            "What went wrong since then, and what did you do?" if f["since"]
            else "What went wrong lately, and what did you do?",
            *(["Which of last year's risk actions got done?"] if f["risks"] else []),
            *f["chat"]["points"], "What is missing from page 1?"]),
        ("B", "Impact: where did it change?", 12, [
            "For each class (health, financial, legal, image, operational): from which hour does "
            "it start to hurt, and what happens then?",
            "Then compare with last year's grid on page 1; mark every cell that differs.",
            *(["Settle the check on page 1: which holds, the grid or the MTPD?"] if flagged
              else [])]),
        ("C", "Recovery figures", 4, ["RTO and MTPD: what would you set today, and why?"]),
        ("D", "The marked boxes, one open question each", min(12, 2 * len(d) + 2),  # r3: rule 6
         d or ["Which dependency would you miss first?"]),
        ("E", "People and outside help", 6, [
            "Who do you call first, and who after?",
            *(["Who else can deliver?", SHARE_KNOWN if shared else SHARE_OPEN] if providers
              else []),
            PEAK_KNOWN if peak else PEAK_OPEN,
            "What could you live on, and for how long (stock, backlog, manual)?"]),
        ("F", "Close", 3, ["Who decides each open point, and by when?"])]


E = html.escape
CSS = """@page{size:A4;margin:0}*{box-sizing:border-box}
body{margin:0;font:10px/1.36 "DejaVu Sans",system-ui,sans-serif;color:#0f1d2e;background:#fff}
.pg{width:210mm;min-height:296mm;padding:11mm 12mm 13mm;position:relative;display:flex;
flex-direction:column;break-after:page}.pg:last-child{break-after:auto}
h1{font-size:17px;margin:0}h2{font-size:10px;margin:7px 0 3px;text-transform:uppercase;
letter-spacing:.05em;color:#5b6676;border-bottom:1px solid #d8dde5;padding-bottom:2px}
h3{font-size:10.5px;margin:7px 0 2px}h4{margin:0 0 3px;font-size:9px;text-transform:uppercase;
letter-spacing:.04em;color:#5b6676}.sub{display:block;margin-top:3px;font-size:8px;color:#5b6676;
text-transform:uppercase;letter-spacing:.03em}.subt{color:#5b6676;margin:2px 0 0}
.two{display:flex;gap:12px}.two>div{flex:1}p{margin:2px 0}
table.g{border-collapse:collapse;width:100%;font-size:9px}table.g td,table.g th{border:1px solid
#c9d0da;padding:0 4px;text-align:center}table.g th.l{text-align:left;font-weight:600;
white-space:nowrap}table.r{border-collapse:collapse;width:100%}table.r td{border-top:1px solid
#d8dde5;padding:2px 5px;vertical-align:middle}table.r td.k{color:#5b6676;font-size:9px}
table.r td.m{white-space:nowrap;width:1%}.fn{font-size:8.5px;color:#5b6676;margin:2px 0}
.ft{position:absolute;bottom:6mm;left:12mm;right:12mm;font-size:8px;color:#5b6676;display:flex;
justify-content:space-between}.chk{border:1.5px solid #0f1d2e;border-radius:5px;padding:3px 8px;
margin:5px 0}.bd{display:inline-block;min-width:14px;text-align:center;font-weight:700;
border-radius:3px;padding:0 3px;margin-left:3px;font-size:9px;line-height:13px;color:#b8470f;
border:1.5px solid #b8470f;background:#fff}.four{display:grid;grid-template-columns:repeat(4,1fr);
gap:6px}.chip{border:1px solid #c9d0da;border-radius:4px;padding:1px 4px;margin:2px 0;
font-size:9px;line-height:1.25}.chip.mk{border:1.6px solid #b8470f}.ck{display:flex;gap:6px;
margin:2px 0;align-items:flex-start}.bx{flex:none;width:10px;height:10px;border:1.3px solid
#0f1d2e;border-radius:2px;margin-top:2px}.ab{display:inline-block;width:15px;height:15px;
border-radius:50%;background:#0f1d2e;color:#fff;text-align:center;font-size:9px;line-height:15px;
margin-right:3px}.min{float:right;font-weight:400;color:#5b6676}
.notes{border:1px solid #d8dde5;border-radius:4px;flex:1;min-height:10mm;margin:3px 0 0}"""
LEVEL_COLOUR = {"low": "#fbf3df", "medium": "#f6dcb8", "high": "#e9a37c", "very high": "#d9805a"}


def _badges(marks: list[str]) -> str:
    return "".join(f'<span class="bd">{m}</span>' for m in marks)


def _cell(level: str) -> str:
    return f'<td style="background:{LEVEL_COLOUR.get(level, "#fff")}">{E(level)}</td>'


def _grid(f: dict[str, Any]) -> str:
    """Last year's grid as the record states it; an hour no lens rated is no column (ADR-0050)."""
    if not f["grid"]:
        return "<p>The record states no impact grid.</p>"
    blank = ("", core.GRID_BLANK, "-")
    unrated = [h for h in f["horizons"] if all(r["cells"].get(h, "") in blank
                                                for r in f["grid"].values())]
    shown = [h for h in f["horizons"] if h not in unrated]
    return ("<table class='g'><tr><th></th>" + "".join(f"<th>{E(h)}</th>" for h in shown)
            + "</tr>" + "".join(
                f"<tr><th class='l'>{E(n)}</th>" + "".join(_cell(r["cells"].get(h, ""))
                                                          for h in shown) + "</tr>"
                for n, r in f["grid"].items()) + "</table><p class='fn'>"
            + " · ".join([*core.GRID_LEVELS, *sorted(
                {v for r in f["grid"].values() for v in r["cells"].values()}
                - {*core.GRID_LEVELS, *blank})]) + " (high = intolerable)"
            + "".join(f" · {E(h)}: not rated in the source" for h in unrated) + ".</p>")


def _column(kinds: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    """One of the four columns: marked rows first, at most `PER_COLUMN`, the rest named."""
    mine = sorted((r for r in rows if r["col"] in kinds), key=lambda r: not r["marks"])
    shown, rest = mine[:PER_COLUMN], mine[PER_COLUMN:]
    out = f"<h4>{E(kinds[0])}</h4>" if len(kinds) == 1 else ""
    for kind in kinds:
        these = [r for r in shown if r["col"] == kind]
        if len(kinds) > 1 and these:
            out += f'<span class="sub">{E(kind)}</span>'
        out += "".join(f"<div class='chip{' mk' if r['marks'] else ''}'>{E(r['name'])}"
                       f"{_badges(r['marks'])}</div>" for r in these)
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


def sheet(folder: Path, activity: str) -> str:
    """The two pages as one HTML document, A4 each."""
    f = facts(folder, activity)
    chat, rows = f["chat"], f["rows"]
    marked = [r for r in rows if r["marks"]]
    there = [function for function, held in chat["attendees"] if held is None]
    added = "; ".join([f"{E(o)} ({E(why)})" for o, why in f["suggested"][:SUGGESTED]]
                      + ([f"also {E(core._listed([o for o, _ in f['suggested'][SUGGESTED:]]))}"]
                         if f["suggested"][SUGGESTED:] else []))
    used = sorted({m for r in marked for m in r["marks"]}, key=list(MARKS).index)
    gaps = ("<table class='r'>" + "".join(
        f"<tr><td class='m'>{_badges(r['marks'])}</td><td><b>{E(r['name'])}</b></td>"
        f"<td>{E(_why(r, f['rto']))}</td><td class='k'>{E(r['owner'])}</td></tr>" for r in marked)
        + "</table><p class='fn'>" + " · ".join(f"{_badges([m])} {MARKS[m]}" for m in used)
        + "</p>") if marked else "<p>The register marks no gap for this process.</p>"
    lines = "".join(f"<p class='fn'>{E(rule)}: {E(core._listed(names))}.</p>"
                    for rule, names in f["lines"])
    known = "".join(f"<p><b>{E(label)}:</b> {E(fact)}</p>" for label, fact in f["authored"])
    plan = blocks(f)
    planned = sum(m for _, _, m, _ in plan)
    checklist = "".join(
        f"<h3><span class='ab'>{a}</span> {E(t)} <span class='min'>{m} min</span></h3>"
        + "".join(f"<div class='ck'><span class='bx'></span><span>{E(q)}</span></div>" for q in qs)
        for a, t, m, qs in plan)
    came = " · ".join(E(x) for x in there) or (NO_INTERVIEW if f["record"] else NO_EARLIER)
    add = ("The same" + (", plus " + added if added else "") + ".") if there \
        else f"{added}." if added else NO_INTERVIEW if f["record"] else NO_ONE
    results = f"<p><b>RTO {E(f['rto'])} · MTPD {E(f['mtpd'])}</b></p>{_grid(f)}" \
        if f["record"] else f"<p>{NO_RECORD}</p>"
    drawn = [r for r in rows if not r["without"]]
    four = f'<div class="four">{"".join(_column(k, drawn) for k in FOUR)}</div>' if rows \
        else f"<p>{NO_ROWS}</p>"
    four += (f"<p class='fn'>{RUNS_WITHOUT}: {E(', '.join(chat['without']))}.</p>"
             if chat["without"] else "")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Briefing · {E(f['name'])}</title><style>{CSS}</style></head><body>
<div class="pg"><h1>{E(f['name'])}</h1>
<p class="subt">{f"BIA re-interview briefing · record {E(f['record'])}" if f['record'] else FIRST}
{f" · owner: {E(f['owner'])}" if f['owner'] != core.NOT_STATED else ''} · {f['minutes']} minutes</p>
{''.join(f'<p>{E(w.removeprefix("- "))}</p>' for w in chat['why'])}
{f"<p><b>What it does:</b> {E(f['does'])} {E(f['updown'])}</p>" if f['does'] else ''}
<div class="two"><div><h2>Last interview</h2><p>{came}</p></div>
<div><h2>Suggested this time</h2><p>{add}</p></div></div>
<div class="chk"><b>Check before you go</b>{''.join(f'<p>{E(c)}</p>' for c in f['checks'])}</div>
{f'<h2>From the supplier register · {E(merge_table.MARK)}</h2>{known}' if known else ''}
<h2>Last year's results</h2>{results}
<h2>{'Gaps and single points of failure' if 'S' in used else 'Gaps'}</h2>{gaps}
<h2>Dependencies</h2>{four}{lines}
<h2>Notes</h2><div class="notes"></div>
<div class="ft"><span>nemo · from the record and the register · no model wrote any of it</span>
<span>page 1 of 2</span></div></div>
<div class="pg"><h1>Interview checklist · {E(f['name'])}</h1>
<p class="subt">Ask open, write the answer, compare after. Marked boxes from page 1 come in D.</p>
{checklist}<p class="fn">{f['minutes']} minutes in the invitation = {planned} planned +
{f['minutes'] - planned} spare (interviews overrun).</p>
<h2>Notes</h2><div class="notes"></div>
<div class="ft"><span>nemo · from the record and the register</span><span>page 2 of 2</span>
</div></div></body></html>"""


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
