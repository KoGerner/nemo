"""The referee's tests, ported from v1's `test_bia_referee.py` — the pure half.

What did not come across, and why: the save token, the HMAC-peppered finding tags and the
self-writing pp4_handoff merge are gate bookkeeping (ADR-0007), the dependency register belongs
to ticket 16, and the question/activity adapter is gone because nemo's record holds activities.
The two deliberate behaviour changes are the ones the story's scenarios name: an asserted MTPD
that the grid does not support is a finding rather than a refusal, and an RTO that is not
strictly inside its MTPD is a refusal rather than a finding (`CONTEXT.md`, *Referee*).
"""

import ast
import datetime
import json
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from nemo import referee
from nemo.evidence import standardise

# The grid derivation moved to `nemo.impact` when ticket 16 needed the same figure for the
# worksheet: the referee and the views both derive the MTPD, so it sits below both rather than in
# whichever of them happened to need it first. Aliased rather than renamed here, so the properties
# written against it still read as properties of the figure the referee puts on the record.
from nemo.impact import NO_MTPD, crossing, derive_mtpd
from nemo.impact import worst_case_row as _worst_case_row
from nemo.record import UNRATED_BAND_ACK
from nemo.referee import (
    BOUNDARY_CHECK,
    EVIDENCE_TYPES,
    GRID_CHECK,
    MTPD_CHECK,
    QUOTES_CHECK,
    RPO_CHECK,
    RTO_CHECK,
    Verdict,
    _review_rto,
    _same_horizon,
    _squash,
    review,
)

# Every way a record can be refused is a name in `nemo.refusal`, below the referee that raises
# one and the walk that words it for a manager. Neither writes the other's half.
from nemo.refusal import (
    BAND_UNSCORED,
    BOUNDARY,
    KINDS,
    MISSING_HORIZONS,
    NO_ACTIVITIES,
    TARGET_OUTSIDE_MTPD,
    UNRATED_BAND_NEEDS_OWNER,
    UNREADABLE_TARGET,
    Rejection,
)
from nemo.seed import SEED

# `_norm` moved to nemo.text as the public `norm` when ticket 09 needed the same normaliser for
# the card. Aliased rather than renamed here so the properties written against it still read as
# properties of the referee's comparison key, which is what they are.
from nemo.test_ask import repo_root
from nemo.text import found_in
from nemo.text import norm as _norm

HORIZONS = ["0–4 h", "8 h", "24 h", "48 h", "72 h", "1 week"]
LENSES = [
    "financial",
    "customer-delivery",
    "legal-regulatory",
    "reputation",
    "animal-welfare-food-safety",
    "people-safety",
    "environment",
]
METHOD = {
    "time_horizons": HORIZONS,
    "intolerability_threshold": 4,
    "scenarios": [{"id": lens} for lens in LENSES],
    "rpo_vocabulary": [
        "0 h (no loss)",
        "4 h (ERP order data)",
        "24 h (batch/traceability)",
        "n/a (physical)",
    ],
}
TRANSCRIPT_PATH = "07_Interviews/2026-06-01-ahlgrim-interview.md"
TRANSCRIPT = (
    "Interview with Ahlgrim (Slaughter).\n"
    "Ahlgrim: The line has to keep moving; if it stops we lose product fast.\n"
    "Ahlgrim: Realistically we can be back in about eight hours once power returns."
)
FILES = {TRANSCRIPT_PATH: TRANSCRIPT}


def full_grid(worst_row: dict) -> dict:
    """A complete seven-lens grid whose worst case equals `worst_row` (every other lens 1)."""
    grid = {lens: dict.fromkeys(HORIZONS, 1) for lens in LENSES}
    grid["financial"] = dict(worst_row)
    return grid


WORST = {"0–4 h": 1, "8 h": 2, "24 h": 4, "48 h": 5, "72 h": 5, "1 week": 5}


def valid_record() -> dict:
    return {
        "dept": "Slaughter",
        "plan": None,
        "comparison": [],
        "pp4_handoff": [],
        "activities": [
            {
                "id": "slaughter",
                "name": "Slaughter",
                "impact_grid": full_grid(WORST),
                "mtpd": "24 h",
                "rpo": "4 h (ERP order data)",
                "recovery_target": "8 h",
                "impact_summary": "the line stops and product is at risk",
                "evidence": [
                    {
                        "type": "transcript_quote",
                        "lens": "financial",
                        "quote": "The line has to keep moving",
                        "source_path": TRANSCRIPT_PATH,
                    }
                ],
            }
        ],
    }


def refereed(record: dict, method: dict = METHOD) -> Verdict:
    """One record put to the referee against the fixed method and the room's one readable file."""
    return review(record, method, FILES)


def rejections_text(record: dict) -> str:
    """Every rejection on one record, joined, so a test can look for one phrase among them."""
    return " ".join(refereed(record).rejections)


# ── the happy path ───────────────────────────────────────────────────────────
def test_a_valid_record_passes_with_nothing_to_report() -> None:
    verdict = refereed(valid_record())
    assert verdict.rejections == []
    assert verdict.findings == []
    assert verdict.passed is True


def test_a_verdict_with_a_rejection_has_not_passed() -> None:
    assert Verdict(rejections=[Rejection(NO_ACTIVITIES, "something")]).passed is False


# ── what a rejection is: parts, not a sentence for a manager (ticket 26) ─────


def test_a_rejection_carries_the_activity_the_category_and_the_bands_as_parts() -> None:
    """The story's own card: `impact_grid['legal-regulatory'] missing horizon(s): ['72 h']`."""
    record = valid_record()
    del grid_of(record)["legal-regulatory"]["72 h"]
    rejection, = [r for r in refereed(record).rejections if r.kind == MISSING_HORIZONS]

    assert rejection.parts == {"activity": "slaughter", "lens": "legal-regulatory",
                               "horizons": ("72 h",)}


def test_a_rejection_is_still_the_developers_line_it_always_was() -> None:
    """The string is for a log and for a test. What a manager reads is `nemo.walk`'s."""
    record = valid_record()
    del grid_of(record)["legal-regulatory"]["72 h"]
    rejection, = [r for r in refereed(record).rejections if r.kind == MISSING_HORIZONS]

    assert rejection == ("activity slaughter: impact_grid['legal-regulatory'] "
                         "missing horizon(s): ['72 h']")


def test_a_verdict_carrying_only_findings_still_passes() -> None:
    assert Verdict(findings=["Gap: something"]).passed is True


# ── scenario: MTPD is derived, never accepted ────────────────────────────────
def test_an_asserted_mtpd_the_grid_does_not_support_is_a_finding() -> None:
    record = valid_record()
    record["activities"][0]["mtpd"] = "1 week"
    verdict = refereed(record)
    assert verdict.passed is True
    assert any("'24 h'" in f and "1 week" in f for f in verdict.findings), verdict.findings


def test_the_derived_mtpd_is_the_earliest_horizon_at_the_threshold() -> None:
    assert derive_mtpd({"0–4 h": 1, "8 h": 4, "24 h": 5}, METHOD) == "8 h"


def test_a_grid_that_never_reaches_the_threshold_derives_no_mtpd() -> None:
    assert derive_mtpd({"0–4 h": 1, "8 h": 2, "24 h": 3}, METHOD) == NO_MTPD


def test_a_horizon_absent_from_the_worst_case_row_is_skipped() -> None:
    assert derive_mtpd({"1 week": 5}, METHOD) == "1 week"


def test_no_asserted_mtpd_is_no_finding_because_the_referee_derives_it() -> None:
    record = valid_record()
    del record["activities"][0]["mtpd"]
    assert refereed(record).findings == []


def test_mtpd_typography_is_tolerated() -> None:
    record = valid_record()
    record["activities"][0]["mtpd"] = "24h"
    assert refereed(record).findings == []


def test_mtpd_stated_in_another_unit_of_the_same_duration_is_tolerated() -> None:
    record = valid_record()
    record["activities"][0]["mtpd"] = "24 hours"
    assert refereed(record).findings == []


def test_an_unparseable_asserted_mtpd_of_a_different_label_is_a_finding() -> None:
    record = valid_record()
    record["activities"][0]["mtpd"] = "same day"
    assert refereed(record).findings, "an unmatched label cannot be the grid's MTPD"


def test_the_no_mtpd_verdict_matches_itself() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(dict.fromkeys(HORIZONS, 2))
    record["activities"][0]["mtpd"] = NO_MTPD
    assert refereed(record).findings == []


# ── the method's word past the last horizon (t139, F1) ───────────────────────
BEYOND = ">1 week"
BEYOND_METHOD = {**METHOD, "beyond_horizons": BEYOND}


def test_the_method_s_beyond_word_agrees_with_a_grid_that_never_crosses() -> None:
    """A >168 h record with no crossing: the owner said what the grid says. No finding."""
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(dict.fromkeys(HORIZONS, 2))
    record["activities"][0]["mtpd"] = BEYOND
    assert refereed(record, BEYOND_METHOD).findings == []


def test_the_beyond_word_against_a_grid_that_crosses_is_a_finding_that_shows_it_whole() -> None:
    """Helpdesk: the grid crosses at 24 h and the owner said past the last horizon."""
    record = valid_record()
    record["activities"][0]["mtpd"] = BEYOND
    finding, = refereed(record, BEYOND_METHOD).findings
    assert f"the grid derives an MTPD of '24 h', not the asserted '{BEYOND}'" in finding


def test_the_beyond_word_is_not_the_last_horizon_itself() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid({**dict.fromkeys(HORIZONS, 1), "1 week": 5})
    record["activities"][0]["mtpd"] = BEYOND
    assert refereed(record, BEYOND_METHOD).findings, "past 1 week is not 1 week"


def test_only_the_method_s_own_word_agrees_with_no_crossing() -> None:
    """Never a literal: a method that states no beyond word has no word that agrees with it."""
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(dict.fromkeys(HORIZONS, 2))
    record["activities"][0]["mtpd"] = BEYOND
    assert refereed(record).findings
    assert refereed(record, {**METHOD, "beyond_horizons": ">2 weeks"}).findings


def _recovery(target: str, mtpd_grid: dict, method: dict = BEYOND_METHOD) -> Verdict:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(mtpd_grid)
    record["activities"][0]["recovery_target"] = target
    del record["activities"][0]["mtpd"]
    return refereed(record, method)


QUIET = dict.fromkeys(HORIZONS, 2)


def test_an_rto_and_an_mtpd_both_beyond_the_horizons_is_neither_refused_nor_flagged() -> None:
    """The owner's ruling (t139 (c)): RTO the method's beyond word, grid never crossing."""
    verdict = _recovery(BEYOND, QUIET)
    assert (verdict.rejections, verdict.findings) == ([], [])


def test_an_rto_beyond_the_horizons_against_a_24_h_mtpd_is_still_refused() -> None:
    verdict = _recovery(BEYOND, WORST)
    assert [r.kind for r in verdict.rejections] == [TARGET_OUTSIDE_MTPD], verdict.rejections


def test_a_beyond_rto_is_judged_as_before_where_the_method_states_no_beyond_word() -> None:
    assert [r.kind for r in _recovery(BEYOND, WORST, METHOD).rejections] == [TARGET_OUTSIDE_MTPD]
    assert _recovery(BEYOND, QUIET, METHOD).rejections == []
    assert RTO_CHECK not in _recovery(BEYOND, QUIET, METHOD).checked


def test_an_rto_beyond_against_an_mtpd_of_the_same_beyond_word_is_neither_refused_nor_flagged():
    """The MTPD handed over as the method's beyond word rather than NO_MTPD: the same pair."""
    verdict = Verdict()
    _review_rto(verdict, "a", {"recovery_target": BEYOND}, BEYOND, BEYOND)
    assert (verdict.rejections, verdict.findings) == ([], [])
    old = Verdict()
    _review_rto(old, "a", {"recovery_target": BEYOND}, BEYOND, None)
    assert [r.kind for r in old.rejections] == [TARGET_OUTSIDE_MTPD], "no beyond word: as before"


def test_only_the_beyond_word_itself_wins_the_exception_over_a_grid_that_never_crosses() -> None:
    """The exception is for an RTO that *is* the method's beyond word (t139 (c)); an RTO of
    any other duration is judged as ever, and over a grid that never crosses there is no MTPD
    to hold it against, so the RTO check does not say it ran."""
    verdict = _recovery("8 h", QUIET)
    assert (verdict.rejections, verdict.findings) == ([], [])
    assert RTO_CHECK not in verdict.checked, "nothing was compared: the MTPD is not a duration"


def test_an_rto_that_reads_none_is_refused_where_the_method_states_no_beyond_word() -> None:
    """A method that states no beyond word has no exception to give, whatever the RTO says: an
    RTO nobody can parse is refused rather than waved past."""
    assert [r.kind for r in _recovery("none", QUIET, METHOD).rejections] == [UNREADABLE_TARGET]


# ── scenario: the worst case cannot improve with time ────────────────────────
def test_a_grid_whose_impact_falls_at_a_later_horizon_is_reported() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(
        {"0–4 h": 5, "8 h": 5, "24 h": 4, "48 h": 5, "72 h": 5, "1 week": 5}
    )
    record["activities"][0]["mtpd"] = "0–4 h"
    record["activities"][0]["recovery_gap_flagged"] = True
    verdict = refereed(record)
    assert verdict.passed is True, verdict.rejections
    assert any("improves with time" in f and "24 h" in f for f in verdict.findings)


def test_a_flat_worst_case_is_not_a_fall() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(dict.fromkeys(HORIZONS, 4))
    record["activities"][0]["mtpd"] = "0–4 h"
    assert refereed(record).findings == []


def test_the_worst_case_is_the_highest_lens_not_the_last_one() -> None:
    record = valid_record()
    grid = record["activities"][0]["impact_grid"]
    grid["environment"] = dict.fromkeys(HORIZONS, 5)
    record["activities"][0]["mtpd"] = "0–4 h"
    assert refereed(record).findings == []


