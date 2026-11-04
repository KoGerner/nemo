Feature: A room shows its processes and one Stage 1 card
  As a BCM manager I open my room link on my phone, see which processes my company has on
  file, open the BIA for one of them, and agree the scope in a single press.

  The first five scenarios are `reference/01-walking-skeleton.feature`, lifted whole — that file
  was deleted by 221 and lives in git history at `a5991da`. The ones
  after them are the rest of the story's "Done when", each written as something the manager or
  the owner can watch happen.

  Background:
    Given my company's room is "demo-1"
    And our interview transcripts name the departments "Incident and problem management" and "Access management"
    And our dependency register names the departments "Incident and problem management" and "IT event management"
    And no BIA has been started in the room yet
    And my room link is the page with "?room=demo-1"

  # Each once, in alphabetical order: `sorted(set(...))`. No collation, no ordering table.
  Scenario: I see which processes we have on file
    When I open my room link
    Then I am offered exactly these processes, each once and in alphabetical order:
      | process                         |
      | Access management               |
      | IT event management             |
      | Incident and problem management |
    And each one is a button I can press
    And I am not asked to type a process name

  Scenario Outline: Opening a process gives me its scope card
    Given I have opened my room link
    When I open the BIA for "<process>"
    Then the card is headed "Stage 1 of 5 · Scope"
    And it proposes one activity, "<process>"
    And it offers one button, "Yes, that's the scope"
    And it offers me nothing else

    Examples:
      | process                         |
      | Incident and problem management |
      | Access management               |

  Scenario: One press agrees the scope and tells me so
    Given I have opened the BIA for "Incident and problem management"
    When I press "Yes, that's the scope"
    Then I read "Got it. The scope for Incident and problem management is agreed. That's stage 1 of 5 done, and there's nothing more to do here yet."
    And the button is gone
    And nothing further is asked of me

  Scenario: My decision is kept with the company's files
    Given I have agreed the scope for "Incident and problem management"
    When I look at what the room holds
    Then my decision is on file at "output/.bia-runs/incident-and-problem-management.json"
    And it says stage 1 was decided "yes"

  Scenario: I come back later and I am not asked again
    Given I have agreed the scope for "Incident and problem management"
    And I have closed the page
    When I open my room link and open the BIA for "Incident and problem management" again
    Then the card is headed "Stage 1 of 5 · Scope"
    And I read "The scope for Incident and problem management is already agreed, from your last visit."
    And I am not asked to agree it a second time

  Scenario: The card tells me which files it read
    Given I have opened my room link
    When I open the BIA for "Incident and problem management"
    Then the card carries a "Source:" line
    And that line names every file the proposal was read from
    And every file it names is a file in my room

  Scenario: The card reads like a colleague wrote it
    Given I have opened the BIA for "Incident and problem management"
    When I read the card
    Then it is written in sentences, not as a numbered list of machine actions
    And it names no tool, no field name and no file path anywhere but its "Source:" line

  Scenario: The method on my card is my company's own, not one the software invented
    Given our method file sets our impact categories, our time horizons, our 1-5 scale, the level at which impact is no longer tolerable, and the words we use for data loss
    When I open the BIA for "Incident and problem management" and agree the scope
    Then the method my walk carries is the one in our method file, parameter for parameter
    And nothing appears in it that our method file does not say

  Scenario: I get to a decision on file without typing anything
    Given I have opened my room link
    When I open the BIA for "Incident and problem management" and agree the scope
    Then every single thing I did was a press
    And I typed nothing at all — not a process name, not a stage, not a number

  Scenario: A stage begins because I pressed something, never because the assistant said it would
    Given I have opened my room link
    When the assistant writes that it is opening the BIA for "Incident and problem management"
    Then no BIA has been opened for "Incident and problem management"
    And nothing is on file at "output/.bia-runs/incident-and-problem-management.json"
    And the only way to open it is still the button named "Incident and problem management"

  # Ticket 03's conditional write, compare-and-set on revision. Nothing new is built here.
  Scenario: A save that was overtaken does not quietly win
    Given I have opened the BIA for "Incident and problem management"
    And the room's record of my walk has moved on since my page read it
    When I press "Yes, that's the scope"
    Then my press does not land on top of the newer record
    And the room still holds the newer record
    And I read that someone else saved this BIA while I was reading

  Scenario: The room remembers, so I do not have to
    Given I have agreed the scope for "Incident and problem management"
    And everything that was said in the conversation has been thrown away
    When the walk is picked up again knowing only my room and "Incident and problem management"
    Then the correct next card comes back
    And it carries what was saved for "Incident and problem management"
    And I am asked nothing at all to rebuild it

  Scenario: I cannot be dropped into a later stage that has not been earned
    Given I have agreed the scope for "Incident and problem management" and nothing more
    When a later stage of the BIA is asked for by name
    Then that stage is not served
    And what comes back is the card for the stage my walk has actually reached

  Scenario: Stage 1 leaves me nothing to read
    Given I have agreed the scope for "Incident and problem management"
    When I look at what the room holds
    Then no document has been written for me to read
    And the only new thing on file is my decision

  Scenario: A room I have just claimed already holds my company's work
    Given I claim a room of my own
    When I open it
    Then it holds our interview transcripts and our company files
    And it holds a BIA already in progress

  # NOT BUILT until ticket 15 binds `run_id`. Until it passes, the skeleton is not safe against a
  # walk that closes over work it did not do, and nobody may read it as if it were.
  @not-yet-built-ticket-15
  Scenario: The BIA a room ships cannot be closed over by a walk that did no work
    Given a room that ships a BIA already in progress
    And a walk that has refereed nothing and written nothing
    When that walk tries to finish over the BIA the room shipped
    Then it is refused, because that walk did not produce it
