"""Management-command orchestration; snapshots precede atomic per-page refresh."""
from collections import deque
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.utils import timezone

from .models import WebResource
from .web_crawler import (
    OfficialSiteClient, PERSON_CATEGORY, ROSTER_CATEGORY, canonical_url,
    discover_links, extract_records,
)


def configure_arguments(parser):
    parser.add_argument('--url', action='append', help='Fetch only these explicit official URLs; repeatable')
    parser.add_argument('--discover', action='store_true', help='Follow same-host links with bounded breadth-first traversal')
    parser.add_argument('--max-pages', type=int, default=24)
    parser.add_argument('--max-depth', type=int, default=1)
    parser.add_argument('--delay', type=float, default=0.5, help='Minimum seconds between requests')
    parser.add_argument('--dry-run', action='store_true', help='Fetch, extract and report without database writes')
    parser.add_argument('--no-embeddings', action='store_true', help='Defer embedding generation; exact personnel lookup still works')
    parser.add_argument('--output-dir', default='knowledge_base/website_snapshots', help='Workspace-relative snapshot/report directory')


def replace_page_resources(url, records, old_title):
    """A successful extraction replaces only this scraper's records for this URL."""
    with transaction.atomic():
        # Serialize refreshes of this page and preserve unrelated/manual resources.
        with connection.cursor() as cursor:
            lock_id = int.from_bytes(hashlib.sha256(url.encode()).digest()[:8], 'big', signed=True)
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [lock_id])
        existing = list(WebResource.objects.select_for_update().filter(url=url))
        by_title = {obj.title: obj for obj in existing}
        managed = {obj.pk for obj in existing if obj.category in (PERSON_CATEGORY, ROSTER_CATEGORY)
                   or obj.title == old_title or obj.title.startswith(old_title + ' (Part ')
                   or obj.title.startswith(old_title + ' | ')}
        kept, created, updated = [], 0, 0
        for record in records:
            obj = by_title.get(record['title'])
            is_new = obj is None
            if is_new:
                obj = WebResource.objects.create(url=url, **record)
            else:
                changed = obj.content != record['content'] or obj.category != record['category']
                obj.content, obj.category = record['content'], record['category']
                if changed:
                    obj.embedding = None
                # Django update_or_create may omit embedding from update_fields,
                # even when the model's save() cleared it. Persist invalidation
                # explicitly so changed website text never keeps an old vector.
                obj.save(update_fields=['content', 'category', 'embedding', 'last_scraped'])
            kept.append(obj.pk)
            created += int(is_new)
            updated += int(not is_new)
        obsolete = managed - set(kept)
        deleted = WebResource.objects.filter(pk__in=obsolete).delete()[0]
        return {'created': created, 'refreshed': updated, 'obsolete_chunks_removed': deleted}


def run_crawl(command, core_pages, options):
    if connection.vendor != 'postgresql':
        raise CommandError('Run this command through the Docker web service configured for PostgreSQL.')
    if not 1 <= options['max_pages'] <= 200 or not 0 <= options['max_depth'] <= 3 or not 0.25 <= options['delay'] <= 60:
        raise CommandError('Require max-pages 1–200, max-depth 0–3 and delay 0.25–60 seconds.')
    root = Path(settings.BASE_DIR).resolve()
    output = (root / options['output_dir']).resolve()
    if root not in output.parents:
        raise CommandError('Snapshot output must be beneath the project workspace.')
    output.mkdir(parents=True, exist_ok=True)
    # Explicitly endorsed external portals remain seeds, never arbitrary hosts.
    allowed_hosts = sorted({urlsplit(page['url']).hostname for page in core_pages})
    known = {canonical_url(page['url'], allowed_hosts): page for page in core_pages}
    try:
        seeds = [canonical_url(url, allowed_hosts) for url in options['url']] if options['url'] else list(known)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    queue = deque((url, 0) for url in seeds)
    queued, visited = set(seeds), set()
    client = OfficialSiteClient(allowed_hosts, delay=options['delay'])
    report = {'started_at': timezone.now().isoformat(), 'dry_run': options['dry_run'],
              'max_pages': options['max_pages'], 'max_depth': options['max_depth'], 'pages': []}
    successful = 0
    while queue and len(visited) < options['max_pages']:
        requested, depth = queue.popleft()
        if requested in visited:
            continue
        visited.add(requested)
        page = known.get(requested, {'title': urlsplit(requested).path.strip('/').replace('-', ' ').title() or 'SPUS Homepage',
                                     'category': 'Discovered'})
        result = {'requested_url': requested, 'depth': depth}
        command.stdout.write(f'Fetching {requested}')
        try:
            url, html = client.fetch(requested)
            digest = hashlib.sha256(html.encode('utf-8')).hexdigest()
            snapshot = output / f'{digest}.html'
            snapshot.write_text(html, encoding='utf-8')
            admin = urlsplit(url).hostname == 'spus.edu.ph' and urlsplit(url).path.rstrip('/') == '/administrator'
            records, details = extract_records(html, page['title'], page['category'], administration=admin)
            result.update(url=url, sha256=digest, snapshot=str(snapshot.relative_to(root)), records=len(records), extraction=details)
            if not options['dry_run']:
                # Keep the old page recoverable before replacing its crawler records.
                previous = list(WebResource.objects.filter(url=url).values('title', 'category', 'content', 'url', 'last_scraped'))
                archive = output / f'{digest}.previous_records.{timezone.now().strftime("%Y%m%dT%H%M%S%f")}.json'
                archive.write_text(json.dumps(previous, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
                result['database'] = replace_page_resources(url, records, page['title'])
            result['status'] = 'extracted' if options['dry_run'] else 'ingested'
            successful += 1
            command.stdout.write(f'  {len(records)} source records; {len(details.get("incomplete_cards", []))} incomplete cards excluded')
            if options['discover'] and depth < options['max_depth']:
                links = discover_links(html, url, allowed_hosts)
                for link in sorted(links, key=lambda link: (link not in known, link)):
                    # Personnel profiles are redundant with the audited directory;
                    # prefer other institutional pages over hundreds of portraits.
                    if link not in queued and not urlsplit(link).path.startswith('/team/') and len(queued) < 1000:
                        queue.append((link, depth + 1))
                        queued.add(link)
        except Exception as exc:
            # No fetched/error body is ingested. Failure is explicit in the report.
            result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            command.stderr.write(f'  Failed: {result["error"]}')
        report['pages'].append(result)
        (output / 'latest_crawl_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report.update(finished_at=timezone.now().isoformat(), pages_visited=len(visited),
                  successful=successful, queued_remaining=len(queue))
    if successful and not options['dry_run'] and not options['no_embeddings']:
        try:
            from .rag import RAGSearcher
            RAGSearcher().ensure_embeddings()
            report['embeddings'] = 'complete'
        except Exception as exc:
            report['embeddings'] = f'failed: {type(exc).__name__}'
    (output / 'latest_crawl_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    command.stdout.write(f'Report: {output / "latest_crawl_report.json"}')
    if not successful or any(page['status'] == 'failed' for page in report['pages']) or report.get('embeddings', '').startswith('failed'):
        raise CommandError('Crawl had failures; see the report. Failed pages retain their existing knowledge.')
    return None
