"""Properties of an arbitrary register and an arbitrary method, not of the one room.

The package holds no files, no clock and no network, so every function in it is a pure function of
data the caller passes in. That is what lets these be stated as properties: Hypothesis builds the
register and the method, and the claims below have to hold for all of them.
"""

from __future__ import annotations

from typing import Any

from hypothesis import assume, given
from hypothesis import strategies as st

from bia_figures.deps import FILES, PROPOSED, dependencies, floor
from bia_figures.impact import derive_rpo
from bia_figures.register import assets as assets_of
from bia_figures.register import is_asset, is_dependable, is_metadata, recovery_point_for
from bia_figures.vocabulary import (
    duration_of,
    looseness,
    no_data_duration,
    words_by_duration,
)

NO_DATA = "n/a"

ASSET_IDS = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", min_size=2, max_size=10)

# A register's own words about itself. Lowercase and underscores, so no metadata key a room draws
# can collide with an asset id: what these properties claim about the two kinds stays separable.
METADATA_KEYS = st.sampled_from(["synthetic", "walked_by", "version", "source_file", "notes"])

# What a register may carry beside its entries, including the boolean the first package died on and
# the mapping that looks like an entry until you ask it for a recovery point.
METADATA_VALUES = st.one_of(
    st.booleans(),
    st.integers(),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=12),
    st.lists(st.text(alphabet="abc", max_size=3), max_size=3),
    st.fixed_dictionaries({"name": st.text(alphabet="abc", max_size=5)}),
)


@st.composite
def rooms(
    draw: st.DrawFn,
    min_assets: int = 0,
    with_metadata: bool = False,
    mixed_forms: bool = False,
) -> dict[str, Any]:
    """A method, a register whose entries all speak the method's durations, and an activity.

    A real register carries a line about itself beside its assets, so a room may be drawn with
    metadata interleaved among the entries: `assets` names the ids that declare a recovery point
    and `metadata` the keys that do not.

    A real register also writes those recovery points in whichever form a colleague reached for. A
    room drawn with `mixed_forms` declares each entry either as the bare duration or as the
    method's whole word for it, so nothing below may assume the bare one. `declared` keeps the
    duration each entry stands for however it is written, and `words` the method's word for each
    duration.
    """
    numbers = draw(st.lists(st.integers(0, 999), min_size=1, max_size=5, unique=True))
    durations = [f"{number} h" for number in numbers] + [NO_DATA]
    words = {duration: f"{duration} ({duration} word)" for duration in durations}
    method = {"rpo_vocabulary": list(words.values())}
    assets = draw(st.lists(ASSET_IDS, min_size=min_assets, max_size=6, unique=True))
    declared = {asset: draw(st.sampled_from(durations)) for asset in assets}
    entries: dict[str, Any] = {}
    for asset, duration in declared.items():
        forms = [duration, words[duration]] if mixed_forms else [duration]
        entries[asset] = {"name": asset, "rpo": draw(st.sampled_from(forms))}
    metadata: dict[str, Any] = (
        draw(st.dictionaries(METADATA_KEYS, METADATA_VALUES, max_size=4)) if with_metadata else {}
    )
    register = (
        dict(draw(st.permutations([*entries.items(), *metadata.items()])))
        if metadata
        else entries
    )
    dependency_ids = (
        draw(st.lists(st.sampled_from(assets), max_size=6)) if assets else []
    )
    return {
        "method": method,
        "register": register,
        "assets": assets,
        "metadata": metadata,
        "durations": durations,
        "declared": declared,
        "words": words,
        "dependencies": list(dict.fromkeys(dependency_ids)),
    }


def written_bare(register: dict[str, Any], declared: dict[str, str]) -> dict[str, Any]:
    """The same register with every entry's recovery point written as its bare duration.

    The twin a mixed-form register has to agree with: same room, one form, nothing else moved.
    """
    return {
        key: (dict(value) | {"rpo": declared[key]}) if key in declared else value
        for key, value in register.items()
    }


# --- the register ---------------------------------------------------------------------------


@given(room=rooms(with_metadata=True))
def test_every_key_the_register_holds_is_dependable_or_metadata_and_never_both(
    room: dict[str, Any],
) -> None:
    """The one rule the three layers rest on, stated of every key an arbitrary register holds;
    every asset is dependable (ticket 184)."""
    register = room["register"]
    for key in register:
        assert is_dependable(register, key) != is_metadata(register, key)
        assert not is_asset(register, key) or is_dependable(register, key)


