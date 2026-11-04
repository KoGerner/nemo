"""What a record is, and the fingerprint that identifies one.

Split out of `nemo.graph` (gone since ticket 243, ADR-0040) because two layers above needed it.
The walk binds stage 4's receipt to a record by this fingerprint. The ask lane's own property —
that asking touches no **record** (ticket 11) — is that same fingerprint taken before and after,
over a record read back through `nemo.room_store`, so the thing both need lives below them both.

The type alias is here for the same reason: `nemo.graph` and `nemo.room_store` each spelled
`Record` for themselves, and two spellings of one idea is how the two drift apart.

`DEPARTMENT` arrived by the same road at ticket 14. The name a room's files give a process is a
field two layers read: `nemo.interview` finds it in a transcript's front matter, and `nemo.evidence`
finds it on a register entry to see who holds an asset. `nemo.evidence` had it by importing
`nemo.interview` — one string's worth of need, in exchange for an edge from the module that reads
no disk to the module that is the disk reader, and pointing at the one thing in it that has nothing
to do with reading a file. So the word both need lives below both, and neither imports the other.

Nothing here reaches the disk, the clock or the network. A fingerprint is a function of a record
and of nothing else.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

#: A record is a JSON object in a room folder. One spelling, annotated against by both layers.
Record = dict[str, Any]

#: The name a room's files give a process. Both of the room's sources spell it the same way,
#: because a manager presses the name rather than typing it, and two spellings would offer the
#: same process twice. In a transcript it is a `department:` line in the front matter; on a
#: dependency register's entry it is the field that says which department holds the asset.
DEPARTMENT = "department"

#: The fields of an activity in the record, spelled once for the layer that writes them and the
#: two that read them back. `nemo.bia` assembles an activity and `nemo.referee` judges one; the
#: referee and the builder are siblings that may not import each other, so the words both need
#: live here.
#:
#: A drift between the writer's spelling and the judge's is silent in the direction that matters:
#: `activity.get("mtpd")` on an activity that files the figure under any other name reads `None`,
#: and the referee's answer to a figure nobody stated is to say nothing about it. A renamed
#: `EVIDENCE` or `IMPACT_GRID` is worse still — the judge reads `or []`, finds nothing to check,
#: and passes an activity it never looked at. That is the shape of the defect stage 4 exists to
#: close, arriving as two string literals instead of as a seeded file.
ACTIVITIES = "activities"
IMPACT_GRID = "impact_grid"
EVIDENCE = "evidence"
#: Ticket 376 (ADR-0050): the named acknowledgement of a band the source left unrated in every
#: category, under the band it acknowledges: `{band: {approved_by, reason, review_owner}}`.
UNRATED_BAND_ACK = "unrated_band_ack"
DEPENDENCIES = "dependencies"

#: What the record carries about the walk it came out of, beside the activities. `nemo.bia` writes
#: them and `nemo.views` reads them back: the department the BIA is about, the room's own method,
#: and what the walk left open. The method is in the record because a view is a function of the
#: record bytes — a document that had to go to the room for the horizons it lays a grid over could
#: be rendered twice from one record and come back different.
DEPT = "dept"
METHOD = "method"
OPEN_ITEMS = "open_items"
NAME = "name"

#: Who the record has stating this activity's own figures — the person a sign-off for it has to
#: come from (ticket 18). It is in the record rather than read back out of the interview at the
#: signature, because the authority check and the document that names the signer must both be a
#: function of the record bytes: a walk that went to the transcript for it would check a file
#: somebody could edit between the acceptance and the signature.
OWNER = "owner"

#: What this BIA refers to the risk assessment, and to whom. No stage writes one yet and the
#: handover says so rather than staying silent; the word lives here so the stage that comes to
#: write them and the document that reads them back cannot spell it apart.
REFERRALS = "risk_referrals"
REFERS = "refers"
REFERRED_TO = "to"
#: Ticket 256: the run's referrals, each a `{REFERS, REFERRED_TO}` row, written by `walk.refer` and
#: carried into the record's `REFERRALS` by `bia.build` when the record lands.
PENDING_REFERRALS = "pending_referrals"

#: What a reservation nobody named is recorded as. Never rounded up to an endorsement, never
#: refused either: nothing in the walk may punish a disagreement (`docs/voice.md` §4.3). Below
#: both the stage that records it and the handover that carries it to the signature, so the two
#: cannot come to disagree about what an unnamed reservation looks like.
UNNAMED = "unnamed"

#: The run's own fields — the walk's file beside the record, which is a record like any other.
#: Two layers need them and neither may import the other: `nemo.walk` writes a decision at every
#: stage and reads its own file back to see which stage a manager has reached, and `nemo.handover`
#: carries every reservation and every finding from those same decisions onto the documents. The
#: handover sits below the walk and may not import it, so until ticket 18's architect pass the
#: lower layer spelled the upper layer's shape for itself and the upper layer wrote the same keys
#: as bare literals — two spellings of one idea, which is the drift `Record` and `DEPARTMENT` are
#: down here to prevent. A key that is renamed on one side and not the other is silent in the worst
#: direction: `run.get("decisions", [])` over a run that files them under anything else is an empty
#: list, and a handover rendered from an empty list carries no reservation and says the walk
#: endorsed everything as it stood.
DECISIONS = "decisions"
AT_STAGE = "stage"

#: What a decision carries besides the answer itself, so that one real walk can be read after the
#: fact by somebody who was not watching it: **when** it was taken, **which card** it was taken on,
#: and **what the referee refused** over the record it saved. Those are the four questions a walk
#: has to answer to be worth anything as evidence — where he stalled, what nemo refused him, what
#: he was looking at, how long it took — and until ticket 2026-09-20 the only answers were an
#: operator's handwritten turnlog. They are a record of what happened and never a check on it.
#:
#: A refusal is kept the way `nemo.refusal` hands it over — a kind and the parts it was found in —
#: and never as the sentence a manager read: `nemo.walk.REFUSAL_SAYS` stays the one place the words
#: live, so a refusal re-read a year from now is re-worded by today's walk rather than frozen in
#: yesterday's prose. These are here rather than in the walk for the reason `DECISIONS` is: the
#: handover reads the same list from below and may not import the module that writes it.
AT_TIME = "at_time"
ON_CARD = "card"
#: `REFUSALS` rather than `REFUSED`, because `nemo.walk` already spells the *sentence* a refused
#: card carries under that name and one of the two would have shadowed the other in every file
#: that reads both.
REFUSALS = "refused"
KIND = "kind"
PARTS = "parts"
GRADIENT = "gradient"
NAMING = "naming"
FINDINGS = "findings"
STATUS = "status"

#: t71: the reservations a reopen carried over from the answers it undid, each `{AT_STAGE, NAMING}`.
#: A reopen puts the run back as it stood when stage 3 closed, and every reservation made after
#: that still stands until he signs.
CARRIED = "carried_reservations"
#: t71b: the notes a tool call supplied with a decision, which are never his reason: kept for the
#: audit trail and marked as whose they were. No view reads them, and a reopen never undoes them.
MODEL_NOTES = "model_notes"

#: The signature, and the fields it lands under. The name and the role are the two things a human
#: types here; the capacity is not typed and cannot be — what capacity a signature was given in is
#: decided against the owner the record holds — and the accepted ids are the ids the signer was
#: shown. The walk writes this and the certificate reads it back, so the words live below both.
SIGNATURE = "signature"
SIGNER = "name"
ROLE = "role"
ACCEPTED = "accepted"
CAPACITY = "capacity"

#: The four figures an activity carries, under the names the record files them as. The labels a
#: human reads them by are `nemo.evidence.LABELS`; these are what the JSON says.
MTPD = "mtpd"
RECOVERY_TARGET = "recovery_target"
RPO = "rpo"
MBCO = "mbco"

#: t116: the manager's answers to the referee's questions on this activity, keyed by the question
#: (`referee.ASSERTED_MTPD`). Each carries both figures it answered, so an answer to figures the
#: record no longer holds answers nothing (12_nemo_check's amendment 1).
ANSWERS = "answers"

#: The two things the worksheet is asked for per activity that no stage writes yet: the recovery
#: target and the recovery point **per data set**, and the minimum resources over time with the
#: workaround per resource. The names live here, with the rest of the record's vocabulary, so the
#: stage that comes to write them and the view that reads them cannot spell them apart. A record
#: that carries neither is a record with a gap in it, and `nemo.views` says so rather than filling
#: it in from the room.
DATA_SETS = "data_sets"
RESOURCES = "resources"
BY_WHEN = "by_when"
WORKAROUND = "workaround"

#: One evidence item: what kind of thing it is, the exact words, the file they came from, and the
#: impact category the words support where they support one.
TYPE = "type"
QUOTE = "quote"
SOURCE_PATH = "source_path"
LENS = "lens"
#: Every other file the same words were found in, after the one `source_path` names (ticket 131,
#: ADR-0030 decision 3). Data, never a sentence: the signed documents add no line for it.
ALSO_IN = "also_in"

#: The one kind of evidence this walk writes: a quote from the interview the manager bound. The
#: referee allows more kinds than the builder produces (v1 records carry the others), so the
#: shared word is this one and the allow-list stays where it is enforced.
TRANSCRIPT_QUOTE = "transcript_quote"

#: A figure the manager confirmed in chat (ticket 132, ADR-0030): his confirmation, never a quote.
#: nemo writes it from the room's turn file (`nemo.turn_file.his_turns`), never from a model call's
#: arguments: his `WORDS` on that turn (for a tap, the words it showed him), the day it was `ON`,
#: and the `TURN_ID`. A record signed before it may carry `manager_confirmed`, the prototype's old
#: spelling; it is read as it stands and never judged again (ruling A).
CHAT_CONFIRMATION = "chat_confirmation"
WORDS = "words"
ON = "on"
TURN_ID = "turn_id"

#: The register-derived RPO's evidence (ticket 171): the dependency register's own row for one
#: asset the figure was derived from, `{ACTIVITY, ASSET_ID, QUOTE, SOURCE_PATH}`, with the QUOTE the
#: value that asset gives THAT activity: its consumer row for the activity where the entry has
#: `consumers`, else the entry's own (t171-shape, a DRAFT awaiting the owner). Checked against the
#: room's register like a quote, and the ACTIVITY is the record's own department.
REGISTER_ROW = "register_row"
ASSET_ID = "asset_id"
ACTIVITY = "activity"
#: The register giving an activity no RPO (190 x t171-shape, DRAFT): `{ACTIVITY, ASSET_IDS,
#: SOURCE_PATH}`. Checked by confirming that no dependency it lists, nor any the activity lists,
#: names a figure for that activity in the room's register.
REGISTER_NO_RPO = "register_no_rpo"
ASSET_IDS = "asset_ids"

# The compact bytes the fingerprint is taken over. `ensure_ascii=False` keeps the record's own
# characters, because a digest over `ä` is a digest over the escaping rather than over the
# record. An encoder rather than a `json.dumps(...)` call so the spelling is stated once, in one
# place, and cannot drift away from the digest that depends on it.
_CANONICAL = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(record: Record) -> str:
    """The record's identity: the SHA-256 of its canonical bytes.

    Canonical, so two records that differ only in key order are one record. The digest is what
    the page carries and what a receipt binds on (ticket 17) — never the page's own bytes, which
    a re-render changes without the record having moved.
    """
    return hashlib.sha256(_CANONICAL.encode(record).encode()).hexdigest()
