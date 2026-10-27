# Registrar PDF Recheck

Review date: October 27, 2026.

Source: `../Registrar/REGISTRAR ENROLLMENT PROCEDURES.pdf` (four scanned pages).
Compared with `../Registrar/Registrar_knowledge.json` and the existing extracted
Registrar guide/raw OCR text.

## Method and limits

All four PDF pages were freshly rendered with the existing container's PyMuPDF
library and visually inspected. Each page returned zero characters through PDF
text extraction. RapidOCR and pytesseract were not installed in that container,
so this was **visual verification, not a new automated OCR run**. No dependencies
were installed and no source PDF, JSON entry, or database record was changed.

## Page findings

| PDF page | Subject | Visible document number | Visible effective date | Main flow |
|---|---|---|---|---|
| 1 | Changing / adding / dropping / withdrawal of subjects | URO-PR-007-(003) | October 6, 2015 | Request form → clerk issues form → student completes form → approval/signatures → copies to Finance and Registrar |
| 2 | Enrollment for old students | URO-PR-0016 | August 1, 2017 | Academic advising → fee assessment → payment → Registrar encoding and validation |
| 3 | Enrollment for transferees | URO-PR-017-(001) | September 29, 2023 | Dean evaluation/crediting → SAO information and encoding → Finance payment → Registrar validation/study load → ICT ID validation and clinic profiling |
| 4 | Enrollment for incoming freshmen | URO-PR-005-(007) | September 29, 2023 | Guidance entrance examination/admitting verification → Dean advising/schedule → Finance assessment/payment → Registrar validation/study load → ICT ID → clinic profiling |

The three enrollment flow sequences broadly match the separate JSON procedure
entries. A generic enrollment question does not identify which flow applies.
It should ask the student category before selecting a procedure.

## Details requiring care

- The JSON uses abbreviated document references; the PDF includes revision
  suffixes and spells the old-student identifier `URO-PR-0016`.
- The freshman page includes a marriage-document label for married applicants.
  Its exact wording should be confirmed with the Registrar before treating a
  normalized document name in a summary as an exact transcription.
- Summaries expand abbreviations and describe administrative details. Agreement
  on the step sequence is not a word-for-word validation of every JSON claim.
- These effective dates do not establish that the documents are the latest
  revisions in force today. Their currency requires institutional confirmation.

This review supports category clarification and procedure selection. It does not
approve automatic replacement or re-ingestion of the existing knowledge records.
