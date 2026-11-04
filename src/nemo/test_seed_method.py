"""The seed's method derives the MTPD its own records' grids give (ticket 136, ADR-0032 decision 6).

The method and three grids are fixtures in this repo, copied from the seed's build folder and the
records, so no test here reads the seed or the vault (12_nemo_check, amendment 2). The grids are
transcribed cell by cell: a blank cell is `"MISSING"`, the referee's own word for one.

The figure asserted is the **MTPD**, the first horizon the grid crosses at, never the RTO: the
records' RTO is the interview's judgement and does not follow from the grid (amendment 1).
"""

import json
from pathlib import Path

import pytest

from nemo import walk
from nemo.impact import crossing, is_score
from nemo.method import horizons, lenses
from nemo.referee import RTO_CHECK, review
from nemo.refusal import TARGET_OUTSIDE_MTPD

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "seed"
METHOD = json.loads((FIXTURES / "method.json").read_text(encoding="utf-8"))
GRIDS = json.loads((FIXTURES / "grids.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(("process", "mtpd", "reasons"), [
    ("order-picking", "168 h", ["operational"]),
    ("incident-and-problem-management", "24 h", ["operational"]),
    ("access-management", "2 h", ["financial", "operational"]),
])
def test_a_record_grid_derives_its_mtpd_under_the_seed_method(process, mtpd, reasons):
    """Order picking: operational low at 72 h, high at 168 h, all else none. Incident: operational
    high at 24 h. Access: financial very high and operational high at 2 h. The grid is said in the
    method's own categories and horizons, every one of them, or the referee refuses its shape."""
    grid = GRIDS[process]

    assert list(grid) == lenses(METHOD)
    assert all(list(row) == horizons(METHOD) for row in grid.values())
    assert crossing(grid, METHOD) == (mtpd, reasons)


def test_the_scale_has_five_levels_and_every_cell_is_on_it():
    """Very high is 5 (the owner's ruling at t136's stop). nemo checks a cell only against a hard
    1-5, never against the method's own scale, so the fixture checks it here."""
    levels = [step["level"] for step in METHOD["severity_scale"]]
    cells = [value for grid in GRIDS.values() for row in grid.values() for value in row.values()]

    assert levels == [1, 2, 3, 4, 5]
    assert METHOD["intolerability_threshold"] == 4
    assert all(value == "MISSING" or (is_score(value) and value in levels) for value in cells)


QUOTED = "07_Interviews/record.md"


def _record(process, recovery_target):
    """The fixture grid as a record, each scored category carrying a quote from one file."""
    grid = GRIDS[process]
    evidence = [{"type": "transcript_quote", "lens": lens, "quote": f"{lens} is scored",
                 "source_path": QUOTED}
                for lens, row in grid.items() if any(map(is_score, row.values()))]
    return {"activities": [{"id": process, "name": process, "impact_grid": grid,
                            "evidence": evidence, "recovery_target": recovery_target}]}


def _files(process):
    return {QUOTED: " ".join(f"{lens} is scored." for lens in GRIDS[process])}


@pytest.mark.parametrize("target", ["24 h", "72 h"])
def test_an_rto_at_or_past_the_mtpd_is_refused_under_the_seed_method(target):
    """The seed method has no rto_map (t139, 13_nemo_check's ruling (1)): no RTO is derived, and
    the guard is the referee's. Incident and problem management derives 24 h; an RTO of 24 h or
    more is not strictly inside it and is refused."""
    assert "rto_map" not in METHOD
    verdict = review(_record("incident-and-problem-management", target), METHOD,
                     _files("incident-and-problem-management"))

    assert [r.kind for r in verdict.rejections] == [TARGET_OUTSIDE_MTPD], verdict.rejections


def test_an_rto_strictly_inside_the_mtpd_passes_under_the_seed_method():
    verdict = review(_record("incident-and-problem-management", "8 h"), METHOD,
                     _files("incident-and-problem-management"))

    assert verdict.passed, verdict.rejections
    assert RTO_CHECK in verdict.checked


def test_the_walk_carries_the_seed_method_s_beyond_word_to_the_referee(tmp_path):
    """The referee judges under the run's copy of the method (`walk._method`), so the copy keeps
    `beyond_horizons`; a method that states none (the old seed's) copies none."""
    (tmp_path / "02_BCM-Method").mkdir()
    (tmp_path / "02_BCM-Method" / "method.json").write_text(json.dumps(METHOD), encoding="utf-8")
    assert walk._method(tmp_path)["beyond_horizons"] == METHOD["beyond_horizons"] == ">168 h"

    old = {key: value for key, value in METHOD.items() if key != "beyond_horizons"}
    (tmp_path / "02_BCM-Method" / "method.json").write_text(json.dumps(old), encoding="utf-8")
    assert "beyond_horizons" not in walk._method(tmp_path)


def test_a_beyond_record_that_never_crosses_is_no_finding_and_helpdesk_s_is_one():
    """Under the seed method: ">168 h" over a grid that never reaches 4 agrees; over a grid that
    crosses at 24 h it is the one MTPD finding, the ">" shown."""
    quiet = {lens: dict.fromkeys(horizons(METHOD), 1) for lens in lenses(METHOD)}
    record = {"activities": [{"id": "time-recording", "impact_grid": quiet, "mtpd": ">168 h",
                              "recovery_target": ">168 h"}]}
    assert review(record, METHOD).findings == []

    helpdesk = _record("incident-and-problem-management", "8 h")
    helpdesk["activities"][0]["mtpd"] = ">168 h"
    findings = review(helpdesk, METHOD, _files("incident-and-problem-management")).findings
    assert [f for f in findings if "MTPD" in f] == [
        "Gap: activity incident-and-problem-management: the grid derives an MTPD of '24 h', not "
        "the asserted '>168 h' — the MTPD comes from the grid, so the assertion is the thing to "
        "explain or withdraw"]
