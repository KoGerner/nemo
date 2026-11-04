"""The ask lane, driven off responses recorded verbatim from the real lane and the real connector.

Every fixture under `tests/fixtures/ask/` is a `curl` body saved as it arrived — `guidance-*`
from `https://mcp.ai4bcm.org/mcp` with no bearer token, `lane-*` from litellm at `127.0.0.1:4000`.
The two searches and their fetches are of 2026-11-01, release 2026.11.1 (ticket 673, ADR-0062;
first recorded 2026-10-03 at 2026.11, ticket 306); the lane bodies are of 2026-09-12, and why
the answer stays is said above `ANSWER`. None of them was typed from memory, and a green run here
proves only that the code matches them; the live run is recorded in
`docs/research/ask-lane-live-run.md`.

No test in this file opens a socket: both seams (`guidance`, `lane`) and the one below them
(`post`) are parameters with real defaults, so the fixtures stand in for the network.

The seam below is `nemo.lane`'s since ticket 17 — `post`, `get`, `call_lane` and the one
`LaneUnavailable` they all fail as. What is driven from here is the *difference* between the two
hosts: the connector is asked for JSON or an event stream and the health page for JSON alone, and
a copy-paste between them only shows up where both are recorded off one harness. The lane's own
properties — the header never sent, the payload that arrives as it was given, the one exception
every failure becomes — are in `src/nemo/test_lane.py`, which imports neither caller, because a
module that sits below two of them should be provable below them too.
"""

import json
import re
import urllib.error
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

import nemo.ask
from nemo.ask import (
    CARD,
    CORPUS_RELEASE,
    EXCERPTS,
    GUIDANCE_HEALTH_URL,
    GUIDANCE_URL,
    GUIDELINE,
    LITERATURE,
    NOT_COVERED,
    NOTHING_MATCHED,
    RELEASE_AGREES,
    RELEASE_MISMATCH,
    RELEASE_UNREADABLE,
    SAYS_GUIDANCE,
    SAYS_LITERATURE,
    SOURCES,
    UNAVAILABLE,
    UNCOVERED,
    WRONG_RELEASE,
    Answer,
    Excerpt,
    ask,
    call_guidance,
    release_note,
    served_release,
    source_of,
    uncovered_standard,
)
from nemo.lane import (
    LANE_URL,
    LANE_URL_ENV,
    MODEL,
    TIMEOUT_SECONDS,
    LaneUnavailable,
    call_lane,
    get,
    lane_url,
    post,
)
from nemo.record import fingerprint
from nemo.room_store import read_record, write_record
from nemo.text import norm


def repo_root(start: Path = Path(__file__)) -> Path:
    """The tree the skin ships from, found rather than counted off `__file__`.

    `mutmut` runs this suite from a copy under `mutants/` that holds `pyproject.toml`, `src/` and
    `tests/` and nothing else — no `docs/`, no skin. Counting parents off `__file__` therefore
    lands on a directory that holds neither, so the tests below that read the running skin's own
    files raise `FileNotFoundError` there — and they raise it during mutmut's stats collection,
    which then abandons the whole run and leaves every mutant in the package "not checked".
    `mutmut results` lists no survivor when it has judged nothing at all, so the gate reads green
    on an empty verdict. Walking up to the first ancestor that holds `gate.sh` finds the same real
    tree from either copy; `pyproject.toml` beside `src/` would not, because the copy holds both.
    The marker was `demo_skin/` until ticket 129, which retires that folder.
    """
    return next(folder for folder in start.resolve().parents if (folder / "gate.sh").is_file())


REPO = repo_root()


def test_the_real_tree_is_found_from_mutmuts_copy(tmp_path: Path) -> None:
    """Ticket 129: the marker outlives `demo_skin/`, and `mutants/` (which holds `pyproject.toml`
    and `src/`) is never taken for the real tree."""
    (tmp_path / "gate.sh").touch()
    copy = tmp_path / "mutants" / "src" / "nemo"
    copy.mkdir(parents=True)
    (tmp_path / "mutants" / "pyproject.toml").touch()
    assert repo_root(copy / "test_this.py") == tmp_path


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ask"
MTPD_QUESTION = "What does the corpus say about setting an MTPD?"
RTO_QUESTION = "What does the corpus say about recovery time objectives?"
WORKFLOW_ID = "workflow-design-the-bia-workflow-five-stages"
#: The two recorded chunks that are literature rather than the project's own units.
NIST_ID = "nist-ai-100-1-ai-rmf-1-0-5-4-manage"
DELEGATED_ID = (
    "eur-lex-delegated-regulation-2024-1774-article-24-components-of-the-ict-business-"
    "continuity-policy"
)


def fixture(name: str) -> dict:
    """One recorded body, parsed."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def structured(name: str) -> dict:
    """What `call_guidance` hands back: one recorded JSON-RPC reply's `structuredContent`."""
    content: dict = fixture(name)["result"]["structuredContent"]
    return content


#: The answer the real lane gave to `MTPD_QUESTION` on 2026-09-12, recorded verbatim, on
#: `ai4bcm/glm-5.3-flash` over the 2026.09.1 top four. It stays through ticket 306's live run of
#: 2026-10-03 (`docs/research/ask-lane-live-run.md`) because both of that run's MTPD answers, on
#: `ai4bcm/glm-5.3-flash-fastest`, report 0 reasoning tokens, and "the model's thinking never
#: reaches me" needs a body in which the lane thought. The tests here read it only as text.
ANSWER: str = fixture("lane-answer-mtpd")["choices"][0]["message"]["content"]


class Guidance:
    """The connector, answering from the recorded bodies and remembering what it was asked."""

    def __init__(self, search: dict | None = None) -> None:
        self.search = search or structured("guidance-search-mtpd")
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, tool: str, arguments: dict) -> dict:
        self.calls.append((tool, arguments))
        if tool == "search":
            return self.search
        return structured(f"guidance-fetch-{arguments['id']}")


class Lane:
    """The model lane, answering with one recorded body's content, or refusing like a cap."""

    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.unavailable:
            raise LaneUnavailable("the lane answered 402")
        return ANSWER


# ------------------------------------------------ answered from the corpus, with its source


def test_an_answer_is_drawn_from_the_corpus() -> None:
    guidance, lane = Guidance(), Lane()
    answer = ask(MTPD_QUESTION, guidance=guidance, lane=lane)
    assert answer.text == ANSWER
    assert [tool for tool, _ in guidance.calls] == ["search", "fetch", "fetch", "fetch", "fetch"]
    assert guidance.calls[0][1] == {"query": MTPD_QUESTION}


def test_the_lane_is_given_the_question_and_the_excerpts_to_answer_from() -> None:
    guidance, lane = Guidance(), Lane()
    ask(MTPD_QUESTION, guidance=guidance, lane=lane)
    prompt = lane.prompts[0]
    excerpt = structured(f"guidance-fetch-{WORKFLOW_ID}")
    assert prompt.startswith(CARD)
    assert "Answer only from those excerpts" in CARD
    assert f"The question: {MTPD_QUESTION}" in prompt
    assert excerpt["text"] in prompt
    assert str(_workflow_excerpt()) in prompt


