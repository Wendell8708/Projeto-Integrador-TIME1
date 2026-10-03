"""
Configuracoes do projeto piADS04 (monitoramento de temperatura e umidade
no transporte de frutas).

Tudo o que muda de uma maquina para outra, ou que e segredo, vem do arquivo
.env (lido pelo python-decouple). Veja o .env.example para a lista de variaveis.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent


# --- Seguranca -------------------------------------------------------------

SECRET_KEY = config('SECRET_KEY')

# Seguro por padrao: se a variavel faltar, DEBUG fica desligado.
# Em desenvolvimento, coloque DEBUG=True no .env.
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())


# --- Apps ------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Terceiros
    'rest_framework',
    'rest_framework_simplejwt',
    'django_filters',
    'drf_spectacular',
    'corsheaders',

    # Apps do projeto
    'usuarios',
    'dominio',
    'transporte',
    'iot',
    'alertas',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',

    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Origens do frontend (React) autorizadas a chamar a API.
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000',
    cast=Csv(),
)


# --- Django REST Framework + JWT -------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    # Permissoes nativas do Django (model permissions), com "ver" tambem
    # protegido. Os grupos recebem essas permissoes (comando criar_grupos).
    'DEFAULT_PERMISSION_CLASSES': (
        'usuarios.permissions.PermissaoPorModelo',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'piADS04 - API de monitoramento de transporte de frutas',
    'DESCRIPTION': 'Temperatura e umidade durante o transporte, da fazenda ao centro de distribuicao.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}


ROOT_URLCONF = 'piADS04.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'piADS04.wsgi.application'


# --- Banco de dados (PostgreSQL) -------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# --- Validacao de senhas ---------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# --- Internacionalizacao ---------------------------------------------------

LANGUAGE_CODE = 'pt-br'

# Fuso do Vale do Sao Francisco (Petrolina/Juazeiro, UTC-3, sem horario de verao).
# O banco guarda tudo em UTC (USE_TZ=True); este fuso so afeta a exibicao.
TIME_ZONE = 'America/Recife'

USE_I18N = True

USE_TZ = True


# --- Arquivos estaticos ----------------------------------------------------

STATIC_URL = 'static/'
