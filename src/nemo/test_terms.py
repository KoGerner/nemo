"""Ticket 107: abbreviations and method terms named the first time a text uses them.

What the manager reads is held to the junior-manager standard (round 2, r2-02, r2-04, r2-12, r2-37):
"NTV" alone means nothing to him, "NTV (the logistics company that collects slaughter waste)" does.
The naming is a rendering of tables, never a check on what the model wrote (M13), so it is tested
as a pure function over model-shaped text.
"""

import re
from collections.abc import Callable

import pytest

from nemo import terms
from nemo.terms import METHOD_TERMS, abbreviations, glossary, name_first_uses, undefined

NTV_NAMED = "NTV (the logistics company that collects slaughter waste)"
ROOM = {"NTV": "the logistics company that collects slaughter waste", "ABP": "animal by-products"}


def named(text: str, table: dict[str, str] | None = None,
          already: frozenset[str] = frozenset()) -> str:
    return name_first_uses(text, ROOM if table is None else table, already)[0]


# ── first use only ────────────────────────────────────────────────────────────────────────────────
def test_a_term_used_twice_is_named_the_first_time_only() -> None:
    assert named("NTV collects it. If NTV is late, the cold store fills.") == (
        "NTV (the logistics company that collects slaughter waste) collects it. "
        "If NTV is late, the cold store fills.")


def test_each_term_is_named_at_its_own_first_use() -> None:
    assert named("ABP go to NTV. NTV takes the ABP.") == (
        "ABP (animal by-products) go to NTV (the logistics company that collects slaughter waste). "
        "NTV takes the ABP.")


def test_the_terms_it_named_are_returned_so_a_turn_can_carry_them_on() -> None:
    text, used = name_first_uses("NTV only.", ROOM)
    assert used == frozenset({"NTV"})
    assert name_first_uses("NTV again.", ROOM, used) == ("NTV again.", used)


def test_a_term_already_named_earlier_in_the_turn_stays_bare() -> None:
    assert named("NTV and ABP.", already=frozenset({"NTV"})) == "NTV and ABP (animal by-products)."


def test_text_with_no_term_comes_back_as_it_was() -> None:
    assert name_first_uses("Nothing here.", ROOM) == ("Nothing here.", frozenset())


def test_an_empty_table_names_nothing() -> None:
    assert name_first_uses("NTV here.", {}) == ("NTV here.", frozenset())


# ── never inside someone's words, a code span or a link ──────────────────────────────────────────
def test_a_model_shaped_answer_names_ntv_outside_the_quote_and_leaves_the_quote_whole() -> None:
    """Amendment 1 (11_nemo_check): NTV twice, the first time inside the interviewee's words."""
    answer = ('Ms Louven said “if NTV does not come, we stop cutting”. So NTV is the dependency to '
              'look at first.')
    assert named(answer) == (
        'Ms Louven said “if NTV does not come, we stop cutting”. So NTV (the logistics company '
        'that collects slaughter waste) is the dependency to look at first.')


def test_a_straight_quote_is_left_whole_too() -> None:
    assert named('He said "NTV is late" and NTV is late.') == (
        f'He said "NTV is late" and {NTV_NAMED} is late.')


def test_a_code_span_and_a_fenced_block_are_left_whole() -> None:
    kept = "`NTV` and\n```\nNTV\n```\nthen "
    assert named(kept + "ABP") == kept + "ABP (animal by-products)"


def test_a_blockquote_is_left_whole_and_the_same_term_after_it_is_named() -> None:
    """Fix round 1 (12_nemo_check): nemo draws an interviewee's words as "> " lines on a card."""
    card = ("**Side 1 · Wohlleben**\n\n> If NTV does not come,  \n>NTV means the ABP pile up\n\n"
            "So NTV sets the pace.")
    assert named(card) == (
        "**Side 1 · Wohlleben**\n\n> If NTV does not come,  \n>NTV means the ABP pile up\n\n"
        f"So {NTV_NAMED} sets the pace.")


def test_a_greater_than_inside_a_line_is_not_a_blockquote() -> None:
    assert named("a > NTV") == f"a > {NTV_NAMED}"


def test_a_link_and_a_bare_address_are_left_whole() -> None:
    links = "[NTV](https://x.example/NTV) <https://NTV.example> https://y.example/NTV done"
    assert named(links) == links