def test_the_prompt_puts_a_blank_line_between_the_card_the_excerpts_and_the_question() -> None:
    """One blank line joins the blocks, so nothing is run together and nothing is inserted.

    Inside one excerpt's block the source line sits directly under the citation, one newline and
    not two (ticket 81): it is the label on that citation, not a fourth kind of block.
    """
    guidance, lane = Guidance(), Lane()
    answer = ask(MTPD_QUESTION, guidance=guidance, lane=lane)
    prompt = lane.prompts[0]
    assert prompt.startswith(f"{CARD}\n\nExcerpt from ")
    assert prompt.endswith(f"\n\nThe question: {MTPD_QUESTION}")
    for citation in answer.citations:
        under = said_of(citation)
        assert f"\n\nExcerpt from {citation}\n{under}\n\n{citation.text}\n\n" in prompt


# ------------------------------- which excerpt is the Guidance, and which is outside it (t81)


def sourced_as(units: list[str]) -> Guidance:
    """The recorded connector, serving the nth chunk it fetches under the nth of `units`.

    The fixtures hold eleven chunks and only five of the nine literature documents, so a source the
    release carries but the recording does not is driven by putting its unit on a recorded chunk:
    the one field `source_of` reads varies, and everything the model is handed stays a recording.
    """

    class Under(Guidance):
        def __init__(self) -> None:
            super().__init__()
            self.fetched = 0

        def __call__(self, tool: str, arguments: dict) -> dict:
            served = super().__call__(tool, arguments)
            if tool == "search":
                return served
            unit = units[self.fetched]
            self.fetched += 1
            return {**served, "metadata": {**served["metadata"], "unit": unit}}

    return Under()


def told_sources(prompt: str) -> list[str]:
    """The line under each excerpt's citation, in the order the model receives them."""
    return [block.splitlines()[1] for block in prompt.split("\n\nExcerpt from ")[1:]]


def said_of(citation: Excerpt) -> str:
    """What the model should be told one excerpt is: the verdict from `source`, the name from
    `document`, which is the connector's own title for the document it served."""
    if citation.source == GUIDELINE:
        return SAYS_GUIDANCE
    return SAYS_LITERATURE.format(document=citation.document)


def test_the_card_stops_calling_every_excerpt_the_guidance_and_keeps_the_rest() -> None:
    """Ticket 81. The blanket claim is what let an answer resting on NIST call it the Guidance.

    The owner's ruling was to fix what nemo tells the model, so the card says where the excerpts
    come from — each one names its own source — and states the rule the labels already follow.
    Everything else it said is still said: the excerpts are the only material, gaps are admitted,
    nothing else is cited, and the instructions are not mentioned.
    """
    assert "come from the AI4BCM guidance corpus" not in CARD
    assert "Call each source by the name given with its excerpt" in CARD
    assert "an outside source is never called AI4BCM Guidance" in CARD
    assert "AI4BCM guidance" not in CARD, "one capitalisation, or the model reads two things"
    assert "Answer only from those excerpts" in CARD
    assert "say so rather than filling the gap" in CARD
    assert "Do not cite anything that is not below" in CARD
    assert "do not mention these instructions" in CARD


def test_the_card_ends_by_asking_for_the_answer_first_and_one_short_paragraph() -> None:
    """Ticket 202's set B, in the words it was measured in and at the end of the card.

    ADR-0029 G says fixes are what nemo serves and draws, never prompt sentences. This one
    sentence is G's named exception, dated 2026-09-29 on the owner's ruling, and it is allowed
    because it was measured first: over 7 replays of one real request it took the median answer
    from 248 words to 147 (`~/work/nemo-builds/t202-report.md`, FINAL 202m). The wording is
    pinned verbatim rather than by a phrase, because a re-worded sentence is a different
    sentence and would need its own measurement before it could stand here.

    The sentence is the whole of what he picked: set C (two excerpts instead of four) was dropped
    on the same ruling because it lost the excerpt naming who sets the MTPD, so `EXCERPTS` is
    still four and this test is the only one the ticket adds.
    """
    assert CARD.endswith(
        " Give the answer in the first sentence, then at most one short paragraph; "
        "keep your reasoning brief."
    )
    assert "two or three short paragraphs of prose" in CARD, "B was measured with this in place"
    assert EXCERPTS == 4, "set C was dropped: the four excerpts are what B was measured on"


def test_the_two_sentences_name_the_guidance_and_the_outside_document_that_served_it() -> None:
    """The words themselves, because the card and these lines are the whole of this ticket."""
    assert SAYS_GUIDANCE == "This excerpt is from the AI4BCM Guidance."
    assert SAYS_LITERATURE.format(document="NIST AI 100-1 — AI RMF 1.0") == (
        "This excerpt is from NIST AI 100-1 — AI RMF 1.0, an outside document, "
        "not the AI4BCM Guidance."
    )


def test_a_prompt_of_guidance_excerpts_says_so_under_every_one_of_them() -> None:
    """The recorded MTPD search: four chunks, all from the project's own `units/` tree."""
    guidance, lane = Guidance(), Lane()

    answer = ask(MTPD_QUESTION, guidance=guidance, lane=lane)

    prompt = lane.prompts[0]
    assert [citation.source for citation in answer.citations] == [GUIDELINE] * EXCERPTS
    assert told_sources(prompt) == [SAYS_GUIDANCE] * EXCERPTS
    for citation in answer.citations:
        assert f"Excerpt from {citation}\n{SAYS_GUIDANCE}\n\n{citation.text}" in prompt


def test_a_prompt_of_literature_excerpts_names_each_document_and_calls_none_the_guidance() -> None:
    """Two recorded chunks, NIST and the delegated regulation: neither is the Guidance."""
    guidance = Guidance(search={"results": [{"id": NIST_ID}, {"id": DELEGATED_ID}]})
    lane = Lane()

    answer = ask(RTO_QUESTION, guidance=guidance, lane=lane)

    prompt = lane.prompts[0]
    assert [citation.source for citation in answer.citations] == [
        "nist-ai-100-1-ai-rmf-1-0",
        "eur-lex-delegated-regulation-2024-1774",
    ]
    assert told_sources(prompt) == [said_of(citation) for citation in answer.citations]
    assert SAYS_GUIDANCE not in prompt
    for citation in answer.citations:
        assert citation.document in prompt, "the document names itself, not its unit slug"


def test_a_mixed_prompt_tells_the_guidance_and_the_literature_apart_excerpt_by_excerpt() -> None:
    """NIST SP 800-34, ours, DORA, ours: two recorded hits from each search, interleaved.

    Since 2026.11's ranking (ticket 306) the recorded RTO search is all literature and the MTPD
    search all guideline, so neither straddles the split alone; every body fetched is recorded.
    """
    rto = structured("guidance-search-rto")["results"]
    mtpd = structured("guidance-search-mtpd")["results"]
    guidance, lane = Guidance(search={"results": [rto[0], mtpd[0], rto[1], mtpd[1]]}), Lane()

    answer = ask(RTO_QUESTION, guidance=guidance, lane=lane)

    prompt = lane.prompts[0]
    assert told_sources(prompt) == [said_of(citation) for citation in answer.citations]
    assert told_sources(prompt).count(SAYS_GUIDANCE) == 2
    assert len(set(told_sources(prompt))) == 3


