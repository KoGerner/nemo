import io
import re
import tokenize
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from nemo.card import (
    CardGeneratorBug,
    _alternation,
    _held_text,
    _name_spans,
    _outside_the_names,
    _searchable,
    _untraceable_words,
    render,
    render_walk,
    untraceable,
)

MTPD_8H = {"revision": 3, "activities": [{"id": "BIA-2026-002", "name": "Cutting / deboning",
                                         "mtpd": "8 h", "recovery_target": "8 h"}]}
MBCO = {"activities": [{"name": "Cutting / deboning",
                        "mbco": "50% cutting capacity, A-customers only, one shift; "
                                "approximately 45 cutters, two foremen"}]}
GRID = {"activities": [{"name": "Cutting / deboning", "mtpd": "8 h",
                        "impact_grid": {"customer-delivery": {"8 h": 4, "48 h": 5}}}]}


# ── the one test: the figure on the card is a string the record holds ────────
def test_a_figure_the_record_holds_passes():
    assert untraceable("MTPD 8 h — the legal/regulatory impact reaches the threshold at 8 h",
                       MTPD_8H) == []


def test_a_figure_said_in_words_is_not_a_string_the_record_holds():
    assert untraceable("about a working day", MTPD_8H) == ["a working day"]


def test_a_softened_figure_is_named_with_the_word_that_softened_it():
    assert untraceable("the MTPD is about 8 h", MTPD_8H) == ["about 8h"]


def test_invented_precision_fails_like_vagueness():
    assert untraceable("Cutting's MTPD is 8 h 15 m", MTPD_8H) == ["15m"]


def test_a_figure_nobody_put_in_the_record_fails():
    assert untraceable("The RTO is 12 h", MTPD_8H) == ["12h"]


def test_dropping_the_records_own_qualifier_invents_precision():
    assert untraceable("The MBCO is 45 cutters", MBCO) == ["45"]


def test_the_records_own_hedge_is_not_the_cards_hedge():
    assert untraceable("approximately 45 cutters — that 'approximately' is Petra Louven's word, "
                       "not a rounding of mine", MBCO) == []


def test_a_softened_severity_fails_like_a_softened_figure():
    assert untraceable("Cutting is fairly critical and gets worse the longer it's down",
                       GRID) == ["fairly critical"]


def test_a_score_the_grid_holds_passes():
    assert untraceable("Cutting scores 4 of 5 on customer and delivery reliability at 8 h, "
                       "and 5 at 48 h", GRID) == []


def test_ordinary_english_away_from_a_figure_is_not_vagueness():
    record = {"activities": [{"name": "Slaughter process", "mtpd": "24 h"}]}
    assert untraceable("There's a question about scope I'd like you to settle, and Slaughter's "
                       "MTPD is 24 h", record) == []


def test_a_card_carrying_no_figure_at_all_has_nothing_to_trace():
    assert untraceable("Got it. The scope for Slaughter is agreed.", MTPD_8H) == []


def test_typography_is_tolerated_but_the_figure_is_not_reworded():
    assert untraceable("the MTPD is 8h", MTPD_8H) == []


def test_a_word_the_record_itself_uses_about_a_figure_is_traceable():
    record = {"activities": [{"quote": "eight hours is fairly critical, I'd say"}]}
    assert untraceable("Cutting is fairly critical", record) == []


def test_a_path_on_a_source_line_is_not_read_as_a_figure():
    record = {"activities": [{"evidence": [{"source_path": "07_Interviews/26_08_03_cutting.md"}]}]}
    assert untraceable("Source: 07_Interviews/26_08_03_cutting.md", record) == []


def test_every_untraceable_string_is_named_not_only_the_first():
    assert untraceable("The MTPD is roughly 12 h and Cutting is fairly critical",
                       MTPD_8H) == ["fairly critical", "roughly 12h"]


def test_a_record_that_is_wrong_about_the_world_still_passes():
    record = {"activities": [{"name": "CIP cleaning", "mtpd": "no MTPD within horizons"}] * 7}
    assert untraceable("CIP cleaning has no MTPD within the horizons your method covers",
                       record) == []


