"""The method's own words for a recovery point, and the order over them.

The derivation needs these words to answer in them, and their order to find the tightest.

Each word begins with the duration it stands for, so `4 h (ERP order data)` stands for `4 h`. A
duration may be a bound rather than a figure (ticket 190, the new seed's `<1 h` … `>168 h`): `<24 h`
is just under 24 hours and `>168 h` just over 168, so a bound sorts between its number and the next.
The word whose duration carries no number is the method's no-data value: it allows no data to be
held, and therefore loses more of it than any figure. A method may have no such word (the new
seed has none): then an activity none of whose dependencies holds data has no RPO at all.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

Method = Mapping[str, Sequence[str]]

RPO_VOCABULARY = "rpo_vocabulary"


def duration_of(word: str) -> str:
    """The duration a vocabulary word stands for: `4 h (ERP order data)` stands for `4 h`."""
    return word.split("(")[0].strip()


#: How far a bound sits from its number: less than a whole hour, so `<24 h` stays above `23 h`.
BOUNDS = {"<": -0.5, ">": 0.5}


def looseness(duration: str) -> float:
    """How much data a recovery point allows to be lost; the no-data value allows none to hold."""
    number = duration.split()[0]
    bound = BOUNDS.get(number[0], 0)
    figure = number[1:] if bound else number
    return int(figure) + bound if figure.isdigit() else math.inf


def words_by_duration(method: Method) -> dict[str, str]:
    """The method's words for an RPO, each keyed by the duration it stands for."""
    return {duration_of(word): word for word in method[RPO_VOCABULARY]}


def no_data_duration(vocabulary: Mapping[str, str]) -> str | None:
    """The duration the method reserves for an entry that holds no data; None where it has none."""
    return next((duration for duration in vocabulary if looseness(duration) == math.inf), None)
