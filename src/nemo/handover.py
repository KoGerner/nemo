"""Stage 5's three documents: the management BIA, the requirements handover, and the certificate.

Where the BIA ends. The requirements are put in front of the manager to hand to whoever designs
the continuity solutions, accepted, and then signed — and the signature is the one moment in the
whole walk where anybody is asked who they are.

**Who this is written for was asked of the frozen corpus rather than assumed** (owner's ruling,
2026-09-13): the next activity in the lifecycle after analysis is solutions design, so the reader
is a BCM manager about to design continuity solutions and what they get is MTPD, RTO, RPO, MBCO,
minimum resources, dependencies and the reservation attached to any answer that was not *endorsed*.
The corpus states its own gap — it holds no step-by-step method for solutions design — so these
documents hand over inputs and never instruct the reader how to do the next stage. That is the same
line the method already holds: it never drafts a continuity plan and stops here, deliberately.

**Nothing here reaches the disk, the clock, the network or the chat.** The two records this walk
has on disk are the whole of the input: the BIA record, which carries the figures, the activities,
what the walk left open and the method it was judged under, and the run, which carries what was
answered at each earlier card and what the referee found. Everything below is a function of those
bytes, so rendering twice produces the same bytes twice and a manager's documents cannot drift
away from the record they claim to be about while a transcript is edited underneath them.

**The words for what a run holds are `nemo.record`'s, not this module's.** The run is a record like
any other and its fields are read here and written one layer up in `nemo.walk`, which this module
may not import; so the vocabulary both need — the decisions, what each reserved, the findings, and
the signature's own fields — sits below them both, where `Record` and `DEPARTMENT` already are.

**The sentences are `nemo.figures`', not this module's and not `nemo.views`'.** The four views and
these documents say the same figure to the same human hours apart, and two spellings of that
sentence is the v1 defect one layer up: `output/<process>/` held MTPD `24 h` in the record, `8 h`
in the handover and `0–4 hours` in the worksheet, with owner validation pending, and nothing
compared them. They were `nemo.views`' until the sentences moved below both, and this module
imported the stage-4 renderer to reach them — which put these documents on the renderer, and
through it on the disk door it opens, for six sentences that reach no disk. What two layers both
need sits under both of them: the same reason `Record` is below this module and the walk.

**A signature must identify somebody with authority to give it.** In v1 a sign-off whose signer's
role read *"explicitly not the process owner"* validated cleanly, because nothing checked who
signed. The check here is on the signer's **name** against the owner the record holds for the
activity, never on the role string they typed: a role is what somebody calls themselves, and v1's
defect arriving with a better job title would be the same defect.

**The certificate has exactly one identity sentence.** Nothing anywhere in this product captures
an email address — `docs/stage-model.md:189` settled on 2026-09-12 that the third typed slot is one
free-text amendment and not an email at the door — so *identity asserted in session, not verified*
is the only thing a certificate here can truthfully say. The stronger branch would be a flag
nothing sets and a claim no code in this product can make true (corrected 2026-09-14).

**The sentences he signs are the ones he approved, and they are written here** (ADR-0030 decision
5, ticket 133). The live app wrote them for weeks through a runtime patch over this module — t64's
plain wording (the activity named once in its heading and "this activity" after it, a category by
its method's name, the shared-quote finding in words), t71 and t75's recovery-gap sentences, t76's
gap he closed in his own words, t79's one addressee per document — and he walked and ruled on them
there. One source writes them now, so a signed sentence reads the same on every run (t88). Every
figure sentence is one the record holds, and a gap sentence states the record's own gap flag.

**No document here says "room".** `CONTEXT.md` makes *Room* the binding internal word and these
three documents are the ones a customer reads; the owner ruled the thing is a chat, not a room.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable

from nemo import duration, referee, views

# The band and its upper edge live below the referee since ticket 240; the skin reads them here.
from nemo.duration import BAND as BAND
from nemo.duration import upper_edge as upper_edge
from nemo.figures import requirements
from nemo.method import beyond_horizons
from nemo.record import (
    ACCEPTED,
    ACTIVITIES,
    AT_STAGE,
    CAPACITY,
    CARRIED,
    CHAT_CONFIRMATION,
    DECISIONS,
    DEPT,
    EVIDENCE,
    FINDINGS,
    GRADIENT,
    METHOD,
    MTPD,
    NAME,
    NAMING,
    ON,
    OPEN_ITEMS,
    OWNER,
    RECOVERY_TARGET,
    REFERRALS,
    REFERRED_TO,
    REFERS,
    ROLE,
    RPO,
    SIGNATURE,
    SIGNER,
    TYPE,
    UNNAMED,
    WORDS,
    Record,
)
from nemo.text import norm

#: The three documents, under the names the story spells them, in the order the walk produces
#: them: the two the acceptance writes, and the one the signature writes.
DRAFT = "bia-draft.md"
HANDOVER = "requirements-handover.md"
CERTIFICATE = "owner-signoff-certificate.md"

#: What the run carries that these documents read is `nemo.record`'s vocabulary, imported above.
#: The run's own shape is the walk's and this module sits below the walk and may not import it, so
#: the words both need live below them both rather than being spelled once here and once up there.

#: What a signature was given in. The owner of the activity closes the run, and so does a delegate
#: signing on behalf of them (the owner's ruling of 2026-09-17, ADR-0030 decision 7); anybody else
#: is recorded as what they actually are, and the run stays where it was.
OWNER_OF_THE_ACTIVITY = "the owner of the activity"
SPONSOR = "sponsor or reviewer acceptance"
#: The third capacity, and the only one that carries a second name: whom he signs for, in the
#: record's own spelling of them. It is never what a signer typed about themselves.
ON_BEHALF = "on behalf of"
ON_BEHALF_OF = ON_BEHALF + " {owner}, whom the record holds as the owner"


class NotAnOwner(Exception):
    """A signature offered on behalf of somebody this record does not hold as an owner.

    Whom a delegate signs for is one of the record's own names or it is nothing: a signature that
    could name anybody would be v1's "on behalf of" the absent owner again, this time spelled in
    the argument rather than in a job title.
    """

#: How an open item is named at the signature. The manager accepts findings by id, so the id has
#: to be a function of the record and the run alone: it is the item's position, which two renders
#: of the same bytes agree on and nothing else needs to be stored to reproduce.
ITEM_ID = "OPEN-{number}"

LABEL = ("This is a requirements handover for solution-design discussion. It is not approved: "
         "nobody has signed off a decision by writing it, and nothing in it commits anybody to "
         "anything.")
READER = ("It is written for whoever designs the continuity solutions next. What it hands over is "
          "the figures and the decisions behind them — how long each activity can be down, what "
          "has to be back and by when, the minimum acceptable service, the resources, what each "
          "activity depends on, and every reservation attached to an answer that was not "
          "endorsed.")
NO_METHOD = ("It hands over those inputs and stops at them. The guidance this BIA was run under "
             "holds no step-by-step method for designing a continuity solution, so nothing below "
             "tells you how to design one.")
DRAFT_LEAD = ("The BIA for management: what this analysis found, said in the sentences the record "
              "holds for it. Every figure below is read out of the BIA record, so it says what the "
              "record says or it does not appear.")

REQUIREMENTS = "## The continuity requirements, activity by activity"
ACTIVITY = "### {activity}"
OWNED_BY = "The record has {owner} stating {activity}'s own figures, so this activity is theirs."
NO_OWNER = ("The record has nobody stating {activity}'s own figures, so it records no owner for "
            "it and this sign-off cannot be given for it by anybody.")

REFERRED = "## Referred to the risk assessment"
REFERRAL = "For {to}: {refers}."
NO_REFERRALS = ("This BIA refers nothing to the risk assessment. That is what the record holds "
                "rather than a section left out.")

OPEN = "## What is still open, and accepted by id at the signature"
ITEM = "{id} — {text}"
NOTHING_OPEN = "This BIA left nothing open, so there is nothing here to accept by id."

RESERVED = "## What was reserved on the way here"
RESERVATION = "Stage {stage} was answered “{gradient}”, and what was reserved is: {naming}"
NOT_NAMED = ("Stage {stage} was answered “{gradient}”, and a reservation was recorded and never "
             "named. It is carried as that rather than as agreement.")
NOTHING_RESERVED = "Every card in this BIA was endorsed as it stood, so nothing was reserved."
#: t71: a reopen puts the run back to step 3 and would drop every reservation made at steps 3 to 5
#: with it, so the ones it carried over are said first, and they stand.
CARRIED_SAYS = (
    "Before the BIA was reopened, step {stage} carried this reservation, and it stands: {naming}"
)

FOUND = "## What the check of this BIA found"
NO_FINDINGS = "The check of this BIA found nothing to raise."

STOPS = "## Where this BIA stops, and what you decide after it"
BOUNDARY = ("The BIA stops here. It says what has to be back and by when, and it chooses nothing "
            "about how: no site, no supplier, no system, no continuity plan. Which continuity "
            "solution meets these requirements, and which of the open items above anybody carries, "
            "is yours to decide after reading this and is not decided in here.")

#: The record's gap keys: the manager acknowledged a recovery gap (the referee's own flag); whose
#: account he settled on when he did (t75); and the words he typed to close one (t76).
GAP_FLAGGED = "recovery_gap_flagged"
GAP_ACCOUNT = "recovery_gap_account"
GAP_CLOSED = "recovery_gap_closed"
ACCOUNT_SAYS = " on {speaker}'s account"
#: A gap whose target is outside the MTPD the record carries: the true reason, and his
#: acknowledgement.
GAP_SAYS = ("{activity}'s recovery target {target} is not inside its MTPD of {mtpd}: a recovery "
            "gap, acknowledged by the manager{account} and handed to solution design as a known "
            "exposure.")
#: t75: a gap whose target the record's own figures put inside its MTPD: his acknowledgement only.
GAP_ACK_SAYS = ("For {activity} the manager acknowledged a recovery gap{account}, handed to "
                "solution design as a known exposure; the recovery target {target} is inside its "
                "MTPD of {mtpd}.")
#: t75 fix 1: a gap on figures the record carries but cannot be compared: the figures as carried.
GAP_CARRIED_SAYS = ("For {activity} the manager acknowledged a recovery gap{account}, handed to "
                    "solution design as a known exposure; the record carries recovery target "
                    "{target}, MTPD {mtpd}.")
#: The same, as the few words a figure line carries after the target.
GAP_WORDS = "a recovery gap, acknowledged{account}"
WHERE_WORDS = ", with the target {where} the MTPD"
#: t76: a gap he closed, in the words he typed to close it. t79 fix 1: these documents are written
#: for other people, so he is in the third person here; only a stage card speaks to him.
CLOSED_MARK = "a recovery gap he closed"
CLOSED_WORDS = CLOSED_MARK + ", in his own words: “{words}”"
CLOSED_SAYS = ("For {activity} the record carries " + CLOSED_MARK + ": he recorded, in his own "
               "words, that the arrangements can now meet the recovery target — “{words}”.")
#: t64: the activity's full name said once, in its heading, and this after it.
THIS_ACTIVITY = "this activity"
#: A span somebody said, “…” or "…": never reworded (t64 fix 1, I1).
QUOTED = re.compile(r"(“[^”]*”|\"[^\"\n]*\")")
#: The referee's shared-quote finding, which ends in the JSON a developer would record (t64).
REUSED = re.compile(r"^Human decisions: activity (?P<aid>.+?) — the same quote is the evidence for "
                    r"(?P<lenses>\[[^\]]*\])\. .*shared_quote_ack.*$", re.S)
REUSED_SAYS = ("Human decisions: one quote is the only evidence for {count} impact categories "
               "({said}). A person has to confirm that it supports each of them; accepting this "
               "item at the signature is that confirmation.")

SIGNED = "# The sign-off for {dept}"
BY = "Signed by {name}, {role}, as {capacity}."
#: The one sentence a certificate here can truthfully carry, in those words and no others.
ASSERTED = "identity asserted in session, not verified"
IDENTITY = ("How this signature stands: {asserted}. Nobody was asked for a password and nothing "
            "was sent anywhere to establish who signed, so this says exactly as much as it says.")
#: t71, M14 and t134: what the certificate says before what the signature accepted: whom a delegate
#: signs for, the figures signed, and every reservation in the words it was made in.
SIGNED_FOR = "{name} signs on behalf of {owners}, whom the record holds as the owner."
SIGNED_FIGURES = "## What was signed"
#: 190 (the owner's "No RPO at all"): what every view says of an activity none of whose
#: dependencies declares an RPO for it, under a method with no no-data word. The words are the
#: derivation's own reason (`bia_figures.impact.NO_DATA_HELD`, beside the skin; a skin test holds
#: the two equal, since nothing here may import it).
NO_RPO = "no RPO: none of the systems it depends on gives one for this activity"
ACCEPTED_HERE = "## What was accepted at this signature"
NOTHING_ACCEPTED = "Nothing was left open for this signature to accept."
NOT_AN_APPROVAL = "## What this sign-off does not say"
NOT_APPROVAL = ("It is a signature on a requirements handover for solution-design discussion. It "
                "is not an approval of a continuity plan, and no plan was drafted: this BIA hands "
                "over the requirements above and stops.")


def documents(record: Record, run: Record, *, plainly: bool = True) -> dict[str, str]:
    """The two documents the acceptance writes, each as markdown a human reads. Writes nothing.

    ``plainly=False`` is the wording before t64 (the raw findings, the full name in every sentence),
    kept only so a handover on file written then is recognised as exactly that (t64 fix 1).
    """
    return {
        DRAFT: _document(f"# The BIA for {record.get(DEPT, '')}", [DRAFT_LEAD], record, run,
                         plainly),
        HANDOVER: _document(f"# Requirements handover — {record.get(DEPT, '')}",
                            [LABEL, READER, NO_METHOD], record, run, plainly),
    }


def certificate(record: Record, run: Record) -> str:
    """The certificate the signature writes: who signed, in what role, the figures signed, every
    reservation, and what they accepted (t71, M14: the phone's certificate, nemo's since 241)."""
    signature: Record = run.get(SIGNATURE) or {}
    activities = record.get(ACTIVITIES) or []
    return _joined([
        SIGNED.format(dept=record.get(DEPT, "")),
        BY.format(name=signature.get(SIGNER, ""), role=signature.get(ROLE, ""),
                  capacity=signature.get(CAPACITY, "")),
        IDENTITY.format(asserted=ASSERTED),
        *_signed_for(record, signature),
        SIGNED_FIGURES, *(figure_line(activity, record.get(METHOD)) for activity in activities),
        # t132: each figure he confirmed in chat, as his confirmation on its day, never a quote
        *_chat_confirmations(activities),
        RESERVED, *_reservations(run),
        ACCEPTED_HERE, *_accepted(record, run, signature),
        NOT_AN_APPROVAL, NOT_APPROVAL])


def _chat_confirmations(activities: list[Record]) -> list[str]:
    """Each figure he confirmed in chat, as his confirmation on its day (t132)."""
    return [views.CONFIRMED.format(on=given.get(ON), words=given.get(WORDS))
            for activity in activities for given in activity.get(EVIDENCE) or []
            if given.get(TYPE) == CHAT_CONFIRMATION]


def items(record: Record, run: Record, *, plainly: bool = True) -> tuple[tuple[str, str], ...]:
    """Everything still open, each under the id the signature accepts it by.

    What the walk left open and what the check of the record found, in that order and numbered
    where they stand: a dependency the register does not model is a **finding** carried to this
    signature and accepted by its id, never a sixth stage that chases somebody for an owner. Each
    is said in words (t64), so the card, both documents and the certificate say the same ones.
    """
    method = signed_method(record, run)
    open_items = [*(record.get(OPEN_ITEMS) or []), *(run.get(FINDINGS) or [])]
    return tuple((ITEM_ID.format(number=number),
                  plain_finding(str(text), method) if plainly else str(text))
                 for number, text in enumerate(open_items, 1))


def owners(record: Record) -> tuple[str, ...]:
    """Whom this record has owning its activities, each once and in the record's own order."""
    return tuple(dict.fromkeys(
        str(activity[OWNER]) for activity in record.get(ACTIVITIES) or [] if activity.get(OWNER)))


