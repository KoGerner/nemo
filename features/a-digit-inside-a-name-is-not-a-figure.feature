Feature: A digit inside a name is not a figure the record must hold
  A room called `Werk 1`, `Linie 2` or `Halle 45` makes the Stage 1 card refuse and the manager sees
  a dead screen. They press the one button the room offers and nothing at all comes back:
  `nemo.card._FIGURE` reads the digit inside the name as a figure, the empty Stage 1 record does not
  hold it, and `render` raises `CardGeneratorBug` where only an operator ever reads it. Live today,
  and no test catches it — ticket 22 renamed its demo rooms to words and walked around it honestly,
  which took the three red tests with it. Any real plant name with a line or a building number in it
  hits this, which is why it is a demo blocker rather than a tidy-up.

  The owner's ruling, 2026-09-13, closing open question 7: **exempt a digit only where it sits
  inside a name, scoped to that span.** The obvious form — adding the room's names to the text the
  card is checked against — was tried in review and breaks ticket 09's own Scenario 3. One
  `Halle 45` in a room would then license every bare `45` on every card of that walk, a fabricated
  headcount included. Unit-bearing figures survive that, so MTPD, RTO and RPO are mostly safe;
  unit-less counts are not, and those are exactly what Scenario 3 was written for. So the scenarios
  below are as much about what is still refused as about the dead screen going away.

  This is not a new kind of carve-out. `Card.screen` already keeps a verbatim interview preview out
  of the check, in its own words: "a verbatim quotation is not the card talking." A room's own name
  on a card is the same kind of thing — the card is not asserting a quantity when it says which
  building the manager works in.

  The last scenario is about the repository rather than the product, and deliberately so. Ticket 09
  states the rule with no exemptions at all, and that is already untrue of the shipped code. A repo
  that asserts a rule it does not follow teaches the next reader the wrong rule.

  # The dead screen, from the manager's end.

  Scenario: My department is called "Werk 1" and I get a card, not a dead screen
    Given my company's department is called "Werk 1"
    # Ticket 164: re-aimed from the demo skin's process button to the walk that draws the card;
    # the phone app draws no process buttons and no stage card through `render`.
    When I open the BIA for it and reach the stage 1 card
    Then the card is on my screen
    And nothing was refused over the "1" in the name of my own department

  Scenario: The record is empty at stage 1 and the name is still not a figure
    Given a stage 1 card for "Halle 60" whose record holds nothing at all yet
    When the card is checked against that record
    Then it is not refused, because the only digit on it sits inside the name

  # What is still refused. This half is the ticket: the carve-out is the span and nothing wider.

  Scenario: A fabricated count beside the name is still refused
    Given a record whose MBCO says "about 60 internal lorries"
    When a card says "The MBCO for Halle 60 is 60 internal lorries"
    Then the card is refused
    And the refusal names the count the record does not hold, not the building

  Scenario: A name this room does not hold licenses nothing
    Given my department is called "Werk 1"
    When a card says "Werk 7"
    Then the card is refused, because nothing in this room is called "Werk 7"

  Scenario: A hedge the card dropped is still caught
    Given a department called "Werk 1"
    And a record whose MBCO says "about 60 internal lorries"
    When a card says "Werk 1 runs 60 internal lorries"
    Then the card is refused

  Scenario: A hedge the card added is still caught
    Given a department called "Werk 1"
    And a record whose MTPD is "24 h"
    When a card says "Werk 1's MTPD is about 24 h"
    Then the card is refused

  Scenario: The record's own hedge still passes beside a name with a digit in it
    Given a department called "Werk 1"
    And a record whose MBCO says "about 60 internal lorries"
    When a card says "Werk 1's MBCO is about 60 internal lorries"
    Then the card passes

  # The repository's own account of the rule.

  Scenario: The repo no longer states a rule it does not follow
    Given ticket 09 says every figure on a card is a string the record holds, with no exemptions
    When a reader looks for the exemptions the shipped code actually makes
    Then ticket 09's own text names them — the verbatim preview, and a name the room supplies
    And it does so where the rule is stated, not as a footnote somewhere else

  # Cut: "Linie 2" and "Halle 60" as a second walk of the dead screen. One digit inside one name is
  # the same code path as another; "Halle 60" is still exercised by the check-level scenarios above,
  # and section A of the QA drives "Halle 45". Add a second name the day two names take different
  # paths.

  # Cut: the name carried through all five stages. `the-card-must-agree-with-the-record.feature`
  # already pins "every stage's card is checked, not the last one", and the exemption is one rule in
  # that one check. Add it back if a stage ever renders its department name differently.

  # Cut: a bare "45" on a card that does not name the room. That is ticket 09's "a figure the record
  # does not hold fails", unchanged; QA step 12 drives it by hand. Add it back if this file is ever
  # the only place the no-name path is walked.

  # Cut: "Werk 1's MTPD is 12 h" refused, and "about a working day" refused. The first is the
  # fabricated-count scenario with a different figure; the second is ticket 09's vagueness table,
  # which this ticket does not touch. Add them back if the exemption ever reads the word tables.

  # Cut: "a refused card is a bug and not a finding", "the check cannot be switched off", "it runs
  # before the human". Unchanged by this ticket and walked by
  # `the-card-must-agree-with-the-record.feature`; this file must not fork a second copy of them.

  # Cut: a department called "Key Accounts", where the name carries a word from the vague table
  # rather than a digit. The owner's ruling is about a digit inside a name and says so; widening it
  # to the word tables is a second ruling nobody has made. Add it the day a plant hits it.

  # Not a scenario, deliberately: what the dead screen looked like. The defect is the absence of a
  # message, and a scenario that asserts a stand-in sent nothing would have passed all through
  # ticket 22. It is section A of `archive/qa/a-digit-inside-a-name-is-not-a-figure.md`, driven by a human
  # who presses the button in a browser and watches the room stay empty.
