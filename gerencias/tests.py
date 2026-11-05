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
            'pnome': 'Ana', 'snome': 'Souza', 'cpf': '529.982.247-25',
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
            'responsavel': resp.pk, 'pnome': 'Joao', 'snome': 'Silva', 'sexo': 'M',
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
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'snome': 'Nova',
            'cpf': '***.***.***-25', 'dt_nasc': '', 'bairro': 'B', 'cidade': 'C', 'estado': 'SP',
            'validado': 'S', 'ativo': 'S',
        })
        resp.refresh_from_db()
        self.assertEqual(resp.cpf, CPF_A)
        self.assertEqual(resp.snome, 'Nova')

    def test_data_nascimento_em_branco_nao_apaga(self):
        resp = criar_responsavel(data_nascimento='10/05/1990')
        self.client.post(reverse('atualiza_responsavel'), {
            'id_responsavel': resp.pk, 'pnome': 'Maria', 'cpf': '***', 'dt_nasc': '',
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
            'responsavel': resp.pk, 'pnome': 'Novo Nome', 'cpf': '', 'sexo': 'M',
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
