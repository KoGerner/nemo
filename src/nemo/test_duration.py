"""The duration reader's properties, moved from `test_referee.py` with the code (ticket 218).

They are the same five properties, unchanged: what a duration reads as, the two nudges ADR-0030
decision 1 and 14_nemo_check's t130 follow-up put on '<', '>' and '≥', a band read at its lower
bound, and the order two durations keep through parsing. They sit here because the skin's
`same_figure` and `tighter` read this number too, and a change to it is a change to them.
"""

from hypothesis import given
from hypothesis import strategies as st

# Aliased to the name it had in the referee, so the five properties below are the same text they
# were there: each binds its expected value to `minutes`, which is now the function's own name.
from nemo.duration import minutes as _parse_dur
from nemo.duration import upper_edge, worst_case

UNITS = {"min": 1, "mins": 1, "minute": 1, "minutes": 1, "m": 1,
         "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
         "d": 1440, "day": 1440, "days": 1440, "week": 10080, "weeks": 10080}


@given(st.integers(min_value=1, max_value=999), st.sampled_from(sorted(UNITS)))
def test_a_duration_is_its_number_times_its_unit_however_it_is_spelled(number, unit):
    minutes = number * UNITS[unit]
    assert _parse_dur(f"{number} {unit}") == minutes
    assert _parse_dur(f"{number}{unit}") == minutes
    assert _parse_dur(f"  {number} {unit.upper()}  ") == minutes


@given(st.integers(min_value=1, max_value=999), st.sampled_from(sorted(UNITS)))
def test_under_a_duration_is_one_minute_less_than_it(number, unit):
    """ADR-0030 decision 1 (t130): "< 8 h" is just under 8 hours, so it fits inside an 8-hour limit.
    It used to read as 8 h itself and was refused against an MTPD of "8 h"."""
    minutes = number * UNITS[unit]
    assert _parse_dur(f"<{number} {unit}") == minutes - 1
    assert _parse_dur(f"< {number} {unit}") == minutes - 1


@given(st.integers(min_value=1, max_value=999), st.sampled_from(sorted(UNITS)))
def test_past_a_duration_is_one_minute_more_than_it_and_about_it_is_it(number, unit):
    """14_nemo_check's ruling (t130 follow-up): '>' and '≥' read one minute past N; '≈' and '~'
    (about N) and '≤' (at most N) read N itself."""
    minutes = number * UNITS[unit]
    for sign in (">", "≥", "> "):
        assert _parse_dur(f"{sign}{number} {unit}") == minutes + 1
    for sign in ("≈", "~", "≤", "~ "):
        assert _parse_dur(f"{sign}{number} {unit}") == minutes


@given(st.integers(min_value=1, max_value=999), st.integers(min_value=1, max_value=999),
       st.sampled_from(sorted(UNITS)), st.text(alphabet="abc ", max_size=8))
def test_a_band_is_read_at_its_lower_bound_and_a_trailing_note_is_ignored(low, high, unit, note):
    """The deadline is where the band starts, and the parenthesis the owner added is not data."""
    assert _parse_dur(f"{low}-{high} {unit}") == _parse_dur(f"{low} {unit}")
    assert _parse_dur(f"{low} {unit} ({note})") == _parse_dur(f"{low} {unit}")


@given(st.integers(min_value=1, max_value=500), st.integers(min_value=1, max_value=500),
       st.sampled_from(sorted(UNITS)))
def test_a_longer_outage_never_parses_as_a_shorter_one(low, high, unit):
    """An RTO is compared to an MTPD, so the order of two durations has to survive parsing."""
    left, right = sorted((low, high))
    assert _parse_dur(f"{left} {unit}") <= _parse_dur(f"{right} {unit}")


@given(st.integers(min_value=0, max_value=999), st.integers(min_value=1, max_value=999),
       st.sampled_from(sorted(UNITS)), st.sampled_from(["-", "–", "—", " - "]))
def test_a_band_s_upper_edge_is_its_second_figure_in_its_own_unit(low, high, unit, dash):
    """ADR-0039 (ticket 240): the referee holds a banded target at its upper edge, as t74 holds a
    band MTPD; a trailing note is not data, and anything not a band has no edge."""
    assert upper_edge(f"{low}{dash}{high} {unit.upper()} (stated)") == f"{high} {unit}"
    assert upper_edge(f"{high} {unit}") is None
    assert upper_edge(f"{low}-{high} fortnights") is None


@given(st.integers(min_value=0, max_value=999), st.integers(min_value=1, max_value=999),
       st.sampled_from(sorted(UNITS)))
def test_the_worst_case_of_a_band_is_its_upper_edge_and_of_anything_else_its_reading(low, high,
                                                                                       unit):
    """ADR-0039: the comparison holds a band at its upper edge; a plain value is read as written."""
    assert worst_case(f"{low}–{high} {unit}") == _parse_dur(f"{high} {unit}")
    assert worst_case(f"<{high} {unit}") == _parse_dur(f"<{high} {unit}")
    assert worst_case(None) is None
