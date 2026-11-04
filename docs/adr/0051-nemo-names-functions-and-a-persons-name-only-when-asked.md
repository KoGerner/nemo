# nemo names functions; a person's name appears only when the typed line asks for names

Status: **the owner's words**, recorded 2026-10-10 by 21_nemo_plan for ticket 418, all in 34_nemo_check's a732e064 and verified there:
TYPED 2026-10-10T19:47:20Z *"no names in chat, keep them in teh marschkamp datam, but only write the functions, only the real names if
asked for"*; ANSWERS 19:48:49Z, to whether drafts follow it: *"also in emails, makes it easier for the demo. check if all names have functions
which are realistic and simple to understand and are not duplicates"*, and to when a line asks for names: *"Only when 'name' is in the line
(Recommended)"*. Tightens his "Functions instead of names": **"Everywhere"** (ANSWER 2026-10-07T10:54:14Z, /opt/brain 8a65fc28).

## Decision

1. **Everything nemo shows names a function, not a person**: chat answers, tap labels (the "Write to an owner" picks), cards, email
   drafts (To line, greeting, body) and the briefing PDF read "the Head of IT Operations", never "Marek Sobotta".
2. **A person's name appears only when the typed line contains "name" or "names"**, and then beside the function.
3. **The seed keeps the names** (Marschkamp's org-and-roles, interviews, register owners): this is a rule about what nemo shows, not
   what the data holds. Every function the seed names is realistic, plain and held by one person (13_marschkamp checks).
4. **A draft greets the function by its title**: *"Dear Head of IT Operations,"* (his ANSWER 2026-10-10T19:50:31Z in a732e064, verified).
5. A draft's To address is a function mailbox (e.g. `head-of-it-operations@marschkamp.example`), never a person's. **Corrected 2026-10-11** (review-2026-10-11, 35_nemo_check's ruling 2026-10-11): ADR-0043's 2026-10-05 note had changed the To line to the person (`first.last@`); this decision supersedes that note.

## Considered and rejected

Names everywhere (the state before): at a table of 50 strangers a function reads at once, a fictional name does not. Names in drafts
only: rejected by his "also in emails".

## Consequences

Quotes keep their speaker's words but are attributed by function. **The graph pages too** (owner lines, strips, trays, Sites, phone and laptop views): his TYPED 2026-10-10T19:49:36Z in a732e064,
*"yes, drop names on the graph pages too"* (verified). The prompt check's expected facts already use functions (`seed-marks-387.md`; now the current sheet `seed-marks-387-m12.md`).

## Note, 2026-10-19 (25_nemo_plan): names inside quotes stay

His ANSWER 2026-10-19T09:32:26Z in 15_nemo_design's window (991d0491, verified from the tool result by 25_nemo_plan), *"Keep quotes as said"*: a quote stays byte for byte, a name said inside it included; the speaker label above a quote stays a function. The exemption above ("Quotes keep their speaker's words") stands. No ticket.
