"""PROTOTYPE, throwaway (14_nemo / t71). Every decision the manager made is in what he signs.

v1's last rated run accepted seven reservations and printed "no analytical reservation is recorded";
its certificate read "Signed by: Claude" (M14). This is the comparison nobody made: the run's
decisions against the record, and the record against every view the manager signs over. It runs
when the record is written (stage 4) and again at the signature, and a mismatch refuses the write or
the signature with a `say` naming the item (ticket 67's shape, `PROTOTYPE_core.standing`).

**It reads files nemo writes, and nothing the model composed** (M13): the state file (the step-3
decisions, the reservations nemo took, the reopen's snapshot), the run file, the record, and the
views nemo renders from them — the stage-4 card, the handover, the certificate. Every rule below is
a comparison between two of those.

The rules, per item:
- **a changed figure** (`decide … change value=`): the record carries that value (an RPO in the
  method's word for its duration), on evidence the manager gave (`origin: manager`) with his
  reason. An RPO no tighter than the register's derivation, and an MTPD the method's rule replaced
  at his own choice, may be overridden, but only where the evidence says so in those terms;
- **an acknowledged recovery gap**: the record flags it, on the manager's evidence; a side that
  acknowledges it is a decision about the gap, so the record flags it too. t76: a target he typed
  later never clears it — only his own words closing it do, and then the record carries them;
- **a gap said to be closed**: no view says a gap was closed unless the record carries the words he
  closed it in, and those words are a line he typed (t76);
- **a chosen side**: the record's open items say "settled by the manager on <speaker>'s side:
  <that side's claim>", the speaker as the draft stores it;
- **a conflict left unresolved**: the record carries it as open, and no view calls it settled (t76);
- **an accepted proposal**: the record carries the draft's figure or score row, or, for a figure,
  one the method derives with its reason said (origin `method`);
- **a reservation**: every one nemo took (the state file's ledger) is in the run, word for word,
  and in the handover and the certificate (in the stage-4 card too, once it was made before it);
- **the views**: the stage-4 card, the handover and the certificate state the record's figures, its
  gap, every item still open and every reservation; none says a gap the record does not flag;
- **the record against itself** (t75): no target outside the record's own MTPD without an
  acknowledged gap, and no view saying "not inside" where the record's figures put it inside;
- **the signer**: the name the signature carries is a person's, not the tool's; one who is not the
  owner the record holds signs on behalf of that owner, and the certificate says both;
- **the reopen**: a decision nobody touched since is as it was, and the record signed is the one
  the decisions make now (never one written before them);
- **a model turn** (fix 3): no figure he set is moved or removed by it — the record's figures
  before the turn against after it (`his_figures_kept`, run by `Session.turn`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nemo import handover, walk

import PROTOTYPE_core as core

#: A figure item's field, the label its evidence carries, and the key the record holds it under.
FIELDS = {"mtpd": ("MTPD", "mtpd"), "rto": ("RTO", "recovery_target"), "rpo": ("RPO", "rpo")}
#: Who may never be the signer: the tool, a model, a product. A signature is a person's.
NOT_A_PERSON = re.compile(r"\b(claude|nemo|chat ?gpt|gpt[\w.-]*|deepseek|openai|anthropic|llm|"
                          r"assistant|the tool|the system|ai|bot)\b", re.I)
#: **A fidelity check keys on DATA, and where it must read a rendered view it compares against the
#: product's OWN string — never a copy of one** (7_nemo_check, 2026-09-21). This line held a
#: hand-typed duplicate of `core.GAP_WORDS`; rewording that constant red 21 of 80 walks. Ticket 91
#: is the wording ticket and cannot be briefed into a tree where changing a word does that.
ACKNOWLEDGED_GAP = core.GAP_WORDS.format(account="")
#: The product spells an acknowledged gap FIVE ways, and a check that lists the ones we thought of
#: is the same hand-kept list this build has already lost to three times. So the phrase every view
#: must carry is **computed from the product's own sentences** — the longest run of text they all
#: share — and reworded with them. `_GAP_SAID` names the renderings, not the words: leaving one out
#: LENGTHENS the phrase and reds the walks loudly, where a forgotten word would have passed
#: silently.
_GAP_SAID = (core.GAP_SAYS, core.GAP_ACK_SAYS, core.GAP_CARRIED_SAYS, core.GAP_WORDS, core.GAP)


def _shared(texts: tuple[str, ...]) -> str:
    """The longest run of text every one of these sentences carries, lower-cased."""
    first, rest = texts[0].lower(), [t.lower() for t in texts[1:]]
    runs = (first[i:j] for i in range(len(first)) for j in range(len(first), i, -1))
    return max((r for r in runs if all(r in t for t in rest)), key=len, default="")


GAP_PHRASE = _shared(_GAP_SAID)
#: A verification that can only return one answer is not a verification: if a reword leaves the
#: renderings with nothing meaningful in common, this fails at import rather than passing
#: everything.
assert len(GAP_PHRASE.strip()) >= 8, GAP_PHRASE


def says_gap(text: str) -> bool:
    """Whether a rendered view spells the acknowledged gap, in the product's own shared words."""
    return GAP_PHRASE in text.lower()


