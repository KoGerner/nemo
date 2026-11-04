Feature: The card must agree with the record
  The referee checks the record against the method. Nothing checks the card against the record.
  ADR-0006 names that failure — "if the card says 'about a working day' and the record says
  MTPD: 8h, those have drifted" — without naming a mechanism for it. This is the mechanism.

  One test settles it, and `docs/voice.md` §4.4 has already written it down: the figure on the
  card must be a string the record holds. That catches both directions at once. "About a working
  day" is unverifiable because it softens a figure; "8 h 15 m" is unverifiable because it invents
  one. Neither is a string the record holds, so neither reaches a human.

  This is a mechanism and not a review. It runs on every card in every walk, before the card is
  rendered, and it fails the walk. A card that cannot be traced is a bug in the card generator,
  reported as such — never a finding, because a finding is something the human resolves and the
  human cannot resolve a card that disagrees with the record behind it.

  What it does not catch, said plainly so nobody assumes otherwise: it compares a card to a
  record, so a record that is wrong about the world passes here. The defence against that is
  ticket 16, not this one.

  Scenario: A figure the record does not hold fails
    Given a record whose MTPD is "24 h"
    When a card says "about a working day"
    Then the card is refused before a human sees it
    And the refusal names "a working day" as the string the record does not hold

  Scenario: A figure the record does hold passes
    Given a record whose MTPD is "24 h"
    When a card says "MTPD 24 h — the operational impact reaches the threshold at 24 h"
    Then the card passes

  Scenario: Invented precision fails like vagueness
    Given a record whose MBCO says "about 60 internal lorries"
    When a card says "60 internal lorries"
    Then the card is refused

  Scenario: The record's own hedge is not the card's hedge
    Given a record whose MBCO says "about 60 internal lorries"
    When a card says "about 60 internal lorries — that 'about' is Henning Barsch's word, not a rounding of mine"
    Then the card passes

  Scenario: A softened severity fails like a softened figure
    Given a record scoring Incident and problem management 4 of 5 on operational at 24 h
    When a card says "Incident and problem management is fairly critical and gets worse the longer it's down"
    Then the card is refused

  Scenario: Ordinary English away from a figure is not vagueness
    Given a record whose MTPD is "24 h"
    When a card says "There's a question about scope I'd like you to settle, and Incident and problem management's MTPD is 24 h"
    Then the card passes

  Scenario: The check runs before the human, not after
    Given any card
    Then it is checked against the record before it is rendered

  Scenario: Every stage's card is checked, not the last one
    Given a walk that reaches all five stages
    When each stage puts a card in front of the manager
    Then every one of the five was checked against the record first
    And no card reached the manager unchecked

  Scenario: A refused card is a bug, not something the manager is asked to sort out
    Given a card whose figures cannot be traced to the record
    When the check refuses it
    Then the failure is reported as a bug in the card generator
    And it does not appear as an open item on the manager's card
    And it does not travel to the sign-off as something the manager accepts

  Scenario: A record that is wrong about the world still passes here
    Given a record whose seven activities are resources and dependencies rather than activities
    And every one of them reads "no MTPD within horizons"
    When a card says "Automated warehouse control has no MTPD within the horizons your method covers"
    Then the card passes, because the card and the record agree
