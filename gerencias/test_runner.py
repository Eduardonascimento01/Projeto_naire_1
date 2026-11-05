from django.apps import apps
from django.test.runner import DiscoverRunner


class UnmanagedModelTestRunner(DiscoverRunner):
    """
    Os models deste app espelham tabelas que já existem no MySQL, por isso
    usam `managed = False` (o Django não cria nem altera essas tabelas).

    Nos testes, porém, o banco é um SQLite vazio. Este runner liga o
    `managed` temporariamente para o Django criar as tabelas de teste.

    O AuthUser fica de fora porque a tabela `auth_user` já é criada pelo
    próprio app `django.contrib.auth`.
    """

    def setup_test_environment(self, *args, **kwargs):
        self._unmanaged = [
            m for m in apps.get_app_config('gerencias').get_models()
            if not m._meta.managed and m._meta.db_table != 'auth_user'
        ]
        for m in self._unmanaged:
            m._meta.managed = True
        super().setup_test_environment(*args, **kwargs)

    def teardown_test_environment(self, *args, **kwargs):
        super().teardown_test_environment(*args, **kwargs)
        for m in self._unmanaged:
            m._meta.managed = False
