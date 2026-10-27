# PAULA website crawling and personnel lookup update

Verified on 27 October 2026 against the Docker PostgreSQL runtime and the frontend API at `http://localhost:5173/api/chat`.

## Why the reported answers failed

1. The administrator URL was already a seed in `chatbot/management/commands/scrape_spus.py`. Supplying a URL did not ensure that every personnel relationship was retained or retrievable.
2. The previous scraper flattened the page and split it into character-sized chunks. Names, roles and college headings could cross chunk boundaries. A CEIT chunk could include the preceding college or the next college. The grounding gates correctly reject ambiguous associations, but that left only two manually stored instructors for the reported query.
3. PostgreSQL already contained the university president. For the correctly spelled question, that staff record had a measured raw cosine distance of **0.468895**, outside the configured **0.45** cutoff. No answer passed retrieval. The fix does not globally loosen that cutoff.
4. The typo vocabulary did not include `president`. The reported `preseidnt` spelling also needs more than the existing one-edit correction. It now has an explicit correction, while the expanded role vocabulary supports other unambiguous single-edit role typos.
5. A default HTTP request returned 406 and the web browsing tool returned 403. The scraper's existing request headers successfully fetched the live HTML. The new crawler checks robots rules and explicitly reports blocked/failed requests; it does not solve access challenges or ingest error pages.

## What changed

### Crawling and ingestion

- `chatbot/web_crawler.py` parses the HTML DOM with Python's standard library; no new parser dependency or external extraction model is required.
- Each team card's **name and position stay together**. Its containing accordion or tab supplies the section. Collapsed sections present in the HTML are included.
- SEO descriptions, scripts, portraits, navigation and footer content do not supply personnel claims. The page's metadata includes older personnel descriptions; those are deliberately excluded.
- Complete cards become source-linked `WebResource` personnel entries. Each section also receives a faculty roster containing only cards with explicit faculty/instructor/teacher/professor/lecturer roles. An office secretary or librarian alone is not automatically a faculty member.
- General pages retain section headings in their chunks and do not carry an overlapping tail from a different section.
- `--discover` now performs bounded breadth-first traversal from fetched pages. Limits cover pages, depth, request frequency, response size and redirects. Known institutional pages receive priority over other links. Redundant `/team/` profiles are not traversed; their directory cards are already extracted.
- HTTPS host allowlisting applies to every redirect. Search/query URLs, administrative/API routes and downloadable assets are outside this HTML crawler's scope. Previously configured Google Sites/library portals remain explicitly allowed seeds; arbitrary external domains are excluded.
- `chatbot/crawling.py` saves the fetched HTML, SHA-256 digest, extraction diagnostics and a JSON archive of previous page records before an update.
- Each page refresh is transactional. Only that scraper's records for the successfully extracted page are replaced. The 22 old administrator chunks were archived and replaced by structured records. Other knowledge, student accounts and PostgreSQL volumes were preserved.
- Concurrent crawler refreshes of a page are serialized with a PostgreSQL advisory lock. Changed content explicitly clears its stored embedding; an unchanged record keeps its vector. This avoids Django `update_or_create` retaining an old vector when the model clears it outside `update_fields`.
- A failed fetch or a major personnel-layout extraction failure preserves that page's existing database knowledge. Missing card roles are reported and excluded; they are never inferred from the next person's card.

### Retrieval and answers

- `chatbot/personnel.py` performs exact, constrained personnel/college-roster lookup against the structured official-page records.
- This lookup runs before semantic retrieval, so an explicit identity query is not rejected just because its embedding distance exceeds 0.45.
- The exact path does not load MiniLM, generate embeddings or call an LLM. General questions retain the existing gated RAG pipeline.
- A university president query excludes vice presidents. Role and department constraints remain required. Two distinct matching holders/roles produce abstention rather than an arbitrary selection.
- The exact path accepts short identity/roster requests. Historical dates, foreign institutions and additional unsupported constraints do not enter that path.
- A department faculty answer uses the published section roster rather than five nearest individual records. A person's additional graduate-school role does not move them out of their actual CEIT section.
- Personnel names and roles are copied from website text. No office location is added unless the source actually establishes one.
- Website citations now include a fetch timestamp. React displays it as **Website fetched**; this is not a claim that the office confirmed the roster on that date.
- Decorative SVG icons are hidden from assistive text. The literal `svg` wording in the supplied transcript was not returned by the API's factual response; a browser visual check remains distinct from the API tests.

## Actual ingestion results

Source: <https://spus.edu.ph/administrator/>

