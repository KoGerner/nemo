Feature: Stage 3 — standardise the interview evidence
  As a BCM manager I reach stage 3 and the server has already done the work: it has read the
  transcript I bound at stage 2 and drafted the standardised evidence out of it, and it shows me
  its own work. I answer with the four labels. If I disagree, that is the point of the whole
  product, so nothing here may punish me for it.

  The story's own four scenarios come first, in its words. The ones after them are the rest of its
  "Done when", each written as something the manager, the operator or the next stage can watch
  happen.

  Two rulings of 2026-09-12 bind this file and are written into it as scenarios rather than left as
  prose. **The acknowledgement folds into the gradient answer** (`docs/stage-model.md` Stage 3,
  `docs/voice.md` §1): where the transcript did not reach a category the reason is recorded as
  "not stated", and the three options to tap were withdrawn, not deferred — so there is a scenario
  proving the affordance is absent, because an absence nobody tests comes back. And **a reservation
  is named in the composer** (`docs/voice.md` §4.3, "Where a reservation is named"): this is the
  stage that builds it, stages 4 and 5 reuse it, and the tap is what advances the walk so nothing
  ever waits on characters.

  Background:
    Given my company's room is "demo-1"
    And I have agreed the scope for "Incident and problem management"
    And I bound an interview transcript to this walk at stage 2

  # The story's four, in the words it asked them in.

  Scenario: The draft asserts only what the transcript states
    Given an approved transcript
    When the stage 3 card is drafted
    Then an RTO is asserted only where a label and a value co-occur
    And MTPD, RPO and MBCO are marked owner-stated with the quote beside them

  Scenario: An unmodelled dependency is a finding, not an invention
    Given the transcript names a dependency absent from the register
    Then it is raised as a finding
    And no asset id is invented for it

  Scenario: What the interview never reached is proposed honestly
    Given the interview did not reach some impact categories
    Then the worst case is proposed as all-unknown for those categories
    And the not-elicited acknowledgement is pre-filled from the transcript header

  Scenario: Disagreeing is a first-class answer
    Given the stage 3 card
    When I answer "needs discussion" and name what I disagree with
    Then my words are kept verbatim and carried forward to the signature
    And the walk continues rather than refusing

  # What the draft may and may not say.

  Scenario: A label with no value beside it produces no RTO
    Given the transcript says "RTO:" for problem management and never gives a figure
    When the stage 3 card is drafted
    Then no RTO is asserted for that activity
    And nothing on the card reads as though a target had been stated

  Scenario: An owner-stated figure carries the owner's own sentence
    Given the transcript holds Marek Sobotta's MTPD for incident and problem management
    When I read the stage 3 card
    Then the figure is marked owner-stated
    And his sentence is beside it, word for word as the transcript holds it
    And the figure is exactly the string the transcript holds, neither rounded nor sharpened

  Scenario: A dependency the register does model is named by its exact asset id
    Given the transcript names a dependency the register holds
    When the stage 3 card is drafted
    Then that dependency resolves to the register's exact asset id
    And no near-match or lookalike id is used for it

  Scenario: The unmodelled dependency's finding says what was heard and where to look
    Given the transcript names a dependency absent from the register
    When I read the open items on my card
    Then one of them is the dependency, in the words the transcript used for it
    And it says the register does not model it
    And it is an open item I would be accepting at sign-off, not a wall

  Scenario: The card leads with whatever the evidence forces a decision about
    Given the transcript contradicts the register about who owns Cisco Call Manager
    When I read the stage 3 card
    Then the first thing the card puts in front of me is that contradiction
    And what is already settled comes after it, or not at all

  # The fold: one tap, not two.

  # Cut: "the card asks me for one decision and not two" — the two scenarios below already say it
  # from both ends; add it back if a second control is ever proposed for this card.

  Scenario: The three-option acknowledgement is not drawn anywhere
    Given the interview did not reach some impact categories
    When I read the stage 3 card
    Then I am not offered three options for why they were not elicited
    And I am not asked to ratify a fact about a document I did not write

  Scenario: Where the transcript did not reach a category the reason is "not stated"
    Given the interview did not reach some impact categories
    And the transcript header gives no reason for it
    When I endorse the card
    Then what the walk records as the reason is "not stated"
    And no reason is invented at the card to stand in for it

  Scenario: Endorsing costs one tap and nothing typed
    Given I agree with everything on the stage 3 card
    When I press "endorsed"
    Then stage 3 is answered
    And I have typed nothing at all

  # What goes to disk, and what does not.

  Scenario: Stage 3 leaves me nothing to read
    When I endorse the stage 3 card
    Then no document has been written for me to read
    And the endorsed proposal is in the run state

  # Cut: "the standardised evidence is carried to stage 4 from the run state" — it asserts stage 4's
  # rendering, and there is no stage 4; add it back with the stage 4 ticket.

  # Where a reservation is named. This stage builds it; stages 4 and 5 reuse it.

  Scenario: Pressing a label other than endorsed asks for the naming
    Given the stage 3 card
    When I press "endorsed with reservations"
    Then the card says the next thing I type is what I am reserving
    And it says the box is the walk's for now, not the place I ask questions

  Scenario: The tap advances the stage, so nothing waits on my characters
    Given the stage 3 card
    When I press "blocked" and type nothing
    Then stage 3 is already answered
    And the walk has moved on rather than sitting waiting for characters

  Scenario: A reservation nobody names is recorded as unnamed
    Given I pressed "endorsed with reservations" and typed nothing
    When I reach the signature
    Then that answer shows as unnamed
    And it has not been rounded up to an endorsement
    And it was not refused either

  Scenario: What I type after the tap is attached to that stage's answer
    Given I pressed "needs discussion" at stage 3
    When I type "Marek gave me 6 h for that line last week, not 8"
    Then those words are attached to my stage 3 answer
    And they are stored exactly as I typed them, not tidied or summarised

  Scenario: My words reach the signature word for word
    Given I named a reservation at stage 3
    When I reach the signature
    Then my sentence appears there verbatim
    And it is attributed to the stage 3 card I pressed it on

  Scenario: The naming does not go to the ask lane
    Given I pressed "needs discussion" and the card is waiting for the naming
    When I type my sentence
    Then it is taken as the naming
    And the guidance is not searched, and I am not answered as though I had asked a question

  Scenario: Once the naming is taken the box is mine again
    Given I typed the naming for my stage 3 reservation
    When I ask what MTPD means
    Then I am answered from the guidance
    And my BIA has not moved because I asked

  # Cut: "stage 4 and stage 5 name a reservation the same way" — it builds two stages this ticket
  # does not own; add it back with the stage 4 ticket, which is where the reuse can be walked.

  # Nothing here may punish a disagreement.

  # Cut: "disagreeing does not cost me the walk" — the story's own fourth scenario and the verbatim
  # one above say it at the cards that exist; add it back when there is a signature to reach.

  Scenario: Both facts about an argued run are reported
    Given a run that argued with three cards
    When the run is reported
    Then it is reported as a better BIA
    And it is reported as a longer one
    And neither fact is left out to make the other look tidier

  # The rest of the walk's rules still hold at this card.

  # Cut: "stage 3's card is answered with the four labels" — the labels are `nemo.walk.GRADIENT`,
  # one tuple already pinned in `test_walk`; add it back if a stage ever draws its own labels.

  Scenario: The stage 3 card I see has been checked against the record behind it
    Given the stage 3 card says a figure the record does not hold
    When that card would be put in front of me
    Then no card is rendered at all
    And the failure is reported as a bug in the card generator
    And it does not appear as an open item on my card

  Scenario: The stage 3 card reads like a colleague wrote it
    When I read the stage 3 card
    Then it is written in sentences, not as a numbered list of machine actions
    And it names no tool, no field name and no file path anywhere but its "Source:" line
    And the reason comes before the figure

  Scenario: The stage 3 card tells me which files it read
    When I reach stage 3
    Then the card carries a "Source:" line
    And that line names the transcript I bound and the register it resolved against
    And every file it names is a file in my room
