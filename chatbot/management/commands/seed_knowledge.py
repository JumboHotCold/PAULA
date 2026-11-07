"""
Management command to seed the Knowledge Base tables from the legacy data.py file.
This migrates the hardcoded data into the PostgreSQL database so Faculty can manage it.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from chatbot.models import Location, StaffMember, FAQ, WebResource
from chatbot.data import LOCATIONS, STAFF, FAQS


class Command(BaseCommand):
    help = 'Seed the Knowledge Base tables with initial data from data.py'

    @transaction.atomic
    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('PAULA requires PostgreSQL.')
        if any(model.objects.exists() for model in (Location, StaffMember, FAQ, WebResource)):
            raise CommandError('Legacy seed is allowed only on an empty knowledge database. Existing facts were preserved. Use reviewed ingestion instead.')
        self.stdout.write(self.style.WARNING('Legacy starter data is not the current reviewed knowledge base. Verify all facts before use.'))
        self.stdout.write('Seeding empty knowledge database...')

        # Seed Locations
        for key, data in LOCATIONS.items():
            obj, created = Location.objects.update_or_create(
                name=data['name'],
                defaults={
                    'description': data['description'],
                    'map_available': data.get('map_available', False),
                }
            )
            status = "CREATED" if created else "UPDATED"
            self.stdout.write(f"  [{status}] Location: {obj.name}")

        # Seed Staff
        for key, data in STAFF.items():
            obj, created = StaffMember.objects.update_or_create(
                name=data['name'],
                defaults={
                    'position': data['position'],
                    'office': data['office'],
                }
            )
            status = "CREATED" if created else "UPDATED"
            self.stdout.write(f"  [{status}] Staff: {obj.name}")

        # Seed FAQs
        for faq_data in FAQS:
            defaults = {
                'category': faq_data['category'],
                'answer': faq_data['answer'],
            }
            if 'source_type' in faq_data:
                defaults['source_type'] = faq_data['source_type']
            if 'source_office' in faq_data:
                defaults['source_office'] = faq_data['source_office']
            obj, created = FAQ.objects.update_or_create(
                question=faq_data['question'],
                defaults=defaults
            )
            status = "CREATED" if created else "UPDATED"
            self.stdout.write(f"  [{status}] FAQ: {obj.question}")

        self.stdout.write(self.style.SUCCESS("\nKnowledge Base seeded successfully!"))