# ── a term the text already names, and a term that is part of something longer ───────────────────
def test_a_term_followed_by_its_own_bracket_is_not_named_twice() -> None:
    said = "NTV (the renderer) comes daily; NTV is late."
    assert named(said) == said
    assert named("NTV(renderer) today") == "NTV(renderer) today"


def test_a_term_inside_a_bracket_after_its_name_is_not_named_again() -> None:
    assert named("animal by-products (ABP) and ABP") == "animal by-products (ABP) and ABP"


def test_a_space_before_the_bracket_is_one_space_only() -> None:
    """t444: two spaces before a bracket do not make it the term's own, and a gloss there would
    stand back to back with it, so the term stays bare and is glossed at its next use."""
    assert named("NTV  (x) next, NTV") == f"NTV  (x) next, {NTV_NAMED}"


def test_a_term_inside_a_code_word_or_a_path_is_not_a_use() -> None:
    table = {"SUP": "supply", "MTPD": "m"}
    for text in ("R-SUP-03", "SUP-03", "x/SUP", "a.SUP", "SUPPLY", "XSUP", "SUP_1", "MTPD-RULE",
                 "SUP+", "+SUP"):
        assert named(text, table) == text, text


def test_a_term_ending_a_sentence_or_in_brackets_is_a_use() -> None:
    assert named("the ABP.") == "the ABP (animal by-products)."
    assert named("[ABP]") == "[ABP (animal by-products)]"


def test_an_abbreviation_matches_only_as_written() -> None:
    assert named("abp and Abp") == "abp and Abp"


def test_a_lower_case_term_matches_in_any_case_and_keeps_his_spelling() -> None:
    table = {"safety buffer": "the margin kept back"}
    assert named("A Safety Buffer and a safety buffer.", table) == (
        "A Safety Buffer (the margin kept back) and a safety buffer.")


def test_the_longer_term_wins_over_the_one_inside_it() -> None:
    table = {"MTPD": "how long", "MTPD anchor": "the first intolerable point"}
    assert named("The MTPD anchor sets the MTPD.", table) == (
        "The MTPD anchor (the first intolerable point) sets the MTPD (how long).")


def test_the_longer_term_wins_by_length_not_by_spelling() -> None:
    """A capital sorts before a small letter, so only the length puts the longer one first here."""
    table = {"canonical": "the agreed one", "Canonical MTPD": "the one limit that counts"}
    assert named("Canonical MTPD", table) == "Canonical MTPD (the one limit that counts)"


def test_a_term_with_a_plus_in_it_is_named() -> None:
    assert named("N+1 cooling", {"N+1": "one spare"}) == "N+1 (one spare) cooling"


# ── nemo's own table: method terms only, in plain words ──────────────────────────────────────────
def test_the_method_table_holds_the_clocks_in_plain_words() -> None:
    assert METHOD_TERMS["MTPD"] == (
        "how long the activity can be down before the damage is intolerable")
    assert {"BIA", "BCM", "RTO", "RPO", "MBCO", "SPOF", "N+1", "safety buffer",
            "intolerability threshold", "MTPD anchor", "grid-derived",
            "canonical MTPD"} <= set(METHOD_TERMS)


def test_the_method_table_is_exactly_these_words() -> None:
    """Plain words are the owner's tiebreak (plain beats precise); changing one is a decision."""
    assert dict(METHOD_TERMS) == {
        "BIA": "business impact analysis: what a stop does to the organisation over time",
        "BCM": "business continuity management",
        "BC": "business continuity",
        "MTPD": "how long the activity can be down before the damage is intolerable",
        "RTO": "how soon the activity must be back at its agreed minimum level",
        "RPO": "how far back the information it uses may be restored",
        "MBCO": "the least the activity must still deliver while it is disrupted",
        "SPOF": "single point of failure: one thing whose loss stops the activity",
        "N+1": "one spare beyond what is needed",
        "PIR": "post-incident review",
        "intolerability threshold": "the score at which a stop is no longer tolerable",
        "safety buffer": "the margin kept between how soon it must be back and how long it can "
                         "be down",
        "MTPD anchor": "the first point in time at which a stop becomes intolerable",
        "grid-derived": "worked out from the impact scores over time",
        "canonical MTPD": "the one limit that counts: the tightest of all that apply",
    }


