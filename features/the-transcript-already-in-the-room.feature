Feature: Stage 2 — the transcript already in the room
  As a BCM manager I reach stage 2 of my BIA and the interviews are already in my room. I read a
  preview of each one, press the one this BIA rests on, and answer it with the four labels. One
  tap, nothing typed.

  The story's own four scenarios come first, in its words. The ones after them are the rest of its
  "Done when", each written as something the manager or the operator can watch happen.

  Transcripts are the evidence, not a side effect. The referee proves nothing was invented by
  finding each quote verbatim in a readable file, so the question was only ever whose disk — and
  for a demo room the answer is ours, readable by the operator (ADR-0002).

  Background:
    Given my company's room is "demo-1"
    And I have agreed the scope for "Incident and problem management"
    And my room holds transcripts under "07_Interviews/"

  Scenario: The room's transcripts are offered with a preview
    When I reach stage 2
    Then each transcript is offered with an exact preview of its content
    And I am not asked to type a path

  Scenario: Picking one binds it to this walk
    Given the transcripts are offered
    When I pick one and answer the gradient
    Then the walk records which transcript it rests on, and that transcript's fingerprint
    And I have typed nothing

  Scenario: A transcript that changed under me is caught
    Given I bound a transcript at stage 2
    When its bytes change before stage 3 reads it
    Then the change is raised as a finding rather than passing unnoticed
    And the finding names the interview I bound

  Scenario: A room with no transcript offers the other path
    Given my room holds no transcript for this process
    When I reach stage 2
    Then I am offered the interview in the room instead
    And stage 2 is not blocked

  # Both homes, because an interview held in the room earlier is evidence exactly as an interview
  # we already had is: `07_Interviews/` and `output/owner-interviews/`.
  Scenario: An interview held in the room earlier is offered beside the ones we already had
    Given my room also holds an interview it recorded earlier for "Incident and problem management"
    When I reach stage 2
    Then both interviews are offered, each with its own preview
    And neither is offered twice

  Scenario: Stage 2 leaves me nothing to read
    Given the transcripts are offered
    When I pick one and answer the gradient
    Then no document has been written for me to read
    And the only new thing on file is which transcript my walk rests on, and its fingerprint

  Scenario: The stage 2 card tells me which files it read
    When I reach stage 2
    Then the card carries a "Source:" line
    And that line names every interview the card offered me
    And every file it names is a file in my room

  Scenario: The stage 2 card reads like a colleague wrote it
    When I read the stage 2 card
    Then it is written in sentences, not as a numbered list of machine actions
    And it names no tool, no field name and no file path anywhere but its "Source:" line
    And it asks me for one decision and not two

  # ADR-0011, the owner's ruling of 2026-09-12. Stage 2 binds the evidence the whole BIA rests on.
  Scenario: Stage 2's card is answered with the four labels
    When I reach stage 2
    Then the card offers exactly these four ways to answer it:
      | endorsed                   |
      | endorsed with reservations |
      | needs discussion           |
      | blocked                    |
    And it offers me no fifth way, and no "not sure"

  # The other half of the same ruling: do not "fix" Stage 1 to match Stage 2.
  Scenario: Stage 1's card still offers one control and draws no gradient
    Given I have opened the BIA for "Access management" and not agreed its scope
    When I read that card
    Then it offers one button, "Yes, that's the scope"
    And the four labels are not drawn on it

  Scenario: Stage 1's one press is still recorded as one of the four labels
    Given I have opened the BIA for "Access management" and not agreed its scope
    When I press "Yes, that's the scope"
    Then what my walk records underneath is "endorsed"

  # Ticket 09 built the door and nothing went through it. Both stages share the card path, so both
  # are checked, and the check is what the manager never sees working.
  Scenario: The stage 2 card I see has been checked against the record behind it
    Given the stage 2 card says a figure the record does not hold
    When that card would be put in front of me
    Then no card is rendered at all
    And the failure is reported as a bug in the card generator
    And it does not appear as an open item on my card

  Scenario: Stage 1's card goes through the same door
    Given the stage 1 card says a figure the record does not hold
    When that card would be put in front of me
    Then no card is rendered at all
