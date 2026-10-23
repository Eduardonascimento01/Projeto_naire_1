import os
import django

# Carrega as configurações do seu projeto
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from gerencias.models import TbFuncionario, TbCadastroResponsavel, TbFilhosResponsavel, TbMadrinhaPadrinho, Conn

print("Iniciando criptografia dos dados de teste...")

# 1. Funcionários
funcs = Conn.executa_query("SELECT id_funcionario, cpf FROM tb_funcionario WHERE cpf NOT LIKE 'gAAAAA%'")
for f in funcs:
    if f['cpf']:
        TbFuncionario.objects.filter(id_funcionario=f['id_funcionario']).update(cpf=f['cpf'])
        print(f"Funcionário {f['id_funcionario']} criptografado.")

# 2. Responsáveis
resps = Conn.executa_query("SELECT id_responsavel, cpf FROM tb_cadastro_responsavel WHERE cpf NOT LIKE 'gAAAAA%'")
for r in resps:
    if r['cpf']:
        TbCadastroResponsavel.objects.filter(id_responsavel=r['id_responsavel']).update(cpf=r['cpf'])
        print(f"Responsável {r['id_responsavel']} criptografado.")

# 3. Filhos
filhos = Conn.executa_query("SELECT id_filho, cpf FROM tb_filhos_responsavel WHERE cpf IS NOT NULL AND cpf NOT LIKE 'gAAAAA%'")
for f in filhos:
    if f['cpf']:
        TbFilhosResponsavel.objects.filter(id_filho=f['id_filho']).update(cpf=f['cpf'])
        print(f"Filho {f['id_filho']} criptografado.")

# 4. Madrinhas e Padrinhos
pads = Conn.executa_query("SELECT id_mad_pad, cpf FROM tb_madrinha_padrinho WHERE cpf IS NOT NULL AND cpf NOT LIKE 'gAAAAA%'")
for p in pads:
    if p['cpf']:
        TbMadrinhaPadrinho.objects.filter(id_mad_pad=p['id_mad_pad']).update(cpf=p['cpf'])
        print(f"Padrinho/Madrinha {p['id_mad_pad']} criptografado.")

print("Migração concluída com sucesso! Todos os CPFs agora estão ilegíveis no banco de dados.")