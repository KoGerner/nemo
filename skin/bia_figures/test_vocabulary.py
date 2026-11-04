"""The method's words and the register's key, pinned where mutation testing cannot reach.

`mutmut` mutates function bodies only, so a module-level constant — the key a register entry
declares its recovery point under, the key the method lists its words under, the two marks the
floor stamps on a dependency — is invisible to it. These are caller-visible names: the package
reads a register and a method it did not build, so what it reads them by is part of the contract.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

from bia_figures.register import (
    RECOVERY_POINT,
    assets,
    is_asset,
    is_metadata,
    recovery_point_for,
)
from bia_figures.vocabulary import (
    RPO_VOCABULARY,
    duration_of,
    looseness,
    no_data_duration,
    words_by_duration,
)

#: The new seed (read only, frozen): its method and register are read, never retyped (ticket 190).
#: It sits on brain only, so a tree or a runner without it skips these cases rather than failing.
#: A gate reads its own seed copy (NEMO_SEED, as nemo.seed does): 250's landing showed that the
#: live path hides a seed change from the gate. 139 moved the seed here.
NEW_SEED = Path(os.environ.get("NEMO_SEED", "/home/user/work/nemo-playground/seed"))
new_seed_only = pytest.mark.skipif(not NEW_SEED.is_dir(), reason="the new seed is on brain only")


def new_seed_method() -> dict[str, list[str]]:
    """The new seed's method, as its `02_BCM-Method/method.json` writes it."""
    method: dict[str, list[str]] = json.loads(
        (NEW_SEED / "02_BCM-Method" / "method.json").read_text()
    )
    return method


METHOD = {
    "rpo_vocabulary": [
        "0 h (no loss)",
        "4 h (ERP order data)",
        "24 h (batch/traceability)",
        "n/a (physical)",
    ]
}


def test_a_register_entry_declares_its_recovery_point_under_the_key_rpo() -> None:
    assert RECOVERY_POINT == "rpo"
    assert recovery_point_for({"IT-ERP-01": {"rpo": "4 h"}}, "IT-ERP-01", activity=None) == "4 h"


def test_a_register_entry_is_read_by_id_not_by_position() -> None:
    register = {"KA-01": {"rpo": "n/a"}, "IT-ERP-01": {"rpo": "4 h"}}
    assert recovery_point_for(register, "IT-ERP-01", activity=None) == "4 h"
    assert recovery_point_for(register, "KA-01", activity=None) == "n/a"


def test_a_method_lists_its_words_under_the_key_rpo_vocabulary() -> None:
    assert RPO_VOCABULARY == "rpo_vocabulary"
    assert set(words_by_duration(METHOD)) == {"0 h", "4 h", "24 h", "n/a"}


def test_every_word_is_found_again_under_the_duration_it_begins_with() -> None:
    assert words_by_duration(METHOD)["4 h"] == "4 h (ERP order data)"


def test_a_word_without_an_explanation_still_stands_for_its_duration() -> None:
    assert duration_of("4 h") == "4 h"


def test_the_explanation_is_dropped_whatever_it_says() -> None:
    assert duration_of("24 h (batch/traceability)") == "24 h"


def test_the_no_data_value_loses_more_than_any_figure_the_method_allows() -> None:
    """It allows no data to be held, so nothing a register can declare is looser than it."""
    vocabulary = words_by_duration(METHOD)
    no_data = no_data_duration(vocabulary)
    assert no_data is not None
    assert looseness(no_data) == math.inf


def test_the_no_data_duration_is_the_one_the_method_reserves_for_it() -> None:
    assert no_data_duration(words_by_duration(METHOD)) == "n/a"


def test_a_duration_carrying_no_number_is_a_no_data_value_whatever_the_word() -> None:
    """The method names its own no-data value; the package reads the missing number, not `n/a`."""
    method = {"rpo_vocabulary": ["0 h (no loss)", "keine Daten (rein physisch)"]}
    assert no_data_duration(words_by_duration(method)) == "keine Daten"


def test_the_order_is_by_the_number_not_by_the_text_of_the_duration() -> None:
    """`4 h` sorts before `24 h` although `"24 h" < "4 h"` as text."""
    assert looseness("4 h") < looseness("24 h")


def test_an_asset_is_a_register_entry_that_declares_a_recovery_point() -> None:
    register = {"IT-ERP-01": {"rpo": "4 h"}, "synthetic": True, "note": {"name": "no rpo"}}
    assert is_asset(register, "IT-ERP-01")
    assert not is_asset(register, "synthetic")
    assert not is_asset(register, "note")


def test_an_id_the_register_does_not_hold_at_all_is_neither_asset_nor_metadata() -> None:
    register = {"IT-ERP-01": {"rpo": "4 h"}, "synthetic": True}
    assert not is_asset(register, "AN-SCHLACHT-01")
    assert not is_metadata(register, "AN-SCHLACHT-01")
    assert is_metadata(register, "synthetic")
    assert not is_metadata(register, "IT-ERP-01")


def test_the_assets_of_a_register_are_its_entries_with_a_recovery_point() -> None:
    register = {"synthetic": True, "IT-ERP-01": {"rpo": "4 h"}, "KA-01": {"rpo": "n/a"}}
    assert assets(register) == ["IT-ERP-01", "KA-01"]


# ── 190: the new seed's words are bounds, `<1 h` … `>168 h`, and they are ordered like figures ──


def test_a_bound_below_a_number_is_just_under_it() -> None:
    """`<24 h` loses less than 24 hours and more than 23: it sits between the two figures."""
    assert looseness("23 h") < looseness("<24 h") < looseness("24 h")


def test_a_bound_above_a_number_is_just_over_it() -> None:
    assert looseness("168 h") < looseness(">168 h") < looseness("169 h")


def test_a_bare_number_reads_exactly_as_the_number() -> None:
    assert looseness("24 h") == 24
    assert looseness("0 h") == 0


def test_a_bound_carrying_no_number_still_reads_as_no_figure() -> None:
    assert looseness("< h") == math.inf
    assert looseness("<n/a") == math.inf


@new_seed_only
def test_the_new_seeds_words_are_ordered_from_under_an_hour_to_over_a_week() -> None:
    words = new_seed_method()["rpo_vocabulary"]
    assert sorted(words, key=looseness) == ["<1 h", "<24 h", "<168 h", ">168 h"]
    assert len({looseness(word) for word in words}) == len(words)


@new_seed_only
def test_no_word_of_the_new_seed_reads_as_the_no_data_value() -> None:
    """`>168 h` is not no-data: both systems writing it hold data (the ticket's evidence)."""
    for word in new_seed_method()["rpo_vocabulary"]:
        assert looseness(duration_of(word)) != math.inf


def test_a_method_whose_every_word_carries_a_number_has_no_no_data_duration() -> None:
    """190 item 2: the owner's (a), "No RPO at all"; the old seed keeps `n/a` (above)."""
    assert no_data_duration(words_by_duration({"rpo_vocabulary": ["<1 h", "24 h"]})) is None


@new_seed_only
def test_the_new_seed_has_no_no_data_duration() -> None:
    assert no_data_duration(words_by_duration(new_seed_method())) is None
