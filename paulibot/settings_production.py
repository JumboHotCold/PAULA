"""Opt-in production policy. This does not make an unsupported Django release safe."""
from urllib.parse import urlsplit
from .settings import *  # noqa: F403

DEBUG = False
if SECRET_KEY.startswith('django-insecure') or len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('Production requires a strong DJANGO_SECRET_KEY.')
if not config('POSTGRES_PASSWORD', default=''):
    raise ImproperlyConfigured('Production requires POSTGRES_PASSWORD.')
if not config('ALLOWED_HOSTS', default='') or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Production requires explicit ALLOWED_HOSTS.')
if not PAULA_FRONTEND_ORIGIN or urlsplit(PAULA_FRONTEND_ORIGIN).scheme != 'https':
    raise ImproperlyConfigured('Production requires an HTTPS PAULA_FRONTEND_ORIGIN.')
for _name in ('CORS_ALLOWED_ORIGINS', 'CSRF_TRUSTED_ORIGINS'):
    _origins = config(_name, default='')
    if not _origins:
        raise ImproperlyConfigured(f'Production requires explicit {_name}.')
    for _origin in globals()[_name]:
        _parsed = urlsplit(_origin)
        if _parsed.scheme != 'https' or not _parsed.netloc or _parsed.path or _parsed.query or _parsed.fragment:
            raise ImproperlyConfigured(f'{_name} must contain HTTPS origins only.')

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=3600, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Enable only behind a trusted proxy that strips client-supplied forwarded headers.
if config('PAULA_TRUST_HTTPS_PROXY', default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