CARD, HANDOVER, CERTIFICATE = "the stage-4 card", "the handover", "the certificate"


def says(text: str, value: Any) -> bool:
    """Whether a rendered text states this value as a whole ("4 h" is not in "0–4 h" or "24 h")."""
    v = str(value).strip()
    return bool(v) and re.search(r"(?<![\w.–-])" + re.escape(v) + r"(?![\w])", text) is not None


def _same(a: Any, b: Any) -> bool:
    return " ".join(str(a).split()).lower() == " ".join(str(b).split()).lower()


def _evidence(rec: dict[str, Any], label: str) -> dict[str, Any]:
    return next((e for e in rec.get("evidence") or [] if e.get("label") == label), {})


def reservations(run: dict[str, Any]) -> list[tuple[int, str]]:
    """Every reservation the run carries: those a reopen carried over, then nemo's own namings."""
    carried = [(int(r["stage"]), str(r["naming"])) for r in run.get(core.CARRIED) or []]
    # why: walk takes UNNAMED from nemo.record; reading it there is a code edit
    return carried + [(s, w) for s, w in walk.namings(run) if w != walk.UNNAMED]  # type: ignore[attr-defined]


# ── the decisions against the record ─────────────────────────────────────────────────────────
def decisions_in_record(state: dict[str, Any], record: dict[str, Any],
                        method: dict[str, Any]) -> list[str]:
    draft = state.get("draft") or {}
    decisions = state.get("decisions") or {}
    by_name = {a.get("name"): a for a in record.get("activities") or []}
    acts = {a["id"]: a for a in draft.get("activities") or []}
    conflicts = {c["id"]: c for c in draft.get("conflicts") or []}
    opened = [str(i) for i in record.get("open_items") or []]
    out = []
    for iid, d in decisions.items():
        if iid in conflicts:
            side = d.get("side")
            sides = conflicts[iid].get("sides") or []
            about = conflicts[iid].get("about")
            if isinstance(side, int) and side < len(sides):
                claim = str(sides[side].get("claim"))
                # t76 (6_nemo_check, 2026-09-19): whose side, as the draft stores the speaker
                # t120: with nemo's one line where the record kept another figure, exactly
                kept = core.kept_line(d)
                if core.settled_says(about, sides[side].get("speaker"), claim, kept) not in opened:
                    out.append(
                        f"{iid}: the side the manager took "
                        f"({core._who(sides[side].get('speaker'))}: "
                        f"“{claim[:90]}”) is not in the record's open items"
                    )
                out += _gap_side_in_record(iid, d, sides[side], acts, by_name)
            # t76: a conflict he left unresolved has `left_unresolved` to itself, below
            continue
        aid, _, key = iid.partition(".")
        act = acts.get(aid)
        rec = by_name.get((act or {}).get("name"))
        if act is None:
            continue
        if rec is None:
            out.append(f"{iid}: the record holds no activity {act.get('name')!r}")
            continue
        if key.startswith(f"{core.DEP}."):
            # 195: a dependency he added is on the record, once, and the record says he added it
            asset = core.dep_asset(iid)
            if d.get("decision") == "accept" \
                    and (rec.get("dependencies") or []).count(asset) != 1:
                out.append(f"{iid}: the manager added {asset} as a dependency, and the record "
                           f"lists it {(rec.get('dependencies') or []).count(asset)} times")
        elif key in FIELDS:
            out += _figure_in_record(iid, key, d, act, rec, decisions, method)
        elif isinstance((act.get("grid") or {}).get(key), dict):
            out += _row_in_record(iid, key, d, act, rec)
    return out


