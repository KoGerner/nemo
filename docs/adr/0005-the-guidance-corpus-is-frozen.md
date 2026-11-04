---
status: accepted
---

# The AI4BCM guidance corpus is frozen as it stands

The guidance connector (`mcp.ai4bcm.org`, open, no bearer token, five tools) serves release
`2026.09.1`: 383 chunks built 2026-09-11 from nine sources — the project's own `units/` tree plus
eight literature documents. It is done. Nothing is added to it for nemo, and it stays open to the
public deliberately rather than by oversight.

Recorded so it is not re-proposed: **ISO 22301, ISO/TS 22317 and the BCI Good Practice Guidelines are
not in the corpus and are not going in.** A BCM manager asking what ISO/TS 22317 says about setting
MTPD will be answered from what is in the corpus — DORA, NIST SP 800-34r1, the Swiss FONES minimum
standard, the UK Cabinet Office guidance and the rest — or not at all. This is a deliberate call by
the owner, taken with the BCI World audience known.

## Consequences

- Wiring, not content: the Chainlit chat lane calls the connector live and prints the citation on
  screen. No corpus work is on nemo's critical path.
- The connector serving exactly what `AI4BCM/guidance` `origin/main` holds is a verified fact as of
  2026-09-11, not an assumption. If they ever diverge, the corpus is no longer frozen — it is stale.
