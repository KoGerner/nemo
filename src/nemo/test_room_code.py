"""What a room code is, and what a refusal about one carries. Both asked over generated text.

`mintable` is a pure function of one string, so it is the kind of thing a property says everything
about: the two tests below are the two halves of an *iff*, and between them they leave the function
no freedom. That matters more than it looks. The property this file inherited from `test_door.py`
was one-sided — it asserted where the rooms folder ends up *when* `mintable` says yes, and said
nothing at all when it says no — so a `mintable` that refused every code on earth passed it. A
half-property reads like a guarantee and is not one.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo.room_code import UNAUTHORISED, Refused, mintable

#: The alphabet a printed room code is drawn from, spelled out here rather than imported, so that
#: this file and `nemo.room_code` have to agree rather than being the same statement twice.
ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-"

#: A code of the shape the fifty QRs carry. The band is stated rather than left to the default:
#: the suite's Hypothesis profile is derandomised (see the root `conftest.py`), so a strategy that
#: does not say how short and how long gets a narrow sample of the same lengths on every run and
#: the boundary — a code of one character — may never be offered at all.
PRINTED = st.text(alphabet=ALPHABET, min_size=1, max_size=12)

#: Either side of an intruding character, and either may be empty: a code is refused for a bad
#: character at its start, in its middle and at its end alike.
EITHER_SIDE = st.text(alphabet=ALPHABET, max_size=6)

#: One character no printed code carries — anything at all outside the alphabet, rather than the
#: half-dozen separators and dots we would have thought to list.
OUTSIDE = st.characters().filter(lambda character: character not in ALPHABET)

#: Text that leans on the shapes an attacker reaches for first, plus arbitrary text behind them.
CRAFTED = (
    st.sampled_from(["../../scratch", "..", ".", "/", "", "/etc/passwd", "a/b", "\x00",
                     ".hidden", "..%2F..%2Fetc", "Adler-7YCYET"])
    | st.text()
)


@given(PRINTED)
def test_every_shape_a_printed_qr_can_carry_may_be_minted(code):
    """The half the old property left out: a code of the printed shape is always mintable.

    Without this, a `mintable` that said no to everything would satisfy every other property in
    this file — and a demo whose fifty scans all refuse is a demo that fails safe into failing.
    """
    assert mintable(code)


@given(EITHER_SIDE, OUTSIDE, EITHER_SIDE)
def test_one_character_from_outside_the_alphabet_is_enough_to_refuse_a_code(before, outsider,
                                                                           after):
    """And the other half: one character no QR carries refuses the code, wherever it sits.

    A separator, a dot leading a hidden name, a percent sign, a NUL, a newline past what `$` would
    have stopped at, a letter from another script — none of them are enumerated here, because the
    property is over every character outside the alphabet rather than over the ones we listed.
    """
    assert not mintable(before + outsider + after)


def test_a_code_with_nothing_in_it_may_not_be_minted():
    """The boundary the band above cannot reach from the other side: one character, not none.

    An empty code names the rooms folder itself, which `mint_room` would then copy the seed over.
    """
    assert not mintable("")


def test_the_codes_a_printed_qr_carries_may_be_minted():
    """The shapes ADR-0017's fifty QRs are printed with, and the ones this QA drives it with."""
    assert [code for code in ("adler-7ycyet", "buche-2kd91p", "qa-room-01", "demo-1")
            if not mintable(code)] == []


@given(CRAFTED)
def test_a_mintable_code_can_only_name_a_new_child_of_the_rooms_folder(tmp_path_factory, code):
    """Ticket 50 **creates** where ticket 22 only read, so the crafted shapes that were merely
    refused a folder have to be refused a `mkdir` as well — a traversal that reads nothing and
    writes a folder into `/etc` is the same defect the other way up.

    Whatever arrives, a code a door would mint for resolves to a child of the rooms folder and
    names neither that folder nor anything above it. `.` and `..` are the two one-segment codes
    that resolve somewhere other than a child, and `..%2F..%2Fetc` is the one this ticket's own
    scenario presents.
    """
    rooms = tmp_path_factory.mktemp("rooms")
    if mintable(code):
        assert (rooms / code).resolve().parent == rooms.resolve()
        assert (rooms / code).resolve() != rooms.resolve()


def test_a_refusal_says_one_thing_to_the_delegate_and_another_to_the_operator():
    """Two audiences, and a refusal that has only one sentence says it to both."""
    plain = Refused("the room 'demo-9' has no folder")
    assert plain.operator == str(plain)
    two = Refused("This room is not ready.", "the seed under /srv/seed names no department")
    assert str(two) == "This room is not ready." and two.operator != str(two)


@given(st.text(min_size=1), st.text())
def test_a_refusal_never_loses_either_sentence_it_was_given(delegate, operator):
    """Whatever the two are: the delegate reads what was raised, the journal reads `operator`.

    The one place the two meet is an operator line nobody wrote, which falls back to the
    delegate's sentence rather than to the empty string — a blank journal line is a refusal an
    operator cannot act on, and `or` is what makes the fallback rather than a default argument
    somebody remembers to pass.
    """
    refusal = Refused(delegate, operator)

    assert str(refusal) == delegate
    assert refusal.operator == (operator or delegate)
    assert refusal.operator, "no refusal reaches the journal as a blank line"


@given(st.text(min_size=1))
def test_every_refusal_is_the_status_the_http_layer_answers(delegate):
    """`status` is the class's, so it is on a refusal nobody gave one to — which is all of them."""
    assert Refused(delegate).status == UNAUTHORISED == 401


def test_a_refusal_is_an_exception_a_caller_can_catch_as_one():
    """The skin mints and then checks inside a single `except`; both sides raise this class."""
    with pytest.raises(Refused, match="no folder"):
        raise Refused("the room 'demo-9' has no folder")
