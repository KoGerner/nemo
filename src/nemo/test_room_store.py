import io
import json
import stat
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

import pytest
from hypothesis import assume, example, given, settings
from hypothesis import strategies as st

from nemo import room_store
from nemo.room_store import (
    PathRefused,
    Shrunk,
    StaleWrite,
    jailed_path,
    read_record,
    room_lock,
    write_document,
    write_record,
)
from nemo.test_ask import repo_root


def test_a_path_inside_the_room_is_allowed(tmp_path):
    assert jailed_path(tmp_path, "output/.bia-runs/slaughter.json") == (
        tmp_path / "output/.bia-runs/slaughter.json"
    )


def test_a_path_climbing_out_of_the_room_is_refused(tmp_path):
    room = tmp_path / "demo-1"
    room.mkdir()
    with pytest.raises(PathRefused, match="'../escaped.json' resolves outside the room"):
        jailed_path(room, "../escaped.json")


def test_an_absolute_path_is_refused(tmp_path):
    with pytest.raises(PathRefused):
        jailed_path(tmp_path, "/etc/passwd")


def test_the_room_folder_itself_is_not_a_writable_path(tmp_path):
    with pytest.raises(PathRefused):
        jailed_path(tmp_path, "")


def test_a_symlink_pointing_out_of_the_room_is_refused(tmp_path):
    room = tmp_path / "demo-1"
    room.mkdir()
    (room / "out").symlink_to(tmp_path)
    with pytest.raises(PathRefused):
        jailed_path(room, "out/escaped.json")


def test_a_write_resolving_outside_the_room_changes_nothing_outside_it(tmp_path):
    room = tmp_path / "demo-1"
    room.mkdir()
    outside = tmp_path / "escaped.json"
    outside.write_text("untouched", encoding="utf-8")

    with pytest.raises(PathRefused):
        write_record(room, "../escaped.json", {"stage": 1}, 0)

    assert outside.read_text(encoding="utf-8") == "untouched"


def test_reading_a_record_that_was_never_written_gives_nothing(tmp_path):
    assert read_record(tmp_path, "output/.bia-runs/slaughter.json") is None


def test_the_first_write_creates_the_record_at_revision_one(tmp_path):
    saved = write_record(tmp_path, "output/.bia-runs/slaughter.json", {"stage": 1}, 0)

    assert saved == {"stage": 1, "revision": 1}
    assert read_record(tmp_path, "output/.bia-runs/slaughter.json") == saved
    assert json.loads(
        (tmp_path / "output/.bia-runs/slaughter.json").read_text(encoding="utf-8")
    ) == saved


def test_a_fresh_writer_wins_and_the_revision_advances(tmp_path):
    write_record(tmp_path, "run.json", {"stage": 1}, 0)

    saved = write_record(tmp_path, "run.json", {"stage": 2}, 1)

    assert saved == {"stage": 2, "revision": 2}
    assert read_record(tmp_path, "run.json") == {"stage": 2, "revision": 2}


def test_a_stale_writer_loses_and_the_saved_revision_is_intact(tmp_path):
    write_record(tmp_path, "run.json", {"stage": 1}, 0)  # revision A
    write_record(tmp_path, "run.json", {"stage": 2}, 1)  # revision B, by another writer

    with pytest.raises(StaleWrite) as refused:
        write_record(tmp_path, "run.json", {"stage": 9}, 1)

    assert refused.value.current_revision == 2
    assert str(refused.value) == "the record is at revision 2"
    assert read_record(tmp_path, "run.json") == {"stage": 2, "revision": 2}


def test_creating_a_record_that_already_exists_is_stale(tmp_path):
    write_record(tmp_path, "run.json", {"stage": 1}, 0)

    with pytest.raises(StaleWrite) as refused:
        write_record(tmp_path, "run.json", {"stage": 1}, 0)

    assert refused.value.current_revision == 1


def test_a_writer_ahead_of_the_record_is_stale_too(tmp_path):
    with pytest.raises(StaleWrite) as refused:
        write_record(tmp_path, "run.json", {"stage": 1}, 3)

    assert refused.value.current_revision == 0


def test_the_revision_the_caller_offers_is_not_the_one_that_is_saved(tmp_path):
    saved = write_record(tmp_path, "run.json", {"stage": 1, "revision": 7}, 0)

    assert saved["revision"] == 1


