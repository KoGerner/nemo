# Orphaned session directories are swept every 15 minutes, at an age of two hours

**Proposed by ticket 05, 2026-09-12. The numbers are a proposal, not an owner call** — ADR-0010
left "what sweeps the disk after a room dies" explicitly open, and nothing measured picks these two
figures for us. What is measured is that the sweep has to exist.

## What forces it

`tests/isolation/test_room_isolation.py::test_7` kills a Chainlit process with `SIGKILL` while a
room is open and finds the session's files directory still on disk afterwards. That is not the crash
case only: Chainlit deletes a session's directory `session_timeout` seconds after the socket drops
(`socket.py:282-286`), the default is 3600 s, and uvicorn's graceful shutdown will not stay alive
for an hour. On a real box an ordinary restart orphans every open room's directory too, and each
deploy adds another set. Nobody ever collects them.

## The decision

`nemo.door.sweep` removes every directory under the skin's `.files/` that nothing has touched for
**`SWEEP_AGE_SECONDS = 7200`**, and `deploy/nemo-sweep.timer` runs it every
**`SWEEP_INTERVAL_SECONDS = 900`**. The demo skin also calls it once when a room opens, so a box
with a stopped timer still converges while it is in use.

Why those two numbers:

- **Two hours** is Chainlit's own 3600 s `session_timeout` plus an hour of slack. Under the age
  Chainlit itself still believes a dropped socket may come back, and a manager who puts their phone
  down mid-walk is the ordinary path (ADR-0010), so a shorter age would delete a live room's upload
  to save disk that is not the constraint — this box has 15 Gi of RAM and plenty of disk.
- **Fifteen minutes** is short enough that a deploy's orphans are gone before the next one and long
  enough that the timer is invisible. Nothing is racing it: a directory is only taken once it is two
  hours cold, so the interval only sets how late a sweep is, never whether it is safe.

Both are single constants in `nemo/door.py`. Changing them is an edit and a rerun of the suite, and
the owner may set different ones on the day without touching the code's shape.

## What this does not decide

How long a room lives, or what stops one. That is still open and still belongs to whoever writes the
room lifecycle; this ADR only collects what a stopped process leaves behind, however it stopped.
