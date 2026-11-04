"""Ticket 255: the impact over time, as a picture drawn from the record.

The owner, round 2 Q3 (2026-10-01T20:40:22Z): *"(a) nemo's code draws them from the record, the
same picture every time, with no model involved"*. So the picture is a function of the grid and
the method alone, an SVG string built with the standard library: x the method's horizons as equal
steps, y the scores 1-5, one step line per lens, the intolerability threshold dashed. A cell with
no score is a gap in its line, never guessed; a grid with no score at all draws nothing (`""`).

The grid card beside it is the table view, so the colours never carry a figure alone. t287: they are
the pinned Harbour palette's (`skin/harbour/tokens/colors.css`), read by name: the chart is served
as an SVG file, which links no stylesheet, so it states the values themselves.

t314: the same chart, asked for in the chat. Last year's record states its grid in words
(`from_record` reads it by the method's own names and labels), and with this walk's grid as well it
is drawn on the same chart, dashed and faint under this year's solid lines (`prior`). The subtitle
wraps at the chart's width rather than being cut, and the five lenses take five Harbour colours a
projector tells apart.
"""
from __future__ import annotations

import itertools
import re
import textwrap
from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any, NamedTuple

from nemo.impact import is_score, worst_case_row
from nemo.method import SEVERITY_SCALE, horizons, lenses, threshold

#: Every `--color-<name>: #hex` the pinned Harbour palette states, by name; t403 r4: and nemo's
#: own beside it (`nemo-colors.css`, which a Harbour re-sync never rewrites).
HARBOUR: dict[str, str] = dict(re.findall(r"--color-([\w-]+):\s*(#[0-9a-fA-F]{6})\b", "".join(
    (Path(__file__).resolve().parent / "harbour/tokens" / f).read_text(encoding="utf-8")
    for f in ("colors.css", "nemo-colors.css"))))
#: One colour per lens, by its place in the method: a lens keeps its colour whoever else is drawn.
#: t314 fix 2: the first five (the method's five lenses) are all about 20 apart (CIEDE2000, at
#: worst 19.97), where rust and peach-text, two browns, were 13.4.
COLOURS = tuple(HARBOUR[name] for name in ("navy", "amber", "muted", "amber-wordmark", "rust",
                                            "peach-text"))
INK, MUTED, GRID_LINE, PAPER = (HARBOUR[name] for name in ("navy", "slate", "hairline", "white"))
WIDTH, LEFT, RIGHT, TOP, ROW = 360, 34, 344, 50, 30
#: t314 fix 1: the subtitle's characters a line, so that 0.6 em each still fits in `WIDTH`
WRAP, LINE = 49, 14
#: t314: last year's lines, under this year's
LAST_DASH, LAST_OPACITY = "5 4", "0.55"
FAINT = f' stroke-dasharray="{LAST_DASH}" stroke-opacity="{LAST_OPACITY}"'
LAST_YEAR, THIS_YEAR = "last year", "this year"
#: t403: the faint ink of chart A's last-year lines; r7: and of their names where no this-year
#: line is drawn
LAST_INK = "0.45"
#: t403 r7: between a number and its unit in the conclusion, so "168 h" never wraps apart
NBSP = "\u00a0"
#: t430 (9_nemo_design, 2026-10-12): a last-year line's name at least this contrast on white
#: (WCAG's floor for bold text), its line faint as it is
NAME_CONTRAST = 3.0


def _y(score: float, top: float = TOP) -> float:
    return top + 4 * ROW - (score - 1) * ROW


def _f(v: float) -> str:
    return f"{v:.1f}"


def svg(grid: Mapping[str, Any] | None, method: Mapping[str, Any], title: str = "",
        prior: Mapping[str, Any] | None = None) -> str:
    """The grid as a step chart, or `""` where no cell holds a score. t314: `prior`, last year's
    grid, is drawn under it per lens, dashed and faint, and the legend says which is which."""
    hors, order = horizons(method), lenses(method)
    names = {s["id"]: s.get("name") or s["id"] for s in method.get("scenarios") or []
             if isinstance(s, dict) and s.get("id")}
    rows, last = _scored(grid, hors), _scored(prior, hors)
    drawn = [lens for lens in order if lens in rows or lens in last]
    if not drawn:
        return ""
    step = (RIGHT - LEFT) / len(hors)
    xs = [LEFT + i * step for i in range(len(hors))]
    # the heading on its own line, what it is about under it, so a long name is never cut short;
    # t314 fix 1: and a long subtitle wraps, the chart moving down under it
    lines = textwrap.wrap(title, WRAP) or [title]
    top = TOP + (len(lines) - 1) * LINE
    out = [f'<text x="{LEFT}" y="16" font-size="13" font-weight="600" fill="{INK}">'
           f"Impact over time</text>",
           *(f'<text x="{LEFT}" y="{32 + n * LINE}" class="subtitle" font-size="11" '
             f'fill="{MUTED}">{escape(line)}</text>' for n, line in enumerate(lines)),
           *_axes(hors, xs, threshold(method), top)]
    for cls, held, extra in (("lens-last", last, FAINT), ("lens", rows, "")):
        for k, lens in enumerate(drawn):
            if lens not in held:
                continue
            # lines a few pixels apart, in drawing order, so one never hides another
            d = _steps([held[lens].get(h) for h in hors], xs, step,
                       (k - (len(drawn) - 1) / 2) * 2, top)
            out.append(f'<path class="{cls}" data-lens="{escape(lens)}" d="{d}" '
                       f'stroke="{_colour(order, lens)}" stroke-width="2"{extra} fill="none" '
                       f'stroke-linejoin="round"><title>{escape(names.get(lens, lens))}</title>'
                       "</path>")
    keys = [(names.get(lens, lens), _colour(order, lens), "") for lens in drawn]
    keys += [(LAST_YEAR, INK, FAINT), (THIS_YEAR, INK, "")] if rows and last else []
    height = top + 4 * ROW + 40 + ((len(keys) + 1) // 2) * 18
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" font-family="system-ui, sans-serif" role="img">'
            f'<rect width="{WIDTH}" height="{height}" fill="{PAPER}"/>'
            + "".join(out + _legend(keys, top + 4 * ROW + 40)) + "</svg>")


