"""PROTOTYPE, throwaway (2026-09-17, owner's rulings of the same day). Not nemo's product code.

Chainlit skin over PROTOTYPE_core: native short chat with taps + typing, cards only for the record
and the certificate, a model switch (GLM-5.3 Flash / DeepSeek V4.1 Flash / GPT-6 reference via
codex). Each model gets its own room (`<room>-<model>`), so walks never collide. Type /reset to
start over (the old room is archived, not deleted).
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import chainlit as cl
import chainlit.server as chainlit_server
from chainlit.auth import create_jwt
from chainlit.auth.cookie import set_auth_cookie
from chainlit.config import FILES_DIRECTORY, config
from chainlit.input_widget import Select
from chainlit.server import app
from chainlit.socket import sio
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

sys.path.insert(0, str(Path(__file__).parent))

import answer_shapes as shapes  # noqa: E402
import chat_build  # noqa: E402
import drafts  # noqa: E402
import led_turn  # noqa: E402
import live_graph  # noqa: E402
import shown as kept  # noqa: E402
import workspace  # noqa: E402

from nemo import turn_file, walk  # noqa: E402
from nemo.ask import RELEASE_MISMATCH, release_note  # noqa: E402
from nemo.door import (  # noqa: E402
    checked_room_folder,
    checked_session_id,
    identity_from_link,
    sweep,
)
from nemo.room_code import Refused, mintable  # noqa: E402
from nemo.room_store import PathRefused  # noqa: E402

import PROTOTYPE_core as core  # noqa: E402
import PROTOTYPE_lanes as lanes  # noqa: E402
import stage_door  # noqa: E402

ROOMS = Path(os.environ["NEMO_ROOMS"])
SEED = Path(os.environ["NEMO_SEED"])
LOG = Path(os.environ.get("PROTO_LOG", "proto.log"))
ARCHIVE = Path(__file__).parent / "archived-rooms"
#: The lane key, and half of every room's folder name (`_session`), so it does not change when the
#: route behind it does: ticket 198 pointed "glm" at the fastest GLM-5.3 Flash route (ADR-0036)
#: rather than adding a key, because a new key would open every existing room empty.
DEFAULT_MODEL = "glm"

core.install_patches()
# t288: the chat in Harbour, light only, from a dressed copy of Chainlit's own frontend
chat_build.install(chainlit_server, config)

# t175: a crash or a restart leaves Chainlit's `.files/<session>` behind; nemo's sweep takes the
# UUID-named ones older than its age, here at start and after each new chat's greeting.
sweep(FILES_DIRECTORY)

# t160: the second layer. Chainlit makes a directory of the client's own `sessionId` and rmtree's it
# when the socket drops, so `../../x` writes into and then deletes x (tests/isolation probe 1). The
# value rides inside the Socket.IO CONNECT payload, where nginx cannot see it; nemo's door refuses
# anything but a UUID here, before Chainlit reads it.
_chainlit_connect = sio.handlers["/"]["connect"]


async def _checked_connect(sid: str, environ: dict[str, Any], auth: dict[str, Any] | None) -> Any:
    try:
        checked_session_id((auth or {}).get("sessionId"))
    except Refused as refusal:
        raise ConnectionRefusedError(str(refusal)) from refusal
    return await _chainlit_connect(sid, environ, auth)  # its own answer, unchanged


sio.handlers["/"]["connect"] = _checked_connect


#: t174: what a manager reads first in his chat when the connector serves another guidance corpus
#: release than the ask lane trusts (the owner, 2026-09-23: "Start, visible warning"). One line; on
#: a
#: match, and when the connector would not say, nothing is shown.
CORPUS_WARNING = ("Guidance answers are unavailable until the guidance corpus is fixed; "
                  "your walk and signing work as usual.")
#: What every room shows before its greeting, filled once by the startup hook below.
SHOWN_AT_START: list[str] = []


#: t174 fix 1: a launch under test names a JSON file standing in for the connector's health page, so
#: no test launch reaches mcp.ai4bcm.org. The phone's launcher unsets it (run-live.sh): the served
#: app always reads the real page.
HEALTH_FIXTURE = "NEMO_GUIDANCE_HEALTH"


# t174: read once at start, from the connector's own health page, and written to the console, so to
# the unit's journal (`docs/facilitator-note.md`). **In a startup hook and never at module scope**:
# `release_note()` is live HTTP, and a module-scope call would reach the connector from every
# import, test collection included (skin/tests/test_t174_corpus_release.py pins that it does not).
@cl.on_app_startup
async def announce_the_corpus_release() -> None:
    fixture = os.environ.get(HEALTH_FIXTURE)
    note = (
        release_note(get=lambda url: json.loads(Path(fixture).read_text()))
        if fixture
        else release_note()
    )
    print(note, flush=True)
    SHOWN_AT_START[:] = [CORPUS_WARNING] * note.startswith(RELEASE_MISMATCH.split("{")[0])


def log(kind: str, data: Any) -> None:
    user = cl.user_session.get("user")
    logged(user.identifier if user else "?", kind, data)


#: t442: a non-turn line stays near this many characters, and stays one JSON object.
LINE_CAP = 6000


def _shortened(value: Any, most: int) -> Any:
    """t442: every string in `value` cut to `most` characters, each cut marked."""
    if isinstance(value, str) and len(value) > most:
        return f"{value[:most]}… [{len(value) - most} characters cut]"
    if isinstance(value, dict):
        return {k: _shortened(v, most) for k, v in value.items()}
    if isinstance(value, list):
        return [_shortened(v, most) for v in value]
    return value


def logged(room: str, kind: str, data: Any) -> None:
    """One line on the log for the room (t292: the live graph page logs outside any chat).

    Ticket 69: a turn line is read back whole (PROTOTYPE_clocks), never cut. t442: any other line
    over LINE_CAP has its strings shortened inside the object, so it is still one JSON object.
    """
    head = {"t": time.strftime("%H:%M:%S"), "room": room}
    line = json.dumps({**head, kind: data}, default=str, ensure_ascii=False)
    if kind != "turn" and len(line) > LINE_CAP:
        plain, most = json.loads(line)[kind], LINE_CAP
        while len(line) > LINE_CAP and most > 1:
            most //= 2
            line = json.dumps({**head, kind: _shortened(plain, most)}, ensure_ascii=False)
        if len(line) > LINE_CAP:  # too many small parts: the whole value as one marked string
            whole = json.dumps(plain, ensure_ascii=False)
            line = json.dumps({**head, kind: _shortened(whole, LINE_CAP // 2)}, ensure_ascii=False)
    with LOG.open("a") as f:
        f.write(line + "\n")


def _session(model: str, reset: bool = False) -> core.Session | None:
    """The room's session, or None when the room is not ready (13_nemo, t66: the readiness check).

    Every activity the room offers must be walkable before the chat opens; if one is not, the log
    gets one line naming it and the operator gets the setup-fault message instead of the chat.
    """
    code = f"{cl.user_session.get('user').identifier}-{model}"
    if reset:
        core.fresh_room(SEED, ROOMS, code, ARCHIVE)
    else:
        walk.mint_room(SEED, ROOMS, code)
    fault = core.refuse_short(ROOMS / code, model, log)
    if fault:
        print(f"setup fault: room {code} not opened, see {LOG}", flush=True)
        cl.user_session.set("s", None)
        cl.user_session.set("fault", fault)
        return None
    s = core.Session(ROOMS / code, model, log)
    s.root = ROOT  # t276: a page tap's link
    # t277 (ADR-0045 kind 3): 257's mailbox tap, drawn as a next step; the core never names drafts
    s.mailbox_offered = lambda: mailbox_offered(s.folder, s.walking)
    s.place_drafts = functools.partial(mailbox_pressed, cl.user_session.get("user").identifier,
                                       s.folder)
    s.place_invite = functools.partial(invite_pressed, s.folder)  # t373 (ADR-0049)
    # t406, bound lazily: the name is read at the tap, so a test running `_session` from its
    # own source slice needs no `shown_pressed` (M11 sweep: 17 NameErrors)
    s.place_shown = lambda activity: shown_pressed(s.folder, activity)
    # t539/t540: a model-led turn's letter, placed by his tap, and its invitation, moved by it
    s.place_letter = lambda tap: letter_pressed(led_turn.place, s.folder, tap)
    s.place_move = lambda tap: led_pressed(led_turn.move, s.folder, tap)
    cl.user_session.set("s", s)
    return s


async def _refused() -> None:
    await cl.Message(content=cl.user_session.get("fault"), author="prototype").send()


async def _turn(
    text: str, how: str = "typed", pick: bool = False, action: str | None = None,
    wait: dict[str, Any] | None = None,
) -> None:
    # t310: one turn at a time in a room. A tap, or a second question, sent while a turn runs
    # waits for it and then runs: two at once shared the session's `turn_id` and `last_turn`, so
    # both turn-file lines carried one id and the calls crossed. Nothing is refused
    # `seconds` stays what the person waited (26_nemo_check): from the send, the wait included
    s: core.Session | None = cl.user_session.get("s")
    sent = time.time()
    wait = {} if wait is None else wait
    async with TURNING.setdefault(s.folder if s else Path(), asyncio.Lock()):
        try:
            await _one_turn(text, how, pick, action, waited=time.time() - sent, wait=wait)
        except BaseException:  # t628: a raise, or his stop, leaves no wait line behind it
            wait["over"] = True
            if "bubble" in wait:
                await wait["bubble"].remove()
            raise


#: t310: the lock each room's turns take in turn, by room folder (two tabs on one room share it)
TURNING: dict[Path, asyncio.Lock] = {}


async def _turn_or_down(
    text: str, how: str = "typed", pick: bool = False, action: str | None = None,
    offer: bool = False,
) -> None:
    """727: his typed line or tap. Chainlit only logs a raise, so he reads `DOWN` and the log keeps
    the traceback (its end, the raising frame: `logged` cuts a long line from the end); anything
    already said stands, with no sentence saying it never came. His stop is no `Exception` and goes
    on up. `_turn` raises on, as t628 has it. `offer`: t257's mailbox offer, on a turn that did not
    raise."""
    wait: dict[str, Any] = {}
    try:
        s = cl.user_session.get("s")
        before = await cl.make_async(core.follow_up)(s.folder) if offer and s else []
        await _turn(text, how, pick, action, wait)
        if offer:
            await _mailbox_offer(before)
    except Exception as e:  # 727
        said = {"raise": f"{type(e).__name__}: {e}"[:500],
                "traceback": traceback.format_exc()[-4000:]}
        try:
            if "said" not in wait:  # before the log's await: a turn queued behind this one waits
                await cl.Message(content=lanes.DOWN).send()
        finally:
            try:
                await cl.make_async(log)("turn_raise", said)
            except Exception:  # a log it cannot write (a full disk): the journal has it
                traceback.print_exc()


async def _wait_line(step: Any, wait: dict[str, Any], line: str) -> None:
    """t628: `line` in the reply bubble, the turn still running; the answer takes its id
    (`_one_turn`). A timer already firing as the answer came draws nothing after it."""
    if wait.get("over"):
        return
    bubble = cl.Message(content=line)
    # the answer's level, as every answer: made in this context it is the step's child, and goes
    # with `step.remove()`
    bubble.parent_id = step.parent_id
    wait["bubble"] = bubble
    await bubble.send()


async def _one_turn(text: str, how: str, pick: bool, action: str | None,
                    waited: float = 0.0, wait: dict[str, Any] | None = None) -> None:
    s: core.Session = cl.user_session.get("s")
    if s is None:  # the room did not open: no conversation, only the setup fault
        await _refused()
        return
    # t82 fix 3: a turn that drafts says so before the draft (the owner's "Accept it", 2026-09-21).
    # Core calls this from the place that drafts, inside the turn's thread, so the same message the
    # reply goes out as is sent from there, on the event loop, while the draft is still running.
    s.say_now = lambda line: cl.run_sync(cl.Message(content=line).send())
    down = None
    said: dict[str, Any] = {"said": text}
    # t132: a tap as his phone showed it, read before the turn redraws the taps. His confirmation
    # of a figure is read from this line (`turn_file.his_turns`), never from a model's call
    if how == "tapped" and (shown := s.shown(text)) != text:
        said["shown"] = shown
    calls = s.stats["calls"]
    wait = {} if wait is None else wait
    async with cl.Step(name=f"thinking · {lanes.LABELS[s.model]}", type="run") as step:
        # t537: a model-led turn past its mark says "Checking your files…" (t628: in the bubble)
        s.waiting = lambda line: cl.run_sync(_wait_line(step, wait, line))
        # ticket 69 (3_nemo_check / t70): the turn is logged as typed or tapped
        try:
            reply, options, cards = await cl.make_async(
                functools.partial(s.turn, how=how, pick=pick, action=action)
            )(text)
            said.update(reply=reply, options=options, cards=cards)
        except lanes.LaneDown as e:  # t33: chainlit only logs a raise from a typed line or a tap
            down = e
        finally:  # t109: every phone turn, a failed one too, on the room's turn file (off the loop)
            line = {**s.last_turn, **said}
            if waited and isinstance(line.get("seconds"), (int, float)):  # t310: it queued
                line["seconds"] = round(line["seconds"] + waited, 1)
            await cl.make_async(core.record_turn)(s.folder, line)
        step.output = f"{s.stats['calls']} model calls so far"
    wait["over"] = True
    # t628: what is said next goes under the wait line's id. Chainlit's client draws a new message
    # of a known id over that message, and one it never got (a phone asleep at the mark) as new; an
    # update for an id it lacks it drops, so an answer is never sent as an update
    taken = {"id": wait["bubble"].id} if "bubble" in wait else {}
    if down is not None:  # sent outside the step, or it is folded inside it; his taps stay
        wait.pop("bubble", None)  # said from here on, so his stop never takes the sentence away
        wait["said"] = True  # 727
        await cl.Message(content=down.said, **taken).send()
        return
    # t255: the impact chart beside its grid card, drawn by code from what the card carries
    charts = [s.impact_charts(c) for c in cards]
    phones = [s.phone_charts(c) for c in cards]  # t403 r6: each chart's phone split beside it
    if any(charts) and s.stats["calls"] == calls:  # t377 N7: code drew it; no model thought
        await step.remove()
    reply, cards = s.drawn_turn(reply, cards)  # t107: every term named at its first use
    # t478: every answer says its stage; the opener is nemo's greeting, no answer
    if how != "opener" and reply and (stage := s.stage_line(reply, cards)):
        reply = f"{stage}\n\n{reply}"
    reply = _in_bold(reply, s.last_turn)  # 757: only here and in the replay, nothing reads it after
    # t73 fix 1: the previous message's taps go (Chainlit keeps them until removed); the core also
    # takes a tap off any earlier message as plain text, so a stale one dispatches nothing.
    # t115 (117's amendment): on a show tap's turn the decision taps stay on the live card's
    # message, still current, and only the show taps move under the table
    stay = [
        a
        for a in cl.user_session.get("taps") or []
        if s.taps_stay and a.payload["text"] not in core.SHOW_TAPS
    ]
    for old in cl.user_session.get("taps") or []:
        if old not in stay:
            await old.remove()
    actions = [
        # ticket 68 fix 1: the server's taps say so. t73: every tap is nemo's, and its payload
        # carries the action it stands for, which the tap dispatches directly
        # t96: he reads the tap in plain words (`Session.shown`); the payload carries the tap as
        # nemo drew it, and its action id, so what it calls and what the record stores are unchanged
        cl.Action(
            name="tap",
            label=s.shown(o),
            payload={"text": o, "shown": s.shown(o), "pick": s.last_pick, "action": aid},
        )
        for o, aid in zip(options, s.last_actions, strict=False)
        if not s.taps_stay or o in core.SHOW_TAPS
    ]
    cl.user_session.set("taps", stay + actions)
    # t115: the answer first, then what nemo drew, with the taps under the last message; a show
    # tap's turn has no answer, only its table. t117: on a turn that drew the live card, the taps
    # go on the live card's own message, whatever follows it ("the taps sit on the card they act
    # on")
    head = int(bool(reply or not cards))
    # why: `said` named the turn dict above; renaming it is a code edit
    said = [{"content": reply}] * head + [  # type: ignore[assignment]
        {"content": c, "author": "nemo · card"}
        | ({"elements": _card_images(chart, phone)} if chart else {})
        for c, chart, phone in zip(cards, charts, phones, strict=True)]
    at = len(said) - 1 if s.live_at is None else head + s.live_at
    # t499 r4: Chainlit sends a message's images all at once (asyncio.gather), so the screen shows
    # them in the order they arrive; a card with 2+ charts goes out without them, then each image
    # goes on it in list order, each sent before the next. A one-chart card goes as it always did
    apart = [False] * head + [len(chart) > 1 for chart in charts]
    said[0] |= taken  # type: ignore[index]
    for k, (m, one_by_one) in enumerate(zip(said, apart, strict=True)):
        # why: each `m` is a dict of str, as built on the line above
        later = m.pop("elements") if one_by_one else []  # type: ignore[attr-defined]
        wait.pop("bubble", None)  # t628: said from here on, so a later raise leaves the answer
        wait["said"] = True  # 727: Chainlit emits first; only the taps and images raise after that
        sent = await cl.Message(**m, actions=actions if k == at else []).send()  # type: ignore[arg-type]
        for image in later:
            await image.send(for_id=sent.id)


def _in_bold(reply: str, record: dict[str, Any]) -> str:
    """757: the answer as it goes to his screen, in his pick's bold; its record stays plain."""
    import led_turn  # the tests run this part of the app's source over a stand-in `cl`

    return led_turn.in_bold(reply) if led_turn.bolds(record) else reply


