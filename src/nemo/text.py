"""The one normalizer, below every layer that compares two strings.

`nemo.card`, `nemo.referee` and `nemo.ask` all compare a string a human wrote against a string
something else holds — the card check against the record, the referee against a room file, the ask
lane against the three standards ADR-0005 leaves out of the corpus. Three normalizers would drift
into three answers, so there is one; it lives below all of them rather than inside any. The card
used to import the referee to borrow it, and that edge pointed at a module the card otherwise has
nothing to do with, in the one direction that invites a cycle: the referee's findings travel *to*
the card, so the day a finding needs formatting the import would come back the other way. The ask
lane's copy was a bare `.lower()`, which is the same drift arriving as duplication rather than as
an edge: it declined a typed "Good Practice Guidelines" and answered a pasted one.

Typography only, never wording. It may fold a curly quote into a straight one, drop the markdown
that wraps a word and collapse a run of spaces. It may not reword, reorder, round or translate
anything: every comparison in the package is only as honest as that line, and `docs/voice.md` §4.4
rests on it entirely — a normalizer that quietly rewrote "approximately 45" to "45" would make the
card check pass the exact drift it exists to catch.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping

# The quotes and dashes a word processor substitutes silently. Folded so that two strings a human
# would call identical are identical here; nothing in this table changes a letter. The spaces it
# substitutes are not here: NFKC runs first in `norm` and already folds every one of them to a
# space, so a row for them could never fire.
_PUNCT_EQUIVALENTS = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
})


def norm(value: object) -> str:
    """The project's one normalizer for comparing two strings: typography only, never wording.

    The one place typography is allowed to be forgiven. Callers compare `norm(a)` to `norm(b)`,
    or ask whether `norm(a)` is inside `norm(b)`; nobody re-implements the folding.
    """
    text = unicodedata.normalize("NFKC", str(value)).translate(_PUNCT_EQUIVALENTS).lower()
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text)).strip()


def found_in(words: object, files: Mapping[str, str]) -> list[str]:
    """Which of `files` hold `words`, in the order they were handed over: the one comparison.

    `nemo.bia` asks it where a quote was found, to write that file into the record (ticket 131),
    and `nemo.referee` asks it whether the quote is there at all. One function, so the file a
    record names and the check the referee makes can never disagree about a match.
    """
    return finder(files)(words)


def finder(files: Mapping[str, str]) -> Callable[[object], list[str]]:
    """`found_in` over `files` with each file folded once, for a caller seeking many quotes.

    Folding a whole interview costs far more than seeking a quote in it, and `nemo.bia` seeks every
    quote of a record in every confirmed interview: folded again per quote, that doubled the skin
    suite (ticket 131's perf fix).
    """
    folded = [(path, norm(text)) for path, text in files.items()]

    def holding(words: object) -> list[str]:
        wanted = norm(words)
        return [path for path, text in folded if wanted in text]

    return holding
