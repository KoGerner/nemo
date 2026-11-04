"""Ticket 100: the stage QR's minting door. One QR on the screen, one fresh room per scan.

The owner, 2026-09-26T19:43:57Z: *"Stage QR, one room per scan"*. The QR carries this door, never a
room: every scan draws a code nobody holds, makes that room from the seed, and is sent on to its
link, which is the credential (ADR-0003). Since ticket 186 (c) the link only opens a room and never
makes one: this door and `skin/new_room.py` are the only places a room comes from.

**Why the door refuses two prefixes, and why here.** The nightly export files a live room by its
name (`~/work/nemo-langfuse/export.py` `room_kind`): `konstantin*` is the owner's, `check*` a check
session's practice room, anything else a delegate's holdout. A delegate's room called `check…`
would put a human walk into practice. `nemo.room_code.mintable` is not the place: the owner's and
the check sessions' rooms are made by `skin/new_room.py` through the same `walk.mint_room`.
"""
from __future__ import annotations

import asyncio
import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import string
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path

import copies

#: The prefixes `room_kind` files as not a delegate's: the owner's, then a check session's.
NOT_A_DELEGATES = ("konstantin", "check")

#: Where the audience's app is served under nemo.ai4bcm.org, whose root is the read-only site.
ROOT_PATH = "/chat"

#: The string the stage QR encodes, in full (ticket 49's box).
QR_URL = f"https://nemo.ai4bcm.org{ROOT_PATH}/new"

#: Ticket 228: the link Thursday's testers are sent (the QR he sends encodes it). nginx sends it
#: on to the landing page, `<root>/start`, which since ticket 290 is the password itself.
TESTERS_URL = "https://nemo.ai4bcm.org/"

#: Ticket 409, the owner 2026-10-10T16:28:02Z: *"Same phone keeps its room"*. The door's cookie,
#: holding the room code the phone was sent to and nothing else: the code is already in the room
#: link that phone holds, so the cookie shows it nowhere new. HttpOnly, so no page script reads it.
ROOM_COOKIE = "nemo_room"

#: Twelve characters over 36 is 62 bits: a room link nobody guesses, and short enough to read aloud.
_ALPHABET = string.ascii_lowercase + string.digits
_LENGTH = 12


def _draw() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))


def fresh_code(taken: Callable[[str], bool], draw: Callable[[], str] = _draw) -> str:
    """A room code no room holds yet, and never one the export files as his or a check session's."""
    while True:
        code = draw()
        if not code.startswith(NOT_A_DELEGATES) and not taken(code):
            return code


# ── ticket 436 (ADR-0052): several copies of the app, each room on exactly one ─────────────────
# A room's turn lock, its cache and its "already placed" guards live in one copy's memory, so the
# room router (`skin/room_router.py`) sends every request for a room to the copy this names. It is
# a function of the code alone, the same in every process and after any restart, so no table can be
# lost or disagree.

#: `<k>/<n>`: this process is copy k of n behind the router. Unset for one copy (today's units).
COPY_ENV = "NEMO_COPY"
#: t437: which copy holds a room lives with the copies (skin/copies.py); the name stays here
copy_of = copies.copy_of



def held_here(code: str) -> bool:
    """Whether this copy holds the room: the stage door mints only codes it holds, so a room is
    made where it then lives. Always, for a copy started alone."""
    k, _, n = os.environ.get(COPY_ENV, "").partition("/")
    return not n or copy_of(code, int(n)) == int(k)


# ── ticket 228: Thursday's testers ────────────────────────────────────────────────────────
# The owner, 2026-09-29: *"a landing page ... where people can put their email (but dont have
# to)"*, and for the email *"Follow-up only"*: kept on the box beside the rooms, never in one. A
# room's files are what the chat reads (ADR-0022) and `rooms/*/.turns/` is all the Langfuse export
# reads, so an email outside `rooms/` reaches neither the AI nor Langfuse. t683 (ADR-0063): the
# email now also opens its newest chat at this page's Start, so this file grants that way in.

#: Beside `rooms/`, never under it. 7_Langfuse's guard in ~/work/nemo-langfuse (0dc0d3e) names it.
CONTACTS = "contacts.jsonl"

#: The page at `<root>/start`, phone-first and plain. The disclosure is ADR-0002's, for testers.
#: t321: what a tester reads before typing anything, on this page and under the chat's composer
#: (`chat_build.install` puts it in place of Chainlit's "LLMs can make mistakes").
#: t634 (C11, 2026-10-30): the Privacy link beside it says who reads the chats (ADR-0002's note of
#: 2026-10-30). t682 (his answer of 2026-11-01, "change it back"): the words of his C11 original.
NOT_PRIVATE = "Don't type anything confidential. nemo learns from your answers."

