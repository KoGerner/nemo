"""Ticket 535 (ADR-0056, rework S4): one check stack for model text.

Every sentence the model writes on a model-led turn goes through the same checks before he sees it,
and a failing one is dropped with its reason (the turn record's `drops`, t532). No model judges:
every check reads the room's files, the turn's own reads and tool results, or his line.

- **Cite and claim** (`_why`): a sentence stating a figure, date, count or impact class ends with a
  `[file:line]` cite (`[file:a-b]` and `[file:a,b]` too) of a line read this turn, and each of
  those facts stands on the cited line, as an exact substring. A cite into a `.json` file is
  checked against the whole row object spanning that line (`_json_row`): a register cite points at
  a row's first line and the value sits lower.
- **Column pairs** (`PAIRS`): only the seed seat's 19 (`column-pairs.md`, 20_marschkamp). A sentence
  whose words claim one member of a pair while its figure sits in the other member is dropped.
  P1-P3, P13 by the cited row's columns (`_columns`); P4 by the method's reading; P5-P6 by the cited
  file's year; P8 by who says the cited line; P9-P12 by code's counts (`_counts`); P14 by the
  story's today and code's weekday; P15 by his own hours; P19 by the line that states money. P7 is
  the substring check (an empty cell holds no figure), P16 is `words.functions_only`, P17 the demo
  pack's mark (`_marked`), P18 the absence check.
- **Absence** (`ABSENT`): "there is no X" stands only where a cell of the cited row itself
  states the absence (`_states_absence`: its workaround cell only, read through `core.spof`, 604);
  otherwise the files only name none ("not named", "not stated"). 649: a count of rows in the
  register's words ("2 have no workaround", "7 more have none stated") is no absence claim; it is
  code's number (`_rows_counted`) or dropped. 664: so is a total of the table an answer lists
  ("depends on 16 resources across 8 groups": `_total_counted`). 666: "not stated" about
  workarounds, owners, dates or single points of failure, wholly one form and one name, is read
  against code's fact for the activity: a line denying what code holds goes (`_denies_code`); every
  other stands.
- **Single point of failure** (604, 576 part C): said of a register resource only where
  `core.spof` flags its row (`_not_spof`).
- **Action claims**: 530's rule, `core.drop_claims` and its closed done-word list, against what
  this turn's tools did (`DONE_BY`): a sentence describing a draft this reply shows stands; a
  sentence saying something was placed, sent, moved or blocked never does (taps do that); a
  negated one ("Nothing has been sent") is no claim. 449's `core.drop_denials` beside it.
- **Names to functions** (ADR-0051), in text and draft bodies, unless his line asks for names.
- **Must-cover misses** are recorded, never appended (his Q26). **A list code handed** (the
  method's MTPD reading, the due list, the last participants, the suppliers, the invitees) may
  not be shortened: an answer leaving an item out is refused (`Checked.refused`).
- **A drop never leaves a sentence without its subject or label** (`_orphans`).
- **The graph answer** (536, 488): at most three plain lines; the rest are dropped with their
  reason (`GRAPH_LINES`). 632: a line naming a must-cover item the drawn graph shows is no plain
  line, and never cut; the items the drawn graph shows count as covered (`covered`'s `drawn`).
- **A named day** (536, 544): where his line names a day holding interviews, a sentence drawn on
  another interview goes (`OTHER_DAY`); the rest of the stack is unchanged.
- **A count a fact counts** (645): a who or how-many count ("Three people decide", "4 gaps") is
  the count the fact tool returned this turn (`Room.counts`) where the sentence opens on it, else
  dropped (`_fact_counts`); a date
  a fact value holds stands uncited as its other values do; a cite naming a file and no line is
  one cite miss (`NO_LINE`), never the figures of its path.
- **Next steps** (`next_steps`): the model's, kept only where a tool of this room can do them.
- **A retry changes only the failed item** (`retry`): after a send-back, code diffs the retry's
  arguments against the first try's and refuses a retry that changes anything else.
- **607, every answer:** a tap's narration and a guidance answer meet this stack too (the
  session's `_checked`). A count code counts is said as code counts it (`COUNT_OFF`, rule 11); a
  tap a sentence names is one drawn (`TAP_OFF`); a quotation stands on its cited line
  (`NOT_QUOTED`); a heading goes with its quotes and no connective opens the answer after a drop
  (576 A and B). A list number left alone, a date's day or year, an ISO date and a date said with
  its weekday are no figures and no counts. A fact tool's value stands uncited only about the
  activity it was read for, or anywhere where read for the whole company (`known_by`).
"""

from __future__ import annotations

import dataclasses
import datetime
import functools
import itertools
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import line_reads
import workspace

from nemo import impact, interview, walk

import PROTOTYPE_core as core
import PROTOTYPE_draft as drafting
import PROTOTYPE_words as words

#: what the turn read: (room-relative path, line number) -> the line
Read = dict[tuple[str, int], str]
#: a tool the room offers: code's matcher for it, its tap's label, its call (`Session._offered`)
Offer = tuple[Callable[[str], Any], str, dict[str, Any] | None]
#: one cell of cited evidence: (its column, its value, the activity its row is for or "")
Cell = tuple[str, str, str]
#: the group of a cell from a row around the cited one (a consumer's resource)
OUTER = "^"

#: the cite forms: [file:12], [file:12-14], [file:2982,4028] (the probe's note 3)
_SPAN = r"\d+(?:\s*[-–]\s*\d+)?"
CITE = re.compile(r"\[(?P<path>[\w./ -]+?\.(?:md|json)):(?P<at>" + _SPAN + r"(?:\s*,\s*" + _SPAN +
                  r")*)\]")
_CITES = re.compile(r"[ \t]*(?:" + CITE.pattern.replace("(?P<path>", "(?:").replace(
    "(?P<at>", "(?:") + r"[,;]?[ \t]*)+")
#: 640 (Amend 1): a bracket of several cites at ";" or ",", "[a.md:100; b.md:45]": that many
#: cites (`each_cite`), never the file names' digits and the line numbers as figures
_SPAN_END = _SPAN + r"(?![\w./-])"
_ONE_CITE = r"[\w./ -]+?\.(?:md|json):" + _SPAN_END + r"(?:\s*,\s*" + _SPAN_END + r")*"
_SEVERAL = re.compile(r"\[(" + _ONE_CITE + r"(?:\s*[;,]\s*" + _ONE_CITE + r")+)\]")
#: a cite written after the sentence's full stop belongs to that sentence
_CITE_AFTER = re.compile(r"([.!?])((?:[ \t]*" + CITE.pattern.replace("(?P<path>", "(?:").replace(
    "(?P<at>", "(?:") + r")+)")
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\d])")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DATE = re.compile(r"\b(?P<day>\d{1,2})\s+(?P<month>" + "|".join(_MONTHS) +
                  r")[a-z]*\.?(?:\s+(?P<year>\d{4}))?\b")
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
#: 647: a number that is part of a name is no figure: a file's ("plan-2025.xlsx"), a code's
#: ("microsoft-365"), a product's after a capitalised word mid-sentence ("Microsoft 365"); never
#: a year, a decimal, one with a unit, or one after a level's, a date's or a time's word
_UNIT = r"\s*(?:%|€|[hk]\b|(?:minute|hour|day|week|month|year)s?\b)"
IN_NAME = re.compile(
    r"\b[\w-]*\d[\w-]*\.(?:md|json|docx?|xlsx?|pptx?|pdf|csv|txt)\b"
    r"|(?<=[A-Za-z]-)\d+(?![\d]|[.,]\d|" + _UNIT + r")"
    r"|(?<=[^\s.!?:;] )(?P<name>(?!(?:Level|Tier|Class|Category|Priority|Score|Impact|Step|Stage"
    r"|Phase|Day|Week|Hour|Month|Year|Line|Page|Row|Table|Item|Top|Within)s?\b|(?:"
    + "|".join(_MONTHS) + "|" + "|".join(d[:3] for d in _WEEKDAYS) + r")[a-z]*\b)"
    r"[A-ZÄÖÜ][^\W\d_]*[a-zäöüß][^\W\d_]*)\s+(?!(?:19|20)\d{2}\b)\d+(?![\d]|[.,]\d|" + _UNIT + ")")
#: 645: the month and weekday words a date in the room's words takes (`led_turn.room_words`)
MONTHS, WEEKDAYS = _MONTHS, _WEEKDAYS
WEEKDAY_DATE = re.compile(r"\b(?P<weekday>" + "|".join(d[:3] for d in _WEEKDAYS) +
                          r")[a-z]*,?\s+" + DATE.pattern)
#: 607: an ISO date (read as the date in words) and a year alone: a date's parts are no figures
ISO_DATE = re.compile(r"\b(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])-(?P<day>0[1-9]|[12]\d|3[01])\b")
YEAR = re.compile(r"(?<![\w.,/-])(?:19|20)\d{2}(?![\w/-]|[.,]\d)")
#: a list's own number or bullet at a line's start is no figure (607: one left alone too)
_LEAD = re.compile(r"^\s*(?:[-*•]|\d+[.)])(?:\s+|$)")
#: 713: a number opening a sentence, in its words or not ("1.", "1) Call", "**1.** Call", never
#: "1.5"), and one `answer_shapes.unnumbered` holds as that many invisible marks
_OPENING_NUMBER = re.compile(r"[-*•\s]*(\d+)[.)](?!\d)")
_HELD_NUMBER = re.compile(r"\s*\u2063+")
#: 713: a table's separator line, "|---|:--|"
_SEPARATOR = re.compile(r"\s*\|?(?:\s*:?-+:?\s*\|)+(?:\s*:?-+:?\s*)?")
#: 665: a list's number where a sentence ends, right before its item or at the line's end ("…: 1.",
#: "Call the supplier 2.")
_LIST_END = re.compile(r"(?<=\s)(\d{1,2})\.\s*$")
#: 665 (49's widening): a parenthesised number right before an item, "check (1) the backup and (2)"
_PAREN = re.compile(r"\((\d{1,2})\)(?=\s+[^\W\d])")
#: 665: a list's "2." opening a line or a sentence
_TWO = re.compile(r"\s*2[.)](?:\s|$)")
#: 665 (23's read): an item ends on the list's next number only on a thing named after "the", "a",
#: … ("Call the supplier 2."); "The RTO is 2.", "Production flags 3." keep it a figure
_ITEM_END = re.compile(r"\b(?:the|a|an|its|their|this|that|each|every|our|your|his|her)"
                       r"(?:\s+[A-Za-z][\w-]*){1,3}\s*$", re.I)
#: 665: a word anywhere in the item that takes the number after it ("runs at a level 3.")
_TAKES_A_FIGURE = re.compile(r"\b(?:is|are|was|were|be|of|for|at|on|to|by|in|within|under|over|"
                             r"than|about|around|has|have|had|flags?|states?|lists?|counts?|"
                             r"totals?|numbers?|levels?|steps?|stages?|phases?|tiers?|shifts?|"
                             r"many|much|minimum|maximum|least|most|up)\b",
                             re.I)
#: 665 (23's r5 read): an item that may end on the list's next number opens on a step to take, so it
#: states nothing ("Call the supplier 2."); "Resources without a workaround 3." keeps it a figure
_STEP = re.compile(r"^\s*(?:Call|Ask|Check|Confirm|Review|Book|Send|Update|Agree|Plan|Prepare|"
                   r"Collect|Verify|Clarify|Schedule|Invite|Discuss|Follow|Write|Read|Note|Bring|"
                   r"Contact|Request|Walk|Visit|Test|Name|Find|Get|Set|Raise|Share|Mark|Record)\b")
#: 665 (23's r7 read): a list's lead "…: 1." is a whole label that heads a list, with at most a
#: context with no comma ("Focus points for the re-interview: 1."), so its 1 is a marker; "Open
#: gaps in production: 1." keeps the 1 a figure (49: closed list). Before/After take one word, an
#: optional "the" first ("Before the interview: 1.", "After it: 1."), then the same context
_LEAD_LABEL = re.compile(r"\s*(?:(?:Focus|Action) points?|Focus|Next steps|Steps|Open (?:points|"
                         r"questions)|Questions to ask|Points to (?:check|ask|raise)|Things to "
                         r"(?:check|ask|do|raise)|To do|Plan|Agenda|Priorities|Tasks|Topics|"
                         r"Actions|(?:Before|After)(?:\s+(?:the\s+)?[\w-]+)?)"
                         r"(?:\s+(?:for|before|after|at|in|on|ahead of)\s+[^,:;]+)?\s*:", re.I)
#: 665: a unit, which a measure's label or an item names ("The RTO in hours: 1.")
_UNIT_WORD = re.compile(r"\b(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|h)\b",
                        re.I)
#: 607 (576 B): a connective that leans on the sentence before it
CONNECTIVE = re.compile(r"^(\s*(?:[-*•]|\d+[.)])?\s*)(?:But|And|So|Yet|However|Also|Still),?"
                        r"\s+(\w)")

#: absence said as a fact (U4), and absence said as the files' silence
NONE_UNTIL = re.compile(
    r"\bno (?P<cls>[a-z][\w ]*?) impacts? until (?P<h>\d+)\s*h(?:ours?)?\b", re.I)  # AMEND 1
ABSENT = re.compile(r"\b(?:there (?:is|are|was|were) no|(?:has|have|had) no|no \w+ (?:exists?|at "
                    r"all)|none exists?|does(?:n't| not) exist)\b", re.I)
STATED_ABSENT = re.compile(r"\bnot (?:named|stated|recorded|given)\b", re.I)
#: 666: a sentence that says what is not stated, heading it ("Not stated: the owner") or ending on
#: it ("The owner is not stated in the files"). Saying a source other than the files ("in the
#: plan") says less than code reads, and stands
_NOT_STATED_HEAD = re.compile(r"^\W*not (?:named|stated|recorded|given)(?: in the files)?\s*"
                              r"[:—–-]\W*", re.I)
_NOT_STATED_TAIL = re.compile(r"(?:\s+(?:is|are|was|were)|\s*:)?\s+not (?:named|stated|recorded|"
                              r"given)(?: in the files)?\W*$", re.I)
#: 666: what a "Not stated" line must be, whole, for code to hold a fact against it. Each `name` is
#: read as one register row's, so a list of names reads as none and stands
_NONE_WITHOUT = re.compile(r"no (?:supplier|dependency|resource|row)s?(?: or (?:supplier|"
                           r"dependency|resource|row)s?)?(?: (?:of|for|in) this (?:process|"
                           r"activity))? (?:is|are) without (?:a )?workarounds?(?: in the (?:files|"
                           r"register))?", re.I)
_WORKAROUND_FOR = re.compile(r"(?:an? |the )?workarounds? for (?:the )?(?P<name>.+)", re.I)
_OWNER_OF = re.compile(r"(?:an? |the )?owners? (?:of|for) (?:the )?(?P<name>.+)", re.I)
_PROCESS_OWNER = re.compile(r"(?:the )?process owner", re.I)
_ANY_SPOF = re.compile(r"(?:an? |any |the )?(?:single points? of failure|SPOFs?)", re.I)
_SPOF_NAMED = re.compile(r"whether (?:the )?(?P<name>.+) is (?:an? |the )?(?:single point of "
                         r"failure|SPOF)", re.I)
_REVIEW_DATE = re.compile(r"(?:the )?(?:(?:next )?review(?: due)? date|date of the (?:next )?review"
                          r"|due date)", re.I)
_LAST_DATE = re.compile(r"(?:the )?(?:last interview date|date of the last interview)", re.I)
_REINTERVIEW_DATE = re.compile(r"(?:the )?(?:re-?interview date|date of the re-?interview)", re.I)
_PLAN_DAY = re.compile(r"\b\d{1,2} [A-Z][a-z]{2,8} \d{4}\b")
_REINTERVIEW_ON = re.compile(r"\b[Rr]e-?interview (?:planned for|held)(?: on)? (?:[A-Z][a-z]{2} )?"
                             r"\d{1,2} [A-Z][a-z]{2,8}\b")
#: 666: a cell that holds no way round though it says something
_NO_WAY_ROUND = re.compile(r"\W*(?:none|n/?a|not (?:stated|known)|unknown)?\W*", re.I)
#: 604 (576 part C): a single point of failure said, and said not to be one
SPOF_SAID = re.compile(r"\bsingle points? of failure\b|\bSPOFs?\b", re.I)
SPOF_DENIED = re.compile(r"\b(?:(?:is|are|was|were)\s+(?:not|never|no longer)(?:\s+an?|\s+the)?|no"
                         r"|none of the)\s+(?:single points? of failure|SPOFs?)\b", re.I)

#: P17: the demo pack's mark, as the files write it and as nemo shows it (ADR-0034 D10's)
DEMO = re.compile(r"written for the demo pack", re.I)
DEMO_MARK = " (for the demo)"
#: a sentence that already says so, in the files' words or nemo's
DEMO_SAID = re.compile(r"\bfor the demo\b", re.I)
#: 720: a row a fact handed that was written for the demo pack, and what of it is its value: `id`
#: and `controls`, never its resource or activities (a true record sentence names those)
MARKED_ROW = re.compile(r'\{[^{}]*"marking":\s*"[^"]*written for the demo pack[^{}]*\}', re.I)
ROW_VALUE = re.compile(r'"(?:id|controls)":\s*"([^"]+)"')

#: the words a sentence claims a column with (column-pairs.md); a member is its columns' names
RTO = re.compile(r"\bRTOs?\b|\brecover\w* within\b|\bback within\b|\brecovery target", re.I)
MTPD = re.compile(r"\bMTPD\b|\btolerable outage\b|\bcan be down\b", re.I)
RPO = re.compile(r"\bRPOs?\b|\bdata loss\b|\blose up to\b", re.I)
STATUS = re.compile(r"\breviewed\b|\bconfirmed (?:on|unchanged)\b|\bplanned for\b|\bheld\b", re.I)
LAST_INTERVIEW = re.compile(r"\blast interview", re.I)
DUE = re.compile(r"\bdue\b", re.I)
#: (pair, {member: (its words, the names of its columns)})
COLUMN_PAIRS: list[tuple[str, dict[str, tuple[re.Pattern[str], tuple[str, ...]]]]] = [
    ("P1", {"RTO": (RTO, ("rto",)), "MTPD": (MTPD, ("consumer_mtpd", "mtpd"))}),
    ("P2", {"RTO": (RTO, ("rto",)), "RPO": (RPO, ("rpo",))}),
    ("P13", {"Status": (STATUS, ("status",)),
             "Last interview": (LAST_INTERVIEW, ("last interview",)),
             "Review due": (DUE, ("review due",))}),
]
#: P4: the method's reading, said as such (482 r2)
BY_METHOD = re.compile(r"\bimpact scores give\b|\bby the method\b|\bthe method(?:'s)? "
                       r"(?:reading|gives|reads)\b|\bscores (?:give|reach)\b", re.I)