def _card_images(charts: list[str], phones: list[str]) -> list[Any]:
    """t255: a card's charts as the images on its message, each SVG inline, its phone split after
    it (t403 r6); t533: a replayed card's the same way, so there is one path to the screen."""
    return [cl.Image(name=name, content=svg.encode(), mime="image/svg+xml", display="inline",
                     size="large") for name, svg in core.impact_chart.images(charts, phones)]


@cl.header_auth_callback
def room(headers: Any) -> cl.User | None:
    # t186 (c): the login opens a room that exists and never makes one, the seed present or not; a
    # room comes only from a door: the stage QR's `/new` below, or skin/new_room.py for his and the
    # check sessions'. An absent mount keeps its own words (ticket 50), so the operator can tell it.
    try:
        code = identity_from_link(headers.get("X-Room-Link") or "")
        if not ROOMS.is_dir():
            raise Refused(walk.ABSENT_MOUNT.format(rooms=ROOMS, room=code))
        checked_room_folder(ROOMS, code)
    except Refused as refusal:
        print(refusal.operator, flush=True)
        return None
    return cl.User(identifier=code, metadata={"room": code})


@cl.on_chat_start
async def start() -> None:
    model = cl.user_session.get("chat_settings", {}).get("model") or DEFAULT_MODEL
    await cl.ChatSettings([Select(id="model", label="Model",
                                  items={v: k for k, v in lanes.LABELS.items()},
                                  initial_value=model)]).send()
    s = _session(model)
    if s is None:
        await _refused()
        return
    # t118: the room's recent conversation, drawn again as he read it: a tapped
    # answer in its plain words (t96), the reply and then its cards named (t107, 115's order), no
    # taps on any of it, and nothing written (the turn file is only read). t533 (511): each answer
    # on the stage label it had live, each card with the chart the room kept for it (`shown`), its
    # images sent as `_one_turn` sends them (t499 r4: 2+ charts one by one, in order)
    kept = turn_file.past(s.folder)
    # 757: bold as he read it live; the turn file says which turns took it
    import led_turn  # as `_in_bold`

    took_bold = await cl.make_async(led_turn.bold_turns)(s.folder) if kept else set()
    for past in kept:
        await cl.Message(content=core.TAP_WORDS.get(past.said, past.said) if past.how == "tapped"
                         else past.said, type="user_message").send()
        if past.reply is not None:
            reply, cards, charts = s.replayed(past)
            reply = led_turn.in_bold(reply) if past.turn_id in took_bold else reply
            if reply or not cards:  # t745: as `_one_turn`, no empty bubble over a card
                await cl.Message(content=reply).send()
            for c, (wide, phone) in zip(cards, charts, strict=True):
                images = _card_images(wide, phone)
                one_by_one = len(wide) > 1
                sent = await cl.Message(content=c, author="nemo · card",
                                        **({"elements": images} if images and not one_by_one
                                           else {})).send()
                for image in images if one_by_one else []:
                    await image.send(for_id=sent.id)
    for line in SHOWN_AT_START:  # t174: on every open, and never on the turn file
        await cl.Message(content=line).send()
    # t745: a room that holds an answer stands as he left it: no greeting, no opener row
    if not any(past.reply is not None for past in kept):
        await _turn("(The manager has just opened the room. Greet them.)", how="opener")
    await cl.make_async(sweep)(FILES_DIRECTORY)  # t175: on every open, off the loop