def _figure_in_record(
    iid: str,
    key: str,
    d: dict[str, Any],
    act: dict[str, Any],
    rec: dict[str, Any],
    decisions: dict[str, Any],
    method: dict[str, Any],
) -> list[str]:
    label, field = FIELDS[key]
    if key == "mtpd" and core.withdrawn(decisions, act["id"]):
        return []  # t116: he withdrew it after this decision; `record_is_current` holds the grid's
    got = rec.get(field)
    ev = _evidence(rec, label)
    value = str(d.get("value") or "")
    if d.get("decision") == "change" and value:
        if key == "rto" and "gap" in value.lower():
            if rec.get(core.GAP_CLOSED):
                return []  # t76: he closed it in his own words, and `his_words` holds them to his
            if rec.get("recovery_gap_flagged") is not True:
                return [
                    f"{iid}: the recovery gap the manager acknowledged is not flagged in the record"
                ]
            return _his(iid, "the recovery gap", d, ev)
        want = value
        if key == "rpo":
            want = core.words_by_duration(method).get(core.duration_of(value), value) \
                if value not in method.get(core.RPO_VOCABULARY, []) else value
        same = _same(got, want) or _same(got, value)
        if key == "mtpd" and (decisions.get(f"{act['id']}-MTPD-RULE") or {}).get("side") in (0, 1) \
                and core.rule_is_latest(decisions, act["id"]):
            return []  # fix 3: he took a side of the method's rule after this change (either side)
        if ev.get("origin") == "method":
            # fix 1: the method's figure may stand over his, equal or not, only where the rule says
            # so: an RPO his is not tighter than (equal: the derivation's evidence as it was;
            # looser or no duration: the evidence says so), an MTPD after he took the method's rule
            if key == "rpo" and not core.tighter(value, got) and (
                    same or core.explicit_change(d) is None):
                # fix 1 (the review's finding 7): this branched on the record's own SENTENCE ("The
                # manager's X is not tighter, so the derivation stands."), which is why
                # `PROTOTYPE_core` kept that sentence for the check to read — a check dictating
                # the wording of a signed record, one wording change from refusing a faithful
                # walk, and ticket 91 changes wording next. It keys on the DECISION now: since
                # t93 a figure HE set explicitly is never dropped for the derivation, so the only
                # figure the derivation may stand over is one a conflict side implied (`by`), by
                # t71/t73b's MIN semantics.
                return []
            if (
                key == "mtpd"
                and (decisions.get(f"{act['id']}-MTPD-RULE") or {}).get("side") == 0
                and core.rule_is_latest(decisions, act["id"])
            ):  # fix 2: his latest decision wins
                return []
        if same:
            return _his(iid, f"{label} {value}", d, ev)
        return [f"{iid}: {label} {value}, which the manager set, is not in the record: it carries "
                f"{got or 'no ' + label}"]
    if d.get("decision") == core.DERIVED:
        # fix 1 (the review's finding 6): t93 shipped a THIRD decision kind and this function
        # branched on "change" and "accept" only, so a `derived` decision returned "no problem"
        # whatever the record said about it. `record_is_current` still held the record to the
        # right VALUE, so the hole was provenance, not arithmetic — the record could carry the
        # derivation and say the manager set it, and nothing looked. Keyed on data, never on a
        # sentence: the derivation happened, and his own figure is still underneath it.
        if ev.get("origin") != "method":
            return [f"{iid}: the manager handed {label} to the dependency register, and the "
                    f"record does not carry it as derived: its evidence is "
                    f"{ev.get('origin') or 'none'}"]
        under = core.explicit_change(d.get("over"))
        # t171: his own figure underneath is his act that set it, on its turn, among the RPO's
        # rows: keyed on the decision's turn id, never on a sentence of nemo's
        acts = {e.get(core.TURN_ID) for e in rec.get("evidence") or []
                if e.get("label") == label and e.get(core.TYPE) == core.CHAT_CONFIRMATION}
        if under and not (under.get(core.TURN_ID) and under[core.TURN_ID] in acts):
            return [f"{iid}: the manager set {label} {under['value']} and handed it over, and the "
                    "record does not say so: his own figure is not under the derivation"]
        return []
    if d.get("decision") == "accept":
        proposed = str((act.get(key) or {}).get("value") or "")
        if not proposed:
            return []
        if key == "rto" and "gap" in proposed.lower():
            return [] if rec.get("recovery_gap_flagged") is True or rec.get(core.GAP_CLOSED) else \
                [f"{iid}: the recovery gap the manager accepted is not flagged in the record"]
        if _same(got, proposed) or (got and ev.get("origin") == "method"):
            return []
        if key == "rpo" and core.no_rpo(rec):
            return []  # 190: no dependency holds data, so the method gives no RPO, and says so
        return [f"{iid}: the accepted {label} {proposed} is not in the record: it carries "
                f"{got or 'no ' + label}, and no derivation says why"]
    return []


