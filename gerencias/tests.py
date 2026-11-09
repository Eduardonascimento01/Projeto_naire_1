"""
Testes automatizados.

Rode com:
    python manage.py test --settings=setup.settings_test

Usa SQLite em memória: não precisa de MySQL e não toca no banco real.
"""
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.template.loader import get_template
from django.test import TestCase, RequestFactory
from django.urls import reverse

from gerencias.cpf_utils import cpf_valido, hash_cpf, mascarar_cpf
from gerencias.models import (
    TbCadastroResponsavel, TbEntrega, TbEvento, TbFilhosResponsavel,
    TbMadrinhaPadrinho, TbFuncionario, TbTipoFuncionario,
)
from gerencias.views import GRUPO_LGPD, insere_novo_evento, novo_oficio

# CPFs válidos (dígitos verificadores corretos), gerados só para teste.
CPF_A = '52998224725'
CPF_B = '11144477735'
CPF_C = '15350946056'


def criar_responsavel(**extra):
    dados = dict(pnome='Maria', snome='Silva', cpf=CPF_A, bairro='Centro',
                 cidade='Mogi', estado='SP', flag_ativo='S', flag_validado='S')
    dados.update(extra)
    return TbCadastroResponsavel.objects.create(**dados)


class BaseLogado(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff', password='x', is_staff=True)
        self.client.force_login(self.user)

    def dar_permissao_lgpd(self):
        grupo, _ = Group.objects.get_or_create(name=GRUPO_LGPD)
        self.user.groups.add(grupo)


# ----------------------------------------------------------------------
# Regras de CPF
# ----------------------------------------------------------------------
class CpfUtilsTests(TestCase):
    def test_validacao_de_digitos(self):
        self.assertTrue(cpf_valido(CPF_A))
        self.assertFalse(cpf_valido('52998224724'))   # dígito errado
        self.assertFalse(cpf_valido('11111111111'))   # todos iguais
        self.assertFalse(cpf_valido('123'))

    def test_hash_ignora_pontuacao(self):
        self.assertEqual(hash_cpf('529.982.247-25'), hash_cpf(CPF_A))
        self.assertIsNone(hash_cpf(''))
        self.assertIsNone(hash_cpf('ANON-12'))

    def test_mascara(self):
        self.assertEqual(mascarar_cpf(CPF_A), '***.***.***-25')
        self.assertEqual(mascarar_cpf('ANON-7'), 'ANON-***')

    def test_save_preenche_cpf_hash(self):
        resp = criar_responsavel()
        self.assertEqual(resp.cpf_hash, hash_cpf(CPF_A))


# ----------------------------------------------------------------------
# Teste 1: cadastros novos aparecem nas listas (flags não ficam NULL)
# ----------------------------------------------------------------------
class CadastroApareceNaListaTests(BaseLogado):
    def test_responsavel_novo_tem_flags_e_aparece_em_nao_validados(self):
        self.client.post(reverse('insere_novo_responsavel'), {
            'pnome': 'Ana', 'snome': 'Souza', 'cpf': '529.982.247-25', 'endereco': 'Rua A, 1',
            'dt_nasc': '1990-05-10', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
        })
        resp = TbCadastroResponsavel.objects.get()
        self.assertEqual((resp.flag_ativo, resp.flag_validado), ('S', 'N'))
        self.assertEqual(resp.data_nascimento, '10/05/1990')

        pagina = self.client.get(reverse('lista_responsavel_nval'))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Ana')

    def test_crianca_nova_aparece_em_lista_filhos(self):
        resp = criar_responsavel()
        self.client.post(reverse('insere_novo_filho'), {
            'responsavel': resp.pk, 'filho-0-pnome': 'Joao', 'filho-0-snome': 'Silva',
            'filho-0-dt_nasc': '10/05/2018', 'filho-0-sexo': 'M',
        })
        filho = TbFilhosResponsavel.objects.get()
        self.assertEqual(filho.flag_ativo, 'S')
        pagina = self.client.get(reverse('lista_filhos', args=[resp.pk]))
        self.assertContains(pagina, 'Joao')

    def test_entrega_nova_tem_flag_finalizado(self):
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='F')
        mp = TbMadrinhaPadrinho.objects.create(pnome='P')
        ev = TbEvento.objects.create(nome='Natal', data_evento='24/12/2026')
        self.client.post(reverse('insere_nova_entrega'), {
            'id_evento': ev.pk, 'id_mad_pad': mp.pk, 'id_crianca': filho.pk,
        })
        self.assertEqual(TbEntrega.objects.get().flag_finalizado, 'N')

    def test_listas_com_registros_nao_quebram(self):
        """Antes, aplicar_mascara_cpf tentava escrever numa @property e TODA
        lista com pelo menos um registro dava erro 500."""
        resp = criar_responsavel()
        TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='F', cpf=CPF_B, flag_ativo='S')
        TbMadrinhaPadrinho.objects.create(pnome='P', cpf=CPF_C, flag_ativo='S')
        for nome, args in [('lista_responsavel', []), ('lista_filhos_total', []),
                           ('lista_filhos', [resp.pk]), ('lista_madrinha_padrinho', []),
                           ('nova_entrega', [])]:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 200)

    def test_listas_vazias_nao_quebram(self):
        for nome in ['lista_responsavel', 'lista_responsavel_nval', 'lista_responsavel_des',
                     'lista_filhos_total', 'lista_madrinha_padrinho', 'lista_madrinha_padrinho_desativados',
                     'lista_funcionarios', 'lista_funcionarios_desativos', 'listar_eventos',
                     'listar_entregas', 'lista_oficio', 'lista_apadrinhamento', 'nova_entrega']:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)

    def test_cpf_invalido_e_recusado(self):
        self.client.post(reverse('insere_novo_responsavel'), {
            'pnome': 'Ana', 'cpf': '123.456.789-00', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
        })
        self.assertFalse(TbCadastroResponsavel.objects.exists())

    def test_cpf_duplicado_e_recusado(self):
        criar_responsavel()
        self.client.post(reverse('insere_novo_responsavel'), {
            'pnome': 'Outra', 'cpf': '529.982.247-25', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
        })
        self.assertEqual(TbCadastroResponsavel.objects.count(), 1)

    def test_padrinho_anonimo_e_gravado(self):
        """O formulário envia o campo 'anonimo' (não 'flag_anonimo')."""
        self.client.post(reverse('inserir_madrinha_padrinho'), {
            'anonimo': 'S', 'pnome': 'Fulano', 'flag_ativo': 'S',
        })
        mp = TbMadrinhaPadrinho.objects.get()
        self.assertEqual((mp.flag_anonimo, mp.pnome), ('S', 'Anônimo'))


# ----------------------------------------------------------------------
# Teste 2: o HTML nunca contém o CPF completo
# ----------------------------------------------------------------------
class CpfNaoVazaNoHtmlTests(BaseLogado):
    def assertSemCpf(self, response, cpf):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        formatado = f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'
        self.assertNotIn(cpf, html)
        self.assertNotIn(formatado, html)
        self.assertNotIn(cpf[:3] + '.', html)  # pegaria o slice de 3 dígitos

    def test_telas_de_responsavel(self):
        resp = criar_responsavel(cpf='98765432100')
        for url in [reverse('lista_responsavel'), reverse('edit_responsavel', args=[resp.pk])]:
            with self.subTest(url):
                pagina = self.client.get(url)
                self.assertEqual(pagina.status_code, 200)
                self.assertSemCpf(pagina, '98765432100')
                self.assertContains(pagina, '***.***.***-00')
        resp.flag_validado = 'N'
        resp.save()
        self.assertSemCpf(self.client.get(reverse('lista_responsavel_nval')), '98765432100')
        resp.flag_ativo = 'N'
        resp.save()
        self.assertSemCpf(self.client.get(reverse('lista_responsavel_des')), '98765432100')

    def test_telas_de_padrinho(self):
        mp = TbMadrinhaPadrinho.objects.create(pnome='P', cpf='98765432100', flag_ativo='S')
        for url in [reverse('lista_madrinha_padrinho'), reverse('editar_madrinha_padrinho', args=[mp.pk]),
                    reverse('apadrinhar_crianca', args=[mp.pk])]:
            with self.subTest(url):
                self.assertSemCpf(self.client.get(url), '98765432100')
        mp.flag_ativo = 'N'
        mp.save()
        self.assertSemCpf(self.client.get(reverse('lista_madrinha_padrinho_desativados')), '98765432100')

    def test_telas_de_crianca_e_funcionario(self):
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='Zeca', cpf='98765432100', flag_ativo='S')
        tipo = TbTipoFuncionario.objects.create(descricao='Voluntário')
        func = TbFuncionario.objects.create(id_tipo=tipo, pnome='F', snome='G', cpf='98765432100',
                                            endereco='R', bairro='B', cidade='C', estado='SP', flag_ativo='N')
        for url in [reverse('lista_filhos_total'), reverse('editar_filho', args=[filho.pk]),
                    reverse('editar_funcionario', args=[func.pk]), reverse('lista_funcionarios_desativos')]:
            with self.subTest(url):
                self.assertSemCpf(self.client.get(url), '98765432100')
        pagina = self.client.post(reverse('buscar_filhos'), {'termo_busca': 'Zeca', 'tipo_busca': 'nome'})
        self.assertSemCpf(pagina, '98765432100')

    def test_editar_com_mascara_mantem_cpf(self):
        resp = criar_responsavel()
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'endereco': 'Rua A, 1', 'snome': 'Nova',
            'cpf': '***.***.***-25', 'dt_nasc': '', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
            'validado': 'S', 'ativo': 'S',
        })
        resp.refresh_from_db()
        self.assertEqual(resp.cpf, CPF_A)
        self.assertEqual(resp.snome, 'Nova')

    def test_data_nascimento_em_branco_nao_apaga(self):
        resp = criar_responsavel(data_nascimento='10/05/1990')
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'snome': 'Silva', 'endereco': 'Rua A, 1', 'cpf': '***', 'dt_nasc': '',
            'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
        })
        resp.refresh_from_db()
        self.assertEqual(resp.data_nascimento, '10/05/1990')