def test_a_missing_cell_does_not_pull_the_worst_case_down() -> None:
    record = valid_record()
    grid = record["activities"][0]["impact_grid"]
    grid["environment"] = dict.fromkeys(HORIZONS, "MISSING")
    assert refereed(record).findings == []


# ── scenario: an RTO must be strictly inside its MTPD ────────────────────────
def test_an_rto_equal_to_its_mtpd_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "24 h"
    verdict = refereed(record)
    assert verdict.passed is False
    assert any("strictly inside" in r for r in verdict.rejections), verdict.rejections


def test_an_rto_beyond_its_mtpd_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "48 h"
    assert refereed(record).passed is False


def test_an_rto_gap_is_accepted_once_it_is_acknowledged() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "24 h"
    record["activities"][0]["recovery_gap_flagged"] = True
    assert refereed(record).passed is True


def test_an_rto_strictly_inside_its_mtpd_needs_no_acknowledgement() -> None:
    assert refereed(valid_record()).passed is True


def test_an_unparseable_rto_is_refused_with_an_example_of_the_shape() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "as soon as possible"
    verdict = refereed(record)
    assert any("parseable duration" in r and "8 h" in r for r in verdict.rejections)


def test_an_activity_with_no_rto_at_all_is_refused() -> None:
    record = valid_record()
    del record["activities"][0]["recovery_target"]
    assert any("no recovery_target" in r for r in refereed(record).rejections)


def test_an_empty_rto_string_is_the_same_as_none() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = ""
    assert any("no recovery_target" in r for r in refereed(record).rejections)


def test_an_rto_is_not_compared_against_a_grid_that_derives_no_mtpd() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(dict.fromkeys(HORIZONS, 2))
    record["activities"][0]["mtpd"] = NO_MTPD
    record["activities"][0]["recovery_target"] = "1 week"
    assert refereed(record).passed is True


def test_an_rto_beyond_the_record_s_mtpd_is_refused_when_the_grid_could_not_be_judged() -> None:
    """ADR-0030 decision 2 (t130; t75 "a signed record agrees with itself"): the target is held
    against the MTPD the record carries, grid or no grid. It used to be skipped here."""
    record = valid_record()
    del record["activities"][0]["impact_grid"]["environment"]
    record["activities"][0]["recovery_target"] = "1 week"
    rejections = refereed(record).rejections
    assert any("missing lens row" in r for r in rejections)
    assert [r.kind for r in rejections if r.kind == TARGET_OUTSIDE_MTPD] == [TARGET_OUTSIDE_MTPD]
    assert any("strictly inside the MTPD 24 h" in r for r in rejections), rejections


def test_an_rto_inside_the_record_s_mtpd_passes_when_the_grid_could_not_be_judged() -> None:
    record = valid_record()
    del record["activities"][0]["impact_grid"]["environment"]
    verdict = refereed(record)
    assert any("missing lens row" in r for r in verdict.rejections)
    assert not any(r.kind == TARGET_OUTSIDE_MTPD for r in verdict.rejections), verdict.rejections
    assert RTO_CHECK in verdict.checked


def test_the_rto_is_held_against_the_record_s_mtpd_not_the_grid_s() -> None:
    """The record carries 8 h, the grid derives 24 h: a 12 h target is outside what he signs."""
    record = valid_record()
    record["activities"][0]["mtpd"] = "8 h"
    record["activities"][0]["recovery_target"] = "12 h"
    assert [r.kind for r in refereed(record).rejections] == [TARGET_OUTSIDE_MTPD]


def test_a_target_of_168_h_is_inside_an_mtpd_past_168_h() -> None:
    """14_nemo_check's ruling (t130 follow-up): '>168 h' is past 168 h, so a 168 h target is inside
    it. It used to read as 168 h itself: a false gap (hr-service-ticketing on the new seed)."""
    assert _against("168 h", ">168 h") == []


def test_a_target_past_168_h_against_a_168_h_mtpd_is_refused() -> None:
    assert _against(">168 h", "168 h") == [TARGET_OUTSIDE_MTPD]


def test_a_target_past_168_h_against_an_mtpd_past_168_h_is_the_both_beyond_exception() -> None:
    verdict = Verdict()
    _review_rto(verdict, "a", {"recovery_target": ">168 h", "mtpd": ">168 h"}, ">168 h", ">168 h")
    assert (verdict.rejections, verdict.findings) == ([], [])


def _beyond_over(record_mtpd: str, grid: dict) -> Verdict:
    """A '>168 h' target on a record carrying `record_mtpd`, over a grid the method judges."""
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(grid)
    record["activities"][0]["mtpd"] = record_mtpd
    record["activities"][0]["recovery_target"] = ">168 h"
    return refereed(record, {**METHOD, "beyond_horizons": ">168 h"})


def test_the_both_beyond_exception_reads_the_mtpd_the_record_carries_not_the_grid_s() -> None:
    """ADR-0030 decision 2: the target is held against the MTPD the record carries, and the
    exception (t139 (c)) is part of that holding, so it reads the same MTPD. The method
    (impact-criteria.md:46-48): '>168 h' is the word for an MTPD no horizon reaches.

    Case 1, record '>168 h' over a grid crossing at 24 h: exempt from the refusal; the grid's
    disagreement is the asserted-MTPD finding, as for any MTPD the grid does not support.
    Case 2, record '>168 h' over a grid that never crosses: exempt, and nothing to find.
    Case 3, record '24 h' over a grid that never crosses: refused, held against the 24 h he signs.
    """
    crossing_at_24 = _beyond_over(">168 h", WORST)
    assert crossing_at_24.rejections == [], crossing_at_24.rejections
    assert [f for f in crossing_at_24.findings if "the grid derives an MTPD of '24 h'" in f]
    assert RTO_CHECK in crossing_at_24.checked
    quiet = _beyond_over(">168 h", QUIET)
    assert (quiet.rejections, quiet.findings) == ([], [])
    signed_24 = _beyond_over("24 h", QUIET)
    assert [r.kind for r in signed_24.rejections] == [TARGET_OUTSIDE_MTPD], signed_24.rejections


def _against(target: str, mtpd: str) -> list[str]:
    verdict = Verdict()
    _review_rto(verdict, "a", {"recovery_target": target, "mtpd": mtpd}, mtpd, None)
    return [r.kind for r in verdict.rejections]


def test_a_target_under_8_h_is_inside_an_8_h_mtpd() -> None:
    assert _against("< 8 h", "8 h") == []


def test_a_target_of_8_h_against_an_8_h_mtpd_is_refused() -> None:
    assert _against("8 h", "8 h") == [TARGET_OUTSIDE_MTPD]


def test_a_target_under_8_h_against_an_mtpd_under_8_h_is_refused() -> None:
    """12_nemo_check's amendment: a target no tighter than its limit is not inside it."""
    assert _against("< 8 h", "< 8 h") == [TARGET_OUTSIDE_MTPD]


def test_a_capture_line_qualifier_on_the_rto_is_ignored() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "8 h (stated on the line)"
    assert refereed(record).passed is True


def test_an_rto_band_whose_upper_edge_is_inside_the_mtpd_passes() -> None:
    """ADR-0039: a band is held at its upper edge; "8-12 hours" is inside the 24 h MTPD at 12 h."""
    record = valid_record()
    record["activities"][0]["recovery_target"] = "8-12 hours"
    assert refereed(record).passed is True


@pytest.mark.parametrize("target, refused", [("2-6 hours", True), ("2–4 h", True), ("2-3 h", False),
                                             ("3 h", False), ("4 h", True)])
def test_a_banded_target_is_held_against_the_mtpd_at_its_upper_edge(target: str,
                                                                    refused: bool) -> None:
    """ADR-0039 (ticket 240): a band is inside the MTPD only if its worst case is, by the same
    strict comparison as a plain value, so "2–4 h" against 4 h is refused like "4 h" is."""
    assert _against(target, "4 h") == ([TARGET_OUTSIDE_MTPD] if refused else [])


def test_an_rto_written_with_a_less_than_sign_is_parseable() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "< 8 h"
    assert refereed(record).passed is True


def test_an_rto_in_minutes_is_parseable() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "90 minutes"
    assert refereed(record).passed is True


def test_an_rto_in_days_is_compared_in_the_same_clock_as_hours() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "2 days"
    assert any("strictly inside" in r for r in refereed(record).rejections)


def test_an_rto_of_one_week_is_a_real_duration_not_an_unparseable_one() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "1 week"
    rejections = refereed(record).rejections
    assert any("strictly inside" in r for r in rejections), rejections
    assert not any("parseable" in r for r in rejections)


def test_an_rto_with_a_unit_the_method_does_not_know_is_unparseable() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "8 fortnights"
    assert any("parseable duration" in r for r in refereed(record).rejections)


# ── scenario: a quote must exist ─────────────────────────────────────────────
def test_a_quote_in_no_readable_file_in_the_room_fails_and_nothing_is_saved() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "we would be back within the hour"
    verdict = refereed(record)
    assert verdict.passed is False
    assert any("possible fabrication" in r for r in verdict.rejections), verdict.rejections


def test_a_quote_absent_from_the_transcript_it_cites_names_that_file() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "we would be back within the hour"
    rejections = rejections_text(record)
    assert TRANSCRIPT_PATH in rejections


def test_a_quote_present_in_another_file_still_fails_against_the_one_it_cites() -> None:
    record = valid_record()
    files = {TRANSCRIPT_PATH: TRANSCRIPT, "07_Interviews/other.md": "a different sentence"}
    record["activities"][0]["evidence"][0]["quote"] = "a different sentence"
    assert review(record, METHOD, files).passed is False


def test_a_quote_with_no_cited_file_is_sought_in_every_readable_file() -> None:
    record = valid_record()
    del record["activities"][0]["evidence"][0]["source_path"]
    assert refereed(record).passed is True


def test_a_quote_with_no_cited_file_and_no_match_anywhere_fails() -> None:
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    del evidence["source_path"]
    evidence["quote"] = "nobody said this"
    assert any("readable file in the room" in r for r in refereed(record).rejections)


# ── ticket 131: the file a quote names is where its words were found ─────────
SECOND_PATH = "07_Interviews/2026-08-20-ahlgrim-followup-interview.md"
SECOND = "Ahlgrim: Nobody on the line would call that a small stop."


def test_a_quote_recorded_with_the_second_interviews_path_passes_against_that_file() -> None:
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    evidence.update(quote="Nobody on the line would call that a small stop",
                    source_path=SECOND_PATH)
    assert review(record, METHOD, {**FILES, SECOND_PATH: SECOND}).passed is True


def test_a_quote_in_two_files_passes_with_the_first_cited_and_the_other_in_also_in() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["also_in"] = [SECOND_PATH]
    files = {TRANSCRIPT_PATH: TRANSCRIPT, SECOND_PATH: TRANSCRIPT}
    assert review(record, METHOD, files).passed is True


@given(st.text(max_size=12), st.lists(st.text(max_size=30), min_size=1, max_size=3))
def test_finding_the_file_and_checking_the_quote_are_one_comparison(quote, texts) -> None:
    """The amendment of ticket 131: where the record says the words were found and where the
    referee finds them never disagree, whatever the typography, because both ask `found_in`."""
    assume(_norm(quote))
    files = {f"07_Interviews/{n}.md": text for n, text in enumerate(texts)}
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    evidence["quote"] = quote
    del evidence["source_path"]
    fabricated = any("possible fabrication" in r for r in review(record, METHOD, files).rejections)
    assert fabricated == (found_in(quote, files) == [])
    for path in found_in(quote, files):
        evidence["source_path"] = path
        assert not any("possible fabrication" in r
                       for r in review(record, METHOD, files).rejections)


def test_a_quote_cannot_be_verified_when_the_room_holds_no_readable_file() -> None:
    verdict = review(valid_record(), METHOD, {})
    assert any("cannot be verified" in r for r in verdict.rejections), verdict.rejections


def test_a_stitched_quote_is_not_verbatim() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "The line has to keep moving ... eight hours"
    assert any("possible fabrication" in r for r in refereed(record).rejections)


def test_quote_typography_is_tolerated_without_weakening_contiguity() -> None:
    record = valid_record()
    files = {TRANSCRIPT_PATH: "Ahlgrim: the line’s  got to keep\nmoving"}
    record["activities"][0]["evidence"][0]["quote"] = "The line's got to keep moving"
    assert review(record, METHOD, files).passed is True


def test_markdown_emphasis_around_a_quote_is_not_part_of_the_words() -> None:
    record = valid_record()
    files = {TRANSCRIPT_PATH: "Ahlgrim: **The line has to keep moving**"}
    assert review(record, METHOD, files).passed is True


def test_a_relative_source_path_resolves_against_the_rooms_files() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["source_path"] = (
        "marschkamp/" + TRANSCRIPT_PATH
    )
    assert refereed(record).passed is True


def test_a_leading_slash_on_a_source_path_is_tolerated() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["source_path"] = "/" + TRANSCRIPT_PATH
    assert refereed(record).passed is True


def test_a_source_path_naming_no_file_in_the_room_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["source_path"] = "07_Interviews/nowhere.md"
    assert any("not found or ambiguous" in r for r in refereed(record).rejections)


def test_an_ambiguous_source_path_is_refused_rather_than_guessed() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["source_path"] = "notes.md"
    files = {"a/notes.md": TRANSCRIPT, "b/notes.md": TRANSCRIPT}
    verdict = review(record, METHOD, files)
    assert any("not found or ambiguous" in r for r in verdict.rejections)


def test_an_evidence_item_that_is_not_an_object_is_refused_not_a_crash() -> None:
    record = valid_record()
    record["activities"][0]["evidence"] = ["the line has to keep moving"]
    assert any("malformed evidence item" in r for r in refereed(record).rejections)