def test_a_sibling_whose_name_starts_with_the_room_name_is_refused(tmp_path):
    """The jail compares path parts, not string prefixes: `demo-10` is not inside `demo-1`."""
    room = tmp_path / "demo-1"
    room.mkdir()
    (tmp_path / "demo-10").mkdir()

    with pytest.raises(PathRefused):
        jailed_path(room, "../demo-10/run.json")


def test_a_symlink_that_stays_inside_the_room_is_allowed(tmp_path):
    """The jail refuses escape, not indirection, so a link within the room resolves and is kept."""
    room = tmp_path / "demo-1"
    (room / "real").mkdir(parents=True)
    (room / "link").symlink_to(room / "real")

    assert jailed_path(room, "link/run.json") == room / "real/run.json"


def test_a_write_only_creates_folders_inside_the_room(tmp_path):
    room = tmp_path / "demo-1"
    room.mkdir()

    write_record(room, "output/.bia-runs/slaughter.json", {"stage": 1}, 0)

    assert (room / "output/.bia-runs").is_dir()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["demo-1"]


def test_two_records_in_one_room_hold_independent_revisions(tmp_path):
    write_record(tmp_path, "a.json", {"stage": 1}, 0)
    write_record(tmp_path, "a.json", {"stage": 2}, 1)

    saved = write_record(tmp_path, "b.json", {"stage": 1}, 0)

    assert saved["revision"] == 1
    assert read_record(tmp_path, "a.json") == {"stage": 2, "revision": 2}


