Feature: Stage 5 — consolidate, hand over, and sign
  As a BCM manager I reach the end of my BIA: what we found is put in front of me as requirements to
  hand to whoever designs the continuity solutions, I accept it, and then I sign it with my name and
  my role. The signature is the one moment in the whole walk where anybody asks who I am. Nothing
  here drafts a plan for me — the method hands over the figures and the decisions behind them and
  stops, deliberately.

  The story's own five scenarios come first, in the words it asked them in. The ones after them are
  the rest of its "Done when", each written as something the manager, the operator or the reader of
  the three documents can watch happen.

  Who the handover is written for was asked of the frozen corpus rather than assumed (owner's
  ruling, 2026-09-13): the next activity in the lifecycle is **solutions design**, so the reader is
  a BCM manager about to design continuity solutions and what they get is MTPD, RTO, RPO, MBCO,
  minimum resources, dependencies, and the reservation attached to any answer that was not
  *endorsed*. The corpus states its own gap — it holds no step-by-step method for solutions design —
  so the document hands over inputs and never instructs the reader how to do the next stage.

  Two v1 defects this ticket exists to close, both of them numbers rather than opinions. A sign-off
  whose signer's role read "explicitly not the process owner" validated cleanly, because nothing
  checked who signed. And a certificate can only ever say **identity asserted in session, not
  verified** here, because nothing anywhere in this product captures an email — the branch that
  would say anything stronger is a flag nothing sets, and writing one would be writing a claim no
  code can make true (corrected 2026-09-14; `docs/stage-model.md:189` settled on 2026-09-12 that the
  third typed slot is one free-text amendment and not an email address at the door).

  Stage 5 is the last stage. The missing-owner loop is a finding carried here and accepted by id;
  it is not a sixth stage, and nothing below may read like one.

  Background:
    Given my company's room is "demo-1"
    And I walked to stage 4 and accepted the record the server refereed

  # The story's five, in the words it asked them in.

  Scenario: Stage 5 cannot start without the receipt
    Given a record saved with no graph receipt
    When I try to reach stage 5
    Then I cannot, and the walk says it is not finished

  Scenario: The handover is rendered from the record
    Given a record and its receipt
    Then the management BIA and the requirements handover are rendered from the record bytes
    And every reservation and contradiction from every earlier gradient answer is carried onto them

  Scenario: Accepting is not signing
    Given I have accepted the handover
    Then the walk is `reviewed_pending_owner`
    And no certificate has been written

  Scenario: A generic confirmation never becomes a signature
    Given a chat message saying "yes"
    Then no named person's signature is recorded

  Scenario: The certificate does not overclaim
    Given I signed, and nothing anywhere captured an email
    Then the certificate reads "identity asserted in session, not verified", in those words

  # Cut: "the receipt has to be for this record" and "re-drawing the picture does not shut the gate" —
  # both are already asserted against stage 5 by ticket 17
  # (`stage-4c-the-graph-and-its-receipt.feature`, "The receipt binds the record, not the page" and
  # "A receipt is not a receipt for some other record"); add them back here if the stage-5 gate ever
  # reads anything but that receipt.

  # What the handover says on its face.

  Scenario: The handover is labelled for solution-design discussion, and not approved
    Given a record and its receipt
    When I read the requirements handover
    Then it says on its face that it is a requirements handover for solution-design discussion
    And it says it is not approved

  Scenario: The handover names the reader it is written for
    Given a record and its receipt
    When I read the requirements handover
    Then it is addressed to whoever designs the continuity solutions next

  Scenario: The handover hands over inputs and never teaches the next stage
    Given a record and its receipt
    When I read the requirements handover
    Then it tells the reader nothing about how to design a continuity solution

  # What it carries, item by item, out of the record.

  Scenario: The continuity requirements are carried per prioritised activity
    Given a record whose department has more than one prioritised activity
    When I read the requirements handover
    Then every one of them carries its own MTPD, recovery target, recovery point, MBCO, minimum resources and dependencies

  Scenario: The risk-assessment referrals are carried
    Given a record that refers something to the risk assessment
    When I read the requirements handover
    Then the referral is there, said as what it refers and to whom

  Scenario: The missing evidence is carried rather than tidied away
    Given a record whose activity has evidence missing
    When I read the requirements handover
    Then it says what is missing
    And no figure is shown in the gap's place

  Scenario: The sanity-check findings are carried
    Given a record the referee raised findings on
    When I read the requirements handover
    Then every finding is there, in the words the referee raised it in

  Scenario: The decision boundary is carried
    Given a record and its receipt
    When I read the requirements handover
    Then it says where the BIA stops and what the reader decides after it

  # Every earlier gradient answer, carried forward.

  Scenario: A reservation named at stage 3 reaches the handover word for word
    Given I answered stage 3 with "endorsed with reservations" and typed what I was reserving
    When I read the requirements handover
    Then my words are there exactly as I typed them, against the card I typed them on

  Scenario: A reservation nobody named is carried as unnamed, not as agreement
    Given I answered a card with something other than "endorsed" and typed nothing after it
    When I read the requirements handover
    Then it says a reservation was recorded and never named
    And that answer is not shown as an endorsement

  Scenario: A contradiction between two owners reaches the handover
    Given a record carrying a contradiction between what the interview said and what the register holds
    When I read the requirements handover
    Then both sides of it are there, and neither has been settled on my behalf

  # Cut: "the management BIA carries the same reservations as the handover" — both are rendered from
  # one record by one function and the story's second scenario asserts the carrying; add it back if
  # the two documents are ever rendered apart.

  # Accepting, and then signing.

  Scenario: Accepting the handover costs one gradient answer
    Given a record and its receipt
    When I accept the handover
    Then that is one answer and nothing else was demanded of me

  Scenario: Signing asks for a name and a role, and accepts every open item it lists
    Given I have accepted the handover
    When I am asked to sign
    Then it asks for my name and my role, and says signing accepts every open item listed

  Scenario: The signature is two typed replies, and the walk costs at most seven
    Given a clean run where the server proposed right every time
    When I reach the end of it
    Then the name and the role are the only two things I typed at the signature
    And the whole walk cost no more than seven typed replies

  Scenario: A dependency with no owner is accepted here by its id
    Given a record carrying a dependency with no owner
    When I sign
    Then I accept that finding by its id, at this signature
    And no further stage is opened to chase the owner

  # Authority: who is allowed to sign this.

  Scenario: A signature by the activity's owner closes the run
    Given I have accepted the handover and I am the owner of the activity
    When I sign with my name and my role
    Then the walk is `closed`
    And the certificate is written

  Scenario: A signature by somebody who is not the owner does not close the run
    Given I have accepted the handover and I am not the owner of the activity
    When I sign with my name and my role
    Then it is either refused or recorded as sponsor acceptance
    And the walk is still `reviewed_pending_owner`

  Scenario: v1's signer who says outright they are not the process owner
    Given a signer whose role reads "explicitly not the process owner"
    When they sign
    Then the walk is still `reviewed_pending_owner`
    And nothing anywhere calls that sign-off valid

  # Cut: "a sponsor acceptance is still carried on the certificate" — no certificate exists while the
  # walk is `reviewed_pending_owner`, which the scenario above asserts; add it back if a sponsor
  # acceptance ever gets a document of its own.

  # The three documents on disk.

  Scenario: The three documents land under the process I walked
    Given I signed with authority for the process "incident-and-problem-management"
    When I look at what my room holds
    Then "output/incident-and-problem-management/" holds "bia-draft.md", "requirements-handover.md" and "owner-signoff-certificate.md"

  Scenario: The three documents are a function of the record bytes
    Given the three documents have been written
    When the transcripts, the dependency register and the method file are taken out of my room
    And they are rendered again from the same record
    Then they are byte for byte what they were

  Scenario: No document says "room"
    Given the three documents have been written
    Then not one of them uses the word "room"

  # The certificate.

  Scenario: The certificate says who signed, in what role, and what they accepted
    Given I signed with authority
    When I read the certificate
    Then it carries my name, my role, and the id of every open item I accepted

  Scenario: The certificate never claims an identity was verified
    Given I signed with authority
    When I read the certificate
    Then it never says an identity was confirmed, checked or verified by anything

  # Cut: "the certificate reads 'identity confirmed by email' where an email was given" — nothing in
  # this product captures an email and no ticket owns capturing one, so the branch is a flag nothing
  # sets; add it back when a ticket names where a door-supplied email lands.

  # Where the method stops.

  Scenario: The tool never chooses a recovery solution
    Given a record and its receipt
    When I read all three documents
    Then not one of them picks a site, a supplier, a system or a way of recovering

  Scenario: The tool never accepts a risk on my behalf
    Given a record carrying an open risk
    When I read all three documents
    Then the risk is stated and left open for a human to accept

  Scenario: The tool never drafts a continuity plan
    Given a record and its receipt
    When I read all three documents
    Then there is no plan in any of them, and the handover says the BIA stops here
