Feature: A run that already exists gets an identity too
  ADR-0011's own room shape raises `KeyError('run_id')` at stage 4. A walk that starts from a
  prepared chat — which is the product — stops dead before the handover, and that is the whole of
  why this is a BLOCKER for the demo.

  `run_id` is minted only by `_opened_run`, and `agree_scope` calls it only when the card has
  nothing saved. A run that exists **before the first press** — which is ADR-0011's entire premise,
  a chat that arrives already at Stage 1 with nothing decided — never gets one. Measured in
  `docs/reviews/code-review-2026-09-13.md` against exactly the room the ADR describes: after the
  Stage 1 press the run carries `['decisions','process','revision','room','schema','stage',
  'status']`, `run_id` is absent, and Stage 4 raises. The same cause skips the method copy, so that
  run reaches Stage 3 with no lenses and an empty grid, and loses its `Source:` provenance.

  **This is a defect against ticket 15's binding, not an argument about ADR-0011's wording.** That
  wording stays open question 2 and is the owner's. The product crashing on the room shape the ADR
  describes is not.

  Why no test catches it: every test room is `room(tmp_path)` with no `output/.bia-runs/` — a room
  ADR-0011 says a minted room is not. So the rooms below are the ADR's shape, and the last two
  scenarios keep the shape the suite already walks green beside it.

  Background:
    Given my room is the one ADR-0011 describes
    And it ships a run for "Incident and problem management" whose stage is 1 and whose decisions are empty
    And that run carries no identity of its own

  # The premise. A run at stage 1 with nothing decided has decided nothing, whatever it is that
  # arrived with the room.
  Scenario: The scope is still mine to agree
    When I open the BIA for "Incident and problem management"
    Then I am asked to agree the scope, the way a room with no run at all asks me
    And nothing tells me the scope is already agreed

  Scenario: The first answer gives that run an identity
    When I agree the scope for "Incident and problem management"
    Then the run on file carries an identity of its own
    And it is the same shape of identity a run created at that press would have got

  Scenario: The method came with the identity
    Given I have agreed the scope for "Incident and problem management"
    When I reach stage 3
    Then the evidence is laid over the lenses my room's method names
    And the grid is not empty

  Scenario: The card still says which files it read
    Given I have agreed the scope for "Incident and problem management"
    When I read the card
    Then it carries a "Source:" line
    And every file it names is a file in my room

  Scenario: Stage 4 does not raise, and the walk carries its record past it
    Given I have agreed the scope for "Incident and problem management" and walked on to stage 4
    When the record for that walk is built and accepted
    Then it is built, and it carries that run's identity
    And nothing on my screen is an exception out of the walk
    And the walk may go on to stage 5, because that record is its own work

  # The mint happens where an identity is missing and nowhere else. A second minting would break
  # exactly the binding this ticket is repairing: the record on disk would name a run the walk is
  # no longer called.
  Scenario: An identity is minted once and does not change under me
    Given I have agreed the scope for "Incident and problem management"
    When I answer the stages that follow, one after another
    Then the identity on the run is the one it was given at the first answer, every time

  # Cut: two prepared runs carry different identities — that is `uuid.uuid4()`. Add it back the day
  # the mint stops being uuid4 and starts deriving the id from the room or the process.

  # Ticket 15's binding is not loosened to make this work: a record somebody else's run produced is
  # still refused, and a run given its identity here is not thereby given somebody else's work.
  Scenario: A record another run produced is still refused
    Given my room also holds a BIA record produced by some other run
    When I agree the scope for "Incident and problem management" and walk on to stage 4
    Then the walk refuses to finish over that record
    And it says the record was not produced by this walk

  # Cut: a run created at the first answer still gets its identity — `room(tmp_path)` is that room,
  # so the whole suite is already this scenario. Add it back if a test room ever ships a run file.
