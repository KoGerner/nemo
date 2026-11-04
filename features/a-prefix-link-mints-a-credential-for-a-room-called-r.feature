Feature: A prefix link mints a credential for a room called `r`
  `X-Room-Link: /demo/r/` — the room-link prefix with nothing after it — is answered 200 today and
  mints a real `access_token` for a room called `r`. That is the link a scan of a damaged or
  half-printed QR actually produces, and ADR-0003 makes the link the whole credential. No data is
  exposed, because `/srv/addendum/demo-rooms/r` does not exist and so the room has no folder to read
  or write; the defect is that the door mints a credential at all. A door that mints a token for a
  room that does not exist is a door that has stopped checking.

  Third in one family. Ticket 20 fixed the other two — `sweep()` blocking inside the chat start, and
  nginx's `$request_uri` putting a query string inside the room code. This one survived because the
  fix asked what the remainder of the path is and never whether there is a remainder at all.

  Two rules, at two severities, and they are not the same rule:

  - **The link refuses an empty remainder.** A malformed credential can be judged without touching
    the disk, which is what keeps `nemo.door` pure and lets `identity_from_link` stay a property
    test. It cannot catch a well-formed code for a room that was never minted.
  - **The door refuses a room with no folder**, with a separate refusal in its own words. This
    catches both, and it makes admission depend on the disk: a mount that is slow or briefly absent
    starts refusing valid rooms. That is an accepted cost, and it is why the two refusals must stay
    distinguishable — an operator has to be able to tell a damaged scan from an absent mount without
    guessing.

  `the-room-door.feature` owns isolation and is not restated here. `the-real-skin-under-test.feature`
  owns the query string and the sweep.

  Cut, and when to bring it back:
  - "A room code with a path separator in it cannot escape its folder": `the-room-door.feature`
    already refuses `../../scratch` at the session identifier, and `ROOMS / room` keeps a room code
    to one segment. What this ticket adds about encoding is below, as one scenario about what reaches
    the filesystem. Bring the wider version back if a room code is ever joined to anything but
    `ROOMS`.
  - "The strict xfail at step 7 goes green": a suite saying so is a fact about the suite, not
    something a manager can observe. It is QA step 1, where a human reads the run.
  - The two single-shape scenarios for "/demo/r/" and "/demo/r": rows of the outline below, which
    asserts the same three things. Bring one back if a shape ever needs its own Given.
  - "My link with the code still on it opens my room": the same steps already run as the first
    scenario of `the-room-door.feature`. Bring it back here if that one moves; the human control
    stays as QA section C.

  Scenario Outline: No damaged shape of the link mints a credential
    # Ticket 20 proved the query-string fix with a property over query, fragment, trailing slash and
    # appended text. Hold this to the same standard: every shape of the prefix with no remainder,
    # not the two above.
    Given the rooms folder holds "demo-1" and "demo-2"
    When a scan presents the link "<link>"
    Then I am refused
    And no access token is minted for me
    And no room folder named "r" is created

    Examples:
      | link            |
      | /demo/r/        |
      | /demo/r         |
      | /demo/r//       |
      | /demo/r/?x=1    |
      | /demo/r/#top    |
      | /demo/r?utm=qr  |
      |                 |

  Scenario: A well-formed code for a room nobody minted is refused
    Given the rooms folder holds "demo-1" and "demo-2"
    When I open the link for "demo-9", which has no folder
    Then I am refused
    And no access token is minted for me
    And no room folder named "demo-9" is created

  Scenario: An operator can tell a damaged scan from an absent mount
    Given the rooms folder holds "demo-1" and "demo-2"
    When a scan presents the room link prefix "/demo/r/" with nothing after it
    And I open the link for "demo-9", which has no folder
    Then the operator's log carries one sentence about a link that carries no room code
    And a different sentence about a room that has no folder
    And neither refusal is worded as the other

  Scenario: An absent rooms mount reads as an absent mount, not as a damaged code
    Given the rooms folder is not there at all
    When I open the link for "demo-1"
    Then I am refused
    And the operator's log says the room has no folder
    And it does not say my link carries no room code

  Scenario: An encoded separator in the code never reaches the filesystem
    # Ticket 20 found percent-encoding passed through undecoded and safe, and untested. Decided
    # here rather than inherited, and the decision is written where the code makes it.
    Given the rooms folder holds "demo-1" and "demo-2"
    When a scan presents a room code with an encoded separator in it
    Then I am refused
    And nothing outside the rooms folder is read or written
    And the rooms folder still holds exactly "demo-1" and "demo-2"

  Scenario: A refused manager reads a sentence, not a fault
    Given the rooms folder holds "demo-1" and "demo-2"
    When a scan presents the room link prefix "/demo/r/" with nothing after it
    Then what I read carries no stack trace
    And it carries no room code, path or field name
