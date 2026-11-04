Feature: Stage 4a — the refereed record
  As a BCM manager I reach stage 4 and the server shows me the record it refereed: what it scored,
  the quote and the file behind every score, the reason before every figure, and the things it will
  not settle on my behalf. I accept it with one tap, and that is where my walk stops being
  reversible. What lands on disk is what I saw, and it is the work this run did — never the BIA the
  room happened to ship with.

  The story's own four scenarios come first, in its words. The ones after them are the rest of its
  "Done when", each written as something the manager, the operator or the next stage can watch
  happen.

  This ticket is the first of stage 4's three movements and owns exactly one of them: the record at
  `output/<process>/bia-record.json` (one per process since ticket 235). The four views are ticket
  16 and the graph and its receipt ticket 17,
  so nothing here may assert a view file, a graph page or a bound receipt — the run stops at
  "saved, and not yet finished" (`docs/adr/0010`).

  Two behaviours were deferred to this file by name and are picked up here rather than lost. Ticket
  14 cut "the standardised evidence is carried to stage 4 from the run state" and "stage 4 and
  stage 5 name a reservation the same way" with "add it back with the stage 4 ticket"; the halves
  of each that stage 4 can actually walk are below. And `features/the-walking-skeleton.feature`'s
  `@not-yet-built-ticket-15` scenario is the story's third scenario in the skeleton's words — this
  is the ticket that builds it, so that tag comes off there when these pass.

  Background:
    Given my company's room is "demo-1"
    And I have agreed the scope and bound the interview
    And I endorsed the standardised evidence at stage 3

  # The story's four, in the words it asked them in.

  Scenario: The card shows what was refereed
    Given a refereed record
    When the stage 4 card is drawn
    Then every scored category shows its exact quote and the file it came from
    And each finding is shown as a finding rather than a refusal

  Scenario: The reason comes before the figure
    Given an MTPD derived from the grid
    Then the card says why before it says the number

  Scenario: A record this run did not produce cannot be accepted
    Given a room seeded with a valid record and a worked folder
    And a walk that never refereed and never wrote
    When the walk tries to move past stage 4
    Then it is refused, naming the stale record

  Scenario: Nothing lands without the human
    Given the card has been shown
    When I have not answered the gradient
    Then no bytes are written

  # What the card is made of.

  # Cut: "every score is traceable to something I can read" — the story's own first scenario says
  # it, and that the quote is in the file is a referee check; add it back if the card ever quotes
  # from somewhere the referee did not read.

  # Cut: "the MTPD is said as a consequence, not as a label" — the story's own second scenario says
  # it, and the derivation behind it is the referee's; add it back if the card ever prints a bare
  # label again.

  Scenario: An MTPD nobody derived is not printed as though somebody had
    Given the grid never reaches the threshold within the horizons
    When I read the stage 4 card
    Then it says so in the manager's words
    And no MTPD figure is shown for that activity

  Scenario: The findings are open items I would be accepting, not a wall
    Given the referee raised findings on this record
    When I read the stage 4 card
    Then the findings are on it as open items with what was seen and where
    And I can still accept the record with them on it
    And nothing about them stops the stage

  Scenario: A defect the referee will not pass is not dressed up as a finding
    Given the record quotes a sentence no file in my room holds
    When the stage 4 card would be drawn
    Then the record is not offered for acceptance at all
    And what is wrong with it is said before I am asked for anything

  Scenario: The stage 4 card reads like a colleague wrote it
    When I read the stage 4 card
    Then it is written in sentences, not as a numbered list of machine actions
    And it names no tool, no field name and no file path anywhere but its "Source:" line
    And every file the "Source:" line names is a file in my room

  Scenario: Stage 3's endorsed evidence is what stage 4 shows me
    Given I endorsed the standardised evidence at stage 3
    When I read the stage 4 card
    Then the figures on it are the ones I endorsed, character for character
    And nothing was re-read from the transcript to produce them a second time

  # Checked before I am asked, not after I have said yes.

  Scenario: A draft's content problems are reachable before anyone approves it
    Given a draft record with content problems
    When it is checked without anybody having confirmed anything
    Then its content problems come back
    And it is not answered with "approval missing" instead

  Scenario: Checking a draft writes nothing
    Given a draft record with content problems
    When it is checked without anybody having confirmed anything
    Then no bytes are written anywhere in my room

  # Cut: "the problems are shown before the tap, not behind it" — "a defect the referee will not
  # pass is not dressed up as a finding" above says the same thing from the card's end; add it back
  # if the draft check and the card are ever built as two separate orders.

  # The one tap, and what it costs.

  Scenario: Accepting the record costs one tap and nothing typed
    Given I agree with the record on the stage 4 card
    When I press "endorsed"
    Then stage 4 is answered
    And I have typed nothing at all

  # Cut: "the card offers the four labels and no second control" — the labels are
  # `nemo.walk.GRADIENT`, one tuple pinned in `test_walk` for every stage; add it back if a stage
  # ever draws its own labels. QA step 13 still checks it on the running skin.

  Scenario: A reservation at stage 4 is named the way stage 3 named it
    Given the stage 4 card
    When I press "endorsed with reservations"
    Then the card says the next thing I type is what I am reserving
    And stage 4 is already answered rather than waiting for my characters
    And my words are kept verbatim and carried forward to the signature

  # What lands on disk, and only then.

  Scenario: The record lands where the walk says it lands
    Given I accepted the record
    When I look at what my room holds
    Then "output/incident-and-problem-management/bia-record.json" holds the record I accepted

  Scenario: The bytes on disk are the record the card showed me
    Given I accepted the record
    When the saved record is read back
    Then it matches what the card put in front of me
    And nothing was added to it after I had seen it

  Scenario: A record the room has moved on from is not overwritten blind
    Given the record in my room moved on after this walk read it
    When my acceptance tries to save
    Then the save is refused as out of date
    And the record already in the room is left as it is

  Scenario: Saved is not finished
    Given I accepted the record
    When the walk reports where it is
    Then it says the record is saved and the picture is not bound yet
    And it does not report the walk as finished

  Scenario: Accepting twice over the same record writes the same bytes
    Given the walk stopped just after the record landed
    When it resumes and does the movement again
    Then the record on disk is byte for byte what it was
    And nothing is written twice into the room for me to read

  # The record must be this run's work.

  Scenario: The record I accept is not the one the room shipped with
    Given a room that ships a BIA already in progress
    When I walk to stage 4 and accept the record
    Then the record now in my room is not the one the room shipped
    And it carries this walk's own identity

  # Cut: "a walk that refereed nothing cannot move past stage 4 over a seeded record" — it is the
  # story's own third scenario in other words, and the timestamp scenario below is the half of it
  # nobody else states; add it back only if the two are ever built apart.

  Scenario: The refusal does not depend on a timestamp the record has never had
    Given a seeded record with no modification time recorded in it at all
    And a walk that has refereed nothing and written nothing
    When that walk tries to move past stage 4
    Then it is still refused
    And the refusal rests on which run produced the record, not on when it was touched

  Scenario: A record this run advanced is a record this run may accept
    Given a room that ships a BIA already in progress
    And a walk that refereed it and wrote it
    When that walk moves past stage 4
    Then it is allowed through
    And the record in the room carries that walk's identity

  # The receipt says what was actually checked.

  Scenario: What the walk says it checked is what it checked
    Given I accepted the record
    When I read what the walk says about the record being checked
    Then it names the checks the referee actually ran on this record
    And every clause of it is true of this run

  Scenario: A run that never refereed says nothing about having refereed
    Given a walk that has refereed nothing and written nothing
    When I read everything the walk says about that record
    Then no sentence claims the record was checked
    And no sentence claims it was saved

  # Cut: "the findings I accepted are named where I accepted them" — nobody measured a run that
  # lost them, and the record holds the referee's findings either way; add it back with the
  # signature ticket, which is where an accepted finding has to reappear.

  # One card, five activities. Whether it holds is measured, not assumed.

  Scenario: A department with five activities still gets one stage 4 card
    Given my department has five activities in scope
    When I reach stage 4
    Then there is one card for all five
    And it is answered with one gradient answer

  Scenario: Each of the five activities is on that card in full
    Given my department has five activities in scope
    When I read the stage 4 card
    Then every one of the five carries its own grid, MTPD sentence, RTO, RPO and dependencies
    And no activity is summarised away or left for a later card

  Scenario: The decision is findable without reading the whole card
    Given my department has five activities in scope
    When I read the stage 4 card
    Then what I am being asked to decide is at the top of it
    And what the referee will not settle comes before what is already settled

  # The rest of the walk's rules still hold at this card.

  Scenario: The stage 4 card I see has been checked against the record behind it
    Given the stage 4 card says a figure the record does not hold
    When that card would be put in front of me
    Then no card is rendered at all
    And the failure is reported as a bug in the card generator
    And it does not appear as an open item on my card

  # Cut: "asking a question at stage 4 does not move my BIA" — the composer is routed once for the
  # whole walk and that is already walked at stages 2 and 3; the one stage-4 thing about it, the
  # reservation holding the composer, is above. Add it back if a card ever routes its own composer.
