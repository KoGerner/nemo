"""Ticket 109: the turn file. One writer, one file per room, every model call on its turn.

What a reader of the file sees is what is asserted: the line as it lands, read back. The callers
(a scripted walk, a chat batch, the live phone app) are the skin's, and each is proved to write
through this writer in `skin/tests/test_t109_turn_file.py`.
"""

import json
import threading

import pytest

from nemo import turn_file
from nemo.turn_file import ANSWERED, CAP, FAILED, Calls, Past, call, past, path, read, write

WORDING = "abc1234"


def _call(n: int, error: str | None = None) -> dict[str, object]:
    return call(lane="glm", asked="ai4bcm/glm-5.3-flash", answered="z-ai/glm-5.3-flash",
                messages=[{"role": "user", "content": f"q{n}"}], tools=[{"name": "t"}],
                reply={"role": "assistant", "content": f"a{n}"},
                usage={"prompt_tokens": 7, "total_tokens": 9, "cost": 0.0002},
                seconds=1.5, start=1_800_000_000.25, purpose="turn", thread="MainThread",
                attempts=[200], error=error)


# ── where it lives ────────────────────────────────────────────────────────────────────────────
def test_the_turn_file_lives_under_a_dot_path_in_the_room(tmp_path):
    """Under a dot-path, so the chat's room listing never shows it; never `output/`, where the
    signed documents live (the verdict's amendment)."""
    assert path(tmp_path / "room-1") == tmp_path / "room-1" / ".turns" / "turns.jsonl"
    assert turn_file.DIR.startswith(".")


# ── one call entry ────────────────────────────────────────────────────────────────────────────
def test_a_call_entry_holds_what_was_sent_what_came_back_and_what_it_cost():
    assert _call(1) == {
        "purpose": "turn", "thread": "MainThread", "start": 1_800_000_000.25, "seconds": 1.5,
        "lane": "glm", "model_asked": "ai4bcm/glm-5.3-flash",
        "model_answered": "z-ai/glm-5.3-flash",
        "messages": [{"role": "user", "content": "q1"}], "tools": [{"name": "t"}],
        "reply": {"role": "assistant", "content": "a1"},
        "usage": {"prompt_tokens": 7, "total_tokens": 9, "cost": 0.0002},
        "tokens": 9, "cost": 0.0002, "outcome": ANSWERED, "error": None, "attempts": [200]}


def test_a_transport_failure_is_a_failed_call_and_never_a_reply():
    """ADR-0020: a broken lane is never mistaken for a good refusal, nor the other way round."""
    failed = _call(1, error="LaneDown: lane glm failed: 502")
    assert (failed["outcome"], failed["error"]) == (FAILED, "LaneDown: lane glm failed: 502")
    assert ANSWERED != FAILED


def test_a_call_with_no_usage_reported_says_so_rather_than_zero():
    entry = call(lane="gpt6", asked="gpt-6-astra", answered=None, messages=[], tools=None,
                 reply=None, usage={}, seconds=0.0, start=0.0, purpose=None, thread="t",
                 attempts=[], error=None)
    assert (entry["tokens"], entry["cost"], entry["usage"]) == (None, None, {})


# ── the writer ────────────────────────────────────────────────────────────────────────────────
def test_every_turn_carries_its_id_its_clock_its_room_its_wording_and_its_calls(tmp_path):
    room = tmp_path / "konstantin-chat-glm"
    written = write(room, {"said": "hi", "reply": "Hello."}, wording=WORDING,
                    calls=[_call(1), _call(2)], clock=lambda: 1_800_000_000.26,
                    new_id=lambda: "t-1")
    assert read(path(room)) == [written]
    assert written == {"at": 1_800_000_000.3, "said": "hi", "reply": "Hello.", "turn_id": "t-1",
                       "room": "konstantin-chat-glm", "wording": WORDING,
                       "calls": [_call(1), _call(2)]}


def test_a_turn_that_already_says_when_it_ended_keeps_its_own_clock(tmp_path):
    written = write(tmp_path / "r", {"at": 1_700_000_000.5}, wording=WORDING, calls=[],
                    clock=lambda: 1_800_000_000.0)
    assert written["at"] == 1_700_000_000.5


def test_the_writer_names_the_room_and_the_wording_whatever_the_record_said(tmp_path):
    written = write(tmp_path / "r", {"room": "elsewhere", "wording": "old", "turn_id": "x",
                                     "calls": ["stale"]}, wording=WORDING, calls=[])
    assert (written["room"], written["wording"], written["calls"]) == ("r", WORDING, [])
    assert written["turn_id"] != "x"