_HOURS = re.compile(r"(\d+)\s*h(?:ours?)?\b")
#: P5, P6: the year a sentence claims
THIS_YEAR = re.compile(r"\bthis year\b|\bnow\b", re.I)
LAST_YEAR = re.compile(r"\blast year\b", re.I)
_SCORE = re.compile(r"\bscores?\b|\blevels?\b|\bimpact\b|\brated\b", re.I)
#: P8: a figure on the interviewer's own line
_SUM_UP = re.compile(r"^\s*(?:\*\*)?(?:To sum up|Last year)\b", re.I)
#: P9-P12: the words that claim each count
TALK_ABOUT = re.compile(r"\b(?:talk|talks|mention|mentions|touch|touches)\b|\babout it\b", re.I)
READ_WORD = re.compile(r"\bread\b", re.I)
REVIEWED_THIS = re.compile(r"\breviewed\b", re.I)
NO_INTERVIEW = re.compile(r"\b(?:no|without)\b[^.]*\binterview", re.I)
OVERDUE = re.compile(r"^(?!.*\b(?:more than|over) (?:a|one) year\b).*\boverdue\b", re.I | re.S)
OVER_A_YEAR = re.compile(r"\b(?:more than|over) (?:a|one) year\b|\bover a year\b", re.I)
USES = re.compile(r"\buse[sd]?\b|\bdirect(?:ly)?\b", re.I)
REACHES = re.compile(r"\bgoes down with\b|\breach\w*\b|\baffect\w*\b", re.I)
#: P14: the story's today
TODAY = re.compile(r"\btoday(?: is|,)?\s+(?:(?:" + "|".join(_WEEKDAYS) + r"),?\s+)?" +
                   DATE.pattern, re.I)
#: P15: an hour of the day
HOUR = re.compile(r"\b(?P<h>\d{1,2})(?::(?P<m>\d{2})|\s?(?P<ap>[ap]\.?m\.?)\b|\s?o['’]clock)",
                  re.I)
#: P15: an hour said bare after "at" ("at 9"), never a duration ("at 8 hours")
AT_HOUR = re.compile(r"\bat (\d{1,2})\b(?!\s*(?:h|hours?)\b)")
#: 588 (L1): a count of days, hours, weeks or months in words, read as its figure in a letter
SPELLED = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
           "twelve")
_SPELLED = re.compile(rf"\b({'|'.join(SPELLED)})(?=\s+(?:day|hour|week|month)s?\b)", re.I)
#: 607 (rule 11): a count said of the things code counts
COUNTED = re.compile(rf"\b(\d+|{'|'.join(SPELLED)})\s+(?:[\w-]+\s+)?(?:BIAs?|reviews?|"
                     r"process(?:es)?|activit(?:y|ies)|interviews?)\b", re.I)
#: 640 (b), 603's rule 11: a count of things a first line says, and what it counts
LISTED = re.compile(rf"\b(\d+|{'|'.join(SPELLED)})\s+((?:[A-Za-z-]+\s+)?(?:mismatch(?:es)?|gaps?"
                    r"|dependenc(?:y|ies)|people|persons?|owners?|suppliers?|processes|BIAs?"
                    r"|drafts?|interviews?|changes?|points?|risks?|resources?|workarounds?))\b",
                    re.I)
#: 645: a cite naming a file and no line, alone in its bracket or among others
FILE_ONLY = re.compile(r"\[(?:[^\]\[]*?[;,]\s*)?(?P<path>[\w./-][\w./ -]*?\.(?:md|json))"
                       r"\s*(?=[;,\]])")
#: 645: the word a count says, as the thing a fact result counts (`Room.counts`)
#: 648: what a spof lead's count is said of: the things that have no workaround
NO_WORKAROUND_SAID = re.compile(r"[^,;.]*?\b(?:have|has|with)\s+no\s+workarounds?\b", re.I)
#: 656: a spof lead's count said as single points of failure, and a count said to have no
#: workaround after the lead's own ("4 dependencies, two with no workaround")
SPOF_COUNTED = re.compile(r"\s+of\s+failure\b", re.I)
NO_WORKAROUND_AFTER = re.compile(rf"\s*,\s*(?:and\s+)?(?P<n>\d+|{'|'.join(SPELLED)})\s+"
                                 r"(?P<what>(?:of (?:them|which)\s+)?(?:have|has|with)\s+no\s+"
                                 r"workarounds?)\b", re.I)
#: 649: a count of rows said in the register's words, the count its subject ("2 have no workaround",
#: "7 more have none stated", "26 of them have no workaround stated"): no absence claim. Never a
#: lone "one" ("this one has no workaround" is one thing), never a name's number (647's `IN_NAME`).
#: 759: "2 resources have no workaround" only where the count opens the sentence, "Yes," before it
#: at most: "Level 2 resources" and "over 2 resources" count nothing
ROWS_COUNTED = re.compile(rf"(?:\b(?!\S+\s+resources\s)|^[\s*_]*(?:yes,[\s*_]*)?)(?P<n>\d+|"
                          rf"{'|'.join(SPELLED[1:])})\s+(?P<what>(?:of (?:them|which|"
                          r"these)\s+|more\s+|resources\s+)?(?:have|has)\s+(?:no\s+workarounds?"
                          r"(?P<stated>\s+stated)?|none\s+(?P<none>stated)))\b", re.I)
#: 664: a count said in words up to 99, for a total (`SPELLED` stops at twelve, and tables do not)
_TEENS = ("thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
_WORDS = {**{w: k for k, w in enumerate((*SPELLED, *_TEENS), 1)},
          **{w: 10 * k for k, w in enumerate(_TENS, 2)},
          **{f"{w}-{u}": 10 * k + n for k, w in enumerate(_TENS, 2)
             for n, u in enumerate(SPELLED[:9], 1)}}
_SAID_N = rf"\d+|{'|'.join(sorted(_WORDS, key=len, reverse=True))}"
#: 664: a total of an activity's dependency table: "depends on N resources", "N dependencies in M
#: groups". Only "direct" may qualify it (a mixed pair): "2 critical resources" counts some of the
#: rows, and so does a total that goes on ("in 2 groups with no workaround", "3 resources owned by
#: IT", "2 resources: Microsoft 365 and the ERP"): it must end its clause, and one that says its
#: groups may run on in a list or a clause of its own
TOTAL = re.compile(
    r"(?P<on>\b(?:depends|relies|draws)\s+on\s+(?:(?:its|the|a\s+total\s+of)\s+)?)?"
    rf"(?:(?<!\blevel\s)\b(?P<n>{_SAID_N})\s+)?"
    r"(?P<what>(?:direct\s+)?(?:resources?|dependenc(?:y|ies)))"
    rf"(?:,?\s+(?:across|in|over)\s+(?P<m>{_SAID_N})\s+groups?)?\b"
    r"(?:\s+(?:in\s+total|in\s+all|altogether|overall)\b)?"
    rf"(?=\s*(?:$|[.;!?]|\(for the demo\)|,\s*(?:\d+\b|(?:{'|'.join(SPELLED)})\b|and\b|of\b)"
    r"|(?(m)[:()]|(?!))|(?(m)and\s|(?!))|(?(m)[—–-]\s|(?!))"
    r"|(?(m),(?!\s*(?:with|that|which)\b)|(?!))))", re.I)
#: 664 Amend 2: what may follow a total that lends its digits: the rows-counted forms, each with the
#: rows it names in a bracket, and those it can run without, said with their rows (`_form_holds`)
_ROWS_FORM = re.compile(rf"(?:{ROWS_COUNTED.pattern}|\b(?P<without>{_SAID_N})\s+(?:more\s+)?"
                        r"(?:it\s+)?can\s+(?:be\s+)?run\s+without(?:\s+them)?\b)"
                        r"(?:\s*\((?P<rows>[^()]*)\))?", re.I)
_HAS = r"(?:(?:is|are|has|lists?)\b\s*)?"
#: 664: what opens a sentence that says a total of the turn's activity, naming no subject of its own
_TURN_SAID = re.compile(r"\W*(?:(?:yes|no)\b\W*)?(?:(?:it|(?:this|the)\s+(?:activity|process)|this)"
                        rf"\b\s*)?(?:also\s+)?{_HAS}", re.I)
#: 664: what may stand between the activity a total is said of and the total: no other subject
_NAMED_SAID = re.compile(
    rf"(?:['’]s\b)?\W*(?:(?:it|there|which)\b\s*)?(?:also\s+)?{_HAS}(?:its\s+)?", re.I)
COUNTED_AS = {"people": "people", "person": "people", "persons": "people", "owner": "people",
              "owners": "people", "gap": "gaps", "gaps": "gaps", "mismatch": "mismatches",
              "mismatches": "mismatches"}
#: 759: a count of mismatches is code's only where nothing qualifies it, before or after: "3
#: financial mismatches", "3 mismatches last year", "2 mismatches are upward" count some or others
_COUNT_ENDS = re.compile(r"[\s*_]*(?:$|[,:;.!?—–-])")
#: 655: a fact's count (`Room.counts`) that stands as a figure, where the count is said as what it
#: counted, "2 are flagged a single point of failure" (`led_turn.FACT_COUNTS`), and not denied
COUNT_SAID = {"flagged": (r"(?:(?:are|were|is)\s+)?(?:flagged\s+(?:as\s+)?)?(?:an?\s+)?"
                          r"(?:single points? of failure|SPOFs?)\b"  # r4: no workaround is 649's
                          r"(?!\s*(?:and|,)?\s*(?:(?:with|have|has)\s+no|without\s+an?)\s+workaround)",
                          SPOF_DENIED)}
#: 655: a fact value that is a figure whole, ">168 h", "72 h": prose or a path holding one is none
_FIGURE_VALUE = re.compile(r"(?P<cmp>[<>≤≥~]?)\s*(?P<n>\d+(?:[.,]\d+)?)\s*"
                           r"(?P<unit>h|hours?|days?|%|€)?", re.I)
#: 655 r4: a figure as a sentence says it, its comparator and unit beside it, to match a value whole
_FIGURE_SAID = (r"(?:(?P<cmp>[<>≤≥~]|\bmore than|\bover|\bless than|\bunder)\s*)?(?<![\d.,]){n}"
                r"(?![\d]|[.,]\d)\s*(?P<unit>hours?\b|h\b|days?\b|%|€)?")
_SAID_AS = {"more than": ">", "over": ">", "less than": "<", "under": "<", "hour": "h",
            "hours": "h", "days": "day"}
#: 655 r4 (49's ruling): the fact key holding a member's figure; a member with none (the RPO) is
#: held by no fact value
MEMBER_KEYS = {"MTPD": ("mtpd_reading", "figure"), "RTO": ("mtpd_reading", "rto")}
MEMBERS = {"MTPD": MTPD, "RTO": RTO, "RPO": RPO}
#: 655 r4 (F3): a sentence naming a speaker or a source: a cite it carries is never taken out
SOURCED = re.compile(r"\b(?:said|says?|say|told|tells?|stated|according to|interview\w*|quoted?)\b",
                     re.I)
#: 655 r5 (23's R1), r6: the record itself said or says last year's figures: the fact's own
#: source, no speaker
RECORD_SAID = re.compile(r"\b(?:the record(?: from last year)?|last year['’]s record)"
                         r" sa(?:id|ys)\b", re.I)
#: 655 r8 (49's ruling, 23's form, widened by 49's ruling (a)): the record's own sentence, whole,
#: cites aside: a tie ("Last year", "Last year's", "the record" or "Last year's record" saying or
#: having), then only the figures, then the end; a record figure stands uncited in this shape only
#: (no clause split: any other word needs a line); "should be" only as the record's (review)
_RECORD_PAIR = (r"(the |an )?(MTPD|RTO) ((was|is|should be|of) )?[<>]?\d+ (h|hours)"
                r"( \(\d+ days\))?")
RECORD_FORM = re.compile(r"(?i:((last year,? )?the record (said|says|from last year says|had|has)"
                         r"|last year['’]s record (said|says|had|has)) (that )?"
                         r"|(last year,? |last year['’]s (?=MTPD|RTO))(?!.*should be))"  # a target
                         rf"{_RECORD_PAIR}((,| and|, and) {_RECORD_PAIR})*\.")
#: 655 r5 (R2): a year but the record's own: this year, now; one in digits too (in doubt, a line)
OTHER_YEAR = re.compile(r"\bthis year\b|\bnow\b|\bcurrently\b|\btoday\b|\bat present\b"
                        r"|\b(?:19|20)\d{2}\b", re.I)
#: 680: a sentence that says who was there last time and nothing else, whole: the frame, then the
#: list of `_PRESENT_ITEMS` (a date beside the frame is `when`); any other claim is none of these
_PRESENT_THERE = r"(?:was|were)(?: all| both)? (?:there|present)|attended"
_MONTH_SAID = "|".join(_MONTHS)
_DAY_SAID = "|".join(d[:3] for d in _WEEKDAYS)
_PRESENT_FRAMED = re.compile(
    r"(?P<head>(?:(?:who (?:was|were) (?:there|present)|who attended|participants|attendees"
    r"|present)\s+(?:(?:at|in|of) )?)?(?:the )?last (?:time|interview))"
    rf"(?P<when>\s*\([^()]*\)|,?\s+(?:(?:on|in)\s+)?(?:(?:(?:{_DAY_SAID})[a-z]*\.?,?\s+)?"
    rf"\d{{1,2}}\s+(?:{_MONTH_SAID})[a-z]*\.?"
    rf"(?:\s+\d{{4}})?|(?:{_MONTH_SAID})[a-z]*\s+\d{{4}}|(?:19|20)\d{{2}})\s*,?)?"
    r"\s*,?\s*(?P<open>[:—–]|the interview was with|with)?\s*(?P<listed>.+?)"
    rf"(?:\s+(?P<tail>{_PRESENT_THERE}))?", re.I)
_PRESENT_ENDING = re.compile(
    rf"(?P<listed>.+?)\s+(?P<tail>(?:{_PRESENT_THERE})\s+(?:last time|(?:at |in )?the last "
    r"interview))", re.I)
_PRESENT_ITEMS = re.compile(r"(?:\s*[,;]\s*(?:and\s+)?|\s+and\s+|\s*&\s*)(?![^()]*\))", re.I)
_PRESENT_ITEM = re.compile(r"(?:(?:both|all|the)\s+)*(?P<who>[^()]+?)(?:\s*\((?P<paren>[^()]*)\)"
                           r"|\s+as\s+(?:the\s+)?(?P<role>.+?)|\s+[—–-]\s+(?P<dash>.+?))?", re.I)
#: 680: what a sentence cites its participants to, a file with no line and the fact's own name too
_PRESENT_CITE = re.compile(r"[ \t]*\[(?:[^\]\[]*\.(?:md|json)[^\]\[]*|fact_[^\]\[]*)\]")
#: 680 (23's r1 amend): a date beside the frame that `_why` checks against the lines read: a day and
#: a month, alone; any other `when` ("in March 2024", "(after the 2024 outage)") is always taken out
_PRESENT_DATE = re.compile(rf"[\s,(]*(?:(?:on|in)\s+)?{DATE.pattern}[\s,)]*", re.I)
#: 655: hours a sentence says in days beside them, "72 h (3 days)"
_DAYS_BESIDE = re.compile(r"\b(\d+)\s*(?:h|hours?)\s*\((\d+)\s*days?\)", re.I)
#: 657 (667): a count said in days ("3 days")
_DAYS_SAID = re.compile(r"(?<![\d.,])(\d+)\s*days?\b", re.I)
#: 657: a speaker's turn in an interview ("Franziska Dohm: Image?")
_TURN = re.compile(r"^([^:\n]{1,80}):\s")
#: P19: money
MONEY = re.compile(r"€|\beuros?\b|\bEUR\b", re.I)

#: 530's rule on a model-led turn: what each tool's own result did, so what a sentence may say
#: was done. A drafting tool shows a draft in this reply: it is drafted, created, put together,
#: added to or changed; never placed, saved, sent, moved, booked or blocked (his taps do those)
_DRAFTED = frozenset({"done", "drafted", "created", "put", "added", "updated", "changed"})
DONE_BY: dict[str, frozenset[str]] = {
    "letter": _DRAFTED, "invitation": _DRAFTED,
    "impact_chart": frozenset({"done", "created", "added", "updated", "changed"}),
}
#: a claim of placing or sending: never a tool's on this path
PLACED = re.compile(r"\bin(?:to)? (?:the |your |his )?drafts\b|\bmailbox\b|\bcalendar\b|\bsent\b"
                    r"|\bplaced\b|\bsaved\b|\bmoved\b|\brescheduled\b|\bblocked\b|\bbooked\b", re.I)
#: the probe's note 4: "Nothing has been sent" is no claim
NEGATED = re.compile(r"\b(?:nothing|nobody|no one|neither|nor|none|not|never|no)\b|n['’]t\b", re.I)
#: 652: a clause that says a cell was left unrated ("empty" and "blank" of a cell or of an hour a
#: grid leaves, not of a stock), and what denies it
UNRATED = re.compile(r"\bunrated\b|\bnot rated\b|\bleft as ['‘\"“]?[–-]"
                     r"|\b(?:cell|column|row)\b.*\b(?:blank|empty)\b"
                     r"|\b(?:leaves?|left|leaving)\s+(?:\w+\s+)?\d+\s*h(?:ours?)?\s+(?:\w+\s+)?"
                     r"(?:blank|empty)\b", re.I)
_CLAUSES = re.compile(r"[,;]|\b(?:but|so)\b", re.I)
UNRATED_DENIED = re.compile(r"(?:\bnot?|\bnever|\bneither|\bnor|n['’]t|\brather than|\binstead of"
                            r"|\bno longer|\bhardly|\bbarely|\bscarcely|\bfar from)\s+"
                            r"(?:\w+\s+){0,5}?(?:unrated\b|blank\b|empty\b|left as\b)"
                            r"|\bevery horizon\b", re.I)
#: 652: a claim across years or records holds only on two cited files
ACROSS = re.compile(r"\bboth\b|\balways\b|\b(?:each|every|all|two|three|several|many|either"
                    r"|neither)\b(?:\s+\w+){0,2}?\s+(?:years?|records?|cycles?|grids?|interviews?|files?"
                    r"|categor(?:y|ies)|class(?:es)?)\b", re.I)
#: 652: said uncited, it says last year or the prior record
LAST_RECORD = re.compile(r"\blast year\b|\bprior (?:record|grid|cycle)\b", re.I)
_RATING = "|".join((*core.GRID_LEVELS, r"\d"))
NO_TOOL = "no tool"
#: a claim no tap reads still says who did it ("I have drafted", "nemo moved", "has been sent",
#: "is now", "Done —"); a fact about the files ("the grid changed") is no claim
ACTED = re.compile(r"(?:\b(?:I|nemo|we)(?:['’]ve)?(?:\s+(?:have|has|had|just|now|also|already))*"
                   r"|\b(?:has|have) been|\b(?:is|are) now|^\W*)\s*" + core.CLAIMED.pattern, re.I)

#: a sentence leaning on the one before it for its subject (B2's "It is the only overdue BIA")
_PRONOUN = re.compile(r"^\W*(?:It|Its|It's|This|That|These|Those|They|Their|Both)\b")
#: 668: a short line that only points back at the sentence before it: a step (`_STEP`) on "him",
#: "it", "one" … ("Ask him directly."), an "Ask X to name one", or a question on one ("Can he
#: attend?", "Who owns it?"). "her deputy", "one to two days" say what they mean; a line's "it" is
#: its own.
_BACK = r"(?:(?:him|them)\b|(?:her|it)(?=\W*$|\s+(?:directly|now|today|before|by|about|whether" \
        r"|if|to|for|with)\b)|one(?=\W*$|\s+(?:before|by)\b))"
_POINTS_BACK = re.compile(
    rf"^\W*(?:\w+\s+{_BACK}|Ask\s+(?:(?!and\b)\w+\s+){{1,6}}?to\s+\w+\s+{_BACK})")
_QUESTION_BACK = re.compile(
    r"^\W*(?:(?:Is|Are|Was|Were|Did|Does|Do|Has|Have|Can|Could|Will|Would|Should|Who|What|When"
    r"|Where|Why|How|Which)\s+(?:he|she|they)\b|.*\b(?:him|her|them|it)\W*$)")
FOLLOW_ON_WORDS, FOLLOW_ON_QUESTION = 12, 6
#: a line that labels what follows it (A2's gap labels): ends on a colon, or is a heading
_LABEL = re.compile(r"(?::\W*$)|^\s*#")

#: the reasons a drop is recorded with
NO_CITE = "it states {facts} with no [file:line] cite"
NO_LINE = "it cites {path} with no line: a cite is [file:line]"
NOT_READ = "it cites {path}:{n}, a line not read this turn"
NOT_HELD = "the line it cites does not hold {facts}"
#: 655: a cite whose line holds nothing the sentence says, where a fact result of the turn holds
#: its figure: taken out of the sentence and recorded, never a cut (49's ruling)
CITE_MISS = NOT_HELD + "; a fact result of this turn does, so the cite was taken out"
_CITE_MISS_SAID = re.compile(re.escape(CITE_MISS).replace(re.escape("{facts}"), ".+"))
#: 680: who was there last time, as `fact_last_participants` holds it
NO_PARTICIPANTS = ("it says who was there last time with no fact_last_participants result this "
                   "turn and no line holding them")
NOT_THERE = "{name}: not who was there last time, by this turn's fact_last_participants result"
PRESENT_LINE = "who they say was there last time"
#: 680: the interview's date is no value of the result (the ticket's Not in): never lent, a note
DATE_OUT = "no line it read holds the last interview's date, and the participants result does " \
    "not: taken out"
DENIES_CODE = "it says this is not stated, but code holds it: {what}"
SAYS_ABSENT = "it says something does not exist; the files only name none: say 'not named' or " \
    "'not stated'"
FALSE_THRESHOLD = "it says no {cls} impact until {hour}, but the cited row {first}"
NOT_SPOF = "it calls {resource} a single point of failure, but the register does not flag it: " \
    "a workaround is named, or no gap"
PAIR_OFF = "{pair}: it says {claimed}, but the cited row holds {fact} as {other}"
CLAIMED_DONE = "it says something was done that no tool did this turn"
DENIED = "it denies the room a tool it has"
NO_SUBJECT = "its subject went with the sentence before it"
FOLLOWS_CUT = "it only follows the sentence before it, which went"
NO_LABEL = "its label was dropped"
SHORTENED = "it leaves out {items} of {what}, the list code handed"
COUNT_OFF = "it says {said} {what}, but code counts {count}"
TAP_OFF = "it names the tap {tap!r}, and no tap of that name is drawn"
NOT_QUOTED = "it quotes {quote!r}, which the line it cites does not hold"
NO_QUOTES = "its quotes were all taken out"
RETRY_CHANGED = "the retry changed {path}, which had passed; nemo kept it as the first try had it"
#: 660: a list holding failed items, sent again beyond them: its fix is taken, nothing "had passed"
RETRY_FIX = "the retry's fix to a failed item of {path} was taken"
RETRY_OVER = ("the retry changed {path} beyond its failed items; "
              "nemo kept it as the first try had it")
#: 761: the retry's rows for the list go on to the check; nothing else of its change to the list
RETRY_ROWS = ("the retry's rows for the list code handed went on to the check; "
              "the rest of its change to {path} nemo kept as the first try had it")
#: 536 (488, his standing rule): a graph answer is at most three plain lines, then code's link;
#: 632: a line naming a must-cover item the drawn graph shows is not one of them
GRAPH_LINES = 3
GRAPH_LINES_REASON = "a graph answer takes at most {n} plain lines; nemo kept the first {n}"
#: 536, 544's named day: only the interview of the day his line names is the answer's evidence
OTHER_DAY = "it draws on {path}:{n}, an interview of another day than the one he named"


@dataclass
class Checked:
    """What the stack let stand: the text, each drop with its reason (t532's `drops` shape), the
    must-cover items it misses (recorded, never appended), what it refuses outright (a shortened
    code list), the taps of the tools a dropped sentence claimed or denied."""

    text: str
    drops: list[dict[str, str]] = field(default_factory=list)
    must_cover_misses: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    claimed: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)


