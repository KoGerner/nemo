"""Ticket 257 (ADR-0043): the follow-up list's drafts, placed in the one demo mailbox and drawn as
.eml. The only mail code in the repo, reached only from `PROTOTYPE_conversation_app.py`.

One draft per (recipient, activity), holding only that activity's rows of the follow-up list
(`PROTOTYPE_core.follow_up`), drawn by code from the room's runs and records: nothing the model
wrote, never the room code, its link or the model key. The To address is fictional, its slug taken
from the stored `to` by ADR-0043's note of 2026-10-02; ticket 315 (its note of 2026-10-05) shows the
register's named holder, looked up by that slug, and "owner not yet named" where the register names
no person. Ticket 418 r2 (ADR-0051 decision 5, ADR-0043's note of 2026-10-11): every address is a
function mailbox, never a person's (`owner_address`). Ticket 279 (its note of 2026-10-05): the
subject has no time tail (ticket 371: "Quick check: <the boxes the rows are about>", several joined
"A and B", "A, B and C"), drafts from different rooms are told apart by their Date header; the To
header is one line, never folded. Ticket 371 (workshop script v7's "Email template") makes the body
a short, friendly note of fixed words around the rows: a greeting, where it comes from, one
question, a reply date a week after the story's today (`PROTOTYPE_core.story_today`, never the
clock), a signature, the owner's mark last. Ticket 418 (ADR-0051): every draft names functions,
never people: the To line and the greeting the holder's function by its title ("Dear Head of IT
Operations,"), the signature the BCM Officer's. Ticket 503: every draft closes with 476's letter's
lines (`core.closing`), signed by that function. Each row is a "- " line, one alone as well,
said in plain words by `PROTOTYPE_core.plain_row`: no code and no hour grid.

Never sent, by construction: IMAP `APPEND` with `\\Draft` into the folder whose `LIST` carries
`\\Drafts` (RFC 6154), never a folder named here, and no other mail call. One call, one try: no
retry, nothing in the background. The password is read from its 0600 file at the call and goes
nowhere but the `LOGIN`.

Ticket 373 (ADR-0049) adds the second kind: the interview invitation (`invitation`), one draft to
the people `PROTOTYPE_core.invitees` names, on the slot `PROTOTYPE_core.interview_slot` reads from
the programme plan, with an `invite.ics` (`text/calendar; method=REQUEST`) and the re-interview
sheet (260) as the questionnaire attached; placed the same way, by `put_invitation`.

Ticket 406 adds the third: the drafts A8 showed first (`core.draft_parts`), each word for word,
placed by one tap (`put_shown`), each subject ending in the room's marker (`ROOM_MARKER`), a
digest that tells one mailbox's rooms apart and never the room code.

Every top-level name here is in `src/nemo/test_handover.py`'s `KEPT_FOR_FOLLOW_UP` (step 43), and
the mail imports sit inside the definitions, so step 43's hunt spares exactly this module's names.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import shown

from nemo import interview, walk

import PROTOTYPE_core as core

MAILBOX_HOST = "w01eb30c.kasserver.com"
MAILBOX_USER = "nemo@ai4bcm.org"
#: Placed by him through a kgadmin steps doc, mode 0600, owned by brain; read only at the call.
MAILBOX_PASSWORD = Path("/home/user/.config/nemo/imap-nemo")
#: t373 (ADR-0049 point 3): nemo's calendar, `CALDAV_URL` (its collection, ending "/"),
#: `CALDAV_USER` and `CALDAV_PASSWORD`, one KEY=value a line; placed by him with
#: calendar-wizard.sh, mode 0600; read only at the call, never printed or logged.
CALENDAR_ENV = Path("/home/user/.config/nemo/caldav-nemo.env")
#: Never a real domain (RFC 2606): no draft can reach a person even if it were sent.
OWNER_DOMAIN = "marschkamp.example"
FOLLOW_UP_SUBJECT = core.DRAFT_SUBJECT  # t391: the subject the drafts are shown first with
#: t373: the invitation's subject, its day and hour the plan's ("BIA raw material procurement:
#: Tue 17 Nov, 10:00")
INVITE_SUBJECT = "BIA {name}: {start:%a} {start.day} {start:%b}, {start:%H:%M}"
#: t373: who the invitation is from, as the .ics names its organiser (371's signature); t418
#: (ADR-0051): by function, as every draft signs
INVITE_FROM = "BCM Officer"
#: t418 (ADR-0051): how every draft closes, the sender by function; t503: the letter's closing
#: (`core.closing`), its `{function}` the BCM Officer's (`core.bcm_officer`)
CLOSING = "\n".join(core.closing("{function}")) + "\n"
#: t373: the event's agenda, the invitation's "What we'll do", in code's words
INVITE_AGENDA = ("Go through last year's answers and see what has changed. "
                 "The questionnaire is attached to the invitation.")
#: t406: the end of each shown draft's subject in the mailbox, so his one mailbox tells 50 rooms
#: apart; `mark` is `room_mark`, never the room code (ADR-0043 point 3: the code is the room's key)
ROOM_MARKER = " · room {mark}"
#: One line of a LIST answer: its attributes, its delimiter, its name as the server spells it.
LISTED_FOLDER = re.compile(rb'^\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$')


def owner_address(to: str) -> str:
    """The function mailbox for a stored `to` ("Owner of <resource name>"): the resource's name
    lower case, each run of characters other than a-z and 0-9 one hyphen, ends trimmed (ADR-0043's
    note of 2026-10-02). t418 r2 (ADR-0051 decision 5): never a person's, whoever holds it."""
    name = to.removeprefix(walk.REFERRED_TO_SAID.format(resource=""))
    return f"owner-of-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}@{OWNER_DOMAIN}"


