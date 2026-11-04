"""The model lane's own properties, proved without importing either of its callers.

`nemo.lane` was split out of `nemo.ask` in ticket 17 precisely because `nemo.conduct` needed the
same HTTP and should not have to import a guidance corpus to place one call. A module that sits
below two callers should be provable below them too: nothing in this file imports `nemo.ask` or
`nemo.conduct`, so the day either one changes, a red line here is about the lane and not about
the module that happened to drive it.

What `src/nemo/test_ask.py` holds instead is the *difference* between the two hosts — the
connector's headers against the health page's, recorded off one harness so a copy-paste between
them shows up. Those are examples about a pair. These are properties about the lane itself: the
header that is never sent, the payload that arrives as it was given, the one exception every
failure becomes, and the single field a reply is read for.

No test in this file opens a socket: `urlopen` is a parameter with a real default, and every
call here passes a stand-in.
"""

import io
import json
import os
import urllib.error
from unittest.mock import patch

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

import nemo.lane
from nemo.lane import (
    LANE_URL,
    LANE_URL_ENV,
    MAX_TOKENS,
    MODEL,
    TIMEOUT_SECONDS,
    LaneUnavailable,
    call_lane,
    get,
    lane_url,
    post,
)

# The strategies. Bands are stated rather than left to the default, because the profile in
# `conftest.py` is derandomized: hypothesis draws the same examples every run, so a strategy
# that merely *could* offer an interesting value is not the same as one that does.

#: Printable text with the awkward characters in it — the quotes and dashes a word processor
#: substitutes, and a script outside latin-1 — because the payload is encoded on its way out.
_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=0, max_size=40
)

#: JSON scalars. The integer band is small and explicitly two-sided so that both 0 and a negative
#: number are actually drawn; a bare `st.integers()` under `derandomize` offers neither reliably.
_SCALARS = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-1000, max_value=1000)
    | _TEXT
)

#: What a caller hands `post`: a JSON object, sometimes nested one level.
_PAYLOADS = st.dictionaries(
    st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=1, max_size=12),
    _SCALARS | st.lists(_SCALARS, max_size=3),
    max_size=5,
)

#: Somewhere on loopback. Never opened — every test hands `post`/`get` its own `urlopen`.
_URLS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", max_size=20).map(
    lambda path: f"http://127.0.0.1:4000/{path}"
)

#: The ways a lane stops answering. The cap arrives as one of these, and so does a dead port.
_FAILURES = st.sampled_from(
    [OSError, ValueError, TimeoutError, ConnectionRefusedError, urllib.error.URLError]
)


class _Response:
    """The context manager `urlopen` returns, with only the one method the lane uses."""

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def _answering(body: bytes, seen: list) -> object:
    """An `urlopen` that records the request it was given and answers with fixed bytes."""

    def urlopen(request, timeout):
        seen.append((request, timeout))
        return _Response(body)

    return urlopen


def _authorization(request) -> list:
    """Every header on the request whose name is `Authorization`, however it is spelled.

    `Request.get_header` title-cases the name it is asked for, so asking it alone cannot tell a
    header that is absent from one spelled `AUTHORIZATION`. Reading the table is what can.
    """
    return [value for name, value in request.header_items() if name.lower() == "authorization"]


@given(url=_URLS, payload=_PAYLOADS)
def test_a_post_never_carries_an_authorization_header_whatever_it_is_sending(url, payload):
    """The lane takes no key and the connector is open (ADR-0005), so there is none to leak.

    Whatever the caller is posting and wherever, there is no credential in the request: a public
    visitor's question travels the same bytes as anything else.
    """
    seen: list = []

    post(url, payload, urlopen=_answering(b"{}", seen))

    request, _timeout = seen[0]
    assert _authorization(request) == []


@given(url=_URLS)
def test_a_get_never_carries_an_authorization_header_and_never_a_body(url):
    """The health page is public. A GET with no body declares nothing and asks with nothing."""
    seen: list = []

    get(url, urlopen=_answering(b"{}", seen))

    request, _timeout = seen[0]
    assert _authorization(request) == []
    assert request.data is None
    assert request.get_method() == "GET"


