Feature: The ask lane must refuse rather than answer from nothing

  The ask lane drops any excerpt whose corpus tag is not the frozen release. If the connector's tag
  moves, every excerpt is dropped — and the lane is called anyway. Probed on ticket 11: the model
  returned an answer with zero `Source:` lines, produced from nothing at all. This is not
  hypothetical: the local guidance repo stamped `2026.09` while the connector served the release
  after it, so it was one release bump away.

  A lane that answers with no sources breaks refusal-to-invent and ADR-0005 at once, and it breaks
  them in the one direction nobody checks: a confident answer looks like a working system. The
  referee catches an invented figure; nothing catches an invented answer. So zero surviving excerpts
  refuses, and says why.

  Two cases, and a facilitator acts on them differently. The guidance corpus answered and nothing
  matched the question — ask it another way. The guidance corpus is the wrong release and the lane
  cannot vouch for anything — stop asking, and fix the corpus before the room opens.

  This ticket does not reopen what the corpus holds (ADR-0005 is an owner call).

  Cut, with when to add it back:
  - "A refusal leaves the room usable" — `the-ask-lane.feature` already pins "the walk is not left
    in an unfinished state" on the cap refusal, which is the same return path. Add it back if a
    refusal ever stops being a returned answer.
  - "The frozen release still answers, with its sources" — `the-ask-lane.feature`'s first scenario
    is the same walk. Add it back if that one is ever retired.
  - "The model is never called" and "The two refusals read differently" were separate scenarios on
    an identical Given/When; their assertions are the last three lines of the first scenario below.

  Scenario: The corpus is the wrong release, so the lane cannot vouch for anything
    Given the guidance connector is serving a corpus release that is not the frozen one
    When I ask what the corpus says about setting an MTPD
    Then I am told the guidance corpus is not the frozen release and the lane cannot vouch for it
    And no answer to my question is produced
    And the model is never called
    And no "Source:" line is printed, because there is nothing to cite
    And it does not read like the refusal for a question nothing in the corpus matched

  Scenario: The corpus answered, and nothing matched the question
    Given the guidance connector is serving the frozen release
    And the corpus holds nothing on what I am about to ask
    When I ask a question the corpus does not match
    Then I am told the guidance corpus holds nothing on my question
    And nothing is invented to fill the gap

  Scenario: The expected release is named in one place
    Given the frozen release the lane expects is named once and nowhere else
    When the corpus moves to a new release and that one name is changed to match
    Then the lane answers from the new release
    And no other place had to be edited to make it stop refusing

  # Retired by ticket 164: "A tag mismatch is surfaced before anyone in a room asks anything". It
  # read the demo skin's startup hook, which printed `release_note()` for the operator. The phone
  # app has no startup hook and never calls `release_note()` (ticket 161 retired the same read in
  # `src/nemo/test_ask.py`, its row 1); `release_note` itself is pinned there, against a served
  # tag that agrees, one that does not, and a connector that cannot be reached.