def gap_mailbox(folder: Path, activity: str, d: dict[str, Any]) -> str:
    """t418 r2: the function mailbox a discrepancy goes to: its register resource's, else its
    activity's, as 377 refers it (`follow_up_drafts`)."""
    return owner_address(walk.REFERRED_TO_SAID.format(
        resource=d["resource"] or core.process_name(folder, activity)))


def invitee_address(folder: Path, activity: str, person: str, role: str) -> str:
    """t418 r2 (ADR-0051 decision 5): an invitee's function mailbox: the activity's own for its
    process owner; else that of the first resource the register has them holding that the
    activity uses (`core.holders`); else their function's, as ADR-0051's example names it
    ("head-of-it-operations@…"): no resource is theirs to own."""
    if "process owner" in role:
        return owner_address(core.process_name(folder, activity))
    held = dict(core.holders(folder, activity)).get(person)
    if held:
        return owner_address(held[0])
    return function_address(core.holder_function(folder, {"holder": role, "to": person}))


def function_address(function: str) -> str:
    """t539 (ADR-0056 S7): the mailbox code maps a function to, the model never typing one: its
    title lower case, each run of characters other than a-z and 0-9 one hyphen, at `OWNER_DOMAIN`
    (the seed names no address; ADR-0051's "head-of-it-operations@…")."""
    return f"{re.sub(r'[^a-z0-9]+', '-', function.lower()).strip('-')}@{OWNER_DOMAIN}"