@given(url=_URLS, payload=_PAYLOADS)
def test_a_post_sends_the_payload_it_was_given_and_not_a_word_more(url, payload):
    """The bytes on the wire are the caller's object, and they come back as the same object.

    Byte equality is the wrong claim — `json.dumps` escapes a non-ASCII character on its way out —
    so the property is the round trip: whatever the encoder spells, decoding it returns exactly
    what the caller handed in, with no key added, dropped or reordered into a different meaning.
    """
    seen: list = []

    post(url, payload, urlopen=_answering(b"{}", seen))

    request, timeout = seen[0]
    assert json.loads(request.data.decode()) == payload
    assert request.full_url == url
    assert request.get_method() == "POST"
    assert timeout == TIMEOUT_SECONDS


@given(url=_URLS)
def test_a_get_asks_at_the_url_it_was_given_and_waits_the_one_timeout(url):
    """One timeout for both verbs: an unavailable lane is a stop, not a longer wait."""
    seen: list = []

    get(url, urlopen=_answering(b"{}", seen))

    request, timeout = seen[0]
    assert request.full_url == url
    assert timeout == TIMEOUT_SECONDS


def _refused_as(url: str, failure: type) -> str:
    """How the refusal opens: a stall has been asked `TRIES` times by then (ticket 191's words,
    ruling B on 111 x 191); every other failure was asked once."""
    if failure is TimeoutError:
        return f"{url} did not answer in {nemo.lane.TRIES} tries: "
    return f"{url} did not answer: "


@given(url=_URLS, failure=_FAILURES, message=_TEXT)
def test_every_way_a_post_can_fail_is_the_one_named_refusal(url, failure, message):
    """A 402 from the cap, a refused connection, a body that is not JSON: one exception.

    Nothing in the lane parses an error, because the cap is a hard stop rather than a degradation
    (ADR-0009) and both callers act on all of them the same way. What the manager is told is said
    upstairs, by `nemo.ask` or `nemo.conduct`, which is why the difference is not down here.
    """

    def unreachable(request, timeout):
        raise failure(message)

    with pytest.raises(LaneUnavailable) as raised:
        post(url, {"q": "mtpd"}, urlopen=unreachable)
    assert str(raised.value).startswith(_refused_as(url, failure))


@given(url=_URLS, failure=_FAILURES, message=_TEXT)
def test_every_way_a_get_can_fail_is_the_one_named_refusal(url, failure, message):
    """The health read stops the same way the lane does, and names the same url."""

    def unreachable(request, timeout):
        raise failure(message)

    with pytest.raises(LaneUnavailable) as raised:
        get(url, urlopen=unreachable)
    assert str(raised.value).startswith(_refused_as(url, failure))


@given(url=_URLS, body=_TEXT)
def test_a_body_that_is_not_json_is_the_same_refusal_and_never_a_half_read_reply(url, body):
    """An HTML error page from a proxy is a failure to answer, not an answer to parse."""
    raw = body.encode()
    try:
        json.loads(raw)
    except ValueError:
        pass
    else:
        assume(False)

    with pytest.raises(LaneUnavailable):
        post(url, {"q": "mtpd"}, urlopen=lambda request, timeout: _Response(raw))


@given(prompt=_TEXT, content=_TEXT)
def test_the_lane_is_asked_on_the_named_model_with_the_prompt_character_for_character(
    prompt, content
):
    """One user message, the prompt as it was written, on the alias ADR-0008 pins."""
    sent: list = []

    def fake_post(url, payload):
        sent.append((url, payload))
        return {"choices": [{"message": {"content": content}}]}

    call_lane(prompt, post=fake_post)

    url, payload = sent[0]
    assert url == lane_url()
    assert payload == {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }


@given(prompt=_TEXT)
def test_every_request_caps_what_the_model_may_spend_at_the_named_ceiling(prompt):
    """Ticket 187: a request without `max_tokens` reserves 131072 tokens against the capped key.

    OpenRouter refuses with a 402 as soon as the key cannot afford that reservation, long before
    the key is actually spent, so every call names its own ceiling and the ceiling is the constant.
    """
    sent: list = []

    def fake_post(url, payload):
        sent.append(payload)
        return {"choices": [{"message": {"content": "ok"}}]}

    call_lane(prompt, post=fake_post)

    assert sent[0].get("max_tokens") == MAX_TOKENS


