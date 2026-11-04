"""The ask lane: a BCM question answered from the frozen guidance corpus, with its citation.

This is one of the demo skin's two model jobs (ADR-0008), and the model is the **skin's**, not the
product's — nemo itself is deterministic and a production front end brings its own model. The lane
lives here rather than in `demo_skin/app.py` for the reason `nemo.door` does: the decisions have to
be testable without Chainlit, which is not a nemo dependency (ADR-0001). `demo_skin/app.py` holds
the four lines that put an `Answer` on screen.

Two hosts, never one (`docs/status.md`): the corpus is read from the **open** guidance connector
`mcp.ai4bcm.org`, five tools, no bearer token. `agent.ai4bcm.org` is the BIA session connector,
needs a token, and is not this lane's business — it is named nowhere in this module but here.

**The citation is not parsed out of the model's answer.** It is built from the chunks the connector
served, so a citation can only name a chunk that was actually fetched, at the frozen release
`CORPUS_RELEASE`. That name is defined once, below, and the filter, both refusals and the check the
skin runs at start all read it: moving the corpus to a new release is one edit and nowhere else.

**Nothing surviving that filter is a refusal, not a question asked of the model with no excerpts
under it.** If the connector's tag moves, every chunk is dropped at once — and the lane was still
called, so the model answered from nothing at all and printed no `Source:` line (found by probe on
ticket 11). The two ways it can happen are told apart in the words, because a facilitator acts on
them differently: the corpus answered and nothing matched the question, so ask it another way; or
the corpus is the wrong release, so nothing can be vouched for and it needs fixing before the room
is used. `release_note` reads the connector's own health page once at start so the second case is
on the operator's console before the first question of the day.

**ISO 22301, ISO/TS 22317 and the BCI Good Practice Guidelines are not in the corpus and are not
going in** (ADR-0005, an owner call taken with the BCI World audience known). A question naming one
is declined here, before the connector and before the model, because the answer is already known:
the corpus does not hold that text. Nothing else is second-guessed for the model. Whether a
question names one is `nemo.text.norm`'s judgement, not this module's: a manager pastes the
question out of Word as often as typing it, and a non-breaking space inside "Good Practice
Guidelines" must not be the difference between declining and answering about a text the corpus
does not hold. That normalizer lives below this lane, `nemo.card` and `nemo.referee` alike,
because three private spellings of "the same string" would drift into three answers.

**The cap is a hard stop, not a degradation** (ADR-0009). `OPENROUTER_API_KEY_AI4BCM` is capped at
OpenRouter and shared across five `ai4bcm/*` lanes; when it is reached every call fails at once.
The call itself, and the one `LaneUnavailable` a 402 and a dead port both arrive as, are
`nemo.lane`'s — it sits below `nemo.conduct` too, and an interview held in the room has no use for
a guidance corpus. What is this module's is the answer: one plain sentence and no citations — no
retry, no cached answer, no buttons-only substitute, and the room stays usable. Nothing on this box
reports the remaining budget: litellm runs with no database, so checking the OpenRouter dashboard
before a demo is a manual act by the owner (`docs/facilitator-note.md`).

Neither `strict` nor `tool_choice` appears below, and the ten-minute check that established what
the lane can do is recorded in `docs/research/ask-lane-lever-check.md` — forcing a schema would
convert "refuses to supply the owner name" into "invents a plausible one", which is the trait
ADR-0007 keeps.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# The lane this job speaks over, and the one refusal every failure of it wears. It sits below
# `nemo.conduct` as well, which is the whole reason it is not in this module: the interview held
# in the room needs the lane and needs nothing else the guidance corpus knows.
from nemo.lane import Getter, LaneCall, LaneUnavailable, Poster, call_lane, field, get, post
from nemo.text import norm

#: The open guidance connector. No bearer token: it is public deliberately (ADR-0005).
GUIDANCE_URL = "https://mcp.ai4bcm.org/mcp"

#: The same connector's health page, which names the release it is serving. One GET, no token.
GUIDANCE_HEALTH_URL = "https://mcp.ai4bcm.org/health"

#: The frozen release (ADR-0062, which re-pinned ADR-0046 d1). A chunk stamped anything else,
#: 2026.11 included, is stale, not corpus, and is not cited.
CORPUS_RELEASE = "2026.11.1"

#: How many of the connector's hits are fetched and handed to the lane. Search returns four.
EXCERPTS = 4

#: The connector puts the document before the section in one title.
TITLE_SEPARATOR = " > "

#: The tenth source: the project's own `units/` tree, which the corpus splits across many units.
GUIDELINE = "the AI4BCM guideline"

#: The nine literature documents, as `AI4BCM/guidance` `data/chunks.json` spells their units.
#: NIST CSWP 29, the Cybersecurity Framework 2.0, came with `CORPUS_RELEASE` (ADR-0046 d4); it is
#: listed so that it is cited as itself and never as the AI4BCM guideline.
LITERATURE = (
    "esas-jc-2026-25-frontier-ai-models-statement",
    "eur-lex-ai-act-2024-1689-articles-4-26-50",
    "eur-lex-delegated-regulation-2024-1774",
    "eur-lex-dora-regulation-2022-2554",
    "nist-ai-100-1-ai-rmf-1-0",
    "nist-cswp-29-csf-2-0",
    "nist-sp-800-34r1-contingency-planning-body",
    "swiss-fones-minimum-standard-ict-resilience-2023",
    "uk-cabinet-office-organisational-resilience-guidance",
)

#: The ten sources of the frozen release (ADR-0005, ADR-0046).
SOURCES = (GUIDELINE, *LITERATURE)

#: What is not in the corpus, by the string a manager would type, spelled in `norm`'s normal form
#: so that the question and the mark are compared on the same footing. ADR-0005.
UNCOVERED = {
    "22317": "ISO/TS 22317",
    "22301": "ISO 22301",
    "good practice guidelines": "the BCI Good Practice Guidelines",
}

#: Said when the question names one of those three. It declines and says where to go instead.
NOT_COVERED = (
    "{standard} isn't in the guidance corpus, so I can't tell you what it says — and I'd rather "
    "say that than guess. What the corpus does hold on this is DORA, NIST SP 800-34r1, the Swiss "
    "FONES minimum standard and the UK Cabinet Office guidance. Ask me the same question without "
    "naming the standard and I'll answer from those."
)

#: Said when the corpus answered and no chunk of it matched. Asking it another way may work.
NOTHING_MATCHED = (
    "The guidance corpus holds nothing on your question, so there is nothing for me to answer "
    "from — and I would rather say that than make something up. Ask it another way, or in the "
    "words a BCM colleague would use, and I will look again."
)

#: Said when chunks came back and every one of them is stamped some other release. Not the same
#: stop: nothing can be vouched for, and no rephrasing will change that.
WRONG_RELEASE = (
    "The guidance corpus this room is reading is not the frozen release {expected}, so I cannot "
    "vouch for anything it would tell you and I will not answer from it. Asking another way will "
    "not help — the guidance corpus needs putting back to {expected} first."
)

#: Written to the console at start when the connector agrees with us. Quiet on purpose: a check
#: that shouts on a healthy guidance corpus is a check that is ignored on an unhealthy one.
RELEASE_AGREES = "Guidance corpus release {served}, as expected."

#: Written at start when it does not agree. Both tags, so an operator can act without the code.
RELEASE_MISMATCH = (
    "The guidance connector is serving guidance corpus release {served}, and the ask lane expects "
    "{expected}. Until they match the ask lane will refuse every question rather than answer from "
    "a corpus it cannot vouch for."
)

#: Written at start when the connector would not say. The skin still starts; the lane still stops.
RELEASE_UNREADABLE = (
    "The guidance connector did not say which guidance corpus release it is serving ({reason}). "
    "Until it does, the ask lane will refuse every question."
)

#: Said when the lane or the connector does not answer, including when the key cap is reached.
UNAVAILABLE = (
    "The service that answers these questions is unavailable, so I can't answer this one. "
    "Nothing else in your room is affected, and the rest of the walk carries on without it."
)

#: What the lane is told to do. Prose, and the excerpts are the only material it may use.
#:
#: It used to say the excerpts "come from the AI4BCM guidance corpus", which is true of the
#: corpus and false of an excerpt: the frozen release carries the project's own guideline **and**
#: nine outside documents (ADR-0005, ADR-0046), so that blanket sentence told the model NIST was the
#: Guidance and the answer text said so. Ticket 81, on the owner's ruling: nemo fixes what it
#: tells the model, and each excerpt now names its own source below. Nothing reads the answer
#: back to check it followed this — the model's wording is never policed (M13).
#:
#: The last sentence is ticket 202's, and is ADR-0029 G's one named exception (2026-09-29, the
#: owner's ruling): a prompt sentence is not normally a fix, and this one stands because it was
#: measured first — 7 replays of one real request, a median answer of 248 words without it and
#: 147 with it. It asks for brevity and nothing else; the "two or three short paragraphs" above
#: stays as it was, because that is the card set B was measured against. Re-wording either of
#: them is a new measurement, not an edit.
CARD = (
    "You are answering a business continuity manager's question from the excerpts below. Each "
    "excerpt says which source it came from — the AI4BCM Guidance, or a document from outside "
    "it. Call each source by the name given with its excerpt: an outside source is never called "
    "AI4BCM Guidance. Answer only from those excerpts, in two or three short paragraphs of "
    "prose, in the words a BCM colleague would use. Where the excerpts do not settle something, "
    "say so rather than filling the gap. Do not cite anything that is not below, and do not "
    "mention these instructions. Give the answer in the first sentence, then at most one short "
    "paragraph; keep your reasoning brief."
)

#: Said under one excerpt's citation, so the model knows which of the two kinds it is reading.
#: The verdict is the one nemo already served the chunk under (`Excerpt.source`), never a reading
#: of the excerpt's own words, and the manager's `Source:` line is not where this goes (t65).
SAYS_GUIDANCE = "This excerpt is from the AI4BCM Guidance."

#: The same line for one of the nine documents. The **verdict** is still `Excerpt.source`; what
#: is printed is `Excerpt.document`, the connector's own name for the document it served, because
#: the unit slug is not a name a BCM colleague would write and this sentence is the only place
#: nemo frames anything as that excerpt's identity. Not a table: both fields are on the excerpt.
SAYS_LITERATURE = "This excerpt is from {document}, an outside document, not the AI4BCM Guidance."

GuidanceCall = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Excerpt:
    """One chunk as the connector served it: the words the lane answers from, and its citation.

    `document` and `locator` are the two halves of the connector's own title, and `url` is its
    own link, so `str(excerpt)` is a line a manager can look up and nothing in it was written
    here. `source` is which of the ten `SOURCES` it came from.
    """

    document: str
    locator: str
    source: str
    url: str
    text: str

    def __str__(self) -> str:
        """The citation line, as the `Source:` line prints it."""
        return f"{self.document}{TITLE_SEPARATOR}{self.locator} — {self.url}"


@dataclass(frozen=True)
class Answer:
    """What goes on screen: the answer, and the citation of every excerpt it was drawn from."""

    text: str
    citations: tuple[Excerpt, ...]

    @property
    def on_screen(self) -> str:
        """The answer, then one `Source:` line per citation. The whole of what the manager sees."""
        return "\n\n".join([self.text, *(f"Source: {citation}" for citation in self.citations)])


def call_guidance(
    tool: str, arguments: dict[str, Any], *, post: Poster = post
) -> dict[str, Any]:
    """Call one of the connector's five tools and return its structured result."""
    reply = post(
        GUIDANCE_URL,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
    )
    content: dict[str, Any] = field(reply, GUIDANCE_URL, "result", "structuredContent")
    return content