# ----------------------------------------------------------------------
# Teste 3: anonimização de responsável com filhos e entregas
# ----------------------------------------------------------------------
class AnonimizacaoTests(BaseLogado):
    def test_responsavel_com_filhos_e_entregas(self):
        self.dar_permissao_lgpd()
        resp = criar_responsavel(observacoes='mora perto da escola', url_image_familia='/f.jpg')
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='F', cpf=CPF_B,
                                                   url_imagem='/foto.jpg', flag_ativo='S')
        entrega = TbEntrega.objects.create(id_evento=1, id_crianca=filho.pk, endereco='Rua X', bairro='Y')

        r = self.client.post(reverse('anonimizar_responsavel', args=[resp.pk]))
        self.assertEqual(r.status_code, 302)

        resp.refresh_from_db(); filho.refresh_from_db(); entrega.refresh_from_db()
        self.assertEqual(resp.cpf, f'ANON-{resp.pk}')
        self.assertIsNone(resp.cpf_hash)
        self.assertEqual((resp.bairro, resp.cidade, resp.estado), ('Removido', 'Removido', '--'))
        self.assertEqual(resp.observacoes, '')
        self.assertIsNone(resp.url_image_familia)
        self.assertEqual(filho.cpf, f'ANON-{filho.pk}')
        self.assertIsNone(filho.url_imagem)
        self.assertEqual(entrega.bairro, 'Anonimizado')

    def test_cpf_anonimizado_fica_livre_para_novo_cadastro(self):
        self.dar_permissao_lgpd()
        resp = criar_responsavel()
        self.client.post(reverse('anonimizar_responsavel', args=[resp.pk]))
        self.assertFalse(TbCadastroResponsavel.objects.filter(cpf_hash=hash_cpf(CPF_A)).exists())

    def test_staff_sem_grupo_lgpd_e_bloqueado(self):
        resp = criar_responsavel()
        r = self.client.post(reverse('anonimizar_responsavel', args=[resp.pk]))
        self.assertEqual(r.status_code, 403)
        resp.refresh_from_db()
        self.assertEqual(resp.pnome, 'Maria')
        self.assertEqual(self.client.get(reverse('exportar_dados_responsavel', args=[resp.pk])).status_code, 403)


# ----------------------------------------------------------------------
# Teste 4: ID inexistente -> 404 (e não 500)
# ----------------------------------------------------------------------
class NaoEncontradoTests(BaseLogado):
    def test_ids_inexistentes_dao_404(self):
        for nome in ['editar_filho', 'edit_responsavel', 'editar_funcionario',
                     'editar_madrinha_padrinho', 'editar_evento', 'exibe_oficio']:
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(nome, args=[99999])).status_code, 404)

    def test_erro_inesperado_e_logado_com_traceback(self):
        with patch('gerencias.views.TbEvento.objects.all', side_effect=RuntimeError('falhou')), \
                self.assertLogs('gerencias.views', 'ERROR') as log:
            r = self.client.get(reverse('listar_eventos'))
        self.assertEqual(r.status_code, 500)
        self.assertIn('Traceback', log.output[0])


# ----------------------------------------------------------------------
# Teste 5: editar criança não cria registro novo
# ----------------------------------------------------------------------
class EdicaoCriancaTests(BaseLogado):
    def test_formulario_aponta_para_atualiza_filho(self):
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='F', flag_ativo='S')
        pagina = self.client.get(reverse('editar_filho', args=[filho.pk]))
        self.assertContains(pagina, f'action="{reverse("atualiza_filho", args=[filho.pk])}"')

    def test_edicao_nao_duplica(self):
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='F', flag_ativo='S')
        self.client.post(reverse('atualiza_filho', args=[filho.pk]), {
            'responsavel': resp.pk, 'filho-0-pnome': 'Novo Nome', 'filho-0-snome': 'Silva',
            'filho-0-dt_nasc': '10/05/2018', 'filho-0-cpf': '', 'filho-0-sexo': 'M',
        })
        self.assertEqual(TbFilhosResponsavel.objects.count(), 1)
        filho.refresh_from_db()
        self.assertEqual(filho.pnome, 'Novo Nome')


# ----------------------------------------------------------------------
# Busca de padrinhos e eventos
# ----------------------------------------------------------------------
class BuscaEEventosTests(BaseLogado):
    def test_busca_padrinho_por_cpf_com_pontuacao(self):
        TbMadrinhaPadrinho.objects.create(pnome='Carla', cpf=CPF_C, flag_ativo='S')
        TbMadrinhaPadrinho.objects.create(pnome='Outro', cpf=CPF_B, flag_ativo='S')
        pagina = self.client.get(reverse('lista_madrinha_padrinho'), {'q': '153.509.460-56'})
        self.assertEqual([m.pnome for m in pagina.context['dados']], ['Carla'])

    def test_busca_padrinho_por_sobrenome(self):
        TbMadrinhaPadrinho.objects.create(pnome='Carla', snome='Prado', flag_ativo='S')
        pagina = self.client.get(reverse('lista_madrinha_padrinho'), {'q': 'prado'})
        self.assertEqual(len(pagina.context['dados']), 1)

    def test_eventos_ordenados_por_data_real(self):
        for nome, data in [('A', '01/12/2025'), ('B', '31/01/2026'), ('C', '15/06/2024')]:
            TbEvento.objects.create(nome=nome, data_evento=data)
        pagina = self.client.get(reverse('listar_eventos'))
        self.assertEqual([e.nome for e in pagina.context['lista']], ['B', 'A', 'C'])

    def test_atualiza_evento_rejeita_data_invalida(self):
        ev = TbEvento.objects.create(nome='Natal', data_evento='24/12/2026', endereco='R',
                                     bairro='B', cidade='C', estado='SP')
        self.client.post(reverse('atualiza_evento', args=[ev.pk]), {
            'nome': 'Natal', 'data_evento': '31/02/2026', 'endereco': 'R',
            'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
        })
        ev.refresh_from_db()
        self.assertEqual(ev.data_evento, '24/12/2026')


# ----------------------------------------------------------------------
# Testes que já existiam
# ----------------------------------------------------------------------
class EdicaoEntregaTests(TestCase):
    def test_rota_de_atualizacao_de_entrega_existe(self):
        self.assertEqual(
            reverse('atualiza_entrega', kwargs={'id_entrega': 1}),
            '/gerencias/atualiza_entrega/1/'
        )

    def test_template_de_edicao_de_entrega_carrega(self):
        self.assertIsNotNone(get_template('gerencias/editar_entrega.html'))

    def test_pagina_de_novo_oficio_aceita_get(self):
        request = RequestFactory().get('/gerencias/novo_oficio/')
        request.user = User(id=1, username='teste')
        response = novo_oficio.__wrapped__(request)
        self.assertEqual(response.status_code, 200)

    def test_evento_rejeita_data_inexistente(self):
        request = RequestFactory().post('/gerencias/insere_novo_evento/', {
            'nome': 'Evento teste',
            'data_evento': '31/02/2026',
            'endereco': 'Rua teste',
            'bairro': 'Centro',
            'cidade': 'São Paulo',
            'estado': 'SP',
        })
        with patch('gerencias.views.messages.error'), \
                patch('gerencias.views.TbEvento.objects.create') as create_event:
            response = insere_novo_evento.__wrapped__(request)
        self.assertEqual(response.status_code, 302)
        create_event.assert_not_called()


# ----------------------------------------------------------------------
# Comando preencher_cpf_hash (registros antigos)
# ----------------------------------------------------------------------
class PreencherCpfHashTests(TestCase):
    def test_preenche_e_aponta_duplicados(self):
        from io import StringIO
        from django.core.management import call_command

        a = criar_responsavel(cpf=CPF_A)
        b = criar_responsavel(cpf=CPF_B)
        c = criar_responsavel(cpf=CPF_C)
        # Simula registros antigos: hash vazio e b com o mesmo CPF de c.
        TbCadastroResponsavel.objects.update(cpf_hash=None)
        TbCadastroResponsavel.objects.filter(pk=b.pk).update(cpf=CPF_C)

        saida = StringIO()
        call_command('preencher_cpf_hash', stdout=saida)

        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.cpf_hash, hash_cpf(CPF_A))
        self.assertIsNone(b.cpf_hash)  # duplicado: não grava, só avisa
        self.assertIn(f'CPF repetido nos ids {sorted([b.pk, c.pk])}', saida.getvalue())

    def test_converte_cpf_gravado_como_bytes(self):
        """A versão antiga do criptografar_banco.py cifrava bytes, não texto."""
        from io import StringIO
        from django.core.management import call_command

        resp = criar_responsavel(cpf=CPF_A)
        TbCadastroResponsavel.objects.filter(pk=resp.pk).update(cpf=CPF_A.encode(), cpf_hash=None)
        resp.refresh_from_db()
        self.assertEqual(resp.cpf, "b'52998224725'")  # como ficou no banco

        call_command('preencher_cpf_hash', stdout=StringIO())

        resp.refresh_from_db()
        self.assertEqual(resp.cpf, CPF_A)
        self.assertEqual(resp.cpf_hash, hash_cpf(CPF_A))