def capacity(record: Record, name: str, on_behalf_of: str | None = None) -> str:
    """What a signature by this person is: the activity's owner, a delegate for them, or neither.

    The comparison is against the name the **record** holds, and never against the role string the
    signer typed. v1 validated a sign-off whose role read "explicitly not the process owner"
    because nothing compared the signer with anybody; a check that read the role instead would
    pass the same sign-off the moment it called itself something better. There is no role argument
    here, so no job title anybody types can reach this verdict.

    ``on_behalf_of`` is **his own explicit choice**, taken at the signature and passed in (ADR-0030
    decision 7): ``None`` is "as the owner", which is decided by his name exactly as it always was,
    and a name is "on behalf of them", which has to be one of the record's own names and raises
    `NotAnOwner` when it is not. The live app read a role string out of a module global to decide
    this, which is the one thing this module's docstring says it never does.
    """
    if on_behalf_of is None:
        return OWNER_OF_THE_ACTIVITY if any(
            norm(name) == norm(owner) for owner in owners(record)) else SPONSOR
    for owner in owners(record):
        if norm(on_behalf_of) == norm(owner):
            return ON_BEHALF_OF.format(owner=owner)
    raise NotAnOwner(on_behalf_of)


def closes(given: str) -> bool:
    """Whether a signature given in this capacity closes the BIA.

    The owner's own signature does, and a delegate's on their behalf does (2026-09-17): every
    phone walk of the demo is a delegate's, and nemo left each of them open. An acceptance beside
    the owner does not, and that is the whole of the difference.
    """
    return given != SPONSOR