def _legend(keys: list[tuple[str, str, str]], legend_top: float) -> list[str]:
    """Each line's sample and its name, two to a row, so colour never carries a figure alone."""
    out = []
    for k, (said, colour, extra) in enumerate(keys):
        x, y = LEFT + (k % 2) * 160, legend_top + (k // 2) * 18
        out.append(f'<line x1="{x}" x2="{x + 16}" y1="{y}" y2="{y}" '
                   f'stroke="{colour}" stroke-width="2"{extra}/>')
        out.append(f'<text class="legend" x="{x + 22}" y="{y}" dominant-baseline="middle" '
                   f'font-size="12" fill="{INK}">{escape(said)}</text>')
    return out


def _scored(grid: Mapping[str, Any] | None, hors: list[str]) -> dict[str, Mapping[str, Any]]:
    return {lens: row for lens, row in (grid or {}).items()
            if isinstance(row, Mapping) and any(is_score(row.get(h)) for h in hors)}


def from_record(record: Mapping[str, Any] | None,
                method: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    """t314: last year's grid as its record states it (`{category: {"remark", "cells"}}`, the
    skin's `last_year`), read by the method's own words: a category by its scenario's name, a cell
    by its severity label ("low" is 2). A blank cell, or a word the scale does not hold, is a gap,
    never guessed; so is a category the method does not name."""
    ids = {str(s.get("name") or "").strip().lower(): s["id"] for s in method.get("scenarios") or []
           if isinstance(s, dict) and s.get("id")}
    levels: dict[str, Any] = {str(s.get("label") or "").strip().lower(): s.get("level")
              for s in method.get(SEVERITY_SCALE) or [] if isinstance(s, dict)}
    out: dict[str, dict[str, int]] = {}
    for category, row in (record or {}).items():
        cells = {h: levels[str(v).strip().lower()]
                 for h, v in ((row or {}).get("cells") or {}).items()
                 if is_score(levels.get(str(v).strip().lower()))}
        if (lens := ids.get(str(category).strip().lower())) and cells:
            out[lens] = cells
    return out


def _colour(order: list[str], lens: str) -> str:
    return COLOURS[order.index(lens) % len(COLOURS)]


def _axes(hors: list[str], xs: list[float], intolerable: Any, top: float = TOP) -> list[str]:
    """The scores up the side, the horizons along the bottom, the threshold dashed across."""
    out = []
    for s in range(1, 6):
        y = _f(_y(s, top))
        out.append(f'<line x1="{LEFT}" x2="{RIGHT}" y1="{y}" y2="{y}" '
                   f'stroke="{GRID_LINE}" stroke-width="1"/>')
        out.append(f'<text class="score" y="{y}" x="{LEFT - 8}" text-anchor="end" '
                   f'dominant-baseline="middle" font-size="11" fill="{MUTED}">{s}</text>')
    for x, h in zip(xs, hors, strict=True):
        out.append(f'<text class="hor" x="{_f(x)}" y="{_f(top + 4 * ROW + 18)}" '
                   f'text-anchor="middle" font-size="11" fill="{MUTED}">{escape(str(h))}</text>')
    if is_score(intolerable):
        y = _f(_y(intolerable, top))
        out.append(f'<line class="threshold" x1="{LEFT}" x2="{RIGHT}" y1="{y}" y2="{y}" '
                   f'stroke="{INK}" stroke-width="1" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{RIGHT}" y="{_f(_y(5, top) - 8)}" text-anchor="end" font-size="10" '
                   f'fill="{MUTED}">- - - intolerable from {intolerable}</text>')
    return out


def _steps(scores: list[Any], xs: list[float], step: float, off: float,
           top: float = TOP) -> str:
    """One lens's path: each score held from its horizon to the next; a cell with none breaks it."""
    d, held = [], False
    for x, score in zip(xs, scores, strict=True):
        if not is_score(score):
            held = False
            continue
        y, end = _f(_y(score, top) + off), _f(x + step)
        d.append(f"V{y}H{end}" if held else f"M{_f(x)},{y}H{end}")
        held = True
    return "".join(d)


def stacked(charts: list[str]) -> str:
    """One chart as it is; several (a process with more than one activity), one under the other."""
    if len(charts) == 1:
        return charts[0]
    heights = [int(m[1]) if (m := re.search(r'height="(\d+)"', c)) else 0 for c in charts]
    inner = "".join(f'<svg y="{sum(heights[:k])}" ' + c[len("<svg "):]
                    for k, c in enumerate(charts))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{sum(heights)}" '
            f'viewBox="0 0 {WIDTH} {sum(heights)}">{inner}</svg>')


# ── t367: chart A (spec §13, 5_nemo_design; mockup variant 1) ─────────────────────────────────
#: t403 (his answer 2026-10-10T16:24:34Z, 8_nemo_design's option A): one line per category for each
#: year, last year's record against this year's interview, a category's colour the same in both
#: (r2: its own hue, `CLASS_COLOURS`):
#: this year's straight and solid with a dot at each hour, last year's dashed and faint behind it,
#: a blank hour no point. Lines that meet are drawn `DODGE` px apart; each of this year's lines ends
#: in its category's name, the names spaced `SPACED` apart with a leader to the line. The SVG holds
#: the drawing twice, a laptop plate and a phone plate of one shape, and shows the one that fits
#: (`@media` on the image's own width), never scrolled. The labels read 13 px at 1440, and at 390
#: at least the graph's 13 px rule (362: the chat draws the image ~295 px wide there, so the phone
#: plate's size is 15.5 on its 340); the phone plate states the scores as digits, with their words
#: in a key under the plot, its key for the years ("this year", "last record (2024)"), and the
#: hours closed up ("24h"). The drawing is taller than 367's (600, was 540), so the phone plate's
#: plot keeps room for five scores above those lines.
#: (plate, view box width, font size); the phone plate is drawn on the laptop's shape, scaled
PLATES = (("wide", 600, 13.0), ("narrow", 340, 15.5))
CHART_W, CHART_H = 600, 600
FONT = "Inter, system-ui, sans-serif"
RUST, SLATE, WHITE, MUTED_TEXT = (HARBOUR[n] for n in ("rust", "slate", "white", "muted"))
#: t517 (his TYPED 2026-10-19T05:45:03Z): a chart with no this-year line keys last year's
#: lines with their year, drawn `STRONG` (about twice as thick, in the full class colour)
LAST_STRONG = "last record ({year})"
STRONG = ' stroke-width="4" stroke-dasharray="6 4"'
LABEL = "Impact over time by category"
NOT_RECORDED = "not recorded"
#: t403: the end labels' least spacing, in ems
SPACED = 1.25
#: t430: an end label's letters reckoned this wide, in ems (bold: headless Chromium drew
#: "Operational" 0.605 em a letter, against 0.55 for the plate's regular text), and the end-label
#: column ends this far, in ems, inside the plate
END_EM, END_PAD = 0.62, 0.5
#: t403 r2: how wide the chat draws each plate, in px (read off the page: 600 at 1440, 295.4 at 390)
SHOWN = {"wide": 600, "narrow": 295}
#: t403 r2 (8_nemo_design, as the prototype): how far apart two neighbouring classes' lines are
#: drawn, in px as the chat shows each plate, so lines that meet never hide one another; r4: wide
#: enough that two read as two at a glance, a gap of daylight between this year's 2.6 strokes
DODGE = {"wide": 3.8, "narrow": 2.8}
#: t403 r3: last year's line drawn this far above its class's place, in px as shown (r2's half
#: dodge, kept as it was when r4 widened the dodge)
YEAR_OFF = {"wide": 1.3, "narrow": 1.1}
#: t403 r2: one hue a class (nemo's own `--color-class-*`), the same in both years
CLASS_COLOURS = {name.removeprefix("class-"): c for name, c in HARBOUR.items()
                 if name.startswith("class-")}
#: t403 r6: the width, in CSS px, at and under which the phone's look is shown: inside the chart's
#: own image (`_SWITCH`, on the image's width) and on the chat's page (`PAGE_SWITCH`, on the page's)
NARROW_PX = 480
_SWITCH = (f".narrow{{display:none}}@media (max-width:{NARROW_PX}px){{.wide{{display:none}}"
           ".narrow{display:inline}}")


def worst_points(grid: Mapping[str, Any] | None, hors: list[str]) -> list[int | None]:
    """The worst category's score at each hour (`worst_case_row`), None where no category has
    one: a blank stays blank."""
    worst = worst_case_row(_scored(grid, hors))
    return [worst.get(h) for h in hors]


#: t377 L: a year as a date names it ("9 Nov 2026", "24 Sep 2024, 15:23")
YEAR = re.compile(r"\b((?:19|20)\d\d)\b")


def year(said: str) -> str:
    """t377 L: the last year a date names, "" where it names none."""
    found = YEAR.findall(said)
    return found[-1] if found else ""


def last_word(year: str) -> str:
    """741 (his word, 'Last record (2024)'): last year's short word, by the year its record states;
    `LAST_YEAR` where it states none."""
    return LAST_STRONG.format(year=year) if year else LAST_YEAR


def conclusion(last: list[int | None], this: list[int | None], hors: list[str],
               method: Mapping[str, Any], years: tuple[str, str] = ("", "")) -> str:
    """One line on when each drawn year first reached the method's intolerable score, by its own
    word for it ("high"). t377 L: `years` (this year's grid's, last year's), each said after its
    year's words where known ("this year (2026)"), last year's in `LAST_STRONG`'s ("last record
    (2024)", 741, his word), `LAST_YEAR` with no year known. t403 r7: each hour held together
    (`NBSP`)."""
    now = f"{THIS_YEAR} ({years[0]})" if years[0] else THIS_YEAR
    then = last_word(years[1])
    level = threshold(method)
    word = next((str(s.get("label")) for s in method.get(SEVERITY_SCALE) or []
                 if isinstance(s, dict) and s.get("level") == level), str(level))

    def reached(points: list[int | None]) -> str | None:
        return next((NBSP.join(h.split()) for h, v in zip(hors, points, strict=True)
                     if v is not None and is_score(level) and v >= level), None)

    drawn_last, drawn_this = any(v is not None for v in last), any(v is not None for v in this)
    at_last, at_this = reached(last), reached(this)
    if drawn_this and not drawn_last:
        return f'Reached "{word}" at {at_this} {now}.' if at_this else \
            f'Not "{word}" {now}.'
    if not drawn_this:
        return f'{then.capitalize()} reached "{word}" at {at_last}.' if at_last else \
            f'{then.capitalize()} never reached "{word}".'
    this_part = f'Reached "{word}" at {at_this} {now}' if at_this else \
        f'Not "{word}" {now}'
    return f"{this_part}, against {at_last} {then}." if at_last else \
        f"{this_part}; {then} never."


class Lens(NamedTuple):
    """t403: one category as chart A draws it: its id, its label, its colour and each year's score
    at every hour (None where its grid states none)."""

    id: str
    said: str
    colour: str
    last: list[int | None]
    this: list[int | None]


class Drawn(NamedTuple):
    """What chart A draws, the same on both plates: each category's line for each year, each year's
    worst per hour (for "not recorded" and the conclusion), the record's recovery target, the key
    and the conclusion."""

    hors: list[str]
    lenses: list[Lens]
    last: list[int | None]
    this: list[int | None]
    target: str | None
    record: str | None
    keys: list[tuple[str, str]]
    said: str
    level: Any
    words: dict[Any, Any]
    last_word: str


class Plate(NamedTuple):
    """One plate's geometry: its view box, its font size and the plot inside it."""

    cls: str
    w: float
    h: float
    fs: float
    left: float
    top: float
    plot_w: float
    plot_h: float
    hours: int
    #: how far every other hour's label drops below its neighbours, 0 where they all fit in a row
    stagger: float = 0.0

    def x(self, i: int) -> float:
        return self.left + i * self.plot_w / (self.hours - 1)

    def y(self, v: float) -> float:
        return self.top + self.plot_h * (5 - v) / 4

    @property
    def phone(self) -> bool:
        return self.cls == "narrow"


def class_chart(last_grid: Mapping[str, Any] | None, this_grid: Mapping[str, Any] | None,
                method: Mapping[str, Any], *, last_said: str, this_said: str | None,
                target: str | None, record: str | None = None,
                years: tuple[str, str] = ("", "")) -> str:
    """Chart A, or `""` where neither grid holds a score. `last_said` and `this_said` are the
    key's words for each year ("Last record (1.2, 2024)", "This year's interview (1 Oct
    2026)"); t377 L: `years` go to `conclusion`;
    t517: no line drawn this year, last year's are `STRONG`, keyed `LAST_STRONG`. `target` is the
    record's recovery target, marked where it is one of the method's hours and a line has a point
    there, its label naming `record`, the record it is read from ("recovery target 72 h (record
    1.2)")."""
    return class_charts(last_grid, this_grid, method, last_said=last_said, this_said=this_said,
                        target=target, record=record, years=years)[0]


def class_charts(last_grid: Mapping[str, Any] | None, this_grid: Mapping[str, Any] | None,
                 method: Mapping[str, Any], *, last_said: str, this_said: str | None,
                 target: str | None, record: str | None = None,
                 years: tuple[str, str] = ("", "")) -> tuple[str, str]:
    """t403 r6 (spec §13, 403b): chart A as `class_chart` draws it, and beside it the phone's
    split of it (`phone_split`), both `""` where neither grid holds a score."""
    hors, order = horizons(method), lenses(method)
    last, this = worst_points(last_grid, hors), worst_points(this_grid, hors)
    if not any(v is not None for v in last + this):
        return "", ""
    names = {s["id"]: str(s.get("name") or s["id"]) for s in method.get("scenarios") or []
             if isinstance(s, dict) and s.get("id")}
    rows, prior = _scored(this_grid, hors), _scored(last_grid, hors)
    drawn_lenses = [Lens(lens, names.get(lens, lens).split()[0],
                         CLASS_COLOURS.get(lens) or _colour(order, lens),
                         [_score(prior.get(lens), h) for h in hors],
                         [_score(rows.get(lens), h) for h in hors])
                    for lens in order if lens in rows or lens in prior]
    drawn_this = any(v is not None for v in this)
    keys = ([("this", this_said or "")] if drawn_this else []) + (
        [("last", last_said) if drawn_this else
         ("strong", last_word(years[1]))]
        if any(v is not None for v in last) else [])
    drawn = Drawn(hors, drawn_lenses, last, this, target, record, keys,
                  conclusion(last, this, hors, method, years), threshold(method),
                  {s.get("level"): s.get("label") for s in method.get(SEVERITY_SCALE) or []
                   if isinstance(s, dict)}, last_word(years[1]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{CHART_W}" height="{CHART_H}" '
            f'viewBox="0 0 {CHART_W} {CHART_H}" role="img" aria-label="{LABEL}">'
            f"<style>{_SWITCH}</style>"
            f'<rect width="{CHART_W}" height="{CHART_H}" fill="{WHITE}"/>'
            + "".join(_plate(cls, w, fs, drawn) for cls, w, fs in PLATES) + "</svg>",
            phone_split(drawn))


def _score(row: Mapping[str, Any] | None, hor: str) -> int | None:
    v = (row or {}).get(hor)
    return v if is_score(v) else None


def _hour(hor: str, phone: bool) -> str:
    """An hour as the plate writes it: "24h" on the phone, "24 h" on the laptop."""
    return "".join(hor.split()) if phone else hor


def _scale_words(drawn: Drawn, per_line: int) -> list[str]:
    """t403: the phone's key for its digit scores, "1 none · 2 low · …"; r3: broken only between
    pairs, in as few rows as fit `per_line`, the rows as even as such a break makes them."""
    pairs = [f"{v} {drawn.words[v]}" for v in range(1, 6) if drawn.words.get(v)]
    for n in range(1, len(pairs) + 1):
        splits = [[" · ".join(pairs[a:b]) for a, b in itertools.pairwise((0, *cut, len(pairs)))]
                  for cut in itertools.combinations(range(1, len(pairs)), n - 1)]
        if fits := [rows for rows in splits if max(map(len, rows)) <= per_line]:
            return min(fits, key=lambda rows: max(map(len, rows)))
    return pairs


def _plate(cls: str, w: float, fs: float, drawn: Drawn) -> str:
    """One plate: the axis, the band, the marker, the lines and their labels, the key and the
    conclusion."""
    p, key_rows, scale, told = _frame(cls, w, fs, drawn)
    return _drawing(p, drawn, key_rows, scale, told, "0", CHART_W, CHART_H)


def _frame(cls: str, w: float, fs: float, drawn: Drawn, ends_of: list[Lens] | None = None,
           plot_h: float | None = None) -> tuple[Plate, list[list[tuple[str, str]]], list[str],
                                                 list[str]]:
    """A plate's geometry, its key's rows, its scale words and its conclusion's lines. r6: the end
    labels' column sized by `ends_of`'s labels (the drawn ones where not given), and a plate
    `plot_h` tall in the plot, as tall as it needs, where given (else the laptop's shape). A
    drawing with no key or no conclusion keeps no room for one."""
    phone = cls == "narrow"
    per_line = int((w - fs) / (0.55 * fs))
    # t403: the phone's key says the years in few words; 741: last year's by its record's year
    keys = [(line, {"this": THIS_YEAR, "last": drawn.last_word}.get(line, said) if phone else said)
            for line, said in drawn.keys]
    key_rows = ([keys] if sum(len(t) + 6 for _, t in keys) <= per_line else [[k] for k in keys]) \
        if keys else []
    told = (textwrap.wrap(drawn.said, per_line) or [drawn.said]) if drawn.said else []
    scale = _scale_words(drawn, per_line) if phone else []
    h = w * CHART_H / CHART_W
    left, top = (fs * 1.6 if phone else fs * 6.6), fs * 1.8
    # t403: the end labels' column at the right, as wide as the longest label and its leader
    # t430: reckoned as bold, `END_PAD` past its leader and label
    ends = max((_wide(lens.said, fs, END_EM) for lens in ends_of or drawn.lenses
                if _ends_at(lens, _named(drawn)) is not None), default=0.0)
    plot_w = w - left - (ends + fs * (1.4 + END_PAD) if ends else fs * 2.0)
    hours = [_hour(hor, phone) for hor in drawn.hors]
    # 362: two neighbouring hours wider than their spacing drop every other one a line
    apart = plot_w / (len(hours) - 1)
    stagger = fs * 1.2 if any((_wide(a, fs) + _wide(b, fs)) / 2 + fs * 0.4 > apart
                              for a, b in itertools.pairwise(hours)) else 0.0
    bottom = (fs * 2.2 + stagger + (len(key_rows) + len(scale)) * fs * 1.6
              + len(told) * fs * 1.45 + fs * 0.4)
    if plot_h is not None:
        h = top + plot_h + bottom
    return (Plate(cls, w, h, fs, left, top, plot_w, h - top - bottom, len(hours), stagger),
            key_rows, scale, told)


def _drawing(p: Plate, drawn: Drawn, key_rows: list[list[tuple[str, str]]], scale: list[str],
             told: list[str], y: str, width: float, height: float) -> str:
    return "".join([
        f'<svg class="{p.cls}" x="0" y="{y}" width="{width}" height="{height}" '
        f'viewBox="0 0 {_f(p.w)} {_f(p.h)}" font-family="{FONT}" font-size="{p.fs}">',
        *_band(p, drawn), *_scale(p, drawn), *_marker(p, drawn), *_lines(p, drawn),
        *_ends(p, drawn), *_key(p, key_rows, scale, told), "</svg>"])


# ── t403 r6: the phone split (spec §13, 403b; his answers 2026-10-11T07:23:46Z, 07:25:22Z,
# 07:31:41Z "Build it" on design-2026-10-11-403b/) ───────────────────────────────────────────
#: how many classes the phone's top chart holds, his "max three lines per chart"
TOP_CHART = 3
#: each phone chart's plot height, in the narrow plate's view units (the prototype's, both plots
#: ~130, `proto_403b.py`)
PHONE_PLOT_H = 130.0
#: the gap between the two phone charts, one text line (the conclusion's line spacing), from the
#: top chart's last baseline to the bottom chart's highest text
GAP_LINE = 1.45
#: the phone split's own image, by name in the chat; the laptop chart beside it keeps its name
PHONE_IMAGE = "impact-{k}-phone.svg"
#: t403 r6 (9_nemo_design's way out, after r6's measured STOP): the chat's card carries both
#: images and its own page shows one by width, at the image's own break (`NARROW_PX`): the phone
#: split's grid cell hidden on a wide page, the laptop chart's beside it hidden on a narrow one.
#: Nothing knows the device. (Chainlit lays a message's images in a grid, a cell each, in an
#: order of its own; a `:has()` holds no `:has()`: so on a narrow page, in a grid holding a phone
#: image, every other cell goes.)
_PHONE = "img[alt$='-phone.svg']"
PAGE_SWITCH = (f"div:has(> div > {_PHONE}){{display:none}}"
               f"@media (max-width:{NARROW_PX}px){{div:has(> div > {_PHONE}){{display:block}}"
               f"div:has(> div > div > {_PHONE}) > div:has(> div > img:not({_PHONE}))"
               "{display:none}}")


def images(charts: list[str], phones: list[str]) -> list[tuple[str, str]]:
    """t403 r6: a card's images by name, each chart as `impact-<k>.svg` (its name as it was),
    straight after it its phone split where it has one (`PHONE_IMAGE`)."""
    return [(name, svg) for k, chart in enumerate(charts)
            for name, svg in ((f"impact-{k}.svg", chart),
                              (PHONE_IMAGE.format(k=k), phones[k] if k < len(phones) else ""))
            if svg]


def worst_three(drawn: list[Lens]) -> list[Lens]:
    """The classes the phone's top chart holds, in the method's order: the `TOP_CHART` whose
    this-year line reaches the highest score, ties by the earliest hour reaching it, then the
    earliest hour it first rises (a score above the one before it), then the method's order. With
    no this-year line in any class, last year's lines, ranked the same way."""
    year = "this" if any(v is not None for lens in drawn for v in lens.this) else "last"

    def rank(at: tuple[int, Lens]) -> tuple[int, int, int, int]:
        k, lens = at
        scored = [(i, v) for i, v in enumerate(getattr(lens, year)) if v is not None]
        top = max((v for _, v in scored), default=0)
        never = len(lens.this)
        return (-top, next((i for i, v in scored if v == top), never),
                next((i for (_, a), (i, b) in itertools.pairwise(scored) if b > a), never), k)

    top = {lens.id for _, lens in sorted(enumerate(drawn), key=rank)[:TOP_CHART]}
    return [lens for lens in drawn if lens.id in top]


def phone_split(drawn: Drawn) -> str:
    """The phone's chart A as its own image: the narrow plate twice, stacked, the worst three
    classes on top (`worst_three`), the rest under them, each in the method's order with its own
    scale, band and recovery target marker; the scale words, years key and conclusion once, under
    the bottom chart. Both share one plot width and end-label column (sized by every drawn
    class's label) and one plot height, `GAP_LINE` apart. Three classes or fewer: one chart."""
    cls, w, fs = next(plate for plate in PLATES if plate[0] == "narrow")
    up = worst_three(drawn.lenses)
    rest = [lens for lens in drawn.lenses if lens not in up]
    charts = [drawn._replace(lenses=up, keys=[], said="", words={}),
              drawn._replace(lenses=rest)] if rest else [drawn]
    parts, y = [], 0.0
    for n, part in enumerate(charts):
        p, key_rows, scale, told = _frame(cls, w, fs, part, drawn.lenses, PHONE_PLOT_H)
        if n:  # one text line from the chart above's last hour to this chart's highest text
            y += GAP_LINE * fs - _highest(p, part)
        parts.append(_drawing(p, part, key_rows, scale, told, _f(y), w, p.h))
        y += p.y(1) + p.fs * 1.5 + p.stagger if n < len(charts) - 1 else p.h
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{CHART_W}" '
            f'height="{_f(CHART_W * y / w)}" viewBox="0 0 {_f(w)} {_f(y)}" role="img" '
            f'aria-label="{LABEL}" class="phone-split">'
            f'<rect width="{_f(w)}" height="{_f(y)}" fill="{WHITE}"/>' + "".join(parts) + "</svg>")


def _highest(p: Plate, drawn: Drawn) -> float:
    """The top of a plate's highest text: its recovery target's label, else its top score."""
    at = _target_at(p, drawn)
    return min(at[1], p.y(5) - p.fs * 0.5) if at else p.y(5) - p.fs * 0.5


def _wide(text: str, fs: float, em: float = 0.55) -> float:
    """About how wide a label runs at this size (the plate's own reckoning: 0.55 em a letter)."""
    return len(text) * em * fs


def _rgb(colour: str) -> list[float]:
    return [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def _on_white(colour: str) -> float:
    """WCAG 2.x: a colour's contrast against white, from its relative luminance."""
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in _rgb(colour)]
    return 1.05 / (0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2] + 0.05)