# ----------------------------------------------------------------------
# Comandos do banco de demonstração (PythonAnywhere / SQLite)
# ----------------------------------------------------------------------
class DemoTests(TestCase):
    def test_popular_demo_cria_dados_validos_e_usuarios(self):
        from io import StringIO
        from django.core.management import call_command

        saida = StringIO()
        call_command('popular_demo', '--usuarios', 'ana', 'bruno', '--lgpd', stdout=saida)

        self.assertEqual(TbCadastroResponsavel.objects.count(), 8)
        for resp in TbCadastroResponsavel.objects.all():
            self.assertTrue(cpf_valido(resp.cpf))
            self.assertEqual(resp.cpf_hash, hash_cpf(resp.cpf))
        self.assertTrue(TbFilhosResponsavel.objects.exists())

        ana = User.objects.get(username='ana')
        self.assertTrue(ana.is_staff)
        self.assertTrue(ana.groups.filter(name=GRUPO_LGPD).exists())
        self.assertIn('usuário: ana', saida.getvalue())

        # Rodar de novo não duplica nada
        call_command('popular_demo', stdout=StringIO())
        self.assertEqual(TbCadastroResponsavel.objects.count(), 8)

    def test_criar_tabelas_demo_nao_recria_tabelas_existentes(self):
        from io import StringIO
        from django.core.management import call_command

        saida = StringIO()
        call_command('criar_tabelas_demo', stdout=saida)
        self.assertIn('0 tabela(s) criada(s)', saida.getvalue())


# ----------------------------------------------------------------------
# Botões de LGPD seguem a mesma regra das views
# ----------------------------------------------------------------------
class BotoesLgpdTests(BaseLogado):
    def test_staff_sem_grupo_nao_ve_botoes(self):
        criar_responsavel()
        pagina = self.client.get(reverse('lista_responsavel'))
        self.assertNotContains(pagina, 'Exportar Dados LGPD')

    def test_membro_do_grupo_lgpd_ve_botoes(self):
        """Antes, os botões só apareciam para superusuário, mesmo com o grupo LGPD."""
        self.dar_permissao_lgpd()
        resp = criar_responsavel()
        TbMadrinhaPadrinho.objects.create(pnome='P', flag_ativo='S')
        pagina = self.client.get(reverse('lista_responsavel'))
        self.assertContains(pagina, reverse('exportar_dados_responsavel', args=[resp.pk]))
        pagina = self.client.get(reverse('lista_madrinha_padrinho'))
        self.assertContains(pagina, 'Anonimizar Titular LGPD')

    def test_excluir_oficio_so_aparece_com_permissao(self):
        from gerencias.models import TbOficios
        oficio = TbOficios.objects.create(id_usuario_id=self.user.id, destinatario='X', mensagem='M')
        url_excluir = reverse('excluir_oficio', args=[oficio.pk])
        self.assertNotContains(self.client.get(reverse('lista_oficio')), url_excluir)
        self.dar_permissao_lgpd()
        self.assertContains(self.client.get(reverse('lista_oficio')), url_excluir)


class VisualTests(BaseLogado):
    def test_paginas_carregam_o_css_global(self):
        pagina = self.client.get(reverse('lista_responsavel'))
        self.assertContains(pagina, '/assets/css/naire.css')
        self.assertContains(pagina, '<body class="naire">')


# ----------------------------------------------------------------------
# Ajustes das tabelas (datas, colunas) e modo LGPD
# ----------------------------------------------------------------------
class AjustesTabelasTests(BaseLogado):
    def test_data_de_cadastro_aparece_como_mes_e_ano(self):
        from datetime import datetime
        from django.utils import timezone
        criar_responsavel(data_cadastro=timezone.make_aware(datetime(2026, 3, 15, 14, 30)))
        pagina = self.client.get(reverse('lista_responsavel')).content.decode()
        self.assertIn('03/2026', pagina)
        self.assertNotIn('15/03/2026', pagina)
        self.assertNotIn('14:30', pagina)

    def test_lista_de_criancas_sem_responsavel_e_sem_acoes(self):
        resp = criar_responsavel()
        TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='Zeca', data_nascimento='10/05/2018', flag_ativo='S')
        pagina = self.client.get(reverse('lista_filhos_total')).content.decode()
        self.assertNotIn('# RESP', pagina)
        self.assertNotIn('AÇÃO</th>', pagina)
        self.assertNotIn(reverse('desativar_filho', args=[resp.pk]), pagina)
        self.assertIn('**/**/2018', pagina)                                   # ano de nascimento
        self.assertIn(reverse('lista_filhos', args=[resp.pk]), pagina)       # link para a família

    def test_lista_de_funcionarios_sem_coluna_tipo(self):
        pagina = self.client.get(reverse('lista_funcionarios')).content.decode()
        self.assertNotIn('TIP FUNC', pagina)

    def test_editar_funcionario_marca_o_tipo_atual(self):
        """Antes nenhuma opção ficava marcada e, ao salvar, o tipo era trocado sem aviso."""
        tipos = [TbTipoFuncionario.objects.create(descricao=d) for d in ('A', 'B', 'C')]
        func = TbFuncionario.objects.create(id_tipo=tipos[2], pnome='F', snome='G', cpf=CPF_A,
                                            endereco='R', bairro='B', cidade='C', estado='SP', flag_ativo='S')
        pagina = self.client.get(reverse('editar_funcionario', args=[func.pk])).content.decode()
        self.assertRegex(pagina, rf'<option value="{tipos[2].pk}"\s+selected>')

    def test_botao_modo_lgpd_so_para_quem_tem_permissao(self):
        criar_responsavel()
        botao = 'class="btn btn-sm btn-modo-lgpd'
        pagina = self.client.get(reverse('lista_responsavel'))
        self.assertNotContains(pagina, botao)
        self.assertNotContains(pagina, 'class="acoes-lgpd"')
        self.dar_permissao_lgpd()
        pagina = self.client.get(reverse('lista_responsavel'))
        self.assertContains(pagina, botao)
        self.assertContains(pagina, 'class="acoes-lgpd"')

    def test_buscar_criancas_sem_responsavel_e_sem_acoes(self):
        resp = criar_responsavel()
        TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='Zeca', data_nascimento='10/05/2018', flag_ativo='S')
        pagina = self.client.post(reverse('buscar_filhos'), {'termo_busca': 'Zeca', 'tipo_busca': 'nome'}).content.decode()
        self.assertNotIn('RESPONSÁVEL</th>', pagina)
        self.assertNotIn('AÇÃO</th>', pagina)
        self.assertNotIn(reverse('desativar_filho', args=[resp.pk]), pagina)
        self.assertIn(reverse('lista_filhos', args=[resp.pk]), pagina)
        self.assertIn('**/**/2018', pagina)
        self.assertNotIn('10/05/2018', pagina)

    def test_funcionarios_desativados_mascaram_telefone_e_endereco(self):
        tipo = TbTipoFuncionario.objects.create(descricao='Voluntário')
        TbFuncionario.objects.create(id_tipo=tipo, pnome='F', snome='G', cpf=CPF_A, telefone='11987654321',
                                     endereco='Rua Secreta, 99', bairro='Centro', cidade='C', estado='SP', flag_ativo='N')
        pagina = self.client.get(reverse('lista_funcionarios_desativos')).content.decode()
        self.assertNotIn('11987654321', pagina)
        self.assertNotIn('Rua Secreta', pagina)
        self.assertIn('(11) *****-4321', pagina)
        self.assertIn('Oculto - LGPD', pagina)


class JavascriptDosTemplatesTests(TestCase):
    def test_nenhum_template_usa_seletor_exclusivo_do_jquery(self):
        """':visible' só existe no jQuery, que o projeto não carrega; no JavaScript
        puro ele dá erro e o botão "Exportar" deixava de funcionar."""
        import pathlib, re
        pasta = pathlib.Path(__file__).parent / 'templates'
        problemas = [
            str(arq.relative_to(pasta))
            for arq in pasta.rglob('*.html')
            if re.search(r"querySelector(All)?\([^)]*:visible", arq.read_text(encoding='utf-8'))
        ]
        self.assertEqual(problemas, [])