@dataclass
class Room:
    """What every check reads beside the text: the room, the turn's reads, his line (and the
    lines before it), the activity the turn is about, and the tools this turn ran."""

    folder: Path
    read: Read
    line: str
    said: list[str] = field(default_factory=list)
    activity: str | None = None
    ran: list[str] = field(default_factory=list)
    offers: list[Offer] = field(default_factory=list)
    #: facts code checks elsewhere (a chart caption's own classes and years: the call's arguments)
    known: set[str] = field(default_factory=set)
    #: 607 (Amend 2): a fact tool's values by the activity it read them for ("" the whole company)
    known_by: dict[str, set[str]] = field(default_factory=dict)
    #: 645: what a fact tool counted this turn, by the activity it read and the thing counted
    #: (`COUNTED_AS`)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    #: 680: what `fact_last_participants` returned this turn, by the activity it read: (function,
    #: role)
    participants: dict[str, list[list[str]]] = field(default_factory=dict)
    #: 652: what `fact_unrated_last_year` returned this turn, by the activity it read: the hours of
    #: last year's grid left unrated, by class
    unrated: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    #: 607: the taps drawn under the text, where code draws them (a tap's narration)
    taps: list[str] | None = None
    #: 720: the values handed this turn from a row written for the demo pack (`marked_values`)
    marked: set[str] = field(default_factory=set)
    #: 536: the interviews of the day his line names, where it names one that holds any: only
    #: their sentences stand (544's rule, on the model-led path)
    day: tuple[str, ...] = field(default_factory=tuple)

    @functools.cached_property
    def resource_words(self) -> set[tuple[str, str]]:
        """720: the word pairs of each register row some activity uses: its name, never a control's
        words ("Microsoft Teams"), read only where a marked value was handed."""
        return {p for a in drafting.read_register(self.folder).values()
                if isinstance(a, dict) and a.get("consumers")
                for p in _word_pairs(str(a.get("name") or ""))}

    @functools.cached_property
    def today(self) -> datetime.date | None:
        return core.story_today(self.folder)

    @functools.cached_property
    def method(self) -> dict[str, Any]:
        return dict(walk._method(self.folder))

    @functools.cached_property
    def classes(self) -> list[str]:
        return [str(s.get("name") or s["id"]) for s in self.method.get("scenarios") or []]


# ── the evidence a cite points at ───────────────────────────────────────────────────────────────
@functools.lru_cache(maxsize=16)
def _objects(text: str) -> tuple[tuple[int, int, int, int], ...]:
    """Every JSON object in `text`: (its first line, its last line, its start, its end)."""
    out: list[tuple[int, int, int, int]] = []
    opened: list[tuple[int, int]] = []
    line, quoted, escaped = 1, False, False
    for i, ch in enumerate(text):
        if quoted:
            escaped, quoted = (False, True) if escaped else (ch == "\\", ch != '"')
        elif ch == '"':
            quoted = True
        elif ch == "{":
            opened.append((line, i))
        elif ch == "}" and opened:
            first, start = opened.pop()
            out.append((first, line, start, i + 1))
        line += ch == "\n"
    return tuple(out)


def _flat(value: Any, key: str, group: str) -> list[Cell]:
    """A row's every scalar as (its key, its value, the activity its object is for)."""
    if isinstance(value, dict):
        group = str(value.get("department") or group)
        return [c for k, v in value.items() for c in _flat(v, str(k), group)]
    if isinstance(value, list):
        return [c for v in value for c in _flat(v, key, group)]
    return [(key.lower(), str(value), group)]


def _json_row(text: str, n: int) -> list[Cell]:
    """S0 note 5: the whole row object spanning line `n` (the innermost object holding it), with
    the scalars of the rows around it (a consumer's resource: its name, its owner), never the
    file's own top level."""
    spans = [o for o in _objects(text) if o[0] <= n <= o[1]]
    if not spans:
        return []
    *outer, inner = sorted(spans, key=lambda o: o[2])
    cells = _flat(json.loads(text[inner[2]:inner[3]]), "", "")
    for o in outer[1:]:
        row = json.loads(text[o[2]:o[3]])
        cells += [(str(k).lower(), str(v), OUTER) for k, v in row.items()
                  if not isinstance(v, (dict, list))]
    return cells


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _header(lines: list[str], n: int) -> list[str] | None:
    """The header of the Markdown table line `n` sits in, below it its separator; None where line
    `n` is no table row."""
    at = n - 1
    while at > 0 and lines[at - 1].lstrip().startswith("|"):
        at -= 1
    if not lines[n - 1].lstrip().startswith("|") or n - 1 <= at + 1 or \
            not re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[at + 1]):
        return None
    return [h.lower() for h in _cells(lines[at])]


def _named_cell(head: str, cell: str) -> list[Cell]:
    """A cell under its header's name; the plan's Status cell keeps its "next review due" part as
    that column's (P13)."""
    if not head.startswith("status"):
        return [(head, cell, "")]
    due = re.search(r"\bnext review due\b(.*)", cell, re.I)
    return [("status", cell[:due.start()], ""), ("review due", due[1], "")] if due else \
        [("status", cell, "")]


def _table_row(lines: list[str], n: int) -> list[Cell] | None:
    """A Markdown table row as its cells under their header's names; a two-column "Field | Value"
    table names each value by its field. None where line `n` is no table row."""
    head = _header(lines, n)
    if head is None:
        return None
    row = _cells(lines[n - 1])
    if head[:2] == ["field", "value"] and len(row) >= 2:
        return [(row[0].lower(), row[1], "")]
    return [c for h, x in zip(head, row, strict=False) for c in _named_cell(h, x)]


@functools.lru_cache(maxsize=64)
def _file(folder: Path, path: str) -> str:
    return (folder / path).read_text(encoding="utf-8", errors="replace")


def evidence(folder: Path, path: str, n: int) -> list[Cell]:
    """What a cite of line `n` of `path` puts behind a sentence: a JSON file's whole row, a table
    row's named cells, else the line itself."""
    text = _file(folder, path)
    if path.endswith(".json"):
        return _json_row(text, n)
    lines = text.splitlines()
    if not 0 < n <= len(lines):
        return []
    return _table_row(lines, n) or [("", lines[n - 1], "")]


def _resolve(path: str, read: Read) -> str:
    """A cite's path as read: the whole path, else the one read path ending in it."""
    paths = {p for p, _ in read}
    if path in paths:
        return path
    ends = {p for p in paths if p.endswith("/" + path.lstrip("/"))}
    return ends.pop() if len(ends) == 1 else path


def each_cite(text: str) -> str:
    """640 (Amend 1): each bracket of several cites as one bracket a cite."""
    return _SEVERAL.sub(lambda m: " ".join(f"[{c[0].strip()}]" for c in re.finditer(
        _ONE_CITE, m[1])), text)


def cites(sentence: str, read: Read) -> list[tuple[str, int]]:
    """Every (path, line) a sentence cites, each range and list opened up."""
    out: list[tuple[str, int]] = []
    for m in CITE.finditer(each_cite(sentence)):
        path = _resolve(m["path"].strip(), read)
        for part in m["at"].split(","):
            a, _, b = re.sub(r"\s", "", part).replace("–", "-").partition("-")
            out += [(path, k) for k in range(int(a), int(b or a) + 1)]
    return out


# ── one sentence ────────────────────────────────────────────────────────────────────────────────
def _bare(sentence: str) -> str:
    return _LEAD.sub("", _CITES.sub(" ", each_cite(sentence)))


def _own(sentence: str) -> str:
    """The sentence's own words: a quotation is the files' evidence, never the model's claim."""
    return core.QUOTED.sub(" ", _bare(sentence))


@functools.lru_cache(maxsize=8)
def _names(folder: Path) -> re.Pattern[str]:
    """The room's own names that may hold a digit (a resource, an activity): no figure in them."""
    said = [str(r.get("name")) for r in drafting.read_register(folder).values()
            if isinstance(r, dict) and r.get("name")] + [
        core.map_name(folder, a) for a in walk.processes(folder)]
    return re.compile("|".join(re.escape(x) for x in sorted(
        {x for x in said if re.search(r"\d", x)}, key=len, reverse=True)) or r"(?!)")


def facts(sentence: str, classes: Iterable[str] = (), folder: Path | None = None) -> list[str]:
    """The figures, dates and impact classes a sentence states, its cites, list marks and the
    room's own names and a number inside a name (647) aside."""
    bare = _bare(sentence)
    bare = _names(folder).sub(" ", bare) if folder else bare
    bare = _iso(IN_NAME.sub(lambda m: f"{m['name'] or ''} ", bare))
    dated = [f"{m['day']} {m['month']}" for m in DATE.finditer(bare)]
    rest = DATE.sub(lambda m: f" {m['year'] or ''} ", bare)
    return list(dict.fromkeys([
        *dated, *NUMBER.findall(HOUR.sub(" ", rest)),
        *(c for c in classes if re.search(rf"\b{re.escape(c)}\b", bare, re.I))]))


def _iso(text: str) -> str:
    """607: each ISO date as the date in words ("2025-02-13" is 13 Feb 2025)."""
    return ISO_DATE.sub(lambda m: f"{int(m['day'])} {_MONTHS[int(m['month']) - 1]} {m['year']}",
                        text)


def _holds(value: str, fact: str) -> bool:
    if (m := re.fullmatch(r"(\d+) (\w+)", fact)) and m[2] in _MONTHS:
        return re.search(rf"(?<!\d){m[1]}\s+{m[2]}", _iso(value), re.I) is not None
    if fact[0].isdigit():
        return re.search(rf"(?<![\d.,]){re.escape(fact)}(?![\d]|[.,]\d)", value) is not None
    return fact.lower() in value.lower()


def _member(fact: str, cells: list[Cell], pair: str, own: str,
            members: dict[str, tuple[re.Pattern[str], tuple[str, ...]]],
            named: list[str]) -> str | None:
    """One figure against a pair: held in another member's column only (the pair), or, with an
    activity named, held in its own column only on another activity's row (P3)."""
    mine = members[own][1]
    others = {c: m for m, (_, cs) in members.items() if m != own for c in cs}
    undated = DATE.fullmatch(fact) is None  # 760: a bare figure is no day of a date in a cell
    holders = [(col, grp) for col, value, grp in cells if _holds(
        DATE.sub(lambda m: f" {m['year'] or ''} ", _iso(value)) if undated else value, fact)]
    if holders and not any(col in mine for col, _ in holders):
        other = next((others[col] for col, _ in holders if col in others), None)
        return PAIR_OFF.format(pair=pair, claimed=own, fact=fact, other=other) if other else None
    if named and holders and not any(col in mine and grp in ("", OUTER, *named)
                                     for col, grp in holders):
        return PAIR_OFF.format(pair="P3", claimed=f"{own} for {', '.join(named)}", fact=fact,
                               other=f"{own} of another record")
    return None


def _columns(bare: str, cells: list[Cell], room: Room) -> str | None:
    """P1, P2, P3, P13: a figure the sentence's words put in one member of a pair that the cited
    row holds only in another; and an RTO said with an activity, held only on another's row."""
    named = core.named_in(room.folder, bare) or []
    for pair, members in COLUMN_PAIRS:
        claimed = [m for m, (said, _) in members.items() if said.search(bare)]
        for fact in facts(bare, folder=room.folder) if len(claimed) == 1 else []:
            if why := _member(fact, cells, pair, claimed[0], members, named):
                return why
    return None


def method_reading(room: Room, activity: str) -> str | None:
    """P4: the MTPD the method reads off this year's grid: the earliest horizon where the worst
    class reaches the threshold (None where no grid is stated this year)."""
    grid, _ = core.this_years_scores(room.folder, activity, room.method)
    if not grid:
        return None
    return str(impact.mtpd_reading(grid, room.method)["horizon"])


def _method(bare: str, room: Room) -> str | None:
    if not BY_METHOD.search(bare):
        return None
    activity = next(iter(core.named_in(room.folder, bare) or []), room.activity)
    reading = method_reading(room, activity) if activity else None
    said = _HOURS.findall(bare)
    if said and (reading is None or f"{said[0]} h" != reading):
        return PAIR_OFF.format(pair="P4", claimed="the method's reading", fact=f"{said[0]} h",
                               other=f"a stated figure (the method reads {reading or 'none'})")
    return None


def _file_year(room: Room, path: str) -> str | None:
    """P5, P6: "this" for a file of the story's year, "last" for the prior cycle's or an older
    interview; None for a file with no year (the plan, the register)."""
    if path.startswith("08_Prior-Cycle/"):
        return "last"
    dated = re.search(r"^date: (\d{4})", _file(room.folder, path)[:800], re.M) \
        if path.startswith(interview.INTERVIEWS) else None
    if not dated or room.today is None:
        return None
    return "this" if int(dated[1]) == room.today.year else "last"


def _years(bare: str, cited: list[tuple[str, int]], room: Room) -> str | None:
    claims = "this" if THIS_YEAR.search(bare) and not LAST_YEAR.search(bare) else \
        "last" if LAST_YEAR.search(bare) and not THIS_YEAR.search(bare) else None
    years = {y for p, _ in cited if (y := _file_year(room, p))}
    if claims and years and claims not in years:
        pair = "P6" if _SCORE.search(bare) else "P5"
        return PAIR_OFF.format(pair=pair, claimed=f"{claims} year", fact="it",
                               other=f"{years.pop()} year's")
    return None


def _speaker(bare: str, cited: list[tuple[str, int]], room: Room) -> str | None:
    """P8: a figure for this year stands on the speaker's answer, never on the interviewer's
    question or sum-up."""
    lines = [(p, room.read.get((p, n)) or "") for p, n in cited
             if p.startswith(interview.INTERVIEWS)]
    if not lines or not NUMBER.search(bare) or not any(
            w.search(bare) for w in (_SCORE, _HOURS, RTO, MTPD, RPO)):
        return None
    by = _facilitator(_file(room.folder, lines[0][0]))
    asks = [x for _, x in lines if _SUM_UP.match(x) or (by and x.startswith(f"{by}:"))]
    if len(asks) == len(lines):
        return PAIR_OFF.format(pair="P8", claimed="a score", fact="it",
                               other="the interviewer's question or sum-up")
    return None


def _facilitator(text: str) -> str | None:
    """The interviewer an interview's head names."""
    by = re.search(r"^facilitator: (.+)$", text[:800], re.M)
    return by[1] if by else None


def _asked(room: Room, cited: list[tuple[str, int]]) -> list[str]:
    """657: the interviewer's question each cited interview answer (another speaker's turn)
    replies to: the nearest line above it the interviewer says, over the answers between, where it
    asks ("?")."""
    out: list[str] = []
    for p, n in cited:
        if not (p.startswith(interview.INTERVIEWS + "/") and p.endswith(".md")):
            continue
        text = _file(room.folder, p)
        lines, by = text.splitlines(), _facilitator(text)
        said = _TURN.match(lines[n - 1]) if by and 0 < n <= len(lines) else None
        if not said or said[1] == by:
            continue
        for x in reversed(lines[:n - 1]):
            if not x.strip():
                continue
            if not (turn := _TURN.match(x)):
                break
            if turn[1] == by:
                out += [x] if "?" in x else []
                break
    return out


