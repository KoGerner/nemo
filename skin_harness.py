"""The phone app, `skin/PROTOTYPE_conversation_app.py`, loaded under nemo's own interpreter over
stand-ins for Chainlit and httpx, with a scripted lane in place of the model.

Ticket 164. The phone app is what a manager talks to on 10 November (`skin/run-live.sh` runs it),
so the steps behind `features/` drive it rather than the old demo skin. Chainlit is not a nemo
dependency and must not become one (ADR-0001), and neither is httpx, which the phone's lane module
imports. So this module supplies the names the app takes from `chainlit`, records what it sent,
and loads the app's own file whole: the doors (`stage_qr`, which mints, and `room`, which opens),
the greeting (`start`) and a typed turn (`typed`) are the app's lines, not a restatement of them.

**Every model turn goes through a scripted lane.** `PROTOTYPE_lanes._litellm` and `_codex` are
replaced by `scripted_lane`, which answers with a fixed reply and counts the calls, and the httpx
stand-in raises if anything reaches for the network. The rest is real: the room is minted by
`nemo.walk`, the session is `PROTOTYPE_core.Session`, and a turn is written by the real writer. A
live model would make the coder gate depend on the lane again, which it must not.

**The app is loaded once per scenario, and what loading it does is undone afterwards.** Importing
the app runs `core.install_patches()`, which rebinds names in `nemo.walk` and `nemo.bia` for the
whole process. The phone runs with them, so a scenario on the
phone does too; every other test in this process must not, so each rebinding is handed to the
scenario's `monkeypatch` and undone when it ends.

It lives at the root for the reason `features_steps.py` does: the root is on `sys.path` for every
run of this suite.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent
PHONE = REPO / "skin"

#: The file a manager's phone runs.
APP = PHONE / "PROTOTYPE_conversation_app.py"

#: What the scripted lane answers every model call with. Plain text and no tool call, so a typed
#: turn is one model call and a reply: the walk is not moved by it.
SCRIPTED_REPLY = "Thank you. Tell me more when you are ready."

#: Every message the app has sent, in the order it sent them.
SENT: list[Any] = []

#: Every call the scripted lane answered, by model: a scenario sees the lane was the scripted one.
LANE_CALLS: list[str] = []

#: Replies a scenario scripts for the next model calls, in order, before `SCRIPTED_REPLY` again:
#: a tool call the model would make on the manager's words is scripted here, never inferred.
SCRIPTED: list[dict[str, Any]] = []

#: The app loaded for the scenario running now.
app: Any = None


class User:
    def __init__(self, identifier: str, metadata: dict[str, Any] | None = None) -> None:
        self.identifier = identifier
        self.metadata = metadata or {}


class Action:
    def __init__(self, name: str, label: str = "", payload: dict[str, Any] | None = None) -> None:
        self.name, self.label, self.payload = name, label, payload or {}

    async def remove(self) -> None:
        pass


class Image:
    """`cl.Image`: a picture on a message (ticket 255's impact chart). Only what it carries."""

    def __init__(self, name: str = "", content: bytes = b"", mime: str = "", **_: Any) -> None:
        self.name, self.content, self.mime = name, content, mime


class Message:
    def __init__(self, content: str = "", author: str = "nemo", actions: Any = (),
                 type: str = "assistant_message", elements: Any = ()) -> None:
        self.content, self.author, self.actions, self.type = content, author, list(actions), type
        self.elements = list(elements)

    async def send(self) -> Message:
        SENT.append(self)
        return self

    @property
    def labels(self) -> list[str]:
        return [action.label for action in self.actions]


class Step:
    """`cl.Step`: the "thinking" line around a turn. Nothing of it is on the manager's screen."""

    def __init__(self, **_: Any) -> None:
        self.output = None

    async def __aenter__(self) -> Step:
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False


class ChatSettings:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def send(self) -> None:
        pass


class UserSession(dict[str, Any]):
    """`cl.user_session`: one browser tab's state, read with `get` and written with `set`."""

    def set(self, key: str, value: Any) -> None:
        self[key] = value


#: The loop a turn is awaited on, so `run_sync` from the turn's worker thread can reach it.
_LOOP: dict[str, asyncio.AbstractEventLoop] = {}


def make_async(func: Any) -> Any:
    """What `cl.make_async` is: the call moved onto a worker thread, awaited by the caller."""
    async def called(*args: Any, **kwargs: Any) -> Any:
        _LOOP["now"] = asyncio.get_running_loop()
        return await asyncio.to_thread(func, *args, **kwargs)
    return called


def run_sync(coroutine: Any) -> Any:
    """What `cl.run_sync` is: a coroutine run on the app's loop from a worker thread."""
    return asyncio.run_coroutine_threadsafe(coroutine, _LOOP["now"]).result()


async def chainlit_connect(sid: str, environ: dict[str, Any], auth: dict[str, Any] | None) -> bool:
    """Chainlit's own CONNECT handler, which the app's guard stands in front of."""
    return True


def _register(func: Any) -> Any:
    return func


def _chainlit(root: Path) -> dict[str, types.ModuleType]:
    """Every module the app imports from Chainlit, as one fresh set per load, over `root`.

    `tests/gate/test_skin_harness_stand_ins.py` reads the app's own imports and asserts this set
    offers each of them: the contract is two files wide, so it is a named failure here rather than
    an `ImportError` under every scenario.
    """
    chainlit = types.ModuleType("chainlit")
    widgets = types.ModuleType("chainlit.input_widget")
    socket = types.ModuleType("chainlit.socket")
    for name, value in {
        "User": User, "Action": Action, "Message": Message, "Image": Image, "Step": Step,
        "ChatSettings": ChatSettings, "make_async": make_async, "run_sync": run_sync,
        "user_session": UserSession(), "header_auth_callback": _register,
        "on_chat_start": _register, "on_settings_update": _register, "on_message": _register,
        "action_callback": lambda name: _register,
        # t174 put a startup hook in the app. Chainlit's own `on_app_startup` registers the hook on
        # `config.code` and runs it later, from the server's lifespan
        # (chainlit/callbacks.py:39, chainlit/server.py:93-94), so an import never runs it — and
        # neither does this: registered, never run, as 174's own skin tests do it
        # (skin/tests/test_t118_reopened_chat.py:97).
        "on_app_startup": _register, "sleep": asyncio.sleep,
    }.items():
        setattr(chainlit, name, value)
    widgets.Select = lambda **_: None  # type: ignore[attr-defined]
    socket.sio = types.SimpleNamespace(  # type: ignore[attr-defined]
        handlers={"/": {"connect": chainlit_connect}})
    # Ticket 100's stage door: the app mints Chainlit's own cookie on `/r/<code>` and adds two
    # routes to Chainlit's server. Registered here and never served: what those routes call is
    # `stage_qr` and `room`, which the scenarios drive directly (`scan_the_qr`, `scan`).
    auth = types.ModuleType("chainlit.auth")
    auth.__path__ = []  # type: ignore[attr-defined]
    auth.create_jwt = lambda user: "a-token"  # type: ignore[attr-defined]
    cookie = types.ModuleType("chainlit.auth.cookie")
    cookie.set_auth_cookie = lambda request, response, token: None  # type: ignore[attr-defined]
    config = types.ModuleType("chainlit.config")
    config.config = types.SimpleNamespace(  # type: ignore[attr-defined]
        run=types.SimpleNamespace(root_path=""))
    # On a phone this is Chainlit's own `.files`, which the app sweeps (ticket 175). Here it is a
    # folder under the scenario's tmp root and nothing makes it, so a sweep of it reaches nothing:
    # `nemo.door.sweep` no-ops on a directory Chainlit has not made yet.
    config.FILES_DIRECTORY = root / ".files"  # type: ignore[attr-defined]
    server = types.ModuleType("chainlit.server")
    routes: list[Any] = []
    server.app = types.SimpleNamespace(  # type: ignore[attr-defined]
        router=types.SimpleNamespace(routes=routes),
        add_api_route=lambda path, endpoint, **_: routes.append((path, endpoint)))
    chainlit.__path__ = []  # type: ignore[attr-defined]
    return {"chainlit": chainlit, "chainlit.input_widget": widgets, "chainlit.socket": socket,
            "chainlit.auth": auth, "chainlit.auth.cookie": cookie, "chainlit.config": config,
            "chainlit.server": server}


def _fastapi() -> dict[str, types.ModuleType]:
    """The names the app's two routes are typed and answered with. FastAPI is Chainlit's, not
    nemo's, so it is stood in for exactly as Chainlit is."""
    fastapi = types.ModuleType("fastapi")
    fastapi.__path__ = []  # type: ignore[attr-defined]
    fastapi.Request = fastapi.Response = object  # type: ignore[attr-defined]
    responses = types.ModuleType("fastapi.responses")
    # t409: the stage door sets its room cookie on the redirect; nothing here reads it back.
    responses.HTMLResponse = responses.PlainTextResponse = responses.RedirectResponse = (  # type: ignore[attr-defined]
        lambda *a, **k: types.SimpleNamespace(args=a, kwargs=k, set_cookie=lambda *_, **__: None))
    return {"fastapi": fastapi, "fastapi.responses": responses}


class NoNetwork(AssertionError):
    """A lane call that got past the scripted lane: this suite never dials out."""


def _httpx() -> types.ModuleType:
    """httpx, for the one module that imports it (`PROTOTYPE_lanes`): nothing here can post."""
    httpx = types.ModuleType("httpx")

    def post(url: str, **_: Any) -> Any:
        raise NoNetwork(f"a live call to {url} was made past the scripted lane")

    httpx.post = post  # type: ignore[attr-defined]
    httpx.TimeoutException = type("TimeoutException", (Exception,), {})  # type: ignore[attr-defined]
    httpx.HTTPError = type("HTTPError", (Exception,), {})  # type: ignore[attr-defined]
    return httpx


def stand_ins(root: Path) -> dict[str, types.ModuleType]:
    """Every module the harness fakes, by the name the app imports it under. `fresh_skin`
    installs these, and `tests/gate/test_skin_harness_stand_ins.py` checks the skin's imports
    against them."""
    return {**_chainlit(root), **_fastapi(), "httpx": _httpx()}


def scripted_lane(model: str, *_: Any, **__: Any) -> dict[str, Any]:
    """The model, stubbed: every call is answered with the next `SCRIPTED` reply, else with
    `SCRIPTED_REPLY`, and counted."""
    LANE_CALLS.append(model)
    if SCRIPTED:
        return {"role": "assistant", "_usage": {}, **SCRIPTED.pop(0)}
    return {"role": "assistant", "content": SCRIPTED_REPLY, "_usage": {}}


def tool_call(name: str, **arguments: Any) -> dict[str, Any]:
    """One scripted reply that calls one tool, shaped as the lane returns it."""
    call = {"name": name, "arguments": json.dumps(arguments)}
    return {"content": None,
            "tool_calls": [{"id": f"scripted-{name}", "type": "function", "function": call}]}


def _nemo_modules() -> list[types.ModuleType]:
    return [module for name, module in list(sys.modules.items())
            if module is not None and (name == "nemo" or name.startswith("nemo."))]


def _undone_afterwards(monkeypatch: Any, before: dict[types.ModuleType, dict[str, Any]]) -> None:
    """Every name the load rebound in a nemo module, handed to `monkeypatch` to put back."""
    for module, was in before.items():
        for name, now in list(vars(module).items()):
            if name in was and was[name] is now:
                continue
            if name in was:
                setattr(module, name, was[name])
            else:
                delattr(module, name)
            monkeypatch.setattr(module, name, now, raising=False)


def fresh_skin(monkeypatch: Any, root: Path) -> Any:
    """The phone app over a rooms folder, a seed and a log this caller owns, and nobody else's.

    The seed is named and not made: a caller that wants a room minted puts a seed there, or points
    `app.SEED` at one (`walkable_seed`), and one that does not gets the door that refuses a room
    with no folder.
    """
    global app
    SENT.clear()
    LANE_CALLS.clear()
    SCRIPTED.clear()
    for name, module in stand_ins(root).items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "path", [str(PHONE), *sys.path])
    # Imported before the snapshot below, so the nemo modules they pull in are in the snapshot and
    # only the app's own load is what is undone; and before the environment below is set, which
    # is the app's alone (the skin's scenario module reads `NEMO_SEED` once, at import).
    import PROTOTYPE_core  # noqa: F401
    import PROTOTYPE_lanes as lanes
    import PROTOTYPE_scenarios  # noqa: F401

    monkeypatch.setenv("NEMO_ROOMS", str(root / "rooms"))
    monkeypatch.setenv("NEMO_SEED", str(root / "seed"))
    monkeypatch.setenv("PROTO_LOG", str(root / "proto.log"))

    from nemo import turn_file, walk

    monkeypatch.setattr(lanes, "httpx", sys.modules["httpx"])
    monkeypatch.setattr(lanes, "_litellm", scripted_lane)
    monkeypatch.setattr(lanes, "_codex", lambda *a, **k: scripted_lane("gpt6"))
    monkeypatch.setattr(lanes, "CALLS", turn_file.Calls())
    # `install_patches` adds a row to this table in place, so the load gets a copy of it.
    monkeypatch.setattr(walk, "_RESERVED_AT", dict(walk._RESERVED_AT))
    before = {module: dict(vars(module)) for module in _nemo_modules()}
    spec = importlib.util.spec_from_file_location("phone_app_under_test", APP)
    assert spec is not None and spec.loader is not None
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    _undone_afterwards(monkeypatch, before)
    monkeypatch.setattr(app, "ARCHIVE", root / "archived")
    # The one door a delegate's room comes from (t186 (c)), driven by `scan_the_qr`: the code it
    # draws is the scan's own, and nothing else of the door is stood in for.
    monkeypatch.setattr(app.stage_door, "fresh_code",
                        _the_scans_own_code(app.stage_door.fresh_code))
    (root / "rooms").mkdir()
    return app


