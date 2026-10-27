# Automated Office PDF OCR Review — 2026-10-27

**Start here:** [Source-to-knowledge findings and unresolved issues](MANUAL_REVIEW_NOTES.md).

All four PDFs were processed locally in an isolated worker. Source PDFs were mounted read-only.
Original source hashes were unchanged. Existing JSON and database knowledge were not updated.

OCR was run on every page, including pages that also contain a text layer.

| Document | Pages | New transcript characters | Flagged pages |
|---|---:|---:|---:|
| Registrar/REGISTRAR ENROLLMENT PROCEDURES.pdf | 4 | 5874 | 4 |
| PBMO/PBMO FAQs.pdf | 3 | 4919 | 3 |
| PBMO/PBMO PROCEDURES.pdf | 2 | 4458 | 2 |
| PBMO/PBMO SPUS BRANDING.pdf | 7 | 3419 | 3 |

## Method and interpretation

Post-processing retained two higher-confidence, spatially matched alternate readings;
see `reconciliation_audit.json` and each document's `reconciled_text.txt`.
A focused deskewed, line-by-line retry separately recovered the PBMO FAQ page 3
research-use paragraph. These supplemental outputs preserve all initial OCR results.

- RapidOCR 1.4.4 CPU inference; engine/package versions are recorded in manifest.json.
- Each page has color, grayscale/autocontrast, and overlapping-tile OCR passes.
- The primary transcript is selected heuristically for fuller, confidently recognized text. All passes are retained.
- Page JSON contains recognized boxes and scores. Red outlines in preview overlays identify lines below 0.85 recognition confidence.
- Recognition confidence is not measured character accuracy. High confidence does not prove a transcription is correct.
- Diff files compare against earlier raw extraction; differences may reflect reading order, spacing, omissions, or recognition errors.
- Flowcharts/tables are flattened into text. Consult page previews to establish relationships and reading order.
- knowledge_comparison.json proposes pages to compare with each existing FAQ; lexical coverage does not verify an answer.
- Authenticity, latest-revision status, signatures, names, dates, codes, and branding colors require human/institutional checks.

## Engine documentation

[RapidOCR 1.4.4 API](https://rapidai.github.io/RapidOCRDocs/v1.4.4/install_usage/api/RapidOCR/)
