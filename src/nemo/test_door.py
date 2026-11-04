import os
import time
import uuid
from pathlib import PurePosixPath

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo.door import (
    PREFIX_SEGMENT,
    SWEEP_AGE_SECONDS,
    admit,
    authorise,
    checked_room_folder,
    checked_session_id,
    identity_from_link,
    sweep,
)

# The refusal itself is `nemo.room_code`'s, one layer below this door and `nemo.walk`'s mint both.
# What the door does with it is here; what it *is* is pinned in `test_room_code.py`.
from nemo.room_code import UNAUTHORISED, Refused


def test_the_room_code_in_the_link_is_the_identity():
    assert identity_from_link("https://demo.ai4bcm.org/r/demo-1") == "demo-1"


def test_a_trailing_slash_does_not_change_the_room():
    assert identity_from_link("https://demo.ai4bcm.org/r/demo-1/") == "demo-1"


def test_only_the_separator_is_stripped_from_the_end_of_the_link():
    """`rstrip` takes a set of characters, so a room code ending in one of them must survive."""
    assert identity_from_link("https://demo.ai4bcm.org/r/demoX") == "demoX"


def test_a_tracking_parameter_on_the_scanned_link_is_not_part_of_the_room():
    """nginx forwards `$request_uri`, which carries the query string. A room code decides storage,
    so `?x=1` inside the code is a silent wrong-room write rather than a cosmetic defect."""
    assert identity_from_link("https://demo.ai4bcm.org/r/demo-1?x=1") == "demo-1"
    assert identity_from_link("/demo/r/demo-1?utm_source=qr&utm_campaign=bciworld") == "demo-1"


def test_a_fragment_on_the_scanned_link_is_not_part_of_the_room():
    assert identity_from_link("/demo/r/demo-1#top") == "demo-1"


def test_a_link_carrying_no_room_code_is_refused():
    with pytest.raises(Refused, match="carries no room code"):
        identity_from_link("")


def test_the_prefix_with_nothing_after_it_is_refused():
    """The scan of a damaged QR: `/demo/r/` left `r`, and `r` is the prefix, not a room."""
    with pytest.raises(Refused, match="carries no room code"):
        identity_from_link("/demo/r/")


def test_the_prefix_without_its_trailing_slash_is_refused():
    with pytest.raises(Refused, match="carries no room code"):
        identity_from_link("/demo/r")


def test_a_room_folder_that_exists_is_the_room(tmp_path):
    (tmp_path / "demo-1").mkdir()
    assert checked_room_folder(tmp_path, "demo-1") == tmp_path / "demo-1"


def test_a_room_nobody_minted_has_no_folder_and_is_refused(tmp_path):
    (tmp_path / "demo-1").mkdir()
    with pytest.raises(Refused, match="the room 'demo-9' has no folder"):
        checked_room_folder(tmp_path, "demo-9")


def test_a_code_too_long_for_the_filesystem_is_refused_rather_than_raised(tmp_path):
    """The third outcome the door promises does not exist, found by this build's own hypothesis run.

    `Path.is_dir` swallows some errno values and re-raises the rest. A code past the filesystem's
    255-character name limit raises `ENAMETOOLONG`, which used to escape `checked_room_folder` as a
    bare `OSError` — a 500 in the running skin where the door's whole contract is a refusal in its
    own words. Deterministic at the boundary; it only looked flaky because the property test that
    caught it had to generate a name that long, and under `mutants/` the derandomised profile is
    absent so the search is random.
    """
    (tmp_path / "demo-1").mkdir()
    with pytest.raises(Refused, match="has no folder"):
        checked_room_folder(tmp_path, "a" * 300)


def test_a_code_at_the_filesystem_limit_is_still_only_refused(tmp_path):
    """The other side of the boundary, so the fix cannot be "refuse everything long"."""
    (tmp_path / "demo-1").mkdir()
    with pytest.raises(Refused, match="has no folder"):
        checked_room_folder(tmp_path, "a" * 255)
    assert checked_room_folder(tmp_path, "demo-1") == tmp_path / "demo-1"