def test_a_lone_evidence_object_is_read_as_one_item_rather_than_skipped() -> None:
    record = valid_record()
    record["activities"][0]["evidence"] = record["activities"][0]["evidence"][0]
    assert refereed(record).passed is True


def test_an_unknown_evidence_type_is_refused_and_names_the_allowed_types() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["type"] = "hearsay"
    rejections = rejections_text(record)
    assert "unknown evidence type" in rejections and "transcript_quote" in rejections


def test_every_allowed_evidence_type_is_accepted() -> None:
    for allowed in ("transcript_quote", "prior_bia", "prior_cycle", "company_file"):
        record = valid_record()
        record["activities"][0]["evidence"][0]["type"] = allowed
        assert refereed(record).passed is True, allowed


def test_a_file_path_in_the_legacy_ref_field_gets_a_repair_hint() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0] = {
        "type": "transcript_quote",
        "lens": "financial",
        "ref": TRANSCRIPT_PATH,
    }
    assert any("a file path, not a quote" in r for r in refereed(record).rejections)


def test_the_legacy_ref_field_still_carries_a_quote() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0] = {
        "type": "transcript_quote",
        "lens": "financial",
        "ref": "The line has to keep moving",
    }
    assert refereed(record).passed is True


def test_an_empty_quote_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "   "
    assert any("quote is empty" in r for r in refereed(record).rejections)


def test_an_evidence_lens_that_is_not_a_method_scenario_id_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["lens"] = "supply-chain"
    rejections = rejections_text(record)
    assert "not a method scenario id" in rejections and "financial" in rejections


def test_an_evidence_item_with_no_lens_is_not_judged_on_one() -> None:
    record = valid_record()
    record["activities"][0]["evidence"].append(
        {"type": "transcript_quote", "quote": "once power returns", "source_path": TRANSCRIPT_PATH}
    )
    assert refereed(record).passed is True


# ── scenario: the analysis stops at the boundary ─────────────────────────────
def test_a_continuity_plan_in_the_record_is_refused() -> None:
    record = valid_record()
    record["plan"] = "1. declare an incident 2. call the team"
    verdict = refereed(record)
    assert verdict.passed is False
    assert any("PP4 boundary" in r for r in verdict.rejections), verdict.rejections


def test_a_chosen_recovery_solution_in_the_record_is_refused() -> None:
    record = valid_record()
    record["recovery_solution"] = "a warm standby line in Hall 2"
    assert any("PP4 boundary" in r for r in refereed(record).rejections)


def test_an_absent_plan_key_is_not_a_boundary_violation() -> None:
    record = valid_record()
    del record["plan"]
    assert refereed(record).passed is True


def test_plan_drafting_language_in_a_summary_is_a_finding_not_a_wall() -> None:
    record = valid_record()
    record["activities"][0]["impact_summary"] = "Immediate actions: stop the line"
    verdict = refereed(record)
    assert verdict.passed is True
    assert any("plan-drafting language" in f for f in verdict.findings)


def test_plan_drafting_language_in_a_handoff_item_is_a_finding() -> None:
    record = valid_record()
    record["pp4_handoff"] = ["Option: roles and responsibilities need deciding"]
    verdict = refereed(record)
    assert verdict.passed is True
    assert any("plan-drafting language" in f for f in verdict.findings)


def test_a_handoff_item_without_one_of_the_four_prefixes_is_refused() -> None:
    record = valid_record()
    record["pp4_handoff"] = ["the ERP restore is unclear"]
    assert any("must start with" in r for r in refereed(record).rejections)


def test_each_of_the_four_handoff_prefixes_is_accepted() -> None:
    for prefix in ("Gap:", "Option:", "Human decisions:", "Missing evidence:"):
        record = valid_record()
        record["pp4_handoff"] = [f"{prefix} the ERP restore is unclear"]
        assert refereed(record).passed is True, prefix


def test_a_handoff_item_that_is_not_a_string_is_a_clean_refusal() -> None:
    record = valid_record()
    record["pp4_handoff"] = [{"gap": "the ERP restore"}]
    assert any("must start with" in r for r in refereed(record).rejections)


# ── grid completeness ────────────────────────────────────────────────────────
def test_a_missing_lens_row_is_refused() -> None:
    record = valid_record()
    del record["activities"][0]["impact_grid"]["environment"]
    assert any("missing lens row" in r for r in refereed(record).rejections)


def test_a_missing_horizon_is_refused() -> None:
    record = valid_record()
    del record["activities"][0]["impact_grid"]["financial"]["48 h"]
    assert any("missing horizon" in r for r in refereed(record).rejections)


def test_an_unknown_horizon_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["financial"]["96 h"] = 5
    assert any("unknown horizon" in r for r in refereed(record).rejections)


def test_an_invented_lens_is_refused_and_the_valid_ids_are_named() -> None:
    record = valid_record()
    grid = record["activities"][0]["impact_grid"]
    grid["supply-chain"] = dict(grid["financial"])
    rejections = rejections_text(record)
    assert "not a method scenario id" in rejections and "people-safety" in rejections


def test_a_score_outside_one_to_five_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["financial"]["8 h"] = 6
    assert any("invalid score" in r for r in refereed(record).rejections)


def test_a_score_of_zero_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["financial"]["8 h"] = 0
    assert any("invalid score" in r for r in refereed(record).rejections)


def test_a_boolean_is_not_a_score() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["financial"]["8 h"] = True
    assert any("invalid score" in r for r in refereed(record).rejections)


def test_a_string_score_is_refused_unless_it_is_missing() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["financial"]["8 h"] = "2"
    assert any("invalid score" in r for r in refereed(record).rejections)


def test_missing_is_the_honest_state_for_one_cell() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["environment"]["8 h"] = "MISSING"
    assert refereed(record).passed is True


def test_a_lens_row_that_is_not_an_object_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["environment"] = 3
    assert any("must be an object" in r for r in refereed(record).rejections)


def test_a_grid_that_is_not_an_object_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = ["financial"]
    assert any("impact_grid must be an object" in r for r in refereed(record).rejections)


def test_an_activity_with_no_grid_at_all_is_refused() -> None:
    record = valid_record()
    del record["activities"][0]["impact_grid"]
    assert any("impact_grid must be an object" in r for r in refereed(record).rejections)


def test_a_horizon_no_lens_scored_cannot_derive_an_mtpd() -> None:
    record = valid_record()
    for row in record["activities"][0]["impact_grid"].values():
        row["48 h"] = "MISSING"
    rejections = rejections_text(record)
    assert "has no scored lens" in rejections and "48 h" in rejections


def test_horizon_typography_is_canonicalized_to_the_methods_own_label() -> None:
    record = valid_record()
    grid = record["activities"][0]["impact_grid"]
    for row in grid.values():
        row["0-4 h"] = row.pop("0–4 h")
    assert refereed(record).passed is True


def test_lens_typography_is_canonicalized_like_horizon_typography() -> None:
    record = valid_record()
    grid = record["activities"][0]["impact_grid"]
    grid["People-Safety"] = grid.pop("people-safety")
    assert refereed(record).passed is True


def test_a_collision_between_a_typo_and_its_canonical_lens_is_kept_not_merged() -> None:
    record = valid_record()
    grid = record["activities"][0]["impact_grid"]
    grid["People-Safety"] = dict.fromkeys(HORIZONS, 1)
    assert any("not a method scenario id" in r for r in refereed(record).rejections)


def test_a_collision_between_a_typo_and_its_canonical_horizon_is_kept() -> None:
    record = valid_record()
    row = record["activities"][0]["impact_grid"]["financial"]
    row["0-4 h"] = 1
    assert any("unknown horizon" in r for r in refereed(record).rejections)


# ── the lens that is scored but has no quote ─────────────────────────────────
def test_a_scored_lens_with_no_quote_tagged_to_it_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["customer-delivery"]["24 h"] = 3
    rejections = rejections_text(record)
    assert "customer-delivery" in rejections and "no evidence item carries lens" in rejections


def test_a_lens_at_baseline_needs_no_quote() -> None:
    assert refereed(valid_record()).passed is True


def test_a_lens_that_is_entirely_missing_needs_no_quote() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"]["environment"] = dict.fromkeys(HORIZONS, "MISSING")
    assert refereed(record).passed is True


def test_an_activity_with_no_evidence_key_at_all_is_still_judged_on_its_claims() -> None:
    record = valid_record()
    del record["activities"][0]["evidence"]
    assert any("no evidence item carries lens" in r for r in refereed(record).rejections)


# ── one quote under several scored lenses ────────────────────────────────────
def _two_scored_lenses(record: dict) -> dict:
    activity = record["activities"][0]
    activity["impact_grid"]["customer-delivery"] = dict(WORST)
    activity["evidence"].append(
        {
            "type": "transcript_quote",
            "lens": "customer-delivery",
            "quote": "The line has to keep moving",
            "source_path": TRANSCRIPT_PATH,
        }
    )
    return record


def test_one_quote_under_two_scored_lenses_is_a_finding_not_a_wall() -> None:
    verdict = refereed(_two_scored_lenses(valid_record()))
    assert verdict.passed is True
    assert any("the same quote is the evidence for" in f for f in verdict.findings)


def test_distinct_quotes_per_lens_raise_nothing() -> None:
    record = _two_scored_lenses(valid_record())
    record["activities"][0]["evidence"][1]["quote"] = "once power returns"
    assert refereed(record).findings == []


def test_a_quote_reused_on_an_unscored_lens_is_not_the_failure() -> None:
    record = valid_record()
    activity = record["activities"][0]
    activity["impact_grid"]["environment"] = dict.fromkeys(HORIZONS, "MISSING")
    activity["evidence"].append(
        {
            "type": "transcript_quote",
            "lens": "environment",
            "quote": "The line has to keep moving",
            "source_path": TRANSCRIPT_PATH,
        }
    )
    assert refereed(record).findings == []


def test_an_acknowledgement_naming_the_lenses_and_a_human_silences_it() -> None:
    record = _two_scored_lenses(valid_record())
    record["activities"][0]["shared_quote_ack"] = {
        "lenses": ["customer-delivery", "financial"],
        "approved_by": "Dr Reinhard Kettler",
    }
    assert refereed(record).findings == []


def test_an_acknowledgement_must_name_every_affected_lens() -> None:
    record = _two_scored_lenses(valid_record())
    record["activities"][0]["shared_quote_ack"] = {
        "lenses": ["financial"],
        "approved_by": "Dr Reinhard Kettler",
    }
    assert refereed(record).findings


def test_an_acknowledgement_supplied_without_a_name_is_refused() -> None:
    record = _two_scored_lenses(valid_record())
    record["activities"][0]["shared_quote_ack"] = {"lenses": ["financial", "customer-delivery"]}
    assert any("no approved_by" in r for r in refereed(record).rejections)


def test_a_bare_click_as_an_acknowledgement_is_refused() -> None:
    record = _two_scored_lenses(valid_record())
    record["activities"][0]["shared_quote_ack"] = True
    assert any("no approved_by" in r for r in refereed(record).rejections)


# ── the owner who gave no numbers ────────────────────────────────────────────
ACK = {
    "approved_by": "Dr Reinhard Kettler",
    "review_date": "2099-01-01",
    "reason": "The owner declined every figure and gave a reason for each.",
    "review_owner": "Uwe Templin",
    "next_question": "What discharge volume would breach the permit, at what duration?",
    "owner_informed": "Uwe Templin, read-back sent 2026-08-26",
}


def unscored_record() -> dict:
    record = valid_record()
    activity = record["activities"][0]
    activity["impact_grid"] = {lens: dict.fromkeys(HORIZONS, "MISSING") for lens in LENSES}
    activity["mtpd"] = NO_MTPD
    return record


def test_a_wholly_unscored_grid_without_an_acknowledgement_is_refused() -> None:
    rejections = rejections_text(unscored_record())
    assert "not_elicited_ack" in rejections and "approved_by" in rejections


def test_a_wholly_unscored_grid_passes_once_a_named_sponsor_accepts_it() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = ACK
    assert refereed(record).passed is True


def test_a_partly_scored_grid_cannot_buy_silence_with_the_acknowledgement() -> None:
    record = valid_record()
    for row in record["activities"][0]["impact_grid"].values():
        row["48 h"] = "MISSING"
    record["activities"][0]["not_elicited_ack"] = ACK
    assert any("has no scored lens" in r for r in refereed(record).rejections)


def test_the_acknowledgement_needs_a_reason_not_just_a_name() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "reason": ""}
    assert any('needs a "reason"' in r for r in refereed(record).rejections)


def test_the_acknowledgement_needs_a_sponsor() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "approved_by": ""}
    assert any('needs "approved_by"' in r for r in refereed(record).rejections)


def test_the_review_date_needs_a_name_against_it() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "review_owner": ""}
    assert any('needs "review_owner"' in r for r in refereed(record).rejections)


def test_the_review_needs_the_question_that_would_produce_a_number() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "next_question": ""}
    assert any('needs "next_question"' in r for r in refereed(record).rejections)


def test_the_declining_owner_must_have_been_told() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "owner_informed": ""}
    assert any('needs "owner_informed"' in r for r in refereed(record).rejections)


def test_an_acknowledgement_without_a_usable_review_date_is_a_shrug() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "review_date": "next quarter"}
    assert any("ISO date" in r for r in refereed(record).rejections)


def test_an_acknowledgement_with_no_review_date_at_all_is_a_shrug() -> None:
    record = unscored_record()
    ack = dict(ACK)
    del ack["review_date"]
    record["activities"][0]["not_elicited_ack"] = ack
    assert any("ISO date" in r for r in refereed(record).rejections)


def test_an_expired_review_date_reopens_the_acknowledgement() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "review_date": "2020-01-01"}
    assert any("has passed" in r for r in refereed(record).rejections)


def test_a_review_date_of_today_has_not_passed_yet() -> None:
    record = unscored_record()
    today = datetime.date.today().isoformat()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "review_date": today}
    assert refereed(record).passed is True


