import os
import django

# Carrega as configurações do seu projeto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from gerencias.models import TbFuncionario, TbCadastroResponsavel, TbFilhosResponsavel, TbMadrinhaPadrinho, Conn

print("Iniciando criptografia dos dados de teste...")


def ja_criptografado(valor):
    """
    O django-cryptography grava BINÁRIO começando pelo byte 0x80 (não o
    texto 'gAAAAA' do Fernet em base64). Sem esta checagem, rodar o script
    duas vezes cifraria o CPF já cifrado e ele ficaria irrecuperável.
    """
    if isinstance(valor, (bytes, bytearray)):
        return valor[:1] == b'\x80'
    return str(valor).startswith('gAAAAA')


def precisa_cifrar(valor):
    return bool(valor) and not ja_criptografado(valor)


def como_texto(valor):
    # Coluna VARBINARY devolve bytes; o CPF em texto puro precisa virar str.
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor).decode()
    return valor


# 1. Funcionários
funcs = Conn.executa_query("SELECT id_funcionario, cpf FROM tb_funcionario")
for f in funcs:
    if precisa_cifrar(f['cpf']):
        TbFuncionario.objects.filter(id_funcionario=f['id_funcionario']).update(cpf=como_texto(f['cpf']))
        print(f"Funcionário {f['id_funcionario']} criptografado.")

# 2. Responsáveis
resps = Conn.executa_query("SELECT id_responsavel, cpf FROM tb_cadastro_responsavel")
for r in resps:
    if precisa_cifrar(r['cpf']):
        TbCadastroResponsavel.objects.filter(id_responsavel=r['id_responsavel']).update(cpf=como_texto(r['cpf']))
        print(f"Responsável {r['id_responsavel']} criptografado.")

# 3. Filhos
filhos = Conn.executa_query("SELECT id_filho, cpf FROM tb_filhos_responsavel WHERE cpf IS NOT NULL")
for f in filhos:
    if precisa_cifrar(f['cpf']):
        TbFilhosResponsavel.objects.filter(id_filho=f['id_filho']).update(cpf=como_texto(f['cpf']))
        print(f"Filho {f['id_filho']} criptografado.")

# 4. Madrinhas e Padrinhos
pads = Conn.executa_query("SELECT id_mad_pad, cpf FROM tb_madrinha_padrinho WHERE cpf IS NOT NULL")
for p in pads:
    if precisa_cifrar(p['cpf']):
        TbMadrinhaPadrinho.objects.filter(id_mad_pad=p['id_mad_pad']).update(cpf=como_texto(p['cpf']))
        print(f"Padrinho/Madrinha {p['id_mad_pad']} criptografado.")

print("Migração concluída! Agora rode: python manage.py preencher_cpf_hash")