def walkable_seed() -> Path:
    """A seed every activity of which the phone can walk (`core.refuse_short` passes on it).

    The phone opens a chat only on a room whose every activity has a prepared draft, and the drafts
    are the skin's own (`skin/drafts/`), made for the seed the skin's suite walks. So a scenario
    that opens the chat mints its room from that same seed, as the skin's suite does.
    """
    import PROTOTYPE_scenarios as scenarios

    return Path(scenarios.SEED)


def scan(link: str) -> Any:
    """Present a scanned link the way nginx does, and get back what the phone makes of it."""
    return app.room({"X-Room-Link": link})


#: The draw the stage door uses for the scan running now, per thread: fifty scans at one moment are
#: fifty threads through one door, and each brings its own code.
_DRAWN = threading.local()


def _the_scans_own_code(fresh_code: Any) -> Any:
    """`stage_door.fresh_code` drawing the code this scan asked for in place of a random one.

    `fresh_code`'s own `draw` argument is the seam kept for exactly this, and it is all that is
    stood in for: the prefixes the door refuses and the codes it will not hand out twice are still
    the door's own work, judged on what it drew. Its `taken` is the door's own too, and a scan waits
    for the others once that has answered (ticket 231), so the mint is all that is left to race.
    """
    def drawing(taken: Any, draw: Any = None) -> str:
        def checked(code: str) -> bool:
            held = bool(taken(code))
            _DRAWN.checked()
            return held
        return fresh_code(checked, draw=_DRAWN.draw)
    return drawing


