"""
Preenche a coluna `cpf_hash` dos registros que já existiam.

Uso:
    python manage.py preencher_cpf_hash            # grava
    python manage.py preencher_cpf_hash --dry-run  # só mostra o que faria

Rode depois do script Dump_banco/migracao_cpf_hash.sql. Pode ser rodado
várias vezes sem problema (só atualiza o que estiver diferente).
"""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from gerencias.cpf_utils import hash_cpf
from gerencias.models import (
    TbCadastroResponsavel, TbFilhosResponsavel, TbFuncionario, TbMadrinhaPadrinho,
)

_FORMATO_BYTES = re.compile(r"""^(?:bytearray\()?b(['"])(.*)\1\)?$""")


def _cpf_de_bytes(valor):
    if isinstance(valor, (bytes, bytearray)):
        return bytes(valor).decode('utf-8', 'replace')
    m = _FORMATO_BYTES.match(str(valor or ''))
    return m.group(2) if m else None


MODELS = [TbCadastroResponsavel, TbFilhosResponsavel, TbMadrinhaPadrinho, TbFuncionario]


class Command(BaseCommand):
    help = 'Calcula o cpf_hash (HMAC) de todos os registros com CPF.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Não grava nada.')

    def handle(self, *args, dry_run=False, **options):
        teve_problema = False
        for model in MODELS:
            teve_problema |= self._processar(model, dry_run)

        if teve_problema:
            self.stdout.write(self.style.WARNING(
                '\nHá pendências acima. Corrija-as e rode o comando de novo.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nTudo certo.'))

    def _processar(self, model, dry_run):
        nome = model._meta.db_table
        hashes = {}
        ilegiveis = []
        convertidos = {}

        # Um registro por vez: se um CPF não puder ser decifrado, os outros
        # continuam e o problema é LISTADO (antes ele era pulado em silêncio).
        for pk in model.objects.values_list('pk', flat=True):
            try:
                obj = model.objects.only('pk', 'cpf', 'cpf_hash').get(pk=pk)
            except Exception as exc:  # noqa: BLE001 - queremos relatar qualquer falha
                ilegiveis.append((pk, type(exc).__name__))
                continue
            # A versão antiga do criptografar_banco.py cifrava o CPF como
            # BYTES; ao decifrar ele volta como o texto "b'12345678909'"
            # (ou "bytearray(b'...')"). Aqui recuperamos só o CPF.
            texto = _cpf_de_bytes(obj.cpf)
            if texto is not None:
                convertidos[pk] = texto
                obj.cpf = texto
            hashes[pk] = (hash_cpf(obj.cpf), obj.cpf_hash)

        por_hash = defaultdict(list)
        for pk, (novo, _) in hashes.items():
            if novo:
                por_hash[novo].append(pk)
        duplicados = [pks for pks in por_hash.values() if len(pks) > 1]
        pks_duplicados = {pk for grupo in duplicados for pk in grupo}

        a_atualizar = {
            pk: novo for pk, (novo, atual) in hashes.items()
            if novo != atual and pk not in pks_duplicados
        }

        if not dry_run and convertidos:
            with transaction.atomic():
                for pk, texto in convertidos.items():
                    model.objects.filter(pk=pk).update(cpf=texto)

        if not dry_run and a_atualizar:
            with transaction.atomic():
                # Zera primeiro para não esbarrar no índice único durante a troca.
                model.objects.filter(pk__in=a_atualizar).update(cpf_hash=None)
                for pk, novo in a_atualizar.items():
                    model.objects.filter(pk=pk).update(cpf_hash=novo)

        acao = 'seriam atualizados' if dry_run else 'atualizados'
        self.stdout.write(f'{nome}: {len(hashes)} lidos, {len(a_atualizar)} {acao}.')
        if convertidos:
            self.stdout.write(f'  {len(convertidos)} CPF(s) gravados como bytes {"seriam convertidos" if dry_run else "convertidos"} para texto.')
        for pk, erro in ilegiveis:
            self.stdout.write(self.style.ERROR(
                f'  id {pk}: CPF não pôde ser decifrado ({erro}). '
                'Rode criptografar_banco.py ou confira a CRYPTOGRAPHY_KEY.'))
        for grupo in duplicados:
            self.stdout.write(self.style.ERROR(
                f'  CPF repetido nos ids {sorted(grupo)}: mantenha um só cadastro.'))
        return bool(ilegiveis or duplicados)