def test_an_acknowledgement_that_is_not_an_object_teaches_the_shape() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = "Kettler said so"
    rejections = rejections_text(record)
    assert "not_elicited_ack" in rejections and "review_date" in rejections


# ── a band the source left unrated (ticket 376, ADR-0050) ────────────────────
#: The seed's 2024 production interview: "1 h –" in every lens, scored from 2 h on.
UNRATED_INTERVIEW = "07_Interviews/24_09_24_production-and-processing-barsch-interview.md"
BAND_ACK = {"approved_by": "Henning Barsch", "reason": "The interview did not rate the first hour.",
            "review_owner": "Franziska Dohm"}


def _seed_method() -> dict:
    return json.loads((Path(SEED) / "02_BCM-Method" / "method.json").read_text())


def code_read_record() -> tuple[dict, dict, dict]:
    """The seed interview's grid as code reads it (M13), every horizon it left out said as
    MISSING, with the quotes it was read from: (record, method, files)."""
    method = _seed_method()
    transcript = (Path(SEED) / UNRATED_INTERVIEW).read_text()
    [activity] = standardise(transcript, {}, [s["id"] for s in method["scenarios"]]).activities
    horizons = method["time_horizons"]
    grid = {lens: {h: row.get(h, "MISSING") for h in horizons}
            for lens, row in activity.impact_grid.items()}
    mtpd = derive_mtpd(_worst_case_row(grid), method)
    record = {"dept": activity.name, "plan": None, "comparison": [], "pp4_handoff": [],
              "activities": [{
                  "id": "production", "name": activity.name, "impact_grid": grid, "mtpd": mtpd,
                  "rpo": method["rpo_vocabulary"][0], "recovery_target": horizons[0],
                  "impact_summary": "goods can be frozen, stored or sold",
                  "evidence": [{"type": "transcript_quote", "lens": s.lens, "quote": s.quote,
                                "source_path": UNRATED_INTERVIEW} for s in activity.scores]}]}
    return record, method, {UNRATED_INTERVIEW: transcript}


def _unrated(record: dict, method: dict) -> list[str]:
    grid = record["activities"][0]["impact_grid"]
    return [h for h in method["time_horizons"]
            if all(row[h] == "MISSING" for row in grid.values())]


def test_the_code_read_grid_leaves_one_band_unrated_in_every_lens_and_scores_the_rest() -> None:
    record, method, _files = code_read_record()
    assert _unrated(record, method) == method["time_horizons"][:1]


def test_a_band_the_source_left_unrated_is_refused_without_an_acknowledgement() -> None:
    record, method, files = code_read_record()
    rejections = review(record, method, files).rejections
    assert [(r.kind, r.parts.get("horizon")) for r in rejections] == [
        (BAND_UNSCORED, h) for h in _unrated(record, method)]


def test_a_band_the_source_left_unrated_is_signable_with_a_named_acknowledgement() -> None:
    record, method, files = code_read_record()
    record["activities"][0][UNRATED_BAND_ACK] = {h: BAND_ACK for h in _unrated(record, method)}
    verdict = review(record, method, files)
    assert verdict.rejections == [] and verdict.passed is True
    assert MTPD_CHECK in verdict.checked and verdict.findings == [], "the MTPD is the grid's own"


@pytest.mark.parametrize("blank", list(BAND_ACK))
def test_an_unrated_band_acknowledgement_missing_a_field_names_the_field(blank: str) -> None:
    record, method, files = code_read_record()
    [band] = _unrated(record, method)
    record["activities"][0][UNRATED_BAND_ACK] = {band: {**BAND_ACK, blank: " "}}
    [rejection] = review(record, method, files).rejections
    assert (rejection.kind, rejection.parts) == (
        UNRATED_BAND_NEEDS_OWNER, {"activity": "production", "horizon": band, "missing": (blank,)})
    assert rejection == f"activity production: {UNRATED_BAND_ACK}[{band!r}] needs {[blank]}"


def test_an_acknowledgement_for_another_band_does_not_cover_the_unrated_one() -> None:
    record, method, files = code_read_record()
    [band] = _unrated(record, method)
    other = method["time_horizons"][-1]
    record["activities"][0][UNRATED_BAND_ACK] = {other: BAND_ACK}
    assert [r.kind for r in review(record, method, files).rejections] == [BAND_UNSCORED]
    record["activities"][0][UNRATED_BAND_ACK] = {band: "Barsch said so"}
    assert [r.kind for r in review(record, method, files).rejections] == [BAND_UNSCORED]
    record["activities"][0][UNRATED_BAND_ACK] = "Barsch said so"
    assert [r.kind for r in review(record, method, files).rejections] == [BAND_UNSCORED]


def test_the_acknowledgement_names_the_band_in_the_method_s_spelling_or_any_spacing() -> None:
    record, method, files = code_read_record()
    [band] = _unrated(record, method)
    record["activities"][0][UNRATED_BAND_ACK] = {band.replace(" ", ""): BAND_ACK}
    assert review(record, method, files).passed is True


def test_a_wholly_unscored_grid_is_not_signed_by_an_unrated_band_acknowledgement() -> None:
    record = unscored_record()
    record["activities"][0][UNRATED_BAND_ACK] = dict.fromkeys(HORIZONS, BAND_ACK)
    assert any("not_elicited_ack" in r for r in refereed(record).rejections)


# ── the RPO vocabulary ───────────────────────────────────────────────────────
def test_an_rpo_outside_the_methods_vocabulary_is_refused() -> None:
    record = valid_record()
    record["activities"][0]["rpo"] = "4 h"
    rejections = rejections_text(record)
    assert "rpo_vocabulary" in rejections and "0 h (no loss)" in rejections


def test_rpo_spacing_is_tolerated() -> None:
    record = valid_record()
    record["activities"][0]["rpo"] = "4h(ERP order data)"
    assert refereed(record).passed is True


def test_an_rpo_with_the_wrong_parenthetical_is_still_refused() -> None:
    record = valid_record()
    record["activities"][0]["rpo"] = "4 h (invoices)"
    assert any("rpo_vocabulary" in r for r in refereed(record).rejections)


def test_an_absent_rpo_is_not_judged() -> None:
    record = valid_record()
    del record["activities"][0]["rpo"]
    assert refereed(record).passed is True


def test_every_entry_of_the_vocabulary_is_accepted() -> None:
    for allowed in METHOD["rpo_vocabulary"]:
        record = valid_record()
        record["activities"][0]["rpo"] = allowed
        assert refereed(record).passed is True, allowed


# ── conflicts between two owners ─────────────────────────────────────────────
def test_a_conflict_with_no_named_human_owner_is_a_finding() -> None:
    record = valid_record()
    record["comparison"] = [{"issue": "the ERP clock"}]
    verdict = refereed(record)
    assert verdict.passed is True
    assert any("named human owner" in f and "the ERP clock" in f for f in verdict.findings)


def test_a_conflict_escalated_to_a_named_human_raises_nothing() -> None:
    record = valid_record()
    record["comparison"] = [{"issue": "the ERP clock", "escalated_to": "Dr Kettler"}]
    assert refereed(record).findings == []


def test_a_conflict_escalated_to_the_ai_is_a_false_record_and_is_refused() -> None:
    record = valid_record()
    record["comparison"] = [{"issue": "the ERP clock", "escalated_to": "the assistant"}]
    assert any("names the AI" in r for r in refereed(record).rejections)


def test_a_conflict_with_no_issue_name_still_reports() -> None:
    record = valid_record()
    record["comparison"] = [{}]
    assert any("named human owner" in f for f in refereed(record).findings)


def test_plan_drafting_language_in_a_conflicts_rationale_is_a_finding() -> None:
    record = valid_record()
    record["comparison"] = [
        {
            "issue": "the ERP clock",
            "escalated_to": "Dr Kettler",
            "why_it_matters": "Step 1: activate the plan",
        }
    ]
    assert any("plan-drafting language" in f for f in refereed(record).findings)


# ── the record as a whole ────────────────────────────────────────────────────
def test_a_record_with_no_activities_is_refused() -> None:
    assert any("no activities" in r for r in refereed({"activities": []}).rejections)


def test_a_record_with_no_activities_key_is_refused() -> None:
    assert any("no activities" in r for r in refereed({}).rejections)


def test_an_activity_that_is_not_an_object_is_refused_not_a_crash() -> None:
    record = valid_record()
    record["activities"] = ["Slaughter"]
    assert any("malformed activity" in r for r in refereed(record).rejections)


def test_an_activity_with_no_id_is_named_by_its_name() -> None:
    record = valid_record()
    del record["activities"][0]["id"]
    record["activities"][0]["impact_grid"]["financial"]["8 h"] = 9
    assert any("Slaughter" in r for r in refereed(record).rejections)


def test_an_activity_with_neither_id_nor_name_is_still_judged() -> None:
    record = valid_record()
    del record["activities"][0]["id"]
    del record["activities"][0]["name"]
    record["activities"][0]["impact_grid"]["financial"]["8 h"] = 9
    assert any("invalid score" in r for r in refereed(record).rejections)


def test_two_activities_are_both_judged() -> None:
    record = valid_record()
    second = valid_record()["activities"][0]
    second["id"] = "sales"
    second["rpo"] = "nonsense"
    record["activities"].append(second)
    assert any("sales" in r for r in refereed(record).rejections)


def test_the_referee_keeps_no_record_of_having_refereed() -> None:
    """No save token, no gate ledger, no marker written back: it reports and stops.

    `checked` is part of the report and not a mark on the record: stage 4's receipt is built from
    it, so the sentence is a function of what ran rather than a literal (ticket 15). The record
    itself comes back out of `review` exactly as it went in, which is what this asserts.
    """
    record = valid_record()
    before = repr(record)
    verdict = refereed(record)
    assert repr(record) == before
    assert sorted(vars(verdict)) == ["checked", "findings", "questions", "rejections"]  # t116


def test_the_room_files_are_optional_when_nothing_is_quoted() -> None:
    record = valid_record()
    del record["activities"][0]["evidence"]
    record["activities"][0]["impact_grid"] = {
        lens: dict.fromkeys(HORIZONS, "MISSING") for lens in LENSES
    }
    record["activities"][0]["not_elicited_ack"] = ACK
    assert review(record, METHOD).passed is True


# ── the exact wording of every message ───────────────────────────────────────
# The referee's output *is* its text: there is no code beside it, so a caller reads the sentence
# and nothing else. These tests pin each message verbatim, which makes a reworded rejection a
# deliberate edit rather than something that slips past a substring match.
SCENARIO_IDS = sorted(LENSES)
# ticket 132 (ADR-0030) adds his chat confirmation to the allowed types, a deliberate re-pin; ticket
# 171 the register row the derived RPO rests on, another
ALLOWED_TYPES = ["chat_confirmation", "company_file", "prior_bia", "prior_cycle", "register_no_rpo",
                 "register_row", "transcript_quote"]


def grid_of(record: dict) -> dict:
    return record["activities"][0]["impact_grid"]


def test_the_unknown_horizon_rejection_names_the_activity_lens_and_horizons() -> None:
    record = valid_record()
    grid_of(record)["financial"]["90 d"] = 3
    assert ("activity slaughter: impact_grid['financial'] has unknown horizon(s): ['90 d']"
            in refereed(record).rejections)


def test_the_missing_horizon_rejection_names_the_activity_lens_and_horizons() -> None:
    record = valid_record()
    del grid_of(record)["financial"]["8 h"]
    assert ("activity slaughter: impact_grid['financial'] missing horizon(s): ['8 h']"
            in refereed(record).rejections)


def test_the_lens_row_shape_rejection_names_the_type_it_got() -> None:
    record = valid_record()
    grid_of(record)["financial"] = "n/a"
    assert ("activity slaughter: impact_grid['financial'] must be an object of "
            "{horizon: score}, got str") in refereed(record).rejections


def test_the_grid_shape_rejection_names_the_type_it_got() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = "none given"
    assert ("activity slaughter: impact_grid must be an object of "
            "{lens: {horizon: score}}, got str") in refereed(record).rejections


def test_the_invented_lens_rejection_lists_the_method_scenario_ids() -> None:
    record = valid_record()
    grid_of(record)["supply-chain"] = dict.fromkeys(HORIZONS, 1)
    assert (f"activity slaughter: impact_grid lens 'supply-chain' is not a method scenario id — "
            f"method scenario ids: {SCENARIO_IDS}") in refereed(record).rejections


def test_the_missing_lens_rejection_lists_the_rows_that_are_absent() -> None:
    record = valid_record()
    del grid_of(record)["environment"]
    assert ("activity slaughter: impact_grid missing lens row(s): ['environment']"
            in refereed(record).rejections)


def test_the_invalid_score_rejection_names_the_cell_and_the_allowed_range() -> None:
    record = valid_record()
    grid_of(record)["financial"]["8 h"] = 9
    assert ("activity slaughter: impact_grid['financial']['8 h'] invalid score 9 "
            "(1-5 or 'MISSING')") in refereed(record).rejections


def test_an_activity_with_neither_id_nor_name_is_named_with_a_question_mark() -> None:
    record = valid_record()
    del record["activities"][0]["id"]
    del record["activities"][0]["name"]
    grid_of(record)["financial"]["8 h"] = 9
    assert ("activity ?: impact_grid['financial']['8 h'] invalid score 9 (1-5 or 'MISSING')"
            in refereed(record).rejections)


def test_the_skipped_time_band_rejection_says_the_mtpd_cannot_be_derived() -> None:
    record = valid_record()
    for row in grid_of(record).values():
        row["8 h"] = "MISSING"
    assert ("activity slaughter: impact_grid horizon '8 h' has no scored lens (all MISSING) "
            "— cannot derive MTPD") in refereed(record).rejections