def _document(title: str, lead: list[str], record: Record, run: Record, plainly: bool) -> str:
    """One document: what it is, the requirements activity by activity, and everything still open.

    Both are built here and both carry the same sections under the same sentences. That is the
    whole mechanism behind "the two documents cannot disagree": there is one rendering of a
    reservation, of a finding and of a figure, and two documents that quote it.
    """
    return _joined([
        title, *lead,
        REQUIREMENTS, *_per_activity(record, plainly=plainly),
        REFERRED, *_referrals(record),
        OPEN, *_still_open(record, run, plainly),
        RESERVED, *_reservations(run),
        FOUND, *_found(record, run, plainly),
        STOPS, BOUNDARY])


def _per_activity(record: Record, *, plainly: bool = True) -> list[str]:
    """The continuity requirements activity by activity, each under who the record has owning it.

    The figures are ``nemo.figures``' sentences and the ownership line is this module's, because the
    only thing this document says about an activity that a view does not is what its ownership
    means for the signature at the end of it. After them, the recovery gap the manager acknowledged
    (t71, the record's own flag) and the one he closed, in the words he closed it in (t76).

    Said plainly (t64): the activity named in full once, in its heading, and "this activity" after
    it, and a category by its method's name. His words closing a gap come after that, because they
    are his: a line of them that named the activity would come back reworded.
    """
    method: Record = record.get(METHOD) or {}
    return [line for activity in record.get(ACTIVITIES) or []
            for line in _activity_lines(activity, method, plainly)]


