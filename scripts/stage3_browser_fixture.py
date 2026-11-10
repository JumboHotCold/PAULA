"""Create only public/synthetic browser fixtures in the isolated CI database."""
import json
from pathlib import Path
from django.db import connection
from chatbot.models import FAQ,CustomUser


def export_public():
    rows=list(FAQ.objects.filter(question__icontains='programs are offered at SPUS').values('question','answer','category','source_type','source_office','embedding'))
    if not rows:raise RuntimeError('Public program fixture source was not found')
    def encode(value):return value.tolist() if hasattr(value,'tolist') else value
    Path('artifacts/stage3/browser_fixture.json').write_text(json.dumps(rows,default=encode),encoding='utf-8')
    print('Exported existing public program source; no application data changed.')


def seed_ci():
    if connection.settings_dict['NAME']!='paulibot_ci':raise RuntimeError('Refusing browser fixtures outside isolated CI database')
    for row in json.loads(Path('artifacts/stage3/browser_fixture.json').read_text(encoding='utf-8')):FAQ.objects.create(**row)
    FAQ.objects.create(question='What is the fixture president?',answer='Reviewed synthetic fixture role used only for automated tests.',
        category='CI fixture',source_type='curated',embedding=[1.0]+[0.0]*383)
    CustomUser.objects.create_user(username='stage3-browser',student_id='C-2099-0001',password='Synthetic-Stage3-Only-2026!')
    print('Seeded temporary CI-only browser fixtures.')
