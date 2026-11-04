"""The room code, and the one refusal every door gives about one. Below all of them.

A room code is the credential (ADR-0003), and until ticket 50 exactly one module read one:
`nemo.door`, which the demo skin calls before it lets anybody in. Minting made a second reader out
of `nemo.walk` — `mint_room` has to know what a code may look like before it joins one to a path
and makes it, and it has to say no in the same word the skin already catches. `nemo.walk` read all
three names out of `nemo.door` for one commit, which put the top layer's import on a module it
otherwise has nothing to do with, in the direction that invites a cycle: the door's next refusal
about a room that has no walk would come back the other way. So the thing they share sits below
them both rather than one of them importing the other, exactly as `nemo.lane` sits below `nemo.ask`
and `nemo.conduct` and `nemo.text` below every layer that compares two strings.

**One exception type, not two.** `demo_skin/app.py` mints and then checks inside a single `except`,
and a second class there would be a second `except` somebody forgets to add — the refusal a
delegate meets is the same event whether the code named no room or named a room nobody could
build. What differs is the sentence, which is the caller's, and `operator` is how one refusal
carries two of them.

Nothing here touches the disk or is told what time it is: a code is a string, and what this module
says about one is the same answer every time it is asked. `test_room_code.py` asks it over
generated text rather than over the shapes we thought of.
"""

from __future__ import annotations

import re

#: What the HTTP layer answers when a door says no.
UNAUTHORISED = 401

#: Ticket 22's second refusal, in the one place it is worded. An absent mount refuses in this
#: sentence too (``nemo.walk.ABSENT_MOUNT`` says which mount, and then this), so an operator who
#: learns to read one of them reads both — which is only true while there is one sentence to change.
NO_FOLDER = "the room {room!r} has no folder"


class Refused(Exception):
    """A door said no. ``status`` is what the HTTP layer answers.

    ``operator`` is the line that goes to the console, and so to the unit's journal. It is the
    same sentence unless a refusal has two audiences — ticket 50's broken seed is the first: the
    delegate reads why nobody could seat them, in words with no path and no field name in them
    (``docs/voice.md`` §3.1), and the operator reads which file to open. One sentence written for
    both is one of them badly served.
    """

    status = UNAUTHORISED

    def __init__(self, message: str, operator: str = "") -> None:
        super().__init__(message)
        self.operator = operator or message


#: What a room code has to look like before any door will **create** a folder for it: one segment
#: of lowercase letters, digits and hyphens, which is what the printed QRs carry (`adler-7ycyet`).
#: Reading asks nothing of a code — a folder on disk is a room whatever it is called — so this is
#: `mintable`'s and never `nemo.door.checked_room_folder`'s.
_A_ROOM_CODE = re.compile(r"\A[a-z0-9-]+\Z")


def mintable(code: str) -> bool:
    """Whether a room may be *created* for this code. Ticket 50's half of the encoding decision.

    ``nemo.door.identity_from_link`` decodes nothing, so ``..%2F..%2Fetc`` arrives as one literal
    segment and ``rooms / code`` stays a child of the rooms folder — which was the whole defence
    while a code could only ever be read. Minting joins a code to a path that does not exist yet
    and then makes it, so a shape that was harmless to look up is not harmless to `mkdir`: `.` and
    `..` name the rooms folder and its parent, and a dot-file name is a room no QR carries. This
    says yes to the shapes a printed code has and to nothing else, which needs no decoding and no
    second validation. ``test_a_mintable_code_can_only_name_a_new_child_of_the_rooms_folder``
    pins it over arbitrary text rather than over the shapes we thought of.
    """
    return _A_ROOM_CODE.match(code) is not None