def test_the_unusable_review_date_rejection_is_worded_in_full() -> None:
    record = unscored_record()
    ack = dict(ACK)
    del ack["review_date"]
    record["activities"][0]["not_elicited_ack"] = ack
    assert ('activity slaughter: not_elicited_ack needs a usable "review_date" as an ISO date '
            "(YYYY-MM-DD) — an acceptance without one is not an acceptance, it is a shrug"
            ) in refereed(record).rejections


def test_the_expired_review_date_rejection_is_worded_in_full() -> None:
    record = unscored_record()
    record["activities"][0]["not_elicited_ack"] = {**ACK, "review_date": "2020-01-01"}
    assert ("activity slaughter: the not_elicited_ack review date (2020-01-01) has passed — the "
            "unscored assessment is due for review. Re-accept with a new review_date, or go back "
            "to the owner for the figures") in refereed(record).rejections


def test_the_untagged_lens_rejection_teaches_both_ways_out() -> None:
    record = valid_record()
    grid_of(record)["customer-delivery"]["24 h"] = 3
    assert ("activity slaughter: impact_grid['customer-delivery'] is scored but no evidence item "
            "carries lens 'customer-delivery' — tag the quote that supports the score with "
            "lens='customer-delivery', or set the row to 'MISSING'"
            ) in refereed(record).rejections


def test_a_lens_whose_highest_cell_is_two_is_already_a_claim() -> None:
    """2 is a claim and needs a quote; only 1 is negligible."""
    record = valid_record()
    grid_of(record)["reputation"]["24 h"] = 2
    assert ("activity slaughter: impact_grid['reputation'] is scored but no evidence item "
            "carries lens 'reputation' — tag the quote that supports the score with "
            "lens='reputation', or set the row to 'MISSING'") in refereed(record).rejections


def test_the_unsigned_shared_quote_ack_rejection_is_worded_in_full() -> None:
    record = _two_scored_lenses(valid_record())
    record["activities"][0]["shared_quote_ack"] = {"lenses": ["financial", "customer-delivery"]}
    assert ("activity slaughter: shared_quote_ack was supplied for "
            "['customer-delivery', 'financial'] but has no approved_by — an unsigned entry is "
            "not an acknowledgement") in refereed(record).rejections


def test_the_reused_quote_finding_is_worded_in_full() -> None:
    verdict = refereed(_two_scored_lenses(valid_record()))
    assert verdict.findings == [
        "Human decisions: activity slaughter — the same quote is the evidence for "
        "['customer-delivery', 'financial']. One quote cannot be what supports 2 different "
        "impact categories unless a human confirms it. Quote the span that supports each "
        "category separately, or record {\"shared_quote_ack\": {\"lenses\": "
        "['customer-delivery', 'financial'], "
        '"approved_by": "<name of the person approving>"}}'
    ]


def test_an_acknowledged_reuse_does_not_stop_the_referee_seeing_the_next_one() -> None:
    """One acknowledged group is skipped, not a signal to stop looking at the rest."""
    record = valid_record()
    activity = record["activities"][0]
    for lens in ("customer-delivery", "legal-regulatory", "people-safety"):
        activity["impact_grid"][lens] = dict(WORST)
    activity["evidence"] = [
        {"type": "transcript_quote", "lens": lens, "quote": quote,
         "source_path": TRANSCRIPT_PATH}
        for lens, quote in (
            ("financial", "The line has to keep moving"),
            ("customer-delivery", "The line has to keep moving"),
            ("legal-regulatory", "back in about eight hours"),
            ("people-safety", "back in about eight hours"),
        )
    ]
    activity["shared_quote_ack"] = {
        "lenses": ["customer-delivery", "financial"],
        "approved_by": "Dr Reinhard Kettler",
    }
    assert refereed(record).findings == [
        "Human decisions: activity slaughter — the same quote is the evidence for "
        "['legal-regulatory', 'people-safety']. One quote cannot be what supports 2 different "
        "impact categories unless a human confirms it. Quote the span that supports each "
        "category separately, or record {\"shared_quote_ack\": {\"lenses\": "
        "['legal-regulatory', 'people-safety'], "
        '"approved_by": "<name of the person approving>"}}'
    ]


def test_the_falling_worst_case_finding_names_both_horizons_and_both_scores() -> None:
    record = valid_record()
    activity = record["activities"][0]
    activity["impact_grid"] = full_grid(
        {"0–4 h": 1, "8 h": 4, "24 h": 3, "48 h": 4, "72 h": 5, "1 week": 5})
    activity["mtpd"] = "8 h"
    activity["recovery_target"] = "4 h"
    assert refereed(record).findings == [
        "Gap: activity slaughter: the worst case improves with time — impact falls from 4 at 8 h "
        "to 3 at 24 h. A later outage cannot hurt less than an earlier one; say why, or correct "
        "the grid"
    ]


def test_the_asserted_mtpd_finding_is_worded_in_full() -> None:
    record = valid_record()
    record["activities"][0]["mtpd"] = "1 week"
    assert refereed(record).findings == [
        "Gap: activity slaughter: the grid derives an MTPD of '24 h', not the asserted '1 week' "
        "— the MTPD comes from the grid, so the assertion is the thing to explain or withdraw"
    ]


def test_the_absent_rto_rejection_shows_the_shape_to_record() -> None:
    record = valid_record()
    del record["activities"][0]["recovery_target"]
    assert ('activity slaughter: no recovery_target — record the RTO the owner stated, as '
            '"recovery_target": "8 h"') in refereed(record).rejections


def test_the_unparseable_rto_rejection_is_worded_in_full() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "8 fortnights"
    assert ("activity slaughter: recovery_target '8 fortnights' is not a parseable duration — "
            "give a bare number and unit like '8 h', '24 h' or '2-4 hours' so the RTO can be "
            "compared to the MTPD (a trailing note in parentheses is ignored)"
            ) in refereed(record).rejections


def test_the_rto_outside_its_mtpd_rejection_is_worded_in_full() -> None:
    record = valid_record()
    record["activities"][0]["recovery_target"] = "24 h"
    assert ("activity slaughter: recovery target 24 h is not strictly inside the MTPD 24 h — "
            "close the gap, or acknowledge it deliberately with recovery_gap_flagged"
            ) in refereed(record).rejections


def test_the_plan_language_finding_on_a_summary_carries_its_qualifier() -> None:
    record = valid_record()
    record["activities"][0]["impact_summary"] = "Step 1: activate the plan"
    assert refereed(record).findings == [
        "Human decisions: possible plan-drafting language in activity slaughter — review "
        "against the PP4 boundary (options and questions only)"
    ]


def test_the_continuity_plan_rejection_is_worded_in_full() -> None:
    record = valid_record()
    record["plan"] = "step 1: declare an incident"
    assert ("a continuity plan is present in 'plan' — the PP4 boundary is violated: the BIA "
            "hands requirements to solution design and stops before drafting either"
            ) in refereed(record).rejections


def test_the_chosen_solution_rejection_is_worded_in_full() -> None:
    record = valid_record()
    record["recovery_solution"] = "a hired generator"
    assert ("a chosen recovery solution is present in 'recovery_solution' — the PP4 boundary is "
            "violated: the BIA hands requirements to solution design and stops before drafting "
            "either") in refereed(record).rejections


def test_the_handoff_prefix_rejection_lists_the_four_prefixes() -> None:
    record = valid_record()
    record["pp4_handoff"] = ["buy a generator"]
    assert ("pp4_handoff item must start with Gap:/Option:/Human decisions:/Missing evidence: "
            "— got 'buy a generator'") in refereed(record).rejections


def test_the_plan_language_finding_on_a_handoff_item_carries_no_qualifier() -> None:
    record = valid_record()
    record["pp4_handoff"] = ["Option: activate the plan"]
    assert refereed(record).findings == [
        "Human decisions: possible plan-drafting language in pp4_handoff item "
        "'Option: activate the plan' — review against the PP4 boundary"
    ]


def test_a_handoff_finding_is_added_to_the_earlier_findings_not_put_in_their_place() -> None:
    record = valid_record()
    record["activities"][0]["impact_summary"] = "Step 1: activate the plan"
    record["pp4_handoff"] = ["Option: activate the plan"]
    findings = refereed(record).findings
    assert ("Human decisions: possible plan-drafting language in activity slaughter — review "
            "against the PP4 boundary (options and questions only)") in findings
    assert ("Human decisions: possible plan-drafting language in pp4_handoff item "
            "'Option: activate the plan' — review against the PP4 boundary") in findings


def test_the_unowned_conflict_finding_is_worded_in_full() -> None:
    record = valid_record()
    record["comparison"] = [{"issue": "the ERP clock"}]
    assert refereed(record).findings == [
        "Human decisions: conflict 'the ERP clock' needs a named human owner (escalated_to) "
        "before it can be resolved"
    ]


def test_a_conflict_with_no_issue_key_is_named_with_a_question_mark() -> None:
    record = valid_record()
    record["comparison"] = [{}]
    assert refereed(record).findings == [
        "Human decisions: conflict '?' needs a named human owner (escalated_to) before it can "
        "be resolved"
    ]


def test_the_ai_owner_rejection_is_worded_in_full() -> None:
    record = valid_record()
    record["comparison"] = [{"issue": "the ERP clock", "escalated_to": "the assistant"}]
    assert ("comparison 'the ERP clock': escalated_to names the AI, not a human "
            "('the assistant')") in refereed(record).rejections


def test_a_conflict_owned_by_a_named_human_is_not_refused_at_all() -> None:
    """Only a name drawn from the AI vocabulary is a false record; an ordinary name is not."""
    record = valid_record()
    record["comparison"] = [{"issue": "the ERP clock", "escalated_to": "Dr Kettler"}]
    assert refereed(record).rejections == []


def test_the_plan_language_finding_on_a_conflict_names_the_issue() -> None:
    record = valid_record()
    record["comparison"] = [
        {"issue": "the ERP clock", "escalated_to": "Dr Kettler",
         "why_it_matters": "Step 1: activate the plan"},
    ]
    assert refereed(record).findings == [
        "Human decisions: possible plan-drafting language in comparison 'the ERP clock' — "
        "review against the PP4 boundary"
    ]


def test_the_no_activities_rejection_is_worded_in_full() -> None:
    assert refereed({"activities": []}).rejections == [
        "no activities — a BIA must record at least one critical activity"
    ]


def test_the_malformed_activity_rejection_names_the_type_it_got() -> None:
    record = valid_record()
    record["activities"] = ["Slaughter"]
    assert ("malformed activity (expected an object, got str)" in refereed(record).rejections)


# ── the evidence messages ────────────────────────────────────────────────────
def test_the_malformed_evidence_rejection_names_the_type_it_got() -> None:
    record = valid_record()
    record["activities"][0]["evidence"] = ["the line has to keep moving"]
    assert ("activity slaughter: malformed evidence item (expected an object with "
            "type/quote/source_path, got str)") in refereed(record).rejections


def test_the_unknown_evidence_type_rejection_lists_the_allowed_types() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["type"] = "hearsay"
    assert (f"activity slaughter: unknown evidence type 'hearsay' (allowed: {ALLOWED_TYPES})"
            in refereed(record).rejections)


def test_the_empty_quote_rejection_names_the_evidence_type() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "   "
    assert ("activity slaughter: transcript_quote evidence quote is empty"
            in refereed(record).rejections)


def test_an_evidence_item_with_neither_quote_nor_ref_is_empty_not_fabricated() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0] = {"type": "transcript_quote", "lens": "financial"}
    assert ("activity slaughter: transcript_quote evidence quote is empty"
            in refereed(record).rejections)


def test_the_unverifiable_room_rejection_is_worded_in_full() -> None:
    assert ("activity slaughter: transcript_quote evidence cannot be verified — no file in the "
            "room is readable, so nothing was checked. Cite the file the words come from in "
            "source_path") in review(valid_record(), METHOD, {}).rejections


def test_the_missing_source_path_rejection_names_the_path_it_was_given() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["source_path"] = "07_Interviews/nowhere.md"
    assert ("activity slaughter: evidence source_path not found or ambiguous: "
            "'07_Interviews/nowhere.md'") in refereed(record).rejections


def test_the_fabricated_quote_rejection_names_the_file_it_cited() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "we would be back within the hour"
    assert (f"activity slaughter: transcript_quote quote not found in {TRANSCRIPT_PATH!r} "
            "(possible fabrication): 'we would be back within the hour'"
            ) in refereed(record).rejections


def test_the_fabricated_quote_rejection_with_no_cited_file_is_worded_in_full() -> None:
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    del evidence["source_path"]
    evidence["quote"] = "nobody said this"
    assert ("activity slaughter: transcript_quote quote not found in any readable file in the "
            "room (possible fabrication): 'nobody said this'") in refereed(record).rejections


def test_the_legacy_ref_repair_hint_is_given_for_every_readable_extension() -> None:
    for ext in (".md", ".json", ".jsonl", ".txt"):
        record = valid_record()
        ref = "07_Interviews/notes" + ext
        record["activities"][0]["evidence"][0] = {
            "type": "transcript_quote", "lens": "financial", "ref": ref}
        expected = (
            "activity slaughter: evidence.ref contains a file path, not a quote; use "
            '{"type": \'transcript_quote\', "quote": "exact contiguous text", '
            f'"source_path": {ref!r}' + "}"
        )
        assert expected in refereed(record).rejections, ext


def test_a_quote_carrying_a_slash_is_not_mistaken_for_a_file_path() -> None:
    """Both halves of the test matter: a path has a separator *and* a readable extension."""
    record = valid_record()
    record["activities"][0]["evidence"][0] = {
        "type": "transcript_quote", "lens": "financial",
        "ref": "the line stops / product is at risk",
    }
    files = {TRANSCRIPT_PATH: "Ahlgrim: the line stops / product is at risk"}
    assert review(record, METHOD, files).passed is True


