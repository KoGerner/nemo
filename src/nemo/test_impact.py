"""The impact grid's derivation, as properties of an arbitrary grid rather than of one example.

`nemo.impact` is the module the referee and the views both derive the MTPD from, so a defect here
reaches the record *and* the four documents at once, saying the same wrong figure in both — which
is worse than v1's three different figures, because nothing would look odd. The grid-shaped
properties the referee already rests on are in `test_referee.py` and still read as properties of
the figure it puts on a record; what is here is what the *module* promises to both its callers:
what counts as a score, what canonicalizing may and may not do, and that a crossing never names a
figure without naming its reason.
"""

from hypothesis import given
from hypothesis import strategies as st

from nemo.impact import (
    NO_MTPD,
    canonicalize_grid,
    crossing,
    derive_mtpd,
    is_score,
    unrated_bands,
    worst_case_row,
)

HORIZONS = ["0–4 h", "8 h", "24 h", "48 h"]
LENSES = ["financial", "legal-regulatory", "reputation"]
METHOD = {
    "time_horizons": HORIZONS,
    "scenarios": [{"id": lens} for lens in LENSES],
    "intolerability_threshold": 4,
}

#: A cell as a record may hold one: a score, the word for a cell nobody scored, and the shapes a
#: hand-edited record can put there instead.
CELLS = st.integers(min_value=1, max_value=5) | st.just("MISSING") | st.none() | st.text(max_size=3)

#: Horizons and lenses spelled the method's way, spelled a word processor's way, and spelled a way
#: the method never heard of — which is what canonicalizing exists to tell apart.
TYPOGRAPHY = st.sampled_from([*HORIZONS, "0-4 h", "0–4 H", " 8 h ", "**24 h**", "next tuesday"])
LENS_SPELLINGS = st.sampled_from([*LENSES, "Financial", "*reputation*", "animal-welfare"])

GRIDS = st.dictionaries(
    LENS_SPELLINGS,
    st.dictionaries(TYPOGRAPHY, CELLS, max_size=5),
    max_size=4,
)


# ── what counts as a score ───────────────────────────────────────────────────


#: Integers around the scale and integers from anywhere. The narrow band is not decoration: the
#: suite is derandomized (`conftest.py`), and a bare `st.integers()` draws 0 and then numbers far
#: from the scale — it never offers a 6, so it cannot tell `<= 5` from `<= 6`, which is the one
#: mutation of this line that matters.
SCALE_AND_BEYOND = st.integers(min_value=-2, max_value=9) | st.integers()


@given(SCALE_AND_BEYOND)
def test_a_score_is_an_integer_the_method_s_scale_actually_runs_to(value: int) -> None:
    """1 to 5, the scale `severity_scale` states. A 0 and a 6 are not scores off the end of it."""
    assert is_score(value) == (1 <= value <= 5)


@given(st.booleans())
def test_a_boolean_is_not_a_score_although_python_would_let_it_be_one(value: bool) -> None:
    """`True == 1` in Python, and a grid cell holding `true` is a record defect, not a 1."""
    assert not is_score(value)


@given(st.text() | st.none() | st.floats() | st.lists(st.integers()) | st.dictionaries(
    st.text(max_size=2), st.integers()))
def test_nothing_that_is_not_an_integer_is_a_score(value: object) -> None:
    """`"MISSING"`, `None` and a 4.0 included: a cell is judged as a score or it is not judged."""
    assert not is_score(value)


# ── canonicalizing ───────────────────────────────────────────────────────────


@given(GRIDS)
def test_canonicalizing_a_grid_twice_is_canonicalizing_it_once(grid: dict) -> None:
    """Otherwise the referee and the views, canonicalizing at different depths, see two grids."""
    once = canonicalize_grid(grid, METHOD)

    assert canonicalize_grid(once, METHOD) == once


@given(GRIDS)
def test_canonicalizing_never_invents_a_label_neither_the_grid_nor_the_method_said(
        grid: dict) -> None:
    """Typography may be forgiven into the method's own spelling; nothing else may appear."""
    lenses = set(grid) | set(LENSES)
    horizons = {key for row in grid.values() for key in row} | set(HORIZONS)
    for lens, row in canonicalize_grid(grid, METHOD).items():
        assert lens in lenses
        assert set(row) <= horizons


@given(GRIDS)
def test_canonicalizing_never_changes_a_score_it_only_changes_where_it_is_filed(
        grid: dict) -> None:
    """A normalizer that touched a value would be a grid rewritten rather than a grid read."""
    said = [value for row in canonicalize_grid(grid, METHOD).values() for value in row.values()]
    held = [value for row in grid.values() for value in row.values()]

    assert all(value in held for value in said)


# ── the crossing ─────────────────────────────────────────────────────────────


@given(GRIDS)
def test_a_crossing_names_a_reason_exactly_when_it_names_a_figure(grid: dict) -> None:
    """Stage 4 says the reason before the figure, so a figure with no reason has nothing to say.

    The other way round matters as much: a grid that reaches nothing crosses nowhere and must name
    nobody, rather than listing the categories that came closest as though they had crossed.
    """
    horizon, lenses = crossing(grid, METHOD)

    assert (horizon == NO_MTPD) == (lenses == [])


@given(GRIDS)
def test_every_category_a_crossing_names_actually_reaches_the_threshold_there(grid: dict) -> None:
    canonical = canonicalize_grid(grid, METHOD)
    horizon, lenses = crossing(grid, METHOD)

    for lens in lenses:
        assert canonical[lens][horizon] >= METHOD["intolerability_threshold"]


@given(GRIDS)
def test_a_crossing_is_a_horizon_the_method_names_or_it_is_no_figure_at_all(grid: dict) -> None:
    """Never a band the grid invented: an MTPD outside the method is an MTPD nobody can act on."""
    horizon, _ = crossing(grid, METHOD)

    assert horizon in [*HORIZONS, NO_MTPD]


@given(GRIDS)
def test_the_crossing_is_the_derivation_the_referee_runs_and_not_a_second_one(grid: dict) -> None:
    """The one guarantee `nemo.impact` exists for: one derivation, so only ever one figure."""
    horizon, _ = crossing(grid, METHOD)

    assert horizon == derive_mtpd(worst_case_row(canonicalize_grid(grid, METHOD)), METHOD)


# ── ticket 376 (ADR-0050): a band the source left unrated in every category ──
def test_a_band_is_unrated_only_where_no_category_scored_it() -> None:
    grid = {"financial": {"0–4 h": "MISSING", "8 h": 2, "24 h": "MISSING", "48 h": 5},
            "legal": {"0–4 h": "MISSING", "8 h": "MISSING", "24 h": 1, "48 h": 5}}
    assert unrated_bands(grid, HORIZONS) == HORIZONS[:1]


def test_a_grid_with_no_category_leaves_no_band_unrated() -> None:
    assert unrated_bands({}, HORIZONS) == []
    assert unrated_bands({"financial": {}}, HORIZONS) == HORIZONS