def _activity_lines(activity: Record, method: Record, plainly: bool) -> list[str]:
    """One activity's section of `_per_activity`: heading, owner, figures, the gaps."""
    lines = [ACTIVITY.format(activity=activity[NAME]), _owned(activity),
             *requirements(activity, method)]
    if activity.get(GAP_FLAGGED):
        lines.append(gap_says(activity, method))
    if plainly:
        name = str(activity.get(NAME) or "")
        lines = lines[:1] + [said_plainly(line, name, method) for line in lines[1:]]
    if activity.get(GAP_CLOSED):
        lines.append(closed_says(activity))
    return lines


def said_plainly(line: str, name: str, method: Record | None) -> str:
    """One requirements sentence with the activity's full name said as "this activity" and each
    category id said by the method's name (t64). The name is swapped only where it stands as a
    whole word, so a longer word it sits inside ("Kuehlungsanlage", "order-picking-station") is
    left alone; letters, digits and "-" count as word characters."""
    if name:
        line = re.sub(rf"(?<![\w-]){re.escape(name)}(?![\w-])", lambda _: THIS_ACTIVITY, line)
        line = re.sub(rf"(^|[.:;!?]\s+){THIS_ACTIVITY}",
                      lambda m: m.group(1) + THIS_ACTIVITY.capitalize(), line)
    return categories_said(line, method)