def test_the_turn_id_is_fresh_on_every_turn(tmp_path):
    first = write(tmp_path / "r", {}, wording=WORDING, calls=[])
    second = write(tmp_path / "r", {}, wording=WORDING, calls=[])
    assert first["turn_id"] != second["turn_id"]
    assert len(first["turn_id"]) == 32 and int(first["turn_id"], 16) >= 0


def test_the_clock_is_the_real_one_unless_the_caller_passes_another(tmp_path):
    import time
    before = time.time()
    at = write(tmp_path / "r", {}, wording=WORDING, calls=[])["at"]
    assert before - 0.1 <= at <= time.time() + 0.1


def test_turns_append_one_whole_line_each(tmp_path):
    room = tmp_path / "r"
    for n in range(3):
        write(room, {"n": n}, wording=WORDING, calls=[_call(n)])
    lines = path(room).read_bytes().decode().splitlines()
    assert [json.loads(ln)["n"] for ln in lines] == [0, 1, 2]


def test_the_file_is_utf_8_whatever_the_locale(tmp_path):
    room = tmp_path / "r"
    write(room, {"said": "Grüße, 30 Minuten"}, wording=WORDING, calls=[])
    assert "Grüße, 30 Minuten" in path(room).read_bytes().decode("utf-8")


def test_a_value_json_cannot_hold_is_written_as_its_text(tmp_path):
    written = write(tmp_path / "r", {"where": tmp_path}, wording=WORDING, calls=[])
    assert read(path(tmp_path / "r"))[0]["where"] == str(tmp_path)
    assert written["where"] == tmp_path


def test_an_index_file_gets_the_same_turn_without_its_calls(tmp_path):
    """A scripted walk's batch file is committed to git beside its summary, so it carries the turn
    and its id and leaves the calls (every message sent, whole) to the room's file."""
    room, index = tmp_path / "r", tmp_path / "out" / "deep" / "straight.turns.jsonl"
    written = write(room, {"said": "hi"}, wording=WORDING, calls=[_call(1)], index=index)
    [line] = read(index)
    assert line == {k: v for k, v in written.items() if k != "calls"}
    assert read(path(room))[0]["calls"] == [_call(1)]


def test_without_an_index_only_the_room_file_is_written(tmp_path):
    write(tmp_path / "r", {}, wording=WORDING, calls=[])
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()) \
        == ["r/.turns/turns.jsonl"]


# ── the reader ────────────────────────────────────────────────────────────────────────────────
def test_a_walk_that_died_mid_write_is_still_read(tmp_path):
    """ADR-0020: every reader skips a broken line rather than failing; the walks that died are the
    ones most worth reading."""
    f = tmp_path / "turns.jsonl"
    f.write_bytes(b'{"n": 0}\n{"n": 1, "reply": "cut of\n{"n": 2}\n{"n": 3, "rep')
    assert read(f) == [{"n": 0}, {"n": 2}]


# ── what is drawn again when he reopens the link (ticket 118) ─────────────────────────────────
def _said(room, n, **more):
    turn = {"how": "typed", "said": f"q{n}", "reply": f"a{n}", "cards": [f"c{n}"], **more}
    return write(room, turn, wording=WORDING, calls=[])


def test_his_turns_come_back_in_order_as_his_words_nemos_reply_and_the_cards_before_it(tmp_path):
    room = tmp_path / "r"
    for n in range(3):
        _said(room, n)
    assert [p[:4] for p in past(room)] == [Past(f"q{n}", f"a{n}", [f"c{n}"], "typed")[:4]
                                         for n in range(3)]
    first = past(room)[0]
    assert (first.said, first.reply, first.cards, first.how) == ("q0", "a0", ["c0"], "typed")


def test_each_turn_comes_back_with_its_stage_and_its_id(tmp_path):
    """Ticket 533 (511): the stage the answer was at, as the turn file has it (478's
    `answer_stage`), and the turn's id; a line written before 478 has no stage."""
    room = tmp_path / "r"
    staged = _said(room, 0, answer_stage=2)
    before = _said(room, 1)
    assert [(p.stage, p.turn_id) for p in past(room)] == [(2, staged["turn_id"]),
                                                         (None, before["turn_id"])]
    assert Past("q", "a", [], "typed")[4:] == (None, None)


def test_only_the_last_fifty_turns_come_back(tmp_path):
    room = tmp_path / "r"
    for n in range(CAP + 2):
        _said(room, n)
    assert CAP == 50
    assert [p.said for p in past(room)] == [f"q{n}" for n in range(2, CAP + 2)]
    assert [p.said for p in past(room, cap=2)] == [f"q{CAP}", f"q{CAP + 1}"]


