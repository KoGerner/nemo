Feature: The room door
  A manager scans a code and lands in their own room, with no account, no password and nothing
  to type — and lands in *only* that room. The code in the QR is a credential, not an address:
  it is presented to the demo skin as an authenticated identity, one identity per room.

  Isolation has no partial credit. With no auth callback registered, `get_current_user` returns
  `None` and every `if current_user:` guard becomes a no-op at the same moment. The property
  comes from distinct identifiers, not from the framework.

  Scenario: My room link puts me in my room
    Given room "demo-1" and room "demo-2" both hold files
    When I open the link for "demo-1"
    Then I am in room "demo-1" without being asked for an account or a password
    And the demo skin holds "demo-1" as my identity

  Scenario: I cannot reach another room's file
    Given I am in room "demo-1"
    When I request a file belonging to room "demo-2" over an HTTP GET
    Then I am refused with 401

  Scenario: I cannot fire another room's callback
    Given I am in room "demo-1"
    When I post an action belonging to room "demo-2"
    Then I am refused with 401
    And room "demo-2"'s callback did not run

  Scenario: I cannot join another room's socket
    Given room "demo-2" has a live socket
    When I connect carrying room "demo-2"'s session identifier
    Then the connection is refused
    And room "demo-2"'s occupant is not evicted

  Scenario: A crafted session identifier cannot write outside the room
    Given a connect payload whose session identifier is "../../scratch"
    When the connect handler runs
    Then it is refused because the value is not a UUID
    And the directory "scratch" still exists

  Scenario: One browser profile holds one room
    Given I am in room "demo-1"
    When I open the link for "demo-2" in the same profile
    Then I am in room "demo-2" and no longer in room "demo-1"

  Scenario: A killed process does not leave its session directory behind for good
    Given a session directory left behind by a process that was killed
    When the sweep runs
    Then that session directory is gone

  Scenario: The sweep does not take a live room's files
    Given a session directory younger than the sweep's age
    When the sweep runs
    Then that session directory still holds its files

  # Cut by ticket 166: "The unit file ships both layers of the sandbox". It read
  # `deploy/nemo-demo-skin.service`, the unit of the demo_skin app, which was never loaded and went to
  # `archive/demo_skin/` with that app. The phone runs as `nemo-phone.service`.

  Scenario: The facilitator is told one browser holds one room
    Given the note the facilitator reads before the day
    When I read it
    Then it says two rooms means two browsers or a private window