def legible(colour: str, ink: float) -> str:
    """t430: `colour` laid at `ink` over white, darkened a hundredth of ink at a time until it
    reads `NAME_CONTRAST` to 1 on white: the faintest of its own hue that does, as one colour."""
    for step in range(round(ink * 100), 101):
        a = step / 100
        mixed = "#" + "".join(f"{round((c * a + 1 - a) * 255):02x}" for c in _rgb(colour))
        if _on_white(mixed) >= NAME_CONTRAST:
            return mixed
    return colour


def _band(p: Plate, drawn: Drawn) -> list[str]:
    """The band from the intolerable score up, shaded, with its words at the left inside it."""
    level = drawn.level
    if not is_score(level):
        return []
    return [f'<rect class="band-fill" x="{_f(p.left)}" y="{_f(p.y(5))}" width="{_f(p.plot_w)}" '
            f'height="{_f(p.y(level) - p.y(5))}" fill="{RUST}" fill-opacity="0.07"/>',
            f'<text class="band" x="{_f(p.left + p.fs * 0.5)}" y="{_f(p.y(level) - p.fs * 0.5)}" '
            f'fill="{RUST}">intolerable from {escape(str(level))}</text>']


def _scale(p: Plate, drawn: Drawn) -> list[str]:
    """The scores 1-5 up the side, with their words on the laptop (t403: digits on the phone);
    the hours evenly along the bottom, "not recorded" over an hour no line has a point at."""
    out = []
    for v in range(1, 6):
        said = str(v) if p.phone else f"{v} {drawn.words.get(v, '')}"
        out.append(f'<line x1="{_f(p.left)}" x2="{_f(p.left + p.plot_w)}" y1="{_f(p.y(v))}" '
                   f'y2="{_f(p.y(v))}" stroke="{GRID_LINE}" stroke-width="1"/>')
        out.append(f'<text class="score" x="{_f(p.left - p.fs * 0.5)}" y="{_f(p.y(v))}" '
                   f'text-anchor="end" dominant-baseline="middle" fill="{MUTED_TEXT}">'
                   f"{escape(said)}</text>")
    for i, hor in enumerate(drawn.hors):
        drop = p.stagger if i % 2 else 0.0
        out.append(f'<text class="hor" x="{_f(p.x(i))}" y="{_f(p.y(1) + p.fs * 1.5 + drop)}" '
                   f'text-anchor="middle" fill="{MUTED_TEXT}">{escape(_hour(hor, p.phone))}</text>')
        if drawn.last[i] is None and drawn.this[i] is None:
            x, anchor = _inside(p, p.x(i), NOT_RECORDED)
            y = p.y(1) - p.fs * 0.9
            if anchor != "middle":
                y = _clear(p, drawn, x if anchor == "start" else x - _wide(NOT_RECORDED, p.fs), y)
            out.append(f'<text class="unrecorded" x="{_f(x)}" '
                       f'y="{_f(y)}" text-anchor="{anchor}" '
                       f'fill="{MUTED_TEXT}">{NOT_RECORDED}</text>')
    return out


