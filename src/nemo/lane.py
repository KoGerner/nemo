"""The model lane, and the HTTP both of the skin's model jobs speak it over.

One litellm lane serves both jobs (ADR-0008): `nemo.ask` answers a question from the frozen
guidance corpus, and `nemo.conduct` holds the interview in the room. Neither is the other's
business — the corpus's release pins, its refusals and its citations mean nothing to an interview,
and the interviewer's card means nothing to a question — so the thing they share sits below them
both rather than one of them importing the other. `nemo.conduct` read `call_lane` out of
`nemo.ask` until ticket 17, which made the live interview depend on the whole guidance corpus to
place one HTTP call.

**Every failure is one `LaneUnavailable`.** A 402 when the shared key hits its cap, a refused
connection, a body that is not JSON: nothing here parses an error, because the cap is a hard stop
rather than a degradation (ADR-0009) and both callers act on all three the same way.

**Except that a stall is asked again first** (ticket 111, the skin's lane's three rules; ticket
191). A stall is one upstream provider not answering inside `TIMEOUT_SECONDS`, and the next try
routes elsewhere, so it is re-asked, up to `TRIES` tries in all. There is one retry loop, in
`_read`, under both `post` and `get`; `call_lane` has none of its own, so nothing nests
(16_nemo_check, ruling B on 111 x 191). It is told from the cap by what the lane did, never by
a clock: a stall is `urlopen` running out of time (`TimeoutError`, bare on a read, inside a
`URLError` on a connect); the cap is the lane *answering* with a 402, an `HTTPError`, and like
every other failure it is asked once. No try waits longer than `TIMEOUT_SECONDS`, so the worst
stall costs `TRIES` x `TIMEOUT_SECONDS`. Each stall is a warning on this module's logger: nemo
adds no handler, so under the skin's unit it is stderr and the journal, where a human finds it
after the demo. What
each says to the manager is the caller's — `nemo.ask.UNAVAILABLE` and `nemo.conduct.STOPPED` are two
sentences about two jobs, and that difference is the point of them being said upstairs.

**No Authorization header, ever.** litellm sits on loopback and takes no key, and the guidance
connector is open deliberately (ADR-0005), so there is no token here to leak into a public
visitor's request. Changing the lane itself means editing `litellm/config.yaml` and running
`sudo /opt/brain/security/install.sh`: a kgadmin round, not something the build can do.
"""

from __future__ import annotations

import functools
import json
import logging
import operator
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

#: The estate's litellm gateway. The lane pins zero data retention and `reasoning: exclude: true`.
LANE_URL = "http://127.0.0.1:4000/v1/chat/completions"

#: Set this to a dead port to rehearse an unavailable lane without exhausting the shared key,
#: which is what `docs/research/ask-lane-live-run.md` §3 tells an operator to do. Unset in
#: production: the unit names no such variable.
LANE_URL_ENV = "NEMO_LANE_URL"

#: ADR-0036 (supersedes ADR-0026, which superseded ADR-0008 here). The fastest route to the same
#: model: `openrouter/z-ai/glm-5.3-flash` behind the alias, same effort and key, sorted by
#: throughput. The plain `ai4bcm/glm-5.3-flash` answered p50 22.85 s, p95 80.1 s on ticket 192's
#: 24 practice questions and so lost answers to `TIMEOUT_SECONDS`; this route answered them in
#: p50 11.3 s, p95 27.4 s. Interim: ticket 192's blind round picks the long-term model.
MODEL = "ai4bcm/glm-5.3-flash-fastest"

#: Long enough for a four-excerpt answer, short enough that an unavailable lane is a stop. Per try.
#: Ticket 33 set 30 s and ticket 191 kept it; **ticket 198 raised it to 80 s** on his ruling of
#: 2026-09-28 15:18:03Z ("80 s, one try + shorten"). `nemo-builds/lanediag-report.md` replayed one
#: real guidance request seven times on this route: 20, 26, 36, 51, 59, 87 and 99 s, spending
#: 800-2,650 reasoning tokens each — the answer is simply longer than a 30 s clock, and 80 s covers
#: 5 of the 7 while staying strictly inside the UI's 90 s page wait. Making the answer shorter,
#: which is the real cure, is ticket 202.
TIMEOUT_SECONDS = 80

_log = logging.getLogger(__name__)

#: Ticket 191. How many times `_read` asks when the model does not answer in time. **Ticket 198
#: set it to 1** on his ruling of 2026-09-28 15:18:03Z: a re-ask is aimed at a *provider* stall
#: that rerouting fixes, and `nemo-builds/lanediag-report.md` showed this is not one — the same
#: model spends the same reasoning tokens on try 2, so the second try only turned an 80 s stall
#: into a 160 s one at double the spend. **The retry loop in `_read` stays**, driven by this
#: number, so raising it again is his one-line call rather than a rebuild. One, where the skin's
#: is 2 since 740 (`skin/PROTOTYPE_lanes.py`): 1 x 80 s, an 80 s worst case, strictly inside the
#: UI's 90 s page wait. Only a timeout is asked again: a 402, any other HTTP status, a refused
#: connection or a body that is not JSON is a stop at the first try.
TRIES = 1