def categories_said(text: str, method: Record | None) -> str:
    """Prose with each of the method's category ids said by its name, outside anybody's quote."""
    names = _category_names(method)
    if not names:
        return text
    ids = "|".join(map(re.escape, sorted(names, key=lambda name: -len(name))))
    return outside_quotes(text, lambda part: re.sub(rf"(?<![\w-])({ids})(?![\w-])",
                                                    lambda m: names[m.group(1)], part))


def outside_quotes(text: str, change: Callable[[str], str]) -> str:
    """``change`` applied to the text outside every quoted span, and the quotes left as they are."""
    return "".join(part if n % 2 else change(part) for n, part in enumerate(QUOTED.split(text)))


def plain_finding(text: str, method: Record | None) -> str:
    """A finding as the manager reads it (t64). The shared-quote finding ends in the JSON a
    developer would record; here it is said in words, its categories by the method's names. Any
    other finding is the referee's own sentence already and stands as it is."""
    match = REUSED.match(str(text))
    if not match:
        return str(text)
    try:
        lenses = [str(x) for x in ast.literal_eval(match.group("lenses"))]
    except (ValueError, SyntaxError):
        return str(text)
    names = _category_names(method)
    return REUSED_SAYS.format(count=len(lenses), said="; ".join(names.get(x, x) for x in lenses))