| Item | Result |
| --- | --- |
| Complete section-specific personnel cards | 407 |
| Distinct section labels | 25 |
| Section faculty roster records | 18 |
| Total new structured website records | 425 |
| Explicit faculty-role entries under CEIT | 27 |
| Incomplete cards excluded | 1 |
| Old administrator chunks archived/replaced | 22 |
| Missing website embeddings after refresh | 0 |

The 407 count represents **section memberships**, not 407 unique people. A person can appear in top management and a faculty section.

The incomplete card is **Ms. Nessel Auditor**, under College of Education, Arts and Sciences: the returned HTML has a name but no stated role. PAULA does not invent one. Other spelling/credential details remain verbatim, including the site's `SPCS` suffix for the president. Crawl success does not certify these institutional details independently.

## Live behavior checked

| Query | Observed frontend API result |
| --- | --- |
| `who is the university president?` | Sr. Marie Rosanne Mallillin, SPCS — University President; administrator-page citation |
| `who is the university preseidnt?` | Same supported answer after normalization |
| `uh who is the ICT Director?` | Engr. Arnold A. Magalona — Director, Information & Communications Technology Systems and Services; administrator-page citation |
| `who are the CEIT faculty?` | One website roster citation with 27 faculty-role entries, including full-time and part-time labels |
| `How do I enroll?` | Student-category clarification |
| `wher is the registar office?` | Registrar map action |
| `who is the director?` | Abstains because several different directors match |
| `who is the CEIT dean?` | Dr. Karen T. Plaza, with the published role and administrator-page citation |

All **eight live frontend API checks passed**. These guest checks did not save student conversations. Exact lookup was separately inspected and left the embedding model unloaded for the four reported personnel requests. A repeat live ingestion refreshed the same 425 records with zero duplicates created, and all website records retained valid embeddings afterward.

## Verification

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler --verbosity 1
```

**69 tests passed.** Coverage includes department boundaries, collapsed sections, missing roles, misleading metadata, president-versus-VP distinction, ambiguity, typos, no-model exact lookup, robots denial, HTTP failures, redirect restrictions, UTF-8, page budgets, dry-run database preservation and changed-versus-unchanged embedding invalidation. Existing grounding and clarification tests also passed.

`npm.cmd run build` passed. Existing large JavaScript bundle and Node deprecation warnings remain.

Snapshots, previous-record archives, extraction diagnostics and live responses are in:

`knowledge_base/website_snapshots/administrator_review_2026-10-27/`

- `latest_crawl_report.json`: live crawl/ingestion outcome.
- `*.html`: fetched HTML snapshots, identified by digest.
- `*.previous_records.*.json`: previous administrator knowledge before replacement.
- `live_chat_checks.json`: actual guest frontend API responses.

A separate three-page **live discovery dry run** successfully followed links from
the administrator page to the homepage and `about-us-2`, producing 425, 16 and 4
review records respectively. It made no database changes. Its report is in
`knowledge_base/website_snapshots/discovery_review_2026-10-27/`.

## Refresh commands

Run through the Docker web service using PostgreSQL. A dry run writes review snapshots and diagnostics but does not write database records:

```powershell
docker exec paulibot_web python -B manage.py scrape_spus --url https://spus.edu.ph/administrator/ --dry-run --max-pages 1
```

Refresh that page and generate missing vectors:

```powershell
docker exec -e HF_HUB_OFFLINE=1 paulibot_web python -B manage.py scrape_spus --url https://spus.edu.ph/administrator/ --max-pages 1
```

Bounded same-host discovery, for review first:

```powershell
docker exec paulibot_web python -B manage.py scrape_spus --url https://spus.edu.ph/administrator/ --discover --max-pages 20 --max-depth 2 --dry-run
```

Omit `--dry-run` to ingest successfully extracted pages. A run with failures exits nonzero and records which pages failed; independently successful pages may already have committed. `--no-embeddings` can defer vectors, but is not the default. The default seed list retains the previous official institutional pages and portals.

## Scope and remaining limits

- This update actually refreshed **the administrator page**, not every SPUS page. Recursive discovery was regression-tested and checked with a three-page live dry run; no complete live site crawl is claimed.
- HTML contains all the personnel cards observed in this fetch. Image-only text, PDFs, login-only content and data loaded solely by JavaScript need separate ingestion. Existing local PDF OCR is a different pipeline.
- This is a management-command refresh, not a scheduled background job or an automatic scrape on every chat request. A new website change requires another refresh.
- The website itself can be incomplete, outdated or inconsistent. PAULA labels faculty answers as stored website information and preserves source wording and timestamps. Office confirmation remains necessary to establish a fully current authoritative roster.
- No account changes, database-volume resets, schema migrations, secret copying, commits or pushes were performed for this update.
