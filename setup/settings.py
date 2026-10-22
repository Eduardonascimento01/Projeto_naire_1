from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured

# Constrói os caminhos dentro do projeto, por exemplo: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in {'true', '1', 'yes'}
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY fora do modo DEBUG.')
    SECRET_KEY = 'django-insecure-local-development-only-key'

# CHAVE CRIPTOGRÁFICA (Protege CPFs e dados sensíveis gerados pelo django-cryptography)
CRYPTOGRAPHY_KEY = os.environ.get('CRYPTOGRAPHY_KEY', 'chave-super-secreta-ong-naire-2026')

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

# Definição das aplicações instaladas no projeto
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'gerencias.apps.GerenciasConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'setup.urls'

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

WSGI_APPLICATION = 'setup.wsgi.application'

# Configuração do Banco de Dados (MySQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'bd_naire2'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),  # ou o IP do servidor
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}

# Criptografia de senhas com Bcrypt (mantendo compatibilidade com as senhas já criadas)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

try:
    import bcrypt
    PASSWORD_HASHERS.insert(0, 'django.contrib.auth.hashers.BCryptSHA256PasswordHasher')
except ImportError:
    pass

# Validação de senhas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalização (Idioma e Fuso Horário)
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Arquivos estáticos (CSS, JavaScript, Imagens) e redirecionamento de Login/Logout
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
STATIC_URL = '/assets/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static')
]

# ==============================================================================
# POLÍTICAS DE SEGURANÇA AVANÇADA (WAF Interno, Bloqueio XSS e Blindagem)
# ==============================================================================
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Barrar clickjacking (incorporação do site em iframes maliciosos)
X_FRAME_OPTIONS = 'DENY'

# Prevenir MIME-Type sniffing (evita injeção de scripts ocultos)
SECURE_CONTENT_TYPE_NOSNIFF = True

# Forçar HTTPS (HSTS) - Ativado automaticamente quando não estiver em DEBUG (produção)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'