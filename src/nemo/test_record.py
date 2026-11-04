"""The fingerprint, as properties rather than as examples.

`fingerprint` is the whole of `nemo.record` and it is pure — a function of a record and of
nothing else — so what is worth pinning is not a digest anybody typed out but the four things
every caller leans on: it is always a SHA-256, it depends on the record's content and not on its
key order, it says two records are one only when they are, and it leaves the record alone.

Two examples close it, moved here from `nemo.graph`'s tests when ticket 243 took that module
out: the exact canonical bytes the digest is taken over, and a non-ASCII value kept apart from
its ASCII look-alike.

No floats in the strategies, deliberately. `float` in a record would put `nan` and `-0.0` into
the corpus of generated values, where JSON has no spelling for the first and two records that
compare equal can differ in the second — real questions about what a record may hold, and a
question for whoever first needs one, not something a digest test should answer by accident.
"""

import copy
import hashlib
import json

from hypothesis import given
from hypothesis import strategies as st

from nemo.record import fingerprint

HEX = set("0123456789abcdef")

_SCALARS = st.none() | st.booleans() | st.integers() | st.text(max_size=8)
_VALUES = st.recursive(
    _SCALARS,
    lambda children: st.lists(children, max_size=3)
    | st.dictionaries(st.text(max_size=6), children, max_size=3),
    max_leaves=6,
)
RECORDS = st.dictionaries(st.text(max_size=6), _VALUES, max_size=4)


@given(RECORDS)
def test_a_fingerprint_is_always_sixty_four_lowercase_hex_characters(record):
    """Whatever the record holds, the digest is the same shape — a receipt can rely on that."""
    taken = fingerprint(record)

    assert len(taken) == 64
    assert set(taken) <= HEX


@given(RECORDS)
def test_a_fingerprint_is_the_same_every_time_it_is_taken(record):
    """Nothing here reads the clock or the network, so the same record answers the same twice."""
    assert fingerprint(record) == fingerprint(record)


@given(RECORDS)
def test_a_fingerprint_ignores_the_order_the_keys_were_inserted_in(record):
    """Canonical bytes: two records that differ only in key order are one record."""
    reversed_record = dict(reversed(list(record.items())))

    assert fingerprint(reversed_record) == fingerprint(record)


@given(RECORDS, RECORDS)
def test_two_records_share_a_fingerprint_only_when_they_are_the_same_record(left, right):
    """The property the graph's stamp rests on: a changed record cannot keep its digest.

    Sameness is compared through `json` rather than with `==`, because Python reads `0 == False`
    as true while JSON spells `0` and `false` apart — and it is the JSON the digest is taken
    over, so JSON is the one that decides whether two records are one.
    """
    same_record = json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)

    assert (fingerprint(left) == fingerprint(right)) == same_record


@given(RECORDS)
def test_taking_a_fingerprint_does_not_touch_the_record(record):
    """Asking a record who it is must not edit it — the ask lane leans on exactly this."""
    before = copy.deepcopy(record)

    fingerprint(record)

    assert record == before


def test_a_fingerprint_is_taken_over_the_canonical_bytes():
    expected = hashlib.sha256(
        json.dumps({"a": "ä"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    assert fingerprint({"a": "ä"}) == expected


def test_a_non_ascii_value_is_kept_apart_from_its_ascii_look_alike():
    assert fingerprint({"company": "NH₃"}) != fingerprint({"company": "NH3"})
