"""Import the supplied About SPUS document without replacing existing knowledge."""
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from chatbot.models import FAQ


SOURCE = 'knowledge_base/About_SPUS/About SPUS.txt'


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def document_entries(text):
    """Keep source wording; split at explicit headings and paragraph boundaries."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    headings = ('About us', 'VISION-MISSION', 'PAULINIAN CORE VALUES', 'Why Choose SPUS?')
    starts = []
    for heading in headings:
        matches = list(re.finditer(r'^' + re.escape(heading) + r'\s*$', text, re.MULTILINE))
        if len(matches) != 1:
            raise CommandError(f'Expected exactly one heading: {heading}')
        starts.append(matches[0].start())
    if starts != sorted(starts):
        raise CommandError('Source headings are out of order')
    blocks = [text[start:end].strip() for start, end in zip(starts, starts[1:] + [len(text)])]
    overview, vision_mission, values, reasons = blocks
    paragraphs = [part.strip() for part in overview.split('\n\n') if part.strip()]
    campuses = [part for part in paragraphs if part.startswith('It has two campuses:')]
    history = [part for part in paragraphs if part.startswith('St. Paul University Surigao traces its roots')]
    if len(campuses) != 1 or len(history) != 1:
        raise CommandError('Cannot identify the campus and history paragraphs safely')
    return [
        ('What is Saint Paul University Surigao (SPUS)?', overview),
        ('What is SPUS?', paragraphs[0].removeprefix('About us\n').strip()),
        ('What is the SPUS Vision and Mission?', vision_mission),
        ('What are the complete definitions of the Paulinian core values at SPUS?', values),
        ('Why choose SPUS? What makes SPUS special?', reasons),
        ('What are the SPUS campuses and what does each campus house?', campuses[0]),
        ('What is the early history of SPUS?', history[0]),
    ]


class Command(BaseCommand):
    help = 'Add missing About SPUS FAQ topics; preserve existing records and embeddings'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--report', default='PAULA_ABOUT_SPUS_INGESTION.json')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Run through the Docker web service using PostgreSQL')
        path = Path(settings.BASE_DIR) / SOURCE
        try:
            raw = path.read_bytes()
            text = raw.decode('utf-8-sig')
        except (OSError, UnicodeError) as exc:
            raise CommandError('Cannot read the source as UTF-8') from exc
        entries = document_entries(text)
        existing = list(FAQ.objects.order_by('pk'))
        plan = []
        for question, answer in entries:
            # Reuse equivalent complete entries, not incidental paragraph matches
            # inside broad documents: focused topics need their own embedding.
            matches = [obj for obj in existing if normalized(obj.answer) == normalized(answer)]
            stored_question = f'[About SPUS.txt] {question}'
            if matches:
                plan.append({'question': question, 'action': 'reuse', 'record_ids': [obj.pk for obj in matches]})
            elif any(normalized(obj.question) in (normalized(question), normalized(stored_question)) for obj in existing):
                raise CommandError(f'Existing question has different content; review manually: {question}')
            else:
                plan.append({'question': question, 'action': 'create', 'answer': answer, 'stored_question': stored_question})

        report = {
            'source_path': SOURCE,
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'encoding': 'UTF-8',
            'source_type': 'curated',
            'verification': 'User-supplied document; not independently verified against the live website',
            'dry_run': options['dry_run'],
            'entries': plan,
        }
        if not options['dry_run']:
            pending = [item for item in plan if item['action'] == 'create']
            if pending:
                # Use the exact embedding format/model already used by RAG.
                # Only this import's new records are encoded; no global backfill.
                from chatbot.embedding_runtime import runtime
                model = runtime.get_model()
                vectors = model.encode([
                    f"FAQ about About SPUS: {item['stored_question']} - {item['answer']}"
                    for item in pending
                ]).tolist()
                if len(vectors) != len(pending) or any(
                        len(vector) != 384 or not all(math.isfinite(value) for value in vector)
                        for vector in vectors):
                    raise CommandError('Invalid embedding output; no records created')
                with transaction.atomic():
                    # Serialize repeat/concurrent invocations of this importer.
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [7842011906])
                    for item, vector in zip(pending, vectors):
                        matches = list(FAQ.objects.filter(question=item['stored_question']))
                        if matches:
                            if any(normalized(obj.answer) != normalized(item['answer']) for obj in matches):
                                raise CommandError('Source changed during import; rolled back')
                            item.update(action='reuse', record_ids=[obj.pk for obj in matches])
                            continue
                        obj = FAQ.objects.create(
                            category='About SPUS', question=item['stored_question'],
                            answer=item['answer'], source_type='curated', embedding=vector,
                        )
                        item.update(record_ids=[obj.pk], embedding_dimensions=len(vector))
        for item in plan:
            item.pop('answer', None)
            item.pop('stored_question', None)
        report['created'] = sum(item['action'] == 'create' for item in plan) if not options['dry_run'] else 0
        report['would_create'] = sum(item['action'] == 'create' for item in plan)
        report['reused'] = sum(item['action'] == 'reuse' for item in plan)
        report_path = Path(settings.BASE_DIR) / options['report']
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(json.dumps(report, ensure_ascii=True))
