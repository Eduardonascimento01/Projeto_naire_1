"""
Ponte de compatibilidade para o django-cryptography 1.1 no Django 5.

O django-cryptography (que cifra os CPFs) usa `django.utils.baseconv`, um
módulo que o Django 5 removeu. O Django 4.1+ já tem as mesmas funções em
`django.core.signing` (b62_encode / b62_decode, mesmo alfabeto 0-9A-Za-z).
Este arquivo recria o módulo antigo apontando para elas, ANTES de qualquer
model ser carregado (é importado no topo do settings.py).

O formato dos dados cifrados não muda: CPFs cifrados no Django 4.2 continuam
abrindo no 5.2 (teste: test_compat_cripto.py).
"""
import sys
import types

import django.utils
from django.core.signing import b62_decode, b62_encode

if 'django.utils.baseconv' not in sys.modules:
    class _Base62:
        encode = staticmethod(b62_encode)
        decode = staticmethod(b62_decode)

    _modulo = types.ModuleType('django.utils.baseconv')
    _modulo.base62 = _Base62()
    sys.modules['django.utils.baseconv'] = _modulo
    django.utils.baseconv = _modulo
