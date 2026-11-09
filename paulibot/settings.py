"""
PauliBot Django Settings
=========================
Author: Senior Full-Stack Developer & DevOps Engineer
Purpose: Django configuration for production-ready PostgreSQL deployment

Security Notes:
- SECRET_KEY loaded from environment variables
- DEBUG controlled by environment
- Passwords hashed with PBKDF2 (600,000 iterations)
"""

from pathlib import Path
import os
from decouple import config
from django.templatetags.static import static
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# Load secret key from environment variable
SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-mock-key-for-paulibot-mvp')

# Gemini API Key (Phase 1 — kept for handbook ingestion scripts)
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')

# Groq API Key (Phase 2 — Live Chat AI Engine)
GROQ_API_KEY = config('GROQ_API_KEY', default='')
GROQ_MODEL = config('GROQ_MODEL', default='openai/gpt-oss-20b')
PAULA_GROQ_ENABLED = config('PAULA_GROQ_ENABLED', default=True, cast=bool)
PAULA_OPENAI_ENABLED = config('PAULA_OPENAI_ENABLED', default=False, cast=bool)
PAULA_GENERATION_DEADLINE_SECONDS = min(8.0, max(.01, config('PAULA_GENERATION_DEADLINE_SECONDS', default=4.0, cast=float)))
PAULA_PROVIDER_CALL_TIMEOUT_SECONDS = min(4.0, max(.01, config('PAULA_PROVIDER_CALL_TIMEOUT_SECONDS', default=3.0, cast=float)))
PAULA_EMBEDDING_REVISION = config('PAULA_EMBEDDING_REVISION', default='1110a243fdf4706b3f48f1d95db1a4f5529b4d41')
PAULA_EMBEDDING_MODEL_PATH = config('PAULA_EMBEDDING_MODEL_PATH', default='')
PAULA_RUNTIME_DIR = config('PAULA_RUNTIME_DIR', default='/tmp/paula-runtime')
PAULA_BUILD_COMMIT = config('PAULA_BUILD_COMMIT', default='')

# OpenAI API Key (Fallback AI Engine)
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# Conservative relevance gate, applied to raw cosine distance before ranking.
# Tune using labeled SPUS evaluation queries; this is not a probability score.
RAG_MAX_COSINE_DISTANCE = config('RAG_MAX_COSINE_DISTANCE', default=0.45, cast=float)

# Debug mode controlled by environment
DEBUG = config('DEBUG', default=False, cast=bool)

# React and Django admin are separate interfaces during Vite development.
PAULA_FRONTEND_ORIGIN = (config('PAULA_FRONTEND_ORIGIN', default='') or ('http://localhost:5173' if DEBUG else '')).rstrip('/')

# Allowed hosts from environment
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    # django-unfold must be before django.contrib.admin
    'unfold',
    'unfold.contrib.filters',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'chatbot',
]

# =============================================================================
# UNFOLD ADMIN THEME CONFIGURATION (SPUS Branding)
# =============================================================================