@given(content=_TEXT, reasoning=_TEXT)
def test_only_the_content_of_a_reply_is_read_however_much_else_it_carries(content, reasoning):
    """The lane pins `reasoning: {exclude: true}`, and reading `content` alone is the belt.

    Whatever else a reply grows — a reasoning trace, a second choice, a usage block — the answer
    is the first choice's content and exactly its characters. A reply that started carrying the
    thinking would still not put it on a manager's screen.
    """

    def fake_post(url, payload):
        return {
            "choices": [
                {"message": {"content": content, "reasoning": reasoning}},
                {"message": {"content": "the second choice nobody reads"}},
            ],
            "usage": {"total_tokens": 1},
        }

    assert call_lane("anything", post=fake_post) == content


@given(where=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789.:/-", min_size=1, max_size=40))
def test_the_lane_can_be_pointed_anywhere_an_operator_names_and_nowhere_else(where):
    """The dead-port rehearsal `docs/research/ask-lane-live-run.md` §3 tells an operator to run.

    Set, the variable wins outright; unset, the loopback gateway is where the lane is. The unit
    names no such variable, so production reads the default and nothing else.
    """
    with patch.dict(os.environ, {LANE_URL_ENV: where}):
        assert lane_url() == where

    with patch.dict(os.environ, {}, clear=True):
        assert lane_url() == LANE_URL


def test_an_empty_setting_is_not_a_place_and_the_default_stands():
    """An exported-but-blank variable is an operator who set nothing, not a lane at an empty url."""
    with patch.dict(os.environ, {LANE_URL_ENV: ""}):
        assert lane_url() == LANE_URL


# ---------------------------------------------- the stall, and the cap that is not one
#
# Ticket 111 (33's nemo half). The skin's lane already keeps three rules, and this lane keeps the
# same three: a stall is re-asked, up to `TRIES` tries (1 since ticket 198, his 15:18:03Z ruling —
# the loop stays and the number is his one-line call); a spent cap (402) is
# never retried; no single try waits longer than `TIMEOUT_SECONDS`. A stall and a cap are told
# apart by what the lane did, not by a clock: a stall is `urlopen` running out of time and raising
# `TimeoutError` (bare on a read, wrapped in `URLError` on a connect); the cap is the lane
# *answering*, with a 402, which arrives as an `HTTPError`. No test here waits: the fakes raise at
# once, so an outage of the real lane can never red one of them.


class _Lane:
    """An `urlopen` that takes the next outcome on each call — an exception to raise, or bytes to
    answer with — repeats its last one when it runs out, and records the timeout of every try."""

    def __init__(self, *outcomes: object) -> None:
        self.outcomes, self.timeouts = list(outcomes), []

    def __call__(self, request, timeout):
        self.timeouts.append(timeout)
        nxt = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(nxt, BaseException):
            raise nxt
        return _Response(nxt)


def _capped(url: str) -> urllib.error.HTTPError:
    """The cap as the lane says it: an answered 402 (`skin/tests/test_t33_lanes.py`'s body)."""
    return urllib.error.HTTPError(url, 402, "Payment Required", {}, None)


def test_the_lane_asks_a_stall_once_in_all():
    """nemo's own number, one like the skin's (229). Ticket 198, his ruling of 2026-09-28 15:18:03Z:
    ONE try of 80 s, an 80 s worst case, strictly inside the UI's 90 s page wait. lanediag measured
    the same request at 20-99 s on this route and a second try thinking just as long again, so the
    re-ask bought a doubled stall rather than a reroute. The loop in `_read` stays, driven by
    `TRIES`, so raising the number again is his one-line call. The skin's is his apart (229)."""
    assert nemo.lane.TRIES == 1


def test_one_call_lane_post_is_at_most_tries_attempts_the_retry_is_never_nested():
    """One retry loop, in `_read`: `call_lane` asks through it and has none of its own, so a lane
    that always stalls costs `TRIES` attempts, never `TRIES` squared. Read from `TRIES` rather
    than spelled, so it stays the nesting's pin whatever number he sets (ticket 198)."""
    lane = _Lane(TimeoutError("timed out"))

    with pytest.raises(LaneUnavailable):
        call_lane("anything", post=lambda url, payload: post(url, payload, urlopen=lane))
    assert len(lane.timeouts) <= nemo.lane.TRIES


@pytest.mark.parametrize("stall", [TimeoutError("the read timed out"),
                                   urllib.error.URLError(TimeoutError("connect timed out"))],
                         ids=["read", "connect"])
def test_a_stall_is_re_asked_and_the_next_answer_is_the_reply(stall, monkeypatch):
    """The loop itself, which ticket 198 kept while setting `TRIES` to 1: with the number put back
    to 2 the second try still answers, so raising it again is a one-line change, not a rebuild."""
    monkeypatch.setattr(nemo.lane, "TRIES", 2)
    lane = _Lane(stall, b'{"ok": true}')

    assert post(LANE_URL, {"q": "mtpd"}, urlopen=lane) == {"ok": True}
    assert lane.timeouts == [TIMEOUT_SECONDS, TIMEOUT_SECONDS]


def test_a_lane_that_keeps_stalling_is_asked_tries_times_and_then_refuses(caplog):
    """Each stall is logged as a warning on `nemo.lane`, so a human finds it after the demo in the
    unit's journal: a silent re-ask is how a lane's health stops being visible."""
    lane = _Lane(TimeoutError("timed out"))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable) as raised:
        post(LANE_URL, {"q": "mtpd"}, urlopen=lane)
    assert lane.timeouts == [TIMEOUT_SECONDS] * nemo.lane.TRIES
    assert str(raised.value) == f"{LANE_URL} did not answer in {nemo.lane.TRIES} tries: timed out"
    stalls = [r.getMessage() for r in caplog.records if r.name == "nemo.lane"]
    assert len(stalls) == nemo.lane.TRIES
    assert f"try 1 of {nemo.lane.TRIES}" in stalls[0]
    assert f"try {nemo.lane.TRIES} of {nemo.lane.TRIES}" in stalls[-1]