def _gap_side_in_record(iid: str, d: dict[str, Any], side: dict[str, Any], acts: dict[str, Any],
                        by_name: dict[str, Any]) -> list[str]:
    """fix 4: a side that acknowledges the recovery gap is a decision about the gap: the record
    flags it. t76 (the owner's ruling, 2026-09-19): a later decision on the RTO no longer replaces
    it — a changed target never clears an acknowledged gap — so only his own words closing it do,
    and the record then carries them (`GAP_CLOSED`)."""
    implied = side.get("implies") if isinstance(side.get("implies"), dict) else {}
    # why: `implied` is a dict: the isinstance on the line above chose it
    target = str(implied.get("item_id") or "")  # type: ignore[union-attr]
    # why: `implied` is a dict, as above
    if not (target.endswith(".rto") and core.is_gap(implied.get("value"))):  # type: ignore[union-attr]
        return []
    act = acts.get(target.split(".")[0]) or {}
    # why: `.get(None)` finds nothing, and `or {}` follows
    rec = by_name.get(act.get("name")) or {}  # type: ignore[arg-type]
    if rec.get("recovery_gap_flagged") is True or rec.get(core.GAP_CLOSED):
        return []
    return [f"{iid}: the side the manager took acknowledges a recovery gap for {act.get('name')}, "
            "and the record does not flag it"]


def _his(iid: str, what: str, d: dict[str, Any], ev: dict[str, Any]) -> list[str]:
    """A figure the manager set rests on his evidence. t71b: its reason is no longer required to
    be the decision's note (a tool call's note is the model's); `his_words` holds the reason."""
    if ev.get("origin") != "manager":
        return [f"{iid}: the record does not say that {what} is the manager's decision"]
    return []


def _row_in_record(iid: str, lens: str, d: dict[str, Any], act: dict[str, Any],
                   rec: dict[str, Any]) -> list[str]:
    want = dict(act["grid"][lens].get("scores") or {})
    if d.get("decision") == "change" and d.get("scores"):
        want.update({h: int(v) for h, v in d["scores"].items() if h in want})
    elif d.get("decision") == "reject":
        want = dict.fromkeys(want, core.MISSING)
    got = (rec.get("impact_grid") or {}).get(lens)
    if got != want:
        return [
            f"{iid}: the {lens} scores the manager "
            # why: every stored decision carries its `decision` (accept, reject, change)
            f"{'set' if d.get('decision') == 'change' else d.get('decision') + 'ed'} "  # type: ignore[operator]
            f"({' · '.join(map(str, want.values()))}) are not the record's "
            f"({' · '.join(map(str, (got or {}).values())) or 'none'})"
        ]
    return []