@cl.on_settings_update
async def switched(settings: dict[str, Any]) -> None:
    model = settings.get("model") or DEFAULT_MODEL
    if _session(model) is None:
        await _refused()
        return
    await cl.Message(content=f"Switched to **{lanes.LABELS[model]}** (its own room).",
                     author="prototype").send()
    await _turn("(The manager has just opened the room. Greet them. If a BIA is already under way, "
                "say where it stands.)", how="opener")


@cl.action_callback("tap")
async def tapped(action: cl.Action) -> None:
    text = str(action.payload["text"])
    await cl.Message(content=str(action.payload.get("shown") or text), type="user_message").send()
    await _turn_or_down(text, how="tapped", pick=bool(action.payload.get("pick")),
                        action=action.payload.get("action"))


@cl.on_message
async def typed(message: cl.Message) -> None:
    if message.content.strip() == "/reset":
        s: core.Session | None = cl.user_session.get("s")
        if _session(s.model if s else DEFAULT_MODEL, reset=True) is None:
            await _refused()
            return
        await cl.Message(content="Fresh room minted from the seed (the old one is archived).",
                         author="prototype").send()
        await _turn("(The manager has just opened the room. Greet them.)", how="opener")
        return
    await _turn_or_down(message.content, offer=True)  # t257: a referral changed the list