def follow_up_drafts(folder: Path, now: datetime) -> list[tuple[str, bytes]]:
    """The room's drafts, one per (recipient, activity), each as its .eml file name and bytes: an
    unsent draft (`X-Unsent: 1`) with its own `Message-ID`, dated `now`, no header folded."""
    from email import policy
    from email.headerregistry import Address
    from email.message import EmailMessage
    from email.utils import format_datetime, make_msgid

    # Ticket 315: each resource's register owner, by its address under the stored `to`'s rule.
    owners = {owner_address(walk.REFERRED_TO_SAID.format(resource=asset.get("name") or "")):
              str(asset.get("owner_name") or "")
              for asset in core.drafting.read_register(folder).values() if isinstance(asset, dict)}
    # Ticket 377: a discrepancy with no register resource is referred about its activity, to the
    # process owner its interview names (`core.discrepancies`)
    owners.update({owner_address(walk.REFERRED_TO_SAID.format(
        resource=core.process_name(folder, a))): d["holder"] for a in walk.processes(folder)
        for d in core.discrepancies(folder, a) if d["resource"] is None})
    # Ticket 317: one draft per (recipient, activity), so a named holder's resources share one;
    # an unnamed owner is its resource's, one draft each. t418 r2: the draft goes to the function
    # mailbox of the first resource it is about (`owner_address`), never the holder's own
    grouped: dict[tuple[str, str], dict[str, list[str]]] = {}
    for to, activity, row in core.follow_up(folder):
        holder = owners.get(owner_address(to))
        person = re.fullmatch(r".+ \((.+)\)", holder or "")
        grouped.setdefault((person[1] if person else owner_address(to), activity),
                           {}).setdefault(to, []).append(row)
    made = []
    for (_, activity), by_to in sorted(grouped.items(), key=lambda g: (min(g[1]), g[0][1])):
        to = min(by_to)
        rows = [core.plain_row(row, t.removeprefix(walk.REFERRED_TO_SAID.format(resource="")))
                for t, said in sorted(by_to.items()) for row in said]
        rows = [row for row in rows if row.strip()]  # t418 r2: the closing follows a stated row
        if not rows:
            continue
        name = core.process_name(folder, activity)
        abouts = [t.removeprefix(walk.REFERRED_TO_SAID.format(resource="")) for t in sorted(by_to)]
        about = ", ".join(abouts[:-1]) + " and " * (len(abouts) > 1) + abouts[-1]
        owner = owners.get(owner_address(to))
        named = re.fullmatch(r"(.+) \((.+)\)", owner or "")
        # t418 (ADR-0051): the holder by function, never by name; r2: at a function mailbox
        shown = (named[1].split(",")[0].strip() if named else to if owner is None
                 else core.NOT_NAMED.format(resource=about))
        draft = EmailMessage(policy=policy.default.clone(max_line_length=None))
        draft["From"] = MAILBOX_USER
        draft["To"] = Address(shown, addr_spec=owner_address(to))
        draft["Subject"] = FOLLOW_UP_SUBJECT.format(about=about[:1].upper() + about[1:])
        draft["Date"] = format_datetime(now)
        draft["Message-ID"] = make_msgid(domain=MAILBOX_USER.partition("@")[2])
        draft["X-Unsent"] = "1"
        # Ticket 371: the v6 note, every word code's; its dates the story's, never the clock. t418:
        # it greets the function by its title (`core.DRAFT_DEAR`)
        today = core.story_today(folder)
        held = [datetime.strptime(Path(p).name[:8], "%y_%m_%d").date() for p in
                interview.paths_about(folder, interview.INTERVIEWS, activity)
                if re.match(r"\d\d_\d\d_\d\d_", Path(p).name)]
        day = max(held, default=None)
        on = (f", from the interview on {day:%A}, {day.day} {day:%B}"
              f"{f' {day.year}' if today is None or day.year != today.year else ''}" if day else "")
        by = today and today + timedelta(days=7)
        reply = f"by {by:%A}, {by.day} {by:%B}" if by else "within a week"
        draft.set_content(
            f"{core.DRAFT_DEAR.format(function=shown if named else to[:1].lower() + to[1:])}\n\n"
            f"this is about this year's BIA for {name}{on}.\n\n"
            + "".join(f"- {row}\n" for row in rows)
            + f"\n{core.DRAFT_ASK}\n"
              f"A short reply {reply} would be great.\n\n"
            + CLOSING.format(function=core.bcm_officer(folder))
            # The owner is authored (ADR-0034 Part D point 10): marked wherever it shows.
            + (f"\nOwner: {shown} · for the demo\n" if named else ""), cte="8bit")
        made.append((f"{owner_address(to).partition('@')[0]}--{activity}.eml", draft.as_bytes()))
    return made


def room_mark(folder: Path) -> str:
    """t406: the room's marker: six hex digits of a SHA-256 of its folder's name, the same for one
    room every time and different between rooms, and nothing that opens one."""
    import hashlib
    return hashlib.sha256(folder.name.encode("utf-8")).hexdigest()[:6]