# ── the mechanism: the check is the door, and a failure is a bug ─────────────
def test_a_card_that_traces_is_rendered_unchanged():
    card = "Cutting's MTPD is 8 h."
    assert render(4, card, MTPD_8H) == card


def test_a_card_that_does_not_trace_renders_nothing_at_all():
    with pytest.raises(CardGeneratorBug) as refusal:
        render(4, "The MTPD is about a working day.", MTPD_8H)
    assert refusal.value.stage == 4
    assert refusal.value.strings == ["a working day"]


def test_the_refusal_is_a_bug_in_the_card_generator_and_not_a_finding():
    with pytest.raises(CardGeneratorBug) as refusal:
        render(2, "The MTPD is about a working day.", MTPD_8H)
    message = str(refusal.value)
    assert "bug in the card generator at stage 2" in message
    assert "'a working day'" in message
    assert "finding" not in message.lower()


def test_the_refusal_names_the_record_it_was_checked_against():
    with pytest.raises(CardGeneratorBug) as refusal:
        render(1, "roughly a day", MTPD_8H)
    assert "revision 3" in str(refusal.value)
    assert "BIA-2026-002" in str(refusal.value)


def test_every_stage_of_a_walk_is_checked():
    cards = [f"Stage {n} of 5: Cutting's MTPD is 8 h." for n in range(1, 6)]
    assert render_walk(cards, MTPD_8H) == cards


def test_one_untraceable_card_stops_the_walk_at_the_stage_that_wrote_it():
    for broken in range(5):
        cards = ["Cutting's MTPD is 8 h."] * 5
        cards[broken] = "The MTPD is about a working day."
        with pytest.raises(CardGeneratorBug) as refusal:
            render_walk(cards, MTPD_8H)
        assert refusal.value.stage == broken + 1


def test_an_unnamed_activity_still_identifies_the_record():
    with pytest.raises(CardGeneratorBug) as refusal:
        render(1, "roughly a day", {"activities": ["not an object"]})
    assert "revision 0" in str(refusal.value)


# ── the properties: §4.4 holds across all figures, not the eight written above ──
# Sampled from literals rather than from `card.py`'s own `_HEDGES` and `_VAGUE`: a strategy built
# out of the constant under test would shrink with it, and a mutant that emptied either tuple would
# leave these tests passing on an empty pool.
HELD = ["8 h", "24 h", "48 h", "45 cutters", "50%", "4", "5"]
HEDGES = ["about", "roughly", "around", "somewhere around", "approximately", "circa", "almost",
          "nearly", "up to", "at least", "no more than", "over", "under"]
VAGUE = ["a working day", "a day or so", "overnight", "a few hours", "several days",
         "fairly critical", "business critical", "mission critical", "very important", "vital",
         "significant", "high risk", "probably", "it seems", "presumably", "broadly", "i think",
         "signed off", "looks good"]
GOOD_CARDS = ["Cutting's MTPD is 8 h.", "Cutting's recovery target is 8 h.", "Scope agreed."]
BAD_CARDS = ["The MTPD is about a working day.", "roughly 12 h", "Cutting is fairly critical"]


def _record_of(*figures):
    """A record holding exactly `figures` and nothing else a card could trace to."""
    return {"revision": 3, "activities": [{"id": "BIA-1", "mtpd": f} for f in figures]}


@given(st.lists(st.sampled_from(HELD), min_size=1, max_size=4))
def test_a_card_that_only_repeats_the_records_own_figures_always_traces(figures):
    """§4.4 from the passing side: quoting the record is always enough to get through the door."""
    assert untraceable(" and ".join(figures), _record_of(*figures)) == []


@given(st.sampled_from(HELD), st.sampled_from(HEDGES))
def test_a_hedge_the_record_does_not_carry_is_always_vagueness(figure, hedge):
    """The first direction: softening a figure the record states plainly is refused, every time."""
    assert untraceable(f"the MTPD is {hedge} {figure}", _record_of(figure)) != []


