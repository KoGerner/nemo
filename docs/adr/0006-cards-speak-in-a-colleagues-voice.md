# Stage cards speak in a colleague's voice, generated from the record

Every stage card is written as a competent, friendly BCM manager would write to another BCM manager
who rarely uses LLM tools: prose, the reason before the figure, and the next move offered in a
sentence rather than as a numbered machine list. The decision, its stated rule and its four-way
gradient stay underneath unchanged, so the card is still auditable and a model still cannot decide on
the human's behalf.

This is a binding rule alongside the six in `docs/architecture-options.html`, not copy polish: it
changes what all five stages emit, and it is the single largest improvement never built in v1.

## Consequences

- **The prose is generated from the record's figures, never written beside them.** The human approves
  the card while the referee validates the record; if the card says "about a working day" and the
  record says `MTPD: 8h`, those have drifted, and a view disagreeing with its record is precisely the
  failure the acceptance spec exists to catch.
- The banned list has two halves. Banned **jargon** makes a card unreadable; banned **vagueness** —
  "roughly", "about", "fairly critical", "a working day" — makes it unverifiable, and only the second
  breaks the product. The four strings in `features/01-walking-skeleton.feature` are the worked
  examples for the first half; the second half still has to be written.

## Amendment, 2026-10-19 (ADR-0056)

His answers Q3 and Q5 in 1_nemo_rework's grill (88e66808, 15:44:48Z *"Stage cards too"*, 15:48:02Z *"Words yes, figures/record
no (Recommended)"*): the model writes a stage card's sentences. The figures, the decision rule, the four-way gradient and the
record stay code's, and every figure in the sentences is checked against the record, so the prose still cannot drift from it.
The colleague's voice and the banned list stand.