# ── t215: the standard's own words, named once per conversation ──────────────────────────────────
def test_the_standards_own_words_are_marked_standard() -> None:
    """t215, on the owner's 2026-09-28T20:43:33Z words ("basic terms such as BCM, RPO, etc must not
    always be explained in ()"): these seven are the standard's own, named once per conversation."""
    assert terms.STANDARD_TERMS == frozenset({"BCM", "BC", "BIA", "MTPD", "RTO", "RPO", "MBCO"})
    assert terms.STANDARD_TERMS <= set(METHOD_TERMS)


def test_the_coined_terms_and_the_less_basic_abbreviations_are_not_standard() -> None:
    """107's naming stands for everything else: SPOF, N+1 and PIR (ticket 64's beginners) and
    nemo's own coined terms are still named at their first use in each turn."""
    assert set(METHOD_TERMS) - terms.STANDARD_TERMS == {
        "SPOF", "N+1", "PIR", "intolerability threshold", "safety buffer", "MTPD anchor",
        "grid-derived", "canonical MTPD"}


def test_a_standard_word_handed_in_as_already_named_stays_bare() -> None:
    """The conversation's own set is handed to `name_first_uses` as `already`, like a turn's."""
    text, used = name_first_uses("The MTPD anchor sits before the MTPD.", METHOD_TERMS,
                                 frozenset({"MTPD"}))
    assert text == f"The MTPD anchor ({METHOD_TERMS['MTPD anchor']}) sits before the MTPD."
    assert used == frozenset({"MTPD", "MTPD anchor"})


def test_no_meaning_in_the_method_table_carries_an_abbreviation_or_a_figure() -> None:
    """A bracket that needs its own bracket names nothing; a digit would meet the figure check."""
    for term, meaning in METHOD_TERMS.items():
        assert not abbreviations(meaning), term
        assert not any(ch.isdigit() for ch in meaning), term


# ── the room's glossary file ─────────────────────────────────────────────────────────────────────
def test_the_glossary_is_read_from_its_bullets() -> None:
    text = ("# Glossary\n\nSome words.\n\n"
            "- **NTV**: the logistics company that collects slaughter waste\n"
            "* **ABP**:   animal by-products  \n- not an entry\n- **odd** no colon\n")
    assert glossary(text) == {"NTV": "the logistics company that collects slaughter waste",
                              "ABP": "animal by-products"}


def test_the_glossary_file_sits_in_the_organisation_folder() -> None:
    assert terms.GLOSSARY == "01_Organisation/glossary.md"


# ── the completeness check: every abbreviation a room's files use has a name ─────────────────────
def test_abbreviations_are_capitals_of_two_or_more() -> None:
    said = "NTV takes ABP, HACCP-01 is a code, PP4 and NH3 and N+1; a P1 and an A."
    assert abbreviations(said) == {"NTV", "ABP", "PP4", "NH3", "N+1"}


def test_roman_numerals_shouted_words_and_placeholders_are_not_abbreviations() -> None:
    assert abbreviations("Annex II, III and IV. NOT YET RE-ASSESSED, OPTIONAL, TEST FILE, "
                         "DD Mon YYYY, NO backup, PER ACTIVITY, RECOVERY GAP, AND OR MM, "
                         "STATUS, CCP") == {"CCP"}


def test_a_long_run_of_capitals_with_a_digit_is_still_an_abbreviation() -> None:
    assert abbreviations("FY2025 and EUROP") == {"FY2025", "EUROP"}


def test_undefined_lists_what_no_table_names_sorted() -> None:
    texts = ["NTV collects ABP.", "The MTPD and the ZQX and the ERP."]
    assert undefined(texts, ROOM) == ["ERP", "MTPD", "ZQX"]
    assert undefined(texts, {**ROOM, **METHOD_TERMS, "ERP": "x", "ZQX": "y"}) == []


def test_naming_is_pure(seal: Callable[[], None]) -> None:
    seal()
    assert named("NTV") == "NTV (the logistics company that collects slaughter waste)"
    assert glossary("- **A**: b") == {"A": "b"}
    assert undefined(["QQ"], {}) == ["QQ"]


# ── t377 M: a gloss never lands inside a quoted item name ────────────────────────────────────────
#: the m5-seed wording (12_marschkamp), the test's own table: never read from a seed
NAMED_ROOM = {"CSB": "the business software used at the Marschkamp site, named after its maker",
              "ERP": "the business software for orders, stock and invoices"}