# t257 (ADR-0043): the follow-up list's drafts, put in the one demo mailbox by his tap and drawn as
# .eml in "Your documents". All of it is `drafts`, reached from here only: the core and the
# workspace sit on the signature's path and never name it (step 43).
MAILBOX_TAP = "Put the drafts in the mailbox"
MAILBOX_LANDED = ("{landed} of {drafted} drafts are in the mailbox {box}. Nothing is sent: each "
                  "waits there as a draft. They download from Your documents too:")
MAILBOX_UNREACHABLE = ("The mailbox is not reachable, so {landed} of {drafted} drafts are in it. "
                       "Download them from Your documents:")
MAILBOX_ALREADY = "These drafts are in the mailbox already."
MAILBOX_OFFER = "The follow-up list has drafts for the resource owners."
#: The room folder each placement was made for, and the rows it placed: one tap, once.
PLACED: dict[Path, list[tuple[str, str, str]]] = {}


def mailbox_offered(folder: Path, walking: bool) -> bool:
    """The tap is offered in free chat while the room's follow-up rows are not yet placed."""
    rows = core.follow_up(folder)
    return not walking and bool(rows) and PLACED.get(folder) != rows \
        and not drafts.follow_up_placed(folder)  # t533: the room keeps it past a restart


async def _mailbox_offer(before: list[tuple[str, str, str]]) -> None:
    """The tap, on a message of its own, where the follow-up list differs from `before` and is
    not placed yet; the tap offered before it goes."""
    s: core.Session | None = cl.user_session.get("s")
    if s is None or drew_mailbox(s) or not await cl.make_async(mailbox_offered)(s.folder,
                                                                                 s.walking):
        return  # t277: an answer that drew the tap as a next step never gets it twice
    if await cl.make_async(core.follow_up)(s.folder) == before:
        return
    if old := cl.user_session.get("mailbox_tap"):
        await old.remove()
    tap = cl.Action(name="mailbox", label=MAILBOX_TAP, payload={"text": MAILBOX_TAP})
    cl.user_session.set("mailbox_tap", tap)
    await cl.Message(content=MAILBOX_OFFER, actions=[tap]).send()