def record_is_current(state: dict[str, Any], record: dict[str, Any], method: dict[str, Any],
                      folder: Path) -> list[str]:
    """The record carries the figures the decisions make now: never one written before them (a
    decision taken after the record was accepted, or a reopen that was not accepted again)."""
    draft = state.get("draft") or {}
    if not draft.get("activities"):
        return []
    now = core.build_proposal(draft, state, method, folder)["activities"]
    by_name = {a.get("name"): a for a in record.get("activities") or []}
    out = []
    for a in now:
        rec = by_name.get(a["name"]) or {}
        meta = {m["label"]: m for m in a["evidence_meta"]}
        for label, field in FIELDS.values():
            want = (meta.get(label) or {}).get("value")
            if want and not _same(rec.get(field), want):
                out.append(f"{label}: the decisions now make it {want}, and the record carries "
                           f"{rec.get(field) or 'none'}")
    return out


def reopen_kept(state: dict[str, Any]) -> list[str]:
    """After a reopen, every decision nobody touched since is as it stood when it was reopened."""
    snap = state.get(core.REOPENED) or {}
    before, touched = snap.get("decisions") or {}, set(snap.get("touched") or [])
    now = state.get("decisions") or {}

    def plain(d: Any) -> Any:
        return {k: v for k, v in (d or {}).items() if k != "at"} if d else None

    return [f"{iid}: changed after the reopen though nobody decided it again"
            for iid, d in before.items() if iid not in touched and plain(now.get(iid)) != plain(d)]


# ── t71b: manager-origin text is his typed line or a tap label, nothing else ────────────────────
#: the sentences nemo adds after the reason in a manager's evidence (`core.build_proposal`)
_AFTER_REASON = re.compile(r"\. (?=He typed |He confirmed |The value given in chat was |"
                           r"The register derives |The manager set |The manager's )")
_HE_TYPED = re.compile(r"He typed (.+?); ")
_BY_CONFLICT = re.compile(r"settled by the manager on conflict (\S+)")


def _plain(text: Any) -> str:
    return " ".join(str(text).split()).rstrip(".")


def his_words(state: dict[str, Any], record: dict[str, Any], run: dict[str, Any],
              said: list[str]) -> list[str]:
    """Every text the record and the run give as the manager's equals a line he typed or a label
    nemo drew for him to tap, word for word (t71b). The texts: the reason in each figure he set
    ("Set by the manager in chat: <reason>."), a value "He typed", and every reservation (the run's,
    and the ledger the views are held to). Allowed besides: nemo's own "no reason given", and
    nemo's own "settled by the manager on conflict <id>" where he did settle that conflict.
    Data against data (M13): his input against nemo's output; nothing here reads for meaning."""
    his = {_plain(line) for line in said}
    decided = set(state.get("decisions") or {})
    out = []
    for a in record.get("activities") or []:
        for ev in a.get("evidence") or []:
            quote = str(ev.get("quote") or "")
            if ev.get("origin") != "manager" or not quote.startswith(core.SET_BY):
                continue
            reason = _plain(_AFTER_REASON.split(quote[len(core.SET_BY):], 1)[0])
            by = _BY_CONFLICT.fullmatch(reason)
            if (
                reason != core.NO_REASON
                and not (by and by.group(1) in decided)
                and reason not in his
            ):
                out.append(
                    f"{ev.get('label')} for {a.get('name')}: the reason “{reason[:90]}” is not a "
                    "line the manager typed, nor a tap he made"
                )
            typed = _HE_TYPED.search(quote)
            if typed and _plain(typed.group(1)) not in his:
                out.append(
                    f"{ev.get('label')} for {a.get('name')}: “He typed {typed.group(1)}”, and "
                    f"{typed.group(1)} is not a line the manager typed"
                )
        # t76: the words a recovery gap was closed with are his own, or the record does not say he
        # closed it. Nothing here reads them for meaning: his input against nemo's output
        closed = str(a.get(core.GAP_CLOSED) or "")
        if closed and _plain(closed) not in his:
            out.append(f"the recovery gap for {a.get('name')} is recorded as closed with "
                       f"“{closed[:90]}”, which is not a line the manager typed")
    ledger = [(int(r["stage"]), str(r["naming"])) for r in state.get(core.RESERVATIONS) or []]
    for stage, words in dict.fromkeys([*reservations(run), *ledger]):
        if _plain(words) not in his:
            out.append(f"the reservation made at step {stage} (“{words[:90]}”) is not a line the "
                       "manager typed")
    return out