# ----------------------------------------------------------------------
# Família, padrinhos, funcionários, entregas e mensagens
# ----------------------------------------------------------------------
class SituacaoEmCascataTests(BaseLogado):
    def _familia(self):
        resp = criar_responsavel()
        filhos = [TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome=n, flag_ativo='S') for n in ('A', 'B')]
        return resp, filhos

    def test_desativar_responsavel_desativa_as_criancas(self):
        resp, filhos = self._familia()
        self.client.post(reverse('desativar_responsavel', args=[resp.pk]))
        resp.refresh_from_db()
        self.assertEqual(resp.flag_ativo, 'N')
        self.assertEqual(set(TbFilhosResponsavel.objects.values_list('flag_ativo', flat=True)), {'N'})

    def test_reativar_responsavel_reativa_as_criancas(self):
        resp, filhos = self._familia()
        self.client.post(reverse('desativar_responsavel', args=[resp.pk]))
        self.client.post(reverse('reativar_responsavel', args=[resp.pk]))
        self.assertEqual(set(TbFilhosResponsavel.objects.values_list('flag_ativo', flat=True)), {'S'})

    def test_desativar_pelo_formulario_de_edicao_tambem_desativa_as_criancas(self):
        resp, filhos = self._familia()
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'snome': 'Silva', 'endereco': 'Rua A, 1', 'cpf': '***', 'bairro': 'B',
            'cidade': 'C', 'estado': 'SP', 'ativo': 'N',
        })
        self.assertFalse(TbFilhosResponsavel.objects.filter(flag_ativo='S').exists())

    def test_padrinho_inativo_sai_dos_apadrinhamentos(self):
        resp, filhos = self._familia()
        mp = TbMadrinhaPadrinho.objects.create(pnome='Pad', flag_ativo='S')
        outro = TbMadrinhaPadrinho.objects.create(pnome='Outro', flag_ativo='S')
        from gerencias.models import TbApadrinhamentoCrianca
        for f in filhos:
            TbApadrinhamentoCrianca.objects.create(id_mad_pad=mp, id_filho=f)
        TbApadrinhamentoCrianca.objects.create(id_mad_pad=outro, id_filho=filhos[0])

        # Editar sem mudar a situação não mexe nos apadrinhamentos
        dados = {'pnome': 'Pad', 'cpf': '', 'flag_ativo': 'S'}
        self.client.post(reverse('atualiza_madrinha_padrinho', args=[mp.pk]), dados)
        self.assertEqual(TbApadrinhamentoCrianca.objects.filter(id_mad_pad=mp).count(), 2)

        resposta = self.client.post(reverse('atualiza_madrinha_padrinho', args=[mp.pk]),
                                    dict(dados, flag_ativo='N'), follow=True)
        self.assertFalse(TbApadrinhamentoCrianca.objects.filter(id_mad_pad=mp).exists())
        self.assertEqual(TbApadrinhamentoCrianca.objects.filter(id_mad_pad=outro).count(), 1)  # o outro fica
        self.assertContains(resposta, 'saiu de 2 apadrinhamento(s)')

    def test_padrinho_anonimizado_sai_dos_apadrinhamentos(self):
        self.dar_permissao_lgpd()
        resp, filhos = self._familia()
        mp = TbMadrinhaPadrinho.objects.create(pnome='Pad', flag_ativo='S')
        from gerencias.models import TbApadrinhamentoCrianca
        TbApadrinhamentoCrianca.objects.create(id_mad_pad=mp, id_filho=filhos[0])
        self.client.post(reverse('anonimizar_titular', args=[mp.pk]))
        self.assertFalse(TbApadrinhamentoCrianca.objects.exists())


class FuncionariosStatusTests(BaseLogado):
    def test_interruptor_ligado_e_desativacao_de_verdade(self):
        tipo = TbTipoFuncionario.objects.create(descricao='V')
        func = TbFuncionario.objects.create(id_tipo=tipo, pnome='F', snome='G', cpf=CPF_A,
                                            endereco='R', bairro='B', cidade='C', estado='SP', flag_ativo='S')
        pagina = self.client.get(reverse('lista_funcionarios')).content.decode()
        self.assertRegex(pagina, r'class="form-check-input status-toggle"[^>]*\bchecked\b')
        resposta = self.client.post(reverse('desativa_funcionario', args=[func.pk]), follow=True)
        func.refresh_from_db()
        self.assertEqual(func.flag_ativo, 'N')
        self.assertContains(resposta, 'foi desativado')


class EntregasComNomesTests(BaseLogado):
    def test_entregas_mostram_nomes_e_data_do_evento(self):
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='Zeca', snome='Silva', flag_ativo='S')
        mp = TbMadrinhaPadrinho.objects.create(pnome='Carla', snome='Prado', flag_ativo='S')
        ev = TbEvento.objects.create(nome='Natal Solidário', data_evento='20/12/2026', endereco='Salão da ONG')
        TbEntrega.objects.create(id_evento=ev.pk, id_mad_pad=mp.pk, id_crianca=filho.pk,
                                 endereco='Salão da ONG', bairro='Centro', cidade='Mogi', estado='SP')
        pagina = self.client.get(reverse('listar_entregas')).content.decode()
        for texto in ('Natal Solidário', 'Carla Prado', 'Zeca Silva', '20/12/2026', '📍 LOCAL'):
            self.assertIn(texto, pagina)
        self.assertNotIn('ID: ', pagina)
        self.assertNotIn('DATA CHEGADA', pagina)


class MensagensTests(BaseLogado):
    def test_erro_de_validacao_aparece_para_o_usuario(self):
        """Antes as mensagens eram criadas, mas nenhuma página as exibia."""
        resposta = self.client.post(reverse('insere_novo_responsavel'), {
            'pnome': 'Ana', 'cpf': '123.456.789-00', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
        }, follow=True)
        self.assertContains(resposta, 'CPF inválido', status_code=400)
        self.assertContains(resposta, 'alert-danger', status_code=400)


class ApadrinhamentoAoDesativarCriancaTests(BaseLogado):
    def setUp(self):
        super().setUp()
        from gerencias.models import TbApadrinhamentoCrianca
        self.Apad = TbApadrinhamentoCrianca
        self.resp = criar_responsavel()
        self.filhos = [TbFilhosResponsavel.objects.create(id_responsavel=self.resp, pnome=n, flag_ativo='S') for n in ('A', 'B')]
        outra = criar_responsavel(cpf=CPF_B)
        self.de_outra_familia = TbFilhosResponsavel.objects.create(id_responsavel=outra, pnome='C', flag_ativo='S')
        self.padrinho = TbMadrinhaPadrinho.objects.create(pnome='Pad', flag_ativo='S')
        for f in self.filhos + [self.de_outra_familia]:
            self.Apad.objects.create(id_mad_pad=self.padrinho, id_filho=f)

    def test_familia_desativada_sai_dos_apadrinhamentos(self):
        resposta = self.client.post(reverse('desativar_responsavel', args=[self.resp.pk]), follow=True)
        self.assertEqual(list(self.Apad.objects.values_list('id_filho', flat=True)), [self.de_outra_familia.pk])
        self.assertEqual(TbMadrinhaPadrinho.objects.get(pk=self.padrinho.pk).flag_ativo, 'S')  # padrinho continua
        self.assertContains(resposta, '2 apadrinhamento(s) removido(s)')

    def test_familia_desativada_pela_edicao_tambem(self):
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': self.resp.pk, 'pnome': 'Maria', 'snome': 'Silva', 'endereco': 'Rua A, 1', 'cpf': '***', 'bairro': 'B',
            'cidade': 'C', 'estado': 'SP', 'ativo': 'N',
        })
        self.assertEqual(self.Apad.objects.count(), 1)

    def test_crianca_desativada_sozinha_sai_do_apadrinhamento(self):
        self.client.post(reverse('desativar_filho', args=[self.resp.pk]), {'id_filho': self.filhos[0].pk})
        restantes = set(self.Apad.objects.values_list('id_filho', flat=True))
        self.assertEqual(restantes, {self.filhos[1].pk, self.de_outra_familia.pk})

    def test_reativar_nao_apaga_nada(self):
        self.client.post(reverse('reativar_responsavel', args=[self.resp.pk]))
        self.assertEqual(self.Apad.objects.count(), 3)


class NovoPadrinhoTests(BaseLogado):
    def test_formulario_vem_com_ativo_marcado(self):
        import re
        pagina = self.client.get(reverse('novo_madrinha_padrinho')).content.decode()
        campo_ativo = re.search(r'<select name="flag_ativo".*?</select>', pagina, re.S).group(0)
        self.assertRegex(campo_ativo, r'<option value="S" selected>')
        self.assertNotIn('<option value="N" selected>', campo_ativo)


# ----------------------------------------------------------------------
# Cadastro de funcionário com login e regra do administrador
# ----------------------------------------------------------------------
class CenarioFuncionarios(TestCase):
    """Tipos de funcionário, um administrador ('chefe') e um membro ('membro'). Sem testes."""
    SENHA = 'Girassol-Azul-2026'

    def setUp(self):
        from gerencias.models import TbFuncionarioUsuario
        self.Link = TbFuncionarioUsuario
        self.tipos = {d: TbTipoFuncionario.objects.create(pk=pk, descricao=d)
                      for pk, d in [(1, 'ADMIN'), (2, 'MEMBRO'), (3, 'CONTRATADO'), (4, 'VOLUNTARIO')]}
        self.admin = User.objects.create_user('chefe', password='x', is_staff=True, is_superuser=True)
        self.membro = User.objects.create_user('membro', password='x', is_staff=True)

    def dados(self, **extra):
        d = {'tp_funcionario': self.tipos['MEMBRO'].pk, 'flag': 'S', 'pnome': 'Ana', 'snome': 'Souza',
             'cpf': '529.982.247-25', 'telefone': '(11) 98765-4321', 'rua': 'Rua A', 'numero': '10',
             'comp': '', 'bairro': 'Centro', 'cidade': 'Mogi', 'estado': 'SP',
             'usuario': 'ana.souza', 'senha': self.SENHA, 'senha2': self.SENHA}
        d.update(extra)
        return d

    def entra(self, usuario, senha):
        """Login pela tela de login de verdade (passa pelo django-axes). True se entrou."""
        self.client.logout()
        resposta = self.client.post(reverse('login'), {'username': usuario, 'password': senha})
        return resposta.status_code == 302

    def cadastrar(self, quem, **extra):
        self.client.force_login(quem)
        return self.client.post(reverse('insere_novo_funcionario'), self.dados(**extra), follow=True)



