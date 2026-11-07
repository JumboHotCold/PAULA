# About SPUS knowledge source

Imported into Docker PostgreSQL on 4 November 2026 from `About SPUS.txt`.
The original UTF-8 file is unchanged. This is user-supplied **curated** knowledge;
the import does not certify it against the current official website or invent
a website URL, publication date, or supplying office.

## Imported coverage

| Topic | Result in this database |
| --- | --- |
| Complete university overview | Reused FAQ 95 |
| Short university identity (`What is SPUS?`) | Created FAQ 151 |
| Vision and mission | Reused FAQ 96 |
| Full Paulinian core-value definitions | Created FAQ 152 |
| Reasons to choose SPUS | Reused FAQ 98 |
| Main campus and Luna campus | Created FAQ 153 |
| Early history and San Nicolas School | Created FAQ 154 |

All four new entries use the existing cached `all-MiniLM-L6-v2` model and
384-dimensional embedding format. Their question labels include
`[About SPUS.txt]` for source attribution. Complete duplicate answers are reused;
focused identity, campus and history excerpts have their own retrieval topics.
Existing records and embeddings were preserved. FAQ count changed from 134 to
138; personnel, web resources and conversation/history fingerprints stayed equal.

## Repeating the import

```powershell
docker exec paulibot_web python -B manage.py ingest_about_spus --dry-run
docker exec paulibot_web python -B manage.py ingest_about_spus
```

The command expects this document's headings, validates UTF-8, and aborts on
unrecognized structure or conflicting content for an existing question. It
does not overwrite or delete existing knowledge. Repeating the completed import
reused all seven topics, created zero rows, and loaded no embedding model.
Editing the source file does not automatically update PostgreSQL; rerun the
preview and review any conflicts before ingestion.

`scripts/verify_about_spus_import.py` additionally fingerprints old rows and
checks repeat-import idempotence. `scripts/verify_about_spus_http.py` checks live
guest answers without creating persistent conversation history.

## Retrieval integration and validation

Short overview questions previously lost every subject token to the relevance
stopword list. Some literal FAQ questions also missed the cosine cutoff despite
already being stored. The reusable exact-FAQ lookup now compares complete
normalized questions before semantic fallback, retaining source attribution,
conflict detection and grounding. Explicit overview phrasings such as
`What is …`, `Tell me about …`, and `Ano ang …` share a question key without
dropping the subject or extra constraints. Unmatched questions continue through
the existing hybrid pipeline with the unchanged **0.45** cutoff.

The lookup does not generate names or institutional facts and refuses differing
answers for the same matched question. The empty-token grounding exception is
limited to a matching stored FAQ; a bare institutional name cannot admit an
arbitrary neighboring document.

**227 backend tests passed**, including 11 new import/FAQ regression tests.
**12 live checks passed**, covering English/Filipino overview questions, vision,
mission, values, reasons to choose SPUS, campuses, early history, a compound
history question and an unsupported 2030 enrollment deadline. The seven original
live questions returned sources in 4/7 cases before and 7/7 afterward. These
single-request checks establish behavior for this corpus, not general accuracy
or latency guarantees.

### Additional recommendation-question regression

The original live suite checked `Why choose SPUS?`, but not
`why should i choose spus?`. Both relevant records were already in the active
PostgreSQL database, with 384-dimensional embeddings: FAQ 98 and FAQ 116.
The reported wording missed exact FAQ matching and its raw cosine distances were
**0.496694** and **0.583072**, respectively, above the unchanged **0.45** cutoff.
The failure was reproduced against both port 8080 and the Vite proxy on 5173.
See `PAULA_ABOUT_SPUS_PARAPHRASE_DIAGNOSIS.json`.

`faq_question_key` now aligns `why should I/we/you …` with `why …` for any stored
FAQ topic. It preserves the full predicate, negative wording, dates, comparisons
and additional audience constraints; it does not treat can/could/must as should.
No knowledge records or embeddings were added, changed or regenerated for this
correction. **231 backend regression tests passed**, including four additional
tests across recommendation domains, constraints and conflicting answers.

The live harness also accepts `--url`, allowing verification through the same
frontend proxy used by `npm run dev`:

```powershell
python -B scripts/verify_about_spus_http.py --url http://localhost:5173/api/chat
```

All **14 updated live checks passed through the Vite proxy**, including the
reported exact wording and its `we` variant. The reported question returned all
four stored reasons and an attributed FAQ source in **36.44 ms** in that single
smoke-test request; this is not a p95 benchmark. Results are saved in
`PAULA_ABOUT_SPUS_LIVE_CHECKS.json`, with the tested URL on each record.
All three restarted workers completed preparation without worker timeouts;
model startup in this run took approximately **101–103 seconds per worker**,
separate from ready-service response time.

Initial database-test setup failed because the isolated Django test database
lacked pgvector. The extension was enabled in that test database only; the
application schema was not changed. The final regression run passed.

Evidence artifacts at the repository root:

- `PAULA_ABOUT_SPUS_INGESTION.json`: source hash, imported/reused IDs and dimensions.
- `PAULA_ABOUT_SPUS_REPEAT.json`: zero new records on repeat ingestion.
- `PAULA_ABOUT_SPUS_INTEGRITY.json`: old-row and embedding integrity checks.
- `PAULA_ABOUT_SPUS_BEFORE.json` and `PAULA_ABOUT_SPUS_LIVE_CHECKS.json`: actual responses and sources.

Implementation files: `chatbot/management/commands/ingest_about_spus.py`,
`chatbot/query_normalization.py`, `chatbot/rag.py`, `chatbot/grounding.py`,
`chatbot/test_about_spus_ingestion.py`, and the two verification scripts above.
