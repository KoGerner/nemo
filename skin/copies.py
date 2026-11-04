"""Ticket 437 (ADR-0052): the phone and the stage each run as N copies behind the room router.

On the demo day nemo runs as four copies (ADR-0052, decision 1), each on a port of its own, and the
room router (`room_router.py`, ticket 436) takes the port nginx and the phone proxy already send to:
127.0.0.1:8473 for the phone (behind his 8474), 127.0.0.1:8477 for the stage (behind the vhost's
/chat/). So nothing in front of nemo changes. `COPIES` below is the one place N is set: the units,
the router, the move's checks and the move walk all read it from here.

Every copy of a fleet shares one `PROTO_RUN` (so one rooms folder and one approot), its unit's one
`CHAINLIT_AUTH_SECRET` and run-live.sh's one `NEMO_SEED` (436's STOP 2); it differs only in its
port, its `NEMO_COPY=<k>/<n>` (copy k is the router's k-th URL) and its own `PROTO_LOG`, so four
processes never append turn lines to one file.

    copies.py copy <fleet> <k>   exec copy k: run-live.sh (the guard, then the app), as the unit
                                 nemo-<fleet>-copy@<k> starts it
    copies.py router <fleet>     exec the room router on the fleet's port, the copies in order
    copies.py units <fleet>      the fleet's unit names, the copies first, the router last
    copies.py check <fleet>      every copy and the router answer the fleet's probe with 200; one
                                 line, exit 1 when any does not (the phone move's per-copy check)

`--first-port P --router-port R --run DIR` walk a fleet on scratch ports and folders; a live port is
never a scratch one. With `PROTO_CHECK_ONLY` set, `router` prints what it would start and starts
nothing, as run-live.sh does for a copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

#: ADR-0052: four copies on the day (three is the floor). The one place N is set.
COPIES = 4
SKIN = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Fleet:
    """One app run as copies: the router's port and root, the copies' first port, and the run
    folder every copy shares."""

    name: str
    port: int
    root: str
    first: int
    run: str


FLEETS = {
    "phone": Fleet("phone", 8473, "", 8511, "/home/user/work/nemo/skin/run"),
    "demo": Fleet("demo", 8477, "/chat", 8521, "/home/user/work/nemo-demo-run"),
}
#: the ports the live apps hold: his proxy, the public site, and every fleet's router and copies
LIVE_PORTS = frozenset({8474, 8476, *(f.port for f in FLEETS.values()),
                        *(f.first + k for f in FLEETS.values() for k in range(COPIES))})


def copy_of(code: str, copies: int) -> int:
    """The copy, 0 to copies - 1, that holds the room (t436): a function of the code alone, the
    same in every process and after any restart. `stage_door.copy_of` is this."""
    return int.from_bytes(hashlib.sha256(code.encode()).digest()[:8], "big") % copies


def ports(fleet: Fleet) -> list[int]:
    return [fleet.first + k for k in range(COPIES)]


def urls(fleet: Fleet) -> list[str]:
    """The copies in the router's order: copy k is the k-th."""
    return [f"http://127.0.0.1:{p}" for p in ports(fleet)]


def log(fleet: Fleet, k: int) -> Path:
    """Copy k's own turn log."""
    return Path(fleet.run) / f"proto-copy{k}.log"


def copy_env(fleet: Fleet, k: int) -> dict[str, str]:
    """What copy k is started with on top of its unit's environment."""
    if not 0 <= k < COPIES:
        raise SystemExit(f"copies.py: there is no copy {k} of {COPIES}")
    return {"PROTO_RUN": fleet.run, "PROTO_PORT": str(fleet.first + k),
            "PROTO_ROOT_PATH": fleet.root, "NEMO_COPY": f"{k}/{COPIES}",
            "PROTO_LOG": str(log(fleet, k))}


def router_args(fleet: Fleet) -> list[str]:
    return ["--root", fleet.root, "--log", str(Path(fleet.run) / "router.jsonl"), "127.0.0.1",
            str(fleet.port), *urls(fleet)]


def units(fleet: Fleet) -> list[str]:
    return [*(f"nemo-{fleet.name}-copy@{k}.service" for k in range(COPIES)),
            f"nemo-{fleet.name}-router.service"]


def _status(url: str) -> int | str:
    try:
        with urllib.request.urlopen(url, timeout=10) as answer:
            return int(answer.status)
    except urllib.error.HTTPError as e:
        return e.code
    except OSError as e:
        return type(e).__name__


def check(fleet: Fleet, status: Callable[[str], int | str] = _status) -> tuple[bool, str]:
    """Each copy and the router asked for the fleet's landing page (`<root>/start`)."""
    asked = [*((f"copy {k}", u) for k, u in enumerate(urls(fleet))),
             ("router", f"http://127.0.0.1:{fleet.port}")]
    said = [(name, url, status(f"{url}{fleet.root}/start")) for name, url in asked]
    serving = sum(1 for name, _, s in said if name != "router" and s == 200)
    ok = all(s == 200 for _, _, s in said)
    return ok, (f"{fleet.name}: {serving} of {COPIES} copies serve, router "
                f"{'serves' if said[-1][2] == 200 else 'does not serve'} ("
                + ", ".join(f"{name} :{url.rpartition(':')[2]} {s}" for name, url, s in said)
                + ")")


def scratched(fleet: Fleet, got: argparse.Namespace) -> Fleet:
    """The fleet on the scratch ports and folder the flags name; never on a live port."""
    out = replace(fleet, first=got.first_port or fleet.first, port=got.router_port or fleet.port,
                  run=got.run or fleet.run)
    if out != fleet and LIVE_PORTS & {out.port, *ports(out)}:
        raise SystemExit(f"copies.py: a scratch fleet never takes a live port "
                         f"({', '.join(map(str, sorted(LIVE_PORTS)))})")
    return out


def main(argv: list[str]) -> int:
    ask = argparse.ArgumentParser(prog="copies.py", description=__doc__.partition("\n")[0])
    ask.add_argument("what", choices=["copy", "router", "units", "check"])
    ask.add_argument("fleet", choices=sorted(FLEETS))
    ask.add_argument("k", nargs="?", type=int)
    ask.add_argument("--first-port", type=int)
    ask.add_argument("--router-port", type=int)
    ask.add_argument("--run")
    got = ask.parse_args(argv)
    if (got.what == "copy") != (got.k is not None):
        ask.error("copy takes <k>; nothing else does")
    fleet = scratched(FLEETS[got.fleet], got)
    if got.what == "units":
        print(" ".join(units(fleet)))
        return 0
    if got.what == "check":
        ok, line = check(fleet)
        print(line)
        return 0 if ok else 1
    if got.what == "copy":
        env = {**os.environ, **copy_env(fleet, got.k)}
        env.setdefault("PROTO_CHECKOUT", str(SKIN))  # the guard checks the tree it runs from
        os.execve("/bin/bash", ["/bin/bash", str(SKIN / "run-live.sh")], env)
    argv = [sys.executable, str(SKIN / "room_router.py"), *router_args(fleet)]
    if os.environ.get("PROTO_CHECK_ONLY"):
        print(f"copies.py: PROTO_CHECK_ONLY is set; would route: {json.dumps(argv)}")
        return 0
    os.execv(sys.executable, argv)
    return 1  # pragma: no cover - exec does not return


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
