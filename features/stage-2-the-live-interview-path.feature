Feature: Stage 2 — the live interview path
  As a BCM manager I reach stage 2 for a process my room holds no interview for, and instead of
  being sent away to find a file I am interviewed here and now. I read back the whole
  question-and-answer in my own words before anything is kept, and the same gradient that would
  have bound a transcript already in the room binds this one.

  The story's own four scenarios come first, in its words. The ones after them are the rest of its
  "Done when", each written as something the manager, the operator or the next stage can watch
  happen.

  Two things bind this file and are written into it as scenarios rather than left as prose. **A
  live interview is a longer path, not a more expensive gate** (`docs/stage-model.md` Stage 2): the
  preview confirmation folds into the same stage 2 decision, so there is a scenario proving the
  second card is absent, because an absence nobody tests comes back. And **the model conducts, it
  does not conclude** (ADR-0007, ADR-0008): this is the demo skin's second model job and, like the
  first, it never writes a record and never puts a figure in the manager's mouth.

  This is also the one stage where typing is the method working rather than the budget breaking.
  The clean run is ticket 12's — a transcript already in the room, zero typed inputs. Here the
  manager answers questions, so the scenarios below fix what the box is for while an interview is
  running and what it goes back to being afterwards.

  Background:
    Given my company's room is "demo-1"
    And I have agreed the scope for "IT event management"
    And my room holds no interview for "IT event management" in either of its homes

  # The story's four, in the words it asked them in.

  Scenario: The interview is conducted and shown before it is kept
    Given my room holds no transcript for this process
    When I answer the interview in the room
    Then I am shown the verbatim question-and-answer with its fingerprint
    And nothing is on disk until I answer the gradient

  Scenario: What is kept is what I saw
    Given I have answered the gradient on the preview
    Then the transcript on disk is byte-identical to the preview
    And it is bound to this walk

  Scenario: The interview cannot write a record
    Given a live interview of any length
    Then no record is written and no figure is asserted by the model

  Scenario: The cap stops the interview legibly
    Given the OpenRouter key cap has been reached mid-interview
    Then I am told plainly, and what was already captured is not lost

  # Where the evidence lands, and what makes it evidence.

  Scenario: The interview is filed where the referee will hunt quotes
    Given I have answered the gradient on the preview
    When the operator looks in my room
    Then the transcript is at "output/owner-interviews/<process>-interview-transcript.md"
    And it holds the questions and my answers as they were asked and given

  Scenario: The fingerprint on the preview is the fingerprint of the file
    Given I am shown the preview of the interview I just answered
    When I keep it and the operator digests the saved file
    Then the digest is the fingerprint the preview carried
    And the walk records that same fingerprint against this interview

  # Cut: "an interview held in the room is offered again like any transcript" — once it is a file in
  # `output/owner-interviews/`, ticket 12 walks both homes. Add it back if this path ever files
  # somewhere ticket 12 does not read.

  # Cut: "the only new files are the transcript and the binding" — the story's third scenario is the
  # one that says no record is written. Add it back if a stage-2 capture document is ever proposed.

  # The fold: one decision, not two.

  Scenario: Keeping the interview is the stage 2 decision itself
    Given I am shown the preview of the interview I just answered
    When I answer it with one of the four labels
    Then stage 2 is answered and the interview is bound
    And I am not asked to confirm the transcript and then answer a second card

  # Cut: "an interview I never kept leaves nothing behind" — the story's first scenario already
  # says nothing is on disk until the gradient is answered, and abandoning is that same assertion
  # from the other end. Section F of the QA procedure still walks it by hand. Add it back if
  # anything is ever written before the gradient.

  # The model conducts; it does not conclude.

  Scenario: The interview asks for the reason and never supplies the figure
    Given the interview reaches what an outage of this process would cost
    When I read what it says to me
    Then it asks me and waits
    And no MTPD, RTO, RPO or MBCO is stated back to me as though I had said it

  # Cut: "the transcript holds my words and no conclusion drawn from them" — the saved bytes are the
  # preview's bytes ("What is kept is what I saw"), so what the preview may not carry the file
  # cannot either. Add it back if the save ever stops being byte-identical.

  # Cut: "stage 3 reads those figures out of the transcript, and only where the transcript states
  # them" — that is ticket 14's card and its feature file already walks it from both ends. What is
  # this ticket's is only that the transcript gives stage 3 nothing pre-concluded to read.

  # The box, while an interview is running and after it.

  Scenario: What I type during the interview is my answer
    Given the interview has asked me a question
    When I type my answer
    Then it is taken as my answer to that question
    And the guidance is not searched, and I am not answered as though I had asked a question

  # Cut: "once the interview is kept the box is mine again" — that is ticket 11's ask lane owning the
  # box, which its own feature walks. Add it back if keeping an interview ever leaves state behind.

  # Cut: the cap's two halves, "it does not cost me the answers I already gave" and "it is told as a
  # plain sentence" — both are the story's fourth scenario restated, and it stays above. Sections I
  # and J of the QA procedure read the sentence against `docs/voice.md` by hand.

  # The rest of the walk's rules still hold on this path.

  Scenario: The live interview reads like a colleague conducting it
    When I read what the interview says to me
    Then it asks one thing at a time, in sentences
    And it names no tool, no field name and no file path

  # Cut: "the stage 2 card I see has been checked against the record behind it" — ticket 12 walks
  # the card door at stage 2 and stage 1, and this path renders the same card through the same
  # `nemo.card.render`. Add it back if the live path ever grows a card of its own.

  # Not a scenario, deliberately: "run live once against the real lane". A scenario here would run
  # against a stand-in, which is the thing the box exists to distrust. It is section G of
  # `archive/qa/stage-2-the-live-interview-path.md`, driven by a human against `127.0.0.1:4000`.
