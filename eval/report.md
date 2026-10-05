# Extraction evaluation report

- Date: 2026-10-05
- Model: `mock`
- Prompt: `extraction_v1`
- Golden notes: 20 (synthetic, Iraqi dialect)

| Field | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| symptoms | 1.00 | 1.00 | 13 | 0 | 0 |
| access_findings | 1.00 | 1.00 | 6 | 0 | 0 |

- Invalid drafts: 0 / 20 (0%)
- Evidence failures caught by the validator: 0
- Accepted drafts with ungrounded spans: 0 (the validator rejects them by construction)

Scoring is by `code` per note. Invalid drafts count as misses, never as predictions.

## Notes that differ from the golden annotation

- none