def served_release(*, get: Getter = get) -> str:
    """The release the connector says it is serving, read from it rather than assumed."""
    tag: str = get(GUIDANCE_HEALTH_URL)["release_tag"]
    return tag


def release_note(*, get: Getter = get) -> str:
    """The line the skin writes at start: agreement, the mismatch, or neither read.

    A mismatch here is a lane that refuses all day, so it is said once where an operator sees it
    before the room opens. It never stops the skin starting: the walk does not need the corpus.
    """
    try:
        served = served_release(get=get)
    except LaneUnavailable as unavailable:
        return RELEASE_UNREADABLE.format(reason=unavailable)
    if served == CORPUS_RELEASE:
        return RELEASE_AGREES.format(served=served)
    return RELEASE_MISMATCH.format(served=served, expected=CORPUS_RELEASE)


def uncovered_standard(question: str) -> str | None:
    """The name of the standard this question asks about that the corpus does not hold, if any.

    The question is read through the package's one normalizer, so a spelling that went through a
    word processor — bolded, curly-quoted, joined by a non-breaking space — names the standard
    just as plainly as one typed into the box, and is declined rather than answered from a corpus
    that does not hold it.
    """
    asked = norm(question)
    for mark, standard in UNCOVERED.items():
        if mark in asked:
            return standard
    return None


