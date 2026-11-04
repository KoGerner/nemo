"""Ticket 108: the next step, the one tap nemo draws under a free-chat answer.

`next_step(turn, room)` names the activity to offer: the one the turn touched, else none (ticket
252: no fallback). These tests hold its rules; the skin's tests hold the tap.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo.next_step import Activity, Turn, next_step, touched

REGISTER = "03_Dependencies/dependency-register.json"


def act(name: str, mtpd: str | None = "168 h", rto: str | None = "72 h", gap: bool = False,
        files: tuple[str, ...] = ()) -> Activity:
    return Activity(name=name, files=frozenset(files or (f"07_Interviews/{name}-interview.md",)),
                    mtpd=mtpd, rto=rto, gap=gap)


ROOM = (act("payroll", mtpd="168 h"),
        act("access-management", mtpd="2 h", rto="1 h"),
        act("helpdesk-and-support", mtpd="24 h", rto="8 h"),
        act("hr-service-ticketing", mtpd=">168 h", rto="168 h", gap=True))


def test_the_activity_the_turn_touched_wins_over_one_with_a_gap() -> None:
    turn = Turn(read=("07_Interviews/payroll-interview.md",))
    assert next_step(turn, ROOM) == "payroll"


def test_a_single_interview_read_picks_that_interview_s_activity() -> None:
    turn = Turn(read=("07_Interviews/helpdesk-and-support-interview.md",))
    assert next_step(turn, ROOM) == "helpdesk-and-support"


def test_two_touched_the_one_with_the_tighter_mtpd_wins() -> None:
    turn = Turn(read=("07_Interviews/payroll-interview.md",
                      "07_Interviews/helpdesk-and-support-interview.md"))
    assert next_step(turn, ROOM) == "helpdesk-and-support"
    assert next_step(Turn(read=tuple(reversed(turn.read))), ROOM) == "helpdesk-and-support"


def test_two_touched_with_the_same_mtpd_the_room_order_decides() -> None:
    room = (act("b", mtpd="24 h"), act("a", mtpd="24 h"))
    turn = Turn(read=("07_Interviews/a-interview.md", "07_Interviews/b-interview.md"))
    assert next_step(turn, room) == "b"


def test_a_touched_activity_without_a_readable_mtpd_comes_after_one_with_it() -> None:
    room = (act("a", mtpd=None), act("b", mtpd="no MTPD within horizons"), act("c", mtpd="72 h"))
    turn = Turn(read=tuple(f"07_Interviews/{n}-interview.md" for n in "abc"))
    assert next_step(turn, room) == "c"


def test_an_activity_named_by_the_turn_is_touched() -> None:
    assert next_step(Turn(named=("payroll",)), ROOM) == "payroll"


def test_a_name_the_room_does_not_hold_touches_nothing() -> None:
    """Ruling D: the tap never names an activity the room does not hold."""
    assert next_step(Turn(named=("Slaughter",)), ROOM) is None


def test_a_file_read_under_the_activity_s_own_folder_touches_it() -> None:
    room = (act("a", files=("output/a/",)), act("b", mtpd="1 h"))
    assert next_step(Turn(read=("output/a/bia-analysis.md",)), room) == "a"


def test_a_file_entry_names_that_one_file_unless_it_ends_in_a_slash() -> None:
    """`Activity.files`: "A path ending in '/' holds every file under it." Any other entry is
    one file's own path, so a longer path that merely starts with it is somebody else's."""
    room = (act("a"), act("b", mtpd="1 h"))
    assert touched(Turn(read=("07_Interviews/a-interview.md.bak",)), room) == []
    assert [x.name for x in touched(Turn(read=("07_Interviews/a-interview.md",)), room)] == ["a"]


def test_t252_a_turn_that_touched_nothing_offers_nothing() -> None:
    """Ticket 252: no fallback. Before it, this turn was offered the room's most urgent activity
    (hr-service-ticketing here, access-management on the phone's room)."""
    assert next_step(Turn(), ROOM) is None


@pytest.mark.parametrize("read", [(REGISTER, "01_Organisation/process-map.md"),
                                  ("02_BCM-Method/method.json",)])
def test_t252_a_room_wide_read_offers_nothing(read: tuple[str, ...]) -> None:
    assert next_step(Turn(read=read), ROOM) is None


def test_an_empty_room_has_no_next_step() -> None:
    assert next_step(Turn(), ()) is None
    assert next_step(Turn(read=(REGISTER,), named=("payroll",)), ()) is None


def test_touched_keeps_the_room_s_order_and_each_activity_once() -> None:
    turn = Turn(read=("07_Interviews/payroll-interview.md",) * 2,
                named=("access-management", "payroll"))
    assert [a.name for a in touched(turn, ROOM)] == ["payroll", "access-management"]


def test_it_reaches_neither_the_disk_the_clock_nor_the_network(seal: Callable[[], None]) -> None:
    seal()
    assert next_step(Turn(read=("07_Interviews/payroll-interview.md",)), ROOM) == "payroll"


NAMES = st.lists(st.sampled_from("abcdefgh"), min_size=1, max_size=6, unique=True)
FIGURES = st.sampled_from([None, "30 min", "1 h", "4 h", "8 h", "24 h", "72 h", "168 h", ">168 h",
                           "no MTPD within horizons"])


@st.composite
def rooms(draw: st.DrawFn) -> tuple[Activity, ...]:
    return tuple(act(n, mtpd=draw(FIGURES), rto=draw(FIGURES), gap=draw(st.booleans()))
                 for n in draw(NAMES))


@given(rooms(), st.lists(st.sampled_from("abcdefghz"), max_size=4))
def test_the_next_step_is_always_an_activity_the_room_holds(
        room: tuple[Activity, ...], named: list[str]) -> None:
    """Ruling D over any room and any turn: never a name outside the room, and None exactly when
    the turn named none the room holds (ticket 252)."""
    chosen = next_step(Turn(named=tuple(named)), room)
    held = [n for n in named if n in {a.name for a in room}]
    if held:
        assert chosen in held
    else:
        assert chosen is None


@pytest.mark.parametrize("figure", ["", "  ", "soon"])
def test_an_unreadable_mtpd_is_never_the_tightest(figure: str) -> None:
    room = (act("vague", mtpd=figure), act("known", mtpd="168 h"))
    assert next_step(Turn(named=("vague", "known")), room) == "known"