def scan_the_qr(code: str, drawing: Any = None) -> str:
    """One scan of the stage QR: the app's `/new` door, and the link it sends the phone on to.

    Ticket 186 (c): a room link never makes a room and only a door does, so this is where a
    delegate's room comes from. `/new` draws a code, mints its room from the seed and answers with
    a redirect to `/r/<code>`; what comes back here is that link, which the caller presents as the
    phone does. A mint the door refuses is printed by the door and nothing is made.

    `drawing` is called once the door has drawn the code and asked whether a room holds it, which
    is where a scan waits for the others when a scenario scans at one moment: every scan is then
    past that question before any of them has a room, so what races is the mint, which is what "at
    the same moment" is about (`walk.mint_room`). Waiting at the draw instead let one scan mint
    before the other asked, and the door rightly drew again (ticket 231).
    """
    drawn: list[str] = []

    def draw() -> str:
        assert not drawn, f"the door would not draw {code!r} twice: a room of that name is there"
        drawn.append(code)
        return code

    _DRAWN.draw = draw
    _DRAWN.checked = drawing or (lambda: None)
    return str(asyncio.run(app.stage_qr(None)).args[0])


def arrive(room: str) -> None:
    """What Chainlit has done by the time `on_chat_start` runs: an identity in the tab."""
    app.cl.user_session.set("user", User(room))