class FuncionarioComLoginTests(CenarioFuncionarios):
    def test_membro_cadastrado_ganha_login_normal(self):
        resposta = self.cadastrar(self.admin)
        self.assertContains(resposta, 'Login: ana.souza')
        novo = User.objects.get(username='ana.souza')
        self.assertTrue(novo.is_staff and novo.is_active)
        self.assertFalse(novo.is_superuser)
        self.assertTrue(self.Link.objects.filter(usuario=novo, funcionario__pnome='Ana').exists())
        self.assertTrue(self.entra('ana.souza', self.SENHA))

    def test_so_administrador_cadastra_funcionario(self):
        # Quem cadastra escolhe a senha do login: um membro poderia criar uma
        # conta e entrar com ela. Por isso só o administrador cadastra.
        for tipo in ('MEMBRO', 'ADMIN'):
            resposta = self.cadastrar(self.membro, tp_funcionario=self.tipos[tipo].pk)
            self.assertContains(resposta, 'Somente um administrador pode cadastrar funcionários e criar logins')
        self.assertFalse(User.objects.filter(username='ana.souza').exists())
        self.assertFalse(TbFuncionario.objects.exists())

        self.cadastrar(self.admin, tp_funcionario=self.tipos['ADMIN'].pk)
        self.assertTrue(User.objects.get(username='ana.souza').is_superuser)

    def test_membro_nao_ve_novo_funcionario(self):
        self.client.force_login(self.membro)
        self.assertRedirects(self.client.get(reverse('novo_funcionario')), reverse('lista_funcionarios'))
        pagina = self.client.get(reverse('lista_funcionarios')).content.decode()
        self.assertNotIn(reverse('novo_funcionario'), pagina)          # nem no menu, nem no botão
        self.assertIn('Só um administrador cadastra funcionários', pagina)
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse('novo_funcionario')).content.decode()
        self.assertNotRegex(pagina, r'<option value="1"\s+disabled>')
        self.assertIn(reverse('novo_funcionario'), self.client.get(reverse('lista_funcionarios')).content.decode())

    def test_erros_devolvem_o_formulario_preenchido_sem_a_senha(self):
        resposta = self.cadastrar(self.admin, senha2='OutraSenha-99', telefone='123')
        self.assertEqual(resposta.status_code, 400)
        html = resposta.content.decode()
        self.assertIn('As senhas não são iguais', html)
        self.assertIn('Informe o telefone com DDD', html)
        self.assertIn('value="Ana"', html)            # dados voltam preenchidos
        self.assertNotIn(self.SENHA, html)            # a senha nunca volta na página
        self.assertFalse(TbFuncionario.objects.exists())

    def test_senha_fraca_e_usuario_repetido_sao_recusados(self):
        resposta = self.cadastrar(self.admin, senha='12345678', senha2='12345678')
        self.assertContains(resposta, 'senha', status_code=400)
        resposta = self.cadastrar(self.admin, usuario='MEMBRO')   # já existe (sem diferenciar maiúsculas)
        self.assertContains(resposta, 'já está em uso', status_code=400)
        self.assertFalse(TbFuncionario.objects.exists())

    def test_desativar_funcionario_bloqueia_o_login(self):
        self.cadastrar(self.admin)
        self.client.force_login(self.membro)
        func = TbFuncionario.objects.get()
        self.client.post(reverse('desativa_funcionario', args=[func.pk]))
        self.assertFalse(User.objects.get(username='ana.souza').is_active)
        self.assertFalse(self.entra('ana.souza', self.SENHA))
        self.client.force_login(self.membro)
        self.client.post(reverse('reativa_funcionario', args=[func.pk]))
        self.assertTrue(User.objects.get(username='ana.souza').is_active)

    def test_membro_nao_mexe_em_administrador(self):
        self.cadastrar(self.admin, tp_funcionario=self.tipos['ADMIN'].pk)
        func = TbFuncionario.objects.get()
        self.client.force_login(self.membro)
        self.client.get(reverse('editar_funcionario', args=[func.pk]))
        self.client.post(reverse('desativa_funcionario', args=[func.pk]))
        self.client.post(reverse('atualiza_funcionario'), {
            'id_funcionario': func.pk, 'id_tipo': self.tipos['VOLUNTARIO'].pk, 'pnome': 'X', 'snome': 'Y',
            'cpf': '***', 'telefone': '11987654321', 'endereco': 'R', 'bairro': 'B', 'cidade': 'C',
            'estado': 'SP', 'flag_ativo': 'S'})
        func.refresh_from_db()
        self.assertEqual((func.flag_ativo, func.pnome, func.id_tipo_id), ('S', 'Ana', self.tipos['ADMIN'].pk))
        self.assertTrue(User.objects.get(username='ana.souza').is_superuser)

    def test_membro_nao_se_promove_a_administrador(self):
        self.cadastrar(self.admin)
        func = TbFuncionario.objects.get()
        self.client.force_login(self.membro)
        self.client.post(reverse('atualiza_funcionario'), {
            'id_funcionario': func.pk, 'id_tipo': self.tipos['ADMIN'].pk, 'pnome': 'Ana', 'snome': 'Souza',
            'cpf': '***', 'telefone': '11987654321', 'endereco': 'R', 'bairro': 'B', 'cidade': 'C',
            'estado': 'SP', 'flag_ativo': 'S'})
        func.refresh_from_db()
        self.assertEqual(func.id_tipo_id, self.tipos['MEMBRO'].pk)
        self.assertFalse(User.objects.get(username='ana.souza').is_superuser)

    def test_verificacao_de_usuario_disponivel(self):
        self.client.force_login(self.membro)
        url = reverse('usuario_disponivel')
        self.assertEqual(self.client.get(url, {'usuario': 'Chefe'}).json(), {'valido': True, 'disponivel': False})
        self.assertEqual(self.client.get(url, {'usuario': 'nova.pessoa'}).json(), {'valido': True, 'disponivel': True})
        self.assertFalse(self.client.get(url, {'usuario': 'com espaço'}).json()['valido'])

    def test_anonimizar_funcionario_apaga_e_bloqueia_o_login(self):
        self.cadastrar(self.admin)
        func = TbFuncionario.objects.get()
        self.client.force_login(self.admin)
        self.client.post(reverse('anonimizar_funcionario', args=[func.pk]))
        login = self.Link.objects.get(funcionario=func).usuario
        self.assertEqual(login.username, f'anonimizado-{func.pk}')
        self.assertFalse(login.is_active or login.has_usable_password())
        self.assertEqual(login.first_name, '')

    def test_popular_demo_deixa_os_tipos_iguais_aos_do_banco_real(self):
        from io import StringIO
        from django.core.management import call_command
        # Banco de demonstração antigo: o tipo 1 era "Coordenação" e tinha funcionários.
        TbTipoFuncionario.objects.filter(pk=1).update(descricao='Coordenação')
        func = TbFuncionario.objects.create(id_tipo_id=1, pnome='F', snome='G', cpf=CPF_A,
                                            endereco='R', bairro='B', cidade='C', estado='SP')
        call_command('popular_demo', stdout=StringIO())
        self.assertEqual(list(TbTipoFuncionario.objects.order_by('pk').values_list('descricao', flat=True)),
                         ['ADMIN', 'MEMBRO', 'CONTRATADO', 'VOLUNTARIO'])
        func.refresh_from_db()
        self.assertEqual(func.id_tipo_id, 2)   # não virou administrador