# ── the reservations and the views against the record ────────────────────────────────────────
def reservations_kept(state: dict[str, Any], run: dict[str, Any]) -> list[str]:
    """Every reservation nemo took (the state file's ledger) is in the run, word for word."""
    held = reservations(run)
    return [
        f"the reservation made at step {r['stage']} (“{r['naming'][:90]}”) is not in the record"
        for r in state.get(core.RESERVATIONS) or []
        if (int(r["stage"]), r["naming"]) not in held
    ]


def views_say(record: dict[str, Any], run: dict[str, Any], views: dict[str, str],
              ledger: list[dict[str, Any]]) -> list[str]:
    out = []
    items = handover.items(record, run)
    for name, text in views.items():
        for a in record.get("activities") or []:
            for label, field in FIELDS.values():
                if a.get(field) and not says(text, a[field]):
                    out.append(f"{name} does not state {label} {a[field]} for {a.get('name')}")
            if a.get("recovery_gap_flagged") and not says_gap(text):
                out.append(
                    f"{name} does not state the acknowledged recovery gap for {a.get('name')}"
                )
            if a.get(core.GAP_CLOSED) and str(a[core.GAP_CLOSED]) not in text:
                # t76: he closed it in his own words, so every view says them, word for word
                out.append(f"{name} does not state the words the manager closed the recovery gap "
                           f"for {a.get('name')} with")
            if not a.get("recovery_gap_flagged") and any(
                    ACKNOWLEDGED_GAP in line for line in lines_about(text, str(a.get("name")))):
                # fix 4: nor may a view say a gap the record does not flag
                out.append(
                    f"{name} states an acknowledged recovery gap for {a.get('name')}, and the "
                    "record does not flag it"
                )
        for at, item in items:
            if item not in text:
                out.append(f"{name} does not state {at} (“{item[:90]}”)")
        for r in ledger:
            if r["naming"] not in text and (name != CARD or int(r["stage"]) < walk.STAGE_4):
                out.append(f"{name} does not state the reservation made at step {r['stage']} "
                           f"(“{r['naming'][:90]}”)")
    return out


def gap_closed_by_him(record: dict[str, Any], views: dict[str, str]) -> list[str]:
    """t76, the owner's ruling (2026-09-19): a recovery gap closes only on his own words. So no
    view may say a gap was closed unless the record carries the words he closed it in
    (`core.GAP_CLOSED`); `his_words` then holds those words to a line he typed. Data against data:
    nemo's own wording for a close (`core.CLOSED_MARKS`) against the record's own key.

    t79 fix 1: two spellings of that wording, because a document about him for somebody else says
    "he closed" and a stage card says "you closed". Every view is held to both, so no document can
    state a close in either voice without the words on the record.
    """
    out = []
    for a in record.get("activities") or []:
        if a.get(core.GAP_CLOSED):
            continue
        for view, text in views.items():
            if any(mark in line for line in lines_about(text, str(a.get("name")))
                   for mark in core.CLOSED_MARKS):
                out.append(f"{view} says the recovery gap for {a.get('name')} was closed, and the "
                           "record carries no words of the manager closing it")
    return out