def test_the_opener_and_a_turn_without_his_words_are_not_his(tmp_path):
    room = tmp_path / "r"
    _said(room, 0, how="opener", said="(The manager has just opened the room. Greet them.)")
    _said(room, 1, said="")
    write(room, {"reply": "no words of his"}, wording=WORDING, calls=[])
    _said(room, 2)
    assert [p[:4] for p in past(room)] == [("q2", "a2", ["c2"], "typed")]


def test_a_turn_whose_lane_failed_keeps_his_words_and_has_no_reply(tmp_path):
    room = tmp_path / "r"
    failed = {"how": "typed", "said": "hello", "failed": "LaneDown: 402"}
    write(room, failed, wording=WORDING, calls=[])
    assert [p[:4] for p in past(room)] == [("hello", None, [], "typed")]


def test_how_he_took_the_turn_comes_back_so_a_tap_can_be_drawn_as_his_phone_showed_it(tmp_path):
    room = tmp_path / "r"
    _said(room, 0, how="tapped", said="endorsed")
    write(room, {"said": "no how"}, wording=WORDING, calls=[])
    assert [(p.said, p.how) for p in past(room)] == [("endorsed", "tapped"), ("no how", None)]


def test_a_line_that_cannot_be_read_is_skipped(tmp_path):
    room = tmp_path / "r"
    _said(room, 0)
    with path(room).open("ab") as f:
        f.write(b'{"said": "cut of\n[1, 2]\n"a string"\n\xff\xfe\n')
    _said(room, 1)
    with path(room).open("ab") as f:
        f.write(b'{"said": "q2", "rep')
    assert [p.said for p in past(room)] == ["q0", "q1"]


def test_a_room_with_no_turn_file_has_nothing_to_draw(tmp_path):
    assert past(tmp_path / "never-walked") == []
    (tmp_path / "walked-before-109" / "output").mkdir(parents=True)
    assert past(tmp_path / "walked-before-109") == []


def test_two_rooms_never_mix(tmp_path):
    a, b = tmp_path / "konstantin-chat-glm", tmp_path / "konstantin-chat-deepseek"
    _said(a, 0)
    _said(b, 1)
    _said(a, 2)
    assert [p.said for p in past(a)] == ["q0", "q2"]
    assert [p.said for p in past(b)] == ["q1"]


def test_the_reader_reads_line_by_line_and_keeps_no_calls(tmp_path, monkeypatch):
    """A line can reach hundreds of KB (12_nemo_check on 109): the file is never read whole, and
    what is kept per turn is his words, the reply and the cards, never the calls."""
    room = tmp_path / "r"
    write(room, {"how": "typed", "said": "q", "reply": "a"}, wording=WORDING,
          calls=[{**_call(0), "pad": "x" * 300_000}])

    whole = lambda *a, **k: pytest.fail("the turn file was read whole")  # noqa: E731
    monkeypatch.setattr(type(path(room)), "read_bytes", whole)
    monkeypatch.setattr(type(path(room)), "read_text", whole)
    assert [p[:4] for p in past(room)] == [("q", "a", [], "typed")]


# ── the calls not yet in a turn, kept by room ─────────────────────────────────────────────────
def test_calls_are_taken_by_the_room_they_were_made_for_and_only_once(tmp_path):
    calls = Calls()
    a, b = tmp_path / "a", tmp_path / "b"
    calls.add(a, _call(1))
    calls.add(b, _call(2))
    calls.add(a, _call(3))
    assert calls.take(a) == [_call(1), _call(3)]
    assert calls.take(a) == []
    assert calls.take(b) == [_call(2)]


def test_a_room_that_made_no_call_takes_an_empty_list(tmp_path):
    assert Calls().take(tmp_path / "quiet") == []


def test_two_rooms_written_in_parallel_never_interleave(tmp_path):
    """Ticket 100's need: fifty rooms share one process and one call path. Many threads per room,
    turns large enough that an unlocked append would tear, and each file holds only its own."""
    calls, rooms = Calls(), [tmp_path / "room-a", tmp_path / "room-b"]
    big = "x" * 200_000

    def walk(room, n):
        for i in range(5):
            calls.add(room, {**_call(i), "made_for": room.name, "pad": big})
            write(room, {"n": n, "i": i, "for": room.name}, wording=WORDING, calls=calls.take(room))

    threads = [threading.Thread(target=walk, args=(r, n)) for n in range(4) for r in rooms]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for room in rooms:
        lines = path(room).read_bytes().decode().splitlines()
        turns = [json.loads(ln) for ln in lines]
        assert len(turns) == 20
        assert {t["for"] for t in turns} == {room.name} == {t["room"] for t in turns}
        assert {c["made_for"] for t in turns for c in t["calls"]} == {room.name}