def shown_drafts(folder: Path, activity: str, now: datetime) -> list[tuple[str, bytes]]:
    """t406: each draft A8 showed first (`core.draft_parts`), as its .eml file name and bytes:
    its lines word for word, its subject with the room's marker (`ROOM_MARKER`) at the end, to
    the function it names at the function mailbox of its first gap (`gap_mailbox`, t418 r2); an
    unsent draft (`X-Unsent: 1`) with its own `Message-ID`, dated `now`, no header folded."""
    found = core.discrepancies(folder, activity)
    made = []
    for to, person, subject, lines in core.draft_parts(folder, activity):
        address = gap_mailbox(folder, activity, next(d for d in found if d["to"] == person))
        # t418 (ADR-0051): the function by its title; r2: at its function mailbox
        made.append((f"{address.partition('@')[0]}--{activity}.eml", letter_draft(
            to.removeprefix(core.DRAFT_TO.format(function="")), address,
            subject + ROOM_MARKER.format(mark=room_mark(folder)), lines, now)))
    return made


def letter_draft(function: str, address: str, subject: str, lines: list[str],
                 now: datetime) -> bytes:
    """t406's draft, factored out for t539's letters: to the function by its title at `address`,
    the letter's lines word for word; an unsent draft (`X-Unsent: 1`) with its own `Message-ID`,
    dated `now`, no header folded."""
    from email import policy
    from email.headerregistry import Address
    from email.message import EmailMessage
    from email.utils import format_datetime, make_msgid

    draft = EmailMessage(policy=policy.default.clone(max_line_length=None))
    draft["From"] = MAILBOX_USER
    draft["To"] = Address(function, addr_spec=address)
    draft["Subject"] = subject
    draft["Date"] = format_datetime(now)
    draft["Message-ID"] = make_msgid(domain=MAILBOX_USER.partition("@")[2])
    draft["X-Unsent"] = "1"
    draft.set_content("\n".join(lines) + "\n", cte="8bit")  # t476: the letter, line for line
    return draft.as_bytes()


def put_shown(folder: Path, activity: str, now: datetime, *, password: Path | None = None,
              connect: Callable[[], Any] | None = None) -> list[str]:
    """t406: one tap: each draft A8 showed (`shown_drafts`) appended once to the drafts folder;
    the subjects placed, as the mailbox has them, or none where not all of them landed."""
    from email import message_from_bytes, policy

    named = shown_drafts(folder, activity, now)
    made = [data for _, data in named]
    if not made:  # nothing to place: the mailbox is never asked for nothing
        return []
    landed = appended(made, now, password=password, connect=connect) == len(made)
    shown.keep_drafts(folder, shown.digest(activity, core.drafts_first(folder, activity)),
                      activity, [name for name, _ in named], landed)
    if not landed:
        return []
    return [str(message_from_bytes(data, policy=policy.default)["Subject"]) for data in made]


