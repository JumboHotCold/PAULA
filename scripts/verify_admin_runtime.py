"""Read-only Docker admin render, asset delivery, readiness, and data checks.

Run with Docker's manage.py shell; never creates or logs into an account.
"""
import json
from html.parser import HTMLParser
from pathlib import Path
import runpy
from urllib.parse import urlparse
from urllib.request import urlopen

from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import connection, transaction
from django.test import RequestFactory
from chatbot.models import CustomUser


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag in ('img', 'script', 'link'):
            for key in ('src', 'href'):
                value = attrs.get(key, '')
                if value.startswith('/static/'):
                    self.paths.add(value)


def main():
    base = 'http://127.0.0.1:8000'
    with urlopen(base + '/api/health/ready', timeout=3) as response:
        ready = json.load(response)
    assert ready['ready'] and ready['ready_workers'] == ready['expected_workers']
    parser = Assets()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        user = CustomUser.objects.filter(is_active=True, is_staff=True, is_superuser=True).first()
        assert user is not None, 'No existing active administrator available for read-only rendering'
        request = RequestFactory().get('/admin/')
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = admin.site.index(request)
        response.render()
        assert response.status_code == 200
        html = response.content.decode()
        assert 'Institutional Analytics' in html
        assert 'src="/static/chatbot/images/SPUS-Logo1.' in html
        assert 'src="chatbot/images/' not in html
        parser.feed(html)
    with urlopen(base + '/admin/login/', timeout=5) as response:
        parser.feed(response.read().decode())
    assets = []
    for path in sorted(parser.paths):
        assert not urlparse(path).netloc
        with urlopen(base + path, timeout=5) as response:
            assert response.status == 200
            assert response.headers['Content-Type'].split(';')[0] != 'text/html'
            assets.append({'path': path, 'status': response.status, 'content_type': response.headers['Content-Type']})
    report = {'all_workers_ready': True, 'ready_workers': ready['ready_workers'],
              'admin_index_rendered_read_only': True, 'analytics_link_present': True,
              'assets': assets, 'assets_passed': len(assets),
              'notes': 'Existing administrator used only for RequestFactory read-only rendering. No HTTP login, new account, session persistence or database mutations.'}
    Path('PAULA_ADMIN_RUNTIME_VERIFICATION.json').write_text(json.dumps(report, indent=2))
    proof_path = Path('PAULA_ADMIN_DATA_INTEGRITY.json')
    proof = json.loads(proof_path.read_text())
    proof['after'] = runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()
    proof['unchanged'] = proof['before'] == proof['after']
    proof_path.write_text(json.dumps(proof, indent=2))
    assert proof['unchanged'], 'Knowledge/history changed; inspect audit before attributing concurrent changes'
    print(json.dumps({'ready_workers': ready['ready_workers'], 'assets_passed': len(assets), 'data_unchanged': proof['unchanged']}))


main()
