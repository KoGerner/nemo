"""What `nemo.seed` reports about a seed, and what it stays silent about.

The seed the demo mints from lives outside this repo, so the last test in this file is the one
that matters on 10 November: it asks `nemo.seed.problems` about the real directory. It **fails**
rather than skips when that directory is not there, for the reason `gate.sh`'s qa block gives
about `tests/isolation/` — a green that measured nothing is the failure this build is named after,
and a demo with no seed is not a demo.
"""

import json
from pathlib import Path

import pytest

from nemo.handover import CERTIFICATE
from nemo.interview import INTERVIEWS, OWNER_INTERVIEWS
from nemo.seed import (
    NOT_NEMOS_TO_OVERWRITE,
    SEED,
    WITHOUT_REVISION,
    problems,
)
from nemo.views import ANALYSIS, CAPTURE, SCOPE, WORKSHEET
from nemo.walk import NAMES_NOBODY, NOTHING_TO_PRESS, RUNS, record_file

RECORD = record_file("Slaughter")


def seed(tmp_path, departments=("Slaughter", "Cutting / Deboning")):
    """A seed that passes every one of nemo's own gates: transcripts that name somebody, and
    nothing under `output/` that nemo itself would have written."""
    folder = tmp_path / "demo-seed"
    (folder / INTERVIEWS).mkdir(parents=True)
    for index, department in enumerate(departments):
        wrote(folder / INTERVIEWS / f"26_08_0{index}_interview.md",
              f"---\ndepartment: {department}\n---\n\n# {department} interview\n")
    return folder


def wrote(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_seed_nemo_would_mint_from_has_no_problems(tmp_path):
    assert problems(seed(tmp_path)) == []


def test_a_transcript_that_names_no_department_is_reported(tmp_path):
    """Problem one of the three the demo seed had: the admission check, asked of the seed rather
    than of the delegate who scanned it."""
    folder = seed(tmp_path)
    wrote(folder / OWNER_INTERVIEWS / "vertrieb-interview-transcript.md", "Q: ...\nA: ...\n")

    assert problems(folder) == [
        NAMES_NOBODY.format(path=f"{OWNER_INTERVIEWS}/vertrieb-interview-transcript.md")]


def test_a_seed_with_nothing_to_press_is_reported(tmp_path):
    """The admission check's other voice, so the report is nemo's whole refusal and not half."""
    folder = seed(tmp_path, departments=())

    assert problems(folder) == [NOTHING_TO_PRESS]


def test_a_record_without_a_revision_is_reported(tmp_path):
    """Problem two: `walk.record_card` reads `saved["revision"]`, so a v1 record turns stage 4
    into a `KeyError` in front of the manager (tick log, 2026-09-17 18:21)."""
    folder = seed(tmp_path)
    wrote(folder / RECORD, json.dumps({"company": "Marschkamp", "activities": []}))

    assert problems(folder) == [WITHOUT_REVISION.format(path=RECORD)]


def test_a_run_file_without_a_revision_is_reported(tmp_path):
    """A run is read by the same `_revision`, so the walk it belongs to raises the same KeyError."""
    folder = seed(tmp_path)
    wrote(folder / RUNS / "slaughter.json", json.dumps({"process": "Slaughter", "stage": 1}))

    assert problems(folder) == [WITHOUT_REVISION.format(path=f"{RUNS}/slaughter.json")]


def test_a_record_that_is_not_an_object_at_all_is_reported_rather_than_raised(tmp_path):
    """A check that crashes on the file it exists to report is one an operator cannot use."""
    folder = seed(tmp_path)
    wrote(folder / RUNS / "slaughter.json", json.dumps(["not", "a", "record"]))

    assert problems(folder) == [WITHOUT_REVISION.format(path=f"{RUNS}/slaughter.json")]


def test_a_record_that_carries_its_revision_is_not_reported(tmp_path):
    folder = seed(tmp_path)
    wrote(folder / RUNS / "slaughter.json", json.dumps({"process": "Slaughter", "revision": 1}))

    assert problems(folder) == []


@pytest.mark.parametrize("name", [SCOPE, CAPTURE, ANALYSIS, WORKSHEET, CERTIFICATE])
def test_a_document_nemo_writes_itself_is_reported(tmp_path, name):
    """Problem three: `room_store.write_document` refuses a save that would lose more than half
    of what is on disk, so a v1 document sitting where nemo writes its own is a refused save with
    nothing overwritten — and ADR-0011 says a minted room holds no document a human reads as
    output in the first place."""
    folder = seed(tmp_path)
    wrote(folder / "output" / "slaughter" / name, "# a document v1 wrote\n" * 500)

    assert problems(folder) == [NOT_NEMOS_TO_OVERWRITE.format(path=f"output/slaughter/{name}")]


def test_a_file_under_output_that_nemo_never_writes_is_left_alone(tmp_path):
    """The room's second home for interviews lives under `output/` too (ADR-0002), and a v1 name
    nemo does not write is not a document any walk would collide with."""
    folder = seed(tmp_path)
    wrote(folder / OWNER_INTERVIEWS / "x-interview.md", "---\ndepartment: Slaughter\n---\n")
    wrote(folder / "output" / "slaughter" / "pp4-handoff.md", "# v1\n")

    assert problems(folder) == []


def test_every_problem_is_reported_at_once(tmp_path):
    """One scan, one list: an operator putting a seed right reads all of it rather than peeling
    the refusals off one at a time."""
    folder = seed(tmp_path)
    wrote(folder / OWNER_INTERVIEWS / "nobody.md", "Q: ...\n")
    wrote(folder / RECORD, json.dumps({"company": "Marschkamp"}))
    wrote(folder / "output" / "slaughter" / SCOPE, "# a document v1 wrote\n")

    assert problems(folder) == [
        NAMES_NOBODY.format(path=f"{OWNER_INTERVIEWS}/nobody.md"),
        WITHOUT_REVISION.format(path=RECORD),
        NOT_NEMOS_TO_OVERWRITE.format(path=f"output/slaughter/{SCOPE}"),
    ]


def test_the_seed_the_demo_mints_from_passes_every_one_of_nemos_own_gates():
    """Ticket 59's whole point, asked of the directory ticket 49 serves rather than of a fixture.

    Red rather than skipped when the seed is not there: `NEMO_SEED` names it for a box that keeps
    it somewhere else, and nothing else is a reason for this check to measure nothing.
    """
    assert Path(SEED).is_dir(), f"the demo seed is not at {SEED}; set NEMO_SEED if it moved"

    assert problems(Path(SEED)) == []
