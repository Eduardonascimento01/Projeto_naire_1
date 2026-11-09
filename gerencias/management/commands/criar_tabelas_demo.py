"""
Cria as tabelas do sistema num banco SQLite de DEMONSTRAÇÃO.

Uso (com DB_ENGINE=sqlite no .env):
    python manage.py migrate
    python manage.py criar_tabelas_demo

Por que é preciso: os models deste app usam `managed = False`, porque no
banco real (MySQL) as tabelas já existem e o Django não deve mexer nelas.
Num banco novo e vazio, alguém precisa criá-las: é o que este comando faz.

Por segurança, ele SÓ roda em SQLite. Nunca altera o MySQL.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Cria as tabelas do app gerencias num banco SQLite de demonstração.'

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError(
                'Este comando só funciona com DB_ENGINE=sqlite. '
                'Ele nunca deve ser usado no banco MySQL real.')

        existentes = set(connection.introspection.table_names())
        if 'auth_user' not in existentes:
            raise CommandError('Rode antes: python manage.py migrate')

        # Todo model do app cuja tabela ainda não existe. O AuthUser fica de
        # fora porque a tabela auth_user é do próprio Django (criada no migrate).
        faltando = []
        for model in apps.get_app_config('gerencias').get_models():
            tabela = model._meta.db_table
            if tabela == 'auth_user':
                continue
            if tabela in existentes:
                self.stdout.write(f'  {tabela}: já existe')
            else:
                faltando.append(model)

        if faltando:
            with connection.schema_editor() as editor:
                for model in faltando:
                    editor.create_model(model)
                    self.stdout.write(f'  {model._meta.db_table}: criada')
        criadas = len(faltando)

        self.stdout.write(self.style.SUCCESS(f'Pronto: {criadas} tabela(s) criada(s).'))