@pytest.mark.parametrize("source", SOURCES)
def test_every_one_of_the_ten_sources_is_told_to_the_model_as_source_of_gives_it(source) -> None:
    """Driven off `SOURCES` itself, not a list typed here: ten sources, ten cards.

    The unit is the source's own for the nine documents and one of the project's own units for
    the guideline, which is exactly the mapping `source_of` makes — so what the model is told is
    read from the served chunk's `metadata.unit` and from nothing else.
    """
    unit = "workflow-design" if source == GUIDELINE else source
    lane = Lane()

    answer = ask(MTPD_QUESTION, guidance=sourced_as([unit] * EXCERPTS), lane=lane)

    prompt = lane.prompts[0]
    assert source_of(unit) == source
    assert [citation.source for citation in answer.citations] == [source] * EXCERPTS
    assert told_sources(prompt) == [said_of(citation) for citation in answer.citations]
    assert (SAYS_GUIDANCE in prompt) == (source == GUIDELINE)
    if source != GUIDELINE:
        for citation, line in zip(answer.citations, told_sources(prompt), strict=True):
            assert citation.document in line, "the document names itself, not its unit slug"
            assert source not in line


def test_the_manager_s_screen_is_the_answer_then_one_source_line_per_citation() -> None:
    """The whole screen, written out, so ticket 65's rendering is pinned and not re-derived.

    Two citations, one of each kind, and nothing about which is which reaches the screen: the
    line is the document, the locator and the url the connector served, and that is all it is.
    """
    nist = Excerpt(
        document="NIST AI 100-1 — AI RMF 1.0",
        locator="5.4 Manage",
        source="nist-ai-100-1-ai-rmf-1-0",
        url="https://example.invalid/nist#54-manage",
        text="the excerpt's words",
    )
    ours = Excerpt(
        document="Glossary",
        locator="glossary",
        source=GUIDELINE,
        url="https://example.invalid/glossary#glossary",
        text="the excerpt's words",
    )

    screen = Answer("Two short paragraphs.", (nist, ours)).on_screen

    assert screen == (
        "Two short paragraphs.\n"
        "\n"
        "Source: NIST AI 100-1 — AI RMF 1.0 > 5.4 Manage — https://example.invalid/nist#54-manage\n"
        "\n"
        "Source: Glossary > glossary — https://example.invalid/glossary#glossary"
    )


def test_what_the_model_is_told_about_a_source_never_reaches_the_manager_s_screen() -> None:
    """Ticket 65's citation line is proven and unchanged: the source went into the prompt."""
    guidance, lane = Guidance(search=structured("guidance-search-rto")), Lane()

    answer = ask(RTO_QUESTION, guidance=guidance, lane=lane)

    screen = answer.on_screen
    assert SAYS_GUIDANCE not in screen
    for citation in answer.citations:
        assert said_of(citation) not in screen
        assert f"Source: {citation.document} > {citation.locator} — {citation.url}" in screen


def test_the_citation_is_printed_on_screen_beside_the_answer() -> None:
    answer = ask(MTPD_QUESTION, guidance=Guidance(), lane=Lane())
    screen = answer.on_screen
    assert answer.text in screen
    for citation in answer.citations:
        assert f"Source: {citation}" in screen
    assert screen.index(answer.text) < screen.index(f"Source: {answer.citations[0]}")


def test_each_citation_names_one_of_the_ten_sources_with_a_locator() -> None:
    answer = ask(MTPD_QUESTION, guidance=Guidance(), lane=Lane())
    assert len(SOURCES) == 10
    assert len(answer.citations) == 4
    for citation in answer.citations:
        assert citation.source in SOURCES
        assert citation.document and citation.locator and citation.url
        assert str(citation) == f"{citation.document} > {citation.locator} — {citation.url}"


def test_the_citation_splits_the_connector_s_title_into_document_and_locator() -> None:
    citation = _workflow_excerpt()
    assert citation.document == "Workflow Design"
    assert citation.locator == "The BIA workflow, five stages"
    assert citation.url == (
        "https://github.com/AI4BCM/guidance/blob/2026.11.1/units/workflow-design.md"
        "#the-bia-workflow-five-stages"
    )
    assert citation.source == GUIDELINE


def test_a_chunk_whose_title_carries_no_section_is_located_by_its_id() -> None:
    guidance = Guidance(search={"results": [{"id": "glossary"}]})
    citation = ask("What is an MTPD?", guidance=guidance, lane=Lane()).citations[0]
    assert citation.document == "Glossary"
    assert citation.locator == "glossary"
    assert citation.source == GUIDELINE


def test_the_ten_sources_are_the_guideline_and_the_nine_literature_documents() -> None:
    assert len(LITERATURE) == 9
    assert SOURCES == (GUIDELINE, *LITERATURE)
    assert source_of("nist-ai-100-1-ai-rmf-1-0") == "nist-ai-100-1-ai-rmf-1-0"
    assert source_of("stages-analysis") == GUIDELINE


def test_a_literature_chunk_is_cited_to_its_own_document_not_the_guideline() -> None:
    """The four fetched chunks of the recorded RTO search are all literature, from three documents.

    Each stands for its own document and none collapses into the guideline: a chunk's source is
    read from its own `metadata.unit`. Until 2026.11's ranking (ticket 306) two of the four were
    the project's own units; the mixed case is now driven from both recorded searches above.
    """
    guidance = Guidance(search=structured("guidance-search-rto"))
    answer = ask(RTO_QUESTION, guidance=guidance, lane=Lane())

    assert [citation.source for citation in answer.citations] == [
        "nist-sp-800-34r1-contingency-planning-body",
        "eur-lex-dora-regulation-2022-2554",
        "eur-lex-delegated-regulation-2024-1774",
        "nist-sp-800-34r1-contingency-planning-body",
    ]
    nist = answer.citations[0]
    assert nist.document == (
        "NIST SP 800-34 Rev. 1 — Contingency Planning Guide for Federal Information Systems"
        " (body, Chapters 1 to 5)"
    )
    assert nist.locator == "3.2.1 Determine Business Processes and Recovery Criticality"
    assert nist.source in LITERATURE


def test_no_more_excerpts_are_fetched_than_the_lane_is_given() -> None:
    hits = structured("guidance-search-mtpd")["results"]
    guidance = Guidance(search={"results": hits + hits})
    ask(MTPD_QUESTION, guidance=guidance, lane=Lane())
    assert len(guidance.calls) == 1 + EXCERPTS == 5


def test_a_chunk_from_another_release_is_not_cited() -> None:
    stale = {**structured(f"guidance-fetch-{WORKFLOW_ID}")}
    stale["metadata"] = {**stale["metadata"], "release_tag": "2026.09"}

    class Stale(Guidance):
        def __call__(self, tool: str, arguments: dict) -> dict:
            fetched = super().__call__(tool, arguments)
            return stale if arguments.get("id") == WORKFLOW_ID else fetched

    answer = ask(MTPD_QUESTION, guidance=Stale(), lane=Lane())
    assert CORPUS_RELEASE == "2026.11.1"
    assert [citation.locator for citation in answer.citations] == [
        "prompts-bia",
        "Say that AI helped",
        "prompts-management-report",
    ]


