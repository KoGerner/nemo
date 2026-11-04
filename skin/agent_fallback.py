"""His switch, and the words other files read here (ticket 599, ADR-0061 decision 11).

ADR-0053's agent fallback answered a typed line no code card answered with its own small loop. No
turn reached it any more: with the switch ON a typed line in free chat goes to the model-led turn
(`led_turn`), and the phone has no switch. Ticket 599 took the loop out, with its brief, its claim
check, its lists and its route; what the live path borrowed from it moved whole to `line_reads`.

What stays is the switch: one line, `on` or `off`, in `SWITCH`, outside the tree, so flipping it
needs no build and no commit, and read at run time on every turn (`switched_on`). With the file
absent it is OFF, and OFF is today's behaviour byte for byte. Tests set it through `ENV` and never
read the file. And the words files outside 599 read here by name (Amend 1d): the plain line, the
graph's link, and three whose home is now `line_reads`.
"""

from __future__ import annotations

import os
from pathlib import Path

#: their home is `line_reads`; prompt_check.py and tests t490, t534, t538 and t546 read them here
from line_reads import IMPACT_OVER_TIME as IMPACT_OVER_TIME
from line_reads import MOST as MOST
from line_reads import SUPPLIER as SUPPLIER

#: his switch (ADR-0053 answer 2): one line, "on" or "off"; absent or anything else is OFF
SWITCH = Path.home() / ".config" / "nemo" / "agent-fallback"
#: how a test (or a test's child process) sets the switch instead, so no test reads `SWITCH`
ENV = "NEMO_AGENT_FALLBACK"
#: the plain line where nothing usable came back (never an empty answer); `led_turn.PLAIN_LINE`
NO_ANSWER = "I couldn't give you a reliable answer to that. Try asking it another way."
#: code's line under an answer about a resource: the graph page opened on it (488's words)
GRAPH_LINK = "[Open the dependency graph]({link})"


def switched_on() -> bool:
    """The switch, read now: `ENV` where it is set (a test's), else `SWITCH`'s one line."""
    said = os.environ.get(ENV)
    if said is None:
        try:
            said = SWITCH.read_text(encoding="utf-8")
        except OSError:
            return False
    return said.strip().lower() == "on"