@given(st.sampled_from(HELD), st.sampled_from(HEDGES))
def test_dropping_a_hedge_the_record_does_carry_is_always_invented_precision(figure, hedge):
    """The second direction, against the same record: the qualifier is the owner's, not ours."""
    hedged = _record_of(f"{hedge} {figure}")
    assert untraceable(f"the MTPD is {figure}", hedged) != []
    assert untraceable(f"the MTPD is {hedge} {figure}", hedged) == []


@given(st.integers(min_value=9, max_value=99))
def test_a_figure_nobody_put_in_the_record_is_always_refused(number):
    assert untraceable(f"the RTO is {number} h", _record_of("8 h")) == [f"{number}h"]


@given(st.sampled_from(VAGUE))
def test_a_figure_said_in_words_is_always_refused(phrase):
    assert phrase in untraceable(f"Cutting is {phrase}", _record_of("8 h"))


@given(st.sampled_from(VAGUE))
def test_a_word_the_record_itself_uses_is_always_traceable(phrase):
    """Vagueness is the card's, never the room's: the owner's own words are a string it holds."""
    spoken = {"activities": [{"quote": f"the owner said it is {phrase}"}]}
    assert untraceable(f"Cutting is {phrase}", spoken) == []


# ── the properties: the check is the door, for every card that reaches it ────
@given(st.sampled_from(GOOD_CARDS + BAD_CARDS))
def test_a_traceable_card_is_always_returned_exactly_as_written(card):
    """§2: the check refuses or it gets out of the way. It never edits a card on its way through."""
    assume(untraceable(card, MTPD_8H) == [])
    assert render(2, card, MTPD_8H) == card


@given(st.sampled_from(GOOD_CARDS + BAD_CARDS), st.integers(min_value=1, max_value=5))
def test_an_untraceable_card_always_raises_and_names_every_string(card, stage):
    """No argument turns the door off, and the bug report carries the whole list, not the first."""
    assume(untraceable(card, MTPD_8H) != [])
    with pytest.raises(CardGeneratorBug) as refusal:
        render(stage, card, MTPD_8H)
    assert refusal.value.strings == untraceable(card, MTPD_8H)
    assert refusal.value.stage == stage


@given(st.integers(min_value=0, max_value=4), st.sampled_from(BAD_CARDS))
def test_a_walk_always_fails_at_the_stage_that_wrote_the_card(index, bad):
    cards = [GOOD_CARDS[0]] * 5
    cards[index] = bad
    with pytest.raises(CardGeneratorBug) as refusal:
        render_walk(cards, MTPD_8H)
    assert refusal.value.stage == index + 1


@given(st.lists(st.sampled_from(GOOD_CARDS), max_size=6))
def test_a_walk_whose_cards_all_trace_returns_every_one_of_them(cards):
    assert render_walk(cards, MTPD_8H) == cards


# ── the parts the eight scenarios reach through, read on their own ───────────
def test_the_alternation_matches_the_longest_phrase_that_fits():
    """`a day or so` is its own row in §4.3 and must not be read as `a day` plus noise."""
    pattern = re.compile(_alternation(("a day", "a day or so")))
    assert pattern.match("a day or so").group() == "a day or so"


def test_the_walks_own_position_is_removed_and_leaves_nothing_behind():
    """§2: the header's `2 of 5` is the method's, not the room's. It comes out; what a generator
    ran into it does not come out with it."""
    assert untraceable("Stage 2 of 512 h", MTPD_8H) == ["12h"]


def test_an_activity_with_no_id_is_named_to_the_developer_by_its_name():
    with pytest.raises(CardGeneratorBug) as refusal:
        render(1, "roughly a day", {"activities": [{"name": "Cutting / deboning"}]})
    assert "activities ['Cutting / deboning']" in str(refusal.value)


def test_the_bug_lists_every_untraceable_string_in_one_readable_sentence():
    with pytest.raises(CardGeneratorBug) as refusal:
        render(3, "The MTPD is roughly 12 h and Cutting is fairly critical", MTPD_8H)
    assert ("says 'fairly critical', 'roughly 12h', which the record does not hold"
            in str(refusal.value))


def test_the_alternation_orders_by_length_and_not_by_the_alphabet():
    """`some time` is longer than `soon` and comes first; the alphabet would say the reverse."""
    assert _alternation(("soon", "some time")) == r"some\ time|soon"