# ------------------------------------- nothing survives the filter, so the lane refuses
#
# The filter fails open unless the lane refuses: if the connector's tag moves, every chunk is
# dropped and the model is handed a card with no excerpts under it at all. Probed on ticket 11,
# and the answer that came back carried zero `Source:` lines. The tag below is the one the local
# guidance repo already stamps, so this is one release bump away rather than hypothetical.

STALE_RELEASE = "2026.09"

#: The release the connector served before 2026.11. Answered from during the switch (ADR-0046 d2),
#: and stale again, like any other tag, since ticket 294.
PREVIOUS_RELEASE = "2026.09.1"


def restamped(release: str) -> Guidance:
    """The recorded connector, serving the same chunks stamped some other release."""

    class Restamped(Guidance):
        def __call__(self, tool: str, arguments: dict) -> dict:
            served = super().__call__(tool, arguments)
            if tool == "search":
                return served
            return {**served, "metadata": {**served["metadata"], "release_tag": release}}

    return Restamped()


def restamped_each(tags: list[str]) -> Guidance:
    """The recorded connector, stamping the nth chunk it serves with the nth of `tags`.

    `restamped` above moves the whole corpus at once, which is the one case a release bump makes.
    This one mixes them, so "nothing survived" and "something survived" are the same code path
    driven to both ends rather than two tests that share a name.
    """

    class Each(Guidance):
        def __init__(self) -> None:
            super().__init__()
            self.fetched = 0

        def __call__(self, tool: str, arguments: dict) -> dict:
            served = super().__call__(tool, arguments)
            if tool == "search":
                return served
            tag = tags[self.fetched]
            self.fetched += 1
            return {**served, "metadata": {**served["metadata"], "release_tag": tag}}

    return Each()


def test_a_corpus_at_the_wrong_release_is_refused_rather_than_answered_from_nothing() -> None:
    guidance, lane = restamped(STALE_RELEASE), Lane()

    answer = ask(MTPD_QUESTION, guidance=guidance, lane=lane)

    assert answer == Answer(WRONG_RELEASE.format(expected=CORPUS_RELEASE), ())
    assert lane.prompts == [], "the model was asked to answer from no excerpts at all"
    assert "Source:" not in answer.on_screen
    assert "MTPD" not in answer.text, "the refusal answered the question it refused"


def test_the_wrong_release_refusal_says_it_cannot_vouch_and_names_the_frozen_release() -> None:
    text = WRONG_RELEASE.format(expected=CORPUS_RELEASE)
    assert "guidance corpus" in text
    assert "vouch" in text
    assert CORPUS_RELEASE in text


def test_a_question_the_corpus_matched_nothing_for_is_refused_too() -> None:
    guidance, lane = Guidance(search={"results": []}), Lane()

    answer = ask("What does the corpus say about the melting point of tungsten?",
                 guidance=guidance, lane=lane)

    assert answer == Answer(NOTHING_MATCHED, ())
    assert lane.prompts == [], "the model was asked to answer from no excerpts at all"
    assert [tool for tool, _ in guidance.calls] == ["search"]
    assert "tungsten" not in answer.text


def test_the_two_refusals_read_differently_because_they_are_acted_on_differently() -> None:
    """One says ask another way; the other says fix the guidance corpus. Neither reads as both."""
    matched_nothing, wrong_release = NOTHING_MATCHED, WRONG_RELEASE.format(expected=CORPUS_RELEASE)

    assert matched_nothing != wrong_release
    assert CORPUS_RELEASE not in matched_nothing, "a missed question is not a release problem"
    assert "vouch" not in matched_nothing
    assert "holds nothing on your question" not in wrong_release
    for text in (matched_nothing, wrong_release):
        assert "guidance corpus" in text
        for avoided in ("knowledge base", "KB", "session", "tenant", "error"):
            assert avoided not in text


# The other half of the property — one stale chunk among four costs that chunk and not the
# answer — is `test_a_chunk_from_another_release_is_not_cited` above. These refusals are for
# *nothing* surviving the filter; a corpus that still answers still answers.

# ------------------------------------------------ the frozen release, named in one place

#: The package's own source. `demo_skin/`, the Chainlit app that drew it, was read here too until
#: 166 archived it.
SOURCE_FILES = sorted(
    path for path in (REPO / "src").rglob("*.py") if not path.name.startswith("test_")
)


def _names_release(line: str, release: str) -> bool:
    """Whether `line` spells `release` out as a whole tag: "2026.11" is inside "2026.11.1", so a
    substring check would let the withdrawn release pass as named (675). A tag is digits and
    dots, so only a digit beside it, or a dot and a digit, makes it a different tag: "v2026.11.1",
    "2026.11.1.json" and "Release 2026.11.1." all still name it."""
    return re.search(rf"(?<![\d.]){re.escape(release)}(?!\.?\d)", line) is not None


def test_the_frozen_release_is_named_in_one_place_and_that_place_is_the_constant() -> None:
    """Two live copies of the tag is what makes moving it a hunt rather than an edit."""
    named = [
        (path.name, line.strip())
        for path in SOURCE_FILES
        for line in path.read_text().splitlines()
        if _names_release(line, CORPUS_RELEASE)
    ]

    assert named == [("ask.py", f'CORPUS_RELEASE = "{CORPUS_RELEASE}"')]


def test_changing_that_one_name_is_the_whole_of_moving_to_a_new_release(monkeypatch) -> None:
    """Change the name, and the corpus that was refused a moment ago is answered from."""
    guidance, lane = restamped(STALE_RELEASE), Lane()
    assert ask(MTPD_QUESTION, guidance=guidance, lane=lane).citations == ()

    monkeypatch.setattr(nemo.ask, "CORPUS_RELEASE", STALE_RELEASE)
    answer = ask(MTPD_QUESTION, guidance=guidance, lane=lane)

    assert answer.text == ANSWER
    assert len(answer.citations) == EXCERPTS


# --------------------------------------------- the served release, read once at start


def health(release: str) -> object:
    """A `get` that answers the connector's health page, and remembers what it was asked."""

    class Health:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def __call__(self, url: str) -> dict:
            self.urls.append(url)
            return {"ok": True, "chunks": 383, "release_tag": release}

    return Health()


def test_the_served_release_is_read_from_the_connector_rather_than_assumed() -> None:
    reading = health(STALE_RELEASE)

    assert served_release(get=reading) == STALE_RELEASE
    assert reading.urls == [GUIDANCE_HEALTH_URL]
    assert GUIDANCE_HEALTH_URL == "https://mcp.ai4bcm.org/health"


def test_a_start_that_agrees_with_the_frozen_release_says_nothing_alarming() -> None:
    note = release_note(get=health(CORPUS_RELEASE))

    assert note == RELEASE_AGREES.format(served=CORPUS_RELEASE)
    assert "refuse" not in note


def test_a_start_against_the_wrong_release_names_both_tags_and_what_it_means() -> None:
    note = release_note(get=health(STALE_RELEASE))

    assert note == RELEASE_MISMATCH.format(served=STALE_RELEASE, expected=CORPUS_RELEASE)
    assert STALE_RELEASE in note and CORPUS_RELEASE in note
    assert "refuse" in note