STANDBY_NAME, ERP_NAME = "CSB standby at Breitenburg", "CSB ERP Marschkamp"
CSB_SAID = "CSB: the business software used at the Marschkamp site, named after its maker"
ERP_SAID = "ERP: the business software for orders, stock and invoices"


def in_names(text: str, already: frozenset[str] = frozenset()) -> tuple[str, frozenset[str]]:
    return name_first_uses(text, NAMED_ROOM, already, names=(STANDBY_NAME, ERP_NAME))


def test_red_first_a_gloss_goes_after_the_whole_name_once() -> None:
    """(1): the add-tap echo quotes the name unbroken, its term's gloss after it."""
    for head in ("Added:", "Noted:"):
        said, _ = in_names(f"{head} CSB standby at Breitenburg is a dependency of production.")
        assert said == (f"{head} CSB standby at Breitenburg ({CSB_SAID}) is a dependency of "
                        "production.")


def test_a_name_that_extends_another_is_kept_whole() -> None:
    """The longer of two names starting alike wins, whichever order they are given in."""
    for names in (("CSB ERP", ERP_NAME), (ERP_NAME, "CSB ERP")):
        said, _ = name_first_uses("Last year: CSB ERP Marschkamp failed.", NAMED_ROOM, names=names)
        assert said == f"Last year: CSB ERP Marschkamp ({CSB_SAID}; {ERP_SAID}) failed."


def test_red_first_every_gloss_of_one_name_goes_in_one_bracket_after_it() -> None:
    """(2): two terms in one name, one bracket, `TERM: meaning` joined by '; ', in order."""
    said, used = in_names("   Last year: CSB ERP Marschkamp, “orders on paper”")
    assert said == f"   Last year: CSB ERP Marschkamp ({CSB_SAID}; {ERP_SAID}), “orders on paper”"
    assert used == frozenset({"CSB", "ERP"})


def test_a_term_glossed_inside_a_name_counts_as_used_and_a_bare_first_use_is_as_before() -> None:
    """(3): outside a name, the gloss follows the term; a second use stays bare either way."""
    assert in_names("CSB ERP Marschkamp is down; CSB calls back.")[0] == (
        f"CSB ERP Marschkamp ({CSB_SAID}; {ERP_SAID}) is down; CSB calls back.")
    assert in_names("CSB calls. CSB ERP Marschkamp is down.")[0] == (
        f"CSB ({NAMED_ROOM['CSB']}) calls. CSB ERP Marschkamp ({ERP_SAID}) is down.")
    assert in_names("CSB ERP Marschkamp.", frozenset({"CSB", "ERP"}))[0] == "CSB ERP Marschkamp."


def test_a_name_in_a_quote_a_code_span_or_a_link_is_never_glossed() -> None:
    """(4)."""
    for kept in ("“CSB ERP Marschkamp”", "`CSB ERP Marschkamp`", "[CSB ERP Marschkamp](x.md)"):
        assert in_names(f"See {kept}.") == (f"See {kept}.", frozenset())


def test_a_name_the_text_glosses_itself_is_not_glossed_again() -> None:
    once = f"CSB ERP Marschkamp ({CSB_SAID}; {ERP_SAID}) is down."
    assert in_names(once)[0] == once


def test_without_names_a_term_is_glossed_where_it_stands_as_before() -> None:
    assert name_first_uses("CSB standby at Breitenburg.", NAMED_ROOM)[0] == (
        f"CSB ({NAMED_ROOM['CSB']}) standby at Breitenburg.")


# ── t438: the pattern for one term table is built once, not for every string ─────────────────────
NAMED_ITEMS = (STANDBY_NAME, ERP_NAME)


@pytest.fixture(autouse=True)
def built_afresh() -> None:
    """Each test builds its own patterns: none comes from an earlier test or a forked parent."""
    terms._pattern_of.cache_clear()
    terms._names_pattern_of.cache_clear()