def test_an_absent_rooms_folder_reads_as_an_absent_folder(tmp_path):
    """A mount that is away refuses a valid room — the accepted cost — and says which it is."""
    with pytest.raises(Refused, match="has no folder") as refusal:
        checked_room_folder(tmp_path / "not-mounted", "demo-1")
    assert "carries no room code" not in str(refusal.value)


def test_the_two_refusals_are_not_the_same_sentence(tmp_path):
    with pytest.raises(Refused) as damaged:
        identity_from_link("/demo/r/")
    with pytest.raises(Refused) as absent:
        checked_room_folder(tmp_path, "demo-9")
    assert str(damaged.value) != str(absent.value)
    assert "carries no room code" in str(damaged.value)
    assert "has no folder" in str(absent.value)


@pytest.mark.parametrize("room", [".", ".."])
def test_a_room_code_naming_the_rooms_folder_itself_is_refused(tmp_path, room):
    """`ROOMS / room` keeps a code to one segment, and `..` is one segment that leaves anyway."""
    assert (tmp_path / room).is_dir(), "the guard is what refuses this, not the folder check"
    with pytest.raises(Refused, match="has no folder"):
        checked_room_folder(tmp_path, room)


def test_the_room_that_owns_a_thing_may_touch_it():
    assert authorise("demo-1", "demo-1") is None


def test_another_room_may_not_touch_it():
    with pytest.raises(Refused, match="'demo-1' may not touch 'demo-2'") as refusal:
        authorise("demo-1", "demo-2")
    assert refusal.value.status == 401


def test_a_caller_with_no_identity_may_not_touch_it():
    with pytest.raises(Refused):
        authorise(None, "demo-2")


def test_a_uuid_session_identifier_is_passed_through_unchanged():
    session_id = str(uuid.uuid4())
    assert checked_session_id(session_id) == session_id


def test_a_traversal_session_identifier_is_refused():
    with pytest.raises(Refused, match="'../../scratch' is not a UUID"):
        checked_session_id("../../scratch")


def test_a_missing_session_identifier_is_refused():
    with pytest.raises(Refused, match="is not a UUID"):
        checked_session_id(None)


def test_a_connect_with_a_fresh_session_identifier_is_admitted():
    session_id = str(uuid.uuid4())
    assert admit("demo-1", {"sessionId": session_id}, {}) == session_id


def test_a_connect_reclaiming_the_rooms_own_session_is_admitted():
    session_id = str(uuid.uuid4())
    assert admit("demo-1", {"sessionId": session_id}, {session_id: "demo-1"}) == session_id


def test_a_connect_carrying_another_rooms_session_identifier_is_refused():
    session_id = str(uuid.uuid4())
    occupants = {session_id: "demo-2"}
    with pytest.raises(Refused):
        admit("demo-1", {"sessionId": session_id}, occupants)
    assert occupants == {session_id: "demo-2"}, "the occupant was evicted by the refusal"


def test_a_connect_with_a_crafted_session_identifier_is_refused_before_anything_else():
    with pytest.raises(Refused, match="is not a UUID"):
        admit("demo-1", {"sessionId": "../../scratch"}, {})


def _session_dir(parent, name, *, age_seconds):
    directory = parent / name
    directory.mkdir(parents=True)
    (directory / "upload.txt").write_text("a file the room uploaded")
    stamp = time.time() - age_seconds
    os.utime(directory, (stamp, stamp))
    return directory


#: Chainlit names a session's directory after its `sessionId`, which the door lets through only
#: as a UUID (ticket 160), so a session directory is one whose name is a UUID (ticket 175).
ORPHAN = "5b0e8c4a-3f1d-4e2b-9a7c-6d8e0f1a2b3c"
LIVE = "0c9d8e7f-6a5b-4c3d-8e2f-1a0b9c8d7e6f"


def test_the_sweep_takes_an_orphaned_session_directory(tmp_path):
    orphan = _session_dir(tmp_path, ORPHAN, age_seconds=SWEEP_AGE_SECONDS + 60)
    assert sweep(tmp_path) == [ORPHAN]
    assert not orphan.exists()