# ── a digit inside a name the room supplies is not a figure (ticket 32) ──────
# The owner's ruling of 2026-09-13: exempt a digit only where it sits **inside an occurrence of a
# name on the card**, scoped to that span. Handing the names to the held text instead — the obvious
# form — lets one `Halle 45` in a room license every bare `45` on every card of that walk, which is
# `test_dropping_the_records_own_qualifier_invents_precision` above gone. Half of these tests are
# therefore about what is still refused.
HALLE = ("Halle 45",)
WERK = ("Werk 1",)


def test_a_digit_inside_a_name_the_room_supplies_is_not_a_figure():
    assert untraceable("Halle 45 is the scope of this BIA, and nothing wider.", {}, HALLE) == []


def test_the_exemption_is_the_span_and_not_the_card_it_sits_on():
    """The one that decides the ticket: the building is a name, the headcount is not."""
    assert untraceable("The MBCO for Halle 45 is 45 cutters", MBCO, HALLE) == ["45"]


def test_two_occurrences_of_a_name_do_not_cover_the_figure_between_them():
    assert untraceable("Halle 45 keeps 45 cutters in Halle 45", MBCO, HALLE) == ["45"]


def test_a_figure_on_a_card_the_name_is_not_on_has_no_span_to_sit_inside():
    assert untraceable("45 cutters stay on shift.", MBCO, HALLE) == ["45"]


def test_a_name_this_room_does_not_hold_licenses_nothing():
    """Otherwise the carve-out matches a shape — word plus digits — and any figure can wear it."""
    assert untraceable("Werk 7 is the scope of this BIA.", {}, WERK) == ["7"]


def test_a_room_that_names_nothing_exempts_nothing():
    assert untraceable("45 cutters", {}, ("",)) == ["45"]


def test_a_hedge_the_card_dropped_is_still_caught_beside_a_name():
    assert untraceable("Werk 1 runs 45 cutters", MBCO, WERK) == ["45"]


def test_a_hedge_the_card_added_is_still_caught_beside_a_name():
    assert untraceable("Werk 1's MTPD is about 8 h", MTPD_8H, WERK) == ["about 8h"]


def test_the_records_own_hedge_still_passes_beside_a_name_with_a_digit_in_it():
    assert untraceable("Werk 1's MBCO is approximately 45 cutters", MBCO, WERK) == []


def test_a_name_that_opens_with_its_own_digit_is_covered_from_its_first_character():
    """The span's left edge, which `Halle 45` never reaches: a room whose name *starts* with the
    figure — a `24h Leitstand` is a control room, not a claim about 24 hours — puts the digit at
    the very first character of the name, and the exemption has to reach it there. The headcount
    beside it is still a figure the record does not hold."""
    assert untraceable("24h Leitstand keeps 45 cutters", MBCO, ("24h Leitstand",)) == ["45"]


def test_with_no_name_supplied_the_check_is_the_one_ticket_09_built():
    assert untraceable("Halle 45 is the scope of this BIA, and nothing wider.", {}) == ["45"]


def test_the_door_carries_the_names_the_room_supplies():
    assert render(1, "Halle 45 is the scope", {}, HALLE) == "Halle 45 is the scope"
    with pytest.raises(CardGeneratorBug):
        render(1, "Halle 45 is the scope", {})


# ── the properties: the exemption is a span, and a span is not a licence ─────
# The eleven scenarios above pin `Halle 45` and `Werk 1`; these say the same things for every plant
# name of that shape. The number band is written into the strategy rather than left to Hypothesis:
# the profile is derandomized (root `conftest.py`), so an unbounded `st.integers()` offers the same
# short list of values on every run and a boundary nobody named is never tried.
NAME_WORDS = ["Werk", "Halle", "Linie", "Standort", "Lager", "Schicht"]
NAME_NUMBERS = st.integers(min_value=1, max_value=99)


def _is_subsequence(part, whole):
    """Whether `part` is `whole` with entries dropped — same strings, same order, nothing new."""
    rest = iter(whole)
    return all(item in rest for item in part)