def compiles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every `re.compile` from here on, by its pattern: a build of a term or name pattern."""
    built: list[str] = []
    real = re.compile

    def spy(pattern: str, flags: int = 0) -> re.Pattern[str]:
        built.append(pattern)
        return real(pattern, flags)

    monkeypatch.setattr(re, "compile", spy)
    return built


def test_red_first_one_term_table_builds_its_patterns_once_across_many_strings(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """431's profile: room_state's result has hundreds of strings, and each rebuilt the same regex
    (32% of CPU). The same table and names, string after string, build nothing after the first."""
    built = compiles(monkeypatch)
    strings = [f"CSB ERP Marschkamp is down for {n} hours; CSB calls back." for n in range(50)]
    name_first_uses(strings[0], NAMED_ROOM, names=NAMED_ITEMS)
    first = len(built)
    assert first
    for s in strings[1:]:
        name_first_uses(s, NAMED_ROOM, names=list(NAMED_ITEMS))
    assert len(built) == first


def test_a_changed_term_table_or_name_set_builds_new_patterns(
        monkeypatch: pytest.MonkeyPatch) -> None:
    built = compiles(monkeypatch)
    text = "CSB ERP Marschkamp is down; CSB calls back."
    before = name_first_uses(text, NAMED_ROOM, names=NAMED_ITEMS)
    seen = len(built)
    grown = {**NAMED_ROOM, "TMS": "the transport management system"}
    assert name_first_uses(text + " TMS too.", grown, names=NAMED_ITEMS)[0].endswith(
        f"TMS ({grown['TMS']}) too.")
    assert len(built) > seen
    seen = len(built)
    assert name_first_uses(text, NAMED_ROOM, names=("CSB ERP",))[0] != before[0]
    assert len(built) > seen
    assert name_first_uses(text, NAMED_ROOM, names=NAMED_ITEMS) == before


# ── t444 (his A, 2026-10-12T15:49:43Z): after the bold, never nested ─────────────────────────────
def test_red_first_a_bold_names_gloss_goes_after_the_bold_all_terms_in_one_bracket() -> None:
    said, used = in_names("**CSB ERP Marschkamp**: not stated")
    assert said == f"**CSB ERP Marschkamp** ({CSB_SAID}; {ERP_SAID}): not stated"
    assert used == frozenset({"CSB", "ERP"})
    assert named("- **ABP pile**: none") == "- **ABP pile** (ABP: animal by-products): none"


def test_red_first_a_heading_carries_none_and_its_term_is_glossed_at_its_next_plain_use() -> None:
    for heading in ("**ABP pile**\n", "**ABP pile** · from the register\n", "## ABP pile\n"):
        assert named(heading + "The ABP wait.") == heading + "The ABP (animal by-products) wait."
    assert name_first_uses("**ABP pile**", ROOM) == ("**ABP pile**", frozenset())


def test_red_first_a_term_inside_another_bracket_is_glossed_at_its_first_bare_use() -> None:
    said, used = in_names("(owner: CSB ERP Marschkamp) and (CSB standby). Then CSB again.")
    assert said == ("(owner: CSB ERP Marschkamp) and (CSB standby). "
                    f"Then CSB ({NAMED_ROOM['CSB']}) again.")
    assert used == frozenset({"CSB"})
    assert named("**ABP pile** (owner: NTV team) and NTV.") == (
        f"**ABP pile** (ABP: {ROOM['ABP']}; owner: NTV team) and {NTV_NAMED}.")


def test_red_first_never_two_brackets_back_to_back() -> None:
    said, used = name_first_uses("CSB ERP Marschkamp (2 sites), then CSB.", NAMED_ROOM,
                                 names=(ERP_NAME,))
    assert said == f"CSB ERP Marschkamp (2 sites), then CSB ({NAMED_ROOM['CSB']})."
    assert used == frozenset({"CSB"})
    assert named("**ABP pile** (2 t) and ABP.") == (
        "**ABP pile** (2 t) and ABP (animal by-products).")


# ── t444 r2 (37_nemo_check's FORM FINAL 2026-10-13 00:21:44): one bracket, beside the owner ─────
def test_red_first_a_bold_names_gloss_goes_first_in_the_owner_bracket_after_it() -> None:
    said, used = in_names("- Not stated for: **CSB ERP Marschkamp** (owner: Head of IT)")
    assert said == (f"- Not stated for: **CSB ERP Marschkamp** ({CSB_SAID}; {ERP_SAID}; "
                    "owner: Head of IT)")
    assert used == frozenset({"CSB", "ERP"})


def test_an_owner_bracket_after_a_bold_name_with_no_new_term_stays_as_it_is() -> None:
    for text, already in (("**CSB ERP Marschkamp** (owner: x)", frozenset({"CSB", "ERP"})),
                          ("**Power supply** (owner: x)", frozenset())):
        assert in_names(text, already) == (text, already)


def test_a_term_inside_the_owner_bracket_is_still_glossed_at_its_first_bare_use() -> None:
    assert named("**ABP pile** (owner: NTV team)\n**ABP**\nThe NTV wait.") == (
        f"**ABP pile** (ABP: {ROOM['ABP']}; owner: NTV team)\n**ABP**\nThe {NTV_NAMED} wait.")


def test_an_owner_bracket_that_names_its_own_term_counts_it_as_used() -> None:
    assert named("**ABP pile** (owner: x; NTV: the renderer)\nNTV calls.") == (
        f"**ABP pile** (ABP: {ROOM['ABP']}; owner: x; NTV: the renderer)\nNTV calls.")


def test_a_bold_names_own_bracket_still_names_its_term_beside_the_owner() -> None:
    assert named("**ABP pile (ABP)** (owner: x) and NTV.") == (
        f"**ABP pile (ABP)** (owner: x) and {NTV_NAMED}.")


def test_a_heading_line_ending_in_an_owner_bracket_is_a_row_and_carries_the_gloss() -> None:
    assert named("**ABP pile** (owner: x)\nABP.") == (
        f"**ABP pile** (ABP: {ROOM['ABP']}; owner: x)\nABP.")


def test_only_an_owner_bracket_takes_the_gloss_any_other_still_waits() -> None:
    for other in ("(deputy: x)", "(owner x)", "(2 t)"):
        assert named(f"**ABP pile** {other} and ABP.") == (
            f"**ABP pile** {other} and ABP ({ROOM['ABP']}).")
    assert named("**ABP pile**  (owner: x) and ABP.") == (
        f"**ABP pile**  (owner: x) and ABP ({ROOM['ABP']}).")


def test_a_bracket_the_text_writes_for_its_own_terms_names_them() -> None:
    once = f"Its CSB ERP Marschkamp ({CSB_SAID}; {ERP_SAID}) and **ABP** (ABP: animal by-products)."
    assert name_first_uses(once, {**NAMED_ROOM, **ROOM}, names=(ERP_NAME,)) == (
        once, frozenset({"CSB", "ERP", "ABP"}))


def test_control_a_term_met_only_in_plain_prose_is_glossed_once_where_it_stands() -> None:
    assert named("NTV calls (twice). NTV again.") == f"{NTV_NAMED} calls (twice). NTV again."


def test_a_bold_line_after_other_lines_is_a_heading_too() -> None:
    assert named("Intro.\n**ABP pile**\nThe ABP wait.") == (
        "Intro.\n**ABP pile**\nThe ABP (animal by-products) wait.")


def test_a_bracket_that_ends_its_line_still_names_its_term() -> None:
    assert name_first_uses("(ABP)\nThe ABP wait.", ROOM) == ("(ABP)\nThe ABP wait.",
                                                              frozenset({"ABP"}))


def test_a_bracket_inside_a_bold_name_names_its_term_and_nothing_else_does() -> None:
    assert name_first_uses("**ABP pile (ABP)** and ABP.", ROOM) == (
        "**ABP pile (ABP)** and ABP.", frozenset({"ABP"}))
    assert named("**ABP(s) pile** and ABP.") == (
        "**ABP(s) pile** (ABP: animal by-products) and ABP.")


def test_a_term_in_a_bracket_that_holds_another_is_glossed_at_its_first_bare_use() -> None:
    """t444: the outer bracket is no shelter (it holds one), but a gloss there would nest."""
    assert name_first_uses("(ABP and (2 t)). Then ABP.", ROOM) == (
        "(ABP and (2 t)). Then ABP (animal by-products).", frozenset({"ABP"}))


def test_two_names_in_one_run_keep_the_text_between_them() -> None:
    said, used = in_names(f"Before {ERP_NAME} and {STANDBY_NAME}.")
    assert said == f"Before {ERP_NAME} ({CSB_SAID}; {ERP_SAID}) and {STANDBY_NAME}."
    assert used == frozenset({"CSB", "ERP"})