def open_the_room(room: str) -> None:
    """A manager arriving: the identity Chainlit hands over, and then the greeting."""
    arrive(room)
    asyncio.run(app.start())


def type_into_the_composer(words: str) -> Any:
    """What a manager typing into the box does: the app's own `on_message`, and what it answers."""
    asyncio.run(app.typed(Message(words, type="user_message")))
    return SENT[-1]


def session() -> Any:
    """The `PROTOTYPE_core.Session` the tab holds: the room folder a turn writes into."""
    return app.cl.user_session.get("s")


def room_names(rooms: Path) -> list[str]:
    """Which rooms are on disk, by code — what every "no room was created" assertion reads."""
    return sorted(path.name for path in rooms.iterdir())


def seed_room(rooms: Path, code: str, *departments: str) -> Path:
    """A room folder holding transcripts, made by hand rather than minted."""
    folder = rooms / code
    (folder / "07_Interviews").mkdir(parents=True)
    for department in departments:
        (folder / "07_Interviews" / f"{department}.md").write_text(
            f"---\ndepartment: {department}\n---\n\nan interview\n", encoding="utf-8")
    return folder


def phone_sources() -> list[Path]:
    """The phone app's file and every file of `skin/` it imports, however deep: what it runs."""
    seen: set[Path] = set()
    todo = [APP]
    while todo:
        path = todo.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                todo += [PHONE / f"{alias.name}.py" for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                todo.append(PHONE / f"{node.module}.py")
    return sorted(seen)