@pytest.mark.parametrize("error", [None, ""])
def test_an_empty_error_is_still_an_answer(error):
    assert _call(1, error=error)["outcome"] == ANSWERED


def test_a_write_cut_inside_a_character_loses_only_the_torn_line(tmp_path):
    """Ticket 210 (1): the writer keeps non-ASCII, so a cut can land between a character's bytes.
    Decoding the file whole would raise there and lose every turn; each line decodes on its own."""
    f = tmp_path / "turns.jsonl"
    torn = '{"n": 1, "said": "Grüezi"}'.encode()
    assert torn[-7:-6] == b"\xc3"  # the cut lands between the two bytes of the u-umlaut
    f.write_bytes('{"n": 0, "said": "Grüezi"}\n'.encode() + torn[:-6] + b'\n{"n": 2}\n')
    assert read(f) == [{"n": 0, "said": "Grüezi"}, {"n": 2}]


# ── ticket 132: what he said on a turn, as a chat confirmation is read from it ─────────────────
def test_his_words_on_a_turn_are_what_he_typed_or_what_the_tap_showed_him(tmp_path):
    """ADR-0030, 132's amendment: a confirmation's words are read from his turn — his `said`, or
    for a tap the words it showed him (`shown`) — each by the turn's id, with the day it ended."""
    room = tmp_path / "room-1"
    typed = write(room, {"said": "make it two hours", "how": "typed"}, wording=WORDING, calls=[],
                  clock=lambda: 1_800_000_000.0, new_id=lambda: "t-typed")
    write(room, {"said": "endorsed", "shown": "Yes, agreed", "how": "tapped"}, wording=WORDING,
          calls=[], clock=lambda: 1_800_090_000.0, new_id=lambda: "t-tap")
    write(room, {"said": "(opens)", "how": "opener"}, wording=WORDING, calls=[],
          new_id=lambda: "t-opener")
    assert typed["turn_id"] == "t-typed"
    assert turn_file.his_turns(room) == {
        "t-typed": {"words": "make it two hours", "on": "2027-01-15"},
        "t-tap": {"words": "Yes, agreed", "on": "2027-01-16"}}
    assert turn_file.his_turns(room, {"t-tap"}) == {
        "t-tap": {"words": "Yes, agreed", "on": "2027-01-16"}}


def test_a_room_with_no_turn_file_holds_no_turn_of_his(tmp_path):
    assert turn_file.his_turns(tmp_path / "none") == {}


@pytest.mark.parametrize("line", [
    b"not json at all",                                  # a line that cannot be read
    b'["t-1", "yes"]',                                   # read, but not a turn
    b'{"turn_id": "t-1", "how": "typed"}',               # a turn with no words of his
    b'{"turn_id": "t-1", "said": "(opens)", "how": "opener"}',  # nemo's opener, not his
])
def test_a_line_that_is_not_a_turn_of_his_is_no_turn_of_his(line):
    assert turn_file._his_turn(line, None) is None


def test_a_line_naming_no_wanted_id_is_never_read():
    """`wanted` is matched on the raw bytes first, so a line naming none of them is not parsed."""
    assert not turn_file._names_one(b'{"turn_id": "t-2", "said": "yes"}', {"t-1"})
    assert turn_file._names_one(b'{"turn_id": "t-1", "said": "yes"}', {"t-1"})
    assert turn_file._names_one(b"anything", None)


def test_his_turn_does_not_parse_a_line_naming_no_wanted_id(monkeypatch):
    monkeypatch.setattr(turn_file, "_his_line", None)  # calling it would raise
    assert turn_file._his_turn(b'{"turn_id": "t-2", "said": "yes"}', {"t-1"}) is None


def test_a_line_that_names_a_wanted_id_but_is_another_turn_is_not_kept():
    """The raw match is only a sieve: his words may name the id while the turn is another one."""
    line = b'{"turn_id": "t-2", "said": "as I said on t-1", "at": 0}'
    assert turn_file._his_turn(line, {"t-1"}) is None
    assert turn_file._his_turn(line, {"t-2"}) == ("t-2", {"words": "as I said on t-1",
                                                          "on": "1970-01-01"})


def test_a_turn_with_no_end_time_is_dated_the_epoch_and_a_tap_reads_as_it_showed():
    assert turn_file._his_turn(b'{"turn_id": "t-1", "said": "endorsed", "shown": "Yes"}',
                               None) == ("t-1", {"words": "Yes", "on": "1970-01-01"})
