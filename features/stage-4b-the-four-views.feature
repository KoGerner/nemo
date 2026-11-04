Feature: Stage 4b — the four views, rendered from the record bytes
  As a BCM manager I get four documents I can hand to somebody: what we agreed was in scope, what
  the interview said, what the analysis found, and the worksheet my auditor will ask for. I never
  wrote any of them. They are the record, read out loud, so they cannot say one thing while the
  BIA on file says another — and if I change the record, they change with it.

  The story's own three scenarios come first, in the words it asked them in. The ones after them
  are the rest of its "Done when", each written as something the manager, the operator or the next
  stage can watch happen.

  In v1 the closed package for one room held MTPD `24 h` in the record, `8 h` in the handover and
  `0–4 hours` in the worksheet, with owner validation pending, and nothing compared them. The fix
  this ticket asks for is not a comparison. It is that there is only one place a figure can come
  from, so the three cannot be written apart in the first place. Every scenario below that looks
  like a comparison is really a check that the single source held.

  This ticket is the second of stage 4's three movements and owns exactly one of them: the four
  views under `output/<process>/`. The record beside them (`bia-record.json`) is ticket 15 and the
  graph with its receipt is ticket 17, so nothing here may assert a graph page, an `evidence.json`
  or a bound receipt — the run still stops at "saved, and not yet finished" (`docs/adr/0010`).

  Two limits, stated so nobody assumes them away.

  `features/the-card-must-agree-with-the-record.feature` says its defence against a record that is
  wrong about the world is "ticket 16, where activities come from the register and an unmodelled
  dependency is a finding rather than an invented id". Half of that landed here and half did not.
  Rendering is a pure function of the record bytes, so a view cannot go to the register to check an
  id — what it can do, and does below, is never print an id the record does not hold. Where an
  activity comes from is the record builder's question, not the renderer's, and it stays with the
  builder.

  And the worksheet is asked for facts the record may not carry yet: the RTO and the RPO **per data
  set**, and the **minimum resources over time with the workaround per resource**. If the record
  does not hold them, that is a bug in the record and the repair belongs in the stage that writes
  it. The renderer's half of the contract is below: it never reaches outside the record to fill a
  gap, and it never leaves one silent.

  Background:
    Given my company's room is "demo-1"
    And I walked to stage 4 and accepted the record

  # The story's three, in the words it asked them in.

  Scenario: The views come from the record
    Given a saved record
    When the four views are rendered
    Then every figure in them is a string the record holds

  Scenario: A changed record changes the views
    Given the four views have been rendered
    When the record changes and they are rendered again
    Then they change with it

  Scenario: The views cannot disagree
    Given any saved record
    Then the worksheet, the capture, the analysis and the scope guide agree on MTPD, RTO, RPO, MBCO, resources and open items

  # Where the four land, and when.

  Scenario: The four views land under the process I walked
    Given I accepted the record for the process "incident-and-problem-management"
    When I look at what my room holds
    Then "output/incident-and-problem-management/" holds "stage1-scope-and-guide.md", "stage2-interview-capture.md", "stage3-dependency-analysis.md" and "stage4-worksheet.md"
    And no view was written anywhere else in my room

  # Cut: "another process's views are not disturbed" — the four land under `output/<process>/`, so
  # the filesystem holds them apart; add it back if a view is ever written outside that directory.
  # Cut: "nothing is rendered until I have answered" — stage 4a's "Nothing lands without the human"
  # measures it; add it back if rendering ever gets a trigger of its own.
  # Cut: "the views do not finish the walk" — stage 4a's "Saved is not finished" is the same Then;
  # add it back if rendering ever reports walk state itself.

  # What the worksheet carries, per activity.

  Scenario: The worksheet shows the impact grid across the horizons
    Given a saved record with an impact grid
    When I read the worksheet
    Then each activity's grid is there across every horizon the method covers
    And no horizon is dropped because nothing was scored in it

  Scenario: The worksheet says the MTPD with the reason before the figure
    Given an MTPD derived from the grid
    When I read the worksheet
    Then it says why before it says the number

  Scenario: An MTPD nobody derived is not printed on the worksheet either
    Given the grid never reaches the threshold within the horizons
    When I read the worksheet
    Then it says so in the manager's words
    And no MTPD figure is shown for that activity

  Scenario: The worksheet gives the RTO and the RPO per data set
    Given a record whose activity names more than one data set
    When I read the worksheet
    Then the RTO and the RPO are shown for each data set by name
    And one data set's figure is never shown as though it covered them all

  Scenario: The worksheet states the MBCO in the words the record holds
    Given a saved record
    When I read the worksheet
    Then the MBCO is there, character for character as the record has it

  Scenario: The worksheet shows the minimum resources over time with the workaround per resource
    Given a record that names the minimum resources over time
    When I read the worksheet
    Then each resource is there with what is needed by when
    And each one carries the workaround for doing without it

  Scenario: The worksheet names dependencies by their register ids
    Given a record whose activity depends on register entries
    When I read the worksheet
    Then each dependency is named by the register id the record holds
    And no id appears that the record does not hold

  Scenario: Every scored category is quoted beside its score with its file
    Given a saved record
    When I read the worksheet
    Then each scored category shows the exact quote the score rests on
    And the file that quote came from is beside it

  # Rendering is a pure function of the record bytes.

  # Cut: "the same record renders the same bytes twice" — the scenario below re-renders and compares
  # bytes too; add it back only if that one ever stops comparing byte for byte.

  Scenario: Nothing but the record is read to render a view
    Given the four views have been rendered
    When the transcripts, the dependency register and the method file are taken out of my room
    And the four views are rendered again
    Then they are byte for byte what they were

  Scenario: A fact the record does not hold is never filled in from somewhere else
    Given a record that says nothing about the minimum resources
    When I read the worksheet
    Then it says that was not established
    And no resource appears that the record does not name

  # Cut: "a gap is an open item worded the same way in every view" — "the views cannot disagree"
  # already covers open items; add it back if the views ever stop being rendered from one function.

  # Cut: "the four views cannot hold three different MTPDs" — the v1 defect this ticket exists to
  # close is the story's third scenario above, said generally; add it back only if the views are
  # ever rendered by more than one function.

  # Overwriting a contract-path document with a fraction of its bytes.

  Scenario: A view that would shrink to a fraction of its saved size is not overwritten
    Given "output/incident-and-problem-management/stage2-interview-capture.md" holds 10514 bytes
    When something tries to overwrite it with 2099 bytes
    Then the write is refused
    And the refusal names the document and both byte counts, so a human decides whether the record lost something

  Scenario: Keeping the headings does not buy the shrink
    Given a saved view and a replacement carrying exactly the same "##" headings
    When the replacement is a fraction of the saved size
    Then it is refused just the same
    And the refusal is about the bytes, not about the headings

  Scenario: The same refusal guards all four views, not only the capture
    Given each of the four views has been saved
    When each in turn is offered a replacement a fraction of its size
    Then every one of the four is refused

  Scenario: A refused overwrite leaves the saved document alone
    Given a saved view
    When an overwrite is refused for shrinking it
    Then the bytes on disk are the ones that were there before
    And the refusal is reported rather than swallowed

  Scenario: A view that grows or barely moves is written
    Given a saved view
    When a re-render is the same size or larger
    Then it is written without argument

  Scenario: The first write of a view has nothing to shrink from
    Given my room holds no view for this process yet
    When the four views are rendered
    Then all four are written

  # Cut: "a record that honestly shrank is still not overwritten quietly" — the same refusal as the
  # first scenario above, which now names the document; add it back if a record-shrink path bypasses it.

  # Five activities, one card.

  Scenario: The four views render for a department with five activities
    Given my department has five activities in scope
    When I accept the record
    Then all four views are written
    And every one of the five is in the worksheet in full

  # Cut: "five activities do not split the stage 4 card" — stage 4a's "A department with five
  # activities still gets one stage 4 card" measures the owner's ruling; add it back if the card moves here.

  # Cut: "record what five activities do to each view's length on a phone screen" — it is a
  # measurement a reader takes, not a behaviour, and there is no threshold to assert against. QA
  # section H takes it and writes the numbers down for the owner.