def test_a_connector_that_will_not_say_does_not_stop_the_skin_from_starting() -> None:
    def unreachable(url: str) -> dict:
        raise LaneUnavailable(f"{url} did not answer: Connection refused")

    note = release_note(get=unreachable)

    assert note.startswith(RELEASE_UNREADABLE.split("(")[0])
    assert "Connection refused" in note


#: What a connector could answer the health page with: the frozen release, the one a deployment
#: left behind serves, an older one, and the empty string a misconfigured one reports. Sampled
#: rather than generated, so the branch where the two agree is drawn as often as the branch where
#: they do not — under this project's derandomized profile, `st.text()` would offer
#: `CORPUS_RELEASE` not once, and the agreeing half of the rule would go untested every run.
SERVED_TAGS = st.sampled_from([CORPUS_RELEASE, PREVIOUS_RELEASE, STALE_RELEASE, "2025.01.1", ""])


@given(SERVED_TAGS)
def test_the_start_note_agrees_exactly_when_the_connector_serves_the_release_we_expect(served):
    """One note, one decision, and whatever it read always in it.

    The three examples above pin the three sentences. What is pinned here is the rule that chooses
    between them, which is the whole of `release_note` and is pure — `get` is the only thing it
    touches and it is a parameter. A note that said "as expected" over a tag that is not ours
    would tell an operator the lane is answering on a day it refuses every question, and the
    check's own quietness (`docs/voice.md`: a check that shouts on a healthy corpus is ignored on
    an unhealthy one) is what makes that reading the likely one.
    """
    note = release_note(get=health(served))

    assert (note == RELEASE_AGREES.format(served=served)) == (served == CORPUS_RELEASE)
    assert served in note, "the note does not carry the tag it read"
    assert ("refuse" in note) == (served != CORPUS_RELEASE)


# -------------------- 2026.11.1, and only 2026.11.1 (ADR-0046, ADR-0062; tickets 285, 294, 673)
#
# Ticket 285 answered from 2026.09.1 too while the connector and the phone switched; 294 made it
# stale again. Ticket 673 re-pinned to 2026.11.1 with no switch window, because the connector
# serves only 2026.11.1 and 2026.11 is withdrawn: 2026.11 is stale now, like any other tag.

#: 2026.11's tenth source (ADR-0046 d4): NIST CSWP 29, the Cybersecurity Framework 2.0.
CSF_UNIT = "nist-cswp-29-csf-2-0"
CSF_ID = "nist-cswp-29-csf-2-0-appendix-c-glossary"


def test_the_release_is_2026_11_1() -> None:
    assert CORPUS_RELEASE == "2026.11.1"


def test_a_csf_chunk_is_cited_to_its_own_document_not_the_guideline() -> None:
    """Before 285, `source_of` called every unit it did not list the AI4BCM guideline."""
    assert source_of(CSF_UNIT) == CSF_UNIT
    lane = Lane()

    citation = ask(RTO_QUESTION, guidance=Guidance(search={"results": [{"id": CSF_ID}]}),
                   lane=lane).citations[0]

    assert citation.source == CSF_UNIT and citation.source in LITERATURE
    assert citation.document == "NIST CSWP 29 — The NIST Cybersecurity Framework (CSF) 2.0"
    assert told_sources(lane.prompts[0]) == [said_of(citation)]
    assert SAYS_GUIDANCE not in lane.prompts[0]


def test_a_chunk_stamped_2026_11_1_is_answered_from() -> None:
    lane = Lane()

    answer = ask(MTPD_QUESTION, guidance=restamped("2026.11.1"), lane=lane)

    assert answer.text == ANSWER
    assert len(answer.citations) == EXCERPTS
    assert len(lane.prompts) == 1


@pytest.mark.parametrize(
    "release", [PREVIOUS_RELEASE, STALE_RELEASE, "2026.10", "2026.11", "2026.09.2", ""]
)
def test_any_other_release_is_still_refused_as_stale(release) -> None:
    lane = Lane()

    answer = ask(MTPD_QUESTION, guidance=restamped(release), lane=lane)

    assert answer == Answer(WRONG_RELEASE.format(expected=CORPUS_RELEASE), ())
    assert lane.prompts == []


def test_a_chunk_recorded_at_the_previous_release_is_dropped_as_stale() -> None:
    """A body the connector served at 2026.09.1, kept as it arrived: today it is not corpus.

    The glossary leads the search here because 2026.11's ranking (ticket 306) took it out of the
    recorded MTPD top four; the three after it are that search's own first three.
    """
    previous = structured("previous-release-fetch-glossary")
    assert previous["metadata"]["release_tag"] == PREVIOUS_RELEASE
    hits = structured("guidance-search-mtpd")["results"]

    class Previous(Guidance):
        def __call__(self, tool: str, arguments: dict) -> dict:
            served = super().__call__(tool, arguments)
            return previous if arguments.get("id") == "glossary" else served

    answer = ask(
        MTPD_QUESTION,
        guidance=Previous(search={"results": [{"id": "glossary"}, *hits[: EXCERPTS - 1]]}),
        lane=Lane(),
    )

    assert "glossary" not in [hit["id"] for hit in hits]
    assert [c.locator for c in answer.citations if c.locator == "glossary"] == []
    assert len(answer.citations) == EXCERPTS - 1
    assert all(f"/blob/{CORPUS_RELEASE}/" in c.url for c in answer.citations)


def test_a_start_on_the_previous_release_is_a_mismatch_again() -> None:
    note = release_note(get=health(PREVIOUS_RELEASE))

    assert note == RELEASE_MISMATCH.format(served=PREVIOUS_RELEASE, expected=CORPUS_RELEASE)


def test_a_get_carries_no_body_and_no_authorization_header() -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(b'{"release_tag": "2026.11.1"}')

    assert get(GUIDANCE_HEALTH_URL, urlopen=fake_urlopen) == {"release_tag": CORPUS_RELEASE}
    request, timeout = requests[0]
    assert request.full_url == GUIDANCE_HEALTH_URL
    assert request.data is None and request.get_method() == "GET"
    assert request.get_header("Authorization") is None
    assert timeout == TIMEOUT_SECONDS


def test_the_health_page_is_asked_for_json_and_for_nothing_else(monkeypatch) -> None:
    """The one header the start-up read sends, spelled as it is sent, and no second one.

    `urllib.request.Request` title-cases every key it is handed and stores the value as given, so
    `get_header("Accept")` above answers the same for `accept`, `ACCEPT` and no `Accept` at all —
    the header could be dropped outright and that test would still pass. Recording the `Request`
    as it is built is the only place the spelling is visible, which is what the sibling test does
    for `post`. It matters on this GET for the same reason it matters there: the connector is an
    MCP server behind a proxy that content-negotiates, and the release tag this whole lane refuses
    on is read through it.
    """
    original = urllib.request.Request
    built: list[tuple[str, dict]] = []

    def record(url, data=None, headers=None):
        built.append((url, headers))
        return original(url, data=data, headers=headers)

    monkeypatch.setattr(urllib.request, "Request", record)
    get(GUIDANCE_HEALTH_URL, urlopen=lambda request, timeout: _Response(b"{}"))

    assert built == [(GUIDANCE_HEALTH_URL, {"Accept": "application/json"})]


