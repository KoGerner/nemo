"""PROTOTYPE, throwaway (2026-09-17). One chat call over three model lanes, for the bake-off.

- glm, glmplain, deepseek: litellm (`ai4bcm/...`), native tool calls. The only product candidates.
- gpt6: `codex exec -m gpt-6-astra` on the subscription, ONLY as a reference to compare against
  (owner, 2026-09-17). Never through litellm (box rule). Codex has no function-calling here, so the
  tools are described in the prompt and it answers in a small JSON protocol, parsed back into the
  same shape litellm returns.
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from nemo import turn_file

LITELLM = "http://127.0.0.1:4000/v1/chat/completions"
MODELS = {
    # ADR-0036, ticket 198: the phone's default. The same model, effort and key as before, on the
    # route sorted by throughput (p50 11.3 s against the plain route's 22.85 s), so a guidance
    # answer fits inside `nemo.lane.TIMEOUT_SECONDS`. The KEY does not change: the phone names a
    # room `<user>-<model key>`, so re-keying the default would open every existing room empty
    # (lanediag2; 17_nemo_check's ruling). The plain route keeps a key of its own instead, for
    # ticket 192's recorded batches and 199's round to name it by.
    "glm": "ai4bcm/glm-5.3-flash-fastest",
    "glmplain": "ai4bcm/glm-5.3-flash",
    "deepseek": "ai4bcm/deepseek-v4.1-flash",
    "gpt6": "gpt-6-astra (codex subscription, reference only)",
}
LABELS = {"glm": "GLM-5.3 Flash (fastest route)", "glmplain": "GLM-5.3 Flash (plain route)",
          "deepseek": "DeepSeek V4.1 Flash", "gpt6": "GPT-6 (reference)"}


# ── ticket 82: the lane ledger ────────────────────────────────────────────────────────────────
#: Every call on the lane, in EVERY thread, with the attempts inside it. Ticket 69's `unaccounted`
#: number came from a turn whose model clock counts only the lane calls the turn's own thread makes
#: inside `Session._model_calls`; the 489.83 s it could not name was a drafting call on the same
#: lane in a BACKGROUND thread, which the turn was blocked waiting for. A per-turn clock can never
#: see that, because the seconds were not spent in the turn's thread. This ledger is process-wide
#: and thread-tagged, so a turn can subtract what the lane was doing anywhere while it waited.
SPANS: list[dict[str, Any]] = []
_SPANS_LOCK = threading.Lock()
_CURRENT = threading.local()
#: Bounded: a walk is ~50 turns and a few hundred lane calls; this keeps a long-lived app flat.
SPANS_KEPT = 4000


def note_purpose(name: str | None) -> str | None:
    """What the next lane calls on THIS thread are for ("turn", "draft", "interview"). Returns
    the purpose it replaces, so a call made inside a turn can hand the turn its own back (t33)."""
    before = getattr(_CURRENT, "purpose", None)
    _CURRENT.purpose = name
    return before


def _record(span: dict[str, Any]) -> None:
    with _SPANS_LOCK:
        SPANS.append(span)
        if len(SPANS) > SPANS_KEPT:
            del SPANS[: len(SPANS) - SPANS_KEPT]


def spans_overlapping(start: float, end: float) -> list[dict[str, Any]]:
    """Every lane span that overlaps the window, each with the seconds it spent INSIDE it.

    Clipped to the window, so a draft that began before the turn contributes only the part the
    manager actually waited through — the number is what he waited for, not what the call cost.
    """
    with _SPANS_LOCK:
        spans = list(SPANS)
    out = []
    for s in spans:
        lo, hi = max(s["start"], start), min(s.get("end") or end, end)
        if hi > lo:
            out.append({**s, "in_window_s": round(hi - lo, 2)})
    return out


#: t109: the calls made for each room, waiting for the turn that will write them
#: (`core.record_turn`).
CALLS = turn_file.Calls()


CODEX = str(Path.home() / ".npm-global/bin/codex")
SCRATCH = Path(__file__).parent / "scratch"


# ── ticket 33: a stalled lane is re-asked; a capped one is still a hard stop ─────────────────────
#: Tries per lane call: his, a retry count being a time cap. Ticket 740, his "Yes, retry once"
#: (2 Nov 2026), replaces 229's "One try, like nemo". The second try of a room on `glm` goes over
#: the plain route, his "Yes, plain route"; a draft's and every other key's stay on their own. The
#: number is his one-line call. The cap is never re-asked, whatever this says.
TRIES = 2
#: The longest one try may wait, on every call but the draft: the 30 s turn ceiling (ticket 69).
#: The default, so an unlabelled call or a purpose nobody thought of is capped, never given minutes.
TRY_TIMEOUT_S = 30
#: The draft's own try (owner, 2026-09-21, "Accept it": the confirm-time draft may take minutes).
#: 28 rebuilds: median 74 s, worst 662 s, so 600 s would have cut the worst one off; 900 s clears it
#: by a third and matches the codex reference's own cap. A stalled draft is not re-asked: a second
#: 900 s would put one confirm tap past ticket 19's 20-minute walk, and stage 3 drafts again.
DRAFT_TIMEOUT_S = 900
#: ADR-0009: the key cap is a hard stop. The lane says so with this status, answering at once.
CAP_STATUS = 402

#: t33 fix 1: true for a spent cap and for OpenRouter's in-flight cap alike (every 402 on disk is
#: the
#: in-flight kind, which lifts once calls settle), and it promises no wait: a real cap needs credit.
CAPPED = "nemo has reached its AI budget, so it can't answer right now."
DOWN = "The AI did not answer this time, so I can't reply now. Please send it again."
#: t615: an empty answer goes to the next cheapest provider until this many seconds have passed
#: since the call began: his question limit ("45 seconds", 2026-10-29T11:38:05Z), ADR-0019's cap.
#: The draft keeps its own longer one, `DRAFT_TIMEOUT_S`.
EMPTY_LIMIT_S = 45
#: t646: the caller's test of a reply that carries no answer though it holds a call (`led_turn`'s
#: empty template call). Such a reply goes to the next provider once, inside his limit, as an empty
#: one does; the last such reply comes back as it came, for the caller's own one retry, where the
#: lane would give up. Unset (every other caller), a reply with a call stands as it always did.
NO_ANSWER: contextvars.ContextVar[Callable[[dict[str, Any]], bool] | None] = \
    contextvars.ContextVar("no_answer", default=None)
NO_ANSWER_OUTCOME = "200-no-answer"

class LaneDown(RuntimeError):
    """The lane gave up. `said` is the one plain sentence for his screen; the message keeps the
    lane's own words for the log, where the check sessions read the 402's body."""

    def __init__(self, detail: str, said: str):
        super().__init__(detail)
        self.said = said


def _skipping(body: dict[str, Any], skipped: list[str]) -> dict[str, Any]:
    """t615: the request asked again, with the providers that answered empty named in
    `metadata.skip_provider`; the gateway's hook adds them to the alias's own `provider.ignore`.
    A request's own `extra_body` would replace the alias's block, ZDR pin and all (216,
    ADR-0036), and a `provider` field would be a skip outside the hook, so neither is built."""
    if "extra_body" in body or "provider" in body:
        raise ValueError("a lane request carries its own routing; the skip goes in metadata only")
    return {**body, "metadata": {"skip_provider": ", ".join(skipped)}}


def _litellm(model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
             max_tokens: int, json_mode: bool) -> dict[str, Any]:
    first: dict[str, Any] = {"model": MODELS[model], "max_tokens": max_tokens,
                             "messages": messages}
    if tools:
        first["tools"] = tools
    if json_mode:
        first["response_format"] = {"type": "json_object"}
    body = first
    skipped: list[str] = []  # t615: per call, so the next turn starts from the cheapest again
    began = time.time()
    last = ""
    # t82: `attempts` distinguishes a retry or a backoff from a single slow call. Without it a
    # timeout followed by two more tries and a 200 is ONE span and reads like one very slow answer.
    # t33: so every stall is in it, by name (`ReadTimeout`, ...), where a human finds it afterwards.
    attempts = getattr(_CURRENT, "span", None)
    attempts = attempts["attempts"] if attempts is not None else []
    draft = getattr(_CURRENT, "purpose", None) == "draft"
    limit = DRAFT_TIMEOUT_S if draft else EMPTY_LIMIT_S
    tries = 0
    held = NO_ANSWER.get()
    kept: dict[str, Any] | None = None  # t646: a reply that carried no answer, re-asked once
    while tries < TRIES:
        tries += 1
        # t740: his plain route, the model alone. The gateway's hook ignores a skip there, so what
        # comes back empty from it is never re-asked: at `TRIES` 2, one post on it per call at most.
        plain = tries > 1 and model == "glm" and not draft
        if plain:
            body = {**first, "model": MODELS["glmplain"]}
        a0 = time.time()
        timeout: float = DRAFT_TIMEOUT_S if draft else TRY_TIMEOUT_S
        if skipped:  # t615: a re-ask never waits past his limit, and is never sent with none left
            timeout = min(timeout, limit - (a0 - began))
            if timeout <= 0:
                break
        try:
            r = httpx.post(LITELLM, json=body, timeout=timeout)
        except httpx.TimeoutException as e:  # a stall: nothing came back in time
            last = f"no answer in time ({type(e).__name__})"
            attempts.append({"seconds": round(time.time() - a0, 2), "outcome": type(e).__name__,
                             "slept_s": 0})  # the wait it just served is the backoff
            if draft:
                break
            continue
        except httpx.HTTPError as e:
            last = str(e)
            attempts.append({"seconds": round(time.time() - a0, 2), "outcome": type(e).__name__,
                             "slept_s": 2})
            time.sleep(2)
            continue
        if r.status_code == CAP_STATUS:  # the lane answered, and refused: never asked again
            attempts.append({"seconds": round(time.time() - a0, 2), "outcome": r.status_code,
                             "slept_s": 0})
            raise LaneDown(f"lane {model} capped: {r.status_code} {r.text[:300]}", CAPPED)
        if r.status_code == 200:
            data = r.json()
            # t615 Amend 1: the provider that answered, as OpenRouter names it, or that it did not
            provider = data.get("provider") or "absent"
            if "choices" not in data:  # OpenRouter answers 200 with an error body for some refusals
                last = f"200 but no choices: {json.dumps(data)[:400]}"
                attempts.append({"seconds": round(time.time() - a0, 2),
                                 "outcome": "200-no-choices", "slept_s": 2, "provider": provider})
                time.sleep(2)
                continue
            # t209, t615: an empty `choices`, or a message with neither words nor a tool call, is
            # no answer. It is asked again of the next cheapest provider (his words), never of
            # one already asked, and only inside his limit; it is not a try, so TRIES is untouched
            msg = (data["choices"] or [{}])[0].get("message") or {}
            if msg.get("content") is None and not msg.get("tool_calls"):
                attempts.append({"seconds": round(time.time() - a0, 2),
                                 "outcome": "200-no-choices", "slept_s": 0, "provider": provider})
                if (plain or provider == "absent" or provider in skipped
                        or time.time() - began >= limit):
                    if kept is not None:
                        return kept
                    tried = ", ".join([*skipped, provider])
                    raise LaneDown(f"lane {model} failed: 200 but no answer from {tried}: "
                                   f"{json.dumps(data)[:400]}", DOWN)
                skipped.append(provider)
                body = _skipping(first, skipped)
                tries -= 1
                continue
            msg["_usage"] = data.get("usage") or {}
            msg["_model"] = data.get("model")  # t109: the model that answered, as the lane says
            if held is not None and kept is None and not plain and provider != "absent" \
                    and provider not in skipped and time.time() - began < limit and held(msg):
                attempts.append({"seconds": round(time.time() - a0, 2),
                                 "outcome": NO_ANSWER_OUTCOME, "slept_s": 0, "provider": provider})
                kept = msg
                skipped.append(provider)
                body = _skipping(first, skipped)
                tries -= 1
                continue
            attempts.append({"seconds": round(time.time() - a0, 2), "outcome": 200, "slept_s": 0,
                             "provider": provider})
            return msg
        last = f"{r.status_code} {r.text[:300]}"
        attempts.append({"seconds": round(time.time() - a0, 2), "outcome": r.status_code,
                         "slept_s": 2})
        time.sleep(2)
    if kept is not None:
        return kept
    empty = f" (no answer from {', '.join(skipped)} before)" if skipped else ""
    raise LaneDown(f"lane {model} failed: {last}{empty}", DOWN)


_PROTOCOL = """You are running inside a tool loop. You cannot run shell commands or read files \
yourself; \
use ONLY the tools listed below by answering in the JSON protocol.

