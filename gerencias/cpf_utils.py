"""
Regras de CPF centralizadas num lugar só.

- limpar_cpf:   "123.456.789-09" -> "12345678909"
- cpf_valido:   confere os dois dígitos verificadores
- mascarar_cpf: "12345678909" -> "***.***.***-09" (só para exibir)
- hash_cpf:     HMAC-SHA256 do CPF. É o que vai para a coluna `cpf_hash`,
                que tem índice único e permite buscar/deduplicar por igualdade
                sem precisar decifrar a tabela inteira.

Por que HMAC e não só SHA-256? Existem só 10^11 CPFs possíveis; com SHA-256
puro qualquer um que veja o banco testa todos em minutos. O HMAC usa uma
chave secreta (CPF_HASH_KEY), então sem a chave o hash não revela nada.
"""
import hashlib
import hmac

from django.conf import settings

PREFIXO_ANONIMO = 'ANON-'


def somente_digitos(valor):
    """Mantém só os dígitos. Aceita None. Serve para CPF, telefone etc."""
    if not valor:
        return ''
    return ''.join(ch for ch in str(valor) if ch.isdigit())


limpar_cpf = somente_digitos


def cpf_valido(cpf):
    """Valida tamanho e dígitos verificadores (recebe o CPF já limpo)."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def mascarar_cpf(cpf):
    """Versão para exibição. Nunca grave o resultado no banco."""
    if not cpf:
        return ''
    cpf_str = str(cpf).strip()
    if cpf_str.startswith(PREFIXO_ANONIMO):
        return 'ANON-***'
    digitos = limpar_cpf(cpf_str)
    if len(digitos) == 11:
        return f'***.***.***-{digitos[-2:]}'
    return '***.***.***-**'


def _chave_hash():
    chave = getattr(settings, 'CPF_HASH_KEY', None) or settings.CRYPTOGRAPHY_KEY
    return str(chave).encode()


def hash_cpf(cpf):
    """
    Devolve o HMAC (64 caracteres hex) de um CPF com 11 dígitos.
    Para vazio, anonimizado ou formato inválido devolve None — e NULL não
    conflita com o índice único, então vários registros podem ficar sem CPF.
    """
    digitos = limpar_cpf(cpf)
    if len(digitos) != 11 or str(cpf).startswith(PREFIXO_ANONIMO):
        return None
    return hmac.new(_chave_hash(), digitos.encode(), hashlib.sha256).hexdigest()