def test_the_get_asks_for_json_alone_where_the_post_also_takes_an_event_stream(
    monkeypatch,
) -> None:
    """The two calls do not share a header table, and the difference is deliberate.

    `post` speaks to the MCP endpoint, which may answer a tool call as SSE, so it accepts both.
    The health page is a plain JSON document and is asked for as one. Reading both spellings out
    of the same recorder is what keeps a copy-paste between them from going unnoticed.
    """
    original = urllib.request.Request
    built: list[dict] = []

    def record(url, data=None, headers=None):
        built.append(headers)
        return original(url, data=data, headers=headers)

    monkeypatch.setattr(urllib.request, "Request", record)
    def responder(request, timeout):
        return _Response(b"{}")

    get(GUIDANCE_HEALTH_URL, urlopen=responder)
    post(GUIDANCE_URL, {"query": "mtpd"}, urlopen=responder)

    accepted, posted = built
    assert accepted == {"Accept": "application/json"}
    assert posted["Accept"] == "application/json, text/event-stream"
    assert accepted["Accept"] != posted["Accept"]
    assert "Content-Type" not in accepted, "a GET with no body declares no content type"


def test_a_health_page_that_does_not_answer_is_the_same_named_refusal() -> None:
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("Connection refused")

    with pytest.raises(LaneUnavailable) as raised:
        get(GUIDANCE_HEALTH_URL, urlopen=fake_urlopen)
    assert str(raised.value).startswith(f"{GUIDANCE_HEALTH_URL} did not answer: ")


# Retired by ticket 161:
# `test_the_skin_reads_the_release_at_start_and_puts_it_where_an_operator_sees_it` read demo_skin's
# startup hook; the phone app (skin/PROTOTYPE_conversation_app.py) had no startup hook then.
# Ticket 174 gave it one; it is pinned by behaviour in skin/tests/test_t174_corpus_release.py.


# ------------------------------------------------------ what the corpus does not cover


@pytest.mark.parametrize(
    ("question", "standard"),
    [
        ("What does ISO/TS 22317 say about setting an MTPD?", "ISO/TS 22317"),
        ("What does iso 22301 clause 8.2.2 require?", "ISO 22301"),
        (
            "What do the BCI Good Practice Guidelines say about PP4?",
            "the BCI Good Practice Guidelines",
        ),
    ],
)
def test_a_question_the_corpus_cannot_answer_says_so(question: str, standard: str) -> None:
    guidance, lane = Guidance(), Lane()
    answer = ask(question, guidance=guidance, lane=lane)
    assert answer == Answer(NOT_COVERED.format(standard=standard), ())
    assert standard in answer.text
    assert lane.prompts == [], "the model was asked about a text the corpus does not hold"
    assert guidance.calls == [], "the corpus was searched for a text it does not hold"


def test_nothing_is_invented_to_fill_the_gap() -> None:
    answer = ask("What does ISO/TS 22317 say about MTPD?", guidance=Guidance(), lane=Lane())
    assert answer.citations == ()
    assert "8.2" not in answer.text and "clause" not in answer.text
    assert answer.on_screen == answer.text


def test_the_three_standards_are_recognised_however_they_are_written() -> None:
    assert uncovered_standard("iso/ts 22317 and mtpd") == "ISO/TS 22317"
    assert uncovered_standard("ISO22301") == "ISO 22301"
    assert uncovered_standard("the bci good practice guidelines") == (
        "the BCI Good Practice Guidelines"
    )
    assert uncovered_standard(MTPD_QUESTION) is None


def test_the_decline_points_at_what_the_corpus_does_hold() -> None:
    text = NOT_COVERED.format(standard="ISO/TS 22317")
    for held in ("DORA", "NIST SP 800-34r1", "FONES", "Cabinet Office"):
        assert held in text


# --------------------------------------------------------------- the two hosts and the token


def test_the_corpus_is_read_from_the_open_guidance_connector() -> None:
    assert GUIDANCE_URL == "https://mcp.ai4bcm.org/mcp"
    assert LANE_URL == "http://127.0.0.1:4000/v1/chat/completions"
    assert "agent.ai4bcm.org" not in GUIDANCE_URL + LANE_URL


def test_a_guidance_call_is_a_json_rpc_tool_call_carrying_no_bearer_token() -> None:
    sent: list[tuple[str, dict]] = []
    reply = fixture(f"guidance-fetch-{WORKFLOW_ID}")

    def fake_post(url: str, payload: dict) -> dict:
        sent.append((url, payload))
        return reply

    assert call_guidance("fetch", {"id": WORKFLOW_ID}, post=fake_post) == structured(
        f"guidance-fetch-{WORKFLOW_ID}"
    )
    assert sent == [
        (
            GUIDANCE_URL,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "fetch", "arguments": {"id": WORKFLOW_ID}},
            },
        )
    ]


def test_the_lane_is_asked_on_the_named_model_and_only_its_content_is_read() -> None:
    sent: list[tuple[str, dict]] = []
    body = fixture("lane-completion")
    body["choices"][0]["message"]["reasoning"] = "the thinking the lane excludes"

    def fake_post(url: str, payload: dict) -> dict:
        sent.append((url, payload))
        return body

    assert call_lane("Reply with the single word: ready", post=fake_post) == "ready"
    assert sent == [
        (
            LANE_URL,
            {
                "model": "ai4bcm/glm-5.3-flash-fastest",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
            },
        )
    ]
    assert MODEL == "ai4bcm/glm-5.3-flash-fastest"


#: Ticket 216: what no request on the lane may carry, at the top level or inside a message.
#: `extra_body` first: the gateway alias pins `provider: {zdr: true}` in its own `extra_body`
#: (ADR-0036, ADR-0021), and litellm's merge is shallow, so a request that sends one replaces that
#: block whole — delegates' words would leave the lane without zero data retention. The rest are
#: the model's and the gateway's to settle: `tool_choice` (the lane sends no tools at all, and
#: FlashX would refuse anything but "auto"), `temperature` and `top_p` (the defaults stand), and
#: `reasoning` or `reasoning_details`, which the alias sets and a previous turn never echoes back.
STRIPS_THE_PIN_OR_OVERRIDES_THE_LANE = (
    "extra_body",
    "tool_choice",
    "temperature",
    "top_p",
    "reasoning",
    "reasoning_details",
)


def test_the_lane_request_carries_nothing_that_could_strip_its_zdr_pin() -> None:
    """A request's own `extra_body` would replace the alias's `provider: {zdr: true}` whole, and
    the rest of these keys override what the gateway and the model already settle."""
    sent: list[dict] = []

    def fake_post(url: str, payload: dict) -> dict:
        sent.append(payload)
        return fixture("lane-completion")

    call_lane("Reply with the single word: ready", post=fake_post)
    [payload] = sent
    for key in STRIPS_THE_PIN_OR_OVERRIDES_THE_LANE:
        assert key not in payload, f"the lane request carries {key}"
        for message in payload["messages"]:
            assert key not in message, f"a message sent to the lane carries {key}"


def test_the_lane_can_be_pointed_at_a_dead_port_to_rehearse_the_stop(monkeypatch) -> None:
    assert LANE_URL_ENV == "NEMO_LANE_URL"
    monkeypatch.delenv(LANE_URL_ENV, raising=False)
    assert lane_url() == LANE_URL
    monkeypatch.setenv(LANE_URL_ENV, "http://127.0.0.1:4999/v1/chat/completions")
    assert lane_url() == "http://127.0.0.1:4999/v1/chat/completions"

    sent: list[str] = []
    call_lane("anything", post=lambda url, payload: sent.append(url) or fixture("lane-completion"))
    assert sent == ["http://127.0.0.1:4999/v1/chat/completions"]


