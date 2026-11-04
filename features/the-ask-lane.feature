Feature: The ask lane
  In a room, a manager asks a BCM question in their own words and gets an answer drawn from the
  frozen guidance corpus, with its citation printed on screen. This is one of the demo skin's two
  model jobs, and it touches no record.

  The corpus is frozen at release `2026.11.1` — 453 chunks from ten sources — and served by the
  open guidance connector `mcp.ai4bcm.org`, which needs no bearer token (ADR-0046, ADR-0062). It is not
  `agent.ai4bcm.org`, the BIA session connector, which does. ISO 22301, ISO/TS 22317 and the BCI
  Good Practice Guidelines are not in it and are not going in (ADR-0005).

  The model is the skin's, not the product's. nemo is deterministic; a production front end brings
  its own model and never touches this lane.

  Scenario: A question is answered from the corpus, with its source
    Given I am in my room
    When I ask what the corpus says about setting an MTPD
    Then I get an answer drawn from the corpus
    And the citation is printed on screen where I can see it
    And it names one of the ten sources in release "2026.11.1", with a locator I can look up

  Scenario: A question the corpus cannot answer says so
    Given the corpus holds nothing on ISO/TS 22317
    When I ask what ISO/TS 22317 says about setting an MTPD
    Then I am told the corpus does not cover it
    And nothing is invented to fill the gap

  Scenario: The answer is fetched from the open guidance connector
    Given I am in my room
    When I ask a BCM question
    Then the corpus is read from "mcp.ai4bcm.org"
    And no bearer token is sent
    And the BIA session connector "agent.ai4bcm.org" is never called

  Scenario: The model's thinking never reaches me
    Given I am in my room
    When I ask a BCM question
    Then the answer on screen is the answer
    And none of the model's reasoning is printed with it

  Scenario: The cap is a legible stop, not a hang
    Given the OpenRouter key cap has been reached
    When I ask a question
    Then I am told plainly that the lane is unavailable
    And the walk is not left in an unfinished state

  Scenario: The cap is a hard stop, not a degradation
    Given the OpenRouter key cap has been reached
    When I ask a second question
    Then it fails the same way at once
    And I am offered no buttons-only substitute for the answer

  Scenario: Asking never touches the record
    Given a saved record
    When I ask any number of questions
    Then the record's fingerprint is unchanged
