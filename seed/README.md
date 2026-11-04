<!-- synthetic:true pack:marschkamp note:"wholly invented demo data (D5) — no real organisation, person or brand" -->

# Marschkamp — company files for the BIA

## What Marschkamp is

Marschkamp Fleisch GmbH & Co. KG is an invented food producer focused on meat cutting, meat processing and
convenience products: about 600 FTE, about €320 million revenue a year, three production sites (Marschkamp with the
headquarters and the logistics centre, Wilstermarsch, Breitenburg). Its twenty finished BIA records, one per
process, are the prior cycle; each also stands as one interview transcript. A walk re-does the BIA on that evidence,
starting each process at stage 1.

## Folder structure

| Folder | Files |
|---|---|
| `01_Organisation/` | company-profile.md, org-and-roles.md, process-map.md, glossary.md, bia-programme-plan.md |
| `02_BCM-Method/` | method.json, impact-criteria.md |
| `03_Dependencies/` | dependency-register.json, asset-inventory.md, supplier-register.md |
| `06_Risk-and-Incidents/` | risk-register.md, the operational risk register written for the demo pack |
| `07_Interviews/` | twenty prior interview transcripts, one per walkable process; three 2026 re-interviews (production, order picking, dispatch) |
| `08_Prior-Cycle/` | the prior cycle 2024–2025: the twenty records |
| `09_Evaluation/` | rt1-poison.md, a test fixture for nemo, not company evidence |
| `output/` | the walks in progress (`.bia-runs/`), written by the walk |
| `output/.retired/` | retired-from-register.md, the register's retired entries, outside every chat reader |

## How the files fit together

- **The process map** lists 25 processes in three groups (core, HR, IT). Twenty have a finished record and are
  walkable; five HR processes were rated not time-critical and have none.
- **The method** (`method.json`) rates five impact categories (health of persons, financial, legal, image,
  operational) over seven time horizons (1 h to 168 h) on five levels (none, low, medium, high, very high), with
  intolerability threshold 4.
- **The dependency register** holds the IT systems, technical resources, documents and roles that the records'
  resource tables name, each with the processes that use it. A transcript's "Depends on" line uses the register's
  names exactly.
- **The transcripts** carry `department:` (the process's slug), and their front matter names the interviewee, the
  date and the record they come from.

## Document control

The company's documents carry a reference number, a confidentiality note and a control note. The prior cycle's
records carry no approval: no check, approval date or signature is recorded.