#: t287: its colours are Harbour's, from the one stylesheet the skin serves; light only (ADR-0042's
#: note of 2026-10-03). t290 redrew it as direction A (`nemo-design-directions.html`): the heading,
#: then a white card; on a laptop the heading left and the card right. The closing line is a
#: promise to testers and stays, in small type (spec §3).
#: t484, his R18 *"Change the deck/page wording"* and his answer "B: send + copy": the closing
#: lines also say plainly that nemo does not send the work, so copy it before 11 November.
LANDING = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Try nemo</title>
<link rel="stylesheet" href="{root}/harbour/harbour.css">
<style>
* {{ box-sizing: border-box; }}
html {{ background: var(--color-harbour-grey); color: var(--color-navy);
        -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; font: 400 1rem/1.6 var(--font-body); }}
.top {{ display: flex; align-items: center; gap: .6rem; padding: 1rem 1.25rem;
        border-bottom: 1px solid var(--color-hairline); }}
.wm {{ font: 700 1.125rem/1 var(--font-display); letter-spacing: -.03em; }}
.wm b {{ color: var(--color-amber-wordmark); }}
.prod {{ font: 500 1.125rem/1 var(--font-display); letter-spacing: -.02em; }}
main {{ display: flex; flex-direction: column; gap: 1.5rem; max-width: 30rem; margin: 0 auto;
        padding: 2rem 1.25rem 2.5rem; }}
.eb {{ font: 500 .75rem/1.2 var(--font-mono); letter-spacing: .12em; text-transform: uppercase;
       color: var(--color-muted); margin: 0 0 .75rem; }}
h1 {{ font: 700 2.5rem/1 var(--font-display); letter-spacing: -.035em; margin: 0 0 1rem; }}
mark {{ background: var(--highlight-marker-image) no-repeat var(--highlight-marker-position) /
                    var(--highlight-marker-size);
        color: inherit; padding: 0 .04em; }}
.lead {{ font-size: 1.125rem; margin: 0; }}
.card {{ display: flex; flex-direction: column; gap: 1rem; margin: 0; padding: 1.25rem;
         background: var(--color-white); border: 1px solid var(--color-hairline);
         border-radius: 14px; }}
label {{ display: block; font: 500 .75rem/1.4 var(--font-mono); letter-spacing: .12em;
         text-transform: uppercase; color: var(--color-muted); }}
label small {{ display: block; font: 400 .875rem/1.4 var(--font-body); letter-spacing: 0;
               text-transform: none; margin-top: 2px; }}
input {{ display: block; width: 100%; margin-top: .5rem; font: 1rem var(--font-body);
         color: var(--color-navy); background: var(--color-white);
         border: 1px solid var(--color-hairline); border-radius: 6px; padding: 11px 14px; }}
.go {{ font: 500 1.125rem var(--font-body); color: var(--color-navy);
       background: var(--color-amber); border: 0; border-radius: 100px; padding: 15px 28px;
       align-self: flex-start; cursor: pointer; }}
.go:hover {{ background: var(--color-amber-hover); }}
.wrong {{ margin: 0; padding: .6rem .8rem; color: var(--color-rust);
          background: var(--color-peach); border-left: 1.5px solid var(--color-rust); }}
.note, .closing {{ font-size: .875rem; color: var(--color-muted); margin: 1rem 0 0; }}
.note a {{ color: inherit; text-underline-offset: .2em; }}
input:focus-visible, button:focus-visible, a:focus-visible {{ outline: 3px solid var(--color-amber);
                                                                outline-offset: 2px; }}
@media (min-width: 52rem) {{
main {{ flex-direction: row; align-items: center; gap: 5rem; max-width: 72rem;
        padding: 5rem 3rem; }}
.say {{ flex: 1.2; }}
.side {{ flex: 1; }}
h1 {{ font-size: 4rem; line-height: .95; letter-spacing: -.05em; }}
.card {{ padding: 1.75rem; }}
}}
</style></head>
<body>
<header class="top"><span class="wm">AI4<b>BCM</b></span><span class="prod">nemo</span></header>
<main>
<div class="say">
<p class="eb">AI4BCM · nemo</p>
<h1>Try <mark>nemo</mark>.</h1>
<p class="lead">Walk a business impact analysis with nemo, on a sample company.</p>
</div>
<div class="side">
<form class="card" method="post" action="{root}/start">
{wrong}{password}<label for="email">Email
<small>Optional. Type the same email next time to come back to your chat.</small>
<input id="email" name="email" type="email" autocomplete="email" maxlength="254"></label>
<button class="go" type="submit">Start</button>
</form>
<p class="note">{not_private}
<a href="https://ai4bcm.org/privacy/#stage-demo">Privacy</a></p>
<p class="closing"><small>nemo does not send you your work. Copy anything you want to keep
before 11 November.</small>
<small>Your chat and your email are closed on 11 November and deleted within
ninety days.</small></p>
</div>
</main>
</body></html>
"""

#: t290: the card's first field while his switch is on and the browser holds no gate cookie.
PASSWORD_FIELD = """<label for="password">Password
<input id="password" name="password" type="password" autocomplete="current-password" required>
</label>
"""

#: t290: what a wrong password gets, above the field, and nothing else: no room and no cookie.
WRONG = '<p class="wrong" role="alert">That password is not right.</p>\n'


def landing(root: str, ask_password: bool, wrong: bool = False) -> str:
    """The page, with the password field only while nginx's gate asks for it (t290)."""
    return LANDING.format(root=root, password=PASSWORD_FIELD if ask_password else "",
                          wrong=WRONG if wrong else "", not_private=NOT_PRIVATE)


