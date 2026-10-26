from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

# Constrói os caminhos dentro do projeto, por exemplo: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in {'true', '1', 'yes'}

# Se não estiver em DEBUG (desenvolvimento), o sistema QUEBRA se não houver uma chave segura
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('CRÍTICO: Defina DJANGO_SECRET_KEY no ambiente de produção.')
    SECRET_KEY = 'django-insecure-local-development-only-key'

# CHAVE CRIPTOGRÁFICA (Protege CPFs e dados sensíveis gerados pelo django-cryptography)
CRYPTOGRAPHY_KEY = os.environ.get('CRYPTOGRAPHY_KEY')
if not CRYPTOGRAPHY_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('CRÍTICO: Defina CRYPTOGRAPHY_KEY no ambiente de produção.')
    CRYPTOGRAPHY_KEY = 'chave-super-secreta-ong-naire-2026'

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
    'gerencias.middleware.LogAuditoriaMiddleware',
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

# Configuração do Banco de Dados (MySQL) blindada contra credenciais padrão
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')

if not DEBUG and (DB_USER in [None, 'root', ''] or DB_PASSWORD in [None, '1234', '']):
    raise ImproperlyConfigured('CRÍTICO: Não utilize root, senhas em branco ou padrões genéricos em produção.')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'bd_naire2'),
        'USER': DB_USER or 'root', # Aceita root apenas localmente (DEBUG=True)
        'PASSWORD': DB_PASSWORD or '', 
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
# Segurança de Cookies (Seguro: False no localhost, True em produção)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Barrar clickjacking (incorporação do site em iframes maliciosos)
X_FRAME_OPTIONS = 'DENY'

# Proteção contra XSS e Sniffing (MIME-Type)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Forçar HTTPS (HSTS) - Ativado automaticamente em produção (DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Tempo de expiração curta para a sessão (Requisito 5 - Tokens Seguros)
# Desloga o usuário após 1 hora (3600 segundos) de inatividade
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ==========================================
# SEGURANÇA CONTRA FORÇA BRUTA (DJANGO-AXES)
# ==========================================
INSTALLED_APPS.append('axes')
MIDDLEWARE.append('axes.middleware.AxesMiddleware')

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AXES_FAILURE_LIMIT = 5      # Bloqueia o IP após 5 tentativas erradas de senha
AXES_COOLOFF_TIME = 1       # Tempo de bloqueio: 1 hora
AXES_RESET_ON_SUCCESS = True # Zera a contagem se o usuário logar com sucesso