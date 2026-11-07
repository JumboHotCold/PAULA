"""Admin assets must work under Gunicorn, including with DEBUG disabled."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.core.wsgi import get_wsgi_application
from django.test import RequestFactory, SimpleTestCase, override_settings


class AdminAssetTests(SimpleTestCase):
    def test_admin_login_has_absolute_static_assets_and_branding(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PAULA Administration')
        self.assertContains(response, '/static/unfold/css/styles.')
        self.assertContains(response, '/static/chatbot/images/SPUS-Logo1.')
        self.assertContains(response, 'alt="St. Paul University Surigao logo"')
        self.assertNotContains(response, 'src="chatbot/images/')

    def test_admin_requires_authentication(self):
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/admin/login/'))

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'], WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False)
    def test_collected_static_files_served_without_debug(self):
        app = get_wsgi_application()
        for path, content_type in (
            ('/static/unfold/css/styles.css', 'text/css'),
            ('/static/unfold/js/app.js', 'javascript'),
            ('/static/unfold/fonts/material-symbols/styles.css', 'text/css'),
            ('/static/chatbot/images/SPUS-Logo1.webp', 'image/webp'),
        ):
            with self.subTest(path=path):
                result = {}
                def start_response(status, headers):
                    result.update(status=status, headers=dict(headers))
                response = app(RequestFactory().get(path).environ, start_response)
                try:
                    self.assertTrue(result['status'].startswith('200 '), result)
                    self.assertIn(content_type, result['headers']['Content-Type'])
                    self.assertTrue(next(iter(response)))
                finally:
                    response.close()

    @override_settings(PAULA_FRONTEND_ORIGIN='https://paula.example.edu')
    def test_workspace_links_preserve_analytics(self):
        request = RequestFactory().get('/admin/login/')
        request.user = AnonymousUser()
        context = admin.site.each_context(request)
        self.assertEqual(context['site_url'], 'https://paula.example.edu')
        items = settings.UNFOLD['SIDEBAR']['navigation'][0]['items']
        self.assertEqual(items[0]['link'](request), 'https://paula.example.edu/admin')
        self.assertEqual(items[1]['link'](request), 'https://paula.example.edu/')

    def test_unknown_static_path_is_not_served(self):
        response = self.client.get('/static/not-a-paula-public-asset.css')
        self.assertEqual(response.status_code, 404)