def _clear(p: Plate, drawn: Drawn, left: float, y: float) -> float:
    """t517 r2 (15_nemo_design's nit): the baseline from `y` up, a quarter em at a time, where a
    "not recorded" starting at `left` meets no line of either year and no recovery target, under
    the band: held inside the plate it runs past its hour, over the lines from the next; `y`
    where no such baseline is."""
    right, pad = left + _wide(NOT_RECORDED, p.fs), p.fs * 0.3
    up = YEAR_OFF[p.cls] * p.w / SHOWN[p.cls]  # last year's lines, as `_lines` lifts them
    segs = [((p.x(i), p.y(a) + off), (p.x(i + 1), p.y(b) + off))
            for name, faint in (("last", True), ("this", False))
            for k, lens in enumerate(drawn.lenses)
            for off in [_off(p, drawn, k) - (up if faint else 0.0)]
            for i, (a, b) in enumerate(itertools.pairwise(getattr(lens, name)))
            if a is not None and b is not None]
    if at := _target_at(p, drawn):
        segs.append(((p.x(at[3]), p.top - p.fs * 0.6), (p.x(at[3]), p.y(1))))
    ceiling = p.y(drawn.level) if is_score(drawn.level) else p.top
    base = y
    while base - p.fs > ceiling:
        top, bottom = base - p.fs * 0.8 - pad, base + p.fs * 0.25 + pad
        if not any(left - pad <= x0 + (x1 - x0) * t / 40 <= right + pad
                   and top <= y0 + (y1 - y0) * t / 40 <= bottom
                   for (x0, y0), (x1, y1) in segs for t in range(41)):
            return base
        base -= p.fs * 0.25
    return y


