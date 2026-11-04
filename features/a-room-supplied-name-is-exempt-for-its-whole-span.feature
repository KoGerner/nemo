Feature: A room-supplied name is exempt for its whole span
  A department called `Key Accounts` trips the vague-word check, `render` raises
  `CardGeneratorBug`, and the manager gets a dead screen at whichever stage names the department.
  That is a walk stopped mid-way, which `spec.md` ranks above everything else. It is the class of
  defect ticket 32 just fixed, one word to the left: `card.py` hands the name spans to
  `_untraceable_figures` and not to `_untraceable_words`, so today
  `untraceable("Key Accounts is the scope", {}, ("Key Accounts",))` is `['key']`.

  The owner's ruling, 2026-09-14, answering open question 13: **a name the room supplied is never
  a figure and never a vague word, whatever it contains — it is exempt for its whole span.**
  Ticket 32 scoped the exemption to a digit inside a name deliberately; the ruling of 2026-09-13
  was about digits and widening it was a second ruling nobody had made. This is that second ruling.

  The scoping rule from ticket 32 holds unchanged and is the whole reason this is safe. The names
  are never added to what the record holds. A room with a `Key Accounts` in it exempts `key` only
  where it sits inside an occurrence of that name on that card — never a bare `key` elsewhere on
  any card of the walk. So half of what follows is the dead screen going away and half is what is
  still refused, and the second half is the one that fails the ticket if it goes wrong.

  `Prime Cuts` and `Critical Care`, which the ticket names beside `Key Accounts`, do not in fact
  trip anything today: neither `prime` nor a bare `critical` is in §4.3's tables. The words that do
  are `key`, `vital`, `significant`, `reasonable`, `soon`, `material impact` and `mission
  critical`, and the scenarios below use names built from those, because a scenario has to be true.

  # The dead screen, from the manager's end.

  Scenario: My department is called "Key Accounts" and I get a card, not a dead screen
    Given my company's department is called "Key Accounts"
    # Ticket 164: re-aimed from the demo skin's process button to the walk that draws the card;
    # the phone app draws no process buttons and no stage card through `render`.
    When I open the BIA for it and reach the stage 1 card
    Then the card is on my screen
    And nothing was refused over the word "key" in the name of my own department

  Scenario: The record is empty at stage 1 and the name is still not a vague word
    Given a stage 1 card for "Vital Signs" whose record holds nothing at all yet
    When the card is checked against that record
    Then it is not refused, because the only vague word on it sits inside the name

  Scenario: The name stands in the middle of a sentence and the card still passes
    Given a department called "Key Accounts"
    When a card says "The scope of this BIA is Key Accounts, and nothing wider."
    Then the card passes

  # What is still refused. This half is the ticket: the carve-out is the span and nothing wider.

  Scenario: The same word outside the name is still refused on the very card that names it
    Given a department called "Key Accounts"
    When a card says "Key Accounts is the scope and the key risk is staff"
    Then the card is refused
    And the refusal names "key" as the string the record does not hold
    And it names it once, for the bare word and not for the one inside the name

  Scenario: A card that never names the department licenses nothing
    Given a department called "Key Accounts"
    When a card says "The key risk is staff turnover."
    Then the card is refused
    And the refusal names "key" as the string the record does not hold

  Scenario: A phrase that only starts inside the name is still refused
    Given a department called "Group Business"
    When a card says "Group Business critical work runs here."
    Then the card is refused
    And the refusal names "business critical" as the string the record does not hold

  # The repository's own account of the rule.

  Scenario: The repo no longer tells the next reader the narrower rule
    Given `nemo.card`'s module docstring and `untraceable`'s docstring state the name exemption
    When a reader looks for what a name the room supplies is exempt from
    Then both say a name and not a digit, so the whole span is exempt whatever it contains
    And the scoping rule is stated unchanged: never added to what the record holds

  # Cut: `Vital Signs` on a `Key Accounts` card refused, i.e. a name this room does not hold. Word
  # for word a scenario of `a-digit-inside-a-name-is-not-a-figure.feature` (`Werk 7`), which reads
  # the same `_name_spans` this ticket does not touch; QA step 14 drives it by hand. Add it back the
  # day the two checks build their spans separately.

  # Cut: `Key Accounts' MTPD is about a working day` refused for `a working day`. A vague word
  # outside the span on a card that names the department, which is the `and the key risk is staff`
  # scenario above with a different word. Add it back if a phrase and a word ever take different
  # paths out of the span check.

  # Cut: a department called `Halle 45` still getting a card, and `The MBCO for Halle 45 is 45
  # cutters` still refused. That is ticket 32 and it has its own feature file and its own proof
  # file; the done-when asks for `tests/ui/test_a_digit_inside_a_name_is_not_a_figure.py` to pass
  # untouched, which proves it without a second copy of it living here. Section D of the QA drives
  # both strings by hand as well. Add them back the day this file is the only place they are walked.

  # Cut: a name carrying both a digit and a vague word, e.g. `Key Accounts 24`. One rule now reads
  # the spans for both checks, so this is the two scenarios above running on one string rather than
  # a third behaviour. Add it the day the two checks read the spans differently.

  # Cut: the name carried through all five stages, and `a refused card is a bug and not a finding`,
  # and `the check cannot be switched off`. Unchanged by this ticket and walked by
  # `the-card-must-agree-with-the-record.feature`; this file must not fork a second copy of them.

  # Cut: the record's own hedge still passing beside a name carrying a vague word. That is ticket
  # 09's both-directions scenario with a name added, and the name is not what decides it.

  # Not a scenario, deliberately: what the dead screen looked like. The defect is the absence of a
  # message, and a scenario asserting that a stand-in sent nothing would have passed all through
  # ticket 22. It is section A of `archive/qa/a-room-supplied-name-is-exempt-for-its-whole-span.md`, driven
  # by a human who presses the button in a browser and watches the room stay empty.
