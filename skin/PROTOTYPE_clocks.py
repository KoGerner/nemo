"""PROTOTYPE, throwaway. Ticket 69 (nemo-conversation 12): a walk says how fast it was.

Reads walks back from their logs, turn by turn, and prints per walk how it ended and its clocks:

- **model latency**: seconds inside the model lane per turn (the skin's own measurement);
- **scripted elapsed**: a bakeoff walk's own wall-clock (the script answers instantly, so this
  proves nothing about a person);
- **human completion**: a walk a person made on a phone (the live app's log), first turn to last.
  Only walks named with --human ROOM: the log cannot tell a person from the check session, which
  walks the skin in its own rooms. Any other live walk has no human clock, only its wall-clock.

The three are never summed. The owner's bar (docs/what-good-looks-like.md §3) is computed only from
the human clock. The per-turn ceiling (owner, 2026-09-18) is checked over bakeoff turns.

    python PROTOTYPE_clocks.py [turns files or dirs …] [--live run/proto.log [--human ROOM …]]

With no arguments it reads the bakeoff archive's *.turns.jsonl (BAKEOFF) and every saved
.build/**/*.turns*.jsonl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # this tree's own src (135)

from nemo.room_store import SHRINK_FACTOR  # noqa: E402 — nemo's own rule for a shrunk document

PROTO = Path(__file__).parent
#: The bakeoff's runs and instrument files. Ticket 242 step 8 archived skin/bakeoff/ outside the
#: repo (the last commit holding it is 1d2a7908); `NEMO_BAKEOFF` points a run elsewhere.
BAKEOFF = Path(os.environ.get("NEMO_BAKEOFF", Path.home() / "work/nemo-builds/bakeoff-archive"))

#: A walk with no turn for this long, and no end of its own, is `abandoned`. The owner's bar gives
#: a whole walk 20 minutes (what-good-looks-like §3); one silence as long as the whole budget means
#: this walk has already failed it, so a turn after it is read as a new walk, not the same one.
ABANDON_AFTER_S = 20 * 60
#: The owner's per-turn ceiling on the bakeoff (2026-09-18): worst turn and median, in seconds.
CEILING_WORST_S, CEILING_MEDIAN_S = 30, 10
#: The owner's bar (what-good-looks-like §3, restated 2026-09-13): typed replies, stage cards
#: answered, signatures, minutes.
BAR_TYPED, BAR_CARDS, BAR_SIGNATURES, BAR_MINUTES = 7, 5, 1, 20
#: The app's opener lines start so (PROTOTYPE_conversation_app); an old log logged them as typed.
OPENER = "(The manager has just opened the room"


def _failed(t: dict[str, Any]) -> bool:
    """A turn that raised: a bakeoff turn's `error`, a live turn's `failed` (ticket 69)."""
    return bool(t.get("error") or t.get("failed"))


def _silent_end(last_at: float | None, now: float) -> str:
    return "abandoned" if last_at is None or now - last_at >= ABANDON_AFTER_S else "open"


# ── bakeoff turns files ───────────────────────────────────────────────────────────────────────
def _seed(path: Path, scenario: str) -> str:
    m = re.findall(r"(?<!\d)(\d{4})(?!\d)", f"{path.parent.name}/{path.name}")
    if m:
        return m[-1]  # type: ignore[no-any-return]  # re.findall's items are Any
    try:
        return str(json.loads((path.parent / f"{scenario}.json").read_text()).get("seed", "?"))
    except (OSError, ValueError):
        return "?"


def _termination(path: Path, scenario: str) -> dict[str, str]:
    """An old run's ends, from the scenario file written beside its turns (before ticket 69)."""
    for name in (f"{scenario}.json", *(p.name for p in path.parent.glob(f"{scenario}-*.json"))):
        try:
            data = json.loads((path.parent / name).read_text())
        except (OSError, ValueError):
            continue
        return (data.get("scores") or {}).get("termination") or {}
    return {}


