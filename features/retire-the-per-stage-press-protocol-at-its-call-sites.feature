Feature: Retire the per-stage press protocol at its call sites
  As the owner of this walk I said the press protocol goes and the walk gets one door. Ticket 24
  built the door and took the seven per-stage functions private behind it. This ticket is the other
  half: the callers move, and the tree loads and passes again.

  The ruling is mine, of 2026-09-13, and it is ADR-0013: *"we overpowered the buttons approach; we
  shifted to having the answers as text, like Claude does."* Nothing here is new design.
  **24 and this ticket land as ONE merge:** 24 alone leaves `tests/ui` un-collectable.

  **This is the third walk, and I named its subject myself: the ADR-0013 harness contract.**
  Not "the rest of the migration" — a walk pointed at anything wider rediscovers walk 2. Walk 1
  moved the 20 call sites the story listed. Walk 2 moved stage 5's eighteen and went red at qa with
  174 assertion failures, zero crashes, in one seam. Its diagnosis was right and its repair is
  committed red on purpose at `c7e17bd`, which added `ways`, `answer_in_words` and
  `typed_besides_the_answers` to `tests/ui/walk/procedure.py`. **Do not revert it; build on it.**

  **Everything below was measured on this branch at `666684e`, today, on an idle box.** That merge
  brought `main` in for the third walk and moved the ground again, so the numbers walk 2's findings
  quote are no longer this tree's. What is actually red now:

      $ .venv/bin/python -m pytest -q
      16 failed, 1505 passed, 1 xfailed in 117.20s

      $ .venv/bin/python -m pytest tests --collect-only -q | tail -3
      E   ImportError: cannot import name 'agree_scope' from 'nemo.walk'
      ERROR tests/ui/test_a_scan_mints_a_room_from_the_seed.py
      400 tests collected, 1 error in 1.42s

  **One. Ticket 47 arrived in that merge and brought three fresh call sites back**, and the sweep
  at `features_steps.py:5184` prints them itself:

      [('features_steps.py', 'agree_scope'),                     line 6932 — a NameError, and
       ('src/nemo/test_walk.py', 'agree_scope'),                  line 666    it reds 13 of the 16
       ('tests/ui/test_a_scan_mints_a_room_from_the_seed.py', 'agree_scope')] lines 106 and 217

  Each becomes a call through the public door, `answer(room_folder, process, words, revision)`. The
  scan slice's file is the one module in the tree that does not load, so this is the headline
  symptom again, in a file nobody had seen when the ticket was written.

  **Two, and this is the subject. A card's answers are in the card's sentence, and the harness must
  read them there.** Since ADR-0013 the skin registers `open_bia` and `pick_interview` and nothing
  else — `demo_skin/app.py:219`'s `_actions` draws interview picks and nothing else — so on any card
  screen `Screen.buttons` is `()`. **A test that asks what a card offers by reading the controls is
  a call site of the press protocol exactly as a call by name is**, and that is the whole of the 174.
  `Screen.ways` is where the question goes now: it reads `nemo.walk.IN_WORDS` back out of the card's
  own prose. Fifteen files under `tests/` still name `.buttons` outside `procedure.py`, 92 times.
  Most of those are legitimate — a process to open, an interview to pick, or `buttons == ()`
  asserted as the new truth — and **must stay**. The ones that go are the ones comparing the
  controls against an *answer*, and today they are:

      tests/ui/walk/test_a_room_supplied_name_is_exempt_for_its_whole_span.py:432, :435
      tests/ui/test_a_scan_mints_a_room_from_the_seed.py:613, :645
      tests/ui/walk/test_stage_4a_the_refereed_record.py:528
      and every `mobile.press(AGREE)` / `press(ENDORSED)` / `press("endorsed")` — 20 of them,
      in six files — which only still work through `procedure.py`'s fallback and only where the
      card happens to ask for exactly those words.

  **Three. Walk 2's repair left a regression, and it is 7 of the 10 on the merge bar.** Measured
  here at `666684e` on an idle box:

      $ .venv/bin/python -m pytest -q <the three stage-4 files>
      10 failed, 21 passed, 3 xfailed in 122.25s        (on main, the same three: 29 passed,
                                                         5 xfailed — so the break is this branch's)
      7 × E  AttributeError: 'Card' object has no attribute 'ways'

  `ways` is the **harness's** word, on `procedure.Screen`. `nemo.walk.Card` is the **product's**
  card and carries `buttons`, `gradient` and `decision` — walk 2's repair spelled the harness's word
  against the product's object in seven places and they crash rather than fail. **Which way that is
  repaired is the coder's, and both ways are honest:** ask a product card in the product's words
  (`card.gradient`), or give the product card the same question the screen answers. What may not
  happen is a test taught to expect the AttributeError. The remaining three are a different fault —
  a typed stage-3 naming reaching the ask lane instead — and `demo_skin/app.py:372`'s `on_message`
  is where that arbitration lives.

  **What no scenario here may do is run a test suite.** This file is collected by `pytest -q`, which
  the coder, cleaner and hardener gates each run, the last of them once per mutant. Read the tree
  with `pathlib` and `in`, the way the sweep at `features_steps.py:5184` already does, and read the
  answer labels out of `nemo.walk` rather than spelling them here. A browser, `tests/ui` and
  31 minutes belong to `archive/qa/retire-the-per-stage-press-protocol-at-its-call-sites.md`.

  Background:
    Given the files the sweep's checklist names

  # The headline symptom. `testpaths` is `src`, `demo_skin`, `features` — no gate collects `tests`
  # at all, so this is the one place in the line that notices the tree does not load. Reworded from
  # walk 2's version, which named the stage-5 module: that one loads now and the scan slice's does
  # not, and the next merge will pick a third. Name no module; ask the tree.

  Scenario: Every test module in the tree loads
    Given every test module in the tree, including the ones no gate collects
    When the whole tree is collected
    Then no module is reported as a collection error
    And every module the checklist names is collected, with its tests in it

  # Cut: "every file that answers a card answers through the door" — a nine-file copy of 24's own
  # sweep, which reads every source outside the walk and lands in the same merge; its steps at
  # `features_steps.py:6597-6624` go with it. Bring it back if 24's sweep ever narrows.

  # Cut: "a card says its answers in its own words and draws none of them" — 24's "the card offers
  # me no ways to answer to press" and "opening a BIA ... are still choices" pin the product in the
  # same merge, `tests/ui/walk/test_the_harness_reads_a_card.py` pins `ways` reading the prose, and
  # the qa's step 29 reads the sentence on a real screen. Bring it back if 24's pair is ever cut.

  # THE SUBJECT: the checklist a migration is finished against. It pins the callers, which is the
  # work; the product side is 24's, above.

  # Cut by ticket 165's last slice: "No test asks a card what it offers by reading what there is to
  # press", with its reading rule. Every file under tests/ that read a card's controls (the real-skin
  # file, procedure.py and the stage-4 trio) retired whole (last held at 602cc648), so nothing was
  # left for it to read.

  # Cut: "every legitimate `.buttons` is still there" — a scenario that counts what did NOT move is
  # a harness for a number that changes whenever a UI file does. The qa's section F reads those by
  # hand instead, which is where judgement belongs. Bring it back if a walk ever deletes a
  # process-pick assertion to get a red to go away.

  # Cut: "no harness word is spelled against the walk's own card" — the seven AttributeErrors. It
  # needs to know which of two types a name was read off, which needs Python parsed, and the qa's
  # step 11 catches it in two minutes by running the three files. Bring it back if the crash ever
  # survives a green merge bar.

  # Cut by 165 slice 4: "a card still may not show a manager a machine name" read the banned-word
  # lists of the stage-3 and skeleton walk files, which that slice retired (git holds them).

  # The seam ticket 24's door made with ticket 18's stage 5. Green since walk 2 and kept as a
  # regression guard: `main` has been merged into this branch three times and each merge put the
  # two movements back in front of each other.

  Scenario: Answering the stage 4 card never hands me an error
    Given a walk standing at stage 4 with its record refereed
    When I answer that card in my own words, through the door
    Then the record I just accepted is the one in my room, and its receipt binds it
    And if the walk stopped between the two, the card I get says my BIA is saved and not finished
    And nothing that happens on my screen is an exception out of the walk

  # Cut: "nothing was deleted to make the tree load" — sixteen literal counts, in a suite the next
  # merge of `main` reds; the first scenario already reads each named module's tests back out of
  # the checklist, and the qa's steps 25 and 26 hold the sixteen numbers and the skip count at
  # `666684e`. Bring it back if a walk ever deletes a test to make the tree load.

  # Cut: "nothing outside the walk calls a per-stage press function by name" — that is ticket 24's
  # own scenario, in `features/the-one-door-a-walk-is-answered-with-words.feature`, and this ticket
  # is the work that makes it pass rather than a second copy of it.

  # Cut: "a skin is never handed over without a finally" — ticket 34's, and its sweep already reds
  # on this ticket's own qa spec file (`features_steps.py:7998`). This ticket has to satisfy it, not
  # restate it; the qa's step 8 is where that is read.

  # Cut: "the stage-4 suites still pass", "tests/isolation still passes", and "no phone presses a
  # label its card has not got" — a browser, 122 s, 31 minutes and a second interpreter between
  # them. Sections D, G and H of the qa procedure. Bring them back if any of it ever becomes
  # something this venv can run in milliseconds, which is not today.