def test_a_path_shaped_ref_is_ignored_once_the_item_also_carries_a_quote() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["ref"] = "07_Interviews/notes.md"
    assert refereed(record).passed is True


def test_a_leading_slash_does_not_make_a_source_path_ambiguous() -> None:
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    evidence["source_path"] = "/x/notes.md"
    evidence["quote"] = "beta sentence"
    files = {"notes.md": "alpha sentence", "x/notes.md": "beta sentence"}
    assert review(record, METHOD, files).passed is True


def test_a_bare_filename_resolves_against_a_room_file_in_a_subdirectory() -> None:
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    evidence["source_path"] = "notes.md"
    evidence["quote"] = "beta sentence"
    assert review(record, METHOD, {"x/notes.md": "beta sentence"}).passed is True


def test_markdown_emphasis_inside_a_quote_is_not_part_of_the_words() -> None:
    record = valid_record()
    record["activities"][0]["evidence"][0]["quote"] = "The line **has** to keep _moving_"
    assert refereed(record).passed is True


def test_every_evidence_item_is_judged_not_just_the_last_one() -> None:
    record = valid_record()
    record["activities"][0]["evidence"] = [
        {"type": "hearsay", "lens": "financial", "quote": "The line has to keep moving",
         "source_path": TRANSCRIPT_PATH},
        {"type": "transcript_quote", "lens": "financial", "quote": "nobody said this",
         "source_path": TRANSCRIPT_PATH},
    ]
    rejections = refereed(record).rejections
    assert (f"activity slaughter: unknown evidence type 'hearsay' (allowed: {ALLOWED_TYPES})"
            in rejections)
    assert (f"activity slaughter: transcript_quote quote not found in {TRANSCRIPT_PATH!r} "
            "(possible fabrication): 'nobody said this'") in rejections


def test_a_scenario_without_an_id_is_skipped_rather_than_dereferenced() -> None:
    method = {**METHOD, "scenarios": [*METHOD["scenarios"], {"label": "not a lens"}]}
    assert review(valid_record(), method, FILES).passed is True


def test_a_leading_slash_is_all_that_is_stripped_from_a_source_path() -> None:
    """Only the separator comes off: a path whose first character looks like one is kept whole."""
    record = valid_record()
    evidence = record["activities"][0]["evidence"][0]
    evidence["source_path"] = "/Xfiles/notes.md"
    evidence["quote"] = "beta sentence"
    assert review(record, METHOD, {"Xfiles/notes.md": "beta sentence"}).passed is True


def test_a_stray_character_in_front_of_the_number_is_not_silently_dropped() -> None:
    """Only the comparison qualifiers come off the front; a letter is a reason to refuse."""
    record = valid_record()
    record["activities"][0]["recovery_target"] = "X8 h"
    assert ("activity slaughter: recovery_target 'X8 h' is not a parseable duration — "
            "give a bare number and unit like '8 h', '24 h' or '2-4 hours' so the RTO can be "
            "compared to the MTPD (a trailing note in parentheses is ignored)"
            ) in refereed(record).rejections


# ── properties ───────────────────────────────────────────────────────────────
# The referee is a pure function of the record, the method and the room's files, and so is every
# helper it leans on. These state what holds for all inputs rather than for one grid: the examples
# above say what a given record earns, the properties below say what no record can make it do.

#: The characters a horizon label or a duration is actually written with, including the
#: typography `_norm` exists to tolerate. Arbitrary text would drag in combining marks, whose
#: composition depends on the spaces around them — a real quirk, not a property to assert.
LABEL_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz -–—h'’\"“*_`"
LABELS = st.text(alphabet=LABEL_CHARS, min_size=1, max_size=12)

SCORES = st.integers(min_value=1, max_value=5)
#: What a cell holds: a score, the honest refusal, or something the shape check already rejected.
CELLS = SCORES | st.just("MISSING") | st.none() | st.booleans() | st.just(0) | st.just(6)


@given(st.text())
def test_normalising_a_normalised_label_changes_nothing(text):
    """`_norm` is the comparison key, so it has to be a fixed point or two passes disagree."""
    assert _norm(_norm(text)) == _norm(text)


@given(LABELS)
def test_squashing_ignores_every_space_in_a_label(label):
    """`_squash`'s whole job: '24 h', '24h' and ' 24  h ' are one key."""
    assert _squash(label) == _squash(label.replace(" ", "")) == _squash(f"  {label}  ")


@given(st.text(), st.text())
def test_naming_one_horizon_is_reflexive_and_symmetric(left, right):
    """A comparison that depended on argument order would refuse a grid it had just accepted."""
    assert _same_horizon(left, left)
    assert _same_horizon(left, right) == _same_horizon(right, left)


@given(LABELS)
def test_typography_never_makes_two_horizons_different(label):
    assert _same_horizon(label, f"**{label}**")
    assert _same_horizon(label, label.upper())
    assert _same_horizon(label, label.replace("-", "–").replace("'", "’"))


@given(st.dictionaries(st.sampled_from(HORIZONS), SCORES), st.integers(min_value=1, max_value=5))
def test_the_derived_mtpd_is_the_earliest_intolerable_horizon(worst, threshold):
    """Derived, never asserted: the first band the method calls intolerable, or none of them."""
    method = {"time_horizons": HORIZONS, "intolerability_threshold": threshold}
    intolerable = [h for h in HORIZONS if worst.get(h, 0) >= threshold]

    mtpd = derive_mtpd(worst, method)

    assert mtpd == (intolerable[0] if intolerable else NO_MTPD)


@given(st.dictionaries(st.sampled_from(LENSES), st.dictionaries(st.sampled_from(HORIZONS), CELLS)))
def test_the_worst_case_row_is_the_worst_of_every_lens_and_nothing_a_lens_did_not_say(grid):
    """MISSING must not pull the worst case down, and no horizon may appear that nobody scored."""
    worst = _worst_case_row(grid)

    for horizon in HORIZONS:
        scored = [row[horizon] for row in grid.values()
                  if isinstance(row.get(horizon), int) and not isinstance(row[horizon], bool)
                  and 1 <= row[horizon] <= 5]
        assert worst.get(horizon) == (max(scored) if scored else None)


# ── the referee as a whole ───────────────────────────────────────────────────
# `review` reads and reports; it records nothing and it touches nothing. That makes the whole
# referee a pure function of three mappings, and these are the invariants of its verdict.
#
# The strategy generates junk *values* inside a record whose *containers* are the shapes JSON and
# `room_store` can hold: `activities`, `pp4_handoff` and `comparison` are lists, a conflict is an
# object, and `shared_quote_ack["lenses"]` is a list or a string. `review` is not total outside
# those — `{"comparison": ["x"]}` raises `AttributeError` and `{"pp4_handoff": 5}` raises
# `TypeError` rather than rejecting them. That is a real hole and a separate ticket: closing it
# changes the referee's refusal set, which is not a change to make behind a property test.

JSON_LEAF = (st.none() | st.booleans() | st.integers(min_value=-5, max_value=9)
             | st.text(max_size=8) | st.sampled_from(HORIZONS + LENSES))
DURATIONS = st.sampled_from(["8 h", "24 h", "2-4 hours", "0–4 h", "soon", "", "30 min"])
PLAN_TALK = st.sampled_from(["immediate actions: call the plant", "we lose product fast",
                             "Gap: no figure", "Option: a second line", "step 1: declare"])

EVIDENCE_ITEMS = st.fixed_dictionaries({}, optional={
    "type": st.sampled_from(EVIDENCE_TYPES) | JSON_LEAF,
    "quote": st.sampled_from(["The line has to keep moving", "not in any file", ""]) | JSON_LEAF,
    "source_path": st.sampled_from([TRANSCRIPT_PATH, "nope.md", ""]) | JSON_LEAF,
    "lens": st.sampled_from(LENSES) | JSON_LEAF,
    "ref": JSON_LEAF,
})
GRIDS = st.dictionaries(st.sampled_from(LENSES) | st.text(max_size=4),
                        st.dictionaries(st.sampled_from(HORIZONS) | st.text(max_size=4), CELLS)
                        | JSON_LEAF, max_size=3)
ACKS = st.fixed_dictionaries({}, optional={
    "approved_by": st.text(max_size=6), "reason": st.text(max_size=6),
    "review_owner": st.text(max_size=6), "next_question": st.text(max_size=6),
    "owner_informed": st.text(max_size=6),
    "review_date": st.sampled_from(["2020-01-01", "2099-12-31", "soon", ""]),
})
SHARED_ACKS = st.fixed_dictionaries({}, optional={
    "approved_by": st.text(max_size=6),
    "lenses": st.lists(st.sampled_from(LENSES), max_size=3) | st.text(max_size=4),
})
ACTIVITIES = st.fixed_dictionaries({}, optional={
    "id": st.text(max_size=4), "name": st.text(max_size=4),
    "impact_grid": GRIDS | JSON_LEAF,
    "evidence": st.lists(EVIDENCE_ITEMS | JSON_LEAF, max_size=2) | JSON_LEAF,
    "recovery_target": DURATIONS | JSON_LEAF,
    "recovery_gap_flagged": st.booleans(),
    "mtpd": st.sampled_from(HORIZONS) | DURATIONS | JSON_LEAF,
    "rpo": st.sampled_from(["0 h (no loss)", "whenever"]) | JSON_LEAF,
    "impact_summary": PLAN_TALK | JSON_LEAF,
    "not_elicited_ack": ACKS | JSON_LEAF,
    "shared_quote_ack": SHARED_ACKS | st.none(),
    "unrated_band_ack": st.dictionaries(st.sampled_from(HORIZONS), ACKS | JSON_LEAF,
                                        max_size=2) | JSON_LEAF,
})
CONFLICTS = st.fixed_dictionaries({}, optional={
    "issue": st.text(max_size=6),
    "escalated_to": st.sampled_from(["Ahlgrim", "the AI assistant", "", "GPT"]) | JSON_LEAF,
    "why_it_matters": PLAN_TALK | JSON_LEAF,
})
RECORDS = st.fixed_dictionaries({}, optional={
    "activities": st.lists(ACTIVITIES | JSON_LEAF, max_size=3),
    "pp4_handoff": st.lists(PLAN_TALK | JSON_LEAF, max_size=3),
    "comparison": st.lists(CONFLICTS, max_size=2),
    "plan": JSON_LEAF,
    "recovery_solution": JSON_LEAF,
})


@given(RECORDS)
def test_the_referee_reads_any_record_the_store_can_hold_without_raising(record):
    """Whatever a stage card produced, the referee answers with a verdict rather than a crash."""
    verdict = review(record, METHOD, FILES)

    assert isinstance(verdict, Verdict)
    assert all(isinstance(text, str) and text for text in verdict.rejections + verdict.findings)


@given(RECORDS)
def test_every_rejection_is_parts_a_card_can_be_written_from(record):
    """Whatever it refuses, it refuses as data: there is no way out of this module as prose.

    The one that reached a manager's screen — `impact_grid['legal-regulatory'] missing
    horizon(s): ['72 h']` — reached it because a rejection was a string and the card had nothing
    else to print. A kind nothing can word is a card nobody can read, so `nemo.walk` holds a
    sentence for every one of these and a test up there pins the two lists together.
    """
    for rejection in review(record, METHOD, FILES).rejections:
        assert isinstance(rejection, Rejection), rejection
        assert rejection.kind in KINDS


@given(RECORDS)
def test_only_a_rejection_blocks_a_save(record):
    """A finding is data carried to the card, never a wall — so it can never move `passed`."""
    verdict = review(record, METHOD, FILES)

    assert verdict.passed is (not verdict.rejections)
    assert Verdict(rejections=[], findings=verdict.findings).passed


@given(RECORDS)
def test_every_finding_is_written_in_the_handoff_vocabulary(record):
    """A finding rides to the card and to the PP4 handoff, which only takes these prefixes."""
    for finding in review(record, METHOD, FILES).findings:
        assert finding.startswith(("Gap:", "Option:", "Human decisions:", "Missing evidence:"))


@given(RECORDS)
def test_the_referee_records_nothing_and_answers_the_same_twice(record):
    """It reads; it reports; it records nothing — so the record it read is the record it left."""
    before = repr(record)
    first = review(record, METHOD, FILES)
    second = review(record, METHOD, FILES)

    assert repr(record) == before
    assert (first.rejections, first.findings) == (second.rejections, second.findings)

# ── the properties: what the derivation guarantees for every grid, not these grids ──
# `HORIZONS` above is the method's own band list, so these run against the real labels — including
# the en dash in "0–4 h", which is exactly the typography `norm` exists to survive. The horizon
# lists are drawn in arbitrary order because `derive_mtpd` reads "earliest" off the method's own
# ordering, and nothing promises a method lists its bands shortest-first.
BAND = st.sampled_from(HORIZONS)
BAND_LISTS = st.lists(BAND, min_size=1, max_size=6, unique=True)
WORST_ROWS = st.dictionaries(BAND, st.integers(min_value=1, max_value=5), max_size=6)
THRESHOLDS = st.integers(min_value=1, max_value=5)


@given(BAND_LISTS, WORST_ROWS, THRESHOLDS)
def test_the_derived_mtpd_is_always_a_band_the_method_names(bands, worst, threshold):
    """It never invents a horizon: the answer is the method's vocabulary or the honest refusal."""
    method = {"time_horizons": bands, "intolerability_threshold": threshold}
    assert derive_mtpd(worst, method) in [*bands, NO_MTPD]


@given(BAND_LISTS, WORST_ROWS, THRESHOLDS)
def test_the_derived_mtpd_is_always_the_earliest_band_that_reaches_the_threshold(
    bands, worst, threshold
):
    """The MTPD is where the grid first crosses, so no earlier band may have crossed already."""
    method = {"time_horizons": bands, "intolerability_threshold": threshold}
    derived = derive_mtpd(worst, method)
    assume(derived != NO_MTPD)
    assert all(worst.get(band, 0) < threshold for band in bands[:bands.index(derived)])


