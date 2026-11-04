"""The machine's counts, each on a fixture answer it must catch and one it must leave alone.

Ticket 123 (ADR-0029 F). Every count is advisory and never a gate (M13, ADR-0023): these tests
pin what each count *finds*, never that an answer passes. `invented_figure` is not here on purpose:
it is the skin's `_flag`, called as it is (12_nemo_check's amendment), so the chat and the count
can never disagree about what a figure is.
"""

from collections.abc import Callable

import pytest

from nemo import counts

GUIDANCE_URL = "https://github.com/AI4BCM/guidance/blob/2026.11.1/units/glossary.md#glossary"
DEAD_URL = "https://github.com/AI4BCM/guidance/blob/2026.11.1/units/glossary.md#no-such-section"

#: The shape the chat serves under a guidance answer (`skin/PROTOTYPE_core.py`, `guidance_block`).
SERVED = ("The recovery point is set by the process owner.\n\n"
          "*Answered from AI4BCM Guidance · Release 2026.11.1*\n"
          f"1. [Glossary]({GUIDANCE_URL}) — *glossary*")


@pytest.mark.parametrize(("tools", "where"), [
    (["list_room_files", "read_room_file"], "files"),
    (["ask_guidance"], "guidance"),
    (["read_room_file", "ask_guidance"], "both"),
    ([], "neither"),
])
def test_went_where_reads_the_tools_the_answer_called(tools: list[str], where: str) -> None:
    assert counts.went_where(tools) == where


def test_an_anti_slop_word_is_caught_whole_and_in_any_case() -> None:
    words = ["delve", "robust", "Moreover", "at its core"]
    answer = ("Moreover, let us DELVE into it: at its core the plan is sound. "
              "Robustness is not listed.")
    assert counts.ai_words(answer, words) == ["Moreover", "at its core", "delve"]


def test_an_answer_with_no_listed_word_counts_none() -> None:
    assert counts.ai_words("The cutting line can stop for 24 h.", ["delve", "robust"]) == []
    assert counts.ai_words("The deleverage plan stands.", ["leverage"]) == []


def test_an_answer_that_never_read_the_guidance_has_no_sources_to_count() -> None:
    assert counts.sources(SERVED, ["read_room_file"], {GUIDANCE_URL}) is None


def test_a_present_source_line_whose_link_the_corpus_holds() -> None:
    assert counts.sources(SERVED, ["ask_guidance"], {GUIDANCE_URL}) == {
        "source_line": True, "links": [{"url": GUIDANCE_URL, "resolves": True}]}


def test_a_missing_source_line_is_said_to_be_missing() -> None:
    assert counts.sources("The recovery point is set by the process owner.", ["ask_guidance"],
                          {GUIDANCE_URL}) == {"source_line": False, "links": []}


def test_a_dead_link_does_not_resolve() -> None:
    answer = SERVED.replace(GUIDANCE_URL, DEAD_URL)
    assert counts.sources(answer, ["ask_guidance"], {GUIDANCE_URL}) == {
        "source_line": True, "links": [{"url": DEAD_URL, "resolves": False}]}


def test_a_link_in_prose_is_counted_but_is_no_source_line() -> None:
    answer = f"See [the glossary]({GUIDANCE_URL}) for the term."
    assert counts.sources(answer, ["ask_guidance"], {GUIDANCE_URL}) == {
        "source_line": False, "links": [{"url": GUIDANCE_URL, "resolves": True}]}


def test_iso_22301_is_named_outside_the_corpus_and_nist_sp_800_34_is_not() -> None:
    said = "ISO 22301 asks for a BIA; so does NIST SP 800-34."
    assert counts.outside_references(said) == ["ISO 22301"]
    assert counts.outside_references("NIST SP 800-34 and DORA both ask for one.") == []


@pytest.mark.parametrize(("said", "named"), [
    ("ISO/TS 22317 describes the BIA.", "ISO/TS 22317"),
    ("The BCI Good Practice Guidelines say so.", "the BCI Good Practice Guidelines"),
    ("ISO 22313 is the guidance to 22301's requirements.", "ISO 22313"),
    ("Risk sits in ISO 31000.", "ISO 31000"),
    ("Information security is ISO/IEC 27001.", "ISO/IEC 27001"),
    ("The old BS 25999 said the same.", "BS 25999"),
    ("In the US, NFPA 1600 is the standard.", "NFPA 1600"),
])
def test_each_name_on_the_fixed_list_is_flagged(said: str, named: str) -> None:
    assert named in counts.outside_references(said)


@pytest.mark.parametrize("said", [
    "The outage cost EUR 131000 in the first day.",
    "The invoice came to 22301000.",
    "The figure is 222313.",
    "goods on ramp 25999a went out.",
])
def test_a_figure_that_merely_contains_a_standards_number_is_not_a_reference(said: str) -> None:
    """Ticket 210 (5): the marks were matched as bare substrings, so `EUR 131000` counted as
    ISO 31000. The whole-word match `ai_words` uses beside it is the one this needs too."""
    assert counts.outside_references(said) == []


def test_a_name_that_runs_up_against_punctuation_is_still_a_reference() -> None:
    assert counts.outside_references("(ISO 22301), ISO 31000: risk.") == ["ISO 22301", "ISO 31000"]


def test_the_counts_reach_neither_disk_nor_clock_nor_network(seal: Callable[[], None]) -> None:
    seal()
    assert counts.went_where(["ask_guidance"]) == "guidance"
    assert counts.ai_words("delve", ["delve"]) == ["delve"]
    assert counts.sources(SERVED, ["ask_guidance"], {GUIDANCE_URL}) is not None
    assert counts.outside_references("ISO 22301") == ["ISO 22301"]