def signed_method(record: Record, run: Record) -> Record | None:
    """The method a finding's words come from: the **record's**, the one he signs, and the run's
    only where the record holds none (t196). One source, so the open-items list and the section
    that says what the check found name an impact category the same way on the same document."""
    return record.get(METHOD) or run.get(METHOD)


def _category_names(method: Record | None) -> dict[str, str]:
    return {c["id"]: c["name"] for c in (method or {}).get("scenarios") or [] if c.get("id")}


def gap_reading(activity: Record, method: Record | None = None) -> bool | None:
    """Whether the record's recovery target is outside the MTPD it carries, by the referee's own
    reading (t74, ADR-0039: a band, MTPD or target, at its upper edge); None where the record
    carries no MTPD or target that can be read (t75 fix 1: then nothing claims inside or outside).

    t156: an RTO and an MTPD both past the method's last horizon are inside (the owner's ruling,
    t139 (c)), decided by the referee's own rule, `referee._both_beyond`, never a copy of it. The
    method is the record's; without one there is no beyond word."""
    if referee._both_beyond(activity.get(RECOVERY_TARGET), activity.get(MTPD),
                            beyond_horizons(method or {})):
        return False
    target = duration.worst_case(activity.get(RECOVERY_TARGET))
    limit = duration.worst_case(activity.get(MTPD))
    return None if target is None or limit is None else target >= limit


def _account(activity: Record) -> str:
    account = activity.get(GAP_ACCOUNT)
    return ACCOUNT_SAYS.format(speaker=account) if account else ""


def gap_says(activity: Record, method: Record | None = None) -> str:
    """An acknowledged recovery gap in one sentence, from the record's own figures (t75): "not
    inside" only where they put the target outside, and whose account he settled on."""
    reading = gap_reading(activity, method)
    return (GAP_CARRIED_SAYS if reading is None else GAP_SAYS if reading else GAP_ACK_SAYS).format(
        activity=activity.get(NAME), target=activity.get(RECOVERY_TARGET) or "—",
        mtpd=activity.get(MTPD) or "—", account=_account(activity))


def gap_words(activity: Record, method: Record | None = None) -> str:
    """The same, as the few words a figure line carries after the target (t75)."""
    reading = gap_reading(activity, method)
    where = "" if reading is None else WHERE_WORDS.format(
        where="not inside" if reading else "inside")
    return GAP_WORDS.format(account=_account(activity)) + where


def closed_says(activity: Record) -> str:
    """A recovery gap he closed, in one sentence with the words he closed it in (t76)."""
    return CLOSED_SAYS.format(activity=activity.get(NAME), words=activity.get(GAP_CLOSED))


def closed_words(activity: Record) -> str:
    """The same, as the few words a figure line carries after the target (t76)."""
    return CLOSED_WORDS.format(words=activity.get(GAP_CLOSED))


def no_rpo(activity: Record) -> bool:
    """Whether an activity carries no RPO because the method gives none (190): no figure, and the
    method's own statement behind the RPO."""
    return not activity.get(RPO) and any(
        given.get("label") == "RPO" and given.get("origin") == "method"
        for given in activity.get(EVIDENCE) or [])


def rpo_clause(activity: Record) -> str:
    """The RPO clause of a figure line: its figure, or why there is none (190)."""
    return f", {NO_RPO}" if no_rpo(activity) else f", RPO {activity.get(RPO) or '—'}"


