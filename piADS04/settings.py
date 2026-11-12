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

# Origens (com https://) que podem enviar formularios POST, como o login do /admin/.
# Em producao: https://<nome>.onrender.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# No Render, o endereco publico do servico (ex.: projeto-integrador-time1.onrender.com)
# vem nesta variavel, criada pelo proprio Render. Assim nao da "Bad Request (400)"
# mesmo se ALLOWED_HOSTS e CSRF_TRUSTED_ORIGINS nao forem preenchidos.
RENDER_EXTERNAL_HOSTNAME = config('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

# Atras do proxy do Render, o Django recebe HTTP puro. Este cabecalho (que o proxy
# define) avisa que o acesso original do usuario foi por HTTPS.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')



# --------------------------------------------------
# CONFIGURAÇÕES DE SEGURANÇA
# --------------------------------------------------

if DEBUG:
    # Ambiente local de desenvolvimento
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0

else:
    # Ambiente de produção (Render)
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS inicial de 1 hora
    SECURE_HSTS_SECONDS = 3600
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False


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
    'rest_framework_simplejwt.token_blacklist',
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
    # Serve os arquivos estaticos (admin, Swagger) em producao, sem precisar de Nginx.
    # Precisa vir logo depois do SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
    # Respostas no formato do plano: {"data": ...} e paginacao com "pagination.next" (piADS04/api.py).
    'DEFAULT_RENDERER_CLASSES': (
        'piADS04.api.EnvelopeRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PAGINATION_CLASS': 'piADS04.api.StandardPagination',
    'PAGE_SIZE': 50,
    # Limites de requisicoes: login por IP (forca bruta) e telemetria por placa.
    'DEFAULT_THROTTLE_RATES': {
    'login': config('THROTTLE_LOGIN', default='10/min'),
    'iot': config('THROTTLE_IOT', default='120/min'),
    'password_reset': config('THROTTLE_PASSWORD_RESET', default='5/hour'),
},
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# --- IoT -------------------------------------------------------------------

# Placa sem comunicar ha mais que isso aparece como "sem comunicacao" (online = false).
DEVICE_ONLINE_TOLERANCE_MINUTES = config('DEVICE_ONLINE_TOLERANCE_MINUTES', default=10, cast=int)
# Maximo de itens (leituras + impactos) por lote enviado pela placa.
IOT_MAX_BATCH_ITEMS = config('IOT_MAX_BATCH_ITEMS', default=200, cast=int)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'piADS04 - API de monitoramento de transporte de frutas',
    'DESCRIPTION': 'Temperatura, umidade e impactos durante o transporte de frutas. Rotas da placa: /api/v1/iot/* (cabecalho X-Device-Key).',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'ENUM_NAME_OVERRIDES': {'ConnectionTypeEnum': 'iot.models.Device.CONNECTION_CHOICES'},
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
        # Local: 'prefer' (usa SSL se o servidor tiver). Neon/producao: DB_SSLMODE=require.
        'OPTIONS': {'sslmode': config('DB_SSLMODE', default='prefer')},
        'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
        'CONN_HEALTH_CHECKS':True,
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
# Pasta onde o "collectstatic" junta os arquivos para o WhiteNoise servir (fica fora do Git).
STATIC_ROOT = BASE_DIR / 'staticfiles'
