# PAULA retrieval consistency and supplementary CSV review

Implementation review: 28 October 2026. Source changes run in the existing
Docker Django service against PostgreSQL/pgvector. No institutional records,
embeddings, accounts, historical chats, source CSVs, or retrieval thresholds were
changed by this implementation. There are no new dependencies or migrations.

## Root causes and implemented behavior

1. **Normalization disagreed between retrieval and grounding.** Personnel lookup
   ignored words such as `currently`, `now`, and `today`, but the final evidence
   gate treated them as unsupported factual constraints. A shared normalization
   module now aligns lexical matching, role checks, and grounding. Freshness
   requests produce a snapshot caveat; they do not establish real-time validity.
   Dates, historical language, and other substantive constraints remain present.
2. **Equivalent role titles failed validation.** `VP` versus `Vice President`,
   `Academics` versus `Academic`, and supported Filipino role terms now share
   lexical representations. Displayed institutional text remains unchanged.
   A vice president cannot answer a university-president identity query.
3. **Headings supplied incorrect role qualifiers.** A section called Academic
   Services could make an unrelated vice president appear eligible. Qualifiers
   must now occur in the actual personnel role, rather than a nearby heading.
4. **Directory presence caused premature abstention.** An empty structured
   personnel result now proceeds to supported local role lookup and gated hybrid
   retrieval. Conflicts and ambiguity stop retrieval instead of triggering a
   less constrained fallback. Exhausted personnel hybrid searches are not
   repeated, and contextual fallback cannot bypass their identity filter.
5. **Repeated personnel cards crowded results.** Identical name/role claims
   across website sections now return one representative with supporting source
   records and preserved section memberships. Generic question/answer duplicates
   also consolidate within the same office scope. Copies are not independent
   votes. Different credentials or conflicting holders are not silently merged.
6. **Follow-up rewriting lost meaning.** Generic role entities use the existing
   entity-slot resolver, retaining explicit role qualifiers. Repeated references
   such as “Who is currently holding that role?” resolve to the earlier subject.
   Valid pronouns such as `there` are protected from typo correction. Rewritten
   queries continue through retrieval and final evidence validation.

The shared normalization, duplicate handling, and fallback safeguards apply to
all knowledge sources using this pipeline. Tests also cover scholarship,
academic-program, policy, office, and procedure evidence. Personnel-specific
identity constraints remain in the existing structured personnel adapter.
Existing enrollment, navigation, authentication, guest context, source
attribution, and provider architecture are preserved.

The raw cosine-distance cutoff remains **0.45**. Exact structured lookups remain
separate from vector similarity. No threshold relaxation was used to obtain the
reported results. These deterministic paths add no LLM calls.

## Conflict and source handling

- Official website excerpts are source-linked. Differences from legacy local
  staff records are shown as explicit source-review notes, with record references
  retained internally. They do not update the staff database.
- Different official holders for the same role trigger a conflict. Multiple
  plausible roles or incomplete name variants require clarification.
- An eligible office-submitted identity claim that disagrees with website
  personnel evidence blocks a definitive answer. The PBMO director query now
  exposes this conflict instead of silently choosing a spelling.
- Queries requesting current information receive a stored-snapshot caveat.
  Scrape time is an observation time, not an appointment or effective date.
- Existing evidence-only rendering and provider evidence-ID validation remain
  active. Conversation history supplies intent, never factual evidence.

Outstanding review examples include the president's `SPC`/`SPCS` credential
forms, differing legacy and website VP details, abbreviated personnel names,
and PBMO name spelling. The implementation does not decide these facts.
The manually corrected **Khen Malaque / JSIT Moderator** record is preserved.

## CSV dry-run workflow

Command: `chatbot/management/commands/audit_personnel_csv.py`.
Pure audit: `chatbot/csv_reference_audit.py`.

```powershell
docker exec paulibot_web python -B manage.py audit_personnel_csv --output PAULA_PERSONNEL_CSV_DRY_RUN.json
```