def _in_hours(bare: str, cells: list[Cell]) -> tuple[str, set[str]]:
    """657 (667): each day count the cited cells hold in hours (24 h = 1 day: "3 days" over
    "72 h") said as those hours, for the pair checks; and the day counts so held, where the
    sentence says that number no other way."""
    held: set[str] = set()
    cited = {h for _, v, _ in cells for h in re.findall(r"(?<![\d.,])(\d+)\s*h(?:ours?)?\b", v)}

    def hours(m: re.Match[str]) -> str:
        h = str(24 * int(m[1]))
        if h not in cited:
            return m[0]
        held.add(m[1])
        return f"{h} h"
    said = _DAYS_SAID.sub(hours, bare)
    return said, {d for d in held if not re.search(rf"(?<![\d.,]){d}(?![\d]|[.,]\d)", said)}


def _class_in(text: str, room: Room) -> list[str]:
    """672: the impact classes `text` names ("Financially", "Impact health" too)."""
    return [c for c in room.classes if re.search(rf"\b{re.escape(c.split()[0])}", text, re.I)]


def _scale(room: Room) -> dict[str, str]:
    """672: the method's level words by score ("4" is "high")."""
    return {str(k): str(v).lower() for k, v in core._scale_words(room.method).items()}


def _level_word(room: Room) -> str:
    return "|".join(re.escape(w) for w in sorted(_scale(room).values(), key=len, reverse=True))


#: 672: a step of a schedule: (its hour, its level, whether it holds on after its hour)
Step = tuple[int, str, bool]


def _at_hour(clause: str, room: Room) -> tuple[int, re.Match[str]] | None:
    """672: the hour a clause puts a level at ("at 72 h", "from eight hours", "after a day", "at
    168" where 168 h is a horizon), in hours, and where the clause says it."""
    m = re.search(r"\b(?P<by>at|from|after)\s+(?:(?P<n>\d+)(?![\d:.,])(?:\s*(?P<unit>h\b|"
                  r"hours?\b|days?\b|weeks?\b))?|(?:a|one)\s+(?P<one>day|week)\b)", clause, re.I)
    if not m:
        return None
    if m["one"]:
        return (24 if m["one"].lower() == "day" else 168), m
    if not m["unit"] and f"{m['n']} h" not in (room.method.get("time_horizons") or []):
        return None
    return int(m["n"]) * {"h": 1, "d": 24, "w": 168}[(m["unit"] or "h")[0].lower()], m


def _said_levels(text: str, room: Room, carry: str | None = None
                 ) -> list[tuple[str, int, str | None, bool]]:
    """672: (class, hour, level or None, held on after it: "from", "after") of each clause that
    puts a class at an hour: the class the clause names, else the one named last before it
    (`carry` before the first); the level word nearest the hour; never a clause on last year."""
    out: list[tuple[str, int, str | None, bool]] = []
    word = re.compile(rf"\b({_level_word(room)})\b", re.I) if _scale(room) else None
    for clause in re.split(r"[,;:!?]|\.(?!\d)|\b(?:and|but|then)\b", _figures(text)):
        named = _class_in(clause, room)
        carry = named[0] if len(named) == 1 else None if named else carry
        at = _at_hour(clause, room)
        if carry is None or at is None or LAST_YEAR.search(clause) or any(
                p.search(clause) for p in (RTO, MTPD, RPO)):
            continue
        hour, m = at
        level = min(word.finditer(clause) if word else [], default=None, key=lambda w: min(
            abs(w.start() - m.end()), abs(m.start() - w.end())))
        out.append((carry, hour, level[1].lower() if level else None,
                    m["by"].lower() != "at"))
    return out


def _score_row(value: str, room: Room) -> list[Step] | None:
    """672: an impact row ("Impact legal: 1 h 1, … 72 h 4", "In words: 1 h none, …") as its
    steps; None where `value` is no such row."""
    scale = _scale(room)
    found = re.findall(rf"(?<![\d.,])(\d+)\s*h\s+(\d|{_level_word(room)})\b", value,
                       re.I) if scale else []
    return [(int(h), scale.get(x, x.lower()), True) for h, x in found] if len(found) >= 3 \
        else None


def _schedules(cited: list[tuple[str, int]], room: Room) -> list[tuple[str, list[Step]]]:
    """672: the levels each cited line gives a class by hour: an impact row's under the class it
    names; an answer's under the class each clause names, else the one its question names
    (657's `_asked`)."""
    out: list[tuple[str, list[Step]]] = []
    for p, n in cited:
        asked = [c for q in _asked(room, [(p, n)]) for c in _class_in(q, room)]
        for _, value, _ in evidence(room.folder, p, n):
            value = _figures(value)
            if (row := _score_row(value, room)) is not None:
                named = _class_in(value, room)
                out += [(named[0], row)] if len(named) == 1 else []
                continue
            by: dict[str, list[Step]] = {}
            for cls, hour, level, on in _said_levels(value, room, asked[0] if len(asked) == 1
                                                     else None):
                if level:
                    by.setdefault(cls, []).append((hour, level, on))
            out += list(by.items())
    return out


def _level_at(steps: list[Step], hour: int) -> str | None:
    """The level a schedule gives at `hour`: its last step at or before it, where that step holds
    on to `hour` ("from", "after", a row's, or one a later step follows; "Low at 72 hours" alone
    gives no level at 168 h)."""
    ordered = sorted(steps, key=lambda s: s[0])  # stable: steps at one hour keep the said order
    before = [s for s in ordered if s[0] <= hour]
    if not before:
        return None
    h, level, on = before[-1]
    return level if h == hour or on or len(before) < len(ordered) else None


def _onsets(steps: list[Step], room: Room) -> set[int]:
    """The hours a schedule's level changes at (its first step unless at the lowest level)."""
    out, last = set(), _scale(room).get("1")
    for h, level, _ in sorted(steps, key=lambda s: s[0]):
        if level != last:
            out.add(h)
        last = level
    return out


#: 733: what `_said_levels` splits a sentence on, so a "was" part's clause is the one P20 reads
_CLAIM_CLAUSE = re.compile(r"[,;:!?]|\.(?!\d)|\b(?:and|but|then)\b")
#: 733: "was none at 72 h and 168 h, now high at both", "moved from none at 72 h to high", "goes
#: from none at 72 h last year to high", "was none from 8 h on, now low at 8 h, medium at 24 h"; the
#: now part ends the clause, so no hour past it goes unread
_AN_HOUR = r"\d+\s*h(?:ours?)?\b"
_HOURS_SAID = rf"{_AN_HOUR}(?: and {_AN_HOUR})*"
_WAS_NOW = (r"\b(?:was|(?:moved|goes) from) (?P<was>{w}) (?:at (?P<at>" + _HOURS_SAID
            + r")|from (?P<on>" + _AN_HOUR + r") on)(?: last year)?,? (?:now|to) "
            r"(?P<now>(?:{w})(?: at (?:both|" + _HOURS_SAID + r"))?(?:, (?:{w}) at "
            + _HOURS_SAID + r")*)(?=(?: this year)?\s*(?:$|[.;:!?)]|\s[-–—]\s))")


def _last_years_grid(said: str, cited: list[tuple[str, int]], room: Room) -> dict[str, Any]:
    """733: last year's grid of the one activity a sentence is about, where its cited interviews
    are that activity's too (so last year and this year are one activity's), else nothing."""
    about = core.named_in(room.folder, said) or ([room.activity] if room.activity else [])
    if len(about) != 1:
        return {}
    spoken = {p for p, _ in cited if any(p.startswith(f"{h}/") for h in interview.HOMES)}
    if not spoken or spoken - {p for h in interview.HOMES
                               for p in interview.paths_about(room.folder, h, about[0])}:
        return {}
    return core.last_year(room.folder, about[0]).get("grid") or {}


def _now_levels(m: re.Match[str], hours: list[int], word: str) -> list[tuple[str, int]]:
    """733: (level, hour) of each thing a "now" part says: at the hours it names, else at `hours`;
    "both" is those hours only where they are two."""
    out: list[tuple[str, int]] = []
    for level, at in re.findall(rf"({word})(?: at (both|{_HOURS_SAID}))?", m["now"], re.I):
        own = [int(h) for h in _HOURS.findall(at)]
        out += [(level.lower(), h) for h in own or (
            hours if not at or len(hours) == 2 else [])]
    return out


def _without_true_was(said: str, cited: list[tuple[str, int]], room: Room) -> str:
    """733: `said` without each "was" part that is true, the one reading P20 has no business with:
    it opens its clause (past the class it is on, so no denial, condition or other period governs
    it), last year's record gives that level for that class at each hour it names, each later one
    too for "from N h on" (a "–" gives none), and this year's cited row gives each level of the
    "now" part at its hours, the hours the "was" names among them. Where code cannot read last
    year, `said` as it is. The rest of it is read as ever."""
    word = _level_word(room)
    found = list(re.finditer(_WAS_NOW.format(w=word), said, re.I))
    grid = _last_years_grid(said, cited, room) if found else {}
    rows = _schedules([c for c in cited if _file_year(room, c[0]) != "last"], room) if grid else []
    opens = "|".join(re.escape(c) for c in room.classes)
    for m in reversed(found if grid else []):
        stop = m.end("at") if m["at"] else m.end("on")
        read = _said_levels(said[:stop], room)
        named = [int(h) for h in _HOURS.findall(m["at"] or m["on"])]
        before = _CLAIM_CLAUSE.split(said[:m.start()])[-1]
        if not read or read[-1][1:3] != (named[0], m["was"].lower()) or not re.fullmatch(
                rf"\W*(?:(?:the|its)\s+)?(?:(?:{opens})(?:\s+impact)?)?\W*", before, re.I):
            continue
        cls = read[-1][0]
        row = grid.get(cls, {}).get("cells", {})
        cells = {int(c[1]): v.lower() for k, v in row.items() if (c := re.fullmatch(r"(\d+) h", k))}
        if m["on"] and len(cells) != len(row):
            continue  # a horizon that is no plain hour: "from N h on" cannot be read
        hours = named + [h for h in cells if m["on"] and h > named[0]]
        now = _now_levels(m, hours, word)
        if all(cells.get(h) == m["was"].lower() for h in hours) \
                and set(named) <= {h for _, h in now} and all(
                    level in {g for c, s in rows if c == cls and (g := _level_at(s, h))}
                    for level, h in now):
            said = f"{said[:m.start()]} {said[stop:]}"
    return said


def _levels(said: str, cited: list[tuple[str, int]], room: Room) -> str | None:
    """672: P20, a level said for a class at an hour is the level the cited lines give that class
    there, where they give one, a true "was" part apart (733, `_without_true_was`); P21, an hour
    said with a class (no level) is that class's onset, where it is not and another cited class's
    it is. Dropped, never rewritten."""
    claims = _said_levels(said, room)
    known = _schedules(cited, room) if claims else []
    if any(level for _, _, level, _ in claims) and (
            rest := _without_true_was(said, cited, room)) != said:
        claims = _said_levels(rest, room)
    for cls, hour, level, _ in claims:
        mine = [s for c, s in known if c == cls]
        if level:
            given = {g for s in mine if (g := _level_at(s, hour))}
            if given and level not in given:
                return PAIR_OFF.format(pair="P20", claimed=f"{cls} {level} at {hour} h",
                                       fact=f"{cls} at {hour} h", other=" or ".join(sorted(given)))
        elif mine and not any(hour in _onsets(s, room) for s in mine) and (other := next(
                (c for c, s in known if c != cls and hour in _onsets(s, room)), None)):
            return PAIR_OFF.format(pair="P21", claimed=f"{cls} at {hour} h", fact=f"{hour} h",
                                   other=other)
    return None


def _plan_rows(folder: Path) -> list[list[str]]:
    lines = _file(folder, core.PROGRAMME_PLAN).splitlines()
    rows = [_table_row(lines, n) for n in range(1, len(lines) + 1)]
    return [[v for _, v, _ in r] for r in rows if r and re.fullmatch(r"\d+\.\d+", r[0][1])]


def _date(said: str, year: int) -> datetime.date | None:
    m = DATE.search(said)
    if not m:
        return None
    try:
        return datetime.date(int(m["year"] or year), _MONTHS.index(m["month"]) + 1, int(m["day"]))
    except ValueError:
        return None


def _heard_this_year(folder: Path, year: int) -> set[str]:
    """The activities with an interview dated in the story's year."""
    heads = [_file(folder, f"{interview.INTERVIEWS}/{p.name}")[:800]
             for p in (folder / interview.INTERVIEWS).glob("*.md")]
    return {m[1] for h in heads if re.search(rf"^date: {year}", h, re.M)
            and (m := re.search(r"^department: (\S+)", h, re.M))}


def _count_pairs(bare: str, room: Room) -> list[tuple[str, tuple[str, re.Pattern[str], int],
                                                     tuple[str, re.Pattern[str], int]]]:
    """P9-P12 as code counts them, for what the sentence is about: (pair, each member's name, its
    words, its count)."""
    pairs = []
    activity = next(iter(core.named_in(room.folder, bare) or []), room.activity)
    if re.search(r"\binterviews?\b", bare, re.I) and activity and (
            draft := core.draft_for(activity, "glm", room.folder)):
        held = draft.get("interviews") or []
        pairs.append(("P9", ("talk about it", TALK_ABOUT, sum(1 for i in held if i.get("keep"))),
                      ("read", READ_WORD, len(held))))
    if room.today and re.search(r"\b(?:BIAs?|reviews?|interviews?|process|activit)", bare, re.I):
        year, plan = room.today.year, _plan_rows(room.folder)
        late = [r for r in plan if r[-1].lower().startswith("overdue")]
        pairs += [
            ("P10", ("reviewed this year", REVIEWED_THIS,
                     sum(1 for r in plan if re.search(rf"\breviewed\b.*\b{year}\b", r[-1]))),
             ("without an interview this year", NO_INTERVIEW,
              len(set(walk.processes(room.folder)) - _heard_this_year(room.folder, year)))),
            ("P11", ("overdue", OVERDUE, len(late)),
             ("overdue by more than a year", OVER_A_YEAR, sum(
                 1 for r in late if (d := _date(r[-2], year)) and (room.today - d).days > 365)))]
    if found := line_reads.resource_row(room.folder, bare):
        register = drafting.read_register(room.folder)
        pairs.append(("P12", ("used directly", USES, len(line_reads.reached(
            room.folder, [found[0]], register))), ("reached", REACHES, len(
                line_reads.reached(room.folder, line_reads.down(register, found[0]),
                                       register)))))
    return pairs


def _claimed_counts(bare: str, room: Room) -> tuple[set[int], str | None]:
    """P9-P12: (the counts the sentence says that are code's count of the member its words claim;
    why it fails where a count it says is the other member's)."""
    bare = YEAR.sub(lambda m: " " if _a_year(m[0], room) else m[0], DATE.sub(" ", _iso(
        bare)))  # 607: a date's day and a year count nothing
    said = {int(n) for n in NUMBER.findall(bare) if n.isdigit()} | {
        k for k, w in enumerate(core.COUNTS) if k and re.search(rf"\b{w}\b", bare, re.I)}
    counts = [(m, int(m[1]) if m[1].isdigit() else SPELLED.index(m[1].lower()) + 1)
              for m in COUNTED.finditer(bare)]
    held: set[int] = set()
    for pair, a, b in _count_pairs(bare, room) if said else []:
        for own, other in ((a, b), (b, a)):
            if not own[1].search(bare) or other[1].search(bare):
                continue
            if own[2] in said:
                held.add(own[2])
            elif other[2] in said:
                return held, PAIR_OFF.format(pair=pair, claimed=own[0], fact=other[2],
                                             other=other[0])
            elif wrong := sorted({n for m, n in counts if n != own[2] and own[1].search(
                    bare[m.start():m.end() + 30])}):  # 607 (rule 11): code's count, of its thing
                return held, COUNT_OFF.format(said=wrong[0], what=own[0], count=own[2])
    return held, None


def _days(bare: str, room: Room) -> str | None:
    """P14 and U2: "today" is the story's day; a weekday said with a date is that date's."""
    year = room.today.year if room.today else 0  # never the clock: a date with no year is unread
    if (m := TODAY.search(bare)) and room.today and _date(m[0], year) != room.today:
        return PAIR_OFF.format(pair="P14", claimed="today", fact=m[0].split(None, 1)[-1],
                               other=f"a day not the story's today ({room.today:%-d %b %Y})")
    for m in WEEKDAY_DATE.finditer(bare):
        day = _date(m[0], year)
        if day and not _WEEKDAYS[day.weekday()].startswith(m["weekday"]):
            return f"it says {m[0]}, but that day is a {_WEEKDAYS[day.weekday()]}"
    return None


def _his_hours(room: Room) -> set[int]:
    said = " ".join([room.line, *room.said])
    return {int(m["h"]) % 12 for m in HOUR.finditer(said)} | {
        int(h) % 12 for h in AT_HOUR.findall(said)}


def _hour(bare: str, room: Room) -> str | None:
    """P15: an hour is only ever his."""
    for m in HOUR.finditer(bare):
        if int(m["h"]) % 12 not in _his_hours(room):
            return PAIR_OFF.format(pair="P15", claimed="an hour", fact=m[0].strip(),
                                   other="an hour he did not give (the files state none)")
    return None


def _why(sentence: str, room: Room, held: bool = False) -> str | None:
    """Why a sentence fails the stack, or None where it stands. A `held` one (a letter's) reads its
    counts in words as figures, and so does the line it cites (589)."""
    sentence = _figures(sentence) if held else sentence
    bare = _own(sentence)
    if room.taps is not None and (tap := _untapped(sentence, room.taps)):
        return TAP_OFF.format(tap=tap)
    if file := FILE_ONLY.search(sentence):
        return NO_LINE.format(path=file["path"].strip())
    cited = cites(sentence, room.read)
    unread = next(((p, n) for p, n in cited if (p, n) not in room.read), None)
    if unread:
        return NOT_READ.format(path=unread[0], n=unread[1])
    if room.day and (other := next(((p, n) for p, n in cited
                                    if p.startswith(interview.INTERVIEWS + "/")
                                    and p not in room.day), None)):
        return OTHER_DAY.format(path=other[0], n=other[1])
    cells = [(col, _figures(v) if held else v, grp)
             for path, n in cited for col, v, grp in evidence(room.folder, path, n)]
    if cited and (quote := _unquoted(sentence, cells)):
        return NOT_QUOTED.format(quote=quote)
    if (m := NONE_UNTIL.search(bare)) and (why := _threshold(m, cells)):
        return why
    rows_counted, why = _rows_counted(bare, room)
    total_counted, off = _total_counted(bare, room)
    if why := why or off or _says_absent(bare, cells, room) or _not_stated(bare, room):
        return why
    if why := (None if held else _present_why(sentence, cited, room)) or _not_spof(bare, room):
        return why
    counted, why = _claimed_counts(bare, room)
    about = core.named_in(room.folder, bare) or ([room.activity] if room.activity else [])
    fact_counted, off = _fact_counts(bare, room, about)
    if why := why or off or _days(bare, room) or _hour(bare, room):
        return why
    return _held(sentence, bare, cited, cells, room, {
        str(n) for n in counted | fact_counted | rows_counted | total_counted}, about)


