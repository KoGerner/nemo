Feature: The one door — a walk is answered with words, not a press
  As a BCM manager I answer the card the way I answer anybody: I type what I think. There is one
  box on the screen and it is the only door into my walk. I never hunt for the button that matches
  what I mean, and the walk never stops at stage 3 because nobody built the button for stage 4.

  The owner ruled it on 2026-09-13: "We overpowered the buttons approach; we shifted to having the
  answers as text, like Claude does." That is ADR-0013's substance and this feature is the code
  half of it.

  The blocker it clears is arithmetic, not taste. `demo_skin/app.py`'s `_ANSWER` table has rows for
  stages 1, 2 and 3 and `_actions` indexes it by `card.stage`, so stage 4 raises `KeyError: 4` and
  no manager can reach the card that fires the four views or the graph. The table goes; so do the
  per-stage callbacks behind it and the `on_message` chain in front of it.

  **The typed box has four claimants and the order between them is the thing this feature is most
  careful about.** Second-opinion finding 1, 2026-09-14, which both outside models reached
  independently. `demo_skin/app.py:360-387` arbitrates between three of them today and the card
  answer is the fourth, with no branch at all. In order:

    1. An **interview underway** — a question was put to the manager and what he types is the
       answer to it, not a question of his own.
    2. A **walk waiting for a reservation to be named** — the same reason, one stage up. While a
       naming is awaited the composer belongs to the walk (`docs/voice.md` §4.3).
    3. The **ask lane**, when what he typed is a question rather than an answer. "What does MTPD
       mean?" is a BCM question and `docs/what-good-looks-like.md:201` puts it inside the release
       bar; recorded as an endorsed stage answer it fails ticket 19 on a lane this ticket never
       meant to touch.
    4. The **card the walk is waiting on** — everything else.

  Dropping 1 or 3 is not a simplification, it is a regression, and the scenarios below are written
  so that a replacement rule which drops either goes red.

  **Which way the rough edge leans.** The owner: "this is a demo, we don't have to get it 100%
  correct, the 80/20 principle is totally fine." So telling a caveat from a plain answer may be
  rough, and telling a question from an answer may be rough. Both lean the same way — **never
  record something the manager did not say**. A plain answer misread as a caveat costs him one
  extra question and he waves it off; an answer misread as a question costs him a paragraph of
  guidance and he answers again. Both are recoverable in one turn. Recording an endorsement nobody
  gave, or a reservation nobody made, is not: `docs/voice.md` §4.3 reserves that pressure for
  someone who said nothing.

  **What this feature does not touch.**

  `walk.OVERTAKEN`'s sentence is ticket 29's (second-opinion finding 8, settled 2026-09-14), so
  nothing below asserts its wording — only that the stale answer is refused and that the refusal is
  said in the module's own words, whatever 29 makes them. The guard itself stays here, and stays
  real: it is proven **through the public door**, never at the store, because an implementation
  that reloads the current revision inside `answer()` compares equal every time and a store-level
  test would still pass over the no-op.

  Stage 5 is ticket 18 and the four views and the graph are 16 and 17, so the walk below ends
  where it ends today — the record saved and its receipt bound — and nothing here asserts a
  signature.

  Background:
    Given my company's room is "demo-1"
    And the room holds the process register, the method and one interview for "incident-and-problem-management"

  # The blocker, in the words the ticket put it in.

  Scenario: Stage 4 can be answered at all
    Given I have walked "incident-and-problem-management" to the stage 4 card
    When I answer it in words
    Then my BIA is saved in my room, the four views are written and the receipt binds it
    And nothing on the way there failed on a stage nobody built an answer for
    And nothing here signs anything, because the signature is ticket 18's

  # One door, every stage.

  Scenario: One entry point answers any stage
    Given a card at stage 1, at stage 2, at stage 3 and at stage 4 in turn
    When each is answered with typed words
    Then every one of them is answered through the same entry point
    And the seven per-stage press functions are private behind it

  Scenario: Nothing outside the walk calls a per-stage press function by name
    Given the demo skin, the step bodies and every test in the tree
    When I read what they call to answer a card
    Then it is the one public entry point, in all of them
    And no per-stage press function is named anywhere outside the walk itself

  Scenario: I agree the scope by saying so
    Given the stage 1 card proposing "incident-and-problem-management"
    When I type that the scope is right
    Then the scope is agreed on disk with the answer I gave
    And the walk moves to stage 2

  Scenario: I bind the interview the room already holds by saying so
    Given the stage 2 card offering the interview in my room
    When I type that this is the interview my BIA should rest on
    Then that interview is bound to my BIA with its own bytes beside it
    And the walk moves to stage 3

  # Retired by ticket 164: "With no interview on file I ask for one in words". Holding the
  # interview was the demo skin's deterministic in-room interview (`conduct`), started from its
  # process button; the phone app has neither, and starts an interview through a model turn.
  # Ticket 162 retired the same behaviour's unit tests for the same reason (its rows 26-32).
  # The LIVE behaviour (a real model asks the first question) is covered in qa, in
  # tests/ui/walk/test_stage_2_the_live_interview_path.py sections h and j (16_nemo_check, 2026-09-28).

  Scenario: With the interview's service down I am told plainly the interview could not start
    Given a process my room holds no interview for
    And the service that asks the interview's questions refuses every call
    When I type that we should hold the interview now
    Then I am told plainly the interview could not start, no interview card is offered, nothing is saved

  Scenario: I keep the interview I just held by saying so
    Given an interview held in this room and previewed whole
    When I type my answer to the preview
    Then exactly the previewed bytes are filed and bound in one save

  # What words become — the owner's ruling of 2026-09-13.

  Scenario: A plain answer with nothing held back is endorsed
    Given the stage 3 card
    When I type a plain answer that holds nothing back
    Then the record carries it as endorsed
    And I am not asked to name anything

  Scenario: An answer that carries a caveat makes the walk ask me to name the reservation
    Given the stage 3 card
    When I type an answer that holds something back
    Then the record carries an answer other than endorsed, with the reservation unnamed
    And the card asks me to name it, in plain words, so I know the box is the walk's
    And the stage has moved on anyway, so disagreeing cost me no more than agreeing

  # Cut: "what I type next is the naming, verbatim" — the claimant-2 scenario below keeps the words
  # verbatim, the two-walks scenario attaches them to the right stage's answer, and
  # `features/stage-3-standardise-the-interview-evidence.feature` has the walk stop asking. Bring it
  # back if the naming stops going through `take_naming`.

  Scenario: A reservation I never make is never recorded for me
    Given a plain answer the walk read as a caveat
    When I say there is nothing I want to record
    Then no reservation is left on that stage's answer
    And nothing reaches the signature saying I reserved something

  # Cut: "a reservation nobody names is recorded as unnamed" —
  # `features/stage-3-standardise-the-interview-evidence.feature` measures that already and this
  # ticket reuses the mechanism rather than rebuilding it. Bring it back if the naming stops going
  # through `take_naming`.

  # The four claimants, in order.

  # Retired by ticket 164: "An interview underway takes my words first". The claimant it put
  # first was the demo skin's in-room interview (`CONDUCTING`, `conduct`), which only the demo skin
  # has (ticket 162, rows 26-32). It was also the one scenario that held a live interview on the
  # model lane under `./gate.sh coder`; on the phone every model turn is the scripted lane.

  Scenario: A walk waiting for a naming takes my words before the ask lane does
    Given a walk waiting for me to name a reservation
    When I type words that would read as a BCM question
    Then they are kept as the naming, verbatim
    And no answer from the guidance corpus reaches the page

  Scenario: I can still ask a BCM question while a card is open
    Given the stage 3 card, open and waiting
    When I type "what does MTPD mean?"
    Then it is answered from the frozen guidance corpus, citation and all
    And nothing is recorded as my answer to that card
    And the card is still waiting for me afterwards

  Scenario: Anything else answers the card the walk is waiting on
    Given the stage 4 card, open and waiting
    And no interview underway and no reservation to name
    When I type an ordinary answer
    Then it answers that card

  # Cut: "with no card open my words are a question" — the scenario above reaches the ask lane with
  # a card open, which is the harder case, and `features/the-ask-lane.feature` measures the plain
  # one. Bring it back if the ask lane stops being the fallback.

  # A reservation names the BIA it was made on — defect 1 of the 2026-09-13 code review.

  Scenario: Two walks in one room, and the reservation lands on the right BIA
    Given walks in progress for "incident-and-problem-management" and for "helpdesk-and-support" in the same room
    And I answer "helpdesk-and-support" with something held back
    When I name the reservation
    Then it is attached to "helpdesk-and-support"'s answer
    And "incident-and-problem-management"'s walk carries no reservation at all

  # Cut: "the walk I did not reserve anything on carries no unnamed reservation" — the scenario
  # above already asserts it on the same two walks. Bring it back if that Then is ever dropped.

  Scenario: The naming knows which walk it is for without guessing from the room
    Given two walks in one room, both waiting for a naming
    When I name the reservation on the one I am working through
    Then the other walk is still waiting for its own
    And neither naming was filed against the other's BIA

  # The compare-and-set, proven through the public door.

  Scenario: An answer carrying a revision the room has moved past is refused
    Given the stage 3 card I read, and a write that landed after I read it
    When I answer with the revision that card carried
    Then my answer is not recorded
    And what comes back is that stage's card again, in the walk's own words about being overtaken
    And the answer already on disk is untouched

  # Cut: "the revision travels rather than being read again at the door" — the scenario above is
  # that test: it goes through the public door with a room already moved on, so a door that reloads
  # the revision compares equal, records the answer and goes red. Bring it back if that scenario
  # ever asserts at the store instead.

  # Cut: "the answer I make against a current card is written" — every scenario above writes an
  # answer against a current card. Bring it back if answering ever grows a retry.

  # Cut: "the refusal tells me what to do next" — `walk.OVERTAKEN`'s sentence is ticket 29's and
  # this ticket does not touch the string. Bring it back in 29.

  # What is left of the press protocol, and what is not.

  # Retired by ticket 164: "The card offers me no ways to answer to press". It read the demo
  # skin's stage-card messages. On the phone app the taps nemo draws carry his answers, by ruling
  # (ADR-0023; ticket 161 retired the same read for the same reason, its row 5), so "no answer to
  # press" is a property the phone does not have.

  Scenario: Opening a BIA and choosing between two interviews are still choices, not typing
    Given a room offering three processes and a process with two interviews on file
    When I open a BIA and choose between the interviews
    Then both are still a choice I make from what the room holds
    And neither asks me to type a name

  # The slice, and the movement a resume still owes.

  Scenario: A walk stopped between the record and the receipt still gets its receipt
    Given a walk that saved its record and stopped before the receipt bound
    When it is resumed
    Then the receipt binds the record on disk
    And that second movement is still reachable without calling a private function

  # Cut: "answering stage 4 ends where the slice ends" — folded into the blocker scenario at the
  # top, which answers the same card. Bring it back if that scenario stops asserting the ending.
