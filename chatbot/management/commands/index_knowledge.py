"""Review missing vectors by default; fill only missing vectors with --apply."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from chatbot.models import FAQ, Location, StaffMember, WebResource
from chatbot.rag import RAGSearcher


class Command(BaseCommand):
    help = 'Audit missing knowledge vectors; use --apply for explicit indexing maintenance'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Fill missing vectors only; never overwrite facts or existing vectors')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('PAULA knowledge indexing requires PostgreSQL.')
        missing = {model.__name__: model.objects.filter(embedding__isnull=True).count()
                   for model in (FAQ, Location, StaffMember, WebResource)}
        result = {'dry_run': not options['apply'], 'missing': missing}
        if options['apply'] and any(missing.values()):
            result.update(RAGSearcher().ensure_embeddings())
        self.stdout.write(json.dumps(result, sort_keys=True))
