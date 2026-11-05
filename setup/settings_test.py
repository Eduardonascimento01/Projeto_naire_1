"""
Configurações usadas SOMENTE para rodar os testes automatizados.

Uso:
    python manage.py test --settings=setup.settings_test

Diferenças em relação ao settings.py normal:
- Usa SQLite em memória (não precisa de MySQL rodando nem mexe no banco real).
- Desliga as migrations do app `gerencias` e usa um test runner que marca os
  models `managed = False` como gerenciados, para que o Django crie as tabelas
  temporárias a partir dos models.
"""
import os

os.environ.setdefault('DJANGO_DEBUG', 'True')

from setup.settings import *  # noqa: E402,F401,F403

DEBUG = False
SECURE_SSL_REDIRECT = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

MIGRATION_MODULES = {'gerencias': None}
TEST_RUNNER = 'gerencias.test_runner.UnmanagedModelTestRunner'

# Senhas rápidas nos testes (bcrypt/PBKDF2 deixam os testes lentos).
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

CPF_HASH_KEY = 'chave-de-teste-cpf-hash'
