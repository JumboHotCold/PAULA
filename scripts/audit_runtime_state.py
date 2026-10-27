"""Read-only runtime/dependency/office-knowledge audit through the Docker web service.

Prints no credentials, account records, or document answers. Does not ingest data.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paulibot.settings')

CODE_FILES = (
    'chatbot/grounding.py', 'chatbot/intents.py', 'chatbot/logic.py', 'chatbot/rag.py',
    'chatbot/views.py', 'chatbot/templates/chatbot/chat.html', 'paulibot/settings.py',
    'frontend/src/App.jsx', 'frontend/src/api/chatApi.js',
    'frontend/src/components/MapModule.jsx', 'frontend/vite.config.js',
    'docker-compose.yml', 'scripts/start_workspace_backend.ps1',
    'chatbot/test_grounding.py', 'chatbot/test_intents.py',
    'scripts/evaluate_grounding.py', 'scripts/reocr_office_documents.py',
    'scripts/reconcile_ocr_review.py', 'scripts/audit_runtime_state.py',
    'PAULA_SYSTEM_UNDERSTANDING_REPORT.md', 'PAULA_RESPONSE_GROUNDING.md',
    'knowledge_base/office_documents/Registrar/Registrar_knowledge.json',
    'knowledge_base/office_documents/PBMO/PBMO_knowledge.json',
    'knowledge_base/office_documents/extracted/REGISTRAR_PDF_REVIEW.md',
    'knowledge_base/office_documents/extracted/ocr_review_2026-10-27/REVIEW_REPORT.md',
    'knowledge_base/office_documents/extracted/ocr_review_2026-10-27/MANUAL_REVIEW_NOTES.md',
)


def main():
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection, transaction
    from django.db.migrations.executor import MigrationExecutor
    from packaging.requirements import Requirement
    from chatbot.models import FAQ, Location, StaffMember, WebResource
    from chatbot.views import bot

    if connection.vendor != 'postgresql':
        raise RuntimeError('Audit requires the configured Docker PostgreSQL database.')
    dependencies = []
    for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        requirement = Requirement(line)
        try:
            installed = importlib.metadata.version(requirement.name)
            status = 'matches' if installed in requirement.specifier else 'version_mismatch'
        except importlib.metadata.PackageNotFoundError:
            installed, status = None, 'missing'
        dependencies.append({'package': requirement.name, 'installed': installed,
                             'required': str(requirement.specifier), 'status': status})

    knowledge = []
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            vector_extension = cursor.fetchone()[0]
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        missing_vectors = {model.__name__: model.objects.filter(embedding__isnull=True).count()
                           for model in (FAQ, Location, StaffMember, WebResource)}
        for office in ('Registrar', 'PBMO'):
            source = ROOT / 'knowledge_base' / 'office_documents' / office / f'{office}_knowledge.json'
            items = json.loads(source.read_text(encoding='utf-8'))['items']
            for number, item in enumerate(items, 1):
                records = list(FAQ.objects.filter(source_office=office, question__in=[
                    item['question'], f'[{office}] {item["question"]}']))
                if not records:
                    status = 'missing_from_database'
                elif len(records) > 1:
                    status = 'multiple_matching_records'
                elif records[0].source_type != 'office':
                    status = 'source_metadata_differs'
                elif ' '.join(records[0].answer.split()) != ' '.join(item['answer'].split()):
                    status = 'answer_differs'
                else:
                    status = 'matches_existing_json'
                knowledge.append({'office': office, 'item': number,
                                  'question': item['question'], 'status': status})

    result = {
        'source_hashes': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in CODE_FILES},
        'database': {'vendor': connection.vendor, 'driver': connection.Database.__name__, 'vector_extension': vector_extension,
                     'pending_migrations': [f'{migration.app_label}.{migration.name}' for migration, _ in pending],
                     'missing_embeddings': missing_vectors},
        'dependencies': dependencies, 'office_knowledge_comparison': knowledge,
        'settings': {'debug': settings.DEBUG, 'cosine_threshold': settings.RAG_MAX_COSINE_DISTANCE,
                     'groq_model': settings.GROQ_MODEL,
                     'groq_key_present': bool(settings.GROQ_API_KEY),
                     'openai_key_present': bool(settings.OPENAI_API_KEY)},
        'provider_clients': {'groq': bot.client is not None,
                             'openai': bot.openai_client is not None,
                             'gemini': bot.gemini_model is not None},
        'ocr_outputs_are_review_artifacts_not_automatic_ingestion': True,
    }
    ocr_root = ROOT / 'knowledge_base/office_documents/extracted/ocr_review_2026-10-27'
    ocr_digest = hashlib.sha256()
    ocr_files = sorted(path for path in ocr_root.rglob('*') if path.is_file())
    for path in ocr_files:
        ocr_digest.update(path.relative_to(ocr_root).as_posix().encode('utf-8'))
        ocr_digest.update(hashlib.sha256(path.read_bytes()).digest())
    result['ocr_artifacts'] = {'files': len(ocr_files), 'combined_sha256': ocr_digest.hexdigest()}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