@given(room=rooms(with_metadata=True), stranger=ASSET_IDS)
def test_an_id_the_register_does_not_hold_is_neither_an_asset_nor_metadata(
    room: dict[str, Any], stranger: str
) -> None:
    register = room["register"]
    assume(stranger not in register)
    assert not is_asset(register, stranger)
    assert not is_metadata(register, stranger)


@given(room=rooms(with_metadata=True))
def test_the_assets_are_the_entries_declaring_a_recovery_point_in_register_order(
    room: dict[str, Any],
) -> None:
    register = room["register"]
    assert assets_of(register) == [key for key in register if is_asset(register, key)]
    assert set(assets_of(register)) == set(room["assets"])


@given(room=rooms(with_metadata=True))
def test_every_asset_answers_when_asked_for_its_recovery_point(room: dict[str, Any]) -> None:
    """What a metadata key does not do, and why only assets are ever asked."""
    register = room["register"]
    for asset in assets_of(register):
        assert recovery_point_for(register, asset, activity=None) == register[asset]["rpo"]
    for key in room["metadata"]:
        assert key not in assets_of(register)


# --- the floor ------------------------------------------------------------------------------


@given(room=rooms(), proposed=st.lists(ASSET_IDS, max_size=6, unique=True))
def test_every_id_an_interview_names_survives_whatever_the_model_proposed(
    room: dict[str, Any], proposed: list[str]
) -> None:
    """A model may add ids the interviews do not name; it may never remove one they do."""
    register, named = room["register"], room["dependencies"]
    interview = "Wir haben " + ", ".join(named) + " im Einsatz."
    result = dependencies(register, [interview], proposed)
    for asset in named:
        assert result[asset] == FILES


@given(room=rooms(), proposed=st.lists(ASSET_IDS, max_size=6, unique=True))
def test_a_proposal_can_only_add_and_is_marked_as_a_proposal(
    room: dict[str, Any], proposed: list[str]
) -> None:
    register, named = room["register"], room["dependencies"]
    interview = "Wir haben " + ", ".join(named) + " im Einsatz."
    with_proposal = dependencies(register, [interview], proposed)
    without = dependencies(register, [interview], [])
    assert set(without) <= set(with_proposal)
    assert set(with_proposal) == set(without) | set(proposed)
    for asset in set(proposed) - set(without):
        assert with_proposal[asset] == PROPOSED


@given(room=rooms(), noise=st.text(max_size=40))
def test_the_floor_never_invents_an_id_the_register_does_not_hold(
    room: dict[str, Any], noise: str
) -> None:
    assert floor(room["register"], [noise]) <= set(room["register"])


@given(room=rooms())
def test_a_longer_token_beginning_with_an_id_never_names_it(room: dict[str, Any]) -> None:
    register = room["register"]
    longer = [f"{asset}99" for asset in register]
    assume(not set(longer) & set(register))
    assert floor(register, [" ".join(longer)]) == set()


@given(room=rooms())
def test_the_consumer_list_changes_nothing(room: dict[str, Any]) -> None:
    """The register's own consumers are known to be incomplete, so they are never consulted."""
    register = room["register"]
    interview = "Wir haben " + ", ".join(room["dependencies"]) + " im Einsatz."
    listed = {
        asset: dict(entry) | {"consumers": "schlachtung"} for asset, entry in register.items()
    }
    assert dependencies(listed, [interview], []) == dependencies(register, [interview], [])


@given(room=rooms(with_metadata=True))
def test_a_word_the_register_holds_as_metadata_can_never_become_a_dependency(
    room: dict[str, Any],
) -> None:
    """Named by an interview and proposed by a model at once, and still not a dependency."""
    register, metadata = room["register"], room["metadata"]
    interview = "Das Zimmer fuehrt " + ", ".join(register) + "."
    result = dependencies(register, [interview], list(metadata))
    assert set(result) == set(room["assets"])
    for key in metadata:
        assert key not in result


@given(room=rooms(with_metadata=True), proposed=st.lists(ASSET_IDS, max_size=4, unique=True))
def test_an_id_the_register_does_not_hold_may_still_be_proposed(
    room: dict[str, Any], proposed: list[str]
) -> None:
    """A model proposes freely and a register is edited between cycles: this must not crash."""
    register = room["register"]
    result = dependencies(register, [], proposed)
    for stranger in (p for p in proposed if p not in register):
        assert result[stranger] == PROPOSED


# --- the vocabulary -------------------------------------------------------------------------


@given(room=rooms())
def test_a_word_is_found_again_under_the_duration_it_stands_for(room: dict[str, Any]) -> None:
    vocabulary = words_by_duration(room["method"])
    for word in room["method"]["rpo_vocabulary"]:
        assert vocabulary[duration_of(word)] == word