class AcessoNaEdicaoTests(CenarioFuncionarios):
    NOVA = 'Orquidea-Lilas-2027'

    def funcionario_sem_login(self, tipo='VOLUNTARIO'):
        return TbFuncionario.objects.create(id_tipo=self.tipos[tipo], pnome='Beto', snome='Lima', cpf=CPF_B,
                                            endereco='R', bairro='B', cidade='C', estado='SP', flag_ativo='S')

    def criar_acesso(self, quem, func, **extra):
        self.client.force_login(quem)
        dados = {'usuario': 'beto.lima', 'senha': self.SENHA, 'senha2': self.SENHA}
        dados.update(extra)
        return self.client.post(reverse('criar_acesso_funcionario', args=[func.pk]), dados, follow=True)

    def trocar(self, quem, func, senha=None, senha_atual=None):
        self.client.force_login(quem)
        senha = senha or self.NOVA
        dados = {'senha': senha, 'senha2': senha}
        if senha_atual is not None:
            dados['senha_atual'] = senha_atual
        return self.client.post(reverse('trocar_senha_funcionario', args=[func.pk]), dados, follow=True)

    def test_edicao_mostra_criar_acesso_para_quem_nao_tem_login(self):
        func = self.funcionario_sem_login()
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse('editar_funcionario', args=[func.pk])).content.decode()
        self.assertIn('id="formCriarAcesso"', pagina)
        self.assertNotIn('id="formTrocarSenha"', pagina)
        # O membro vê só o aviso, sem o formulário
        self.client.force_login(self.membro)
        pagina = self.client.get(reverse('editar_funcionario', args=[func.pk])).content.decode()
        self.assertNotIn('id="formCriarAcesso"', pagina)
        self.assertIn('Somente um administrador pode criar o acesso', pagina)

    def test_criar_acesso_para_funcionario_antigo(self):
        func = self.funcionario_sem_login()
        resposta = self.criar_acesso(self.admin, func)
        self.assertContains(resposta, 'Acesso criado para Beto Lima. Login: beto.lima')
        self.assertTrue(self.Link.objects.filter(funcionario=func, usuario__username='beto.lima').exists())
        self.assertTrue(self.entra('beto.lima', self.SENHA))
        # Não dá para criar um segundo acesso
        resposta = self.criar_acesso(self.admin, func, usuario='beto.dois')
        self.assertContains(resposta, 'já tem acesso')
        self.assertFalse(User.objects.filter(username='beto.dois').exists())

    def test_criar_acesso_com_erro_volta_preenchido(self):
        func = self.funcionario_sem_login()
        resposta = self.criar_acesso(self.admin, func, senha2='Diferente-123')
        self.assertContains(resposta, 'As senhas não são iguais', status_code=400)
        self.assertContains(resposta, 'value="beto.lima"', status_code=400)
        self.assertNotContains(resposta, self.SENHA, status_code=400)
        self.assertFalse(User.objects.filter(username='beto.lima').exists())

    def test_membro_nao_cria_acesso(self):
        for tipo in ('VOLUNTARIO', 'ADMIN'):
            TbFuncionario.objects.all().delete()
            func = self.funcionario_sem_login(tipo=tipo)
            resposta = self.criar_acesso(self.membro, func)
            self.assertContains(resposta, 'Somente um administrador pode cadastrar funcionários e criar logins')
            self.assertFalse(User.objects.filter(username='beto.lima').exists())
        self.criar_acesso(self.admin, func)
        self.assertTrue(User.objects.get(username='beto.lima').is_superuser)

    def test_administrador_troca_senha_de_outra_pessoa(self):
        func = self.funcionario_sem_login()
        self.criar_acesso(self.admin, func)
        resposta = self.trocar(self.admin, func)
        self.assertContains(resposta, 'Senha de beto.lima alterada')
        self.assertTrue(self.entra('beto.lima', self.NOVA))
        self.assertFalse(self.entra('beto.lima', self.SENHA))

    def test_membro_nao_troca_senha_de_colega(self):
        func = self.funcionario_sem_login()
        self.criar_acesso(self.admin, func)
        pagina = self.client.get(reverse('editar_funcionario', args=[func.pk]))
        self.client.force_login(self.membro)
        pagina = self.client.get(reverse('editar_funcionario', args=[func.pk])).content.decode()
        self.assertNotIn('id="formTrocarSenha"', pagina)
        self.assertIn('Somente um administrador pode trocar a senha de outra pessoa', pagina)
        resposta = self.trocar(self.membro, func)                 # tentativa direta, sem a tela
        self.assertContains(resposta, 'Somente um administrador pode trocar a senha')
        self.assertTrue(self.entra('beto.lima', self.SENHA))      # senha continua a mesma

    def test_cada_um_troca_a_propria_senha_e_continua_logado(self):
        func = self.funcionario_sem_login()
        self.criar_acesso(self.admin, func)
        beto = User.objects.get(username='beto.lima')
        # Sem a senha atual (ou com ela errada), não troca
        resposta = self.trocar(beto, func, senha_atual='errada')
        self.assertContains(resposta, 'A senha atual não confere', status_code=400)
        resposta = self.trocar(beto, func, senha_atual=self.SENHA)
        self.assertContains(resposta, 'Senha de beto.lima alterada')
        # Continua logado depois de trocar a própria senha
        self.assertEqual(self.client.get(reverse('lista_funcionarios')).status_code, 200)
        self.assertTrue(self.entra('beto.lima', self.NOVA))

    def test_senha_fraca_na_troca_e_recusada(self):
        func = self.funcionario_sem_login()
        self.criar_acesso(self.admin, func)
        resposta = self.trocar(self.admin, func, senha='12345678')
        self.assertEqual(resposta.status_code, 400)
        self.assertTrue(self.entra('beto.lima', self.SENHA))


# ----------------------------------------------------------------------
# Início = blog aberto a todos; login numa tela própria ("Acesso à equipe")
# ----------------------------------------------------------------------
class InicioELoginTests(TestCase):
    SENHA = 'Girassol-Azul-2026'

    def setUp(self):
        self.user = User.objects.create_user('equipe', password=self.SENHA, is_staff=True)

    def entrar(self, **extra):
        dados = {'username': 'equipe', 'password': self.SENHA}
        dados.update(extra)
        return self.client.post(reverse('login'), dados)

    def test_inicio_e_so_o_blog_com_botao_acesso_a_equipe(self):
        pagina = self.client.get(reverse('home')).content.decode()
        self.assertIn('Blog NAIRE', pagina)
        self.assertIn('Acesso à equipe', pagina)
        self.assertIn(f'href="{reverse("login")}"', pagina)
        self.assertNotIn('id="formLogin"', pagina)             # o login não fica no início
        for item in ('FUNCIONÁRIOS', 'RESPONSÁVEL', 'MADRINHAS', 'OFÍCIOS', 'Cadastrar'):
            self.assertNotIn(item, pagina)

    def test_tela_de_login_propria(self):
        pagina = self.client.get(reverse('login')).content.decode()
        self.assertIn('id="formLogin"', pagina)
        self.assertIn('Voltar ao site', pagina)
        self.assertNotIn('FUNCIONÁRIOS', pagina)

    def test_pagina_protegida_manda_para_a_tela_de_login(self):
        resposta = self.client.get(reverse('lista_responsavel'))
        self.assertRedirects(resposta, '/accounts/login/?next=/gerencias/lista_responsavel/',
                             fetch_redirect_response=False)
        self.assertContains(self.client.get(resposta['Location']), 'Entre para continuar')

    def test_login_leva_para_a_pagina_que_a_pessoa_tentou_abrir(self):
        resposta = self.entrar(next='/gerencias/lista_responsavel/')
        self.assertRedirects(resposta, '/gerencias/lista_responsavel/', fetch_redirect_response=False)
        pagina = self.client.get(reverse('home')).content.decode()
        self.assertIn('FUNCIONÁRIOS', pagina)                  # agora o menu aparece
        self.assertNotIn('Acesso à equipe', pagina)

    def test_sem_next_volta_para_o_inicio(self):
        self.assertRedirects(self.entrar(), reverse('home'), fetch_redirect_response=False)

    def test_link_para_site_externo_e_ignorado(self):
        """Golpe do redirecionamento aberto: depois do login, nunca ir para outro site."""
        resposta = self.entrar(next='https://site-falso.com/naire')
        self.assertRedirects(resposta, reverse('home'), fetch_redirect_response=False)
        self.client.logout()
        pagina = self.client.get(reverse('login') + '?next=//site-falso.com').content.decode()
        self.assertNotIn('site-falso', pagina)

    def test_senha_errada_mostra_aviso_e_mantem_o_usuario(self):
        resposta = self.entrar(password='errada')
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'alert-danger')
        self.assertContains(resposta, 'value="equipe"')

    def test_quem_ja_entrou_nao_ve_a_tela_de_login(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse('login')), reverse('home'), fetch_redirect_response=False)

    def test_conta_que_nao_e_da_equipe_nao_ve_o_menu(self):
        User.objects.create_user('visitante', password=self.SENHA, is_staff=False)
        self.entrar(username='visitante')
        pagina = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('FUNCIONÁRIOS', pagina)
        self.assertIn('não tem acesso às funções', pagina)
        self.assertIn(reverse('logout'), pagina)               # mas consegue sair


