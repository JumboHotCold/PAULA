"""Read-only deployment gate for PostgreSQL knowledge, separate from unit tests."""
import json
from django.core.management.base import BaseCommand, CommandError
from chatbot.knowledge_audit import audit


class Command(BaseCommand):
    help = 'Audit vector validity, FAQ source self-matches and exact conflicts; --strict enforces a release gate'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true')

    def handle(self, *args, **options):
        report = audit()
        self.stdout.write(json.dumps(report, sort_keys=True))
        invalid = (not sum(row['count'] for row in report['models'].values()) or report['faq_conflicts'] or
                   report['faq_self_match_failures'] or any(row['missing_embeddings'] or row['invalid_embeddings'] or row['zero_vectors']
                                                          for row in report['models'].values()))
        if options['strict'] and invalid:
            raise CommandError('Knowledge release check failed. Review the audit; no records were changed.')