def test_the_stall_warning_names_the_lane_the_try_and_what_the_lane_did(caplog):
    """The module's words: "Each stall is a warning on this module's logger ... where a human
    finds it after the demo." What that human needs is in the line itself — which lane was
    asked, which try of how many this was, and what went wrong — so it is read whole here."""
    lane = _Lane(TimeoutError("timed out"))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(LANE_URL, {"q": "mtpd"}, urlopen=lane)
    assert [r.getMessage() for r in caplog.records if r.name == "nemo.lane"] == [
        f"{LANE_URL} stalled on try 1 of {nemo.lane.TRIES}: timed out"]


def test_a_lane_that_is_asked_no_times_at_all_says_so_rather_than_answering_nothing(monkeypatch):
    """`_read` ends "unreachable: the loop returns or raises", and while `TRIES` is at least one
    it is: every try returns, raises, or is the last. The one way to reach it is a `TRIES` of
    nought, which is no configuration the unit has — and then it is loud, not a silent `None`."""
    monkeypatch.setattr(nemo.lane, "TRIES", 0)
    lane = _Lane(b'{"ok": true}')

    with pytest.raises(AssertionError) as raised:
        post(LANE_URL, {"q": "mtpd"}, urlopen=lane)
    assert str(raised.value) == "unreachable: the loop returns or raises"
    assert lane.timeouts == [], "the lane was not asked at all"


def test_no_try_waits_past_80_s():
    """The ceiling holds per try, re-asks included: the worst stall is TRIES x 80 s. 80 s is his
    ruling of 2026-09-28 15:18:03Z, and with TRIES at 1 the worst case is the 80 s itself."""
    lane = _Lane(TimeoutError("timed out"))

    with pytest.raises(LaneUnavailable):
        get(LANE_URL, urlopen=lane)
    assert lane.timeouts and all(t <= 80 for t in lane.timeouts)
    assert TIMEOUT_SECONDS == 80