def bakeoff_walks(path: Path, now: float | None = None) -> list[dict[str, Any]]:
    """The walks in one bakeoff turns file, each starting at its turn 0."""
    now = time.time() if now is None else now
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    groups: list[list[dict[str, Any]]] = []
    for t in rows:
        if t.get("n") == 0 or not groups:
            groups.append([])
        groups[-1].append(t)
    walks = []
    for turns in groups:
        last, scenario = turns[-1], turns[0].get("scenario", "?")
        key = f"{last['activity']} ({last['route']})" if last.get("route") else last.get("activity")
        if "end" in last:  # ticket 69: the last line says how it ended; None: killed, or going on
            end = last["end"] or _silent_end(last.get("at"), now)
        else:  # before ticket 69 only the scenario file beside it says, and only for a finished run
            # why: `.get` of a key it lacks, None included, gives None
            end = _termination(path, scenario).get(key) or _silent_end(path.stat().st_mtime, now)  # type: ignore[arg-type]
        walks.append({"source": str(path), "scenario": scenario, "seed": _seed(path, scenario),
                      "activity": key, "clock": "scripted", "end": end, "turns": turns})
    return walks


# ── the live app's log ────────────────────────────────────────────────────────────────────────
def _signed(t: dict[str, Any]) -> bool:
    if "sign" not in (t.get("tools") or []) or t.get("refusal") or _failed(t):
        return False
    return bool(t.get("signed", True))


def _dated(rows: list[dict[str, Any]], last_write: float) -> None:
    """Give an old turn line (before ticket 69, no epoch) the epoch its H:M:S stands for.

    The log is appended in time order, so its H:M:S roll over midnight in order, and its last line
    was written when the file last was. A silence of a whole day between two lines is not seen."""
    day, last, sec = 0, None, {}
    for i, row in enumerate(rows):
        try:
            h, m, s = (int(x) for x in str(row["t"]).split(":"))
        except (KeyError, ValueError):
            continue
        now = h * 3600 + m * 60 + s
        day += 86400 if last is not None and now < last else 0
        last, sec[i] = now, now + day
    if not sec:
        return
    anchor = last_write - sec[max(sec)]
    for i, row in enumerate(rows):
        t = row.get("turn")
        if isinstance(t, dict) and "at" not in t and i in sec:
            t["at"] = round(anchor + sec[i], 1)


