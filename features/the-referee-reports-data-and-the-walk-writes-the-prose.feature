Feature: The referee reports findings as data; the walk writes the prose
  As a BCM manager I reach stage 4 and the BIA cannot be accepted. I am told so — and what I read is
  a sentence a colleague would have said to me, naming the activity, the impact category and the
  time bands nobody scored. Not `activity Slaughter: impact_grid['legal-regulatory'] missing
  horizon(s): ['72 h']`, which is what the card says today on an ordinary interview, in a room the
  owner can reach from his phone this afternoon.

  `impact_grid` and `recovery_target` are banned by name in `docs/voice.md` §3.1 and in the suite's
  own `BANNED_ON_A_CARD`. They reach the card because the refused body is the referee's own
  rejections joined end to end, and every one of those is an f-string written for a developer.
  `nemo.card` implements §4 (vagueness) only; §3, machine identifiers, has no mechanism anywhere.
  The one check that would have caught it is applied to the card where it cannot fire: the voice
  scenario in `features/stage-4a-the-refereed-record.feature` opens "When I read the stage 4 card",
  the **passing** card, and the refusal's own scenario beside it asserts only that the problem is
  said before anything is asked — never that it is said in the voice. So the first half of this file
  is that scenario written for the card that refuses.

  The shape asked for: the referee reports what it found as data — activity, category, horizons —
  and `nemo.walk`, the module that already owns every card string, turns them into prose. Which is
  why the scenarios below are about what a manager reads and not about where a string is built. The
  one exception is the scenario that says the referee holds no sentence addressed to a manager,
  because two places writing a card's words is how the card and the handover come to word one open
  item two ways.

  The second half is the clause that cannot be false. The receipt's mechanism is right — a clause is
  there because the check that names it ran — but `_review_boundary` records itself as having run
  before it looks at anything, and the keys it then reads are keys a BIA this walk builds cannot
  carry. So every manager reads "and confirmed this is still a BIA and not a continuity plan" about
  a check that examined nothing: v1's hard-coded "record validated and saved" wearing the new
  mechanism. On today's record shape the correct outcome is that the clause stops appearing.

  Two slices this file does not own. Whether a refused card should leave the manager something to
  press is ticket 27 — here a refusal still refuses, and only its words change. And the categories
  are named on this card the way the rest of the card already names them; one spelling per card is
  the rule, and inventing a second one for the refusal is the failure, not the fix.

  Background:
    Given my company's room is "demo-1"
    And I have agreed the scope and bound the interview
    And I endorsed the standardised evidence at stage 3

  # The card the owner can reach today.

  Scenario: The BIA I cannot accept tells me what is wrong in my own language
    Given the interview I bound leaves one of my method's time bands unscored for a category
    When the stage 4 card is drawn
    Then I am told what is wrong with the BIA
    And it names no tool, no field name and no file path anywhere but its "Source:" line
    And it is written in sentences, not as a numbered list of machine actions

  Scenario: It says which activity, which impact category and which time bands
    Given the interview I bound leaves one of my method's time bands unscored for a category
    When the stage 4 card is drawn
    Then it names the activity the way the rest of the card names it
    And it names the impact category the way the rest of the card names it
    And it names the time bands nobody scored, as my method names them
    And no bracket, quote mark or list punctuation stands around any of them

  Scenario: Whatever the referee refuses, I read it in one voice
    Given every way the referee can refuse a record
    When each of those refusals reaches the stage 4 card
    Then not one of them puts a machine identifier in front of me
    And not one of them is the referee's own words passed through untouched

  Scenario: A card never tells me to set a field
    Given the recovery target my interview states is not inside the MTPD the grid derives
    When that refusal reaches the stage 4 card
    Then it says which target and which MTPD, in the figures the record holds
    And what it asks of me is something I could do by talking to a person

  # Cut: "and I can get past it". Whether a refused card leaves the manager something to press is
  # ticket 27, which owns the recovery gap as a finding rather than a wall. This ticket changes the
  # words of a refusal and nothing about its force; add this back the day the two are built together.

  # Cut: the nothing-scored-at-all refusal — "whatever the referee refuses, I read it in one voice"
  # above ranges over every rejection kind including this one; add it back if that one is ever
  # narrowed to a list of named kinds.

  # Cut: "nothing became answerable while the words were being fixed" — `stage-4a`'s "nothing lands
  # without the human" owns the bytes and ticket 27 owns the wall; add it back the day a refusal is
  # given something to press.

  # Cut: "what is wrong with it is said before I am asked for anything" —
  # `stage-4a-the-refereed-record.feature` says it and this ticket does not touch the order; the
  # scenario above holds the half of it that the rewording could break.

  # The open items, which are the same words in three places.

  # Cut: the open items on the passing card reading like a colleague wrote them — `stage-4a` already
  # says both halves of it ("with what was seen and where", "names no tool, no field name"); add it
  # back if either is ever dropped there.

  Scenario: An open item reads at sign-off exactly as it read on the card
    Given I accepted the record with an open item on it
    When I reach the handover and the signature
    Then that item is worded there exactly as it was worded on the card
    And no field name reached the handover documents either

  # What the referee hands back.

  Scenario: What the referee reports is data, not a sentence for me
    Given the referee refuses a record for a category that is missing time bands
    When what the referee reports is read
    Then the activity, the category and the missing time bands are separate parts of it
    And no sentence of it is addressed to a manager

  # Cut: the same assertion for every other kind of rejection. "Whatever the referee refuses, I read
  # it in one voice" above measures the outcome across all of them from the manager's end, which is
  # the thing that matters; add this back if a rejection is ever worded at the card rather than
  # carried as parts.

  # The receipt, and the clause that cannot be false.

  Scenario: Every clause of what it says it checked is a check that had something to examine
    Given I accepted my BIA
    When I read what the walk says it checked before writing
    Then every clause names a check that ran over something my BIA actually carries
    And it does not tell me it confirmed this is still a BIA and not a continuity plan

  Scenario: The clauses that were earned are all still there
    Given I accepted my BIA
    When I read what the walk says it checked before writing
    Then it says it found every quote word for word in a file in my room
    And it says it read the grid and derived the MTPD from it rather than taking the one I stated
    And it says it held the recovery target against the MTPD and checked the data-loss answer

  Scenario: A check that reads something my BIA cannot carry claims nothing
    Given the things a BIA this walk builds can carry
    When the referee's checks are read against them
    Then a check with nothing of mine to look at records no clause for me to read
    And no clause is recorded before the thing it judges has been looked at

  Scenario: A record that does carry a plan is judged, and only then said to have been
    Given a record that carries a continuity plan
    When the referee reviews that record
    Then it refuses it for standing over the handover boundary
    And the check of that boundary is one it may then say it ran

  # Cut: "a run that refereed nothing says nothing about having refereed" — that is
  # `stage-4a-the-refereed-record.feature`'s scenario and the mechanism under it is unchanged here;
  # this ticket narrows which checks record themselves, not whether an empty run may speak.

  # Cut: the draft check answering with the same problems in the same words. One verdict is built
  # once per walk and both the card and the draft check read it, which
  # `stage-4a-the-refereed-record.feature` already pins; add it back the day a second verdict is
  # built anywhere.