@given(st.sampled_from(NAME_WORDS), NAME_NUMBERS)
def test_a_room_named_with_any_digit_always_walks_to_a_rendered_card(word, number):
    """The demo blocker, for every plant name and not only `Werk 1`: the manager sees a card."""
    name = f"{word} {number}"
    card = f"{name} is the scope of this BIA, and nothing wider."
    assert render(1, card, {}, (name,)) == card


@given(st.sampled_from(NAME_WORDS), NAME_NUMBERS, NAME_NUMBERS)
def test_a_figure_outside_the_name_is_always_refused_however_the_room_is_named(word, named, count):
    """The ticket's own line: the building is a name, the headcount beside it is still a figure —
    including when the two carry the same digits and the span is the only thing telling them
    apart."""
    name = f"{word} {named}"
    assert untraceable(f"{name} keeps {count} cutters", {}, (name,)) == [str(count)]


@given(st.sampled_from(NAME_WORDS), NAME_NUMBERS, NAME_NUMBERS)
def test_only_the_name_this_room_actually_holds_ever_licenses_a_digit(word, held, other):
    """A `Werk 7` nobody supplied is nobody's name, and `Werk 7` does not stand inside `Werk 77`:
    the carve-out is an occurrence on the card, never a shape a figure can wear."""
    assume(held != other)
    assert untraceable(f"{word} {other} is the scope", {}, (f"{word} {held}",)) == [str(other)]


@given(st.sampled_from(NAME_WORDS), NAME_NUMBERS, st.sampled_from(BAD_CARDS))
def test_supplying_a_name_only_ever_drops_a_refusal_and_never_adds_one(word, number, card):
    """The direction that keeps this an exemption rather than a second rule: names narrow the list
    the check would otherwise make, in the card's own order, and add nothing to it."""
    name = f"{word} {number}"
    sentence = f"{name}: {card}"
    assert _is_subsequence(untraceable(sentence, MTPD_8H, (name,)),
                           untraceable(sentence, MTPD_8H))


@given(st.sampled_from(NAME_WORDS), NAME_NUMBERS, st.sampled_from(HEDGES))
def test_a_hedge_the_card_added_is_always_caught_beside_a_name_with_a_digit_in_it(
        word, number, hedge):
    """Done-when 3, across every hedge: the room's name buys the room's name and nothing else."""
    name = f"{word} {number}"
    assert untraceable(f"{name}'s MTPD is {hedge} 8 h", MTPD_8H, (name,)) == [f"{hedge} 8h"]


@given(NAME_NUMBERS, st.sampled_from(NAME_WORDS))
def test_a_room_named_from_its_digit_onwards_also_always_walks_to_a_rendered_card(number, word):
    """The same demo blocker at the other edge of the span, for every plant name of that shape:
    `24h Leitstand`, `8h Schicht`. Nothing before the digit means the figure begins exactly where
    the name does, and a span that started one character later would leave the card refused."""
    name = f"{number}h {word}"
    card = f"{name} is the scope of this BIA, and nothing wider."
    assert render(1, card, {}, (name,)) == card


@given(st.sampled_from(NAME_WORDS), NAME_NUMBERS)
def test_every_span_a_name_claims_is_exactly_where_that_name_stands(word, number):
    """`_name_spans` reports a stretch of this card, once per occurrence — not the name itself, and
    not a span borrowed from somewhere the name does not stand."""
    name = f"{word} {number}"
    text = _searchable(f"{name} and {name} again")
    assert [text[start:end] for start, end in _name_spans(text, (name,))] == [_searchable(name)] * 2


# ── a name the room supplies is not a vague word either (ticket 47) ──────────
# The owner's ruling of 2026-09-14, answering open question 13: a name the room supplied is never a
# figure and never a vague word, whatever it contains — it is exempt for its whole span. Ticket 32
# scoped the exemption above to a digit deliberately, and this is the second ruling that widens
# *which check* reads the spans. The span rule itself does not move, so half of these tests are
# again about what is still refused: a `Key Accounts` in a room must not license a bare `key`.
KEY = ("Key Accounts",)


def test_a_vague_word_inside_a_name_the_room_supplies_is_not_a_vague_word():
    assert untraceable("Key Accounts is the scope", {}, KEY) == []