def _inside(p: Plate, x: float, said: str) -> tuple[float, str]:
    """t517: where a label centred on `x` goes and its anchor: held whole inside the plate, half an
    em from its edge, where centred it would run past one (the phone's "not recorded" at 1 h)."""
    half, pad = _wide(said, p.fs) / 2, p.fs * 0.5
    if x - half < pad:
        return pad, "start"
    if x + half > p.w - pad:
        return p.w - pad, "end"
    return x, "middle"


def _marker(p: Plate, drawn: Drawn) -> list[str]:
    """The record's recovery target, dotted navy, where it is an hour a line has a point at."""
    if (at := _target_at(p, drawn)) is None:
        return []
    end, top, said, i = at
    tx, ty = _f(p.x(i)), _f(p.top - p.fs * 0.6)
    return [f'<line class="target" x1="{tx}" x2="{tx}" y1="{ty}" y2="{_f(p.y(1))}" '
            f'stroke="{INK}" stroke-width="1.2" stroke-dasharray="2 3"/>',
            f'<text class="target" x="{_f(end)}" y="{_f(top)}" text-anchor="end" '
            f'dominant-baseline="hanging" fill="{INK}">{escape(said)}</text>']


def _target_at(p: Plate, drawn: Drawn) -> tuple[float, float, str, int] | None:
    """Where the recovery target's label goes (its right end, its top), what it says and its
    hour's place; None where the target is no hour a line has a point at."""
    if drawn.target not in drawn.hors:
        return None
    i = drawn.hors.index(str(drawn.target))
    if drawn.last[i] is None and drawn.this[i] is None:
        return None
    said = f"recovery target {drawn.target}" + (f" (record {drawn.record})" if drawn.record else "")
    # 362: a label that would run into the scores' words goes up a line, and right enough to fit
    end, top = p.x(i) - p.fs * 0.4, p.top - p.fs * 0.6
    if end - _wide(said, p.fs) < p.left:
        end, top = min(max(end, p.fs * 0.5 + _wide(said, p.fs)), p.w - p.fs * 0.5), \
            p.top - p.fs * 1.6
    return end, top, said, i