@given(url=_URLS, status=st.integers(min_value=400, max_value=599), phrase=_TEXT)
def test_an_answered_refusal_the_cap_s_402_among_them_is_never_asked_again(url, status, phrase):
    """ADR-0009: the cap is a hard stop, and every call fails at once when it is reached, so a
    retry buys nothing. The lane answered, so no time ran out — even when its status phrase says
    "timed out", because the stall is read from the exception's type and never from its words."""
    lane = _Lane(urllib.error.HTTPError(url, status, phrase, {}, None), b"{}")

    with pytest.raises(LaneUnavailable):
        post(url, {"q": "mtpd"}, urlopen=lane)
    assert lane.timeouts == [TIMEOUT_SECONDS]


def test_the_cap_is_asked_once():
    lane = _Lane(_capped(LANE_URL), b"{}")

    with pytest.raises(LaneUnavailable) as raised:
        post(LANE_URL, {"q": "mtpd"}, urlopen=lane)
    assert len(lane.timeouts) == 1
    assert "402" in str(raised.value), "the log keeps the lane's own words for the check session"


@given(failure=st.sampled_from([OSError, ValueError, ConnectionRefusedError]), message=_TEXT)
def test_a_dead_port_or_an_unreadable_body_is_not_a_stall_and_is_asked_once(failure, message):
    """A refused connection answered at once, bare or wrapped the way urllib wraps a connect:
    only a `TimeoutError` is a stall. The dead-port rehearsal stays one fast stop."""
    for raised in (failure(message), urllib.error.URLError(failure(message))):
        lane = _Lane(raised, b"{}")
        with pytest.raises(LaneUnavailable):
            get(LANE_URL, urlopen=lane)
        assert len(lane.timeouts) == 1


# ── ticket 191: a timeout is asked again, nothing else is ────────────────────


def _scripted(*outcomes: object) -> tuple[list, object]:
    """A poster over the real `post`, whose `urlopen` takes the next outcome on each call.

    An outcome is an exception to raise inside `urlopen` or the content of a reply, so the
    `LaneUnavailable` and its cause are built by the lane's own code rather than by the test.
    """
    posts: list = []
    queue = list(outcomes)

    def urlopen(request, timeout):
        posts.append(timeout)
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return _Response(json.dumps({"choices": [{"message": {"content": outcome}}]}).encode())

    return posts, lambda url, payload: post(url, payload, urlopen=urlopen)


