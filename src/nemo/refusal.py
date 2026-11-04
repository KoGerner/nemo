"""The vocabulary of refusal, below the module that raises one and the module that words it.

`nemo.referee` decides that a record cannot be saved. `nemo.walk` writes the sentence the manager
reads about it. Neither owns both halves and neither may be the other's source for the names, so
the names sit here — the same placement, and for the same reason, as `nemo.record`'s field names
below `nemo.bia` and `nemo.handover`, `nemo.method`'s parameter names below the referee and the
walk, and `nemo.text`'s one normalizer below everything that compares two strings.

It is the seam `nemo.text`'s docstring predicted: *"the referee's findings travel to the card, so
the day a finding needs formatting the import would come back the other way."* That day is this
ticket. What travels is a `Rejection` — a **kind** and the **parts** the record put against it, the
activity, the impact category, the time bands — and never a sentence. Every sentence the referee
ever wrote was written for a developer, which is how `impact_grid['legal-regulatory'] missing
horizon(s): ['72 h']` reached a manager's screen on a live stage 4 card.

**A kind with no words is a card nobody can read.** `nemo.walk.REFUSAL_SAYS` holds a sentence for
every name in `KINDS` and a test up there pins the two lists together, which is why `KINDS` is a
list and not a reading of the referee's source. A ticket that adds a way of refusing adds the name
here, raises it there, and words it in the walk; leaving any one of the three out is red.

This module imports nothing. It is names and one small type, and a name is not a judgement.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# ── every way a record can be refused, as a name rather than as a sentence ───
MISSING_HORIZONS = "missing-horizons"
UNKNOWN_HORIZONS = "unknown-horizons"
INVALID_SCORE = "invalid-score"
UNREADABLE_ROW = "unreadable-row"
UNREADABLE_GRID = "unreadable-grid"
UNKNOWN_LENS = "unknown-lens"
MISSING_LENSES = "missing-lenses"
BAND_UNSCORED = "band-unscored"
UNSCORED_NEEDS_OWNER = "unscored-needs-owner"
UNRATED_BAND_NEEDS_OWNER = "unrated-band-needs-owner"
REVIEW_DATE_UNUSABLE = "review-date-unusable"
REVIEW_DATE_PASSED = "review-date-passed"
LENS_UNQUOTED = "lens-unquoted"
UNSIGNED_ACK = "unsigned-ack"
QUOTE_NOT_FOUND = "quote-not-found"
EVIDENCE_UNCHECKED = "evidence-unchecked"
UNREADABLE_EVIDENCE = "unreadable-evidence"
NO_RECOVERY_TARGET = "no-recovery-target"
UNREADABLE_TARGET = "unreadable-target"
TARGET_OUTSIDE_MTPD = "target-outside-mtpd"
RPO_NOT_ALLOWED = "rpo-not-allowed"
BOUNDARY = "over-the-boundary"
HANDOFF_ITEM = "handoff-item"
OWNER_NOT_A_PERSON = "owner-not-a-person"
NO_ACTIVITIES = "no-activities"
MALFORMED_ACTIVITY = "malformed-activity"

#: The whole of it, so that "every way it can refuse" is a list and not a reading of a module.
KINDS = (
    MISSING_HORIZONS, UNKNOWN_HORIZONS, INVALID_SCORE, UNREADABLE_ROW, UNREADABLE_GRID,
    UNKNOWN_LENS, MISSING_LENSES, BAND_UNSCORED, UNRATED_BAND_NEEDS_OWNER, UNSCORED_NEEDS_OWNER,
    REVIEW_DATE_UNUSABLE,
    REVIEW_DATE_PASSED, LENS_UNQUOTED, UNSIGNED_ACK, QUOTE_NOT_FOUND, EVIDENCE_UNCHECKED,
    UNREADABLE_EVIDENCE, NO_RECOVERY_TARGET, UNREADABLE_TARGET, TARGET_OUTSIDE_MTPD,
    RPO_NOT_ALLOWED, BOUNDARY, HANDOFF_ITEM, OWNER_NOT_A_PERSON, NO_ACTIVITIES,
    MALFORMED_ACTIVITY,
)

#: The one part name both sides spell: the referee reports it, the walk reads each field in it out
#: as the thing it stands for. A field name is not a sentence and never goes on a card.
MISSING = "missing"


class Rejection(str):
    """One refusal, as the parts it was found in: ``kind``, and what the record put against it.

    It is a string as well, and that string is the developer's line — the one a test reads and a
    log holds. It is never what a manager reads: `nemo.walk` writes that sentence out of `kind`
    and `parts`, because a card's words belong to the module that owns every other card string.
    """

    kind: str
    parts: Mapping[str, Any]

    def __new__(cls, kind: str, said: str, **parts: Any) -> Rejection:
        rejection = super().__new__(cls, said)
        rejection.kind = kind
        rejection.parts = parts
        return rejection