@dataclass
class _Present:
    """680: a sentence that says who was there last time, its parts (`_PRESENT_FRAMED`), and each
    item of its list."""

    head: str
    when: str
    opening: str
    listed: str
    tail: str
    items: list[str]


def _present(sentence: str, room: Room) -> _Present | None:
    """680: the sentence read as who was there last time: its frame says so, a date in it is a date,
    and at least one item of its list is wholly a person of the room."""
    plain = " ".join(_iso(_PRESENT_CITE.sub("", _bare(sentence)).replace("*", "")).split())
    plain = plain.rstrip(" .?")
    m = _PRESENT_FRAMED.fullmatch(plain) or _PRESENT_ENDING.fullmatch(plain)
    if m is None:
        return None
    parts = m.groupdict(default="")
    if not (parts.get("open") or parts["tail"]) or (parts.get("when") and not (
            DATE.search(parts["when"]) or YEAR.search(parts["when"]))):
        return None
    functions = set(words.people(room.folder).values())
    listed = parts["listed"]
    for f in functions:  # "Head of Fleet and Transport" is one person
        listed = re.sub(re.escape(f), lambda m: m[0].replace(" and ", "\0"), listed, flags=re.I)
    items = [i.replace("\0", " and ") for i in _PRESENT_ITEMS.split(listed) if i.strip()]
    people = {f.lower() for f in functions}
    opened_with = parts.get("open", "").lower() == "with"  # "with A and B, the team reviewed …"
    if not (all if opened_with else any)(_person(i, room) in people for i in items):
        return None
    return _Present(parts.get("head", ""), parts.get("when", ""), parts.get("open", ""),
                    parts["listed"], parts["tail"], items)


def _person(item: str, room: Room) -> str:
    """680: the function an item of the list says, in the words of the fact's result."""
    m = _PRESENT_ITEM.fullmatch(item.strip())
    return words.functions_only(m["who"], room.folder).lower() if m else ""


def _participants_held(said: _Present, room: Room) -> list[list[str]] | None:
    """680: the turn's result for the activity it is about, never another's; with no activity, the
    one of its results holding most of the sentence's people (one interview, never a mix). None
    where there is no such result."""
    if room.activity:
        return room.participants.get(room.activity)
    return max(room.participants.values(), default=None,
               key=lambda rows: sum(_there(i, rows, room) for i in said.items))


def _there(item: str, rows: list[list[str]], room: Room) -> bool:
    """680: the result holds this person, and every role the item gives them: "Supply Chain Manager
    as process owner" is no one it holds."""
    m = _PRESENT_ITEM.fullmatch(item.strip())
    who = _person(item, room)
    roles = next(({who, *(r.strip().lower() for r in role.split(","))}
                  for function, role in rows if function.lower() == who), None)
    said = (m and (m["paren"] or m["role"] or m["dash"])) or ""
    return roles is not None and all(  # "Head of Purchasing (Jens Harder)" says them twice
        re.sub(r"^the\s+", "", words.functions_only(r.strip(), room.folder).lower()) in roles
        for r in said.split(",") if r.strip())


def _present_why(sentence: str, cited: list[tuple[str, int]], room: Room) -> str | None:
    """680: why a sentence saying who was there last time fails: no result holds any of them, or
    no result and no line, or a line it cites that does not hold them. A name the result does not
    hold beside one it does goes alone (`_who_was_there`)."""
    said = _present(sentence, room)
    if said is None:
        return None
    rows = _participants_held(said, room)
    kept = said.items if rows is None else [i for i in said.items if _there(i, rows, room)]
    if not kept:
        return NOT_THERE.format(name=said.listed)
    if cited:
        line = words.functions_only(" ".join(
            v for c in cited for _, v, _ in evidence(room.folder, *c)), room.folder).lower()
        return None if all((p := _person(i, room)) and re.search(rf"\b{re.escape(p)}\b", line)
                           for i in kept) else NOT_HELD.format(facts=PRESENT_LINE)
    # a tap's narration (`taps`) says what nemo handed it, which no fact call holds
    return None if rows is not None or room.taps is not None else NO_PARTICIPANTS


def _date_checked(when: str, sentence: str, room: Room) -> bool:
    """680: a date beside the frame that may stay for `_why` to read: a day and month alone, whose
    year (which `_why` does not compare) is in a line the sentence cites."""
    if not when:
        return True
    if (m := _PRESENT_DATE.fullmatch(when)) is None:
        return False
    return not m["year"] or any(m["year"] in v for c in cites(sentence, room.read)
                                for _, v, _ in evidence(room.folder, *c))


def _who_was_there(sentence: str, room: Room) -> tuple[str, list[dict[str, str]]]:
    """680: (the sentence as it stands on the turn's `fact_last_participants` result, what was taken
    out of it): a name the result does not hold; a cite that fails where the result holds them, as
    655 takes one out; the interview's date where it is held by no line, never lent."""
    said = _present(sentence, room)
    rows = _participants_held(said, room) if said else None
    if said is None or rows is None:
        return sentence, []
    kept = [i for i in said.items if _there(i, rows, room)]
    # the result's own form: "Head of Purchasing, process owner" says a role, and no one is gone
    gone = [i for n, i in enumerate(said.items) if i not in kept and not (
        n and _there(f"{said.items[n - 1]} ({i})", rows, room))]
    dated = _date_checked(said.when, sentence, room)
    why = _why(sentence, room)
    if not kept or (why or "").startswith(OTHER_DAY.partition("{")[0]) or (
            dated and not gone and "[fact_" not in sentence and not why):
        return sentence, []
    listed = said.listed if not gone else (
        re.sub(r"^(?:both|all)\s+", "", kept[0], flags=re.I) if len(kept) == 1
        else f"{', '.join(kept[:-1])} and {kept[-1]}")
    tail = re.sub(r"\bwere(?: all| both)?\b", "was", said.tail) if len(kept) == 1 and gone \
        else said.tail
    cite = " ".join(m[0] for m in CITE.finditer(each_cite(sentence)))
    lead = m[0] if (m := _LEAD.match(sentence)) else ""

    def built(when: bool, cited: bool) -> str:
        opening = {"": " ", ":": ": "}.get(said.opening, f" {said.opening} ") if said.head else ""
        text = (f"{said.head}{said.when if when else ''}{opening}{listed}"
                f"{' ' + tail if tail else ''}{' ' + cite if cited and cite else ''}.")
        return f"{lead}{text[0].upper()}{text[1:]}"
    for when, kept_cite in ((True, True), (False, True), (False, False)):
        if when and not dated:
            continue
        text = built(when, kept_cite)
        if not _why(text, room):
            return text, [
                *({"text": g.strip(), "reason": NOT_THERE.format(name=g.strip())} for g in gone),
                *({"text": said.when.strip(" ,"), "reason": DATE_OUT}
                  for _ in [1] if said.when and not when),
                *({"text": c.strip(), "reason": CITE_MISS.format(facts=PRESENT_LINE)}
                  for c in _PRESENT_CITE.findall(sentence) if c.strip() not in text)]
    return sentence, []


def _unnamed(bare: str) -> str:
    """The sentence with a name's number left out (647's `IN_NAME`): "Microsoft 365 has no …"."""
    return IN_NAME.sub(lambda m: f"{m['name'] or ''} ", bare)


def _says_absent(bare: str, cells: list[Cell], room: Room) -> str | None:
    """The absence check: "there is no X" stands only where the cited row's own cell states none.
    649: a count of rows (`ROWS_COUNTED`) is no absence claim."""
    if ABSENT.search(ROWS_COUNTED.sub(" ", _unnamed(bare))) and not STATED_ABSENT.search(
            bare) and not NONE_UNTIL.search(bare) and not _states_absence(cells, room.folder):
        return SAYS_ABSENT
    return None


def _is_name(said: str, name: str) -> bool:
    """666: `said` is the register's whole name, or that name less its bracket: "CSB ERP Marschkamp"
    is never "Marschkamp (headquarters)", and a list of names is none."""
    return said.casefold() in (name.casefold(), re.sub(r"\s*\(.*", "", name).casefold())


def _holds_date(what: str, folder: Path, on: str) -> bool:
    """666: the programme plan's row for `on` holds the date `what` says is not stated."""
    name = core._map_key(core.process_name(folder, on))
    row = next((r for r in core._plan_table(folder)[1] if core._map_key(r[1]) == name), None)
    return row is not None and bool(
        _REVIEW_DATE.fullmatch(what) and _PLAN_DAY.search(row[4])
        or _LAST_DATE.fullmatch(what) and _PLAN_DAY.search(row[3])
        or _REINTERVIEW_DATE.fullmatch(what) and _REINTERVIEW_ON.search(row[5]))


def _holds_against(what: str, folder: Path, on: str) -> bool:
    """666: code's fact on activity `on` says otherwise than "`what` is not stated". A one-name
    workaround reads that row's cell, not `core.no_workaround`, which never says a row has a way
    round; a cell that is empty or says there is none has none. An owner is a person: `core.holders`
    names one (`_unowned`), the organisation file names the process owner."""
    if _PROCESS_OWNER.fullmatch(what):
        return core._decides(folder, on)[1] in words.people(folder)
    rows = core.spof(folder, on)["rows"]
    if _NONE_WITHOUT.fullmatch(what):
        return bool(core.no_workaround(folder, on))
    if _ANY_SPOF.fullmatch(what):
        return any(r["flagged"] for r in rows)
    if m := _WORKAROUND_FOR.fullmatch(what):
        return any(not _NO_WAY_ROUND.fullmatch(str(r["workaround"] or ""))
                   and not workspace.flagged({}, r)
                   for r in rows if _is_name(m["name"], r["resource"]))
    if m := _SPOF_NAMED.fullmatch(what):
        return any(r["flagged"] for r in rows if _is_name(m["name"], r["resource"]))
    if m := _OWNER_OF.fullmatch(what):
        return any(_is_name(m["name"], r["resource"]) and r["resource"] not in core._unowned(
            folder, on) for r in rows)
    return _holds_date(what, folder, on)


def _denies_code(said: str, room: Room) -> str | None:
    """666: a "Not stated" line, its words `said` without the saying so, that denies what code holds
    for the turn's activity. Anything else stands: no activity, a line not wholly one of the forms
    `_holds_against` reads, a fact code does not hold, or a line of his naming two activities, where
    the turn's is not surely the one it means."""
    what = said.strip(" .\u2063")
    return DENIES_CODE.format(what=what) if room.activity and _holds_against(
        what, room.folder, room.activity) and len(
            core.named_in(room.folder, room.line)) < 2 else None


def _not_stated_said(said: str) -> str:
    """666: what a sentence says is not stated, in either wording, its bold gone; itself, its bold
    gone, where it says neither."""
    plain = said.replace("*", "")
    return _NOT_STATED_TAIL.sub("", _NOT_STATED_HEAD.sub("", plain))


def _not_stated(bare: str, room: Room) -> str | None:
    """666: `_denies_code` over a sentence that says "Not stated"."""
    what = _not_stated_said(bare)
    return _denies_code(what, room) if what != bare.replace("*", "") else None


def _counted_on(bare: str, at: int, room: Room) -> list[str]:
    """649: the activity a count is said of: the one named last before it, else the first the
    sentence names, else the turn's, else every activity (a folder-wide count)."""
    before = core.named_in(room.folder, bare[:at])
    if before:
        return [max(before, key=lambda a: max(bare[:at].lower().rfind(n.lower()) for n in (
            core.map_name(room.folder, a), a.replace("-", " "))))]
    return core.named_in(room.folder, bare)[:1] or (
        [room.activity] if room.activity else walk.processes(room.folder))


def _rows_counted(bare: str, room: Room) -> tuple[set[int], str | None]:
    """649: a count of rows said in the register's words (`ROWS_COUNTED`) is code's, for the
    activity it is said of (`_counted_on`): "have no workaround" `core.no_workaround`'s, "none
    stated" or "no workaround stated" `core.no_workaround_cell`'s. (The counts code holds; why it
    fails where one is not code's.)"""
    held: set[int] = set()
    code: dict[tuple[Any, tuple[str, ...]], int] = {}
    text = _unnamed(bare)
    for m in ROWS_COUNTED.finditer(text):
        rows = core.no_workaround_cell if m["stated"] or m["none"] else core.no_workaround
        on = tuple(_counted_on(text, m.start(), room))
        n = code.setdefault((rows, on), len(set().union(*(rows(room.folder, a) for a in on))))
        if n != _number(m["n"]):
            return held, COUNT_OFF.format(said=m["n"], what=m["what"], count=n)
        held.add(n)
    return held, None


def _subject(text: str, t: re.Match[str], room: Room) -> str | None:
    """664: the activity whose table the total `t` counts: the one named last before it, with no
    other subject between them, else the turn's where the sentence opens on no subject of its own.
    A resource's own needs and a folder-wide total have no such table, and need their cite."""
    before = text[:t.start()]
    if not core.named_in(room.folder, before):
        return room.activity if _TURN_SAID.fullmatch(before) else None
    on = _counted_on(text, t.start(), room)[0]
    ends = [at + len(n) for n in (core.map_name(room.folder, on), on.replace("-", " "))
            if (at := before.lower().rfind(n.lower())) >= 0]
    between = before[max(ends):] if ends else "?"
    return on if _NAMED_SAID.fullmatch(between) and not (t["on"] and "," in between) else None


def _tables(text: str, room: Room) -> list[tuple[re.Match[str], str]]:
    """664: each total the text says (`TOTAL`) and the activity whose table it counts."""
    return [(t, on) for t in TOTAL.finditer(text)
            if (t["n"] and t["m"] or t["on"] and (t["n"] or t["m"]))
            and (on := _subject(text, t, room))]


def opens_on_a_total(bare: str, folder: Path) -> bool:
    """664: the first line's own count (`LISTED`) is a total code checks, not a count of points."""
    text = _unnamed(bare)
    m = LISTED.search(text)
    return m is not None and any(t.start("n") == m.start(1) and _lends(text, t, on, folder)
                                 for t, on in _tables(text, Room(folder, {}, "")))


def _form_holds(m: re.Match[str], on: str, folder: Path) -> bool:
    """664 Amend 2: a rows-counted form's bracket names rows that form counts, each whole or by two
    words or more at the head or end of its name ("SharePoint Online"). What the activity can run
    without has no count of code's: it needs its bracket, one name per row said, of rows whose cell
    says the activity can go on without them, and not that it is only possible with them."""
    said = {re.sub(r"^the\s+", "", x.strip(), flags=re.I).casefold()
            for x in (m["rows"] or "").split(",") if x.strip()}
    if n := m["without"]:
        if (int(n) if n.isdigit() else _WORDS[n.lower()]) != len(said):
            return False
        rows = {r["resource"] for r in core.spof(folder, on)["rows"] if re.search(
            r"\b(?:possible|can run) without\b", cell := str(r["workaround"] or ""), re.I)
                and not re.search(r"\bonly possible with\b", cell, re.I)
                } - core.no_workaround(folder, on)
    else:
        rows = (core.no_workaround_cell if m["stated"] or m["none"] else core.no_workaround)(
            folder, on)
    names = [re.sub(r"\s*\(.*", "", r).casefold() for r in rows]
    return all(any(x == n or " " in x and (n.startswith(f"{x} ") or n.endswith(f" {x}"))
                   for n in names) for x in said)


def _lends(text: str, t: re.Match[str], on: str, folder: Path) -> bool:
    """664 Amend 2: a true total lends its digits only where it is the table's own ("direct" is the
    mixed pair turned round), its sentence opens on the activity, and nothing follows in that
    sentence but the rows-counted forms. Else the old checks read it."""
    if t["what"].lower().startswith("direct"):
        return False
    before = text[:t.start()].lower()
    opens = min((at for n in (core.map_name(folder, on), on.replace("-", " "))
                 if (at := before.find(n.lower())) >= 0), default=0)
    rest = re.split(r"[.!?]\W*\s|\n", text[t.end():].replace(DEMO_MARK.strip(), " "), maxsplit=1)[0]
    return _TURN_SAID.fullmatch(before[:opens]) is not None and re.fullmatch(
        r"(?:\W|\band\b)*", _ROWS_FORM.sub(
            lambda m: "" if _form_holds(m, on, folder) else m[0], rest)) is not None


def _total_counted(bare: str, room: Room) -> tuple[set[int], str | None]:
    """664: a total is code's, one count only, the table the answer lists: N `core.dependencies`'
    rows, M its groups. (The counts code holds, where no other figure of the sentence says the same
    digits; why it fails where one is not code's: dropped, never rewritten.)"""
    text = _unnamed(bare)
    held: set[int] = set()
    said: list[str] = []
    for t, on in _tables(text, room):
        groups = core.dependencies(room.folder, on)["groups"]
        lends = _lends(text, t, on, room.folder)
        for n, what, count in ((t["n"], t["what"], sum(len(g["rows"]) for g in groups)),
                               (t["m"], "groups", len(groups))):
            if n and (int(n) if n.isdigit() else _WORDS[n.lower()]) != count:
                return set(), COUNT_OFF.format(said=n, what=what, count=count)
            if n and lends:
                held.add(count)
                said.append(n)
    return {n for n in held if NUMBER.findall(text).count(str(n)) == said.count(str(n))}, None


def _fact_counts(bare: str, room: Room, about: list[str]) -> tuple[set[int], str | None]:
    """645: the who or how-many count a sentence opens on ("Three people decide", "4 gaps in", 759:
    "Yes, 3 mismatches"), of a thing a fact tool counted this turn for the activity it is about
    (any, where it names none): (the count where it is the fact's; why it fails where it is not)."""
    counts = [room.counts[a] for a in about if a in room.counts] if about else list(
        room.counts.values())
    m = LISTED.search(DATE.sub(" ", _iso(bare))) if counts else None  # a date's day counts nothing
    if m is None:
        return set(), None
    thing = COUNTED_AS.get(m[2].split()[-1].lower())
    opens = re.sub(r"[ *_]", "", m.string[:m.start()]).lower()
    if opens and (opens != "yes," or thing != "mismatches"):  # 759: "Yes," for mismatches alone
        return set(), None
    want = {c[thing] for c in counts if thing in c}
    if not want or (thing == "mismatches" and (
            " " in m[2] or len(about) > 1 or not _COUNT_ENDS.match(m.string, m.end()))):
        return set(), None  # 759: code counted the activity's whole list, of one activity
    said = int(m[1]) if m[1].isdigit() else SPELLED.index(m[1].lower()) + 1
    if said not in want:
        return set(), COUNT_OFF.format(said=m[1], what=m[2], count=" or ".join(
            f"{n} {thing}" for n in sorted(want)))
    return {said}, None