def test_the_sweep_leaves_an_old_directory_whose_name_is_not_a_uuid(tmp_path):
    """A room's folder, or anything else in the dir that Chainlit did not name after a session."""
    for name in ("demo-1", "not-a-session"):
        _session_dir(tmp_path, name, age_seconds=SWEEP_AGE_SECONDS + 60)
    assert sweep(tmp_path) == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["demo-1", "not-a-session"]


def test_the_sweep_never_follows_a_symlink_out_of_the_dir(tmp_path):
    outside = _session_dir(tmp_path, "outside", age_seconds=SWEEP_AGE_SECONDS + 60)
    files = tmp_path / "files"
    files.mkdir()
    link = files / ORPHAN
    link.symlink_to(outside, target_is_directory=True)
    assert sweep(files) == []
    assert link.is_symlink()
    assert (outside / "upload.txt").exists()


def test_the_sweep_leaves_a_session_directory_younger_than_its_age(tmp_path):
    live = _session_dir(tmp_path, LIVE, age_seconds=SWEEP_AGE_SECONDS - 60)
    assert sweep(tmp_path) == []
    assert (live / "upload.txt").exists()


def test_the_sweep_leaves_a_session_directory_exactly_at_its_age(tmp_path, monkeypatch):
    """The cutoff is not an orphan yet: at exactly `SWEEP_AGE_SECONDS` the room keeps its files.

    The clock is frozen on a whole second so the directory's mtime lands *on* the cutoff rather
    than a microsecond either side of it, which is the only place `<` and `<=` disagree.
    """
    frozen = 1_000_000_000.0
    monkeypatch.setattr(time, "time", lambda: frozen)
    on_the_cutoff = tmp_path / ORPHAN
    on_the_cutoff.mkdir()
    (on_the_cutoff / "upload.txt").write_text("a file the room uploaded")
    stamp = frozen - SWEEP_AGE_SECONDS
    os.utime(on_the_cutoff, (stamp, stamp))
    assert on_the_cutoff.stat().st_mtime == stamp, "the filesystem rounded the timestamp"

    assert sweep(tmp_path) == []
    assert (on_the_cutoff / "upload.txt").exists()


def test_the_sweep_is_a_no_op_before_chainlit_has_made_its_directory(tmp_path):
    """The first manager into a fresh room meets this: `.files` does not exist yet."""
    assert sweep(tmp_path / "files-chainlit-has-not-made-yet") == []


def test_the_sweep_leaves_stray_files_alone(tmp_path):
    stray = tmp_path / ORPHAN
    stray.write_text("x")
    os.utime(stray, (0, 0))
    assert sweep(tmp_path) == []
    assert stray.exists()


# ── properties ───────────────────────────────────────────────────────────────
# The door's four decisions are pure functions of their arguments, so what holds of them holds
# for every input rather than for the handful an example test names. Isolation has no partial
# credit: an example says the traversal in the story is refused, a property says no input at all
# gets a path separator past the door.

ROOM_CODES = st.text(alphabet=st.characters(categories=["Ll", "Lu", "Nd"]) | st.just("-"),
                     min_size=1, max_size=12).filter(
    lambda room: room.strip("/") == room and room != PREFIX_SEGMENT)

#: Every way a scanned link can end at the prefix instead of at a room code: the prefix with
#: nothing after it, and the prefix's own last segment repeated as the remainder.
NO_REMAINDER = st.sampled_from(["", PREFIX_SEGMENT])

#: Text that leans on the shapes an attacker reaches for first, plus arbitrary text behind them.
CRAFTED = (
    st.sampled_from(["../../scratch", "..", ".", "/", "", "/etc/passwd", "a/b",
                     "00000000-0000-0000-0000-00000000000", "\x00"])
    | st.text()
    | st.builds(lambda: str(uuid.uuid4()))
)


@given(ROOM_CODES, st.text(alphabet="abc/", max_size=8))
def test_the_room_is_always_the_last_segment_and_never_a_path(prefix_room, prefix):
    """Whatever nginx forwarded, the identity is one segment of it — never a path of its own."""
    room = identity_from_link(f"https://demo.ai4bcm.org/{prefix}{prefix_room}")

    assert "/" not in room
    assert room


