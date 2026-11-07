"""Explicit cache preparation; HTTP workers remain offline and fail readiness closed."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from chatbot.embedding_runtime import EmbeddingRuntime, MODEL_ID


class Command(BaseCommand):
    help = 'Check the pinned MiniLM cache; --download explicitly prepares a fresh cache.'

    def add_arguments(self, parser):
        parser.add_argument('--download', action='store_true')
        parser.add_argument('--verify', action='store_true', help='Load and encode a compatibility probe in this process.')

    def handle(self, *args, **options):
        if options['download']:
            if settings.PAULA_EMBEDDING_MODEL_PATH:
                raise CommandError('Custom model paths must be prepared separately; no download performed.')
            from huggingface_hub import snapshot_download
            snapshot_download(repo_id=MODEL_ID, revision=settings.PAULA_EMBEDDING_REVISION)
        try:
            EmbeddingRuntime.cached_path()
            if options['verify']:
                EmbeddingRuntime().initialize()
        except Exception as exc:
            raise CommandError(f'Embedding cache check failed ({type(exc).__name__}).') from None
        self.stdout.write(self.style.SUCCESS('Pinned embedding cache available' + ('; 384-dimensional encode verified.' if options['verify'] else '.')))
