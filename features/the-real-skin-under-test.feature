Feature: The real demo skin under test
  `demo_skin/app.py` is the file a manager actually talks to on 10 November. Ticket 05 proved that
  **the guard works** — not that the app that carries it does: the isolation suite still launches a
  stand-in, and the app's own three decisions (the scanned code becoming an identity, the hijack
  rule, the sweep on start) were never exercised.

  Two wiring defects were found by reading and not by a test. The sweep runs blocking inside the
  chat start and raises if the files directory does not exist yet, so the first manager into a fresh
  room is the one who meets it. And the room link arrives as nginx's `$request_uri`, which carries
  the query string, so `?utm=…` on a scanned link lands inside the room code. A room code decides
  storage, which makes the second one a silent wrong-room write, not a cosmetic bug.

  The room door's own properties are in `the-room-door.feature` and are not restated here. What is
  new is that they are now measured against the real app, and that the app's wiring around them is
  measured at all.

  Cut, and when to bring it back:
  - "Another room cannot take my session over mid-walk": the-room-door.feature already has "I
    cannot join another room's socket" with "the occupant is not evicted", and that is isolation
    assertion 4 — which this ticket re-points at the real app, so it now measures `admit` and
    `OCCUPANTS` themselves. Bring it back if that assertion turns out to pass with the `admit`
    line removed, i.e. if Chainlit's own refusal is what it was reading all along.
  - "The seven assertions are still seven": no test can see that an assertion got easier to pass;
    a reader can. It is `git diff origin/main -- tests/isolation/` and QA step 25. Bring it back
    when the count is a property of something other than the diff under review.
  - "The demo skin is inside the gates that can reach it": `gate.sh` is proven by running it
    against a broken skin (QA step 30), not by a scenario that reads it. Bring it back if a gate
    ever goes green on a file it silently stopped reaching.

  Scenario: A scanned link with tracking on the end still lands in my own room
    # `identity_from_link` strips the query before taking the last segment: stdlib, one line —
    # `urllib.parse.urlsplit(link).path`, or `link.partition("?")[0]`.
    Given room "demo-1" holds files
    When I open the link for "demo-1" with "?x=1" on the end
    Then I am in room "demo-1" without being asked for an account or a password
    And the demo skin holds "demo-1" as my identity
    And what I write lands in the room folder for "demo-1"
    And no room folder named "demo-1?x=1" is created

  Scenario: A link that carries no room code opens no room
    When I open a link that carries no room code
    Then I am admitted to no room at all
    And the demo skin holds no identity for me

  # Ticket 164: every scenario here now runs on the phone app, `skin/PROTOTYPE_conversation_app.py`,
  # over `skin_harness.py` and its scripted lane. On the phone a room is `<room>-<model>` per model,
  # so "the room folder for demo-1" is the folder the phone keeps for the identity `demo-1`.

  Scenario: The first manager into a fresh room is greeted, not met with an error
    # Ticket 164: re-aimed. The phone mints the room on the first scan and greets it; the old
    # half about `sweep` and the `.files` directory is retired, because the phone does no sweep.
    Given a fresh room whose files directory does not exist yet
    When I am the first to open its link
    Then I am greeted with what the room holds
    And no error about a missing directory reaches the page

  # Retired by ticket 164: "The sweep does not keep a room waiting". It measured the demo skin's
  # `cl.make_async(sweep)` in its chat start; the phone app does no sweep at all, so there is no
  # greeting for a sweep to hold up. `nemo.door.sweep` itself is still pinned by the two sweep
  # scenarios of `the-room-door.feature` and by `src/nemo/test_door.py`.

  Scenario: The isolation suite attacks the app the manager talks to
    Given the isolation suite
    When I read what it launches
    Then it launches "skin/PROTOTYPE_conversation_app.py" and nothing else
    And no stand-in app is launched in its place
    And it runs on the scratch Chainlit interpreter
    And Chainlit is not a dependency of nemo