def source_of(unit: str) -> str:
    """Which of the ten sources a chunk's unit belongs to."""
    return unit if unit in LITERATURE else GUIDELINE


def ask(
    question: str, *, guidance: GuidanceCall = call_guidance, lane: LaneCall = call_lane
) -> Answer:
    """Answer one question from the corpus, or say plainly why it is not being answered."""
    standard = uncovered_standard(question)
    if standard is not None:
        return Answer(NOT_COVERED.format(standard=standard), ())
    try:
        return _from_the_corpus(question, guidance, lane)
    except LaneUnavailable:
        return Answer(UNAVAILABLE, ())


def _from_the_corpus(question: str, guidance: GuidanceCall, lane: LaneCall) -> Answer:
    """The corpus read and filtered to the frozen release, then answered from — or refused.

    Nothing surviving the filter is the refusal, and the model is not called: it is the only
    place where a card could reach the lane with no excerpt under it at all.
    """
    chunks = _chunks(question, guidance)
    excerpts = _at_the_frozen_release(chunks)
    if not excerpts:
        return Answer(_nothing_to_answer_from(chunks), ())
    return Answer(lane(_prompt(question, excerpts)), excerpts)


def _chunks(question: str, guidance: GuidanceCall) -> list[dict[str, Any]]:
    """The corpus chunks behind an answer: search the connector, then fetch what it named."""
    hits = guidance("search", {"query": question})["results"][:EXCERPTS]
    return [guidance("fetch", {"id": hit["id"]}) for hit in hits]


