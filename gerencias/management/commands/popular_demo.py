"""
Preenche o banco de DEMONSTRAÇÃO com dados fictícios e, opcionalmente,
cria as contas do grupo de teste.

Uso:
    python manage.py popular_demo
    python manage.py popular_demo --usuarios ana bruno carla
    python manage.py popular_demo --usuarios ana bruno --lgpd

- Os nomes, endereços e CPFs são inventados. Os CPFs têm dígitos
  verificadores válidos (o sistema exige), mas foram sorteados.
- As senhas das contas criadas aparecem UMA vez na tela. Anote e repasse
  a cada pessoa por mensagem privada.
- Por segurança, só roda em SQLite (nunca no MySQL real).
"""
import random
import secrets
from datetime import date

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from gerencias.models import (
    TbApadrinhamentoCrianca, TbCadastroResponsavel, TbEntrega, TbEvento,
    TbFilhosResponsavel, TbFuncionario, TbMadrinhaPadrinho, TbTipoFuncionario,
)
from gerencias.permissoes import GRUPO_LGPD

PRIMEIROS = ['Ana', 'Bruno', 'Carla', 'Diego', 'Elisa', 'Fábio', 'Gabriela', 'Heitor',
             'Isabela', 'João', 'Larissa', 'Marcos', 'Natália', 'Otávio', 'Paula', 'Rafael']
SOBRENOMES = ['Teste Silva', 'Exemplo Souza', 'Demo Oliveira', 'Fictício Santos',
              'Modelo Lima', 'Amostra Costa']
CRIANCAS = ['Lucas', 'Sofia', 'Miguel', 'Alice', 'Arthur', 'Helena', 'Davi', 'Laura',
            'Gael', 'Valentina', 'Theo', 'Cecília']
BAIRROS = ['Jundiapeba', 'Centro', 'Vila Suíça', 'Braz Cubas']
AVISO = 'DADOS FICTÍCIOS - DEMONSTRAÇÃO'


def gerar_cpf(rng):
    while True:
        base = [rng.randint(0, 9) for _ in range(9)]
        if len(set(base)) > 1:
            break
    for tamanho in (9, 10):
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(base))
        base.append((soma * 10) % 11 % 10)
    return ''.join(map(str, base))


def data_br(ano, rng):
    return date(ano, rng.randint(1, 12), rng.randint(1, 28)).strftime('%d/%m/%Y')


