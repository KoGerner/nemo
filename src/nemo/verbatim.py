"""The one verbatim block, below the skin that writes one and the stand-in that reads one back.

A preview a manager is asked to say yes to has to be what he will get, so the characters a
transcript holds have to reach the screen as the transcript holds them: its `---` three hyphens
and its `#` a hash, not a rule and a heading. In markdown the one construct that promises that is
a fence, and a fence is a two-ended thing — something writes one and something else reads it. That
is two modules needing the same grammar, which is why it is spelled here rather than in either.

Ticket 23 had it in both. `demo_skin/app.py` built the fence and `skin_harness.py` matched it back
with a regex of its own, and nothing proved the two agreed: the app is outside coverage, CRAP and
mutmut by `gate.sh`'s own design (the framework is not installed in this venv, so a number about
those lines would be a number about a stand-in), and the harness at the root is outside ruff and
mypy as well. The one function deciding whether a manager sees the truth sat in the least-watched
pair of files in the tree, written twice. Here it is written once, under all of them, and the
round trip — `blocks(block(x)) == [x]` for every x — is a property rather than a hope.

Nothing in `nemo` imports this and that is correct: no front end is privileged, so the rule the
second skin has to obey is kept where the second skin can reach it, not inside the first one.
"""

from __future__ import annotations

import re

#: A fenced block as a renderer finds one: a run of backticks alone on a line, whatever lies
#: between, and the same run closing it. What is inside is drawn as the characters it is made of.
_FENCE = re.compile(r"^(`{3,})\n(.*?)\n\1$", re.M | re.S)


def fence(said: str) -> str:
    """A run of backticks nothing inside `said` can close: longer than any run `said` holds.

    Three is markdown's least, and three is enough until the company files a fence of its own —
    `07_Interviews/` is its folder and it writes what it likes in it. A fence its own contents
    close early is the ticket 23 defect back one file later: everything past the early close is
    read as markdown again.
    """
    return "`" * max([3, *(len(run) + 1 for run in re.findall("`+", said))])


def block(said: str) -> str:
    """`said` wrapped so a renderer draws it as the characters it is made of, and nothing else.

    The whole of the writing half: the fence, the text untouched between two newlines of its own,
    and the same fence again. Nothing is prefixed to a line — the blockquote this replaced put
    `> ` in front of every one of them, the file's own `>` included.
    """
    edge = fence(said)
    return f"{edge}\n{said}\n{edge}"


def blocks(content: str) -> list[str]:
    """What a renderer would draw verbatim off this text, in the order the text carries it.

    The reading half, and the reason both halves live together: this is the only statement of what
    `block` has to produce, so a test that reads a card with it is testing the screen rather than
    the writer's own opinion of the screen.
    """
    return [held for _, held in _FENCE.findall(content)]


def unfenced(content: str) -> str:
    """What is left once the blocks are out: everything a renderer reads as markdown.

    The other half of the same question. A `---` alone on a line is a rule out here and three
    hyphens in there, so a preview's own punctuation being safe means finding it in `blocks`
    **and** finding it loose nowhere.
    """
    return _FENCE.sub("", content)
