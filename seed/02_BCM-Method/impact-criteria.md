# BIA rating scale: impact categories, time horizons, threshold

| | |
|---|---|
| **Organisation** | Marschkamp Fleisch GmbH & Co. KG |
| **Machine-readable mirror** | `method.json` (`method_version: 2026.2-MK`) |

## 1. Purpose

This is the read-back scale against which every critical activity is rated in the Business Impact Analysis. It states the impact categories, the time horizons, the rating scale, the intolerability threshold and the MTPD rule, in the same words as `method.json`.

## 2. Rating scale (severity 1 to 5)

| Level | Label |
|---|---|
| 1 | none |
| 2 | low |
| 3 | medium |
| 4 | high |
| 5 | very high |

**Intolerability threshold = 4.**

## 3. Time horizons (7)

`1 h · 2 h · 4 h · 8 h · 24 h · 72 h · 168 h`

## 4. The 5 impact categories

| Id | Category |
|---|---|
| `health` | Health of persons |
| `financial` | Financial |
| `legal` | Legal |
| `image` | Image |
| `operational` | Operational |

## 5. RPO vocabulary

The words an RPO may be stated in (identical to `method.json` → `rpo_vocabulary`):

`<1 h` · `<24 h` · `<168 h` · `>168 h`

## 6. MTPD rule

Beyond the last horizon: **`>168 h`** (`beyond_horizons` in `method.json`), the word said for an MTPD no horizon reaches.

MTPD = the earliest time horizon at which the worst-case rating across the categories reaches intolerability threshold 4 (high). A grid that reaches it in no horizon has no MTPD within the horizons, which is what '>168 h' means.

## 7. RTO

The RTO is the process owner's decision in the interview, recorded as stated; it is not derived from the grid.