def test_a_record_that_is_not_json_is_raised_and_never_read_as_absent(tmp_path):
    """A record too broken to read must not look like revision 0, or a write would clobber it."""
    (tmp_path / "run.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        read_record(tmp_path, "run.json")
    with pytest.raises(json.JSONDecodeError):
        write_record(tmp_path, "run.json", {"stage": 1}, 0)
    assert (tmp_path / "run.json").read_text(encoding="utf-8") == "{not json"


def test_the_revision_json_hands_back_is_read_as_an_integer(tmp_path):
    """`revision` arrives from JSON, so the store pins its type rather than trusting the file."""
    (tmp_path / "run.json").write_text('{"stage": 1, "revision": "1"}', encoding="utf-8")

    saved = write_record(tmp_path, "run.json", {"stage": 2}, 1)

    assert saved == {"stage": 2, "revision": 2}


def test_a_record_with_text_outside_ascii_round_trips(tmp_path):
    saved = write_record(tmp_path, "run.json", {"process": "Schlachtung Groß"}, 0)

    assert read_record(tmp_path, "run.json") == saved
    assert read_record(tmp_path, "run.json")["process"] == "Schlachtung Groß"


# ── properties ───────────────────────────────────────────────────────────────
# The two properties this module exists for, stated over every input rather than over the
# examples above: nothing lands outside the room, and no accepted write skips a revision.
# `tmp_path` is a function-scoped fixture and Hypothesis reuses it across examples, so these
# make their own directory per example instead.

#: The shapes a relative path arrives in, with arbitrary text behind them.
RELATIVE_PATHS = (
    st.sampled_from(["../escaped.json", "..", ".", "", "/etc/passwd", "a/../../b", "run.json",
                     "output/.bia-runs/slaughter.json", "./run.json", "a//b"])
    | st.text(alphabet="ab./\\-", max_size=10)
    | st.text(max_size=20)
)

JSON_SCALARS = st.none() | st.booleans() | st.integers() | st.text()
RECORDS = st.dictionaries(st.text(max_size=8).filter(lambda k: k != "revision"),
                          JSON_SCALARS | st.lists(JSON_SCALARS, max_size=3), max_size=4)


@given(RELATIVE_PATHS)
def test_a_jailed_path_is_always_strictly_inside_the_room(relative_path):
    """Allowed or refused, there is no third answer, and allowed means strictly below the room."""
    with tempfile.TemporaryDirectory() as scratch:
        room = Path(scratch).resolve() / "demo-1"
        room.mkdir()
        try:
            target = jailed_path(room, relative_path)
        except (PathRefused, OSError, ValueError):
            return
        assert room in target.parents
        assert target != room


@given(st.lists(RECORDS, min_size=1, max_size=6))
def test_every_accepted_write_advances_the_revision_by_exactly_one(records):
    """Revision counts accepted writes, and the last one written is the one that reads back."""
    with tempfile.TemporaryDirectory() as scratch:
        room = Path(scratch)
        for expected, record in enumerate(records):
            saved = write_record(room, "run.json", record, expected)
            assert saved["revision"] == expected + 1
        assert read_record(room, "run.json") == {**records[-1], "revision": len(records)}


@given(st.lists(RECORDS, min_size=1, max_size=4), st.integers(min_value=-3, max_value=8))
def test_a_write_at_any_other_revision_is_refused_and_changes_nothing(records, offered):
    """A loser leaves the record exactly as the winner left it — compare-and-set, not last-wins."""
    with tempfile.TemporaryDirectory() as scratch:
        room = Path(scratch)
        for expected, record in enumerate(records):
            write_record(room, "run.json", record, expected)
        current = read_record(room, "run.json")

        if offered == len(records):
            return
        with pytest.raises(StaleWrite) as refused:
            write_record(room, "run.json", {"loser": True}, offered)
        assert refused.value.current_revision == len(records)
        assert read_record(room, "run.json") == current

# ── the properties: the jail holds for every path, not the six written above ──
# Each example makes its own room with `tempfile` rather than taking `tmp_path`: a function-scoped
# fixture is shared across a Hypothesis run, so one example's file would be the next one's starting
# state. `max_examples` is trimmed and `deadline` dropped because these touch a real filesystem —
# the hardener runs this suite once per mutant, and a disk-bound default would dominate that run.
SEGMENT = st.text(alphabet="abcXY019_-", min_size=1, max_size=6)
SEGMENTS = st.lists(SEGMENT, min_size=1, max_size=4)
ON_DISK = settings(max_examples=25, deadline=None)


@ON_DISK
@given(SEGMENTS)
def test_a_benign_relative_path_always_lands_strictly_inside_the_room(segments):
    """The jail's whole promise, as a property: what comes back is under the room, or nothing is.

    `in target.parents` is strict, so the room folder itself can never be the answer — a record is
    always a file in the room, never the room.
    """
    with tempfile.TemporaryDirectory() as room:
        target = jailed_path(Path(room), "/".join(segments))
        assert Path(room).resolve() in target.parents


@ON_DISK
@given(SEGMENTS)
def test_a_path_climbing_out_of_the_room_is_always_refused(segments):
    with tempfile.TemporaryDirectory() as room:
        with pytest.raises(PathRefused):
            jailed_path(Path(room), "../" + "/".join(segments))


@ON_DISK
@given(SEGMENTS)
def test_an_absolute_path_is_always_refused(segments):
    """An absolute path discards the room folder entirely — refused, never quietly re-rooted."""
    with tempfile.TemporaryDirectory() as room:
        with pytest.raises(PathRefused):
            jailed_path(Path(room), "/" + "/".join(segments))


@ON_DISK
@given(SEGMENTS, st.text(max_size=20))
def test_a_written_record_always_reads_back_as_it_was_saved(segments, mtpd):
    """Round-trip, with the revision the store owns: a first write lands at 1, not at 0."""
    with tempfile.TemporaryDirectory() as room:
        relative = "/".join(segments) + ".json"
        saved = write_record(Path(room), relative, {"mtpd": mtpd}, 0)
        assert saved == {"mtpd": mtpd, "revision": 1}
        assert read_record(Path(room), relative) == saved


@ON_DISK
@given(SEGMENTS, st.integers(min_value=1, max_value=6))
def test_every_accepted_write_advances_the_revision_on_any_path(segments, writes):
    """So a writer that read revision n and won holds n+1, whatever the record has been through."""
    with tempfile.TemporaryDirectory() as room:
        relative = "/".join(segments) + ".json"
        for revision in range(writes):
            write_record(Path(room), relative, {"n": revision}, revision)
        assert read_record(Path(room), relative)["revision"] == writes


@ON_DISK
@given(SEGMENTS, st.integers(min_value=0, max_value=6))
def test_only_the_revision_the_writer_actually_read_is_ever_accepted(segments, claimed):
    """Compare-and-set from the losing side: every other revision is refused, and told the truth."""
    with tempfile.TemporaryDirectory() as room:
        relative = "/".join(segments) + ".json"
        write_record(Path(room), relative, {"n": 0}, 0)
        assume(claimed != 1)
        with pytest.raises(StaleWrite) as refused:
            write_record(Path(room), relative, {"n": 1}, claimed)
        assert refused.value.current_revision == 1


# ── a document may not be overwritten with a fraction of its bytes ───────────
#
# v1's numbers: a stage-2 capture went 10,514 -> 2,099 bytes and a stage-3 analysis
# 11,939 -> 1,853, with every `##` heading intact, while every gate behaved as designed.


def test_the_first_write_of_a_document_has_nothing_to_shrink_from(tmp_path):
    write_document(tmp_path, "output/slaughter/stage4-worksheet.md", "x" * 20)

    assert (tmp_path / "output/slaughter/stage4-worksheet.md").read_bytes() == b"x" * 20


def test_a_document_that_is_not_there_yet_shrinks_from_nothing_even_when_it_is_empty(tmp_path):
    """The one write where "nothing saved" and "nothing offered" meet.

    A first write starts from zero saved bytes, not from one: were it one, an empty document —
    which is what a view of a record holding no activity and no open item comes to — would be
    refused on its very first write, and the room would never get the file at all.
    """
    write_document(tmp_path, "output/slaughter/stage1-scope-and-guide.md", "")

    assert (tmp_path / "output/slaughter/stage1-scope-and-guide.md").read_bytes() == b""


def test_a_document_offered_a_fraction_of_its_bytes_is_refused_with_both_counts(tmp_path):
    write_document(tmp_path, "capture.md", "x" * 10514)

    with pytest.raises(Shrunk) as refused:
        write_document(tmp_path, "capture.md", "x" * 2099)

    assert "capture.md" in str(refused.value)
    assert "10514" in str(refused.value) and "2099" in str(refused.value)
    assert refused.value.saved == 10514 and refused.value.offered == 2099


def test_the_refusal_is_about_the_bytes_and_not_about_the_headings(tmp_path):
    """v1's gate compared the set of `##` headings, and the gutted document kept every one."""
    headings = "\n".join(f"## {n}" for n in range(30))
    write_document(tmp_path, "capture.md", headings + "\n" + "body. " * 2000)

    with pytest.raises(Shrunk) as refused:
        write_document(tmp_path, "capture.md", headings + "\n")

    said = str(refused.value).lower()
    assert "heading" not in said and "##" not in said


def test_a_refused_overwrite_leaves_the_document_on_disk_exactly_as_it_was(tmp_path):
    write_document(tmp_path, "capture.md", "x" * 4000)

    with pytest.raises(Shrunk):
        write_document(tmp_path, "capture.md", "y" * 100)

    assert (tmp_path / "capture.md").read_bytes() == b"x" * 4000


@example(saved=10514, offered=2099)  # v1's gutted capture: the case this threshold exists for.
@example(saved=2099, offered=10514)  # and the same write the other way round, which is allowed.
@example(saved=4000, offered=2000)  # exactly half, which is not a fraction of it.
@given(saved=st.integers(min_value=1, max_value=12000),
       offered=st.integers(min_value=1, max_value=12000))
@ON_DISK
def test_a_document_is_refused_exactly_when_it_would_lose_more_than_half_its_bytes(saved, offered):
    """One threshold, in one place, for every document that goes through this door.

    Both sides of it are named above rather than left to the generator: at 25 examples a range
    that happens to hold only one of the two answers is a property that passes without ever
    seeing a refusal.
    """
    with tempfile.TemporaryDirectory() as room:
        write_document(Path(room), "view.md", "x" * saved)
        try:
            write_document(Path(room), "view.md", "y" * offered)
        except Shrunk:
            assert offered * 2 < saved
        else:
            assert offered * 2 >= saved


class DiesMidWrite:
    """A file that takes the first bytes and then the process goes away.

    The crash is injected at `io.open`, which is the one seam both a plain `write_bytes` and a
    staged temp file go through, so the test says nothing about how the write is spelled.
    """

    def __init__(self, handle):
        self._handle = handle

    def write(self, payload):
        self._handle.write(payload[:12])
        self._handle.flush()
        raise OSError("the process died mid-write")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return self._handle.__exit__(*exc_info)


@contextmanager
def dying_disk(monkeypatch):
    """Every file opened for writing inside the block dies after twelve bytes."""
    opened_for_real = io.open

    def dies(*args, **kwargs):
        handle = opened_for_real(*args, **kwargs)
        return DiesMidWrite(handle) if "w" in getattr(handle, "mode", "") else handle

    monkeypatch.setattr(io, "open", dies)
    try:
        yield
    finally:
        monkeypatch.undo()


def test_a_record_write_that_dies_partway_leaves_the_saved_record_intact(tmp_path, monkeypatch):
    """ADR-0010 makes the run file the resume checkpoint, and a `SIGTERM` deploy or an OOM kill
    lands between bytes. What is on disk after a half-finished write must still load."""
    write_record(tmp_path, "output/.bia-runs/slaughter.json", {"stage": 1}, 0)

    with dying_disk(monkeypatch), pytest.raises(OSError, match="the process died"):
        write_record(tmp_path, "output/.bia-runs/slaughter.json", {"stage": 2}, 1)

    assert read_record(tmp_path, "output/.bia-runs/slaughter.json") == {"stage": 1, "revision": 1}
    assert [child.name for child in (tmp_path / "output/.bia-runs").iterdir()] == [
        "slaughter.json"], "the staged file the write died on was left in the room"


def test_a_written_record_is_readable_by_whoever_serves_the_room(tmp_path):
    """The staged file a write goes through is the process's own, mode 0600. The record is not:
    nginx serves the graph page and the views out of the room folder under another uid, so a write
    that narrowed the mode would take the pictures off the web without touching a byte of them."""
    write_record(tmp_path, "output/.bia-runs/slaughter.json", {"stage": 1}, 0)
    write_document(tmp_path, "output/capture.md", "the manager's words")

    for relative_path in ("output/.bia-runs/slaughter.json", "output/capture.md"):
        assert stat.S_IMODE((tmp_path / relative_path).stat().st_mode) == 0o644, relative_path


def test_the_bytes_are_staged_in_the_rooms_own_folder_so_the_rename_is_atomic(tmp_path,
                                                                             monkeypatch):
    """`rename` is atomic within one filesystem and is not one across two. Staging in the system
    temp directory instead of beside the target is a cross-device rename: an error outright on a
    box whose `/tmp` is a tmpfs, and on a box where it is not it stops being the one property this
    write exists for. Nothing about the finished file says which happened, so the staged file is
    caught where it lives, while the write is still going on."""
    write_record(tmp_path, "output/.bia-runs/slaughter.json", {"stage": 1}, 0)
    beside = []
    opened_for_real = io.open

    def watching(*args, **kwargs):
        handle = opened_for_real(*args, **kwargs)
        if "w" in getattr(handle, "mode", ""):
            beside.extend(child.name for child in (tmp_path / "output/.bia-runs").iterdir())
        return handle

    monkeypatch.setattr(io, "open", watching)
    write_record(tmp_path, "output/.bia-runs/slaughter.json", {"stage": 2}, 1)
    monkeypatch.undo()

    assert len(beside) == 2 and "slaughter.json" in beside, (
        f"the bytes were staged outside the room's own folder: {beside}")


# ── ticket 208 (finding B2): two of his tabs, one room ────────────────────────
#
# `os.replace` is atomic; the revision compare in front of it is not part of it. One manager has
# one room and one process serves the phone, so the two writers the demo can really produce are
# two threads: a double-tap, or the room link open on a second device.

#: How long a writer standing inside the compare waits for the other one. Long enough that a
#: second thread with nothing in its way finishes its whole write, short enough that the test
#: costs no more than this when the lock is doing its job and the other one never gets in.
A_MOMENT = 0.5


def both_read_the_same_revision(monkeypatch, room_folder):
    """Stand the first writer still between its read and its replace, and let the second through.

    This is the race as it happens, held open on purpose: there is no way to sit inside a window
    of a few microseconds from outside the module. The first writer reads, waits for the second to
    say it is done, and then replaces. With the compare and the replace under the room's own lock
    the second cannot even start, the wait times out, and the second writer loses at the compare —
    which is the whole of what the lock is for.
    """
    read_it = threading.Event()
    second_is_done = threading.Event()
    reading = room_store._record_at
    first = None

    def waiting(target):
        nonlocal first
        record = reading(target)
        if first is None:
            first = threading.current_thread()
        if threading.current_thread() is first:
            read_it.set()
            second_is_done.wait(A_MOMENT)
        return record

    monkeypatch.setattr(room_store, "_record_at", waiting)
    return read_it, second_is_done


def test_two_writers_at_one_revision_do_not_both_win(tmp_path, monkeypatch):
    """A double-tap: both presses read revision 1, and one of them must lose at the compare."""
    room = tmp_path / "konstantin-glm"
    write_record(room, "output/.bia-runs/slaughter.json", {"who": "the opening"}, 0)
    read_it, second_is_done = both_read_the_same_revision(monkeypatch, room)
    won = []

    def press(who):
        try:
            won.append(write_record(room, "output/.bia-runs/slaughter.json", {"who": who}, 1))
        except StaleWrite:
            pass

    first = threading.Thread(target=press, args=("the first tap",))
    first.start()
    read_it.wait(A_MOMENT)
    second = threading.Thread(target=press, args=("the second tap",))
    second.start()
    second.join()
    second_is_done.set()
    first.join()

    assert len(won) == 1, f"both writers were told they had saved: {won}"
    assert read_record(room, "output/.bia-runs/slaughter.json") == won[0]


def test_the_revision_counts_the_writes_that_were_told_they_won(tmp_path, monkeypatch):
    """The lost update, said as the number it is: a revision of 2 after two accepted writes means
    one of them was never anybody's to read."""
    room = tmp_path / "konstantin-glm"
    write_record(room, "output/.bia-runs/slaughter.json", {"who": "the opening"}, 0)
    read_it, second_is_done = both_read_the_same_revision(monkeypatch, room)
    accepted = []

    def press(who):
        try:
            write_record(room, "output/.bia-runs/slaughter.json", {"who": who}, 1)
            accepted.append(who)
        except StaleWrite:
            pass

    first = threading.Thread(target=press, args=("the first tap",))
    first.start()
    read_it.wait(A_MOMENT)
    second = threading.Thread(target=press, args=("the second tap",))
    second.start()
    second.join()
    second_is_done.set()
    first.join()

    assert read_record(room, "output/.bia-runs/slaughter.json")["revision"] == len(accepted) + 1


def test_one_room_hands_out_one_lock(tmp_path):
    assert room_lock(tmp_path) is room_lock(tmp_path)


def test_two_rooms_do_not_share_a_lock(tmp_path):
    """A slow write in one manager's room must not hold up another manager's."""
    first, second = tmp_path / "konstantin-glm", tmp_path / "torsten-glm"
    first.mkdir()
    second.mkdir()
    assert room_lock(first) is not room_lock(second)


def test_the_same_room_reached_two_ways_is_one_room(tmp_path):
    """Keyed on the resolved path: a room reached through a symlink is not a second room with a
    lock of its own, which would be a lock that guards nothing."""
    room = tmp_path / "konstantin-glm"
    room.mkdir()
    (tmp_path / "by-another-name").symlink_to(room)
    assert room_lock(room) is room_lock(tmp_path / "by-another-name")


def test_a_writer_that_already_holds_the_room_may_write_through_it(tmp_path):
    """Ticket 211: the record press holds the room's lock across its land and its save, and both
    of those go through `write_record`, which takes the same lock again on the same thread. A
    plain `threading.Lock` deadlocks there, so the room's lock is reentrant.

    Run in a thread with a deadline, because the failure this pins is a hang rather than a raise:
    a suite that asserted it inline would stop instead of going red.
    """
    room = tmp_path / "konstantin-glm"

    def press():
        with room_lock(room):
            write_record(room, "output/.bia-runs/slaughter.json", {"who": "the press"}, 0)

    writer = threading.Thread(target=press, daemon=True)
    writer.start()
    writer.join(A_MOMENT)

    assert not writer.is_alive(), "a writer holding the room's lock deadlocked on its own write"
    assert read_record(room, "output/.bia-runs/slaughter.json")["who"] == "the press"


# ── One threshold, in one place ──────────────────────────────────────────────────────────────────
# From `tests/ui/walk/test_stage_4b_the_four_views.py` step 34 (ticket 16), last held at 602cc648,
# which ticket 165's last slice retired with that walk file. Read off the real tree.


def test_the_shrink_threshold_is_stated_in_the_store_and_nowhere_else():
    source = repo_root() / "src"
    holders = sorted(path.relative_to(source).as_posix() for path in source.rglob("*.py")
                     if not path.name.startswith("test_")
                     and "SHRINK_FACTOR" in path.read_text(encoding="utf-8"))
    assert holders == ["nemo/room_store.py"], f"step 34: the threshold is stated in {holders}"
    assert "SHRINK" not in (source / "nemo" / "views.py").read_text(encoding="utf-8"), (
        "step 34: `nemo.views` carries a threshold of its own, and two thresholds drift")
