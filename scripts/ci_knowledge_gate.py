"""Synthetic ephemeral CI gate. Refuses any non-CI database."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','paulibot.settings')
import django
django.setup()
from django.db import connection,transaction
from django.core.management import call_command
from chatbot.models import FAQ

def run_gate():
    if connection.vendor!='postgresql' or connection.settings_dict['NAME']!='paulibot_ci':
        raise RuntimeError('CI-only fixture refuses this database')
    if FAQ.objects.exists():raise RuntimeError('CI gate requires a fresh empty fixture database')
    # The audit deliberately opens its own READ ONLY transaction. Seed in
    # autocommit first: PostgreSQL cannot switch an already-writing transaction
    # to READ ONLY. Cleanup is constrained to this one ephemeral CI fixture.
    fixture=FAQ.objects.create(question='What is the CI fixture?',answer='Reviewed synthetic CI fixture.',category='CI fixture',embedding=[1.0]+[0.0]*383)
    try:call_command('audit_knowledge',strict=True)
    finally:FAQ.objects.filter(pk=fixture.pk,category='CI fixture').delete()


if __name__=='__main__':run_gate()