def mailbox_said(code: str, folder: Path) -> str:
    """His tap: each draft appended once, and what he reads; the downloads always listed."""
    rows = core.follow_up(folder)
    if PLACED.get(folder) == rows or drafts.follow_up_placed(folder):  # t533: and the room
        return MAILBOX_ALREADY
    now = datetime.now().astimezone()
    landed, drafted = drafts.put_in_mailbox(folder, now)
    if landed == drafted:
        PLACED[folder] = rows
    said = MAILBOX_LANDED if landed == drafted else MAILBOX_UNREACHABLE
    return "\n".join([said.format(landed=landed, drafted=drafted, box=drafts.MAILBOX_USER),
                      *(f"- [{name}]({ROOT}/w/{code}/eml/{quote(name)})"
                        for name, _ in drafts.follow_up_drafts(folder, now))])


def drew_mailbox(s: core.Session) -> bool:
    """t277: this answer drew the mailbox tap as one of its next steps."""
    return any(tap.get("kind") == "mailbox" for tap in s._last_taps)


def mailbox_pressed(user: str, folder: Path) -> str:
    """t277: the next step's press, as 257's tap below: placed, logged, and what he reads."""
    said = mailbox_said(user, folder)
    log("mailbox", said.partition("\n")[0])  # what he read, never the password
    return said


#: t373 (ADR-0049): what he reads when he taps "Invite to the interview", each line code's
INVITE_LANDED = ("The invitation to {people} is in the Drafts of {box}, with the calendar file and "
                 "the questionnaire attached. Nothing is sent.")
INVITE_UNREACHABLE = "The mailbox is not reachable, so the invitation is not in its Drafts."
INVITE_BLOCKED = "The interview is in nemo's calendar: {when}."
INVITE_NOT_BLOCKED = ("The calendar entry was not placed in nemo's calendar: the calendar is "
                      "not reachable.")
INVITE_ALREADY = "This invitation is in the mailbox and nemo's calendar already."
#: the (room, activity) pairs whose invitation and calendar entry both landed: no second tap adds
INVITED: set[tuple[Path, str]] = set()


def invite_pressed(folder: Path, activity: str) -> str:
    """t373: his tap: the invitation in the mailbox's Drafts and its entry in nemo's calendar,
    once each, and what he reads; logged, never the password."""
    if (folder, activity) in INVITED or drafts.invited(folder, activity):  # t533: and the room
        return INVITE_ALREADY
    landed, blocked = drafts.put_invitation(folder, activity, datetime.now().astimezone())
    if landed and blocked:
        INVITED.add((folder, activity))
    names = [person for person, _, _ in core.invitees(folder, activity)]
    start, end = core.interview_slot(folder, activity) or (None, None)
    when = f"{start:%A}, {start.day} {start:%B} {start.year}, {start:%H:%M}–{end:%H:%M}" \
        if start and end else ""
    said = " ".join([
        INVITE_LANDED.format(people=", ".join(names[:-1]) + " and " * (len(names) > 1)
                             + names[-1], box=drafts.MAILBOX_USER) if landed
        else INVITE_UNREACHABLE,
        INVITE_BLOCKED.format(when=when) if blocked else INVITE_NOT_BLOCKED])
    logged(folder.name, "invite", said)  # the room, as 292 logs outside a chat
    return said


#: t406: what he reads when he taps "Put these in Drafts", each line code's; the subjects follow,
#: one "- " line each, as the mailbox has them
SHOWN_LANDED = "In the Drafts of {box}, unsent:"
SHOWN_UNREACHABLE = "The mailbox is not reachable, so these drafts are not in its Drafts."
SHOWN_ALREADY = "These drafts are in the mailbox's Drafts already: nothing is added."
#: the room and the drafts it placed: a second tap on the same drafts adds nothing
SHOWN_PLACED: set[tuple[Path, tuple[str, ...]]] = set()