This command has no import or apply mode. PostgreSQL reads execute in a read-only
transaction. The optional JSON file is a review artifact, not a knowledge import.
The original CSV files remain supplementary references and are not added to live
RAG evidence or embedded automatically.

Each observation records file SHA-256, stable observation ID, filename, row,
original source URL, scraper order, name, role, optional image URL, matching
database references, potential section memberships, and review flags. Capture
time and appointment effective date remain null when unverified. Repeated runs
against unchanged files and database snapshots produce identical output.

Invalid UTF-8, unsupported schemas, malformed extra columns, missing identity
fields, unapproved URLs, and spreadsheet-formula prefixes are rejected or
quarantined for review. Filename labels never establish a department. Repeated
name/role observations retain cross-file provenance without creating records.

| Audit result | Count |
| --- | ---: |
| UTF-8 BOM CSV files | 10 |
| Observations | 177 |
| Distinct normalized name/role claims | 159 |
| Repeated claim occurrences | 18 |
| Rows matching stored structured website snapshots | 176 |
| Quarantined rows | 1 |
| Rows with review flags, including repeated claims | 24 |
| Database records imported or updated | 0 |

`corroborated_snapshot` means matching stored website text, not independently
verified current information. All CSVs cite the same administrator page; matching
the database copy does not create a second independent authority.

The quarantined row is **Ms. Nessel Auditor**, whose role is blank. The file
named `CollegeFaculty_CFP.csv` matches **College of Education, Arts and Sciences**
content and requires section-label review. Cards in a college section are not
automatically interpreted as teaching faculty. Records missing from this scrape
are preserved; absence is not evidence of resignation or removal.

Future ingestion remains a separate, explicitly reviewed operation: approve
source/section mappings and effective dates, resolve flagged identity conflicts,
then link verified observations to existing records before considering genuinely
new claims. Only approved new or changed factual text should require embeddings.
No importer or automatic fact-overwrite mechanism was introduced here.

## Verification and measurements

### Automated regression suite