def _ics_text(value: str) -> str:
    """An iCalendar TEXT value (RFC 5545 3.3.11): a backslash, semicolon, comma, newline escaped."""
    return (value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\n", "\\n"))


def _ics(lines: list[str]) -> bytes:
    """iCalendar lines as RFC 5545 has them: CRLF, each folded at 75 octets."""
    out = []
    for line in lines:
        part = ""
        for char in line:
            if len((part + char).encode("utf-8")) > 75:
                out.append(part)
                part = " "
            part += char
        out.append(part)
    return ("\r\n".join(out) + "\r\n").encode("utf-8")


def invitation(folder: Path, activity: str, now: datetime, *,
               slot: tuple[datetime, datetime] | None = None, uid: str | None = None,
               sequence: int = 0) -> tuple[str, bytes, bytes]:
    """t373: the activity's interview invitation, as its .eml file name and bytes, and the
    calendar event for nemo's own calendar (ADR-0049 point 2): one unsent draft (`X-Unsent: 1`,
    its own `Message-ID`, dated `now`, no header folded) to `core.invitees`, on
    `core.interview_slot`, in 371's friendly words and signature, the register-named people
    marked; `invite.ics` (method REQUEST) and the questionnaire attached. The event is the same
    VEVENT, the same UID, with no METHOD (a stored object, RFC 4791) and every attendee
    `SCHEDULE-AGENT=CLIENT` (RFC 6638), so the server sends nobody anything. t540: on `slot`
    where given, under the event's own `uid` and its `sequence` where it is moved."""
    import uuid
    from datetime import UTC
    from email import policy
    from email.headerregistry import Address
    from email.message import EmailMessage
    from email.utils import format_datetime, make_msgid

    import workspace  # the questionnaire's own module (260)

    slot = slot or core.interview_slot(folder, activity)
    if slot is None:
        raise ValueError(f"no planned day for {activity}")
    start, end = slot
    name = core.process_name(folder, activity)
    people = core.invitees(folder, activity)
    place = core.interview_place(folder)
    uid = uid or f"{uuid.uuid4()}@{MAILBOX_USER.partition('@')[2]}"
    addresses = [invitee_address(folder, activity, person, role) for person, role, _ in people]
    # t418 (ADR-0051): each invitee by function, never by name; r2: at function mailboxes
    functions = [core.holder_function(folder, {"holder": role, "to": person})
                 for person, role, _ in people]

    def event(stored: bool) -> bytes:
        agent = ";SCHEDULE-AGENT=CLIENT" * stored
        return _ics([
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//nemo//interview invitation//EN",
            *(["METHOD:REQUEST"] if not stored else []), "BEGIN:VEVENT", f"UID:{uid}",
            f"DTSTAMP:{now.astimezone(UTC):%Y%m%dT%H%M%SZ}",
            f"DTSTART:{start.astimezone(UTC):%Y%m%dT%H%M%SZ}",
            f"DTEND:{end.astimezone(UTC):%Y%m%dT%H%M%SZ}",
            f"SUMMARY:{_ics_text(f'BIA {name.lower()}: re-interview')}",
            *([f"LOCATION:{_ics_text(place[:1].upper() + place[1:])}"] if place else []),
            f"DESCRIPTION:{_ics_text(INVITE_AGENDA)}",
            f"ORGANIZER;CN={INVITE_FROM}{agent}:mailto:{MAILBOX_USER}",
            *(f"ATTENDEE;CN={function};ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE"
              f"{agent}:mailto:{address}" for function, address in zip(functions, addresses,
                                                                       strict=True)),
            f"SEQUENCE:{sequence}", "STATUS:CONFIRMED", "TRANSP:OPAQUE", "END:VEVENT",
            "END:VCALENDAR"])

    draft = EmailMessage(policy=policy.default)  # its parts base64 at 76; its headers below
    draft["From"] = MAILBOX_USER
    draft["To"] = [Address(function, addr_spec=address)
                   for function, address in zip(functions, addresses, strict=True)]
    draft["Subject"] = INVITE_SUBJECT.format(name=name.lower(), start=start)
    draft["Date"] = format_datetime(now)
    draft["Message-ID"] = make_msgid(domain=MAILBOX_USER.partition("@")[2])
    draft["X-Unsent"] = "1"
    when = f"{start:%A}, {start.day} {start:%B}, {start:%H:%M}–{end:%H:%M}"
    draft.set_content(
        f"Dear {', dear '.join(functions)},\n\n"
        f"it's time to review the BIA for {name.lower()}. Could we meet on {when}"
        f"{f', in {place}' if place else ''}?\n\n"
        "What we'll do: go through last year's answers and see what has changed.\n\n"
        "The questionnaire is attached. No preparation needed beyond a quick look.\n\n"
        # t377 (B3): an interview invitation carries no owner line (317/371's drafts keep theirs)
        + CLOSING.format(function=core.bcm_officer(folder)), cte="8bit")
    # base64, so the .ics keeps its CRLF lines byte for byte
    draft.add_attachment(event(False), maintype="text", subtype="calendar", filename="invite.ics",
                         params={"method": "REQUEST", "charset": "utf-8"})
    sheet = workspace.re_interview(folder, activity)
    if sheet:
        draft.add_attachment(sheet, subtype="html", filename="questionnaire.html")
    unfolded = policy.default.clone(max_line_length=None)  # no header folded, as 257's
    return f"invitation--{activity}.eml", draft.as_bytes(policy=unfolded), event(True)


def follow_up_folder(listed: list[Any]) -> str | None:
    """The folder a LIST answer marks `\\Drafts`, as the server spells it; None where none is."""
    for line in listed:
        found = LISTED_FOLDER.match(line) if isinstance(line, bytes) else None
        if found and rb"\drafts" in found["flags"].lower().split():
            return found["name"].decode()
    return None


def put_in_mailbox(folder: Path, now: datetime, *, password: Path | None = None,
                   connect: Callable[[], Any] | None = None) -> tuple[int, int]:
    """One tap: each of the room's drafts appended once, flagged `\\Draft`, to the mailbox's
    drafts folder. (landed, drafted); landed short of drafted where the mailbox is not reachable:
    no password file, no answer, a refused login, or no folder marked `\\Drafts`."""
    made = follow_up_drafts(folder, now)
    if not made:  # nothing to place: the mailbox is never asked for nothing
        return 0, 0
    landed = appended([data for _, data in made], now, password=password, connect=connect)
    shown.keep_drafts(folder, shown.digest("follow-up", core.follow_up(folder)), None,
                      [name for name, _ in made], landed == len(made))
    return landed, len(made)


def appended(made: list[bytes], now: datetime, *, password: Path | None = None,
             connect: Callable[[], Any] | None = None) -> int:
    """Each message appended once, flagged `\\Draft`, to the mailbox's drafts folder; how many
    landed: none where the mailbox is not reachable (no password file, no answer, a refused
    login, or no folder marked `\\Drafts`). t695: under pytest the real login with no `connect` of
    the test's own gets 0 before it is read, whichever fixture the test forgot; a test's own file
    is its own stub's."""
    import imaplib
    import os
    import ssl

    login = password or MAILBOX_PASSWORD
    if (connect is None and "PYTEST_CURRENT_TEST" in os.environ
            and login == Path("/home/user/.config/nemo/imap-nemo")):
        return 0
    landed = 0
    try:
        secret = login.read_text(encoding="utf-8").strip()
        opened = connect or (lambda: imaplib.IMAP4_SSL(
            MAILBOX_HOST, ssl_context=ssl.create_default_context(), timeout=20))
        with opened() as box:
            box.login(MAILBOX_USER, secret)
            into = follow_up_folder(box.list()[1])
            for data in made if into else []:
                said, _ = box.append(into, r"(\Draft)", imaplib.Time2Internaldate(now), data)
                landed += said == "OK"
    except (OSError, imaplib.IMAP4.error):
        pass
    return landed


def put_in_calendar(event: bytes, calendar: Path | None = None, *, update: bool = False) -> bool:
    """t373 (ADR-0049 point 2): the one event `PUT` into nemo's calendar under its own UID, with
    `If-None-Match: *` so no other event is ever overwritten; nothing read, edited or deleted.
    t540: an `update` is the same PUT with `If-Match: *`: it moves that one event, never makes one.
    Placed or not: no env file, no answer, a refusal. One call, one try.
    t407: the login is Digest, the only one all-inkl's server takes; its challenge is answered
    once, and a refused answer is never tried again (urllib's own handler would, five times).
    t695: under pytest the real env file gets False before it is read, as `appended`'s login."""
    import os
    import urllib.request

    env = calendar or CALENDAR_ENV
    if ("PYTEST_CURRENT_TEST" in os.environ
            and env == Path("/home/user/.config/nemo/caldav-nemo.env")):
        return False

    class OneDigestTry(urllib.request.HTTPDigestAuthHandler):
        def http_error_401(self, req: Any, fp: Any, code: int, msg: str, headers: Any) -> Any:
            if req.has_header("Authorization"):
                return None  # answered once and refused: the 401 stands
            return super().http_error_401(req, fp, code, msg, headers)

    try:
        said = dict(line.split("=", 1) for line in env.read_text(
            encoding="utf-8").splitlines() if "=" in line)
        uid = re.search(rb"^UID:(.+)\r$", event, re.M)[1].decode()  # type: ignore[index]
        url = said["CALDAV_URL"].strip().rstrip("/") + f"/{uid}.ics"
        known = urllib.request.HTTPPasswordMgrWithDefaultRealm()  # whatever realm it names
        known.add_password(None, url, said["CALDAV_USER"], said["CALDAV_PASSWORD"])
        request = urllib.request.Request(
            url, data=event, method="PUT",
            headers={"Content-Type": "text/calendar; charset=utf-8",
                     "If-Match" if update else "If-None-Match": "*"})
        with urllib.request.build_opener(OneDigestTry(known)).open(request, timeout=20) as answer:
            return bool(200 <= answer.status < 300)
    except (OSError, KeyError, ValueError):  # urllib's errors are OSErrors
        return False


def put_invitation(folder: Path, activity: str, now: datetime, *, password: Path | None = None,
                   connect: Callable[[], Any] | None = None,
                   calendar: Path | None = None) -> tuple[bool, bool]:
    """t373: one tap: the activity's invitation (`invitation`) appended once to the drafts folder,
    and its event put once into nemo's calendar (`put_in_calendar`), the one whether or not the
    other lands. (landed, the blocker placed)."""
    _, data, event = invitation(folder, activity, now)
    landed = appended([data], now, password=password, connect=connect) == 1
    blocked = put_in_calendar(event, calendar)
    start, end = core.interview_slot(folder, activity) or (now, now)  # `invitation` had one
    shown.put(folder, shown.INVITATION, {  # t533: kept in the room, so a restart knows it
        "activity": activity, "slot": [start.isoformat(), end.isoformat()],
        "event": re.search(rb"^UID:(.+)\r$", event, re.M)[1].decode(),  # type: ignore[index]
        "placed": landed and blocked})
    return landed, blocked


def move_invitation(folder: Path, activity: str, slot: tuple[datetime, datetime], now: datetime, *,
                    password: Path | None = None, connect: Callable[[], Any] | None = None,
                    calendar: Path | None = None) -> tuple[bool, bool]:
    """t540 (ADR-0056 S8): one tap: the activity's invitation on `slot`: its one calendar event
    moved there (the event's id kept, an update, its sequence one on), else placed new where the
    room keeps none; and a new invitation appended to the drafts folder, the earlier draft left
    as it is. (landed, the event moved or placed)."""
    was = shown.last(folder, shown.INVITATION, activity=activity)
    sequence = int(was.get("sequence") or 0) + 1 if was else 0
    _, data, event = invitation(folder, activity, now, slot=slot,
                                uid=was["event"] if was else None, sequence=sequence)
    landed = appended([data], now, password=password, connect=connect) == 1
    moved = put_in_calendar(event, calendar, update=was is not None)
    shown.put(folder, shown.INVITATION, {
        "activity": activity, "slot": [slot[0].isoformat(), slot[1].isoformat()],
        "event": re.search(rb"^UID:(.+)\r$", event, re.M)[1].decode(),  # type: ignore[index]
        "sequence": sequence, "placed": landed and moved})
    return landed, moved


# ── t533: what was placed, kept in the room (`shown`): a restart, a reconnect, a second copy's
# reopened link all read it, where the app's own sets are one process's memory ─────────────────
def invited(folder: Path, activity: str) -> bool:
    """The activity's last invitation landed in the mailbox and in nemo's calendar."""
    kept = shown.last(folder, shown.INVITATION, activity=activity)
    return bool(kept and kept.get("placed"))


def shown_placed(folder: Path, activity: str) -> bool:
    """The drafts A8 shows for the activity now were all placed, these same ones."""
    return shown.all_placed(folder, shown.digest(activity, core.drafts_first(folder, activity)))


def follow_up_placed(folder: Path) -> bool:
    """The follow-up list's drafts as they stand now were all placed (257)."""
    return shown.all_placed(folder, shown.digest("follow-up", core.follow_up(folder)))

