Feature: A scan mints a room from the seed
  Fifty delegates scan, and each one works on their own copy of the marschkamp files. Ticket 22
  mints a *credential* for a room; minting the room's **contents** is what does not exist, so today
  fifty scans arrive at fifty names with nothing behind them. On first arrival at a room that has no
  folder, the seed is copied into it, once, and the walk proceeds as it already does. That is the
  whole story (ADR-0017).

  The seed is `marschkamp`: `01_Organisation` through `09_Evaluation`, plus `output/`. **A minted
  room ships a BIA in progress on purpose** (ADR-0011) — deleting that pre-loaded record breaks the
  product rather than making it safer, and the defence against closing over work nobody did is
  ticket 15's run binding on `run_id`, not an empty room.

  **This supersedes one rule of ticket 22, and the coder must carry that through.**
  `a-prefix-link-mints-a-credential-for-a-room-called-r.feature` has "A well-formed code for a room
  nobody minted is refused". On ADR-0017's authority that is no longer the behaviour: a well-formed
  code for a room nobody minted is now the ordinary case — it mints. Two of ticket 22's three
  defences are untouched and are restated below as scenarios, because they are what stops this
  ticket turning the door into a folder generator:

  - **A link carrying no room code is still refused, without touching the disk.** That is
    `identity_from_link`, and it stays the defence against a damaged or half-printed QR.
  - **An absent rooms folder is still an absent mount.** Minting creates a room *inside* the rooms
    folder and never creates the rooms folder itself, so a mount that is away refuses instead of
    handing fifty delegates fifty brand-new rooms and losing the ones they had. The operator's two
    sentences must stay distinguishable, and a mint is now a third thing the log says.

  **Minting is idempotent and it is a race.** Fifty phones scan within a minute of each other and a
  delegate who reloads must not get a second room or a half-copied one. The scenarios below say what
  is observable — exactly one room, complete at the instant it appears, never partial to a watcher —
  and leave the coder the choice between copying to a temporary path and moving it into place, or
  holding a lock. Whichever is chosen must be **written down where the choice is made**; QA section A
  reads it, and the "never partial" scenario is what proves it rather than the docstring.

  **Admission stays.** Ticket 02's check runs at mint, not only at refresh: a room that would fail
  the walk's own gates must not be handed to a delegate. It is better to refuse a scan than to seat
  somebody in front of a BIA that cannot reach stage 5.

  `the-room-door.feature` owns isolation, and ticket 30's gate is what proves it; only the one thing
  this ticket changes about it — that a room minted a second ago is no more readable than one that
  existed all along — is restated here.

  Cut, and when to bring it back:
  - "The card is headed Stage 1 of 5 · Scope", per process, and the whole of what
    a Stage 1 card says: `the-walking-skeleton.feature` owns the card. What this ticket adds is only
    that the card is reached **from a room nobody set up**, which is one scenario below.
  - "A crafted session identifier cannot write outside the room": `the-room-door.feature` owns the
    connect payload. Minting joins the room code to the rooms folder and to nothing else, and the
    one scenario below covers the new risk, which is that minting *creates* where reading only read.
  - "Every shape of a damaged link is refused": ticket 22 proved that with an outline over seven
    shapes and a property test. One shape is kept here as a regression guard on the mint path; bring
    the outline back only if minting ever reads the link itself rather than the code taken from it.
  - "The seed passes every gate the walk applies": that is ticket 02's, and G4(a). Here it appears
    only as what happens to a *scan* when it does not.
  - "A room is never visible half-copied", with a watcher: a green watcher proves only that it did
    not look at the wrong microsecond. The whole-or-nothing claim is measured by the two scenarios
    below and by QA step 14's check for a leftover staging folder. Bring it back if the coder ever
    copies into the room's own path rather than moving a finished one into place.
  - "A broken seed seats nobody at all", fifty times: admission runs per mint and is deterministic,
    so it is the refusal scenario below with a loop around it. QA step 29 runs that loop by hand.
    Bring it back if admission is ever cached, sampled or made per-room.
  - "The operator can count the rooms in the log": nothing in the ticket asks for it, and the count
    is already the deliverable of the fifty-codes scenario. QA step 37 reads the log by hand. Bring
    it back when a ticket makes the operator's console a product surface (51, 52).

  Background:
    Given the rooms folder is there
    And the seed holds "01_Organisation" through "09_Evaluation" and "output/"

  Scenario: My scan gives me a room with my company's files already in it
    Given the rooms folder holds no room called "adler-7ycyet"
    When I scan the code for "adler-7ycyet"
    Then I am in room "adler-7ycyet"
    And it holds every folder the seed holds, "01_Organisation" through "09_Evaluation"
    And what is in them is what is in the seed, file for file

  # ADR-0011: a minted room ships a BIA in progress on purpose. Terminal-eligibility is the test,
  # never emptiness — a room that holds nothing has to interrogate the manager, and the bar is
  # three typed inputs. Cite the ADR in the test that pins this.
  Scenario: A freshly minted room ships a BIA in progress, deliberately
    Given the rooms folder holds no room called "adler-7ycyet"
    When I scan the code for "adler-7ycyet"
    Then the room holds "output/"
    And it holds a BIA already in progress
    And it holds nothing a signature could close over

  Scenario: The walk reaches a Stage 1 card from a room nobody set up
    Given the rooms folder holds no room called "adler-7ycyet"
    When I scan the code for "adler-7ycyet" and open the BIA for "Incident and problem management"
    Then I read a Stage 1 card for "Incident and problem management"
    And nothing was set up between my scan and that card

  Scenario: A second scan lands me back in the room I already have
    Given I scanned the code for "adler-7ycyet" and agreed the scope for "Incident and problem management"
    When I scan the same code again
    Then I am in the same room, with the same files
    And my agreed scope for "Incident and problem management" is still there
    And I am not asked to agree it a second time
    And no second room was made

  Scenario: Two scans of one code at the same moment make one whole room
    Given the rooms folder holds no room called "adler-7ycyet"
    When the code for "adler-7ycyet" is scanned twice at the same moment
    Then exactly one room called "adler-7ycyet" exists
    And it holds every folder the seed holds
    And neither scan was refused

  Scenario: Fifty codes in a tight loop give fifty whole rooms
    Given the rooms folder holds no rooms
    When fifty different codes are scanned within a minute of each other
    Then there are exactly fifty rooms
    And every one of them holds the whole seed
    And not one of them is partial
    And the run says how many rooms it made and how long it took

  Scenario: My answers land in my own copy and never in the seed
    Given I scanned the code for "adler-7ycyet"
    And another delegate scanned the code for "buche-2kd91p"
    When I agree the scope for "Incident and problem management"
    Then my decision is on file in my own room
    And the seed is exactly as it was

  Scenario: A room minted a second ago is no more readable than one that was always there
    Given a room "buche-2kd91p" that has been there all along
    When I scan the code for "adler-7ycyet" and request a file belonging to "buche-2kd91p"
    Then I am refused with 401
    And a delegate in "buche-2kd91p" requesting a file of mine is refused the same way

  Scenario: A seed that would fail the walk's gates refuses the scan
    Given a seed whose Stage 2 capture is missing the sections the walk's gates require
    When I scan the code for "adler-7ycyet"
    Then I am refused
    And what I read is one sentence I can understand
    And it carries no file path, no field name and no stack trace
    And no room called "adler-7ycyet" was made

  Scenario: An absent rooms folder is an absent mount, not fifty new rooms
    Given the rooms folder is not there at all
    When I scan the code for "adler-7ycyet"
    Then I am refused
    And the rooms folder was not created
    And the operator's log says the rooms folder is not there
    And it does not say my link carries no room code

  Scenario: A link that carries no room code mints nothing
    When a scan presents the room link prefix "/demo/r/" with nothing after it
    Then I am refused
    And no room folder named "r" is created
    And the operator's log says the link carries no room code

  Scenario: A crafted code cannot mint a room outside the rooms folder
    Given the rooms folder holds no rooms
    When a scan presents a room code with an encoded separator in it
    Then I am refused
    And nothing was created outside the rooms folder
    And the rooms folder still holds no rooms
