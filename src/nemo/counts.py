"""Five of the machine's counts beside his marks (ticket 123, ADR-0029 F).

He judges a round's answers first; these are shown only after, as reading aids. **Each is advisory
and never a gate** (M13, ADR-0023): nothing reads a count to fail an answer, a walk or a build. Each
has a known limit, stated in the header of the file the skin's round instrument writes
(`skin/PROTOTYPE_chatbar.py counts`), not here.

The sixth count, `invented_figure`, is deliberately not in this module. It is the skin's own
`_flag`, called as it is, so the figure checker the chat uses and the one that counts are the same
code (the check session's amendment: a second finder drifts, as 106's second verbatim check did).

**Nothing here reaches the disk, the clock or the network.** The corpus's links and the anti-slop
list are handed in by the caller; `nemo.test_counts` holds that shut with the package's seal.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence

from nemo.ask import UNCOVERED
from nemo.text import norm

#: The one chat tool that reads the guidance corpus; every other tool reads the room.
GUIDANCE_TOOL = "ask_guidance"

#: Names the field uses that are not among the corpus's ten sources: the three `nemo.ask` already
#: declines on, and a few more. Keyed like `UNCOVERED`, in `norm`'s normal form.
OUTSIDE = {
    **UNCOVERED,
    "22313": "ISO 22313",
    "31000": "ISO 31000",
    "27001": "ISO/IEC 27001",
    "25999": "BS 25999",
    "nfpa 1600": "NFPA 1600",
}

_WHERE = {(True, True): "both", (True, False): "guidance",
          (False, True): "files", (False, False): "neither"}
_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
_SOURCE_LINE = re.compile(r"^\d+\. \[[^\]]+\]\(https?://", re.M)


def went_where(tools: Sequence[str]) -> str:
    """`files`, `guidance`, `both` or `neither`, from the tools the answer called."""
    guidance = GUIDANCE_TOOL in tools
    room = any(tool != GUIDANCE_TOOL for tool in tools)
    return _WHERE[(guidance, room)]


def ai_words(answer: str, words: Iterable[str]) -> list[str]:
    """The listed words and phrases the answer uses, whole, as the list spells them."""
    said = norm(answer)
    return sorted(w for w in words if re.search(rf"(?<!\w){re.escape(norm(w))}(?!\w)", said))


def sources(answer: str, tools: Sequence[str],
            corpus_urls: Collection[str]) -> dict[str, object] | None:
    """For an answer that read the guidance: whether a numbered source line is under it, and
    whether each link in it is a section the corpus holds. None when it never read the guidance."""
    if GUIDANCE_TOOL not in tools:
        return None
    links = [{"url": url, "resolves": url in corpus_urls} for url in _LINK.findall(answer)]
    return {"source_line": bool(_SOURCE_LINE.search(answer)), "links": links}


def outside_references(answer: str) -> list[str]:
    """The names on `OUTSIDE` the answer mentions: named, so not linkable or checkable here.

    Whole words, the same match `ai_words` makes above (ticket 210): a bare substring counted the
    `31000` inside `EUR 131000` as ISO 31000."""
    said = norm(answer)
    return [name for mark, name in OUTSIDE.items()
            if re.search(rf"(?<!\w){re.escape(norm(mark))}(?!\w)", said)]