@given(BAND_LISTS, WORST_ROWS, THRESHOLDS)
def test_no_mtpd_is_returned_only_when_no_band_reaches_the_threshold(bands, worst, threshold):
    """The complement: "no MTPD within horizons" is a claim about every band, so check them all."""
    method = {"time_horizons": bands, "intolerability_threshold": threshold}
    assume(derive_mtpd(worst, method) == NO_MTPD)
    assert all(worst.get(band, 0) < threshold for band in bands)


@given(BAND_LISTS, WORST_ROWS, THRESHOLDS, THRESHOLDS)
def test_raising_the_threshold_never_moves_the_mtpd_earlier(bands, worst, low, high):
    """Monotone in the method's tolerance: a method harder to offend cannot produce a tighter MTPD.

    Position is read off `[*bands, NO_MTPD]`, which puts the refusal last without a special case —
    "no MTPD within horizons" is later than every band, which is precisely what it means.
    """
    def derive(threshold):
        return derive_mtpd(worst, {"time_horizons": bands,
                                   "intolerability_threshold": threshold})

    order = [*bands, NO_MTPD]
    assert order.index(derive(max(low, high))) >= order.index(derive(min(low, high)))


# ── what it checked, as a fact about this run (ticket 15) ────────────────────
#
# The receipt stage 4 prints is built out of this list and out of nothing else, so a clause can
# only appear because the check that names it ran. v1's closure note was a literal string that
# said "record validated and saved" whatever the run had done; a literal cannot be made false.


def test_a_record_nobody_refereed_has_nothing_checked_against_it() -> None:
    assert Verdict().checked == []


def test_every_check_the_referee_ran_names_itself() -> None:
    assert refereed(valid_record()).checked == [
        QUOTES_CHECK, GRID_CHECK, MTPD_CHECK, RTO_CHECK, RPO_CHECK]


def test_a_grid_that_cannot_be_judged_claims_no_grid_and_no_mtpd() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = "not a grid"
    checked = refereed(record).checked
    assert GRID_CHECK not in checked and MTPD_CHECK not in checked


# ── the clause that could not be false (ticket 26) ───────────────────────────
#
# `_review_boundary` said it had run before it looked, and the two keys it then read are keys
# `nemo.bia` does not write — so the clause appeared on every receipt about a check that had
# examined nothing. A check claims itself where it had something of the manager's to judge.


def test_a_record_carrying_no_plan_is_not_told_it_was_held_against_the_boundary() -> None:
    record = valid_record()
    assert all(record.get(key) is None for key in ("plan", "recovery_solution"))
    assert BOUNDARY_CHECK not in refereed(record).checked


def test_a_record_that_carries_a_plan_is_judged_and_only_then_says_so() -> None:
    record = valid_record()
    record["plan"] = {"immediate actions": "call the plant"}
    verdict = refereed(record)
    assert [r for r in verdict.rejections if r.kind == BOUNDARY]
    assert BOUNDARY_CHECK in verdict.checked


def test_an_item_handed_over_is_something_to_judge_the_boundary_over() -> None:
    record = valid_record()
    record["pp4_handoff"] = ["Gap: no figure for the permit"]
    assert BOUNDARY_CHECK in refereed(record).checked


def test_a_grid_the_method_does_not_recognise_claims_no_grid() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = {"invented-lens": dict.fromkeys(HORIZONS, 1)}
    assert GRID_CHECK not in refereed(record).checked


def test_an_rto_never_held_against_an_mtpd_is_not_claimed_to_have_been() -> None:
    """The comparison is the claim. An unparseable target was read and not compared."""
    record = valid_record()
    record["activities"][0]["recovery_target"] = "as soon as we can"
    assert RTO_CHECK not in refereed(record).checked


def test_an_rto_with_no_mtpd_to_hold_it_against_is_not_claimed_either() -> None:
    record = valid_record()
    record["activities"][0]["impact_grid"] = full_grid(dict.fromkeys(HORIZONS, 1))
    record["activities"][0]["mtpd"] = NO_MTPD
    assert RTO_CHECK not in refereed(record).checked
    assert GRID_CHECK in refereed(record).checked


def test_an_activity_that_states_no_rpo_claims_no_rpo_check() -> None:
    record = valid_record()
    del record["activities"][0]["rpo"]
    assert RPO_CHECK not in refereed(record).checked


def test_a_quote_nothing_in_the_room_could_be_checked_against_claims_nothing() -> None:
    record = valid_record()
    assert QUOTES_CHECK not in review(record, METHOD, {}).checked


def test_an_activity_with_no_evidence_at_all_claims_no_quote_check() -> None:
    record = valid_record()
    record["activities"][0]["evidence"] = []
    assert QUOTES_CHECK not in refereed(record).checked


def test_a_check_that_ran_over_five_activities_is_named_once() -> None:
    record = valid_record()
    record["activities"] = [dict(record["activities"][0], id=f"a{n}") for n in range(5)]
    assert refereed(record).checked.count(GRID_CHECK) == 1


# ── the reason behind the figure (ticket 15) ─────────────────────────────────


def test_the_crossing_is_the_derived_mtpd_and_the_categories_that_reach_it() -> None:
    assert crossing(full_grid(WORST), METHOD) == ("24 h", ["financial"])


def test_every_category_that_reaches_the_threshold_there_is_named() -> None:
    grid = full_grid(WORST)
    grid["reputation"] = dict(WORST)
    assert crossing(grid, METHOD) == ("24 h", ["financial", "reputation"])


def test_a_category_below_the_threshold_at_that_horizon_is_not_the_reason() -> None:
    grid = full_grid(WORST)
    grid["reputation"] = {**WORST, "24 h": 3}
    assert crossing(grid, METHOD) == ("24 h", ["financial"])


def test_a_grid_that_crosses_nowhere_names_nobody() -> None:
    assert crossing(full_grid(dict.fromkeys(HORIZONS, 1)), METHOD) == (NO_MTPD, [])


def test_the_crossing_reads_the_grid_the_referee_reads_typography_and_all() -> None:
    """The same canonicalization, so the card cannot say a horizon the referee judged elsewhere."""
    grid = {lens.upper(): {h.replace("–", "-"): v for h, v in row.items()}
            for lens, row in full_grid(WORST).items()}
    assert crossing(grid, METHOD) == ("24 h", ["financial"])


def test_a_missing_cell_is_not_read_as_reaching_anything() -> None:
    grid = full_grid({**WORST, "24 h": "MISSING"})
    assert crossing(grid, METHOD) == ("48 h", ["financial"])


# ── ticket 132 (ADR-0030): a figure he confirms in chat is his confirmation, never a quote ────────
TURNS = {"t-7": {"words": "Record RTO 8 h", "on": "2026-09-23"}}


def _confirmed(**entry: str) -> dict:
    record = valid_record()
    record["activities"][0]["evidence"].append(
        {"type": "chat_confirmation", "words": "Record RTO 8 h", "on": "2026-09-23",
         "turn_id": "t-7", **entry})
    return record


def test_an_interview_quote_in_no_file_is_refused_whatever_its_type() -> None:
    """The word-for-word check has no exception: every type that carries a quote is held to the
    room's files, and `manager_confirmed` is no quote type at all (the live patch's skip is gone
    from nemo's allow-list, where it never was)."""
    assert "manager_confirmed" not in EVIDENCE_TYPES
    for kind in (*EVIDENCE_TYPES, "manager_confirmed"):
        if kind == "chat_confirmation":
            continue
        record = valid_record()
        record["activities"][0]["evidence"].append(
            {"type": kind, "quote": "we'd be down a week", "source_path": ""})
        assert review(record, METHOD, FILES, TURNS).rejections, kind


def test_a_chat_confirmation_is_accepted_with_its_date_and_turn_id() -> None:
    verdict = review(_confirmed(), METHOD, FILES, TURNS)
    assert verdict.rejections == []
    assert "chat_confirmation" in EVIDENCE_TYPES


def test_a_confirmation_whose_words_are_not_on_his_turn_is_refused() -> None:
    """The amendment: words a model call supplied, and not the words of his turn, are refused."""
    [rejection] = review(_confirmed(words="Record RTO 2 h"), METHOD, FILES, TURNS).rejections
    assert rejection.kind == "quote-not-found"
    assert rejection.parts == {"activity": "slaughter", "quote": "Record RTO 2 h", "turn": "t-7",
                               "on": "2026-09-23"}


def test_a_confirmation_naming_a_turn_the_turn_file_does_not_hold_is_refused() -> None:
    [rejection] = review(_confirmed(turn_id="t-99"), METHOD, FILES, TURNS).rejections
    assert rejection.kind == "evidence-unchecked"
    assert rejection == ("activity slaughter: a chat confirmation names turn 't-99', which the "
                         "room's turn file does not hold")


def test_a_confirmation_dated_otherwise_than_its_turn_is_refused() -> None:
    [rejection] = review(_confirmed(on="2026-09-01"), METHOD, FILES, TURNS).rejections
    assert rejection.kind == "evidence-unchecked"
    assert rejection == ("activity slaughter: a chat confirmation is dated '2026-09-01', and turn "
                         f"'t-7' was on {TURNS['t-7']['on']!r}")


def test_with_no_turn_file_read_a_confirmation_is_refused() -> None:
    assert review(_confirmed(), METHOD, FILES).rejections


# ── ticket 171: the register-derived RPO rests on the register's own row, checked like a quote ───
REGISTER_PATH = "03_Dependencies/dependency-register.json"
REGISTER_TEXT = ('{"synthetic": true, "erp": {"asset_id": "erp", "name": "ERP", '
                 '"recovery_point": "4 h (order data)"}, "note": "4 h (order data) elsewhere"}')


def _from_register(**entry: str) -> dict:
    record = valid_record()
    record["activities"][0]["evidence"].append(
        {"type": "register_row", "activity": "Slaughter", "asset_id": "erp",
         "quote": "4 h (order data)", "source_path": REGISTER_PATH, **entry})
    return record


def test_a_register_row_the_room_s_register_holds_for_its_asset_is_accepted() -> None:
    assert "register_row" in EVIDENCE_TYPES
    verdict = review(_from_register(), METHOD, {**FILES, REGISTER_PATH: REGISTER_TEXT})
    assert verdict.rejections == []


def test_a_register_row_whose_words_its_asset_does_not_hold_is_refused() -> None:
    """Tampered: words the register holds, but not under the asset the row names; words it holds
    nowhere; an asset it does not hold."""
    files = {**FILES, REGISTER_PATH: REGISTER_TEXT}
    for entry in ({"quote": "2 h (order data)"}, {"asset_id": "note"}, {"asset_id": "crm"},
                  {"quote": "ERP order"}):
        [rejection] = review(_from_register(**entry), METHOD, files).rejections
        assert rejection.kind == "quote-not-found", entry


def test_a_register_row_naming_json_that_is_no_register_is_refused() -> None:
    """JSON that is no mapping holds no entries: nothing was checked (171's split)."""
    files = {**FILES, REGISTER_PATH: '["4 h (order data)"]'}
    [rejection] = review(_from_register(), METHOD, files).rejections
    assert rejection.kind == "evidence-unchecked"


def test_a_register_row_naming_a_file_the_room_does_not_hold_is_refused() -> None:
    [rejection] = review(_from_register(), METHOD, FILES).rejections
    assert rejection.kind == "evidence-unchecked"
    [rejection] = review(_from_register(), METHOD, {**FILES, REGISTER_PATH: "not json"}).rejections
    assert rejection.kind == "evidence-unchecked"


# ── t171-shape (DRAFT, awaiting the owner): a register row is read for ITS activity ───────────
#: The new seed's shape: an entry with `consumers` declares only what its row for a department says;
#: one with no `consumers` field declares its own figure for every activity (the old seed's shape).
CONSUMER_REGISTER = json.dumps({
    "m365": {"consumers": [{"department": "Slaughter", "rpo": "<1 h"},
                           {"department": "Packing", "rpo": "<24 h"}]},
    "fleet": {"consumers": [{"department": "Slaughter", "rpo": None}]},
    "erp": {"rpo": "<24 h", "consumers": [{"department": "Packing", "rpo": "<24 h"}]},
    "scales": {"rpo": "4 h"},
})


def _for_activity(*rows: dict, dependencies: list[str] | None = None) -> dict:
    """The fixed record carrying `rows` (and its dependency list), with the consumer register."""
    record = valid_record()
    record["activities"][0]["evidence"] += [{"source_path": REGISTER_PATH, **r} for r in rows]
    record["activities"][0]["dependencies"] = dependencies or []
    return record


def _refused(record: dict) -> list:
    return review(record, METHOD, {**FILES, REGISTER_PATH: CONSUMER_REGISTER}).rejections


def _row(asset: str, quote: str, activity: str = "Slaughter") -> dict:
    return {"type": "register_row", "activity": activity, "asset_id": asset, "quote": quote}


def _no_rpo(*assets: str, activity: str = "Slaughter") -> dict:
    return {"type": "register_no_rpo", "activity": activity, "asset_ids": list(assets)}


def test_a_register_row_holds_its_activity_s_consumer_row_or_an_entry_s_own_figure() -> None:
    assert "register_no_rpo" in EVIDENCE_TYPES
    assert _refused(_for_activity(_row("m365", "<1 h"), _row("scales", "4 h"))) == []


def test_a_register_row_claiming_another_activity_s_consumer_value_is_refused() -> None:
    """Packing's <24 h, quoted for Slaughter; the same row naming Packing on Slaughter's record;
    an entry's own top-level figure where it has consumer rows and none for Slaughter."""
    for row in (_row("m365", "<24 h"), _row("m365", "<24 h", activity="Packing"),
                _row("erp", "<24 h"), _row("fleet", "<1 h")):
        [rejection] = _refused(_for_activity(row))
        assert rejection.kind == "quote-not-found", row