@given(ROOM_CODES, st.integers(min_value=0, max_value=5))
def test_trailing_slashes_never_change_the_room(room, slashes):
    assert identity_from_link(f"https://demo.ai4bcm.org/r/{room}" + "/" * slashes) == room


@given(ROOM_CODES, st.none() | st.text(), st.none() | st.text())
def test_no_query_string_or_fragment_ever_reaches_the_room_code(room, query, fragment):
    """The defect the examples above name, as a property: a room code decides storage.

    The three literal links in this file prove `?x=1`, `?utm_…` and `#top` are dropped. They are
    the shapes a scanned link was shared with *today*; whatever a campaign appends tomorrow is
    arbitrary text, and this says none of it lands inside the directory that gets written. The
    other `identity_from_link` properties build links that never carry a `?` or a `#` at all, so
    without this one the `urlsplit` call could be deleted and only the examples would notice.
    """
    link = f"https://demo.ai4bcm.org/r/{room}"
    if query is not None:
        link += f"?{query}"
    if fragment is not None:
        link += f"#{fragment}"

    assert identity_from_link(link) == room


@given(NO_REMAINDER, st.integers(min_value=0, max_value=3), st.none() | st.text(),
       st.none() | st.text(), st.sampled_from(["/demo/r", "/r", "https://demo.ai4bcm.org/r"]))
def test_no_damaged_shape_of_the_link_ever_mints_a_room(remainder, slashes, query, fragment,
                                                        prefix):
    """The defect, as a property: a scan that loses the room code gets a refusal, not a room.

    Ticket 20 asked what the remainder of the path is and never whether there is one, so
    `/demo/r/` minted a credential for a room called `r`. The shapes here are the ones a damaged
    or half-printed QR actually produces — the prefix with nothing after it, with and without its
    trailing slash, with whatever a campaign appended, and with the prefix's own last segment as
    the remainder — and none of them is a room code.
    """
    link = f"{prefix}/{remainder}" + "/" * slashes
    if query is not None:
        link += f"?{query}"
    if fragment is not None:
        link += f"#{fragment}"

    with pytest.raises(Refused, match="carries no room code"):
        identity_from_link(link)


@given(ROOM_CODES, st.sampled_from(["%2F", "%2f", "%2e%2e%2F", "%00"]), ROOM_CODES)
def test_an_encoded_separator_never_reaches_the_filesystem(tmp_path_factory, before, encoded,
                                                           after):
    """The percent-encoding decision, pinned: nothing is decoded, so nothing has to be validated.

    `urlsplit` leaves `%2F` as three characters, so what comes out of the link is one segment and
    `rooms / room` is one child of the rooms folder. No room is named that, so the door refuses it
    — and the refusal is the one about a folder, because the code is well formed and merely does
    not exist.
    """
    rooms = tmp_path_factory.mktemp("rooms")
    (rooms / "demo-1").mkdir()
    room = identity_from_link(f"/demo/r/{before}{encoded}{after}")

    assert (rooms / room).parent == rooms, "a code reached outside the rooms folder"
    with pytest.raises(Refused, match="has no folder"):
        checked_room_folder(rooms, room)
    assert sorted(path.name for path in rooms.iterdir()) == ["demo-1"]


@given(st.data())
def test_no_scanned_link_at_all_admits_anything_but_the_room_that_was_minted(tmp_path_factory,
                                                                            data):
    """The door's whole admission, over every input rather than over the shapes we drew.

    Every other `identity_from_link` property builds its link out of `ROOM_CODES` and one of
    three known prefixes, so each says something about the links a QR *we* printed produces. A
    damaged scan produces characters nobody chose, and this ticket exists because a shape nobody
    had thought of — the prefix with nothing after it — was answered with a credential. So this
    one hands the composition the skin actually calls, `identity_from_link` then
    `checked_room_folder`, arbitrary text, and says there is no third outcome: either a refusal
    carrying the 401 the HTTP layer answers, or the one room that was really minted.

    The link is drawn from arbitrary text *and* from the real link for that room, because a
    property whose admitting branch never runs says only that the door refuses everything, which
    a door that refused its own rooms would satisfy too. `st.data` rather than two arguments to
    `given`: the room the folder is made for and the room the link names have to be the same
    draw, and independent strategies would agree only by a collision that never happens.
    """
    minted = data.draw(ROOM_CODES)
    link = data.draw(st.text() | st.sampled_from([f"/demo/r/{minted}", f"/demo/r/{minted}/"]))
    rooms = tmp_path_factory.mktemp("rooms")
    (rooms / minted).mkdir()

    try:
        folder = checked_room_folder(rooms, identity_from_link(link))
    except Refused as refusal:
        assert refusal.status == UNAUTHORISED
        return
    assert folder.parent == rooms, "a link reached outside the rooms folder"
    assert folder.name == minted, "a room nobody minted was admitted"
    assert folder.is_dir()