def _off(p: Plate, drawn: Drawn, k: int) -> float:
    """t403: the k-th category's lines drawn this far below their scores, so lines that meet stay
    apart, the middle one on its score."""
    return (k - (len(drawn.lenses) - 1) / 2) * DODGE[p.cls] * p.w / SHOWN[p.cls]


def _lines(p: Plate, drawn: Drawn) -> list[str]:
    """Every category's line, last year's faint first so this year's are drawn over them; r3:
    last year's `YEAR_OFF` above its class's place, so where both years score the same it is
    never hidden under this year's."""
    out = []
    last = STRONG if _named(drawn) == "last" else \
        f' stroke-width="2" stroke-dasharray="6 4" stroke-opacity="{LAST_INK}"'
    for name, faint in (("last", True), ("this", False)):
        for k, lens in enumerate(drawn.lenses):
            off = _off(p, drawn, k) - (YEAR_OFF[p.cls] * p.w / SHOWN[p.cls] if faint else 0.0)
            out += _line(name, lens, getattr(lens, name), p.x, lambda v, o=off: p.y(v) + o,
                         last if faint else ' stroke-width="2.6"',
                         "" if faint else f'r="{_f(p.fs * 0.24)}" fill="{lens.colour}"')
    return out


def _named(drawn: Drawn) -> str:
    """t403 r7: the year whose lines are named at their ends: this year's, or last year's on a
    chart that draws no this-year line."""
    return "this" if any(v is not None for v in drawn.this) else "last"


