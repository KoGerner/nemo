"""The method vocabulary's tests. Properties, because this module is four total functions.

The one that earns the module is `test_copying_the_method_changes_nothing_the_referee_reads`: the
walk copies the method onto the record parameter by parameter and the referee reads it back, and
those are the two sides that used to spell the names separately.
"""

from hypothesis import given
from hypothesis import strategies as st

from nemo.method import (
    INTOLERABILITY_THRESHOLD,
    PARAMETERS,
    RPO_VOCABULARY,
    SCENARIOS,
    SEVERITY_SCALE,
    TIME_HORIZONS,
    horizons,
    lenses,
    rpo_vocabulary,
    threshold,
)

LABELS = st.text(max_size=6)
#: A scenario as a method file has one, as something that is not one, and as one with no id.
SCENARIO = (st.fixed_dictionaries({"id": LABELS, "name": LABELS})
            | st.fixed_dictionaries({"name": LABELS})
            | st.none() | LABELS)

#: A method file: every parameter optional, because a room states what it states.
METHODS = st.fixed_dictionaries({}, optional={
    SCENARIOS: st.lists(SCENARIO, max_size=4),
    TIME_HORIZONS: st.lists(LABELS, max_size=4),
    SEVERITY_SCALE: st.lists(st.integers(min_value=1, max_value=5), max_size=5),
    INTOLERABILITY_THRESHOLD: st.integers(min_value=1, max_value=5),
    RPO_VOCABULARY: st.lists(LABELS, max_size=3),
    "org": LABELS,
    "author": LABELS,
})

ACCESSORS = (horizons, lenses, threshold, rpo_vocabulary)


def copied(method):
    """What `walk._method` carries onto the record, written out here rather than imported.

    Imported, this test would pass while both sides moved together. Written out, it is the second
    statement of the walk's rule, and the property below is what holds the two against each other.
    """
    return {name: method[name] for name in PARAMETERS if name in method}


# ── the reason this module is below both layers ──────────────────────────────


@given(METHODS)
def test_copying_the_method_changes_nothing_the_referee_reads(method):
    """Every parameter the referee reads is one the walk copies. The whole point of the module."""
    carried = copied(method)
    assert [accessor(carried) for accessor in ACCESSORS] == [
        accessor(method) for accessor in ACCESSORS]


@given(METHODS)
def test_the_copy_carries_no_key_the_room_did_not_state(method):
    """A parameter the file omits stays omitted; a key that is not a parameter is left behind."""
    carried = copied(method)
    assert set(carried) <= set(method)
    assert set(carried) <= set(PARAMETERS)
    assert all(carried[name] == method[name] for name in carried)


# ── the accessors invent nothing ─────────────────────────────────────────────


@given(METHODS)
def test_an_absent_parameter_is_never_filled_in(method):
    """An empty method judges nothing. It does not judge by our defaults."""
    stripped = {key: value for key, value in method.items() if key not in PARAMETERS}
    assert horizons(stripped) == []
    assert lenses(stripped) == []
    assert rpo_vocabulary(stripped) == []
    assert threshold(stripped) is None


@given(METHODS)
def test_the_horizons_are_the_method_s_own_in_the_method_s_order(method):
    """The order of the time bands is the method's meaning, so it is carried, never sorted."""
    assert horizons(method) == list(method.get(TIME_HORIZONS) or [])


@given(METHODS)
def test_every_lens_is_the_id_of_a_scenario_the_file_states(method):
    """No lens is derived, shortened or invented from a scenario's other keys."""
    stated = [s for s in method.get(SCENARIOS) or [] if isinstance(s, dict)]
    assert all(lens in [s.get("id") for s in stated] for lens in lenses(method))


@given(METHODS)
def test_a_scenario_without_an_id_is_not_a_lens(method):
    """A scenario the file did not name cannot be a row of the grid, so it is not offered as one."""
    unnamed = [s for s in method.get(SCENARIOS) or []
               if not (isinstance(s, dict) and s.get("id"))]
    assert len(lenses(method)) == len(method.get(SCENARIOS) or []) - len(unnamed)


@given(METHODS)
def test_the_threshold_is_handed_back_exactly_as_the_file_states_it(method):
    """A comparison against a rounded or coerced threshold is a different method."""
    assert threshold(method) == method.get(INTOLERABILITY_THRESHOLD)


@given(METHODS)
def test_the_rpo_vocabulary_is_a_list_of_the_method_s_own_words(method):
    assert rpo_vocabulary(method) == list(method.get(RPO_VOCABULARY) or [])