#: Ticket 187. The most a call may generate, reasoning included. Sent on every request, because
#: without it OpenRouter reserves the model's whole output ceiling (131072) against the capped key
#: and answers 402 once the key cannot afford that (`nemo-builds/live-scenarios-report.md`).
#: Measured: the longest recorded call on this model outside drafting is 742 tokens (42 reasoning),
#: the longest recorded ask answer 324 (33 reasoning), and the most reasoning any recorded call on
#: this model spent is 3863 (a draft). 4096 holds all three: 5x the longest answer.
MAX_TOKENS = 4096

LaneCall = Callable[[str], str]
Poster = Callable[[str, dict[str, Any]], dict[str, Any]]
Getter = Callable[[str], dict[str, Any]]


class LaneUnavailable(Exception):
    """The lane or the connector did not answer. The cap arrives here, and so does a dead port."""


def post(url: str, payload: dict[str, Any], *, urlopen: Any = urllib.request.urlopen) -> Any:
    """POST `payload` as JSON and return the parsed reply. No Authorization header, ever.

    The connector is open and litellm on loopback takes no key, so there is no token to leak into
    a public visitor's request. Every failure — a 402 from the cap, a refused connection, a body
    that is not JSON — becomes one `LaneUnavailable`, because nothing here parses an error.
    """
    return _read(
        urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        ),
        urlopen,
    )


def get(url: str, *, urlopen: Any = urllib.request.urlopen) -> Any:
    """GET `url` and return the parsed reply. The health page is public: no token, no body."""
    return _read(urllib.request.Request(url, headers={"Accept": "application/json"}), urlopen)


def _read(request: urllib.request.Request, urlopen: Any) -> Any:
    """Send one built request and parse what comes back, or say plainly that it did not.

    A stall is asked again, up to `TRIES` times; anything else fails on its first try. A refusal
    is said in the journal in `_refusal`'s words, which is all that line is; this one sends and
    parses.
    """
    for attempt in range(1, TRIES + 1):
        try:
            with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read())
        except (OSError, ValueError) as exc:
            if not _stalled(exc):
                _log.warning(_refusal(request, exc))
                raise LaneUnavailable(f"{request.full_url} did not answer: {exc}") from exc
            _log.warning("%s stalled on try %d of %d: %s", request.full_url, attempt, TRIES, exc)
            if attempt == TRIES:
                raise LaneUnavailable(
                    f"{request.full_url} did not answer in {TRIES} tries: {exc}"
                ) from exc
    raise AssertionError("unreachable: the loop returns or raises")  # pragma: no cover


def _refusal(request: urllib.request.Request, exc: OSError | ValueError) -> str:
    """The one line a refusal leaves in the journal, which the caller's `_read` only logs.

    Every caller is told the same `LaneUnavailable` whatever refused (ADR-0009), so the journal is
    the only place the two hosts and their reasons are told apart: ticket 217, after three 1.3 s
    refusals in 207's qa that nobody could name. The line says which service, its host, and what
    it said — a status and the first 200 characters of the body where the lane answered, the class
    and message where it did not. Never the request body, a header or a key.
    """
    if isinstance(exc, urllib.error.HTTPError):
        said = f"{exc.code} {exc.reason}: {exc.read().decode(errors='replace')[:200]}"
    else:
        said = f"{type(exc).__name__}: {str(exc)[:200]}"
    service = "the model lane" if request.full_url == lane_url() else "the guidance connector"
    return f"{service} at {urllib.parse.urlsplit(request.full_url).netloc} refused: {said}"


def _stalled(exc: BaseException) -> bool:
    """Whether the timeout ran out, the only evidence of a stall. An `HTTPError` (the cap's 402)
    has a `reason` too, but it is a status phrase and never a `TimeoutError`."""
    return isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)


def lane_url() -> str:
    """Where the lane is, which an operator can move to a dead port to rehearse the stop."""
    return os.environ.get(LANE_URL_ENV) or LANE_URL


def call_lane(prompt: str, *, post: Poster = post) -> str:
    """Ask the model lane and return the message content — only the content.

    The lane pins `reasoning: {effort: low, exclude: true}`, so the thinking is not in the reply
    at all; reading nothing but `content` is what keeps it off the screen if that ever changes.
    A timeout is asked again under `post`, up to `TRIES` in all; any other failure stops at once.
    """
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    text: str = field(post(lane_url(), payload), lane_url(), "choices", 0, "message", "content")
    return text


def field(reply: Any, url: str, *path: str | int) -> Any:
    """`reply[path[0]][path[1]]...`, or the one `LaneUnavailable` naming the reply's shape.

    Ticket 209: a 200 can carry an error object, no choice or a message with no content, and
    indexing it raw put a `KeyError` on the manager's screen instead of the unavailable sentence.
    A null at the end of the path is no answer either: `"content": null` is the usual form.
    """
    try:
        found = functools.reduce(operator.getitem, path, reply)
    except (KeyError, IndexError, TypeError):
        found = None
    if found is None:
        shape = json.dumps(reply)[:200]
        raise LaneUnavailable(f"{url} answered with no answer in it: {shape}")
    return found