UNFOLD = {
    "SITE_TITLE": "PAULA Administration",
    "SITE_HEADER": "PAULA",
    "SITE_SUBHEADER": "Saint Paul University Surigao",
    "SITE_LOGO": lambda request: static('chatbot/images/SPUS-Logo1.webp'),
    "SITE_URL": lambda request: django_settings.PAULA_FRONTEND_ORIGIN or '/',
    "SITE_FAVICONS": [{"rel": "icon", "href": lambda request: static('chatbot/images/SPUS-Logo1.webp')}],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "#f0fdf4",
            "100": "#dcfce7",
            "200": "#bbf7d0",
            "300": "#86efac",
            "400": "#fcd108",
            "500": "#deb402",
            "600": "#215a2e",
            "700": "#005301",
            "800": "#052416",
            "900": "#041a10",
            "950": "#020d08",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "PAULA Workspace",
                "items": [
                    {"title": "Institutional Analytics", "link": lambda request: f'{django_settings.PAULA_FRONTEND_ORIGIN}/admin', "icon": "analytics", "permission": lambda request: request.user.is_superuser},
                    {"title": "Assistant & Campus Map", "link": lambda request: f'{django_settings.PAULA_FRONTEND_ORIGIN}/', "icon": "map"},
                ],
            },
            {
                "title": "Knowledge Base",
                "icon": "library_books",
                "items": [
                    {"title": "Locations", "link": "/admin/chatbot/location/", "icon": "place"},
                    {"title": "Staff Members", "link": "/admin/chatbot/staffmember/", "icon": "badge"},
                    {"title": "FAQs", "link": "/admin/chatbot/faq/", "icon": "help"},
                ],
            },
            {
                "title": "Chat Management",
                "icon": "chat",
                "items": [
                    {"title": "Chat Histories", "link": "/admin/chatbot/chathistory/", "icon": "history"},
                    {"title": "Conversations", "link": "/admin/chatbot/conversation/", "icon": "forum"},
                ],
            },
            {
                "title": "Users & Auth",
                "icon": "people",
                "items": [
                    {"title": "Users", "link": "/admin/chatbot/customuser/", "icon": "person"},
                    {"title": "Groups", "link": "/admin/auth/group/", "icon": "group"},
                ],
            },
        ],
    },
}

MIDDLEWARE = [
    'chatbot.performance.RequestTimingMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS support
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'paulibot.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'paulibot.wsgi.application'

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# PostgreSQL configuration with environment variables
# PostgreSQL/pgvector is required. Fail explicitly rather than reading another DB.
USE_POSTGRES = config('USE_POSTGRES', default=True, cast=bool)
if not USE_POSTGRES:
    raise ImproperlyConfigured('PAULA requires PostgreSQL. Set USE_POSTGRES=true.')

if USE_POSTGRES:
    # PostgreSQL (for Docker/Production)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('POSTGRES_DB', default='paulibot_db'),
            'USER': config('POSTGRES_USER', default='paulibot_user'),
            'PASSWORD': config('POSTGRES_PASSWORD', default='password'),
            'HOST': config('POSTGRES_HOST', default='localhost'),
            'PORT': config('POSTGRES_PORT', default='5432'),
            'OPTIONS': {'connect_timeout': max(1, config('POSTGRES_CONNECT_TIMEOUT', default=3, cast=int))},
        }
    }

# =============================================================================
# AUTHENTICATION CONFIGURATION
# =============================================================================

# Custom user model
AUTH_USER_MODEL = 'chatbot.CustomUser'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'chatbot.backends.StudentIDBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Session configuration
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG  # Use HTTPS in production
SESSION_COOKIE_SAMESITE = 'Lax'

# CSRF configuration
CSRF_COOKIE_HTTPONLY = False  # Allow JavaScript to read CSRF token
CSRF_COOKIE_SECURE = not DEBUG  # Use HTTPS in production
CSRF_COOKIE_SAMESITE = 'Lax'

# =============================================================================
# REST FRAMEWORK CONFIGURATION
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # Allow guest access
    ],
}

# =============================================================================
# CORS CONFIGURATION
# =============================================================================

# Allow frontend to communicate with backend (adjust for production)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",   # React dev server (Vite)
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins for React SPA
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]

# Explicit origins for a hosted frontend; local development defaults stay intact.
for _name in ('CORS_ALLOWED_ORIGINS', 'CSRF_TRUSTED_ORIGINS'):
    _configured = config(_name, default=None)
    if _configured is not None:
        globals()[_name] = [value.strip() for value in _configured.split(',') if value.strip()]

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES CONFIGURATION
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# =============================================================================
# DEFAULT FIELD CONFIGURATION
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'paula_console': {'class': 'logging.StreamHandler'}},
    'loggers': {'paula.performance': {'handlers': ['paula_console'], 'level': 'INFO', 'propagate': False}},
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