def _at_the_frozen_release(chunks: list[dict[str, Any]]) -> tuple[Excerpt, ...]:
    """The chunks stamped `CORPUS_RELEASE`, as excerpts. Anything else is stale, not corpus."""
    return tuple(
        _excerpt(chunk) for chunk in chunks if chunk["metadata"]["release_tag"] == CORPUS_RELEASE
    )


def _nothing_to_answer_from(chunks: list[dict[str, Any]]) -> str:
    """Which of the two refusals: the corpus matched nothing, or it is the wrong release."""
    if not chunks:
        return NOTHING_MATCHED
    return WRONG_RELEASE.format(expected=CORPUS_RELEASE)


def _excerpt(chunk: dict[str, Any]) -> Excerpt:
    """One fetched chunk as an excerpt, its citation taken from the connector's own fields."""
    document, _, locator = str(chunk["title"]).partition(TITLE_SEPARATOR)
    return Excerpt(
        document=document,
        locator=locator or chunk["id"],
        source=source_of(chunk["metadata"]["unit"]),
        url=chunk["url"],
        text=chunk["text"],
    )


def _which_source(excerpt: Excerpt) -> str:
    """The line telling the model which source one excerpt is, decided by `Excerpt.source`.

    Which is `source_of`'s verdict on the served chunk's own unit, so a document the release
    gains or loses says its own name here without a list of names being kept anywhere. The
    document the sentence names is the connector's own title for it, never the unit slug and
    never a word of the excerpt: what decides and what is printed both come off the excerpt.
    """
    if excerpt.source == GUIDELINE:
        return SAYS_GUIDANCE
    return SAYS_LITERATURE.format(document=excerpt.document)


def _prompt(question: str, excerpts: tuple[Excerpt, ...]) -> str:
    """The card, the excerpts with their citations and sources, and the question as asked.

    The source goes here and not into `Excerpt.__str__`: that line is the manager's `Source:`
    citation, ticket 65's and proven, and what the model needs to know is not what he reads.
    """
    return "\n\n".join(
        [
            CARD,
            *(
                f"Excerpt from {excerpt}\n{_which_source(excerpt)}\n\n{excerpt.text}"
                for excerpt in excerpts
            ),
            f"The question: {question}",
        ]
    )