@given(NO_REMAINDER, st.sampled_from(["/demo/r", "/r", "https://demo.ai4bcm.org/r"]), ROOM_CODES)
def test_a_damaged_scan_and_an_absent_room_never_read_alike(tmp_path_factory, remainder, prefix,
                                                            room):
    """The operator's half of the ticket, held to the same standard as the defect's half.

    The two refusals are one class carrying one status, so the only thing that tells them apart
    is the sentence. An operator reading the journal has to know whether the QR on the table is
    damaged or the mount is away — they are different mornings' work — and that has to hold for
    every shape a damaged scan takes and every code a room can be called, not for the one pair
    an example names. Collapsing the two into one wording is the failure this refuses.
    """
    rooms = tmp_path_factory.mktemp("rooms")
    with pytest.raises(Refused) as damaged:
        identity_from_link(f"{prefix}/{remainder}")
    with pytest.raises(Refused) as absent:
        checked_room_folder(rooms, room)

    assert str(damaged.value) != str(absent.value)
    assert "carries no room code" in str(damaged.value)
    assert "carries no room code" not in str(absent.value)
    assert "has no folder" in str(absent.value)
    assert "has no folder" not in str(damaged.value)


@given(ROOM_CODES)
def test_a_room_is_admitted_only_when_its_folder_is_there(tmp_path_factory, room):
    """Both ways round, so the check cannot be satisfied by refusing everything."""
    rooms = tmp_path_factory.mktemp("rooms")
    with pytest.raises(Refused, match="has no folder"):
        checked_room_folder(rooms, room)

    (rooms / room).mkdir()
    assert checked_room_folder(rooms, room) == rooms / room


@given(st.text(min_size=1), st.text(min_size=1))
def test_authorise_admits_the_owning_room_and_refuses_every_other(actor, owner):
    """Equality is the whole rule, so it holds both ways: no near-miss is admitted."""
    if actor == owner:
        assert authorise(actor, owner) is None
    else:
        with pytest.raises(Refused):
            authorise(actor, owner)


@given(CRAFTED)
def test_a_checked_session_identifier_is_always_one_safe_path_component(value):
    """Chainlit makes a directory of whatever comes back, so what comes back must be a name.

    This is the property `deploy/nemo-demo-skin.service`'s second layer contains rather than
    closes: no separator, no `..`, nothing that resolves anywhere but one level down.
    """
    try:
        session_id = checked_session_id(value)
    except Refused:
        return
    assert PurePosixPath(session_id).parts == (session_id,)
    assert session_id not in (".", "..")
    assert session_id == str(value)


@given(st.text(min_size=1), CRAFTED, st.dictionaries(st.text(), st.text(min_size=1), max_size=4),
       st.none() | st.sampled_from(["demo-1", "demo-2"]))
def test_admit_never_evicts_an_occupant(room, session_id, occupants, holder):
    """A refusal at the door is a refusal and nothing more: the room already open stays open.

    `holder` seeds the identifier under test into the map, so the hijack branch is reached rather
    than left to a collision between arbitrary text and a UUID that never happens.
    """
    if holder is not None:
        occupants[session_id] = holder
    before = dict(occupants)
    try:
        admitted = admit(room, {"sessionId": session_id}, occupants)
    except Refused:
        assert occupants == before
        return
    assert occupants == before
    assert occupants.get(admitted, room) == room