@given(room=rooms())
def test_the_no_data_duration_is_the_one_loosest_word(room: dict[str, Any]) -> None:
    vocabulary = words_by_duration(room["method"])
    no_data = no_data_duration(vocabulary)
    assert no_data == NO_DATA
    for duration in vocabulary:
        assert looseness(duration) <= looseness(no_data)


@given(first=st.integers(0, 999), second=st.integers(0, 999))
def test_looseness_follows_the_number_the_duration_carries(first: int, second: int) -> None:
    assert (first < second) == (looseness(f"{first} h") < looseness(f"{second} h"))


# --- the two written forms -------------------------------------------------------------------


@given(room=rooms())
def test_reading_a_duration_out_of_a_word_twice_reads_the_same_duration(
    room: dict[str, Any],
) -> None:
    """What lets a recovery point be read wherever it comes from: reading a bare one is a no-op."""
    for word in room["method"]["rpo_vocabulary"]:
        assert duration_of(duration_of(word)) == duration_of(word)


@given(room=rooms())
def test_a_word_and_the_bare_duration_it_stands_for_are_equally_loose(
    room: dict[str, Any],
) -> None:
    """`4 h` and `4 h (ERP order data)` are the same four hours, so neither loses more than the
    other."""
    for word in room["method"]["rpo_vocabulary"]:
        bare = duration_of(word)
        assert looseness(bare) == looseness(duration_of(word))


@given(room=rooms(mixed_forms=True, with_metadata=True))
def test_an_entry_writing_the_methods_whole_word_is_still_an_asset(room: dict[str, Any]) -> None:
    """Story 02's rule is unchanged: declaring a recovery point at all is what makes an asset,
    and the form it is written in has no say in it."""
    register = room["register"]
    assert set(assets_of(register)) == set(room["declared"])
    for key in room["metadata"]:
        assert is_metadata(register, key)


@given(room=rooms(mixed_forms=True, with_metadata=True))
def test_the_form_the_register_writes_in_changes_nothing_about_the_derivation(
    room: dict[str, Any],
) -> None:
    """The whole story, as a property: a register that mixes the two forms derives exactly what
    the same register written one way does — figure, reason, complaints and all."""
    bare = written_bare(room["register"], room["declared"])
    mixed = derive_rpo(room["dependencies"], room["register"], room["method"])
    assert mixed == derive_rpo(room["dependencies"], bare, room["method"])


@given(room=rooms(mixed_forms=True))
def test_a_recovery_point_written_as_the_methods_own_word_is_never_unmatched(
    room: dict[str, Any],
) -> None:
    """Thirteen physical entries writing the method's whole word used to be thirteen complaints."""
    derivation = derive_rpo(room["dependencies"], room["register"], room["method"])
    assert derivation.unmatched == ()
    assert derivation.figure in room["method"]["rpo_vocabulary"]


@given(room=rooms(min_assets=1, mixed_forms=True))
def test_dependencies_that_hold_no_data_either_way_derive_the_no_data_word_without_complaint(
    room: dict[str, Any],
) -> None:
    """An activity depending only on physical entries derives `n/a`, and is told of nothing."""
    physical = [asset for asset, duration in room["declared"].items() if duration == NO_DATA]
    assume(physical)
    derivation = derive_rpo(physical, room["register"], room["method"])
    assert derivation.figure == room["words"][NO_DATA]
    assert derivation.reason == ()
    assert derivation.unmatched == ()


@given(room=rooms(mixed_forms=True))
def test_the_figure_follows_the_tightest_duration_however_its_entry_wrote_it(
    room: dict[str, Any],
) -> None:
    """Durations are compared with durations: the one entry holding data sets the figure alone."""
    derivation = derive_rpo(room["dependencies"], room["register"], room["method"])
    holders = [a for a in room["dependencies"] if room["declared"][a] != NO_DATA]
    if not holders:
        assert derivation.figure == room["words"][NO_DATA]
        assert derivation.reason == ()
        return
    tightest = min((room["declared"][a] for a in holders), key=looseness)
    assert derivation.figure == room["words"][tightest]
    assert set(derivation.reason) == {a for a in holders if room["declared"][a] == tightest}


# --- the derivation -------------------------------------------------------------------------


@given(room=rooms())
def test_the_figure_is_always_one_of_the_methods_own_words(room: dict[str, Any]) -> None:
    derivation = derive_rpo(room["dependencies"], room["register"], room["method"])
    assert derivation.figure in room["method"]["rpo_vocabulary"]
    assert derivation.unmatched == ()