# ── ticket 290: the gate in place of nginx's password pop-up ─────────────────────────────────
# His switch (`nemo-site-password on`) puts `auth_request` in front of the whole host: nginx asks
# `<root>/gate` about each request and sends a 401 to this page. The page is the only place the
# cookie comes from, and only on the right password. The cookie only lets a browser past nginx; a
# room still opens by its link alone (ADR-0003). One secret, on one side: the skin both sets and
# checks the cookie, so nginx holds nothing to keep in step.

#: nginx's word for the switch: "on" from the "on" snippet, "off" from the other. A browser cannot
#: send its own, because the vhost sets it on every request to the skin.
GATE_HEADER = "X-Nemo-Gate"
GATE_COOKIE = "nemo_gate"
#: Long enough to run past 11 November from a first visit in early October.
GATE_DAYS = 45
#: One line his steps doc writes, `scrypt:<n>:<r>:<p>:<salt hex>:<hash hex>`, brain's alone (0600).
#: Never the password itself. `NEMO_GATE_SECRET` names another file; the tests' is in tmp_path.
GATE_SECRET = Path.home() / ".config" / "nemo" / "gate.secret"
#: scrypt's cost: 16 MiB and some tens of milliseconds a try, on the standard library alone.
_SCRYPT = (16384, 8, 1)


def secret_line(password: str, salt: bytes | None = None) -> str:
    """The line to keep for a password, salted; the steps doc's own Python writes the same."""
    salt = salt or os.urandom(16)
    n, r, p = _SCRYPT
    made = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt:{n}:{r}:{p}:{salt.hex()}:{made.hex()}"


def gate_secret() -> str | None:
    """The secret's line, read on every ask so a new password needs no restart; None if unset."""
    try:
        line = Path(os.environ.get("NEMO_GATE_SECRET", GATE_SECRET)).read_text().strip()
    except OSError:
        return None
    return line or None


def right_password(said: str, line: str | None) -> bool:
    """Whether `said` is the password `line` was made from. A line it cannot read lets nobody in."""
    try:
        kind, n, r, p, salt, made = (line or "").split(":")
        if kind != "scrypt" or not said:
            return False
        tried = hashlib.scrypt(said.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r),
                               p=int(p), dklen=len(bytes.fromhex(made)))
    except ValueError:
        return False
    return hmac.compare_digest(tried, bytes.fromhex(made))


def _mac(line: str, lapse: str) -> str:
    key = hashlib.sha256(b"nemo gate cookie\n" + line.encode()).digest()
    return hmac.new(key, lapse.encode(), "sha256").hexdigest()


def gate_cookie(line: str, now: float) -> str:
    """`<lapse>.<mac>`: when it lapses, signed with a key drawn from the secret, so a new password
    ends every cookie the old one gave."""
    lapse = str(int(now) + GATE_DAYS * 86400)
    return f"{lapse}.{_mac(line, lapse)}"


def cookie_holds(value: str | None, line: str | None, now: float) -> bool:
    """Whether the cookie is one `gate_cookie` gave under this secret and has not lapsed."""
    lapse, _, mac = (value or "").partition(".")
    if not line or not (lapse.isascii() and lapse.isdigit()) or int(lapse) <= now:
        return False
    return hmac.compare_digest(mac.encode(), _mac(line, lapse).encode())


def kept_email(said: str) -> str | None:
    """The email to keep, or None: empty, or not shaped like an address (one `@`, 254 at most)."""
    email = said.strip()
    local, at, domain = email.partition("@")
    shaped = at and local and domain and "@" not in domain and not any(c.isspace() for c in email)
    return email if shaped and len(email) <= 254 else None


def keep_contact(run: Path, room: str, email: str) -> None:
    """One line per room in `<run>/contacts.jsonl`, readable by brain alone. The order matters
    (t683): an email's last line is the chat it opens."""
    line = json.dumps({"room": room, "email": email, "at": datetime.now(UTC).isoformat()})
    fd = os.open(run / CONTACTS, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(line + "\n")


def newest_room(run: Path, email: str) -> str | None:
    """t683 (ADR-0063): the room of this email's last line in the contacts, or None. The whole
    trimmed email decides, case-blind, never a part of it; any other line is skipped."""
    wanted, newest = email.strip().lower(), None
    try:
        text = (run / CONTACTS).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or not isinstance(row.get("room"), str):
            continue
        said = row.get("email")
        if isinstance(said, str) and said.strip().lower() == wanted:
            newest = row["room"]
    return newest


@contextlib.asynccontextmanager
async def contacts_held(run: Path) -> AsyncIterator[None]:
    """t683: one Start's look and mint at a time across the copies, so a double tap makes one chat.
    The kernel drops the lock with its holder; waiting takes no thread, which the mint needs."""
    fd = os.open(run / CONTACTS, os.O_RDONLY | os.O_CREAT, 0o600)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                await asyncio.sleep(0.02)
        yield
    finally:
        os.close(fd)