def shown_pressed(folder: Path, activity: str) -> str:
    """t406: his tap: every draft A8 showed placed once in the mailbox's Drafts, and what he
    reads: each subject; logged, never the password."""
    placed = (folder, tuple(core.drafts_first(folder, activity)))
    if placed in SHOWN_PLACED or drafts.shown_placed(folder, activity):  # t533: and the room
        return SHOWN_ALREADY
    subjects = drafts.put_shown(folder, activity, datetime.now().astimezone())
    if subjects:
        SHOWN_PLACED.add(placed)
    said = "\n".join([SHOWN_LANDED.format(box=drafts.MAILBOX_USER),
                      *(f"- {subject}" for subject in subjects)]) if subjects \
        else SHOWN_UNREACHABLE
    log("put_drafts", said.partition("\n")[0])
    return said


def led_pressed(press: Any, folder: Path, tap: dict[str, Any]) -> str:
    """t539/t540: his tap on a model-led letter or invitation, pressed now (`led_turn.place`,
    `led_turn.move`), and what he reads; logged, never the password."""
    said = str(press(folder, tap, datetime.now().astimezone()))
    log(str(tap["kind"]), said.partition("\n")[0])
    return said


def letter_pressed(press: Any, folder: Path, tap: dict[str, Any]) -> str:
    """629: his tap on a model-led letter (`led_pressed`, logged as before); once its drafts are
    all placed, what he reads opens with the drafts kind's first line, now "in Drafts"."""
    said = led_pressed(press, folder, tap)
    if not kept.all_placed(folder, led_turn.letter_key(tap["letter"])):
        return said
    return "\n".join([shapes.drafts_first(len(tap["letter"]["to"]), placed=True), said])


@cl.action_callback("mailbox")
async def mailbox(action: cl.Action) -> None:
    await action.remove()
    cl.user_session.set("mailbox_tap", None)
    await cl.Message(content=MAILBOX_TAP, type="user_message").send()
    s: core.Session | None = cl.user_session.get("s")
    if s is None:
        await _refused()
        return
    said = await cl.make_async(mailbox_pressed)(cl.user_session.get("user").identifier, s.folder)
    await cl.Message(content=said).send()


# t100: the stage QR and the room link, as two routes on Chainlit's own server. Ticket 49 found that
# a header nginx sets at `/r/` never reaches Chainlit's `/auth/header`, which the page posts from
# `/login`; so the room comes from the URL itself. `<root>/new` is what the QR encodes: it draws a
# fresh code (`stage_door`), makes that room from the seed (t186: the one door a delegate's room
# comes from) and sends the phone to its link. `<root>/r/<code>` is the credential: the same
# door as the header callback above, judged on the link's raw path (nothing
# percent-decoded, as `nemo.door` decided), then Chainlit's own cookie and on to its page. The
# header callback stays for the owner's tailnet proxy; behind nginx no request carries the header.
ROOT = config.run.root_path
REFUSED = "This link opens no chat. Scan the code on the screen to get your own chat."
#: t764: where Start goes first, and the cookie the tour sets on "Don't show again". The tour and
#: its cookie are its own session's; the door only reads it; the exit comes back by `<root>/new`.
TOUR = "https://ai4bcm.org/nemo/tour/"
TOUR_OFF = "nemo_tour_off"


async def stage_qr(request: Request) -> Response:
    """t409: a phone that holds the door's cookie for a room still there is sent back to it; any
    other phone gets a fresh room, and so does a call with no request (the features harness's
    `stage_qr(None)`). The annotation stays bare: FastAPI injects only a plain `Request`."""
    kept = getattr(request, "cookies", {}).get(stage_door.ROOM_COOKIE) or ""
    return _sent_to(kept if await asyncio.to_thread(_still_there, kept) else await _minted())


def _still_there(code: str) -> bool:
    """t409: a room the door could have made, and whose folder is still in the rooms folder (an
    archived room is not): never his, a check session's, or a name that is no room."""
    if not mintable(code) or code.startswith(stage_door.NOT_A_DELEGATES):
        return False
    try:
        checked_room_folder(ROOMS, code)
    except Refused:
        return False
    return True


async def _minted() -> str:
    # t436: behind the room router, a code this copy holds, so the room stays where it was made
    code = stage_door.fresh_code(
        taken=lambda c: not stage_door.held_here(c) or any(ROOMS.glob(f"{c}*")))
    try:
        await asyncio.to_thread(walk.mint_room, SEED, ROOMS, code)
    except Refused as refusal:  # an absent mount or a refused seed: the link then opens nothing
        print(refusal.operator, flush=True)
    return code


def _sent_to(code: str) -> Response:
    """On to the room's link, with the cookie that brings this phone back to it (t409); scoped to
    the app's root, and as long-lived as the gate's."""
    response = RedirectResponse(f"{ROOT}/r/{code}", status_code=303)
    response.set_cookie(stage_door.ROOM_COOKIE, code, max_age=stage_door.GATE_DAYS * 86400,
                        path=ROOT or "/", httponly=True, samesite="lax")
    return response


async def room_link(request: Request) -> Response:
    link = request.scope.get("raw_path", b"").decode("latin-1") or request.url.path
    if link.rstrip("/").rpartition("/")[-1].startswith(stage_door.NOT_A_DELEGATES):
        print(f"the link {link!r} names a room the export files as not a delegate's", flush=True)
        user = None
    else:
        user = await asyncio.to_thread(room, {"X-Room-Link": link})
    if user is None:
        return PlainTextResponse(REFUSED, status_code=401)
    # t280: the link lands on its room's workspace; the workspace's own chat frame asks `?frame`
    # and lands on the chat. The query only picks the target: the room is judged above, on the raw
    # path, which carries none.
    target = f"{ROOT}/" if "frame" in request.query_params else f"{ROOT}/w/{user.identifier}/"
    response = RedirectResponse(target, status_code=303)
    set_auth_cookie(request, response, create_jwt(user))
    return response