def _held(sentence: str, bare: str, cited: list[tuple[str, int]], cells: list[Cell], room: Room,
          counted: set[str], about: list[str]) -> str | None:
    """U1 and the pairs: each fact on the cited line, in the member its words claim. A count code
    holds (`_claimed_counts`) needs no line."""
    known = room.known | _fact_values(room, about)
    fact_held = _fact_held(sentence, room, about)
    unrated = _unrated_hours(sentence, cited, cells, room, about)
    beside = set(NUMBER.findall(_HOURS.sub(" ", _bare(sentence))))  # that figure, not as an hour
    unheld = [f for f in facts(sentence, room.classes, room.folder)  # 607: a year alone is none
              if f not in counted and f not in known and not _a_year(f, room)
              and not _known_date(f, known) and f not in fact_held] + _theirs(
        bare, room, known)
    stated = [f for f in unheld if f not in unrated or f in beside]
    if not cited:
        stated = [f for f in stated if f not in _calendar(bare, room)]
    if not stated and (not cited or not unheld):  # 652: what it held still meets the rest
        return None
    if not cited:
        return NO_CITE.format(facts=", ".join(stated))
    cells = [(k, _figures(v), g) for k, v, g in cells]  # 657 Amend 2: "eight hours" holds 8
    header = _header_hours(bare, cells) | _read_hours(bare, room)
    said, days = _in_hours(bare, cells)  # 657 (667): the pair checks read them as the hours
    off = [f for f in stated if f not in header and f not in days
           and not any(_holds(v, f) for _, v, _ in cells)]
    if off and (classes := [f for f in off if f in room.classes]):
        asked = _asked(room, cited)  # 657: a class the question a cited answer replies to names
        off = [f for f in off if f not in classes or not any(
            re.search(rf"\b{re.escape(f)}", q, re.I) for q in asked)]  # "Financially?" too
    if off:
        return NOT_HELD.format(facts=", ".join(off))
    if MONEY.search(bare) and not any(MONEY.search(v) for _, v, _ in cells):
        return PAIR_OFF.format(pair="P19", claimed="money", fact="it",
                               other="a figure on a line that states no money")
    return _empty(said, cells, unrated) or _levels(said, cited, room) \
        or _columns(said, cells, room) or _method(said, room) \
        or _years(said, cited, room) or _speaker(said, cited, room)


def _known_date(fact: str, known: set[str]) -> bool:
    """645: a date ("9 Nov") a fact value holds ("9 Nov 2026", "Mon 9 Nov 2026") stands uncited."""
    return bool(re.fullmatch(rf"\d{{1,2}} (?:{'|'.join(_MONTHS)})", fact)) and any(
        _holds(v, fact) for v in known)


def _fact_values(room: Room, about: list[str]) -> set[str]:
    """The values the turn's fact results returned about what a sentence is about (any, where it is
    about none)."""
    return room.known_by.get("", set()).union(*(
        room.known_by.get(a, set()) for a in about) if about else room.known_by.values())


def _fact_held(sentence: str, room: Room, about: list[str]) -> set[str]:
    """655: the figures of a sentence a fact result of this turn holds, each the whole of a value
    (`_FIGURE_VALUE`: 16 is none inside 168, nor a date's day, nor a number in a value's prose),
    said whole with its unit and as the member its key holds (`_whole`), about what the sentence
    is about: its hours said in days beside them ("72 h (3 days)") too, and a count the fact
    counted for the activity it names, or the focus, said as what it counted (`COUNT_SAID`). A
    figure only where the whole sentence is the record's own form (`RECORD_FORM`, r8; else a
    line). None where it names a speaker or a source (r4, F3; uncited, "the record said" or
    "says" is the fact's own, r5 R1), another year or one in digits (`OTHER_YEAR`, R2; in doubt,
    a line) or a negation (`NEGATED`, R3)."""
    bare, own = _bare(sentence), _own(sentence)
    said = [f for f in facts(sentence, folder=room.folder) if NUMBER.fullmatch(f)]
    if not said or _sourced(own if CITE.search(sentence) else RECORD_SAID.sub(" ", own), room) \
            or OTHER_YEAR.search(own) or NEGATED.search(own):  # r4 (F3), r5 (R1-R3): a line
        return set()  # ties a speaker, a year or a denial to the figure
    tied = RECORD_FORM.fullmatch(re.sub(r"\s+([.,])", r"\1", " ".join(bare.split())))  # r8
    values = [m for v in _fact_values(room, about)
              if (m := _FIGURE_VALUE.fullmatch(v.strip()))] if tied else []
    held = {f for f in said if any(_whole(bare, v, f, room, about) for v in values)} | {
        str(n) for a in about for k, n in room.counts.get(a, {}).items()
        if (c := COUNT_SAID.get(k)) and str(n) in said and not c[1].search(bare)
        and re.search(rf"(?<![\d.,]){n}\s+{c[0]}", bare, re.I)}
    return held | {m[2] for m in _DAYS_BESIDE.finditer(bare)
                   if m[1] in held and int(m[1]) == 24 * int(m[2])}


def _whole(bare: str, value: re.Match[str], fact: str, room: Room, about: list[str]) -> bool:
    """655 r4 (49's ruling): the sentence says `fact` as the whole of `value` (">168 h", never 168
    nor "72 people" for "72 h"), each time as the member its fact key holds: the member named last
    before it, else first after it (`MEMBER_KEYS`; a member no key holds is held by none)."""
    if fact != value["n"]:
        return False
    found = list(re.finditer(_FIGURE_SAID.format(n=re.escape(fact)), bare, re.I))

    def norm(x: str | None) -> str:
        return _SAID_AS.get((x or "").lower(), (x or "").lower())

    def member_ok(at: int) -> bool:
        named = max(((m.start(), k) for k, w in MEMBERS.items() for m in w.finditer(bare[:at])),
                    default=None) or min(((m.start(), k) for k, w in MEMBERS.items()
                                          for m in w.finditer(bare, at)), default=None)
        if named is None:
            return True
        key = MEMBER_KEYS.get(named[1])
        return key is not None and any(
            isinstance(r := core.FACTS[key[0]](room.folder, a), dict)
            and str(r.get(key[1]) or "").strip() == value[0].strip() for a in about)
    return bool(found) and all(norm(m["cmp"]) == norm(value["cmp"])
                               and norm(m["unit"]) == norm(value["unit"])
                               and member_ok(m.start()) for m in found)


def _sourced(bare: str, room: Room) -> bool:
    """655 r4 (F3): the sentence's own words (a quotation aside) name a speaker or a source:
    "said", "the interview", a person the organisation file names, or their function."""
    people = words.people(room.folder)
    named = {w for n in people for w in n.split() if len(w) > 2} | set(people.values())
    return bool(SOURCED.search(bare)) or any(
        re.search(rf"\b{re.escape(n)}\b", bare) for n in named if n)


def _missed(sentence: str, room: Room) -> tuple[list[str], list[str]]:
    """655: (the cites to take out of a sentence, the figures they miss): where a figure it says
    is held by a fact result of this turn and by no line it cites, each cite whose line holds none
    of its facts and none of its quotations, so no cite is shown that does not hold what it backs.
    Only where the sentence fails on nothing else but a line not holding a figure (no quotation,
    day or threshold check is skipped by it) and stands without them."""
    at = {m[0]: cites(m[0], room.read) for m in CITE.finditer(sentence)}
    if not at or any(c not in room.read for cs in at.values() for c in cs) or (
            (w := _why(sentence, room)) and not w.startswith(NOT_HELD.partition("{")[0])):
        return [], []
    about = core.named_in(room.folder, _own(sentence)) or (
        [room.activity] if room.activity else [])
    cells = {b: [v for c in cs for _, v, _ in evidence(room.folder, *c)] for b, cs in at.items()}
    said, held = facts(sentence, room.classes, room.folder), _fact_held(sentence, room, about)
    missed = [f for f in said if f in held and not any(  # 657 Amend 2: as `_held` reads them
        _holds(_figures(v), f) for vs in cells.values() for v in vs)]
    quotes = [_plain(m["words"]) for m in core.QUOTED.finditer(
        core.TAP_QUOTED.sub(" ", _bare(sentence))) if len(m["words"].split()) > 1]
    out = [b for b, vs in cells.items() if missed and not any(
        _holds(_figures(v), f) for v in vs for f in said) and not any(q in _plain(" ".join(vs))
                                                            for q in quotes)]
    if not out or _why(_without(sentence, out), room):
        return [], []
    return out, missed


def _closed(sentence: str) -> str:
    """713: a sentence a cite went from: commas with nothing left between them go, those opening or
    closing it, an empty bracket too, and it keeps its one stop. A comma with words on both sides
    stays, and so does one before a figure's own point (", .5")."""
    one = re.sub(r"[ \t]*([,;])(?:[ \t]*[,;])+", r"\1", sentence)
    empty = re.sub(r"[ \t]*\([ \t,;]*\)", "", one)
    cited = re.sub(r"[ \t]*[,;][ \t]*(?=" + CITE.pattern + ")", " ", empty)
    opens = re.sub(r"^[ \t]*[,;][ \t]*", "", cited)
    closes = re.sub(r"[ \t]*[,;][ \t]*(?!\.\.)(?=[.!?):](?:[\s.!?)]|$)|$)", "", opens)
    return re.sub(r"(?<![.!?])([.!?])[ \t]*\.(?![.!?])(?=\s|$)", r"\1", closes)


def _without(sentence: str, brackets: list[str]) -> str:
    for b in brackets:
        sentence = re.sub(rf"[ \t]*{re.escape(b)}", "", sentence)
    return _closed(sentence)


def cite_miss(why: str) -> bool:
    """655: a drop that records a cite taken out (`CITE_MISS`), or 680's date (`DATE_OUT`): the
    sentence stands, no cut."""
    return why == DATE_OUT or bool(_CITE_MISS_SAID.fullmatch(why))


def _a_year(said: str, room: Room) -> bool:
    """607: a year of the story (ten either side of its today), no figure and no count."""
    return bool(YEAR.fullmatch(said)) and (
        room.today is None or abs(int(said) - room.today.year) <= 10)


def _calendar(bare: str, room: Room) -> set[str]:
    """607: the dates said with their weekday that need no cite: code's calendar checks the
    weekday (`_days`), and the day is the plan's, or one his line names by its weekday (B8)."""
    if room.today is None:
        return set()
    his = " ".join([room.line, *room.said]).lower()
    plan = room.folder / core.PROGRAMME_PLAN
    held = plan.read_text(encoding="utf-8") if plan.is_file() else ""
    return {f"{m['day']} {m['month']}" for m in WEEKDAY_DATE.finditer(_iso(bare))
            if next(d for d in _WEEKDAYS if d.startswith(m["weekday"])).lower() in his
            or _holds(held, f"{m['day']} {m['month']}")}


def _theirs(bare: str, room: Room, known: set[str]) -> list[str]:
    """607 (Amend 2): the values a fact tool returned for another activity that the sentence
    says: a name of the room's (a supplier, a function), never a class or an activity's name."""
    return sorted({v for vs in room.known_by.values() for v in vs if v not in known
                   and v not in room.classes and re.search(r"[A-Z\d]", v) and len(v) > 3
                   and re.search(rf"(?<!\w){re.escape(v)}(?!\w)", bare)
                   and not core.named_in(room.folder, v)})


def _untapped(sentence: str, taps: list[str]) -> str | None:
    """607 (rule 11, a step matches its tap): the label a sentence tells him to tap, where no tap
    drawn has it."""
    def plain(x: str) -> str:
        return " ".join(x.replace(core.MAIL_MARK, "").strip(" *").lower().split())
    drawn = {plain(t) for t in taps}
    return next((m["label"] for m in core.TAP_QUOTED.finditer(sentence)  # never "tapped"
                 if plain(m["label"]) not in drawn and not re.match(r"\w+ed\b", m[0])), None)


def _unquoted(sentence: str, cells: list[Cell]) -> str | None:
    """607 (576's example 11): a quotation of two words or more that the cited lines do not hold,
    each part around an ellipsis on its own; a tap's label is no quotation."""
    held = _plain(" ".join(v for _, v, _ in cells))
    said = core.TAP_QUOTED.sub(" ", _bare(sentence))
    return next((m["words"].strip() for m in core.QUOTED.finditer(said)
                 if len(m["words"].split()) > 1 and any(
                     (part := _plain(x)) and part not in held
                     for x in re.split(r"\.\.\.|…", m["words"]))), None)