class Command(BaseCommand):
    help = 'Cria dados fictícios no banco SQLite de demonstração.'

    def add_arguments(self, parser):
        parser.add_argument('--usuarios', nargs='*', default=[],
                            help='Nomes de usuário a criar para o grupo de teste.')
        parser.add_argument('--lgpd', action='store_true',
                            help='Coloca os usuários criados no grupo LGPD.')

    def handle(self, *args, usuarios, lgpd, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('Este comando só funciona com DB_ENGINE=sqlite.')

        if TbCadastroResponsavel.objects.exists():
            self.stdout.write('O banco já tem cadastros: dados fictícios não foram recriados.')
        else:
            with transaction.atomic():
                self._criar_dados()

        if usuarios:
            self._criar_usuarios(usuarios, lgpd)

    # ------------------------------------------------------------------
    def _criar_dados(self):
        rng = random.Random(2026)  # mesma semente = mesmos dados sempre
        agora = timezone.now()
        hoje = date.today()

        tipos = [TbTipoFuncionario.objects.get_or_create(descricao=d)[0]
                 for d in ('Coordenação', 'Voluntário', 'Assistente Social')]

        for i in range(4):
            TbFuncionario.objects.create(
                id_tipo=tipos[i % len(tipos)],
                pnome=PRIMEIROS[i], snome=SOBRENOMES[i % len(SOBRENOMES)],
                cpf=gerar_cpf(rng), telefone=f'1199999{1000 + i}',
                endereco=f'Rua Exemplo, {100 + i}', complemento='',
                bairro=rng.choice(BAIRROS), cidade='Mogi das Cruzes', estado='SP',
                flag_ativo='S',
            )

        filhos = []
        # 5 validados, 2 aguardando validação, 1 desativado
        situacoes = [('S', 'S')] * 5 + [('S', 'N')] * 2 + [('N', 'S')]
        for i, (ativo, validado) in enumerate(situacoes):
            resp = TbCadastroResponsavel.objects.create(
                pnome=PRIMEIROS[4 + i], snome=SOBRENOMES[i % len(SOBRENOMES)],
                cpf=gerar_cpf(rng), data_nascimento=data_br(rng.randint(1975, 2000), rng),
                flag_responsavel_trabalha=rng.choice('SN'), flag_conjuge=rng.choice('SN'),
                flag_conjuge_trabalha=rng.choice('SN'),
                endereco=f'Rua das Flores Fictícias, {10 + i}', complemento='',
                bairro=rng.choice(BAIRROS), cidade='Mogi das Cruzes', estado='SP',
                observacoes=AVISO, data_cadastro=agora,
                flag_ativo=ativo, flag_validado=validado,
            )
            for _ in range(rng.randint(1, 3)):
                filhos.append(TbFilhosResponsavel.objects.create(
                    id_responsavel=resp, pnome=rng.choice(CRIANCAS), snome=resp.snome,
                    data_nascimento=data_br(hoje.year - rng.randint(2, 12), rng),
                    cpf=gerar_cpf(rng) if rng.random() < 0.5 else None,
                    sexo=rng.choice('MF'), numero_roupa=str(rng.choice([4, 6, 8, 10, 12])),
                    numero_sapato=rng.randint(22, 34), cadastro_outra_ong='N',
                    data_cadastro=agora, flag_ativo=ativo,
                ))

        padrinhos = []
        for i in range(4):
            anonimo = i == 3
            padrinhos.append(TbMadrinhaPadrinho.objects.create(
                pnome='Anônimo' if anonimo else PRIMEIROS[12 + i],
                snome='' if anonimo else 'Padrinho Exemplo',
                cpf=None if anonimo else gerar_cpf(rng), flag_anonimo='S' if anonimo else 'N',
                endereco='Av. Demonstração, 500', complemento='', bairro='Centro',
                cidade='Mogi das Cruzes', estado='SP', data_cadastro=agora, flag_ativo='S',
            ))

        natal = TbEvento.objects.create(
            nome='Natal Solidário (demo)', data_evento=f'20/12/{hoje.year}',
            endereco='Salão da ONG, 1', bairro='Jundiapeba', cidade='Mogi das Cruzes',
            estado='SP', data_cadastro=agora, flag_finalizado='N')
        TbEvento.objects.create(
            nome='Dia das Crianças (demo)', data_evento=f'12/10/{hoje.year}',
            endereco='Praça Exemplo, s/n', bairro='Centro', cidade='Mogi das Cruzes',
            estado='SP', data_cadastro=agora, flag_finalizado='S')

        ativos = [f for f in filhos if f.flag_ativo == 'S']
        for padrinho, crianca in zip(padrinhos, ativos):
            TbApadrinhamentoCrianca.objects.create(id_mad_pad=padrinho, id_filho=crianca, data_cadastro=agora)
        for padrinho, crianca in list(zip(padrinhos, ativos))[:3]:
            TbEntrega.objects.create(
                id_evento=natal.id_evento, id_mad_pad=padrinho.id_mad_pad, id_crianca=crianca.id_filho,
                endereco=natal.endereco, bairro=natal.bairro, cidade=natal.cidade,
                estado=natal.estado, data_cadastro=agora, flag_finalizado='N')

        self.stdout.write(self.style.SUCCESS(
            f'Dados fictícios criados: 4 funcionários, {len(situacoes)} responsáveis, '
            f'{len(filhos)} crianças, {len(padrinhos)} padrinhos, 2 eventos.'))

    def _criar_usuarios(self, nomes, lgpd):
        grupo = Group.objects.get_or_create(name=GRUPO_LGPD)[0] if lgpd else None
        self.stdout.write('\nContas do grupo (anote as senhas, elas não aparecem de novo):')
        for nome in nomes:
            if User.objects.filter(username=nome).exists():
                self.stdout.write(f'  {nome}: já existe, senha não alterada')
                continue
            senha = secrets.token_urlsafe(9)
            user = User.objects.create_user(nome, password=senha, is_staff=True)
            if grupo:
                user.groups.add(grupo)
            self.stdout.write(f'  usuário: {nome}   senha: {senha}')