async def landing(request: Request) -> Response:
    """t228: Thursday's testers' page. Start mints a room as the stage QR does; an email that looks
    like one is kept beside the rooms (`stage_door.keep_contact`), never in one, and any other
    goes. t683 (ADR-0063): such an email opens its newest chat if that is still there, never an
    older one; else a new chat, and only a room really made gets the line. The page never reads
    the room cookie, so a typed email wins over it and `_sent_to` moves it.

    t290: with his switch on (nginx's `X-Nemo-Gate: on`) and no gate cookie yet, the page asks the
    password. A wrong one gets the page again, 401: no room, no email kept, no cookie. The right
    one gets the room and the cookie nginx's `auth_request` asks `gate` about.

    t764: Start then goes to the tour, cookies and all, unless the phone holds `TOUR_OFF`. Here and
    never in `_sent_to`: the tour's exit is `stage_qr`, which would send the phone straight back."""
    secret = await asyncio.to_thread(stage_door.gate_secret)
    now = time.time()
    gated = (request.headers.get(stage_door.GATE_HEADER) == "on"
             and not stage_door.cookie_holds(request.cookies.get(stage_door.GATE_COOKIE), secret,
                                             now))
    if request.method == "GET":
        return HTMLResponse(stage_door.landing(ROOT, gated))
    form = parse_qs((await request.body()).decode("utf-8", "replace"))
    if gated and not await asyncio.to_thread(stage_door.right_password,
                                             form.get("password", [""])[0], secret):
        if secret is None:
            print("the gate is on and no gate secret is set: nobody gets in", flush=True)
        return HTMLResponse(stage_door.landing(ROOT, True, wrong=True), status_code=401)
    email = stage_door.kept_email(form.get("email", [""])[0])
    if not email:
        code = await _minted()
    else:
        run = ROOMS.parent
        async with stage_door.contacts_held(run):
            newest = await asyncio.to_thread(stage_door.newest_room, run, email)
            if newest is not None and await asyncio.to_thread(_still_there, newest):
                code = newest
            else:
                code = await _minted()
                if await asyncio.to_thread(_still_there, code):
                    await asyncio.to_thread(stage_door.keep_contact, run, code, email)
    response = _sent_to(code)
    if request.cookies.get(TOUR_OFF) != "1":
        response.headers["location"] = TOUR
    if gated and secret:
        response.set_cookie(stage_door.GATE_COOKIE, stage_door.gate_cookie(secret, now),
                            max_age=stage_door.GATE_DAYS * 86400, path="/", secure=True,
                            httponly=True, samesite="lax")
    return response


async def gate(request: Request) -> Response:
    """t290: what nginx's `auth_request` asks about every request while his switch is on. 204 lets
    the request through; 401 sends the browser to the login page."""
    secret = await asyncio.to_thread(stage_door.gate_secret)
    held = stage_door.cookie_holds(request.cookies.get(stage_door.GATE_COOKIE), secret, time.time())
    return Response(b"", status_code=204 if held else 401)


def _drafted(folder: Path | None) -> dict[str, bytes]:
    """t257: the room's drafts by .eml name, drawn now; none where its runs or records do not read,
    so the page and its files are served as they were (`workspace.reached` reads them the same)."""
    try:
        return dict(drafts.follow_up_drafts(folder, datetime.now().astimezone())) if folder else {}
    except (OSError, ValueError, PathRefused):
        return {}