def _ends_at(lens: Lens, year: str = "this") -> int | None:
    """Where a category's label goes: the last hour of its `year`'s line, None with none."""
    return max((i for i, v in enumerate(getattr(lens, year)) if v is not None), default=None)


def _ends(p: Plate, drawn: Drawn) -> list[str]:
    """t403: each of this year's lines named at its end, in its colour, the names `SPACED` apart
    (pushed down in the order the ends stand, then up together where they would run past the
    plot), each with a leader from its line's end. r7: with no this-year line, last year's lines
    named the same way, from where last year's line is drawn; t517: in their full colour, as those
    lines are now drawn (`STRONG`)."""
    year = _named(drawn)
    up = YEAR_OFF[p.cls] * p.w / SHOWN[p.cls] if year == "last" else 0.0
    at = sorted((p.y(getattr(lens, year)[i] or 1) + _off(p, drawn, k) - up, lens.said, lens)
                for k, lens in enumerate(drawn.lenses)
                if (i := _ends_at(lens, year)) is not None)
    ys: list[float] = []
    for y0, _, _ in at:
        ys.append(max(y0, ys[-1] + p.fs * SPACED) if ys else y0)
    lift = max(0.0, (ys[-1] if ys else 0.0) - (p.y(1) + p.fs * 0.3))
    x0 = p.x(len(drawn.hors) - 1)
    out = []
    for (y0, _, lens), y in zip(at, ys, strict=True):
        y -= lift
        out.append(f'<polyline class="leader" fill="none" stroke="{lens.colour}" stroke-width="1"'
                   f' points="{_f(x0 + p.fs * 0.4)},{_f(y0)} '
                   f'{_f(x0 + p.fs * 0.9)},{_f(y)} {_f(x0 + p.fs * 1.2)},{_f(y)}"/>')
        out.append(f'<text class="end" data-lens="{escape(lens.id)}" x="{_f(x0 + p.fs * 1.4)}" '
                   f'y="{_f(y)}" dominant-baseline="middle" fill="{lens.colour}" '
                   f'font-weight="600">{escape(lens.said)}</text>')
    return out


