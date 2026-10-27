"""Audits scraped CSV provenance; deliberately has no import/write mode."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from chatbot.csv_reference_audit import audit_files
from chatbot.models import FAQ, StaffMember, WebResource
from chatbot.personnel import structured_person


class Command(BaseCommand):
    help='Read-only personnel CSV provenance, deduplication and conflict audit. Never imports records.'

    def add_arguments(self,parser):
        parser.add_argument('--directory',default='knowledge_base/office_documents/Administrators_and_College_Faculty_Personel')
        parser.add_argument('--output',help='Optional workspace-relative JSON review report')

    def handle(self,*args,**options):
        if connection.vendor!='postgresql':raise CommandError('Use Docker PostgreSQL for this audit.')
        root=Path(settings.BASE_DIR).resolve();directory=(root/options['directory']).resolve()
        if root not in directory.parents or not directory.is_dir():raise CommandError('CSV directory must exist inside the workspace.')
        paths=list(directory.glob('*.csv'))
        if not paths:raise CommandError('No CSV files found.')
        with transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('SET TRANSACTION READ ONLY')
            people=[]
            for obj in WebResource.objects.filter(category='Website personnel',url='https://spus.edu.ph/administrator/').order_by('pk'):
                person=structured_person(obj)
                if person:people.append({**person,'record_id':obj.pk,'observed_at':obj.last_scraped.isoformat(),'source_url':obj.url})
            staff=[{'record_id':obj.pk,'name':obj.name,'role':obj.position} for obj in StaffMember.objects.order_by('pk')]
            faqs=list(FAQ.objects.order_by('pk').values('id','question','answer','source_type','source_office'))
            report=audit_files(paths,people,staff,faqs)
            report['directory']=str(directory.relative_to(root))
        if options.get('output'):
            output=(root/options['output']).resolve()
            if root not in output.parents:raise CommandError('Report must be inside the workspace.')
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.stdout.write(json.dumps(report['summary'],sort_keys=True))
        self.stdout.write('DRY RUN ONLY: zero database writes; all review flags require manual resolution.')