# ----------------------------------------------------------------------
# Cadastro de família com crianças ("+ 1 filho")
# ----------------------------------------------------------------------
class FamiliaComCriancasTests(BaseLogado):
    def familia(self, **extra):
        d = {'pnome': 'Maria', 'snome': 'Souza', 'cpf': '529.982.247-25', 'dt_nasc': '1988-03-15',
             'resp_trabalha': 'S', 'flag_conjuge': 'N', 'conjuge_trabalha': 'N',
             'endereco': 'Rua das Flores, 10', 'complemento': '', 'bairro': 'Centro',
             'cidade': 'Mogi', 'estado': 'SP', 'obs': 'Teste'}
        d.update(extra)
        return d

    def filho(self, n, **extra):
        d = {'pnome': f'Filho{n}', 'snome': 'Souza', 'dt_nasc': '10/05/2018', 'cpf': '',
             'sexo': 'M', 'roupa': '8', 'sapato': '28', 'outra_ong': 'N'}
        d.update(extra)
        return {f'filho-{n}-{k}': v for k, v in d.items()}

    def enviar(self, *blocos, **extra):
        dados = self.familia(**extra)
        for b in blocos:
            dados.update(b)
        return self.client.post(reverse('insere_novo_responsavel'), dados, follow=True)

    def test_formulario_tem_secao_de_criancas_e_botao_mais_um(self):
        pagina = self.client.get(reverse('novo_responsavel')).content.decode()
        self.assertIn('Crianças da família', pagina)
        self.assertIn('id="adicionarFilho"', pagina)
        self.assertIn('+ 1 filho', pagina)
        self.assertIn('id="moldeFilho"', pagina)          # molde do bloco para o "+ 1 filho"

    def test_familia_com_tres_criancas(self):
        resposta = self.enviar(self.filho(0), self.filho(1, pnome='Ana', sexo='F', cpf=CPF_B),
                               self.filho(4, pnome='Caio', sapato=''))   # bloco 2 e 3 foram removidos
        self.assertContains(resposta, 'cadastrada com 3 criança(s)')
        resp = TbCadastroResponsavel.objects.get()
        filhos = list(TbFilhosResponsavel.objects.filter(id_responsavel=resp).order_by('id_filho'))
        self.assertEqual([f.pnome for f in filhos], ['Filho0', 'Ana', 'Caio'])
        ana = filhos[1]
        self.assertEqual((ana.sexo, ana.cpf, ana.data_nascimento, ana.numero_sapato, ana.flag_ativo),
                         ('F', CPF_B, '10/05/2018', 28, 'S'))
        self.assertIsNone(filhos[2].numero_sapato)
        self.assertEqual(resp.data_nascimento, '15/03/1988')

    def test_familia_sem_criancas_tambem_pode(self):
        self.assertContains(self.enviar(), 'cadastrada com 0 criança(s)')
        self.assertEqual(TbCadastroResponsavel.objects.count(), 1)

    def test_erro_em_uma_crianca_nao_grava_nada_e_volta_tudo_preenchido(self):
        resposta = self.enviar(self.filho(0, pnome='Lia'), self.filho(1, pnome='Teo', dt_nasc='31/02/2019'))
        self.assertEqual(resposta.status_code, 400)
        html = resposta.content.decode()
        self.assertIn('Data inválida', html)
        self.assertIn('value="Lia"', html)                 # crianças voltam preenchidas
        self.assertIn('value="Teo"', html)
        self.assertIn('value="Maria"', html)               # e o responsável também
        self.assertFalse(TbCadastroResponsavel.objects.exists())   # nada gravado pela metade
        self.assertFalse(TbFilhosResponsavel.objects.exists())

    def test_validacoes_das_criancas(self):
        resposta = self.enviar(
            self.filho(0, pnome='', sexo=''),
            self.filho(1, cpf='123.456.789-00'),
            self.filho(2, cpf=CPF_B), self.filho(3, cpf=CPF_B),       # mesmo CPF duas vezes
            self.filho(5, dt_nasc='01/01/2999', sapato='trinta'),
        )
        html = resposta.content.decode()
        for aviso in ('Informe o nome da criança.', 'Escolha o sexo.', 'CPF inválido',
                      'É o mesmo CPF da criança 3', 'A data não pode ser no futuro', 'Use só números'):
            self.assertIn(aviso, html)
        self.assertFalse(TbFilhosResponsavel.objects.exists())

    def test_cpf_de_crianca_ja_cadastrada_e_recusado(self):
        outra = criar_responsavel(cpf=CPF_C)
        TbFilhosResponsavel.objects.create(id_responsavel=outra, pnome='X', cpf=CPF_B, flag_ativo='S')
        resposta = self.enviar(self.filho(0, cpf=CPF_B))
        self.assertContains(resposta, 'Já existe uma criança cadastrada com este CPF', status_code=400)
        self.assertEqual(TbCadastroResponsavel.objects.count(), 1)   # só a família que já existia

    def test_responsavel_com_campos_vazios_e_avisado_no_campo(self):
        resposta = self.enviar(self.filho(0), endereco='', bairro='', dt_nasc='')
        html = resposta.content.decode()
        for aviso in ('Informe o endereço.', 'Informe o bairro.', 'Informe a data de nascimento.'):
            self.assertIn(aviso, html)
        self.assertEqual(resposta.status_code, 400)


# ----------------------------------------------------------------------
# Telas de adicionar e editar UMA criança (mesmas regras do cadastro de família)
# ----------------------------------------------------------------------
class CriancaAvulsaTests(BaseLogado):
    def setUp(self):
        super().setUp()
        self.resp = criar_responsavel(snome='Prado')

    def dados(self, **extra):
        d = {'pnome': 'Bia', 'snome': 'Prado', 'dt_nasc': '01/02/2024', 'cpf': '', 'sexo': 'F',
             'roupa': '', 'sapato': '', 'outra_ong': 'N'}
        d.update(extra)
        return {'responsavel': self.resp.pk, **{f'filho-0-{k}': v for k, v in d.items()}}

    def test_crianca_pequena_sem_cpf_roupa_e_sapato(self):
        resposta = self.client.post(reverse('insere_novo_filho'), self.dados(), follow=True)
        self.assertContains(resposta, 'Bia Prado foi cadastrado(a)')
        bia = TbFilhosResponsavel.objects.get()
        self.assertEqual((bia.cpf, bia.numero_roupa, bia.numero_sapato), (None, None, None))

    def test_sapato_com_letras_nao_da_mais_erro_500(self):
        resposta = self.client.post(reverse('insere_novo_filho'), self.dados(sapato='28a'))
        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, 'Use só números', status_code=400)
        self.assertContains(resposta, 'value="Bia"', status_code=400)       # volta preenchido
        self.assertFalse(TbFilhosResponsavel.objects.exists())

    def test_nome_e_data_conferidos_no_servidor(self):
        resposta = self.client.post(reverse('insere_novo_filho'), self.dados(pnome='', dt_nasc='30/02/2020'))
        self.assertContains(resposta, 'Informe o nome da criança.', status_code=400)
        self.assertContains(resposta, 'Data inválida', status_code=400)

    def test_formulario_novo_ja_traz_o_sobrenome_da_familia(self):
        pagina = self.client.get(reverse('novo_filho', args=[self.resp.pk])).content.decode()
        self.assertIn('value="Prado"', pagina)
        self.assertIn('crianças pequenas muitas vezes não têm', pagina)

    def _filho(self, **extra):
        d = dict(id_responsavel=self.resp, pnome='Caio', snome='Prado', data_nascimento='05/06/2015',
                 sexo='M', numero_roupa='10', numero_sapato=30, cpf=CPF_B, flag_ativo='S')
        d.update(extra)
        return TbFilhosResponsavel.objects.create(**d)

    def editar(self, filho, **extra):
        d = {'pnome': 'Caio', 'snome': 'Prado', 'dt_nasc': '05/06/2015', 'cpf': '***.***.***-35',
             'sexo': 'M', 'roupa': '10', 'sapato': '30', 'outra_ong': 'N'}
        d.update(extra)
        return self.client.post(reverse('atualiza_filho', args=[filho.pk]),
                                {f'filho-0-{k}': v for k, v in d.items()}, follow=True)

    def test_edicao_pode_apagar_roupa_e_sapato(self):
        """Antes, apagar o sapato e salvar fazia o número antigo voltar."""
        caio = self._filho()
        self.editar(caio, roupa='', sapato='')
        caio.refresh_from_db()
        self.assertEqual((caio.numero_roupa, caio.numero_sapato), (None, None))
        self.assertEqual(caio.cpf, CPF_B)                     # máscara mantida = CPF mantido

    def test_edicao_pode_apagar_o_cpf(self):
        caio = self._filho()
        self.editar(caio, cpf='')
        caio.refresh_from_db()
        self.assertIsNone(caio.cpf)

    def test_edicao_mostra_os_dados_atuais_com_cpf_mascarado(self):
        caio = self._filho()
        pagina = self.client.get(reverse('editar_filho', args=[caio.pk])).content.decode()
        for valor in ('value="Caio"', 'value="05/06/2015"', 'value="10"', 'value="30"', '***.***.***-35'):
            self.assertIn(valor, pagina)
        self.assertNotIn(CPF_B, pagina)

    def test_cancelar_da_edicao_e_um_link_e_nao_salva(self):
        """Antes o "Cancelar" ficava dentro do formulário e pedia para SALVAR."""
        caio = self._filho()
        pagina = self.client.get(reverse('editar_filho', args=[caio.pk])).content.decode()
        self.assertRegex(pagina, r'<a href="%s" class="btn btn-outline-secondary btn-lg px-4">\s*<i class="bi bi-x-circle"></i> Cancelar'
                         % reverse('lista_filhos', args=[self.resp.pk]))

    def test_edicao_com_erro_volta_preenchida(self):
        caio = self._filho()
        resposta = self.editar(caio, pnome='Caio Novo', sapato='trinta')
        self.assertContains(resposta, 'Use só números', status_code=400)
        self.assertContains(resposta, 'value="Caio Novo"', status_code=400)
        caio.refresh_from_db()
        self.assertEqual(caio.pnome, 'Caio')                   # nada foi salvo


