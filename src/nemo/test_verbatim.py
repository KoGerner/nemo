"""Properties of the one verbatim block. The screen inherits them.

The writer and the reader used to live in two files and nothing tied them together; the tie is the
round trip, and a round trip is a property rather than a list of the five transcripts somebody
thought of. A company's `07_Interviews/` folder holds whatever the company writes in it, so the
question these tests answer is not "does this transcript survive" but "which transcript does not",
and the answer has to be none.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from nemo.verbatim import block, blocks, fence, unfenced

#: The characters a transcript out of Word or an editor actually carries, weighted so that the
#: ones that break markdown — a rule, a heading, a fence of the company's own — keep turning up.
SAID = st.text(alphabet=st.sampled_from("ab \n\t-#`>*_\\\r'\"|~[]()Ä€"), max_size=60)

#: A markdown-safe name to put above a block, so a failure is the block's and never the name's.
NAME = st.text(alphabet="abcdefgh ", min_size=1, max_size=12)


@given(SAID)
def test_a_block_always_reads_back_as_the_characters_that_went_into_it(said):
    """The round trip, which is the whole contract between the writer and the screen.

    Byte-exact, not nearly: a yes to a preview is a yes to bytes (`nemo.interview.Interview`), so
    a transcript that comes back one character different has not been previewed at all.
    """
    assert blocks(block(said)) == [said]


@given(NAME, SAID)
def test_a_block_still_reads_back_when_something_is_written_above_it(name, said):
    """A card is never only the preview: stage 2 puts the interview's name over every one."""
    assert blocks(f"**{name}**\n\n{block(said)}") == [said]


@given(NAME, SAID, SAID)
def test_every_block_on_one_card_reads_back_in_the_order_the_card_carries_it(name, first, second):
    """A stage 2 card previews every interview the room holds, not one."""
    card = f"**{name}**\n\n{block(first)}\n\n{block(second)}"

    assert blocks(card) == [first, second]


@given(SAID)
def test_nothing_a_transcript_says_is_ever_left_loose_on_the_card(said):
    """The defect, stated from the other end: outside the fences there is nothing of the file.

    `---` alone on a line is a horizontal rule and `#` a heading, and the manager was being shown
    those instead of what he was endorsing. Finding the preview inside a block is only half of it;
    the other half is that no copy of it is sitting out where the renderer will read it.
    """
    assert unfenced(block(said)) == ""


@given(SAID)
def test_a_fence_is_longer_than_any_run_of_backticks_the_transcript_holds(said):
    """So the company's own fenced block can never close ours early and free the rest again."""
    edge = fence(said)

    assert edge not in said
    assert f"\n{edge}\n" not in f"\n{said}\n"


@given(SAID)
def test_a_fence_is_backticks_and_never_fewer_than_markdowns_three(said):
    assert set(fence(said)) == {"`"}
    assert len(fence(said)) >= 3


def test_a_transcript_with_no_backticks_in_it_is_fenced_with_markdowns_three():
    """The ordinary case, pinned exactly: nothing wider is spent on a file that needs nothing."""
    assert fence("---\ndepartment: Slaughter\n---\n\n# Cutting\n") == "```"
    assert block("x") == "```\nx\n```"


def test_a_transcript_that_fences_something_itself_is_fenced_one_backtick_wider():
    """The company's `systemctl` block is three, so ours is four; its four would make ours five."""
    assert fence("```\nsystemctl restart ka-01\n```") == "````"
    assert fence("````\nnested\n````") == "`````"
    assert fence("a ` b `` c") == "```"


def test_the_widest_run_decides_the_fence_and_not_the_last_one():
    """`max`, not the one that happened to come last: a wide run anywhere closes a narrow fence."""
    assert fence("`````\nwide\n`````\n\n```\nnarrow\n```") == "``````"


def test_a_transcript_of_several_lines_reads_back_whole():
    """Pinned as an example as well as a property, because a reader that stops at the first
    newline would still satisfy every single-line case hypothesis happened to shrink to."""
    said = "---\ndepartment: Slaughter\n---\n\n# Cutting\n\n> \"We dress 400 a day.\"\n"

    assert blocks(block(said)) == [said]
    assert unfenced(f"**Slaughter**\n\n{block(said)}") == "**Slaughter**\n\n"


def test_an_empty_transcript_is_still_a_block_and_still_reads_back():
    """A file a manager has not written in yet is an empty preview, not a missing one."""
    assert block("") == "```\n\n```"
    assert blocks(block("")) == [""]


def test_text_carrying_no_fence_at_all_reads_back_as_no_blocks_and_as_itself():
    """The reader says "nothing here is verbatim" rather than guessing at one."""
    card = "**Slaughter**\n\nnothing fenced here\n"

    assert blocks(card) == []
    assert unfenced(card) == card