def test_a_name_in_the_middle_of_a_sentence_is_exempt_there_too():
    assert untraceable("The scope of this BIA is Key Accounts, and nothing wider.", {}, KEY) == []


def test_the_same_word_outside_the_name_is_still_refused_on_the_card_that_names_it():
    """The one that decides the ticket, and it names `key` once: the bare one, not the name's."""
    assert untraceable("Key Accounts is the scope and the key risk is staff", {}, KEY) == ["key"]


def test_a_card_that_never_names_the_department_licenses_nothing():
    assert untraceable("The key risk is staff turnover.", {}, KEY) == ["key"]


def test_a_phrase_that_only_starts_inside_the_name_is_still_refused():
    """The span covers what the name occupies and no more, so containment is not where it starts."""
    assert untraceable("Group Business critical work runs here.", {}, ("Group Business",)) == [
        "business critical"]


def test_a_name_this_room_does_not_hold_is_still_a_vague_word():
    assert untraceable("Vital Signs is the scope of this BIA.", {}, KEY) == ["vital"]


def test_the_vagueness_rule_is_untouched_beside_an_exempt_name():
    assert untraceable("Key Accounts' MTPD is about a working day", {}, KEY) == ["a working day"]


def test_the_door_carries_the_names_past_the_word_check_as_well():
    """Done-when 4: the manager gets a rendered card, proven through `render` and not the helper."""
    assert render(1, "Key Accounts is the scope", {}, KEY) == "Key Accounts is the scope"
    with pytest.raises(CardGeneratorBug):
        render(1, "Key Accounts is the scope", {})


# The names above pin `Key Accounts`; these say the same two things for every vague word §4.3 has,
# because a name is a name whatever word it happens to carry.
VAGUE_WORDS = ["key", "vital", "significant", "reasonable", "soon", "material impact",
               "mission critical"]


@given(st.sampled_from(VAGUE_WORDS))
def test_a_room_named_with_any_vague_word_always_walks_to_a_rendered_card(word):
    """The demo blocker, for every word a department could be named after."""
    name = f"{word.title()} Accounts"
    card = f"{name} is the scope of this BIA, and nothing wider."
    assert render(1, card, {}, (name,)) == card


@given(st.sampled_from(VAGUE_WORDS))
def test_a_bare_vague_word_is_always_refused_however_the_room_is_named(word):
    """The scoping half: the name buys its own span and never the word elsewhere on the card."""
    name = f"{word.title()} Accounts"
    assert untraceable(f"{name} is the scope and {word} is not", {}, (name,)) == [word]


# ── the properties: the one seam both checks now read the spans through ──────
# Ticket 47's structure, stated on its own. `_outside_the_names` is where the exemption lives for
# the figure check and the word check alike, so the two checks share a rule rather than each
# carrying a copy of it — and a rule in one place is worth saying in one set of properties. The
# pattern below is the test's own, neither `_FIGURE` nor `_VAGUE_RE`: the seam is about spans and
# must hold for anything a check ever looks for, and a strategy built out of the constant under
# test would shrink with it.
SEAM = re.compile(r"[a-z]+|\d+")
SEAM_TEXT = st.text(alphabet="ab 12", min_size=0, max_size=12)
SEAM_SPANS = st.lists(
    st.tuples(st.integers(min_value=0, max_value=12), st.integers(min_value=0, max_value=12))
    .map(lambda pair: (min(pair), max(pair))),
    max_size=3)


@given(SEAM_TEXT)
def test_a_card_no_name_stands_on_has_every_match_checked(text):
    """No name, no exemption: the seam hands both checks exactly what the pattern found, in order.
    This is the path every card of a room that named nothing takes."""
    assert ([found.span() for found in _outside_the_names(SEAM, text, ())]
            == [found.span() for found in SEAM.finditer(text)])


@given(SEAM_TEXT, SEAM_SPANS)
def test_a_match_is_dropped_exactly_when_one_name_wholly_contains_it(text, spans):
    """The span rule ticket 32 settled, unmoved by ticket 47 widening who reads it: containment,
    not overlap, and nothing reordered or invented on the way through."""
    kept = [found.span() for found in _outside_the_names(SEAM, text, spans)]
    assert kept == [found.span() for found in SEAM.finditer(text)
                    if not any(start <= found.start() and found.end() <= end
                               for start, end in spans)]