def live_walks(log: Path, now: float | None = None, human: set[str] | frozenset[str] = frozenset()
               ) -> list[dict[str, Any]]:
    """The walks made at the skin, per room and model, from the app's log.

    A walk ends `signed` on the turn that signs; `error` or `abandoned` when no turn follows for
    ABANDON_AFTER_S (by whether its last turn failed); and is `open` while it may still go on. A
    walk in a room named in `human` is a person's (the human clock); any other is at the skin."""
    now = time.time() if now is None else now
    rows = []
    for line in log.read_text(errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    rows = [r for r in rows if isinstance(r, dict)]
    _dated(rows, log.stat().st_mtime)
    streams: dict[tuple[str, str], list[dict[str, Any]]] = {}
    said: dict[str, str] = {}
    refused: dict[str, bool] = {}  # room -> its last sign call came back an error
    for row in rows:
        room = str(row.get("room"))
        if isinstance(row.get("manager"), dict):
            said[room] = str(row["manager"].get("text") or "")
            continue
        if isinstance(row.get("tool"), dict) and row["tool"].get("name") == "sign":
            result = row["tool"].get("result")
            refused[room] = isinstance(result, dict) and "error" in result
            continue
        t = row.get("turn")
        if not isinstance(t, dict):
            continue
        t = dict(t)
        if t.get("how") == "typed" and said.get(room, "").startswith(OPENER):
            t["how"] = "opener"  # an old line logged the app's opener as typed
        if "signed" not in t and "sign" in (t.get("tools") or []):  # an old line: its sign call's
            t["signed"] = not refused.pop(room, False)  # result, when its line was not cut
        streams.setdefault((room, str(t.get("model"))), []).append(t)
    walks = []
    for (room, model), turns in streams.items():
        cur: list[dict[str, Any]] = []

        def close(end: str) -> None:
            walks.append(
                {
                    "source": "live",
                    "room": room,
                    "model": model,
                    "clock": "human" if room in human else "skin",
                    "activity": next(
                        (x["activity"] for x in reversed(cur) if x.get("activity")), None
                    ),
                    "end": end,
                    "turns": list(cur),
                }
            )
            cur.clear()
        for t in turns:
            if cur and None not in (t.get("at"), cur[-1].get("at")) and \
                    t["at"] - cur[-1]["at"] >= ABANDON_AFTER_S:
                close("error" if _failed(cur[-1]) else "abandoned")
            cur.append(t)
            if _signed(t):
                close("signed")
        if cur:
            end = _silent_end(cur[-1].get("at"), now)
            close("error" if end == "abandoned" and _failed(cur[-1]) else end)
    return walks


# ── clocks, ceiling, the owner's bar ──────────────────────────────────────────────────────────
def _span_s(turns: list[dict[str, Any]]) -> float | None:
    return turns[-1]["at"] - turns[0]["at"] if turns and all("at" in t for t in turns) else None


def walk_clocks(w: dict[str, Any]) -> dict[str, Any]:
    """The three clocks of one walk, apart. At most one of the last two is ever filled."""
    lat = [t["model_seconds"] for t in w["turns"] if t.get("model_seconds") is not None]
    span = _span_s(w["turns"])
    return {
        "model_latency": {
            "median_s": statistics.median(lat) if lat else None,
            "worst_s": max(lat) if lat else None,
            "turns": len(lat),
        },
        "scripted_elapsed_s": w["turns"][-1].get("elapsed") if w["clock"] == "scripted" else None,
        "human_minutes": round(span / 60, 1)
        if w["clock"] == "human" and span is not None
        else None,
    }


def _timed(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The turns the ceiling is read from: finished, and not the wait before a lane gave up.

    Fix 1: a failed turn now carries `seconds` (ticket 69 made the core log it; run_walk used to
    write null), and `PROTOTYPE_lanes` retries inside a 600 s timeout. Counting that wait would let
    one lane outage red the owner's 30 s ceiling with nothing about nemo having changed.
    """
    return [t for t in turns if t.get("seconds") is not None and not _failed(t)]


def worst_turn(turns: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The slowest turn the ceiling counts: the one the worst figure comes from."""
    return max(_timed(turns), key=lambda t: t["seconds"], default=None)


def unaccounted_s(t: dict[str, Any]) -> float | None:
    """The turn's seconds that neither the model lane nor a tool accounted for.

    Fix 1: the 497.6 s confirm-interview turn logged 7.75 s of model and 0.02 s of tools, so ~490 s
    of what the manager waited for had no name at all. What those seconds went on is not in the log,
    so this names them as unaccounted and guesses nothing. Worked out here for a line logged before
    the core published the number itself.
    """
    if t.get("unaccounted_seconds") is not None:
        return t["unaccounted_seconds"]  # type: ignore[no-any-return]  # a JSON value
    s, m, k = t.get("seconds"), t.get("model_seconds"), t.get("tool_seconds")
    # why: `None in (s, m, k)` is checked first
    return None if None in (s, m, k) else round(s - m - k, 2)  # type: ignore[operator]


def ceiling(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """The owner's per-turn ceiling over whole turns (what the manager waits for: model + tools)."""
    s = [t["seconds"] for t in _timed(turns)]
    if not s:
        return {"worst_s": None, "median_s": None, "turns": 0, "pass": None}
    worst, median = max(s), statistics.median(s)
    return {"worst_s": worst, "median_s": median, "turns": len(s),
            "pass": worst <= CEILING_WORST_S and median <= CEILING_MEDIAN_S}


def most_critical(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The turns where he asked which activity is most critical: their calls and seconds."""
    return [{"n": t.get("n"), "calls": len(t.get("tools") or []), "tools": t.get("tools") or [],
             "seconds": t.get("seconds")}
            for t in turns if re.search(r"most critical", str(t.get("said") or ""), re.I)]


def _cards(turns: list[dict[str, Any]]) -> int | None:
    """Stage cards answered in the walk: each stage an activity rose through, counted once. A turn
    says the stage it started from; an old line does not, so its first sighting is the start."""
    if not any("stage" in t for t in turns):
        return None  # an old log line has no stage: cards unknown, not 0
    stages: dict[str, int] = {}
    cards: set[tuple[str, int]] = set()
    for t in turns:
        a, st = t.get("activity"), t.get("stage")
        if not a or st is None:
            continue
        cards |= {(a, s) for s in range(t.get("stage_before", stages.get(a, st)) + 1, st + 1)}
        stages[a] = st
    return len(cards)


def _shrunk(turns: list[dict[str, Any]]) -> list[str] | None:
    """Artefacts left with less than 1/SHRINK_FACTOR of the most they held in the walk (nemo's own
    rule, `nemo.room_store`), gone ones included."""
    sized = [t["artefacts"] for t in turns if isinstance(t.get("artefacts"), dict)]
    if not sized:
        return None  # an old log line has no sizes: the check was not made
    most: dict[str, int] = {}
    shrunk: set[str] = set()
    for sizes in sized:
        shrunk |= {p for p, n in most.items() if n > SHRINK_FACTOR * sizes.get(p, 0)}
        for p, n in sizes.items():
            most[p] = max(n, most.get(p, 0))
    return sorted(shrunk)


def owners_bar(w: dict[str, Any]) -> dict[str, Any] | None:
    """The owner's bar, from a human walk only; None for any other clock."""
    if w["clock"] != "human":
        return None
    turns = w["turns"]
    typed = sum(t.get("how") == "typed" for t in turns)
    cards, shrunk = _cards(turns), _shrunk(turns)
    signature = sum(_signed(t) for t in turns)
    span = _span_s(turns)
    minutes = round(span / 60, 1) if span is not None else None
    return {"typed": typed, "cards": cards, "signature": signature, "minutes": minutes,
            "shrunk": shrunk,
            "pass": typed <= BAR_TYPED and cards == BAR_CARDS and signature == BAR_SIGNATURES
            and minutes is not None and minutes <= BAR_MINUTES and shrunk == []}


# ── the printout ──────────────────────────────────────────────────────────────────────────────
def _fmt(x: Any) -> str:
    return "—" if x is None else f"{x:g}" if isinstance(x, (int, float)) else str(x)


def walk_line(w: dict[str, Any]) -> str:
    c = walk_clocks(w)
    how = [t.get("how") for t in w["turns"]]
    head = (
        f"{w.get('scenario', w.get('room'))} {w.get('seed', w.get('model'))} · "
        f"{_fmt(w['activity'])} · "
        f"ended {w['end']} · {len(how)} turns ({how.count('typed')} typed, {how.count('tapped')} "
        "tapped)"
    )
    lat = c["model_latency"]
    line = (
        f"{head}\n    model latency: median {_fmt(lat['median_s'])} s, worst "
        f"{_fmt(lat['worst_s'])} s"
        f"  |  scripted elapsed: {_fmt(c['scripted_elapsed_s'])} s"
        f"  |  human completion: {_fmt(c['human_minutes'])} min"
    )
    if w["clock"] == "skin":
        span = _span_s(w["turns"])
        line += (
            f"\n    wall-clock at the skin {_fmt(None if span is None else round(span / 60, 1))} "
            "min: "
            "not named a person's walk (--human), so no human clock and no owner's bar"
        )
    bar = owners_bar(w)
    if bar:
        shrunk = (
            "not checked (no sizes logged)" if bar["shrunk"] is None else bar["shrunk"] or "none"
        )
        line += (
            f"\n    owner's bar (human clock): typed {bar['typed']}/≤{BAR_TYPED}, cards "
            f"{_fmt(bar['cards'])}/{BAR_CARDS}, signature {bar['signature']}/{BAR_SIGNATURES}, "
            f"{_fmt(bar['minutes'])}/≤{BAR_MINUTES} min, shrunk {shrunk} → "
            f"{'MET' if bar['pass'] else 'not met'}"
        )
    return line


def turns_files(args: list[str], bakeoff: Path = BAKEOFF) -> list[Path]:
    if not args:
        return sorted(
            [*bakeoff.glob("*.turns.jsonl"), *PROTO.glob(".build/**/*.turns*.jsonl")]
        )
    out = []
    for a in map(Path, args):
        out += sorted(a.rglob("*.turns*.jsonl")) if a.is_dir() else [a]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--live", help="the live app's log (run/proto.log): the walks made at the skin")
    ap.add_argument("--human", action="append", default=[], metavar="ROOM",
                    help="a room whose live walks a person made on a phone (the human clock)")
    ap.add_argument("--walks", action="store_true", help="print every walk, not only the ceiling")
    a = ap.parse_args()
    print(f"Ceiling over bakeoff turns: worst ≤ {CEILING_WORST_S} s, median ≤ {CEILING_MEDIAN_S} s "
          "(whole turns: model + tools)")
    seen: dict[str, Path]
    everything, seen = [], {}
    for f in turns_files(a.paths):
        name = f.relative_to(PROTO) if f.is_relative_to(PROTO) else f
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        if digest in seen:  # a saved copy of a run already counted: listed, never counted twice
            print(f"  {name} · a copy of {seen[digest]}")
            continue
        seen[digest] = name
        walks = bakeoff_walks(f)
        turns = [t for w in walks for t in w["turns"]]
        everything += turns
        c = ceiling(turns)
        crit = most_critical(turns)
        dead = sum(_failed(t) for t in turns)
        print(
            f"  {name} · "
            f"{walks[0]['scenario'] if walks else '?'} seed {walks[0]['seed'] if walks else '?'} · "
            f"{c['turns']} turns · worst {_fmt(c['worst_s'])} s · median {_fmt(c['median_s'])} s · "
            f"{'pass' if c['pass'] else 'FAIL' if c['pass'] is False else '—'}"
            + (f" · {dead} failed turn(s), not counted" if dead else "")
            + "".join(
                f" · most critical: turn {m['n']}, {m['calls']} call(s) {m['tools']}, "
                f"{_fmt(m['seconds'])} s"
                for m in crit
            )
        )
        if c["pass"] is False and (w := worst_turn(turns)):  # fix 1: where the worst turn went
            print(f"      worst turn {_fmt(w.get('n'))}: {_fmt(w.get('seconds'))} s = model "
                  f"{_fmt(w.get('model_seconds'))} s + tools {_fmt(w.get('tool_seconds'))} s + "
                  f"{_fmt(unaccounted_s(w))} s unaccounted")
        if a.walks:
            for w in walks:
                print("    " + walk_line(w).replace("\n", "\n    "))
    c = ceiling(everything)
    print(
        f"All saved bakeoff turns (each run once): {c['turns']} · worst {_fmt(c['worst_s'])} s · "
        "median "
        f"{_fmt(c['median_s'])} s · "
        f"{'pass' if c['pass'] else 'FAIL' if c['pass'] is False else '—'}"
        f" · {sum(_failed(t) for t in everything)} failed turn(s), not counted"
    )
    if a.live:
        print(
            f"\nLive walks ({a.live}); a walk is abandoned after {ABANDON_AFTER_S // 60} min with "
            "no turn:"
        )
        for w in live_walks(Path(a.live), human=set(a.human)):
            print("  " + walk_line(w).replace("\n", "\n  "))


if __name__ == "__main__":
    main()