@given(room=rooms())
def test_the_reason_names_only_dependencies_and_all_that_tie(room: dict[str, Any]) -> None:
    register, dependency_ids = room["register"], room["dependencies"]
    derivation = derive_rpo(dependency_ids, register, room["method"])
    assert set(derivation.reason) <= set(dependency_ids)
    tightest = {recovery_point_for(register, asset, activity=None) for asset in derivation.reason}
    assert len(tightest) <= 1
    for asset in derivation.reason:
        for other in dependency_ids:
            point, other_point = (
                recovery_point_for(register, a, activity=None) for a in (asset, other)
            )
            assert looseness(duration_of(point)) <= looseness(duration_of(other_point))


@given(room=rooms())
def test_the_figure_is_the_word_for_the_tightest_data_holding_dependency(
    room: dict[str, Any],
) -> None:
    register, dependency_ids = room["register"], room["dependencies"]
    derivation = derive_rpo(dependency_ids, register, room["method"])
    holders = [
        asset
        for asset in dependency_ids
        if recovery_point_for(register, asset, activity=None) != NO_DATA
    ]
    if holders:
        tightest = min(
            (recovery_point_for(register, a, activity=None) for a in holders), key=looseness
        )
        assert duration_of(str(derivation.figure)) == tightest
        assert set(derivation.reason) == {
            a for a in holders if recovery_point_for(register, a, activity=None) == tightest
        }
    else:
        assert duration_of(str(derivation.figure)) == NO_DATA
        assert derivation.reason == ()


@given(room=rooms(), permutation=st.randoms(use_true_random=False))
def test_the_order_the_dependencies_arrive_in_changes_nothing(
    room: dict[str, Any], permutation: Any
) -> None:
    shuffled = list(room["dependencies"])
    permutation.shuffle(shuffled)
    first = derive_rpo(room["dependencies"], room["register"], room["method"])
    second = derive_rpo(shuffled, room["register"], room["method"])
    assert first.figure == second.figure
    assert set(first.reason) == set(second.reason)


@given(room=rooms(min_assets=1))
def test_a_dependency_holding_no_data_never_moves_the_figure(room: dict[str, Any]) -> None:
    register, method = room["register"], room["method"]
    physical = "KEIN-SYSTEM-01"
    assume(physical not in register)
    widened = dict(register) | {physical: {"name": physical, "rpo": NO_DATA}}
    before = derive_rpo(room["dependencies"], register, method)
    after = derive_rpo([*room["dependencies"], physical], widened, method)
    assert before == after


@given(room=rooms(min_assets=1), stranger=st.sampled_from(["12 h", "90 min", "unbekannt"]))
def test_a_recovery_point_the_method_has_no_word_for_derives_nothing(
    room: dict[str, Any], stranger: str
) -> None:
    register, method = room["register"], room["method"]
    assume(stranger not in room["durations"])
    odd = next(iter(register))
    strange = dict(register) | {odd: {"name": odd, "rpo": stranger}}
    derivation = derive_rpo([*room["dependencies"], odd], strange, method)
    assert derivation.figure is None
    assert (odd, stranger) in derivation.unmatched


@given(room=rooms(with_metadata=True))
def test_metadata_among_the_dependencies_moves_no_figure_and_is_named_back(
    room: dict[str, Any],
) -> None:
    register, method, ids = room["register"], room["method"], room["dependencies"]
    extra = list(room["metadata"])
    before = derive_rpo(ids, register, method)
    after = derive_rpo([*ids, *extra], register, method)
    assert (after.figure, after.reason) == (before.figure, before.reason)
    assert after.unrecognised == (*before.unrecognised, *extra)


@given(room=rooms(with_metadata=True), stranger=ASSET_IDS)
def test_an_id_the_register_does_not_hold_moves_no_figure_and_is_named_back(
    room: dict[str, Any], stranger: str
) -> None:
    register, method, ids = room["register"], room["method"], room["dependencies"]
    assume(stranger not in register)
    before = derive_rpo(ids, register, method)
    after = derive_rpo([*ids, stranger], register, method)
    assert (after.figure, after.reason) == (before.figure, before.reason)
    assert after.unrecognised == (*before.unrecognised, stranger)


@given(room=rooms(with_metadata=True), strangers=st.lists(ASSET_IDS, max_size=3, unique=True))
def test_unrecognised_names_every_dependency_that_is_not_an_asset_and_nothing_else(
    room: dict[str, Any], strangers: list[str]
) -> None:
    """Never silently treated as holding no data: silently is how the first wrong figure got
    signed."""
    register = room["register"]
    ids = [*room["dependencies"], *room["metadata"], *strangers]
    derivation = derive_rpo(ids, register, room["method"])
    assert set(derivation.unrecognised) == {i for i in ids if not is_asset(register, i)}
    assert derivation.figure is not None