def test_the_register_giving_no_rpo_is_accepted_where_no_row_for_the_activity_names_one() -> None:
    record = _for_activity(_no_rpo("fleet"), dependencies=["fleet", "not-in-the-register"])
    assert _refused(record) == []
    assert _refused(_for_activity(_no_rpo())) == []


def test_a_no_rpo_row_where_a_row_for_the_activity_names_a_figure_is_refused() -> None:
    """Its own list names one; the record's dependency list names one the row left out; an entry
    with no consumers declares its own for every activity; and a row for another activity."""
    for record in (_for_activity(_no_rpo("fleet", "m365")),
                   _for_activity(_no_rpo("fleet"), dependencies=["fleet", "m365"]),
                   _for_activity(_no_rpo("scales")),
                   _for_activity(_no_rpo("m365", activity="Kitchen"))):
        [rejection] = _refused(record)
        assert rejection.kind == "quote-not-found", record


def test_a_no_rpo_row_naming_no_register_the_room_holds_is_refused() -> None:
    [rejection] = review(_for_activity(_no_rpo("fleet")), METHOD, FILES).rejections
    assert rejection.kind == "evidence-unchecked"


# 171h: each register rejection pinned verbatim, with the parts the walk words it from, like the
# other rejections above. `Rejection` is a str, so `==` alone would not see `parts`.
def _pinned(rejection: Rejection) -> tuple[str, str, dict]:
    return str(rejection), rejection.kind, dict(rejection.parts)


def test_a_register_row_s_refusal_names_its_activity_asset_file_and_quote() -> None:
    [rejection] = _refused(_for_activity(_row("m365", "<24 h")))
    assert _pinned(rejection) == (
        "activity slaughter: register_row quote not held for 'm365' for 'Slaughter' in "
        "'03_Dependencies/dependency-register.json' (possible fabrication): '<24 h'",
        "quote-not-found", {"activity": "slaughter", "quote": "<24 h"})


def test_a_register_row_naming_no_asset_is_refused_as_naming_none() -> None:
    row = {"type": "register_row", "activity": "Slaughter", "quote": "4 h"}
    [rejection] = _refused(_for_activity(row))
    assert str(rejection) == (
        "activity slaughter: register_row quote not held for '' for 'Slaughter' in "
        "'03_Dependencies/dependency-register.json' (possible fabrication): '4 h'")


def test_an_empty_register_row_is_refused_even_where_the_entry_holds_an_empty_value() -> None:
    """No words are nobody's words, here too: the empty quote is refused before it is looked for,
    so an entry holding "" does not hold it."""
    files = {**FILES, REGISTER_PATH: json.dumps({"blank": {"rpo": ""}})}
    [rejection] = review(_for_activity(_row("blank", "")), METHOD, files).rejections
    assert rejection.kind == "quote-not-found"


def test_a_register_the_room_does_not_hold_is_refused_naming_the_row_s_type_and_path() -> None:
    cited = {"source_path": REGISTER_PATH}
    for row, said in (({**_row("m365", "<1 h"), **cited}, f"register_row names {REGISTER_PATH!r}"),
                      ({**_no_rpo("fleet"), **cited}, f"register_no_rpo names {REGISTER_PATH!r}"),
                      (_row("m365", "<1 h"), "register_row names ''")):
        record = valid_record()
        record["activities"][0]["evidence"].append(row)
        [rejection] = review(record, METHOD, FILES).rejections
        assert _pinned(rejection) == (
            f"activity slaughter: {said}, which is no register the room holds, so nothing was "
            "checked", "evidence-unchecked", {"activity": "slaughter"})


def test_a_no_rpo_row_s_refusal_names_the_assets_that_give_the_activity_a_figure() -> None:
    [rejection] = _refused(_for_activity(_no_rpo("fleet", "m365")))
    assert _pinned(rejection) == (
        "activity slaughter: register_no_rpo for 'Slaughter', but the register names a figure "
        "for 'Slaughter' in ['m365'] (possible fabrication)",
        "quote-not-found", {"activity": "slaughter", "quote": "['m365']"})


def test_a_no_rpo_row_on_a_record_naming_no_department_is_read_for_none() -> None:
    record = _for_activity(_no_rpo("scales"))
    del record["dept"]
    [rejection] = _refused(record)
    assert str(rejection) == (
        "activity slaughter: register_no_rpo for 'Slaughter', but the register names a figure "
        "for '' in ['scales'] (possible fabrication)")


def test_a_confirmation_with_no_words_is_refused_whatever_his_turn_holds() -> None:
    """No words are nobody's words: an empty confirmation is found in every turn, so it is refused
    before it is looked for."""
    [rejection] = review(_confirmed(words=" "), METHOD, FILES, TURNS).rejections
    assert rejection == ("activity slaughter: a chat confirmation's words ' ' are not his on "
                         "turn 't-7'")


def test_a_confirmation_naming_no_turn_at_all_is_refused_naming_what_it_claimed() -> None:
    """Its turn is in the room's turn file: one that names no turn names nothing the file holds,
    and the refusal carries the turn it claimed and the day it claimed, so the record shows both."""
    [rejection] = review(_confirmed(turn_id=""), METHOD, FILES, TURNS).rejections
    assert rejection.kind == "evidence-unchecked"
    assert rejection == ("activity slaughter: a chat confirmation names turn '', which the "
                         "room's turn file does not hold")
    assert rejection.parts == {"activity": "slaughter", "turn": "", "on": "2026-09-23"}


def test_a_confirmation_naming_an_unheld_turn_carries_that_turn_in_its_refusal() -> None:
    """The refusal names the turn that was looked for, not nothing: nemo could check the words
    against no turn, and the record says which one it was handed."""
    [rejection] = review(_confirmed(turn_id="t-99"), METHOD, FILES, TURNS).rejections
    assert rejection.parts == {"activity": "slaughter", "turn": "t-99", "on": "2026-09-23"}


def test_a_confirmation_with_no_words_field_at_all_is_refused_as_words_not_found() -> None:
    """Words that are not his are words not found: a confirmation filed with no words has none of
    his, and the refusal quotes what it carried — nothing."""
    [rejection] = review(_confirmed(words=""), METHOD, FILES, TURNS).rejections
    assert rejection.kind == "quote-not-found"
    assert rejection == ("activity slaughter: a chat confirmation's words '' are not his on "
                         "turn 't-7'")
    assert rejection.parts == {"activity": "slaughter", "quote": "", "turn": "t-7",
                               "on": "2026-09-23"}


def test_a_confirmation_dated_otherwise_carries_its_turn_and_both_days() -> None:
    """Its day is that turn's: the refusal carries the turn, the day the turn was on, and the day
    the confirmation claimed, so the two can be read against each other."""
    [rejection] = review(_confirmed(on="2026-09-01"), METHOD, FILES, TURNS).rejections
    assert rejection.parts == {"activity": "slaughter", "turn": "t-7", "on": "2026-09-23",
                               "claimed": "2026-09-01"}


def test_a_turn_that_holds_no_words_of_his_confirms_nothing() -> None:
    """His words are his words on that turn: a turn the file holds with nothing of his in it has no
    words to be found, so whatever a confirmation claims for it, long or short, is not his."""
    turns = {"t-7": {"words": "", "on": "2026-09-23"}}
    for claim in ("Record RTO 8 h", "xx"):
        [rejection] = review(_confirmed(words=claim), METHOD, FILES, turns).rejections
        assert rejection.kind == "quote-not-found", claim


def test_his_words_confirm_under_whatever_turn_id_the_file_holds_them_on() -> None:
    """His words are his words on that turn, and the turn id is only which turn: the same words
    confirm on any id the room's turn file holds them under, and when they are not his the refusal
    still names the real turn — the one the confirmation was handed, whatever it is called."""
    for turn_id in ("t-7", "", "0", "turn/9", "a turn id with spaces"):
        turns = {turn_id: {"words": "Record RTO 8 h", "on": "2026-09-23"}}
        assert review(_confirmed(turn_id=turn_id), METHOD, FILES, turns).rejections == [], turn_id
        [rejection] = review(_confirmed(turn_id=turn_id, words="Record RTO 2 h"),
                             METHOD, FILES, turns).rejections
        assert rejection.kind == "quote-not-found", turn_id
        assert rejection.parts == {"activity": "slaughter", "quote": "Record RTO 2 h",
                                   "turn": turn_id, "on": "2026-09-23"}
        assert rejection == (f"activity slaughter: a chat confirmation's words 'Record RTO 2 h' "
                             f"are not his on turn {turn_id!r}")


# ── Every check reads the record before it says it ran ───────────────────────────────────────────
# From `tests/ui/walk/test_the_referee_reports_data_and_the_walk_writes_the_prose.py` step 26
# (ticket 26), last held at 602cc648, which ticket 165's last slice retired with that walk file.
# Read off the real tree found by walking up, never mutmut's rewritten copy.


def _reads_before(function: ast.FunctionDef, line: int) -> bool:
    """Whether anything of the record is read in `function` before `line`: `x.get(...)` or `x[...]`,
    which is how every check reaches into the record, the activity or the method it was handed."""
    return any(getattr(node, "lineno", line) < line and (
        isinstance(node, ast.Subscript)
        or (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"))
        for node in ast.walk(function))


def test_every_check_records_its_clause_only_after_it_has_read_the_record():
    tree = ast.parse((repo_root() / "src" / "nemo" / "referee.py").read_text(encoding="utf-8"))
    ran = [(function, call) for function in ast.walk(tree)
           if isinstance(function, ast.FunctionDef)
           for call in ast.walk(function) if isinstance(call, ast.Call)
           and isinstance(call.func, ast.Attribute) and call.func.attr == "ran"]
    assert ran, "step 26: no `verdict.ran(...)` in `nemo.referee`, so this read nothing"
    early = [(function.name, ast.unparse(call)) for function, call in ran
             if (isinstance(function.body[0], ast.Expr) and function.body[0].value is call)
             or not _reads_before(function, call.lineno)]
    assert early == [], (
        f"step 26: {early} record a clause before anything of the record has been read")


# ── a band MTPD at its upper edge: what the phone refuses, nemo's own (t74, 241 slice 3) ─────
#: (target, the grid's MTPD, what the record carries) → the one refusal's parts, or None for a
#: pass. Every row is what the phone's `_patched_review_recovery` gave on 3c9b6779: a band MTPD is
#: held at its upper edge, the refusal names the band the record carries, and the edge is a part.
PHONE_BAND_VERDICTS = [
    ("< 4 h", "0–4 h", {}, None),
    ("4 h", "0–4 h", {}, {"target": "4 h", "mtpd": "0–4 h", "edge": "4 h"}),
    ("8 h", "0-4 h", {}, {"target": "8 h", "mtpd": "0-4 h", "edge": "4 h"}),
    ("2–6 h", "0–4 h (grid)", {}, {"target": "2–6 h", "mtpd": "0–4 h (grid)", "edge": "4 h"}),
    ("5 hours", "0 – 4 hours", {},
     {"target": "5 hours", "mtpd": "0 – 4 hours", "edge": "4 hours"}),
    ("3 days", "1-2 days", {}, {"target": "3 days", "mtpd": "1-2 days", "edge": "2 days"}),
    ("5 h", None, {"mtpd": "0–4 h"}, {"target": "5 h", "mtpd": "0–4 h", "edge": "4 h"}),
    ("5 h", "0–4 h", {"mtpd": "24 h"}, None),
    ("30 h", "0–4 h", {"mtpd": "24 h"}, {"target": "30 h", "mtpd": "24 h"}),
    ("5 h", "1–3 days", {"mtpd": "garbage"}, None),
    ("5 h", "0–4 h", {"recovery_gap_flagged": True}, None),
    ("8 h", "24 h", {}, None),
    ("25 h", "24 h", {}, {"target": "25 h", "mtpd": "24 h"}),
    ("5 h", "4 h", {}, {"target": "5 h", "mtpd": "4 h"}),
    ("5 h", "garbage", {}, None),
    # an em dash is a band to `upper_edge` and no duration to `minutes`: the record's still wins
    ("5 h", "24 h", {"mtpd": "0—4 h"}, {"target": "5 h", "mtpd": "0—4 h", "edge": "4 h"}),
    ("3 h", "0—4 h", {}, None),
    # a band behind "<" is no band to `upper_edge`, so it keeps `minutes`' reading and no edge
    ("1 h", "< 0–4 h", {}, {"target": "1 h", "mtpd": "< 0–4 h"}),
]


@pytest.mark.parametrize("target, mtpd, carried, refused", PHONE_BAND_VERDICTS)
def test_a_band_mtpd_is_held_at_its_upper_edge_as_the_phone_holds_it(
        target: str, mtpd: str | None, carried: dict, refused: dict | None) -> None:
    """t74, the owner's ruling (2026-09-18): "back within 4 hours" is not inside "0–4 h", and
    "< 4 h" is. The refusal says the band, so the card can say why from the record's figures."""
    verdict = Verdict()
    referee._review_recovery(verdict, "A0", {"recovery_target": target, **carried}, mtpd)
    if refused is None:
        assert verdict.rejections == []
        return
    [rejection] = verdict.rejections
    assert (rejection.kind, dict(rejection.parts)) == (
        TARGET_OUTSIDE_MTPD, {"activity": "A0", **refused})
    assert str(rejection) == (
        f"activity A0: recovery target {target} is not strictly inside the MTPD "
        f"{refused['mtpd']} — close the gap, or acknowledge it deliberately with "
        "recovery_gap_flagged")
    assert list(rejection.parts) == ["activity", *refused]  # the edge last, as the phone has it


def test_a_band_mtpd_still_runs_the_rto_check() -> None:
    verdict = Verdict()
    referee._review_recovery(verdict, "A0", {"recovery_target": "< 4 h"}, "0–4 h")
    assert verdict.checked == [RTO_CHECK]