async def room_workspace(request: Request) -> Response:
    """t247 (ADR-0042): the room's workspace page, its files page and its files, read-only. The
    link is judged on its raw path as `room_link` judges it; `workspace` says why nothing of another
    room can come back, and every refusal is the same empty 404. A briefing's link is the one
    exception (t757): a refused one and a failed print answer the same plain words.

    t257: the room's follow-up drafts, `<root>/w/<code>/eml/<name>`, drawn on request for the room
    the workspace judges the link to name, and served only if the name is, string for string, one
    of that room's drafts; "Your documents" lists them on its own page (t291) and the rail counts
    them, drawn here (the workspace names no draft)."""
    raw = request.scope.get("raw_path", b"").decode("latin-1") or request.url.path
    stamped = request.headers.get("X-Room-Link")
    if urlsplit(raw).path.partition("/briefing/")[1]:  # t405: B7's PDF, printed now
        pdf = await asyncio.to_thread(workspace.briefing, ROOMS, ROOT, raw, DEFAULT_MODEL, stamped)
        name = f"briefing-{urlsplit(raw).path.rpartition('/')[2]}"
        return (Response(pdf, media_type="application/pdf", headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": f'inline; filename="{name}"'})
                if pdf else Response("The print did not run. Please tap the link again.",
                                     status_code=404, media_type="text/plain",
                                     headers={"Cache-Control": "no-store"}))
    said = await asyncio.to_thread(workspace.answer, ROOMS, ROOT, raw, DEFAULT_MODEL, stamped)
    path = urlsplit(raw).path
    code, _, rest = path[len(ROOT) + 3:].partition("/")
    folder = (workspace._folder(ROOMS, code, DEFAULT_MODEL, stamped)
              if path.startswith(f"{ROOT}/w/")
              and (rest in ("", "documents") or rest.startswith("eml/"))
              else None)
    made = await asyncio.to_thread(_drafted, folder)
    if folder and rest.startswith("eml/"):
        name = rest[4:]
        return (Response(made[name], media_type="message/rfc822", headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": f'attachment; filename="{name}"'})
                if name in made else Response(b"", status_code=404, media_type="text/plain"))
    body = said.body
    if made and said.status == 200 and not rest:  # t291 merge: the rail counts them
        body = workspace.counted(body, len(made))
    elif made and said.status == 200:
        head, docs, tail = body.partition('<ul class="docs">')
        body = head + docs + "".join(
            f"<li>{workspace._link(f'{ROOT}/w/{code}/eml/{quote(name)}', name)}</li>"
            for name in made) + tail.replace("<li><small>None yet from nemo</small></li>", "", 1)
    return Response(body, status_code=said.status, media_type=said.kind,
                    headers={"Cache-Control": "no-store"})


async def start_over(request: Request) -> Response:
    """t684 (ADR-0063 point 4): the page's "Start over", what `/reset` does to the room's chat
    (`core.fresh_room`): the old chat into the archive, a fresh one from the seed, the code kept.
    Its own route, not the workspace's: that one stays GET alone (ADR-0042). The room is judged on
    the raw path as the workspace judges it, and only a JSON request is taken, as `graph_ask` takes
    one: no other site's form can send it. Any refusal is the same empty 404. Where the old chat
    cannot be archived the answer is 409, never a fresh chat over a deleted one."""
    raw = request.scope.get("raw_path", b"").decode("latin-1") or request.url.path
    path, prefix = urlsplit(raw).path, f"{ROOT}/start-over/"
    code = path[len(prefix):] if path.startswith(prefix) else ""
    json_sent = request.headers.get("content-type", "").partition(";")[0].strip() == (
        "application/json")
    if not (json_sent and code and "/" not in code
            and await asyncio.to_thread(workspace._folder, ROOMS, code, DEFAULT_MODEL,
                                        request.headers.get("X-Room-Link"))):
        return Response(b"", status_code=404, media_type="text/plain")
    chat = f"{code}-{DEFAULT_MODEL}"
    async with TURNING.setdefault(ROOMS / chat, asyncio.Lock()):  # never under a turn (t310)
        GRAPH_SESSIONS.pop(ROOMS / chat, None)  # the graph page's session was the old chat's
        try:
            await asyncio.to_thread(core.fresh_room, SEED, ROOMS, chat, ARCHIVE)
        except OSError:
            return Response(b"", status_code=409, media_type="text/plain")
    return Response(b"", status_code=204)


async def harbour(request: Request) -> Response:
    """t287: the one Harbour stylesheet every skin page links, its tokens and its fonts, by exact
    name from `skin/harbour/` (`workspace.harbour_file`); any other name is the same empty 404."""
    found = workspace.harbour_file(request.path_params["rest"])
    if found is None:
        return Response(b"", status_code=404, media_type="text/plain")
    kind, body = found
    return Response(body, media_type=kind, headers={"Cache-Control": "no-cache"})


#: t292: each room's session on the live graph page, kept beside the chat's own (`live_graph.ask`)
GRAPH_SESSIONS: live_graph.Sessions = {}


async def graph_ask(request: Request) -> Response:
    """t292: a question from the room's live graph page, one turn of the room's chat, answered as
    JSON with the cards nemo's answer names. The room is judged on the raw path as the workspace
    judges it, and only a JSON body is read: no other site's page can send one here without the
    browser asking first. Every refusal is the same empty 404."""
    raw = request.scope.get("raw_path", b"").decode("latin-1") or request.url.path
    path = urlsplit(raw).path
    code = path[len(ROOT) + 5:] if path.startswith(f"{ROOT}/ask/") else ""
    try:
        body = json.loads(await request.body())
    except ValueError:
        body = None
    json_sent = request.headers.get("content-type", "").partition(";")[0].strip()
    folder = (await asyncio.to_thread(live_graph.room_chat, ROOMS, SEED, code, DEFAULT_MODEL,
                                      request.headers.get("X-Room-Link"))
              if code and json_sent == "application/json" and isinstance(body, dict) else None)
    if folder is None:
        return Response(b"", status_code=404, media_type="text/plain")
    # t409: the page's turn is a turn of the room's chat, so it waits its turn as the chat's own
    # do (t310): run beside one, the line written first carried both turns' model calls. Its
    # `seconds` counts the wait, as the chat's do
    queued = time.time()
    async with TURNING.setdefault(folder, asyncio.Lock()):
        said = await asyncio.to_thread(live_graph.ask, folder, DEFAULT_MODEL, GRAPH_SESSIONS,
                                       functools.partial(logged, code), body, ROOT,
                                       time.time() - queued)
    return Response(json.dumps(said, ensure_ascii=False), media_type="application/json",
                    headers={"Cache-Control": "no-store"})


app.add_api_route(f"{ROOT}/new", stage_qr, methods=["GET"], include_in_schema=False)
app.add_api_route(f"{ROOT}/r/{{rest:path}}", room_link, methods=["GET"], include_in_schema=False)
app.add_api_route(f"{ROOT}/start", landing, methods=["GET", "POST"], include_in_schema=False)
app.add_api_route(f"{ROOT}/w/{{rest:path}}", room_workspace, methods=["GET"],
                  include_in_schema=False)
app.add_api_route(f"{ROOT}/start-over/{{rest:path}}", start_over, methods=["POST"],
                  include_in_schema=False)
app.add_api_route(f"{ROOT}/harbour/{{rest:path}}", harbour, methods=["GET"],
                  include_in_schema=False)
app.add_api_route(f"{ROOT}/ask/{{rest:path}}", graph_ask, methods=["POST"],
                  include_in_schema=False)
app.add_api_route(f"{ROOT}/gate", gate, methods=["GET"], include_in_schema=False)
# Chainlit's catch-all page route was registered first and answers every GET: these go before it.
app.router.routes[:0] = [app.router.routes.pop() for _ in range(8)]