@given(SEAM_TEXT)
def test_a_name_covering_the_whole_card_leaves_neither_check_anything_to_do(text):
    """The far edge of the exemption: a card that is nothing but the room's own name says nothing
    the record has to hold."""
    assert _outside_the_names(SEAM, text, [(0, len(text))]) == []


@given(st.lists(st.sampled_from(VAGUE_WORDS), max_size=4),
       st.lists(st.sampled_from(VAGUE_WORDS), max_size=4))
def test_the_word_check_names_every_match_the_record_does_not_hold_and_no_other(said, holds):
    """`_untraceable_words` reads matches now rather than the card, and the rule it applies to them
    is unchanged: a phrase the record holds is traceable, in the card's own order."""
    held = " | ".join(holds)
    words = list(re.compile(_alternation(VAGUE_WORDS)).finditer(" | ".join(said)))
    assert _untraceable_words(words, held) == [word for word in said if word not in held]


# ── the properties: a name is exempt whole, whatever it happens to carry ─────
@given(st.sampled_from(VAGUE_WORDS), NAME_NUMBERS)
def test_a_name_carrying_a_vague_word_and_a_digit_is_exempt_for_all_of_it(word, number):
    """The owner's ruling of 2026-09-14 in one sentence, for a name that trips both checks at once:
    a `Key Accounts Halle 45` is a department, and the manager sees the card."""
    name = f"{word.title()} Halle {number}"
    card = f"{name} is the scope of this BIA, and nothing wider."
    assert render(1, card, {}, (name,)) == card


@given(st.sampled_from(VAGUE_WORDS), NAME_NUMBERS)
def test_the_same_word_and_the_same_digit_bare_are_both_still_refused(word, number):
    """The scoping half of that ruling, for both checks at once and in the order `untraceable`
    reports them: the name buys its own span, never the word or the count standing outside it."""
    name = f"{word.title()} Halle {number}"
    card = f"{name} keeps {number} cutters and {word} is not the scope"
    assert untraceable(card, {}, (name,)) == [word, str(number)]


@given(st.sampled_from(VAGUE_WORDS), st.sampled_from(BAD_CARDS))
def test_a_name_made_of_a_vague_word_only_ever_drops_a_refusal_and_never_adds_one(word, card):
    """The same direction ticket 32 pinned for digits, now that the word check reads the spans too:
    supplying a name narrows the list the check would otherwise make, and adds nothing to it."""
    name = f"{word.title()} Accounts"
    sentence = f"{name}: {card}"
    assert _is_subsequence(untraceable(sentence, MTPD_8H, (name,)),
                           untraceable(sentence, MTPD_8H))


# ── the properties: the two lines every check above is measured in ───────────
# Both checks now read one seam, and that seam reads two strings neither of them builds: the card
# `_searchable` makes, which every span offset counts characters of, and the line `_held_text`
# makes, which is the whole of what "the record holds" means. Ticket 47 widened who consults the
# spans, so what the spans are measured in carries twice the weight it did; these say what those
# two lines are for anything a room or a record can put in them, not only for the cards above.
# The alphabets are named rather than left open for the reason the number band above is: the
# profile is derandomized, so an unbounded `st.text()` offers the same short list every run.
NORMALIZABLE = st.text(alphabet="ab 12hm%*_`’“— ", max_size=20)
LEAVES = st.text(alphabet="abc 45h", max_size=8)


@given(NORMALIZABLE)
def test_normalizing_the_card_twice_is_normalizing_it_once(text):
    """A span is an offset into `_searchable(card)`, and `_name_spans` finds it by searching that
    string for `_searchable(name)` — two separate passes of the same folding. They only ever agree
    about where a name stands if the folding has nothing left to do the second time, so this is
    the property the whole exemption is measured in. The alphabet is what `norm` folds: typography,
    markdown, a non-breaking space, and a digit beside a unit for the gap `_searchable` closes."""
    assert _searchable(_searchable(text)) == _searchable(text)


