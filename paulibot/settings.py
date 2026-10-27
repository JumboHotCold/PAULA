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
GROQ_MODEL = config('GROQ_MODEL', default='llama-3.3-70b-versatile')

# OpenAI API Key (Fallback AI Engine)
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# Conservative relevance gate, applied to raw cosine distance before ranking.
# Tune using labeled SPUS evaluation queries; this is not a probability score.
RAG_MAX_COSINE_DISTANCE = config('RAG_MAX_COSINE_DISTANCE', default=0.45, cast=float)

# Debug mode controlled by environment
DEBUG = config('DEBUG', default=False, cast=bool)

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
    "SITE_TITLE": "PauliBot Admin",
    "SITE_HEADER": "PauliBot",
    "SITE_SUBHEADER": "Saint Paul University Surigao",
    "SITE_LOGO": "chatbot/images/SPUS-Logo1.webp",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "#f0fdf4",
            "100": "#dcfce7",
            "200": "#bbf7d0",
            "300": "#86efac",
            "400": "#4ade80",
            "500": "#0A4D2E",
            "600": "#083d25",
            "700": "#06301d",
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
    'django.middleware.security.SecurityMiddleware',
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
# Falls back to SQLite3 for local development if PostgreSQL is not configured
USE_POSTGRES = config('USE_POSTGRES', default='false', cast=str).lower() == 'true'

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
        }
    }
else:
    # SQLite3 (for local development without Docker)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
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

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# =============================================================================
# DEFAULT FIELD CONFIGURATION
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