# ----------------------------------------------------------------------
# Conferências "onde precisar": entregas, ofício, responsável, padrinho, ids
# ----------------------------------------------------------------------
class ConferenciasGeraisTests(BaseLogado):
    def test_entrega_sem_escolhas_avisa_em_vez_de_erro_500(self):
        resposta = self.client.post(reverse('insere_nova_entrega'),
                                    {'id_evento': '', 'id_mad_pad': '', 'id_crianca': ''}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Escolha o evento, o padrinho/madrinha, a criança')
        self.assertFalse(TbEntrega.objects.exists())

    def test_entrega_com_so_a_crianca_faltando(self):
        ev = TbEvento.objects.create(nome='Natal', data_evento='24/12/2026')
        mp = TbMadrinhaPadrinho.objects.create(pnome='P', flag_ativo='S')
        resposta = self.client.post(reverse('insere_nova_entrega'),
                                    {'id_evento': ev.pk, 'id_mad_pad': mp.pk, 'id_crianca': 'abc'}, follow=True)
        self.assertContains(resposta, 'Escolha a criança para registrar a entrega')

    def test_id_estranho_no_formulario_da_404_e_nao_500(self):
        self.assertEqual(self.client.post(reverse('atualiza_responsavel'), {'id_responsavel': 'xyz'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('insere_novo_filho'), {'responsavel': ''}).status_code, 404)

    def test_oficio_sem_destinatario_ou_mensagem(self):
        from gerencias.models import TbOficios
        resposta = self.client.post(reverse('insere_novo_oficio'), {'destinatario': ' ', 'mensagem': 'Oi'}, follow=True)
        self.assertContains(resposta, 'Preencha o destinatário e a mensagem')
        self.assertFalse(TbOficios.objects.exists())

    def test_editar_responsavel_sem_nome_nao_apaga(self):
        resp = criar_responsavel()
        resposta = self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': '', 'snome': 'Silva', 'cpf': '***', 'endereco': 'R',
            'bairro': 'B', 'cidade': 'C', 'estado': 'SP'}, follow=True)
        self.assertContains(resposta, 'Informe o primeiro nome.')
        resp.refresh_from_db()
        self.assertEqual(resp.pnome, 'Maria')

    def test_editar_responsavel_com_data_invalida(self):
        resp = criar_responsavel(data_nascimento='10/05/1990')
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'snome': 'Silva', 'cpf': '***', 'dt_nasc': '31/02/1990',
            'endereco': 'R', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP'})
        resp.refresh_from_db()
        self.assertEqual(resp.data_nascimento, '10/05/1990')

    def test_padrinho_anonimo_nao_precisa_de_nome_e_os_outros_precisam(self):
        self.client.post(reverse('inserir_madrinha_padrinho'), {'anonimo': 'S', 'pnome': '', 'flag_ativo': 'S'})
        self.assertTrue(TbMadrinhaPadrinho.objects.filter(pnome='Anônimo').exists())
        resposta = self.client.post(reverse('inserir_madrinha_padrinho'),
                                    {'anonimo': 'N', 'pnome': '', 'flag_ativo': 'S'}, follow=True)
        self.assertContains(resposta, 'Informe o nome do padrinho/madrinha')
        self.assertEqual(TbMadrinhaPadrinho.objects.count(), 1)

    def test_avisos_ligados_em_todas_as_paginas(self):
        pagina = self.client.get(reverse('novo_evento')).content.decode()
        self.assertIn('naire-validacao.js', pagina)
        self.assertIn('NaireValidacao.ativarTodos()', pagina)
        self.assertIn('data-validar="data-evento"', pagina)

    def test_lista_da_familia_tem_botao_editar_crianca(self):
        """Antes nenhuma página levava à tela de editar criança."""
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='Lia', flag_ativo='S')
        pagina = self.client.get(reverse('lista_filhos', args=[resp.pk])).content.decode()
        self.assertIn(f'href="{reverse("editar_filho", args=[filho.pk])}"', pagina)


# ----------------------------------------------------------------------
# Achados da revisão externa: anonimizados, sessão, senha atual, menu
# ----------------------------------------------------------------------
class RevisaoExternaTests(BaseLogado):
    def test_familia_anonimizada_nao_pode_ser_reativada(self):
        self.dar_permissao_lgpd()
        resp = criar_responsavel()
        filho = TbFilhosResponsavel.objects.create(id_responsavel=resp, pnome='A', flag_ativo='S')
        self.client.post(reverse('anonimizar_responsavel', args=[resp.pk]))
        resposta = self.client.post(reverse('reativar_responsavel', args=[resp.pk]), follow=True)
        self.assertContains(resposta, 'foi anonimizado (LGPD)')
        resp.refresh_from_db(); filho.refresh_from_db()
        self.assertEqual((resp.flag_ativo, filho.flag_ativo), ('N', 'N'))
        # nem a criança sozinha, nem pela edição
        self.client.post(reverse('reativar_filho', args=[filho.pk]))
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'snome': 'Silva', 'cpf': '***', 'endereco': 'R',
            'bairro': 'B', 'cidade': 'C', 'estado': 'SP', 'ativo': 'S'})
        resp.refresh_from_db(); filho.refresh_from_db()
        self.assertEqual((resp.flag_ativo, resp.pnome, filho.flag_ativo), ('N', 'Responsável', 'N'))
        self.assertEqual(self.client.get(reverse('editar_filho', args=[filho.pk])).status_code, 302)

    def test_padrinho_anonimizado_nao_pode_ser_reativado(self):
        self.dar_permissao_lgpd()
        mp = TbMadrinhaPadrinho.objects.create(pnome='P', flag_ativo='S')
        self.client.post(reverse('anonimizar_titular', args=[mp.pk]))
        self.client.post(reverse('reativar_madrinha_padrinho', args=[mp.pk]))
        mp.refresh_from_db()
        self.assertEqual(mp.flag_ativo, 'N')

    def test_sessao_conta_a_partir_da_ultima_atividade(self):
        from django.conf import settings
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_menu_usa_links_e_nao_formularios(self):
        """Formulários no menu faziam o F5 perguntar "reenviar formulário?"."""
        pagina = self.client.get(reverse('home')).content.decode()
        self.assertIn(f'class="dropdown-item" href="{reverse("lista_responsavel")}"', pagina)
        self.assertNotIn(f'<form action="{reverse("lista_responsavel")}"', pagina)
        # todos os destinos do menu abrem com um link (GET)
        import re
        for url in set(re.findall(r'class="dropdown-item" href="([^"]+)"', pagina)):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 200)


# ----------------------------------------------------------------------
# Finalizar entregas: uma a uma, ou todas juntas ao finalizar o evento
# ----------------------------------------------------------------------
class FinalizarEntregasTests(BaseLogado):
    def setUp(self):
        super().setUp()
        self.evento = TbEvento.objects.create(nome='Páscoa', data_evento='05/04/2027', endereco='Salão')
        self.outro = TbEvento.objects.create(nome='Natal', data_evento='20/12/2027', endereco='Salão')
        self.e1, self.e2 = [TbEntrega.objects.create(id_evento=self.evento.pk, flag_finalizado='N') for _ in range(2)]
        self.e3 = TbEntrega.objects.create(id_evento=self.outro.pk, flag_finalizado='N')

    def situacao(self, *entregas):
        for e in entregas:
            e.refresh_from_db()
        return [e.flag_finalizado for e in entregas]

    def test_finalizar_uma_entrega(self):
        resposta = self.client.post(reverse('finalizar_entrega', args=[self.e1.pk]), follow=True)
        self.assertContains(resposta, f'Entrega {self.e1.pk} finalizada')
        self.assertEqual(self.situacao(self.e1, self.e2, self.e3), ['S', 'N', 'N'])
        self.assertIsNotNone(self.e1.data_chegada)
        # A lista mostra "Reabrir" para a finalizada e "Finalizar" para as outras
        pagina = resposta.content.decode()
        self.assertIn(reverse('reabrir_entrega', args=[self.e1.pk]), pagina)
        self.assertIn(reverse('finalizar_entrega', args=[self.e2.pk]), pagina)
        self.assertNotIn(reverse('finalizar_entrega', args=[self.e1.pk]), pagina)

    def test_so_aceita_post(self):
        self.client.get(reverse('finalizar_entrega', args=[self.e1.pk]))
        self.assertEqual(self.situacao(self.e1), ['N'])

    def test_reabrir_entrega_finalizada_por_engano(self):
        self.client.post(reverse('finalizar_entrega', args=[self.e1.pk]))
        self.client.post(reverse('reabrir_entrega', args=[self.e1.pk]))
        self.assertEqual(self.situacao(self.e1), ['N'])
        self.assertIsNone(self.e1.data_chegada)

    def test_finalizar_evento_finaliza_todas_as_entregas_dele(self):
        resposta = self.client.post(reverse('finalizar_evento', args=[self.evento.pk]), follow=True)
        self.assertContains(resposta, '2 entrega(s) dele também foram finalizadas')
        self.assertEqual(self.situacao(self.e1, self.e2, self.e3), ['S', 'S', 'N'])   # o outro evento não muda
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.flag_finalizado, 'S')
        # Evento finalizado: suas entregas não podem voltar a ficar pendentes
        resposta = self.client.post(reverse('reabrir_entrega', args=[self.e1.pk]), follow=True)
        self.assertContains(resposta, 'já foi finalizado')
        self.assertEqual(self.situacao(self.e1), ['S'])
        self.assertNotIn(reverse('reabrir_entrega', args=[self.e1.pk]),
                         self.client.get(reverse('listar_entregas')).content.decode())
        # e o botão "Finalizar" some do evento finalizado
        self.assertNotIn(reverse('finalizar_evento', args=[self.evento.pk]),
                         self.client.get(reverse('listar_eventos')).content.decode())

    def test_entrega_ja_finalizada_mantem_a_data_de_chegada(self):
        self.client.post(reverse('finalizar_entrega', args=[self.e1.pk]))
        self.e1.refresh_from_db()
        chegada = self.e1.data_chegada
        self.client.post(reverse('finalizar_evento', args=[self.evento.pk]))
        self.e1.refresh_from_db()
        self.assertEqual(self.e1.data_chegada, chegada)
