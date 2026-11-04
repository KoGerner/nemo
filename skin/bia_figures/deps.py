"""The dependency floor.

Every register entry a confirmed interview names is a dependency of the activity, whatever a model
proposed. A model may add ids the interviews do not name; it may never remove one they do. The
register's own consumer list is deliberately not consulted: it is known to be incomplete.

An interview names an entry in one of two ways (ticket 184). By its **id**, anywhere in the text, as
the old rooms do: an asset only, as it always was, since an id like `bank` is an ordinary word too.
Or by its **name**, exactly as the register spells it, on the interviewee's own "Depends on:" line,
which is where he lists what his activity needs: any entry that may be depended on — a system, a
technology, a role, a supplier, a document. A name said anywhere else ("Bank details are taken from
the file") names nothing.

Only what the register holds as dependable is offered, so a word an interview happens to share with
a metadata key — `synthetic`, of a room that says of itself that it is synthetic data — is not a
dependency, and no model can make it one by proposing it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from bia_figures.register import Register, assets, is_dependable, is_metadata

FILES = "files"
PROPOSED = "proposed"

_TOKEN = re.compile(r"[\w-]+")
NAME = "name"

#: A line an interview lists its dependencies on: "Henning Barsch: Depends on: Microsoft 365, …",
#: or the bare "Depends on: …". The speaker, when there is one, comes before the first colon.
DEPENDS_ON = "Depends on:"
_DEPENDS_ON = re.compile(rf"^(?:(?P<who>[^:\n]*?):[ \t]*)?{DEPENDS_ON}(?P<said>.*)$", re.MULTILINE)
#: Who the interview's front matter says was interviewed, when it says so.
_INTERVIEWEE = re.compile(r"^interviewee:[ \t]*(?P<who>.*?)[ \t]*$", re.MULTILINE)


def _names(register: Register) -> dict[str, str]:
    """Each register name, mapped to its key: the words a person says (ticket 184).

    Every mapping that has a name, not only the dependable ones: a longer name the register holds
    shields a shorter one inside it even when it is metadata. `floor` keeps the dependable ones.
    """
    return {entry[NAME]: key for key, entry in register.items()
            if isinstance(entry, Mapping) and entry.get(NAME)}


def _named(names: dict[str, str], text: str) -> set[str]:
    """The ids whose names the text says whole and exactly as the register spells them.

    Longest name first, so a name said as part of a longer one ("Atlassian Jira" in "Atlassian
    Jira Service Management") is not said as well; a name running on into a word ("Microsoft
    3650") is not said at all, the same boundary `_TOKEN` gives an id.
    """
    if not names:
        return set()
    spoken = "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
    return {names[said] for said in re.findall(rf"(?<![\w-])(?:{spoken})(?![\w-])", text)}


def _depends_on(text: str) -> str:
    """What the interviewee says on his own "Depends on:" lines, and nothing else of the text.

    A line someone else speaks is not his: when the front matter names the interviewee, a line
    with another speaker ("Franziska Dohm: Depends on: …?") lists nothing.
    """
    interviewee = _INTERVIEWEE.search(text)
    return "\n".join(line["said"] for line in _DEPENDS_ON.finditer(text)
                     if not (interviewee and line["who"] and line["who"] != interviewee["who"]))


def elsewhere(text: str) -> str:
    """An interview read for an activity other than its own: its "Depends on:" lines list nothing.

    The line lists what the interviewee's own activity needs, so a draft that rests on another
    department's interview does not inherit that list; an id the text says still names an asset.
    """
    return text.replace(DEPENDS_ON, "Depends on -")


def floor(register: Register, interviews: Iterable[str]) -> set[str]:
    """The register entries the confirmed interviews name: the dependencies no model may remove."""
    texts = list(interviews)
    tokens = {token for text in texts for token in _TOKEN.findall(text)}
    names = _names(register)
    said = {key for text in texts for key in _named(names, _depends_on(text))}
    return ({asset for asset in assets(register) if asset in tokens}
            | {key for key in said if is_dependable(register, key)})


def dependencies(
    register: Register,
    interviews: Iterable[str],
    proposed: Iterable[str],
) -> dict[str, str]:
    """Map each dependency id of the activity to where it came from: `FILES` or `PROPOSED`.

    The floor is a set, and a mapping is an order: sorted, because the order a set reads in is
    the hash seed's and a caller reads these ids out as a sentence a manager signs.
    """
    found = dict.fromkeys(sorted(floor(register, interviews)), FILES)
    for asset in proposed:
        if asset not in found and not is_metadata(register, asset):
            found[asset] = PROPOSED
    return found
