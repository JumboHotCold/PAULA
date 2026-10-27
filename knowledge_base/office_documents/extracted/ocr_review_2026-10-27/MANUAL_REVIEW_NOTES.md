# OCR and Source-to-Knowledge Findings

**Review date:** October 27, 2026.  
**Scope:** Four local PDFs, 16 pages; fresh automated OCR with page previews and targeted retries.  
**Status:** Extraction completed; source discrepancies and unresolved readings remain. No blanket institutional verification is claimed.

## Reading the outputs

- Start with each document's `reconciled_text.txt`. This contains recognized text, not generated summaries.
- `raw_text.txt` preserves the original page-pass selection. Each page JSON retains all three result variants and their bounding boxes/scores.
- `reconciliation_audit.json` records two spatially matched alternate readings selected using a higher-confidence OCR pass. These are heuristic substitutions, not human-certified corrections.
- There are 29 remaining lines below the review threshold of 0.85 after reconciliation. Many concern seals, signatures, or small header text; this number is not an OCR error rate.
- Read flowcharts and multi-column layouts using the page images. Flattened text can place an interface, activity, or document identifier beside the wrong label.
- The PBMO FAQ page 3 research-use paragraph was missed by full-page OCR. A focused deskewed, line-segmented retry recovered its five lines. Read [the separate retry](PBMO_FAQs/page_03_research_scope_line_retry.txt) with [its crop](PBMO_FAQs/page_03_research_scope_deskewed.jpg); it is deliberately not silently inserted into the raw transcript.

## Substantive comparison findings

| Finding | Source evidence | Existing knowledge representation | Review outcome |
|---|---|---|---|
| PBMO director spelling and credentials | FAQ PDF page 3's printed line appears as **MRS. MICHELLE TIMBLACO-PLAZA, LPT, MA-Comm** | PBMO JSON items 9 and 10 use **Michelle Timblacol-Plaza, PT, MAComm** | Visible source-to-JSON discrepancy. Confirm exact spelling and credentials with PBMO before editing personnel data. |
| Publication list | FAQ PDF page 1 identifies the **1st Semester President's Report**, **The PauliGlobe**, and annual **Yearbooks** | PBMO JSON item 1 additionally includes **Monthly Institutional Newsletters** | The newsletter claim was not corroborated in these four PDFs. It may require another source; do not treat absence here as proof it does not exist. |
| Logo color exception | Branding PDF page 6 states that logo color cannot be changed **except in greyscale** | PBMO JSON item 6 presents an absolute no-recoloring rule | Preserve this source qualification or clarify its intended application with PBMO. The FAQ letter also gives general no-modification language, so the sources need careful reconciliation. |
| Broader historical claim | Branding graphics show the seal/motto and year; the reviewed body text provides Paulinian mission/charism statements | PBMO JSON item 14 also calls SPUS the first university in the Caraga Region | A seal graphic alone does not substantiate that historical/status claim. An additional authoritative source is needed. |
| Registrar identifier | Registrar PDF page 2 prints **URO-PR-0016**; pages 1, 3, and 4 include revision suffixes | Registrar JSON abbreviates document references, including **URO-PR-016** | The procedure sequence broadly agrees, but exact document identifiers should be checked before presenting them as verbatim source references. |
| Married-applicant document | Registrar PDF page 4 is recognized as **Marriage Contact if Married**; the printed label is ambiguous/possibly a source typo | Registrar JSON says **Marriage Certificate** | Do not silently infer a different document name from OCR. Ask the Registrar to confirm the intended requirement. |
| Scope of PBMO posting requests | Procedure PDF page 2 lists communication interfaces including verbal communication, letter, text message, and email | PBMO JSON item 12 summarizes a formal written/electronic request | The summary is narrower than the flowchart interface. Confirm whether the stricter interpretation is intended. |

These are source comparison findings, not automatic corrections. Original JSON entries, PDFs, earlier extraction files, and PostgreSQL records were preserved.

## Details corroborated by the reviewed pages

- Registrar pages 2–4 contain separate continuing-student, transferee, and incoming-freshman enrollment flows. They do not justify selecting freshmen for an unspecified enrollment question.
- PBMO FAQ page 2 specifies event-coverage requests **three to five working days** in advance and posting submissions **at least two working days** before the target publishing date.
- PBMO FAQ page 2 gives weekday hours of **8:00 AM–12:00 NN and 1:30 PM–5:00 PM**, and Saturday hours of **8:00 AM–12:00 PM**.
- PBMO procedure page 2 depicts request → layout → director review/approval → online posting.
- Branding page 4 visibly lists `deb402`, `005301`, `002c04`, `215a2e`, `0101c1`, `fcd108`, and `da0200`. Exact classification of every swatch as primary/secondary should not be inferred from OCR text alone.
- Branding page 6 specifies a **0.5-inch minimum logo width**; page 7 distinguishes primary headline/title fonts from secondary body/caption fonts and cautions against stretching, compressing, or warping text.

## Dates visible in the scans

| Source | Visible date |
|---|---|
| Registrar subject changes, page 1 | Effective October 6, 2015 |
| Registrar old students, page 2 | Effective August 1, 2017 |
| Registrar transferees/freshmen, pages 3–4 | Effective September 29, 2023 |
| PBMO FAQ letter, page 1 | October 20, 2026 |
| PBMO online-posting policy, page 1 | Effective July 21, 2025 |
| PBMO online-posting procedure, page 2 | Effective July 1, 2025 |

The current document identifier and a superseded identifier may appear in reverse order in flattened OCR. Use the image labels when establishing revision history. The presence of a date does not establish that no newer revision exists.

## Source-use note

The PBMO FAQ letter's final page limits the supplied materials to the approved PAULA capstone research/development scope. That paragraph was recovered by the focused retry. Its restrictions are part of the source and should remain associated with the documents. OCR processing in this task was local; no document was sent to a cloud OCR/LLM service.

## What this review establishes

Every page was processed, outputs are inspectable, source PDF hashes remained unchanged, and important transcription/knowledge discrepancies were surfaced. Names, signatures, exact codes, ambiguous requirements, and latest-revision status still require human or institutional confirmation. The new OCR outputs were not ingested into PAULA.