def left_unresolved(state: dict[str, Any], record: dict[str, Any],
                    views: dict[str, str]) -> list[str]:
    """t76, the owner's ruling: a conflict he left unresolved is open, never settled. No view says
    a side was taken on it, and the record carries it as an open item. The comparison is the
    draft's own sides against nemo's own wording for a settled conflict (`core.settled_says`)."""
    decisions = state.get("decisions") or {}
    opened = [str(i) for i in record.get("open_items") or []]
    out = []
    for c in (state.get("draft") or {}).get("conflicts") or []:
        if (decisions.get(c["id"]) or {}).get("decision") != core.UNRESOLVED:
            continue
        if not any(o.startswith(core.UNRESOLVED_HEAD.format(about=c.get("about"))) for o in opened):
            out.append(
                f"{c['id']}: the conflict the manager left unresolved is not carried as open"
            )
        for side in c.get("sides") or []:
            said = core.settled_says(c.get("about"), side.get("speaker"), side.get("claim"))
            for view, text in views.items():
                if said in text:
                    out.append(f"{view} says {c['id']} was settled, and the manager left it "
                               "unresolved and referred it to the activity's owner")
    return out


#: a view's claim that a recovery target is outside its MTPD
NOT_INSIDE = re.compile(r"\bnot (strictly )?inside\b", re.I)


def agrees_with_itself(
    record: dict[str, Any], views: dict[str, str], his: tuple[str, ...] = ()
) -> list[str]:
    """t75, the owner's rule: every signed record agrees with itself. No record carries a target
    outside its own MTPD without an acknowledged gap, and no view says a gap's target is "not
    inside" where the record's own figures put it inside (`core.gap_reading`, the referee's reading;
    fix 1: where they cannot be read, neither). Only nemo's own gap wording is held to it (fix 1):
    a line carrying `ACKNOWLEDGED_GAP`, with `his` lines (his reservations, the open items' words)
    taken out of it first, so nothing he typed or a draft said can refuse his signature."""
    out = []
    for a in record.get("activities") or []:
        name, target, mtpd = a.get("name"), a.get("recovery_target"), a.get("mtpd")
        outside = core.gap_reading(a, record.get("method"))
        if outside and not a.get("recovery_gap_flagged"):
            out.append(
                f"the record carries a recovery target of {target} for {name}, not inside its "
                f"MTPD of {mtpd}, and no recovery gap is acknowledged"
            )
        if outside is not False:
            continue
        for view, text in views.items():
            if any(ACKNOWLEDGED_GAP in line and NOT_INSIDE.search(line)
                   for line in (_without(line, his) for line in lines_about(text, str(name)))):
                out.append(
                    f"{view} says the recovery target of {name} is not inside its MTPD, and the "
                    f"record's own figures put {target} inside {mtpd}"
                )
    return out


def _without(line: str, his: tuple[str, ...]) -> str:
    for words in sorted(filter(None, his), key=len, reverse=True):
        line = line.replace(words, " ")
    return line


