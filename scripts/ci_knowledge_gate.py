"""Synthetic, transaction-rolled-back CI gate. Refuses any non-CI database."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','paulibot.settings')
import django
django.setup()
from django.db import connection,transaction
from django.core.management import call_command
from chatbot.models import FAQ

assert connection.vendor=='postgresql' and connection.settings_dict['NAME']=='paulibot_ci','CI-only fixture refuses this database'
with transaction.atomic():
    FAQ.objects.create(question='What is the CI fixture?',answer='Reviewed synthetic CI fixture.',category='CI fixture',embedding=[1.0]+[0.0]*383)
    call_command('audit_knowledge',strict=True)
    transaction.set_rollback(True)