def _refusal(status: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(LANE_URL, status, "refused", {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("stall", [
    lambda: TimeoutError("timed out"),
    lambda: urllib.error.URLError(TimeoutError("timed out")),
], ids=["read-timeout", "connect-timeout"])
def test_a_timeout_is_asked_again_and_the_second_try_s_answer_is_the_answer(stall, monkeypatch):
    """Ticket 191: a conduct call often spends 20 s reasoning, and 3 in 8 hit the then 30 s cap.
    `TRIES` is 1 since ticket 198, so the loop is proven here with the number put back to 2."""
    monkeypatch.setattr(nemo.lane, "TRIES", 2)
    posts, poster = _scripted(stall(), "what does the process do?")

    assert call_lane("anything", post=poster) == "what does the process do?"
    assert posts == [TIMEOUT_SECONDS] * 2


def test_two_timeouts_are_one_refusal_that_names_the_two_tries_and_there_is_no_third(monkeypatch):
    """What the refusal says when the loop has run out, with `TRIES` put back to 2: the number is
    named and there is no third try. `TRIES` is 1 in production since ticket 198 (80 s, one try)."""
    monkeypatch.setattr(nemo.lane, "TRIES", 2)
    stall = TimeoutError("timed out")
    posts, poster = _scripted(stall, TimeoutError("timed out"), "never asked for")

    with pytest.raises(LaneUnavailable) as raised:
        call_lane("anything", post=poster)
    assert len(posts) == 2
    assert "2 tries" in str(raised.value)
    assert "timed out" in str(raised.value)


@pytest.mark.parametrize("failure", [
    lambda: _refusal(402),
    lambda: _refusal(403),
    lambda: _refusal(500),
    lambda: ConnectionRefusedError("Connection refused"),
    lambda: urllib.error.URLError(ConnectionRefusedError("Connection refused")),
    lambda: ValueError("not json"),
], ids=["402", "403", "500", "refused", "refused-url", "not-json"])
def test_anything_but_a_timeout_stops_at_the_first_post(failure):
    """The cap is a hard stop (ADR-0009); a refusal or a bad body is not a slow model."""
    posts, poster = _scripted(failure(), "never asked for")

    with pytest.raises(LaneUnavailable):
        call_lane("anything", post=poster)
    assert len(posts) == 1


def test_a_timeout_then_a_refusal_stops_at_the_refusal(monkeypatch):
    """A re-asked stall that comes back a 402 is not asked a third time. `TRIES` is 1 since ticket
    198, so the second try this is about only exists with the number put back to 2."""
    monkeypatch.setattr(nemo.lane, "TRIES", 2)
    posts, poster = _scripted(TimeoutError("timed out"), _refusal(402), "never asked for")

    with pytest.raises(LaneUnavailable):
        call_lane("anything", post=poster)
    assert len(posts) == 2


# ── ticket 217: a fast refusal says in the journal which service refused, and with what ──

#: The guidance connector, spelled here rather than imported: nothing in this file imports
#: `nemo.ask`, and what the lane needs to know about the connector is only that its url is not
#: `lane_url()`. `nemo.ask.GUIDANCE_URL` is the same string.
_CONNECTOR_URL = "https://mcp.ai4bcm.org/mcp"


def _warnings(caplog) -> list:
    """Every line this module logged, read whole: a substring check lets the wording rot."""
    return [record.getMessage() for record in caplog.records if record.name == "nemo.lane"]


def test_a_refusal_the_lane_answered_names_the_lane_its_status_and_what_it_said(caplog):
    """207's qa got three "service unavailable" answers after 1.3 s and nobody could say what
    refused. A status and the first words of the body are where litellm says why, so they are in
    the line itself — the whole line, because that is what a human reads in the journal."""
    lane = _Lane(urllib.error.HTTPError(
        lane_url(), 503, "Service Unavailable", {}, io.BytesIO(b"No deployments available")))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": "mtpd"}, urlopen=lane)
    assert _warnings(caplog) == [
        "the model lane at 127.0.0.1:4000 refused: "
        "503 Service Unavailable: No deployments available"]


def test_a_connector_that_refuses_the_connection_is_named_with_the_failure_s_class(caplog):
    """The other host on the lane: `ask` maps both to the one `UNAVAILABLE` sentence, so the
    journal is the only place the two are told apart. A refused connection carries no status, so
    what it is called and what it said is all there is."""
    refused = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
    lane = _Lane(refused)

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        get(_CONNECTOR_URL, urlopen=lane)
    assert _warnings(caplog) == [
        "the guidance connector at mcp.ai4bcm.org refused: "
        "URLError: <urlopen error [Errno 111] Connection refused>"]


def test_a_long_error_page_is_cut_to_its_first_two_hundred_characters(caplog):
    """A proxy answers with a whole HTML page. The journal takes the first 200 characters of it,
    which is where the reason is, and never the page."""
    body = "x" * 1000
    lane = _Lane(urllib.error.HTTPError(
        lane_url(), 502, "Bad Gateway", {}, io.BytesIO(body.encode())))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": "mtpd"}, urlopen=lane)
    assert _warnings(caplog) == [
        f"the model lane at 127.0.0.1:4000 refused: 502 Bad Gateway: {'x' * 200}"]


def test_a_long_message_from_anything_else_is_cut_the_same_way(caplog):
    """The same 200 characters when there is no status to read: the class and what it said."""
    lane = _Lane(ValueError("y" * 1000))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": "mtpd"}, urlopen=lane)
    assert _warnings(caplog) == [
        f"the model lane at 127.0.0.1:4000 refused: ValueError: {'y' * 200}"]


def test_no_log_line_carries_the_question_that_was_asked(caplog):
    """"No Authorization header, ever" is the request's rule; the journal's is the same one. A
    manager's question is in the payload, and a public journal is not where it goes."""
    marker = "NEMO-217-MARKER-the-managers-own-words"
    lane = _Lane(urllib.error.HTTPError(
        lane_url(), 400, "Bad Request", {}, io.BytesIO(b"bad request")))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": marker}, urlopen=lane)
    assert marker not in "".join(str(record.__dict__) for record in caplog.records)


def test_a_stall_still_logs_only_its_own_stall_line(caplog):
    """The stall path is untouched: it says the same words it said before ticket 217, and the
    refusal line is not added to it."""
    lane = _Lane(TimeoutError("timed out"))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": "mtpd"}, urlopen=lane)
    assert _warnings(caplog) == [
        f"{lane_url()} stalled on try 1 of {nemo.lane.TRIES}: timed out"]


def test_a_lane_that_answers_says_nothing_in_the_journal(caplog):
    """The journal is for what went wrong. A working lane is silent, so a line in it means one."""
    with caplog.at_level("WARNING", logger="nemo.lane"):
        assert post(lane_url(), {"q": "mtpd"}, urlopen=_answering(b'{"ok": true}', [])) == {
            "ok": True}
    assert _warnings(caplog) == []


def test_a_body_carrying_a_percent_sign_is_logged_exactly_as_it_came(caplog):
    """litellm's reasons carry percent signs ("100% of the cap"), and a logged line is only a
    format string until something is substituted into it. `_refusal` builds the whole line, so
    nothing is left to substitute and a body's own `%s` is not a hole in the journal."""
    lane = _Lane(urllib.error.HTTPError(
        lane_url(), 429, "Too Many Requests", {}, io.BytesIO(b"budget 100% spent: %s %d %%")))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": "mtpd"}, urlopen=lane)
    assert _warnings(caplog) == [
        "the model lane at 127.0.0.1:4000 refused: "
        "429 Too Many Requests: budget 100% spent: %s %d %%"]


def test_a_body_that_is_not_utf_8_is_still_logged_with_the_bad_bytes_replaced(caplog):
    """An error page from a proxy is bytes of unknown encoding, and the reason in it is worth
    reading anyway: every byte that is not utf-8 becomes the replacement character rather than
    costing the line. The refusal is still the one `LaneUnavailable`, not a decoding error."""
    lane = _Lane(urllib.error.HTTPError(
        lane_url(), 500, "Internal Server Error", {}, io.BytesIO(b"\xff\xfe no upstream")))

    with caplog.at_level("WARNING", logger="nemo.lane"), pytest.raises(LaneUnavailable):
        post(lane_url(), {"q": "mtpd"}, urlopen=lane)
    assert _warnings(caplog) == [
        "the model lane at 127.0.0.1:4000 refused: "
        "500 Internal Server Error: �� no upstream"]


#: Ticket 209. Four 200s that carry no answer: the provider's error object, a reply with no
#: choice in it, and a message whose content is missing or null. Each is the one `LaneUnavailable`,
#: never a `KeyError`, an `IndexError`, a `TypeError` or a `None` reaching the manager.
_MALFORMED = [
    {"error": {"message": "Provider returned error", "code": 502}},
    {"choices": []},
    {"choices": [{"message": {"role": "assistant"}}]},
    {"choices": [{"message": {"role": "assistant", "content": None}}]},
]


@pytest.mark.parametrize("reply", _MALFORMED)
def test_a_reply_with_no_answer_in_it_is_the_one_refusal_naming_its_shape(reply):
    with pytest.raises(LaneUnavailable) as raised:
        call_lane("anything", post=lambda url, payload: reply)
    assert str(raised.value) == f"{lane_url()} answered with no answer in it: {json.dumps(reply)}"


def test_the_shape_of_a_long_reply_is_cut_to_its_first_two_hundred_characters():
    reply = {"error": {"message": "x" * 300}}
    with pytest.raises(LaneUnavailable) as raised:
        call_lane("anything", post=lambda url, payload: reply)
    assert str(raised.value).endswith(f": {json.dumps(reply)[:200]}")