**153 tests passed** through the Docker Django service; Django system checks
reported no issues. Tests use fictional fixtures and mocked providers where
appropriate. Passing tests do not certify every institutional fact.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_retrieval_consistency chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context chatbot.test_chat_sessions --verbosity 1
```

Coverage includes role aliases and qualifiers, exact identities, duplicate
section cards, source conflicts, missing knowledge, temporal constraints,
cross-domain grounding, English/Filipino/Taglish follow-ups, topic switching,
context isolation, invalid provider selections, retrieval failures, and CSV
idempotency/quarantine. Existing guest and authenticated conversation tests
were rerun; no historical records were removed or reassigned.

### Read-only PostgreSQL retrieval benchmark

Artifacts: `PAULA_RETRIEVAL_BASELINE.json` and `PAULA_RETRIEVAL_AFTER.json`.
Runner: `scripts/evaluate_retrieval_consistency.py`.

| Measurement | Before | After |
| --- | ---: | ---: |
| Targeted regression checks passing | 8/14 | 14/14 |
| Retrieval cutoff | 0.45 | 0.45 |

The six repaired checks concern `currently`, `now`, `today`, expanded VP title,
a repeated-role follow-up, and a role-switch follow-up. Ten positive direct
queries are timed using six runs each, discarding the first run. Two negative
controls check exact-lookup exclusion only; two follow-ups validate resolution
and retrieval. This is a small diagnostic corpus, not a general accuracy score
or a benchmark of all vector retrieval domains.

Before measurements were approximately 45–62 ms per successful website-role
case; final after measurements were approximately 58–78 ms per website-role
case. The local moderator lookup measured 4.64 ms after the change. Exact
per-case timings are recorded in the JSON artifacts.
Source-review reads add work, and machine load varies. There is **no demonstrated
latency improvement**. The eliminated redundant hybrid retry is verified by
call-count tests, not a claimed production speedup. No LLM or embedding
generation is included in these retrieval timings.

### Running-application checks

`scripts/verify_retrieval_consistency_http.py` exercises the Vite proxy and actual
Docker backend in guest mode, including canonical titles, Filipino phrasing,
signed contextual follow-ups, one consolidated official-page citation, the
manually corrected moderator, and the PBMO conflict response.

Results are in `PAULA_RETRIEVAL_LIVE_CHECKS.json`. All **13 checks passed** against
the final active version, with a median of **155.18 ms** and maximum of
**3312.39 ms**. Every checked response reports `saved: false`. First requests to
cold Gunicorn workers take longer than warm requests. Backend startup briefly returned HTTP
500 at the proxy; readiness subsequently returned HTTP 200.

### Database integrity and dry-run repeatability

`scripts/verify_csv_reference_integrity.py` performs the audit twice and compares
the report bytes, source hashes, and complete PostgreSQL row fingerprints.
It also compares knowledge fingerprints against the earlier saved snapshot.

```powershell
docker exec paulibot_web python -B manage.py shell -c "import runpy;runpy.run_path('scripts/verify_csv_reference_integrity.py',run_name='__main__')"
```

Proof: `PAULA_CSV_INTEGRITY_CHECK.json`. Knowledge facts and embedding arrays
remain unchanged: **12 StaffMember, 134 FAQ, 476 WebResource** records.
All **139 conversations and 176 stored exchanges** were preserved. Source CSV
hashes match the audited files, repeated reports are byte-identical, and the
corrected JSIT moderator remains in place.

## Files changed in this implementation

| File | Purpose |
| --- | --- |
| `chatbot/query_normalization.py` | Shared Unicode, lexical, role, identity and freshness helpers |
| `chatbot/evidence_identity.py` | Claim consolidation with supporting provenance |
| `chatbot/grounding.py` | Shared validation, role constraints, aliases, ranking and citation metadata |
| `chatbot/personnel.py` | Structured name/role lookup, ambiguity, conflicts and review notes |
| `chatbot/rag.py` | Consistent fallback, metadata, deduplication and conflict propagation |
| `chatbot/intents.py` | Protect valid contextual words from typo correction |
| `chatbot/conversation_context.py` | Generic role swaps and repeated-role references |
| `chatbot/logic.py` | Visible source-review notes and snapshot caveats |
| `chatbot/csv_reference_audit.py` | Provenance-aware, non-importing CSV analysis |
| `chatbot/management/commands/audit_personnel_csv.py` | PostgreSQL read-only review command |
| `chatbot/test_retrieval_consistency.py` | New regression tests |
| `scripts/evaluate_retrieval_consistency.py` | Read-only targeted retrieval benchmark |
| `scripts/verify_retrieval_consistency_http.py` | Live guest response checks |
| `scripts/verify_csv_reference_integrity.py` | Database/source integrity and idempotency checks |
| `PAULA_RESPONSE_GROUNDING.md` | Pointer to this implementation review |
| `PAULA_RETRIEVAL_CSV_REVIEW.md` | This report |

Generated JSON artifacts are listed in the verification sections. Other dirty
files in this checkout include earlier authorized work; this list identifies
the current retrieval/CSV implementation scope. No frontend files changed in
this implementation.

## Remaining limitations

- Institutional source conflicts require human verification. Neither a newer
  filename nor a scrape timestamp establishes a current appointment.
- Generalized utilities improve shared paths but do not provide universal
  language understanding, arbitrary typo correction, or contradiction detection
  across all differently worded documents. Unsupported references still clarify.
- Strict name matching preserves uncertain identity variants rather than
  guessing. Incomplete names may need clarification or manual alias review.
- Broader labeled SPUS evaluation data is still required for recall/precision,
  full semantic-search latency, multilingual coverage, and threshold calibration.
- Cold-start behavior and production concurrency require separate profiling.
  These checks do not establish production performance or deployment readiness.
- No fresh official-site crawl or OCR was performed in this implementation.
  The CSV workflow compares stored evidence and flags unknowns; it does not
  certify that the live website or university personnel has not changed.