def _plain(x: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", x.lower()).split())


def _read_hours(bare: str, room: Room) -> set[str]:
    """546 r3 AMEND 2: the figure of the method's reading, said as such, is held by that reading
    (`_method` judges that it is the reading), not by a cell of the cited row."""
    if not BY_METHOD.search(bare):
        return set()
    activity = next(iter(core.named_in(room.folder, bare) or []), room.activity)
    reading = method_reading(room, activity) if activity else None
    return set(_HOURS.findall(reading or ""))


def _header_hours(bare: str, cells: list[Cell]) -> set[str]:
    """546 r3: a grid's hour header holds a figure only as the horizon of the cell the sentence
    rates ("<rating> at <h>", where the row's cell at <h> is that rating), or as the hour of a
    threshold phrase (`_threshold` has judged it). Never an RTO, RPO or MTPD figure."""
    held = {m["h"] for m in NONE_UNTIL.finditer(bare)
            if any(k == f"{int(m['h'])} h" for k, _, _ in cells)}
    for k, v, _ in cells:
        if (h := _HOURS.fullmatch(k)) and v.strip().isalpha() and re.search(
                rf"\b{re.escape(v.strip())}\b\W+(?:\w+\W+){{0,2}}at\s+{h[1]}\s*h\b", bare, re.I):
            held.add(h[1])
    return held


def _threshold(m: re.Match[str], cells: list[Cell]) -> str | None:
    """AMEND 1: "no <class> impact until <h>" on a grid row stands only where <h> is the first hour
    the row rates above none. The ratings are the row's hour columns, in the table's order; a row
    with no such column is no grid and is not judged here."""
    hours = [(k, v.strip().lower()) for k, v, _ in cells if _HOURS.fullmatch(k)]
    said = f"{int(m['h'])} h"
    if not hours or said not in dict(hours):
        return None
    first = next((k for k, v in hours if v not in ("none", "–", "-", "")), None)
    if first == said:
        return None
    return FALSE_THRESHOLD.format(
        cls=m["cls"], hour=said,
        first=f"first rates above none at {first}" if first else "never rates above none")


def _states_absence(cells: list[Cell], folder: Path, on: Iterable[str] | None = None) -> bool:
    """546 r2: the cited row's WORKAROUND cell itself states none ("No workaround: …", "no direct
    workaround"). No other cell does: not a takeover or owner cell
    ("not stated"), not an outer row's (`OUTER`), not the demo mark's own words. 604: read through
    `core.spof` (`core.no_workaround`), the rule the workspace table draws. 648: where `on` names
    activities, only a row of one of them."""
    names = {v for k, v, _ in cells if k == "name"}
    groups = {g for k, v, g in cells if k == "workaround" and g not in (OUTER, "") and v.strip()
              and (on is None or g in on)}
    return any(names & core.no_workaround(folder, g) for g in groups)


def _flagged(folder: Path, activity: str) -> set[str]:
    """656: the activity's single points of failure: the resources `core.spof` flags."""
    return {r["resource"] for r in core.spof(folder, activity)["rows"] if r["flagged"]}


def _number(n: str) -> int:
    """A count said in digits or spelled ("three")."""
    return int(n) if n.isdigit() else SPELLED.index(n.lower()) + 1


def _not_spof(bare: str, room: Room) -> str | None:
    """604 (576 part C): a sentence calling a register resource a single point of failure stands
    only where `core.spof` flags its row, for the activities it names, else the turn's, else any.
    A sentence saying something is not one claims nothing."""
    if not SPOF_SAID.search(bare) or SPOF_DENIED.search(bare):
        return None
    on = core.named_in(room.folder, bare) or (
        [room.activity] if room.activity else walk.processes(room.folder))
    rows = [r for a in on for r in core.spof(room.folder, a)["rows"]]
    return next((NOT_SPOF.format(resource=name) for name in sorted({r["resource"] for r in rows})
                 if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", bare, re.I)
                 and not any(r["flagged"] for r in rows if r["resource"] == name)), None)


def _left_empty(hours: str, cells: list[Cell]) -> bool:
    """The cited line leaves the cell at this hour empty ("1 h –" in a worded line, "–" under a
    grid's hour)."""
    return any((col == f"{hours} h" and v.strip() in ("–", "-", "")) or
               re.search(rf"(?<!\d){hours} h\s*[–-](?!\s*\d)", v) for col, v, _ in cells)


def _rates(said: str, hours: str, cells: list[Cell]) -> bool:
    """652: the sentence holds a rating, bound to no other hour, that no cited line's cell at this
    hour holds."""
    other = rf"(?<![\d.])(?!{hours}\s*h)\d+\s*h(?:ours?)?\b"
    rest = _HOURS.sub(" ", re.sub(
        rf"\b(?:{_RATING})\s+(?:at|for)\s+{other}"
        rf"|{other}(?:\s+\w+){{0,2}}?\s+(?:is|was|at|as|rated)\s+(?:rated\s+)?(?:{_RATING})\b",
        " ", said, flags=re.I))
    return any(not any((k == f"{hours} h" and v.strip().lower() == rating.lower())
                       or re.search(rf"(?<!\d){hours} h\s+{rating}\b", v, re.I)
                       for k, v, _ in cells)
               for rating in re.findall(rf"\b(?:{_RATING})\b", rest, re.I))


def _unrated_hours(sentence: str, cited: list[tuple[str, int]], cells: list[Cell], room: Room,
                   about: list[str]) -> set[str]:
    """652: the hours a sentence says were left unrated, and so no figure: said so in the hour's
    clause (`UNRATED`), not denied, not rated, and the dash in a cited line's cell; a claim
    `ACROSS` years, in the cells of two cited files. Uncited: about last year, as `_fact_held`
    reads a source and a year, and listed by this turn's result for all it is about
    (`Room.unrated`, never `known_by`, which holds every hour fact_mismatches returned)."""
    said = _bare(sentence)
    if UNRATED_DENIED.search(said):
        return set()
    clauses = _CLAUSES.split(said)
    hours = {h for clause in clauses if UNRATED.search(clause)
             for h in _HOURS.findall(clause) if not _rates(said, h, cells)} - {
        h for clause in clauses if not UNRATED.search(clause)  # "and the RTO was 1 h" is a figure
        and not re.search(rf"\b(?:{_RATING})\b", _HOURS.sub(" ", clause), re.I)
        for h in _HOURS.findall(clause)}
    if not cited:
        if ACROSS.search(said) or not LAST_RECORD.search(said) or OTHER_YEAR.search(said) \
                or _sourced(RECORD_SAID.sub(" ", _own(sentence)), room):
            return set()
        listed = [{h for hs in room.unrated.get(a, {}).values() for h in hs} for a in about] or [
            {h for r in room.unrated.values() for hs in r.values() for h in hs}]
        return {h for h in hours if f"{h} h" in set.intersection(*listed)}
    if ACROSS.search(said):
        return {h for h in hours if sum(any(_left_empty(h, evidence(room.folder, p, n))
                                            for q, n in cited if q == p)
                                        for p in {q for q, _ in cited}) >= 2}
    return {h for h in hours if _left_empty(h, cells)}


def _empty(bare: str, cells: list[Cell], unrated: set[str]) -> str | None:
    """P7: a cell the cited line leaves empty holds no figure, whatever else the line holds, unless
    the sentence says just that (`unrated`, 652)."""
    for hours in _HOURS.findall(bare):
        h = f"{hours} h"
        if hours not in unrated and len(NUMBER.findall(bare)) > 1 and _left_empty(hours, cells):
            return PAIR_OFF.format(pair="P7", claimed=f"a figure at {h}", fact=h,
                                   other="a cell the line leaves empty")
    return None


def _demo(cells: list[Cell], sentence: str) -> bool:
    """P17: the cited row was written for the demo pack (`authored`, or the mark in a cell), or a
    row around it was for the field the sentence states ("owner_evidence" for its owner)."""
    fields = {k: v for k, v, g in cells if g == OUTER}
    return any(g != OUTER and (DEMO.search(v) or (k == "authored" and v == "True"))
               for k, v, g in cells) or any(
        g == OUTER and k.endswith("_evidence") and DEMO.search(v) and (said := fields.get(
            k.removesuffix("_evidence"))) and re.split(r"\s*\(", said)[0].lower() in
        sentence.lower() for k, v, g in cells) or fields.get("authored") == "True"


def marked_values(handed: str) -> set[str]:
    """720: what nemo handed that a row written for the demo pack states (`MARKED_ROW`)."""
    return {v for row in MARKED_ROW.findall(handed) for v in ROW_VALUE.findall(row)}


def _word_pairs(text: str) -> set[tuple[str, str]]:
    """720: each two neighbouring words of a clause, a short word skipped, so a control said in
    other words ("an emergency generator") still reads as it."""
    said = [re.findall(r"[^\W\d_]{4,}", clause.lower()) for clause in text.split(";")]
    return {pair for words_of in said for pair in zip(words_of, words_of[1:], strict=False)}


def _marked(sentence: str, room: Room) -> bool:
    """P17: a fact from a row or line written for the demo pack. A cited sentence by its cite (720:
    the mark no longer goes in the sentence); an uncited one by the values handed from such a row
    (N3): it adds a mark and cuts nothing."""
    if cited := cites(sentence, room.read):
        cells = [c for p, n in cited for c in evidence(room.folder, p, n)]
        return _demo(cells, words.functions_only(sentence, room.folder))
    if not room.marked:
        return False
    pairs = _word_pairs(sentence) - room.resource_words
    return any(re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", sentence, re.I)
               or _word_pairs(DEMO.sub(" ", v)) & pairs for v in room.marked)


def stands_marked(text: str, room: Room) -> bool:
    """720: a sentence of `text`, as it stands after the checks, states a fact `_marked` finds."""
    return any(_marked(s, room) for line in text.split("\n") for s in core._sentences(line))


def marked_call(template: str, args: dict[str, Any], room: Room) -> bool:
    """720: the same over a template call's parts as they stand; a draft's body carries no mark."""
    return any(stands_marked(said, room) for _, said, body in parts(template, args) if not body)


def mark_line(text: str, marked: bool) -> list[str]:
    """720: the mark as he reads it, its own line under `text`; none where the mark stands in it."""
    return [DEMO_MARK.strip()] if marked and DEMO_MARK.strip() not in text.lower() else []


# ── action claims (530's rule, reused) ──────────────────────────────────────────────────────────
def _done(sentence: str, ran: list[str]) -> bool:
    """A sentence describing what this turn's tools did: each done-word it says is one a tool
    that ran did, and it says nothing was placed, sent, moved or blocked."""
    did = frozenset().union(*(DONE_BY.get(t, frozenset()) for t in ran))
    said = {m[0].lower() for m in core.CLAIMED.finditer(sentence)}
    return bool(said) and said <= did and not PLACED.search(sentence)


def claims(text: str, room: Room) -> tuple[list[str], list[str]]:
    """530's `drop_claims` on a model-led turn: (the sentences claiming an action no tool of this
    turn did, the taps of the room's tools they claimed). No tap's kind is ever the model's to run,
    so a claim stands only where `_done` holds; a claim no tap reads goes too."""
    def guard(reads: Callable[[str], Any]) -> Callable[[str], bool]:
        return lambda s: not (NEGATED.search(s) or CITE.search(s) or _done(s, room.ran)) \
            and bool(reads(s))
    offers: list[Offer] = [(guard(r), label, call) for r, label, call in room.offers]
    _, gone, labels = core.drop_claims(text, [*offers, (guard(ACTED.search), "",
                                                        {"kind": NO_TOOL})], [])
    return gone, [x for x in labels if x]


def denials(text: str, room: Room) -> tuple[list[str], list[str]]:
    """449's `drop_denials` on a model-led turn: (the sentences denying a tool the room has, its
    taps)."""
    if not (core.DENIED_BY.search(text) and core.DENIAL.search(text)):
        return [], []
    _, gone, labels = core.drop_denials(text, [(r, label) for r, label, _ in room.offers])
    return gone, labels


# ── the stack ───────────────────────────────────────────────────────────────────────────────────
Unit = tuple[int, int]


def _follows_on(s: str) -> bool:
    """668: a short line with nothing of its own to stand on (`_POINTS_BACK`, `_QUESTION_BACK`)."""
    n = len(s.split())
    return bool(n <= FOLLOW_ON_WORDS and _POINTS_BACK.match(s) and _STEP.match(s.lstrip("*_ "))
                or n <= FOLLOW_ON_QUESTION and s.rstrip(" *_").endswith("?")
                and _QUESTION_BACK.match(s))


def _unsubjected(units: list[list[str]], why: dict[Unit, str]) -> None:
    """A sentence opening on a pronoun right after a dropped one, in the same paragraph, goes with
    it (B2: "It is the only overdue BIA" with the BIA's name dropped); 668: so does a line that only
    follows it (B9: "Ask him directly.")."""
    flat = [(i, j) for i, line in enumerate(units) for j in range(len(line))]
    for (a, b), (i, j) in itertools.pairwise(flat):
        if (a, b) in why and (i, j) not in why \
                and all(units[x][0].strip() for x in range(a, i + 1)):
            s = _LEAD.sub("", units[i][j])
            reason = NO_SUBJECT if _PRONOUN.match(s) else FOLLOWS_CUT if _follows_on(s) else None
            why.update({(i, j): reason} if reason else {})


def _unlabelled(units: list[list[str]], why: dict[Unit, str]) -> None:
    """What sits under a dropped label line goes with it, up to a blank line or the next label (A2's
    quotes with no gap name)."""
    labels = [i for i, line in enumerate(units) if line and _LABEL.search(" ".join(line))
              and all((i, j) in why for j in range(len(line))) and why[(i, 0)] != NO_LABEL]
    for i in labels:
        for x in itertools.takewhile(lambda x: "".join(units[x]).strip() and not _LABEL.search(
                " ".join(units[x])), range(i + 1, len(units))):
            why.update({(x, j): NO_LABEL for j in range(len(units[x]))})


def _headless(units: list[list[str]], why: dict[Unit, str]) -> None:
    """607 (576 A): a label line whose lines under it all went goes with them (A2's gap headings
    with no quote left)."""
    for i, line in enumerate(units):
        under = list(itertools.takewhile(lambda x: "".join(units[x]).strip() and not _LABEL.search(
            " ".join(units[x])), range(i + 1, len(units))))
        if line and _LABEL.search(" ".join(line)) and under and all(
                (x, j) in why for x in under for j in range(len(units[x]))):
            why.update({(i, j): NO_QUOTES for j in range(len(line)) if (i, j) not in why})


def _opener(units: list[list[str]], why: dict[Unit, str]) -> None:
    """607 (576 B): the answer's first sentence that stands, after a drop before it, loses the
    connective it opens with ("But …"); a quotation's own never (it opens on its mark)."""
    flat = [(i, j) for i, line in enumerate(units) for j, s in enumerate(line) if s.strip()]
    first = next(((i, j) for i, j in flat if (i, j) not in why), None)
    if first and first != flat[0]:
        i, j = first
        units[i][j] = CONNECTIVE.sub(lambda m: m[1] + m[2].upper(), units[i][j], count=1)


def _figures(sentence: str) -> str:
    """588 (L1): the sentence with each count in words a figure ("five days" is 5 days)."""
    return _SPELLED.sub(lambda m: str(SPELLED.index(m[1].lower()) + 1), sentence)


def _measured(s: str) -> bool:
    """665: the text names a measure or a unit, so a number ending it is that measure's."""
    return any(p.search(s) for p in (RTO, MTPD, RPO, SPOF_SAID, _UNIT_WORD))


def _item_end(s: str) -> bool:
    """665 (23's read): the text before a list's next number ends an item: it opens on a step to
    take (`_STEP`, a closed list), ends on a thing named after "the", "a", …, and has no word that
    takes a figure and no measure anywhere in it. A label's ("MTPD in days: 2.") never matches: the
    thing named must end the text."""
    return bool(_STEP.match(s) and _ITEM_END.search(s)) and not _TAKES_A_FIGURE.search(s) and \
        not _measured(s)


def _listed(units: list[list[str]]) -> set[Unit]:
    """665: the sentences ending on a list's number. A list opens on a lead, "…: 1." or a "1."
    alone, and runs on through each next sentence ending on its next number after an item's end
    ("Call the supplier 2.", `_item_end`), never a label's ("MTPD in days: 2.") or a figure's ("The
    RTO is 2."), up to a blank line. A lead's label is one that heads a list, whole
    (`_LEAD_LABEL`, "Focus points: 1."); a measure's ("The RTO in hours: 1.") or a count's ("Empty
    cells in production: 1.") is no lead. It is a list where two of its numbers end sentences, or
    a lead's "1." has a "2." opening a line or sentence after it in the paragraph or opening the
    next one (a loose list); any other number is a figure, as before ("Open points: 1. Call …")."""
    out: set[Unit] = set()
    paragraphs = [list(g) for blank, g in itertools.groupby(
        [((i, j), s) for i, line in enumerate(units) for j, s in enumerate(line)],
        key=lambda x: not x[1].strip()) if not blank]
    for p, flat in enumerate(paragraphs):
        k = 0
        while k < len(flat):
            s = flat[k][1]
            m = _LIST_END.search(s)
            head = s[:m.start()] if m is not None and m[1] == "1" else ""
            colon = bool(_LEAD_LABEL.fullmatch(head.rstrip())) and not _measured(head)
            if not colon and s.strip() != "1.":
                k += 1
                continue
            chain, n = [flat[k][0]] if colon else [], 1
            k += 1
            while k < len(flat) - 1 and (m := _LIST_END.search(flat[k][1])) and int(
                    m[1]) == n + 1 and _item_end(flat[k][1][:m.start()]):
                chain, n, k = [*chain, flat[k][0]], n + 1, k + 1
            after = [*flat[k:], *(paragraphs[p + 1][:1] if p + 1 < len(paragraphs) else [])]
            if len(chain) >= 2 or colon and any(_TWO.match(x) for _, x in after):
                out.update(chain)
    return out


def _bracketed(text: str) -> bool:
    """665: the answer's parenthesised numbers before items are a list's: each run (1), (2), … in
    order, two or more long, across its sentences and lines; "(72 h)", a lone "(3)" or one out of
    order leaves every one a figure."""
    runs: list[int] = []
    for n in (int(m[1]) for m in _PAREN.finditer(text)):
        if n == 1:
            runs.append(1)
        elif runs and n == runs[-1] + 1:
            runs[-1] = n
        else:
            return False
    return bool(runs) and min(runs) >= 2


def _unlisted(s: str, listed: bool, bracketed: bool) -> str:
    """665: the sentence with a list's numbers taken out: the one ending it where `listed`, and
    the parenthesised ones before items where the answer's are `bracketed`."""
    s = _LIST_END.sub("", s) if listed else s
    return _PAREN.sub("", s) if bracketed else s


def _verdicts(units: list[list[str]], room: Room, body: bool, claimed: list[str],
              denied: list[str], held: bool = False, *, listed: set[Unit], bracketed: bool
              ) -> dict[Unit, str]:
    """Why each sentence goes, by its place; a drop's orphans with it. A `held` body (588, a
    letter's) goes through the facts' stack as an answer does, its counts in words as figures.
    A list's number is no figure (665, `_listed`, `_bracketed`)."""
    why: dict[Unit, str] = {}
    for i, line in enumerate(units):
        for j, s in enumerate(line):
            reason = None if not s.strip() else CLAIMED_DONE if s in claimed else \
                DENIED if s in denied else None if body and not held else \
                _why(_unlisted(s, (i, j) in listed, bracketed), room, held)
            why.update({(i, j): reason} if reason else {})
    _unsubjected(units, why)
    _unlabelled(units, why)
    _headless(units, why)
    return why


def _kept(line: list[str], i: int, why: dict[Unit, str], shown: Callable[[str], str],
          listed: set[Unit]) -> list[str]:
    """What of a line stands. 713: on a line with a cut, a bullet or a list's number with nothing
    left after it goes, wherever it stands, as does the number ending a sentence (`_listed`) with
    nothing after it, the sentence keeping its stop. A number is a list's in a run up from 1 on
    the line: a "2." answering a question stays, unless nothing else on the line does."""
    if not any((i, j) in why for j in range(len(line))):
        return [shown(s) for s in line]
    bare = r"\s*(?:\d+[.)]|[-*•])\s*"
    stands = [(j, shown(s)) for j, s in enumerate(line) if (i, j) not in why]
    if all(re.fullmatch(bare, x) or x.strip() == "|" for _, x in stands):  # a cut row's last pipe
        return []
    numbers = {int(m[1]) for j, s in enumerate(line) for m in (
        _OPENING_NUMBER.match(s), (i, j) in listed and _LIST_END.search(s)) if m} | {
        len(m[0].strip()) for s in line if (m := _HELD_NUMBER.match(s))}
    last = next(n for n in itertools.count(1) if n not in numbers)  # a list runs up from its 1
    kept: list[str] = []
    empty = True  # nothing stands yet between here and the next number or the line's end
    for j, x in reversed(stands):
        if re.fullmatch(bare, x):
            if not empty or (n := re.match(r"\s*(\d+)", x)) and not (int(n[1]) < last and last > 2):
                kept = [*kept, x]
            empty = True
            continue
        if empty and (i, j) in listed and j < len(line) - 1:
            words = _LIST_END.sub("", x).rstrip()
            x = words if words.endswith((":", ".", "!", "?")) else f"{words}."
        kept, empty = [*kept, x], False
    return kept[::-1]


def rowless(lines: list[str]) -> list[str]:
    """713: the lines without a table's separator that has no row under it, nor its header row:
    the piped line right above it, opening as the separator does, unless a piped line above makes
    it a row. A sentence stays; one with a pipe stays above a separator that opens on a pipe."""
    def piped(k: int) -> bool:
        return 0 <= k < len(lines) and "|" in lines[k]

    def lone(k: int) -> bool:
        return k < len(lines) and bool(_SEPARATOR.fullmatch(lines[k])) and not (
            piped(k + 1) and not _SEPARATOR.fullmatch(lines[k + 1]))

    def header(k: int) -> bool:
        return piped(k) and lone(k + 1) and not piped(k - 1) and lines[k].lstrip(
            ).startswith("|") == lines[k + 1].lstrip().startswith("|")
    return [x for k, x in enumerate(lines) if not lone(k) and not header(k)]


def _uncited(sentence: str) -> str:
    """602: a body's cites taken out, the space between its words kept ("72 h [cite] and" reads
    "72 h and", never "72 hand"). 713: and the comma ("the plant [cite], then" reads "the plant,
    then"), with none left over (`_closed`)."""
    def between(m: re.Match[str]) -> str:
        if m.start() == 0 or re.match(r"[.,;:!?]|$", sentence[m.end():]):
            return ""
        last = m[0].rstrip()[-1]
        none = re.search(r"^\s*[-*•]\s*$|[:(,;]\s*$", sentence[:m.start()])  # nothing to part
        return f"{last} " if last in ",;" and not none else " "
    out, n = _CITES.subn(between, sentence)
    return _closed(out) if n else out


def check(text: str, room: Room, must_cover: Iterable[str] = (),
          code_lists: dict[str, list[str]] | None = None, body: bool = False,
          held: bool = False) -> Checked:
    """Every sentence of `text` through the stack. A draft's `body` (the recipient's letter) is read
    for action claims, denials and names only; a `held` one (588, the model's letter) for its facts
    too. A body's cites are taken out of what the recipient reads."""
    text = _CITE_AFTER.sub(lambda m: f"{m[2]}{m[1]}", each_cite(text or ""))
    claimed, taps = claims(text, room)
    denied, has = denials(text, room)
    units = [core._sentences(line) if line.strip() else [line] for line in text.split("\n")]
    said = [list(line) for line in units]
    listed = set() if body and not held else _listed(units)
    bracketed = not (body and not held) and _bracketed(text)
    present = {} if body or held else {  # 680: judged and shown as the result holds them
        (i, j): w for i, line in enumerate(units) for j, s in enumerate(line)
        if (w := _who_was_there(s, room))[1]}
    for (i, j), (stands, _) in present.items():
        units[i][j] = stands
    missed = {} if body or held else {
        (i, j): m for i, line in enumerate(units) for j, s in enumerate(line)
        if (m := _missed(_unlisted(s, (i, j) in listed, bracketed), room))[0]}
    for (i, j), (gone, _) in missed.items():  # 655: the sentence is judged and shown without them
        units[i][j] = _without(units[i][j], gone)
    why = _verdicts(units, room, body, claimed, denied, held, listed=listed, bracketed=bracketed)
    out = Checked("", claimed=taps, denied=has)
    taken = [(at, {"text": b, "reason": CITE_MISS.format(facts=", ".join(f))})
             for at, (gone, f) in missed.items() if at not in why for b in gone] + [
        (at, d) for at, (_, taken_out) in present.items() if at not in why for d in taken_out]
    out.drops = [d for _, d in sorted(taken + [
        ((i, j), {"text": said[i][j].strip(), "reason": r}) for (i, j), r in why.items()],
        key=lambda x: x[0])]  # 655: in the text's order
    _opener(units, why)
    lines = [" ".join(_kept(line, i, why, _uncited if body else str, listed))
             for i, line in enumerate(units)]
    lines = [x for x, line in zip(lines, units, strict=True) if x or not "".join(line).strip()]
    shown = re.sub(r"\n{3,}", "\n\n", "\n".join(rowless(lines) if why else lines)).strip()
    out.text = shown if words.NAMES_ASKED.search(room.line) else \
        words.functions_only(shown, room.folder)
    out.must_cover_misses, out.refused = covered(out.text, must_cover, code_lists)
    return out


def _said(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def covered(text: str, must_cover: Iterable[str] = (),
            code_lists: dict[str, list[str]] | None = None,
            drawn: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    """(the must-cover items `text` misses, recorded and never appended; a refusal for each list
    code handed that it shortens). 632: an item the drawn graph shows (`drawn`) is covered, for
    both: the graph names it where the text does not."""
    seen, shown = _said(text), {_said(x) for x in drawn}

    def missing(items: Iterable[str]) -> list[str]:
        return [x for x in items if _said(x) not in seen and _said(x) not in shown]
    return missing(must_cover), [SHORTENED.format(items=", ".join(left), what=what)
                                 for what, items in (code_lists or {}).items()
                                 if (left := missing(items))]


# ── a template call's parts, and the retry ──────────────────────────────────────────────────────
Place = tuple[str | int, ...]


def parts(template: str, args: dict[str, Any]) -> list[tuple[Place, str, bool]]:
    """The text a template call's arguments hold, each as (its place in the arguments, its text,
    whether it is a draft's body)."""
    out: list[tuple[Place, str, bool]] = []
    for key, value in args.items():
        if key in ("body",):
            out.append(((key,), str(value), True))
        elif key in ("answer", "details", "verdict", "caption", "subject") \
                and isinstance(value, str):
            out.append(((key,), value, False))
        elif key in ("reasons", "not_stated", "lines", "details") and isinstance(value, list):
            for i, v in enumerate(value):
                said = f"{v.get('text', '')} [{str(v.get('cite', '')).strip('[]')}]" \
                    if isinstance(v, dict) and v.get("cite") else \
                    str(v.get("text", "")) if isinstance(v, dict) else str(v)
                out.append(((key, i), said, False))
    return out


@dataclass
class CheckedCall:
    """A template call through the stack: its arguments with what failed taken out, the places
    in them that failed (what a send-back may change), and every part's drops."""

    args: dict[str, Any]
    failed: list[Place]
    drops: list[dict[str, str]]
    refused: list[str]
    must_cover_misses: list[str]


def _put(kept: dict[str, Any], at: Place, text: str) -> bool:
    """Write a part's checked text back into the arguments; False where nothing of it is left and
    it is a list's item (it goes from the list)."""
    if len(at) == 1:
        kept[str(at[0])] = text
        return True
    if not text.strip():
        return False
    items, i = kept[str(at[0])], int(at[1])
    if isinstance(items[i], dict):
        items[i]["text"] = re.sub(r"\s+([.!?])$", r"\1", CITE.sub("", text).strip()) \
            if items[i].get("cite") else text
    else:
        items[i] = text
    return True


#: 625: every list-typed argument of an offered tool, and where one sent as a string splits: None
#: at line breaks (its own non-blank lines), else at the pattern (names at commas and semicolons
#: too, ids and the years at spaces as well), never into letters
SPLITS: dict[str, str | None] = {
    "details": None, "reasons": None, "not_stated": None, "lines": None,
    "activities": r"[\n,;]", "to": r"[\n,;]", "classes": r"[\s,;]", "years": r"[\s,;]",
    "next_steps": None}


def as_list(value: Any, split: str | None = None) -> list[Any]:
    """625 (624's `graph_lines`): a list argument as a list; a string sent whole is its non-blank
    lines (or its items at `split`), never its letters; one other value is one item, never its
    keys."""
    if isinstance(value, str):
        if split is None:
            return [x for x in value.splitlines() if x.strip()]
        return [x.strip() for x in re.split(split, value) if x.strip()]
    return list(value) if isinstance(value, list | tuple) else [] if value is None else [value]


#: 755: the lists of lines the model may send a line of as an object (`reasons` has its own reader)
_LINE_LISTS = ("details", "not_stated", "next_steps")
_BRACKET = re.compile(r"\[[^\[\]]+\]")
NO_TEXT = "the model sent this line with no text, so it was not shown"


def _has_no_text(line: Any) -> bool:
    """755: an object with no words to show."""
    return isinstance(line, dict) and not (
        isinstance(line.get("text"), str) and line["text"].strip())


def _line_said(line: dict[str, Any]) -> str:
    """755: a line sent as an object as a line: its text, then a bracket for each `cite` and
    `cites` the text does not hold yet. Its other keys are no part of the line."""
    said = str(line["text"]).strip()
    for cite in (*as_list(line.get("cite")), *as_list(line.get("cites"))):
        for bracket in _BRACKET.findall(each_cite(f"[{cite.strip('[] ')}]")
                                        if isinstance(cite, str) else ""):
            opened = set(cites(bracket, {}))
            if bracket not in each_cite(said) and not (opened and opened <= set(cites(said, {}))):
                # a table row's cite goes in its last cell, or the row has a cell too many
                said = f"{said[:-1].rstrip()} {bracket} |" \
                    if said.startswith("|") and said.endswith("|") else f"{said} {bracket}"
    return said


def no_text_drops(args: dict[str, Any]) -> list[dict[str, str]]:
    """755: what `arrived` takes out of these arguments, as drops: named by its keys, never its
    contents, which are not rescued."""
    return [{"text": f"a line with no text ({', '.join(map(str, x))})", "reason": NO_TEXT}
            for k in _LINE_LISTS for x in as_list(args.get(k)) if _has_no_text(x)]


def arrived(args: dict[str, Any]) -> dict[str, Any]:
    """625: a tool call's arguments as they arrive, each list one sent as a string (or one value)
    read once here (`as_list`), so no later reader, the retry and the send-back included, sees
    anything but a list. 755: and each line of `_LINE_LISTS` sent as an object is its text with
    its cites (`_line_said`); one with no text goes from the list (`no_text_drops`)."""
    listed = {k: as_list(v, SPLITS[k]) if k in SPLITS and v is not None
              and not isinstance(v, list) else v for k, v in args.items()}
    return {k: [_line_said(x) if isinstance(x, dict) else x for x in v if not _has_no_text(x)]
            if k in _LINE_LISTS and isinstance(v, list) else v for k, v in listed.items()}


def graph_lines(value: Any) -> list[Any]:
    """624: a graph answer's `lines` as lines (`as_list`). The check and the answer text both
    read the value here."""
    return as_list(value)


def check_call(template: str, args: dict[str, Any], room: Room, must_cover: Iterable[str] = (),
               code_lists: dict[str, list[str]] | None = None,
               drawn: Iterable[str] = ()) -> CheckedCall:
    """Each part of a template call through `check`; the lists code handed and the must-cover
    items are read over the parts together, the items the drawn graph shows (`drawn`, 632) covered.
    A chart's caption may name its own classes and years with no cite: code checks those against
    the call's arguments (the probe's note 5)."""
    drawn, must_cover = list(drawn), list(must_cover)
    args = arrived(args)
    kept = json.loads(json.dumps(args))
    if template == "impact_chart":
        room = dataclasses.replace(room, known=room.known | set(room.classes) | {
            str(y) for y in args.get("years") or []})
    out = CheckedCall(kept, [], [], [], [])
    if template == "graph_link":  # 536 (488): at most three plain lines, then code's link
        lines = graph_lines(kept.get("lines"))
        # 632: a line naming a must-cover item the graph draws (one it covers) is never cut;
        # 654: each item buys one such line, the first naming it, and a later line is plain; a
        # longer name is read first and taken out, so a shorter one inside it is not named there
        must = {_said(m) for m in must_cover}
        covers = [(d, re.compile(rf"(?<!\w){re.escape(d)}(?!\w)"))
                  for d in sorted(must & set(map(_said, drawn)), key=len, reverse=True)]
        left, plain = {d for d, _ in covers}, []
        for i, x in enumerate(lines):
            rest, named = _said(str(x)), set()
            for d, pattern in covers:
                rest, n = pattern.subn("\0", rest)
                named |= {d} if n else set()
            plain += [] if named & left else [i]
            left -= named
        cut = set(plain[GRAPH_LINES:])
        out.drops += [{"text": str(lines[i]), "reason": GRAPH_LINES_REASON.format(n=GRAPH_LINES)}
                      for i in sorted(cut)]
        kept["lines"] = [x for i, x in enumerate(lines) if i not in cut]
        args = kept
    gone: dict[str, list[int]] = {}
    points = [t for at, t, _ in parts(template, args) if at[0] == "details" and len(at) > 1]
    for at, said, body in parts(template, args):
        on = _on_the_plan(said, room) if template == "briefing" and at == ("answer",) else room
        c = _lead(said, points, on, template) if at == ("answer",) and points else \
            check(said, on, body=body, held=template == "letter")
        if at[0] == "not_stated" and (slot := _denies_code(_not_stated_said(_bare(said)), on)):
            c = Checked("", [{"text": said.strip(), "reason": slot}])
        out.drops += c.drops
        out.failed += [at] if any(not cite_miss(d["reason"]) for d in c.drops) else []
        if c.text != said and not _put(kept, at, c.text):
            gone.setdefault(str(at[0]), []).append(int(at[1]))
    for key, idx in gone.items():
        kept[key] = [v for i, v in enumerate(kept[key]) if i not in idx]
    out.must_cover_misses, out.refused = covered(
        "\n".join(t for _, t, _ in parts(template, kept)), must_cover, code_lists, drawn)
    return out


#: 679: a line denying a date is due, or calling a row met ("not been done" calls it no such thing)
_DENIES_DUE = re.compile(
    r"(?:\b(?:not|never|no longer|nothing is|none is)|n['’]t)\s+(?:yet\s+)?(?:over-?)?due\b", re.I)
_CALLS_MET = re.compile(
    r"\b(?:finished|complete[d]?|confirmed|reviewed|closed|signed off|up to date|on time|met"
    r"|approved|passed|resolved|concluded|held|updated|(?:re-?)?interviewed|next (?:review|year)"
    r"|(?<!not )(?<!not been )(?<!not yet )(?<!not yet been )done)\b", re.I)


#: 679 r4 (23's amend): what a line about the turn's own BIA opens on, past `_BRIEFING_WORD`. "IT"
#: is no "it", and a review or record of something else is not the BIA.
_OF_THE_BIA = re.compile(
    r"^(?:to print\s*[—–-]\s*)?(?:for\s+)?(?:(?:the|its|this|his|her|their)\s+)?"
    r"(?:BIA|(?-i:[Ii]t)|re-?interview|review|record)\b(?!\s+of\b)", re.I)
_BRIEFING_WORD = re.compile(r"^\W*(?:(?:the|your)\s+)?briefing(?:\s+to\s+print)?\b\W*", re.I)


def _on_the_plan(said: str, room: Room) -> Room:
    """679 (B7): a briefing's first line says why now from the programme plan: the due date of the
    row of the ONE activity it names, said whole with its year and as its due date (`_said_due`),
    needs no cite. A line naming none takes the turn's activity only where it is about that BIA
    (`_OF_THE_BIA`) or names it loosely: a line titled by another subject lends nothing, and
    nothing is lent past another's loose name. Any other date still needs its cite."""
    bare, folder = _bare(said), room.folder
    loose = {*core.loosely_named(folder, bare), *core.run_named(folder, bare)}
    about = _OF_THE_BIA.search(_BRIEFING_WORD.sub("", bare))
    on = core.named_in(folder, bare) or ([room.activity] if room.activity and (loose or about)
                                         else [])
    if not loose <= {*on}:
        on = []
    names = {core._map_key(core.process_name(folder, a)) for a in on}
    return dataclasses.replace(room, known=room.known | {
        r[4] for r in core._plan_table(folder)[1]
        if len(names) == 1 and core._map_key(r[1]) in names and _said_due(bare, r)})


def _said_due(bare: str, row: list[str]) -> bool:
    """679 r3: only an overdue row (its status says so) lends its due date, said once, "due on",
    "due since" or "overdue since". A met row lends nothing: a briefing's why now off it is "late",
    and false, in whatever words. A line denying the date is due, or calling the row met, lends
    nothing either: each needs its cite, as on base."""
    if (not row[5].lower().startswith("overdue")
            or len(re.findall(rf"(?<!\d){re.escape(row[4][:-5])}", bare)) != 1
            or _DENIES_DUE.search(bare) or _CALLS_MET.search(bare)):
        return False
    return bool(re.search(
        rf"\b(?:due(?: date)?(?: was| is|:)?(?: on| since)?|overdue since) {re.escape(row[4])}",
        bare, re.I))


def _lead(said: str, points: list[str], room: Room, template: str = "") -> Checked:
    """640 (b): a first line over the points listed under it. Its own count of things (its first,
    in digits) is the points' (`answer_shapes` reads it against them), never a cited line's,
    where no other figure of the line says the same digits; and a line that fails with no cite of
    its own stands where the points' cites hold what it says.
    648: a `spof` lead's count said to have no workaround is code's (`core.no_workaround` for the
    activity that clause names, else the turn's): one that differs is dropped, never rewritten, and
    with no activity it is no known figure. It borrows only the cites, read this turn, of rows of
    that activity stating none (`_states_absence`).
    656: a count of single points of failure is `core.spof`'s flagged rows, the same way; and in
    "4 dependencies, two with no workaround" the "two" is `core.no_workaround`'s (the 4, the
    points')."""
    bare = _bare(said)
    m = LISTED.search(bare)
    on = None
    if template == "spof":
        w = NO_WORKAROUND_SAID.match(bare, m.end()) if m else None
        s = SPOF_COUNTED.match(bare, m.end()) if m and m[2].lower().startswith("single point") \
            else None
        a = NO_WORKAROUND_AFTER.match(bare, (s or m).end()) if m and not w else None
        last = a or s
        on = core.named_in(room.folder, bare[m.start():w.end()] if m and w else
                           bare[:last.end()] if last else bare)[:1] or (
            [room.activity] if room.activity else [])
        counted = [(m[1], m[2], core.no_workaround)] if m and w else []
        counted += [(m[1], m[2], _flagged)] if m and s else []
        counted += [(a["n"], a["what"], core.no_workaround)] if a else []
        for n, what, rows in counted if on else []:
            if (code := len(rows(room.folder, on[0]))) != _number(n):
                return Checked("", [{"text": said.strip(), "reason": COUNT_OFF.format(
                    said=n, what=what, count=code)}])
        if on and a and a["n"].isdigit():
            room = dataclasses.replace(room, known=room.known | {a["n"]})
    if m and m[1].isdigit() and NUMBER.findall(bare).count(m[1]) == 1 and (
            on is None or bool(on and (w or s))):
        room = dataclasses.replace(room, known=room.known | {m[1]})
    c = check(said, room)
    if not c.drops or CITE.search(each_cite(said)):
        return c
    lent_by = points if on is None else [
        p for p in points if any(_states_absence(evidence(room.folder, *at), room.folder, on)
                                 for at in cites(p, room.read) if at in room.read)]
    theirs = " ".join(dict.fromkeys(m[0] for p in lent_by for m in CITE.finditer(each_cite(p))))
    if not theirs:
        return c
    lent = check(re.sub(r"(?=[.!?]?\s*$)", f" {theirs}", said, count=1), room)
    if lent.drops:
        return c
    lent.text = lent.text.replace(f" {theirs}", "")
    return lent


def _changes(a: Any, b: Any, at: Place, failed: list[Place]) -> list[Place]:
    """Where `b` differs from `a`, outside the failed places (a failed list item may change or
    go)."""
    if any(at[:len(f)] == f for f in failed):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for k in dict.fromkeys([*a, *b])
                for p in _changes(a.get(k), b.get(k), (*at, k), failed)]
    if isinstance(a, list) and isinstance(b, list):
        out = [i for i in range(len(a)) if any(f == (*at, i) for f in failed)]
        kept = [x for i, x in enumerate(a) if i not in out]
        it = iter(b)
        if all(any(x == y for y in it) for x in kept) and len(b) - len(kept) <= len(out):
            return []
        return [at] if len(a) != len(b) or out else [
            p for i, (x, y) in enumerate(zip(a, b, strict=True))
            for p in _changes(x, y, (*at, i), failed)]
    return [] if a == b else [at]


def _fill(first: list[Any], again: list[Any], fails: set[int]) -> list[Any]:
    """650 (658): a list holding failed items, after a retry that changed it beyond them: each
    passed item the first try's, each failed one the retry's new item at its place, else its next
    new one, and gone where the retry brings none; one the retry left as it was stays (and fails
    again: a change elsewhere is no fix)."""
    new = [y for y in again if y not in first]

    def fixed(i: int) -> Any:
        if i < len(again) and again[i] == first[i]:
            return first[i]
        y = again[i] if i < len(again) and again[i] in new else next(iter(new), None)
        if y is not None:
            new.remove(y)
        return y
    return [y for i, x in enumerate(first) if (y := fixed(i) if i in fails else x) is not None]


def _keep(kept: Any, first: Any, at: Place, fails: set[int]) -> Any:
    """`kept` with the part at `at` as `first` has it (gone where `first` has none; a list holding
    failed items `fails`, filled from `kept` by `_fill`)."""
    if not at:
        return _fill(first, kept, fails) if fails and isinstance(first, list) and isinstance(
            kept, list) else first
    head, *rest = at
    if isinstance(kept, dict) and isinstance(first, dict):
        if head not in first:
            return {k: v for k, v in kept.items() if k != head}
        return {**kept, head: _keep(kept.get(head), first[head], tuple(rest), fails)}
    if isinstance(kept, list) and isinstance(first, list) and isinstance(head, int):
        return [_keep(x, first[i], tuple(rest), fails) if i == head else x
                for i, x in enumerate(kept)]
    return first


def _retry_reason(p: Place, first: dict[str, Any], again: dict[str, Any], kept: dict[str, Any],
                  fails: set[int]) -> str:
    """660: what a retry's change at `p` did. "Had passed" is said of a passed part it changed or
    left out alone: of the place, or of a list holding failed `fails`; beside a fix (`RETRY_FIX`)
    of those items by name."""
    path = ".".join(map(str, p))
    if not fails:
        return RETRY_CHANGED.format(path=path)
    was, said = as_list(first.get(str(p[0]))), as_list(again.get(str(p[0])))
    lost = [f"{path}.{i}" for i, x in enumerate(was) if i not in fails and x not in said]
    if any(y not in was for y in as_list(kept.get(str(p[0])))):
        return "; ".join([RETRY_FIX.format(path=path),
                          *([RETRY_CHANGED.format(path=", ".join(lost))] if lost else [])])
    return (RETRY_CHANGED if lost else RETRY_OVER).format(path=path)


def _owed_rows(first: dict[str, Any], again: dict[str, Any], rows: list[Any],
               must_cover: Iterable[str]) -> list[Any]:
    """761: the retry's new `details` items, not in `rows`, naming an item of the list code handed
    that no `details` item of the first try names. None where the first try drew no `details`."""
    if "details" not in first:
        return []
    owed = [_said(m) for m in covered(" ".join(map(str, as_list(first["details"]))), must_cover)[0]]
    said = as_list(again.get("details"))
    return [y for i, y in enumerate(said) if y not in rows and y not in said[:i]
            and any(m in _said(str(y)) for m in owed)]


def retry(first: dict[str, Any], again: dict[str, Any], failed: list[Place],
          must_cover: Iterable[str] = ()) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """A retry after a send-back may change only what failed. 650 (658): the arguments that stand
    are the retry's, with every place it changed outside the failed ones as the first try had it
    (each such change a drop, `_retry_reason`), so its fix to a failed place stands beside the first
    try's parts that passed. 761: a new `details` item naming an item of the list code handed that
    no `details` item of the first try names stands too, after those kept."""
    kept: dict[str, Any] = again
    changed = _changes(first, again, (), failed)
    held = {p: {int(f[len(p)]) for f in failed if len(f) > len(p) and f[:len(p)] == p}
            for p in changed}
    for p, fails in held.items():
        kept = _keep(kept, first, p, fails)
    rows = as_list(kept.get("details"))
    new = _owed_rows(first, again, rows, must_cover)
    stands = {**kept, "details": [*rows, *new]} if new else kept
    return stands, [{"text": ".".join(map(str, p)) or "the call",
                     "reason": RETRY_ROWS.format(path="details")
                     if new and p == ("details",) and not fails
                     else _retry_reason(p, first, again, kept, fails)}  # 660's read, without them
                    for p, fails in held.items()
                    if p != ("details",) or stands.get("details") != again.get("details")]


def passed(first: dict[str, Any], failed: Iterable[str]) -> dict[str, Any]:
    """630: the parts of a letter call sent back that passed, which its retry keeps where it leaves
    them out (a part it sends is its own); a part that failed is never carried over. A template
    call's retry is held to its failed places instead (`retry`)."""
    out = set(failed)
    return {k: v for k, v in first.items() if k not in out}


def next_steps(proposed: Iterable[str], room: Room, most: int = 5) -> list[str]:
    """The model's next steps a tool of this room can do now (ADR-0045 amended), at most `most`."""
    return [s for s in proposed if any(call and reads(s) for reads, _, call in room.offers)][:most]
