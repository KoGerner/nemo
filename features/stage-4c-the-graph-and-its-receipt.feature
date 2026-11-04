Feature: Stage 4c — the receipt that binds the record
  As a BCM manager I accept my BIA and the walk binds a receipt to the record that just landed,
  there and then. The receipt says which record stage 4 accepted, so nobody has to take the walk's
  word for it. Until that receipt binds, my walk is saved and not yet finished — and it says so,
  rather than telling me it is done while nothing has been bound.

  This is the movement that fixes v1's worst symptom. On 2026-08-31, in room `adler-stjmed`, a run
  declared itself closed while the graph URL showed nothing new: the record never went through the
  write lane, so no regeneration ever fired, and closure was bookkeeping about gates rather than a
  statement about artefacts on disk.

  Ticket 243 (ADR-0040) took nemo's own dependency page out: nobody was ever shown it, and the
  grouped graph the skin draws is the only picture. So the receipt carries the record's fingerprint
  and its schema version and nothing about a page, and the gate past stage 4 binds on `record_sha`
  alone. The scenarios that pinned nemo's page went with it.

  Two rules from `docs/adr/0010` are what the scenarios below are written against: an interrupted
  movement is re-executed rather than rolled back, and the run file is a claim while the artefacts
  are the truth.

  Background:
    Given my company's room is "demo-1"
    And I walked to stage 4 and accepted the record the server refereed

  Scenario: Saved is not finished
    Given a record has been saved and the receipt has not yet bound
    Then the walk's status is "record_saved_graph_pending"
    And stage 5 cannot start

  Scenario: A record write draws no page of nemo's own
    Given a record has just been saved
    When I look at what my room holds
    Then nothing is under "public/graph/"

  Scenario: The receipt says which record stage 4 bound, and nothing about a page
    Given a receipt exists
    Then it carries the fingerprint of the record on disk and the record's version, and nothing else

  Scenario: The receipt is bound before I am spoken to
    Given I press "endorsed" at stage 4
    When the walk answers me
    Then nothing about the receipt is left for a later job to finish

  # Binding, both signs. A deadlock is the same failure as a false closure, wearing the other sign.

  Scenario: Once the receipt binds the walk is not held up
    Given a record has just been saved
    When the receipt binds
    Then the walk is no longer at "record_saved_graph_pending"
    And stage 5 can start

  Scenario: A receipt is not a receipt for some other record
    Given a receipt exists
    When the record in my room is replaced by one that receipt was never taken over
    Then the walk is back at saved and not yet finished
    And the receipt binds again to the record now on disk before stage 5 can start

  Scenario: A stop between the record and the receipt costs nothing but the movement again
    Given the walk stopped after the record landed and before the receipt bound
    When it resumes and does the movement again
    Then the receipt binds and the walk is waiting for me again

  # v1's symptom, stated as the thing that may never be said.

  Scenario: No walk says it is finished while the receipt has not bound
    Given a record has been saved and the receipt has not yet bound
    When I read everything the walk says about where it stands
    Then no sentence says my BIA is finished
    And it says the record is saved and the picture is not bound yet