@given(st.sampled_from(VAGUE_WORDS), NAME_NUMBERS, st.integers(min_value=1, max_value=3))
def test_a_name_claims_one_span_per_occurrence_and_every_span_holds_that_name(word, number, times):
    """The span rule read from the other end: not what is exempt, but that a name claims exactly
    where it stands and nothing between two of its occurrences — for a name carrying a vague word
    and a digit at once, which is both checks' business since the owner's ruling of 2026-09-14."""
    name = f"{word.title()} Halle {number}"
    card = _searchable(" and ".join([f"{name} is the scope"] * times))
    spans = _name_spans(card, (name,))
    assert len(spans) == times
    assert {card[start:end] for start, end in spans} == {_searchable(name)}


@given(st.dictionaries(LEAVES, st.one_of(LEAVES, st.lists(LEAVES, max_size=3)), max_size=4))
def test_every_string_a_record_holds_reaches_the_line_the_checks_search(record):
    """Both checks ask one question of one line — is this string in what the record holds — so a
    leaf the flattening drops is a figure a card is refused for saying although the record says it.
    Keys are leaves too: a grid's horizon labels are figures the record holds, and they are its
    keys. Said for a record of any shape, because a room's method file is not one fixed shape."""
    line = _held_text(record)
    for key, value in record.items():
        assert key in line
        assert all(leaf in line for leaf in (value if isinstance(value, list) else [value]))


# ── One rule inside the one check: no switch, no second door ─────────────────
# From `tests/ui/walk/test_a_digit_inside_a_name_is_not_a_figure.py` step 19 (ticket 32) and
# `tests/ui/walk/test_a_room_supplied_name_is_exempt_for_its_whole_span.py` steps 22 and 24 (ticket
# 47), last held at 4ffe6783, which ticket 165 slice 4 retired with those walk files. They read the
# real `card.py`, found by walking up to `gate.sh`: `mutmut` runs this suite from a copy under
# `mutants/` whose source it has rewritten (`nemo.test_layers.repo_root`).
CARD_PY = next(folder for folder in Path(__file__).resolve().parents
               if (folder / "gate.sh").is_file()) / "src" / "nemo" / "card.py"


def _code_of(path: Path) -> str:
    """A module's code with its prose taken out: no comments, no docstrings, no literals.

    A word in a sentence is not a switch: `nemo.card`'s docstring says what is exempt inside a
    name, and a search over the file's characters would read that as a `skip` flag."""
    return "".join(token.string for token in
                   tokenize.generate_tokens(io.StringIO(CARD_PY.read_text()).readline)
                   if token.type not in (tokenize.COMMENT, tokenize.STRING))


def test_the_name_exemption_cannot_be_switched_off():
    """No flag, no environment variable, no "trust the names" path."""
    for switch in ("environ", "getenv", "argv", "skip", "disable", "enabled", "strict="):
        assert switch not in _code_of(CARD_PY), f"step 19: the check has a switch: {switch!r}"


def test_render_takes_the_card_the_record_and_the_room_s_names_and_nothing_else():
    assert re.search(r"^def render\(stage: int, card: str, record: Mapping\[str, Any\], "
                     r"names: Sequence\[str\] = \(\)\) -> str:$", CARD_PY.read_text(), re.M), (
        "step 19: `render` takes an argument beyond the card, the record and the room's names")


def test_the_names_are_not_a_second_door():
    """The exemption is inside the one check `render` makes, and that check takes nothing more."""
    source = CARD_PY.read_text()
    assert source.count("def untraceable(") == 1, "step 22: the names are a second door"
    assert re.search(r"^def untraceable\(card: str, record: Mapping\[str, Any\], "
                     r"names: Sequence\[str\] = \(\)\) -> list\[str\]:$", source, re.M), (
        "step 24: the check takes something beyond the card, the record and the room's names")


def test_the_span_rule_is_applied_in_one_place_for_both_checks():
    source = CARD_PY.read_text()
    for helper in ("_outside_the_names", "_inside_a_name", "_held_with_the_same_hedge"):
        assert source.count(f"def {helper}(") == 1, (
            f"step 24: `{helper}` is defined {source.count(f'def {helper}(')} times")