def _key(p: Plate, rows: list[list[tuple[str, str]]], scale: list[str],
         told: list[str]) -> list[str]:
    """The phone's scale words (t403), the key, one row (or a row an entry where one does not
    fit), then the conclusion."""
    out, fs, row_y = [], p.fs, p.y(1) + p.fs * 3.4 + p.stagger
    for text in scale:
        out.append(f'<text class="scale" x="{_f(fs * 0.5)}" y="{_f(row_y)}" '
                   f'dominant-baseline="middle" fill="{MUTED_TEXT}">{escape(text)}</text>')
        row_y += fs * 1.6
    for row in rows:
        kx = fs * 0.5
        for line, words in row:
            if line:
                dash = {"last": f' stroke-dasharray="6 4" stroke-opacity="{LAST_INK}"',
                        "strong": ' stroke-dasharray="6 4"'}.get(line, "")
                out.append(f'<line class="key-sample" x1="{_f(kx)}" x2="{_f(kx + fs * 1.4)}" '
                           f'y1="{_f(row_y)}" y2="{_f(row_y)}" stroke-width="3" '
                           f'stroke="{SLATE}"{dash}/>')
                kx += fs * 1.9
            out.append(f'<text class="key" x="{_f(kx)}" y="{_f(row_y)}" '
                       f'dominant-baseline="middle" fill="{INK}">{escape(words)}</text>')
            kx += (len(words) * 0.55 + 1.6) * fs
        row_y += fs * 1.6
    out += [f'<text class="conclusion" x="{_f(fs * 0.5)}" y="{_f(row_y + n * fs * 1.45)}" '
            f'dominant-baseline="middle" fill="{MUTED_TEXT}">{escape(text)}</text>'
            for n, text in enumerate(told)]
    return out


def _line(name: str, lens: Lens, points: list[int | None], x: Any, y: Any, stroke: str,
          dot: str) -> list[str]:
    """One category's line of one year, straight from point to point; a blank hour breaks it and
    gets no point. `dot` "" draws none."""
    d, held = [], False
    for i, v in enumerate(points):
        if v is None:
            held = False
            continue
        d.append(f"{'L' if held else 'M'}{_f(x(i))},{_f(y(v))}")
        held = True
    if not d:
        return []
    return [f'<path class="line-{name}" data-lens="{escape(lens.id)}" d="{" ".join(d)}" '
            f'fill="none" stroke="{lens.colour}"{stroke} stroke-linejoin="round"/>',
            *(f'<circle class="pt-{name}" cx="{_f(x(i))}" cy="{_f(y(v))}" {dot}/>'
              for i, v in enumerate(points) if v is not None and dot)]