def figure_line(activity: Record, method: Record | None = None) -> str:
    """One activity's figures in one sentence, as the stage-4 card and the certificate say them
    (t71: the same words in both, read off the record). A gap he closed is said in the third
    person, because the certificate is a document about him that other people read (t79 fix 1).
    """
    return (f"{activity.get(NAME)}: MTPD {activity.get(MTPD) or '—'}, recovery target "
            f"{activity.get(RECOVERY_TARGET) or '—'}"
            + (f" — {gap_words(activity, method)}" if activity.get(GAP_FLAGGED)
               else f" — {closed_words(activity)}" if activity.get(GAP_CLOSED) else "")
            + f"{rpo_clause(activity)}. Owner on file: {activity.get(OWNER) or '—'}.")


def _still_open(record: Record, run: Record, plainly: bool) -> list[str]:
    """Everything still open, each under the id the signature accepts it by — or that nothing is."""
    return [ITEM.format(id=at, text=text)
            for at, text in items(record, run, plainly=plainly)] or [NOTHING_OPEN]


def _found(record: Record, run: Record, plainly: bool = True) -> list[str]:
    """What the check of this BIA found, in the referee's own words — or that it found nothing.

    Said in words (t64) by `signed_method`, the same one the open-items list above reads (t196):
    one finding said twice on one document cannot be said two ways. Until t196 this read the
    method the **run** carries, as the live app said it, and a run carrying none — the usual case
    — named a category by its id here and by its name there.
    """
    return [plain_finding(str(finding), signed_method(record, run)) if plainly else str(finding)
            for finding in run.get(FINDINGS) or []] or [NO_FINDINGS]


def _signed_for(record: Record, signature: Record) -> list[str]:
    """Whom a delegate signs for, said once, or nothing (t134): read off the capacity the signature
    was given in, which is his own choice and the record's verdict on it."""
    held = owners(record)
    if not held or not str(signature.get(CAPACITY)).startswith(ON_BEHALF):
        return []
    return [SIGNED_FOR.format(name=signature.get(SIGNER) or "", owners=", ".join(held))]


def _accepted(record: Record, run: Record, signature: Record) -> list[str]:
    """The open items this signature accepted, by the ids it accepted them under.

    By id and never by text: the manager was shown these ids on the signature card, so what lands
    on the certificate is what they read, and an item nobody accepted is absent rather than
    softened into one they did.
    """
    ids = signature.get(ACCEPTED) or []
    return [ITEM.format(id=at, text=text)
            for at, text in items(record, run) if at in ids] or [NOTHING_ACCEPTED]


def _owned(activity: Record) -> str:
    """Who the record has owning this activity, said as what it means for the signature."""
    if not activity.get(OWNER):
        return NO_OWNER.format(activity=activity[NAME])
    return OWNED_BY.format(owner=activity[OWNER], activity=activity[NAME])


def _referrals(record: Record) -> list[str]:
    """What this BIA refers to the risk assessment: what is referred, and to whom.

    An empty section says the record holds no referral, because a section silently left out reads
    as one nobody thought about rather than as one the BIA did not make.
    """
    return [REFERRAL.format(refers=item[REFERS], to=item[REFERRED_TO])
            for item in record.get(REFERRALS) or []] or [NO_REFERRALS]


def _reservations(run: Record) -> list[str]:
    """What every earlier gradient answer reserved, in the words it was reserved in.

    Those a reopen carried over first (t71), then this run's own. Verbatim, because a reservation
    summarised is a reservation answered on behalf of the person
    who made it — and one nobody named is carried as unnamed, never rounded up to an endorsement.
    """
    return _carried_over(run) + [_reserved(decision) for decision in run.get(DECISIONS) or []
                                 if NAMING in decision] or [NOTHING_RESERVED]


def _carried_over(run: Record) -> list[str]:
    """The reservations a reopen carried over (t71), each as it was carried."""
    return [CARRIED_SAYS.format(stage=kept[AT_STAGE], naming=kept[NAMING])
            for kept in run.get(CARRIED) or []]


def _reserved(decision: Record) -> str:
    """One gradient answer's reservation, verbatim — or carried as unnamed if nobody was named."""
    return (NOT_NAMED if decision[NAMING] == UNNAMED else RESERVATION).format(
        stage=decision[AT_STAGE], gradient=decision[GRADIENT], naming=decision[NAMING])


def _joined(parts: list[str]) -> str:
    """The parts as one markdown document: a blank line between them, and one at the end."""
    return "\n\n".join(parts) + "\n"