def test_a_post_carries_json_and_no_authorization_header() -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(b'{"ok": true}')

    assert post(GUIDANCE_URL, {"query": "mtpd"}, urlopen=fake_urlopen) == {"ok": True}
    request, timeout = requests[0]
    assert request.full_url == GUIDANCE_URL
    assert json.loads(request.data) == {"query": "mtpd"}
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Accept") == "application/json, text/event-stream"
    assert request.get_header("Authorization") is None
    assert timeout == TIMEOUT_SECONDS == 80


def test_the_request_is_built_with_exactly_the_two_headers_the_connector_wants(monkeypatch) -> None:
    """The two header names, spelled as they are sent.

    `urllib.request.Request` capitalises every key it is handed — `content-type`, `CONTENT-TYPE`
    and `Content-Type` all become `Content-type` — so `get_header` above cannot see the spelling
    and cannot see a third header appearing either. Here, where the `Request` is built, it can.
    """
    original = urllib.request.Request
    built: list[dict] = []

    def record(url, data=None, headers=None):
        built.append(headers)
        return original(url, data=data, headers=headers)

    monkeypatch.setattr(urllib.request, "Request", record)
    post(GUIDANCE_URL, {"query": "mtpd"}, urlopen=lambda request, timeout: _Response(b"{}"))

    assert built == [
        {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    ]


# ---------------------------------------------------------- the cap is a legible stop


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError(LANE_URL, 402, "Payment Required", {}, None),
        urllib.error.URLError("Connection refused"),
        ValueError("not JSON"),
    ],
)
def test_any_failure_of_the_call_is_one_named_refusal(failure: Exception) -> None:
    def fake_urlopen(request, timeout):
        raise failure

    with pytest.raises(LaneUnavailable) as raised:
        post(LANE_URL, {}, urlopen=fake_urlopen)
    assert str(raised.value) == f"{LANE_URL} did not answer: {failure}"


def test_the_cap_is_told_plainly_and_leaves_the_room_usable() -> None:
    answer = ask(MTPD_QUESTION, guidance=Guidance(), lane=Lane(unavailable=True))
    assert answer == Answer(UNAVAILABLE, ())
    assert "unavailable" in answer.on_screen
    assert "402" not in answer.on_screen and "Traceback" not in answer.on_screen


def test_a_real_402_under_the_lane_is_asked_once_and_read_as_the_plain_sentence() -> None:
    """Ticket 111: the lane now re-asks a stall, and ADR-0009 still holds for the cap. The 402 is
    raised by `urlopen` itself, under the real `post` and `call_lane`, so the one try is the lane's
    own count and not a fake's."""
    tries: list = []

    def capped(request, timeout):
        tries.append(timeout)
        raise urllib.error.HTTPError(LANE_URL, 402, "Payment Required", {}, None)

    def lane(prompt: str) -> str:
        return call_lane(prompt, post=lambda url, payload: post(url, payload, urlopen=capped))

    answer = ask(MTPD_QUESTION, guidance=Guidance(), lane=lane)
    assert answer == Answer(UNAVAILABLE, ())
    assert len(tries) == 1, "a 402 was asked again"


def test_the_cap_fails_the_same_way_at_once_and_offers_no_substitute() -> None:
    guidance, lane = Guidance(), Lane(unavailable=True)
    first = ask(MTPD_QUESTION, guidance=guidance, lane=lane)
    second = ask("What does the corpus say about an RTO?", guidance=guidance, lane=lane)
    assert first == second == Answer(UNAVAILABLE, ())
    assert len(lane.prompts) == 2, "the second question was answered from something cached"
    assert second.citations == ()


def test_a_connector_that_does_not_answer_is_the_same_legible_stop() -> None:
    def guidance(tool: str, arguments: dict) -> dict:
        raise LaneUnavailable("the connector did not answer")

    assert ask(MTPD_QUESTION, guidance=guidance, lane=Lane()) == Answer(UNAVAILABLE, ())


# ------------------------------------------------------------- asking touches no record


def test_asking_never_touches_the_record(tmp_path) -> None:
    record = {"company": "Slaughter", "activities": []}
    saved = write_record(tmp_path, "output/bia-record.json", record, 0)
    before = tmp_path / "output" / "bia-record.json"
    stat, sha = before.stat(), fingerprint(saved)

    guidance, lane = Guidance(), Lane()
    for _ in range(6):
        ask(MTPD_QUESTION, guidance=guidance, lane=lane)
        ask("What does ISO/TS 22317 say?", guidance=guidance, lane=lane)

    reread = read_record(tmp_path, "output/bia-record.json")
    assert reread is not None
    assert fingerprint(reread) == sha
    assert (before.stat().st_mtime_ns, before.stat().st_size) == (stat.st_mtime_ns, stat.st_size)


# ------------------------------------------------- the pure functions, as properties

# `uncovered_standard`, `source_of` and the two `__str__`/`on_screen` renderings are the whole of
# this module that touches neither the connector nor the lane: a question in, a verdict out. The
# examples above pin the three standards and the ten sources by name, which is what a reader
# needs; these pin the shape of the answer for questions and units nobody thought to type.


#: Words that cannot spell any of the three marks, so only the injected one is ever present.
INNOCENT = st.text(alphabet="abc ", max_size=12)


@given(st.sampled_from(sorted(UNCOVERED)), INNOCENT, INNOCENT)
def test_a_question_naming_an_uncovered_standard_is_always_declined(mark, before, after) -> None:
    """However the mark is buried in a sentence, the standard is recognised and named back."""
    standard = uncovered_standard(f"{before}{mark.upper()}{after}")

    assert standard == UNCOVERED[mark]


@given(st.text(max_size=40))
def test_a_question_naming_none_of_the_three_is_never_declined(question) -> None:
    """Nothing else is second-guessed for the model: only those three are decided here.

    "Names one" is `norm`'s judgement and the guard is stated in its terms, not in `.lower()`'s.
    Written the other way this test is not stricter, it is flaky: `norm` strips the markdown a
    word processor leaves behind, so a generated `2*2301` names the standard while `.lower()`
    says it does not, and the run that first produced one would fail a correct decline.
    """
    assume(not any(mark in norm(question) for mark in UNCOVERED))

    assert uncovered_standard(question) is None


@given(st.sampled_from(sorted(UNCOVERED)), st.text(max_size=12))
def test_a_declined_question_never_reaches_the_connector_or_the_lane(mark, after) -> None:
    """The decline is taken before both hosts, because the answer is already known."""
    guidance, lane = Guidance(), Lane()

    answer = ask(f"What does {mark}{after} say?", guidance=guidance, lane=lane)

    assert answer.citations == ()
    assert guidance.calls == []
    assert lane.prompts == []


@given(st.text(max_size=20))
def test_every_unit_belongs_to_exactly_one_of_the_ten_sources(unit) -> None:
    """A chunk from a unit nobody listed is the guideline's, never an invented eleventh source."""
    source = source_of(unit)

    assert source in SOURCES
    assert source == (unit if unit in LITERATURE else GUIDELINE)