def lines_about(text: str, name: str) -> list[str]:
    """The lines of a view about one activity: each line naming it, and every line of the section
    its heading opens (t64: the handover names it once there, then says "this activity")."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            inside = line.lstrip("#").strip() == name
        if inside or name in line:
            out.append(line)
    return out


def signer_named(
    record: dict[str, Any], signature: dict[str, Any], certificate: str | None
) -> list[str]:
    """The signer is a person, who signs as the owner or on behalf of the owner the record holds.

    t134: which of the two is the *capacity* the signature carries — his own explicit choice, and
    the record's verdict on it. It was read out of the role string he typed until this ticket,
    which is the one thing `handover.capacity`'s docstring says decides nothing here.
    """
    name = str(signature.get("name") or "").strip()
    owners = handover.owners(record)
    if not name or NOT_A_PERSON.search(name):
        return [
            f"the signer {name or '(nobody)'} is not a person: only the one who types their own "
            "name signs, never the tool"
        ]
    owner = any(core.norm_name(name) == core.norm_name(o) for o in owners)
    out = []
    if not owner and not str(signature.get("capacity") or "").startswith(core.ON_BEHALF):
        # fix 1: said without the owner's name, so the model has no phrase to copy into the role
        out.append(f"{name} is not the owner the record holds, and the signature does not say "
                   "whom he signs for")
    if certificate is not None:
        if f"Signed by {name}" not in certificate:
            out.append(f"the certificate does not name {name} as the signer")
        if not owner and not all(o in certificate for o in owners):
            out.append(
                f"the certificate does not name {', '.join(owners)}, the owner {name} signs for"
            )
    return out


# ── fix 3: around a model turn ───────────────────────────────────────────────────────────────
def his_figures_kept(folder: Path, activity: str, before: dict[str, Any], after: dict[str, Any],
                     method: dict[str, Any]) -> list[str]:
    """Every figure HE set that a model turn moved or removed: the record's figures before the turn
    against after it, for each figure item carrying a decision of his (not the model's, not one a
    side implied). Keyed on data — the item, its decision, the value the record carries — never on a
    word. The gate (`Session._his_act`) is total, so this finds nothing on this tree; it exists so
    a gate that stops being total reds (review 3's `p5.py`: `accept` restored nemo's 8 h over his
    4 h, `reject` left no MTPD, `accept` handed his 24 h RPO to the register's 4 h)."""
    if before == after:
        return []
    mine = {iid for iid, d in (before.get("decisions") or {}).items()
            if iid.rsplit(".", 1)[-1] in FIELDS and not d.get("model") and not d.get("by")}
    if not mine:
        return []

    def figures(state: dict[str, Any]) -> dict[str, Any]:
        draft = state.get("draft") or {}
        if not draft.get("activities"):
            return {}
        acts = core.build_proposal(draft, state, method, folder)["activities"]
        return {
            f"{x['id']}.{key}": next(
                (m.get("value") for m in act["evidence_meta"] if m["label"] == label), None
            )
            for x, act in zip(draft["activities"], acts, strict=False)
            for key, (label, _) in FIELDS.items()
        }

    was, now = figures(before), figures(after)
    out = []
    for iid in sorted(mine):
        label = FIELDS[iid.rsplit(".", 1)[-1]][0]
        if (after.get("decisions") or {}).get(iid) != before["decisions"][iid] \
                or was.get(iid) != now.get(iid):
            out.append(f"{label} for {activity}: you set {was.get(iid)}, and a model turn made it "
                       f"{now.get(iid) or 'nothing'}")
    return out


# ── the check, at the two moments ────────────────────────────────────────────────────────────
def check(folder: Path, activity: str, record: dict[str, Any], run: dict[str, Any],
          views: dict[str, str], signature: dict[str, Any] | None = None,
          said: list[str] | None = None) -> list[str]:
    """Every mismatch between the run's decisions, the record and the views, each naming its item.
    `signature` is given at the signature and not at the record's write. `said` (t71b): the lines
    he typed and the labels nemo drew for him; by default, the room's log of his lines."""
    state = core.load_state(folder, activity)
    method = json.loads((folder / walk.METHOD).read_text())
    ledger = state.get(core.RESERVATIONS) or []
    out = decisions_in_record(state, record, method)
    out += record_is_current(state, record, method, folder)
    out += reopen_kept(state)
    out += reservations_kept(state, run)
    out += views_say(record, run, views, ledger)
    out += gap_closed_by_him(record, views)
    out += left_unresolved(state, record, views)
    out += agrees_with_itself(record, views, tuple(
        [w for _, w in reservations(run)] + [str(r.get("naming")) for r in ledger]
        + [item for _, item in handover.items(record, run)]))
    out += his_words(state, record, run, core.said_lines(folder) if said is None else said)
    if signature is not None:
        out += signer_named(record, signature, views.get(CERTIFICATE))
    return list(dict.fromkeys(out))