TOOLS (JSON schema):
{tools}

Answer with exactly one JSON object and nothing else:
- to call tools: {{"tool_calls": [{{"name": "<tool>", "arguments": {{...}}}}]}}
- to reply to the manager: {{"content": "<your chat reply, including the OPTIONS: line>"}}

CONVERSATION SO FAR (oldest first):
{history}
"""


def _render(messages: list[dict[str, Any]]) -> tuple[str, str]:
    system = ""
    lines = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        elif m["role"] == "tool":
            lines.append(f"[tool result {m.get('tool_call_id')}]\n{m['content']}")
        elif m.get("tool_calls"):
            lines.append("[assistant called tools] " + json.dumps(
                [{"id": c["id"], "name": c["function"]["name"],
                  "arguments": c["function"]["arguments"]} for c in m["tool_calls"]]))
        else:
            lines.append(f"[{m['role']}]\n{m.get('content') or ''}")
    return system, "\n\n".join(lines)


def _codex(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None,
           json_mode: bool) -> dict[str, Any]:
    SCRATCH.mkdir(exist_ok=True)
    system, history = _render(messages)
    if tools:
        prompt = system + "\n\n" + _PROTOCOL.format(
            tools=json.dumps([t["function"] for t in tools], indent=1), history=history)
    else:
        prompt = (
            system
            + "\n\n"
            + history
            + ("\n\nAnswer with one JSON object only." if json_mode else "")
        )
    with tempfile.TemporaryDirectory(dir=SCRATCH) as tmp:
        out = Path(tmp) / "last.txt"
        proc = subprocess.run(
            [CODEX, "exec", "-m", "gpt-6-astra", "--ephemeral", "--skip-git-repo-check",
             "-s", "read-only", "-C", tmp, "-o", str(out), "-"],
            input=prompt, capture_output=True, text=True, timeout=900,
            env={**os.environ, "PATH": f"{Path(CODEX).parent}:{os.environ.get('PATH', '')}"})
        text = out.read_text() if out.exists() else ""
        if proc.returncode != 0 and not text:
            raise RuntimeError(f"codex failed rc={proc.returncode}: {proc.stderr[-400:]}")
        # codex exits 0 with no text when the workspace is out of credits (2026-09-21): a lane down
        errors = [ln for ln in (proc.stdout + proc.stderr).splitlines() if ln.startswith("ERROR:")]
        if not text.strip() and errors:
            raise LaneDown(f"lane gpt6 failed: {errors[-1]}", DOWN)
    tokens = re.findall(r"tokens used\s*\n([\d,]+)", proc.stdout + proc.stderr)
    usage = {"total_tokens": int(tokens[-1].replace(",", ""))} if tokens else {}
    if not tools:
        return {"role": "assistant", "content": text, "_usage": usage}
    try:
        obj = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return {"role": "assistant", "content": text, "_usage": usage}
    if obj.get("tool_calls"):
        return {"role": "assistant", "content": None, "_usage": usage, "tool_calls": [
            {"id": "call_" + uuid.uuid4().hex[:8], "type": "function",
             "function": {"name": c["name"], "arguments": json.dumps(c.get("arguments") or {})}}
            for c in obj["tool_calls"]]}
    return {"role": "assistant", "content": obj.get("content") or text, "_usage": usage}


def chat(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 1500,
    json_mode: bool = False,
    room: Path | None = None,
) -> dict[str, Any]:
    """One model call. Returns an OpenAI-shaped assistant message plus `_usage` and `_seconds`.

    t82: the call is entered in `SPANS` when it STARTS, not when it returns, so a turn blocked on a
    lane call another thread is still making can see it and name the seconds. A span that never
    closes (the process died inside the call) keeps `end` None and is read as still running.

    t109: a call made for a `room` is kept for that room's turn file (`CALLS`), answered or failed,
    with the messages and tools as sent (copied now: the history grows after) and the raw reply.
    The room is passed by the caller, never read from anywhere: fifty rooms share this function.
    """
    t0 = time.time()
    span: dict[str, Any] = {"start": t0, "end": None, "model": model,
                            "thread": threading.get_ident(),
                            "thread_name": threading.current_thread().name,
                            "purpose": getattr(_CURRENT, "purpose", None), "attempts": []}
    sent = json.loads(json.dumps([messages, tools], default=str)) if room is not None else None
    _record(span)
    _CURRENT.span = span
    msg: dict[str, Any] | None = None
    failed: str | None = None
    try:
        msg = _codex(messages, tools, json_mode) if model == "gpt6" else \
            _litellm(model, messages, tools, max_tokens, json_mode)
    except Exception as e:
        failed = f"{type(e).__name__}: {e}"
        raise
    finally:
        span["end"] = time.time()
        _CURRENT.span = None
        if sent is not None:
            # why: `sent` is set only when `room` is
            CALLS.add(room, turn_file.call(  # type: ignore[arg-type]
                lane=model, asked=MODELS.get(model, model), answered=(msg or {}).get("_model"),
                messages=sent[0], tools=sent[1],
                reply=None if msg is None else json.loads(json.dumps(
                    {k: v for k, v in msg.items() if not k.startswith("_")}, default=str)),
                usage=(msg or {}).get("_usage") or {}, seconds=round(span["end"] - t0, 2), start=t0,
                purpose=span["purpose"], thread=span["thread_name"],
                attempts=[a["outcome"] for a in span["attempts"]], error=failed)
                | {"providers": [a.get("provider") for a in span["attempts"]]})
    msg["_seconds"] = round(time.time() - t0, 1)
    return msg

