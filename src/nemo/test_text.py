"""Properties of the one normalizer. Every comparison in the package inherits them.

`norm` is the only function both `nemo.card` and `nemo.referee` call, so its contract is stated as
properties rather than as examples: the examples would pin the five strings somebody thought of,
and what the card check needs is the guarantee across all of them. The line these tests defend is
`docs/voice.md` §4.4 — a normalizer that rewords is a card check that passes the drift it exists to
catch, so "never changes a letter or a digit" is the property that matters most here.
"""

from hypothesis import given
from hypothesis import strategies as st

from nemo.text import found_in, norm

# Lowercase alnum: already normal, so `norm` of it is itself and an exact result can be asserted.
WORD = st.text(alphabet="abcdefghij0123456789", min_size=1, max_size=8)
WHITESPACE = st.text(alphabet=" \t\n\r", min_size=1, max_size=4)
# The characters §4.3's tables wrap a figure in when a card is written as markdown.
WRAPPER = st.sampled_from("*_`")
# An alphabet NFKC leaves alone, so "what came out is what went in" is a fair thing to assert.
STABLE = st.text(alphabet="abcXYZ 019'\"-*_`\t\n.,/%", max_size=40)
# Straight character -> the variant a word processor substitutes for it behind the writer's back.
SUBSTITUTIONS = {"'": "’", '"': "“", "-": "–", " ": " "}


@given(st.text())
def test_normalizing_a_normalized_string_changes_nothing(value):
    """Idempotent, so it is safe to normalize at either end of a comparison, or at both."""
    assert norm(norm(value)) == norm(value)


@given(st.text())
def test_the_result_never_carries_a_double_space_or_an_edge_space(value):
    """The shape every caller relies on when it asks whether one normal form is inside another."""
    result = norm(value)
    assert "  " not in result
    assert result == result.strip()


@given(STABLE)
def test_normalizing_never_changes_a_letter_or_a_digit(value):
    """§4.4's floor: typography may be folded, wording may not.

    Stated as the characters that carry meaning — every letter and digit survives, in order, with
    only case folded. A normalizer that quietly turned "approximately 45" into "45" would make the
    card check green on exactly the invented precision it exists to refuse.
    """
    assert [c for c in norm(value) if c.isalnum()] == [c for c in value.lower() if c.isalnum()]


@given(WORD, WHITESPACE, WORD)
def test_a_run_of_whitespace_between_two_words_becomes_one_space(first, gap, second):
    assert norm(first + gap + second) == f"{first} {second}"


@given(WHITESPACE, WORD, WHITESPACE)
def test_whitespace_around_a_word_is_dropped(before, word, after):
    assert norm(before + word + after) == word


@given(WRAPPER, WORD)
def test_the_markdown_that_wraps_a_word_is_not_part_of_the_word(wrapper, word):
    """So a card's bolded **8 h** is the record's `8 h`, and emphasis is not invented precision."""
    assert norm(wrapper * 2 + word + wrapper * 2) == word


@given(WORD)
def test_case_is_folded(word):
    assert norm(word.upper()) == word


@given(STABLE)
def test_the_variants_a_word_processor_substitutes_are_folded(value):
    """A curly quote, an en dash and a non-breaking space compare equal to what they replaced.

    This is the whole reason the translation table exists: two strings a human would call identical
    must not be a card-generator bug because one of them went through Word.
    """
    substituted = "".join(SUBSTITUTIONS.get(c, c) for c in value)
    assert norm(substituted) == norm(value)


@given(st.sampled_from([("¹", "1"), ("Ａ", "a"), ("ﬁ", "fi"), ("Ⅸ", "ix")]))
def test_compatibility_forms_are_folded_to_the_characters_they_stand_for(pair):
    """NFKC, so a superscript or a fullwidth digit in a pasted-in file is still the figure it is."""
    raw, expected = pair
    assert norm(raw) == expected


# ── where some words are found (ticket 131) ───────────────────────────────────


def test_the_files_holding_some_words_come_back_in_the_order_they_were_handed_over():
    files = {"b.md": "we lose product fast", "a.md": "nothing here", "c.md": "we lose product fast"}
    assert found_in("lose product", files) == ["b.md", "c.md"]


def test_words_no_file_holds_are_found_nowhere():
    assert found_in("nobody said this", {"a.md": "somebody said that"}) == []


@given(WORD, WORD, st.sampled_from(sorted(SUBSTITUTIONS)))
def test_words_are_found_across_the_typography_a_word_processor_substitutes(first, second, plain):
    """The one comparison: what `norm` forgives, finding forgives, and nothing else."""
    held = f"{first}{SUBSTITUTIONS[plain]}{second}"
    assert found_in(f"{first}{plain}{second}", {"room.md": f"x {held} y"}) == ["room.md"]
