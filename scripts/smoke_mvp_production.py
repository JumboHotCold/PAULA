"""Isolated HTTPS-policy WSGI smoke against existing read-only guest knowledge.

Run inside Docker. No migrations, new users, chat persistence or live providers.
Uses a temporary local Gunicorn process and a test-only signing key.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler


def main():
    report = {'checks': {}, 'passed': False, 'mode': 'isolated Gunicorn, DEBUG=false, HTTPS proxy policy, live PostgreSQL and offline cached MiniLM, providers disabled'}
    env = dict(os.environ, DJANGO_SETTINGS_MODULE='paulibot.settings_production', DEBUG='false',
               DJANGO_SECRET_KEY='mvp-smoke-only-do-not-deploy-' + 'x' * 56,
               ALLOWED_HOSTS='localhost,127.0.0.1', PAULA_FRONTEND_ORIGIN='https://paula.test',
               CORS_ALLOWED_ORIGINS='https://paula.test', CSRF_TRUSTED_ORIGINS='https://paula.test',
               PAULA_TRUST_HTTPS_PROXY='true', PAULA_GROQ_ENABLED='false', PAULA_OPENAI_ENABLED='false',
               GROQ_API_KEY='', OPENAI_API_KEY='', GEMINI_API_KEY='')
    with tempfile.TemporaryDirectory(prefix='paula-mvp-smoke-') as root:
        env['PAULA_RUNTIME_DIR'] = root
        with open(Path(root) / 'gunicorn.log', 'w') as log:
            process = subprocess.Popen(['gunicorn', 'paulibot.wsgi:application', '--config', 'python:paulibot.gunicorn_conf',
                                        '--bind', '127.0.0.1:8001', '--workers', '1', '--timeout', '150'],
                                       env=env, stdout=log, stderr=log, start_new_session=True)
            def request(path, payload=None):
                headers = {'X-Forwarded-Proto': 'https'}
                if payload is not None:
                    headers['Content-Type'] = 'application/json'
                return urlopen(Request('http://127.0.0.1:8001' + path,
                                       data=json.dumps(payload).encode() if payload is not None else None,
                                       headers=headers), timeout=15)
            try:
                started = time.perf_counter()
                deadline = time.monotonic() + 200
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Isolated Gunicorn exited before readiness')
                    try:
                        with request('/api/health/ready') as response:
                            state = json.load(response)
                        if state['ready'] and state['database_ready'] and state['index_complete']:
                            break
                    except (HTTPError, URLError, TimeoutError):
                        pass
                    time.sleep(1)
                else:
                    raise RuntimeError('Production-policy readiness deadline exceeded')
                report['readiness_ms'] = round((time.perf_counter() - started) * 1000, 2)
                report['readiness'] = state
                report['checks']['postgres_and_all_vectors_ready'] = True
                with request('/api/session') as response:
                    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
                    assert response.headers.get('Strict-Transport-Security')
                    cookies = response.headers.get_all('Set-Cookie') or []
                    assert any('csrftoken=' in value and 'Secure' in value and 'SameSite=Lax' in value for value in cookies)
                report['checks']['https_headers_and_secure_csrf_cookie'] = True
                for query in ('What programs are offered?', 'Who is the ICT Director and CEIT Dean?',
                              'How are announcements and promotional materials broadcast across the SPUS campus?'):
                    with request('/api/chat', {'message': query, 'mode': 'guest'}) as response:
                        data = json.load(response)
                    assert data['sources'] and data['saved'] is False and data['conversation_id'] is None
                report['checks']['grounded_faq_compound_and_semantic_without_provider'] = True
                with request('/static/unfold/css/styles.css') as response:
                    assert response.status == 200 and 'text/css' in response.headers.get('Content-Type', '')
                report['checks']['admin_static_css_available'] = True
                with request('/admin/login/') as response:
                    assert response.status == 200
                report['checks']['admin_login_template_rendered'] = True
                with request('/api/chat', {'message': 'What is quantum entanglement?', 'mode': 'guest'}) as response:
                    data = json.load(response)
                assert not data['sources']
                report['checks']['unknown_request_does_not_fabricate'] = True
                try:
                    with request('/api/chat', []) as response:
                        raise AssertionError('Invalid JSON object was accepted')
                except HTTPError as exc:
                    assert exc.code == 400 and json.load(exc)['error_code'] == 'invalid_request'
                report['checks']['malformed_request_safe'] = True
                class NoRedirect(HTTPRedirectHandler):
                    def redirect_request(self, *args, **kwargs):
                        return None
                try:
                    build_opener(NoRedirect).open('http://127.0.0.1:8001/api/session', timeout=5)
                    raise AssertionError('Plain HTTP was not redirected')
                except HTTPError as exc:
                    assert exc.code == 301 and exc.headers.get('Location', '').startswith('https://')
                report['checks']['plain_http_redirects_to_https'] = True
                report['passed'] = True
            except Exception as exc:
                report['error_type'] = type(exc).__name__
                # Do not publish raw exceptions, process environment or cookies.
                raise
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
                Path('PAULA_MVP_PRODUCTION_SMOKE.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