@given(st.lists(st.text(max_size=10), min_size=1, max_size=4, unique=True))
def test_each_literature_unit_is_its_own_source_and_the_rest_are_the_guideline(units) -> None:
    """The nine documents stand for themselves; the project's own units collapse into one."""
    assert [source_of(unit) for unit in LITERATURE] == list(LITERATURE)
    assume(not set(units) & set(LITERATURE))
    assert {source_of(unit) for unit in units} == {GUIDELINE}


# The decline reads the question through the package's one normalizer, which is what makes a
# pasted question and a typed one the same question. Both halves are properties: every mark is
# reachable by that normalizer at all, and no amount of word-processor mangling hides one.

#: What a word processor substitutes behind the writer's back, as `nemo.text` folds it back.
SUBSTITUTIONS = {"'": "’", '"': "“", "-": "–", " ": " "}


@given(st.sampled_from(sorted(UNCOVERED)))
def test_every_mark_is_spelled_in_the_normal_form_the_question_is_read_in(mark) -> None:
    """A mark that is not its own normal form can never be found, however it is asked about."""
    assert norm(mark) == mark


@given(st.sampled_from(sorted(UNCOVERED)), INNOCENT, INNOCENT)
def test_a_standard_named_in_a_pasted_question_is_declined_like_a_typed_one(
    mark, before, after
) -> None:
    """The one that bites: "Good Practice Guidelines" pasted out of Word carries a hard space.

    A bare `.lower()` declines the typed spelling and answers the pasted one — from a corpus that
    does not hold that text, which is the whole of what ADR-0005 says must not happen. Bolded and
    hard-spaced at once, because a paste arrives carrying both.
    """
    pasted = "".join(SUBSTITUTIONS.get(character, character) for character in mark.upper())

    assert uncovered_standard(f"{before}**{pasted}**{after}") == UNCOVERED[mark]


@given(st.text(max_size=40))
def test_a_question_the_corpus_matched_nothing_for_is_always_the_same_refusal(question) -> None:
    """Whatever was asked, a corpus that matched nothing is never reported as a release problem."""
    assume(uncovered_standard(question) is None)
    guidance, lane = Guidance(search={"results": []}), Lane()

    answer = ask(question, guidance=guidance, lane=lane)

    assert answer == Answer(NOTHING_MATCHED, ())
    assert lane.prompts == [], "the model was asked to answer from no excerpts at all"
    assert CORPUS_RELEASE not in answer.text


@given(
    st.lists(
        st.sampled_from([CORPUS_RELEASE, PREVIOUS_RELEASE, STALE_RELEASE, "2025.12", ""]),
        min_size=EXCERPTS,
        max_size=EXCERPTS,
    )
)
def test_the_lane_is_never_asked_to_answer_from_no_excerpt_whatever_the_tags_are(tags) -> None:
    """The property the probe on ticket 11 broke, over every mix of tags rather than two.

    The filter keeps exactly the chunks stamped the frozen release; whether that leaves four, one
    or none is the connector's business. What is this module's business is that the model is
    called if and only if something survived, and that every card it ever sees has an excerpt
    under it. A partial corpus still answers — only an empty one refuses.
    """
    guidance, lane = restamped_each(tags), Lane()

    answer = ask(MTPD_QUESTION, guidance=guidance, lane=lane)

    kept = tags.count(CORPUS_RELEASE)
    assert len(answer.citations) == kept
    assert len(lane.prompts) == (1 if kept else 0)
    for prompt in lane.prompts:
        assert prompt.count("Excerpt from ") == kept >= 1
    if kept:
        assert answer.text == ANSWER
    else:
        assert answer == Answer(WRONG_RELEASE.format(expected=CORPUS_RELEASE), ())
    assert ("Source:" in answer.on_screen) == bool(kept)


@given(st.text(max_size=30), st.lists(st.text(max_size=8), max_size=3))
def test_the_screen_shows_the_answer_and_one_source_line_per_citation(text, urls) -> None:
    """`on_screen` invents nothing and drops nothing: the answer, then every citation."""
    citations = tuple(
        Excerpt(document="d", locator="l", source=GUIDELINE, url=url, text="t") for url in urls
    )

    on_screen = Answer(text, citations).on_screen

    assert on_screen.startswith(text)
    assert on_screen.count("\n\nSource: ") == len(citations)
    for citation in citations:
        assert str(citation) in on_screen


@given(st.text(max_size=10), st.text(max_size=10), st.text(max_size=10))
def test_a_citation_line_carries_the_document_the_locator_and_the_url(document, locator, url):
    """Every part of the citation comes from the connector's own fields and is printed whole."""
    line = str(Excerpt(document=document, locator=locator, source=GUIDELINE, url=url, text="t"))

    assert line == f"{document} > {locator} — {url}"


# ------------------------------------------------------------------------------ helpers


class _Response:
    """The context manager `urlopen` returns, with only the one method `post` uses."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def _workflow_excerpt() -> Excerpt:
    """The citation the recorded workflow-design chunk produces, for the tests that read one.

    Third of the recorded MTPD search at 2026.11.1 (ticket 673); second at 2026.11 (ticket 306),
    last before that.
    """
    answer = ask(MTPD_QUESTION, guidance=Guidance(), lane=Lane())
    return answer.citations[2]


#: Ticket 209. Three 200s that carry no result: a JSON-RPC error object, a reply of the wrong
#: kind altogether, and a result with no `structuredContent`.
_NO_RESULT = [
    {"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "Internal error"}},
    {"choices": []},
    {"jsonrpc": "2.0", "id": 1, "result": {"content": []}},
]


@pytest.mark.parametrize("reply", _NO_RESULT)
def test_a_connector_reply_with_no_result_in_it_is_the_one_refusal_naming_its_shape(
    reply: dict,
) -> None:
    with pytest.raises(LaneUnavailable) as raised:
        call_guidance("search", {"query": MTPD_QUESTION}, post=lambda url, payload: reply)
    assert str(raised.value) == f"{GUIDANCE_URL} answered with no answer in it: {json.dumps(reply)}"


@pytest.mark.parametrize("reply", _NO_RESULT)
def test_a_malformed_connector_reply_is_the_unavailable_sentence(reply: dict) -> None:
    """What the manager sees: the one sentence, never a traceback."""

    def guidance(tool: str, arguments: dict) -> dict:
        return call_guidance(tool, arguments, post=lambda url, payload: reply)

    assert ask(MTPD_QUESTION, guidance=guidance, lane=Lane()) == Answer(UNAVAILABLE, ())


@pytest.mark.parametrize(
    "reply",
    [
        {"error": {"message": "Provider returned error"}},
        {"choices": []},
        {"choices": [{"message": {"role": "assistant"}}]},
        {"choices": [{"message": {"role": "assistant", "content": None}}]},
    ],
)
def test_a_malformed_lane_reply_is_the_unavailable_sentence(reply: dict) -> None:
    def lane(prompt: str) -> str:
        return call_lane(prompt, post=lambda url, payload: reply)

    assert ask(MTPD_QUESTION, guidance=Guidance(), lane=lane) == Answer(UNAVAILABLE, ())
